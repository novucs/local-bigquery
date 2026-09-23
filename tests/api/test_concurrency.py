from concurrent.futures import ThreadPoolExecutor

from tests.cases import rows, run, scalar, unique


def parallel(work, count: int = 32):
    with ThreadPoolExecutor(16) as pool:
        return list(pool.map(work, range(count)))


def test_queries_and_catalog_calls_interleave(bq, dataset):
    table = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table} AS SELECT 1 AS x")

    def work(i: int):
        match i % 3:
            case 0:
                return [p.project_id for p in bq.list_projects()]
            case 1:
                project = unique("project").replace("_", "-")
                return bq.create_dataset(f"{project}.{unique('ds')}").dataset_id
            case _:
                return rows(bq, f"SELECT x FROM {table}")

    assert len(parallel(work)) == 32


def test_concurrent_dml_on_one_table_is_serialised(bq, dataset):
    table = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table} AS SELECT 0 AS x")
    parallel(lambda _: run(bq, f"UPDATE {table} SET x = x + 1 WHERE TRUE"), 16)
    assert scalar(bq, f"SELECT x FROM {table}") == 16


def test_new_policy_applies_to_concurrent_readers(bq, dataset):
    table = f"{dataset.dataset_id}.{unique('t')}"
    run(bq, f"CREATE TABLE {table} AS SELECT x FROM UNNEST([1, 2, 3]) AS x")
    readers = ThreadPoolExecutor(8)
    busy = [readers.submit(rows, bq, f"SELECT x FROM {table}") for _ in range(16)]
    run(
        bq,
        f"CREATE ROW ACCESS POLICY only_one ON {table} "
        "GRANT TO ('allUsers') FILTER USING (x = 1)",
    )
    for future in busy:
        future.result()
    readers.shutdown()
    assert rows(bq, f"SELECT x FROM {table}") == [(1,)]
