"""Exact, relationship-defined static boundary for query-handler's first callee.

All machine-code observations are deliberately retained as syntax receipts.  The
analysis label is provenance metadata, never an asserted source-level meaning.
"""
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
ANALYSIS_KIND = "pe_native_query_handler_first_callee_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_QUERY_HANDLER = "742e341a855de34731177afd53b385c67fbd64f3d277fedf8ba6c8e9bbf61705"
_ENTRY = 0x3584B0
_BODY = "93bb41b37798fb0a60379b4b50ede0bb7a6d56d2b83519ccf07f640b3e220fc7"
_ATLAS = "f12f7540169b9978ec62ba6c80f46b98f37a143c798487a2eec78a9088b688b8"
_CFG = "d28e5db8f58f83bb0cc57183fade47aa55a2f5e8be0dd540e1dd6cfc032b3d27"
_PREDECESSOR = (0x38BC0F, "e89cc8fcff", _ENTRY)


class NativeQueryHandlerFirstCalleeStaticBoundaryError(RuntimeError):
    """The sealed relationship-defined callee boundary cannot be reproduced."""


def _point(role: str, rva: int, encoded: str) -> dict[str, Any]:
    return {"role": role, "rva": rva, "encoded": bytes.fromhex(encoded), "api": None,
            "meaning": {"operation": "decoded_instruction", "source_semantic_names_assigned": False}}


_POINTS = tuple(_point(f"instruction_{index:02d}", rva, encoded) for index, (rva, encoded) in enumerate((
    (0x3584B0, "68b0297700"), (0x3584B5, "64ff3500000000"), (0x3584BC, "8b442410"),
    (0x3584C0, "896c2410"), (0x3584C4, "8d6c2410"), (0x3584C8, "2be0"),
    (0x3584CA, "53"), (0x3584CB, "56"), (0x3584CC, "57"), (0x3584CD, "a1283f8900"),
    (0x3584D2, "3145fc"), (0x3584D5, "33c5"), (0x3584D7, "50"), (0x3584D8, "8965e8"),
    (0x3584DB, "ff75f8"), (0x3584DE, "8b45fc"), (0x3584E1, "c745fcfeffffff"),
    (0x3584E8, "8945f8"), (0x3584EB, "8d45f0"), (0x3584EE, "64a300000000"),
    (0x3584F4, "f2c3"),
)))
_FUNCTION = {
    "role": "relationship_defined_query_handler_first_callee_static_boundary", "entry_rva": _ENTRY,
    "body_size": 70, "body_sha256": _BODY, "cfg_canonical_sha256": _CFG,
    "direct_calls": [], "staged_dispatches": [], "call_r32": {}, "points": list(_POINTS),
    "semantic_facts": {"analysis_label": "__SEH_prolog4", "analysis_label_only": True,
                       "relationship_defined_by_predecessor_edge": True,
                       "source_semantic_names_assigned": False, "runtime_or_success_claimed": False},
}
_METHOD = {
    "structural_boundary": "PE-free validation rebuilds every finite prerequisite, instruction, CFG, opaque operand syntax, predecessor, and owner-partition record. Exact bytes and whole-atlas traversal require the sealed executable.",
    "not_claimed": [
        "callee purpose, SEH, prolog, exception, stack, register, security-cookie, ABI, argument meaning, state mutation, success, or normal return semantics",
        "runtime reachability, invocation, order, frequency, source identity, or runtime effect",
        "contents or semantics of segment-relative or absolute operands or their pointed-to data",
        "dynamic, computed, indirect, data, un-atlased, or Lua-side references",
    ],
}


