import contextlib
import functools
import shutil
import threading
from collections.abc import Iterator

import duckdb

from local_bigquery.settings import settings
from local_bigquery.sql.dialect import FUNCTIONS

EMULATOR_SCHEMA = """
CREATE SCHEMA IF NOT EXISTS emulator._results;
CREATE TABLE IF NOT EXISTS emulator.datasets (
    project_id VARCHAR,
    dataset_id VARCHAR,
    resource JSON NOT NULL,
    PRIMARY KEY (project_id, dataset_id)
);
CREATE TABLE IF NOT EXISTS emulator.tables (
    project_id VARCHAR,
    dataset_id VARCHAR,
    table_id VARCHAR,
    resource JSON NOT NULL,
    PRIMARY KEY (project_id, dataset_id, table_id)
);
CREATE TABLE IF NOT EXISTS emulator.js_functions (
    name VARCHAR PRIMARY KEY,
    definition VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS emulator.jobs (
    project_id VARCHAR,
    job_id VARCHAR,
    parent_job_id VARCHAR,
    state VARCHAR NOT NULL,
    creation_time BIGINT NOT NULL,
    resource JSON NOT NULL,
    PRIMARY KEY (project_id, job_id)
);
"""
_attach_lock = threading.Lock()


def quote(*parts: str) -> str:
    return ".".join('"' + part.replace('"', '""') + '"' for part in parts)


@functools.cache
def connection() -> duckdb.DuckDBPyConnection:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(config={"TimeZone": "UTC"})
    con.execute(f"ATTACH '{settings.data_dir / 'emulator.duckdb'}' AS emulator")
    con.execute(EMULATOR_SCHEMA)
    con.execute("ATTACH ':memory:' AS bq; USE bq")
    for path in FUNCTIONS:
        con.execute(path.read_text())
    con.execute("USE memory")
    for path in sorted(settings.data_dir.glob("*.ducklake")):
        _attach(con, path.stem)
    _attach(con, settings.default_project_id)
    default = quote(settings.default_project_id, settings.default_dataset_id)
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {default}")
    return con


def _attach(con: duckdb.DuckDBPyConnection, project_id: str):
    path = settings.data_dir / project_id
    con.execute(
        f"ATTACH IF NOT EXISTS 'ducklake:{path}.ducklake' AS {quote(project_id)} "
        f"(DATA_PATH '{path}/')"
    )


def attach(project_id: str):
    with _attach_lock:
        _attach(connection(), project_id)


def projects() -> list[str]:
    rows = connection().sql(
        "SELECT database_name FROM duckdb_databases() WHERE type = 'ducklake' "
        "ORDER BY database_name"
    )
    return [name for (name,) in rows.fetchall()]


@contextlib.contextmanager
def cursor() -> Iterator[duckdb.DuckDBPyConnection]:
    cur = connection().cursor()
    try:
        yield cur
    finally:
        cur.close()


def fetch(sql: str, params: list | None = None) -> list[tuple]:
    with cursor() as cur:
        return cur.execute(sql, params).fetchall()


def execute(sql: str, params: list | None = None):
    with cursor() as cur:
        cur.execute(sql, params)


def reset():
    if connection.cache_info().currsize:
        connection().close()
        connection.cache_clear()
    shutil.rmtree(settings.data_dir, ignore_errors=True)
