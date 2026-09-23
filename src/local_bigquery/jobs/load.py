import io
import re

import duckdb
import fastavro
import pyarrow as pa
import pyarrow.orc

from local_bigquery.catalog import datasets, tables
from local_bigquery.engine import types
from local_bigquery.engine.database import quote
from local_bigquery.errors import BigQueryError
from local_bigquery.jobs.storage import literal, paths
from local_bigquery.models import TableFieldSchema

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


def _avro(data: bytes, config: dict) -> pa.Table:
    reader = fastavro.reader(io.BytesIO(data))
    schema = reader.writer_schema
    table = pa.Table.from_pylist(list(reader), pa.schema(_arrow_type(schema, True)))
    logical = bool(config.get("useAvroLogicalTypes"))
    return table.cast(pa.schema(_arrow_type(schema, logical)))


def _orc(data: bytes, config: dict) -> pa.Table:
    return pyarrow.orc.read_table(pa.BufferReader(data))


ARROW_READERS = {"AVRO": _avro, "ORC": _orc}
FORMATS = {"CSV", "NEWLINE_DELIMITED_JSON", "PARQUET", *ARROW_READERS}


def validate(config: dict):
    kind = config.get("sourceFormat") or "CSV"
    if kind not in FORMATS:
        raise BigQueryError("invalid", f"Invalid source format {kind}")


def _options(options: dict) -> str:
    return "".join(f", {key} = {value}" for key, value in options.items())


def _struct(fields: list[TableFieldSchema], type_of) -> str:
    pairs = (f"{literal(f.name)}: {literal(type_of(f))}" for f in fields)
    return "{" + ", ".join(pairs) + "}"


def _hive(config: dict) -> dict:
    options = config.get("hivePartitioningOptions")
    if not options:
        return {}
    mode = options.get("mode") or "AUTO"
    if mode == "STRINGS":
        return {"hive_partitioning": "true", "hive_types_autocast": "false"}
    if mode == "CUSTOM":
        keys = HIVE_KEY.findall(options.get("sourceUriPrefix") or "")
        fields = [TableFieldSchema(name=key, type=kind) for key, kind in keys]
        return {
            "hive_partitioning": "true",
            "hive_types": _struct(fields, types.duckdb_type),
        }
    return {"hive_partitioning": "true"}


def _csv(config: dict, fields: list[TableFieldSchema]) -> dict:
    encoding = config.get("encoding") or "UTF-8"
    if encoding not in ENCODINGS:
        raise BigQueryError("invalid", f"Unsupported encoding: {encoding}")
    skip = int(config.get("skipLeadingRows") or 0)
    options = {
        "delim": literal(config.get("fieldDelimiter") or ","),
        "quote": literal(config.get("quote", '"')),
        "nullstr": literal(config.get("nullMarker") or ""),
        "null_padding": str(bool(config.get("allowJaggedRows"))).lower(),
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


def _reader(cur, files: str, config: dict, fields: list[TableFieldSchema]) -> str:
    kind = config.get("sourceFormat") or "CSV"
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
        columns = {"columns": _struct(fields, types.duckdb_type)} if fields else {}
        options = {"format": "'newline_delimited'"} | columns | hive
        return f"read_json({files}{_options(options)})"
    return f"read_csv({files}{_options(_csv(config, fields) | hive)})"


def _projection(
    config: dict, fields: list[TableFieldSchema], columns: list[str]
) -> tuple[str, str]:
    if not fields:
        return "*", "false"
    typed = (config.get("sourceFormat") or "CSV") != "CSV"
    casts, bad = [], []
    for field in fields:
        column, target = quote(field.name), types.duckdb_type(field)
        cast = f"{'CAST' if typed else 'TRY_CAST'}({column} AS {target})"
        casts.append(f"{cast} AS {column}")
        if not typed:
            bad.append(f"({column} IS NOT NULL AND {cast} IS NULL)")
    if config.get("hivePartitioningOptions"):
        declared = {field.name.casefold() for field in fields}
        casts += [quote(c) for c in columns if c.casefold() not in declared]
    return ", ".join(casts), " OR ".join(bad) or "false"


def run(cur: duckdb.DuckDBPyConnection, config: dict, upload: str | None) -> dict:
    reference = tables.reference(config["destinationTable"])
    datasets.load(*reference[:2])
    uris = config.get("sourceUris") or []
    sources = [upload] if upload else [p for uri in uris for p in paths(cur, uri)]
    files = f"[{', '.join(map(literal, sources))}]"
    fields = [
        TableFieldSchema.model_validate(field)
        for field in (config.get("schema") or {}).get("fields", [])
    ]
    try:
        reader = _reader(cur, files, config, fields)
        columns = cur.sql(f"SELECT * FROM {reader} LIMIT 0").columns
        projection, bad = _projection(config, fields, columns)
        total, rejected = cur.sql(
            f"SELECT count(*), count(*) FILTER ({bad}) FROM {reader}"
        ).fetchone()
    except (duckdb.Error, pa.ArrowException, ValueError) as error:
        message = str(error).split("\n")[0]
        raise BigQueryError(
            "invalid", f"Error while reading data, error message: {message}"
        )
    if rejected > int(config.get("maxBadRecords") or 0):
        raise BigQueryError(
            "invalid",
            "Error while reading data, error message: too many errors, giving up. "
            f"Rows: {total}; errors: {rejected}.",
        )
    query = f"SELECT {projection} FROM {reader} WHERE NOT ({bad})"
    relation = cur.sql(query)
    write = config.get("writeDisposition") or "WRITE_APPEND"
    layout = tables.layout(relation.columns, config, write)
    created = not tables.exists(*reference)
    if not created:
        tables.evolve(
            cur,
            reference,
            relation,
            config.get("schemaUpdateOptions"),
            "Provided Schema does not match Table {}:{}.{}. ".format(*reference),
        )
    tables.write(cur, query, None, reference, write, config.get("createDisposition"))
    schema = {"schema": config["schema"]} if created and fields else {}
    tables.annotate(reference, schema | layout)
    count, size = cur.sql(
        f"SELECT count(*), coalesce(sum(size), 0) FROM read_blob({files})"
    ).fetchone()
    return {
        "inputFiles": str(count),
        "inputFileBytes": str(size),
        "outputRows": str(total - rejected),
        "outputBytes": str(
            tables.logical_bytes(total - rejected, len(relation.columns))
        ),
        "badRecords": str(rejected),
    }
