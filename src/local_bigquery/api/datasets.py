from fastapi import Body, Header

from local_bigquery.api import Router, paginate
from local_bigquery.catalog import datasets
from local_bigquery.models import Dataset, DatasetList, DatasetListDatasetsItem

router = Router(tags=["datasets"])
SUMMARY_FIELDS = set(DatasetListDatasetsItem.model_fields)


@router.get("/projects/{project_id}/datasets")
def list_datasets(
    project_id: str,
    maxResults: int | None = None,
    pageToken: str | None = None,
    all: bool = False,
    filter: str | None = None,
) -> DatasetList:
    summaries = [
        dataset.model_dump(include=SUMMARY_FIELDS, exclude_none=True)
        for dataset in datasets.list_(project_id, filter, all)
    ]
    page, token = paginate(summaries, maxResults, pageToken)
    return DatasetList(kind="bigquery#datasetList", datasets=page, nextPageToken=token)


@router.post("/projects/{project_id}/datasets")
def insert_dataset(project_id: str, body: dict = Body()) -> Dataset:
    return datasets.create(project_id, body)


@router.get("/projects/{project_id}/datasets/{dataset_id}")
def get_dataset(project_id: str, dataset_id: str) -> Dataset:
    return datasets.get(project_id, dataset_id)


@router.patch("/projects/{project_id}/datasets/{dataset_id}")
def patch_dataset(
    project_id: str,
    dataset_id: str,
    body: dict = Body(),
    if_match: str | None = Header(None),
) -> Dataset:
    return datasets.update(project_id, dataset_id, body, if_match, replace=False)


@router.put("/projects/{project_id}/datasets/{dataset_id}")
def update_dataset(
    project_id: str,
    dataset_id: str,
    body: dict = Body(),
    if_match: str | None = Header(None),
) -> Dataset:
    return datasets.update(project_id, dataset_id, body, if_match, replace=True)


@router.delete("/projects/{project_id}/datasets/{dataset_id}", status_code=204)
def delete_dataset(project_id: str, dataset_id: str, deleteContents: bool = False):
    datasets.delete(project_id, dataset_id, deleteContents)
