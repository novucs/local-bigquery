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
CREATE MACRO _interval_months(i) AS datepart('year', i) * 12 + datepart('month', i);
CREATE MACRO _interval_micros(i) AS
    datepart('hour', i) * 3600000000 + datepart('minute', i) * 60000000
    + datepart('microsecond', i);
CREATE MACRO justify_days(i) AS
    to_months(CAST(bq.main._interval_months(i) + trunc(datepart('day', i) / 30) AS INTEGER))
    + to_days(CAST(datepart('day', i) - 30 * trunc(datepart('day', i) / 30) AS INTEGER))
    + to_microseconds(bq.main._interval_micros(i));
CREATE MACRO justify_hours(i) AS
    to_months(CAST(bq.main._interval_months(i) AS INTEGER))
    + to_days(CAST(
        datepart('day', i) + trunc(bq.main._interval_micros(i) / 86400000000) AS INTEGER
    ))
    + to_microseconds(CAST(
        bq.main._interval_micros(i)
        - 86400000000 * trunc(bq.main._interval_micros(i) / 86400000000) AS BIGINT
    ));
CREATE MACRO justify_interval(i) AS bq.main.justify_days(bq.main.justify_hours(i));
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
