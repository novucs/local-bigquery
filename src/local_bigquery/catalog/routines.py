import json

from sqlglot import exp

from local_bigquery.catalog import metadata, names
from local_bigquery.errors import not_found, not_implemented
from local_bigquery.models import Argument, Routine, StandardSqlDataType
from local_bigquery.sql.dialect import BigQueryDialect, table_body

ROUTINE_TYPES = {
    "SCALAR_FUNCTION": "FUNCTION",
    "TABLE_VALUED_FUNCTION": "TABLE FUNCTION",
    "PROCEDURE": "PROCEDURE",
}
MANAGED = ("kind", "etag", "creationTime", "lastModifiedTime")


def load(project_id: str, dataset_id: str, routine_id: str) -> Routine | None:
    return metadata.load(Routine, project_id, dataset_id, routine_id)


def get(project_id: str, dataset_id: str, routine_id: str) -> Routine:
    if (routine := load(project_id, dataset_id, routine_id)) is None:
        raise not_found("Routine", names.label(project_id, dataset_id, routine_id))
    return routine


def list_(project_id: str, dataset_id: str | None = None) -> list[Routine]:
    keys = (project_id, dataset_id) if dataset_id else (project_id,)
    return metadata.list_(Routine, *keys)


def save(
    project_id: str, dataset_id: str, routine_id: str, resource: Routine
) -> Routine:
    now = metadata.now()
    current = load(project_id, dataset_id, routine_id)
    identity = Routine(
        kind="bigquery#routine",
        routineReference={
            "projectId": project_id,
            "datasetId": dataset_id,
            "routineId": routine_id,
        },
        creationTime=current.creationTime if current else now,
        lastModifiedTime=now,
    )
    resource = identity.replace(**resource.without(*MANAGED).dump())
    return metadata.save(resource, project_id, dataset_id, routine_id)


def delete(project_id: str, dataset_id: str, routine_id: str):
    metadata.delete(Routine, project_id, dataset_id, routine_id)


def data_type(kind: exp.DataType) -> StandardSqlDataType:
    if kind.is_type("array"):
        element = data_type(kind.expressions[0])
        return StandardSqlDataType(typeKind="ARRAY", arrayElementType=element)
    if kind.is_type("struct"):
        fields = [{"name": f.name, "type": data_type(f.kind)} for f in kind.expressions]
        return StandardSqlDataType(typeKind="STRUCT", structType={"fields": fields})
    return StandardSqlDataType(typeKind=kind.sql(dialect=BigQueryDialect))


def sql_type(kind: StandardSqlDataType) -> str:
    match kind.typeKind:
        case "ARRAY":
            return f"ARRAY<{sql_type(kind.arrayElementType)}>"
        case "STRUCT":
            fields = kind.structType.fields or []
            members = ", ".join(f"`{f.name}` {sql_type(f.type)}" for f in fields)
            return f"STRUCT<{members}>"
        case "RANGE":
            return f"RANGE<{sql_type(kind.rangeElementType)}>"
    return kind.typeKind


def _argument(argument: Argument) -> str:
    kind = sql_type(argument.dataType) if argument.dataType else "ANY TYPE"
    return " ".join(filter(None, (argument.mode, f"`{argument.name}`", kind)))


def statement(resource: Routine, replace: bool) -> str:
    reference = resource.routineReference
    name = f"`{reference.projectId}.{reference.datasetId}.{reference.routineId}`"
    routine_type, language = resource.routineType, resource.language
    if routine_type not in ROUTINE_TYPES or language not in (None, "SQL", "JAVASCRIPT"):
        raise not_implemented(f"{language or 'SQL'} {routine_type} routines")
    arguments = ", ".join(map(_argument, resource.arguments or []))
    head = f"CREATE {'OR REPLACE ' if replace else ''}{ROUTINE_TYPES[routine_type]} "
    head += f"{name}({arguments})"
    body = resource.definitionBody or ""
    if routine_type == "PROCEDURE":
        return f"{head} BEGIN\n{body}\nEND"
    if columns := resource.returnTableType and resource.returnTableType.columns:
        fields = ", ".join(f"`{c.name}` {sql_type(c.type)}" for c in columns)
        head += f" RETURNS TABLE<{fields}>"
    if returns := resource.returnType:
        head += f" RETURNS {sql_type(returns)}"
    if routine_type == "TABLE_VALUED_FUNCTION":
        return f"{head} AS {body}"
    if language != "JAVASCRIPT":
        return f"{head} AS ({body})"
    head += " LANGUAGE js"
    if libraries := resource.importedLibraries:
        head += f" OPTIONS (library = {json.dumps(libraries)})"
    return f"{head} AS {exp.Literal.string(body).sql(BigQueryDialect)}"


def record(tree: exp.Expression, project_id: str, dataset_id: str | None):
    if tree.args.get("kind") != "FUNCTION" or tree.find(exp.TemporaryProperty):
        return
    target = tree.find(exp.Table)
    reference = names.reference(target, project_id, dataset_id)
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
            Argument(name=column.name, argumentKind="ANY_TYPE")
            if column.kind.is_type("variant")
            else Argument(name=column.name, dataType=data_type(column.kind))
            for column in tree.this.expressions
            if isinstance(column, exp.ColumnDef) and column.kind
        ],
        "definitionBody": body.name
        if isinstance(body, exp.Literal)
        else body.sql(dialect=BigQueryDialect),
    }
    if (returns := tree.find(exp.ReturnsProperty)) and returns.this:
        resource["returnType"] = data_type(returns.this)
    for option in tree.find_all(exp.Property):
        if option.name.lower() == "description":
            resource["description"] = option.text("value")
    save(*reference, Routine.model_validate(resource))
