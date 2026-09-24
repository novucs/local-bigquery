import codecs

from sqlglot import exp

ARITHMETIC = (exp.Add, exp.Sub, exp.Mul, exp.Div, exp.IntDiv, exp.Mod)
INT32_MIN = -(2**31)
UNITS = ["YEAR", "MONTH", "DAY", "HOUR", "MINUTE", "SECOND"]


def _integer(node: exp.Expression) -> bool:
    return (
        isinstance(node, exp.Literal)
        and node.is_number
        and not any(c in node.this for c in ".eE")
    )


def _bigint(value: int) -> exp.Expression:
    return exp.cast(exp.Literal.number(value), exp.DataType.build("BIGINT"))


def float_literal(node: exp.Expression, context) -> exp.Expression:
    if (
        isinstance(node, exp.Literal)
        and node.is_number
        and any(c in node.this for c in ".eE")
    ):
        text = exp.Literal.string(node.this)
        return exp.Cast(this=text, to=exp.DataType.build("DOUBLE"))
    return node


def integer_literal(node: exp.Expression, context) -> exp.Expression:
    if _integer(node) and isinstance(node.parent, ARITHMETIC):
        return _bigint(int(node.this))
    if isinstance(node, exp.Neg) and _integer(node.this):
        value = -int(node.this.this)
        if isinstance(node.parent, ARITHMETIC) or value < INT32_MIN:
            return _bigint(value)
        return exp.Literal.number(value)
    return node


def byte_string(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.ByteString):
        value = codecs.escape_decode(node.this.encode())[0]
        return exp.func("from_hex", exp.Literal.string(value.hex()))
    return node


NODE_RULES = [float_literal, integer_literal, byte_string]
