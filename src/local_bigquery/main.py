import json
import logging
import pathlib
import traceback
import uuid
from datetime import datetime
from typing import Optional

import duckdb
import sqlglot
from fastapi import APIRouter, Depends, FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import db
from .db import timestamp_now
from .errors import NotFoundError, AlreadyExistsError
from .models import (
    AccelerationMode,
    BatchDeleteRowAccessPoliciesRequest,
    BiEngineMode,
    BiEngineReason,
    BiEngineStatistics,
    Code,
    Code2,
    CommonQueryParams,
    Dataset,
    DatasetList,
    DatasetView,
    GetIamPolicyRequest,
    GetQueryResultsResponse,
    GetServiceAccountResponse,
    Job,
    JobCancelResponse,
    JobCreationReason,
    JobList,
    JobReference,
    JobStatistics,
    JobStatistics2,
    JobStatus,
    ListModelsResponse,
    ListRoutinesResponse,
    ListRowAccessPoliciesResponse,
    Model,
    Policy,
    ProjectList,
    Projection,
    QueryRequest,
    QueryResponse,
    Routine,
    RowAccessPolicy,
    SessionInfo,
    SetIamPolicyRequest,
    StateFilterEnum,
    Table,
    Table1,
    TableDataInsertAllRequest,
    TableDataInsertAllResponse,
    TableDataList,
    TableList,
    TableReference,
    TestIamPermissionsRequest,
    TestIamPermissionsResponse,
    UndeleteDatasetRequest,
    View,
)


app = FastAPI(
    contact={"name": "Google", "url": "https://google.com"},
    description="A data platform for customers to create, manage, share and query data.",
    license={
        "name": "Creative Commons Attribution 3.0",
        "url": "http://creativecommons.org/licenses/by/3.0/",
    },
    termsOfService="https://developers.google.com/terms/",
    title="BigQuery API",
    version="v2",
)
discovery = json.loads(
    (pathlib.Path(__file__).parent.parent / "resources" / "discovery.json").read_text()
)
bigquery_router = APIRouter()
discovery_router = APIRouter()


def error_response(status_code: int, message: str, reason: str) -> JSONResponse:
    logging.error(message)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "errors": [
                    {
                        "domain": "global",
                        "reason": reason,
                        "message": message,
                    }
                ],
                "code": status_code,
                "message": message,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, e: RequestValidationError):
    return error_response(422, str(e), "invalid")


@app.exception_handler(NotFoundError)
async def not_found_error_handler(request: Request, e: NotFoundError) -> JSONResponse:
    return error_response(404, str(e), "notFound")


@app.exception_handler(AlreadyExistsError)
async def already_exists_error_handler(
    request: Request, e: AlreadyExistsError
) -> JSONResponse:
    return error_response(409, str(e), "duplicate")


@app.exception_handler(sqlglot.ParseError)
async def parse_error_handler(request: Request, e: sqlglot.ParseError) -> JSONResponse:
    return error_response(400, str(e), "invalidQuery")


@app.exception_handler(duckdb.Error)
async def duckdb_error_handler(request: Request, e: duckdb.Error) -> JSONResponse:
    return error_response(400, str(e), "invalidQuery")


@app.exception_handler(NotImplementedError)
async def not_implemented_error_handler(request: Request, e: NotImplementedError):
    message = (
        f"{e}\nIf you're seeing this, and want to use this feature, "
        f"please file an issue (or raise a pull request!).\n"
        f"See: https://github.com/novucs/local-bigquery/issues"
    )
    return error_response(501, message, "notImplemented")


@app.exception_handler(Exception)
async def internal_error_handler(request: Request, e: Exception):
    message = (
        f"{traceback.format_exc()}\n{e}\n"
        "This is an unexpected internal error, treat this as a bug. "
        "If you see this, please file an issue with the above logs.\n"
        f"See: https://github.com/novucs/local-bigquery/issues"
    )
    return error_response(500, message, "dontRetry")


@bigquery_router.get(
    "/projects",
    response_model=ProjectList,
    response_model_exclude_unset=True,
    tags=["projects"],
)
def bigquery_projects_list(
    max_results: Optional[int] = Query(10, alias="maxResults"),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    params: CommonQueryParams = Depends(),
) -> ProjectList:
    projects = db.list_projects()
    return ProjectList(projects=projects, totalItems=len(projects))


