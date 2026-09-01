"""Exact and adversarial tests for the analysis-only ``__callnewh`` boundary."""
from __future__ import annotations
import copy
import os
import threading
import hashlib
import json
from pathlib import Path
from typing import Any
import pytest
from scripts import itb_native_callnewh_static_boundary as cli
from src.observatory import native_callnewh_static_boundary as helper
from src.observatory.native_callnewh_static_boundary import NativeCallnewhStaticBoundaryError

ROOT=Path(__file__).resolve().parents[1]; PROGRAMS=ROOT/"data"/"observatory"/"programs"; INVENTORIES=ROOT/"data"/"observatory"/"inventories"
PREFIX="windows_build_13725832_31fe35265598_"; EXE=Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
RAW_SHA256="5b1651f4b17b3d6531b71a19c828ab4700cebb19f444c5db6d694e5534793449"; CANONICAL_SHA256="27f7495174094b3d6dca6acd6e9975a4dfa7d349f3bf974d40c3f5acd0b4eb45"; EXE_SHA256="31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
def _read(path:Path)->dict[str,Any]:return json.loads(path.read_text(encoding="utf-8"))
@pytest.fixture(scope="module")
def values()->dict[str,Any]:
    paths={"inventory":INVENTORIES/(PREFIX+"full_decompile_baseline_20260830.json"),"facts":PROGRAMS/(PREFIX+"program_facts.json"),"direct":PROGRAMS/(PREFIX+"native_lua_direct_call_census.json"),"operator":PROGRAMS/(PREFIX+"native_operator_new_static_boundary.json"),"evidence":PROGRAMS/(PREFIX+"native_callnewh_static_boundary.json")}
    if any(not path.is_file() for path in paths.values()):pytest.skip("callnewh prerequisites unavailable")
    result={name:_read(path) for name,path in paths.items()};result["paths"]=paths;result["target"]=helper._atlas_functions(result["facts"])[helper._ENTRY];return result
def _common(v):return v["operator"],v["direct"],v["facts"]
def _structure(v,e=None):return helper.validate_native_callnewh_static_boundary_structure(v["evidence"] if e is None else e,*_common(v))
def _fast(monkeypatch,v,e):
    monkeypatch.setattr(helper,"_validate_json_tree",lambda *a,**k:None);monkeypatch.setattr(helper,"_assert_publication_safe",lambda *a,**k:None)
    monkeypatch.setattr(helper,"validate_native_lua_direct_call_structure",lambda *a,**k:{"status":"structurally_verified","evidence_sha256":helper._DIRECT_SHA256})
    monkeypatch.setattr(helper,"_atlas_functions",lambda *a,**k:{helper._ENTRY:v["target"]})
    monkeypatch.setattr(helper,"_native_edges",lambda *a,**k:copy.deepcopy(v["evidence"]["native_calls"]))
    monkeypatch.setattr(helper,"_expected_scan",lambda *a,**k:copy.deepcopy(v["evidence"]["whole_atlas_reference_scan"]))
    return _structure(v,e)
def _rejects(v,monkeypatch,e):
    with pytest.raises(NativeCallnewhStaticBoundaryError):_fast(monkeypatch,v,e)
def _changed(x):
    if isinstance(x,bool):return not x
    if isinstance(x,int):return x+1
    if isinstance(x,str):return "changed"
    if isinstance(x,list):return [] if x else ["changed"]
    if isinstance(x,dict):return {}
    return "changed"
def _replace(value,path,replacement):
    if not path:return replacement
    output=dict(value) if isinstance(value,dict) else list(value);output[path[0]]=_replace(value[path[0]],path[1:],replacement);return output
def _add(value,path,addition):
    if len(path)==1:output=dict(value);output[path[0]]=addition;return output
    output=dict(value) if isinstance(value,dict) else list(value);output[path[0]]=_add(value[path[0]],path[1:],addition);return output

def test_committed_encoding_receipts_and_structure(values):
    raw=values["paths"]["evidence"].read_bytes();assert raw==helper.encode_native_callnewh_static_boundary(values["evidence"]).encode("utf-8")
    assert hashlib.sha256(raw).hexdigest()==RAW_SHA256;assert helper._canonical_sha256(values["evidence"])==CANONICAL_SHA256
    receipt=_structure(values);assert receipt["status"]=="structurally_verified" and receipt["evidence_sha256"]==CANONICAL_SHA256
    assert values["evidence"]["summary"]=={"reviewed_callnewh_count":1,"reviewed_callnewh_bytes":68,"sealed_instruction_count":30,"sealed_control_flow_graph_count":1,"sealed_control_flow_graph_node_count":30,"sealed_control_flow_graph_edge_count":31,"direct_lua_call_count":0,"staged_lua_dispatch_count":0,"call_r32_count":1,"literal_count":0,"native_direct_edge_count":2,"native_indirect_call_syntax_count":2,"absolute_memory_read_syntax_count":1,"operator_new_predecessor_edge_count":1,"target_reference_count":4,"target_reference_owner_count":4,"schema_violations":0}
