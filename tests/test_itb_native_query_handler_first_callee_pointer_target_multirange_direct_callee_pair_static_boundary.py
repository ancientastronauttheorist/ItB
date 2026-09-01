"""Regression coverage for the paired direct-callee static receipt."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
from pathlib import Path

import pytest

from scripts import (
    itb_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary as cli,
)
from src.observatory import (
    native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary as target,
)
from src.observatory.native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary import (
    NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
RAW = "bffdbec3554c1969563d4ac235a2e7d150aff311b5b277a31a9f413a3b5094e2"
CANONICAL = "c479ae8d802d848877f8fd57475d8909e0fe2129d25182996d16f599b6cbaf8c"
CFGS = (
    "f189c9abc78a31c21e1b5e479382105374ab05508d05b181cedd61083d3999cb",
    "94c13ceee9fdf0c3d9feeb6664abca7380f97df101a86dcc5265e12461bee80e",
)


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


EVIDENCE_PATH = PROGRAMS / (
    PREFIX
    + "native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary.json"
)
STATIC_EVIDENCE = _read(EVIDENCE_PATH)


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


def _mappings(value, path=()):
    if isinstance(value, dict):
        yield path
        for key, item in value.items():
            yield from _mappings(item, path + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _mappings(item, path + (index,))


def _lists(value, path=()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _lists(item, path + (key,))
    elif isinstance(value, list):
        yield path, value
        for index, item in enumerate(value):
            yield from _lists(item, path + (index,))


LEAF_PATHS = tuple(_leaves(STATIC_EVIDENCE))
MAPPING_PATHS = tuple(_mappings(STATIC_EVIDENCE))
LIST_PATHS = tuple(path for path, _value in _lists(STATIC_EVIDENCE))


@pytest.fixture(scope="module")
def values():
    paths = {
        "inventory": INVENTORIES
        / (PREFIX + "full_decompile_baseline_20260830.json"),
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "multirange": PROGRAMS
        / (
            PREFIX
            + "native_query_handler_first_callee_pointer_target_multirange_static_boundary.json"
        ),
        "evidence": EVIDENCE_PATH,
    }
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    return result


def _common(values):
    return values["multirange"], values["direct"], values["facts"]


def _structure(values, evidence=None):
    return target.validate_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary_structure(
        values["evidence"] if evidence is None else evidence,
        *_common(values),
    )


def _replace(value, path, replacement):
    if not path:
        return replacement
    result = dict(value) if isinstance(value, dict) else list(value)
    result[path[0]] = _replace(value[path[0]], path[1:], replacement)
    return result


def _add(value, path, addition):
    result = dict(value) if isinstance(value, dict) else list(value)
    if not path:
        result["unexpected"] = addition
        return result
    result[path[0]] = _add(value[path[0]], path[1:], addition)
    return result


def _remove(value, path):
    result = dict(value) if isinstance(value, dict) else list(value)
    if len(path) == 1:
        del result[path[0]]
        return result
    result[path[0]] = _remove(value[path[0]], path[1:])
    return result


def _at(value, path):
    for key in path:
        value = value[key]
    return value


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
    monkeypatch.setattr(target, "_validate_json_tree", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        target, "_evidence", lambda *args, **kwargs: values["evidence"]
    )
    monkeypatch.setattr(
        target, "_assert_publication_safe", lambda *args, **kwargs: None
    )
    return _structure(values, evidence)


def _reject_fast(monkeypatch, values, evidence):
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError
    ):
        _fast(monkeypatch, values, evidence)


def test_identity_bodies_cfg_partitions_and_nonclaims(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW
    assert raw == target.encode_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary(
        evidence
    ).encode()
    assert target._canonical_sha256(evidence) == CANONICAL
    assert _structure(values)["evidence_sha256"] == CANONICAL

    bodies = evidence["function_bodies"]
    assert [body["entry_rva"] for body in bodies] == [
        "0x0039d530",
        "0x0039d640",
    ]
    assert [body["body_size"] for body in bodies] == [67, 49]
    assert [body["control_flow_graph_canonical_sha256"] for body in bodies] == list(
        CFGS
    )
    assert [len(body["reviewed_points"]) for body in bodies] == [33, 19]
    assert all(
        body["direct_lua_calls"] == body["staged_lua_dispatches"] == []
        for body in bodies
    )
    assert all(
        not row["call_rvas"]
        for body in bodies
        for row in body["call_r32_audit"]
    )

    graphs = evidence["control_flow_graphs"]
    assert [(graph["node_count"], graph["edge_count"]) for graph in graphs] == [
        (33, 36),
        (19, 19),
    ]
    assert [target._canonical_json_sha256(graph) for graph in graphs] == list(CFGS)
    assert all(
        graph["body_local_successor_policy"]
        == evidence["method"]["body_local_successor_policy"]
        for graph in graphs
    )
    first = {row["rva"]: row for row in graphs[0]["nodes"]}
    assert first["0x0039d54f"]["successor_rvas"] == [
        "0x0039d551",
        "0x0039d56c",
    ]
    assert first["0x0039d559"]["successor_rvas"] == [
        "0x0039d55b",
        "0x0039d564",
    ]
    assert first["0x0039d562"]["successor_rvas"] == [
        "0x0039d564",
        "0x0039d56e",
    ]
    assert first["0x0039d56a"]["successor_rvas"] == [
        "0x0039d56c",
        "0x0039d554",
    ]
    assert first["0x0039d572"]["flow_kind"] == "terminal"
    assert first["0x0039d572"]["successor_rvas"] == []
    second = {row["rva"]: row for row in graphs[1]["nodes"]}
    assert second["0x0039d64e"]["successor_rvas"] == [
        "0x0039d650",
        "0x0039d654",
    ]
    assert second["0x0039d661"]["successor_rvas"] == [
        "0x0039d663",
        "0x0039d66f",
    ]
    assert [
        row["rva"]
        for row in graphs[1]["nodes"]
        if row["flow_kind"] == "terminal"
    ] == ["0x0039d653", "0x0039d670"]

    parents = evidence["multirange_parent_edges"]
    assert parents == values["multirange"]["native_calls"]["outgoing_direct"]
    assert [row["instruction"]["rva"] for row in parents] == [
        "0x0039d5bf",
        "0x0039d5d9",
    ]
    assert [row["target_entry_rva"] for row in parents] == [
        "0x0039d640",
        "0x0039d530",
    ]

    native = evidence["native_calls"]
    assert native["outgoing_direct"] == []
    assert native["opaque_indirect_controls"] == []
    assert native["segment_qualified_memory_syntax"] == []
    assert all(not row["call_rvas"] for row in native["call_r32_audit"])
    pe = native["pe_address_operands"]
    assert [row["instruction"]["rva"] for row in pe] == [
        "0x0039d54f",
        "0x0039d559",
        "0x0039d562",
        "0x0039d56a",
        "0x0039d64e",
        "0x0039d661",
    ]
    assert all(
        (
            row["operand_class"],
            row["operand_index"],
            row["operand_access"],
            row["section_name"],
            row["section_writable"],
            row["file_backed"],
        )
        == ("immediate", 0, "none", ".text", False, True)
        for row in pe
    )

    scan = evidence["whole_atlas_reference_scan"]
    assert scan["scope"] == {
        "atlas_function_count": 25312,
        "atlas_body_range_count": 25490,
        "decoded_bytes": 3735718,
        "decoded_instructions": 1153814,
        "all_declared_ranges_decoded": True,
        "operand_classes": ["absolute_memory", "immediate"],
    }
    assert scan["aggregates"] == {
        "reference_count": 2,
        "target_count": 2,
        "owner_count": 1,
        "target_owner_count": 2,
        "direct_call_count": 2,
        "other_address_count": 0,
        "memory_operand_count": 0,
    }
    assert scan["partition_sha256"] == {
        "owner_partition": target._PAIR_OWNER_HASH,
        "target_owner_partition": target._PAIR_TARGET_OWNER_HASH,
        "target_reference_partition": target._PAIR_TARGET_REF_HASH,
    }
    assert [row["target_rva"] for row in scan["target_partition"]] == [
        "0x0039d530",
        "0x0039d640",
    ]
    parent_by_site = {row["instruction"]["rva"]: row for row in parents}
    for reference in scan["references"]:
        parent = parent_by_site[reference["instruction_rva"]]
        assert reference["instruction_sha256"] == parent["instruction"]["sha256"]
        assert reference["owner_entry_rva"] == parent["source_entry_rva"]
        assert reference["target_rva"] == parent["target_entry_rva"]
        assert reference["operand_class"] == "immediate"
        assert reference["use_class"] == "direct_call"
    assert any(
        "semantic identity" in item for item in evidence["method"]["not_claimed"]
    )
    assert any("un-atlased" in item for item in evidence["method"]["not_claimed"])


@pytest.mark.parametrize("path", LEAF_PATHS)
def test_every_nested_leaf_rejects(monkeypatch, values, path):
    changed = _replace(
        values["evidence"], path, _changed(_at(values["evidence"], path))
    )
    _reject_fast(monkeypatch, values, changed)


@pytest.mark.parametrize("path", MAPPING_PATHS)
def test_unknown_key_at_every_mapping_rejects(monkeypatch, values, path):
    _reject_fast(monkeypatch, values, _add(values["evidence"], path, True))


@pytest.mark.parametrize("path", LIST_PATHS)
def test_every_list_shape_rejects(monkeypatch, values, path):
    original = _at(values["evidence"], path)
    changed = [True] if not original else list(original[:-1])
    _reject_fast(monkeypatch, values, _replace(values["evidence"], path, changed))


@pytest.mark.parametrize(
    "path",
    [
        ("schema_version",),
        ("analysis_kind",),
        ("function_bodies", 0, "ranges"),
        ("function_bodies", 1, "control_flow_graph_canonical_sha256"),
        ("control_flow_graphs", 0, "nodes", 26, "successor_rvas"),
        ("control_flow_graphs", 1, "nodes", 13, "successor_rvas"),
        ("native_calls", "pe_address_operands", 5, "operand_index"),
        ("whole_atlas_reference_scan", "references", 1, "operand_index"),
        ("summary", "schema_violations"),
    ],
)
def test_required_field_removal_rejects(monkeypatch, values, path):
    _reject_fast(monkeypatch, values, _remove(values["evidence"], path))


def test_parent_and_scan_joins_reject(values):
    multirange = copy.deepcopy(values["multirange"])
    multirange["native_calls"]["outgoing_direct"][0]["instruction"][
        "sha256"
    ] = "0" * 64
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError,
        match="parent edge identity",
    ):
        target._parent_rows(multirange, values["facts"])

    scan = copy.deepcopy(values["evidence"]["whole_atlas_reference_scan"])
    scan["references"][0]["instruction_sha256"] = "0" * 64
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError,
        match="parent/reference join",
    ):
        target._parent_scan_join(
            values["evidence"]["multirange_parent_edges"], scan
        )


def test_exact_builder_requires_verified_direct_census(monkeypatch, values):
    seen = {}

    def fake(_executable, _direct, _facts, *, inventory):
        seen["inventory"] = inventory
        return {"status": "verified", "evidence_sha256": "0" * 64}

    monkeypatch.setattr(target, "validate_native_lua_direct_call_census", fake)
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError,
        match="direct-call exact prerequisite",
    ):
        target.build_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary(
            EXE,
            *_common(values),
            inventory=values["inventory"],
        )
    assert seen["inventory"] is values["inventory"]


@pytest.mark.parametrize(
    "value",
    [
        {1: "non-text key"},
        {"unsupported": object()},
        {"nonfinite": float("nan")},
    ],
)
def test_encoder_normalizes_invalid_json_trees(value):
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError
    ):
        target.encode_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary(
            value
        )


def test_exact_rebuild_and_validate(values):
    if not EXE.is_file():
        pytest.skip("sealed executable unavailable")
    rebuilt = target.build_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary(
        EXE,
        *_common(values),
        inventory=values["inventory"],
    )
    assert rebuilt == values["evidence"]
    verification = target.validate_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary(
        EXE,
        values["evidence"],
        *_common(values),
        inventory=values["inventory"],
    )
    assert verification["status"] == "verified"
    assert verification["evidence_sha256"] == CANONICAL


def _root(monkeypatch, temporary):
    info = temporary.stat()
    monkeypatch.setattr(
        cli, "_prepare_output_root", lambda: (temporary, temporary, info)
    )
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def _rendered(values):
    return target.encode_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary(
        values["evidence"]
    )


def test_cli_error_normalization_and_existing_preservation(
    tmp_path, monkeypatch, values
):
    _root(monkeypatch, tmp_path)
    output = tmp_path / "e.json"
    rendered = _rendered(values)
    cli._write_immutably(output, rendered, values["evidence"])
    output.write_bytes(rendered.encode() + b" ")
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError,
        match="refusing to overwrite",
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    monkeypatch.setattr(
        cli,
        "_prepare_output_root",
        lambda: (_ for _ in ()).throw(
            cli.NativeLuaPropertyFactoryChainError("inherited root failure")
        ),
    )
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError,
        match="inherited root failure",
    ):
        cli._write_immutably(
            tmp_path / "other.json", rendered, values["evidence"]
        )
    assert output.read_bytes() == rendered.encode() + b" "


def test_cli_rejects_output_outside_program_root(tmp_path, monkeypatch, values):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    _root(monkeypatch, allowed)
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError,
        match="direct child",
    ):
        cli._write_immutably(
            tmp_path / "outside.json", _rendered(values), values["evidence"]
        )


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
        NativeQueryHandlerFirstCalleePointerTargetMultirangeDirectCalleePairStaticBoundaryError,
        match="final content validation",
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    if existing:
        assert output.read_bytes() == rendered.encode()
    else:
        assert not output.exists()
