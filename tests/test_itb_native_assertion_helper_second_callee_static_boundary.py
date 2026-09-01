"""Exact and adversarial checks for the assertion-helper second callee."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

import pytest

from scripts import itb_native_assertion_helper_second_callee_static_boundary as cli
from src.observatory import native_assertion_helper_second_callee_static_boundary as helper
from src.observatory.native_assertion_helper_second_callee_static_boundary import NativeAssertionHelperSecondCalleeStaticBoundaryError


ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
EXE_SHA256 = helper._EXE
RAW_SHA256 = "d9ae877fc1f9acb604a566470d0b8c2c1bb471701ef19de0e7c0a170e1287a07"
CANONICAL_SHA256 = "ad26b7dddb2996fd69b53937de0ae8bdb6d694982df62c280c4a03430895e0d7"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    paths = {"inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"), "facts": PROGRAMS / (PREFIX + "program_facts.json"),
             "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"), "predecessor": PROGRAMS / (PREFIX + "native_assertion_helper_static_boundary.json"),
             "evidence": PROGRAMS / (PREFIX + "native_assertion_helper_second_callee_static_boundary.json")}
    if any(not path.is_file() for path in paths.values()):
        pytest.skip("assertion-helper second-callee prerequisites are unavailable")
    result = {name: _read(path) for name, path in paths.items()}; result["paths"] = paths
    return result


def _common(values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return values["predecessor"], values["direct"], values["facts"]


def _structure(values: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return helper.validate_native_assertion_helper_second_callee_static_boundary_structure(values["evidence"] if evidence is None else evidence, *_common(values))


def _replace(value: Any, path: tuple[Any, ...], replacement: Any) -> Any:
    if not path:
        return replacement
    clone = dict(value) if isinstance(value, dict) else list(value)
    clone[path[0]] = _replace(value[path[0]], path[1:], replacement)
    return clone


def _fast_structure(monkeypatch: pytest.MonkeyPatch, values: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    target = helper._atlas_functions(values["facts"])[helper._ENTRY]
    monkeypatch.setattr(helper, "_validate_json_tree", lambda *args, **kwargs: None)
    monkeypatch.setattr(helper, "_assert_publication_safe", lambda *args, **kwargs: None)
    monkeypatch.setattr(helper, "validate_native_lua_direct_call_structure", lambda *args, **kwargs: {"status": "structurally_verified", "evidence_sha256": helper._DIRECT})
    monkeypatch.setattr(helper, "_preflight", lambda *args, **kwargs: {"program_facts": copy.deepcopy(values["evidence"]["program_facts"]), "predecessor_static_boundary": copy.deepcopy(values["evidence"]["predecessor_static_boundary"]), "direct_call_census": copy.deepcopy(values["evidence"]["direct_call_census"])})
    monkeypatch.setattr(helper, "_target_function", lambda *args, **kwargs: target)
    monkeypatch.setattr(helper, "_expected_scan", lambda *args, **kwargs: copy.deepcopy(values["evidence"]["whole_atlas_reference_scan"]))
    return _structure(values, evidence)


def _reject(monkeypatch: pytest.MonkeyPatch, values: dict[str, Any], path: tuple[Any, ...], replacement: Any) -> None:
    with pytest.raises(NativeAssertionHelperSecondCalleeStaticBoundaryError):
        _fast_structure(monkeypatch, values, _replace(values["evidence"], path, replacement))


def test_static_contract_constants_are_stable() -> None:
    assert (helper._ENTRY, helper._SIZE, helper._RAW, helper._BODY, helper._ATLAS, helper._CFG) == (0x38C89F, 6, "a118738b00c3", "f664d3656a8c5a2735ac645e41a9bf134e95d47511b55d5466a3384f9d529fec", "bedac224c196ecaac1be86641c5dff897aa6f82a898bb95760259b310f50d207", "56183b6f25df792273808ded5bb52ca03b46561f13c794f0ef9abf7d687cb375")


def test_decode_graph_and_empty_partitions(values: dict[str, Any]) -> None:
    evidence = values["evidence"]; body, graph, calls = evidence["function_body"], evidence["control_flow_graph"], evidence["native_calls"]
    assert (body["entry_rva"], body["body_size"], body["body_sha256"], len(body["reviewed_points"])) == ("0x0038c89f", 6, helper._BODY, 2)
    assert (graph["node_count"], graph["edge_count"], helper._canonical_sha256(graph)) == (2, 1, helper._CFG)
    assert graph["nodes"][-1]["flow_kind"] == "terminal" and graph["nodes"][-1]["successor_rvas"] == []
    assert all(calls[key] == [] for key in ("outgoing_direct", "direct_lua_calls", "staged_lua_dispatches", "opaque_indirect_controls", "non_pe_immediate_literals", "segment_qualified_memory_syntax", "bnd_prefixed_control_syntax", "opaque_interrupt_syntax"))
    assert calls["pe_address_operands"] == [{"role":"opaque_absolute_memory_read_syntax","instruction":helper._instruction(0x38C89F,"a118738b00"),"operand_class":"absolute_memory","operand_index":1,"operand_access":"read","operand_va":"0x008b7318","operand_rva":"0x004b7318","section_name":".data","section_rva":"0x00492000","section_characteristics":"0xc0000040","section_writable":True,"section_virtual_size":"0x000471cc","section_raw_size":"0x00024800","section_raw_offset":"0x00490200","file_backed":False,"file_offset":None,"contents_or_runtime_behavior_opaque":True}]


def test_structure_parent_and_reference_join(values: dict[str, Any]) -> None:
    result = _structure(values); scan = values["evidence"]["whole_atlas_reference_scan"]
    assert result["status"] == "structurally_verified" and result["summary"] == values["evidence"]["summary"]
    assert [(row["instruction_rva"], row["owner_entry_rva"], row["target_rva"]) for row in scan["references"]] == [("0x00379cdc", "0x00379cc2", "0x0038c89f"), ("0x00392d68", "0x00392d32", "0x0038c89f"), ("0x00392f34", "0x00392efb", "0x0038c89f")]
    assert values["evidence"]["predecessor_parent_edges"][0]["instruction"]["rva"] in [row["instruction_rva"] for row in scan["references"]]


def _changed(value: Any) -> Any:
    if isinstance(value, bool): return not value
    if isinstance(value, int): return value + 1
    if isinstance(value, str): return "tampered"
    if value is None: return "tampered"
    if isinstance(value, list): return ["tampered"]
    if isinstance(value, dict): return {"tampered": True}
    raise AssertionError(f"unsupported mutation value {value!r}")


TAMPER_PATHS = [
    ("schema_version",), ("analysis_kind",), ("build_identity", "architecture"), ("program_facts", "canonical_sha256"),
    ("predecessor_static_boundary", "canonical_sha256"), ("direct_call_census", "canonical_sha256"), ("decoder", "name"),
    ("decoder", "register_call_encoding_audit", 0, "encoding"), ("function_body", "role"), ("function_body", "entry_rva"),
    ("function_body", "atlas_record_sha256"), ("function_body", "body_size"), ("function_body", "body_sha256"),
    ("function_body", "range_start_rva"), ("function_body", "control_flow_graph_canonical_sha256"), ("function_body", "reviewed_points", 0, "rva"),
    ("function_body", "reviewed_points", 0, "size"), ("function_body", "reviewed_points", 0, "sha256"), ("function_body", "reviewed_points", 0, "writes_esp"),
    ("function_body", "ghidra_analysis_metadata", "thunk"), ("function_body", "semantic_facts", "analysis_labels_opaque"),
    ("control_flow_graph", "caller_entry_rva"), ("control_flow_graph", "nodes", 0, "successor_rvas"), ("control_flow_graph", "nodes", 1, "flow_kind"),
    ("predecessor_parent_edges", 0, "source_atlas_record_sha256"), ("predecessor_parent_edges", 0, "instruction", "sha256"),
    ("native_calls", "outgoing_direct"), ("native_calls", "outgoing_direct_partition_complete"), ("native_calls", "direct_lua_calls"),
    ("native_calls", "staged_lua_dispatches"), ("native_calls", "opaque_indirect_controls"), ("native_calls", "call_r32_audit", 0, "call_rvas"),
    ("native_calls", "pe_address_operands", 0, "operand_index"), ("native_calls", "pe_address_operands", 0, "operand_rva"),
    ("native_calls", "pe_address_operands", 0, "section_virtual_size"), ("native_calls", "pe_address_operands", 0, "file_backed"),
    ("native_calls", "pe_address_operands", 0, "file_offset"), ("whole_atlas_reference_scan", "references", 1, "owner_entry_rva"),
    ("whole_atlas_reference_scan", "references", 2, "instruction_sha256"), ("whole_atlas_reference_scan", "target_partition", 0, "reference_count"),
    ("whole_atlas_reference_scan", "owner_partition", 0, "reference_count"), ("whole_atlas_reference_scan", "target_owner_partition", 1, "owner_entry_rva"),
    ("whole_atlas_reference_scan", "target_reference_partition", 0, "reference_count"), ("whole_atlas_reference_scan", "partition_sha256", "target_partition"),
    ("whole_atlas_reference_scan", "partition_sha256", "owner_partition"), ("whole_atlas_reference_scan", "references_canonical_sha256"),
    ("whole_atlas_reference_scan", "aggregates", "direct_call_count"), ("method", "not_claimed", 0), ("summary", "target_reference_count"),
]


@pytest.mark.parametrize("path", TAMPER_PATHS)
def test_structure_rejects_every_retained_partition(values: dict[str, Any], path: tuple[Any, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    value: Any = values["evidence"]
    for key in path: value = value[key]
    _reject(monkeypatch, values, path, _changed(value))


@pytest.mark.parametrize("path", [("unexpected",), ("function_body", "unexpected"), ("native_calls", "unexpected"), ("whole_atlas_reference_scan", "references", 0, "unexpected"), ("summary", "unexpected")])
def test_structure_rejects_unknown_keys(values: dict[str, Any], path: tuple[Any, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = copy.deepcopy(values["evidence"]); node: Any = evidence
    for key in path[:-1]: node = node[key]
    node[path[-1]] = "injected"
    with pytest.raises(NativeAssertionHelperSecondCalleeStaticBoundaryError): _fast_structure(monkeypatch, values, evidence)


def test_empty_outgoing_partition_fails_on_injected_edge(values: dict[str, Any]) -> None:
    facts = copy.deepcopy(values["facts"]); facts["ghidra_declared_direct_calls"].append({"instruction_rva":"0x0038c89f","source_entry_rva":"0x0038c89f","target_entry_rva":"0x0038c89f","target_rva":"0x0038c89f","target_name":"injected"})
    with pytest.raises(NativeAssertionHelperSecondCalleeStaticBoundaryError, match="outgoing native"):
        helper._native_calls(facts)


def test_encodes_deterministically_and_rejects_invalid_tree(values: dict[str, Any]) -> None:
    rendered = helper.encode_native_assertion_helper_second_callee_static_boundary(values["evidence"])
    assert rendered.encode() == values["paths"]["evidence"].read_bytes() and hashlib.sha256(rendered.encode()).hexdigest() == RAW_SHA256 and helper._canonical_sha256(values["evidence"]) == CANONICAL_SHA256
    with pytest.raises(NativeAssertionHelperSecondCalleeStaticBoundaryError):
        helper.encode_native_assertion_helper_second_callee_static_boundary({"x": float("nan")})


def _patch_output_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = tmp_path.stat(); monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info)); monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def test_immutable_writer_and_differing_destination(values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_output_root(monkeypatch, tmp_path); output = tmp_path / "evidence.json"; rendered = helper.encode_native_assertion_helper_second_callee_static_boundary(values["evidence"])
    cli._write_immutably(output, rendered, values["evidence"]); cli._write_immutably(output, rendered, values["evidence"])
    output.write_bytes(rendered.encode() + b" ")
    with pytest.raises(NativeAssertionHelperSecondCalleeStaticBoundaryError, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_writer_detects_post_read_race(values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_output_root(monkeypatch, tmp_path); output = tmp_path / "evidence.json"; rendered = helper.encode_native_assertion_helper_second_callee_static_boundary(values["evidence"]); output.write_bytes(rendered.encode())
    original, calls = cli._read_json_document, []
    def mutate(path: Path, label: str):
        result = original(path, label); calls.append(1)
        if len(calls) == 1:
            with path.open("ab") as stream: stream.write(b" ")
        return result
    monkeypatch.setattr(cli, "_read_json_document", mutate)
    with pytest.raises(NativeAssertionHelperSecondCalleeStaticBoundaryError, match="final content validation"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_writer_final_lock_blocks_cooperating_writer(values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_output_root(monkeypatch, tmp_path); output = tmp_path / "evidence.json"; rendered = helper.encode_native_assertion_helper_second_callee_static_boundary(values["evidence"]); output.write_bytes(rendered.encode())
    original, attempts = cli._read_locked_json_document, []
    def contender() -> None:
        try:
            with output.open("ab") as stream: stream.write(b" ")
        except OSError: attempts.append("blocked")
        else: attempts.append("mutated")
    def during(descriptor: int, label: str):
        result = original(descriptor, label); worker = threading.Thread(target=contender); worker.start(); worker.join(5); return result
    monkeypatch.setattr(cli, "_read_locked_json_document", during); cli._write_immutably(output, rendered, values["evidence"])
    assert attempts == ["blocked"]


def test_cli_parser_and_strict_json_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    parsed = cli.build_parser().parse_args(["build", "--assertion-helper-static-boundary", "a.json", "--direct-calls", "b.json", "--program-facts", "c.json", "--inventory", "d.json", "--executable", "Breach.exe"])
    assert parsed.command == "build"
    bad = tmp_path / "bad.json"; bad.write_bytes(b'{"x":NaN}')
    args = ["verify-structure", "--assertion-helper-static-boundary", str(bad), "--direct-calls", str(bad), "--program-facts", str(bad), "--evidence", str(bad)]
    assert cli.main(args) == 1 and capsys.readouterr().err.startswith("error: ")


def _exact_executable() -> Path:
    configured = os.environ.get("ITB_EXACT_EXE")
    if not configured: pytest.skip("set ITB_EXACT_EXE to run expensive exact PE checks")
    path = Path(configured)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != EXE_SHA256:
        pytest.skip("exact installed Breach.exe is unavailable")
    return path


def test_exact_rebuild_verify_cli_and_nonvacuous_scanner(values: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    executable = _exact_executable(); rebuilt = helper.build_native_assertion_helper_second_callee_static_boundary(executable, *_common(values), inventory=values["inventory"])
    assert rebuilt == values["evidence"]
    data, image, _ = helper._load_executable(executable); decoder, _ = helper._decoder(); assert helper._whole_atlas_reference_scan(data, image, decoder, values["facts"]) == helper._expected_scan(values["facts"])
    original = helper._decode_range
    import capstone
    for encoded in ("b89fc87800", "a19fc87800"):
        def altered(data: bytes, image: Any, start: int, size: int, decoder: Any, encoded: str = encoded):
            rows = original(data, image, start, size, decoder)
            if start == 0x379CC2:
                altered_decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); altered_decoder.detail = True; replacement = list(altered_decoder.disasm(bytes.fromhex(encoded), image.image_base + 0x379CCD))
                assert len(replacement) == 1 and replacement[0].size == rows[6].size; rows[6] = replacement[0]
            return rows
        monkeypatch.setattr(helper, "_decode_range", altered); changed, _ = helper._decoder()
        with pytest.raises(NativeAssertionHelperSecondCalleeStaticBoundaryError, match="all-operand"):
            helper._whole_atlas_reference_scan(data, image, changed, values["facts"])
        monkeypatch.setattr(helper, "_decode_range", original)
    receipt = helper.validate_native_assertion_helper_second_callee_static_boundary(executable, values["evidence"], *_common(values), inventory=values["inventory"])
    assert receipt["status"] == "verified"
    p = values["paths"]
    assert cli.main(["verify", "--assertion-helper-static-boundary", str(p["predecessor"]), "--direct-calls", str(p["direct"]), "--program-facts", str(p["facts"]), "--inventory", str(p["inventory"]), "--executable", str(executable), "--evidence", str(p["evidence"])]) == 0
    assert '"status": "verified"' in capsys.readouterr().out
