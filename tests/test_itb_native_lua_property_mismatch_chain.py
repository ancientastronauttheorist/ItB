from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import itb_native_lua_property_mismatch_chain as mismatch_cli
from src.observatory import native_lua_property_mismatch_chain as mismatch_chain
from src.observatory.native_lua_property_mismatch_chain import (
    ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND,
    NativeLuaPropertyMismatchChainError,
    build_native_lua_property_mismatch_chain,
    encode_native_lua_property_mismatch_chain,
    validate_native_lua_property_mismatch_chain,
    validate_native_lua_property_mismatch_chain_structure,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROGRAM_ROOT = _REPO_ROOT / "data" / "observatory" / "programs"
_INVENTORY_ROOT = _REPO_ROOT / "data" / "observatory" / "inventories"
_PREFIX = "windows_build_13725832_31fe35265598_"
_EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_RAW_SHA256 = "dcae907285c435a8ac178a65bb4c1edb341f0b6cfdd35597b5d2cd57306bdb63"
_CANONICAL_SHA256 = "49276d63020a536bdd456d3f36667428afff2b3d8b15e479eb5444c241b23263"
_CONSUMER_SHA256 = "2c6569177595cbdc8abdbe4ba1bdc3d09f4bb0d15dac5d280c16ba3dfcc2d3b9"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def real_inputs() -> dict[str, dict]:
    paths = {
        "inventory": _INVENTORY_ROOT / f"{_PREFIX}full_decompile_baseline_20260830.json",
        "facts": _PROGRAM_ROOT / f"{_PREFIX}program_facts.json",
        "direct": _PROGRAM_ROOT / f"{_PREFIX}native_lua_direct_call_census.json",
        "callbacks": _PROGRAM_ROOT / f"{_PREFIX}native_lua_cclosure_callbacks.json",
        "setfield": _PROGRAM_ROOT / f"{_PREFIX}native_lua_cclosure_setfield_publications.json",
        "direct_table": _PROGRAM_ROOT / f"{_PREFIX}native_lua_cclosure_table_setter_publications.json",
        "indirect": _PROGRAM_ROOT / f"{_PREFIX}native_lua_cclosure_indirect_settable_publications.json",
        "table_keys": _PROGRAM_ROOT / f"{_PREFIX}native_lua_cclosure_table_key_provenance.json",
        "terminal": _PROGRAM_ROOT / f"{_PREFIX}native_lua_cclosure_terminal_dispositions.json",
        "property": _PROGRAM_ROOT / f"{_PREFIX}native_lua_property_factory_chain.json",
        "consumer": _PROGRAM_ROOT / f"{_PREFIX}native_lua_property_consumer_chain.json",
        "evidence": _PROGRAM_ROOT / f"{_PREFIX}native_lua_property_mismatch_chain.json",
    }
    missing = [path for path in paths.values() if not path.is_file()]
    if missing:
        pytest.skip("committed property-mismatch prerequisites are unavailable")
    return {name: _load(path) for name, path in paths.items()}


def _structure_args(values: dict[str, dict]) -> tuple[dict, ...]:
    return (
        values["consumer"],
        values["property"],
        values["direct"],
        values["callbacks"],
        values["setfield"],
        values["direct_table"],
        values["indirect"],
        values["table_keys"],
        values["terminal"],
        values["facts"],
    )


def _consumer_receipt(values: dict[str, dict]) -> dict:
    return {
        "analysis_kind": mismatch_chain.CONSUMER_STRUCTURE_VERIFICATION_KIND,
        "status": "structurally_verified",
        "build_identity": copy.deepcopy(values["consumer"]["build_identity"]),
        "evidence_sha256": _CONSUMER_SHA256,
    }


def _fast_structure(monkeypatch, evidence, values):
    monkeypatch.setattr(
        mismatch_chain,
        "validate_native_lua_property_consumer_chain_structure",
        lambda *args, **kwargs: _consumer_receipt(values),
    )
    return validate_native_lua_property_mismatch_chain_structure(
        evidence, *_structure_args(values)
    )


def test_committed_artifact_encoding_and_digests(real_inputs):
    path = _PROGRAM_ROOT / f"{_PREFIX}native_lua_property_mismatch_chain.json"
    payload = path.read_bytes()
    evidence = real_inputs["evidence"]
    assert hashlib.sha256(payload).hexdigest() == _RAW_SHA256
    assert mismatch_chain._canonical_sha256(evidence) == _CANONICAL_SHA256
    assert payload == encode_native_lua_property_mismatch_chain(evidence).encode("utf-8")
    assert evidence["analysis_kind"] == ANALYSIS_KIND


def test_committed_artifact_full_structural_validation(real_inputs):
    receipt = validate_native_lua_property_mismatch_chain_structure(
        real_inputs["evidence"], *_structure_args(real_inputs)
    )
    assert receipt["analysis_kind"] == STRUCTURE_VERIFICATION_KIND
    assert receipt["status"] == "structurally_verified"
    assert receipt["evidence_sha256"] == _CANONICAL_SHA256


def test_committed_artifact_exact_rebuild_and_verification(real_inputs):
    if not _EXE.is_file() or hashlib.sha256(_EXE.read_bytes()).hexdigest() != _EXE_SHA256:
        pytest.skip("sealed Breach.exe is unavailable")
    rebuilt = build_native_lua_property_mismatch_chain(
        _EXE, *_structure_args(real_inputs), inventory=real_inputs["inventory"]
    )
    assert rebuilt == real_inputs["evidence"]
    receipt = validate_native_lua_property_mismatch_chain(
        _EXE,
        real_inputs["evidence"],
        *_structure_args(real_inputs),
        inventory=real_inputs["inventory"],
    )
    assert receipt["status"] == "verified"
    assert receipt["evidence_sha256"] == _CANONICAL_SHA256


def test_expected_paths_stack_models_and_summary(real_inputs):
    evidence = real_inputs["evidence"]
    assert evidence["consumer_chain"]["canonical_sha256"] == _CONSUMER_SHA256
    assert [item["entry_rva"] for item in evidence["source_bodies"]] == [
        "0x002e9fd0",
        "0x002ea110",
    ]
    getter = evidence["getter_mismatch_path"]
    setter = evidence["setter_mismatch_path"]
    assert len(getter["path_points"]) == 24
    assert len(setter["path_points"]) == 54
    assert getter["semantics"]["common_terminal_internal_stack_claimed"] is False
    assert [path["internal_stack"] for path in getter["semantics"]["terminal_paths"]] == [
        ["S", "F", "D"],
        ["S", "F", "nil"],
        ["S", "F", "nil", "M", "W"],
    ]
    assert [path["selected_result"] for path in getter["semantics"]["terminal_paths"]] == [
        "D",
        "nil",
        "W",
    ]
    assert setter["semantics"]["post_mismatch_candidate_removal"] == {
        "after": ["S", "F"],
        "before": ["S", "F", "C"],
        "lua_settop_index": -2,
    }
    assert setter["semantics"]["absolute_slot_four_partition"] == [
        {
            "entry_input_count": 3,
            "slot_four_is_appended_environment_slot": True,
            "slot_four_symbol": "F",
        },
        {
            "minimum_entry_input_count": 4,
            "slot_four_is_appended_environment_slot": False,
            "slot_four_symbol": "I4",
        },
    ]
    assert [path["raw_store_destination"] for path in setter["semantics"]["storage_paths"]] == [
        "F",
        "T",
    ]
    assert evidence["summary"] == {
        "candidate_source_count": 6,
        "conditional_entry_arity_partition_count": 2,
        "consumer_prerequisite_count": 1,
        "declared_path_point_count": 78,
        "getter_path_point_count": 24,
        "getter_terminal_path_count": 3,
        "mismatch_trace_count": 2,
        "non_normalized_getter_candidate_stack_count": 1,
        "normalized_setter_candidate_stack_count": 1,
        "schema_violations": 0,
        "setter_path_point_count": 54,
        "setter_storage_path_count": 2,
        "source_body_count": 2,
        "source_cfg_count": 2,
        "source_cfg_edge_count": 195,
        "source_cfg_node_count": 190,
    }


def test_path_points_retain_branch_and_lua_dispatch_joins(real_inputs):
    evidence = real_inputs["evidence"]
    getter = {item["role"]: item for item in evidence["getter_mismatch_path"]["path_points"]}
    setter = {item["role"]: item for item in evidence["setter_mismatch_path"]["path_points"]}
    assert getter["candidate_nonnil_branch"]["successor_rvas"] == [
        "0x002ea145",
        "0x002ea166",
    ]
    assert getter["identity_mismatch_branch"]["successor_rvas"] == [
        "0x002ea179",
        "0x002ea197",
    ]
    assert setter["slot_four_has_metatable_branch"]["successor_rvas"] == [
        "0x002ea0be",
        "0x002ea0e8",
    ]
    assert setter["fresh_table_to_common_tail"]["successor_rvas"] == ["0x002ea0f0"]
    assert getter["lua_pushvalue_key"]["lua_dispatch_kind"] == "staged_register"
    assert setter["lua_settop_pop_candidate"]["lua_dispatch_kind"] == "staged_register"
    assert setter["lua_rawset"]["lua_dispatch_kind"] == "direct_import"


def _replace_path(value, path, replacement):
    current = value
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = replacement


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("consumer_chain", "canonical_sha256"), "0" * 64),
        (("source_bodies", 0, "body_sha256"), "1" * 64),
        (("getter_mismatch_path", "path_points", 0, "sha256"), "2" * 64),
        (("getter_mismatch_path", "path_points", 9, "successor_rvas"), []),
        (("getter_mismatch_path", "semantics", "common_terminal_internal_stack_claimed"), True),
        (("getter_mismatch_path", "semantics", "terminal_paths", 2, "internal_stack"), ["S", "F", "W"]),
        (("getter_mismatch_path", "semantics", "normal_result_count"), 0),
        (("setter_mismatch_path", "semantics", "post_mismatch_candidate_removal", "lua_settop_index"), -3),
        (("setter_mismatch_path", "semantics", "absolute_slot_four_partition", 1, "slot_four_symbol"), "F"),
        (("setter_mismatch_path", "semantics", "storage_paths", 0, "raw_store_destination"), "T"),
        (("setter_mismatch_path", "semantics", "storage_paths", 1, "setmetatable_attempt", "return_checked"), True),
        (("setter_mismatch_path", "semantics", "normal_result_count"), 1),
        (("lua51_abi", "normal_return_only"), False),
        (("method", "normal_return_boundary"), "broader claim"),
        (("summary", "declared_path_point_count"), 77),
    ],
)
def test_structural_validator_rejects_tamper(
    monkeypatch, real_inputs, path, replacement
):
    evidence = copy.deepcopy(real_inputs["evidence"])
    _replace_path(evidence, path, replacement)
    with pytest.raises(NativeLuaPropertyMismatchChainError):
        _fast_structure(monkeypatch, evidence, real_inputs)


