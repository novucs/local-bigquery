import json
import re

import duckdb
import sqlglot
from sqlglot import exp

from local_bigquery.catalog import datasets, metadata, routines, tables
from local_bigquery.catalog import ddl as catalog_ddl
from local_bigquery.engine import database, types
from local_bigquery.engine.database import quote
from local_bigquery.errors import BigQueryError, from_duckdb
from local_bigquery.jobs import extract, merge
from local_bigquery.sql import js, params, script
from local_bigquery.sql.dialect import DuckDBDialect
from local_bigquery.sql.rules import ddl
from local_bigquery.sql.translate import Context, parse, translate

TEMPORARY_FUNCTION = re.compile(
    r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?TEMP(?:ORARY)?\s+FUNCTION\b", re.IGNORECASE
)
STATEMENT_TYPES = {
    exp.Insert: "INSERT",
    exp.Update: "UPDATE",
    exp.Delete: "DELETE",
    exp.Merge: "MERGE",
    exp.TruncateTable: "TRUNCATE_TABLE",
    exp.Export: "EXPORT_DATA",
}
DML_COUNTS = {
    exp.Insert: "insertedRowCount",
    exp.Update: "updatedRowCount",
    exp.Delete: "deletedRowCount",
}
DDL = (exp.Create, exp.Drop, exp.Alter)
LAYOUT = ("timePartitioning", "rangePartitioning", "clustering")


def statement_type(tree: exp.Expression) -> str:
    if isinstance(tree, exp.Query):
        return "SELECT"
    if type(tree) in STATEMENT_TYPES:
        return STATEMENT_TYPES[type(tree)]
    if isinstance(tree, DDL):
        verb = type(tree).__name__.upper()
        kind = (tree.args.get("kind") or "TABLE").upper()
        if tree.find(exp.MaterializedProperty) or tree.args.get("materialized"):
            kind = "MATERIALIZED_VIEW"
        if tree.meta.get("snapshot"):
            kind = "SNAPSHOT_TABLE"
        if isinstance(tree, exp.Create) and kind == "TABLE" and tree.expression:
            return "CREATE_TABLE_AS_SELECT"
        return f"{verb}_{kind}"
    return "SCRIPT"


def _temporary_function(tree: exp.Expression) -> bool:
    return (
        isinstance(tree, exp.Create)
        and tree.args.get("kind") == "FUNCTION"
        and tree.find(exp.TemporaryProperty) is not None
    )


def _ddl(tree: exp.Expression, context: Context) -> dict:
    kind = (tree.args.get("kind") or "").upper()
    target = tree.find(exp.Table)
    if kind == "SCHEMA" and target is not None:
        reference = {
            "projectId": target.catalog or context.project_id,
            "datasetId": target.db or target.name,
        }
        found = datasets.exists(reference["projectId"], reference["datasetId"])
        key = "ddlTargetDataset"
        database.attach(reference["projectId"])
    elif kind in ("TABLE", "VIEW") and target is not None:
        reference = {
            "projectId": target.catalog or context.project_id,
            "datasetId": target.db or context.dataset_id,
            "tableId": target.name,
        }
        found = tables.exists(*_reference(reference))
        key = "ddlTargetTable"
    elif kind == "FUNCTION" and target is not None:
        reference = {
            "projectId": target.catalog or context.project_id,
            "datasetId": target.db or context.dataset_id,
            "routineId": target.name,
        }
        found = bool(
            database.fetch(
                "SELECT 1 FROM duckdb_functions() WHERE database_name = ? "
                "AND schema_name = ? AND function_name = ?",
                list(reference.values()),
            )
        )
        key = "ddlTargetRoutine"
    else:
        return {}
    if isinstance(tree, exp.Drop) and not found and tree.args.get("exists"):
        operation = "SKIP"
    elif isinstance(tree, exp.Drop):
        if kind == "SCHEMA" and found and not tree.args.get("cascade"):
            datasets.check_empty(*reference.values())
        operation = "DROP"
    elif isinstance(tree, exp.Alter):
        operation = "ALTER"
    elif found and tree.args.get("exists"):
        operation = "SKIP"
    elif found and tree.args.get("replace"):
        operation = "REPLACE"
    else:
        operation = "CREATE"
    return {"ddlOperationPerformed": operation, key: reference}


def _reference(table: dict) -> tuple[str, str, str]:
    return table["projectId"], table["datasetId"], table["tableId"]


