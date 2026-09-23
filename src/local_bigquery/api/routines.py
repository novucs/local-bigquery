from fastapi import Body, Header

from local_bigquery.api import Router, paginate
from local_bigquery.catalog import datasets, metadata, routines
from local_bigquery.errors import already_exists
from local_bigquery.jobs.query import run_ddl
from local_bigquery.models import ListRoutinesResponse, Routine

router = Router(tags=["routines"])
ROUTINES = "/projects/{project_id}/datasets/{dataset_id}/routines"
ROUTINE = f"{ROUTINES}/{{routine_id}}"


def load(project_id: str, dataset_id: str, routine_id: str) -> dict:
    datasets.load(project_id, dataset_id)
    return routines.get(project_id, dataset_id, routine_id)


def define(
    project_id: str, dataset_id: str, routine_id: str, body: dict, replace: bool
) -> dict:
    reference = {
        "projectId": project_id,
        "datasetId": dataset_id,
        "routineId": routine_id,
    }
    body = body | {"routineReference": reference}
    run_ddl(project_id, routines.statement(body, replace))
    stored = routines.load(project_id, dataset_id, routine_id)
    return routines.save(project_id, dataset_id, routine_id, stored | body)


@router.get(ROUTINES)
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


@router.post(ROUTINES)
def insert_routine(project_id: str, dataset_id: str, body: dict = Body()) -> Routine:
    datasets.load(project_id, dataset_id)
    routine_id = (body.get("routineReference") or {}).get("routineId")
    if routines.load(project_id, dataset_id, routine_id) is not None:
        raise already_exists("Routine", f"{project_id}:{dataset_id}.{routine_id}")
    return define(project_id, dataset_id, routine_id, body, False)


@router.get(ROUTINE)
def get_routine(project_id: str, dataset_id: str, routine_id: str) -> Routine:
    return load(project_id, dataset_id, routine_id)


@router.put(ROUTINE)
def update_routine(
    project_id: str,
    dataset_id: str,
    routine_id: str,
    body: dict = Body(),
    if_match: str | None = Header(None),
) -> Routine:
    current = load(project_id, dataset_id, routine_id)
    metadata.check_etag(current, if_match)
    return define(project_id, dataset_id, routine_id, current | body, True)


@router.delete(ROUTINE, status_code=204)
def delete_routine(project_id: str, dataset_id: str, routine_id: str):
    load(project_id, dataset_id, routine_id)
    routines.delete(project_id, dataset_id, routine_id)
