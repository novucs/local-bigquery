import datetime

from sqlglot import exp

from local_bigquery.catalog import datasets, metadata, names, tables
from local_bigquery.catalog.options import (
    COLUMN_OPTIONS,
    DATASET_OPTIONS,
    TABLE_OPTIONS,
    Evaluate,
    options,
)
from local_bigquery.errors import BigQueryError
from local_bigquery.models import Dataset, Table, TableConstraints
from local_bigquery.sql.dialect import AlterColumnOptions, DropPrimaryKey

PARAMETERS = {
    exp.DataType.Type.TEXT: ("maxLength",),
    exp.DataType.Type.BINARY: ("maxLength",),
    exp.DataType.Type.DECIMAL: ("precision", "scale"),
    exp.DataType.Type.BIGDECIMAL: ("precision", "scale"),
}


def _partitioning(node: exp.PartitionedByProperty) -> dict:
    expression = node.this
    if isinstance(expression, exp.RangeBucket):
        series = expression.expression
        bounds = {
            "start": series.args["start"].name,
            "end": series.args["end"].name,
            "interval": series.args["step"].name,
        }
        return {"rangePartitioning": {"field": expression.this.name, "range": bounds}}
    unit = expression.args.get("unit")
    field = next(expression.find_all(exp.Identifier)).name
    partitioning = {"type": unit.name.upper() if unit else "DAY"}
    if field.upper() not in ("_PARTITIONDATE", "_PARTITIONTIME"):
        partitioning["field"] = field
    return {"timePartitioning": partitioning}


def _parameters(kind: exp.DataType | None) -> dict:
    values = [param.name for param in kind.expressions] if kind else []
    names = PARAMETERS.get(kind.this, ()) if values else ()
    return dict(zip(names, values))


def _fields(schema: exp.Expression, evaluate: Evaluate) -> list[dict]:
    fields = []
    for column in schema.expressions if isinstance(schema, exp.Schema) else []:
        extras = options(
            column.find(exp.Properties), COLUMN_OPTIONS, evaluate
        ) | _parameters(column.args.get("kind"))
        if extras:
            fields.append({"name": column.name} | extras)
    return fields


def _foreign_key(reference: exp.Reference, table: tuple, position: int) -> dict:
    key = reference.parent
    columns = (
        [column.name for column in key.expressions]
        if isinstance(key, exp.ForeignKey)
        else [reference.find_ancestor(exp.ColumnDef).name]
    )
    target = names.reference(reference.this.this, *table[:2])
    pairs = zip(columns, reference.this.expressions)
    constraint = key.parent if isinstance(key.parent, exp.Constraint) else None
    return {
        "name": constraint.name if constraint else f"fk${position}",
        "referencedTable": dict(zip(("projectId", "datasetId", "tableId"), target)),
        "columnReferences": [
            {"referencingColumn": column, "referencedColumn": referenced.name}
            for column, referenced in pairs
        ],
    }


def check_references(tree: exp.Expression, project_id: str, dataset_id: str | None):
    for reference in tree.find_all(exp.Reference):
        target = names.reference(reference.this.this, project_id, dataset_id)
        stored = metadata.load(Table, *target)
        if not (
            stored and stored.tableConstraints and stored.tableConstraints.primaryKey
        ):
            raise BigQueryError(
                "invalid",
                f"Table {target[1]}.{target[2]} does not have Primary Key constraints",
            )


def _keys(node: exp.Expression, table: tuple, foreign: int = 0) -> dict:
    keys = {}
    for key in node.find_all(
        exp.PrimaryKey, exp.PrimaryKeyColumnConstraint, exp.Reference, bfs=False
    ):
        if isinstance(key, exp.Reference):
            foreign += 1
            keys.setdefault("foreignKeys", []).append(_foreign_key(key, table, foreign))
        elif isinstance(key, exp.PrimaryKey):
            keys["primaryKey"] = {"columns": [e.name for e in key.expressions]}
        else:
            keys["primaryKey"] = {"columns": [key.find_ancestor(exp.ColumnDef).name]}
    return keys


