import re
import datetime
import time

import pytest
from google.api_core.exceptions import BadRequest, Conflict, NotFound
from google.cloud import bigquery

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


def test_create_table_as_select_with_column_list(bq, table):
    run(bq, f"CREATE TABLE {table} (a NUMERIC, b STRING) AS SELECT 1, 'x'")
    assert schema(bq, table) == [
        ("a", "NUMERIC", "NULLABLE"),
        ("b", "STRING", "NULLABLE"),
    ]


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


def test_alter_table_set_options(bq, table):
    run(bq, f"CREATE TABLE {table} (x INT64)")
    run(
        bq,
        f"ALTER TABLE {table} SET OPTIONS (description = 'new', labels = [('a', 'b')])",
    )
    fetched = bq.get_table(table)
    assert fetched.description == "new"
    assert fetched.labels == {"a": "b"}


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


def test_drop_non_empty_schema_requires_cascade(bq):
    schema_id = unique("schema")
    run(bq, f"CREATE SCHEMA {schema_id}")
    run(bq, f"CREATE TABLE {schema_id}.t (x INT64)")
    with fails(BadRequest, "resourceInUse"):
        run(bq, f"DROP SCHEMA {schema_id}")
    run(bq, f"DROP SCHEMA {schema_id} CASCADE")
    with fails(NotFound, "notFound"):
        bq.get_dataset(schema_id)


def test_schema_ddl_with_quoted_project_path(bq, project):
    path = f"{project}.{unique('schema')}"
    create = run_job(bq, f"CREATE SCHEMA `{path}`")
    assert create.ddl_operation_performed == "CREATE"
    run_job(bq, f"CREATE TABLE `{path}.t` (x INT64)")
    with fails(BadRequest, "resourceInUse"):
        run(bq, f"DROP SCHEMA `{path}`")
    drop = run_job(bq, f"DROP SCHEMA `{path}` CASCADE")
    assert drop.ddl_operation_performed == "DROP"
    with fails(NotFound, "notFound"):
        bq.get_dataset(path)


@pytest.mark.parametrize(
    "sql, fields",
    [
        (
            "CREATE TABLE {t} (id INT64 NOT NULL, name STRING)",
            [("id", "INT64", "REQUIRED"), ("name", "STRING", "NULLABLE")],
        ),
        (
            "CREATE TABLE {t} (tags ARRAY<STRING>, info STRUCT<a INT64, b STRING>)",
            [
                ("tags", "ARRAY<STRING>", "REPEATED"),
                ("info", "STRUCT<a INT64, b STRING>", "NULLABLE"),
            ],
        ),
        (
            "CREATE OR REPLACE TABLE {t} AS SELECT 1 AS id, 'x' AS name",
            [("id", "INT64", "NULLABLE"), ("name", "STRING", "NULLABLE")],
        ),
        (
            "CREATE VIEW {t} AS SELECT 1 AS id, 'x' AS name",
            [("id", "INT64", "NULLABLE"), ("name", "STRING", "NULLABLE")],
        ),
    ],
)
def test_ddl_result_schema(bq, table, sql, fields):
    result = run(bq, sql.format(t=table))
    assert [(f.name, type_name(f), f.mode) for f in result.schema] == fields
    assert list(result) == []


def test_skipped_create_reports_declared_schema(bq, table):
    run(bq, f"CREATE TABLE {table} (x INT64)")
    result = run(bq, f"CREATE TABLE IF NOT EXISTS {table} (x INT64, y STRING)")
    assert [f.name for f in result.schema] == ["x", "y"]


def test_schema_ddl_result_has_no_schema(bq):
    schema_id = unique("schema")
    assert run(bq, f"CREATE SCHEMA {schema_id}").schema == []
    assert run(bq, f"DROP SCHEMA {schema_id}").schema == []