def _same(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _facts_identity(facts: Mapping[str, Any]) -> dict[str, Any]:
    identity = _source_identity(facts, "pe_ghidra_program_facts", _FACTS, "program facts")
    summary = _mapping(facts.get("summary"), "program facts summary")
    return {**identity, "function_count": summary.get("function_count"), "body_range_count": summary.get("body_range_count"), "function_body_bytes": summary.get("function_body_bytes")}


def _preflight(query_handler: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]):
    identity = _mapping(facts.get("identity"), "program facts identity")
    if identity.get("executable_sha256") != _EXE:
        raise NativeQueryHandlerFirstCalleeStaticBoundaryError("program facts are not the reviewed profile")
    if not _same(query_handler.get("build_identity"), dict(identity)) or not _same(direct.get("build_identity"), dict(identity)):
        raise NativeQueryHandlerFirstCalleeStaticBoundaryError("prerequisite build identity differs")
    if _query_handler_canonical_sha256(query_handler) != _QUERY_HANDLER:
        raise NativeQueryHandlerFirstCalleeStaticBoundaryError("query-handler prerequisite receipt differs")
    return (_facts_identity(facts), _source_identity(direct, DIRECT_KIND, _DIRECT, "direct calls"), _source_identity(query_handler, QUERY_HANDLER_KIND, _QUERY_HANDLER, "query-handler boundary"))


def _profile(facts: Mapping[str, Any]) -> dict[str, Any]:
    refs = []
    for raw in _array(facts.get("ghidra_declared_direct_calls"), "declared direct calls"):
        edge = _mapping(raw, "declared direct call")
        if _rva(edge.get("target_entry_rva"), "target") == _ENTRY:
            site, target, owner = (_rva(edge.get(key), key) for key in ("instruction_rva", "target_rva", "source_entry_rva"))
            refs.append({"instruction_rva": site, "owner_entry_rva": owner, "target_rva": target, "encoded": (b"\xe8" + int(target - (site + 5)).to_bytes(4, "little", signed=True)).hex(), "operand_index": 0})
    refs.sort(key=lambda item: item["instruction_rva"])
    if len(refs) != 66 or len({item["owner_entry_rva"] for item in refs}) != 66:
        raise NativeQueryHandlerFirstCalleeStaticBoundaryError("declared incoming owner partition differs")
    if not any((item["instruction_rva"], item["owner_entry_rva"]) == (0x38BC0F, 0x38BC08) for item in refs):
        raise NativeQueryHandlerFirstCalleeStaticBoundaryError("relationship predecessor absent")
    return {"executable_sha256": _EXE, "functions": [_FUNCTION], "literals": [], "native_edges": [], "target_references": refs}


