import contextlib
import functools
import inspect
from typing import Optional

import duckdb
import sqlglot
from py_mini_racer import MiniRacer

from local_bigquery.errors import NotFoundError, AlreadyExistsError
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
    bigquery_params_to_duckdb_params,
    duckdb_values_to_bigquery_values,
    duckdb_fields_to_bigquery_fields,
)


def strip_quotes(value: Optional[str]) -> Optional[str]:
    value = value.strip("`'\"")
    if not value:
        return None
    return value


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
        context = ""
        if bq_sql:
            context += f"BigQuery SQL:\n{bq_sql}"
        if duckdb_sql:
            context += f"\nDuckDB SQL:\n{duckdb_sql}"
        if params:
            context += f"\nParams:\n{params}\n"
        if "does not exist" in str(e) or "not found" in str(e):
            raise NotFoundError(context + f"DuckDB SQL error:\n{e}")
        if "already exists" in str(e):
            raise AlreadyExistsError(context + f"DuckDB SQL error:\n{e}")
        raise


def list_projects():
    with cursor(settings.default_project_id, settings.default_dataset_id) as cur:
        results = cur.sql("SELECT schema_name FROM duckdb_databases")
        return sorted([row[0] for row in results.fetchall()])


def list_datasets(project_id):
    with cursor(project_id, settings.default_dataset_id) as cur:
        results = cur.sql(
            "SELECT schema_name FROM duckdb_schemas WHERE database_name = $project_id",
            params={"project_id": strip_quotes(project_id)},
        )
        return sorted([row[0] for row in results.fetchall()])


def get_dataset(project_id, dataset_id):
    dataset_id = strip_quotes(dataset_id)
    return dataset_id if dataset_id in list_datasets(project_id) else None


def delete_dataset(project_id, dataset_id):
    with cursor(project_id, dataset_id) as cur:
        project_id = strip_quotes(project_id)
        dataset_id = strip_quotes(dataset_id)
        duckdb_sql = f'DROP SCHEMA "{project_id}"."{dataset_id}" CASCADE'
        with debug_sql(duckdb_sql=duckdb_sql):
            cur.execute(duckdb_sql)


def create_dataset(project_id, dataset_id):
    with cursor(project_id, dataset_id) as cur:
        project_id = strip_quotes(project_id)
        dataset_id = strip_quotes(dataset_id)
        duckdb_sql = f'CREATE SCHEMA "{project_id}"."{dataset_id}"'
        with debug_sql(duckdb_sql=duckdb_sql):
            cur.execute(duckdb_sql)


def list_tables(project_id, dataset_id: Optional[str] = None):
    project_id = strip_quotes(project_id)
    dataset_id = strip_quotes(dataset_id)
    with cursor(project_id, dataset_id) as cur:
        result = cur.sql("SHOW ALL TABLES")
        return sorted(
            [
                {
                    "project_id": row_project_id,
                    "dataset_id": row_dataset_id,
                    "table_name": table_name,
                    "columns": columns,
                }
                for row_project_id, row_dataset_id, table_name, columns, *_ in result.fetchall()
                if project_id == row_project_id
                and (not dataset_id or dataset_id == row_dataset_id)
            ],
            key=lambda x: (x["project_id"], x["dataset_id"], x["table_name"]),
        )


def delete_table(project_id, dataset_id, table_id):
    table_name = build_table_name(project_id, dataset_id, table_id)
    with cursor(project_id, dataset_id) as cur:
        duckdb_sql = f"DROP TABLE {table_name}"
        with debug_sql(duckdb_sql=duckdb_sql):
            cur.execute(duckdb_sql)


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
            (project_id, job.model_dump_json(exclude_unset=True, by_alias=True)),
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
                job.model_dump_json(exclude_unset=True, by_alias=True),
                None
                if not results
                else results.model_dump_json(exclude_unset=True, by_alias=True),
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
            results = GetQueryResultsResponse.model_validate_json(row[1], by_alias=True)
        job = Job.model_validate_json(row[0], by_alias=True)
        return job, results


