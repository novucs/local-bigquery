from local_bigquery import db
from local_bigquery.api import Router
from local_bigquery.errors import not_found
from local_bigquery.models import Dataset, DatasetList, DatasetListDatasetsItem

router = Router(tags=["datasets"])


def summary(dataset: Dataset) -> DatasetListDatasetsItem:
    fields = DatasetListDatasetsItem.model_fields.keys()
    return DatasetListDatasetsItem.model_validate(dataset.model_dump(include=fields))


def get(project_id: str, dataset_id: str) -> Dataset:
    dataset = db.get_dataset(project_id, dataset_id)
    if dataset is None:
        raise not_found("Dataset", f"{project_id}:{dataset_id}")
    return dataset


@router.get("/projects/{project_id}/datasets")
def list_datasets(project_id: str) -> DatasetList:
    return DatasetList(datasets=[summary(d) for d in db.list_datasets(project_id)])


@router.post("/projects/{project_id}/datasets")
def insert_dataset(project_id: str, body: Dataset) -> Dataset:
    return db.create_dataset(project_id, body.datasetReference.datasetId, body)


@router.get("/projects/{project_id}/datasets/{dataset_id}")
def get_dataset(project_id: str, dataset_id: str) -> Dataset:
    return get(project_id, dataset_id)


@router.patch("/projects/{project_id}/datasets/{dataset_id}")
def patch_dataset(project_id: str, dataset_id: str, body: Dataset) -> Dataset:
    dataset = get(project_id, dataset_id)
    dataset = dataset.model_copy(update=body.model_dump(exclude_unset=True))
    return db.update_dataset(project_id, dataset_id, dataset)


@router.put("/projects/{project_id}/datasets/{dataset_id}")
def update_dataset(project_id: str, dataset_id: str, body: Dataset) -> Dataset:
    return db.update_dataset(project_id, dataset_id, body)


@router.delete("/projects/{project_id}/datasets/{dataset_id}", status_code=204)
def delete_dataset(project_id: str, dataset_id: str):
    db.delete_dataset(project_id, dataset_id)
