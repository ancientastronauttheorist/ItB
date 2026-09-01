"""Immutable machine-code receipt for four adjacent pointer-target callees.

The four bodies are grouped solely because their sealed atlas ranges are
contiguous.  All labels, registers, operands, and control syntax are retained
as opaque decoded facts; this module deliberately makes no semantic claim.
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
    _normalized_declared_edge, _point_record, _source_identity, _with_edi_writes,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError, _array, _assert_publication_safe,
    _atlas_functions, _decode_range, _exact_keys, _hex, _mapping, _rva,
    _validate_json_tree,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_KIND, SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError, _decoder, _load_executable,
    validate_native_lua_direct_call_census, validate_native_lua_direct_call_structure,
)
from src.observatory.native_query_handler_first_callee_pointer_target_static_boundary import (
    ANALYSIS_KIND as POINTER_TARGET_KIND,
    _canonical_sha256 as _pointer_target_canonical_sha256,
)
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_POINTER_TARGET = "41ee47debe789243dfe9fd9566958846cd79cb82549acb99eafc9e2b5cfd9349"
_ENTRIES = (0x378B3E, 0x378B55, 0x378B6E, 0x378B87)
_BODIES = {
    0x378B3E: (23, "6e2b3bd553f0ffdd43df815cf3341fce2e76a73e8f9b243867c06b12310701fb", "21bfa842aaa26c0306ff5b8da85ba63bc13daaa71cd930aaa24b91da1e34ed6c", "a88b1abbcaa972963f916fd4574f173aafcc6a899d26c28848d86d2f4a9c6b0c", 16, 15),
    0x378B55: (25, "c60b762b740ca702e7dd2f96ac96f31c9122758f9c0bf0b518a54cda2986dfe7", "0bf347712ab1049e562b947e0a83c7669425e76e910aab6096bb42c8a45f2c46", "db652309bf25985f8a5909d782947fbb6b2ebed9d29d251ed091c973b6e0f8eb", 11, 10),
    0x378B6E: (25, "e4c5374582d34dcaf8ef3cd401b6bcc2e38a1cc1ab6950af7eaf0ce7129c3286", "e58ae61360dfe3582ded9e78d44ae9c56e1226ebad653da407ed81b5f39ab4bc", "34669d29c9c8fd8a47c973be00fdbd8b4df94e34e48574542470bd70bdcf2bf4", 15, 14),
    0x378B87: (23, "00a48f1b6eb852efff2b66f536e59bcdffe8c722348a1127d976604a5c3cc994", "6cb344ca1b46add4cfae6c7a40acda49140fff99365b33a5d0f572e8047fc5b3", "e4f26af633adad0cf0c255d9f96cc8ce2202d91fd5a8a3c65b7f530303f2505c", 9, 8),
}
_POINT_BYTES = {
 0x378B3E: ((0x378B3E,"55"),(0x378B3F,"56"),(0x378B40,"57"),(0x378B41,"53"),(0x378B42,"8bea"),(0x378B44,"33c0"),(0x378B46,"33db"),(0x378B48,"33d2"),(0x378B4A,"33f6"),(0x378B4C,"33ff"),(0x378B4E,"ffd1"),(0x378B50,"5b"),(0x378B51,"5f"),(0x378B52,"5e"),(0x378B53,"5d"),(0x378B54,"c3")),
 0x378B55: ((0x378B55,"8bea"),(0x378B57,"8bf1"),(0x378B59,"8bc1"),(0x378B5B,"6a01"),(0x378B5D,"e8b3feffff"),(0x378B62,"33c0"),(0x378B64,"33db"),(0x378B66,"33c9"),(0x378B68,"33d2"),(0x378B6A,"33ff"),(0x378B6C,"ffe6")),
 0x378B6E: ((0x378B6E,"55"),(0x378B6F,"8bec"),(0x378B71,"53"),(0x378B72,"56"),(0x378B73,"57"),(0x378B74,"6a00"),(0x378B76,"52"),(0x378B77,"68828b7700"),(0x378B7C,"51"),(0x378B7D,"e816400200"),(0x378B82,"5f"),(0x378B83,"5e"),(0x378B84,"5b"),(0x378B85,"5d"),(0x378B86,"c3")),
 0x378B87: ((0x378B87,"55"),(0x378B88,"8b6c2408"),(0x378B8C,"52"),(0x378B8D,"51"),(0x378B8E,"ff742414"),(0x378B92,"e8a9feffff"),(0x378B97,"83c40c"),(0x378B9A,"5d"),(0x378B9B,"c20800")),
}
_PARENT_EDGES = ((0x372A2A,0x378B3E),(0x372A80,0x378B6E),(0x372AC9,0x378B87),(0x372AF1,0x378B87),(0x372B10,0x378B55))
_OUTGOING_EDGES = ((0x378B5D,0x378B55,0x378A15),(0x378B7D,0x378B6E,0x39CB98),(0x378B92,0x378B87,0x378A40))

class NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError(RuntimeError):
    """The contiguous four-body receipt cannot be reproduced exactly."""

def _same(a: Any, b: Any) -> bool: return _canonical_bytes(a) == _canonical_bytes(b)
def _identity(value: Mapping[str, Any], kind: str, digest: str, label: str) -> dict[str, Any]: return _source_identity(value,kind,digest,label)
def _point(role: str, rva: int, encoded: str) -> dict[str, Any]: return {"role":role,"rva":rva,"encoded":bytes.fromhex(encoded),"api":None,"meaning":{"operation":"decoded_instruction","source_semantic_names_assigned":False}}
def _points(entry: int) -> tuple[dict[str,Any],...]: return tuple(_point(f"instruction_{i:03d}",r,b) for i,(r,b) in enumerate(_POINT_BYTES[entry]))
def _facts_identity(facts: Mapping[str,Any]) -> dict[str,Any]:
    summary=_mapping(facts.get("summary"),"facts summary")
    return {**_identity(facts,"pe_ghidra_program_facts",_FACTS,"program facts"),"function_count":summary.get("function_count"),"body_range_count":summary.get("body_range_count"),"function_body_bytes":summary.get("function_body_bytes")}
def _preflight(pointer: Mapping[str,Any], direct: Mapping[str,Any], facts: Mapping[str,Any]):
    identity=_mapping(facts.get("identity"),"facts identity")
    if identity.get("executable_sha256")!=_EXE or not all(_same(v.get("build_identity"),dict(identity)) for v in (pointer,direct)): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("prerequisite build identity differs")
    if _pointer_target_canonical_sha256(pointer)!=_POINTER_TARGET: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("pointer-target prerequisite differs")
    return _facts_identity(facts),_identity(direct,DIRECT_KIND,_DIRECT,"direct calls"),_identity(pointer,POINTER_TARGET_KIND,_POINTER_TARGET,"pointer target")
def _body(entry: int, facts: Mapping[str,Any]) -> dict[str,Any]:
    size,body,atlas,cfg,nodes,edges=_BODIES[entry]; f=_atlas_functions(facts).get(entry)
    if f is None or (f.get("body_size"),f.get("body_sha256"),atlas_record_sha256(f)) != (size,body,atlas): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("cluster atlas differs")
    calls={0x378B3E:{"ECX":[0x378B4E]},0x378B55:{},0x378B6E:{},0x378B87:{}}[entry]
    return {"role":"contiguous_atlas_member_opaque_static_boundary","entry_rva":_hex(entry),"atlas_record_sha256":atlas,"body_size":size,"body_sha256":body,"range_start_rva":_hex(entry),"range_size":size,"control_flow_graph_canonical_sha256":cfg,"reviewed_points":[_expected_point_record(p) for p in _points(entry)],"direct_lua_calls":[],"staged_lua_dispatches":[],"call_r32_audit":[{"register":r,"call_rvas":[_hex(x) for x in calls.get(r,[])]} for r in _REGISTER_NAMES],"register_call_partition_complete":True,"semantic_facts":{"adjacency_only":True,"analysis_labels_opaque":True,"source_semantic_names_assigned":False,"runtime_or_success_claimed":False}}
def _direct_records(facts: Mapping[str,Any]) -> list[dict[str,Any]]:
    declared={_rva(_mapping(r,"edge").get("instruction_rva"),"site"):_mapping(r,"edge") for r in _array(facts.get("ghidra_declared_direct_calls"),"edges")}; functions=_atlas_functions(facts); rows=[]
    observed={(site,_rva(edge.get("source_entry_rva"),"source"),_rva(edge.get("target_rva"),"target")) for site,edge in declared.items() if _rva(edge.get("source_entry_rva"),"source") in _ENTRIES}
    if observed != set(_OUTGOING_EDGES): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("outgoing declared-edge partition differs")
    for site,source,target in _OUTGOING_EDGES:
        edge=declared.get(site)
        if edge is None or (_rva(edge.get("source_entry_rva"),"source"),_rva(edge.get("target_entry_rva"),"entry"),_rva(edge.get("target_rva"),"target")) != (source,target,target): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("outgoing declared edge differs")
        raw=b"\xe8"+int(target-(site+5)).to_bytes(4,"little",signed=True); sf,tf=functions.get(source),functions.get(target)
        if sf is None or tf is None: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("outgoing edge atlas join differs")
        rows.append({"role":"opaque_declared_direct_edge","instruction":{"rva":_hex(site),"size":5,"sha256":hashlib.sha256(raw).hexdigest()},"source_entry_rva":_hex(source),"source_atlas_record_sha256":atlas_record_sha256(sf),"source_body_size":sf.get("body_size"),"source_body_sha256":sf.get("body_sha256"),"target_entry_rva":_hex(target),"target_atlas_record_sha256":atlas_record_sha256(tf),"target_body_size":tf.get("body_size"),"target_body_sha256":tf.get("body_sha256"),"ghidra_declared_direct_edge":_normalized_declared_edge(edge)})
    return rows
def _parent_edges(pointer: Mapping[str,Any], facts: Mapping[str,Any]) -> list[dict[str,Any]]:
    rows=_array(_mapping(pointer.get("native_calls"),"pointer calls").get("direct"),"pointer direct edges"); expected=[]
    for site,target in _PARENT_EDGES:
        hit=next((r for r in rows if _rva(_mapping(_mapping(r,"edge").get("instruction"),"instruction").get("rva"),"site")==site and _rva(_mapping(r,"edge").get("target_entry_rva"),"target")==target),None)
        if hit is None: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("pointer parent edge differs")
        expected.append(dict(_mapping(hit,"pointer parent edge")))
    return expected
def _opaque_syntax(image: Any|None, instructions: dict[int,list[Any]]|None=None) -> list[dict[str,Any]]:
    specs=((0x378B4E,"opaque_register_call_syntax","ECX","ffd1"),(0x378B6C,"opaque_register_jmp_syntax","ESI","ffe6"),(0x378B77,"opaque_absolute_immediate_syntax",None,"68828b7700"))
    out=[]
    for site,role,register,encoded in specs:
        rec={"role":role,"instruction":{"rva":_hex(site),"size":len(bytes.fromhex(encoded)),"sha256":hashlib.sha256(bytes.fromhex(encoded)).hexdigest()},"target_identity_or_runtime_behavior_opaque":True}
        if register is not None: rec["register"]=register
        else: rec.update({"operand_class":"immediate","operand_index":0,"operand_access":"none","operand_va":"0x00778b82","operand_rva":"0x00378b82","section_name":".text","section_characteristics":"0x60000020","section_writable":False,"file_backed":True,"contents_or_semantics_opaque":True})
        out.append(rec)
    if image is not None:
        section=next((s for s in image.sections if s.virtual_address<=0x378B82<s.virtual_address+s.virtual_size),None)
        if section is None or (section.name,_hex(section.characteristics),bool(section.characteristics&0x80000000),image.rva_to_file_offset(0x378B82) is not None)!=(".text","0x60000020",False,True): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("absolute operand section differs")
    if instructions is not None:
        import capstone, capstone.x86_const as x
        by={i.address-image.image_base:i for ins in instructions.values() for i in ins}
        expected={0x378B4E:(x.X86_INS_CALL,"ECX",b"\xff\xd1"),0x378B6C:(x.X86_INS_JMP,"ESI",b"\xff\xe6")}
        for site,(kind,register,raw) in expected.items():
            ins=by.get(site)
            if ins is None or ins.id!=kind or bytes(ins.bytes)!=raw or len(ins.operands)!=1 or ins.operands[0].type!=x.X86_OP_REG or ins.reg_name(ins.operands[0].reg).upper()!=register: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("indirect-control syntax differs")
        push=by.get(0x378B77)
        if push is None or push.id!=x.X86_INS_PUSH or bytes(push.bytes)!=bytes.fromhex("68828b7700") or len(push.operands)!=1 or push.operands[0].type!=x.X86_OP_IMM or (int(push.operands[0].imm)&0xffffffff)!=0x778B82 or push.operands[0].access!=0: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("absolute immediate syntax differs")
        pe=[]
        for ins in by.values():
            for index,op in enumerate(ins.operands):
                if op.type==x.X86_OP_IMM: value,kind=int(op.imm)&0xffffffff,"immediate"
                elif op.type==x.X86_OP_MEM and op.mem.segment==x.X86_REG_INVALID and op.mem.base==x.X86_REG_INVALID and op.mem.index==x.X86_REG_INVALID: value,kind=int(op.mem.disp)&0xffffffff,"absolute_memory"
                else: continue
                if any(section.virtual_address <= value-image.image_base < section.virtual_address+section.virtual_size for section in image.sections): pe.append((ins.address-image.image_base,index,kind,op.access))
        if sorted(pe) != [(0x378B5D,0,"immediate",0),(0x378B77,0,"immediate",0),(0x378B7D,0,"immediate",0),(0x378B92,0,"immediate",0)]: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("PE-address operand partition differs")
    return out
def _scan(data: bytes|None,image: Any|None,decoder: Any|None,facts: Mapping[str,Any]) -> dict[str,Any]:
    functions=_atlas_functions(facts); base=_rva(_mapping(facts.get("ghidra"),"ghidra").get("image_base"),"base"); refs=[]; declared={_rva(_mapping(row,"edge").get("instruction_rva"),"site"):_mapping(row,"edge") for row in _array(facts.get("ghidra_declared_direct_calls"),"declared edges")}
    for site,target in _PARENT_EDGES:
        f=functions.get(0x3729B0); raw=b"\xe8"+int(target-(site+5)).to_bytes(4,"little",signed=True); edge=declared.get(site)
        if edge is None or (_rva(edge.get("source_entry_rva"),"source"),_rva(edge.get("target_entry_rva"),"target entry"),_rva(edge.get("target_rva"),"target")) != (0x3729B0,target,target): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("parent declared edge differs")
        refs.append({"instruction_rva":_hex(site),"instruction_size":5,"instruction_sha256":hashlib.sha256(raw).hexdigest(),"owner_entry_rva":"0x003729b0","owner_atlas_record_sha256":atlas_record_sha256(f),"target_rva":_hex(target),"target_atlas_record_sha256":_BODIES[target][2],"target_va":_hex(base+target),"operand_class":"immediate","operand_index":0,"use_class":"direct_call","call_form":"x86_relative_near_call_e8","ghidra_declared_direct_edge":_normalized_declared_edge(edge)})
    refs.sort(key=lambda r:(r["instruction_rva"],r["target_rva"]))
    expected={"target_rvas":[_hex(x) for x in _ENTRIES],"target_vas":[_hex(base+x) for x in _ENTRIES],"scope":{"atlas_function_count":25312,"atlas_body_range_count":25490,"decoded_bytes":3735718,"decoded_instructions":1153814,"all_declared_ranges_decoded":True,"operand_classes":["absolute_memory","immediate"]},"references":refs,"aggregates":{"target_count":4,"reference_count":5,"direct_call_count":5,"comparison_count":0,"other_address_count":0,"memory_operand_count":0,"owner_count":1,"immediate_operand_count":5,"absolute_memory_operand_count":0},"target_partition":[{"target_rva":_hex(entry),"target_atlas_record_sha256":_BODIES[entry][2],"reference_count":sum(r["target_rva"]==_hex(entry) for r in refs)} for entry in _ENTRIES],"owner_partition":[{"owner_entry_rva":"0x003729b0","owner_atlas_record_sha256":atlas_record_sha256(functions[0x3729B0]),"reference_count":5}]}
    if data is None: return expected
    import capstone.x86_const as x
    observed=[]; count=decoded=ranges=0; decoder.detail=True; targets={image.image_base+entry:entry for entry in _ENTRIES}
    for owner,function in sorted(functions.items()):
        for span in _array(function.get("ranges"),"ranges"):
            start=_rva(_mapping(span,"range").get("start_rva"),"start"); size=_mapping(span,"range").get("size")
            for ins in _decode_range(data,image,start,size,decoder):
                count+=1
                for index,op in enumerate(ins.operands):
                    value=(int(op.imm)&0xffffffff) if op.type==x.X86_OP_IMM else (int(op.mem.disp)&0xffffffff if op.type==x.X86_OP_MEM and op.mem.segment==x.X86_REG_INVALID and op.mem.base==x.X86_REG_INVALID and op.mem.index==x.X86_REG_INVALID else None)
                    if value not in targets: continue
                    target=targets[value]; raw=bytes(ins.bytes); cls="immediate" if op.type==x.X86_OP_IMM else "absolute_memory"
                    observed.append({"instruction_rva":_hex(ins.address-image.image_base),"instruction_size":ins.size,"instruction_sha256":hashlib.sha256(raw).hexdigest(),"owner_entry_rva":_hex(owner),"owner_atlas_record_sha256":atlas_record_sha256(function),"target_rva":_hex(target),"target_atlas_record_sha256":_BODIES[target][2],"target_va":_hex(image.image_base+target),"operand_class":cls,"operand_index":index,"use_class":"memory_operand" if cls=="absolute_memory" else "direct_call" if ins.id==x.X86_INS_CALL else "comparison" if ins.id in {x.X86_INS_CMP,x.X86_INS_TEST} else "other_address","call_form":"x86_relative_near_call_e8" if len(raw)==5 and raw[0]==0xe8 else None,"ghidra_declared_direct_edge":_normalized_declared_edge(declared[ins.address-image.image_base]) if ins.address-image.image_base in declared else None})
            ranges+=1; decoded+=size
    observed.sort(key=lambda r:(r["instruction_rva"],r["target_rva"],r["operand_index"]))
    if observed!=refs or (ranges,decoded,count)!=(25490,3735718,1153814): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("whole-atlas reference partition differs")
    return expected
def _decoder_contract() -> dict[str,Any]: return {"name":"capstone","version":SUPPORTED_CAPSTONE_VERSION,"architecture":"x86","mode_bits":32,"sealed_instruction_count":51,"register_call_encoding_audit":[{"register":r,"encoding":f"ff{0xd0+i:02x}"} for i,r in enumerate(_REGISTER_NAMES)]}
def _layout(data: bytes|None,image: Any|None) -> dict[str,Any]:
    record={"role":"contiguous_atlas_layout_only","start_rva":"0x00378b3e","end_rva_exclusive":"0x00378b9e","size":96,"sha256":"90bbfc64c1432f6b635812d241f996137a7e02d88381c66e66955102f1f9d48d","member_entries":[_hex(x) for x in _ENTRIES],"adjacent_pairs":[{"left_entry_rva":_hex(a),"right_entry_rva":_hex(b),"left_end_rva_exclusive":_hex(a+_BODIES[a][0])} for a,b in zip(_ENTRIES,_ENTRIES[1:])],"semantic_kinship_claimed":False}
    if data is not None:
        start=image.rva_to_file_offset(0x378B3E); end=image.rva_to_file_offset(0x378B9E)
        if start is None or end is None or hashlib.sha256(data[start:end]).hexdigest()!=record["sha256"]: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("contiguous layout bytes differ")
    return record
_METHOD={"structural_boundary":"PE-free validation reconstructs the fixed prerequisite, layout-only span, four atlas body, CFG, declared-edge, opaque-control, opaque-operand, and whole-atlas reference receipts. Exact bytes and the atlas traversal require the sealed executable.","not_claimed":["semantic kinship based on adjacency, analysis labels, ABI, registers, compiler, exception, arguments, control transfer, behavior, success, or normal return","runtime reachability, invocation, order, frequency, target identity, state mutation, or runtime effect","contents or semantics of operands, indirect controls, registers, or pointed-to data","dynamic, computed, indirect, data, un-atlased, or Lua-side references"]}
def _summary(_: Mapping[str,Any]) -> dict[str,Any]: return {"reviewed_adjacent_callee_cluster_count":4,"reviewed_adjacent_callee_cluster_bytes":96,"sealed_instruction_count":51,"sealed_control_flow_graph_count":4,"sealed_control_flow_graph_node_count":51,"sealed_control_flow_graph_edge_count":47,"direct_lua_call_count":0,"staged_lua_dispatch_count":0,"call_r32_count":1,"indirect_jmp_count":1,"native_direct_edge_count":3,"opaque_instruction_syntax_count":3,"pe_address_operand_count":4,"noncontrol_pe_address_operand_count":1,"pointer_target_parent_edge_count":5,"target_reference_count":5,"target_reference_target_count":4,"target_reference_direct_call_count":5,"target_reference_comparison_count":0,"target_reference_other_address_count":0,"target_reference_memory_operand_count":0,"target_reference_owner_count":1,"schema_violations":0}
def build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary(executable: Path,pointer_target_static_boundary: Mapping[str,Any],direct_calls: Mapping[str,Any],program_facts: Mapping[str,Any],*,inventory: Mapping[str,Any]) -> dict[str,Any]:
    try:
        for value,label in ((pointer_target_static_boundary,"pointer target"),(direct_calls,"direct calls"),(program_facts,"facts"),(inventory,"inventory")): _validate_json_tree(value,label)
        receipt=validate_native_lua_direct_call_census(executable,direct_calls,program_facts,inventory=inventory)
        if receipt.get("status")!="verified" or receipt.get("evidence_sha256")!=_DIRECT: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("direct prerequisite differs")
        atlas,direct,pointer=_preflight(pointer_target_static_boundary,direct_calls,program_facts); data,image,digest=_load_executable(executable)
        if digest!=_EXE: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("executable differs")
        decoder,_=_decoder(); decoder.detail=True; import capstone,capstone.x86_const as x
        bodies=[]; graphs=[]
        for entry in _ENTRIES:
            size,body,_,cfg,nodes,edges=_BODIES[entry]; ins=_decode_range(data,image,entry,size,decoder)
            if len(ins)!=nodes or hashlib.sha256(b"".join(bytes(i.bytes) for i in ins)).hexdigest()!=body: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("body bytes differ")
            graph=_with_edi_writes(_enhanced_cfg(ins,image.image_base,(entry,size),capstone,x),ins,x); graph["caller_entry_rva"]=_hex(entry)
            if _canonical_sha256(graph)!=cfg or (graph.get("node_count"),graph.get("edge_count"))!=(nodes,edges): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("CFG differs")
            by={i.address-image.image_base:i for i in ins}; b=_body(entry,program_facts); b["reviewed_points"]=[_point_record(by[p["rva"]],image.image_base,p) for p in _points(entry)]; b["call_r32_audit"]=_call_r32_audit(ins,{"entry_rva":entry,"call_r32":{"ECX":[0x378B4E]} if entry==0x378B3E else {}}); bodies.append(b); graphs.append(graph)
        scan=_scan(data,image,decoder,program_facts)
        direct_lua=[call for row in _array(direct_calls.get("records"),"direct records") if _rva(_mapping(row,"record").get("entry_rva"),"entry") in _ENTRIES for call in _array(_mapping(row,"record").get("direct_lua_import_calls"),"calls")]
        if direct_lua: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("direct Lua partition differs")
        result={"schema_version":SCHEMA_VERSION,"analysis_kind":ANALYSIS_KIND,"build_identity":dict(_mapping(program_facts.get("identity"),"identity")),"atlas":atlas,"direct_call_census":direct,"pointer_target_static_boundary":pointer,"decoder":_decoder_contract(),"contiguous_layout":_layout(data,image),"function_bodies":bodies,"control_flow_graphs":graphs,"pointer_target_parent_edges":_parent_edges(pointer_target_static_boundary,program_facts),"native_calls":{"direct":_direct_records(program_facts),"opaque_instruction_syntax":_opaque_syntax(image,{entry:_decode_range(data,image,entry,_BODIES[entry][0],decoder) for entry in _ENTRIES})},"whole_atlas_reference_scan":scan,"method":_METHOD}; result["summary"]=_summary(result); _assert_publication_safe(result)
        if _load_executable(executable)[2]!=digest: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("executable changed")
        validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary_structure(result,pointer_target_static_boundary,direct_calls,program_facts); return result
    except NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError: raise
    except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassReturnHelperChainError,PEAnchorError,OSError) as exc: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError(str(exc)) from exc
def validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary_structure(evidence: Mapping[str,Any],pointer_target_static_boundary: Mapping[str,Any],direct_calls: Mapping[str,Any],program_facts: Mapping[str,Any]) -> dict[str,Any]:
    try:
        for value,label in ((evidence,"evidence"),(pointer_target_static_boundary,"pointer target"),(direct_calls,"direct calls"),(program_facts,"facts")): _validate_json_tree(value,label)
        receipt=validate_native_lua_direct_call_structure(direct_calls,program_facts)
        if receipt.get("status")!="structurally_verified" or receipt.get("evidence_sha256")!=_DIRECT: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("direct prerequisite differs")
        atlas,direct,pointer=_preflight(pointer_target_static_boundary,direct_calls,program_facts); evidence=_mapping(evidence,"evidence")
        _exact_keys(evidence,{"schema_version","analysis_kind","build_identity","atlas","direct_call_census","pointer_target_static_boundary","decoder","contiguous_layout","function_bodies","control_flow_graphs","pointer_target_parent_edges","native_calls","whole_atlas_reference_scan","method","summary"},"evidence")
        if type(evidence.get("schema_version")) is not int or evidence.get("schema_version")!=SCHEMA_VERSION or evidence.get("analysis_kind")!=ANALYSIS_KIND: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("schema differs")
        if not all((_same(evidence.get("build_identity"),dict(_mapping(program_facts.get("identity"),"identity"))),_same(evidence.get("atlas"),atlas),_same(evidence.get("direct_call_census"),direct),_same(evidence.get("pointer_target_static_boundary"),pointer),_same(evidence.get("decoder"),_decoder_contract()),_same(evidence.get("contiguous_layout"),_layout(None,None)),_same(evidence.get("method"),_METHOD))): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("pinned prerequisite differs")
        bodies=_array(evidence.get("function_bodies"),"bodies")
        if len(bodies)!=4 or any(not _same(bodies[i],_body(entry,program_facts)) for i,entry in enumerate(_ENTRIES)): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("body differs")
        graphs=_validated_graphs({"control_flow_graphs":evidence.get("control_flow_graphs")},_atlas_functions(program_facts))
        if set(graphs)!=set(_ENTRIES): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("CFG entries differ")
        for entry in _ENTRIES:
            graph=graphs[entry][0]; _,_,_,cfg,nodes,edges=_BODIES[entry]
            if _canonical_sha256(graph)!=cfg or (graph.get("node_count"),graph.get("edge_count"))!=(nodes,edges): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("CFG differs")
            point_nodes={_rva(n.get("rva"),"node") : n for n in _array(graph.get("nodes"),"nodes")}; body=next(b for b in bodies if _rva(_mapping(b,"body").get("entry_rva"),"entry")==entry)
            for point in _array(_mapping(body,"body").get("reviewed_points"),"points"):
                node=point_nodes.get(_rva(_mapping(point,"point").get("rva"),"point"))
                if node is None or (point.get("size"),point.get("sha256"))!=(node.get("size"),node.get("sha256")): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("point CFG join differs")
        reviewed={p.get("rva"):p for body in bodies for p in _array(_mapping(body,"body").get("reviewed_points"),"points")}
        for records in (_array(_mapping(evidence.get("native_calls"),"calls").get("direct"),"direct"),_array(_mapping(evidence.get("native_calls"),"calls").get("opaque_instruction_syntax"),"opaque")):
            for row in records:
                inst=_mapping(_mapping(row,"record").get("instruction"),"instruction"); point=reviewed.get(inst.get("rva"))
                if point is None or (point.get("size"),point.get("sha256"))!=(inst.get("size"),inst.get("sha256")): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("instruction body join differs")
        scan=_mapping(evidence.get("whole_atlas_reference_scan"),"scan")
        parent_edges=_array(evidence.get("pointer_target_parent_edges"),"parent edges"); references=_array(scan.get("references"),"scan references")
        if len(parent_edges)!=5 or len(references)!=5: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("parent scan cardinality differs")
        for parent,reference in zip(parent_edges,references):
            p=_mapping(parent,"parent edge"); r=_mapping(reference,"scan reference"); instruction=_mapping(p.get("instruction"),"parent instruction")
            if (instruction.get("rva"),instruction.get("size"),instruction.get("sha256"),p.get("source_entry_rva"),p.get("source_atlas_record_sha256"),p.get("target_entry_rva"),p.get("target_atlas_record_sha256"),p.get("ghidra_declared_direct_edge")) != (r.get("instruction_rva"),r.get("instruction_size"),r.get("instruction_sha256"),r.get("owner_entry_rva"),r.get("owner_atlas_record_sha256"),r.get("target_rva"),r.get("target_atlas_record_sha256"),r.get("ghidra_declared_direct_edge")): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("parent scan join differs")
        if not all((_same(evidence.get("pointer_target_parent_edges"),_parent_edges(pointer_target_static_boundary,program_facts)),_same(evidence.get("native_calls"),{"direct":_direct_records(program_facts),"opaque_instruction_syntax":_opaque_syntax(None)}),_same(scan,_scan(None,None,None,program_facts)),_same(evidence.get("summary"),_summary(evidence)))): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("cross-check differs")
        _assert_publication_safe(evidence); return {"schema_version":SCHEMA_VERSION,"analysis_kind":STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","build_identity":dict(evidence["build_identity"]),"evidence_sha256":_canonical_sha256(evidence),"summary":dict(evidence["summary"])}
    except NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError: raise
    except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassReturnHelperChainError,NativeLuaClassFactoryChainError) as exc: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError(str(exc)) from exc
def validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary(executable: Path,evidence: Mapping[str,Any],pointer_target_static_boundary: Mapping[str,Any],direct_calls: Mapping[str,Any],program_facts: Mapping[str,Any],*,inventory: Mapping[str,Any]) -> dict[str,Any]:
    rebuilt=build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary(executable,pointer_target_static_boundary,direct_calls,program_facts,inventory=inventory)
    if not _same(evidence,rebuilt): raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError("evidence differs from exact rebuild")
    return {"schema_version":SCHEMA_VERSION,"analysis_kind":VERIFICATION_KIND,"status":"verified","build_identity":dict(rebuilt["build_identity"]),"evidence_sha256":_canonical_sha256(rebuilt),"summary":dict(rebuilt["summary"])}
def encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary(value: Mapping[str,Any]) -> str:
    try: _validate_json_tree(value); return json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2,sort_keys=True)+"\n"
    except NativeLuaCClosurePublicationError as exc: raise NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError(str(exc)) from exc
