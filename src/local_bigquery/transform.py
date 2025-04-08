from datetime import date, datetime
from typing import Any, List, Optional

from local_bigquery.models import QueryParameter, QueryParameterValue, TableFieldSchema


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
    nullable = "" if mode == "REQUIRED" else "NULL"
    return f"{name} {sql_type} {nullable}".strip()


def bigquery_schema_to_sql(schema: list, table_name: str) -> str:
    columns = ", ".join(field_to_sql(f) for f in schema)
    return f"CREATE TABLE {table_name} ({columns});"


def map_value_to_bq_type(value: Any) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "FLOAT"
    if isinstance(value, datetime):
        return "TIMESTAMP"
    if isinstance(value, date):
        return "DATE"
    if isinstance(value, bytes):
        return "BYTES"
    return "STRING"


def merge_types(types: List[str]) -> str:
    unique = set(types)
    # If all values have the same type, use it.
    if len(unique) == 1:
        return unique.pop()
    # Allow INTEGER alongside FLOAT to be promoted to FLOAT.
    if unique == {"INTEGER", "FLOAT"}:
        return "FLOAT"
    # For conflicting types default to STRING.
    return "STRING"


def infer_bigquery_schema(rows, columns) -> List[TableFieldSchema]:
    col_types = {col: [] for col in columns}
    col_required = {col: True for col in columns}

    for row in rows:
        for idx, value in enumerate(row):
            col_name = columns[idx]
            if value is None:
                col_required[col_name] = False
            else:
                col_types[col_name].append(map_value_to_bq_type(value))

    schema = []
    for col in columns:
        # If no data exists for this column, default to STRING.
        inferred_type = merge_types(col_types[col]) if col_types[col] else "STRING"
        mode = "REQUIRED" if col_required[col] else "NULLABLE"
        field_schema = TableFieldSchema(name=col, type=inferred_type, mode=mode)
        schema.append(field_schema)
    return schema


def convert_value(qpv: Optional[QueryParameterValue]) -> Any:
    if qpv is None:
        return None
    if qpv.value is not None:
        return qpv.value
    if qpv.arrayValues is not None:
        return [convert_value(item) for item in qpv.arrayValues]
    if qpv.structValues is not None:
        return {k: convert_value(v) for k, v in qpv.structValues.items()}
    if qpv.rangeValue is not None:
        start = convert_value(qpv.rangeValue.start)
        end = convert_value(qpv.rangeValue.end)
        return (start, end)
    return None


def query_params_to_duckdb(params: list[QueryParameter]) -> dict[str, Any]:
    if not params:
        return {}
    result = {}
    for i, param in enumerate(params):
        key = param.name if param.name else f"param{i}"
        result[key] = convert_value(param.parameterValue)
    return result


def convert_missing_fields(data):
    if isinstance(data, dict):
        return {k: convert_missing_fields(v) for k, v in data.items()}
    elif isinstance(data, list):
        new_list = [convert_missing_fields(item) for item in data]
        if new_list and all(isinstance(item, dict) for item in new_list):
            all_keys = set().union(*(item.keys() for item in new_list))
            new_list = [{key: d.get(key, None) for key in all_keys} for d in new_list]
        return new_list
    else:
        return data


def convert_nested_timestamps_to_bigquery_ints(results, schema_fields):
    transformed = []
    for row in results:
        new_row = []
        for cell, field in zip(row, schema_fields):
            if field.type and field.type.upper() == "TIMESTAMP" and cell:
                new_row.append(int(cell.timestamp()) * 1e6)
            else:
                new_row.append(cell)
        transformed.append(new_row)
    return transformed
