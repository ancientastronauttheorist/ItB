"""Exact, deliberately opaque static boundary for the native ``operator_new`` label.

The name is retained solely as an analysis label from program facts.  This
module seals the finite PE evidence without assigning allocator or ABI meaning.
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
    NativeLuaClassReturnHelperChainError, _REGISTER_NAMES, _build_function_records,
    _canonical_bytes, _canonical_sha256, _expected_point_record,
    _normalized_declared_edge, _source_identity,
    _expected_reference_scan as _base_expected_reference_scan,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError, _array, _assert_publication_safe,
    _atlas_functions, _exact_keys, _hex, _mapping, _rva, _validate_json_tree,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_CALL_ANALYSIS_KIND, SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError, _decoder, _load_executable,
    validate_native_lua_direct_call_census, validate_native_lua_direct_call_structure,
)
from src.observatory.native_lua_property_factory_chain import NativeLuaPropertyFactoryChainError
from src.observatory.native_self_linked_record_helper_chain import NativeSelfLinkedRecordHelperChainError
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_operator_new_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS_SHA256 = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT_SHA256 = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_SELF_LINKED_SHA256 = "994b4af188a8017d0dce172a53a9598b9cdf7a48d2faef1fbcbfa5ffcbbf2ddb"
_ENTRY = 0x003574DB
_BODY_SHA256 = "452b4c981b0a2567c6f4fc35b20076deca45a6b3509707358212028d21db5bfa"
_ATLAS_SHA256 = "605ec81a3c1419f23863f79237b52573167b4dd5d86c86c3bcb958bc46a75eba"
_CFG_SHA256 = "86559777b13d1527d904c9f979cf9ae8e822c26246e9c0cba7261ec6d8250fa4"


class NativeOperatorNewStaticBoundaryError(RuntimeError):
    """Raised when the reviewed static boundary cannot be reproduced exactly."""


def _point(role: str, rva: int, encoded: str) -> dict[str, Any]:
    return {"role": role, "rva": rva, "encoded": bytes.fromhex(encoded), "api": None,
            "meaning": {"operation": "decoded_instruction", "source_semantic_names_assigned": False}}


# Every decoded instruction in the sole 51-byte atlas range is pinned.  Roles
# identify byte positions only; none carries allocator, ABI, or source meaning.
_FUNCTION = {
    "role": "analysis_labeled_operator_new_static_boundary", "entry_rva": _ENTRY,
    "body_size": 51, "body_sha256": _BODY_SHA256, "cfg_canonical_sha256": _CFG_SHA256,
    "direct_calls": [], "staged_dispatches": [], "call_r32": {},
    "points": [
        _point("instruction_00", 0x3574DB, "55"), _point("instruction_01", 0x3574DC, "8bec"),
        _point("instruction_02", 0x3574DE, "eb1f"), _point("instruction_03", 0x3574E0, "ff7508"),
        _point("instruction_04", 0x3574E3, "e8dc460300"), _point("instruction_05", 0x3574E8, "59"),
        _point("instruction_06", 0x3574E9, "85c0"), _point("instruction_07", 0x3574EB, "7512"),
        _point("instruction_08", 0x3574ED, "837d08ff"), _point("instruction_09", 0x3574F1, "7507"),
        _point("instruction_10", 0x3574F3, "e8970f0000"), _point("instruction_11", 0x3574F8, "eb05"),
        _point("instruction_12", 0x3574FA, "e8bdc0feff"), _point("instruction_13", 0x3574FF, "ff7508"),
        _point("instruction_14", 0x357502, "e84b2a0200"), _point("instruction_15", 0x357507, "59"),
        _point("instruction_16", 0x357508, "85c0"), _point("instruction_17", 0x35750A, "74d4"),
        _point("instruction_18", 0x35750C, "5d"), _point("instruction_19", 0x35750D, "c3"),
    ],
    "semantic_facts": {"analysis_label": "operator_new", "analysis_label_only": True,
                       "source_semantic_names_assigned": False,
                       "runtime_or_success_claimed": False},
}
_NATIVE_EDGES = ((0x3574E3, "e8dc460300", 0x38BBC4), (0x3574F3, "e8970f0000", 0x35848F),
                 (0x3574FA, "e8bdc0feff", 0x3435BC), (0x357502, "e84b2a0200", 0x379F52))
_JUMP_SITE, _JUMP_OWNER = 0x00357874, 0x00357870
_JUMP_BYTES = "e962fcffff"
_JUMP_SHA256 = "cdca88990634fb7740f46920a3ff9963c07df60f5ddf4334b345678eb7fbbe51"
_JUMP_OWNER_ATLAS_SHA256 = "bfb0b19ec211eecf01aacb25b9d603b86c54f1280ce76ca1c0b9f4cf9be1ecea"
_JUMP_OWNER_BODY_SHA256 = "6177d8106443c852dadf2c9b97ff04041bc8e6687fc40fb9c40e939023510684"
_METHOD = {
    "structural_boundary": "PE-free validation reconstructs finite canonical-pinned prerequisites, all 20 decoded instruction records, the complete CFG identity, opaque native edges, and a program-facts direct-call profile. Exact bytes and the all-operand PE traversal require an exact rebuild.",
    "not_claimed": [
        "allocation semantics, ABI, success, ownership, lifetime, or size meaning",
        "runtime reachability, invocation, order, frequency, normal return, or source identity",
        "behavior of the four opaque native callees",
        "computed, indirect, data, un-atlased, or Lua-side references",
    ],
}


def _json_equal(left: Any, right: Any) -> bool:
    return _canonical_bytes(left) == _canonical_bytes(right)


def _facts_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    result = _source_identity(value, "pe_ghidra_program_facts", _FACTS_SHA256, "program facts")
    summary = _mapping(value.get("summary"), "program facts summary")
    return {**result, "function_count": summary.get("function_count"), "body_range_count": summary.get("body_range_count"), "function_body_bytes": summary.get("function_body_bytes")}


def _preflight(self_linked: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    identity = _mapping(facts.get("identity"), "program facts identity")
    if identity.get("executable_sha256") != _EXE_SHA256:
        raise NativeOperatorNewStaticBoundaryError("program facts are not the reviewed operator-new profile")
    for label, value in (("self-linked helper", self_linked), ("direct-call census", direct)):
        if not _json_equal(value.get("build_identity"), dict(identity)):
            raise NativeOperatorNewStaticBoundaryError(f"{label} build identity differs")
    return (_facts_identity(facts), _source_identity(direct, DIRECT_CALL_ANALYSIS_KIND, _DIRECT_SHA256, "direct-call census"),
            _source_identity(self_linked, "pe_native_self_linked_record_helper_chain", _SELF_LINKED_SHA256, "self-linked helper"))


def _profile(facts: Mapping[str, Any]) -> dict[str, Any]:
    refs = []
    for raw in _array(facts.get("ghidra_declared_direct_calls"), "program facts direct calls"):
        edge = _mapping(raw, "program facts direct call")
        if (_rva(edge.get("target_entry_rva"), "target entry") == _ENTRY
                and _rva(edge.get("instruction_rva"), "direct-call site") != _JUMP_SITE):
            site, target, owner = (_rva(edge.get(key), key) for key in ("instruction_rva", "target_rva", "source_entry_rva"))
            if target != _ENTRY:
                raise NativeOperatorNewStaticBoundaryError("target entry and target RVA differ")
            refs.append({"instruction_rva": site, "owner_entry_rva": owner, "target_rva": target,
                         "encoded": (b"\xe8" + int(target - (site + 5)).to_bytes(4, "little", signed=True)).hex(), "operand_index": 0})
    refs.sort(key=lambda item: item["instruction_rva"])
    if len(refs) != 1232 or len({item["owner_entry_rva"] for item in refs}) != 1049:
        raise NativeOperatorNewStaticBoundaryError("operator-new declared direct-call census differs")
    return {"executable_sha256": _EXE_SHA256, "functions": [_FUNCTION], "literals": [], "native_edges": [], "target_references": refs}


def _reference_scan(scan: Mapping[str, Any]) -> dict[str, Any]:
    result, aggregates = dict(_mapping(scan, "reference scan")), dict(_mapping(scan.get("aggregates"), "reference aggregates"))
    aggregates.pop("returned_callback_reference_count", None); aggregates.pop("alternate_owner_reference_count", None)
    result["aggregates"] = aggregates
    refs = _array(result.get("references"), "references")
    direct = [item for item in refs if _mapping(item, "reference").get("use_class") == "direct_call"]
    jumps = [item for item in refs if _mapping(item, "reference").get("use_class") == "other_address"]
    if len(refs) != 1233 or len(direct) != 1232 or len(jumps) != 1 or aggregates != {"reference_count": 1233, "direct_call_count": 1232, "comparison_count": 0, "other_address_count": 1, "memory_operand_count": 0, "owner_count": 1050}:
        raise NativeOperatorNewStaticBoundaryError("all-operand operator-new reference partition differs")
    for item in direct:
        record = _mapping(item, "direct reference")
        if record.get("instruction_size") != 5 or record.get("operand_index") != 0 or record.get("operand_class") != "immediate" or record.get("call_form") != "x86_relative_near_call_e8" or record.get("ghidra_declared_direct_edge") is None:
            raise NativeOperatorNewStaticBoundaryError("direct reference is not a declared E8 operand-zero call")
    jump = _mapping(jumps[0], "jump reference")
    if jump.get("instruction_size") != 5 or jump.get("operand_index") != 0 or jump.get("operand_class") != "immediate" or jump.get("call_form") is not None:
        raise NativeOperatorNewStaticBoundaryError("sole non-call reference is not an immediate near jump")
    owners: dict[str, list[Mapping[str, Any]]] = {}
    for raw in refs:
        record = _mapping(raw, "reference")
        owner = record.get("owner_entry_rva")
        owner_sha256 = record.get("owner_atlas_record_sha256")
        if type(owner) is not str or type(owner_sha256) is not str:
            raise NativeOperatorNewStaticBoundaryError("operator-new reference lacks owner identity")
        owners.setdefault(owner, []).append(record)
    if len(owners) != 1050:
        raise NativeOperatorNewStaticBoundaryError("operator-new owner partition differs")
    for owner, group in owners.items():
        if any(record.get("owner_atlas_record_sha256") != group[0].get("owner_atlas_record_sha256") for record in group):
            raise NativeOperatorNewStaticBoundaryError(f"operator-new owner identity differs at {owner}")
    result["owner_partition"] = [
        {
            "owner_entry_rva": owner,
            "owner_atlas_record_sha256": group[0].get("owner_atlas_record_sha256"),
            "reference_count": len(group),
        }
        for owner, group in sorted(owners.items())
    ]
    return result


def _expected_jump(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Reconstruct the one non-E8 operand from pinned atlas and Ghidra facts."""
    functions = _atlas_functions(facts)
    owner = functions.get(_JUMP_OWNER)
    if (owner is None or atlas_record_sha256(owner) != _JUMP_OWNER_ATLAS_SHA256
            or owner.get("body_size") != 9 or owner.get("body_sha256") != _JUMP_OWNER_BODY_SHA256):
        raise NativeOperatorNewStaticBoundaryError("immediate-jump owner atlas identity differs")
    declared = {_rva(_mapping(raw, "edge").get("instruction_rva"), "edge site"): _mapping(raw, "edge")
                for raw in _array(facts.get("ghidra_declared_direct_calls"), "edges")}
    edge = declared.get(_JUMP_SITE)
    if (edge is None or _rva(edge.get("source_entry_rva"), "jump source") != _JUMP_OWNER
            or _rva(edge.get("target_entry_rva"), "jump target entry") != _ENTRY
            or _rva(edge.get("target_rva"), "jump target") != _ENTRY):
        raise NativeOperatorNewStaticBoundaryError("immediate-jump Ghidra edge differs")
    return {"instruction_rva": _hex(_JUMP_SITE), "instruction_size": 5,
            "instruction_sha256": _JUMP_SHA256, "owner_entry_rva": _hex(_JUMP_OWNER),
            "owner_atlas_record_sha256": _JUMP_OWNER_ATLAS_SHA256, "target_rva": _hex(_ENTRY),
            "target_atlas_record_sha256": _ATLAS_SHA256,
            "target_va": _hex(_rva(_mapping(facts.get("ghidra"), "ghidra").get("image_base"), "image base") + _ENTRY),
            "operand_class": "immediate", "operand_index": 0, "use_class": "other_address",
            "call_form": None, "ghidra_declared_direct_edge": _normalized_declared_edge(edge)}


