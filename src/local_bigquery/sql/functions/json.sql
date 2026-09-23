CREATE MACRO _json_number(j) AS json_type(j) IN ('BIGINT', 'UBIGINT', 'DOUBLE');

CREATE MACRO int64(j) AS CASE
    WHEN j IS NULL OR json_type(j) = 'NULL' THEN NULL
    WHEN json_type(j) IN ('BIGINT', 'UBIGINT') THEN j::BIGINT
    WHEN json_type(j) = 'DOUBLE' AND j::DOUBLE = trunc(j::DOUBLE) THEN j::DOUBLE::BIGINT
    ELSE error('The provided JSON input is not an integer')
END;

CREATE MACRO float64(j) AS CASE
    WHEN j IS NULL OR json_type(j) = 'NULL' THEN NULL
    WHEN bq.main._json_number(j) THEN j::DOUBLE
    ELSE error('The provided JSON input is not a number')
END;

CREATE MACRO bool(j) AS CASE
    WHEN j IS NULL OR json_type(j) = 'NULL' THEN NULL
    WHEN json_type(j) = 'BOOLEAN' THEN j::BOOLEAN
    ELSE error('The provided JSON input is not a boolean')
END;

CREATE MACRO string(x) AS CASE
    WHEN typeof(x) <> 'JSON' THEN CAST(x AS VARCHAR)
    WHEN json_type(x::JSON) = 'VARCHAR' THEN json_extract_string(x::JSON, '$')
    WHEN json_type(x::JSON) = 'NULL' THEN NULL
    ELSE error('The provided JSON input is not a string')
END;

CREATE MACRO lax_int64(j) AS CASE
    WHEN json_type(j) = 'BOOLEAN' THEN j::BOOLEAN::BIGINT
    WHEN bq.main._json_number(j) THEN TRY_CAST(round(j::DOUBLE) AS BIGINT)
    WHEN json_type(j) = 'VARCHAR'
        THEN TRY_CAST(round(TRY_CAST(json_extract_string(j, '$') AS DOUBLE)) AS BIGINT)
END;

CREATE MACRO lax_float64(j) AS CASE
    WHEN bq.main._json_number(j) THEN j::DOUBLE
    WHEN json_type(j) = 'VARCHAR' THEN TRY_CAST(json_extract_string(j, '$') AS DOUBLE)
END;

CREATE MACRO lax_bool(j) AS CASE
    WHEN json_type(j) = 'BOOLEAN' THEN j::BOOLEAN
    WHEN bq.main._json_number(j) THEN j::DOUBLE <> 0
    WHEN json_type(j) = 'VARCHAR' THEN CASE lower(json_extract_string(j, '$'))
        WHEN 'true' THEN TRUE WHEN 'false' THEN FALSE END
END;

CREATE MACRO lax_string(j) AS CASE
    WHEN json_type(j) = 'VARCHAR' THEN json_extract_string(j, '$')
    WHEN bq.main._json_number(j) OR json_type(j) = 'BOOLEAN' THEN j::VARCHAR
END;

CREATE MACRO json_type(j) AS CASE json_type(j)
    WHEN 'BIGINT' THEN 'number'
    WHEN 'UBIGINT' THEN 'number'
    WHEN 'DOUBLE' THEN 'number'
    WHEN 'VARCHAR' THEN 'string'
    ELSE lower(json_type(j))
END;

CREATE MACRO _json_keys(j, depth) AS (
    SELECT list_sort(list_distinct(list(k)))
    FROM (SELECT regexp_replace(fullkey, '^\$\.', '') AS k FROM json_tree(j) WHERE fullkey <> '$' AND NOT contains(fullkey, '['))
    WHERE len(string_split(k, '.')) <= depth
);

CREATE MACRO json_keys(j) AS bq.main._json_keys(j, 2147483647),
    (j, depth) AS bq.main._json_keys(j, depth);

CREATE MACRO to_json(x) AS coalesce(to_json(x), 'null'::JSON);

CREATE MACRO _json_pretty(j) AS array_to_string(list_transform(
    string_split(json_pretty(j), chr(10)),
    lambda line: repeat(' ', (length(line) - length(ltrim(line))) // 2) || ltrim(line)
), chr(10));

CREATE MACRO to_json_string(x) AS coalesce(to_json(x)::VARCHAR, 'null'),
    (x, pretty) AS CASE
        WHEN pretty THEN coalesce(bq.main._json_pretty(to_json(x)), 'null')
        ELSE coalesce(to_json(x)::VARCHAR, 'null')
    END;

CREATE MACRO _json_patch(path, value) AS json(
    array_to_string(list_transform(
        string_split(substr(path, 3), '.'),
        lambda k: '{' || to_json(k)::VARCHAR || ':'
    ), '')
    || value::VARCHAR
    || repeat('}', len(string_split(substr(path, 3), '.')))
);

CREATE MACRO _json_put(j, path, value) AS CASE
    WHEN path = '$' THEN value::JSON
    ELSE json_merge_patch(j, bq.main._json_patch(path, value))
END;

CREATE MACRO json_set(j, path, value) AS bq.main._json_put(j, path, to_json(value));

CREATE MACRO json_remove(j, path) AS bq.main._json_put(j, path, 'null'::JSON);

CREATE MACRO json_strip_nulls(j) AS CASE
    WHEN json_type(j) = 'OBJECT' THEN json_merge_patch('{}'::JSON, j)
    ELSE j
END;

CREATE MACRO json_array_append(j, path, value) AS bq.main._json_put(
    j,
    path,
    to_json(list_append(CAST(json_extract(j, path) AS JSON[]), to_json(value)))
);

CREATE MACRO json_array_insert(j, path, value) AS bq.main._json_put(
    j,
    regexp_replace(path, '\[\d+\]$', ''),
    to_json(list_concat(
        CAST(json_extract(j, regexp_replace(path, '\[\d+\]$', '')) AS JSON[])[
            1:regexp_extract(path, '\[(\d+)\]$', 1)::INTEGER
        ],
        [to_json(value)],
        CAST(json_extract(j, regexp_replace(path, '\[\d+\]$', '')) AS JSON[])[
            regexp_extract(path, '\[(\d+)\]$', 1)::INTEGER + 1:
        ]
    ))
);

CREATE MACRO parse_json(s) AS CASE
    WHEN EXISTS (
        SELECT 1 FROM json_tree(json(s))
        WHERE type = 'DOUBLE' AND regexp_matches(value::VARCHAR, '^-?[0-9]+$')
    ) THEN error('Invalid input to PARSE_JSON: number cannot be stored without loss of precision')
    ELSE json(s)
END;
