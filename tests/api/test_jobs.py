import datetime

import pytest
from google.api_core.exceptions import (
    BadRequest,
    Conflict,
    GoogleAPICallError,
    NotFound,
)
from google.cloud import bigquery

from tests.cases import FAST_RETRY, fails, run, run_job, unique

ROWS_25 = "SELECT x FROM UNNEST(GENERATE_ARRAY(1, 25)) AS x ORDER BY x"


@pytest.fixture
def table(bq, dataset):
    table_id = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table_id} (x INT64)")
    return table_id


def test_insert_and_fast_path_agree(bq):
    job = run_job(bq, "SELECT 1 AS a")
    assert [tuple(r.values()) for r in job.result()] == [(1,)]
    assert [tuple(r.values()) for r in run(bq, "SELECT 1 AS a")] == [(1,)]


def test_completed_job_resource(bq, project):
    job = run_job(bq, "SELECT 1")
    assert job.state == "DONE"
    assert job.project == project
    assert job.location == "US"
    assert job.error_result is None
    assert job.created <= job.started <= job.ended


def test_caller_supplied_job_id(bq):
    job_id = unique("job")
    job = bq.query("SELECT 1 AS a", job_id=job_id)
    assert job.job_id == job_id
    assert [tuple(r.values()) for r in job.result()] == [(1,)]
    assert bq.get_job(job_id).job_id == job_id


def test_job_id_prefix(bq):
    assert bq.query("SELECT 1", job_id_prefix="prefix_").job_id.startswith("prefix_")


def test_duplicate_job_id(bq):
    job_id = unique("job")
    bq.query("SELECT 1", job_id=job_id).result()
    with fails(Conflict, "duplicate"):
        bq.query("SELECT 1", job_id=job_id, retry=FAST_RETRY, job_retry=None)


def test_get_missing_job(bq):
    with fails(NotFound, "notFound"):
        bq.get_job(unique("missing"), retry=FAST_RETRY)


def test_list_jobs(bq):
    job = run_job(bq, "SELECT 1")
    assert job.job_id in [j.job_id for j in bq.list_jobs()]


@pytest.mark.xfail(reason="list_jobs ignores maxResults")
def test_list_jobs_pages(bq):
    run_job(bq, "SELECT 1")
    run_job(bq, "SELECT 2")
    assert len(list(bq.list_jobs(max_results=1))) == 1
    assert {p.num_items for p in bq.list_jobs(page_size=1, max_results=2).pages} == {1}


@pytest.mark.xfail(reason="list_jobs ignores stateFilter")
def test_list_jobs_state_filter(bq):
    job = run_job(bq, "SELECT 1")
    assert job.job_id in [j.job_id for j in bq.list_jobs(state_filter="done")]
    assert job.job_id not in [j.job_id for j in bq.list_jobs(state_filter="running")]


@pytest.mark.xfail(reason="list_jobs ignores creation time filters")
def test_list_jobs_creation_time_filters(bq):
    job = run_job(bq, "SELECT 1")
    after = job.created + datetime.timedelta(seconds=1)
    assert job.job_id in [j.job_id for j in bq.list_jobs(max_creation_time=after)]
    assert job.job_id not in [j.job_id for j in bq.list_jobs(min_creation_time=after)]


def test_list_jobs_all_users(bq):
    job = run_job(bq, "SELECT 1")
    assert job.job_id in [j.job_id for j in bq.list_jobs(all_users=True)]


def test_cancel_done_job_is_noop(bq):
    job = run_job(bq, "SELECT 1")
    cancelled = bq.cancel_job(job.job_id, location=job.location)
    assert cancelled.state == "DONE"
    assert cancelled.error_result is None


def test_cancel_missing_job(bq):
    with fails(NotFound, "notFound"):
        bq.cancel_job(unique("missing"), location="US", retry=FAST_RETRY)


def test_delete_job_metadata(bq):
    job = run_job(bq, "SELECT 1")
    bq.delete_job_metadata(job)
    with fails(NotFound, "notFound"):
        bq.get_job(job.job_id, location=job.location, retry=FAST_RETRY)


@pytest.mark.xfail(reason="dry run executes and omits statistics")
def test_dry_run(bq):
    job = bq.query(
        "SELECT 1 AS a, 'x' AS b", job_config=bigquery.QueryJobConfig(dry_run=True)
    )
    assert job.state == "DONE"
    assert job.statement_type == "SELECT"
    assert job.total_bytes_processed == 0
    assert [f.name for f in job.schema] == ["a", "b"]


