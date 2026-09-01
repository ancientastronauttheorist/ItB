"""Opaque relationship-only static boundary for RVA ``0x00370dab``.

Analysis and import names are retained only as metadata.  This receipt makes
no ABI, exception, runtime-reachability, imported-function-execution, or
normal-return claim.
"""
from __future__ import annotations

import hashlib
import json
import struct
from collections import Counter
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
from src.observatory.native_operator_new_second_callee_static_boundary import ANALYSIS_KIND as PREDECESSOR_KIND
from src.observatory.native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary import ANALYSIS_KIND as SEALED_TARGETS_KIND
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_operator_new_second_callee_second_callee_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"

_EXE = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_PREDECESSOR = "ebc3514d67711d7774e51eecd4c881f9826ed6ec68f40ca462415e654ba7d856"
_SEALED_TARGETS = "0783fffcd973eca3937ce01faa4d4f93b974540cfdaf004a301ce7ef0198fd5d"
_BASE, _ENTRY, _SIZE = 0x400000, 0x370DAB, 110
_RAW = "558bec83ec20538b5d0856576a0859be0c287f008d7de0f3a58b7d0c85ff741cf6071074178b0b83e904518b018b70208bce8b7818e8ce73feffffd6895df8897dfc85ff740cf607087407c745f4004099018d45f450ff75f0ff75e4ff75e0ff156c617d005f5e5b8be55dc20800"
_BODY = "896ec8b098391d89781713fa087cc8a9c6ac934baf88b56cb8ebbb0431c48e68"
_ATLAS = "577983a75685f308e9989992bec7e1231b8155375179f3463376e2744816f9e0"
_CFG = "038ec878b177ec4f42bcaa09b401ff95eb0fc61867e9c26d6b424c2448b3a260"
_PARENT = (0x3584A6, 0x35848F, "e800890100", "1db39b499d8261ff48c0bdaac1a9e538601fa4f94cdb25f4b53882e01d325526")
_CHILD = (0x370DE0, "e8ce73feff", 0x3581B3, 6, "830f019638817ae10a1187ae4c3e39e8c131975cd1b098f357c6b74bb026cfd9", "5800bbedd2bf56defb8512ec1185966e6d6b4b21adee1d7df3147106559fccf5", "bfc11525c53b449009167bf3f1962df65c7c691d882eaa63af4e92e0d11400a9")
_SCOPE = {"atlas_function_count":25312,"atlas_body_range_count":25490,"decoded_bytes":3735718,"decoded_instructions":1153814,"all_declared_ranges_decoded":True,"operand_classes":["absolute_memory","immediate"]}
_PARTITION_HASHES = {"owner_partition":"90e97d475f3472a0abfc41721b23461292172410f59d5580df3ebf8a8e6c59bb","target_partition":"98e317a6bde622f8e5e6e54461717d7040cbc2408335fbfc8ed065f8db16f8ad","target_owner_partition":"f83c88a495872c8f7c9e12f2bfef155b0a15a5fcb836b940d54882148b4630c4","target_reference_partition":"d0b16b5205042378e0a88ca1eee131180dbdb146e95cd7fbfe718017e158b3c7"}
_REFERENCE_HASH = "473efb87d20b7095e5cbfb2a0e44b2fad0ab72c143b69fe371627f361be6f133"
_IAT_REFERENCE_HASH = "c6700c1297e29267d694dab39a809ac85213c46426325a3df8f9e1b046fd840f"
_IAT_OWNER_HASH = "59525e3c380864e0f1b0ee9ebcb29b31ad5f3c5d2e51bd695b47026a0f323b74"

class NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError(RuntimeError):
    pass

