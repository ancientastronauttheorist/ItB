"""Relationship-defined static boundary for the first callee's pointer target.

This receipt preserves decoded machine-code syntax and binary joins only.  In
particular, all analysis labels and register/operand contents remain opaque.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_class_factory_chain import _validated_graphs
from src.observatory.native_lua_class_return_helper_chain import (
    NativeLuaClassReturnHelperChainError, _REGISTER_NAMES, _canonical_bytes,
    _canonical_sha256, _enhanced_cfg, _expected_point_record, _point_record,
    _source_identity, _with_edi_writes, _call_r32_audit, _normalized_declared_edge,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError, _array, _assert_publication_safe,
    _atlas_functions, _exact_keys, _hex, _mapping, _rva, _validate_json_tree,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_KIND, SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError, _decoder, _load_executable,
    validate_native_lua_direct_call_census, validate_native_lua_direct_call_structure,
)
from src.observatory.native_query_handler_first_callee_static_boundary import (
    ANALYSIS_KIND as FIRST_CALLEE_KIND,
    _canonical_sha256 as _first_callee_canonical_sha256,
)
from src.observatory.native_query_new_handler_static_boundary import (
    ANALYSIS_KIND as QUERY_HANDLER_KIND,
    _canonical_sha256 as _query_handler_canonical_sha256,
)
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_query_handler_first_callee_pointer_target_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_QUERY_HANDLER = "742e341a855de34731177afd53b385c67fbd64f3d277fedf8ba6c8e9bbf61705"
_FIRST_CALLEE = "b08dc12a2f4951817e4e7c24dbdfc4afec03550c2828d7d14c1d757404517d73"
_ENTRY = 0x3729B0
_BODY = "041351f97ec254c16a90406f1db804efed9b575e1f7e253f3cc459add09f316e"
_ATLAS = "e777279976e53e36c9adba5d9286452cf9ac91e85061c1414cbf892941d6b845"
_CFG = "7cb067add3d8415d9ddfa92baa0988298d88f64799e90fce0c29b35154095c09"
_POINTER = (0x3584B0, "68b0297700", _ENTRY)
_REFERENCES = ((0x3584B0, 0x3584B0), (0x39D58A, 0x39D580), (0x39D770, 0x39D770))
_DIRECT_EDGES = (
    (0x3729DB, 0x372970), (0x3729E4, 0x007E70), (0x372A2A, 0x378B3E),
    (0x372A53, 0x39D580), (0x372A6C, 0x3581B3), (0x372A80, 0x378B6E),
    (0x372AC9, 0x378B87), (0x372AD2, 0x372970), (0x372AF1, 0x378B87),
    (0x372B00, 0x372970), (0x372B10, 0x378B55),
)

class NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError(RuntimeError):
    """The pointer-defined boundary cannot be reproduced exactly."""

def _point(role: str, rva: int, encoded: str) -> dict[str, Any]:
    return {"role": role, "rva": rva, "encoded": bytes.fromhex(encoded), "api": None,
            "meaning": {"operation": "decoded_instruction", "source_semantic_names_assigned": False}}

_POINT_BYTES = (
    (0x3729B0,'55'),(0x3729B1,'8bec'),(0x3729B3,'83ec1c'),(0x3729B6,'53'),(0x3729B7,'56'),(0x3729B8,'8b750c'),(0x3729BB,'57'),(0x3729BC,'c645ff00'),(0x3729C0,'c745f401000000'),(0x3729C7,'8b5e08'),(0x3729CA,'8d4610'),(0x3729CD,'331d283f8900'),(0x3729D3,'50'),(0x3729D4,'53'),(0x3729D5,'8945ec'),(0x3729D8,'895df8'),(0x3729DB,'e890ffffff'),(0x3729E0,'8b7d10'),(0x3729E3,'57'),(0x3729E4,'e88754c9ff'),(0x3729E9,'8b4508'),(0x3729EC,'83c40c'),(0x3729EF,'f6400466'),(0x3729F3,'0f85ba000000'),(0x3729F9,'8945e4'),(0x3729FC,'8d45e4'),(0x3729FF,'897de8'),(0x372A02,'8b7e0c'),(0x372A05,'8946fc'),(0x372A08,'83fffe'),(0x372A0B,'0f84c9000000'),(0x372A11,'8d4702'),(0x372A14,'8d0447'),(0x372A17,'8b4c8304'),(0x372A1B,'8d0483'),(0x372A1E,'8b18'),(0x372A20,'8945f0'),(0x372A23,'85c9'),(0x372A25,'7465'),(0x372A27,'8d5610'),(0x372A2A,'e80f610000'),(0x372A2F,'b101'),(0x372A31,'884dff'),(0x372A34,'85c0'),(0x372A36,'7866'),(0x372A38,'7e55'),(0x372A3A,'8b4508'),(0x372A3D,'813863736de0'),(0x372A43,'7537'),(0x372A45,'833d50277f0000'),(0x372A4C,'742e'),(0x372A4E,'6850277f00'),(0x372A53,'e828ab0200'),(0x372A58,'83c404'),(0x372A5B,'85c0'),(0x372A5D,'741a'),(0x372A5F,'8b3550277f00'),(0x372A65,'8bce'),(0x372A67,'6a01'),(0x372A69,'ff7508'),(0x372A6C,'e84257feff'),(0x372A71,'ffd6'),(0x372A73,'8b750c'),(0x372A76,'83c408'),(0x372A79,'8b4508'),(0x372A7C,'8bd0'),(0x372A7E,'8bce'),(0x372A80,'e8e9600000'),(0x372A85,'397e0c'),(0x372A88,'746c'),(0x372A8A,'eb58'),(0x372A8C,'8a4dff'),(0x372A8F,'8bfb'),(0x372A91,'83fbfe'),(0x372A94,'7414'),(0x372A96,'8b5df8'),(0x372A99,'e973ffffff'),(0x372A9E,'8b5df8'),(0x372AA1,'c745f400000000'),(0x372AA8,'eb24'),(0x372AAA,'84c9'),(0x372AAC,'742c'),(0x372AAE,'8b5df8'),(0x372AB1,'eb1b'),(0x372AB3,'837e0cfe'),(0x372AB7,'7421'),(0x372AB9,'68283f8900'),(0x372ABE,'8d4610'),(0x372AC1,'bafeffffff'),(0x372AC6,'50'),(0x372AC7,'8bce'),(0x372AC9,'e8b9600000'),(0x372ACE,'ff75ec'),(0x372AD1,'53'),(0x372AD2,'e899feffff'),(0x372AD7,'83c408'),(0x372ADA,'8b45f4'),(0x372ADD,'5f'),(0x372ADE,'5e'),(0x372ADF,'5b'),(0x372AE0,'8be5'),(0x372AE2,'5d'),(0x372AE3,'c3'),(0x372AE4,'68283f8900'),(0x372AE9,'8d4610'),(0x372AEC,'8bd7'),(0x372AEE,'50'),(0x372AEF,'8bce'),(0x372AF1,'e891600000'),(0x372AF6,'895e0c'),(0x372AF9,'8d5e10'),(0x372AFC,'53'),(0x372AFD,'ff75f8'),(0x372B00,'e86bfeffff'),(0x372B05,'8b4df0'),(0x372B08,'83c408'),(0x372B0B,'8bd3'),(0x372B0D,'8b4908'),(0x372B10,'e840600000'),(0x372B15,'cc'),
)
_POINTS = tuple(_point(f"instruction_{index:03d}", rva, encoded) for index, (rva, encoded) in enumerate(_POINT_BYTES))
_FUNCTION = {"role": "relationship_defined_query_handler_first_callee_pointer_target_static_boundary", "entry_rva": _ENTRY, "body_size": 358, "body_sha256": _BODY, "cfg_canonical_sha256": _CFG, "direct_calls": [], "staged_dispatches": [], "call_r32": {"ESI": [0x372A71]}, "points": list(_POINTS), "semantic_facts": {"analysis_label": "__except_handler4", "analysis_label_only": True, "relationship_defined_by_opaque_pointer_syntax": True, "source_semantic_names_assigned": False, "runtime_or_success_claimed": False}}
_METHOD = {"structural_boundary": "PE-free validation reconstructs finite prerequisite, instruction, CFG, direct-edge, opaque operand, register-call, and owner-partition receipts. Exact bytes and the whole-atlas traversal require the sealed executable.", "not_claimed": ["target purpose, exception, handler, compiler, stack, register, security, ABI, argument meaning, state mutation, success, or normal-return semantics", "runtime reachability, invocation, order, frequency, source identity, target identity, or runtime effect", "contents or semantics of absolute operands, register loads, or their pointed-to data", "dynamic, computed, indirect, data, un-atlased, or Lua-side references"]}

def _same(a: Any, b: Any) -> bool: return _canonical_bytes(a) == _canonical_bytes(b)
def _identity(value: Mapping[str, Any], kind: str, digest: str, label: str) -> dict[str, Any]: return _source_identity(value, kind, digest, label)
def _facts_identity(facts: Mapping[str, Any]) -> dict[str, Any]:
    summary = _mapping(facts.get("summary"), "facts summary"); return {**_identity(facts, "pe_ghidra_program_facts", _FACTS, "program facts"), "function_count": summary.get("function_count"), "body_range_count": summary.get("body_range_count"), "function_body_bytes": summary.get("function_body_bytes")}

def _preflight(first: Mapping[str, Any], query: Mapping[str, Any], direct: Mapping[str, Any], facts: Mapping[str, Any]):
    identity = _mapping(facts.get("identity"), "facts identity")
    if identity.get("executable_sha256") != _EXE or not all(_same(v.get("build_identity"), dict(identity)) for v in (first, query, direct)): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("prerequisite build identity differs")
    if _first_callee_canonical_sha256(first) != _FIRST_CALLEE or _query_handler_canonical_sha256(query) != _QUERY_HANDLER: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("prerequisite receipt differs")
    return _facts_identity(facts), _identity(direct, DIRECT_KIND, _DIRECT, "direct calls"), _identity(query, QUERY_HANDLER_KIND, _QUERY_HANDLER, "query handler"), _identity(first, FIRST_CALLEE_KIND, _FIRST_CALLEE, "first callee")

def _direct_records(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    declared = {_rva(_mapping(row, "edge").get("instruction_rva"), "site"): _mapping(row, "edge") for row in _array(facts.get("ghidra_declared_direct_calls"), "edges")}
    functions = _atlas_functions(facts); result=[]
    for site, target in _DIRECT_EDGES:
        edge=declared.get(site)
        if edge is None or (_rva(edge.get("source_entry_rva"),"source"),_rva(edge.get("target_entry_rva"),"target entry"),_rva(edge.get("target_rva"),"target")) != (_ENTRY,target,target): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("declared direct edge differs")
        encoded=b"\xe8"+int(target-(site+5)).to_bytes(4,"little",signed=True)
        source=functions.get(_ENTRY); target_record=functions.get(target)
        if source is None or target_record is None: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("direct edge atlas join differs")
        result.append({"role":"opaque_declared_direct_edge", "instruction":{"rva":_hex(site),"size":5,"sha256":hashlib.sha256(encoded).hexdigest()}, "source_entry_rva":_hex(_ENTRY), "source_atlas_record_sha256":atlas_record_sha256(source), "source_body_size":source.get("body_size"), "source_body_sha256":source.get("body_sha256"), "target_entry_rva":_hex(target), "target_atlas_record_sha256":atlas_record_sha256(target_record), "target_body_size":target_record.get("body_size"), "target_body_sha256":target_record.get("body_sha256"), "ghidra_declared_direct_edge":_normalized_declared_edge(edge)})
    return result

def _operand_records(image: Any | None, instructions: list[Any] | None = None) -> list[dict[str, Any]]:
    specs=((0x3729CD,"opaque_absolute_memory_syntax","absolute_memory",1,"read","0x00893f28","0x00493f28",".data","0xc0000040",True),(0x372A45,"opaque_absolute_memory_syntax","absolute_memory",0,"read","0x007f2750","0x003f2750",".rdata","0x40000040",False),(0x372A4E,"opaque_absolute_immediate_syntax","immediate",0,"none","0x007f2750","0x003f2750",".rdata","0x40000040",False),(0x372A5F,"opaque_absolute_memory_esi_load_syntax","absolute_memory",1,"read","0x007f2750","0x003f2750",".rdata","0x40000040",False),(0x372AB9,"opaque_absolute_immediate_syntax","immediate",0,"none","0x00893f28","0x00493f28",".data","0xc0000040",True),(0x372AE4,"opaque_absolute_immediate_syntax","immediate",0,"none","0x00893f28","0x00493f28",".data","0xc0000040",True))
    points={r:e for r,e in _POINT_BYTES}; records=[]
    for site,role,operand_class,operand_index,access,va,rva,name,chars,writable in specs:
        raw=bytes.fromhex(points[site]); record={"role":role,"instruction":{"rva":_hex(site),"size":len(raw),"sha256":hashlib.sha256(raw).hexdigest()},"operand_class":operand_class,"operand_index":operand_index,"operand_access":access,"operand_va":va,"operand_rva":rva,"section_name":name,"section_characteristics":chars,"section_writable":writable,"file_backed":True,"contents_or_semantics_opaque":True}
        if operand_class=="absolute_memory": record.update({"segment_register":None,"base_register":None,"index_register":None})
        records.append(record)
        if image is not None:
            section=next((s for s in image.sections if s.virtual_address<=int(rva,16)<s.virtual_address+s.virtual_size),None)
            if section is None or (section.name,_hex(section.characteristics),bool(section.characteristics&0x80000000),image.rva_to_file_offset(int(rva,16)) is not None)!=(name,chars,writable,True): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("operand section differs")
    indirect={"role":"opaque_register_call_syntax","instruction":{"rva":"0x00372a71","size":2,"sha256":hashlib.sha256(bytes.fromhex("ffd6")).hexdigest()},"register":"ESI","target_identity_or_runtime_behavior_opaque":True}
    if instructions is not None:
        import capstone, capstone.x86_const as x
        by={i.address-instructions[0].address+_ENTRY:i for i in instructions}; call=by.get(0x372A71); load=by.get(0x372A5F)
        for site,_,kind,index,access,va,_,_,_,_ in specs:
            instruction=by.get(site); operand=None if instruction is None or len(instruction.operands)<=index else instruction.operands[index]
            if operand is None or (access=="read" and not (operand.access & capstone.CS_AC_READ)) or (access=="none" and operand.access!=0): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("operand access differs")
            if kind=="immediate":
                if operand.type!=x.X86_OP_IMM or (int(operand.imm)&0xffffffff)!=int(va,16): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("immediate operand differs")
            elif operand.type!=x.X86_OP_MEM or operand.mem.segment!=x.X86_REG_INVALID or operand.mem.base!=x.X86_REG_INVALID or operand.mem.index!=x.X86_REG_INVALID or (int(operand.mem.disp)&0xffffffff)!=int(va,16): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("absolute-memory operand differs")
        if call is None or bytes(call.bytes)!=b"\xff\xd6" or call.id!=x.X86_INS_CALL or call.operands[0].type!=x.X86_OP_REG or call.reg_name(call.operands[0].reg).upper()!="ESI": raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("register call differs")
        if load is None or bytes(load.bytes)!=bytes.fromhex("8b3550277f00") or load.id!=x.X86_INS_MOV: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("ESI load differs")
    return records+[indirect]

def _reference_scan(data: bytes | None, image: Any | None, decoder: Any | None, facts: Mapping[str, Any]) -> dict[str, Any]:
    functions=_atlas_functions(facts); target=functions.get(_ENTRY)
    if target is None or target.get("body_size")!=358 or target.get("body_sha256")!=_BODY or atlas_record_sha256(target)!=_ATLAS: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("target atlas differs")
    image_base=_rva(_mapping(facts.get("ghidra"),"ghidra").get("image_base"),"image base")
    refs=[]; instruction_count=0
    for site,owner in _REFERENCES:
        owner_record=functions.get(owner)
        if owner_record is None: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("reference owner missing")
        raw=bytes.fromhex(_POINTER[1]); refs.append({"instruction_rva":_hex(site),"instruction_size":len(raw),"instruction_sha256":hashlib.sha256(raw).hexdigest(),"owner_entry_rva":_hex(owner),"owner_atlas_record_sha256":atlas_record_sha256(owner_record),"target_rva":_hex(_ENTRY),"target_atlas_record_sha256":_ATLAS,"target_va":_hex(image_base+_ENTRY),"operand_class":"immediate","operand_index":0,"use_class":"other_address","call_form":None,"ghidra_declared_direct_edge":None})
    expected={"target_rvas":[_hex(_ENTRY)],"target_vas":[_hex(image_base+_ENTRY)],"scope":{"atlas_function_count":25312,"atlas_body_range_count":25490,"decoded_bytes":3735718,"decoded_instructions":1153814,"all_declared_ranges_decoded":True,"operand_classes":["absolute_memory","immediate"]},"references":refs,"aggregates":{"reference_count":3,"direct_call_count":0,"comparison_count":0,"other_address_count":3,"memory_operand_count":0,"owner_count":3},"owner_partition":[{"owner_entry_rva":r["owner_entry_rva"],"owner_atlas_record_sha256":r["owner_atlas_record_sha256"],"reference_count":1} for r in refs]}
    if data is None: return expected
    import capstone.x86_const as x
    observed=[]; ranges=0; decoded=0
    decoder.detail=True
    from src.observatory.native_lua_cclosure_setfield_publications import _decode_range
    for owner,function in sorted(functions.items()):
        for span in _array(function.get("ranges"),"ranges"):
            start=_rva(_mapping(span,"range").get("start_rva"),"range start"); size=_mapping(span,"range").get("size")
            for ins in _decode_range(data,image,start,size,decoder):
                instruction_count += 1
                for index,op in enumerate(ins.operands):
                    if (op.type==x.X86_OP_IMM and (int(op.imm)&0xffffffff)==image.image_base+_ENTRY) or (op.type==x.X86_OP_MEM and op.mem.segment==x.X86_REG_INVALID and op.mem.base==x.X86_REG_INVALID and op.mem.index==x.X86_REG_INVALID and (int(op.mem.disp)&0xffffffff)==image.image_base+_ENTRY):
                        raw=bytes(ins.bytes); operand_class="immediate" if op.type==x.X86_OP_IMM else "absolute_memory"; observed.append({"instruction_rva":_hex(ins.address-image.image_base),"instruction_size":ins.size,"instruction_sha256":hashlib.sha256(raw).hexdigest(),"owner_entry_rva":_hex(owner),"owner_atlas_record_sha256":atlas_record_sha256(function),"target_rva":_hex(_ENTRY),"target_atlas_record_sha256":_ATLAS,"target_va":_hex(image.image_base+_ENTRY),"operand_class":operand_class,"operand_index":index,"use_class":"memory_operand" if operand_class=="absolute_memory" else "direct_call" if ins.id==x.X86_INS_CALL else "comparison" if ins.id in {x.X86_INS_CMP,x.X86_INS_TEST} else "other_address","call_form":"x86_relative_near_call_e8" if len(raw)==5 and raw[0]==0xe8 else None,"ghidra_declared_direct_edge":None})
            ranges+=1; decoded+=size
    observed.sort(key=lambda r:(r["instruction_rva"],r["operand_index"]))
    if observed!=refs: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("whole-atlas pointer-reference partition differs")
    if (ranges,decoded,instruction_count)!=(25490,3735718,1153814): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("whole-atlas scan scope differs")
    return expected

def _pointer_predecessor(first: Mapping[str, Any], scan: Mapping[str, Any]) -> dict[str, Any]:
    records=_array(_mapping(first.get("native_calls"),"first native calls").get("opaque_instruction_syntax"),"first opaque syntax")
    matches=[_mapping(r,"pointer predecessor") for r in records if _mapping(r,"pointer predecessor").get("role")=="opaque_absolute_immediate_push_syntax" and _rva(_mapping(_mapping(r,"pointer predecessor").get("instruction"),"instruction").get("rva"),"site")==_POINTER[0]]
    if len(matches)!=1: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("pointer predecessor differs")
    record=matches[0]; inst=_mapping(record.get("instruction"),"pointer instruction"); raw=bytes.fromhex(_POINTER[1])
    if (inst.get("size"),inst.get("sha256"),record.get("operand_rva"))!=(len(raw),hashlib.sha256(raw).hexdigest(),_hex(_ENTRY)): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("pointer predecessor bytes differ")
    reference=next((r for r in _array(scan.get("references"),"references") if r.get("instruction_rva")==_hex(_POINTER[0]) and r.get("owner_entry_rva")==_hex(_POINTER[0])),None)
    if reference is None or (reference.get("call_form"),reference.get("ghidra_declared_direct_edge"),reference.get("use_class"))!=(None,None,"other_address"): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("pointer predecessor scan join differs")
    return record

def _expected_body(facts: Mapping[str, Any]) -> dict[str, Any]:
    if _atlas_functions(facts).get(_ENTRY) is None: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("target absent")
    return {"role":_FUNCTION["role"],"entry_rva":_hex(_ENTRY),"atlas_record_sha256":_ATLAS,"body_size":358,"body_sha256":_BODY,"range_start_rva":_hex(_ENTRY),"range_size":358,"control_flow_graph_canonical_sha256":_CFG,"reviewed_points":[_expected_point_record(p) for p in _POINTS],"direct_lua_calls":[],"staged_lua_dispatches":[],"call_r32_audit":[{"register":r,"call_rvas":["0x00372a71"] if r=="ESI" else []} for r in _REGISTER_NAMES],"register_call_partition_complete":True,"semantic_facts":_FUNCTION["semantic_facts"]}
def _decoder_contract() -> dict[str, Any]: return {"name":"capstone","version":SUPPORTED_CAPSTONE_VERSION,"architecture":"x86","mode_bits":32,"sealed_instruction_count":120,"register_call_encoding_audit":[{"register":r,"encoding":f"ff{0xd0+i:02x}"} for i,r in enumerate(_REGISTER_NAMES)]}
def _summary(_: Mapping[str, Any]) -> dict[str, Any]: return {"reviewed_query_handler_first_callee_pointer_target_count":1,"reviewed_query_handler_first_callee_pointer_target_bytes":358,"sealed_instruction_count":120,"sealed_control_flow_graph_count":1,"sealed_control_flow_graph_node_count":120,"sealed_control_flow_graph_edge_count":130,"direct_lua_call_count":0,"staged_lua_dispatch_count":0,"call_r32_count":1,"literal_count":0,"native_direct_edge_count":11,"opaque_operand_syntax_count":7,"first_callee_pointer_predecessor_count":1,"target_reference_count":3,"target_reference_direct_call_count":0,"target_reference_comparison_count":0,"target_reference_other_address_count":3,"target_reference_memory_operand_count":0,"target_reference_owner_count":3,"schema_violations":0}

def build_native_query_handler_first_callee_pointer_target_static_boundary(executable: Path, first_callee_static_boundary: Mapping[str, Any], query_handler_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any], *, inventory: Mapping[str, Any]) -> dict[str, Any]:
    try:
        for value,label in ((first_callee_static_boundary,"first callee"),(query_handler_static_boundary,"query handler"),(direct_calls,"direct calls"),(program_facts,"facts"),(inventory,"inventory")): _validate_json_tree(value,label)
        receipt=validate_native_lua_direct_call_census(executable,direct_calls,program_facts,inventory=inventory)
        if receipt.get("status")!="verified" or receipt.get("evidence_sha256")!=_DIRECT: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("direct prerequisite differs")
        atlas,direct,query,first=_preflight(first_callee_static_boundary,query_handler_static_boundary,direct_calls,program_facts); data,image,digest=_load_executable(executable)
        if digest!=_EXE: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("executable differs")
        decoder,_=_decoder(); decoder.detail=True
        from src.observatory.native_lua_cclosure_setfield_publications import _decode_range
        instructions=_decode_range(data,image,_ENTRY,358,decoder)
        if len(instructions)!=120 or hashlib.sha256(b"".join(bytes(i.bytes) for i in instructions)).hexdigest()!=_BODY: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("target bytes differ")
        import capstone,capstone.x86_const as x
        graph=_with_edi_writes(_enhanced_cfg(instructions,image.image_base,(_ENTRY,358),capstone,x),instructions,x); graph["caller_entry_rva"]=_hex(_ENTRY)
        if _canonical_sha256(graph)!=_CFG: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("target CFG differs")
        by={i.address-image.image_base:i for i in instructions}; body={**_expected_body(program_facts),"reviewed_points":[_point_record(by[p["rva"]],image.image_base,p) for p in _POINTS],"call_r32_audit":_call_r32_audit(instructions,_FUNCTION)}; scan=_reference_scan(data,image,decoder,program_facts)
        direct_lua=[call for record in _array(direct_calls.get("records"),"direct records") if _mapping(record,"direct record").get("entry_rva")==_hex(_ENTRY) for call in _array(_mapping(record,"direct record").get("direct_lua_import_calls"),"direct Lua calls")]
        if direct_lua: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("direct Lua-call partition differs")
        result={"schema_version":SCHEMA_VERSION,"analysis_kind":ANALYSIS_KIND,"build_identity":dict(_mapping(program_facts.get("identity"),"identity")),"atlas":atlas,"direct_call_census":direct,"query_handler_static_boundary":query,"first_callee_static_boundary":first,"first_callee_pointer_predecessor":_pointer_predecessor(first_callee_static_boundary,scan),"decoder":_decoder_contract(),"function_bodies":[body],"control_flow_graphs":[graph],"native_calls":{"direct":_direct_records(program_facts),"opaque_instruction_syntax":_operand_records(image,instructions)},"whole_atlas_reference_scan":scan,"method":_METHOD}; result["summary"]=_summary(result); _assert_publication_safe(result)
        if _load_executable(executable)[2]!=digest: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("executable changed")
        validate_native_query_handler_first_callee_pointer_target_static_boundary_structure(result,first_callee_static_boundary,query_handler_static_boundary,direct_calls,program_facts); return result
    except NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError: raise
    except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassReturnHelperChainError,PEAnchorError,OSError) as exc: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError(str(exc)) from exc

def validate_native_query_handler_first_callee_pointer_target_static_boundary_structure(evidence: Mapping[str, Any], first_callee_static_boundary: Mapping[str, Any], query_handler_static_boundary: Mapping[str, Any], direct_calls: Mapping[str, Any], program_facts: Mapping[str, Any]) -> dict[str, Any]:
    try:
        for value,label in ((evidence,"evidence"),(first_callee_static_boundary,"first callee"),(query_handler_static_boundary,"query handler"),(direct_calls,"direct calls"),(program_facts,"facts")): _validate_json_tree(value,label)
        receipt=validate_native_lua_direct_call_structure(direct_calls,program_facts)
        if receipt.get("status")!="structurally_verified" or receipt.get("evidence_sha256")!=_DIRECT: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("direct prerequisite differs")
        atlas,direct,query,first=_preflight(first_callee_static_boundary,query_handler_static_boundary,direct_calls,program_facts); evidence=_mapping(evidence,"evidence")
        _exact_keys(evidence,{"schema_version","analysis_kind","build_identity","atlas","direct_call_census","query_handler_static_boundary","first_callee_static_boundary","first_callee_pointer_predecessor","decoder","function_bodies","control_flow_graphs","native_calls","whole_atlas_reference_scan","method","summary"},"evidence")
        if type(evidence.get("schema_version")) is not int or evidence.get("schema_version")!=SCHEMA_VERSION or evidence.get("analysis_kind")!=ANALYSIS_KIND: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("schema differs")
        if not all((_same(evidence.get("build_identity"),dict(_mapping(program_facts.get("identity"),"identity"))),_same(evidence.get("atlas"),atlas),_same(evidence.get("direct_call_census"),direct),_same(evidence.get("query_handler_static_boundary"),query),_same(evidence.get("first_callee_static_boundary"),first),_same(evidence.get("decoder"),_decoder_contract()),_same(evidence.get("method"),_METHOD))): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("pinned prerequisite differs")
        bodies=_array(evidence.get("function_bodies"),"bodies")
        if len(bodies)!=1 or not _same(bodies[0],_expected_body(program_facts)): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("body differs")
        graphs=_validated_graphs({"control_flow_graphs":evidence.get("control_flow_graphs")},_atlas_functions(program_facts))
        if set(graphs)!={_ENTRY} or _canonical_sha256(graphs[_ENTRY][0])!=_CFG or (graphs[_ENTRY][0].get("node_count"),graphs[_ENTRY][0].get("edge_count"))!=(120,130): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("CFG differs")
        nodes={_rva(node.get("rva"),"node rva"):node for node in _array(graphs[_ENTRY][0].get("nodes"),"nodes")}
        for point in _array(bodies[0].get("reviewed_points"),"points"):
            node=nodes.get(_rva(_mapping(point,"point").get("rva"),"point rva"))
            if node is None or (point.get("size"),point.get("sha256"))!=(node.get("size"),node.get("sha256")): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("point CFG join differs")
        reviewed={point.get("rva"):point for point in _array(bodies[0].get("reviewed_points"),"points")}
        for edge in _array(_mapping(evidence.get("native_calls"),"native calls").get("direct"),"direct edges"):
            instruction=_mapping(_mapping(edge,"edge").get("instruction"),"edge instruction"); point=reviewed.get(instruction.get("rva"))
            if point is None or (point.get("size"),point.get("sha256"))!=(instruction.get("size"),instruction.get("sha256")): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("direct edge point join differs")
        for record in _array(_mapping(evidence.get("native_calls"),"native calls").get("opaque_instruction_syntax"),"opaque syntax"):
            instruction=_mapping(_mapping(record,"syntax").get("instruction"),"syntax instruction"); point=reviewed.get(instruction.get("rva"))
            if point is None or (point.get("size"),point.get("sha256"))!=(instruction.get("size"),instruction.get("sha256")): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("opaque syntax point join differs")
        scan=_mapping(evidence.get("whole_atlas_reference_scan"),"scan"); expected_scan=_reference_scan(None,None,None,program_facts)
        if not _same(scan,expected_scan) or not _same(evidence.get("native_calls"),{"direct":_direct_records(program_facts),"opaque_instruction_syntax":_operand_records(None)}) or not _same(evidence.get("first_callee_pointer_predecessor"),_pointer_predecessor(first_callee_static_boundary,scan)) or not _same(evidence.get("summary"),_summary(evidence)): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("cross-check differs")
        _assert_publication_safe(evidence); return {"schema_version":SCHEMA_VERSION,"analysis_kind":STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","build_identity":dict(evidence["build_identity"]),"evidence_sha256":_canonical_sha256(evidence),"summary":dict(evidence["summary"])}
    except NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError: raise
    except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassReturnHelperChainError) as exc: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError(str(exc)) from exc

def validate_native_query_handler_first_callee_pointer_target_static_boundary(executable: Path,evidence: Mapping[str, Any],first_callee_static_boundary: Mapping[str, Any],query_handler_static_boundary: Mapping[str, Any],direct_calls: Mapping[str, Any],program_facts: Mapping[str, Any],*,inventory: Mapping[str, Any]) -> dict[str, Any]:
    rebuilt=build_native_query_handler_first_callee_pointer_target_static_boundary(executable,first_callee_static_boundary,query_handler_static_boundary,direct_calls,program_facts,inventory=inventory)
    if not _same(evidence,rebuilt): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("evidence differs from exact rebuild")
    return {"schema_version":SCHEMA_VERSION,"analysis_kind":VERIFICATION_KIND,"status":"verified","build_identity":dict(rebuilt["build_identity"]),"evidence_sha256":_canonical_sha256(rebuilt),"summary":dict(rebuilt["summary"])}
def encode_native_query_handler_first_callee_pointer_target_static_boundary(value: Mapping[str, Any]) -> str:
    try: _validate_json_tree(value); return json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2,sort_keys=True)+"\n"
    except NativeLuaCClosurePublicationError as exc: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError(str(exc)) from exc
