"""Exact and adversarial tests for the five native Lua ``__gc`` records."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]; PROGRAMS=ROOT/"data"/"observatory"/"programs"; PREFIX="windows_build_13725832_31fe35265598_"
EXE=Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
RAW="9d4435d6d67b5ab46b6391585fecb1e09dc3be926dac66aa04fa1b4c39e34fc7"; CANONICAL="4c2e4be756ef611f234d7d78418daf3fe16be2928ef440bb67b5a586df3bef8a"
sys.path.insert(0,str(ROOT))
import src.observatory.native_lua_cclosure_gc_metatable_consumers as subject  # noqa:E402
import scripts.itb_native_lua_cclosure_gc_metatable_consumers as cli  # noqa:E402
from src.observatory.native_lua_cclosure_gc_metatable_consumers import (  # noqa:E402
    NativeLuaCClosureGcMetatableConsumersError,_canonical_sha256,
    build_native_lua_cclosure_gc_metatable_consumers,
    validate_native_lua_cclosure_gc_metatable_consumers,
    validate_native_lua_cclosure_gc_metatable_consumers_structure)

def _load(path): return json.loads(path.read_text(encoding="utf-8"))
@pytest.fixture(scope="module")
def values():
    names={"inventory":ROOT/"data"/"observatory"/"inventories"/(PREFIX+"full_decompile_baseline_20260830.json"),"facts":PROGRAMS/(PREFIX+"program_facts.json"),"direct":PROGRAMS/(PREFIX+"native_lua_direct_call_census.json"),"callbacks":PROGRAMS/(PREFIX+"native_lua_cclosure_callbacks.json"),"setfield":PROGRAMS/(PREFIX+"native_lua_cclosure_setfield_publications.json"),"direct_setters":PROGRAMS/(PREFIX+"native_lua_cclosure_table_setter_publications.json"),"indirect":PROGRAMS/(PREFIX+"native_lua_cclosure_indirect_settable_publications.json"),"keys":PROGRAMS/(PREFIX+"native_lua_cclosure_table_key_provenance.json"),"evidence":PROGRAMS/(PREFIX+"native_lua_cclosure_gc_metatable_consumers.json")}
    return {k:_load(v) for k,v in names.items()}|{"paths":names}
def _structure(v,e=None): return validate_native_lua_cclosure_gc_metatable_consumers_structure(v["evidence"] if e is None else e,v["direct"],v["callbacks"],v["setfield"],v["direct_setters"],v["indirect"],v["keys"],v["facts"])

def test_pinned_bytes_and_complete_partition(values):
    assert hashlib.sha256(values["paths"]["evidence"].read_bytes()).hexdigest()==RAW
    assert _canonical_sha256(values["evidence"])==CANONICAL
    result=_structure(values); assert result["status"]=="structurally_verified"
    assert result["summary"]["gc_publication_consumer_records"]==5
    assert [r["callback_call_rva"] for r in values["evidence"]["records"]]==["0x002e69f1","0x002e6a8c","0x002e6af9","0x002e6b66","0x002ea533"]

@pytest.mark.parametrize("case",[
    "drop","top_unknown","nested_unknown","registry","literal","writable","userdata","setter","metatable","store","gate","stack","raw","type","helper_edge","consumer","upvalues","duplicate","state_transfer","source_digest","body","cfg","direct","stage","staged_call","last_def","premise","point","point_meaning","adjacency","adjacency_instruction","scan_scope","scan_reference","subtree","initializer_stack","receipt","callback","raw_stack","method","nonclaim","summary",
])
def test_structure_rejects_one_fact_tamper(values,monkeypatch,case):
    # These tests target this artifact's boundary; prerequisite validators are
    # separately covered by their own suites.
    monkeypatch.setattr(subject,"validate_native_lua_cclosure_setfield_publication_structure",lambda *a,**k:{})
    monkeypatch.setattr(subject,"validate_native_lua_cclosure_table_setter_publication_structure",lambda *a,**k:{})
    monkeypatch.setattr(subject,"validate_native_lua_cclosure_table_key_provenance_structure",lambda *a,**k:{})
    e=copy.deepcopy(values["evidence"]); rows=e["records"]
    if case=="drop": rows.pop()
    elif case=="top_unknown": e["unknown"]=True
    elif case=="nested_unknown": rows[0]["metatable_consumer"]["unknown"]=True
    elif case=="registry": rows[0]["registry_key"]["text"]="wrong"
    elif case=="literal": e["shared_gc_literal"]["nul_terminated_bytes_sha256"]="0"*64
    elif case=="writable": rows[1]["registry_key"]["section_writable"]=True
    elif case=="userdata": rows[2]["userdata_size"]=9
    elif case=="setter": rows[1]["publication"]["setter_call_rva"]="0x002e6b77"
    elif case=="metatable": rows[0]["metatable_consumer"]["import_name"]="lua_rawset"
    elif case=="store": rows[0]["registry_store"]["call_rva"]="0x002e6b22"
    elif case=="gate": rows[0]["conditional_null_gate"]["fallthrough_rva"]="0x002e6c19"
    elif case=="stack": rows[0]["stack_trace"].pop()
    elif case=="raw": rows[4]["cache"]["raw_access"]=False
    elif case=="type": rows[4]["cache"]["table_type_constant"]=4
    elif case=="helper_edge": rows[4]["consumer"]["direct_call_rva"]="0x002ea838"
    elif case=="consumer": rows[4]["consumer"]["userdata_size"]=8
    elif case=="upvalues": rows[4]["consumer"]["upvalue_count"]=1
    elif case=="duplicate": rows[4]["cache"]["store"]["import_name"]="lua_settable"
    elif case=="state_transfer": e["helper_consumer_call_boundary"]["state_transfer"]["source"]="esi"
    elif case=="source_digest": e["table_key_provenance_census"]["canonical_sha256"]="0"*64
    elif case=="body": e["source_bodies"][0]["body_sha256"]="0"*64
    elif case=="cfg": e["source_bodies"][0]["control_flow_graph_edge_count"]+=1
    elif case=="direct": e["source_bodies"][0]["direct_lua_calls"][0]["instruction_sha256"]="0"*64
    elif case=="stage": e["source_bodies"][1]["staged_lua_calls"][0]["stage_rva"]="0x002e69f8"
    elif case=="staged_call": e["source_bodies"][1]["staged_lua_calls"][0]["calls"][0]["call_rva"]="0x002e6a04"
    elif case=="last_def": e["source_bodies"][1]["staged_lua_calls"][0]["calls"][0]["last_reaching_stage_rvas"]=[]
    elif case=="premise": e["source_bodies"][1]["staged_lua_calls"][0]["premise"]="volatile"
    elif case=="point": e["semantic_points"][0]["instruction_sha256"]="0"*64
    elif case=="point_meaning": e["semantic_points"][0]["meaning"]["constant"]=1
    elif case=="adjacency": e["semantic_adjacencies"][0]["end_rva"]="0x0004cadd"
    elif case=="adjacency_instruction": e["semantic_adjacencies"][0]["instructions"][0]["sha256"]="0"*64
    elif case=="scan_scope": e["target_reference_scan"]["scope"]["decoded_instruction_count"]-=1
    elif case=="scan_reference": e["target_reference_scan"]["references"][0]["operand_class"]="absolute_memory"
    elif case=="subtree": e["initializer_subtree"]["direct_edges"][0]["instruction_sha256"]="0"*64
    elif case=="initializer_stack": e["initializer_subtree"]["stack_proof"]["join_shape"]="B,K"
    elif case=="receipt": e["table_key_provenance_receipt"]["status"]="structurally_verified"
    elif case=="callback": e["callback_identities"][0]["body_size"]+=1
    elif case=="raw_stack": rows[4]["stack_trace"]["consumer"][-1]["after"]="B,C"
    elif case=="method": e["method"]["cache_boundary"]="all caches are raw"
    elif case=="nonclaim": e["method"]["not_claimed"].pop()
    else: e["summary"]["raw_cache_records"]=2
    with pytest.raises(NativeLuaCClosureGcMetatableConsumersError): _structure(values,e)

def test_exact_real_rebuild_and_verify(values):
    if not EXE.is_file(): pytest.skip("sealed executable unavailable")
    rebuilt=build_native_lua_cclosure_gc_metatable_consumers(EXE,values["direct"],values["callbacks"],values["setfield"],values["direct_setters"],values["indirect"],values["keys"],values["facts"],inventory=values["inventory"])
    assert rebuilt==values["evidence"]
    assert validate_native_lua_cclosure_gc_metatable_consumers(EXE,values["evidence"],values["direct"],values["callbacks"],values["setfield"],values["direct_setters"],values["indirect"],values["keys"],values["facts"],inventory=values["inventory"])["status"]=="verified"


def test_cli_parser_exposes_complete_prerequisite_surface():
    args=cli.build_parser().parse_args(["verify","--executable","game.exe","--inventory","inventory.json","--program-facts","facts.json","--direct-calls","direct.json","--callbacks","callbacks.json","--setfield-publications","setfield.json","--direct-table-setter-publications","direct-setters.json","--indirect-settable-publications","indirect.json","--table-key-provenance","keys.json","--evidence","evidence.json"])
    assert args.command=="verify"
    assert args.table_key_provenance.name=="keys.json"
    assert args.direct_table_setter_publications.name=="direct-setters.json"


def test_cli_writer_is_immutable(tmp_path,values,monkeypatch):
    monkeypatch.setattr(cli,"_OUT",tmp_path)
    monkeypatch.setattr(cli,"_output_root",lambda:tmp_path)
    output=tmp_path/"gc.json"; rendered=subject.encode_native_lua_cclosure_gc_metatable_consumers(values["evidence"])
    cli._write(output,rendered,values["evidence"])
    assert output.read_text(encoding="utf-8")==rendered
    cli._write(output,rendered,values["evidence"])
    output.write_text(rendered+" ",encoding="utf-8")
    with pytest.raises(NativeLuaCClosureGcMetatableConsumersError,match="refusing to overwrite"):
        cli._write(output,rendered,values["evidence"])


def test_staged_proof_rejects_modeled_interior_entry(values):
    facts=copy.deepcopy(values["facts"])
    facts["ghidra_declared_direct_calls"].append({"instruction_rva":"0x00001000","source_entry_rva":"0x00001000","target_rva":"0x002e6901"})
    with pytest.raises(NativeLuaCClosureGcMetatableConsumersError,match="alternate modeled entry"):
        subject._core_body_records(facts,values["direct"])


def test_cli_writer_rejects_existing_symlink(tmp_path,values,monkeypatch):
    monkeypatch.setattr(cli,"_OUT",tmp_path)
    monkeypatch.setattr(cli,"_output_root",lambda:tmp_path)
    target=tmp_path/"target.json"; target.write_text(subject.encode_native_lua_cclosure_gc_metatable_consumers(values["evidence"]),encoding="utf-8")
    output=tmp_path/"gc.json"
    try: output.symlink_to(target)
    except OSError as exc: pytest.skip(f"symlink creation unavailable: {exc}")
    with pytest.raises(NativeLuaCClosureGcMetatableConsumersError,match="not a real programs file"):
        cli._write(output,target.read_text(encoding="utf-8"),values["evidence"])


def test_cli_writer_rejects_existing_reparse_point(tmp_path,values,monkeypatch):
    monkeypatch.setattr(cli,"_OUT",tmp_path)
    monkeypatch.setattr(cli,"_output_root",lambda:tmp_path)
    output=tmp_path/"gc.json"; rendered=subject.encode_native_lua_cclosure_gc_metatable_consumers(values["evidence"])
    output.write_text(rendered,encoding="utf-8")
    monkeypatch.setattr(cli,"_is_reparse",lambda path:path==output)
    with pytest.raises(NativeLuaCClosureGcMetatableConsumersError,match="not a real programs file"):
        cli._write(output,rendered,values["evidence"])
