import base64
import datetime
import decimal
import uuid
from dataclasses import dataclass, field

import grpc
import pyarrow as pa
from google.cloud.bigquery_storage_v1 import types
from google.protobuf import (
    descriptor_pb2,
    descriptor_pool,
    json_format,
    message_factory,
    timestamp_pb2,
)
from google.rpc import status_pb2

from local_bigquery.catalog import tabledata, tables
from local_bigquery.grpc.read import table
from local_bigquery.models import TableFieldSchema

Type = types.WriteStream.Type
EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)
STORAGE_TYPES = {
    "INTEGER": "INT64",
    "FLOAT": "DOUBLE",
    "BOOLEAN": "BOOL",
    "RECORD": "STRUCT",
}


class StorageError(Exception):
    def __init__(self, code: grpc.StatusCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Stream:
    name: str
    table: tuple[str, str, str]
    type: Type
    created: timestamp_pb2.Timestamp | None
    rows: list[dict] = field(default_factory=list)
    count: int = 0
    flushed: int = 0
    finalized: bool = False
    committed: timestamp_pb2.Timestamp | None = None


_streams: dict[str, Stream] = {}


def _now() -> timestamp_pb2.Timestamp:
    now = timestamp_pb2.Timestamp()
    now.GetCurrentTime()
    return now


def _field(field: TableFieldSchema) -> types.TableFieldSchema:
    return types.TableFieldSchema(
        name=field.name,
        type_=STORAGE_TYPES.get(field.type, field.type),
        mode=field.mode,
        fields=[_field(child) for child in field.fields or []],
    )


def _stream(name: str) -> Stream:
    if name.endswith("/streams/_default") and name not in _streams:
        path = name.removesuffix("/streams/_default")
        tables.load(*table(path))
        _streams[name] = Stream(name, table(path), Type.COMMITTED, None)
    if name not in _streams:
        raise StorageError(
            grpc.StatusCode.INVALID_ARGUMENT, f"Invalid stream name. Entity: {name}"
        )
    return _streams[name]


def create(request: types.CreateWriteStreamRequest) -> types.WriteStream:
    reference = table(request.parent)
    tables.load(*reference)
    name = f"{request.parent}/streams/{uuid.uuid4().hex}"
    kind, now = request.write_stream.type_, _now()
    stream = Stream(
        name, reference, kind, now, committed=now if kind == Type.COMMITTED else None
    )
    _streams[name] = stream
    schema = types.TableSchema(fields=[_field(f) for f in tables.columns(*reference)])
    return types.WriteStream(
        name=name,
        type_=kind,
        create_time=stream.created,
        commit_time=stream.committed,
        table_schema=schema,
    )


def get(request: types.GetWriteStreamRequest) -> types.WriteStream:
    stream = _stream(request.name)
    return types.WriteStream(
        name=stream.name,
        type_=stream.type,
        create_time=stream.created,
        commit_time=stream.committed,
        location="us",
    )


def _message_class(proto: descriptor_pb2.DescriptorProto):
    package = f"write_{uuid.uuid4().hex}"
    file = descriptor_pb2.FileDescriptorProto(name=f"{package}.proto", package=package)
    file.message_type.add().CopyFrom(proto)
    pool = descriptor_pool.DescriptorPool()
    pool.Add(file)
    return message_factory.GetMessageClass(
        pool.FindMessageTypeByName(f"{package}.{proto.name}")
    )


def _value(schema: TableFieldSchema, value):
    if value is None:
        return None
    if schema.mode == "REPEATED":
        element = schema.model_copy(update={"mode": "NULLABLE"})
        return [_value(element, item) for item in value]
    if schema.type == "RECORD":
        return _row(schema.fields or [], value)
    if schema.type == "TIMESTAMP" and str(value).lstrip("-").isdigit():
        return (EPOCH + datetime.timedelta(microseconds=int(value))).isoformat()
    if schema.type == "DATE" and isinstance(value, int):
        return (EPOCH.date() + datetime.timedelta(days=value)).isoformat()
    return value


def _row(fields: list[TableFieldSchema], values: dict) -> dict:
    by_name = {f.name.casefold(): f for f in fields}
    return {
        key: _value(by_name[key.casefold()], value)
        if key.casefold() in by_name
        else value
        for key, value in values.items()
    }


def _insert(stream: Stream, rows: list[dict]) -> list[dict]:
    body = {"rows": [{"json": row} for row in rows]}
    response = tabledata.insert_all(*stream.table, body)
    return [
        error
        for error in response.get("insertErrors", [])
        if any(e["reason"] != "stopped" for e in error["errors"])
    ]


def _status(code: grpc.StatusCode, message: str) -> status_pb2.Status:
    return status_pb2.Status(code=code.value[0], message=message)


def _append(
    stream: Stream, rows: list[dict], offset: int | None
) -> types.AppendRowsResponse:
    response = types.AppendRowsResponse(write_stream=stream.name)
    if stream.finalized:
        response.error = _status(
            grpc.StatusCode.INVALID_ARGUMENT, "Stream is finalized"
        )
        return response
    if offset is not None and offset < stream.count:
        response.error = _status(
            grpc.StatusCode.ALREADY_EXISTS, f"Offset {offset} exists"
        )
        return response
    if offset is not None and offset > stream.count:
        response.error = _status(
            grpc.StatusCode.OUT_OF_RANGE, f"Offset {offset} is beyond the end of stream"
        )
        return response
    if stream.type == Type.COMMITTED:
        if errors := _insert(stream, rows):
            response.error = _status(
                grpc.StatusCode.INVALID_ARGUMENT, "Rows are invalid"
            )
            response.row_errors = [
                types.RowError(
                    index=error["index"],
                    code=types.RowError.RowErrorCode.FIELDS_ERROR,
                    message=error["errors"][0]["message"],
                )
                for error in errors
            ]
            return response
    else:
        stream.rows += rows
    result = types.AppendRowsResponse.AppendResult()
    if not stream.name.endswith("/_default"):
        result.offset = stream.count
    stream.count += len(rows)
    response.append_result = result
    return response


def _plain(value):
    match value:
        case dict():
            return {key: _plain(item) for key, item in value.items()}
        case list():
            return [_plain(item) for item in value]
        case bytes():
            return base64.b64encode(value).decode()
        case decimal.Decimal():
            return str(value)
        case datetime.date() | datetime.time():
            return value.isoformat()
    return value


def _decoder(request: types.AppendRowsRequest):
    if "arrow_rows" in request:
        if serialized := request.arrow_rows.writer_schema.serialized_schema:
            schema = pa.ipc.read_schema(pa.py_buffer(serialized))
            return lambda request, fields: [
                _plain(row)
                for row in pa.ipc.read_record_batch(
                    pa.py_buffer(request.arrow_rows.rows.serialized_record_batch),
                    schema,
                ).to_pylist()
            ]
        return None
    descriptor = request.proto_rows.writer_schema.proto_descriptor
    if not descriptor.name:
        return None
    message = _message_class(descriptor)
    return lambda request, fields: [
        _row(
            fields,
            json_format.MessageToDict(
                message.FromString(serialized), preserving_proto_field_name=True
            ),
        )
        for serialized in request.proto_rows.rows.serialized_rows
    ]


def append(requests):
    name, decode = None, None
    for request in requests:
        name = request.write_stream or name
        stream = _stream(name)
        decode = _decoder(request) or decode
        rows = decode(request, tables.columns(*stream.table))
        offset = request.offset if "offset" in request else None
        yield _append(stream, rows, offset)


def finalize(
    request: types.FinalizeWriteStreamRequest,
) -> types.FinalizeWriteStreamResponse:
    if request.name.endswith("/streams/_default"):
        raise StorageError(
            grpc.StatusCode.NOT_FOUND,
            f"Requested entity was not found. Entity: {request.name}",
        )
    stream = _stream(request.name)
    stream.finalized = True
    return types.FinalizeWriteStreamResponse(row_count=stream.count)


def commit(
    request: types.BatchCommitWriteStreamsRequest,
) -> types.BatchCommitWriteStreamsResponse:
    streams = [_stream(name) for name in request.write_streams]
    errors = [
        types.StorageError(
            code=types.StorageError.StorageErrorCode.INVALID_STREAM_STATE,
            entity=stream.name,
            error_message="Stream is not finalized",
        )
        for stream in streams
        if stream.type != Type.PENDING or not stream.finalized or stream.committed
    ]
    if errors:
        return types.BatchCommitWriteStreamsResponse(stream_errors=errors)
    now = _now()
    for stream in streams:
        _insert(stream, stream.rows)
        stream.committed = now
    return types.BatchCommitWriteStreamsResponse(commit_time=now)


def flush(request: types.FlushRowsRequest) -> types.FlushRowsResponse:
    stream = _stream(request.write_stream)
    offset = request.offset if "offset" in request else len(stream.rows) - 1
    if (
        stream.type != Type.BUFFERED
        or offset >= len(stream.rows)
        or offset < stream.flushed
    ):
        raise StorageError(
            grpc.StatusCode.OUT_OF_RANGE,
            f"Offset {offset} is beyond the end of the stream Entity: {stream.name}",
        )
    _insert(stream, stream.rows[stream.flushed : offset + 1])
    stream.flushed = offset + 1
    return types.FlushRowsResponse(offset=offset)
