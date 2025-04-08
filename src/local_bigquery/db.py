import contextlib
import sqlite3
from pathlib import Path
from typing import Optional

import sqlglot

from local_bigquery.models import GetQueryResultsResponse, Job, TableSchema
from local_bigquery.transform import bigquery_schema_to_sql


@contextlib.contextmanager
def connection():
    conn = sqlite3.connect(Path(__file__).parent.parent / "db.sqlite3")
    try:
        yield conn
    finally:
        conn.close()


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
        cur.execute(
            """
            DROP TABLE '{}.{}.{}'
            """.format(project_id, dataset_id, table_id)
        )


def create_table(project_id, dataset_id, table_id, schema: TableSchema):
    with cursor() as cur:
        bq_sql = bigquery_schema_to_sql(
            schema.fields, f"{project_id}.{dataset_id}.{table_id}"
        )
        expression_tree = sqlglot.parse_one(bq_sql)

        def transformer(node):
            if isinstance(node, sqlglot.exp.Table):
                return sqlglot.parse_one(f"`{node.name}`")
            return node

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


def query(project_id, bq_sql):
    with cursor() as cur:
        expression_tree = sqlglot.parse_one(bq_sql)

        def transformer(node):
            if isinstance(node, sqlglot.exp.Table):
                # Combine project_id, dataset_id, and table_name into a single string
                # and remove backticks.
                table_name = str(node).replace("`", "")
                return sqlglot.parse_one(f"'{table_name}'")
            return node

        transformed_tree = expression_tree.transform(transformer)
        sqlite_sql = transformed_tree.sql("sqlite")
        cur.execute(sqlite_sql)
        columns = []
        if cur.description:
            columns = [desc[0] for desc in cur.description]
        return cur.fetchall(), columns
