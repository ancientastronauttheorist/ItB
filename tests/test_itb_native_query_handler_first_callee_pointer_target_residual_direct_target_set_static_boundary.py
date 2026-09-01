import copy
import hashlib
import json
import os
import threading
from pathlib import Path

import pytest

from scripts import (
    itb_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary as cli,
)
from src.observatory import (
    native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary as target,
)
from src.observatory.native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary import (
    NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
RAW = "13784d112c47e9de5b0a92f7cfaac17245a98afb48214699ed516360b6d4d702"
CANONICAL = "0783fffcd973eca3937ce01faa4d4f93b974540cfdaf004a301ce7ef0198fd5d"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values():
    paths = {
        "inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"),
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "pointer": PROGRAMS / (PREFIX + "native_query_handler_first_callee_pointer_target_static_boundary.json"),
        "cluster": PROGRAMS / (PREFIX + "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json"),
        "evidence": PROGRAMS / (PREFIX + "native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json"),
    }
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    result["functions"] = target._atlas_functions(result["facts"])
    result["declared"] = target._declared_edges(result["facts"])
    result["image_base"] = int(result["facts"]["ghidra"]["image_base"], 16)
    result["preflight"] = target._preflight(
        result["pointer"], result["cluster"], result["direct"], result["facts"]
    )
    result["parents"] = target._partition_pointer_rows(result["pointer"], result["cluster"])
    result["direct_lua"] = target._direct_lua_partition(result["direct"])
    result["bodies"] = {
        entry: target._expected_body(entry, result["facts"]) for entry in target._TARGETS
    }
    result["edges"] = target._edge_rows(result["facts"])
    result["scan"] = result["evidence"]["whole_atlas_reference_scan"]
    return result


def _common(values):
    return values["pointer"], values["cluster"], values["direct"], values["facts"]


def _structure(values, evidence=None):
    return target.validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary_structure(
        values["evidence"] if evidence is None else evidence, *_common(values)
    )


def _replace(value, path, replacement):
    if not path:
        return replacement
    result = dict(value) if isinstance(value, dict) else list(value)
    result[path[0]] = _replace(value[path[0]], path[1:], replacement)
    return result


def _add(value, path, addition):
    if len(path) == 1:
        result = dict(value)
        result[path[0]] = addition
        return result
    result = dict(value) if isinstance(value, dict) else list(value)
    result[path[0]] = _add(value[path[0]], path[1:], addition)
    return result


def _remove(value, path):
    if len(path) == 1:
        result = dict(value)
        del result[path[0]]
        return result
    result = dict(value) if isinstance(value, dict) else list(value)
    result[path[0]] = _remove(value[path[0]], path[1:])
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


def _leaves(value, path=()):
    if isinstance(value, dict):
        if not value:
            yield path
        for key, item in value.items():
            yield from _leaves(item, path + (key,))
    elif isinstance(value, list):
        if not value:
            yield path
        for index, item in enumerate(value):
            yield from _leaves(item, path + (index,))
    else:
        yield path


def _lists(value, path=()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _lists(item, path + (key,))
    elif isinstance(value, list):
        yield path, value
        for index, item in enumerate(value):
            yield from _lists(item, path + (index,))


def _at(value, path):
    for key in path:
        value = value[key]
    return value


def _fast(monkeypatch, values, evidence):
    monkeypatch.setattr(target, "_validate_json_tree", lambda *args, **kwargs: None)
    monkeypatch.setattr(target, "validate_native_lua_direct_call_structure", lambda *args, **kwargs: {
        "status": "structurally_verified", "evidence_sha256": target._DIRECT,
    })
    monkeypatch.setattr(target, "_preflight", lambda *args: values["preflight"])
    monkeypatch.setattr(target, "_partition_pointer_rows", lambda *args: values["parents"])
    monkeypatch.setattr(target, "_direct_lua_partition", lambda *args: values["direct_lua"])
    monkeypatch.setattr(target, "_expected_body", lambda entry, facts: values["bodies"][entry])
    monkeypatch.setattr(target, "_edge_rows", lambda facts: values["edges"])

    def scan_structure(scan, _facts):
        if not target._same(scan, values["scan"]):
            raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError(
                "fast scan differs"
            )

    monkeypatch.setattr(target, "_scan_structure", scan_structure)
    monkeypatch.setattr(target, "_parent_scan_join", lambda *args: None)
    monkeypatch.setattr(target, "_assert_publication_safe", lambda *args: None)
    return _structure(values, evidence)


def _reject(monkeypatch, values, evidence):
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError):
        _fast(monkeypatch, values, evidence)


