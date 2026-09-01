import copy, hashlib, json, os, threading
from pathlib import Path
import pytest
from src.observatory import native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary as target
from src.observatory.native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary import NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError
from scripts import itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary as cli

ROOT=Path(__file__).resolve().parents[1]; PROGRAMS=ROOT/"data"/"observatory"/"programs"; INVENTORIES=ROOT/"data"/"observatory"/"inventories"; PREFIX="windows_build_13725832_31fe35265598_"; EXE=Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
RAW="c7da48c159c104db62ce6f0a6c47e31e2739179d9435a49c52e2dfc3014bbaea"; CANONICAL="1385ca599a7442b2b18a45206619d520b19db1b5a2fa9c0ba5b54908831462a5"
def _read(path): return json.loads(path.read_text(encoding="utf-8"))
@pytest.fixture(scope="module")
def values():
 paths={"inventory":INVENTORIES/(PREFIX+"full_decompile_baseline_20260830.json"),"facts":PROGRAMS/(PREFIX+"program_facts.json"),"direct":PROGRAMS/(PREFIX+"native_lua_direct_call_census.json"),"pointer":PROGRAMS/(PREFIX+"native_query_handler_first_callee_pointer_target_static_boundary.json"),"evidence":PROGRAMS/(PREFIX+"native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json")}; out={k:_read(p) for k,p in paths.items()}; out["paths"]=paths; out["atlas_functions"]=target._atlas_functions(out["facts"]); out["preflight"]=target._preflight(out["pointer"],out["direct"],out["facts"]); out["direct_records"]=target._direct_records(out["facts"]); out["parent_edges"]=target._parent_edges(out["pointer"],out["facts"]); out["scan"]=target._scan(None,None,None,out["facts"]); return out
def _common(v): return v["pointer"],v["direct"],v["facts"]
def _structure(v,e=None): return target.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary_structure(v["evidence"] if e is None else e,*_common(v))
def _replace(v,path,value):
 if not path:return value
 out=dict(v) if isinstance(v,dict) else list(v); out[path[0]]=_replace(v[path[0]],path[1:],value); return out
def _add(v,path,value):
 if len(path)==1: out=dict(v);out[path[0]]=value;return out
 out=dict(v) if isinstance(v,dict) else list(v);out[path[0]]=_add(v[path[0]],path[1:],value);return out
def _remove(v,path):
 if len(path)==1:
  out=dict(v); del out[path[0]]; return out
 out=dict(v) if isinstance(v,dict) else list(v); out[path[0]]=_remove(v[path[0]],path[1:]); return out
def _changed(value): return not value if isinstance(value,bool) else value+1 if isinstance(value,int) else "changed" if isinstance(value,str) else [True] if isinstance(value,list) else {"changed":True} if isinstance(value,dict) else "changed"
def _fast(monkeypatch,v,e):
 monkeypatch.setattr(target,"validate_native_lua_direct_call_structure",lambda *a,**k:{"status":"structurally_verified","evidence_sha256":target._DIRECT}); monkeypatch.setattr(target,"_atlas_functions",lambda _facts:v["atlas_functions"]); monkeypatch.setattr(target,"_preflight",lambda *args:v["preflight"]); monkeypatch.setattr(target,"_direct_records",lambda _facts:v["direct_records"]); monkeypatch.setattr(target,"_parent_edges",lambda *args:v["parent_edges"]); monkeypatch.setattr(target,"_scan",lambda *args:v["scan"]); return _structure(v,e)
def _reject(monkeypatch,v,e):
 with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError): _fast(monkeypatch,v,e)
def _leaves(value,path=()):
 if isinstance(value,dict):
  if not value: yield path
  for key,item in value.items(): yield from _leaves(item,path+(key,))
 elif isinstance(value,list):
  if not value: yield path
  for index,item in enumerate(value): yield from _leaves(item,path+(index,))
 else: yield path
def _lists(value,path=()):
 if isinstance(value,dict):
  for key,item in value.items(): yield from _lists(item,path+(key,))
 elif isinstance(value,list):
  yield path,value
  for index,item in enumerate(value): yield from _lists(item,path+(index,))
def _at(value,path):
 for key in path: value=value[key]
 return value

