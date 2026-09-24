import contextlib

import duckdb

from local_bigquery.catalog import datasets, metadata, names
from local_bigquery.engine import database, results, types
from local_bigquery.engine.database import quote
from local_bigquery.errors import (
    BigQueryError,
    already_exists,
    not_found,
)
from local_bigquery.models import (
    Dataset,
    MaterializedViewDefinition,
    Table,
    TableFieldSchema,
)

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
    rows = [
        row[1:] for row in database.objects(*physical(project_id, dataset_id, table_id))
    ]
    stored = metadata.load(Table, project_id, dataset_id, table_id)
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


def expired(stored: Table | None) -> bool:
    expiration = stored and stored.expirationTime
    return expiration is not None and int(expiration) <= int(metadata.now())


def fields(table: Table) -> list[TableFieldSchema]:
    return (table.schema_ and table.schema_.fields) or []


def defaults(project_id: str, dataset_id: str, table_id: str) -> Table:
    now = metadata.now()
    dataset = metadata.load(Dataset, project_id, dataset_id)
    expiration = dataset and dataset.defaultTableExpirationMs
    return Table.model_validate(
        ({"expirationTime": str(int(now) + int(expiration))} if expiration else {})
        | {
            "kind": "bigquery#table",
            "id": names.label(project_id, dataset_id, table_id),
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
    )


def _overlay(
    fields: list[TableFieldSchema],
    extras: list[TableFieldSchema],
    nested: bool = False,
) -> list[TableFieldSchema]:
    extras_by_name = {extra.name.casefold(): extra for extra in extras}
    merged = []
    for field in fields:
        extra = extras_by_name.get(field.name.casefold(), TableFieldSchema())
        children = _overlay(field.fields or [], extra.fields or [], True)
        field = extra.replace(
            **field.dump() | ({"fields": children} if children else {})
        )
        if nested and extra.mode == "REQUIRED":
            field = field.replace(mode="REQUIRED")
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


def load(project_id: str, dataset_id: str, table_id: str) -> Table:
    found = _lookup(project_id, dataset_id, table_id)
    if not found:
        raise not_found("Table", names.label(project_id, dataset_id, table_id))
    kind, num_rows = found
    stored = metadata.load(Table, project_id, dataset_id, table_id)
    resource = stored or defaults(project_id, dataset_id, table_id)
    actual = columns(project_id, dataset_id, table_id) if kind != "EMPTY" else []
    kind = "TABLE" if kind == "EMPTY" else kind
    num_bytes = str(logical_bytes(num_rows, len(actual)))
    return resource.replace(
        type=_type(resource, kind),
        schema={"fields": _overlay(actual, fields(resource))},
        numRows=str(num_rows),
        numBytes=num_bytes,
        numLongTermBytes="0",
        numTotalLogicalBytes=num_bytes,
        numActiveLogicalBytes=num_bytes,
        numLongTermLogicalBytes="0",
    )


def _type(resource: Table, kind: str) -> str:
    return resource.type if resource.type in STORED_TYPES else kind


def _select(
    fields: list[TableFieldSchema], paths: list[list[str]]
) -> list[TableFieldSchema]:
    selected = []
    for field in fields:
        rest = [path[1:] for path in paths if path[0] == field.name.casefold()]
        if not rest:
            continue
        if [] not in rest:
            field = field.replace(fields=_select(field.fields or [], rest))
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
        resource = resource.without(*STORAGE_STATS)
    if selected_fields:
        paths = [f.strip().casefold().split(".") for f in selected_fields.split(",")]
        resource = resource.replace(schema={"fields": _select(fields(resource), paths)})
    return resource


def list_(project_id: str, dataset_id: str) -> list[Table]:
    datasets.get(project_id, dataset_id)
    rows = [row[:2] for row in database.objects(project_id, dataset_id)]
    physical_ids = {table_id for table_id, _ in rows}
    rows += [
        (resource.tableReference.tableId, "TABLE")
        for resource in metadata.list_(Table, project_id, dataset_id)
        if resource.tableReference.tableId not in physical_ids
    ]
    summaries = []
    for table_id, kind in sorted(rows):
        stored = metadata.load(Table, project_id, dataset_id, table_id)
        if expired(stored):
            continue
        resource = stored or defaults(project_id, dataset_id, table_id)
        summaries.append(resource.without(*DERIVED).replace(type=_type(resource, kind)))
    return summaries


def record(project_id: str, dataset_id: str, table_id: str, resource: Table):
    if partitioning := resource.timePartitioning:
        resource = resource.replace(
            timePartitioning=partitioning.replace(type=partitioning.type or "DAY")
        )
    derived = STORAGE_STATS if resource.type in STORED_TYPES else DERIVED[1:]
    metadata.save(resource.without(*derived), project_id, dataset_id, table_id)


def _store(project_id: str, dataset_id: str, table_id: str, resource: Table) -> Table:
    record(project_id, dataset_id, table_id, resource)
    return get(project_id, dataset_id, table_id)


def forget(project_id: str, dataset_id: str, table_id: str):
    metadata.delete(Table, project_id, dataset_id, table_id)
    metadata.delete(metadata.Index, project_id, dataset_id, table_id)


def rename(project_id: str, dataset_id: str, table_id: str, new_id: str):
    stored = metadata.load(Table, project_id, dataset_id, table_id)
    forget(project_id, dataset_id, table_id)
    if stored:
        fresh = defaults(project_id, dataset_id, new_id)
        identity = fresh.only("id", "selfLink", "tableReference")
        record(project_id, dataset_id, new_id, stored.merged(identity))


def create(project_id: str, dataset_id: str, body: Table, translate) -> Table:
    table_id = body.tableReference and body.tableReference.tableId
    if not table_id:
        raise BigQueryError("invalid", "Required parameter is missing: tableId")
    names.table(table_id)
    names.fields(fields(body))
    datasets.get(project_id, dataset_id)
    if _lookup(project_id, dataset_id, table_id):
        raise already_exists("Table", names.label(project_id, dataset_id, table_id))
    table = name(project_id, dataset_id, table_id)
    if body.view:
        query = translate(project_id, dataset_id, body.view.query)
        database.execute(f"CREATE VIEW {table} AS {query}")
    elif fields(body):
        columns_sql = ", ".join(types.column(f) for f in fields(body))
        database.execute(f"CREATE TABLE {table} ({columns_sql})")
    resource = defaults(project_id, dataset_id, table_id).merged(body)
    return _store(project_id, dataset_id, table_id, resource)


def _alter(
    project_id: str, dataset_id: str, table_id: str, fields: list[TableFieldSchema]
):
    table = name(project_id, dataset_id, table_id)
    current = {f.name.casefold(): f for f in columns(project_id, dataset_id, table_id)}
    given = {field.name.casefold() for field in fields}
    if removed := [f.name for key, f in current.items() if key not in given]:
        raise BigQueryError(
            "invalid",
            f"Provided Schema does not match Table {names.label(project_id, dataset_id, table_id)}. "
            f"Cannot remove field: {removed[0]}",
        )
    for field in fields:
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
    body: Table,
    etag: str | None,
    replace: bool,
) -> Table:
    current = load(project_id, dataset_id, table_id)
    metadata.check_etag(current, etag)
    if given := fields(body):
        names.fields(given)
        if _lookup(project_id, dataset_id, table_id)[0] == "EMPTY":
            columns_sql = ", ".join(types.column(f) for f in given)
            database.execute(
                f"CREATE TABLE {name(project_id, dataset_id, table_id)} ({columns_sql})"
            )
        else:
            _alter(project_id, dataset_id, table_id, given)
    stored = metadata.load(Table, project_id, dataset_id, table_id) or current
    if replace:
        stored = current.only(*defaults(project_id, dataset_id, table_id).dump())
    resource = stored.merged(body).replace(lastModifiedTime=metadata.now())
    return _store(project_id, dataset_id, table_id, resource)


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


