import os

import duckdb

from local_bigquery.errors import BigQueryError
from local_bigquery.settings import settings


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def path(cur: duckdb.DuckDBPyConnection, uri: str) -> str:
    if uri.startswith("file://"):
        return uri.removeprefix("file://")
    if not uri.startswith("gs://"):
        return uri
    if settings.gcs_local_root:
        local = settings.gcs_local_root / uri.removeprefix("gs://")
        local.parent.mkdir(parents=True, exist_ok=True)
        return str(local)
    endpoint = os.environ.get("STORAGE_EMULATOR_HOST")
    if not endpoint:
        raise BigQueryError(
            "invalid",
            "gs:// URIs require GCS_LOCAL_ROOT or STORAGE_EMULATOR_HOST",
        )
    cur.execute(
        "CREATE SECRET IF NOT EXISTS gcs_emulator (TYPE gcs, KEY_ID '', SECRET '', "
        f"ENDPOINT {literal(endpoint.split('://')[-1])}, URL_STYLE 'path', "
        f"USE_SSL {str(endpoint.startswith('https')).lower()})"
    )
    return uri
