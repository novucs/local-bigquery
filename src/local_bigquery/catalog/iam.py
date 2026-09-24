import base64
import hashlib
import json

from local_bigquery.catalog import names, row_access, routines, tables
from local_bigquery.engine.database import execute, fetch
from local_bigquery.errors import BigQueryError
from local_bigquery.models import Policy


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


def _load(resource: str) -> Policy:
    rows = fetch(
        "SELECT policy FROM emulator.iam_policies WHERE resource = ?", [resource]
    )
    return (
        Policy.model_validate_json(rows[0][0])
        if rows
        else Policy(version=1, etag="ACAB")
    )


def get(resource: str) -> Policy:
    _resolve(resource)
    return _load(resource)


def set_(resource: str, policy: Policy) -> Policy:
    label, current = _resolve(resource), _load(resource)
    if (etag := policy.etag) and etag != current.etag:
        raise BigQueryError(
            "invalid",
            f"IAM setPolicy failed for {label}: There were concurrent policy changes. "
            "Please retry the whole read-modify-write with exponential backoff. "
            f"The request's ETag '{etag}' did not match the current policy's ETag "
            f"'{current.etag}'.",
        )
    policy = Policy(version=1).replace(**policy.without("etag").dump())
    digest = hashlib.md5(json.dumps(policy.dump(), sort_keys=True).encode()).digest()
    policy = policy.replace(etag=base64.b64encode(digest[:8]).decode())
    execute(
        "INSERT OR REPLACE INTO emulator.iam_policies VALUES (?, ?)",
        [resource, json.dumps(policy.dump())],
    )
    return policy
