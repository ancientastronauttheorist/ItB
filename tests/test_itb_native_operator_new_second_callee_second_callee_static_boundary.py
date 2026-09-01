"""Focused fail-closed coverage for the opaque ``0x00370dab`` boundary."""
from __future__ import annotations
import copy,hashlib,json,os,struct,threading
from pathlib import Path
from typing import Any
import pytest

from scripts import itb_native_operator_new_second_callee_second_callee_static_boundary as cli
from src.observatory import native_operator_new_second_callee_second_callee_static_boundary as helper
from src.observatory.native_operator_new_second_callee_second_callee_static_boundary import NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError

ROOT=Path(__file__).resolve().parents[1];PROGRAMS=ROOT/"data"/"observatory"/"programs";INVENTORIES=ROOT/"data"/"observatory"/"inventories";PREFIX="windows_build_13725832_31fe35265598_"
EXE_SHA256="31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
RAW_SHA256="e2b04a14adfa5440a1b01f978b8785a48b3f7cf6ed26d59577963a48d4eef365"
CANONICAL_SHA256="87f650968e7858d1676b51a99b98822846db39577da2ef737d9e8d74f4c251a8"
def _read(p:Path)->dict[str,Any]:return json.loads(p.read_text(encoding="utf-8"))
@pytest.fixture(scope="module")
def values():
 paths={"inventory":INVENTORIES/(PREFIX+"full_decompile_baseline_20260830.json"),"facts":PROGRAMS/(PREFIX+"program_facts.json"),"direct":PROGRAMS/(PREFIX+"native_lua_direct_call_census.json"),"predecessor":PROGRAMS/(PREFIX+"native_operator_new_second_callee_static_boundary.json"),"sealed":PROGRAMS/(PREFIX+"native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json"),"evidence":PROGRAMS/(PREFIX+"native_operator_new_second_callee_second_callee_static_boundary.json")}
 if any(not p.is_file() for p in paths.values()):pytest.skip("second-callee prerequisites unavailable")
 result={n:_read(p) for n,p in paths.items()};result["paths"]=paths;return result
def _common(v):return v["predecessor"],v["sealed"],v["direct"],v["facts"]
def _structure(v,e=None):return helper.validate_native_operator_new_second_callee_second_callee_static_boundary_structure(v["evidence"] if e is None else e,*_common(v))
def _replace(v,path,replacement):
 if not path:return replacement
 clone=dict(v) if isinstance(v,dict) else list(v);clone[path[0]]=_replace(v[path[0]],path[1:],replacement);return clone
def _add(v,path):
 clone=copy.deepcopy(v);cursor=clone
 for key in path[:-1]:cursor=cursor[key]
 cursor[path[-1]]=True;return clone
def _reject(v,e):
 with pytest.raises(NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError):_structure(v,e)
def _exact_executable():
 configured=os.environ.get("ITB_EXACT_EXE")
 if not configured:pytest.skip("set ITB_EXACT_EXE for exact PE checks")
 p=Path(configured)
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=EXE_SHA256:pytest.skip("ITB_EXACT_EXE is not sealed Breach.exe")
 return p

def test_decoder_cfg_and_terminal_nonclaim():
 rows=helper._decode();assert len(rows)==45 and b"".join(bytes(x.bytes) for x in rows).hex()==helper._RAW
 graph=helper._graph(rows);assert (graph["node_count"],graph["edge_count"],helper._canonical_sha256(graph))==(45,48,helper._CFG)
 assert graph["nodes"][-1]["flow_kind"]=="terminal" and graph["nodes"][-1]["successor_rvas"]==[]

def test_committed_encoding_hashes_and_structure(values):
 raw=values["paths"]["evidence"].read_bytes();e=values["evidence"]
 assert raw==helper.encode_native_operator_new_second_callee_second_callee_static_boundary(e).encode()
 assert hashlib.sha256(raw).hexdigest()==RAW_SHA256 and helper._canonical_sha256(e)==CANONICAL_SHA256
 assert _structure(values)["status"]=="structurally_verified"

