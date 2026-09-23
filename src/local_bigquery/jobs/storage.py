import os

import duckdb

from local_bigquery.errors import BigQueryError


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def path(cur: duckdb.DuckDBPyConnection, uri: str) -> str:
    if uri.startswith("file://"):
        return uri.removeprefix("file://")
    if not uri.startswith("gs://"):
        return uri
    endpoint = os.environ.get("STORAGE_EMULATOR_HOST")
    if not endpoint:
        raise BigQueryError(
            "invalid",
            "gs:// URIs require STORAGE_EMULATOR_HOST to point at a GCS emulator",
        )
    cur.execute(
        "CREATE SECRET IF NOT EXISTS gcs_emulator (TYPE gcs, KEY_ID '', SECRET '', "
        f"ENDPOINT {literal(endpoint.split('://')[-1])}, URL_STYLE 'path', "
        f"USE_SSL {str(endpoint.startswith('https')).lower()})"
    )
    return uri
