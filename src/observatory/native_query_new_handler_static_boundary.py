"""Exact, syntax-only static boundary for Ghidra's ``__query_new_handler`` label."""
from __future__ import annotations
import hashlib,json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_class_factory_chain import NativeLuaClassFactoryChainError,_validated_graphs
from src.observatory.native_lua_class_return_helper_chain import (NativeLuaClassReturnHelperChainError,_REGISTER_NAMES,_canonical_bytes,_canonical_sha256,_expected_point_record,_normalized_declared_edge,_source_identity,_expected_reference_scan,_whole_atlas_reference_scan,_enhanced_cfg,_with_edi_writes,_point_record,_direct_call_records,_call_r32_audit)
from src.observatory.native_lua_cclosure_setfield_publications import NativeLuaCClosurePublicationError,_array,_assert_publication_safe,_atlas_functions,_exact_keys,_hex,_mapping,_rva,_validate_json_tree
from src.observatory.native_lua_direct_calls import ANALYSIS_KIND as DIRECT_KIND,SUPPORTED_CAPSTONE_VERSION,NativeLuaDirectCallError,_decoder,_load_executable,validate_native_lua_direct_call_census,validate_native_lua_direct_call_structure
from src.observatory.native_callnewh_static_boundary import ANALYSIS_KIND as CALLNEWH_KIND,_canonical_sha256 as _callnewh_canonical
from src.observatory.pe_anchor_map import PEAnchorError
SCHEMA_VERSION=1; ANALYSIS_KIND="pe_native_query_new_handler_static_boundary"; VERIFICATION_KIND=ANALYSIS_KIND+"_verification"; STRUCTURE_VERIFICATION_KIND=ANALYSIS_KIND+"_structure_verification"
_EXE="31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9";_FACTS="631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803";_DIRECT="07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608";_CALLNEWH="27f7495174094b3d6dca6acd6e9975a4dfa7d349f3bf974d40c3f5acd0b4eb45"
_ENTRY=0x38BC08;_BODY="d891c503b590777cfded201a57a6b3032eea43bf3392f0133a49fcc44f8b890c";_ATLAS="0f3f986d1408f60a6ea68a357bd990d494e96e44115d6de19ba633e22f0804d5";_CFG="d21337510640f0a3c667168438e31aeb61dcc6391119b79fb3c3552c313ce35d"
class NativeQueryNewHandlerStaticBoundaryError(RuntimeError):pass
def _point(role,rva,encoded):return {"role":role,"rva":rva,"encoded":bytes.fromhex(encoded),"api":None,"meaning":{"operation":"decoded_instruction","source_semantic_names_assigned":False}}
_BYTES=((0x38BC08,"6a0c"),(0x38BC0A,"68a8e38800"),(0x38BC0F,"e89cc8fcff"),(0x38BC14,"8365e400"),(0x38BC18,"6a00"),(0x38BC1A,"e8a6cfffff"),(0x38BC1F,"59"),(0x38BC20,"8365fc00"),(0x38BC24,"8b35283f8900"),(0x38BC2A,"8bce"),(0x38BC2C,"83e11f"),(0x38BC2F,"3335e4718b00"),(0x38BC35,"d3ce"),(0x38BC37,"8975e4"),(0x38BC3A,"c745fcfeffffff"),(0x38BC41,"e80b000000"),(0x38BC46,"8bc6"),(0x38BC48,"e8a9c8fcff"),(0x38BC4D,"c3"))
_FUNCTION={"role":"analysis_labeled_query_new_handler_static_boundary","entry_rva":_ENTRY,"body_size":70,"body_sha256":_BODY,"cfg_canonical_sha256":_CFG,"direct_calls":[],"staged_dispatches":[],"call_r32":{},"points":[_point(f"instruction_{i:02d}",r,b) for i,(r,b) in enumerate(_BYTES)],"semantic_facts":{"analysis_label":"__query_new_handler","analysis_label_only":True,"source_semantic_names_assigned":False,"runtime_or_success_claimed":False}}
_EDGES=((0x38BC0F,"e89cc8fcff",0x3584B0),(0x38BC1A,"e8a6cfffff",0x388BC5),(0x38BC41,"e80b000000",0x38BC51),(0x38BC48,"e8a9c8fcff",0x3584F6))
_METHOD={"structural_boundary":"PE-free validation reconstructs every retained finite record. Exact bytes, pointer-location section spans, and all-atlas traversal require the sealed executable.","not_claimed":["new-handler, allocation, SEH, lock, security, ABI, success, ownership, lifetime, or size semantics","runtime reachability, invocation, order, frequency, normal return, source identity, or pointer contents","behavior or identity of opaque direct callees","computed, indirect, data, un-atlased, or Lua-side references"]}
def _same(a,b):return _canonical_bytes(a)==_canonical_bytes(b)
def _facts_identity(f):
 b=_source_identity(f,"pe_ghidra_program_facts",_FACTS,"facts");s=_mapping(f.get("summary"),"summary");return {**b,"function_count":s.get("function_count"),"body_range_count":s.get("body_range_count"),"function_body_bytes":s.get("function_body_bytes")}
