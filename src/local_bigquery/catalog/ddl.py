import datetime
from collections.abc import Callable

from sqlglot import exp

from local_bigquery.catalog import datasets, metadata, tables

TABLE_OPTIONS = {
    "description": "description",
    "friendly_name": "friendlyName",
    "labels": "labels",
    "expiration_timestamp": "expirationTime",
    "require_partition_filter": "requirePartitionFilter",
}
DATASET_OPTIONS = {
    "description": "description",
    "friendly_name": "friendlyName",
    "labels": "labels",
    "location": "location",
    "default_table_expiration_days": "defaultTableExpirationMs",
}
Evaluate = Callable[[exp.Expression], object]


def _convert(key: str, node: exp.Expression, evaluate: Evaluate):
    if key == "labels":
        return {
            k.name: v.name for k, v in (pair.expressions for pair in node.expressions)
        }
    value = evaluate(node)
    match key:
        case "expirationTime":
            moment = datetime.datetime.fromisoformat(value)
            return str(int(moment.timestamp() * 1000))
        case "defaultTableExpirationMs":
            return str(int(float(value) * 86_400_000))
    return value


def options(node: exp.Expression | None, mapping: dict, evaluate: Evaluate) -> dict:
    resource = {}
    for prop in node.find_all(exp.Property) if node else []:
        if (key := mapping.get(prop.name.lower())) is not None:
            resource[key] = _convert(key, prop.args["value"], evaluate)
    return resource


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


def _fields(schema: exp.Expression, evaluate: Evaluate) -> list[dict]:
    fields = []
    for column in schema.expressions if isinstance(schema, exp.Schema) else []:
        extras = options(
            column.find(exp.Properties), {"description": "description"}, evaluate
        )
        if extras:
            fields.append({"name": column.name} | extras)
    return fields


def _table(tree: exp.Create, evaluate: Evaluate) -> dict:
    properties = tree.args.get("properties")
    resource = options(properties, TABLE_OPTIONS, evaluate)
    for node in properties.expressions if properties else []:
        if isinstance(node, exp.PartitionedByProperty):
            resource |= _partitioning(node)
        elif isinstance(node, exp.ClusterProperty):
            resource["clustering"] = {"fields": [e.name for e in node.expressions]}
    if fields := _fields(tree.this, evaluate):
        resource["schema"] = {"fields": fields}
    return resource


def _reference(
    table: exp.Table, project_id: str, dataset_id: str
) -> tuple[str, str, str]:
    return table.catalog or project_id, table.db or dataset_id, table.name


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
        source = _reference(clone.this, project_id, dataset_id)
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
            datasets.record(*reference, options(properties, DATASET_OPTIONS, evaluate))
        elif isinstance(tree, exp.Drop):
            datasets.forget(*reference)
        elif isinstance(tree, exp.Alter):
            changes = options(tree, DATASET_OPTIONS, evaluate)
            datasets.update(*reference, changes, None, replace=False)
        return
    reference = _reference(target, project_id, dataset_id)
    if isinstance(tree, exp.Create):
        resource = _table(tree, evaluate) | _definition(tree, project_id, dataset_id)
        now = metadata.now()
        resource |= {"creationTime": now, "lastModifiedTime": now}
        tables.record(*reference, tables.defaults(*reference) | resource)
    elif isinstance(tree, exp.Drop):
        tables.forget(*reference)
    elif isinstance(tree, exp.Alter):
        for action in tree.args.get("actions") or []:
            if isinstance(action, exp.AlterRename):
                tables.rename(*reference, action.this.name)
            elif isinstance(action, exp.AlterSet):
                stored = tables.load(*reference)
                changes = options(action, TABLE_OPTIONS, evaluate)
                tables.record(*reference, metadata.merge(stored, changes))