def _bad(message: str) -> None: raise NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError(message)
def _same(a: Any,b: Any)->bool: return _canonical_bytes(a)==_canonical_bytes(b)
def _compact(v: Any)->str: return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def _instruction(rva:int,encoded:str)->dict[str,Any]:
    raw=bytes.fromhex(encoded);return {"rva":_hex(rva),"size":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
def _empty_register_calls()->list[dict[str,Any]]: return [{"register":r,"call_rvas":[]} for r in _REGISTER_NAMES]

def _edges(facts:Mapping[str,Any])->dict[int,Mapping[str,Any]]:
    result={}
    for raw in _array(facts.get("ghidra_declared_direct_calls"),"declared calls"):
        edge=_mapping(raw,"declared edge");site=_rva(edge.get("instruction_rva"),"edge site")
        if site in result:_bad("duplicate declared direct-call site")
        result[site]=edge
    return result

def _normalized_edge(edge:Mapping[str,Any])->dict[str,Any]:
    name=edge.get("target_name")
    if type(name) is not str:_bad("declared edge lacks analysis label")
    return {"instruction_rva":_hex(_rva(edge.get("instruction_rva"),"site")),"source_entry_rva":_hex(_rva(edge.get("source_entry_rva"),"source")),"target_entry_rva":_hex(_rva(edge.get("target_entry_rva"),"target entry")),"target_rva":_hex(_rva(edge.get("target_rva"),"target")),"target_name_sha256":hashlib.sha256(name.encode()).hexdigest()}

def _decode(raw:bytes=bytes.fromhex(_RAW))->list[Any]:
    decoder,_=_decoder();decoder.detail=True;rows=list(decoder.disasm(raw,_BASE+_ENTRY))
    if len(rows)!=45 or b"".join(bytes(x.bytes) for x in rows)!=raw:_bad("sealed target bytes do not decode exactly")
    return rows

def _points(rows:list[Any])->list[dict[str,Any]]:
    result=[]
    for x in rows:
        _,writes=x.regs_access();names={x.reg_name(r).lower() for r in writes};raw=bytes(x.bytes)
        result.append({"rva":_hex(x.address-_BASE),"size":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"writes_ebx":"ebx" in names,"writes_esi":"esi" in names,"writes_edi":"edi" in names,"writes_esp":"esp" in names})
    return result

def _graph(rows:list[Any]|None=None)->dict[str,Any]:
    import capstone,capstone.x86_const as x86
    decoded=_decode() if rows is None else rows
    graph=_with_edi_writes(_enhanced_cfg(decoded,_BASE,(_ENTRY,_SIZE),capstone,x86),decoded,x86);graph["caller_entry_rva"]=_hex(_ENTRY)
    if (graph.get("node_count"),graph.get("edge_count"),_canonical_sha256(graph))!=(45,48,_CFG):_bad("sealed CFG differs")
    return graph

def _preflight(predecessor:Mapping[str,Any],sealed:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any])->dict[str,Any]:
    identity=dict(_mapping(facts.get("identity"),"facts identity"))
    if identity.get("executable_sha256")!=_EXE:_bad("program facts executable differs")
    for value,label in ((predecessor,"predecessor"),(sealed,"sealed targets"),(direct,"direct calls")):
        if not _same(value.get("build_identity"),identity):_bad(label+" build identity differs")
    if predecessor.get("analysis_kind")!=PREDECESSOR_KIND or _canonical_sha256(predecessor)!=_PREDECESSOR:_bad("predecessor canonical differs")
    if sealed.get("analysis_kind")!=SEALED_TARGETS_KIND or _canonical_sha256(sealed)!=_SEALED_TARGETS:_bad("sealed-target receipt differs")
    summary=_mapping(facts.get("summary"),"facts summary")
    return {"program_facts":{**_source_identity(facts,"pe_ghidra_program_facts",_FACTS,"program facts"),"function_count":summary.get("function_count"),"body_range_count":summary.get("body_range_count"),"function_body_bytes":summary.get("function_body_bytes")},"predecessor_static_boundary":_source_identity(predecessor,PREDECESSOR_KIND,_PREDECESSOR,"predecessor"),"sealed_direct_target_set":_source_identity(sealed,SEALED_TARGETS_KIND,_SEALED_TARGETS,"sealed targets"),"direct_call_census":_source_identity(direct,DIRECT_KIND,_DIRECT,"direct calls")}

def _target_function(facts:Mapping[str,Any])->Mapping[str,Any]:
    f=_atlas_functions(facts).get(_ENTRY)
    if f is None or (f.get("body_size"),f.get("body_sha256"),atlas_record_sha256(f))!=(_SIZE,_BODY,_ATLAS):_bad("target atlas record differs")
    return f

def _parent_edge(predecessor:Mapping[str,Any])->list[dict[str,Any]]:
    rows=[dict(_mapping(x,"parent edge")) for x in _array(_mapping(predecessor.get("native_calls"),"parent calls").get("outgoing_direct"),"parent edges")]
    found=[x for x in rows if _rva(_mapping(x.get("instruction"),"instruction").get("rva"),"site")==_PARENT[0] and _rva(x.get("source_entry_rva"),"source")==_PARENT[1] and _rva(x.get("target_entry_rva"),"target")==_ENTRY]
    if len(rows)!=2 or len(found)!=1 or found[0].get("control_encoding")!="e8" or not _same(found[0]["instruction"],_instruction(_PARENT[0],_PARENT[2])):_bad("parent edge differs")
    return found

