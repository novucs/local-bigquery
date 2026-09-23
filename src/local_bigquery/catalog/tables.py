import json

import duckdb

from local_bigquery.catalog import datasets, metadata
from local_bigquery.engine import database, results, types
from local_bigquery.engine.database import quote
from local_bigquery.errors import (
    BigQueryError,
    already_exists,
    not_found,
    not_implemented,
)
from local_bigquery.models import Table, TableFieldSchema

DERIVED = ("schema", "numRows", "numBytes", "type")


def _lookup(project_id: str, dataset_id: str, table_id: str) -> tuple[str, int] | None:
    rows = database.fetch(
        "SELECT 'TABLE', estimated_size FROM duckdb_tables() "
        "WHERE database_name = ? AND schema_name = ? AND table_name = ? "
        "UNION ALL SELECT 'VIEW', 0 FROM duckdb_views() "
        "WHERE database_name = ? AND schema_name = ? AND view_name = ? AND NOT internal",
        [project_id, dataset_id, table_id] * 2,
    )
    return rows[0] if rows else None


def _defaults(project_id: str, dataset_id: str, table_id: str) -> dict:
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


def _overlay(fields: list[dict], extras: list[dict]) -> list[dict]:
    extras_by_name = {extra["name"].casefold(): extra for extra in extras}
    merged = []
    for field in fields:
        extra = extras_by_name.get(field["name"].casefold(), {})
        nested = _overlay(field.get("fields", []), extra.get("fields", []))
        field = extra | field | ({"fields": nested} if nested else {})
        merged.append(field)
    return merged


def columns(project_id: str, dataset_id: str, table_id: str) -> list[TableFieldSchema]:
    name = quote(project_id, dataset_id, table_id)
    required = database.fetch(
        "SELECT column_name FROM duckdb_columns() WHERE database_name = ? "
        "AND schema_name = ? AND table_name = ? AND NOT is_nullable",
        [project_id, dataset_id, table_id],
    )
    required = {column for (column,) in required}
    with database.cursor() as cur:
        relation = cur.sql(f"SELECT * FROM {name} LIMIT 0")
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
    resource = stored or _defaults(project_id, dataset_id, table_id)
    fields = [
        field.model_dump(exclude_none=True)
        for field in columns(project_id, dataset_id, table_id)
    ]
    extras = resource.get("schema", {}).get("fields", [])
    return resource | {
        "type": kind,
        "schema": {"fields": _overlay(fields, extras)},
        "numRows": str(num_rows),
        "numBytes": str(num_rows * len(fields) * 8),
    }


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
    summaries = []
    for table_id, kind in rows:
        stored = metadata.load("tables", project_id, dataset_id, table_id)
        resource = stored or _defaults(project_id, dataset_id, table_id)
        summaries.append(
            {key: value for key, value in resource.items() if key not in DERIVED}
            | {"type": kind}
        )
    return summaries


def _store(project_id: str, dataset_id: str, table_id: str, resource: dict) -> Table:
    if partitioning := resource.get("timePartitioning"):
        partitioning.setdefault("type", "DAY")
    stored = {key: value for key, value in resource.items() if key not in DERIVED[1:]}
    metadata.save("tables", stored, project_id, dataset_id, table_id)
    return get(project_id, dataset_id, table_id)


def create(project_id: str, dataset_id: str, body: dict, translate) -> Table:
    table_id = body.get("tableReference", {}).get("tableId")
    if not table_id:
        raise BigQueryError("invalid", "Required parameter is missing: tableId")
    datasets.load(project_id, dataset_id)
    if _lookup(project_id, dataset_id, table_id):
        raise already_exists("Table", f"{project_id}:{dataset_id}.{table_id}")
    name = quote(project_id, dataset_id, table_id)
    fields = [
        TableFieldSchema.model_validate(field)
        for field in body.get("schema", {}).get("fields", [])
    ]
    if view := body.get("view"):
        query = translate(project_id, dataset_id, view["query"])
        database.execute(f"CREATE VIEW {name} AS {query}")
    elif fields:
        database.execute(
            f"CREATE TABLE {name} ({', '.join(types.column(f) for f in fields)})"
        )
    else:
        raise not_implemented("Tables without a schema")
    resource = _defaults(project_id, dataset_id, table_id) | body
    return _store(project_id, dataset_id, table_id, resource)