def test_identity_cfg_partitions_and_nonclaims(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW
    assert raw == target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary(evidence).encode()
    assert target._canonical_sha256(evidence) == CANONICAL
    assert _structure(values)["evidence_sha256"] == CANONICAL
    assert [
        (body["entry_rva"], body["body_size"], len(body["reviewed_points"]))
        for body in evidence["function_bodies"]
    ] == [("0x00372970", 50, 21), ("0x00007e70", 1, 1), ("0x003581b3", 6, 1)]
    assert [
        (graph["node_count"], graph["edge_count"], graph["nodes"][-1]["flow_kind"])
        for graph in evidence["control_flow_graphs"]
    ] == [(21, 21, "direct_unconditional_external_branch"), (1, 0, "terminal"), (1, 0, "indirect_jump")]
    assert evidence["pointer_target_direct_partition"]["pointer_target_parent_count"] == 11
    assert [
        len(evidence[name]) for name in (
            "residual_parent_rows", "adjacent_cluster_parent_rows", "deferred_multirange_parent_rows"
        )
    ] == [5, 5, 1]
    assert evidence["whole_atlas_reference_scan"]["partition_sha256"] == {
        "owner_partition": target._OWNER_PARTITION_SHA256,
        "target_owner_partition": target._TARGET_OWNER_PARTITION_SHA256,
        "target_reference_partition": target._TARGET_REFERENCE_PARTITION_SHA256,
    }
    assert len(evidence["native_calls"]["pe_address_operands"]) == 4
    assert evidence["native_calls"]["opaque_indirect_controls"][0]["encoding"] == "ff25"
    for word in ("semantic kinship", "runtime", "dynamic target", "Lua-side"):
        assert any(word.lower() in claim.lower() for claim in evidence["method"]["not_claimed"])


def test_every_non_scan_nested_leaf_rejects(values, monkeypatch):
    for path in _leaves(values["evidence"]):
        if path and path[0] == "whole_atlas_reference_scan":
            continue
        original = _at(values["evidence"], path)
        changed = _changed(original)
        assert changed != original
        _reject(monkeypatch, values, _replace(values["evidence"], path, changed))


@pytest.mark.parametrize("path", [
    ("unexpected",),
    ("decoder", "unexpected"),
    ("function_bodies", 0, "unexpected"),
    ("function_bodies", 0, "reviewed_points", 0, "unexpected"),
    ("function_bodies", 0, "call_r32_audit", 0, "unexpected"),
    ("control_flow_graphs", 0, "unexpected"),
    ("control_flow_graphs", 0, "nodes", 0, "unexpected"),
    ("residual_parent_rows", 0, "unexpected"),
    ("native_calls", "unexpected"),
    ("native_calls", "outgoing_direct", 0, "unexpected"),
    ("native_calls", "opaque_indirect_controls", 0, "unexpected"),
    ("native_calls", "pe_address_operands", 0, "unexpected"),
    ("whole_atlas_reference_scan", "unexpected"),
    ("whole_atlas_reference_scan", "scope", "unexpected"),
    ("whole_atlas_reference_scan", "references", 0, "unexpected"),
    ("whole_atlas_reference_scan", "aggregates", "unexpected"),
])
def test_unknown_keys_reject(values, monkeypatch, path):
    _reject(monkeypatch, values, _add(values["evidence"], path, True))


def test_every_non_scan_list_field_and_shape_rejects(values, monkeypatch):
    for path, sequence in _lists(values["evidence"]):
        if path and path[0] == "whole_atlas_reference_scan":
            continue
        parent = _at(values["evidence"], path[:-1])
        assert isinstance(parent, dict) and isinstance(path[-1], str), path
        _reject(monkeypatch, values, _remove(values["evidence"], path))
        replacement = list(sequence[1:]) if sequence else [True]
        assert replacement != sequence
        _reject(monkeypatch, values, _replace(values["evidence"], path, replacement))
        duplicate = list(sequence) + [copy.deepcopy(sequence[0])] if sequence else [True]
        assert duplicate != sequence
        _reject(monkeypatch, values, _replace(values["evidence"], path, duplicate))
        if len(sequence) > 1:
            reversed_sequence = list(reversed(sequence))
            if reversed_sequence != sequence:
                _reject(monkeypatch, values, _replace(values["evidence"], path, reversed_sequence))


def test_body_cfg_and_call_r32_list_shapes_are_enumerated(values):
    list_paths = {path for path, _ in _lists(values["evidence"])}
    for body_index, body in enumerate(values["evidence"]["function_bodies"]):
        assert ("function_bodies", body_index, "reviewed_points") in list_paths
        assert ("function_bodies", body_index, "direct_lua_calls") in list_paths
        assert ("function_bodies", body_index, "staged_lua_dispatches") in list_paths
        assert ("function_bodies", body_index, "call_r32_audit") in list_paths
        for audit_index, _audit in enumerate(body["call_r32_audit"]):
            assert ("function_bodies", body_index, "call_r32_audit", audit_index, "call_rvas") in list_paths
    for graph_index, graph in enumerate(values["evidence"]["control_flow_graphs"]):
        assert ("control_flow_graphs", graph_index, "nodes") in list_paths
        for node_index, _node in enumerate(graph["nodes"]):
            assert ("control_flow_graphs", graph_index, "nodes", node_index, "successor_rvas") in list_paths
    assert ("decoder", "register_call_encoding_audit") in list_paths


@pytest.mark.parametrize("path,value", [
    (("schema_version",), True),
    (("decoder",), []),
    (("pointer_target_direct_partition", "pointer_target_parent_count"), True),
    (("function_bodies",), {}),
    (("function_bodies", 0, "body_size"), True),
    (("control_flow_graphs", 0, "node_count"), True),
    (("native_calls", "pe_address_operand_partition_complete"), 1),
    (("whole_atlas_reference_scan", "aggregates"), []),
    (("summary", "schema_violations"), False),
])
def test_wrong_types_reject(values, monkeypatch, path, value):
    _reject(monkeypatch, values, _replace(values["evidence"], path, value))


@pytest.mark.parametrize("path,value", [
    (("control_flow_graphs", 0, "nodes", 20, "successor_rvas"), ["0x003574ca"]),
    (("control_flow_graphs", 2, "nodes", 0, "flow_kind"), "terminal"),
    (("out_of_body_direct_transfers",), []),
    (("native_calls", "opaque_indirect_controls", 0, "operand_access"), "none"),
    (("native_calls", "opaque_indirect_controls", 0, "section_name"), ".data"),
    (("native_calls", "pe_address_operands", 0, "operand_va"), "0x007d6581"),
    (("function_bodies", 0, "direct_lua_calls"), [{"changed": True}]),
    (("function_bodies", 1, "staged_lua_dispatches"), [{"changed": True}]),
    (("function_bodies", 2, "call_r32_audit", 0, "call_rvas"), ["0x003581b3"]),
    (("deferred_multirange_parent_rows",), []),
])
def test_explicit_cfg_control_lua_and_parent_attacks_reject(values, monkeypatch, path, value):
    _reject(monkeypatch, values, _replace(values["evidence"], path, value))


def test_every_reference_row_field_rejects_cheaply(values):
    for row in values["scan"]["references"]:
        for key, original in row.items():
            changed = dict(row)
            changed[key] = _changed(original)
            with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError):
                target._reference_row(
                    changed, values["functions"], values["declared"], values["image_base"]
                )


