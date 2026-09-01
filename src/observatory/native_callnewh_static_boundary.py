"""Exact, deliberately opaque boundary for Ghidra's ``__callnewh`` label.

The spelling is analysis metadata only.  This module records a finite PE
surface without assigning allocation, handler, ABI, or runtime semantics.
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
    NativeLuaClassReturnHelperChainError, _REGISTER_NAMES, _call_r32_audit, _direct_call_records,
    _canonical_bytes, _canonical_sha256, _expected_point_record, _normalized_declared_edge,
    _source_identity, _expected_reference_scan, _whole_atlas_reference_scan, _enhanced_cfg, _with_edi_writes, _point_record,
)
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError, _array, _assert_publication_safe, _atlas_functions,
    _exact_keys, _hex, _mapping, _rva, _validate_json_tree,
)
from src.observatory.native_lua_direct_calls import (
    ANALYSIS_KIND as DIRECT_CALL_ANALYSIS_KIND, SUPPORTED_CAPSTONE_VERSION,
    NativeLuaDirectCallError, _decoder, _load_executable,
    validate_native_lua_direct_call_census, validate_native_lua_direct_call_structure,
)
from src.observatory.native_operator_new_static_boundary import (
    ANALYSIS_KIND as OPERATOR_NEW_KIND, _canonical_sha256 as _operator_canonical_sha256,
)
from src.observatory.pe_anchor_map import PEAnchorError

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_callnewh_static_boundary"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
_EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_FACTS_SHA256 = "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803"
_DIRECT_SHA256 = "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608"
_OPERATOR_NEW_SHA256 = "d0cecf29ab94b05dbe8f75c2c6edd823b83c53ed06f853d4db478a76e046479f"
_ENTRY = 0x0038BBC4
_BODY_SHA256 = "d07e8825b4056293a201addd75dc71d222f4fa5055d9df0b98752c2868f10b8f"
_ATLAS_SHA256 = "9da290b981e37b2d40289ea20b7462cbaf44c8cd4d3ddfeeff21c5237158da4c"
_CFG_SHA256 = "e493f1d42b5d75a18b9cd35cb51360b573a5278cbaa7015900bd81ff0fcb9e46"

class NativeCallnewhStaticBoundaryError(RuntimeError):
    """Raised when this reviewable static boundary cannot be reproduced."""

def _point(role: str, rva: int, encoded: str) -> dict[str, Any]:
    return {"role": role, "rva": rva, "encoded": bytes.fromhex(encoded), "api": None,
            "meaning": {"operation": "decoded_instruction", "source_semantic_names_assigned": False}}

_BYTES = ((0x38BBC4,"8bff"),(0x38BBC6,"55"),(0x38BBC7,"8bec"),(0x38BBC9,"51"),
 (0x38BBCA,"a1283f8900"),(0x38BBCF,"33c5"),(0x38BBD1,"8945fc"),(0x38BBD4,"56"),
 (0x38BBD5,"e82e000000"),(0x38BBDA,"8bf0"),(0x38BBDC,"85f6"),(0x38BBDE,"7417"),
 (0x38BBE0,"ff7508"),(0x38BBE3,"8bce"),(0x38BBE5,"ff1580657d00"),(0x38BBEB,"ffd6"),
 (0x38BBED,"59"),(0x38BBEE,"85c0"),(0x38BBF0,"7405"),(0x38BBF2,"33c0"),
 (0x38BBF4,"40"),(0x38BBF5,"eb02"),(0x38BBF7,"33c0"),(0x38BBF9,"8b4dfc"),
 (0x38BBFC,"33cd"),(0x38BBFE,"5e"),(0x38BBFF,"e8c6b8fcff"),(0x38BC04,"8be5"),
 (0x38BC06,"5d"),(0x38BC07,"c3"))
_FUNCTION = {"role":"analysis_labeled_callnewh_static_boundary", "entry_rva":_ENTRY,
 "body_size":68, "body_sha256":_BODY_SHA256, "cfg_canonical_sha256":_CFG_SHA256,
 "direct_calls":[], "staged_dispatches":[], "call_r32":{"ESI":[0x38BBEB]},
 "points":[_point(f"instruction_{i:02d}", rva, raw) for i,(rva,raw) in enumerate(_BYTES)],
 "semantic_facts":{"analysis_label":"__callnewh", "analysis_label_only":True,
                   "source_semantic_names_assigned":False, "runtime_or_success_claimed":False}}
_DIRECT_EDGES = ((0x38BBD5,"e82e000000",0x38BC08),(0x38BBFF,"e8c6b8fcff",0x3574CA))
_INDIRECT_EDGES = ((0x38BBE5,"ff1580657d00","x86_indirect_memory_call","absolute_memory","0x007d6580"),
                   (0x38BBEB,"ffd6","x86_register_call_r32","register","ESI"))
_METHOD = {"structural_boundary":"PE-free validation reconstructs canonical-pinned prerequisites, all 30 decoded instructions, CFG receipt, declared direct native edges, indirect call syntax, and all target E8 references. Exact bytes and the PE-wide traversal require the sealed executable.",
 "not_claimed":["allocation, new-handler, ABI, success, ownership, lifetime, or size meaning", "runtime reachability, invocation, order, frequency, normal return, or source identity", "behavior or identity of direct and indirect callees", "computed, indirect target resolution, data, un-atlased, or Lua-side references"]}

def _same(a: Any,b: Any)->bool: return _canonical_bytes(a)==_canonical_bytes(b)
def _build_records(data:bytes,image:Any,decoder:Any,facts:Mapping[str,Any],direct:Mapping[str,Any])->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    """Deliberately avoid generic staged-dispatch interpretation for this opaque body."""
    import capstone
    import capstone.x86_const as x86
    from src.observatory.native_lua_cclosure_setfield_publications import _decode_range
    decoder.detail=True; function=_atlas_functions(facts).get(_ENTRY)
    if function is None or function.get("thunk") is not False or function.get("body_size")!=68 or function.get("body_sha256")!=_BODY_SHA256:raise NativeCallnewhStaticBoundaryError("target atlas body differs")
    instructions=_decode_range(data,image,_ENTRY,68,decoder); encoded=b"".join(bytes(item.bytes) for item in instructions)
    if hashlib.sha256(encoded).hexdigest()!=_BODY_SHA256:raise NativeCallnewhStaticBoundaryError("target PE body differs")
    graph=_with_edi_writes(_enhanced_cfg(instructions,image.image_base,(_ENTRY,68),capstone,x86),instructions,x86); graph["caller_entry_rva"]=_hex(_ENTRY)
    if _canonical_sha256(graph)!=_CFG_SHA256:raise NativeCallnewhStaticBoundaryError("target CFG differs")
    by_rva={item.address-image.image_base:item for item in instructions}; points=[]
    for spec in _FUNCTION["points"]:
        item=by_rva.get(spec["rva"])
        if item is None:raise NativeCallnewhStaticBoundaryError("sealed instruction missing")
        points.append(_point_record(item,image.image_base,spec))
    body={"role":_FUNCTION["role"],"entry_rva":_hex(_ENTRY),"atlas_record_sha256":_ATLAS_SHA256,"body_size":68,"body_sha256":_BODY_SHA256,"range_start_rva":_hex(_ENTRY),"range_size":68,"control_flow_graph_canonical_sha256":_CFG_SHA256,"reviewed_points":points,"direct_lua_calls":_direct_call_records(_FUNCTION,direct),"staged_lua_dispatches":[],"call_r32_audit":_call_r32_audit(instructions,_FUNCTION),"register_call_partition_complete":True,"semantic_facts":dict(_FUNCTION["semantic_facts"])}
    return [body],[graph]
def _facts_identity(facts: Mapping[str,Any])->dict[str,Any]:
    base=_source_identity(facts,"pe_ghidra_program_facts",_FACTS_SHA256,"program facts"); summary=_mapping(facts.get("summary"),"facts summary")
    return {**base,"function_count":summary.get("function_count"),"body_range_count":summary.get("body_range_count"),"function_body_bytes":summary.get("function_body_bytes")}
def _operator_identity(value: Mapping[str,Any])->dict[str,Any]:
    result=_source_identity(value,OPERATOR_NEW_KIND,_OPERATOR_NEW_SHA256,"operator-new boundary")
    if _operator_canonical_sha256(value)!=_OPERATOR_NEW_SHA256: raise NativeCallnewhStaticBoundaryError("operator-new canonical receipt differs")
    return result
def _preflight(operator: Mapping[str,Any],direct: Mapping[str,Any],facts: Mapping[str,Any])->tuple[dict[str,Any],dict[str,Any],dict[str,Any]]:
    identity=_mapping(facts.get("identity"),"facts identity")
    if identity.get("executable_sha256")!=_EXE_SHA256: raise NativeCallnewhStaticBoundaryError("program facts profile differs")
    if not _same(operator.get("build_identity"),dict(identity)) or not _same(direct.get("build_identity"),dict(identity)): raise NativeCallnewhStaticBoundaryError("prerequisite build identity differs")
    return _facts_identity(facts), _source_identity(direct,DIRECT_CALL_ANALYSIS_KIND,_DIRECT_SHA256,"direct-call census"), _operator_identity(operator)
def _profile(facts: Mapping[str,Any])->dict[str,Any]:
    refs=[]
    for raw in _array(facts.get("ghidra_declared_direct_calls"),"declared calls"):
        edge=_mapping(raw,"edge")
        if _rva(edge.get("target_entry_rva"),"target") == _ENTRY:
            site,target,owner=(_rva(edge.get(k),k) for k in ("instruction_rva","target_rva","source_entry_rva"))
            if target!=_ENTRY: raise NativeCallnewhStaticBoundaryError("declared target differs")
            refs.append({"instruction_rva":site,"owner_entry_rva":owner,"target_rva":target,"encoded":(b"\xe8"+int(target-(site+5)).to_bytes(4,"little",signed=True)).hex(),"operand_index":0})
    refs.sort(key=lambda item:item["instruction_rva"])
    if len(refs)!=4 or len({item["owner_entry_rva"] for item in refs})!=4: raise NativeCallnewhStaticBoundaryError("callnewh declared reference profile differs")
    return {"executable_sha256":_EXE_SHA256,"functions":[_FUNCTION],"literals":[],"native_edges":[],"target_references":refs}
def _reference_scan(scan: Mapping[str,Any])->dict[str,Any]:
    result=dict(_mapping(scan,"scan")); refs=_array(result.get("references"),"references"); aggregate=dict(_mapping(result.get("aggregates"),"aggregates")); aggregate.pop("returned_callback_reference_count",None); aggregate.pop("alternate_owner_reference_count",None); result["aggregates"]=aggregate
    if len(refs)!=4 or aggregate!={"reference_count":4,"direct_call_count":4,"comparison_count":0,"other_address_count":0,"memory_operand_count":0,"owner_count":4}: raise NativeCallnewhStaticBoundaryError("reference partition differs")
    for raw in refs:
        item=_mapping(raw,"reference")
        if (item.get("instruction_size"),item.get("operand_index"),item.get("operand_class"),item.get("use_class"),item.get("call_form")) != (5,0,"immediate","direct_call","x86_relative_near_call_e8") or item.get("ghidra_declared_direct_edge") is None: raise NativeCallnewhStaticBoundaryError("reference is not declared E8")
        if type(item.get("owner_entry_rva")) is not str or type(item.get("owner_atlas_record_sha256")) is not str: raise NativeCallnewhStaticBoundaryError("reference lacks owner identity")
    owners={item["owner_entry_rva"]:item["owner_atlas_record_sha256"] for item in refs}
    if len(owners)!=4: raise NativeCallnewhStaticBoundaryError("owner partition differs")
    supplied=_array(result.get("owner_partition",[]),"owner partition")
    if supplied:
        for item in supplied:_exact_keys(_mapping(item,"owner partition item"),{"owner_entry_rva","owner_atlas_record_sha256","reference_count"},"owner partition item")
    result["owner_partition"]=[{"owner_entry_rva":owner,"owner_atlas_record_sha256":digest,"reference_count":1} for owner,digest in sorted(owners.items())]
    return result
def _expected_scan(facts: Mapping[str,Any],direct: Mapping[str,Any])->dict[str,Any]: return _reference_scan(_expected_reference_scan(facts,direct,_profile(facts)))
def _native_edges(facts: Mapping[str,Any], image: Any | None = None)->dict[str,list[dict[str,Any]]]:
    functions=_atlas_functions(facts); source=functions.get(_ENTRY)
    if source is None or atlas_record_sha256(source)!=_ATLAS_SHA256 or source.get("body_size")!=68 or source.get("body_sha256")!=_BODY_SHA256: raise NativeCallnewhStaticBoundaryError("source atlas identity differs")
    declared={_rva(_mapping(raw,"edge").get("instruction_rva"),"site"):_mapping(raw,"edge") for raw in _array(facts.get("ghidra_declared_direct_calls"),"edges")}; direct=[]
    for site,encoded,target in _DIRECT_EDGES:
        edge=declared.get(site); callee=functions.get(target)
        if edge is None or callee is None or _rva(edge.get("source_entry_rva"),"source")!=_ENTRY or _rva(edge.get("target_entry_rva"),"target")!=target: raise NativeCallnewhStaticBoundaryError("direct native edge differs")
        direct.append({"role":"opaque_native_direct_edge","source_entry_rva":_hex(_ENTRY),"source_atlas_record_sha256":_ATLAS_SHA256,"source_body_size":68,"source_body_sha256":_BODY_SHA256,"instruction":{"rva":_hex(site),"size":5,"sha256":hashlib.sha256(bytes.fromhex(encoded)).hexdigest()},"target_entry_rva":_hex(target),"target_rva":_hex(target),"target_atlas_record_sha256":atlas_record_sha256(callee),"target_body_size":callee.get("body_size"),"target_body_sha256":callee.get("body_sha256"),"ghidra_declared_direct_edge":_normalized_declared_edge(edge),"callee_behavior_opaque":True})
    indirect=[]
    for site,encoded,form,operand_kind,operand in _INDIRECT_EDGES:
        record={"role":"opaque_native_indirect_call_syntax","instruction":{"rva":_hex(site),"size":len(bytes.fromhex(encoded)),"sha256":hashlib.sha256(bytes.fromhex(encoded)).hexdigest()},"call_form":form,"operand_kind":operand_kind,"operand":operand,"callee_behavior_opaque":True,"target_resolved":False}
        if site==0x38BBE5: record.update({"operand_va":"0x007d6580","operand_rva":"0x003d6580","section_name":".rdata","section_characteristics":"0x40000040","section_writable":False})
        indirect.append(record)
    result={"direct":direct,"indirect":indirect,"absolute_memory_reads":[{"role":"opaque_absolute_memory_read_syntax","instruction":{"rva":"0x0038bbca","size":5,"sha256":hashlib.sha256(bytes.fromhex("a1283f8900")).hexdigest()},"operand_kind":"absolute_memory","operand_va":"0x00893f28","operand_rva":"0x00493f28","section_name":".data","section_characteristics":"0xc0000040","section_writable":True,"value_or_behavior_opaque":True}]}
    if image is not None:
        for record in (result["indirect"][0],result["absolute_memory_reads"][0]):
            section=image.section_for_offset(image.rva_to_file_offset(_rva(record["operand_rva"],"operand RVA")))
            if section is None or (section.name,_hex(section.characteristics),bool(section.characteristics & 0x80000000)) != (record["section_name"],record["section_characteristics"],record["section_writable"]): raise NativeCallnewhStaticBoundaryError("absolute-memory section identity differs")
    return result
def _operator_predecessor(operator: Mapping[str,Any],scan:Mapping[str,Any])->dict[str,Any]:
    matches=[dict(_mapping(raw,"operator edge")) for raw in _array(operator.get("native_edges"),"operator edges") if _rva(_mapping(raw,"edge").get("source_entry_rva"),"source")==0x3574DB and _rva(_mapping(raw,"edge").get("target_entry_rva"),"target")==_ENTRY and _rva(_mapping(_mapping(raw,"edge").get("instruction"),"instruction").get("rva"),"site")==0x3574E3]
    if len(matches)!=1: raise NativeCallnewhStaticBoundaryError("operator-new edge join differs")
    edge=matches[0]; refs=[_mapping(raw,"reference") for raw in _array(scan.get("references"),"references") if _rva(_mapping(raw,"reference").get("instruction_rva"),"site")==0x3574E3]
    if len(refs)!=1: raise NativeCallnewhStaticBoundaryError("PE reference scan lacks operator-new edge")
    ref=refs[0]; instruction=_mapping(edge.get("instruction"),"instruction")
    if ref.get("owner_entry_rva")!="0x003574db" or ref.get("use_class")!="direct_call" or ref.get("call_form")!="x86_relative_near_call_e8" or (ref.get("instruction_size"),ref.get("instruction_sha256")) != (instruction.get("size"),instruction.get("sha256")) or ref.get("owner_atlas_record_sha256")!=edge.get("source_atlas_record_sha256") or ref.get("target_atlas_record_sha256")!=edge.get("target_atlas_record_sha256") or not _same(ref.get("ghidra_declared_direct_edge"),edge.get("ghidra_declared_direct_edge")): raise NativeCallnewhStaticBoundaryError("operator-new edge and reference scan differ")
    return edge
def _decoder_contract()->dict[str,Any]: return {"name":"capstone","version":SUPPORTED_CAPSTONE_VERSION,"architecture":"x86","mode_bits":32,"sealed_instruction_count":30,"register_call_encoding_audit":[{"register":r,"encoding":f"ff{0xd0+i:02x}"} for i,r in enumerate(_REGISTER_NAMES)]}
def _expected_body(facts:Mapping[str,Any])->dict[str,Any]:
    if _atlas_functions(facts).get(_ENTRY) is None: raise NativeCallnewhStaticBoundaryError("target absent from atlas")
    return {"role":_FUNCTION["role"],"entry_rva":_hex(_ENTRY),"atlas_record_sha256":_ATLAS_SHA256,"body_size":68,"body_sha256":_BODY_SHA256,"range_start_rva":_hex(_ENTRY),"range_size":68,"control_flow_graph_canonical_sha256":_CFG_SHA256,"reviewed_points":[_expected_point_record(x) for x in _FUNCTION["points"]],"direct_lua_calls":[],"staged_lua_dispatches":[],"call_r32_audit":[{"register":r,"call_rvas":["0x0038bbeb"] if r=="ESI" else []} for r in _REGISTER_NAMES],"register_call_partition_complete":True,"semantic_facts":_FUNCTION["semantic_facts"]}
def _summary(result:Mapping[str,Any])->dict[str,Any]:
    scan=_mapping(result.get("whole_atlas_reference_scan"),"scan")
    return {"reviewed_callnewh_count":1,"reviewed_callnewh_bytes":68,"sealed_instruction_count":30,"sealed_control_flow_graph_count":1,"sealed_control_flow_graph_node_count":30,"sealed_control_flow_graph_edge_count":31,"direct_lua_call_count":0,"staged_lua_dispatch_count":0,"call_r32_count":1,"literal_count":0,"native_direct_edge_count":2,"native_indirect_call_syntax_count":2,"absolute_memory_read_syntax_count":1,"operator_new_predecessor_edge_count":1,"target_reference_count":len(_array(scan.get("references"),"refs")),"target_reference_owner_count":4,"schema_violations":0}
def _build(executable:Path,operator:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any],*,inventory:Mapping[str,Any])->dict[str,Any]:
    for value,label in ((operator,"operator-new"),(direct,"direct calls"),(facts,"facts"),(inventory,"inventory")):_validate_json_tree(value,label)
    receipt=validate_native_lua_direct_call_census(executable,direct,facts,inventory=inventory)
    if receipt.get("status")!="verified" or receipt.get("evidence_sha256")!=_DIRECT_SHA256: raise NativeCallnewhStaticBoundaryError("direct-call prerequisite differs")
    atlas,direct_identity,operator_identity=_preflight(operator,direct,facts); data,image,digest=_load_executable(executable)
    if digest!=_EXE_SHA256: raise NativeCallnewhStaticBoundaryError("executable identity differs")
    decoder,_=_decoder(); bodies,graphs=_build_records(data,image,decoder,facts,direct); scan=_reference_scan(_whole_atlas_reference_scan(data,image,decoder,facts,direct,_profile(facts)))
    result={"schema_version":SCHEMA_VERSION,"analysis_kind":ANALYSIS_KIND,"build_identity":dict(_mapping(facts.get("identity"),"identity")),"atlas":atlas,"direct_call_census":direct_identity,"operator_new_static_boundary":operator_identity,"operator_new_callnewh_edge":_operator_predecessor(operator,scan),"decoder":_decoder_contract(),"function_bodies":bodies,"control_flow_graphs":graphs,"native_calls":_native_edges(facts,image),"whole_atlas_reference_scan":scan,"method":_METHOD}; result["summary"]=_summary(result); _assert_publication_safe(result)
    if _load_executable(executable)[2]!=digest: raise NativeCallnewhStaticBoundaryError("executable changed during rebuild")
    validate_native_callnewh_static_boundary_structure(result,operator,direct,facts); return result
def build_native_callnewh_static_boundary(executable:Path,operator_new_static_boundary:Mapping[str,Any],direct_calls:Mapping[str,Any],program_facts:Mapping[str,Any],*,inventory:Mapping[str,Any])->dict[str,Any]:
    try:return _build(executable,operator_new_static_boundary,direct_calls,program_facts,inventory=inventory)
    except NativeCallnewhStaticBoundaryError:raise
    except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassFactoryChainError,NativeLuaClassReturnHelperChainError,PEAnchorError,OSError) as exc: raise NativeCallnewhStaticBoundaryError(str(exc)) from exc
def validate_native_callnewh_static_boundary_structure(evidence:Mapping[str,Any],operator:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any])->dict[str,Any]:
    try:
        for value,label in ((evidence,"evidence"),(operator,"operator-new"),(direct,"direct"),(facts,"facts")):_validate_json_tree(value,label)
        receipt=validate_native_lua_direct_call_structure(direct,facts)
        if receipt.get("status")!="structurally_verified" or receipt.get("evidence_sha256")!=_DIRECT_SHA256: raise NativeCallnewhStaticBoundaryError("direct structural prerequisite differs")
        atlas,direct_identity,operator_identity=_preflight(operator,direct,facts); evidence=_mapping(evidence,"evidence")
        _exact_keys(evidence,{"schema_version","analysis_kind","build_identity","atlas","direct_call_census","operator_new_static_boundary","operator_new_callnewh_edge","decoder","function_bodies","control_flow_graphs","native_calls","whole_atlas_reference_scan","method","summary"},"evidence")
        if type(evidence.get("schema_version")) is not int or evidence.get("schema_version")!=SCHEMA_VERSION or evidence.get("analysis_kind")!=ANALYSIS_KIND: raise NativeCallnewhStaticBoundaryError("schema differs")
        if not all((_same(evidence.get("build_identity"),dict(_mapping(facts.get("identity"),"identity"))),_same(evidence.get("atlas"),atlas),_same(evidence.get("direct_call_census"),direct_identity),_same(evidence.get("operator_new_static_boundary"),operator_identity),_same(evidence.get("decoder"),_decoder_contract()),_same(evidence.get("method"),_METHOD))):raise NativeCallnewhStaticBoundaryError("pinned prerequisite differs")
        bodies=_array(evidence.get("function_bodies"),"bodies")
        if len(bodies)!=1 or not _same(bodies[0],_expected_body(facts)):raise NativeCallnewhStaticBoundaryError("body differs")
        graph_map=_validated_graphs({"control_flow_graphs":evidence.get("control_flow_graphs")},_atlas_functions(facts))
        if set(graph_map)!={_ENTRY} or _canonical_sha256(graph_map[_ENTRY][0])!=_CFG_SHA256 or graph_map[_ENTRY][0].get("node_count")!=30 or graph_map[_ENTRY][0].get("edge_count")!=31:raise NativeCallnewhStaticBoundaryError("CFG differs")
        for point in _array(_mapping(bodies[0],"body").get("reviewed_points"),"points"):
            node=graph_map[_ENTRY][1].get(_rva(_mapping(point,"point").get("rva"),"rva"))
            if node is None or (node.get("size"),node.get("sha256")) != (_mapping(point,"point").get("size"),_mapping(point,"point").get("sha256")):raise NativeCallnewhStaticBoundaryError("point does not join CFG")
        scan=_reference_scan(_mapping(evidence.get("whole_atlas_reference_scan"),"scan"))
        if not _same(scan,_expected_scan(facts,direct)) or not _same(evidence.get("operator_new_callnewh_edge"),_operator_predecessor(operator,scan)) or not _same(evidence.get("native_calls"),_native_edges(facts)) or not _same(evidence.get("summary"),_summary(evidence)):raise NativeCallnewhStaticBoundaryError("edge, reference, or summary differs")
        _assert_publication_safe(evidence); return {"schema_version":SCHEMA_VERSION,"analysis_kind":STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","build_identity":dict(evidence["build_identity"]),"evidence_sha256":_canonical_sha256(evidence),"summary":dict(evidence["summary"])}
    except NativeCallnewhStaticBoundaryError:raise
    except (NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaClassFactoryChainError,NativeLuaClassReturnHelperChainError) as exc:raise NativeCallnewhStaticBoundaryError(str(exc)) from exc
def validate_native_callnewh_static_boundary(executable:Path,evidence:Mapping[str,Any],operator:Mapping[str,Any],direct:Mapping[str,Any],facts:Mapping[str,Any],*,inventory:Mapping[str,Any])->dict[str,Any]:
    rebuilt=build_native_callnewh_static_boundary(executable,operator,direct,facts,inventory=inventory)
    if not _same(evidence,rebuilt):raise NativeCallnewhStaticBoundaryError("evidence differs from rebuild")
    return {"schema_version":SCHEMA_VERSION,"analysis_kind":VERIFICATION_KIND,"status":"verified","build_identity":dict(rebuilt["build_identity"]),"evidence_sha256":_canonical_sha256(rebuilt),"summary":dict(rebuilt["summary"])}
def encode_native_callnewh_static_boundary(value:Mapping[str,Any])->str:
    try:_validate_json_tree(value); return json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2,sort_keys=True)+"\n"
    except NativeLuaCClosurePublicationError as exc:raise NativeCallnewhStaticBoundaryError(str(exc)) from exc
