import email
import email.policy
import re
import uuid

import pydantic
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from local_bigquery.api import Router
from local_bigquery.errors import BigQueryError, invalid_payload
from local_bigquery.jobs import runner
from local_bigquery.models import Job
from local_bigquery.settings import settings

router = Router(tags=["jobs"])
CONTENT_RANGE = re.compile(r"bytes (?:\d+-\d+|\*)/(\d+|\*)")
_resumable: dict[str, tuple[str, Job]] = {}


def _file(upload_id: str) -> str:
    directory = settings.data_dir / "uploads"
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory / upload_id)


def _job(payload: bytes) -> Job:
    try:
        return Job.model_validate_json(payload)
    except pydantic.ValidationError as error:
        raise invalid_payload(error.errors()[0])


def _start(project_id: str, body: Job, upload: str) -> JSONResponse:
    job_id = (body.jobReference and body.jobReference.jobId) or str(uuid.uuid4())
    configuration = body.configuration.given() if body.configuration else {}
    runner.submit(project_id, job_id, configuration, upload)
    return JSONResponse(runner.submitted(project_id, job_id))


def _parts(content_type: str, payload: bytes) -> tuple[Job, bytes]:
    header = f"Content-Type: {content_type}\r\n\r\n".encode()
    message = email.message_from_bytes(header + payload, policy=email.policy.HTTP)
    parts = [part.get_payload(decode=True) for part in message.iter_parts()]
    if len(parts) != 2:
        raise BigQueryError("invalid", "Multipart upload must have two parts")
    return _job(parts[0]), parts[1]


@router.post("/projects/{project_id}/jobs")
async def upload(project_id: str, uploadType: str, request: Request):
    upload_id = str(uuid.uuid4())
    if uploadType == "multipart":
        body, data = _parts(request.headers["content-type"], await request.body())
        with open(_file(upload_id), "wb") as file:
            file.write(data)
        return await run_in_threadpool(_start, project_id, body, _file(upload_id))
    if uploadType != "resumable":
        raise BigQueryError("invalid", f"Unsupported uploadType: {uploadType}")
    _resumable[upload_id] = (project_id, _job(await request.body()))
    open(_file(upload_id), "wb").close()
    location = request.url.include_query_params(upload_id=upload_id)
    return Response(
        headers={"Location": str(location), "X-GUploader-UploadID": upload_id}
    )


@router.put("/projects/{project_id}/jobs")
async def upload_chunk(project_id: str, upload_id: str, request: Request):
    if upload_id not in _resumable:
        raise BigQueryError("notFound", f"Not found: Upload {upload_id}")
    with open(_file(upload_id), "ab") as file:
        file.write(await request.body())
        size = file.tell()
    match = CONTENT_RANGE.match(request.headers.get("content-range", ""))
    if match and (match[1] == "*" or int(match[1]) > size):
        received = {"Range": f"bytes=0-{size - 1}"} if size else {}
        return Response(status_code=308, headers=received)
    _, body = _resumable.pop(upload_id)
    return await run_in_threadpool(_start, project_id, body, _file(upload_id))
