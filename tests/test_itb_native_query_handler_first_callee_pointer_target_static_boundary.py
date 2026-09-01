"""Exact and adversarial tests for the first-callee pointer target receipt."""
from __future__ import annotations
import copy, hashlib, json, os, threading
from pathlib import Path
import pytest
from scripts import itb_native_query_handler_first_callee_pointer_target_static_boundary as cli
from src.observatory import native_query_handler_first_callee_pointer_target_static_boundary as target
from src.observatory.native_query_handler_first_callee_pointer_target_static_boundary import NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError

ROOT=Path(__file__).resolve().parents[1]; PROGRAMS=ROOT/"data"/"observatory"/"programs"; INVENTORIES=ROOT/"data"/"observatory"/"inventories"; PREFIX="windows_build_13725832_31fe35265598_"; EXE=Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
RAW="0fc22f514989853df44f285396b4f59683ee94f703fcc355b566ad6518783c4d"; CANONICAL="41ee47debe789243dfe9fd9566958846cd79cb82549acb99eafc9e2b5cfd9349"
def _read(p): return json.loads(p.read_text(encoding="utf-8"))
@pytest.fixture(scope="module")
def values():
 paths={"inventory":INVENTORIES/(PREFIX+"full_decompile_baseline_20260830.json"),"facts":PROGRAMS/(PREFIX+"program_facts.json"),"direct":PROGRAMS/(PREFIX+"native_lua_direct_call_census.json"),"query":PROGRAMS/(PREFIX+"native_query_new_handler_static_boundary.json"),"first":PROGRAMS/(PREFIX+"native_query_handler_first_callee_static_boundary.json"),"evidence":PROGRAMS/(PREFIX+"native_query_handler_first_callee_pointer_target_static_boundary.json")}; out={k:_read(p) for k,p in paths.items()}; out["paths"]=paths; out["atlas_functions"]=target._atlas_functions(out["facts"]); out["preflight"]=target._preflight(out["first"],out["query"],out["direct"],out["facts"]); return out
def _common(v): return v["first"],v["query"],v["direct"],v["facts"]
def _structure(v,e=None): return target.validate_native_query_handler_first_callee_pointer_target_static_boundary_structure(v["evidence"] if e is None else e,*_common(v))
def _replace(v,path,value):
 if not path: return value
 out=dict(v) if isinstance(v,dict) else list(v); out[path[0]]=_replace(v[path[0]],path[1:],value); return out
def _add(v,path,value):
 if len(path)==1: out=dict(v); out[path[0]]=value; return out
 out=dict(v) if isinstance(v,dict) else list(v); out[path[0]]=_add(v[path[0]],path[1:],value); return out
def _changed(v): return (not v) if isinstance(v,bool) else v+1 if isinstance(v,int) else "changed" if isinstance(v,str) else ([] if v else [True]) if isinstance(v,list) else ({} if v else {"changed":True}) if isinstance(v,dict) else "changed"
def _fast(monkeypatch,v,e):
 monkeypatch.setattr(target,"validate_native_lua_direct_call_structure",lambda *a,**k:{"status":"structurally_verified","evidence_sha256":target._DIRECT}); monkeypatch.setattr(target,"_atlas_functions",lambda _facts:v["atlas_functions"]); monkeypatch.setattr(target,"_preflight",lambda *args:v["preflight"]); return _structure(v,e)
def _reject(monkeypatch,v,e):
 with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError): _fast(monkeypatch,v,e)

def test_receipt_reference_partition_and_nonclaims(values):
 e=values["evidence"]; raw=values["paths"]["evidence"].read_bytes(); assert hashlib.sha256(raw).hexdigest()==RAW and raw==target.encode_native_query_handler_first_callee_pointer_target_static_boundary(e).encode() and target._canonical_sha256(e)==CANONICAL and _structure(values)["evidence_sha256"]==CANONICAL
 b,g=e["function_bodies"][0],e["control_flow_graphs"][0]; assert (b["entry_rva"],b["body_size"],len(b["reviewed_points"]),g["node_count"],g["edge_count"])==("0x003729b0",358,120,120,130)
 rows=e["whole_atlas_reference_scan"]["references"]; assert [(r["instruction_rva"],r["owner_entry_rva"],r["use_class"],r["call_form"],r["ghidra_declared_direct_edge"]) for r in rows]==[("0x003584b0","0x003584b0","other_address",None,None),("0x0039d58a","0x0039d580","other_address",None,None),("0x0039d770","0x0039d770","other_address",None,None)]
 assert len(e["native_calls"]["direct"])==11 and e["function_bodies"][0]["call_r32_audit"][6]=={"register":"ESI","call_rvas":["0x00372a71"]}
 for word in ("exception","handler","stack","register","security","ABI","runtime","target identity","Lua-side"): assert any(word.lower() in x.lower() for x in e["method"]["not_claimed"])

