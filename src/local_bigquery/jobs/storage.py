import contextlib
import pathlib
import tempfile
import urllib.error
import urllib.parse
import urllib.request

import duckdb

from local_bigquery.errors import BigQueryError
from local_bigquery.settings import settings


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _emulator(uri: str) -> str | None:
    endpoint = settings.storage_emulator_host
    if not uri.startswith("gs://") or not endpoint or settings.gcs_local_root:
        return None
    return endpoint if "://" in endpoint else f"http://{endpoint}"


def _local(uri: str) -> str:
    if uri.startswith("file://"):
        return uri.removeprefix("file://")
    if not uri.startswith("gs://"):
        return uri
    root = settings.gcs_local_root or settings.data_dir / "gcs"
    local = root / uri.removeprefix("gs://")
    local.parent.mkdir(parents=True, exist_ok=True)
    return str(local)


def path(cur: duckdb.DuckDBPyConnection, uri: str) -> str:
    endpoint = _emulator(uri)
    if endpoint is None:
        return _local(uri)
    host = urllib.parse.urlsplit(endpoint)
    cur.execute(
        "CREATE SECRET IF NOT EXISTS gcs_emulator (TYPE gcs, KEY_ID '', SECRET '', "
        f"ENDPOINT {literal(host.netloc)}, URL_STYLE 'path', "
        f"USE_SSL {str(host.scheme == 'https').lower()})"
    )
    return uri


@contextlib.contextmanager
def written(uri: str):
    endpoint = _emulator(uri)
    if endpoint is None:
        yield _local(uri)
        return
    bucket, _, name = uri.removeprefix("gs://").partition("/")
    with tempfile.TemporaryDirectory() as directory:
        staged = pathlib.Path(directory) / "object"
        yield str(staged)
        query = urllib.parse.urlencode({"uploadType": "media", "name": name})
        request = urllib.request.Request(
            f"{endpoint.rstrip('/')}/upload/storage/v1/b/{bucket}/o?{query}",
            data=staged.read_bytes(),
            method="POST",
        )
        try:
            urllib.request.urlopen(request).close()
        except urllib.error.HTTPError as error:
            raise BigQueryError(
                "invalid", f"Unable to write {uri}: HTTP {error.code}"
            ) from error
