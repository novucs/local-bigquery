from sqlglot import exp

from local_bigquery.errors import BigQueryError


def require_where(tree: exp.Expression, context) -> exp.Expression:
    if isinstance(tree, exp.Update | exp.Delete) and not tree.args.get("where"):
        verb = type(tree).__name__.upper()
        raise BigQueryError("invalidQuery", f"{verb} must have a WHERE clause")
    return tree


def delete_from(tree: exp.Expression, context) -> exp.Expression:
    if isinstance(tree, exp.Delete) and not tree.this and tree.args.get("tables"):
        tree.set("this", tree.args["tables"][0])
        tree.set("tables", None)
    return tree


def update_fields(tree: exp.Expression, context) -> exp.Expression:
    if not isinstance(tree, exp.Update):
        return tree
    target = tree.this
    names = {target.name.casefold(), target.alias_or_name.casefold()}
    for assignment in tree.expressions:
        column = assignment.this
        if not isinstance(column, exp.Column) or not column.table:
            continue
        if column.table.casefold() in names:
            assignment.set("this", exp.column(column.name))
        else:
            value = exp.PropertyEQ(
                this=exp.to_identifier(column.name), expression=assignment.expression
            )
            assignment.set("this", exp.column(column.table))
            assignment.set(
                "expression", exp.func("struct_update", exp.column(column.table), value)
            )
    return tree


STATEMENT_RULES = [require_where, delete_from, update_fields]