def _alter(project_id: str, dataset_id: str, table_id: str, fields: list[dict]):
    name = quote(project_id, dataset_id, table_id)
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
                f"ALTER TABLE {name} ADD COLUMN {types.column(field, nested=True)}"
            )
        elif existing.mode == "REQUIRED" and field.mode != "REQUIRED":
            database.execute(
                f"ALTER TABLE {name} ALTER COLUMN {quote(field.name)} DROP NOT NULL"
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
        _alter(project_id, dataset_id, table_id, fields)
    stored = metadata.load("tables", project_id, dataset_id, table_id) or current
    identity = {
        key: current[key] for key in _defaults(project_id, dataset_id, table_id)
    }
    resource = identity | body if replace else metadata.merge(stored, body)
    return _store(
        project_id,
        dataset_id,
        table_id,
        resource | {"lastModifiedTime": metadata.now()},
    )


def delete(project_id: str, dataset_id: str, table_id: str):
    kind, _ = _lookup(project_id, dataset_id, table_id) or (None, None)
    if kind is None:
        raise not_found("Table", f"{project_id}:{dataset_id}.{table_id}")
    database.execute(f"DROP {kind} {quote(project_id, dataset_id, table_id)}")
    metadata.delete("tables", project_id, dataset_id, table_id)


def _spec_type(t) -> str:
    return "VARCHAR" if str(t) in ("JSON", "BLOB") else str(t)


def _select(column: str, t) -> str:
    if str(t) == "JSON":
        return f"CAST(r.{column} AS JSON)"
    if str(t) == "BLOB":
        return f"from_base64(r.{column})"
    return f"r.{column}"


def insert_all(project_id: str, dataset_id: str, table_id: str, body: dict) -> dict:
    if suffix := body.get("templateSuffix"):
        template = get(project_id, dataset_id, table_id)
        table_id += suffix
        if not _lookup(project_id, dataset_id, table_id):
            create(
                project_id,
                dataset_id,
                {
                    "tableReference": {"tableId": table_id},
                    "schema": template.schema_.model_dump(exclude_none=True),
                },
                translate=None,
            )
    load(project_id, dataset_id, table_id)
    name = quote(project_id, dataset_id, table_id)
    with database.cursor() as cur:
        relation = cur.sql(f"SELECT * FROM {name} LIMIT 0")
        schema = {
            c.casefold(): (c, t) for c, t in zip(relation.columns, relation.types)
        }
    required = {
        f.name
        for f in columns(project_id, dataset_id, table_id)
        if f.mode == "REQUIRED"
    }
    errors, valid, seen = [], [], set()
    for index, row in enumerate(body.get("rows") or []):
        data = row.get("json") or {}
        problems = [
            {"reason": "invalid", "location": key, "message": f"no such field: {key}."}
            for key in data
            if key.casefold() not in schema and not body.get("ignoreUnknownValues")
        ] + [
            {
                "reason": "invalid",
                "location": key,
                "message": f"Missing required field: {key}.",
            }
            for key in required
            if next(
                (v for k, v in data.items() if k.casefold() == key.casefold()), None
            )
            is None
        ]
        if problems:
            errors.append({"index": index, "errors": problems})
        elif (insert_id := row.get("insertId")) is None or insert_id not in seen:
            seen.add(insert_id)
            valid.append(
                (
                    index,
                    {
                        schema[k.casefold()][0]: v
                        for k, v in data.items()
                        if k.casefold() in schema
                    },
                )
            )
    if errors and not body.get("skipInvalidRows"):
        stopped = {"reason": "stopped", "location": "", "message": ""}
        errors += [{"index": index, "errors": [stopped]} for index, _ in valid]
        return {"insertErrors": sorted(errors, key=lambda e: e["index"])}
    errors += _insert(name, schema, valid)
    return {"insertErrors": sorted(errors, key=lambda e: e["index"])} if errors else {}


def _insert(name: str, schema: dict, rows: list[tuple[int, dict]]) -> list[dict]:
    keys = list(dict.fromkeys(key for _, data in rows for key in data))
    if not keys:
        return []
    columns = [(quote(key), schema[key.casefold()][1]) for key in keys]
    spec = json.dumps(
        [f"STRUCT({', '.join(f'{c} {_spec_type(t)}' for c, t in columns)})"]
    )
    sql = (
        f"INSERT INTO {name} ({', '.join(c for c, _ in columns)}) "
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
    name = quote(project_id, dataset_id, table_id)
    with database.cursor() as cur:
        page = results.page(cur, name, max_results, start, fields, int64_timestamps)
    schema = [
        f
        for f in columns(project_id, dataset_id, table_id)
        if not fields or f.name.casefold() in fields
    ]
    return page, schema
