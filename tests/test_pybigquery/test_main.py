import pathlib
import threading
import time
import datetime

import pytest
import requests
import uvicorn
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery
from google.cloud.bigquery import QueryJobConfig
from sqlalchemy import column, create_engine, select, text
from testcontainers.postgres import PostgresContainer

from local_bigquery.main import app, db
from local_bigquery.settings import settings


@pytest.fixture(scope="session")
def server_url():
    settings.data_dir = pathlib.Path("/tmp/local-bigquery")
    db.reset()
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
        if time.time() - start_time > 1:
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
    bq.create_dataset("dataset1", exists_ok=True)
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
                    bigquery.SchemaField("item", "STRING"),
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
    bq.create_dataset("project1.dataset1", exists_ok=True)
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
    bq.create_dataset("project1.dataset1", exists_ok=True)
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
    bq.create_dataset("project1.dataset1", exists_ok=True)
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
            (1, datetime.datetime.fromisoformat("2023-01-01T00:00:00+00:00")),
            (2, datetime.datetime.fromisoformat("2023-01-02T00:00:00+00:00")),
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


def test_sql_udf(bq):
    assert query(
        bq,
        """
        CREATE TEMP FUNCTION AddFourAndDivide(x INT64, y INT64)
        RETURNS FLOAT64
        AS (
          (x + 4) / y
        );

        SELECT
          val, AddFourAndDivide(val, 2) AS result
        FROM
          UNNEST(@params) AS val;
        """,
        config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter(
                    "params",
                    "INT64",
                    [2, 3, 5, 8],
                ),
            ],
        ),
    ) == [
        {"val": 2, "result": 3.0},
        {"val": 3, "result": 3.5},
        {"val": 5, "result": 4.5},
        {"val": 8, "result": 6.0},
    ]


