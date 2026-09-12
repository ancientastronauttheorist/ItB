"""One native red-uncle recoloring, return ABI, and independent tree invariants."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.observatory import native_tree_recolor_return_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "data/observatory/programs/windows_build_13725832_31fe35265598_"
CANONICAL_SHA256 = "5a17fee37ae6ae5d545d70e8268ae80b8b073321bb521339ec8cf989b5a6f6f3"
RAW_SHA256 = "18e6461ae59b87e80c19bb0ce732a35bdbf3e107fa4f45181373eef2bc61040e"


def read(pages, address, width=4):
    return sum(
        pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] << (8 * i)
        for i in range(width)
    )


def put(pages, address, value, width=4):
    for i, byte in enumerate(value.to_bytes(width, "little")):
        pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte


@pytest.mark.parametrize("vector", c.vectors())
def test_recolor_four_nodes_and_exact_return(vector):
    f = c._fixture(vector)
    e = c._expected(vector, f)
    a = c.attachment
    n, p, s = f["node"], f["parent"], f["s"]
    uncle = a.RIGHT if p == a.LEFT else a.LEFT
    assert [read(e["pages"], x + 12, 1) for x in (a.ROOT, a.LEFT, a.RIGHT, n)] == [
        1,
        1,
        1,
        0,
    ]
    assert e["root"] == a.ROOT
    assert read(e["pages"], a.TREE + 4) == 4
    assert read(e["pages"], c.OUTPUT) == n
    assert e["registers"] == dict(
        f["registers"], eax=c.OUTPUT, ecx=a.HEAD, edx=uncle, esp=s + 24
    )
    assert e["endpoint"] == read(f["pages"], s)
    assert e["flags"] == (0 if vector["head_color"] == 1 else 0x84)
    if vector["head_color"] == 1:
        assert c.color_invariants(e["pages"], [a.ROOT, a.LEFT, a.RIGHT, n]) == {
            "nodes": 4,
            "black_height": 3,
        }
    else:
        with pytest.raises(c.ConformanceError, match="canonical black sentinel"):
            c.color_invariants(e["pages"], [a.ROOT, a.LEFT, a.RIGHT, n])

    # Retain repeated ancestor loads: equal values are distinct native accesses.
    tail = [
        ("read", n + 4, 4, p),
        ("read", p + 12, 1, 0),
        ("write", s - 16, 4, f["registers"]["esi"]),
        ("read", n + 4, 4, p),
        ("read", p + 4, 4, a.ROOT),
        ("read", a.ROOT, 4, a.LEFT),
    ]
    if p == a.LEFT:
        tail.append(("read", a.ROOT + 8, 4, a.RIGHT))
    tail += [
        ("read", uncle + 12, 1, 0),
        ("write", p + 12, 1, 1),
        ("write", uncle + 12, 1, 1),
        ("read", n + 4, 4, p),
        ("read", p + 4, 4, a.ROOT),
        ("write", a.ROOT + 12, 1, 0),
        ("read", n + 4, 4, p),
        ("read", p + 4, 4, a.ROOT),
        ("read", a.ROOT + 4, 4, a.HEAD),
        ("read", a.HEAD + 12, 1, vector["head_color"]),
        ("read", s - 16, 4, f["registers"]["esi"]),
        ("read", a.TREE, 4, a.HEAD),
        ("read", s - 12, 4, f["registers"]["edi"]),
        ("read", a.HEAD + 4, 4, a.ROOT),
        ("write", a.ROOT + 12, 1, 1),
        ("read", s + 4, 4, c.OUTPUT),
        ("write", c.OUTPUT, 4, n),
        ("read", s - 8, 4, f["registers"]["ebx"]),
        ("read", s - 4, 4, f["registers"]["ebp"]),
        ("read", s, 4, e["endpoint"]),
    ]
    assert e["events"][-len(tail) :] == [
        dict(access=access, address=address, width=width, value=value)
        for access, address, width, value in tail
    ]


@pytest.mark.parametrize("color", [0, 2, 128, True, -1, 256])
def test_wrong_head_color_fixture_rejected(color):
    with pytest.raises(c.ConformanceError, match="recolor fixture differs"):
        c._fixture(dict(c.vectors()[0], head_color=color))


@pytest.mark.parametrize("count", [0, 2, 4])
def test_wrong_population_fixture_rejected(count):
    with pytest.raises(c.ConformanceError, match="count must match fixture population"):
        c._fixture(dict(c.vectors()[0], count=count))


@pytest.mark.parametrize(
    "corruption,message",
    [
        ("head", "canonical black sentinel"),
        ("head_nil", "canonical black sentinel"),
        ("root", "root must be black"),
        ("color", "noncanonical color"),
        ("red_parent", "red parent violation"),
        ("black_height", "unequal black height"),
        ("cycle", "cycle sharing or unknown child"),
        ("sharing", "cycle sharing or unknown child"),
        ("parent", "parent or nil metadata differs"),
        ("nil", "parent or nil metadata differs"),
        ("count", "membership or count differs"),
        ("duplicate", "invalid node partition"),
        ("head_member", "invalid node partition"),
        ("missing", "cycle sharing or unknown child"),
    ],
)
def test_forged_colored_topology_rejected(corruption, message):
    v = c.vectors()[0]
    f = c._fixture(v)
    e = c._expected(v, f)
    a = c.attachment
    n = f["node"]
    pages = {p: bytearray(value) for p, value in e["pages"].items()}
    nodes = [a.ROOT, a.LEFT, a.RIGHT, n]
    mutations = {
        "head": (a.HEAD + 12, 255, 1),
        "head_nil": (a.HEAD + 13, 0, 1),
        "root": (a.ROOT + 12, 0, 1),
        "color": (a.LEFT + 12, 2, 1),
        "red_parent": (a.LEFT + 12, 0, 1),
        "black_height": (n + 12, 1, 1),
        "cycle": (a.LEFT + 8, a.ROOT, 4),
        "sharing": (a.LEFT + 8, n, 4),
        "parent": (n + 4, a.RIGHT, 4),
        "nil": (n + 13, 1, 1),
        "count": (a.TREE + 4, 3, 4),
    }
    if corruption in mutations:
        put(pages, *mutations[corruption])
    elif corruption == "duplicate":
        nodes.append(n)
    elif corruption == "head_member":
        nodes.append(a.HEAD)
    else:
        nodes.remove(n)
    with pytest.raises(c.ConformanceError, match=message):
        c.color_invariants(pages, nodes)


@pytest.fixture(scope="module")
def receipts():
    paths = {
        k: Path(
            str(PREFIX)
            + ("native_tree_attachment_conformance" if k == "attachment" else k)
            + ".json"
        )
        for k in c.SOURCE_PINS
    }
    paths["evidence"] = Path(
        str(PREFIX) + "native_tree_recolor_return_conformance.json"
    )
    data = {k: json.loads(p.read_bytes()) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in c.SOURCE_PINS}


def test_receipt_seal_and_raw_encoding(receipts):
    paths, data, sources = receipts
    evidence = data["evidence"]
    raw = paths["evidence"].read_bytes()
    assert c.SEALED_SHA256 == c._canonical_sha256(evidence) == CANONICAL_SHA256
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert raw == c.encode_conformance(evidence).encode() and b"\r\n" not in raw
    assert hashlib.sha256(raw).hexdigest() == RAW_SHA256
    assert evidence["summary"] == dict(
        cases=320,
        instruction_bytes=199,
        static_sites=71,
        executed_sites=65,
        returned_cases=320,
        opaque_instructions=0,
        accounting_promotions=0,
    )


@pytest.mark.parametrize("kind", ["evidence", "attachment", "program_facts"])
def test_mutated_receipts_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 999
    with pytest.raises((c.ConformanceError, RuntimeError)):
        c.validate_structure(
            changed if kind == "evidence" else data["evidence"],
            sources if kind == "evidence" else dict(sources, **{kind: changed}),
        )


def test_exact_cli_rebuild(receipts):
    exe = os.environ.get("ITB_EXACT_EXE")
    if not exe:
        pytest.skip("requires private exact executable and Unicorn runtime")
    paths, _, sources = receipts
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_tree_recolor_return_conformance.py"),
        "build",
        "--executable",
        exe,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["evidence"].read_bytes()
