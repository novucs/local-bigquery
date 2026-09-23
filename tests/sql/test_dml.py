import pytest
from google.api_core.exceptions import BadRequest, NotFound

from tests.cases import fails, rows, run, run_job, unique


@pytest.fixture
def table(bq, dataset):
    table = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table} (id INT64, name STRING, qty INT64)")
    run(bq, f"INSERT {table} VALUES (1, 'a', 10), (2, 'b', 20), (3, 'c', NULL)")
    return table


@pytest.mark.xfail(reason="DML statistics not reported")
def test_insert_values(bq, table):
    insert = run_job(bq, f"INSERT INTO {table} (id, name) VALUES (4, 'd'), (5, 'e')")
    assert insert.statement_type == "INSERT"
    assert insert.num_dml_affected_rows == 2
    assert insert.dml_stats.inserted_row_count == 2
    assert rows(bq, f"SELECT * FROM {table} WHERE id > 3 ORDER BY id") == [
        (4, "d", None),
        (5, "e", None),
    ]


@pytest.mark.xfail(reason="DML statistics not reported")
def test_insert_select(bq, table):
    insert = run_job(bq, f"INSERT {table} SELECT id + 10, name, qty FROM {table}")
    assert insert.num_dml_affected_rows == 3
    assert rows(bq, f"SELECT COUNT(*) FROM {table}") == [(6,)]


def test_insert_default_values(bq, dataset):
    table = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table} (id INT64, v STRING DEFAULT 'd')")
    run(bq, f"INSERT {table} (id) VALUES (1)")
    run(bq, f"INSERT {table} VALUES (2, DEFAULT)")
    assert rows(bq, f"SELECT * FROM {table} ORDER BY id") == [(1, "d"), (2, "d")]


def test_insert_nested_values(bq, dataset):
    table = f"{dataset.dataset_id}.{unique('t')}"
    run(
        bq, f"CREATE TABLE {table} (tags ARRAY<STRING>, info STRUCT<a INT64, b STRING>)"
    )
    run(bq, f"INSERT {table} VALUES (['x', 'y'], (1, 'p')), ([], NULL)")
    assert rows(bq, f"SELECT * FROM {table} ORDER BY info.a NULLS LAST") == [
        (["x", "y"], {"a": 1, "b": "p"}),
        ([], None),
    ]


def test_insert_type_mismatch(bq, table):
    with fails(BadRequest, "invalidQuery"):
        run(bq, f"INSERT {table} (id) VALUES ('x')")


def test_insert_null_into_required_column(bq, dataset):
    table = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table} (id INT64 NOT NULL)")
    with pytest.raises(BadRequest):
        run(bq, f"INSERT {table} (id) VALUES (NULL)")


@pytest.mark.xfail(reason="DML statistics not reported")
def test_update(bq, table):
    update = run_job(bq, f"UPDATE {table} SET qty = qty + 1 WHERE qty IS NOT NULL")
    assert update.statement_type == "UPDATE"
    assert update.num_dml_affected_rows == 2
    assert update.dml_stats.updated_row_count == 2
    assert rows(bq, f"SELECT qty FROM {table} ORDER BY id") == [(11,), (21,), (None,)]


@pytest.mark.xfail(reason="missing WHERE not rejected")
def test_update_requires_where(bq, table):
    with fails(BadRequest, "invalidQuery"):
        run(bq, f"UPDATE {table} SET qty = 0")


@pytest.mark.xfail(reason="numDmlAffectedRows always 0")
def test_update_where_true(bq, table):
    assert (
        run(bq, f"UPDATE {table} SET name = NULL WHERE TRUE").num_dml_affected_rows == 3
    )
    assert rows(bq, f"SELECT COUNTIF(name IS NULL) FROM {table}") == [(3,)]


def test_update_from_join(bq, dataset, table):
    source = f"{dataset.dataset_id}.{unique('s')}"
    run(bq, f"CREATE TABLE {source} AS SELECT 2 AS id, 99 AS qty")
    run(
        bq,
        f"UPDATE {table} AS t SET qty = s.qty FROM {source} AS s WHERE t.id = s.id",
    )
    assert rows(bq, f"SELECT qty FROM {table} ORDER BY id") == [(10,), (99,), (None,)]


@pytest.mark.xfail(reason="nested field UPDATE unsupported")
def test_update_nested_field(bq, dataset):
    table = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table} (id INT64, info STRUCT<a INT64, b STRING>)")
    run(bq, f"INSERT {table} VALUES (1, (1, 'p'))")
    run(bq, f"UPDATE {table} SET info.a = 5 WHERE id = 1")
    assert rows(bq, f"SELECT info FROM {table}") == [({"a": 5, "b": "p"},)]


