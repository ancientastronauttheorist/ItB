"""Focused proofs for the exact native-to-Lua direct-call census."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import struct
from pathlib import Path
from types import SimpleNamespace

import capstone
import pytest

from scripts import itb_native_lua_direct_calls
import src.observatory.native_lua_direct_calls as native_lua_direct_calls
from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND,
    CALL_FORM,
    NativeLuaDirectCallError,
    _assert_publication_safe,
    build_native_lua_direct_call_census,
    encode_native_lua_direct_call_census,
    validate_native_lua_direct_call_census,
)
from src.observatory.program_facts import build_program_facts
from src.observatory.pe_anchor_map import PEImage


_IMAGE_BASE = 0x00400000
_IAT_RVA = 0x00001190
_REPO_ROOT = Path(__file__).resolve().parents[1]
_COMMITTED_RAW_SHA256 = "6c4d1068da108d49084e19680caf4232ccf0950be1f595fe9417046a24a308a9"
_COMMITTED_CANONICAL_SHA256 = (
    "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
)


def _synthetic_pe(code: bytes | None = None) -> bytes:
    if code is None:
        code = b"\xff\x15" + struct.pack("<I", _IMAGE_BASE + _IAT_RVA) + b"\xc3"
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
    data[0x240:0x242] = b"\x90\xc3"
    struct.pack_into("<IIIII", data, 0x300, 0x1180, 0, 0, 0x1140, _IAT_RVA)
    data[0x340:0x34B] = b"lua5.1.dll\0"
    struct.pack_into("<H", data, 0x360, 7)
    data[0x362:0x36D] = b"lua_gettop\0"
    struct.pack_into("<II", data, 0x380, 0x1160, 0)
    struct.pack_into("<II", data, 0x390, 0x1160, 0)
    return bytes(data)


def _inventory(data: bytes, *, build_id: str = "123") -> dict:
    return {
        "platform": "windows",
        "label": "synthetic native Lua direct-call test",
        "executable": {
            "path": "Breach.exe",
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "format": "pe",
            "architecture": "x86",
        },
        "steam": {
            "build_id": build_id,
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
    first = hashlib.sha256(data[0x220 : 0x220 + code_size]).hexdigest()
    second = hashlib.sha256(data[0x240:0x242]).hexdigest()
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
            f"function\t0x00001020\tcaller\tGlobal\tUSER_DEFINED\t0\t{code_size}\t{first}",
            f"function\t0x00001040\tother\tGlobal\tUSER_DEFINED\t0\t2\t{second}",
            f"range\t0x00001020\t0x00001020\t{code_size}",
            "range\t0x00001040\t0x00001040\t2",
            "",
        ]
    )


def _write_inputs(
    tmp_path: Path,
    *,
    code: bytes | None = None,
) -> tuple[Path, Path, Path, dict, dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    data = _synthetic_pe(code)
    if code is None:
        code_size = 7
    else:
        code_size = len(code)
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(data)
    inventory = _inventory(data)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    facts_path = tmp_path / "facts.tsv"
    facts_path.write_text(_facts(data, code_size), encoding="utf-8", newline="\n")
    program_facts = build_program_facts(
        executable,
        facts_path,
        inventory=inventory,
    )
    program_path = tmp_path / "program.json"
    program_path.write_text(json.dumps(program_facts), encoding="utf-8")
    return executable, inventory_path, program_path, inventory, program_facts


def _build(
    executable: Path,
    inventory: dict,
    program_facts: dict,
) -> dict:
    return build_native_lua_direct_call_census(
        executable,
        program_facts,
        inventory=inventory,
    )


def test_builds_exact_direct_call_relation_without_publishing_instruction_bytes(
    tmp_path: Path,
):
    executable, _inventory_path, _program_path, inventory, program_facts = (
        _write_inputs(tmp_path)
    )

    result = _build(executable, inventory, program_facts)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["summary"] == {
        "atlas_functions": 2,
        "atlas_body_ranges": 2,
        "atlas_body_bytes": 9,
        "decoded_ranges": 2,
        "decoded_bytes": 9,
        "decoded_instructions": 4,
        "lua_named_imports": 1,
        "lua_imports_with_direct_calls": 1,
        "lua_imports_without_direct_calls": 0,
        "direct_lua_import_call_sites": 1,
        "atlas_functions_with_direct_lua_import_calls": 1,
        "schema_violations": 0,
    }
    assert result["lua_imports"] == [
        {
            "library": "lua5.1.dll",
            "name": "lua_gettop",
            "hint": 7,
            "iat_rva": "0x00001190",
            "direct_call_sites": 1,
            "direct_calling_functions": 1,
        }
    ]
    record = result["records"][0]
    assert record["entry_rva"] == "0x00001020"
    assert record["atlas_record_sha256"] == atlas_record_sha256(
        program_facts["functions"][0]
    )
    assert record["direct_call_count"] == 1
    assert record["import_names"] == ["lua_gettop"]
    call = record["direct_lua_import_calls"][0]
    assert call == {
        "call_rva": "0x00001020",
        "instruction_size": 6,
        "instruction_sha256": hashlib.sha256(
            b"\xff\x15" + struct.pack("<I", _IMAGE_BASE + _IAT_RVA)
        ).hexdigest(),
        "call_form": CALL_FORM,
        "library": "lua5.1.dll",
        "import_name": "lua_gettop",
        "iat_rva": "0x00001190",
    }
    rendered = encode_native_lua_direct_call_census(result)
    assert "ff1590114000" not in rendered
    assert "call dword" not in rendered
    verification = validate_native_lua_direct_call_census(
        executable,
        result,
        program_facts,
        inventory=inventory,
    )
    assert verification["status"] == "verified"


def test_non_call_iat_reference_is_not_promoted(tmp_path: Path):
    code = b"\xa1" + struct.pack("<I", _IMAGE_BASE + _IAT_RVA) + b"\xc3"
    executable, _inventory_path, _program_path, inventory, program_facts = (
        _write_inputs(tmp_path, code=code)
    )

    result = _build(executable, inventory, program_facts)

    assert result["records"] == []
    assert result["lua_imports"][0]["direct_call_sites"] == 0
    assert result["summary"]["direct_lua_import_call_sites"] == 0
    assert result["summary"]["lua_imports_without_direct_calls"] == 1


def test_prefixed_or_other_computed_call_form_is_not_accepted(tmp_path: Path):
    code = b"\x2e\xff\x15" + struct.pack("<I", _IMAGE_BASE + _IAT_RVA) + b"\xc3"
    executable, _inventory_path, _program_path, inventory, program_facts = (
        _write_inputs(tmp_path, code=code)
    )

    result = _build(executable, inventory, program_facts)

    assert result["records"] == []
    assert result["summary"]["direct_lua_import_call_sites"] == 0


def test_fails_when_any_atlas_range_is_not_fully_decodable(tmp_path: Path):
    executable, _inventory_path, _program_path, inventory, program_facts = (
        _write_inputs(tmp_path, code=b"\x0f")
    )

    with pytest.raises(NativeLuaDirectCallError, match="did not decode completely"):
        _build(executable, inventory, program_facts)


def test_pins_capstone_version(monkeypatch, tmp_path: Path):
    executable, _inventory_path, _program_path, inventory, program_facts = (
        _write_inputs(tmp_path)
    )
    monkeypatch.setattr(capstone, "__version__", "5.0.8")

    with pytest.raises(NativeLuaDirectCallError, match="unsupported Capstone"):
        _build(executable, inventory, program_facts)


def test_rejects_stale_atlas_and_tampered_evidence(tmp_path: Path):
    executable, _inventory_path, _program_path, inventory, program_facts = (
        _write_inputs(tmp_path)
    )
    result = _build(executable, inventory, program_facts)

    stale = copy.deepcopy(program_facts)
    stale["functions"][0]["body_sha256"] = "0" * 64
    with pytest.raises(NativeLuaDirectCallError, match="prerequisite"):
        _build(executable, inventory, stale)

    tampered = copy.deepcopy(result)
    tampered["records"][0]["direct_lua_import_calls"][0]["import_name"] = (
        "lua_pushvalue"
    )
    with pytest.raises(NativeLuaDirectCallError, match="does not match"):
        validate_native_lua_direct_call_census(
            executable,
            tampered,
            program_facts,
            inventory=inventory,
        )


def test_rejects_executable_drift_after_prerequisite_verification(
    monkeypatch,
    tmp_path: Path,
):
    executable, _inventory_path, _program_path, inventory, program_facts = (
        _write_inputs(tmp_path)
    )
    changed = bytearray(executable.read_bytes())
    changed[0x240] = 0xCC
    changed_data = bytes(changed)

    monkeypatch.setattr(
        native_lua_direct_calls,
        "_load_executable",
        lambda _path: (
            changed_data,
            PEImage(changed_data),
            hashlib.sha256(changed_data).hexdigest(),
        ),
    )

    with pytest.raises(NativeLuaDirectCallError, match="changed after"):
        _build(executable, inventory, program_facts)


@pytest.mark.parametrize(
    "value",
    [
        r"\Users\BMO\private",
        r"C:Users\BMO\private",
        r"note(C:\Users\BMO\private)",
        "/home/user/private",
        "note(/home/user/private)",
    ],
)
def test_publication_scrub_rejects_local_path_forms(value: str):
    with pytest.raises(NativeLuaDirectCallError, match="absolute path"):
        _assert_publication_safe({"value": value})


def test_cli_build_verify_and_replacement_identity(monkeypatch, tmp_path: Path):
    executable, inventory_path, program_path, _inventory_value, _program_value = (
        _write_inputs(tmp_path)
    )
    repo_root = tmp_path / "repo"
    output_root = repo_root / "data/observatory/programs"
    output_root.mkdir(parents=True)
    output = output_root / "census.json"
    monkeypatch.setattr(itb_native_lua_direct_calls, "_REPO_ROOT", repo_root)
    monkeypatch.setattr(itb_native_lua_direct_calls, "_OUTPUT_ROOT", output_root)

    assert (
        itb_native_lua_direct_calls.main(
            [
                "build",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory_path),
                "--program-facts",
                str(program_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["analysis_kind"] == ANALYSIS_KIND
    assert (
        itb_native_lua_direct_calls.main(
            [
                "verify",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory_path),
                "--program-facts",
                str(program_path),
                "--evidence",
                str(output),
            ]
        )
        == 0
    )
    deterministic = output.read_bytes()
    output.write_text(json.dumps(evidence), encoding="utf-8")
    reformatted = output.read_bytes()
    assert reformatted != deterministic
    assert (
        itb_native_lua_direct_calls.main(
            [
                "verify",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory_path),
                "--program-facts",
                str(program_path),
                "--evidence",
                str(output),
            ]
        )
        == 1
    )
    assert (
        itb_native_lua_direct_calls.main(
            [
                "build",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory_path),
                "--program-facts",
                str(program_path),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert output.read_bytes() == reformatted
    output.write_bytes(deterministic)

    foreign = copy.deepcopy(evidence)
    foreign["build_identity"]["build_id"] = "another-build"
    output.write_text(json.dumps(foreign), encoding="utf-8")
    assert (
        itb_native_lua_direct_calls.main(
            [
                "build",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory_path),
                "--program-facts",
                str(program_path),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert json.loads(output.read_text(encoding="utf-8"))["build_identity"][
        "build_id"
    ] == "another-build"


def test_cli_rejects_duplicate_json_keys_and_output_escape(monkeypatch, tmp_path: Path):
    executable, inventory_path, program_path, _inventory_value, _program_value = (
        _write_inputs(tmp_path)
    )
    inventory_path.write_text(
        '{"platform":"windows","platform":"windows"}',
        encoding="utf-8",
    )
    assert (
        itb_native_lua_direct_calls.main(
            [
                "build",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory_path),
                "--program-facts",
                str(program_path),
            ]
        )
        == 1
    )

    executable, inventory_path, program_path, _inventory_value, _program_value = (
        _write_inputs(tmp_path / "fresh")
    )
    repo_root = tmp_path / "repo"
    output_root = repo_root / "data/observatory/programs"
    output_root.mkdir(parents=True)
    monkeypatch.setattr(itb_native_lua_direct_calls, "_REPO_ROOT", repo_root)
    monkeypatch.setattr(itb_native_lua_direct_calls, "_OUTPUT_ROOT", output_root)
    outside = repo_root / "outside.json"
    assert (
        itb_native_lua_direct_calls.main(
            [
                "build",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory_path),
                "--program-facts",
                str(program_path),
                "--output",
                str(outside),
            ]
        )
        == 1
    )
    assert not outside.exists()


def test_cli_never_overwrites_a_concurrently_created_destination(
    monkeypatch,
    tmp_path: Path,
):
    executable, inventory_path, program_path, _inventory_value, _program_value = (
        _write_inputs(tmp_path)
    )
    repo_root = tmp_path / "repo"
    output_root = repo_root / "data/observatory/programs"
    output_root.mkdir(parents=True)
    output = output_root / "race.json"
    monkeypatch.setattr(itb_native_lua_direct_calls, "_REPO_ROOT", repo_root)
    monkeypatch.setattr(itb_native_lua_direct_calls, "_OUTPUT_ROOT", output_root)
    original_link = itb_native_lua_direct_calls.os.link
    foreign = b'{"foreign":true}\n'

    def create_foreign_then_link(source, destination):
        Path(destination).write_bytes(foreign)
        return original_link(source, destination)

    monkeypatch.setattr(
        itb_native_lua_direct_calls.os,
        "link",
        create_foreign_then_link,
    )
    assert (
        itb_native_lua_direct_calls.main(
            [
                "build",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory_path),
                "--program-facts",
                str(program_path),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert output.read_bytes() == foreign


def test_cli_rejects_symlinked_input_when_supported(tmp_path: Path):
    executable, inventory_path, program_path, _inventory_value, _program_value = (
        _write_inputs(tmp_path)
    )
    linked = tmp_path / "linked-program.json"
    try:
        linked.symlink_to(program_path)
    except OSError:
        pytest.skip("host does not permit unprivileged symlink creation")

    assert (
        itb_native_lua_direct_calls.main(
            [
                "build",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory_path),
                "--program-facts",
                str(linked),
            ]
        )
        == 1
    )


def test_cli_json_reader_rechecks_parent_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "input.json"
    source.write_text('{"value":1}', encoding="utf-8")
    parent = source.parent
    observed = parent.lstat()

    def stale_parent_chain(_path, _label):
        return [
            (
                parent,
                SimpleNamespace(
                    st_mode=observed.st_mode,
                    st_dev=observed.st_dev,
                    st_ino=observed.st_ino + 1,
                ),
            )
        ]

    monkeypatch.setattr(
        itb_native_lua_direct_calls,
        "_require_real_parent_chain",
        stale_parent_chain,
    )

    with pytest.raises(NativeLuaDirectCallError, match="changed while"):
        itb_native_lua_direct_calls._read_json_object(source, "input")


def test_committed_census_identity_partitions_and_publication_boundary():
    artifact_path = (
        _REPO_ROOT
        / "data/observatory/programs"
        / "windows_build_13725832_31fe35265598_native_lua_direct_call_census.json"
    )
    atlas_path = (
        _REPO_ROOT
        / "data/observatory/programs"
        / "windows_build_13725832_31fe35265598_program_facts.json"
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
    assert artifact["build_identity"]["architecture"] == "x86"
    assert artifact["build_identity"]["executable_sha256"] == (
        "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
    )
    assert artifact["summary"] == {
        "atlas_functions": 25312,
        "atlas_body_ranges": 25490,
        "atlas_body_bytes": 3735718,
        "decoded_ranges": 25490,
        "decoded_bytes": 3735718,
        "decoded_instructions": 1153814,
        "lua_named_imports": 54,
        "lua_imports_with_direct_calls": 54,
        "lua_imports_without_direct_calls": 0,
        "direct_lua_import_call_sites": 4739,
        "atlas_functions_with_direct_lua_import_calls": 1787,
        "schema_violations": 0,
    }

    atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
    atlas_by_entry = {item["entry_rva"]: item for item in atlas["functions"]}
    records = artifact["records"]
    entries = [item["entry_rva"] for item in records]
    assert entries == sorted(entries)
    assert len(entries) == len(set(entries)) == 1787
    all_calls = []
    import_site_counts: dict[str, int] = {}
    import_callers: dict[str, set[str]] = {}
    expected_call_fields = {
        "call_rva",
        "instruction_size",
        "instruction_sha256",
        "call_form",
        "library",
        "import_name",
        "iat_rva",
    }
    for record in records:
        assert record["atlas_record_sha256"] == atlas_record_sha256(
            atlas_by_entry[record["entry_rva"]]
        )
        calls = record["direct_lua_import_calls"]
        assert calls
        assert record["direct_call_count"] == len(calls)
        assert [item["call_rva"] for item in calls] == sorted(
            item["call_rva"] for item in calls
        )
        assert record["import_names"] == sorted(
            {item["import_name"] for item in calls}
        )
        for call in calls:
            assert set(call) == expected_call_fields
            assert call["instruction_size"] == 6
            assert call["call_form"] == CALL_FORM
            all_calls.append(call["call_rva"])
            import_site_counts[call["import_name"]] = (
                import_site_counts.get(call["import_name"], 0) + 1
            )
            import_callers.setdefault(call["import_name"], set()).add(
                record["entry_rva"]
            )
    assert len(all_calls) == len(set(all_calls)) == 4739

    imports = artifact["lua_imports"]
    assert [item["iat_rva"] for item in imports] == sorted(
        item["iat_rva"] for item in imports
    )
    assert len({item["iat_rva"] for item in imports}) == 54
    assert len({item["name"] for item in imports}) == 54
    for item in imports:
        assert item["direct_call_sites"] == import_site_counts[item["name"]]
        assert item["direct_calling_functions"] == len(
            import_callers[item["name"]]
        )

    assert re.search(rb"[A-Za-z]:[\\/]", payload) is None
    forbidden_fields = {
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
            assert forbidden_fields.isdisjoint(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(artifact)
