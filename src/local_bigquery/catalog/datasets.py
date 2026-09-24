import re

from local_bigquery.catalog import metadata, names
from local_bigquery.engine import database
from local_bigquery.engine.database import quote
from local_bigquery.errors import BigQueryError, already_exists, not_found
from local_bigquery.models import Dataset

LABEL_FILTER = re.compile(r"labels\.([\w-]+)(?::(\S*))?")


def exists(project_id: str, dataset_id: str) -> bool:
    return bool(
        database.fetch(
            "SELECT 1 FROM duckdb_schemas() WHERE database_name = ? AND schema_name = ?",
            [project_id, dataset_id],
        )
    )


def _defaults(project_id: str, dataset_id: str) -> dict:
    now = metadata.now()
    return {
        "kind": "bigquery#dataset",
        "id": f"{project_id}:{dataset_id}",
        "selfLink": f"/bigquery/v2/projects/{project_id}/datasets/{dataset_id}",
        "datasetReference": {"projectId": project_id, "datasetId": dataset_id},
        "location": "US",
        "type": "DEFAULT",
        "maxTimeTravelHours": "168",
        "access": [
            {"role": "WRITER", "specialGroup": "projectWriters"},
            {"role": "OWNER", "specialGroup": "projectOwners"},
            {"role": "READER", "specialGroup": "projectReaders"},
        ],
        "creationTime": now,
        "lastModifiedTime": now,
    }


def load(project_id: str, dataset_id: str) -> dict:
    if not exists(project_id, dataset_id):
        raise not_found("Dataset", f"{project_id}:{dataset_id}")
    stored = metadata.load("datasets", project_id, dataset_id)
    return stored or _defaults(project_id, dataset_id)


def get(project_id: str, dataset_id: str) -> Dataset:
    return Dataset.model_validate(load(project_id, dataset_id))


def _matches(dataset: Dataset, filter: str | None) -> bool:
    labels = dataset.labels or {}
    for key, value in LABEL_FILTER.findall(filter or ""):
        if key not in labels or (value and labels[key] != value):
            return False
    return True


def list_(
    project_id: str, filter: str | None = None, all: bool = False
) -> list[Dataset]:
    rows = database.fetch(
        "SELECT schema_name FROM duckdb_schemas() WHERE database_name = ? "
        "AND schema_name <> 'main' AND (? OR NOT starts_with(schema_name, '_')) "
        "ORDER BY schema_name",
        [project_id, bool(all)],
    )
    datasets = metadata.existing(
        get, [(project_id, dataset_id) for (dataset_id,) in rows]
    )
    return [dataset for dataset in datasets if _matches(dataset, filter)]


def save(project_id: str, dataset_id: str, resource: dict) -> Dataset:
    return Dataset.model_validate(
        metadata.save("datasets", resource, project_id, dataset_id)
    )


def create(project_id: str, body: dict) -> Dataset:
    dataset_id = body.get("datasetReference", {}).get("datasetId")
    if not dataset_id:
        raise BigQueryError("invalid", "Required parameter is missing: datasetId")
    names.dataset(dataset_id)
    database.attach(project_id)
    if exists(project_id, dataset_id):
        raise already_exists("Dataset", f"{project_id}:{dataset_id}")
    database.execute(f"CREATE SCHEMA {quote(project_id, dataset_id)}")
    return save(project_id, dataset_id, _defaults(project_id, dataset_id) | body)


def update(
    project_id: str, dataset_id: str, body: dict, etag: str | None, replace: bool
) -> Dataset:
    current = load(project_id, dataset_id)
    metadata.check_etag(current, etag)
    identity = {key: current[key] for key in _defaults(project_id, dataset_id)}
    resource = identity | body if replace else metadata.merge(current, body)
    resource |= {"lastModifiedTime": metadata.now()}
    return save(project_id, dataset_id, resource)


def record(project_id: str, dataset_id: str, resource: dict) -> Dataset:
    return save(project_id, dataset_id, _defaults(project_id, dataset_id) | resource)


def check_empty(project_id: str, dataset_id: str):
    tables = database.fetch(
        "SELECT 1 FROM duckdb_tables() WHERE database_name = ? AND schema_name = ? "
        "UNION ALL SELECT 1 FROM duckdb_views() WHERE database_name = ? "
        "AND schema_name = ? AND NOT internal",
        [project_id, dataset_id] * 2,
    )
    if tables:
        raise BigQueryError(
            "resourceInUse", f"Dataset {project_id}:{dataset_id} is still in use"
        )


def forget(project_id: str, dataset_id: str):
    for kind in metadata.KEYS:
        metadata.delete(kind, project_id, dataset_id)


def delete(project_id: str, dataset_id: str, delete_contents: bool):
    load(project_id, dataset_id)
    if not delete_contents:
        check_empty(project_id, dataset_id)
    database.execute(f"DROP SCHEMA {quote(project_id, dataset_id)} CASCADE")
    forget(project_id, dataset_id)
