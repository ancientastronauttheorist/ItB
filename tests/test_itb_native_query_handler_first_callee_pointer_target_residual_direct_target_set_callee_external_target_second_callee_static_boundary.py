"""Regression coverage for the 0x00357b42 external-target sibling receipt."""
from __future__ import annotations

import hashlib
import json
import os
import struct
import threading
from pathlib import Path
from types import SimpleNamespace

import capstone.x86_const as x86
import pytest

from scripts import (
    itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary as cli,
)
from src.observatory import (
    native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary as target,
)
from src.observatory.native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary import (
    NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetSecondCalleeStaticBoundaryError,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
PREFIX = "windows_build_13725832_31fe35265598_"
NAME = (
    "native_query_handler_first_callee_pointer_target_residual_direct_target_set_"
    "callee_external_target_second_callee_static_boundary"
)
RAW = "5ccb1830fe36c58579b35089c68b84f0eb34bd5303eab72c09d4ed6b8b3096d2"
CANONICAL = "f82310c91d26d3580458decdd70450c130f965ea53134cf0a383b7f9e5ea56d4"
CFG = "b3d334286def4ca119c59b70f91b17aa46c35b9737edf5088bf755b3f43e0b39"


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values():
    paths = {
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "inventory": ROOT / "data" / "observatory" / "inventories" / "windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json",
        "predecessor": PROGRAMS
        / (
            PREFIX
            + "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary.json"
        ),
        "evidence": PROGRAMS / (PREFIX + NAME + ".json"),
    }
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    return result


def _common(values):
    return values["predecessor"], values["direct"], values["facts"]


def _structure(values, evidence=None):
    return target.validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary_structure(
        values["evidence"] if evidence is None else evidence, *_common(values)
    )


def _at(value, path):
    for key in path:
        value = value[key]
    return value


def _replace(value, path, replacement):
    if not path:
        return replacement
    result = dict(value) if isinstance(value, dict) else list(value)
    result[path[0]] = _replace(value[path[0]], path[1:], replacement)
    return result


def _add(value, path, addition):
    if not path:
        return {**value, "unexpected": addition}
    result = dict(value) if isinstance(value, dict) else list(value)
    result[path[0]] = _add(value[path[0]], path[1:], addition)
    return result


def _changed(value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        return "changed"
    if value is None:
        return "changed"
    if isinstance(value, list):
        return list(value) + [True]
    if isinstance(value, dict):
        return {**value, "changed": True}
    raise AssertionError(type(value))


def _fast(monkeypatch, values, evidence):
    monkeypatch.setattr(target, "_validate_json_tree", lambda *args: None)
    monkeypatch.setattr(target, "_evidence", lambda *args, **kwargs: values["evidence"])
    return _structure(values, evidence)


def _reject(monkeypatch, values, evidence):
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetSecondCalleeStaticBoundaryError
    ):
        _fast(monkeypatch, values, evidence)


def test_artifact_identity_body_cfg_imports_parent_frontier_and_scans(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert raw == target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary(
        evidence
    ).encode()
    if RAW is not None:
        assert hashlib.sha256(raw).hexdigest() == RAW
    if CANONICAL is not None:
        assert target._canonical_sha256(evidence) == CANONICAL
    certificate = _structure(values)
    assert certificate["evidence_sha256"] == target._canonical_sha256(evidence)

    body = evidence["function_body"]
    assert (body["entry_rva"], body["body_size"], len(body["reviewed_points"])) == (
        "0x00357b42",
        40,
        12,
    )
    assert body["control_flow_graph_canonical_sha256"] == CFG
    graph = evidence["control_flow_graph"]
    assert (graph["node_count"], graph["edge_count"]) == (12, 11)
    assert target._canonical_sha256(graph) == CFG
    assert [node["flow_kind"] for node in graph["nodes"]] == [
        "fallthrough", "fallthrough", "fallthrough", "call_fallthrough",
        "fallthrough", "call_fallthrough", "fallthrough", "call_fallthrough",
        "fallthrough", "call_fallthrough", "fallthrough", "terminal",
    ]
    assert graph["nodes"][-1]["flow_kind"] == "terminal"
    assert graph["nodes"][-1]["successor_rvas"] == []

    native = evidence["native_calls"]
    assert native["outgoing_direct"] == []
    opaque = native["opaque_indirect_controls"]
    assert [row["instruction"]["rva"] for row in opaque] == [
        "0x00357b47", "0x00357b50", "0x00357b5b", "0x00357b62"
    ]
    assert all(row["control_encoding"] == "ff15" for row in opaque)
    assert all(row["fallthrough_syntax_only"] for row in opaque)
    assert all(row["runtime_target_opaque"] for row in opaque)
    assert all(row["runtime_execution_or_behavior_opaque"] for row in opaque)
    operands = native["pe_address_operands"]
    assert len(operands) == 4
    assert [row["operand_rva"] for row in operands] == [
        "0x003d60e4", "0x003d6018", "0x003d60f0", "0x003d6014"
    ]
    assert all(row["instruction"]["size"] == 6 for row in operands)
    assert all(row["operand_class"] == "absolute_memory" for row in operands)
    assert all(row["operand_index"] == 0 for row in operands)
    assert all(row["operand_access"] == "read" for row in operands)
    assert all(row["file_backed"] and row["import_metadata_only"] for row in operands)
    assert all(row["contents_or_runtime_behavior_opaque"] for row in operands)
    expected_imports = [
        ("SetUnhandledExceptionFilter", 1189, "0x003d60e4"),
        ("UnhandledExceptionFilter", 1235, "0x003d6018"),
        ("GetCurrentProcess", 448, "0x003d60f0"),
        ("TerminateProcess", 1216, "0x003d6014"),
    ]
    for row, (name, hint, slot) in zip(operands, expected_imports, strict=True):
        metadata = row["pe_import_metadata"]
        binding = row["raw_pe_import_table_binding"]
        assert (metadata["library"], metadata["name"], metadata["hint"], metadata["iat_rva"]) == (
            "KERNEL32.dll", name, hint, slot
        )
        assert binding["metadata_only"]
        assert binding["matching_name_count"] == binding["matching_iat_slot_count"] == 1
        assert binding["descriptor_index"] == 7
        assert binding["descriptor_size"] == 20
        assert binding["original_first_thunk_rva"] == "0x0048ed80"
        assert binding["first_thunk_rva"] == "0x003d6000"
        assert binding["lookup_thunk_rva"]
        assert binding["iat_slot_rva"] == slot
        assert binding["import_by_name_rva"]
        assert binding["hint_and_name_nul_terminated_size"] > 2
        assert len(binding["descriptor_sha256"]) == 64
        assert len(binding["lookup_thunk_sha256"]) == 64
        assert len(binding["iat_slot_sha256"]) == 64
        assert len(binding["hint_and_name_nul_terminated_sha256"]) == 64

    parent = evidence["predecessor_parent_edges"]
    assert len(parent) == 1
    assert parent[0]["instruction"]["rva"] == "0x00357c5c"
    assert parent[0]["source_entry_rva"] == "0x00357b6a"
    assert parent[0]["target_entry_rva"] == "0x00357b42"
    assert parent[0]["control_encoding"] == "e8"

    scan = evidence["whole_atlas_reference_scan"]
    assert scan["aggregates"] == {
        "reference_count": 2, "target_count": 1, "owner_count": 2,
        "target_owner_count": 2, "direct_call_count": 2,
        "other_address_count": 0, "memory_operand_count": 0,
    }
    assert [row["instruction_rva"] for row in scan["references"]] == [
        "0x00357c5c", "0x00357d38"
    ]
    assert len(scan["partition_sha256"]["owner_partition"]) == 64
    assert len(scan["partition_sha256"]["target_owner_partition"]) == 64
    assert len(scan["partition_sha256"]["target_reference_partition"]) == 64

    slot_scans = evidence["whole_atlas_iat_slot_use_scans"]
    assert [row["scanned_operand_rva"] for row in slot_scans] == [
        "0x003d6014", "0x003d6018", "0x003d60e4", "0x003d60f0"
    ]
    expected_counts = {"0x003d6014": 3, "0x003d6018": 3, "0x003d60e4": 5, "0x003d60f0": 13}
    for row in slot_scans:
        assert row["aggregates"]["reference_count"] == expected_counts[row["scanned_operand_rva"]]
        assert row["aggregates"]["immediate_operand_count"] == 0
        assert row["aggregates"]["absolute_memory_operand_count"] == expected_counts[row["scanned_operand_rva"]]
        assert len(row["reference_rows_canonical_sha256"]) == 64
    special = next(row for row in slot_scans if row["scanned_operand_rva"] == "0x003d60f0")
    assert any(
        row["instruction_rva"] == "0x00094fce"
        and row["operand_index"] == 1
        and row["control_syntax"] == "x86_absolute_memory_move_8b3d"
        for row in special["references"]
    )
    assert all(
        native[name] == []
        for name in (
            "segment_qualified_memory_syntax", "bnd_prefixed_control_syntax",
            "opaque_interrupt_syntax",
        )
    )
    assert all(not row["call_rvas"] for row in native["call_r32_audit"])
    assert body["direct_lua_calls"] == body["staged_lua_dispatches"] == []
    assert evidence["function_body"]["ghidra_analysis_metadata"]["metadata_only"]
    assert any("termination" in item for item in evidence["method"]["not_claimed"])


@pytest.mark.parametrize("path", [
    ("schema_version",), ("analysis_kind",),
    ("predecessor_static_boundary", "canonical_sha256"),
    ("function_body", "reviewed_points", 3, "sha256"),
    ("control_flow_graph", "nodes", 1, "successor_rvas"),
    ("native_calls", "opaque_indirect_controls", 2, "control_encoding"),
    ("native_calls", "pe_address_operands", 1, "raw_pe_import_table_binding", "lookup_thunk_rva"),
    ("native_calls", "pe_address_operands", 3, "raw_pe_import_table_binding", "hint_and_name_nul_terminated_sha256"),
    ("predecessor_parent_edges", 0, "instruction", "sha256"),
    ("whole_atlas_reference_scan", "references", 1, "instruction_sha256"),
    ("whole_atlas_reference_scan", "partition_sha256", "owner_partition"),
    ("whole_atlas_iat_slot_use_scans", 3, "references", 1, "operand_index"),
    ("summary", "iat_slot_use_scan_count"),
])
def test_representative_mutations_fail_closed(monkeypatch, values, path):
    _reject(monkeypatch, values, _replace(values["evidence"], path, _changed(_at(values["evidence"], path))))


@pytest.mark.parametrize("path", [
    (), ("function_body",), ("function_body", "reviewed_points", 0),
    ("control_flow_graph", "nodes", 0), ("native_calls",),
    ("native_calls", "opaque_indirect_controls", 0),
    ("native_calls", "pe_address_operands", 0),
    ("whole_atlas_reference_scan",),
    ("whole_atlas_iat_slot_use_scans", 0, "references", 0),
])
def test_unknown_keys_fail_closed(monkeypatch, values, path):
    _reject(monkeypatch, values, _add(values["evidence"], path, True))


@pytest.mark.parametrize("path,replacement", [
    (("function_body", "reviewed_points"), []),
    (("control_flow_graph", "nodes"), []),
    (("native_calls", "opaque_indirect_controls"), []),
    (("native_calls", "pe_address_operands"), []),
    (("predecessor_parent_edges",), []),
    (("whole_atlas_reference_scan", "references"), []),
    (("whole_atlas_iat_slot_use_scans",), []),
    (("whole_atlas_iat_slot_use_scans", 0, "references"), []),
])
def test_list_shapes_fail_closed(monkeypatch, values, path, replacement):
    _reject(monkeypatch, values, _replace(values["evidence"], path, replacement))


@pytest.mark.parametrize("path", [
    ("schema_version",), ("function_body", "body_size"),
    ("native_calls", "opaque_indirect_controls", 0, "instruction", "size"),
    ("native_calls", "pe_address_operands", 0, "operand_index"),
])
def test_bool_is_not_accepted_as_integer(monkeypatch, values, path):
    _reject(monkeypatch, values, _replace(values["evidence"], path, True))


@pytest.mark.parametrize("value", [
    {1: "non-text key"}, {"unsupported": object()}, {"nonfinite": float("nan")},
])
def test_encoder_normalizes_invalid_json_trees(value):
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetSecondCalleeStaticBoundaryError):
        target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary(value)


@pytest.mark.parametrize("failure", [target.CsError(1), struct.error("bad import")])
def test_build_normalizes_decoder_and_struct_errors(monkeypatch, values, failure):
    monkeypatch.setattr(target, "validate_native_lua_direct_call_census", lambda *args, **kwargs: {"status": "verified", "evidence_sha256": target._DIRECT})
    monkeypatch.setattr(target, "_load_executable", lambda *args: (b"", SimpleNamespace(image_base=target._BASE), target._EXE))
    monkeypatch.setattr(target, "_decoder", lambda: (_ for _ in ()).throw(failure))
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetSecondCalleeStaticBoundaryError):
        target.build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary(Path("missing.exe"), *_common(values), inventory={})