@bigquery_router.get(
    "/projects/{projectId}/datasets",
    response_model=DatasetList,
    response_model_exclude_unset=True,
    tags=["datasets"],
)
def bigquery_datasets_list(
    project_id: str = Path(..., alias="projectId"),
    all: Optional[bool] = None,
    filter: Optional[str] = None,
    max_results: Optional[int] = Query(10, alias="maxResults"),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    params: CommonQueryParams = Depends(),
) -> DatasetList:
    return DatasetList(datasets=[d.to_dataset1() for d in db.list_datasets(project_id)])


@bigquery_router.post(
    "/projects/{projectId}/datasets",
    response_model=Dataset,
    response_model_exclude_unset=True,
    tags=["datasets"],
)
def bigquery_datasets_insert(
    project_id: str = Path(..., alias="projectId"),
    access_policy_version: Optional[int] = Query(None, alias="accessPolicyVersion"),
    params: CommonQueryParams = Depends(),
    body: Dataset = None,
) -> Dataset:
    return db.create_dataset(project_id, body.datasetReference.datasetId, body)


@bigquery_router.delete(
    "/projects/{projectId}/datasets/{datasetId}",
    response_model=None,
    response_model_exclude_unset=True,
    tags=["datasets"],
)
def bigquery_datasets_delete(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    delete_contents: Optional[bool] = Query(None, alias="deleteContents"),
    params: CommonQueryParams = Depends(),
) -> None:
    db.delete_dataset(project_id, dataset_id)


@bigquery_router.get(
    "/projects/{projectId}/datasets/{datasetId}",
    response_model=Dataset,
    response_model_exclude_unset=True,
    tags=["datasets"],
)
def bigquery_datasets_get(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    access_policy_version: Optional[int] = Query(None, alias="accessPolicyVersion"),
    dataset_view: Optional[DatasetView] = Query(None, alias="datasetView"),
    params: CommonQueryParams = Depends(),
) -> Dataset:
    dataset = db.get_dataset(project_id, dataset_id)
    if dataset is None:
        raise NotFoundError(
            f'Dataset "{dataset_id}" not found in project "{project_id}"'
        )
    return dataset


@bigquery_router.patch(
    "/projects/{projectId}/datasets/{datasetId}",
    response_model=Dataset,
    response_model_exclude_unset=True,
    tags=["datasets"],
)
def bigquery_datasets_patch(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    access_policy_version: Optional[int] = Query(None, alias="accessPolicyVersion"),
    params: CommonQueryParams = Depends(),
    body: Dataset = None,
) -> Dataset:
    dataset = db.get_dataset(project_id, dataset_id)
    if dataset is None:
        raise NotFoundError(
            f'Dataset "{dataset_id}" not found in project "{project_id}"'
        )
    dataset = dataset.model_copy(update=body.model_dump(exclude_unset=True))
    dataset = db.update_dataset(project_id, dataset_id, dataset)
    return dataset


@bigquery_router.put(
    "/projects/{projectId}/datasets/{datasetId}",
    response_model=Dataset,
    response_model_exclude_unset=True,
    tags=["datasets"],
)
def bigquery_datasets_update(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    access_policy_version: Optional[int] = Query(None, alias="accessPolicyVersion"),
    params: CommonQueryParams = Depends(),
    body: Dataset = None,
) -> Dataset:
    return db.update_dataset(project_id, dataset_id, body)


@bigquery_router.get(
    "/projects/{projectId}/datasets/{datasetId}/models",
    response_model=ListModelsResponse,
    response_model_exclude_unset=True,
    tags=["models"],
)
def bigquery_models_list(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    max_results: Optional[int] = Query(10, alias="maxResults"),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    params: CommonQueryParams = Depends(),
) -> ListModelsResponse:
    raise NotImplementedError("List models is not implemented yet.")


@bigquery_router.delete(
    "/projects/{projectId}/datasets/{datasetId}/models/{modelId}",
    response_model=None,
    response_model_exclude_unset=True,
    tags=["models"],
)
def bigquery_models_delete(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    model_id: str = Path(..., alias="modelId"),
    params: CommonQueryParams = Depends(),
) -> None:
    raise NotImplementedError("Delete model is not implemented yet.")


