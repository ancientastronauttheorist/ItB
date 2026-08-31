"""Exact and PE-free proofs for native Lua table-key provenance."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROGRAMS = _REPO_ROOT / "data" / "observatory" / "programs"
_PREFIX = "windows_build_13725832_31fe35265598_"
_EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_RAW_SHA256 = "4b37f2206e05b2b881ae6b550df494f908f40eb0beb76b132d3a75364935734e"
_CANONICAL_SHA256 = "8b8cab571c3c8945dae440933107022b35eed28b4c806a35188202bd52073db6"
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import itb_native_lua_cclosure_table_key_provenance as cli  # noqa: E402
import src.observatory.native_lua_cclosure_table_key_provenance as keyprov  # noqa: E402
from src.observatory.native_lua_cclosure_table_key_provenance import (  # noqa: E402
    FAMILY_DEFERRED_TWO,
    FAMILY_DIRECT_TWO,
    FAMILY_GUARDED_ZERO,
    FAMILY_STRAIGHT_ZERO,
    NativeLuaCClosureTableKeyProvenanceError,
    _canonical_sha256,
    build_native_lua_cclosure_table_key_provenance_census,
    validate_native_lua_cclosure_table_key_provenance_census,
    validate_native_lua_cclosure_table_key_provenance_structure,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def committed() -> dict:
    names = {
        "inventory": _REPO_ROOT
        / "data"
        / "observatory"
        / "inventories"
        / f"{_PREFIX}full_decompile_baseline_20260830.json",
        "facts": _PROGRAMS / f"{_PREFIX}program_facts.json",
        "direct": _PROGRAMS / f"{_PREFIX}native_lua_direct_call_census.json",
        "callbacks": _PROGRAMS / f"{_PREFIX}native_lua_cclosure_callbacks.json",
        "setfield": _PROGRAMS / f"{_PREFIX}native_lua_cclosure_setfield_publications.json",
        "direct_setters": _PROGRAMS
        / f"{_PREFIX}native_lua_cclosure_table_setter_publications.json",
        "indirect_setters": _PROGRAMS
        / f"{_PREFIX}native_lua_cclosure_indirect_settable_publications.json",
        "evidence": _PROGRAMS
        / f"{_PREFIX}native_lua_cclosure_table_key_provenance.json",
    }
    return {name: _load(path) for name, path in names.items()} | {"paths": names}


def _structure(values: dict, evidence: dict | None = None) -> dict:
    return validate_native_lua_cclosure_table_key_provenance_structure(
        values["evidence"] if evidence is None else evidence,
        values["direct"],
        values["callbacks"],
        values["setfield"],
        values["direct_setters"],
        values["indirect_setters"],
        values["facts"],
    )


def test_committed_artifact_has_pinned_raw_and_canonical_identity(committed):
    path = committed["paths"]["evidence"]
    payload = path.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == _RAW_SHA256
    assert _canonical_sha256(committed["evidence"]) == _CANONICAL_SHA256


def test_committed_artifact_structurally_verifies_complete_key_partition(committed):
    result = _structure(committed)
    assert result["status"] == "structurally_verified"
    assert result["evidence_sha256"] == _CANONICAL_SHA256
    assert result["summary"] == {
        "table_setter_publication_sites": 7,
        "direct_publication_sites": 4,
        "staged_indirect_publication_sites": 3,
        "unique_key_literals": 4,
        "global_environment_destinations": 5,
        "fresh_unnamed_table_destinations": 2,
        "alternate_global_clear_sites": 1,
        "grammar_family_counts": [
            {"grammar_family": FAMILY_DEFERRED_TWO, "publication_sites": 1},
            {"grammar_family": FAMILY_DIRECT_TWO, "publication_sites": 1},
            {"grammar_family": FAMILY_GUARDED_ZERO, "publication_sites": 1},
            {"grammar_family": FAMILY_STRAIGHT_ZERO, "publication_sites": 4},
        ],
        "schema_violations": 0,
    }


def test_committed_sites_have_exact_keys_families_and_destinations(committed):
    sites = {
        item["callback_call_rva"]: (
            item["key"]["text"],
            item["grammar_family"],
            item["destination"]["class"],
        )
        for item in committed["evidence"]["publications"]
    }
    assert sites == {
        "0x002e69f1": (
            "__gc",
            FAMILY_GUARDED_ZERO,
            "fresh_unnamed_table_at_relative_index_minus_3",
        ),
        "0x002e6ba1": (
            "class",
            FAMILY_STRAIGHT_ZERO,
            "lua51_global_environment_pseudo_index",
        ),
        "0x002e6bc2": (
            "property",
            FAMILY_STRAIGHT_ZERO,
            "lua51_global_environment_pseudo_index",
        ),
        "0x002e6c01": (
            "super",
            FAMILY_STRAIGHT_ZERO,
            "lua51_global_environment_pseudo_index",
        ),
        "0x002ea533": (
            "__gc",
            FAMILY_STRAIGHT_ZERO,
            "fresh_unnamed_table_at_relative_index_minus_3",
        ),
        "0x002eb086": (
            "super",
            FAMILY_DIRECT_TWO,
            "lua51_global_environment_pseudo_index",
        ),
        "0x002eb2a5": (
            "super",
            FAMILY_DEFERRED_TWO,
            "lua51_global_environment_pseudo_index",
        ),
    }


def test_literal_records_are_exact_nonwritable_nul_terminated_ascii(committed):
    literals = {item["text"]: item for item in committed["evidence"]["key_literals"]}
    assert set(literals) == {"__gc", "class", "property", "super"}
    assert {name: item["rva"] for name, item in literals.items()} == {
        "__gc": "0x0043bf84",
        "class": "0x0043bf98",
        "property": "0x0043bf8c",
        "super": "0x0043bfa0",
    }
    for text, item in literals.items():
        assert item["section_name"] == ".rdata"
        assert item["section_writable"] is False
        assert item["byte_length_excluding_nul"] == len(text)
        assert item["nul_terminated_bytes_sha256"] == hashlib.sha256(
            text.encode("ascii") + b"\0"
        ).hexdigest()


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        ("drop_site", "complete ordered partition"),
        ("source_kind", "source-kind"),
        ("key_text", "key literal fields"),
        ("writable_literal", "key literal fields"),
        ("stack", "VM stack trace"),
        ("register_dominance", "CFG proof"),
        ("register_clobber", "CFG proof"),
        ("zero_writer", "zero proof"),
        ("deferred_writer", "deferred proof"),
        ("deferred_stack_store", "deferred proof"),
        ("non_hex_instruction_digest", "CFG node is malformed"),
        ("producer_argument", "does not join stored CFG"),
        ("fresh_identity", "fresh table destination"),
        ("alternate_index", "alternate clear semantics"),
        ("fallthrough_edge", "fallthrough edge"),
    ],
)
def test_structural_validator_rejects_partition_stack_cfg_and_semantic_tamper(
    committed, monkeypatch: pytest.MonkeyPatch, tamper: str, message: str
):
    monkeypatch.setattr(
        keyprov,
        "validate_native_lua_cclosure_indirect_settable_publication_structure",
        lambda *args, **kwargs: {
            "analysis_kind": keyprov.INDIRECT_STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
        },
    )
    evidence = copy.deepcopy(committed["evidence"])
    by_call = {item["callback_call_rva"]: item for item in evidence["publications"]}
    if tamper == "drop_site":
        evidence["publications"].pop()
    elif tamper == "source_kind":
        by_call["0x002e69f1"]["source_publication_kind"] = "direct"
    elif tamper == "key_text":
        by_call["0x002e6ba1"]["key"]["text"] = "klass"
    elif tamper == "writable_literal":
        by_call["0x002e6ba1"]["key"]["section_characteristics"] = "0x80000000"
    elif tamper == "stack":
        by_call["0x002eb086"]["vm_stack_trace"]["before_closure"] = ["K", "U1"]
    elif tamper == "register_dominance":
        by_call["0x002e6ba1"]["key_register_api_proof"]["stage_dominates_call"] = False
    elif tamper == "register_clobber":
        proof = by_call["0x002e6ba1"]["key_register_api_proof"]
        graph = next(
            item
            for item in evidence["control_flow_graphs"]
            if item["caller_entry_rva"] == "0x002e6900"
        )
        node = next(
            item
            for item in graph["nodes"]
            if item["rva"] in proof["stage_to_call_path_rvas"][1:]
        )
        node["writes_ebx"] = True
    elif tamper == "zero_writer":
        proof = by_call["0x002e69f1"]["zero_guard_proof"]
        graph = next(
            item
            for item in evidence["control_flow_graphs"]
            if item["caller_entry_rva"] == "0x002e6900"
        )
        next(
            item for item in graph["nodes"] if item["rva"] in proof["zero_path_rvas"]
        )["writes_esi"] = True
    elif tamper == "deferred_writer":
        proof = by_call["0x002eb2a5"]["deferred_argument_proof"]
        graph = next(
            item
            for item in evidence["control_flow_graphs"]
            if item["caller_entry_rva"] == "0x002eb230"
        )
        next(
            item
            for item in graph["nodes"]
            if item["rva"] in proof["state_to_call_path_rvas"][1:-1]
        )["writes_esp"] = True
    elif tamper == "deferred_stack_store":
        graph = next(
            item
            for item in evidence["control_flow_graphs"]
            if item["caller_entry_rva"] == "0x002eb230"
        )
        next(item for item in graph["nodes"] if item["rva"] == "0x002eb265")[
            "sha256"
        ] = hashlib.sha256(b"\x89\x04\x24").hexdigest()
    elif tamper == "non_hex_instruction_digest":
        graph = next(
            item
            for item in evidence["control_flow_graphs"]
            if item["caller_entry_rva"] == "0x002ea4e0"
        )
        graph["nodes"][-1]["sha256"] = "z" * 64
    elif tamper == "producer_argument":
        by_call["0x002eb086"]["upvalue_producers"][0]["argument_push"][
            "sha256"
        ] = "0" * 64
    elif tamper == "fresh_identity":
        by_call["0x002ea533"]["destination"]["semantic_table_identity"] = "metatable"
    elif tamper == "alternate_index":
        by_call["0x002eb2a5"]["alternate_global_clear"]["table_index"] = -3
    else:
        graph = next(
            item
            for item in evidence["control_flow_graphs"]
            if item["caller_entry_rva"] == "0x002ea4e0"
        )
        node = next(item for item in graph["nodes"] if item["flow_kind"] == "fallthrough")
        node["successor_rvas"] = [graph["nodes"][-1]["rva"]]

    with pytest.raises(NativeLuaCClosureTableKeyProvenanceError, match=message):
        _structure(committed, evidence)


@pytest.fixture(scope="module")
def exact_real(committed):
    if not _EXE.is_file():
        pytest.skip("exact installed Breach.exe is unavailable")
    if hashlib.sha256(_EXE.read_bytes()).hexdigest() != _EXE_SHA256:
        pytest.skip("installed Breach.exe is not the sealed build")
    rebuilt = build_native_lua_cclosure_table_key_provenance_census(
        _EXE,
        committed["direct"],
        committed["callbacks"],
        committed["setfield"],
        committed["direct_setters"],
        committed["indirect_setters"],
        committed["facts"],
        inventory=committed["inventory"],
    )
    return rebuilt


def test_exact_real_build_reproduces_committed_artifact(committed, exact_real):
    assert exact_real == committed["evidence"]
    verification = validate_native_lua_cclosure_table_key_provenance_census(
        _EXE,
        committed["evidence"],
        committed["direct"],
        committed["callbacks"],
        committed["setfield"],
        committed["direct_setters"],
        committed["indirect_setters"],
        committed["facts"],
        inventory=committed["inventory"],
    )
    assert verification["status"] == "verified"
    assert verification["evidence_sha256"] == _CANONICAL_SHA256


def test_exact_validator_rejects_structurally_coherent_binary_different_key(
    committed, exact_real
):
    evidence = copy.deepcopy(exact_real)
    publication = evidence["publications"][1]
    publication["key"]["text"] = "klass"
    publication["key"]["byte_length_excluding_nul"] = 5
    publication["key"]["nul_terminated_bytes_sha256"] = hashlib.sha256(
        b"klass\0"
    ).hexdigest()
    for literal in evidence["key_literals"]:
        if literal["text"] == "class":
            literal.update(publication["key"])
    evidence["keys"] = [item for item in evidence["keys"] if item["key"] != "class"]
    evidence["keys"].append(
        {
            "key": "klass",
            "publication_site_count": 1,
            "callback_call_rvas": [publication["callback_call_rva"]],
            "callback_entry_rvas": [publication["callback_entry_rva"]],
            "destination_classes": [publication["destination"]["class"]],
        }
    )
    evidence["keys"].sort(key=lambda item: item["key"])
    assert _structure(committed, evidence)["status"] == "structurally_verified"
    with pytest.raises(
        NativeLuaCClosureTableKeyProvenanceError,
        match="differs from exact rebuild",
    ):
        validate_native_lua_cclosure_table_key_provenance_census(
            _EXE,
            evidence,
            committed["direct"],
            committed["callbacks"],
            committed["setfield"],
            committed["direct_setters"],
            committed["indirect_setters"],
            committed["facts"],
            inventory=committed["inventory"],
        )


def test_cli_parser_exposes_full_prerequisite_chain():
    parser = cli.build_parser()
    build = parser.parse_args(
        [
            "build",
            "--executable",
            "game.exe",
            "--inventory",
            "inventory.json",
            "--program-facts",
            "facts.json",
            "--direct-calls",
            "direct.json",
            "--callbacks",
            "callbacks.json",
            "--setfield-publications",
            "setfield.json",
            "--direct-table-setter-publications",
            "direct-setters.json",
            "--indirect-settable-publications",
            "indirect-setters.json",
        ]
    )
    assert build.command == "build"
    assert build.direct_table_setter_publications.name == "direct-setters.json"
    assert build.indirect_settable_publications.name == "indirect-setters.json"
