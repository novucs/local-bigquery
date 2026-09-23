import json
from typing import Any

from local_bigquery.engine.database import quote
from local_bigquery.engine.types import TO_DUCKDB
from local_bigquery.errors import BigQueryError


def _duckdb_type(parameter_type: dict) -> str:
    match parameter_type.get("type"):
        case "ARRAY":
            return f"{_duckdb_type(parameter_type['arrayType'])}[]"
        case "STRUCT":
            fields = ", ".join(
                f"{quote(field['name'])} {_duckdb_type(field['type'])}"
                for field in parameter_type.get("structTypes") or []
            )
            return f"STRUCT({fields})"
        case kind if kind in TO_DUCKDB:
            return TO_DUCKDB[kind]
    raise BigQueryError("invalid", f"Unsupported parameter type: {parameter_type}")


def _spec(parameter_type: dict) -> Any:
    match parameter_type.get("type"):
        case "ARRAY":
            return [_spec(parameter_type["arrayType"])]
        case "STRUCT":
            return {
                field["name"]: _spec(field["type"])
                for field in parameter_type.get("structTypes") or []
            }
    return "VARCHAR"


def _plain(parameter_type: dict, value: dict | None) -> Any:
    if value is None:
        return None
    match parameter_type.get("type"):
        case "ARRAY":
            return [
                _plain(parameter_type["arrayType"], item)
                for item in value.get("arrayValues") or []
            ]
        case "STRUCT":
            values = value.get("structValues") or {}
            return {
                field["name"]: _plain(field["type"], values.get(field["name"]))
                for field in parameter_type.get("structTypes") or []
            }
    return value.get("value")


def _decode(expression: str, parameter_type: dict) -> str:
    match parameter_type.get("type"):
        case "ARRAY":
            element = _decode("e", parameter_type["arrayType"])
            return f"list_transform({expression}, e -> {element})"
        case "STRUCT":
            fields = ", ".join(
                f"{quote(field['name'])} := "
                f"{_decode(f'{expression}.{quote(field["name"])}', field['type'])}"
                for field in parameter_type.get("structTypes") or []
            )
            return f"struct_pack({fields})"
        case "BYTES":
            return f"from_base64({expression})"
    return f"CAST({expression} AS {_duckdb_type(parameter_type)})"


def bind(parameters: list[dict]) -> tuple[dict[str, str], dict[str, Any]]:
    expressions, values, position = {}, {}, 0
    for parameter in parameters:
        name = parameter.get("name")
        if not name:
            name, position = f"p{position}", position + 1
        parameter_type = parameter.get("parameterType") or {}
        value = _plain(parameter_type, parameter.get("parameterValue"))
        if parameter_type.get("type") in ("ARRAY", "STRUCT"):
            spec = json.dumps(_spec(parameter_type)).replace("'", "''")
            source = f"from_json(${name}, '{spec}')"
            values[name] = None if value is None else json.dumps(value)
        else:
            source = f"${name}"
            values[name] = value
        target = _duckdb_type(parameter_type)
        expressions[name] = f"CAST({_decode(source, parameter_type)} AS {target})"
    return expressions, values
