import pytest
from google.cloud import bigquery

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


def test_schemata(bq, dataset):
    ds = dataset.dataset_id
    assert rows(
        bq,
        "SELECT schema_name, location FROM `region-us`.INFORMATION_SCHEMA.SCHEMATA "
        f"WHERE schema_name = '{ds}'",
    ) == [(ds, "US")]


def test_tables(bq, project, dataset):
    ds = dataset.dataset_id
    assert rows(
        bq,
        "SELECT table_catalog, table_schema, table_name, table_type "
        f"FROM {ds}.INFORMATION_SCHEMA.TABLES WHERE table_name IN ('t', 'v') "
        "ORDER BY table_name",
    ) == [(project, ds, "t", "BASE TABLE"), (project, ds, "v", "VIEW")]


def test_dropped_table_disappears(bq, dataset):
    ds = dataset.dataset_id
    table = unique("dropped")
    run(bq, f"CREATE TABLE {ds}.{table} (x INT64); DROP TABLE {ds}.{table};")
    assert rows(
        bq,
        f"SELECT COUNT(*) FROM {ds}.INFORMATION_SCHEMA.TABLES WHERE table_name = '{table}'",
    ) == [(0,)]


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


def test_tables_insertable_and_typed(bq, dataset):
    assert rows(
        bq,
        "SELECT table_name, is_insertable_into, is_typed "
        f"FROM {dataset.dataset_id}.INFORMATION_SCHEMA.TABLES "
        "WHERE table_name IN ('t', 'v') ORDER BY table_name",
    ) == [("t", "YES", "NO"), ("v", "NO", "NO")]


def test_columns_partitioning_and_clustering(bq, dataset):
    ds, table = dataset.dataset_id, unique("layout")
    run(
        bq,
        f"CREATE TABLE {ds}.{table} (dt DATE, k STRING, v INT64) "
        "PARTITION BY dt CLUSTER BY k",
    )
    assert rows(
        bq,
        "SELECT column_name, is_partitioning_column, clustering_ordinal_position, "
        f"is_hidden, is_generated FROM {ds}.INFORMATION_SCHEMA.COLUMNS "
        f"WHERE table_name = '{table}' ORDER BY ordinal_position",
    ) == [
        ("dt", "YES", None, "NO", "NEVER"),
        ("k", "NO", 1, "NO", "NEVER"),
        ("v", "NO", None, "NO", "NEVER"),
    ]


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


def test_views(bq, dataset):
    ds = dataset.dataset_id
    assert rows(
        bq,
        "SELECT table_name, view_definition, use_standard_sql "
        f"FROM {ds}.INFORMATION_SCHEMA.VIEWS WHERE table_name = 'v'",
    ) == [("v", f"SELECT id FROM {ds}.t", "YES")]


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


def test_more_table_options(bq, dataset):
    ds, table = dataset.dataset_id, unique("options")
    run(
        bq,
        f"CREATE TABLE {ds}.{table} (d DATE) PARTITION BY d OPTIONS ("
        "friendly_name = 'nice', expiration_timestamp = TIMESTAMP '2099-01-01 00:00:00+00', "
        "require_partition_filter = true)",
    )
    assert rows(
        bq,
        "SELECT option_name, option_type, option_value "
        f"FROM {ds}.INFORMATION_SCHEMA.TABLE_OPTIONS "
        f"WHERE table_name = '{table}' ORDER BY option_name",
    ) == [
        ("expiration_timestamp", "TIMESTAMP", 'TIMESTAMP "2099-01-01T00:00:00+00:00"'),
        ("friendly_name", "STRING", '"nice"'),
        ("require_partition_filter", "BOOL", "true"),
    ]


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


def test_routines(bq, dataset):
    ds = dataset.dataset_id
    routine = unique("f")
    run(bq, f"CREATE FUNCTION {ds}.{routine}(x INT64) RETURNS INT64 AS (x + 1)")
    assert rows(
        bq,
        "SELECT routine_name, routine_type, routine_body, data_type "
        f"FROM {ds}.INFORMATION_SCHEMA.ROUTINES WHERE routine_name = '{routine}'",
    ) == [(routine, "FUNCTION", "SQL", "INT64")]