@bigquery_router.get(
    "/projects/{projectId}/datasets/{datasetId}/models/{modelId}",
    response_model=Model,
    response_model_exclude_unset=True,
    tags=["models"],
)
def bigquery_models_get(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    model_id: str = Path(..., alias="modelId"),
    params: CommonQueryParams = Depends(),
) -> Model:
    raise NotImplementedError("Get model is not implemented yet.")


@bigquery_router.patch(
    "/projects/{projectId}/datasets/{datasetId}/models/{modelId}",
    response_model=Model,
    response_model_exclude_unset=True,
    tags=["models"],
)
def bigquery_models_patch(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    model_id: str = Path(..., alias="modelId"),
    params: CommonQueryParams = Depends(),
    body: Model = None,
) -> Model:
    raise NotImplementedError("Patch model is not implemented yet.")


@bigquery_router.get(
    "/projects/{projectId}/datasets/{datasetId}/routines",
    response_model=ListRoutinesResponse,
    response_model_exclude_unset=True,
    tags=["routines"],
)
def bigquery_routines_list(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    filter: Optional[str] = None,
    max_results: Optional[int] = Query(10, alias="maxResults"),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    read_mask: Optional[str] = Query(None, alias="readMask"),
    params: CommonQueryParams = Depends(),
) -> ListRoutinesResponse:
    raise NotImplementedError("List routines is not implemented yet.")


@bigquery_router.post(
    "/projects/{projectId}/datasets/{datasetId}/routines",
    response_model=Routine,
    response_model_exclude_unset=True,
    tags=["routines"],
)
def bigquery_routines_insert(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    params: CommonQueryParams = Depends(),
    body: Routine = None,
) -> Routine:
    raise NotImplementedError("Insert routine is not implemented yet.")


@bigquery_router.delete(
    "/projects/{projectId}/datasets/{datasetId}/routines/{routineId}",
    response_model=None,
    response_model_exclude_unset=True,
    tags=["routines"],
)
def bigquery_routines_delete(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    routine_id: str = Path(..., alias="routineId"),
    params: CommonQueryParams = Depends(),
) -> None:
    raise NotImplementedError("Delete routine is not implemented yet.")


@bigquery_router.get(
    "/projects/{projectId}/datasets/{datasetId}/routines/{routineId}",
    response_model=Routine,
    response_model_exclude_unset=True,
    tags=["routines"],
)
def bigquery_routines_get(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    routine_id: str = Path(..., alias="routineId"),
    read_mask: Optional[str] = Query(None, alias="readMask"),
    params: CommonQueryParams = Depends(),
) -> Routine:
    raise NotImplementedError("Get routine is not implemented yet.")


@bigquery_router.put(
    "/projects/{projectId}/datasets/{datasetId}/routines/{routineId}",
    response_model=Routine,
    response_model_exclude_unset=True,
    tags=["routines"],
)
def bigquery_routines_update(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    routine_id: str = Path(..., alias="routineId"),
    params: CommonQueryParams = Depends(),
    body: Routine = None,
) -> Routine:
    raise NotImplementedError("Update routine is not implemented yet.")


@bigquery_router.get(
    "/projects/{projectId}/datasets/{datasetId}/tables",
    response_model=TableList,
    response_model_exclude_unset=True,
    tags=["tables"],
)
def bigquery_tables_list(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    max_results: Optional[int] = Query(10, alias="maxResults"),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    params: CommonQueryParams = Depends(),
) -> TableList:
    tables = db.list_tables(project_id, dataset_id)
    return TableList(
        etag="etag",
        kind="bigquery#tableList",
        tables=[
            Table1(
                creationTime=str(int(datetime.now().timestamp())),
                friendlyName=table_name,
                id=table_name,
                kind="bigquery#table",
                requirePartitionFilter=False,
                tableReference=TableReference(
                    datasetId=dataset_id,
                    projectId=project_id,
                    tableId=table_name,
                ),
                type="TABLE",
            )
            for table_name in tables
        ],
        totalItems=len(tables),
    )


