from sqlglot import exp

from local_bigquery.sql import js
from local_bigquery.sql.dialect import TableMacro, table_body


def definition(tree: exp.Expression, context) -> exp.Expression:
    js.restore()
    if not isinstance(tree, exp.Create) or tree.args.get("kind") != "FUNCTION":
        return tree
    if js.is_udf(tree):
        return tree
    for param in tree.this.expressions:
        kind = param.kind if isinstance(param, exp.ColumnDef) else None
        if kind is None or not kind.is_type("variant", *exp.DataType.NESTED_TYPES):
            continue
        param.set("kind", None)
        if kind.is_type(*exp.DataType.NESTED_TYPES):
            for column in list(tree.expression.find_all(exp.Column)):
                if not column.table and column.name.casefold() == param.name.casefold():
                    column.replace(exp.cast(column.copy(), kind))
    returns = tree.find(exp.ReturnsProperty)
    if body := table_body(tree):
        tree.set("expression", TableMacro(this=body))
    elif returns is not None and not returns.args.get("is_table"):
        tree.set("expression", exp.cast(tree.expression, returns.this))
    return tree


def _coerce(arg: exp.Expression, kind: exp.DataType) -> exp.Expression:
    if isinstance(arg, exp.Struct) and not any(
        isinstance(e, exp.PropertyEQ) for e in arg.expressions
    ):
        return exp.cast(exp.Anonymous(this="ROW", expressions=arg.expressions), kind)
    return arg


def _parts(node: exp.Expression) -> list[str]:
    if isinstance(node, exp.Dot):
        return _parts(node.this) + _parts(node.expression)
    return node.name.split(".")


def routine_path(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.Anonymous) and isinstance(node.this, exp.Identifier):
        path, function = node.this, node
    elif isinstance(node, exp.Dot) and isinstance(node.expression, exp.Anonymous):
        path, function = node, node.expression
    else:
        return node
    *prefix, name = _parts(path)
    if not any("." in part.name for part in path.find_all(exp.Identifier)):
        return node
    call = exp.Anonymous(this=name, expressions=function.expressions)
    return exp.Dot.build([*(exp.to_identifier(p, quoted=True) for p in prefix), call])


def call(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.Anonymous) and node.name.casefold() in context.functions:
        name, kinds = context.functions[node.name.casefold()]
        args = [_coerce(arg, kind) for arg, kind in zip(node.expressions, kinds)]
        return exp.Anonymous(this=name, expressions=args)
    if isinstance(node, exp.Table) and isinstance(node.this, exp.Anonymous):
        if not node.catalog and "." in node.db:
            catalog, db = node.db.split(".", 1)
            node.set("db", exp.to_identifier(db, quoted=True))
            node.set("catalog", exp.to_identifier(catalog, quoted=True))
        if node.db and not node.catalog:
            node.set("catalog", exp.to_identifier(context.project_id))
    return node


STATEMENT_RULES = [definition]
NODE_RULES = [routine_path, call]
