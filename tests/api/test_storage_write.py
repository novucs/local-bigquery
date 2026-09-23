import datetime
import uuid

import pytest
from google.api_core.exceptions import InvalidArgument, NotFound
from google.cloud.bigquery_storage_v1 import types, writer
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

from tests.cases import rows, run, unique

FIELD = descriptor_pb2.FieldDescriptorProto
PENDING = types.WriteStream.Type.PENDING
COMMITTED = types.WriteStream.Type.COMMITTED
BUFFERED = types.WriteStream.Type.BUFFERED
ALREADY_EXISTS, OUT_OF_RANGE, INVALID_ARGUMENT = 6, 11, 3


def schema(**fields: int):
    proto = descriptor_pb2.DescriptorProto(name="Row")
    for number, (name, kind) in enumerate(fields.items(), 1):
        proto.field.add(name=name, number=number, type=kind, label=FIELD.LABEL_OPTIONAL)
    package = f"test_{uuid.uuid4().hex}"
    file = descriptor_pb2.FileDescriptorProto(name=f"{package}.proto", package=package)
    file.message_type.add().CopyFrom(proto)
    pool = descriptor_pool.DescriptorPool()
    pool.Add(file)
    message = pool.FindMessageTypeByName(f"{package}.Row")
    return message_factory.GetMessageClass(message), proto


ROW, PROTO = schema(x=FIELD.TYPE_INT64, s=FIELD.TYPE_STRING)


def request(stream: str, *values: dict, offset: int | None = None):
    data = types.AppendRowsRequest.ProtoData(
        writer_schema=types.ProtoSchema(proto_descriptor=PROTO),
        rows=types.ProtoRows(
            serialized_rows=[ROW(**value).SerializeToString() for value in values]
        ),
    )
    append = types.AppendRowsRequest(write_stream=stream, proto_rows=data)
    if offset is not None:
        append.offset = offset
    return append


def append(bqwrite, stream: str, *values: dict, offset: int | None = None):
    return next(
        iter(bqwrite.append_rows(iter([request(stream, *values, offset=offset)])))
    )


@pytest.fixture
def table(bq, dataset):
    table_id = unique("t")
    run(bq, f"CREATE TABLE {dataset.dataset_id}.{table_id} (x INT64, s STRING)")
    return f"projects/{dataset.project}/datasets/{dataset.dataset_id}/tables/{table_id}"


def select(bq, table: str) -> list[tuple]:
    _, project, _, dataset, _, table_id = table.split("/")
    return sorted(rows(bq, f"SELECT x, s FROM `{project}.{dataset}.{table_id}`"))


def create(bqwrite, table: str, kind) -> str:
    return bqwrite.create_write_stream(
        parent=table, write_stream=types.WriteStream(type_=kind)
    ).name


def test_default_stream_rows_are_visible(bq, bqwrite, table):
    response = append(
        bqwrite, f"{table}/streams/_default", {"x": 1, "s": "a"}, {"x": 2}
    )
    assert response.error.code == 0
    assert select(bq, table) == [(1, "a"), (2, None)]


def test_append_rows_stream_helper(bq, bqwrite, table):
    template = types.AppendRowsRequest(write_stream=f"{table}/streams/_default")
    template.proto_rows = types.AppendRowsRequest.ProtoData(
        writer_schema=types.ProtoSchema(proto_descriptor=PROTO)
    )
    stream = writer.AppendRowsStream(bqwrite, template)
    data = types.AppendRowsRequest.ProtoData(
        rows=types.ProtoRows(serialized_rows=[ROW(x=7).SerializeToString()])
    )
    stream.send(types.AppendRowsRequest(proto_rows=data)).result()
    stream.close()
    assert select(bq, table) == [(7, None)]


