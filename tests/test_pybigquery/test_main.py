import threading
import time

import google
import pytest
import requests
import uvicorn
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

from local_bigquery import app


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
    bigquery.DEFAULT_RETRY._timeout = 1
    google.cloud.bigquery.retry.DEFAULT_RETRY._timeout = 1
    google.cloud.bigquery.retry.DEFAULT_JOB_RETRY._timeout = 1
    bq = bigquery.Client(
        project="bigquery-public-data",
        credentials=AnonymousCredentials(),
        client_options=ClientOptions(api_endpoint=server_url),
    )
    try:
        yield bq
    finally:
        bq.close()


def query(bq: bigquery.Client, sql: str) -> list[dict]:
    return [dict(row.items()) for row in bq.query(sql).result()]


def test_create_table(bq):
    bq.delete_table("bigquery-public-data.test_dataset.test_table", not_found_ok=True)
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
    assert query(bq, "SELECT 1 AS a") == [{"a": 1}]


def test_multi_query(bq):
    query(bq, "DROP TABLE IF EXISTS project1.dataset1.table1")
    query(bq, "CREATE TABLE project1.dataset1.table1 AS SELECT 1 AS b")
    assert query(bq, "SELECT * FROM project1.dataset1.table1") == [{"b": 1}]
