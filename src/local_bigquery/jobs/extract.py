import duckdb
import fastavro
from sqlglot import exp

from local_bigquery.catalog import tables
from local_bigquery.errors import BigQueryError
from local_bigquery.jobs.storage import literal, written

FORMATS = {
    "CSV": "csv",
    "JSON": "json",
    "NEWLINE_DELIMITED_JSON": "json",
    "PARQUET": "parquet",
    "AVRO": "avro",
}
AVRO_CODECS = {"DEFLATE": "deflate", "SNAPPY": "snappy", "ZSTD": "zstandard"}
EXPORT_OPTIONS = {
    "uri": "destinationUri",
    "format": "destinationFormat",
    "header": "printHeader",
    "field_delimiter": "fieldDelimiter",
    "compression": "compression",
}


def _recode(target: str, codec: str):
    with open(target, "rb") as file:
        reader = fastavro.reader(file)
        schema, records = reader.writer_schema, list(reader)
    with open(target, "wb") as file:
        fastavro.writer(file, schema, records, codec=codec)


def write(
    cur: duckdb.DuckDBPyConnection, query: str, params: dict, config: dict
) -> int:
    kind = (config.get("destinationFormat") or "CSV").upper()
    if kind not in FORMATS:
        raise BigQueryError("invalid", f"Unsupported destination format: {kind}")
    options = [f"FORMAT {FORMATS[kind]}"]
    if kind == "CSV":
        options += [
            f"HEADER {str(config.get('printHeader', True)).lower()}",
            f"DELIMITER {literal(config.get('fieldDelimiter') or ',')}",
        ]
    compression = (config.get("compression") or "NONE").upper()
    codec = AVRO_CODECS.get(compression) if kind == "AVRO" else None
    if compression != "NONE" and kind != "AVRO":
        options.append(f"COMPRESSION {compression.lower()}")
    uris = config.get("destinationUris") or [config.get("destinationUri")]
    rows = 0
    for uri in uris:
        with written(uri.replace("*", "000000000000")) as target:
            (rows,) = cur.execute(
                f"COPY ({query}) TO {literal(target)} ({', '.join(options)})", params
            ).fetchone()
            if codec:
                _recode(target, codec)
    return rows


def run(cur: duckdb.DuckDBPyConnection, config: dict, upload: str | None) -> dict:
    source = config["sourceTable"]
    reference = (source["projectId"], source["datasetId"], source["tableId"])
    tables.load(*reference)
    write(cur, f"SELECT * FROM {tables.name(*reference)}", {}, config)
    uris = config.get("destinationUris") or [config.get("destinationUri")]
    return {"destinationUriFileCounts": ["1" for _ in uris], "inputBytes": "0"}


def export_config(tree: exp.Export) -> dict:
    config = {}
    for option in tree.args["options"].expressions:
        if isinstance(option, exp.FileFormatProperty):
            config["destinationFormat"] = option.this.name
        elif key := EXPORT_OPTIONS.get(option.name.lower()):
            value = option.args["value"]
            config[key] = value.this if isinstance(value, exp.Boolean) else value.name
    if not config.get("destinationUri"):
        raise BigQueryError("invalidQuery", "Option 'uri' is missing or empty.")
    kind = config.get("destinationFormat", "CSV").upper()
    if kind not in FORMATS or kind == "NEWLINE_DELIMITED_JSON":
        raise BigQueryError(
            "invalidQuery",
            f"'{kind}' is not a valid value; failed to set 'format' in EXPORT DATA OPTIONS",
        )
    return config
