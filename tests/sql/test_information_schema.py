import pytest

from tests.cases import FAST_RETRY, rows, run, unique

pytestmark = pytest.mark.usefixtures("seed")


@pytest.fixture(scope="module")
def seed(bq, dataset):
    ds = dataset.dataset_id
    run(
        bq,
        f"""
        CREATE TABLE {ds}.t (
            id INT64 NOT NULL, name STRING, rec STRUCT<a INT64, b ARRAY<STRING>>
        );
        CREATE VIEW {ds}.v AS SELECT id FROM {ds}.t;
        """,
    )


@pytest.mark.xfail(reason="INFORMATION_SCHEMA unsupported")
def test_schemata(bq, dataset):
    ds = dataset.dataset_id
    assert rows(
        bq,
        "SELECT schema_name, location FROM `region-us`.INFORMATION_SCHEMA.SCHEMATA "
        f"WHERE schema_name = '{ds}'",
    ) == [(ds, "US")]


@pytest.mark.xfail(reason="INFORMATION_SCHEMA unsupported")
def test_tables(bq, project, dataset):
    ds = dataset.dataset_id
    assert rows(
        bq,
        "SELECT table_catalog, table_schema, table_name, table_type "
        f"FROM {ds}.INFORMATION_SCHEMA.TABLES WHERE table_name IN ('t', 'v') "
        "ORDER BY table_name",
    ) == [(project, ds, "t", "BASE TABLE"), (project, ds, "v", "VIEW")]


@pytest.mark.xfail(reason="INFORMATION_SCHEMA unsupported")
def test_dropped_table_disappears(bq, dataset):
    ds = dataset.dataset_id
    table = unique("dropped")
    run(bq, f"CREATE TABLE {ds}.{table} (x INT64); DROP TABLE {ds}.{table};")
    assert rows(
        bq,
        f"SELECT COUNT(*) FROM {ds}.INFORMATION_SCHEMA.TABLES WHERE table_name = '{table}'",
    ) == [(0,)]


@pytest.mark.xfail(reason="INFORMATION_SCHEMA unsupported")
def test_columns(bq, dataset):
    assert rows(
        bq,
        "SELECT column_name, ordinal_position, is_nullable, data_type "
        f"FROM {dataset.dataset_id}.INFORMATION_SCHEMA.COLUMNS "
        "WHERE table_name = 't' ORDER BY ordinal_position",
    ) == [
        ("id", 1, "NO", "INT64"),
        ("name", 2, "YES", "STRING"),
        ("rec", 3, "YES", "STRUCT<a INT64, b ARRAY<STRING>>"),
    ]


@pytest.mark.xfail(reason="INFORMATION_SCHEMA unsupported")
def test_column_field_paths(bq, dataset):
    assert rows(
        bq,
        "SELECT field_path, data_type "
        f"FROM {dataset.dataset_id}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS "
        "WHERE table_name = 't' ORDER BY field_path",
    ) == [
        ("id", "INT64"),
        ("name", "STRING"),
        ("rec", "STRUCT<a INT64, b ARRAY<STRING>>"),
        ("rec.a", "INT64"),
        ("rec.b", "ARRAY<STRING>"),
    ]


@pytest.mark.xfail(reason="INFORMATION_SCHEMA unsupported")
def test_views(bq, dataset):
    ds = dataset.dataset_id
    assert rows(
        bq,
        "SELECT table_name, view_definition, use_standard_sql "
        f"FROM {ds}.INFORMATION_SCHEMA.VIEWS WHERE table_name = 'v'",
    ) == [("v", f"SELECT id FROM {ds}.t", "YES")]


@pytest.mark.xfail(reason="INFORMATION_SCHEMA unsupported")
def test_table_options(bq, dataset):
    ds = dataset.dataset_id
    table = unique("options")
    run(
        bq,
        f"CREATE TABLE {ds}.{table} (x INT64) "
        "OPTIONS (description = 'desc', labels = [('k', 'v')])",
    )
    assert rows(
        bq,
        "SELECT option_name, option_type, option_value "
        f"FROM {ds}.INFORMATION_SCHEMA.TABLE_OPTIONS "
        f"WHERE table_name = '{table}' ORDER BY option_name",
    ) == [
        ("description", "STRING", '"desc"'),
        ("labels", "ARRAY<STRUCT<STRING, STRING>>", '[STRUCT("k", "v")]'),
    ]


@pytest.mark.xfail(reason="INFORMATION_SCHEMA unsupported")
def test_partitions(bq, dataset):
    ds = dataset.dataset_id
    table = unique("partitioned")
    run(
        bq,
        f"""
        CREATE TABLE {ds}.{table} (d DATE) PARTITION BY d;
        INSERT {ds}.{table} VALUES ('2020-01-01'), ('2020-01-01'), ('2020-01-02');
        """,
    )
    assert rows(
        bq,
        "SELECT partition_id, total_rows "
        f"FROM {ds}.INFORMATION_SCHEMA.PARTITIONS "
        f"WHERE table_name = '{table}' ORDER BY partition_id",
    ) == [("20200101", 2), ("20200102", 1)]


@pytest.mark.xfail(reason="INFORMATION_SCHEMA unsupported")
def test_routines(bq, dataset):
    ds = dataset.dataset_id
    routine = unique("f")
    run(bq, f"CREATE FUNCTION {ds}.{routine}(x INT64) RETURNS INT64 AS (x + 1)")
    assert rows(
        bq,
        "SELECT routine_name, routine_type, routine_body, data_type "
        f"FROM {ds}.INFORMATION_SCHEMA.ROUTINES WHERE routine_name = '{routine}'",
    ) == [(routine, "FUNCTION", "SQL", "INT64")]


@pytest.mark.xfail(reason="INFORMATION_SCHEMA unsupported")
@pytest.mark.parametrize("view", ["JOBS", "JOBS_BY_PROJECT"])
def test_jobs(bq, view):
    job = bq.query("SELECT 1", job_id=unique("job"), retry=FAST_RETRY, job_retry=None)
    job.result()
    assert rows(
        bq,
        "SELECT job_id, job_type, statement_type, state "
        f"FROM `region-us`.INFORMATION_SCHEMA.{view} WHERE job_id = '{job.job_id}'",
    ) == [(job.job_id, "QUERY", "SELECT", "DONE")]


@pytest.mark.xfail(reason="__TABLES__ unsupported")
def test_legacy_tables_meta(bq, dataset):
    assert rows(
        bq,
        "SELECT table_id, row_count, type "
        f"FROM {dataset.dataset_id}.__TABLES__ "
        "WHERE table_id IN ('t', 'v') ORDER BY table_id",
    ) == [("t", 0, 1), ("v", 0, 2)]