def test_identity_layout_and_nonclaims(values):
 e=values["evidence"]; raw=values["paths"]["evidence"].read_bytes(); assert hashlib.sha256(raw).hexdigest()==RAW and raw==target.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary(e).encode() and target._canonical_sha256(e)==CANONICAL
 assert _structure(values)["evidence_sha256"]==CANONICAL
 assert [(b["entry_rva"],b["body_size"],len(b["reviewed_points"])) for b in e["function_bodies"]]==[("0x00378b3e",23,16),("0x00378b55",25,11),("0x00378b6e",25,15),("0x00378b87",23,9)]
 assert e["contiguous_layout"]["semantic_kinship_claimed"] is False and [r["reference_count"] for r in e["whole_atlas_reference_scan"]["target_partition"]]==[1,1,1,2]
 for word in ("adjacency","ABI","runtime","target identity","Lua-side"): assert any(word.lower() in claim.lower() for claim in e["method"]["not_claimed"])

def test_every_nested_leaf_rejects(values,monkeypatch):
 for path in _leaves(values["evidence"]):
  value=values["evidence"]
  for key in path:value=value[key]
  _reject(monkeypatch,values,_replace(values["evidence"],path,_changed(value)))

@pytest.mark.parametrize("path",[("unexpected",),("function_bodies",0,"unexpected"),("function_bodies",0,"reviewed_points",0,"unexpected"),("control_flow_graphs",0,"nodes",0,"unexpected"),("native_calls","direct",0,"unexpected"),("native_calls","direct",0,"ghidra_declared_direct_edge","unexpected"),("native_calls","opaque_instruction_syntax",0,"unexpected"),("whole_atlas_reference_scan","references",0,"unexpected"),("whole_atlas_reference_scan","target_partition",0,"unexpected"),("whole_atlas_reference_scan","owner_partition",0,"unexpected"),("whole_atlas_reference_scan","aggregates","unexpected")])
def test_unknown_keys_reject(values,monkeypatch,path): _reject(monkeypatch,values,_add(values["evidence"],path,True))

@pytest.mark.parametrize("path",[("function_bodies",),("control_flow_graphs",),("native_calls","direct"),("native_calls","opaque_instruction_syntax"),("pointer_target_parent_edges",),("whole_atlas_reference_scan","references"),("whole_atlas_reference_scan","target_partition"),("whole_atlas_reference_scan","owner_partition")])
def test_missing_reordered_and_duplicate_partitions_reject(values,monkeypatch,path):
 e=copy.deepcopy(values["evidence"]); owner=e
 for key in path[:-1]: owner=owner[key]
 sequence=owner[path[-1]]; del owner[path[-1]]; _reject(monkeypatch,values,e)
 if len(sequence)>1:
  e=copy.deepcopy(values["evidence"]); owner=e
  for key in path[:-1]: owner=owner[key]
  owner[path[-1]]=list(reversed(owner[path[-1]])); _reject(monkeypatch,values,e)
 e=copy.deepcopy(values["evidence"]); owner=e
 for key in path[:-1]: owner=owner[key]
 owner[path[-1]].append(copy.deepcopy(owner[path[-1]][0])); _reject(monkeypatch,values,e)

def test_every_nested_list_field_and_shape_rejects(values,monkeypatch):
 """Exercise every list schema field with only real, nonidentity mutations."""
 for path,sequence in _lists(values["evidence"]):
  parent=_at(values["evidence"],path[:-1])
  assert isinstance(parent,dict) and isinstance(path[-1],str), path
  _reject(monkeypatch,values,_remove(values["evidence"],path))
  if sequence:
   shortened=list(sequence[1:])
   assert shortened != sequence
   _reject(monkeypatch,values,_replace(values["evidence"],path,shortened))
   duplicated=list(sequence)+[copy.deepcopy(sequence[0])]
   assert duplicated != sequence
   _reject(monkeypatch,values,_replace(values["evidence"],path,duplicated))
  if len(sequence)>1:
   reversed_sequence=list(reversed(sequence))
   if reversed_sequence != sequence: _reject(monkeypatch,values,_replace(values["evidence"],path,reversed_sequence))

def test_all_body_point_cfg_and_register_shapes_are_enumerated(values):
 e=values["evidence"]
 list_paths={path for path,_ in _lists(e)}
 for index in range(4):
  assert ("function_bodies",index,"reviewed_points") in list_paths
  assert ("function_bodies",index,"call_r32_audit") in list_paths
  for register_index,row in enumerate(e["function_bodies"][index]["call_r32_audit"]):
   assert row["register"] and ("function_bodies",index,"call_r32_audit",register_index,"call_rvas") in list_paths
  assert ("control_flow_graphs",index,"nodes") in list_paths
  for node_index,node in enumerate(e["control_flow_graphs"][index]["nodes"]):
   assert ("control_flow_graphs",index,"nodes",node_index,"successor_rvas") in list_paths
 assert ("decoder","register_call_encoding_audit") in list_paths
 assert ("contiguous_layout","member_entries") in list_paths and ("contiguous_layout","adjacent_pairs") in list_paths

