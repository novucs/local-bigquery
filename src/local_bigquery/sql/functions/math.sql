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
    CASE WHEN point IS NULL THEN NULL ELSE len(list_filter(boundaries, b -> b <= point)) END;
CREATE MACRO parse_numeric(s) AS CAST(trim(s) AS DECIMAL(38, 9));
CREATE MACRO parse_bignumeric(s) AS CAST(trim(s) AS DECIMAL(38, 18));
CREATE MACRO _shift_left(a, b) AS
    CASE
        WHEN b < 0 THEN error('Bit shift by negative value is not allowed')
        WHEN b >= 64 THEN 0
        ELSE CAST(a AS BIGINT) << b
    END;
CREATE MACRO _shift_right(a, b) AS
    CASE
        WHEN b < 0 THEN error('Bit shift by negative value is not allowed')
        WHEN b >= 64 THEN 0
        WHEN b = 0 THEN CAST(a AS BIGINT)
        ELSE (CAST(a AS BIGINT) >> b) & (9223372036854775807 >> (b - 1))
    END;
