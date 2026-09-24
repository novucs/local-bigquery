import pytest
from google.api_core.exceptions import BadRequest, NotFound
from google.cloud import bigquery

from tests.cases import FAST_RETRY, run, unique

VIEWER = "roles/bigquery.dataViewer"
MEMBER = "allAuthenticatedUsers"


@pytest.fixture
def table(bq, dataset):
    table_id = f"{dataset.project}.{dataset.dataset_id}.{unique('t')}"
    return bq.create_table(bigquery.Table(table_id), retry=FAST_RETRY)


@pytest.fixture
def post(rest):
    return lambda resource, method, body: rest(
        "POST", f"/bigquery/v2/{resource}:{method}", json=body
    )


def test_empty_policy(bq, table):
    policy = bq.get_iam_policy(table, retry=FAST_RETRY)
    assert policy.bindings == [] and policy.etag


def test_set_and_get_policy(bq, table):
    policy = bq.get_iam_policy(table, retry=FAST_RETRY)
    policy.bindings = [{"role": VIEWER, "members": {MEMBER}}]
    updated = bq.set_iam_policy(table, policy, retry=FAST_RETRY)
    assert updated.etag != policy.etag
    fetched = bq.get_iam_policy(table, retry=FAST_RETRY)
    assert fetched.etag == updated.etag
    assert fetched.bindings == [{"role": VIEWER, "members": {MEMBER}}]


def test_set_policy_with_stale_etag(bq, table):
    policy = bq.get_iam_policy(table, retry=FAST_RETRY)
    policy.bindings = [{"role": VIEWER, "members": {MEMBER}}]
    bq.set_iam_policy(table, policy, retry=FAST_RETRY)
    with pytest.raises(BadRequest, match="There were concurrent policy changes"):
        bq.set_iam_policy(table, policy, retry=FAST_RETRY)


def test_policy_does_not_survive_recreation(bq, table):
    policy = bq.get_iam_policy(table, retry=FAST_RETRY)
    policy.bindings = [{"role": VIEWER, "members": {MEMBER}}]
    bq.set_iam_policy(table, policy, retry=FAST_RETRY)
    bq.delete_table(table, retry=FAST_RETRY)
    bq.create_table(bigquery.Table(table.reference), retry=FAST_RETRY)
    assert bq.get_iam_policy(table, retry=FAST_RETRY).bindings == []


def test_test_permissions(bq, table):
    permissions = ["bigquery.tables.get", "bigquery.tables.getData"]
    response = bq.test_iam_permissions(table, permissions, retry=FAST_RETRY)
    assert response["permissions"] == permissions


def test_missing_table_policy(bq, dataset):
    with pytest.raises(NotFound):
        bq.get_iam_policy(f"{dataset.dataset_id}.missing", retry=FAST_RETRY)


def test_routine_policy(bq, dataset, post):
    routine = unique("f")
    run(bq, f"CREATE FUNCTION {dataset.dataset_id}.{routine}() AS (1)")
    resource = (
        f"projects/{dataset.project}/datasets/{dataset.dataset_id}/routines/{routine}"
    )
    binding = {"role": VIEWER, "members": [MEMBER]}
    response = post(resource, "setIamPolicy", {"policy": {"bindings": [binding]}})
    assert response.status_code == 200, response.text
    policy = post(resource, "getIamPolicy", {}).json()
    assert policy["bindings"] == [binding]
    permissions = post(resource, "testIamPermissions", {"permissions": ["a.b"]})
    assert permissions.json() == {"permissions": ["a.b"]}


def test_row_access_policy_policy(bq, table, post):
    reference = table.reference
    run(
        bq,
        f"CREATE ROW ACCESS POLICY p ON `{reference.dataset_id}.{reference.table_id}` "
        "GRANT TO ('allUsers') FILTER USING (TRUE)",
    )
    resource = f"{table.path.lstrip('/')}/rowAccessPolicies/p"
    policy = post(resource, "getIamPolicy", {})
    assert policy.status_code == 200, policy.text
    assert "etag" in policy.json()
    missing = post(f"{table.path.lstrip('/')}/rowAccessPolicies/q", "getIamPolicy", {})
    assert missing.status_code == 404
