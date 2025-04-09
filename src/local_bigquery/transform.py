import datetime
from decimal import Decimal
from typing import Any, List, Optional

from duckdb.typing import DuckDBPyType

from local_bigquery.models import (
    QueryParameter,
    QueryParameterValue,
    TableFieldSchema,
    TableRow,
    TableCell,
)


def field_to_sql(field):
    name = field.name
    mode = field.mode or "NULLABLE"
    typ = (field.type or "").upper()

    if typ in {"RECORD", "STRUCT"}:
        subfields = ", ".join(field_to_sql(f) for f in field.fields or [])
        sql_type = f"STRUCT<{subfields}>"
    else:
        sql_type = typ

    if mode == "REPEATED":
        return f"{name} ARRAY<{sql_type}>"
    nullable = "NOT NULL" if mode == "REQUIRED" else ""
    return f"{name} {sql_type} {nullable}".strip()


def bigquery_schema_to_sql(schema: list, table_name: str) -> str:
    columns = ", ".join(field_to_sql(f) for f in schema)
    return f"CREATE TABLE {table_name} ({columns});"


def duckdb_field_to_bigquery_field(
    name: str,
    duckdb_type: DuckDBPyType,
) -> TableFieldSchema:
    mode = "NULLABLE"
    fields = None
    match duckdb_type.id:
        case "integer" | "bigint" | "smallint" | "tinyint":
            bigquery_type = "INTEGER"
        case "float" | "decimal":
            bigquery_type = "FLOAT"
        case "varchar":
            bigquery_type = "STRING"
            if str(duckdb_type) == "JSON":
                bigquery_type = "JSON"
        case "bytes":
            bigquery_type = "BYTES"
        case "boolean":
            bigquery_type = "BOOLEAN"
        case "date":
            bigquery_type = "DATE"
        case "time":
            bigquery_type = "TIME"
        case "timestamp" | "timestamp with time zone":
            bigquery_type = "TIMESTAMP"
        case "json":
            bigquery_type = "JSON"
        case "list":
            mode = "REPEATED"
            child_type = duckdb_type.children[0][1]
            if child_type.id == "struct":
                bigquery_type = "RECORD"
                fields = duckdb_fields_to_bigquery_fields(child_type.children)
            else:
                bigquery_type = duckdb_field_to_bigquery_field(name, child_type).type
        case "struct":
            bigquery_type = "RECORD"
            fields = [
                duckdb_field_to_bigquery_field(child_name, child_type)
                for child_name, child_type in duckdb_type.children
            ]
        case _:
            raise ValueError(f"Unsupported DuckDB type: {duckdb_type.id}")
    return TableFieldSchema(mode=mode, name=name, type=bigquery_type, fields=fields)


def duckdb_fields_to_bigquery_fields(
    fields: list[tuple[str, DuckDBPyType]],
) -> List[TableFieldSchema]:
    return [
        duckdb_field_to_bigquery_field(name, duckdb_type)
        for name, duckdb_type in fields
    ]


def bigquery_param_to_duckdb_param(param: Optional[QueryParameterValue]) -> Any:
    if param is None:
        return None
    if param.value:
        return param.value
    if param.arrayValues:
        return [bigquery_param_to_duckdb_param(item) for item in param.arrayValues]
    if param.structValues:
        return {
            k: bigquery_param_to_duckdb_param(v) for k, v in param.structValues.items()
        }
    if param.rangeValue:
        start = bigquery_param_to_duckdb_param(param.rangeValue.start)
        end = bigquery_param_to_duckdb_param(param.rangeValue.end)
        return start, end
    return None


def bigquery_params_to_duckdb_param(params: list[QueryParameter]) -> dict[str, Any]:
    return {
        param.name: bigquery_param_to_duckdb_param(param.parameterValue)
        for param in params or []
    }


def fill_missing_fields(data):
    if isinstance(data, dict):
        return {k: fill_missing_fields(v) for k, v in data.items()}
    elif isinstance(data, list):
        new_list = [fill_missing_fields(item) for item in data]
        if new_list and all(isinstance(item, dict) for item in new_list):
            all_keys = set().union(*(item.keys() for item in new_list))
            new_list = [{key: d.get(key, None) for key in all_keys} for d in new_list]
        return new_list
    else:
        return data


def duckdb_value_to_bigquery_value(value: Any) -> TableCell:
    if value is None:
        return TableCell(v=None)
    if isinstance(value, bool):
        return TableCell(v=str(value).lower())
    if isinstance(value, int) or isinstance(value, float) or isinstance(value, Decimal):
        return TableCell(v=str(value))
    if isinstance(value, str):
        return TableCell(v=value)
    if isinstance(value, datetime.datetime):
        return TableCell(v=str(int(value.timestamp() * 1e6)))
    if isinstance(value, datetime.date) or isinstance(value, datetime.time):
        return TableCell(v=value.isoformat())
    if isinstance(value, list):
        return TableCell(v=[duckdb_value_to_bigquery_value(item) for item in value])
    if isinstance(value, dict):
        return TableCell(
            v=TableRow(f=[duckdb_value_to_bigquery_value(v) for _, v in value.items()])
        )
    raise ValueError(f"Unsupported DuckDB type: {type(value)}. Value: {value}")


def duckdb_values_to_bigquery_values(values: list[Any]) -> list[TableRow]:
    return [
        TableRow(f=[duckdb_value_to_bigquery_value(cell) for cell in value])
        for value in values
    ]
