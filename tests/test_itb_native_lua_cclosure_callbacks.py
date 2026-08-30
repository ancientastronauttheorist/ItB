"""Focused proofs for exact native Lua C-closure callback arguments."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import struct
from pathlib import Path

import pytest

from scripts import itb_native_lua_cclosure_callbacks
import src.observatory.native_lua_cclosure_callbacks as cclosure_callbacks
from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_callbacks import (
    ANALYSIS_KIND,
    CALLBACK_ARGUMENT_FORM,
    NativeLuaCClosureError,
    build_native_lua_cclosure_callback_census,
    encode_native_lua_cclosure_callback_census,
    validate_native_lua_cclosure_callback_census,
    validate_native_lua_cclosure_callback_structure,
)
from src.observatory.native_lua_direct_calls import (
    build_native_lua_direct_call_census,
)
from src.observatory.program_facts import build_program_facts


_IMAGE_BASE = 0x00400000
_IAT_RVA = 0x00001190
_CALLBACK_RVA = 0x00001040
_REPO_ROOT = Path(__file__).resolve().parents[1]
_COMMITTED_RAW_SHA256 = (
    "9cb573f3cf5831a93c53ee0d673666d853c7e2515eb5d2f24546099f59154579"
)
_COMMITTED_CANONICAL_SHA256 = (
    "cb594d7662778b98549bde5f460f1c9d8d0b30f3625d44953c392b8caa50b003"
)


def _resolved_code(callback_rva: int = _CALLBACK_RVA) -> bytes:
    return (
        b"\x6a\x02"
        + b"\x68"
        + struct.pack("<I", _IMAGE_BASE + callback_rva)
        + b"\x50"
        + b"\xff\x15"
        + struct.pack("<I", _IMAGE_BASE + _IAT_RVA)
        + b"\xc3"
    )


def _synthetic_pe(code: bytes) -> bytes:
    data = bytearray(0xA00)
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
    struct.pack_into("<I", data, optional + 16, 0x1020)
    struct.pack_into("<I", data, optional + 28, _IMAGE_BASE)
    struct.pack_into("<I", data, optional + 32, 0x1000)
    struct.pack_into("<I", data, optional + 36, 0x200)
    struct.pack_into("<I", data, optional + 56, 0x2000)
    struct.pack_into("<I", data, optional + 60, 0x200)
    struct.pack_into("<I", data, optional + 92, 16)
    struct.pack_into("<II", data, optional + 96 + 8, 0x1100, 40)
    section = optional + 0xE0
    data[section : section + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, section + 8, 0x800, 0x1000, 0x800, 0x200)
    struct.pack_into("<I", data, section + 36, 0x60000020)

    data[0x220 : 0x220 + len(code)] = code
    data[0x240:0x243] = b"\x31\xc0\xc3"
    struct.pack_into("<IIIII", data, 0x300, 0x1180, 0, 0, 0x1140, _IAT_RVA)
    data[0x340:0x34B] = b"lua5.1.dll\0"
    struct.pack_into("<H", data, 0x360, 7)
    data[0x362:0x373] = b"lua_pushcclosure\0"
    struct.pack_into("<II", data, 0x380, 0x1160, 0)
    struct.pack_into("<II", data, 0x390, 0x1160, 0)
    return bytes(data)


def _inventory(data: bytes) -> dict:
    return {
        "platform": "windows",
        "label": "synthetic native Lua callback test",
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
    callback_hash = hashlib.sha256(data[0x240:0x243]).hexdigest()
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
            "meta\tomitted_call_target_count\t1",
            (
                "function\t0x00001020\tcaller\tGlobal\tUSER_DEFINED\t0\t"
                f"{code_size}\t{caller_hash}"
            ),
            (
                "function\t0x00001040\tcallback\tGlobal\tUSER_DEFINED\t0\t"
                f"3\t{callback_hash}"
            ),
            f"range\t0x00001020\t0x00001020\t{code_size}",
            "range\t0x00001040\t0x00001040\t3",
            "",
        ]
    )


def _write_inputs(
    tmp_path: Path,
    *,
    code: bytes | None = None,
) -> tuple[Path, dict, dict, dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    code = _resolved_code() if code is None else code
    data = _synthetic_pe(code)
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(data)
    inventory = _inventory(data)
    facts_path = tmp_path / "facts.tsv"
    facts_path.write_text(
        _facts(data, len(code)), encoding="utf-8", newline="\n"
    )
    program_facts = build_program_facts(
        executable,
        facts_path,
        inventory=inventory,
    )
    direct_calls = build_native_lua_direct_call_census(
        executable,
        program_facts,
        inventory=inventory,
    )
    return executable, inventory, program_facts, direct_calls


def _build(
    executable: Path,
    inventory: dict,
    program_facts: dict,
    direct_calls: dict,
) -> dict:
    return build_native_lua_cclosure_callback_census(
        executable,
        direct_calls,
        program_facts,
        inventory=inventory,
    )


def test_builds_exact_immediate_callback_edge_without_publishing_bytes(
    tmp_path: Path,
):
    executable, inventory, program_facts, direct_calls = _write_inputs(tmp_path)

    result = _build(executable, inventory, program_facts, direct_calls)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["summary"] == {
        "direct_pushcclosure_call_sites": 1,
        "resolved_immediate_callback_sites": 1,
        "unresolved_callback_sites": 0,
        "unresolved_register_callback_sites": 0,
        "unresolved_memory_callback_sites": 0,
        "unique_callback_targets": 1,
        "duplicate_callback_targets": 0,
        "self_callback_sites": 0,
        "callback_targets_with_direct_lua_import_calls": 0,
        "callback_targets_that_call_pushcclosure": 0,
        "schema_violations": 0,
    }
    site = result["resolved_sites"][0]
    assert site["caller_entry_rva"] == "0x00001020"
    assert site["call_rva"] == "0x00001028"
    assert site["callback_entry_rva"] == "0x00001040"
    assert site["argument_form"] == CALLBACK_ARGUMENT_FORM
    assert site["upvalue_argument_kind"] == "immediate"
    assert site["literal_upvalue_count"] == 2
    assert site["self_callback"] is False
    assert site["callback_atlas_record_sha256"] == atlas_record_sha256(
        program_facts["functions"][1]
    )
    assert result["unresolved_sites"] == []
    rendered = encode_native_lua_cclosure_callback_census(result)
    assert "6840104000" not in rendered
    assert "call dword" not in rendered
    assert "instruction_bytes" not in rendered
    assert re.search(r"[A-Za-z]:[\\/]", rendered) is None
    verification = validate_native_lua_cclosure_callback_census(
        executable,
        result,
        direct_calls,
        program_facts,
        inventory=inventory,
    )
    assert verification["status"] == "verified"


@pytest.mark.parametrize(
    ("callback_push", "kind"),
    [(b"\x53", "register"), (b"\xff\x70\x04", "memory")],
)
def test_register_and_memory_callbacks_remain_unresolved(
    tmp_path: Path,
    callback_push: bytes,
    kind: str,
):
    code = (
        b"\x6a\x02"
        + callback_push
        + b"\x50"
        + b"\xff\x15"
        + struct.pack("<I", _IMAGE_BASE + _IAT_RVA)
        + b"\xc3"
    )
    executable, inventory, program_facts, direct_calls = _write_inputs(
        tmp_path, code=code
    )

    result = _build(executable, inventory, program_facts, direct_calls)

    assert result["resolved_sites"] == []
    assert result["summary"]["unresolved_callback_sites"] == 1
    assert result["unresolved_sites"][0]["callback_argument_kind"] == kind


def test_interleaved_immediate_argument_setup_fails_closed(tmp_path: Path):
    code = (
        b"\x6a\x02"
        + b"\x68"
        + struct.pack("<I", _IMAGE_BASE + _CALLBACK_RVA)
        + b"\x90\x50"
        + b"\xff\x15"
        + struct.pack("<I", _IMAGE_BASE + _IAT_RVA)
        + b"\xc3"
    )
    executable, inventory, program_facts, direct_calls = _write_inputs(
        tmp_path, code=code
    )

    with pytest.raises(NativeLuaCClosureError, match="unsupported"):
        _build(executable, inventory, program_facts, direct_calls)


def test_immediate_callback_must_equal_an_atlas_entry(tmp_path: Path):
    executable, inventory, program_facts, direct_calls = _write_inputs(
        tmp_path, code=_resolved_code(_CALLBACK_RVA + 1)
    )

    with pytest.raises(NativeLuaCClosureError, match="atlas entry"):
        _build(executable, inventory, program_facts, direct_calls)


def test_stale_direct_call_prerequisite_fails_closed(tmp_path: Path):
    executable, inventory, program_facts, direct_calls = _write_inputs(tmp_path)
    stale = copy.deepcopy(direct_calls)
    stale["records"][0]["direct_lua_import_calls"][0]["call_rva"] = "0x00001029"

    with pytest.raises(NativeLuaCClosureError, match="prerequisite"):
        _build(executable, inventory, program_facts, stale)


def test_executable_second_read_drift_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    executable, inventory, program_facts, direct_calls = _write_inputs(tmp_path)
    original = cclosure_callbacks.validate_native_lua_direct_call_census

    def validate_then_change(*args, **kwargs):
        verification = original(*args, **kwargs)
        changed = bytearray(executable.read_bytes())
        changed[0x250] ^= 1
        executable.write_bytes(changed)
        return verification

    monkeypatch.setattr(
        cclosure_callbacks,
        "validate_native_lua_direct_call_census",
        validate_then_change,
    )

    with pytest.raises(NativeLuaCClosureError, match="changed after"):
        _build(executable, inventory, program_facts, direct_calls)


def _write_cli_inputs(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, dict]:
    executable, inventory, program_facts, direct_calls = _write_inputs(
        tmp_path / "inputs"
    )
    inventory_path = tmp_path / "inventory.json"
    program_path = tmp_path / "program.json"
    direct_path = tmp_path / "direct.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    program_path.write_text(json.dumps(program_facts), encoding="utf-8")
    direct_path.write_text(json.dumps(direct_calls), encoding="utf-8")
    return executable, inventory_path, program_path, direct_path, inventory


def _cli_build_args(
    executable: Path,
    inventory: Path,
    program: Path,
    direct: Path,
    output: Path,
) -> list[str]:
    return [
        "build",
        "--executable",
        str(executable),
        "--inventory",
        str(inventory),
        "--program-facts",
        str(program),
        "--direct-calls",
        str(direct),
        "--output",
        str(output),
    ]


def test_cli_reuses_identical_output_and_rejects_differing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
):
    executable, inventory, program, direct, _inventory_value = _write_cli_inputs(
        tmp_path
    )
    repo = tmp_path / "repo"
    output_root = repo / "data" / "observatory" / "programs"
    output_root.mkdir(parents=True)
    output = output_root / "callbacks.json"
    monkeypatch.setattr(itb_native_lua_cclosure_callbacks, "_REPO_ROOT", repo)
    monkeypatch.setattr(
        itb_native_lua_cclosure_callbacks, "_OUTPUT_ROOT", output_root
    )
    args = _cli_build_args(executable, inventory, program, direct, output)

    assert itb_native_lua_cclosure_callbacks.main(args) == 0
    before = output.stat().st_mtime_ns
    assert itb_native_lua_cclosure_callbacks.main(args) == 0
    assert output.stat().st_mtime_ns == before
    deterministic = output.read_bytes()
    value = json.loads(deterministic)
    output.write_text(json.dumps(value), encoding="utf-8")
    reformatted = output.read_bytes()
    verify_args = [
        "verify",
        "--executable",
        str(executable),
        "--inventory",
        str(inventory),
        "--program-facts",
        str(program),
        "--direct-calls",
        str(direct),
        "--evidence",
        str(output),
    ]
    assert itb_native_lua_cclosure_callbacks.main(verify_args) == 1
    assert "deterministically encoded" in capsys.readouterr().err
    assert itb_native_lua_cclosure_callbacks.main(args) == 1
    assert "deterministically encoded" in capsys.readouterr().err
    assert output.read_bytes() == reformatted
    output.write_bytes(deterministic)
    differing = json.loads(output.read_text(encoding="utf-8"))
    differing["summary"]["schema_violations"] = 1
    output.write_text(json.dumps(differing), encoding="utf-8")
    foreign = output.read_bytes()

    assert itb_native_lua_cclosure_callbacks.main(args) == 1
    assert output.read_bytes() == foreign


def test_cli_preserves_concurrently_created_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    executable, inventory, program, direct, _inventory_value = _write_cli_inputs(
        tmp_path
    )
    repo = tmp_path / "repo"
    output_root = repo / "data" / "observatory" / "programs"
    output_root.mkdir(parents=True)
    output = output_root / "callbacks.json"
    monkeypatch.setattr(itb_native_lua_cclosure_callbacks, "_REPO_ROOT", repo)
    monkeypatch.setattr(
        itb_native_lua_cclosure_callbacks, "_OUTPUT_ROOT", output_root
    )
    original_link = itb_native_lua_cclosure_callbacks.os.link
    foreign = b"foreign concurrent output\n"

    def race_link(source, destination):
        Path(destination).write_bytes(foreign)
        return original_link(source, destination)

    monkeypatch.setattr(itb_native_lua_cclosure_callbacks.os, "link", race_link)

    assert (
        itb_native_lua_cclosure_callbacks.main(
            _cli_build_args(executable, inventory, program, direct, output)
        )
        == 1
    )
    assert output.read_bytes() == foreign


def test_committed_callback_census_identity_and_partitions():
    artifact_path = (
        _REPO_ROOT
        / "data/observatory/programs"
        / "windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json"
    )
    payload = artifact_path.read_bytes()
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
        "direct_pushcclosure_call_sites": 15,
        "resolved_immediate_callback_sites": 13,
        "unresolved_callback_sites": 2,
        "unresolved_register_callback_sites": 1,
        "unresolved_memory_callback_sites": 1,
        "unique_callback_targets": 11,
        "duplicate_callback_targets": 2,
        "self_callback_sites": 1,
        "callback_targets_with_direct_lua_import_calls": 11,
        "callback_targets_that_call_pushcclosure": 3,
        "schema_violations": 0,
    }
    assert [item["call_rva"] for item in artifact["resolved_sites"]] == sorted(
        item["call_rva"] for item in artifact["resolved_sites"]
    )
    assert [item["call_rva"] for item in artifact["unresolved_sites"]] == [
        "0x002e6545",
        "0x002ea85e",
    ]
    targets = artifact["callback_targets"]
    assert len({item["callback_entry_rva"] for item in targets}) == 11
    assert sum(item["resolved_site_count"] for item in targets) == 13
    assert all(item["also_direct_lua_import_caller"] for item in targets)
    assert [
        item["call_rva"]
        for item in artifact["resolved_sites"]
        if item["self_callback"]
    ] == ["0x002eb2a5"]
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


def test_structure_validator_accepts_complete_synthetic_and_committed_censuses(
    tmp_path: Path,
):
    executable, inventory, program_facts, direct_calls = _write_inputs(tmp_path)
    result = _build(executable, inventory, program_facts, direct_calls)

    verification = validate_native_lua_cclosure_callback_structure(
        result, direct_calls, program_facts
    )
    assert verification["status"] == "structurally_verified"
    assert verification["evidence_sha256"] == hashlib.sha256(
        cclosure_callbacks._canonical_bytes(result)
    ).hexdigest()

    root = _REPO_ROOT / "data" / "observatory" / "programs"
    committed = json.loads(
        (root / "windows_build_13725832_31fe35265598_native_lua_cclosure_callbacks.json").read_text(
            encoding="utf-8"
        )
    )
    committed_direct = json.loads(
        (root / "windows_build_13725832_31fe35265598_native_lua_direct_call_census.json").read_text(
            encoding="utf-8"
        )
    )
    committed_facts = json.loads(
        (root / "windows_build_13725832_31fe35265598_program_facts.json").read_text(
            encoding="utf-8"
        )
    )
    assert validate_native_lua_cclosure_callback_structure(
        committed, committed_direct, committed_facts
    )["status"] == "structurally_verified"


def test_structure_validator_rejects_direct_and_atlas_identity_drift(
    tmp_path: Path,
):
    executable, inventory, program_facts, direct_calls = _write_inputs(tmp_path)
    result = _build(executable, inventory, program_facts, direct_calls)

    wrong_direct = copy.deepcopy(result)
    wrong_direct["direct_call_census"]["canonical_sha256"] = "0" * 64
    with pytest.raises(NativeLuaCClosureError, match="direct-call census identity"):
        validate_native_lua_cclosure_callback_structure(
            wrong_direct, direct_calls, program_facts
        )

    wrong_atlas = copy.deepcopy(program_facts)
    wrong_atlas["functions"][1]["name"] = "not-the-reviewed-atlas"
    with pytest.raises(NativeLuaCClosureError, match="structural prerequisite"):
        validate_native_lua_cclosure_callback_structure(
            result, direct_calls, wrong_atlas
        )


def test_structure_validator_rejects_malformed_other_site_and_target(
    tmp_path: Path,
):
    executable, inventory, program_facts, direct_calls = _write_inputs(tmp_path)
    result = _build(executable, inventory, program_facts, direct_calls)

    malformed_site = copy.deepcopy(result)
    extra = copy.deepcopy(malformed_site["resolved_sites"][0])
    extra["call_rva"] = "0x00001040"
    malformed_site["resolved_sites"].append(extra)
    with pytest.raises(NativeLuaCClosureError, match="direct lua_pushcclosure"):
        validate_native_lua_cclosure_callback_structure(
            malformed_site, direct_calls, program_facts
        )

    malformed_target = copy.deepcopy(result)
    malformed_target["callback_targets"][0]["unrelated"] = True
    with pytest.raises(NativeLuaCClosureError, match="fields differ"):
        validate_native_lua_cclosure_callback_structure(
            malformed_target, direct_calls, program_facts
        )


def test_structure_validator_rejects_duplicate_order_and_partition_holes(
    tmp_path: Path,
):
    executable, inventory, program_facts, direct_calls = _write_inputs(tmp_path)
    result = _build(executable, inventory, program_facts, direct_calls)

    duplicate = copy.deepcopy(result)
    duplicate["resolved_sites"].append(copy.deepcopy(duplicate["resolved_sites"][0]))
    with pytest.raises(NativeLuaCClosureError, match="unique and call-RVA ordered"):
        validate_native_lua_cclosure_callback_structure(
            duplicate, direct_calls, program_facts
        )

    hole = copy.deepcopy(result)
    hole["resolved_sites"] = []
    with pytest.raises(NativeLuaCClosureError, match="exactly partition"):
        validate_native_lua_cclosure_callback_structure(hole, direct_calls, program_facts)

    unordered_target = copy.deepcopy(result)
    unordered_target["callback_targets"].append(
        copy.deepcopy(unordered_target["callback_targets"][0])
    )
    with pytest.raises(NativeLuaCClosureError, match="unique and callback-entry-RVA ordered"):
        validate_native_lua_cclosure_callback_structure(
            unordered_target, direct_calls, program_facts
        )


@pytest.mark.parametrize(
    ("location", "value", "message"),
    [
        (("resolved_sites", 0, "caller_entry_rva"), "0x00001040", "exact direct call"),
        (("resolved_sites", 0, "callback_atlas_record_sha256"), "0" * 64, "does not match atlas"),
        (("resolved_sites", 0, "self_callback"), True, "self_callback disagrees"),
        (("callback_targets", 0, "also_direct_lua_import_caller"), True, "do not exactly aggregate"),
    ],
)
def test_structure_validator_rejects_caller_target_hash_self_and_overlap_drift(
    tmp_path: Path,
    location: tuple[object, ...],
    value: object,
    message: str,
):
    executable, inventory, program_facts, direct_calls = _write_inputs(tmp_path)
    result = _build(executable, inventory, program_facts, direct_calls)
    tampered = copy.deepcopy(result)
    destination: object = tampered
    for key in location[:-1]:
        destination = destination[key]  # type: ignore[index]
    destination[location[-1]] = value  # type: ignore[index]

    with pytest.raises(NativeLuaCClosureError, match=message):
        validate_native_lua_cclosure_callback_structure(
            tampered, direct_calls, program_facts
        )


def test_structure_validator_rejects_sequence_and_callback_push_hash_drift(
    tmp_path: Path,
):
    executable, inventory, program_facts, direct_calls = _write_inputs(tmp_path)
    result = _build(executable, inventory, program_facts, direct_calls)

    wrong_sequence = copy.deepcopy(result)
    wrong_sequence["resolved_sites"][0]["callback_push"]["rva"] = "0x00001025"
    with pytest.raises(NativeLuaCClosureError, match="not contiguous"):
        validate_native_lua_cclosure_callback_structure(
            wrong_sequence, direct_calls, program_facts
        )

    wrong_hash = copy.deepcopy(result)
    wrong_hash["resolved_sites"][0]["callback_push"]["sha256"] = "0" * 64
    with pytest.raises(NativeLuaCClosureError, match="does not reconstruct"):
        validate_native_lua_cclosure_callback_structure(
            wrong_hash, direct_calls, program_facts
        )

    outside_caller_range = copy.deepcopy(result)
    outside_caller_range["resolved_sites"][0]["callback_push"]["rva"] = (
        "0x0000101f"
    )
    outside_caller_range["resolved_sites"][0]["callback_push"]["size"] = 8
    with pytest.raises(NativeLuaCClosureError, match="exact caller atlas range"):
        validate_native_lua_cclosure_callback_structure(
            outside_caller_range, direct_calls, program_facts
        )

    wrong_state_push = copy.deepcopy(result)
    wrong_state_push["resolved_sites"][0]["state_push"]["sha256"] = "0" * 64
    with pytest.raises(NativeLuaCClosureError, match="exact x86 register PUSH"):
        validate_native_lua_cclosure_callback_structure(
            wrong_state_push, direct_calls, program_facts
        )

    wrong_upvalue_push = copy.deepcopy(result)
    wrong_upvalue_push["resolved_sites"][0]["upvalue_push"]["sha256"] = "0" * 64
    with pytest.raises(NativeLuaCClosureError, match="literal upvalue count"):
        validate_native_lua_cclosure_callback_structure(
            wrong_upvalue_push, direct_calls, program_facts
        )


def test_structure_validator_rejects_callback_image_va_overflow(
    tmp_path: Path,
):
    executable, inventory, program_facts, direct_calls = _write_inputs(tmp_path)
    result = _build(executable, inventory, program_facts, direct_calls)
    overflow_facts = copy.deepcopy(program_facts)
    overflow_facts["functions"][1]["entry_rva"] = "0xffffffff"
    overflow_direct = copy.deepcopy(direct_calls)
    overflow_direct["atlas"]["canonical_sha256"] = (
        cclosure_callbacks._canonical_sha256(overflow_facts)
    )
    overflow_evidence = copy.deepcopy(result)
    overflow_evidence["atlas"]["canonical_sha256"] = overflow_direct["atlas"][
        "canonical_sha256"
    ]
    overflow_evidence["direct_call_census"]["canonical_sha256"] = (
        cclosure_callbacks._canonical_sha256(overflow_direct)
    )
    overflow_hash = atlas_record_sha256(overflow_facts["functions"][1])
    overflow_evidence["resolved_sites"][0]["callback_entry_rva"] = "0xffffffff"
    overflow_evidence["resolved_sites"][0]["callback_atlas_record_sha256"] = (
        overflow_hash
    )
    overflow_evidence["callback_targets"][0]["callback_entry_rva"] = "0xffffffff"
    overflow_evidence["callback_targets"][0]["callback_atlas_record_sha256"] = (
        overflow_hash
    )

    with pytest.raises(NativeLuaCClosureError, match="overflows the x86 image VA"):
        validate_native_lua_cclosure_callback_structure(
            overflow_evidence, overflow_direct, overflow_facts
        )


def test_structure_validator_rejects_unresolved_target_invention_and_kind_drift(
    tmp_path: Path,
):
    code = b"\x6a\x02\x53\x50\xff\x15" + struct.pack(
        "<I", _IMAGE_BASE + _IAT_RVA
    ) + b"\xc3"
    executable, inventory, program_facts, direct_calls = _write_inputs(
        tmp_path, code=code
    )
    result = _build(executable, inventory, program_facts, direct_calls)

    invention = copy.deepcopy(result)
    invention["unresolved_sites"][0]["callback_entry_rva"] = "0x00001040"
    with pytest.raises(NativeLuaCClosureError, match="fields differ"):
        validate_native_lua_cclosure_callback_structure(
            invention, direct_calls, program_facts
        )

    unsupported = copy.deepcopy(result)
    unsupported["unresolved_sites"][0]["callback_argument_kind"] = "immediate"
    with pytest.raises(NativeLuaCClosureError, match="unsupported"):
        validate_native_lua_cclosure_callback_structure(
            unsupported, direct_calls, program_facts
        )


@pytest.mark.parametrize(
    ("location", "value", "message"),
    [
        (("schema_version",), 2, "unsupported native Lua callback schema"),
        (("method", "accepted_callback_edge"), "drift", "method contract"),
        (("decoder", "version"), "5.0.8", "decoder contract"),
    ],
)
def test_structure_validator_rejects_schema_method_and_decoder_drift(
    tmp_path: Path,
    location: tuple[str, ...],
    value: object,
    message: str,
):
    executable, inventory, program_facts, direct_calls = _write_inputs(tmp_path)
    result = _build(executable, inventory, program_facts, direct_calls)
    tampered = copy.deepcopy(result)
    destination: object = tampered
    for key in location[:-1]:
        destination = destination[key]  # type: ignore[index]
    destination[location[-1]] = value  # type: ignore[index]

    with pytest.raises(NativeLuaCClosureError, match=message):
        validate_native_lua_cclosure_callback_structure(
            tampered, direct_calls, program_facts
        )
