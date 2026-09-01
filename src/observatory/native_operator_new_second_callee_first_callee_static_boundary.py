"""Opaque, relationship-only static boundary for ``0x00358477``.

This receipt is deliberately limited to immutable PE bytes and finite atlas
relationships.  Ghidra names and local address operands are metadata only.
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
    NativeLuaCClosurePublicationError, _array, _assert_publication_safe,
    _atlas_functions, _decode_range, _hex, _mapping, _rva, _validate_json_tree,
)
from src.observatory.native_lua_class_return_helper_chain import (
    NativeLuaClassReturnHelperChainError, _REGISTER_NAMES, _canonical_bytes,
    _canonical_sha256, _enhanced_cfg, _source_identity, _with_edi_writes,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_KIND, SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError, _decoder, _load_executable,
    validate_native_lua_direct_call_census, validate_native_lua_direct_call_structure,
)
from src.observatory.native_operator_new_second_callee_static_boundary import (
    ANALYSIS_KIND as PREDECESSOR_KIND,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_operator_new_second_callee_first_callee_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_PREDECESSOR = "ebc3514d67711d7774e51eecd4c881f9826ed6ec68f40ca462415e654ba7d856"
_BASE = 0x400000
_ENTRY = 0x358477
_SIZE = 24
_RAW = "836104008bc183610800c741040c1a7f00c701041a7f00c3"
_BODY = "9026f0c92e01f3ee65b7f14c6cc0c3212acfab8f2f78a791662fbddfbb97487e"
_ATLAS = "42e566ad75aecc0769a11441d5518b213f8abd460080096fc142d595f37f5b5f"
_CFG = "132688f239bf9c4dd1cbec45b3bb8a04d1c78907169de10c58ae80d2eeec9aaf"
_PARENT = (0x358498, 0x35848F, "e8daffffff", "1db39b499d8261ff48c0bdaac1a9e538601fa4f94cdb25f4b53882e01d325526")
_SCOPE = {"atlas_function_count": 25312, "atlas_body_range_count": 25490,
          "decoded_bytes": 3735718, "decoded_instructions": 1153814,
          "all_declared_ranges_decoded": True,
          "operand_classes": ["absolute_memory", "immediate"]}
_PARTITION_HASHES = {
    "owner_partition": "bd65e5d80bc2e3fa4bb8c7fb9c7b0b6b1a2000eb64e0d3dcb3d137366a592c9a",
    "target_owner_partition": "e1bf7a2f6d4ecc00e19ab6d6014f22b53b64b99b164b3147db7f4a2b75628e36",
    "target_reference_partition": "dcec913000b1c93933280e5ace0ec6a5cbc8f8f0737c00b063fff21b924015ff",
}
_REFERENCE_HASH = "61a8bd46690d61a56934ec290053205eba2f57f84b2d96adeae682697f80fa93"


class NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError(RuntimeError):
    """Raised when the finite reviewed boundary cannot be reproduced."""


def _bad(message: str) -> None:
    raise NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError(message)


def _same(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _compact(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _instruction(rva: int, encoded: str) -> dict[str, Any]:
    raw = bytes.fromhex(encoded)
    return {"rva": _hex(rva), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


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
    return {"instruction_rva": _hex(_rva(edge.get("instruction_rva"), "edge site")),
            "source_entry_rva": _hex(_rva(edge.get("source_entry_rva"), "edge source")),
            "target_entry_rva": _hex(_rva(edge.get("target_entry_rva"), "edge target entry")),
            "target_rva": _hex(_rva(edge.get("target_rva"), "edge target")),
            "target_name_sha256": hashlib.sha256(name.encode()).hexdigest()}


def _decode(raw: bytes = bytes.fromhex(_RAW)) -> list[Any]:
    decoder, _ = _decoder()
    decoder.detail = True
    instructions = list(decoder.disasm(raw, _BASE + _ENTRY))
    if len(instructions) != 6 or b"".join(bytes(item.bytes) for item in instructions) != raw:
        _bad("sealed target bytes do not decode exactly")
    return instructions


def _points(instructions: list[Any]) -> list[dict[str, Any]]:
    result = []
    for item in instructions:
        _, writes = item.regs_access()
        names = {item.reg_name(register).lower() for register in writes}
        raw = bytes(item.bytes)
        result.append({"rva": _hex(item.address - _BASE), "size": len(raw),
                       "sha256": hashlib.sha256(raw).hexdigest(),
                       "writes_ebx": "ebx" in names, "writes_esi": "esi" in names,
                       "writes_edi": "edi" in names, "writes_esp": "esp" in names})
    return result


def _graph(instructions: list[Any] | None = None) -> dict[str, Any]:
    """Seal decoded control syntax; terminal syntax does not imply normal return."""
    import capstone
    import capstone.x86_const as x86

    rows = _decode() if instructions is None else instructions
    graph = _with_edi_writes(_enhanced_cfg(rows, _BASE, (_ENTRY, _SIZE), capstone, x86), rows, x86)
    graph["caller_entry_rva"] = _hex(_ENTRY)
    if (graph.get("node_count"), graph.get("edge_count"), _canonical_sha256(graph)) != (6, 5, _CFG):
        _bad("sealed target control-flow graph differs")
    return graph


def _preflight(predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]) -> dict[str, Any]:
    identity = dict(_mapping(facts.get("identity"), "program facts identity"))
    if identity.get("executable_sha256") != _EXE:
        _bad("program facts executable differs")
    if not _same(predecessor.get("build_identity"), identity) or not _same(direct.get("build_identity"), identity):
        _bad("prerequisite build identity differs")
    if predecessor.get("analysis_kind") != PREDECESSOR_KIND or _canonical_sha256(predecessor) != _PREDECESSOR:
        _bad("operator-new second-callee predecessor receipt differs")
    summary = _mapping(facts.get("summary"), "program facts summary")
    return {"program_facts": {**_source_identity(facts, "pe_ghidra_program_facts", _FACTS, "program facts"),
                                "function_count": summary.get("function_count"), "body_range_count": summary.get("body_range_count"),
                                "function_body_bytes": summary.get("function_body_bytes")},
            "predecessor_static_boundary": _source_identity(predecessor, PREDECESSOR_KIND, _PREDECESSOR, "operator-new second-callee predecessor"),
            "direct_call_census": _source_identity(direct, DIRECT_KIND, _DIRECT, "direct-call census")}


def _target_function(facts: Mapping[str, Any]) -> Mapping[str, Any]:
    function = _atlas_functions(facts).get(_ENTRY)
    if function is None or (function.get("body_size"), function.get("body_sha256"), atlas_record_sha256(function)) != (_SIZE, _BODY, _ATLAS):
        _bad("target atlas record differs")
    return function


def _parent_edge(predecessor: Mapping[str, Any]) -> list[dict[str, Any]]:
    calls = _mapping(predecessor.get("native_calls"), "predecessor native calls")
    rows = [dict(_mapping(raw, "predecessor direct edge")) for raw in _array(calls.get("outgoing_direct"), "predecessor direct edges")]
    matches = [row for row in rows if _rva(_mapping(row.get("instruction"), "parent instruction").get("rva"), "parent site") == _PARENT[0]
               and _rva(row.get("source_entry_rva"), "parent source") == _PARENT[1]
               and _rva(row.get("target_entry_rva"), "parent target") == _ENTRY]
    if len(rows) != 2 or len(matches) != 1:
        _bad("operator-new second-callee parent edge differs")
    parent = matches[0]
    if parent.get("control_encoding") != "e8" or not _same(parent.get("instruction"), _instruction(_PARENT[0], _PARENT[2])):
        _bad("operator-new second-callee parent instruction differs")
    return matches


def _native_calls(facts: Mapping[str, Any], image: Any | None = None) -> dict[str, Any]:
    """Close the declared outgoing-edge partition before publishing it empty."""
    _target_function(facts)
    source_sites = {
        site for site, edge in _edges(facts).items()
        if _rva(edge.get("source_entry_rva"), "declared direct source") == _ENTRY
    }
    if source_sites:
        _bad("outgoing native direct-edge partition differs")
    operands = []
    for site, encoded, va, rva, offset in ((0x358481, "c741040c1a7f00", 0x7F1A0C, 0x3F1A0C, 0x3F0A0C),
                                           (0x358488, "c701041a7f00", 0x7F1A04, 0x3F1A04, 0x3F0A04)):
        operands.append({"role": "opaque_absolute_immediate_operand", "instruction": _instruction(site, encoded),
                         "operand_class": "immediate", "operand_index": 1, "operand_access": "none",
                         "operand_va": _hex(va), "operand_rva": _hex(rva), "control_syntax": "x86_mov_mem_imm32",
                         "section_name": ".rdata", "section_rva": "0x003d6000", "section_characteristics": "0x40000040",
                         "section_writable": False, "file_backed": True, "file_offset": _hex(offset),
                         "contents_or_runtime_behavior_opaque": True})
    if image is not None:
        for operand in operands:
            rva = _rva(operand["operand_rva"], "operand rva")
            section = next((row for row in image.sections if row.virtual_address <= rva < row.virtual_address + row.virtual_size), None)
            if section is None or (section.name, section.virtual_address, section.characteristics, image.rva_to_file_offset(rva)) != (
                ".rdata", 0x3D6000, 0x40000040, int(operand["file_offset"], 16)):
                _bad("local PE-address operand section binding differs")
    return {"outgoing_direct": [], "outgoing_direct_partition_complete": True,
            "direct_lua_calls": [], "direct_lua_partition_complete": True,
            "staged_lua_dispatches": [], "staged_lua_partition_complete": True,
            "opaque_indirect_controls": [], "indirect_control_partition_complete": True,
            "pe_address_operands": operands, "pe_address_operand_partition_complete": True,
            "non_pe_immediate_literals": [{"instruction_rva": "0x00358477", "operand_index": 1, "value": "0x00000000"},
                                            {"instruction_rva": "0x0035847d", "operand_index": 1, "value": "0x00000000"}],
            "non_pe_immediate_literal_partition_complete": True,
            "segment_qualified_memory_syntax": [], "segment_qualified_memory_partition_complete": True,
            "bnd_prefixed_control_syntax": [], "bnd_prefixed_control_partition_complete": True,
            "opaque_interrupt_syntax": [], "opaque_interrupt_partition_complete": True,
            "call_r32_audit": _empty_register_calls(), "register_call_partition_complete": True}


def _expected_scan(facts: Mapping[str, Any]) -> dict[str, Any]:
    functions, edges = _atlas_functions(facts), _edges(facts)
    parent_edge, owner = edges.get(_PARENT[0]), functions.get(_PARENT[1])
    if parent_edge is None or owner is None or (_rva(parent_edge.get("source_entry_rva"), "parent source"),
                                                _rva(parent_edge.get("target_entry_rva"), "parent target"),
                                                _rva(parent_edge.get("target_rva"), "parent target"), atlas_record_sha256(owner)) != (_PARENT[1], _ENTRY, _ENTRY, _PARENT[3]):
        _bad("incoming frontier facts differ")
    record = {"instruction_rva": _hex(_PARENT[0]), "instruction_size": 5,
              "instruction_sha256": hashlib.sha256(bytes.fromhex(_PARENT[2])).hexdigest(),
              "owner_entry_rva": _hex(_PARENT[1]), "owner_atlas_record_sha256": _PARENT[3],
              "target_rva": _hex(_ENTRY), "target_atlas_record_sha256": _ATLAS, "target_va": _hex(_BASE + _ENTRY),
              "operand_class": "immediate", "operand_index": 0, "use_class": "direct_call",
              "call_form": "x86_relative_near_call_e8", "ghidra_declared_direct_edge": _normalized_edge(parent_edge)}
    owner_partition = [{"owner_entry_rva": _hex(_PARENT[1]), "owner_atlas_record_sha256": _PARENT[3], "reference_count": 1}]
    target_partition = [{"target_rva": _hex(_ENTRY), "target_atlas_record_sha256": _ATLAS, "reference_count": 1, "owner_count": 1}]
    target_owner_partition = [{"target_rva": _hex(_ENTRY), **owner_partition[0]}]
    target_reference_partition = [{"target_rva": _hex(_ENTRY), "target_atlas_record_sha256": _ATLAS, "reference_count": 1}]
    partition_sha256 = {"owner_partition": _compact(owner_partition), "target_owner_partition": _compact(target_owner_partition),
                        "target_reference_partition": _compact(target_reference_partition)}
    if partition_sha256 != _PARTITION_HASHES or _compact([record]) != _REFERENCE_HASH:
        _bad("target-reference hash differs")
    return {"target_rvas": [_hex(_ENTRY)], "target_vas": [_hex(_BASE + _ENTRY)], "scope": dict(_SCOPE), "references": [record],
            "target_partition": target_partition, "owner_partition": owner_partition, "target_owner_partition": target_owner_partition,
            "target_reference_partition": target_reference_partition, "partition_sha256": partition_sha256,
            "references_canonical_sha256": _REFERENCE_HASH,
            "aggregates": {"reference_count": 1, "target_count": 1, "owner_count": 1, "target_owner_count": 1,
                           "direct_call_count": 1, "comparison_count": 0, "other_address_count": 0, "memory_operand_count": 0}}


def _whole_atlas_reference_scan(data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]) -> dict[str, Any]:
    """Decode every declared range and inspect IMM and pure absolute-MEM operands."""
    import capstone.x86_const as x86

    found, totals = [], [0, 0, 0]
    decoder.detail = True
    target_va = image.image_base + _ENTRY
    for owner, function in sorted(_atlas_functions(facts).items()):
        for raw_range in _array(function.get("ranges"), "atlas range"):
            span = _mapping(raw_range, "atlas range")
            start, size = _rva(span.get("start_rva"), "range start"), span.get("size")
            if type(size) is not int or size <= 0:
                _bad("invalid atlas range")
            instructions = _decode_range(data, image, start, size, decoder)
            totals[0] += 1; totals[1] += size; totals[2] += len(instructions)
            for instruction in instructions:
                for operand_index, operand in enumerate(instruction.operands):
                    operand_class, value = None, None
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
    body = {"role": "relationship_defined_operator_new_second_callee_first_callee_static_boundary", "entry_rva": _hex(_ENTRY),
            "atlas_record_sha256": _ATLAS, "body_size": _SIZE, "body_sha256": _BODY,
            "range_start_rva": _hex(_ENTRY), "range_size": _SIZE, "control_flow_graph_canonical_sha256": _CFG,
            "reviewed_points": _points(decoded), "direct_lua_calls": [], "staged_lua_dispatches": [],
            "call_r32_audit": _empty_register_calls(), "register_call_partition_complete": True,
            "ghidra_analysis_metadata": {"name": "FUN_00758477", "namespace": "Global", "name_source": "DEFAULT", "thunk": False, "metadata_only": True},
            "semantic_facts": {"relationship_defined_only": True, "analysis_labels_opaque": True,
                               "source_semantic_names_assigned": False, "runtime_or_success_claimed": False}}
    calls = _native_calls(facts, image)
    result = {"schema_version": SCHEMA_VERSION, "analysis_kind": ANALYSIS_KIND,
              "build_identity": dict(_mapping(facts.get("identity"), "program facts identity")), **prerequisite,
              "decoder": {"name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION, "architecture": "x86", "mode_bits": 32,
                          "sealed_instruction_count": 6,
                          "register_call_encoding_audit": [{"register": register, "encoding": f"ff{0xD0 + index:02x}"} for index, register in enumerate(_REGISTER_NAMES)]},
              "function_body": body, "control_flow_graph": _graph(decoded), "predecessor_parent_edges": parent,
              "native_calls": calls, "whole_atlas_reference_scan": supplied_scan,
              "method": {"structural_boundary": "The receipt seals 24 decoded bytes, two opaque local PE-address immediate operands, the predecessor edge, and a finite all-atlas reference traversal.",
                         "not_claimed": ["analysis-label meaning, source identity, ABI, inputs, outputs, behavior, success, failure, or normal return",
                                         "runtime reachability, invocation, ordering, frequency, or effects", "contents or runtime meaning of local PE-address operands",
                                         "computed, indirect, data, un-atlased, dynamic, or Lua-side references"]},
              "summary": {"reviewed_target_count": 1, "reviewed_target_bytes": _SIZE, "sealed_instruction_count": 6,
                          "sealed_control_flow_graph_count": 1, "sealed_control_flow_graph_node_count": 6, "sealed_control_flow_graph_edge_count": 5,
                          "native_direct_edge_count": 0, "direct_lua_call_count": 0, "staged_lua_dispatch_count": 0, "call_r32_count": 0,
                          "opaque_indirect_control_count": 0, "pe_address_operand_count": 2, "pe_immediate_operand_count": 2,
                          "pe_absolute_memory_operand_count": 0, "non_pe_immediate_literal_count": 2,
                          "segment_qualified_memory_syntax_count": 0, "bnd_prefixed_control_syntax_count": 0, "opaque_interrupt_syntax_count": 0,
                          "predecessor_parent_edge_count": 1, "target_reference_count": 1, "target_reference_target_count": 1,
                          "target_reference_owner_count": 1, "target_reference_direct_call_count": 1,
                          "target_reference_other_address_count": 0, "target_reference_memory_operand_count": 0, "schema_violations": 0}}
    return result


def _normalize(operation):
    try:
        return operation()
    except NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError:
        raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassReturnHelperChainError,
            PEAnchorError, CsError, struct.error, OSError, TypeError, ValueError) as exc:
        raise NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError(str(exc)) from exc


def validate_native_operator_new_second_callee_first_callee_static_boundary_structure(evidence: Mapping[str, Any], operator_new_second_callee_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any]) -> dict[str, Any]:
    def run():
        for value, label in ((evidence, "evidence"), (operator_new_second_callee_static_boundary, "operator-new second-callee predecessor"), (direct_calls, "direct calls"), (program_facts, "program facts")):
            _validate_json_tree(value, label)
        prerequisite = validate_native_lua_direct_call_structure(direct_calls, program_facts)
        if prerequisite.get("status") != "structurally_verified" or prerequisite.get("evidence_sha256") != _DIRECT:
            _bad("direct-call structural prerequisite differs")
        expected = _evidence(operator_new_second_callee_static_boundary, direct_calls, program_facts)
        if not _same(evidence, expected):
            _bad("structure receipt differs from finite reconstruction")
        _assert_publication_safe(evidence)
        return {"schema_version": SCHEMA_VERSION, "analysis_kind": STRUCTURE_VERIFICATION_KIND, "status": "structurally_verified",
                "build_identity": dict(evidence["build_identity"]), "evidence_sha256": _canonical_sha256(evidence), "summary": dict(evidence["summary"])}
    return _normalize(run)


def build_native_operator_new_second_callee_first_callee_static_boundary(executable: Path, operator_new_second_callee_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    def run():
        for value, label in ((operator_new_second_callee_static_boundary, "operator-new second-callee predecessor"), (direct_calls, "direct calls"), (program_facts, "program facts"), (inventory, "inventory")):
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
        result = _evidence(operator_new_second_callee_static_boundary, direct_calls, program_facts, instructions=decoded, image=image, scan=scan)
        if _load_executable(executable)[2] != digest:
            _bad("executable changed during exact rebuild")
        _assert_publication_safe(result)
        validate_native_operator_new_second_callee_first_callee_static_boundary_structure(result, operator_new_second_callee_static_boundary, direct_calls, program_facts)
        return result
    return _normalize(run)


def validate_native_operator_new_second_callee_first_callee_static_boundary(executable: Path, evidence: Mapping[str, Any], operator_new_second_callee_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    def run():
        _validate_json_tree(evidence, "evidence")
        rebuilt = build_native_operator_new_second_callee_first_callee_static_boundary(executable, operator_new_second_callee_static_boundary, direct_calls, program_facts, inventory=inventory)
        if not _same(evidence, rebuilt):
            _bad("evidence differs from exact rebuild")
        return {"schema_version": SCHEMA_VERSION, "analysis_kind": VERIFICATION_KIND, "status": "verified",
                "build_identity": dict(rebuilt["build_identity"]), "evidence_sha256": _canonical_sha256(rebuilt), "summary": dict(rebuilt["summary"])}
    return _normalize(run)


def encode_native_operator_new_second_callee_first_callee_static_boundary(value: Mapping[str, Any]) -> str:
    def run():
        _validate_json_tree(value, "encoded value")
        return json.dumps(_mapping(value, "encoded value"), ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n"
    return _normalize(run)
