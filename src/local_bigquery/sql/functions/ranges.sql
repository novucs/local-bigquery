CREATE MACRO range(s, e) AS CASE
    WHEN s >= e THEN error('Range start element must be less than the end element')
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
        THEN error('Provided RANGE inputs: ' || a || ' and ' || b || ' do not overlap.')
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
