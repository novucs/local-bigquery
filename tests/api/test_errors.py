import re

import pytest
from google.api_core.exceptions import (
    BadRequest,
    Conflict,
    Forbidden,
    GoogleAPICallError,
    NotFound,
)
from google.cloud import bigquery

from tests.cases import FAST_RETRY, fails, run, unique

DUCKDB_TEXT = ("Binder Error", "Catalog Error", "Parser Error", "DuckDB")


def assert_no_duckdb_text(error):
    assert not any(text in error.message for text in DUCKDB_TEXT), error.message


def test_query_missing_table(bq, project, dataset):
    config = bigquery.QueryJobConfig(default_dataset=dataset.reference)
    with fails(NotFound, "notFound") as info:
        run(bq, "SELECT * FROM missing_table", config)
    assert f"Not found: Table {project}:{dataset.dataset_id}.missing_table" in (
        info.value.message
    )


def test_get_missing_table(bq, project, dataset):
    with fails(NotFound, "notFound") as info:
        bq.get_table(f"{dataset.dataset_id}.missing_table", retry=FAST_RETRY)
    assert_no_duckdb_text(info.value)


def test_create_duplicate_table(bq, project, dataset):
    table_id = f"{dataset.dataset_id}.{unique('t')}"
    bq.create_table(table_id)
    with fails(Conflict, "duplicate") as info:
        bq.create_table(table_id, retry=FAST_RETRY)
    assert "Already Exists: Table" in info.value.message


def test_syntax_error(bq):
    with fails(BadRequest, "invalidQuery") as info:
        run(bq, "SELEC 1")
    assert "Syntax error" in info.value.message
    assert "[1:1]" in info.value.message


def test_unknown_function(bq):
    with fails(BadRequest, "invalidQuery") as info:
        run(bq, "SELECT no_such_function(1)")
    assert "Function not found: no_such_function" in info.value.message


def test_unknown_column(bq):
    with fails(BadRequest, "invalidQuery") as info:
        run(bq, "SELECT nope FROM (SELECT 1 AS x)")
    assert "Unrecognized name: nope" in info.value.message


def test_type_error(bq):
    with fails(BadRequest, "invalidQuery") as info:
        run(bq, "SELECT 1 + TRUE")
    assert_no_duckdb_text(info.value)


def test_division_by_zero(bq):
    with fails(BadRequest, "invalidQuery") as info:
        run(bq, "SELECT 1 / 0")
    assert "division by zero" in info.value.message


def test_null_array_element(bq):
    with fails(BadRequest, "invalidQuery"):
        run(bq, "SELECT [1, NULL]")


def test_error_function(bq):
    with fails(BadRequest, "invalidQuery") as info:
        run(bq, "SELECT ERROR('boom')")
    assert "boom" in info.value.message


def test_invalid_project(bq):
    with fails(Forbidden, "accessDenied"):
        bq.query_and_wait(
            "SELECT 1", project="Invalid_Project!", retry=FAST_RETRY, job_retry=None
        )


def test_list_models_empty(bq, dataset):
    assert list(bq.list_models(dataset, retry=FAST_RETRY)) == []


def test_get_missing_model(bq, dataset):
    with fails(NotFound, "notFound"):
        bq.get_model(f"{dataset.dataset_id}.missing_model", retry=FAST_RETRY)


def test_get_missing_routine(bq, dataset):
    with fails(NotFound, "notFound"):
        bq.get_routine(f"{dataset.dataset_id}.missing_routine", retry=FAST_RETRY)


def query_error(bq, sql, **config) -> tuple[dict, str]:
    with pytest.raises(GoogleAPICallError) as info:
        run(bq, sql, bigquery.QueryJobConfig(**config))
    return info.value.errors[0], info.value.message


