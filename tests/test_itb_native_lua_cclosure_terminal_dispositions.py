from __future__ import annotations

import copy
import hashlib
import json
import re
import struct
from pathlib import Path

import pytest

from scripts import itb_native_lua_cclosure_terminal_dispositions as terminal_cli
from src.observatory import native_lua_cclosure_terminal_dispositions as terminal
from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_terminal_dispositions import (
    ANALYSIS_KIND,
    HOLDER_KIND,
    RETURN_KIND,
    NativeLuaCClosureTerminalDispositionError,
    build_native_lua_cclosure_terminal_disposition_census,
    encode_native_lua_cclosure_terminal_disposition_census,
    validate_native_lua_cclosure_terminal_disposition_census,
    validate_native_lua_cclosure_terminal_disposition_structure,
)
from src.observatory.native_lua_direct_calls import CALL_FORM
from src.observatory.program_facts import build_program_facts


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROGRAM_ROOT = _REPO_ROOT / "data" / "observatory" / "programs"
_EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
_PREFIX = "windows_build_13725832_31fe35265598_"
_EXPECTED_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_COMMITTED_RAW_SHA256 = (
    "99644fed0a247caa45ee914375d2969377d9913fcf825a56d3fdecc671228731"
)
_COMMITTED_CANONICAL_SHA256 = (
    "74b762e486611a6dc71325276d9e8e92b7894de30f99bacf9e301e894c85bb85"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


_IMAGE_BASE = 0x00400000
_SYNTHETIC_IATS = {
    "lua_pushcclosure": 0x00001800,
    "lua_rawgeti": 0x00001804,
    "lua_pushvalue": 0x00001808,
    "luaL_ref": 0x0000180C,
    "lua_settop": 0x00001810,
}


def _synthetic_pe(chunks: dict[int, bytes]) -> bytes:
    data = bytearray(0x1400)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 0x84, 0x014C, 1, 0x12345678, 0, 0, 0xE0, 0x010F)
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x10B)
    struct.pack_into("<I", data, optional + 16, min(chunks))
    struct.pack_into("<I", data, optional + 28, _IMAGE_BASE)
    struct.pack_into("<I", data, optional + 32, 0x1000)
    struct.pack_into("<I", data, optional + 36, 0x200)
    struct.pack_into("<I", data, optional + 56, 0x2000)
    struct.pack_into("<I", data, optional + 60, 0x200)
    struct.pack_into("<I", data, optional + 92, 16)
    section = optional + 0xE0
    data[section : section + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, section + 8, 0x1000, 0x1000, 0x1000, 0x200)
    struct.pack_into("<I", data, section + 36, 0x60000020)
    for rva, code in chunks.items():
        offset = 0x200 + rva - 0x1000
        data[offset : offset + len(code)] = code
    return bytes(data)


