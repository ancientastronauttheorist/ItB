"""Exact and adversarial tests for the local query-new-handler helper boundary."""
from __future__ import annotations
import copy,hashlib,json,os,threading
from pathlib import Path
from typing import Any
import pytest
from scripts import itb_native_query_new_handler_local_helper_static_boundary as cli
from src.observatory import native_query_new_handler_local_helper_static_boundary as helper
from src.observatory.native_query_new_handler_local_helper_static_boundary import NativeQueryNewHandlerLocalHelperStaticBoundaryError

ROOT=Path(__file__).resolve().parents[1];P=ROOT/"data"/"observatory"/"programs";I=ROOT/"data"/"observatory"/"inventories";PREFIX="windows_build_13725832_31fe35265598_";EXE=Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
RAW="3cc19d7a2fb7aac636aba2395692598dad8de7e51c5be9a12c75c30b33eb306c";CANONICAL="01a03401fdbef4e6d1d575ab74e498b5271387a1ffde440c0dee44b28ad5439c";EXE_SHA="31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
def _read(p):return json.loads(p.read_text(encoding="utf-8"))
@pytest.fixture(scope="module")
def values():
 paths={"inventory":I/(PREFIX+"full_decompile_baseline_20260830.json"),"facts":P/(PREFIX+"program_facts.json"),"direct":P/(PREFIX+"native_lua_direct_call_census.json"),"query":P/(PREFIX+"native_query_new_handler_static_boundary.json"),"evidence":P/(PREFIX+"native_query_new_handler_local_helper_static_boundary.json")}
 value={k:_read(p) for k,p in paths.items()};value["paths"]=paths;value["target"]=helper._atlas_functions(value["facts"])[helper._ENTRY];return value
def _common(v):return v["query"],v["direct"],v["facts"]
def _structure(v,e=None):return helper.validate_native_query_new_handler_local_helper_static_boundary_structure(v["evidence"] if e is None else e,*_common(v))
def _fast(m,v,e):
 m.setattr(helper,"_validate_json_tree",lambda *a,**k:None);m.setattr(helper,"_assert_publication_safe",lambda *a,**k:None);m.setattr(helper,"validate_native_lua_direct_call_structure",lambda *a,**k:{"status":"structurally_verified","evidence_sha256":helper._DIRECT});m.setattr(helper,"_atlas_functions",lambda *a,**k:{helper._ENTRY:v["target"]});m.setattr(helper,"_native",lambda *a,**k:copy.deepcopy(v["evidence"]["native_edges"]));return _structure(v,e)
def _reject(v,m,e):
 with pytest.raises(NativeQueryNewHandlerLocalHelperStaticBoundaryError):_fast(m,v,e)
def _replace(v,path,x):
 if not path:return x
 out=dict(v) if isinstance(v,dict) else list(v);out[path[0]]=_replace(v[path[0]],path[1:],x);return out
def _add(v,path,x):
 if len(path)==1:out=dict(v);out[path[0]]=x;return out
 out=dict(v) if isinstance(v,dict) else list(v);out[path[0]]=_add(v[path[0]],path[1:],x);return out
def _changed(x):
 if isinstance(x,bool):return not x
 if isinstance(x,int):return x+1
 if isinstance(x,str):return "changed"
 if isinstance(x,list):return [] if x else ["changed"]
 if isinstance(x,dict):return {}
 return "changed"

