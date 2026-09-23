import datetime
import functools
import io
import json
import re
import uuid
from dataclasses import dataclass

import fastavro
from google.cloud.bigquery_storage_v1 import types

from local_bigquery.catalog import tables
from local_bigquery.engine import database
from local_bigquery.engine import types as engine_types
from local_bigquery.engine.database import quote
from local_bigquery.errors import BigQueryError
from local_bigquery.models import TableFieldSchema
from local_bigquery.sql.translate import Context, parse, translate

TABLE = re.compile(r"projects/([^/]+)/datasets/([^/]+)/tables/([^/]+)")
ARROW = types.DataFormat.ARROW
AVRO = types.DataFormat.AVRO
ENCODED = {ARROW: ("GEOGRAPHY", "JSON", "INTERVAL")}
ENCODED[AVRO] = (*ENCODED[ARROW], "DATETIME")
STREAM_ROWS = 100_000
SESSION_LIFETIME = datetime.timedelta(hours=6)
AVRO_TYPES = {
    "INTEGER": "long",
    "FLOAT": "double",
    "BOOLEAN": "boolean",
    "STRING": "string",
    "BYTES": "bytes",
    "NUMERIC": {"type": "bytes", "logicalType": "decimal", "precision": 38, "scale": 9},
    "BIGNUMERIC": {
        "type": "bytes",
        "logicalType": "decimal",
        "precision": 77,
        "scale": 38,
    },
    "DATE": {"type": "int", "logicalType": "date"},
    "TIME": {"type": "long", "logicalType": "time-micros"},
    "TIMESTAMP": {"type": "long", "logicalType": "timestamp-micros"},
    "DATETIME": {"type": "string", "logicalType": "datetime"},
    "GEOGRAPHY": {"type": "string", "sqlType": "GEOGRAPHY"},
    "JSON": {"type": "string", "sqlType": "JSON"},
    "INTERVAL": {"type": "string", "sqlType": "INTERVAL"},
}


@dataclass
class Stream:
    query: str
    start: int
    end: int
    avro: str | None


_streams: dict[str, Stream] = {}


def table(path: str) -> tuple[str, str, str]:
    if not (match := TABLE.fullmatch(path)):
        raise BigQueryError("invalid", f"Invalid table name: {path}")
    return match[1], match[2], match[3]


def _avro_type(field: TableFieldSchema) -> dict | str:
    if field.type == "RECORD":
        kind = {
            "type": "record",
            "name": field.name,
            "fields": [_avro_field(f) for f in field.fields or []],
        }
    else:
        kind = AVRO_TYPES[field.type]
    if field.mode == "REPEATED":
        return {"type": "array", "items": kind}
    return kind if field.mode == "REQUIRED" else ["null", kind]


def _avro_field(field: TableFieldSchema) -> dict:
    return {"name": field.name, "type": _avro_type(field)}


@functools.cache
def _parsed(schema: str) -> dict:
    return fastavro.parse_schema(json.loads(schema))


def _column(name: str, t, data_format) -> str:
    field = engine_types.field(name, t)
    expression = quote(name)
    if field.type in ENCODED[data_format]:
        expression = engine_types.encode(expression, t)
    if field.mode == "REPEATED":
        expression = f"coalesce({expression}, [])"
    return f"{expression} AS {quote(name)}"


def _query(path: str, options, data_format) -> tuple[str, list[TableFieldSchema]]:
    project_id, dataset_id, table_id = table(path)
    tables.load(project_id, dataset_id, table_id)
    source = tables.name(project_id, dataset_id, table_id)
    selected = {field.casefold() for field in options.selected_fields}
    with database.cursor() as cur:
        relation = cur.sql(f"SELECT * FROM {source} LIMIT 0")
        chosen = [
            (name, t)
            for name, t in zip(relation.columns, relation.types)
            if not selected or name.casefold() in selected
        ]
    fields = [engine_types.field(name, t) for name, t in chosen]
    columns = ", ".join(_column(name, t, data_format) for name, t in chosen)
    if not options.row_restriction:
        return f"SELECT {columns} FROM {source}", fields
    context = Context(project_id, dataset_id, temporary={"__read"})
    tree = parse(f"SELECT * FROM __read WHERE {options.row_restriction}")[0]
    filtered, _ = translate(tree, context)
    query = (
        f"WITH __read AS (SELECT * FROM {source}) SELECT {columns} FROM ({filtered})"
    )
    return query, fields


