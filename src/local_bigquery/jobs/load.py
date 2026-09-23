import os

import duckdb

from local_bigquery.catalog import datasets, tables
from local_bigquery.engine import types
from local_bigquery.engine.database import quote
from local_bigquery.errors import BigQueryError
from local_bigquery.jobs.storage import literal, path
from local_bigquery.models import TableFieldSchema

READERS = {"PARQUET": "read_parquet", "AVRO": "read_avro", "ORC": "read_orc"}
FORMATS = {"CSV", "NEWLINE_DELIMITED_JSON", *READERS}


def validate(config: dict):
    kind = config.get("sourceFormat") or "CSV"
    if kind not in FORMATS:
        raise BigQueryError("invalid", f"Invalid source format {kind}")


def _options(options: dict) -> str:
    return "".join(f", {key} = {value}" for key, value in options.items())


def _struct(fields: list[TableFieldSchema], type_of) -> str:
    pairs = (f"{literal(f.name)}: {literal(type_of(f))}" for f in fields)
    return "{" + ", ".join(pairs) + "}"


def _reader(files: str, config: dict, fields: list[TableFieldSchema]) -> str:
    kind = config.get("sourceFormat") or "CSV"
    if kind == "NEWLINE_DELIMITED_JSON":
        columns = {"columns": _struct(fields, types.duckdb_type)} if fields else {}
        options = {"format": "'newline_delimited'"} | columns
        return f"read_json({files}{_options(options)})"
    if kind != "CSV":
        return f"{READERS.get(kind, 'read_' + kind.lower())}({files})"
    skip = int(config.get("skipLeadingRows") or 0)
    options = {
        "delim": literal(config.get("fieldDelimiter") or ","),
        "quote": literal(config.get("quote", '"')),
        "nullstr": literal(config.get("nullMarker") or ""),
        "null_padding": str(bool(config.get("allowJaggedRows"))).lower(),
    }
    if fields:
        options |= {
            "columns": _struct(fields, lambda _: "VARCHAR"),
            "header": "false",
            "skip": skip,
            "auto_detect": "false",
        }
    elif skip:
        options |= {"header": "true", "skip": skip - 1}
    return f"read_csv({files}{_options(options)})"


def _projection(config: dict, fields: list[TableFieldSchema]) -> tuple[str, str]:
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
    return ", ".join(casts), " OR ".join(bad) or "false"


def run(cur: duckdb.DuckDBPyConnection, config: dict, upload: str | None) -> dict:
    reference = tables.reference(config["destinationTable"])
    datasets.load(*reference[:2])
    uris = config.get("sourceUris") or []
    sources = [upload] if upload else [path(cur, uri) for uri in uris]
    fields = [
        TableFieldSchema.model_validate(field)
        for field in (config.get("schema") or {}).get("fields", [])
    ]
    reader = _reader(f"[{', '.join(map(literal, sources))}]", config, fields)
    projection, bad = _projection(config, fields)
    try:
        total, rejected = cur.sql(
            f"SELECT count(*), count(*) FILTER ({bad}) FROM {reader}"
        ).fetchone()
    except duckdb.Error as error:
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
    created = not tables.exists(*reference)
    if not created:
        tables.evolve(
            cur,
            reference,
            cur.sql(query),
            config.get("schemaUpdateOptions"),
            "Provided Schema does not match Table {}:{}.{}. ".format(*reference),
        )
    write = config.get("writeDisposition") or "WRITE_APPEND"
    tables.write(cur, query, None, reference, write, config.get("createDisposition"))
    if created and fields:
        tables.record(
            *reference, tables.defaults(*reference) | {"schema": config["schema"]}
        )
    return {
        "inputFiles": str(len(sources)),
        "inputFileBytes": str(
            sum(os.path.getsize(s) for s in sources if os.path.isfile(s))
        ),
        "outputRows": str(total - rejected),
        "outputBytes": "0",
        "badRecords": str(rejected),
    }
