import datetime
from decimal import Decimal

import pytest
from google.cloud import bigquery

from tests.cases import q

pytestmark = pytest.mark.xdist_group("postgres")

SEED = """
CREATE TABLE person (id SERIAL PRIMARY KEY, name TEXT, description TEXT);
INSERT INTO person (name, description) VALUES
    ('Alice', 'Enjoys hiking and outdoor activities.'),
    ('Bob', 'Avid reader and coffee enthusiast.');
CREATE TABLE types (
    i INTEGER, big BIGINT, n NUMERIC(10, 2), r DOUBLE PRECISION, t TEXT, b BOOLEAN,
    d DATE, ts TIMESTAMP, tstz TIMESTAMPTZ, js JSON, jsb JSONB, bin BYTEA, nul TEXT
);
INSERT INTO types VALUES (
    1, 9007199254740993, 1.50, 2.5, 'x', TRUE, '2024-01-02', '2024-01-02 03:04:05',
    '2024-01-02 03:04:05+02', '{"a": 1}', '{"a": 1}', '\\x6869', NULL
);
"""

PEOPLE = [
    ("Alice", "Enjoys hiking and outdoor activities."),
    ("Bob", "Avid reader and coffee enthusiast."),
]

CASES = [
    q(
        "SELECT person.name, person.description "
        "FROM EXTERNAL_QUERY(@connection, @query) AS person ORDER BY person.name",
        rows=PEOPLE,
        params=[
            bigquery.ScalarQueryParameter("connection", "STRING", "us.default"),
            bigquery.ScalarQueryParameter(
                "query", "STRING", "SELECT name, description FROM person"
            ),
        ],
    ),
    q(
        "SELECT name, description FROM EXTERNAL_QUERY('us.default', '''"
        "WITH cte AS (SELECT p.name, p.description FROM person AS p) SELECT * FROM cte"
        "''') ORDER BY name",
        rows=PEOPLE,
    ),
    q(
        "SELECT name FROM EXTERNAL_QUERY('us.default', "
        "\"SELECT name FROM person WHERE name ~ '^A'\")",
        "Alice",
    ),
    q("SELECT two FROM EXTERNAL_QUERY('us.default', 'SELECT 1::int + 1 AS two')", 2),
    q("SELECT COUNT(*) FROM EXTERNAL_QUERY('us.default', 'SELECT id FROM person')", 2),
    q(
        "WITH scores AS (SELECT 'Alice' AS name, 10 AS score) "
        "SELECT p.name, s.score "
        "FROM EXTERNAL_QUERY('us.default', 'SELECT name FROM person') AS p "
        "JOIN scores AS s USING (name)",
        rows=[("Alice", 10)],
    ),
    q(
        "SELECT * FROM EXTERNAL_QUERY('us.default', "
        "'SELECT i, big, n, r, t, b, d, ts, tstz, js, bin, nul FROM types')",
        rows=[
            (
                1,
                9007199254740993,
                Decimal("1.5"),
                2.5,
                "x",
                True,
                datetime.date(2024, 1, 2),
                datetime.datetime(2024, 1, 2, 3, 4, 5),
                datetime.datetime(2024, 1, 2, 1, 4, 5, tzinfo=datetime.timezone.utc),
                '{"a": 1}',
                b"hi",
                None,
            )
        ],
        types=(
            "INT64",
            "INT64",
            "NUMERIC",
            "FLOAT64",
            "STRING",
            "BOOL",
            "DATE",
            "DATETIME",
            "TIMESTAMP",
            "STRING",
            "BYTES",
            "STRING",
        ),
    ),
    q(
        "SELECT * FROM EXTERNAL_QUERY('us.default', 'SELECT jsb FROM types')",
        error="(?i)unsupported|not supported",
        xfail="unsupported Postgres types not rejected",
    ),
    q("SELECT * FROM EXTERNAL_QUERY('us.nope', 'SELECT 1')", error="(?i)connection"),
    q(
        "SELECT * FROM EXTERNAL_QUERY('us.default', 'SELECT 1; SELECT 2')",
        error="invalidQuery",
    ),
    q(
        "SELECT * FROM EXTERNAL_QUERY('us.default', 'SELECT * FROM missing_table')",
        error="(?i)missing_table",
    ),
]


@pytest.fixture(scope="session", autouse=True)
def postgres(request):
    if request.config.getoption("--endpoint"):
        pytest.skip("EXTERNAL_QUERY is served by the emulator's own Postgres")
    docker = pytest.importorskip("docker")
    try:
        docker.from_env().ping()
    except Exception:
        pytest.skip("docker is unavailable")
    from sqlalchemy import create_engine, text
    from testcontainers.postgres import PostgresContainer

    from local_bigquery.settings import settings

    with PostgresContainer("postgres:17") as container:
        url = container.get_connection_url()
        with create_engine(url).begin() as conn:
            conn.execute(text(SEED))
        settings.postgres_uri = url.replace("+psycopg2", "")
        yield


@pytest.mark.parametrize("case", CASES)
def test_external_query(check, case):
    check(case)
