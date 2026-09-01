from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import itb_native_lua_property_initializer_chain as initializer_cli
from src.observatory import native_lua_property_initializer_chain as initializer_chain
from src.observatory.native_lua_property_initializer_chain import (
    ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND,
    NativeLuaPropertyInitializerChainError,
    encode_native_lua_property_initializer_chain,
    validate_native_lua_property_initializer_chain,
    validate_native_lua_property_initializer_chain_structure,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROGRAM_ROOT = _REPO_ROOT / "data" / "observatory" / "programs"
_INVENTORY_ROOT = _REPO_ROOT / "data" / "observatory" / "inventories"
_PREFIX = "windows_build_13725832_31fe35265598_"
_EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_RAW_SHA256 = "21aa8589ea24fc5b0f468781bb27c299d7df3f75927fc2202dbe5d08dec18872"
_CANONICAL_SHA256 = "b76b3d46d30da4801a3bc4f67be78d3818f847557a0b275f6048120873b44bc4"
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
        "evidence": _PROGRAM_ROOT / f"{_PREFIX}native_lua_property_initializer_chain.json",
    }
    missing = [path for path in paths.values() if not path.is_file()]
    if missing:
        pytest.skip("committed property-initializer prerequisites are unavailable")
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
        "schema_version": 1,
        "analysis_kind": initializer_chain.CONSUMER_STRUCTURE_VERIFICATION_KIND,
        "status": "structurally_verified",
        "build_identity": copy.deepcopy(values["consumer"]["build_identity"]),
        "evidence_sha256": _CONSUMER_SHA256,
    }


def _fast_structure(monkeypatch, evidence, values):
    monkeypatch.setattr(
        initializer_chain,
        "validate_native_lua_property_consumer_chain_structure",
        lambda *args, **kwargs: _consumer_receipt(values),
    )
    return validate_native_lua_property_initializer_chain_structure(
        evidence, *_structure_args(values)
    )


def test_committed_artifact_encoding_and_digests(real_inputs):
    path = _PROGRAM_ROOT / f"{_PREFIX}native_lua_property_initializer_chain.json"
    payload = path.read_bytes()
    evidence = real_inputs["evidence"]
    assert hashlib.sha256(payload).hexdigest() == _RAW_SHA256
    assert initializer_chain._canonical_sha256(evidence) == _CANONICAL_SHA256
    assert payload == encode_native_lua_property_initializer_chain(evidence).encode(
        "utf-8"
    )
    assert evidence["analysis_kind"] == ANALYSIS_KIND


def test_committed_artifact_full_structural_validation(real_inputs):
    receipt = validate_native_lua_property_initializer_chain_structure(
        real_inputs["evidence"], *_structure_args(real_inputs)
    )
    assert receipt["analysis_kind"] == STRUCTURE_VERIFICATION_KIND
    assert receipt["status"] == "structurally_verified"
    assert receipt["evidence_sha256"] == _CANONICAL_SHA256


def test_committed_artifact_exact_verification(real_inputs):
    if not _EXE.is_file() or hashlib.sha256(_EXE.read_bytes()).hexdigest() != _EXE_SHA256:
        pytest.skip("sealed Breach.exe is unavailable")
    receipt = validate_native_lua_property_initializer_chain(
        _EXE,
        real_inputs["evidence"],
        *_structure_args(real_inputs),
        inventory=real_inputs["inventory"],
    )
    assert receipt["status"] == "verified"
    assert receipt["evidence_sha256"] == _CANONICAL_SHA256


def test_expected_marker_cleanup_loop_and_summary(real_inputs):
    evidence = real_inputs["evidence"]
    assert evidence["consumer_chain"]["canonical_sha256"] == _CONSUMER_SHA256
    assert evidence["source_body"]["entry_rva"] == "0x002ea2d0"
    assert evidence["source_body"]["body_size"] == 245
    semantics = evidence["semantics"]
    assert semantics["marker_placement"] == {
        "key": "__luabind_class",
        "setter": "lua_setfield",
        "stack_after_setter": ["S", "T"],
        "stack_before_value": ["S", "T"],
        "table_index": -2,
        "value": True,
    }
    assert semantics["cleanup_placement"]["callback_entry_rva"] == "0x002e9f40"
    assert semantics["cleanup_placement"]["closure_upvalue_count"] == 0
    loop = semantics["wrapper_loop"]
    assert loop["initial_index"] == 0
    assert loop["exclusive_upper_bound"] == 13
    assert loop["true_boolean_indices"] == [9, 12]
    assert loop["false_boolean_indices"] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11]
    assert loop["callback_entry_rva"] == "0x002ea1a0"
    assert loop["closure_upvalue_count"] == 2
    assert loop["upvalue_order"] == ["K", "B"]
    assert [row["key"] for row in loop["ordered_rows"]] == [
        "__add", "__sub", "__mul", "__div", "__pow", "__lt", "__le",
        "__eq", "__call", "__unm", "__tostring", "__concat", "__len",
    ]
    assert evidence["summary"] == {
        "cleanup_closure_placement_count": 1,
        "consumer_prerequisite_count": 1,
        "declared_path_point_count": 33,
        "direct_lua_path_point_count": 6,
        "literal_count": 15,
        "marker_placement_count": 1,
        "pointer_array_entry_count": 13,
        "schema_violations": 0,
        "source_body_count": 1,
        "source_cfg_edge_count": 91,
        "source_cfg_node_count": 89,
        "staged_lua_path_point_count": 4,
        "wrapper_closure_placement_count": 13,
        "wrapper_false_boolean_count": 11,
        "wrapper_true_boolean_count": 2,
    }


