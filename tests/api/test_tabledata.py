import datetime
from decimal import Decimal

import pytest
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from tests.cases import fails, run, unique

UTC = datetime.timezone.utc
SCHEMA = [
    bigquery.SchemaField("s", "STRING"),
    bigquery.SchemaField("b", "BYTES"),
    bigquery.SchemaField("i", "INTEGER"),
    bigquery.SchemaField("f", "FLOAT"),
    bigquery.SchemaField("n", "NUMERIC"),
    bigquery.SchemaField("bn", "BIGNUMERIC"),
    bigquery.SchemaField("bool", "BOOLEAN"),
    bigquery.SchemaField("ts", "TIMESTAMP"),
    bigquery.SchemaField("d", "DATE"),
    bigquery.SchemaField("t", "TIME"),
    bigquery.SchemaField("dt", "DATETIME"),
    bigquery.SchemaField("j", "JSON"),
    bigquery.SchemaField("tags", "STRING", mode="REPEATED"),
    bigquery.SchemaField(
        "rec",
        "RECORD",
        fields=[
            bigquery.SchemaField("x", "INTEGER"),
            bigquery.SchemaField("ys", "STRING", mode="REPEATED"),
        ],
    ),
]
ROW = {
    "s": "a",
    "b": b"\x00\xff",
    "i": 1,
    "f": 1.5,
    "n": Decimal("1.25"),
    "bn": Decimal("12345678901234567890.123456789"),
    "bool": True,
    "ts": datetime.datetime(2020, 1, 1, 12, tzinfo=UTC),
    "d": datetime.date(2020, 1, 2),
    "t": datetime.time(3, 4, 5),
    "dt": datetime.datetime(2020, 1, 2, 3, 4, 5),
    "j": {"k": [1, 2]},
    "tags": ["x", "y"],
    "rec": {"x": 1, "ys": ["z"]},
}


def create(bq, dataset, *fields):
    table = bigquery.Table(
        f"{dataset.project}.{dataset.dataset_id}.{unique('t')}",
        schema=list(fields) or [bigquery.SchemaField("x", "INTEGER")],
    )
    bq.create_table(table)
    return table


def select(bq, table, order_by="x"):
    order = f" ORDER BY {order_by}" if order_by else ""
    return [dict(row) for row in run(bq, f"SELECT * FROM `{table.reference}`{order}")]


def ints(bq, table, count):
    assert bq.insert_rows_json(table, [{"x": i} for i in range(count)]) == []
    return table


def test_insert_rows_round_trips_every_type(bq, dataset):
    table = create(bq, dataset, *SCHEMA)
    assert bq.insert_rows(table, [ROW]) == []
    assert select(bq, table, "s") == [ROW]


