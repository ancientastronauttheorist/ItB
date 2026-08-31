from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import itb_native_lua_property_factory_chain as property_cli
from src.observatory import native_lua_property_factory_chain as property_chain
from src.observatory.native_lua_property_factory_chain import (
    ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND,
    NativeLuaPropertyFactoryChainError,
    build_native_lua_property_factory_chain,
    encode_native_lua_property_factory_chain,
    validate_native_lua_property_factory_chain,
    validate_native_lua_property_factory_chain_structure,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROGRAM_ROOT = _REPO_ROOT / "data" / "observatory" / "programs"
_INVENTORY_ROOT = _REPO_ROOT / "data" / "observatory" / "inventories"
_PREFIX = "windows_build_13725832_31fe35265598_"
_EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_RAW_SHA256 = "5859871e2a61522a7f80a3b92f12ed705ad906b770c1fa2247877f16a066fa4b"
_CANONICAL_SHA256 = "aef6475375ce31da7d089eb819bf4b3a42228332892aa2bb8645668fe2db3b5e"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def real_inputs() -> dict[str, dict]:
    paths = {
        "inventory": _INVENTORY_ROOT
        / f"{_PREFIX}full_decompile_baseline_20260830.json",
        "facts": _PROGRAM_ROOT / f"{_PREFIX}program_facts.json",
        "direct": _PROGRAM_ROOT / f"{_PREFIX}native_lua_direct_call_census.json",
        "callbacks": _PROGRAM_ROOT / f"{_PREFIX}native_lua_cclosure_callbacks.json",
        "setfield": _PROGRAM_ROOT
        / f"{_PREFIX}native_lua_cclosure_setfield_publications.json",
        "direct_table": _PROGRAM_ROOT
        / f"{_PREFIX}native_lua_cclosure_table_setter_publications.json",
        "indirect": _PROGRAM_ROOT
        / f"{_PREFIX}native_lua_cclosure_indirect_settable_publications.json",
        "table_keys": _PROGRAM_ROOT
        / f"{_PREFIX}native_lua_cclosure_table_key_provenance.json",
        "terminal": _PROGRAM_ROOT
        / f"{_PREFIX}native_lua_cclosure_terminal_dispositions.json",
        "evidence": _PROGRAM_ROOT
        / f"{_PREFIX}native_lua_property_factory_chain.json",
    }
    missing = [path for path in paths.values() if not path.is_file()]
    if missing:
        pytest.skip("committed property-factory prerequisites are unavailable")
    return {name: _load(path) for name, path in paths.items()}


def _structure_args(values: dict[str, dict]) -> tuple[dict, ...]:
    return (
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
        property_chain,
        "validate_native_lua_cclosure_table_key_provenance_structure",
        lambda *args, **kwargs: {
            "analysis_kind": property_chain.TABLE_KEY_STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
        },
    )
    monkeypatch.setattr(
        property_chain,
        "validate_native_lua_cclosure_terminal_disposition_structure",
        lambda *args, **kwargs: {
            "analysis_kind": property_chain.TERMINAL_STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
        },
    )
    return validate_native_lua_property_factory_chain_structure(
        evidence, *_structure_args(values)
    )


def test_committed_artifact_encoding_and_digests(real_inputs):
    path = _PROGRAM_ROOT / f"{_PREFIX}native_lua_property_factory_chain.json"
    payload = path.read_bytes()
    evidence = real_inputs["evidence"]
    assert hashlib.sha256(payload).hexdigest() == _RAW_SHA256
    assert property_chain._canonical_sha256(evidence) == _CANONICAL_SHA256
    assert payload == encode_native_lua_property_factory_chain(evidence).encode(
        "utf-8"
    )
    assert evidence["analysis_kind"] == ANALYSIS_KIND


def test_committed_artifact_full_structural_validation(real_inputs):
    receipt = validate_native_lua_property_factory_chain_structure(
        real_inputs["evidence"], *_structure_args(real_inputs)
    )
    assert receipt["analysis_kind"] == STRUCTURE_VERIFICATION_KIND
    assert receipt["status"] == "structurally_verified"
    assert receipt["evidence_sha256"] == _CANONICAL_SHA256


def test_committed_artifact_exact_rebuild_and_verification(real_inputs):
    if not _EXE.is_file() or hashlib.sha256(_EXE.read_bytes()).hexdigest() != _EXE_SHA256:
        pytest.skip("sealed Breach.exe is unavailable")
    rebuilt = build_native_lua_property_factory_chain(
        _EXE,
        *_structure_args(real_inputs),
        inventory=real_inputs["inventory"],
    )
    assert rebuilt == real_inputs["evidence"]
    receipt = validate_native_lua_property_factory_chain(
        _EXE,
        real_inputs["evidence"],
        *_structure_args(real_inputs),
        inventory=real_inputs["inventory"],
    )
    assert receipt["status"] == "verified"
    assert receipt["evidence_sha256"] == _CANONICAL_SHA256


def test_expected_chain_partition_and_nonclaims(real_inputs):
    evidence = real_inputs["evidence"]
    chain = evidence["publication_chain"]
    assert chain["property_publication"]["callback_entry_rva"] == "0x002e67b0"
    assert chain["factory_returned_closure"]["callback_entry_rva"] == "0x002eaa50"
    assert chain["factory_returned_closure"]["literal_upvalue_count"] == 2
    alternate = chain["alternate_registry_holder_producer"]
    assert alternate["callback_entry_rva"] == "0x002eaa50"
    assert alternate["factory_origin_claimed"] is False
    assert [item["entry_rva"] for item in evidence["callback_targets"]] == [
        "0x002e67b0",
        "0x002eaa50",
    ]
    assert [
        item["use_class"] for item in evidence["target_reference_scan"]["references"]
    ] == [
        "alternate_registry_holder_closure_producer",
        "factory_returned_closure_producer",
        "global_factory_closure_producer",
        "callback_identity_comparison",
        "callback_identity_comparison",
    ]
    assert evidence["target_reference_scan"]["aggregates"] == {
        "reference_count": 5,
        "producer_count": 3,
        "factory_producer_count": 1,
        "factory_returned_producer_count": 1,
        "alternate_producer_count": 1,
        "direct_call_count": 0,
        "comparison_count": 2,
        "other_address_count": 0,
        "memory_operand_count": 0,
    }
    assert evidence["summary"] == {
        "publication_count": 1,
        "returned_closure_count": 1,
        "alternate_producer_count": 1,
        "unique_callback_target_count": 2,
        "reviewed_function_count": 2,
        "reviewed_function_bytes": 125,
        "sealed_control_flow_graph_count": 2,
        "sealed_control_flow_graph_node_count": 45,
        "sealed_control_flow_graph_edge_count": 46,
        "literal_count": 3,
        "direct_lua_call_count": 7,
        "dynamic_register_call_count": 0,
        "target_reference_count": 5,
        "target_reference_producer_count": 3,
        "target_reference_comparison_count": 2,
        "target_reference_direct_call_count": 0,
        "target_reference_other_address_count": 0,
        "target_reference_memory_operand_count": 0,
        "factory_normal_result_count": 1,
        "returned_callback_binary_fallback_result_count": 0,
        "schema_violations": 0,
    }
    assert evidence["literals"][2]["text"] is None
    assert evidence["literals"][2]["text_published"] is False
    serialized = json.dumps(evidence, sort_keys=True)
    assert "property '%s' is read only" not in serialized
    assert "__index" not in serialized
    assert "__newindex" not in serialized
    assert (
        "that callback identity proves factory origin or a particular upvalue schema"
        in evidence["method"]["not_claimed"]
    )


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("terminal_disposition_census", "canonical_sha256"), "0" * 64),
        (
            ("publication_chain", "property_publication", "callback_entry_rva"),
            "0x002eaa50",
        ),
        (
            (
                "publication_chain",
                "factory_returned_closure",
                "caller_callback_target_witness",
                "construction_call_rva",
            ),
            "0x002e6bc3",
        ),
        (
            (
                "publication_chain",
                "alternate_registry_holder_producer",
                "factory_origin_claimed",
            ),
            True,
        ),
        (("literals", 2, "nul_terminated_bytes_sha256"), "1" * 64),
        (("function_bodies", 0, "reviewed_points", 0, "sha256"), "2" * 64),
        (("function_bodies", 0, "direct_lua_call_partition_complete"), False),
        (("function_bodies", 1, "dynamic_register_call_rvas"), ["0x002eaa53"]),
        (
            ("target_reference_scan", "references", 0, "use_class"),
            "factory_returned_closure_producer",
        ),
        (("target_reference_scan", "scope", "decoded_instructions"), 1),
        (("summary", "target_reference_count"), 4),
        (("method", "accepted_chain"), "changed"),
    ],
)
def test_structural_validator_rejects_tamper(
    monkeypatch, real_inputs, path, replacement
):
    evidence = copy.deepcopy(real_inputs["evidence"])
    target = evidence
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = replacement
    with pytest.raises(NativeLuaPropertyFactoryChainError):
        _fast_structure(monkeypatch, evidence, real_inputs)