def _preflight(callnewh,direct,facts):
 identity=_mapping(facts.get("identity"),"identity")
 if identity.get("executable_sha256")!=_EXE or not _same(callnewh.get("build_identity"),dict(identity)) or not _same(direct.get("build_identity"),dict(identity)):raise NativeQueryNewHandlerStaticBoundaryError("prerequisite build identity differs")
 if _callnewh_canonical(callnewh)!=_CALLNEWH:raise NativeQueryNewHandlerStaticBoundaryError("callnewh canonical receipt differs")
 return _facts_identity(facts),_source_identity(direct,DIRECT_KIND,_DIRECT,"direct calls"),_source_identity(callnewh,CALLNEWH_KIND,_CALLNEWH,"callnewh boundary")
def _profile(facts):
 refs=[]
 for raw in _array(facts.get("ghidra_declared_direct_calls"),"edges"):
  edge=_mapping(raw,"edge")
  if _rva(edge.get("target_entry_rva"),"target")==_ENTRY:
   site,target,owner=(_rva(edge.get(k),k) for k in ("instruction_rva","target_rva","source_entry_rva"));refs.append({"instruction_rva":site,"owner_entry_rva":owner,"target_rva":target,"encoded":(b"\xe8"+int(target-(site+5)).to_bytes(4,"little",signed=True)).hex(),"operand_index":0})
 if len(refs)!=1 or refs[0]["instruction_rva"]!=0x38BBD5 or refs[0]["owner_entry_rva"]!=0x38BBC4:raise NativeQueryNewHandlerStaticBoundaryError("incoming reference profile differs")
 return {"executable_sha256":_EXE,"functions":[_FUNCTION],"literals":[],"native_edges":[],"target_references":refs}
def _scan(scan,require_owner_partition=False):
 out=dict(_mapping(scan,"scan"));a=dict(_mapping(out.get("aggregates"),"aggregates"));a.pop("returned_callback_reference_count",None);a.pop("alternate_owner_reference_count",None);out["aggregates"]=a;refs=_array(out.get("references"),"references")
 if len(refs)!=1 or a!={"reference_count":1,"direct_call_count":1,"comparison_count":0,"other_address_count":0,"memory_operand_count":0,"owner_count":1}:raise NativeQueryNewHandlerStaticBoundaryError("reference partition differs")
 item=_mapping(refs[0],"reference")
 if (item.get("instruction_rva"),item.get("owner_entry_rva"),item.get("instruction_size"),item.get("operand_index"),item.get("operand_class"),item.get("use_class"),item.get("call_form")) != ("0x0038bbd5","0x0038bbc4",5,0,"immediate","direct_call","x86_relative_near_call_e8") or item.get("ghidra_declared_direct_edge") is None or type(item.get("owner_atlas_record_sha256")) is not str:raise NativeQueryNewHandlerStaticBoundaryError("incoming E8 record differs")
 supplied=_array(out.get("owner_partition",[]),"owners")
 for owner in supplied:_exact_keys(_mapping(owner,"owner"),{"owner_entry_rva","owner_atlas_record_sha256","reference_count"},"owner")
 derived=[{"owner_entry_rva":item["owner_entry_rva"],"owner_atlas_record_sha256":item["owner_atlas_record_sha256"],"reference_count":1}]
 if require_owner_partition and ("owner_partition" not in out or not _same(supplied,derived)):raise NativeQueryNewHandlerStaticBoundaryError("owner partition differs")
 out["owner_partition"]=derived;return out
