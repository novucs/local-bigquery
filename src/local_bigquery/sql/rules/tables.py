import functools

import sqlglot
from sqlglot import exp

from local_bigquery.engine import database
from local_bigquery.errors import BigQueryError


def _temporary(tree: exp.Expression) -> bool:
    return tree.find(exp.TemporaryProperty) is not None


def qualify(tree: exp.Expression, context) -> exp.Expression:
    if isinstance(tree, exp.Create) and tree.args.get("kind") == "SCHEMA":
        target = tree.find(exp.Table)
        if target is not None and not target.catalog:
            target.set("catalog", exp.to_identifier(context.project_id))
        return tree
    if isinstance(tree, exp.Create) and _temporary(tree):
        context.temporary.add(tree.find(exp.Table).name.casefold())
    ctes = {cte.alias_or_name.casefold() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = table.name.casefold()
        if not isinstance(table.this, exp.Identifier) or table.catalog:
            continue
        if not table.db and (name in ctes or name in context.temporary):
            continue
        if not table.db and context.dataset_id is None:
            continue
        table.set("catalog", exp.to_identifier(context.project_id))
        if not table.db:
            table.set("db", exp.to_identifier(context.dataset_id))
    return tree


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
        raise BigQueryError(
            "notFound", f"Not found: Table {project_id}:{dataset_id}.{node.name}"
        )
    selects = [
        sqlglot.select(
            "*",
            exp.alias_(exp.Literal.string(table_id[len(prefix) :]), "_TABLE_SUFFIX"),
        ).from_(exp.table_(table_id, db=dataset_id, catalog=project_id, quoted=True))
        for (table_id,) in tables
    ]
    union = functools.reduce(lambda left, right: left.union(right), selects)
    return exp.paren(union) if len(selects) > 1 else union


STATEMENT_RULES = [qualify]
NODE_RULES = [wildcard_table]
