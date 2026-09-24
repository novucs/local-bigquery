import duckdb
from sqlglot import exp

from local_bigquery.catalog import datasets, tables
from local_bigquery.jobs import query
from local_bigquery.sql.rules.tables import decorated

CLONES = {"SNAPSHOT": "CREATE SNAPSHOT TABLE", "CLONE": "CREATE TABLE"}


def _name(reference: tuple[str, str, str]) -> str:
    project_id, dataset_id, table_id = reference
    return exp.table_(table_id, dataset_id, project_id, quoted=True).sql("bigquery")


def _source(reference: tuple[str, str, str]) -> str:
    if source := decorated(*reference):
        return source
    tables.load(*reference)
    return tables.name(*reference)


def run(cur: duckdb.DuckDBPyConnection, config: dict, upload: str | None) -> dict:
    sources = config.get("sourceTables") or [config["sourceTable"]]
    references = [tables.reference(source) for source in sources]
    destination = tables.reference(config["destinationTable"])
    datasets.load(*destination[:2])
    select = " UNION ALL BY NAME ".join(
        f"SELECT * FROM {_source(reference)}" for reference in references
    )
    (copied,) = cur.sql(f"SELECT count(*) FROM ({select})").fetchone()
    if create := CLONES.get(config.get("operationType")):
        statement = f"{create} {_name(destination)} CLONE {_name(references[0])}"
        query.execute(cur, destination[0], None, {"query": statement})
    else:
        tables.write(cur, select, None, destination, config)
    return {"copiedRows": str(copied), "copiedLogicalBytes": "0"}
