import uuid

from fastapi import Query

from local_bigquery.api import Router, paginate, with_rows
from local_bigquery.catalog import tabledata, tables
from local_bigquery.jobs import runner, store
from local_bigquery.models import (
    Job,
    JobCancelResponse,
    JobConfiguration,
    JobList,
    JobListJobsItem,
    QueryRequest,
    TableSchema,
)

router = Router(tags=["jobs"])
LIST_FIELDS = set(JobListJobsItem.model_fields)
QUERY_CONFIGURATION = ("dryRun", "labels", "jobTimeoutMs", "jobCreationMode")
QUERY_ONLY = ("kind", "formatOptions", "timeoutMs")


def results(
    job: Job, max_results: int | None, start: int, int64_timestamps: bool
) -> tuple[dict, list[str]]:
    payload = {"jobReference": job.jobReference, "jobComplete": False}
    if job.status.state != "DONE":
        return payload, []
    if error := runner.error(job):
        raise error
    statistics = job.statistics.query
    payload |= {
        "jobComplete": True,
        "cacheHit": False,
        "totalBytesProcessed": "0",
        "statementType": statistics.statementType,
        "numDmlAffectedRows": statistics.numDmlAffectedRows,
        "dmlStats": statistics.dmlStats,
        "totalRows": "0",
    }
    destination = job.configuration.query.destinationTable
    if not destination:
        return payload | {"schema": statistics.schema_}, []
    page, schema = tabledata.list_rows(
        *tables.reference(destination), max_results, start, None, int64_timestamps
    )
    payload |= {
        "schema": TableSchema(fields=schema),
        "totalRows": str(page.total),
        "pageToken": page.next_token,
    }
    return payload, page.rows


@router.get("/projects/{project_id}/jobs")
def list_jobs(
    project_id: str,
    maxResults: int | None = None,
    pageToken: str | None = None,
    stateFilter: list[str] | None = Query(None),
    parentJobId: str | None = None,
    minCreationTime: int | None = None,
    maxCreationTime: int | None = None,
) -> JobList:
    states = [state.upper() for state in stateFilter] if stateFilter else None
    jobs = [
        JobListJobsItem.model_validate(
            job.model_dump(include=LIST_FIELDS, exclude_none=True)
            | {"state": job.status.state, "errorResult": job.status.errorResult}
        )
        for job in store.list_(
            project_id, states, parentJobId, minCreationTime, maxCreationTime
        )
    ]
    page, token = paginate(jobs, maxResults, pageToken)
    return JobList(kind="bigquery#jobList", jobs=page, nextPageToken=token)


@router.post("/projects/{project_id}/jobs")
def insert_job(project_id: str, body: Job) -> Job:
    job_id = (body.jobReference and body.jobReference.jobId) or str(uuid.uuid4())
    job = runner.submit(project_id, job_id, body.configuration or JobConfiguration())
    if job.jobReference.jobId is None:
        return job
    return runner.submitted(project_id, job_id)


@router.get("/projects/{project_id}/jobs/{job_id}")
def get_job(project_id: str, job_id: str) -> Job:
    return runner.get(project_id, job_id)


@router.post("/projects/{project_id}/jobs/{job_id}/cancel")
def cancel_job(project_id: str, job_id: str) -> JobCancelResponse:
    job = runner.cancel(project_id, job_id)
    return JobCancelResponse(kind="bigquery#jobCancelResponse", job=job)


@router.delete("/projects/{project_id}/jobs/{job_id}/delete")
def delete_job(project_id: str, job_id: str) -> dict:
    job = runner.get(project_id, job_id)
    config = job.configuration.query
    destination = config and config.destinationTable
    if destination and destination.datasetId == tables.RESULTS:
        tables.delete(project_id, tables.RESULTS, job_id)
    store.delete(project_id, job_id)
    return {}


@router.post("/projects/{project_id}/queries")
def run_query(project_id: str, body: QueryRequest):
    request = body.given()
    configuration = JobConfiguration.model_validate(
        {key: request[key] for key in QUERY_CONFIGURATION if key in request}
        | {
            "query": {
                key: value
                for key, value in request.items()
                if key not in (*QUERY_CONFIGURATION, *QUERY_ONLY)
            }
        }
    )
    job_id = body.requestId or str(uuid.uuid4())
    job = runner.submit(project_id, job_id, configuration)
    if job.jobReference.jobId is None:
        statistics = job.statistics.query
        return with_rows(
            {
                "kind": "bigquery#queryResponse",
                "jobReference": job.jobReference,
                "jobComplete": True,
                "schema": statistics.schema_,
                "totalBytesProcessed": "0",
                "statementType": statistics.statementType,
            },
            [],
        )
    job = runner.wait(project_id, job_id, body.timeoutMs)
    if error := runner.error(job):
        raise runner.synchronous(error)
    int64_timestamps = bool(body.formatOptions and body.formatOptions.useInt64Timestamp)
    payload, rows = results(job, body.maxResults, 0, int64_timestamps)
    statistics = job.statistics
    return with_rows(
        {"kind": "bigquery#queryResponse"}
        | payload
        | {
            "queryId": job_id,
            "location": "US",
            "creationTime": statistics.creationTime,
            "startTime": statistics.startTime,
            "endTime": statistics.endTime,
            "jobCreationReason": job.jobCreationReason,
            "sessionInfo": statistics.sessionInfo,
            "totalBytesBilled": "0",
            "totalSlotMs": "0",
        },
        rows,
    )


@router.get("/projects/{project_id}/queries/{job_id}")
def get_query_results(
    project_id: str,
    job_id: str,
    maxResults: int | None = None,
    pageToken: str | None = None,
    startIndex: int = 0,
    timeoutMs: int | None = None,
    int64_timestamps: bool = Query(False, alias="formatOptions.useInt64Timestamp"),
):
    job = runner.wait(project_id, job_id, timeoutMs)
    start = int(pageToken) if pageToken else startIndex
    payload, rows = results(job, maxResults, start, int64_timestamps)
    return with_rows({"kind": "bigquery#getQueryResultsResponse"} | payload, rows)
