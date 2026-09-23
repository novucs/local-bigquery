import datetime

import pytest
from google.cloud import bigquery

from tests.cases import q, run, unique

CASES = [
    q("SELECT [1, 2, 3]", [1, 2, 3], types="ARRAY<INT64>"),
    q("SELECT ARRAY<STRING>['a']", ["a"], types="ARRAY<STRING>"),
    q("SELECT ARRAY<INT64>[]", []),
    q(
        "SELECT CAST(NULL AS ARRAY<INT64>)",
        [],
    ),
    q("SELECT ARRAY(SELECT x * 2 FROM UNNEST([1, 2]) AS x ORDER BY x)", [2, 4]),
    q("SELECT ARRAY(SELECT DISTINCT x FROM UNNEST([3, 1, 3]) AS x ORDER BY x)", [1, 3]),
    q(
        "SELECT [1, 2, 3][OFFSET(0)], [1, 2, 3][ORDINAL(1)], [1, 2, 3][1]",
        rows=[(1, 1, 2)],
    ),
    q("SELECT [1, 2][SAFE_OFFSET(5)], [1, 2][SAFE_ORDINAL(0)]", rows=[(None, None)]),
    q(
        "SELECT [1, 2][OFFSET(5)]",
        error="out of bounds",
    ),
    q(
        "SELECT [1, 2][ORDINAL(0)]",
        error="out of bounds",
    ),
    q("SELECT ARRAY_LENGTH([1, 2, 3]), ARRAY_LENGTH(ARRAY<INT64>[])", rows=[(3, 0)]),
    q("SELECT ARRAY_LENGTH(GENERATE_ARRAY(5, 1))", 0),
    q("SELECT ARRAY_CONCAT([1], [2, 3])", [1, 2, 3]),
    q("SELECT ARRAY_CONCAT(ARRAY<INT64>[], [1])", [1]),
    q("SELECT ARRAY_REVERSE([1, 2, 3])", [3, 2, 1]),
    q("SELECT ARRAY_TO_STRING(['a', NULL, 'b'], ',')", "a,b"),
    q("SELECT ARRAY_TO_STRING(['a', NULL, 'b'], ',', 'N')", "a,N,b"),
    q("SELECT GENERATE_ARRAY(1, 10, 3)", [1, 4, 7, 10]),
    q(
        "SELECT GENERATE_ARRAY(0, 1, 0.5)",
        [0.0, 0.5, 1.0],
        types="ARRAY<FLOAT64>",
    ),
    q(
        "SELECT GENERATE_DATE_ARRAY('2020-02-28', '2020-03-01')",
        [
            datetime.date(2020, 2, 28),
            datetime.date(2020, 2, 29),
            datetime.date(2020, 3, 1),
        ],
        types="ARRAY<DATE>",
    ),
    q(
        "SELECT ARRAY_INCLUDES([1, 2], 2), ARRAY_INCLUDES([1, 2], 3)",
        rows=[(True, False)],
    ),
    q(
        "SELECT ARRAY_FIRST(['a', 'b']), ARRAY_LAST(['a', 'b'])",
        rows=[("a", "b")],
    ),
    q("SELECT ARRAY_FIRST(ARRAY<INT64>[])", error="empty"),
    q(
        "SELECT ARRAY_SLICE([1, 2, 3, 4, 5], 1, 3)",
        [2, 3, 4],
    ),
    q("SELECT ARRAY_SLICE([1, 2, 3, 4, 5], -3, -1)", [3, 4, 5]),
    q("SELECT x FROM UNNEST([3, 1, 2]) AS x ORDER BY x", rows=[(1,), (2,), (3,)]),
    q(
        "SELECT x, o FROM UNNEST(['a', 'b']) AS x WITH OFFSET AS o ORDER BY o",
        rows=[("a", 0), ("b", 1)],
    ),
    q(
        "SELECT a, b FROM UNNEST(ARRAY<STRUCT<a INT64, b STRING>>[(1, 'x'), (2, 'y')]) ORDER BY a",
        rows=[(1, "x"), (2, "y")],
    ),
    q(
        "SELECT * FROM UNNEST(ARRAY<STRUCT<a INT64, b STRING>>[(1, 'x')])",
        rows=[(1, "x")],
    ),
    q("SELECT COUNT(*) FROM UNNEST(ARRAY<INT64>[])", 0),
    q("SELECT SUM(x) FROM UNNEST(ARRAY<INT64>[]) AS x", None),
    q("SELECT COUNT(*) FROM UNNEST(CAST(NULL AS ARRAY<INT64>))", 0),
    q(
        "WITH t AS (SELECT 1 AS id, [10, 20] AS xs UNION ALL SELECT 2, [30]) "
        "SELECT id, x FROM t, UNNEST(t.xs) AS x ORDER BY x",
        rows=[(1, 10), (1, 20), (2, 30)],
    ),
    q(
        "WITH t AS (SELECT 1 AS id, ARRAY<INT64>[] AS xs) "
        "SELECT id, x FROM t LEFT JOIN UNNEST(t.xs) AS x",
        rows=[(1, None)],
    ),
    q("SELECT 2 IN UNNEST([1, 2, 3]), 5 IN UNNEST([1, 2, 3])", rows=[(True, False)]),
    q(
        "SELECT [1, NULL]",
        error="NULL element|null element",
    ),
    q("SELECT [1] = [1]", error="not defined"),
    q(
        "SELECT [[1]]",
        error="Cannot construct array",
    ),
    q(
        "SELECT [STRUCT('a' AS k, [1, 2] AS v)]",
        [{"k": "a", "v": [1, 2]}],
        types="ARRAY<STRUCT<k STRING, v ARRAY<INT64>>>",
    ),
    q(
        "SELECT STRUCT(1 AS a, 'x' AS b)",
        {"a": 1, "b": "x"},
        types="STRUCT<a INT64, b STRING>",
    ),
    q("SELECT STRUCT<a INT64, b STRING>(1, 'x')", {"a": 1, "b": "x"}),
    q(
        "SELECT STRUCT(1, 'x')",
        {"_field_1": 1, "_field_2": "x"},
        types="STRUCT<_field_1 INT64, _field_2 STRING>",
    ),
    q(
        "SELECT (1, 'x')",
        {"_field_1": 1, "_field_2": "x"},
    ),
    q("SELECT STRUCT(1 AS a).a", 1),
    q("SELECT s.b.c FROM (SELECT STRUCT(STRUCT(5 AS c) AS b) AS s)", 5),
    q("SELECT STRUCT(ARRAY<INT64>[] AS xs)", {"xs": []}),
    q("SELECT STRUCT(CAST(NULL AS STRING) AS a, '' AS b)", {"a": None, "b": ""}),
    q(
        "WITH t AS (SELECT STRUCT(1 AS a) AS s UNION ALL SELECT STRUCT(2)) "
        "SELECT s.a FROM t WHERE s.a > 1",
        2,
    ),
    q("SELECT STRUCT(1 AS a) = STRUCT(1 AS a)", True),
    q(
        "SELECT STRUCT(1, 2) < STRUCT(1, 3)",
        error="not defined|No matching signature",
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_arrays_structs(check, case):
    check(case)


def test_repeated_record_round_trip(bq, dataset):
    table = bq.create_table(
        bigquery.Table(
            dataset.table(unique("nested")),
            schema=[
                bigquery.SchemaField("id", "INTEGER", "REQUIRED"),
                bigquery.SchemaField(
                    "nested",
                    "RECORD",
                    "REPEATED",
                    fields=[bigquery.SchemaField("item", "STRING")],
                ),
            ],
        )
    )
    rows = [{"id": 1, "nested": [{"item": "a"}, {"item": "b"}, {"item": None}]}]
    assert bq.insert_rows(table, rows) == []
    result = run(bq, f"SELECT * FROM `{table}`")
    assert [dict(row.items()) for row in result] == rows
