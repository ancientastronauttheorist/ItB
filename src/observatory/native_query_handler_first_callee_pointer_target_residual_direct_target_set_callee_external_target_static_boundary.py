"""Immutable structural receipt for external target 0x00357b6a."""
from __future__ import annotations
import hashlib, json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from capstone import CsError
from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_class_return_helper_chain import (_REGISTER_NAMES,_canonical_bytes,_canonical_sha256,_normalized_declared_edge,_source_identity,NativeLuaClassReturnHelperChainError)
from src.observatory.native_lua_cclosure_setfield_publications import (_array,_assert_publication_safe,_atlas_functions,_decode_range,_hex,_mapping,_rva,_validate_json_tree,NativeLuaCClosurePublicationError)
from src.observatory.native_lua_direct_calls import (ANALYSIS_KIND as DIRECT_KIND,SUPPORTED_CAPSTONE_VERSION,_decoder,_load_executable,validate_native_lua_direct_call_census,validate_native_lua_direct_call_structure,NativeLuaDirectCallError)
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION=1
ANALYSIS_KIND="pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary"
VERIFICATION_KIND=ANALYSIS_KIND+"_verification"; STRUCTURE_VERIFICATION_KIND=ANALYSIS_KIND+"_structure_verification"
_EXE="31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"; _FACTS="631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"; _DIRECT="07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"; _PREDECESSOR="8e8a4c0d5c462bf20417b529313e634a76030214c34c35f0875e506a4f57f8b1"; _IMAGE_BASE=0x400000
_ROOT=0x357b6a; _SIZE=251; _SHA="0a7f470e5151d95873547c1201fe9ad8d4c502d6afc9b530de59d9390eb9c0ed"; _ATLAS="324c7636ddd286b956053bb39fa045719f388d5254e441ce98b33d77d11fb074"; _CFG="020e22523160d01f527e80e62320f1052dc8654755d8aee3b8a88ae4dcc14048"
_RAW=("558bec81ec240300006a17e81850040085c074056a0259cd29a3286c8b00890d246c8b008915206c8b00891d1c6c8b008935186c8b00893d146c8b00668c15406c8b00668c0d346c8b00668c1d106c8b00668c050c6c8b00668c25086c8b00668c2d046c8b009c8f05386c8b008b4500a32c6c8b008b4504a3306c8b008d4508a33c6c8b008b85dcfcffffc705786b8b0001000100a1306c8b00a3346b8b00c705286b8b00090400c0c7052c6b8b0001000000c705386b8b00010000006a04586bc000c7803c6b8b00020000006a04586bc0008b0d283f8900894c05f86a0458c1e0008b0d243f8900894c05f868f8197f00e8e1feffff8be55dc3")
_OUT=((0x357b75,0x39cb92,"e818500400",6,"247575b8ff280345c05bf6c58c3620b861c076bb718663401c6c729f4542cee7","495f4729075f0f38c369905e1cd00f3f3d9b1eb5247caf5ce112fec3e6066f4e"),(0x357c5c,0x357b42,"e8e1feffff",40,"5a4568c1047a793bff70d7632cc28b29500160dea29a7a4b913c8416835bee26","c3417b9783a2a113a7f51883f10fd57557b7457ca184638a679cf15ac7ed863e"))
_PART={"owner_partition":"2a2416dd95714b643e9479120de7fa221ca334afb358d3c3ebed2cfd155be7ba","target_owner_partition":"2947e96c511745d6e8cdeec79be647a470829e7aad9ea2156e72a2894370e492","target_reference_partition":"c8390fdbf8e42e8a1fa6256377a5ddb23304a651eae818eaebf2a3f23a5c31bf"}
_VIRTUAL_ONLY_DATA_SITES = frozenset(
    {
        0x357B83,
        0x357B88,
        0x357B8E,
        0x357B94,
        0x357B9A,
        0x357BA0,
        0x357BA6,
        0x357BAD,
        0x357BB4,
        0x357BBB,
        0x357BC2,
        0x357BC9,
        0x357BD1,
        0x357BDA,
        0x357BE2,
        0x357BEA,
        0x357BF5,
        0x357BFF,
        0x357C04,
        0x357C09,
        0x357C13,
        0x357C1D,
    }
)

class NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError(RuntimeError): pass
def _bad(s:str)->None: raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError(s)
def _same(a:Any,b:Any)->bool:return _canonical_bytes(a)==_canonical_bytes(b)
def _h(r:int,b:str)->dict[str,Any]:x=bytes.fromhex(b);return {"rva":_hex(r),"size":len(x),"sha256":hashlib.sha256(x).hexdigest()}
def _fun(f:Mapping[str,Any])->dict[int,Mapping[str,Any]]:return _atlas_functions(f)
def _edges(f:Mapping[str,Any])->dict[int,Mapping[str,Any]]:
 out={}
 for x in _array(f.get("ghidra_declared_direct_calls"),"edges"):
  e=_mapping(x,"edge");s=_rva(e.get("instruction_rva"),"site")
  if s in out:_bad("duplicate declared edge")
  out[s]=e
 return out
def _compact(x:Any)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def _access(x:int)->str:
 if x not in {0,1,2,3}:_bad("operand access")
 return {0:"none",1:"read",2:"write",3:"read_write"}[x]

def _decode()->list[Any]:
 d,_=_decoder();d.detail=True;ins=list(d.disasm(bytes.fromhex(_RAW),_IMAGE_BASE+_ROOT))
 if len(ins)!=56 or b"".join(bytes(x.bytes) for x in ins)!=bytes.fromhex(_RAW):_bad("synthetic body decode")
 return ins
def _points(ins:list[Any])->list[dict[str,Any]]:
 out=[]
 for i in ins:
  _,w=i.regs_access();n={i.reg_name(x).lower() for x in w};raw=bytes(i.bytes)
  out.append({"rva":_hex(i.address-_IMAGE_BASE),"size":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"writes_ebx":"ebx"in n,"writes_esi":"esi"in n,"writes_edi":"edi"in n,"writes_esp":"esp"in n})
 return out
def _graph(ins:list[Any]|None=None)->dict[str,Any]:
 import capstone,capstone.x86_const as x
 from src.observatory.native_lua_cclosure_table_key_provenance import _enhanced_cfg
 from src.observatory.native_lua_class_factory_chain import _with_edi_writes
 ins=_decode() if ins is None else ins;g=_with_edi_writes(_enhanced_cfg(ins,_IMAGE_BASE,(_ROOT,_SIZE),capstone,x),ins,x);g["caller_entry_rva"]=_hex(_ROOT)
 node=next((n for n in g["nodes"] if n["rva"]=="0x00357b81"),None)
 if node is None or node["flow_kind"]!="terminal" or node["successor_rvas"]!=[] or _canonical_sha256(g)!=_CFG or (g["node_count"],g["edge_count"])!=(56,55):_bad("root CFG")
 return g
def _section(v:int)->tuple[str,int,int]:
 r=v-_IMAGE_BASE
 if 0x1000<=r<0x3d6000:return ".text",0x1000,0x60000020
 if 0x3d6000<=r<0x492000:return ".rdata",0x3d6000,0x40000040
 if 0x492000<=r<0x4d9000:return ".data",0x492000,0xc0000040
 _bad("unsealed PE section");raise AssertionError
