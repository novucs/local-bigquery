CREATE MACRO current_datetime() AS CAST(current_timestamp AS TIMESTAMP),
    (zone) AS timezone(zone, current_timestamp);

CREATE MACRO _week(d, start) AS
    CAST((dayofyear(d) + 6 - (dayofweek(d) - start + 7) % 7) // 7 AS BIGINT);

CREATE MACRO _week_start(d, start) AS
    CAST(d - to_days(CAST((dayofweek(d) - start + 7) % 7 AS INTEGER)) AS DATE);

CREATE MACRO _months(i) AS datepart('year', i) * 12 + datepart('month', i);

CREATE MACRO _micros(i) AS
    datepart('hour', i) * 3600000000 + datepart('minute', i) * 60000000
    + datepart('microsecond', i);

CREATE MACRO justify_days(i) AS
    to_months(CAST(bq.main._months(i) + trunc(datepart('day', i) / 30) AS INTEGER))
    + to_days(CAST(datepart('day', i) - 30 * trunc(datepart('day', i) / 30) AS INTEGER))
    + to_microseconds(bq.main._micros(i));

CREATE MACRO justify_hours(i) AS
    to_months(CAST(bq.main._months(i) AS INTEGER))
    + to_days(CAST(datepart('day', i) + trunc(bq.main._micros(i) / 86400000000) AS INTEGER))
    + to_microseconds(CAST(
        bq.main._micros(i) - 86400000000 * trunc(bq.main._micros(i) / 86400000000) AS BIGINT
    ));

CREATE MACRO justify_interval(i) AS bq.main.justify_days(bq.main.justify_hours(i));

CREATE MACRO _fraction(micros) AS
    CASE WHEN micros % 1000000 = 0 THEN ''
    ELSE rtrim(printf('.%06d', micros % 1000000), '0') END;

CREATE MACRO _interval_string(i) AS
    printf(
        '%s%d-%d %d %s%d:%d:%d',
        CASE WHEN bq.main._months(i) < 0 THEN '-' ELSE '' END,
        abs(bq.main._months(i)) // 12, abs(bq.main._months(i)) % 12, datepart('day', i),
        CASE WHEN bq.main._micros(i) < 0 THEN '-' ELSE '' END,
        abs(bq.main._micros(i)) // 3600000000,
        abs(bq.main._micros(i)) // 60000000 % 60,
        abs(bq.main._micros(i)) // 1000000 % 60
    ) || bq.main._fraction(abs(bq.main._micros(i)));

CREATE MACRO _offset(seconds, separator, minutes) AS
    CASE WHEN seconds < 0 THEN '-' ELSE '+' END
    || lpad(CAST(abs(seconds) // 3600 AS VARCHAR), 2, '0')
    || CASE WHEN minutes OR abs(seconds) % 3600 <> 0
        THEN separator || lpad(CAST(abs(seconds) % 3600 // 60 AS VARCHAR), 2, '0')
        ELSE '' END;

CREATE MACRO _timestamp_string(ts, local) AS
    strftime(local, '%Y-%m-%d %H:%M:%S') || bq.main._fraction(microsecond(local))
    || bq.main._offset(CAST(epoch(local) - epoch(ts) AS BIGINT), ':', false);

CREATE MACRO _seconds(ts, digits) AS strftime(ts, '%S') || CASE WHEN digits = 0 THEN ''
    ELSE '.' || left(lpad(CAST(microsecond(ts) % 1000000 AS VARCHAR), 6, '0'), digits) END;

CREATE MACRO date_bucket(d, width) AS time_bucket(width, d, DATE '1950-01-01'),
    (d, width, origin) AS time_bucket(width, d, origin);

CREATE MACRO datetime_bucket(d, width) AS time_bucket(width, d, TIMESTAMP '1950-01-01'),
    (d, width, origin) AS time_bucket(width, d, origin);

CREATE MACRO timestamp_bucket(ts, width) AS
    timezone('UTC', time_bucket(width, timezone('UTC', ts), TIMESTAMP '1950-01-01')),
    (ts, width, origin) AS
    timezone('UTC', time_bucket(width, timezone('UTC', ts), timezone('UTC', origin)));