def _expected_reference_scan(facts: Mapping[str, Any], direct: Mapping[str, Any]) -> dict[str, Any]:
    # Program facts independently reconstruct every declared E8 call.  The one
    # E9 immediate target is also declared by Ghidra, but is modeled separately
    # so its non-call instruction form cannot be coerced into the E8 partition.
    expected = _base_expected_reference_scan(facts, direct, _profile(facts))
    expected["references"].append(_expected_jump(facts))
    expected["references"].sort(key=lambda item: (_rva(item["instruction_rva"], "site"), item["operand_index"]))
    expected["aggregates"] = {"reference_count": 1233, "direct_call_count": 1232,
                              "comparison_count": 0, "other_address_count": 1,
                              "memory_operand_count": 0, "owner_count": 1050}
    return _reference_scan(expected)


def _whole_atlas_reference_scan(data: bytes, image: Any, decoder: Any, facts: Mapping[str, Any], direct: Mapping[str, Any]) -> dict[str, Any]:
    # The inherited scanner is deliberately invoked with the 1,232 program-facts
    # E8 profile.  Its comparison is reimplemented below because this target also
    # has one immediate JMP operand not represented by the call-only facts table.
    import capstone.x86_const as x86
    functions, declared = _atlas_functions(facts), { _rva(_mapping(e, "edge").get("instruction_rva"), "edge RVA"): _mapping(e, "edge") for e in _array(facts.get("ghidra_declared_direct_calls"), "edges") }
    decoder.detail = True; refs=[]; ranges=bytes_seen=instructions_seen=0; target_va=image.image_base + _ENTRY
    from src.observatory.native_lua_cclosure_setfield_publications import _decode_range
    for owner, function in sorted(functions.items()):
        owner_hash=atlas_record_sha256(function)
        for raw_range in _array(function.get("ranges"), "atlas ranges"):
            span=_mapping(raw_range,"atlas range"); start=_rva(span.get("start_rva"),"range start"); size=span.get("size")
            if type(size) is not int or size <= 0: raise NativeOperatorNewStaticBoundaryError("invalid atlas range")
            instructions=_decode_range(data,image,start,size,decoder); ranges += 1; bytes_seen += size; instructions_seen += len(instructions)
            for instruction in instructions:
                for operand_index, operand in enumerate(instruction.operands):
                    operand_class=value=None
                    if operand.type == x86.X86_OP_IMM: operand_class,value="immediate",int(operand.imm)&0xffffffff
                    elif operand.type == x86.X86_OP_MEM and operand.mem.base == x86.X86_REG_INVALID and operand.mem.index == x86.X86_REG_INVALID: operand_class,value="absolute_memory",int(operand.mem.disp)&0xffffffff
                    if value != target_va: continue
                    encoded=bytes(instruction.bytes); site=instruction.address-image.image_base
                    refs.append({"instruction_rva":_hex(site),"instruction_size":instruction.size,"instruction_sha256":hashlib.sha256(encoded).hexdigest(),"owner_entry_rva":_hex(owner),"owner_atlas_record_sha256":owner_hash,"target_rva":_hex(_ENTRY),"target_atlas_record_sha256":_ATLAS_SHA256,"target_va":_hex(value),"operand_class":operand_class,"operand_index":operand_index,"use_class":"direct_call" if instruction.id == x86.X86_INS_CALL else "comparison" if instruction.id in {x86.X86_INS_CMP,x86.X86_INS_TEST} else "other_address","call_form":"x86_relative_near_call_e8" if len(encoded)==5 and encoded[0]==0xe8 else None,"ghidra_declared_direct_edge":None if site not in declared else _normalized_declared_edge(declared[site])})
    refs.sort(key=lambda item: (_rva(item["instruction_rva"], "site"), item["operand_index"]))
    result={"target_rvas":[_hex(_ENTRY)],"target_vas":[_hex(target_va)],"scope":{"atlas_function_count":len(functions),"atlas_body_range_count":ranges,"decoded_bytes":bytes_seen,"decoded_instructions":instructions_seen,"all_declared_ranges_decoded":True,"operand_classes":["absolute_memory","immediate"]},"references":refs,"aggregates":{"reference_count":len(refs),"direct_call_count":sum(x["use_class"]=="direct_call" for x in refs),"comparison_count":sum(x["use_class"]=="comparison" for x in refs),"other_address_count":sum(x["use_class"]=="other_address" for x in refs),"memory_operand_count":sum(x["operand_class"]=="absolute_memory" for x in refs),"owner_count":len({x["owner_entry_rva"] for x in refs})}}
    result=_reference_scan(result)
    # Exact call records must equal an independently reconstructed program-facts profile.
    expected=_base_expected_reference_scan(facts,direct,_profile(facts))
    if [x for x in result["references"] if x["use_class"]=="direct_call"] != expected["references"]:
        raise NativeOperatorNewStaticBoundaryError("PE-wide E8 traversal differs from program-facts profile")
    if not _json_equal([x for x in result["references"] if x["use_class"] == "other_address"], [_expected_jump(facts)]):
        raise NativeOperatorNewStaticBoundaryError("PE-wide E9 traversal differs from pinned jump profile")
    return result


