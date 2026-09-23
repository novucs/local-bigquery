import datetime
import functools
import re
import time

import sqlglot
from sqlglot import exp

from local_bigquery.catalog import metadata, tables
from local_bigquery.engine import database
from local_bigquery.errors import BigQueryError

DATASET_ID = re.compile(r"^[\w-]{1,1024}$")
DECORATOR = re.compile(r"^(.+)@(-?\d+)$")
DML = exp.Insert | exp.Update | exp.Delete | exp.Merge | exp.TruncateTable


def _temporary(tree: exp.Expression) -> bool:
    return tree.find(exp.TemporaryProperty) is not None


def _target(tree: exp.Expression) -> exp.Table | None:
    if isinstance(tree, exp.Create | exp.Drop | exp.Alter | DML):
        target = tree.this if isinstance(tree.this, exp.Expression) else None
        target = target.this if isinstance(target, exp.Schema) else target
        return target if isinstance(target, exp.Table) else tree.find(exp.Table)
    return None


def _not_found(project_id: str, dataset_id: str, table_id: str) -> BigQueryError:
    table = f"{project_id}:{dataset_id}.{table_id}"
    if project_id not in database.projects():
        return BigQueryError(
            "accessDenied",
            f"Access Denied: Table {table}: User does not have permission to query "
            f"table {table}, or perhaps it does not exist.",
        )
    if not database.fetch(
        "SELECT 1 FROM duckdb_schemas() WHERE database_name = ? AND schema_name = ?",
        [project_id, dataset_id],
    ):
        return BigQueryError(
            "notFound",
            f"Not found: Dataset {project_id}:{dataset_id} was not found in location US",
        )
    return BigQueryError(
        "notFound", f"Not found: Table {table} was not found in location US"
    )


def _check(tree: exp.Expression, table: exp.Table, is_target: bool):
    project_id, dataset_id, table_id = table.catalog, table.db, table.name
    if not DATASET_ID.match(dataset_id):
        raise BigQueryError(
            "invalid",
            f'Invalid dataset ID "{dataset_id}". Dataset IDs must be alphanumeric '
            "(plus underscores and dashes) and must be at most 1024 characters long.",
            f"{dataset_id}.{table_id}",
        )
    if table.args.get("when"):
        return
    kind = tree.args.get("kind")
    if is_target and (
        isinstance(tree, exp.Create)
        or tree.args.get("exists")
        or kind not in (None, "TABLE", "VIEW")
    ):
        return
    names = database.fetch(
        "SELECT table_name FROM duckdb_tables() WHERE database_name = ? "
        "AND schema_name = ? AND lower(table_name) = lower(?) "
        "UNION ALL SELECT view_name FROM duckdb_views() WHERE database_name = ? "
        "AND schema_name = ? AND lower(view_name) = lower(?) AND NOT internal",
        [project_id, dataset_id, table_id] * 2,
    )
    stored = metadata.load("tables", project_id, dataset_id, table_id) or {}
    if table_id not in {name for (name,) in names} or tables.expired(stored):
        raise _not_found(project_id, dataset_id, table_id)
    if is_target and isinstance(tree, DML) and stored.get("type") == "SNAPSHOT":
        raise BigQueryError(
            "invalidQuery",
            f"Cannot modify snapshot table {project_id}:{dataset_id}.{table_id}",
        )
    if stored.get("requirePartitionFilter") and not is_target:
        partitioning = stored.get("timePartitioning") or {}
        fields = {
            partitioning.get("field", "_PARTITIONTIME").casefold(),
            "_partitiondate",
        }
        filtered = {
            column.name.casefold()
            for where in tree.find_all(exp.Where)
            for column in where.find_all(exp.Column)
        }
        if not fields & filtered:
            raise BigQueryError(
                "invalidQuery",
                f"Cannot query over table '{project_id}.{dataset_id}.{table_id}' without a filter "
                f"over column(s) '{partitioning.get('field', '_PARTITIONTIME')}' "
                "that can be used for partition elimination",
            )


def _as_of(milliseconds: int) -> exp.HistoricalData:
    if milliseconds < 0:
        milliseconds += int(time.time() * 1000)
    moment = datetime.datetime.fromtimestamp(milliseconds / 1000, datetime.UTC)
    timestamp = exp.cast(exp.Literal.string(moment.isoformat()), "TIMESTAMPTZ")
    return exp.HistoricalData(this="AT", kind="TIMESTAMP", expression=timestamp)