def _owner_partition(refs: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = [{"owner_entry_rva": item["owner_entry_rva"], "owner_atlas_record_sha256": item["owner_atlas_record_sha256"], "reference_count": 1} for item in refs]
    if len(result) != 66 or len({item["owner_entry_rva"] for item in result}) != 66:
        raise NativeQueryHandlerFirstCalleeStaticBoundaryError("owner partition differs")
    return result


def _scan(value: Mapping[str, Any], *, require_partition: bool) -> dict[str, Any]:
    scan = dict(_mapping(value, "reference scan")); scan["aggregates"] = dict(_mapping(scan.get("aggregates"), "reference aggregates"))
    # The inherited traversal is a broader producer and reports two counts that
    # are outside this sealed schema.  They are normalized only before an exact
    # executable rebuild; supplied evidence always takes the strict path below.
    if not require_partition:
        scan["aggregates"].pop("returned_callback_reference_count", None)
        scan["aggregates"].pop("alternate_owner_reference_count", None)
    keys = {"target_rvas", "target_vas", "scope", "references", "aggregates"}
    if "owner_partition" in scan: keys.add("owner_partition")
    _exact_keys(scan, keys, "reference scan")
    expected_aggregates = {"reference_count": 66, "direct_call_count": 66, "comparison_count": 0, "other_address_count": 0, "memory_operand_count": 0, "owner_count": 66}
    refs = _array(scan.get("references"), "references")
    if len(refs) != 66 or scan["aggregates"] != expected_aggregates:
        raise NativeQueryHandlerFirstCalleeStaticBoundaryError("reference partition differs")
    for ref in refs:
        item = _mapping(ref, "reference")
        _exact_keys(item, {"instruction_rva", "instruction_size", "instruction_sha256", "owner_entry_rva", "owner_atlas_record_sha256", "target_rva", "target_atlas_record_sha256", "target_va", "operand_class", "operand_index", "use_class", "call_form", "ghidra_declared_direct_edge"}, "reference")
        if (item.get("instruction_size"), item.get("operand_index"), item.get("operand_class"), item.get("use_class"), item.get("call_form")) != (5, 0, "immediate", "direct_call", "x86_relative_near_call_e8"):
            raise NativeQueryHandlerFirstCalleeStaticBoundaryError("incoming reference syntax differs")
        if type(item.get("owner_entry_rva")) is not str or type(item.get("owner_atlas_record_sha256")) is not str or item.get("ghidra_declared_direct_edge") is None:
            raise NativeQueryHandlerFirstCalleeStaticBoundaryError("incoming reference identity differs")
    partition = _owner_partition(refs); supplied = _array(scan.get("owner_partition", []), "owner partition")
    for item in supplied: _exact_keys(_mapping(item, "owner partition record"), {"owner_entry_rva", "owner_atlas_record_sha256", "reference_count"}, "owner partition record")
    if require_partition and ("owner_partition" not in scan or not _same(supplied, partition)):
        raise NativeQueryHandlerFirstCalleeStaticBoundaryError("owner partition differs")
    scan["owner_partition"] = partition
    return scan


def _expected_scan(facts: Mapping[str, Any], direct: Mapping[str, Any]) -> dict[str, Any]:
    expected = _expected_reference_scan(facts, direct, _profile(facts))
    expected["aggregates"] = {"reference_count": 66, "direct_call_count": 66, "comparison_count": 0, "other_address_count": 0, "memory_operand_count": 0, "owner_count": 66}
    expected["owner_partition"] = _owner_partition(expected["references"])
    return _scan(expected, require_partition=True)


def _section(image: Any, rva: int, *, name: str, characteristics: str, writable: bool, backed: bool) -> None:
    section = next((item for item in image.sections if item.virtual_address <= rva < item.virtual_address + item.virtual_size), None)
    if section is None or (section.name, _hex(section.characteristics), bool(section.characteristics & 0x80000000), image.rva_to_file_offset(rva) is not None) != (name, characteristics, writable, backed):
        raise NativeQueryHandlerFirstCalleeStaticBoundaryError("opaque operand section span differs")


def _opaque_syntax_records(image: Any | None, instructions: Any | None = None) -> list[dict[str, Any]]:
    records = [
        {"role": "opaque_absolute_immediate_push_syntax", "instruction": {"rva": "0x003584b0", "size": 5, "sha256": "2cd70ac0568a662c5eea274ddc21557b6b6f72535521169154fbd399707a63fb"}, "operand_va": "0x007729b0", "operand_rva": "0x003729b0", "section_name": ".text", "section_characteristics": "0x60000020", "section_writable": False, "file_backed": True, "contents_or_semantics_opaque": True},
        {"role": "opaque_segment_relative_memory_push_syntax", "instruction": {"rva": "0x003584b5", "size": 7, "sha256": "f3644f7c8b1079079fa7f26620a659aaa65d709a9f3c5ffc8cc0d5ab4d6757c1"}, "source_memory_operand_index": 0, "segment_register": "fs", "base_register": None, "index_register": None, "displacement": 0, "contents_or_semantics_opaque": True},
        {"role": "opaque_absolute_memory_read_syntax", "instruction": {"rva": "0x003584cd", "size": 5, "sha256": "fb411162b29d74c22c65bab2722f82b7eb48e520f5e230139a6fdff51960ded6"}, "operand_va": "0x00893f28", "operand_rva": "0x00493f28", "section_name": ".data", "section_characteristics": "0xc0000040", "section_writable": True, "file_backed": True, "contents_or_semantics_opaque": True},
        {"role": "opaque_segment_relative_memory_write_syntax", "instruction": {"rva": "0x003584ee", "size": 6, "sha256": "1edae75bd6fc653f73e571e9c91820e2459779cab75b8f113984abe23e3d65f3"}, "destination_memory_operand_index": 0, "segment_register": "fs", "base_register": None, "index_register": None, "displacement": 0, "contents_or_semantics_opaque": True},
        {"role": "opaque_bnd_prefixed_return_syntax", "instruction": {"rva": "0x003584f4", "size": 2, "sha256": "ce39fa6fe0288ed17651ce2ac8b88926f8492a4ae7b7def1249a7038a163ed85"}, "encoded_prefix_hex": "f2", "contents_or_semantics_opaque": True},
    ]
    if image is not None:
        _section(image, 0x3729B0, name=".text", characteristics="0x60000020", writable=False, backed=True)
        _section(image, 0x493F28, name=".data", characteristics="0xc0000040", writable=True, backed=True)
    if instructions is not None:
        import capstone
        import capstone.x86_const as x86
        by_rva = {item.address - instructions[0].address + _ENTRY: item for item in instructions}
        push = by_rva.get(0x3584B0)
        if push is None or push.id != x86.X86_INS_PUSH or len(push.operands) != 1 or push.operands[0].type != x86.X86_OP_IMM or (int(push.operands[0].imm) & 0xffffffff) != 0x007729B0:
            raise NativeQueryHandlerFirstCalleeStaticBoundaryError("absolute immediate push operand syntax differs")
        absolute_read = by_rva.get(0x3584CD)
        read_operand = None if absolute_read is None or absolute_read.id != x86.X86_INS_MOV or len(absolute_read.operands) != 2 else absolute_read.operands[1]
        if read_operand is None or read_operand.type != x86.X86_OP_MEM or read_operand.mem.segment != x86.X86_REG_INVALID or read_operand.mem.base != x86.X86_REG_INVALID or read_operand.mem.index != x86.X86_REG_INVALID or read_operand.mem.disp != 0x00893F28 or not (read_operand.access & capstone.CS_AC_READ):
            raise NativeQueryHandlerFirstCalleeStaticBoundaryError("absolute memory read operand syntax differs")
        checks = ((0x3584B5, x86.X86_INS_PUSH, 0, capstone.CS_AC_READ, "source_memory_operand_index"), (0x3584EE, x86.X86_INS_MOV, 0, capstone.CS_AC_WRITE, "destination_memory_operand_index"))
        for rva, opcode, index, access, _ in checks:
            item = by_rva.get(rva); operand = None if item is None or item.id != opcode or len(item.operands) < 1 else item.operands[index]
            if operand is None or operand.type != x86.X86_OP_MEM or operand.mem.segment != x86.X86_REG_FS or operand.mem.base != x86.X86_REG_INVALID or operand.mem.index != x86.X86_REG_INVALID or operand.mem.disp != 0 or not (operand.access & access):
                raise NativeQueryHandlerFirstCalleeStaticBoundaryError("segment-relative operand syntax differs")
        terminal = by_rva.get(0x3584F4)
        if terminal is None or terminal.id != x86.X86_INS_RET or bytes(terminal.bytes) != bytes.fromhex("f2c3") or terminal.size != 2:
            raise NativeQueryHandlerFirstCalleeStaticBoundaryError("BND-prefixed return bytes differ")
    return records


def _records(data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any]):
    import capstone
    import capstone.x86_const as x86
    from src.observatory.native_lua_cclosure_setfield_publications import _decode_range
    function = _atlas_functions(facts).get(_ENTRY)
    if function is None or function.get("body_size") != 70 or function.get("body_sha256") != _BODY or atlas_record_sha256(function) != _ATLAS:
        raise NativeQueryHandlerFirstCalleeStaticBoundaryError("target atlas identity differs")
    decoder.detail = True; instructions = _decode_range(data, image, _ENTRY, 70, decoder)
    if hashlib.sha256(b"".join(bytes(item.bytes) for item in instructions)).hexdigest() != _BODY:
        raise NativeQueryHandlerFirstCalleeStaticBoundaryError("target bytes differ")
    graph = _with_edi_writes(_enhanced_cfg(instructions, image.image_base, (_ENTRY, 70), capstone, x86), instructions, x86); graph["caller_entry_rva"] = _hex(_ENTRY)
    if _canonical_sha256(graph) != _CFG: raise NativeQueryHandlerFirstCalleeStaticBoundaryError("target CFG differs")
    by_rva = {item.address - image.image_base: item for item in instructions}
    body = {"role": _FUNCTION["role"], "entry_rva": _hex(_ENTRY), "atlas_record_sha256": _ATLAS, "body_size": 70, "body_sha256": _BODY, "range_start_rva": _hex(_ENTRY), "range_size": 70, "control_flow_graph_canonical_sha256": _CFG, "reviewed_points": [_point_record(by_rva[spec["rva"]], image.image_base, spec) for spec in _POINTS], "direct_lua_calls": [], "staged_lua_dispatches": [], "call_r32_audit": _call_r32_audit(instructions, _FUNCTION), "register_call_partition_complete": True, "semantic_facts": dict(_FUNCTION["semantic_facts"])}
    return [body], [graph], _opaque_syntax_records(image, instructions)