def test_control_operand_literal_and_segment_partitions(values):
 calls=values["evidence"]["native_calls"]
 assert len(calls["outgoing_direct"])==1 and calls["outgoing_direct"][0]["target_entry_rva"]=="0x003581b3"
 assert calls["outgoing_direct"][0]["sealed_target_join"]["receipt_canonical_sha256"]==helper._SEALED_TARGETS
 assert [(x["instruction"]["rva"],x["call_form"]) for x in calls["opaque_indirect_controls"]]==[("0x00370de5","x86_register_call_r32"),("0x00370e0a","x86_absolute_memory_indirect_call_ff15")]
 assert len(calls["pe_address_operands"])==7 and sum(x["operand_class"]=="immediate" for x in calls["pe_address_operands"])==6
 assert [(x["instruction_rva"],x["operand_index"],x["value"]) for x in calls["non_pe_immediate_literals"]]==[(f"0x{r:08x}",i,f"0x{v:08x}") for r,i,v in helper._NON_PE]
 assert calls["segment_qualified_memory_syntax"]==[{"role":"opaque_segment_qualified_memory_syntax","instruction":helper._instruction(0x370DC2,"f3a5"),"operand_index":0,"operand_access":"write","segment_register":"ES","base_register":"EDI","repeat_prefix":"F3","runtime_behavior_opaque":True}]
 assert calls["direct_lua_calls"]==calls["staged_lua_dispatches"]==calls["bnd_prefixed_control_syntax"]==calls["opaque_interrupt_syntax"]==[]
 assert next(x for x in calls["call_r32_audit"] if x["register"]=="ESI")["call_rvas"]==["0x00370de5"]

def test_reference_and_iat_receipts(values):
 scan=values["evidence"]["whole_atlas_reference_scan"];iat=values["evidence"]["whole_atlas_iat_slot_use_scan"]
 assert scan["scope"]==helper._SCOPE and scan["partition_sha256"]==helper._PARTITION_HASHES and scan["references_canonical_sha256"]==helper._REFERENCE_HASH
 assert scan["aggregates"]=={"reference_count":481,"target_count":1,"owner_count":414,"target_owner_count":414,"direct_call_count":481,"comparison_count":0,"other_address_count":0,"memory_operand_count":0}
 assert any(x["instruction_rva"]=="0x003584a6" and x["owner_entry_rva"]=="0x0035848f" for x in scan["references"])
 assert iat["references_canonical_sha256"]==helper._IAT_REFERENCE_HASH and iat["owner_partition_canonical_sha256"]==helper._IAT_OWNER_HASH
 assert [x["instruction_rva"] for x in iat["references"]]==["0x00370e0a","0x003922d2","0x0039d2d1"]

def test_raw_import_binding_expected_metadata(values):
 binding=values["evidence"]["native_calls"]["opaque_indirect_controls"][1]["raw_import_table_binding"]
 assert (binding["descriptor_index"],binding["thunk_index"],binding["iat_slot_rva"],binding["hint"],binding["library"],binding["name"],binding["metadata_only"])==(7,91,"0x003d616c",945,"KERNEL32.dll","RaiseException",True)
 assert binding==helper._raw_import_binding()

@pytest.mark.parametrize("path",[("analysis_kind",),("build_identity",),("program_facts",),("predecessor_static_boundary",),("sealed_direct_target_set",),("direct_call_census",),("decoder",),("function_body",),("control_flow_graph",),("predecessor_parent_edges",),("native_calls",),("whole_atlas_reference_scan",),("whole_atlas_iat_slot_use_scan",),("method",),("summary",),("function_body","reviewed_points",0,"sha256"),("function_body","ghidra_analysis_metadata","name_source"),("control_flow_graph","nodes",-1,"flow_kind"),("predecessor_parent_edges",0,"instruction","sha256"),("native_calls","outgoing_direct",0,"sealed_target_join","body_sha256"),("native_calls","opaque_indirect_controls",1,"call_form"),("native_calls","pe_address_operands",0,"operand_rva"),("native_calls","non_pe_immediate_literals",5,"value"),("native_calls","segment_qualified_memory_syntax",0,"segment_register"),("whole_atlas_reference_scan","references",0,"owner_entry_rva"),("whole_atlas_reference_scan","owner_partition",0,"reference_count"),("whole_atlas_reference_scan","partition_sha256","owner_partition"),("whole_atlas_iat_slot_use_scan","references",0,"operand_rva"),("whole_atlas_iat_slot_use_scan","owner_partition_canonical_sha256"),("method","not_claimed"),("summary","target_reference_count")])
def test_structure_rejects_retained_categories(values,path):
 old=values["evidence"]
 for key in path:old=old[key]
 replacement="changed" if not isinstance(old,(bool,int,list,dict)) else (not old if isinstance(old,bool) else old+1 if isinstance(old,int) else [] if isinstance(old,list) else {})
 _reject(values,_replace(values["evidence"],path,replacement))