def test_dry_runs_report_target_schema(bq, table):
    dry = bigquery.QueryJobConfig(dry_run=True)
    job = bq.query(f"CREATE TABLE {table} (id INT64, label STRING)", job_config=dry)
    assert [f.name for f in job.schema] == ["id", "label"]
    with fails(NotFound, "notFound"):
        bq.get_table(table)
    run(bq, f"CREATE TABLE {table} (id INT64, label STRING)")
    job = bq.query(f"INSERT INTO {table} VALUES (1, 'x')", job_config=dry)
    assert [f.name for f in job.schema] == ["id", "label"]
    assert rows(bq, f"SELECT * FROM {table}") == []


@pytest.mark.parametrize(
    "option, message",
    [
        (
            {"clustering_fields": ["nope"]},
            "The field specified for clustering cannot be found in the schema",
        ),
        (
            {"time_partitioning": bigquery.TimePartitioning(field="nope")},
            "The field specified for partitioning cannot be found in the schema",
        ),
    ],
)
def test_destination_layout_must_name_result_columns(bq, dataset, option, message):
    destination = f"{bq.project}.{dataset.dataset_id}.{unique('dest')}"
    with fails(BadRequest, "invalid") as info:
        run_job(bq, "SELECT 1 AS id", destination=destination, **option)
    assert message in info.value.message


def test_destination_layout_is_recorded(bq, dataset):
    destination = f"{bq.project}.{dataset.dataset_id}.{unique('dest')}"
    run_job(
        bq,
        "SELECT DATE '2020-01-01' AS d, 'x' AS k",
        destination=destination,
        time_partitioning=bigquery.TimePartitioning(field="d"),
        clustering_fields=["k"],
    )
    table = bq.get_table(destination)
    assert (table.time_partitioning.field, table.clustering_fields) == ("d", ["k"])


@pytest.mark.parametrize(
    "select",
    [
        "SELECT 1 AS a, 2 AS a",
        pytest.param(
            "SELECT * FROM (SELECT 1 AS a), (SELECT 2 AS a)",
            marks=pytest.mark.xfail(reason="DuckDB suffixes star-expanded duplicates"),
        ),
    ],
)
def test_create_table_as_select_rejects_duplicate_columns(bq, table, select):
    with fails(BadRequest, "invalidQuery") as info:
        run(bq, f"CREATE TABLE {table} AS {select}")
    assert "CREATE TABLE has columns with duplicate name a" in info.value.message


def constraints(bq, table) -> tuple:
    found = bq.get_table(table).table_constraints
    if found is None:
        return None, []
    keys = [
        (
            key.name,
            key.referenced_table.table_id,
            [
                (c.referencing_column, c.referenced_column)
                for c in key.column_references
            ],
        )
        for key in found.foreign_keys or []
    ]
    return found.primary_key and found.primary_key.columns, keys


def test_create_table_with_unenforced_keys(bq, dataset, table):
    parent = unique("parent")
    run(
        bq,
        f"CREATE TABLE {dataset.dataset_id}.{parent} (id INT64 PRIMARY KEY NOT ENFORCED)",
    )
    run(
        bq,
        f"""
        CREATE TABLE {table} (
            a INT64, b INT64,
            c INT64 REFERENCES {dataset.dataset_id}.{parent}(id) NOT ENFORCED,
            PRIMARY KEY (a, b) NOT ENFORCED,
            CONSTRAINT fk FOREIGN KEY (b) REFERENCES {dataset.dataset_id}.{parent}(id)
                NOT ENFORCED
        )
        """,
    )
    run(bq, f"INSERT {table} VALUES (1, 1, 7), (1, 1, 8)")
    assert constraints(bq, f"{dataset.dataset_id}.{parent}") == (["id"], [])
    assert constraints(bq, table) == (
        ["a", "b"],
        [
            (f"{table.split('.')[1]}.fk$1", parent, [("c", "id")]),
            ("fk", parent, [("b", "id")]),
        ],
    )


@pytest.mark.parametrize(
    "columns, message",
    [
        ("id INT64 PRIMARY KEY", "Enforcement of primary keys is not supported"),
        ("id INT64, PRIMARY KEY (id)", "Enforcement of primary keys is not supported"),
        (
            "id INT64 REFERENCES other(id) NOT ENFORCED",
            'Table "other" must be qualified with a dataset (e.g. dataset.table).',
        ),
    ],
)
def test_invalid_keys(bq, table, columns, message):
    with pytest.raises(BadRequest) as info:
        run(bq, f"CREATE TABLE {table} ({columns})")
    assert message in info.value.message


