import pytest
from google.api_core.exceptions import BadRequest, NotFound

from tests.cases import fails, rows, run, unique


@pytest.fixture
def source(bq, dataset):
    source = f"{dataset.dataset_id}.{unique('source')}"
    run(bq, f"CREATE TABLE {source} AS SELECT 1 AS id, 'a' AS grp, 10 AS v")
    return source


@pytest.fixture
def name(dataset):
    return lambda prefix: f"{dataset.dataset_id}.{unique(prefix)}"


@pytest.mark.xfail(reason="CREATE SNAPSHOT TABLE unsupported")
def test_snapshot_is_frozen(bq, source, name):
    snapshot = name("snapshot")
    run(bq, f"CREATE SNAPSHOT TABLE {snapshot} CLONE {source}")
    run(bq, f"INSERT {source} VALUES (2, 'b', 20)")
    assert rows(bq, f"SELECT id FROM {snapshot}") == [(1,)]
    fetched = bq.get_table(snapshot)
    assert fetched.table_type == "SNAPSHOT"
    assert (
        fetched.snapshot_definition.base_table_reference.table_id
        == source.split(".")[1]
    )


@pytest.mark.xfail(reason="CREATE SNAPSHOT TABLE unsupported")
def test_snapshot_survives_dropping_source(bq, source, name):
    snapshot = name("snapshot")
    run(bq, f"CREATE SNAPSHOT TABLE {snapshot} CLONE {source}")
    run(bq, f"DROP TABLE {source}")
    assert rows(bq, f"SELECT id FROM {snapshot}") == [(1,)]


@pytest.mark.xfail(reason="CREATE SNAPSHOT TABLE unsupported")
def test_snapshot_rejects_dml(bq, source, name):
    snapshot = name("snapshot")
    run(bq, f"CREATE SNAPSHOT TABLE {snapshot} CLONE {source}")
    with pytest.raises(BadRequest):
        run(bq, f"INSERT {snapshot} VALUES (2, 'b', 20)")


@pytest.mark.xfail(reason="CREATE SNAPSHOT TABLE unsupported")
def test_drop_snapshot(bq, source, name):
    snapshot = name("snapshot")
    run(bq, f"CREATE SNAPSHOT TABLE {snapshot} CLONE {source}")
    run(bq, f"DROP SNAPSHOT TABLE {snapshot}")
    with fails(NotFound, "notFound"):
        bq.get_table(snapshot)


@pytest.mark.xfail(reason="CREATE TABLE CLONE unsupported")
def test_clone_diverges_from_source(bq, source, name):
    clone = name("clone")
    run(bq, f"CREATE TABLE {clone} CLONE {source}")
    run(bq, f"INSERT {source} VALUES (2, 'b', 20)")
    run(bq, f"UPDATE {clone} SET v = 99 WHERE TRUE")
    assert rows(bq, f"SELECT id, v FROM {clone}") == [(1, 99)]
    assert rows(bq, f"SELECT id, v FROM {source} ORDER BY id") == [(1, 10), (2, 20)]
    base = bq.get_table(clone).clone_definition.base_table_reference
    assert base.table_id == source.split(".")[1]


@pytest.mark.xfail(reason="CREATE TABLE CLONE unsupported")
def test_clone_of_missing_table(bq, name):
    with fails(NotFound, "notFound"):
        run(bq, f"CREATE TABLE {name('clone')} CLONE {name('missing')}")


@pytest.mark.xfail(reason="SUM of INT64 returned as string")
def test_materialized_view_tracks_base_table(bq, source, name):
    view = name("mv")
    run(
        bq,
        f"CREATE MATERIALIZED VIEW {view} AS "
        f"SELECT grp, SUM(v) AS total FROM {source} GROUP BY grp",
    )
    run(bq, f"INSERT {source} VALUES (2, 'a', 5), (3, 'b', 7)")
    assert rows(bq, f"SELECT grp, total FROM {view} ORDER BY grp") == [
        ("a", 15),
        ("b", 7),
    ]
    assert bq.get_table(view).table_type == "MATERIALIZED_VIEW"


def test_materialized_view_rejects_dml(bq, source, name):
    view = name("mv")
    run(bq, f"CREATE MATERIALIZED VIEW {view} AS SELECT id FROM {source}")
    with pytest.raises(BadRequest):
        run(bq, f"DELETE FROM {view} WHERE TRUE")


@pytest.mark.xfail(reason="FOR SYSTEM_TIME AS OF mistranslated")
def test_time_travel_reads_earlier_state(bq, source):
    [(before,)] = rows(bq, "SELECT CURRENT_TIMESTAMP()")
    run(bq, f"DELETE FROM {source} WHERE TRUE")
    assert rows(
        bq,
        f"SELECT id FROM {source} FOR SYSTEM_TIME AS OF '{before.isoformat()}'",
    ) == [(1,)]
    assert rows(bq, f"SELECT id FROM {source}") == []


def test_time_travel_before_creation(bq, source):
    with pytest.raises(BadRequest):
        run(
            bq,
            f"SELECT id FROM {source} "
            "FOR SYSTEM_TIME AS OF TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)",
        )
