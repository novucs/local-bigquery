from fastapi import Body, Header

from local_bigquery.api import Router, paginate
from local_bigquery.catalog import models
from local_bigquery.models import ListModelsResponse, Model

router = Router(tags=["models"])
MODEL = "/projects/{project_id}/datasets/{dataset_id}/models/{model_id}"


@router.get("/projects/{project_id}/datasets/{dataset_id}/models")
def list_models(
    project_id: str,
    dataset_id: str,
    maxResults: int | None = None,
    pageToken: str | None = None,
) -> ListModelsResponse:
    page, token = paginate(models.list_(project_id, dataset_id), maxResults, pageToken)
    return ListModelsResponse(models=page, nextPageToken=token)


@router.get(MODEL)
def get_model(project_id: str, dataset_id: str, model_id: str) -> Model:
    return models.get(project_id, dataset_id, model_id)


@router.patch(MODEL)
def patch_model(
    project_id: str,
    dataset_id: str,
    model_id: str,
    body: dict = Body(),
    if_match: str | None = Header(None),
) -> Model:
    return models.update(project_id, dataset_id, model_id, body, if_match)


@router.delete(MODEL, status_code=204)
def delete_model(project_id: str, dataset_id: str, model_id: str):
    models.delete(project_id, dataset_id, model_id)