def test_structural_validator_rejects_unknown_field(monkeypatch, real_inputs):
    evidence = copy.deepcopy(real_inputs["evidence"])
    evidence["unexpected"] = True
    with pytest.raises(NativeLuaPropertyMismatchChainError):
        _fast_structure(monkeypatch, evidence, real_inputs)


def test_structural_validator_rejects_other_consumer_receipt(monkeypatch, real_inputs):
    receipt = _consumer_receipt(real_inputs)
    receipt["evidence_sha256"] = "0" * 64
    monkeypatch.setattr(
        mismatch_chain,
        "validate_native_lua_property_consumer_chain_structure",
        lambda *args, **kwargs: receipt,
    )
    with pytest.raises(NativeLuaPropertyMismatchChainError):
        validate_native_lua_property_mismatch_chain_structure(
            real_inputs["evidence"], *_structure_args(real_inputs)
        )


def test_derivations_do_not_share_mutable_schema_objects(real_inputs):
    first = mismatch_chain._derive_native_lua_property_mismatch_chain(
        real_inputs["consumer"], real_inputs["facts"]
    )
    first["getter_mismatch_path"]["semantics"]["normal_result_count"] = 99
    first["method"]["not_claimed"].append("mutation")
    second = mismatch_chain._derive_native_lua_property_mismatch_chain(
        real_inputs["consumer"], real_inputs["facts"]
    )
    assert second["getter_mismatch_path"]["semantics"]["normal_result_count"] == 1
    assert "mutation" not in second["method"]["not_claimed"]


