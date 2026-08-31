from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import itb_native_lua_property_consumer_chain as consumer_cli
from src.observatory import native_lua_property_consumer_chain as consumer_chain
from src.observatory.native_lua_property_consumer_chain import (
    ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND,
    NativeLuaPropertyConsumerChainError,
    build_native_lua_property_consumer_chain,
    encode_native_lua_property_consumer_chain,
    validate_native_lua_property_consumer_chain,
    validate_native_lua_property_consumer_chain_structure,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROGRAM_ROOT = _REPO_ROOT / "data" / "observatory" / "programs"
_INVENTORY_ROOT = _REPO_ROOT / "data" / "observatory" / "inventories"
_PREFIX = "windows_build_13725832_31fe35265598_"
_EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_RAW_SHA256 = "1cc4b84cebb5b5fab17b059f8050bca477c6d27742efb267b7a29851d87d88a5"
_CANONICAL_SHA256 = "2c6569177595cbdc8abdbe4ba1bdc3d09f4bb0d15dac5d280c16ba3dfcc2d3b9"


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
        "evidence": _PROGRAM_ROOT / f"{_PREFIX}native_lua_property_consumer_chain.json",
    }
    missing = [path for path in paths.values() if not path.is_file()]
    if missing:
        pytest.skip("committed property-consumer prerequisites are unavailable")
    return {name: _load(path) for name, path in paths.items()}


