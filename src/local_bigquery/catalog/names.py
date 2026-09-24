import re
import unicodedata

from local_bigquery.errors import BigQueryError

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


def fields(schema: list[dict]):
    for field in schema:
        name = field.get("name") or ""
        if not name or len(name) > 300 or FIELD_FORBIDDEN & set(name):
            raise BigQueryError(
                "invalid",
                f'Invalid field name "{name}". Fields must contain the allowed '
                "characters, and be at most 300 characters long.",
            )
        fields(field.get("fields") or [])
