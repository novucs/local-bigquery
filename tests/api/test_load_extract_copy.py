import datetime
import decimal
import gzip
import io
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import fastavro
import pandas as pd
import pyarrow as pa
import pyarrow.orc as orc
import pyarrow.parquet as pq
import pytest
from google.api_core.exceptions import BadRequest, Conflict, NotFound
from google.cloud import bigquery

from tests.cases import fails, run, run_job, type_name, unique

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
    job_config = bigquery.LoadJobConfig(**{"schema": X} | config)
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
    schema = run(bq, f"SELECT * FROM `{table}`").schema
    assert {f.name: type_name(f) for f in schema} == {
        "x": "INT64",
        "s": "STRING",
        "f": "FLOAT64",
        "b": "BOOL",
    }


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


@pytest.mark.parametrize(
    "data, source_format",
    [
        (b"1\nabc\n", "CSV"),
        (b'{"x": 1}\n{"x": "abc"}\n', "NEWLINE_DELIMITED_JSON"),
    ],
)
def test_load_max_bad_records(bq, dataset, data, source_format):
    table = table_id(dataset)
    with fails(BadRequest, "invalid"):
        load_file(bq, table, data, schema=X, source_format=source_format)
    job = load_file(
        bq, table, data, schema=X, source_format=source_format, max_bad_records=1
    )
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


@pytest.fixture
def local(request, tmp_path):
    if request.config.getoption("--endpoint"):
        pytest.skip("extract to file:// needs the in-process emulator")
    return tmp_path


def extract(bq, table, uri, **config):
    job_config = bigquery.ExtractJobConfig(**config)
    return bq.extract_table(table, uri, job_config=job_config).result()


def test_extract_csv_with_header(bq, dataset, local):
    job = extract(bq, ctas(bq, dataset, 1), f"file://{local}/out.csv")
    assert job.state == "DONE"
    assert (local / "out.csv").read_text().splitlines() == ["x", "1"]


def test_extract_compressed_csv(bq, dataset, local):
    extract(
        bq,
        ctas(bq, dataset, 1),
        f"file://{local}/out.csv.gz",
        compression=bigquery.Compression.GZIP,
        print_header=False,
    )
    assert gzip.decompress((local / "out.csv.gz").read_bytes()) == b"1\n"


def test_extract_newline_delimited_json(bq, dataset, local):
    extract(
        bq,
        ctas(bq, dataset, 1, 2),
        f"file://{local}/out.json",
        destination_format=bigquery.DestinationFormat.NEWLINE_DELIMITED_JSON,
    )
    lines = (local / "out.json").read_text().splitlines()
    assert sorted(json.loads(line)["x"] for line in lines) == [1, 2]


def test_extract_parquet(bq, dataset, local):
    extract(
        bq,
        ctas(bq, dataset, 1, 2),
        f"file://{local}/out.parquet",
        destination_format=bigquery.DestinationFormat.PARQUET,
    )
    assert sorted(pq.read_table(local / "out.parquet")["x"].to_pylist()) == [1, 2]


def test_extract_wildcard_uri(bq, dataset, local):
    extract(bq, ctas(bq, dataset, 1), f"file://{local}/part-*.csv")
    assert [p.name for p in local.iterdir()] == ["part-000000000000.csv"]


def test_extract_missing_table(bq, dataset, local):
    with fails(NotFound, "notFound"):
        extract(
            bq, f"{dataset.dataset_id}.{unique('missing')}", f"file://{local}/x.csv"
        )


def test_export_data_statement(bq, dataset, local):
    run(
        bq,
        f"EXPORT DATA OPTIONS (uri = 'file://{local}/export-*.csv', format = 'CSV', "
        "overwrite = true, header = true) AS SELECT 1 AS x",
    )
    exported = next(local.iterdir()).read_text().splitlines()
    assert exported == ["x", "1"]


