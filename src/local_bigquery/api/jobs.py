import uuid

from fastapi import Body, Query

from local_bigquery.api import Router, paginate, with_rows
from local_bigquery.catalog import metadata
from local_bigquery.engine import database, results
from local_bigquery.errors import already_exists, not_found, not_implemented
from local_bigquery.jobs import query
from local_bigquery.models import (
    Job,
    JobCancelResponse,
    JobList,
    JobListJobsItem,
)

router = Router(tags=["jobs"])
LIST_FIELDS = set(JobListJobsItem.model_fields)


def load(project_id: str, job_id: str) -> dict:
    job = metadata.load("jobs", project_id, job_id)
    if job is None:
        raise not_found("Job", f"{project_id}:{job_id}")
    return job


def execute(project_id: str, job_id: str, configuration: dict) -> dict:
    if metadata.load("jobs", project_id, job_id):
        raise already_exists("Job", f"{project_id}:{job_id}")
    if "query" not in configuration:
        kind = next(
            iter(configuration.keys() - {"dryRun", "labels", "jobTimeoutMs"}), ""
        )
        raise not_implemented(f"{kind.capitalize()} jobs")
    now = metadata.now()
    statistics = query.run(project_id, job_id, configuration["query"])
    reference = {"projectId": project_id, "jobId": job_id, "location": "US"}
    job = {
        "kind": "bigquery#job",
        "id": f"{project_id}:US.{job_id}",
        "selfLink": f"/bigquery/v2/projects/{project_id}/jobs/{job_id}?location=US",
        "jobReference": reference,
        "configuration": configuration | {"jobType": "QUERY"},
        "jobCreationReason": {"code": "REQUESTED"},
        "status": {"state": "DONE"},
        "statistics": {
            "creationTime": now,
            "startTime": now,
            "endTime": metadata.now(),
            "query": {"statementType": "SELECT", **statistics},
            **statistics,
        },
    }
    return metadata.save("jobs", job, project_id, job_id)


def query_results(
    job: dict, max_results: int | None, start: int, int64_timestamps: bool
) -> tuple[dict, list[str]]:
    reference = job["jobReference"]
    table = query.results_table(reference["projectId"], reference["jobId"])
    payload = {
        "jobReference": reference,
        "jobComplete": True,
        "cacheHit": False,
        "totalBytesProcessed": "0",
        "numDmlAffectedRows": job["statistics"].get("numDmlAffectedRows"),
        "schema": {"fields": []},
        "totalRows": "0",
    }
    if not database.fetch(
        "SELECT 1 FROM duckdb_tables() WHERE database_name = 'emulator' "
        "AND schema_name = '_results' AND table_name = ?",
        [f"{reference['projectId']}:{reference['jobId']}"],
    ):
        return payload, []
    with database.cursor() as cur:
        page = results.page(cur, table, max_results, start, None, int64_timestamps)
        fields = results.schema(cur, table)
    payload |= {
        "schema": {"fields": [f.model_dump(exclude_none=True) for f in fields]},
        "totalRows": str(page.total),
        "pageToken": page.next_token,
    }
    return payload, page.rows


@router.get("/projects/{project_id}/jobs")
def list_jobs(
    project_id: str, maxResults: int | None = None, pageToken: str | None = None
) -> JobList:
    jobs = [
        {key: value for key, value in job.items() if key in LIST_FIELDS}
        | {"state": job["status"]["state"]}
        for job in metadata.list_("jobs", project_id)
    ]
    page, token = paginate(jobs, maxResults, pageToken)
    return JobList(kind="bigquery#jobList", jobs=page, nextPageToken=token)


@router.post("/projects/{project_id}/jobs")
def insert_job(project_id: str, body: dict = Body()) -> Job:
    job_id = (body.get("jobReference") or {}).get("jobId") or str(uuid.uuid4())
    return execute(project_id, job_id, body.get("configuration") or {})


@router.get("/projects/{project_id}/jobs/{job_id}")
def get_job(project_id: str, job_id: str) -> Job:
    return load(project_id, job_id)


@router.post("/projects/{project_id}/jobs/{job_id}/cancel")
def cancel_job(project_id: str, job_id: str) -> JobCancelResponse:
    return JobCancelResponse(
        kind="bigquery#jobCancelResponse", job=load(project_id, job_id)
    )


@router.delete("/projects/{project_id}/jobs/{job_id}/delete", status_code=204)
def delete_job(project_id: str, job_id: str):
    load(project_id, job_id)
    database.execute(f"DROP TABLE IF EXISTS {query.results_table(project_id, job_id)}")
    metadata.delete("jobs", project_id, job_id)


@router.post("/projects/{project_id}/queries")
def run_query(project_id: str, body: dict = Body()):
    configuration = {
        key: value
        for key, value in body.items()
        if key in ("dryRun", "labels", "jobTimeoutMs")
    } | {"query": {k: v for k, v in body.items() if k not in ("kind", "formatOptions")}}
    job = execute(project_id, str(uuid.uuid4()), configuration)
    int64_timestamps = (body.get("formatOptions") or {}).get("useInt64Timestamp", False)
    payload, rows = query_results(job, body.get("maxResults"), 0, int64_timestamps)
    statistics = job["statistics"]
    return with_rows(
        {"kind": "bigquery#queryResponse"}
        | payload
        | {
            "queryId": job["jobReference"]["jobId"],
            "location": "US",
            "creationTime": statistics["creationTime"],
            "startTime": statistics["startTime"],
            "endTime": statistics["endTime"],
            "jobCreationReason": job["jobCreationReason"],
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
    int64_timestamps: bool = Query(False, alias="formatOptions.useInt64Timestamp"),
):
    job = load(project_id, job_id)
    start = int(pageToken) if pageToken else startIndex
    payload, rows = query_results(job, maxResults, start, int64_timestamps)
    return with_rows({"kind": "bigquery#getQueryResultsResponse"} | payload, rows)