@bigquery_router.post(
    "/projects/{projectId}/datasets/{datasetId}/tables",
    response_model=Table,
    response_model_exclude_unset=True,
    tags=["tables"],
)
def bigquery_tables_insert(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    params: CommonQueryParams = Depends(),
    body: Table = None,
) -> Table:
    db.create_table(project_id, dataset_id, body.tableReference.tableId, body.schema_)
    return body


@bigquery_router.delete(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}",
    response_model=None,
    response_model_exclude_unset=True,
    tags=["tables"],
)
def bigquery_tables_delete(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    table_id: str = Path(..., alias="tableId"),
    params: CommonQueryParams = Depends(),
) -> None:
    db.delete_table(project_id, dataset_id, table_id)


@bigquery_router.get(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}",
    response_model=Table,
    response_model_exclude_unset=True,
    tags=["tables"],
)
def bigquery_tables_get(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    table_id: str = Path(..., alias="tableId"),
    selected_fields: Optional[str] = Query(None, alias="selectedFields"),
    view: Optional[View] = None,
    params: CommonQueryParams = Depends(),
) -> Table:
    raise NotImplementedError("Get table is not implemented yet.")


@bigquery_router.patch(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}",
    response_model=Table,
    response_model_exclude_unset=True,
    tags=["tables"],
)
def bigquery_tables_patch(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    table_id: str = Path(..., alias="tableId"),
    autodetect_schema: Optional[bool] = None,
    params: CommonQueryParams = Depends(),
    body: Table = None,
) -> Table:
    raise NotImplementedError("Patch table is not implemented yet.")


@bigquery_router.put(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}",
    response_model=Table,
    response_model_exclude_unset=True,
    tags=["tables"],
)
def bigquery_tables_update(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    table_id: str = Path(..., alias="tableId"),
    autodetect_schema: Optional[bool] = None,
    params: CommonQueryParams = Depends(),
    body: Table = None,
) -> Table:
    raise NotImplementedError("Update table is not implemented yet.")


@bigquery_router.get(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/data",
    response_model=TableDataList,
    response_model_exclude_unset=True,
    tags=["tabledata"],
)
def bigquery_tabledata_list(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    table_id: str = Path(..., alias="tableId"),
    format_options_use_int64_timestamp: Optional[bool] = Query(
        None, alias="formatOptions.useInt64Timestamp"
    ),
    max_results: Optional[int] = Query(10, alias="maxResults"),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    selected_fields: Optional[str] = Query(None, alias="selectedFields"),
    start_index: Optional[str] = Query(None, alias="startIndex"),
    params: CommonQueryParams = Depends(),
) -> TableDataList:
    raise NotImplementedError("List table data is not implemented yet.")


@bigquery_router.post(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/insertAll",
    response_model=TableDataInsertAllResponse,
    response_model_exclude_unset=True,
    tags=["tabledata"],
)
def bigquery_tabledata_insert_all(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    table_id: str = Path(..., alias="tableId"),
    params: CommonQueryParams = Depends(),
    body: TableDataInsertAllRequest = None,
) -> TableDataInsertAllResponse:
    if body.rows:
        db.tabledata_insert_all(project_id, dataset_id, table_id, body.rows)
    return TableDataInsertAllResponse()


@bigquery_router.get(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/rowAccessPolicies",
    response_model=ListRowAccessPoliciesResponse,
    response_model_exclude_unset=True,
    tags=["rowAccessPolicies"],
)
def bigquery_row_access_policies_list(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    table_id: str = Path(..., alias="tableId"),
    page_size: Optional[int] = Query(None, alias="pageSize"),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    params: CommonQueryParams = Depends(),
) -> ListRowAccessPoliciesResponse:
    raise NotImplementedError("List row access policies is not implemented yet.")


@bigquery_router.post(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/rowAccessPolicies",
    response_model=RowAccessPolicy,
    response_model_exclude_unset=True,
    tags=["rowAccessPolicies"],
)
def bigquery_row_access_policies_insert(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    table_id: str = Path(..., alias="tableId"),
    params: CommonQueryParams = Depends(),
    body: RowAccessPolicy = None,
) -> RowAccessPolicy:
    raise NotImplementedError("Insert row access policy is not implemented yet.")


