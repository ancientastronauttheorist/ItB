from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import itb_native_lua_super_rebinding as super_cli
from src.observatory import native_lua_super_rebinding as super_chain
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError,
)
from src.observatory.native_lua_cclosure_table_key_provenance import (
    NativeLuaCClosureTableKeyProvenanceError,
)
from src.observatory.native_lua_super_rebinding import (
    ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND,
    NativeLuaSuperRebindingError,
    build_native_lua_super_rebinding_chain,
    encode_native_lua_super_rebinding_chain,
    validate_native_lua_super_rebinding_chain,
    validate_native_lua_super_rebinding_structure,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROGRAM_ROOT = _REPO_ROOT / "data" / "observatory" / "programs"
_INVENTORY_ROOT = _REPO_ROOT / "data" / "observatory" / "inventories"
_PREFIX = "windows_build_13725832_31fe35265598_"
_EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_RAW_SHA256 = "3b79c82dde6b1bdb7e0b36f9612dc4e5d598b7505ab76411ad6035dccafe34a2"
_CANONICAL_SHA256 = "da064ec63caddb0f3c7735caefa8397795455be76a9ead2ffc8ed678a9612ba4"


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
        "evidence": _PROGRAM_ROOT / f"{_PREFIX}native_lua_super_rebinding.json",
    }
    missing = [path for path in paths.values() if not path.is_file()]
    if missing:
        pytest.skip("committed super-rebinding prerequisites are unavailable")
    return {name: _load(path) for name, path in paths.items()}


def _structure_args(values: dict[str, dict]) -> tuple[dict, ...]:
    return (
        values["direct"],
        values["callbacks"],
        values["setfield"],
        values["direct_table"],
        values["indirect"],
        values["table_keys"],
        values["facts"],
    )


def _fast_structure(
    monkeypatch: pytest.MonkeyPatch,
    evidence: dict,
    values: dict[str, dict],
) -> dict:
    monkeypatch.setattr(
        super_chain,
        "validate_native_lua_cclosure_table_key_provenance_structure",
        lambda *args, **kwargs: {
            "analysis_kind": super_chain.TABLE_KEY_STRUCTURE_VERIFICATION_KIND,
            "status": "structurally_verified",
        },
    )
    return validate_native_lua_super_rebinding_structure(
        evidence, *_structure_args(values)
    )


def test_committed_artifact_encoding_and_digests(real_inputs):
    path = _PROGRAM_ROOT / f"{_PREFIX}native_lua_super_rebinding.json"
    payload = path.read_bytes()
    evidence = real_inputs["evidence"]
    assert hashlib.sha256(payload).hexdigest() == _RAW_SHA256
    assert super_chain._canonical_sha256(evidence) == _CANONICAL_SHA256
    assert payload == encode_native_lua_super_rebinding_chain(evidence).encode("utf-8")
    assert evidence["analysis_kind"] == ANALYSIS_KIND


def test_committed_artifact_full_structural_validation(real_inputs):
    receipt = validate_native_lua_super_rebinding_structure(
        real_inputs["evidence"], *_structure_args(real_inputs)
    )
    assert receipt["analysis_kind"] == STRUCTURE_VERIFICATION_KIND
    assert receipt["status"] == "structurally_verified"
    assert receipt["evidence_sha256"] == _CANONICAL_SHA256


def test_committed_artifact_exact_rebuild_and_verification(real_inputs):
    if not _EXE.is_file() or hashlib.sha256(_EXE.read_bytes()).hexdigest() != _EXE_SHA256:
        pytest.skip("sealed Breach.exe is unavailable")
    rebuilt = build_native_lua_super_rebinding_chain(
        _EXE,
        *_structure_args(real_inputs)[:-1],
        real_inputs["facts"],
        inventory=real_inputs["inventory"],
    )
    assert rebuilt == real_inputs["evidence"]
    receipt = validate_native_lua_super_rebinding_chain(
        _EXE,
        real_inputs["evidence"],
        *_structure_args(real_inputs)[:-1],
        real_inputs["facts"],
        inventory=real_inputs["inventory"],
    )
    assert receipt["status"] == "verified"
    assert receipt["evidence_sha256"] == _CANONICAL_SHA256


def test_expected_chain_partition_and_nonclaims(real_inputs):
    evidence = real_inputs["evidence"]
    assert [item["callback_call_rva"] for item in evidence["publications"]] == [
        "0x002e6c01",
        "0x002eb086",
        "0x002eb2a5",
    ]
    assert [item["callback_entry_rva"] for item in evidence["publications"]] == [
        "0x002e6810",
        "0x002eb230",
        "0x002eb230",
    ]
    assert evidence["target_reference_scan"]["aggregates"] == {
        "reference_count": 3,
        "producer_count": 3,
        "direct_call_count": 0,
        "comparison_count": 0,
        "other_address_count": 0,
        "memory_operand_count": 0,
    }
    assert evidence["literals"][1]["text"] is None
    assert evidence["literals"][1]["text_published"] is False
    assert evidence["summary"]["sealed_control_flow_graph_count"] == 4
    assert evidence["summary"]["staged_lua_dispatch_count"] == 5
    assert evidence["summary"]["staged_lua_call_count"] == 13
    assert all(
        body["staged_register_call_partition_complete"] is True
        for body in evidence["function_bodies"]
    )
    assert "runtime reachability, execution order, frequency, or persistence" in evidence["method"]["not_claimed"]


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("literals", 0, "nul_terminated_bytes_sha256"), "0" * 64),
        (("publications", 1, "callback_entry_rva"), "0x002e6810"),
        (("function_bodies", 2, "reviewed_points", 0, "sha256"), "1" * 64),
        (("function_bodies", 1, "staged_lua_dispatches", 0, "iat_rva"), "0x00000000"),
        (("function_bodies", 2, "staged_lua_dispatches", 0, "stage", "sha256"), "3" * 64),
        (("function_bodies", 3, "staged_lua_dispatches", 0, "call_sites", 2, "call", "sha256"), "4" * 64),
        (("function_bodies", 3, "staged_lua_dispatches", 1, "call_sites", 1, "stage_to_call_path_node_count"), 1),
        (("target_reference_scan", "references", 0, "use_class"), "direct_call"),
        (("target_reference_scan", "scope", "decoded_instructions"), 1),
        (("summary", "target_reference_count"), 4),
        (("method", "accepted_chain"), "changed"),
    ],
)
def test_structural_validator_rejects_tamper(
    monkeypatch,
    real_inputs,
    path,
    replacement,
):
    evidence = copy.deepcopy(real_inputs["evidence"])
    target = evidence
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = replacement
    with pytest.raises(
        (
            NativeLuaSuperRebindingError,
            NativeLuaCClosurePublicationError,
            NativeLuaCClosureTableKeyProvenanceError,
        )
    ):
        _fast_structure(monkeypatch, evidence, real_inputs)