def test_receipts_exact_body_edge_predecessor_and_nonclaims(values):
 e=values["evidence"];raw=values["paths"]["evidence"].read_bytes();assert hashlib.sha256(raw).hexdigest()==RAW;assert raw==helper.encode_native_query_new_handler_local_helper_static_boundary(e).encode();assert helper._canonical_sha256(e)==CANONICAL;assert _structure(values)["evidence_sha256"]==CANONICAL
 b=e["function_bodies"][0];g=e["control_flow_graphs"][0];assert (b["entry_rva"],b["body_size"],b["body_sha256"],b["control_flow_graph_canonical_sha256"])==("0x0038bc51",9,"00315b39ffe024b2d781b3d76bd5cdbbf45af50ee16d3d2fef11fb7f1c78e172","248d530fb5189513119b2c55a07739a7b48bb2344cfb0ae9fb926263b3fec2a3");assert (g["node_count"],g["edge_count"],len(b["reviewed_points"]))==(4,3,4)
 assert [(x["rva"],x["size"]) for x in b["reviewed_points"]]==[("0x0038bc51",2),("0x0038bc53",5),("0x0038bc58",1),("0x0038bc59",1)]
 assert b["direct_lua_calls"]==[] and b["staged_lua_dispatches"]==[] and b["call_r32_audit"]==[{"register":r,"call_rvas":[]} for r in helper._REGISTER_NAMES]
 assert [(x["instruction"]["rva"],x["target_entry_rva"]) for x in e["native_edges"]]==[("0x0038bc53","0x00388c0d")]
 predecessor=e["query_predecessor_edge"];assert (predecessor["source_entry_rva"],predecessor["instruction"]["rva"],predecessor["target_entry_rva"])==("0x0038bc08","0x0038bc41","0x0038bc51")
 scan=e["whole_atlas_reference_scan"];assert scan["aggregates"]=={"reference_count":1,"direct_call_count":1,"comparison_count":0,"other_address_count":0,"memory_operand_count":0,"owner_count":1};assert scan["owner_partition"]==[{"owner_entry_rva":"0x0038bc08","owner_atlas_record_sha256":scan["references"][0]["owner_atlas_record_sha256"],"reference_count":1}]
 for word in ("helper purpose","unlock","ABI","argument","success","state mutation","normal return","runtime","source identity","callee","dynamic","data","Lua-side"):assert any(word.lower() in item.lower() for item in e["method"]["not_claimed"])

def test_exact_rebuild(values):
 if not EXE.is_file() or hashlib.sha256(EXE.read_bytes()).hexdigest()!=EXE_SHA:pytest.skip("sealed executable unavailable")
 rebuilt=helper.build_native_query_new_handler_local_helper_static_boundary(EXE,*_common(values),inventory=values["inventory"]);assert rebuilt==values["evidence"];assert helper.validate_native_query_new_handler_local_helper_static_boundary(EXE,values["evidence"],*_common(values),inventory=values["inventory"])["status"]=="verified"

@pytest.mark.parametrize("path",[("unexpected",),("function_bodies",0,"unexpected"),("function_bodies",0,"reviewed_points",0,"meaning","unexpected"),("native_edges",0,"instruction","unexpected"),("whole_atlas_reference_scan","references",0,"unexpected"),("whole_atlas_reference_scan","owner_partition",0,"unexpected")])
def test_strict_schema_rejects_unknown_keys(values,monkeypatch,path):_reject(values,monkeypatch,_add(values["evidence"],path,True))
@pytest.mark.parametrize("path",[("schema_version",),("function_bodies",0,"body_size"),("function_bodies",0,"register_call_partition_complete"),("whole_atlas_reference_scan","references",0,"operand_index"),("whole_atlas_reference_scan","owner_partition",0,"reference_count")])
def test_strict_types_and_tamper_reject(values,monkeypatch,path):
 x=values["evidence"]
 for k in path:x=x[k]
 _reject(values,monkeypatch,_replace(values["evidence"],path,True if isinstance(x,int) and not isinstance(x,bool) else _changed(x)))
def test_missing_and_tampered_owner_partition_reject(values,monkeypatch):
 e=copy.deepcopy(values["evidence"]);del e["whole_atlas_reference_scan"]["owner_partition"];_reject(values,monkeypatch,e)
 _reject(values,monkeypatch,_replace(values["evidence"],("whole_atlas_reference_scan","owner_partition",0,"owner_entry_rva"),"0x00000000"))

@pytest.mark.parametrize("path",[("schema_version",),("analysis_kind",),("build_identity",),("atlas",),("direct_call_census",),("query_new_handler_static_boundary",),("query_predecessor_edge",),("decoder",),("function_bodies",),("control_flow_graphs",),("native_edges",),("whole_atlas_reference_scan",),("method",),("summary",)])
def test_top_level_category_mutations_reject(values,monkeypatch,path):
 x=values["evidence"]
 for k in path:x=x[k]
 _reject(values,monkeypatch,_replace(values["evidence"],path,_changed(x)))

