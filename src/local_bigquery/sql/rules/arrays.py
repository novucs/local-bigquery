from sqlglot import exp

from local_bigquery.errors import BigQueryError
from local_bigquery.sql.dialect import macro


def checked_offsets(tree: exp.Expression, context) -> exp.Expression:
    for bracket in list(tree.find_all(exp.Bracket)):
        base = bracket.args.get("offset")
        if base in (0, 1) and not bracket.args.get("safe"):
            index = bracket.expressions[0]
            bracket.replace(
                macro("_array_at", bracket.this, index, exp.Literal.number(base))
            )
    return tree


def unnest_offsets(tree: exp.Expression, context) -> exp.Expression:
    for unnest in list(tree.find_all(exp.Unnest)):
        offset = unnest.args.get("offset")
        if not isinstance(offset, exp.Identifier):
            continue
        alias = unnest.args.get("alias")
        columns = alias.columns if alias else []
        value = columns[0].name if columns else (alias.name if alias else "value")
        offset = offset.name
        source = exp.Unnest(
            expressions=unnest.expressions,
            alias=exp.TableAlias(
                this=exp.to_identifier("_u"),
                columns=[exp.to_identifier("_e"), exp.to_identifier("_i")],
            ),
            offset=True,
        )
        select = exp.select(
            exp.alias_(exp.column("_e", "_u"), value),
            exp.alias_(exp.column("_i", "_u") - 1, offset),
        ).from_(source)
        unnest.replace(exp.Subquery(this=select))
    return tree


def anonymous_structs(tree: exp.Expression, context) -> exp.Expression:
    for struct in list(tree.find_all(exp.Struct)):
        if isinstance(struct.parent, exp.Cast):
            continue
        fields = struct.expressions
        if not any(isinstance(field, exp.PropertyEQ) for field in fields):
            struct.replace(exp.Anonymous(this="row", expressions=fields))
            continue
        for index, field in enumerate(list(fields)):
            if not isinstance(field, exp.PropertyEQ):
                field.replace(
                    exp.PropertyEQ(
                        this=exp.to_identifier(f"_field_{index + 1}"),
                        expression=field.copy(),
                    )
                )
    return tree


def invalid_literals(tree: exp.Expression, context) -> exp.Expression:
    for array in tree.find_all(exp.Array):
        if any(isinstance(element, exp.Array) for element in array.expressions):
            raise BigQueryError(
                "invalidQuery",
                "Cannot construct array with element type ARRAY because nested "
                "arrays are not supported",
            )
    for comparison in tree.find_all(exp.EQ, exp.NEQ):
        if any(isinstance(side, exp.Array) for side in comparison.args.values()):
            raise BigQueryError(
                "invalidQuery", "Equality is not defined for arguments of type ARRAY"
            )
    for comparison in tree.find_all(exp.LT, exp.LTE, exp.GT, exp.GTE):
        if any(isinstance(side, exp.Struct) for side in comparison.args.values()):
            raise BigQueryError(
                "invalidQuery", "Less than is not defined for arguments of type STRUCT"
            )
    return tree


def count_if_default(tree: exp.Expression, context) -> exp.Expression:
    for count in list(tree.find_all(exp.CountIf)):
        target = count.parent if isinstance(count.parent, exp.Window) else count
        target.replace(exp.func("COALESCE", target.copy(), exp.Literal.number(0)))
    return tree


STATEMENT_RULES = [
    invalid_literals,
    checked_offsets,
    unnest_offsets,
    anonymous_structs,
    count_if_default,
]
