"""Exact and adversarial tests for the native ``operator_new`` boundary.

The Ghidra spelling is an analysis label only.  These tests deliberately make
no allocation, ABI, size, ownership, lifetime, or runtime claim.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

import pytest

from scripts import itb_native_operator_new_static_boundary as cli
from src.observatory import native_operator_new_static_boundary as helper
from src.observatory.native_operator_new_static_boundary import (
    NativeOperatorNewStaticBoundaryError,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
RAW_SHA256 = "08cfc38143f47c4b4f737e4638f82495b5bfd22341626a1ee3d7ea66df2005e9"
CANONICAL_SHA256 = "d0cecf29ab94b05dbe8f75c2c6edd823b83c53ed06f853d4db478a76e046479f"
CFG_SHA256 = "86559777b13d1527d904c9f979cf9ae8e822c26246e9c0cba7261ec6d8250fa4"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    paths = {
        "inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"),
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "self_linked": PROGRAMS / (PREFIX + "native_self_linked_record_helper_chain.json"),
        "evidence": PROGRAMS / (PREFIX + "native_operator_new_static_boundary.json"),
    }
    if any(not path.is_file() for path in paths.values()):
        pytest.skip("native operator-new evidence prerequisites are unavailable")
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    result["target_atlas"] = helper._atlas_functions(result["facts"])[helper._ENTRY]
    return result


def _common(values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return values["self_linked"], values["direct"], values["facts"]


def _structure(values: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return helper.validate_native_operator_new_static_boundary_structure(
        values["evidence"] if evidence is None else evidence, *_common(values)
    )


def _fast_structure(
    monkeypatch: pytest.MonkeyPatch, values: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    """Keep mutation tests PE-free and avoid rehashing the complete atlas."""
    target = values["target_atlas"]
    monkeypatch.setattr(helper, "_validate_json_tree", lambda *args, **kwargs: None)
    monkeypatch.setattr(helper, "_assert_publication_safe", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        helper,
        "validate_native_lua_direct_call_structure",
        lambda *args, **kwargs: {"status": "structurally_verified", "evidence_sha256": helper._DIRECT_SHA256},
    )
    monkeypatch.setattr(helper, "_atlas_functions", lambda *args, **kwargs: {helper._ENTRY: target})
    monkeypatch.setattr(
        helper,
        "_native_edges",
        lambda *args, **kwargs: copy.deepcopy(values["evidence"]["native_edges"]),
    )
    monkeypatch.setattr(
        helper,
        "_expected_reference_scan",
        lambda *args, **kwargs: copy.deepcopy(values["evidence"]["whole_atlas_reference_scan"]),
    )
    return _structure(values, evidence)


def _rejects(values: dict[str, Any], monkeypatch: pytest.MonkeyPatch, evidence: dict[str, Any]) -> None:
    with pytest.raises(NativeOperatorNewStaticBoundaryError):
        _fast_structure(monkeypatch, values, evidence)


def _body(evidence: dict[str, Any]) -> dict[str, Any]:
    assert len(evidence["function_bodies"]) == 1
    return evidence["function_bodies"][0]


def _graph(evidence: dict[str, Any]) -> dict[str, Any]:
    assert len(evidence["control_flow_graphs"]) == 1
    return evidence["control_flow_graphs"][0]


def _changed(value: Any) -> Any:
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


def _replace(value: Any, path: tuple[Any, ...], replacement: Any) -> Any:
    if not path:
        return replacement
    key = path[0]
    clone = dict(value) if isinstance(value, dict) else list(value)
    clone[key] = _replace(value[key], path[1:], replacement)
    return clone


def _add(value: Any, path: tuple[Any, ...], addition: Any) -> Any:
    if len(path) == 1:
        clone = dict(value)
        clone[path[0]] = addition
        return clone
    key = path[0]
    clone = dict(value) if isinstance(value, dict) else list(value)
    clone[key] = _add(value[key], path[1:], addition)
    return clone


def _set_path(value: Any, path: tuple[Any, ...], replacement: Any) -> None:
    cursor = value
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement


def test_committed_encoding_structure_and_summary(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert raw == helper.encode_native_operator_new_static_boundary(evidence).encode("utf-8")
    if RAW_SHA256 is not None:
        assert hashlib.sha256(raw).hexdigest() == RAW_SHA256
    if CANONICAL_SHA256 is not None:
        assert helper._canonical_sha256(evidence) == CANONICAL_SHA256
    receipt = _structure(values)
    assert receipt["status"] == "structurally_verified"
    assert type(receipt["evidence_sha256"]) is str and len(receipt["evidence_sha256"]) == 64
    assert evidence["summary"] == {
        "reviewed_operator_new_count": 1, "reviewed_operator_new_bytes": 51,
        "sealed_instruction_count": 20, "sealed_control_flow_graph_count": 1,
        "sealed_control_flow_graph_node_count": 20, "sealed_control_flow_graph_edge_count": 22,
        "direct_lua_call_count": 0, "staged_lua_dispatch_count": 0,
        "call_r32_count": 0, "literal_count": 0, "native_edge_count": 4,
        "self_linked_predecessor_edge_count": 1,
        "target_reference_count": 1233, "target_reference_direct_call_count": 1232,
        "target_reference_comparison_count": 0, "target_reference_other_address_count": 1,
        "target_reference_memory_operand_count": 0, "target_reference_owner_count": 1050,
        "schema_violations": 0,
    }


def test_committed_artifact_exact_rebuild_and_verification(values):
    if not EXE.is_file() or hashlib.sha256(EXE.read_bytes()).hexdigest() != EXE_SHA256:
        pytest.skip("sealed Breach.exe is unavailable")
    rebuilt = helper.build_native_operator_new_static_boundary(EXE, *_common(values), inventory=values["inventory"])
    assert rebuilt == values["evidence"]
    receipt = helper.validate_native_operator_new_static_boundary(
        EXE, values["evidence"], *_common(values), inventory=values["inventory"]
    )
    assert receipt["status"] == "verified"
    if CANONICAL_SHA256 is not None:
        assert receipt["evidence_sha256"] == CANONICAL_SHA256


def test_all_exact_instructions_cfg_edges_analysis_label_and_nonclaims(values):
    evidence, body, graph = values["evidence"], _body(values["evidence"]), _graph(values["evidence"])
    assert (body["entry_rva"], body["body_size"], body["body_sha256"]) == (
        "0x003574db", 51, "452b4c981b0a2567c6f4fc35b20076deca45a6b3509707358212028d21db5bfa"
    )
    assert [(point["role"], point["rva"]) for point in body["reviewed_points"]] == [
        (f"instruction_{index:02d}", rva) for index, rva in enumerate([
            "0x003574db", "0x003574dc", "0x003574de", "0x003574e0", "0x003574e3",
            "0x003574e8", "0x003574e9", "0x003574eb", "0x003574ed", "0x003574f1",
            "0x003574f3", "0x003574f8", "0x003574fa", "0x003574ff", "0x00357502",
            "0x00357507", "0x00357508", "0x0035750a", "0x0035750c", "0x0035750d",
        ])
    ]
    encoded = [
        "55", "8bec", "eb1f", "ff7508", "e8dc460300", "59", "85c0", "7512", "837d08ff", "7507",
        "e8970f0000", "eb05", "e8bdc0feff", "ff7508", "e84b2a0200", "59", "85c0", "74d4", "5d", "c3",
    ]
    assert [point["size"] for point in body["reviewed_points"]] == [len(bytes.fromhex(item)) for item in encoded]
    assert [point["sha256"] for point in body["reviewed_points"]] == [hashlib.sha256(bytes.fromhex(item)).hexdigest() for item in encoded]
    assert (graph["node_count"], graph["edge_count"]) == (20, 22)
    assert body["control_flow_graph_canonical_sha256"] == CFG_SHA256
    assert body["semantic_facts"] == {
        "analysis_label": "operator_new", "analysis_label_only": True,
        "source_semantic_names_assigned": False, "runtime_or_success_claimed": False,
    }
    assert body["direct_lua_calls"] == [] and body["staged_lua_dispatches"] == []
    assert body["call_r32_audit"] == [{"register": r, "call_rvas": []} for r in helper._REGISTER_NAMES]
    assert body["register_call_partition_complete"] is True and evidence.get("literals", []) == []
    assert [(edge["instruction"]["rva"], edge["target_entry_rva"]) for edge in evidence["native_edges"]] == [
        ("0x003574e3", "0x0038bbc4"), ("0x003574f3", "0x0035848f"),
        ("0x003574fa", "0x003435bc"), ("0x00357502", "0x00379f52"),
    ]
    assert all(edge["role"] == "opaque_native_direct_edge" and edge["callee_behavior_opaque"] is True for edge in evidence["native_edges"])
    predecessor = evidence["self_linked_operator_new_edge"]
    assert predecessor["role"] == "symbol_labeled_native_size_request_edge"
    assert predecessor["source_entry_rva"] == "0x0007c600"
    assert predecessor["instruction"]["rva"] == "0x0007c602"
    assert predecessor["target_entry_rva"] == "0x003574db"
    not_claimed = evidence["method"]["not_claimed"]
    for token in ("allocation", "ABI", "success", "ownership", "lifetime", "size", "source identity", "runtime", "computed", "indirect", "un-atlased", "Lua-side"):
        assert any(token.lower() in item.lower() for item in not_claimed)


def test_full_atlas_reference_partition_and_independent_e8_profile(values):
    scan = values["evidence"]["whole_atlas_reference_scan"]
    refs, owners = scan["references"], scan["owner_partition"]
    assert len(refs) == 1233 and len(owners) == 1050
    assert scan["aggregates"] == {
        "reference_count": 1233, "direct_call_count": 1232, "comparison_count": 0,
        "other_address_count": 1, "memory_operand_count": 0, "owner_count": 1050,
    }
    e8 = [item for item in refs if item["use_class"] == "direct_call"]
    jumps = [item for item in refs if item["use_class"] == "other_address"]
    assert len(e8) == 1232 and len(jumps) == 1
    assert all(item["instruction_size"] == 5 and item["operand_index"] == 0 for item in refs)
    assert all(item["operand_class"] == "immediate" and item["call_form"] == "x86_relative_near_call_e8" for item in e8)
    assert all(item["ghidra_declared_direct_edge"] is not None for item in e8)
    assert jumps[0]["instruction_rva"] == "0x00357874"
    assert jumps[0]["owner_entry_rva"] == "0x00357870"
    assert jumps[0]["instruction_sha256"] == "cdca88990634fb7740f46920a3ff9963c07df60f5ddf4334b345678eb7fbbe51"
    assert jumps[0]["call_form"] is None and jumps[0]["ghidra_declared_direct_edge"] is not None
    assert sum(owner["reference_count"] for owner in owners) == 1233
    # The E8-only shared profile comes independently from program facts; the
    # separately pinned E9 is also present in Ghidra's declared-edge table.
    expected = helper._base_expected_reference_scan(values["facts"], values["direct"], helper._profile(values["facts"]))
    assert e8 == expected["references"]


@pytest.mark.parametrize("key", [
    "schema_version", "analysis_kind", "build_identity", "atlas", "direct_call_census",
    "self_linked_record_helper_chain", "self_linked_operator_new_edge", "decoder", "function_bodies", "control_flow_graphs",
    "native_edges", "whole_atlas_reference_scan", "method", "summary",
])
def test_structure_rejects_every_retained_top_level_category(values, monkeypatch, key):
    _rejects(values, monkeypatch, _replace(values["evidence"], (key,), _changed(values["evidence"][key])))


@pytest.mark.parametrize("path", [
    ("unexpected",), ("function_bodies", 0, "unexpected"),
    ("function_bodies", 0, "reviewed_points", 0, "meaning", "unexpected"),
    ("control_flow_graphs", 0, "nodes", 0, "unexpected"),
    ("native_edges", 0, "instruction", "unexpected"),
    ("self_linked_operator_new_edge", "instruction", "unexpected"),
    ("whole_atlas_reference_scan", "references", 0, "unexpected"),
    ("whole_atlas_reference_scan", "owner_partition", 0, "unexpected"), ("method", "unexpected"),
])
def test_structure_rejects_unknown_keys_at_retained_depths(values, monkeypatch, path):
    _rejects(values, monkeypatch, _add(values["evidence"], path, True))


@pytest.mark.parametrize(("path", "replacement"), [
    (("schema_version",), True), (("function_bodies", 0, "body_size"), True),
    (("function_bodies", 0, "register_call_partition_complete"), 1),
    (("function_bodies", 0, "reviewed_points", 0, "size"), False),
    (("control_flow_graphs", 0, "node_count"), False),
    (("whole_atlas_reference_scan", "references", 0, "instruction_size"), True),
    (("whole_atlas_reference_scan", "owner_partition", 0, "reference_count"), False),
    (("summary", "native_edge_count"), True),
])
def test_structure_rejects_bool_int_substitutions(values, monkeypatch, path, replacement):
    evidence = copy.deepcopy(values["evidence"])
    _set_path(evidence, path, replacement)
    _rejects(values, monkeypatch, evidence)


@pytest.mark.parametrize("path", [
    ("control_flow_graphs", 0, "nodes", 0, "sha256"),
    ("native_edges", 0, "instruction", "sha256"),
    ("whole_atlas_reference_scan", "references", 0, "instruction_sha256"),
    ("whole_atlas_reference_scan", "references", 0, "owner_atlas_record_sha256"),
    ("whole_atlas_reference_scan", "owner_partition", 0, "owner_atlas_record_sha256"),
])
def test_structure_rejects_cfg_edge_reference_owner_and_digest_tamper(values, monkeypatch, path):
    cursor: Any = values["evidence"]
    for key in path:
        cursor = cursor[key]
    _rejects(values, monkeypatch, _replace(values["evidence"], path, _changed(cursor)))


def test_structure_rejects_missing_reference_owner_without_leaking_key_error(values, monkeypatch):
    evidence = copy.deepcopy(values["evidence"])
    del evidence["whole_atlas_reference_scan"]["references"][0]["owner_entry_rva"]
    _rejects(values, monkeypatch, evidence)


@pytest.mark.parametrize("replacement", [None, False, [], {}])
def test_structure_rejects_wrong_type_reference_owner_without_leaking_type_error(values, monkeypatch, replacement):
    evidence = _replace(
        values["evidence"],
        ("whole_atlas_reference_scan", "references", 0, "owner_entry_rva"),
        replacement,
    )
    _rejects(values, monkeypatch, evidence)


@pytest.mark.parametrize("register_index", range(8))
def test_structure_rejects_every_call_r32_audit_encoding(values, monkeypatch, register_index):
    evidence = _replace(values["evidence"], ("function_bodies", 0, "call_r32_audit", register_index, "call_rvas"), ["0x003574db"])
    _rejects(values, monkeypatch, evidence)


def test_structure_rejects_self_linked_prerequisite_pin(values, monkeypatch):
    _rejects(values, monkeypatch, _replace(values["evidence"], ("self_linked_record_helper_chain", "canonical_sha256"), "0" * 64))


def _patch_output_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = tmp_path.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def test_cli_parser_exposes_complete_surface():
    parser, common = cli.build_parser(), []
    for flag in ("--self-linked-record-helper-chain", "--direct-calls", "--program-facts"):
        common += [flag, "input.json"]
    execution = ["--executable", "Breach.exe", "--inventory", "inventory.json"]
    assert parser.parse_args(["build", *common, *execution, "--output", "out.json"]).command == "build"
    assert parser.parse_args(["verify", *common, *execution, "--evidence", "out.json"]).command == "verify"
    assert parser.parse_args(["verify-structure", *common, "--evidence", "out.json"]).command == "verify-structure"


@pytest.mark.parametrize("payload", ['{"a": 1, "a": 2}', '{"a": NaN}'])
def test_cli_main_reports_strict_json_errors(tmp_path, capsys, payload):
    malformed = tmp_path / "malformed.json"
    malformed.write_text(payload, encoding="utf-8")
    argv = ["verify"]
    for flag in ("--executable", "--inventory", "--self-linked-record-helper-chain", "--direct-calls", "--program-facts", "--evidence"):
        argv += [flag, str(malformed)]
    assert cli.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("error: ") and "Traceback" not in captured.err


def test_cli_writer_is_immutable(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    evidence, output = values["evidence"], tmp_path / "evidence.json"
    rendered = helper.encode_native_operator_new_static_boundary(evidence)
    cli._write_immutably(output, rendered, evidence)
    cli._write_immutably(output, rendered, evidence)
    output.write_text(rendered + " ", encoding="utf-8")
    with pytest.raises(NativeOperatorNewStaticBoundaryError, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, evidence)


@pytest.mark.parametrize("existing", [True, False])
def test_cli_writer_holds_final_lock_through_validation_and_return(tmp_path, monkeypatch, values, existing):
    """The lock promises point-in-time integrity against cooperating writers."""
    _patch_output_root(monkeypatch, tmp_path)
    evidence, output = values["evidence"], tmp_path / "evidence.json"
    rendered = helper.encode_native_operator_new_static_boundary(evidence)
    if existing:
        output.write_text(rendered, encoding="utf-8", newline="\n")
    original_reader, attempts = cli._read_locked_json_document, []

    def cooperating_writer() -> None:
        if os.name == "nt":
            try:
                with output.open("ab") as stream:
                    stream.write(b" ")
            except OSError:
                attempts.append("blocked")
            else:
                attempts.append("mutated")
            return
        import fcntl

        descriptor = os.open(output, os.O_WRONLY | os.O_APPEND)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                attempts.append("blocked")
            else:
                os.write(descriptor, b" ")
                attempts.append("mutated")
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    def read_while_contended(descriptor: int, label: str):
        result = original_reader(descriptor, label)
        contender = threading.Thread(target=cooperating_writer)
        contender.start(); contender.join(timeout=5)
        assert not contender.is_alive()
        return result

    monkeypatch.setattr(cli, "_read_locked_json_document", read_while_contended)
    cli._write_immutably(output, rendered, evidence)
    assert attempts == ["blocked"]
    assert output.read_bytes() == rendered.encode("utf-8")


def test_cli_writer_detects_same_inode_mutation_and_preserves_published_path(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    evidence, output = values["evidence"], tmp_path / "evidence.json"
    rendered = helper.encode_native_operator_new_static_boundary(evidence)
    output.write_text(rendered, encoding="utf-8", newline="\n")
    original_reader, calls = cli._read_json_document, 0

    def mutate_existing(path: Path, label: str):
        nonlocal calls
        result = original_reader(path, label)
        calls += 1
        if calls == 1:
            with path.open("ab") as stream:
                stream.write(b" ")
        return result

    monkeypatch.setattr(cli, "_read_json_document", mutate_existing)
    with pytest.raises(NativeOperatorNewStaticBoundaryError, match="final content validation"):
        cli._write_immutably(output, rendered, evidence)
    assert output.exists()
    output.unlink()
    original_link = cli.os.link

    def mutate_created(source: Path, destination: Path) -> None:
        original_link(source, destination)
        with Path(destination).open("ab") as stream:
            stream.write(b" ")

    monkeypatch.setattr(cli, "_read_json_document", original_reader)
    monkeypatch.setattr(cli.os, "link", mutate_created)
    with pytest.raises(NativeOperatorNewStaticBoundaryError, match="final content validation"):
        cli._write_immutably(output, rendered, evidence)
    assert output.exists()


@pytest.mark.parametrize("kind", ["symlink", "reparse", "directory"])
def test_cli_writer_rejects_nonregular_existing_output(tmp_path, monkeypatch, values, kind):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helper.encode_native_operator_new_static_boundary(values["evidence"])
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
    with pytest.raises(NativeOperatorNewStaticBoundaryError, match="regular-file identity"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_cli_writer_rejects_output_outside_programs(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    rendered = helper.encode_native_operator_new_static_boundary(values["evidence"])
    with pytest.raises(NativeOperatorNewStaticBoundaryError, match="direct child"):
        cli._write_immutably(tmp_path.parent / "evidence.json", rendered, values["evidence"])