def _synthetic_inventory(data: bytes) -> dict:
    return {
        "platform": "windows",
        "label": "synthetic terminal-disposition matcher",
        "executable": {"path": "Breach.exe", "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "format": "pe", "architecture": "x86"},
        "steam": {"build_id": "123", "installed_depots": [{"depot_id": "590381", "manifest": "456"}], "evidence": {"sha256": "d" * 64}},
        "content": {"scripts": {"revision_sha256": "a" * 64}, "maps": {"revision_sha256": "b" * 64}},
        "native_libraries": [{"path": "lua5.1.dll", "size": 7, "sha256": "c" * 64, "format": "pe", "architecture": "x86"}],
    }


def _synthetic_facts_text(data: bytes, functions: list[tuple[int, str, bytes]]) -> str:
    lines = [
        "meta\tformat_version\t1", "meta\tghidra_version\t12.1.3",
        "meta\tprogram_name\tBreach.exe", "meta\tlanguage_id\tx86:LE:32:default",
        "meta\tcompiler_spec_id\twindows", f"meta\timage_base\t0x{_IMAGE_BASE:08x}",
        f"meta\tfunction_count\t{len(functions)}", f"meta\trange_count\t{len(functions)}",
        "meta\tdirect_internal_call_count\t0", "meta\tomitted_call_target_count\t0",
    ]
    for rva, name, code in functions:
        offset = 0x200 + rva - 0x1000
        digest = hashlib.sha256(data[offset : offset + len(code)]).hexdigest()
        lines.append(f"function\t0x{rva:08x}\t{name}\tGlobal\tUSER_DEFINED\t0\t{len(code)}\t{digest}")
    for rva, _name, code in functions:
        lines.append(f"range\t0x{rva:08x}\t0x{rva:08x}\t{len(code)}")
    lines.append("")
    return "\n".join(lines)


def _import_records(counts: dict[str, int]) -> list[dict]:
    return [
        {"name": name, "library": "lua5.1.dll", "iat_rva": terminal._hex(iat), "hint": index, "direct_call_sites": counts.get(name, 0), "direct_calling_functions": counts.get(name, 0)}
        for index, (name, iat) in enumerate(_SYNTHETIC_IATS.items())
    ]


def _direct_call(call_rva: int, name: str, encoded: bytes) -> dict:
    return {
        "call_rva": terminal._hex(call_rva), "iat_rva": terminal._hex(_SYNTHETIC_IATS[name]),
        "library": "lua5.1.dll", "import_name": name, "call_form": CALL_FORM,
        "instruction_size": len(encoded), "instruction_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _callback_source(facts: dict, caller: int, call: int, callback: int, n: int, state_opcode: int) -> dict:
    by_entry = {int(item["entry_rva"], 16): item for item in facts["functions"]}
    call_bytes = b"\xff\x15" + struct.pack("<I", _IMAGE_BASE + _SYNTHETIC_IATS["lua_pushcclosure"])
    return {
        "argument_form": "x86_cdecl_pushes_n_callback_imm32_state_register",
        "call_instruction_sha256": hashlib.sha256(call_bytes).hexdigest(),
        "call_rva": terminal._hex(call),
        "callback_atlas_record_sha256": atlas_record_sha256(by_entry[callback]),
        "callback_entry_rva": terminal._hex(callback),
        "caller_atlas_record_sha256": atlas_record_sha256(by_entry[caller]),
        "caller_entry_rva": terminal._hex(caller),
        "iat_rva": terminal._hex(_SYNTHETIC_IATS["lua_pushcclosure"]),
        "import_name": "lua_pushcclosure", "library": "lua5.1.dll",
        "literal_upvalue_count": n, "self_callback": False,
        "state_push": {"rva": terminal._hex(call - 1), "size": 1, "sha256": hashlib.sha256(bytes([state_opcode])).hexdigest()},
        "upvalue_argument_kind": "immediate",
    }


def _synthetic_prerequisites(tmp_path: Path, kind: str, mutation: str | None = None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    callback_code = b"\x31\xc0\xc3"
    call_pushclosure = b"\xff\x15" + struct.pack("<I", _IMAGE_BASE + _SYNTHETIC_IATS["lua_pushcclosure"])
    imports_for_template = {name: {"iat_rva": terminal._hex(iat)} for name, iat in _SYNTHETIC_IATS.items()}
    direct_specs: list[tuple[int, str, bytes]] = []
    if kind == "return":
        prefix = b"\x6a\x02\x68" + struct.pack("<I", _IMAGE_BASE + 0x1080) + b"\x56" + call_pushclosure
        tail = b"".join(encoded for _, encoded in terminal.RETURN_EPILOGUES["simple_saved_edi_esi_ebp"])
        if mutation == "eax":
            tail = tail[:4] + b"\x00" + tail[5:]
        elif mutation == "branch":
            tail = b"\xeb\x01\x90" + tail[3:]
        elif mutation == "extra_call":
            tail = tail[:3] + b"\xe8\x00\x00\x00\x00" + tail[8:]
        elif mutation == "state":
            prefix = prefix[:7] + b"\x57" + prefix[8:]
        caller_code = prefix + tail
        witness_code = b"\x6a\x00\x68" + struct.pack("<I", _IMAGE_BASE + 0x1020) + b"\x57" + call_pushclosure + b"\xc3"
        functions = [(0x1020, "returning_callback", caller_code), (0x1080, "inner_callback", callback_code), (0x10A0, "callback_constructor", witness_code)]
        chunks = {rva: code for rva, _, code in functions}
    elif kind == "holder":
        template = terminal._registry_template(_IMAGE_BASE, {"callback_entry_rva": "0x000010c0"}, imports_for_template)
        encoded = [value for _, value in template]
        role_index = {role: index for index, (role, _) in enumerate(template)}
        if mutation == "state":
            encoded[role_index["closure_state_push"]] = b"\x56"
        elif mutation == "index":
            encoded[role_index["ref_registry_index"]] = b"\x68\xf1\xd8\xff\xff"
        elif mutation == "import":
            encoded[role_index["pushvalue"]] = b"\xff\x15" + struct.pack("<I", _IMAGE_BASE + _SYNTHETIC_IATS["lua_rawgeti"])
        elif mutation == "base":
            encoded[role_index["store_holder_state"]] = b"\x89\x3f"
        elif mutation == "store":
            encoded[role_index["store_holder_reference"]] = b"\x89\x03\x90"
        elif mutation == "settop":
            encoded[role_index["lua_settop"]] = b"\xff\x15" + struct.pack("<I", _IMAGE_BASE + _SYNTHETIC_IATS["lua_pushvalue"])
        caller_code = b"\x55\x8b\xec\x53" + b"".join(encoded)
        functions = [(0x1020, "holder_constructor", caller_code), (0x10C0, "held_callback", callback_code)]
        chunks = {rva: code for rva, _, code in functions}
    else:  # pragma: no cover - test helper contract
        raise AssertionError(kind)
    data = _synthetic_pe(chunks)
    executable = tmp_path / "Breach.exe"; executable.write_bytes(data)
    inventory = _synthetic_inventory(data)
    facts_path = tmp_path / "facts.tsv"; facts_path.write_text(_synthetic_facts_text(data, functions), encoding="utf-8", newline="\n")
    facts = build_program_facts(executable, facts_path, inventory=inventory)
    identity = facts["identity"]
    if kind == "return":
        first_state = 0x57 if mutation == "state" else 0x56
        sources = [_callback_source(facts, 0x1020, 0x1028, 0x1080, 2, first_state), _callback_source(facts, 0x10A0, 0x10A8, 0x1020, 0, 0x57)]
        direct_specs = [(0x1028, "lua_pushcclosure", call_pushclosure), (0x10A8, "lua_pushcclosure", call_pushclosure)]
    else:
        template = terminal._registry_template(_IMAGE_BASE, {"callback_entry_rva": "0x000010c0"}, imports_for_template)
        rva = 0x1024; role_rvas = {}
        encoded_by_role = {}
        cursor = 0x1024
        for role, expected in template:
            role_rvas[role] = cursor
            size = len(expected)
            actual = caller_code[cursor - 0x1020 : cursor - 0x1020 + size]
            encoded_by_role[role] = actual
            cursor += size
        callback_call = role_rvas["pushcclosure"]
        state_opcode = encoded_by_role["closure_state_push"][0]
        sources = [_callback_source(facts, 0x1020, callback_call, 0x10C0, 2, state_opcode)]
        names = {"first_rawgeti": "lua_rawgeti", "second_rawgeti": "lua_rawgeti", "pushcclosure": "lua_pushcclosure", "pushvalue": "lua_pushvalue", "luaL_ref": "luaL_ref", "lua_settop": "lua_settop"}
        direct_specs = [(role_rvas[role], name, encoded_by_role[role]) for role, name in names.items()]
    counts = {}
    for _, name, _ in direct_specs:
        counts[name] = counts.get(name, 0) + 1
    direct_records = []
    by_caller = {source["caller_entry_rva"]: source["caller_atlas_record_sha256"] for source in sources}
    for caller_entry, caller_hash in by_caller.items():
        caller = int(caller_entry, 16)
        calls = [_direct_call(rva, name, encoded) for rva, name, encoded in direct_specs if (caller == 0x1020 and rva < 0x1080) or (caller == 0x10A0 and rva >= 0x10A0)]
        direct_records.append({"entry_rva": caller_entry, "atlas_record_sha256": caller_hash, "direct_call_count": len(calls), "import_names": sorted({call["import_name"] for call in calls}), "direct_lua_import_calls": calls})
    direct = {"schema_version": 1, "analysis_kind": "pe_native_lua_direct_import_call_census", "build_identity": identity, "atlas": {"analysis_kind": "pe_ghidra_program_facts", "canonical_sha256": terminal._canonical_sha256(facts), "function_count": len(functions)}, "lua_imports": _import_records(counts), "records": direct_records}
    callbacks = {"schema_version": 1, "analysis_kind": "pe_native_lua_immediate_cclosure_callback_census", "build_identity": identity, "resolved_sites": sources}
    frontier = [{"callback_call_rva": source["call_rva"], "caller_entry_rva": source["caller_entry_rva"], "caller_atlas_record_sha256": source["caller_atlas_record_sha256"], "callback_entry_rva": source["callback_entry_rva"], "callback_atlas_record_sha256": source["callback_atlas_record_sha256"], "resolution": "no_exact_contiguous_direct_table_setter_publication"} for source in sources]
    table = {"schema_version": 1, "analysis_kind": "pe_native_lua_immediate_cclosure_direct_table_setter_publication_census", "build_identity": identity, "still_unmatched_resolved_sites": frontier, "summary": {"still_unmatched_resolved_callback_sites": len(frontier)}}
    return executable, inventory, facts, direct, callbacks, {}, table


def _build_synthetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, mutation: str | None = None):
    inputs = _synthetic_prerequisites(tmp_path, kind, mutation)
    table = inputs[6]
    monkeypatch.setattr(
        terminal,
        "validate_native_lua_cclosure_table_setter_publication_census",
        lambda *args, **kwargs: {"evidence_sha256": terminal._canonical_sha256(table)},
    )
    return build_native_lua_cclosure_terminal_disposition_census(
        inputs[0], inputs[3], inputs[4], inputs[5], inputs[6], inputs[2], inventory=inputs[1]
    )


@pytest.fixture(scope="module")
def real_inputs():
    paths = {
        "inventory": _REPO_ROOT / "data" / "observatory" / "inventories" / f"{_PREFIX}full_decompile_baseline_20260830.json",
        "facts": _PROGRAM_ROOT / f"{_PREFIX}program_facts.json",
        "direct": _PROGRAM_ROOT / f"{_PREFIX}native_lua_direct_call_census.json",
        "callbacks": _PROGRAM_ROOT / f"{_PREFIX}native_lua_cclosure_callbacks.json",
        "setfield": _PROGRAM_ROOT / f"{_PREFIX}native_lua_cclosure_setfield_publications.json",
        "table": _PROGRAM_ROOT / f"{_PREFIX}native_lua_cclosure_table_setter_publications.json",
    }
    if not _EXE.is_file() or any(not path.is_file() for path in paths.values()):
        pytest.skip("exact installed build or committed prerequisites are unavailable")
    if hashlib.sha256(_EXE.read_bytes()).hexdigest() != _EXPECTED_EXE_SHA256:
        pytest.skip("installed Breach.exe is not the sealed build")
    values = {name: _load(path) for name, path in paths.items()}
    result = build_native_lua_cclosure_terminal_disposition_census(
        _EXE,
        values["direct"],
        values["callbacks"],
        values["setfield"],
        values["table"],
        values["facts"],
        inventory=values["inventory"],
    )
    return values, result


def _structure(values: dict, evidence: dict):
    return validate_native_lua_cclosure_terminal_disposition_structure(
        evidence,
        values["direct"],
        values["callbacks"],
        values["setfield"],
        values["table"],
        values["facts"],
    )


def test_synthetic_return_tail_matches_exact_builder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    result = _build_synthetic(tmp_path, monkeypatch, "return")
    assert [(item["callback_call_rva"], item["disposition_kind"]) for item in result["dispositions"]] == [("0x00001028", RETURN_KIND)]
    assert [item["callback_call_rva"] for item in result["still_unmatched_resolved_sites"]] == ["0x000010a8"]
    assert result["dispositions"][0]["caller_callback_target_witness"]["construction_call_rva"] == "0x000010a8"


@pytest.mark.parametrize("mutation", ["eax", "branch", "extra_call", "state"])
def test_synthetic_return_tail_near_misses_remain_unmatched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
):
    result = _build_synthetic(tmp_path, monkeypatch, "return", mutation)
    assert result["dispositions"] == []
    assert len(result["still_unmatched_resolved_sites"]) == 2


def test_synthetic_registry_holder_matches_exact_builder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    result = _build_synthetic(tmp_path, monkeypatch, "holder")
    assert [(item["callback_call_rva"], item["disposition_kind"]) for item in result["dispositions"]] == [(result["dispositions"][0]["callback_call_rva"], HOLDER_KIND)]
    assert result["still_unmatched_resolved_sites"] == []


@pytest.mark.parametrize("mutation", ["state", "index", "import", "base", "store", "settop"])
def test_synthetic_registry_holder_near_misses_remain_unmatched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
):
    result = _build_synthetic(tmp_path, monkeypatch, "holder", mutation)
    assert result["dispositions"] == []
    assert len(result["still_unmatched_resolved_sites"]) == 1