@bigquery_router.delete(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/rowAccessPolicies/{policyId}",
    response_model=None,
    response_model_exclude_unset=True,
    tags=["rowAccessPolicies"],
)
def bigquery_row_access_policies_delete(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    table_id: str = Path(..., alias="tableId"),
    policy_id: str = Path(..., alias="policyId"),
    force: Optional[bool] = None,
    params: CommonQueryParams = Depends(),
) -> None:
    raise NotImplementedError("Delete row access policy is not implemented yet.")


@bigquery_router.get(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/rowAccessPolicies/{policyId}",
    response_model=RowAccessPolicy,
    response_model_exclude_unset=True,
    tags=["rowAccessPolicies"],
)
def bigquery_row_access_policies_get(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    table_id: str = Path(..., alias="tableId"),
    policy_id: str = Path(..., alias="policyId"),
    params: CommonQueryParams = Depends(),
) -> RowAccessPolicy:
    raise NotImplementedError("Get row access policy is not implemented yet.")


@bigquery_router.put(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/rowAccessPolicies/{policyId}",
    response_model=RowAccessPolicy,
    response_model_exclude_unset=True,
    tags=["rowAccessPolicies"],
)
def bigquery_row_access_policies_update(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    table_id: str = Path(..., alias="tableId"),
    policy_id: str = Path(..., alias="policyId"),
    params: CommonQueryParams = Depends(),
    body: RowAccessPolicy = None,
) -> RowAccessPolicy:
    raise NotImplementedError("Update row access policy is not implemented yet.")


@bigquery_router.post(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/rowAccessPolicies:batchDelete",
    response_model=None,
    response_model_exclude_unset=True,
    tags=["rowAccessPolicies"],
)
def bigquery_row_access_policies_batch_delete(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    table_id: str = Path(..., alias="tableId"),
    params: CommonQueryParams = Depends(),
    body: BatchDeleteRowAccessPoliciesRequest = None,
) -> None:
    raise NotImplementedError(
        "Batch delete row access policies is not implemented yet."
    )


@bigquery_router.post(
    "/projects/{projectId}/datasets/{datasetId}:undelete",
    response_model=Dataset,
    response_model_exclude_unset=True,
    tags=["datasets"],
)
def bigquery_datasets_undelete(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    params: CommonQueryParams = Depends(),
    body: UndeleteDatasetRequest = None,
) -> Dataset:
    return db.create_dataset(project_id=project_id, dataset_id=dataset_id)


@bigquery_router.get(
    "/projects/{projectId}/jobs",
    response_model=JobList,
    response_model_exclude_unset=True,
    tags=["jobs"],
)
def bigquery_jobs_list(
    project_id: str = Path(..., alias="projectId"),
    all_users: Optional[bool] = Query(None, alias="allUsers"),
    max_creation_time: Optional[str] = Query(None, alias="maxCreationTime"),
    max_results: Optional[int] = Query(10, alias="maxResults"),
    min_creation_time: Optional[str] = Query(None, alias="minCreationTime"),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    parent_job_id: Optional[str] = Query(None, alias="parentJobId"),
    projection: Optional[Projection] = None,
    state_filter: Optional[list[StateFilterEnum]] = Query(None, alias="stateFilter"),
    params: CommonQueryParams = Depends(),
) -> JobList:
    jobs = db.list_jobs(project_id)
    return JobList(jobs=jobs)


@bigquery_router.post(
    "/projects/{projectId}/jobs",
    response_model=Job,
    response_model_exclude_unset=True,
    tags=["jobs"],
)
def bigquery_jobs_insert(
    project_id: str = Path(..., alias="projectId"),
    params: CommonQueryParams = Depends(),
    body: Optional[Job] = None,
) -> Job:
    default_dataset = body.configuration.query.defaultDataset
    rows, schema = db.query(
        default_dataset.projectId if default_dataset else project_id,
        default_dataset.datasetId if default_dataset else None,
        body.configuration.query.query,
        parameters=body.configuration.query.queryParameters,
    )
    job_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    now = timestamp_now()
    job_reference = JobReference(jobId=job_id, location="US", projectId=project_id)
    job = Job(
        configuration=body.configuration,
        id=job_id,
        jobCreationReason=JobCreationReason(code=Code2.REQUESTED),
        jobReference=job_reference,
        selfLink=f"/bigquery/v2/projects/{project_id}/jobs/{job_id}",
        statistics=JobStatistics(
            completionRatio=1.0,
            creationTime=now,
            endTime=now,
            query=JobStatistics2(
                biEngineStatistics=BiEngineStatistics(
                    accelerationMode=AccelerationMode.BI_ENGINE_DISABLED,
                    biEngineMode=BiEngineMode.DISABLED,
                    biEngineReasons=[
                        BiEngineReason(
                            code=Code.OTHER_REASON,
                            message="BI Engine is not emulated",
                        )
                    ],
                ),
                statementType="SELECT",
            ),
            sessionInfo=SessionInfo(sessionId=session_id),
            startTime=now,
        ),
        status=JobStatus(state="DONE"),
    )
    db.create_job(project_id, job_id, job)
    results_response = GetQueryResultsResponse(
        cacheHit=False,
        jobComplete=True,
        jobReference=job_reference,
        numDmlAffectedRows="0",
        rows=rows,
        schema=schema,
        totalBytesProcessed="0",
        totalRows=str(len(rows)),
    )
    db.set_query_results(project_id, job_id, results_response)
    return job


