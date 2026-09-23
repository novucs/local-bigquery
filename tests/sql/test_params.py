import datetime
from decimal import Decimal

import pytest
from google.cloud import bigquery
from google.cloud.bigquery import ArrayQueryParameter as Array
from google.cloud.bigquery import RangeQueryParameter as Range
from google.cloud.bigquery import ScalarQueryParameter as Scalar
from google.cloud.bigquery import StructQueryParameter as Struct

from tests.cases import q, run, unique

UTC = datetime.timezone.utc
SCALARS = [
    ("STRING", "example"),
    ("INT64", 123),
    ("FLOAT64", 3.14),
    ("NUMERIC", Decimal("123.45")),
    ("BIGNUMERIC", Decimal("12345678901234567890.123456789")),
    ("BOOL", True),
    ("BYTES", b"bytes"),
    ("DATE", datetime.date(2025, 4, 10)),
    ("DATETIME", datetime.datetime(2025, 4, 10, 11, 30)),
    ("TIME", datetime.time(11, 30)),
    ("TIMESTAMP", datetime.datetime(2025, 4, 10, 11, 30, tzinfo=UTC)),
]


CASES = [
    *(
        q(
            f"SELECT @{t.lower()}",
            v,
            types=t,
            params=[Scalar(t.lower(), t, v)],
        )
        for t, v in SCALARS
    ),
    *(
        q(
            f"SELECT @{t.lower()}_array",
            [v, v],
            types=f"ARRAY<{t}>",
            params=[Array(f"{t.lower()}_array", t, [v, v])],
        )
        for t, v in SCALARS
    ),
    *(
        q(
            f"SELECT @{t.lower()}_null IS NULL",
            True,
            params=[Scalar(f"{t.lower()}_null", t, None)],
        )
        for t, _ in SCALARS
    ),
    q(
        "SELECT @ts",
        datetime.datetime(2025, 4, 10, 11, 0, tzinfo=UTC),
        params=[Scalar("ts", "TIMESTAMP", "2025-04-10 11:00:00+00:00")],
    ),
    q(
        "SELECT x FROM UNNEST(['one', 'two', 'three']) AS x WHERE x = @arg",
        "one",
        params=[Scalar("arg", "STRING", "one")],
    ),
    q(
        "SELECT @user",
        {"id": "123", "name": "John", "scores": ["85", "90"]},
        types="STRUCT<id STRING, name STRING, scores ARRAY<STRING>>",
        params=[
            Struct(
                "user",
                Scalar("id", "STRING", "123"),
                Scalar("name", "STRING", "John"),
                Array("scores", "STRING", ["85", "90"]),
            )
        ],
    ),
    q(
        "SELECT @s.a, @s.b",
        rows=[("x", 42)],
        params=[Struct("s", Scalar("a", "STRING", "x"), Scalar("b", "INT64", 42))],
    ),
    q(
        "SELECT @rows",
        [{"a": "x", "b": 100}, {"a": "y", "b": 200}],
        types="ARRAY<STRUCT<a STRING, b INT64>>",
        params=[
            Array(
                "rows",
                "RECORD",
                [
                    Struct(None, Scalar("a", "STRING", "x"), Scalar("b", "INT64", 100)),
                    Struct(None, Scalar("a", "STRING", "y"), Scalar("b", "INT64", 200)),
                ],
            )
        ],
    ),
    q(
        "SELECT ?, ?, ?",
        rows=[(1, "a", True)],
        params=[
            Scalar(None, "INT64", 1),
            Scalar(None, "STRING", "a"),
            Scalar(None, "BOOL", True),
        ],
    ),
    q(
        "SELECT ? IS NULL",
        True,
        params=[Scalar(None, "STRING", None)],
    ),
    q(
        "SELECT SUM(x) FROM UNNEST(?) AS x",
        6,
        params=[Array(None, "INT64", [1, 2, 3])],
    ),
    q(
        "SELECT l FROM UNNEST([1, 2, 3]) AS l JOIN UNNEST([2, 3]) AS r ON l = r AND l > @min",
        3,
        params=[Scalar("min", "INT64", 2)],
    ),
    q("SELECT @n / 2", 2.5, types="FLOAT64", params=[Scalar("n", "INT64", 5)]),
    q(
        "SELECT x FROM UNNEST([1, 2, 3]) AS x ORDER BY x LIMIT @n",
        rows=[(1,), (2,)],
        params=[Scalar("n", "INT64", 2)],
    ),
    q(
        "SELECT RANGE_START(@r), RANGE_END(@r), RANGE_CONTAINS(@r, DATE '2024-01-02')",
        rows=[(datetime.date(2024, 1, 1), datetime.date(2024, 2, 1), True)],
        params=[
            Range("DATE", datetime.date(2024, 1, 1), datetime.date(2024, 2, 1), "r")
        ],
    ),
    q(
        "SELECT @r",
        {"start": datetime.date(2024, 1, 1), "end": None},
        types="RANGE",
        params=[Range("DATE", datetime.date(2024, 1, 1), name="r")],
    ),
    q(
        "SELECT RANGE_START(?), RANGE_END(?)",
        rows=[(datetime.datetime(2024, 1, 1, 10, 30), None)],
        params=[
            Range("DATETIME", datetime.datetime(2024, 1, 1, 10, 30)),
            Range("DATETIME", datetime.datetime(2024, 1, 1, 10, 30)),
        ],
    ),
    q(
        "SELECT RANGE_START(@r) IS NULL, RANGE_END(@r)",
        rows=[(True, datetime.datetime(2024, 1, 1, tzinfo=UTC))],
        params=[
            Range("TIMESTAMP", end=datetime.datetime(2024, 1, 1, tzinfo=UTC), name="r")
        ],
        types=("BOOL", "TIMESTAMP"),
    ),
    q("SELECT 1", 1, params=[Scalar("unused", "INT64", 1)]),
    q("SELECT @missing", error="missing"),
    q(
        "SELECT @s + 1",
        error="No matching signature",
        params=[Scalar("s", "STRING", "a")],
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_params(check, case):
    check(case)


def test_params_in_dml(bq, dataset):
    table = bq.create_table(
        bigquery.Table(
            dataset.table(unique("params")),
            schema=[
                bigquery.SchemaField("name", "STRING"),
                bigquery.SchemaField("n", "INTEGER"),
            ],
        )
    )
    config = bigquery.QueryJobConfig(
        query_parameters=[Scalar("name", "STRING", "a"), Scalar("n", "INT64", 7)]
    )
    inserted = run(bq, f"INSERT INTO `{table}` (name, n) VALUES (@name, @n)", config)
    assert inserted.num_dml_affected_rows == 1
    rows = run(bq, f"SELECT name, n FROM `{table}` WHERE n = @n", config)
    assert [tuple(row.values()) for row in rows] == [("a", 7)]
