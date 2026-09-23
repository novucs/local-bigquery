from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

from local_bigquery.sql.dialect import BigQueryDialect, DuckDBDialect
from local_bigquery.sql.rules import NODE_RULES, STATEMENT_RULES


@dataclass
class Context:
    project_id: str
    dataset_id: str | None
    parameters: dict[str, str] = field(default_factory=dict)
    values: dict = field(default_factory=dict)
    temporary: set[str] = field(default_factory=set)
    attach_postgres: callable = None
    used: set[str] = field(default_factory=set)
    position: int = 0


def parse(sql: str) -> list[exp.Expression]:
    return [tree for tree in sqlglot.parse(sql, dialect=BigQueryDialect) if tree]


def translate(tree: exp.Expression, context: Context) -> tuple[str, dict]:
    context.used.clear()
    tree = tree.copy()
    for rule in STATEMENT_RULES:
        tree = rule(tree, context)
    tree = tree.transform(lambda node: _rewrite(node, context))
    return tree.sql(dialect=DuckDBDialect), {
        name: context.values[name] for name in context.used
    }


def _rewrite(node: exp.Expression, context: Context) -> exp.Expression:
    for rule in NODE_RULES:
        node = rule(node, context)
    return node
