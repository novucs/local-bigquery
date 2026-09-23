import json
import time

import duckdb

from local_bigquery.catalog import tables
from local_bigquery.catalog.tables import columns, create, get, load, name
from local_bigquery.engine import database, results
from local_bigquery.engine.database import quote
from local_bigquery.models import TableFieldSchema

DEDUP_SECONDS = 60
_recent: dict[tuple[str, str], float] = {}


def _spec_type(t) -> str:
    return "VARCHAR" if str(t) in ("JSON", "BLOB") else str(t)


def _select(column: str, t) -> str:
    if str(t) == "JSON":
        return f"CAST(r.{column} AS JSON)"
    if str(t) == "BLOB":
        return f"from_base64(r.{column})"
    return f"r.{column}"


def _template(project_id: str, dataset_id: str, table_id: str, suffix: str) -> str:
    template = get(project_id, dataset_id, table_id)
    if not tables.exists(project_id, dataset_id, table_id + suffix):
        create(
            project_id,
            dataset_id,
            {
                "tableReference": {"tableId": table_id + suffix},
                "schema": template.schema_.model_dump(exclude_none=True),
            },
            translate=None,
        )
    return table_id + suffix


def _problem(location: str, message: str) -> dict:
    return {"reason": "invalid", "location": location, "message": message}


def _unconvertible(schema: dict, rows: list[dict]) -> list[list[str]]:
    scalars = [
        (column, t)
        for column, t in schema.values()
        if t.id not in ("list", "array", "struct", "map")
        and str(t) not in ("JSON", "BLOB")
    ]
    if not scalars or not rows:
        return [[] for _ in rows]
    spec = json.dumps(
        [f"STRUCT({', '.join(f'{quote(column)} VARCHAR' for column, _ in scalars)})"]
    )
    checks = ", ".join(
        f"CASE WHEN r.{quote(column)} IS NOT NULL "
        f"AND TRY_CAST(r.{quote(column)} AS {t}) IS NULL THEN '{column}' END"
        for column, t in scalars
    )
    with database.cursor() as cur:
        found = cur.execute(
            f"SELECT list_filter([{checks}], f -> f IS NOT NULL) "
            "FROM (SELECT unnest(from_json($payload, $spec)) AS r)",
            {"payload": json.dumps(rows), "spec": spec},
        ).fetchall()
    return [columns for (columns,) in found]


def _deduplicate(table: str, rows: list) -> list:
    now = time.monotonic()
    for key, seen in list(_recent.items()):
        if now - seen > DEDUP_SECONDS:
            del _recent[key]
    unique = []
    for index, insert_id, data in rows:
        if insert_id is None or (table, insert_id) not in _recent:
            _recent[(table, insert_id)] = now
            unique.append((index, data))
    return unique


def insert_all(project_id: str, dataset_id: str, table_id: str, body: dict) -> dict:
    if suffix := body.get("templateSuffix"):
        table_id = _template(project_id, dataset_id, table_id, suffix)
    load(project_id, dataset_id, table_id)
    table = name(project_id, dataset_id, table_id)
    with database.cursor() as cur:
        relation = cur.sql(f"SELECT * FROM {table} LIMIT 0")
        schema = {
            c.casefold(): (c, t) for c, t in zip(relation.columns, relation.types)
        }
    required = [
        f.name
        for f in columns(project_id, dataset_id, table_id)
        if f.mode == "REQUIRED"
    ]
    rows = body.get("rows") or []
    known = [
        {
            schema[k.casefold()][0]: v
            for k, v in (row.get("json") or {}).items()
            if k.casefold() in schema
        }
        for row in rows
    ]
    unconvertible = _unconvertible(schema, known)
    errors, valid = [], []
    for index, row in enumerate(rows):
        problems = [
            _problem(key, f"no such field: {key}.")
            for key in row.get("json") or {}
            if key.casefold() not in schema and not body.get("ignoreUnknownValues")
        ]
        problems += [
            _problem(key, f"Missing required field: {key}.")
            for key in required
            if known[index].get(key) is None
        ]
        problems += [
            _problem(
                key,
                f"Cannot convert value to {schema[key.casefold()][1]}: {known[index][key]}",
            )
            for key in unconvertible[index]
        ]
        if problems:
            errors.append({"index": index, "errors": problems})
        else:
            valid.append((index, row.get("insertId"), known[index]))
    if errors and not body.get("skipInvalidRows"):
        stopped = {"reason": "stopped", "location": "", "message": ""}
        errors += [{"index": index, "errors": [stopped]} for index, _, _ in valid]
    else:
        errors += _insert(table, schema, _deduplicate(table, valid))
    return {"insertErrors": sorted(errors, key=lambda e: e["index"])} if errors else {}


def _insert(table: str, schema: dict, rows: list[tuple[int, dict]]) -> list[dict]:
    keys = list(dict.fromkeys(key for _, data in rows for key in data))
    if not keys:
        return []
    columns = [(quote(key), schema[key.casefold()][1]) for key in keys]
    spec = json.dumps(
        [f"STRUCT({', '.join(f'{c} {_spec_type(t)}' for c, t in columns)})"]
    )
    sql = (
        f"INSERT INTO {table} ({', '.join(c for c, _ in columns)}) "
        f"SELECT {', '.join(_select(c, t) for c, t in columns)} "
        "FROM (SELECT unnest(from_json($payload, $spec)) AS r)"
    )
    with database.cursor() as cur:
        try:
            payload = json.dumps([data for _, data in rows])
            cur.execute(sql, {"payload": payload, "spec": spec})
            return []
        except duckdb.Error:
            if len(rows) == 1:
                raise
        errors = []
        for index, data in rows:
            try:
                cur.execute(sql, {"payload": json.dumps([data]), "spec": spec})
            except duckdb.Error as error:
                errors.append(
                    {
                        "index": index,
                        "errors": [{"reason": "invalid", "message": str(error)}],
                    }
                )
        return errors


def list_rows(
    project_id: str,
    dataset_id: str,
    table_id: str,
    max_results: int | None,
    start: int,
    selected_fields: str | None,
    int64_timestamps: bool,
) -> tuple[results.Page, list[TableFieldSchema]]:
    load(project_id, dataset_id, table_id)
    fields = (
        [f.strip().casefold() for f in selected_fields.split(",")]
        if selected_fields
        else None
    )
    table = name(project_id, dataset_id, table_id)
    with database.cursor() as cur:
        page = results.page(cur, table, max_results, start, fields, int64_timestamps)
    schema = [
        f
        for f in columns(project_id, dataset_id, table_id)
        if not fields or f.name.casefold() in fields
    ]
    return page, schema
