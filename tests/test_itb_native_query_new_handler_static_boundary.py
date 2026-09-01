"""Exact and adversarial tests for the analysis-only query-new-handler boundary."""
from __future__ import annotations
import copy,hashlib,json,os,threading
from pathlib import Path
from typing import Any
import pytest
from scripts import itb_native_query_new_handler_static_boundary as cli
from src.observatory import native_query_new_handler_static_boundary as helper
from src.observatory.native_query_new_handler_static_boundary import NativeQueryNewHandlerStaticBoundaryError
ROOT=Path(__file__).resolve().parents[1];PROGRAMS=ROOT/"data"/"observatory"/"programs";INVENTORIES=ROOT/"data"/"observatory"/"inventories";PREFIX="windows_build_13725832_31fe35265598_";EXE=Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
RAW="a0e4913c271166ee3ebd0e429f86161d47f9108c5201d2de6d4219bae8b85263";CANONICAL="742e341a855de34731177afd53b385c67fbd64f3d277fedf8ba6c8e9bbf61705";EXE_SHA="31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
def _read(p):return json.loads(p.read_text(encoding="utf-8"))
@pytest.fixture(scope="module")
def values():
 paths={"inventory":INVENTORIES/(PREFIX+"full_decompile_baseline_20260830.json"),"facts":PROGRAMS/(PREFIX+"program_facts.json"),"direct":PROGRAMS/(PREFIX+"native_lua_direct_call_census.json"),"callnewh":PROGRAMS/(PREFIX+"native_callnewh_static_boundary.json"),"evidence":PROGRAMS/(PREFIX+"native_query_new_handler_static_boundary.json")}
 if any(not p.is_file() for p in paths.values()):pytest.skip("query-new-handler prerequisites unavailable")
 value={k:_read(p) for k,p in paths.items()};value["paths"]=paths;value["target"]=helper._atlas_functions(value["facts"])[helper._ENTRY];return value
def _common(v):return v["callnewh"],v["direct"],v["facts"]
def _structure(v,e=None):return helper.validate_native_query_new_handler_static_boundary_structure(v["evidence"] if e is None else e,*_common(v))
def _fast(monkeypatch,v,e):
 monkeypatch.setattr(helper,"_validate_json_tree",lambda *a,**k:None);monkeypatch.setattr(helper,"_assert_publication_safe",lambda *a,**k:None);monkeypatch.setattr(helper,"validate_native_lua_direct_call_structure",lambda *a,**k:{"status":"structurally_verified","evidence_sha256":helper._DIRECT});monkeypatch.setattr(helper,"_atlas_functions",lambda *a,**k:{helper._ENTRY:v["target"]});monkeypatch.setattr(helper,"_native",lambda *a,**k:copy.deepcopy(v["evidence"]["native_calls"]));monkeypatch.setattr(helper,"_expected_scan",lambda *a,**k:copy.deepcopy(v["evidence"]["whole_atlas_reference_scan"]));return _structure(v,e)
def _rejects(v,m,e):
 with pytest.raises(NativeQueryNewHandlerStaticBoundaryError):_fast(m,v,e)
def _changed(x):
 if isinstance(x,bool):return not x
 if isinstance(x,int):return x+1
 if isinstance(x,str):return "changed"
 if isinstance(x,list):return [] if x else ["changed"]
 if isinstance(x,dict):return {}
 return "changed"
def _replace(v,path,x):
 if not path:return x
 result=dict(v) if isinstance(v,dict) else list(v);result[path[0]]=_replace(v[path[0]],path[1:],x);return result
def _add(v,path,x):
 if len(path)==1:result=dict(v);result[path[0]]=x;return result
 result=dict(v) if isinstance(v,dict) else list(v);result[path[0]]=_add(v[path[0]],path[1:],x);return result
def test_committed_receipts_and_structure(values):
 raw=values["paths"]["evidence"].read_bytes();assert raw==helper.encode_native_query_new_handler_static_boundary(values["evidence"]).encode("utf-8");assert hashlib.sha256(raw).hexdigest()==RAW;assert helper._canonical_sha256(values["evidence"])==CANONICAL;assert _structure(values)["evidence_sha256"]==CANONICAL
