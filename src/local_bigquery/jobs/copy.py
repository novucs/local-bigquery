import duckdb

from local_bigquery.catalog import datasets, tables


def _reference(table: dict) -> tuple[str, str, str]:
    return table["projectId"], table["datasetId"], table["tableId"]


def run(cur: duckdb.DuckDBPyConnection, config: dict, upload: str | None) -> dict:
    sources = config.get("sourceTables") or [config["sourceTable"]]
    references = [_reference(source) for source in sources]
    for reference in references:
        tables.load(*reference)
    destination = _reference(config["destinationTable"])
    datasets.load(*destination[:2])
    query = " UNION ALL BY NAME ".join(
        f"SELECT * FROM {tables.name(*reference)}" for reference in references
    )
    (copied,) = cur.sql(f"SELECT count(*) FROM ({query})").fetchone()
    write = config.get("writeDisposition") or "WRITE_EMPTY"
    tables.write(cur, query, None, destination, write, config.get("createDisposition"))
    return {"copiedRows": str(copied), "copiedLogicalBytes": "0"}