def _expected_scan(facts,direct):return _scan(_expected_reference_scan(facts,direct,_profile(facts)))
def _records(data,image,decoder,facts,direct):
 import capstone,capstone.x86_const as x86
 from src.observatory.native_lua_cclosure_setfield_publications import _decode_range
 decoder.detail=True;function=_atlas_functions(facts).get(_ENTRY)
 if function is None or function.get("thunk") is not False or function.get("body_size")!=70 or function.get("body_sha256")!=_BODY:raise NativeQueryNewHandlerStaticBoundaryError("atlas body differs")
 ins=_decode_range(data,image,_ENTRY,70,decoder)
 if hashlib.sha256(b"".join(bytes(i.bytes) for i in ins)).hexdigest()!=_BODY:raise NativeQueryNewHandlerStaticBoundaryError("PE body differs")
 graph=_with_edi_writes(_enhanced_cfg(ins,image.image_base,(_ENTRY,70),capstone,x86),ins,x86);graph["caller_entry_rva"]=_hex(_ENTRY)
 if _canonical_sha256(graph)!=_CFG:raise NativeQueryNewHandlerStaticBoundaryError("CFG differs")
 by={i.address-image.image_base:i for i in ins};points=[]
 for spec in _FUNCTION["points"]:
  item=by.get(spec["rva"])
  if item is None:raise NativeQueryNewHandlerStaticBoundaryError("instruction missing")
  points.append(_point_record(item,image.image_base,spec))
 body={"role":_FUNCTION["role"],"entry_rva":_hex(_ENTRY),"atlas_record_sha256":_ATLAS,"body_size":70,"body_sha256":_BODY,"range_start_rva":_hex(_ENTRY),"range_size":70,"control_flow_graph_canonical_sha256":_CFG,"reviewed_points":points,"direct_lua_calls":_direct_call_records(_FUNCTION,direct),"staged_lua_dispatches":[],"call_r32_audit":_call_r32_audit(ins,_FUNCTION),"register_call_partition_complete":True,"semantic_facts":dict(_FUNCTION["semantic_facts"])};return [body],[graph]
