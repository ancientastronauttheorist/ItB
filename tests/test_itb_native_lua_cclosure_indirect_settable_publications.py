"""Focused proofs for staged indirect-lua_settable closure publications."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import struct
from pathlib import Path

import pytest

from scripts import itb_native_lua_cclosure_indirect_settable_publications as cli
import src.observatory.native_lua_cclosure_indirect_settable_publications as indirect
from src.observatory.native_lua_cclosure_callbacks import (
    build_native_lua_cclosure_callback_census,
)
from src.observatory.native_lua_cclosure_indirect_settable_publications import (
    ANALYSIS_KIND,
    PUBLICATION_FORM,
    NativeLuaCClosureIndirectSettablePublicationError,
    build_native_lua_cclosure_indirect_settable_publication_census,
    encode_native_lua_cclosure_indirect_settable_publication_census,
    validate_native_lua_cclosure_indirect_settable_publication_census,
    validate_native_lua_cclosure_indirect_settable_publication_structure,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    build_native_lua_cclosure_setfield_publication_census,
)
from src.observatory.native_lua_cclosure_table_setter_publications import (
    build_native_lua_cclosure_table_setter_publication_census,
)
from src.observatory.native_lua_direct_calls import build_native_lua_direct_call_census
from src.observatory.program_facts import build_program_facts


_IMAGE_BASE = 0x00400000
_CALLER_RVA = 0x00001020
_CALLBACK_RVA = 0x00001080
_PUSHCLOSURE_IAT_RVA = 0x000011E0
_SETTABLE_IAT_RVA = 0x000011E4
_SETFIELD_IAT_RVA = 0x000011EC
_REPO_ROOT = Path(__file__).resolve().parents[1]
_COMMITTED_RAW_SHA256 = (
    "cd87cf7e5b6edd3595a11b1d06accb965680baed3d85533fbf4c347ec1153710"
)
_COMMITTED_CANONICAL_SHA256 = (
    "50790f8372d90ab11e44a483a39bd575e5af10ceb037c1aa557e4ebf801ac682"
)


def _push_signed(value: int, *, force_imm32: bool = False) -> bytes:
    if not force_imm32 and -128 <= value <= 127:
        return b"\x6a" + struct.pack("<b", value)
    return b"\x68" + struct.pack("<i", value)


def _publication_code(
    *,
    upvalue_count: int = 0,
    cleanup: bytes = b"\x83\xc4\x14",
    table_index: int = -3,
    force_table_imm32: bool = False,
    callback_state_push: bytes = b"\x57",
    publication_state_push: bytes = b"\x57",
    stage: bytes | None = None,
    between_stage_and_cleanup: bytes = b"",
    between_tail: bytes = b"",
    table_push: bytes | None = None,
    setter_call: bytes = b"\xff\xd6",
) -> bytes:
    if stage is None:
        stage = b"\x8b\x35" + struct.pack(
            "<I", _IMAGE_BASE + _SETTABLE_IAT_RVA
        )
    if table_push is None:
        table_push = _push_signed(table_index, force_imm32=force_table_imm32)
    return (
        b"\x6a"
        + bytes([upvalue_count])
        + b"\x68"
        + struct.pack("<I", _IMAGE_BASE + _CALLBACK_RVA)
        + callback_state_push
        + b"\xff\x15"
        + struct.pack("<I", _IMAGE_BASE + _PUSHCLOSURE_IAT_RVA)
        + stage
        + between_stage_and_cleanup
        + cleanup
        + table_push
        + between_tail
        + publication_state_push
        + setter_call
        + b"\xc3"
    )


def _synthetic_pe(code: bytes) -> bytes:
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
    data[0x37A:0x387] = b"lua_settable\0"
    struct.pack_into("<H", data, 0x390, 9)
    data[0x392:0x39D] = b"lua_rawset\0"
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
        "label": "synthetic indirect settable publication test",
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
            f"function\t0x00001020\tcaller\tGlobal\tUSER_DEFINED\t0\t{code_size}\t{caller_hash}",
            f"function\t0x00001080\tcallback\tGlobal\tUSER_DEFINED\t0\t3\t{callback_hash}",
            f"range\t0x00001020\t0x00001020\t{code_size}",
            "range\t0x00001080\t0x00001080\t3",
            "",
        ]
    )


def _write_inputs(
    tmp_path: Path, *, code: bytes | None = None
) -> tuple[Path, dict, dict, dict, dict, dict, dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    code = _publication_code() if code is None else code
    data = _synthetic_pe(code)
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(data)
    inventory = _inventory(data)
    facts_path = tmp_path / "facts.tsv"
    facts_path.write_text(_facts(data, len(code)), encoding="utf-8", newline="\n")
    facts = build_program_facts(executable, facts_path, inventory=inventory)
    direct = build_native_lua_direct_call_census(
        executable, facts, inventory=inventory
    )
    callbacks = build_native_lua_cclosure_callback_census(
        executable, direct, facts, inventory=inventory
    )
    setfield = build_native_lua_cclosure_setfield_publication_census(
        executable, direct, callbacks, facts, inventory=inventory
    )
    direct_setters = build_native_lua_cclosure_table_setter_publication_census(
        executable,
        direct,
        callbacks,
        setfield,
        facts,
        inventory=inventory,
    )
    assert direct_setters["summary"]["still_unmatched_resolved_callback_sites"] >= 1
    return executable, inventory, facts, direct, callbacks, setfield, direct_setters


def _build(inputs: tuple[Path, dict, dict, dict, dict, dict, dict]) -> dict:
    executable, inventory, facts, direct, callbacks, setfield, direct_setters = inputs
    return build_native_lua_cclosure_indirect_settable_publication_census(
        executable,
        direct,
        callbacks,
        setfield,
        direct_setters,
        facts,
        inventory=inventory,
    )


def test_builds_exact_staged_indirect_settable_publication(tmp_path: Path):
    inputs = _write_inputs(tmp_path)
    result = _build(inputs)

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["still_unmatched_resolved_sites"] == []
    publication = result["publications"][0]
    assert publication["publication_form"] == PUBLICATION_FORM
    assert publication["callback_call_rva"] == "0x00001028"
    assert publication["callback_entry_rva"] == "0x00001080"
    assert publication["setter_stage"]["rva"] == "0x0000102e"
    assert publication["setter_stage_iat_rva"] == "0x000011e4"
    assert publication["stage_between_callback_and_tail"] is True
    assert publication["cleanup_stack_bytes"] == 0x14
    assert publication["table_index"] == -3
    assert publication["setter_call_rva"] == "0x0000103a"
    assert publication["esi_preservation_instruction_count"] == 3
    assert all(
        item["writes_esi"] is False
        for item in publication["esi_preservation_witness"]
    )
    assert result["summary"] == {
        "prior_unmatched_resolved_callback_sites": 1,
        "matched_indirect_settable_publication_sites": 1,
        "still_unmatched_resolved_callback_sites": 0,
        "unique_registered_callback_targets": 1,
        "unique_registration_builders": 1,
        "unique_setter_stages": 1,
        "unique_table_indices": 1,
        "esi_preservation_witness_instructions": 3,
        "cfg_instruction_nodes": 10,
        "cfg_edges": 9,
        "stage_to_setter_path_nodes": 5,
        "schema_violations": 0,
    }
    assert publication["cfg_proof"]["stage_dominates_setter_call"] is True
    assert publication["cfg_proof"]["bootstrap_callback_dominance_exception"] is True
    assert len(result["control_flow_graphs"]) == 1
    rendered = encode_native_lua_cclosure_indirect_settable_publication_census(result)
    assert rendered == encode_native_lua_cclosure_indirect_settable_publication_census(result)
    assert "8b35e4114000" not in rendered
    assert "instruction_bytes" not in rendered
    assert "mnemonic" not in rendered
    assert re.search(r"[A-Za-z]:[\\/]", rendered) is None


def test_accepts_imm32_index_and_upvalue_metadata(tmp_path: Path):
    inputs = _write_inputs(
        tmp_path,
        code=_publication_code(
            upvalue_count=2,
            cleanup=b"\x83\xc4\x24",
            table_index=-10002,
            force_table_imm32=True,
        ),
    )
    publication = _build(inputs)["publications"][0]
    assert publication["literal_upvalue_count"] == 2
    assert publication["table_index"] == -10002
    assert publication["table_index_push"]["size"] == 5


@pytest.mark.parametrize(
    "code",
    [
        _publication_code(
            stage=b"\x8b\x35" + struct.pack("<I", _IMAGE_BASE + _SETFIELD_IAT_RVA)
        ),
        _publication_code(
            stage=b"\x8b\x3d" + struct.pack("<I", _IMAGE_BASE + _SETTABLE_IAT_RVA)
        ),
        _publication_code(stage=b"\x90" * 6),
        _publication_code(publication_state_push=b"\x53"),
        _publication_code(callback_state_push=b"\x50", publication_state_push=b"\x50"),
        _publication_code(table_index=0),
        _publication_code(table_index=-1),
        _publication_code(cleanup=b"\x83\xc4\x00"),
        _publication_code(cleanup=b"\x83\xc4\x03"),
        _publication_code(cleanup=b""),
        _publication_code(between_tail=b"\x90"),
        _publication_code(setter_call=b"\xff\xd7"),
        _publication_code(setter_call=b"\xff\x15" + struct.pack("<I", _IMAGE_BASE + _SETTABLE_IAT_RVA)),
        _publication_code(between_stage_and_cleanup=b"\x89\xc6"),
    ],
    ids=[
        "wrong-stage-iat",
        "wrong-stage-register",
        "wrong-stage-opcode",
        "state-mismatch",
        "caller-saved-state",
        "zero-index",
        "minus-one-index",
        "zero-cleanup",
        "unaligned-cleanup",
        "missing-cleanup",
        "noncontiguous-tail",
        "wrong-indirect-register",
        "direct-call-instead",
        "esi-clobber-after-stage",
    ],
)
def test_near_misses_remain_in_residual_frontier(tmp_path: Path, code: bytes):
    result = _build(_write_inputs(tmp_path, code=code))
    assert result["publications"] == []
    assert len(result["still_unmatched_resolved_sites"]) == 1
    assert result["summary"]["matched_indirect_settable_publication_sites"] == 0


def _entry_branch_bypassing_stage_code() -> bytes:
    base = _publication_code()
    cleanup_offset = base.index(b"\x83\xc4\x14")
    return b"\x75" + struct.pack("<b", cleanup_offset) + base


def _entry_jump_making_publication_unreachable_code() -> bytes:
    base = _publication_code()
    target_offset = 2 + len(base) - 1
    return b"\xeb" + struct.pack("<b", target_offset - 2) + base


def _alternate_path_esi_clobber_code() -> bytes:
    first = _publication_code()[:-1]
    second = (
        b"\x6a\x00"
        + b"\x68"
        + struct.pack("<I", _IMAGE_BASE + _CALLBACK_RVA)
        + b"\x57"
        + b"\xff\x15"
        + struct.pack("<I", _IMAGE_BASE + _PUSHCLOSURE_IAT_RVA)
        + b"\x83\xc4\x14"
        + b"\x6a\xfd"
        + b"\x57"
        + b"\xff\xd6"
    )
    code = bytearray(first)
    branch_to_clobber = len(code)
    code += b"\x75\x00"
    second_callback = len(code)
    code += second
    jump_to_end = len(code)
    code += b"\xeb\x00"
    clobber = len(code)
    code += b"\x89\xc6"
    jump_back = len(code)
    code += b"\xe9\x00\x00\x00\x00"
    end = len(code)
    code += b"\xc3"
    struct.pack_into("<b", code, branch_to_clobber + 1, clobber - (branch_to_clobber + 2))
    struct.pack_into("<b", code, jump_to_end + 1, end - (jump_to_end + 2))
    struct.pack_into("<i", code, jump_back + 1, second_callback - (jump_back + 5))
    return bytes(code)


def test_cfg_rejects_direct_branch_bypassing_setter_stage(tmp_path: Path):
    result = _build(
        _write_inputs(tmp_path, code=_entry_branch_bypassing_stage_code())
    )
    assert result["publications"] == []
    assert len(result["still_unmatched_resolved_sites"]) == 1


def test_cfg_rejects_esi_clobber_on_alternate_nonlexical_path(tmp_path: Path):
    result = _build(
        _write_inputs(tmp_path, code=_alternate_path_esi_clobber_code())
    )
    assert result["summary"]["prior_unmatched_resolved_callback_sites"] == 2
    assert result["summary"]["matched_indirect_settable_publication_sites"] == 1
    assert result["summary"]["still_unmatched_resolved_callback_sites"] == 1
    assert len(result["publications"][0]["cfg_proof"]["stage_to_setter_path_rvas"]) > 0


def test_cfg_rejects_unconditional_nonfallthrough_path_break(tmp_path: Path):
    result = _build(
        _write_inputs(
            tmp_path, code=_entry_jump_making_publication_unreachable_code()
        )
    )
    assert result["publications"] == []
    assert len(result["still_unmatched_resolved_sites"]) == 1


def test_exact_and_pe_free_structural_validation(tmp_path: Path, monkeypatch):
    inputs = _write_inputs(tmp_path)
    result = _build(inputs)
    verification = validate_native_lua_cclosure_indirect_settable_publication_census(
        inputs[0],
        result,
        inputs[3],
        inputs[4],
        inputs[5],
        inputs[6],
        inputs[2],
        inventory=inputs[1],
    )
    assert verification["status"] == "verified"

    def no_binary_read(*args, **kwargs):
        raise AssertionError("structural validation must not load the PE")

    monkeypatch.setattr(indirect, "_load_executable", no_binary_read)
    structural = validate_native_lua_cclosure_indirect_settable_publication_structure(
        result, inputs[3], inputs[4], inputs[5], inputs[6], inputs[2]
    )
    assert structural["status"] == "structurally_verified"
    assert structural["summary"] == result["summary"]


@pytest.mark.parametrize(
    "mutator",
    [
        lambda d: d.__setitem__("schema_version", True),
        lambda d: d["lua_settable_import"].__setitem__("iat_rva", "0x000011ec"),
        lambda d: d["publications"][0]["setter_stage"].__setitem__("sha256", "0" * 64),
        lambda d: d["publications"][0].__setitem__("stage_between_callback_and_tail", False),
        lambda d: d["publications"][0]["cleanup_instruction"].__setitem__("rva", "0x00001035"),
        lambda d: d["publications"][0]["state_push"].__setitem__("sha256", hashlib.sha256(b"\x50").hexdigest()),
        lambda d: d["publications"][0].__setitem__("setter_call_instruction_sha256", "0" * 64),
        lambda d: d["publications"][0]["esi_preservation_witness"][0].__setitem__("writes_esi", True),
        lambda d: d["publications"][0]["esi_preservation_witness"][0].__setitem__("rva", "0x00001035"),
        lambda d: d["control_flow_graphs"][0]["nodes"][0].__setitem__("successor_rvas", ["0x00001034"]),
        lambda d: d["control_flow_graphs"][0]["nodes"][5].__setitem__("writes_esi", True),
        lambda d: d["publications"][0]["cfg_proof"].__setitem__("stage_dominates_setter_call", False),
        lambda d: d["control_flow_graphs"][0]["nodes"][0].__setitem__("flow_kind", "unsupported_branch"),
        lambda d: d.__setitem__("publications", []),
        lambda d: d["builders"][0].__setitem__("publication_site_count", 2),
        lambda d: d["summary"].__setitem__("matched_indirect_settable_publication_sites", 2),
    ],
)
def test_structure_validator_rejects_adversarial_drift(
    tmp_path: Path, mutator
):
    inputs = _write_inputs(tmp_path)
    altered = copy.deepcopy(_build(inputs))
    mutator(altered)
    with pytest.raises(NativeLuaCClosureIndirectSettablePublicationError):
        validate_native_lua_cclosure_indirect_settable_publication_structure(
            altered, inputs[3], inputs[4], inputs[5], inputs[6], inputs[2]
        )


def test_exact_validator_rejects_binary_or_evidence_drift(tmp_path: Path):
    inputs = _write_inputs(tmp_path)
    result = _build(inputs)
    altered = copy.deepcopy(result)
    altered["publications"][0]["table_index"] = -4
    with pytest.raises(
        NativeLuaCClosureIndirectSettablePublicationError,
        match="differs from exact rebuild",
    ):
        validate_native_lua_cclosure_indirect_settable_publication_census(
            inputs[0], altered, inputs[3], inputs[4], inputs[5], inputs[6], inputs[2], inventory=inputs[1]
        )

    data = bytearray(inputs[0].read_bytes())
    data[0x500] ^= 1
    inputs[0].write_bytes(data)
    with pytest.raises(NativeLuaCClosureIndirectSettablePublicationError):
        validate_native_lua_cclosure_indirect_settable_publication_census(
            inputs[0], result, inputs[3], inputs[4], inputs[5], inputs[6], inputs[2], inventory=inputs[1]
        )


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def test_cli_round_trip_and_immutable_output(tmp_path: Path, capsys, monkeypatch):
    inputs = _write_inputs(tmp_path / "inputs")
    paths = {}
    for name, value in (
        ("inventory", inputs[1]),
        ("program", inputs[2]),
        ("direct", inputs[3]),
        ("callbacks", inputs[4]),
        ("setfield", inputs[5]),
        ("direct_setters", inputs[6]),
    ):
        path = tmp_path / f"{name}.json"
        _write_json(path, value)
        paths[name] = path
    fake_repo = tmp_path / "repo"
    output_root = fake_repo / "data" / "observatory" / "programs"
    output_root.mkdir(parents=True)
    monkeypatch.setattr(cli, "_REPO_ROOT", fake_repo)
    monkeypatch.setattr(cli, "_OUTPUT_ROOT", output_root)
    output = output_root / "synthetic_indirect_settable.json"
    common = [
        "--executable", str(inputs[0]),
        "--inventory", str(paths["inventory"]),
        "--program-facts", str(paths["program"]),
        "--direct-calls", str(paths["direct"]),
        "--callbacks", str(paths["callbacks"]),
        "--setfield-publications", str(paths["setfield"]),
        "--direct-table-setter-publications", str(paths["direct_setters"]),
    ]
    assert cli.main(["build", *common, "--output", str(output)]) == 0
    first = output.read_bytes()
    assert cli.main(["build", *common, "--output", str(output)]) == 0
    assert output.read_bytes() == first
    capsys.readouterr()
    assert cli.main(["verify", *common, "--evidence", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "verified"
    output.write_bytes(first + b" ")
    assert cli.main(["build", *common, "--output", str(output)]) == 1
    assert "refusing to overwrite" in capsys.readouterr().err


def test_committed_artifact_if_present():
    path = (
        _REPO_ROOT
        / "data"
        / "observatory"
        / "programs"
        / "windows_build_13725832_31fe35265598_native_lua_cclosure_indirect_settable_publications.json"
    )
    if not path.exists():
        pytest.skip("committed indirect-settable artifact is not in this tranche yet")
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
    assert artifact["analysis_kind"] == ANALYSIS_KIND
    assert artifact["build_identity"]["executable_sha256"] == (
        "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
    )
    assert artifact["summary"] == {
        "cfg_edges": 265,
        "cfg_instruction_nodes": 260,
        "esi_preservation_witness_instructions": 288,
        "matched_indirect_settable_publication_sites": 3,
        "prior_unmatched_resolved_callback_sites": 6,
        "schema_violations": 0,
        "stage_to_setter_path_nodes": 294,
        "still_unmatched_resolved_callback_sites": 3,
        "unique_registered_callback_targets": 3,
        "unique_registration_builders": 1,
        "unique_setter_stages": 1,
        "unique_table_indices": 2,
    }
    assert [
        (
            item["callback_call_rva"],
            item["callback_entry_rva"],
            item["setter_call_rva"],
            item["table_index"],
            item["cleanup_stack_bytes"],
            item["cfg_proof"]["stage_dominates_callback"],
            item["cfg_proof"]["stage_dominates_setter_call"],
        )
        for item in artifact["publications"]
    ] == [
        ("0x002e69f1", "0x002e6c30", "0x002e6a03", -3, 20, False, True),
        ("0x002e6ba1", "0x002ec220", "0x002e6bb0", -10002, 36, True, True),
        ("0x002e6bc2", "0x002e67b0", "0x002e6bd1", -10002, 28, True, True),
    ]
    assert re.search(rb"[A-Za-z]:[\\/]", payload) is None
