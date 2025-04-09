import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import duckdb
import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse

from local_bigquery.settings import settings
from . import db
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
    Dataset1,
    DatasetList,
    DatasetReference,
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
    LinkState,
    LinkedDatasetMetadata,
    ListModelsResponse,
    ListRoutinesResponse,
    ListRowAccessPoliciesResponse,
    Model,
    Policy,
    Project,
    ProjectList,
    ProjectReference,
    Projection,
    QueryRequest,
    QueryResponse,
    Routine,
    RowAccessPolicy,
    SessionInfo,
    SetIamPolicyRequest,
    StateFilterEnum,
    StorageBillingModel,
    Table,
    Table1,
    TableCell,
    TableDataInsertAllRequest,
    TableDataInsertAllResponse,
    TableDataList,
    TableList,
    TableReference,
    TableRow,
    TableSchema,
    TestIamPermissionsRequest,
    TestIamPermissionsResponse,
    UndeleteDatasetRequest,
    View,
)
from .transform import infer_bigquery_schema, convert_nested_timestamps_to_bigquery_ints


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.migrate()
    yield


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
    lifespan=lifespan,
)
router = APIRouter(prefix="/bigquery/v2")


@app.exception_handler(Exception)
async def internal_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, duckdb.Error) and "does not exist" in str(exc):
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "message": str(exc),
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                            "reason": traceback.format_exc(),
                        }
                    ],
                }
            },
        )
    return JSONResponse(
        # Hack to force BigQuery client to not retry, I've yet to
        # properly dig into the retry logic of the client.
        # 500 errors appear to be retried indefinitely.
        status_code=400,
        content={
            "error": {
                "message": f"internal error, 400 status code set to avoid retry loops: {exc}",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                        "reason": traceback.format_exc(),
                    }
                ],
            }
        },
    )


@router.get("/projects", response_model=ProjectList, tags=["projects"])
def bigquery_projects_list(
    max_results: Optional[int] = Query(10, alias="maxResults"),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    params: CommonQueryParams = Depends(),
) -> ProjectList:
    return ProjectList(
        etag="etag",
        kind="bigquery#projectList",
        nextPageToken=None,
        projects=[
            Project(
                friendlyName="dev",
                id="dev",
                kind="bigquery#project",
                numericId="1",
                projectReference=ProjectReference(
                    projectId="dev",
                ),
            )
        ],
        totalItems=1,
    )


@router.get(
    "/projects/{projectId}/datasets", response_model=DatasetList, tags=["datasets"]
)
def bigquery_datasets_list(
    project_id: str = Path(..., alias="projectId"),
    all: Optional[bool] = None,
    filter: Optional[str] = None,
    max_results: Optional[int] = Query(10, alias="maxResults"),
    page_token: Optional[str] = Query(None, alias="pageToken"),
    params: CommonQueryParams = Depends(),
) -> DatasetList:
    datasets = db.list_datasets(project_id)
    return DatasetList(
        datasets=[
            Dataset1(
                datasetReference=DatasetReference(
                    datasetId=dataset.schema_name,
                    projectId=dataset.project_id,
                ),
                friendlyName=dataset.schema_name,
                id=dataset.schema_name,
                kind="bigquery#dataset",
                labels={"key": "value"},
                location="US",
            )
            for dataset in datasets
        ],
        etag="etag",
        kind="bigquery#datasetList",
        nextPageToken=None,
        unreachable=[],
    )


@router.post(
    "/projects/{projectId}/datasets", response_model=Dataset, tags=["datasets"]
)
def bigquery_datasets_insert(
    project_id: str = Path(..., alias="projectId"),
    access_policy_version: Optional[int] = Query(None, alias="accessPolicyVersion"),
    params: CommonQueryParams = Depends(),
    body: Dataset = None,
) -> Dataset:
    db.create_dataset(body.datasetReference.projectId, body.datasetReference.datasetId)
    return body


@router.delete(
    "/projects/{projectId}/datasets/{datasetId}",
    response_model=None,
    tags=["datasets"],
)
def bigquery_datasets_delete(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    delete_contents: Optional[bool] = Query(None, alias="deleteContents"),
    params: CommonQueryParams = Depends(),
) -> None:
    db.delete_dataset(project_id, dataset_id)


