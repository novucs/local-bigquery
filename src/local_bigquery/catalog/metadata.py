import hashlib
import json
import time

from local_bigquery.engine.database import RESOURCES, execute, fetch
from local_bigquery.errors import BigQueryError, already_exists, not_found
from local_bigquery.models import Dataset, Model, Routine, RowAccessPolicy, Table
from local_bigquery.resource import Resource


class Index(Resource):
    kind: str
    name: str
    ddl: str
    creationTime: str


KINDS: dict[type[Resource], str] = {
    Dataset: "datasets",
    Table: "tables",
    Routine: "routines",
    RowAccessPolicy: "row_access_policies",
    Model: "models",
    Index: "indexes",
}

COLLECTIONS = {
    "project_id": "projects",
    "dataset_id": "datasets",
    "table_id": "tables",
    "routine_id": "routines",
    "policy_id": "rowAccessPolicies",
    "model_id": "models",
    "index_id": "indexes",
}


def now() -> str:
    return str(int(time.time() * 1000))


def existing(load, keys) -> list:
    found = []
    for key in keys:
        try:
            found.append(load(*key))
        except BigQueryError as error:
            if error.reason != "notFound":
                raise
    return found


def check_etag(resource: Resource, etag: str | None):
    if etag and etag != resource.etag:
        raise BigQueryError("conditionNotMet", "Precondition check failed.")


def _where(kind: str, count: int) -> str:
    return " AND ".join(f"{key} = ?" for key in RESOURCES[kind][:count])


def list_[R: Resource](model: type[R], *keys: str) -> list[R]:
    kind = KINDS[model]
    rows = fetch(
        f"SELECT resource FROM emulator.{kind} WHERE {_where(kind, len(keys))}",
        list(keys),
    )
    return [model.model_validate_json(resource) for (resource,) in rows]


def load[R: Resource](model: type[R], *keys: str) -> R | None:
    return next(iter(list_(model, *keys)), None)


def save[R: Resource](resource: R, *keys: str) -> R:
    body = {k: v for k, v in resource.dump().items() if k != "etag"}
    etag = hashlib.md5(json.dumps(body, sort_keys=True).encode()).hexdigest()
    kind = KINDS[type(resource)]
    execute(
        f"INSERT OR REPLACE INTO emulator.{kind} ({', '.join(RESOURCES[kind])}, resource) "
        f"VALUES ({', '.join('?' for _ in keys)}, ?)",
        [*keys, json.dumps(body | {"etag": etag})],
    )
    return resource.replace(etag=etag)


def delete(model: type[Resource], *keys: str):
    kind = KINDS[model]
    execute(f"DELETE FROM emulator.{kind} WHERE {_where(kind, len(keys))}", list(keys))
    names = [COLLECTIONS[key] for key in RESOURCES[kind]]
    path = "".join(f"{name}/{key}/" for name, key in zip(names, keys))
    path += "".join(f"{name}/" for name in names[len(keys) : len(keys) + 1])
    execute(
        "DELETE FROM emulator.iam_policies WHERE starts_with(resource || '/', ?)",
        [path],
    )


def outcome(
    kind: str, label: str, found: bool, drop: bool, if_exists: bool, replace=False
) -> str:
    if drop:
        if found:
            return "DROP"
        if if_exists:
            return "SKIP"
        raise not_found(kind, label)
    if found and if_exists:
        return "SKIP"
    if found and not replace:
        raise already_exists(kind, label)
    return "REPLACE" if found else "CREATE"
