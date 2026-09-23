import datetime

import pytest
from google.api_core.exceptions import BadRequest, Conflict, NotFound

from tests.cases import fails, rows, run, run_job, type_name, unique


def schema(bq, table):
    return [(f.name, type_name(f), f.mode) for f in bq.get_table(table).schema]


@pytest.fixture
def table(dataset):
    return f"{dataset.dataset_id}.{unique('t')}"


def test_create_table_types(bq, table):
    run(
        bq,
        f"""
        CREATE TABLE {table} (
            i INT64 NOT NULL, f FLOAT64, n NUMERIC, bn BIGNUMERIC, b BOOL, s STRING,
            bs BYTES, d DATE, dt DATETIME, t TIME, ts TIMESTAMP, j JSON,
            a ARRAY<INT64>, r STRUCT<x INT64, y ARRAY<STRING>>
        )
        """,
    )
    assert schema(bq, table) == [
        ("i", "INT64", "REQUIRED"),
        ("f", "FLOAT64", "NULLABLE"),
        ("n", "NUMERIC", "NULLABLE"),
        ("bn", "BIGNUMERIC", "NULLABLE"),
        ("b", "BOOL", "NULLABLE"),
        ("s", "STRING", "NULLABLE"),
        ("bs", "BYTES", "NULLABLE"),
        ("d", "DATE", "NULLABLE"),
        ("dt", "DATETIME", "NULLABLE"),
        ("t", "TIME", "NULLABLE"),
        ("ts", "TIMESTAMP", "NULLABLE"),
        ("j", "JSON", "NULLABLE"),
        ("a", "ARRAY<INT64>", "REPEATED"),
        ("r", "STRUCT<x INT64, y ARRAY<STRING>>", "NULLABLE"),
    ]


def test_create_table_statistics(bq, table):
    create = run_job(bq, f"CREATE TABLE {table} (x INT64)")
    assert create.statement_type == "CREATE_TABLE"
    assert create.ddl_operation_performed == "CREATE"
    assert create.ddl_target_table.table_id == table.split(".")[1]


def test_create_table_if_not_exists_skips(bq, table):
    run(bq, f"CREATE TABLE {table} (x INT64)")
    create = run_job(bq, f"CREATE TABLE IF NOT EXISTS {table} (y STRING)")
    assert create.ddl_operation_performed == "SKIP"
    assert schema(bq, table) == [("x", "INT64", "NULLABLE")]


def test_create_or_replace_table(bq, table):
    run(bq, f"CREATE TABLE {table} AS SELECT 1 AS x")
    replace = run_job(bq, f"CREATE OR REPLACE TABLE {table} AS SELECT 'a' AS y")
    assert replace.ddl_operation_performed == "REPLACE"
    assert rows(bq, f"SELECT * FROM {table}") == [("a",)]


def test_create_existing_table(bq, table):
    run(bq, f"CREATE TABLE {table} (x INT64)")
    with fails(Conflict, "duplicate"):
        run(bq, f"CREATE TABLE {table} (x INT64)")


@pytest.mark.xfail(reason="tables.get not implemented")
def test_create_table_options(bq, table):
    run(
        bq,
        f"""
        CREATE TABLE {table} (x INT64 OPTIONS (description = 'col'))
        OPTIONS (
            description = 'desc',
            friendly_name = 'Friendly',
            labels = [('env', 'dev')],
            expiration_timestamp = TIMESTAMP '2100-01-01 00:00:00 UTC'
        )
        """,
    )
    fetched = bq.get_table(table)
    assert fetched.description == "desc"
    assert fetched.friendly_name == "Friendly"
    assert fetched.labels == {"env": "dev"}
    assert fetched.expires == datetime.datetime(2100, 1, 1, tzinfo=datetime.UTC)
    assert fetched.schema[0].description == "col"


@pytest.mark.xfail(reason="tables.get not implemented")
def test_create_table_partitioned_and_clustered(bq, table):
    run(
        bq,
        f"""
        CREATE TABLE {table} (ts TIMESTAMP, k STRING)
        PARTITION BY DATE(ts) CLUSTER BY k
        OPTIONS (require_partition_filter = TRUE)
        """,
    )
    fetched = bq.get_table(table)
    assert fetched.time_partitioning.type_ == "DAY"
    assert fetched.time_partitioning.field == "ts"
    assert fetched.require_partition_filter is True
    assert fetched.clustering_fields == ["k"]


