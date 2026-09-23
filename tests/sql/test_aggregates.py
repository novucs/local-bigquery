import datetime
from decimal import Decimal

import pytest

from tests.cases import q, run


@pytest.fixture(scope="module", autouse=True)
def t(bq, dataset):
    run(
        bq,
        f"""
        CREATE TABLE {dataset.dataset_id}.t (g STRING, v INT64);
        INSERT INTO {dataset.dataset_id}.t (g, v)
        VALUES ('a', 1), ('a', 2), ('b', 3), ('b', NULL), ('c', NULL)
        """,
    )


STATS = "FROM UNNEST([2, 4, 4, 4, 5, 5, 7, 9]) AS x"
PAIRS = "FROM (SELECT 1 AS x, 2 AS y UNION ALL SELECT 2, 4 UNION ALL SELECT 3, 6)"

CASES = [
    q("SELECT COUNT(*) FROM UNNEST([1, 2, NULL]) AS x", 3, types="INT64"),
    q("SELECT COUNT(x) FROM UNNEST([1, 2, NULL]) AS x", 2),
    q("SELECT COUNT(DISTINCT x) FROM UNNEST([1, 1, 2, NULL]) AS x", 2),
    q("SELECT COUNT(*) FROM UNNEST(ARRAY<INT64>[])", 0),
    q(
        "SELECT COUNTIF(x > 1) FROM UNNEST([1, 2, 3, NULL]) AS x",
        2,
        types="INT64",
    ),
    q(
        "SELECT COUNTIF(x > 1) FROM UNNEST(ARRAY<INT64>[]) AS x",
        0,
        xfail="COUNTIF over empty input returns NULL",
    ),
    q(
        "SELECT SUM(x) FROM UNNEST([1, 2, 3]) AS x",
        6,
        types="INT64",
    ),
    q("SELECT SUM(x) FROM UNNEST(ARRAY<INT64>[]) AS x", None),
    q("SELECT SUM(x) FROM UNNEST([CAST(NULL AS INT64)]) AS x", None),
    q("SELECT SUM(x) FROM UNNEST([1.5, 2.5]) AS x", 4.0, types="FLOAT64"),
    q(
        "SELECT SUM(x) FROM UNNEST([NUMERIC '1.1', NUMERIC '2.2']) AS x",
        Decimal("3.3"),
        types="NUMERIC",
        xfail="NUMERIC reported as FLOAT",
    ),
    q("SELECT AVG(x) FROM UNNEST([1, 2]) AS x", 1.5, types="FLOAT64"),
    q(
        "SELECT AVG(x) FROM UNNEST([NUMERIC '1', NUMERIC '2']) AS x",
        Decimal("1.5"),
        types="NUMERIC",
        xfail="NUMERIC reported as FLOAT",
    ),
    q("SELECT AVG(x) FROM UNNEST(ARRAY<INT64>[]) AS x", None),
    q("SELECT MIN(x), MAX(x) FROM UNNEST(['b', 'a', 'c']) AS x", rows=[("a", "c")]),
    q("SELECT MAX(x) FROM UNNEST([1, NULL, 3]) AS x", 3),
    q(
        "SELECT MAX(x) FROM UNNEST([DATE '2020-01-02', DATE '2021-01-01']) AS x",
        datetime.date(2021, 1, 1),
        types="DATE",
    ),
    q("SELECT ANY_VALUE(x) FROM UNNEST([7]) AS x", 7),
    q(
        "SELECT MAX_BY(fruit, price), MIN_BY(fruit, price) "
        "FROM (SELECT 'apple' AS fruit, 3 AS price UNION ALL SELECT 'pear', 5)",
        rows=[("pear", "apple")],
    ),
    q(
        "SELECT ARRAY_AGG(x ORDER BY x) FROM UNNEST([3, 1, 2]) AS x",
        [1, 2, 3],
        types="ARRAY<INT64>",
    ),
    q(
        "SELECT ARRAY_AGG(x ORDER BY x DESC LIMIT 2) FROM UNNEST([3, 1, 2]) AS x",
        [3, 2],
        xfail="ARRAY_AGG LIMIT unsupported",
    ),
    q(
        "SELECT ARRAY_AGG(x IGNORE NULLS ORDER BY x) FROM UNNEST([2, NULL, 1]) AS x",
        [1, 2],
    ),
    q("SELECT ARRAY_AGG(DISTINCT x ORDER BY x) FROM UNNEST([1, 1, 2]) AS x", [1, 2]),
    q(
        "SELECT ARRAY_AGG(x) FROM UNNEST(ARRAY<INT64>[]) AS x",
        [],
    ),
    q(
        "SELECT ARRAY_AGG(x) FROM UNNEST([1, NULL]) AS x",
        error="(?i)null element",
        xfail="NULL array elements not rejected",
    ),
    q(
        "SELECT ARRAY_CONCAT_AGG(a ORDER BY a[OFFSET(0)]) "
        "FROM (SELECT [3] AS a UNION ALL SELECT [1, 2])",
        [1, 2, 3],
    ),
    q("SELECT STRING_AGG(x ORDER BY x) FROM UNNEST(['b', 'a']) AS x", "a,b"),
    q(
        "SELECT STRING_AGG(x, ' | ' ORDER BY x DESC) FROM UNNEST(['a', 'b']) AS x",
        "b | a",
    ),
    q(
        "SELECT STRING_AGG(x, ',' ORDER BY x LIMIT 2) FROM UNNEST(['c', 'a', 'b']) AS x",
        "a,b",
        xfail="STRING_AGG LIMIT unsupported",
    ),
    q(
        "SELECT STRING_AGG(DISTINCT x, ',' ORDER BY x) FROM UNNEST(['a', 'a', 'b']) AS x",
        "a,b",
    ),
    q("SELECT STRING_AGG(x ORDER BY x) FROM UNNEST(['a', NULL, 'b']) AS x", "a,b"),
    q("SELECT STRING_AGG(x) FROM UNNEST(ARRAY<STRING>[]) AS x", None),
    q(
        "SELECT STRING_AGG(x, b'-' ORDER BY x) FROM UNNEST([b'a', b'b']) AS x",
        b"a-b",
        types="BYTES",
        xfail="STRING_AGG over BYTES unsupported",
    ),
    q(
        "SELECT LOGICAL_AND(x), LOGICAL_OR(x) FROM UNNEST([TRUE, FALSE, NULL]) AS x",
        rows=[(False, True)],
    ),
    q("SELECT LOGICAL_AND(x) FROM UNNEST([TRUE, NULL]) AS x", True),
    q(
        "SELECT BIT_AND(x), BIT_OR(x), BIT_XOR(x) FROM UNNEST([12, 10]) AS x",
        rows=[(8, 14, 6)],
    ),
    q(f"SELECT STDDEV_POP(x), VAR_POP(x) {STATS}", rows=[(2.0, 4.0)]),
    q(
        f"SELECT STDDEV_SAMP(x), STDDEV(x) {STATS}",
        rows=[(2.138089935299395, 2.138089935299395)],
    ),
    q(
        f"SELECT VAR_SAMP(x), VARIANCE(x) {STATS}",
        rows=[(4.571428571428571, 4.571428571428571)],
    ),
    q("SELECT VAR_SAMP(x), VAR_POP(x) FROM UNNEST([5]) AS x", rows=[(None, 0.0)]),
    q(f"SELECT CORR(x, y) {PAIRS}", 1.0),
    q(f"SELECT COVAR_POP(x, y), COVAR_SAMP(x, y) {PAIRS}", rows=[(4 / 3, 2.0)]),
    q("SELECT APPROX_COUNT_DISTINCT(x) FROM UNNEST([1, 1, 2, 3]) AS x", 3),
    q(
        "SELECT APPROX_QUANTILES(x, 2) FROM UNNEST([1, 1, 1, 4, 5, 6, 7, 8, 9, 10]) AS x",
        [1, 5, 10],
        xfail="APPROX_QUANTILES picks upper median",
    ),
    q(
        "SELECT APPROX_TOP_COUNT(x, 2) "
        "FROM UNNEST(['apple', 'apple', 'pear', 'pear', 'pear', 'banana']) AS x",
        [{"value": "pear", "count": 3}, {"value": "apple", "count": 2}],
        types="ARRAY<STRUCT<value STRING, count INT64>>",
        xfail="returns values without counts",
    ),
    q(
        "SELECT APPROX_TOP_SUM(x, w, 2) FROM (SELECT 'apple' AS x, 3 AS w UNION ALL "
        "SELECT 'pear', 2 UNION ALL SELECT 'apple', 0 UNION ALL SELECT 'banana', 5 "
        "UNION ALL SELECT 'pear', 4)",
        [{"value": "pear", "sum": 6}, {"value": "banana", "sum": 5}],
        xfail="missing function",
    ),
    q(
        "SELECT HLL_COUNT.EXTRACT(HLL_COUNT.INIT(x)) FROM UNNEST([1, 2, 2, 3]) AS x",
        3,
        xfail="missing function",
    ),
    q(
        "SELECT HLL_COUNT.MERGE(s) FROM ("
        "SELECT HLL_COUNT.INIT(x) AS s FROM UNNEST([1, 2]) AS x UNION ALL "
        "SELECT HLL_COUNT.INIT(x) FROM UNNEST([2, 3]) AS x)",
        3,
        xfail="missing function",
    ),
    q(
        "SELECT g, SUM(v) FROM t GROUP BY g ORDER BY g",
        rows=[("a", 3), ("b", 3), ("c", None)],
    ),
    q(
        "SELECT g, COUNT(*), COUNT(v) FROM t GROUP BY 1 ORDER BY 1",
        rows=[("a", 2, 2), ("b", 2, 1), ("c", 1, 0)],
    ),
    q(
        "SELECT UPPER(g) AS h, COUNT(*) FROM t GROUP BY h ORDER BY h",
        rows=[("A", 2), ("B", 2), ("C", 1)],
    ),
    q(
        "SELECT g, SUM(v) AS s FROM t GROUP BY ALL ORDER BY g",
        rows=[("a", 3), ("b", 3), ("c", None)],
    ),
    q("SELECT g FROM t GROUP BY g HAVING COUNT(v) = 2", "a"),
    q("SELECT g FROM t GROUP BY g HAVING COUNT(*) > 10", rows=[]),
    q(
        "SELECT SUM(CASE WHEN g = 'a' THEN v ELSE 0 END) FROM t",
        3,
    ),
    q("SELECT COUNT(*) FROM t WHERE FALSE", 0),
    q("SELECT COUNT(*) FROM t WHERE FALSE GROUP BY g", rows=[]),
    q(
        "SELECT g, SUM(v) FROM t WHERE g != 'c' GROUP BY ROLLUP (g) ORDER BY g NULLS LAST",
        rows=[("a", 3), ("b", 3), (None, 6)],
    ),
    q(
        "SELECT g, GROUPING(g) FROM t WHERE g != 'c' GROUP BY ROLLUP (g) ORDER BY 2, 1",
        rows=[("a", 0), ("b", 0), (None, 1)],
    ),
    q(
        "SELECT g, COUNT(*) FROM t GROUP BY CUBE (g) ORDER BY g NULLS LAST",
        rows=[("a", 2), ("b", 2), ("c", 1), (None, 5)],
    ),
    q(
        "SELECT g, COUNT(*) FROM t GROUP BY GROUPING SETS ((g), ()) ORDER BY g NULLS LAST",
        rows=[("a", 2), ("b", 2), ("c", 1), (None, 5)],
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_aggregates(check, case):
    check(case)