def refreshed(project_id: str, dataset_id: str, table_id: str):
    view = load(project_id, dataset_id, table_id).materializedView
    view = (view or MaterializedViewDefinition()).replace(
        lastRefreshTime=metadata.now()
    )
    annotate((project_id, dataset_id, table_id), Table(materializedView=view))


def annotate(reference: tuple[str, str, str], changes: Table):
    if changes.model_fields_set:
        stored = metadata.load(Table, *reference) or defaults(*reference)
        record(*reference, stored.replace(**changes.given()))


def write(
    cur: duckdb.DuckDBPyConnection,
    query: str,
    params: dict | None,
    reference: tuple[str, str, str],
    config: dict,
    default: str = "WRITE_EMPTY",
    prefix: str = "Invalid schema update. ",
    isolated: bool = False,
) -> bool:
    disposition = config.get("writeDisposition") or default
    relation = cur.sql(query, params=params)
    changes = layout(relation.columns, config, disposition)
    table, label = name(*reference), names.label(*reference)
    with (
        database.writing(*reference),
        database.cursor() if isolated else contextlib.nullcontext(cur) as writer,
    ):
        found = exists(*reference)
        if not found and config.get("createDisposition") == "CREATE_NEVER":
            raise not_found("Table", label)
        if found and disposition == "WRITE_EMPTY":
            if cur.sql(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                raise already_exists("Table", label)
        append = found and disposition == "WRITE_APPEND"
        if append:
            options = config.get("schemaUpdateOptions")
            evolve(writer, reference, relation, options, prefix)
        results.materialise(
            cur, query, table, params, append, writer if isolated else None
        )
    annotate(reference, Table.model_validate(changes))
    return not found


def delete(project_id: str, dataset_id: str, table_id: str):
    kind, _ = _lookup(project_id, dataset_id, table_id) or (None, None)
    if kind is None:
        raise not_found("Table", names.label(project_id, dataset_id, table_id))
    if kind != "EMPTY":
        database.execute(f"DROP {kind} {name(project_id, dataset_id, table_id)}")
    forget(project_id, dataset_id, table_id)