@pytest.mark.parametrize("view", ["JOBS", "JOBS_BY_PROJECT"])
def test_jobs(bq, view):
    job = bq.query("SELECT 1", job_id=unique("job"), retry=FAST_RETRY, job_retry=None)
    job.result()
    assert rows(
        bq,
        "SELECT job_id, job_type, statement_type, state "
        f"FROM `region-us`.INFORMATION_SCHEMA.{view} WHERE job_id = '{job.job_id}'",
    ) == [(job.job_id, "QUERY", "SELECT", "DONE")]


def test_legacy_tables_meta(bq, dataset):
    assert rows(
        bq,
        "SELECT table_id, row_count, type "
        f"FROM {dataset.dataset_id}.__TABLES__ "
        "WHERE table_id IN ('t', 'v') ORDER BY table_id",
    ) == [("t", 0, 1), ("v", 0, 2)]


@pytest.mark.parametrize(
    "view, where",
    [
        ("INFORMATION_SCHEMA.TABLES", "table_name = 'x' AND creation_time IS NOT NULL"),
        ("INFORMATION_SCHEMA.COLUMNS", "table_name = 'x' AND ordinal_position > 0"),
        ("INFORMATION_SCHEMA.PARTITIONS", "table_name = 'x' AND total_rows > 0"),
        ("INFORMATION_SCHEMA.ROUTINES", "routine_name = 'x'"),
        ("INFORMATION_SCHEMA.TABLE_OPTIONS", "option_name = 'x'"),
        ("INFORMATION_SCHEMA.TABLE_CONSTRAINTS", "table_name = 'x'"),
        ("INFORMATION_SCHEMA.KEY_COLUMN_USAGE", "ordinal_position > 0"),
        ("INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE", "column_name = 'x'"),
        ("INFORMATION_SCHEMA.MATERIALIZED_VIEWS", "last_refresh_time IS NULL"),
        ("INFORMATION_SCHEMA.PARAMETERS", "ordinal_position > 0"),
        ("INFORMATION_SCHEMA.ROUTINE_OPTIONS", "option_name = 'x'"),
        ("INFORMATION_SCHEMA.TABLE_SNAPSHOTS", "snapshot_time IS NULL"),
        ("INFORMATION_SCHEMA.SEARCH_INDEXES", "creation_time IS NULL"),
        ("INFORMATION_SCHEMA.VECTOR_INDEXES", "creation_time IS NULL"),
        ("__TABLES__", "table_id = 'x' AND row_count > 0"),
    ],
)
def test_empty_views_keep_column_types(bq, view, where):
    dataset_id = unique("empty")
    bq.create_dataset(dataset_id)
    assert rows(bq, f"SELECT * FROM {dataset_id}.{view} WHERE {where}") == []


def test_table_constraints(bq, dataset):
    ds, parent, child = dataset.dataset_id, unique("parent"), unique("child")
    run(
        bq,
        f"""
        CREATE TABLE {ds}.{parent} (id INT64, PRIMARY KEY (id) NOT ENFORCED);
        CREATE TABLE {ds}.{child} (
            a INT64, b INT64, PRIMARY KEY (a, b) NOT ENFORCED,
            CONSTRAINT fk FOREIGN KEY (b) REFERENCES {ds}.{parent}(id) NOT ENFORCED
        );
        """,
    )
    where = f"WHERE table_name IN ('{parent}', '{child}')"
    assert sorted(
        rows(
            bq,
            "SELECT constraint_schema, constraint_name, table_name, constraint_type, "
            f"is_deferrable, enforced FROM {ds}.INFORMATION_SCHEMA.TABLE_CONSTRAINTS "
            + where,
        )
    ) == sorted(
        [
            (ds, f"{child}.pk$", child, "PRIMARY KEY", "NO", "NO"),
            (ds, f"{child}.fk", child, "FOREIGN KEY", "NO", "NO"),
            (ds, f"{parent}.pk$", parent, "PRIMARY KEY", "NO", "NO"),
        ]
    )
    assert sorted(
        rows(
            bq,
            "SELECT constraint_name, table_name, column_name, ordinal_position, "
            "position_in_unique_constraint "
            f"FROM {ds}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE " + where,
        )
    ) == sorted(
        [
            (f"{child}.pk$", child, "a", 1, None),
            (f"{child}.pk$", child, "b", 2, None),
            (f"{child}.fk", child, "b", 1, 1),
            (f"{parent}.pk$", parent, "id", 1, None),
        ]
    )
    assert sorted(
        rows(
            bq,
            "SELECT table_name, column_name, constraint_name "
            f"FROM {ds}.INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE " + where,
        )
    ) == sorted(
        [
            (child, "a", f"{child}.pk$"),
            (child, "b", f"{child}.pk$"),
            (parent, "id", f"{child}.fk"),
            (parent, "id", f"{parent}.pk$"),
        ]
    )


