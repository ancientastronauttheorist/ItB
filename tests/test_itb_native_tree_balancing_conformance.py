"""Finite native balancing equations against independent whole-tree semantics."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.observatory import native_tree_balancing_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "data/observatory/programs/windows_build_13725832_31fe35265598_"
CANONICAL = "58b41864a6b9f486adf139102e08bdb8d4620660963998bd43675800265b31ce"
RAW = "e383bf77f6ec42e23f1bd5c40d07c9170d38bca5dd00ae307c3f9906bfd588d7"


def read(pages, address, width=4):
    return sum(
        pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] << (8 * i)
        for i in range(width)
    )


def event(access, address, value, width=4):
    return dict(access=access, address=address, width=width, value=value)


def vector(keys):
    return dict(
        c.vectors()[0],
        keys=keys[:-1],
        key=keys[-1],
        node_alignment=31,
        tree_alignment=15,
        frame_alignment=7,
        df=1,
    )


@pytest.fixture(scope="module")
def representatives():
    """Find actual corpus witnesses once, without loading Unicorn in pytest."""
    selected = {}
    maximum_iterations = maximum_rotations = 0
    for v in c.vectors():
        f = c._fixture(v)
        e = c._expected(v, f)
        case = (v, f, e)
        selected.setdefault("baseline", case)
        for feature in e["features"]:
            selected.setdefault(feature, case)
        if e["features"].count("red_uncle") >= 2 and e["rotations"]:
            selected.setdefault("repeated_before_rotation", case)
        maximum_iterations = max(maximum_iterations, e["iterations"])
        maximum_rotations = max(maximum_rotations, e["rotations"])
    assert maximum_iterations == 4 and maximum_rotations == 2
    return selected


@pytest.mark.parametrize(
    "keys,kinds,root",
    [
        ([3, 2, 1], ["left_line_root"], 1),
        ([3, 1, 2], ["left_triangle_left_child", "left_line_root"], 2),
        ([1, 2, 3], ["right_line_root"], 1),
        ([1, 3, 2], ["right_triangle_right_child", "right_line_root"], 2),
    ],
)
def test_four_hand_derived_rotation_orientations(keys, kinds, root):
    v = vector(keys)
    f = c._fixture(v)
    e = c._expected(v, f)
    assert e["features"] == kinds
    assert e["rotations"] == len(kinds)
    assert read(e["pages"], c.attachment.HEAD + 4) == f["addresses"][root]
    assert [read(e["pages"], a + 12, 1) for a in f["addresses"]] == [
        int(i == root) for i in range(3)
    ]
    assert e["registers"]["edx"] == f["addresses"][0]


def test_complete_model_pages_and_protected_storage(representatives):
    cases = {id(v): (v, f, e) for v, f, e in representatives.values()}
    for v, f, e in cases.values():
        before = copy.deepcopy(f["tree"])
        independent = c.model.insert(f["tree"], v["key"])["tree"]
        assert f["tree"] == before
        assert independent == f["result"]["tree"]
        addresses = f["addresses"]
        at = lambda i: c.attachment.HEAD if i is None else addresses[i]
        # Construct complete expected non-stack pages independently. All bytes
        # outside structural fields, count and the output slot must survive.
        pages = {p: bytearray(payload) for p, payload in f["pages"].items()}

        def put(address, value, width=4):
            for i, byte in enumerate(value.to_bytes(width, "little")):
                pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte

        for i, node in enumerate(independent["nodes"]):
            address = addresses[i]
            for offset, field in ((0, "left"), (4, "parent"), (8, "right")):
                put(address + offset, at(node[field]))
            put(address + 12, node["color"], 1)
            assert read(e["pages"], address + 16) == node["key"]
            assert read(e["pages"], address + 20) == (
                0x87654321 if i == len(addresses) - 1 else 0x75310000 + i
            )
            assert read(e["pages"], address + 14, 2) == 0xA5A5
        order = sorted(
            range(len(addresses)), key=lambda i: independent["nodes"][i]["key"]
        )
        for offset, identity in (
            (0, order[0]),
            (4, independent["root"]),
            (8, order[-1]),
        ):
            put(c.attachment.HEAD + offset, at(identity))
        put(c.attachment.TREE + 4, len(addresses))
        put(c.OUTPUT, f["node"])
        for page, payload in pages.items():
            if page not in (c.attachment.STACK, c.attachment.STACK + 0x1000):
                assert bytes(payload) == e["pages"][page]
        assert read(e["pages"], c.attachment.HEAD + 13, 1) == v["nil_marker"]
        for offset in range(0, 24, 4):
            assert read(e["pages"], f["s"] + offset) == read(
                f["pages"], f["s"] + offset
            )


@pytest.mark.parametrize("keys", [[0], [1, 2], [2, 1, 3, 0], [3, 1, 2], list(range(8))])
def test_exact_return_abi_and_branch_dependent_edx(keys):
    v = vector(keys)
    f = c._fixture(v)
    e = c._expected(v, f)
    steps = f["result"]["steps"]
    last = steps[-1] if steps else None
    at = lambda i: c.attachment.HEAD if i is None else f["addresses"][i]
    edx = (
        f["registers"]["edx"]
        if last is None
        else at(last["uncle"] if last["kind"] == "red_uncle" else last["grandparent"])
    )
    # Final loop condition reads the parent and its canonical black byte.
    color_read = max(
        i
        for i, a in enumerate(e["events"])
        if a["access"] == "read" and a["width"] == 1
    )
    final_color = e["events"][color_read]
    parent = final_color["address"] - 12
    cursor = (
        len(f["addresses"]) - 1
        if last is None
        else (last["grandparent"] if last["kind"] == "red_uncle" else last["current"])
    )
    assert parent == at(f["result"]["tree"]["nodes"][cursor]["parent"])
    assert final_color["value"] == 1
    assert e["events"][color_read - 1]["value"] == parent
    assert e["registers"] == dict(
        f["registers"], eax=c.OUTPUT, ecx=parent, edx=edx, esp=f["s"] + 24
    )
    assert e["flags"] == 0 and e["endpoint"] == read(f["pages"], f["s"])
    assert read(e["pages"], c.OUTPUT) == f["node"]
    assert all(
        e["registers"][r] == f["registers"][r] for r in ("ebx", "ebp", "esi", "edi")
    )


@pytest.mark.parametrize(
    "kind", ["left_triangle", "left_line", "right_triangle", "right_line"]
)
def test_nonnil_transfer_keeps_repeated_reads_and_parent_write(representatives, kind):
    _, f, e = representatives[kind + "_nonnil_transfer"]
    step = next(s for s in f["result"]["steps"] if s["kind"] == kind)
    pivot = f["addresses"][
        step["parent"] if kind.endswith("triangle") else step["grandparent"]
    ]
    left_rotation = kind in ("left_triangle", "right_line")
    child, inner = (8, 0) if left_rotation else (0, 8)
    events = e["events"]
    found = False
    for index, first in enumerate(events[:-5]):
        if (
            first["access"] != "read"
            or first["address"] != pivot + child
            or first["width"] != 4
        ):
            continue
        promoted = first["value"]
        middle = events[index + 1]["value"]
        if middle == c.attachment.HEAD:
            continue
        expected = [
            event("read", pivot + child, promoted),
            event("read", promoted + inner, middle),
            event("write", pivot + child, middle),
            event("read", promoted + inner, middle),
            event("read", middle + 13, 0, 1),
            event("write", middle + 4, pivot),
        ]
        if events[index : index + 6] == expected:
            found = True
            break
    assert found, (kind, f["result"]["steps"])


def test_repeated_recolor_precedes_rotations(representatives):
    _, f, e = representatives["repeated_before_rotation"]
    kinds = [s["kind"] for s in f["result"]["steps"]]
    assert kinds[:2] == ["red_uncle", "red_uncle"]
    assert e["features"][:2] == ["red_uncle", "red_uncle"]
    assert e["rotations"] in (1, 2)
    assert e["iterations"] >= 3
    assert any(k.endswith("line") for k in kinds[2:])


@pytest.mark.parametrize(
    "field,value",
    [
        ("node_alignment", 32),
        ("node_alignment", True),
        ("tree_alignment", 16),
        ("frame_alignment", -1),
        ("df", 2),
        ("nil_marker", 0),
        ("nil_marker", 256),
        ("keys", [True]),
        ("keys", [-1]),
        ("keys", [2**32]),
        ("keys", [1, 1]),
        ("keys", list(range(256))),
        ("keys", (1,)),
        ("key", True),
        ("key", 2**32),
    ],
)
def test_malformed_fixture_rejected(field, value):
    v = dict(vector([1, 2]), **{field: value})
    with pytest.raises(RuntimeError):
        c._fixture(v)


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "attachment": "native_tree_attachment_conformance",
        "semantics": "native_tree_balancing_semantics",
        "program_facts": "program_facts",
        "evidence": "native_tree_balancing_conformance",
    }
    paths = {k: Path(str(PREFIX) + name + ".json") for k, name in suffix.items()}
    data = {k: json.loads(p.read_bytes()) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in c.SOURCE_PINS}


def test_sealed_identity_and_exact_coverage(receipts):
    paths, data, sources = receipts
    e = data["evidence"]
    assert c.validate_structure(e, sources)["status"] == "structurally_verified"
    assert c.SEALED_SHA256 == c._canonical_sha256(e) == CANONICAL
    raw = paths["evidence"].read_bytes()
    assert raw == c.encode_conformance(e).encode() and b"\r\n" not in raw
    assert hashlib.sha256(raw).hexdigest() == RAW
    assert {
        k: e["summary"][k]
        for k in (
            "cases",
            "instruction_bytes",
            "static_sites",
            "executed_sites",
            "max_iterations",
            "max_rotations",
            "returned_cases",
            "opaque_instructions",
            "accounting_promotions",
        )
    } == dict(
        cases=1329,
        instruction_bytes=500,
        static_sites=181,
        executed_sites=175,
        max_iterations=4,
        max_rotations=2,
        returned_cases=1329,
        opaque_instructions=0,
        accounting_promotions=0,
    )
    unreachable = {
        "0x0007d149",
        "0x0007d14c",
        "0x0007d159",
        "0x0007d209",
        "0x0007d20c",
        "0x0007d21b",
    }
    assert set(e["scope"]["unreachable_rvas"]) == unreachable
    assert {p["rva"] for p in e["body"]["points"]} - set(
        e["executed_rvas"]
    ) == unreachable
    assert e["negative_controls"] == [
        dict(kind=k, rejected=True) for k in ("ancestor", "padding", "saved_esi")
    ]


@pytest.mark.parametrize(
    "kind", ["evidence", "attachment", "semantics", "program_facts"]
)
def test_mutated_evidence_and_source_rejected(receipts, kind):
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
        str(ROOT / "scripts/itb_native_tree_balancing_conformance.py"),
        "build",
        "--executable",
        exe,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=300)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["evidence"].read_bytes()
