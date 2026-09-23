from sqlglot import exp
from sqlglot.optimizer.annotate_types import annotate_types

from local_bigquery.sql.dialect import macro

Type = exp.DataType.Type
DECIMALS = {Type.DECIMAL: "DECIMAL(38, 9)", Type.BIGDECIMAL: "DECIMAL(38, 18)"}
FLOATS = {Type.DOUBLE, Type.FLOAT}
SHIFTS = {exp.BitwiseLeftShift: "_shift_left", exp.BitwiseRightShift: "_shift_right"}
OPERATORS = {exp.Div: "/", exp.IntDiv: "DIV", exp.Mod: "MOD"}


def annotate(tree: exp.Expression, context) -> exp.Expression:
    try:
        return annotate_types(tree, dialect="bigquery")
    except Exception:
        return tree


def _type(node: exp.Expression) -> exp.DataType.Type | None:
    if isinstance(node, exp.Cast):
        return node.to.this
    return node.type.this if node.type else None


def decimal_type(node: exp.Expression, context) -> exp.Expression:
    if (
        isinstance(node, exp.DataType)
        and node.this in DECIMALS
        and not node.expressions
    ):
        return exp.DataType.build(DECIMALS[node.this], dialect="duckdb")
    return node


def _numeric(node: exp.Expression) -> exp.Expression:
    return exp.cast(node, exp.DataType.build(DECIMALS[Type.DECIMAL], dialect="duckdb"))


def _nonzero(node: exp.Binary, value: exp.Expression) -> exp.Expression:
    left, right = node.this.copy(), node.expression.copy()
    message = exp.func(
        "concat",
        exp.Literal.string("division by zero: "),
        left,
        exp.Literal.string(f" {OPERATORS[type(node)]} "),
        right,
    )
    zero = exp.EQ(this=right.copy(), expression=exp.Literal.number(0))
    return exp.Case(
        ifs=[exp.If(this=zero, true=exp.func("error", message))], default=value
    )


def division(node: exp.Expression, context) -> exp.Expression:
    decimal = _type(node) in DECIMALS
    if isinstance(node, exp.Div) and not node.args.get("safe"):
        return _nonzero(node, _numeric(node.copy()) if decimal else node.copy())
    if isinstance(node, exp.IntDiv):
        quotient = exp.Div(this=node.this.copy(), expression=node.expression.copy())
        value = _numeric(exp.func("trunc", quotient)) if decimal else node.copy()
        return _nonzero(node, value)
    if isinstance(node, exp.Mod):
        return _nonzero(node, node.copy())
    return node


def float_to_integer(node: exp.Expression, context) -> exp.Expression:
    if (
        isinstance(node, exp.Cast)
        and node.to.this == Type.BIGINT
        and _type(node.this) in FLOATS
    ):
        node.set("this", exp.func("round", node.this))
    return node


def float_sign(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.Sign) and _type(node.this) in FLOATS:
        return exp.cast(node, exp.DataType.build("DOUBLE"))
    return node


def shift(node: exp.Expression, context) -> exp.Expression:
    if type(node) in SHIFTS:
        return macro(SHIFTS[type(node)], node.this, node.expression)
    return node


STATEMENT_RULES = [annotate]
NODE_RULES = [decimal_type, division, float_to_integer, float_sign, shift]