def test_insert_rows_nested_repeated_records(bq, dataset):
    table = create(
        bq,
        dataset,
        bigquery.SchemaField("id", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField(
            "nested",
            "RECORD",
            mode="REPEATED",
            fields=[bigquery.SchemaField("item", "STRING")],
        ),
    )
    rows = [{"id": 1, "nested": [{"item": "a"}, {"item": "b"}, {"item": None}]}]
    assert bq.insert_rows(table, rows) == []
    assert select(bq, table, "id") == rows


def test_insert_rows_bulk_with_json_and_case_insensitive_keys(bq, dataset):
    table = create(
        bq,
        dataset,
        bigquery.SchemaField("Name", "STRING"),
        bigquery.SchemaField("age", "INTEGER"),
        bigquery.SchemaField("meta", "JSON"),
    )
    rows = [{"name": f"user{i}", "age": i, "meta": {"i": i}} for i in range(1000)]
    assert bq.insert_rows(table, rows) == []
    assert select(bq, table, "age") == [
        {"Name": r["name"], "age": r["age"], "meta": r["meta"]} for r in rows
    ]


def test_insert_dedups_by_insert_id(bq, dataset):
    table = create(bq, dataset)
    for _ in range(2):
        assert bq.insert_rows_json(table, [{"x": 1}], row_ids=["same"]) == []
    assert select(bq, table) == [{"x": 1}]


def test_skip_invalid_rows_reports_per_row_errors(bq, dataset):
    table = create(bq, dataset)
    errors = bq.insert_rows_json(
        table, [{"x": 1}, {"x": "abc"}], skip_invalid_rows=True
    )
    assert [e["index"] for e in errors] == [1]
    assert [(e["reason"], e["location"]) for e in errors[0]["errors"]] == [
        ("invalid", "x")
    ]
    assert select(bq, table) == [{"x": 1}]


def test_invalid_row_stops_the_whole_request(bq, dataset):
    table = create(bq, dataset)
    errors = bq.insert_rows_json(table, [{"x": 1}, {"x": "abc"}])
    reasons = {e["index"]: e["errors"][0]["reason"] for e in errors}
    assert reasons == {0: "stopped", 1: "invalid"}
    assert select(bq, table) == []


def test_unknown_field_is_rejected(bq, dataset):
    table = create(bq, dataset)
    errors = bq.insert_rows_json(table, [{"x": 1, "nope": 2}])
    assert [(e["reason"], e["location"]) for e in errors[0]["errors"]] == [
        ("invalid", "nope")
    ]


def test_ignore_unknown_values(bq, dataset):
    table = create(bq, dataset)
    assert (
        bq.insert_rows_json(table, [{"x": 1, "nope": 2}], ignore_unknown_values=True)
        == []
    )
    assert select(bq, table) == [{"x": 1}]


def test_missing_required_field_is_rejected(bq, dataset):
    table = create(bq, dataset, bigquery.SchemaField("x", "INTEGER", mode="REQUIRED"))
    errors = bq.insert_rows_json(table, [{}])
    assert errors[0]["errors"][0]["reason"] == "invalid"
    assert select(bq, table) == []


def test_template_suffix_creates_table_from_template(bq, dataset):
    table = create(bq, dataset)
    assert bq.insert_rows_json(table, [{"x": 1}], template_suffix="_s") == []
    assert [
        tuple(r.values()) for r in run(bq, f"SELECT x FROM `{table.reference}_s`")
    ] == [(1,)]
    assert select(bq, table) == []


def test_insert_into_missing_table(bq, dataset):
    table = bigquery.Table(
        f"{dataset.project}.{dataset.dataset_id}.{unique('missing')}"
    )
    with fails(NotFound, "notFound"):
        bq.insert_rows_json(table, [{"x": 1}])


def test_list_rows_decodes_every_type(bq, dataset):
    table = create(bq, dataset, *SCHEMA)
    bq.insert_rows(table, [ROW])
    rows = bq.list_rows(table)
    assert [dict(row) for row in rows] == [ROW]
    assert rows.total_rows == 1


def test_list_rows_pages(bq, dataset):
    table = ints(bq, create(bq, dataset), 5)
    pages = [[r["x"] for r in page] for page in bq.list_rows(table, page_size=2).pages]
    assert [len(page) for page in pages] == [2, 2, 1]
    assert sorted(x for page in pages for x in page) == [0, 1, 2, 3, 4]


def test_list_rows_max_results_and_start_index(bq, dataset):
    table = ints(bq, create(bq, dataset), 5)
    everything = [r["x"] for r in bq.list_rows(table)]
    assert [r["x"] for r in bq.list_rows(table, max_results=2)] == everything[:2]
    assert [
        r["x"] for r in bq.list_rows(table, start_index=1, max_results=2)
    ] == everything[1:3]


def test_list_rows_selected_fields(bq, dataset):
    a, b = bigquery.SchemaField("a", "INTEGER"), bigquery.SchemaField("b", "STRING")
    table = create(bq, dataset, a, b)
    bq.insert_rows(table, [{"a": 1, "b": "x"}])
    assert [dict(r) for r in bq.list_rows(table, selected_fields=[b])] == [{"b": "x"}]


def test_list_rows_empty_table(bq, dataset):
    rows = bq.list_rows(create(bq, dataset))
    assert list(rows) == []
    assert rows.total_rows == 0


def test_list_rows_to_dataframe(bq, dataset):
    table = ints(bq, create(bq, dataset), 3)
    frame = bq.list_rows(table).to_dataframe(create_bqstorage_client=False)
    assert sorted(frame["x"].tolist()) == [0, 1, 2]
    assert str(frame["x"].dtype) == "Int64"


def test_query_to_dataframe(bq):
    frame = run(
        bq, "SELECT x, CAST(x AS STRING) AS s FROM UNNEST([1, 2]) AS x ORDER BY x"
    ).to_dataframe()
    assert frame.to_dict("list") == {"x": [1, 2], "s": ["1", "2"]}


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        ["a"],
    ],
)
def test_repeated_field_null_and_empty_read_back_as_list(bq, dataset, value):
    table = create(bq, dataset, bigquery.SchemaField("tags", "STRING", mode="REPEATED"))
    assert bq.insert_rows_json(table, [{"tags": value}]) == []
    assert select(bq, table, None) == [{"tags": value or []}]
