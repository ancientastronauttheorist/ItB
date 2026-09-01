"""Regression coverage for the deferred multi-range static receipt."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
from pathlib import Path

import pytest

from scripts import (
    itb_native_query_handler_first_callee_pointer_target_multirange_static_boundary as cli,
)
from src.observatory import (
    native_query_handler_first_callee_pointer_target_multirange_static_boundary as target,
)
from src.observatory.native_query_handler_first_callee_pointer_target_multirange_static_boundary import (
    NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
RAW = "ecf806bea49d116e0dd785d5d22aab4a769b51634efd1545acefa303d5c17778"
CANONICAL = "a19a16ff5b999872acba98381163dc7d67113864ff508454d63162aa719e1c4e"
CFG = "9f88252951d61c605a8deea0eb6e3e9cf1e85453e1515aded9c62b5539214d94"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


EVIDENCE_PATH = PROGRAMS / (
    PREFIX
    + "native_query_handler_first_callee_pointer_target_multirange_static_boundary.json"
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
        "pointer": PROGRAMS
        / (
            PREFIX
            + "native_query_handler_first_callee_pointer_target_static_boundary.json"
        ),
        "residual": PROGRAMS
        / (
            PREFIX
            + "native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json"
        ),
        "evidence": EVIDENCE_PATH,
    }
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    return result


def _common(values):
    return (
        values["pointer"],
        values["residual"],
        values["direct"],
        values["facts"],
    )


def _structure(values, evidence=None):
    return target.validate_native_query_handler_first_callee_pointer_target_multirange_static_boundary_structure(
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
    if len(path) == 1:
        result = dict(value) if isinstance(value, dict) else list(value)
        del result[path[0]]
        return result
    result = dict(value) if isinstance(value, dict) else list(value)
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
    monkeypatch.setattr(target, "_evidence", lambda *args, **kwargs: values["evidence"])
    monkeypatch.setattr(target, "_assert_publication_safe", lambda *args, **kwargs: None)
    return _structure(values, evidence)


def _reject_fast(monkeypatch, values, evidence):
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError
    ):
        _fast(monkeypatch, values, evidence)


def test_identity_ranges_cfg_partitions_and_nonclaims(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW
    assert raw == target.encode_native_query_handler_first_callee_pointer_target_multirange_static_boundary(
        evidence
    ).encode()
    assert target._canonical_sha256(evidence) == CANONICAL
    assert _structure(values)["evidence_sha256"] == CANONICAL

    body = evidence["function_body"]
    assert body["body_size"] == 164
    assert body["control_flow_graph_canonical_sha256"] == CFG
    assert [(item["start_rva"], item["size"]) for item in body["ranges"]] == [
        ("0x0039d580", 137),
        ("0x0039d61f", 27),
    ]
    assert len(body["reviewed_points"]) == 57
    assert body["direct_lua_calls"] == body["staged_lua_dispatches"] == []
    assert all(not row["call_rvas"] for row in body["call_r32_audit"])

    graph = evidence["control_flow_graph"]
    assert (graph["node_count"], graph["edge_count"]) == (57, 57)
    nodes = {row["rva"]: row for row in graph["nodes"]}
    assert nodes["0x0039d5bf"]["successor_rvas"] == ["0x0039d5c4"]
    assert nodes["0x0039d5c9"]["successor_rvas"] == [
        "0x0039d5cb",
        "0x0039d61f",
    ]
    assert nodes["0x0039d5e3"]["successor_rvas"] == [
        "0x0039d5e5",
        "0x0039d61f",
    ]
    assert nodes["0x0039d608"]["flow_kind"] == "terminal"
    assert nodes["0x0039d608"]["successor_rvas"] == []
    assert nodes["0x0039d639"]["flow_kind"] == "terminal"
    assert not any(row["flow_kind"] == "gap_boundary" for row in graph["nodes"])

    parents = evidence["pointer_target_parent_edges"]
    assert parents == values["residual"]["deferred_multirange_parent_rows"]
    outgoing = evidence["native_calls"]["outgoing_direct"]
    assert [row["instruction"]["rva"] for row in outgoing] == [
        "0x0039d5bf",
        "0x0039d5d9",
    ]
    assert [row["target_entry_rva"] for row in outgoing] == [
        "0x0039d640",
        "0x0039d530",
    ]

    native = evidence["native_calls"]
    assert native["opaque_indirect_controls"] == []
    assert all(not row["call_rvas"] for row in native["call_r32_audit"])
    pe = native["pe_address_operands"]
    assert len(pe) == 7
    assert [row["instruction"]["rva"] for row in pe] == [
        "0x0039d585",
        "0x0039d58a",
        "0x0039d59c",
        "0x0039d5bf",
        "0x0039d5c9",
        "0x0039d5d9",
        "0x0039d5e3",
    ]
    absolute = [row for row in pe if row["operand_class"] == "absolute_memory"]
    assert len(absolute) == 1
    assert (
        absolute[0]["instruction"]["rva"],
        absolute[0]["operand_index"],
        absolute[0]["operand_access"],
        absolute[0]["section_name"],
        absolute[0]["section_writable"],
    ) == ("0x0039d59c", 1, "read", ".data", True)
    assert all(
        row["operand_access"] == "none"
        for row in pe
        if row["operand_class"] == "immediate"
    )
    segment = native["segment_qualified_memory_syntax"]
    assert [row["instruction"]["rva"] for row in segment] == [
        "0x0039d58f",
        "0x0039d5aa",
        "0x0039d5fa",
        "0x0039d62b",
    ]
    assert [(row["operand_index"], row["operand_access"]) for row in segment] == [
        (1, "read"),
        (0, "write"),
        (0, "write"),
        (0, "write"),
    ]
    assert all(row["absolute_memory_class_excluded"] for row in segment)

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
        "reference_count": 1,
        "target_count": 1,
        "owner_count": 1,
        "target_owner_count": 1,
        "direct_call_count": 1,
        "other_address_count": 0,
        "memory_operand_count": 0,
    }
    assert scan["partition_sha256"] == {
        "owner_partition": target._OWNER_PARTITION_SHA256,
        "target_owner_partition": target._TARGET_OWNER_PARTITION_SHA256,
        "target_reference_partition": target._TARGET_REFERENCE_PARTITION_SHA256,
    }
    reference = scan["references"][0]
    parent = parents[0]
    assert reference["instruction_rva"] == parent["instruction"]["rva"]
    assert reference["instruction_sha256"] == parent["instruction"]["sha256"]
    assert reference["owner_entry_rva"] == parent["source_entry_rva"]
    assert reference["target_rva"] == parent["target_entry_rva"]
    assert any("semantic identity" in item for item in evidence["method"]["not_claimed"])
    assert any("un-atlased" in item for item in evidence["method"]["not_claimed"])


@pytest.mark.parametrize("path", LEAF_PATHS)
def test_every_nested_leaf_rejects(monkeypatch, values, path):
    changed = _replace(values["evidence"], path, _changed(_at(values["evidence"], path)))
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
        ("function_body", "ranges"),
        ("control_flow_graph", "nodes", 23, "successor_rvas"),
        ("native_calls", "pe_address_operands", 2, "operand_index"),
        ("native_calls", "segment_qualified_memory_syntax", 3, "operand_access"),
        ("whole_atlas_reference_scan", "references", 0, "operand_index"),
        ("summary", "schema_violations"),
    ],
)
def test_required_field_removal_rejects(monkeypatch, values, path):
    _reject_fast(monkeypatch, values, _remove(values["evidence"], path))


def test_parent_residual_cross_join_and_scan_join_reject(values):
    residual = copy.deepcopy(values["residual"])
    residual["deferred_multirange_parent_rows"][0]["instruction"]["sha256"] = "0" * 64
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError,
        match="parent join",
    ):
        target._parent_rows(values["pointer"], residual)

    scan = copy.deepcopy(values["evidence"]["whole_atlas_reference_scan"])
    scan["references"][0]["instruction_sha256"] = "0" * 64
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError,
        match="parent/reference join",
    ):
        target._parent_scan_join(
            values["evidence"]["pointer_target_parent_edges"], scan
        )


def test_exact_builder_requires_verified_direct_census(monkeypatch, values):
    seen = {}

    def fake(_executable, _direct, _facts, *, inventory):
        seen["inventory"] = inventory
        return {"status": "verified", "evidence_sha256": "0" * 64}

    monkeypatch.setattr(target, "validate_native_lua_direct_call_census", fake)
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError,
        match="direct-call exact prerequisite",
    ):
        target.build_native_query_handler_first_callee_pointer_target_multirange_static_boundary(
            EXE,
            *_common(values),
            inventory=values["inventory"],
        )
    assert seen["inventory"] is values["inventory"]


def test_exact_rebuild_and_validate(values):
    if not EXE.is_file():
        pytest.skip("sealed executable unavailable")
    rebuilt = target.build_native_query_handler_first_callee_pointer_target_multirange_static_boundary(
        EXE,
        *_common(values),
        inventory=values["inventory"],
    )
    assert rebuilt == values["evidence"]
    verification = target.validate_native_query_handler_first_callee_pointer_target_multirange_static_boundary(
        EXE,
        values["evidence"],
        *_common(values),
        inventory=values["inventory"],
    )
    assert verification["status"] == "verified"
    assert verification["evidence_sha256"] == CANONICAL


def _root(monkeypatch, temporary):
    info = temporary.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (temporary, temporary, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def _rendered(values):
    return target.encode_native_query_handler_first_callee_pointer_target_multirange_static_boundary(
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
        NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError,
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
        NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError,
        match="inherited root failure",
    ):
        cli._write_immutably(tmp_path / "other.json", rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode() + b" "


def test_cli_rejects_output_outside_program_root(tmp_path, monkeypatch, values):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    _root(monkeypatch, allowed)
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError,
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
        NativeQueryHandlerFirstCalleePointerTargetMultirangeStaticBoundaryError,
        match="final content validation",
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    if existing:
        assert output.read_bytes() == rendered.encode()
    else:
        assert not output.exists()