def _alteration(
    stored: Table, action: exp.Expression, reference: tuple, evaluate: Evaluate
) -> dict:
    if isinstance(action, exp.AlterSet):
        return options(action, TABLE_OPTIONS, evaluate)
    if isinstance(action, AlterColumnOptions):
        extras = options(action, COLUMN_OPTIONS, evaluate)
        fields = [
            field.replace(**extras)
            if field.name.casefold() == action.name.casefold()
            else field
            for field in tables.fields(stored)
        ]
        return {"schema": {"fields": fields}}
    keys = stored.tableConstraints or TableConstraints()
    foreign = keys.foreignKeys or []
    label = names.label(*reference)
    if isinstance(action, exp.AddConstraint):
        added = _keys(action, reference, len(foreign))
        foreign = foreign + added.get("foreignKeys", [])
        return {"tableConstraints": added | {"foreignKeys": foreign or None}}
    if isinstance(action, exp.Drop) and action.args.get("kind") == "CONSTRAINT":
        name = action.find(exp.Table).name
        kept = [key for key in foreign if key.name != name]
        if len(kept) == len(foreign) and not action.args.get("exists"):
            raise BigQueryError(
                "invalidQuery", f"Constraint {name} does not exist in table {label}"
            )
        return {"tableConstraints": {"foreignKeys": kept or None}}
    if isinstance(action, DropPrimaryKey):
        if not keys.primaryKey and not action.args.get("exists"):
            raise BigQueryError(
                "invalidQuery", f"Primary key does not exist in table {label}"
            )
        return {"tableConstraints": {"primaryKey": None}}
    return {}


def _table(tree: exp.Create, reference: tuple, evaluate: Evaluate) -> dict:
    properties = tree.args.get("properties")
    resource = options(properties, TABLE_OPTIONS, evaluate)
    for node in properties.expressions if properties else []:
        if isinstance(node, exp.PartitionedByProperty):
            resource |= _partitioning(node)
        elif isinstance(node, exp.ClusterProperty):
            resource["clustering"] = {"fields": [e.name for e in node.expressions]}
    if fields := _fields(tree.this, evaluate):
        resource["schema"] = {"fields": fields}
    if keys := _keys(tree.this, reference):
        resource["tableConstraints"] = keys
    return resource


def _definition(tree: exp.Create, project_id: str, dataset_id: str) -> dict:
    query = tree.expression
    if tree.args.get("kind") == "VIEW" and query is not None:
        if tree.find(exp.MaterializedProperty):
            return {
                "type": "MATERIALIZED_VIEW",
                "materializedView": {"query": query.sql("bigquery")},
            }
        return {"view": {"query": query.sql("bigquery"), "useLegacySql": False}}
    if clone := tree.args.get("clone"):
        source = names.reference(clone.this, project_id, dataset_id)
        base = dict(zip(("projectId", "datasetId", "tableId"), source))
        now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        if tree.meta.get("snapshot"):
            return {
                "type": "SNAPSHOT",
                "snapshotDefinition": {"baseTableReference": base, "snapshotTime": now},
            }
        if not clone.args.get("copy"):
            return {"cloneDefinition": {"baseTableReference": base, "cloneTime": now}}
    return {}


def apply(tree: exp.Expression, project_id: str, dataset_id: str, evaluate: Evaluate):
    kind = (tree.args.get("kind") or "").upper()
    target = tree.find(exp.Table)
    if target is None or tree.find(exp.TemporaryProperty):
        return
    if kind == "SCHEMA":
        reference = (target.catalog or project_id, target.db or target.name)
        if isinstance(tree, exp.Create):
            properties = tree.args.get("properties")
            resource = options(properties, DATASET_OPTIONS, evaluate)
            datasets.record(*reference, Dataset.model_validate(resource))
        elif isinstance(tree, exp.Drop):
            datasets.forget(*reference)
        elif isinstance(tree, exp.Alter):
            changes = Dataset.model_validate(options(tree, DATASET_OPTIONS, evaluate))
            datasets.update(*reference, changes, None, replace=False)
        return
    reference = names.reference(target, project_id, dataset_id)
    if isinstance(tree, exp.Create):
        resource = _table(tree, reference, evaluate) | _definition(
            tree, project_id, dataset_id
        )
        resource = tables.defaults(*reference).merged(Table.model_validate(resource))
        tables.record(*reference, resource)
    elif isinstance(tree, exp.Drop):
        tables.forget(*reference)
    elif isinstance(tree, exp.Alter):
        for action in tree.args.get("actions") or []:
            if isinstance(action, exp.AlterRename):
                tables.rename(*reference, action.this.name)
            elif changes := _alteration(
                stored := tables.load(*reference), action, reference, evaluate
            ):
                tables.record(*reference, stored.merged(Table.model_validate(changes)))