@pytest.mark.parametrize("path",[("whole_atlas_reference_scan","references",0,"owner_entry_rva"),("whole_atlas_reference_scan","references",0,"owner_atlas_record_sha256")])
@pytest.mark.parametrize("replacement",[None,False,7,[]])
def test_missing_or_wrong_type_reference_owner_identity_rejects_domain_error(values,monkeypatch,path,replacement):
 e=copy.deepcopy(values["evidence"])
 cursor=e
 for key in path[:-1]:cursor=cursor[key]
 if replacement is None:del cursor[path[-1]]
 else:cursor[path[-1]]=replacement
 _reject(values,monkeypatch,e)

def test_structure_requires_prerequisite_status(values,monkeypatch):
 monkeypatch.setattr(helper,"validate_native_lua_direct_call_structure",lambda *a,**k:{"status":"verified","evidence_sha256":helper._DIRECT})
 with pytest.raises(NativeQueryNewHandlerLocalHelperStaticBoundaryError,match="prerequisite"):_structure(values)

def test_encoder_wraps_inherited_json_tree_error(monkeypatch):
 monkeypatch.setattr(helper,"_validate_json_tree",lambda *a,**k:(_ for _ in ()).throw(helper.NativeLuaCClosurePublicationError("bad JSON tree")))
 with pytest.raises(NativeQueryNewHandlerLocalHelperStaticBoundaryError,match="bad JSON tree"):helper.encode_native_query_new_handler_local_helper_static_boundary({})

def _root(m,tmp):info=tmp.stat();m.setattr(cli,"_prepare_output_root",lambda:(tmp,tmp,info));m.setattr(cli,"_recheck_output_root",lambda *a:None)
def test_cli_inherited_errors_and_published_failure_preservation(tmp_path,monkeypatch,values):
 _root(monkeypatch,tmp_path);out=tmp_path/"e.json";rendered=helper.encode_native_query_new_handler_local_helper_static_boundary(values["evidence"]);cli._write_immutably(out,rendered,values["evidence"]);out.write_bytes(rendered.encode()+b" ")
 with pytest.raises(NativeQueryNewHandlerLocalHelperStaticBoundaryError,match="refusing to overwrite"):cli._write_immutably(out,rendered,values["evidence"])
 def bad():raise cli.NativeLuaPropertyFactoryChainError("inherited root failure")
 monkeypatch.setattr(cli,"_prepare_output_root",bad)
 with pytest.raises(NativeQueryNewHandlerLocalHelperStaticBoundaryError,match="inherited root failure"):cli._write_immutably(tmp_path/"other.json",rendered,values["evidence"])
 assert out.read_bytes()==rendered.encode()+b" "
def test_cli_lock_contention(tmp_path,monkeypatch,values):
 _root(monkeypatch,tmp_path);out=tmp_path/"e.json";rendered=helper.encode_native_query_new_handler_local_helper_static_boundary(values["evidence"]);out.write_bytes(rendered.encode());seen=[];original=cli._read_locked_json_document
 def writer():
  if os.name=="nt":
   try:
    with out.open("ab") as s:s.write(b" ")
   except OSError:seen.append("blocked")
   else:seen.append("mutated")
  else:
   import fcntl;fd=os.open(out,os.O_WRONLY|os.O_APPEND)
   try:
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:seen.append("blocked")
    else:os.write(fd,b" ");seen.append("mutated")
   finally:os.close(fd)
 def read(fd,label):
  result=original(fd,label);t=threading.Thread(target=writer);t.start();t.join(5);assert not t.is_alive();return result
 monkeypatch.setattr(cli,"_read_locked_json_document",read);cli._write_immutably(out,rendered,values["evidence"]);assert seen==["blocked"]

@pytest.mark.parametrize("existing",[True,False])
def test_cli_final_locked_read_corruption_preserves_existing_or_cleans_private_publication(tmp_path,monkeypatch,values,existing):
 _root(monkeypatch,tmp_path);out=tmp_path/"e.json";rendered=helper.encode_native_query_new_handler_local_helper_static_boundary(values["evidence"])
 if existing:out.write_bytes(rendered.encode())
 original=cli._read_locked_json_document
 def corrupt(fd,label):
  value,payload=original(fd,label);return value,payload+b" "
 monkeypatch.setattr(cli,"_read_locked_json_document",corrupt)
 with pytest.raises(NativeQueryNewHandlerLocalHelperStaticBoundaryError,match="final content validation"):cli._write_immutably(out,rendered,values["evidence"])
 if existing:assert out.read_bytes()==rendered.encode()
 else:assert not out.exists()
