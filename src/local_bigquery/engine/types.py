import itertools

from duckdb.sqltypes import DuckDBPyType

from local_bigquery.engine.database import quote
from local_bigquery.errors import BigQueryError
from local_bigquery.models import TableFieldSchema

TO_DUCKDB = {
    "STRING": "VARCHAR",
    "BYTES": "BLOB",
    "INTEGER": "BIGINT",
    "INT64": "BIGINT",
    "FLOAT": "DOUBLE",
    "FLOAT64": "DOUBLE",
    "NUMERIC": "DECIMAL(38,9)",
    "BIGNUMERIC": "DECIMAL(38,18)",
    "BIGDECIMAL": "DECIMAL(38,18)",
    "BOOLEAN": "BOOLEAN",
    "BOOL": "BOOLEAN",
    "TIMESTAMP": "TIMESTAMPTZ",
    "DATE": "DATE",
    "TIME": "TIME",
    "DATETIME": "TIMESTAMP",
    "GEOGRAPHY": "GEOMETRY",
    "JSON": "JSON",
    "INTERVAL": "INTERVAL",
}
SCALARS = {
    "boolean": ("BOOLEAN", "BOOLEAN"),
    "float": ("FLOAT", "DOUBLE"),
    "double": ("FLOAT", "DOUBLE"),
    "varchar": ("STRING", "VARCHAR"),
    "blob": ("BYTES", "BLOB"),
    "date": ("DATE", "DATE"),
    "time": ("TIME", "TIME"),
    "time with time zone": ("TIME", "TIME"),
    "timestamp with time zone": ("TIMESTAMP", "TIMESTAMPTZ"),
    "interval": ("INTERVAL", "INTERVAL"),
    "geometry": ("GEOGRAPHY", "GEOMETRY"),
    **dict.fromkeys(
        ["timestamp", "timestamp_s", "timestamp_ms", "timestamp_ns"],
        ("DATETIME", "TIMESTAMP"),
    ),
    **dict.fromkeys(
        [
            *("tinyint", "smallint", "integer", "bigint", "hugeint"),
            *("utinyint", "usmallint", "uinteger", "ubigint", "uhugeint"),
        ],
        ("INTEGER", "BIGINT"),
    ),
    **dict.fromkeys(["uuid", "enum", "bit", "bignum"], ("STRING", "VARCHAR")),
    **dict.fromkeys(["map", "union"], ("JSON", "JSON")),
}


def duckdb_type(field: TableFieldSchema) -> str:
    kind = (field.type or "STRING").upper()
    if kind in ("RECORD", "STRUCT"):
        name = (
            f"STRUCT({', '.join(column(f, nested=True) for f in field.fields or [])})"
        )
    elif kind in TO_DUCKDB:
        name = TO_DUCKDB[kind]
    else:
        raise BigQueryError("invalid", f"Unsupported field type: {field.type}")
    return f"{name}[]" if field.mode == "REPEATED" else name


def column(field: TableFieldSchema, nested: bool = False) -> str:
    sql = f"{quote(field.name)} {duckdb_type(field)}"
    return sql if nested or field.mode != "REQUIRED" else f"{sql} NOT NULL"


def _scalar(t: DuckDBPyType) -> tuple[str, str]:
    if str(t) == "JSON":
        return "JSON", "JSON"
    if t.id == "decimal":
        precision, scale = (value for _, value in t.children)
        if scale <= 9 and precision - scale <= 29:
            return "NUMERIC", "DECIMAL(38,9)"
        return "BIGNUMERIC", str(t)
    if t.id not in SCALARS:
        raise BigQueryError("invalidQuery", f"Unsupported result type: {t}")
    return SCALARS[t.id]


def _element(t: DuckDBPyType) -> DuckDBPyType | None:
    return t.children[0][1] if t.id in ("list", "array") else None


