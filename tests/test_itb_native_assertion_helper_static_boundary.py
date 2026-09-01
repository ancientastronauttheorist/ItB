"""Exact and adversarial tests for native assertion-helper static evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

import pytest

from scripts import itb_native_assertion_helper_static_boundary as cli
from src.observatory import native_assertion_helper_static_boundary as helper
from src.observatory.native_assertion_helper_static_boundary import (
    NativeAssertionHelperStaticBoundaryError,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
# Fill these receipts only after the committed evidence artifact is generated.
RAW_SHA256 = "7fd6879c031ba4e665024789f3cbf9308c49ea3c649ca300b441ada38d9ade5e"
CANONICAL_SHA256 = "beeebb2dadd0ef2a77742f9296760fd09afe5c566c7b46bf36d2dd3cf8e441b4"
CFG_SHA256 = "95575ce84f0cfec966300ed6b457a5b148126f334fede1bc5c4459a895f095ed"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    paths = {
        "inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"),
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "initializer": PROGRAMS / (PREFIX + "native_lua_class_initializer_chain.json"),
        "evidence": PROGRAMS / (PREFIX + "native_assertion_helper_static_boundary.json"),
    }
    if any(not path.is_file() for path in paths.values()):
        pytest.skip("native assertion-helper evidence prerequisites are unavailable")
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    result["target_atlas"] = helper._atlas_functions(result["facts"])[helper._ENTRY]
    return result


def _common(values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return values["initializer"], values["direct"], values["facts"]


def _structure(values: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return helper.validate_native_assertion_helper_static_boundary_structure(
        values["evidence"] if evidence is None else evidence, *_common(values)
    )


def _fast_structure(
    monkeypatch: pytest.MonkeyPatch, values: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    """Exercise the fail-closed joins without rehashing the 25k-function atlas."""
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
        helper, "_expected_reference_scan", lambda *args, **kwargs: copy.deepcopy(values["evidence"]["whole_atlas_reference_scan"])
    )
    monkeypatch.setattr(
        helper, "_native_edges", lambda *args, **kwargs: copy.deepcopy(values["evidence"]["native_edges"])
    )
    return _structure(values, evidence)


def _rejects(values: dict[str, Any], monkeypatch: pytest.MonkeyPatch, evidence: dict[str, Any]) -> None:
    with pytest.raises(NativeAssertionHelperStaticBoundaryError):
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
    """Copy only the tampered path; reference receipts are deliberately large."""
    if not path:
        return replacement
    key = path[0]
    clone = dict(value) if isinstance(value, dict) else list(value)
    clone[key] = _replace(value[key], path[1:], replacement)
    return clone


def _add(value: Any, path: tuple[Any, ...], addition: Any) -> Any:
    """Copy a path and append one otherwise-unrecognized mapping key."""
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


def test_committed_encoding_receipts_structure_and_summary(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert raw == helper.encode_native_assertion_helper_static_boundary(evidence).encode("utf-8")
    if RAW_SHA256 is not None:
        assert hashlib.sha256(raw).hexdigest() == RAW_SHA256
    if CANONICAL_SHA256 is not None:
        assert helper._canonical_sha256(evidence) == CANONICAL_SHA256
    receipt = _structure(values)
    assert receipt["status"] == "structurally_verified"
    assert type(receipt["evidence_sha256"]) is str and len(receipt["evidence_sha256"]) == 64
    assert evidence["summary"] == {
        "reviewed_assertion_helper_count": 1,
        "reviewed_assertion_helper_bytes": 72,
        "sealed_instruction_count": 29,
        "sealed_control_flow_graph_count": 1,
        "sealed_control_flow_graph_node_count": 29,
        "sealed_control_flow_graph_edge_count": 30,
        "direct_lua_call_count": 0,
        "staged_lua_dispatch_count": 0,
        "call_r32_count": 0,
        "literal_count": 0,
        "native_edge_count": 4,
        "initializer_predecessor_window_count": 6,
        "target_reference_count": 881,
        "target_reference_direct_call_count": 881,
        "target_reference_comparison_count": 0,
        "target_reference_other_address_count": 0,
        "target_reference_memory_operand_count": 0,
        "target_reference_owner_count": 660,
        "schema_violations": 0,
    }


def test_committed_artifact_exact_rebuild_and_verification(values):
    if not EXE.is_file() or hashlib.sha256(EXE.read_bytes()).hexdigest() != EXE_SHA256:
        pytest.skip("sealed Breach.exe is unavailable")
    rebuilt = helper.build_native_assertion_helper_static_boundary(
        EXE, *_common(values), inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    receipt = helper.validate_native_assertion_helper_static_boundary(
        EXE, values["evidence"], *_common(values), inventory=values["inventory"]
    )
    assert receipt["status"] == "verified"
    if CANONICAL_SHA256 is not None:
        assert receipt["evidence_sha256"] == CANONICAL_SHA256


def test_static_boundary_facts_nonclaims_and_all_reviewed_instructions(values):
    evidence = values["evidence"]
    body, graph = _body(evidence), _graph(evidence)
    assert (body["entry_rva"], body["body_size"]) == ("0x00379cc2", 72)
    assert [(point["role"], point["rva"]) for point in body["reviewed_points"]] == [
        ("hotpatch_nop", "0x00379cc2"), ("frame_push", "0x00379cc4"),
        ("frame_establish", "0x00379cc5"), ("esi_push", "0x00379cc7"),
        ("stack_relative_load", "0x00379cc8"), ("scalar_three", "0x00379ccb"),
        ("native_edge_one", "0x00379ccd"), ("stack_pop", "0x00379cd2"),
        ("result_one_compare", "0x00379cd3"), ("result_one_branch", "0x00379cd6"),
        ("result_zero_test", "0x00379cd8"), ("result_nonzero_branch", "0x00379cda"),
        ("native_edge_two", "0x00379cdc"), ("result_two_compare", "0x00379ce1"),
        ("result_two_branch", "0x00379ce4"), ("argument_four_push", "0x00379ce6"),
        ("argument_three_push", "0x00379ce7"), ("argument_two_push", "0x00379cea"),
        ("argument_one_push", "0x00379ced"), ("native_edge_three", "0x00379cf0"),
        ("stack_cleanup", "0x00379cf5"), ("esi_pop", "0x00379cf8"),
        ("frame_pop", "0x00379cf9"), ("return", "0x00379cfa"),
        ("alternate_argument_three_push", "0x00379cfb"),
        ("alternate_argument_two_push", "0x00379cfe"),
        ("alternate_argument_one_push", "0x00379d01"),
        ("native_edge_four", "0x00379d04"), ("post_call_trap", "0x00379d09"),
    ]
    assert body["semantic_facts"] == {
        "callee_behavior_opaque": True, "direct_lua_calls_absent": True,
        "staged_lua_dispatches_absent": True, "register_r32_calls_absent": True,
        "int3_after_last_direct_call_does_not_prove_termination": True,
        "source_semantic_names_assigned": False,
    }
    assert (graph["node_count"], graph["edge_count"]) == (29, 30)
    assert body["control_flow_graph_canonical_sha256"] == CFG_SHA256
    assert body["direct_lua_calls"] == []
    assert body["staged_lua_dispatches"] == []
    assert body["call_r32_audit"] == [{"register": register, "call_rvas": []} for register in helper._REGISTER_NAMES]
    assert body["register_call_partition_complete"] is True
    assert evidence.get("literals", []) == []
    assert len(evidence["native_edges"]) == 4
    assert all(edge["role"] == "opaque_native_direct_edge" and edge["callee_behavior_opaque"] is True for edge in evidence["native_edges"])
    assert [edge["target_entry_rva"] for edge in evidence["native_edges"]] == [
        "0x0038e392", "0x0038c89f", "0x00379550", "0x00379b31"
    ]
    assert evidence["method"]["not_claimed"] == [
        "runtime reachability, invocation, order, or frequency", "argument validity",
        "dialog or display behavior", "CRT identity or ownership",
        "normal return, abort, or termination", "source equivalence",
        "computed, indirect, data, un-atlased, or Lua-side references",
    ]
    assert "allocation" not in json.dumps(evidence["method"], sort_keys=True).lower()


def test_initializer_predecessor_join_window_and_reference_owner_partition(values):
    evidence = values["evidence"]
    edge = evidence["initializer_assertion_edge"]
    assert edge["source_entry_rva"] == "0x002eacf0"
    assert edge["target_entry_rva"] == "0x00379cc2"
    window = evidence["initializer_predecessor_window"]
    assert [point["role"] for point in window] == [
        "classes_sentinel_compare", "classes_sentinel_branch", "assertion_line_push",
        "assertion_source_pointer", "assertion_condition_pointer", "registry_classes_assertion",
    ]
    assert window[3]["meaning"] == {"operation": "push_nonwritable_rdata_pointer", "literal_rva": "0x0043c680"}
    assert window[4]["meaning"] == {"operation": "push_nonwritable_rdata_pointer", "literal_rva": "0x0043c6b0"}
    assert window[-1]["meaning"] == {"operation": "direct_call", "target_rva": "0x00379cc2"}
    scan = evidence["whole_atlas_reference_scan"]
    assert scan["scope"] == {
        "atlas_function_count": values["facts"]["summary"]["function_count"],
        "atlas_body_range_count": values["facts"]["summary"]["body_range_count"],
        "decoded_bytes": values["facts"]["summary"]["function_body_bytes"],
        "decoded_instructions": values["direct"]["summary"]["decoded_instructions"],
        "all_declared_ranges_decoded": True,
        "operand_classes": ["absolute_memory", "immediate"],
    }
    assert len(scan["references"]) == 881 and len(scan["owner_partition"]) == 660
    assert all(item["instruction_size"] == 5 and item["operand_index"] == 0 for item in scan["references"])
    assert all(item["use_class"] == "direct_call" and item["call_form"] == "x86_relative_near_call_e8" for item in scan["references"])
    assert scan["aggregates"] == {
        "reference_count": 881, "direct_call_count": 881, "comparison_count": 0,
        "other_address_count": 0, "memory_operand_count": 0, "owner_count": 660,
    }
    assert sum(owner["reference_count"] for owner in scan["owner_partition"]) == 881


@pytest.mark.parametrize("key", [
    "schema_version", "analysis_kind", "build_identity", "atlas", "direct_call_census",
    "class_initializer_chain", "decoder", "initializer_assertion_edge", "initializer_predecessor_window",
    "function_bodies", "control_flow_graphs", "native_edges", "whole_atlas_reference_scan", "method", "summary",
])
def test_structure_rejects_every_retained_top_level_category(values, monkeypatch, key):
    _rejects(values, monkeypatch, _replace(values["evidence"], (key,), _changed(values["evidence"][key])))


@pytest.mark.parametrize("path", [
    ("unexpected",),
    ("function_bodies", 0, "unexpected"),
    ("function_bodies", 0, "reviewed_points", 0, "meaning", "unexpected"),
    ("control_flow_graphs", 0, "nodes", 0, "unexpected"),
    ("native_edges", 0, "instruction", "unexpected"),
    ("whole_atlas_reference_scan", "references", 0, "unexpected"),
    ("whole_atlas_reference_scan", "owner_partition", 0, "unexpected"),
    ("method", "unexpected"),
])
def test_structure_rejects_unknown_keys_at_every_retained_depth(values, monkeypatch, path):
    _rejects(values, monkeypatch, _add(values["evidence"], path, True))


@pytest.mark.parametrize(("path", "replacement"), [
    (("schema_version",), True),
    (("function_bodies", 0, "body_size"), True),
    (("function_bodies", 0, "register_call_partition_complete"), 1),
    (("function_bodies", 0, "reviewed_points", 0, "size"), False),
    (("control_flow_graphs", 0, "node_count"), False),
    (("whole_atlas_reference_scan", "references", 0, "instruction_size"), True),
    (("whole_atlas_reference_scan", "owner_partition", 0, "reference_count"), False),
    (("summary", "native_edge_count"), True),
])
def test_structure_rejects_bool_int_json_substitutions(values, monkeypatch, path, replacement):
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
    source = values["evidence"]
    cursor: Any = source
    for key in path:
        cursor = cursor[key]
    _rejects(values, monkeypatch, _replace(source, path, _changed(cursor)))


@pytest.mark.parametrize("register_index", range(8))
def test_structure_rejects_every_call_r32_audit_encoding(values, monkeypatch, register_index):
    evidence = _replace(
        values["evidence"],
        ("function_bodies", 0, "call_r32_audit", register_index, "call_rvas"),
        ["0x00379cc2"],
    )
    _rejects(values, monkeypatch, evidence)


def test_structure_rejects_call_r32_graph_and_audit_mismatch(values, monkeypatch):
    evidence = _replace(
        values["evidence"],
        ("control_flow_graphs", 0, "nodes", 0, "sha256"),
        hashlib.sha256(b"\xff\xd0").hexdigest(),
    )
    _rejects(values, monkeypatch, evidence)


def test_structure_rejects_class_initializer_prerequisite_pin(values, monkeypatch):
    _rejects(values, monkeypatch, _replace(values["evidence"], ("class_initializer_chain", "canonical_sha256"), "0" * 64))


def _patch_output_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = tmp_path.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def test_cli_parser_exposes_complete_surface():
    parser, common = cli.build_parser(), []
    for flag in ("--class-initializer", "--direct-calls", "--program-facts"):
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
    for flag in ("--executable", "--inventory", "--class-initializer", "--direct-calls", "--program-facts", "--evidence"):
        argv += [flag, str(malformed)]
    assert cli.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("error: ") and "Traceback" not in captured.err


def test_cli_writer_is_immutable(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    evidence, output = values["evidence"], tmp_path / "evidence.json"
    rendered = helper.encode_native_assertion_helper_static_boundary(evidence)
    cli._write_immutably(output, rendered, evidence)
    cli._write_immutably(output, rendered, evidence)
    output.write_text(rendered + " ", encoding="utf-8")
    with pytest.raises(NativeAssertionHelperStaticBoundaryError, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, evidence)


def test_cli_writer_detects_existing_and_created_same_inode_mutation_and_cleans_up(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    evidence, output = values["evidence"], tmp_path / "evidence.json"
    rendered = helper.encode_native_assertion_helper_static_boundary(evidence)
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
    with pytest.raises(NativeAssertionHelperStaticBoundaryError, match="final content validation"):
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
    with pytest.raises(NativeAssertionHelperStaticBoundaryError, match="final content validation"):
        cli._write_immutably(output, rendered, evidence)
    assert not output.exists()


@pytest.mark.parametrize("existing", [True, False])
def test_cli_writer_holds_final_lock_through_validation_and_return(tmp_path, monkeypatch, values, existing):
    _patch_output_root(monkeypatch, tmp_path)
    evidence, output = values["evidence"], tmp_path / "evidence.json"
    rendered = helper.encode_native_assertion_helper_static_boundary(evidence)
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
        contender.start()
        contender.join(timeout=5)
        assert not contender.is_alive()
        return result

    monkeypatch.setattr(cli, "_read_locked_json_document", read_while_contended)
    cli._write_immutably(output, rendered, evidence)
    assert attempts == ["blocked"]
    assert output.read_bytes() == rendered.encode("utf-8")
    with output.open("ab") as stream:
        stream.write(b" ")
    assert output.read_bytes() == rendered.encode("utf-8") + b" "


@pytest.mark.parametrize("kind", ["symlink", "reparse", "directory"])
def test_cli_writer_rejects_nonregular_existing_output(tmp_path, monkeypatch, values, kind):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helper.encode_native_assertion_helper_static_boundary(values["evidence"])
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
    with pytest.raises(NativeAssertionHelperStaticBoundaryError, match="regular-file identity"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_cli_writer_rejects_output_outside_programs(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    rendered = helper.encode_native_assertion_helper_static_boundary(values["evidence"])
    with pytest.raises(NativeAssertionHelperStaticBoundaryError, match="direct child"):
        cli._write_immutably(tmp_path.parent / "evidence.json", rendered, values["evidence"])
