"""Exact, relationship-defined static boundary for the query-handler second callee."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_class_factory_chain import NativeLuaClassFactoryChainError, _validated_graphs
from src.observatory.native_lua_class_return_helper_chain import (
    NativeLuaClassReturnHelperChainError, _REGISTER_NAMES, _call_r32_audit,
    _canonical_bytes, _canonical_sha256, _enhanced_cfg, _expected_point_record,
    _expected_reference_scan, _point_record, _source_identity, _whole_atlas_reference_scan,
    _with_edi_writes,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError, _array, _assert_publication_safe, _atlas_functions,
    _exact_keys, _hex, _mapping, _rva, _validate_json_tree,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_KIND, SUPPORTED_CAPSTONE_VERSION, NativeLuaDirectCallError,
    _decoder, _load_executable, validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_query_new_handler_static_boundary import (
    ANALYSIS_KIND as QUERY_HANDLER_KIND, _canonical_sha256 as _query_handler_canonical_sha256,
)
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_query_handler_second_callee_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_QUERY_HANDLER = "742e341a855de34731177afd53b385c67fbd64f3d277fedf8ba6c8e9bbf61705"
_ENTRY = 0x388BC5
_BODY = "69b4aa2f4b6af7246c4b83b20a5dd4f3129a2a2116800a974709e84e0b687c8e"
_ATLAS = "9ce652f9a4c358e2a2a09b383c3f506e363f169bdcbf11e15ea147c1d7c7bc38"
_CFG = "dca310d5590e06f780f360c256894dac6cdabb305dc1a62848cbd0f16a643e20"
_PREDECESSOR = (0x38BC1A, "e8a6efffff", _ENTRY)


class NativeQueryHandlerSecondCalleeStaticBoundaryError(RuntimeError):
    """The sealed relationship-defined callee boundary cannot be reproduced."""

def _point(role: str, rva: int, encoded: str) -> dict[str, Any]:
    return {"role": role, "rva": rva, "encoded": bytes.fromhex(encoded), "api": None,
            "meaning": {"operation": "decoded_instruction", "source_semantic_names_assigned": False}}


_POINTS = tuple(_point(f"instruction_{index:02d}", rva, encoded) for index, (rva, encoded) in enumerate((
    (0x388BC5, "8bff"), (0x388BC7, "55"), (0x388BC8, "8bec"),
    (0x388BCA, "6b450818"), (0x388BCE, "05a8708b00"), (0x388BD3, "50"),
    (0x388BD4, "ff1584607d00"), (0x388BDA, "5d"), (0x388BDB, "c3"),
)))
_FUNCTION = {
    "role": "relationship_defined_query_handler_second_callee_static_boundary", "entry_rva": _ENTRY,
    "body_size": 23, "body_sha256": _BODY, "cfg_canonical_sha256": _CFG,
    "direct_calls": [], "staged_dispatches": [], "call_r32": {}, "points": list(_POINTS),
    "semantic_facts": {"analysis_label": "___acrt_lock", "analysis_label_only": True,
                       "relationship_defined_by_predecessor_edge": True,
                       "source_semantic_names_assigned": False, "runtime_or_success_claimed": False},
}
_METHOD = {
    "structural_boundary": "PE-free validation rebuilds every finite prerequisite, instruction, CFG, import-binding, pointer-span, predecessor, and owner-partition record. Exact bytes and the whole-atlas reference traversal require the sealed executable.",
    "not_claimed": [
        "callee purpose, lock or synchronization semantics, ABI, argument meaning, state mutation, success, or normal return",
        "runtime reachability, invocation, order, frequency, source identity, imported-function execution, or imported-function effect",
        "contents or semantics of absolute memory operands or their pointed-to data",
        "dynamic, computed, indirect, data, un-atlased, or Lua-side references",
    ],
}


def _same(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _facts_identity(facts: Mapping[str, Any]) -> dict[str, Any]:
    identity = _source_identity(facts, "pe_ghidra_program_facts", _FACTS, "program facts")
    summary = _mapping(facts.get("summary"), "program facts summary")
    return {**identity, "function_count": summary.get("function_count"),
            "body_range_count": summary.get("body_range_count"),
            "function_body_bytes": summary.get("function_body_bytes")}


def _preflight(query_handler: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]):
    identity = _mapping(facts.get("identity"), "program facts identity")
    if identity.get("executable_sha256") != _EXE:
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("program facts are not the reviewed profile")
    if not _same(query_handler.get("build_identity"), dict(identity)) or not _same(direct.get("build_identity"), dict(identity)):
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("prerequisite build identity differs")
    if _query_handler_canonical_sha256(query_handler) != _QUERY_HANDLER:
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("query-handler prerequisite receipt differs")
    return (_facts_identity(facts), _source_identity(direct, DIRECT_KIND, _DIRECT, "direct calls"),
            _source_identity(query_handler, QUERY_HANDLER_KIND, _QUERY_HANDLER, "query-handler boundary"))


def _profile(facts: Mapping[str, Any]) -> dict[str, Any]:
    refs = []
    for raw in _array(facts.get("ghidra_declared_direct_calls"), "declared direct calls"):
        edge = _mapping(raw, "declared direct call")
        if _rva(edge.get("target_entry_rva"), "target") == _ENTRY:
            site, target, owner = (_rva(edge.get(key), key) for key in ("instruction_rva", "target_rva", "source_entry_rva"))
            refs.append({"instruction_rva": site, "owner_entry_rva": owner, "target_rva": target,
                         "encoded": (b"\xe8" + int(target - (site + 5)).to_bytes(4, "little", signed=True)).hex(), "operand_index": 0})
    refs.sort(key=lambda item: item["instruction_rva"])
    if len(refs) != 26 or len({item["owner_entry_rva"] for item in refs}) != 26:
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("declared incoming owner partition differs")
    if not any((item["instruction_rva"], item["owner_entry_rva"]) == (0x38BC1A, 0x38BC08) for item in refs):
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("relationship predecessor absent")
    return {"executable_sha256": _EXE, "functions": [_FUNCTION], "literals": [], "native_edges": [], "target_references": refs}


def _owner_partition(refs: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    partition = [{"owner_entry_rva": item["owner_entry_rva"],
                  "owner_atlas_record_sha256": item["owner_atlas_record_sha256"], "reference_count": 1}
                 for item in refs]
    if len(partition) != 26 or len({item["owner_entry_rva"] for item in partition}) != 26:
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("owner partition differs")
    return partition


def _scan(value: Mapping[str, Any], *, require_partition: bool) -> dict[str, Any]:
    scan = dict(_mapping(value, "reference scan")); aggregates = dict(_mapping(scan.get("aggregates"), "reference aggregates"))
    aggregates.pop("returned_callback_reference_count", None); aggregates.pop("alternate_owner_reference_count", None)
    scan["aggregates"] = aggregates
    expected_keys = {"target_rvas", "target_vas", "scope", "references", "aggregates"}
    if "owner_partition" in scan:
        expected_keys.add("owner_partition")
    _exact_keys(scan, expected_keys, "reference scan")
    refs = _array(scan.get("references"), "references")
    expected_aggregates = {"reference_count": 26, "direct_call_count": 26, "comparison_count": 0,
                           "other_address_count": 0, "memory_operand_count": 0, "owner_count": 26}
    if len(refs) != 26 or aggregates != expected_aggregates:
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("reference partition differs")
    for ref in refs:
        item = _mapping(ref, "reference")
        _exact_keys(item, {"instruction_rva", "instruction_size", "instruction_sha256", "owner_entry_rva",
                           "owner_atlas_record_sha256", "target_rva", "target_atlas_record_sha256", "target_va",
                           "operand_class", "operand_index", "use_class", "call_form", "ghidra_declared_direct_edge"}, "reference")
        if (item.get("instruction_size"), item.get("operand_index"), item.get("operand_class"), item.get("use_class"), item.get("call_form")) != (5, 0, "immediate", "direct_call", "x86_relative_near_call_e8"):
            raise NativeQueryHandlerSecondCalleeStaticBoundaryError("incoming reference syntax differs")
        if type(item.get("owner_entry_rva")) is not str or type(item.get("owner_atlas_record_sha256")) is not str or item.get("ghidra_declared_direct_edge") is None:
            raise NativeQueryHandlerSecondCalleeStaticBoundaryError("incoming reference owner identity differs")
    partition = _owner_partition(refs)
    supplied = _array(scan.get("owner_partition", []), "owner partition")
    for item in supplied:
        _exact_keys(_mapping(item, "owner partition record"), {"owner_entry_rva", "owner_atlas_record_sha256", "reference_count"}, "owner partition record")
    if require_partition and ("owner_partition" not in scan or not _same(supplied, partition)):
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("owner partition differs")
    scan["owner_partition"] = partition
    return scan


def _expected_scan(facts: Mapping[str, Any], direct: Mapping[str, Any]) -> dict[str, Any]:
    expected = _expected_reference_scan(facts, direct, _profile(facts))
    expected["owner_partition"] = _owner_partition(expected["references"])
    return _scan(expected, require_partition=True)


def _section(image: Any, rva: int, *, name: str, characteristics: str, writable: bool, backed: bool) -> None:
    section = next((item for item in image.sections if item.virtual_address <= rva < item.virtual_address + item.virtual_size), None)
    if section is None or (section.name, _hex(section.characteristics), bool(section.characteristics & 0x80000000), image.rva_to_file_offset(rva) is not None) != (name, characteristics, writable, backed):
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("absolute operand section span differs")


def _absolute_records(image: Any | None) -> list[dict[str, Any]]:
    records = [
        {"role": "opaque_absolute_add_immediate_syntax", "instruction": {"rva": "0x00388bce", "size": 5, "sha256": hashlib.sha256(bytes.fromhex("05a8708b00")).hexdigest()}, "operand_va": "0x008b70a8", "operand_rva": "0x004b70a8", "section_name": ".data", "section_characteristics": "0xc0000040", "section_writable": True, "file_backed": False, "contents_or_semantics_opaque": True},
        {"role": "named_pe_import_absolute_memory_call_syntax", "instruction": {"rva": "0x00388bd4", "size": 6, "sha256": hashlib.sha256(bytes.fromhex("ff1584607d00")).hexdigest()}, "operand_va": "0x007d6084", "operand_rva": "0x003d6084", "section_name": ".rdata", "section_characteristics": "0x40000040", "section_writable": False, "file_backed": True, "pe_import_binding": {"evidence_class": "fact", "library": "KERNEL32.dll", "name": "EnterCriticalSection", "hint": 238, "ordinal": None, "iat_rva": "0x003d6084"}, "contents_or_semantics_opaque": True},
    ]
    if image is not None:
        _section(image, 0x4B70A8, name=".data", characteristics="0xc0000040", writable=True, backed=False)
        _section(image, 0x3D6084, name=".rdata", characteristics="0x40000040", writable=False, backed=True)
        matches = [dict(_mapping(raw, "PE import")) for raw in image.imports() if raw.get("iat_rva") == "0x003d6084"]
        if matches != [{"evidence_class": "fact", "library": "KERNEL32.dll", "name": "EnterCriticalSection", "ordinal": None, "hint": 238, "iat_rva": "0x003d6084"}]:
            raise NativeQueryHandlerSecondCalleeStaticBoundaryError("PE import binding differs")
    return records


def _records(data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]):
    import capstone
    import capstone.x86_const as x86
    from src.observatory.native_lua_cclosure_setfield_publications import _decode_range
    function = _atlas_functions(facts).get(_ENTRY)
    if function is None or function.get("body_size") != 23 or function.get("body_sha256") != _BODY or atlas_record_sha256(function) != _ATLAS:
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("target atlas identity differs")
    decoder.detail = True; instructions = _decode_range(data, image, _ENTRY, 23, decoder)
    if hashlib.sha256(b"".join(bytes(item.bytes) for item in instructions)).hexdigest() != _BODY:
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("target bytes differ")
    graph = _with_edi_writes(_enhanced_cfg(instructions, image.image_base, (_ENTRY, 23), capstone, x86), instructions, x86)
    graph["caller_entry_rva"] = _hex(_ENTRY)
    if _canonical_sha256(graph) != _CFG:
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("target CFG differs")
    by_rva = {item.address - image.image_base: item for item in instructions}
    body = {"role": _FUNCTION["role"], "entry_rva": _hex(_ENTRY), "atlas_record_sha256": _ATLAS,
            "body_size": 23, "body_sha256": _BODY, "range_start_rva": _hex(_ENTRY), "range_size": 23,
            "control_flow_graph_canonical_sha256": _CFG,
            "reviewed_points": [_point_record(by_rva[spec["rva"]], image.image_base, spec) for spec in _POINTS],
            "direct_lua_calls": [], "staged_lua_dispatches": [], "call_r32_audit": _call_r32_audit(instructions, _FUNCTION),
            "register_call_partition_complete": True, "semantic_facts": dict(_FUNCTION["semantic_facts"])}
    return [body], [graph]


def _predecessor(query_handler: Mapping[str, Any], scan: Mapping[str, Any]) -> dict[str, Any]:
    direct = _array(_mapping(query_handler.get("native_calls"), "query-handler native calls").get("direct"), "query-handler native edges")
    matches = [dict(_mapping(item, "predecessor edge")) for item in direct if
               ( _rva(_mapping(item, "predecessor edge").get("source_entry_rva"), "source"),
                 _rva(_mapping(_mapping(item, "predecessor edge").get("instruction"), "instruction").get("rva"), "site"),
                 _rva(_mapping(item, "predecessor edge").get("target_entry_rva"), "target")) == (0x38BC08, _PREDECESSOR[0], _ENTRY)]
    if len(matches) != 1:
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("relationship predecessor differs")
    edge = matches[0]
    ref = next((item for item in _array(scan.get("references"), "references") if item["instruction_rva"] == "0x0038bc1a"), None)
    instruction = _mapping(edge.get("instruction"), "predecessor instruction")
    if ref is None or (ref.get("instruction_rva"), ref.get("owner_entry_rva"), ref.get("instruction_size"), ref.get("instruction_sha256"), ref.get("operand_class"), ref.get("use_class"), ref.get("call_form")) != ("0x0038bc1a", "0x0038bc08", instruction.get("size"), instruction.get("sha256"), "immediate", "direct_call", "x86_relative_near_call_e8") or ref.get("owner_atlas_record_sha256") != edge.get("source_atlas_record_sha256") or ref.get("target_atlas_record_sha256") != edge.get("target_atlas_record_sha256") or not _same(ref.get("ghidra_declared_direct_edge"), edge.get("ghidra_declared_direct_edge")):
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("relationship predecessor scan join differs")
    return edge


def _decoder_contract() -> dict[str, Any]:
    return {"name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION, "architecture": "x86", "mode_bits": 32,
            "sealed_instruction_count": 9,
            "register_call_encoding_audit": [{"register": name, "encoding": f"ff{0xd0 + index:02x}"} for index, name in enumerate(_REGISTER_NAMES)]}


def _expected_body(facts: Mapping[str, Any]) -> dict[str, Any]:
    if _atlas_functions(facts).get(_ENTRY) is None:
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("target absent")
    return {"role": _FUNCTION["role"], "entry_rva": _hex(_ENTRY), "atlas_record_sha256": _ATLAS, "body_size": 23,
            "body_sha256": _BODY, "range_start_rva": _hex(_ENTRY), "range_size": 23,
            "control_flow_graph_canonical_sha256": _CFG, "reviewed_points": [_expected_point_record(item) for item in _POINTS],
            "direct_lua_calls": [], "staged_lua_dispatches": [],
            "call_r32_audit": [{"register": name, "call_rvas": []} for name in _REGISTER_NAMES],
            "register_call_partition_complete": True, "semantic_facts": _FUNCTION["semantic_facts"]}


def _summary(_: Mapping[str, Any]) -> dict[str, Any]:
    return {"reviewed_query_handler_second_callee_count": 1, "reviewed_query_handler_second_callee_bytes": 23,
            "sealed_instruction_count": 9, "sealed_control_flow_graph_count": 1,
            "sealed_control_flow_graph_node_count": 9, "sealed_control_flow_graph_edge_count": 8,
            "direct_lua_call_count": 0, "staged_lua_dispatch_count": 0, "call_r32_count": 0, "literal_count": 0,
            "native_direct_edge_count": 0, "absolute_operand_syntax_count": 2, "named_pe_import_binding_count": 1,
            "query_handler_predecessor_edge_count": 1, "target_reference_count": 26,
            "target_reference_direct_call_count": 26, "target_reference_comparison_count": 0,
            "target_reference_other_address_count": 0, "target_reference_memory_operand_count": 0,
            "target_reference_owner_count": 26, "schema_violations": 0}


def build_native_query_handler_second_callee_static_boundary(executable: Path, query_handler_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    try:
        for value, label in ((query_handler_static_boundary, "query handler"), (direct_calls, "direct calls"), (program_facts, "facts"), (inventory, "inventory")):
            _validate_json_tree(value, label)
        receipt = validate_native_lua_direct_call_census(executable, direct_calls, program_facts, inventory=inventory)
        if receipt.get("status") != "verified" or receipt.get("evidence_sha256") != _DIRECT:
            raise NativeQueryHandlerSecondCalleeStaticBoundaryError("direct-call prerequisite differs")
        atlas, direct, query_handler = _preflight(query_handler_static_boundary, direct_calls, program_facts)
        data, image, digest = _load_executable(executable)
        if digest != _EXE:
            raise NativeQueryHandlerSecondCalleeStaticBoundaryError("executable differs")
        decoder, _ = _decoder(); bodies, graphs = _records(data, image, decoder, program_facts)
        scan = _scan(_whole_atlas_reference_scan(data, image, decoder, program_facts, direct_calls, _profile(program_facts)), require_partition=False)
        result = {"schema_version": SCHEMA_VERSION, "analysis_kind": ANALYSIS_KIND,
                  "build_identity": dict(_mapping(program_facts.get("identity"), "identity")), "atlas": atlas,
                  "direct_call_census": direct, "query_handler_static_boundary": query_handler,
                  "query_handler_second_callee_predecessor_edge": _predecessor(query_handler_static_boundary, scan),
                  "decoder": _decoder_contract(), "function_bodies": bodies, "control_flow_graphs": graphs,
                  "native_calls": {"direct": [], "absolute_pointer_or_memory_syntax": _absolute_records(image)},
                  "whole_atlas_reference_scan": scan, "method": _METHOD}
        result["summary"] = _summary(result); _assert_publication_safe(result)
        if _load_executable(executable)[2] != digest:
            raise NativeQueryHandlerSecondCalleeStaticBoundaryError("executable changed")
        validate_native_query_handler_second_callee_static_boundary_structure(result, query_handler_static_boundary, direct_calls, program_facts)
        return result
    except NativeQueryHandlerSecondCalleeStaticBoundaryError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassFactoryChainError, NativeLuaClassReturnHelperChainError, PEAnchorError, OSError) as exc:
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError(str(exc)) from exc


def validate_native_query_handler_second_callee_static_boundary_structure(evidence: Mapping[str, Any], query_handler_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any]) -> dict[str, Any]:
    try:
        for value, label in ((evidence, "evidence"), (query_handler_static_boundary, "query handler"), (direct_calls, "direct calls"), (program_facts, "facts")):
            _validate_json_tree(value, label)
        receipt = validate_native_lua_direct_call_structure(direct_calls, program_facts)
        if receipt.get("status") != "structurally_verified" or receipt.get("evidence_sha256") != _DIRECT:
            raise NativeQueryHandlerSecondCalleeStaticBoundaryError("direct-call prerequisite differs")
        atlas, direct, query_handler = _preflight(query_handler_static_boundary, direct_calls, program_facts); evidence = _mapping(evidence, "evidence")
        _exact_keys(evidence, {"schema_version", "analysis_kind", "build_identity", "atlas", "direct_call_census", "query_handler_static_boundary", "query_handler_second_callee_predecessor_edge", "decoder", "function_bodies", "control_flow_graphs", "native_calls", "whole_atlas_reference_scan", "method", "summary"}, "evidence")
        if type(evidence.get("schema_version")) is not int or evidence.get("schema_version") != SCHEMA_VERSION or evidence.get("analysis_kind") != ANALYSIS_KIND:
            raise NativeQueryHandlerSecondCalleeStaticBoundaryError("schema differs")
        if not all((_same(evidence.get("build_identity"), dict(_mapping(program_facts.get("identity"), "identity"))), _same(evidence.get("atlas"), atlas), _same(evidence.get("direct_call_census"), direct), _same(evidence.get("query_handler_static_boundary"), query_handler), _same(evidence.get("decoder"), _decoder_contract()), _same(evidence.get("method"), _METHOD))):
            raise NativeQueryHandlerSecondCalleeStaticBoundaryError("pinned prerequisite differs")
        bodies = _array(evidence.get("function_bodies"), "bodies")
        if len(bodies) != 1 or not _same(bodies[0], _expected_body(program_facts)):
            raise NativeQueryHandlerSecondCalleeStaticBoundaryError("body differs")
        graphs = _validated_graphs({"control_flow_graphs": evidence.get("control_flow_graphs")}, _atlas_functions(program_facts))
        if set(graphs) != {_ENTRY} or _canonical_sha256(graphs[_ENTRY][0]) != _CFG or graphs[_ENTRY][0].get("node_count") != 9 or graphs[_ENTRY][0].get("edge_count") != 8:
            raise NativeQueryHandlerSecondCalleeStaticBoundaryError("CFG differs")
        nodes = {_rva(item.get("rva"), "CFG node rva"): item for item in _array(graphs[_ENTRY][0].get("nodes"), "CFG nodes")}
        for point in _array(bodies[0].get("reviewed_points"), "reviewed points"):
            node = nodes.get(_rva(point.get("rva"), "point rva"))
            if node is None or (point.get("size"), point.get("sha256")) != (node.get("size"), node.get("sha256")):
                raise NativeQueryHandlerSecondCalleeStaticBoundaryError("reviewed point CFG join differs")
        scan = _scan(_mapping(evidence.get("whole_atlas_reference_scan"), "scan"), require_partition=True)
        expected_calls = {"direct": [], "absolute_pointer_or_memory_syntax": _absolute_records(None)}
        if not _same(scan, _expected_scan(program_facts, direct_calls)) or not _same(evidence.get("native_calls"), expected_calls) or not _same(evidence.get("query_handler_second_callee_predecessor_edge"), _predecessor(query_handler_static_boundary, scan)) or not _same(evidence.get("summary"), _summary(evidence)):
            raise NativeQueryHandlerSecondCalleeStaticBoundaryError("cross-check differs")
        _assert_publication_safe(evidence)
        return {"schema_version": SCHEMA_VERSION, "analysis_kind": STRUCTURE_VERIFICATION_KIND,
                "status": "structurally_verified", "build_identity": dict(evidence["build_identity"]),
                "evidence_sha256": _canonical_sha256(evidence), "summary": dict(evidence["summary"])}
    except NativeQueryHandlerSecondCalleeStaticBoundaryError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassFactoryChainError, NativeLuaClassReturnHelperChainError) as exc:
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError(str(exc)) from exc


def validate_native_query_handler_second_callee_static_boundary(executable: Path, evidence: Mapping[str, Any], query_handler_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    rebuilt = build_native_query_handler_second_callee_static_boundary(executable, query_handler_static_boundary, direct_calls, program_facts, inventory=inventory)
    if not _same(evidence, rebuilt):
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError("evidence differs from exact rebuild")
    return {"schema_version": SCHEMA_VERSION, "analysis_kind": VERIFICATION_KIND, "status": "verified",
            "build_identity": dict(rebuilt["build_identity"]), "evidence_sha256": _canonical_sha256(rebuilt), "summary": dict(rebuilt["summary"])}


def encode_native_query_handler_second_callee_static_boundary(value: Mapping[str, Any]) -> str:
    try:
        _validate_json_tree(value)
        return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    except NativeLuaCClosurePublicationError as exc:
        raise NativeQueryHandlerSecondCalleeStaticBoundaryError(str(exc)) from exc
