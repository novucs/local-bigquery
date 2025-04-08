import threading
import time

import pytest
import requests
import uvicorn
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery
from google.cloud.bigquery import QueryJobConfig

from local_bigquery import app, db


@pytest.fixture(scope="session")
def server_url():
    db.clear()
    host = "127.0.0.1"
    port = 8000
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://{host}:{port}"
    # Wait for the server to start
    start_time = time.time()
    while True:
        if time.time() - start_time > 5:
            raise Exception("Server did not start in time")
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
    bq = bigquery.Client(
        project="project1",
        credentials=AnonymousCredentials(),
        client_options=ClientOptions(api_endpoint=server_url),
        default_query_job_config=bigquery.QueryJobConfig(
            default_dataset="project1.dataset1",
        ),
    )
    try:
        yield bq
    finally:
        bq.close()


def query(
    bq: bigquery.Client,
    sql: str,
    config: bigquery.QueryJobConfig = None,
) -> list[dict]:
    return [dict(row.items()) for row in bq.query(sql, job_config=config).result()]


def test_create_table(bq):
    bq.create_dataset("test_dataset")
    bq.delete_table("`bigquery-public-data`.test_dataset.test_table", not_found_ok=True)
    bq.create_table(
        bigquery.Table(
            "`bigquery-public-data`.test_dataset.test_table",
            schema=[
                bigquery.SchemaField("name", "STRING"),
                bigquery.SchemaField("age", "INTEGER"),
            ],
        )
    )


def test_query(bq):
    assert query(bq, "SELECT 1 AS a") == [{"a": 1}]


def test_multi_query(bq):
    bq.create_dataset("dataset1")
    query(bq, "DROP TABLE IF EXISTS project1.dataset1.table1")
    query(bq, "CREATE TABLE project1.dataset1.table1 AS SELECT 1 AS b")
    assert query(bq, "SELECT * FROM project1.dataset1.table1") == [{"b": 1}]


def test_json(bq):
    bq.delete_table("project1.dataset1.table2", not_found_ok=True)
    bq.create_table(
        bigquery.Table(
            "project1.dataset1.table2",
            schema=[
                bigquery.SchemaField("data", "JSON"),
            ],
        )
    )
    query(
        bq,
        """
        INSERT INTO dataset1.table2 (data)
        VALUES
        ('{"x": 1, "y": 2, "$tricky": "this has a tricky key"}')
        """,
    )
    assert query(bq, "SELECT * FROM dataset1.table2") == [
        {"data": '{"x": 1, "y": 2, "$tricky": "this has a tricky key"}'}
    ]
    assert query(bq, "SELECT data.x FROM dataset1.table2") == [{"x": "1"}]
    assert query(
        bq, """SELECT JSON_VALUE(data, '$."$tricky"') AS tricky FROM table2"""
    ) == [{"tricky": "this has a tricky key"}]


def test_args(bq):
    bq.delete_table("project1.dataset1.table3", not_found_ok=True)
    bq.create_table(
        bigquery.Table(
            "project1.dataset1.table3",
            schema=[
                bigquery.SchemaField("data", "STRING"),
            ],
        )
    )
    query(
        bq,
        """
        INSERT INTO dataset1.table3 (data)
        VALUES
        ('one'),
        ('two'),
        ('three')
        """,
    )
    assert query(
        bq,
        "SELECT * FROM dataset1.table3 WHERE data=@arg",
        config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("arg", "STRING", "one"),
            ],
        ),
    ) == [{"data": "one"}]


def test_complex_args(bq):
    assert query(
        bq,
        "SELECT @user AS user",
        config=QueryJobConfig(
            query_parameters=[
                bigquery.StructQueryParameter(
                    "user",
                    bigquery.ScalarQueryParameter("id", "STRING", "123"),
                    bigquery.ScalarQueryParameter("name", "STRING", "John Doe"),
                    bigquery.ArrayQueryParameter(
                        "scores",
                        "STRING",
                        ["85", "90"],
                    ),
                )
            ]
        ),
    ) == [
        {
            "user": {"id": "123", "name": "John Doe", "scores": ["85", "90"]},
        }
    ]


def test_bulk_insert(bq):
    bq.create_dataset("`bigquery-public-data`.test_dataset", exists_ok=True)
    bq.delete_table("`bigquery-public-data`.test_dataset.test_table", not_found_ok=True)
    table = bq.create_table(
        bigquery.Table(
            "`bigquery-public-data`.test_dataset.test_table",
            schema=[
                bigquery.SchemaField("name", "STRING"),
                bigquery.SchemaField("age", "INTEGER"),
            ],
        )
    )
    bq.insert_rows(
        table,
        [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ],
    )
    assert query(
        bq, "SELECT * FROM `bigquery-public-data`.test_dataset.test_table"
    ) == [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ]