def decorator(tree: exp.Expression, context) -> exp.Expression:
    for table in tree.find_all(exp.Table):
        if match := DECORATOR.match(table.name):
            table.set("this", exp.to_identifier(match[1]))
            table.set("when", _as_of(int(match[2])))
    return tree


def qualify(tree: exp.Expression, context) -> exp.Expression:
    if (
        isinstance(tree, exp.Create | exp.Alter | exp.Drop)
        and tree.args.get("kind") == "SCHEMA"
    ):
        target = tree.find(exp.Table)
        if target is not None and not target.catalog:
            target.set("catalog", exp.to_identifier(context.project_id))
        return tree
    for table in tree.find_all(exp.Table):
        if not table.catalog and table.db.casefold() == "_session":
            table.set("db", None)
    if isinstance(tree, exp.Create) and _temporary(tree):
        context.temporary.add(tree.find(exp.Table).name.casefold())
    ctes = {cte.alias_or_name.casefold() for cte in tree.find_all(exp.CTE)}
    target = _target(tree)
    for table in list(tree.find_all(exp.Table)):
        name = table.name.casefold()
        if not isinstance(table.this, exp.Identifier) or name.endswith("*"):
            continue
        if not table.db and (name in ctes or name in context.temporary):
            continue
        if not table.db and context.dataset_id is None:
            continue
        reference = (
            table.catalog or context.project_id,
            table.db or context.dataset_id,
            table.name,
        )
        if table is not target or isinstance(tree, DML):
            context.referenced.add(reference)
        path = tables.physical(*reference)
        for key, part in zip(("catalog", "db", "this"), path):
            table.set(key, exp.to_identifier(part, quoted=True))
        _check(tree, table, table is target)
    return tree


def _system_name(node: exp.Expression) -> str | None:
    if isinstance(node, exp.Parameter) and isinstance(node.this, exp.Parameter):
        return node.this.name.lower()
    if isinstance(node, exp.Dot) and (prefix := _system_name(node.this)):
        return f"{prefix}.{node.name.lower()}"
    return None


def system_variable(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node.parent, exp.Dot) and node.parent.this is node:
        return node
    if (name := _system_name(node)) is None:
        return node
    values = context.system | {
        "project_id": context.project_id,
        "dataset_id": context.dataset_id,
    }
    if name not in values:
        return node
    value = values[name]
    if value is None:
        return exp.null()
    if isinstance(value, bool):
        return exp.Boolean(this=value)
    if isinstance(value, int):
        return exp.Literal.number(value)
    return exp.Literal.string(str(value))


def time_travel(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.Table) and (version := node.args.get("version")):
        node.set("version", None)
        timestamp = exp.cast(version.expression, exp.DataType.build("TIMESTAMPTZ"))
        node.set(
            "when",
            exp.HistoricalData(this="AT", kind="TIMESTAMP", expression=timestamp),
        )
    return node


def wildcard_table(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, exp.Table) or not node.name.endswith("*"):
        return node
    prefix = node.name.rstrip("*")
    project_id = node.catalog or context.project_id
    dataset_id = node.db or context.dataset_id
    tables = database.fetch(
        "SELECT table_name FROM duckdb_tables() WHERE database_name = ? "
        "AND schema_name = ? AND starts_with(table_name, ?) ORDER BY table_name",
        [project_id, dataset_id, prefix],
    )
    if not tables:
        raise _not_found(project_id, dataset_id, node.name)
    selects = [
        sqlglot.select(
            "*",
            exp.alias_(exp.Literal.string(table_id[len(prefix) :]), "_TABLE_SUFFIX"),
        ).from_(exp.table_(table_id, db=dataset_id, catalog=project_id, quoted=True))
        for (table_id,) in tables
    ]
    select = node.find_ancestor(exp.Select)
    if select is not None:
        for star in select.expressions:
            if isinstance(star, exp.Star) and not star.args.get("except_"):
                star.set("except_", [exp.column("_TABLE_SUFFIX")])
    union = functools.reduce(lambda left, right: left.union(right), selects)
    alias = node.args.get("alias") or exp.TableAlias(this=exp.to_identifier(prefix))
    return exp.Subquery(this=union, alias=alias)


STATEMENT_RULES = [decorator, qualify]
NODE_RULES = [system_variable, time_travel, wildcard_table]
