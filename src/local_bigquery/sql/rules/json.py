from sqlglot import exp

from local_bigquery.errors import BigQueryError
from local_bigquery.sql.dialect import macro
from local_bigquery.sql.rules.typing import TEXT, kind


def string_input(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, (exp.JSONExtract, exp.JSONExtractArray)):
        return node
    if kind(node.this) not in TEXT:
        return node
    target = "VARCHAR[]" if isinstance(node, exp.JSONExtractArray) else "VARCHAR"
    return exp.Cast(this=node, to=exp.DataType.build(target))


def equality(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, (exp.EQ, exp.NEQ)) and exp.DataType.Type.JSON in (
        kind(node.left),
        kind(node.right),
    ):
        raise BigQueryError(
            "invalidQuery", "Equality is not defined for arguments of type JSON"
        )
    return node


def string(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.String) and node.args.get("zone") is None:
        return macro("_string", node.this)
    return node


def wide_number_mode(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.Anonymous) and node.name.lower() == "bq.main.parse_json":
        node.set(
            "expressions",
            [a.expression if isinstance(a, exp.Kwarg) else a for a in node.expressions],
        )
    return node


def literal_field(node: exp.Expression, context) -> exp.Expression:
    if not (isinstance(node, exp.ParseJSON) and isinstance(node.this, exp.Dot)):
        return node
    path = node.this
    innermost = path
    while isinstance(innermost.this, exp.Dot):
        innermost = innermost.this
    innermost.set("this", exp.ParseJSON(this=innermost.this))
    return path


NODE_RULES = [literal_field, equality, string_input, string, wide_number_mode]
