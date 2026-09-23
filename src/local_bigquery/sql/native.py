import base64
import hashlib
import json
import unicodedata

import duckdb

MASK = (1 << 64) - 1
K0, K1, K2 = 0xC3A5C85C97CB3127, 0xB492B66FBE98F273, 0x9AE16A3B2F90404F


def _fetch64(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 8], "little")


def _fetch32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def _rotate(value: int, shift: int) -> int:
    return value if shift == 0 else ((value >> shift) | (value << (64 - shift))) & MASK


def _shift_mix(value: int) -> int:
    return value ^ (value >> 47)


def _hash16(u: int, v: int, mul: int) -> int:
    a = _shift_mix(((u ^ v) * mul) & MASK)
    b = _shift_mix(((v ^ a) * mul) & MASK)
    return (b * mul) & MASK


def _weak32(data: bytes, offset: int, a: int, b: int) -> tuple[int, int]:
    w, x, y, z = (_fetch64(data, offset + 8 * i) for i in range(4))
    a = (a + w) & MASK
    b = _rotate((b + a + z) & MASK, 21)
    c = a
    a = (a + x + y) & MASK
    b = (b + _rotate(a, 44)) & MASK
    return (a + z) & MASK, (b + c) & MASK


def _short(data: bytes) -> int:
    length = len(data)
    mul = (K2 + length * 2) & MASK
    if length >= 8:
        a = (_fetch64(data, 0) + K2) & MASK
        b = _fetch64(data, length - 8)
        c = (_rotate(b, 37) * mul + a) & MASK
        d = ((_rotate(a, 25) + b) * mul) & MASK
        return _hash16(c, d, mul)
    if length >= 4:
        a = _fetch32(data, 0)
        return _hash16((length + (a << 3)) & MASK, _fetch32(data, length - 4), mul)
    if length:
        y = data[0] + (data[length >> 1] << 8)
        z = length + (data[length - 1] << 2)
        return (_shift_mix(((y * K2) ^ (z * K0)) & MASK) * K2) & MASK
    return K2


def _medium(data: bytes) -> int:
    length = len(data)
    mul = (K2 + length * 2) & MASK
    a = (_fetch64(data, 0) * K1) & MASK
    b = _fetch64(data, 8)
    c = (_fetch64(data, length - 8) * mul) & MASK
    d = (_fetch64(data, length - 16) * K2) & MASK
    return _hash16(
        (_rotate((a + b) & MASK, 43) + _rotate(c, 30) + d) & MASK,
        (a + _rotate((b + K2) & MASK, 18) + c) & MASK,
        mul,
    )


def _long(data: bytes) -> int:
    length = len(data)
    mul = (K2 + length * 2) & MASK
    a = (_fetch64(data, 0) * K2) & MASK
    b = _fetch64(data, 8)
    c = (_fetch64(data, length - 8) * mul) & MASK
    d = (_fetch64(data, length - 16) * K2) & MASK
    y = (_rotate((a + b) & MASK, 43) + _rotate(c, 30) + d) & MASK
    z = _hash16(y, (a + _rotate((b + K2) & MASK, 18) + c) & MASK, mul)
    e = (_fetch64(data, 16) * mul) & MASK
    f = _fetch64(data, 24)
    g = ((y + _fetch64(data, length - 32)) * mul) & MASK
    h = ((z + _fetch64(data, length - 24)) * mul) & MASK
    return _hash16(
        (_rotate((e + f) & MASK, 43) + _rotate(g, 30) + h) & MASK,
        (e + _rotate((f + a) & MASK, 18) + g) & MASK,
        mul,
    )


def _fingerprint(data: bytes) -> int:
    length = len(data)
    if length <= 16:
        return _short(data)
    if length <= 32:
        return _medium(data)
    if length <= 64:
        return _long(data)
    x, y = 81, (81 * K1 + 113) & MASK
    z = (_shift_mix((y * K2 + 113) & MASK) * K2) & MASK
    v, w = (0, 0), (0, 0)
    x = (x * K2 + _fetch64(data, 0)) & MASK
    end = ((length - 1) // 64) * 64
    last = end + ((length - 1) & 63) - 63
    offset = 0
    while offset != end:
        x = (
            _rotate((x + y + v[0] + _fetch64(data, offset + 8)) & MASK, 37) * K1
        ) & MASK
        y = (_rotate((y + v[1] + _fetch64(data, offset + 48)) & MASK, 42) * K1) & MASK
        x ^= w[1]
        y = (y + v[0] + _fetch64(data, offset + 40)) & MASK
        z = (_rotate((z + w[0]) & MASK, 33) * K1) & MASK
        v = _weak32(data, offset, (v[1] * K1) & MASK, (x + w[0]) & MASK)
        w = _weak32(
            data,
            offset + 32,
            (z + w[1]) & MASK,
            (y + _fetch64(data, offset + 16)) & MASK,
        )
        z, x = x, z
        offset += 64
    mul = (K1 + ((z & 0xFF) << 1)) & MASK
    w = ((w[0] + ((length - 1) & 63)) & MASK, w[1])
    v = ((v[0] + w[0]) & MASK, v[1])
    w = ((w[0] + v[0]) & MASK, w[1])
    x = (_rotate((x + y + v[0] + _fetch64(data, last + 8)) & MASK, 37) * mul) & MASK
    y = (_rotate((y + v[1] + _fetch64(data, last + 48)) & MASK, 42) * mul) & MASK
    x ^= (w[1] * 9) & MASK
    y = (y + v[0] * 9 + _fetch64(data, last + 40)) & MASK
    z = (_rotate((z + w[0]) & MASK, 33) * mul) & MASK
    v = _weak32(data, last, (v[1] * mul) & MASK, (x + w[0]) & MASK)
    w = _weak32(
        data, last + 32, (z + w[1]) & MASK, (y + _fetch64(data, last + 16)) & MASK
    )
    z, x = x, z
    return _hash16(
        (_hash16(v[0], w[0], mul) + _shift_mix(y) * K0 + z) & MASK,
        (_hash16(v[1], w[1], mul) + x) & MASK,
        mul,
    )


def farm_fingerprint(data: bytes) -> int:
    value = _fingerprint(bytes(data))
    return value - (1 << 64) if value >= 1 << 63 else value


def from_base32(text: str) -> bytes:
    return base64.b32decode(text + "=" * (-len(text) % 8))


def normalize(text: str, form: str, casefold: bool) -> str:
    return unicodedata.normalize(form.upper(), text.casefold() if casefold else text)


def _integer(text: str) -> int:
    value = int(text)
    if not -(1 << 63) <= value < 1 << 64:
        raise OverflowError
    return value


def json_exact(text: str) -> bool:
    try:
        json.loads(text, parse_int=_integer)
    except OverflowError:
        return False
    except ValueError:
        return True
    return True


FUNCTIONS = {
    "_json_exact": (json_exact, ["VARCHAR"], "BOOLEAN"),
    "_farm_fingerprint": (farm_fingerprint, ["BLOB"], "BIGINT"),
    "_sha512": (lambda data: hashlib.sha512(data).digest(), ["BLOB"], "BLOB"),
    "_to_base32": (lambda data: base64.b32encode(data).decode(), ["BLOB"], "VARCHAR"),
    "_from_base32": (from_base32, ["VARCHAR"], "BLOB"),
    "_normalize": (normalize, ["VARCHAR", "VARCHAR", "BOOLEAN"], "VARCHAR"),
}


def register(con: duckdb.DuckDBPyConnection):
    for name, (function, parameters, returns) in FUNCTIONS.items():
        con.create_function(name, function, parameters, returns)
