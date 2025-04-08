import contextlib
from pathlib import Path
from typing import Optional

import duckdb
import sqlglot

from local_bigquery.models import (
    DatasetReference,
    GetQueryResultsResponse,
    Job,
    QueryParameter,
    Row1,
    TableSchema,
)
from local_bigquery.transform import bigquery_schema_to_sql, query_params_to_duckdb

DB_PATH = Path(__file__).parent.parent / "bigquery.db"


@contextlib.contextmanager
def connection():
    conn = duckdb.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def clear():
    DB_PATH.unlink(missing_ok=True)


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
                id INTEGER PRIMARY KEY,
                project_id TEXT,
                job JSON,
                results JSON
            )
            """
        )
        cur.execute(
            """
            CREATE SEQUENCE IF NOT EXISTS jobs_id_seq;
            """
        )


def get_duckdb_table_name(
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
    table_name = ".".join(filter(None, [dataset_id, table_id]))
    table_name = table_name.replace('"', "")
    table_name = table_name.replace("`", "")
    table_name = table_name.replace("-", "_")
    return table_name


def list_datasets(project_id):
    tables = list_tables(project_id, None)
    datasets = {table.dataset_id for table in tables}
    return sorted(datasets)


def delete_dataset(project_id, dataset_id):
    tables = list_tables(project_id, dataset_id)
    with connection() as cur:
        for table in tables:
            cur.execute(f"DROP TABLE {table.table_name}")


def create_dataset(project_id, dataset_id):
    with connection() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS %s" % dataset_id)


def list_tables(project_id, dataset_id):
    with cursor() as cur:
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
    with cursor() as cur:
        table_name = get_duckdb_table_name(table_id, dataset_id, project_id)
        cur.execute(f"DROP TABLE {table_name}")


def create_table(project_id, dataset_id, table_id, schema: TableSchema):
    with cursor() as cur:
        table_name = f"{project_id}.{dataset_id}.{table_id}"
        bq_sql = bigquery_schema_to_sql(schema.fields, table_name)

        def transformer(node):
            if isinstance(node, sqlglot.exp.Table):
                table_name = get_duckdb_table_name(str(node), dataset_id, project_id)
                return sqlglot.exp.to_table(table_name)
            return node

        expression_tree = sqlglot.parse_one(bq_sql, "bigquery")
        transformed_tree = expression_tree.transform(transformer)
        duckdb_sql = transformed_tree.sql("duckdb")
        cur.execute(duckdb_sql)


def create_job(project_id, job: Job) -> int:
    with cursor() as cur:
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
                table_name = get_duckdb_table_name(
                    str(node),
                    project_id=project_id,
                    default_dataset=default_dataset,
                )
                return sqlglot.exp.to_table(table_name)
            return node

        expression_tree = sqlglot.parse_one(bq_sql, "bigquery")
        transformed_tree = expression_tree.transform(transformer)
        duckdb_sql = transformed_tree.sql("duckdb")
        cur.execute(duckdb_sql, query_params_to_duckdb(parameters))
        columns = []
        if cur.description:
            columns = [desc[0] for desc in cur.description]
        return cur.fetchall(), columns


def tabledata_insert_all(project_id, dataset_id, table_id, rows: list[Row1]):
    table_name = get_duckdb_table_name(table_id, dataset_id, project_id)
    with cursor() as cur:
        for row in rows:
            if not row.json or not row.json.root:
                continue
            columns = {k for k, v in row.json.root.items()}
            columns_str = ", ".join(columns)
            sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({', '.join([f'${col}' for col in columns])})"
            cur.execute(sql, {k: v.root for k, v in row.json.root.items()})
