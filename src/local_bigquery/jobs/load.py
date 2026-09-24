import contextlib
import io
import re

import duckdb
import fastavro
import pyarrow as pa
import pyarrow.orc

from local_bigquery.catalog import datasets, names, tables
from local_bigquery.engine import types
from local_bigquery.engine.database import quote
from local_bigquery.errors import DUCKDB_PREFIX, BigQueryError
from local_bigquery.jobs.storage import literal, paths
from local_bigquery.models import (
    JobConfigurationLoad,
    JobStatistics3,
    Table,
    TableFieldSchema,
)

ENCODINGS = {"UTF-8": "utf-8", "ISO-8859-1": "latin-1", "UTF-16LE": "utf-16"}
HIVE_KEY = re.compile(r"\{(\w+):(\w+)\}")
AVRO_TYPES = {
    "null": pa.null(),
    "boolean": pa.bool_(),
    "int": pa.int32(),
    "long": pa.int64(),
    "float": pa.float32(),
    "double": pa.float64(),
    "bytes": pa.binary(),
    "fixed": pa.binary(),
    "string": pa.string(),
    "enum": pa.string(),
}
AVRO_LOGICAL_TYPES = {
    "date": pa.date32(),
    "time-millis": pa.time32("ms"),
    "time-micros": pa.time64("us"),
    "timestamp-millis": pa.timestamp("ms", "UTC"),
    "timestamp-micros": pa.timestamp("us", "UTC"),
    "local-timestamp-millis": pa.timestamp("ms"),
    "local-timestamp-micros": pa.timestamp("us"),
}


def _arrow_type(avro, logical: bool) -> pa.DataType:
    if isinstance(avro, list):
        return _arrow_type(next((t for t in avro if t != "null"), "null"), logical)
    if isinstance(avro, str):
        return AVRO_TYPES[avro]
    if avro.get("logicalType") == "decimal":
        return pa.decimal128(avro["precision"], avro.get("scale", 0))
    if logical and avro.get("logicalType") in AVRO_LOGICAL_TYPES:
        return AVRO_LOGICAL_TYPES[avro["logicalType"]]
    match avro["type"]:
        case "record":
            fields = avro["fields"]
            return pa.struct(
                [(f["name"], _arrow_type(f["type"], logical)) for f in fields]
            )
        case "array":
            return pa.list_(_arrow_type(avro["items"], logical))
        case "map":
            return pa.map_(pa.string(), _arrow_type(avro["values"], logical))
    return _arrow_type(avro["type"], logical)


def _avro(data: bytes, config: JobConfigurationLoad) -> pa.Table:
    reader = fastavro.reader(io.BytesIO(data))
    schema = reader.writer_schema
    table = pa.Table.from_pylist(list(reader), pa.schema(_arrow_type(schema, True)))
    logical = bool(config.useAvroLogicalTypes)
    return table.cast(pa.schema(_arrow_type(schema, logical)))


def _orc(data: bytes, config: JobConfigurationLoad) -> pa.Table:
    return pyarrow.orc.read_table(pa.BufferReader(data))


ARROW_READERS = {"AVRO": _avro, "ORC": _orc}
FORMATS = {"CSV", "NEWLINE_DELIMITED_JSON", "PARQUET", *ARROW_READERS}


def validate(config: JobConfigurationLoad):
    kind = config.sourceFormat or "CSV"
    if kind not in FORMATS:
        raise BigQueryError("invalid", f"Invalid source format {kind}")


def _options(options: dict) -> str:
    return "".join(f", {key} = {value}" for key, value in options.items())


def _struct(fields: list[TableFieldSchema], type_of) -> str:
    pairs = (f"{literal(f.name)}: {literal(type_of(f))}" for f in fields)
    return "{" + ", ".join(pairs) + "}"


def _hive(config: JobConfigurationLoad) -> dict:
    options = config.hivePartitioningOptions
    if not options:
        return {}
    mode = options.mode or "AUTO"
    if mode == "STRINGS":
        return {"hive_partitioning": "true", "hive_types_autocast": "false"}
    if mode == "CUSTOM":
        keys = HIVE_KEY.findall(options.sourceUriPrefix or "")
        fields = [TableFieldSchema(name=key, type=kind) for key, kind in keys]
        return {
            "hive_partitioning": "true",
            "hive_types": _struct(fields, types.duckdb_type),
        }
    return {"hive_partitioning": "true"}


def _csv(config: JobConfigurationLoad, fields: list[TableFieldSchema]) -> dict:
    encoding = config.encoding or "UTF-8"
    if encoding not in ENCODINGS:
        raise BigQueryError("invalid", f"Unsupported encoding: {encoding}")
    skip = config.skipLeadingRows or 0
    options = {
        "delim": literal(config.fieldDelimiter or ","),
        "quote": literal('"' if config.quote is None else config.quote),
        "nullstr": literal(config.nullMarker or ""),
        "null_padding": str(bool(config.allowJaggedRows)).lower(),
        "encoding": literal(ENCODINGS[encoding]),
    }
    if fields:
        return options | {
            "columns": _struct(fields, lambda _: "VARCHAR"),
            "header": "false",
            "skip": skip,
            "auto_detect": "false",
        }
    if skip:
        return options | {"header": "true", "skip": skip - 1}
    return options