@pytest.mark.parametrize("path",[("unexpected",),("function_bodies",0,"unexpected"),("function_bodies",0,"reviewed_points",0,"unexpected"),("native_calls","direct",0,"unexpected"),("native_calls","direct",0,"instruction","unexpected"),("native_calls","direct",0,"ghidra_declared_direct_edge","unexpected"),("native_calls","opaque_instruction_syntax",0,"unexpected"),("whole_atlas_reference_scan","scope","unexpected"),("whole_atlas_reference_scan","aggregates","unexpected"),("whole_atlas_reference_scan","references",1,"unexpected"),("whole_atlas_reference_scan","owner_partition",2,"unexpected")])
def test_unknown_keys_reject(values,monkeypatch,path): _reject(monkeypatch,values,_add(values["evidence"],path,True))

def _mutate_all(monkeypatch,values,paths):
 for path in paths:
  item=values["evidence"]
  for key in path: item=item[key]
  _reject(monkeypatch,values,_replace(values["evidence"],path,_changed(item)))

def test_every_direct_edge_field_rejects(values,monkeypatch):
 fields=("role","source_entry_rva","source_atlas_record_sha256","source_body_size","source_body_sha256","target_entry_rva","target_atlas_record_sha256","target_body_size","target_body_sha256")
 paths=[]
 for index in range(11):
  paths += [("native_calls","direct",index,key) for key in fields]
  paths += [("native_calls","direct",index,"instruction",key) for key in ("rva","size","sha256")]
  paths += [("native_calls","direct",index,"ghidra_declared_direct_edge",key) for key in ("instruction_rva","source_entry_rva","target_entry_rva","target_rva","target_name_sha256")]
 _mutate_all(monkeypatch,values,paths)

def test_every_opaque_operand_and_register_call_field_rejects(values,monkeypatch):
 paths=[]
 for index in range(6):
  record=values["evidence"]["native_calls"]["opaque_instruction_syntax"][index]
  paths += [("native_calls","opaque_instruction_syntax",index,key) for key in record]
  paths += [("native_calls","opaque_instruction_syntax",index,"instruction",key) for key in record["instruction"]]
 for key in values["evidence"]["native_calls"]["opaque_instruction_syntax"][6]:
  paths.append(("native_calls","opaque_instruction_syntax",6,key))
 paths += [("native_calls","opaque_instruction_syntax",6,"instruction",key) for key in ("rva","size","sha256")]
 _mutate_all(monkeypatch,values,paths)

def test_every_register_audit_reference_partition_scope_and_aggregate_field_rejects(values,monkeypatch):
 paths=[]; evidence=values["evidence"]
 for index,row in enumerate(evidence["function_bodies"][0]["call_r32_audit"]): paths += [("function_bodies",0,"call_r32_audit",index,key) for key in row]
 for index,row in enumerate(evidence["whole_atlas_reference_scan"]["references"]): paths += [("whole_atlas_reference_scan","references",index,key) for key in row]
 for index,row in enumerate(evidence["whole_atlas_reference_scan"]["owner_partition"]): paths += [("whole_atlas_reference_scan","owner_partition",index,key) for key in row]
 paths += [("whole_atlas_reference_scan","scope",key) for key in evidence["whole_atlas_reference_scan"]["scope"]]
 paths += [("whole_atlas_reference_scan","aggregates",key) for key in evidence["whole_atlas_reference_scan"]["aggregates"]]
 _mutate_all(monkeypatch,values,paths)

def test_reference_partition_missing_removed_reordered_and_stale_fields_reject(values,monkeypatch):
 evidence=copy.deepcopy(values["evidence"]); del evidence["whole_atlas_reference_scan"]["owner_partition"]; _reject(monkeypatch,values,evidence)
 for key in ("references","owner_partition"):
  evidence=copy.deepcopy(values["evidence"]); evidence["whole_atlas_reference_scan"][key].pop(); _reject(monkeypatch,values,evidence)
  evidence=copy.deepcopy(values["evidence"]); evidence["whole_atlas_reference_scan"][key].reverse(); _reject(monkeypatch,values,evidence)
 for key in ("returned_callback_reference_count","alternate_owner_reference_count"):
  _reject(monkeypatch,values,_add(values["evidence"],("whole_atlas_reference_scan","aggregates",key),0))

