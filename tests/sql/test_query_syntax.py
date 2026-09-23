import pytest
from google.cloud import bigquery

from tests.cases import q, run


@pytest.fixture(scope="module", autouse=True)
def tables(bq, dataset):
    run(
        bq,
        f"""
        CREATE TABLE {dataset.dataset_id}.l (id INT64, x STRING);
        CREATE TABLE {dataset.dataset_id}.r (id INT64, y STRING);
        INSERT INTO {dataset.dataset_id}.l (id, x) VALUES (1, 'a'), (2, 'b'), (NULL, 'n');
        INSERT INTO {dataset.dataset_id}.r (id, y) VALUES (1, 'A'), (3, 'C'), (NULL, 'N')
        """,
    )


CASES = [
    q("SELECT x, y FROM l JOIN r ON l.id = r.id", rows=[("a", "A")]),
    q(
        "SELECT x, y FROM l LEFT JOIN r ON l.id = r.id ORDER BY x",
        rows=[("a", "A"), ("b", None), ("n", None)],
    ),
    q(
        "SELECT x, y FROM l RIGHT JOIN r ON l.id = r.id ORDER BY y",
        rows=[("a", "A"), (None, "C"), (None, "N")],
    ),
    q(
        "SELECT x, y FROM l FULL JOIN r ON l.id = r.id ORDER BY x, y",
        rows=[(None, "C"), (None, "N"), ("a", "A"), ("b", None), ("n", None)],
    ),
    q("SELECT COUNT(*) FROM l CROSS JOIN r", 9),
    q("SELECT COUNT(*) FROM l, r", 9),
    q("SELECT id, x, y FROM l JOIN r USING (id)", rows=[(1, "a", "A")]),
    q(
        "SELECT x, y FROM l LEFT JOIN r ON l.id = r.id AND r.y = 'Z' ORDER BY x",
        rows=[("a", None), ("b", None), ("n", None)],
    ),
    q("SELECT x FROM l WHERE EXISTS (SELECT 1 FROM r WHERE r.id = l.id)", "a"),
    q("SELECT x FROM l WHERE id NOT IN (SELECT id FROM r)", rows=[]),
    q("SELECT x FROM l WHERE id NOT IN (SELECT id FROM r WHERE id IS NOT NULL)", "b"),
    q("SELECT 1 IN (SELECT id FROM r WHERE FALSE)", False),
    q("SELECT NULL IN (SELECT id FROM r WHERE FALSE)", False),
    q("SELECT 1 IN (2, NULL), 1 IN (1, NULL)", rows=[(None, True)]),
    q("SELECT (SELECT MAX(id) FROM r)", 3),
    q(
        "SELECT x, (SELECT y FROM r WHERE r.id = l.id) FROM l ORDER BY x",
        rows=[("a", "A"), ("b", None), ("n", None)],
    ),
    q(
        "SELECT (SELECT id FROM r)",
        error="(?i)more than one element",
    ),
    q("SELECT ARRAY(SELECT id FROM r WHERE id IS NOT NULL ORDER BY id)", [1, 3]),
    q("SELECT EXISTS (SELECT 1 FROM r WHERE FALSE)", False),
    q("SELECT 1 UNION ALL SELECT 1", rows=[(1,), (1,)]),
    q("SELECT 1 UNION DISTINCT SELECT 1", 1),
    q("SELECT id FROM l WHERE id IS NOT NULL INTERSECT DISTINCT SELECT id FROM r", 1),
    q("SELECT id FROM l WHERE id IS NOT NULL EXCEPT DISTINCT SELECT id FROM r", 2),
    q(
        "SELECT a FROM (SELECT 1 AS a UNION ALL SELECT 2 AS b) ORDER BY a",
        rows=[(1,), (2,)],
    ),
    q(
        "SELECT x FROM (SELECT 1 AS x UNION ALL SELECT 2.5) ORDER BY x",
        rows=[(1.0,), (2.5,)],
        types="FLOAT64",
    ),
    q(
        "SELECT * FROM (SELECT 1 AS a, 2 AS b UNION ALL CORRESPONDING "
        "SELECT 3 AS b, 4 AS a) ORDER BY a",
        rows=[(1, 2), (4, 3)],
    ),
    q(
        "SELECT * FROM (SELECT 1 AS a, 2 AS b UNION ALL BY NAME SELECT 3 AS b, 4 AS a) "
        "ORDER BY a",
        rows=[(1, 2), (4, 3)],
    ),
    q(
        "SELECT * FROM (SELECT 'a' AS g, 1 AS v UNION ALL SELECT 'a', 2 "
        "UNION ALL SELECT 'b', 3) PIVOT (SUM(v) FOR g IN ('a', 'b'))",
        rows=[(3, 3)],
    ),
    q(
        "SELECT * FROM (SELECT 1 AS id, 10 AS q1, 20 AS q2) "
        "UNPIVOT (sales FOR quarter IN (q1, q2)) ORDER BY quarter",
        rows=[(1, 10, "q1"), (1, 20, "q2")],
    ),
    q("SELECT * EXCEPT (b) FROM (SELECT 1 AS a, 2 AS b, 3 AS c)", rows=[(1, 3)]),
    q("SELECT * REPLACE (b * 10 AS b) FROM (SELECT 1 AS a, 2 AS b)", rows=[(1, 20)]),
    q(
        "SELECT ARRAY(SELECT AS STRUCT 1 AS a, 'x' AS b)",
        [{"a": 1, "b": "x"}],
        types="ARRAY<STRUCT<a INT64, b STRING>>",
    ),
    q("SELECT ARRAY(SELECT AS VALUE STRUCT(1 AS a))", [{"a": 1}]),
    q(
        "WITH cte AS (SELECT 1 AS a, 2 AS b) SELECT alias.a, alias.b FROM cte AS alias",
        rows=[(1, 2)],
    ),
    q("WITH a AS (SELECT 1 AS x), b AS (SELECT x + 1 AS x FROM a) SELECT x FROM b", 2),
    q(
        "WITH RECURSIVE n AS (SELECT 1 AS i UNION ALL SELECT i + 1 FROM n WHERE i < 5) "
        "SELECT SUM(i) FROM n",
        15,
        types="INT64",
    ),
    q(
        "SELECT x FROM UNNEST([2, NULL, 1]) AS x ORDER BY x",
        rows=[(None,), (1,), (2,)],
    ),
    q(
        "SELECT x FROM UNNEST([2, NULL, 1]) AS x ORDER BY x DESC",
        rows=[(2,), (1,), (None,)],
    ),
    q(
        "SELECT x FROM UNNEST([2, NULL, 1]) AS x ORDER BY x NULLS LAST",
        rows=[(1,), (2,), (None,)],
    ),
    q(
        "SELECT x FROM UNNEST([1, 2, 3, 4]) AS x ORDER BY x LIMIT 2 OFFSET 1",
        rows=[(2,), (3,)],
    ),
    q("SELECT x FROM UNNEST([1, 2]) AS x LIMIT 0", rows=[]),
    q(
        "SELECT DISTINCT x FROM UNNEST([1, 1, NULL, NULL]) AS x ORDER BY x",
        rows=[(None,), (1,)],
    ),
    q("SELECT * FROM l WHERE FALSE", rows=[], types=("INT64", "STRING")),
    q(
        "SELECT CASE 2 WHEN 1 THEN 'one' WHEN 2 THEN 'two' ELSE 'many' END, "
        "CASE WHEN NULL THEN 'yes' ELSE 'no' END",
        rows=[("two", "no")],
    ),
    q(
        "SELECT IF(1 > 0, 'y', 'n'), IFNULL(NULL, 'd'), COALESCE(NULL, NULL, 3)",
        rows=[("y", "d", 3)],
    ),
    q("SELECT NULLIF(1, 1), NULLIF(1, 2)", rows=[(None, 1)]),
    q("SELECT 2 BETWEEN 1 AND 3, NULL BETWEEN 1 AND 3", rows=[(True, None)]),
    q(
        "SELECT NULL IS DISTINCT FROM NULL, 1 IS DISTINCT FROM NULL",
        rows=[(False, True)],
    ),
    q("SELECT A FROM (SELECT 1 AS a)", 1),
    q("SELECT `my col` FROM (SELECT 1 AS `my col`)", 1),
    q("SELECT 1 -- line\n + 1 # hash\n /* block */", 2),
    q("SELECT COUNT(*) FROM l TABLESAMPLE SYSTEM (100 PERCENT)", 3),
    q("FROM l |> WHERE id IS NOT NULL |> AGGREGATE COUNT(*) AS c", 2),
    q(
        "FROM l |> WHERE id IS NOT NULL |> SELECT x |> ORDER BY x DESC",
        rows=[("b",), ("a",)],
    ),
    q("CREATE OR REPLACE TABLE m AS SELECT 1 AS b; SELECT b FROM m", 1),
    q("CREATE TEMP TABLE tmp AS SELECT 2 AS b; SELECT b FROM tmp", 2),
    q(
        "SELECT 1 AS a, 2 AS a",
        rows=[(1, 2)],
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_query_syntax(check, case):
    check(case)


def names(bq, dataset, sql):
    config = bigquery.QueryJobConfig(default_dataset=dataset.reference)
    return [field.name for field in run(bq, sql, config).schema]


def test_anonymous_columns_are_numbered(bq, dataset):
    assert names(bq, dataset, "SELECT 1 AS a, 2, 3") == ["a", "f0_", "f1_"]


def test_aggregate_columns_are_anonymous(bq, dataset):
    assert names(bq, dataset, "SELECT x, COUNT(*) FROM l GROUP BY x") == ["x", "f0_"]


def test_columns_are_named_after_references(bq, dataset):
    sql = "SELECT l.x, s.a FROM l, (SELECT STRUCT(1 AS a) AS s) LIMIT 1"
    assert names(bq, dataset, sql) == ["x", "a"]


def test_duplicate_columns_get_suffixes(bq, dataset):
    sql = "SELECT a.x, b.x, a.x FROM l AS a, l AS b LIMIT 1"
    assert names(bq, dataset, sql) == ["x", "x_1", "x_2"]
