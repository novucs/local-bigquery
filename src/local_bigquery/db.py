import contextlib
import logging
from typing import Optional

import duckdb
import sqlglot

from local_bigquery.models import (
    GetQueryResultsResponse,
    Job,
    QueryParameter,
    Row1,
    TableSchema,
    TableRow,
)
from local_bigquery.settings import settings
from local_bigquery.transform import (
    bigquery_schema_to_sql,
    fill_missing_fields,
    bigquery_params_to_duckdb_param,
    duckdb_values_to_bigquery_values,
    duckdb_fields_to_bigquery_fields,
)


def strip_quotes(value: str) -> str:
    return value.strip("`'\"")


def build_table_name(
    project_id: Optional[str], dataset_id: Optional[str], table_id: str
) -> str:
    parts = [project_id, dataset_id, table_id]
    parts = [strip_quotes(part) for part in parts if part if part]
    return ".".join([f'"{part}"' for part in parts])


@contextlib.contextmanager
def connection(project_id: Optional[str] = None):
    project_id = strip_quotes(project_id or settings.default_project_id)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    dbs = {db.stem for db in settings.data_dir.glob("*.db")}
    default_dbs = {
        project_id,
        settings.default_project_id,
        settings.internal_project_id,
    }
    for db in default_dbs - dbs:
        conn = duckdb.connect(settings.data_dir / f"{db}.db")
        try:
            if db == settings.internal_project_id:
                migrate(conn)
            if db == settings.default_project_id:
                dataset = (
                    f'"{settings.default_project_id}"."{settings.default_dataset_id}"'
                )
                conn.execute(f"CREATE SCHEMA IF NOT EXISTS {dataset}")
        finally:
            conn.close()
    dbs |= default_dbs
    conn = duckdb.connect()
    try:
        for db in dbs:
            conn.execute(f"ATTACH '{settings.data_dir / db}.db' AS \"{db}\"")
        yield conn
    finally:
        conn.close()


def reset():
    for db in settings.data_dir.glob("*.db"):
        db.unlink()


@contextlib.contextmanager
def cursor(project_id: Optional[str] = None, dataset_id: Optional[str] = None):
    project_id = strip_quotes(project_id)
    dataset_id = strip_quotes(dataset_id or "main")
    with connection(project_id) as conn:
        cur = conn.cursor()
        try:
            cur.execute(f'USE "{project_id}"."{dataset_id}"')
        except duckdb.CatalogException:
            cur.execute(f'USE "{project_id}"."main"')
        try:
            yield cur
            conn.commit()
        finally:
            cur.close()


