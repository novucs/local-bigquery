CREATE MACRO ieee_divide(a, b) AS
    CASE
        WHEN a IS NULL OR b IS NULL THEN NULL
        WHEN b <> 0 THEN CAST(a AS DOUBLE) / b
        WHEN a > 0 THEN CAST('inf' AS DOUBLE)
        WHEN a < 0 THEN CAST('-inf' AS DOUBLE)
        ELSE CAST('nan' AS DOUBLE)
    END;
CREATE MACRO safe_add(a, b) AS TRY(a + b);
CREATE MACRO safe_subtract(a, b) AS TRY(a - b);
CREATE MACRO safe_multiply(a, b) AS TRY(a * b);
CREATE MACRO safe_negate(a) AS TRY(-a);
CREATE MACRO sec(x) AS 1 / cos(x);
CREATE MACRO csc(x) AS 1 / sin(x);
CREATE MACRO range_bucket(point, boundaries) AS
    CASE WHEN point IS NULL THEN NULL ELSE len(list_filter(boundaries, lambda b: b <= point)) END;
CREATE MACRO parse_numeric(s) AS CAST(trim(s) AS DECIMAL(38, 9));
CREATE MACRO parse_bignumeric(s) AS CAST(trim(s) AS DECIMAL(38, 18));
CREATE MACRO _shift_left(a, b) AS
    CASE
        WHEN b < 0 THEN _raise('Bit shift by negative value is not allowed')
        WHEN b >= 64 THEN 0
        ELSE CAST(a AS BIGINT) << b
    END;
CREATE MACRO _shift_right(a, b) AS
    CASE
        WHEN b < 0 THEN _raise('Bit shift by negative value is not allowed')
        WHEN b >= 64 THEN 0
        WHEN b = 0 THEN CAST(a AS BIGINT)
        ELSE (CAST(a AS BIGINT) >> b) & (9223372036854775807 >> (b - 1))
    END;
CREATE MACRO _logarithm(x, value) AS
    CASE
        WHEN x = 0 THEN _raise('cannot take logarithm of zero')
        WHEN x < 0 THEN _raise('cannot take logarithm of a negative number')
        ELSE value
    END;
CREATE MACRO _ln(x) AS bq.main._logarithm(x, ln(x));
CREATE MACRO _log(x, base) AS CASE
    WHEN base = 1 THEN _raise('cannot take logarithm with base 1')
    ELSE bq.main._logarithm(base, bq.main._logarithm(x, log(base, x)))
END;
CREATE MACRO _sqrt(x) AS
    CASE WHEN x < 0 THEN _raise('cannot take square root of a negative number') ELSE sqrt(x) END;
CREATE MACRO _acos(x) AS
    CASE WHEN isfinite(x) AND abs(x) > 1 THEN _raise('ACOS is undefined outside [-1,1]') ELSE acos(x) END;
CREATE MACRO _asin(x) AS
    CASE WHEN isfinite(x) AND abs(x) > 1 THEN _raise('ASIN is undefined outside [-1,1]') ELSE asin(x) END;
CREATE MACRO _atanh(x) AS
    CASE WHEN isfinite(x) AND abs(x) > 1 THEN _raise('ATANH is undefined outside [-1,1]') ELSE atanh(x) END;
CREATE MACRO coth(x) AS 1 / tanh(x);
CREATE MACRO csch(x) AS 1 / sinh(x);
CREATE MACRO sech(x) AS 1 / cosh(x);
