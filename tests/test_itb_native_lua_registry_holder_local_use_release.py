"""Exact, adversarial, and publication tests for the registry-holder census."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import itb_native_lua_registry_holder_local_use_release as cli
from src.observatory import native_lua_registry_holder_local_use_release as holder
from src.observatory.native_lua_registry_holder_local_use_release import (
    NativeLuaRegistryHolderError,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
RAW_SHA256 = "139ed2444ee9b8824a4913638214db8c68a7899340a5e53b955c4a367c576755"
CANONICAL_SHA256 = "395603c2a163925fc202a5a35791200859313872c242fe5901e4de8c05ab892f"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values() -> dict:
    paths = {
        "inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"),
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "terminal": PROGRAMS / (PREFIX + "native_lua_cclosure_terminal_dispositions.json"),
        "evidence": PROGRAMS / (PREFIX + "native_lua_registry_holder_local_use_release_census.json"),
    }
    if any(not path.is_file() for path in paths.values()):
        pytest.skip("registry-holder evidence prerequisites are unavailable")
    result = {key: _read(path) for key, path in paths.items()}
    result["paths"] = paths
    result["expected"] = holder._expected_artifact(
        result["facts"], result["direct"], result["terminal"]
    )
    result["functions"] = holder._atlas_functions(result["facts"])
    result["edges"] = holder._ghidra_edges(result["facts"])
    return result


def _structure(values: dict, evidence: dict | None = None) -> dict:
    return holder.validate_native_lua_registry_holder_local_use_release_census_structure(
        values["evidence"] if evidence is None else evidence,
        values["facts"],
        values["direct"],
        values["terminal"],
    )


def test_pinned_bytes_complete_partition_and_structural_replay(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW_SHA256
    assert holder._canonical_sha256(evidence) == CANONICAL_SHA256
    assert holder.encode_native_lua_registry_holder_local_use_release_census(evidence).encode() == raw
    assert evidence == values["expected"]
    receipt = _structure(values)
    assert receipt["status"] == "structurally_verified"
    assert receipt["evidence_sha256"] == CANONICAL_SHA256


def test_complete_caller_and_reference_invariants(values):
    evidence = values["evidence"]
    assert len(evidence["callers"]) == 46
    assert len(evidence["producer"]["reviewed_sequence"]) == 33
    assert [item["api"] for item in evidence["producer"]["direct_lua_calls"]] == [
        "lua_rawgeti", "lua_rawgeti", "lua_pushcclosure", "lua_pushvalue",
        "luaL_ref", "lua_settop",
    ]
    for caller in evidence["callers"]:
        assert caller["body_size"] == 247
        assert (caller["control_flow_graph_node_count"], caller["control_flow_graph_edge_count"]) == (90, 94)
        assert len(caller["semantic_points"]) == 37
        assert [item["api"] for item in caller["direct_lua_calls"]] == ["lua_pushvalue", "lua_settable"]
        assert [item["register"] for item in caller["register_indirect_calls"]] == ["ESI"] * 6
        assert [len(item["calls"]) for item in caller["stage_path_audit"]] == [2, 2, 2]
        window = caller["holder_register_window_audit"]
        assert window["explicit_register_mention_rvas"] == [
            caller["local_holder"]["return_transfer_rva"],
            caller["local_use"]["reference_read_rva"],
        ]
        assert window["explicit_store_through_holder_register_rvas"] == []
        assert window["explicit_persistent_holder_copy_rvas"] == []
        assert window["syntactic_holder_address_argument_transfer_rvas"] == []
        assert caller["local_use"]["raw_lookup_state_equality_proven"] is False
        assert caller["excluded_second_release"]["attributed_to_holder"] is False
        assert caller["entry_audit"]["all_declared_targets_are_function_entry"] is True
    scan = evidence["whole_atlas_reference_scan"]
    assert scan["reference_count"] == 46
    assert scan["all_references_are_declared_direct_e8_calls"] is True
    assert [item["owner_entry_rva"] for item in scan["references"]] == [
        item["entry_rva"] for item in evidence["callers"]
    ]
    assert evidence["summary"] == {
        "all_source_body_bytes": 11469,
        "all_source_body_count": 47,
        "all_source_cfg_edge_count": 4360,
        "all_source_cfg_node_count": 4177,
        "caller_body_bytes": 11362,
        "caller_cfg_edge_count": 4324,
        "caller_cfg_node_count": 4140,
        "caller_direct_lua_call_count": 92,
        "caller_register_indirect_call_count": 276,
        "caller_semantic_point_count": 1702,
        "declared_direct_caller_count": 46,
        "high_rva_cluster_caller_count": 37,
        "holder_register_window_count": 46,
        "low_rva_cluster_caller_count": 9,
        "producer_direct_lua_call_count": 6,
        "schema_violations": 0,
        "whole_atlas_target_reference_count": 46,
    }


def _mutate(evidence: dict, case: str) -> None:
    caller = evidence["callers"][0]
    if case == "top_unknown": evidence["unknown"] = True
    elif case == "nested_unknown": caller["local_use"]["unknown"] = True
    elif case == "drop_caller": evidence["callers"].pop()
    elif case == "caller_order": evidence["callers"][0], evidence["callers"][1] = evidence["callers"][1], evidence["callers"][0]
    elif case == "producer_body": evidence["producer"]["body_sha256"] = "0" * 64
    elif case == "producer_cfg": evidence["producer"]["control_flow_graph_edge_count"] += 1
    elif case == "producer_direct": evidence["producer"]["direct_lua_calls"][0]["iat_rva"] = "0x003d64c1"
    elif case == "producer_sequence": evidence["producer"]["reviewed_sequence"][0]["sha256"] = "0" * 64
    elif case == "producer_point": evidence["producer"]["producer_points"][0]["role"] = "wrong"
    elif case == "terminal_join": evidence["producer"]["terminal_disposition_join"]["canonical_sha256"] = "0" * 64
    elif case == "constructor_target": caller["constructor_edge"]["target_rva"] = "0x00057971"
    elif case == "constructor_hash": caller["constructor_edge"]["sha256"] = "0" * 64
    elif case == "semantic_point": caller["semantic_points"][0]["sha256"] = "0" * 64
    elif case == "semantic_meaning": caller["semantic_points"][0]["meaning"]["stack_offset"] = 16
    elif case == "local_holder": caller["local_holder"]["stack_offset"] = 16
    elif case == "direct_call": caller["direct_lua_calls"][0]["api"] = "lua_rawgeti"
    elif case == "register_call": caller["register_indirect_calls"][0]["register"] = "EDI"
    elif case == "r32_audit": caller["call_r32_audit"][0]["call_rvas"].append("0x0005479e")
    elif case == "stage_iat": caller["stage_path_audit"][0]["iat_rva"] = "0x003d64c1"
    elif case == "stage_instruction": caller["stage_path_audit"][0]["stage_instruction"]["sha256"] = "0" * 64
    elif case == "staged_call": caller["stage_path_audit"][0]["calls"][0]["call_instruction"]["rva"] = "0x0005479f"
    elif case == "stage_path": caller["stage_path_audit"][0]["calls"][0]["path_rvas"].pop()
    elif case == "last_stage": caller["stage_path_audit"][0]["calls"][0]["last_reaching_stage_rvas"] = []
    elif case == "stage_writer": caller["stage_path_audit"][0]["calls"][0]["post_stage_esi_writer_rvas"] = ["0x0005478b"]
    elif case == "window_boundary": caller["holder_register_window_audit"]["end_exclusive_rva"] = "0x00054777"
    elif case == "window_capture": caller["holder_register_window_audit"]["holder_capture"]["sha256"] = "0" * 64
    elif case == "window_access": caller["holder_register_window_audit"]["memory_accesses_through_holder_register"][0]["access"] = "write"
    elif case == "window_store": caller["holder_register_window_audit"]["explicit_store_through_holder_register_rvas"] = ["0x00054773"]
    elif case == "window_copy": caller["holder_register_window_audit"]["explicit_persistent_holder_copy_rvas"] = ["0x00054773"]
    elif case == "window_transfer": caller["holder_register_window_audit"]["syntactic_holder_address_argument_transfer_rvas"] = ["0x00054773"]
    elif case == "window_overwrite": caller["holder_register_window_audit"]["window_end_overwrite"]["source_stack_offset"] = 16
    elif case == "local_use": caller["local_use"]["separate_temporary_stack_offset"] = 16
    elif case == "state_equality": caller["local_use"]["raw_lookup_state_equality_proven"] = True
    elif case == "release_sentinel": caller["local_release"]["sentinel"] = -1
    elif case == "release_branch": caller["local_release"]["state_null_branch_target_rva"] = "0x00054812"
    elif case == "second_release": caller["excluded_second_release"]["attributed_to_holder"] = True
    elif case == "entry_audit": caller["entry_audit"]["accepted_entry_rva"] = "0x00054741"
    elif case == "incoming_edge": caller["entry_audit"]["ghidra_declared_direct_calls_into_body"][0]["target_rva"] = "0x00054741"
    elif case == "cluster": evidence["caller_clusters"][0]["caller_count"] = 8
    elif case == "scan_scope": evidence["whole_atlas_reference_scan"]["scope"]["decoded_instructions"] -= 1
    elif case == "scan_reference": evidence["whole_atlas_reference_scan"]["references"][0]["operand_class"] = "absolute_memory"
    elif case == "scan_form": evidence["whole_atlas_reference_scan"]["references"][0]["call_form"] = "other"
    elif case == "scan_ghidra": evidence["whole_atlas_reference_scan"]["references"][0]["ghidra_declared_direct_edge"]["target_name"] = "wrong"
    elif case == "scan_complete": evidence["whole_atlas_reference_scan"]["all_references_are_declared_direct_e8_calls"] = False
    elif case == "method": evidence["method"]["holder_window_boundary"] = "unbounded"
    elif case == "nonclaim": evidence["method"]["not_claimed"].pop()
    elif case == "summary": evidence["summary"]["whole_atlas_target_reference_count"] = 45
    else: raise AssertionError(case)


@pytest.mark.parametrize("case", [
    "top_unknown", "nested_unknown", "drop_caller", "caller_order",
    "producer_body", "producer_cfg", "producer_direct", "producer_sequence",
    "producer_point", "terminal_join", "constructor_target", "constructor_hash",
    "semantic_point", "semantic_meaning", "local_holder", "direct_call",
    "register_call", "r32_audit", "stage_iat", "stage_instruction", "staged_call",
    "stage_path", "last_stage", "stage_writer", "window_boundary", "window_capture",
    "window_access", "window_store", "window_copy", "window_transfer",
    "window_overwrite", "local_use", "state_equality", "release_sentinel",
    "release_branch", "second_release", "entry_audit", "incoming_edge", "cluster",
    "scan_scope", "scan_reference", "scan_form", "scan_ghidra", "scan_complete",
    "method", "nonclaim", "summary",
])
def test_structure_rejects_every_retained_category(values, monkeypatch, case):
    # The prerequisite validators have their own suites. Cache this module's
    # already-authenticated expected replay so this matrix targets only the
    # registry-holder artifact boundary rather than repeatedly hashing the
    # 25,312-function atlas.
    monkeypatch.setattr(holder, "validate_native_lua_direct_call_structure", lambda *args, **kwargs: {})
    monkeypatch.setattr(holder, "_expected_artifact", lambda *args, **kwargs: values["expected"])
    evidence = copy.deepcopy(values["evidence"])
    _mutate(evidence, case)
    with pytest.raises(NativeLuaRegistryHolderError):
        _structure(values, evidence)


def test_entry_audit_rejects_modeled_interior_target(values):
    edges = copy.deepcopy(values["edges"])
    entry = holder._CALLERS[0]
    edges.append({
        "instruction_rva": "0x00001000",
        "source_entry_rva": "0x00001000",
        "target_entry_rva": holder._hex(entry),
        "target_name": "interior",
        "target_rva": holder._hex(entry + 0x45),
    })
    with pytest.raises(NativeLuaRegistryHolderError, match="alternate modeled interior entry"):
        holder._entry_audit_expected(edges, values["functions"], entry)


def test_entry_audit_rejects_atlas_interior_entry(values):
    functions = dict(values["functions"])
    entry = holder._CALLERS[0]
    functions[entry + 1] = functions[entry]
    with pytest.raises(NativeLuaRegistryHolderError, match="alternate modeled interior entry"):
        holder._entry_audit_expected(values["edges"], functions, entry)


def _patch_output_root(monkeypatch, tmp_path: Path) -> None:
    info = tmp_path.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def test_cli_parser_exposes_complete_inputs():
    common = []
    for flag in ("--executable", "--inventory", "--program-facts", "--direct-calls", "--terminal-dispositions"):
        common += [flag, "input.json"]
    assert cli.build_parser().parse_args(["build", *common, "--output", "out.json"]).command == "build"
    assert cli.build_parser().parse_args(["verify", *common, "--evidence", "out.json"]).command == "verify"


@pytest.mark.parametrize("payload", ['{"a": 1, "a": 2}', '{"a": NaN}'])
def test_cli_main_reports_strict_json_errors(tmp_path, capsys, payload):
    malformed = tmp_path / "malformed.json"
    malformed.write_text(payload, encoding="utf-8")
    argv = ["verify"]
    for flag in ("--executable", "--inventory", "--program-facts", "--direct-calls", "--terminal-dispositions", "--evidence"):
        argv += [flag, str(malformed)]
    assert cli.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "Traceback" not in captured.err


def test_cli_main_reports_output_root_rejection(tmp_path, monkeypatch, capsys, values):
    monkeypatch.setattr(cli, "_read_json_object", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        cli,
        "build_native_lua_registry_holder_local_use_release_census",
        lambda *args, **kwargs: values["evidence"],
    )

    def reject_root():
        raise cli.NativeLuaPropertyFactoryChainError("unsafe output root")

    monkeypatch.setattr(cli, "_prepare_output_root", reject_root)
    argv = ["build"]
    for flag in ("--executable", "--inventory", "--program-facts", "--direct-calls", "--terminal-dispositions"):
        argv += [flag, str(tmp_path / "input.json")]
    argv += ["--output", str(tmp_path / "evidence.json")]
    assert cli.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: unsafe output root\n"


def test_cli_writer_is_immutable(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    evidence = values["evidence"]
    rendered = holder.encode_native_lua_registry_holder_local_use_release_census(evidence)
    output = tmp_path / "evidence.json"
    cli._write_immutably(output, rendered, evidence)
    cli._write_immutably(output, rendered, evidence)
    output.write_text(rendered + " ", encoding="utf-8")
    with pytest.raises(NativeLuaRegistryHolderError, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, evidence)


def test_cli_writer_rejects_existing_symlink(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    rendered = holder.encode_native_lua_registry_holder_local_use_release_census(values["evidence"])
    target = tmp_path / "target.json"
    target.write_text(rendered, encoding="utf-8")
    output = tmp_path / "evidence.json"
    try:
        output.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    with pytest.raises(NativeLuaRegistryHolderError, match="linked, reparse, or non-regular"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_cli_writer_rejects_existing_reparse(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    rendered = holder.encode_native_lua_registry_holder_local_use_release_census(values["evidence"])
    output = tmp_path / "evidence.json"
    output.write_text(rendered, encoding="utf-8")
    monkeypatch.setattr(cli, "_is_reparse", lambda _info: True)
    with pytest.raises(NativeLuaRegistryHolderError, match="linked, reparse, or non-regular"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_cli_writer_rejects_existing_nonregular(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    output.mkdir()
    rendered = holder.encode_native_lua_registry_holder_local_use_release_census(values["evidence"])
    with pytest.raises(NativeLuaRegistryHolderError, match="linked, reparse, or non-regular"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_cli_writer_detects_existing_inode_swap(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = holder.encode_native_lua_registry_holder_local_use_release_census(values["evidence"])
    output.write_text(rendered, encoding="utf-8")
    original_reader = cli._read_json_document

    def swapped_reader(path: Path, label: str):
        result = original_reader(path, label)
        path.unlink()
        path.write_text(rendered, encoding="utf-8")
        return result

    monkeypatch.setattr(cli, "_read_json_document", swapped_reader)
    with pytest.raises(NativeLuaRegistryHolderError, match="changed during validation"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_cli_writer_rejects_output_outside_programs(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    outside = tmp_path.parent / "evidence.json"
    rendered = holder.encode_native_lua_registry_holder_local_use_release_census(values["evidence"])
    with pytest.raises(NativeLuaRegistryHolderError, match="direct child"):
        cli._write_immutably(outside, rendered, values["evidence"])


def test_exact_rebuild_if_executable_available(values):
    if not EXE.is_file():
        pytest.skip("exact Windows executable is unavailable")
    receipt = holder.validate_native_lua_registry_holder_local_use_release_census(
        EXE,
        values["evidence"],
        values["inventory"],
        values["facts"],
        values["direct"],
        values["terminal"],
    )
    assert receipt["status"] == "verified"
    assert receipt["evidence_sha256"] == CANONICAL_SHA256