def _layout(cur, sql: str, bound: dict, config: dict) -> dict:
    layout = {key: config[key] for key in LAYOUT if config.get(key)}
    if not layout:
        return layout
    columns = {name.casefold() for name in cur.sql(sql, params=bound).columns}
    partitioning = (
        layout.get("timePartitioning") or layout.get("rangePartitioning") or {}
    )
    if (field := partitioning.get("field")) and field.casefold() not in columns:
        raise BigQueryError(
            "invalid",
            "The field specified for partitioning cannot be found in the schema.",
        )
    for field in (layout.get("clustering") or {}).get("fields") or []:
        if field.casefold() not in columns:
            raise BigQueryError(
                "invalid",
                "The field specified for clustering cannot be found in the schema. "
                f"Invalid field: {field}",
            )
    return layout


def _write(cur, sql: str, bound: dict, destination: dict, config: dict, isolated: bool):
    reference = _reference(destination)
    write = config.get("writeDisposition") or "WRITE_EMPTY"
    create = config.get("createDisposition")
    layout = _layout(cur, sql, bound, config)
    if not isolated:
        tables.write(cur, sql, bound, reference, write, create)
    else:
        with database.cursor() as writer:
            tables.write(cur, sql, bound, reference, write, create, writer)
    if layout:
        stored = metadata.load("tables", *reference) or tables.defaults(*reference)
        tables.record(*reference, stored | layout)


def _fields(relation: duckdb.DuckDBPyRelation, required: set[str]) -> list[dict]:
    return [
        types.field(n, t, n in required).model_dump(exclude_none=True)
        for n, t in zip(relation.columns, relation.types)
    ]


def _declared_schema(cur, tree: exp.Create, context: Context) -> list[dict] | None:
    if isinstance(tree.expression, exp.Query):
        sql, bound = translate(tree.expression, context)
        return _fields(cur.sql(sql, params=bound), set())
    if not isinstance(tree.this, exp.Schema):
        return None
    translated = sqlglot.parse_one(translate(tree, context)[0], dialect=DuckDBDialect)
    columns = [c for c in translated.this.expressions if isinstance(c, exp.ColumnDef)]
    select = exp.select(
        *(exp.alias_(exp.cast(exp.null(), c.args["kind"]), c.name) for c in columns)
    )
    required = {
        c.name
        for c in columns
        if any(isinstance(k.kind, exp.NotNullColumnConstraint) for k in c.constraints)
    }
    return _fields(cur.sql(select.sql(dialect=DuckDBDialect)), required)


def _result_schema(cur, tree, context, statistics: dict, dry_run: bool) -> list | None:
    target = statistics.get("ddlTargetTable")
    if tree.find(exp.TemporaryProperty):
        return None
    if isinstance(tree, exp.Create) and target:
        if dry_run or statistics.get("ddlOperationPerformed") == "SKIP":
            return _declared_schema(cur, tree, context)
        return tables.load(*_reference(target))["schema"]["fields"]
    if dry_run and type(tree) in DML_COUNTS:
        table = tree.find(exp.Table)
        reference = (
            table.catalog or context.project_id,
            table.db or context.dataset_id,
            table.name,
        )
        return tables.load(*reference)["schema"]["fields"]
    return None


def _evaluator(cur: duckdb.DuckDBPyConnection):
    def evaluate(node: exp.Expression):
        query = exp.select(exp.func("to_json", node.copy())).sql(dialect=DuckDBDialect)
        return json.loads(cur.sql(query).fetchone()[0])

    return evaluate


def _statement(
    cur: duckdb.DuckDBPyConnection,
    tree: exp.Expression,
    context: Context,
    destination: dict | None,
    config: dict,
    dry_run: bool,
    isolated: bool,
) -> dict:
    tree = ddl.normalise(tree)
    try:
        return _run(cur, tree, context, destination, config, dry_run, isolated)
    except duckdb.Error as error:
        raise from_duckdb(error, context) from error


