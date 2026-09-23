import datetime
import json

import sqlglot
from sqlglot import exp

from local_bigquery.catalog import datasets, metadata, tables
from local_bigquery.catalog import routines as catalog_routines
from local_bigquery.engine import database
from local_bigquery.engine.database import quote

TABLE_TYPES = {
    "TABLE": "BASE TABLE",
    "VIEW": "VIEW",
    "MATERIALIZED_VIEW": "MATERIALIZED VIEW",
    "SNAPSHOT": "SNAPSHOT",
}
IDENTITY = ("table_catalog", "table_schema", "table_name")
STANDARD_TYPES = {"INTEGER": "INT64", "FLOAT": "FLOAT64", "BOOLEAN": "BOOL"}
PARTITION_FORMATS = {"HOUR": "%Y%m%d%H", "DAY": "%Y%m%d", "MONTH": "%Y%m", "YEAR": "%Y"}
JOBS = """
SELECT
    job_id,
    project_id,
    resource ->> '$.configuration.jobType' AS job_type,
    resource ->> '$.statistics.query.statementType' AS statement_type,
    state,
    make_timestamp(creation_time * 1000) AS creation_time,
    resource ->> '$.user_email' AS user_email,
    resource ->> '$.configuration.query.query' AS query,
    parent_job_id,
    resource ->> '$.status.errorResult.reason' AS error_reason
FROM emulator.main.jobs
WHERE project_id = {project}
"""


def _type(field: dict) -> str:
    kind = STANDARD_TYPES.get(field["type"], field["type"])
    if kind in ("RECORD", "STRUCT"):
        kind = (
            f"STRUCT<{', '.join(f'{f["name"]} {_type(f)}' for f in field['fields'])}>"
        )
    return f"ARRAY<{kind}>" if field.get("mode") == "REPEATED" else kind


def _paths(fields: list[dict], prefix: str = "") -> list[tuple[str, dict]]:
    return [
        path
        for field in fields
        for path in [(prefix + field["name"], field)]
        + _paths(field.get("fields", []), f"{prefix}{field['name']}.")
    ]


def _timestamp(ms: str | None) -> exp.Expression:
    if not ms:
        return exp.null()
    moment = datetime.datetime.fromtimestamp(int(ms) / 1000, datetime.UTC)
    return exp.cast(
        exp.Literal.string(moment.isoformat()), exp.DataType.build("TIMESTAMPTZ")
    )


def _tables(project_id: str, dataset_id: str | None) -> list[dict]:
    dataset_ids = (
        [dataset_id]
        if dataset_id
        else [
            dataset.datasetReference.datasetId for dataset in datasets.list_(project_id)
        ]
    )
    listings = metadata.existing(tables.list_, [(project_id, ds) for ds in dataset_ids])
    references = [
        (
            project_id,
            summary["tableReference"]["datasetId"],
            summary["tableReference"]["tableId"],
        )
        for listing in listings
        for summary in listing
    ]
    return metadata.existing(tables.load, references)


def _identity(table: dict) -> list[str]:
    reference = table["tableReference"]
    return [reference["projectId"], reference["datasetId"], reference["tableId"]]


def schemata(project_id: str, dataset_id: str | None):
    columns = [
        "catalog_name",
        "schema_name",
        "location",
        "creation_time TIMESTAMP",
        "last_modified_time TIMESTAMP",
    ]
    rows = [
        [
            project_id,
            d.datasetReference.datasetId,
            d.location,
            _timestamp(d.creationTime),
            _timestamp(d.lastModifiedTime),
        ]
        for d in datasets.list_(project_id, all=True)
    ]
    return columns, rows


def table_list(project_id: str, dataset_id: str | None):
    columns = [
        *IDENTITY,
        "table_type",
        "is_insertable_into",
        "is_typed",
        "creation_time TIMESTAMP",
    ]
    rows = [
        _identity(t)
        + [
            TABLE_TYPES.get(t["type"], t["type"]),
            "YES" if t["type"] == "TABLE" else "NO",
            "NO",
            _timestamp(t.get("creationTime")),
        ]
        for t in _tables(project_id, dataset_id)
    ]
    return columns, rows