@bigquery_router.get(
    "/projects/{projectId}/jobs/{jobId}",
    response_model=Job,
    response_model_exclude_unset=True,
    tags=["jobs"],
)
def bigquery_jobs_get(
    project_id: str = Path(..., alias="projectId"),
    job_id: str = Path(..., alias="jobId"),
    location: Optional[str] = None,
    params: CommonQueryParams = Depends(),
) -> Job:
    job = db.get_job(project_id, job_id)
    if job is None:
        raise NotFoundError(f'Job "{job_id}" not found in project "{project_id}"')
    return job


@bigquery_router.post(
    "/projects/{projectId}/jobs/{jobId}/cancel",
    response_model=JobCancelResponse,
    response_model_exclude_unset=True,
    tags=["jobs"],
)
def bigquery_jobs_cancel(
    project_id: str = Path(..., alias="projectId"),
    job_id: str = Path(..., alias="jobId"),
    location: Optional[str] = None,
    params: CommonQueryParams = Depends(),
) -> JobCancelResponse:
    job = db.get_job(project_id, job_id)
    if job is None:
        raise NotFoundError(f'Job "{job_id}" not found in project "{project_id}"')
    return JobCancelResponse(job=job)


@bigquery_router.delete(
    "/projects/{projectId}/jobs/{jobId}/delete",
    response_model=None,
    response_model_exclude_unset=True,
    tags=["jobs"],
)
def bigquery_jobs_delete(
    project_id: str = Path(..., alias="projectId"),
    job_id: str = Path(..., alias="jobId"),
    location: Optional[str] = None,
    params: CommonQueryParams = Depends(),
) -> None:
    job = db.get_job(project_id, job_id)
    if job is None:
        raise NotFoundError(f'Job "{job_id}" not found in project "{project_id}"')
    db.delete_job(project_id, job_id)


@bigquery_router.post(
    "/projects/{projectId}/queries",
    response_model=QueryResponse,
    response_model_exclude_unset=True,
    tags=["jobs"],
)
def bigquery_jobs_query(
    project_id: str = Path(..., alias="projectId"),
    params: CommonQueryParams = Depends(),
    body: QueryRequest = None,
) -> QueryResponse:
    default_dataset = body.defaultDataset
    rows, schema = db.query(
        default_dataset.projectId if default_dataset else project_id,
        default_dataset.datasetId if default_dataset else None,
        body.query,
        parameters=body.queryParameters,
    )
    job_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    now = timestamp_now()
    job_reference = JobReference(jobId=job_id, location="US", projectId=project_id)
    job = Job(
        configuration=body.to_job_configuration(),
        id=job_id,
        jobCreationReason=JobCreationReason(code=Code2.REQUESTED),
        jobReference=job_reference,
        selfLink=f"/bigquery/v2/projects/{project_id}/jobs/{job_id}",
        statistics=JobStatistics(
            completionRatio=1.0,
            creationTime=now,
            endTime=now,
            query=JobStatistics2(
                biEngineStatistics=BiEngineStatistics(
                    accelerationMode=AccelerationMode.BI_ENGINE_DISABLED,
                    biEngineMode=BiEngineMode.DISABLED,
                    biEngineReasons=[
                        BiEngineReason(
                            code=Code.OTHER_REASON,
                            message="BI Engine is not emulated",
                        )
                    ],
                ),
                statementType="SELECT",
            ),
            sessionInfo=SessionInfo(sessionId=session_id),
            startTime=now,
        ),
        status=JobStatus(state="DONE"),
    )
    db.create_job(project_id, job_id, job)
    query_results = GetQueryResultsResponse(
        cacheHit=False,
        jobComplete=True,
        jobReference=job_reference,
        numDmlAffectedRows="0",
        rows=rows,
        schema=schema,
        totalBytesProcessed="0",
        totalRows=str(len(rows)),
    )
    db.set_query_results(project_id, job_id, query_results)
    return QueryResponse(
        cacheHit=False,
        creationTime=now,
        endTime=now,
        jobComplete=True,
        jobCreationReason=JobCreationReason(code=Code2.REQUESTED),
        jobReference=job_reference,
        location="US",
        numDmlAffectedRows="0",
        queryId=job_id,
        rows=rows,
        schema=schema,
        sessionInfo=SessionInfo(sessionId=session_id),
        startTime=now,
        totalBytesBilled="0",
        totalBytesProcessed="0",
        totalRows=str(len(rows)),
        totalSlotMs="0",
    )


