from sqlglot import exp


def safe_function(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, exp.SafeFunc):
        return node
    function = node.this
    arguments = [
        argument
        for argument in function.iter_expressions()
        if not isinstance(argument, exp.Literal)
    ]
    fields = []
    for index, argument in enumerate(arguments):
        name = f"a{index}"
        fields.append(
            exp.PropertyEQ(this=exp.to_identifier(name), expression=argument.copy())
        )
        argument.replace(exp.column(name, table="s"))
    if not fields:
        return exp.func("TRY", function)
    evaluate = exp.Lambda(
        this=exp.func("TRY", function), expressions=[exp.to_identifier("s")]
    )
    values = exp.Array(expressions=[exp.Struct(expressions=fields)])
    return exp.func(
        "list_extract",
        exp.func("list_transform", values, evaluate),
        exp.Literal.number(1),
    )


NODE_RULES = [safe_function]
