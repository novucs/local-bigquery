from datetime import date, datetime, time, timezone

import pytest

from tests.cases import q


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


CASES = [
    q("SELECT DATE '2020-02-29'", date(2020, 2, 29), types="DATE"),
    q("SELECT DATE(2016, 12, 25)", date(2016, 12, 25)),
    q("SELECT DATE(DATETIME '2016-12-25 23:59:59')", date(2016, 12, 25)),
    q(
        "SELECT DATE(TIMESTAMP '2016-12-25 05:30:00+07', 'America/Los_Angeles')",
        date(2016, 12, 24),
    ),
    q(
        "SELECT DATETIME '2020-07-01 00:00:00'",
        datetime(2020, 7, 1),
        types="DATETIME",
    ),
    q(
        "SELECT DATETIME(2008, 12, 25, 5, 30, 0)",
        datetime(2008, 12, 25, 5, 30),
    ),
    q(
        "SELECT DATETIME(DATE '2020-01-02', TIME '03:04:05')",
        datetime(2020, 1, 2, 3, 4, 5),
    ),
    q("SELECT TIME '12:34:56.789'", time(12, 34, 56, 789000), types="TIME"),
    q("SELECT TIME(15, 30, 0)", time(15, 30)),
    q(
        "SELECT TIME(TIMESTAMP '2008-12-25 15:30:00+08', 'America/Los_Angeles')",
        time(23, 30),
    ),
    q("SELECT TIMESTAMP '2020-01-01 00:00:00+00'", utc(2020, 1, 1), types="TIMESTAMP"),
    q(
        "SELECT TIMESTAMP '2020-07-01 00:00:00'",
        utc(2020, 7, 1),
    ),
    q(
        "SELECT TIMESTAMP '2020-01-01 00:00:00 America/Los_Angeles'",
        utc(2020, 1, 1, 8),
    ),
    q("SELECT TIMESTAMP '2020-01-01 00:00:00-04:30'", utc(2020, 1, 1, 4, 30)),
    q("SELECT TIMESTAMP '2020-01-01 00:00:00+05:45'", utc(2019, 12, 31, 18, 15)),
    q(
        "SELECT TIMESTAMP('2008-12-25 15:30:00', 'America/Los_Angeles')",
        utc(2008, 12, 25, 23, 30),
    ),
    q(
        "SELECT TIMESTAMP(DATETIME '2008-12-25 15:30:00', 'Pacific/Auckland')",
        utc(2008, 12, 25, 2, 30),
    ),
    q(
        "SELECT TIMESTAMP(DATE '2008-12-25')",
        utc(2008, 12, 25),
    ),
    q("SELECT DATE '2019-02-29'", error="invalidQuery"),
    q("SELECT DATE(2019, 2, 29)", error="invalidQuery"),
    q(
        "SELECT TIMESTAMP('2020-01-01', 'Mars/Olympus')",
        error="invalidQuery",
    ),
    q(
        "SELECT CURRENT_DATE(), CURRENT_DATETIME(), CURRENT_TIME(), CURRENT_TIMESTAMP()",
        types=("DATE", "DATETIME", "TIME", "TIMESTAMP"),
    ),
    q("SELECT CURRENT_DATE() = DATE(CURRENT_TIMESTAMP())", True),
    q(
        "SELECT EXTRACT(YEAR FROM d), EXTRACT(MONTH FROM d), EXTRACT(DAY FROM d)"
        " FROM (SELECT DATE '2013-12-25' AS d)",
        rows=[(2013, 12, 25)],
        types=("INT64", "INT64", "INT64"),
    ),
    q(
        "SELECT EXTRACT(ISOYEAR FROM d), EXTRACT(ISOWEEK FROM d),"
        " EXTRACT(YEAR FROM d), EXTRACT(WEEK FROM d)"
        " FROM UNNEST([DATE '2015-12-27', '2015-12-28', '2016-01-02', '2016-01-04'])"
        " AS d ORDER BY d",
        rows=[
            (2015, 52, 2015, 52),
            (2015, 53, 2015, 52),
            (2015, 53, 2016, 0),
            (2016, 1, 2016, 1),
        ],
    ),
    q(
        "SELECT EXTRACT(WEEK(SUNDAY) FROM DATE '2017-11-05'),"
        " EXTRACT(WEEK(MONDAY) FROM DATE '2017-11-05')",
        rows=[(45, 44)],
    ),
    q(
        "SELECT EXTRACT(DAYOFWEEK FROM DATE '2008-12-28'),"
        " EXTRACT(DAYOFWEEK FROM DATE '2008-12-27')",
        rows=[(1, 7)],
    ),
    q("SELECT EXTRACT(DAYOFYEAR FROM DATE '2020-12-31')", 366),
    q("SELECT EXTRACT(QUARTER FROM DATE '2020-08-15')", 3),
    q(
        "SELECT EXTRACT(MILLISECOND FROM t), EXTRACT(MICROSECOND FROM t)"
        " FROM (SELECT TIMESTAMP '2020-01-01 00:00:00.123456+00' AS t)",
        rows=[(123, 123456)],
    ),
    q(
        "SELECT EXTRACT(HOUR FROM TIMESTAMP '2020-01-01 23:30:00+00'"
        " AT TIME ZONE 'Asia/Tokyo')",
        8,
    ),
    q(
        "SELECT EXTRACT(DATE FROM TIMESTAMP '2020-01-01 23:30:00+00'"
        " AT TIME ZONE 'Asia/Tokyo')",
        date(2020, 1, 2),
    ),
    q(
        "SELECT EXTRACT(DATE FROM TIMESTAMP '2020-01-01 23:30:00+00')",
        date(2020, 1, 1),
    ),
    q(
        "SELECT EXTRACT(TIME FROM DATETIME '2020-01-01 12:34:56')",
        time(12, 34, 56),
    ),
    q(
        "SELECT EXTRACT(DAYOFWEEK FROM TIMESTAMP '2020-01-04 23:00:00+00'"
        " AT TIME ZONE 'Asia/Tokyo')",
        1,
    ),
    q("SELECT EXTRACT(YEAR FROM CAST(NULL AS DATE))", None),
    q(
        "SELECT DATE_ADD(DATE '2008-12-25', INTERVAL 5 DAY)",
        date(2008, 12, 30),
        types="DATE",
    ),
    q(
        "SELECT DATE_SUB(DATE '2008-12-25', INTERVAL 5 DAY)",
        date(2008, 12, 20),
    ),
    q(
        "SELECT DATE_ADD(DATE '2020-01-31', INTERVAL 1 MONTH)",
        date(2020, 2, 29),
    ),
    q(
        "SELECT DATE_ADD(DATE '2020-02-29', INTERVAL 1 YEAR)",
        date(2021, 2, 28),
    ),
    q(
        "SELECT DATE_ADD(DATE '2020-01-01', INTERVAL 1 QUARTER),"
        " DATE_ADD(DATE '2020-01-01', INTERVAL 2 WEEK)",
        rows=[(date(2020, 4, 1), date(2020, 1, 15))],
    ),
    q("SELECT DATE_ADD(CAST(NULL AS DATE), INTERVAL 1 DAY)", None),
    q("SELECT DATE '2024-02-28' + 2", date(2024, 3, 1), types="DATE"),
    q("SELECT 2 + DATE '2024-02-28'", date(2024, 3, 1), types="DATE"),
    q("SELECT DATE '2024-03-01' - 1", date(2024, 2, 29), types="DATE"),
    q(
        "SELECT d - n FROM (SELECT DATE '2024-03-01' AS d, CAST(2 AS INT64) AS n)",
        date(2024, 2, 28),
    ),
    q("SELECT '2024-02-28' + 2", date(2024, 3, 1), types="DATE"),
    q("SELECT 'a' + 1", error=r'Could not cast literal "a" to type DATE at \[1:8\]'),
    q(
        "SELECT DATE '2020-01-01' + INTERVAL 1 DAY",
        datetime(2020, 1, 2),
        types="DATETIME",
    ),
    q(
        "SELECT DATETIME_ADD(DATETIME '2008-12-25 15:30:00', INTERVAL 10 MINUTE)",
        datetime(2008, 12, 25, 15, 40),
        types="DATETIME",
    ),
    q(
        "SELECT DATETIME_SUB(DATETIME '2020-03-31 00:00:00', INTERVAL 1 MONTH)",
        datetime(2020, 2, 29),
    ),
    q(
        "SELECT TIMESTAMP_ADD(TIMESTAMP '2008-12-25 15:30:00+00', INTERVAL 10 MINUTE)",
        utc(2008, 12, 25, 15, 40),
        types="TIMESTAMP",
    ),
    q(
        "SELECT TIMESTAMP_SUB(TIMESTAMP '2020-03-09 00:00:00+00', INTERVAL 1 DAY)",
        utc(2020, 3, 8),
    ),
    q(
        "SELECT TIMESTAMP_ADD(TIMESTAMP '2020-01-01 00:00:00+00', INTERVAL 1 MONTH)",
        error="invalidQuery",
    ),
    q(
        "SELECT TIME_ADD(TIME '23:30:00', INTERVAL 60 MINUTE)",
        time(0, 30),
        types="TIME",
    ),
    q("SELECT TIME_SUB(TIME '00:10:00', INTERVAL 20 MINUTE)", time(23, 50)),
    q("SELECT DATE_DIFF(DATE '2010-07-07', DATE '2008-12-25', DAY)", 559),
    q(
        "SELECT DATE_DIFF(DATE '2017-12-18', DATE '2017-12-17', WEEK),"
        " DATE_DIFF(DATE '2017-12-18', DATE '2017-12-17', WEEK(MONDAY)),"
        " DATE_DIFF(DATE '2017-12-18', DATE '2017-12-17', ISOWEEK)",
        rows=[(0, 1, 1)],
    ),
    q(
        "SELECT DATE_DIFF(DATE '2017-12-30', DATE '2014-12-30', YEAR),"
        " DATE_DIFF(DATE '2017-12-30', DATE '2014-12-30', ISOYEAR)",
        rows=[(3, 2)],
    ),
    q("SELECT DATE_DIFF(DATE '2018-01-01', DATE '2017-12-31', YEAR)", 1),
    q("SELECT DATE_DIFF(DATE '2018-01-31', DATE '2018-01-01', MONTH)", 0),
    q(
        "SELECT DATETIME_DIFF(DATETIME '2010-07-07 10:20:00',"
        " DATETIME '2008-12-25 15:30:00', DAY)",
        559,
    ),
    q(
        "SELECT DATETIME_DIFF(DATETIME '2017-10-15 00:00:00',"
        " DATETIME '2017-10-14 00:00:00', WEEK)",
        1,
    ),
    q(
        "SELECT TIMESTAMP_DIFF(TIMESTAMP '2010-07-07 10:20:00+00',"
        " TIMESTAMP '2008-12-25 15:30:00+00', HOUR)",
        13410,
    ),
    q(
        "SELECT TIMESTAMP_DIFF(TIMESTAMP '2018-08-14', TIMESTAMP '2018-10-14', DAY)",
        -61,
    ),
    q(
        "SELECT TIMESTAMP_DIFF(TIMESTAMP '2001-02-01 01:00:00',"
        " TIMESTAMP '2001-02-01 00:00:01', HOUR)",
        0,
    ),
    q(
        "SELECT TIMESTAMP_DIFF(TIMESTAMP '2020-03-09 00:00:00 America/Los_Angeles',"
        " TIMESTAMP '2020-03-08 00:00:00 America/Los_Angeles', HOUR)",
        23,
    ),
    q("SELECT TIME_DIFF(TIME '15:30:00', TIME '14:35:00', MINUTE)", 55),
    q(
        "SELECT DATE_TRUNC(DATE '2008-12-25', MONTH)",
        date(2008, 12, 1),
        types="DATE",
    ),
    q(
        "SELECT DATE_TRUNC(DATE '2017-11-05', WEEK),"
        " DATE_TRUNC(DATE '2017-11-05', WEEK(MONDAY))",
        rows=[(date(2017, 11, 5), date(2017, 10, 30))],
    ),
    q(
        "SELECT DATE_TRUNC(DATE '2015-06-15', ISOYEAR),"
        " DATE_TRUNC(DATE '2015-06-18', ISOWEEK)",
        rows=[(date(2014, 12, 29), date(2015, 6, 15))],
    ),
    q(
        "SELECT DATE_TRUNC(DATE '2020-08-15', QUARTER)",
        date(2020, 7, 1),
    ),
    q(
        "SELECT DATETIME_TRUNC(DATETIME '2008-12-25 15:30:00', DAY)",
        datetime(2008, 12, 25),
        types="DATETIME",
    ),
    q(
        "SELECT TIMESTAMP_TRUNC(TIMESTAMP '2008-12-25 15:30:00+00', DAY)",
        utc(2008, 12, 25),
        types="TIMESTAMP",
    ),
    q(
        "SELECT TIMESTAMP_TRUNC(TIMESTAMP '2008-12-25 15:30:00+00', DAY,"
        " 'America/Los_Angeles')",
        utc(2008, 12, 25, 8),
    ),
    q(
        "SELECT TIMESTAMP_TRUNC(TIMESTAMP '2020-03-08 12:00:00 America/Los_Angeles',"
        " DAY, 'America/Los_Angeles')",
        utc(2020, 3, 8, 8),
    ),
    q(
        "SELECT TIME_TRUNC(TIME '15:30:45', MINUTE)",
        time(15, 30),
    ),
    q(
        "SELECT LAST_DAY(DATE '2008-11-25'), LAST_DAY(DATE '2008-11-25', YEAR)",
        rows=[(date(2008, 11, 30), date(2008, 12, 31))],
        types=("DATE", "DATE"),
    ),
    q("SELECT LAST_DAY(DATE '2020-02-10')", date(2020, 2, 29)),
    q(
        "SELECT LAST_DAY(DATE '2008-11-10', WEEK(SUNDAY)),"
        " LAST_DAY(DATE '2008-11-10', WEEK(MONDAY))",
        rows=[(date(2008, 11, 15), date(2008, 11, 16))],
    ),
    q("SELECT FORMAT_DATE('%x', DATE '2008-12-25')", "12/25/08"),
    q("SELECT FORMAT_DATE('%b-%d-%Y', DATE '2008-12-25')", "Dec-25-2008"),
    q("SELECT FORMAT_DATE('%A %B %j', DATE '2008-12-25')", "Thursday December 360"),
    q(
        "SELECT FORMAT_DATE('%Q', DATE '2008-12-25')",
        "4",
    ),
    q("SELECT FORMAT_DATE('%G-W%V-%u', DATE '2008-12-29')", "2009-W01-1"),
    q(
        "SELECT FORMAT_DATE('%E4Y', DATE '0099-01-01')",
        "0099",
    ),
    q(
        "SELECT FORMAT_DATETIME('%c', DATETIME '2008-12-25 15:30:00')",
        "Thu Dec 25 15:30:00 2008",
    ),
    q(
        "SELECT FORMAT_TIME('%R', TIME '15:30:00')",
        "15:30",
    ),
    q(
        "SELECT FORMAT_TIMESTAMP('%F %T', TIMESTAMP '2020-07-01 00:00:00+00')",
        "2020-07-01 00:00:00",
    ),
    q(
        "SELECT FORMAT_TIMESTAMP('%c', TIMESTAMP '2050-12-25 15:30:55+00', 'UTC')",
        "Sun Dec 25 15:30:55 2050",
    ),
    q(
        "SELECT FORMAT_TIMESTAMP('%Ez %z', TIMESTAMP '2020-01-01 00:00:00+00',"
        " 'Asia/Kolkata')",
        "+05:30 +0530",
    ),
    q(
        "SELECT FORMAT_TIMESTAMP('%H:%M:%E3S', TIMESTAMP '2020-01-01 00:00:00.123456+00')",
        "00:00:00.123",
    ),
    q(
        "SELECT FORMAT_TIMESTAMP('%s', TIMESTAMP '2020-01-01 00:00:00+00')",
        "1577836800",
    ),
    q("SELECT PARSE_DATE('%Y%m%d', '20081225')", date(2008, 12, 25), types="DATE"),
    q("SELECT PARSE_DATE('%F', '2000-12-30')", date(2000, 12, 30)),
    q(
        "SELECT PARSE_DATE('%A %b %e %Y', 'Thursday Dec 25 2008')",
        date(2008, 12, 25),
    ),
    q(
        "SELECT PARSE_DATETIME('%Y-%m-%d %H:%M:%S', '1998-10-18 13:45:55')",
        datetime(1998, 10, 18, 13, 45, 55),
        types="DATETIME",
    ),
    q(
        "SELECT PARSE_DATETIME('%a %b %e %I:%M:%S %Y', 'Thu Dec 25 07:30:00 2008')",
        datetime(2008, 12, 25, 7, 30),
    ),
    q("SELECT PARSE_TIME('%H', '15')", time(15), types="TIME"),
    q("SELECT PARSE_TIME('%I:%M:%S %p', '2:23:38 pm')", time(14, 23, 38)),
    q(
        "SELECT PARSE_TIMESTAMP('%c', 'Thu Dec 25 07:30:00 2008')",
        utc(2008, 12, 25, 7, 30),
        types="TIMESTAMP",
    ),
    q(
        "SELECT PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S%Ez', '2020-01-01 00:00:00+05:30')",
        utc(2019, 12, 31, 18, 30),
    ),
    q(
        "SELECT PARSE_TIMESTAMP('%Y-%m-%d %H:%M', '2020-07-01 00:00', 'America/New_York')",
        utc(2020, 7, 1, 4),
    ),
    q("SELECT PARSE_DATE('%Y-%m-%d', '2019-02-29')", error="invalidQuery"),
    q("SELECT PARSE_DATE('%Y-%m-%d', 'not a date')", error="invalidQuery"),
    q(
        "SELECT SAFE.PARSE_DATE('%Y-%m-%d', '2019-02-29')",
        None,
    ),
    q("SELECT UNIX_DATE(DATE '2008-12-25')", 14238),
    q(
        "SELECT DATE_FROM_UNIX_DATE(14238)",
        date(2008, 12, 25),
        types="DATE",
    ),
    q(
        "SELECT UNIX_SECONDS(t), UNIX_MILLIS(t), UNIX_MICROS(t)"
        " FROM (SELECT TIMESTAMP '2008-12-25 15:30:00+00' AS t)",
        rows=[(1230219000, 1230219000000, 1230219000000000)],
    ),
    q(
        "SELECT UNIX_SECONDS(TIMESTAMP '1970-01-01 00:00:01.8+00')",
        1,
    ),
    q(
        "SELECT TIMESTAMP_SECONDS(1230219000), TIMESTAMP_MILLIS(1230219000000),"
        " TIMESTAMP_MICROS(1230219000000000)",
        rows=[(utc(2008, 12, 25, 15, 30),) * 3],
        types=("TIMESTAMP",) * 3,
    ),
    q(
        "SELECT GENERATE_DATE_ARRAY('2016-10-05', '2016-10-08')",
        [date(2016, 10, d) for d in range(5, 9)],
        types="ARRAY<DATE>",
    ),
    q(
        "SELECT GENERATE_DATE_ARRAY('2016-10-05', '2016-10-01', INTERVAL -1 DAY)",
        [date(2016, 10, d) for d in range(5, 0, -1)],
    ),
    q(
        "SELECT GENERATE_DATE_ARRAY('2016-01-01', '2016-12-31', INTERVAL 2 MONTH)",
        [date(2016, m, 1) for m in range(1, 12, 2)],
    ),
    q("SELECT GENERATE_DATE_ARRAY('2016-10-05', '2016-10-01')", []),
    q(
        "SELECT GENERATE_TIMESTAMP_ARRAY('2016-10-05 00:00:00',"
        " '2016-10-05 00:02:00', INTERVAL 1 MINUTE)",
        [utc(2016, 10, 5, 0, m) for m in range(3)],
        types="ARRAY<TIMESTAMP>",
    ),
    q(
        "SELECT CAST(INTERVAL 1 DAY AS STRING)",
        "0-0 1 0:0:0",
    ),
    q(
        "SELECT CAST(INTERVAL '1-2 3 4:5:6' YEAR TO SECOND AS STRING)",
        "1-2 3 4:5:6",
    ),
    q(
        "SELECT CAST(MAKE_INTERVAL(1, 2, 3) AS STRING)",
        "1-2 3 0:0:0",
    ),
    q(
        "SELECT CAST(DATE '2021-05-20' - DATE '2020-04-19' AS STRING)",
        "0-0 396 0:0:0",
    ),
    q(
        "SELECT CAST(JUSTIFY_HOURS(INTERVAL 29 HOUR) AS STRING),"
        " CAST(JUSTIFY_DAYS(INTERVAL 35 DAY) AS STRING),"
        " CAST(JUSTIFY_INTERVAL(INTERVAL '29 49:00:00' DAY TO SECOND) AS STRING)",
        rows=[("0-0 1 5:0:0", "0-1 5 0:0:0", "0-1 1 1:0:0")],
    ),
    q(
        "SELECT CAST(TIMESTAMP '2020-07-01 00:00:00+00' AS STRING)",
        "2020-07-01 00:00:00+00",
    ),
    q(
        "SELECT STRING(TIMESTAMP '2008-12-25 15:30:00+00', 'America/Los_Angeles')",
        "2008-12-25 07:30:00-08",
    ),
    q(
        "SELECT CAST(DATETIME '2020-01-01 12:00:00' AS STRING),"
        " CAST(DATE '2020-01-01' AS STRING)",
        rows=[("2020-01-01 12:00:00", "2020-01-01")],
    ),
    q(
        "SELECT CAST('2020-07-01 12:00:00' AS TIMESTAMP)",
        utc(2020, 7, 1, 12),
    ),
    q("SELECT CAST('2020-01-01 12:00:00-08' AS TIMESTAMP)", utc(2020, 1, 1, 20)),
    q(
        "SELECT CAST(DATETIME '2020-07-01 00:00:00' AS TIMESTAMP)",
        utc(2020, 7, 1),
        types="TIMESTAMP",
    ),
    q(
        "SELECT CAST(TIMESTAMP '2020-07-01 00:00:00+00' AS DATETIME)",
        datetime(2020, 7, 1),
        types="DATETIME",
    ),
    q("SELECT CAST(TIMESTAMP '2020-01-01 23:00:00+00' AS DATE)", date(2020, 1, 1)),
    q("SELECT CAST('2020-13-01' AS DATE)", error="invalidQuery"),
    q("SELECT SAFE_CAST('2020-13-01' AS DATE)", None),
    q(
        "SELECT DATETIME(TIMESTAMP '2020-01-01 12:00:00+00', 'America/New_York'),"
        " DATETIME(TIMESTAMP '2020-07-01 12:00:00+00', 'America/New_York')",
        rows=[(datetime(2020, 1, 1, 7), datetime(2020, 7, 1, 8))],
    ),
    q(
        "SELECT DATETIME(TIMESTAMP '2020-01-01 00:00:00+00', 'Pacific/Auckland')",
        datetime(2020, 1, 1, 13),
    ),
    q(
        "SELECT DATETIME(TIMESTAMP '2020-01-01 00:00:00+00', '+05:45')",
        datetime(2020, 1, 1, 5, 45),
    ),
    q(
        "SELECT DATETIME(TIMESTAMP '2020-01-01 00:00:00+00', 'Etc/UTC')",
        datetime(2020, 1, 1),
    ),
    q(
        "SELECT EXTRACT(HOUR FROM TIMESTAMP '2024-06-15 12:00:00+00' AT TIME ZONE '-04:30')",
        7,
    ),
    q(
        "SELECT EXTRACT(HOUR FROM TIMESTAMP '2024-06-15 00:00:00+00' AT TIME ZONE '+05:45')",
        5,
    ),
    q(
        "SELECT DATE(TIMESTAMP '2024-06-15 20:00:00+00', '+05:45')",
        date(2024, 6, 16),
    ),
    q(
        "SELECT DATETIME(TIMESTAMP '2024-06-15 00:00:00+00', '-04:30')",
        datetime(2024, 6, 14, 19, 30),
    ),
    q(
        "SELECT TIME(TIMESTAMP '2024-06-15 00:00:00+00', '+05:45')",
        time(5, 45),
    ),
    q(
        "SELECT FORMAT_TIMESTAMP('%H:%M', TIMESTAMP '2024-06-15 00:00:00+00', '-04:30')",
        "19:30",
    ),
    q(
        "SELECT TIMESTAMP_TRUNC(TIMESTAMP '2024-06-15 20:00:00+00', DAY, '+05:45')",
        utc(2024, 6, 15, 18, 15),
    ),
    q(
        "SELECT TIME(TIMESTAMP '2024-01-15 12:30:45 UTC')",
        time(12, 30, 45),
        types="TIME",
    ),
    q("SELECT FORMAT_DATE('%Y-%m-%d', CAST(NULL AS DATE))", None, types="STRING"),
    q(
        "SELECT FORMAT_DATE('%Y-%m-%d', DATE '0001-01-01')",
        "1-01-01",
    ),
    q(
        "SELECT PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S %Z', '2024-01-15 12:00:00 UTC')",
        utc(2024, 1, 15, 12),
        types="TIMESTAMP",
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_datetime(check, case):
    check(case)
