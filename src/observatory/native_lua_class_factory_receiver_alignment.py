"""Bounded producer address adapter for the existing empty receiver grammar."""

from __future__ import annotations
from src.observatory import native_lua_class_factory_conformance as full
from src.observatory import native_lua_class_tree_conformance as tree

USERDATA, RECORD = tree.RECEIVER, tree.leaf.HEAD
_require = full._require


def vectors():
    return [
        v
        for v in full.vectors()
        if v["length"] in (0, 16, 255)
        and v["pattern"] == "high"
        and v["name_alignment"] == 4095
        and not v["equal_pointers"]
        and v["record_bias"] == 0x100
        and v["record_alignment"] == 0
    ]


def install(vector, prototype):
    """Preserve extended fixture pages and supply two writable target spans.

    The normal native factory performs all userdata and record writes. This
    adapter never populates a tree or writes produced field values itself.
    """
    _require(
        type(vector) is dict
        and vector in vectors()
        and all(
            type(vector[k]) is int
            for k in vector
            if k not in ("pattern", "equal_pointers")
        )
        and type(vector["pattern"]) is str
        and type(vector["equal_pointers"]) is bool,
        "unreviewed factory receiver alignment vector",
    )
    fixture = full._extend_fixture(vector, prototype)
    pages = dict(fixture["pages"])
    for page in (USERDATA & ~4095, (USERDATA + 71) & ~4095):
        _require(
            page not in pages, "factory receiver alignment overlaps original pages"
        )
        pages[page] = b"\xa5" * 4096
    _require(
        USERDATA + 52 == tree.leaf.TREE
        and RECORD == 0x10000100
        and USERDATA + 72 <= RECORD
        and RECORD + 24 < 0x10001000,
        "factory receiver alignment grammar differs",
    )
    return dict(fixture, pages=pages, userdata=USERDATA, record=RECORD)
