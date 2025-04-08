import threading
import time

import pytest
import requests
import uvicorn
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

from pybigquery import app


@pytest.fixture(scope="session")
def server_url():
    host = "127.0.0.1"
    port = 8000
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://{host}:{port}"
    # Wait for the server to start
    while True:
        try:
            requests.get(url)
            break
        except requests.ConnectionError:
            time.sleep(0.01)
    yield url
    server.should_exit = True
    thread.join()


@pytest.fixture
def bq(server_url):
    # disable retries
    bigquery.DEFAULT_RETRY._timeout = 0
    bq = bigquery.Client(
        project="bigquery-public-data",
        credentials=AnonymousCredentials(),
        client_options=ClientOptions(api_endpoint=server_url),
    )
    yield bq
    bq.close()


def test_create_table(bq):
    bq.delete_table("bigquery-public-data.test_dataset.test_table")
    bq.create_table(
        bigquery.Table(
            "bigquery-public-data.test_dataset.test_table",
            schema=[
                bigquery.SchemaField("name", "STRING"),
                bigquery.SchemaField("age", "INTEGER"),
            ],
        )
    )


def test_query(bq):
    assert bq.query("SELECT 1 AS a").to_dataframe().to_dict(orient="records") == [
        {"a": 1}
    ]