def test_scan_structure_and_partition_attacks(values):
    target._scan_structure(values["scan"], values["facts"])
    attacks = [
        (("scope", "decoded_bytes"), 3735719),
        (("target_partition", 0, "owner_count"), 2),
        (("target_reference_partition", 0, "reference_count"), 253),
        (("owner_partition", 0, "reference_count"), 2),
        (("target_owner_partition", 0, "reference_count"), 2),
        (("partition_sha256", "owner_partition"), "0" * 64),
        (("aggregates", "direct_call_count"), 718),
    ]
    for path, value in attacks:
        with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError):
            target._scan_structure(_replace(values["scan"], path, value), values["facts"])
    reordered = dict(values["scan"])
    reordered["references"] = list(values["scan"]["references"])
    reordered["references"][:2] = reversed(reordered["references"][:2])
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError):
        target._scan_structure(reordered, values["facts"])


def test_exact_rebuild_and_validate(values):
    if not EXE.is_file():
        pytest.skip("sealed executable unavailable")
    rebuilt = target.build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary(
        EXE, *_common(values), inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    assert target.validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary(
        EXE, values["evidence"], *_common(values), inventory=values["inventory"]
    )["status"] == "verified"


def _root(monkeypatch, temporary):
    info = temporary.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (temporary, temporary, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def test_cli_error_normalization_and_existing_preservation(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path)
    output = tmp_path / "e.json"
    rendered = target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary(values["evidence"])
    cli._write_immutably(output, rendered, values["evidence"])
    output.write_bytes(rendered.encode() + b" ")
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, values["evidence"])
    monkeypatch.setattr(
        cli, "_prepare_output_root",
        lambda: (_ for _ in ()).throw(cli.NativeLuaPropertyFactoryChainError("inherited root failure")),
    )
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError, match="inherited root failure"):
        cli._write_immutably(tmp_path / "other.json", rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode() + b" "


def test_cli_rejects_output_outside_program_root(tmp_path, monkeypatch, values):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    _root(monkeypatch, allowed)
    rendered = target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary(values["evidence"])
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError, match="direct child"):
        cli._write_immutably(tmp_path / "outside.json", rendered, values["evidence"])


def test_cli_lock_contention(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path)
    output = tmp_path / "e.json"
    rendered = target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary(values["evidence"])
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
        thread.start(); thread.join(5)
        assert not thread.is_alive()
        return value

    monkeypatch.setattr(cli, "_read_locked_json_document", locked)
    cli._write_immutably(output, rendered, values["evidence"])
    assert seen == ["blocked"]


@pytest.mark.parametrize("existing", [True, False])
def test_cli_final_locked_read_corruption_preserves_or_cleans(tmp_path, monkeypatch, values, existing):
    _root(monkeypatch, tmp_path)
    output = tmp_path / "e.json"
    rendered = target.encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary(values["evidence"])
    if existing:
        output.write_bytes(rendered.encode())
    original = cli._read_locked_json_document

    def corrupt(descriptor, label):
        value, payload = original(descriptor, label)
        return value, payload + b" "

    monkeypatch.setattr(cli, "_read_locked_json_document", corrupt)
    with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetStaticBoundaryError, match="final content validation"):
        cli._write_immutably(output, rendered, values["evidence"])
    if existing:
        assert output.read_bytes() == rendered.encode()
    else:
        assert not output.exists()