def test_synthetic_iat_scan_rejects_extra_immediate_reference(monkeypatch):
    slot = 0x3D6000
    owner = 0x1000
    site = 0x1000
    raw = "ff1500607d00"
    # Match the all-atlas cardinality pins without decoding a real PE: the
    # synthetic iterable reports the exact instruction totals but yields only
    # the two operands relevant to this closure check.
    range_count = target._SCOPE["atlas_body_range_count"]
    byte_count = target._SCOPE["decoded_bytes"]
    ranges = [{"start_rva": "0x00001000", "size": 1}] * (range_count - 1)
    ranges.append({"start_rva": "0x00001000", "size": byte_count - (range_count - 1)})
    function = {"ranges": ranges}
    expected_row = {
        "instruction_rva": "0x00001000", "instruction_size": 6,
        "instruction_sha256": hashlib.sha256(bytes.fromhex(raw)).hexdigest(),
        "owner_entry_rva": "0x00001000", "owner_atlas_record_sha256": "a" * 64,
        "operand_class": "absolute_memory", "operand_index": 0,
        "operand_access": "read", "operand_va": "0x007d6000",
        "operand_rva": "0x003d6000",
        "control_syntax": "x86_absolute_memory_indirect_call_ff15",
    }
    monkeypatch.setattr(
        target, "_SLOT_SCANS",
        {slot: ("0" * 64, target._compact([expected_row]), ((site, owner, raw, 0),))},
    )
    monkeypatch.setattr(target, "_functions", lambda facts: {owner: function})
    monkeypatch.setattr(target, "atlas_record_sha256", lambda value: "a" * 64)
    expected_memory = SimpleNamespace(
        type=x86.X86_OP_MEM,
        access=1,
        mem=SimpleNamespace(disp=target._BASE + slot, segment=x86.X86_REG_INVALID, base=x86.X86_REG_INVALID, index=x86.X86_REG_INVALID),
    )
    extra_immediate = SimpleNamespace(
        type=x86.X86_OP_IMM, access=0, imm=target._BASE + slot
    )
    instruction = SimpleNamespace(
        address=target._BASE + site,
        bytes=bytes.fromhex(raw),
        operands=[expected_memory],
    )
    class SyntheticDecoded:
        def __init__(self, yielded, count):
            self.yielded = yielded
            self.count = count

        def __iter__(self):
            return iter(self.yielded)

        def __len__(self):
            return self.count

    calls = 0

    def decode_range(*args):
        nonlocal calls
        calls += 1
        return SyntheticDecoded(
            [instruction] if calls == 1 else [],
            target._SCOPE["decoded_instructions"] if calls == 1 else 0,
        )

    monkeypatch.setattr(target, "_decode_range", decode_range)
    image = SimpleNamespace(image_base=target._BASE)
    baseline = target._slot_scan(
        {"unused": True}, slot, b"", image, SimpleNamespace(detail=False)
    )
    assert baseline["aggregates"]["reference_count"] == 1

    calls = 0
    instruction.operands.append(extra_immediate)
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetSecondCalleeStaticBoundaryError, match="IAT exhaustive scan"):
        target._slot_scan({"unused": True}, slot, b"", image, SimpleNamespace(detail=False))


