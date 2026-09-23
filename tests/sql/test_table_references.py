import datetime

import pytest
from google.api_core.exceptions import BadRequest, NotFound

from tests.cases import fails, q, run, unique

pytestmark = pytest.mark.usefixtures("seed")


@pytest.fixture(scope="module")
def seed(bq, dataset):
    ds = dataset.dataset_id
    run(
        bq,
        f"""
        CREATE TABLE {ds}.t AS SELECT 1 AS id UNION ALL SELECT 2;
        CREATE TABLE {ds}.events_20200101 AS SELECT 1 AS id;
        CREATE TABLE {ds}.events_20200102 AS SELECT 2 AS id UNION ALL SELECT 3;
        CREATE TABLE {ds}.events_2021 AS SELECT 4 AS id;
        """,
    )


CASES = [
    q("SELECT id FROM t ORDER BY id", rows=[(1,), (2,)]),
    q(
        "SELECT id, _TABLE_SUFFIX FROM `events_*` ORDER BY id",
        rows=[(1, "20200101"), (2, "20200102"), (3, "20200102"), (4, "2021")],
    ),
    q(
        "SELECT * FROM `events_*` ORDER BY id",
        rows=[(1,), (2,), (3,), (4,)],
        xfail="SELECT * includes _TABLE_SUFFIX",
    ),
    q("SELECT id FROM `events_2020*` ORDER BY id", rows=[(1,), (2,), (3,)]),
    q("SELECT COUNT(*) FROM `events_*` WHERE _TABLE_SUFFIX = '20200102'", 2),
    q(
        "SELECT COUNT(*) FROM `events_*` "
        "WHERE _TABLE_SUFFIX BETWEEN '20200101' AND '20201231'",
        3,
    ),
    q(
        "SELECT _TABLE_SUFFIX AS s, COUNT(*) FROM `events_*` GROUP BY s ORDER BY s",
        rows=[("20200101", 1), ("20200102", 2), ("2021", 1)],
    ),
    q("SELECT id FROM T", error="notFound", xfail="table names case-insensitive"),
    q(
        "SELECT * FROM missing",
        error="notFound",
    ),
    q(
        "SELECT * FROM `nothing_*`",
        error="notFound",
    ),
    q(
        "SELECT id FROM t FOR SYSTEM_TIME AS OF CURRENT_TIMESTAMP() ORDER BY id",
        rows=[(1,), (2,)],
        xfail="FOR SYSTEM_TIME AS OF mistranslated",
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_table_references(check, case):
    check(case)


@pytest.mark.parametrize(
    "reference",
    [
        "{dataset}.t",
        pytest.param(
            "{project}.{dataset}.t",
            marks=pytest.mark.xfail(reason="unquoted dashed project ids unsupported"),
        ),
        "`{project}.{dataset}.t`",
        "`{project}`.{dataset}.t",
        "`{project}`.`{dataset}`.`t`",
        "`{project}.{dataset}`.t",
    ],
)
def test_reference_forms(bq, project, dataset, reference):
    table = reference.format(project=project, dataset=dataset.dataset_id)
    assert [r.id for r in run(bq, f"SELECT id FROM {table} ORDER BY id")] == [1, 2]


@pytest.mark.xfail(reason="unquoted dashed project ids unsupported")
def test_same_dataset_name_in_two_projects(bq, dataset):
    other = unique("other-project").replace("_", "-")
    ds = dataset.dataset_id
    bq.create_dataset(f"{other}.{ds}")
    try:
        run(bq, f"CREATE TABLE `{other}`.{ds}.t AS SELECT 99 AS id")
        assert [r.id for r in run(bq, f"SELECT id FROM {other}.{ds}.t")] == [99]
        assert [r.id for r in run(bq, f"SELECT id FROM {ds}.t ORDER BY id")] == [1, 2]
    finally:
        bq.delete_dataset(f"{other}.{ds}", delete_contents=True)


@pytest.mark.xfail(reason="@@project_id unsupported")
def test_project_id_system_variable(bq, project):
    assert [tuple(r.values()) for r in run(bq, "SELECT @@project_id")] == [(project,)]


@pytest.mark.xfail(reason="notFound message leaks DuckDB error")
def test_missing_table_message(bq, project, dataset):
    with fails(NotFound, "notFound") as info:
        run(bq, f"SELECT * FROM {dataset.dataset_id}.missing")
    assert f"Not found: Table {project}:{dataset.dataset_id}.missing" in str(info.value)


@pytest.mark.xfail(reason="_PARTITIONTIME pseudo-column unsupported")
def test_ingestion_time_pseudo_columns(bq, dataset):
    table = f"{dataset.dataset_id}.{unique('ingested')}"
    run(bq, f"CREATE TABLE {table} (x INT64) PARTITION BY _PARTITIONDATE")
    run(bq, f"INSERT {table} (_PARTITIONTIME, x) VALUES (TIMESTAMP '2020-01-01', 1)")
    assert [
        tuple(r.values())
        for r in run(bq, f"SELECT x, _PARTITIONDATE, _PARTITIONTIME FROM {table}")
    ] == [
        (
            1,
            datetime.date(2020, 1, 1),
            datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC),
        )
    ]
    before = run(bq, f"SELECT x FROM {table} WHERE _PARTITIONDATE < '2019-01-01'")
    assert list(before) == []


@pytest.mark.xfail(reason="require_partition_filter not enforced")
def test_require_partition_filter(bq, dataset):
    table = f"{dataset.dataset_id}.{unique('filtered')}"
    run(
        bq,
        f"CREATE TABLE {table} (d DATE) PARTITION BY d "
        "OPTIONS (require_partition_filter = TRUE)",
    )
    with fails(BadRequest, "invalidQuery"):
        run(bq, f"SELECT * FROM {table}")
    assert list(run(bq, f"SELECT * FROM {table} WHERE d = '2020-01-01'")) == []
