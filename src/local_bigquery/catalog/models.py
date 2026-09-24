from sqlglot import exp

from local_bigquery.catalog import datasets, metadata, names, routines
from local_bigquery.catalog.options import TABLE_OPTIONS, Evaluate, Option, options
from local_bigquery.engine import types
from local_bigquery.errors import BigQueryError, not_found
from local_bigquery.models import Model, StandardSqlField, TableFieldSchema
from local_bigquery.sql.dialect import BigQueryDialect

OPTIONS = TABLE_OPTIONS | {
    "model_type": Option("modelType"),
    "input_label_cols": Option("inputLabelCols"),
}


def get(project_id: str, dataset_id: str, model_id: str) -> Model:
    datasets.get(project_id, dataset_id)
    if (model := metadata.load(Model, project_id, dataset_id, model_id)) is None:
        raise not_found("Model", names.label(project_id, dataset_id, model_id))
    return model


def list_(project_id: str, dataset_id: str) -> list[Model]:
    datasets.get(project_id, dataset_id)
    return metadata.list_(Model, project_id, dataset_id)


def update(
    project_id: str, dataset_id: str, model_id: str, body: Model, etag: str | None
) -> Model:
    current = get(project_id, dataset_id, model_id)
    metadata.check_etag(current, etag)
    resource = current.merged(body).replace(lastModifiedTime=metadata.now())
    return metadata.save(resource, project_id, dataset_id, model_id)


def delete(project_id: str, dataset_id: str, model_id: str):
    get(project_id, dataset_id, model_id)
    metadata.delete(Model, project_id, dataset_id, model_id)


def _column(field: TableFieldSchema) -> StandardSqlField:
    kind = exp.DataType.build(types.bigquery_type(field), dialect=BigQueryDialect)
    return StandardSqlField(name=field.name, type=routines.data_type(kind))


def _resource(
    tree: exp.Create, fields: list[TableFieldSchema], evaluate: Evaluate
) -> Model:
    resource = options(tree.args.get("properties"), OPTIONS, evaluate)
    if "description" in resource:
        raise BigQueryError("invalidQuery", "unsupported option description")
    kind = resource.get("modelType", "MODEL_TYPE_UNSPECIFIED").upper()
    labels = {name.casefold() for name in resource.pop("inputLabelCols", ["label"])}
    columns = [_column(field) for field in fields]
    if "label" not in labels and any(c.name.casefold() == "label" for c in columns):
        raise BigQueryError(
            "invalidQuery",
            f"Column 'label' is a reserved column name for the model type {kind}. "
            "Please rename the column in query statement.",
        )
    now = metadata.now()
    return Model.model_validate(
        resource
        | {
            "modelType": kind,
            "location": "US",
            "creationTime": now,
            "lastModifiedTime": now,
            "featureColumns": [c for c in columns if c.name.casefold() not in labels],
            "labelColumns": [c for c in columns if c.name.casefold() in labels],
        }
    )


def apply(
    tree: exp.Expression,
    project_id: str,
    dataset_id: str | None,
    fields: list[TableFieldSchema],
    evaluate: Evaluate,
    dry_run: bool,
):
    target = tree.find(exp.Table)
    keys = names.reference(target, project_id, dataset_id)
    datasets.get(*keys[:2])
    operation = metadata.outcome(
        "Model",
        names.label(*keys),
        metadata.load(Model, *keys) is not None,
        isinstance(tree, exp.Drop),
        bool(tree.args.get("exists")),
        bool(tree.args.get("replace")),
    )
    if dry_run or operation == "SKIP":
        return
    if operation == "DROP":
        metadata.delete(Model, *keys)
    else:
        reference = dict(zip(("projectId", "datasetId", "modelId"), keys))
        resource = _resource(tree, fields, evaluate).replace(modelReference=reference)
        metadata.save(resource, *keys)