def test_cli_verify_structure(values, capsys):
    paths = values["paths"]
    assert cli.main([
        "verify-structure", "--predecessor-static-boundary", str(paths["predecessor"]),
        "--direct-calls", str(paths["direct"]), "--program-facts", str(paths["facts"]),
        "--evidence", str(paths["evidence"]),
    ]) == 0
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["status"] == "structurally_verified"
    assert certificate["evidence_sha256"] == target._canonical_sha256(values["evidence"])


def _root(monkeypatch, temporary):
    info = temporary.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (temporary, temporary, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def _rendered(values):
    return target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary(values["evidence"])


def test_cli_immutable_existing_difference_and_outside_root(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path)
    output = tmp_path / "e.json"
    rendered = _rendered(values)
    cli._write_immutably(output, rendered, values["evidence"])
    output.write_bytes(rendered.encode() + b" ")
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetSecondCalleeStaticBoundaryError, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode() + b" "
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetSecondCalleeStaticBoundaryError, match="direct child"):
        cli._write_immutably(tmp_path.parent / "outside.json", rendered, values["evidence"])


@pytest.mark.parametrize("existing", [True, False])
def test_cli_final_locked_corruption_preserves_or_cleans(tmp_path, monkeypatch, values, existing):
    _root(monkeypatch, tmp_path)
    output = tmp_path / "e.json"
    rendered = _rendered(values)
    if existing:
        output.write_bytes(rendered.encode())
    original = cli._read_locked_json_document
    monkeypatch.setattr(cli, "_read_locked_json_document", lambda descriptor, label: (lambda result: (result[0], result[1] + b" "))(original(descriptor, label)))
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetSecondCalleeStaticBoundaryError, match="final content validation"):
        cli._write_immutably(output, rendered, values["evidence"])
    assert output.exists() is existing


