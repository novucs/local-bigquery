from decimal import Decimal

import pytest

from tests.cases import q, run

NAN = float("nan")


@pytest.fixture(scope="module", autouse=True)
def t(bq, dataset):
    run(
        bq,
        f"CREATE TABLE {dataset.dataset_id}.t "
        "(id INT64, amount NUMERIC, qty INT64, f FLOAT64, j JSON, b BYTES)",
    )
    run(
        bq,
        f"INSERT INTO {dataset.dataset_id}.t VALUES "
        """(1, 100, 4, 2.5, JSON '{"xs": [10, 20]}', b'\\x05'), """
        "(2, 250.5, 2, CAST('nan' AS FLOAT64), NULL, NULL), "
        "(3, 75, 3, NULL, NULL, NULL)",
    )


CASES = [
    q(
        "SELECT AVG(amount) FROM t",
        Decimal("141.833333333"),
        types="NUMERIC",
    ),
    q(
        "SELECT SUM(amount) / COUNT(*) FROM t",
        Decimal("141.833333333"),
        types="NUMERIC",
    ),
    q(
        "SELECT amount / qty FROM t ORDER BY id",
        rows=[(Decimal("25"),), (Decimal("125.25"),), (Decimal("25"),)],
        types="NUMERIC",
    ),
    q(
        "SELECT amount * qty FROM t ORDER BY id",
        rows=[(Decimal("400"),), (Decimal("501"),), (Decimal("225"),)],
        types="NUMERIC",
    ),
    q(
        "SELECT AVG(amount) OVER (ORDER BY id ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) "
        "FROM t ORDER BY id",
        rows=[(Decimal("100"),), (Decimal("175.25"),), (Decimal("162.75"),)],
        types="NUMERIC",
    ),
    q(
        "WITH c AS (SELECT amount FROM t) SELECT MAX(amount) / 2 FROM c",
        Decimal("125.25"),
        types="NUMERIC",
    ),
    q("SELECT amount / 2.0 FROM t WHERE id = 1", Decimal("50"), types="NUMERIC"),
    q("SELECT ROUND(SUM(amount) / 7.0, 4) FROM t", Decimal("60.7857"), types="NUMERIC"),
    q("SELECT amount / CAST(2 AS FLOAT64) FROM t WHERE id = 1", 50.0, types="FLOAT64"),
    q(
        "SELECT f FROM t ORDER BY f",
        rows=[(None,), (NAN,), (2.5,)],
    ),
    q(
        "SELECT f FROM t ORDER BY f DESC",
        rows=[(2.5,), (NAN,), (None,)],
    ),
    q("SELECT CAST(f AS INT64) FROM t WHERE id = 1", 3),
    q("SELECT j.xs[1] FROM t WHERE id = 1", 20, types="JSON"),
    q(
        "SELECT TO_JSON_STRING(STRUCT(b AS b)) FROM t WHERE id = 1",
        '{"b":"BQ=="}',
    ),
    q(r"SELECT b & b'\x03' FROM t WHERE id = 1", b"\x01"),
]


@pytest.mark.parametrize("case", CASES)
def test_numeric(check, case):
    check(case)
