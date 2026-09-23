from sqlglot import exp


def float_literal(node: exp.Expression, context) -> exp.Expression:
    if (
        isinstance(node, exp.Literal)
        and node.is_number
        and any(c in node.this for c in ".eE")
    ):
        return exp.cast(node, exp.DataType.build("DOUBLE"))
    return node


NODE_RULES = [float_literal]
