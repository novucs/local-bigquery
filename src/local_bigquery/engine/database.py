import contextlib
import functools
import shutil
import threading
from collections.abc import Iterator

import duckdb

from local_bigquery.settings import settings
from local_bigquery.sql import native
from local_bigquery.sql.dialect import FUNCTIONS, MACRO

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
CREATE TABLE IF NOT EXISTS emulator.routines (
    project_id VARCHAR,
    dataset_id VARCHAR,
    routine_id VARCHAR,
    resource JSON NOT NULL,
    PRIMARY KEY (project_id, dataset_id, routine_id)
);
CREATE TABLE IF NOT EXISTS emulator.row_access_policies (
    project_id VARCHAR,
    dataset_id VARCHAR,
    table_id VARCHAR,
    policy_id VARCHAR,
    resource JSON NOT NULL,
    PRIMARY KEY (project_id, dataset_id, table_id, policy_id)
);
CREATE TABLE IF NOT EXISTS emulator.models (
    project_id VARCHAR,
    dataset_id VARCHAR,
    model_id VARCHAR,
    resource JSON NOT NULL,
    PRIMARY KEY (project_id, dataset_id, model_id)
);
CREATE TABLE IF NOT EXISTS emulator.iam_policies (
    resource VARCHAR PRIMARY KEY,
    policy JSON NOT NULL
);
CREATE TABLE IF NOT EXISTS emulator.indexes (
    project_id VARCHAR,
    dataset_id VARCHAR,
    table_id VARCHAR,
    index_id VARCHAR,
    resource JSON NOT NULL,
    PRIMARY KEY (project_id, dataset_id, table_id, index_id)
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
_attached: set[str] = set()
_writers: dict[tuple[str, ...], threading.Lock] = {}
_connection_lock = threading.Lock()


def quote(*parts: str) -> str:
    return ".".join('"' + part.replace('"', '""') + '"' for part in parts)


def connection() -> duckdb.DuckDBPyConnection:
    with _connection_lock:
        return _connect()


@functools.cache
def _connect() -> duckdb.DuckDBPyConnection:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(config={"TimeZone": "UTC"})
    con.execute(
        "SET ducklake_max_retry_count = 100; SET ducklake_retry_wait_ms = 20; "
        "SET ducklake_retry_backoff = 1.05"
    )
    con.execute(f"ATTACH '{settings.data_dir / 'emulator.duckdb'}' AS emulator")
    con.execute(EMULATOR_SCHEMA)
    con.execute("ATTACH ':memory:' AS bq")
    native.register(con)
    for path in FUNCTIONS:
        con.execute(MACRO.sub(r"CREATE MACRO bq.main.\1", path.read_text()))
    for project_id in {p.stem for p in settings.data_dir.glob("*.ducklake")} | {
        settings.default_project_id
    }:
        _attach(con, project_id)
    default = quote(settings.default_project_id, settings.default_dataset_id)
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {default}")
    return con


def _attach(con: duckdb.DuckDBPyConnection, project_id: str):
    path = settings.data_dir / project_id
    source = f"'ducklake:{path}.ducklake' AS {{}} (DATA_PATH '{path}/')"
    if not path.with_name(f"{path.name}.ducklake").exists():
        with duckdb.connect() as scratch:
            scratch.execute(f"ATTACH {source.format('fresh')}")
    con.execute(f"ATTACH IF NOT EXISTS {source.format(quote(project_id))}")
    _attached.add(project_id)


def attach(project_id: str):
    if project_id in _attached:
        return
    with _attach_lock, cursor() as cur:
        _attach(cur, project_id)


@contextlib.contextmanager
def writing(*table: str) -> Iterator[None]:
    key = tuple(part.casefold() for part in table)
    with _attach_lock:
        lock = _writers.setdefault(key, threading.Lock())
    with lock:
        yield


def projects() -> list[str]:
    rows = fetch(
        "SELECT database_name FROM duckdb_databases() WHERE type = 'ducklake' "
        "ORDER BY database_name"
    )
    return [name for (name,) in rows]


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
    if _connect.cache_info().currsize:
        connection().close()
        _connect.cache_clear()
        _attached.clear()
    shutil.rmtree(settings.data_dir, ignore_errors=True)