def _structure_args(values: dict[str, dict]) -> tuple[dict, ...]:
    return (
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


def _fast_structure(monkeypatch, evidence, values):
    monkeypatch.setattr(
        consumer_chain,
        "validate_native_lua_property_factory_chain_structure",
        lambda *args, **kwargs: {
            "analysis_kind": consumer_chain.PROPERTY_FACTORY_STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
        },
    )
    return validate_native_lua_property_consumer_chain_structure(
        evidence, *_structure_args(values)
    )


def test_committed_artifact_encoding_and_digests(real_inputs):
    path = _PROGRAM_ROOT / f"{_PREFIX}native_lua_property_consumer_chain.json"
    payload = path.read_bytes()
    evidence = real_inputs["evidence"]
    assert hashlib.sha256(payload).hexdigest() == _RAW_SHA256
    assert consumer_chain._canonical_sha256(evidence) == _CANONICAL_SHA256
    assert payload == encode_native_lua_property_consumer_chain(evidence).encode("utf-8")
    assert evidence["analysis_kind"] == ANALYSIS_KIND


def test_committed_artifact_full_structural_validation(real_inputs):
    receipt = validate_native_lua_property_consumer_chain_structure(
        real_inputs["evidence"], *_structure_args(real_inputs)
    )
    assert receipt["analysis_kind"] == STRUCTURE_VERIFICATION_KIND
    assert receipt["status"] == "structurally_verified"
    assert receipt["evidence_sha256"] == _CANONICAL_SHA256


def test_committed_artifact_exact_rebuild_and_verification(real_inputs):
    if not _EXE.is_file() or hashlib.sha256(_EXE.read_bytes()).hexdigest() != _EXE_SHA256:
        pytest.skip("sealed Breach.exe is unavailable")
    rebuilt = build_native_lua_property_consumer_chain(
        _EXE, *_structure_args(real_inputs), inventory=real_inputs["inventory"]
    )
    assert rebuilt == real_inputs["evidence"]
    receipt = validate_native_lua_property_consumer_chain(
        _EXE,
        real_inputs["evidence"],
        *_structure_args(real_inputs),
        inventory=real_inputs["inventory"],
    )
    assert receipt["status"] == "verified"
    assert receipt["evidence_sha256"] == _CANONICAL_SHA256


def test_expected_consumers_placements_partitions_and_nonclaims(real_inputs):
    evidence = real_inputs["evidence"]
    source = evidence["property_tag_source"]
    assert source["canonical_sha256"] == "aef6475375ce31da7d089eb819bf4b3a42228332892aa2bb8645668fe2db3b5e"
    assert source["tag_callback_entry_rva"] == "0x002eaa50"
    assert source["factory_closure_upvalue_count"] == 2
    assert source["callback_identity_establishes_factory_origin"] is False
    assert [item["comparison_instruction_rva"] for item in source["identity_comparison_witnesses"]] == [
        "0x002ea047",
        "0x002ea172",
    ]
    bodies = evidence["function_bodies"]
    assert [item["entry_rva"] for item in bodies] == [
        "0x002e9fd0",
        "0x002ea110",
        "0x002ea2d0",
    ]
    assert sum(item["body_size"] for item in bodies) == 706
    assert sum(
        point["direct_lua_import"] is not None
        for body in bodies
        for point in body["reviewed_points"]
    ) == 34
    assert sum(
        len(dispatch["call_sites"])
        for body in bodies
        for dispatch in body["staged_lua_dispatches"]
    ) == 23
    assert all(body["all_eight_register_call_encodings_checked"] for body in bodies)
    setter, getter, initializer = bodies
    assert setter["semantic_facts"]["identity_match_arm"] == {
        "getupvalue_native_result_checked": False,
        "nil_arm": "read_only_lua_error",
        "nil_type_value": 0,
        "non_nil_lua_call_argument_count": 2,
        "non_nil_lua_call_result_count": 0,
        "non_nil_original_argument_indices": [1, 3],
        "non_nil_value_callability_proven": False,
        "normal_result_count": 0,
        "retrieved_upvalue_index": 2,
    }
    assert getter["semantic_facts"]["identity_match_arm"]["retrieved_upvalue_index"] == 1
    assert getter["semantic_facts"]["identity_mismatch_arm"]["semantics_normalized"] is False
    assert initializer["semantic_facts"]["numeric_getter_rawset_is_index_metamethod_placement"] is False
    placements = evidence["placements"]
    assert [item["role"] for item in placements] == [
        "numeric_getter_rawset",
        "index_getter_setfield",
        "newindex_setter_setfield",
    ]
    assert placements[0]["metamethod_name"] is None
    assert placements[0]["metamethod_placement_claimed"] is False
    assert [item["metamethod_name"] for item in placements[1:]] == ["__index", "__newindex"]
    assert evidence["target_reference_scan"]["aggregates"] == {
        "closure_producer_count": 3,
        "comparison_count": 2,
        "direct_call_count": 1,
        "getter_target_reference_count": 4,
        "initializer_target_reference_count": 1,
        "memory_operand_count": 0,
        "other_address_count": 0,
        "reference_count": 6,
        "setter_target_reference_count": 1,
    }
    assert evidence["summary"] == {
        "constant_count": 1,
        "direct_lua_call_count": 34,
        "literal_count": 3,
        "metamethod_placement_count": 2,
        "normalized_identity_match_arm_count": 2,
        "normalized_read_only_arm_count": 1,
        "numeric_rawset_placement_count": 1,
        "opaque_identity_mismatch_arm_count": 2,
        "placement_count": 3,
        "property_factory_prerequisite_count": 1,
        "property_tag_identity_comparison_count": 2,
        "reviewed_function_bytes": 706,
        "reviewed_function_count": 3,
        "schema_violations": 0,
        "sealed_control_flow_graph_count": 3,
        "sealed_control_flow_graph_edge_count": 286,
        "sealed_control_flow_graph_node_count": 279,
        "staged_lua_call_count": 23,
        "staged_lua_dispatch_count": 5,
        "target_reference_closure_producer_count": 3,
        "target_reference_comparison_count": 2,
        "target_reference_count": 6,
        "target_reference_direct_call_count": 1,
        "target_reference_memory_operand_count": 0,
        "target_reference_other_address_count": 0,
    }
    nonclaims = evidence["method"]["not_claimed"]
    assert "factory provenance from callback identity alone" in nonclaims
    assert "dynamic metatable attachment, recipient identity, later lookup, or invocation" in nonclaims
    assert "normalized semantics for either callback-identity mismatch branch" in nonclaims


def _replace_path(value, path, replacement):
    current = value
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = replacement


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("property_factory_chain", "canonical_sha256"), "0" * 64),
        (("property_tag_source", "callback_identity_establishes_factory_origin"), True),
        (("property_tag_source", "identity_comparison_witnesses", 0, "source_reference_record_sha256"), "1" * 64),
        (("literals", 0, "nul_terminated_bytes_sha256"), "2" * 64),
        (("constants", 0, "bytes_sha256"), "3" * 64),
        (("function_bodies", 0, "reviewed_points", 0, "sha256"), "4" * 64),
        (("function_bodies", 0, "direct_lua_call_partition_complete"), False),
        (("function_bodies", 1, "dynamic_register_call_rvas"), []),
        (("function_bodies", 1, "semantic_facts", "identity_match_arm", "retrieved_upvalue_index"), 2),
        (("function_bodies", 1, "semantic_facts", "identity_mismatch_arm", "semantics_normalized"), True),
        (("placements", 0, "metamethod_placement_claimed"), True),
        (("placements", 1, "target_push_rva"), "0x002ea318"),
        (("target_reference_scan", "references", 1, "use_class"), "index_getter_closure_producer"),
        (("target_reference_scan", "scope", "decoded_instructions"), 1),
        (("decoder", "dynamic_register_call_encodings"), ["ffd7"]),
        (("summary", "staged_lua_call_count"), 22),
    ],
)
def test_structural_validator_rejects_tamper(monkeypatch, real_inputs, path, replacement):
    evidence = copy.deepcopy(real_inputs["evidence"])
    _replace_path(evidence, path, replacement)
    with pytest.raises(NativeLuaPropertyConsumerChainError):
        _fast_structure(monkeypatch, evidence, real_inputs)


