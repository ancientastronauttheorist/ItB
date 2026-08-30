"""Tests for the normalized whole-program Ghidra function atlas."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import itb_program_facts  # noqa: E402

from src.observatory.program_facts import (  # noqa: E402
    ProgramFactsError,
    build_program_facts,
    encode_program_facts,
    validate_program_facts,
)


def _synthetic_pe() -> bytes:
    data = bytearray(0x600)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into(
        "<HHIIIHH",
        data,
        0x84,
        0x014C,
        1,
        0x12345678,
        0,
        0,
        0xE0,
        0x010F,
    )
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x10B)
    struct.pack_into("<I", data, optional + 16, 0x1000)
    struct.pack_into("<I", data, optional + 28, 0x400000)
    struct.pack_into("<I", data, optional + 32, 0x1000)
    struct.pack_into("<I", data, optional + 36, 0x200)
    struct.pack_into("<I", data, optional + 56, 0x2000)
    struct.pack_into("<I", data, optional + 60, 0x200)
    struct.pack_into("<I", data, optional + 92, 16)
    section = optional + 0xE0
    data[section : section + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, section + 8, 0x400, 0x1000, 0x400, 0x200)
    struct.pack_into("<I", data, section + 36, 0x60000020)
    data[0x220:0x224] = b"\xe8\x0b\x00\x00"
    data[0x230:0x232] = b"\x90\xc3"
    return bytes(data)


def _inventory(data: bytes) -> dict:
    return {
        "platform": "windows",
        "label": "synthetic full-decompile test",
        "executable": {
            "path": "Breach.exe",
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "format": "pe",
            "architecture": "x86",
        },
        "steam": {
            "build_id": "123",
            "installed_depots": [{"depot_id": "590381", "manifest": "456"}],
            "evidence": {"sha256": "d" * 64},
        },
        "content": {
            "scripts": {"revision_sha256": "a" * 64},
            "maps": {"revision_sha256": "b" * 64},
        },
        "native_libraries": [],
    }


def _facts(data: bytes) -> str:
    first = hashlib.sha256(data[0x220:0x224]).hexdigest()
    second = hashlib.sha256(data[0x230:0x232]).hexdigest()
    return "\n".join(
        [
            "meta\tformat_version\t1",
            "meta\tghidra_version\t12.1.3",
            "meta\tprogram_name\tBreach.exe",
            "meta\tlanguage_id\tx86:LE:32:default",
            "meta\tcompiler_spec_id\twindows",
            "meta\timage_base\t0x00400000",
            "meta\tfunction_count\t2",
            "meta\trange_count\t2",
            "meta\tdirect_internal_call_count\t1",
            "meta\tomitted_call_target_count\t3",
            f"function\t0x00001020\tFUN_00401020\tGlobal\tDEFAULT\t0\t4\t{first}",
            f"function\t0x00001030\tnamed_target\tGlobal\tUSER_DEFINED\t0\t2\t{second}",
            "range\t0x00001020\t0x00001020\t4",
            "range\t0x00001030\t0x00001030\t2",
            "call\t0x00001020\t0x00001020\t0x00001030\t0x00001030\tGlobal::named_target",
            "",
        ]
    )


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path, bytes]:
    data = _synthetic_pe()
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(data)
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps(_inventory(data)), encoding="utf-8")
    facts = tmp_path / "program.tsv"
    facts.write_text(_facts(data), encoding="utf-8", newline="\n")
    return executable, inventory, facts, data


def test_builds_deterministic_normalized_program_facts(tmp_path: Path):
    executable, inventory_path, facts, data = _write_inputs(tmp_path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))

    result = build_program_facts(executable, facts, inventory=inventory)

    assert result["analysis_kind"] == "pe_ghidra_program_facts"
    assert result["identity"]["executable_sha256"] == hashlib.sha256(data).hexdigest()
    assert [item["entry_rva"] for item in result["functions"]] == [
        "0x00001020",
        "0x00001030",
    ]
    assert result["ghidra_declared_direct_calls"] == [
        {
            "source_entry_rva": "0x00001020",
            "instruction_rva": "0x00001020",
            "target_rva": "0x00001030",
            "target_entry_rva": "0x00001030",
            "target_name": "Global::named_target",
        }
    ]
    assert result["summary"] == {
        "function_count": 2,
        "body_range_count": 2,
        "ghidra_declared_direct_internal_call_count": 1,
        "omitted_call_target_count": 3,
        "function_body_bytes": 6,
        "unique_function_body_bytes": 6,
        "executable_file_bytes": 1024,
        "ghidra_function_discovery_coverage_basis_points": 58,
    }
    assert encode_program_facts(result) == encode_program_facts(
        build_program_facts(executable, facts, inventory=inventory)
    )
    assert str(tmp_path) not in encode_program_facts(result)


def test_verifies_every_range_against_exact_executable(tmp_path: Path):
    executable, inventory_path, facts, _data = _write_inputs(tmp_path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    evidence = build_program_facts(executable, facts, inventory=inventory)

    verification = validate_program_facts(
        executable, evidence, inventory=inventory
    )

    assert verification["status"] == "verified"
    assert verification["summary"] == evidence["summary"]
    assert len(verification["evidence_sha256"]) == 64


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda value: value["functions"][0].update(body_size=5), "body size"),
        (
            lambda value: value["functions"][0].update(body_sha256="0" * 64),
            "SHA-256",
        ),
        (
            lambda value: value["ghidra_declared_direct_calls"][0].update(
                instruction_rva="0x00001025"
            ),
            "outside its source body",
        ),
        (
            lambda value: value["summary"].update(function_count=999),
            "summary function_count",
        ),
    ],
)
def test_verifier_rejects_drift(tmp_path: Path, mutation, message: str):
    executable, inventory_path, facts, _data = _write_inputs(tmp_path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    evidence = build_program_facts(executable, facts, inventory=inventory)
    mutation(evidence)

    with pytest.raises(ProgramFactsError, match=message):
        validate_program_facts(executable, evidence, inventory=inventory)


def test_builder_rejects_unknown_rows_and_metadata_count_drift(tmp_path: Path):
    executable, inventory_path, facts, _data = _write_inputs(tmp_path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    facts.write_text(
        facts.read_text(encoding="utf-8") + "mystery\tvalue\n",
        encoding="utf-8",
    )
    with pytest.raises(ProgramFactsError, match="unsupported row kind"):
        build_program_facts(executable, facts, inventory=inventory)

    facts.write_text(
        _facts(_synthetic_pe()).replace("function_count\t2", "function_count\t3"),
        encoding="utf-8",
    )
    with pytest.raises(ProgramFactsError, match="function_count disagrees"):
        build_program_facts(executable, facts, inventory=inventory)


def test_verifier_rejects_declared_target_identity_drift(tmp_path: Path):
    executable, inventory_path, facts, _data = _write_inputs(tmp_path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    evidence = build_program_facts(executable, facts, inventory=inventory)

    evidence["ghidra_declared_direct_calls"][0]["target_rva"] = "0x00001020"
    with pytest.raises(ProgramFactsError, match="outside its declared target"):
        validate_program_facts(executable, evidence, inventory=inventory)

    evidence = build_program_facts(executable, facts, inventory=inventory)
    evidence["ghidra_declared_direct_calls"][0]["target_name"] = "wrong_name"
    with pytest.raises(ProgramFactsError, match="target name disagrees"):
        validate_program_facts(executable, evidence, inventory=inventory)


def test_cli_build_and_verify_round_trip(tmp_path: Path, capsys):
    executable, inventory, facts, _data = _write_inputs(tmp_path)

    assert (
        itb_program_facts.main(
            [
                "build",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory),
                "--ghidra-facts",
                str(facts),
            ]
        )
        == 0
    )
    evidence = tmp_path / "evidence.json"
    evidence.write_text(capsys.readouterr().out, encoding="utf-8")

    assert (
        itb_program_facts.main(
            [
                "verify",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory),
                "--evidence",
                str(evidence),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "verified"


def test_cli_rejects_oversized_json_before_parsing(
    tmp_path: Path, capsys, monkeypatch
):
    executable, inventory, facts, _data = _write_inputs(tmp_path)
    monkeypatch.setattr(itb_program_facts, "_MAX_JSON_BYTES", 8)

    assert (
        itb_program_facts.main(
            [
                "build",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory),
                "--ghidra-facts",
                str(facts),
            ]
        )
        == 2
    )
    assert "inventory exceeds the JSON size limit" in capsys.readouterr().err


def test_output_guard_rejects_oversized_existing_json(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(itb_program_facts, "_OUTPUT_ROOT", tmp_path)
    monkeypatch.setattr(itb_program_facts, "_MAX_JSON_BYTES", 8)
    destination = tmp_path / "atlas.json"
    destination.write_text(
        json.dumps({"analysis_kind": "pe_ghidra_program_facts"}),
        encoding="utf-8",
    )

    with pytest.raises(
        ProgramFactsError, match="existing non-program-facts artifact"
    ):
        itb_program_facts._write_evidence_atomically(destination, "{}\n")


def test_ghidra_exporter_never_emits_decompiler_or_instruction_text():
    source = (
        _REPO_ROOT / "scripts" / "ghidra" / "ExportItbProgramFacts.java"
    ).read_text(encoding="utf-8")
    assert "getFunctions(true)" in source
    assert "bodySha256" in source
    assert "getInstructions" in source
    assert "DecompInterface" not in source
    assert "getDefaultOperandRepresentation" not in source