def _sealed_child(sealed:Mapping[str,Any])->dict[str,Any]:
    bodies=[_mapping(x,"sealed body") for x in _array(sealed.get("function_bodies"),"sealed bodies") if _rva(_mapping(x,"sealed body").get("entry_rva"),"entry")==_CHILD[2]]
    if len(bodies)!=1:_bad("sealed outgoing target body missing")
    body=bodies[0]
    if (body.get("body_size"),body.get("body_sha256"),body.get("atlas_record_sha256"),body.get("control_flow_graph_canonical_sha256"))!=(_CHILD[3],_CHILD[4],_CHILD[5],_CHILD[6]):_bad("sealed outgoing target identity differs")
    return {"receipt_analysis_kind":SEALED_TARGETS_KIND,"receipt_canonical_sha256":_SEALED_TARGETS,"entry_rva":_hex(_CHILD[2]),"body_size":_CHILD[3],"body_sha256":_CHILD[4],"atlas_record_sha256":_CHILD[5],"control_flow_graph_canonical_sha256":_CHILD[6],"analysis_labels_opaque":True}

_PE_OPERANDS=(
 (0x370DBA,"be0c287f00","immediate",1,"none",0x7F280C,0x3F280C,"x86_mov_imm32",".rdata",0x3D6000,0x40000040,0x3F180C),
 (0x370DC9,"741c","immediate",0,"none",0x770DE7,0x370DE7,"direct_conditional_branch_target",".text",0x1000,0x60000020,0x3701E7),
 (0x370DCE,"7417","immediate",0,"none",0x770DE7,0x370DE7,"direct_conditional_branch_target",".text",0x1000,0x60000020,0x3701E7),
 (0x370DE0,"e8ce73feff","immediate",0,"none",0x7581B3,0x3581B3,"x86_relative_near_call_e8",".text",0x1000,0x60000020,0x3575B3),
 (0x370DEF,"740c","immediate",0,"none",0x770DFD,0x370DFD,"direct_conditional_branch_target",".text",0x1000,0x60000020,0x3701FD),
 (0x370DF4,"7407","immediate",0,"none",0x770DFD,0x370DFD,"direct_conditional_branch_target",".text",0x1000,0x60000020,0x3701FD),
 (0x370E0A,"ff156c617d00","absolute_memory",0,"read",0x7D616C,0x3D616C,"x86_absolute_memory_indirect_call_ff15",".rdata",0x3D6000,0x40000040,0x3D516C),)
_NON_PE=((0x370DAE,1,0x20),(0x370DB7,0,8),(0x370DCB,1,0x10),(0x370DD2,1,4),(0x370DF1,1,8),(0x370DF6,1,0x01994000),(0x370E16,0,8))

