import datetime

import pytest
import sqlalchemy
from google.cloud.bigquery import dbapi
from sqlalchemy import column, select, text

from tests.cases import run, unique


@pytest.fixture(scope="module")
def table_id(bq, dataset):
    table_id = unique("people")
    run(
        bq,
        f"CREATE TABLE {dataset.dataset_id}.{table_id} (id INT64, name STRING, ts TIMESTAMP)",
    )
    run(
        bq,
        f"INSERT INTO {dataset.dataset_id}.{table_id} VALUES "
        "(1, 'a', TIMESTAMP '2023-01-01 00:00:00+00'), "
        "(2, 'b', TIMESTAMP '2023-01-02 00:00:00+00')",
    )
    return table_id


@pytest.fixture(scope="module")
def engine(bq, project, dataset):
    return sqlalchemy.create_engine(
        f"bigquery://{project}/{dataset.dataset_id}?user_supplied_client=True",
        connect_args={"client": bq},
    )


def test_sqlalchemy_select(engine, dataset, table_id):
    with engine.connect() as conn:
        rows = conn.execute(
            select(column("id"), column("name"))
            .select_from(text(f"{dataset.dataset_id}.{table_id}"))
            .order_by(column("id"))
        )
        assert rows.fetchall() == [(1, "a"), (2, "b")]


def test_sqlalchemy_table_alias(engine, dataset, table_id):
    with engine.connect() as conn:
        rows = conn.execute(
            select(column("t.id"))
            .select_from(text(f"{dataset.dataset_id}.{table_id} AS t"))
            .order_by(column("t.id"))
        )
        assert rows.fetchall() == [(1,), (2,)]


def test_sqlalchemy_timestamps(engine, dataset, table_id):
    with engine.connect() as conn:
        rows = conn.execute(
            select(column("ts"))
            .select_from(text(f"{dataset.dataset_id}.{table_id}"))
            .order_by(column("ts"))
        )
        assert rows.scalars().all() == [
            datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            datetime.datetime(2023, 1, 2, tzinfo=datetime.timezone.utc),
        ]


@pytest.mark.xfail(reason="tables.get not implemented")
def test_sqlalchemy_reflection(engine, table_id):
    inspector = sqlalchemy.inspect(engine)
    assert inspector.has_table(table_id)
    assert not inspector.has_table(unique("missing"))
    columns = inspector.get_columns(table_id)
    assert [(c["name"], str(c["type"])) for c in columns] == [
        ("id", "INTEGER"),
        ("name", "VARCHAR"),
        ("ts", "TIMESTAMP"),
    ]


def test_sqlalchemy_table_names(engine, table_id):
    assert table_id in sqlalchemy.inspect(engine).get_table_names()


def test_dbapi_params_and_fetch(bq):
    cursor = dbapi.connect(client=bq).cursor()
    cursor.execute(
        "SELECT x FROM UNNEST(GENERATE_ARRAY(1, %(n)s)) AS x ORDER BY x", {"n": 5}
    )
    assert [d.name for d in cursor.description] == ["x"]
    assert [tuple(r) for r in cursor.fetchmany(2)] == [(1,), (2,)]
    assert [tuple(r) for r in cursor.fetchall()] == [(3,), (4,), (5,)]


@pytest.mark.xfail(reason="DML statistics not reported")
def test_dbapi_rowcount(bq, dataset):
    table = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table} (x INT64)")
    cursor = dbapi.connect(client=bq).cursor()
    cursor.execute(f"INSERT INTO {table} VALUES (1), (2)")
    assert cursor.rowcount == 2


def test_to_dataframe(bq):
    frame = run(bq, "SELECT 1 AS a, 'x' AS b, 1.5 AS c").to_dataframe(
        create_bqstorage_client=False
    )
    assert frame.to_dict("records") == [{"a": 1, "b": "x", "c": 1.5}]
    assert str(frame.dtypes["a"]) == "Int64"
