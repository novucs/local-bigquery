from local_bigquery.api import Router
from local_bigquery.catalog import datasets
from local_bigquery.errors import not_found
from local_bigquery.models import ListModelsResponse

router = Router(tags=["models"])
MODEL = "/projects/{project_id}/datasets/{dataset_id}/models/{model_id}"


@router.get("/projects/{project_id}/datasets/{dataset_id}/models")
def list_models(project_id: str, dataset_id: str) -> ListModelsResponse:
    datasets.load(project_id, dataset_id)
    return ListModelsResponse()


@router.get(MODEL)
@router.patch(MODEL)
@router.delete(MODEL)
def missing_model(project_id: str, dataset_id: str, model_id: str):
    datasets.load(project_id, dataset_id)
    raise not_found("Model", f"{project_id}:{dataset_id}.{model_id}")
