import concurrent.futures
import contextlib
import functools

import grpc
from google.cloud.bigquery_storage_v1 import types

from local_bigquery.catalog import row_access
from local_bigquery.errors import from_exception
from local_bigquery.grpc import read, write

CODES = {
    "notFound": grpc.StatusCode.NOT_FOUND,
    "duplicate": grpc.StatusCode.ALREADY_EXISTS,
    "invalid": grpc.StatusCode.INVALID_ARGUMENT,
    "invalidQuery": grpc.StatusCode.INVALID_ARGUMENT,
    "accessDenied": grpc.StatusCode.PERMISSION_DENIED,
    "notImplemented": grpc.StatusCode.UNIMPLEMENTED,
}


def _abort(context: grpc.ServicerContext, error: Exception):
    if isinstance(error, read.StorageError):
        context.abort(error.code, error.message)
    error = from_exception(error)
    context.abort(CODES.get(error.reason, grpc.StatusCode.INTERNAL), error.message)


@contextlib.contextmanager
def _caller(context: grpc.ServicerContext):
    metadata = dict(context.invocation_metadata())
    identity = row_access.identify(
        metadata.get("x-local-bigquery-caller"), metadata.get("x-local-bigquery-groups")
    )
    token = row_access.caller.set(identity)
    try:
        yield
    finally:
        row_access.caller.reset(token)


def _unary(function, request_type, response_type):
    @functools.wraps(function)
    def handler(request, context):
        try:
            with _caller(context):
                return function(request)
        except Exception as error:
            _abort(context, error)

    return grpc.unary_unary_rpc_method_handler(
        handler, request_type.deserialize, response_type.serialize
    )


def _streaming(function, request_type, response_type, bidirectional=False):
    @functools.wraps(function)
    def handler(request, context):
        try:
            with _caller(context):
                yield from function(request)
        except Exception as error:
            _abort(context, error)

    factory = (
        grpc.stream_stream_rpc_method_handler
        if bidirectional
        else grpc.unary_stream_rpc_method_handler
    )
    return factory(handler, request_type.deserialize, response_type.serialize)


SERVICES = {
    "google.cloud.bigquery.storage.v1.BigQueryRead": {
        "CreateReadSession": _unary(
            read.create_session, types.CreateReadSessionRequest, types.ReadSession
        ),
        "ReadRows": _streaming(
            read.read_rows, types.ReadRowsRequest, types.ReadRowsResponse
        ),
        "SplitReadStream": _unary(
            read.split_stream,
            types.SplitReadStreamRequest,
            types.SplitReadStreamResponse,
        ),
    },
    "google.cloud.bigquery.storage.v1.BigQueryWrite": {
        "CreateWriteStream": _unary(
            write.create, types.CreateWriteStreamRequest, types.WriteStream
        ),
        "AppendRows": _streaming(
            write.append,
            types.AppendRowsRequest,
            types.AppendRowsResponse,
            bidirectional=True,
        ),
        "GetWriteStream": _unary(
            write.get, types.GetWriteStreamRequest, types.WriteStream
        ),
        "FinalizeWriteStream": _unary(
            write.finalize,
            types.FinalizeWriteStreamRequest,
            types.FinalizeWriteStreamResponse,
        ),
        "BatchCommitWriteStreams": _unary(
            write.commit,
            types.BatchCommitWriteStreamsRequest,
            types.BatchCommitWriteStreamsResponse,
        ),
        "FlushRows": _unary(
            write.flush, types.FlushRowsRequest, types.FlushRowsResponse
        ),
    },
}


def start(host: str, port: int) -> tuple[grpc.Server, int]:
    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=16))
    server.add_generic_rpc_handlers(
        [grpc.method_handlers_generic_handler(n, h) for n, h in SERVICES.items()]
    )
    port = server.add_insecure_port(f"{host}:{port}")
    server.start()
    return server, port
