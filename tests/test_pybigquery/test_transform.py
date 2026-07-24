import datetime

import duckdb
import pytest
import sqlglot

from local_bigquery.models import QueryParameter, TableFieldSchema
from local_bigquery.transform import (
    bigquery_params_to_duckdb_params,
    bigquery_schema_to_duckdb_sql,
    duckdb_fields_to_bigquery_fields,
    duckdb_values_to_bigquery_values,
    table_expr,
)


def test_bigquery_params_to_duckdb_params():
    bigquery_params = [
        {
            "parameterType": {"type": "STRING"},
            "parameterValue": {"value": "unnamed parameter"},
        },
        {
            "name": "string_param",
            "parameterType": {"type": "STRING"},
            "parameterValue": {"value": "example string"},
        },
        {
            "name": "int64_param",
            "parameterType": {"type": "INT64"},
            "parameterValue": {"value": "123"},
        },
        {
            "name": "float64_param",
            "parameterType": {"type": "FLOAT64"},
            "parameterValue": {"value": 3.14},
        },
        {
            "name": "numeric_param",
            "parameterType": {"type": "NUMERIC"},
            "parameterValue": {"value": "123.45"},
        },
        {
            "name": "bignumeric_param",
            "parameterType": {"type": "BIGNUMERIC"},
            "parameterValue": {"value": "12345678901234567890.123456789"},
        },
        {
            "name": "boolean_param",
            "parameterType": {"type": "BOOL"},
            "parameterValue": {"value": "true"},
        },
        {
            "name": "bytes_param",
            "parameterType": {"type": "BYTES"},
            "parameterValue": {"value": "ZXhhbXBsZSBieXRlcw=="},
        },
        {
            "name": "date_param",
            "parameterType": {"type": "DATE"},
            "parameterValue": {"value": "2025-04-10"},
        },
        {
            "name": "datetime_param",
            "parameterType": {"type": "DATETIME"},
            "parameterValue": {"value": "2025-04-10 11:00:00"},
        },
        {
            "name": "time_param",
            "parameterType": {"type": "TIME"},
            "parameterValue": {"value": "11:00:00"},
        },
        {
            "name": "timestamp_param",
            "parameterType": {"type": "TIMESTAMP"},
            "parameterValue": {"value": "2025-04-10 11:00:00+00:00"},
        },
        {
            "name": "array_string_param",
            "parameterType": {"arrayType": {"type": "STRING"}, "type": "ARRAY"},
            "parameterValue": {
                "arrayValues": [{"value": "a"}, {"value": "b"}, {"value": "c"}]
            },
        },
        {
            "name": "array_int64_param",
            "parameterType": {"arrayType": {"type": "INT64"}, "type": "ARRAY"},
            "parameterValue": {
                "arrayValues": [{"value": "1"}, {"value": "2"}, {"value": "3"}]
            },
        },
        {
            "name": "array_float64_param",
            "parameterType": {"arrayType": {"type": "FLOAT64"}, "type": "ARRAY"},
            "parameterValue": {
                "arrayValues": [{"value": 1.1}, {"value": 2.2}, {"value": 3.3}]
            },
        },
        {
            "name": "array_numeric_param",
            "parameterType": {"arrayType": {"type": "NUMERIC"}, "type": "ARRAY"},
            "parameterValue": {
                "arrayValues": [{"value": "1.1"}, {"value": "2.2"}, {"value": "3.3"}]
            },
        },
        {
            "name": "array_bignumeric_param",
            "parameterType": {"arrayType": {"type": "BIGNUMERIC"}, "type": "ARRAY"},
            "parameterValue": {
                "arrayValues": [
                    {"value": "123.1"},
                    {"value": "456.2"},
                    {"value": "789.3"},
                ]
            },
        },
        {
            "name": "array_boolean_param",
            "parameterType": {"arrayType": {"type": "BOOL"}, "type": "ARRAY"},
            "parameterValue": {
                "arrayValues": [
                    {"value": "true"},
                    {"value": "false"},
                    {"value": "true"},
                ]
            },
        },
        {
            "name": "array_bytes_param",
            "parameterType": {"arrayType": {"type": "BYTES"}, "type": "ARRAY"},
            "parameterValue": {
                "arrayValues": [{"value": "Ynl0ZTE="}, {"value": "Ynl0ZTI="}]
            },
        },
        {
            "name": "array_date_param",
            "parameterType": {"arrayType": {"type": "DATE"}, "type": "ARRAY"},
            "parameterValue": {
                "arrayValues": [{"value": "2025-04-01"}, {"value": "2025-04-05"}]
            },
        },
        {
            "name": "array_datetime_param",
            "parameterType": {"arrayType": {"type": "DATETIME"}, "type": "ARRAY"},
            "parameterValue": {
                "arrayValues": [
                    {"value": "2025-04-10 10:00:00"},
                    {"value": "2025-04-10 12:00:00"},
                ]
            },
        },
        {
            "name": "array_time_param",
            "parameterType": {"arrayType": {"type": "TIME"}, "type": "ARRAY"},
            "parameterValue": {
                "arrayValues": [{"value": "09:00:00"}, {"value": "13:00:00"}]
            },
        },
        {
            "name": "array_timestamp_param",
            "parameterType": {"arrayType": {"type": "TIMESTAMP"}, "type": "ARRAY"},
            "parameterValue": {
                "arrayValues": [
                    {"value": "2025-04-10 10:00:00+00:00"},
                    {"value": "2025-04-10 12:00:00+00:00"},
                ]
            },
        },
        {
            "name": "struct_param",
            "parameterType": {
                "structTypes": [
                    {"name": "field1", "type": {"type": "STRING"}},
                    {"name": "field2", "type": {"type": "INT64"}},
                ],
                "type": "STRUCT",
            },
            "parameterValue": {
                "structValues": {
                    "field1": {"value": "struct value 1"},
                    "field2": {"value": "42"},
                }
            },
        },
        {
            "name": "array_struct_param",
            "parameterType": {
                "arrayType": {
                    "structTypes": [
                        {"name": "field1", "type": {"type": "STRING"}},
                        {"name": "field2", "type": {"type": "INT64"}},
                    ],
                    "type": "STRUCT",
                },
                "type": "ARRAY",
            },
            "parameterValue": {
                "arrayValues": [
                    {
                        "structValues": {
                            "field1": {"value": "array struct value 1a"},
                            "field2": {"value": "100"},
                        }
                    }
                ]
            },
        },
    ]
    bigquery_params = [QueryParameter(**param) for param in bigquery_params]
    duckdb_params = bigquery_params_to_duckdb_params(bigquery_params)
    assert duckdb_params == {
        "param0": "unnamed parameter",
        "string_param": "example string",
        "int64_param": 123,
        "float64_param": 3.14,
        "numeric_param": 123.45,
        "bignumeric_param": 12345678901234567890.123456789,
        "boolean_param": True,
        "bytes_param": b"example bytes",
        "date_param": datetime.date(2025, 4, 10),
        "datetime_param": datetime.datetime(2025, 4, 10, 11, 0),
        "time_param": datetime.time(11, 0),
        "timestamp_param": datetime.datetime(
            2025, 4, 10, 11, 0, tzinfo=datetime.timezone.utc
        ),
        "array_string_param": ["a", "b", "c"],
        "array_int64_param": [1, 2, 3],
        "array_float64_param": [1.1, 2.2, 3.3],
        "array_numeric_param": [1.1, 2.2, 3.3],
        "array_bignumeric_param": [123.1, 456.2, 789.3],
        "array_boolean_param": [True, False, True],
        "array_bytes_param": [b"byte1", b"byte2"],
        "array_date_param": [datetime.date(2025, 4, 1), datetime.date(2025, 4, 5)],
        "array_datetime_param": [
            datetime.datetime(2025, 4, 10, 10, 0),
            datetime.datetime(2025, 4, 10, 12, 0),
        ],
        "array_time_param": [datetime.time(9, 0), datetime.time(13, 0)],
        "array_timestamp_param": [
            datetime.datetime(2025, 4, 10, 10, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2025, 4, 10, 12, 0, tzinfo=datetime.timezone.utc),
        ],
        "struct_param": {"field1": "struct value 1", "field2": 42},
        "array_struct_param": [{"field1": "array struct value 1a", "field2": 100}],
    }