def _raw_import_binding(image:Any|None=None)->dict[str,Any]:
    result={"pe_bits":32,"import_directory_rva":"0x0048eca4","import_directory_size":220,"import_directory_file_offset":"0x0048dca4","import_directory_sha256":"788f7357cb31ba62895740d67e0d8a0f6bf962c467ec801a29cf9044d522fd65","descriptor_count":10,"import_record_count":342,"named_import_count":342,"ordinal_import_count":0,"kernel32_import_count":139,"matching_name_count":1,"matching_iat_slot_count":1,"descriptor_index":7,"descriptor_rva":"0x0048ed30","descriptor_file_offset":"0x0048dd30","descriptor_size":20,"descriptor_sha256":"fe01ec3285fd8be5c0857ae597b2ac4a14de3579860f5f3577a6bdbe8595bc10","original_first_thunk_rva":"0x0048ed80","timestamp":0,"forwarder_chain":0,"first_thunk_rva":"0x003d6000","library_name_rva":"0x004905fe","library_name_file_offset":"0x0048f5fe","library_nul_terminated_size":13,"library_nul_terminated_sha256":"f8efc1f27ef6c525f7fd20dcb8d65e8197e97410eced20db4d323dfbf230a2a4","thunk_index":91,"lookup_thunk_rva":"0x0048eeec","lookup_thunk_file_offset":"0x0048deec","lookup_thunk_raw_value":"0x00490d1e","lookup_thunk_sha256":"939c7bbe49ef043f3914c2b3fa471173f3eb97c203ab4fa6622ce4c452f2f391","iat_slot_rva":"0x003d616c","iat_slot_file_offset":"0x003d516c","iat_slot_raw_value":"0x00490d1e","iat_slot_sha256":"939c7bbe49ef043f3914c2b3fa471173f3eb97c203ab4fa6622ce4c452f2f391","import_by_name_rva":"0x00490d1e","import_by_name_file_offset":"0x0048fd1e","hint_and_name_nul_terminated_size":17,"hint_and_name_nul_terminated_sha256":"511ead1e92f6be475c1a601468e4fe2fe075bd288c1dd827bb0ae02a3e43d1ed","hint":945,"library":"KERNEL32.dll","name":"RaiseException","metadata_only":True}
    if image is None:return result
    if image.bits!=32 or len(image.data_directories)<=1 or image.data_directories[1]!=(0x48ECA4,220):_bad("raw import directory differs")
    def span(rva:int,size:int,offset:int,digest:str)->bytes:
        actual=image.rva_span_to_file_offset(rva,size)
        if actual!=offset:_bad("raw import span differs")
        raw=image.data[actual:actual+size]
        if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=digest:_bad("raw import bytes differ")
        return raw
    directory=span(0x48ECA4,220,0x48DCA4,result["import_directory_sha256"])
    descriptors=[struct.unpack_from("<IIIII",directory,i*20) for i in range(11)]
    if any(not any(x) for x in descriptors[:10]) or any(descriptors[10]):_bad("raw import descriptor partition differs")
    descriptor=span(0x48ED30,20,0x48DD30,result["descriptor_sha256"])
    original_first_thunk,timestamp,forwarder_chain,library_name_rva,first_thunk=struct.unpack("<IIIII",descriptor)
    if (original_first_thunk,timestamp,forwarder_chain,library_name_rva,first_thunk)!=(0x48ED80,0,0,0x4905FE,0x3D6000):_bad("raw import descriptor differs")
    thunk_index=result["thunk_index"]
    if original_first_thunk+thunk_index*4!=0x48EEEC or first_thunk+thunk_index*4!=0x3D616C:_bad("raw import thunk arithmetic differs")
    if span(0x4905FE,13,0x48F5FE,result["library_nul_terminated_sha256"])!=b"KERNEL32.dll\0":_bad("raw import library differs")
    lookup=span(0x48EEEC,4,0x48DEEC,result["lookup_thunk_sha256"]);iat=span(0x3D616C,4,0x3D516C,result["iat_slot_sha256"])
    if lookup!=iat or struct.unpack("<I",lookup)!=(0x490D1E,):_bad("raw ILT/IAT differs")
    zero_sha256="df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119"
    if span(original_first_thunk+139*4,4,0x48DFAC,zero_sha256)!=b"\0"*4 or span(first_thunk+139*4,4,0x3D522C,zero_sha256)!=b"\0"*4:_bad("raw ILT/IAT terminator differs")
    hintname=span(0x490D1E,17,0x48FD1E,result["hint_and_name_nul_terminated_sha256"])
    if struct.unpack("<H",hintname[:2])!=(945,) or hintname[2:]!=b"RaiseException\0":_bad("raw import name differs")
    imports=image.imports();byname=[x for x in imports if x.get("name")=="RaiseException"];byslot=[x for x in imports if x.get("iat_rva")=="0x003d616c"]
    expected={"library":"KERNEL32.dll","name":"RaiseException","ordinal":None,"hint":945,"iat_rva":"0x003d616c"}
    if len(imports)!=342 or sum(x.get("name") is not None for x in imports)!=342 or sum(x.get("ordinal") is not None for x in imports)!=0 or sum(x.get("library")=="KERNEL32.dll" for x in imports)!=139 or len(byname)!=1 or len(byslot)!=1 or byname!=byslot or any(byname[0].get(key)!=value for key,value in expected.items()):_bad("parsed import metadata differs")
    return result