def _native_edges(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions=_atlas_functions(facts); source=functions.get(_ENTRY)
    if source is None or atlas_record_sha256(source)!=_ATLAS_SHA256 or source.get("body_size")!=51 or source.get("body_sha256")!=_BODY_SHA256: raise NativeOperatorNewStaticBoundaryError("source atlas identity differs")
    declared={_rva(_mapping(raw,"edge").get("instruction_rva"),"site"):_mapping(raw,"edge") for raw in _array(facts.get("ghidra_declared_direct_calls"),"edges")}; result=[]
    for site, encoded_hex, target in _NATIVE_EDGES:
        edge,target_function=declared.get(site),functions.get(target)
        if edge is None or target_function is None or _rva(edge.get("source_entry_rva"),"source")!=_ENTRY or _rva(edge.get("target_entry_rva"),"target")!=target or _rva(edge.get("target_rva"),"target RVA")!=target: raise NativeOperatorNewStaticBoundaryError("opaque native-edge join differs")
        encoded=bytes.fromhex(encoded_hex); result.append({"role":"opaque_native_direct_edge","source_entry_rva":_hex(_ENTRY),"source_atlas_record_sha256":_ATLAS_SHA256,"source_body_size":51,"source_body_sha256":_BODY_SHA256,"instruction":{"rva":_hex(site),"size":5,"sha256":hashlib.sha256(encoded).hexdigest()},"target_entry_rva":_hex(target),"target_rva":_hex(target),"target_atlas_record_sha256":atlas_record_sha256(target_function),"target_body_size":target_function.get("body_size"),"target_body_sha256":target_function.get("body_sha256"),"ghidra_declared_direct_edge":_normalized_declared_edge(edge),"label_source":"analysis_or_default","callee_behavior_opaque":True})
    return result


def _self_linked_predecessor_edge(self_linked: Mapping[str, Any], scan: Mapping[str, Any]) -> dict[str, Any]:
    matches = [
        dict(_mapping(raw, "self-linked native edge"))
        for raw in _array(self_linked.get("native_edges"), "self-linked native edges")
        if _rva(_mapping(raw, "self-linked native edge").get("source_entry_rva"), "edge source") == 0x0007C600
        and _rva(_mapping(raw, "self-linked native edge").get("target_entry_rva"), "edge target") == _ENTRY
        and _rva(_mapping(_mapping(raw, "self-linked native edge").get("instruction"), "edge instruction").get("rva"), "edge site") == 0x0007C602
    ]
    if len(matches) != 1 or matches[0].get("role") != "symbol_labeled_native_size_request_edge":
        raise NativeOperatorNewStaticBoundaryError("self-linked predecessor edge differs")
    edge = matches[0]
    references = [
        _mapping(raw, "operator-new reference")
        for raw in _array(scan.get("references"), "operator-new references")
        if _rva(_mapping(raw, "operator-new reference").get("instruction_rva"), "reference site") == 0x0007C602
        and _rva(_mapping(raw, "operator-new reference").get("owner_entry_rva"), "reference owner") == 0x0007C600
        and _rva(_mapping(raw, "operator-new reference").get("target_rva"), "reference target") == _ENTRY
    ]
    instruction = _mapping(edge.get("instruction"), "predecessor instruction")
    if len(references) != 1:
        raise NativeOperatorNewStaticBoundaryError("operator-new scan lacks the self-linked predecessor")
    reference = references[0]
    if (
        reference.get("use_class") != "direct_call"
        or reference.get("call_form") != "x86_relative_near_call_e8"
        or (reference.get("instruction_size"), reference.get("instruction_sha256"))
        != (instruction.get("size"), instruction.get("sha256"))
        or reference.get("owner_atlas_record_sha256") != edge.get("source_atlas_record_sha256")
        or reference.get("target_atlas_record_sha256") != edge.get("target_atlas_record_sha256")
        or not _json_equal(reference.get("ghidra_declared_direct_edge"), edge.get("ghidra_declared_direct_edge"))
    ):
        raise NativeOperatorNewStaticBoundaryError("self-linked edge and current reference record differ")
    return edge


def _decoder_contract() -> dict[str, Any]:
    return {"name":"capstone","version":SUPPORTED_CAPSTONE_VERSION,"architecture":"x86","mode_bits":32,"sealed_instruction_count":20,"register_call_encoding_audit":[{"register":r,"encoding":f"ff{0xd0+i:02x}"} for i,r in enumerate(_REGISTER_NAMES)]}


def _expected_body(facts: Mapping[str, Any]) -> dict[str, Any]:
    if _atlas_functions(facts).get(_ENTRY) is None: raise NativeOperatorNewStaticBoundaryError("operator-new target absent from atlas")
    return {"role":_FUNCTION["role"],"entry_rva":_hex(_ENTRY),"atlas_record_sha256":_ATLAS_SHA256,"body_size":51,"body_sha256":_BODY_SHA256,"range_start_rva":_hex(_ENTRY),"range_size":51,"control_flow_graph_canonical_sha256":_CFG_SHA256,"reviewed_points":[_expected_point_record(x) for x in _FUNCTION["points"]],"direct_lua_calls":[],"staged_lua_dispatches":[],"call_r32_audit":[{"register":r,"call_rvas":[]} for r in _REGISTER_NAMES],"register_call_partition_complete":True,"semantic_facts":_FUNCTION["semantic_facts"]}


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    scan=_mapping(result.get("whole_atlas_reference_scan"),"scan"); a=_mapping(scan.get("aggregates"),"aggregates")
    return {"reviewed_operator_new_count":1,"reviewed_operator_new_bytes":51,"sealed_instruction_count":20,"sealed_control_flow_graph_count":1,"sealed_control_flow_graph_node_count":20,"sealed_control_flow_graph_edge_count":22,"direct_lua_call_count":0,"staged_lua_dispatch_count":0,"call_r32_count":0,"literal_count":0,"native_edge_count":4,"self_linked_predecessor_edge_count":1,"target_reference_count":len(_array(scan.get("references"),"references")),"target_reference_direct_call_count":a["direct_call_count"],"target_reference_comparison_count":a["comparison_count"],"target_reference_other_address_count":a["other_address_count"],"target_reference_memory_operand_count":a["memory_operand_count"],"target_reference_owner_count":a["owner_count"],"schema_violations":0}


def _build(executable: Path, self_linked: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    for value,label in ((self_linked,"self-linked helper"),(direct,"direct calls"),(facts,"program facts"),(inventory,"inventory")): _validate_json_tree(value,label)
    receipt=validate_native_lua_direct_call_census(executable,direct,facts,inventory=inventory)
    if receipt.get("status")!="verified" or receipt.get("evidence_sha256")!=_DIRECT_SHA256: raise NativeOperatorNewStaticBoundaryError("direct-call prerequisite exact verification failed")
    atlas,direct_identity,self_identity=_preflight(self_linked,direct,facts); data,image,digest=_load_executable(executable); identity=_mapping(facts.get("identity"),"identity")
    if digest!=_EXE_SHA256 or identity.get("executable_size")!=len(data) or identity.get("architecture")!=image.architecture: raise NativeOperatorNewStaticBoundaryError("executable identity differs")
    decoder,_=_decoder(); bodies,graphs=_build_function_records(data,image,decoder,facts,direct,_profile(facts)); scan=_whole_atlas_reference_scan(data,image,decoder,facts,direct); result={"schema_version":SCHEMA_VERSION,"analysis_kind":ANALYSIS_KIND,"build_identity":dict(identity),"atlas":atlas,"direct_call_census":direct_identity,"self_linked_record_helper_chain":self_identity,"self_linked_operator_new_edge":_self_linked_predecessor_edge(self_linked,scan),"decoder":_decoder_contract(),"function_bodies":bodies,"control_flow_graphs":graphs,"native_edges":_native_edges(facts),"whole_atlas_reference_scan":scan,"method":_METHOD}; result["summary"]=_summary(result); _assert_publication_safe(result)
    if _load_executable(executable)[2]!=digest: raise NativeOperatorNewStaticBoundaryError("executable changed during exact rebuild")
    validate_native_operator_new_static_boundary_structure(result,self_linked,direct,facts); return result


def build_native_operator_new_static_boundary(executable: Path, self_linked_record_helper_chain: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    try: return _build(executable,self_linked_record_helper_chain,direct_calls,program_facts,inventory=inventory)
    except NativeOperatorNewStaticBoundaryError: raise
    except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassFactoryChainError,NativeLuaClassReturnHelperChainError,NativeLuaPropertyFactoryChainError,NativeSelfLinkedRecordHelperChainError,PEAnchorError,OSError) as exc: raise NativeOperatorNewStaticBoundaryError(str(exc)) from exc


def validate_native_operator_new_static_boundary_structure(evidence: Mapping[str, Any], self_linked: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]) -> dict[str, Any]:
    try:
        for value,label in ((evidence,"evidence"),(self_linked,"self-linked helper"),(direct,"direct calls"),(facts,"program facts")): _validate_json_tree(value,label)
        receipt=validate_native_lua_direct_call_structure(direct,facts)
        if receipt.get("status")!="structurally_verified" or receipt.get("evidence_sha256")!=_DIRECT_SHA256: raise NativeOperatorNewStaticBoundaryError("direct-call structural prerequisite failed")
        atlas,direct_identity,self_identity=_preflight(self_linked,direct,facts); evidence=_mapping(evidence,"evidence")
        _exact_keys(evidence,{"schema_version","analysis_kind","build_identity","atlas","direct_call_census","self_linked_record_helper_chain","self_linked_operator_new_edge","decoder","function_bodies","control_flow_graphs","native_edges","whole_atlas_reference_scan","method","summary"},"evidence")
        if type(evidence.get("schema_version")) is not int or evidence.get("schema_version")!=SCHEMA_VERSION or evidence.get("analysis_kind")!=ANALYSIS_KIND: raise NativeOperatorNewStaticBoundaryError("unsupported schema or kind")
        if not all((_json_equal(evidence.get("build_identity"),dict(_mapping(facts.get("identity"),"identity"))),_json_equal(evidence.get("atlas"),atlas),_json_equal(evidence.get("direct_call_census"),direct_identity),_json_equal(evidence.get("self_linked_record_helper_chain"),self_identity),_json_equal(evidence.get("decoder"),_decoder_contract()),_json_equal(evidence.get("method"),_METHOD))): raise NativeOperatorNewStaticBoundaryError("pinned prerequisite or method differs")
        bodies=_array(evidence.get("function_bodies"),"bodies")
        if len(bodies)!=1 or not _json_equal(bodies[0],_expected_body(facts)): raise NativeOperatorNewStaticBoundaryError("operator-new body record differs")
        graph_map=_validated_graphs({"control_flow_graphs":evidence.get("control_flow_graphs")},_atlas_functions(facts))
        if set(graph_map)!={_ENTRY} or _canonical_sha256(graph_map[_ENTRY][0])!=_CFG_SHA256 or graph_map[_ENTRY][0].get("node_count")!=20 or graph_map[_ENTRY][0].get("edge_count")!=22: raise NativeOperatorNewStaticBoundaryError("operator-new CFG differs")
        for point in _array(_mapping(bodies[0],"body").get("reviewed_points"),"points"):
            node=graph_map[_ENTRY][1].get(_rva(_mapping(point,"point").get("rva"),"point RVA"))
            if node is None or (node.get("size"),node.get("sha256")) != (_mapping(point,"point").get("size"),_mapping(point,"point").get("sha256")): raise NativeOperatorNewStaticBoundaryError("sealed point does not join CFG")
        scan=_mapping(evidence.get("whole_atlas_reference_scan"),"scan"); _reference_scan(scan)
        if not _json_equal(evidence.get("whole_atlas_reference_scan"), _expected_reference_scan(facts,direct)) or not _json_equal(evidence.get("self_linked_operator_new_edge"),_self_linked_predecessor_edge(self_linked,scan)) or not _json_equal(evidence.get("native_edges"),_native_edges(facts)) or not _json_equal(evidence.get("summary"),_summary(evidence)): raise NativeOperatorNewStaticBoundaryError("edge, reference, or summary partition differs")
        _assert_publication_safe(evidence); return {"schema_version":SCHEMA_VERSION,"analysis_kind":STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","build_identity":dict(evidence["build_identity"]),"evidence_sha256":_canonical_sha256(evidence),"summary":dict(evidence["summary"])}
    except NativeOperatorNewStaticBoundaryError: raise
    except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassFactoryChainError,NativeLuaClassReturnHelperChainError,NativeLuaPropertyFactoryChainError,NativeSelfLinkedRecordHelperChainError) as exc: raise NativeOperatorNewStaticBoundaryError(str(exc)) from exc


def validate_native_operator_new_static_boundary(executable: Path, evidence: Mapping[str, Any], self_linked_record_helper_chain: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    try:
        _validate_json_tree(evidence,"evidence"); rebuilt=build_native_operator_new_static_boundary(executable,self_linked_record_helper_chain,direct_calls,program_facts,inventory=inventory)
        if not _json_equal(evidence,rebuilt): raise NativeOperatorNewStaticBoundaryError("evidence differs from exact rebuild")
        return {"schema_version":SCHEMA_VERSION,"analysis_kind":VERIFICATION_KIND,"status":"verified","build_identity":dict(rebuilt["build_identity"]),"evidence_sha256":_canonical_sha256(rebuilt),"summary":dict(rebuilt["summary"])}
    except NativeOperatorNewStaticBoundaryError: raise
    except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassFactoryChainError,NativeLuaClassReturnHelperChainError,NativeLuaPropertyFactoryChainError,NativeSelfLinkedRecordHelperChainError,PEAnchorError,OSError) as exc: raise NativeOperatorNewStaticBoundaryError(str(exc)) from exc


def encode_native_operator_new_static_boundary(value: Mapping[str, Any]) -> str:
    try: _validate_json_tree(value); return json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2,sort_keys=True)+"\n"
    except NativeLuaCClosurePublicationError as exc: raise NativeOperatorNewStaticBoundaryError(str(exc)) from exc
