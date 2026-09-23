import sqlglot
from sqlglot import exp

from local_bigquery.errors import BigQueryError


def system_variable(node: exp.Expression) -> bool:
    return isinstance(node, exp.Parameter) and (
        isinstance(node.this, exp.Parameter) or isinstance(node.parent, exp.Parameter)
    )


def parameter(node: exp.Expression, context) -> exp.Expression:
    if system_variable(node):
        return node
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


NODE_RULES = [parameter]
