import json
from typing import Any

from local_bigquery.engine.database import quote
from local_bigquery.engine.types import RANGE_FIELDS, TO_DUCKDB
from local_bigquery.errors import BigQueryError
from local_bigquery.models import (
    QueryParameter,
    QueryParameterType,
    QueryParameterValue,
    RangeValue,
)


def _range(parameter_type: QueryParameterType) -> QueryParameterType:
    element = parameter_type.rangeElementType
    fields = [{"name": name, "type": element} for name in RANGE_FIELDS]
    return QueryParameterType(type="STRUCT", structTypes=fields)


def _duckdb_type(parameter_type: QueryParameterType) -> str:
    match parameter_type.type:
        case "RANGE":
            return _duckdb_type(_range(parameter_type))
        case "ARRAY":
            return f"{_duckdb_type(parameter_type.arrayType)}[]"
        case "STRUCT":
            fields = ", ".join(
                f"{quote(field.name)} {_duckdb_type(field.type)}"
                for field in parameter_type.structTypes or []
            )
            return f"STRUCT({fields})"
        case kind if kind in TO_DUCKDB:
            return TO_DUCKDB[kind]
    raise BigQueryError(
        "invalid", f"Unsupported parameter type: {parameter_type.dump()}"
    )


def _spec(parameter_type: QueryParameterType) -> Any:
    match parameter_type.type:
        case "RANGE":
            return _spec(_range(parameter_type))
        case "ARRAY":
            return [_spec(parameter_type.arrayType)]
        case "STRUCT":
            return {
                field.name: _spec(field.type)
                for field in parameter_type.structTypes or []
            }
    return "VARCHAR"


def _plain(
    parameter_type: QueryParameterType, value: QueryParameterValue | None
) -> Any:
    if value is None:
        return None
    match parameter_type.type:
        case "RANGE":
            bounds = value.rangeValue or RangeValue()
            return {
                name: _plain(parameter_type.rangeElementType, bound)
                for name, bound in zip(RANGE_FIELDS, (bounds.start, bounds.end))
            }
        case "ARRAY":
            return [
                _plain(parameter_type.arrayType, item)
                for item in value.arrayValues or []
            ]
        case "STRUCT":
            values = value.structValues or {}
            return {
                field.name: _plain(field.type, values.get(field.name))
                for field in parameter_type.structTypes or []
            }
    return value.value


def _decode(expression: str, parameter_type: QueryParameterType) -> str:
    match parameter_type.type:
        case "RANGE":
            return _decode(expression, _range(parameter_type))
        case "ARRAY":
            element = _decode("e", parameter_type.arrayType)
            return f"list_transform({expression}, e -> {element})"
        case "STRUCT":
            fields = ", ".join(
                f"{quote(field.name)} := "
                f"{_decode(f'{expression}.{quote(field.name)}', field.type)}"
                for field in parameter_type.structTypes or []
            )
            return f"struct_pack({fields})"
        case "BYTES":
            return f"from_base64({expression})"
    return f"CAST({expression} AS {_duckdb_type(parameter_type)})"


def bind(
    parameters: list[QueryParameter],
) -> tuple[dict[str, str], dict[str, Any]]:
    expressions, values, position = {}, {}, 0
    for parameter in parameters:
        name = parameter.name
        if not name:
            name, position = f"p{position}", position + 1
        parameter_type = parameter.parameterType or QueryParameterType()
        value = _plain(parameter_type, parameter.parameterValue)
        if parameter_type.type in ("ARRAY", "STRUCT", "RANGE"):
            spec = json.dumps(_spec(parameter_type)).replace("'", "''")
            source = f"from_json(${name}, '{spec}')"
            values[name] = None if value is None else json.dumps(value)
        else:
            source = f"${name}"
            values[name] = value
        target = _duckdb_type(parameter_type)
        expressions[name] = f"CAST({_decode(source, parameter_type)} AS {target})"
    return expressions, values
