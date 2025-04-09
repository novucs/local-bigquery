import pathlib
import threading
import time
from datetime import datetime

import pytest
import requests
import uvicorn
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery
from google.cloud.bigquery import QueryJobConfig
from sqlalchemy import column, create_engine, select, text

from local_bigquery.__main__ import app, db
from local_bigquery.settings import settings


@pytest.fixture(scope="session")
def server_url():
    settings.database_path = pathlib.Path("/tmp/local-bigquery")
    db.clear()
    host = "127.0.0.1"
    port = 9050
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
    return [dict(row.items()) for row in bq.query_and_wait(sql, job_config=config)]


def test_default_dataset(server_url):
    bq = bigquery.Client(
        project="project1",
        credentials=AnonymousCredentials(),
        client_options=ClientOptions(api_endpoint=server_url),
        default_query_job_config=QueryJobConfig(
            default_dataset=bigquery.DatasetReference("project1", "dataset1"),
        ),
    )
    bq.query("create schema if not exists dataset1")
    assert query(
        bq,
        "select current_catalog() as project, current_schema() as dataset",
    ) == [{"project": "project1", "dataset": "dataset1"}]


def test_create_table(bq):
    bq.create_dataset("bigquery-public-data.test_dataset2")
    bq.create_table(
        bigquery.Table(
            "`bigquery-public-data`.test_dataset2.test_table",
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
        {"data": {"x": 1, "y": 2, "$tricky": "this has a tricky key"}}
    ]
    assert query(bq, "SELECT data.x FROM dataset1.table2") == [{"x": 1}]
    assert query(
        bq, """SELECT JSON_VALUE(data, '$."$tricky"') AS tricky FROM dataset1.table2"""
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


def test_create_record_table(bq):
    bq.create_dataset("project.nested_dataset")
    table = bigquery.Table(
        "project.nested_dataset.nested_table",
        schema=[
            bigquery.SchemaField("id", "INTEGER", "REQUIRED"),
            bigquery.SchemaField(
                "nested",
                "RECORD",
                "REPEATED",
                fields=[
                    bigquery.SchemaField("item", "TEXT"),
                ],
            ),
        ],
    )
    bq.create_table(table, exists_ok=True)
    data = [
        {
            "id": 1,
            "nested": [
                {"item": "item1"},
                {"item": "item2"},
                {"item": None},
            ],
        }
    ]
    bq.insert_rows(table, data)
    assert query(bq, "SELECT * FROM project.nested_dataset.nested_table") == data


def test_bigquery_jobs_query(bq):
    bq.create_dataset("project1.dataset1")
    bq.delete_table("project1.dataset1.table1", not_found_ok=True)
    table = bigquery.Table(
        "project1.dataset1.table1",
        schema=[
            bigquery.SchemaField("id", "INTEGER"),
        ],
    )
    bq.create_table(table)
    bq.insert_rows(
        table,
        [
            {"id": 1},
            {"id": 2},
        ],
    )
    engine = create_engine(
        "bigquery://project1/dataset1?user_supplied_client=True",
        connect_args={"client": bq},
    )
    with engine.connect() as conn:
        result = conn.execute(
            select(column("id")).select_from(text("project1.dataset1.table1"))
        )
        assert result.fetchall() == [(1,), (2,)]


def test_table_aliasing(bq):
    bq.create_dataset("project1.dataset1")
    bq.delete_table("project1.dataset1.table1", not_found_ok=True)
    table = bigquery.Table(
        "project1.dataset1.table1",
        schema=[
            bigquery.SchemaField("id", "INTEGER"),
        ],
    )
    bq.create_table(table)
    bq.insert_rows(
        table,
        [
            {"id": 1},
            {"id": 2},
        ],
    )
    engine = create_engine(
        "bigquery://project1/dataset1?user_supplied_client=True",
        connect_args={"client": bq},
    )
    with engine.connect() as conn:
        result = conn.execute(
            select(column("t.id")).select_from(text("dataset1.table1 AS t"))
        )
        assert result.fetchall() == [(1,), (2,)]


def test_timestamps(bq):
    bq.create_dataset("project1.dataset1")
    bq.delete_table("project1.dataset1.table1", not_found_ok=True)
    table = bigquery.Table(
        "project1.dataset1.table1",
        schema=[
            bigquery.SchemaField("id", "INTEGER"),
            bigquery.SchemaField("ts", "TIMESTAMP"),
        ],
    )
    bq.create_table(table)
    bq.insert_rows(
        table,
        [
            {"id": 1, "ts": "2023-01-01T00:00:00Z"},
            {"id": 2, "ts": "2023-01-02T00:00:00Z"},
        ],
    )
    engine = create_engine(
        "bigquery://project1/dataset1?user_supplied_client=True",
        connect_args={"client": bq},
    )
    with engine.connect() as conn:
        result = conn.execute(
            select(column("id"), column("ts")).select_from(text("dataset1.table1"))
        )
        assert result.fetchall() == [
            (1, datetime.fromisoformat("2023-01-01T00:00:00+00:00")),
            (2, datetime.fromisoformat("2023-01-02T00:00:00+00:00")),
        ]


def test_cte_alias(bq):
    assert query(
        bq,
        """
        WITH cte AS (
            SELECT
                1 AS a,
                2 AS b
        )
        SELECT
            alias.a,
            alias.b
        FROM
            cte AS alias
        """,
    ) == [{"a": 1, "b": 2}]