def _operands(ins:list[Any],image:Any|None=None)->list[dict[str,Any]]:
 import capstone.x86_const as x
 out=[]
 for i in ins:
  r=i.address-_IMAGE_BASE;raw=bytes(i.bytes)
  for n,o in enumerate(i.operands):
   if o.type==x.X86_OP_IMM:v,k=o.imm&0xffffffff,"immediate"
   elif o.type==x.X86_OP_MEM and o.mem.segment==x.X86_REG_INVALID and o.mem.base==x.X86_REG_INVALID and o.mem.index==x.X86_REG_INVALID:v,k=o.mem.disp&0xffffffff,"absolute_memory"
   else:continue
   try:name,s,c=_section(v)
   except NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError:continue
   backed = r not in _VIRTUAL_ONLY_DATA_SITES
   if image is not None:
    actual=next((q for q in image.sections if q.virtual_address<=v-image.image_base<q.virtual_address+q.virtual_size),None)
    if actual is None or (actual.name,actual.virtual_address,actual.characteristics)!=(name,s,c) or (image.rva_to_file_offset(v-image.image_base) is not None)!=backed:_bad("exact PE section or backing differs")
   role={0x357b75:"declared_direct_call_target",0x357b7c:"declared_conditional_branch_target",0x357c5c:"declared_direct_call_target"}.get(r,"noncontrol_absolute_memory" if k=="absolute_memory" else "noncontrol_immediate")
   out.append({"role":"typed_pe_address_operand","instruction":{"rva":_hex(r),"size":len(raw),"sha256":hashlib.sha256(raw).hexdigest()},"operand_class":k,"operand_index":n,"operand_access":_access(o.access),"operand_va":_hex(v),"operand_rva":_hex(v-_IMAGE_BASE),"control_syntax":role,"section_name":name,"section_rva":_hex(s),"section_characteristics":_hex(c),"section_writable":bool(c&0x80000000),"file_backed":backed,"contents_or_runtime_behavior_opaque":True})
 out.sort(key=lambda z:(_rva(z["instruction"]["rva"],"site"),z["operand_index"]));data=[z for z in out if z["section_name"]==".data"]
 if len(out)!=28 or sum(z["operand_class"]=="immediate" for z in out)!=4 or len(data)!=24 or sum(z["operand_access"]=="write" for z in data)!=21 or sum(z["operand_access"]=="read" for z in data)!=3:_bad("PE operand partition")
 return out
def _pre(p:Mapping[str,Any],d:Mapping[str,Any],f:Mapping[str,Any])->dict[str,Any]:
 ident=_mapping(f.get("identity"),"identity")
 if ident.get("executable_sha256")!=_EXE or not _same(p.get("build_identity"),dict(ident)) or not _same(d.get("build_identity"),dict(ident)) or _canonical_sha256(p)!=_PREDECESSOR:_bad("predecessor pin")
 if p.get("analysis_kind")!="pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary":_bad("predecessor kind")
 q=validate_native_lua_direct_call_structure(d,f)
 if q.get("status")!="structurally_verified" or q.get("evidence_sha256")!=_DIRECT:_bad("direct prerequisite")
 return {"program_facts":_source_identity(f,"pe_ghidra_program_facts",_FACTS,"facts"),"predecessor_static_boundary":_source_identity(p,p["analysis_kind"],_PREDECESSOR,"predecessor"),"direct_call_census":_source_identity(d,DIRECT_KIND,_DIRECT,"direct")}
def _outgoing(f:Mapping[str,Any])->list[dict[str,Any]]:
 fs,es=_fun(f),_edges(f);src=fs.get(_ROOT)
 if src is None or {s for s,e in es.items() if _rva(e.get("source_entry_rva"),"src")==_ROOT}!={x[0] for x in _OUT}:_bad("outgoing partition")
 out=[]
 for s,t,b,size,body,atlas in _OUT:
  e,tf=es.get(s),fs.get(t)
  if e is None or tf is None or (_rva(e.get("target_entry_rva"),"target"),_rva(e.get("target_rva"),"rva"))!=(t,t) or (tf.get("body_size"),tf.get("body_sha256"),atlas_record_sha256(tf))!=(size,body,atlas):_bad("outgoing target")
  out.append({"role":"opaque_declared_direct_edge","instruction":_h(s,b),"source_entry_rva":_hex(_ROOT),"source_body_size":_SIZE,"source_body_sha256":_SHA,"source_atlas_record_sha256":_ATLAS,"target_entry_rva":_hex(t),"target_body_size":size,"target_body_sha256":body,"target_atlas_record_sha256":atlas,"ghidra_declared_direct_edge":_normalized_declared_edge(e),"control_encoding":"e8"})
 return out
