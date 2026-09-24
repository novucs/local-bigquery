import pytest
import requests
from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import BadRequest, Conflict, NotFound
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery
from google.cloud.bigquery_storage_v1 import types

from tests.cases import fails, run, run_job, unique

ALICE = "user:alice@example.com"
TEAM = "group:team@example.com"


@pytest.fixture
def caller(endpoint, project):
    if endpoint == "google":
        pytest.skip("caller identity headers are emulator-only")

    def caller(member: str, groups: str = "") -> bigquery.Client:
        session = requests.Session()
        session.headers.update({"X-Bqemu-Caller": member, "X-Bqemu-Groups": groups})
        return bigquery.Client(
            project=project,
            credentials=AnonymousCredentials(),
            client_options=ClientOptions(api_endpoint=endpoint),
            _http=session,
        )

    return caller


@pytest.fixture
def orders(bq, dataset):
    table = f"{dataset.dataset_id}.{unique('orders')}"
    run(
        bq,
        f"CREATE TABLE {table} AS SELECT 1 AS id, 'US' AS country, 100 AS amount "
        "UNION ALL SELECT 2, 'US', 200 UNION ALL SELECT 3, 'EU', 300 "
        "UNION ALL SELECT 4, 'JP', 400",
    )
    return table


def policy(bq, table, name, grantees, predicate):
    members = ", ".join(f'"{member}"' for member in grantees)
    run(
        bq,
        f"CREATE ROW ACCESS POLICY {name} ON {table} "
        f"GRANT TO ({members}) FILTER USING ({predicate})",
    )


def ids(client, sql):
    return [row[0] for row in run(client, sql)]


def test_table_without_policies_is_unrestricted(caller, orders):
    assert ids(caller(ALICE), f"SELECT id FROM {orders} ORDER BY id") == [1, 2, 3, 4]


def test_policy_filters_rows_for_grantee(bq, caller, orders):
    policy(bq, orders, "us", [ALICE], "country = 'US'")
    assert ids(caller(ALICE), f"SELECT id FROM {orders} ORDER BY id") == [1, 2]


def test_no_matching_policy_returns_no_rows(bq, caller, orders):
    policy(bq, orders, "us", ["user:bob@example.com"], "country = 'US'")
    assert ids(caller(ALICE), f"SELECT id FROM {orders}") == []


def test_matching_policies_are_unioned(bq, caller, orders):
    policy(bq, orders, "us", [ALICE], "country = 'US'")
    policy(bq, orders, "big", [ALICE], "amount >= 400")
    assert ids(caller(ALICE), f"SELECT id FROM {orders} ORDER BY id") == [1, 2, 4]


@pytest.mark.parametrize(
    "grantee, groups",
    [
        (TEAM, TEAM),
        ("allUsers", ""),
        ("allAuthenticatedUsers", ""),
        ("domain:example.com", ""),
    ],
)
def test_grantee_kinds(bq, caller, orders, grantee, groups):
    policy(bq, orders, "eu", [grantee], "country = 'EU'")
    assert ids(caller(ALICE, groups), f"SELECT id FROM {orders}") == [3]


def test_policy_applies_to_subqueries_and_aggregates(bq, caller, orders):
    policy(bq, orders, "cheap", [ALICE], "amount <= 300")
    client = caller(ALICE)
    assert ids(client, f"SELECT COUNT(*) FROM {orders}") == [3]
    sql = f"SELECT id FROM {orders} WHERE amount > (SELECT AVG(amount) FROM {orders})"
    assert ids(client, sql) == [3]


def test_policy_applies_through_joins_and_aliases(bq, caller, orders):
    policy(bq, orders, "us", [ALICE], "country = 'US'")
    sql = f"SELECT o.id FROM {orders} AS o JOIN {orders} AS p USING (id) ORDER BY o.id"
    assert ids(caller(ALICE), sql) == [1, 2]


def test_views_do_not_bypass_policies(bq, caller, dataset, orders):
    view = f"{dataset.dataset_id}.{unique('v')}"
    run(bq, f"CREATE VIEW {view} AS SELECT id, country FROM {orders}")
    policy(bq, orders, "us", [ALICE], "country = 'US'")
    assert ids(caller(ALICE), f"SELECT id FROM {view} ORDER BY id") == [1, 2]
    assert ids(caller("user:bob@example.com"), f"SELECT id FROM {view}") == []


