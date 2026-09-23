from sqlglot import exp
from sqlglot.optimizer.annotate_types import annotate_types

from local_bigquery.errors import BigQueryError
from local_bigquery.sql.dialect import macro

TEXT = (exp.DataType.Type.VARCHAR, exp.DataType.Type.TEXT)


def _type(node: exp.Expression) -> exp.DataType.Type | None:
    annotated = annotate_types(node.copy(), dialect="bigquery").type
    return annotated.this if annotated else None


def string_input(node: exp.Expression, context) -> exp.Expression:
    if not isinstance(node, (exp.JSONExtract, exp.JSONExtractArray)):
        return node
    if _type(node.this) not in TEXT:
        return node
    target = "VARCHAR[]" if isinstance(node, exp.JSONExtractArray) else "VARCHAR"
    return exp.Cast(this=node, to=exp.DataType.build(target))


def equality(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, (exp.EQ, exp.NEQ)) and exp.DataType.Type.JSON in (
        _type(node.left),
        _type(node.right),
    ):
        raise BigQueryError(
            "invalidQuery", "Equality is not defined for arguments of type JSON"
        )
    return node


def string(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.String) and node.args.get("zone") is None:
        return macro("_string", node.this)
    return node


NODE_RULES = [equality, string_input, string]
