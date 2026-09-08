"""Relocated append arguments and complete native ancestor-frame contract."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_tree_insert_decision_conformance as helper

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
        frame_alignment=7,
        nil_flag=128,
        seed=7,
    )


def test_unordered_existing_return_still_implies_exact_match():
    v = vector(b"a")
    e = helper._expected(v, helper._fixture(v))
    assert not e["ordered"] and not e["allocate"] and e["classification"] == 0
    assert e["candidate"] == 1


def test_unordered_allocation_frontier_does_not_prove_global_absence():
    v = vector(b"b")
    e = helper._expected(v, helper._fixture(v))
    assert not e["ordered"] and e["allocate"]
    assert any(bytes(n["key"]) == b"b" for n in v["nodes"])
    assert e["classification"] == -1


def test_empty_tree_never_dereferences_unmapped_query_argument():
    v = dict(nodes=[], root=None, query=None, frame_alignment=15, nil_flag=255, seed=7)
    f = helper._fixture(v)
    e = helper._expected(v, f)
    assert e["allocate"] and e["candidate"] is None
    assert all(event["address"] != f["query_argument"] for event in e["events"])
    assert e["flag_mask"] == 0x8D5 and e["flags"] & 0x8D5 == 0x44


@pytest.mark.parametrize("o", [44, 0x30001000, 0x3000100F, 2**32 - 17])
def test_decision_and_future_factory_frames_are_distinct(o):
    f = helper.frame_join(o)
    assert f["lower_bound"] == o - 28 and f["deepest_save"] == o - 44
    assert f["existing_return"] == o + 12 and f["factory_frontier"] == o - 32
    assert f["future_factory_entry"] == o - 36 and f["future_heap_entry"] == o - 96


@pytest.mark.parametrize("query", [b"a", b"b"])
def test_output_is_written_only_on_existing_return(query):
    v = vector(query)
    f = helper._fixture(v)
    e = helper._expected(v, f)
    writes = [
        event
        for event in e["events"]
        if event["access"] == "write"
        and helper.OUTPUT <= event["address"] < helper.OUTPUT + 16
    ]
    assert [(event["address"], event["width"]) for event in writes] == (
        [] if e["allocate"] else [(helper.OUTPUT, 4), (helper.OUTPUT + 4, 1)]
    )


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "lower_bound_semantics": "native_tree_lower_bound_semantics",
        "lower_bound_conformance": "native_tree_lower_bound_conformance",
        "conformance": "native_tree_insert_decision_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_sealed_decision_receipt(receipts):
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
        evidence["summary"]["executed_sites"] == 94
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
        str(ROOT / "scripts/itb_native_tree_insert_decision_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["conformance"].read_bytes()