def test_export_data_statistics(bq, local):
    job = run_job(
        bq,
        f"EXPORT DATA OPTIONS (uri = 'file://{local}/stats-*.csv', format = 'CSV') "
        "AS SELECT x FROM UNNEST([1, 2, 3]) AS x",
    )
    statistics = job._properties["statistics"]["query"]
    assert statistics["statementType"] == "EXPORT_DATA"
    assert statistics["exportDataStatistics"] == {"fileCount": "1", "rowCount": "3"}


@pytest.fixture
def bucket(request, monkeypatch):
    if request.config.getoption("--endpoint"):
        pytest.skip("inspects the emulator's data directory")
    from local_bigquery.settings import settings

    monkeypatch.setattr(settings, "gcs_local_root", None)
    monkeypatch.setattr(settings, "storage_emulator_host", None)
    return settings.data_dir / "gcs" / unique("bucket")


def test_extract_to_gcs(bq, dataset, bucket):
    extract(bq, ctas(bq, dataset, 1), f"gs://{bucket.name}/out/data.csv")
    assert (bucket / "out" / "data.csv").read_text().splitlines() == ["x", "1"]


def test_load_from_gcs(bq, dataset, bucket):
    bucket.mkdir(parents=True)
    (bucket / "in.csv").write_text("x\n1\n2\n")
    table = table_id(dataset)
    config = bigquery.LoadJobConfig(schema=X, skip_leading_rows=1)
    bq.load_table_from_uri(
        f"gs://{bucket.name}/in.csv", table, job_config=config
    ).result()
    assert select(bq, table) == [(1,), (2,)]


def test_export_data_to_gcs(bq, bucket):
    run(
        bq,
        f"EXPORT DATA OPTIONS (uri = 'gs://{bucket.name}/export/*.csv', "
        "format = 'CSV', overwrite = true) AS SELECT 1 AS x",
    )
    assert [p.read_text() for p in (bucket / "export").iterdir()] == ["x\n1\n"]


@pytest.fixture
def storage_emulator(request, monkeypatch):
    if request.config.getoption("--endpoint"):
        pytest.skip("points the emulator at a fake storage endpoint")
    from local_bigquery.settings import settings

    uploads = {}

    class Uploads(BaseHTTPRequestHandler):
        def do_POST(self):
            url = urllib.parse.urlsplit(self.path)
            bucket = url.path.split("/b/")[1].split("/")[0]
            name = urllib.parse.parse_qs(url.query)["name"][0]
            length = int(self.headers["Content-Length"])
            uploads[f"{bucket}/{name}"] = self.rfile.read(length)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Uploads)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host = f"127.0.0.1:{server.server_port}"
    monkeypatch.setattr(settings, "gcs_local_root", None)
    monkeypatch.setattr(settings, "storage_emulator_host", host)
    yield uploads
    server.shutdown()


def test_export_data_uploads_to_storage_emulator(bq, storage_emulator):
    run(
        bq,
        "EXPORT DATA OPTIONS (uri = 'gs://bkt/export/*.csv', format = 'CSV') "
        "AS SELECT 1 AS x",
    )
    assert storage_emulator == {"bkt/export/000000000000.csv": b"x\n1\n"}


def test_export_data_requires_uri(bq):
    with fails(BadRequest, "invalidQuery") as info:
        run(bq, "EXPORT DATA OPTIONS (format = 'CSV') AS SELECT 1 AS x")
    assert "Option 'uri' is missing or empty." in str(info.value)


def test_export_data_rejects_orc(bq, local):
    with fails(BadRequest, "invalidQuery") as info:
        run(
            bq,
            f"EXPORT DATA OPTIONS (uri = 'file://{local}/x-*.orc', format = 'ORC') "
            "AS SELECT 1 AS x",
        )
    assert "'ORC' is not a valid value; failed to set 'format'" in str(info.value)


