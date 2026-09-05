"""Independent conditional import-argument and calling-convention checks."""

from __future__ import annotations
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from src.observatory import native_assertion_helper_import_arguments as helper
from scripts import itb_native_assertion_helper_import_arguments as cli

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.fixture(scope="module")
def chain():
    suffixes = {
        "pair": "native_assertion_helper_descendant_pair",
        "program_facts": "program_facts",
        "handoff": "native_assertion_helper_import_handoff",
        "layout": "windows_exception_layout",
        "evidence": "native_assertion_helper_import_arguments",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffixes.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, {k: data[k] for k in helper.SOURCE_PINS}, data["evidence"]


def test_conditional_transfer_and_callee_cleanup():
    result = helper.symbolic_transfer(helper.operation_spec())
    frame = lambda n: {"kind": "frame_relative", "offset": n}
    unknown = lambda name: {"kind": "opaque_u32", "name": name}
    assert result["entry_esp_offset"] == -812
    first, second = result["call_frames"]
    assert first == {
        "call_index": 0,
        "pre_call_esp_offset": -812,
        "callee_entry_esp_offset": -816,
        "return_esp_offset": -812,
        "arguments": [],
    }
    assert second == {
        "call_index": 1,
        "pre_call_esp_offset": -816,
        "callee_entry_esp_offset": -820,
        "return_esp_offset": -812,
        "arguments": [{"kind": "u32_constant", "value": 0}],
    }
    assert result["final_registers"] == {
        "eax": frame(-808),
        "esp": frame(-816),
        "ebp": frame(0),
        "edi": unknown("call_0_eax"),
        "ebx": unknown("entry_ebx"),
        "esi": unknown("entry_esi"),
        "ecx": unknown("call_1_ecx"),
        "edx": unknown("call_1_edx"),
        "eflags": unknown("call_1_eflags"),
    }
    assert result["final_known_outgoing_words"] == [
        {"frame_offset": -816, "width": 4, "value": frame(-808)}
    ]
    assert result["unexecuted_call_argument"] == {
        "call_rva": "0x00379e37",
        "iat_slot_rva": "0x003d6018",
        "import_name": "UnhandledExceptionFilter",
        "argument_index": 0,
        "at_pre_call_esp_offset": 0,
        "value": frame(-808),
        "callee_entry_argument_offset_if_call_occurs": 4,
    }
    assert result["preserved_frame_regions"] == [[-808, -800], [-800, -720], [-720, -4]]


@pytest.mark.parametrize(
    "index,key,value",
    [
        (0, "normal_return_assumed", False),
        (1, "callee_argument_cleanup_bytes", 0),
        (1, "callee_argument_cleanup_bytes", 8),
        (0, "preserved_registers", ["ebx", "esi", "ebp"]),
        (1, "caller_owned_memory_preserved_from_frame_offset", -800),
        (0, "argument_bytes", False),
    ],
)
def test_changed_external_premise_is_not_silently_accepted(index, key, value):
    assumptions = helper.call_summary_spec()
    assumptions[index][key] = value
    with pytest.raises(helper.ArgumentError):
        helper.symbolic_transfer(helper.operation_spec(), assumptions)


@pytest.mark.parametrize(
    "index,key,value",
    [
        (1, "value", {"kind": "u32_constant", "value": 1}),
        (2, "source", "ecx"),
        (4, "offset", -800),
        (5, "source", "edi"),
        (0, "call_index", False),
    ],
)
def test_changed_instruction_transfer_rejected(index, key, value):
    operations = helper.operation_spec()
    operations[index][key] = value
    with pytest.raises(helper.ArgumentError):
        helper.symbolic_transfer(operations)


def test_sealed_receipt(chain):
    paths, sources, evidence = chain
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert (
        helper.SEALED_SHA256
        == "a5db0b615b94a1291132a500fd025a74aeb4b0f8b78409f5d91bb30a6d4e282f"
    )
    assert (
        hashlib.sha256(paths["evidence"].read_bytes()).hexdigest()
        == "0c37b9bd564224d0d2593a3b9d9b573aadbf42e847b40587fada7a188c6c6933"
    )
    assert evidence["summary"] == {
        "abstract_import_calls": 2,
        "argument_frame_offset": -808,
        "bytes": 23,
        "explicit_caller_stack_writes": 2,
        "final_esp_offset": -816,
        "instructions": 6,
        "unexecuted_import_boundaries": 1,
    }
    assert evidence["operations"] == helper.operation_spec()
    assert evidence["symbolic_transfer"] == helper.argument_transfer_spec()
    assert len(evidence["import_joins"]) == 3
    assert helper.encode_arguments(evidence).encode() == paths["evidence"].read_bytes()
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )


@pytest.mark.parametrize("source", ["pair", "program_facts", "handoff", "layout"])
def test_changed_source_rejected(chain, source):
    _, sources, evidence = chain
    changed = dict(sources)
    changed[source] = dict(sources[source], unexpected=True)
    with pytest.raises(helper.ArgumentError):
        helper.validate_structure(evidence, changed)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("scope", {}),
        ("raw_bytes", "private"),
        ("source_receipts", {}),
        ("summary", {}),
    ],
)
def test_changed_receipt_rejected(chain, key, value):
    _, sources, evidence = chain
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.ArgumentError):
        helper.validate_structure(changed, sources)


def arguments(chain, command):
    paths, sources, _ = chain
    result = [command, "--evidence", str(paths["evidence"])]
    for key in sources:
        result += ["--" + key.replace("_", "-"), str(paths[key])]
    return result


def test_pe_free_structure(chain, monkeypatch, capsys):
    def forbidden(*a):
        raise AssertionError("structure check opened PE")

    monkeypatch.setattr(helper, "_load_executable", forbidden)
    assert cli.main(arguments(chain, "verify-structure")) == 0
    result = capsys.readouterr()
    assert (
        result.err == "" and json.loads(result.out)["status"] == "structurally_verified"
    )


def test_exact_pe_rebuild(chain):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE to recheck the exact import argument witnesses")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_assertion_helper_import_arguments.py"),
            *arguments(chain, "verify"),
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
