from fastapi import Body

from local_bigquery.api import Router, paginate
from local_bigquery.catalog import row_access

router = Router(tags=["rowAccessPolicies"])
POLICIES = (
    "/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}/rowAccessPolicies"
)


@router.get(POLICIES)
def list_policies(
    project_id: str,
    dataset_id: str,
    table_id: str,
    pageSize: int | None = None,
    pageToken: str | None = None,
) -> dict:
    policies = row_access.list_(project_id, dataset_id, table_id)
    page, token = paginate(policies, pageSize, pageToken)
    return {"rowAccessPolicies": page} | ({"nextPageToken": token} if token else {})


@router.post(POLICIES)
def insert_policy(
    project_id: str, dataset_id: str, table_id: str, body: dict = Body()
) -> dict:
    return row_access.save(project_id, dataset_id, table_id, body)


@router.post(f"{POLICIES}:batchDelete")
def batch_delete(
    project_id: str, dataset_id: str, table_id: str, body: dict = Body()
) -> dict:
    row_access.delete(project_id, dataset_id, table_id, *body.get("policyIds", []))
    return {}


@router.get(f"{POLICIES}/{{policy_id}}")
def get_policy(project_id: str, dataset_id: str, table_id: str, policy_id: str) -> dict:
    return row_access.get(project_id, dataset_id, table_id, policy_id)


@router.put(f"{POLICIES}/{{policy_id}}")
def update_policy(
    project_id: str, dataset_id: str, table_id: str, policy_id: str, body: dict = Body()
) -> dict:
    row_access.get(project_id, dataset_id, table_id, policy_id)
    reference = (body.get("rowAccessPolicyReference") or {}) | {"policyId": policy_id}
    body = body | {"rowAccessPolicyReference": reference}
    return row_access.save(project_id, dataset_id, table_id, body, replace=True)


@router.delete(f"{POLICIES}/{{policy_id}}")
def delete_policy(
    project_id: str, dataset_id: str, table_id: str, policy_id: str
) -> dict:
    row_access.delete(project_id, dataset_id, table_id, policy_id)
    return {}
