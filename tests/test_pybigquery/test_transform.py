import datetime

import duckdb
import pytest
import sqlglot

from local_bigquery.models import QueryParameter
from local_bigquery.transform import (
    fill_missing_fields,
    bigquery_params_to_duckdb_params,
    duckdb_fields_to_bigquery_fields,
    duckdb_values_to_bigquery_values,
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


def test_fill_missing_fields():
    data = {"id": "1", "nested": [{"item": "item1"}, {"item": "item2"}, {}]}
    converted_data = {k: fill_missing_fields(v) for k, v in data.items()}
    assert converted_data == {
        "id": "1",
        "nested": [
            {"item": "item1"},
            {"item": "item2"},
            {"item": None},
        ],
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
        {"mode": "NULLABLE", "name": "bytes", "type": "STRING"},
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
                {"v": "abc"},
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
