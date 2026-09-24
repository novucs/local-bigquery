import concurrent.futures
import contextvars
import contextlib
import os
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
)
from local_bigquery.jobs import copy, extract, load, query, store
from local_bigquery.models import (
    Job,
    JobConfiguration,
    JobConfigurationQuery,
    JobStatistics,
    JobStatistics2,
    JobStatus,
)

JOB_TYPES = {"query": "query", "load": "load", "copy": "copy_", "extract": "extract"}
SUBMIT_WAIT_MS = 1000
HANDLERS = {"load": load.run, "copy": copy.run, "extract": extract.run}
QUERY_STATISTICS = {
    "totalBytesProcessed": "0",
    "totalBytesBilled": "0",
    "cacheHit": False,
}
ABORT_SESSION = re.compile(r"^\s*CALL\s+BQ\.ABORT_SESSION\s*\(\s*\)\s*;?\s*$", re.I)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)


@dataclass
class Running:
    future: concurrent.futures.Future | None = None
    cursor: duckdb.DuckDBPyConnection | None = None
    cancelled: bool = False


_running: dict[tuple[str, str], Running] = {}


def _job(project_id: str, job_id: str | None, configuration: JobConfiguration) -> Job:
    return Job(
        id=f"{project_id}:US.{job_id}",
        selfLink=f"/bigquery/v2/projects/{project_id}/jobs/{job_id}?location=US",
        jobReference={"projectId": project_id, "jobId": job_id, "location": "US"},
        configuration=configuration,
        jobCreationReason={"code": "REQUESTED"},
        status={"state": "PENDING"},
        statistics={"creationTime": metadata.now()},
        user_email="local-bigquery@localhost",
    )


def _done(
    job: Job, statistics: JobStatistics, error: BigQueryError | None = None
) -> Job:
    status = JobStatus(state="DONE")
    if error:
        status = status.replace(errorResult=error.proto(), errors=[error.proto()])
    if statistics.query:
        query = JobStatistics2.model_validate(
            QUERY_STATISTICS | statistics.query.dump()
        )
        statistics = statistics.replace(query=query)
    finished = {"endTime": metadata.now(), "totalBytesProcessed": "0"}
    return job.replace(
        status=status,
        statistics=job.statistics.replace(**finished | statistics.dump()),
    )


def _session(project_id: str, config: JobConfigurationQuery) -> sessions.Session | None:
    for prop in config.connectionProperties or []:
        if prop.key == "session_id":
            return sessions.get(prop.value)
    return sessions.create(project_id) if config.createSession else None


def get(project_id: str, job_id: str) -> Job:
    job = store.load(project_id, job_id)
    if job is None:
        raise not_found("Job", f"{project_id}:{job_id}")
    return job


def submit(
    project_id: str,
    job_id: str,
    configuration: JobConfiguration,
    upload: str | None = None,
) -> Job:
    given = configuration.dump()
    job_type = next((kind for kind in JOB_TYPES if kind in given), None)
    if job_type is None:
        raise BigQueryError("invalid", "Job configuration must specify a job type")
    configuration = configuration.replace(jobType=job_type.upper())
    if job_type == "load":
        load.validate(configuration.load)
    if job_type == "query" and configuration.dryRun:
        return _dry_run(project_id, configuration)
    if store.load(project_id, job_id):
        raise already_exists("Job", f"{project_id}:{job_id}")
    session = _session(project_id, configuration.query) if job_type == "query" else None
    job = store.save(_job(project_id, job_id, configuration))
    running = _running[(project_id, job_id)] = Running()
    context = contextvars.copy_context()
    running.future = _executor.submit(
        context.run, _execute, job, job_type, session, running, upload
    )
    return job


def _dry_run(project_id: str, configuration: JobConfiguration) -> Job:
    with database.cursor() as cur:
        try:
            statistics, _, _ = query.execute(
                cur, project_id, None, configuration.query, dry_run=True
            )
        except Exception as exception:
            raise synchronous(from_exception(exception)) from exception
    job = _job(project_id, None, configuration)
    job = job.replace(jobReference=job.jobReference.without("jobId"))
    return _done(job, JobStatistics(query=statistics))


def _query(
    job: Job, session: sessions.Session | None, running: Running
) -> JobStatistics:
    project_id, job_id = job.jobReference.projectId, job.jobReference.jobId
    config = job.configuration.query
    with session.lock if session else contextlib.nullcontext():
        if session and ABORT_SESSION.match(config.query or ""):
            sessions.abort(session.id)
            return JobStatistics(query={})
        cursor = session.cursor if session else database.connection().cursor()
        running.cursor = cursor
        try:
            statistics, children, destination = query.execute(
                cursor,
                project_id,
                job_id,
                config,
                session=session,
            )
        finally:
            if not session:
                cursor.close()
    if destination:
        config.destinationTable = destination
    for index, child in enumerate(children):
        child_job = _job(project_id, f"script_job_{job_id}_{index}", job.configuration)
        child_statistics = JobStatistics(
            parentJobId=job_id, startTime=metadata.now(), query=child
        )
        store.save(_done(child_job, child_statistics))
    result = JobStatistics(query=statistics)
    return result.replace(numChildJobs=str(len(children))) if children else result


def _handle(
    job: Job, job_type: str, running: Running, upload: str | None
) -> JobStatistics:
    with database.cursor() as cursor:
        running.cursor = cursor
        try:
            config = getattr(job.configuration, JOB_TYPES[job_type])
            result = HANDLERS[job_type](cursor, config, upload)
            return JobStatistics.model_validate({job_type: result})
        finally:
            if upload:
                os.remove(upload)


def _execute(
    job: Job,
    job_type: str,
    session: sessions.Session | None,
    running: Running,
    upload: str | None,
):
    project_id, job_id = job.jobReference.projectId, job.jobReference.jobId
    started = job.statistics.replace(startTime=metadata.now())
    job = store.save(job.replace(status={"state": "RUNNING"}, statistics=started))
    statistics, error = JobStatistics.model_validate({job_type: {}}), None
    try:
        if running.cancelled:
            raise duckdb.InterruptException()
        if job_type == "query":
            statistics = _query(job, session, running)
        else:
            statistics = _handle(job, job_type, running, upload)
    except Exception as exception:
        error = (
            BigQueryError(
                "stopped", "Job execution was cancelled: User requested cancellation"
            )
            if running.cancelled
            else from_exception(exception)
        )
    if session:
        statistics = statistics.replace(sessionInfo={"sessionId": session.id})
    store.save(_done(job, statistics, error))
    _running.pop((project_id, job_id), None)


def submitted(project_id: str, job_id: str) -> Job:
    return wait(project_id, job_id, SUBMIT_WAIT_MS)


def wait(project_id: str, job_id: str, timeout_ms: int | None = None) -> Job:
    if running := _running.get((project_id, job_id)):
        timeout = 10 if timeout_ms is None else timeout_ms / 1000
        concurrent.futures.wait([running.future], timeout=timeout)
    return get(project_id, job_id)


def cancel(project_id: str, job_id: str) -> Job:
    get(project_id, job_id)
    if running := _running.get((project_id, job_id)):
        running.cancelled = True
        if running.cursor:
            running.cursor.interrupt()
    return wait(project_id, job_id, 1000)


def synchronous(error: BigQueryError) -> BigQueryError:
    error.location = "q" if error.location == "query" else None
    return error


def error(job: Job) -> BigQueryError | None:
    if result := job.status.errorResult:
        return BigQueryError(result.reason, result.message, result.location)
    return None
