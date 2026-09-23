import functools

import sqlglot
from sqlglot import exp

from local_bigquery.catalog import metadata
from local_bigquery.engine import database
from local_bigquery.errors import BigQueryError

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
    return BigQueryError(
        "notFound",
        f"Not found: Table {project_id}:{dataset_id}.{table_id} was not found in location US",
    )


def _check(tree: exp.Expression, table: exp.Table, is_target: bool):
    project_id, dataset_id, table_id = table.catalog, table.db, table.name
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
    if table_id not in {name for (name,) in names}:
        raise _not_found(project_id, dataset_id, table_id)
    stored = metadata.load("tables", project_id, dataset_id, table_id) or {}
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


def qualify(tree: exp.Expression, context) -> exp.Expression:
    if (
        isinstance(tree, exp.Create | exp.Alter | exp.Drop)
        and tree.args.get("kind") == "SCHEMA"
    ):
        target = tree.find(exp.Table)
        if target is not None and not target.catalog:
            target.set("catalog", exp.to_identifier(context.project_id))
        return tree
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
        table.set(
            "catalog",
            exp.to_identifier(table.catalog or context.project_id, quoted=True),
        )
        table.set("db", exp.to_identifier(table.db or context.dataset_id, quoted=True))
        table.set("this", exp.to_identifier(table.name, quoted=True))
        _check(tree, table, table is target)
    return tree


def system_variable(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.Parameter) and isinstance(node.this, exp.Parameter):
        values = {"project_id": context.project_id, "dataset_id": context.dataset_id}
        if (name := node.this.name.lower()) in values:
            return exp.Literal.string(values[name]) if values[name] else exp.null()
    return node


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


STATEMENT_RULES = [qualify]
NODE_RULES = [system_variable, time_travel, wildcard_table]