def _native_calls(facts:Mapping[str,Any],sealed:Mapping[str,Any],image:Any|None=None)->dict[str,Any]:
    functions,edges=_atlas_functions(facts),_edges(facts);_target_function(facts)
    source={s for s,e in edges.items() if _rva(e.get("source_entry_rva"),"source")==_ENTRY}
    if source!={_CHILD[0]}:_bad("outgoing direct partition differs")
    edge=edges[_CHILD[0]];target=functions.get(_CHILD[2])
    if target is None or (_rva(edge.get("target_entry_rva"),"target"),_rva(edge.get("target_rva"),"target"))!=(_CHILD[2],_CHILD[2]) or (target.get("body_size"),target.get("body_sha256"),atlas_record_sha256(target))!=(_CHILD[3],_CHILD[4],_CHILD[5]):_bad("outgoing direct edge differs")
    direct={"role":"opaque_native_direct_edge","source_entry_rva":_hex(_ENTRY),"source_atlas_record_sha256":_ATLAS,"source_body_size":_SIZE,"source_body_sha256":_BODY,"instruction":_instruction(_CHILD[0],_CHILD[1]),"target_entry_rva":_hex(_CHILD[2]),"target_rva":_hex(_CHILD[2]),"target_atlas_record_sha256":_CHILD[5],"target_body_size":_CHILD[3],"target_body_sha256":_CHILD[4],"ghidra_declared_direct_edge":_normalized_edge(edge),"control_encoding":"e8","callee_behavior_opaque":True,"sealed_target_join":_sealed_child(sealed)}
    operands=[]
    for site,encoded,kind,index,access,va,rva,syntax,name,srva,chars,offset in _PE_OPERANDS:
        operands.append({"role":"opaque_pe_address_operand","instruction":_instruction(site,encoded),"operand_class":kind,"operand_index":index,"operand_access":access,"operand_va":_hex(va),"operand_rva":_hex(rva),"control_syntax":syntax,"section_name":name,"section_rva":_hex(srva),"section_characteristics":_hex(chars),"section_writable":False,"file_backed":True,"file_offset":_hex(offset),"contents_or_runtime_behavior_opaque":True})
        if image is not None:
            section=next((x for x in image.sections if x.virtual_address<=rva<x.virtual_address+x.virtual_size),None)
            if section is None or (section.name,section.virtual_address,section.characteristics,image.rva_to_file_offset(rva))!=(name,srva,chars,offset):_bad("PE operand binding differs")
    indirect=[{"role":"opaque_native_indirect_call_syntax","instruction":_instruction(0x370DE5,"ffd6"),"call_form":"x86_register_call_r32","operand_kind":"register","operand":"ESI","target_resolved":False,"callee_behavior_opaque":True},{"role":"opaque_native_indirect_call_syntax","instruction":_instruction(0x370E0A,"ff156c617d00"),"call_form":"x86_absolute_memory_indirect_call_ff15","operand_kind":"absolute_memory","operand_va":"0x007d616c","operand_rva":"0x003d616c","section_name":".rdata","section_characteristics":"0x40000040","section_writable":False,"target_resolved":False,"callee_behavior_opaque":True,"raw_import_table_binding":_raw_import_binding(image)}]
    return {"outgoing_direct":[direct],"outgoing_direct_partition_complete":True,"direct_lua_calls":[],"direct_lua_partition_complete":True,"staged_lua_dispatches":[],"staged_lua_partition_complete":True,"opaque_indirect_controls":indirect,"indirect_control_partition_complete":True,"pe_address_operands":operands,"pe_address_operand_partition_complete":True,"non_pe_immediate_literals":[{"instruction_rva":_hex(r),"operand_index":i,"value":_hex(v)} for r,i,v in _NON_PE],"non_pe_immediate_literal_partition_complete":True,"segment_qualified_memory_syntax":[{"role":"opaque_segment_qualified_memory_syntax","instruction":_instruction(0x370DC2,"f3a5"),"operand_index":0,"operand_access":"write","segment_register":"ES","base_register":"EDI","repeat_prefix":"F3","runtime_behavior_opaque":True}],"segment_qualified_memory_partition_complete":True,"bnd_prefixed_control_syntax":[],"bnd_prefixed_control_partition_complete":True,"opaque_interrupt_syntax":[],"opaque_interrupt_partition_complete":True,"call_r32_audit":[{"register":r,"call_rvas":["0x00370de5"] if r=="ESI" else []} for r in _REGISTER_NAMES],"register_call_partition_complete":True}

def _expected_scan(facts:Mapping[str,Any])->dict[str,Any]:
    functions,edges=_atlas_functions(facts),_edges(facts);target=_target_function(facts);references=[]
    for site,edge in sorted(edges.items()):
        if _rva(edge.get("target_entry_rva"),"target entry")!=_ENTRY or _rva(edge.get("target_rva"),"target")!=_ENTRY:continue
        owner=_rva(edge.get("source_entry_rva"),"owner");f=functions.get(owner)
        if f is None:_bad("incoming owner missing")
        raw=b"\xe8"+int(_ENTRY-(site+5)).to_bytes(4,"little",signed=True)
        references.append({"instruction_rva":_hex(site),"instruction_size":5,"instruction_sha256":hashlib.sha256(raw).hexdigest(),"owner_entry_rva":_hex(owner),"owner_atlas_record_sha256":atlas_record_sha256(f),"target_rva":_hex(_ENTRY),"target_atlas_record_sha256":_ATLAS,"target_va":_hex(_BASE+_ENTRY),"operand_class":"immediate","operand_index":0,"use_class":"direct_call","call_form":"x86_relative_near_call_e8","ghidra_declared_direct_edge":_normalized_edge(edge)})
    counts=Counter(x["owner_entry_rva"] for x in references)
    owners=[{"owner_entry_rva":owner,"owner_atlas_record_sha256":atlas_record_sha256(functions[int(owner,16)]),"reference_count":counts[owner]} for owner in sorted(counts,key=lambda x:int(x,16))]
    target_partition=[{"target_rva":_hex(_ENTRY),"target_atlas_record_sha256":_ATLAS,"reference_count":len(references),"owner_count":len(owners)}]
    target_owner=[{"target_rva":_hex(_ENTRY),**x} for x in owners];target_refs=[{"target_rva":_hex(_ENTRY),"target_atlas_record_sha256":_ATLAS,"reference_count":len(references)}]
    hashes={"owner_partition":_compact(owners),"target_partition":_compact(target_partition),"target_owner_partition":_compact(target_owner),"target_reference_partition":_compact(target_refs)}
    if (len(references),len(owners),hashes,_compact(references))!=(481,414,_PARTITION_HASHES,_REFERENCE_HASH):_bad("incoming reference partition differs")
    return {"target_rvas":[_hex(_ENTRY)],"target_vas":[_hex(_BASE+_ENTRY)],"scope":dict(_SCOPE),"references":references,"target_partition":target_partition,"owner_partition":owners,"target_owner_partition":target_owner,"target_reference_partition":target_refs,"partition_sha256":hashes,"references_canonical_sha256":_REFERENCE_HASH,"aggregates":{"reference_count":481,"target_count":1,"owner_count":414,"target_owner_count":414,"direct_call_count":481,"comparison_count":0,"other_address_count":0,"memory_operand_count":0}}

