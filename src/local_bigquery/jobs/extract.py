import duckdb

from local_bigquery.catalog import tables
from local_bigquery.errors import BigQueryError
from local_bigquery.jobs.storage import literal, path

FORMATS = {
    "CSV": "csv",
    "NEWLINE_DELIMITED_JSON": "json",
    "PARQUET": "parquet",
    "AVRO": "avro",
}


def run(cur: duckdb.DuckDBPyConnection, config: dict, upload: str | None) -> dict:
    source = config["sourceTable"]
    reference = (source["projectId"], source["datasetId"], source["tableId"])
    tables.load(*reference)
    kind = config.get("destinationFormat") or "CSV"
    if kind not in FORMATS:
        raise BigQueryError("invalid", f"Unsupported destination format: {kind}")
    options = [f"FORMAT {FORMATS[kind]}"]
    if kind == "CSV":
        options += [
            f"HEADER {str(config.get('printHeader', True)).lower()}",
            f"DELIMITER {literal(config.get('fieldDelimiter') or ',')}",
        ]
    if compression := config.get("compression"):
        options.append(f"COMPRESSION {compression.lower()}")
    uris = config.get("destinationUris") or [config.get("destinationUri")]
    for uri in uris:
        target = path(cur, uri.replace("*", "000000000000"))
        cur.execute(
            f"COPY (SELECT * FROM {tables.name(*reference)}) "
            f"TO {literal(target)} ({', '.join(options)})"
        )
    return {"destinationUriFileCounts": ["1" for _ in uris], "inputBytes": "0"}
