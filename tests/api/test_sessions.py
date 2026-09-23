import pytest
from google.api_core.exceptions import BadRequest, GoogleAPICallError
from google.cloud import bigquery

from tests.cases import FAST_RETRY, fails, run, unique


def in_session(bq, sql, session_id=None):
    config = bigquery.QueryJobConfig(
        create_session=session_id is None,
        connection_properties=[bigquery.ConnectionProperty("session_id", session_id)]
        if session_id
        else [],
    )
    job = bq.query(sql, job_config=config, retry=FAST_RETRY, job_retry=None)
    return job, [tuple(r.values()) for r in job.result(retry=FAST_RETRY)]


def new_session(bq):
    job, _ = in_session(bq, "SELECT 1")
    return job.session_info.session_id


def test_create_session(bq):
    assert new_session(bq)


def test_jobs_report_their_session(bq):
    session_id = new_session(bq)
    job, _ = in_session(bq, "SELECT 1", session_id)
    assert job.session_info.session_id == session_id


def test_jobs_outside_sessions_have_none(bq):
    job = bq.query("SELECT 1")
    job.result()
    assert job.session_info is None


def test_temp_table_persists(bq):
    session_id = new_session(bq)
    in_session(bq, "CREATE TEMP TABLE t AS SELECT 1 AS x", session_id)
    assert in_session(bq, "SELECT x FROM t", session_id)[1] == [(1,)]


@pytest.mark.xfail(reason="sessions not supported")
def test_variables_persist(bq):
    session_id = new_session(bq)
    in_session(bq, "DECLARE x INT64 DEFAULT 5", session_id)
    assert in_session(bq, "SELECT x", session_id)[1] == [(5,)]


def test_sessions_are_isolated(bq):
    first, second = new_session(bq), new_session(bq)
    in_session(bq, "CREATE TEMP TABLE isolated AS SELECT 1 AS x", first)
    with pytest.raises(GoogleAPICallError):
        in_session(bq, "SELECT x FROM isolated", second)


def test_abort_session(bq):
    session_id = new_session(bq)
    in_session(bq, "CALL BQ.ABORT_SESSION()", session_id)
    with pytest.raises(GoogleAPICallError):
        in_session(bq, "SELECT 1", session_id)


def test_unknown_session(bq):
    with fails(BadRequest, "invalid"):
        in_session(bq, "SELECT 1", "not-a-session")


def test_transaction_spans_jobs(bq, dataset):
    table_id = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table_id} (x INT64)")
    session_id = new_session(bq)
    in_session(bq, "BEGIN TRANSACTION", session_id)
    in_session(bq, f"INSERT INTO {table_id} VALUES (1)", session_id)
    assert in_session(bq, f"SELECT COUNT(*) FROM {table_id}", session_id)[1] == [(1,)]
    assert list(run(bq, f"SELECT * FROM {table_id}")) == []
    in_session(bq, "ROLLBACK TRANSACTION", session_id)
    assert list(run(bq, f"SELECT * FROM {table_id}")) == []


def test_transaction_commits_within_script(bq, dataset):
    table_id = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table_id} (x INT64)")
    run(
        bq,
        f"BEGIN TRANSACTION; INSERT INTO {table_id} VALUES (1); COMMIT TRANSACTION;",
    )
    assert [tuple(r.values()) for r in run(bq, f"SELECT x FROM {table_id}")] == [(1,)]
