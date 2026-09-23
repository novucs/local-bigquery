import hashlib
import json
import time

from local_bigquery.engine.database import execute, fetch
from local_bigquery.errors import BigQueryError

KEYS = {
    "datasets": ("project_id", "dataset_id"),
    "tables": ("project_id", "dataset_id", "table_id"),
    "routines": ("project_id", "dataset_id", "routine_id"),
}


def now() -> str:
    return str(int(time.time() * 1000))


def merge(target: dict, patch: dict) -> dict:
    merged = dict(target)
    for key, value in patch.items():
        if value is None:
            merged.pop(key, None)
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def check_etag(resource: dict, etag: str | None):
    if etag and etag != resource.get("etag"):
        raise BigQueryError("conditionNotMet", "Precondition check failed.")


def _where(kind: str, count: int) -> str:
    return " AND ".join(f"{key} = ?" for key in KEYS[kind][:count])


def load(kind: str, *keys: str) -> dict | None:
    rows = fetch(
        f"SELECT resource FROM emulator.{kind} WHERE {_where(kind, len(keys))}",
        list(keys),
    )
    return json.loads(rows[0][0]) if rows else None


def list_(kind: str, *keys: str) -> list[dict]:
    rows = fetch(
        f"SELECT resource FROM emulator.{kind} WHERE {_where(kind, len(keys))}",
        list(keys),
    )
    return [json.loads(resource) for (resource,) in rows]


def save(kind: str, resource: dict, *keys: str) -> dict:
    body = json.dumps(
        {k: v for k, v in resource.items() if k != "etag"}, sort_keys=True
    )
    resource = resource | {"etag": hashlib.md5(body.encode()).hexdigest()}
    params = ", ".join("?" for _ in keys)
    execute(
        f"INSERT OR REPLACE INTO emulator.{kind} ({', '.join(KEYS[kind])}, resource) "
        f"VALUES ({params}, ?)",
        [*keys, json.dumps(resource)],
    )
    return resource


def delete(kind: str, *keys: str):
    execute(f"DELETE FROM emulator.{kind} WHERE {_where(kind, len(keys))}", list(keys))
