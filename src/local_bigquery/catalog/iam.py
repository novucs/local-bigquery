import base64
import hashlib
import json

from local_bigquery.catalog import names, row_access, routines, tables
from local_bigquery.engine.database import execute, fetch
from local_bigquery.errors import BigQueryError


def _resolve(resource: str) -> str:
    match resource.split("/"):
        case ["projects", project_id, "datasets", dataset_id, "tables", table_id]:
            tables.load(project_id, dataset_id, table_id)
            return f"Table {names.label(project_id, dataset_id, table_id)}"
        case ["projects", project_id, "datasets", dataset_id, "routines", routine_id]:
            routines.get(project_id, dataset_id, routine_id)
            return f"Routine {names.label(project_id, dataset_id, routine_id)}"
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
            table = names.label(project_id, dataset_id, table_id)
            return f"RowAccessPolicy {policy_id} on table {table}"
    raise BigQueryError("invalid", f"Invalid resource name: {resource}")


def _load(resource: str) -> dict:
    rows = fetch(
        "SELECT policy FROM emulator.iam_policies WHERE resource = ?", [resource]
    )
    return json.loads(rows[0][0]) if rows else {"version": 1, "etag": "ACAB"}


def get(resource: str) -> dict:
    _resolve(resource)
    return _load(resource)


def set_(resource: str, policy: dict) -> dict:
    label, current = _resolve(resource), _load(resource)
    if (etag := policy.get("etag")) and etag != current["etag"]:
        raise BigQueryError(
            "invalid",
            f"IAM setPolicy failed for {label}: There were concurrent policy changes. "
            "Please retry the whole read-modify-write with exponential backoff. "
            f"The request's ETag '{etag}' did not match the current policy's ETag "
            f"'{current['etag']}'.",
        )
    policy = {"version": 1} | {k: v for k, v in policy.items() if k != "etag"}
    digest = hashlib.md5(json.dumps(policy, sort_keys=True).encode()).digest()
    policy |= {"etag": base64.b64encode(digest[:8]).decode()}
    execute(
        "INSERT OR REPLACE INTO emulator.iam_policies VALUES (?, ?)",
        [resource, json.dumps(policy)],
    )
    return policy
