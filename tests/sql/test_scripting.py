import pytest

from tests.cases import q, run, unique

CASES = [
    q(
        "DECLARE x INT64 DEFAULT 1; SELECT x",
        1,
        types="INT64",
        xfail="scripting not supported",
    ),
    q("DECLARE x INT64; SELECT x", None, xfail="scripting not supported"),
    q("DECLARE a, b INT64 DEFAULT 2; SELECT a + b", 4, xfail="scripting not supported"),
    q(
        "DECLARE x INT64 DEFAULT (SELECT COUNT(*) FROM UNNEST([1, 2, 3])); SELECT x",
        3,
        xfail="scripting not supported",
    ),
    q("DECLARE x STRING; SET x = 'a'; SELECT x", "a", xfail="scripting not supported"),
    q(
        "DECLARE a INT64; DECLARE b STRING; SET (a, b) = (1, 'x'); SELECT a, b",
        rows=[(1, "x")],
        xfail="scripting not supported",
    ),
    q(
        "DECLARE x INT64; SET x = (SELECT MAX(v) FROM UNNEST([4, 9]) AS v); SELECT x",
        9,
        xfail="scripting not supported",
    ),
    q(
        "DECLARE lim INT64 DEFAULT 2; "
        "SELECT v FROM UNNEST([1, 2, 3]) AS v WHERE v <= lim ORDER BY v",
        rows=[(1,), (2,)],
        xfail="scripting not supported",
    ),
    q("SELECT 1; SELECT 2", 2),
    q(
        "DECLARE x INT64 DEFAULT 1; CREATE TEMP TABLE t AS SELECT x",
        rows=[],
        xfail="scripting not supported",
    ),
    q(
        "DECLARE x INT64 DEFAULT 5; "
        "IF x > 3 THEN SELECT 'big'; ELSEIF x > 1 THEN SELECT 'mid'; "
        "ELSE SELECT 'small'; END IF",
        "big",
        xfail="scripting not supported",
    ),
    q(
        "DECLARE x INT64 DEFAULT 2; "
        "IF x > 3 THEN SELECT 'big'; ELSEIF x > 1 THEN SELECT 'mid'; "
        "ELSE SELECT 'small'; END IF",
        "mid",
        xfail="scripting not supported",
    ),
    q(
        "DECLARE i INT64 DEFAULT 0; WHILE i < 5 DO SET i = i + 1; END WHILE; SELECT i",
        5,
        xfail="scripting not supported",
    ),
    q(
        "DECLARE i INT64 DEFAULT 0; "
        "LOOP SET i = i + 1; IF i >= 3 THEN BREAK; END IF; END LOOP; SELECT i",
        3,
        xfail="scripting not supported",
    ),
    q(
        "DECLARE i INT64 DEFAULT 0; "
        "LOOP SET i = i + 1; IF i >= 3 THEN LEAVE; END IF; END LOOP; SELECT i",
        3,
        xfail="scripting not supported",
    ),
    q(
        "DECLARE i INT64 DEFAULT 0; DECLARE s INT64 DEFAULT 0; "
        "WHILE i < 5 DO SET i = i + 1; IF MOD(i, 2) = 0 THEN CONTINUE; END IF; "
        "SET s = s + i; END WHILE; SELECT s",
        9,
        xfail="scripting not supported",
    ),
    q(
        "DECLARE i INT64 DEFAULT 0; DECLARE s INT64 DEFAULT 0; "
        "WHILE i < 5 DO SET i = i + 1; IF MOD(i, 2) = 0 THEN ITERATE; END IF; "
        "SET s = s + i; END WHILE; SELECT s",
        9,
        xfail="scripting not supported",
    ),
    q(
        "DECLARE i INT64 DEFAULT 0; REPEAT SET i = i + 1; UNTIL i >= 3 END REPEAT; "
        "SELECT i",
        3,
        xfail="scripting not supported",
    ),
    q(
        "DECLARE s INT64 DEFAULT 0; "
        "FOR r IN (SELECT v FROM UNNEST([1, 2, 3]) AS v) DO SET s = s + r.v; END FOR; "
        "SELECT s",
        6,
        xfail="scripting not supported",
    ),
    q(
        "DECLARE s INT64 DEFAULT 0; "
        "FOR r IN (SELECT v FROM UNNEST(ARRAY<INT64>[]) AS v) DO SET s = s + r.v; "
        "END FOR; SELECT s",
        0,
        xfail="scripting not supported",
    ),
    q(
        "DECLARE x INT64 DEFAULT 2; "
        "CASE x WHEN 1 THEN SELECT 'one'; WHEN 2 THEN SELECT 'two'; "
        "ELSE SELECT 'other'; END CASE",
        "two",
        xfail="scripting not supported",
    ),
    q(
        "DECLARE x INT64 DEFAULT 7; "
        "CASE WHEN x < 5 THEN SELECT 'low'; ELSE SELECT 'high'; END CASE",
        "high",
        xfail="scripting not supported",
    ),
    q(
        "BEGIN DECLARE x INT64 DEFAULT 1; SELECT x; END",
        1,
        xfail="scripting not supported",
    ),
    q("BEGIN DECLARE x INT64 DEFAULT 1; END; SELECT x", error="invalidQuery"),
    q("SELECT 1; DECLARE x INT64", error="invalidQuery"),
    q("SET y = 1", error="invalidQuery"),
    q("SELECT 1; RETURN; SELECT 2", 1, xfail="scripting not supported"),
    q(
        "BEGIN SELECT ERROR('boom'); "
        "EXCEPTION WHEN ERROR THEN SELECT @@error.message LIKE '%boom%'; END",
        True,
        xfail="scripting not supported",
    ),
    q(
        "BEGIN RAISE USING MESSAGE = 'nope'; "
        "EXCEPTION WHEN ERROR THEN SELECT @@error.message; END",
        "nope",
        xfail="scripting not supported",
    ),
    q("RAISE USING MESSAGE = 'nope'", error="nope"),
    q(
        "BEGIN EXECUTE IMMEDIATE 'SELECT 1 / 0'; "
        "EXCEPTION WHEN ERROR THEN SELECT 'caught'; END",
        "caught",
        xfail="scripting not supported",
    ),
    q("ASSERT 1 = 1; SELECT 'ok'", "ok", xfail="ASSERT not supported"),
    q("ASSERT 1 = 2 AS 'custom failure'", error="custom failure"),
    q(
        "ASSERT (SELECT COUNT(*) FROM UNNEST([1])) = 2",
        error="Assertion failed",
        xfail="ASSERT not supported",
    ),
    q("EXECUTE IMMEDIATE 'SELECT 1 + 1'", 2, xfail="EXECUTE IMMEDIATE not supported"),
    q(
        "EXECUTE IMMEDIATE 'SELECT ? + ?' USING 1, 2",
        3,
        xfail="EXECUTE IMMEDIATE not supported",
    ),
    q(
        "EXECUTE IMMEDIATE 'SELECT @a * 2' USING 5 AS a",
        10,
        xfail="EXECUTE IMMEDIATE not supported",
    ),
    q(
        "DECLARE x INT64; EXECUTE IMMEDIATE 'SELECT 7' INTO x; SELECT x",
        7,
        xfail="EXECUTE IMMEDIATE not supported",
    ),
    q(
        "SET @@dataset_id = 'abc'; SELECT @@dataset_id",
        "abc",
        xfail="system variables not supported",
    ),
    q(
        "SET @@time_zone = 'Asia/Tokyo'; SELECT @@time_zone",
        "Asia/Tokyo",
        xfail="system variables not supported",
    ),
    q(
        "SELECT @@current_job_id IS NOT NULL",
        True,
        xfail="system variables not supported",
    ),
    q(
        "SELECT @@script.job_id IS NOT NULL",
        True,
        xfail="system variables not supported",
    ),
    q(
        "CREATE TEMP TABLE t AS SELECT v FROM UNNEST([1, 2]) AS v; "
        "UPDATE t SET v = v + 1 WHERE TRUE; SELECT @@row_count",
        2,
        xfail="system variables not supported",
    ),
    q(
        "CREATE TEMP TABLE t AS SELECT 1 AS v; INSERT INTO t VALUES (2); "
        "SELECT SUM(v) FROM t",
        3,
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_scripting(check, case):
    check(case)


@pytest.fixture
def table(bq, dataset):
    table = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table} (v INT64)")
    return table


def count(bq, table) -> int:
    return next(iter(run(bq, f"SELECT COUNT(*) FROM {table}")))[0]


@pytest.mark.xfail(reason="scripting not supported")
def test_statement_type_is_script(bq):
    job = bq.query("DECLARE x INT64 DEFAULT 1; SELECT x")
    assert [tuple(r) for r in job.result()] == [(1,)]
    assert job.statement_type == "SCRIPT"


@pytest.mark.xfail(reason="scripting not supported")
def test_script_child_jobs(bq):
    job = bq.query("SELECT 1; SELECT 2")
    job.result()
    children = list(bq.list_jobs(parent_job=job))
    assert len(children) == 2
    assert {child.statement_type for child in children} == {"SELECT"}


@pytest.mark.xfail(reason="scripting not supported")
def test_for_loop_inserts(bq, table):
    run(
        bq,
        f"FOR r IN (SELECT v FROM UNNEST([1, 2, 3]) AS v) DO INSERT {table} VALUES (r.v); END FOR",
    )
    assert count(bq, table) == 3


def test_transaction_commit(bq, table):
    run(bq, f"BEGIN TRANSACTION; INSERT {table} VALUES (1); COMMIT TRANSACTION")
    assert count(bq, table) == 1


def test_transaction_rollback(bq, table):
    run(bq, f"BEGIN TRANSACTION; INSERT {table} VALUES (1); ROLLBACK TRANSACTION")
    assert count(bq, table) == 0


@pytest.mark.xfail(reason="scripting not supported")
def test_transaction_rolled_back_in_exception_handler(bq, table):
    run(
        bq,
        f"BEGIN BEGIN TRANSACTION; INSERT {table} VALUES (1); SELECT ERROR('x'); "
        "COMMIT TRANSACTION; EXCEPTION WHEN ERROR THEN ROLLBACK TRANSACTION; END",
    )
    assert count(bq, table) == 0


def test_failed_statement_keeps_earlier_statements(bq, table):
    with pytest.raises(Exception):
        run(bq, f"INSERT {table} VALUES (1); SELECT ERROR('x')")
    assert count(bq, table) == 1


@pytest.mark.xfail(reason="EXECUTE IMMEDIATE not supported")
def test_execute_immediate_dml(bq, table):
    run(bq, f"EXECUTE IMMEDIATE 'INSERT {table} VALUES (?)' USING 5")
    assert count(bq, table) == 1
