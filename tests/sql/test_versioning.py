import time

import pytest
from google.api_core.exceptions import BadRequest, NotFound

from tests.cases import FAST_RETRY, fails, rows, run, unique


@pytest.fixture
def source(bq, dataset):
    source = f"{dataset.dataset_id}.{unique('source')}"
    run(bq, f"CREATE TABLE {source} AS SELECT 1 AS id, 'a' AS grp, 10 AS v")
    return source


@pytest.fixture
def name(dataset):
    return lambda prefix: f"{dataset.dataset_id}.{unique(prefix)}"


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


def test_snapshot_survives_dropping_source(bq, source, name):
    snapshot = name("snapshot")
    run(bq, f"CREATE SNAPSHOT TABLE {snapshot} CLONE {source}")
    run(bq, f"DROP TABLE {source}")
    assert rows(bq, f"SELECT id FROM {snapshot}") == [(1,)]


def test_snapshot_rejects_dml(bq, source, name):
    snapshot = name("snapshot")
    run(bq, f"CREATE SNAPSHOT TABLE {snapshot} CLONE {source}")
    with pytest.raises(BadRequest):
        run(bq, f"INSERT {snapshot} VALUES (2, 'b', 20)")


def test_drop_snapshot(bq, source, name):
    snapshot = name("snapshot")
    run(bq, f"CREATE SNAPSHOT TABLE {snapshot} CLONE {source}")
    run(bq, f"DROP SNAPSHOT TABLE {snapshot}")
    with fails(NotFound, "notFound"):
        bq.get_table(snapshot)


def test_clone_diverges_from_source(bq, source, name):
    clone = name("clone")
    run(bq, f"CREATE TABLE {clone} CLONE {source}")
    run(bq, f"INSERT {source} VALUES (2, 'b', 20)")
    run(bq, f"UPDATE {clone} SET v = 99 WHERE TRUE")
    assert rows(bq, f"SELECT id, v FROM {clone}") == [(1, 99)]
    assert rows(bq, f"SELECT id, v FROM {source} ORDER BY id") == [(1, 10), (2, 20)]
    base = bq.get_table(clone).clone_definition.base_table_reference
    assert base.table_id == source.split(".")[1]


def test_clone_of_missing_table(bq, name):
    with fails(NotFound, "notFound"):
        run(bq, f"CREATE TABLE {name('clone')} CLONE {name('missing')}")


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


def test_drop_and_refresh_materialized_view(bq, source, name):
    view = name("mv")
    run(
        bq,
        f"CREATE MATERIALIZED VIEW {view} OPTIONS (enable_refresh = false) "
        f"AS SELECT COUNT(*) AS n FROM {source}",
    )
    run(bq, f"INSERT {source} VALUES (2, 'a', 5)")
    run(bq, f"CALL BQ.REFRESH_MATERIALIZED_VIEW('{view}')")
    assert rows(bq, f"SELECT n FROM {view}") == [(2,)]
    run(bq, f"DROP MATERIALIZED VIEW {view}")
    with fails(NotFound, "notFound"):
        bq.get_table(view)
    run(bq, f"CREATE MATERIALIZED VIEW {view} AS SELECT MAX(v) AS m FROM {source}")
    assert rows(bq, f"SELECT m FROM {view}") == [(10,)]


def test_materialized_view_rejects_dml(bq, source, name):
    view = name("mv")
    run(bq, f"CREATE MATERIALIZED VIEW {view} AS SELECT id FROM {source}")
    with pytest.raises(BadRequest):
        run(bq, f"DELETE FROM {view} WHERE TRUE")


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


def test_table_decorators_are_rejected_in_sql(bq, source):
    [(before,)] = rows(bq, "SELECT UNIX_MILLIS(CURRENT_TIMESTAMP())")
    run(bq, f"DELETE FROM {source} WHERE TRUE")
    with pytest.raises(BadRequest) as info:
        run(bq, f"SELECT id FROM `{source}@{before}`")
    assert f'Table "{source}@{before}" cannot include decorator' in info.value.message


def test_copy_reads_table_decorator(bq, source, name):
    time.sleep(0.2)
    [(before,)] = rows(bq, "SELECT UNIX_MILLIS(CURRENT_TIMESTAMP())")
    run(bq, f"DELETE FROM {source} WHERE TRUE")
    target = name("before")
    bq.copy_table(f"{source}@{before}", target).result(retry=FAST_RETRY)
    assert rows(bq, f"SELECT id FROM {target}") == [(1,)]


def test_undelete_with_table_decorator(bq, source):
    [(before,)] = rows(bq, "SELECT UNIX_MILLIS(CURRENT_TIMESTAMP())")
    run(bq, f"DROP TABLE {source}")
    with fails(NotFound, "notFound"):
        run(bq, f"SELECT id FROM {source}")
    bq.copy_table(f"{source}@{before}", source).result(retry=FAST_RETRY)
    assert rows(bq, f"SELECT id, grp, v FROM {source}") == [(1, "a", 10)]


@pytest.mark.parametrize("kind", ["SNAPSHOT TABLE", "TABLE"])
def test_clone_as_of_earlier_state(bq, source, name, kind):
    time.sleep(0.2)
    [(before,)] = rows(bq, "SELECT CURRENT_TIMESTAMP()")
    run(bq, f"INSERT {source} VALUES (2, 'b', 20)")
    target = name("asof")
    run(
        bq,
        f"CREATE {kind} {target} CLONE {source} "
        f"FOR SYSTEM_TIME AS OF '{before.isoformat()}'",
    )
    assert rows(bq, f"SELECT id FROM {target}") == [(1,)]
