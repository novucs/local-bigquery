from fastapi import Body

from local_bigquery.api import Router
from local_bigquery.catalog import iam

router = Router(tags=["iam"])
RESOURCE = "/{resource:path}"


@router.post(f"{RESOURCE}:getIamPolicy")
def get_policy(resource: str) -> dict:
    return iam.get(resource)


@router.post(f"{RESOURCE}:setIamPolicy")
def set_policy(resource: str, body: dict = Body()) -> dict:
    return iam.set_(resource, body.get("policy") or {})


@router.post(f"{RESOURCE}:testIamPermissions")
def test_permissions(resource: str, body: dict = Body()) -> dict:
    iam.get(resource)
    return {"permissions": body.get("permissions") or []}