def query(
    project_id,
    dataset_id,
    bq_sql,
    parameters: Optional[list[QueryParameter]] = None,
) -> tuple[list[TableRow], TableSchema]:
    params = bigquery_params_to_duckdb_params(parameters)
    with cursor(project_id, dataset_id) as cur:
        result = None
        for tree in sqlglot.parse(bq_sql, "bigquery"):
            if is_js_udf(tree):
                bind_js_udf(cur, tree)
                continue

            transform = bigquery_to_duckdb_sqlglot(project_id, dataset_id)
            duckdb_sql = tree.transform(transform).sql("duckdb")
            used_params = {
                node.this.this: params.get(node.this.this)
                for node in tree.dfs()
                if isinstance(node, sqlglot.exp.Parameter)
            }
            with debug_sql(bq_sql=bq_sql, duckdb_sql=duckdb_sql, params=params):
                result = cur.sql(duckdb_sql, params=used_params)

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


def is_js_udf(tree):
    langs = [n for n in tree.dfs() if isinstance(n, sqlglot.exp.LanguageProperty)]
    return langs and langs[0].this.this == "js"


def bind_js_udf(cur, tree):
    assert is_js_udf(tree), f"Supplied tree is not a JS UDF: {tree}"
    name = [n for n in tree.dfs() if isinstance(n, sqlglot.exp.Table)][0].this.this
    params = [
        {
            "name": n.this.this,
            "type": getattr(duckdb.typing, n.kind.sql("duckdb"), duckdb.typing.VARCHAR),
        }
        for n in tree.dfs()
        if isinstance(n, sqlglot.exp.ColumnDef) and n.this
    ]

    def fn(*args):
        param_names_str = ", ".join([p["name"] for p in params])
        ctx = MiniRacer()
        ctx.eval(f"var f = function({param_names_str}) {{ {tree.expression.this} }}")
        return ctx.call("f", *args)

    fn.__name__ = name
    fn.__signature__ = inspect.signature(fn).replace(
        parameters=[
            inspect.Parameter(
                name=param["name"],
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
            for param in params
        ],
    )

    param_types = [p["type"] for p in params]
    returns = [
        getattr(duckdb.typing, n.this.sql("duckdb"), duckdb.typing.VARCHAR)
        for n in tree.dfs()
        if isinstance(n, sqlglot.exp.ReturnsProperty) and n.this
    ]
    return_type = next(iter(returns), None)
    cur.create_function(name, fn, param_types, return_type)


def bigquery_to_duckdb_sqlglot(project_id, dataset_id):
    def transform(node):
        return bigquery_to_duckdb_sqlglot_wildcard(project_id, dataset_id, node)

    return transform


def bigquery_to_duckdb_sqlglot_wildcard(project_id, dataset_id, node):
    if not isinstance(node, sqlglot.exp.Table):
        return node
    if not node.this or not node.this.this:
        return node
    is_wildcard = strip_quotes(node.this.this).endswith("*")
    if not is_wildcard:
        return node
    wildcard = strip_quotes(node.this.this).rstrip("*")
    if node.db:
        dataset_id = strip_quotes(node.db)
    if node.catalog:
        project_id = strip_quotes(node.catalog)
    table_names = {
        t["table_name"]
        for t in list_tables(project_id, dataset_id)
        if t["table_name"].startswith(wildcard)
    }
    selects = [
        sqlglot.select(
            "*",
            sqlglot.alias(
                sqlglot.exp.Literal(
                    this=table_name[len(wildcard) :],
                    is_string=True,
                ),
                "_TABLE_SUFFIX",
            ),
        ).from_(build_table_name(node.catalog, node.db, table_name))
        for table_name in table_names
    ]
    if len(selects) == 0:
        msg = f"No tables found for {node.this.this}"
        if project_id:
            msg += f" in project {project_id}"
        if dataset_id:
            msg += f" in dataset {dataset_id}"
        raise sqlglot.ParseError(msg)
    if len(selects) == 1:
        return selects[0]
    unions = functools.reduce(lambda x, y: x.union(y), selects)
    return sqlglot.exp.paren(unions)
