import json
import time

import duckdb

from local_bigquery.catalog import datasets, metadata
from local_bigquery.engine import database, results, types
from local_bigquery.engine.database import quote
from local_bigquery.errors import (
    BigQueryError,
    already_exists,
    not_found,
)
from local_bigquery.models import Table, TableFieldSchema

DERIVED = ("schema", "numRows", "numBytes", "type")
STORED_TYPES = ("MATERIALIZED_VIEW", "SNAPSHOT")
RESULTS = "_results"
DEDUP_SECONDS = 60
_recent: dict[tuple[str, str], float] = {}


def physical(project_id: str, dataset_id: str, table_id: str) -> tuple[str, str, str]:
    if dataset_id == RESULTS:
        return "emulator", RESULTS, f"{project_id}:{table_id}"
    return project_id, dataset_id, table_id


def name(project_id: str, dataset_id: str, table_id: str) -> str:
    return quote(*physical(project_id, dataset_id, table_id))


def exists(project_id: str, dataset_id: str, table_id: str) -> bool:
    return _lookup(project_id, dataset_id, table_id) is not None


def _lookup(project_id: str, dataset_id: str, table_id: str) -> tuple[str, int] | None:
    rows = database.fetch(
        "SELECT 'TABLE', estimated_size FROM duckdb_tables() "
        "WHERE database_name = ? AND schema_name = ? AND table_name = ? "
        "UNION ALL SELECT 'VIEW', 0 FROM duckdb_views() "
        "WHERE database_name = ? AND schema_name = ? AND view_name = ? AND NOT internal",
        list(physical(project_id, dataset_id, table_id)) * 2,
    )
    if rows:
        return rows[0]
    if metadata.load("tables", project_id, dataset_id, table_id):
        return "EMPTY", 0
    return None


def defaults(project_id: str, dataset_id: str, table_id: str) -> dict:
    now = metadata.now()
    return {
        "kind": "bigquery#table",
        "id": f"{project_id}:{dataset_id}.{table_id}",
        "selfLink": f"/bigquery/v2/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}",
        "tableReference": {
            "projectId": project_id,
            "datasetId": dataset_id,
            "tableId": table_id,
        },
        "location": "US",
        "creationTime": now,
        "lastModifiedTime": now,
    }


def _overlay(
    fields: list[dict], extras: list[dict], nested: bool = False
) -> list[dict]:
    extras_by_name = {extra["name"].casefold(): extra for extra in extras}
    merged = []
    for field in fields:
        extra = extras_by_name.get(field["name"].casefold(), {})
        children = _overlay(field.get("fields", []), extra.get("fields", []), True)
        field = extra | field | ({"fields": children} if children else {})
        if nested and extra.get("mode") == "REQUIRED":
            field["mode"] = "REQUIRED"
        merged.append(field)
    return merged


def columns(project_id: str, dataset_id: str, table_id: str) -> list[TableFieldSchema]:
    table = name(project_id, dataset_id, table_id)
    required = database.fetch(
        "SELECT column_name FROM duckdb_columns() WHERE database_name = ? "
        "AND schema_name = ? AND table_name = ? AND NOT is_nullable",
        list(physical(project_id, dataset_id, table_id)),
    )
    required = {column for (column,) in required}
    with database.cursor() as cur:
        relation = cur.sql(f"SELECT * FROM {table} LIMIT 0")
        return [
            types.field(column, t, column in required)
            for column, t in zip(relation.columns, relation.types)
        ]


def load(project_id: str, dataset_id: str, table_id: str) -> dict:
    found = _lookup(project_id, dataset_id, table_id)
    if not found:
        raise not_found("Table", f"{project_id}:{dataset_id}.{table_id}")
    kind, num_rows = found
    stored = metadata.load("tables", project_id, dataset_id, table_id)
    resource = stored or defaults(project_id, dataset_id, table_id)
    fields = (
        [
            field.model_dump(exclude_none=True)
            for field in columns(project_id, dataset_id, table_id)
        ]
        if kind != "EMPTY"
        else []
    )
    kind = "TABLE" if kind == "EMPTY" else kind
    extras = resource.get("schema", {}).get("fields", [])
    return resource | {
        "type": _type(resource, kind),
        "schema": {"fields": _overlay(fields, extras)},
        "numRows": str(num_rows),
        "numBytes": str(num_rows * len(fields) * 8),
    }


def _type(resource: dict, kind: str) -> str:
    return resource["type"] if resource.get("type") in STORED_TYPES else kind


def get(project_id: str, dataset_id: str, table_id: str) -> Table:
    return Table.model_validate(load(project_id, dataset_id, table_id))


def list_(project_id: str, dataset_id: str) -> list[dict]:
    datasets.load(project_id, dataset_id)
    rows = database.fetch(
        "SELECT table_name, 'TABLE' FROM duckdb_tables() "
        "WHERE database_name = ? AND schema_name = ? "
        "UNION ALL SELECT view_name, 'VIEW' FROM duckdb_views() "
        "WHERE database_name = ? AND schema_name = ? AND NOT internal ORDER BY 1",
        [project_id, dataset_id] * 2,
    )
    physical_ids = {table_id for table_id, _ in rows}
    rows += [
        (resource["tableReference"]["tableId"], "TABLE")
        for resource in metadata.list_("tables", project_id, dataset_id)
        if resource["tableReference"]["tableId"] not in physical_ids
    ]
    summaries = []
    for table_id, kind in sorted(rows):
        stored = metadata.load("tables", project_id, dataset_id, table_id)
        resource = stored or defaults(project_id, dataset_id, table_id)
        summaries.append(
            {key: value for key, value in resource.items() if key not in DERIVED}
            | {"type": _type(resource, kind)}
        )
    return summaries


