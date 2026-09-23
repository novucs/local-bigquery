from dataclasses import dataclass

import duckdb

from local_bigquery.engine import types
from local_bigquery.engine.database import quote
from local_bigquery.models import TableFieldSchema

DEFAULT_PAGE_SIZE = 100_000


@dataclass
class Page:
    rows: list[str]
    total: int
    next_token: str | None


def materialise(
    cur: duckdb.DuckDBPyConnection,
    query: str,
    name: str,
    params: dict | None = None,
    append: bool = False,
    writer: duckdb.DuckDBPyConnection | None = None,
):
    relation = cur.sql(query, params=params)
    positions = [f"c{index}" for index in range(len(relation.columns))]
    columns = ", ".join(
        f"{types.cast(position, t)} AS {quote(column)}"
        for position, column, t in zip(positions, relation.columns, relation.types)
    )
    select = f"SELECT {columns} FROM ({query}) AS q({', '.join(positions)})"
    statement = (
        f"INSERT INTO {name} BY NAME"
        if append
        else f"CREATE OR REPLACE TABLE {name} AS"
    )
    if writer is None:
        cur.execute(f"{statement} {select}", params)
        return
    writer.register("result", cur.sql(select, params=params).to_arrow_reader())
    try:
        writer.execute(f"{statement} SELECT * FROM result")
    finally:
        writer.unregister("result")


def schema(cur: duckdb.DuckDBPyConnection, source: str) -> list[TableFieldSchema]:
    relation = cur.sql(f"SELECT * FROM {source} LIMIT 0")
    return [types.field(n, t) for n, t in zip(relation.columns, relation.types)]


def page(
    cur: duckdb.DuckDBPyConnection,
    source: str,
    max_results: int | None = None,
    start: int = 0,
    fields: list[str] | None = None,
    int64_timestamps: bool = True,
) -> Page:
    total = cur.sql(f"SELECT count(*) FROM {source}").fetchone()[0]
    limit = DEFAULT_PAGE_SIZE if max_results is None else max_results
    relation = cur.sql(f"SELECT * FROM {source} LIMIT 0")
    columns = [
        (name, t)
        for name, t in zip(relation.columns, relation.types)
        if not fields or name.casefold() in fields
    ]
    projection = ", ".join(quote(name) for name, _ in columns) or "NULL"
    rows = cur.sql(
        f"SELECT {types.row(columns, int64_timestamps)} "
        f"FROM (SELECT {projection} FROM {source} LIMIT {limit} OFFSET {start})"
    ).fetchall()
    end = start + len(rows)
    return Page([row for (row,) in rows], total, str(end) if end < total else None)
