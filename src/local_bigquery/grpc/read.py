import re
import uuid
from dataclasses import dataclass

from google.cloud.bigquery_storage_v1 import types

from local_bigquery.catalog import tables
from local_bigquery.engine import database
from local_bigquery.engine import types as engine_types
from local_bigquery.engine.database import quote
from local_bigquery.errors import BigQueryError
from local_bigquery.sql.translate import Context, parse, translate

TABLE = re.compile(r"projects/([^/]+)/datasets/([^/]+)/tables/([^/]+)")
ENCODED = ("GEOGRAPHY", "JSON", "INTERVAL")


@dataclass
class Stream:
    query: str
    start: int
    end: int


_streams: dict[str, Stream] = {}


def table(path: str) -> tuple[str, str, str]:
    if not (match := TABLE.fullmatch(path)):
        raise BigQueryError("invalid", f"Invalid table name: {path}")
    return match[1], match[2], match[3]


def _column(name: str, t) -> str:
    expression = quote(name)
    if engine_types.field(name, t).type in ENCODED:
        expression = engine_types.encode(expression, t)
    return f"{expression} AS {quote(name)}"


def _query(path: str, options: types.ReadSession.TableReadOptions) -> str:
    project_id, dataset_id, table_id = table(path)
    tables.load(project_id, dataset_id, table_id)
    source = tables.name(project_id, dataset_id, table_id)
    selected = {field.casefold() for field in options.selected_fields}
    with database.cursor() as cur:
        relation = cur.sql(f"SELECT * FROM {source} LIMIT 0")
        columns = [
            _column(name, t)
            for name, t in zip(relation.columns, relation.types)
            if not selected or name.casefold() in selected
        ]
    if not options.row_restriction:
        return f"SELECT {', '.join(columns)} FROM {source}"
    context = Context(project_id, dataset_id, temporary={"__read"})
    tree = parse(f"SELECT * FROM __read WHERE {options.row_restriction}")[0]
    filtered, _ = translate(tree, context)
    return (
        f"WITH __read AS (SELECT * FROM {source}) "
        f"SELECT {', '.join(columns)} FROM ({filtered})"
    )


def _stream(name: str, query: str, start: int, end: int) -> types.ReadStream:
    _streams[name] = Stream(query, start, end)
    return types.ReadStream(name=name)


def create_session(request: types.CreateReadSessionRequest) -> types.ReadSession:
    session = request.read_session
    if session.data_format == types.DataFormat.AVRO:
        raise BigQueryError("invalid", "AVRO read sessions are not supported")
    query = _query(session.table, session.read_options)
    with database.cursor() as cur:
        schema = cur.sql(f"SELECT * FROM ({query}) LIMIT 0").to_arrow_table().schema
        (total,) = cur.sql(f"SELECT count(*) FROM ({query})").fetchone()
    count = min(max(request.max_stream_count, 1), total)
    name = (
        f"projects/{table(session.table)[0]}/locations/US/sessions/{uuid.uuid4().hex}"
    )
    return types.ReadSession(
        name=name,
        table=session.table,
        data_format=types.DataFormat.ARROW,
        read_options=session.read_options,
        arrow_schema=types.ArrowSchema(
            serialized_schema=schema.serialize().to_pybytes()
        ),
        estimated_row_count=total,
        streams=[
            _stream(
                f"{name}/streams/{index}",
                query,
                total * index // count,
                total * (index + 1) // count,
            )
            for index in range(count)
        ],
    )


def _lookup(name: str) -> Stream:
    if name not in _streams:
        raise BigQueryError("notFound", f"Not found: Stream {name}")
    return _streams[name]


def read_rows(request: types.ReadRowsRequest):
    stream = _lookup(request.read_stream)
    start = stream.start + request.offset
    with database.cursor() as cur:
        reader = cur.sql(
            f"SELECT * FROM ({stream.query}) LIMIT {stream.end - start} OFFSET {start}"
        ).to_arrow_reader()
        schema = types.ArrowSchema(
            serialized_schema=reader.schema.serialize().to_pybytes()
        )
        for batch in reader:
            batch_message = types.ArrowRecordBatch(
                serialized_record_batch=batch.serialize().to_pybytes(),
                row_count=batch.num_rows,
            )
            yield types.ReadRowsResponse(
                arrow_record_batch=batch_message,
                row_count=batch.num_rows,
                arrow_schema=schema,
            )


def split_stream(
    request: types.SplitReadStreamRequest,
) -> types.SplitReadStreamResponse:
    stream = _lookup(request.name)
    size = stream.end - stream.start
    if size < 2:
        return types.SplitReadStreamResponse()
    cut = stream.start + min(size - 1, max(1, int(size * (request.fraction or 0.5))))
    return types.SplitReadStreamResponse(
        primary_stream=_stream(f"{request.name}.0", stream.query, stream.start, cut),
        remainder_stream=_stream(f"{request.name}.1", stream.query, cut, stream.end),
    )