def test_structural_validator_rejects_unknown_field(monkeypatch, real_inputs):
    evidence = copy.deepcopy(real_inputs["evidence"])
    evidence["unexpected"] = True
    with pytest.raises(NativeLuaPropertyConsumerChainError):
        _fast_structure(monkeypatch, evidence, real_inputs)


@pytest.mark.parametrize("register_index", range(8))
def test_structural_validator_rejects_ungrouped_call_register(
    monkeypatch, real_inputs, register_index
):
    evidence = copy.deepcopy(real_inputs["evidence"])
    graph = evidence["control_flow_graphs"][1]
    reviewed = {
        point["rva"] for point in evidence["function_bodies"][1]["reviewed_points"]
    }
    node = next(
        item
        for item in graph["nodes"]
        if item["size"] == 2 and item["rva"] not in reviewed
    )
    encoded = bytes((0xFF, 0xD0 + register_index))
    node["sha256"] = hashlib.sha256(encoded).hexdigest()
    original = consumer_chain._canonical_sha256

    def accept_mutated_graph(value):
        if value is graph:
            return consumer_chain._SEALED_PROFILE["functions"][1]["cfg_canonical_sha256"]
        return original(value)

    monkeypatch.setattr(consumer_chain, "_canonical_sha256", accept_mutated_graph)
    monkeypatch.setattr(
        consumer_chain,
        "validate_native_lua_property_factory_chain_structure",
        lambda *args, **kwargs: {
            "analysis_kind": consumer_chain.PROPERTY_FACTORY_STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
        },
    )
    with pytest.raises(NativeLuaPropertyConsumerChainError):
        validate_native_lua_property_consumer_chain_structure(
            evidence, *_structure_args(real_inputs)
        )


def test_cli_parser_has_full_prerequisite_surface():
    parser = consumer_cli.build_parser()
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
            "--evidence", "consumer.json",
        ]
    )
    assert args.command == "verify"
    assert args.property_factory_chain == Path("property.json")
    assert args.evidence == Path("consumer.json")


def test_cli_immutable_writer_idempotence_and_refusal(monkeypatch, tmp_path, real_inputs):
    output_root = tmp_path / "programs"
    output_root.mkdir()

    def prepare():
        return output_root, output_root.resolve(), output_root.stat()

    monkeypatch.setattr(consumer_cli, "_prepare_output_root", prepare)
    monkeypatch.setattr(consumer_cli, "_recheck_output_root", lambda *args: None)
    output = output_root / "consumer.json"
    evidence = copy.deepcopy(real_inputs["evidence"])
    rendered = encode_native_lua_property_consumer_chain(evidence)
    consumer_cli._write_evidence_immutably(output, rendered, evidence)
    consumer_cli._write_evidence_immutably(output, rendered, evidence)
    assert output.read_text(encoding="utf-8") == rendered
    changed = copy.deepcopy(evidence)
    changed["summary"]["placement_count"] = 4
    with pytest.raises(NativeLuaPropertyConsumerChainError):
        consumer_cli._write_evidence_immutably(
            output, encode_native_lua_property_consumer_chain(changed), changed
        )
