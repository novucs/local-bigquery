import pytest
from google.api_core.exceptions import BadRequest, Conflict, Forbidden, NotFound

from tests.cases import FAST_RETRY, fails, run, unique

DUCKDB_TEXT = ("Binder Error", "Catalog Error", "Parser Error", "DuckDB")


def assert_no_duckdb_text(error):
    assert not any(text in error.message for text in DUCKDB_TEXT), error.message


@pytest.mark.xfail(reason="unknown table leaks DuckDB message")
def test_query_missing_table(bq, project, dataset):
    with fails(NotFound, "notFound") as info:
        run(bq, "SELECT * FROM missing_table")
    assert f"Not found: Table {project}:{dataset.dataset_id}.missing_table" in (
        info.value.message
    )


def test_get_missing_table(bq, project, dataset):
    with fails(NotFound, "notFound") as info:
        bq.get_table(f"{dataset.dataset_id}.missing_table", retry=FAST_RETRY)
    assert_no_duckdb_text(info.value)


@pytest.mark.xfail(reason="duplicate table raises 500")
def test_create_duplicate_table(bq, project, dataset):
    table_id = f"{dataset.dataset_id}.{unique('t')}"
    bq.create_table(table_id)
    with fails(Conflict, "duplicate") as info:
        bq.create_table(table_id, retry=FAST_RETRY)
    assert info.value.message.startswith("Already Exists: Table")


@pytest.mark.xfail(reason="syntax errors leak DuckDB message")
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


@pytest.mark.xfail(reason="division by zero returns NULL")
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


@pytest.mark.xfail(reason="routines.get not implemented")
def test_get_missing_routine(bq, dataset):
    with fails(NotFound, "notFound"):
        bq.get_routine(f"{dataset.dataset_id}.missing_routine", retry=FAST_RETRY)
