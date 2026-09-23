from sqlglot import exp


def safe_function(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.SafeFunc):
        return exp.func("TRY", node.this)
    return node


NODE_RULES = [safe_function]
