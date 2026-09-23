import re

import sqlglot
from sqlglot import exp

from local_bigquery.errors import BigQueryError
from local_bigquery.sql.dialect import AlterColumnOptions, BigQueryDialect, macro

SNAPSHOT = re.compile(
    r"^(CREATE|DROP)\s+SNAPSHOT\s+TABLE\s+(.*)$", re.IGNORECASE | re.DOTALL
)
ALTER_SCHEMA = re.compile(r"^ALTER\s+SCHEMA\s+(.*)$", re.IGNORECASE | re.DOTALL)
KEYS = (exp.PrimaryKey, exp.PrimaryKeyColumnConstraint, exp.Reference)
CONSTRAINTS = (*KEYS, exp.Constraint, exp.ForeignKey)
LENGTHS = {
    exp.DataType.Type.TEXT: "_max_length",
    exp.DataType.Type.BINARY: "_max_byte_length",
}


def _schema_path(tree: exp.Expression) -> exp.Expression:
    target = tree.find(exp.Table)
    if target is not None and not target.catalog and "." in target.db:
        project_id, dataset_id = target.db.rsplit(".", 1)
        target.set("catalog", exp.to_identifier(project_id, quoted=True))
        target.set("db", exp.to_identifier(dataset_id, quoted=True))
    return tree


def _unenforced(tree: exp.Expression):
    for key in tree.find_all(*KEYS):
        if "NOT ENFORCED" not in map(str, key.args.get("options") or []):
            kind = "FOREIGN" if isinstance(key, exp.Reference) else "PRIMARY"
            raise BigQueryError(
                "invalidQuery",
                f"Enforced {kind} KEY constraints are not supported. "
                "Please use NOT ENFORCED qualifier and try again.",
            )


def normalise(tree: exp.Expression) -> exp.Expression:
    if isinstance(tree, exp.Create | exp.Alter):
        _unenforced(tree)
    if isinstance(tree, exp.Create | exp.Drop) and tree.args.get("kind") == "SCHEMA":
        return _schema_path(tree)
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
        return _schema_path(normalised)
    return tree


def split(tree: exp.Expression) -> list[exp.Expression]:
    if isinstance(tree, exp.Alter):
        if tree.args.get("kind") == "SCHEMA":
            return []
        actions = [a for a in tree.args.get("actions") or [] if not metadata_only(a)]
        return [_alter(tree, action) for action in actions]
    if not isinstance(tree, exp.Create) or tree.args.get("kind") != "TABLE":
        return [tree]
    if clone := tree.args.get("clone"):
        source = exp.select("*").from_(clone.this.copy())
        replace = tree.args.get("replace")
        return [
            exp.Create(
                this=tree.this.copy(), kind="TABLE", expression=source, replace=replace
            )
        ]
    if isinstance(tree.this, exp.Schema) and tree.expression:
        create = tree.copy()
        create.set("expression", None)
        insert = exp.insert(tree.expression.copy(), tree.this.this.copy())
        return [create, insert]
    return [tree]


def metadata_only(action: exp.Expression) -> bool:
    return (
        isinstance(action, exp.AlterSet | exp.AddConstraint | AlterColumnOptions)
        or (isinstance(action, exp.Drop) and action.args.get("kind") == "CONSTRAINT")
        or drops_primary_key(action)
    )


def drops_primary_key(action: exp.Expression) -> bool:
    text = action.text("expression").upper() if isinstance(action, exp.Command) else ""
    return text.split()[:2] == ["PRIMARY", "KEY"]


def _alter(tree: exp.Alter, action: exp.Expression) -> exp.Alter:
    single = tree.copy()
    single.set("actions", [action.copy()])
    return single


def max_length(node: exp.Expression, context) -> exp.Expression:
    target = node.args.get("to") if isinstance(node, exp.Cast) else node
    if not (
        isinstance(target, exp.DataType)
        and target.this in LENGTHS
        and target.expressions
        and not (target is node and isinstance(node.parent, exp.Cast))
    ):
        return node
    size = target.expressions[0].this
    target.set("expressions", None)
    return node if target is node else macro(LENGTHS[target.this], node, size)


def table_constraints(tree: exp.Expression, context) -> exp.Expression:
    if isinstance(tree, exp.Create):
        for node in list(tree.find_all(*CONSTRAINTS)):
            parent = node.parent
            (parent if isinstance(parent, exp.ColumnConstraint) else node).pop()
    return tree


def materialized_drop(tree: exp.Expression, context) -> exp.Expression:
    if isinstance(tree, exp.Drop):
        tree.set("materialized", False)
    return tree


STATEMENT_RULES = [materialized_drop, table_constraints]
NODE_RULES = [max_length]
