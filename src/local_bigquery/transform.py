import base64
import datetime
from decimal import Decimal
from typing import Any, List, Optional

from duckdb.sqltypes import DuckDBPyType
from sqlglot import exp

from local_bigquery.models import (
    QueryParameter,
    QueryParameterValue,
    TableFieldSchema,
    TableRow,
    TableCell,
    QueryParameterType,
)

# sqlglot emits standard BigQuery type names; the REST API wants legacy ones.
BIGQUERY_LEGACY_TYPES = {
    "INT64": "INTEGER",
    "FLOAT64": "FLOAT",
    "BOOL": "BOOLEAN",
    "NUMERIC": "FLOAT",
    "BIGNUMERIC": "FLOAT",
    "DATETIME": "TIMESTAMP",
}

PARAM_DECODERS = {
    "STRING": lambda value: value,
    "INT64": int,
    "FLOAT64": float,
    "NUMERIC": float,
    "BIGNUMERIC": float,
    "BOOL": lambda value: value.lower() == "true",
    "BYTES": base64.b64decode,
    "DATE": datetime.date.fromisoformat,
    "TIME": datetime.time.fromisoformat,
    "TIMESTAMP": datetime.datetime.fromisoformat,
    "DATETIME": datetime.datetime.fromisoformat,
}


def strip_quotes(value: Optional[str]) -> Optional[str]:
    return value.strip("`'\"") or None if value else None


def quote_identifier(name: str) -> str:
    return exp.to_identifier(name, quoted=True).sql("duckdb")


def table_expr(
    project_id: Optional[str], dataset_id: Optional[str], table_id: Optional[str] = None
) -> exp.Table:
    catalog, db, table = (
        strip_quotes(part) for part in (project_id, dataset_id, table_id)
    )
    if table is None:
        catalog, db, table = None, catalog, db
    return exp.table_(table, db=db, catalog=catalog, quoted=True)


def bigquery_field_to_datatype(field: TableFieldSchema) -> exp.DataType:
    bigquery_type = (field.type or "").upper()
    if bigquery_type in {"RECORD", "STRUCT"}:
        datatype = exp.DataType(
            this=exp.DataType.Type.STRUCT,
            nested=True,
            expressions=[
                exp.ColumnDef(
                    this=exp.to_identifier(subfield.name, quoted=True),
                    kind=bigquery_field_to_datatype(subfield),
                )
                for subfield in field.fields or []
            ],
        )
    else:
        datatype = exp.DataType.build(bigquery_type, dialect="bigquery")
    if field.mode == "REPEATED":
        datatype = exp.DataType(
            this=exp.DataType.Type.ARRAY, nested=True, expressions=[datatype]
        )
    return datatype


def bigquery_schema_to_duckdb_sql(
    schema: Optional[List[TableFieldSchema]], table: exp.Table
) -> str:
    columns = [
        exp.ColumnDef(
            this=exp.to_identifier(field.name, quoted=True),
            kind=bigquery_field_to_datatype(field),
            constraints=[exp.ColumnConstraint(kind=exp.NotNullColumnConstraint())]
            if field.mode == "REQUIRED"
            else [],
        )
        for field in schema or []
    ]
    create = exp.Create(kind="TABLE", this=exp.Schema(this=table, expressions=columns))
    return create.sql("duckdb")


def duckdb_field_to_bigquery_field(
    name: str,
    duckdb_type: Optional[DuckDBPyType] = None,
    datatype: Optional[exp.DataType] = None,
) -> TableFieldSchema:
    if datatype is None:
        datatype = exp.DataType.build(str(duckdb_type), dialect="duckdb")
    if datatype.this == exp.DataType.Type.ARRAY:
        field = duckdb_field_to_bigquery_field(name, datatype=datatype.expressions[0])
        field.mode = "REPEATED"
        return field
    if datatype.this == exp.DataType.Type.STRUCT:
        return TableFieldSchema(
            mode="NULLABLE",
            name=name,
            type="RECORD",
            fields=[
                duckdb_field_to_bigquery_field(column.name, datatype=column.kind)
                for column in datatype.expressions
            ],
        )
    bigquery_type = datatype.sql("bigquery").split("(")[0].strip()
    return TableFieldSchema(
        mode="NULLABLE",
        name=name,
        type=BIGQUERY_LEGACY_TYPES.get(bigquery_type, bigquery_type),
        fields=None,
    )


def duckdb_fields_to_bigquery_fields(
    fields: list[tuple[str, DuckDBPyType]],
) -> List[TableFieldSchema]:
    return [
        duckdb_field_to_bigquery_field(name, duckdb_type)
        for name, duckdb_type in fields
    ]


def duckdb_value_to_bigquery_value(value: Any) -> TableCell:
    if value is None:
        return TableCell(v=None)
    if isinstance(value, bool):
        return TableCell(v=str(value).lower())
    if isinstance(value, (int, float, Decimal)):
        return TableCell(v=str(value))
    if isinstance(value, str):
        return TableCell(v=value)
    if isinstance(value, datetime.datetime):
        return TableCell(v=str(int(value.timestamp() * 1e6)))
    if isinstance(value, (datetime.date, datetime.time)):
        return TableCell(v=value.isoformat())
    if isinstance(value, list):
        return TableCell(v=[duckdb_value_to_bigquery_value(item) for item in value])
    if isinstance(value, dict):
        return TableCell(
            v=TableRow(f=[duckdb_value_to_bigquery_value(v) for _, v in value.items()])
        )
    if isinstance(value, bytes):
        return TableCell(v=base64.b64encode(value).decode("utf-8"))
    raise ValueError(f"Unsupported DuckDB type: {type(value)}. Value: {value}")


def duckdb_values_to_bigquery_values(values: list[Any]) -> list[TableRow]:
    return [
        TableRow(f=[duckdb_value_to_bigquery_value(cell) for cell in value])
        for value in values
    ]


def bigquery_param_to_duckdb_param(
    param_type: Optional[QueryParameterType], param_value: Optional[QueryParameterValue]
) -> Any:
    if not param_type or not param_value:
        return None
    if param_type.type == "ARRAY":
        return [
            bigquery_param_to_duckdb_param(param_type.arrayType, value)
            for value in param_value.arrayValues or []
        ]
    if param_type.type == "STRUCT":
        values = param_value.structValues or {}
        return {
            field.name: bigquery_param_to_duckdb_param(field.type, values[field.name])
            for field in param_type.structTypes or []
            if values.get(field.name)
        }
    decode = PARAM_DECODERS.get(param_type.type)
    return decode(param_value.value) if decode else None


def bigquery_params_to_duckdb_params(
    params: Optional[list[QueryParameter]],
) -> dict[str, Any]:
    output = {}
    unnamed_count = 0
    for param in params or []:
        if not param.parameterType or not param.parameterValue:
            continue
        name = param.name
        if not name:
            name = f"param{unnamed_count}"
            unnamed_count += 1
        output[name] = bigquery_param_to_duckdb_param(
            param.parameterType, param.parameterValue
        )
    return output