def _reader(
    cur, files: str, config: JobConfigurationLoad, fields: list[TableFieldSchema]
) -> str:
    kind = config.sourceFormat or "CSV"
    if reader := ARROW_READERS.get(kind):
        blobs = cur.sql(f"SELECT content FROM read_blob({files})").fetchall()
        loaded = [reader(content, config) for (content,) in blobs]
        cur.register(
            "_load_source", pa.concat_tables(loaded, promote_options="default")
        )
        return "_load_source"
    hive = _hive(config)
    if kind == "PARQUET":
        return f"read_parquet({files}{_options(hive)})"
    if kind == "NEWLINE_DELIMITED_JSON":
        textual = list(map(_textual, fields))
        columns = {"columns": _struct(textual, types.duckdb_type)} if fields else {}
        options = {"format": "'newline_delimited'"} | columns | hive
        return f"read_json({files}{_options(options)})"
    return f"read_csv({files}{_options(_csv(config, fields) | hive)})"


def _textual(field: TableFieldSchema) -> TableFieldSchema:
    if field.type == "BYTES":
        return field.replace(type="STRING")
    if field.fields:
        return field.replace(fields=list(map(_textual, field.fields)))
    return field


def _decoded(expression: str, field: TableFieldSchema, depth: int = 0) -> str:
    if field.mode == "REPEATED":
        element = field.replace(mode="NULLABLE")
        inner = _decoded(f"e{depth}", element, depth + 1)
        if inner == f"e{depth}":
            return expression
        return f"list_transform({expression}, e{depth} -> {inner})"
    if field.type == "RECORD":
        parts = {
            f.name: _decoded(f"{expression}.{quote(f.name)}", f, depth)
            for f in field.fields or []
        }
        if all(value.endswith(f".{quote(name)}") for name, value in parts.items()):
            return expression
        pairs = ", ".join(f"{quote(name)} := {value}" for name, value in parts.items())
        return f"CASE WHEN {expression} IS NOT NULL THEN struct_pack({pairs}) END"
    return f"from_base64({expression})" if field.type == "BYTES" else expression


def _projection(
    config: JobConfigurationLoad, fields: list[TableFieldSchema], columns: list[str]
) -> tuple[str, str]:
    if not fields:
        return "*", "false"
    typed = (config.sourceFormat or "CSV") != "CSV"
    casts, bad = [], []
    for field in fields:
        column, target = quote(field.name), types.duckdb_type(field)
        source = _decoded(column, field)
        if not typed and source != column:
            source = f"TRY({source})"
        cast = f"{'CAST' if typed else 'TRY_CAST'}({source} AS {target})"
        casts.append(f"{cast} AS {column}")
        if not typed:
            bad.append(f"({column} IS NOT NULL AND {cast} IS NULL)")
    if config.hivePartitioningOptions:
        declared = {field.name.casefold() for field in fields}
        casts += [quote(c) for c in columns if c.casefold() not in declared]
    return ", ".join(casts), " OR ".join(bad) or "false"


@contextlib.contextmanager
def _reading(locations: dict[str, str | None]):
    try:
        yield
    except (duckdb.Error, pa.ArrowException, ValueError) as error:
        message = DUCKDB_PREFIX.sub("", str(error).split("\n")[0])
        for local, uri in locations.items():
            message = message.replace(
                f' in file "{local}"', f" in file {uri}" if uri else ""
            )
        raise BigQueryError(
            "invalid", f"Error while reading data, error message: {message}"
        ) from None


def run(
    cur: duckdb.DuckDBPyConnection, config: JobConfigurationLoad, upload: str | None
) -> JobStatistics3:
    reference = tables.reference(config.destinationTable)
    datasets.get(*reference[:2])
    uris = config.sourceUris or []
    locations = (
        {upload: None} if upload else {p: uri for uri in uris for p in paths(cur, uri)}
    )
    sources = list(locations)
    files = f"[{', '.join(map(literal, sources))}]"
    fields = (config.schema_ and config.schema_.fields) or []
    with _reading(locations):
        reader = _reader(cur, files, config, fields)
        columns = cur.sql(f"SELECT * FROM {reader} LIMIT 0").columns
        projection, bad = _projection(config, fields, columns)
        total, rejected = cur.sql(
            f"SELECT count(*), count(*) FILTER ({bad}) FROM {reader}"
        ).fetchone()
    if rejected > (config.maxBadRecords or 0):
        raise BigQueryError(
            "invalid",
            "Error while reading data, error message: too many errors, giving up. "
            f"Rows: {total}; errors: {rejected}.",
        )
    query = f"SELECT {projection} FROM {reader} WHERE NOT ({bad})"
    prefix = f"Provided Schema does not match Table {names.label(*reference)}. "
    with _reading(locations):
        created = tables.write(
            cur, query, None, reference, config, "WRITE_APPEND", prefix
        )
    if created and fields:
        tables.annotate(reference, Table(schema=config.schema_))
    count, size = cur.sql(
        f"SELECT count(*), coalesce(sum(size), 0) FROM read_blob({files})"
    ).fetchone()
    output = tables.logical_bytes(total - rejected, len(tables.columns(*reference)))
    return JobStatistics3(
        inputFiles=str(count),
        inputFileBytes=str(size),
        outputRows=str(total - rejected),
        outputBytes=str(output),
        badRecords=str(rejected),
    )
