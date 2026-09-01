"""Focused fail-closed coverage for the opaque ``0x0035848f`` boundary."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import struct
import threading
from pathlib import Path
from typing import Any

import pytest

from scripts import itb_native_operator_new_second_callee_static_boundary as cli
from src.observatory import native_operator_new_second_callee_static_boundary as helper
from src.observatory.native_operator_new_second_callee_static_boundary import (
    NativeOperatorNewSecondCalleeStaticBoundaryError,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
# Locked to the first exact immutable publication.
RAW_SHA256 = "c427f25ed77f605911ddea747fcda26b44814ca0060f0c4fce3bbffcfe717f25"
CANONICAL_SHA256 = "ebc3514d67711d7774e51eecd4c881f9826ed6ec68f40ca462415e654ba7d856"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    paths = {
        "inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"),
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "predecessor": PROGRAMS / (PREFIX + "native_operator_new_static_boundary.json"),
        "evidence": PROGRAMS / (PREFIX + "native_operator_new_second_callee_static_boundary.json"),
    }
    if any(not path.is_file() for path in paths.values()):
        pytest.skip("operator-new second-callee receipt prerequisites are unavailable")
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    return result


def _common(values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return values["predecessor"], values["direct"], values["facts"]


def _structure(values: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return helper.validate_native_operator_new_second_callee_static_boundary_structure(
        values["evidence"] if evidence is None else evidence, *_common(values)
    )


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


def _rejects(values: dict[str, Any], evidence: dict[str, Any]) -> None:
    with pytest.raises(NativeOperatorNewSecondCalleeStaticBoundaryError):
        _structure(values, evidence)


def _exact_executable() -> Path:
    """Return the explicitly opted-in PE path; never probe a live default path."""
    configured = os.environ.get("ITB_EXACT_EXE")
    if not configured:
        pytest.skip("set ITB_EXACT_EXE to run expensive exact PE checks")
    executable = Path(configured)
    if not executable.is_file() or hashlib.sha256(executable.read_bytes()).hexdigest() != EXE_SHA256:
        pytest.skip("ITB_EXACT_EXE is not the sealed Breach.exe build")
    return executable


def test_decoder_seals_raw_body_and_direct_call_range_end_cfg_without_runtime_claims():
    instructions = helper._decode()
    assert b"".join(bytes(item.bytes) for item in instructions).hex() == helper._RAW
    assert [(item.address - helper._BASE, bytes(item.bytes).hex()) for item in instructions] == [
        (0x35848F, "55"), (0x358490, "8bec"), (0x358492, "83ec0c"),
        (0x358495, "8d4df4"), (0x358498, "e8daffffff"),
        (0x35849D, "68d4c98800"), (0x3584A2, "8d45f4"),
        (0x3584A5, "50"), (0x3584A6, "e800890100"),
    ]
    graph = helper._graph(instructions)
    assert (graph["node_count"], graph["edge_count"], helper._canonical_sha256(graph)) == (9, 8, helper._CFG)
    assert graph["nodes"][-1]["flow_kind"] == "direct_call_range_end"
    assert graph["nodes"][-1]["successor_rvas"] == []
    assert graph["nodes"][4]["flow_kind"] == "call_fallthrough"
    assert graph["nodes"][4]["successor_rvas"] == ["0x0035849d"]


def test_committed_encoding_structure_and_summary(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert raw == helper.encode_native_operator_new_second_callee_static_boundary(evidence).encode("utf-8")
    if RAW_SHA256 is not None:
        assert hashlib.sha256(raw).hexdigest() == RAW_SHA256
    if CANONICAL_SHA256 is not None:
        assert helper._canonical_sha256(evidence) == CANONICAL_SHA256
    receipt = _structure(values)
    assert receipt["status"] == "structurally_verified"
    assert evidence["summary"] == {
        "reviewed_target_count": 1, "reviewed_target_bytes": 28,
        "sealed_instruction_count": 9, "sealed_control_flow_graph_count": 1,
        "sealed_control_flow_graph_node_count": 9, "sealed_control_flow_graph_edge_count": 8,
        "native_direct_edge_count": 2, "direct_lua_call_count": 0,
        "staged_lua_dispatch_count": 0, "call_r32_count": 0,
        "opaque_indirect_control_count": 0, "pe_address_operand_count": 3,
        "pe_immediate_operand_count": 3, "pe_absolute_memory_operand_count": 0,
        "segment_qualified_memory_syntax_count": 0,
        "bnd_prefixed_control_syntax_count": 0, "opaque_interrupt_syntax_count": 0,
        "predecessor_parent_edge_count": 1, "target_reference_count": 1,
        "target_reference_target_count": 1, "target_reference_owner_count": 1,
        "target_reference_direct_call_count": 1,
        "target_reference_other_address_count": 0,
        "target_reference_memory_operand_count": 0, "schema_violations": 0,
    }


def test_body_parent_join_outgoing_edges_and_local_pe_operand(values):
    evidence = values["evidence"]
    body = evidence["function_body"]
    assert (body["entry_rva"], body["body_size"], body["body_sha256"], body["atlas_record_sha256"]) == (
        "0x0035848f", 28,
        "cb00213987913afe8e6410bc126b10a6e494f7b6c9e859c727f0ab3f8c7261b6",
        "1db39b499d8261ff48c0bdaac1a9e538601fa4f94cdb25f4b53882e01d325526",
    )
    assert body["ghidra_analysis_metadata"] == {
        "name": "FUN_0075848f", "namespace": "Global", "name_source": "DEFAULT",
        "thunk": False, "metadata_only": True,
    }
    assert body["semantic_facts"] == {
        "relationship_defined_only": True, "analysis_labels_opaque": True,
        "source_semantic_names_assigned": False, "runtime_or_success_claimed": False,
    }
    assert len(evidence["predecessor_parent_edges"]) == 1
    parent = evidence["predecessor_parent_edges"][0]
    assert (parent["source_entry_rva"], parent["instruction"]["rva"], parent["target_entry_rva"]) == (
        "0x003574db", "0x003574f3", "0x0035848f"
    )
    calls = evidence["native_calls"]
    assert [(row["instruction"]["rva"], row["target_entry_rva"]) for row in calls["outgoing_direct"]] == [
        ("0x00358498", "0x00358477"), ("0x003584a6", "0x00370dab"),
    ]
    assert all(row["role"] == "opaque_native_direct_edge" and row["callee_behavior_opaque"] is True for row in calls["outgoing_direct"])
    assert calls["pe_address_operands"] == [
        {
            "role": "opaque_relative_direct_target_immediate_operand",
            "instruction": {"rva": "0x00358498", "size": 5, "sha256": "ca72661446c506165e6afd6d7b02f690454de2ea1e494b0817830aa0569bcbc2"},
                "operand_class": "immediate", "operand_index": 0,
                "operand_access": "none", "control_syntax": "x86_relative_near_call_e8",
            "operand_va": "0x00758477", "operand_rva": "0x00358477",
            "section_name": ".text", "section_rva": "0x00001000",
            "section_characteristics": "0x60000020", "section_writable": False,
            "file_backed": True, "file_offset": "0x00357877",
            "contents_or_runtime_behavior_opaque": True,
        },
        {
            "role": "opaque_relative_direct_target_immediate_operand",
            "instruction": {"rva": "0x003584a6", "size": 5, "sha256": "a2d22e3deed029f7ae75e7abbfa7c6b4f039d737099128f819aea0221696ff42"},
                "operand_class": "immediate", "operand_index": 0,
                "operand_access": "none", "control_syntax": "x86_relative_near_call_e8",
            "operand_va": "0x00770dab", "operand_rva": "0x00370dab",
            "section_name": ".text", "section_rva": "0x00001000",
            "section_characteristics": "0x60000020", "section_writable": False,
            "file_backed": True, "file_offset": "0x003701ab",
            "contents_or_runtime_behavior_opaque": True,
        },
        {
            "role": "opaque_absolute_immediate_operand",
            "instruction": {"rva": "0x0035849d", "size": 5, "sha256": "3caa2e4dd30625a1683fe3686225b277f226178e8be7422c5614296024fb8f01"},
                "operand_class": "immediate", "operand_index": 0,
                "operand_access": "none", "control_syntax": "x86_push_imm32",
            "operand_va": "0x0088c9d4", "operand_rva": "0x0048c9d4",
            "section_name": ".rdata", "section_rva": "0x003d6000",
            "section_characteristics": "0x40000040", "section_writable": False,
            "file_backed": True, "file_offset": "0x0048b9d4",
            "contents_or_runtime_behavior_opaque": True,
        },
    ]
    assert calls["outgoing_direct_partition_complete"] is True
    for key in (
        "direct_lua", "staged_lua", "indirect_control", "pe_address_operand",
        "segment_qualified_memory", "bnd_prefixed_control", "opaque_interrupt",
    ):
        assert calls[key + "_partition_complete"] is True
    assert calls["direct_lua_calls"] == [] and calls["staged_lua_dispatches"] == []
    assert calls["opaque_indirect_controls"] == []
    assert calls["segment_qualified_memory_syntax"] == []
    assert calls["bnd_prefixed_control_syntax"] == []
    assert calls["opaque_interrupt_syntax"] == []
    assert calls["call_r32_audit"] == [{"register": name, "call_rvas": []} for name in helper._REGISTER_NAMES]
    for token in ("source identity", "runtime", "behavior", "indirect", "Lua-side"):
        assert any(token in item for item in evidence["method"]["not_claimed"])


def test_complete_both_operand_class_reference_partition(values):
    scan = values["evidence"]["whole_atlas_reference_scan"]
    assert scan["scope"] == helper._SCOPE
    assert scan["aggregates"] == {
        "reference_count": 1, "target_count": 1, "owner_count": 1,
        "target_owner_count": 1, "direct_call_count": 1,
        "comparison_count": 0, "other_address_count": 0, "memory_operand_count": 0,
    }
    assert scan["references"] == [{
        "instruction_rva": "0x003574f3", "instruction_size": 5,
        "instruction_sha256": "2bd5d9e4d53bd35056ba8d9d19b54df8aa51b7198b09548b0b380583419e8580",
        "owner_entry_rva": "0x003574db",
        "owner_atlas_record_sha256": "605ec81a3c1419f23863f79237b52573167b4dd5d86c86c3bcb958bc46a75eba",
        "target_rva": "0x0035848f",
        "target_atlas_record_sha256": "1db39b499d8261ff48c0bdaac1a9e538601fa4f94cdb25f4b53882e01d325526",
        "target_va": "0x0075848f", "operand_class": "immediate", "operand_index": 0,
        "use_class": "direct_call", "call_form": "x86_relative_near_call_e8",
        "ghidra_declared_direct_edge": {
            "instruction_rva": "0x003574f3", "source_entry_rva": "0x003574db",
            "target_entry_rva": "0x0035848f", "target_rva": "0x0035848f",
            "target_name_sha256": "70e39ce6e5bcd13de941bd12bf11267f9f808202d70cf7ada640e654020329a9",
        },
    }]
    assert scan["owner_partition"] == [{
        "owner_entry_rva": "0x003574db",
        "owner_atlas_record_sha256": "605ec81a3c1419f23863f79237b52573167b4dd5d86c86c3bcb958bc46a75eba",
        "reference_count": 1,
    }]
    assert scan["target_partition"] == [{
        "target_rva": "0x0035848f",
        "target_atlas_record_sha256": "1db39b499d8261ff48c0bdaac1a9e538601fa4f94cdb25f4b53882e01d325526",
        "reference_count": 1, "owner_count": 1,
    }]
    assert scan["partition_sha256"] == helper._PARTITION_HASHES
    for name, value in scan["partition_sha256"].items():
        assert helper._compact(scan[name]) == value


def test_committed_artifact_exact_rebuild_and_verify(values):
    executable = _exact_executable()
    rebuilt = helper.build_native_operator_new_second_callee_static_boundary(
        executable, *_common(values), inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    receipt = helper.validate_native_operator_new_second_callee_static_boundary(
        executable, values["evidence"], *_common(values), inventory=values["inventory"]
    )
    assert receipt["status"] == "verified"
    if CANONICAL_SHA256 is not None:
        assert receipt["evidence_sha256"] == CANONICAL_SHA256


@pytest.mark.parametrize("injected", ["b88f847500", "a18f847500"], ids=["extra-immediate", "extra-absolute-memory"])
def test_all_atlas_scanner_rejects_extra_immediate_or_absolute_memory_target(values, monkeypatch, injected):
    """Prove the unmodified full traversal, then reject each extra operand class."""
    executable = _exact_executable()
    data, image, digest = helper._load_executable(executable)
    assert digest == EXE_SHA256
    baseline_decoder, _ = helper._decoder()
    assert helper._whole_atlas_reference_scan(data, image, baseline_decoder, values["facts"]) == helper._expected_scan(values["facts"])
    actual_decode = helper._decode_range
    import capstone

    def altered(data, image, start, size, decoder):
        result = actual_decode(data, image, start, size, decoder)
        if start == 0x3574DB:
            injected_decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
            injected_decoder.detail = True
            replacement = list(injected_decoder.disasm(bytes.fromhex(injected), image.image_base + 0x3574E3))
            assert len(replacement) == 1 and replacement[0].size == result[4].size
            result[4] = replacement[0]
        return result

    monkeypatch.setattr(helper, "_decode_range", altered)
    altered_decoder, _ = helper._decoder()
    with pytest.raises(NativeOperatorNewSecondCalleeStaticBoundaryError, match="all-operand"):
        helper._whole_atlas_reference_scan(data, image, altered_decoder, values["facts"])


@pytest.mark.parametrize("path", [
    ("schema_version",), ("analysis_kind",), ("build_identity",),
    ("program_facts",), ("predecessor_static_boundary",), ("direct_call_census",),
    ("decoder",), ("function_body",), ("control_flow_graph",),
    ("predecessor_parent_edges",), ("native_calls",),
    ("whole_atlas_reference_scan",), ("method",), ("summary",),
])
def test_structure_rejects_every_retained_top_level_category(values, path):
    cursor: Any = values["evidence"]
    for key in path:
        cursor = cursor[key]
    _rejects(values, _replace(values["evidence"], path, _changed(cursor)))


@pytest.mark.parametrize("path", [
    ("unexpected",), ("function_body", "unexpected"),
    ("function_body", "reviewed_points", 0, "unexpected"),
    ("control_flow_graph", "nodes", 0, "unexpected"),
    ("predecessor_parent_edges", 0, "instruction", "unexpected"),
    ("native_calls", "outgoing_direct", 0, "instruction", "unexpected"),
    ("whole_atlas_reference_scan", "references", 0, "unexpected"),
    ("whole_atlas_reference_scan", "owner_partition", 0, "unexpected"),
    ("method", "unexpected"),
])
def test_structure_rejects_unknown_keys_at_retained_depth(values, path):
    _rejects(values, _add(values["evidence"], path, True))


@pytest.mark.parametrize(("path", "replacement"), [
    (("schema_version",), True),
    (("function_body", "body_size"), True),
    (("function_body", "semantic_facts", "relationship_defined_only"), 1),
    (("control_flow_graph", "node_count"), False),
    (("control_flow_graph", "nodes", 0, "writes_esp"), 1),
    (("native_calls", "pe_address_operands", 0, "file_backed"), 1),
    (("whole_atlas_reference_scan", "references", 0, "instruction_size"), True),
    (("whole_atlas_reference_scan", "owner_partition", 0, "reference_count"), False),
    (("summary", "native_direct_edge_count"), True),
])
def test_structure_rejects_bool_int_substitutions(values, path, replacement):
    _rejects(values, _replace(values["evidence"], path, replacement))


def test_encoder_and_normalization_reject_bad_types_and_wrap_struct_error(monkeypatch):
    with pytest.raises(NativeOperatorNewSecondCalleeStaticBoundaryError):
        helper.encode_native_operator_new_second_callee_static_boundary([])
    with pytest.raises(NativeOperatorNewSecondCalleeStaticBoundaryError):
        helper.encode_native_operator_new_second_callee_static_boundary({"value": float("nan")})
    with pytest.raises(NativeOperatorNewSecondCalleeStaticBoundaryError, match="injected struct failure"):
        helper._normalize(lambda: (_ for _ in ()).throw(struct.error("injected struct failure")))


def _patch_output_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = tmp_path.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def test_cli_parser_exposes_complete_surface():
    parser = cli.build_parser()
    common = []
    for flag in ("--operator-new-static-boundary", "--direct-calls", "--program-facts"):
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
    for flag in (
        "--executable", "--inventory", "--operator-new-static-boundary",
        "--direct-calls", "--program-facts", "--evidence",
    ):
        argv += [flag, str(malformed)]
    assert cli.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("error: ") and "Traceback" not in captured.err


def test_cli_writer_is_immutable(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    evidence, output = values["evidence"], tmp_path / "evidence.json"
    rendered = helper.encode_native_operator_new_second_callee_static_boundary(evidence)
    cli._write_immutably(output, rendered, evidence)
    cli._write_immutably(output, rendered, evidence)
    output.write_text(rendered + " ", encoding="utf-8")
    with pytest.raises(NativeOperatorNewSecondCalleeStaticBoundaryError, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, evidence)


@pytest.mark.parametrize("existing", [True, False])
def test_cli_writer_holds_final_lock_through_validation(tmp_path, monkeypatch, values, existing):
    _patch_output_root(monkeypatch, tmp_path)
    evidence, output = values["evidence"], tmp_path / "evidence.json"
    rendered = helper.encode_native_operator_new_second_callee_static_boundary(evidence)
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


def test_cli_writer_detects_same_inode_mutation_and_preserves_destination(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    evidence, output = values["evidence"], tmp_path / "evidence.json"
    rendered = helper.encode_native_operator_new_second_callee_static_boundary(evidence)
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
    with pytest.raises(NativeOperatorNewSecondCalleeStaticBoundaryError, match="final content validation"):
        cli._write_immutably(output, rendered, evidence)
    assert output.exists()
