import gzip
import json
import logging
import pathlib
import re

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from local_bigquery.api import (
    datasets,
    iam,
    jobs,
    models,
    projects,
    row_access_policies,
    routines,
    tables,
    uploads,
)
from local_bigquery.catalog import row_access
from local_bigquery.errors import (
    BigQueryError,
    from_exception,
    invalid_payload,
    not_implemented,
)

DISCOVERY = json.loads((pathlib.Path(__file__).parent / "discovery.json").read_text())
PREFIX = "/" + DISCOVERY["servicePath"].rstrip("/")
PROJECT_ID = re.compile(r"^(?:[a-z0-9.-]+:)?[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")

app = FastAPI(title=DISCOVERY["title"], version=DISCOVERY["version"])


def _invalid(problem: dict) -> BigQueryError:
    source, *field = problem["loc"]
    if source == "body":
        return invalid_payload(problem | {"loc": field})
    return BigQueryError("invalid", f"Invalid value for {field[-1]}: {problem['msg']}")


@app.exception_handler(Exception)
async def handle_error(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, RequestValidationError):
        error = _invalid(error.errors()[0])
    error = from_exception(error)
    if error.reason == "dontRetry":
        logging.exception(error.message, exc_info=error.__context__)
    return JSONResponse(error.response(), status_code=error.code)


for error_type in (BigQueryError, RequestValidationError):
    app.add_exception_handler(error_type, handle_error)


class GzipRequests:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        if scope["type"] != "http" or headers.get(b"content-encoding") != b"gzip":
            return await self.app(scope, receive, send)
        body, more = b"", True
        while more:
            message = await receive()
            body += message.get("body", b"")
            more = message.get("more_body", False)
        body = gzip.decompress(body)
        headers.pop(b"content-encoding")
        headers[b"content-length"] = str(len(body)).encode()
        messages = iter([{"type": "http.request", "body": body}])

        async def replay():
            return next(messages, None) or await receive()

        scope = {**scope, "headers": list(headers.items())}
        await self.app(scope, replay, send)


app.add_middleware(GzipRequests)


@app.middleware("http")
async def identify_caller(request: Request, call_next):
    identity = row_access.identify(request.headers.get("authorization"))
    token = row_access.caller.set(identity)
    try:
        return await call_next(request)
    finally:
        row_access.caller.reset(token)


@app.get("/$discovery/rest", include_in_schema=False)
@app.get("/discovery/v1/apis/bigquery/v2/rest", include_in_schema=False)
def discovery():
    return DISCOVERY


def valid_project(request: Request):
    project_id = request.path_params.get("project_id")
    if project_id is not None and not PROJECT_ID.match(project_id):
        raise BigQueryError("invalid", f"Invalid project ID: {project_id}")


def methods(resource: dict):
    for child in resource.get("resources", {}).values():
        yield from child.get("methods", {}).values()
        yield from methods(child)


def stub(method_id: str):
    def handler():
        raise not_implemented(method_id)

    return handler


for module in (
    projects,
    datasets,
    tables,
    jobs,
    models,
    routines,
    row_access_policies,
    iam,
):
    app.include_router(
        module.router, prefix=PREFIX, dependencies=[Depends(valid_project)]
    )

app.include_router(
    uploads.router, prefix=f"/upload{PREFIX}", dependencies=[Depends(valid_project)]
)

for method in methods(DISCOVERY):
    app.add_api_route(
        f"{PREFIX}/{method['path'].replace('{+', '{')}",
        stub(method["id"]),
        methods=[method["httpMethod"]],
        include_in_schema=False,
    )