def test_exact_literal_and_pointer_array_partition(real_inputs):
    evidence = real_inputs["evidence"]
    literals = evidence["literals"]
    assert len(literals) == 15
    assert literals[0]["text"] == "__luabind_class"
    assert literals[1]["text"] == "__gc"
    assert all(item["section_writable"] is False for item in literals)
    pointer_array = evidence["pointer_array"]
    assert pointer_array["size"] == 52
    assert pointer_array["sha256"] == (
        "95c565ed90ed86b684d214cb95b79de28ecb376e05f58852f091dec49bd6766c"
    )
    assert [row["literal_rva"] for row in pointer_array["entries"]] == [
        row["literal_rva"]
        for row in evidence["semantics"]["wrapper_loop"]["ordered_rows"]
    ]


def test_path_points_retain_branches_and_dispatch_joins(real_inputs):
    points = {item["role"]: item for item in real_inputs["evidence"]["path_points"]}
    assert points["set_marker_field"]["lua_dispatch_kind"] == "staged_register"
    assert points["create_cleanup_closure"]["lua_dispatch_kind"] == "staged_register"
    assert points["set_wrapper_entry"]["lua_dispatch_kind"] == "direct_import"
    assert points["index_nine_true_branch"]["successor_rvas"] == [
        "0x002ea38f",
        "0x002ea398",
    ]
    assert points["loop_back_branch"]["successor_rvas"] == [
        "0x002ea370",
        "0x002ea3c1",
    ]


def _replace_path(value, path, replacement):
    current = value
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = replacement


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("consumer_chain", "canonical_sha256"), "0" * 64),
        (("source_body", "body_sha256"), "1" * 64),
        (("literals", 0, "nul_terminated_bytes_sha256"), "2" * 64),
        (("literals", 1, "text"), "__index"),
        (("pointer_array", "sha256"), "3" * 64),
        (("pointer_array", "entries", 0, "literal_rva"), "0x00420738"),
        (("path_points", 2, "sha256"), "4" * 64),
        (("path_points", 17, "successor_rvas"), []),
        (("semantics", "marker_placement", "value"), False),
        (("semantics", "cleanup_placement", "closure_upvalue_count"), 1),
        (("semantics", "wrapper_loop", "exclusive_upper_bound"), 12),
        (("semantics", "wrapper_loop", "true_boolean_indices"), [9]),
        (("semantics", "wrapper_loop", "closure_upvalue_count"), 1),
        (("semantics", "wrapper_loop", "ordered_rows", 9, "boolean_upvalue"), False),
        (("method", "not_claimed"), []),
        (("summary", "wrapper_closure_placement_count"), 12),
    ],
)
def test_structural_validator_rejects_tamper(
    monkeypatch, real_inputs, path, replacement
):
    evidence = copy.deepcopy(real_inputs["evidence"])
    _replace_path(evidence, path, replacement)
    with pytest.raises(NativeLuaPropertyInitializerChainError):
        _fast_structure(monkeypatch, evidence, real_inputs)


def test_structural_validator_rejects_unknown_field(monkeypatch, real_inputs):
    evidence = copy.deepcopy(real_inputs["evidence"])
    evidence["unexpected"] = True
    with pytest.raises(NativeLuaPropertyInitializerChainError):
        _fast_structure(monkeypatch, evidence, real_inputs)


def test_structural_validator_rejects_other_consumer_receipt(monkeypatch, real_inputs):
    receipt = _consumer_receipt(real_inputs)
    receipt["evidence_sha256"] = "0" * 64
    monkeypatch.setattr(
        initializer_chain,
        "validate_native_lua_property_consumer_chain_structure",
        lambda *args, **kwargs: receipt,
    )
    with pytest.raises(NativeLuaPropertyInitializerChainError):
        validate_native_lua_property_initializer_chain_structure(
            real_inputs["evidence"], *_structure_args(real_inputs)
        )


def test_cli_parser_has_full_prerequisite_surface():
    parser = initializer_cli.build_parser()
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
            "--evidence", "initializer.json",
        ]
    )
    assert args.command == "verify"
    assert args.property_consumer_chain == Path("consumer.json")
    assert args.evidence == Path("initializer.json")


def test_cli_immutable_writer_idempotence_and_refusal(monkeypatch, tmp_path, real_inputs):
    output_root = tmp_path / "programs"
    output_root.mkdir()

    def prepare():
        return output_root, output_root.resolve(), output_root.stat()

    monkeypatch.setattr(initializer_cli, "_prepare_output_root", prepare)
    monkeypatch.setattr(initializer_cli, "_recheck_output_root", lambda *args: None)
    output = output_root / "initializer.json"
    evidence = copy.deepcopy(real_inputs["evidence"])
    rendered = encode_native_lua_property_initializer_chain(evidence)
    initializer_cli._write_evidence_immutably(output, rendered, evidence)
    initializer_cli._write_evidence_immutably(output, rendered, evidence)
    assert output.read_text(encoding="utf-8") == rendered
    changed = copy.deepcopy(evidence)
    changed["summary"]["wrapper_closure_placement_count"] = 12
    with pytest.raises(NativeLuaPropertyInitializerChainError):
        initializer_cli._write_evidence_immutably(
            output, encode_native_lua_property_initializer_chain(changed), changed
        )
