import pytest

from tests.cases import q

ZEROS = b"\x00" * 16
URLS = [
    ("''", None, None, None),
    ("'http://abc.xyz'", "abc.xyz", "abc.xyz", "xyz"),
    ("'//user:password@a.b:80/path?query'", "a.b", None, None),
    ("'https://[::1]:80'", "[::1]", None, None),
    ("'    www.Example.Co.UK    '", "www.Example.Co.UK", "Example.Co.UK", "Co.UK"),
    ("'mailto:?to=&subject=&body='", "mailto", None, None),
]

CASES = [
    *(
        q(
            f"SELECT NET.HOST({url}), NET.REG_DOMAIN({url}), NET.PUBLIC_SUFFIX({url})",
            rows=[tuple(expected)],
        )
        for url, *expected in URLS
    ),
    q(
        "SELECT NET.PUBLIC_SUFFIX('www.example.k12.ca.us')",
        "k12.ca.us",
        xfail="public suffixes approximate the PSL with common suffixes",
    ),
    q(
        "SELECT NET.IP_FROM_STRING('48.49.50.51'), NET.IP_FROM_STRING('::1'), "
        "NET.IP_FROM_STRING('3031:3233:3435:3637:3839:4041:4243:4445')",
        rows=[(b"0123", ZEROS[:15] + b"\x01", b"0123456789@ABCDE")],
        types=("BYTES", "BYTES", "BYTES"),
    ),
    q("SELECT NET.IP_FROM_STRING('1.2.3')", error="1.2.3"),
    q(
        "SELECT NET.SAFE_IP_FROM_STRING('1.2.3'), NET.SAFE_IP_FROM_STRING('1.2.3.4')",
        rows=[(None, b"\x01\x02\x03\x04")],
    ),
    q(
        "SELECT NET.IP_TO_STRING(b'0123'), NET.IP_TO_STRING(b'0123456789@ABCDE'), "
        "NET.IP_TO_STRING(NET.IP_FROM_STRING('::1'))",
        rows=[("48.49.50.51", "3031:3233:3435:3637:3839:4041:4243:4445", "::1")],
    ),
    q(
        "SELECT NET.IPV4_FROM_INT64(0), NET.IPV4_FROM_INT64(1), "
        "NET.IPV4_FROM_INT64(-1), NET.IPV4_FROM_INT64(0xFFFFFFFF)",
        rows=[(ZEROS[:4], b"\x00\x00\x00\x01", b"\xff" * 4, b"\xff" * 4)],
    ),
    q(
        "SELECT NET.IPV4_TO_INT64(b'\\x00\\x00\\x00\\x01'), "
        "NET.IPV4_TO_INT64(b'\\xff\\xff\\xff\\xff')",
        rows=[(1, 4294967295)],
    ),
    q(
        "SELECT NET.IP_NET_MASK(4, 0), NET.IP_NET_MASK(4, 20), NET.IP_NET_MASK(16, 1), "
        "NET.IP_NET_MASK(16, 128)",
        rows=[(ZEROS[:4], b"\xff\xff\xf0\x00", b"\x80" + ZEROS[:15], b"\xff" * 16)],
    ),
    q(
        "SELECT NET.IP_TRUNC(b'\\xaa\\xbb\\xcc\\xdd', 0), "
        "NET.IP_TRUNC(b'\\xaa\\xbb\\xcc\\xdd', 11), "
        "NET.IP_TRUNC(b'\\xaa\\xbb\\xcc\\xdd', 24)",
        rows=[(ZEROS[:4], b"\xaa\xa0\x00\x00", b"\xaa\xbb\xcc\x00")],
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_net(check, case):
    check(case)