def test_create_table_as_select(bq, table):
    create = run_job(bq, f"CREATE TABLE {table} AS SELECT 1 AS x, 'a' AS y")
    assert create.statement_type == "CREATE_TABLE_AS_SELECT"
    assert rows(bq, f"SELECT * FROM {table}") == [(1, "a")]
    assert schema(bq, table) == [
        ("x", "INT64", "NULLABLE"),
        ("y", "STRING", "NULLABLE"),
    ]


@pytest.mark.xfail(reason="CTAS column list unsupported")
def test_create_table_as_select_with_column_list(bq, table):
    run(bq, f"CREATE TABLE {table} (a NUMERIC, b STRING) AS SELECT 1, 'x'")
    assert schema(bq, table) == [
        ("a", "NUMERIC", "NULLABLE"),
        ("b", "STRING", "NULLABLE"),
    ]


@pytest.mark.xfail(reason="CREATE TABLE COPY unsupported")
def test_create_table_like_and_copy(bq, dataset, table):
    run(bq, f"CREATE TABLE {table} AS SELECT 1 AS x")
    like = f"{dataset.dataset_id}.{unique('like')}"
    copy = f"{dataset.dataset_id}.{unique('copy')}"
    run(bq, f"CREATE TABLE {like} LIKE {table}")
    run(bq, f"CREATE TABLE {copy} COPY {table}")
    assert schema(bq, like) == [("x", "INT64", "NULLABLE")]
    assert rows(bq, f"SELECT COUNT(*) FROM {like}") == [(0,)]
    assert rows(bq, f"SELECT * FROM {copy}") == [(1,)]


def test_create_temp_table_in_script(bq):
    result = run(bq, "CREATE TEMP TABLE tmp AS SELECT 1 AS x; SELECT x + 1 FROM tmp;")
    assert [tuple(r.values()) for r in result] == [(2,)]


@pytest.mark.xfail(reason="statement type always SELECT")
def test_create_view(bq, dataset, table):
    run(bq, f"CREATE TABLE {table} AS SELECT 1 AS x UNION ALL SELECT 2")
    view = f"{dataset.dataset_id}.{unique('v')}"
    create = run_job(bq, f"CREATE VIEW {view} AS SELECT x * 10 AS y FROM {table}")
    assert create.statement_type == "CREATE_VIEW"
    assert rows(bq, f"SELECT y FROM {view} ORDER BY y") == [(10,), (20,)]
    fetched = bq.get_table(view)
    assert fetched.table_type == "VIEW"
    assert fetched.view_query == f"SELECT x * 10 AS y FROM {table}"


def test_create_or_replace_view(bq, dataset):
    view = f"{dataset.dataset_id}.{unique('v')}"
    run(bq, f"CREATE VIEW {view} AS SELECT 1 AS x")
    run(bq, f"CREATE OR REPLACE VIEW {view} AS SELECT 2 AS x")
    assert rows(bq, f"SELECT x FROM {view}") == [(2,)]


@pytest.mark.xfail(reason="multiple ALTER actions unsupported")
def test_alter_table_add_column(bq, table):
    run(bq, f"CREATE TABLE {table} AS SELECT 1 AS x")
    alter = run_job(bq, f"ALTER TABLE {table} ADD COLUMN y STRING, ADD COLUMN z INT64")
    assert alter.statement_type == "ALTER_TABLE"
    assert schema(bq, table)[1:] == [
        ("y", "STRING", "NULLABLE"),
        ("z", "INT64", "NULLABLE"),
    ]
    assert rows(bq, f"SELECT * FROM {table}") == [(1, None, None)]


