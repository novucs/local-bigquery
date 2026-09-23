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

STORAGE_STATS = (
    "numRows",
    "numBytes",
    "numLongTermBytes",
    "numTotalLogicalBytes",
    "numActiveLogicalBytes",
    "numLongTermLogicalBytes",
)
DERIVED = ("schema", "type", *STORAGE_STATS)
STORED_TYPES = ("MATERIALIZED_VIEW", "SNAPSHOT")
RESULTS = "_results"
INGESTION_TIME = "_PARTITIONTIME"
LAYOUT = ("timePartitioning", "rangePartitioning", "clustering")


def reference(table: dict) -> tuple[str, str, str]:
    try:
        return table["projectId"], table["datasetId"], table["tableId"]
    except KeyError as error:
        raise BigQueryError(
            "invalid", f"Required parameter is missing: {error.args[0]}"
        ) from None


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
    stored = metadata.load("tables", project_id, dataset_id, table_id)
    if expired(stored):
        if rows:
            database.execute(
                f"DROP {rows[0][0]} IF EXISTS {name(project_id, dataset_id, table_id)}"
            )
        forget(project_id, dataset_id, table_id)
        return None
    if rows:
        return rows[0]
    return ("EMPTY", 0) if stored else None


def expired(stored: dict | None) -> bool:
    expiration = (stored or {}).get("expirationTime")
    return expiration is not None and int(expiration) <= int(metadata.now())


def defaults(project_id: str, dataset_id: str, table_id: str) -> dict:
    now = metadata.now()
    dataset = metadata.load("datasets", project_id, dataset_id) or {}
    expiration = dataset.get("defaultTableExpirationMs")
    return (
        {"expirationTime": str(int(now) + int(expiration))} if expiration else {}
    ) | {
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
            if column != INGESTION_TIME or dataset_id == RESULTS
        ]


def logical_bytes(rows: int, columns: int) -> int:
    return rows * columns * 8


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
        "numBytes": str(num_bytes := logical_bytes(num_rows, len(fields))),
        "numLongTermBytes": "0",
        "numTotalLogicalBytes": str(num_bytes),
        "numActiveLogicalBytes": str(num_bytes),
        "numLongTermLogicalBytes": "0",
    }


def _type(resource: dict, kind: str) -> str:
    return resource["type"] if resource.get("type") in STORED_TYPES else kind


def _select(fields: list[dict], paths: list[list[str]]) -> list[dict]:
    selected = []
    for field in fields:
        rest = [path[1:] for path in paths if path[0] == field["name"].casefold()]
        if not rest:
            continue
        if [] not in rest:
            field = field | {"fields": _select(field.get("fields", []), rest)}
        selected.append(field)
    return selected


def get(
    project_id: str,
    dataset_id: str,
    table_id: str,
    selected_fields: str | None = None,
    view: str | None = None,
) -> Table:
    resource = load(project_id, dataset_id, table_id)
    if view == "BASIC":
        resource = {k: v for k, v in resource.items() if k not in STORAGE_STATS}
    if selected_fields:
        paths = [f.strip().casefold().split(".") for f in selected_fields.split(",")]
        resource["schema"] = {"fields": _select(resource["schema"]["fields"], paths)}
    return Table.model_validate(resource)


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
        if expired(stored):
            continue
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
    metadata.delete("indexes", project_id, dataset_id, table_id)


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
    identity = {
        key: current[key]
        for key in defaults(project_id, dataset_id, table_id)
        if key in current
    }
    resource = identity | body if replace else metadata.merge(stored, body)
    return _store(
        project_id,
        dataset_id,
        table_id,
        resource | {"lastModifiedTime": metadata.now()},
    )


def evolve(
    cur: duckdb.DuckDBPyConnection,
    reference: tuple[str, str, str],
    relation: duckdb.DuckDBPyRelation,
    options: list[str] | None,
    prefix: str,
):
    existing = {f.name.casefold() for f in columns(*reference)}
    added = [
        (column, t)
        for column, t in zip(relation.columns, relation.types)
        if column.casefold() not in existing
    ]
    if added and "ALLOW_FIELD_ADDITION" not in (options or []):
        raise BigQueryError(
            "invalid", f"{prefix}Cannot add fields (field: {added[0][0]})"
        )
    for column, t in added:
        cur.execute(
            f"ALTER TABLE {name(*reference)} "
            f"ADD COLUMN {quote(column)} {types.normalised(t)}"
        )


def layout(columns: list[str], config: dict, write: str) -> dict:
    layout = {key: config[key] for key in LAYOUT if config.get(key)}
    names = {name.casefold() for name in columns}
    partitioning = (
        layout.get("timePartitioning") or layout.get("rangePartitioning") or {}
    )
    if (field := partitioning.get("field")) and field.casefold() not in names:
        raise BigQueryError(
            "invalid",
            "The field specified for partitioning cannot be found in the schema.",
        )
    for field in (layout.get("clustering") or {}).get("fields") or []:
        if field.casefold() not in names:
            raise BigQueryError(
                "invalid",
                "The field specified for clustering cannot be found in the schema. "
                f"Invalid field: {field}",
            )
    if config.get("schemaUpdateOptions") and write != "WRITE_APPEND":
        raise BigQueryError(
            "invalid",
            "Schema update options should only be specified with WRITE_APPEND "
            "disposition, or with WRITE_TRUNCATE disposition on a table partition.",
        )
    return layout


def annotate(reference: tuple[str, str, str], changes: dict):
    if changes:
        stored = metadata.load("tables", *reference) or defaults(*reference)
        record(*reference, stored | changes)


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
    forget(project_id, dataset_id, table_id)
