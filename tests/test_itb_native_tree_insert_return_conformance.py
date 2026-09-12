"""Whole insertion owner: true/false pair, native joins and preserved state."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_tree_insert_return_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "data/observatory/programs/windows_build_13725832_31fe35265598_"
CANONICAL = "3fe78f6dac77180f9098dced2624beb51524202e50bed7952de6ec17e20a682b"
RAW = "257a147eb0e09c47eff593a534256da6e7ac4f72c8f3e6213047bce3497c6ba7"


def read(pages, a, w=4):
    return sum(pages[(a + i) & ~4095][(a + i) & 4095] << (8 * i) for i in range(w))


@pytest.fixture(scope="module")
def cases():
    vectors = c.vectors()
    chosen = []
    for mode in ("empty", "minimum", "end", "interior", "existing"):
        group = [v for v in vectors if v["mode"] == mode]
        chosen.extend(group[:2] + group[-2:])
    return [(v, c._fixture(v)) for v in chosen]


def test_pair_and_independent_final_key_map(cases):
    for v, f in cases:
        before = copy.deepcopy(f)
        e = c._expected(v, f)
        assert f == before
        inserted = v["key"] not in v["keys"]
        assert e["allocate"] == inserted
        wanted = f["node"] if inserted else f["addresses"][v["keys"].index(v["key"])]
        assert read(e["pages"], c.OUTPUT) == wanted
        assert read(e["pages"], c.OUTPUT + 4, 1) == int(inserted)
        assert read(e["pages"], c.leaf.TREE + 4) == len(v["keys"]) + int(inserted)
        tree = f["result"]["tree"] if inserted else f["tree"]
        at = lambda i: c.leaf.HEAD if i is None else f["addresses"][i]
        assert read(e["pages"], c.leaf.HEAD + 4) == at(tree["root"])
        for i, n in enumerate(tree["nodes"]):
            a = at(i)
            for offset, name in ((0, "left"), (4, "parent"), (8, "right")):
                assert read(e["pages"], a + offset) == at(n[name])
            assert read(e["pages"], a + 12, 1) == n["color"]
        if inserted:
            assert read(e["pages"], f["node"] + 20) == 0
        else:
            for page, payload in f["pages"].items():
                if page not in (
                    c.construction.STACK,
                    c.construction.STACK + 4096,
                    c.OUTPUT & ~4095,
                ):
                    assert e["pages"][page] == payload


def test_real_hint_frame_and_pair_write_order(cases):
    for v, f in cases:
        e = c._expected(v, f)
        o = f["stack"]
        events = e["events"]
        writes = [x for x in events if x["access"] == "write"]
        if v["mode"] == "existing":
            assert e["hint_entry"] is None
            assert not any(x["address"] == 0 for x in writes)
            assert not any(
                c.construction.DATA <= x["address"] < c.construction.DATA + 0x4000
                for x in writes
            )
            continue
        h = o - 40
        assert e["hint_entry"] == h
        call = dict(access="write", address=h, width=4, value=c.BASE + 0x2E8270)
        assert events.count(call) == 1
        index = events.index(call)
        assert events[index - 4 : index] == [
            dict(access="write", address=o - 24, width=4, value=f["node"]),
            dict(access="write", address=o - 28, width=4, value=f["node"] + 16),
            dict(
                access="write", address=o - 32, width=4, value=read(e["pages"], o - 32)
            ),
            dict(access="write", address=o - 36, width=4, value=o - 8),
        ]
        assert events[-8:] == [
            dict(access="read", address=o - 8, width=4, value=f["node"]),
            dict(access="write", address=c.OUTPUT, width=4, value=f["node"]),
            dict(access="write", address=c.OUTPUT + 4, width=1, value=1),
            *[
                dict(access="read", address=o + off, width=4, value=f["registers"][reg])
                for off, reg in ((-20, "edi"), (-16, "esi"), (-12, "ebx"), (-4, "ebp"))
            ],
            dict(access="read", address=o, width=4, value=f["return_address"]),
        ]


def test_final_abi_cookie_and_preserved_storage(cases):
    for v, f in cases:
        e = c._expected(v, f)
        o = f["stack"]
        assert e["registers"]["eax"] == c.OUTPUT and e["registers"]["esp"] == o + 12
        assert e["endpoint"] == f["return_address"]
        for reg in ("ebp", "ebx", "esi", "edi"):
            assert e["registers"][reg] == f["registers"][reg]
        assert read(e["pages"], 0) == v["previous_seh"]
        assert read(e["pages"], c.empty.COOKIE) == v["cookie"]
        if e["allocate"]:
            assert e["registers"]["ecx"] == v["cookie"] and e["flags"] == 0x44
        for a, payload in f["strings"].items():
            assert (
                bytes(read(e["pages"], a + i, 1) for i in range(len(payload)))
                == payload
            )
        for offset in (5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15):
            assert read(e["pages"], c.OUTPUT + offset, 1) == read(
                f["pages"], c.OUTPUT + offset, 1
            )
        assert read(e["pages"], o + 12) == read(f["pages"], o + 12)


@pytest.mark.parametrize(
    "changes",
    [
        {"key": True},
        {"key": -1},
        {"key": 2**32},
        {"cookie": True},
        {"cookie": 2**32},
        {"previous_seh": -1},
        {"previous_seh": True},
        {"node_alignment": 32},
        {"frame_alignment": -1},
        {"nil_flag": 0},
        {"mode": "fallback"},
        {"keys": [1, 1]},
        {"keys": list(range(32))},
    ],
)
def test_invalid_inputs_rejected(changes):
    v = next(v for v in c.vectors() if v["mode"] == "existing")
    with pytest.raises(RuntimeError):
        c._fixture(dict(v, **changes))


@pytest.fixture(scope="module")
def receipts():
    names = dict(
        program_facts="program_facts",
        construction="native_tree_insert_construction_conformance",
        empty_hint="native_tree_empty_hint_conformance",
        extreme_hint="native_tree_extreme_hint_conformance",
        interior_hint="native_tree_interior_hint_conformance",
        evidence="native_tree_insert_return_conformance",
    )
    paths = {k: Path(str(PREFIX) + n + ".json") for k, n in names.items()}
    data = {k: json.loads(p.read_bytes()) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in c.SOURCE_PINS}


def test_seal_and_full_owner_coverage(receipts):
    paths, data, sources = receipts
    e = data["evidence"]
    raw = paths["evidence"].read_bytes()
    assert c.validate_structure(e, sources)["status"] == "structurally_verified"
    assert c._canonical_sha256(e) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(raw).hexdigest() == RAW
    assert raw == c.encode_conformance(e).encode() and b"\r\n" not in raw
    assert e["summary"] == dict(
        cases=942,
        instruction_bytes=1483,
        static_sites=580,
        executed_sites=533,
        owner_sites=69,
        allocated_returns=582,
        existing_returns=360,
        modes=dict(empty=6, minimum=144, end=144, interior=288, existing=360),
        heap_api_summaries=582,
        max_child_iterations=3,
        max_child_rotations=2,
        opaque_instructions=0,
        accounting_promotions=0,
    )
    assert e["negative_controls"] == [
        dict(kind=k, rejected=True)
        for k in ("ancestor", "padding", "seh", "local_result", "cookie")
    ]


@pytest.mark.parametrize("kind", ["evidence", *c.SOURCE_PINS])
def test_tampered_receipt_or_source_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 999
    with pytest.raises(RuntimeError):
        c.validate_structure(
            changed if kind == "evidence" else data["evidence"],
            sources if kind == "evidence" else dict(sources, **{kind: changed}),
        )


def test_exact_cli(receipts):
    exe = os.environ.get("ITB_EXACT_EXE")
    if not exe:
        pytest.skip("requires private exact executable and Unicorn runtime")
    paths, _, sources = receipts
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_tree_insert_return_conformance.py"),
        "build",
        "--executable",
        exe,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    r = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=300)
    assert r.returncode == 0, r.stderr
    assert r.stderr == b"" and r.stdout == paths["evidence"].read_bytes()