def test_exact_body_calls_predecessor_and_nonclaims(values):
    e=values["evidence"];body=e["function_bodies"][0];graph=e["control_flow_graphs"][0]
    assert (body["entry_rva"],body["body_size"],body["body_sha256"],body["control_flow_graph_canonical_sha256"])==("0x0038bbc4",68,"d07e8825b4056293a201addd75dc71d222f4fa5055d9df0b98752c2868f10b8f","e493f1d42b5d75a18b9cd35cb51360b573a5278cbaa7015900bd81ff0fcb9e46")
    assert len(body["reviewed_points"])==30 and (graph["node_count"],graph["edge_count"])==(30,31)
    assert body["direct_lua_calls"]==[] and body["staged_lua_dispatches"]==[] and body["call_r32_audit"]==[{"register":r,"call_rvas":["0x0038bbeb"] if r=="ESI" else []} for r in helper._REGISTER_NAMES]
    calls=e["native_calls"];assert [(x["instruction"]["rva"],x["target_entry_rva"]) for x in calls["direct"]]==[("0x0038bbd5","0x0038bc08"),("0x0038bbff","0x003574ca")]
    assert [(x["instruction"]["rva"],x["call_form"],x["target_resolved"]) for x in calls["indirect"]]==[("0x0038bbe5","x86_indirect_memory_call",False),("0x0038bbeb","x86_register_call_r32",False)]
    indirect=calls["indirect"][0];assert (indirect["operand_va"],indirect["operand_rva"],indirect["section_name"],indirect["section_characteristics"],indirect["section_writable"])==("0x007d6580","0x003d6580",".rdata","0x40000040",False)
    read=calls["absolute_memory_reads"][0];assert (read["instruction"]["rva"],read["operand_va"],read["operand_rva"],read["section_name"],read["section_characteristics"],read["section_writable"])==("0x0038bbca","0x00893f28","0x00493f28",".data","0xc0000040",True)
    edge=e["operator_new_callnewh_edge"];assert (edge["source_entry_rva"],edge["instruction"]["rva"],edge["target_entry_rva"])==("0x003574db","0x003574e3","0x0038bbc4")
    assert len(e["whole_atlas_reference_scan"]["references"])==4 and len(e["whole_atlas_reference_scan"]["owner_partition"])==4
    for token in ("allocation","handler","ABI","success","ownership","lifetime","runtime","identity","computed","indirect","Lua-side"):assert any(token.lower() in item.lower() for item in e["method"]["not_claimed"])
def test_committed_exact_rebuild(values):
    if not EXE.is_file() or hashlib.sha256(EXE.read_bytes()).hexdigest()!=EXE_SHA256:pytest.skip("sealed executable unavailable")
    rebuilt=helper.build_native_callnewh_static_boundary(EXE,*_common(values),inventory=values["inventory"]);assert rebuilt==values["evidence"]
    assert helper.validate_native_callnewh_static_boundary(EXE,values["evidence"],*_common(values),inventory=values["inventory"])["status"]=="verified"
@pytest.mark.parametrize("key",["schema_version","analysis_kind","build_identity","atlas","direct_call_census","operator_new_static_boundary","operator_new_callnewh_edge","decoder","function_bodies","control_flow_graphs","native_calls","whole_atlas_reference_scan","method","summary"])
def test_structure_rejects_every_top_level_category(values,monkeypatch,key):_rejects(values,monkeypatch,_replace(values["evidence"],(key,),_changed(values["evidence"][key])))
@pytest.mark.parametrize("path",[("unexpected",),("function_bodies",0,"unexpected"),("native_calls","indirect",0,"unexpected"),("whole_atlas_reference_scan","references",0,"unexpected"),("whole_atlas_reference_scan","owner_partition",0,"unexpected"),("operator_new_callnewh_edge","instruction","unexpected")])
def test_structure_rejects_unknown_retained_keys(values,monkeypatch,path):_rejects(values,monkeypatch,_add(values["evidence"],path,True))
@pytest.mark.parametrize("value",[None,False,[],{}])
def test_structure_rejects_malformed_reference_owner(values,monkeypatch,value):_rejects(values,monkeypatch,_replace(values["evidence"],("whole_atlas_reference_scan","references",0,"owner_entry_rva"),value))
@pytest.mark.parametrize("path",[("native_calls","indirect",0,"instruction","rva"),("native_calls","indirect",0,"call_form"),("native_calls","indirect",0,"operand_va"),("native_calls","indirect",0,"section_characteristics"),("native_calls","absolute_memory_reads",0,"operand_rva"),("native_calls","absolute_memory_reads",0,"section_writable")])
def test_structure_rejects_indirect_and_absolute_syntax_tamper(values,monkeypatch,path):
    cursor=values["evidence"]
    for key in path:cursor=cursor[key]
    _rejects(values,monkeypatch,_replace(values["evidence"],path,_changed(cursor)))
