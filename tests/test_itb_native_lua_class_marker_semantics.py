"""Independent Lua truth, partial EAX return and dual-stack checks."""

from __future__ import annotations
import copy
import hashlib
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from src.observatory import native_lua_class_marker_semantics as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize(
    "present,truth,void_eax",
    itertools.product([False, True], [False, True], [0, 0xFF, 0x12345678, 0xFFFFFFFF]),
)
def test_independent_partial_register_result(present, truth, void_eax):
    r = helper.marker_spec(present, truth, void_eax)
    assert r["al"] == int(present and truth)
    assert r["eax"] == ((void_eax & 0xFFFFFF00) | int(truth) if present else 0)
    assert r["native_esp_delta"] == 4 and r["lua_stack_delta"] == 0
    assert r["lua_stack_prefix_restored"] is True
    assert r["api_calls"] == (5 if present else 1)


def test_false_al_does_not_imply_zero_eax():
    result = helper.marker_spec(True, False, 0xDEADBEEF)
    assert result["al"] == 0 and result["eax"] == 0xDEADBE00


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("nil", False),
        ("false", False),
        ("true", True),
        ("zero", True),
        ("empty_string", True),
        ("table", True),
        ("function", True),
        ("userdata", True),
        ("thread", True),
    ],
)
def test_lua_truth_is_not_python_truth(kind, expected):
    assert helper.lua_truth(kind) is expected


@pytest.mark.parametrize(
    "args",
    [
        (0, False, 0),
        (True, 1, 0),
        (False, False, True),
        (True, True, -1),
        (True, True, 0x100000000),
    ],
)
def test_invalid_interface_inputs_rejected(args):
    with pytest.raises(helper.MarkerError):
        helper.marker_spec(*args)


@pytest.mark.parametrize("kind", [None, False, 0, "", "unknown"])
def test_invalid_value_kind_rejected(kind):
    with pytest.raises(helper.MarkerError):
        helper.lua_truth(kind)


@pytest.mark.parametrize(
    "alignment,prefix,present,kind,void_eax",
    itertools.product(
        [0, 15],
        [1, 3],
        [False, True],
        ["nil", "zero", "empty_string"],
        [0x12345678, 0xFFFFFFFF],
    ),
)
def test_modeled_paths_restore_both_stacks(alignment, prefix, present, kind, void_eax):
    r = helper.model_case(alignment, prefix, present, kind, void_eax)
    assert r["outcome"] == helper.marker_spec(present, kind != "nil", void_eax)
    names = [c["api"] for c in r["calls"]]
    assert names == (
        [
            "lua_getmetatable",
            "lua_pushstring",
            "lua_gettable",
            "lua_toboolean",
            "lua_settop",
        ]
        if present
        else ["lua_getmetatable"]
    )


def test_cdecl_cleanup_and_normal_return_premises():
    s = helper.call_summary_spec()
    assert s["arguments_bytes_each_call"] == 8
    assert s["callee_return_pop_bytes"] == 4 and s["callee_argument_cleanup_bytes"] == 0
    assert s["protected_entry_esp_relative_words"] == [-4, 0]
    assert "metamethods" in next(
        r["effect"] for r in s["lua_effects"] if r["api"] == "lua_gettable"
    )


@pytest.fixture(scope="module")
def chain():
    suffixes = {
        "chain": "native_lua_class_return_helper_chain",
        "direct_calls": "native_lua_direct_call_census",
        "program_facts": "program_facts",
        "evidence": "native_lua_class_marker_semantics",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffixes.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, {k: data[k] for k in helper.SOURCE_PINS}, data["evidence"]


def test_sealed_receipt(chain):
    paths, sources, evidence = chain
    assert (
        hashlib.sha256(paths["evidence"].read_bytes()).hexdigest()
        == "03efb733a13e11d102174abe2231c5a36f43df58f15d272a5ad32d2c19692540"
    )
    assert evidence["summary"] == dict(
        accounting_promotions=0,
        actual_import_executions=0,
        cases=576,
        direct_import_sites=6,
        modeled_nodes=32,
        path_classes=3,
        static_bytes=84,
        static_nodes=32,
        unique_imports=5,
    )
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert helper.encode_semantics(evidence).encode() == paths["evidence"].read_bytes()
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("raw_bytes", "private"),
        ("scope", {}),
        ("summary", {}),
    ],
)
def test_mutated_receipt_rejected(chain, key, value):
    _, sources, evidence = chain
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.MarkerError):
        helper.validate_structure(changed, sources)


def test_exact_pe_binary_cli_build(chain):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE for native marker rebuild")
    paths, sources, _ = chain
    args = ["build", "--executable", executable]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_lua_class_marker_semantics.py"),
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert r.stderr == b"" and r.stdout == paths["evidence"].read_bytes()
