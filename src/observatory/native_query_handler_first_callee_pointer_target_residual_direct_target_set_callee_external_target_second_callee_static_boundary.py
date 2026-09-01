"""Immutable relationship-only receipt for the 0x00357b42 sibling callee.

Import names below are PE-directory metadata only.  Nothing here asserts that
an import resolves, is reached, executes, returns, terminates, or has a named
runtime effect.
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
from src.observatory.native_lua_cclosure_setfield_publications import (NativeLuaCClosurePublicationError,_array,_assert_publication_safe,_atlas_functions,_decode_range,_hex,_mapping,_rva,_validate_json_tree)
from src.observatory.native_lua_class_factory_chain import _with_edi_writes
from src.observatory.native_lua_class_return_helper_chain import (NativeLuaClassReturnHelperChainError,_REGISTER_NAMES,_canonical_bytes,_canonical_sha256,_source_identity)
from src.observatory.native_lua_cclosure_table_key_provenance import _enhanced_cfg
from src.observatory.native_lua_direct_calls import (ANALYSIS_KIND as DIRECT_KIND,SUPPORTED_CAPSTONE_VERSION,NativeLuaDirectCallError,_decoder,_load_executable,validate_native_lua_direct_call_census,validate_native_lua_direct_call_structure)
from src.observatory.native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary import ANALYSIS_KIND as PREDECESSOR_KIND
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION=1
ANALYSIS_KIND="pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary"
VERIFICATION_KIND=ANALYSIS_KIND+"_verification"; STRUCTURE_VERIFICATION_KIND=ANALYSIS_KIND+"_structure_verification"
_EXE="31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"; _FACTS="631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"; _DIRECT="07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"; _PRE="0d8bb3aecc53090dc5282844885ed327e79541ebaad4b7ca928e0494f86b08a9"
_BASE=0x400000; _ROOT=0x357b42; _SIZE=40
_RAW="558bec6a00ff15e4607d00ff7508ff1518607d0068090400c0ff15f0607d0050ff1514607d005dc3"
_BODY="5a4568c1047a793bff70d7632cc28b29500160dea29a7a4b913c8416835bee26"; _ATLAS="c3417b9783a2a113a7f51883f10fd57557b7457ca184638a679cf15ac7ed863e"; _CFG="b3d334286def4ca119c59b70f91b17aa46c35b9737edf5088bf755b3f43e0b39"
_PARENT=(0x357c5c,0x357b6a,"e8e1feffff","324c7636ddd286b956053bb39fa045719f388d5254e441ce98b33d77d11fb074")
_FRONTIER=((0x357c5c,0x357b6a,"e8e1feffff","324c7636ddd286b956053bb39fa045719f388d5254e441ce98b33d77d11fb074"),(0x357d38,0x357c71,"e805feffff","34cee74141620b8de324a94f04fe3dd885a816a6139131ddee8f43ab5785752e"))
_FRONTIER_HASH={"owner_partition":"952f4d8d2d4027d45635f916a9f0160b633762f836754533bbb06ba29ae6ec3c","target_owner_partition":"ac04221eb3f1206725537a9fa5a263ad86b263e4d28dd8139f387fd294dc4614","target_reference_partition":"0a36c89948e227a42750480cf04dbb59625da7d8d1437454a2e68ca4beade141"}
_SCOPE={"atlas_function_count":25312,"atlas_body_range_count":25490,"decoded_bytes":3735718,"decoded_instructions":1153814,"all_declared_ranges_decoded":True,"operand_classes":["absolute_memory","immediate"]}
_SLOTS=(
 (0x357b47,"ff15e4607d00",0x3d60e4,"SetUnhandledExceptionFilter",1189,57,0x48ee64,0x48de64,"8e054900","288d12d18ccaf7ffbb83acb8e302170e9bbcbcb7f0abed0d885b52b7b5e4695c",0x3d50e4,0x49058e,0x48f58e,30,"ed0aa1cde363d40184a2d921355662ccb0ecd5c0dd532c7793429c7478dc3010"),
 (0x357b50,"ff1518607d00",0x3d6018,"UnhandledExceptionFilter",1235,6,0x48ed98,0x48dd98,"d2094900","3625f5da824068d558e712c0a25cf84d78677d759e65f2573d0dc86f8bfa6d3a",0x3d5018,0x4909d2,0x48f9d2,27,"eb9dffa74b0280f1f033ad79ee889d7594b9ba15cad218e41a0801fed5c2baf8"),
 (0x357b5b,"ff15f0607d00",0x3d60f0,"GetCurrentProcess",448,60,0x48ee70,0x48de70,"58054900","ad1e627653830a85ad37d35bf475130f267d7d4f8cc9be3cdaad9669b177623c",0x3d50f0,0x490558,0x48f558,20,"5d94f984ba11e5d2085017ddfbbbed1ee35fbc2c7f012c8bc7d989282858eece"),
 (0x357b62,"ff1514607d00",0x3d6014,"TerminateProcess",1216,5,0x48ed94,0x48dd94,"ee094900","3c38ad980f6d41b84590ad861884f9df4683f0d358c6103ea2cddaa48592e9b1",0x3d5014,0x4909ee,0x48f9ee,19,"b862748c120e4b958de335972607f9cded141e4ebc0e176f9aad3508654747ce"),
)
_SLOT_SCANS={
 0x3d60e4:("51449f88077a1c2b734aea3b913f33768b27f479c1e7c5a223068919e4f5e587","dc78a9fbe8ba09f2a35314967c05ec84e2c6fe2f3c04ce61af989bfc4508d6cf",((0x0e412c,0x0e40f0,"ff15e4607d00",0),(0x357b47,0x357b42,"ff15e4607d00",0),(0x35860f,0x35851b,"ff15e4607d00",0),(0x35866e,0x358669,"ff15e4607d00",0),(0x379e2a,0x379d28,"ff15e4607d00",0))),
 0x3d6018:("4c40e41df4b6a33fdaddf5e12043e9c15b2905499ebd490daf24ffa00d804a3d","2554e6dda9dc42b0ca21a601d3d33b274707ad92742fd42d7c6e7333c012feaa",((0x357b50,0x357b42,"ff1518607d00",0),(0x358619,0x35851b,"ff1518607d00",0),(0x379e37,0x379d28,"ff1518607d00",0))),
 0x3d60f0:("6a07cf4ff0f73b0591d3320bff1eea01f2324af69c0c06e0265ba3592916e194","ab89674809c8e80721a66f49160481140f93ef27ec982adc3b981751c3f7eb87",((0x094f5a,0x094de0,"ff15f0607d00",0),(0x094fce,0x094f90,"8b3df0607d00",1),(0x344580,0x344571,"ff15f0607d00",0),(0x34458e,0x344571,"ff15f0607d00",0),(0x357b5b,0x357b42,"ff15f0607d00",0),(0x35a4c1,0x35a489,"ff15f0607d00",0),(0x35b0bb,0x35b0a5,"ff15f0607d00",0),(0x3614b9,0x361497,"ff15f0607d00",0),(0x3614c3,0x361497,"ff15f0607d00",0),(0x36b817,0x36b7e9,"ff15f0607d00",0),(0x36b825,0x36b7e9,"ff15f0607d00",0),(0x379f43,0x379f1f,"ff15f0607d00",0),(0x387db7,0x387d96,"ff15f0607d00",0))),
 0x3d6014:("b6f92e88d51124c287a2be86017ad7c48b879549c1b3e97e3f839e611bfbcc48","ed3dcec1a49a2dd46463b0930da717238f80b2626e55db9bcdb725ccafb1f202",((0x357b62,0x357b42,"ff1514607d00",0),(0x379f4a,0x379f1f,"ff1514607d00",0),(0x387dbe,0x387d96,"ff1514607d00",0))),
}
_DIR={"pe_bits":32,"import_directory_rva":"0x0048eca4","import_directory_size":220,"import_directory_file_offset":"0x0048dca4","import_directory_sha256":"788f7357cb31ba62895740d67e0d8a0f6bf962c467ec801a29cf9044d522fd65","descriptor_count":10,"import_record_count":342,"named_import_count":342,"ordinal_import_count":0,"kernel32_import_count":139,"descriptor_index":7,"descriptor_rva":"0x0048ed30","descriptor_file_offset":"0x0048dd30","descriptor_size":20,"descriptor_sha256":"fe01ec3285fd8be5c0857ae597b2ac4a14de3579860f5f3577a6bdbe8595bc10","original_first_thunk_rva":"0x0048ed80","timestamp":0,"forwarder_chain":0,"first_thunk_rva":"0x003d6000","library_name_rva":"0x004905fe","library_name_file_offset":"0x0048f5fe","library_nul_terminated_size":13,"library_nul_terminated_sha256":"f8efc1f27ef6c525f7fd20dcb8d65e8197e97410eced20db4d323dfbf230a2a4","metadata_only":True}

class NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetSecondCalleeStaticBoundaryError(RuntimeError): pass
def _bad(x:str)->None: raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetSecondCalleeStaticBoundaryError(x)
def _same(a:Any,b:Any)->bool:return _canonical_bytes(a)==_canonical_bytes(b)
def _ins(r:int,raw:str)->dict[str,Any]: b=bytes.fromhex(raw);return {"rva":_hex(r),"size":len(b),"sha256":hashlib.sha256(b).hexdigest()}
def _empty()->list[dict[str,Any]]:return [{"register":r,"call_rvas":[]}for r in _REGISTER_NAMES]
def _functions(f:Mapping[str,Any])->dict[int,Mapping[str,Any]]:return _atlas_functions(f)
def _edges(f:Mapping[str,Any])->dict[int,Mapping[str,Any]]:
 out={}
 for x in _array(f.get("ghidra_declared_direct_calls"),"declared edges"):
  e=_mapping(x,"declared edge"); site=_rva(e.get("instruction_rva"),"edge site")
  if site in out:_bad("duplicate declared edge")
  out[site]=e
 return out
def _compact(x:Any)->str:return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def _decode()->list[Any]:
 d,_=_decoder();d.detail=True;xs=list(d.disasm(bytes.fromhex(_RAW),_BASE+_ROOT))
 if len(xs)!=12 or b"".join(bytes(x.bytes)for x in xs)!=bytes.fromhex(_RAW):_bad("root decode")
 return xs
def _points(xs:list[Any])->list[dict[str,Any]]:
 out=[]
 for x in xs:
  _,w=x.regs_access();n={x.reg_name(q).lower()for q in w};b=bytes(x.bytes);out.append({"rva":_hex(x.address-_BASE),"size":len(b),"sha256":hashlib.sha256(b).hexdigest(),"writes_ebx":"ebx"in n,"writes_esi":"esi"in n,"writes_edi":"edi"in n,"writes_esp":"esp"in n})
 return out
def _graph(xs:list[Any]|None=None)->dict[str,Any]:
 import capstone,capstone.x86_const as x
 ys=_decode()if xs is None else xs;g=_with_edi_writes(_enhanced_cfg(ys,_BASE,(_ROOT,_SIZE),capstone,x),ys,x);g["caller_entry_rva"]=_hex(_ROOT)
 if (g.get("node_count"),g.get("edge_count"),_canonical_sha256(g))!=(12,11,_CFG):_bad("root CFG")
 return g
def _raw_binding(spec:tuple[Any,...],image:Any|None=None)->dict[str,Any]:
 site,raw,slot,name,hint,index,ilt,ilt_off,value,value_sha,iat_off,iby,iby_off,nsize,nsha=spec
 metadata={"evidence_class":"fact","library":"KERNEL32.dll","name":name,"ordinal":None,"hint":hint,"iat_rva":_hex(slot)}
 b={**_DIR,"matching_name_count":1,"matching_iat_slot_count":1,"thunk_index":index,"lookup_thunk_rva":_hex(ilt),"lookup_thunk_file_offset":_hex(ilt_off),"lookup_thunk_raw_value":_hex(int(value[6:8]+value[4:6]+value[2:4]+value[:2],16)),"lookup_thunk_sha256":value_sha,"iat_slot_rva":_hex(slot),"iat_slot_file_offset":_hex(iat_off),"iat_slot_raw_value":_hex(int(value[6:8]+value[4:6]+value[2:4]+value[:2],16)),"iat_slot_sha256":value_sha,"import_by_name_rva":_hex(iby),"import_by_name_file_offset":_hex(iby_off),"hint_and_name_nul_terminated_size":nsize,"hint_and_name_nul_terminated_sha256":nsha,"hint":hint,"name":name}
 if image is None:return b
 if image.bits!=32 or len(image.data_directories)<=1 or image.data_directories[1]!=(0x48eca4,220):_bad("import directory")
 off=image.rva_span_to_file_offset(0x48eca4,220)
 if off!=0x48dca4 or hashlib.sha256(image.data[off:off+220]).hexdigest()!=_DIR["import_directory_sha256"]:_bad("import directory bytes")
 ds=[struct.unpack_from("<IIIII",image.data,off+i*20)for i in range(11)]
 if len(ds)!=11 or any(not any(z)for z in ds[:10])or any(ds[10])or ds[7]!=(0x48ed80,0,0,0x4905fe,0x3d6000):_bad("import descriptors")
 do=image.rva_span_to_file_offset(0x48ed30,20)
 if do!=0x48dd30 or hashlib.sha256(image.data[do:do+20]).hexdigest()!=_DIR["descriptor_sha256"]:_bad("import descriptor")
 lo=image.rva_span_to_file_offset(ilt,4);io=image.rva_span_to_file_offset(slot,4);no=image.rva_span_to_file_offset(iby,nsize)
 lookup_bytes=image.data[lo:lo+4];iat_bytes=image.data[io:io+4];name_bytes=image.data[no:no+nsize]
 if (lo,io,no)!=(ilt_off,iat_off,iby_off)or lookup_bytes.hex()!=value or iat_bytes.hex()!=value or hashlib.sha256(lookup_bytes).hexdigest()!=value_sha or hashlib.sha256(iat_bytes).hexdigest()!=value_sha or hashlib.sha256(name_bytes).hexdigest()!=nsha:_bad("import thunk/name")
 if struct.unpack_from("<H",image.data,no)[0]!=hint or image.data[no+2:no+nsize]!=name.encode()+b"\0":_bad("import name")
 library_offset=image.rva_span_to_file_offset(0x4905fe,13);library_bytes=image.data[library_offset:library_offset+13]
 if library_offset!=0x48f5fe or library_bytes!=b"KERNEL32.dll\0" or hashlib.sha256(library_bytes).hexdigest()!=_DIR["library_nul_terminated_sha256"]:_bad("import library")
 matches=[q for q in image.imports()if q.get("iat_rva")==_hex(slot)]
 if len(image.imports())!=342 or sum(q.get("name")is not None for q in image.imports())!=342 or sum(q.get("ordinal")is not None for q in image.imports())or sum(q.get("library")=="KERNEL32.dll"for q in image.imports())!=139 or matches!=[metadata] or sum(q.get("name")==name for q in image.imports())!=1:_bad("import uniqueness")
 return b
def _operand(spec:tuple[Any,...],image:Any|None=None)->dict[str,Any]:
 site,raw,slot,name,hint,*_=spec
 if image is not None:
  sec=next((q for q in image.sections if q.virtual_address<=slot<q.virtual_address+q.virtual_size),None)
  if sec is None or (sec.name,sec.virtual_address,sec.characteristics,image.rva_to_file_offset(slot)is not None)!=(".rdata",0x3d6000,0x40000040,True):_bad("IAT section")
 return {"role":"typed_pe_import_iat_operand","instruction":_ins(site,raw),"operand_class":"absolute_memory","operand_index":0,"operand_access":"read","operand_va":_hex(_BASE+slot),"operand_rva":_hex(slot),"control_syntax":"x86_absolute_memory_indirect_call_ff15","section_name":".rdata","section_rva":"0x003d6000","section_characteristics":"0x40000040","section_writable":False,"file_backed":True,"pe_import_metadata":{"evidence_class":"fact","library":"KERNEL32.dll","name":name,"ordinal":None,"hint":hint,"iat_rva":_hex(slot)},"raw_pe_import_table_binding":_raw_binding(spec,image),"import_metadata_only":True,"contents_or_runtime_behavior_opaque":True}
def _native(image:Any|None=None)->dict[str,Any]:
 opaque=[]
 for spec in _SLOTS:
  site,raw,slot,*_=spec;opaque.append({"role":"opaque_absolute_memory_indirect_call","instruction":_ins(site,raw),"operand_class":"absolute_memory","operand_index":0,"operand_access":"read","operand_va":_hex(_BASE+slot),"operand_rva":_hex(slot),"control_encoding":"ff15","fallthrough_syntax_only":True,"runtime_target_opaque":True,"runtime_execution_or_behavior_opaque":True})
 return {"outgoing_direct":[],"opaque_indirect_controls":opaque,"indirect_control_partition_complete":True,"pe_address_operands":[_operand(s,image)for s in _SLOTS],"pe_address_operand_partition_complete":True,"segment_qualified_memory_syntax":[],"segment_qualified_memory_partition_complete":True,"bnd_prefixed_control_syntax":[],"bnd_prefixed_control_partition_complete":True,"opaque_interrupt_syntax":[],"opaque_interrupt_partition_complete":True,"call_r32_audit":_empty(),"register_call_partition_complete":True}
def _pre(p:Mapping[str,Any],d:Mapping[str,Any],f:Mapping[str,Any])->dict[str,Any]:
 ident=dict(_mapping(f.get("identity"),"identity"))
 if ident.get("executable_sha256")!=_EXE or not _same(p.get("build_identity"),ident)or not _same(d.get("build_identity"),ident)or p.get("analysis_kind")!=PREDECESSOR_KIND or _canonical_sha256(p)!=_PRE:_bad("predecessor")
 q=validate_native_lua_direct_call_structure(d,f)
 if q.get("status")!="structurally_verified"or q.get("evidence_sha256")!=_DIRECT:_bad("direct prerequisite")
 return {"program_facts":_source_identity(f,"pe_ghidra_program_facts",_FACTS,"facts"),"predecessor_static_boundary":_source_identity(p,PREDECESSOR_KIND,_PRE,"predecessor"),"direct_call_census":_source_identity(d,DIRECT_KIND,_DIRECT,"direct")}
def _parent(p:Mapping[str,Any])->list[dict[str,Any]]:
 rows=[dict(_mapping(q,"parent"))for q in _array(_mapping(p.get("native_calls"),"calls").get("outgoing_direct"),"outgoing")]
 hit=[q for q in rows if _rva(_mapping(q.get("instruction"),"parent instruction").get("rva"),"site")==_PARENT[0]and _rva(q.get("target_entry_rva"),"target")==_ROOT]
 if len(rows)!=2 or len(hit)!=1 or hit[0].get("control_encoding")!="e8"or not _same(hit[0].get("instruction"),_ins(_PARENT[0],_PARENT[2])):_bad("parent edge")
 return hit
def _frontier(f:Mapping[str,Any],data:bytes|None=None,image:Any|None=None,decoder:Any|None=None)->dict[str,Any]:
 fs,es=_functions(f),_edges(f); rows=[]
 for site,owner,raw,ah in _FRONTIER:
  e=es.get(site);fn=fs.get(owner)
  if e is None or fn is None or (_rva(e.get("source_entry_rva"),"source"),_rva(e.get("target_entry_rva"),"target"),_rva(e.get("target_rva"),"target rva"),atlas_record_sha256(fn))!=(owner,_ROOT,_ROOT,ah):_bad("frontier atlas join")
  rows.append({"instruction_rva":_hex(site),"instruction_size":5,"instruction_sha256":hashlib.sha256(bytes.fromhex(raw)).hexdigest(),"owner_entry_rva":_hex(owner),"owner_atlas_record_sha256":ah,"target_rva":_hex(_ROOT),"target_atlas_record_sha256":_ATLAS,"target_va":_hex(_BASE+_ROOT),"operand_class":"immediate","operand_index":0,"use_class":"direct_call","call_form":"x86_relative_near_call_e8","ghidra_declared_direct_edge":{"instruction_rva":_hex(site),"source_entry_rva":_hex(owner),"target_entry_rva":_hex(_ROOT),"target_rva":_hex(_ROOT),"target_name_sha256":hashlib.sha256(str(e.get("target_name","")).encode()).hexdigest()}})
 owners=[{"owner_entry_rva":q["owner_entry_rva"],"owner_atlas_record_sha256":q["owner_atlas_record_sha256"],"reference_count":1}for q in rows];to=[{"target_rva":_hex(_ROOT),**q}for q in owners];tr=[{"target_rva":_hex(_ROOT),"target_atlas_record_sha256":_ATLAS,"reference_count":2}];hs={"owner_partition":_compact(owners),"target_owner_partition":_compact(to),"target_reference_partition":_compact(tr)}
 if hs!=_FRONTIER_HASH:_bad("frontier partition")
 out={"scope":dict(_SCOPE),"references":rows,"target_partition":[{"target_rva":_hex(_ROOT),"target_atlas_record_sha256":_ATLAS,"reference_count":2,"owner_count":2}],"target_reference_partition":tr,"owner_partition":owners,"target_owner_partition":to,"partition_sha256":hs,"aggregates":{"reference_count":2,"target_count":1,"owner_count":2,"target_owner_count":2,"direct_call_count":2,"other_address_count":0,"memory_operand_count":0}}
 if data is None:return out
 import capstone.x86_const as x
 seen=[];tot=[0,0,0];decoder.detail=True
 for own,fn in sorted(fs.items()):
  for z in _array(fn.get("ranges"),"range"):
   a=_mapping(z,"range");st,sz=_rva(a.get("start_rva"),"start"),a.get("size");xs=_decode_range(data,image,st,sz,decoder);tot[0]+=1;tot[1]+=sz;tot[2]+=len(xs)
   for i in xs:
    for n,o in enumerate(i.operands):
     v=o.imm&0xffffffff if o.type==x.X86_OP_IMM else o.mem.disp&0xffffffff if o.type==x.X86_OP_MEM and o.mem.segment==x.X86_REG_INVALID and o.mem.base==x.X86_REG_INVALID and o.mem.index==x.X86_REG_INVALID else None
     if v==image.image_base+_ROOT:seen.append((i.address-image.image_base,own,n,bytes(i.bytes),"immediate" if o.type==x.X86_OP_IMM else "absolute_memory"))
 exp=[(s,o,0,bytes.fromhex(raw),"immediate")for s,o,raw,_ in _FRONTIER]
 if tuple(tot)!=(25490,3735718,1153814)or seen!=exp:_bad("frontier exhaustive scan")
 return out
def _slot_scan(f:Mapping[str,Any],slot:int,data:bytes|None=None,image:Any|None=None,decoder:Any|None=None)->dict[str,Any]:
 map_hash,row_hash,expected=_SLOT_SCANS[slot];fs=_functions(f); refs=[]
 for site,owner,raw,index in expected:
  fn=fs.get(owner)
  if fn is None:_bad("slot owner")
  refs.append({"instruction_rva":_hex(site),"instruction_size":len(bytes.fromhex(raw)),"instruction_sha256":hashlib.sha256(bytes.fromhex(raw)).hexdigest(),"owner_entry_rva":_hex(owner),"owner_atlas_record_sha256":atlas_record_sha256(fn),"operand_class":"absolute_memory","operand_index":index,"operand_access":"read","operand_va":_hex(_BASE+slot),"operand_rva":_hex(slot),"control_syntax":"x86_absolute_memory_indirect_call_ff15" if raw.startswith("ff15") else "x86_absolute_memory_move_8b3d"})
 # The map's supplied row-list hash is deliberately retained as an independent pin.
 if _compact(refs)!=row_hash:_bad("IAT row hash")
 result={"scope":dict(_SCOPE),"scanned_operand_va":_hex(_BASE+slot),"scanned_operand_rva":_hex(slot),"independent_map_reference_rows_canonical_sha256":map_hash,"reference_rows_canonical_sha256":row_hash,"references":refs,"aggregates":{"reference_count":len(refs),"owner_count":len({q["owner_entry_rva"]for q in refs}),"immediate_operand_count":0,"absolute_memory_operand_count":len(refs),"indirect_call_count":sum(q["control_syntax"].endswith("ff15")for q in refs)}}
 if data is None:return result
 import capstone.x86_const as x
 actual=[];tot=[0,0,0];decoder.detail=True
 for own,fn in sorted(fs.items()):
  for z in _array(fn.get("ranges"),"range"):
   a=_mapping(z,"range");st,sz=_rva(a.get("start_rva"),"start"),a.get("size");xs=_decode_range(data,image,st,sz,decoder);tot[0]+=1;tot[1]+=sz;tot[2]+=len(xs)
   for i in xs:
    for n,o in enumerate(i.operands):
     v=o.imm&0xffffffff if o.type==x.X86_OP_IMM else o.mem.disp&0xffffffff if o.type==x.X86_OP_MEM and o.mem.segment==x.X86_REG_INVALID and o.mem.base==x.X86_REG_INVALID and o.mem.index==x.X86_REG_INVALID else None
     if v==image.image_base+slot:actual.append((i.address-image.image_base,own,bytes(i.bytes),n,getattr(o,"access",0),"immediate" if o.type==x.X86_OP_IMM else "absolute_memory"))
 want=[(s,o,bytes.fromhex(raw),n,1,"absolute_memory")for s,o,raw,n in expected]
 if tuple(tot)!=(25490,3735718,1153814)or actual!=want:_bad("IAT exhaustive scan")
 return result

def _combined_exact_scans(f:Mapping[str,Any],data:bytes,image:Any,decoder:Any)->tuple[dict[str,Any],dict[int,dict[str,Any]]]:
 """Verify the target and all four IAT-slot use sets in one atlas pass."""
 import capstone.x86_const as x
 fs=_functions(f); frontier_actual=[]; slot_actual={slot:[]for slot in _SLOT_SCANS}; totals=[0,0,0]; decoder.detail=True
 va_to_slot={image.image_base+slot:slot for slot in _SLOT_SCANS}
 for owner,fn in sorted(fs.items()):
  for z in _array(fn.get("ranges"),"range"):
   a=_mapping(z,"range");start,size=_rva(a.get("start_rva"),"start"),a.get("size");instructions=_decode_range(data,image,start,size,decoder);totals[0]+=1;totals[1]+=size;totals[2]+=len(instructions)
   for instruction in instructions:
    for index,operand in enumerate(instruction.operands):
     if operand.type==x.X86_OP_IMM:value,operand_class=operand.imm&0xffffffff,"immediate"
     elif operand.type==x.X86_OP_MEM and operand.mem.segment==x.X86_REG_INVALID and operand.mem.base==x.X86_REG_INVALID and operand.mem.index==x.X86_REG_INVALID:value,operand_class=operand.mem.disp&0xffffffff,"absolute_memory"
     else:continue
     site=instruction.address-image.image_base;raw=bytes(instruction.bytes)
     if value==image.image_base+_ROOT:frontier_actual.append((site,owner,index,raw,operand_class))
     slot=va_to_slot.get(value)
     if slot is not None:slot_actual[slot].append((site,owner,raw,index,getattr(operand,"access",0),operand_class))
 if tuple(totals)!=(25490,3735718,1153814):_bad("combined exhaustive scan scope")
 frontier_expected=[(site,owner,0,bytes.fromhex(raw),"immediate")for site,owner,raw,_ in _FRONTIER]
 if frontier_actual!=frontier_expected:_bad("combined exhaustive frontier scan")
 for slot,actual in slot_actual.items():
  expected=[(site,owner,bytes.fromhex(raw),index,1,"absolute_memory")for site,owner,raw,index in _SLOT_SCANS[slot][2]]
  if actual!=expected:_bad("combined exhaustive IAT scan")
 return _frontier(f),{slot:_slot_scan(f,slot)for slot in _SLOT_SCANS}
def _evidence(p:Mapping[str,Any],d:Mapping[str,Any],f:Mapping[str,Any],*,xs:list[Any]|None=None,image:Any|None=None,frontier:Mapping[str,Any]|None=None,slot_scans:Mapping[int,Mapping[str,Any]]|None=None)->dict[str,Any]:
 req=_pre(p,d,f);ys=_decode()if xs is None else xs;raw=b"".join(bytes(i.bytes)for i in ys);fn=_functions(f).get(_ROOT)
 if raw!=bytes.fromhex(_RAW)or hashlib.sha256(raw).hexdigest()!=_BODY or fn is None or (fn.get("body_size"),fn.get("body_sha256"),atlas_record_sha256(fn))!=(_SIZE,_BODY,_ATLAS):_bad("root body")
 fr=_frontier(f)if frontier is None else dict(frontier)
 if not _same(fr,_frontier(f)):_bad("frontier receipt")
 ss={slot:_slot_scan(f,slot)for slot in _SLOT_SCANS}if slot_scans is None else {slot:dict(v)for slot,v in slot_scans.items()}
 if set(ss)!=set(_SLOT_SCANS)or any(not _same(ss[s],_slot_scan(f,s))for s in ss):_bad("slot scan receipt")
 par=_parent(p)
 if fr["references"][0]["instruction_rva"]!=par[0]["instruction"]["rva"]:_bad("parent scan join")
 return {"schema_version":SCHEMA_VERSION,"analysis_kind":ANALYSIS_KIND,"build_identity":dict(_mapping(f.get("identity"),"identity")),"program_facts":req["program_facts"],"predecessor_static_boundary":req["predecessor_static_boundary"],"direct_call_census":req["direct_call_census"],"decoder":{"name":"capstone","version":SUPPORTED_CAPSTONE_VERSION,"architecture":"x86","mode_bits":32,"sealed_instruction_count":12,"register_call_encoding_audit":[{"register":r,"encoding":f"ff{0xd0+i:02x}"}for i,r in enumerate(_REGISTER_NAMES)]},"function_body":{"role":"external_target_second_callee_opaque_static_boundary","entry_rva":_hex(_ROOT),"atlas_record_sha256":_ATLAS,"body_size":_SIZE,"body_sha256":_BODY,"range_start_rva":_hex(_ROOT),"range_size":_SIZE,"control_flow_graph_canonical_sha256":_CFG,"reviewed_points":_points(ys),"direct_lua_calls":[],"staged_lua_dispatches":[],"call_r32_audit":_empty(),"register_call_partition_complete":True,"ghidra_analysis_metadata":{"name":"___raise_securityfailure","namespace":"Global","name_source":"ANALYSIS","thunk":False,"metadata_only":True},"semantic_facts":{"relationship_defined_only":True,"analysis_labels_opaque":True,"source_semantic_names_assigned":False,"runtime_or_success_claimed":False}},"control_flow_graph":_graph(ys),"predecessor_parent_edges":par,"native_calls":_native(image),"whole_atlas_reference_scan":fr,"whole_atlas_iat_slot_use_scans":[ss[s]for s in sorted(ss)],"method":{"structural_boundary":"The receipt seals 40 decoded bytes, four FF15 fallthrough syntaxes, four PE import-directory bindings, the predecessor edge, and finite all-atlas use sets.","not_claimed":["analysis-label meaning, source identity, ABI, inputs, outputs, behavior, success, failure, or normal return","runtime reachability, invocation, ordering, frequency, state mutation, termination, security, exception, imported-function execution, meaning, or effect","contents or runtime meaning of PE-address operands or IAT slots","computed, indirect, data, un-atlased, dynamic, or Lua-side references"]},"summary":{"reviewed_target_count":1,"reviewed_target_bytes":40,"sealed_instruction_count":12,"sealed_control_flow_graph_count":1,"sealed_control_flow_graph_node_count":12,"sealed_control_flow_graph_edge_count":11,"native_direct_edge_count":0,"direct_lua_call_count":0,"staged_lua_dispatch_count":0,"call_r32_count":0,"opaque_indirect_control_count":4,"pe_address_operand_count":4,"pe_immediate_operand_count":0,"pe_absolute_memory_operand_count":4,"pe_import_metadata_count":4,"segment_qualified_memory_syntax_count":0,"bnd_prefixed_control_syntax_count":0,"opaque_interrupt_syntax_count":0,"predecessor_parent_edge_count":1,"target_reference_count":2,"target_reference_target_count":1,"target_reference_owner_count":2,"target_reference_direct_call_count":2,"target_reference_other_address_count":0,"target_reference_memory_operand_count":0,"iat_slot_use_scan_count":4,"schema_violations":0}}
def _normalize(a):
 try:return a()
 except NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetSecondCalleeStaticBoundaryError:raise
 except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassReturnHelperChainError,PEAnchorError,CsError,struct.error,OSError,TypeError,ValueError)as e:raise NativeQueryHandlerFirstCalleePointerTargetResidualDirectTargetSetCalleeExternalTargetSecondCalleeStaticBoundaryError(str(e))from e
def validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary_structure(evidence:Mapping[str,Any],predecessor:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any])->dict[str,Any]:
 def run():
  for x,n in ((evidence,"evidence"),(predecessor,"predecessor"),(direct,"direct"),(facts,"facts")):_validate_json_tree(x,n)
  want=_evidence(predecessor,direct,facts)
  if not _same(evidence,want):_bad("receipt differs")
  return {"schema_version":SCHEMA_VERSION,"analysis_kind":STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","build_identity":dict(evidence["build_identity"]),"evidence_sha256":_canonical_sha256(evidence),"summary":dict(evidence["summary"])}
 return _normalize(run)
def build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary(executable:Path,predecessor:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any],*,inventory:Mapping[str,Any])->dict[str,Any]:
 def run():
  for x,n in ((predecessor,"predecessor"),(direct,"direct"),(facts,"facts"),(inventory,"inventory")):_validate_json_tree(x,n)
  q=validate_native_lua_direct_call_census(executable,direct,facts,inventory=inventory)
  if q.get("status")!="verified"or q.get("evidence_sha256")!=_DIRECT:_bad("exact direct prerequisite")
  data,image,digest=_load_executable(executable)
  if digest!=_EXE or image.image_base!=_BASE:_bad("executable identity")
  dec,_=_decoder();dec.detail=True;xs=_decode_range(data,image,_ROOT,_SIZE,dec)
  frontier,slot_scans=_combined_exact_scans(facts,data,image,dec)
  r=_evidence(predecessor,direct,facts,xs=xs,image=image,frontier=frontier,slot_scans=slot_scans)
  if _load_executable(executable)[2]!=digest:_bad("executable changed")
  _assert_publication_safe(r);validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary_structure(r,predecessor,direct,facts);return r
 return _normalize(run)
def validate_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary(executable:Path,evidence:Mapping[str,Any],predecessor:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any],*,inventory:Mapping[str,Any])->dict[str,Any]:
 def run():
  _validate_json_tree(evidence,"evidence");r=build_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary(executable,predecessor,direct,facts,inventory=inventory)
  if not _same(evidence,r):_bad("exact evidence differs")
  return {"schema_version":SCHEMA_VERSION,"analysis_kind":VERIFICATION_KIND,"status":"verified","build_identity":dict(r["build_identity"]),"evidence_sha256":_canonical_sha256(r),"summary":dict(r["summary"])}
 return _normalize(run)
def encode_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary(value:Mapping[str,Any])->str:
 def run():_validate_json_tree(value,"encoded value");return json.dumps(_mapping(value,"encoded value"),ensure_ascii=False,allow_nan=False,sort_keys=True,indent=2)+"\n"
 return _normalize(run)
