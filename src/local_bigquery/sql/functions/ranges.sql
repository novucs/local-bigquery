CREATE MACRO range(s, e) AS CASE
    WHEN s >= e THEN _raise('Range start element must be less than the end element')
    ELSE {'__range_start': s, '__range_end': e}
END;

CREATE MACRO range_start(r) AS r.__range_start;

CREATE MACRO range_end(r) AS r.__range_end;

CREATE MACRO range_contains(r, x) AS
    (r.__range_start IS NULL OR r.__range_start <= x)
    AND (r.__range_end IS NULL OR x < r.__range_end);

CREATE MACRO _range_contains_range(r, x) AS
    (r.__range_start IS NULL OR (x.__range_start IS NOT NULL AND r.__range_start <= x.__range_start))
    AND (r.__range_end IS NULL OR (x.__range_end IS NOT NULL AND x.__range_end <= r.__range_end));

CREATE MACRO range_overlaps(a, b) AS
    (a.__range_end IS NULL OR b.__range_start IS NULL OR b.__range_start < a.__range_end)
    AND (b.__range_end IS NULL OR a.__range_start IS NULL OR a.__range_start < b.__range_end);

CREATE MACRO range_intersect(a, b) AS CASE
    WHEN NOT bq.main.range_overlaps(a, b)
        THEN _raise('Provided RANGE inputs: ' || a || ' and ' || b || ' do not overlap.')
    ELSE {
        '__range_start': CASE
            WHEN a.__range_start IS NULL THEN b.__range_start
            WHEN b.__range_start IS NULL THEN a.__range_start
            ELSE greatest(a.__range_start, b.__range_start) END,
        '__range_end': CASE
            WHEN a.__range_end IS NULL THEN b.__range_end
            WHEN b.__range_end IS NULL THEN a.__range_end
            ELSE least(a.__range_end, b.__range_end) END
    }
END;

CREATE MACRO _range_array(r, step, last) AS list_transform(
    list_filter(
        generate_series(r.__range_start, r.__range_end, step),
        s -> s < r.__range_end AND (last OR s + step <= r.__range_end)
    ),
    s -> {
        '__range_start': cast_to_type(s, r.__range_start),
        '__range_end': cast_to_type(least(s + step, r.__range_end), r.__range_start)
    }
);

CREATE MACRO generate_range_array(r, step) AS bq.main._range_array(r, step, true),
(r, step, last) AS bq.main._range_array(r, step, last);
