import base64
import hashlib
import json

from local_bigquery.catalog import metadata, row_access, routines, tables
from local_bigquery.engine.database import execute, fetch
from local_bigquery.errors import BigQueryError


def _resolve(resource: str) -> str:
    match resource.split("/"):
        case ["projects", project_id, "datasets", dataset_id, "tables", table_id]:
            tables.load(project_id, dataset_id, table_id)
        case ["projects", project_id, "datasets", dataset_id, "routines", routine_id]:
            routines.get(project_id, dataset_id, routine_id)
        case [
            "projects",
            project_id,
            "datasets",
            dataset_id,
            "tables",
            table_id,
            "rowAccessPolicies",
            policy_id,
        ]:
            row_access.get(project_id, dataset_id, table_id, policy_id)
        case _:
            raise BigQueryError("invalid", f"Invalid resource name: {resource}")
    return resource


def get(resource: str) -> dict:
    rows = fetch(
        "SELECT policy FROM emulator.iam_policies WHERE resource = ?",
        [_resolve(resource)],
    )
    return json.loads(rows[0][0]) if rows else {"version": 1, "etag": "ACAB"}


def set_(resource: str, policy: dict) -> dict:
    metadata.check_etag(get(resource), policy.get("etag"))
    policy = {"version": 1} | {k: v for k, v in policy.items() if k != "etag"}
    digest = hashlib.md5(json.dumps(policy, sort_keys=True).encode()).digest()
    policy |= {"etag": base64.b64encode(digest[:8]).decode()}
    execute(
        "INSERT OR REPLACE INTO emulator.iam_policies VALUES (?, ?)",
        [resource, json.dumps(policy)],
    )
    return policy
