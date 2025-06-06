import contextlib
import functools
import inspect
from datetime import datetime
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
    bigquery_schema_to_sql,
    fill_missing_fields,
    bigquery_params_to_duckdb_params,
    duckdb_values_to_bigquery_values,
    duckdb_fields_to_bigquery_fields,
)


def strip_quotes(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
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
    found_projects = {project.stem for project in settings.data_dir.glob("*.ducklake")}
    default_projects = {
        project_id,
        settings.default_project_id,
        settings.internal_project_id,
    }
    projects = found_projects | default_projects
    conn = duckdb.connect()
    conn.execute("INSTALL ducklake;")
    conn.execute("INSTALL sqlite;")
    try:
        for project in projects:
            metadata = settings.data_dir / f"{project}.ducklake"
            data_path = settings.data_dir / f"{project}"
            conn.execute(
                f"ATTACH 'ducklake:sqlite:{metadata}' AS \"{project}\" (DATA_PATH '{data_path}')"
            )
            if project not in found_projects:
                if project == settings.internal_project_id:
                    migrate(conn)
                if project == settings.default_project_id:
                    dataset = f'"{settings.default_project_id}"."{settings.default_dataset_id}"'
                    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {dataset}")
        yield conn
    finally:
        conn.close()


def reset():
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    for item in settings.data_dir.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            for sub_item in item.iterdir():
                sub_item.unlink()
            item.rmdir()


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


@contextlib.contextmanager
def internal_cursor():
    with cursor(settings.internal_project_id, settings.internal_dataset_id) as cur:
        yield cur


def migrate(conn):
    dataset = f'"{settings.internal_project_id}"."{settings.internal_dataset_id}"'
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {dataset}")
    conn.execute(f"USE {dataset}")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS datasets (
            project_id TEXT,
            dataset_id TEXT,
            item JSON
        );
        CREATE TABLE IF NOT EXISTS models (
            project_id TEXT,
            dataset_id TEXT,
            model_id TEXT,
            item JSON
        );
        CREATE TABLE IF NOT EXISTS routines (
            project_id TEXT,
            dataset_id TEXT,
            routine_id TEXT,
            item JSON
        );
        CREATE TABLE IF NOT EXISTS tables (
            project_id TEXT,
            dataset_id TEXT,
            table_id TEXT,
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
        project_ids = sorted([row[0] for row in results.fetchall()])
    return [
        Project(
            friendlyName=project_id,
            id=project_id,
            numericId=hash(project_id),
            projectReference=ProjectReference(projectId=project_id),
        )
        for project_id in project_ids
    ]


def timestamp_now() -> str:
    return str(int(datetime.now().timestamp()))


def list_datasets(project_id):
    project_id = strip_quotes(project_id)
    with cursor(project_id, settings.default_dataset_id) as cur:
        cur.execute(
            """
                SELECT schema_name
                FROM duckdb_schemas
                WHERE database_name = $project_id
            """,
            {"project_id": project_id},
        )
        dataset_ids = sorted([row[0] for row in cur.fetchall()])
    return [get_dataset(project_id, dataset_id) for dataset_id in dataset_ids]


def get_internal_dataset(project_id: str, dataset_id: str) -> Optional[Dataset]:
    project_id = strip_quotes(project_id)
    dataset_id = strip_quotes(dataset_id)
    with internal_cursor() as cur:
        cur.execute(
            """
                SELECT item
                FROM datasets
                WHERE project_id = $project_id AND dataset_id = $dataset_id
            """,
            {"project_id": project_id, "dataset_id": dataset_id},
        )
        row = cur.fetchone()
        if row is None:
            return None
        item = row[0]
    return Dataset.model_validate_json(item, by_alias=True)


def get_dataset(project_id: str, dataset_id: str) -> Optional[Dataset]:
    project_id = strip_quotes(project_id)
    dataset_id = strip_quotes(dataset_id)
    with cursor(project_id, settings.default_dataset_id) as cur:
        cur.execute(
            """
                SELECT schema_name
                FROM duckdb_schemas
                WHERE database_name = $project_id AND schema_name = $dataset_id
            """,
            {"project_id": project_id, "dataset_id": dataset_id},
        )
        found = cur.fetchone()
        if not found:
            return None
    dataset = get_internal_dataset(project_id, dataset_id)
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
    create_internal_dataset(project_id, dataset_id, dataset)
    return dataset


def delete_dataset(project_id, dataset_id):
    project_id = strip_quotes(project_id)
    dataset_id = strip_quotes(dataset_id)
    with cursor(project_id, dataset_id) as cur:
        duckdb_sql = f'DROP SCHEMA "{project_id}"."{dataset_id}" CASCADE'
        with debug_sql(duckdb_sql=duckdb_sql):
            cur.sql(duckdb_sql)
    with internal_cursor() as cur:
        cur.execute(
            """
            DELETE FROM datasets
            WHERE project_id = $project_id AND dataset_id = $dataset_id
            """,
            {"project_id": project_id, "dataset_id": dataset_id},
        )


def create_internal_dataset(project_id: str, dataset_id: str, dataset: Dataset):
    project_id = strip_quotes(project_id)
    dataset_id = strip_quotes(dataset_id)
    with internal_cursor() as cur:
        cur.execute(
            """
                INSERT INTO datasets (project_id, dataset_id, item)
                VALUES ($project_id, $dataset_id, $item)
            """,
            {
                "project_id": project_id,
                "dataset_id": dataset_id,
                "item": dataset.model_dump_json(exclude_unset=True, by_alias=True),
            },
        )


def create_dataset(project_id, dataset_id, dataset: Dataset) -> Dataset:
    project_id = strip_quotes(project_id)
    dataset_id = strip_quotes(dataset_id)
    if get_dataset(project_id, dataset_id):
        raise AlreadyExistsError(f"Dataset {dataset_id} already exists")
    create_internal_dataset(project_id, dataset_id, dataset)
    with cursor(project_id, dataset_id) as cur:
        duckdb_sql = f'CREATE SCHEMA "{project_id}"."{dataset_id}"'
        with debug_sql(duckdb_sql=duckdb_sql):
            cur.sql(duckdb_sql)
    return dataset


def update_dataset(project_id, dataset_id, dataset: Dataset) -> Dataset:
    project_id = strip_quotes(project_id)
    dataset_id = strip_quotes(dataset_id)
    if not get_dataset(project_id, dataset_id):
        raise NotFoundError(f"Dataset {dataset_id} does not exist")
    with internal_cursor() as cur:
        cur.execute(
            """
                UPDATE datasets
                SET item = $item
                WHERE project_id = $project_id AND dataset_id = $dataset_id
            """,
            {
                "project_id": project_id,
                "dataset_id": dataset_id,
                "item": dataset.model_dump_json(exclude_unset=True, by_alias=True),
            },
        )
    return dataset


def list_tables(project_id, dataset_id: Optional[str] = None) -> list[str]:
    project_id = strip_quotes(project_id)
    dataset_id = strip_quotes(dataset_id)
    with cursor(project_id, dataset_id) as cur:
        result = cur.sql("SHOW TABLES")
        return [table_name for table_name, *_ in result.fetchall()]


def delete_table(project_id, dataset_id, table_id):
    table_name = build_table_name(project_id, dataset_id, table_id)
    with cursor(project_id, dataset_id) as cur:
        duckdb_sql = f"DROP TABLE {table_name}"
        with debug_sql(duckdb_sql=duckdb_sql):
            cur.sql(duckdb_sql)


def create_table(project_id, dataset_id, table_id, schema: TableSchema):
    table_name = build_table_name(project_id, dataset_id, table_id)
    with cursor(project_id, dataset_id) as cur:
        bq_sql = bigquery_schema_to_sql(schema.fields, table_name)
        duckdb_sql = sqlglot.transpile(bq_sql, read="bigquery", write="duckdb")[0]
        with debug_sql(bq_sql=bq_sql, duckdb_sql=duckdb_sql):
            cur.sql(duckdb_sql)


def create_job(project_id: str, job_id: str, job: Job) -> Job:
    project_id = strip_quotes(project_id)
    job_id = strip_quotes(job_id)
    if get_job(project_id, job_id):
        raise AlreadyExistsError(f"Job {job_id} already exists")
    with internal_cursor() as cur:
        cur.sql(
            """
                INSERT INTO jobs (project_id, job_id, item)
                VALUES ($project_id, $job_id, $item)
            """,
            params={
                "project_id": project_id,
                "job_id": job_id,
                "item": job.model_dump_json(exclude_unset=True, by_alias=True),
            },
        )
    return job


def update_job(project_id: str, job_id: str, job: Job) -> Job:
    project_id = strip_quotes(project_id)
    job_id = strip_quotes(job_id)
    with internal_cursor() as cur:
        cur.sql(
            """
            UPDATE jobs
            SET item = $item
            WHERE project_id = $project_id AND job_id = $job_id
            """,
            params={
                "project_id": project_id,
                "job_id": job_id,
                "item": job.model_dump_json(exclude_unset=True, by_alias=True),
            },
        )
    return job


def get_job(project_id: str, job_id: str) -> Optional[Job]:
    project_id = strip_quotes(project_id)
    job_id = strip_quotes(job_id)
    with internal_cursor() as cur:
        results = cur.sql(
            """
                SELECT item
                FROM jobs
                WHERE project_id = $project_id AND job_id = $job_id
            """,
            params={"project_id": project_id, "job_id": job_id},
        )
        row = results.fetchone()
        if not row:
            return None
        item = row[0]
    return Job.model_validate_json(item, by_alias=True)


def list_jobs(project_id: str) -> list[Job]:
    project_id = strip_quotes(project_id)
    with internal_cursor() as cur:
        results = cur.sql(
            """
                SELECT item
                FROM jobs
                WHERE project_id = $project_id
            """,
            params={"project_id": project_id},
        )
        return [
            Job.model_validate_json(row[0], by_alias=True) for row in results.fetchall()
        ]


def delete_job(project_id: str, job_id: str):
    project_id = strip_quotes(project_id)
    job_id = strip_quotes(job_id)
    with internal_cursor() as cur:
        cur.sql(
            """
                DELETE FROM jobs
                WHERE project_id = $project_id AND job_id = $job_id
            """,
            params={"project_id": project_id, "job_id": job_id},
        )


def set_query_results(
    project_id: str,
    job_id: str,
    query_results: GetQueryResultsResponse,
) -> GetQueryResultsResponse:
    project_id = strip_quotes(project_id)
    job_id = strip_quotes(job_id)
    with internal_cursor() as cur:
        if get_query_results(project_id, job_id):
            cur.sql(
                """
                    UPDATE query_results
                    SET item = $item
                    WHERE project_id = $project_id AND job_id = $job_id
                """,
                params={
                    "project_id": project_id,
                    "job_id": job_id,
                    "item": query_results.model_dump_json(
                        exclude_unset=True, by_alias=True
                    ),
                },
            )
        else:
            cur.sql(
                """
                    INSERT INTO query_results (project_id, job_id, item)
                    VALUES ($project_id, $job_id, $item)
                """,
                params={
                    "project_id": project_id,
                    "job_id": job_id,
                    "item": query_results.model_dump_json(
                        exclude_unset=True, by_alias=True
                    ),
                },
            )
    return query_results


def get_query_results(
    project_id: str, job_id: str
) -> Optional[GetQueryResultsResponse]:
    project_id = strip_quotes(project_id)
    job_id = strip_quotes(job_id)
    with internal_cursor() as cur:
        results = cur.sql(
            """
                SELECT item
                FROM query_results
                WHERE project_id = $project_id AND job_id = $job_id
            """,
            params={"project_id": project_id, "job_id": job_id},
        )
        row = results.fetchone()
        if not row:
            return None
        item = row[0]
    return GetQueryResultsResponse.model_validate_json(item, by_alias=True)


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
        table_name
        for table_name in list_tables(project_id, dataset_id)
        if table_name.startswith(wildcard)
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
