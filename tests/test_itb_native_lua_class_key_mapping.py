"""Strict byte encodings preserve canonical class key order and default fixtures."""

import copy
import pytest
from src.observatory import native_lua_class_tree_conformance as c


@pytest.fixture
def fixture():
    vector = next(
        v
        for v in c.vectors()
        if v["source_keys"] and len(set(v["source_keys"] + v["destination_keys"])) >= 3
    )
    return c._fixture(vector)


def test_default_encoding_and_explicit_equivalence():
    for vector in c.vectors()[::12]:
        fixture = c._fixture(vector)
        before = copy.deepcopy(fixture)
        mapping = c._checked_key_bytes(fixture)
        assert mapping == {
            k: f"{k:08x}".encode()
            for k in set(vector["source_keys"] + vector["destination_keys"])
        }
        assert c._expected(vector, fixture) == c._expected(
            vector, dict(fixture, key_bytes=mapping)
        )
        assert fixture == before


@pytest.mark.parametrize("profile", ["prefix", "unsigned", "long"])
def test_accepts_distinct_ordered_bytes_and_returns_copy(fixture, profile):
    keys = sorted(c._checked_key_bytes(fixture))
    values = {
        "prefix": [b"A" * i for i in range(len(keys))],
        "unsigned": [bytes([0x78 + i]) for i in range(len(keys))],
        "long": [b"Q" * 63 + bytes([i + 1]) for i in range(len(keys))],
    }[profile]
    mapping = dict(zip(keys, values))
    actual = c._checked_key_bytes(dict(fixture, key_bytes=mapping))
    assert actual == mapping and actual is not mapping
    assert len(set(actual.values())) == len(keys)


@pytest.mark.parametrize(
    "kind",
    [
        "list",
        "missing",
        "extra",
        "boolkey",
        "negativekey",
        "largekey",
        "string",
        "bytearray",
        "listvalue",
        "nul",
        "long",
        "duplicate",
        "reverse",
    ],
)
def test_invalid_mapping_rejected(fixture, kind):
    mapping = c._checked_key_bytes(fixture)
    keys = sorted(mapping)
    if kind == "list":
        mapping = list(mapping.items())
    elif kind == "missing":
        mapping.pop(keys[0])
    elif kind == "extra":
        mapping[max(keys) + 1] = b"zz"
    elif kind == "boolkey":
        mapping = {True: b"x"}
    elif kind == "negativekey":
        mapping[-1] = b"x"
    elif kind == "largekey":
        mapping[2**32] = b"x"
    elif kind == "string":
        mapping[keys[0]] = "x"
    elif kind == "bytearray":
        mapping[keys[0]] = bytearray(b"x")
    elif kind == "listvalue":
        mapping[keys[0]] = [1]
    elif kind == "nul":
        mapping[keys[0]] = b"a\0b"
    elif kind == "long":
        mapping[keys[0]] = b"a" * 65
    elif kind == "duplicate":
        mapping[keys[0]] = mapping[keys[1]]
    elif kind == "reverse":
        mapping[keys[0]], mapping[keys[1]] = mapping[keys[1]], mapping[keys[0]]
    with pytest.raises(RuntimeError):
        c._checked_key_bytes(dict(fixture, key_bytes=mapping))


@pytest.mark.parametrize("bad", [True, -1, 2**32, "1"])
def test_invalid_canonical_key_rejected_before_mapping(fixture, bad):
    fixture["source_state"]["tree"]["nodes"][0]["key"] = bad
    with pytest.raises(RuntimeError):
        c._checked_key_bytes(fixture)


def test_empty_union_accepts_only_empty_mapping():
    fixture = {
        s: {"tree": {"nodes": []}} for s in ("source_state", "destination_state")
    }
    assert c._checked_key_bytes(fixture) == {}
    assert c._checked_key_bytes(dict(fixture, key_bytes={})) == {}
    with pytest.raises(RuntimeError):
        c._checked_key_bytes(dict(fixture, key_bytes={0: b""}))