def _native(facts,image=None):
 functions=_atlas_functions(facts);source=functions.get(_ENTRY)
 if source is None or atlas_record_sha256(source)!=_ATLAS or source.get("body_size")!=70 or source.get("body_sha256")!=_BODY:raise NativeQueryNewHandlerStaticBoundaryError("source differs")
 declared={_rva(_mapping(x,"edge").get("instruction_rva"),"site"):_mapping(x,"edge") for x in _array(facts.get("ghidra_declared_direct_calls"),"edges")};direct=[]
 for site,encoded,target in _EDGES:
  edge,callee=declared.get(site),functions.get(target)
  if edge is None or callee is None or _rva(edge.get("source_entry_rva"),"source")!=_ENTRY or _rva(edge.get("target_entry_rva"),"target")!=target:raise NativeQueryNewHandlerStaticBoundaryError("native edge differs")
  direct.append({"role":"opaque_native_direct_edge","source_entry_rva":_hex(_ENTRY),"source_atlas_record_sha256":_ATLAS,"source_body_size":70,"source_body_sha256":_BODY,"instruction":{"rva":_hex(site),"size":5,"sha256":hashlib.sha256(bytes.fromhex(encoded)).hexdigest()},"target_entry_rva":_hex(target),"target_rva":_hex(target),"target_atlas_record_sha256":atlas_record_sha256(callee),"target_body_size":callee.get("body_size"),"target_body_sha256":callee.get("body_sha256"),"ghidra_declared_direct_edge":_normalized_declared_edge(edge),"callee_behavior_opaque":True})
 pointers=[{"role":"opaque_absolute_pointer_push_syntax","instruction":{"rva":"0x0038bc0a","size":5,"sha256":hashlib.sha256(bytes.fromhex("68a8e38800")).hexdigest()},"operand_va":"0x0088e3a8","operand_rva":"0x0048e3a8","section_name":".rdata","section_characteristics":"0x40000040","section_writable":False,"file_backed":True,"contents_or_semantics_opaque":True},{"role":"opaque_absolute_memory_read_syntax","instruction":{"rva":"0x0038bc24","size":6,"sha256":hashlib.sha256(bytes.fromhex("8b35283f8900")).hexdigest()},"operand_va":"0x00893f28","operand_rva":"0x00493f28","section_name":".data","section_characteristics":"0xc0000040","section_writable":True,"file_backed":True,"contents_or_semantics_opaque":True},{"role":"opaque_absolute_memory_read_syntax","instruction":{"rva":"0x0038bc2f","size":6,"sha256":hashlib.sha256(bytes.fromhex("3335e4718b00")).hexdigest()},"operand_va":"0x008b71e4","operand_rva":"0x004b71e4","section_name":".data","section_characteristics":"0xc0000040","section_writable":True,"file_backed":False,"contents_or_semantics_opaque":True}]
 if image is not None:
  for item in pointers:
   rva=_rva(item["operand_rva"],"pointer RVA"); section=next((s for s in image.sections if s.virtual_address<=rva<s.virtual_address+s.virtual_size),None);backed=image.rva_to_file_offset(rva) is not None
   if section is None or (section.name,_hex(section.characteristics),bool(section.characteristics&0x80000000),backed)!=(item["section_name"],item["section_characteristics"],item["section_writable"],item["file_backed"]):raise NativeQueryNewHandlerStaticBoundaryError("pointer section span differs")
 return {"direct":direct,"absolute_pointer_or_memory_syntax":pointers}
def _predecessor(callnewh,scan):
 matches=[dict(_mapping(x,"callnewh edge")) for x in _array(callnewh.get("native_calls",{}).get("direct",[]),"callnewh direct") if _rva(_mapping(x,"edge").get("source_entry_rva"),"source")==0x38BBC4 and _rva(_mapping(x,"edge").get("target_entry_rva"),"target")==_ENTRY and _rva(_mapping(_mapping(x,"edge").get("instruction"),"instruction").get("rva"),"site")==0x38BBD5]
 if len(matches)!=1:raise NativeQueryNewHandlerStaticBoundaryError("callnewh predecessor differs")
 edge=matches[0];ref=_mapping(_array(scan.get("references"),"references")[0],"reference");instruction=_mapping(edge.get("instruction"),"instruction")
 if (ref.get("instruction_size"),ref.get("instruction_sha256"))!=(instruction.get("size"),instruction.get("sha256")) or ref.get("owner_atlas_record_sha256")!=edge.get("source_atlas_record_sha256") or ref.get("target_atlas_record_sha256")!=edge.get("target_atlas_record_sha256") or not _same(ref.get("ghidra_declared_direct_edge"),edge.get("ghidra_declared_direct_edge")):raise NativeQueryNewHandlerStaticBoundaryError("predecessor scan join differs")
 return edge