def _accept_mutated_cfg_identity(monkeypatch, evidence, graph_index):
    graph = evidence["control_flow_graphs"][graph_index]
    digest = property_chain._canonical_sha256(graph)
    body = next(
        item
        for item in evidence["function_bodies"]
        if item["entry_rva"] == graph["caller_entry_rva"]
    )
    body["control_flow_graph_canonical_sha256"] = digest
    profile = copy.deepcopy(property_chain._SEALED_PROFILE)
    expected = next(
        item
        for item in profile["functions"]
        if property_chain._hex(item["entry_rva"]) == graph["caller_entry_rva"]
    )
    expected["cfg_canonical_sha256"] = digest
    monkeypatch.setattr(
        property_chain,
        "_PROFILES",
        {profile["executable_sha256"]: profile},
    )


def test_structural_validator_rejects_cfg_point_divergence(monkeypatch, real_inputs):
    evidence = copy.deepcopy(real_inputs["evidence"])
    point = evidence["function_bodies"][0]["reviewed_points"][0]
    graph = evidence["control_flow_graphs"][0]
    node = next(item for item in graph["nodes"] if item["rva"] == point["rva"])
    node["sha256"] = "3" * 64
    with pytest.raises(NativeLuaPropertyFactoryChainError, match="sealed CFG identity"):
        _fast_structure(monkeypatch, evidence, real_inputs)


