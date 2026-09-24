import pytest
from google.cloud import bigquery

from tests.cases import q, run, unique

CASES = [
    q(
        "SELECT j = j FROM (SELECT JSON '1' AS j)",
        error="Equality is not defined for arguments of type JSON",
    ),
    q(
        "SELECT INT64_ARRAY(JSON '[1]')",
        error=r"Function not found: INT64_ARRAY at \[1:8\]",
    ),
    q("""SELECT JSON '{"a": 1}'""", {"a": 1}, types="JSON"),
    q("""SELECT PARSE_JSON('[1, "x", null]')""", [1, "x", None], types="JSON"),
    q(
        "SELECT PARSE_JSON('922337203685477580701')",
        error="invalidQuery",
    ),
    q(
        "SELECT PARSE_JSON('922337203685477580701', wide_number_mode => 'round')",
        9.223372036854776e20,
    ),
    q("SELECT PARSE_JSON('not json')", error="invalidQuery"),
    q("SELECT JSON_OBJECT('a', 1, 'b', 'x')", {"a": 1, "b": "x"}),
    q("SELECT JSON_ARRAY(1, 'a', NULL)", [1, "a", None]),
    q(
        "SELECT TO_JSON(STRUCT(1 AS a, [1, 2] AS b))",
        {"a": 1, "b": [1, 2]},
    ),
    q(
        "SELECT TO_JSON_STRING(STRUCT(1 AS a, 'x' AS b))",
        '{"a":1,"b":"x"}',
        types="STRING",
    ),
    q(
        "SELECT TO_JSON_STRING([1, 2], true)",
        "[\n  1,\n  2\n]",
    ),
    q("SELECT TO_JSON_STRING(NULL)", "null"),
    q(
        "SELECT TO_JSON_STRING(STRUCT(DATE '2020-01-02' AS d, b'ab' AS b))",
        '{"d":"2020-01-02","b":"YWI="}',
    ),
    q("""SELECT JSON_VALUE('{"a": {"b": 1}}', '$.a.b')""", "1", types="STRING"),
    q("""SELECT JSON_VALUE('{"a": {"b": 1}}', '$.a')""", None),
    q("""SELECT JSON_VALUE('{"a": [10, 20]}', '$.a[1]')""", "20"),
    q("""SELECT JSON_VALUE('{"$tricky": "t"}', '$."$tricky"')""", "t"),
    q("""SELECT JSON_VALUE('{"a.b": 1}', '$."a.b"')""", "1"),
    q(
        """SELECT JSON_QUERY('{"a": {"b": 1}}', '$.a')""",
        '{"b":1}',
        types="STRING",
    ),
    q("""SELECT JSON_QUERY(JSON '{"a": [1, 2]}', '$.a')""", [1, 2], types="JSON"),
    q(
        """SELECT JSON_EXTRACT('{"a": "x"}', '$.a')""",
        '"x"',
    ),
    q("""SELECT JSON_EXTRACT_SCALAR('{"a": "x"}', '$.a')""", "x"),
    q("""SELECT JSON_EXTRACT_SCALAR('{"a": true}', '$.a')""", "true"),
    q(
        """SELECT JSON_EXTRACT_ARRAY('[1, "a", {"b": 2}]')""",
        ["1", '"a"', '{"b":2}'],
        types="ARRAY<STRING>",
    ),
    q("""SELECT JSON_EXTRACT_STRING_ARRAY('["a", "é"]')""", ["a", "é"]),
    q("""SELECT JSON_VALUE_ARRAY('["a", 1]')""", ["a", "1"]),
    q(
        """SELECT JSON_QUERY_ARRAY('[{"a": 1}, 2]')""",
        ['{"a":1}', "2"],
    ),
    q("""SELECT j.a.b FROM (SELECT JSON '{"a": {"b": 1}}' AS j)""", 1, types="JSON"),
    q("""SELECT j['a']['b'] FROM (SELECT JSON '{"a": {"b": 1}}' AS j)""", 1),
    q(
        """SELECT j.xs[1] FROM (SELECT JSON '{"xs": [10, 20]}' AS j)""",
        20,
    ),
    q("""SELECT j.missing IS NULL FROM (SELECT JSON '{"a": 1}' AS j)""", True),
    q(
        """SELECT INT64(JSON '1'), FLOAT64(JSON '1.5'), BOOL(JSON 'true'), STRING(JSON '"x"')""",
        rows=[(1, 1.5, True, "x")],
        types=("INT64", "FLOAT64", "BOOL", "STRING"),
    ),
    q(
        """SELECT INT64(JSON '"1"')""",
        error="invalidQuery",
    ),
    q("""SELECT JSON '{"a": {"b": 1}}'.a.b, JSON '{"a": 1}'.a""", rows=[(1, 1)]),
    q(
        """SELECT JSON_FLATTEN(JSON '[1, [2, 3], [[{"a": [4]}]]]')""",
        [1, 2, 3, {"a": [4]}],
        types="ARRAY<JSON>",
    ),
    q(
        """SELECT LAX_INT64(JSON '"10"'),LAX_FLOAT64(JSON '"1.5"'), LAX_BOOL(JSON '"true"'), LAX_STRING(JSON '1')""",
        rows=[(10, 1.5, True, "1")],
    ),
    q(
        """SELECT JSON_TYPE(JSON '1'), JSON_TYPE(JSON '[]'), JSON_TYPE(JSON '{}'), """
        """JSON_TYPE(JSON 'true'), JSON_TYPE(JSON 'null'), JSON_TYPE(JSON '"a"')""",
        rows=[("number", "array", "object", "boolean", "null", "string")],
    ),
    q(
        """SELECT JSON_KEYS(JSON '{"a": {"b": 1}, "c": 2}')""",
        ["a", "a.b", "c"],
    ),
    q(
        """SELECT JSON_KEYS(JSON '{"a": {"b": 1}, "c": 2}', 1)""",
        ["a", "c"],
    ),
    q(
        """SELECT JSON_SET(JSON '{"a": 1}', '$.b', 2)""",
        {"a": 1, "b": 2},
    ),
    q(
        """SELECT JSON_REMOVE(JSON '{"a": 1, "b": 2}', '$.a')""",
        {"b": 2},
    ),
    q(
        """SELECT JSON_STRIP_NULLS(JSON '{"a": null, "b": 1}')""",
        {"b": 1},
    ),
    q("SELECT JSON_ARRAY_APPEND(JSON '[1]', '$', 2)", [1, 2]),
    q(
        "SELECT JSON_ARRAY_INSERT(JSON '[1, 2]', '$[0]', 0)",
        [0, 1, 2],
    ),
    q("SELECT JSON 'null' IS NULL", False),
    q("""SELECT JSON_QUERY(JSON '{"a": null}', '$.a') IS NULL""", False),
    q("""SELECT JSON_VALUE(JSON '{"a": null}', '$.a') IS NULL""", True),
    q(
        "SELECT JSON '1' = JSON '1'",
        error="not defined|No matching signature",
    ),
    q(
        """SELECT JSON_KEYS(PARSE_JSON('{"a": 1, "b": 2, "c": 3}'))""",
        ["a", "b", "c"],
        types="ARRAY<STRING>",
    ),
    q(
        """SELECT ARRAY_LENGTH(JSON_KEYS(PARSE_JSON('{"a": 1, "b": 2}')))""",
        2,
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_json(check, case):
    check(case)


def test_json_column_round_trip(bq, dataset):
    table = bq.create_table(
        bigquery.Table(
            dataset.table(unique("json")),
            schema=[bigquery.SchemaField("data", "JSON")],
        )
    )
    value = {"x": 1, "y": [2, None], "$tricky": "tricky key"}
    run(
        bq,
        f'INSERT INTO `{table}` (data) VALUES (JSON \'{{"x": 1, "y": [2, null], "$tricky": "tricky key"}}\')',
    )
    assert [row.data for row in run(bq, f"SELECT data FROM `{table}`")] == [value]
    assert [row.x for row in run(bq, f"SELECT data.x FROM `{table}`")] == [1]
    tricky = run(bq, f"""SELECT JSON_VALUE(data, '$."$tricky"') AS t FROM `{table}`""")
    assert [row.t for row in tricky] == ["tricky key"]