def _whole_atlas_reference_scan(data:bytes,image:Any,decoder:Any,facts:Mapping[str,Any])->dict[str,Any]:
    import capstone.x86_const as x86
    found=[];totals=[0,0,0];decoder.detail=True;target=image.image_base+_ENTRY
    for owner,f in sorted(_atlas_functions(facts).items()):
        for raw in _array(f.get("ranges"),"ranges"):
            span=_mapping(raw,"range");start,size=_rva(span.get("start_rva"),"start"),span.get("size")
            if type(size) is not int or size<=0:_bad("invalid atlas range")
            rows=_decode_range(data,image,start,size,decoder);totals[0]+=1;totals[1]+=size;totals[2]+=len(rows)
            for ins in rows:
                for index,op in enumerate(ins.operands):
                    kind=value=None
                    if op.type==x86.X86_OP_IMM:kind,value="immediate",int(op.imm)&0xffffffff
                    elif op.type==x86.X86_OP_MEM and op.mem.segment==x86.X86_REG_INVALID and op.mem.base==x86.X86_REG_INVALID and op.mem.index==x86.X86_REG_INVALID:kind,value="absolute_memory",int(op.mem.disp)&0xffffffff
                    if value==target:found.append((ins.address-image.image_base,owner,index,bytes(ins.bytes),kind))
    expected=[(int(x["instruction_rva"],16),int(x["owner_entry_rva"],16),0,b"\xe8"+int(_ENTRY-(int(x["instruction_rva"],16)+5)).to_bytes(4,"little",signed=True),"immediate") for x in _expected_scan(facts)["references"]]
    if tuple(totals)!=(25490,3735718,1153814) or found!=expected:_bad("all-operand target reference traversal differs")
    return _expected_scan(facts)

def _expected_iat_scan(facts:Mapping[str,Any])->dict[str,Any]:
    functions=_atlas_functions(facts);spec=((0x370E0A,0x370DAB),(0x3922D2,0x3920A5),(0x39D2D1,0x39D204));refs=[]
    for site,owner in spec:
        refs.append({"instruction_rva":_hex(site),"instruction_size":6,"instruction_sha256":hashlib.sha256(bytes.fromhex("ff156c617d00")).hexdigest(),"owner_entry_rva":_hex(owner),"owner_atlas_record_sha256":atlas_record_sha256(functions[owner]),"operand_class":"absolute_memory","operand_index":0,"operand_access":"read","operand_va":"0x007d616c","operand_rva":"0x003d616c","control_syntax":"x86_absolute_memory_indirect_call_ff15"})
    owners=[{"owner_entry_rva":x["owner_entry_rva"],"owner_atlas_record_sha256":x["owner_atlas_record_sha256"],"reference_count":1} for x in refs]
    if _compact(refs)!=_IAT_REFERENCE_HASH or _compact(owners)!=_IAT_OWNER_HASH:_bad("IAT use hashes differ")
    return {"scope":dict(_SCOPE),"scanned_operand_va":"0x007d616c","scanned_operand_rva":"0x003d616c","references":refs,"owner_partition":owners,"references_canonical_sha256":_IAT_REFERENCE_HASH,"owner_partition_canonical_sha256":_IAT_OWNER_HASH,"aggregates":{"reference_count":3,"owner_count":3,"absolute_memory_operand_count":3,"indirect_call_count":3}}

