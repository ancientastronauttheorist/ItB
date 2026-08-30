"""Focused proofs for direct table-setter publication of native Lua closures."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import struct
from pathlib import Path

import pytest

from scripts import itb_native_lua_cclosure_table_setter_publications
import src.observatory.native_lua_cclosure_table_setter_publications as table_setters
from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_callbacks import (
    build_native_lua_cclosure_callback_census,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    build_native_lua_cclosure_setfield_publication_census,
)
from src.observatory.native_lua_cclosure_table_setter_publications import (
    ANALYSIS_KIND,
    PUBLICATION_FORM,
    NativeLuaCClosureTableSetterPublicationError,
    build_native_lua_cclosure_table_setter_publication_census,
    encode_native_lua_cclosure_table_setter_publication_census,
    validate_native_lua_cclosure_table_setter_publication_census,
    validate_native_lua_cclosure_table_setter_publication_structure,
)
from src.observatory.native_lua_direct_calls import (
    build_native_lua_direct_call_census,
)
from src.observatory.program_facts import build_program_facts


_IMAGE_BASE = 0x00400000
_CALLER_RVA = 0x00001020
_CALLBACK_RVA = 0x00001080
_PUSHCLOSURE_IAT_RVA = 0x000011E0
_SETTER_IAT_RVA = 0x000011E4
_SETFIELD_IAT_RVA = 0x000011EC
_REPO_ROOT = Path(__file__).resolve().parents[1]
_COMMITTED_RAW_SHA256 = (
    "9be33f9d20415f534f56ad591b2ef8a1bcff58726cffce62b869352a8837ee24"
)
_COMMITTED_CANONICAL_SHA256 = (
    "a6333ffefd9c9d0ed42bea28b9f5a6e82afff58fc7adb26293c34b5589cb5fa9"
)


def _push_signed(value: int, *, force_imm32: bool = False) -> bytes:
    if not force_imm32 and -128 <= value <= 127:
        return b"\x6a" + struct.pack("<b", value)
    return b"\x68" + struct.pack("<i", value)


def _publication_code(
    *,
    setter: str = "lua_rawset",
    upvalue_count: int = 0,
    cleanup: bytes = b"",
    table_index: int = -3,
    force_table_imm32: bool = False,
    callback_state_push: bytes = b"\x57",
    publication_state_push: bytes = b"\x57",
    between: bytes = b"",
    table_push: bytes | None = None,
    setter_call: bytes | None = None,
) -> bytes:
    if setter not in {"lua_rawset", "lua_settable"}:
        raise ValueError("unsupported synthetic setter")
    if not 0 <= upvalue_count <= 127:
        raise ValueError("synthetic upvalue count must fit push imm8")
    if table_push is None:
        table_push = _push_signed(table_index, force_imm32=force_table_imm32)
    if setter_call is None:
        setter_call = b"\xff\x15" + struct.pack(
            "<I", _IMAGE_BASE + _SETTER_IAT_RVA
        )
    return (
        b"\x6a"
        + bytes([upvalue_count])
        + b"\x68"
        + struct.pack("<I", _IMAGE_BASE + _CALLBACK_RVA)
        + callback_state_push
        + b"\xff\x15"
        + struct.pack("<I", _IMAGE_BASE + _PUSHCLOSURE_IAT_RVA)
        + cleanup
        + between
        + table_push
        + publication_state_push
        + setter_call
        + b"\xc3"
    )


def _synthetic_pe(code: bytes, *, setter: str) -> bytes:
    data = bytearray(0xA00)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into(
        "<HHIIIHH", data, 0x84, 0x014C, 1, 0x12345678, 0, 0, 0xE0, 0x010F
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
    struct.pack_into("<IIII", data, section + 8, 0x800, 0x1000, 0x800, 0x200)
    struct.pack_into("<I", data, section + 36, 0x60000020)

    data[0x220 : 0x220 + len(code)] = code
    data[0x280:0x283] = b"\x31\xc0\xc3"
    struct.pack_into(
        "<IIIII", data, 0x300, 0x11C0, 0, 0, 0x1140, _PUSHCLOSURE_IAT_RVA
    )
    data[0x340:0x34B] = b"lua5.1.dll\0"
    struct.pack_into("<H", data, 0x360, 7)
    data[0x362:0x373] = b"lua_pushcclosure\0"
    struct.pack_into("<H", data, 0x378, 8)
    setter_name = setter.encode("ascii") + b"\0"
    data[0x37A : 0x37A + len(setter_name)] = setter_name
    other_setter = (
        b"lua_settable\0" if setter == "lua_rawset" else b"lua_rawset\0"
    )
    struct.pack_into("<H", data, 0x390, 9)
    data[0x392 : 0x392 + len(other_setter)] = other_setter
    struct.pack_into("<H", data, 0x3A4, 10)
    data[0x3A6:0x3B3] = b"lua_setfield\0"
    struct.pack_into(
        "<IIIII", data, 0x3C0, 0x1160, 0x1178, 0x1190, 0x11A4, 0
    )
    struct.pack_into(
        "<IIIII", data, 0x3E0, 0x1160, 0x1178, 0x1190, 0x11A4, 0
    )
    return bytes(data)


def _inventory(data: bytes) -> dict:
    return {
        "platform": "windows",
        "label": "synthetic direct table-setter publication test",
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
    setter: str = "lua_rawset",
) -> tuple[Path, dict, dict, dict, dict, dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    code = _publication_code(setter=setter) if code is None else code
    data = _synthetic_pe(code, setter=setter)
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(data)
    inventory = _inventory(data)
    facts_path = tmp_path / "facts.tsv"
    facts_path.write_text(_facts(data, len(code)), encoding="utf-8", newline="\n")
    program_facts = build_program_facts(
        executable, facts_path, inventory=inventory
    )
    direct_calls = build_native_lua_direct_call_census(
        executable, program_facts, inventory=inventory
    )
    callbacks = build_native_lua_cclosure_callback_census(
        executable, direct_calls, program_facts, inventory=inventory
    )
    setfield = build_native_lua_cclosure_setfield_publication_census(
        executable,
        direct_calls,
        callbacks,
        program_facts,
        inventory=inventory,
    )
    assert len(setfield["unmatched_resolved_sites"]) == 1
    return executable, inventory, program_facts, direct_calls, callbacks, setfield


def _build(
    executable: Path,
    inventory: dict,
    program_facts: dict,
    direct_calls: dict,
    callbacks: dict,
    setfield: dict,
) -> dict:
    return build_native_lua_cclosure_table_setter_publication_census(
        executable,
        direct_calls,
        callbacks,
        setfield,
        program_facts,
        inventory=inventory,
    )


def test_builds_no_cleanup_rawset_minus_three_from_prior_frontier(tmp_path: Path):
    inputs = _write_inputs(tmp_path)
    result = _build(*inputs)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert len(result["publications"]) == 1
    assert result["still_unmatched_resolved_sites"] == []
    publication = result["publications"][0]
    assert publication["publication_form"] == PUBLICATION_FORM
    assert publication["caller_entry_rva"] == "0x00001020"
    assert publication["callback_call_rva"] == "0x00001028"
    assert publication["callback_entry_rva"] == "0x00001080"
    assert publication["cleanup_instruction"] is None
    assert publication["table_index"] == -3
    assert publication["setter_call_rva"] == "0x00001031"
    assert publication["setter_import_name"] == "lua_rawset"
    assert publication["literal_upvalue_count"] == 0
    assert result["builders"] == [
        {
            "builder_entry_rva": "0x00001020",
            "builder_atlas_record_sha256": atlas_record_sha256(
                inputs[2]["functions"][0]
            ),
            "publication_site_count": 1,
            "registered_callback_entry_rvas": ["0x00001080"],
            "setter_import_names": ["lua_rawset"],
            "table_indices": [-3],
            "upvalue_argument_kinds": ["immediate"],
        }
    ]
    rendered = encode_native_lua_cclosure_table_setter_publication_census(result)
    assert rendered == encode_native_lua_cclosure_table_setter_publication_census(
        result
    )
    assert "ff15c0114000" not in rendered
    assert "instruction_bytes" not in rendered
    assert "mnemonic" not in rendered
    assert re.search(r"[A-Za-z]:[\\/]", rendered) is None


def test_accepts_cleanup_settable_signed_imm32_and_nonzero_upvalues(
    tmp_path: Path,
):
    code = _publication_code(
        setter="lua_settable",
        upvalue_count=2,
        cleanup=b"\x83\xc4\x2c",
        table_index=-10002,
        force_table_imm32=True,
    )
    inputs = _write_inputs(tmp_path, code=code, setter="lua_settable")
    result = _build(*inputs)
    publication = result["publications"][0]

    assert publication["literal_upvalue_count"] == 2
    assert publication["cleanup_instruction"]["size"] == 3
    assert publication["table_index"] == -10002
    assert publication["table_index_push"]["size"] == 5
    assert publication["setter_import_name"] == "lua_settable"
    assert publication["setter_call_rva"] == "0x00001037"
    assert result["summary"]["matched_direct_table_setter_publication_sites"] == 1
    assert result["summary"]["still_unmatched_resolved_callback_sites"] == 0
    assert result["summary"]["unique_table_indices"] == 1


@pytest.mark.parametrize(
    ("code", "setter"),
    [
        (_publication_code(publication_state_push=b"\x51"), "lua_rawset"),
        (
            _publication_code(
                callback_state_push=b"\x50", publication_state_push=b"\x50"
            ),
            "lua_rawset",
        ),
        (
            _publication_code(
                callback_state_push=b"\x51", publication_state_push=b"\x51"
            ),
            "lua_rawset",
        ),
        (
            _publication_code(
                callback_state_push=b"\x52", publication_state_push=b"\x52"
            ),
            "lua_rawset",
        ),
        (
            _publication_code(
                callback_state_push=b"\x54", publication_state_push=b"\x54"
            ),
            "lua_rawset",
        ),
        (_publication_code(table_index=0), "lua_rawset"),
        (_publication_code(table_index=-1), "lua_rawset"),
        (_publication_code(table_push=b"\x51"), "lua_rawset"),
        (
            _publication_code(
                setter_call=b"\xff\x15"
                + struct.pack("<I", _IMAGE_BASE + _SETFIELD_IAT_RVA)
            ),
            "lua_rawset",
        ),
        (_publication_code(setter_call=b"\xff\xd0"), "lua_rawset"),
        (_publication_code(between=b"\x90"), "lua_rawset"),
        (_publication_code(cleanup=b"\x83\xc4\x00"), "lua_rawset"),
    ],
    ids=[
        "different-state-register",
        "same-eax-state-register",
        "same-ecx-state-register",
        "same-edx-state-register",
        "same-esp-state-register",
        "zero-table-index",
        "minus-one-table-index",
        "non-immediate-table-index",
        "wrong-direct-import",
        "indirect-setter-call",
        "noncontiguous-nop",
        "zero-byte-cleanup",
    ],
)
def test_near_miss_forms_remain_in_the_prior_unmatched_frontier(
    tmp_path: Path,
    code: bytes,
    setter: str,
):
    inputs = _write_inputs(tmp_path, code=code, setter=setter)
    result = _build(*inputs)

    assert result["publications"] == []
    assert result["builders"] == []
    assert result["registered_targets"] == []
    assert len(result["still_unmatched_resolved_sites"]) == 1
    assert result["still_unmatched_resolved_sites"][0]["callback_call_rva"] == (
        "0x00001028"
    )
    assert result["summary"]["prior_unmatched_resolved_callback_sites"] == 1
    assert result["summary"]["matched_direct_table_setter_publication_sites"] == 0
    assert result["summary"]["still_unmatched_resolved_callback_sites"] == 1


def test_exact_validator_rejects_evidence_and_binary_drift(tmp_path: Path):
    inputs = _write_inputs(tmp_path)
    result = _build(*inputs)
    verification = validate_native_lua_cclosure_table_setter_publication_census(
        inputs[0],
        result,
        inputs[3],
        inputs[4],
        inputs[5],
        inputs[2],
        inventory=inputs[1],
    )
    assert verification["status"] == "verified"
    assert verification["summary"] == result["summary"]

    altered = copy.deepcopy(result)
    altered["publications"][0]["table_index"] = -4
    with pytest.raises(
        NativeLuaCClosureTableSetterPublicationError,
        match="differs from exact rebuild",
    ):
        validate_native_lua_cclosure_table_setter_publication_census(
            inputs[0],
            altered,
            inputs[3],
            inputs[4],
            inputs[5],
            inputs[2],
            inventory=inputs[1],
        )

    data = bytearray(inputs[0].read_bytes())
    data[0x500] ^= 1
    inputs[0].write_bytes(data)
    with pytest.raises(NativeLuaCClosureTableSetterPublicationError):
        validate_native_lua_cclosure_table_setter_publication_census(
            inputs[0],
            result,
            inputs[3],
            inputs[4],
            inputs[5],
            inputs[2],
            inventory=inputs[1],
        )


def test_structure_validator_accepts_without_loading_the_pe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    inputs = _write_inputs(tmp_path)
    result = _build(*inputs)

    def no_binary_read(*args, **kwargs):
        raise AssertionError("structural validation must not load the PE")

    monkeypatch.setattr(table_setters, "_load_executable", no_binary_read)
    verification = validate_native_lua_cclosure_table_setter_publication_structure(
        result, inputs[3], inputs[4], inputs[5], inputs[2]
    )
    assert verification["status"] == "structurally_verified"
    assert verification["summary"] == result["summary"]


@pytest.mark.parametrize(
    ("mutator", "category"),
    [
        (lambda d: d.__setitem__("schema_version", 2), "schema"),
        (lambda d: d.__setitem__("schema_version", True), "schema type"),
        (
            lambda d: d["setfield_publication_census"].__setitem__(
                "canonical_sha256", "0" * 64
            ),
            "prerequisite",
        ),
        (lambda d: d.__setitem__("publications", []), "partition"),
        (
            lambda d: d["publications"][0].__setitem__(
                "callback_atlas_record_sha256", "0" * 64
            ),
            "callback join",
        ),
        (
            lambda d: d["publications"][0]["table_index_push"].__setitem__(
                "sha256", "0" * 64
            ),
            "instruction hash",
        ),
        (
            lambda d: d["publications"][0]["state_push"].__setitem__(
                "rva", "0x00001020"
            ),
            "contiguity",
        ),
        (
            lambda d: d["publications"][0].__setitem__(
                "table_index", 0xFFFFFFFD
            ),
            "signed table index",
        ),
        (
            lambda d: d["builders"][0].__setitem__(
                "publication_site_count", 2
            ),
            "aggregate",
        ),
        (
            lambda d: d["summary"].__setitem__(
                "matched_direct_table_setter_publication_sites", 2
            ),
            "summary",
        ),
    ],
    ids=lambda item: item if isinstance(item, str) else None,
)
def test_structure_validator_rejects_adversarial_drift(
    tmp_path: Path,
    mutator,
    category: str,
):
    inputs = _write_inputs(tmp_path)
    result = _build(*inputs)
    altered = copy.deepcopy(result)
    mutator(altered)

    with pytest.raises(NativeLuaCClosureTableSetterPublicationError):
        validate_native_lua_cclosure_table_setter_publication_structure(
            altered, inputs[3], inputs[4], inputs[5], inputs[2]
        )


def test_structural_grammar_cannot_substitute_for_binary_verification(
    tmp_path: Path,
):
    inputs = _write_inputs(tmp_path)
    result = _build(*inputs)
    forged = copy.deepcopy(result)
    publication = forged["publications"][0]
    publication["table_index"] = -4
    publication["table_index_push"]["sha256"] = hashlib.sha256(
        b"\x6a\xfc"
    ).hexdigest()
    forged["builders"][0]["table_indices"] = [-4]
    forged["registered_targets"][0]["table_indices"] = [-4]

    assert validate_native_lua_cclosure_table_setter_publication_structure(
        forged, inputs[3], inputs[4], inputs[5], inputs[2]
    )["status"] == "structurally_verified"
    with pytest.raises(
        NativeLuaCClosureTableSetterPublicationError,
        match="differs from exact rebuild",
    ):
        validate_native_lua_cclosure_table_setter_publication_census(
            inputs[0],
            forged,
            inputs[3],
            inputs[4],
            inputs[5],
            inputs[2],
            inventory=inputs[1],
        )


@pytest.mark.parametrize("table_index", [0, -1])
def test_structure_validator_rejects_definitely_invalid_table_indices(
    tmp_path: Path,
    table_index: int,
):
    inputs = _write_inputs(tmp_path)
    result = _build(*inputs)
    forged = copy.deepcopy(result)
    publication = forged["publications"][0]
    publication["table_index"] = table_index
    publication["table_index_push"]["sha256"] = hashlib.sha256(
        _push_signed(table_index)
    ).hexdigest()
    forged["builders"][0]["table_indices"] = [table_index]
    forged["registered_targets"][0]["table_indices"] = [table_index]

    with pytest.raises(
        NativeLuaCClosureTableSetterPublicationError,
        match="definitely invalid",
    ):
        validate_native_lua_cclosure_table_setter_publication_structure(
            forged, inputs[3], inputs[4], inputs[5], inputs[2]
        )


@pytest.mark.parametrize("opcode", [0x50, 0x51, 0x52, 0x54])
def test_structural_state_register_gate_rejects_abi_unsafe_pushes(opcode: int):
    fact = (0x1000, 1, hashlib.sha256(bytes([opcode])).hexdigest())

    with pytest.raises(
        NativeLuaCClosureTableSetterPublicationError,
        match="ABI-nonvolatile",
    ):
        table_setters._require_abi_nonvolatile_state_push(fact, "state")


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def test_cli_round_trip_and_immutable_output(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
):
    inputs = _write_inputs(tmp_path / "inputs")
    paths = {}
    for name, value in (
        ("inventory", inputs[1]),
        ("program", inputs[2]),
        ("direct", inputs[3]),
        ("callbacks", inputs[4]),
        ("setfield", inputs[5]),
    ):
        path = tmp_path / f"{name}.json"
        _write_json(path, value)
        paths[name] = path

    fake_repo = tmp_path / "repo"
    output_root = fake_repo / "data" / "observatory" / "programs"
    output_root.mkdir(parents=True)
    monkeypatch.setattr(
        itb_native_lua_cclosure_table_setter_publications,
        "_REPO_ROOT",
        fake_repo,
    )
    monkeypatch.setattr(
        itb_native_lua_cclosure_table_setter_publications,
        "_OUTPUT_ROOT",
        output_root,
    )
    output = output_root / "synthetic_table_setters.json"
    common = [
        "--executable",
        str(inputs[0]),
        "--inventory",
        str(paths["inventory"]),
        "--program-facts",
        str(paths["program"]),
        "--direct-calls",
        str(paths["direct"]),
        "--callbacks",
        str(paths["callbacks"]),
        "--setfield-publications",
        str(paths["setfield"]),
    ]
    assert (
        itb_native_lua_cclosure_table_setter_publications.main(
            ["build", *common, "--output", str(output)]
        )
        == 0
    )
    first = output.read_bytes()
    assert (
        itb_native_lua_cclosure_table_setter_publications.main(
            ["build", *common, "--output", str(output)]
        )
        == 0
    )
    assert output.read_bytes() == first
    capsys.readouterr()
    assert (
        itb_native_lua_cclosure_table_setter_publications.main(
            ["verify", *common, "--evidence", str(output)]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "verified"

    output.write_bytes(first + b" ")
    assert (
        itb_native_lua_cclosure_table_setter_publications.main(
            ["build", *common, "--output", str(output)]
        )
        == 1
    )
    assert "refusing to overwrite" in capsys.readouterr().err


def test_committed_artifact_identity_and_partition_if_present():
    path = (
        _REPO_ROOT
        / "data"
        / "observatory"
        / "programs"
        / (
            "windows_build_13725832_31fe35265598_"
            "native_lua_cclosure_table_setter_publications.json"
        )
    )
    if not path.exists():
        pytest.skip("committed table-setter artifact is not in this tranche yet")

    payload = path.read_bytes()
    artifact = json.loads(payload)
    assert hashlib.sha256(payload).hexdigest() == _COMMITTED_RAW_SHA256
    assert table_setters._canonical_sha256(artifact) == (
        _COMMITTED_CANONICAL_SHA256
    )
    assert artifact["analysis_kind"] == ANALYSIS_KIND
    assert artifact["build_identity"]["build_id"] == "13725832"
    assert artifact["summary"] == {
        "prior_unmatched_resolved_callback_sites": 10,
        "matched_direct_table_setter_publication_sites": 4,
        "still_unmatched_resolved_callback_sites": 6,
        "settable_publication_sites": 3,
        "rawset_publication_sites": 1,
        "unique_registered_callback_targets": 3,
        "unique_registration_builders": 4,
        "unique_table_indices": 2,
        "schema_violations": 0,
    }
    assert [
        (
            item["callback_call_rva"],
            item["setter_import_name"],
            item["setter_call_rva"],
            item["table_index"],
        )
        for item in artifact["publications"]
    ] == [
        ("0x002e6c01", "lua_settable", "0x002e6c10", -10002),
        ("0x002ea533", "lua_rawset", "0x002ea53c", -3),
        ("0x002eb086", "lua_settable", "0x002eb092", -10002),
        ("0x002eb2a5", "lua_settable", "0x002eb2b1", -10002),
    ]
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