def test_alter_table_add_column_if_not_exists(bq, table):
    run(bq, f"CREATE TABLE {table} (x INT64)")
    run(bq, f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS x STRING")
    assert schema(bq, table) == [("x", "INT64", "NULLABLE")]


def test_alter_table_drop_and_rename_column(bq, table):
    run(bq, f"CREATE TABLE {table} AS SELECT 1 AS x, 2 AS y")
    run(bq, f"ALTER TABLE {table} DROP COLUMN x")
    run(bq, f"ALTER TABLE {table} RENAME COLUMN y TO z")
    assert rows(bq, f"SELECT z FROM {table}") == [(2,)]


@pytest.mark.xfail(reason="ALTER TABLE SET OPTIONS mistranslated")
def test_alter_table_set_options(bq, table):
    run(bq, f"CREATE TABLE {table} (x INT64)")
    run(
        bq,
        f"ALTER TABLE {table} SET OPTIONS (description = 'new', labels = [('a', 'b')])",
    )
    fetched = bq.get_table(table)
    assert fetched.description == "new"
    assert fetched.labels == {"a": "b"}


@pytest.mark.xfail(reason="NUMERIC mapped to DECIMAL(18,3)")
def test_alter_column(bq, table):
    run(bq, f"CREATE TABLE {table} (x INT64 NOT NULL)")
    run(bq, f"ALTER TABLE {table} ALTER COLUMN x DROP NOT NULL")
    run(bq, f"ALTER TABLE {table} ALTER COLUMN x SET DATA TYPE NUMERIC")
    assert schema(bq, table) == [("x", "NUMERIC", "NULLABLE")]


def test_alter_column_rejects_narrowing(bq, table):
    run(bq, f"CREATE TABLE {table} (x NUMERIC)")
    with fails(BadRequest, "invalidQuery"):
        run(bq, f"ALTER TABLE {table} ALTER COLUMN x SET DATA TYPE INT64")


def test_alter_table_rename(bq, dataset, table):
    run(bq, f"CREATE TABLE {table} AS SELECT 1 AS x")
    renamed = unique("renamed")
    run(bq, f"ALTER TABLE {table} RENAME TO {renamed}")
    assert rows(bq, f"SELECT x FROM {dataset.dataset_id}.{renamed}") == [(1,)]
    with fails(NotFound, "notFound"):
        bq.get_table(table)


def test_alter_missing_table(bq, table):
    with fails(NotFound, "notFound"):
        run(bq, f"ALTER TABLE {table} ADD COLUMN y STRING")


def test_drop_table(bq, table):
    run(bq, f"CREATE TABLE {table} (x INT64)")
    drop = run_job(bq, f"DROP TABLE {table}")
    assert drop.statement_type == "DROP_TABLE"
    assert drop.ddl_operation_performed == "DROP"
    with fails(NotFound, "notFound"):
        bq.get_table(table)


@pytest.mark.xfail(reason="ddlOperationPerformed not reported")
def test_drop_table_if_exists_skips(bq, table):
    assert (
        run_job(bq, f"DROP TABLE IF EXISTS {table}").ddl_operation_performed == "SKIP"
    )


def test_drop_missing_table(bq, table):
    with fails(NotFound, "notFound"):
        run(bq, f"DROP TABLE {table}")


def test_drop_view(bq, dataset):
    view = f"{dataset.dataset_id}.{unique('v')}"
    run(bq, f"CREATE VIEW {view} AS SELECT 1 AS x")
    assert run_job(bq, f"DROP VIEW {view}").statement_type == "DROP_VIEW"
    run(bq, f"DROP VIEW IF EXISTS {view}")
    with fails(NotFound, "notFound"):
        bq.get_table(view)


@pytest.mark.xfail(reason="statement type always SELECT")
def test_schema_lifecycle(bq):
    schema_id = unique("schema")
    create = run_job(bq, f"CREATE SCHEMA {schema_id} OPTIONS (description = 'a')")
    assert create.statement_type == "CREATE_SCHEMA"
    run(bq, f"CREATE SCHEMA IF NOT EXISTS {schema_id}")
    run(bq, f"ALTER SCHEMA {schema_id} SET OPTIONS (description = 'b')")
    assert bq.get_dataset(schema_id).description == "b"
    assert run_job(bq, f"DROP SCHEMA {schema_id}").statement_type == "DROP_SCHEMA"
    with fails(NotFound, "notFound"):
        bq.get_dataset(schema_id)


@pytest.mark.xfail(reason="non-empty DROP SCHEMA not resourceInUse")
def test_drop_non_empty_schema_requires_cascade(bq):
    schema_id = unique("schema")
    run(bq, f"CREATE SCHEMA {schema_id}")
    run(bq, f"CREATE TABLE {schema_id}.t (x INT64)")
    with fails(BadRequest, "resourceInUse"):
        run(bq, f"DROP SCHEMA {schema_id}")
    run(bq, f"DROP SCHEMA {schema_id} CASCADE")
    with fails(NotFound, "notFound"):
        bq.get_dataset(schema_id)
