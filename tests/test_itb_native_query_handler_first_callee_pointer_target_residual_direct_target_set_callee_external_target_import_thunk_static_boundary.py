"""PE-free regression coverage for the sealed 0x0039cb92 import thunk."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import (
    itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary as cli,
)
from src.observatory import (
    native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary as target,
)
from src.observatory.native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary import (
    NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
PREFIX = "windows_build_13725832_31fe35265598_"
RAW = "91397015cb9d8cd74fe2f18d648060c1e8cb28baa6b79f15f39e55ff77e3b71f"
CANONICAL = "af117e253c45140863acc378051d6b5b1eba37458337aad43be6ef22d2589654"
CFG = "29e8bc268788c4dad137925a79b4350355d7f7db2dd2666bbc21399dd5bce60c"


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values():
    paths = {
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "predecessor": PROGRAMS / (
            PREFIX
            + "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary.json"
        ),
        "evidence": PROGRAMS / (
            PREFIX
            + "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary.json"
        ),
    }
    return {**{name: _read(path) for name, path in paths.items()}, "paths": paths}


def _common(values):
    return values["predecessor"], values["direct"], values["facts"]


def _structure(values, evidence=None):
    return target.validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary_structure(
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


def _add(value, path):
    if not path:
        return {**value, "unexpected": True}
    result = dict(value) if isinstance(value, dict) else list(value)
    result[path[0]] = _add(value[path[0]], path[1:])
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
        return [*value, True]
    raise AssertionError(type(value))


def _fast(monkeypatch, values, evidence):
    monkeypatch.setattr(target, "_validate_json_tree", lambda *args: None)
    monkeypatch.setattr(target, "_evidence", lambda *args, **kwargs: values["evidence"])
    return _structure(values, evidence)


def _reject(monkeypatch, values, evidence):
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError
    ):
        _fast(monkeypatch, values, evidence)


def test_identity_body_cfg_import_frontier_slot_and_summary(values):
    evidence, paths = values["evidence"], values["paths"]
    raw = paths["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW
    assert raw == target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary(evidence).encode()
    assert target._canonical_sha256(evidence) == CANONICAL
    assert _structure(values)["evidence_sha256"] == CANONICAL

    body, graph, native = evidence["function_body"], evidence["control_flow_graph"], evidence["native_calls"]
    assert (body["entry_rva"], body["body_size"], len(body["reviewed_points"])) == ("0x0039cb92", 6, 1)
    assert body["body_sha256"] == "247575b8ff280345c05bf6c58c3620b861c076bb718663401c6c729f4542cee7"
    assert body["control_flow_graph_canonical_sha256"] == CFG
    assert target._canonical_sha256(graph) == CFG
    assert (graph["node_count"], graph["edge_count"]) == (1, 0)
    assert graph["nodes"][0]["flow_kind"] == "indirect_jump"
    assert graph["nodes"][0]["successor_rvas"] == []
    assert body["direct_lua_calls"] == body["staged_lua_dispatches"] == []

    assert native["outgoing_direct"] == []
    assert native["opaque_interrupt_syntax"] == []
    assert native["bnd_prefixed_control_syntax"] == []
    assert native["segment_qualified_memory_syntax"] == []
    assert all(not row["call_rvas"] for row in native["call_r32_audit"])
    opaque = native["opaque_indirect_controls"]
    assert len(opaque) == 1
    assert opaque[0]["instruction"] == {"rva": "0x0039cb92", "size": 6, "sha256": body["body_sha256"]}
    assert opaque[0]["control_encoding"] == "ff25"
    assert opaque[0]["runtime_target_opaque"] is True
    assert opaque[0]["runtime_execution_or_behavior_opaque"] is True

    operands = native["pe_address_operands"]
    assert len(operands) == 1
    operand = operands[0]
    assert (operand["operand_class"], operand["operand_access"], operand["operand_va"], operand["operand_rva"], operand["file_backed"]) == (
        "absolute_memory", "read", "0x007d6010", "0x003d6010", True,
    )
    assert operand["control_syntax"] == "x86_absolute_memory_indirect_jump_ff25"
    assert operand["pe_import_metadata"] == {
        "evidence_class": "fact", "library": "KERNEL32.dll", "name": "IsProcessorFeaturePresent",
        "ordinal": None, "hint": 772, "iat_rva": "0x003d6010",
    }
    assert operand["raw_pe_import_table_binding"] == {
        "pe_bits": 32,
        "import_directory_rva": "0x0048eca4", "import_directory_size": 220,
        "import_directory_file_offset": "0x0048dca4",
        "import_directory_sha256": "788f7357cb31ba62895740d67e0d8a0f6bf962c467ec801a29cf9044d522fd65",
        "descriptor_count": 10, "import_record_count": 342, "named_import_count": 342,
        "ordinal_import_count": 0, "kernel32_import_count": 139,
        "matching_name_count": 1, "matching_iat_slot_count": 1,
        "descriptor_index": 7, "descriptor_rva": "0x0048ed30",
        "descriptor_file_offset": "0x0048dd30", "descriptor_size": 20,
        "descriptor_sha256": "fe01ec3285fd8be5c0857ae597b2ac4a14de3579860f5f3577a6bdbe8595bc10",
        "original_first_thunk_rva": "0x0048ed80", "timestamp": 0, "forwarder_chain": 0,
        "first_thunk_rva": "0x003d6000", "library_name_rva": "0x004905fe",
        "library_name_file_offset": "0x0048f5fe", "library_nul_terminated_size": 13,
        "library_nul_terminated_sha256": "f8efc1f27ef6c525f7fd20dcb8d65e8197e97410eced20db4d323dfbf230a2a4",
        "thunk_index": 4, "lookup_thunk_rva": "0x0048ed90",
        "lookup_thunk_file_offset": "0x0048dd90", "lookup_thunk_raw_value": "0x00490a02",
        "lookup_thunk_sha256": "4a4a07bfd0b46732c457558065401cc422a188a7e84dfb482d179bd610989a61",
        "iat_slot_rva": "0x003d6010", "iat_slot_file_offset": "0x003d5010",
        "iat_slot_raw_value": "0x00490a02",
        "iat_slot_sha256": "4a4a07bfd0b46732c457558065401cc422a188a7e84dfb482d179bd610989a61",
        "import_by_name_rva": "0x00490a02", "import_by_name_file_offset": "0x0048fa02",
        "hint_and_name_nul_terminated_size": 28,
        "hint_and_name_nul_terminated_sha256": "bd0a4eda3c3cad901506880438be40e8c7fe64cb99de20e10c67759b071b7f47",
        "hint": 772, "name": "IsProcessorFeaturePresent", "metadata_only": True,
    }
    assert operand["import_metadata_only"] is True
    assert operand["contents_or_runtime_behavior_opaque"] is True

    parent = evidence["predecessor_parent_edges"]
    assert len(parent) == 1
    assert parent[0]["instruction"]["rva"] == "0x00357b75"
    assert parent[0]["control_encoding"] == "e8"
    scan = evidence["whole_atlas_reference_scan"]
    assert scan["aggregates"] == {
        "reference_count": 6, "target_count": 1, "owner_count": 6, "target_owner_count": 6,
        "direct_call_count": 6, "other_address_count": 0, "memory_operand_count": 0,
    }
    assert len(scan["references"]) == len(scan["owner_partition"]) == 6
    assert scan["references"][0]["instruction_rva"] == parent[0]["instruction"]["rva"]
    assert scan["partition_sha256"] == {
        "owner_partition": "1bbecba81a7d7aa4aeca7f1f710d6f01f560569ffa80408e47615ced30e2abcd",
        "target_owner_partition": "3a8c2764b1ef2d34109ba3afefbceac6055183a06bf28065f29b231f54dd0f8c",
        "target_reference_partition": "4ac37284ab3f41c7661c27432c2e89564f73e16913fa0f183b564f6d2330604e",
    }
    slot = evidence["whole_atlas_iat_slot_use_scan"]
    assert (slot["scanned_operand_va"], slot["scanned_operand_rva"], slot["aggregates"]) == (
        "0x007d6010", "0x003d6010", {"reference_count": 1, "owner_count": 1, "absolute_memory_operand_count": 1, "indirect_jump_count": 1},
    )
    assert slot["references"] == [{
        "instruction_rva": "0x0039cb92", "instruction_size": 6, "instruction_sha256": body["body_sha256"],
        "owner_entry_rva": "0x0039cb92", "owner_atlas_record_sha256": "495f4729075f0f38c369905e1cd00f3f3d9b1eb5247caf5ce112fec3e6066f4e",
        "operand_class": "absolute_memory", "operand_index": 0, "operand_access": "read",
        "operand_va": "0x007d6010", "operand_rva": "0x003d6010", "control_syntax": "x86_absolute_memory_indirect_jump_ff25",
    }]
    assert scan["scope"] == slot["scope"] == {
        "atlas_function_count": 25312, "atlas_body_range_count": 25490, "decoded_bytes": 3735718,
        "decoded_instructions": 1153814, "all_declared_ranges_decoded": True,
        "operand_classes": ["absolute_memory", "immediate"],
    }
    assert evidence["summary"] == target._summary()
    assert any("target resolution" in item for item in evidence["method"]["not_claimed"])


@pytest.mark.parametrize("path", [
    ("schema_version",), ("analysis_kind",), ("predecessor_static_boundary", "canonical_sha256"),
    ("function_body", "body_sha256"), ("control_flow_graph", "nodes", 0, "flow_kind"),
    ("control_flow_graph", "nodes", 0, "successor_rvas"),
    ("native_calls", "opaque_indirect_controls", 0, "control_encoding"),
    ("native_calls", "opaque_indirect_controls", 0, "runtime_target_opaque"),
    ("native_calls", "pe_address_operands", 0, "operand_rva"),
    ("native_calls", "pe_address_operands", 0, "pe_import_metadata", "hint"),
    ("native_calls", "pe_address_operands", 0, "raw_pe_import_table_binding", "import_directory_sha256"),
    ("native_calls", "pe_address_operands", 0, "raw_pe_import_table_binding", "descriptor_sha256"),
    ("native_calls", "pe_address_operands", 0, "raw_pe_import_table_binding", "lookup_thunk_raw_value"),
    ("native_calls", "pe_address_operands", 0, "raw_pe_import_table_binding", "iat_slot_sha256"),
    ("native_calls", "pe_address_operands", 0, "raw_pe_import_table_binding", "hint_and_name_nul_terminated_sha256"),
    ("native_calls", "pe_address_operands", 0, "raw_pe_import_table_binding", "kernel32_import_count"),
    ("native_calls", "pe_address_operands", 0, "raw_pe_import_table_binding", "matching_name_count"),
    ("native_calls", "pe_address_operands", 0, "raw_pe_import_table_binding", "lookup_thunk_rva"),
    ("native_calls", "pe_address_operands", 0, "file_backed"),
    ("predecessor_parent_edges", 0, "control_encoding"),
    ("whole_atlas_reference_scan", "references", 0, "instruction_sha256"),
    ("whole_atlas_reference_scan", "partition_sha256", "owner_partition"),
    ("whole_atlas_iat_slot_use_scan", "references", 0, "operand_va"),
    ("whole_atlas_iat_slot_use_scan", "aggregates", "reference_count"),
    ("method", "not_claimed", 1), ("summary", "opaque_indirect_control_count"),
])
def test_mutations_fail_closed(monkeypatch, values, path):
    _reject(monkeypatch, values, _replace(values["evidence"], path, _changed(_at(values["evidence"], path))))


@pytest.mark.parametrize("path", [
    (), ("function_body",), ("function_body", "reviewed_points", 0), ("control_flow_graph",),
    ("control_flow_graph", "nodes", 0), ("native_calls",),
    ("native_calls", "opaque_indirect_controls", 0), ("native_calls", "pe_address_operands", 0),
    ("native_calls", "pe_address_operands", 0, "raw_pe_import_table_binding"),
    ("predecessor_parent_edges", 0), ("whole_atlas_reference_scan",),
    ("whole_atlas_iat_slot_use_scan", "references", 0), ("summary",),
])
def test_unknown_keys_fail_closed(monkeypatch, values, path):
    _reject(monkeypatch, values, _add(values["evidence"], path))


@pytest.mark.parametrize("path,replacement", [
    (("function_body", "reviewed_points"), []), (("control_flow_graph", "nodes"), []),
    (("native_calls", "opaque_indirect_controls"), []), (("native_calls", "pe_address_operands"), []),
    (("native_calls", "call_r32_audit"), []), (("predecessor_parent_edges",), []),
    (("whole_atlas_reference_scan", "references"), []), (("whole_atlas_reference_scan", "owner_partition"), []),
    (("whole_atlas_iat_slot_use_scan", "references"), []),
])
def test_list_shapes_fail_closed(monkeypatch, values, path, replacement):
    _reject(monkeypatch, values, _replace(values["evidence"], path, replacement))


@pytest.mark.parametrize("path", [
    ("schema_version",), ("function_body", "body_size"),
    ("native_calls", "opaque_indirect_controls", 0, "runtime_target_opaque"),
    ("native_calls", "pe_address_operands", 0, "raw_pe_import_table_binding", "metadata_only"),
    ("native_calls", "pe_address_operands", 0, "raw_pe_import_table_binding", "descriptor_count"),
    ("summary", "target_reference_count"),
])
def test_bool_int_confusion_fails_closed(values, path):
    current = _at(values["evidence"], path)
    evidence = _replace(values["evidence"], path, 1 if isinstance(current, bool) else True)
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError):
        _structure(values, evidence)


@pytest.mark.parametrize("value", [{1: "bad key"}, {"bad": object()}, {"bad": float("nan")}])
def test_encoder_rejects_non_json_trees(value):
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError):
        target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary(value)


def test_build_normalizes_decoder_error(monkeypatch, values):
    monkeypatch.setattr(target, "validate_native_lua_direct_call_census", lambda *args, **kwargs: {"status": "verified", "evidence_sha256": target._DIRECT_SHA256})
    monkeypatch.setattr(target, "_load_executable", lambda *args: (b"", SimpleNamespace(image_base=target._IMAGE_BASE), target._EXE_SHA256))
    monkeypatch.setattr(target, "_decoder", lambda: (_ for _ in ()).throw(target.CsError(1)))
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError):
        target.build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary(Path("missing.exe"), *_common(values), inventory={})


def test_iat_slot_scan_rejects_an_extra_immediate_reference(monkeypatch):
    import capstone.x86_const as x86

    class Decoded:
        def __init__(self, instructions, count):
            self.instructions = instructions
            self.count = count

        def __iter__(self):
            return iter(self.instructions)

        def __len__(self):
            return self.count

    memory = SimpleNamespace(
        type=x86.X86_OP_MEM,
        access=1,
        mem=SimpleNamespace(
            segment=x86.X86_REG_INVALID,
            base=x86.X86_REG_INVALID,
            index=x86.X86_REG_INVALID,
            disp=target._IAT_VA,
        ),
    )
    immediate = SimpleNamespace(
        type=x86.X86_OP_IMM,
        access=0,
        imm=target._IAT_VA,
    )
    root_instruction = SimpleNamespace(
        address=target._IMAGE_BASE + target._ROOT_RVA,
        bytes=bytes.fromhex(target._ROOT_BYTES),
        operands=[memory],
    )
    extra_instruction = SimpleNamespace(
        address=target._IMAGE_BASE + target._ROOT_RVA + 8,
        bytes=bytes.fromhex("6810607d00"),
        operands=[immediate],
    )
    ranges = [{"start_rva": "0x00000001", "size": 3710229}]
    ranges.extend(
        {"start_rva": "0x00000002", "size": 1} for _ in range(25489)
    )
    monkeypatch.setattr(target, "_atlas_functions", lambda _facts: {1: {"ranges": ranges}})
    monkeypatch.setattr(
        target,
        "_decode_range",
        lambda _data, _image, _start, size, _decoder: (
            Decoded([root_instruction, extra_instruction], 1153814)
            if size == 3710229
            else []
        ),
    )
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError,
        match="IAT-slot use scan differs",
    ):
        target._iat_slot_use_scan(
            {},
            b"",
            SimpleNamespace(image_base=target._IMAGE_BASE),
            SimpleNamespace(detail=False),
        )


def test_cli_verify_structure(values, capsys):
    paths = values["paths"]
    assert cli.main(["verify-structure", "--predecessor-static-boundary", str(paths["predecessor"]), "--direct-calls", str(paths["direct"]), "--program-facts", str(paths["facts"]), "--evidence", str(paths["evidence"])]) == 0
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["status"] == "structurally_verified"
    assert certificate["evidence_sha256"] == CANONICAL


def _root(monkeypatch, temporary):
    info = temporary.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (temporary, temporary, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def _rendered(values):
    return target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary(values["evidence"])


def test_cli_existing_difference_and_outside_root(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path)
    output, rendered = tmp_path / "e.json", _rendered(values)
    cli._write_immutably(output, rendered, values["evidence"])
    output.write_bytes(rendered.encode() + b" ")
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, values["evidence"])
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError, match="direct child"):
        cli._write_immutably(tmp_path.parent / "outside.json", rendered, values["evidence"])


def test_cli_root_recheck_and_final_corruption(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path)
    output, rendered = tmp_path / "e.json", _rendered(values)
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: (_ for _ in ()).throw(cli.NativeLuaPropertyFactoryChainError("root changed")))
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError, match="root changed"):
        cli._write_immutably(output, rendered, values["evidence"])
    _root(monkeypatch, tmp_path)
    original = cli._read_locked_json_document
    monkeypatch.setattr(cli, "_read_locked_json_document", lambda descriptor, label: (lambda item: (item[0], item[1] + b" "))(original(descriptor, label)))
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetImportThunkStaticBoundaryError, match="final content validation"):
        cli._write_immutably(output, rendered, values["evidence"])
    assert not output.exists()


def test_cli_lock_contention(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path)
    output, rendered, seen = tmp_path / "e.json", _rendered(values), []
    output.write_bytes(rendered.encode())
    original = cli._read_locked_json_document
    def writer():
        if os.name == "nt":
            try:
                with output.open("ab") as stream: stream.write(b" ")
            except OSError: seen.append("blocked")
            else: seen.append("mutated")
        else:
            import fcntl
            descriptor = os.open(output, os.O_WRONLY | os.O_APPEND)
            try:
                try: fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError: seen.append("blocked")
                else: os.write(descriptor, b" "); seen.append("mutated")
            finally: os.close(descriptor)
    def locked(descriptor, label):
        result = original(descriptor, label)
        thread = threading.Thread(target=writer); thread.start(); thread.join(5)
        assert not thread.is_alive()
        return result
    monkeypatch.setattr(cli, "_read_locked_json_document", locked)
    cli._write_immutably(output, rendered, values["evidence"])
    assert seen == ["blocked"]


@pytest.mark.skipif(os.environ.get("ITB_EXACT_IMPORT_THUNK_TEST") != "1", reason="requires the exact installed executable")
def test_exact_installed_executable_is_sha_guarded(values):
    executable = Path(os.environ["ITB_EXACT_IMPORT_THUNK_EXE"])
    if hashlib.sha256(executable.read_bytes()).hexdigest() != target._EXE_SHA256:
        pytest.skip("installed executable SHA does not match the sealed build")
    inventory = _read(Path(os.environ["ITB_EXACT_IMPORT_THUNK_INVENTORY"]))
    certificate = target.validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary(executable, values["evidence"], *_common(values), inventory=inventory)
    assert certificate["status"] == "verified"