def test_structural_validator_rejects_cfg_point_divergence(monkeypatch, real_inputs):
    evidence = copy.deepcopy(real_inputs["evidence"])
    point = evidence["function_bodies"][0]["reviewed_points"][0]
    graph = evidence["control_flow_graphs"][0]
    node = next(item for item in graph["nodes"] if item["rva"] == point["rva"])
    node["sha256"] = "2" * 64
    with pytest.raises(NativeLuaSuperRebindingError, match="sealed CFG identity"):
        _fast_structure(monkeypatch, evidence, real_inputs)


def _accept_mutated_cfg_identity(monkeypatch, evidence, function_index):
    graph = evidence["control_flow_graphs"][function_index]
    digest = super_chain._canonical_sha256(graph)
    evidence["function_bodies"][function_index][
        "control_flow_graph_canonical_sha256"
    ] = digest
    profile = copy.deepcopy(super_chain._SEALED_PROFILE)
    profile["functions"][function_index]["cfg_canonical_sha256"] = digest
    monkeypatch.setattr(
        super_chain,
        "_PROFILES",
        {profile["executable_sha256"]: profile},
    )


def test_structural_validator_rejects_sealed_branch_path_divergence(
    monkeypatch, real_inputs
):
    evidence = copy.deepcopy(real_inputs["evidence"])
    graph = evidence["control_flow_graphs"][3]
    branch = next(item for item in graph["nodes"] if item["rva"] == "0x002eb26b")
    branch["successor_rvas"] = ["0x002eb26d", "0x002eb289"]
    _accept_mutated_cfg_identity(monkeypatch, evidence, 3)
    with pytest.raises(NativeLuaSuperRebindingError, match="dominating EBX stage"):
        _fast_structure(monkeypatch, evidence, real_inputs)


def test_structural_validator_rejects_staged_register_writer(
    monkeypatch, real_inputs
):
    evidence = copy.deepcopy(real_inputs["evidence"])
    graph = evidence["control_flow_graphs"][1]
    node = next(item for item in graph["nodes"] if item["rva"] == "0x002ea472")
    node["writes_esi"] = True
    _accept_mutated_cfg_identity(monkeypatch, evidence, 1)
    with pytest.raises(NativeLuaSuperRebindingError, match="provenance is clobbered"):
        _fast_structure(monkeypatch, evidence, real_inputs)


def test_structural_validator_rejects_unknown_field(monkeypatch, real_inputs):
    evidence = copy.deepcopy(real_inputs["evidence"])
    evidence["unexpected"] = True
    with pytest.raises(NativeLuaCClosurePublicationError, match="fields differ"):
        _fast_structure(monkeypatch, evidence, real_inputs)


def test_cli_parser_has_full_prerequisite_surface():
    parser = super_cli.build_parser()
    args = parser.parse_args(
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
            "--evidence",
            "evidence.json",
        ]
    )
    assert args.command == "verify"
    assert args.table_key_provenance == Path("keys.json")


def test_cli_immutable_writer_first_write_idempotence_and_refusal(
    monkeypatch,
    tmp_path,
    real_inputs,
):
    repo = tmp_path / "repo"
    output_root = repo / "data" / "observatory" / "programs"
    output_root.mkdir(parents=True)
    monkeypatch.setattr(super_cli, "_REPO_ROOT", repo)
    monkeypatch.setattr(super_cli, "_OUTPUT_ROOT", output_root)
    evidence = real_inputs["evidence"]
    rendered = encode_native_lua_super_rebinding_chain(evidence)
    destination = output_root / "evidence.json"
    super_cli._write_evidence_immutably(destination, rendered, evidence)
    assert destination.read_text(encoding="utf-8") == rendered
    super_cli._write_evidence_immutably(destination, rendered, evidence)
    changed = copy.deepcopy(evidence)
    changed["summary"]["schema_violations"] = 1
    with pytest.raises(NativeLuaSuperRebindingError, match="refusing to overwrite"):
        super_cli._write_evidence_immutably(
            destination,
            encode_native_lua_super_rebinding_chain(changed),
            changed,
        )
    with pytest.raises(NativeLuaSuperRebindingError, match="direct child"):
        super_cli._write_evidence_immutably(
            repo / "outside.json", rendered, evidence
        )