@pytest.mark.xfail(reason="dry run executes DML")
def test_dry_run_does_not_execute(bq, table):
    config = bigquery.QueryJobConfig(dry_run=True)
    job = bq.query(f"INSERT INTO {table} VALUES (1)", job_config=config)
    assert job.statement_type == "INSERT"
    assert list(run(bq, f"SELECT * FROM {table}")) == []


def test_dry_run_invalid_query(bq):
    with fails(BadRequest, "invalidQuery"):
        bq.query(
            "SELECT nope",
            job_config=bigquery.QueryJobConfig(dry_run=True),
            retry=FAST_RETRY,
            job_retry=None,
        )


def test_labels_round_trip(bq):
    job = run_job(bq, "SELECT 1", labels={"team": "data", "env": "dev"})
    assert bq.get_job(job.job_id).labels == {"team": "data", "env": "dev"}


def test_job_timeout_is_echoed(bq):
    job = run_job(bq, "SELECT 1", job_timeout_ms=60_000)
    assert int(bq.get_job(job.job_id).configuration.job_timeout_ms) == 60_000


@pytest.mark.xfail(reason="cacheHit not reported")
def test_cache_hit_reported(bq):
    assert run_job(bq, "SELECT 1", use_query_cache=False).cache_hit is False


@pytest.mark.parametrize(
    "sql, statement_type",
    [
        ("INSERT INTO {t} VALUES (1)", "INSERT"),
        ("UPDATE {t} SET x = 2 WHERE TRUE", "UPDATE"),
        ("DELETE FROM {t} WHERE TRUE", "DELETE"),
        (
            "MERGE {t} T USING (SELECT 1 AS x) S ON T.x = S.x "
            "WHEN NOT MATCHED THEN INSERT (x) VALUES (x)",
            "MERGE",
        ),
        ("CREATE TABLE {t}_new (x INT64)", "CREATE_TABLE"),
        ("CREATE TABLE {t}_ctas AS SELECT 1 AS x", "CREATE_TABLE_AS_SELECT"),
        ("CREATE VIEW {t}_view AS SELECT 1 AS x", "CREATE_VIEW"),
        ("DROP TABLE {t}", "DROP_TABLE"),
        ("SELECT 1; SELECT 2", "SCRIPT"),
    ],
)
@pytest.mark.xfail(reason="statementType always SELECT")
def test_statement_type(bq, table, sql, statement_type):
    assert run_job(bq, sql.format(t=table)).statement_type == statement_type


def test_select_statement_type(bq):
    assert run_job(bq, "SELECT 1").statement_type == "SELECT"


@pytest.mark.xfail(reason="DML statistics not reported")
def test_dml_statistics(bq, table):
    job = run_job(bq, f"INSERT INTO {table} VALUES (1), (2), (3)")
    assert job.num_dml_affected_rows == 3
    assert job.dml_stats.inserted_row_count == 3
    job = run_job(bq, f"UPDATE {table} SET x = x + 1 WHERE x > 1")
    assert job.num_dml_affected_rows == 2
    assert job.dml_stats.updated_row_count == 2
    job = run_job(bq, f"DELETE FROM {table} WHERE x = 1")
    assert job.dml_stats.deleted_row_count == 1


@pytest.mark.xfail(reason="DDL statistics not reported")
def test_ddl_statistics(bq, dataset):
    table_id = f"{dataset.dataset_id}.{unique('ddl')}"
    created = run_job(bq, f"CREATE TABLE {table_id} (x INT64)")
    assert created.ddl_operation_performed == "CREATE"
    assert created.ddl_target_table.table_id == table_id.split(".")[1]
    skipped = run_job(bq, f"CREATE TABLE IF NOT EXISTS {table_id} (x INT64)")
    assert skipped.ddl_operation_performed == "SKIP"
    replaced = run_job(bq, f"CREATE OR REPLACE TABLE {table_id} (x INT64)")
    assert replaced.ddl_operation_performed == "REPLACE"
    assert run_job(bq, f"DROP TABLE {table_id}").ddl_operation_performed == "DROP"


