import datetime
import json
from decimal import Decimal

import pyarrow as pa
import pytest
from google.api_core.exceptions import FailedPrecondition, NotFound
from google.cloud import bigquery
from google.cloud.bigquery_storage_v1 import types

from tests.cases import run, unique

UTC = datetime.timezone.utc


def path(table: str) -> str:
    reference = bigquery.TableReference.from_string(table)
    return (
        f"projects/{reference.project}/datasets/{reference.dataset_id}"
        f"/tables/{reference.table_id}"
    )


def session(
    bqstorage,
    table: str,
    streams: int = 1,
    data_format=types.DataFormat.ARROW,
    preferred: int = 0,
    **options,
) -> types.ReadSession:
    return bqstorage.create_read_session(
        types.CreateReadSessionRequest(
            parent=f"projects/{bigquery.TableReference.from_string(table).project}",
            read_session=types.ReadSession(
                table=path(table),
                data_format=data_format,
                read_options=types.ReadSession.TableReadOptions(**options),
            ),
            max_stream_count=streams,
            preferred_min_stream_count=preferred,
        )
    )


def read(bqstorage, read_session, stream=None, offset=0) -> list[dict]:
    streams = [stream] if stream else read_session.streams
    return [
        row
        for s in streams
        for row in bqstorage.read_rows(s.name, offset=offset)
        .to_arrow(read_session)
        .to_pylist()
    ]


def avro(bqstorage, table: str, streams: int = 1, **options) -> list[dict]:
    read_session = session(bqstorage, table, streams, types.DataFormat.AVRO, **options)
    return [
        row
        for stream in read_session.streams
        for row in bqstorage.read_rows(stream.name).rows(read_session)
    ]


def xs(rows: list[dict]) -> list[int]:
    return sorted(row["x"] for row in rows)


@pytest.fixture(scope="module")
def numbers(bq, dataset):
    table = f"{dataset.project}.{dataset.dataset_id}.{unique('numbers')}"
    run(
        bq,
        f"CREATE TABLE `{table}` AS "
        "SELECT x, CAST(x AS STRING) AS s FROM UNNEST(GENERATE_ARRAY(1, 10)) AS x",
    )
    return table


def test_list_rows_to_arrow(bq, bqstorage, numbers):
    arrow = bq.list_rows(numbers).to_arrow(bqstorage_client=bqstorage)
    assert sorted(arrow["x"].to_pylist()) == list(range(1, 11))


def test_list_rows_to_dataframe(bq, bqstorage, numbers):
    frame = bq.list_rows(numbers).to_dataframe(bqstorage_client=bqstorage)
    assert sorted(frame["x"].tolist()) == list(range(1, 11))


def test_query_destination(bq, bqstorage):
    job = bq.query("SELECT x FROM UNNEST(GENERATE_ARRAY(1, 5)) AS x")
    job.result()
    arrow = bq.list_rows(job.destination).to_arrow(bqstorage_client=bqstorage)
    assert sorted(arrow["x"].to_pylist()) == [1, 2, 3, 4, 5]


def test_every_type(bq, bqstorage, dataset):
    table = f"{dataset.project}.{dataset.dataset_id}.{unique('types')}"
    run(
        bq,
        f"CREATE TABLE `{table}` AS SELECT 1 AS i, 1.5 AS f, NUMERIC '1.25' AS n, "
        "BIGNUMERIC '1.5' AS bn, TRUE AS b, 'x' AS s, b'ab' AS bytes, "
        "DATE '2020-01-02' AS d, TIME '03:04:05' AS t, "
        "DATETIME '2020-01-02 03:04:05' AS dt, TIMESTAMP '2020-01-02 03:04:05+00' AS ts, "
        """JSON '{"a": 1}' AS j, ST_GEOGPOINT(1, 2) AS g, [1, 2] AS xs, """
        "STRUCT(1 AS a, ['p'] AS bs) AS r, CAST(NULL AS STRING) AS nothing",
    )
    arrow = bq.list_rows(table).to_arrow(bqstorage_client=bqstorage)
    row = arrow.to_pylist()[0]
    assert {k: v for k, v in row.items() if k not in ("j", "g")} == {
        "i": 1,
        "f": 1.5,
        "n": Decimal("1.25"),
        "bn": Decimal("1.5"),
        "b": True,
        "s": "x",
        "bytes": b"ab",
        "d": datetime.date(2020, 1, 2),
        "t": datetime.time(3, 4, 5),
        "dt": datetime.datetime(2020, 1, 2, 3, 4, 5),
        "ts": datetime.datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC),
        "xs": [1, 2],
        "r": {"a": 1, "bs": ["p"]},
        "nothing": None,
    }
    assert json.loads(row["j"]) == {"a": 1}
    assert row["g"] == "POINT(1 2)"
    types_by_name = {f.name: f.type for f in arrow.schema}
    assert types_by_name["n"] == pa.decimal128(38, 9)
    assert types_by_name["ts"] == pa.timestamp("us", tz="UTC")
    assert types_by_name["dt"] == pa.timestamp("us")
    assert types_by_name["bytes"] == pa.binary()
    assert types_by_name["d"] == pa.date32()


