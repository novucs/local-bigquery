import datetime
from decimal import Decimal

import pytest
from dateutil.relativedelta import relativedelta

from tests.cases import q, run

UTC = datetime.timezone.utc
INT64_MAX = 9223372036854775807
INT64_MIN = -9223372036854775808

CASES = [
    q("SELECT 1, -5", rows=[(1, -5)], types=("INT64", "INT64")),
    q("SELECT 1.5, 1e3", rows=[(1.5, 1000.0)], types=("FLOAT64", "FLOAT64")),
    q("SELECT TRUE, FALSE", rows=[(True, False)], types=("BOOL", "BOOL")),
    q("SELECT 'a'", "a", types="STRING"),
    q(
        r"SELECT b'\x00\xff'",
        b"\x00\xff",
        types="BYTES",
        xfail="byte escapes fail to parse",
    ),
    q("SELECT DATE '2020-02-29'", datetime.date(2020, 2, 29), types="DATE"),
    q("SELECT TIME '12:34:56.789'", datetime.time(12, 34, 56, 789000), types="TIME"),
    q(
        "SELECT DATETIME '2020-01-02 03:04:05.123456'",
        datetime.datetime(2020, 1, 2, 3, 4, 5, 123456),
        types="DATETIME",
    ),
    q(
        "SELECT DATETIME '2020-07-01 00:00:00'",
        datetime.datetime(2020, 7, 1),
        types="DATETIME",
    ),
    q(
        "SELECT TIMESTAMP '2020-01-01 00:00:00+00'",
        datetime.datetime(2020, 1, 1, tzinfo=UTC),
        types="TIMESTAMP",
    ),
    q(
        "SELECT TIMESTAMP '2020-07-01 00:00:00'",
        datetime.datetime(2020, 7, 1, tzinfo=UTC),
    ),
    q(
        "SELECT TIMESTAMP '2020-01-01 00:00:00 America/Los_Angeles'",
        datetime.datetime(2020, 1, 1, 8, tzinfo=UTC),
    ),
    q(
        "SELECT NUMERIC '123.456'",
        Decimal("123.456"),
        types="NUMERIC",
    ),
    q(
        "SELECT BIGNUMERIC '0.12345678901234567890123456789012345678'",
        Decimal("0.12345678901234567890123456789012345678"),
        types="BIGNUMERIC",
        xfail="BIGNUMERIC mapped to DECIMAL(38,5)",
    ),
    q(
        "SELECT BIGNUMERIC '1e40'",
        Decimal("1e40"),
        types="BIGNUMERIC",
        xfail="BIGNUMERIC mapped to DECIMAL(38,5)",
    ),
    q('SELECT JSON \'{"a": [1, "x"]}\'', {"a": [1, "x"]}, types="JSON"),
    q(
        "SELECT ST_GEOGPOINT(1, 2)",
        "POINT(1 2)",
        types="GEOGRAPHY",
        xfail="GEOGRAPHY unsupported",
    ),
    q("SELECT NULL", None, types="INT64"),
    q("SELECT CAST(NULL AS STRING)", None, types="STRING"),
    q(f"SELECT {INT64_MAX}, {INT64_MIN}", rows=[(INT64_MAX, INT64_MIN)]),
    q(
        f"SELECT {INT64_MAX + 1}",
        error="invalidQuery",
    ),
    q(
        "SELECT NUMERIC '99999999999999999999999999999.999999999'",
        Decimal("99999999999999999999999999999.999999999"),
        xfail="NUMERIC mapped to DECIMAL(18,3)",
    ),
    q(
        "SELECT DATE '0001-01-01', DATE '9999-12-31'",
        rows=[(datetime.date(1, 1, 1), datetime.date(9999, 12, 31))],
    ),
    q(
        "SELECT TIMESTAMP '9999-12-31 23:59:59.999999+00'",
        datetime.datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
    ),
    q(
        "SELECT CAST('NaN' AS FLOAT64), CAST('inf' AS FLOAT64), CAST('-inf' AS FLOAT64)",
        rows=[(float("nan"), float("inf"), float("-inf"))],
    ),
    q("SELECT -0.0 = 0.0", True),
    q(
        "SELECT INTERVAL 1 DAY",
        relativedelta(days=1),
        types="INTERVAL",
    ),
    q(
        "SELECT INTERVAL '1-2' YEAR TO MONTH",
        relativedelta(years=1, months=2),
    ),
    q(
        "SELECT INTERVAL '1 6' DAY TO HOUR",
        relativedelta(days=1, hours=6),
    ),
    q(
        "SELECT INTERVAL -3 MINUTE",
        relativedelta(minutes=-3),
        xfail="INTERVAL results crash encoder",
    ),
    q(
        "SELECT INTERVAL 1 DAY - INTERVAL 2 HOUR",
        relativedelta(days=1, hours=-2),
    ),
    q(
        "SELECT MAKE_INTERVAL(1, 2, 3)",
        relativedelta(years=1, months=2, days=3),
    ),
    q(
        "SELECT JUSTIFY_DAYS(INTERVAL 35 DAY)",
        relativedelta(months=1, days=5),
    ),
    q(
        "SELECT JUSTIFY_HOURS(INTERVAL 29 HOUR)",
        relativedelta(days=1, hours=5),
    ),
    q(
        "SELECT EXTRACT(HOUR FROM INTERVAL '1 6' DAY TO HOUR)",
        6,
    ),
    q(
        "SELECT DATE '2020-01-31' + INTERVAL 1 MONTH",
        datetime.datetime(2020, 2, 29),
        types="DATETIME",
    ),
    q(
        "SELECT TIMESTAMP '2020-01-01 00:00:00+00' + INTERVAL 90 MINUTE",
        datetime.datetime(2020, 1, 1, 1, 30, tzinfo=UTC),
        types="TIMESTAMP",
    ),
    q(
        "SELECT RANGE<DATE> '[2020-01-01, 2020-02-01)'",
        {"start": datetime.date(2020, 1, 1), "end": datetime.date(2020, 2, 1)},
        types="RANGE",
        xfail="RANGE unsupported",
    ),
    q(
        "SELECT RANGE<DATE> '[UNBOUNDED, 2020-02-01)'",
        {"start": None, "end": datetime.date(2020, 2, 1)},
        xfail="RANGE unsupported",
    ),
    q(
        "SELECT RANGE(DATE '2020-01-01', NULL)",
        {"start": datetime.date(2020, 1, 1), "end": None},
        xfail="RANGE unsupported",
    ),
    q(
        "SELECT RANGE_START(RANGE<DATE> '[2020-01-01, 2020-02-01)')",
        datetime.date(2020, 1, 1),
        xfail="RANGE unsupported",
    ),
    q(
        "SELECT RANGE_CONTAINS(RANGE<DATE> '[2020-01-01, 2020-02-01)', DATE '2020-02-01')",
        False,
        xfail="RANGE unsupported",
    ),
    q(
        "SELECT RANGE_OVERLAPS(RANGE<DATE> '[2020-01-01, 2020-02-01)', "
        "RANGE<DATE> '[2020-01-15, 2020-03-01)')",
        True,
        xfail="RANGE unsupported",
    ),
    q("SELECT CAST('123' AS INT64)", 123),
    q("SELECT CAST('abc' AS INT64)", error="invalidQuery"),
    q("SELECT SAFE_CAST('abc' AS INT64)", None),
    q("SELECT SAFE_CAST(NULL AS INT64)", None),
    q("SELECT CAST(1.5 AS INT64), CAST(-1.5 AS INT64)", rows=[(2, -2)]),
    q("SELECT CAST(2.5 AS INT64)", 3, xfail="FLOAT64 to INT64 rounds half to even"),
    q("SELECT CAST(TRUE AS INT64), CAST(0 AS BOOL)", rows=[(1, False)]),
    q("SELECT CAST('true' AS BOOL)", True),
    q("SELECT CAST('2020-01-02' AS DATE)", datetime.date(2020, 1, 2)),
    q("SELECT CAST('2020-13-01' AS DATE)", error="invalidQuery"),
    q("SELECT SAFE_CAST('2020-13-01' AS DATE)", None),
    q(
        "SELECT CAST(DATE '2020-01-02' AS TIMESTAMP)",
        datetime.datetime(2020, 1, 2, tzinfo=UTC),
    ),
    q(
        "SELECT CAST(TIMESTAMP '2020-01-01 23:00:00+00' AS DATE)",
        datetime.date(2020, 1, 1),
    ),
    q(
        "SELECT CAST(DATETIME '2020-01-01 12:00:00' AS STRING)",
        "2020-01-01 12:00:00",
    ),
    q(
        "SELECT CAST(TIMESTAMP '2020-01-01 12:00:00+00' AS STRING)",
        "2020-01-01 12:00:00+00",
    ),
    q("SELECT CAST(b'abc' AS STRING), CAST('abc' AS BYTES)", rows=[("abc", b"abc")]),
    q(
        "SELECT CAST('1.5' AS NUMERIC)",
        Decimal("1.5"),
        types="NUMERIC",
    ),
    q(
        "SELECT CAST('1.0000000005' AS NUMERIC)",
        Decimal("1.000000001"),
        xfail="NUMERIC mapped to DECIMAL(18,3)",
    ),
    q(
        "SELECT CAST('1.005' AS NUMERIC(10, 2))",
        Decimal("1.01"),
        types="NUMERIC",
    ),
    q("SELECT CAST('1e30' AS NUMERIC)", error="invalidQuery"),
    q(
        "SELECT PARSE_NUMERIC('123.45')",
        Decimal("123.45"),
        types="NUMERIC",
        xfail="missing function",
    ),
    q(
        "SELECT PARSE_BIGNUMERIC('1.5')",
        Decimal("1.5"),
        types="BIGNUMERIC",
        xfail="missing function",
    ),
    q(
        "SELECT NUMERIC '1' / 3",
        Decimal("0.333333333"),
        types="NUMERIC",
        xfail="NUMERIC reported as FLOAT",
    ),
    q(
        "SELECT CAST(1.1 AS NUMERIC) * 3",
        Decimal("3.3"),
        types="NUMERIC",
    ),
    q(
        "SELECT NUMERIC '1.5' + 1",
        Decimal("2.5"),
        types="NUMERIC",
    ),
    q("SELECT NUMERIC '1.5' + 1.0", 2.5, types="FLOAT64"),
    q("SELECT 1 + 1.5", 2.5, types="FLOAT64"),
    q("SELECT IF(TRUE, 1, 2.5)", 1.0, types="FLOAT64"),
    q("SELECT [1, 2.5]", [1.0, 2.5], types="ARRAY<FLOAT64>"),
    q("SELECT 'a' + 1", error="invalidQuery"),
    q(
        "SELECT SUM(x) FROM UNNEST([1, 2]) AS x",
        3,
        types="INT64",
    ),
    q("SELECT COUNT(*) FROM UNNEST([1, 2])", 2, types="INT64"),
    q("SELECT AVG(x) FROM UNNEST([1, 2]) AS x", 1.5, types="FLOAT64"),
    q(
        "SELECT SUM(x) FROM UNNEST([NUMERIC '1.5']) AS x",
        Decimal("1.5"),
        types="NUMERIC",
        xfail="NUMERIC reported as FLOAT",
    ),
    q("SELECT CURRENT_DATE()", types="DATE"),
    q("SELECT CURRENT_DATETIME()", types="DATETIME"),
    q("SELECT CURRENT_TIMESTAMP()", types="TIMESTAMP"),
    q("SELECT CURRENT_TIME()", types="TIME"),
    q(
        "SELECT STRUCT(1 AS a, 'x' AS b)",
        {"a": 1, "b": "x"},
        types="STRUCT<a INT64, b STRING>",
    ),
    q("SELECT STRUCT<a INT64>(1)", {"a": 1}, types="STRUCT<a INT64>"),
    q(
        "SELECT STRUCT(1, 'x')",
        {"_field_1": 1, "_field_2": "x"},
        types="STRUCT<_field_1 INT64, _field_2 STRING>",
        xfail="anonymous struct fields not named _field_N",
    ),
    q(
        "SELECT [STRUCT(1 AS x)]",
        [{"x": 1}],
        types="ARRAY<STRUCT<x INT64>>",
    ),
    q(
        "SELECT STRUCT([1, 2] AS xs)",
        {"xs": [1, 2]},
        types="STRUCT<xs ARRAY<INT64>>",
    ),
    q("SELECT ARRAY<STRING>[]", [], types="ARRAY<STRING>"),
    q("SELECT [[1]]", error="invalidQuery", xfail="nested arrays accepted"),
]


@pytest.mark.parametrize("case", CASES)
def test_types(check, case):
    check(case)


@pytest.mark.parametrize(
    "sql, names",
    [
        ("SELECT 1, 'a'", ["f0_", "f1_"]),
        ("SELECT 1 AS a, 2", ["a", "f0_"]),
        ("SELECT x + 1 FROM (SELECT 1 AS x)", ["f0_"]),
        ("SELECT COUNT(*) FROM UNNEST([1])", ["f0_"]),
        ("SELECT x FROM (SELECT 1 AS x)", ["x"]),
        ("SELECT s.a FROM (SELECT STRUCT(1 AS a) AS s)", ["a"]),
    ],
)
def test_column_names(bq, sql, names):
    assert [field.name for field in run(bq, sql).schema] == names
