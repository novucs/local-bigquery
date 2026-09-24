import re

from local_bigquery.catalog import metadata, names, row_access, tables
from local_bigquery.errors import BigQueryError

INDEX = re.compile(
    r"^(OR\s+REPLACE\s+)?(SEARCH|VECTOR)\s+INDEX\s+(IF\s+(?:NOT\s+)?EXISTS\s+)?(\S+)"
    r"\s+ON\s+([^\s(]+)",
    re.IGNORECASE,
)
IVF = re.compile(r"index_type\s*=\s*['\"]IVF['\"]", re.IGNORECASE)
MINIMUM_IVF_ROWS = 5000


def list_(
    project_id: str, dataset_id: str, table_id: str, kind: str
) -> list[metadata.Index]:
    indexes = metadata.list_(metadata.Index, project_id, dataset_id, table_id)
    return [index for index in indexes if index.kind == kind]


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
    found = metadata.load(metadata.Index, *keys) is not None
    operation = metadata.outcome(
        f"{kind.title()} index",
        names.label(*keys),
        found,
        keyword == "DROP",
        bool(if_exists),
        bool(replace),
    )
    if operation in ("CREATE", "REPLACE") and IVF.search(command):
        total = int(tables.load(*keys[:3]).numRows)
        if total < MINIMUM_IVF_ROWS:
            raise BigQueryError(
                "invalid",
                f"Total rows {total} is smaller than min allowed {MINIMUM_IVF_ROWS} "
                "for CREATE VECTOR INDEX query with the IVF index type. Please use "
                "VECTOR_SEARCH table-valued function directly to perform the "
                "similarity search.",
            )
    if not dry_run and operation == "DROP":
        metadata.delete(metadata.Index, *keys)
    elif not dry_run and operation != "SKIP":
        index = metadata.Index(
            kind=kind, name=name, ddl=f"CREATE {command}", creationTime=metadata.now()
        )
        metadata.save(index, *keys)
    return {"statementType": f"{keyword}_{kind}_INDEX"}