def test_materialized_views(bq, dataset):
    ds, view = dataset.dataset_id, unique("mv")
    run(bq, f"CREATE MATERIALIZED VIEW {ds}.{view} AS SELECT COUNT(*) AS n FROM {ds}.t")
    sql = (
        "SELECT table_name, last_refresh_time IS NOT NULL "
        f"FROM {ds}.INFORMATION_SCHEMA.MATERIALIZED_VIEWS"
    )
    assert rows(bq, sql) == [(view, False)]
    run(bq, f"CALL BQ.REFRESH_MATERIALIZED_VIEW('{ds}.{view}')")
    assert rows(bq, sql) == [(view, True)]


def test_table_snapshots(bq, dataset):
    ds, snapshot = dataset.dataset_id, unique("snap")
    run(bq, f"CREATE SNAPSHOT TABLE {ds}.{snapshot} CLONE {ds}.t")
    assert rows(
        bq,
        "SELECT table_name, base_table_schema, base_table_name, "
        f"snapshot_time IS NOT NULL FROM {ds}.INFORMATION_SCHEMA.TABLE_SNAPSHOTS",
    ) == [(snapshot, ds, "t", True)]


@pytest.mark.emulator("region-level TABLE_STORAGE needs extra IAM in BigQuery")
def test_table_storage(bq, dataset):
    ds, table = dataset.dataset_id, unique("stored")
    run(bq, f"CREATE TABLE {ds}.{table} AS SELECT 1 AS x UNION ALL SELECT 2")
    assert rows(
        bq,
        "SELECT table_schema, table_type, total_rows, total_logical_bytes > 0, "
        "deleted FROM `region-us`.INFORMATION_SCHEMA.TABLE_STORAGE "
        f"WHERE table_name = '{table}'",
    ) == [(ds, "BASE TABLE", 2, True, False)]


def test_schemata_options(bq, dataset):
    ds = unique("described")
    created = bigquery.Dataset(f"{bq.project}.{ds}")
    created.description = "about"
    created.labels = {"k": "v"}
    created.default_table_expiration_ms = 86_400_000
    bq.create_dataset(created)
    assert rows(
        bq,
        "SELECT option_name, option_type, option_value "
        "FROM `region-us`.INFORMATION_SCHEMA.SCHEMATA_OPTIONS "
        f"WHERE schema_name = '{ds}' ORDER BY option_name",
    ) == [
        ("default_table_expiration_days", "FLOAT64", "1.0"),
        ("description", "STRING", '"about"'),
        ("labels", "ARRAY<STRUCT<STRING, STRING>>", '[STRUCT("k", "v")]'),
        ("location", "STRING", '"us"'),
    ]
    bq.delete_dataset(ds)


def test_routine_parameters_and_options(bq, dataset):
    ds, routine = dataset.dataset_id, unique("f")
    run(
        bq,
        f"CREATE FUNCTION {ds}.{routine}(x INT64, y STRING) RETURNS INT64 "
        "OPTIONS (description = 'adds') AS (x)",
    )
    assert rows(
        bq,
        "SELECT ordinal_position, is_result, parameter_name, data_type "
        f"FROM {ds}.INFORMATION_SCHEMA.PARAMETERS WHERE specific_name = '{routine}' "
        "ORDER BY ordinal_position",
    ) == [(0, "YES", None, "INT64"), (1, "NO", "x", "INT64"), (2, "NO", "y", "STRING")]
    assert rows(
        bq,
        "SELECT specific_name, option_name, option_type, option_value "
        f"FROM {ds}.INFORMATION_SCHEMA.ROUTINE_OPTIONS "
        f"WHERE specific_name = '{routine}'",
    ) == [(routine, "description", "STRING", '"adds"')]
