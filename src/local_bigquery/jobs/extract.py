import duckdb
import fastavro
from sqlglot import exp

from local_bigquery.catalog import tables
from local_bigquery.errors import BigQueryError
from local_bigquery.jobs.storage import literal, written
from local_bigquery.models import JobConfigurationExtract, JobStatistics4

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
    cur: duckdb.DuckDBPyConnection,
    query: str,
    params: dict,
    config: JobConfigurationExtract,
) -> int:
    kind = (config.destinationFormat or "CSV").upper()
    if kind not in FORMATS:
        raise BigQueryError("invalid", f"Unsupported destination format: {kind}")
    options = [f"FORMAT {FORMATS[kind]}"]
    if kind == "CSV":
        options += [
            f"HEADER {str(config.printHeader is not False).lower()}",
            f"DELIMITER {literal(config.fieldDelimiter or ',')}",
        ]
    compression = (config.compression or "NONE").upper()
    codec = AVRO_CODECS.get(compression) if kind == "AVRO" else None
    if compression != "NONE" and kind != "AVRO":
        options.append(f"COMPRESSION {compression.lower()}")
    rows = 0
    for uri in _uris(config):
        with written(uri.replace("*", "000000000000")) as target:
            (rows,) = cur.execute(
                f"COPY ({query}) TO {literal(target)} ({', '.join(options)})", params
            ).fetchone()
            if codec:
                _recode(target, codec)
    return rows


def _uris(config: JobConfigurationExtract) -> list[str]:
    return config.destinationUris or [config.destinationUri]


def run(
    cur: duckdb.DuckDBPyConnection, config: JobConfigurationExtract, upload: str | None
) -> JobStatistics4:
    reference = tables.reference(config.sourceTable)
    tables.load(*reference)
    write(cur, f"SELECT * FROM {tables.name(*reference)}", {}, config)
    counts = ["1" for _ in _uris(config)]
    return JobStatistics4(destinationUriFileCounts=counts, inputBytes="0")


def export_config(tree: exp.Export) -> JobConfigurationExtract:
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
    return JobConfigurationExtract.model_validate(config)
