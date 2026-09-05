"""Independent stdcall argument lifetimes and conditional return-chain checks."""

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
from src.observatory import native_assertion_helper_failure_return as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize(
    "eax,ebp,target",
    itertools.product([0, 1, 0xFFFFFFFF], [0, 0x87654321], [0x12345678, 0xFFFFFFFF]),
)
def test_independent_return_relation(eax, ebp, target):
    r = helper.return_spec(eax, ebp, target)
    assert r["eax"] == eax and r["ebp"] == ebp and r["instruction_pointer"] == target
    assert r["esp_G_offset"] == 816 + 8 and r["esp_F_offset"] == 8
    assert not r["termination_guaranteed"] and not r["original_owner_return_guaranteed"]


@pytest.mark.parametrize("bad", [True, -1, 0x100000000, 1.0, None, "0"])
@pytest.mark.parametrize("index", range(3))
def test_return_interface_rejects_invalid_words(bad, index):
    args = [0, 0, 0]
    args[index] = bad
    with pytest.raises(helper.FailureReturnError):
        helper.return_spec(*args)


def test_independent_four_call_stack_and_arguments():
    expected_cases = list(
        itertools.product(range(16), [0, 0xFFFFFFFF], [0, 1, 0xFFFFFFFF], range(2))
    )
    assert helper.cases() == expected_cases and len(expected_cases) == 192
    for case in expected_cases:
        result = helper.model_case(case)
        calls = result["calls"]
        assert [c["name"] for c in calls] == [
            "SetUnhandledExceptionFilter",
            "UnhandledExceptionFilter",
            "GetCurrentProcess",
            "TerminateProcess",
        ]
        assert [c["arguments"] for c in calls] == [
            [0],
            [0x7F19F8],
            [],
            [case[1], 0xC0000409],
        ]
        # H=G-816. Status remains at H-4 across the zero-argument call.
        assert [c["esp_G_offset"] for c in calls] == [-824, -824, -824, -828]
        assert result["final"]["eax"] == case[2]
        assert result["final_ecx"] == 0xC0000003 and result["final_edx"] == 0xD0000003
        assert len(result["trace_rvas"]) == 19
        assert result["trace_rvas"][-3:] == ["0x00379e5f", "0x00379e61", "0x00379e62"]


def test_protected_words_and_callee_cleanup_are_explicit():
    summary = helper.call_summary_spec()
    assert summary["protected_memory_G_intervals"] == [[-816, -804], [0, 8], [816, 824]]
    assert summary["get_current_process_additional_protected_G_interval"] == [
        -820,
        -816,
    ]
    assert [c["argument_bytes"] for c in summary["imports"]] == [4, 4, 0, 8]
    assert [c["return_stack_increment"] for c in summary["imports"]] == [8, 8, 4, 12]
    assert "earlier query" in summary["outer_words"]


@pytest.fixture(scope="module")
def chain():
    suffixes = {
        "dispatch": "native_assertion_helper_failure_dispatch",
        "frontier": "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary",
        "tail": "native_assertion_helper_return_tail",
        "program_facts": "program_facts",
        "evidence": "native_assertion_helper_failure_return",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffixes.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, {k: data[k] for k in helper.SOURCE_PINS}, data["evidence"]


def test_sealed_receipt(chain):
    paths, sources, evidence = chain
    assert (
        hashlib.sha256(paths["evidence"].read_bytes()).hexdigest()
        == "b3c17b81879e71274072ca47e94efa454ab1a5690cd0134152593429e356cca4"
    )
    assert evidence["summary"] == dict(
        wrapper_nodes=12,
        parent_tail_nodes=4,
        owner_continuation_nodes=3,
        decoded_bytes=53,
        model_cases=192,
        actual_import_executions=0,
    )
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert helper.encode_return(evidence).encode() == paths["evidence"].read_bytes()
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )


@pytest.mark.parametrize("site,value", [(0x357B45, 1), (0x357B56, 0)])
def test_wrong_import_argument_is_rejected(site, value):
    actions = dict(helper.OPS)
    actions[site] = ("push", ("imm", value))
    with pytest.raises(helper.FailureReturnError, match="argument transfer"):
        helper.model_case((0, 0, 0, 0), actions)


def test_outer_word_protection_is_required(monkeypatch):
    summary = helper.call_summary_spec()
    summary["protected_memory_G_intervals"] = [[-816, -804], [0, 8]]
    monkeypatch.setattr(helper, "call_summary_spec", lambda: summary)
    # Once forgotten, an outer word cannot be recovered from stale model memory.
    with pytest.raises(KeyError):
        helper.model_case((0, 0, 0, 0))


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("raw_bytes", "private"),
        ("scope", {}),
        ("summary", {}),
    ],
)
def test_receipt_mutation_rejected(chain, key, value):
    _, sources, evidence = chain
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.FailureReturnError):
        helper.validate_structure(changed, sources)


def test_exact_pe_and_binary_cli_build(chain):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE for return-chain rebuild")
    paths, sources, _ = chain
    args = ["build", "--executable", executable]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_assertion_helper_failure_return.py"),
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["evidence"].read_bytes()
