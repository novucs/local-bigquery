import pytest

from tests.cases import q

CASES = [
    q("SELECT CONCAT('a', 'b', 'c')", "abc", types="STRING"),
    q("SELECT CONCAT('a', NULL)", None),
    q("SELECT 'a' || 'b'", "ab"),
    q("SELECT CONCAT(b'a', b'b')", b"ab", types="BYTES"),
    q("SELECT LENGTH('héllo')", 5, types="INT64"),
    q("SELECT CHAR_LENGTH('héllo')", 5),
    q("SELECT BYTE_LENGTH('héllo')", 6),
    q("SELECT LENGTH(b'abc')", 3),
    q("SELECT LOWER('AbC'), UPPER('AbC')", rows=[("abc", "ABC")]),
    q("SELECT LOWER(NULL)", None),
    q("SELECT INITCAP('hello world-foo')", "Hello World-Foo"),
    q("SELECT LPAD('abc', 5, '*')", "**abc"),
    q("SELECT LPAD('abc', 2)", "ab"),
    q("SELECT RPAD('abc', 5)", "abc  "),
    q(
        "SELECT LTRIM('  a  '), RTRIM('  a  '), TRIM('  a  ')",
        rows=[("a  ", "  a", "a")],
    ),
    q("SELECT TRIM('xxaxx', 'x')", "a"),
    q("SELECT REPEAT('ab', 3)", "ababab"),
    q("SELECT REPLACE('abcabc', 'b', 'X')", "aXcaXc"),
    q("SELECT REVERSE('abc')", "cba"),
    q("SELECT TRANSLATE('abc', 'ab', 'xy')", "xyc"),
    q("SELECT SUBSTR('abcdef', 2, 3)", "bcd"),
    q("SELECT SUBSTR('abcdef', -2)", "ef"),
    q("SELECT SUBSTR('abc', 0)", "abc"),
    q("SELECT SUBSTR('abc', 2, 100)", "bc"),
    q("SELECT LEFT('abc', 2), RIGHT('abc', 2)", rows=[("ab", "bc")]),
    q("SELECT STRPOS('abcabc', 'c')", 3),
    q(
        "SELECT INSTR('abcabc', 'c', 1, 2)",
        6,
    ),
    q(
        "SELECT INSTR('abcabc', 'c', -1)",
        6,
    ),
    q("SELECT STARTS_WITH('abc', 'ab'), ENDS_WITH('abc', 'bc')", rows=[(True, True)]),
    q("SELECT CONTAINS_SUBSTR('the Blue house', 'blue')", True),
    q("SELECT SPLIT('a,b,,c', ',')", ["a", "b", "", "c"], types="ARRAY<STRING>"),
    q("SELECT SPLIT('abc', '')", ["a", "b", "c"]),
    q("SELECT SPLIT('', ',')", [""]),
    q(r"SELECT REGEXP_CONTAINS('foo@example.com', r'@\w+\.com$')", True),
    q(r"SELECT REGEXP_EXTRACT('abc123', r'\d+')", "123"),
    q(r"SELECT REGEXP_EXTRACT('abc123', r'([a-z]+)\d')", "abc"),
    q(
        "SELECT REGEXP_EXTRACT('abc', r'z')",
        None,
    ),
    q(r"SELECT REGEXP_EXTRACT_ALL('a1b22c333', r'\d+')", ["1", "22", "333"]),
    q(r"SELECT REGEXP_REPLACE('abc123', r'\d', 'X')", "abcXXX"),
    q(r"SELECT REGEXP_REPLACE('ab', r'(a)(b)', r'\2\1')", "ba"),
    q(
        "SELECT FORMAT('%d-%s', 1, 'a')",
        "1-a",
    ),
    q(
        "SELECT FORMAT('%05.2f', 3.14159)",
        "03.14",
    ),
    q(
        "SELECT FORMAT('%t', [1, 2])",
        "[1, 2]",
    ),
    q("SELECT ASCII('A'), CHR(65), UNICODE('â')", rows=[(65, "A", 226)]),
    q("SELECT TO_CODE_POINTS('ab')", [97, 98]),
    q("SELECT CODE_POINTS_TO_STRING([97, 98])", "ab"),
    q("SELECT TO_HEX(b'abc'), FROM_HEX('616263')", rows=[("616263", b"abc")]),
    q("SELECT TO_BASE64(b'abc'), FROM_BASE64('YWJj')", rows=[("YWJj", b"abc")]),
    q("SELECT SAFE_CONVERT_BYTES_TO_STRING(b'abc')", "abc"),
    q(
        r"SELECT NORMALIZE('\u00e9') = NORMALIZE('e\u0301')",
        True,
    ),
    q("SELECT SOUNDEX('Ashcraft')", "A261"),
    q("SELECT EDIT_DISTANCE('abc', 'abd')", 1),
    q("SELECT 'a' < 'B'", False),
    q(
        "SELECT COLLATE('A', 'und:ci') = 'a'",
        True,
    ),
    q("SELECT 'abc' LIKE 'a%', 'abc' LIKE 'A%'", rows=[(True, False)]),
    q(
        r"SELECT 'a_c' LIKE r'a\_c', 'abc' LIKE r'a\_c'",
        rows=[(True, False)],
    ),
    q("SELECT 'abc' LIKE ANY ('x%', 'a%')", True),
    q("SELECT CAST(123 AS STRING), CAST(TRUE AS STRING)", rows=[("123", "true")]),
    q(
        "SELECT CAST(1.5 AS STRING), CAST(1.0 AS STRING)",
        rows=[("1.5", "1")],
    ),
    q(
        "SELECT FARM_FINGERPRINT('hello')",
        -5436999610281751320,
        types="INT64",
    ),
    q(
        "SELECT FARM_FINGERPRINT(CONCAT('seed-', '42'))",
        -1445242963413924359,
    ),
    q(
        "SELECT TO_BASE32(b'hello'), TO_BASE32(b'')",
        rows=[("NBSWY3DP", "")],
    ),
    q(
        "SELECT FROM_BASE32('JBSWY3DPEB3W64TMMQ======')",
        b"Hello world",
        types="BYTES",
    ),
    q(
        "SELECT CODE_POINTS_TO_BYTES([65, 66, 67])",
        b"ABC",
        types="BYTES",
    ),
    q(
        "SELECT CODE_POINTS_TO_BYTES(ARRAY<INT64>[])",
        b"",
    ),
    q(
        r"SELECT LENGTH(NORMALIZE('\u00e9', NFD)), LENGTH(NORMALIZE('e\u0301', NFC))",
        rows=[(2, 1)],
    ),
    q("SELECT NORMALIZE('\uff21', NFKC)", "A"),
    q(
        "SELECT NORMALIZE_AND_CASEFOLD('Straße', NFC)",
        "strasse",
    ),
    q(
        "SELECT TO_HEX(SHA512('hello'))",
        "9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca7"
        "2323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043",
    ),
    q("SELECT UPPER('groß')", "GROSS"),
    q(
        "SELECT COLLATE('Apple', 'binary') = COLLATE('apple', 'binary')",
        error="Collation 'binary' in collate function is not supported",
    ),
    q(
        "SELECT CONCAT(CAST(NULL AS STRING), 'x')",
        None,
        types="STRING",
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_strings(check, case):
    check(case)