@router.get(
    "/projects/{projectId}/datasets/{datasetId}",
    response_model=Dataset,
    tags=["datasets"],
)
def bigquery_datasets_get(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    access_policy_version: Optional[int] = Query(None, alias="accessPolicyVersion"),
    dataset_view: Optional[DatasetView] = Query(None, alias="datasetView"),
    params: CommonQueryParams = Depends(),
) -> Dataset:
    return Dataset(
        tags=[],
        access=[],
        creationTime=datetime.now().isoformat(),
        datasetReference=DatasetReference(
            datasetId=dataset_id,
            projectId=project_id,
        ),
        defaultCollation=None,
        defaultEncryptionConfiguration=None,
        defaultPartitionExpirationMs=None,
        defaultRoundingMode=None,
        defaultTableExpirationMs=None,
        description=None,
        etag="etag",
        externalCatalogDatasetOptions=None,
        externalDatasetReference=None,
        friendlyName=dataset_id,
        id=dataset_id,
        isCaseInsensitive=False,
        kind="bigquery#dataset",
        labels={"key": "value"},
        lastModifiedTime=datetime.now().isoformat(),
        linkedDatasetMetadata=LinkedDatasetMetadata(
            linkState=LinkState.UNLINKED,
        ),
        linkedDatasetSource=None,
        location="US",
        maxTimeTravelHours=None,
        resourceTags=None,
        restrictions=None,
        satisfiesPzi=False,
        satisfiesPzs=False,
        selfLink="/bigquery/v2/projects/projectId/datasets/datasetId",
        storageBillingModel=StorageBillingModel.LOGICAL,
        type="DEFAULT",
    )


@router.patch(
    "/projects/{projectId}/datasets/{datasetId}",
    response_model=Dataset,
    tags=["datasets"],
)
def bigquery_datasets_patch(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    access_policy_version: Optional[int] = Query(None, alias="accessPolicyVersion"),
    params: CommonQueryParams = Depends(),
    body: Dataset = None,
) -> Dataset:
    return body


@router.put(
    "/projects/{projectId}/datasets/{datasetId}",
    response_model=Dataset,
    tags=["datasets"],
)
def bigquery_datasets_update(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    access_policy_version: Optional[int] = Query(None, alias="accessPolicyVersion"),
    params: CommonQueryParams = Depends(),
    body: Dataset = None,
) -> Dataset:
    return body


