import contextlib
import sqlite3
from pathlib import Path

import sqlglot

from pybigquery.models import TableSchema
from pybigquery.transform import bigquery_schema_to_sql


@contextlib.contextmanager
def session():
    yield sqlite3.connect(Path(__file__).parent.parent / "db.sqlite3")


def list_datasets(project_id):
    tables = list_tables(project_id, None)
    datasets = {table.dataset_id for table in tables}
    return sorted(datasets)


def delete_dataset(project_id, dataset_id):
    tables = list_tables(project_id, dataset_id)
    with session() as db:
        for table in tables:
            db.execute(f"DROP TABLE {table.table_name}")


def list_tables(project_id, dataset_id):
    with session() as db:
        cursor = db.cursor()
        cursor.execute(
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
        return cursor.fetchall()


def delete_table(project_id, dataset_id, table_id):
    with session() as db:
        # everyone loves sql injection
        db.execute(
            """
            DROP TABLE IF EXISTS `{}.{}.{}`
            """.format(project_id, dataset_id, table_id)
        )
        db.commit()


def create_table(project_id, dataset_id, table_id, schema: TableSchema):
    with session() as db:
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
        db.execute(sqlite_sql)
        db.commit()


def query(project_id, bq_sql):
    with session() as db:
        expression_tree = sqlglot.parse_one(bq_sql)

        def transformer(node):
            if isinstance(node, sqlglot.exp.Table):
                return sqlglot.parse_one(f"`{node.name}`")
            return node

        transformed_tree = expression_tree.transform(transformer)
        sqlite_sql = transformed_tree.sql("sqlite")
        cursor = db.cursor()
        cursor.execute(sqlite_sql)
        return cursor.fetchall()