def test_timestamps_are_epoch_micros(bq, bqwrite, dataset):
    table_id = unique("ts")
    run(bq, f"CREATE TABLE {dataset.dataset_id}.{table_id} (ts TIMESTAMP)")
    message, proto = schema(ts=FIELD.TYPE_INT64)
    data = types.AppendRowsRequest.ProtoData(
        writer_schema=types.ProtoSchema(proto_descriptor=proto),
        rows=types.ProtoRows(
            serialized_rows=[message(ts=1577836800000000).SerializeToString()]
        ),
    )
    name = f"projects/{dataset.project}/datasets/{dataset.dataset_id}/tables/{table_id}"
    append_request = types.AppendRowsRequest(
        write_stream=f"{name}/streams/_default", proto_rows=data
    )
    next(iter(bqwrite.append_rows(iter([append_request]))))
    assert rows(bq, f"SELECT ts FROM {dataset.dataset_id}.{table_id}") == [
        (datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc),)
    ]


def test_pending_stream_commit(bq, bqwrite, table):
    stream = create(bqwrite, table, PENDING)
    append(bqwrite, stream, {"x": 1}, {"x": 2})
    assert select(bq, table) == []
    assert bqwrite.finalize_write_stream(name=stream).row_count == 2
    response = bqwrite.batch_commit_write_streams(
        types.BatchCommitWriteStreamsRequest(parent=table, write_streams=[stream])
    )
    assert response.commit_time
    assert not response.stream_errors
    assert select(bq, table) == [(1, None), (2, None)]


def test_commit_requires_finalized_stream(bq, bqwrite, table):
    stream = create(bqwrite, table, PENDING)
    append(bqwrite, stream, {"x": 1})
    response = bqwrite.batch_commit_write_streams(
        types.BatchCommitWriteStreamsRequest(parent=table, write_streams=[stream])
    )
    assert response.stream_errors
    assert select(bq, table) == []


def test_committed_stream_offsets(bq, bqwrite, table):
    stream = create(bqwrite, table, COMMITTED)
    assert append(bqwrite, stream, {"x": 1}, offset=0).append_result.offset == 0
    assert append(bqwrite, stream, {"x": 9}, offset=0).error.code == ALREADY_EXISTS
    assert append(bqwrite, stream, {"x": 9}, offset=5).error.code == OUT_OF_RANGE
    assert append(bqwrite, stream, {"x": 2}, offset=1).append_result.offset == 1
    assert select(bq, table) == [(1, None), (2, None)]


def test_buffered_stream_flush(bq, bqwrite, table):
    stream = create(bqwrite, table, BUFFERED)
    append(bqwrite, stream, {"x": 1}, {"x": 2})
    assert select(bq, table) == []
    flush = types.FlushRowsRequest(write_stream=stream, offset=0)
    assert bqwrite.flush_rows(flush).offset == 0
    assert select(bq, table) == [(1, None)]
    bqwrite.flush_rows(types.FlushRowsRequest(write_stream=stream, offset=1))
    assert select(bq, table) == [(1, None), (2, None)]


def test_get_write_stream(bqwrite, table):
    stream = create(bqwrite, table, PENDING)
    fetched = bqwrite.get_write_stream(name=stream)
    assert (fetched.name, fetched.type_) == (stream, PENDING)


def test_unknown_stream(bqwrite, table):
    with pytest.raises(InvalidArgument):
        append(bqwrite, f"{table}/streams/unknown", {"x": 1})


def test_finalize_default_stream(bqwrite, table):
    with pytest.raises(NotFound):
        bqwrite.finalize_write_stream(name=f"{table}/streams/_default")


def test_row_errors(bq, bqwrite, dataset):
    table_id = unique("required")
    run(
        bq, f"CREATE TABLE {dataset.dataset_id}.{table_id} (x INT64 NOT NULL, s STRING)"
    )
    name = f"projects/{dataset.project}/datasets/{dataset.dataset_id}/tables/{table_id}"
    response = append(bqwrite, f"{name}/streams/_default", {"x": 1}, {"s": "a"})
    assert response.error.code == INVALID_ARGUMENT
    assert [error.index for error in response.row_errors] == [1]
    assert rows(bq, f"SELECT x FROM {dataset.dataset_id}.{table_id}") == []