def _iat_slot_use_scan(data:bytes|None,image:Any|None,decoder:Any|None,facts:Mapping[str,Any])->dict[str,Any]:
    result=_expected_iat_scan(facts)
    if data is None:return result
    import capstone.x86_const as x86
    found=[];totals=[0,0,0];assert image is not None and decoder is not None;decoder.detail=True
    for owner,f in sorted(_atlas_functions(facts).items()):
        for raw in _array(f.get("ranges"),"ranges"):
            span=_mapping(raw,"range");start,size=_rva(span.get("start_rva"),"start"),span.get("size");rows=_decode_range(data,image,start,size,decoder);totals[0]+=1;totals[1]+=size;totals[2]+=len(rows)
            for ins in rows:
                for index,op in enumerate(ins.operands):
                    if op.type==x86.X86_OP_IMM:value,kind=int(op.imm)&0xffffffff,"immediate"
                    elif op.type==x86.X86_OP_MEM and op.mem.segment==x86.X86_REG_INVALID and op.mem.base==x86.X86_REG_INVALID and op.mem.index==x86.X86_REG_INVALID:value,kind=int(op.mem.disp)&0xffffffff,"absolute_memory"
                    else:continue
                    if value==0x7D616C:found.append((ins.address-image.image_base,owner,index,bytes(ins.bytes),op.access,kind))
    expected=[(int(x["instruction_rva"],16),int(x["owner_entry_rva"],16),0,bytes.fromhex("ff156c617d00"),1,"absolute_memory") for x in result["references"]]
    if tuple(totals)!=(25490,3735718,1153814) or found!=expected:_bad("exhaustive IAT-slot use scan differs")
    return result

def _evidence(predecessor:Mapping[str,Any],sealed:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any],*,rows:list[Any]|None=None,image:Any|None=None,scan:Mapping[str,Any]|None=None,iat:Mapping[str,Any]|None=None)->dict[str,Any]:
    req=_preflight(predecessor,sealed,direct,facts);decoded=_decode() if rows is None else rows;raw=b"".join(bytes(x.bytes) for x in decoded);_target_function(facts)
    if raw!=bytes.fromhex(_RAW) or hashlib.sha256(raw).hexdigest()!=_BODY:_bad("target body differs")
    target_scan=_expected_scan(facts) if scan is None else dict(scan);iat_scan=_expected_iat_scan(facts) if iat is None else dict(iat)
    if not _same(target_scan,_expected_scan(facts)) or not _same(iat_scan,_expected_iat_scan(facts)):_bad("finite scan receipt differs")
    parent=_parent_edge(predecessor)
    if not any(x["instruction_rva"]==parent[0]["instruction"]["rva"] for x in target_scan["references"]):_bad("parent edge does not join incoming scan")
    calls=_native_calls(facts,sealed,image)
    result={"schema_version":SCHEMA_VERSION,"analysis_kind":ANALYSIS_KIND,"build_identity":dict(_mapping(facts.get("identity"),"identity")),**req,"decoder":{"name":"capstone","version":SUPPORTED_CAPSTONE_VERSION,"architecture":"x86","mode_bits":32,"sealed_instruction_count":45,"register_call_encoding_audit":[{"register":r,"encoding":f"ff{0xd0+i:02x}"} for i,r in enumerate(_REGISTER_NAMES)]},"function_body":{"role":"relationship_defined_operator_new_second_callee_second_callee_static_boundary","entry_rva":_hex(_ENTRY),"atlas_record_sha256":_ATLAS,"body_size":_SIZE,"body_sha256":_BODY,"range_start_rva":_hex(_ENTRY),"range_size":_SIZE,"control_flow_graph_canonical_sha256":_CFG,"reviewed_points":_points(decoded),"direct_lua_calls":[],"staged_lua_dispatches":[],"call_r32_audit":calls["call_r32_audit"],"register_call_partition_complete":True,"ghidra_analysis_metadata":{"name":"__CxxThrowException@8","namespace":"Global","name_source":"ANALYSIS","thunk":False,"metadata_only":True},"semantic_facts":{"relationship_defined_only":True,"analysis_labels_opaque":True,"source_semantic_names_assigned":False,"runtime_or_success_claimed":False}},"control_flow_graph":_graph(decoded),"predecessor_parent_edges":parent,"native_calls":calls,"whole_atlas_reference_scan":target_scan,"whole_atlas_iat_slot_use_scan":iat_scan,"method":{"structural_boundary":"The receipt seals 110 decoded bytes, finite direct and indirect control syntax, seven PE-address operands, seven non-PE immediates, one segment-qualified syntax, raw PE import metadata, the predecessor and already-sealed direct-target joins, and two exhaustive atlas traversals.","not_claimed":["analysis or import label meaning, source identity, ABI, inputs, outputs, exception or throw behavior, success, failure, or normal return","runtime reachability, invocation, ordering, frequency, state mutation, imported-function execution, or effects","identity or behavior of the ESI target, or contents and runtime meaning of PE-address operands and IAT slots","computed, dynamic, data, un-atlased, or Lua-side references"]},"summary":{"reviewed_target_count":1,"reviewed_target_bytes":110,"sealed_instruction_count":45,"sealed_control_flow_graph_count":1,"sealed_control_flow_graph_node_count":45,"sealed_control_flow_graph_edge_count":48,"native_direct_edge_count":1,"sealed_direct_target_join_count":1,"direct_lua_call_count":0,"staged_lua_dispatch_count":0,"call_r32_count":1,"opaque_indirect_control_count":2,"pe_address_operand_count":7,"pe_immediate_operand_count":6,"pe_absolute_memory_operand_count":1,"non_pe_immediate_literal_count":7,"segment_qualified_memory_syntax_count":1,"bnd_prefixed_control_syntax_count":0,"opaque_interrupt_syntax_count":0,"pe_import_metadata_count":1,"predecessor_parent_edge_count":1,"target_reference_count":481,"target_reference_target_count":1,"target_reference_owner_count":414,"target_reference_direct_call_count":481,"target_reference_other_address_count":0,"target_reference_memory_operand_count":0,"iat_slot_use_reference_count":3,"iat_slot_use_owner_count":3,"schema_violations":0}}
    return result