def migrate(conn):
    dataset = f'"{settings.internal_project_id}"."{settings.internal_dataset_id}"'
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {dataset}")
    cur = conn.cursor()
    cur.execute(f"USE {dataset}")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY,
            project_id TEXT,
            job JSON,
            results JSON
        )
        """
    )
    cur.execute("CREATE SEQUENCE IF NOT EXISTS jobs_id_seq")


@contextlib.contextmanager
def debug_sql(
    *,
    bq_sql: Optional[str] = None,
    duckdb_sql: Optional[str] = None,
    params: Optional[dict] = None,
):
    try:
        yield
    except duckdb.Error as e:
        logging.error("DuckDB SQL error:")
        logging.error(e)
        if bq_sql:
            logging.error("BigQuery SQL:")
            logging.error(bq_sql)
        if duckdb_sql:
            logging.error("DuckDB SQL:")
            logging.error(duckdb_sql)
        if params:
            logging.error("Params:")
            logging.error(params)
        raise


def list_datasets(project_id):
    tables = list_tables(project_id, None)
    datasets = {table.dataset_id for table in tables}
    return sorted(datasets)


def delete_dataset(project_id, dataset_id):
    tables = list_tables(project_id, dataset_id)
    with cursor(project_id, dataset_id) as cur:
        for table in tables:
            cur.execute(f'DROP TABLE "{table.table_name}"')


def create_dataset(project_id, dataset_id):
    with cursor(project_id, dataset_id) as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {dataset_id}")


def list_tables(project_id, dataset_id):
    with cursor(project_id, dataset_id) as cur:
        cur.execute(
            """
            WITH parts AS (
              SELECT
                name,
                instr(name, '.') AS dot1,
                instr(substr(name, instr(name, '.') + 1), '.') AS dot2
              FROM duckdb_master
              WHERE type = 'table'
            )
            SELECT
              substr(name, 1, dot1 - 1) AS project_id,
              substr(name, dot1 + 1, dot2 - 1) AS dataset_id,
              substr(name, dot1 + dot2 + 1) AS table_name
            FROM parts
            WHERE project_id = ? AND dataset_id = ?
            """,
            (project_id, dataset_id),
        )
        return cur.fetchall()


def delete_table(project_id, dataset_id, table_id):
    table_name = build_table_name(project_id, dataset_id, table_id)
    with cursor(project_id, dataset_id) as cur:
        cur.execute(f"DROP TABLE {table_name}")


def create_table(project_id, dataset_id, table_id, schema: TableSchema):
    table_name = build_table_name(project_id, dataset_id, table_id)
    with cursor(project_id, dataset_id) as cur:
        bq_sql = bigquery_schema_to_sql(schema.fields, table_name)
        duckdb_sql = sqlglot.transpile(bq_sql, read="bigquery", write="duckdb")[0]
        with debug_sql(bq_sql=bq_sql, duckdb_sql=duckdb_sql):
            cur.execute(duckdb_sql)


def create_job(project_id, job: Job) -> int:
    with cursor(settings.internal_project_id, settings.internal_dataset_id) as cur:
        cur.execute(
            """
                INSERT INTO jobs (id, project_id, job)
                VALUES (nextval('jobs_id_seq'), ?, ?)
                RETURNING id
            """,
            (project_id, job.model_dump_json()),
        )
        return cur.fetchall()[0][0]


def update_job(job_id, job: Job, results: Optional[GetQueryResultsResponse] = None):
    with cursor(settings.internal_project_id, settings.internal_dataset_id) as cur:
        cur.execute(
            """
                UPDATE jobs
                SET job = ?, results = ?
                WHERE id = ?
            """,
            (
                job.model_dump_json(),
                None if not results else results.model_dump_json(),
                job_id,
            ),
        )


def get_job(project_id, job_id):
    with cursor(settings.internal_project_id, settings.internal_dataset_id) as cur:
        cur.execute(
            """
                SELECT job, results
                FROM jobs
                WHERE id = ? AND project_id = ?
            """,
            (job_id, project_id),
        )
        row = cur.fetchone()
        if not row:
            return None, None
        results = None
        if row[1]:
            results = GetQueryResultsResponse.model_validate_json(row[1])
        job = Job.model_validate_json(row[0])
        return job, results


def query(
    project_id,
    dataset_id,
    bq_sql,
    parameters: Optional[list[QueryParameter]] = None,
) -> tuple[list[TableRow], TableSchema]:
    with cursor(project_id, dataset_id) as cur:
        duckdb_sql = sqlglot.transpile(bq_sql, "bigquery", write="duckdb")[0]
        params = bigquery_params_to_duckdb_param(parameters)

        with debug_sql(bq_sql=bq_sql, duckdb_sql=duckdb_sql, params=params):
            result = cur.sql(duckdb_sql, params=params)

        if result is None:
            return [], TableSchema(fields=[], foreignTypeInfo=None)

        duckdb_fields = list(zip(result.columns, result.types))
        bigquery_fields = duckdb_fields_to_bigquery_fields(duckdb_fields)
        bigquery_schema = TableSchema(fields=bigquery_fields, foreignTypeInfo=None)

        duckdb_rows = result.fetchall()
        bigquery_rows = duckdb_values_to_bigquery_values(duckdb_rows)

        return bigquery_rows, bigquery_schema


def tabledata_insert_all(project_id, dataset_id, table_id, rows: list[Row1]):
    table_name = build_table_name(project_id, dataset_id, table_id)
    with cursor(project_id, dataset_id) as cur:
        for row in rows:
            if not row.json_ or not row.json_.root:
                continue
            columns = {f'"{k}"' for k, v in row.json_.root.items()}
            columns_str = ", ".join(columns)
            sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({', '.join([f'${col}' for col in columns])})"
            params = {k: v.root for k, v in row.json_.root.items()}
            params = fill_missing_fields(params)
            with debug_sql(duckdb_sql=sql, params=params):
                cur.execute(sql, params)