@pytest.fixture
def all_duckdb_type_results():
    bigquery_sql = """
        SELECT
            NULL AS null,
            1 AS int64,
            1.23 AS float64,
            "example" AS string,
            B"abc" AS bytes,
            TRUE AS bool,
            DATE "2024-01-01" AS date,
            TIME "12:34:56" AS time,
            DATETIME "2024-01-01 12:34:56" AS datetime,
            TIMESTAMP "2024-01-01 12:34:56+00" AS timestamp,
            JSON '{"key": "value"}' AS json,
            [1, 2, 3] AS repeated_int64,
            ["a", "b"] AS repeated_string,
            STRUCT(
                1 AS id,
                "nested" AS label,
                [STRUCT("item1" AS name), STRUCT("item2" AS name)] AS repeated_struct
            ) AS nested_struct
    """
    duckdb_sql = sqlglot.transpile(bigquery_sql, "bigquery", write="duckdb")[0]
    yield duckdb.sql(duckdb_sql)


def test_duckdb_fields_to_bigquery_fields(all_duckdb_type_results):
    duckdb_fields = list(
        zip(all_duckdb_type_results.columns, all_duckdb_type_results.types)
    )
    bigquery_fields = [
        field.model_dump(exclude_none=True)
        for field in duckdb_fields_to_bigquery_fields(duckdb_fields)
    ]
    assert bigquery_fields == [
        {"mode": "NULLABLE", "name": "null", "type": "INTEGER"},
        {"mode": "NULLABLE", "name": "int64", "type": "INTEGER"},
        {"mode": "NULLABLE", "name": "float64", "type": "FLOAT"},
        {"mode": "NULLABLE", "name": "string", "type": "STRING"},
        {"mode": "NULLABLE", "name": "bytes", "type": "BYTES"},
        {"mode": "NULLABLE", "name": "bool", "type": "BOOLEAN"},
        {"mode": "NULLABLE", "name": "date", "type": "DATE"},
        {"mode": "NULLABLE", "name": "time", "type": "TIME"},
        {"mode": "NULLABLE", "name": "datetime", "type": "TIMESTAMP"},
        {"mode": "NULLABLE", "name": "timestamp", "type": "TIMESTAMP"},
        {"mode": "NULLABLE", "name": "json", "type": "JSON"},
        {"mode": "REPEATED", "name": "repeated_int64", "type": "INTEGER"},
        {"mode": "REPEATED", "name": "repeated_string", "type": "STRING"},
        {
            "fields": [
                {"mode": "NULLABLE", "name": "id", "type": "INTEGER"},
                {"mode": "NULLABLE", "name": "label", "type": "STRING"},
                {
                    "fields": [
                        {
                            "mode": "NULLABLE",
                            "name": "name",
                            "type": "STRING",
                        }
                    ],
                    "mode": "REPEATED",
                    "name": "repeated_struct",
                    "type": "RECORD",
                },
            ],
            "mode": "NULLABLE",
            "name": "nested_struct",
            "type": "RECORD",
        },
    ]


