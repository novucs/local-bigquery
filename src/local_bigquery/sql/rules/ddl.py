import re

import sqlglot
from sqlglot import exp

from local_bigquery.sql.dialect import BigQueryDialect

SNAPSHOT = re.compile(
    r"^(CREATE|DROP)\s+SNAPSHOT\s+TABLE\s+(.*)$", re.IGNORECASE | re.DOTALL
)
ALTER_SCHEMA = re.compile(r"^ALTER\s+SCHEMA\s+(.*)$", re.IGNORECASE | re.DOTALL)
PRECISION = {
    exp.DataType.Type.DECIMAL: "DECIMAL(38, 9)",
    exp.DataType.Type.BIGDECIMAL: "DECIMAL(38, 18)",
}


def normalise(tree: exp.Expression) -> exp.Expression:
    if not isinstance(tree, exp.Command):
        return tree
    text = tree.sql(dialect=BigQueryDialect).strip()
    if match := SNAPSHOT.match(text):
        normalised = sqlglot.parse_one(
            f"{match[1]} TABLE {match[2]}", dialect=BigQueryDialect
        )
        normalised.meta["snapshot"] = True
        return normalised
    if match := ALTER_SCHEMA.match(text):
        normalised = sqlglot.parse_one(
            f"ALTER TABLE {match[1]}", dialect=BigQueryDialect
        )
        normalised.set("kind", "SCHEMA")
        return normalised
    return tree


def split(tree: exp.Expression) -> list[exp.Expression]:
    if isinstance(tree, exp.Alter):
        if tree.args.get("kind") == "SCHEMA":
            return []
        actions = [
            a for a in tree.args.get("actions") or [] if not isinstance(a, exp.AlterSet)
        ]
        return [_alter(tree, action) for action in actions]
    if not isinstance(tree, exp.Create) or tree.args.get("kind") != "TABLE":
        return [tree]
    if clone := tree.args.get("clone"):
        source = exp.select("*").from_(clone.this.copy())
        return [exp.Create(this=tree.this.copy(), kind="TABLE", expression=source)]
    if isinstance(tree.this, exp.Schema) and tree.expression:
        create = tree.copy()
        create.set("expression", None)
        insert = exp.insert(tree.expression.copy(), tree.this.this.copy())
        return [create, insert]
    return [tree]


def _alter(tree: exp.Alter, action: exp.Expression) -> exp.Alter:
    single = tree.copy()
    single.set("actions", [action.copy()])
    return single


def numeric_precision(node: exp.Expression, context) -> exp.Expression:
    if (
        isinstance(node, exp.DataType)
        and node.this in PRECISION
        and not node.expressions
        and isinstance(node.parent, exp.ColumnDef | exp.AlterColumn)
    ):
        return exp.DataType.build(PRECISION[node.this], dialect="duckdb")
    return node


NODE_RULES = [numeric_precision]