def test_alter_table_keys(bq, dataset, table):
    parent = unique("parent")
    run(bq, f"CREATE TABLE {dataset.dataset_id}.{parent} (id INT64)")
    run(bq, f"CREATE TABLE {table} (a INT64, b INT64)")
    run(bq, f"ALTER TABLE {table} ADD PRIMARY KEY (a) NOT ENFORCED")
    run(
        bq,
        f"ALTER TABLE {table} "
        "ADD CONSTRAINT fk FOREIGN KEY (b) "
        f"REFERENCES {dataset.dataset_id}.{parent}(id) NOT ENFORCED",
    )
    assert constraints(bq, table) == (["a"], [("fk", parent, [("b", "id")])])
    run(bq, f"ALTER TABLE {table} DROP PRIMARY KEY")
    assert constraints(bq, table) == (None, [("fk", parent, [("b", "id")])])
    run(bq, f"ALTER TABLE {table} DROP CONSTRAINT fk")
    run(bq, f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS fk")
    assert constraints(bq, table) == (None, [])
    with fails(BadRequest, "invalidQuery"):
        run(bq, f"ALTER TABLE {table} DROP PRIMARY KEY")


def test_table_constraints_via_api(bq, dataset):
    table = bigquery.Table(
        f"{bq.project}.{dataset.dataset_id}.{unique('api')}",
        schema=[bigquery.SchemaField("id", "INT64")],
    )
    table.table_constraints = bigquery.table.TableConstraints(
        primary_key=bigquery.table.PrimaryKey(columns=["id"]), foreign_keys=None
    )
    created = bq.create_table(table)
    assert created.table_constraints.primary_key.columns == ["id"]


def test_alter_column_set_options(bq, table):
    run(bq, f"CREATE TABLE {table} (x INT64, y STRUCT<z INT64>)")
    run(bq, f"ALTER TABLE {table} ALTER COLUMN x SET OPTIONS (description = 'ex')")
    run(bq, f"ALTER TABLE {table} ALTER COLUMN y SET OPTIONS (description = 'why')")
    run(bq, f"ALTER TABLE {table} ALTER COLUMN x SET OPTIONS (description = 'new')")
    fetched = bq.get_table(table)
    assert [f.description for f in fetched.schema] == ["new", "why"]
    assert fetched.schema[1].fields[0].name == "z"


def test_parameterized_types(bq, table):
    run(
        bq,
        f"CREATE TABLE {table} "
        "(s STRING(10), b BYTES(4), n NUMERIC(10, 2), bn BIGNUMERIC(40, 10))",
    )
    fields = [
        (f.name, type_name(f), f.max_length, f.precision, f.scale)
        for f in bq.get_table(table).schema
    ]
    assert fields == [
        ("s", "STRING", 10, None, None),
        ("b", "BYTES", 4, None, None),
        ("n", "NUMERIC", None, 10, 2),
        ("bn", "BIGNUMERIC", None, 40, 10),
    ]
    run(bq, f"INSERT {table} (s, n) VALUES ('short', 1.235)")
    assert rows(bq, f"SELECT s, CAST(n AS STRING) FROM {table}") == [("short", "1.24")]
    with fails(BadRequest, "invalidQuery"):
        run(bq, f"INSERT {table} (n) VALUES (123456789)")


@pytest.mark.parametrize(
    "column, message",
    [
        ("BIGNUMERIC(50, 10)", r"In BIGNUMERIC\(P, 10\), P must be between 10 and 48"),
        ("NUMERIC(5, 6)", r"In NUMERIC\(P, 6\), P must be between 6 and 35"),
    ],
)
def test_numeric_parameters_are_validated(bq, table, column, message):
    with fails(BadRequest, "invalidQuery") as info:
        run(bq, f"CREATE TABLE {table} (n {column})")
    assert re.search(message, info.value.message)


@pytest.mark.xfail(strict=True, reason="STRING/BYTES lengths are not enforced on write")
def test_parameterized_string_length_is_enforced(bq, table):
    run(bq, f"CREATE TABLE {table} (s STRING(3))")
    with fails(BadRequest, "invalidQuery"):
        run(bq, f"INSERT {table} VALUES ('too long')")


def test_create_or_replace_clone(bq, dataset, table):
    run(bq, f"CREATE TABLE {table} AS SELECT 1 AS x")
    clone = f"{dataset.dataset_id}.{unique('clone')}"
    run(bq, f"CREATE TABLE {clone} AS SELECT 2 AS x")
    replace = run_job(bq, f"CREATE OR REPLACE TABLE {clone} CLONE {table}")
    assert replace.ddl_operation_performed == "REPLACE"
    assert rows(bq, f"SELECT x FROM {clone}") == [(1,)]
    with fails(Conflict, "duplicate") as info:
        run(bq, f"CREATE TABLE {clone} CLONE {table}")
    assert f"{bq.project}:{clone}" in info.value.message


def test_search_and_vector_indexes(bq, dataset, table):
    ds, name = dataset.dataset_id, table.split(".")[1]
    run(bq, f"CREATE TABLE {table} (s STRING, e ARRAY<FLOAT64>)")
    run(bq, f"INSERT {table} (s, e) VALUES ('a', [1.0, 2.0])")
    run(bq, f"CREATE SEARCH INDEX si ON {table}(ALL COLUMNS)")
    run(bq, f"CREATE SEARCH INDEX IF NOT EXISTS si ON {table}(s)")
    run(
        bq,
        f"CREATE VECTOR INDEX vi ON {table}(e) "
        "OPTIONS (index_type = 'IVF', distance_type = 'COSINE')",
    )
    assert rows(
        bq,
        f"SELECT index_name, table_name, index_status "
        f"FROM {ds}.INFORMATION_SCHEMA.SEARCH_INDEXES WHERE table_name = '{name}'",
    ) == [("si", name, "ACTIVE")]
    assert rows(
        bq,
        f"SELECT index_name, table_name, index_status "
        f"FROM {ds}.INFORMATION_SCHEMA.VECTOR_INDEXES WHERE table_name = '{name}'",
    ) == [("vi", name, "ACTIVE")]
    run(bq, f"DROP SEARCH INDEX si ON {table}")
    run(bq, f"DROP VECTOR INDEX vi ON {table}")
    run(bq, f"DROP SEARCH INDEX IF EXISTS si ON {table}")
    assert rows(
        bq,
        f"SELECT COUNT(*) FROM {ds}.INFORMATION_SCHEMA.SEARCH_INDEXES "
        f"WHERE table_name = '{name}'",
    ) == [(0,)]


@pytest.mark.emulator("depends on sub-second expiry timing")
def test_expired_table_behaves_as_deleted(bq, table):
    run(bq, f"CREATE TABLE {table} AS SELECT 1 AS x")
    fetched = bq.get_table(table)
    fetched.expires = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        milliseconds=300
    )
    bq.update_table(fetched, ["expires"])
    assert rows(bq, f"SELECT x FROM {table}") == [(1,)]
    time.sleep(0.4)
    with fails(NotFound, "notFound"):
        bq.get_table(table)
    with fails(NotFound, "notFound"):
        run(bq, f"SELECT x FROM {table}")
    run(bq, f"CREATE TABLE {table} AS SELECT 2 AS x")
    assert rows(bq, f"SELECT x FROM {table}") == [(2,)]


def test_dataset_default_table_expiration(bq):
    dataset = bigquery.Dataset(f"{bq.project}.{unique('expiring')}")
    dataset.default_table_expiration_ms = 3_600_000
    dataset = bq.create_dataset(dataset)
    run(bq, f"CREATE TABLE {dataset.dataset_id}.t (x INT64)")
    table = bq.get_table(f"{dataset.dataset_id}.t")
    assert table.expires - table.created == datetime.timedelta(hours=1)
    bq.delete_dataset(dataset, delete_contents=True)