def test_duckdb_values_to_bigquery_values(all_duckdb_type_results):
    duckdb_values = all_duckdb_type_results.fetchall()
    bigquery_values = [
        value.model_dump(exclude_none=True)
        for value in duckdb_values_to_bigquery_values(duckdb_values)
    ]
    assert bigquery_values == [
        {
            "f": [
                {},
                {"v": "1"},
                {"v": "1.23"},
                {"v": "example"},
                {"v": "YWJj"},
                {"v": "true"},
                {"v": "2024-01-01"},
                {"v": "12:34:56"},
                {"v": "1704112496000000"},
                {"v": "1704112496000000"},
                {"v": '{"key":"value"}'},
                {"v": [{"v": "1"}, {"v": "2"}, {"v": "3"}]},
                {"v": [{"v": "a"}, {"v": "b"}]},
                {
                    "v": {
                        "f": [
                            {"v": "1"},
                            {"v": "nested"},
                            {
                                "v": [
                                    {"v": {"f": [{"v": "item1"}]}},
                                    {"v": {"f": [{"v": "item2"}]}},
                                ]
                            },
                        ]
                    }
                },
            ]
        }
    ]


def field(name, type_, mode=None, fields=None):
    return TableFieldSchema(name=name, type=type_, mode=mode, fields=fields)


