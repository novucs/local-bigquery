from local_bigquery.api import Router, paginate
from local_bigquery.catalog import datasets, routines
from local_bigquery.errors import not_found
from local_bigquery.models import ListRoutinesResponse, Routine

router = Router(tags=["routines"])
ROUTINE = "/projects/{project_id}/datasets/{dataset_id}/routines/{routine_id}"


def load(project_id: str, dataset_id: str, routine_id: str) -> dict:
    datasets.load(project_id, dataset_id)
    if (routine := routines.load(project_id, dataset_id, routine_id)) is None:
        raise not_found("Routine", f"{project_id}:{dataset_id}.{routine_id}")
    return routine


@router.get("/projects/{project_id}/datasets/{dataset_id}/routines")
def list_routines(
    project_id: str,
    dataset_id: str,
    maxResults: int | None = None,
    pageToken: str | None = None,
) -> ListRoutinesResponse:
    datasets.load(project_id, dataset_id)
    page, token = paginate(
        routines.list_(project_id, dataset_id), maxResults, pageToken
    )
    return ListRoutinesResponse(routines=page, nextPageToken=token)


@router.get(ROUTINE)
def get_routine(project_id: str, dataset_id: str, routine_id: str) -> Routine:
    return load(project_id, dataset_id, routine_id)


@router.delete(ROUTINE, status_code=204)
def delete_routine(project_id: str, dataset_id: str, routine_id: str):
    load(project_id, dataset_id, routine_id)
    routines.delete(project_id, dataset_id, routine_id)