@pytest.mark.parametrize("encoded", [f"ffd{register:x}" for register in range(8)])
def test_structural_validator_rejects_ungrouped_register_call(
    monkeypatch, real_inputs, encoded
):
    evidence = copy.deepcopy(real_inputs["evidence"])
    graph = evidence["control_flow_graphs"][0]
    node = next(item for item in graph["nodes"] if item["rva"] == "0x002e67bf")
    node["sha256"] = hashlib.sha256(bytes.fromhex(encoded)).hexdigest()
    node["flow_kind"] = "call_fallthrough"
    _accept_mutated_cfg_identity(monkeypatch, evidence, 0)
    with pytest.raises(
        NativeLuaPropertyFactoryChainError,
        match="dynamic register-call partition",
    ):
        _fast_structure(monkeypatch, evidence, real_inputs)


def test_structural_validator_rejects_unknown_field(monkeypatch, real_inputs):
    evidence = copy.deepcopy(real_inputs["evidence"])
    evidence["unexpected"] = True
    with pytest.raises(NativeLuaPropertyFactoryChainError, match="fields differ"):
        _fast_structure(monkeypatch, evidence, real_inputs)


def test_cli_parser_has_full_prerequisite_surface():
    args = property_cli.build_parser().parse_args(
        [
            "verify",
            "--executable",
            "Breach.exe",
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
            "table.json",
            "--indirect-settable-publications",
            "indirect.json",
            "--table-key-provenance",
            "keys.json",
            "--terminal-dispositions",
            "terminal.json",
            "--evidence",
            "evidence.json",
        ]
    )
    assert args.command == "verify"
    assert args.terminal_dispositions == Path("terminal.json")


def _writer_fixture(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    output_root = repo / "data" / "observatory" / "programs"
    output_root.mkdir(parents=True)
    monkeypatch.setattr(property_cli, "_REPO_ROOT", repo)
    monkeypatch.setattr(property_cli, "_OUTPUT_ROOT", output_root)
    return repo, output_root


def test_cli_immutable_writer_first_write_idempotence_and_refusal(
    monkeypatch, tmp_path, real_inputs
):
    repo, output_root = _writer_fixture(monkeypatch, tmp_path)
    evidence = real_inputs["evidence"]
    rendered = encode_native_lua_property_factory_chain(evidence)
    destination = output_root / "evidence.json"
    property_cli._write_evidence_immutably(destination, rendered, evidence)
    first = destination.read_bytes()
    before = destination.stat().st_mtime_ns
    property_cli._write_evidence_immutably(destination, rendered, evidence)
    assert destination.read_bytes() == first
    assert destination.stat().st_mtime_ns == before
    changed = copy.deepcopy(evidence)
    changed["summary"]["schema_violations"] = 1
    with pytest.raises(NativeLuaPropertyFactoryChainError, match="refusing to overwrite"):
        property_cli._write_evidence_immutably(
            destination,
            encode_native_lua_property_factory_chain(changed),
            changed,
        )
    with pytest.raises(NativeLuaPropertyFactoryChainError, match="direct child"):
        property_cli._write_evidence_immutably(
            repo / "outside.json", rendered, evidence
        )


def test_cli_immutable_writer_detects_existing_output_race(
    monkeypatch, tmp_path, real_inputs
):
    _repo, output_root = _writer_fixture(monkeypatch, tmp_path)
    evidence = real_inputs["evidence"]
    rendered = encode_native_lua_property_factory_chain(evidence)
    destination = output_root / "evidence.json"
    property_cli._write_evidence_immutably(destination, rendered, evidence)
    changed = copy.deepcopy(evidence)
    changed["summary"]["schema_violations"] = 1
    raced = encode_native_lua_property_factory_chain(changed).encode("utf-8")
    original_read = property_cli._read_json_document
    destination_reads = 0

    def race_read(path, label):
        nonlocal destination_reads
        value, payload = original_read(path, label)
        if Path(path) == destination:
            destination_reads += 1
            if destination_reads == 1:
                destination.write_bytes(raced)
        return value, payload

    monkeypatch.setattr(property_cli, "_read_json_document", race_read)
    with pytest.raises(NativeLuaPropertyFactoryChainError, match="changed during comparison"):
        property_cli._write_evidence_immutably(destination, rendered, evidence)
    assert destination_reads == 2
    assert destination.read_bytes() == raced


def test_cli_immutable_writer_rejects_reparse_root(
    monkeypatch, tmp_path, real_inputs
):
    _repo, output_root = _writer_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(property_cli, "_is_reparse", lambda _info: True)
    evidence = real_inputs["evidence"]
    with pytest.raises(NativeLuaPropertyFactoryChainError, match="real directory"):
        property_cli._write_evidence_immutably(
            output_root / "evidence.json",
            encode_native_lua_property_factory_chain(evidence),
            evidence,
        )
