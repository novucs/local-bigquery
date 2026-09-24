import contextlib
import pathlib
import re
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
    return str(root / uri.removeprefix("gs://"))


def _matches(uri: str) -> list[str]:
    local = _local(uri)
    if not uri.startswith("gs://") or "*" not in uri:
        return [local]
    pattern = re.compile(".*".join(map(re.escape, local.split("*"))))
    folder = pathlib.Path(local.split("*")[0]).parent
    found = (str(p) for p in folder.rglob("*") if p.is_file())
    return sorted(p for p in found if pattern.fullmatch(p)) or [local]


def paths(cur: duckdb.DuckDBPyConnection, uri: str) -> list[str]:
    endpoint = _emulator(uri)
    if endpoint is None:
        return _matches(uri)
    host = urllib.parse.urlsplit(endpoint)
    cur.execute(
        "CREATE SECRET IF NOT EXISTS gcs_emulator (TYPE gcs, KEY_ID '', SECRET '', "
        f"ENDPOINT {literal(host.netloc)}, URL_STYLE 'path', "
        f"USE_SSL {str(host.scheme == 'https').lower()})"
    )
    return [uri]


@contextlib.contextmanager
def written(uri: str):
    endpoint = _emulator(uri)
    if endpoint is None:
        local = _local(uri)
        pathlib.Path(local).parent.mkdir(parents=True, exist_ok=True)
        yield local
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
