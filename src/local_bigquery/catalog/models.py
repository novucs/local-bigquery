from sqlglot import exp

from local_bigquery.catalog import datasets, metadata, names, routines
from local_bigquery.catalog.options import TABLE_OPTIONS, Evaluate, Option, options
from local_bigquery.engine import types
from local_bigquery.errors import BigQueryError, not_found
from local_bigquery.models import TableFieldSchema
from local_bigquery.sql.dialect import BigQueryDialect

OPTIONS = TABLE_OPTIONS | {
    "model_type": Option("modelType"),
    "input_label_cols": Option("inputLabelCols"),
}


def get(project_id: str, dataset_id: str, model_id: str) -> dict:
    datasets.load(project_id, dataset_id)
    if (model := metadata.load("models", project_id, dataset_id, model_id)) is None:
        raise not_found("Model", names.label(project_id, dataset_id, model_id))
    return model


def list_(project_id: str, dataset_id: str) -> list[dict]:
    datasets.load(project_id, dataset_id)
    return metadata.list_("models", project_id, dataset_id)


def update(
    project_id: str, dataset_id: str, model_id: str, body: dict, etag: str | None
) -> dict:
    current = get(project_id, dataset_id, model_id)
    metadata.check_etag(current, etag)
    resource = metadata.merge(current, body) | {"lastModifiedTime": metadata.now()}
    return metadata.save("models", resource, project_id, dataset_id, model_id)


def delete(project_id: str, dataset_id: str, model_id: str):
    get(project_id, dataset_id, model_id)
    metadata.delete("models", project_id, dataset_id, model_id)


def _column(field: dict) -> dict:
    kind = types.bigquery_type(TableFieldSchema.model_validate(field))
    kind = exp.DataType.build(kind, dialect=BigQueryDialect)
    return {"name": field["name"], "type": routines.data_type(kind)}


def _resource(tree: exp.Create, fields: list[dict], evaluate: Evaluate) -> dict:
    resource = options(tree.args.get("properties"), OPTIONS, evaluate)
    if "description" in resource:
        raise BigQueryError("invalidQuery", "unsupported option description")
    kind = resource.get("modelType", "MODEL_TYPE_UNSPECIFIED").upper()
    labels = {name.casefold() for name in resource.pop("inputLabelCols", ["label"])}
    columns = [_column(field) for field in fields]
    if "label" not in labels and any(c["name"].casefold() == "label" for c in columns):
        raise BigQueryError(
            "invalidQuery",
            f"Column 'label' is a reserved column name for the model type {kind}. "
            "Please rename the column in query statement.",
        )
    now = metadata.now()
    return resource | {
        "modelType": kind,
        "location": "US",
        "creationTime": now,
        "lastModifiedTime": now,
        "featureColumns": [c for c in columns if c["name"].casefold() not in labels],
        "labelColumns": [c for c in columns if c["name"].casefold() in labels],
    }


def apply(
    tree: exp.Expression,
    project_id: str,
    dataset_id: str | None,
    fields: list[dict],
    evaluate: Evaluate,
    dry_run: bool,
):
    target = tree.find(exp.Table)
    keys = names.reference(target, project_id, dataset_id)
    datasets.load(*keys[:2])
    operation = metadata.outcome(
        "Model",
        names.label(*keys),
        metadata.load("models", *keys) is not None,
        isinstance(tree, exp.Drop),
        bool(tree.args.get("exists")),
        bool(tree.args.get("replace")),
    )
    if dry_run or operation == "SKIP":
        return
    if operation == "DROP":
        metadata.delete("models", *keys)
    else:
        reference = dict(zip(("projectId", "datasetId", "modelId"), keys))
        resource = _resource(tree, fields, evaluate) | {"modelReference": reference}
        metadata.save("models", resource, *keys)