def _run(cur, tree, context, destination, config, dry_run, isolated) -> dict:
    statistics = {"statementType": statement_type(tree)}
    if isinstance(tree, DDL):
        statistics |= _ddl(tree, context)
    if isinstance(tree, exp.Merge) and not dry_run:
        return statistics | merge.run(cur, tree, context)
    if isinstance(tree, exp.Export):
        sql, bound = translate(tree.this, context)
        if not dry_run:
            extract.write(cur, sql, bound, extract.export_config(tree))
        return statistics
    parts = ddl.split(tree)
    if dry_run:
        for part in parts:
            sql, bound = translate(part, context)
            if isinstance(part, exp.Query):
                relation = cur.sql(sql, params=bound)
                fields = [
                    types.field(n, t).model_dump(exclude_none=True)
                    for n, t in zip(relation.columns, relation.types)
                ]
                statistics["schema"] = {"fields": fields}
            elif not isinstance(part, exp.Create):
                cur.execute(f"EXPLAIN {sql}", bound)
        return _with_schema(
            statistics, _result_schema(cur, tree, context, statistics, True)
        )
    if statistics.get("ddlOperationPerformed") == "SKIP":
        schema = _result_schema(cur, tree, context, statistics, False)
        return _with_schema(statistics, schema)
    for part in parts:
        sql, bound = translate(part, context)
        if destination is not None:
            _write(cur, sql, bound, destination, config, isolated)
        elif type(part) in STATEMENT_TYPES:
            (count,) = cur.execute(sql, bound).fetchone()
            statistics["numDmlAffectedRows"] = str(count)
            if key := DML_COUNTS.get(type(part)):
                statistics["dmlStats"] = {key: str(count)}
        else:
            cur.execute(sql, bound)
    if isinstance(tree, DDL):
        catalog_ddl.apply(tree, context.project_id, context.dataset_id, _evaluator(cur))
        routines.record(tree, context.project_id, context.dataset_id)
    return _with_schema(
        statistics, _result_schema(cur, tree, context, statistics, False)
    )


def _with_schema(statistics: dict, fields: list | None) -> dict:
    return statistics if fields is None else statistics | {"schema": {"fields": fields}}


def execute(
    cur: duckdb.DuckDBPyConnection,
    project_id: str,
    job_id: str | None,
    config: dict,
    dry_run: bool = False,
    isolated: bool = False,
    variables: dict | None = None,
) -> tuple[dict, list[dict], dict | None]:
    default = config.get("defaultDataset") or {}
    attachments = []

    def attach_postgres(uri: str) -> str:
        alias = f"pg_{len(attachments)}_{id(attachments)}"
        cur.execute(
            f"LOAD postgres; ATTACH '{uri}' AS {alias} (TYPE postgres, READ_ONLY)"
        )
        attachments.append(alias)
        return alias

    temporary = cur.sql("SELECT table_name FROM duckdb_tables() WHERE temporary")
    context = Context(
        default.get("projectId") or project_id,
        default.get("datasetId"),
        *params.bind(config.get("queryParameters") or []),
        temporary={name.casefold() for (name,) in temporary.fetchall()},
        attach_postgres=attach_postgres,
        variables={} if variables is None else variables,
        system={"current_job_id": job_id, "script.job_id": job_id, "time_zone": "UTC"},
    )
    database.attach(context.project_id)
    found = context.dataset_id and datasets.exists(
        context.project_id, context.dataset_id
    )
    cur.execute(
        f"USE {quote(context.project_id, context.dataset_id if found else 'main')}"
    )
    try:
        statements = script.parse_script(config.get("query") or "")
        return _execute(
            cur, project_id, job_id, config, dry_run, isolated, context, statements
        )
    finally:
        for alias in attachments:
            cur.execute(f"DETACH {alias}")


def _definition(statement: script.Statement) -> bool:
    return statement.kind == "SQL" and bool(TEMPORARY_FUNCTION.match(statement.text))


def _execute(
    cur: duckdb.DuckDBPyConnection,
    project_id: str,
    job_id: str | None,
    config: dict,
    dry_run: bool,
    isolated: bool,
    context: Context,
    statements: list[script.Statement],
) -> tuple[dict, list[dict], dict | None]:
    scripted = script.is_script([s for s in statements if not _definition(s)])
    if scripted and dry_run:
        return {"statementType": "SCRIPT"}, [], None
    destination = None
    if job_id:
        destination = {
            "projectId": project_id,
            "datasetId": tables.RESULTS,
            "tableId": job_id,
        }
        if not scripted:
            destination = config.get("destinationTable") or destination
    if scripted:
        config = config | {"writeDisposition": "WRITE_TRUNCATE"}
    children, produced = [], []

    def run_sql(tree: exp.Expression) -> dict | None:
        if js.is_udf(tree):
            return js.bind(cur, tree, context)
        if _temporary_function(tree):
            cur.execute(translate(tree, context)[0])
            return None
        target = destination if isinstance(tree, exp.Query) else None
        statistics = _statement(
            cur, tree, context, target, config, dry_run, isolated or scripted
        )
        children.append(statistics)
        produced.append(target)
        return statistics

    script.Interpreter(cur, context, run_sql).run(statements)
    result = destination if any(produced) else None
    if not scripted:
        return (children[0] if children else {}), [], result
    return {"statementType": "SCRIPT"}, children, result


def translate_view(project_id: str, dataset_id: str, sql: str) -> str:
    return translate(parse(sql)[0], Context(project_id, dataset_id))[0]
