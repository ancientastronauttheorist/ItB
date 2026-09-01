"""Exact cleanup callback chain for the native Lua ``property`` table."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError,
    _array,
    _assert_publication_safe,
    _atlas_functions,
    _canonical_bytes,
    _canonical_sha256,
    _decode_range,
    _exact_keys,
    _hex,
    _mapping,
    _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_cclosure_table_key_provenance import _enhanced_cfg
from src.observatory.native_lua_direct_calls import (
    NativeLuaDirectCallError,
    _decoder,
    _load_executable,
)
from src.observatory.native_lua_property_consumer_chain import _with_edi_writes
from src.observatory.native_lua_property_initializer_chain import (
    ANALYSIS_KIND as INITIALIZER_ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND as INITIALIZER_STRUCTURE_VERIFICATION_KIND,
    VERIFICATION_KIND as INITIALIZER_VERIFICATION_KIND,
    NativeLuaPropertyInitializerChainError,
    validate_native_lua_property_initializer_chain,
    validate_native_lua_property_initializer_chain_structure,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_property_cleanup_chain"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
_LUA_LIBRARY = "lua5.1.dll"
_WRITABLE = 0x80000000


class NativeLuaPropertyCleanupChainError(RuntimeError):
    """Raised when the sealed cleanup callback chain is stale or malformed."""


_PROFILE: dict[str, Any] = {
    "executable_sha256": "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9",
    "initializer_canonical_sha256": "b76b3d46d30da4801a3bc4f67be78d3818f847557a0b275f6048120873b44bc4",
    "functions": [
        {
            "role": "cleanup_registry_helper", "entry_rva": 0x002E9F00,
            "body_size": 64,
            "body_sha256": "65d5712025be3aeb9d3bec9845edf4aec64fb7aaaf04ea706b5482d8d43305eb",
            "cfg_sha256": "5078c6cb6ca9031f04531df4b21f8d9e35406601dd301f90da5e0a582d14f888",
            "node_count": 28, "edge_count": 29,
            "calls": [(0x002E9F17, "lua_pushlightuserdata"), (0x002E9F1E, "lua_pushnil"), (0x002E9F2A, "lua_rawset")],
        },
        {
            "role": "cleanup_callback", "entry_rva": 0x002E9F40,
            "body_size": 137,
            "body_sha256": "42a2e05350e953d42a76c65c17f665e384fd53bc3ef4e1d578681a10c48008ba",
            "cfg_sha256": "9296c21c4acc66e0cc63554a3fdb5dd27cf78d3b61bbf975b36a5af094a0640f",
            "node_count": 55, "edge_count": 57,
            "calls": [(0x002E9F4B, "lua_touserdata"), (0x002E9F59, "lua_pushstring"), (0x002E9F62, "lua_gettable"), (0x002E9F6B, "lua_type"), (0x002E9F7B, "lua_settop"), (0x002E9F89, "lua_pushvalue"), (0x002E9F94, "lua_call")],
        },
    ],
    "literal": {
        "role": "finalize_lookup_key", "text": "__finalize", "rva": 0x0043C50C,
        "nul_terminated_bytes_sha256": "2da9eac9965b6b70aa210a588888733805c3214ecd627e37afd1aa1909b100b7",
        "section_name": ".rdata", "section_rva": 0x003D6000,
        "section_characteristics": 0x40000040,
    },
}

_METHOD = {
    "accepted_chain": "One exact property initializer cleanup-closure producer is joined to a cleanup callback, its registry-nil helper, complete direct Lua-call partitions, and an exhaustive two-target operand scan.",
    "lua51_abi_premises": ["Lua registry index -10000 has Lua 5.1 meaning", "lua_type zero denotes nil", "lua_gettable is metamethod-aware", "lua_rawset bypasses table metamethod dispatch"],
    "structural_boundary": "PE-free validation recursively structure-verifies the initializer and replays static body, direct-census, literal, helper-edge, placement, and target-reference joins. Exact validation additionally redecodes both PE bodies and every atlas range.",
    "not_claimed": [
        "runtime reachability, execution, ordering, frequency, or persistence",
        "successful lookup or invocation, callback callability, runtime __gc dispatch, finalization, destruction, or freeing",
        "allocation origin, registry-key meaning, native pointer type, ownership, or lifetime",
        "computed, indirect, data, un-atlased, or Lua-side references",
        "source-level property, class, ownership, or cleanup equivalence",
    ],
}


def _direct_records(direct_calls: Mapping[str, Any], expected: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = [
        _mapping(item, "direct census record") for item in _array(direct_calls.get("records"), "direct census records")
        if isinstance(item, Mapping) and _rva(item.get("entry_rva"), "direct entry") == expected["entry_rva"]
    ]
    if len(records) != 1:
        raise NativeLuaPropertyCleanupChainError("reviewed direct census body is not unique")
    record = records[0]
    calls = []
    for raw in _array(record.get("direct_lua_import_calls"), "direct Lua calls"):
        call = _mapping(raw, "direct Lua call")
        if call.get("library") != _LUA_LIBRARY or call.get("call_form") != "x86_absolute_iat_indirect_call_ff15":
            raise NativeLuaPropertyCleanupChainError("cleanup Lua call form changed")
        calls.append({
            "rva": call["call_rva"], "api": call["import_name"],
            "instruction_size": call["instruction_size"], "instruction_sha256": call["instruction_sha256"],
        })
    wanted = [( _hex(rva), api) for rva, api in expected["calls"]]
    if [(item["rva"], item["api"]) for item in calls] != wanted:
        raise NativeLuaPropertyCleanupChainError("cleanup direct Lua-call partition changed")
    return calls


def _body_records(program_facts: Mapping[str, Any], direct_calls: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions = _atlas_functions(program_facts)
    result = []
    for expected in _PROFILE["functions"]:
        function = functions.get(expected["entry_rva"])
        if function is None or function.get("thunk") is not False or function.get("body_size") != expected["body_size"] or function.get("body_sha256") != expected["body_sha256"]:
            raise NativeLuaPropertyCleanupChainError("cleanup atlas body identity changed")
        result.append({
            "role": expected["role"], "entry_rva": _hex(expected["entry_rva"]),
            "atlas_record_sha256": atlas_record_sha256(function), "body_size": expected["body_size"],
            "body_sha256": expected["body_sha256"], "control_flow_graph_canonical_sha256": expected["cfg_sha256"],
            "control_flow_graph_node_count": expected["node_count"], "control_flow_graph_edge_count": expected["edge_count"],
            "direct_lua_calls": _direct_records(direct_calls, expected), "staged_lua_call_count": 0,
        })
    return result


def _literal_expected() -> dict[str, Any]:
    item = _PROFILE["literal"]
    return {"role": item["role"], "text": item["text"], "rva": _hex(item["rva"]), "byte_length_excluding_nul": len(item["text"]), "bytes_including_nul": len(item["text"]) + 1, "nul_terminated_bytes_sha256": item["nul_terminated_bytes_sha256"], "section_name": item["section_name"], "section_rva": _hex(item["section_rva"]), "section_characteristics": _hex(item["section_characteristics"]), "section_writable": False}


def _literal_exact(data: bytes, image: Any) -> dict[str, Any]:
    item = _PROFILE["literal"]; offset = image.rva_to_file_offset(item["rva"])
    if offset is None: raise NativeLuaPropertyCleanupChainError("finalize literal is not file backed")
    end = data.find(b"\0", offset, offset + 257)
    if end < 0: raise NativeLuaPropertyCleanupChainError("finalize literal is not NUL terminated")
    raw = data[offset:end + 1]; section = image.section_for_offset(offset)
    if raw != item["text"].encode("ascii") + b"\0" or hashlib.sha256(raw).hexdigest() != item["nul_terminated_bytes_sha256"] or section is None or section.name != item["section_name"] or section.virtual_address != item["section_rva"] or section.characteristics != item["section_characteristics"] or section.characteristics & _WRITABLE:
        raise NativeLuaPropertyCleanupChainError("finalize literal identity changed")
    return _literal_expected()


def _initializer_placement(initializer: Mapping[str, Any]) -> dict[str, Any]:
    if initializer.get("analysis_kind") != INITIALIZER_ANALYSIS_KIND or _canonical_sha256(initializer) != _PROFILE["initializer_canonical_sha256"]:
        raise NativeLuaPropertyCleanupChainError("initializer prerequisite identity changed")
    placement = _mapping(_mapping(initializer.get("semantics"), "initializer semantics").get("cleanup_placement"), "cleanup placement")
    required = {"key": "__gc", "callback_entry_rva": "0x002e9f40", "closure_upvalue_count": 0, "setter": "lua_setfield", "table_index": -2, "callback_behavior_normalized": False}
    if dict(placement) != required: raise NativeLuaPropertyCleanupChainError("initializer cleanup placement changed")
    wanted = {"cleanup_upvalue_count_zero", "cleanup_callback_target", "create_cleanup_closure", "cleanup_key_pointer", "cleanup_table_index_minus_two", "set_cleanup_field"}
    points = [dict(_mapping(p, "initializer point")) for p in _array(initializer.get("path_points"), "initializer points") if isinstance(p, Mapping) and p.get("role") in wanted]
    if {p["role"] for p in points} != wanted: raise NativeLuaPropertyCleanupChainError("initializer cleanup point partition changed")
    return {"initializer_entry_rva": "0x002ea2d0", "initializer_atlas_record_sha256": "9bebfe870176e21574adce7ab56dc323785c19e0cdb73d03afc267a3edf84c1f", "placement": required, "producer_points": sorted(points, key=lambda p: int(p["rva"], 16))}


def _reference_rows(program_facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions = _atlas_functions(program_facts)
    rows = [
        (0x002E9FA0, 0x002E9F40, 0x002E9F00, "callback_direct_helper_call", "e85bffffff"),
        (0x002EA32B, 0x002EA2D0, 0x002E9F40, "initializer_cleanup_closure_producer", "68409f6e00"),
    ]
    result=[]
    for rva, owner, target, use, encoded in rows:
        function=functions.get(owner)
        if function is None: raise NativeLuaPropertyCleanupChainError("target-reference owner is absent")
        raw=bytes.fromhex(encoded)
        result.append({"instruction_rva": _hex(rva), "instruction_size": len(raw), "instruction_sha256": hashlib.sha256(raw).hexdigest(), "owner_entry_rva": _hex(owner), "owner_atlas_record_sha256": atlas_record_sha256(function), "target_rva": _hex(target), "operand_class": "immediate", "operand_index": 0, "use_class": use})
    return result


def _semantics() -> dict[str, Any]:
    return {
        "helper_registry_nil_loop": {"native_pointer_register": "ECX", "lua_state_native_stack_argument_count": 1, "unsigned_count_offset": "+0x2c", "initial_byte_offset": 0, "zero_count_branch": {"instruction_rva": "0x002e9f0c", "condition": "count_unsigned_less_or_equal_zero", "successor_rvas": ["0x002e9f0e", "0x002e9f3a"]}, "per_iteration": ["lua_pushlightuserdata(L,native_pointer_plus_byte_offset)", "lua_pushnil(L)", "lua_rawset(L,-10000)"], "registry_index": -10000, "byte_offset_increment_rva": "0x002e9f30", "loop_branch": {"instruction_rva": "0x002e9f37", "condition": "byte_offset_unsigned_below_count", "successor_rvas": ["0x002e9f12", "0x002e9f39"]}, "return_instruction_rva": "0x002e9f3d", "return_stack_bytes": 4, "pointer_meaning_claimed": False, "ownership_or_lifetime_claimed": False},
        "callback_lookup_and_tail": {"userdata_source": "raw lua_touserdata(L,1) result", "userdata_null_checked_before_native_tail": False, "lookup_key": "__finalize", "lookup_api": "lua_gettable", "lookup_table_index": 1, "nil_type_value": 0, "nil_branch": {"instruction_rva": "0x002e9f76", "successor_rvas": ["0x002e9f78", "0x002e9f86"], "action": "lua_settop(L,-2)"}, "non_nil_branch": {"copies_original_input_index": 1, "lua_call_argument_count": 1, "lua_call_result_count": 0, "callability_proven": False}, "normal_arms_converge_rva": "0x002e9f9d", "direct_helper_edge_rva": "0x002e9fa0", "indirect_native_call": {"instruction_rva": "0x002e9faf", "form": "call_memory_eax", "guard_branch_rva": "0x002e9fa9"}, "conditional_native_tail": {"comparison_rva": "0x002e9fb6", "branch_rva": "0x002e9fb8", "target_rva": "0x0036fb17", "target_label_semantic_evidence": False}, "normal_result_count": 0, "return_instruction_rva": "0x002e9fc8", "runtime_finalization_claimed": False, "native_free_or_destructor_claimed": False},
    }


def _summary(value: Mapping[str, Any]) -> dict[str, Any]:
    bodies=_array(value["source_bodies"], "source bodies"); refs=_array(value["target_reference_scan"]["references"], "references")
    return {"initializer_prerequisite_count": 1, "source_body_count": len(bodies), "source_body_bytes": sum(item["body_size"] for item in bodies), "source_cfg_node_count": sum(item["control_flow_graph_node_count"] for item in bodies), "source_cfg_edge_count": sum(item["control_flow_graph_edge_count"] for item in bodies), "direct_lua_call_count": sum(len(item["direct_lua_calls"]) for item in bodies), "staged_lua_call_count": sum(item["staged_lua_call_count"] for item in bodies), "literal_count": 1, "target_reference_count": len(refs), "helper_direct_call_count": sum(item["use_class"] == "callback_direct_helper_call" for item in refs), "cleanup_closure_producer_count": sum(item["use_class"] == "initializer_cleanup_closure_producer" for item in refs), "schema_violations": 0}


def _derive(initializer: Mapping[str, Any], program_facts: Mapping[str, Any], direct_calls: Mapping[str, Any], literal: Mapping[str, Any]) -> dict[str, Any]:
    _validate_json_tree(initializer, "initializer"); _validate_json_tree(program_facts, "program facts"); _validate_json_tree(direct_calls, "direct calls")
    identity=_mapping(program_facts.get("identity"), "program facts identity")
    if identity.get("executable_sha256") != _PROFILE["executable_sha256"] or initializer.get("build_identity") != dict(identity) or direct_calls.get("build_identity") != dict(identity):
        raise NativeLuaPropertyCleanupChainError("cleanup prerequisites have different build identities")
    result={"schema_version": SCHEMA_VERSION, "analysis_kind": ANALYSIS_KIND, "build_identity": dict(identity), "initializer_chain": {"analysis_kind": INITIALIZER_ANALYSIS_KIND, "canonical_sha256": _canonical_sha256(initializer)}, "initializer_cleanup_placement": _initializer_placement(initializer), "source_bodies": _body_records(program_facts, direct_calls), "literal": dict(literal), "target_reference_scan": {"target_rvas": ["0x002e9f00", "0x002e9f40"], "scope": {"atlas_function_count": len(_atlas_functions(program_facts)), "atlas_body_range_count": 25490, "decoded_bytes": 3735718, "decoded_instructions": 1153814, "all_declared_ranges_decoded": True, "operand_classes": ["absolute_memory", "immediate"]}, "references": _reference_rows(program_facts)}, "semantics": _semantics(), "method": copy.deepcopy(_METHOD)}
    if dict(literal) != _literal_expected(): raise NativeLuaPropertyCleanupChainError("cleanup literal record changed")
    result["summary"]=_summary(result); _assert_publication_safe(result); return result


def _exact_function_checks(data: bytes, image: Any, program_facts: Mapping[str, Any], direct_calls: Mapping[str, Any]) -> None:
    import capstone
    import capstone.x86_const as x86
    decoder,_=_decoder(); decoder.detail=True; functions=_atlas_functions(program_facts)
    for expected in _PROFILE["functions"]:
        function=functions[expected["entry_rva"]]; raw_range=_array(function["ranges"], "ranges")
        if len(raw_range)!=1: raise NativeLuaPropertyCleanupChainError("cleanup body has multiple ranges")
        span=_mapping(raw_range[0], "range"); start=_rva(span["start_rva"], "range start"); size=span["size"]
        instructions=_decode_range(data,image,start,size,decoder); graph=_enhanced_cfg(instructions,image.image_base,(start,size),capstone,x86); graph["caller_entry_rva"]=_hex(expected["entry_rva"]); graph=_with_edi_writes(graph,instructions,x86)
        if _canonical_sha256(graph)!=expected["cfg_sha256"] or graph["node_count"]!=expected["node_count"] or graph["edge_count"]!=expected["edge_count"]: raise NativeLuaPropertyCleanupChainError("cleanup CFG identity changed")
        by_rva={item.address-image.image_base:item for item in instructions}
        calls=_direct_records(direct_calls, expected)
        for item in calls:
            instruction=by_rva.get(_rva(item["rva"], "call rva"))
            if instruction is None or hashlib.sha256(bytes(instruction.bytes)).hexdigest()!=item["instruction_sha256"]: raise NativeLuaPropertyCleanupChainError("cleanup direct Lua call bytes changed")


def _exact_reference_scan(data: bytes, image: Any, program_facts: Mapping[str, Any]) -> None:
    import capstone.x86_const as x86
    decoder,_=_decoder(); decoder.detail=True; targets={image.image_base+0x002E9F00:0x002E9F00,image.image_base+0x002E9F40:0x002E9F40}; found=[]; ranges=bytes_total=ins_total=0
    for owner,function in sorted(_atlas_functions(program_facts).items()):
        for raw in _array(function["ranges"], "ranges"):
            span=_mapping(raw,"range"); start=_rva(span["start_rva"],"range start"); size=span["size"]; instructions=_decode_range(data,image,start,size,decoder); ranges+=1; bytes_total+=size; ins_total+=len(instructions)
            for instruction in instructions:
                for index, operand in enumerate(instruction.operands):
                    if operand.type==x86.X86_OP_IMM: value=int(operand.imm)&0xffffffff; kind="immediate"
                    elif operand.type==x86.X86_OP_MEM and operand.mem.base==x86.X86_REG_INVALID and operand.mem.index==x86.X86_REG_INVALID: value=int(operand.mem.disp)&0xffffffff; kind="absolute_memory"
                    else: continue
                    if value in targets: found.append((instruction.address-image.image_base,owner,targets[value],kind,index,bytes(instruction.bytes)))
    expected=_reference_rows(program_facts)
    observed=[{"instruction_rva":_hex(r),"instruction_size":len(raw),"instruction_sha256":hashlib.sha256(raw).hexdigest(),"owner_entry_rva":_hex(owner),"owner_atlas_record_sha256":atlas_record_sha256(_atlas_functions(program_facts)[owner]),"target_rva":_hex(target),"operand_class":kind,"operand_index":index,"use_class":"callback_direct_helper_call" if r==0x002E9FA0 else "initializer_cleanup_closure_producer"} for r,owner,target,kind,index,raw in found]
    if observed != expected or (ranges,bytes_total,ins_total)!=(25490,3735718,1153814): raise NativeLuaPropertyCleanupChainError("cleanup target-reference scan changed")


def build_native_lua_property_cleanup_chain(executable: Path, initializer: Mapping[str, Any], consumer: Mapping[str, Any], property_factory_chain: Mapping[str, Any], direct_calls: Mapping[str, Any], callback_census: Mapping[str, Any], setfield_publications: Mapping[str, Any], direct_table_setter_publications: Mapping[str, Any], indirect_settable_publications: Mapping[str, Any], table_key_provenance: Mapping[str, Any], terminal_dispositions: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    try:
        receipt=validate_native_lua_property_initializer_chain(executable,initializer,consumer,property_factory_chain,direct_calls,callback_census,setfield_publications,direct_table_setter_publications,indirect_settable_publications,table_key_provenance,terminal_dispositions,program_facts,inventory=inventory)
        if receipt.get("analysis_kind")!=INITIALIZER_VERIFICATION_KIND or receipt.get("status")!="verified" or receipt.get("evidence_sha256")!=_PROFILE["initializer_canonical_sha256"]: raise NativeLuaPropertyCleanupChainError("initializer exact verifier returned another result")
        data,image,digest=_load_executable(executable)
        if digest!=_PROFILE["executable_sha256"]: raise NativeLuaPropertyCleanupChainError("cleanup executable identity changed")
        _exact_function_checks(data,image,program_facts,direct_calls); _exact_reference_scan(data,image,program_facts)
        return _derive(initializer,program_facts,direct_calls,_literal_exact(data,image))
    except NativeLuaPropertyCleanupChainError: raise
    except (NativeLuaPropertyInitializerChainError,NativeLuaCClosurePublicationError,NativeLuaDirectCallError,PEAnchorError) as exc:
        raise NativeLuaPropertyCleanupChainError(f"cleanup prerequisite exact verification failed: {exc}") from exc


def validate_native_lua_property_cleanup_chain_structure(evidence: Mapping[str, Any], initializer: Mapping[str, Any], consumer: Mapping[str, Any], property_factory_chain: Mapping[str, Any], direct_calls: Mapping[str, Any], callback_census: Mapping[str, Any], setfield_publications: Mapping[str, Any], direct_table_setter_publications: Mapping[str, Any], indirect_settable_publications: Mapping[str, Any], table_key_provenance: Mapping[str, Any], terminal_dispositions: Mapping[str, Any], program_facts: Mapping[str, Any]) -> dict[str, Any]:
    try:
        receipt=validate_native_lua_property_initializer_chain_structure(initializer,consumer,property_factory_chain,direct_calls,callback_census,setfield_publications,direct_table_setter_publications,indirect_settable_publications,table_key_provenance,terminal_dispositions,program_facts)
    except (NativeLuaPropertyInitializerChainError,NativeLuaCClosurePublicationError) as exc:
        raise NativeLuaPropertyCleanupChainError(f"cleanup structural prerequisite failed: {exc}") from exc
    if receipt.get("analysis_kind")!=INITIALIZER_STRUCTURE_VERIFICATION_KIND or receipt.get("status")!="structurally_verified" or receipt.get("evidence_sha256")!=_PROFILE["initializer_canonical_sha256"]: raise NativeLuaPropertyCleanupChainError("initializer structural verifier returned another result")
    try:
        expected=_derive(initializer,program_facts,direct_calls,_literal_expected()); evidence=_mapping(evidence,"evidence"); _exact_keys(evidence,set(expected),"evidence")
        if _canonical_bytes(evidence)!=_canonical_bytes(expected): raise NativeLuaPropertyCleanupChainError("cleanup evidence differs from structural replay")
    except NativeLuaCClosurePublicationError as exc:
        raise NativeLuaPropertyCleanupChainError(f"cleanup structural replay failed: {exc}") from exc
    return {"schema_version":SCHEMA_VERSION,"analysis_kind":STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","build_identity":dict(expected["build_identity"]),"evidence_sha256":_canonical_sha256(expected),"summary":dict(expected["summary"])}


def validate_native_lua_property_cleanup_chain(executable: Path, evidence: Mapping[str, Any], initializer: Mapping[str, Any], consumer: Mapping[str, Any], property_factory_chain: Mapping[str, Any], direct_calls: Mapping[str, Any], callback_census: Mapping[str, Any], setfield_publications: Mapping[str, Any], direct_table_setter_publications: Mapping[str, Any], indirect_settable_publications: Mapping[str, Any], table_key_provenance: Mapping[str, Any], terminal_dispositions: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    rebuilt=build_native_lua_property_cleanup_chain(executable,initializer,consumer,property_factory_chain,direct_calls,callback_census,setfield_publications,direct_table_setter_publications,indirect_settable_publications,table_key_provenance,terminal_dispositions,program_facts,inventory=inventory)
    if _canonical_bytes(evidence)!=_canonical_bytes(rebuilt): raise NativeLuaPropertyCleanupChainError("cleanup evidence differs from exact rebuild")
    return {"schema_version":SCHEMA_VERSION,"analysis_kind":VERIFICATION_KIND,"status":"verified","build_identity":dict(rebuilt["build_identity"]),"evidence_sha256":_canonical_sha256(rebuilt),"summary":dict(rebuilt["summary"])}


def encode_native_lua_property_cleanup_chain(value: Mapping[str, Any]) -> str:
    _validate_json_tree(value)
    return json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2,sort_keys=True)+"\n"
