import uuid

from fastapi import Body, Query

from local_bigquery.api import Router, paginate, with_rows
from local_bigquery.catalog import tabledata, tables
from local_bigquery.jobs import runner, store
from local_bigquery.models import Job, JobCancelResponse, JobList, JobListJobsItem

router = Router(tags=["jobs"])
LIST_FIELDS = set(JobListJobsItem.model_fields)
QUERY_CONFIGURATION = ("dryRun", "labels", "jobTimeoutMs", "jobCreationMode")


def results(
    job: dict, max_results: int | None, start: int, int64_timestamps: bool
) -> tuple[dict, list[str]]:
    payload = {"jobReference": job["jobReference"], "jobComplete": False}
    if job["status"]["state"] != "DONE":
        return payload, []
    if error := runner.error(job):
        raise error
    statistics = job["statistics"]["query"]
    payload |= {
        "jobComplete": True,
        "cacheHit": False,
        "totalBytesProcessed": "0",
        "statementType": statistics.get("statementType"),
        "numDmlAffectedRows": statistics.get("numDmlAffectedRows"),
        "dmlStats": statistics.get("dmlStats"),
        "totalRows": "0",
    }
    destination = job["configuration"]["query"].get("destinationTable")
    if not destination:
        return payload | {"schema": statistics.get("schema")}, []
    reference = (
        destination["projectId"],
        destination["datasetId"],
        destination["tableId"],
    )
    page, schema = tabledata.list_rows(
        *reference, max_results, start, None, int64_timestamps
    )
    payload |= {
        "schema": {"fields": [field.model_dump(exclude_none=True) for field in schema]},
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
        {key: value for key, value in job.items() if key in LIST_FIELDS}
        | {
            "state": job["status"]["state"],
            "errorResult": job["status"].get("errorResult"),
        }
        for job in store.list_(
            project_id, states, parentJobId, minCreationTime, maxCreationTime
        )
    ]
    page, token = paginate(jobs, maxResults, pageToken)
    return JobList(kind="bigquery#jobList", jobs=page, nextPageToken=token)


@router.post("/projects/{project_id}/jobs")
def insert_job(project_id: str, body: dict = Body()) -> Job:
    job_id = (body.get("jobReference") or {}).get("jobId") or str(uuid.uuid4())
    job = runner.submit(project_id, job_id, body.get("configuration") or {})
    if job["jobReference"].get("jobId") is None:
        return job
    return runner.wait(project_id, job_id)


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
    destination = job["configuration"].get("query", {}).get("destinationTable")
    if destination and destination["datasetId"] == tables.RESULTS:
        tables.delete(project_id, tables.RESULTS, job_id)
    store.delete(project_id, job_id)
    return {}


@router.post("/projects/{project_id}/queries")
def run_query(project_id: str, body: dict = Body()):
    configuration = {key: body[key] for key in QUERY_CONFIGURATION if key in body} | {
        "query": {
            key: value
            for key, value in body.items()
            if key not in (*QUERY_CONFIGURATION, "kind", "formatOptions", "timeoutMs")
        }
    }
    job_id = body.get("requestId") or str(uuid.uuid4())
    job = runner.submit(project_id, job_id, configuration)
    if job["jobReference"].get("jobId") is None:
        statistics = job["statistics"]["query"]
        return with_rows(
            {
                "kind": "bigquery#queryResponse",
                "jobReference": job["jobReference"],
                "jobComplete": True,
                "schema": statistics.get("schema"),
                "totalBytesProcessed": "0",
                "statementType": statistics.get("statementType"),
            },
            [],
        )
    job = runner.wait(project_id, job_id, body.get("timeoutMs"))
    if error := runner.error(job):
        raise runner.synchronous(error)
    int64_timestamps = (body.get("formatOptions") or {}).get("useInt64Timestamp", False)
    payload, rows = results(job, body.get("maxResults"), 0, int64_timestamps)
    statistics = job["statistics"]
    return with_rows(
        {"kind": "bigquery#queryResponse"}
        | payload
        | {
            "queryId": job_id,
            "location": "US",
            "creationTime": statistics["creationTime"],
            "startTime": statistics.get("startTime"),
            "endTime": statistics.get("endTime"),
            "jobCreationReason": job["jobCreationReason"],
            "sessionInfo": statistics.get("sessionInfo"),
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