def _predecessor(query_handler: Mapping[str, Any], scan: Mapping[str, Any]) -> dict[str, Any]:
    direct = _array(_mapping(query_handler.get("native_calls"), "query-handler native calls").get("direct"), "query-handler native edges")
    matches = [dict(_mapping(item, "predecessor edge")) for item in direct if (_rva(_mapping(item, "predecessor edge").get("source_entry_rva"), "source"), _rva(_mapping(_mapping(item, "predecessor edge").get("instruction"), "instruction").get("rva"), "site"), _rva(_mapping(item, "predecessor edge").get("target_entry_rva"), "target")) == (0x38BC08, _PREDECESSOR[0], _ENTRY)]
    if len(matches) != 1: raise NativeQueryHandlerFirstCalleeStaticBoundaryError("relationship predecessor differs")
    edge = matches[0]; instruction = _mapping(edge.get("instruction"), "predecessor instruction"); encoded = bytes.fromhex(_PREDECESSOR[1])
    if (instruction.get("size"), instruction.get("sha256")) != (len(encoded), hashlib.sha256(encoded).hexdigest()): raise NativeQueryHandlerFirstCalleeStaticBoundaryError("relationship predecessor instruction bytes differ")
    ref = next((item for item in _array(scan.get("references"), "references") if item["instruction_rva"] == "0x0038bc0f"), None)
    if ref is None or (ref.get("owner_entry_rva"), ref.get("instruction_size"), ref.get("instruction_sha256"), ref.get("operand_class"), ref.get("use_class"), ref.get("call_form")) != ("0x0038bc08", instruction.get("size"), instruction.get("sha256"), "immediate", "direct_call", "x86_relative_near_call_e8") or ref.get("owner_atlas_record_sha256") != edge.get("source_atlas_record_sha256") or ref.get("target_atlas_record_sha256") != edge.get("target_atlas_record_sha256") or not _same(ref.get("ghidra_declared_direct_edge"), edge.get("ghidra_declared_direct_edge")):
        raise NativeQueryHandlerFirstCalleeStaticBoundaryError("relationship predecessor scan join differs")
    return edge