@bigquery_router.get(
    "/projects/{projectId}/queries/{jobId}",
    response_model=GetQueryResultsResponse,
    response_model_exclude_unset=True,
    tags=["jobs"],
)
def bigquery_jobs_get_query_results(
    project_id: str = Path(..., alias="projectId"),
    job_id: str = Path(..., alias="jobId"),
    format_options_use_int64_timestamp: Optional[bool] = Query(
        None, alias="formatOptions.useInt64Timestamp"
    ),
    location: Optional[str] = None,
    max_results: Optional[int] = Query(10, alias="maxResults"),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    start_index: Optional[str] = Query(None, alias="startIndex"),
    timeout_ms: Optional[int] = Query(None, alias="timeoutMs"),
    params: CommonQueryParams = Depends(),
) -> GetQueryResultsResponse:
    results = db.get_query_results(project_id, job_id)
    if results is None:
        raise NotFoundError(
            f'No results for job "{job_id}" not found in project "{project_id}"'
        )
    return results


@bigquery_router.get(
    "/projects/{projectId}/serviceAccount",
    response_model=GetServiceAccountResponse,
    response_model_exclude_unset=True,
    tags=["projects"],
)
def bigquery_projects_get_service_account(
    project_id: str = Path(..., alias="projectId"),
    params: CommonQueryParams = Depends(),
) -> GetServiceAccountResponse:
    return GetServiceAccountResponse(
        email=f"service-account@{project_id}.iam.gserviceaccount.com"
    )


@bigquery_router.post(
    "/{resource}:getIamPolicy",
    response_model=Policy,
    response_model_exclude_unset=True,
    tags=["tables"],
)
def bigquery_tables_get_iam_policy(
    resource: str,
    params: CommonQueryParams = Depends(),
    body: GetIamPolicyRequest = None,
) -> Policy:
    raise NotImplementedError("Get IAM policy is not implemented yet.")


@bigquery_router.post(
    "/{resource}:setIamPolicy",
    response_model=Policy,
    response_model_exclude_unset=True,
    tags=["tables"],
)
def bigquery_tables_set_iam_policy(
    resource: str,
    params: CommonQueryParams = Depends(),
    body: SetIamPolicyRequest = None,
) -> Policy:
    raise NotImplementedError("Set IAM policy is not implemented yet.")


@bigquery_router.post(
    "/{resource}:testIamPermissions",
    response_model=TestIamPermissionsResponse,
    response_model_exclude_unset=True,
    tags=["tables"],
)
def bigquery_tables_test_iam_permissions(
    resource: str,
    params: CommonQueryParams = Depends(),
    body: TestIamPermissionsRequest = None,
) -> TestIamPermissionsResponse:
    raise NotImplementedError("Test IAM permissions is not implemented yet.")


@app.get("/$discovery/rest")
def discovery_rest():
    return discovery


@app.get("/discovery/v1/apis/bigquery/v2/rest")
def discovery_v1_apis():
    return discovery


app.include_router(bigquery_router, prefix="/bigquery/v2")
app.include_router(discovery_router)