@pytest.mark.parametrize("path",[("unexpected",),("function_body","unexpected"),("native_calls","unexpected"),("whole_atlas_reference_scan","references",0,"unexpected"),("whole_atlas_iat_slot_use_scan","unexpected")])
def test_structure_rejects_unknown_keys(values,path):_reject(values,_add(values["evidence"],path))

def test_outgoing_partition_fails_if_program_facts_change(values):
 facts=copy.deepcopy(values["facts"]);facts["ghidra_declared_direct_calls"].append({"instruction_rva":"0x00370dab","source_entry_rva":"0x00370dab","target_entry_rva":"0x00370dab","target_rva":"0x00370dab","target_name":"injected"})
 with pytest.raises(NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError,match="outgoing direct"):
  helper._native_calls(facts,values["sealed"])

def test_encoder_and_error_normalization():
 with pytest.raises(NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError):helper.encode_native_operator_new_second_callee_second_callee_static_boundary([])
 with pytest.raises(NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError):helper.encode_native_operator_new_second_callee_second_callee_static_boundary({"x":float("nan")})
 with pytest.raises(NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError,match="injected"):helper._normalize(lambda:(_ for _ in ()).throw(struct.error("injected")))

def test_cli_parser_surface():
 common=[]
 for flag in ("--operator-new-second-callee-static-boundary","--residual-direct-target-set-static-boundary","--direct-calls","--program-facts"):common += [flag,"input.json"]
 assert cli.build_parser().parse_args(["build",*common,"--executable","Breach.exe","--inventory","inventory.json","--output","out.json"]).command=="build"
 assert cli.build_parser().parse_args(["verify-structure",*common,"--evidence","out.json"]).command=="verify-structure"

def _altered_decoder(monkeypatch,helper_module,start_rva,index,address,encoded):
 import capstone
 actual=helper_module._decode_range
 def altered(data,image,start,size,decoder):
  rows=actual(data,image,start,size,decoder)
  if start==start_rva:
   d=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32);d.detail=True;replacement=list(d.disasm(bytes.fromhex(encoded),image.image_base+address));assert len(replacement)==1 and replacement[0].size==rows[index].size;rows[index]=replacement[0]
  return rows
 monkeypatch.setattr(helper_module,"_decode_range",altered);return actual

@pytest.mark.parametrize("injected",["b8ab0d7700","a1ab0d7700"])
def test_exact_incoming_scanner_mutations_preserve_baseline(values,monkeypatch,injected):
 executable=_exact_executable();data,image,_=helper._load_executable(executable);actual=_altered_decoder(monkeypatch,helper,0x35848F,5,0x35849D,injected);decoder,_=helper._decoder()
 with pytest.raises(NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError,match="all-operand"):helper._whole_atlas_reference_scan(data,image,decoder,values["facts"])
 monkeypatch.setattr(helper,"_decode_range",actual)

@pytest.mark.parametrize("injected",["b86c617d00","a16c617d00"])
def test_exact_iat_scanner_mutations_preserve_baseline(values,monkeypatch,injected):
 executable=_exact_executable();data,image,_=helper._load_executable(executable);actual=_altered_decoder(monkeypatch,helper,0x35848F,5,0x35849D,injected);decoder,_=helper._decoder()
 with pytest.raises(NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError,match="IAT-slot"):helper._iat_slot_use_scan(data,image,decoder,values["facts"])
 monkeypatch.setattr(helper,"_decode_range",actual)