def _decoder_contract() -> dict[str, Any]:
    return {"name": "capstone", "version": SUPPORTED_CAPSTONE_VERSION, "architecture": "x86", "mode_bits": 32, "sealed_instruction_count": 21, "register_call_encoding_audit": [{"register": name, "encoding": f"ff{0xd0 + index:02x}"} for index, name in enumerate(_REGISTER_NAMES)]}


def _expected_body(facts: Mapping[str, Any]) -> dict[str, Any]:
    if _atlas_functions(facts).get(_ENTRY) is None: raise NativeQueryHandlerFirstCalleeStaticBoundaryError("target absent")
    return {"role": _FUNCTION["role"], "entry_rva": _hex(_ENTRY), "atlas_record_sha256": _ATLAS, "body_size": 70, "body_sha256": _BODY, "range_start_rva": _hex(_ENTRY), "range_size": 70, "control_flow_graph_canonical_sha256": _CFG, "reviewed_points": [_expected_point_record(item) for item in _POINTS], "direct_lua_calls": [], "staged_lua_dispatches": [], "call_r32_audit": [{"register": name, "call_rvas": []} for name in _REGISTER_NAMES], "register_call_partition_complete": True, "semantic_facts": _FUNCTION["semantic_facts"]}


def _summary(_: Mapping[str, Any]) -> dict[str, Any]:
    return {"reviewed_query_handler_first_callee_count": 1, "reviewed_query_handler_first_callee_bytes": 70, "sealed_instruction_count": 21, "sealed_control_flow_graph_count": 1, "sealed_control_flow_graph_node_count": 21, "sealed_control_flow_graph_edge_count": 20, "direct_lua_call_count": 0, "staged_lua_dispatch_count": 0, "call_r32_count": 0, "literal_count": 0, "native_direct_edge_count": 0, "opaque_operand_syntax_count": 5, "query_handler_predecessor_edge_count": 1, "target_reference_count": 66, "target_reference_direct_call_count": 66, "target_reference_comparison_count": 0, "target_reference_other_address_count": 0, "target_reference_memory_operand_count": 0, "target_reference_owner_count": 66, "schema_violations": 0}


