"""Exact, label-only static boundary for the local query-new-handler helper."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_class_factory_chain import NativeLuaClassFactoryChainError, _validated_graphs
from src.observatory.native_lua_class_return_helper_chain import (
    NativeLuaClassReturnHelperChainError, _REGISTER_NAMES, _canonical_bytes,
    _canonical_sha256, _expected_point_record, _normalized_declared_edge,
    _source_identity, _expected_reference_scan, _whole_atlas_reference_scan,
    _enhanced_cfg, _with_edi_writes, _point_record, _call_r32_audit,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError, _array, _assert_publication_safe,
    _atlas_functions, _exact_keys, _hex, _mapping, _rva, _validate_json_tree,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_KIND, SUPPORTED_CAPSTONE_VERSION, NativeLuaDirectCallError,
    _decoder, _load_executable, validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_query_new_handler_static_boundary import (
    ANALYSIS_KIND as QUERY_KIND,
    _canonical_sha256 as _query_canonical_sha256,
)
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_query_new_handler_local_helper_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_QUERY = "742e341a855de34731177afd53b385c67fbd64f3d277fedf8ba6c8e9bbf61705"
_ENTRY = 0x0038BC51
_BODY = "00315b39ffe024b2d781b3d76bd5cdbbf45af50ee16d3d2fef11fb7f1c78e172"
_ATLAS = "1a8a5f349965dd80b224d1ccaaee4f57e7cd9b02a2ff52a132766f3a9fa2eab0"
_CFG = "248d530fb5189513119b2c55a07739a7b48bb2344cfb0ae9fb926263b3fec2a3"


class NativeQueryNewHandlerLocalHelperStaticBoundaryError(RuntimeError):
    """The sealed local-helper boundary could not be reproduced exactly."""


def _point(role: str, rva: int, encoded: str) -> dict[str, Any]:
    return {"role": role, "rva": rva, "encoded": bytes.fromhex(encoded), "api": None,
            "meaning": {"operation": "decoded_instruction", "source_semantic_names_assigned": False}}


_POINTS = (
    _point("instruction_00", 0x38BC51, "6a00"),
    _point("instruction_01", 0x38BC53, "e8b5cfffff"),
    _point("instruction_02", 0x38BC58, "59"),
    _point("instruction_03", 0x38BC59, "c3"),
)
_FUNCTION = {
    "role": "analysis_labeled_query_new_handler_local_helper_static_boundary",
    "entry_rva": _ENTRY, "body_size": 9, "body_sha256": _BODY,
    "cfg_canonical_sha256": _CFG, "direct_calls": [], "staged_dispatches": [],
    "call_r32": {}, "points": list(_POINTS),
    "semantic_facts": {"analysis_label": "FUN_0078bc51", "analysis_label_only": True,
                       "source_semantic_names_assigned": False,
                       "runtime_or_success_claimed": False},
}
_EDGE = (0x38BC53, "e8b5cfffff", 0x388C0D)
_METHOD = {
    "structural_boundary": "PE-free verification rebuilds all finite prerequisite, instruction, CFG, edge, and owner-partition records. Exact bytes and the full atlas scan require the sealed executable.",
    "not_claimed": [
        "helper purpose, unlock or lock semantics, ABI, argument meaning, success, state mutation, or normal return",
        "runtime reachability, invocation, order, frequency, or source identity",
        "behavior or identity of the opaque analysis-labeled native callee",
        "dynamic, computed, indirect, data, un-atlased, or Lua-side references",
    ],
}


def _same(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _facts_identity(facts: Mapping[str, Any]) -> dict[str, Any]:
    identity = _source_identity(facts, "pe_ghidra_program_facts", _FACTS, "program facts")
    summary = _mapping(facts.get("summary"), "program-facts summary")
    return {**identity, "function_count": summary.get("function_count"),
            "body_range_count": summary.get("body_range_count"),
            "function_body_bytes": summary.get("function_body_bytes")}


def _preflight(query: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]):
    identity = _mapping(facts.get("identity"), "program facts identity")
    if identity.get("executable_sha256") != _EXE:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("program facts are not the reviewed profile")
    if not _same(query.get("build_identity"), dict(identity)) or not _same(direct.get("build_identity"), dict(identity)):
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("prerequisite build identity differs")
    if _query_canonical_sha256(query) != _QUERY:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("query-new-handler prerequisite receipt differs")
    return (_facts_identity(facts), _source_identity(direct, DIRECT_KIND, _DIRECT, "direct calls"),
            _source_identity(query, QUERY_KIND, _QUERY, "query-new-handler boundary"))


def _profile(facts: Mapping[str, Any]) -> dict[str, Any]:
    refs = []
    for raw in _array(facts.get("ghidra_declared_direct_calls"), "declared direct calls"):
        edge = _mapping(raw, "declared direct call")
        if _rva(edge.get("target_entry_rva"), "target") == _ENTRY:
            site, target, owner = (_rva(edge.get(key), key) for key in ("instruction_rva", "target_rva", "source_entry_rva"))
            refs.append({"instruction_rva": site, "owner_entry_rva": owner, "target_rva": target,
                         "encoded": (b"\xe8" + int(target - (site + 5)).to_bytes(4, "little", signed=True)).hex(), "operand_index": 0})
    if len(refs) != 1 or refs[0]["instruction_rva"] != 0x38BC41 or refs[0]["owner_entry_rva"] != 0x38BC08:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("incoming local-helper profile differs")
    return {"executable_sha256": _EXE, "functions": [_FUNCTION], "literals": [], "native_edges": [], "target_references": refs}


def _scan(value: Mapping[str, Any], *, require_partition: bool) -> dict[str, Any]:
    scan = dict(_mapping(value, "reference scan")); aggregates = dict(_mapping(scan.get("aggregates"), "reference aggregates"))
    aggregates.pop("returned_callback_reference_count", None); aggregates.pop("alternate_owner_reference_count", None)
    scan["aggregates"] = aggregates
    expected_keys = {"target_rvas", "target_vas", "scope", "references", "aggregates"}
    if "owner_partition" in scan:
        expected_keys.add("owner_partition")
    _exact_keys(scan, expected_keys, "reference scan")
    refs = _array(scan.get("references"), "references")
    if len(refs) != 1 or aggregates != {"reference_count": 1, "direct_call_count": 1, "comparison_count": 0, "other_address_count": 0, "memory_operand_count": 0, "owner_count": 1}:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("reference partition differs")
    ref = _mapping(refs[0], "reference")
    _exact_keys(ref, {"instruction_rva", "instruction_size", "instruction_sha256", "owner_entry_rva", "owner_atlas_record_sha256", "target_rva", "target_atlas_record_sha256", "target_va", "operand_class", "operand_index", "use_class", "call_form", "ghidra_declared_direct_edge"}, "reference")
    if (ref.get("instruction_rva"), ref.get("owner_entry_rva"), ref.get("instruction_size"), ref.get("operand_index"), ref.get("operand_class"), ref.get("use_class"), ref.get("call_form")) != ("0x0038bc41", "0x0038bc08", 5, 0, "immediate", "direct_call", "x86_relative_near_call_e8") or ref.get("ghidra_declared_direct_edge") is None:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("incoming E8 record differs")
    if type(ref.get("owner_entry_rva")) is not str or type(ref.get("owner_atlas_record_sha256")) is not str:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("reference owner identity differs")
    owner = {"owner_entry_rva": ref["owner_entry_rva"], "owner_atlas_record_sha256": ref["owner_atlas_record_sha256"], "reference_count": 1}
    supplied = _array(scan.get("owner_partition", []), "owner partition")
    if require_partition and (len(supplied) != 1 or not _same(supplied, [owner])):
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("owner partition differs")
    if supplied:
        _exact_keys(_mapping(supplied[0], "owner partition record"), set(owner), "owner partition record")
    scan["owner_partition"] = [owner]
    return scan


def _expected_scan(facts: Mapping[str, Any], direct: Mapping[str, Any]) -> dict[str, Any]:
    return _scan(_expected_reference_scan(facts, direct, _profile(facts)), require_partition=False)


def _records(data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]):
    import capstone
    import capstone.x86_const as x86
    from src.observatory.native_lua_cclosure_setfield_publications import _decode_range
    function = _atlas_functions(facts).get(_ENTRY)
    if function is None or function.get("body_size") != 9 or function.get("body_sha256") != _BODY or atlas_record_sha256(function) != _ATLAS:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("target atlas identity differs")
    decoder.detail = True
    instructions = _decode_range(data, image, _ENTRY, 9, decoder)
    if hashlib.sha256(b"".join(bytes(item.bytes) for item in instructions)).hexdigest() != _BODY:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("target bytes differ")
    graph = _with_edi_writes(_enhanced_cfg(instructions, image.image_base, (_ENTRY, 9), capstone, x86), instructions, x86)
    graph["caller_entry_rva"] = _hex(_ENTRY)
    if _canonical_sha256(graph) != _CFG:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("target CFG differs")
    by_rva = {item.address - image.image_base: item for item in instructions}
    points = [_point_record(by_rva[spec["rva"]], image.image_base, spec) for spec in _POINTS]
    body = {"role": _FUNCTION["role"], "entry_rva": _hex(_ENTRY), "atlas_record_sha256": _ATLAS,
            "body_size": 9, "body_sha256": _BODY, "range_start_rva": _hex(_ENTRY), "range_size": 9,
            "control_flow_graph_canonical_sha256": _CFG, "reviewed_points": points,
            "direct_lua_calls": [], "staged_lua_dispatches": [],
            "call_r32_audit": _call_r32_audit(instructions, _FUNCTION), "register_call_partition_complete": True,
            "semantic_facts": dict(_FUNCTION["semantic_facts"])}
    return [body], [graph]


def _native(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions = _atlas_functions(facts); source = functions.get(_ENTRY)
    declared = {_rva(_mapping(item, "edge").get("instruction_rva"), "site"): _mapping(item, "edge") for item in _array(facts.get("ghidra_declared_direct_calls"), "edges")}
    site, encoded, target = _EDGE; edge, callee = declared.get(site), functions.get(target)
    if source is None or atlas_record_sha256(source) != _ATLAS or edge is None or callee is None or _rva(edge.get("source_entry_rva"), "source") != _ENTRY or _rva(edge.get("target_entry_rva"), "target") != target:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("outgoing opaque edge differs")
    return [{"role": "opaque_native_direct_edge", "source_entry_rva": _hex(_ENTRY), "source_atlas_record_sha256": _ATLAS,
             "source_body_size": 9, "source_body_sha256": _BODY,
             "instruction": {"rva": _hex(site), "size": 5, "sha256": hashlib.sha256(bytes.fromhex(encoded)).hexdigest()},
             "target_entry_rva": _hex(target), "target_rva": _hex(target), "target_atlas_record_sha256": atlas_record_sha256(callee),
             "target_body_size": callee.get("body_size"), "target_body_sha256": callee.get("body_sha256"),
             "ghidra_declared_direct_edge": _normalized_declared_edge(edge), "label_source": "analysis_or_default", "callee_behavior_opaque": True}]


def _predecessor(query: Mapping[str, Any], scan: Mapping[str, Any]) -> dict[str, Any]:
    matches = [dict(_mapping(item, "query edge")) for item in _array(_mapping(query.get("native_calls"), "query calls").get("direct"), "query direct calls") if _rva(_mapping(item, "query edge").get("source_entry_rva"), "source") == 0x38BC08 and _rva(_mapping(item, "query edge").get("target_entry_rva"), "target") == _ENTRY and _rva(_mapping(_mapping(item, "query edge").get("instruction"), "instruction").get("rva"), "site") == 0x38BC41]
    if len(matches) != 1:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("query predecessor differs")
    edge, ref = matches[0], _mapping(_array(scan.get("references"), "references")[0], "reference")
    instruction = _mapping(edge.get("instruction"), "predecessor instruction")
    if (ref.get("instruction_size"), ref.get("instruction_sha256")) != (instruction.get("size"), instruction.get("sha256")) or ref.get("owner_atlas_record_sha256") != edge.get("source_atlas_record_sha256") or ref.get("target_atlas_record_sha256") != edge.get("target_atlas_record_sha256") or not _same(ref.get("ghidra_declared_direct_edge"), edge.get("ghidra_declared_direct_edge")):
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("predecessor scan join differs")
    return edge


def _decoder_contract() -> dict[str, Any]:
    return {"name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION, "architecture": "x86", "mode_bits": 32, "sealed_instruction_count": 4, "register_call_encoding_audit": [{"register": register, "encoding": f"ff{0xd0 + index:02x}"} for index, register in enumerate(_REGISTER_NAMES)]}


def _expected_body(facts: Mapping[str, Any]) -> dict[str, Any]:
    if _atlas_functions(facts).get(_ENTRY) is None:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("target absent")
    return {"role": _FUNCTION["role"], "entry_rva": _hex(_ENTRY), "atlas_record_sha256": _ATLAS, "body_size": 9, "body_sha256": _BODY, "range_start_rva": _hex(_ENTRY), "range_size": 9, "control_flow_graph_canonical_sha256": _CFG, "reviewed_points": [_expected_point_record(item) for item in _POINTS], "direct_lua_calls": [], "staged_lua_dispatches": [], "call_r32_audit": [{"register": register, "call_rvas": []} for register in _REGISTER_NAMES], "register_call_partition_complete": True, "semantic_facts": _FUNCTION["semantic_facts"]}


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {"reviewed_query_new_handler_local_helper_count": 1, "reviewed_query_new_handler_local_helper_bytes": 9, "sealed_instruction_count": 4, "sealed_control_flow_graph_count": 1, "sealed_control_flow_graph_node_count": 4, "sealed_control_flow_graph_edge_count": 3, "direct_lua_call_count": 0, "staged_lua_dispatch_count": 0, "call_r32_count": 0, "literal_count": 0, "native_edge_count": 1, "query_predecessor_edge_count": 1, "target_reference_count": 1, "target_reference_direct_call_count": 1, "target_reference_comparison_count": 0, "target_reference_other_address_count": 0, "target_reference_memory_operand_count": 0, "target_reference_owner_count": 1, "schema_violations": 0}


def build_native_query_new_handler_local_helper_static_boundary(executable: Path, query_new_handler_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    try:
        for value, label in ((query_new_handler_static_boundary, "query boundary"), (direct_calls, "direct calls"), (program_facts, "facts"), (inventory, "inventory")):
            _validate_json_tree(value, label)
        receipt = validate_native_lua_direct_call_census(executable, direct_calls, program_facts, inventory=inventory)
        if receipt.get("status") != "verified" or receipt.get("evidence_sha256") != _DIRECT:
            raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("direct-call prerequisite differs")
        atlas, direct, query = _preflight(query_new_handler_static_boundary, direct_calls, program_facts)
        data, image, digest = _load_executable(executable)
        if digest != _EXE:
            raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("executable differs")
        decoder, _ = _decoder(); bodies, graphs = _records(data, image, decoder, program_facts)
        scan = _scan(_whole_atlas_reference_scan(data, image, decoder, program_facts, direct_calls, _profile(program_facts)), require_partition=False)
        result = {"schema_version": SCHEMA_VERSION, "analysis_kind": ANALYSIS_KIND, "build_identity": dict(_mapping(program_facts.get("identity"), "identity")), "atlas": atlas, "direct_call_census": direct, "query_new_handler_static_boundary": query, "query_predecessor_edge": _predecessor(query_new_handler_static_boundary, scan), "decoder": _decoder_contract(), "function_bodies": bodies, "control_flow_graphs": graphs, "native_edges": _native(program_facts), "whole_atlas_reference_scan": scan, "method": _METHOD}
        result["summary"] = _summary(result); _assert_publication_safe(result)
        if _load_executable(executable)[2] != digest:
            raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("executable changed")
        validate_native_query_new_handler_local_helper_static_boundary_structure(result, query_new_handler_static_boundary, direct_calls, program_facts)
        return result
    except NativeQueryNewHandlerLocalHelperStaticBoundaryError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassFactoryChainError, NativeLuaClassReturnHelperChainError, PEAnchorError, OSError) as exc:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError(str(exc)) from exc


def validate_native_query_new_handler_local_helper_static_boundary_structure(evidence: Mapping[str, Any], query_new_handler_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any]) -> dict[str, Any]:
    try:
        for value, label in ((evidence, "evidence"), (query_new_handler_static_boundary, "query boundary"), (direct_calls, "direct calls"), (program_facts, "facts")):
            _validate_json_tree(value, label)
        receipt = validate_native_lua_direct_call_structure(direct_calls, program_facts)
        if receipt.get("status") != "structurally_verified" or receipt.get("evidence_sha256") != _DIRECT:
            raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("direct-call prerequisite differs")
        atlas, direct, query = _preflight(query_new_handler_static_boundary, direct_calls, program_facts); evidence = _mapping(evidence, "evidence")
        _exact_keys(evidence, {"schema_version", "analysis_kind", "build_identity", "atlas", "direct_call_census", "query_new_handler_static_boundary", "query_predecessor_edge", "decoder", "function_bodies", "control_flow_graphs", "native_edges", "whole_atlas_reference_scan", "method", "summary"}, "evidence")
        if type(evidence.get("schema_version")) is not int or evidence.get("schema_version") != SCHEMA_VERSION or evidence.get("analysis_kind") != ANALYSIS_KIND:
            raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("schema differs")
        if not all((_same(evidence.get("build_identity"), dict(_mapping(program_facts.get("identity"), "identity"))), _same(evidence.get("atlas"), atlas), _same(evidence.get("direct_call_census"), direct), _same(evidence.get("query_new_handler_static_boundary"), query), _same(evidence.get("decoder"), _decoder_contract()), _same(evidence.get("method"), _METHOD))):
            raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("pinned prerequisite differs")
        bodies = _array(evidence.get("function_bodies"), "bodies")
        if len(bodies) != 1 or not _same(bodies[0], _expected_body(program_facts)):
            raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("body differs")
        graph = _validated_graphs({"control_flow_graphs": evidence.get("control_flow_graphs")}, _atlas_functions(program_facts))
        if set(graph) != {_ENTRY} or _canonical_sha256(graph[_ENTRY][0]) != _CFG or graph[_ENTRY][0].get("node_count") != 4 or graph[_ENTRY][0].get("edge_count") != 3:
            raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("CFG differs")
        scan = _scan(_mapping(evidence.get("whole_atlas_reference_scan"), "scan"), require_partition=True)
        if not _same(scan, _expected_scan(program_facts, direct_calls)) or not _same(evidence.get("native_edges"), _native(program_facts)) or not _same(evidence.get("query_predecessor_edge"), _predecessor(query_new_handler_static_boundary, scan)) or not _same(evidence.get("summary"), _summary(evidence)):
            raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("cross-check differs")
        _assert_publication_safe(evidence)
        return {"schema_version": SCHEMA_VERSION, "analysis_kind": STRUCTURE_VERIFICATION_KIND, "status": "structurally_verified", "build_identity": dict(evidence["build_identity"]), "evidence_sha256": _canonical_sha256(evidence), "summary": dict(evidence["summary"])}
    except NativeQueryNewHandlerLocalHelperStaticBoundaryError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassFactoryChainError, NativeLuaClassReturnHelperChainError) as exc:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError(str(exc)) from exc


def validate_native_query_new_handler_local_helper_static_boundary(executable: Path, evidence: Mapping[str, Any], query_new_handler_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    rebuilt = build_native_query_new_handler_local_helper_static_boundary(executable, query_new_handler_static_boundary, direct_calls, program_facts, inventory=inventory)
    if not _same(evidence, rebuilt):
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError("evidence differs from exact rebuild")
    return {"schema_version": SCHEMA_VERSION, "analysis_kind": VERIFICATION_KIND, "status": "verified", "build_identity": dict(rebuilt["build_identity"]), "evidence_sha256": _canonical_sha256(rebuilt), "summary": dict(rebuilt["summary"])}


def encode_native_query_new_handler_local_helper_static_boundary(value: Mapping[str, Any]) -> str:
    try:
        _validate_json_tree(value)
        return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    except NativeLuaCClosurePublicationError as exc:
        raise NativeQueryNewHandlerLocalHelperStaticBoundaryError(str(exc)) from exc
