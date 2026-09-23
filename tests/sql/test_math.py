import math
from decimal import Decimal

import pytest

from tests.cases import q

INT64_MAX = 9223372036854775807
INT64_MIN = -9223372036854775808
NAN = "CAST('NaN' AS FLOAT64)"

CASES = [
    q("SELECT 1 + 2, 5 - 7, 3 * 4", rows=[(3, -2, 12)], types=("INT64",) * 3),
    q("SELECT -(3)", -3),
    q("SELECT 7 / 2", 3.5, types="FLOAT64"),
    q("SELECT 6 / 3", 2.0, types="FLOAT64"),
    q("SELECT 2147483647 + 1", 2147483648),
    q("SELECT DIV(7, 2), DIV(-7, 2)", rows=[(3, -3)], types=("INT64", "INT64")),
    q("SELECT MOD(-7, 2), MOD(7, -2)", rows=[(-1, 1)]),
    q("SELECT MOD(NULL, 2)", None),
    q(
        "SELECT DIV(NUMERIC '7', 2)",
        Decimal("3"),
        types="NUMERIC",
    ),
    q(
        "SELECT MOD(NUMERIC '7.5', 2)",
        Decimal("1.5"),
        types="NUMERIC",
    ),
    q("SELECT 1 / 0", error="division by zero"),
    q(
        "SELECT x FROM UNNEST([0]) AS x WHERE 1 / x > 0",
        error="division by zero",
    ),
    q(
        "SELECT DIV(1, 0)",
        error="division by zero",
    ),
    q(
        "SELECT MOD(1, 0)",
        error="division by zero",
    ),
    q(
        "SELECT IEEE_DIVIDE(1, 0), IEEE_DIVIDE(-1, 0)",
        rows=[(math.inf, -math.inf)],
    ),
    q("SELECT IEEE_DIVIDE(0, 0)", math.nan),
    q("SELECT SAFE_DIVIDE(1, 0), SAFE_DIVIDE(0, 0)", rows=[(None, None)]),
    q("SELECT SAFE_DIVIDE(6, 3)", 2.0),
    q(f"SELECT {INT64_MAX} + 1", error="(?i)overflow"),
    q(f"SELECT {INT64_MAX} * 2", error="(?i)overflow"),
    q(
        f"SELECT -({INT64_MIN})",
        error="(?i)overflow",
    ),
    q(f"SELECT ABS({INT64_MIN})", error="(?i)overflow"),
    q(f"SELECT SAFE_ADD({INT64_MAX}, 1)", None),
    q(f"SELECT SAFE_SUBTRACT({INT64_MIN}, 1)", None),
    q(f"SELECT SAFE_MULTIPLY({INT64_MAX}, 2)", None),
    q(f"SELECT SAFE_NEGATE({INT64_MIN})", None),
    q(
        "SELECT SAFE_ADD(1, 2), SAFE_NEGATE(5)",
        rows=[(3, -5)],
    ),
    q("SELECT LN(0)", error="invalidQuery"),
    q("SELECT SQRT(-1)", error="invalidQuery"),
    q(
        "SELECT SAFE.LN(-1), SAFE.SQRT(-1)",
        rows=[(None, None)],
    ),
    q(
        "SELECT SAFE.LN(1 / 0)",
        error="division by zero",
    ),
    q("SELECT ROUND(2.5), ROUND(-2.5), ROUND(3.5)", rows=[(3.0, -3.0, 4.0)]),
    q("SELECT ROUND(1.2345, 2)", 1.23),
    q("SELECT ROUND(1234.5, -2)", 1200.0),
    q(
        "SELECT ROUND(NUMERIC '2.5')",
        Decimal("3"),
        types="NUMERIC",
    ),
    q(
        "SELECT ROUND(NUMERIC '1.005', 2)",
        Decimal("1.01"),
    ),
    q("SELECT ROUND(NULL)", None),
    q("SELECT TRUNC(1.7), TRUNC(-1.7)", rows=[(1.0, -1.0)]),
    q("SELECT TRUNC(1.2345, 2)", 1.23),
    q("SELECT CEIL(1.2), CEIL(-1.2)", rows=[(2.0, -1.0)]),
    q("SELECT CEILING(1.2)", 2.0),
    q("SELECT FLOOR(1.8), FLOOR(-1.2)", rows=[(1.0, -2.0)]),
    q("SELECT CEIL(1)", 1.0, types="FLOAT64"),
    q("SELECT ABS(-3), ABS(-2.5)", rows=[(3, 2.5)], types=("INT64", "FLOAT64")),
    q(
        "SELECT SIGN(-5), SIGN(0), SIGN(2.5)",
        rows=[(-1, 0, 1.0)],
    ),
    q("SELECT SIGN(NULL)", None),
    q("SELECT POW(2, 10), POWER(4, 0.5)", rows=[(1024.0, 2.0)]),
    q("SELECT POW(0, 0)", 1.0),
    q("SELECT SQRT(16), EXP(0), LN(1)", rows=[(4.0, 1.0, 0.0)]),
    q("SELECT LOG(8, 2), LOG10(1000), LOG(1)", rows=[(3.0, 3.0, 0.0)]),
    q("SELECT CBRT(27), CBRT(-8)", rows=[(3.0, -2.0)]),
    q("SELECT SIN(0), COS(0), TAN(0)", rows=[(0.0, 1.0, 0.0)]),
    q("SELECT ASIN(1), ACOS(1), ATAN(1)", rows=[(math.pi / 2, 0.0, math.pi / 4)]),
    q("SELECT ATAN2(1, 1)", math.pi / 4),
    q("SELECT SINH(0), COSH(0), TANH(0)", rows=[(0.0, 1.0, 0.0)]),
    q("SELECT ASINH(0), ACOSH(1), ATANH(0)", rows=[(0.0, 0.0, 0.0)]),
    q(
        "SELECT COT(1), SEC(0), CSC(1)",
        rows=[(1 / math.tan(1), 1.0, 1 / math.sin(1))],
    ),
    q("SELECT GREATEST(1, 3, 2), LEAST(4, 2, 3)", rows=[(3, 2)]),
    q("SELECT GREATEST(1, NULL), LEAST(1, NULL)", rows=[(None, None)]),
    q("SELECT LEAST(1.5, 2)", 1.5, types="FLOAT64"),
    q(f"SELECT IS_NAN({NAN}), IS_NAN(1.0)", rows=[(True, False)]),
    q("SELECT IS_INF(CAST('inf' AS FLOAT64)), IS_INF(1.0)", rows=[(True, False)]),
    q(
        f"SELECT ARRAY_AGG(x ORDER BY x) FROM UNNEST([1.0, {NAN}, "
        "CAST('-inf' AS FLOAT64)]) AS x",
        [math.nan, -math.inf, 1.0],
    ),
    q("SELECT 5 & 3, 5 | 3, 5 ^ 3, ~0", rows=[(1, 7, 6, -1)]),
    q("SELECT 1 << 4, 1 << 64", rows=[(16, 0)]),
    q("SELECT -16 >> 2", 4611686018427387900),
    q("SELECT BIT_COUNT(7)", 3),
    q(r"SELECT b'\x05' & b'\x03'", b"\x01"),
    q("SELECT RAND() >= 0 AND RAND() < 1", True),
    q("SELECT RANGE_BUCKET(20, [0, 10, 20, 30])", 3),
    q("SELECT RANGE_BUCKET(-1, [0, 10])", 0),
    q("SELECT RANGE_BUCKET(5, [])", 0),
    q("SELECT RANGE_BUCKET(NULL, [1])", None),
    q("SELECT CAST(1e20 AS INT64)", error="invalidQuery"),
    q(f"SELECT CAST({NAN} AS INT64)", error="invalidQuery"),
    q(
        "SELECT CAST(0.1 + 0.2 AS STRING)",
        "0.30000000000000004",
    ),
    q(
        "SELECT NUMERIC '99999999999999999999999999999.999999999' + 1",
        error="(?i)overflow",
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_math(check, case):
    check(case)
