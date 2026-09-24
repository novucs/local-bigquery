import re

import sqlglot
from sqlglot import exp

from local_bigquery.errors import BigQueryError
from local_bigquery.sql.dialect import AlterColumnOptions, BigQueryDialect

SNAPSHOT = re.compile(
    r"^(CREATE|DROP)\s+SNAPSHOT\s+TABLE\s+(.*)$", re.IGNORECASE | re.DOTALL
)
ALTER_SCHEMA = re.compile(r"^ALTER\s+SCHEMA\s+(.*)$", re.IGNORECASE | re.DOTALL)
KEYS = (exp.PrimaryKey, exp.PrimaryKeyColumnConstraint, exp.Reference)
CONSTRAINTS = (*KEYS, exp.Constraint, exp.ForeignKey)
LENGTHS = (exp.DataType.Type.TEXT, exp.DataType.Type.BINARY)
DECIMALS = {exp.DataType.Type.DECIMAL: 29, exp.DataType.Type.BIGDECIMAL: 38}


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


def parameterized_types(tree: exp.Expression, context) -> exp.Expression:
    for datatype in tree.find_all(exp.DataType):
        if datatype.this not in DECIMALS or not datatype.expressions:
            continue
        parameters = [*datatype.expressions, exp.Literal.number(0)][:2]
        precision, scale = (int(parameter.name) for parameter in parameters)
        name = "NUMERIC" if datatype.this == exp.DataType.Type.DECIMAL else "BIGNUMERIC"
        low, high = max(1, scale), scale + DECIMALS[datatype.this]
        if not low <= precision <= high:
            raise BigQueryError(
                "invalidQuery",
                f"In {name}(P, {scale}), P must be between {low} and {high}",
            )
    return tree


def unsized(node: exp.Expression, context) -> exp.Expression:
    if isinstance(node, exp.DataType) and node.this in LENGTHS and node.expressions:
        node.set("expressions", None)
    return node


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


STATEMENT_RULES = [parameterized_types, materialized_drop, table_constraints]
NODE_RULES = [unsized]
