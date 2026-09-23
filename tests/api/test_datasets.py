import pytest
from google.api_core.exceptions import (
    BadRequest,
    Conflict,
    NotFound,
    PreconditionFailed,
)
from google.cloud import bigquery

from tests.cases import fails, unique


@pytest.fixture
def dataset_id(bq):
    dataset_id = unique("ds")
    yield dataset_id
    bq.delete_dataset(dataset_id, delete_contents=True, not_found_ok=True)


def test_create_returns_server_populated_fields(bq, project, dataset_id):
    dataset = bq.create_dataset(dataset_id)
    assert dataset.project == project
    assert dataset.dataset_id == dataset_id
    assert dataset.full_dataset_id == f"{project}:{dataset_id}"
    assert dataset.location == "US"
    assert dataset.created is not None
    assert dataset.etag


def test_create_round_trips_metadata(bq, dataset_id):
    dataset = bigquery.Dataset(f"{bq.project}.{dataset_id}")
    dataset.description = "about"
    dataset.friendly_name = "Friendly"
    dataset.labels = {"env": "dev"}
    dataset.default_table_expiration_ms = 3_600_000
    bq.create_dataset(dataset)
    fetched = bq.get_dataset(dataset_id)
    assert fetched.description == "about"
    assert fetched.friendly_name == "Friendly"
    assert fetched.labels == {"env": "dev"}
    assert fetched.default_table_expiration_ms == 3_600_000


def test_create_duplicate(bq, dataset_id):
    bq.create_dataset(dataset_id)
    with fails(Conflict, "duplicate"):
        bq.create_dataset(dataset_id)
    bq.create_dataset(dataset_id, exists_ok=True)


def test_get_missing(bq):
    with fails(NotFound, "notFound"):
        bq.get_dataset(unique("missing"))


def test_created_by_sql_is_visible(bq, dataset_id):
    bq.query_and_wait(f"CREATE SCHEMA {dataset_id} OPTIONS (description = 'sql')")
    assert bq.get_dataset(dataset_id).description == "sql"


def test_dataset_ids_are_case_sensitive(bq, dataset_id):
    bq.create_dataset(dataset_id)
    with fails(NotFound, "notFound"):
        bq.get_dataset(dataset_id.upper())


def test_list(bq, dataset_id):
    bq.create_dataset(dataset_id)
    assert dataset_id in [d.dataset_id for d in bq.list_datasets()]


def test_list_pages(bq):
    ids = [unique("page") for _ in range(3)]
    for dataset_id in ids:
        bq.create_dataset(dataset_id)
    try:
        pages = [list(page) for page in bq.list_datasets(page_size=1).pages]
        assert {len(page) for page in pages} == {1}
        assert set(ids) <= {d.dataset_id for page in pages for d in page}
    finally:
        for dataset_id in ids:
            bq.delete_dataset(dataset_id)


def test_list_filters_by_label(bq, dataset_id):
    dataset = bigquery.Dataset(f"{bq.project}.{dataset_id}")
    dataset.labels = {"team": dataset_id}
    bq.create_dataset(dataset)
    listed = bq.list_datasets(filter=f"labels.team:{dataset_id}")
    assert [d.dataset_id for d in listed] == [dataset_id]


def test_update_patches_only_given_fields(bq, dataset_id):
    dataset = bigquery.Dataset(f"{bq.project}.{dataset_id}")
    dataset.description = "before"
    dataset = bq.create_dataset(dataset)
    dataset.labels = {"env": "prod"}
    bq.update_dataset(dataset, ["labels"])
    fetched = bq.get_dataset(dataset_id)
    assert fetched.labels == {"env": "prod"}
    assert fetched.description == "before"


def test_update_removes_label_set_to_none(bq, dataset_id):
    dataset = bigquery.Dataset(f"{bq.project}.{dataset_id}")
    dataset.labels = {"a": "1", "b": "2"}
    dataset = bq.create_dataset(dataset)
    dataset.labels["a"] = None
    bq.update_dataset(dataset, ["labels"])
    assert bq.get_dataset(dataset_id).labels == {"b": "2"}


def test_update_with_stale_etag(bq, dataset_id):
    dataset = bq.create_dataset(dataset_id)
    dataset.description = "first"
    bq.update_dataset(dataset, ["description"])
    dataset.description = "second"
    with pytest.raises(PreconditionFailed):
        bq.update_dataset(dataset, ["description"])


def test_delete_non_empty_requires_delete_contents(bq, dataset_id):
    bq.create_dataset(dataset_id)
    bq.query_and_wait(f"CREATE TABLE {dataset_id}.t (x INT64)")
    with fails(BadRequest, "resourceInUse"):
        bq.delete_dataset(dataset_id)
    bq.delete_dataset(dataset_id, delete_contents=True)
    with fails(NotFound, "notFound"):
        bq.get_dataset(dataset_id)


def test_delete_missing(bq):
    with fails(NotFound, "notFound"):
        bq.delete_dataset(unique("missing"))
    bq.delete_dataset(unique("missing"), not_found_ok=True)


def test_other_project(bq, dataset_id):
    other = unique("project").replace("_", "-")
    bq.create_dataset(f"{other}.{dataset_id}")
    assert bq.get_dataset(f"{other}.{dataset_id}").project == other
    bq.delete_dataset(f"{other}.{dataset_id}")