@pytest.mark.parametrize("file_offset",[0x48DEEC,0x48DFAC,0x3D522C])
def test_exact_raw_import_corruption(values,file_offset):
 executable=_exact_executable();_,image,_=helper._load_executable(executable);damaged=copy.copy(image);raw=bytearray(image.data);raw[file_offset]^=1;damaged.data=bytes(raw)
 with pytest.raises(NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError,match="raw import bytes"):helper._raw_import_binding(damaged)

def test_exact_rebuild_and_public_verify(values):
 executable=_exact_executable();rebuilt=helper.build_native_operator_new_second_callee_second_callee_static_boundary(executable,*_common(values),inventory=values["inventory"]);assert rebuilt==values["evidence"]
 receipt=helper.validate_native_operator_new_second_callee_second_callee_static_boundary(executable,values["evidence"],*_common(values),inventory=values["inventory"]);assert receipt["status"]=="verified" and receipt["evidence_sha256"]==CANONICAL_SHA256

def _patch_output_root(monkeypatch,tmp_path):info=tmp_path.stat();monkeypatch.setattr(cli,"_prepare_output_root",lambda:(tmp_path,tmp_path,info));monkeypatch.setattr(cli,"_recheck_output_root",lambda *args:None)
def test_cli_writer_immutable_and_preserves_differing(tmp_path,monkeypatch,values):
 _patch_output_root(monkeypatch,tmp_path);output=tmp_path/"evidence.json";rendered=helper.encode_native_operator_new_second_callee_second_callee_static_boundary(values["evidence"]);cli._write_immutably(output,rendered,values["evidence"]);cli._write_immutably(output,rendered,values["evidence"]);output.write_bytes(rendered.encode()+b" ")
 with pytest.raises(NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError,match="refusing to overwrite"):cli._write_immutably(output,rendered,values["evidence"])
def test_cli_writer_same_inode_race(tmp_path,monkeypatch,values):
 _patch_output_root(monkeypatch,tmp_path);output=tmp_path/"evidence.json";rendered=helper.encode_native_operator_new_second_callee_second_callee_static_boundary(values["evidence"]);output.write_bytes(rendered.encode());reader,calls=cli._read_json_document,[]
 def mutate(path,label):
  result=reader(path,label);calls.append(1)
  if len(calls)==1:
   with path.open("ab") as stream:stream.write(b" ")
  return result
 monkeypatch.setattr(cli,"_read_json_document",mutate)
 with pytest.raises(NativeOperatorNewSecondCalleeSecondCalleeStaticBoundaryError):cli._write_immutably(output,rendered,values["evidence"])
def test_cli_writer_final_lock(tmp_path,monkeypatch,values):
 _patch_output_root(monkeypatch,tmp_path);output=tmp_path/"evidence.json";rendered=helper.encode_native_operator_new_second_callee_second_callee_static_boundary(values["evidence"]);output.write_bytes(rendered.encode());reader,attempts=cli._read_locked_json_document,[]
 def during(fd,label):
  result=reader(fd,label)
  def contender():
   try:
    with output.open("ab") as stream:stream.write(b" ")
   except OSError:attempts.append("blocked")
   else:attempts.append("mutated")
  thread=threading.Thread(target=contender);thread.start();thread.join(5);return result
 monkeypatch.setattr(cli,"_read_locked_json_document",during);cli._write_immutably(output,rendered,values["evidence"]);assert attempts==["blocked"]

def test_cli_reports_strict_json_error(tmp_path,capsys):
 bad=tmp_path/"bad.json";bad.write_text('{"x":NaN}',encoding="utf-8");args=["verify","--operator-new-second-callee-static-boundary",str(bad),"--residual-direct-target-set-static-boundary",str(bad),"--direct-calls",str(bad),"--program-facts",str(bad),"--executable",str(bad),"--inventory",str(bad),"--evidence",str(bad)]
 assert cli.main(args)==1 and capsys.readouterr().err.startswith("error: ")
