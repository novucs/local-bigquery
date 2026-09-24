from sqlglot import exp


def anonymous_columns(tree: exp.Expression, context) -> exp.Expression:
    select = tree
    while isinstance(select, exp.SetOperation):
        select = select.this
    if isinstance(select, exp.Select):
        for expression in select.expressions:
            if isinstance(expression, exp.Paren) and isinstance(
                expression.this, exp.Column
            ):
                expression.replace(expression.this)
        anonymous = [
            expression
            for expression in select.expressions
            if not isinstance(expression, (exp.Alias, exp.Column, exp.Star))
        ]
        for index, expression in enumerate(anonymous):
            expression.replace(exp.alias_(expression.copy(), f"f{index}_"))
    return tree


STATEMENT_RULES = [anonymous_columns]
