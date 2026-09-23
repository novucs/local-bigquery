import re

from local_bigquery.catalog import metadata, row_access, tables
from local_bigquery.errors import already_exists, not_found

INDEX = re.compile(
    r"^(OR\s+REPLACE\s+)?(SEARCH|VECTOR)\s+INDEX\s+(IF\s+(?:NOT\s+)?EXISTS\s+)?(\S+)"
    r"\s+ON\s+([^\s(]+)",
    re.IGNORECASE,
)


def list_(project_id: str, dataset_id: str, table_id: str, kind: str) -> list[dict]:
    indexes = metadata.list_("indexes", project_id, dataset_id, table_id)
    return [index for index in indexes if index["kind"] == kind]


def ddl(
    command: str, keyword: str, project_id: str, dataset_id: str | None, dry_run: bool
) -> dict | None:
    match = INDEX.match(command)
    if keyword not in ("CREATE", "DROP") or not match:
        return None
    replace, kind, if_exists, name, table = match.groups()
    kind = kind.upper()
    keys = (*row_access.table(table, project_id, dataset_id), name)
    tables.load(*keys[:3])
    found = metadata.load("indexes", *keys)
    label = "{}:{}.{}.{}".format(*keys)
    if keyword == "DROP" and not (found or if_exists):
        raise not_found(f"{kind.title()} index", label)
    if keyword == "CREATE" and found and not (replace or if_exists):
        raise already_exists(f"{kind.title()} index", label)
    if not dry_run and keyword == "DROP":
        metadata.delete("indexes", *keys)
    elif not dry_run and not (found and if_exists):
        resource = {
            "kind": kind,
            "name": name,
            "ddl": f"CREATE {command}",
            "creationTime": metadata.now(),
        }
        metadata.save("indexes", resource, *keys)
    return {"statementType": f"{keyword}_{kind}_INDEX"}