@pytest.fixture
def all_bigquery_schema_fields():
    return [
        field("id", "INT64", "REQUIRED"),
        field("order", "STRING"),
        field("tags", "STRING", "REPEATED"),
        field(
            "rec",
            "RECORD",
            None,
            [field("a", "INT64"), field("b", "STRING", "REPEATED")],
        ),
        field("recs", "RECORD", "REPEATED", [field("a", "INT64")]),
        field("ts", "TIMESTAMP"),
        field("n", "NUMERIC"),
        field("raw", "BYTES"),
        field("doc", "JSON"),
        field("f", "FLOAT"),
        field("flag", "BOOLEAN"),
        field("dt", "DATETIME"),
    ]


def test_bigquery_schema_to_duckdb_sql(all_bigquery_schema_fields):
    sql = bigquery_schema_to_duckdb_sql(
        all_bigquery_schema_fields, table_expr("project1", "dataset1", "table1")
    )
    assert sql == (
        'CREATE TABLE "project1"."dataset1"."table1" ('
        '"id" BIGINT NOT NULL, '
        '"order" TEXT, '
        '"tags" TEXT[], '
        '"rec" STRUCT("a" BIGINT, "b" TEXT[]), '
        '"recs" STRUCT("a" BIGINT)[], '
        '"ts" TIMESTAMPTZ, '
        '"n" DECIMAL, '
        '"raw" BLOB, '
        '"doc" JSON, '
        '"f" REAL, '
        '"flag" BOOLEAN, '
        '"dt" TIMESTAMP)'
    )


def test_bigquery_schema_to_duckdb_sql_executes(all_bigquery_schema_fields):
    conn = duckdb.connect()
    conn.execute("CREATE SCHEMA dataset1")
    conn.execute(
        bigquery_schema_to_duckdb_sql(
            all_bigquery_schema_fields, table_expr(None, "dataset1", "table1")
        )
    )
    result = conn.sql("SELECT * FROM dataset1.table1 LIMIT 0")
    assert list(zip(result.columns, [str(t) for t in result.types])) == [
        ("id", "BIGINT"),
        ("order", "VARCHAR"),
        ("tags", "VARCHAR[]"),
        ("rec", "STRUCT(a BIGINT, b VARCHAR[])"),
        ("recs", "STRUCT(a BIGINT)[]"),
        ("ts", "TIMESTAMP WITH TIME ZONE"),
        ("n", "DECIMAL(18,3)"),
        ("raw", "BLOB"),
        ("doc", "JSON"),
        ("f", "FLOAT"),
        ("flag", "BOOLEAN"),
        ("dt", "TIMESTAMP"),
    ]


def test_bigquery_schema_to_duckdb_sql_round_trips_through_duckdb_fields(
    all_bigquery_schema_fields,
):
    conn = duckdb.connect()
    conn.execute("CREATE SCHEMA dataset1")
    conn.execute(
        bigquery_schema_to_duckdb_sql(
            all_bigquery_schema_fields, table_expr(None, "dataset1", "table1")
        )
    )
    result = conn.sql("SELECT * FROM dataset1.table1 LIMIT 0")
    fields = duckdb_fields_to_bigquery_fields(list(zip(result.columns, result.types)))
    assert [(f.name, f.type, f.mode) for f in fields] == [
        ("id", "INTEGER", "NULLABLE"),
        ("order", "STRING", "NULLABLE"),
        ("tags", "STRING", "REPEATED"),
        ("rec", "RECORD", "NULLABLE"),
        ("recs", "RECORD", "REPEATED"),
        ("ts", "TIMESTAMP", "NULLABLE"),
        ("n", "FLOAT", "NULLABLE"),
        ("raw", "BYTES", "NULLABLE"),
        ("doc", "JSON", "NULLABLE"),
        ("f", "FLOAT", "NULLABLE"),
        ("flag", "BOOLEAN", "NULLABLE"),
        ("dt", "TIMESTAMP", "NULLABLE"),
    ]


def test_table_expr_quotes_and_strips():
    assert table_expr("p", "d", "t").sql("duckdb") == '"p"."d"."t"'
    assert table_expr("`p`", '"d"', "t").sql("duckdb") == '"p"."d"."t"'
    assert table_expr("p", "d").sql("duckdb") == '"p"."d"'
    assert table_expr(None, "d", "t").sql("duckdb") == '"d"."t"'
    assert table_expr(None, None, 'a"b').sql("duckdb") == '"a""b"'