@pytest.mark.xfail(reason="DELETE without FROM mistranslated")
def test_delete_without_from_keyword(bq, table):
    delete = run_job(bq, f"DELETE {table} WHERE id = 1")
    assert delete.statement_type == "DELETE"
    assert delete.num_dml_affected_rows == 1
    assert delete.dml_stats.deleted_row_count == 1
    assert rows(bq, f"SELECT id FROM {table} ORDER BY id") == [(2,), (3,)]


def test_delete_with_subquery(bq, table):
    run(bq, f"DELETE FROM {table} WHERE id IN (SELECT id FROM {table} WHERE qty > 15)")
    assert rows(bq, f"SELECT id FROM {table} ORDER BY id") == [(1,), (3,)]


@pytest.mark.xfail(reason="numDmlAffectedRows always 0")
def test_delete_where_true(bq, table):
    assert run(bq, f"DELETE FROM {table} WHERE TRUE").num_dml_affected_rows == 3


def test_delete_null_predicate_deletes_nothing(bq, table):
    assert run(bq, f"DELETE FROM {table} WHERE qty > NULL").num_dml_affected_rows == 0


@pytest.mark.xfail(reason="missing WHERE not rejected")
def test_delete_requires_where(bq, table):
    with fails(BadRequest, "invalidQuery"):
        run(bq, f"DELETE FROM {table}")


@pytest.mark.xfail(reason="multi-action MERGE unsupported on DuckLake")
def test_merge_upsert(bq, table):
    merge = run_job(
        bq,
        f"""
        MERGE {table} T
        USING (SELECT 1 AS id, 'z' AS name, 99 AS qty UNION ALL SELECT 4, 'd', 40) S
        ON T.id = S.id
        WHEN MATCHED THEN UPDATE SET name = S.name, qty = S.qty
        WHEN NOT MATCHED THEN INSERT (id, name, qty) VALUES (S.id, S.name, S.qty)
        """,
    )
    assert merge.statement_type == "MERGE"
    assert merge.num_dml_affected_rows == 2
    assert merge.dml_stats.inserted_row_count == 1
    assert merge.dml_stats.updated_row_count == 1
    assert rows(bq, f"SELECT * FROM {table} ORDER BY id") == [
        (1, "z", 99),
        (2, "b", 20),
        (3, "c", None),
        (4, "d", 40),
    ]


@pytest.mark.xfail(reason="MERGE INSERT ROW unsupported")
def test_merge_insert_row_and_delete_not_matched_by_source(bq, table):
    merge = run(
        bq,
        f"""
        MERGE {table} T
        USING (SELECT 1 AS id, 'a' AS name, 10 AS qty UNION ALL SELECT 9, 'i', 90) S
        ON T.id = S.id
        WHEN NOT MATCHED THEN INSERT ROW
        WHEN NOT MATCHED BY SOURCE THEN DELETE
        """,
    )
    assert merge.num_dml_affected_rows == 3
    assert rows(bq, f"SELECT * FROM {table} ORDER BY id") == [
        (1, "a", 10),
        (9, "i", 90),
    ]


@pytest.mark.xfail(reason="multi-action MERGE unsupported on DuckLake")
def test_merge_first_matching_clause_wins(bq, table):
    run(
        bq,
        f"""
        MERGE {table} T
        USING (SELECT 1 AS id, NULL AS qty UNION ALL SELECT 2, 5) S
        ON T.id = S.id
        WHEN MATCHED AND S.qty IS NULL THEN DELETE
        WHEN MATCHED THEN UPDATE SET qty = S.qty
        """,
    )
    assert rows(bq, f"SELECT id, qty FROM {table} ORDER BY id") == [(2, 5), (3, None)]


def test_merge_null_keys_never_match(bq, table):
    run(
        bq,
        f"""
        MERGE {table} T
        USING (SELECT CAST(NULL AS INT64) AS id) S
        ON T.id = S.id
        WHEN NOT MATCHED THEN INSERT (id, name) VALUES (S.id, 'new')
        """,
    )
    assert rows(bq, f"SELECT name FROM {table} WHERE id IS NULL") == [("new",)]


@pytest.mark.xfail(reason="duplicate source matches not rejected")
def test_merge_rejects_multiple_source_matches(bq, table):
    with fails(BadRequest, "invalidQuery"):
        run(
            bq,
            f"""
            MERGE {table} T
            USING (SELECT 1 AS id UNION ALL SELECT 1) S
            ON T.id = S.id
            WHEN MATCHED THEN UPDATE SET qty = 0
            """,
        )


@pytest.mark.xfail(reason="statement type always SELECT")
def test_truncate(bq, table):
    truncate = run_job(bq, f"TRUNCATE TABLE {table}")
    assert truncate.statement_type == "TRUNCATE_TABLE"
    assert rows(bq, f"SELECT COUNT(*) FROM {table}") == [(0,)]


def test_dml_on_missing_table(bq, dataset):
    with fails(NotFound, "notFound"):
        run(bq, f"INSERT {dataset.dataset_id}.missing (id) VALUES (1)")
