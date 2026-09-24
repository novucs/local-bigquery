import pytest
from google.api_core.exceptions import (
    BadRequest,
    Conflict,
    NotFound,
    PreconditionFailed,
)
from google.cloud import bigquery
from google.cloud.bigquery import StandardSqlDataType, StandardSqlTypeNames

from tests.cases import FAST_RETRY, fails, rows, run, scalar, unique

INT64 = StandardSqlDataType(type_kind=StandardSqlTypeNames.INT64)
FLOAT64 = StandardSqlDataType(type_kind=StandardSqlTypeNames.FLOAT64)


@pytest.fixture
def routine_id(dataset):
    return f"{dataset.project}.{dataset.dataset_id}.{unique('r')}"


def name(routine_id):
    project, rest = routine_id.split(".", 1)
    return f"`{project}`.{rest}"


def argument(name, data_type=INT64, **kwargs):
    return bigquery.RoutineArgument(name=name, data_type=data_type, **kwargs)


def create(bq, routine_id, **properties):
    routine = bigquery.Routine(routine_id, **properties)
    return bq.create_routine(routine, retry=FAST_RETRY)


def test_create_sql_function(bq, dataset, routine_id):
    created = create(
        bq,
        routine_id,
        type_="SCALAR_FUNCTION",
        language="SQL",
        body="x * 2",
        arguments=[argument("x")],
        return_type=INT64,
        description="doubles",
    )
    assert created.etag and created.created
    assert scalar(bq, f"SELECT {name(routine_id)}(21)") == 42
    fetched = bq.get_routine(routine_id, retry=FAST_RETRY)
    assert (fetched.type_, fetched.body, fetched.description) == (
        "SCALAR_FUNCTION",
        "x * 2",
        "doubles",
    )
    assert fetched.arguments[0].data_type.type_kind == StandardSqlTypeNames.INT64
    assert fetched.return_type.type_kind == StandardSqlTypeNames.INT64
    listed = bq.list_routines(dataset, retry=FAST_RETRY)
    assert routine_id in [str(r.reference) for r in listed]
    routine_name = routine_id.rsplit(".", 1)[1]
    assert rows(
        bq,
        "SELECT routine_type, routine_body, data_type FROM "
        f"`{dataset.dataset_id}`.INFORMATION_SCHEMA.ROUTINES "
        f"WHERE routine_name = '{routine_name}'",
    ) == [("FUNCTION", "SQL", "INT64")]


def test_create_function_with_array_argument(bq, routine_id):
    array = StandardSqlDataType(
        type_kind=StandardSqlTypeNames.ARRAY, array_element_type=INT64
    )
    create(
        bq,
        routine_id,
        type_="SCALAR_FUNCTION",
        body="ARRAY_LENGTH(xs)",
        arguments=[argument("xs", array)],
    )
    fetched = bq.get_routine(routine_id, retry=FAST_RETRY)
    element = fetched.arguments[0].data_type.array_element_type
    assert element.type_kind == StandardSqlTypeNames.INT64


def test_ddl_function_types_are_structured(bq, routine_id):
    run(
        bq,
        f"CREATE FUNCTION {name(routine_id)}(xs ARRAY<STRING>, y ANY TYPE) "
        "AS (xs[OFFSET(0)])",
    )
    fetched = bq.get_routine(routine_id, retry=FAST_RETRY)
    data_type = fetched.arguments[0].data_type
    assert data_type.type_kind == StandardSqlTypeNames.ARRAY
    assert data_type.array_element_type.type_kind == StandardSqlTypeNames.STRING
    assert (fetched.arguments[1].kind, fetched.arguments[1].data_type) == (
        "ANY_TYPE",
        None,
    )


def test_create_any_type_function(bq, routine_id):
    create(
        bq,
        routine_id,
        type_="SCALAR_FUNCTION",
        body="x",
        arguments=[bigquery.RoutineArgument(name="x", kind="ANY_TYPE")],
    )
    assert scalar(bq, f"SELECT {name(routine_id)}('a')") == "a"