@pytest.mark.parametrize("path,value",[(("schema_version",),True),(("function_bodies",),[]),(("control_flow_graphs",),{}),(("whole_atlas_reference_scan","aggregates"),[]),(("whole_atlas_reference_scan","aggregates","target_count"),True),(("native_calls","direct",0,"target_body_size"),True),(("native_calls","opaque_instruction_syntax",0,"instruction"),[]),(("contiguous_layout","size"),True)])
def test_wrong_types_reject(values,monkeypatch,path,value): _reject(monkeypatch,values,_replace(values["evidence"],path,value))

@pytest.mark.parametrize("path,value",[(("function_bodies",0,"direct_lua_calls"),[{"changed":True}]),(("function_bodies",1,"staged_lua_dispatches"),[{"changed":True}]),(("function_bodies",2,"call_r32_audit",0,"call_rvas"),["0x00378b6e"]),(("function_bodies",3,"call_r32_audit",0,"call_rvas"),["0x00378b87"])])
def test_empty_lua_and_register_partitions_reject(values,monkeypatch,path,value): _reject(monkeypatch,values,_replace(values["evidence"],path,value))

def test_exact_rebuild_and_validate(values):
 if not EXE.is_file(): pytest.skip("sealed executable unavailable")
 assert target.build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary(EXE,*_common(values),inventory=values["inventory"])==values["evidence"]
 assert target.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary(EXE,values["evidence"],*_common(values),inventory=values["inventory"])["status"]=="verified"
def _root(monkeypatch,tmp): info=tmp.stat(); monkeypatch.setattr(cli,"_prepare_output_root",lambda:(tmp,tmp,info)); monkeypatch.setattr(cli,"_recheck_output_root",lambda *a:None)
def test_cli_error_normalization_and_existing_preservation(tmp_path,monkeypatch,values):
 _root(monkeypatch,tmp_path); out=tmp_path/"e.json"; rendered=target.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary(values["evidence"]); cli._write_immutably(out,rendered,values["evidence"]); out.write_bytes(rendered.encode()+b" ")
 with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError,match="refusing to overwrite"): cli._write_immutably(out,rendered,values["evidence"])
 monkeypatch.setattr(cli,"_prepare_output_root",lambda:(_ for _ in ()).throw(cli.NativeLuaPropertyFactoryChainError("inherited root failure")))
 with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError,match="inherited root failure"): cli._write_immutably(tmp_path/"other.json",rendered,values["evidence"])
 assert out.read_bytes()==rendered.encode()+b" "
def test_cli_lock_contention(tmp_path,monkeypatch,values):
 _root(monkeypatch,tmp_path); out=tmp_path/"e.json"; rendered=target.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary(values["evidence"]); out.write_bytes(rendered.encode()); seen=[]; original=cli._read_locked_json_document
 def writer():
  if os.name=="nt":
   try:
    with out.open("ab") as f:f.write(b" ")
   except OSError:seen.append("blocked")
   else:seen.append("mutated")
  else:
   import fcntl; fd=os.open(out,os.O_WRONLY|os.O_APPEND)
   try:
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:seen.append("blocked")
    else:os.write(fd,b" ");seen.append("mutated")
   finally:os.close(fd)
 def locked(fd,label):
  value=original(fd,label); thread=threading.Thread(target=writer);thread.start();thread.join(5);assert not thread.is_alive();return value
 monkeypatch.setattr(cli,"_read_locked_json_document",locked); cli._write_immutably(out,rendered,values["evidence"]); assert seen==["blocked"]
@pytest.mark.parametrize("existing",[True,False])
def test_cli_final_locked_read_corruption_preserves_or_cleans(tmp_path,monkeypatch,values,existing):
 _root(monkeypatch,tmp_path); out=tmp_path/"e.json"; rendered=target.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary(values["evidence"])
 if existing:out.write_bytes(rendered.encode())
 original=cli._read_locked_json_document
 def corrupt(fd,label): value,payload=original(fd,label);return value,payload+b" "
 monkeypatch.setattr(cli,"_read_locked_json_document",corrupt)
 with pytest.raises(NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterStaticBoundaryError,match="final content validation"): cli._write_immutably(out,rendered,values["evidence"])
 if existing:assert out.read_bytes()==rendered.encode()
 else:assert not out.exists()