def _parent(p:Mapping[str,Any])->list[dict[str,Any]]:
 rows=[dict(_mapping(x,"parent")) for x in _array(_mapping(p.get("native_calls"),"calls").get("outgoing_direct"),"outgoing")]
 hit=[x for x in rows if _rva(_mapping(x.get("instruction"),"instruction").get("rva"),"site")==0x3574d5 and _rva(x.get("target_entry_rva"),"target")==_ROOT]
 if len(rows)!=1 or len(hit)!=1 or hit[0].get("control_encoding")!="f2e9" or not _same(hit[0].get("instruction"),_h(0x3574d5,"f2e98f060000")):_bad("parent join")
 return hit
def _native(ins:list[Any],f:Mapping[str,Any],image:Any|None=None)->dict[str,Any]:
 import capstone.x86_const as x
 if any(i.id in {x.X86_INS_CALL,x.X86_INS_JMP} and any(o.type in {x.X86_OP_REG,x.X86_OP_MEM} for o in i.operands) for i in ins):_bad("indirect root control")
 if any(o.type==x.X86_OP_MEM and o.mem.segment!=x.X86_REG_INVALID for i in ins for o in i.operands):_bad("segment root syntax")
 return {"outgoing_direct":_outgoing(f),"opaque_indirect_controls":[],"indirect_control_partition_complete":True,"pe_address_operands":_operands(ins,image),"pe_address_operand_partition_complete":True,"segment_qualified_memory_syntax":[],"segment_qualified_memory_partition_complete":True,"bnd_prefixed_control_syntax":[],"bnd_prefixed_control_partition_complete":True,"opaque_interrupt_syntax":[{"role":"opaque_interrupt_syntax","instruction":_h(0x357b81,"cd29"),"interrupt_vector":"0x29","runtime_semantics_opaque":True}],"opaque_interrupt_partition_complete":True,"call_r32_audit":[{"register":r,"call_rvas":[]} for r in _REGISTER_NAMES],"register_call_partition_complete":True}
def _scan(f:Mapping[str,Any],data:bytes|None=None,image:Any|None=None,decoder:Any|None=None)->dict[str,Any]:
 fs,es=_fun(f),_edges(f);e=es.get(0x3574d5);owner=fs.get(0x3574ca)
 if e is None or owner is None or (_rva(e.get("source_entry_rva"),"source"),_rva(e.get("target_entry_rva"),"target"))!=(0x3574ca,_ROOT):_bad("scan parent")
 raw=bytes.fromhex("f2e98f060000");ref={"instruction_rva":"0x003574d5","instruction_size":6,"instruction_sha256":hashlib.sha256(raw).hexdigest(),"owner_entry_rva":"0x003574ca","owner_atlas_record_sha256":atlas_record_sha256(owner),"target_rva":_hex(_ROOT),"target_atlas_record_sha256":_ATLAS,"target_va":_hex(_IMAGE_BASE+_ROOT),"operand_class":"immediate","operand_index":0,"use_class":"other_address","call_form":None,"ghidra_declared_direct_edge":_normalized_declared_edge(e)}
 op=[{"owner_entry_rva":ref["owner_entry_rva"],"owner_atlas_record_sha256":ref["owner_atlas_record_sha256"],"reference_count":1}];top=[{"target_rva":_hex(_ROOT),**op[0]}];tr=[{"target_rva":_hex(_ROOT),"target_atlas_record_sha256":_ATLAS,"reference_count":1}];hs={"owner_partition":_compact(op),"target_owner_partition":_compact(top),"target_reference_partition":_compact(tr)}
 if hs!=_PART:_bad("scan partition")
 result={"scope":{"atlas_function_count":25312,"atlas_body_range_count":25490,"decoded_bytes":3735718,"decoded_instructions":1153814,"all_declared_ranges_decoded":True,"operand_classes":["absolute_memory","immediate"]},"references":[ref],"target_partition":[{"target_rva":_hex(_ROOT),"target_atlas_record_sha256":_ATLAS,"reference_count":1,"owner_count":1}],"target_reference_partition":tr,"owner_partition":op,"target_owner_partition":top,"partition_sha256":hs,"aggregates":{"reference_count":1,"target_count":1,"owner_count":1,"target_owner_count":1,"direct_call_count":0,"other_address_count":1,"memory_operand_count":0}}
 if data is None:return result
 import capstone.x86_const as x
 seen=[];count=[0,0,0];decoder.detail=True
 for own,fn in sorted(fs.items()):
  for z in _array(fn.get("ranges"),"range"):
   a=_mapping(z,"range");start,size=_rva(a.get("start_rva"),"start"),a.get("size");xs=_decode_range(data,image,start,size,decoder);count[0]+=1;count[1]+=size;count[2]+=len(xs)
   for i in xs:
    for n,o in enumerate(i.operands):
     v=(o.imm&0xffffffff) if o.type==x.X86_OP_IMM else (o.mem.disp&0xffffffff if o.type==x.X86_OP_MEM and o.mem.segment==x.X86_REG_INVALID and o.mem.base==x.X86_REG_INVALID and o.mem.index==x.X86_REG_INVALID else None)
     if v==image.image_base+_ROOT:seen.append((i.address-image.image_base,n,bytes(i.bytes)))
 if tuple(count)!=(25490,3735718,1153814) or seen!=[(0x3574d5,0,raw)]:_bad("exhaustive scan")
 return result
