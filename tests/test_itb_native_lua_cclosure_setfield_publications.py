"""Focused proofs for exact native Lua C-closure setfield publications."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import struct
from pathlib import Path

import pytest

from scripts import itb_native_lua_cclosure_setfield_publications
from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_callbacks import (
    build_native_lua_cclosure_callback_census,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    ANALYSIS_KIND,
    PUBLICATION_FORM,
    NativeLuaCClosurePublicationError,
    build_native_lua_cclosure_setfield_publication_census,
    encode_native_lua_cclosure_setfield_publication_census,
    validate_native_lua_cclosure_setfield_publication_census,
)
from src.observatory.native_lua_direct_calls import (
    build_native_lua_direct_call_census,
)
from src.observatory.program_facts import build_program_facts


_IMAGE_BASE = 0x00400000
_CALLER_RVA = 0x00001020
_CALLBACK_RVA = 0x00001080
_KEY_RVA = 0x00001200
_PUSHCLOSURE_IAT_RVA = 0x000011C0
_SETFIELD_IAT_RVA = 0x000011C4
_REPO_ROOT = Path(__file__).resolve().parents[1]
_COMMITTED_RAW_SHA256 = (
    "4f4b8a6bd5dbcdaf116e215d38a0c2784b10d731d02d1300c11796045ea4cd5f"
)
_COMMITTED_CANONICAL_SHA256 = (
    "b9a77c1e5e37f251f44b4c1fac304ddbea5251c1cad164e0538c4970417608a6"
)


def _publication_code(
    *,
    upvalue_count: int = 0,
    cleanup: bytes = b"\x83\xc4\x0c",
    callback_state_push: bytes = b"\x50",
    publication_state_push: bytes = b"\x50",
    key_va: int = _IMAGE_BASE + _KEY_RVA,
) -> bytes:
    if not 0 <= upvalue_count <= 127:
        raise ValueError("synthetic upvalue count must fit push imm8")
    return (
        b"\x6a"
        + bytes([upvalue_count])
        + b"\x68"
        + struct.pack("<I", _IMAGE_BASE + _CALLBACK_RVA)
        + callback_state_push
        + b"\xff\x15"
        + struct.pack("<I", _IMAGE_BASE + _PUSHCLOSURE_IAT_RVA)
        + cleanup
        + b"\x68"
        + struct.pack("<I", key_va)
        + b"\x6a\xfe"
        + publication_state_push
        + b"\xff\x15"
        + struct.pack("<I", _IMAGE_BASE + _SETFIELD_IAT_RVA)
        + b"\xc3"
    )


def _synthetic_pe(code: bytes, *, key: bytes = b"__gc\0") -> bytes:
    data = bytearray(0xC00)
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
    struct.pack_into("<I", data, optional + 16, _CALLER_RVA)
    struct.pack_into("<I", data, optional + 28, _IMAGE_BASE)
    struct.pack_into("<I", data, optional + 32, 0x1000)
    struct.pack_into("<I", data, optional + 36, 0x200)
    struct.pack_into("<I", data, optional + 56, 0x2000)
    struct.pack_into("<I", data, optional + 60, 0x200)
    struct.pack_into("<I", data, optional + 92, 16)
    struct.pack_into("<II", data, optional + 96 + 8, 0x1100, 40)
    section = optional + 0xE0
    data[section : section + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, section + 8, 0xA00, 0x1000, 0xA00, 0x200)
    struct.pack_into("<I", data, section + 36, 0x60000020)

    data[0x220 : 0x220 + len(code)] = code
    data[0x280:0x283] = b"\x31\xc0\xc3"
    data[0x400 : 0x400 + len(key)] = key
    struct.pack_into(
        "<IIIII", data, 0x300, 0x11B0, 0, 0, 0x1140, _PUSHCLOSURE_IAT_RVA
    )
    data[0x340:0x34B] = b"lua5.1.dll\0"
    struct.pack_into("<H", data, 0x360, 7)
    data[0x362:0x373] = b"lua_pushcclosure\0"
    struct.pack_into("<H", data, 0x378, 8)
    data[0x37A:0x387] = b"lua_setfield\0"
    struct.pack_into("<III", data, 0x3B0, 0x1160, 0x1178, 0)
    struct.pack_into("<III", data, 0x3C0, 0x1160, 0x1178, 0)
    return bytes(data)


def _inventory(data: bytes) -> dict:
    return {
        "platform": "windows",
        "label": "synthetic closure publication test",
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
        "native_libraries": [
            {
                "path": "lua5.1.dll",
                "size": 7,
                "sha256": "c" * 64,
                "format": "pe",
                "architecture": "x86",
            }
        ],
    }


def _facts(data: bytes, code_size: int) -> str:
    caller_hash = hashlib.sha256(data[0x220 : 0x220 + code_size]).hexdigest()
    callback_hash = hashlib.sha256(data[0x280:0x283]).hexdigest()
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
            "meta\tdirect_internal_call_count\t0",
            "meta\tomitted_call_target_count\t2",
            (
                "function\t0x00001020\tcaller\tGlobal\tUSER_DEFINED\t0\t"
                f"{code_size}\t{caller_hash}"
            ),
            (
                "function\t0x00001080\tcallback\tGlobal\tUSER_DEFINED\t0\t"
                f"3\t{callback_hash}"
            ),
            f"range\t0x00001020\t0x00001020\t{code_size}",
            "range\t0x00001080\t0x00001080\t3",
            "",
        ]
    )


def _write_inputs(
    tmp_path: Path,
    *,
    code: bytes | None = None,
    key: bytes = b"__gc\0",
) -> tuple[Path, dict, dict, dict, dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    code = _publication_code() if code is None else code
    data = _synthetic_pe(code, key=key)
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(data)
    inventory = _inventory(data)
    facts_path = tmp_path / "facts.tsv"
    facts_path.write_text(
        _facts(data, len(code)), encoding="utf-8", newline="\n"
    )
    program_facts = build_program_facts(
        executable, facts_path, inventory=inventory
    )
    direct_calls = build_native_lua_direct_call_census(
        executable, program_facts, inventory=inventory
    )
    callbacks = build_native_lua_cclosure_callback_census(
        executable, direct_calls, program_facts, inventory=inventory
    )
    return executable, inventory, program_facts, direct_calls, callbacks


def _build(
    executable: Path,
    inventory: dict,
    program_facts: dict,
    direct_calls: dict,
    callbacks: dict,
) -> dict:
    return build_native_lua_cclosure_setfield_publication_census(
        executable,
        direct_calls,
        callbacks,
        program_facts,
        inventory=inventory,
    )


def test_builds_exact_setfield_publication_without_publishing_code_bytes(
    tmp_path: Path,
):
    inputs = _write_inputs(tmp_path)
    result = _build(*inputs)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["summary"] == {
        "resolved_immediate_callback_sites": 1,
        "matched_setfield_publication_sites": 1,
        "unmatched_resolved_callback_sites": 0,
        "unique_registered_callback_targets": 1,
        "unique_registration_builders": 1,
        "unique_key_texts": 1,
        "schema_violations": 0,
    }
    publication = result["publications"][0]
    assert publication["publication_form"] == PUBLICATION_FORM
    assert publication["caller_entry_rva"] == "0x00001020"
    assert publication["callback_call_rva"] == "0x00001028"
    assert publication["callback_entry_rva"] == "0x00001080"
    assert publication["setter_call_rva"] == "0x00001039"
    assert publication["key_rva"] == "0x00001200"
    assert publication["key_text"] == "__gc"
    assert publication["key_byte_length"] == 4
    assert publication["table_index"] == -2
    assert result["unmatched_resolved_sites"] == []
    assert result["builders"] == [
        {
            "builder_entry_rva": "0x00001020",
            "builder_atlas_record_sha256": atlas_record_sha256(
                inputs[2]["functions"][0]
            ),
            "publication_site_count": 1,
            "registered_callback_entry_rvas": ["0x00001080"],
            "key_texts": ["__gc"],
        }
    ]
    rendered = encode_native_lua_cclosure_setfield_publication_census(result)
    assert "ff15c0114000" not in rendered
    assert "instruction_bytes" not in rendered
    assert "mnemonic" not in rendered
    assert re.search(r"[A-Za-z]:[\\/]", rendered) is None


@pytest.mark.parametrize(
    "code",
    [
        _publication_code(cleanup=b"\x83\xc4\x08"),
        _publication_code(publication_state_push=b"\x51"),
        _publication_code(upvalue_count=1),
    ],
)
def test_nonmatching_fallthrough_forms_remain_explicitly_unmatched(
    tmp_path: Path,
    code: bytes,
):
    inputs = _write_inputs(tmp_path, code=code)
    result = _build(*inputs)

    assert result["publications"] == []
    assert result["builders"] == []
    assert result["registered_targets"] == []
    assert result["summary"]["matched_setfield_publication_sites"] == 0
    assert result["summary"]["unmatched_resolved_callback_sites"] == 1
    assert result["unmatched_resolved_sites"][0]["callback_call_rva"] == (
        "0x00001028"
    )


def test_matching_form_rejects_unmapped_or_unterminated_key(tmp_path: Path):
    unmapped = _write_inputs(
        tmp_path / "unmapped",
        code=_publication_code(key_va=_IMAGE_BASE + 0x1FFF),
    )
    with pytest.raises(
        NativeLuaCClosurePublicationError, match="file-backed string"
    ):
        _build(*unmapped)

    unterminated = _write_inputs(
        tmp_path / "unterminated",
        key=b"x" * 129,
    )
    with pytest.raises(
        NativeLuaCClosurePublicationError, match="publication limit"
    ):
        _build(*unterminated)


def test_exact_validator_rejects_any_evidence_or_binary_drift(tmp_path: Path):
    inputs = _write_inputs(tmp_path)
    result = _build(*inputs)

    verification = validate_native_lua_cclosure_setfield_publication_census(
        inputs[0],
        result,
        inputs[3],
        inputs[4],
        inputs[2],
        inventory=inputs[1],
    )
    assert verification["status"] == "verified"
    assert verification["summary"] == result["summary"]

    altered = copy.deepcopy(result)
    altered["publications"][0]["key_text"] = "__index"
    with pytest.raises(
        NativeLuaCClosurePublicationError, match="differs from exact rebuild"
    ):
        validate_native_lua_cclosure_setfield_publication_census(
            inputs[0],
            altered,
            inputs[3],
            inputs[4],
            inputs[2],
            inventory=inputs[1],
        )

    data = bytearray(inputs[0].read_bytes())
    data[0x500] ^= 1
    inputs[0].write_bytes(data)
    with pytest.raises(
        NativeLuaCClosurePublicationError, match="prerequisite failed"
    ):
        validate_native_lua_cclosure_setfield_publication_census(
            inputs[0],
            result,
            inputs[3],
            inputs[4],
            inputs[2],
            inventory=inputs[1],
        )


def test_callback_prerequisite_drift_fails_closed(tmp_path: Path):
    inputs = _write_inputs(tmp_path)
    callbacks = copy.deepcopy(inputs[4])
    callbacks["resolved_sites"][0]["callback_entry_rva"] = "0x00001081"
    with pytest.raises(
        NativeLuaCClosurePublicationError, match="prerequisite failed"
    ):
        _build(inputs[0], inputs[1], inputs[2], inputs[3], callbacks)


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def test_cli_build_and_verify_round_trip(tmp_path: Path, capsys):
    inputs = _write_inputs(tmp_path)
    inventory_path = tmp_path / "inventory.json"
    program_path = tmp_path / "program.json"
    direct_path = tmp_path / "direct.json"
    callbacks_path = tmp_path / "callbacks.json"
    evidence_path = tmp_path / "evidence.json"
    for path, value in (
        (inventory_path, inputs[1]),
        (program_path, inputs[2]),
        (direct_path, inputs[3]),
        (callbacks_path, inputs[4]),
    ):
        _write_json(path, value)

    common = [
        "--executable",
        str(inputs[0]),
        "--inventory",
        str(inventory_path),
        "--program-facts",
        str(program_path),
        "--direct-calls",
        str(direct_path),
        "--callbacks",
        str(callbacks_path),
    ]
    assert (
        itb_native_lua_cclosure_setfield_publications.main(["build", *common])
        == 0
    )
    artifact = json.loads(capsys.readouterr().out)
    evidence_path.write_text(
        encode_native_lua_cclosure_setfield_publication_census(artifact),
        encoding="utf-8",
        newline="\n",
    )
    assert (
        itb_native_lua_cclosure_setfield_publications.main(
            ["verify", *common, "--evidence", str(evidence_path)]
        )
        == 0
    )
    verified = json.loads(capsys.readouterr().out)
    assert verified["status"] == "verified"
    assert verified["summary"] == artifact["summary"]


def test_committed_setfield_publication_census_identity_and_partition():
    path = (
        _REPO_ROOT
        / "data/observatory/programs"
        / (
            "windows_build_13725832_31fe35265598_"
            "native_lua_cclosure_setfield_publications.json"
        )
    )
    payload = path.read_bytes()
    artifact = json.loads(payload)
    canonical = (
        json.dumps(
            artifact,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    assert hashlib.sha256(payload).hexdigest() == _COMMITTED_RAW_SHA256
    assert hashlib.sha256(canonical).hexdigest() == _COMMITTED_CANONICAL_SHA256
    assert artifact["build_identity"]["build_id"] == "13725832"
    assert artifact["summary"] == {
        "resolved_immediate_callback_sites": 13,
        "matched_setfield_publication_sites": 3,
        "unmatched_resolved_callback_sites": 10,
        "unique_registered_callback_targets": 3,
        "unique_registration_builders": 1,
        "unique_key_texts": 1,
        "schema_violations": 0,
    }
    assert [item["callback_call_rva"] for item in artifact["publications"]] == [
        "0x002e6a8c",
        "0x002e6af9",
        "0x002e6b66",
    ]
    assert [item["setter_call_rva"] for item in artifact["publications"]] == [
        "0x002e6a9d",
        "0x002e6b0a",
        "0x002e6b77",
    ]
    assert [item["callback_entry_rva"] for item in artifact["publications"]] == [
        "0x002e6840",
        "0x002e6880",
        "0x002e68b0",
    ]
    assert {item["key_text"] for item in artifact["publications"]} == {"__gc"}
    assert len(artifact["unmatched_resolved_sites"]) == 10
    assert artifact["builders"][0]["builder_entry_rva"] == "0x002e6900"
    assert len(artifact["registered_targets"]) == 3
    assert re.search(rb"[A-Za-z]:[\\/]", payload) is None
    forbidden = {
        "bytes",
        "decompiler",
        "disassembly",
        "instruction_bytes",
        "mnemonic",
        "op_str",
        "pseudocode",
    }

    def walk(value):
        if isinstance(value, dict):
            assert forbidden.isdisjoint(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(artifact)
