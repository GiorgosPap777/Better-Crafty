"""A small NBT writer for tests."""

import gzip
import struct


# dict -> compound, str -> string, int -> int, float -> double,
# list -> list; other tags through the helpers below.
def _string(text):
    data = text.encode("utf-8")
    return struct.pack(">H", len(data)) + data


def byte(value):
    return (1, struct.pack(">b", value))


def short(value):
    return (2, struct.pack(">h", value))


def long(value):
    return (4, struct.pack(">q", value))


def flt(value):
    return (5, struct.pack(">f", value))


def int_array(values):
    return (11, struct.pack(f">i{len(values)}i", len(values), *values))


def encode(value):
    if isinstance(value, tuple):
        return value
    if isinstance(value, str):
        return (8, _string(value))
    if isinstance(value, int):
        return (3, struct.pack(">i", value))
    if isinstance(value, float):
        return (6, struct.pack(">d", value))
    if isinstance(value, dict):
        body = b""
        for key, child in value.items():
            tag, data = encode(child)
            body += bytes([tag]) + _string(key) + data
        return (10, body + b"\x00")
    if isinstance(value, list):
        items = [encode(child) for child in value]
        tag = items[0][0] if items else 0
        return (
            9,
            bytes([tag])
            + struct.pack(">i", len(items))
            + b"".join(d for _, d in items),
        )
    raise TypeError(value)


def nbt_file(root, compress=True):
    data = b"\x0a" + _string("") + encode(root)[1]
    return gzip.compress(data) if compress else data