def _decoder_contract():return {"name":"capstone","version":SUPPORTED_CAPSTONE_VERSION,"architecture":"x86","mode_bits":32,"sealed_instruction_count":19,"register_call_encoding_audit":[{"register":r,"encoding":f"ff{0xd0+i:02x}"} for i,r in enumerate(_REGISTER_NAMES)]}
def _expected_body(facts):
 if _atlas_functions(facts).get(_ENTRY) is None:raise NativeQueryNewHandlerStaticBoundaryError("target absent")
 return {"role":_FUNCTION["role"],"entry_rva":_hex(_ENTRY),"atlas_record_sha256":_ATLAS,"body_size":70,"body_sha256":_BODY,"range_start_rva":_hex(_ENTRY),"range_size":70,"control_flow_graph_canonical_sha256":_CFG,"reviewed_points":[_expected_point_record(x) for x in _FUNCTION["points"]],"direct_lua_calls":[],"staged_lua_dispatches":[],"call_r32_audit":[{"register":r,"call_rvas":[]} for r in _REGISTER_NAMES],"register_call_partition_complete":True,"semantic_facts":_FUNCTION["semantic_facts"]}
def _summary(result):return {"reviewed_query_new_handler_count":1,"reviewed_query_new_handler_bytes":70,"sealed_instruction_count":19,"sealed_control_flow_graph_count":1,"sealed_control_flow_graph_node_count":19,"sealed_control_flow_graph_edge_count":18,"direct_lua_call_count":0,"staged_lua_dispatch_count":0,"call_r32_count":0,"literal_count":0,"native_direct_edge_count":4,"absolute_pointer_or_memory_syntax_count":3,"callnewh_predecessor_edge_count":1,"target_reference_count":1,"target_reference_owner_count":1,"schema_violations":0}
def build_native_query_new_handler_static_boundary(executable,callnewh,direct,facts,*,inventory):
 try:
  for x,label in ((callnewh,"callnewh"),(direct,"direct"),(facts,"facts"),(inventory,"inventory")):_validate_json_tree(x,label)
  receipt=validate_native_lua_direct_call_census(executable,direct,facts,inventory=inventory)
  if receipt.get("status")!="verified" or receipt.get("evidence_sha256")!=_DIRECT:raise NativeQueryNewHandlerStaticBoundaryError("direct prerequisite differs")
  atlas,direct_id,callnewh_id=_preflight(callnewh,direct,facts);data,image,digest=_load_executable(executable)
  if digest!=_EXE:raise NativeQueryNewHandlerStaticBoundaryError("executable differs")
  decoder,_=_decoder();bodies,graphs=_records(data,image,decoder,facts,direct);scan=_scan(_whole_atlas_reference_scan(data,image,decoder,facts,direct,_profile(facts)));result={"schema_version":1,"analysis_kind":ANALYSIS_KIND,"build_identity":dict(_mapping(facts.get("identity"),"identity")),"atlas":atlas,"direct_call_census":direct_id,"callnewh_static_boundary":callnewh_id,"callnewh_query_new_handler_edge":_predecessor(callnewh,scan),"decoder":_decoder_contract(),"function_bodies":bodies,"control_flow_graphs":graphs,"native_calls":_native(facts,image),"whole_atlas_reference_scan":scan,"method":_METHOD};result["summary"]=_summary(result);_assert_publication_safe(result)
  if _load_executable(executable)[2]!=digest:raise NativeQueryNewHandlerStaticBoundaryError("executable changed")
  validate_native_query_new_handler_static_boundary_structure(result,callnewh,direct,facts);return result
 except NativeQueryNewHandlerStaticBoundaryError:raise
 except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassFactoryChainError,NativeLuaClassReturnHelperChainError,PEAnchorError,OSError) as exc:raise NativeQueryNewHandlerStaticBoundaryError(str(exc)) from exc
