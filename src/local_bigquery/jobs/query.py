from sqlglot import exp

from local_bigquery.catalog import datasets
from local_bigquery.engine import database, results
from local_bigquery.engine.database import quote
from local_bigquery.sql import js, params
from local_bigquery.sql.translate import (
    Context,
    attach_postgres,
    parse,
    translate,
    uses_external_query,
)

DML = (exp.Insert, exp.Update, exp.Delete, exp.Merge)


def results_table(project_id: str, job_id: str) -> str:
    return f"emulator._results.{quote(f'{project_id}:{job_id}')}"


def run(project_id: str, job_id: str, config: dict) -> dict:
    default = config.get("defaultDataset") or {}
    query_project = default.get("projectId") or project_id
    dataset_id = default.get("datasetId")
    expressions, values = params.bind(config.get("queryParameters") or [])
    context = Context(query_project, dataset_id, expressions, values)
    database.attach(query_project)
    trees = parse(config.get("query") or "")
    statistics = {}
    with database.cursor() as cur:
        schema = (
            dataset_id
            if dataset_id and datasets.exists(query_project, dataset_id)
            else "main"
        )
        cur.execute(f"USE {quote(query_project, schema)}")
        if uses_external_query(trees):
            attach_postgres(cur)
        for index, tree in enumerate(trees):
            if js.is_udf(tree):
                js.bind(cur, tree)
                continue
            sql, bound = translate(tree, context)
            if index == len(trees) - 1 and isinstance(tree, exp.Query):
                results.materialise(cur, sql, results_table(project_id, job_id), bound)
            elif isinstance(tree, DML):
                (count,) = cur.execute(sql, bound).fetchone()
                statistics = {"numDmlAffectedRows": str(count)}
            else:
                cur.execute(sql, bound)
    return statistics


def translate_view(project_id: str, dataset_id: str, sql: str) -> str:
    return translate(parse(sql)[0], Context(project_id, dataset_id))[0]