def test_cli_publisher_is_immutable(tmp_path,monkeypatch,values):
    info=tmp_path.stat();monkeypatch.setattr(cli,"_prepare_output_root",lambda:(tmp_path,tmp_path,info));monkeypatch.setattr(cli,"_recheck_output_root",lambda *a:None)
    output=tmp_path/"evidence.json";rendered=helper.encode_native_callnewh_static_boundary(values["evidence"]);cli._write_immutably(output,rendered,values["evidence"]);cli._write_immutably(output,rendered,values["evidence"]);output.write_text(rendered+" ",encoding="utf-8")
    with pytest.raises(NativeCallnewhStaticBoundaryError,match="refusing to overwrite"):cli._write_immutably(output,rendered,values["evidence"])
def test_cli_normalizes_inherited_output_root_error(tmp_path,monkeypatch,values):
    def reject_root():raise cli.NativeLuaPropertyFactoryChainError("synthetic root rejection")
    monkeypatch.setattr(cli,"_prepare_output_root",reject_root)
    rendered=helper.encode_native_callnewh_static_boundary(values["evidence"])
    with pytest.raises(NativeCallnewhStaticBoundaryError,match="synthetic root rejection"):
        cli._write_immutably(tmp_path/"evidence.json",rendered,values["evidence"])
def test_cli_lock_blocks_cooperating_writer_until_final_validation(tmp_path,monkeypatch,values):
    info=tmp_path.stat();monkeypatch.setattr(cli,"_prepare_output_root",lambda:(tmp_path,tmp_path,info));monkeypatch.setattr(cli,"_recheck_output_root",lambda *a:None)
    output=tmp_path/"evidence.json";rendered=helper.encode_native_callnewh_static_boundary(values["evidence"]);output.write_bytes(rendered.encode("utf-8")); attempts=[]; original=cli._read_locked_json_document
    def writer():
        if os.name=="nt":
            try:
                with output.open("ab") as stream:stream.write(b" ")
            except OSError:attempts.append("blocked")
            else:attempts.append("mutated")
            return
        import fcntl
        descriptor=os.open(output,os.O_WRONLY|os.O_APPEND)
        try:
            try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:attempts.append("blocked")
            else:os.write(descriptor,b" ");attempts.append("mutated");fcntl.flock(descriptor,fcntl.LOCK_UN)
        finally:os.close(descriptor)
    def read_contended(descriptor,label):
        result=original(descriptor,label); contender=threading.Thread(target=writer);contender.start();contender.join(timeout=5);assert not contender.is_alive();return result
    monkeypatch.setattr(cli,"_read_locked_json_document",read_contended);cli._write_immutably(output,rendered,values["evidence"])
    assert attempts==["blocked"] and output.read_bytes()==rendered.encode("utf-8")
def test_cli_preserves_published_path_after_final_validation_failure(tmp_path,monkeypatch,values):
    info=tmp_path.stat();monkeypatch.setattr(cli,"_prepare_output_root",lambda:(tmp_path,tmp_path,info));monkeypatch.setattr(cli,"_recheck_output_root",lambda *a:None)
    output=tmp_path/"evidence.json";rendered=helper.encode_native_callnewh_static_boundary(values["evidence"]);output.write_bytes(rendered.encode("utf-8"))
    original=cli._read_locked_json_document
    def corrupt(descriptor,label):
        value,payload=original(descriptor,label);return value,payload+b" "
    monkeypatch.setattr(cli,"_read_locked_json_document",corrupt)
    with pytest.raises(NativeCallnewhStaticBoundaryError,match="final content validation"):cli._write_immutably(output,rendered,values["evidence"])
    assert output.exists()
@pytest.mark.parametrize("payload",['{"a": 1, "a": 2}','{"a": NaN}'])
def test_cli_rejects_strict_json(tmp_path,capsys,payload):
    path=tmp_path/"bad.json";path.write_text(payload,encoding="utf-8");argv=["verify"]
    for flag in ("--executable","--inventory","--operator-new-static-boundary","--direct-calls","--program-facts","--evidence"):argv += [flag,str(path)]
    assert cli.main(argv)==1 and capsys.readouterr().err.startswith("error: ")