def validate_native_query_new_handler_static_boundary_structure(evidence,callnewh,direct,facts):
 try:
  for x,label in ((evidence,"evidence"),(callnewh,"callnewh"),(direct,"direct"),(facts,"facts")):_validate_json_tree(x,label)
  receipt=validate_native_lua_direct_call_structure(direct,facts)
  if receipt.get("status")!="structurally_verified" or receipt.get("evidence_sha256")!=_DIRECT:raise NativeQueryNewHandlerStaticBoundaryError("direct structure differs")
  atlas,direct_id,callnewh_id=_preflight(callnewh,direct,facts);evidence=_mapping(evidence,"evidence");_exact_keys(evidence,{"schema_version","analysis_kind","build_identity","atlas","direct_call_census","callnewh_static_boundary","callnewh_query_new_handler_edge","decoder","function_bodies","control_flow_graphs","native_calls","whole_atlas_reference_scan","method","summary"},"evidence")
  if type(evidence.get("schema_version")) is not int or evidence.get("schema_version")!=1 or evidence.get("analysis_kind")!=ANALYSIS_KIND:raise NativeQueryNewHandlerStaticBoundaryError("schema differs")
  if not all((_same(evidence.get("build_identity"),dict(_mapping(facts.get("identity"),"identity"))),_same(evidence.get("atlas"),atlas),_same(evidence.get("direct_call_census"),direct_id),_same(evidence.get("callnewh_static_boundary"),callnewh_id),_same(evidence.get("decoder"),_decoder_contract()),_same(evidence.get("method"),_METHOD))):raise NativeQueryNewHandlerStaticBoundaryError("prerequisite differs")
  bodies=_array(evidence.get("function_bodies"),"bodies")
  if len(bodies)!=1 or not _same(bodies[0],_expected_body(facts)):raise NativeQueryNewHandlerStaticBoundaryError("body differs")
  graph=_validated_graphs({"control_flow_graphs":evidence.get("control_flow_graphs")},_atlas_functions(facts));
  if set(graph)!={_ENTRY} or _canonical_sha256(graph[_ENTRY][0])!=_CFG or graph[_ENTRY][0].get("node_count")!=19 or graph[_ENTRY][0].get("edge_count")!=18:raise NativeQueryNewHandlerStaticBoundaryError("CFG differs")
  scan=_scan(_mapping(evidence.get("whole_atlas_reference_scan"),"scan"),require_owner_partition=True)
  if not _same(scan,_expected_scan(facts,direct)) or not _same(evidence.get("callnewh_query_new_handler_edge"),_predecessor(callnewh,scan)) or not _same(evidence.get("native_calls"),_native(facts)) or not _same(evidence.get("summary"),_summary(evidence)):raise NativeQueryNewHandlerStaticBoundaryError("edge, scan, or summary differs")
  _assert_publication_safe(evidence);return {"schema_version":1,"analysis_kind":STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","build_identity":dict(evidence["build_identity"]),"evidence_sha256":_canonical_sha256(evidence),"summary":dict(evidence["summary"])}
 except NativeQueryNewHandlerStaticBoundaryError:raise
 except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassFactoryChainError,NativeLuaClassReturnHelperChainError) as exc:raise NativeQueryNewHandlerStaticBoundaryError(str(exc)) from exc
def validate_native_query_new_handler_static_boundary(executable,evidence,callnewh,direct,facts,*,inventory):
 rebuilt=build_native_query_new_handler_static_boundary(executable,callnewh,direct,facts,inventory=inventory)
 if not _same(evidence,rebuilt):raise NativeQueryNewHandlerStaticBoundaryError("evidence differs from rebuild")
 return {"schema_version":1,"analysis_kind":VERIFICATION_KIND,"status":"verified","build_identity":dict(rebuilt["build_identity"]),"evidence_sha256":_canonical_sha256(rebuilt),"summary":dict(rebuilt["summary"])}
def encode_native_query_new_handler_static_boundary(value):
 try:_validate_json_tree(value);return json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2,sort_keys=True)+"\n"
 except NativeLuaCClosurePublicationError as exc:raise NativeQueryNewHandlerStaticBoundaryError(str(exc)) from exc