def record(project_id: str, dataset_id: str, table_id: str, resource: dict):
    if partitioning := resource.get("timePartitioning"):
        partitioning.setdefault("type", "DAY")
    stored = {
        key: value
        for key, value in resource.items()
        if key not in DERIVED[1:] or value in STORED_TYPES
    }
    metadata.save("tables", stored, project_id, dataset_id, table_id)


def _store(project_id: str, dataset_id: str, table_id: str, resource: dict) -> Table:
    record(project_id, dataset_id, table_id, resource)
    return get(project_id, dataset_id, table_id)


def forget(project_id: str, dataset_id: str, table_id: str):
    metadata.delete("tables", project_id, dataset_id, table_id)


def rename(project_id: str, dataset_id: str, table_id: str, new_id: str):
    stored = metadata.load("tables", project_id, dataset_id, table_id)
    forget(project_id, dataset_id, table_id)
    if stored:
        fresh = defaults(project_id, dataset_id, new_id)
        identity = {key: fresh[key] for key in ("id", "selfLink", "tableReference")}
        record(project_id, dataset_id, new_id, stored | identity)


def create(project_id: str, dataset_id: str, body: dict, translate) -> Table:
    table_id = body.get("tableReference", {}).get("tableId")
    if not table_id:
        raise BigQueryError("invalid", "Required parameter is missing: tableId")
    datasets.load(project_id, dataset_id)
    if _lookup(project_id, dataset_id, table_id):
        raise already_exists("Table", f"{project_id}:{dataset_id}.{table_id}")
    table = name(project_id, dataset_id, table_id)
    fields = [
        TableFieldSchema.model_validate(field)
        for field in body.get("schema", {}).get("fields", [])
    ]
    if view := body.get("view"):
        query = translate(project_id, dataset_id, view["query"])
        database.execute(f"CREATE VIEW {table} AS {query}")
    elif fields:
        database.execute(
            f"CREATE TABLE {table} ({', '.join(types.column(f) for f in fields)})"
        )
    resource = defaults(project_id, dataset_id, table_id) | body
    return _store(project_id, dataset_id, table_id, resource)


def _alter(project_id: str, dataset_id: str, table_id: str, fields: list[dict]):
    table = name(project_id, dataset_id, table_id)
    current = {f.name.casefold(): f for f in columns(project_id, dataset_id, table_id)}
    given = {field["name"].casefold() for field in fields}
    if removed := [f.name for key, f in current.items() if key not in given]:
        raise BigQueryError(
            "invalid",
            f"Provided Schema does not match Table {project_id}:{dataset_id}.{table_id}. "
            f"Cannot remove field: {removed[0]}",
        )
    for field in map(TableFieldSchema.model_validate, fields):
        existing = current.get(field.name.casefold())
        if existing is None:
            database.execute(
                f"ALTER TABLE {table} ADD COLUMN {types.column(field, nested=True)}"
            )
        elif existing.mode == "REQUIRED" and field.mode != "REQUIRED":
            database.execute(
                f"ALTER TABLE {table} ALTER COLUMN {quote(field.name)} DROP NOT NULL"
            )


def update(
    project_id: str,
    dataset_id: str,
    table_id: str,
    body: dict,
    etag: str | None,
    replace: bool,
) -> Table:
    current = load(project_id, dataset_id, table_id)
    metadata.check_etag(current, etag)
    if fields := body.get("schema", {}).get("fields"):
        if _lookup(project_id, dataset_id, table_id)[0] == "EMPTY":
            columns_sql = ", ".join(
                types.column(TableFieldSchema.model_validate(f)) for f in fields
            )
            database.execute(
                f"CREATE TABLE {name(project_id, dataset_id, table_id)} ({columns_sql})"
            )
        else:
            _alter(project_id, dataset_id, table_id, fields)
    stored = metadata.load("tables", project_id, dataset_id, table_id) or current
    identity = {key: current[key] for key in defaults(project_id, dataset_id, table_id)}
    resource = identity | body if replace else metadata.merge(stored, body)
    return _store(
        project_id,
        dataset_id,
        table_id,
        resource | {"lastModifiedTime": metadata.now()},
    )


def write(
    cur: duckdb.DuckDBPyConnection,
    query: str,
    params: dict | None,
    reference: tuple[str, str, str],
    write_disposition: str,
    create_disposition: str | None = None,
    writer: duckdb.DuckDBPyConnection | None = None,
):
    table = name(*reference)
    found = exists(*reference)
    label = "{}:{}.{}".format(*reference)
    if not found and create_disposition == "CREATE_NEVER":
        raise not_found("Table", label)
    if found and write_disposition == "WRITE_EMPTY":
        if cur.sql(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
            raise already_exists("Table", label)
    append = found and write_disposition == "WRITE_APPEND"
    results.materialise(cur, query, table, params, append, writer)


def delete(project_id: str, dataset_id: str, table_id: str):
    kind, _ = _lookup(project_id, dataset_id, table_id) or (None, None)
    if kind is None:
        raise not_found("Table", f"{project_id}:{dataset_id}.{table_id}")
    if kind != "EMPTY":
        database.execute(f"DROP {kind} {name(project_id, dataset_id, table_id)}")
    metadata.delete("tables", project_id, dataset_id, table_id)


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
    if not _lookup(project_id, dataset_id, table_id + suffix):
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
