"""Relocated append arguments and complete native ancestor-frame contract."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_tree_insert_construction_conformance as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


def vector(query):
    return dict(
        nodes=[
            dict(key=list(b"m"), left=1, right=2),
            dict(key=list(b"a"), left=None, right=None),
            dict(key=list(b"b"), left=None, right=None),
        ],
        root=0,
        query=list(query),
        frame_alignment=15,
        nil_flag=255,
        seed=7,
        node_alignment=7,
    )


def read(pages, address, width=4):
    return int.from_bytes(
        bytes(
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] for i in range(width)
        ),
        "little",
    )


def test_existing_return_does_not_construct_node_or_read_heap():
    v = vector(b"a")
    f = helper._fixture(v)
    e = helper._expected(v, f)
    assert not e["allocate"]
    assert all(event["address"] != helper.IAT for event in e["events"])
    assert all(
        e["pages"][helper.DATA + i * 0x1000] == f["pages"][helper.DATA + i * 0x1000]
        for i in range(4)
    )


@pytest.mark.parametrize("alignment", [0, 1, 7, 15, 31])
def test_constructed_node_contains_query_pointer_and_preserved_padding(alignment):
    v = vector(b"b")
    v["node_alignment"] = alignment
    f = helper._fixture(v)
    e = helper._expected(v, f)
    p = f["node"]
    o = f["stack"]
    assert e["allocate"] and e["endpoint"] == helper.BASE + 0x2E826B
    assert [read(e["pages"], p + i) for i in (0, 4, 8)] == [helper.leaf.HEAD] * 3
    assert read(e["pages"], p + 12, 2) == 0
    assert read(e["pages"], p + 14, 2) == read(f["pages"], p + 14, 2)
    assert read(e["pages"], p + 16) == helper.leaf.QUERY
    assert read(e["pages"], p + 20) == 0
    assert [read(e["pages"], o + i) for i in (-36, -32, -28, -24)] == [
        o - 8,
        helper.leaf_replay._node(e["candidate"]),
        p + 16,
        p,
    ]
    assert e["registers"]["esp"] == o - 36 and e["flag_mask"] == 0x8D5
    assert e["flags"] & 0x8D5 == int(((p + 16) & 255).bit_count() % 2 == 0) << 2


def test_empty_tree_supplies_real_key_chain_for_construction():
    v = dict(
        nodes=[],
        root=None,
        query=[],
        frame_alignment=0,
        nil_flag=1,
        seed=7,
        node_alignment=0,
    )
    f = helper._fixture(v)
    e = helper._expected(v, f)
    assert f["query_argument"] == helper.leaf.ARG
    assert e["allocate"] and read(e["pages"], f["node"] + 16) == helper.leaf.QUERY
    assert any(event["address"] == helper.leaf.ARG for event in e["events"])


@pytest.mark.parametrize("o", [96, 0x30001000, 0x3000100F, 2**32 - 17])
def test_hint_frontier_protects_full_nested_factory_frame(o):
    f = helper.frame_join(o)
    assert f["heap_api"] == f["protected_start"] == o - 96
    assert f["hint_frontier"] == o - 36 and f["future_hint_entry"] == o - 40


@pytest.mark.parametrize("o", [44, 95, True, 2**32 - 16])
def test_too_shallow_or_wrapping_ancestor_rejected(o):
    with pytest.raises(helper.ConformanceError):
        helper.frame_join(o)


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "lower_bound_semantics": "native_tree_lower_bound_semantics",
        "lower_bound_conformance": "native_tree_lower_bound_conformance",
        "decision_conformance": "native_tree_insert_decision_conformance",
        "factory_conformance": "native_tree_node_factory_conformance",
        "conformance": "native_tree_insert_construction_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_sealed_construction_receipt(receipts):
    paths, data, sources = receipts
    evidence = data["conformance"]
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )
    assert (
        helper.encode_conformance(evidence).encode()
        == paths["conformance"].read_bytes()
    )
    assert (
        evidence["summary"]["executed_sites"] == 175
        and evidence["summary"]["opaque_instructions"] == 0
    )


def test_changed_receipt_rejected(receipts):
    _, data, sources = receipts
    changed = copy.deepcopy(data["conformance"])
    changed["schema_version"] = 99
    with pytest.raises(helper.ConformanceError):
        helper.validate_structure(changed, sources)


def test_exact_cli_rebuild(receipts):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    paths, _, sources = receipts
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_tree_insert_construction_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["conformance"].read_bytes()