def _summary()->dict[str,Any]:return {"reviewed_target_count":1,"reviewed_target_bytes":251,"sealed_instruction_count":56,"sealed_control_flow_graph_count":1,"sealed_control_flow_graph_node_count":56,"sealed_control_flow_graph_edge_count":55,"native_direct_edge_count":2,"direct_lua_call_count":0,"staged_lua_dispatch_count":0,"call_r32_count":0,"opaque_indirect_control_count":0,"pe_address_operand_count":28,"pe_immediate_operand_count":4,"pe_absolute_memory_operand_count":24,"pe_data_absolute_memory_write_count":21,"pe_data_absolute_memory_read_count":3,"segment_qualified_memory_syntax_count":0,"bnd_prefixed_control_syntax_count":0,"opaque_interrupt_syntax_count":1,"predecessor_parent_edge_count":1,"target_reference_count":1,"target_reference_target_count":1,"target_reference_owner_count":1,"target_reference_direct_call_count":0,"target_reference_other_address_count":1,"target_reference_memory_operand_count":0,"schema_violations":0}
def _evidence(p:Mapping[str,Any],d:Mapping[str,Any],f:Mapping[str,Any],*,ins:list[Any]|None=None,image:Any|None=None,scan:Mapping[str,Any]|None=None)->dict[str,Any]:
 pre=_pre(p,d,f);ins=_decode() if ins is None else ins;raw=b"".join(bytes(i.bytes) for i in ins);fn=_fun(f).get(_ROOT)
 if raw!=bytes.fromhex(_RAW) or hashlib.sha256(raw).hexdigest()!=_SHA or fn is None or (fn.get("body_size"),fn.get("body_sha256"),atlas_record_sha256(fn))!=(_SIZE,_SHA,_ATLAS):_bad("root body")
 g=_graph(ins);n=_native(ins,f,image);s=_scan(f) if scan is None else dict(scan)
 if not _same(s,_scan(f)):_bad("scan receipt")
 par=_parent(p)
 if s["references"][0]["instruction_rva"]!=par[0]["instruction"]["rva"] or s["references"][0]["instruction_sha256"]!=par[0]["instruction"]["sha256"]:_bad("parent scan")
 return {"schema_version":SCHEMA_VERSION,"analysis_kind":ANALYSIS_KIND,"build_identity":dict(_mapping(f.get("identity"),"identity")),"program_facts":pre["program_facts"],"predecessor_static_boundary":pre["predecessor_static_boundary"],"direct_call_census":pre["direct_call_census"],"decoder":{"name":"capstone","version":SUPPORTED_CAPSTONE_VERSION,"architecture":"x86","mode_bits":32,"sealed_instruction_count":56,"register_call_encoding_audit":[{"register":r,"encoding":f"ff{0xd0+i:02x}"} for i,r in enumerate(_REGISTER_NAMES)]},"function_body":{"role":"residual_callee_external_target_opaque_static_boundary","entry_rva":_hex(_ROOT),"atlas_record_sha256":_ATLAS,"body_size":_SIZE,"body_sha256":_SHA,"range_start_rva":_hex(_ROOT),"range_size":_SIZE,"control_flow_graph_canonical_sha256":_CFG,"reviewed_points":_points(ins),"direct_lua_calls":[],"staged_lua_dispatches":[],"call_r32_audit":[{"register":r,"call_rvas":[]} for r in _REGISTER_NAMES],"register_call_partition_complete":True,"semantic_facts":{"relationship_defined_only":True,"analysis_labels_opaque":True,"source_semantic_names_assigned":False,"runtime_or_success_claimed":False}},"control_flow_graph":g,"predecessor_parent_edges":par,"native_calls":n,"whole_atlas_reference_scan":s,"method":{"structural_boundary":"The receipt seals decoded root syntax, opaque interrupt syntax, PE operands, two declared outgoing edges, and its one-row incoming atlas frontier.","not_claimed":["analysis-label meaning, source identity, ABI, inputs, outputs, behavior, success, failure, or normal return","runtime reachability, invocation, ordering, frequency, state mutation, termination, interrupt behavior, or effect","contents or runtime meaning of PE-address operands","computed, indirect, data, un-atlased, dynamic, or Lua-side references"]},"summary":_summary()}