def _partitioning_column(table: dict) -> str | None:
    partitioning = table.get("timePartitioning") or table.get("rangePartitioning")
    return (partitioning or {}).get("field")


def _clustering_position(table: dict, name: str) -> exp.Expression:
    fields = [f.casefold() for f in (table.get("clustering") or {}).get("fields", [])]
    position = fields.index(name.casefold()) + 1 if name.casefold() in fields else None
    return exp.cast(exp.convert(position), "BIGINT")


def column_list(project_id: str, dataset_id: str | None):
    columns = [
        *IDENTITY,
        "column_name",
        "ordinal_position INT64",
        "is_nullable",
        "data_type",
        "is_generated",
        "is_hidden",
        "is_system_defined",
        "is_partitioning_column",
        "clustering_ordinal_position INT64",
    ]
    rows = [
        _identity(t)
        + [
            f["name"],
            position,
            "NO" if f.get("mode") == "REQUIRED" else "YES",
            _type(f),
            "NEVER",
            "NO",
            "NO",
            "YES" if f["name"] == _partitioning_column(t) else "NO",
            _clustering_position(t, f["name"]),
        ]
        for t in _tables(project_id, dataset_id)
        for position, f in enumerate(t["schema"]["fields"], start=1)
    ]
    return columns, rows


def column_field_paths(project_id: str, dataset_id: str | None):
    columns = [*IDENTITY, "column_name", "field_path", "data_type", "description"]
    rows = [
        _identity(t) + [path.split(".")[0], path, _type(f), f.get("description")]
        for t in _tables(project_id, dataset_id)
        for path, f in _paths(t["schema"]["fields"])
    ]
    return columns, rows


def views(project_id: str, dataset_id: str | None):
    columns = [*IDENTITY, "view_definition", "check_option", "use_standard_sql"]
    rows = [
        _identity(t) + [t["view"]["query"], None, "YES"]
        for t in _tables(project_id, dataset_id)
        if "view" in t
    ]
    return columns, rows


def _options(table: dict) -> list[tuple[str, str, str]]:
    options = []
    if "description" in table:
        options.append(("description", "STRING", json.dumps(table["description"])))
    if "friendlyName" in table:
        options.append(("friendly_name", "STRING", json.dumps(table["friendlyName"])))
    if labels := table.get("labels"):
        pairs = ", ".join(
            f"STRUCT({json.dumps(k)}, {json.dumps(v)})" for k, v in labels.items()
        )
        options.append(("labels", "ARRAY<STRUCT<STRING, STRING>>", f"[{pairs}]"))
    if "expirationTime" in table:
        moment = datetime.datetime.fromtimestamp(
            int(table["expirationTime"]) / 1000, datetime.UTC
        )
        options.append(
            ("expiration_timestamp", "TIMESTAMP", f'TIMESTAMP "{moment.isoformat()}"')
        )
    if table.get("requirePartitionFilter"):
        options.append(("require_partition_filter", "BOOL", "true"))
    return options


def table_options(project_id: str, dataset_id: str | None):
    columns = [*IDENTITY, "option_name", "option_type", "option_value"]
    rows = [
        _identity(t) + list(option)
        for t in _tables(project_id, dataset_id)
        for option in _options(t)
    ]
    return columns, rows


def _partitions(table: dict) -> list[tuple[str | None, int]]:
    name = tables.name(*_identity(table))
    partitioning = table.get("timePartitioning") or {}
    if not (field := partitioning.get("field")) or table["type"] != "TABLE":
        return [(None, int(table["numRows"]))]
    fmt = PARTITION_FORMATS.get(partitioning.get("type", "DAY"), "%Y%m%d")
    return database.fetch(
        f"SELECT coalesce(strftime({quote(field)}, '{fmt}'), '__NULL__'), count(*) "
        f"FROM {name} GROUP BY 1 ORDER BY 1"
    )


