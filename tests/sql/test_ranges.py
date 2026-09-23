import datetime

import pytest

from tests.cases import q, run


def d(day: int) -> datetime.date:
    return datetime.date(2024, 1, day)


def r(start: int, end: int) -> dict:
    return {"start": d(start), "end": d(end)}


@pytest.fixture(scope="module", autouse=True)
def seed(bq, dataset):
    run(
        bq,
        f"CREATE TABLE {dataset.dataset_id}.visits (who STRING, span RANGE<DATE>); "
        f"INSERT INTO {dataset.dataset_id}.visits VALUES "
        "('a', RANGE<DATE> '[2024-01-01, 2024-01-03)'), "
        "('a', RANGE<DATE> '[2024-01-03, 2024-01-05)'), "
        "('a', RANGE<DATE> '[2024-01-04, 2024-01-06)'), "
        "('a', RANGE<DATE> '[2024-01-09, 2024-01-10)'), "
        "('b', RANGE<DATE> '[2024-01-02, 2024-01-04)'), "
        "('c', RANGE<DATE> '[2024-01-01, 2024-01-02)'), "
        "('c', NULL), "
        "('c', RANGE<DATE> '[2024-01-05, 2024-01-06)'); "
        f"CREATE TABLE {dataset.dataset_id}.nothing (who STRING, span RANGE<DATE>)",
    )


SESSIONS = (
    "SELECT who, span, session_range "
    "FROM RANGE_SESSIONIZE(TABLE visits, 'span', ['who']"
)

CASES = [
    q(
        "SELECT GENERATE_RANGE_ARRAY("
        "RANGE<DATE> '[2024-01-01, 2024-01-06)', INTERVAL 2 DAY)",
        [r(1, 3), r(3, 5), r(5, 6)],
        types="ARRAY<RANGE>",
    ),
    q(
        "SELECT GENERATE_RANGE_ARRAY("
        "RANGE<DATE> '[2024-01-01, 2024-01-06)', INTERVAL 2 DAY, FALSE)",
        [r(1, 3), r(3, 5)],
    ),
    q(
        f"{SESSIONS}) WHERE who IN ('a', 'b') ORDER BY who, span",
        rows=[
            ("a", r(1, 3), r(1, 6)),
            ("a", r(3, 5), r(1, 6)),
            ("a", r(4, 6), r(1, 6)),
            ("a", r(9, 10), r(9, 10)),
            ("b", r(2, 4), r(2, 4)),
        ],
    ),
    q(
        f"{SESSIONS}, 'OVERLAPS') WHERE who = 'a' ORDER BY span",
        rows=[
            ("a", r(1, 3), r(1, 3)),
            ("a", r(3, 5), r(3, 6)),
            ("a", r(4, 6), r(3, 6)),
            ("a", r(9, 10), r(9, 10)),
        ],
    ),
    q(
        f"{SESSIONS}) WHERE who = 'c' ORDER BY span NULLS FIRST",
        rows=[("c", None, None), ("c", r(1, 2), r(1, 6)), ("c", r(5, 6), r(1, 6))],
        xfail="NULL ranges do not bridge sessions in insertion order",
    ),
    q(
        "SELECT * FROM RANGE_SESSIONIZE(TABLE nothing, 'span', ['who'])",
        rows=[],
    ),
    q(
        f"{SESSIONS}, 'ADJACENT')",
        error='Could not cast literal "ADJACENT" to type RANGE_SESSIONIZE_MODE',
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_ranges(check, case):
    check(case)