def test_load_applies_partitioning_and_clustering(bq, dataset):
    table = table_id(dataset)
    config = bigquery.LoadJobConfig(
        schema=[*X, bigquery.SchemaField("d", "DATE")],
        time_partitioning=bigquery.TimePartitioning(field="d"),
        clustering_fields=["x"],
    )
    rows = [{"x": 1, "d": "2020-01-01"}]
    bq.load_table_from_json(rows, table, job_config=config).result()
    loaded = bq.get_table(table)
    partitioning = loaded.time_partitioning
    assert (partitioning.field, partitioning.type_) == ("d", "DAY")
    assert loaded.clustering_fields == ["x"]


def test_load_rejects_unknown_partitioning_field(bq, dataset):
    config = bigquery.LoadJobConfig(
        schema=X, time_partitioning=bigquery.TimePartitioning(field="missing")
    )
    table = table_id(dataset)
    with fails(BadRequest, "invalid"):
        bq.load_table_from_json([{"x": 1}], table, job_config=config).result()


AVRO_SCHEMA = {
    "type": "record",
    "name": "r",
    "fields": [
        {
            "name": "n",
            "type": {
                "type": "bytes",
                "logicalType": "decimal",
                "precision": 10,
                "scale": 2,
            },
        },
        {"name": "ts", "type": {"type": "long", "logicalType": "timestamp-micros"}},
        {"name": "d", "type": {"type": "int", "logicalType": "date"}},
        {"name": "t", "type": {"type": "long", "logicalType": "time-micros"}},
        {
            "name": "dt",
            "type": {"type": "long", "logicalType": "local-timestamp-micros"},
        },
        {"name": "s", "type": ["null", "string"]},
    ],
}
TS = datetime.datetime(2020, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
AVRO_ROW = {
    "n": decimal.Decimal("1.25"),
    "ts": TS,
    "d": datetime.date(2020, 1, 2),
    "t": datetime.time(3, 4, 5),
    "dt": datetime.datetime(2020, 1, 2, 3, 4, 5),
    "s": None,
}


def avro_bytes(schema, records):
    buffer = io.BytesIO()
    fastavro.writer(buffer, schema, records)
    return buffer.getvalue()


def test_load_avro_logical_types(bq, dataset):
    table = table_id(dataset)
    data = avro_bytes(AVRO_SCHEMA, [AVRO_ROW])
    load_file(bq, table, data, source_format="AVRO", use_avro_logical_types=True)
    assert types(bq, table) == [
        "NUMERIC",
        "TIMESTAMP",
        "DATE",
        "TIME",
        "DATETIME",
        "STRING",
    ]
    assert select(bq, table) == [
        (
            decimal.Decimal("1.25"),
            TS,
            datetime.date(2020, 1, 2),
            datetime.time(3, 4, 5),
            datetime.datetime(2020, 1, 2, 3, 4, 5),
            None,
        )
    ]


def test_load_avro_without_logical_types_uses_primitive_types(bq, dataset):
    table = table_id(dataset)
    load_file(bq, table, avro_bytes(AVRO_SCHEMA, [AVRO_ROW]), source_format="AVRO")
    assert types(bq, table) == ["NUMERIC", "INT64", "INT64", "INT64", "INT64", "STRING"]
    assert select(bq, table)[0][:4] == (
        decimal.Decimal("1.25"),
        int(TS.timestamp()) * 1_000_000,
        18263,
        (3 * 3600 + 4 * 60 + 5) * 1_000_000,
    )


def test_load_avro_nested_fields(bq, dataset):
    table = table_id(dataset)
    inner = {
        "type": "record",
        "name": "inner",
        "fields": [{"name": "y", "type": "int"}],
    }
    schema = {
        "type": "record",
        "name": "r",
        "fields": [
            {"name": "rec", "type": inner},
            {"name": "tags", "type": {"type": "array", "items": "string"}},
        ],
    }
    data = avro_bytes(schema, [{"rec": {"y": 1}, "tags": ["a"]}])
    load_file(bq, table, data, source_format="AVRO")
    assert types(bq, table) == ["STRUCT<y INT64>", "ARRAY<STRING>"]
    assert select(bq, table) == [({"y": 1}, ["a"])]


def test_load_orc(bq, dataset):
    table = table_id(dataset)
    buffer = io.BytesIO()
    orc.write_table(pa.table({"x": [1, 2], "s": ["a", "b"]}), buffer)
    load_file(bq, table, buffer.getvalue(), source_format="ORC")
    assert types(bq, table) == ["INT64", "STRING"]
    assert select(bq, table) == [(1, "a"), (2, "b")]


@pytest.mark.parametrize(
    "encoding, codec",
    [
        ("ISO-8859-1", "latin-1"),
        ("UTF-16LE", "utf-16-le"),
        pytest.param(
            "UTF-16BE",
            "utf-16-be",
            marks=pytest.mark.xfail(strict=True, reason="DuckDB reads only UTF-16LE"),
        ),
    ],
)
def test_load_csv_encoding(bq, dataset, encoding, codec):
    table = table_id(dataset)
    schema = [bigquery.SchemaField("s", "STRING")]
    load_file(bq, table, "é\n".encode(codec), schema=schema, encoding=encoding)
    assert select(bq, table) == [("é",)]


def test_extract_avro_deflate(bq, dataset, local):
    extract(
        bq,
        ctas(bq, dataset, 1, 2),
        f"file://{local}/out.avro",
        destination_format=bigquery.DestinationFormat.AVRO,
        compression=bigquery.Compression.DEFLATE,
    )
    with open(local / "out.avro", "rb") as file:
        reader = fastavro.reader(file)
        assert reader.codec == "deflate"
        assert sorted(record["x"] for record in reader) == [1, 2]


@pytest.mark.xfail(strict=True, reason="snappy needs cramjam, not a dependency")
def test_extract_avro_snappy(bq, dataset, local):
    extract(
        bq,
        ctas(bq, dataset, 1),
        f"file://{local}/out.avro",
        destination_format=bigquery.DestinationFormat.AVRO,
        compression=bigquery.Compression.SNAPPY,
    )
    with open(local / "out.avro", "rb") as file:
        assert fastavro.reader(file).codec == "snappy"


def test_extract_creates_missing_directory(bq, dataset, local):
    extract(bq, ctas(bq, dataset, 1), f"file://{local}/new/dir/out.csv")
    assert (local / "new" / "dir" / "out.csv").read_text().splitlines() == ["x", "1"]


def copy_job(bq, source, destination, operation):
    config = bigquery.CopyJobConfig()
    config._properties["copy"]["operationType"] = operation
    return bq.copy_table(source, destination, job_config=config).result()


def test_copy_snapshot(bq, dataset):
    source, snapshot = ctas(bq, dataset, 1), table_id(dataset)
    copy_job(bq, source, snapshot, "SNAPSHOT")
    created = bq.get_table(snapshot)
    assert created.table_type == "SNAPSHOT"
    base = created.snapshot_definition.base_table_reference
    assert f"{base.project}.{base.dataset_id}.{base.table_id}" == source
    assert created.snapshot_definition.snapshot_time is not None
    assert select(bq, snapshot) == [(1,)]
    with pytest.raises(BadRequest, match="is a snapshot, and snapshots are immutable"):
        run(bq, f"INSERT INTO `{snapshot}` VALUES (2)")


def test_copy_clone(bq, dataset):
    source, clone = ctas(bq, dataset, 1), table_id(dataset)
    copy_job(bq, source, clone, "CLONE")
    created = bq.get_table(clone)
    assert created.table_type == "TABLE"
    assert (
        created.clone_definition.base_table_reference.table_id == source.split(".")[-1]
    )
    run(bq, f"INSERT INTO `{clone}` VALUES (2)")
    assert select(bq, clone) == [(1,), (2,)]


def test_copy_restore_snapshot(bq, dataset):
    source, snapshot = ctas(bq, dataset, 1), table_id(dataset)
    restored = table_id(dataset)
    copy_job(bq, source, snapshot, "SNAPSHOT")
    copy_job(bq, snapshot, restored, "RESTORE")
    created = bq.get_table(restored)
    assert (created.table_type, created.snapshot_definition) == ("TABLE", None)
    run(bq, f"INSERT INTO `{restored}` VALUES (2)")
    assert select(bq, restored) == [(1,), (2,)]


@pytest.mark.parametrize(
    "mode, suffix, expected",
    [
        ("AUTO", "", ["INT64", "STRING", "DATE"]),
        ("STRINGS", "", ["INT64", "STRING", "STRING"]),
        ("CUSTOM", "/{dt:DATE}/{country:STRING}", ["INT64", "STRING", "DATE"]),
    ],
)
def test_load_hive_partitioning(bq, dataset, bucket, mode, suffix, expected):
    for day, country in [("2020-01-01", "us"), ("2020-01-02", "uk")]:
        folder = bucket / "data" / f"dt={day}" / f"country={country}"
        folder.mkdir(parents=True)
        (folder / "part.csv").write_text("1\n")
    options = bigquery.HivePartitioningOptions()
    options.mode = mode
    options.source_uri_prefix = f"gs://{bucket.name}/data{suffix}"
    config = bigquery.LoadJobConfig(schema=X, hive_partitioning=options)
    table = table_id(dataset)
    uri = f"gs://{bucket.name}/data/*"
    bq.load_table_from_uri(uri, table, job_config=config).result()
    assert sorted(types(bq, table)) == sorted(expected)
    assert sorted(row["country"] for row in run(bq, f"SELECT * FROM `{table}`")) == [
        "uk",
        "us",
    ]


def test_load_gcs_wildcard_matches_across_directories(bq, dataset, bucket):
    for name in ("a.csv", "sub/b.csv", "sub/deeper/c.csv", "other.txt"):
        (bucket / "dir" / name).parent.mkdir(parents=True, exist_ok=True)
        (bucket / "dir" / name).write_text("1\n")
    table = table_id(dataset)
    config = bigquery.LoadJobConfig(schema=X)
    uri = f"gs://{bucket.name}/dir/*.csv"
    job = bq.load_table_from_uri(uri, table, job_config=config).result()
    assert select(bq, table) == [(1,), (1,), (1,)]
    assert (job.input_files, job.input_file_bytes, job.output_rows) == (3, 6, 3)
    assert job.output_bytes > 0


def test_load_errors_do_not_expose_local_paths(bq, dataset):
    with fails(BadRequest, "invalid") as info:
        load_file(
            bq,
            table_id(dataset),
            b'{"x": "not a number"}\n',
            schema=X,
            source_format="NEWLINE_DELIMITED_JSON",
        )
    message = info.value.message
    assert (
        "Error while reading data, error message: JSON table encountered too many "
        "errors, giving up. Rows: 1; errors: 1." in message
    )
    assert "/uploads/" not in message and "Invalid Input Error" not in message


def test_load_errors_name_the_source_uri(bq, dataset, bucket):
    bucket.mkdir(parents=True)
    (bucket / "bad.json").write_text('{"x": "not a number"}\n')
    config = bigquery.LoadJobConfig(schema=X, source_format="NEWLINE_DELIMITED_JSON")
    with fails(BadRequest, "invalid") as info:
        bq.load_table_from_uri(
            f"gs://{bucket.name}/bad.json", table_id(dataset), job_config=config
        ).result()
    assert f"gs://{bucket.name}/bad.json" in info.value.message
    assert str(bucket) not in info.value.message


def test_load_write_truncate_replaces_schema(bq, dataset):
    table = ctas(bq, dataset, 1)
    schema = [*X, bigquery.SchemaField("y", "STRING")]
    load_json(
        bq, table, [{"x": 2, "y": "b"}], schema=schema, write_disposition=TRUNCATE
    )
    assert select(bq, table) == [(2, "b")]