def test_exact_real_build_has_complete_six_site_partition(real_inputs):
    values, result = real_inputs
    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["summary"] == {
        "prior_unmatched_resolved_callback_sites": 6,
        "matched_terminal_disposition_sites": 3,
        "still_unmatched_resolved_callback_sites": 3,
        "lua_callback_single_result_sites": 2,
        "registry_reference_holder_sites": 1,
        "unique_disposition_callers": 3,
        "unique_disposition_callback_targets": 2,
        "schema_violations": 0,
    }
    assert [
        (item["callback_call_rva"], item["disposition_kind"], item.get("epilogue_kind"))
        for item in result["dispositions"]
    ] == [
        ("0x000579a2", HOLDER_KIND, None),
        ("0x002e67fa", RETURN_KIND, "simple_saved_edi_esi_ebp"),
        ("0x002ec328", RETURN_KIND, "seh_saved_edi_esi_ebx_frame"),
    ]
    assert [item["callback_call_rva"] for item in result["still_unmatched_resolved_sites"]] == [
        "0x002e69f1", "0x002e6ba1", "0x002e6bc2"
    ]
    assert _structure(values, result)["status"] == "structurally_verified"


def test_return_dispositions_have_independent_callback_target_witnesses(real_inputs):
    _, result = real_inputs
    returns = [item for item in result["dispositions"] if item["disposition_kind"] == RETURN_KIND]
    assert [(item["caller_entry_rva"], item["caller_callback_target_witness"]["construction_call_rva"]) for item in returns] == [
        ("0x002e67b0", "0x002e6bc2"),
        ("0x002ec220", "0x002e6ba1"),
    ]
    for item in returns:
        roles = [fact["role"] for fact in item["reviewed_sequence"]]
        assert roles[1] == "lua_result_count_one"
        assert roles[-1] == "return"
        assert all("branch" not in role and "lua_call" not in role for role in roles)


