"""Opaque, relationship-only static boundary for ``0x0035848f``.

The target is identified exclusively by the direct edge in the operator-new
receipt.  Analysis labels in the underlying program facts remain metadata; this
module makes no source-level, ABI, reachability, or behavioural assertion.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from capstone import CsError

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError,
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _decode_range,
    _hex,
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_class_return_helper_chain import (
    NativeLuaClassReturnHelperChainError,
    _REGISTER_NAMES,
    _canonical_bytes,
    _canonical_sha256,
    _source_identity,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_KIND,
    SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
    validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_operator_new_static_boundary import (
    ANALYSIS_KIND as PREDECESSOR_KIND,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_operator_new_second_callee_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_PREDECESSOR = "d0cecf29ab94b05dbe8f75c2c6edd823b83c53ed06f853d4db478a76e046479f"
_BASE = 0x400000
_ENTRY = 0x35848F
_SIZE = 28
_RAW = "558bec83ec0c8d4df4e8daffffff68d4c988008d45f450e800890100"
_BODY = "cb00213987913afe8e6410bc126b10a6e494f7b6c9e859c727f0ab3f8c7261b6"
_ATLAS = "1db39b499d8261ff48c0bdaac1a9e538601fa4f94cdb25f4b53882e01d325526"
_CFG = "9104d9e619946a77674e8c72f4a44612444291718bbc37c847cf495495af0ac4"

_PARENT = (0x3574F3, 0x3574DB, "e8970f0000", "605ec81a3c1419f23863f79237b52573167b4dd5d86c86c3bcb958bc46a75eba")
_OUTGOING = (
    (0x358498, "e8daffffff", 0x358477),
    (0x3584A6, "e800890100", 0x370DAB),
)
_SCOPE = {
    "atlas_function_count": 25312,
    "atlas_body_range_count": 25490,
    "decoded_bytes": 3735718,
    "decoded_instructions": 1153814,
    "all_declared_ranges_decoded": True,
    "operand_classes": ["absolute_memory", "immediate"],
}
_PARTITION_HASHES = {
    "owner_partition": "9ceaddbafddcd033937586bb6a1b275981654a833c6a7c0fdb2dd9eb37338821",
    "target_owner_partition": "db22cf6840270beb1a1483214ca01fa06f39acdede3ffb6ff0a99ef541255647",
    "target_reference_partition": "35512f2452cecc323a429f7f7309c08fd3092505037d4570e9a67629bca76139",
}
_REFERENCE_HASH = "521612266a8c1856b4bce1b4e0bd4305a3db14d64396349f24cc901f5d1bf155"


class NativeOperatorNewSecondCalleeStaticBoundaryError(RuntimeError):
    """Raised when the finite reviewed boundary cannot be reproduced."""


def _bad(message: str) -> None:
    raise NativeOperatorNewSecondCalleeStaticBoundaryError(message)


def _same(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _instruction(rva: int, encoded: str) -> dict[str, Any]:
    raw = bytes.fromhex(encoded)
    return {"rva": _hex(rva), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _compact(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _empty_register_calls() -> list[dict[str, Any]]:
    return [{"register": register, "call_rvas": []} for register in _REGISTER_NAMES]


def _edges(facts: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for raw in _array(facts.get("ghidra_declared_direct_calls"), "declared direct calls"):
        edge = _mapping(raw, "declared direct call")
        site = _rva(edge.get("instruction_rva"), "declared direct site")
        if site in result:
            _bad("duplicate declared direct-call site")
        result[site] = edge
    return result


def _normalized_edge(edge: Mapping[str, Any]) -> dict[str, Any]:
    name = edge.get("target_name")
    if type(name) is not str:
        _bad("declared direct edge lacks target analysis label")
    return {
        "instruction_rva": _hex(_rva(edge.get("instruction_rva"), "edge site")),
        "source_entry_rva": _hex(_rva(edge.get("source_entry_rva"), "edge source")),
        "target_entry_rva": _hex(_rva(edge.get("target_entry_rva"), "edge target entry")),
        "target_rva": _hex(_rva(edge.get("target_rva"), "edge target")),
        "target_name_sha256": hashlib.sha256(name.encode()).hexdigest(),
    }


def _decode(raw: bytes = bytes.fromhex(_RAW)) -> list[Any]:
    decoder, _ = _decoder()
    decoder.detail = True
    instructions = list(decoder.disasm(raw, _BASE + _ENTRY))
    if len(instructions) != 9 or b"".join(bytes(item.bytes) for item in instructions) != raw:
        _bad("sealed target bytes do not decode exactly")
    return instructions


def _points(instructions: list[Any]) -> list[dict[str, Any]]:
    records = []
    for item in instructions:
        _, writes = item.regs_access()
        write_names = {item.reg_name(register).lower() for register in writes}
        raw = bytes(item.bytes)
        records.append({
            "rva": _hex(item.address - _BASE), "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "writes_ebx": "ebx" in write_names, "writes_esi": "esi" in write_names,
            "writes_edi": "edi" in write_names, "writes_esp": "esp" in write_names,
        })
    return records


def _graph(instructions: list[Any] | None = None) -> dict[str, Any]:
    """Represent only fallthrough syntax inside the finite declared range.

    The final direct-call instruction lies at the end of the Ghidra range.  Its
    dedicated ``direct_call_range_end`` syntax means only that the reviewed
    range ends there; it makes no claim about non-return or runtime behaviour.
    """
    rows = _decode() if instructions is None else instructions
    nodes = []
    for index, point in enumerate(_points(rows)):
        is_call = bytes(rows[index].bytes).startswith(b"\xe8")
        if index + 1 == len(rows):
            if not is_call:
                _bad("sealed range no longer ends in a direct call")
            flow_kind = "direct_call_range_end"
        else:
            flow_kind = "call_fallthrough" if is_call else "fallthrough"
        nodes.append({
            "rva": point["rva"], "size": point["size"], "sha256": point["sha256"],
            "writes_esi": point["writes_esi"],
            "flow_kind": flow_kind,
            "successor_rvas": [] if index + 1 == len(rows) else [_hex(rows[index + 1].address - _BASE)],
            "writes_ebx": point["writes_ebx"], "writes_esp": point["writes_esp"],
            "writes_edi": point["writes_edi"],
        })
    graph = {
        "caller_entry_rva": _hex(_ENTRY), "range_start_rva": _hex(_ENTRY), "range_size": _SIZE,
        "nodes": nodes, "node_count": len(nodes),
        "edge_count": sum(len(node["successor_rvas"]) for node in nodes),
    }
    if (graph["node_count"], graph["edge_count"], _canonical_sha256(graph)) != (9, 8, _CFG):
        _bad("sealed target control-flow graph differs")
    return graph


def _preflight(predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]) -> dict[str, Any]:
    identity = dict(_mapping(facts.get("identity"), "program facts identity"))
    if identity.get("executable_sha256") != _EXE:
        _bad("program facts executable differs")
    if not _same(predecessor.get("build_identity"), identity) or not _same(direct.get("build_identity"), identity):
        _bad("prerequisite build identity differs")
    if predecessor.get("analysis_kind") != PREDECESSOR_KIND or _canonical_sha256(predecessor) != _PREDECESSOR:
        _bad("operator-new predecessor receipt differs")
    summary = _mapping(facts.get("summary"), "program facts summary")
    return {
        "program_facts": {**_source_identity(facts, "pe_ghidra_program_facts", _FACTS, "program facts"),
                          "function_count": summary.get("function_count"), "body_range_count": summary.get("body_range_count"),
                          "function_body_bytes": summary.get("function_body_bytes")},
        "predecessor_static_boundary": _source_identity(predecessor, PREDECESSOR_KIND, _PREDECESSOR, "operator-new predecessor"),
        "direct_call_census": _source_identity(direct, DIRECT_KIND, _DIRECT, "direct-call census"),
    }


def _target_function(facts: Mapping[str, Any]) -> Mapping[str, Any]:
    function = _atlas_functions(facts).get(_ENTRY)
    if function is None or (function.get("body_size"), function.get("body_sha256"), atlas_record_sha256(function)) != (_SIZE, _BODY, _ATLAS):
        _bad("target atlas record differs")
    return function


def _parent_edge(predecessor: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(_mapping(raw, "operator-new native edge")) for raw in _array(predecessor.get("native_edges"), "operator-new native edges")]
    matches = [row for row in rows if _rva(_mapping(row.get("instruction"), "parent instruction").get("rva"), "parent site") == _PARENT[0]
               and _rva(row.get("source_entry_rva"), "parent source") == _PARENT[1]
               and _rva(row.get("target_entry_rva"), "parent target") == _ENTRY]
    if len(rows) != 4 or len(matches) != 1:
        _bad("operator-new parent edge differs")
    parent = matches[0]
    if parent.get("control_encoding") not in (None, "e8") or not _same(parent.get("instruction"), _instruction(_PARENT[0], _PARENT[2])):
        _bad("operator-new parent instruction differs")
    return matches


def _native_calls(facts: Mapping[str, Any], image: Any | None = None) -> dict[str, Any]:
    functions, edges = _atlas_functions(facts), _edges(facts)
    _target_function(facts)
    source_sites = {
        site
        for site, edge in edges.items()
        if _rva(edge.get("source_entry_rva"), "declared direct source") == _ENTRY
    }
    if source_sites != {site for site, _encoded, _target in _OUTGOING}:
        _bad("outgoing native direct-edge partition differs")
    direct = []
    for site, encoded, target in _OUTGOING:
        edge, target_function = edges.get(site), functions.get(target)
        if edge is None or target_function is None or (
            _rva(edge.get("source_entry_rva"), "outgoing source"), _rva(edge.get("target_entry_rva"), "outgoing target entry"),
            _rva(edge.get("target_rva"), "outgoing target"),
        ) != (_ENTRY, target, target):
            _bad("outgoing native direct edge differs")
        direct.append({
            "role": "opaque_native_direct_edge", "source_entry_rva": _hex(_ENTRY),
            "source_atlas_record_sha256": _ATLAS, "source_body_size": _SIZE, "source_body_sha256": _BODY,
            "instruction": _instruction(site, encoded), "target_entry_rva": _hex(target), "target_rva": _hex(target),
            "target_atlas_record_sha256": atlas_record_sha256(target_function), "target_body_size": target_function.get("body_size"),
            "target_body_sha256": target_function.get("body_sha256"), "ghidra_declared_direct_edge": _normalized_edge(edge),
            "control_encoding": "e8", "label_source": "analysis_or_default", "callee_behavior_opaque": True,
        })
    operands = []
    for site, encoded, target in _OUTGOING:
        operands.append({
            "role": "opaque_relative_direct_target_immediate_operand", "instruction": _instruction(site, encoded),
            "operand_class": "immediate", "operand_index": 0, "operand_access": "none",
            "operand_va": _hex(_BASE + target), "operand_rva": _hex(target),
            "control_syntax": "x86_relative_near_call_e8",
            "section_name": ".text", "section_rva": "0x00001000", "section_characteristics": "0x60000020",
            "section_writable": False, "file_backed": True,
            "file_offset": "0x00357877" if target == 0x358477 else "0x003701ab",
            "contents_or_runtime_behavior_opaque": True,
        })
    operands.append({
        "role": "opaque_absolute_immediate_operand", "instruction": _instruction(0x35849D, "68d4c98800"),
        "operand_class": "immediate", "operand_index": 0, "operand_access": "none",
        "operand_va": "0x0088c9d4", "operand_rva": "0x0048c9d4", "control_syntax": "x86_push_imm32",
        "section_name": ".rdata", "section_rva": "0x003d6000", "section_characteristics": "0x40000040",
        "section_writable": False, "file_backed": True, "file_offset": "0x0048b9d4", "contents_or_runtime_behavior_opaque": True,
    })
    if image is not None:
        for target, expected_offset in ((0x358477, 0x357877), (0x370DAB, 0x3701AB)):
            section = next((item for item in image.sections if item.virtual_address <= target < item.virtual_address + item.virtual_size), None)
            if section is None or (section.name, section.virtual_address, section.characteristics, image.rva_to_file_offset(target)) != (".text", 0x1000, 0x60000020, expected_offset):
                _bad("relative direct target section binding differs")
        section = next((item for item in image.sections if item.virtual_address <= 0x48C9D4 < item.virtual_address + item.virtual_size), None)
        if section is None or (section.name, section.virtual_address, section.characteristics, image.rva_to_file_offset(0x48C9D4)) != (".rdata", 0x3D6000, 0x40000040, 0x48B9D4):
            _bad("absolute immediate section binding differs")
    return {
        "outgoing_direct": direct, "outgoing_direct_partition_complete": True,
        "direct_lua_calls": [], "direct_lua_partition_complete": True,
        "staged_lua_dispatches": [], "staged_lua_partition_complete": True,
        "opaque_indirect_controls": [], "indirect_control_partition_complete": True,
        "pe_address_operands": operands, "pe_address_operand_partition_complete": True,
        "segment_qualified_memory_syntax": [], "segment_qualified_memory_partition_complete": True,
        "bnd_prefixed_control_syntax": [], "bnd_prefixed_control_partition_complete": True,
        "opaque_interrupt_syntax": [], "opaque_interrupt_partition_complete": True,
        "call_r32_audit": _empty_register_calls(), "register_call_partition_complete": True,
    }


def _expected_scan(facts: Mapping[str, Any]) -> dict[str, Any]:
    functions, edges = _atlas_functions(facts), _edges(facts)
    parent_edge, owner = edges.get(_PARENT[0]), functions.get(_PARENT[1])
    if parent_edge is None or owner is None or (
        _rva(parent_edge.get("source_entry_rva"), "parent source"), _rva(parent_edge.get("target_entry_rva"), "parent target entry"),
        _rva(parent_edge.get("target_rva"), "parent target"), atlas_record_sha256(owner),
    ) != (_PARENT[1], _ENTRY, _ENTRY, _PARENT[3]):
        _bad("incoming frontier facts differ")
    record = {
        "instruction_rva": _hex(_PARENT[0]), "instruction_size": 5,
        "instruction_sha256": hashlib.sha256(bytes.fromhex(_PARENT[2])).hexdigest(), "owner_entry_rva": _hex(_PARENT[1]),
        "owner_atlas_record_sha256": _PARENT[3], "target_rva": _hex(_ENTRY), "target_atlas_record_sha256": _ATLAS,
        "target_va": _hex(_BASE + _ENTRY), "operand_class": "immediate", "operand_index": 0,
        "use_class": "direct_call", "call_form": "x86_relative_near_call_e8",
        "ghidra_declared_direct_edge": _normalized_edge(parent_edge),
    }
    owner_partition = [{"owner_entry_rva": _hex(_PARENT[1]), "owner_atlas_record_sha256": _PARENT[3], "reference_count": 1}]
    target_partition = [{"target_rva": _hex(_ENTRY), "target_atlas_record_sha256": _ATLAS, "reference_count": 1, "owner_count": 1}]
    target_owner_partition = [{"target_rva": _hex(_ENTRY), **owner_partition[0]}]
    target_reference_partition = [{"target_rva": _hex(_ENTRY), "target_atlas_record_sha256": _ATLAS, "reference_count": 1}]
    partition_sha256 = {
        "owner_partition": _compact(owner_partition),
        "target_owner_partition": _compact(target_owner_partition),
        "target_reference_partition": _compact(target_reference_partition),
    }
    if partition_sha256 != _PARTITION_HASHES:
        _bad("target-reference partition hashes differ")
    reference_sha256 = _compact([record])
    if reference_sha256 != _REFERENCE_HASH:
        _bad("target-reference row hash differs")
    return {
        "target_rvas": [_hex(_ENTRY)], "target_vas": [_hex(_BASE + _ENTRY)], "scope": dict(_SCOPE), "references": [record],
        "target_partition": target_partition,
        "owner_partition": owner_partition,
        "target_owner_partition": target_owner_partition,
        "target_reference_partition": target_reference_partition,
        "partition_sha256": partition_sha256,
        "references_canonical_sha256": reference_sha256,
        "aggregates": {"reference_count": 1, "target_count": 1, "owner_count": 1, "target_owner_count": 1,
                       "direct_call_count": 1, "comparison_count": 0, "other_address_count": 0, "memory_operand_count": 0},
    }


def _whole_atlas_reference_scan(data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]) -> dict[str, Any]:
    """Decode every declared range and inspect each IMM/absolute-MEM operand."""
    import capstone.x86_const as x86

    functions, found = _atlas_functions(facts), []
    totals = [0, 0, 0]
    decoder.detail = True
    target_va = image.image_base + _ENTRY
    for owner, function in sorted(functions.items()):
        for raw_range in _array(function.get("ranges"), "atlas range"):
            span = _mapping(raw_range, "atlas range")
            start, size = _rva(span.get("start_rva"), "range start"), span.get("size")
            if type(size) is not int or size <= 0:
                _bad("invalid atlas range")
            instructions = _decode_range(data, image, start, size, decoder)
            totals[0] += 1; totals[1] += size; totals[2] += len(instructions)
            for instruction in instructions:
                for operand_index, operand in enumerate(instruction.operands):
                    operand_class: str | None = None
                    value: int | None = None
                    if operand.type == x86.X86_OP_IMM:
                        operand_class, value = "immediate", int(operand.imm) & 0xFFFFFFFF
                    elif operand.type == x86.X86_OP_MEM and operand.mem.segment == x86.X86_REG_INVALID and operand.mem.base == x86.X86_REG_INVALID and operand.mem.index == x86.X86_REG_INVALID:
                        operand_class, value = "absolute_memory", int(operand.mem.disp) & 0xFFFFFFFF
                    if value == target_va:
                        found.append((instruction.address - image.image_base, owner, operand_index, bytes(instruction.bytes), operand_class))
    expected = [(_PARENT[0], _PARENT[1], 0, bytes.fromhex(_PARENT[2]), "immediate")]
    if tuple(totals) != (25490, 3735718, 1153814) or found != expected:
        _bad("all-operand target reference traversal differs")
    return _expected_scan(facts)


def _evidence(predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any], *, instructions: list[Any] | None = None, image: Any | None = None, scan: Mapping[str, Any] | None = None) -> dict[str, Any]:
    prerequisite = _preflight(predecessor, direct, facts)
    decoded = _decode() if instructions is None else instructions
    raw = b"".join(bytes(item.bytes) for item in decoded)
    _target_function(facts)
    if raw != bytes.fromhex(_RAW) or hashlib.sha256(raw).hexdigest() != _BODY:
        _bad("target body bytes differ")
    expected_scan = _expected_scan(facts)
    supplied_scan = expected_scan if scan is None else dict(scan)
    if not _same(supplied_scan, expected_scan):
        _bad("target reference receipt differs")
    parent = _parent_edge(predecessor)
    if supplied_scan["references"][0]["instruction_rva"] != parent[0]["instruction"]["rva"]:
        _bad("parent edge does not join exhaustive reference scan")
    body = {
        "role": "relationship_defined_operator_new_second_callee_static_boundary", "entry_rva": _hex(_ENTRY),
        "atlas_record_sha256": _ATLAS, "body_size": _SIZE, "body_sha256": _BODY,
        "range_start_rva": _hex(_ENTRY), "range_size": _SIZE, "control_flow_graph_canonical_sha256": _CFG,
        "reviewed_points": _points(decoded), "direct_lua_calls": [], "staged_lua_dispatches": [],
        "call_r32_audit": _empty_register_calls(), "register_call_partition_complete": True,
        "ghidra_analysis_metadata": {"name": "FUN_0075848f", "namespace": "Global", "name_source": "DEFAULT", "thunk": False, "metadata_only": True},
        "semantic_facts": {"relationship_defined_only": True, "analysis_labels_opaque": True,
                           "source_semantic_names_assigned": False, "runtime_or_success_claimed": False},
    }
    result = {
        "schema_version": SCHEMA_VERSION, "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(_mapping(facts.get("identity"), "program facts identity")), **prerequisite,
        "decoder": {"name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION, "architecture": "x86", "mode_bits": 32,
                    "sealed_instruction_count": 9,
                    "register_call_encoding_audit": [{"register": register, "encoding": f"ff{0xD0 + index:02x}"} for index, register in enumerate(_REGISTER_NAMES)]},
        "function_body": body, "control_flow_graph": _graph(decoded), "predecessor_parent_edges": parent,
        "native_calls": _native_calls(facts, image), "whole_atlas_reference_scan": supplied_scan,
        "method": {"structural_boundary": "The receipt seals 28 decoded bytes, two opaque direct native edges, one local PE-address operand, the predecessor edge, and a finite all-atlas reference traversal.",
                   "not_claimed": ["analysis-label meaning, source identity, ABI, inputs, outputs, behavior, success, failure, or normal return", "runtime reachability, invocation, ordering, frequency, or effects", "contents or runtime meaning of local PE-address operands", "computed, indirect, data, un-atlased, dynamic, or Lua-side references"]},
        "summary": {"reviewed_target_count": 1, "reviewed_target_bytes": _SIZE, "sealed_instruction_count": 9,
                    "sealed_control_flow_graph_count": 1, "sealed_control_flow_graph_node_count": 9, "sealed_control_flow_graph_edge_count": 8,
                    "native_direct_edge_count": 2, "direct_lua_call_count": 0, "staged_lua_dispatch_count": 0, "call_r32_count": 0,
                    "opaque_indirect_control_count": 0, "pe_address_operand_count": 3, "pe_immediate_operand_count": 3, "pe_absolute_memory_operand_count": 0,
                    "segment_qualified_memory_syntax_count": 0, "bnd_prefixed_control_syntax_count": 0, "opaque_interrupt_syntax_count": 0,
                    "predecessor_parent_edge_count": 1, "target_reference_count": 1, "target_reference_target_count": 1,
                    "target_reference_owner_count": 1, "target_reference_direct_call_count": 1, "target_reference_other_address_count": 0,
                    "target_reference_memory_operand_count": 0, "schema_violations": 0},
    }
    return result


def _normalize(operation):
    try:
        return operation()
    except NativeOperatorNewSecondCalleeStaticBoundaryError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassReturnHelperChainError,
            PEAnchorError, CsError, struct.error, OSError, TypeError, ValueError) as exc:
        raise NativeOperatorNewSecondCalleeStaticBoundaryError(str(exc)) from exc


def validate_native_operator_new_second_callee_static_boundary_structure(evidence: Mapping[str, Any], operator_new_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any]) -> dict[str, Any]:
    def run():
        for value, label in ((evidence, "evidence"), (operator_new_static_boundary, "operator-new predecessor"), (direct_calls, "direct calls"), (program_facts, "program facts")):
            _validate_json_tree(value, label)
        prerequisite = validate_native_lua_direct_call_structure(direct_calls, program_facts)
        if prerequisite.get("status") != "structurally_verified" or prerequisite.get("evidence_sha256") != _DIRECT:
            _bad("direct-call structural prerequisite differs")
        expected = _evidence(operator_new_static_boundary, direct_calls, program_facts)
        if not _same(evidence, expected):
            _bad("structure receipt differs from finite reconstruction")
        _assert_publication_safe(evidence)
        return {"schema_version": SCHEMA_VERSION, "analysis_kind": STRUCTURE_VERIFICATION_KIND, "status": "structurally_verified",
                "build_identity": dict(evidence["build_identity"]), "evidence_sha256": _canonical_sha256(evidence), "summary": dict(evidence["summary"])}
    return _normalize(run)


def build_native_operator_new_second_callee_static_boundary(executable: Path, operator_new_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    def run():
        for value, label in ((operator_new_static_boundary, "operator-new predecessor"), (direct_calls, "direct calls"), (program_facts, "program facts"), (inventory, "inventory")):
            _validate_json_tree(value, label)
        prerequisite = validate_native_lua_direct_call_census(executable, direct_calls, program_facts, inventory=inventory)
        if prerequisite.get("status") != "verified" or prerequisite.get("evidence_sha256") != _DIRECT:
            _bad("direct-call exact prerequisite differs")
        data, image, digest = _load_executable(executable)
        if digest != _EXE or image.image_base != _BASE:
            _bad("exact executable identity differs")
        decoder, _ = _decoder(); decoder.detail = True
        decoded = _decode_range(data, image, _ENTRY, _SIZE, decoder)
        scan = _whole_atlas_reference_scan(data, image, decoder, program_facts)
        result = _evidence(operator_new_static_boundary, direct_calls, program_facts, instructions=decoded, image=image, scan=scan)
        if _load_executable(executable)[2] != digest:
            _bad("executable changed during exact rebuild")
        _assert_publication_safe(result)
        validate_native_operator_new_second_callee_static_boundary_structure(result, operator_new_static_boundary, direct_calls, program_facts)
        return result
    return _normalize(run)


def validate_native_operator_new_second_callee_static_boundary(executable: Path, evidence: Mapping[str, Any], operator_new_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    def run():
        _validate_json_tree(evidence, "evidence")
        rebuilt = build_native_operator_new_second_callee_static_boundary(executable, operator_new_static_boundary, direct_calls, program_facts, inventory=inventory)
        if not _same(evidence, rebuilt):
            _bad("evidence differs from exact rebuild")
        return {"schema_version": SCHEMA_VERSION, "analysis_kind": VERIFICATION_KIND, "status": "verified",
                "build_identity": dict(rebuilt["build_identity"]), "evidence_sha256": _canonical_sha256(rebuilt), "summary": dict(rebuilt["summary"])}
    return _normalize(run)


def encode_native_operator_new_second_callee_static_boundary(value: Mapping[str, Any]) -> str:
    def run():
        _validate_json_tree(value, "encoded value")
        return json.dumps(_mapping(value, "encoded value"), ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n"
    return _normalize(run)
