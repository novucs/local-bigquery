import contextvars
import re

from local_bigquery.catalog import metadata, names, tables
from local_bigquery.engine.database import fetch
from local_bigquery.errors import BigQueryError, already_exists, not_found
from local_bigquery.settings import settings

caller: contextvars.ContextVar[tuple[str, ...] | None] = contextvars.ContextVar(
    "caller", default=None
)
CREATE = re.compile(
    r"^(OR\s+REPLACE\s+)?ROW\s+ACCESS\s+POLICY\s+(IF\s+NOT\s+EXISTS\s+)?(\S+)\s+ON\s+(\S+)"
    r"(?:\s+GRANT\s+TO\s*\((.*?)\))?\s+FILTER\s+USING\s*\((.*)\)\s*;?\s*$",
    re.IGNORECASE | re.DOTALL,
)
DROP = re.compile(
    r"^(?:(ALL)\s+ROW\s+ACCESS\s+POLICIES|ROW\s+ACCESS\s+POLICY\s+(IF\s+EXISTS\s+)?(\S+))"
    r"\s+ON\s+(\S+)\s*;?\s*$",
    re.IGNORECASE,
)


def members() -> tuple[str, ...]:
    return caller.get() or (settings.caller,)


def identify(principal: str | None, groups: str | None) -> tuple[str, ...]:
    principal = principal or settings.caller
    return (principal, *(g.strip() for g in (groups or "").split(",") if g.strip()))


def _grants(grantee: str, identity: tuple[str, ...]) -> bool:
    if grantee in identity or grantee == "allUsers":
        return True
    if grantee == "allAuthenticatedUsers":
        return bool(identity[0])
    domain = grantee.removeprefix("domain:")
    return grantee.startswith("domain:") and identity[0].endswith(f"@{domain}")


def secured() -> frozenset[tuple[str, str, str]]:
    rows = fetch(
        "SELECT DISTINCT project_id, dataset_id, table_id FROM emulator.row_access_policies"
    )
    return frozenset(rows)


def list_(project_id: str, dataset_id: str, table_id: str) -> list[dict]:
    tables.load(project_id, dataset_id, table_id)
    return metadata.list_("row_access_policies", project_id, dataset_id, table_id)


def get(project_id: str, dataset_id: str, table_id: str, policy_id: str) -> dict:
    policy = metadata.load(
        "row_access_policies", project_id, dataset_id, table_id, policy_id
    )
    if policy is None:
        label = names.label(project_id, dataset_id, table_id, policy_id)
        raise not_found("Row access policy", label)
    return policy


def save(
    project_id: str, dataset_id: str, table_id: str, body: dict, replace: bool = False
) -> dict:
    policy_id = (body.get("rowAccessPolicyReference") or {}).get("policyId")
    if not policy_id or not body.get("filterPredicate"):
        raise BigQueryError("invalid", "A policy id and filter predicate are required")
    tables.load(project_id, dataset_id, table_id)
    keys = (project_id, dataset_id, table_id, policy_id)
    current = metadata.load("row_access_policies", *keys)
    if current and not replace:
        raise already_exists("Row access policy", names.label(*keys))
    now = metadata.now()
    reference = dict(zip(("projectId", "datasetId", "tableId", "policyId"), keys))
    resource = body | {
        "rowAccessPolicyReference": reference,
        "creationTime": (current or {}).get("creationTime", now),
        "lastModifiedTime": now,
    }
    return metadata.save("row_access_policies", resource, *keys)


def delete(project_id: str, dataset_id: str, table_id: str, *policy_ids: str):
    for policy_id in policy_ids:
        get(project_id, dataset_id, table_id, policy_id)
    for policy_id in policy_ids or [None]:
        keys = [project_id, dataset_id, table_id] + ([policy_id] if policy_id else [])
        metadata.delete("row_access_policies", *keys)


def predicate(project_id: str, dataset_id: str, table_id: str) -> str | None:
    if (project_id, dataset_id, table_id) not in secured():
        return None
    identity = members()
    policies = metadata.list_("row_access_policies", project_id, dataset_id, table_id)
    granted = [
        f"({policy['filterPredicate']})"
        for policy in policies
        if any(_grants(grantee, identity) for grantee in policy.get("grantees") or [])
    ]
    return " OR ".join(granted) or "FALSE"


def table(name: str, project_id: str, dataset_id: str | None) -> tuple[str, str, str]:
    parts = name.strip("`").split(".")
    return (
        *([project_id, dataset_id][: 3 - len(parts)]),
        *parts,
    )


def ddl(
    command: str, keyword: str, project_id: str, dataset_id: str | None, dry_run: bool
):
    if keyword == "CREATE" and (match := CREATE.match(command)):
        replace, if_not_exists, name, table_name, grantees, filter_predicate = (
            match.groups()
        )
        keys = table(table_name, project_id, dataset_id)
        body = {
            "rowAccessPolicyReference": {"policyId": name},
            "filterPredicate": filter_predicate.strip(),
            "grantees": [g for _, g in re.findall(r"([\"'])(.*?)\1", grantees or "")],
        }
        exists = metadata.load("row_access_policies", *keys, name)
        if not dry_run and not (exists and if_not_exists):
            save(*keys, body, replace=bool(replace))
        return {"statementType": "CREATE_ROW_ACCESS_POLICY"}
    if keyword == "DROP" and (match := DROP.match(command)):
        drop_all, if_exists, name, table_name = match.groups()
        keys = table(table_name, project_id, dataset_id)
        tables.load(*keys)
        if drop_all:
            if not dry_run:
                delete(*keys)
            return {"statementType": "DROP_ROW_ACCESS_POLICY"}
        exists = metadata.load("row_access_policies", *keys, name)
        if exists and len(list_(*keys)) == 1:
            raise BigQueryError(
                "invalid",
                "Dropping the last row access policy would make the table accessible "
                "to all users who have access to the table. If this is intended, "
                "please use a DROP ALL statement instead.",
            )
        if not dry_run and (exists or not if_exists):
            delete(*keys, name)
        return {"statementType": "DROP_ROW_ACCESS_POLICY"}
    return None
