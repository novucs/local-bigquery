import functools
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify_tables import qualify_tables

from local_bigquery.engine import database
from local_bigquery.errors import BigQueryError
from local_bigquery.settings import settings


@dataclass
class Context:
    project_id: str
    dataset_id: str | None
    parameters: dict[str, str] = field(default_factory=dict)
    values: dict = field(default_factory=dict)
    used: set[str] = field(default_factory=set)
    position: int = 0


def parse(sql: str) -> list[exp.Expression]:
    return [tree for tree in sqlglot.parse(sql, dialect="bigquery") if tree]


def translate(tree: exp.Expression, context: Context) -> tuple[str, dict]:
    context.used.clear()
    tree = anonymous_columns(tree.copy())
    sql = tree.transform(lambda node: _rewrite(node, context)).sql("duckdb")
    return sql, {name: context.values[name] for name in context.used}


def _rewrite(node: exp.Expression, context: Context) -> exp.Expression:
    for rule in (parameter, float_literal, wildcard_table, external_query):
        node = rule(node, context)
    return node


def anonymous_columns(tree: exp.Expression) -> exp.Expression:
    select = tree
    while isinstance(select, exp.SetOperation):
        select = select.this
    if isinstance(select, exp.Select):
        anonymous = (
            e
            for e in select.expressions
            if not isinstance(e, (exp.Alias, exp.Column, exp.Star))
        )
        for index, expression in enumerate(list(anonymous)):
            expression.replace(exp.alias_(expression.copy(), f"f{index}_"))
    return tree


def float_literal(node: exp.Expression, context: Context) -> exp.Expression:
    if (
        isinstance(node, exp.Literal)
        and node.is_number
        and any(c in node.this for c in ".eE")
    ):
        return exp.cast(node, exp.DataType.build("DOUBLE"))
    return node


def parameter(node: exp.Expression, context: Context) -> exp.Expression:
    if isinstance(node, exp.Parameter):
        name = node.name
    elif isinstance(node, exp.Placeholder):
        name, context.position = f"p{context.position}", context.position + 1
    else:
        return node
    if name not in context.parameters:
        raise BigQueryError("invalidQuery", f"Query parameter '{name}' not found")
    context.used.add(name)
    return sqlglot.parse_one(context.parameters[name], dialect="duckdb")


def wildcard_table(node: exp.Expression, context: Context) -> exp.Expression:
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


def external_query(node: exp.Expression, context: Context) -> exp.Expression:
    if not (
        isinstance(node, exp.Table)
        and isinstance(node.this, exp.Anonymous)
        and node.this.name.upper() == "EXTERNAL_QUERY"
    ):
        return node
    connection_id, query = (_literal(arg, context) for arg in node.this.expressions)
    if connection_id != settings.postgres_connection_id:
        raise BigQueryError(
            "invalidQuery",
            f"EXTERNAL_QUERY expected connection ID "
            f"'{settings.postgres_connection_id}', found: '{connection_id}'",
        )
    trees = sqlglot.parse(query, "postgres")
    if len(trees) != 1:
        raise BigQueryError(
            "invalidQuery", "EXTERNAL_QUERY query must be a single statement"
        )
    return exp.Subquery(
        this=qualify_tables(trees[0], catalog="pg", db="public"), alias=node.alias
    )


def _literal(node: exp.Expression, context: Context) -> str:
    if isinstance(node, exp.Literal):
        return node.this
    if isinstance(node, exp.Parameter) and node.name in context.values:
        return context.values[node.name]
    raise BigQueryError(
        "invalidQuery", "EXTERNAL_QUERY arguments must be literals or parameters"
    )


def uses_external_query(trees: list[exp.Expression]) -> bool:
    return any(
        isinstance(node, exp.Anonymous) and node.name.upper() == "EXTERNAL_QUERY"
        for tree in trees
        for node in tree.walk()
    )


def attach_postgres(cur):
    cur.execute(
        "INSTALL postgres; LOAD postgres; DETACH DATABASE IF EXISTS pg; "
        f"ATTACH '{settings.postgres_uri}' AS pg (TYPE postgres)"
    )
