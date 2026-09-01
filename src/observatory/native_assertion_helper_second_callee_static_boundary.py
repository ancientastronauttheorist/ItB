"""Fail-closed static receipt for assertion-helper direct callee ``0x0038c89f``.

The module records finite PE syntax and atlas relationships only.  It does not
assign meaning to the analysis label, the virtual-only data address, or RET.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_setfield_publications import (
    _array, _assert_publication_safe, _atlas_functions, _decode_range, _hex,
    _mapping, _rva, _validate_json_tree,
)
from src.observatory.native_lua_class_return_helper_chain import (
    _REGISTER_NAMES, _canonical_bytes, _canonical_sha256, _enhanced_cfg,
    _source_identity, _with_edi_writes,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_KIND, SUPPORTED_CAPSTONE_VERSION, _decoder,
    _load_executable, validate_native_lua_direct_call_census,
    validate_native_lua_direct_call_structure,
)
from src.observatory.native_assertion_helper_static_boundary import ANALYSIS_KIND as PREDECESSOR_KIND


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_assertion_helper_second_callee_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_PREDECESSOR = "beeebb2dadd0ef2a77742f9296760fd09afe5c566c7b46bf36d2dd3cf8e441b4"
_BASE, _ENTRY, _SIZE = 0x400000, 0x38C89F, 6
_RAW = "a118738b00c3"
_BODY = "f664d3656a8c5a2735ac645e41a9bf134e95d47511b55d5466a3384f9d529fec"
_ATLAS = "bedac224c196ecaac1be86641c5dff897aa6f82a898bb95760259b310f50d207"
_CFG = "56183b6f25df792273808ded5bb52ca03b46561f13c794f0ef9abf7d687cb375"
_PARENT = (0x379CDC, 0x379CC2, "e8be2b0100", "0103f8a5b002b70e110ee0031538326b0eeb59da2cc798607a62a5603e04ac29")
_REFERENCES = ((0x379CDC, 0x379CC2, "e8be2b0100"), (0x392D68, 0x392D32, "e8329bffff"), (0x392F34, 0x392EFB, "e86699ffff"))
_SCOPE = {"atlas_function_count": 25312, "atlas_body_range_count": 25490,
          "decoded_bytes": 3735718, "decoded_instructions": 1153814,
          "all_declared_ranges_decoded": True,
          "operand_classes": ["absolute_memory", "immediate"]}


class NativeAssertionHelperSecondCalleeStaticBoundaryError(RuntimeError):
    """Raised when the finite assertion-helper receipt cannot be reproduced."""


def _bad(message: str) -> None:
    raise NativeAssertionHelperSecondCalleeStaticBoundaryError(message)


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
        edge = _mapping(raw, "declared direct edge")
        site = _rva(edge.get("instruction_rva"), "declared direct site")
        if site in result:
            _bad("duplicate declared direct-call site")
        result[site] = edge
    return result


def _normalized_edge(edge: Mapping[str, Any]) -> dict[str, Any]:
    name = edge.get("target_name")
    if type(name) is not str:
        _bad("declared direct edge lacks analysis label")
    return {"instruction_rva": _hex(_rva(edge.get("instruction_rva"), "edge site")),
            "source_entry_rva": _hex(_rva(edge.get("source_entry_rva"), "edge source")),
            "target_entry_rva": _hex(_rva(edge.get("target_entry_rva"), "edge target entry")),
            "target_rva": _hex(_rva(edge.get("target_rva"), "edge target")),
            "target_name_sha256": hashlib.sha256(name.encode()).hexdigest()}


def _decode(raw: bytes = bytes.fromhex(_RAW)) -> list[Any]:
    decoder, _ = _decoder()
    decoder.detail = True
    rows = list(decoder.disasm(raw, _BASE + _ENTRY))
    if len(rows) != 2 or b"".join(bytes(row.bytes) for row in rows) != raw:
        _bad("sealed target bytes do not decode exactly")
    return rows


def _points(rows: list[Any]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        _, writes = row.regs_access()
        names = {row.reg_name(register).lower() for register in writes}
        raw = bytes(row.bytes)
        result.append({"rva": _hex(row.address - _BASE), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                       "writes_ebx": "ebx" in names, "writes_esi": "esi" in names,
                       "writes_edi": "edi" in names, "writes_esp": "esp" in names})
    return result


def _graph(rows: list[Any] | None = None) -> dict[str, Any]:
    """A terminal RET is sealed as syntax only; no return behaviour is claimed."""
    import capstone
    import capstone.x86_const as x86

    decoded = _decode() if rows is None else rows
    graph = _with_edi_writes(_enhanced_cfg(decoded, _BASE, (_ENTRY, _SIZE), capstone, x86), decoded, x86)
    graph["caller_entry_rva"] = _hex(_ENTRY)
    if (graph.get("node_count"), graph.get("edge_count"), _canonical_sha256(graph)) != (2, 1, _CFG):
        _bad("sealed target control-flow graph differs")
    return graph


def _preflight(predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]) -> dict[str, Any]:
    identity = dict(_mapping(facts.get("identity"), "program facts identity"))
    if identity.get("executable_sha256") != _EXE:
        _bad("program facts executable differs")
    if not _same(predecessor.get("build_identity"), identity) or not _same(direct.get("build_identity"), identity):
        _bad("prerequisite build identity differs")
    if predecessor.get("analysis_kind") != PREDECESSOR_KIND or _canonical_sha256(predecessor) != _PREDECESSOR:
        _bad("assertion-helper predecessor receipt differs")
    summary = _mapping(facts.get("summary"), "program facts summary")
    return {"program_facts": {**_source_identity(facts, "pe_ghidra_program_facts", _FACTS, "program facts"),
                               "function_count": summary.get("function_count"), "body_range_count": summary.get("body_range_count"),
                               "function_body_bytes": summary.get("function_body_bytes")},
            "predecessor_static_boundary": _source_identity(predecessor, PREDECESSOR_KIND, _PREDECESSOR, "assertion-helper predecessor"),
            "direct_call_census": _source_identity(direct, DIRECT_KIND, _DIRECT, "direct-call census")}


def _target_function(facts: Mapping[str, Any]) -> Mapping[str, Any]:
    function = _atlas_functions(facts).get(_ENTRY)
    if function is None or (function.get("body_size"), function.get("body_sha256"), atlas_record_sha256(function)) != (_SIZE, _BODY, _ATLAS):
        _bad("target atlas record differs")
    return function


def _parent_edge(predecessor: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(_mapping(raw, "predecessor direct edge")) for raw in _array(predecessor.get("native_edges"), "predecessor native edges")]
    matches = [row for row in rows if _rva(_mapping(row.get("instruction"), "parent instruction").get("rva"), "parent site") == _PARENT[0]
               and _rva(row.get("source_entry_rva"), "parent source") == _PARENT[1]
               and _rva(row.get("target_entry_rva"), "parent target") == _ENTRY]
    if len(rows) != 4 or len(matches) != 1:
        _bad("assertion-helper parent edge differs")
    parent = matches[0]
    if parent.get("source_atlas_record_sha256") != _PARENT[3] or not _same(parent.get("instruction"), _instruction(_PARENT[0], _PARENT[2])):
        _bad("assertion-helper parent instruction differs")
    return matches


def _native_calls(facts: Mapping[str, Any], image: Any | None = None) -> dict[str, Any]:
    """Prove every native/Lua/control partition empty before publishing emptiness."""
    _target_function(facts)
    source_sites = {site for site, edge in _edges(facts).items() if _rva(edge.get("source_entry_rva"), "declared direct source") == _ENTRY}
    if source_sites:
        _bad("outgoing native direct-edge partition differs")
    operand = {"role": "opaque_absolute_memory_read_syntax", "instruction": _instruction(_ENTRY, "a118738b00"),
               "operand_class": "absolute_memory", "operand_index": 1, "operand_access": "read",
               "operand_va": "0x008b7318", "operand_rva": "0x004b7318", "section_name": ".data",
               "section_rva": "0x00492000", "section_characteristics": "0xc0000040", "section_writable": True,
               "section_virtual_size": "0x000471cc", "section_raw_size": "0x00024800", "section_raw_offset": "0x00490200",
               "file_backed": False, "file_offset": None, "contents_or_runtime_behavior_opaque": True}
    if image is not None:
        rva = _rva(operand["operand_rva"], "operand rva")
        section = next((row for row in image.sections if row.virtual_address <= rva < row.virtual_address + row.virtual_size), None)
        if section is None or (section.name, section.virtual_address, section.characteristics, section.virtual_size, section.raw_size, section.raw_offset) != (".data", 0x492000, 0xC0000040, 0x471CC, 0x24800, 0x490200):
            _bad("virtual-only PE-address section binding differs")
        if image.rva_to_file_offset(rva) is not None:
            _bad("virtual-only PE-address unexpectedly has file offset")
    return {"outgoing_direct": [], "outgoing_direct_partition_complete": True,
            "direct_lua_calls": [], "direct_lua_partition_complete": True,
            "staged_lua_dispatches": [], "staged_lua_partition_complete": True,
            "opaque_indirect_controls": [], "indirect_control_partition_complete": True,
            "pe_address_operands": [operand], "pe_address_operand_partition_complete": True,
            "non_pe_immediate_literals": [], "non_pe_immediate_literal_partition_complete": True,
            "segment_qualified_memory_syntax": [], "segment_qualified_memory_partition_complete": True,
            "bnd_prefixed_control_syntax": [], "bnd_prefixed_control_partition_complete": True,
            "opaque_interrupt_syntax": [], "opaque_interrupt_partition_complete": True,
            "call_r32_audit": _empty_register_calls(), "register_call_partition_complete": True}


def _expected_scan(facts: Mapping[str, Any]) -> dict[str, Any]:
    functions, edges = _atlas_functions(facts), _edges(facts)
    records = []
    for site, owner_rva, encoded in _REFERENCES:
        edge, owner = edges.get(site), functions.get(owner_rva)
        if edge is None or owner is None or (_rva(edge.get("source_entry_rva"), "reference source"), _rva(edge.get("target_entry_rva"), "reference target"), _rva(edge.get("target_rva"), "reference target")) != (owner_rva, _ENTRY, _ENTRY):
            _bad("incoming frontier facts differ")
        records.append({"instruction_rva": _hex(site), "instruction_size": 5, "instruction_sha256": hashlib.sha256(bytes.fromhex(encoded)).hexdigest(),
                        "owner_entry_rva": _hex(owner_rva), "owner_atlas_record_sha256": atlas_record_sha256(owner),
                        "target_rva": _hex(_ENTRY), "target_atlas_record_sha256": _ATLAS, "target_va": _hex(_BASE + _ENTRY),
                        "operand_class": "immediate", "operand_index": 0, "use_class": "direct_call", "call_form": "x86_relative_near_call_e8",
                        "ghidra_declared_direct_edge": _normalized_edge(edge)})
    owners = []
    for record in records:
        owners.append({"owner_entry_rva": record["owner_entry_rva"], "owner_atlas_record_sha256": record["owner_atlas_record_sha256"], "reference_count": 1})
    target_partition = [{"target_rva": _hex(_ENTRY), "target_atlas_record_sha256": _ATLAS, "reference_count": 3, "owner_count": 3}]
    target_owner = [{"target_rva": _hex(_ENTRY), **owner} for owner in owners]
    target_reference = [{"target_rva": _hex(_ENTRY), "target_atlas_record_sha256": _ATLAS, "reference_count": 3}]
    hashes = {"target_partition": _compact(target_partition), "owner_partition": _compact(owners),
              "target_owner_partition": _compact(target_owner), "target_reference_partition": _compact(target_reference)}
    return {"target_rvas": [_hex(_ENTRY)], "target_vas": [_hex(_BASE + _ENTRY)], "scope": dict(_SCOPE), "references": records,
            "target_partition": target_partition, "owner_partition": owners, "target_owner_partition": target_owner,
            "target_reference_partition": target_reference, "partition_sha256": hashes, "references_canonical_sha256": _compact(records),
            "aggregates": {"reference_count": 3, "target_count": 1, "owner_count": 3, "target_owner_count": 3,
                           "direct_call_count": 3, "comparison_count": 0, "other_address_count": 0, "memory_operand_count": 0}}


def _whole_atlas_reference_scan(data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]) -> dict[str, Any]:
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
            rows = _decode_range(data, image, start, size, decoder)
            totals[0] += 1; totals[1] += size; totals[2] += len(rows)
            for row in rows:
                for index, operand in enumerate(row.operands):
                    kind, value = None, None
                    if operand.type == x86.X86_OP_IMM:
                        kind, value = "immediate", int(operand.imm) & 0xFFFFFFFF
                    elif operand.type == x86.X86_OP_MEM and operand.mem.segment == x86.X86_REG_INVALID and operand.mem.base == x86.X86_REG_INVALID and operand.mem.index == x86.X86_REG_INVALID:
                        kind, value = "absolute_memory", int(operand.mem.disp) & 0xFFFFFFFF
                    if value == target_va:
                        found.append((row.address - image.image_base, owner, index, bytes(row.bytes), kind))
    expected = [(site, owner, 0, bytes.fromhex(encoded), "immediate") for site, owner, encoded in _REFERENCES]
    if tuple(totals) != (25490, 3735718, 1153814) or found != expected:
        _bad("all-operand target reference traversal differs")
    return _expected_scan(facts)


def _evidence(predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any], *, rows: list[Any] | None = None, image: Any | None = None, scan: Mapping[str, Any] | None = None) -> dict[str, Any]:
    prerequisites = _preflight(predecessor, direct, facts)
    decoded = _decode() if rows is None else rows
    raw = b"".join(bytes(row.bytes) for row in decoded)
    if raw != bytes.fromhex(_RAW) or hashlib.sha256(raw).hexdigest() != _BODY:
        _bad("target body bytes differ")
    _target_function(facts)
    expected = _expected_scan(facts)
    supplied = expected if scan is None else dict(scan)
    if not _same(supplied, expected):
        _bad("target reference receipt differs")
    parent = _parent_edge(predecessor)
    if not any(row["instruction_rva"] == parent[0]["instruction"]["rva"] for row in supplied["references"]):
        _bad("parent edge does not join exhaustive reference scan")
    body = {"role": "relationship_defined_assertion_helper_second_callee_static_boundary", "entry_rva": _hex(_ENTRY),
            "atlas_record_sha256": _ATLAS, "body_size": _SIZE, "body_sha256": _BODY, "range_start_rva": _hex(_ENTRY),
            "range_size": _SIZE, "control_flow_graph_canonical_sha256": _CFG, "reviewed_points": _points(decoded),
            "direct_lua_calls": [], "staged_lua_dispatches": [], "call_r32_audit": _empty_register_calls(), "register_call_partition_complete": True,
            "ghidra_analysis_metadata": {"name": "FUN_0078c89f", "namespace": "Global", "name_source": "DEFAULT", "thunk": False, "metadata_only": True},
            "semantic_facts": {"relationship_defined_only": True, "analysis_labels_opaque": True, "source_semantic_names_assigned": False, "runtime_or_success_claimed": False}}
    return {"schema_version": SCHEMA_VERSION, "analysis_kind": ANALYSIS_KIND, "build_identity": dict(_mapping(facts.get("identity"), "program facts identity")),
            **prerequisites, "decoder": {"name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION, "architecture": "x86", "mode_bits": 32,
                                           "sealed_instruction_count": 2, "register_call_encoding_audit": [{"register": register, "encoding": f"ff{0xD0 + index:02x}"} for index, register in enumerate(_REGISTER_NAMES)]},
            "function_body": body, "control_flow_graph": _graph(decoded), "predecessor_parent_edges": parent, "native_calls": _native_calls(facts, image),
            "whole_atlas_reference_scan": supplied,
            "method": {"structural_boundary": "The receipt seals six decoded PE bytes, a virtual-only .data address operand, one predecessor edge, and the all-atlas finite reference partition.",
                       "not_claimed": ["analysis-label meaning, source identity, ABI, inputs, outputs, behavior, success, failure, or normal return", "runtime reachability, invocation, ordering, frequency, or effects", "contents or runtime meaning of the virtual-only PE-address operand", "computed, indirect, data, un-atlased, dynamic, or Lua-side references"]},
            "summary": {"reviewed_target_count": 1, "reviewed_target_bytes": _SIZE, "sealed_instruction_count": 2, "sealed_control_flow_graph_count": 1, "sealed_control_flow_graph_node_count": 2, "sealed_control_flow_graph_edge_count": 1, "native_direct_edge_count": 0, "direct_lua_call_count": 0, "staged_lua_dispatch_count": 0, "call_r32_count": 0, "opaque_indirect_control_count": 0, "bnd_prefixed_control_syntax_count": 0, "segment_qualified_memory_syntax_count": 0, "opaque_interrupt_syntax_count": 0, "non_pe_immediate_literal_count": 0, "pe_address_operand_count": 1, "target_reference_count": 3, "target_reference_owner_count": 3, "target_reference_direct_call_count": 3, "target_reference_memory_operand_count": 0, "target_reference_other_address_count": 0, "schema_violations": 0}}


def _normalize(operation: Any) -> Any:
    try:
        return operation()
    except NativeAssertionHelperSecondCalleeStaticBoundaryError:
        raise
    except Exception as exc:
        raise NativeAssertionHelperSecondCalleeStaticBoundaryError(str(exc)) from exc


def build_native_assertion_helper_second_callee_static_boundary(executable: Path, predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        for value, label in ((predecessor, "predecessor"), (direct, "direct"), (facts, "facts"), (inventory, "inventory")):
            _validate_json_tree(value, label)
        prerequisite = validate_native_lua_direct_call_census(executable, direct, facts, inventory=inventory)
        if prerequisite.get("status") != "verified" or prerequisite.get("evidence_sha256") != _DIRECT:
            _bad("direct-call exact prerequisite failed")
        data, image, digest = _load_executable(executable)
        if digest != _EXE or image.image_base != _BASE:
            _bad("executable identity or image base differs")
        offset = image.rva_to_file_offset(_ENTRY)
        if offset is None or data[offset:offset + _SIZE] != bytes.fromhex(_RAW):
            _bad("executable target bytes differ")
        decoder, _ = _decoder()
        rows = _decode(data[offset:offset + _SIZE])
        scan = _whole_atlas_reference_scan(data, image, decoder, facts)
        result = _evidence(predecessor, direct, facts, rows=rows, image=image, scan=scan)
        replay, replay_image, replay_digest = _load_executable(executable)
        if replay_digest != digest or replay != data or replay_image.image_base != _BASE:
            _bad("executable changed during exact rebuild")
        _assert_publication_safe(result)
        validate_native_assertion_helper_second_callee_static_boundary_structure(result, predecessor, direct, facts)
        return result
    return _normalize(run)


def encode_native_assertion_helper_second_callee_static_boundary(value: Mapping[str, Any]) -> str:
    def run() -> str:
        _validate_json_tree(value)
        return json.dumps(_mapping(value, "encoded evidence"), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    return _normalize(run)


def validate_native_assertion_helper_second_callee_static_boundary_structure(evidence: Mapping[str, Any], predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence)
        prerequisite = validate_native_lua_direct_call_structure(direct, facts)
        if prerequisite.get("status") != "structurally_verified" or prerequisite.get("evidence_sha256") != _DIRECT:
            _bad("direct-call structural prerequisite failed")
        expected = _evidence(predecessor, direct, facts)
        if not _same(evidence, expected):
            _bad("evidence structure differs")
        _assert_publication_safe(evidence)
        return {"schema_version": SCHEMA_VERSION, "analysis_kind": STRUCTURE_VERIFICATION_KIND, "status": "structurally_verified", "build_identity": dict(evidence["build_identity"]), "evidence_sha256": _canonical_sha256(evidence), "summary": dict(evidence["summary"])}
    return _normalize(run)


def validate_native_assertion_helper_second_callee_static_boundary(executable: Path, evidence: Mapping[str, Any], predecessor: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        rebuilt = build_native_assertion_helper_second_callee_static_boundary(executable, predecessor, direct, facts, inventory=inventory)
        if not _same(evidence, rebuilt):
            _bad("evidence differs from exact rebuild")
        return {"schema_version": SCHEMA_VERSION, "analysis_kind": VERIFICATION_KIND, "status": "verified", "build_identity": dict(rebuilt["build_identity"]), "evidence_sha256": _canonical_sha256(rebuilt), "summary": dict(rebuilt["summary"])}
    return _normalize(run)
