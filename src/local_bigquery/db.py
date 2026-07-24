import contextlib
import fcntl
import functools
import inspect
import json
import shutil
import threading
from datetime import datetime
from functools import lru_cache
from typing import Optional

import duckdb
import sqlglot
from duckdb.sqltypes import DuckDBPyType
from py_mini_racer import MiniRacer
from sqlglot.optimizer.qualify_tables import qualify_tables

from local_bigquery.errors import NotFoundError, AlreadyExistsError
from local_bigquery.models import (
    GetQueryResultsResponse,
    Job,
    QueryParameter,
    Row1,
    TableSchema,
    TableRow,
    Dataset,
    DatasetReference,
    LinkedDatasetMetadata,
    LinkState,
    StorageBillingModel,
    Project,
    ProjectReference,
)
from local_bigquery.settings import settings
from local_bigquery.transform import (
    bigquery_params_to_duckdb_params,
    bigquery_schema_to_duckdb_sql,
    duckdb_fields_to_bigquery_fields,
    duckdb_values_to_bigquery_values,
    quote_identifier,
    strip_quotes,
    table_expr,
)


def attach_project(conn, project):
    metadata = settings.data_dir / f"{project}.ducklake"
    data_path = settings.data_dir / f"{project}"
    conn.execute(
        f"ATTACH IF NOT EXISTS 'ducklake:sqlite:{metadata}' "
        f"AS {quote_identifier(project)} (DATA_PATH '{data_path}')"
    )


@lru_cache(maxsize=None)
def lock_data_dir():
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    handle = (settings.data_dir / ".lock").open("w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise RuntimeError(
            f"{settings.data_dir} is already in use by another process. DuckLake's "
            f"SQLite catalog supports a single writer, so concurrent processes "
            f"silently lose writes. Run one server process per data directory."
        )
    return handle


@lru_cache(maxsize=None)
def get_default_connection():
    lock_data_dir()
    found_projects = {project.stem for project in settings.data_dir.glob("*.ducklake")}
    projects = found_projects | {
        settings.default_project_id,
        settings.internal_project_id,
    }
    conn = duckdb.connect()
    conn.execute("INSTALL ducklake;")
    conn.execute("INSTALL sqlite;")
    for project in projects:
        attach_project(conn, project)
        if project in found_projects:
            continue
        if project == settings.internal_project_id:
            migrate(conn)
        if project == settings.default_project_id:
            dataset = table_expr(
                settings.default_project_id, settings.default_dataset_id
            )
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {dataset.sql('duckdb')}")
    return conn


@lru_cache(maxsize=None)
def get_default_connection_with_project(project_id: Optional[str] = None):
    conn = get_default_connection()
    attach_project(conn, project_id)
    return conn


def reset():
    shutil.rmtree(settings.data_dir, ignore_errors=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)


catalog_lock = threading.RLock()


@contextlib.contextmanager
def cursor(project_id: Optional[str] = None, dataset_id: Optional[str] = None):
    project_id = strip_quotes(project_id) or settings.default_project_id
    dataset_id = strip_quotes(dataset_id) or "main"
    conn = get_default_connection_with_project(project_id)
    with catalog_lock:
        cur = conn.cursor()
        try:
            cur.execute(f"USE {table_expr(project_id, dataset_id).sql('duckdb')}")
        except duckdb.CatalogException:
            cur.execute(f"USE {table_expr(project_id, 'main').sql('duckdb')}")
        try:
            yield cur
            cur.commit()
        except Exception:
            with contextlib.suppress(duckdb.Error):
                cur.rollback()
            raise
        finally:
            cur.close()


@contextlib.contextmanager
def internal_cursor():
    with cursor(settings.internal_project_id, settings.internal_dataset_id) as cur:
        yield cur


