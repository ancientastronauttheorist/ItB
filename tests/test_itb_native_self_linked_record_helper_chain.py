"""Exact and adversarial tests for self-linked native helper evidence."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import itb_native_self_linked_record_helper_chain as cli
from src.observatory import native_self_linked_record_helper_chain as helper
from src.observatory.native_self_linked_record_helper_chain import (
    NativeSelfLinkedRecordHelperChainError,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
RAW_SHA256 = "50786d8c2b84702c3d0c246c90ee715afa7c7ef544ddf3fc8afb66e487a01d3c"
CANONICAL_SHA256 = "994b4af188a8017d0dce172a53a9598b9cdf7a48d2faef1fbcbfa5ffcbbf2ddb"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    paths = {
        "inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"),
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "initializer": PROGRAMS / (PREFIX + "native_lua_class_initializer_chain.json"),
        "evidence": PROGRAMS / (PREFIX + "native_self_linked_record_helper_chain.json"),
    }
    if any(not path.is_file() for path in paths.values()):
        pytest.skip("self-linked-record helper evidence prerequisites are unavailable")
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    return result


def _common(values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return values["initializer"], values["direct"], values["facts"]


def _structure(values: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return helper.validate_native_self_linked_record_helper_chain_structure(
        values["evidence"] if evidence is None else evidence, *_common(values)
    )


def _fast_structure(monkeypatch: pytest.MonkeyPatch, values: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    atlas = helper._atlas_functions(values["facts"])
    monkeypatch.setattr(helper, "_validate_json_tree", lambda *args, **kwargs: None)
    monkeypatch.setattr(helper, "_assert_publication_safe", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        helper,
        "validate_native_lua_direct_call_structure",
        lambda *args, **kwargs: {"status": "structurally_verified", "evidence_sha256": helper._DIRECT_SHA256},
    )
    monkeypatch.setattr(
        helper,
        "_expected_reference_scan",
        lambda *args, **kwargs: copy.deepcopy(values["evidence"]["whole_atlas_reference_scan"]),
    )
    monkeypatch.setattr(helper, "_native_edges", lambda *args, **kwargs: copy.deepcopy(values["evidence"]["native_edges"]))
    monkeypatch.setattr(helper, "_expected_caller_grammar", lambda *args, **kwargs: copy.deepcopy(values["evidence"]["caller_grammar_witnesses"]))
    monkeypatch.setattr(helper, "_atlas_functions", lambda *args, **kwargs: atlas)
    return _structure(values, evidence)


def _rejects(values: dict[str, Any], monkeypatch: pytest.MonkeyPatch, evidence: dict[str, Any]) -> None:
    with pytest.raises(NativeSelfLinkedRecordHelperChainError):
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


def _set_path(value: Any, path: tuple[Any, ...], replacement: Any) -> None:
    cursor = value
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement


def _at_path(value: Any, path: tuple[Any, ...]) -> Any:
    for key in path:
        value = value[key]
    return value


def _replace(value: Any, path: tuple[Any, ...], replacement: Any) -> Any:
    """Copy only the path being tampered with; the atlas receipt is large."""
    if not path:
        return replacement
    key = path[0]
    clone = dict(value) if isinstance(value, dict) else list(value)
    clone[key] = _replace(value[key], path[1:], replacement)
    return clone


def _leaf_paths(value: Any, prefix: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    if isinstance(value, dict):
        return [path for key, child in value.items() for path in _leaf_paths(child, (*prefix, key))]
    if isinstance(value, list):
        return [prefix] if not value else [path for index, child in enumerate(value) for path in _leaf_paths(child, (*prefix, index))]
    return [prefix]


def _accept_mutated_cfg_identity(monkeypatch: pytest.MonkeyPatch, evidence: dict[str, Any]) -> None:
    graph = _graph(evidence)
    digest = helper._canonical_sha256(graph)
    _body(evidence)["control_flow_graph_canonical_sha256"] = digest
    function = copy.deepcopy(helper._FUNCTION)
    function["cfg_canonical_sha256"] = digest
    profile = copy.deepcopy(helper._PROFILE)
    profile["functions"] = [function]
    monkeypatch.setattr(helper, "_FUNCTION", function)
    monkeypatch.setattr(helper, "_PROFILE", profile)


def test_committed_artifact_encoding_structure_and_summary(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert raw == helper.encode_native_self_linked_record_helper_chain(evidence).encode("utf-8")
    if RAW_SHA256 is not None:
        assert hashlib.sha256(raw).hexdigest() == RAW_SHA256
    if CANONICAL_SHA256 is not None:
        assert helper._canonical_sha256(evidence) == CANONICAL_SHA256
    receipt = _structure(values)
    assert receipt["status"] == "structurally_verified"
    assert type(receipt["evidence_sha256"]) is str
    assert len(receipt["evidence_sha256"]) == 64
    assert evidence["summary"] == {
        "reviewed_helper_count": 1, "reviewed_helper_bytes": 41,
        "sealed_control_flow_graph_count": 1,
        "sealed_control_flow_graph_node_count": 16,
        "sealed_control_flow_graph_edge_count": 18,
        "direct_lua_call_count": 0, "staged_lua_dispatch_count": 0,
        "staged_lua_call_count": 0, "total_lua_call_count": 0,
        "call_r32_count": 0, "literal_count": 0,
        "selected_native_edge_count": 1, "unique_native_edge_target_count": 1,
        "helper_target_count": 1, "class_initializer_opaque_edge_count": 1,
        "caller_grammar_witness_count": 9, "caller_grammar_zero_pair_count": 9,
        "caller_grammar_return_store_count": 9,
        "target_reference_count": 9, "target_reference_direct_call_count": 9,
        "target_reference_comparison_count": 0,
        "target_reference_other_address_count": 0,
        "target_reference_memory_operand_count": 0,
        "target_reference_owner_count": 9, "schema_violations": 0,
    }


def test_committed_artifact_exact_rebuild_and_verification(values):
    if not EXE.is_file() or hashlib.sha256(EXE.read_bytes()).hexdigest() != EXE_SHA256:
        pytest.skip("sealed Breach.exe is unavailable")
    rebuilt = helper.build_native_self_linked_record_helper_chain(
        EXE, *_common(values), inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    receipt = helper.validate_native_self_linked_record_helper_chain(
        EXE, values["evidence"], *_common(values), inventory=values["inventory"]
    )
    assert receipt["status"] == "verified"
    if CANONICAL_SHA256 is not None:
        assert receipt["evidence_sha256"] == CANONICAL_SHA256


def test_offset_only_semantics_nonclaims_references_and_caller_windows(values):
    evidence = values["evidence"]
    body = _body(evidence)
    assert body["entry_rva"] == "0x0007c600"
    assert body["body_size"] == 41
    assert body["direct_lua_calls"] == []
    assert body["staged_lua_dispatches"] == []
    assert body["call_r32_audit"] == [{"register": register, "call_rvas": []} for register in helper._REGISTER_NAMES]
    facts = body["semantic_facts"]
    assert facts == {
        "requested_size_bytes": 24,
        "conditional_store_guards": ["EAX", "EAX_plus_4", "EAX_plus_8"],
        "stores": {"0x0": "EAX", "0x4": "EAX", "0x8": "EAX", "0xc": "0x0101_word"},
        "return_register": "EAX", "source_semantic_names_assigned": False,
        "runtime_or_success_claimed": False,
    }
    assert facts["conditional_store_guards"][1:] == ["EAX_plus_4", "EAX_plus_8"]
    assert evidence["literals"] == []
    edge = evidence["native_edges"]
    assert len(edge) == 1
    assert edge[0]["source_entry_rva"] == "0x0007c600"
    assert edge[0]["target_entry_rva"] == "0x003574db"
    assert len(evidence["helper_targets"]) == 1
    assert len(evidence["initializer_opaque_edge"]) == 1
    scan = evidence["whole_atlas_reference_scan"]
    assert scan["aggregates"] == {
        "reference_count": 9, "direct_call_count": 9, "comparison_count": 0,
        "other_address_count": 0, "memory_operand_count": 0, "owner_count": 9,
    }
    assert len(scan["references"]) == 9
    assert all(item["use_class"] == "direct_call" for item in scan["references"])
    witnesses = evidence["caller_grammar_witnesses"]
    assert len(witnesses) == 9
    for witness in witnesses:
        assert witness["zero_pair_and_call_are_contiguous_decoded_instructions"] is True
        assert witness["caller_body_or_cfg_sealed"] is False
        assert witness["zero_offset_0"]["meaning"]["relative_offset"] == 0
        assert witness["zero_offset_4"]["meaning"]["relative_offset"] == 4
        assert witness["helper_call"]["meaning"]["target_rva"] == "0x0007c600"
        assert witness["return_to_offset_0"]["meaning"] == {
            "operation": "store_memory", "relative_offset": 0, "source": "EAX"
        }
    not_claimed = evidence["method"]["not_claimed"]
    assert any("allocation success" in item for item in not_claimed)
    assert any("tree, container" in item for item in not_claimed)
    assert any("symbol-labeled native callee" in item for item in not_claimed)
    assert any("computed, indirect" in item for item in not_claimed)


@pytest.mark.parametrize(
    "key",
    [
        "schema_version", "analysis_kind", "build_identity", "atlas",
        "direct_call_census", "class_initializer_chain", "decoder",
        "initializer_opaque_edge", "helper_targets", "literals", "function_bodies",
        "control_flow_graphs", "native_edges", "caller_grammar_witnesses",
        "whole_atlas_reference_scan", "method", "summary",
    ],
)
def test_structure_rejects_every_retained_top_level_category(values, monkeypatch, key):
    evidence = _replace(values["evidence"], (key,), _changed(values["evidence"][key]))
    _rejects(values, monkeypatch, evidence)


def test_structure_rejects_unknown_top_level_and_nested_keys(values, monkeypatch):
    for path in [
        ("unexpected",), ("function_bodies", 0, "semantic_facts", "unexpected"),
        ("method", "unexpected"), ("caller_grammar_witnesses", 0, "unexpected"),
        ("caller_grammar_witnesses", 0, "helper_call", "meaning", "unexpected"),
    ]:
        evidence = _replace(values["evidence"], path, True)
        _rejects(values, monkeypatch, evidence)


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("schema_version",), True),
        (("function_bodies", 0, "semantic_facts", "runtime_or_success_claimed"), 0),
        (("caller_grammar_witnesses", 0, "zero_pair_and_call_are_contiguous_decoded_instructions"), 1),
        (("caller_grammar_witnesses", 0, "zero_offset_0", "meaning", "relative_offset"), False),
        (("whole_atlas_reference_scan", "references", 0, "operand_index"), False),
        (("summary", "reviewed_helper_count"), True),
        (("summary", "direct_lua_call_count"), False),
    ],
)
def test_structure_rejects_bool_int_substitutions(values, monkeypatch, path, replacement):
    evidence = copy.deepcopy(values["evidence"])
    _set_path(evidence, path, replacement)
    _rejects(values, monkeypatch, evidence)


def test_structure_rejects_every_semantic_fact_and_reviewed_point_meaning(values, monkeypatch):
    evidence_source = values["evidence"]
    for field, value in _body(evidence_source)["semantic_facts"].items():
        evidence = _replace(evidence_source, ("function_bodies", 0, "semantic_facts", field), _changed(value))
        _rejects(values, monkeypatch, evidence)
    for index, point in enumerate(_body(evidence_source)["reviewed_points"]):
        for field, value in point.items():
            if field == "meaning":
                continue
            evidence = _replace(evidence_source, ("function_bodies", 0, "reviewed_points", index, field), _changed(value))
            _rejects(values, monkeypatch, evidence)
        for field, value in point["meaning"].items():
            evidence = _replace(evidence_source, ("function_bodies", 0, "reviewed_points", index, "meaning", field), _changed(value))
            _rejects(values, monkeypatch, evidence)


def test_structure_rejects_graph_native_edge_reference_scope_and_aggregates(values, monkeypatch):
    source = values["evidence"]
    groups = [
        (("control_flow_graphs", 0), _graph(source)),
        (("native_edges",), source["native_edges"]),
        (("whole_atlas_reference_scan", "scope"), source["whole_atlas_reference_scan"]["scope"]),
        (("whole_atlas_reference_scan", "aggregates"), source["whole_atlas_reference_scan"]["aggregates"]),
    ]
    for prefix, target in groups:
        for path in _leaf_paths(target):
            full_path = (*prefix, *path)
            evidence = _replace(source, full_path, _changed(_at_path(source, full_path)))
            _rejects(values, monkeypatch, evidence)
    for index, reference in enumerate(source["whole_atlas_reference_scan"]["references"]):
        for field, value in reference.items():
            evidence = _replace(source, ("whole_atlas_reference_scan", "references", index, field), _changed(value))
            _rejects(values, monkeypatch, evidence)


@pytest.mark.parametrize("register_index", range(8))
def test_structure_rejects_ungrouped_call_r32_for_each_encoding(values, monkeypatch, register_index):
    evidence = dict(values["evidence"])
    evidence["control_flow_graphs"] = copy.deepcopy(values["evidence"]["control_flow_graphs"])
    evidence["function_bodies"] = copy.deepcopy(values["evidence"]["function_bodies"])
    node = next(item for item in _graph(evidence)["nodes"] if item["rva"] == "0x0007c600")
    node["sha256"] = hashlib.sha256(bytes((0xFF, 0xD0 + register_index))).hexdigest()
    _accept_mutated_cfg_identity(monkeypatch, evidence)
    _rejects(values, monkeypatch, evidence)


def test_structure_rejects_each_caller_window_instruction_and_metadata(values, monkeypatch):
    source = values["evidence"]
    for index, witness in enumerate(source["caller_grammar_witnesses"]):
        for field, value in witness.items():
            if isinstance(value, dict):
                for path in _leaf_paths(value):
                    full_path = ("caller_grammar_witnesses", index, field, *path)
                    evidence = _replace(source, full_path, _changed(_at_path(source, full_path)))
                    _rejects(values, monkeypatch, evidence)
            else:
                evidence = _replace(source, ("caller_grammar_witnesses", index, field), _changed(value))
                _rejects(values, monkeypatch, evidence)


def test_structure_rejects_class_initializer_prerequisite_pin(values, monkeypatch):
    evidence = _replace(values["evidence"], ("class_initializer_chain", "canonical_sha256"), "0" * 64)
    _rejects(values, monkeypatch, evidence)


@pytest.mark.parametrize(
    "path",
    [
        ("method", "accepted_chain"),
        ("method", "not_claimed", 0),
        ("summary", "reviewed_helper_count"),
        ("summary", "caller_grammar_witness_count"),
    ],
)
def test_structure_rejects_method_and_summary_leaf_tamper(values, monkeypatch, path):
    evidence = _replace(values["evidence"], path, _changed(_at_path(values["evidence"], path)))
    _rejects(values, monkeypatch, evidence)


def _patch_output_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = tmp_path.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def test_cli_parser_exposes_complete_surface():
    common: list[str] = []
    for flag in ("--class-initializer", "--direct-calls", "--program-facts"):
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
    for flag in ("--executable", "--inventory", "--class-initializer", "--direct-calls", "--program-facts", "--evidence"):
        argv += [flag, str(malformed)]
    assert cli.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "Traceback" not in captured.err


def test_cli_writer_is_immutable(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    evidence = values["evidence"]
    rendered = helper.encode_native_self_linked_record_helper_chain(evidence)
    output = tmp_path / "evidence.json"
    cli._write_immutably(output, rendered, evidence)
    cli._write_immutably(output, rendered, evidence)
    output.write_text(rendered + " ", encoding="utf-8")
    with pytest.raises(NativeSelfLinkedRecordHelperChainError, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, evidence)


@pytest.mark.parametrize("kind", ["symlink", "reparse", "directory"])
def test_cli_writer_rejects_nonregular_existing_output(tmp_path, monkeypatch, values, kind):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helper.encode_native_self_linked_record_helper_chain(values["evidence"])
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
    with pytest.raises(NativeSelfLinkedRecordHelperChainError, match="linked, reparse, or non-regular"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_cli_writer_detects_existing_inode_swap(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helper.encode_native_self_linked_record_helper_chain(values["evidence"])
    output.write_text(rendered, encoding="utf-8")
    original_reader = cli._read_json_document

    def swapped_reader(path: Path, label: str):
        result = original_reader(path, label)
        path.unlink()
        path.write_text(rendered, encoding="utf-8")
        return result

    monkeypatch.setattr(cli, "_read_json_document", swapped_reader)
    with pytest.raises(NativeSelfLinkedRecordHelperChainError, match="changed during validation"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_cli_writer_detects_existing_same_inode_content_mutation(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helper.encode_native_self_linked_record_helper_chain(values["evidence"])
    output.write_text(rendered, encoding="utf-8", newline="\n")
    original_reader = cli._read_json_document
    call_count = 0

    def mutated_reader(path: Path, label: str):
        nonlocal call_count
        result = original_reader(path, label)
        call_count += 1
        if call_count == 1:
            with path.open("ab") as stream:
                stream.write(b" ")
        return result

    monkeypatch.setattr(cli, "_read_json_document", mutated_reader)
    with pytest.raises(NativeSelfLinkedRecordHelperChainError, match="final content validation"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_cli_writer_detects_created_same_inode_content_mutation(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helper.encode_native_self_linked_record_helper_chain(values["evidence"])
    original_link = cli.os.link

    def mutated_link(source: Path, destination: Path) -> None:
        original_link(source, destination)
        with Path(destination).open("ab") as stream:
            stream.write(b" ")

    monkeypatch.setattr(cli.os, "link", mutated_link)
    with pytest.raises(NativeSelfLinkedRecordHelperChainError, match="final content validation"):
        cli._write_immutably(output, rendered, values["evidence"])
    assert not output.exists()


def test_cli_writer_rejects_output_outside_programs(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    rendered = helper.encode_native_self_linked_record_helper_chain(values["evidence"])
    with pytest.raises(NativeSelfLinkedRecordHelperChainError, match="direct child"):
        cli._write_immutably(tmp_path.parent / "evidence.json", rendered, values["evidence"])


@pytest.mark.parametrize("failure_site", ["prepare", "recheck"])
def test_cli_main_reports_output_root_failures(tmp_path, monkeypatch, capsys, values, failure_site):
    output = tmp_path / "evidence.json"
    argv = [
        "build", "--executable", str(EXE), "--inventory", str(values["paths"]["inventory"]),
        "--class-initializer", str(values["paths"]["initializer"]),
        "--direct-calls", str(values["paths"]["direct"]),
        "--program-facts", str(values["paths"]["facts"]), "--output", str(output),
    ]
    monkeypatch.setattr(cli, "build_native_self_linked_record_helper_chain", lambda *args, **kwargs: values["evidence"])
    if failure_site == "prepare":
        monkeypatch.setattr(cli, "_prepare_output_root", lambda: (_ for _ in ()).throw(cli.NativeLuaPropertyFactoryChainError("unsafe output root")))
    else:
        info = tmp_path.stat()
        monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
        monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: (_ for _ in ()).throw(cli.NativeLuaPropertyFactoryChainError("changed output root")))
    assert cli.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "Traceback" not in captured.err