def test_exact_body_predecessor_syntax_and_nonclaims(values):
 e=values["evidence"];body=e["function_bodies"][0];graph=e["control_flow_graphs"][0];assert (body["entry_rva"],body["body_size"],body["body_sha256"],body["control_flow_graph_canonical_sha256"],len(body["reviewed_points"]))==("0x0038bc08",70,"d891c503b590777cfded201a57a6b3032eea43bf3392f0133a49fcc44f8b890c","d21337510640f0a3c667168438e31aeb61dcc6391119b79fb3c3552c313ce35d",19);assert (graph["node_count"],graph["edge_count"])==(19,18)
 assert body["direct_lua_calls"]==[] and body["staged_lua_dispatches"]==[] and body["call_r32_audit"]==[{"register":r,"call_rvas":[]} for r in helper._REGISTER_NAMES]
 assert [(x["instruction"]["rva"],x["target_entry_rva"]) for x in e["native_calls"]["direct"]]==[("0x0038bc0f","0x003584b0"),("0x0038bc1a","0x00388bc5"),("0x0038bc41","0x0038bc51"),("0x0038bc48","0x003584f6")]
 pointers=e["native_calls"]["absolute_pointer_or_memory_syntax"];assert [(x["operand_va"],x["operand_rva"],x["section_name"],x["section_characteristics"],x["section_writable"],x["file_backed"]) for x in pointers]==[("0x0088e3a8","0x0048e3a8",".rdata","0x40000040",False,True),("0x00893f28","0x00493f28",".data","0xc0000040",True,True),("0x008b71e4","0x004b71e4",".data","0xc0000040",True,False)]
 edge=e["callnewh_query_new_handler_edge"];assert (edge["source_entry_rva"],edge["instruction"]["rva"],edge["target_entry_rva"])==("0x0038bbc4","0x0038bbd5","0x0038bc08");assert len(e["whole_atlas_reference_scan"]["references"])==1
 for token in ("new-handler","SEH","lock","security","ABI","allocation","runtime","pointer contents","computed","Lua-side"):assert any(token.lower() in x.lower() for x in e["method"]["not_claimed"])
def test_exact_rebuild(values):
 if not EXE.is_file() or hashlib.sha256(EXE.read_bytes()).hexdigest()!=EXE_SHA:pytest.skip("sealed executable unavailable")
 rebuilt=helper.build_native_query_new_handler_static_boundary(EXE,*_common(values),inventory=values["inventory"]);assert rebuilt==values["evidence"];assert helper.validate_native_query_new_handler_static_boundary(EXE,values["evidence"],*_common(values),inventory=values["inventory"])["status"]=="verified"
@pytest.mark.parametrize("key",["schema_version","analysis_kind","build_identity","atlas","direct_call_census","callnewh_static_boundary","callnewh_query_new_handler_edge","decoder","function_bodies","control_flow_graphs","native_calls","whole_atlas_reference_scan","method","summary"])
def test_structure_rejects_categories(values,monkeypatch,key):_rejects(values,monkeypatch,_replace(values["evidence"],(key,),_changed(values["evidence"][key])))
@pytest.mark.parametrize("path",[("unexpected",),("function_bodies",0,"unexpected"),("native_calls","direct",0,"unexpected"),("native_calls","absolute_pointer_or_memory_syntax",2,"unexpected"),("whole_atlas_reference_scan","owner_partition",0,"unexpected")])
def test_structure_rejects_unknown_keys(values,monkeypatch,path):_rejects(values,monkeypatch,_add(values["evidence"],path,True))
@pytest.mark.parametrize("path",[("native_calls","absolute_pointer_or_memory_syntax",0,"operand_va"),("native_calls","absolute_pointer_or_memory_syntax",1,"section_characteristics"),("native_calls","absolute_pointer_or_memory_syntax",2,"file_backed"),("whole_atlas_reference_scan","references",0,"owner_entry_rva")])
def test_structure_rejects_pointer_and_owner_tamper(values,monkeypatch,path):
 cursor=values["evidence"]
 for key in path:cursor=cursor[key]
 _rejects(values,monkeypatch,_replace(values["evidence"],path,_changed(cursor)))