@router.get(
    "/projects/{projectId}/datasets/{datasetId}/models",
    response_model=ListModelsResponse,
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


@router.delete(
    "/projects/{projectId}/datasets/{datasetId}/models/{modelId}",
    response_model=None,
    tags=["models"],
)
def bigquery_models_delete(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    model_id: str = Path(..., alias="modelId"),
    params: CommonQueryParams = Depends(),
) -> None:
    raise NotImplementedError("Delete model is not implemented yet.")


@router.get(
    "/projects/{projectId}/datasets/{datasetId}/models/{modelId}",
    response_model=Model,
    tags=["models"],
)
def bigquery_models_get(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    model_id: str = Path(..., alias="modelId"),
    params: CommonQueryParams = Depends(),
) -> Model:
    raise NotImplementedError("Get model is not implemented yet.")


@router.patch(
    "/projects/{projectId}/datasets/{datasetId}/models/{modelId}",
    response_model=Model,
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


@router.get(
    "/projects/{projectId}/datasets/{datasetId}/routines",
    response_model=ListRoutinesResponse,
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


@router.post(
    "/projects/{projectId}/datasets/{datasetId}/routines",
    response_model=Routine,
    tags=["routines"],
)
def bigquery_routines_insert(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    params: CommonQueryParams = Depends(),
    body: Routine = None,
) -> Routine:
    raise NotImplementedError("Insert routine is not implemented yet.")


@router.delete(
    "/projects/{projectId}/datasets/{datasetId}/routines/{routineId}",
    response_model=None,
    tags=["routines"],
)
def bigquery_routines_delete(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    routine_id: str = Path(..., alias="routineId"),
    params: CommonQueryParams = Depends(),
) -> None:
    raise NotImplementedError("Delete routine is not implemented yet.")


@router.get(
    "/projects/{projectId}/datasets/{datasetId}/routines/{routineId}",
    response_model=Routine,
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


@router.put(
    "/projects/{projectId}/datasets/{datasetId}/routines/{routineId}",
    response_model=Routine,
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


@router.get(
    "/projects/{projectId}/datasets/{datasetId}/tables",
    response_model=TableList,
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
        nextPageToken=None,
        tables=[
            Table1(
                clustering=None,
                creationTime=str(datetime.now().timestamp()),
                expirationTime=None,
                friendlyName=table.table_name,
                id=table.table_name,
                kind="bigquery#table",
                labels=None,
                rangePartitioning=None,
                requirePartitionFilter=False,
                tableReference=TableReference(
                    datasetId=dataset_id,
                    projectId=project_id,
                    tableId=table.table_name,
                ),
                timePartitioning=None,
                type="TABLE",
                view=None,
            )
            for table in tables
        ],
        totalItems=len(tables),
    )


@router.post(
    "/projects/{projectId}/datasets/{datasetId}/tables",
    response_model=Table,
    tags=["tables"],
)
def bigquery_tables_insert(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    params: CommonQueryParams = Depends(),
    body: Table = None,
) -> Table:
    db.create_table(project_id, dataset_id, body.tableReference.tableId, body.schema)
    return body


@router.delete(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}",
    response_model=None,
    tags=["tables"],
)
def bigquery_tables_delete(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    table_id: str = Path(..., alias="tableId"),
    params: CommonQueryParams = Depends(),
) -> None:
    db.delete_table(project_id, dataset_id, table_id)


@router.get(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}",
    response_model=Table,
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


@router.patch(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}",
    response_model=Table,
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


@router.put(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}",
    response_model=Table,
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


@router.get(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/data",
    response_model=TableDataList,
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


@router.post(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/insertAll",
    response_model=TableDataInsertAllResponse,
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
    return TableDataInsertAllResponse(
        insertErrors=[],
        kind="bigquery#tableDataInsertAllResponse",
    )


@router.get(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/rowAccessPolicies",
    response_model=ListRowAccessPoliciesResponse,
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


@router.post(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/rowAccessPolicies",
    response_model=RowAccessPolicy,
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


@router.delete(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/rowAccessPolicies/{policyId}",
    response_model=None,
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


@router.get(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/rowAccessPolicies/{policyId}",
    response_model=RowAccessPolicy,
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


@router.put(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/rowAccessPolicies/{policyId}",
    response_model=RowAccessPolicy,
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


@router.post(
    "/projects/{projectId}/datasets/{datasetId}/tables/{tableId}/rowAccessPolicies:batchDelete",
    response_model=None,
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


@router.post(
    "/projects/{projectId}/datasets/{datasetId}:undelete",
    response_model=Dataset,
    tags=["datasets"],
)
def bigquery_datasets_undelete(
    project_id: str = Path(..., alias="projectId"),
    dataset_id: str = Path(..., alias="datasetId"),
    params: CommonQueryParams = Depends(),
    body: UndeleteDatasetRequest = None,
) -> Dataset:
    raise NotImplementedError("Undelete dataset is not implemented yet.")


@router.get("/projects/{projectId}/jobs", response_model=JobList, tags=["jobs"])
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
    raise NotImplementedError("List jobs is not implemented yet.")


@router.post("/projects/{projectId}/jobs", response_model=Job, tags=["jobs"])
def bigquery_jobs_insert(
    project_id: str = Path(..., alias="projectId"),
    params: CommonQueryParams = Depends(),
    body: Optional[Job] = None,
) -> Job:
    job_id = db.create_job(project_id, body)
    default_dataset = body.configuration.query.defaultDataset
    results, columns = db.query(
        default_dataset.projectId if default_dataset else project_id,
        default_dataset.datasetId if default_dataset else None,
        body.configuration.query.query,
        parameters=body.configuration.query.queryParameters,
    )
    schema = TableSchema(
        fields=infer_bigquery_schema(results, columns),
        foreignTypeInfo=None,
    )
    results = convert_nested_timestamps_to_bigquery_ints(results, schema.fields)
    rows = [TableRow(f=[TableCell(v=cell) for cell in row]) for row in results]
    results_response = GetQueryResultsResponse(
        cacheHit=False,
        errors=[],
        etag="etag",
        jobComplete=True,
        jobReference=JobReference(
            jobId=str(job_id),
            location="US",
            projectId=project_id,
        ),
        kind="bigquery#getQueryResultsResponse",
        numDmlAffectedRows="0",
        pageToken=None,
        rows=rows,
        schema=schema,
        totalBytesProcessed="0",
        totalRows=str(len(results)),
    )
    job = Job(
        configuration=body.configuration,
        etag="etag",
        id=str(job_id),
        jobCreationReason=JobCreationReason(
            code=Code2.REQUESTED,
        ),
        jobReference=JobReference(
            jobId=str(job_id),
            location="US",
            projectId=project_id,
        ),
        kind="bigquery#job",
        principal_subject=None,
        selfLink="/bigquery/v2/projects/projectId/jobs/jobId",
        statistics=JobStatistics(
            completionRatio=1.0,
            copy=None,
            creationTime=str(datetime.now().timestamp()),
            dataMaskingStatistics=None,
            edition=None,
            endTime=str(datetime.now().timestamp()),
            extract=None,
            finalExecutionDurationMs=None,
            load=None,
            numChildJobs=None,
            parentJobId=None,
            query=JobStatistics2(
                biEngineStatistics=BiEngineStatistics(
                    accelerationMode=AccelerationMode.BI_ENGINE_DISABLED,
                    biEngineMode=BiEngineMode.DISABLED,
                    biEngineReasons=[
                        BiEngineReason(
                            code=Code.OTHER_REASON, message="BI Engine is not emulated."
                        )
                    ],
                )
            ),
            quotaDeferments=[],
            reservationUsage=[],
            reservation_id=None,
            rowLevelSecurityStatistics=None,
            scriptStatistics=None,
            sessionInfo=None,
            startTime=str(datetime.now().timestamp()),
            totalBytesProcessed=None,
            totalSlotMs=None,
            transactionInfo=None,
        ),
        status=JobStatus(
            errorResult=None,
            errors=None,
            state="DONE",
        ),
        user_email=None,
    )
    db.update_job(job_id, job, results_response)
    return job


@router.get("/projects/{projectId}/jobs/{jobId}", response_model=Job, tags=["jobs"])
def bigquery_jobs_get(
    project_id: str = Path(..., alias="projectId"),
    job_id: str = Path(..., alias="jobId"),
    location: Optional[str] = None,
    params: CommonQueryParams = Depends(),
) -> Job:
    raise NotImplementedError("Get job is not implemented yet.")


@router.post(
    "/projects/{projectId}/jobs/{jobId}/cancel",
    response_model=JobCancelResponse,
    tags=["jobs"],
)
def bigquery_jobs_cancel(
    project_id: str = Path(..., alias="projectId"),
    job_id: str = Path(..., alias="jobId"),
    location: Optional[str] = None,
    params: CommonQueryParams = Depends(),
) -> JobCancelResponse:
    raise NotImplementedError("Cancel job is not implemented yet.")


@router.delete(
    "/projects/{projectId}/jobs/{jobId}/delete", response_model=None, tags=["jobs"]
)
def bigquery_jobs_delete(
    project_id: str = Path(..., alias="projectId"),
    job_id: str = Path(..., alias="jobId"),
    location: Optional[str] = None,
    params: CommonQueryParams = Depends(),
) -> None:
    raise NotImplementedError("Delete job is not implemented yet.")


@router.post(
    "/projects/{projectId}/queries", response_model=QueryResponse, tags=["jobs"]
)
def bigquery_jobs_query(
    project_id: str = Path(..., alias="projectId"),
    params: CommonQueryParams = Depends(),
    body: QueryRequest = None,
) -> QueryResponse:
    default_dataset = body.defaultDataset
    results, columns = db.query(
        default_dataset.projectId if default_dataset else project_id,
        default_dataset.datasetId if default_dataset else None,
        body.query,
        parameters=body.queryParameters,
    )
    job_id = db.create_job(project_id, Job())
    schema = TableSchema(
        fields=infer_bigquery_schema(results, columns),
        foreignTypeInfo=None,
    )
    results = convert_nested_timestamps_to_bigquery_ints(results, schema.fields)
    rows = [TableRow(f=[TableCell(v=cell) for cell in row]) for row in results]
    results_response = GetQueryResultsResponse(
        cacheHit=False,
        errors=[],
        etag="etag",
        jobComplete=True,
        jobReference=JobReference(
            jobId=str(job_id),
            location="US",
            projectId=project_id,
        ),
        kind="bigquery#getQueryResultsResponse",
        numDmlAffectedRows="0",
        pageToken=None,
        rows=rows,
        schema=schema,
        totalBytesProcessed="0",
        totalRows=str(len(results)),
    )
    job = Job(
        # configuration=body,
        etag="etag",
        id=str(job_id),
        jobCreationReason=JobCreationReason(
            code=Code2.REQUESTED,
        ),
        jobReference=JobReference(
            jobId=str(job_id),
            location="US",
            projectId=project_id,
        ),
        kind="bigquery#job",
        principal_subject=None,
        selfLink="/bigquery/v2/projects/projectId/jobs/jobId",
        statistics=JobStatistics(
            completionRatio=1.0,
            copy=None,
            creationTime=str(datetime.now().timestamp()),
            dataMaskingStatistics=None,
            edition=None,
            endTime=str(datetime.now().timestamp()),
            extract=None,
            finalExecutionDurationMs=None,
            load=None,
            numChildJobs=None,
            parentJobId=None,
            query=JobStatistics2(
                biEngineStatistics=BiEngineStatistics(
                    accelerationMode=AccelerationMode.BI_ENGINE_DISABLED,
                    biEngineMode=BiEngineMode.DISABLED,
                    biEngineReasons=[
                        BiEngineReason(
                            code=Code.OTHER_REASON, message="BI Engine is not emulated."
                        )
                    ],
                )
            ),
            quotaDeferments=[],
            reservationUsage=[],
            reservation_id=None,
            rowLevelSecurityStatistics=None,
            scriptStatistics=None,
            sessionInfo=None,
            startTime=str(datetime.now().timestamp()),
            totalBytesProcessed=None,
            totalSlotMs=None,
            transactionInfo=None,
        ),
        status=JobStatus(
            errorResult=None,
            errors=None,
            state="DONE",
        ),
        user_email=None,
    )
    db.update_job(job_id, job, results_response)
    return QueryResponse(
        cacheHit=False,
        creationTime=str(datetime.now().timestamp()),
        dmlStats=None,
        endTime=str(datetime.now().timestamp()),
        errors=[],
        jobComplete=True,
        jobCreationReason=JobCreationReason(
            code=Code2.REQUESTED,
        ),
        jobReference=JobReference(
            jobId=str(job_id),
            location="US",
            projectId=project_id,
        ),
        kind="bigquery#queryResponse",
        location="US",
        numDmlAffectedRows="0",
        pageToken=None,
        queryId=str(job_id),
        rows=rows,
        schema=schema,
        sessionInfo=SessionInfo(
            sessionId=str(job_id),
        ),
        startTime=str(datetime.now().timestamp()),
        totalBytesBilled="0",
        totalBytesProcessed="0",
        totalRows=str(len(results)),
        totalSlotMs="0",
    )


@router.get(
    "/projects/{projectId}/queries/{jobId}",
    response_model=GetQueryResultsResponse,
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
    job, results = db.get_job(project_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return results


@router.get(
    "/projects/{projectId}/serviceAccount",
    response_model=GetServiceAccountResponse,
    tags=["projects"],
)
def bigquery_projects_get_service_account(
    project_id: str = Path(..., alias="projectId"),
    params: CommonQueryParams = Depends(),
) -> GetServiceAccountResponse:
    raise NotImplementedError("Get service account is not implemented yet.")


@router.post("/{resource}:getIamPolicy", response_model=Policy, tags=["tables"])
def bigquery_tables_get_iam_policy(
    resource: str,
    params: CommonQueryParams = Depends(),
    body: GetIamPolicyRequest = None,
) -> Policy:
    raise NotImplementedError("Get IAM policy is not implemented yet.")


@router.post("/{resource}:setIamPolicy", response_model=Policy, tags=["tables"])
def bigquery_tables_set_iam_policy(
    resource: str,
    params: CommonQueryParams = Depends(),
    body: SetIamPolicyRequest = None,
) -> Policy:
    raise NotImplementedError("Set IAM policy is not implemented yet.")


@router.post(
    "/{resource}:testIamPermissions",
    response_model=TestIamPermissionsResponse,
    tags=["tables"],
)
def bigquery_tables_test_iam_permissions(
    resource: str,
    params: CommonQueryParams = Depends(),
    body: TestIamPermissionsRequest = None,
) -> TestIamPermissionsResponse:
    raise NotImplementedError("Test IAM permissions is not implemented yet.")


app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.bigquery_host, port=settings.bigquery_port)
