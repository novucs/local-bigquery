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


def _without_null_elements(expression: str, column: str, t) -> str:
    if t.id not in ("list", "array"):
        return expression
    message = f"Array cannot have a null element; error in writing field {column}"
    return (
        f"CASE WHEN list_bool_or(list_transform({expression}, e -> e IS NULL)) "
        f"THEN error('{message.replace("'", "''")}') ELSE {expression} END"
    )


def unique(names: list[str]) -> list[str]:
    seen, result = set(), []
    for name in names:
        candidate, suffix = name, 0
        while candidate.casefold() in seen:
            suffix += 1
            candidate = f"{name}_{suffix}"
        seen.add(candidate.casefold())
        result.append(candidate)
    return result


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
        f"{_without_null_elements(types.cast(position, t), column, t)} AS {quote(column)}"
        for position, column, t in zip(
            positions, unique(relation.columns), relation.types
        )
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
    result = cur.sql(select, params=params)
    typed = ", ".join(
        f"CAST({quote(column)} AS {t}) AS {quote(column)}"
        if "JSON" in str(t)
        else quote(column)
        for column, t in zip(result.columns, result.types)
    )
    writer.register("result", result.to_arrow_reader())
    try:
        writer.execute(f"{statement} SELECT {typed} FROM result")
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
        f"FROM (SELECT {projection} FROM {source} ORDER BY rowid "
        f"LIMIT {limit} OFFSET {start})"
    ).fetchall()
    end = start + len(rows)
    return Page([row for (row,) in rows], total, str(end) if end < total else None)
