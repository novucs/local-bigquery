import contextlib
import sqlite3
from pathlib import Path
from typing import Optional

import sqlglot

from local_bigquery.models import (
    DatasetReference,
    GetQueryResultsResponse,
    Job,
    QueryParameter,
    TableSchema,
)
from local_bigquery.transform import bigquery_schema_to_sql, query_params_to_sqlite

SQLITE_PATH = Path(__file__).parent.parent / "db.sqlite3"


@contextlib.contextmanager
def connection():
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        yield conn
    finally:
        conn.close()


def clear():
    SQLITE_PATH.unlink(missing_ok=True)


@contextlib.contextmanager
def cursor():
    with connection() as conn:
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        finally:
            cur.close()


def migrate():
    with cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT,
                job JSON,
                results JSON
            )
            """
        )


def get_sqlite_table_name(
    table_id: str,
    dataset_id: str = None,
    project_id: str = None,
    default_dataset: DatasetReference = None,
):
    parts = table_id.split(".")
    if len(parts) == 2:
        dataset_id, table_id = parts
    if len(parts) == 3:
        project_id, dataset_id, table_id = parts
    if not dataset_id:
        if not default_dataset:
            raise ValueError("default dataset is required if omitting dataset")
        dataset_id = default_dataset.datasetId
        project_id = default_dataset.projectId
    if not project_id:
        project_id = default_dataset.projectId
    table_name = ".".join(filter(None, [project_id, dataset_id, table_id]))
    table_name = table_name.replace('"', "")
    return f"'{table_name}'"


def list_datasets(project_id):
    tables = list_tables(project_id, None)
    datasets = {table.dataset_id for table in tables}
    return sorted(datasets)


def delete_dataset(project_id, dataset_id):
    tables = list_tables(project_id, dataset_id)
    with connection() as db:
        for table in tables:
            db.execute(f"DROP TABLE {table.table_name}")


def list_tables(project_id, dataset_id):
    with cursor() as cur:
        cur.execute(
            """
            WITH parts AS (
              SELECT
                name,
                instr(name, '.') AS dot1,
                instr(substr(name, instr(name, '.') + 1), '.') AS dot2
              FROM sqlite_master
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
    with cursor() as cur:
        table_name = get_sqlite_table_name(table_id, dataset_id, project_id)
        cur.execute(f"DROP TABLE {table_name}")


def create_table(project_id, dataset_id, table_id, schema: TableSchema):
    with cursor() as cur:
        table_name = f"{project_id}.{dataset_id}.{table_id}"
        bq_sql = bigquery_schema_to_sql(schema.fields, table_name)

        def transformer(node):
            if isinstance(node, sqlglot.exp.Table):
                table_name = get_sqlite_table_name(str(node), dataset_id, project_id)
                return sqlglot.exp.to_table(table_name)
            return node

        expression_tree = sqlglot.parse_one(bq_sql, "bigquery")
        transformed_tree = expression_tree.transform(transformer)
        sqlite_sql = transformed_tree.sql("sqlite")
        cur.execute(sqlite_sql)


def create_job(project_id, job: Job) -> int:
    with cursor() as cur:
        cur.execute(
            """
                INSERT INTO jobs (project_id, job)
                VALUES (?, ?)
            """,
            (project_id, job.model_dump_json()),
        )
        return cur.lastrowid


def update_job(job_id, job: Job, results: Optional[GetQueryResultsResponse] = None):
    with cursor() as cur:
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
    with cursor() as cur:
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
    bq_sql,
    default_dataset: DatasetReference = None,
    parameters: Optional[list[QueryParameter]] = None,
):
    with cursor() as cur:

        def transformer(node):
            if isinstance(node, sqlglot.exp.Table):
                table_name = get_sqlite_table_name(
                    str(node),
                    project_id=project_id,
                    default_dataset=default_dataset,
                )
                return sqlglot.exp.to_table(table_name)
            return node

        expression_tree = sqlglot.parse_one(bq_sql, "bigquery")
        transformed_tree = expression_tree.transform(transformer)
        sqlite_sql = transformed_tree.sql("sqlite")
        cur.execute(sqlite_sql, query_params_to_sqlite(parameters))
        columns = []
        if cur.description:
            columns = [desc[0] for desc in cur.description]
        return cur.fetchall(), columns