@pytest.mark.parametrize(
    "sql, message",
    [
        ("SELECT 1 / 0", r"division by zero: 1 / 0"),
        ("SELECT (4.0 / 2) / 0", r"division by zero: 2 / 0"),
        ("SELECT 9223372036854775807 + 1", r"Integer Overflow"),
        ("SELECT CAST('not-a-date' AS DATE)", r"Invalid date: 'not-a-date'"),
        (
            "SELECT EXTRACT(HOUR FROM TIMESTAMP '2024-01-15 12:00:00+00' "
            "AT TIME ZONE 'Mars/Olympus_Mons')",
            r"Invalid time zone: Mars/Olympus_Mons",
        ),
        pytest.param(
            "SELECT PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%S%Z', '2024-01-15T12:34:56IST')",
            r"Invalid time zone: IST",
            marks=pytest.mark.xfail(reason="%Z accepts zone abbreviations like IST"),
        ),
        ("SLECT 1 AS n", r'Syntax error: Unexpected identifier "SLECT" at \[1:1\]'),
        (
            "SELECT (1 + 2 AS x",
            r'Syntax error: Expected "," but got keyword AS at \[1:15\]',
        ),
        (
            "SELECT 'unterminated AS x",
            r"Syntax error: Unclosed string literal at \[1:8\]",
        ),
        (
            "SELECT CONCAT() AS c",
            r"No matching signature for function CONCAT with no arguments at \[1:8\]",
        ),
        ("SELECT\n  concat() AS c", r"function CONCAT with no arguments at \[2:3\]"),
        ("SELECT SAFE.SUBSTR('hello')", r"No matching signature for function SUBSTR"),
        ("SELECT IF(TRUE)", r"No matching signature for function IF at \[1:8\]"),
        ("SELECT UPPER('a', 'b')", r"No matching signature for function UPPER"),
        ("SELECT DATE_ADD(1)", r"No matching signature for function DATE_ADD"),
        (
            "SELECT REGEXP_EXTRACT('a')",
            r"No matching signature for function REGEXP_EXTRACT",
        ),
        (
            "SELECT 'a' = 1",
            r"No matching signature for operator = for argument types: STRING, INT64",
        ),
        (
            "SELECT 1.5 < 'a'",
            r"No matching signature for operator < for argument types: FLOAT64, STRING",
        ),
        (
            "SELECT a.k FROM (SELECT 'x' AS k) AS a JOIN (SELECT 1 AS k) AS b "
            "ON a.k = b.k",
            r"No matching signature for operator = for argument types: STRING, INT64",
        ),
        (
            "SELECT NO_SUCH_FUNCTION(1)",
            r"Function not found: NO_SUCH_FUNCTION at \[1:8\]",
        ),
        (
            "SELECT ARRAY_FIRST(CAST([] AS ARRAY<INT64>))",
            r"ARRAY_FIRST cannot get the first element of an empty array",
        ),
    ],
)
def test_query_error_wording(bq, sql, message):
    error, text = query_error(bq, sql)
    assert (error["reason"], error.get("location")) == ("invalidQuery", "query")
    assert re.search(message, text), text


def test_missing_routine_message(bq, project, dataset):
    path = f"`{project}.{dataset.dataset_id}`"
    error, text = query_error(bq, f"SELECT {path}.missing_fn(1)")
    assert error.get("location") == "query"
    assert f"Function not found: {path}.missing_fn at [1:8]" in text


def test_dry_run_error_location(bq):
    error, text = query_error(bq, "SELECT NO_SUCH_FUNCTION(1)", dry_run=True)
    assert error.get("location") == "q"
    assert "Function not found: NO_SUCH_FUNCTION at [1:8]" in text


def test_query_missing_dataset(bq, project, dataset):
    with fails(NotFound, "notFound") as info:
        run(bq, f"SELECT * FROM {dataset.dataset_id}_missing.t")
    assert (
        f"Not found: Dataset {project}:{dataset.dataset_id}_missing "
        "was not found in location US"
    ) in info.value.message


def test_query_missing_project(bq):
    table = "missing-project-xyz:any_dataset.any_table"
    with fails(Forbidden, "accessDenied") as info:
        run(bq, "SELECT * FROM `missing-project-xyz.any_dataset.any_table`")
    assert (
        f"Access Denied: Table {table}: User does not have permission to query "
        f"table {table}, or perhaps it does not exist."
    ) in info.value.message


def test_query_invalid_dataset_id(bq):
    error, text = query_error(bq, "SELECT * FROM `!!bad!!.t`")
    assert (error["reason"], error.get("location")) == ("invalid", "!!bad!!.t")
    assert (
        'Invalid dataset ID "!!bad!!". Dataset IDs must be alphanumeric '
        "(plus underscores and dashes) and must be at most 1024 characters long."
    ) in text


def test_unknown_session_message(bq):
    property = bigquery.ConnectionProperty("session_id", "no-such-session")
    error, text = query_error(bq, "SELECT 1", connection_properties=[property])
    assert error["reason"] == "invalid"
    assert "Invalid input session id." in text