def test_cli_lock_contention(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path)
    output = tmp_path / "e.json"
    rendered = _rendered(values)
    output.write_bytes(rendered.encode())
    seen = []
    original = cli._read_locked_json_document

    def writer():
        if os.name == "nt":
            try:
                with output.open("ab") as stream:
                    stream.write(b" ")
            except OSError:
                seen.append("blocked")
            else:
                seen.append("mutated")
        else:
            import fcntl
            descriptor = os.open(output, os.O_WRONLY | os.O_APPEND)
            try:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    seen.append("blocked")
                else:
                    os.write(descriptor, b" ")
                    seen.append("mutated")
            finally:
                os.close(descriptor)

    def locked(descriptor, label):
        value = original(descriptor, label)
        thread = threading.Thread(target=writer)
        thread.start()
        thread.join(5)
        assert not thread.is_alive()
        return value

    monkeypatch.setattr(cli, "_read_locked_json_document", locked)
    cli._write_immutably(output, rendered, values["evidence"])
    assert seen == ["blocked"]


@pytest.mark.skipif(not os.environ.get("ITB_EXACT_EXE"), reason="exact installed executable is opt-in")
def test_exact_verify_is_sha_guarded(values):
    executable = Path(os.environ["ITB_EXACT_EXE"])
    if hashlib.sha256(executable.read_bytes()).hexdigest() != target._EXE:
        pytest.skip("opt-in executable does not match the sealed build")
    inventory = _read(values["paths"]["inventory"])
    result = target.validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary(
        executable, values["evidence"], *_common(values), inventory=inventory
    )
    assert result["status"] == "verified"
