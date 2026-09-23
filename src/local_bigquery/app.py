import json
import logging
import pathlib
import re

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from local_bigquery.api import (
    datasets,
    jobs,
    models,
    projects,
    row_access_policies,
    routines,
    tables,
    uploads,
)
from local_bigquery.catalog import row_access
from local_bigquery.errors import BigQueryError, from_exception, not_implemented

DISCOVERY = json.loads((pathlib.Path(__file__).parent / "discovery.json").read_text())
PREFIX = "/" + DISCOVERY["servicePath"].rstrip("/")
PROJECT_ID = re.compile(r"^(?:[a-z0-9.-]+:)?[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")

app = FastAPI(title=DISCOVERY["title"], version=DISCOVERY["version"])


@app.exception_handler(Exception)
async def handle_error(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, RequestValidationError):
        error = BigQueryError("invalid", str(error))
    error = from_exception(error)
    if error.reason == "dontRetry":
        logging.exception(error.message, exc_info=error.__context__)
    return JSONResponse(error.response(), status_code=error.code)


for error_type in (BigQueryError, RequestValidationError):
    app.add_exception_handler(error_type, handle_error)


@app.middleware("http")
async def identify_caller(request: Request, call_next):
    headers = request.headers
    identity = row_access.identify(
        headers.get("x-bqemu-caller"), headers.get("x-bqemu-groups")
    )
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
        raise BigQueryError("accessDenied", f"Access Denied: Project {project_id}")


def methods(resource: dict):
    for child in resource.get("resources", {}).values():
        yield from child.get("methods", {}).values()
        yield from methods(child)


def stub(method_id: str):
    def handler():
        raise not_implemented(method_id)

    return handler


for module in (projects, datasets, tables, jobs, models, routines, row_access_policies):
    app.include_router(
        module.router, prefix=PREFIX, dependencies=[Depends(valid_project)]
    )

app.include_router(
    uploads.router, prefix=f"/upload{PREFIX}", dependencies=[Depends(valid_project)]
)

for method in methods(DISCOVERY):
    path = re.sub(r"\{\+resource\}", "{resource:path}", method["path"])
    app.add_api_route(
        f"{PREFIX}/{path.replace('{+', '{')}",
        stub(method["id"]),
        methods=[method["httpMethod"]],
        include_in_schema=False,
    )