@pytest.mark.parametrize("bad",[None,False,[],{}])
def test_structure_rejects_wrong_owner_type(values,monkeypatch,bad):_rejects(values,monkeypatch,_replace(values["evidence"],("whole_atlas_reference_scan","references",0,"owner_atlas_record_sha256"),bad))
def test_structure_rejects_missing_owner_partition(values,monkeypatch):
 evidence=copy.deepcopy(values["evidence"]);del evidence["whole_atlas_reference_scan"]["owner_partition"];_rejects(values,monkeypatch,evidence)
@pytest.mark.parametrize("path",[("whole_atlas_reference_scan","owner_partition",0,"owner_entry_rva"),("whole_atlas_reference_scan","owner_partition",0,"owner_atlas_record_sha256"),("whole_atlas_reference_scan","owner_partition",0,"reference_count")])
def test_structure_rejects_tampered_owner_partition(values,monkeypatch,path):
 cursor=values["evidence"]
 for key in path:cursor=cursor[key]
 _rejects(values,monkeypatch,_replace(values["evidence"],path,_changed(cursor)))
def _root(monkeypatch,tmp):
 info=tmp.stat();monkeypatch.setattr(cli,"_prepare_output_root",lambda:(tmp,tmp,info));monkeypatch.setattr(cli,"_recheck_output_root",lambda *a:None)
def test_cli_immutable_root_error_and_preservation(tmp_path,monkeypatch,values):
 _root(monkeypatch,tmp_path);out=tmp_path/"e.json";rendered=helper.encode_native_query_new_handler_static_boundary(values["evidence"]);cli._write_immutably(out,rendered,values["evidence"]);cli._write_immutably(out,rendered,values["evidence"]);out.write_bytes(rendered.encode()+b" ")
 with pytest.raises(NativeQueryNewHandlerStaticBoundaryError,match="refusing to overwrite"):cli._write_immutably(out,rendered,values["evidence"])
 def reject():raise cli.NativeLuaPropertyFactoryChainError("synthetic root")
 monkeypatch.setattr(cli,"_prepare_output_root",reject)
 with pytest.raises(NativeQueryNewHandlerStaticBoundaryError,match="synthetic root"):cli._write_immutably(tmp_path/"x.json",rendered,values["evidence"])
def test_cli_lock_blocks_cooperating_writer(tmp_path,monkeypatch,values):
 _root(monkeypatch,tmp_path);out=tmp_path/"e.json";rendered=helper.encode_native_query_new_handler_static_boundary(values["evidence"]);out.write_bytes(rendered.encode());attempt=[];original=cli._read_locked_json_document
 def writer():
  if os.name=="nt":
   try:
    with out.open("ab") as stream:stream.write(b" ")
   except OSError:attempt.append("blocked")
   else:attempt.append("mutated")
  else:
   import fcntl
   fd=os.open(out,os.O_WRONLY|os.O_APPEND)
   try:
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:attempt.append("blocked")
    else:os.write(fd,b" ");attempt.append("mutated");fcntl.flock(fd,fcntl.LOCK_UN)
   finally:os.close(fd)
 def contended(fd,label):
  result=original(fd,label);thread=threading.Thread(target=writer);thread.start();thread.join(timeout=5);assert not thread.is_alive();return result
 monkeypatch.setattr(cli,"_read_locked_json_document",contended);cli._write_immutably(out,rendered,values["evidence"]);assert attempt==["blocked"] and out.read_bytes()==rendered.encode()
def test_cli_preserves_published_destination_on_final_locked_failure(tmp_path,monkeypatch,values):
 _root(monkeypatch,tmp_path);out=tmp_path/"e.json";rendered=helper.encode_native_query_new_handler_static_boundary(values["evidence"]);out.write_bytes(rendered.encode());original=cli._read_locked_json_document
 def corrupt(fd,label):
  value,payload=original(fd,label);return value,payload+b" "
 monkeypatch.setattr(cli,"_read_locked_json_document",corrupt)
 with pytest.raises(NativeQueryNewHandlerStaticBoundaryError,match="final content validation"):cli._write_immutably(out,rendered,values["evidence"])
 assert out.exists()