def _normalize(operation):
    try:return operation()
    except NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError:raise
    except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassReturnHelperChainError,PEAnchorError,CsError,struct.error,OSError,TypeError,ValueError,KeyError,IndexError) as exc:raise NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError(str(exc)) from exc

def validate_native_operator_new_second_callee_second_callee_static_boundary_structure(evidence:Mapping[str,Any],predecessor:Mapping[str,Any],sealed_targets:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any])->dict[str,Any]:
    def run():
        for v,label in ((evidence,"evidence"),(predecessor,"predecessor"),(sealed_targets,"sealed targets"),(direct,"direct"),(facts,"facts")):_validate_json_tree(v,label)
        receipt=validate_native_lua_direct_call_structure(direct,facts)
        if receipt.get("status")!="structurally_verified" or receipt.get("evidence_sha256")!=_DIRECT:_bad("direct-call structural prerequisite differs")
        expected=_evidence(predecessor,sealed_targets,direct,facts)
        if not _same(evidence,expected):_bad("structure receipt differs")
        _assert_publication_safe(evidence)
        return {"schema_version":SCHEMA_VERSION,"analysis_kind":STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","build_identity":dict(evidence["build_identity"]),"evidence_sha256":_canonical_sha256(evidence),"summary":dict(evidence["summary"])}
    return _normalize(run)

def build_native_operator_new_second_callee_second_callee_static_boundary(executable:Path,predecessor:Mapping[str,Any],sealed_targets:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any],*,inventory:Mapping[str,Any])->dict[str,Any]:
    def run():
        for v,label in ((predecessor,"predecessor"),(sealed_targets,"sealed targets"),(direct,"direct"),(facts,"facts"),(inventory,"inventory")):_validate_json_tree(v,label)
        receipt=validate_native_lua_direct_call_census(executable,direct,facts,inventory=inventory)
        if receipt.get("status")!="verified" or receipt.get("evidence_sha256")!=_DIRECT:_bad("direct-call exact prerequisite differs")
        data,image,digest=_load_executable(executable)
        if digest!=_EXE or image.image_base!=_BASE:_bad("exact executable differs")
        decoder,_=_decoder();decoder.detail=True;rows=_decode_range(data,image,_ENTRY,_SIZE,decoder);scan=_whole_atlas_reference_scan(data,image,decoder,facts);iat=_iat_slot_use_scan(data,image,decoder,facts)
        result=_evidence(predecessor,sealed_targets,direct,facts,rows=rows,image=image,scan=scan,iat=iat)
        if _load_executable(executable)[2]!=digest:_bad("executable changed during exact rebuild")
        _assert_publication_safe(result);validate_native_operator_new_second_callee_second_callee_static_boundary_structure(result,predecessor,sealed_targets,direct,facts);return result
    return _normalize(run)

def validate_native_operator_new_second_callee_second_callee_static_boundary(executable:Path,evidence:Mapping[str,Any],predecessor:Mapping[str,Any],sealed_targets:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any],*,inventory:Mapping[str,Any])->dict[str,Any]:
    def run():
        _validate_json_tree(evidence,"evidence");rebuilt=build_native_operator_new_second_callee_second_callee_static_boundary(executable,predecessor,sealed_targets,direct,facts,inventory=inventory)
        if not _same(evidence,rebuilt):_bad("evidence differs from exact rebuild")
        return {"schema_version":SCHEMA_VERSION,"analysis_kind":VERIFICATION_KIND,"status":"verified","build_identity":dict(rebuilt["build_identity"]),"evidence_sha256":_canonical_sha256(rebuilt),"summary":dict(rebuilt["summary"])}
    return _normalize(run)

def encode_native_operator_new_second_callee_second_callee_static_boundary(value:Mapping[str,Any])->str:
    def run():_validate_json_tree(value,"encoded value");return json.dumps(_mapping(value,"encoded value"),ensure_ascii=False,allow_nan=False,sort_keys=True,indent=2)+"\n"
    return _normalize(run)
