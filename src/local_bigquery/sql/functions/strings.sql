CREATE MACRO to_code_points(s) AS
    CASE WHEN s = '' THEN [] ELSE list_transform(string_split(s, ''), c -> unicode(c)) END;
