import re

from sqlglot import exp

from local_bigquery.engine.types import range_type
from local_bigquery.errors import BigQueryError
from local_bigquery.sql.dialect import DuckDBDialect, macro

LITERAL = re.compile(r"^\[\s*([^,]+?)\s*,\s*([^)]+?)\s*\)$")


def _struct(element: exp.DataType) -> exp.DataType:
    return exp.DataType.build(
        range_type(element.sql(dialect=DuckDBDialect)), dialect="duckdb"
    )


def _bound(value: str, element: exp.DataType) -> exp.Expression:
    if value.upper() == "UNBOUNDED":
        return exp.cast(exp.null(), element.copy())
    return exp.cast(exp.Literal.string(value), element.copy())


def _literal(cast: exp.Cast) -> exp.Expression:
    element = cast.to.expressions[0]
    match = LITERAL.match(cast.this.name)
    if match is None:
        raise BigQueryError("invalidQuery", f"Invalid RANGE literal: {cast.this.name}")
    start, end = (_bound(value, element) for value in match.groups())
    return macro("range", start, end)


def _is_range(node: exp.Expression) -> bool:
    if isinstance(node, exp.Cast):
        return node.to.is_type(exp.DataType.Type.RANGE)
    return isinstance(node, exp.Anonymous) and node.name.lower() in (
        "bq.main.range",
        "bq.main.range_intersect",
    )


def ranges(tree: exp.Expression, context) -> exp.Expression:
    for call in list(tree.find_all(exp.Anonymous)):
        if call.name.lower() == "bq.main.range_contains" and _is_range(
            call.expressions[1]
        ):
            call.set("this", "bq.main._range_contains_range")
    for cast in list(tree.find_all(exp.Cast)):
        if cast.to.is_type(exp.DataType.Type.RANGE) and cast.this.is_string:
            cast.replace(_literal(cast))
    for datatype in list(tree.find_all(exp.DataType)):
        if datatype.this == exp.DataType.Type.RANGE:
            datatype.replace(_struct(datatype.expressions[0]))
    return tree


STATEMENT_RULES = [ranges]
