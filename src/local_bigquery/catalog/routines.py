from sqlglot import exp

from local_bigquery.catalog import metadata
from local_bigquery.sql.dialect import BigQueryDialect, table_body


def load(project_id: str, dataset_id: str, routine_id: str) -> dict | None:
    return metadata.load("routines", project_id, dataset_id, routine_id)


def list_(project_id: str, dataset_id: str | None = None) -> list[dict]:
    keys = (project_id, dataset_id) if dataset_id else (project_id,)
    return metadata.list_("routines", *keys)


def save(project_id: str, dataset_id: str, routine_id: str, resource: dict) -> dict:
    now = metadata.now()
    current = load(project_id, dataset_id, routine_id) or {"creationTime": now}
    resource = {
        "kind": "bigquery#routine",
        "routineReference": {
            "projectId": project_id,
            "datasetId": dataset_id,
            "routineId": routine_id,
        },
        "creationTime": current["creationTime"],
        "lastModifiedTime": now,
    } | resource
    return metadata.save("routines", resource, project_id, dataset_id, routine_id)


def delete(project_id: str, dataset_id: str, routine_id: str):
    metadata.delete("routines", project_id, dataset_id, routine_id)


def _type(kind: exp.DataType) -> dict:
    return {"typeKind": kind.sql(dialect=BigQueryDialect)}


def record(tree: exp.Expression, project_id: str, dataset_id: str | None):
    if tree.args.get("kind") != "FUNCTION" or tree.find(exp.TemporaryProperty):
        return
    target = tree.find(exp.Table)
    reference = (target.catalog or project_id, target.db or dataset_id, target.name)
    if isinstance(tree, exp.Drop):
        return delete(*reference)
    if not isinstance(tree, exp.Create):
        return
    body, language = tree.expression, tree.find(exp.LanguageProperty)
    resource = {
        "routineType": "TABLE_VALUED_FUNCTION"
        if table_body(tree)
        else "SCALAR_FUNCTION",
        "language": "JAVASCRIPT"
        if language and language.name.lower() == "js"
        else "SQL",
        "arguments": [
            {"name": column.name, "dataType": _type(column.kind)}
            for column in tree.this.expressions
            if isinstance(column, exp.ColumnDef) and column.kind
        ],
        "definitionBody": body.name
        if isinstance(body, exp.Literal)
        else body.sql(dialect=BigQueryDialect),
    }
    if (returns := tree.find(exp.ReturnsProperty)) and returns.this:
        resource["returnType"] = _type(returns.this)
    save(*reference, resource)