@pytest.mark.parametrize("path",[("schema_version",),("analysis_kind",),("build_identity",),("atlas",),("direct_call_census",),("query_handler_static_boundary",),("first_callee_static_boundary",),("first_callee_pointer_predecessor",),("decoder",),("function_bodies",),("control_flow_graphs",),("native_calls",),("whole_atlas_reference_scan",),("method",),("summary",)])
def test_top_level_category_mutations_reject(values,monkeypatch,path): _reject(monkeypatch,values,_replace(values["evidence"],path,_changed(values["evidence"][path[0]])))
@pytest.mark.parametrize("path,value",[(("schema_version",),True),(("whole_atlas_reference_scan","references",0,"operand_index"),True),(("whole_atlas_reference_scan","references",0,"call_form"),[]),(("whole_atlas_reference_scan","owner_partition",0,"reference_count"),True),(("native_calls","opaque_instruction_syntax",0,"operand_access"),True),(("native_calls","opaque_instruction_syntax",0,"segment_register"),[]),(("native_calls","direct",0,"target_body_size"),True),(("function_bodies",0,"call_r32_audit",6,"call_rvas"),True)])
def test_bool_as_int_and_wrong_container_types_reject(values,monkeypatch,path,value): _reject(monkeypatch,values,_replace(values["evidence"],path,value))
def test_exact_rebuild(values):
 if not EXE.is_file(): pytest.skip("sealed executable unavailable")
 assert target.build_native_query_handler_first_callee_pointer_target_static_boundary(EXE,*_common(values),inventory=values["inventory"])==values["evidence"]
 assert target.validate_native_query_handler_first_callee_pointer_target_static_boundary(EXE,values["evidence"],*_common(values),inventory=values["inventory"])["status"]=="verified"
def _root(monkeypatch,tmp): info=tmp.stat(); monkeypatch.setattr(cli,"_prepare_output_root",lambda:(tmp,tmp,info)); monkeypatch.setattr(cli,"_recheck_output_root",lambda *a:None)
def test_cli_inherited_errors_and_existing_preservation(tmp_path,monkeypatch,values):
 _root(monkeypatch,tmp_path); out=tmp_path/"e.json"; rendered=target.encode_native_query_handler_first_callee_pointer_target_static_boundary(values["evidence"]); cli._write_immutably(out,rendered,values["evidence"]); out.write_bytes(rendered.encode()+b" ")
 with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError,match="refusing to overwrite"): cli._write_immutably(out,rendered,values["evidence"])
 monkeypatch.setattr(cli,"_prepare_output_root",lambda:(_ for _ in ()).throw(cli.NativeLuaPropertyFactoryChainError("inherited root failure")))
 with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError,match="inherited root failure"): cli._write_immutably(tmp_path/"other.json",rendered,values["evidence"])
 assert out.read_bytes()==rendered.encode()+b" "
def test_cli_lock_contention(tmp_path,monkeypatch,values):
 _root(monkeypatch,tmp_path); out=tmp_path/"e.json"; rendered=target.encode_native_query_handler_first_callee_pointer_target_static_boundary(values["evidence"]); out.write_bytes(rendered.encode()); seen=[]; original=cli._read_locked_json_document
 def writer():
  if os.name=="nt":
   try:
    with out.open("ab") as f:f.write(b" ")
   except OSError: seen.append("blocked")
   else: seen.append("mutated")
  else:
   import fcntl; fd=os.open(out,os.O_WRONLY|os.O_APPEND)
   try:
    try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: seen.append("blocked")
    else: os.write(fd,b" "); seen.append("mutated")
   finally: os.close(fd)
 def locked(fd,label): value=original(fd,label); t=threading.Thread(target=writer); t.start(); t.join(5); assert not t.is_alive(); return value
 monkeypatch.setattr(cli,"_read_locked_json_document",locked); cli._write_immutably(out,rendered,values["evidence"]); assert seen==["blocked"]

@pytest.mark.parametrize("existing",[True,False])
def test_cli_final_locked_read_corruption_preserves_or_cleans_publication(tmp_path,monkeypatch,values,existing):
 _root(monkeypatch,tmp_path); out=tmp_path/"e.json"; rendered=target.encode_native_query_handler_first_callee_pointer_target_static_boundary(values["evidence"])
 if existing: out.write_bytes(rendered.encode())
 original=cli._read_locked_json_document
 def corrupt(fd,label): value,payload=original(fd,label); return value,payload+b" "
 monkeypatch.setattr(cli,"_read_locked_json_document",corrupt)
 with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError,match="final content validation"): cli._write_immutably(out,rendered,values["evidence"])
 if existing: assert out.read_bytes()==rendered.encode()
 else: assert not out.exists()
