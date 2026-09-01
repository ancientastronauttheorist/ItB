"""Regression coverage for the residual-callee external-target receipt."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import (
    itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary as cli,
)
from src.observatory import (
    native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary as target,
)
from src.observatory.native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary import (
    NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
PREFIX = "windows_build_13725832_31fe35265598_"
RAW = "366bbfcf22cf6ed4dd667308336036191651c4d6dba3d48e6ae51271b66998c6"
CANONICAL = "0d8bb3aecc53090dc5282844885ed327e79541ebaad4b7ca928e0494f86b08a9"
CFG = "020e22523160d01f527e80e62320f1052dc8654755d8aee3b8a88ae4dcc14048"


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values():
    paths = {
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "predecessor": PROGRAMS
        / (
            PREFIX
            + "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.json"
        ),
        "evidence": PROGRAMS
        / (
            PREFIX
            + "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary.json"
        ),
    }
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    return result


def _common(values):
    return values["predecessor"], values["direct"], values["facts"]


def _structure(values, evidence=None):
    return target.validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary_structure(
        values["evidence"] if evidence is None else evidence,
        *_common(values),
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
    monkeypatch.setattr(target, "_assert_publication_safe", lambda *args: None)
    return _structure(values, evidence)


def _reject(monkeypatch, values, evidence):
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError
    ):
        _fast(monkeypatch, values, evidence)


def test_artifact_identity_body_interrupt_calls_operands_and_scan(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW
    assert raw == target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary(
        evidence
    ).encode()
    assert target._canonical_sha256(evidence) == CANONICAL
    assert _structure(values)["evidence_sha256"] == CANONICAL

    body = evidence["function_body"]
    assert (body["entry_rva"], body["body_size"], len(body["reviewed_points"])) == (
        "0x00357b6a",
        251,
        56,
    )
    assert body["control_flow_graph_canonical_sha256"] == CFG
    graph = evidence["control_flow_graph"]
    assert target._canonical_sha256(graph) == CFG
    assert (graph["node_count"], graph["edge_count"]) == (56, 55)
    interrupt_node = {node["rva"]: node for node in graph["nodes"]}["0x00357b81"]
    assert interrupt_node["flow_kind"] == "terminal"
    assert interrupt_node["successor_rvas"] == []
    native = evidence["native_calls"]
    assert native["opaque_interrupt_syntax"] == [{
        "instruction": {
            "rva": "0x00357b81",
            "sha256": "cde60391fdd88745523e1fb00399098a3ccf2c23e2d9010e121612872ca49229",
            "size": 2,
        },
        "interrupt_vector": "0x29",
        "role": "opaque_interrupt_syntax",
        "runtime_semantics_opaque": True,
    }]
    assert [row["instruction"]["rva"] for row in native["outgoing_direct"]] == [
        "0x00357b75",
        "0x00357c5c",
    ]
    assert [row["control_encoding"] for row in native["outgoing_direct"]] == ["e8", "e8"]
    assert [row["target_entry_rva"] for row in native["outgoing_direct"]] == [
        "0x0039cb92",
        "0x00357b42",
    ]
    parent = evidence["predecessor_parent_edges"]
    assert len(parent) == 1
    assert parent[0]["control_encoding"] == "f2e9"
    assert parent[0]["instruction"]["rva"] == "0x003574d5"

    operands = native["pe_address_operands"]
    assert len(operands) == 28
    assert (sum(item["file_backed"] for item in operands), sum(
        not item["file_backed"] for item in operands
    )) == (6, 22)
    assert (sum(item["operand_access"] == "write" for item in operands), sum(
        item["operand_access"] == "read" for item in operands
    )) == (21, 3)
    assert all(
        native[name] == []
        for name in (
            "opaque_indirect_controls",
            "bnd_prefixed_control_syntax",
            "segment_qualified_memory_syntax",
        )
    )
    assert all(not row["call_rvas"] for row in native["call_r32_audit"])
    assert body["direct_lua_calls"] == body["staged_lua_dispatches"] == []
    assert any("interrupt behavior" in item for item in evidence["method"]["not_claimed"])

    scan = evidence["whole_atlas_reference_scan"]
    assert scan["aggregates"] == {
        "direct_call_count": 0,
        "memory_operand_count": 0,
        "other_address_count": 1,
        "owner_count": 1,
        "reference_count": 1,
        "target_count": 1,
        "target_owner_count": 1,
    }
    assert scan["partition_sha256"] == {
        "owner_partition": "2a2416dd95714b643e9479120de7fa221ca334afb358d3c3ebed2cfd155be7ba",
        "target_owner_partition": "2947e96c511745d6e8cdeec79be647a470829e7aad9ea2156e72a2894370e492",
        "target_reference_partition": "c8390fdbf8e42e8a1fa6256377a5ddb23304a651eae818eaebf2a3f23a5c31bf",
    }
    reference = scan["references"][0]
    assert reference["instruction_rva"] == parent[0]["instruction"]["rva"]
    assert reference["instruction_sha256"] == parent[0]["instruction"]["sha256"]
    assert reference["owner_entry_rva"] == parent[0]["source_entry_rva"]
    assert reference["target_rva"] == parent[0]["target_entry_rva"]


@pytest.mark.parametrize(
    "path",
    [
        ("schema_version",),
        ("analysis_kind",),
        ("predecessor_static_boundary", "canonical_sha256"),
        ("function_body", "reviewed_points", 9, "sha256"),
        ("control_flow_graph", "nodes", 9, "flow_kind"),
        ("control_flow_graph", "nodes", 6, "successor_rvas"),
        ("native_calls", "opaque_interrupt_syntax", 0, "interrupt_vector"),
        ("native_calls", "outgoing_direct", 0, "target_body_sha256"),
        ("native_calls", "pe_address_operands", 2, "file_backed"),
        ("native_calls", "pe_address_operands", 24, "file_backed"),
        ("native_calls", "pe_address_operands", 2, "operand_access"),
        ("predecessor_parent_edges", 0, "control_encoding"),
        ("whole_atlas_reference_scan", "references", 0, "instruction_sha256"),
        ("whole_atlas_reference_scan", "partition_sha256", "owner_partition"),
        ("summary", "pe_data_absolute_memory_write_count"),
    ],
)
def test_representative_mutations_fail_closed(monkeypatch, values, path):
    _reject(monkeypatch, values, _replace(values["evidence"], path, _changed(_at(values["evidence"], path))))


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("function_body",),
        ("function_body", "reviewed_points", 0),
        ("control_flow_graph",),
        ("control_flow_graph", "nodes", 0),
        ("native_calls",),
        ("native_calls", "opaque_interrupt_syntax", 0),
        ("native_calls", "outgoing_direct", 0),
        ("native_calls", "pe_address_operands", 0),
        ("predecessor_parent_edges", 0),
        ("whole_atlas_reference_scan",),
        ("whole_atlas_reference_scan", "references", 0),
    ],
)
def test_unknown_keys_fail_closed(monkeypatch, values, path):
    _reject(monkeypatch, values, _add(values["evidence"], path, True))


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("function_body", "reviewed_points"), []),
        (("control_flow_graph", "nodes"), []),
        (("native_calls", "opaque_interrupt_syntax"), []),
        (("native_calls", "outgoing_direct"), []),
        (("native_calls", "pe_address_operands"), []),
        (("native_calls", "call_r32_audit"), []),
        (("predecessor_parent_edges",), []),
        (("whole_atlas_reference_scan", "references"), []),
        (("whole_atlas_reference_scan", "owner_partition"), []),
        (("whole_atlas_reference_scan", "target_owner_partition"), []),
    ],
)
def test_list_shapes_fail_closed(monkeypatch, values, path, replacement):
    _reject(monkeypatch, values, _replace(values["evidence"], path, replacement))


@pytest.mark.parametrize(
    "value",
    [{1: "non-text key"}, {"unsupported": object()}, {"nonfinite": float("nan")}],
)
def test_encoder_normalizes_invalid_json_trees(value):
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError
    ):
        target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary(
            value
        )


def test_build_normalizes_decoder_error(monkeypatch, values):
    monkeypatch.setattr(
        target,
        "validate_native_lua_direct_call_census",
        lambda *args, **kwargs: {
            "status": "verified", "evidence_sha256": target._DIRECT
        },
    )
    monkeypatch.setattr(
        target,
        "_load_executable",
        lambda *args: (b"", SimpleNamespace(image_base=target._IMAGE_BASE), target._EXE),
    )
    monkeypatch.setattr(
        target,
        "_decoder",
        lambda: (_ for _ in ()).throw(target.CsError(1)),
    )
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError
    ):
        target.build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary(
            Path("missing.exe"), *_common(values), inventory={}
        )


def test_cli_verify_structure(values, capsys):
    paths = values["paths"]
    assert cli.main([
        "verify-structure",
        "--predecessor-static-boundary", str(paths["predecessor"]),
        "--direct-calls", str(paths["direct"]),
        "--program-facts", str(paths["facts"]),
        "--evidence", str(paths["evidence"]),
    ]) == 0
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["status"] == "structurally_verified"
    assert certificate["evidence_sha256"] == CANONICAL


def _root(monkeypatch, temporary):
    info = temporary.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (temporary, temporary, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def _rendered(values):
    return target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary(
        values["evidence"]
    )


def test_cli_immutable_existing_difference(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path)
    output = tmp_path / "e.json"
    rendered = _rendered(values)
    cli._write_immutably(output, rendered, values["evidence"])
    output.write_bytes(rendered.encode() + b" ")
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError,
        match="refusing to overwrite",
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode() + b" "


def test_cli_outside_root_and_root_error(tmp_path, monkeypatch, values):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    _root(monkeypatch, allowed)
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError,
        match="direct child",
    ):
        cli._write_immutably(tmp_path / "outside.json", _rendered(values), values["evidence"])
    monkeypatch.setattr(
        cli,
        "_prepare_output_root",
        lambda: (_ for _ in ()).throw(
            cli.NativeLuaPropertyFactoryChainError("inherited root failure")
        ),
    )
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError,
        match="inherited root failure",
    ):
        cli._write_immutably(tmp_path / "other.json", _rendered(values), values["evidence"])


@pytest.mark.parametrize("existing", [True, False])
def test_cli_final_locked_read_corruption_preserves_or_cleans(
    tmp_path, monkeypatch, values, existing
):
    _root(monkeypatch, tmp_path)
    output = tmp_path / "e.json"
    rendered = _rendered(values)
    if existing:
        output.write_bytes(rendered.encode())
    original = cli._read_locked_json_document

    def corrupt(descriptor, label):
        value, payload = original(descriptor, label)
        return value, payload + b" "

    monkeypatch.setattr(cli, "_read_locked_json_document", corrupt)
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError,
        match="final content validation",
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    if existing:
        assert output.read_bytes() == rendered.encode()
    else:
        assert not output.exists()


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