def _normalize(action):
 try:return action()
 except NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError:raise
 except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassReturnHelperChainError,PEAnchorError,CsError,OSError,TypeError,ValueError) as exc:raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetStaticBoundaryError(str(exc)) from exc
def validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary_structure(evidence:Mapping[str,Any],predecessor:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any])->dict[str,Any]:
 def run():
  for x,l in ((evidence,"evidence"),(predecessor,"predecessor"),(direct,"direct"),(facts,"facts")):_validate_json_tree(x,l)
  want=_evidence(predecessor,direct,facts)
  if not _same(evidence,want):_bad("receipt differs")
  return {"schema_version":SCHEMA_VERSION,"analysis_kind":STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","build_identity":dict(evidence["build_identity"]),"evidence_sha256":_canonical_sha256(evidence),"summary":dict(evidence["summary"])}
 return _normalize(run)
def build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary(executable:Path,predecessor:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any],*,inventory:Mapping[str,Any])->dict[str,Any]:
 def run():
  for x,l in ((predecessor,"predecessor"),(direct,"direct"),(facts,"facts"),(inventory,"inventory")):_validate_json_tree(x,l)
  q=validate_native_lua_direct_call_census(executable,direct,facts,inventory=inventory)
  if q.get("status")!="verified" or q.get("evidence_sha256")!=_DIRECT:_bad("exact direct prerequisite")
  data,image,digest=_load_executable(executable)
  if digest!=_EXE or image.image_base!=_IMAGE_BASE:_bad("executable identity")
  dec,_=_decoder();dec.detail=True;ins=_decode_range(data,image,_ROOT,_SIZE,dec);result=_evidence(predecessor,direct,facts,ins=ins,image=image,scan=_scan(facts,data,image,dec))
  if _load_executable(executable)[2]!=digest:_bad("executable changed")
  validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary_structure(result,predecessor,direct,facts);return result
 return _normalize(run)
def validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary(executable:Path,evidence:Mapping[str,Any],predecessor:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any],*,inventory:Mapping[str,Any])->dict[str,Any]:
 def run():
  _validate_json_tree(evidence,"evidence")
  r=build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary(executable,predecessor,direct,facts,inventory=inventory)
  if not _same(evidence,r):_bad("exact evidence differs")
  return {"schema_version":SCHEMA_VERSION,"analysis_kind":VERIFICATION_KIND,"status":"verified","build_identity":dict(r["build_identity"]),"evidence_sha256":_canonical_sha256(r),"summary":dict(r["summary"])}
 return _normalize(run)
def encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary(value:Mapping[str,Any])->str:
 def run():
  _validate_json_tree(value,"encoded value")
  return json.dumps(_mapping(value,"encoded value"),ensure_ascii=False,allow_nan=False,sort_keys=True,indent=2)+"\n"
 return _normalize(run)