def partitions(project_id: str, dataset_id: str | None):
    columns = [*IDENTITY, "partition_id", "total_rows INT64", "storage_tier"]
    rows = [
        _identity(t) + [partition_id, total_rows, "ACTIVE"]
        for t in _tables(project_id, dataset_id)
        for partition_id, total_rows in _partitions(t)
    ]
    return columns, rows


def routines(project_id: str, dataset_id: str | None):
    columns = [
        "routine_catalog",
        "routine_schema",
        "routine_name",
        "routine_type",
        "routine_body",
        "data_type",
    ]
    rows = [
        [
            project_id,
            r["routineReference"]["datasetId"],
            r["routineReference"]["routineId"],
            catalog_routines.ROUTINE_TYPES[r["routineType"]],
            "EXTERNAL" if r.get("language") == "JAVASCRIPT" else "SQL",
            catalog_routines.sql_type(r["returnType"]) if "returnType" in r else None,
        ]
        for r in catalog_routines.list_(project_id, dataset_id)
    ]
    return columns, rows


def legacy_tables(project_id: str, dataset_id: str | None):
    columns = [
        "project_id",
        "dataset_id",
        "table_id",
        "creation_time INT64",
        "last_modified_time INT64",
        "row_count INT64",
        "size_bytes INT64",
        "type INT64",
    ]
    rows = [
        _identity(t)
        + [
            int(t.get("creationTime") or 0),
            int(t.get("lastModifiedTime") or 0),
            int(t["numRows"]),
            int(t["numBytes"]),
        ]
        + [1 if t["type"] == "TABLE" else 2]
        for t in _tables(project_id, dataset_id)
    ]
    return columns, rows


VIEWS = {
    "SCHEMATA": schemata,
    "TABLES": table_list,
    "COLUMNS": column_list,
    "COLUMN_FIELD_PATHS": column_field_paths,
    "VIEWS": views,
    "TABLE_OPTIONS": table_options,
    "PARTITIONS": partitions,
    "ROUTINES": routines,
    "__TABLES__": legacy_tables,
}


def _literal(value) -> exp.Expression:
    return value if isinstance(value, exp.Expression) else exp.convert(value)


def _values(columns: list[str], rows: list[list]) -> exp.Expression:
    specs = [column.partition(" ") for column in columns]
    names = [name for name, _, _ in specs]
    source = (
        exp.values(
            [tuple(map(_literal, row)) for row in rows], alias="v", columns=names
        )
        if rows
        else exp.select(*(exp.alias_(exp.null(), name) for name in names))
        .where(exp.false())
        .subquery("v")
    )
    return exp.select(
        *(
            exp.alias_(
                exp.cast(exp.column(name), kind or "STRING", dialect="bigquery"), name
            )
            for name, _, kind in specs
        )
    ).from_(source)


def _view(table: exp.Table) -> tuple[str, str, str | None] | None:
    name = table.name.upper()
    if name.startswith("INFORMATION_SCHEMA."):
        view, scope = name.removeprefix("INFORMATION_SCHEMA."), table.db
    elif table.db.upper() == "INFORMATION_SCHEMA":
        view, scope = name, table.catalog
    elif name == "__TABLES__":
        view, scope = name, table.db
    else:
        return None
    return view, table.catalog if scope == table.db else None, scope or None


def information_schema(tree: exp.Expression, context) -> exp.Expression:
    for table in list(tree.find_all(exp.Table)):
        if (found := _view(table)) is None:
            continue
        view, project_id, scope = found
        project_id = project_id or context.project_id
        dataset_id = (
            None
            if scope and scope.lower().startswith("region-")
            else scope or context.dataset_id
        )
        if view in ("JOBS", "JOBS_BY_PROJECT", "JOBS_BY_USER"):
            query = sqlglot.parse_one(
                JOBS.format(project=exp.Literal.string(project_id).sql()),
                dialect="duckdb",
            )
        elif view in VIEWS:
            query = _values(*VIEWS[view](project_id, dataset_id))
        else:
            continue
        alias = exp.TableAlias(this=exp.to_identifier(table.alias or view.lower()))
        table.replace(exp.Subquery(this=query, alias=alias))
    return tree


STATEMENT_RULES = [information_schema]
