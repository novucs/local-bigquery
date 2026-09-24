import re

import sqlglot
from sqlglot import exp

from local_bigquery.engine.types import range_type
from local_bigquery.errors import BigQueryError
from local_bigquery.sql.dialect import DuckDBDialect, macro

MODES = {"MEETS": ">", "OVERLAPS": ">="}
SESSIONIZE = """
SELECT * EXCLUDE (__prev, __session, __bridged), CASE WHEN {column} IS NULL THEN NULL ELSE {{
    '__range_start': min({column}.__range_start) OVER __group,
    '__range_end': max({column}.__range_end) OVER __group
}} END AS session_range
FROM (
    SELECT *, sum(CASE WHEN __prev IS NULL OR {column}.__range_start {compare} __prev
        THEN 1 ELSE 0 END) OVER (PARTITION BY {keys} {column} IS NULL
        ORDER BY {column}.__range_start, {column}.__range_end ROWS UNBOUNDED PRECEDING
    ) AS __session
    FROM (
        SELECT *, max({column}.__range_end) OVER (PARTITION BY {keys} {column} IS NULL
            ORDER BY {column}.__range_start, {column}.__range_end
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS __prev, bool_or({column} IS NULL) OVER (PARTITION BY {keys} 1) AS __bridged
        FROM __source
    )
)
WINDOW __group AS (PARTITION BY {keys} CASE WHEN __bridged THEN 0 ELSE __session END)
"""
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


def _sessionize(call: exp.Anonymous) -> exp.Expression:
    source, column, partitions, *rest = call.expressions
    mode = rest[0].name.upper() if rest else "MEETS"
    if mode not in MODES:
        meta = rest[0].meta
        position = f"{meta.get('line', 1)}:{meta.get('col', 1) - meta.get('end', 0) + meta.get('start', 0)}"
        raise BigQueryError(
            "invalidQuery",
            f'Could not cast literal "{rest[0].name}" to type RANGE_SESSIONIZE_MODE '
            f"at [{position}]",
            "query",
        )
    keys = "".join(
        f"{exp.to_identifier(key.name, quoted=True).sql()}, "
        for key in partitions.expressions
    )
    query = sqlglot.parse_one(
        SESSIONIZE.format(
            column=exp.to_identifier(column.name, quoted=True).sql(),
            keys=keys,
            compare=MODES[mode],
        ),
        dialect="duckdb",
    )
    query.find(exp.Table).replace(source)
    return query


def ranges(tree: exp.Expression, context) -> exp.Expression:
    for table in list(tree.find_all(exp.Table)):
        call = table.this
        if isinstance(call, exp.Anonymous) and call.name == "RANGE_SESSIONIZE":
            alias = table.alias or "range_sessionize"
            table.replace(
                exp.Subquery(
                    this=_sessionize(call),
                    alias=exp.TableAlias(this=exp.to_identifier(alias)),
                )
            )
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
