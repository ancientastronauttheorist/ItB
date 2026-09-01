"""Exact and adversarial tests for native Lua class-initializer evidence."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import itb_native_lua_class_initializer_chain as cli
from src.observatory import native_lua_class_initializer_chain as initializer
from src.observatory.native_lua_class_initializer_chain import (
    NativeLuaClassInitializerChainError,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
RAW_SHA256 = "8bd9b4ad928675f0cb2e708ec6695daf1618dfbd3eff1324f8bfa7147bc9a4b2"
CANONICAL_SHA256 = "799ab272966a317f27c0fbaf25df7d47821650a6f5e0b1a914c98eb40dcfece9"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values() -> dict:
    paths = {
        "inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"),
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "class_factory": PROGRAMS / (PREFIX + "native_lua_class_factory_chain.json"),
        "evidence": PROGRAMS / (PREFIX + "native_lua_class_initializer_chain.json"),
    }
    if any(not path.is_file() for path in paths.values()):
        pytest.skip("class-initializer evidence prerequisites are unavailable")
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    return result


def _common(values: dict) -> tuple[dict, dict, dict]:
    return values["class_factory"], values["direct"], values["facts"]


def _structure(values: dict, evidence: dict | None = None) -> dict:
    return initializer.validate_native_lua_class_initializer_chain_structure(
        values["evidence"] if evidence is None else evidence,
        *_common(values),
    )


def _fast_structure(monkeypatch, values: dict, evidence: dict) -> dict:
    monkeypatch.setattr(
        initializer,
        "validate_native_lua_direct_call_structure",
        lambda *args, **kwargs: {
            "status": "structurally_verified",
            "evidence_sha256": initializer._DIRECT_SHA256,
        },
    )
    return _structure(values, evidence)


def _body(evidence: dict) -> dict:
    assert len(evidence["function_bodies"]) == 1
    return evidence["function_bodies"][0]


def _graph(evidence: dict) -> dict:
    assert len(evidence["control_flow_graphs"]) == 1
    return evidence["control_flow_graphs"][0]


def _point(evidence: dict, role: str) -> dict:
    return next(item for item in _body(evidence)["reviewed_points"] if item["role"] == role)


def _changed(value: object) -> object:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        return "changed"
    if isinstance(value, list):
        return [] if value else ["changed"]
    if isinstance(value, dict):
        return {}
    if value is None:
        return "changed"
    raise AssertionError(f"no deterministic mutation for {value!r}")


def _rejects(values: dict, monkeypatch, evidence: dict) -> None:
    with pytest.raises(NativeLuaClassInitializerChainError):
        _fast_structure(monkeypatch, values, evidence)


def test_committed_artifact_encoding_structure_and_summary(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert raw == initializer.encode_native_lua_class_initializer_chain(evidence).encode("utf-8")
    assert hashlib.sha256(raw).hexdigest() == RAW_SHA256
    assert initializer._canonical_sha256(evidence) == CANONICAL_SHA256
    receipt = _structure(values)
    assert receipt["status"] == "structurally_verified"
    assert type(receipt["evidence_sha256"]) is str
    assert len(receipt["evidence_sha256"]) == 64
    assert evidence["summary"] == {
        "reviewed_initializer_count": 1,
        "reviewed_initializer_bytes": 612,
        "sealed_control_flow_graph_count": 1,
        "sealed_control_flow_graph_node_count": 185,
        "sealed_control_flow_graph_edge_count": 191,
        "direct_lua_call_count": 20,
        "staged_lua_dispatch_count": 2,
        "staged_lua_call_count": 6,
        "total_lua_call_count": 26,
        "call_r32_count": 6,
        "literal_count": 3,
        "selected_native_edge_count": 2,
        "unique_native_edge_target_count": 2,
        "initializer_target_count": 1,
        "class_factory_initializer_edge_count": 1,
        "target_reference_count": 1,
        "target_reference_direct_call_count": 1,
        "target_reference_comparison_count": 0,
        "target_reference_other_address_count": 0,
        "target_reference_memory_operand_count": 0,
        "target_reference_owner_count": 1,
        "schema_violations": 0,
    }


def test_committed_artifact_exact_rebuild_and_verification(values):
    if not EXE.is_file() or hashlib.sha256(EXE.read_bytes()).hexdigest() != EXE_SHA256:
        pytest.skip("sealed Breach.exe is unavailable")
    rebuilt = initializer.build_native_lua_class_initializer_chain(
        EXE, *_common(values), inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    receipt = initializer.validate_native_lua_class_initializer_chain(
        EXE, values["evidence"], *_common(values), inventory=values["inventory"]
    )
    assert receipt["status"] == "verified"
    assert receipt["evidence_sha256"] == CANONICAL_SHA256


def test_offset_only_contract_and_complete_reference_frontier(values):
    evidence = values["evidence"]
    facts = _body(evidence)["semantic_facts"]
    assert facts["receiver_register_transition"] == "ECX_to_EDI"
    assert facts["source_semantic_names_assigned"] is False
    assert facts["fixed_offset_writes"] == {
        "0x0": "0x0089d1d4", "0x4": 0, "0x8": 0, "0xc": 0,
        "0x10": "argument_2", "0x14": 0, "0x18": -2, "0x1c": 0,
        "0x20": -2, "0x24": 0, "0x28": -2, "0x2c": 1,
        "0x30": "classes_lookup_result_plus_8",
        "0x34": "native_0x0007c600_return_after_zero", "0x38": 0,
        "0x3c": 0, "0x40": "cast_graph_lookup_result",
        "0x44": "class_id_map_lookup_result",
    }
    assert facts["registry_index"] == -10000
    assert facts["reference_sentinel"] == -2
    assert facts["first_ref_pair_offsets"] == [28, 32]
    assert facts["second_ref_pair_offsets"] == [36, 40]
    assert facts["third_ref_pair_offsets"] == [20, 24]
    assert facts["prior_ref_unreference_condition"] == "old_state_nonzero_and_old_ref_not_minus_2"
    assert facts["classes_guard_condition"] == "registry_classes_result_plus_0x0c_equals_minus_2"
    assert facts["classes_reference_offset"] == 16
    assert facts["registry_key_lookup_api"] == "lua_gettable"
    assert facts["registry_key_lookup_raw_claimed"] is False
    assert facts["assertion_helper_termination_claimed"] is False
    assert facts["return_register"] == "EDI"
    assert facts["runtime_or_success_claimed"] is False
    assert _point(evidence, "classes_reference_rawgeti")["direct_lua_import"] == "lua_rawgeti"
    assert _point(evidence, "classes_metatable_set")["meaning"]["index"] == -2
    assert _point(evidence, "return_edi")["meaning"]["destination"] == "EAX"
    scan = evidence["whole_atlas_reference_scan"]
    assert len(scan["references"]) == 1
    reference = scan["references"][0]
    assert reference["instruction_rva"] == "0x002ec302"
    assert reference["owner_entry_rva"] == "0x002ec220"
    assert reference["target_rva"] == "0x002eacf0"
    assert reference["use_class"] == "direct_call"
    assert scan["aggregates"] == {
        "reference_count": 1,
        "direct_call_count": 1,
        "comparison_count": 0,
        "other_address_count": 0,
        "memory_operand_count": 0,
        "owner_count": 1,
    }
    not_claimed = evidence["method"]["not_claimed"]
    assert any("runtime reachability" in item for item in not_claimed)
    assert any("source-level class" in item for item in not_claimed)
    assert any("native callee 0x0007c600" in item for item in not_claimed)


@pytest.mark.parametrize(
    "key",
    [
        "schema_version", "analysis_kind", "build_identity", "atlas",
        "direct_call_census", "class_factory_chain", "decoder",
        "conditional_initializer_edge", "initializer_targets", "literals", "function_bodies",
        "control_flow_graphs", "native_edges", "whole_atlas_reference_scan",
        "method", "summary",
    ],
)
def test_structure_rejects_every_retained_top_level_category(values, monkeypatch, key):
    evidence = copy.deepcopy(values["evidence"])
    evidence[key] = _changed(evidence[key])
    _rejects(values, monkeypatch, evidence)


def test_structure_rejects_unknown_top_level_key(values, monkeypatch):
    evidence = copy.deepcopy(values["evidence"])
    evidence["unexpected"] = True
    _rejects(values, monkeypatch, evidence)


def test_structure_rejects_every_direct_call_field(values, monkeypatch):
    original = _body(values["evidence"])["direct_lua_calls"][0]
    for field, value in original.items():
        evidence = copy.deepcopy(values["evidence"])
        _body(evidence)["direct_lua_calls"][0][field] = _changed(value)
        _rejects(values, monkeypatch, evidence)


def test_structure_rejects_every_semantic_fact(values, monkeypatch):
    original = _body(values["evidence"])["semantic_facts"]
    for field, value in original.items():
        evidence = copy.deepcopy(values["evidence"])
        _body(evidence)["semantic_facts"][field] = _changed(value)
        _rejects(values, monkeypatch, evidence)


def test_structure_rejects_reviewed_point_and_meaning_tamper(values, monkeypatch):
    original = _point(values["evidence"], "classes_guard")
    for field, value in original.items():
        if field == "meaning":
            continue
        evidence = copy.deepcopy(values["evidence"])
        _point(evidence, "classes_guard")[field] = _changed(value)
        _rejects(values, monkeypatch, evidence)
    for field, value in original["meaning"].items():
        evidence = copy.deepcopy(values["evidence"])
        _point(evidence, "classes_guard")["meaning"][field] = _changed(value)
        _rejects(values, monkeypatch, evidence)
    evidence = copy.deepcopy(values["evidence"])
    _point(evidence, "return_edi")["meaning"]["unexpected"] = True
    _rejects(values, monkeypatch, evidence)


def _accept_mutated_cfg_identity(monkeypatch, evidence: dict) -> None:
    graph = _graph(evidence)
    digest = initializer._canonical_sha256(graph)
    _body(evidence)["control_flow_graph_canonical_sha256"] = digest
    function = copy.deepcopy(initializer._FUNCTION)
    function["cfg_canonical_sha256"] = digest
    profile = copy.deepcopy(initializer._PROFILE)
    profile["functions"] = [function]
    monkeypatch.setattr(initializer, "_FUNCTION", function)
    monkeypatch.setattr(initializer, "_PROFILE", profile)


def test_structure_rejects_staged_register_writer(values, monkeypatch):
    evidence = copy.deepcopy(values["evidence"])
    graph = _graph(evidence)
    node = next(item for item in graph["nodes"] if item["rva"] == "0x002eadc8")
    node["writes_ebx"] = True
    _accept_mutated_cfg_identity(monkeypatch, evidence)
    _rejects(values, monkeypatch, evidence)


def test_structure_rejects_staged_dispatch_and_path_tamper(values, monkeypatch):
    original = _body(values["evidence"])["staged_lua_dispatches"][0]
    for field, value in original["stage"].items():
        evidence = copy.deepcopy(values["evidence"])
        _body(evidence)["staged_lua_dispatches"][0]["stage"][field] = _changed(value)
        _rejects(values, monkeypatch, evidence)
    for field, value in original["call_sites"][0].items():
        evidence = copy.deepcopy(values["evidence"])
        _body(evidence)["staged_lua_dispatches"][0]["call_sites"][0][field] = _changed(value)
        _rejects(values, monkeypatch, evidence)
    evidence = copy.deepcopy(values["evidence"])
    _body(evidence)["staged_lua_dispatches"][0]["stage"]["unexpected"] = True
    _rejects(values, monkeypatch, evidence)


@pytest.mark.parametrize("register_index", range(8))
def test_structure_rejects_ungrouped_call_r32(values, monkeypatch, register_index):
    evidence = copy.deepcopy(values["evidence"])
    graph = _graph(evidence)
    node = next(item for item in graph["nodes"] if item["rva"] == "0x002eadd3")
    node["sha256"] = hashlib.sha256(bytes((0xFF, 0xD0 + register_index))).hexdigest()
    _accept_mutated_cfg_identity(monkeypatch, evidence)
    _rejects(values, monkeypatch, evidence)


@pytest.mark.parametrize(
    "path",
    [
        ("literals", 0, "nul_terminated_bytes_sha256"),
        ("native_edges", 0, "target_entry_rva"),
        ("whole_atlas_reference_scan", "scope", "decoded_instructions"),
        ("whole_atlas_reference_scan", "references", 0, "target_rva"),
        ("method", "not_claimed"),
        ("summary", "target_reference_count"),
    ],
)
def test_structure_rejects_nested_proof_categories(values, monkeypatch, path):
    evidence = copy.deepcopy(values["evidence"])
    container: object = evidence
    for key in path[:-1]:
        container = container[key]  # type: ignore[index]
    key = path[-1]
    container[key] = _changed(container[key])  # type: ignore[index]
    _rejects(values, monkeypatch, evidence)


def _patch_output_root(monkeypatch, tmp_path: Path) -> None:
    info = tmp_path.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def test_cli_parser_exposes_complete_surface():
    common = []
    for flag in ("--class-factory", "--direct-calls", "--program-facts"):
        common += [flag, "input.json"]
    parser = cli.build_parser()
    execution = ["--executable", "Breach.exe", "--inventory", "inventory.json"]
    assert parser.parse_args(["build", *common, *execution, "--output", "out.json"]).command == "build"
    assert parser.parse_args(["verify", *common, *execution, "--evidence", "out.json"]).command == "verify"
    assert parser.parse_args(["verify-structure", *common, "--evidence", "out.json"]).command == "verify-structure"


@pytest.mark.parametrize("payload", ['{"a": 1, "a": 2}', '{"a": NaN}'])
def test_cli_main_reports_strict_json_errors(tmp_path, capsys, payload):
    malformed = tmp_path / "malformed.json"
    malformed.write_text(payload, encoding="utf-8")
    argv = ["verify"]
    for flag in ("--executable", "--inventory", "--class-factory", "--direct-calls", "--program-facts", "--evidence"):
        argv += [flag, str(malformed)]
    assert cli.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "Traceback" not in captured.err


def test_cli_writer_is_immutable(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    evidence = values["evidence"]
    rendered = initializer.encode_native_lua_class_initializer_chain(evidence)
    output = tmp_path / "evidence.json"
    cli._write_immutably(output, rendered, evidence)
    cli._write_immutably(output, rendered, evidence)
    output.write_text(rendered + " ", encoding="utf-8")
    with pytest.raises(NativeLuaClassInitializerChainError, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, evidence)


@pytest.mark.parametrize("kind", ["symlink", "reparse", "directory"])
def test_cli_writer_rejects_nonregular_existing_output(tmp_path, monkeypatch, values, kind):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = initializer.encode_native_lua_class_initializer_chain(values["evidence"])
    if kind == "symlink":
        target = tmp_path / "target.json"
        target.write_text(rendered, encoding="utf-8")
        try:
            output.symlink_to(target)
        except OSError as exc:
            pytest.skip(f"symlink creation unavailable: {exc}")
    elif kind == "reparse":
        output.write_text(rendered, encoding="utf-8")
        monkeypatch.setattr(cli, "_is_reparse", lambda _info: True)
    else:
        output.mkdir()
    with pytest.raises(NativeLuaClassInitializerChainError, match="linked, reparse, or non-regular"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_cli_writer_detects_existing_inode_swap(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = initializer.encode_native_lua_class_initializer_chain(values["evidence"])
    output.write_text(rendered, encoding="utf-8")
    original_reader = cli._read_json_document

    def swapped_reader(path: Path, label: str):
        result = original_reader(path, label)
        path.unlink()
        path.write_text(rendered, encoding="utf-8")
        return result

    monkeypatch.setattr(cli, "_read_json_document", swapped_reader)
    with pytest.raises(NativeLuaClassInitializerChainError, match="changed during validation"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_cli_writer_rejects_output_outside_programs(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    rendered = initializer.encode_native_lua_class_initializer_chain(values["evidence"])
    with pytest.raises(NativeLuaClassInitializerChainError, match="direct child"):
        cli._write_immutably(tmp_path.parent / "evidence.json", rendered, values["evidence"])


@pytest.mark.parametrize("failure_site", ["prepare", "recheck"])
def test_cli_main_reports_output_root_failures(tmp_path, monkeypatch, capsys, values, failure_site):
    output = tmp_path / "evidence.json"
    argv = [
        "build", "--executable", str(EXE), "--inventory", str(values["paths"]["inventory"]),
        "--class-factory", str(values["paths"]["class_factory"]),
        "--direct-calls", str(values["paths"]["direct"]),
        "--program-facts", str(values["paths"]["facts"]), "--output", str(output),
    ]
    monkeypatch.setattr(cli, "build_native_lua_class_initializer_chain", lambda *args, **kwargs: values["evidence"])
    if failure_site == "prepare":
        monkeypatch.setattr(
            cli, "_prepare_output_root",
            lambda: (_ for _ in ()).throw(cli.NativeLuaPropertyFactoryChainError("unsafe output root")),
        )
    else:
        info = tmp_path.stat()
        monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
        monkeypatch.setattr(
            cli, "_recheck_output_root",
            lambda *args: (_ for _ in ()).throw(cli.NativeLuaPropertyFactoryChainError("changed output root")),
        )
    assert cli.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "Traceback" not in captured.err
