import datetime
import io

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from google.api_core.exceptions import BadRequest, Conflict, NotFound
from google.cloud import bigquery

from tests.cases import fails, run, type_name, unique

X = [bigquery.SchemaField("x", "INTEGER")]
APPEND = bigquery.WriteDisposition.WRITE_APPEND
TRUNCATE = bigquery.WriteDisposition.WRITE_TRUNCATE
EMPTY = bigquery.WriteDisposition.WRITE_EMPTY


def table_id(dataset):
    return f"{dataset.project}.{dataset.dataset_id}.{unique('t')}"


def select(bq, table):
    return sorted(tuple(row.values()) for row in run(bq, f"SELECT * FROM `{table}`"))


def types(bq, table):
    return [type_name(f) for f in run(bq, f"SELECT * FROM `{table}`").schema]


def load_json(bq, table, rows, **config):
    job_config = bigquery.LoadJobConfig(schema=X, **config)
    return bq.load_table_from_json(rows, table, job_config=job_config).result()


def load_file(bq, table, data: bytes, **config):
    job_config = bigquery.LoadJobConfig(**config)
    return bq.load_table_from_file(
        io.BytesIO(data), table, job_config=job_config
    ).result()


def ctas(bq, dataset, *values):
    table = table_id(dataset)
    run(bq, f"CREATE TABLE `{table}` AS SELECT x FROM UNNEST({list(values)}) AS x")
    return table


def test_load_json_rows(bq, dataset):
    table = table_id(dataset)
    job = load_json(bq, table, [{"x": 1}, {"x": 2}])
    assert (job.job_type, job.state, job.output_rows) == ("load", "DONE", 2)
    assert select(bq, table) == [(1,), (2,)]


def test_load_json_autodetects_schema(bq, dataset):
    table = table_id(dataset)
    rows = [{"x": 1, "s": "a", "f": 1.5, "b": True}]
    bq.load_table_from_json(rows, table).result()
    assert types(bq, table) == ["INT64", "STRING", "FLOAT64", "BOOL"]


def test_load_csv_skipping_header(bq, dataset):
    table = table_id(dataset)
    schema = [*X, bigquery.SchemaField("s", "STRING")]
    job = load_file(bq, table, b"x,s\n1,a\n2,b\n", schema=schema, skip_leading_rows=1)
    assert job.output_rows == 2
    assert select(bq, table) == [(1, "a"), (2, "b")]


def test_load_csv_autodetect(bq, dataset):
    table = table_id(dataset)
    load_file(bq, table, b"x,s,d\n1,a,2020-01-01\n", autodetect=True)
    assert types(bq, table) == ["INT64", "STRING", "DATE"]
    assert select(bq, table) == [(1, "a", datetime.date(2020, 1, 1))]


def test_load_newline_delimited_json_with_nested_fields(bq, dataset):
    table = table_id(dataset)
    schema = [
        *X,
        bigquery.SchemaField("tags", "STRING", mode="REPEATED"),
        bigquery.SchemaField(
            "rec", "RECORD", fields=[bigquery.SchemaField("y", "STRING")]
        ),
    ]
    data = b'{"x": 1, "tags": ["a", "b"], "rec": {"y": "z"}}\n{"x": 2}\n'
    load_file(bq, table, data, schema=schema, source_format="NEWLINE_DELIMITED_JSON")
    assert select(bq, table) == [(1, ["a", "b"], {"y": "z"}), (2, [], None)]


def test_load_parquet(bq, dataset):
    table = table_id(dataset)
    buffer = io.BytesIO()
    ts = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    pq.write_table(pa.table({"x": [1], "s": ["a"], "f": [1.5], "ts": [ts]}), buffer)
    load_file(bq, table, buffer.getvalue(), source_format="PARQUET")
    assert types(bq, table) == ["INT64", "STRING", "FLOAT64", "TIMESTAMP"]
    assert select(bq, table) == [(1, "a", 1.5, ts)]


def test_load_dataframe(bq, dataset):
    table = table_id(dataset)
    frame = pd.DataFrame({"x": [1, 2], "s": ["a", "b"]})
    bq.load_table_from_dataframe(frame, table).result()
    assert select(bq, table) == [(1, "a"), (2, "b")]


def test_load_write_append(bq, dataset):
    table = table_id(dataset)
    load_json(bq, table, [{"x": 1}])
    load_json(bq, table, [{"x": 2}], write_disposition=APPEND)
    assert select(bq, table) == [(1,), (2,)]


def test_load_write_truncate(bq, dataset):
    table = table_id(dataset)
    load_json(bq, table, [{"x": 1}])
    load_json(bq, table, [{"x": 2}], write_disposition=TRUNCATE)
    assert select(bq, table) == [(2,)]


def test_load_write_empty_rejects_non_empty_table(bq, dataset):
    table = table_id(dataset)
    load_json(bq, table, [{"x": 1}])
    with fails(Conflict, "duplicate"):
        load_json(bq, table, [{"x": 2}], write_disposition=EMPTY)


def test_load_create_never_requires_existing_table(bq, dataset):
    with fails(NotFound, "notFound"):
        load_json(bq, table_id(dataset), [{"x": 1}], create_disposition="CREATE_NEVER")


def test_load_adding_field_requires_schema_update_option(bq, dataset):
    table = table_id(dataset)
    load_json(bq, table, [{"x": 1}])
    wider = bigquery.LoadJobConfig(
        schema=[*X, bigquery.SchemaField("y", "STRING")], write_disposition=APPEND
    )
    with fails(BadRequest, "invalid"):
        bq.load_table_from_json([{"x": 2, "y": "a"}], table, job_config=wider).result()
    wider.schema_update_options = [bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
    bq.load_table_from_json([{"x": 2, "y": "a"}], table, job_config=wider).result()
    assert select(bq, table) == [(1, None), (2, "a")]


def test_load_max_bad_records(bq, dataset):
    table = table_id(dataset)
    with fails(BadRequest, "invalid"):
        load_file(bq, table, b"1\nabc\n", schema=X)
    job = load_file(bq, table, b"1\nabc\n", schema=X, max_bad_records=1)
    assert job.output_rows == 1
    assert select(bq, table) == [(1,)]


def test_copy_table(bq, dataset):
    source, destination = ctas(bq, dataset, 1, 2), table_id(dataset)
    job = bq.copy_table(source, destination).result()
    assert (job.job_type, job.state) == ("copy", "DONE")
    assert select(bq, destination) == [(1,), (2,)]


def test_copy_multiple_sources(bq, dataset):
    sources, destination = (
        [ctas(bq, dataset, 1), ctas(bq, dataset, 2)],
        table_id(dataset),
    )
    bq.copy_table(sources, destination).result()
    assert select(bq, destination) == [(1,), (2,)]


def test_copy_write_truncate(bq, dataset):
    source, destination = ctas(bq, dataset, 1), ctas(bq, dataset, 2)
    config = bigquery.CopyJobConfig(write_disposition=TRUNCATE)
    bq.copy_table(source, destination, job_config=config).result()
    assert select(bq, destination) == [(1,)]


def test_copy_write_empty_rejects_non_empty_table(bq, dataset):
    source, destination = ctas(bq, dataset, 1), ctas(bq, dataset, 2)
    config = bigquery.CopyJobConfig(write_disposition=EMPTY)
    with fails(Conflict, "duplicate"):
        bq.copy_table(source, destination, job_config=config).result()


def test_copy_missing_source(bq, dataset):
    with fails(NotFound, "notFound"):
        bq.copy_table(table_id(dataset), table_id(dataset)).result()
