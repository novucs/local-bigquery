from sqlglot import exp

from local_bigquery.sql.dialect import macro
from local_bigquery.sql.rules.typing import DECIMALS, FLOATS, kind

Type = exp.DataType.Type
SHIFTS = {exp.BitwiseLeftShift: "_shift_left", exp.BitwiseRightShift: "_shift_right"}
OPERATORS = {exp.Div: "/", exp.IntDiv: "DIV", exp.Mod: "MOD"}


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


def _number(node: exp.Expression) -> exp.Expression:
    text = exp.cast(node, "VARCHAR")
    return exp.func(
        "regexp_replace", text, exp.Literal.string(r"\.0$"), exp.Literal.string("")
    )


def _constant_nonzero(node: exp.Expression) -> bool:
    while isinstance(node, (exp.Cast, exp.Paren)):
        node = node.this
    return isinstance(node, exp.Literal) and node.is_number and float(node.this) != 0


def _nonzero(node: exp.Binary, value: exp.Expression) -> exp.Expression:
    if _constant_nonzero(node.expression):
        return value
    left, right = node.this.copy(), node.expression.copy()
    message = exp.func(
        "concat",
        exp.Literal.string("division by zero: "),
        _number(left),
        exp.Literal.string(f" {OPERATORS[type(node)]} "),
        _number(right.copy()),
    )
    zero = exp.EQ(this=right, expression=exp.Literal.number(0))
    return exp.Case(
        ifs=[exp.If(this=zero, true=exp.func("_raise", message))], default=value
    )


def division(node: exp.Expression, context) -> exp.Expression:
    decimal = kind(node) in DECIMALS
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
        and kind(node.this) in FLOATS
    ):
        node.set("this", exp.func("round", node.this))
    return node


def float_sign(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.Sign) and kind(node.this) in FLOATS:
        nan = exp.If(this=exp.func("isnan", node.this.copy()), true=node.this.copy())
        return exp.Case(ifs=[nan], default=exp.cast(node, exp.DataType.build("DOUBLE")))
    return node


def shift(node: exp.Expression, context) -> exp.Expression:
    if type(node) in SHIFTS:
        return macro(SHIFTS[type(node)], node.this, node.expression)
    return node


NODE_RULES = [decimal_type, division, float_to_integer, float_sign, shift]