def field(name: str, t: DuckDBPyType, required: bool = False) -> TableFieldSchema:
    if element := _element(t):
        return field(name, element).model_copy(update={"mode": "REPEATED"})
    mode = "REQUIRED" if required else "NULLABLE"
    if t.id == "struct":
        fields = [field(child, child_type) for child, child_type in t.children]
        return TableFieldSchema(name=name, type="RECORD", mode=mode, fields=fields)
    return TableFieldSchema(name=name, type=_scalar(t)[0], mode=mode)


def normalised(t: DuckDBPyType) -> str:
    if element := _element(t):
        return f"{normalised(element)}[]"
    if t.id == "struct":
        return (
            f"STRUCT({', '.join(f'{quote(n)} {normalised(c)}' for n, c in t.children)})"
        )
    return _scalar(t)[1]


def cast(expression: str, t: DuckDBPyType) -> str:
    target = normalised(t)
    if target == str(t):
        return expression
    if t.id == "map" or t.id == "union":
        return f"to_json({expression})"
    return f"CAST({expression} AS {target})"


def encode(expression: str, t: DuckDBPyType, int64_timestamps: bool = True) -> str:
    return _encode(expression, t, int64_timestamps, itertools.count())


def _encode(x: str, t: DuckDBPyType, int64: bool, names: itertools.count) -> str:
    if element := _element(t):
        var = f"e{next(names)}"
        cell = _encode(var, element, int64, names)
        return f"coalesce(list_transform({x}, {var} -> {{'v': to_json({cell})}}), [])"
    if t.id == "struct":
        cells = ", ".join(
            f"{{'v': to_json({_encode(f'{x}.{quote(n)}', c, int64, names)})}}"
            for n, c in t.children
        )
        return f"CASE WHEN {x} IS NULL THEN NULL ELSE {{'f': [{cells}]}} END"
    match _scalar(t)[0]:
        case "BYTES":
            return f"base64({x})"
        case "FLOAT":
            return (
                f"CASE WHEN isnan({x}) THEN 'NaN' WHEN {x} = 'inf' THEN 'Infinity' "
                f"WHEN {x} = '-inf' THEN '-Infinity' ELSE CAST({x} AS VARCHAR) END"
            )
        case "NUMERIC" | "BIGNUMERIC":
            trimmed = rf"regexp_replace(CAST({x} AS VARCHAR), '(\.\d*?)0+$', '\1')"
            return rf"regexp_replace({trimmed}, '\.$', '')"
        case "DATETIME":
            return f"replace({_micros(x, 26)}, ' ', 'T')"
        case "TIME":
            return _micros(x, 15)
        case "TIMESTAMP" if int64:
            return f"CAST(epoch_us({x}) AS VARCHAR)"
        case "TIMESTAMP":
            return f"CAST(epoch_us({x}) / 1e6 AS VARCHAR)"
        case "JSON":
            return f"CAST(json({x}) AS VARCHAR)"
        case "GEOGRAPHY":
            return rf"regexp_replace(CAST({x} AS VARCHAR), '([A-Z]) \(', '\1(', 'g')"
        case "INTERVAL":
            parts = ", ".join(
                f"datepart('{part}', {x})"
                for part in ("year", "month", "day", "hour", "minute", "second")
            )
            micros = f"datepart('microsecond', {x}) % 1000000"
            fraction = f"rtrim(printf('.%06d', {micros}), '0')"
            return (
                f"printf('%d-%d %d %d:%d:%d', {parts}) "
                f"|| CASE WHEN {micros} = 0 THEN '' ELSE {fraction} END"
            )
    return f"CAST({x} AS VARCHAR)"


def _micros(x: str, width: int) -> str:
    text = f"CAST({x} AS VARCHAR)"
    return f"CASE WHEN contains({text}, '.') THEN rpad({text}, {width}, '0') ELSE {text} END"


def row(columns: list[tuple[str, DuckDBPyType]], int64_timestamps: bool = True) -> str:
    cells = ", ".join(
        f"{{'v': to_json({encode(quote(name), t, int64_timestamps)})}}"
        for name, t in columns
    )
    return f"to_json({{'f': [{cells}]}})"