def migrate(conn):
    dataset = table_expr(settings.internal_project_id, settings.internal_dataset_id)
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {dataset.sql('duckdb')}")
    conn.execute(f"USE {dataset.sql('duckdb')}")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS datasets (
            project_id TEXT,
            dataset_id TEXT,
            item JSON
        );
        CREATE TABLE IF NOT EXISTS jobs (
            project_id TEXT,
            job_id TEXT,
            item JSON
        );
        CREATE TABLE IF NOT EXISTS query_results (
            project_id TEXT,
            job_id TEXT,
            item JSON
        );
        """
    )


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
            context += f"BigQuery SQL:\n{bq_sql}\n"
        if duckdb_sql:
            context += f"DuckDB SQL:\n{duckdb_sql}\n"
        if params:
            context += f"Params:\n{params}\n"
        if "does not exist" in str(e) or "not found" in str(e):
            raise NotFoundError(context + f"DuckDB SQL error:\n{e}")
        if "already exists" in str(e):
            raise AlreadyExistsError(context + f"DuckDB SQL error:\n{e}")
        raise


def run(
    cur, duckdb_sql: str, params: Optional[dict] = None, bq_sql: Optional[str] = None
):
    with debug_sql(bq_sql=bq_sql, duckdb_sql=duckdb_sql, params=params):
        return cur.sql(duckdb_sql, params=params or {})


def store_where(keys: dict) -> str:
    return " AND ".join(f"{key} = ${key}" for key in keys)


def store_list(table: str, model, **keys) -> list:
    keys = {key: strip_quotes(value) for key, value in keys.items()}
    with internal_cursor() as cur:
        rows = cur.sql(
            f"SELECT item FROM {table} WHERE {store_where(keys)}", params=keys
        ).fetchall()
    return [model.model_validate_json(row[0], by_alias=True) for row in rows]


def store_get(table: str, model, **keys):
    return next(iter(store_list(table, model, **keys)), None)


def store_put(table: str, item, **keys):
    keys = {key: strip_quotes(value) for key, value in keys.items()}
    columns = ", ".join([*keys, "item"])
    values = ", ".join(f"${key}" for key in [*keys, "item"])
    with internal_cursor() as cur:
        cur.execute(f"DELETE FROM {table} WHERE {store_where(keys)}", keys)
        cur.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({values})",
            {**keys, "item": item.model_dump_json(exclude_unset=True, by_alias=True)},
        )
    return item


def store_delete(table: str, **keys):
    keys = {key: strip_quotes(value) for key, value in keys.items()}
    with internal_cursor() as cur:
        cur.execute(f"DELETE FROM {table} WHERE {store_where(keys)}", keys)


def list_projects() -> list[Project]:
    with cursor() as cur:
        results = cur.sql("SELECT database_name FROM duckdb_databases")
        project_ids = sorted(row[0] for row in results.fetchall())
    return [
        Project(
            friendlyName=project_id,
            id=project_id,
            numericId=str(hash(project_id)),
            projectReference=ProjectReference(projectId=project_id),
        )
        for project_id in project_ids
    ]


def timestamp_now() -> str:
    return str(int(datetime.now().timestamp()))


def list_datasets(project_id) -> list[Dataset]:
    project_id = strip_quotes(project_id)
    with cursor(project_id) as cur:
        results = cur.sql(
            "SELECT schema_name FROM duckdb_schemas WHERE database_name = $project_id",
            params={"project_id": project_id},
        )
        dataset_ids = sorted(row[0] for row in results.fetchall())
    return [get_dataset(project_id, dataset_id) for dataset_id in dataset_ids]


def get_dataset(
    project_id: Optional[str], dataset_id: Optional[str]
) -> Optional[Dataset]:
    project_id = strip_quotes(project_id)
    dataset_id = strip_quotes(dataset_id)
    with cursor(project_id) as cur:
        found = cur.sql(
            """
            SELECT schema_name
            FROM duckdb_schemas
            WHERE database_name = $project_id AND schema_name = $dataset_id
            """,
            params={"project_id": project_id, "dataset_id": dataset_id},
        ).fetchone()
    if not found:
        return None
    dataset = store_get(
        "datasets", Dataset, project_id=project_id, dataset_id=dataset_id
    )
    if dataset is not None:
        return dataset
    now = timestamp_now()
    dataset = Dataset(
        creationTime=now,
        datasetReference=DatasetReference(
            datasetId=dataset_id,
            projectId=project_id,
        ),
        friendlyName=dataset_id,
        id=dataset_id,
        isCaseInsensitive=False,
        lastModifiedTime=now,
        linkedDatasetMetadata=LinkedDatasetMetadata(
            linkState=LinkState.UNLINKED,
        ),
        location="US",
        selfLink=f"/bigquery/v2/projects/{project_id}/datasets/{dataset_id}",
        storageBillingModel=StorageBillingModel.LOGICAL,
        type="DEFAULT",
    )
    return store_put("datasets", dataset, project_id=project_id, dataset_id=dataset_id)


def create_dataset(project_id, dataset_id, dataset: Dataset) -> Dataset:
    if get_dataset(project_id, dataset_id):
        raise AlreadyExistsError(f"Dataset {dataset_id} already exists")
    store_put("datasets", dataset, project_id=project_id, dataset_id=dataset_id)
    with cursor(project_id, dataset_id) as cur:
        run(cur, f"CREATE SCHEMA {table_expr(project_id, dataset_id).sql('duckdb')}")
    return dataset


def update_dataset(project_id, dataset_id, dataset: Dataset) -> Dataset:
    if not get_dataset(project_id, dataset_id):
        raise NotFoundError(f"Dataset {dataset_id} does not exist")
    return store_put("datasets", dataset, project_id=project_id, dataset_id=dataset_id)


def delete_dataset(project_id, dataset_id):
    with cursor(project_id, dataset_id) as cur:
        run(
            cur,
            f"DROP SCHEMA {table_expr(project_id, dataset_id).sql('duckdb')} CASCADE",
        )
    store_delete("datasets", project_id=project_id, dataset_id=dataset_id)


def list_tables(project_id, dataset_id: Optional[str] = None) -> list[str]:
    with cursor(project_id, dataset_id) as cur:
        result = cur.sql("SHOW TABLES")
        return [table_name for table_name, *_ in result.fetchall()]


def create_table(project_id, dataset_id, table_id, schema: TableSchema):
    table = table_expr(project_id, dataset_id, table_id)
    with cursor(project_id, dataset_id) as cur:
        run(cur, bigquery_schema_to_duckdb_sql(schema.fields, table))


def delete_table(project_id, dataset_id, table_id):
    table = table_expr(project_id, dataset_id, table_id)
    with cursor(project_id, dataset_id) as cur:
        run(cur, f"DROP TABLE {table.sql('duckdb')}")


def create_job(project_id: str, job_id: str, job: Job) -> Job:
    if get_job(project_id, job_id):
        raise AlreadyExistsError(f"Job {job_id} already exists")
    return store_put("jobs", job, project_id=project_id, job_id=job_id)


def get_job(project_id: str, job_id: str) -> Optional[Job]:
    return store_get("jobs", Job, project_id=project_id, job_id=job_id)


def list_jobs(project_id: str) -> list[Job]:
    return store_list("jobs", Job, project_id=project_id)


def delete_job(project_id: str, job_id: str):
    store_delete("jobs", project_id=project_id, job_id=job_id)


def set_query_results(
    project_id: str,
    job_id: str,
    query_results: GetQueryResultsResponse,
) -> GetQueryResultsResponse:
    return store_put(
        "query_results", query_results, project_id=project_id, job_id=job_id
    )


def get_query_results(
    project_id: str, job_id: str
) -> Optional[GetQueryResultsResponse]:
    return store_get(
        "query_results", GetQueryResultsResponse, project_id=project_id, job_id=job_id
    )


def query(
    project_id,
    dataset_id,
    bq_sql,
    parameters: Optional[list[QueryParameter]] = None,
) -> tuple[list[TableRow], TableSchema]:
    params = bigquery_params_to_duckdb_params(parameters)
    trees = sqlglot.parse(bq_sql, "bigquery")
    with cursor(project_id, dataset_id) as cur:
        result = None
        if has_external_query(trees):
            setup_postgres_connection(cur)
        transform = bigquery_to_duckdb_sqlglot(project_id, dataset_id, params)
        for tree in trees:
            if not tree:
                continue
            if is_js_udf(tree):
                bind_js_udf(cur, tree)
                continue
            tree = tree.transform(transform)
            duckdb_sql = tree.sql("duckdb")
            used_params = {
                node.this.this: params.get(node.this.this)
                for node in tree.dfs()
                if isinstance(node, sqlglot.exp.Parameter)
            }
            result = run(cur, duckdb_sql, params=used_params, bq_sql=bq_sql)

        if result is None:
            return [], TableSchema(fields=[], foreignTypeInfo=None)

        duckdb_fields = list(zip(result.columns, result.types))
        bigquery_schema = TableSchema(
            fields=duckdb_fields_to_bigquery_fields(duckdb_fields),
            foreignTypeInfo=None,
        )
        bigquery_rows = duckdb_values_to_bigquery_values(result.fetchall())
        return bigquery_rows, bigquery_schema


def tabledata_insert_all(project_id, dataset_id, table_id, rows: list[Row1]):
    jsons = [row.json_ for row in rows if row.json_ and row.json_.root]
    keys = list(dict.fromkeys(k for j in jsons for k in j.root))
    if not keys:
        return
    table = table_expr(project_id, dataset_id, table_id).sql("duckdb")
    with cursor(project_id, dataset_id) as cur:
        empty = cur.sql(f"SELECT * FROM {table} LIMIT 0")
        types = {n.casefold(): str(t) for n, t in zip(empty.columns, empty.types)}
        columns = [
            (quote_identifier(k), types.get(k.casefold(), "VARCHAR")) for k in keys
        ]
        fields = [f"{q} {'VARCHAR' if t == 'JSON' else t}" for q, t in columns]
        selects = [
            f"CAST(r.{q} AS JSON)" if t == "JSON" else f"r.{q}" for q, t in columns
        ]
        sql = (
            f"INSERT INTO {table} ({', '.join(q for q, _ in columns)}) "
            f"SELECT {', '.join(selects)} "
            f"FROM (SELECT unnest(from_json($payload, $spec)) AS r)"
        )
        run(
            cur,
            sql,
            params={
                "payload": f"[{','.join(j.model_dump_json() for j in jsons)}]",
                "spec": json.dumps([f"STRUCT({', '.join(fields)})"]),
            },
        )


def duckdb_type(node) -> DuckDBPyType:
    try:
        return DuckDBPyType(node.sql("duckdb"))
    except duckdb.Error:
        return DuckDBPyType("VARCHAR")


def is_js_udf(tree):
    langs = [n for n in tree.dfs() if isinstance(n, sqlglot.exp.LanguageProperty)]
    return langs and langs[0].name == "js"


def bind_js_udf(cur, tree):
    assert is_js_udf(tree), f"Supplied tree is not a JS UDF: {tree}"
    name = [n for n in tree.dfs() if isinstance(n, sqlglot.exp.Table)][0].name
    params = [
        {"name": n.name, "type": duckdb_type(n.kind)}
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

    returns = [
        duckdb_type(n.this)
        for n in tree.dfs()
        if isinstance(n, sqlglot.exp.ReturnsProperty) and n.this
    ]
    cur.create_function(
        name, fn, [p["type"] for p in params], next(iter(returns), None)
    )


def bigquery_to_duckdb_sqlglot(project_id, dataset_id, params: Optional[dict] = None):
    def transform(node):
        node = bigquery_to_duckdb_sqlglot_wildcard(project_id, dataset_id, node)
        return bigquery_to_duckdb_external_query(node, params or {})

    return transform


def bigquery_to_duckdb_sqlglot_wildcard(project_id, dataset_id, node):
    if not isinstance(node, sqlglot.exp.Table) or not node.name.endswith("*"):
        return node
    wildcard = node.name.rstrip("*")
    project_id = node.catalog or project_id
    dataset_id = node.db or dataset_id
    selects = [
        sqlglot.select(
            "*",
            sqlglot.alias(
                sqlglot.exp.Literal(this=table_name[len(wildcard) :], is_string=True),
                "_TABLE_SUFFIX",
            ),
        ).from_(table_expr(node.catalog, node.db, table_name))
        for table_name in sorted(list_tables(project_id, dataset_id))
        if table_name.startswith(wildcard)
    ]
    if not selects:
        raise sqlglot.ParseError(
            f"No tables found for {node.name} in {project_id}.{dataset_id}"
        )
    if len(selects) == 1:
        return selects[0]
    return sqlglot.exp.paren(functools.reduce(lambda x, y: x.union(y), selects))


def external_query_args(node) -> Optional[list]:
    if (
        isinstance(node, sqlglot.exp.Table)
        and isinstance(node.this, sqlglot.exp.Anonymous)
        and node.this.name.upper() == "EXTERNAL_QUERY"
    ):
        return node.this.expressions
    return None


def has_external_query(trees) -> bool:
    return any(
        external_query_args(node) is not None for tree in trees for node in tree.dfs()
    )


def setup_postgres_connection(cur):
    cur.execute(
        f"""
        INSTALL postgres;
        LOAD postgres;
        DETACH DATABASE IF EXISTS pg;
        ATTACH IF NOT EXISTS '{settings.postgres_uri}' AS pg (TYPE postgres);
        """
    )


def bigquery_to_duckdb_external_query(node, params):
    args = external_query_args(node)
    if args is None:
        return node
    if len(args) != 2:
        raise sqlglot.ParseError(
            "EXTERNAL_QUERY requires two arguments: connection_id and query"
        )
    connection_id = get_param_or_literal_value(args[0], params)
    if connection_id != settings.postgres_connection_id:
        raise sqlglot.ParseError(
            f"EXTERNAL_QUERY expected connection ID "
            f"'{settings.postgres_connection_id}', found: '{connection_id}'"
        )
    trees = sqlglot.parse(get_param_or_literal_value(args[1], params), "postgres")
    if len(trees) != 1:
        raise sqlglot.ParseError("EXTERNAL_QUERY query must be a single statement")
    return sqlglot.exp.Subquery(
        this=qualify_tables(trees[0], catalog="pg", db="public"), alias=node.alias
    )


def get_param_or_literal_value(node, params):
    if isinstance(node, sqlglot.exp.Parameter):
        param_name = node.this.this
        if param_name not in params:
            raise ValueError(f"Parameter '{param_name}' not found")
        return params[param_name]
    if isinstance(node, sqlglot.exp.Literal):
        return node.this
    raise ValueError("Node is neither Parameter nor Literal")