def _stream(name: str, stream: Stream) -> types.ReadStream:
    _streams[name] = stream
    return types.ReadStream(name=name)


def create_session(request: types.CreateReadSessionRequest) -> types.ReadSession:
    session = request.read_session
    data_format = AVRO if session.data_format == AVRO else ARROW
    query, fields = _query(session.table, session.read_options, data_format)
    with database.cursor() as cur:
        schema = cur.sql(f"SELECT * FROM ({query}) LIMIT 0").to_arrow_table().schema
        (total,) = cur.sql(f"SELECT count(*) FROM ({query})").fetchone()
    wanted = -(-total // STREAM_ROWS)
    count = min(request.max_stream_count or wanted, wanted)
    name = (
        f"projects/{table(session.table)[0]}/locations/us/sessions/{uuid.uuid4().hex}"
    )
    avro = AVRO == data_format and json.dumps(
        {"type": "record", "name": "__root__", "fields": list(map(_avro_field, fields))}
    )
    size = total * len(fields) * 8
    return types.ReadSession(
        name=name,
        expire_time=datetime.datetime.now(datetime.UTC) + SESSION_LIFETIME,
        table=session.table,
        data_format=data_format,
        read_options=session.read_options,
        estimated_row_count=total,
        estimated_total_bytes_scanned=size,
        estimated_total_physical_file_size=size,
        trace_id=name,
        streams=[
            _stream(
                f"{name}/streams/{index}",
                Stream(
                    query,
                    total * index // count,
                    total * (index + 1) // count,
                    avro or None,
                ),
            )
            for index in range(count)
        ],
        **_schema(avro, schema),
    )


def _schema(avro: str | None, arrow) -> dict:
    if avro:
        return {"avro_schema": types.AvroSchema(schema=avro)}
    return {
        "arrow_schema": types.ArrowSchema(
            serialized_schema=arrow.serialize().to_pybytes()
        )
    }


def _lookup(name: str) -> Stream:
    if name not in _streams:
        raise BigQueryError("notFound", f"Not found: Stream {name}")
    return _streams[name]


def _progress(stream: Stream, before: int, after: int) -> types.StreamStats:
    size = max(stream.end - stream.start, 1)
    return types.StreamStats(
        progress=types.StreamStats.Progress(
            at_response_start=before / size, at_response_end=after / size
        )
    )


def _avro_rows(stream: Stream, batch) -> types.AvroRows:
    buffer = io.BytesIO()
    for row in batch.to_pylist():
        fastavro.schemaless_writer(buffer, _parsed(stream.avro), row)
    return types.AvroRows(serialized_binary_rows=buffer.getvalue())


def read_rows(request: types.ReadRowsRequest):
    stream = _lookup(request.read_stream)
    start = stream.start + request.offset
    with database.cursor() as cur:
        reader = cur.sql(
            f"SELECT * FROM ({stream.query}) LIMIT {stream.end - start} OFFSET {start}"
        ).to_arrow_reader()
        schema = _schema(stream.avro, reader.schema)
        position = start - stream.start
        for batch in reader:
            data = (
                {"avro_rows": _avro_rows(stream, batch)}
                if stream.avro
                else {
                    "arrow_record_batch": types.ArrowRecordBatch(
                        serialized_record_batch=batch.serialize().to_pybytes()
                    )
                }
            )
            yield types.ReadRowsResponse(
                row_count=batch.num_rows,
                stats=_progress(stream, position, position + batch.num_rows),
                **data,
                **schema,
            )
            position += batch.num_rows


def split_stream(
    request: types.SplitReadStreamRequest,
) -> types.SplitReadStreamResponse:
    stream = _lookup(request.name)
    size = stream.end - stream.start
    if size < 2:
        return types.SplitReadStreamResponse()
    cut = stream.start + min(size - 1, max(1, int(size * (request.fraction or 0.5))))
    return types.SplitReadStreamResponse(
        primary_stream=_stream(
            f"{request.name}.0", Stream(stream.query, stream.start, cut, stream.avro)
        ),
        remainder_stream=_stream(
            f"{request.name}.1", Stream(stream.query, cut, stream.end, stream.avro)
        ),
    )
