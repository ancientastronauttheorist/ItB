"""Independent feature-query branch, stack-frame and exclusive-stop checks."""

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
from src.observatory import native_assertion_helper_failure_dispatch as helper
from scripts import itb_native_assertion_helper_failure_dispatch as cli

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.fixture(scope="module")
def chain():
    suffixes = {
        "owner": "native_assertion_helper_owner_composition",
        "frontier": "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary",
        "pair": "native_assertion_helper_descendant_pair",
        "program_facts": "program_facts",
        "evidence": "native_assertion_helper_failure_dispatch",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffixes.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, {k: data[k] for k in helper.SOURCE_PINS}, data["evidence"]


@pytest.mark.parametrize("query", [0, 1, 2, 0x80000000, 0xFFFFFFFF])
def test_independent_dispatch_predicate(query):
    result = helper.dispatch_spec(query)
    assert result["boundary"] == ("before_interrupt" if query else "before_fallback")
    assert result["exclusive_stop_rva"] == ("0x00357b81" if query else "0x00357b83")
    assert result["eax"] == query
    assert result["ecx_value"] == (2 if query else None)
    assert result["esp_G_offset"] == -804
    assert result["query_argument"] == 23
    assert result["zero_flag"] == (query == 0)
    assert result["interrupt_vector_if_reached"] == (41 if query else None)
    assert (
        not result["interrupt_executed"] and not result["fallback_instruction_executed"]
    )


@pytest.mark.parametrize("bad", [True, -1, 0x100000000, 0.0, None, "0"])
def test_bad_query_word_rejected(bad):
    with pytest.raises(helper.DispatchError):
        helper.dispatch_spec(bad)


def test_inherited_frame_arithmetic_and_tail_thunk():
    frame = helper.frame_spec()
    assert frame["new_frame_F_offset"] == -816
    assert frame["entry_esp_F_offset"] == -812
    assert frame["entry_esp_G_offset"] == 4
    assert frame["reserved_locals_G_interval"] == [-804, 0]
    assert frame["reserved_local_bytes"] == 804
    assert frame["query_callee_entry_esp_G_offset"] == -812
    assert frame["query_return_esp_G_offset"] == -804
    assert frame["query_return_esp_F_offset"] == -1620
    assert (
        frame["query_return_esp_F_offset"]
        == frame["new_frame_F_offset"] + frame["query_return_esp_G_offset"]
    )
    contract = helper.query_summary_spec()
    assert contract["callee_entry_to_return_esp_increment"] == 8
    assert contract["callee_argument_cleanup_bytes"] == 4
    assert contract["argument_value"] == 23
    assert contract["protected_memory_G_intervals"] == [[0, 4], [4, 8]]


def test_matrix_and_unexecuted_boundaries():
    expected = list(itertools.product(range(16), [0, 1, 0xFFFFFFFF], range(2)))
    assert helper.cases() == expected and len(expected) == 96
    for case in expected:
        result = helper.model_case(case)
        # Neither reported stop is an executed model instruction.
        assert "0x00357b81" not in result["trace_rvas"]
        assert "0x00357b83" not in result["trace_rvas"]
        assert "0x0039cb92" in result["trace_rvas"]


def test_sealed_receipt(chain):
    paths, sources, evidence = chain
    assert hashlib.sha256(paths["evidence"].read_bytes()).hexdigest() == (
        "531e1a6f00b39a3c80b12cdada984c847ecc134611927a238b06d2c36bdf2525"
    )
    assert evidence["summary"] == {
        "actual_import_executions": 0,
        "before_fallback": 32,
        "before_interrupt": 64,
        "fallback_instruction_executions": 0,
        "interrupt_executions": 0,
        "model_cases": 96,
        "modeled_prefix_nodes": 9,
        "modeled_thunk_nodes": 1,
        "static_prefix_bytes": 25,
        "static_prefix_nodes": 10,
    }
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert helper.encode_dispatch(evidence).encode() == paths["evidence"].read_bytes()
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("scope", {}),
        ("raw_bytes", "private"),
        ("frame", {}),
        ("summary", {}),
    ],
)
def test_receipt_mutation_rejected(chain, key, value):
    _, sources, evidence = chain
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.DispatchError):
        helper.validate_structure(changed, sources)


def args(chain, command):
    paths, sources, _ = chain
    result = [command, "--evidence", str(paths["evidence"])]
    for key in sources:
        result += ["--" + key.replace("_", "-"), str(paths[key])]
    return result


def test_exact_pe_rebuild(chain):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE to rebuild failure dispatch")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_assertion_helper_failure_dispatch.py"),
            *args(chain, "verify"),
            "--executable",
            executable,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == "" and json.loads(result.stdout)["status"] == "verified"
