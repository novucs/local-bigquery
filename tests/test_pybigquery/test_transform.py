import duckdb
import pytest
import sqlglot

from local_bigquery.models import QueryParameter, QueryParameterValue
from local_bigquery.transform import (
    fill_missing_fields,
    bigquery_params_to_duckdb_param,
    duckdb_fields_to_bigquery_fields,
    duckdb_values_to_bigquery_values,
)


def test_query_params_to_duckdb():
    scalar_param = QueryParameter(
        name="scalar_param", parameterValue=QueryParameterValue(value="scalar_value")
    )
    struct_param = QueryParameter(
        name="user",
        parameterValue=QueryParameterValue(
            structValues={
                "id": QueryParameterValue(value="123"),
                "name": QueryParameterValue(value="John Doe"),
                "scores": QueryParameterValue(
                    arrayValues=[
                        QueryParameterValue(value="85"),
                        QueryParameterValue(value="90"),
                    ]
                ),
            }
        ),
    )
    params = [scalar_param, struct_param]
    duckdb_params = bigquery_params_to_duckdb_param(params)
    assert duckdb_params == {
        "scalar_param": "scalar_value",
        "user": {"id": "123", "name": "John Doe", "scores": ["85", "90"]},
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