def test_script_returns_last_statement(bq):
    job = run_job(bq, "SELECT 1; SELECT 2 AS b")
    assert [tuple(r.values()) for r in job.result()] == [(2,)]


@pytest.mark.xfail(reason="scripts do not create child jobs")
def test_script_child_jobs(bq):
    job = run_job(bq, "SELECT 1; SELECT 2")
    assert job.num_child_jobs == 2
    children = list(bq.list_jobs(parent_job=job))
    assert len(children) == 2
    assert {child.parent_job_id for child in children} == {job.job_id}


@pytest.mark.xfail(reason="no anonymous destination table")
def test_anonymous_destination_table(bq):
    job = run_job(bq, "SELECT 1 AS a")
    assert job.destination.dataset_id.startswith("_")
    rows = bq.list_rows(job.destination)
    assert [tuple(r.values()) for r in rows] == [(1,)]


@pytest.mark.xfail(reason="destination table not supported")
def test_destination_write_dispositions(bq, dataset):
    destination = f"{bq.project}.{dataset.dataset_id}.{unique('dest')}"
    truncate = bigquery.WriteDisposition.WRITE_TRUNCATE
    run_job(bq, "SELECT 1 AS x", destination=destination, write_disposition=truncate)
    append = bigquery.WriteDisposition.WRITE_APPEND
    run_job(bq, "SELECT 2 AS x", destination=destination, write_disposition=append)
    assert bq.get_table(destination).num_rows == 2
    run_job(bq, "SELECT 3 AS x", destination=destination, write_disposition=truncate)
    assert [r.x for r in bq.list_rows(destination)] == [3]
    with pytest.raises(GoogleAPICallError):
        run_job(
            bq,
            "SELECT 4 AS x",
            destination=destination,
            write_disposition=bigquery.WriteDisposition.WRITE_EMPTY,
        )


@pytest.mark.xfail(reason="destination table not supported")
def test_destination_create_never_missing_table(bq, dataset):
    destination = f"{bq.project}.{dataset.dataset_id}.{unique('missing')}"
    with fails(NotFound, "notFound"):
        run_job(
            bq,
            "SELECT 1 AS x",
            destination=destination,
            create_disposition=bigquery.CreateDisposition.CREATE_NEVER,
        )


def test_result_total_rows(bq):
    assert run_job(bq, ROWS_25).result().total_rows == 25


@pytest.mark.xfail(reason="result paging not supported")
def test_result_pages(bq):
    pages = run_job(bq, ROWS_25).result(page_size=10).pages
    assert [[r.x for r in page] for page in pages] == [
        list(range(1, 11)),
        list(range(11, 21)),
        list(range(21, 26)),
    ]


def test_result_max_results(bq):
    assert [r.x for r in run_job(bq, ROWS_25).result(max_results=7)] == list(
        range(1, 8)
    )


@pytest.mark.xfail(reason="result paging not supported")
def test_result_start_index(bq):
    rows = run_job(bq, ROWS_25).result(start_index=20)
    assert [r.x for r in rows] == list(range(21, 26))


def test_query_and_wait_max_results(bq):
    rows = bq.query_and_wait(ROWS_25, max_results=5)
    assert [r.x for r in rows] == list(range(1, 6))


@pytest.mark.xfail(reason="result paging not supported")
def test_query_and_wait_pages(bq):
    rows = bq.query_and_wait(ROWS_25, page_size=10)
    assert [len(list(page)) for page in rows.pages] == [10, 10, 5]


def test_large_result(bq):
    rows = run(
        bq, "SELECT x, REPEAT('x', 100) AS s FROM UNNEST(GENERATE_ARRAY(1, 20000)) x"
    )
    assert sum(1 for _ in rows) == 20000


@pytest.mark.xfail(reason="failed queries are rejected at insert")
def test_failed_query_is_done_job_with_error(bq):
    job = bq.query("SELECT nope", retry=FAST_RETRY, job_retry=None)
    with fails(BadRequest, "invalidQuery"):
        job.result(retry=FAST_RETRY)
    assert job.state == "DONE"
    assert job.error_result["reason"] == "invalidQuery"
    assert bq.get_job(job.job_id).error_result["reason"] == "invalidQuery"


def test_query_and_wait_failure(bq):
    with fails(BadRequest, "invalidQuery"):
        run(bq, "SELECT nope")