def test_drop_policies(bq, caller, orders):
    policy(bq, orders, "us", [ALICE], "country = 'US'")
    policy(bq, orders, "eu", [ALICE], "country = 'EU'")
    run(bq, f"DROP ROW ACCESS POLICY us ON {orders}")
    assert ids(caller(ALICE), f"SELECT id FROM {orders}") == [3]
    run(bq, f"DROP ALL ROW ACCESS POLICIES ON {orders}")
    assert len(ids(caller(ALICE), f"SELECT id FROM {orders}")) == 4


def test_create_or_replace_and_if_not_exists(bq, caller, orders):
    policy(bq, orders, "p", [ALICE], "country = 'US'")
    run(
        bq, f"CREATE ROW ACCESS POLICY IF NOT EXISTS p ON {orders} FILTER USING (FALSE)"
    )
    run(
        bq,
        f'CREATE OR REPLACE ROW ACCESS POLICY p ON {orders} GRANT TO ("{ALICE}") '
        "FILTER USING (country = 'JP')",
    )
    assert ids(caller(ALICE), f"SELECT id FROM {orders}") == [4]


def test_duplicate_policy(bq, orders):
    policy(bq, orders, "p", ["allAuthenticatedUsers"], "TRUE")
    with fails(Conflict, "duplicate"):
        policy(bq, orders, "p", ["allAuthenticatedUsers"], "TRUE")


def test_drop_missing_policy(bq, orders):
    with fails(NotFound, "notFound"):
        run(bq, f"DROP ROW ACCESS POLICY missing ON {orders}")
    run(bq, f"DROP ROW ACCESS POLICY IF EXISTS missing ON {orders}")


def test_statement_types(bq, orders):
    job = run_job(bq, f"CREATE ROW ACCESS POLICY p ON {orders} FILTER USING (TRUE)")
    assert job.statement_type == "CREATE_ROW_ACCESS_POLICY"
    run(bq, f"CREATE ROW ACCESS POLICY q ON {orders} FILTER USING (TRUE)")
    job = run_job(bq, f"DROP ROW ACCESS POLICY p ON {orders}")
    assert job.statement_type == "DROP_ROW_ACCESS_POLICY"
    job = run_job(bq, f"DROP ALL ROW ACCESS POLICIES ON {orders}")
    assert job.statement_type == "DROP_ALL_ROW_ACCESS_POLICIES"


def test_dropping_the_last_policy_needs_drop_all(bq, orders):
    run(bq, f"CREATE ROW ACCESS POLICY p ON {orders} FILTER USING (TRUE)")
    with fails(BadRequest, "invalid") as info:
        run(bq, f"DROP ROW ACCESS POLICY p ON {orders}")
    assert "please use a DROP ALL statement instead" in info.value.message


@pytest.fixture
def policies(endpoint, project, orders):
    if endpoint == "google":
        pytest.skip("raw REST calls need an unauthenticated endpoint")
    dataset_id, table_id = orders.split(".")
    base = (
        f"{endpoint}/bigquery/v2/projects/{project}/datasets/{dataset_id}"
        f"/tables/{table_id}/rowAccessPolicies"
    )

    def call(method, path="", **kwargs):
        return requests.request(method, base + path, timeout=5, **kwargs)

    reference = {"projectId": project, "datasetId": dataset_id, "tableId": table_id}
    return call, reference


def test_rest_insert_get_list(policies, caller, orders):
    call, reference = policies
    body = {
        "rowAccessPolicyReference": reference | {"policyId": "us"},
        "filterPredicate": "country = 'US'",
        "grantees": [ALICE],
    }
    created = call("POST", json=body)
    assert created.status_code == 200, created.text
    assert created.json()["filterPredicate"] == "country = 'US'"
    assert created.json()["etag"]
    fetched = call("GET", "/us").json()
    assert fetched["rowAccessPolicyReference"]["policyId"] == "us"
    assert fetched["grantees"] == [ALICE]
    listed = call("GET").json()["rowAccessPolicies"]
    assert [p["rowAccessPolicyReference"]["policyId"] for p in listed] == ["us"]
    assert ids(caller(ALICE), f"SELECT id FROM {orders} ORDER BY id") == [1, 2]
    assert call("POST", json=body).status_code == 409


