import concurrent.futures
import contextlib
import re
from dataclasses import dataclass

import duckdb

from local_bigquery.catalog import metadata
from local_bigquery.engine import database, sessions
from local_bigquery.errors import (
    BigQueryError,
    already_exists,
    from_exception,
    not_found,
    not_implemented,
)
from local_bigquery.jobs import query, store

JOB_TYPES = ("query", "load", "copy", "extract")
ABORT_SESSION = re.compile(r"^\s*CALL\s+BQ\.ABORT_SESSION\s*\(\s*\)\s*;?\s*$", re.I)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)


@dataclass
class Running:
    future: concurrent.futures.Future | None = None
    cursor: duckdb.DuckDBPyConnection | None = None
    cancelled: bool = False


_running: dict[tuple[str, str], Running] = {}


def _job(project_id: str, job_id: str | None, configuration: dict, **extra) -> dict:
    now = metadata.now()
    return {
        "kind": "bigquery#job",
        "id": f"{project_id}:US.{job_id}",
        "selfLink": f"/bigquery/v2/projects/{project_id}/jobs/{job_id}?location=US",
        "jobReference": {"projectId": project_id, "jobId": job_id, "location": "US"},
        "configuration": configuration,
        "jobCreationReason": {"code": "REQUESTED"},
        "status": {"state": "PENDING"},
        "statistics": {"creationTime": now},
        "user_email": "local-bigquery@localhost",
    } | extra


def _done(job: dict, statistics: dict, error: BigQueryError | None = None) -> dict:
    status = {"state": "DONE"}
    if error:
        status |= {"errorResult": error.proto(), "errors": [error.proto()]}
    query_statistics = {
        "totalBytesProcessed": "0",
        "totalBytesBilled": "0",
        "cacheHit": False,
    } | statistics.pop("query", {})
    return job | {
        "status": status,
        "statistics": job["statistics"]
        | {
            "endTime": metadata.now(),
            "totalBytesProcessed": "0",
            "query": query_statistics,
        }
        | statistics,
    }


def _session(project_id: str, config: dict) -> sessions.Session | None:
    for prop in config.get("connectionProperties") or []:
        if prop.get("key") == "session_id":
            return sessions.get(prop.get("value"))
    return sessions.create(project_id) if config.get("createSession") else None


def get(project_id: str, job_id: str) -> dict:
    job = store.load(project_id, job_id)
    if job is None:
        raise not_found("Job", f"{project_id}:{job_id}")
    return job


def submit(project_id: str, job_id: str, configuration: dict) -> dict:
    job_type = next((kind for kind in JOB_TYPES if kind in configuration), None)
    if job_type != "query":
        raise not_implemented(f"{(job_type or 'unknown').capitalize()} jobs")
    configuration = configuration | {"jobType": "QUERY"}
    if configuration.get("dryRun"):
        return _dry_run(project_id, configuration)
    if store.load(project_id, job_id):
        raise already_exists("Job", f"{project_id}:{job_id}")
    session = _session(project_id, configuration["query"])
    job = store.save(_job(project_id, job_id, configuration))
    running = _running[(project_id, job_id)] = Running()
    running.future = _executor.submit(_execute, job, session, running)
    return job


def _dry_run(project_id: str, configuration: dict) -> dict:
    with database.cursor() as cur:
        statistics, _, _ = query.execute(
            cur, project_id, None, configuration["query"], dry_run=True
        )
    job = _job(project_id, None, configuration)
    job["jobReference"].pop("jobId")
    return _done(job, {"query": statistics})


def _execute(job: dict, session: sessions.Session | None, running: Running):
    project_id, job_id = job["jobReference"]["projectId"], job["jobReference"]["jobId"]
    job["statistics"]["startTime"] = metadata.now()
    job = store.save(job | {"status": {"state": "RUNNING"}})
    config = job["configuration"]["query"]
    statistics, children, destination, error = {}, [], None, None
    try:
        if running.cancelled:
            raise duckdb.InterruptException()
        with session.lock if session else contextlib.nullcontext():
            if session and ABORT_SESSION.match(config.get("query", "")):
                sessions.abort(session.id)
            else:
                cursor = session.cursor if session else database.connection().cursor()
                running.cursor = cursor
                try:
                    statistics, children, destination = query.execute(
                        cursor,
                        project_id,
                        job_id,
                        config,
                        isolated=bool(session),
                        variables=session.variables if session else None,
                    )
                finally:
                    if not session:
                        cursor.close()
    except Exception as exception:
        error = (
            BigQueryError(
                "stopped", "Job execution was cancelled: User requested cancellation"
            )
            if running.cancelled
            else from_exception(exception)
        )
    extra = {"query": statistics}
    if children:
        extra["numChildJobs"] = str(len(children))
    if session:
        extra["sessionInfo"] = {"sessionId": session.id}
    if destination:
        job["configuration"]["query"]["destinationTable"] = destination
    for index, child in enumerate(children):
        child_id = f"script_job_{job_id}_{index}"
        child_job = _job(project_id, child_id, job["configuration"])
        child_job["statistics"] |= {"parentJobId": job_id, "startTime": metadata.now()}
        store.save(_done(child_job, {"query": child}))
    store.save(_done(job, extra, error))
    _running.pop((project_id, job_id), None)


def wait(project_id: str, job_id: str, timeout_ms: int | None = None) -> dict:
    if running := _running.get((project_id, job_id)):
        timeout = 10 if timeout_ms is None else timeout_ms / 1000
        concurrent.futures.wait([running.future], timeout=timeout)
    return get(project_id, job_id)


def cancel(project_id: str, job_id: str) -> dict:
    get(project_id, job_id)
    if running := _running.get((project_id, job_id)):
        running.cancelled = True
        if running.cursor:
            running.cursor.interrupt()
    return wait(project_id, job_id, 1000)


def error(job: dict) -> BigQueryError | None:
    if result := job["status"].get("errorResult"):
        return BigQueryError(
            result["reason"], result["message"], result.get("location")
        )
    return None
