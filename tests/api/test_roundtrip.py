import base64
import datetime
import decimal

from google.cloud import bigquery
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.cases import FAST_RETRY, run, unique

UTC = datetime.timezone.utc
NUMERIC = decimal.Decimal("99999999999999999999999999999.999999999")
SCALARS = {
    "INT64": st.integers(-(2**63), 2**63 - 1),
    "FLOAT64": st.floats(allow_nan=False, allow_infinity=False),
    "NUMERIC": st.decimals(-NUMERIC, NUMERIC, places=9, allow_nan=False).filter(
        lambda value: abs(value) <= NUMERIC
    ),
    "STRING": st.text(st.characters(exclude_categories=("Cs", "Cc")), max_size=12),
    "BYTES": st.binary(max_size=12),
    "BOOL": st.booleans(),
    "DATE": st.dates(),
    "DATETIME": st.datetimes(),
    "TIMESTAMP": st.datetimes(timezones=st.just(UTC)),
    "TIME": st.times(),
}


def _field(name: str):
    kind = st.sampled_from(sorted(SCALARS))
    scalar = kind.map(lambda k: bigquery.SchemaField(name, k))
    array = kind.map(lambda k: bigquery.SchemaField(name, k, mode="REPEATED"))
    record = st.tuples(kind, kind).map(
        lambda ks: bigquery.SchemaField(
            name,
            "RECORD",
            fields=[bigquery.SchemaField("a", ks[0]), bigquery.SchemaField("b", ks[1])],
        )
    )
    return st.one_of(scalar, array, record)


def _value(field: bigquery.SchemaField):
    if field.mode == "REPEATED":
        return st.lists(SCALARS[field.field_type], max_size=3)
    if field.field_type == "RECORD":
        values = st.fixed_dictionaries({f.name: _value(f) for f in field.fields})
        return st.none() | values
    return st.none() | SCALARS[field.field_type]


@st.composite
def tables(draw):
    schema = [draw(_field(f"c{index}")) for index in range(draw(st.integers(1, 4)))]
    row = st.fixed_dictionaries({f.name: _value(f) for f in schema})
    return schema, draw(st.lists(row, min_size=1, max_size=4))


def _wire(value):
    match value:
        case dict():
            return {k: _wire(v) for k, v in value.items()}
        case list():
            return [_wire(v) for v in value]
        case bytes():
            return base64.b64encode(value).decode()
        case decimal.Decimal():
            return str(value)
        case datetime.date() | datetime.time():
            return value.isoformat()
    return value


def _canonical(value):
    match value:
        case dict():
            return tuple(sorted((k, _canonical(v)) for k, v in value.items()))
        case list() | tuple():
            return tuple(map(_canonical, value))
        case decimal.Decimal():
            return value.normalize()
    return value


def _rows(rows) -> list:
    return sorted(map(_canonical, (dict(row) for row in rows)), key=repr)


@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(tables())
def test_values_round_trip(bq, bqstorage, dataset, table):
    schema, rows = table
    table_id = f"{dataset.project}.{dataset.dataset_id}.{unique('roundtrip')}"
    config = bigquery.LoadJobConfig(schema=schema)
    bq.load_table_from_json(_wire(rows), table_id, job_config=config).result(
        retry=FAST_RETRY
    )
    expected = _rows(rows)
    assert _rows(run(bq, f"SELECT * FROM `{table_id}`")) == expected
    assert _rows(bq.list_rows(table_id, retry=FAST_RETRY)) == expected
    arrow = bq.list_rows(table_id).to_arrow(bqstorage_client=bqstorage)
    assert _rows(arrow.to_pylist()) == expected
