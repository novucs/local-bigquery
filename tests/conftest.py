import os
import threading
import time

import grpc
import pytest
import uvicorn
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery, bigquery_storage_v1
from hypothesis import settings
from google.cloud.bigquery_storage_v1.services.big_query_read.transports import (
    BigQueryReadGrpcTransport,
)
from google.cloud.bigquery_storage_v1.services.big_query_write.transports import (
    BigQueryWriteGrpcTransport,
)

from tests.cases import Query, unique

settings.register_profile("default", max_examples=20)
settings.register_profile("thorough", max_examples=500)


def pytest_configure(config):
    os.environ["TZ"] = "America/Los_Angeles"
    time.tzset()
    config.addinivalue_line("markers", "emulator(reason): emulator-only behaviour")
    if config.getoption("--endpoint") == "google":
        config.option.timeout = 300


def pytest_collection_modifyitems(config, items):
    if config.getoption("--endpoint") != "google":
        return
    for item in items:
        item.own_markers = [m for m in item.own_markers if m.name != "xfail"]


def pytest_runtest_setup(item):
    marker = item.get_closest_marker("emulator")
    if marker and item.config.getoption("--endpoint") == "google":
        pytest.skip(marker.args[0])


class Client(bigquery.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.created = []

    def create_dataset(self, dataset, *args, **kwargs):
        created = super().create_dataset(dataset, *args, **kwargs)
        self.created.append(created.reference)
        return created

    def close(self):
        for reference in self.created:
            self.delete_dataset(reference, delete_contents=True, not_found_ok=True)
        super().close()


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
        client = Client(project=project)
    else:
        client = Client(
            project=project,
            credentials=AnonymousCredentials(),
            client_options=ClientOptions(api_endpoint=endpoint),
        )
    yield client
    client.close()


@pytest.fixture(scope="session")
def storage_channel(request, endpoint):
    option = request.config.getoption("--endpoint")
    if option == "google":
        yield None
        return
    if option:
        pytest.skip("Storage API tests need the in-process emulator or real BigQuery")
    from local_bigquery.grpc import server

    grpc_server, port = server.start("127.0.0.1", 0)
    yield grpc.insecure_channel(f"127.0.0.1:{port}")
    grpc_server.stop(None)


@pytest.fixture(scope="session")
def bqstorage(storage_channel):
    if storage_channel is None:
        return bigquery_storage_v1.BigQueryReadClient()
    transport = BigQueryReadGrpcTransport(channel=storage_channel)
    return bigquery_storage_v1.BigQueryReadClient(transport=transport)


@pytest.fixture(scope="session")
def bqwrite(storage_channel):
    if storage_channel is None:
        return bigquery_storage_v1.BigQueryWriteClient()
    transport = BigQueryWriteGrpcTransport(channel=storage_channel)
    return bigquery_storage_v1.BigQueryWriteClient(transport=transport)


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
