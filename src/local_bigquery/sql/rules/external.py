import sqlglot
from sqlglot import exp

from local_bigquery.errors import BigQueryError
from local_bigquery.settings import settings


def _literal(node: exp.Expression, context) -> str:
    if isinstance(node, exp.Literal):
        return node.this
    if isinstance(node, exp.Parameter) and node.name in context.values:
        return context.values[node.name]
    raise BigQueryError(
        "invalidQuery", "EXTERNAL_QUERY arguments must be literals or parameters"
    )


def external_query(node: exp.Expression, context) -> exp.Expression:
    if not (
        isinstance(node, exp.Table)
        and isinstance(node.this, exp.Anonymous)
        and node.this.name.upper() == "EXTERNAL_QUERY"
    ):
        return node
    connection_id, query = (_literal(arg, context) for arg in node.this.expressions)
    if connection_id != settings.postgres_connection_id:
        raise BigQueryError("invalidQuery", f"Not found: Connection {connection_id}")
    if len(sqlglot.parse(query, "postgres")) != 1:
        raise BigQueryError(
            "invalidQuery", "EXTERNAL_QUERY query must be a single statement"
        )
    alias = context.attach_postgres(settings.postgres_uri)
    function = exp.Anonymous(
        this="postgres_query",
        expressions=[exp.Literal.string(alias), exp.Literal.string(query)],
    )
    return exp.Table(this=function, alias=node.args.get("alias"))


def external_queries(tree: exp.Expression, context) -> exp.Expression:
    for table in list(tree.find_all(exp.Table)):
        table.replace(external_query(table, context))
    return tree


STATEMENT_RULES = [external_queries]
