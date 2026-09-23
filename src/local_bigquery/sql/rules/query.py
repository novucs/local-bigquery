import sqlglot
from sqlglot import exp

from local_bigquery.errors import BigQueryError
from local_bigquery.sql.dialect import macro


def _values(ordered: exp.Expression) -> exp.Expression:
    return ordered.this if isinstance(ordered, exp.Order) else ordered


def _map_values(ordered: exp.Expression, function: str) -> exp.Expression:
    ordered = ordered.copy()
    _values(ordered).replace(exp.func(function, _values(ordered).copy()))
    return ordered


def _bytes(node: exp.Expression | None) -> bool:
    if isinstance(node, exp.Cast):
        return node.to.is_type(exp.DataType.Type.VARBINARY, exp.DataType.Type.BINARY)
    return isinstance(node, exp.ByteString)


def limited_aggregates(tree: exp.Expression, context) -> exp.Expression:
    for aggregate in list(tree.find_all(exp.ArrayAgg, exp.GroupConcat)):
        limit = aggregate.this
        if not isinstance(limit, exp.Limit):
            continue
        values = exp.ArrayAgg(this=limit.this.copy())
        if isinstance(aggregate, exp.GroupConcat):
            present = exp.Not(
                this=exp.Is(this=_values(limit.this).copy(), expression=exp.null())
            )
            values = exp.Filter(this=values, expression=exp.Where(this=present))
        sliced = exp.func(
            "list_slice", values, exp.Literal.number(1), limit.expression.copy()
        )
        if isinstance(aggregate, exp.GroupConcat):
            separator = aggregate.args.get("separator") or exp.Literal.string(",")
            sliced = exp.func("array_to_string", sliced, separator.copy())
        aggregate.replace(sliced)
    return tree


def byte_string_aggregates(tree: exp.Expression, context) -> exp.Expression:
    for aggregate in list(tree.find_all(exp.GroupConcat)):
        separator = aggregate.args.get("separator")
        if not _bytes(separator):
            continue
        hexed = exp.GroupConcat(
            this=_map_values(aggregate.this, "hex"),
            separator=exp.func("hex", separator.copy()),
        )
        aggregate.replace(exp.func("from_hex", hexed))
    return tree


def corresponding(tree: exp.Expression, context) -> exp.Expression:
    for union in tree.find_all(exp.SetOperation):
        if union.args.get("by_name") and union.args.get("kind") == "INNER":
            union.set("kind", None)
    return tree


def unpivot_order(tree: exp.Expression, context) -> exp.Expression:
    for pivot in list(tree.find_all(exp.Pivot)):
        if not pivot.args.get("unpivot"):
            continue
        source = pivot.parent
        values = [value.name for value in pivot.expressions]
        name = pivot.args["fields"][0].this.name
        columns = ", ".join(
            exp.to_identifier(c).sql("bigquery") for c in [*values, name]
        )
        select = sqlglot.parse_one(
            f"SELECT * EXCEPT ({columns}), {columns}", dialect="bigquery"
        )
        alias = pivot.args.get("alias")
        pivot.set("alias", None)
        wrapped = exp.Subquery(this=select.from_(source.copy()), alias=alias)
        source.replace(wrapped)
    return tree


def hll_count(tree: exp.Expression, context) -> exp.Expression:
    for dot in list(tree.find_all(exp.Dot)):
        if dot.this.name.upper() != "HLL_COUNT" or not isinstance(
            dot.expression, exp.Func
        ):
            continue
        function = dot.expression
        name = function.name if isinstance(function, exp.Anonymous) else function.key
        dot.replace(macro(f"_hll_{name.lower()}", *function.expressions))
    return tree


def duplicate_columns(tree: exp.Expression, context) -> exp.Expression:
    select = tree
    while isinstance(select, exp.SetOperation):
        select = select.this
    if not isinstance(select, exp.Select):
        return tree
    seen = set()
    for expression in select.expressions:
        name = expression.alias_or_name.casefold()
        if isinstance(expression, exp.Star) or not name:
            continue
        if name in seen:
            raise BigQueryError(
                "invalidQuery",
                "Duplicate column names in the result are not supported. "
                f"Found duplicate(s): {expression.alias_or_name}",
            )
        seen.add(name)
    return tree


STATEMENT_RULES = [
    duplicate_columns,
    limited_aggregates,
    byte_string_aggregates,
    corresponding,
    unpivot_order,
    hll_count,
]
