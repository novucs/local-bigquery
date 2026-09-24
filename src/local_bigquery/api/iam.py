from local_bigquery.api import Router
from local_bigquery.catalog import iam
from local_bigquery.models import (
    Policy,
    SetIamPolicyRequest,
    TestIamPermissionsRequest,
    TestIamPermissionsResponse,
)

router = Router(tags=["iam"])
RESOURCE = "/{resource:path}"


@router.post(f"{RESOURCE}:getIamPolicy")
def get_policy(resource: str) -> Policy:
    return iam.get(resource)


@router.post(f"{RESOURCE}:setIamPolicy")
def set_policy(resource: str, body: SetIamPolicyRequest) -> Policy:
    return iam.set_(resource, body.policy or Policy())


@router.post(f"{RESOURCE}:testIamPermissions")
def test_permissions(
    resource: str, body: TestIamPermissionsRequest
) -> TestIamPermissionsResponse:
    iam.get(resource)
    return TestIamPermissionsResponse(permissions=body.permissions or [])
