import datetime

import pytest
from google.api_core.exceptions import BadRequest, Conflict, NotFound
from google.cloud import bigquery

from tests.cases import fails, run, type_name, unique

ALL_TYPES = [
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
    bigquery.SchemaField("g", "GEOGRAPHY"),
    bigquery.SchemaField("j", "JSON"),
    bigquery.SchemaField("tags", "STRING", mode="REPEATED"),
    bigquery.SchemaField(
        "rec",
        "RECORD",
        fields=[
            bigquery.SchemaField("x", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField(
                "ys",
                "RECORD",
                mode="REPEATED",
                fields=[
                    bigquery.SchemaField("z", "STRING"),
                ],
            ),
        ],
    ),
]


def table_ref(dataset, name=None):
    return f"{dataset.project}.{dataset.dataset_id}.{name or unique('t')}"


def create(bq, dataset, schema=None, **properties):
    table = bigquery.Table(
        table_ref(dataset), schema=schema or [bigquery.SchemaField("x", "INTEGER")]
    )
    for key, value in properties.items():
        setattr(table, key, value)
    return bq.create_table(table)


def test_create_returns_server_populated_fields(bq, dataset):
    table = create(bq, dataset)
    assert table.table_type == "TABLE"
    assert (
        table.full_table_id
        == f"{dataset.project}:{dataset.dataset_id}.{table.table_id}"
    )
    assert table.location == "US"
    assert table.created is not None
    assert table.modified is not None
    assert table.etag
    assert table.num_rows == 0


def test_schema_round_trips_every_type(bq, dataset):
    table = create(bq, dataset, ALL_TYPES)
    fetched = bq.get_table(table)
    assert [type_name(f) for f in fetched.schema] == [
        "STRING",
        "BYTES",
        "INT64",
        "FLOAT64",
        "NUMERIC",
        "BIGNUMERIC",
        "BOOL",
        "TIMESTAMP",
        "DATE",
        "TIME",
        "DATETIME",
        "GEOGRAPHY",
        "JSON",
        "ARRAY<STRING>",
        "STRUCT<x INT64, ys ARRAY<STRUCT<z STRING>>>",
    ]
    assert fetched.schema[-1].fields[0].mode == "REQUIRED"


def test_schema_round_trips_descriptions_and_parameters(bq, dataset):
    schema = [
        bigquery.SchemaField(
            "n", "NUMERIC", precision=10, scale=2, description="money"
        ),
        bigquery.SchemaField(
            "s", "STRING", max_length=5, default_value_expression="'x'"
        ),
    ]
    fetched = bq.get_table(create(bq, dataset, schema))
    n, s = fetched.schema
    assert (n.precision, n.scale, n.description) == (10, 2, "money")
    assert (s.max_length, s.default_value_expression) == (5, "'x'")


def test_create_round_trips_metadata(bq, dataset):
    expires = datetime.datetime(2100, 1, 1, tzinfo=datetime.timezone.utc)
    table = create(
        bq,
        dataset,
        description="about",
        friendly_name="Friendly",
        labels={"env": "dev"},
        expires=expires,
    )
    fetched = bq.get_table(table)
    assert fetched.description == "about"
    assert fetched.friendly_name == "Friendly"
    assert fetched.labels == {"env": "dev"}
    assert fetched.expires == expires


def test_create_time_partitioned_and_clustered(bq, dataset):
    schema = [
        bigquery.SchemaField("day", "DATE"),
        bigquery.SchemaField("k", "STRING"),
    ]
    table = create(
        bq,
        dataset,
        schema,
        time_partitioning=bigquery.TimePartitioning(field="day"),
        clustering_fields=["k"],
        require_partition_filter=True,
    )
    fetched = bq.get_table(table)
    assert fetched.time_partitioning.type_ == "DAY"
    assert fetched.time_partitioning.field == "day"
    assert fetched.clustering_fields == ["k"]
    assert fetched.require_partition_filter is True


def test_create_range_partitioned(bq, dataset):
    table = create(
        bq,
        dataset,
        range_partitioning=bigquery.RangePartitioning(
            field="x", range_=bigquery.PartitionRange(start=0, end=100, interval=10)
        ),
    )
    fetched = bq.get_table(table)
    assert fetched.range_partitioning.field == "x"
    assert fetched.range_partitioning.range_.interval == 10


def test_create_view(bq, dataset):
    view = bigquery.Table(table_ref(dataset))
    view.view_query = "SELECT 1 AS one, 'a' AS letter"
    view = bq.create_table(view)
    fetched = bq.get_table(view)
    assert fetched.table_type == "VIEW"
    assert fetched.view_query == "SELECT 1 AS one, 'a' AS letter"
    assert [f.name for f in fetched.schema] == ["one", "letter"]
    assert [
        tuple(r.values()) for r in run(bq, f"SELECT * FROM `{view.reference}`")
    ] == [(1, "a")]


def test_create_duplicate(bq, dataset):
    table = create(bq, dataset)
    with fails(Conflict, "duplicate"):
        bq.create_table(bigquery.Table(table.reference, schema=table.schema))
    bq.create_table(table.reference, exists_ok=True)


def test_create_in_missing_dataset(bq, project):
    with fails(NotFound, "notFound"):
        bq.create_table(f"{project}.{unique('missing')}.t")


def test_get_missing(bq, dataset):
    with fails(NotFound, "notFound"):
        bq.get_table(table_ref(dataset))


def test_get_reports_row_count_and_size(bq, dataset):
    table = create(bq, dataset)
    run(bq, f"INSERT INTO `{table.reference}` (x) VALUES (1), (2), (3)")
    fetched = bq.get_table(table)
    assert fetched.num_rows == 3
    assert fetched.num_bytes > 0


def test_table_ids_are_case_sensitive(bq, dataset):
    name = unique("case")
    lower = bq.create_table(table_ref(dataset, name))
    upper = bq.create_table(table_ref(dataset, name.upper()))
    assert lower.table_id != upper.table_id
    assert bq.get_table(upper).table_id == name.upper()


def test_list_includes_tables_and_views(bq):
    dataset = bq.create_dataset(unique("list"))
    try:
        table = create(bq, dataset)
        view = bigquery.Table(table_ref(dataset))
        view.view_query = "SELECT 1 AS x"
        view = bq.create_table(view)
        listed = {t.table_id: t.table_type for t in bq.list_tables(dataset)}
        assert listed == {table.table_id: "TABLE", view.table_id: "VIEW"}
    finally:
        bq.delete_dataset(dataset, delete_contents=True)


def test_list_pages(bq):
    dataset = bq.create_dataset(unique("pages"))
    try:
        ids = {create(bq, dataset).table_id for _ in range(3)}
        pages = [list(page) for page in bq.list_tables(dataset, page_size=1).pages]
        assert {len(page) for page in pages} == {1}
        assert {t.table_id for page in pages for t in page} == ids
    finally:
        bq.delete_dataset(dataset, delete_contents=True)


def test_update_patches_only_given_fields(bq, dataset):
    table = create(bq, dataset, description="before")
    table.labels = {"env": "prod"}
    bq.update_table(table, ["labels"])
    fetched = bq.get_table(table)
    assert fetched.labels == {"env": "prod"}
    assert fetched.description == "before"


def test_update_expiration(bq, dataset):
    table = create(bq, dataset)
    table.expires = datetime.datetime(2100, 1, 1, tzinfo=datetime.timezone.utc)
    bq.update_table(table, ["expires"])
    assert bq.get_table(table).expires == table.expires


def test_update_adds_column(bq, dataset):
    table = create(bq, dataset)
    table.schema = [*table.schema, bigquery.SchemaField("y", "STRING")]
    bq.update_table(table, ["schema"])
    run(bq, f"INSERT INTO `{table.reference}` (x, y) VALUES (1, 'a')")
    assert [f.name for f in bq.get_table(table).schema] == ["x", "y"]


def test_update_relaxes_required_column(bq, dataset):
    table = create(bq, dataset, [bigquery.SchemaField("x", "INTEGER", mode="REQUIRED")])
    table.schema = [bigquery.SchemaField("x", "INTEGER", mode="NULLABLE")]
    bq.update_table(table, ["schema"])
    assert bq.get_table(table).schema[0].mode == "NULLABLE"


def test_update_rejects_dropping_column(bq, dataset):
    schema = [bigquery.SchemaField("x", "INTEGER"), bigquery.SchemaField("y", "STRING")]
    table = create(bq, dataset, schema)
    table.schema = schema[:1]
    with fails(BadRequest, "invalid"):
        bq.update_table(table, ["schema"])


def test_update_with_stale_etag(bq, dataset):
    table = create(bq, dataset)
    table.description = "first"
    bq.update_table(table, ["description"])
    table.description = "second"
    with pytest.raises(Exception, match="412"):
        bq.update_table(table, ["description"])


def test_update_bumps_modified(bq, dataset):
    table = create(bq, dataset)
    table.description = "changed"
    updated = bq.update_table(table, ["description"])
    assert updated.modified >= table.modified
    assert updated.etag != table.etag


def test_delete(bq, dataset):
    table = create(bq, dataset)
    bq.delete_table(table)
    with fails(NotFound, "notFound"):
        bq.get_table(table)


def test_delete_missing(bq, dataset):
    with fails(NotFound, "notFound"):
        bq.delete_table(table_ref(dataset))
    bq.delete_table(table_ref(dataset), not_found_ok=True)


@pytest.mark.parametrize(
    "dataset_id",
    ['bad"; DROP SCHEMA main; --', "has space", "a.b"],
)
def test_invalid_dataset_ids_are_rejected(bq, dataset_id):
    with fails(BadRequest, "invalid") as info:
        bq.create_dataset(bigquery.Dataset(f"{bq.project}.{dataset_id}"))
    assert f'Invalid dataset ID "{dataset_id}"' in info.value.message


@pytest.mark.parametrize("table_id", ['t"; DROP TABLE x; --', "t;", "t@1"])
def test_invalid_table_ids_are_rejected(bq, dataset, table_id):
    table = bigquery.Table(f"{dataset.project}.{dataset.dataset_id}.{table_id}")
    with fails(BadRequest, "invalid") as info:
        bq.create_table(table)
    assert f'Invalid table ID "{table_id}"' in info.value.message


def test_unicode_and_spaced_table_ids_are_allowed(bq, dataset):
    table_id = f"{dataset.dataset_id}.{unique('tåble с пробелом')}"
    assert bq.create_table(table_id).table_id == table_id.split(".")[1]


@pytest.mark.parametrize("name", ['a"); DROP TABLE t; --', "a.b", "x" * 301])
def test_invalid_field_names_are_rejected(bq, dataset, name):
    table = bigquery.Table(
        f"{dataset.project}.{dataset.dataset_id}.{unique('t')}",
        schema=[bigquery.SchemaField(name, "STRING")],
    )
    with fails(BadRequest, "invalid") as info:
        bq.create_table(table)
    assert "Fields must contain the allowed characters" in info.value.message


def test_flexible_field_names_are_allowed(bq, dataset):
    table = bigquery.Table(
        f"{dataset.project}.{dataset.dataset_id}.{unique('t')}",
        schema=[bigquery.SchemaField("total & count-1", "STRING")],
    )
    assert [f.name for f in bq.create_table(table).schema] == ["total & count-1"]
