import sqlglot
from sqlglot import exp

from local_bigquery.errors import BigQueryError


def system_variable(node: exp.Expression) -> bool:
    return isinstance(node, exp.Parameter) and (
        isinstance(node.this, exp.Parameter) or isinstance(node.parent, exp.Parameter)
    )


VALUE = "__value"


def read(table: str) -> str:
    return f"(SELECT {VALUE} FROM {table})"


def _read(table: str) -> exp.Expression:
    return sqlglot.parse_one(read(table), dialect="duckdb")


def _assigned(node: exp.Column) -> bool:
    parent = node.parent
    return (
        isinstance(parent, exp.EQ)
        and parent.this is node
        and isinstance(parent.parent, exp.Update)
    )


def variable(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, exp.Column) or not context.variables or _assigned(node):
        return node
    if not node.table and (table := context.variables.get(node.name.lower())):
        return _read(table)
    if (
        node.table
        and not node.db
        and (table := context.variables.get(node.table.lower()))
    ):
        return exp.func("struct_extract", _read(table), exp.Literal.string(node.name))
    return node


def parameter(node: exp.Expression, context) -> exp.Expression:
    if system_variable(node):
        return node
    if isinstance(node, exp.Parameter):
        name = node.name
    elif isinstance(node, exp.Placeholder) and node.name in ("", "?"):
        name, context.position = f"p{context.position}", context.position + 1
    else:
        return node
    if name not in context.parameters:
        raise BigQueryError("invalidQuery", f"Query parameter '{name}' not found")
    if name in context.values:
        context.used.add(name)
    return sqlglot.parse_one(context.parameters[name], dialect="duckdb")


NODE_RULES = [variable, parameter]