def build_native_query_handler_first_callee_static_boundary(executable: Path, query_handler_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    try:
        for value, label in ((query_handler_static_boundary, "query handler"), (direct_calls, "direct calls"), (program_facts, "facts"), (inventory, "inventory")): _validate_json_tree(value, label)
        receipt = validate_native_lua_direct_call_census(executable, direct_calls, program_facts, inventory=inventory)
        if receipt.get("status") != "verified" or receipt.get("evidence_sha256") != _DIRECT: raise NativeQueryHandlerFirstCalleeStaticBoundaryError("direct-call prerequisite differs")
        atlas, direct, query_handler = _preflight(query_handler_static_boundary, direct_calls, program_facts); data, image, digest = _load_executable(executable)
        if digest != _EXE: raise NativeQueryHandlerFirstCalleeStaticBoundaryError("executable differs")
        decoder, _ = _decoder(); bodies, graphs, opaque = _records(data, image, decoder, program_facts); scan = _scan(_whole_atlas_reference_scan(data, image, decoder, program_facts, direct_calls, _profile(program_facts)), require_partition=False)
        result = {"schema_version": SCHEMA_VERSION, "analysis_kind": ANALYSIS_KIND, "build_identity": dict(_mapping(program_facts.get("identity"), "identity")), "atlas": atlas, "direct_call_census": direct, "query_handler_static_boundary": query_handler, "query_handler_first_callee_predecessor_edge": _predecessor(query_handler_static_boundary, scan), "decoder": _decoder_contract(), "function_bodies": bodies, "control_flow_graphs": graphs, "native_calls": {"direct": [], "opaque_instruction_syntax": opaque}, "whole_atlas_reference_scan": scan, "method": _METHOD}
        result["summary"] = _summary(result); _assert_publication_safe(result)
        if _load_executable(executable)[2] != digest: raise NativeQueryHandlerFirstCalleeStaticBoundaryError("executable changed")
        validate_native_query_handler_first_callee_static_boundary_structure(result, query_handler_static_boundary, direct_calls, program_facts); return result
    except NativeQueryHandlerFirstCalleeStaticBoundaryError: raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassFactoryChainError, NativeLuaClassReturnHelperChainError, PEAnchorError, OSError) as exc: raise NativeQueryHandlerFirstCalleeStaticBoundaryError(str(exc)) from exc


