import pytest

from tests.cases import q, run


@pytest.fixture(scope="module", autouse=True)
def scores(bq, dataset):
    run(
        bq,
        f"""
        CREATE TABLE {dataset.dataset_id}.scores (id INT64, g STRING, v INT64);
        INSERT INTO {dataset.dataset_id}.scores (id, g, v)
        VALUES (1, 'a', 10), (2, 'a', 20), (3, 'a', 20), (4, 'a', 30),
               (5, 'b', 5), (6, 'b', NULL)
        """,
    )


CASES = [
    q(
        "SELECT id, ROW_NUMBER() OVER (ORDER BY id DESC) FROM scores ORDER BY id",
        rows=[(1, 6), (2, 5), (3, 4), (4, 3), (5, 2), (6, 1)],
        types=("INT64", "INT64"),
    ),
    q(
        "SELECT id, RANK() OVER w, DENSE_RANK() OVER w FROM scores "
        "WINDOW w AS (PARTITION BY g ORDER BY v) ORDER BY id",
        rows=[(1, 1, 1), (2, 2, 2), (3, 2, 2), (4, 4, 3), (5, 2, 2), (6, 1, 1)],
    ),
    q(
        "SELECT id, PERCENT_RANK() OVER (ORDER BY v), CUME_DIST() OVER (ORDER BY v) "
        "FROM scores WHERE g = 'a' ORDER BY id",
        rows=[(1, 0.0, 0.25), (2, 1 / 3, 0.75), (3, 1 / 3, 0.75), (4, 1.0, 1.0)],
        types=("INT64", "FLOAT64", "FLOAT64"),
    ),
    q(
        "SELECT id, NTILE(2) OVER (ORDER BY id) FROM scores ORDER BY id",
        rows=[(1, 1), (2, 1), (3, 1), (4, 2), (5, 2), (6, 2)],
    ),
    q(
        "SELECT LAG(v) OVER (ORDER BY id) FROM scores WHERE g = 'a' ORDER BY id",
        rows=[(None,), (10,), (20,), (20,)],
    ),
    q(
        "SELECT LAG(v, 1, -1) OVER (ORDER BY id) FROM scores WHERE g = 'a' ORDER BY id",
        rows=[(-1,), (10,), (20,), (20,)],
    ),
    q(
        "SELECT LEAD(v, 2) OVER (ORDER BY id) FROM scores WHERE g = 'a' ORDER BY id",
        rows=[(20,), (30,), (None,), (None,)],
    ),
    q(
        "SELECT id, FIRST_VALUE(v) OVER (PARTITION BY g ORDER BY id) FROM scores ORDER BY id",
        rows=[(1, 10), (2, 10), (3, 10), (4, 10), (5, 5), (6, 5)],
    ),
    q(
        "SELECT LAST_VALUE(v) OVER (ORDER BY id) FROM scores WHERE g = 'a' ORDER BY id",
        rows=[(10,), (20,), (20,), (30,)],
    ),
    q(
        "SELECT LAST_VALUE(v) OVER (ORDER BY id "
        "ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) "
        "FROM scores WHERE g = 'a' ORDER BY id",
        rows=[(30,), (30,), (30,), (30,)],
    ),
    q(
        "SELECT NTH_VALUE(v, 2) OVER (ORDER BY id "
        "ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) "
        "FROM scores WHERE g = 'a' ORDER BY id",
        rows=[(20,), (20,), (20,), (20,)],
    ),
    q(
        "SELECT id, FIRST_VALUE(v IGNORE NULLS) OVER (ORDER BY id DESC) "
        "FROM scores WHERE g = 'b' ORDER BY id",
        rows=[(5, 5), (6, None)],
    ),
    q(
        "SELECT id, LAST_VALUE(v IGNORE NULLS) OVER (ORDER BY id) "
        "FROM scores WHERE g = 'b' ORDER BY id",
        rows=[(5, 5), (6, 5)],
    ),
    q(
        "SELECT id, SUM(v) OVER (PARTITION BY g) FROM scores ORDER BY id",
        rows=[(1, 80), (2, 80), (3, 80), (4, 80), (5, 5), (6, 5)],
        xfail="SUM of INT64 reported as INT128",
    ),
    q(
        "SELECT COUNT(*) OVER (), COUNT(v) OVER () FROM scores LIMIT 1",
        rows=[(6, 5)],
    ),
    q(
        "SELECT SUM(v) OVER (ORDER BY id ROWS UNBOUNDED PRECEDING) "
        "FROM scores WHERE g = 'a' ORDER BY id",
        rows=[(10,), (30,), (50,), (80,)],
        xfail="SUM of INT64 reported as INT128",
    ),
    q(
        "SELECT id, SUM(v) OVER (ORDER BY v) FROM scores WHERE g = 'a' ORDER BY id",
        rows=[(1, 10), (2, 50), (3, 50), (4, 80)],
        xfail="SUM of INT64 reported as INT128",
    ),
    q(
        "SELECT AVG(v) OVER (ORDER BY id ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING) "
        "FROM scores WHERE g = 'a' ORDER BY id",
        rows=[(15.0,), (50 / 3,), (70 / 3,), (25.0,)],
    ),
    q(
        "SELECT id, COUNT(*) OVER (ORDER BY v RANGE BETWEEN 10 PRECEDING AND CURRENT ROW) "
        "FROM scores WHERE g = 'a' ORDER BY id",
        rows=[(1, 1), (2, 3), (3, 3), (4, 3)],
    ),
    q(
        "SELECT id, SUM(v) OVER w FROM scores WHERE g = 'a' "
        "WINDOW w AS (ORDER BY id) ORDER BY id",
        rows=[(1, 10), (2, 30), (3, 50), (4, 80)],
        xfail="SUM of INT64 reported as INT128",
    ),
    q(
        "SELECT id FROM scores WHERE TRUE "
        "QUALIFY ROW_NUMBER() OVER (PARTITION BY g ORDER BY v DESC) = 1 ORDER BY id",
        rows=[(4,), (5,)],
    ),
    q(
        "SELECT g, v FROM (SELECT g, v, ROW_NUMBER() OVER (PARTITION BY g ORDER BY id) AS n "
        "FROM scores) WHERE n = 1 ORDER BY g",
        rows=[("a", 10), ("b", 5)],
    ),
    q(
        "SELECT g, RANK() OVER (ORDER BY SUM(v) DESC) FROM scores GROUP BY g ORDER BY g",
        rows=[("a", 1), ("b", 2)],
    ),
    q(
        "SELECT DISTINCT PERCENTILE_CONT(v, 0.5) OVER (), PERCENTILE_CONT(v, 0.25) OVER () "
        "FROM scores WHERE g = 'a'",
        rows=[(20.0, 17.5)],
        types=("FLOAT64", "FLOAT64"),
    ),
    q(
        "SELECT DISTINCT PERCENTILE_DISC(v, 0.5) OVER () FROM scores WHERE g = 'a'",
        20,
        types="INT64",
    ),
    q(
        "SELECT DISTINCT PERCENTILE_CONT(v, 0.5) OVER () FROM scores WHERE g = 'b'",
        5.0,
    ),
    q("SELECT ROW_NUMBER() OVER () FROM scores WHERE FALSE", rows=[]),
]


@pytest.mark.parametrize("case", CASES)
def test_windows(check, case):
    check(case)
