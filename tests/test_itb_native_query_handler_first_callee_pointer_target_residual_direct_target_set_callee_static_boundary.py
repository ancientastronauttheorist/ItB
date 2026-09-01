"""Regression coverage for the residual direct-target-set callee receipt."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import (
    itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary as cli,
)
from src.observatory import (
    native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary as target,
)
from src.observatory.native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary import (
    NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
PREFIX = "windows_build_13725832_31fe35265598_"
RAW = "548580d0fee7d612fe16bfe10b567ffd2c8d9a6add9cfd965a75c48c22123c2b"
CANONICAL = "8e8a4c0d5c462bf20417b529313e634a76030214c34c35f0875e506a4f57f8b1"


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values():
    paths = {
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "residual": PROGRAMS
        / (
            PREFIX
            + "native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json"
        ),
        "evidence": PROGRAMS
        / (
            PREFIX
            + "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.json"
        ),
    }
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    return result


def _common(values):
    return values["residual"], values["direct"], values["facts"]


def _structure(values, evidence=None):
    return target.validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary_structure(
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
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError
    ):
        _fast(monkeypatch, values, evidence)


def test_artifact_identity_cfg_calls_scan_and_nonclaims(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW
    assert raw == target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary(
        evidence
    ).encode()
    assert target._canonical_sha256(evidence) == CANONICAL
    assert _structure(values)["evidence_sha256"] == CANONICAL

    body = evidence["function_body"]
    assert (body["entry_rva"], body["body_size"], len(body["reviewed_points"])) == (
        "0x003574ca",
        17,
        4,
    )
    graph = evidence["control_flow_graph"]
    assert target._canonical_sha256(graph) == body["control_flow_graph_canonical_sha256"]
    assert (graph["node_count"], graph["edge_count"]) == (4, 3)
    assert graph["nodes"][1]["successor_rvas"] == ["0x003574d3", "0x003574d5"]
    assert graph["nodes"][2]["flow_kind"] == "terminal"
    assert graph["nodes"][3]["flow_kind"] == "direct_unconditional_external_branch"

    native = evidence["native_calls"]
    assert [row["decoded_mnemonic"] for row in native["bnd_prefixed_control_syntax"]] == [
        "bnd jne",
        "bnd ret",
        "bnd jmp",
    ]
    assert native["outgoing_direct"][0]["control_encoding"] == "f2e9"
    assert native["outgoing_direct"][0]["target_entry_rva"] == "0x00357b6a"
    assert len(native["pe_address_operands"]) == 3
    assert native["opaque_indirect_controls"] == []

    parents = evidence["residual_direct_target_parent_edges"]
    assert [row["control_encoding"] for row in parents] == ["e8", "e9"]
    assert [row["instruction"]["rva"] for row in parents] == [
        "0x0037298a",
        "0x0037299d",
    ]
    scan = evidence["whole_atlas_reference_scan"]
    assert scan["aggregates"] == {
        "bnd_f2e8_direct_call_count": 3,
        "direct_call_count": 1793,
        "e9_other_address_count": 1,
        "memory_operand_count": 0,
        "other_address_count": 1,
        "owner_count": 1620,
        "reference_count": 1794,
        "standard_e8_direct_call_count": 1790,
        "target_count": 1,
        "target_owner_count": 1620,
    }
    assert scan["partition_sha256"] == {
        "owner_partition": target._OWNER_PARTITION_SHA256,
        "target_owner_partition": target._TARGET_OWNER_PARTITION_SHA256,
        "target_reference_partition": target._TARGET_REFERENCE_PARTITION_SHA256,
    }
    rows = {row["instruction_rva"]: row for row in scan["references"]}
    assert rows["0x00001bd9"]["call_form"] == "x86_relative_near_call_e8"
    assert rows["0x003581d3"]["call_form"] == "x86_bnd_relative_near_call_f2e8"
    assert rows["0x003581e4"]["call_form"] == "x86_bnd_relative_near_call_f2e8"
    assert rows["0x0039d7be"]["call_form"] == "x86_bnd_relative_near_call_f2e8"
    assert rows["0x0037299d"]["call_form"] is None
    assert rows["0x0037299d"]["use_class"] == "other_address"
    assert rows["0x0037299d"]["instruction_sha256"] == parents[1]["instruction"]["sha256"]
    assert any("runtime" in row for row in evidence["method"]["not_claimed"])
    assert any("Lua-side" in row for row in evidence["method"]["not_claimed"])


@pytest.mark.parametrize(
    "path",
    [
        ("schema_version",),
        ("analysis_kind",),
        ("function_body", "reviewed_points", 1, "rva"),
        ("control_flow_graph", "nodes", 1, "successor_rvas"),
        ("native_calls", "bnd_prefixed_control_syntax", 2, "target_scope"),
        ("native_calls", "outgoing_direct", 0, "target_body_sha256"),
        ("residual_direct_target_parent_edges", 1, "control_encoding"),
        ("whole_atlas_reference_scan", "references", 0, "instruction_sha256"),
        ("whole_atlas_reference_scan", "references", 17, "owner_entry_rva"),
        ("whole_atlas_reference_scan", "references", -1, "call_form"),
        ("whole_atlas_reference_scan", "partition_sha256", "owner_partition"),
        ("whole_atlas_reference_scan", "partition_sha256", "target_owner_partition"),
        ("whole_atlas_reference_scan", "partition_sha256", "target_reference_partition"),
        ("summary", "target_reference_count"),
    ],
)
def test_representative_mutations_fail_closed(monkeypatch, values, path):
    original = _at(values["evidence"], path)
    _reject(monkeypatch, values, _replace(values["evidence"], path, _changed(original)))


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("function_body",),
        ("function_body", "reviewed_points", 0),
        ("control_flow_graph", "nodes", 0),
        ("native_calls",),
        ("native_calls", "bnd_prefixed_control_syntax", 0),
        ("native_calls", "outgoing_direct", 0),
        ("residual_direct_target_parent_edges", 0),
        ("whole_atlas_reference_scan",),
        ("whole_atlas_reference_scan", "references", 0),
        ("whole_atlas_reference_scan", "partition_sha256"),
    ],
)
def test_unknown_keys_fail_closed(monkeypatch, values, path):
    _reject(monkeypatch, values, _add(values["evidence"], path, True))


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("function_body", "reviewed_points"), []),
        (("control_flow_graph", "nodes"), []),
        (("native_calls", "bnd_prefixed_control_syntax"), []),
        (("native_calls", "outgoing_direct"), []),
        (("residual_direct_target_parent_edges",), []),
        (("whole_atlas_reference_scan", "references"), []),
        (("whole_atlas_reference_scan", "target_partition"), []),
        (("whole_atlas_reference_scan", "owner_partition"), []),
        (("whole_atlas_reference_scan", "target_owner_partition"), []),
        (("whole_atlas_reference_scan", "target_reference_partition"), []),
    ],
)
def test_list_shapes_fail_closed(monkeypatch, values, path, replacement):
    _reject(monkeypatch, values, _replace(values["evidence"], path, replacement))


def test_parent_and_outgoing_joins_fail_closed(values):
    parents = copy.deepcopy(values["evidence"]["residual_direct_target_parent_edges"])
    parents[1]["instruction"]["sha256"] = "0" * 64
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError,
        match="parent/reference join",
    ):
        target._parent_scan_join(parents, values["evidence"]["whole_atlas_reference_scan"])

    graph = copy.deepcopy(values["evidence"]["control_flow_graph"])
    graph["nodes"][-1]["flow_kind"] = "terminal"
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError,
        match="outgoing/CFG join",
    ):
        target._outgoing_graph_join(
            values["evidence"]["native_calls"]["outgoing_direct"], graph
        )


@pytest.mark.parametrize(
    "value",
    [{1: "non-text key"}, {"unsupported": object()}, {"nonfinite": float("nan")}],
)
def test_encoder_normalizes_invalid_json_trees(value):
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError
    ):
        target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary(
            value
        )


def test_exact_builder_normalizes_capstone_failure(monkeypatch, values):
    monkeypatch.setattr(
        target,
        "validate_native_lua_direct_call_census",
        lambda *args, **kwargs: {
            "status": "verified",
            "evidence_sha256": target._DIRECT,
        },
    )
    monkeypatch.setattr(
        target,
        "_load_executable",
        lambda *args: (
            b"",
            SimpleNamespace(image_base=target._IMAGE_BASE),
            target._EXE,
        ),
    )
    monkeypatch.setattr(
        target,
        "_decoder",
        lambda: (SimpleNamespace(detail=False), object()),
    )

    def fail_decode(*args):
        raise target.CsError(1)

    monkeypatch.setattr(target, "_decode_range", fail_decode)
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError
    ):
        target.build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary(
            Path("sealed.exe"),
            *_common(values),
            inventory={},
        )


def test_cli_verify_structure(values, capsys):
    paths = values["paths"]
    assert cli.main([
        "verify-structure",
        "--residual-direct-target-set-static-boundary", str(paths["residual"]),
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
    return target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary(
        values["evidence"]
    )


def test_cli_immutable_output_refuses_differing_existing(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path)
    output = tmp_path / "e.json"
    rendered = _rendered(values)
    cli._write_immutably(output, rendered, values["evidence"])
    output.write_bytes(rendered.encode() + b" ")
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError,
        match="refusing to overwrite",
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode() + b" "


def test_cli_rejects_outside_root_and_normalizes_root_failure(tmp_path, monkeypatch, values):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    _root(monkeypatch, allowed)
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError,
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
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError,
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
        NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeStaticBoundaryError,
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