def validate_native_query_handler_first_callee_static_boundary_structure(evidence: Mapping[str, Any], query_handler_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any]) -> dict[str, Any]:
    try:
        for value, label in ((evidence, "evidence"), (query_handler_static_boundary, "query handler"), (direct_calls, "direct calls"), (program_facts, "facts")): _validate_json_tree(value, label)
        receipt = validate_native_lua_direct_call_structure(direct_calls, program_facts)
        if receipt.get("status") != "structurally_verified" or receipt.get("evidence_sha256") != _DIRECT: raise NativeQueryHandlerFirstCalleeStaticBoundaryError("direct-call prerequisite differs")
        atlas, direct, query_handler = _preflight(query_handler_static_boundary, direct_calls, program_facts); evidence = _mapping(evidence, "evidence")
        _exact_keys(evidence, {"schema_version", "analysis_kind", "build_identity", "atlas", "direct_call_census", "query_handler_static_boundary", "query_handler_first_callee_predecessor_edge", "decoder", "function_bodies", "control_flow_graphs", "native_calls", "whole_atlas_reference_scan", "method", "summary"}, "evidence")
        if type(evidence.get("schema_version")) is not int or evidence.get("schema_version") != SCHEMA_VERSION or evidence.get("analysis_kind") != ANALYSIS_KIND: raise NativeQueryHandlerFirstCalleeStaticBoundaryError("schema differs")
        if not all((_same(evidence.get("build_identity"), dict(_mapping(program_facts.get("identity"), "identity"))), _same(evidence.get("atlas"), atlas), _same(evidence.get("direct_call_census"), direct), _same(evidence.get("query_handler_static_boundary"), query_handler), _same(evidence.get("decoder"), _decoder_contract()), _same(evidence.get("method"), _METHOD))): raise NativeQueryHandlerFirstCalleeStaticBoundaryError("pinned prerequisite differs")
        bodies = _array(evidence.get("function_bodies"), "bodies")
        if len(bodies) != 1 or not _same(bodies[0], _expected_body(program_facts)): raise NativeQueryHandlerFirstCalleeStaticBoundaryError("body differs")
        graphs = _validated_graphs({"control_flow_graphs": evidence.get("control_flow_graphs")}, _atlas_functions(program_facts))
        if set(graphs) != {_ENTRY} or _canonical_sha256(graphs[_ENTRY][0]) != _CFG or graphs[_ENTRY][0].get("node_count") != 21 or graphs[_ENTRY][0].get("edge_count") != 20: raise NativeQueryHandlerFirstCalleeStaticBoundaryError("CFG differs")
        nodes = {_rva(item.get("rva"), "CFG node rva"): item for item in _array(graphs[_ENTRY][0].get("nodes"), "CFG nodes")}
        for point in _array(bodies[0].get("reviewed_points"), "reviewed points"):
            node = nodes.get(_rva(point.get("rva"), "point rva"))
            if node is None or (point.get("size"), point.get("sha256")) != (node.get("size"), node.get("sha256")): raise NativeQueryHandlerFirstCalleeStaticBoundaryError("reviewed point CFG join differs")
        scan = _scan(_mapping(evidence.get("whole_atlas_reference_scan"), "scan"), require_partition=True)
        expected_calls = {"direct": [], "opaque_instruction_syntax": _opaque_syntax_records(None)}
        if not _same(scan, _expected_scan(program_facts, direct_calls)) or not _same(evidence.get("native_calls"), expected_calls) or not _same(evidence.get("query_handler_first_callee_predecessor_edge"), _predecessor(query_handler_static_boundary, scan)) or not _same(evidence.get("summary"), _summary(evidence)): raise NativeQueryHandlerFirstCalleeStaticBoundaryError("cross-check differs")
        _assert_publication_safe(evidence)
        return {"schema_version": SCHEMA_VERSION, "analysis_kind": STRUCTURE_VERIFICATION_KIND, "status": "structurally_verified", "build_identity": dict(evidence["build_identity"]), "evidence_sha256": _canonical_sha256(evidence), "summary": dict(evidence["summary"])}
    except NativeQueryHandlerFirstCalleeStaticBoundaryError: raise
    except (NativeLuaCClosurePublicationError, NativeLuaDirectCallError, NativeLuaClassFactoryChainError, NativeLuaClassReturnHelperChainError) as exc: raise NativeQueryHandlerFirstCalleeStaticBoundaryError(str(exc)) from exc


def validate_native_query_handler_first_callee_static_boundary(executable: Path, evidence: Mapping[str, Any], query_handler_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    rebuilt = build_native_query_handler_first_callee_static_boundary(executable, query_handler_static_boundary, direct_calls, program_facts, inventory=inventory)
    if not _same(evidence, rebuilt): raise NativeQueryHandlerFirstCalleeStaticBoundaryError("evidence differs from exact rebuild")
    return {"schema_version": SCHEMA_VERSION, "analysis_kind": VERIFICATION_KIND, "status": "verified", "build_identity": dict(rebuilt["build_identity"]), "evidence_sha256": _canonical_sha256(rebuilt), "summary": dict(rebuilt["summary"])}


def encode_native_query_handler_first_callee_static_boundary(value: Mapping[str, Any]) -> str:
    try: _validate_json_tree(value); return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    except NativeLuaCClosurePublicationError as exc: raise NativeQueryHandlerFirstCalleeStaticBoundaryError(str(exc)) from exc
