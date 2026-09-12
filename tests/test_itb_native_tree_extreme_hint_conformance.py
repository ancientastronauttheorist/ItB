"""Joined minimum/end comparison, insertion, balancing and normal return."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.observatory import native_tree_extreme_hint_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "data/observatory/programs/windows_build_13725832_31fe35265598_"
CANONICAL = "7b3921045dbf9db41fd9f84d8c59167423eed78d2c09071734c9546161b4e37c"
RAW = "39f6ac8374c062547ddebb6a8af850eaebba5d66f5398da11673a04a5fa32cc7"


def read(pages, address, width=4):
    return sum(
        pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] << (8 * i)
        for i in range(width)
    )


def event(access, address, value, width=4):
    return dict(access=access, address=address, width=width, value=value)


@pytest.fixture(scope="module")
def cases():
    # One varied-alignment witness for each sequence/size/mode, with complete
    # alignment and DF combinations replayed separately by the native CLI.
    vectors = c.vectors()
    result = []
    for group in range(80):
        v = vectors[group * 40 + group % 40]
        f = c._fixture(v)
        result.append((v, f, c._expected(v, f)))
    return result


def comparison(v, f):
    new = read(f["pages"], f["node"] + 16)
    old = read(f["pages"], f["parent"] + 16)
    return (new, old) if v["mode"] == "minimum" else (old, new)


def test_both_modes_exact_comparator_argument_and_byte_order(cases):
    for v, f, e in cases:
        h = f["s"]
        left, right = comparison(v, f)
        minimum = v["mode"] == "minimum"
        assert read(f["pages"], h + 8) == (
            f["parent"] if minimum else c.attachment.HEAD
        )
        assert read(f["pages"], h + 12) == f["node"] + 16
        ret = c.BASE + (0x2E837A if minimum else 0x2E83AA)
        prologue = [
            event("write", h - 80, ret),
            event("write", h - 84, h - 4),
            event("read", h - 72, right),
            event("read", h - 76, left),
        ]
        begin = e["events"].index(prologue[0])
        assert e["events"][begin : begin + 4] == prologue
        byte_reads = []
        for offset, (a, b) in enumerate(zip(f["strings"][left], f["strings"][right])):
            byte_reads += [
                event("read", left + offset, a, 1),
                event("read", right + offset, b, 1),
            ]
            if a != b:
                assert a < b
                break
        else:
            pytest.fail("strict extreme comparison did not differ")
        assert e["events"][begin + 4 : begin + 4 + len(byte_reads)] == byte_reads
        end = begin + 4 + len(byte_reads)
        assert e["events"][end : end + 2] == [
            event("read", h - 84, h - 4),
            event("read", h - 80, ret),
        ]
        # RET8 from comparator entry H-80 resumes the caller at H-68.
        assert h - 80 + 12 == h - 68


def test_unused_comparison_ecx_and_real_child_frame(cases):
    for v, f, e in cases:
        h, n = f["s"], f["node"]
        selector = int(v["mode"] == "minimum")
        child_ret = c.BASE + (0x2E8392 if selector else 0x2E83C2)
        expected = [
            event("read", h - 32, n),
            event("write", h - 72, n),
            event("write", h - 76, 0xFFFFFFFF),
            event("read", h - 36, c.attachment.TREE),
            event("write", h - 80, f["parent"]),
            event("write", h - 84, selector),
            event("write", h - 88, c.OUTPUT),
            event("write", h - 92, child_ret),
        ]
        begin = e["events"].index(expected[0])
        assert e["events"][begin : begin + len(expected)] == expected
        child_end = e["events"].index(event("read", h - 92, child_ret))
        assert not any(
            a["access"] == "read" and a["address"] == h - 76
            for a in e["events"][begin:child_end]
        )
        assert read(e["pages"], h - 76) == 0xFFFFFFFF
        assert h - 92 + 24 == h - 68


def test_branch_dependent_edx_and_joined_seh_cookie_return(cases):
    branches = set()
    for v, f, e in cases:
        h = f["s"]
        steps = f["result"]["steps"]
        if not steps:
            branches.add("comparison_merge")
            left, right = comparison(v, f)
            last_left = next(
                a for a, b in zip(f["strings"][left], f["strings"][right]) if a != b
            )
            edx = (f["registers"]["edx"] & 0xFFFFFF00) | last_left
        else:
            last = steps[-1]
            if last["kind"] == "red_uncle":
                branches.add("uncle")
                identity = last["uncle"]
            else:
                branches.add("old_grandparent")
                identity = last["grandparent"]
            edx = c.attachment.HEAD if identity is None else f["addresses"][identity]
        assert e["registers"] == dict(
            f["registers"], eax=c.OUTPUT, ecx=v["cookie"], edx=edx, esp=h + 20
        )
        assert e["flags"] == 0x44 and e["endpoint"] == read(f["pages"], h)
        assert [a for a in e["events"] if a["address"] == 0] == [
            event("read", 0, v["previous_seh"]),
            event("write", 0, h - 16),
            event("write", 0, v["previous_seh"]),
        ]
        assert read(e["pages"], 0) == v["previous_seh"]
        assert (
            read(e["pages"], h - 24)
            == read(e["pages"], h - 68)
            == v["cookie"] ^ (h - 4)
        )
        assert read(e["pages"], h - 56) == c.BASE + 0x2E84D8
        assert read(e["pages"], h - 12) == 0x007D0EA0
    assert branches == {"comparison_merge", "uncle", "old_grandparent"}


def test_whole_tree_string_payload_and_output_pages(cases):
    for v, f, e in cases:
        tree = c.balancing.model.insert(f["tree"], v["key"])["tree"]
        pages = {p: bytearray(payload) for p, payload in f["pages"].items()}
        addresses = f["addresses"]
        at = lambda identity: (
            c.attachment.HEAD if identity is None else addresses[identity]
        )

        def put(address, value, width=4):
            for i, byte in enumerate(value.to_bytes(width, "little")):
                pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte

        for i, node in enumerate(tree["nodes"]):
            address = addresses[i]
            for offset, field in ((0, "left"), (4, "parent"), (8, "right")):
                put(address + offset, at(node[field]))
            put(address + 12, node["color"], 1)
            assert read(e["pages"], address + 16) == read(f["pages"], address + 16)
            assert read(e["pages"], address + 20) == read(f["pages"], address + 20)
            assert read(e["pages"], address + 14, 2) == 0xA5A5
        ordered = sorted(range(len(addresses)), key=lambda i: tree["nodes"][i]["key"])
        for offset, identity in ((0, ordered[0]), (4, tree["root"]), (8, ordered[-1])):
            put(c.attachment.HEAD + offset, at(identity))
        put(c.attachment.TREE + 4, len(addresses))
        put(c.OUTPUT, f["node"])
        for page, payload in pages.items():
            if page not in (c.attachment.STACK, c.attachment.STACK + 0x1000):
                assert bytes(payload) == e["pages"][page]
        assert (
            read(e["pages"], c.attachment.HEAD + (0 if v["mode"] == "minimum" else 8))
            == f["node"]
        )
        assert e["pages"][0x11000000] == f["pages"][0x11000000]
        assert e["pages"][0x12001000] == f["pages"][0x12001000]
        for offset in range(0, 24, 4):
            assert read(e["pages"], f["s"] + offset) == read(
                f["pages"], f["s"] + offset
            )


def test_extreme_insertions_have_no_triangle(cases):
    assert max(e["child_iterations"] for _, _, e in cases) == 2
    assert max(e["child_rotations"] for _, _, e in cases) == 1
    assert all(
        not any("triangle" in feature for feature in e["child_features"])
        for _, _, e in cases
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"keys": []},
        {"mode": "interior"},
        {"key": 1},
        {"key": 2},
        {"mode": "end", "key": 1},
        {"mode": "end", "key": 0},
        {"keys": [1, 1]},
        {"keys": list(range(1, 257))},
        {"string_alignment": True},
        {"string_alignment": 4},
        {"previous_seh": -1},
        {"cookie": 2**32},
        {"cookie": True},
        {"node_alignment": 32},
        {"tree_alignment": 16},
        {"frame_alignment": -1},
        {"df": 2},
        {"nil_marker": 0},
        {"key": False},
    ],
)
def test_invalid_extreme_or_input_bound_rejected(changes):
    with pytest.raises(RuntimeError):
        c._fixture(dict(c.vectors()[0], **changes))


@pytest.fixture(scope="module")
def receipts():
    names = dict(
        program_facts="program_facts",
        balancing="native_tree_balancing_conformance",
        comparator="native_tree_key_compare_conformance",
        cookie_return="native_lua_class_vector_return_conformance",
        evidence="native_tree_extreme_hint_conformance",
    )
    paths = {key: Path(str(PREFIX) + name + ".json") for key, name in names.items()}
    data = {key: json.loads(path.read_bytes()) for key, path in paths.items()}
    return paths, data, {key: data[key] for key in c.SOURCE_PINS}


def test_sealed_identity_and_coverage(receipts):
    paths, data, sources = receipts
    evidence = data["evidence"]
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert c.SEALED_SHA256 == c._canonical_sha256(evidence) == CANONICAL
    raw = paths["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW
    assert raw == c.encode_conformance(evidence).encode() and b"\r\n" not in raw
    summary = evidence["summary"]
    assert {key: summary[key] for key in summary if key != "child_features"} == dict(
        cases=3200,
        instruction_bytes=815,
        static_sites=298,
        executed_sites=226,
        normal_returns=3200,
        max_child_iterations=2,
        max_child_rotations=1,
        opaque_instructions=0,
        accounting_promotions=0,
    )
    assert not any("triangle" in feature for feature in summary["child_features"])
    assert evidence["negative_controls"] == [
        dict(kind=kind, rejected=True)
        for kind in ("ancestor", "padding", "seh", "cookie")
    ]


@pytest.mark.parametrize(
    "kind", ["evidence", "program_facts", "balancing", "comparator", "cookie_return"]
)
def test_mutated_receipt_or_source_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 999
    with pytest.raises(RuntimeError):
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
        str(ROOT / "scripts/itb_native_tree_extreme_hint_conformance.py"),
        "build",
        "--executable",
        exe,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=300)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["evidence"].read_bytes()
