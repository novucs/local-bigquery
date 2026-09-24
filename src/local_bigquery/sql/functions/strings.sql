CREATE MACRO to_code_points(s) AS
    CASE WHEN s = '' THEN [] ELSE list_transform(string_split(s, ''), lambda c: unicode(c)) END;

CREATE MACRO code_points_to_string(points) AS
    array_to_string(list_transform(points, lambda c: chr(c::INTEGER)), '');

CREATE MACRO byte_length(x) AS
    octet_length(CASE WHEN typeof(x) = 'BLOB' THEN x::BLOB ELSE encode(x::VARCHAR) END);

CREATE MACRO safe_convert_bytes_to_string(b) AS TRY(decode(b));

CREATE MACRO _positions(s, t) AS
    list_filter(range(1, length(s) - length(t) + 2), lambda i: substr(s, i, length(t)) = t);

CREATE MACRO _instr(s, t, p, n) AS coalesce(
    CASE
        WHEN p > 0 THEN list_filter(bq.main._positions(s, t), lambda i: i >= p)[n]
        ELSE list_reverse(
            list_filter(bq.main._positions(s, t), lambda i: i <= length(s) + p + 1)
        )[n]
    END,
    0
);

CREATE MACRO instr(s, t) AS bq.main._instr(s, t, 1, 1),
    (s, t, p) AS bq.main._instr(s, t, p, 1),
    (s, t, p, n) AS bq.main._instr(s, t, p, n);

CREATE MACRO _soundex_code(letters, skip) AS
    translate(letters, 'AEIOUYHWBFPVCGJKQSXZDTLMNR', '000000' || skip || skip || '111122222222334556');

CREATE MACRO _soundex(letters, digits) AS
    CASE WHEN letters = '' THEN '' ELSE left(letters, 1) || rpad(left(array_to_string(
        list_filter(
            list_filter(digits, lambda c, i: i = 1 OR c <> digits[i - 1])[2:],
            lambda c: c <> '0'
        ),
        ''
    ), 3), 3, '0') END;

CREATE MACRO soundex(s) AS bq.main._soundex(
    regexp_replace(upper(s), '[^A-Z]', '', 'g'),
    string_split(
        bq.main._soundex_code(left(regexp_replace(upper(s), '[^A-Z]', '', 'g'), 1), '0')
        || replace(bq.main._soundex_code(substr(regexp_replace(upper(s), '[^A-Z]', '', 'g'), 2), '-'), '-', ''),
        ''
    )
);

CREATE MACRO _bytes(x) AS CASE WHEN typeof(x) = 'BLOB' THEN x::BLOB ELSE encode(x::VARCHAR) END;

CREATE MACRO farm_fingerprint(x) AS _farm_fingerprint(bq.main._bytes(x));

CREATE MACRO sha512(x) AS _sha512(bq.main._bytes(x));

CREATE MACRO to_base32(b) AS _to_base32(b);

CREATE MACRO from_base32(s) AS _from_base32(s);

CREATE MACRO code_points_to_bytes(points) AS
    unhex(array_to_string(list_transform(points, p -> lpad(to_hex(p), 2, '0')), ''));

CREATE MACRO _search_tokens(s) AS list_filter(
    regexp_split_to_array(lower(s), '[\s\[\]<>(){}|!;,''"`*&?+/:=@.\-$%\\_]+'), t -> t <> ''
);

CREATE MACRO _search_text(s) AS ' ' || array_to_string(bq.main._search_tokens(s), ' ') || ' ';

CREATE MACRO _search_leaf(text, query) AS list_has_all(
    bq.main._search_tokens(text),
    bq.main._search_tokens(regexp_replace(query, '`[^`]*`', ' ', 'g'))
) AND coalesce(list_bool_and(list_transform(
    regexp_extract_all(query, '`([^`]*)`', 1),
    phrase -> contains(bq.main._search_text(text), bq.main._search_text(phrase))
)), true);

CREATE MACRO search(data, query) AS coalesce((
    SELECT bool_or(bq.main._search_leaf(json_extract_string(value, '$'), query))
    FROM json_tree(to_json(data))
    WHERE type = 'VARCHAR'
), false);
