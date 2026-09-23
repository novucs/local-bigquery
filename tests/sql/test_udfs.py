import itertools
import time

import pytest
from google.cloud import bigquery

from tests.cases import q, run, scalar, unique

_names = (f"js{i}" for i in itertools.count())


def js(args: str, returns: str, body: str, select: str) -> str:
    f = next(_names)
    return (
        f"CREATE TEMP FUNCTION {f}({args}) RETURNS {returns} LANGUAGE js AS {body}; "
        + select.format(f=f)
    )


CASES = [
    q("CREATE TEMP FUNCTION f(x INT64) AS (x * 2); SELECT f(3)", 6, types="INT64"),
    q("CREATE TEMPORARY FUNCTION f(x INT64) AS (x + 1); SELECT f(1)", 2),
    q("CREATE TEMP FUNCTION f(x INT64) AS (x * 2); SELECT f(NULL)", None),
    q(
        "CREATE TEMP FUNCTION f(x INT64, y INT64) RETURNS FLOAT64 AS ((x + 4) / y); "
        "SELECT v, f(v, 2) FROM UNNEST(@params) AS v",
        rows=[(2, 3.0), (3, 3.5), (5, 4.5), (8, 6.0)],
        types=("INT64", "FLOAT64"),
        params=[bigquery.ArrayQueryParameter("params", "INT64", [2, 3, 5, 8])],
    ),
    q(
        "CREATE TEMP FUNCTION f(s STRING) AS (CONCAT('hi ', s)); SELECT f('bob')",
        "hi bob",
    ),
    q(
        "CREATE TEMP FUNCTION f(arr ANY TYPE) AS (arr[SAFE_OFFSET(0)]); "
        "SELECT f([1, 2]), f(['a'])",
        rows=[(1, "a")],
        types=("INT64", "STRING"),
    ),
    q(
        "CREATE TEMP FUNCTION f(a INT64) AS (STRUCT(a AS a, a * 2 AS b)); SELECT f(2)",
        {"a": 2, "b": 4},
        types="STRUCT<a INT64, b INT64>",
    ),
    q(
        "CREATE TEMP FUNCTION f(n INT64) AS (GENERATE_ARRAY(1, n)); SELECT f(3)",
        [1, 2, 3],
        types="ARRAY<INT64>",
    ),
    q(
        "CREATE TEMP FUNCTION a(x INT64) AS (x + 1); "
        "CREATE TEMP FUNCTION b(x INT64) AS (a(x) * 2); SELECT b(1)",
        4,
    ),
    q(
        "CREATE TEMP FUNCTION f(x INT64) AS ((SELECT SUM(v) FROM UNNEST([x, x]) AS v)); "
        "SELECT f(4)",
        8,
    ),
    q(
        js(
            "x FLOAT64, y FLOAT64",
            "FLOAT64",
            "'return x * y;'",
            "WITH t AS (SELECT 1 AS x, 5 AS y UNION ALL SELECT 2, 10 UNION ALL SELECT 3, 15) "
            "SELECT x, y, {f}(x, y) FROM t ORDER BY x",
        ),
        rows=[(1, 5, 5.0), (2, 10, 20.0), (3, 15, 45.0)],
    ),
    q(
        js("s STRING", "STRING", "'return s.toUpperCase();'", "SELECT {f}('ab')"),
        "AB",
    ),
    q(
        js("x FLOAT64", "INT64", "'return x + 1;'", "SELECT {f}(41)"),
        42,
        types="INT64",
    ),
    q(js("x INT64", "INT64", "'return x + 1;'", "SELECT {f}(41)"), 411),
    q(
        js("s STRING", "INT64", "'return s;'", "SELECT {f}('9007199254740993')"),
        9007199254740993,
    ),
    q(
        js("b BOOL", "BOOL", "'return !b;'", "SELECT {f}(TRUE)"),
        False,
    ),
    q(
        js(
            "a ARRAY<FLOAT64>",
            "ARRAY<FLOAT64>",
            "'return a.map(x => x * 2);'",
            "SELECT {f}([1.5, 2.0])",
        ),
        [3.0, 4.0],
    ),
    q(
        js(
            "s STRUCT<a FLOAT64, b STRING>",
            "STRING",
            "'return s.b + s.a;'",
            "SELECT {f}(STRUCT(1.0, 'x'))",
        ),
        "x1",
    ),
    q(
        js(
            "x FLOAT64",
            "STRUCT<doubled FLOAT64, label STRING>",
            "'return {doubled: x * 2, label: \"n\" + x};'",
            "SELECT {f}(2)",
        ),
        {"doubled": 4.0, "label": "n2"},
    ),
    q(
        js("x FLOAT64", "FLOAT64", "'return x === null ? -1 : x;'", "SELECT {f}(NULL)"),
        -1.0,
    ),
    q(
        js("x FLOAT64", "FLOAT64", "'return null;'", "SELECT {f}(1)"),
        None,
    ),
    q(
        js(
            "x FLOAT64",
            "FLOAT64",
            "'return Math.max(x, 10);'",
            "SELECT {f}(v) FROM UNNEST([1.0, 20.0]) AS v ORDER BY v",
        ),
        rows=[(10.0,), (20.0,)],
    ),
    q(
        js(
            "s STRING",
            "STRING",
            "'return JSON.parse(s).k;'",
            """SELECT {f}('{{"k": "v"}}')""",
        ),
        "v",
    ),
    q(
        js("x FLOAT64", "FLOAT64", "'throw new Error(\"boom\");'", "SELECT {f}(1)"),
        error="boom",
    ),
    q(
        js(
            "x FLOAT64",
            "FLOAT64",
            "'return x + 1;'",
            "CREATE TEMP FUNCTION g(x FLOAT64) AS ({f}(x) * 2); SELECT g(1)",
        ),
        4.0,
    ),
    q(
        js(
            "x FLOAT64",
            "STRING",
            '\'return x > 1 ? "hi" : "lo";\'',
            "SELECT {f}(v), COUNT(*) FROM UNNEST([1.0, 2.0, 3.0]) AS v GROUP BY 1 ORDER BY 1",
        ),
        rows=[("hi", 2), ("lo", 1)],
    ),
    q(
        "SELECT no_such_function(1)",
        error="Function not found",
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_udfs(check, case):
    check(case)


def test_js_udf_is_fast_over_many_rows(bq):
    start = time.monotonic()
    total = scalar(
        bq,
        js(
            "x FLOAT64",
            "FLOAT64",
            "'return x * 2;'",
            "SELECT SUM({f}(v)) FROM UNNEST(GENERATE_ARRAY(1, 1000)) AS v",
        ),
    )
    assert total == 1001000.0
    assert time.monotonic() - start < 0.5


@pytest.fixture
def routine(dataset):
    return f"{dataset.dataset_id}.{unique('r')}"


def test_persistent_sql_function(bq, routine):
    run(bq, f"CREATE FUNCTION {routine}(x INT64) AS (x + 1)")
    assert scalar(bq, f"SELECT {routine}(1)") == 2


def test_persistent_function_or_replace(bq, routine):
    run(bq, f"CREATE FUNCTION {routine}(x INT64) AS (x + 1)")
    run(bq, f"CREATE OR REPLACE FUNCTION {routine}(x INT64) AS (x + 100)")
    assert scalar(bq, f"SELECT {routine}(1)") == 101


def test_persistent_function_if_not_exists_keeps_original(bq, routine):
    run(bq, f"CREATE FUNCTION {routine}(x INT64) AS (x + 1)")
    run(bq, f"CREATE FUNCTION IF NOT EXISTS {routine}(x INT64) AS (x + 100)")
    assert scalar(bq, f"SELECT {routine}(1)") == 2


def test_persistent_function_duplicate(bq, routine):
    run(bq, f"CREATE FUNCTION {routine}(x INT64) AS (x + 1)")
    with pytest.raises(Exception, match="(?i)already exists"):
        run(bq, f"CREATE FUNCTION {routine}(x INT64) AS (x + 1)")


def test_drop_function(bq, routine):
    run(bq, f"CREATE FUNCTION {routine}(x INT64) AS (x + 1)")
    run(bq, f"DROP FUNCTION {routine}")
    with pytest.raises(Exception, match="Function not found"):
        run(bq, f"SELECT {routine}(1)")
    run(bq, f"DROP FUNCTION IF EXISTS {routine}")


def test_persistent_js_function(bq, routine):
    run(
        bq,
        f"CREATE FUNCTION {routine}(x FLOAT64) RETURNS FLOAT64 "
        "LANGUAGE js AS 'return x * 3;'",
    )
    assert scalar(bq, f"SELECT {routine}(2)") == 6.0


def test_function_ddl_statistics(bq, routine):
    job = bq.query(f"CREATE FUNCTION {routine}(x INT64) AS (x)")
    job.result()
    assert job.statement_type == "CREATE_FUNCTION"
    assert job.ddl_operation_performed == "CREATE"
    assert job.ddl_target_routine.routine_id == routine.split(".")[1]
    job = bq.query(f"CREATE OR REPLACE FUNCTION {routine}(x INT64) AS (x)")
    job.result()
    assert job.ddl_operation_performed == "REPLACE"
    job = bq.query(f"DROP FUNCTION IF EXISTS {routine}_missing")
    job.result()
    assert job.ddl_operation_performed == "SKIP"


def test_table_function(bq, routine):
    run(
        bq,
        f"CREATE TABLE FUNCTION {routine}(n INT64) AS "
        "SELECT v FROM UNNEST(GENERATE_ARRAY(1, n)) AS v",
    )
    rows = run(bq, f"SELECT v FROM {routine}(3) ORDER BY v")
    assert [tuple(r) for r in rows] == [(1,), (2,), (3,)]
    assert scalar(bq, f"SELECT SUM(v) FROM {routine}(4)") == 10
    assert list(run(bq, f"SELECT v FROM {routine}(NULL)")) == []


def test_table_function_joined_with_table(bq, dataset, routine):
    table = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table} AS SELECT 2 AS v, 'two' AS name")
    run(
        bq,
        f"CREATE TABLE FUNCTION {routine}(n INT64) AS "
        "SELECT v FROM UNNEST(GENERATE_ARRAY(1, n)) AS v",
    )
    rows = run(bq, f"SELECT name FROM {routine}(3) JOIN {table} USING (v)")
    assert [tuple(r) for r in rows] == [("two",)]


def test_procedure_out_argument(bq, routine):
    run(
        bq, f"CREATE PROCEDURE {routine}(x INT64, OUT y INT64) BEGIN SET y = x * 2; END"
    )
    assert scalar(bq, f"DECLARE r INT64; CALL {routine}(3, r); SELECT r") == 6


def test_procedure_inout_argument(bq, routine):
    run(bq, f"CREATE PROCEDURE {routine}(INOUT v INT64) BEGIN SET v = v + 1; END")
    sql = f"DECLARE v INT64 DEFAULT 1; CALL {routine}(v); CALL {routine}(v); SELECT v"
    assert scalar(bq, sql) == 3


def test_procedure_modifies_table(bq, dataset, routine):
    table = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table} (v INT64)")
    run(bq, f"CREATE PROCEDURE {routine}(x INT64) BEGIN INSERT {table} VALUES (x); END")
    run(bq, f"CALL {routine}(7)")
    assert scalar(bq, f"SELECT SUM(v) FROM {table}") == 7


def test_drop_procedure(bq, routine):
    run(bq, f"CREATE PROCEDURE {routine}() BEGIN SELECT 1; END")
    run(bq, f"DROP PROCEDURE {routine}")
    with pytest.raises(Exception):
        run(bq, f"CALL {routine}()")


def test_temp_functions_do_not_leak_between_queries(bq):
    define = "CREATE TEMP FUNCTION leak(x FLOAT64) RETURNS FLOAT64 LANGUAGE js AS {};"
    assert scalar(bq, define.format("'return x + 1;'") + " SELECT leak(1)") == 2.0
    assert scalar(bq, define.format("'return x + 2;'") + " SELECT leak(1)") == 3.0
    with pytest.raises(Exception):
        run(bq, "SELECT leak(1)")