def test_cli_parser_has_full_prerequisite_surface():
    parser = mismatch_cli.build_parser()
    args = parser.parse_args(
        [
            "verify",
            "--executable", "Breach.exe",
            "--inventory", "inventory.json",
            "--program-facts", "facts.json",
            "--direct-calls", "direct.json",
            "--callbacks", "callbacks.json",
            "--setfield-publications", "setfield.json",
            "--direct-table-setter-publications", "direct-table.json",
            "--indirect-settable-publications", "indirect.json",
            "--table-key-provenance", "keys.json",
            "--terminal-dispositions", "terminal.json",
            "--property-factory-chain", "property.json",
            "--property-consumer-chain", "consumer.json",
            "--evidence", "mismatch.json",
        ]
    )
    assert args.command == "verify"
    assert args.property_consumer_chain == Path("consumer.json")
    assert args.evidence == Path("mismatch.json")


def test_cli_immutable_writer_idempotence_and_refusal(monkeypatch, tmp_path, real_inputs):
    output_root = tmp_path / "programs"
    output_root.mkdir()

    def prepare():
        return output_root, output_root.resolve(), output_root.stat()

    monkeypatch.setattr(mismatch_cli, "_prepare_output_root", prepare)
    monkeypatch.setattr(mismatch_cli, "_recheck_output_root", lambda *args: None)
    output = output_root / "mismatch.json"
    evidence = copy.deepcopy(real_inputs["evidence"])
    rendered = encode_native_lua_property_mismatch_chain(evidence)
    mismatch_cli._write_evidence_immutably(output, rendered, evidence)
    mismatch_cli._write_evidence_immutably(output, rendered, evidence)
    assert output.read_text(encoding="utf-8") == rendered
    changed = copy.deepcopy(evidence)
    changed["summary"]["mismatch_trace_count"] = 3
    with pytest.raises(NativeLuaPropertyMismatchChainError):
        mismatch_cli._write_evidence_immutably(
            output, encode_native_lua_property_mismatch_chain(changed), changed
        )
