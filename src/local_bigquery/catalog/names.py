import re
import unicodedata

from sqlglot import exp

from local_bigquery.errors import BigQueryError
from local_bigquery.models import TableFieldSchema

DML = exp.Insert | exp.Update | exp.Delete | exp.Merge | exp.TruncateTable
DATASET_ID = re.compile(r"^[A-Za-z0-9_]{1,1024}$")
TABLE_CATEGORIES = {"Pc", "Pd", "Zs"}
FIELD_FORBIDDEN = set('!"$()*,./;?@[\\]^`{}~')


def dataset(dataset_id: str, location: str | None = None):
    if not DATASET_ID.match(dataset_id):
        raise BigQueryError(
            "invalid",
            f'Invalid dataset ID "{dataset_id}". Dataset IDs must be alphanumeric '
            "(plus underscores and dashes) and must be at most 1024 characters long.",
            location,
        )


def table(table_id: str):
    categories = {unicodedata.category(c) for c in table_id}
    if (
        not table_id
        or len(table_id.encode()) > 1024
        or any(c[0] not in "LMN" and c not in TABLE_CATEGORIES for c in categories)
    ):
        raise BigQueryError(
            "invalid",
            f'Invalid table ID "{table_id}". Table IDs must be alphanumeric '
            "(plus underscores) and must be at most 1024 characters long. "
            "Also, Table decorators cannot be used.",
        )


def _illegal(name: str) -> bool:
    return not name or len(name) > 300 or bool(FIELD_FORBIDDEN & set(name))


def fields(schema: list[TableFieldSchema]):
    for field in schema:
        name = field.name or ""
        if len(name) > 300:
            raise BigQueryError(
                "invalid",
                f'Invalid field name "{name}". Fields must contain only letters, '
                "numbers, and underscores, start with a letter or underscore, and be "
                "at most 300 characters long.",
            )
        if _illegal(name):
            raise BigQueryError(
                "invalid",
                f'Invalid field name "{name}". Fields must contain the allowed '
                "characters, and be at most 300 characters long.",
            )
        fields(field.fields or [])


def column(name: str):
    if _illegal(name):
        raise BigQueryError("invalidQuery", f"Illegal field name: {name}")


def label(*parts: str) -> str:
    return f"{parts[0]}:{'.'.join(parts[1:])}"


def reference(
    table: exp.Table, project_id: str, dataset_id: str | None
) -> tuple[str, str, str]:
    return table.catalog or project_id, table.db or dataset_id, table.name


def target(tree: exp.Expression) -> exp.Table | None:
    if not isinstance(tree, exp.Create | exp.Drop | exp.Alter | DML):
        return None
    node = tree.this if isinstance(tree.this, exp.Expression) else None
    node = node.this if isinstance(node, exp.Schema) else node
    return node if isinstance(node, exp.Table) else tree.find(exp.Table)