def test_rest_update_and_delete(policies, caller, orders):
    call, reference = policies
    body = {
        "rowAccessPolicyReference": reference | {"policyId": "p"},
        "filterPredicate": "country = 'US'",
        "grantees": [ALICE],
    }
    call("POST", json=body)
    updated = call("PUT", "/p", json=body | {"filterPredicate": "country = 'EU'"})
    assert updated.status_code == 200, updated.text
    assert ids(caller(ALICE), f"SELECT id FROM {orders}") == [3]
    assert call("DELETE", "/p").status_code in (200, 204)
    assert call("GET", "/p").status_code == 404
    assert call("DELETE", "/p").status_code == 404


def test_rest_batch_delete(policies, caller, orders):
    call, reference = policies
    for name in ("a", "b"):
        call(
            "POST",
            json={
                "rowAccessPolicyReference": reference | {"policyId": name},
                "filterPredicate": "FALSE",
                "grantees": [ALICE],
            },
        )
    deleted = call("POST", ":batchDelete", json={"policyIds": ["a", "b"]})
    assert deleted.status_code in (200, 204), deleted.text
    assert call("GET").json().get("rowAccessPolicies", []) == []
    assert len(ids(caller(ALICE), f"SELECT id FROM {orders}")) == 4


def test_authorized_views_still_apply_policies(bq, caller, dataset, orders):
    views = bq.create_dataset(unique("views"))
    try:
        view = bigquery.Table(f"{bq.project}.{views.dataset_id}.public")
        view.view_query = f"SELECT id FROM `{bq.project}.{orders}`"
        view = bq.create_table(view)
        source = bq.get_dataset(dataset.dataset_id)
        source.access_entries = [
            *source.access_entries,
            bigquery.AccessEntry(None, "view", view.reference.to_api_repr()),
        ]
        bq.update_dataset(source, ["access_entries"])
        policy(bq, orders, "us", ["user:bob@example.com"], "country = 'US'")
        assert ids(caller(ALICE), f"SELECT id FROM {views.dataset_id}.public") == []
    finally:
        bq.delete_dataset(views, delete_contents=True)


def test_information_schema_row_access_policies_not_found(bq, orders):
    policy(bq, orders, "us", ["allAuthenticatedUsers"], "TRUE")
    with fails(NotFound, "notFound"):
        run(
            bq,
            f"SELECT * FROM {orders.split('.')[0]}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES",
        )


def test_storage_read_applies_policies(bq, bqstorage, caller, orders, project):
    policy(bq, orders, "us_only", [ALICE], "country = 'US'")
    dataset_id, table_id = orders.split(".")
    table = f"projects/{project}/datasets/{dataset_id}/tables/{table_id}"

    def read_ids(member: str) -> list[int]:
        session = bqstorage.create_read_session(
            parent=f"projects/{project}",
            read_session=types.ReadSession(
                table=table, data_format=types.DataFormat.ARROW
            ),
            max_stream_count=1,
            metadata=[("x-bqemu-caller", member)],
        )
        if not session.streams:
            return []
        rows = bqstorage.read_rows(session.streams[0].name).to_arrow(session)
        return sorted(rows["id"].to_pylist())

    assert read_ids(ALICE) == [1, 2]
    assert read_ids("user:bob@example.com") == []


def test_session_user_is_the_caller(bq, caller, orders):
    assert ids(caller(ALICE), "SELECT SESSION_USER()") == ["alice@example.com"]
    predicate = "country = IF(SESSION_USER() = 'alice@example.com', 'US', 'EU')"
    policy(bq, orders, "by_user", ["allUsers"], predicate)
    sql = f"SELECT id FROM {orders} ORDER BY id"
    assert ids(caller(ALICE), sql) == [1, 2]
    assert ids(caller("user:bob@example.com"), sql) == [3]