def test_selected_fields(bq, bqstorage, numbers):
    selected = [bigquery.SchemaField("s", "STRING")]
    rows = bq.list_rows(numbers, selected_fields=selected)
    assert rows.to_arrow(bqstorage_client=bqstorage).column_names == ["s"]


def test_row_restriction(bqstorage, numbers):
    read_session = session(bqstorage, numbers, row_restriction="x > 8")
    assert xs(read(bqstorage, read_session)) == [9, 10]


def test_multiple_streams(bqstorage, numbers):
    read_session = session(bqstorage, numbers, streams=3)
    assert 1 <= len(read_session.streams) <= 3
    assert xs(read(bqstorage, read_session)) == list(range(1, 11))


def test_split_read_stream(bqstorage, numbers):
    read_session = session(bqstorage, numbers)
    original = read_session.streams[0]
    split = bqstorage.split_read_stream(
        types.SplitReadStreamRequest(name=original.name, fraction=0.5)
    )
    parts = [s for s in (split.primary_stream, split.remainder_stream) if s.name]
    rows = [
        row for s in parts or [original] for row in read(bqstorage, read_session, s)
    ]
    assert xs(rows) == list(range(1, 11))


def test_empty_table_has_no_streams(bq, bqstorage, dataset):
    table = f"{dataset.project}.{dataset.dataset_id}.{unique('empty')}"
    run(bq, f"CREATE TABLE `{table}` (x INT64)")
    assert list(session(bqstorage, table).streams) == []


def test_missing_table(bqstorage, dataset):
    with pytest.raises(NotFound):
        session(
            bqstorage, f"{dataset.project}.{dataset.dataset_id}.{unique('missing')}"
        )


def test_read_from_offset(bqstorage, numbers):
    read_session = session(bqstorage, numbers)
    stream = read_session.streams[0]
    assert len(read(bqstorage, read_session, stream)) == 10
    assert len(read(bqstorage, read_session, stream, offset=4)) == 6


def test_offset_must_already_be_read(bqstorage, numbers):
    read_session = session(bqstorage, numbers)
    with pytest.raises(FailedPrecondition, match="offset 4 has not been allocated yet"):
        read(bqstorage, read_session, read_session.streams[0], offset=4)


def test_small_table_reads_as_one_stream(bqstorage, numbers):
    assert len(session(bqstorage, numbers, streams=4).streams) == 1
    assert len(session(bqstorage, numbers, streams=4, preferred=2).streams) == 1


def test_session_expires_in_the_future(bqstorage, numbers):
    expires = session(bqstorage, numbers).expire_time
    assert expires > datetime.datetime.now(UTC)


def test_read_rows_response_fields(bqstorage, numbers):
    stream = session(bqstorage, numbers).streams[0]
    response = next(iter(bqstorage.read_rows(stream.name)))
    assert response.row_count == 10
    assert response.arrow_record_batch.row_count == 0
    assert types.ReadRowsResponse.pb(response).stats.HasField("progress")


def test_avro_rows(bqstorage, numbers):
    assert xs(avro(bqstorage, numbers)) == list(range(1, 11))


def test_avro_every_type(bq, bqstorage, dataset):
    table = f"{dataset.project}.{dataset.dataset_id}.{unique('avro')}"
    run(
        bq,
        f"CREATE TABLE `{table}` AS SELECT 42 AS i, 3.5 AS f, 'hello' AS s, "
        "TRUE AS b, NUMERIC '123.456789012' AS n, DATE '2026-05-20' AS d, "
        "TIMESTAMP '2026-05-20 12:34:56+00' AS ts, TIME '01:02:03' AS t, "
        "b'ab' AS bytes, STRUCT(10 AS x, 20 AS y) AS point, ['a', 'b'] AS tags, "
        "CAST(NULL AS STRING) AS nothing",
    )
    assert avro(bqstorage, table) == [
        {
            "i": 42,
            "f": 3.5,
            "s": "hello",
            "b": True,
            "n": Decimal("123.456789012"),
            "d": datetime.date(2026, 5, 20),
            "ts": datetime.datetime(2026, 5, 20, 12, 34, 56, tzinfo=UTC),
            "t": datetime.time(1, 2, 3),
            "bytes": b"ab",
            "point": {"x": 10, "y": 20},
            "tags": ["a", "b"],
            "nothing": None,
        }
    ]


def test_avro_selected_fields(bqstorage, numbers):
    rows = avro(bqstorage, numbers, selected_fields=["s"])
    assert sorted(row["s"] for row in rows) == sorted(str(x) for x in range(1, 11))
    assert {tuple(row) for row in rows} == {("s",)}


def test_avro_split_read_stream(bqstorage, numbers):
    read_session = session(bqstorage, numbers, data_format=types.DataFormat.AVRO)
    split = bqstorage.split_read_stream(
        types.SplitReadStreamRequest(name=read_session.streams[0].name, fraction=0.5)
    )
    rows = [
        row
        for stream in (split.primary_stream, split.remainder_stream)
        for row in bqstorage.read_rows(stream.name).rows(read_session)
    ]
    assert xs(rows) == list(range(1, 11))