def test_create_javascript_function(bq, routine_id):
    create(
        bq,
        routine_id,
        type_="SCALAR_FUNCTION",
        language="JAVASCRIPT",
        body="return x * 3 + 'it\\'s'.length;",
        arguments=[argument("x", FLOAT64)],
        return_type=FLOAT64,
    )
    assert scalar(bq, f"SELECT {name(routine_id)}(2)") == 10.0
    assert bq.get_routine(routine_id, retry=FAST_RETRY).language == "JAVASCRIPT"


def test_create_table_function(bq, routine_id):
    create(
        bq,
        routine_id,
        type_="TABLE_VALUED_FUNCTION",
        body="SELECT v FROM UNNEST(GENERATE_ARRAY(1, n)) AS v",
        arguments=[argument("n")],
    )
    assert scalar(bq, f"SELECT SUM(v) FROM {name(routine_id)}(4)") == 10
    routine = bq.get_routine(routine_id, retry=FAST_RETRY)
    assert routine.type_ == "TABLE_VALUED_FUNCTION"


def test_create_procedure(bq, routine_id):
    create(
        bq,
        routine_id,
        type_="PROCEDURE",
        body="SET y = x * 2;",
        arguments=[argument("x"), argument("y", mode="OUT")],
    )
    sql = f"DECLARE r INT64; CALL {name(routine_id)}(3, r); SELECT r"
    assert scalar(bq, sql) == 6
    routine = bq.get_routine(routine_id, retry=FAST_RETRY)
    assert (routine.type_, routine.arguments[1].mode) == ("PROCEDURE", "OUT")


def test_create_duplicate_routine(bq, routine_id):
    create(bq, routine_id, type_="SCALAR_FUNCTION", body="1")
    with fails(Conflict, "duplicate"):
        create(bq, routine_id, type_="SCALAR_FUNCTION", body="1")


def test_create_routine_in_missing_dataset(bq, project):
    with fails(NotFound, "notFound"):
        create(
            bq, f"{project}.{unique('missing')}.f", type_="SCALAR_FUNCTION", body="1"
        )


def test_update_routine(bq, routine_id):
    routine = create(
        bq, routine_id, type_="SCALAR_FUNCTION", body="x + 1", arguments=[argument("x")]
    )
    routine.body = "x + 100"
    routine.description = "hundred"
    fields = ["type_", "arguments", "body", "description"]
    updated = bq.update_routine(routine, fields, retry=FAST_RETRY)
    assert (updated.body, updated.description) == ("x + 100", "hundred")
    assert updated.type_ == "SCALAR_FUNCTION"
    assert scalar(bq, f"SELECT {name(routine_id)}(1)") == 101
    assert updated.created == routine.created


def test_update_routine_stale_etag(bq, routine_id):
    routine = create(bq, routine_id, type_="SCALAR_FUNCTION", body="1")
    routine.description = "first"
    fields = ["type_", "body", "description"]
    bq.update_routine(routine, fields, retry=FAST_RETRY)
    with fails(PreconditionFailed, "conditionNotMet"):
        bq.update_routine(routine, fields, retry=FAST_RETRY)


def test_update_missing_routine(bq, routine_id):
    with fails(NotFound, "notFound"):
        bq.update_routine(
            bigquery.Routine(routine_id, type_="SCALAR_FUNCTION", body="1"),
            ["type_", "body"],
            retry=FAST_RETRY,
        )


def test_update_requires_routine_type(bq, routine_id):
    routine = create(bq, routine_id, type_="SCALAR_FUNCTION", body="1")
    routine.body = "2"
    with pytest.raises(BadRequest, match="Routine type must be specified"):
        bq.update_routine(routine, ["body"], retry=FAST_RETRY)


def test_routines_are_dropped_with_dataset(bq, project):
    dataset_id = unique("routines")
    bq.create_dataset(dataset_id, retry=FAST_RETRY)
    create(bq, f"{project}.{dataset_id}.f", type_="SCALAR_FUNCTION", body="1")
    bq.delete_dataset(dataset_id, delete_contents=True, retry=FAST_RETRY)
    bq.create_dataset(dataset_id, retry=FAST_RETRY)
    assert list(bq.list_routines(dataset_id, retry=FAST_RETRY)) == []
    bq.delete_dataset(dataset_id, retry=FAST_RETRY)
