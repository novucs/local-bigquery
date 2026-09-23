import uuid

from local_bigquery import db
from local_bigquery.api import Router
from local_bigquery.db import timestamp_now
from local_bigquery.errors import not_found
from local_bigquery.models import (
    GetQueryResultsResponse,
    Job,
    JobCancelResponse,
    JobConfiguration,
    JobConfigurationQuery,
    JobCreationReason,
    JobList,
    JobListJobsItem,
    JobReference,
    JobStatistics,
    JobStatistics2,
    JobStatus,
    QueryRequest,
    QueryResponse,
)

router = Router(tags=["jobs"])


def pick(model, source) -> dict:
    return source.model_dump(include=model.model_fields.keys(), exclude_unset=True)


def get(project_id: str, job_id: str) -> Job:
    job = db.get_job(project_id, job_id)
    if job is None:
        raise not_found("Job", f"{project_id}:{job_id}")
    return job


def execute(
    project_id: str, job_id: str, config: JobConfiguration
) -> tuple[Job, GetQueryResultsResponse]:
    query = config.query
    dataset = query.defaultDataset
    rows, schema = db.query(
        dataset.projectId if dataset else project_id,
        dataset.datasetId if dataset else None,
        query.query,
        parameters=query.queryParameters,
    )
    now = timestamp_now()
    reference = JobReference(projectId=project_id, jobId=job_id, location="US")
    job = Job(
        configuration=config,
        id=job_id,
        jobCreationReason=JobCreationReason(code="REQUESTED"),
        jobReference=reference,
        selfLink=f"/bigquery/v2/projects/{project_id}/jobs/{job_id}",
        statistics=JobStatistics(
            creationTime=now,
            startTime=now,
            endTime=now,
            query=JobStatistics2(statementType="SELECT"),
        ),
        status=JobStatus(state="DONE"),
    )
    results = GetQueryResultsResponse(
        cacheHit=False,
        jobComplete=True,
        jobReference=reference,
        numDmlAffectedRows="0",
        rows=rows,
        schema=schema,
        totalBytesProcessed="0",
        totalRows=str(len(rows)),
    )
    db.create_job(project_id, job_id, job)
    db.set_query_results(project_id, job_id, results)
    return job, results


@router.get("/projects/{project_id}/jobs")
def list_jobs(project_id: str) -> JobList:
    return JobList(
        jobs=[
            JobListJobsItem.model_validate(pick(JobListJobsItem, job))
            for job in db.list_jobs(project_id)
        ]
    )


@router.post("/projects/{project_id}/jobs")
def insert_job(project_id: str, body: Job) -> Job:
    reference = body.jobReference
    job_id = reference.jobId if reference and reference.jobId else str(uuid.uuid4())
    job, _ = execute(project_id, job_id, body.configuration)
    return job


@router.get("/projects/{project_id}/jobs/{job_id}")
def get_job(project_id: str, job_id: str) -> Job:
    return get(project_id, job_id)


@router.post("/projects/{project_id}/jobs/{job_id}/cancel")
def cancel_job(project_id: str, job_id: str) -> JobCancelResponse:
    return JobCancelResponse(job=get(project_id, job_id))


@router.delete("/projects/{project_id}/jobs/{job_id}/delete", status_code=204)
def delete_job(project_id: str, job_id: str):
    get(project_id, job_id)
    db.delete_job(project_id, job_id)


@router.post("/projects/{project_id}/queries")
def query(project_id: str, body: QueryRequest) -> QueryResponse:
    config = JobConfiguration.model_validate(
        pick(JobConfiguration, body)
        | {"jobType": "QUERY", "query": pick(JobConfigurationQuery, body)}
    )
    job, results = execute(project_id, str(uuid.uuid4()), config)
    return QueryResponse(
        **pick(QueryResponse, results),
        queryId=job.id,
        location="US",
        creationTime=job.statistics.creationTime,
        startTime=job.statistics.startTime,
        endTime=job.statistics.endTime,
        jobCreationReason=job.jobCreationReason,
        totalBytesBilled="0",
        totalSlotMs="0",
    )


@router.get("/projects/{project_id}/queries/{job_id}")
def get_query_results(project_id: str, job_id: str) -> GetQueryResultsResponse:
    results = db.get_query_results(project_id, job_id)
    if results is None:
        raise not_found("Job", f"{project_id}:{job_id}")
    return results