def test_registry_holder_reconstructs_all_state_indices_stores_and_calls(real_inputs):
    _, result = real_inputs
    item = next(item for item in result["dispositions"] if item["disposition_kind"] == HOLDER_KIND)
    assert (item["state_register"], item["holder_register"], item["registry_index"], item["initial_reference_sentinel"], item["returned_register"]) == ("edi", "ebx", -10000, -2, "ebx")
    roles = [fact["role"] for fact in item["reviewed_sequence"]]
    assert roles == [role for role, _ in terminal._registry_template(0x00400000, {"callback_entry_rva": "0x002eaa50"}, {name: imp for name, imp in terminal._direct_calls(real_inputs[0]["direct"])[0].items()})]
    assert roles.index("store_holder_noref") < roles.index("pushvalue")
    assert roles.index("store_holder_reference") < roles.index("lua_settop")


def test_deterministic_encoding_omits_code_and_paths(real_inputs):
    _, result = real_inputs
    rendered = encode_native_lua_cclosure_terminal_disposition_census(result)
    assert rendered == encode_native_lua_cclosure_terminal_disposition_census(result)
    assert re.search(r"[A-Za-z]:[\\/]", rendered) is None
    for forbidden in ("instruction_bytes", "mnemonic", "op_str", "pseudocode", "decompiler"):
        assert forbidden not in rendered