def test_bigquery_types(bq):
    query = """
    SELECT
        @string_param AS string_param,
        @int64_param AS int64_param,
        @float64_param AS float64_param,
        @numeric_param AS numeric_param,
        @bignumeric_param AS bignumeric_param,
        @boolean_param AS boolean_param,
        @bytes_param AS bytes_param,
        @date_param AS date_param,
        @datetime_param AS datetime_param,
        @time_param AS time_param,
        @timestamp_param AS timestamp_param,
        @array_string_param AS array_string_param,
        @array_int64_param AS array_int64_param,
        @array_float64_param AS array_float64_param,
        @array_numeric_param AS array_numeric_param,
        @array_bignumeric_param AS array_bignumeric_param,
        @array_boolean_param AS array_boolean_param,
        @array_bytes_param AS array_bytes_param,
        @array_date_param AS array_date_param,
        @array_datetime_param AS array_datetime_param,
        @array_time_param AS array_time_param,
        @array_timestamp_param AS array_timestamp_param,
        @struct_param.field1 AS struct_field1,
        @struct_param.field2 AS struct_field2,
        @array_struct_param AS array_struct_param
    FROM
        (SELECT 1)  -- Dummy table to allow SELECT without FROM a real table
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("string_param", "STRING", "example string"),
            bigquery.ScalarQueryParameter("int64_param", "INT64", 123),
            bigquery.ScalarQueryParameter("float64_param", "FLOAT64", 3.14),
            bigquery.ScalarQueryParameter("numeric_param", "NUMERIC", "123.45"),
            bigquery.ScalarQueryParameter(
                "bignumeric_param", "BIGNUMERIC", "12345678901234567890.123456789"
            ),
            bigquery.ScalarQueryParameter("boolean_param", "BOOL", True),
            bigquery.ScalarQueryParameter("bytes_param", "BYTES", b"example bytes"),
            bigquery.ScalarQueryParameter("date_param", "DATE", "2025-04-10"),
            bigquery.ScalarQueryParameter(
                "datetime_param", "DATETIME", "2025-04-10 11:00:00+00:00"
            ),
            bigquery.ScalarQueryParameter("time_param", "TIME", "11:00:00"),
            bigquery.ScalarQueryParameter(
                "timestamp_param", "TIMESTAMP", "2025-04-10 11:00:00+00:00"
            ),
            bigquery.ArrayQueryParameter(
                "array_string_param", "STRING", ["a", "b", "c"]
            ),
            bigquery.ArrayQueryParameter("array_int64_param", "INT64", [1, 2, 3]),
            bigquery.ArrayQueryParameter(
                "array_float64_param", "FLOAT64", [1.1, 2.2, 3.3]
            ),
            bigquery.ArrayQueryParameter(
                "array_numeric_param", "NUMERIC", ["1.1", "2.2", "3.3"]
            ),
            bigquery.ArrayQueryParameter(
                "array_bignumeric_param", "BIGNUMERIC", ["123.1", "456.2", "789.3"]
            ),
            bigquery.ArrayQueryParameter(
                "array_boolean_param", "BOOL", [True, False, True]
            ),
            bigquery.ArrayQueryParameter(
                "array_bytes_param", "BYTES", [b"byte1", b"byte2"]
            ),
            bigquery.ArrayQueryParameter(
                "array_date_param", "DATE", ["2025-04-01", "2025-04-05"]
            ),
            bigquery.ArrayQueryParameter(
                "array_datetime_param",
                "DATETIME",
                ["2025-04-10 10:00:00+00:00", "2025-04-10 12:00:00+00:00"],
            ),
            bigquery.ArrayQueryParameter(
                "array_time_param", "TIME", ["09:00:00", "13:00:00"]
            ),
            bigquery.ArrayQueryParameter(
                "array_timestamp_param",
                "TIMESTAMP",
                ["2025-04-10 10:00:00+00:00", "2025-04-10 12:00:00+00:00"],
            ),
            bigquery.StructQueryParameter(
                "struct_param",
                bigquery.ScalarQueryParameter("field1", "STRING", "struct value 1"),
                bigquery.ScalarQueryParameter("field2", "INT64", 42),
            ),
            bigquery.ArrayQueryParameter(
                "array_struct_param",
                "RECORD",
                [
                    bigquery.StructQueryParameter(
                        "array_struct_param",
                        bigquery.ScalarQueryParameter(
                            "field1", "STRING", "array struct value 1a"
                        ),
                        bigquery.ScalarQueryParameter("field2", "INT64", 100),
                    ),
                ],
            ),
        ]
    )
    results = bq.query_and_wait(query, job_config=job_config)
    assert dict(list(results)[0]) == {
        "array_bignumeric_param": [123.1, 456.2, 789.3],
        "array_boolean_param": [True, False, True],
        "array_bytes_param": [b"byte1", b"byte2"],
        "array_date_param": [datetime.date(2025, 4, 1), datetime.date(2025, 4, 5)],
        "array_datetime_param": [
            datetime.datetime(2025, 4, 10, 10, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2025, 4, 10, 12, 0, tzinfo=datetime.timezone.utc),
        ],
        "array_float64_param": [1.1, 2.2, 3.3],
        "array_int64_param": [1, 2, 3],
        "array_numeric_param": [1.1, 2.2, 3.3],
        "array_string_param": ["a", "b", "c"],
        "array_struct_param": [{"field1": "array struct value 1a", "field2": 100}],
        "array_time_param": [datetime.time(9, 0), datetime.time(13, 0)],
        "array_timestamp_param": [
            datetime.datetime(2025, 4, 10, 10, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2025, 4, 10, 12, 0, tzinfo=datetime.timezone.utc),
        ],
        "bignumeric_param": 1.2345678901234567e19,
        "boolean_param": True,
        "bytes_param": b"example bytes",
        "date_param": datetime.date(2025, 4, 10),
        "datetime_param": datetime.datetime(
            2025, 4, 10, 11, 0, tzinfo=datetime.timezone.utc
        ),
        "float64_param": 3.14,
        "int64_param": 123,
        "numeric_param": 123.45,
        "string_param": "example string",
        "struct_field1": "struct value 1",
        "struct_field2": 42,
        "time_param": datetime.time(11, 0),
        "timestamp_param": datetime.datetime(
            2025, 4, 10, 11, 0, tzinfo=datetime.timezone.utc
        ),
    }


def test_wildcard_tables(bq):
    assert query(
        bq,
        """
        create table project1.dataset1.wildcard_table1 as select 1 as id;
        create table project1.dataset1.wildcard_table2 as select 2 as id;
        create table project1.dataset1.wildcard_table3 as select 3 as id;
        select * from project1.dataset1.wildcard_table* order by id;
        """,
    ) == [
        {"_TABLE_SUFFIX": "1", "id": 1},
        {"_TABLE_SUFFIX": "2", "id": 2},
        {"_TABLE_SUFFIX": "3", "id": 3},
    ]


def test_javascript_udf(bq):
    assert query(
        bq,
        '''
        CREATE TEMP FUNCTION multiplyInputs(x FLOAT64, y FLOAT64)
        RETURNS FLOAT64
        LANGUAGE js
        AS r"""
          return x*y;
        """;

        WITH numbers AS
          (SELECT 1 AS x, 5 as y
          UNION ALL
          SELECT 2 AS x, 10 as y
          UNION ALL
          SELECT 3 as x, 15 as y)
        SELECT x, y, multiplyInputs(x, y) AS product
        FROM numbers;
        ''',
    ) == [
        {"product": 5.0, "x": 1, "y": 5},
        {"product": 20.0, "x": 2, "y": 10},
        {"product": 45.0, "x": 3, "y": 15},
    ]


@pytest.fixture
def postgres_url():
    postgres = PostgresContainer("postgres:17")
    postgres.start()
    connection_uri = postgres.get_connection_url()
    engine = create_engine(connection_uri)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE person (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100),
                    description TEXT
                );
                INSERT INTO person (name, description) VALUES
                ('Alice', 'Enjoys hiking and outdoor activities.'),
                ('Bob', 'Avid reader and coffee enthusiast.');
                """
            )
        )
    settings.postgres_uri = connection_uri.replace("+psycopg2", "")
    yield connection_uri
    postgres.stop()


def test_external_query(postgres_url, bq):
    assert query(
        bq,
        """
        SELECT
            person.name AS person_name,
            person.description AS person_description
        FROM
            EXTERNAL_QUERY(
                'us.default',
                '''
                SELECT
                    name,
                    description
                FROM
                    person
                '''
            ) AS person
        ORDER BY
            person.name
        """,
    ) == [
        {
            "person_name": "Alice",
            "person_description": "Enjoys hiking and outdoor activities.",
        },
        {
            "person_name": "Bob",
            "person_description": "Avid reader and coffee enthusiast.",
        },
    ]


def test_external_query_cte(postgres_url, bq):
    assert query(
        bq,
        """
        SELECT
            person.name AS person_name,
            person.description AS person_description
        FROM
            EXTERNAL_QUERY(
                'us.default',
                '''
                WITH cte AS (
                    SELECT
                        name,
                        description
                    FROM
                        person
                )
                SELECT * FROM cte
                '''
            ) AS person
        ORDER BY
            person.name
        """,
    ) == [
        {
            "person_name": "Alice",
            "person_description": "Enjoys hiking and outdoor activities.",
        },
        {
            "person_name": "Bob",
            "person_description": "Avid reader and coffee enthusiast.",
        },
    ]
