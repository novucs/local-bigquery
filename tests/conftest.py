import os
import threading
import time

import pytest
import uvicorn
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

from tests.cases import Query, unique


def pytest_configure(config):
    os.environ["TZ"] = "America/Los_Angeles"
    time.tzset()


def pytest_addoption(parser):
    parser.addoption(
        "--endpoint",
        help="Run against this BigQuery endpoint instead of an in-process server. "
        "Use 'google' for real BigQuery with application default credentials.",
    )
    parser.addoption("--project", default="test-project")


@pytest.fixture(scope="session")
def project(request) -> str:
    return request.config.getoption("--project")


@pytest.fixture(scope="session")
def endpoint(request, tmp_path_factory):
    if endpoint := request.config.getoption("--endpoint"):
        yield endpoint
        return
    from local_bigquery import app
    from local_bigquery.settings import settings

    settings.data_dir = tmp_path_factory.mktemp("data")
    server = uvicorn.Server(uvicorn.Config(app, port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        thread.join(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join()


@pytest.fixture(scope="session")
def bq(endpoint, project):
    if endpoint == "google":
        client = bigquery.Client(project=project)
    else:
        client = bigquery.Client(
            project=project,
            credentials=AnonymousCredentials(),
            client_options=ClientOptions(api_endpoint=endpoint),
        )
    yield client
    client.close()


@pytest.fixture(scope="module")
def dataset(bq) -> bigquery.Dataset:
    dataset = bq.create_dataset(unique("test"))
    yield dataset
    bq.delete_dataset(dataset, delete_contents=True, not_found_ok=True)


@pytest.fixture
def check(bq, dataset):
    def check(case: Query):
        case.check(bq, dataset)

    return check
