CREATE MACRO array_includes(a, v) AS CASE WHEN v IS NULL THEN NULL ELSE list_contains(a, v) END;

CREATE MACRO array_first(a) AS
    CASE WHEN len(a) = 0 THEN _raise('ARRAY_FIRST cannot get the first element of an empty array') ELSE a[1] END;

CREATE MACRO array_last(a) AS
    CASE WHEN len(a) = 0 THEN _raise('ARRAY_LAST cannot get the last element of an empty array') ELSE a[-1] END;

CREATE MACRO array_slice(a, first, last) AS
    list_slice(a, CASE WHEN first < 0 THEN first ELSE first + 1 END, CASE WHEN last < 0 THEN last ELSE last + 1 END);

CREATE MACRO generate_array(first, last) AS list_transform(range(0, last - first + 1), i -> first + i),
    (first, last, step) AS CASE
        WHEN step = 0 THEN _raise('Sequence step cannot be 0.')
        ELSE list_transform(range(0, CAST(floor((last - first) / step) AS BIGINT) + 1), i -> first + i * step)
    END;

CREATE MACRO _array_at(a, i, base) AS CASE
    WHEN a IS NULL OR i IS NULL THEN NULL
    WHEN i - base < 0 THEN _raise('Array index ' || i || ' is out of bounds (underflow)')
    WHEN i - base >= len(a) THEN _raise('Array index ' || i || ' is out of bounds (overflow)')
    ELSE a[i - base + 1]
END;

CREATE MACRO array_includes_any(a, b) AS
    CASE WHEN a IS NOT NULL AND b IS NOT NULL THEN list_has_any(a, b) END;

CREATE MACRO array_includes_all(a, b) AS
    CASE WHEN a IS NOT NULL AND b IS NOT NULL THEN list_has_all(a, b) END;

CREATE MACRO array_is_distinct(a) AS len(list_distinct(list_transform(a, e -> [e]))) = len(a);

CREATE MACRO array_avg(a) AS list_avg(a);

CREATE MACRO dot_product(a, b) AS list_dot_product(CAST(a AS DOUBLE[]), CAST(b AS DOUBLE[]));

CREATE MACRO _array_offsets(matches) AS
    list_filter(range(len(matches)), i -> coalesce(matches[i + 1], false));

CREATE MACRO _array_pick(offsets, mode) AS offsets[CASE upper(mode) WHEN 'LAST' THEN -1 ELSE 1 END];

CREATE MACRO array_offsets(a, matches) AS bq.main._array_offsets(matches);

CREATE MACRO array_offset(a, matches) AS bq.main._array_offsets(matches)[1],
    (a, matches, mode) AS bq.main._array_pick(bq.main._array_offsets(matches), mode);

CREATE MACRO array_find(a, matches) AS a[bq.main._array_offsets(matches)[1] + 1],
    (a, matches, mode) AS a[bq.main._array_pick(bq.main._array_offsets(matches), mode) + 1];

CREATE MACRO array_find_all(a, matches) AS
    list_transform(bq.main._array_offsets(matches), i -> a[i + 1]);
