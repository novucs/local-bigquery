import dataclasses
import threading
import uuid

import pytest


@dataclasses.dataclass(frozen=True)
class Emulator:
    rest_url: str
    grpc_address: str
    project_id: str


@pytest.fixture(scope="session")
def bigquery_emulator(tmp_path_factory):
    import uvicorn

    from local_bigquery import app
    from local_bigquery.grpc import server
    from local_bigquery.settings import settings

    settings.data_dir = tmp_path_factory.mktemp("local-bigquery")
    storage, grpc_port = server.start("127.0.0.1", 0)
    rest = uvicorn.Server(uvicorn.Config(app, port=0, log_level="warning"))
    thread = threading.Thread(target=rest.run, daemon=True)
    thread.start()
    while not rest.started and thread.is_alive():
        thread.join(0.01)
    rest_port = rest.servers[0].sockets[0].getsockname()[1]
    yield Emulator(
        f"http://127.0.0.1:{rest_port}",
        f"127.0.0.1:{grpc_port}",
        settings.default_project_id,
    )
    rest.should_exit = True
    thread.join()
    storage.stop(None)


@pytest.fixture(scope="session")
def bigquery_client(bigquery_emulator):
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import bigquery

    client = bigquery.Client(
        project=bigquery_emulator.project_id,
        credentials=AnonymousCredentials(),
        client_options={"api_endpoint": bigquery_emulator.rest_url},
    )
    yield client
    client.close()


@pytest.fixture
def bigquery_dataset(bigquery_client):
    dataset = bigquery_client.create_dataset(f"test_{uuid.uuid4().hex}")
    yield dataset
    bigquery_client.delete_dataset(dataset, delete_contents=True, not_found_ok=True)