@pytest.mark.parametrize(
    ("mutator", "description"),
    [
        (lambda d: d.__setitem__("schema_version", True), "boolean schema"),
        (lambda d: d["summary"].__setitem__("matched_terminal_disposition_sites", 4), "summary aggregate"),
        (lambda d: d["callers"][0].__setitem__("disposition_site_count", 2), "caller aggregate"),
        (lambda d: d["dispositions"][1].__setitem__("result_count", 0), "wrong Lua result count"),
        (lambda d: d["dispositions"][1].__setitem__("result_count", True), "boolean Lua result count"),
        (lambda d: d["dispositions"][1].__setitem__("epilogue_kind", "unreviewed"), "unreviewed epilogue"),
        (lambda d: d["dispositions"][1]["reviewed_sequence"][1].__setitem__("sha256", "0" * 64), "EAX clobber or hash drift"),
        (lambda d: d["dispositions"][1]["reviewed_sequence"][2].__setitem__("role", "branch"), "intervening branch"),
        (lambda d: d["dispositions"][1]["caller_callback_target_witness"].__setitem__("construction_call_rva", "0x002e69f1"), "caller not callback target"),
        (lambda d: d["dispositions"][0].__setitem__("state_register", "esi"), "registry state mismatch"),
        (lambda d: d["dispositions"][0].__setitem__("holder_register", "edi"), "registry base mismatch"),
        (lambda d: d["dispositions"][0].__setitem__("registry_index", -9999), "wrong registry index"),
        (lambda d: d["dispositions"][0].__setitem__("initial_reference_sentinel", -1), "wrong holder sentinel"),
        (lambda d: d["dispositions"][0].__setitem__("returned_register", "eax"), "wrong return register"),
        (lambda d: d["dispositions"][0]["reviewed_sequence"][19].__setitem__("sha256", "1" * 64), "wrong pushvalue API"),
        (lambda d: d["dispositions"][0]["reviewed_sequence"][25].__setitem__("sha256", "2" * 64), "wrong reference store"),
        (lambda d: d["dispositions"][0]["reviewed_sequence"][26].__setitem__("sha256", "3" * 64), "wrong settop"),
        (lambda d: d["dispositions"][0]["reviewed_sequence"][20].__setitem__("rva", "0x000579bb"), "range or contiguity drift"),
        (lambda d: d.__setitem__("still_unmatched_resolved_sites", []), "incomplete partition"),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_structural_validator_rejects_adversarial_drift(real_inputs, mutator, description):
    values, result = real_inputs
    altered = copy.deepcopy(result)
    mutator(altered)
    with pytest.raises(NativeLuaCClosureTerminalDispositionError) as caught:
        _structure(values, altered)
    assert caught.value is not None, description


def test_exact_validator_rejects_semantically_differing_evidence(real_inputs):
    values, result = real_inputs
    verification = validate_native_lua_cclosure_terminal_disposition_census(
        _EXE, result, values["direct"], values["callbacks"], values["setfield"],
        values["table"], values["facts"], inventory=values["inventory"]
    )
    assert verification["status"] == "verified"
    altered = copy.deepcopy(result)
    altered["dispositions"][1]["result_count"] = 0
    with pytest.raises(NativeLuaCClosureTerminalDispositionError, match="differs from exact rebuild"):
        validate_native_lua_cclosure_terminal_disposition_census(
            _EXE, altered, values["direct"], values["callbacks"], values["setfield"],
            values["table"], values["facts"], inventory=values["inventory"]
        )


def test_committed_artifact_if_present(real_inputs):
    values, _ = real_inputs
    path = _PROGRAM_ROOT / f"{_PREFIX}native_lua_cclosure_terminal_dispositions.json"
    if not path.exists():
        pytest.skip("terminal-disposition artifact has not been generated yet")
    evidence = _load(path)
    assert evidence["analysis_kind"] == ANALYSIS_KIND
    assert evidence["summary"]["matched_terminal_disposition_sites"] == 3
    assert _structure(values, evidence)["status"] == "structurally_verified"


def test_committed_artifact_identity_if_present():
    path = _PROGRAM_ROOT / f"{_PREFIX}native_lua_cclosure_terminal_dispositions.json"
    if not path.exists():
        pytest.skip("terminal-disposition artifact has not been generated yet")
    payload = path.read_bytes()
    evidence = json.loads(payload)
    canonical = (
        json.dumps(
            evidence,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    assert hashlib.sha256(payload).hexdigest() == _COMMITTED_RAW_SHA256
    assert hashlib.sha256(canonical).hexdigest() == _COMMITTED_CANONICAL_SHA256
    assert evidence["build_identity"]["executable_sha256"] == _EXPECTED_EXE_SHA256
    assert evidence["summary"] == {
        "lua_callback_single_result_sites": 2,
        "matched_terminal_disposition_sites": 3,
        "prior_unmatched_resolved_callback_sites": 6,
        "registry_reference_holder_sites": 1,
        "schema_violations": 0,
        "still_unmatched_resolved_callback_sites": 3,
        "unique_disposition_callback_targets": 2,
        "unique_disposition_callers": 3,
    }
    assert [
        (
            item["disposition_kind"],
            item["callback_call_rva"],
            item["caller_entry_rva"],
            item["callback_entry_rva"],
        )
        for item in evidence["dispositions"]
    ] == [
        ("registry_reference_holder", "0x000579a2", "0x00057970", "0x002eaa50"),
        ("lua_callback_single_result", "0x002e67fa", "0x002e67b0", "0x002eaa50"),
        ("lua_callback_single_result", "0x002ec328", "0x002ec220", "0x002ec110"),
    ]


def _cli_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: dict):
    repo = tmp_path / "repo"
    output_root = repo / "data" / "observatory" / "programs"
    output_root.mkdir(parents=True)
    monkeypatch.setattr(terminal_cli, "_REPO_ROOT", repo)
    monkeypatch.setattr(terminal_cli, "_OUTPUT_ROOT", output_root)
    monkeypatch.setattr(terminal_cli, "build_native_lua_cclosure_terminal_disposition_census", lambda *args, **kwargs: copy.deepcopy(result))
    verification = {"schema_version": 1, "analysis_kind": "synthetic_verification", "status": "verified", "build_identity": result["build_identity"], "evidence_sha256": terminal._canonical_sha256(result), "summary": result["summary"]}
    monkeypatch.setattr(terminal_cli, "validate_native_lua_cclosure_terminal_disposition_census", lambda *args, **kwargs: verification)
    paths = {}
    for name in ("inventory", "program", "direct", "callbacks", "setfield", "table"):
        path = tmp_path / f"{name}.json"
        path.write_text("{}\n", encoding="utf-8", newline="\n")
        paths[name] = path
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(b"synthetic")
    output = output_root / "terminal.json"
    build_args = ["build", "--executable", str(executable), "--inventory", str(paths["inventory"]), "--program-facts", str(paths["program"]), "--direct-calls", str(paths["direct"]), "--callbacks", str(paths["callbacks"]), "--setfield-publications", str(paths["setfield"]), "--table-setter-publications", str(paths["table"]), "--output", str(output)]
    verify_args = ["verify", "--executable", str(executable), "--inventory", str(paths["inventory"]), "--program-facts", str(paths["program"]), "--direct-calls", str(paths["direct"]), "--callbacks", str(paths["callbacks"]), "--setfield-publications", str(paths["setfield"]), "--table-setter-publications", str(paths["table"]), "--evidence", str(output)]
    return output_root, output, build_args, verify_args


def test_cli_first_write_idempotent_reuse_differing_refusal_and_verify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    result = _build_synthetic(tmp_path / "matcher", monkeypatch, "return")
    _root, output, build_args, verify_args = _cli_fixture(tmp_path / "cli", monkeypatch, result)
    assert terminal_cli.main(build_args) == 0
    first = output.read_bytes(); before = output.stat().st_mtime_ns
    assert terminal_cli.main(build_args) == 0
    assert output.read_bytes() == first and output.stat().st_mtime_ns == before
    assert terminal_cli.main(verify_args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "verified"
    altered = copy.deepcopy(result)
    altered["summary"]["matched_terminal_disposition_sites"] += 1
    foreign = encode_native_lua_cclosure_terminal_disposition_census(altered).encode("utf-8")
    output.write_bytes(foreign)
    assert terminal_cli.main(build_args) == 1
    assert "differing terminal-disposition evidence" in capsys.readouterr().err
    assert output.read_bytes() == foreign


def test_cli_existing_output_confirmation_detects_content_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    result = _build_synthetic(tmp_path / "matcher", monkeypatch, "return")
    _root, output, build_args, _verify_args = _cli_fixture(tmp_path / "cli", monkeypatch, result)
    assert terminal_cli.main(build_args) == 0
    altered = copy.deepcopy(result)
    altered["summary"]["matched_terminal_disposition_sites"] += 1
    raced_payload = encode_native_lua_cclosure_terminal_disposition_census(altered).encode("utf-8")
    original_read = terminal_cli._read_json_document
    destination_reads = 0

    def race_read(path, label):
        nonlocal destination_reads
        value, payload = original_read(path, label)
        if Path(path) == output:
            destination_reads += 1
            if destination_reads == 1:
                output.write_bytes(raced_payload)
        return value, payload

    monkeypatch.setattr(terminal_cli, "_read_json_document", race_read)
    assert terminal_cli.main(build_args) == 1
    assert destination_reads == 2
    assert "changed during comparison" in capsys.readouterr().err
    assert output.read_bytes() == raced_payload


def test_cli_output_root_path_and_reparse_protections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    result = _build_synthetic(tmp_path / "matcher", monkeypatch, "return")
    output_root, _output, build_args, _verify_args = _cli_fixture(tmp_path / "cli", monkeypatch, result)
    outside = tmp_path / "outside.json"
    outside_args = list(build_args)
    outside_args[-1] = str(outside)
    assert terminal_cli.main(outside_args) == 1
    assert "direct child" in capsys.readouterr().err
    assert not outside.exists()
    monkeypatch.setattr(terminal_cli, "_is_reparse", lambda _info: True)
    assert terminal_cli.main(build_args) == 1
    assert "real directory" in capsys.readouterr().err
    assert output_root.is_dir()
