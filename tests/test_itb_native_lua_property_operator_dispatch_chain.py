from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import itb_native_lua_property_operator_dispatch_chain as operator_cli

from src.observatory import native_lua_property_operator_dispatch_chain as operator
from src.observatory.native_lua_property_operator_dispatch_chain import (
    NativeLuaPropertyOperatorDispatchChainError,
    encode_native_lua_property_operator_dispatch_chain,
    validate_native_lua_property_operator_dispatch_chain_structure,
)


ROOT=Path(__file__).resolve().parents[1]
PROGRAMS=ROOT/"data"/"observatory"/"programs"
INVENTORIES=ROOT/"data"/"observatory"/"inventories"
PREFIX="windows_build_13725832_31fe35265598_"
EXE=Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
EXE_SHA256="31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
RAW_SHA256="6b3a33905b8a36463e32fbda680ad86fe21d4ae04dea6cab59bf7b2c4ff0f239"
CANONICAL_SHA256="7db59f62fc9d70e3b2338bc0349afae91ee8c7b34099cd3b034c6c240b035fdc"


def _read(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values() -> dict[str,dict]:
    names={"facts":"program_facts.json","direct":"native_lua_direct_call_census.json","callbacks":"native_lua_cclosure_callbacks.json","setfield":"native_lua_cclosure_setfield_publications.json","direct_table":"native_lua_cclosure_table_setter_publications.json","indirect":"native_lua_cclosure_indirect_settable_publications.json","keys":"native_lua_cclosure_table_key_provenance.json","terminal":"native_lua_cclosure_terminal_dispositions.json","property":"native_lua_property_factory_chain.json","consumer":"native_lua_property_consumer_chain.json","initializer":"native_lua_property_initializer_chain.json","evidence":"native_lua_property_operator_dispatch_chain.json"}
    paths={k:PROGRAMS/(PREFIX+v) for k,v in names.items()}
    paths["inventory"]=INVENTORIES/(PREFIX+"full_decompile_baseline_20260830.json")
    if any(not path.is_file() for path in paths.values()): pytest.skip("operator-chain evidence is unavailable")
    return {k:_read(v) for k,v in paths.items()}


def _args(v: dict[str,dict]) -> tuple[dict,...]: return (v["initializer"],v["consumer"],v["property"],v["direct"],v["callbacks"],v["setfield"],v["direct_table"],v["indirect"],v["keys"],v["terminal"],v["facts"])


def _receipt(v: dict[str,dict]) -> dict:
    return {"analysis_kind":operator.INITIALIZER_STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","evidence_sha256":operator._INIT_SHA,"build_identity":copy.deepcopy(v["initializer"]["build_identity"])}


def _fast(monkeypatch: pytest.MonkeyPatch,evidence: dict,v: dict[str,dict]):
    monkeypatch.setattr(operator,"validate_native_lua_property_initializer_chain_structure",lambda *args,**kwargs:_receipt(v))
    return validate_native_lua_property_operator_dispatch_chain_structure(evidence,*_args(v))


def test_encoding_and_summary(values):
    evidence=values["evidence"]
    payload=(PROGRAMS/(PREFIX+"native_lua_property_operator_dispatch_chain.json")).read_bytes()
    assert hashlib.sha256(payload).hexdigest()==RAW_SHA256
    assert operator._canonical_sha256(evidence)==CANONICAL_SHA256
    assert encode_native_lua_property_operator_dispatch_chain(evidence).encode()==payload
    assert evidence["summary"]=={"initializer_prerequisite_count":1,"source_body_count":2,"source_body_bytes":395,"source_cfg_node_count":155,"source_cfg_edge_count":159,"direct_lua_call_count":20,"staged_lua_call_count":4,"literal_count":1,"target_reference_count":77,"wrapper_closure_producer_count":1,"recognizer_direct_call_reference_count":76,"recognizer_owner_count":76,"schema_violations":0}


def test_structure_and_exact_partitions(monkeypatch,values):
    assert _fast(monkeypatch,values["evidence"],values)["status"]=="structurally_verified"
    wrapper=values["evidence"]["source_bodies"][0]
    assert [len(x["calls"]) for x in wrapper["staged_lua_calls"]]==[2,2]
    assert wrapper["staged_lua_calls"][0]["calls"][1]["last_definition_stage_rvas"]==["0x002ea22b","0x002ea23b"]
    refs=values["evidence"]["target_reference_scan"]["references"]
    assert len(refs)==77 and len({x["owner_entry_rva"] for x in refs[:-1]})==76


def test_committed_artifact_full_structural_validation(values):
    receipt=validate_native_lua_property_operator_dispatch_chain_structure(values["evidence"],*_args(values))
    assert receipt["status"]=="structurally_verified"
    assert receipt["evidence_sha256"]==CANONICAL_SHA256


def test_committed_artifact_exact_rebuild_and_verification(values):
    if not EXE.is_file() or hashlib.sha256(EXE.read_bytes()).hexdigest()!=EXE_SHA256:
        pytest.skip("sealed Breach.exe is unavailable")
    rebuilt=operator.build_native_lua_property_operator_dispatch_chain(
        EXE,*_args(values),inventory=values["inventory"]
    )
    assert rebuilt==values["evidence"]
    receipt=operator.validate_native_lua_property_operator_dispatch_chain(
        EXE,values["evidence"],*_args(values),inventory=values["inventory"]
    )
    assert receipt["status"]=="verified"
    assert receipt["evidence_sha256"]==CANONICAL_SHA256


@pytest.mark.parametrize("path,replacement",[
    (("initializer_chain","canonical_sha256"),"0"*64),
    (("source_bodies",0,"body_sha256"),"1"*64),
    (("source_bodies",0,"direct_lua_calls",0,"api"),"lua_rawget"),
    (("source_bodies",1,"direct_lua_calls",4,"rva"),"0x00000000"),
    (("source_bodies",0,"staged_lua_calls",0,"stages",0,"rva"),"0x002ea23b"),
    (("source_bodies",0,"staged_lua_calls",1,"stages",0,"instruction_sha256"),"0"*64),
    (("source_bodies",0,"staged_lua_calls",0,"calls",0,"rva"),"0x002ea25c"),
    (("source_bodies",0,"staged_lua_calls",0,"calls",1,"last_definition_stage_rvas"),["0x002ea23b"]),
    (("source_bodies",0,"call_r32_audit",3,"call_rvas"),["0x002ea234"]),
    (("initializer_wrapper_placement","callback_entry_rva"),"0x00000000"),
    (("initializer_wrapper_placement","upvalue_order"),["B","K"]),
    (("initializer_wrapper_placement","true_boolean_indices"),[9]),
    (("literal","text"),"other"),
    (("literal","nul_terminated_bytes_sha256"),"0"*64),
    (("literal","section_characteristics"),"0x80000040"),
    (("target_reference_scan","references",0,"instruction_sha256"),"0"*64),
    (("target_reference_scan","references",0,"target_rva"),"0x00000000"),
    (("target_reference_scan","references",0,"owner_entry_rva"),"0x00000000"),
    (("target_reference_scan","references",0,"operand_class"),"absolute_memory"),
    (("target_reference_scan","references",0,"operand_index"),1),
    (("target_reference_scan","references"),[]),
    (("semantics","wrapper_two_input_search","examined_input_indices"),[1,2,3]),
    (("semantics","wrapper_two_input_search","never_examines_input_index"),4),
    (("semantics","wrapper_two_input_search","marker","getter_callback_entry_rva"),"0x00000000"),
    (("semantics","wrapper_two_input_search","key_upvalue_index"),-10004),
    (("semantics","wrapper_two_input_search","boolean_upvalue_index"),-10003),
    (("semantics","wrapper_two_input_search","nil_candidate_cleanup_index"),-3),
    (("semantics","wrapper_two_input_search","success","boolean_read_count"),1),
    (("semantics","wrapper_two_input_search","success","false_nargs"),1),
    (("semantics","wrapper_two_input_search","success","true_remove_absolute_index"),2),
    (("semantics","wrapper_two_input_search","success","lua_call_result_count"),0),
    (("semantics","wrapper_two_input_search","error_clear_index_formula"),"-top"),
    (("semantics","wrapper_two_input_search","error_normal_return_claimed"),True),
    (("semantics","recognizer_predicate","state_register"),"EDX"),
    (("semantics","recognizer_predicate","index_register"),"ECX"),
    (("semantics","recognizer_predicate","requires_non_null_conversion_result"),False),
    (("semantics","recognizer_predicate","requires_getmetatable_success"),False),
    (("semantics","recognizer_predicate","getter_callback_entry_rva"),"0x00000000"),
    (("semantics","recognizer_predicate","cleanup_index"),-2),
    (("semantics","recognizer_predicate","match_returns_original_conversion_result"),False),
    (("semantics","recognizer_predicate","pointer_type_identity_claimed"),True),
    (("semantics","recognizer_predicate","caller_semantics_claimed"),True),
    (("summary","recognizer_owner_count"),75),
])
def test_structure_rejects_semantic_and_partition_mutation(monkeypatch,values,path,replacement):
    evidence=copy.deepcopy(values["evidence"]); cursor=evidence
    for key in path[:-1]: cursor=cursor[key]
    cursor[path[-1]]=replacement
    with pytest.raises(NativeLuaPropertyOperatorDispatchChainError): _fast(monkeypatch,evidence,values)


def test_structure_rejects_unknown_field(monkeypatch,values):
    evidence=copy.deepcopy(values["evidence"]); evidence["extra"]=True
    with pytest.raises(NativeLuaPropertyOperatorDispatchChainError): _fast(monkeypatch,evidence,values)


@pytest.mark.parametrize("audit_index",range(8))
def test_structure_rejects_each_call_r32_audit_row(monkeypatch,values,audit_index):
    evidence=copy.deepcopy(values["evidence"])
    evidence["source_bodies"][0]["call_r32_audit"][audit_index]["opcode_hex"]="ffd9"
    with pytest.raises(NativeLuaPropertyOperatorDispatchChainError): _fast(monkeypatch,evidence,values)


def test_structure_rejects_initializer_receipt_mismatch(monkeypatch,values):
    monkeypatch.setattr(operator,"validate_native_lua_property_initializer_chain_structure",lambda *args,**kwargs:{"analysis_kind":operator.INITIALIZER_STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","evidence_sha256":"0"*64})
    with pytest.raises(NativeLuaPropertyOperatorDispatchChainError): validate_native_lua_property_operator_dispatch_chain_structure(values["evidence"],*_args(values))


def test_cli_parser_has_full_prerequisite_surface():
    args=operator_cli.build_parser().parse_args([
        "verify",
        "--executable","Breach.exe",
        "--inventory","inventory.json",
        "--program-facts","facts.json",
        "--direct-calls","direct.json",
        "--callbacks","callbacks.json",
        "--setfield-publications","setfield.json",
        "--direct-table-setter-publications","direct-table.json",
        "--indirect-settable-publications","indirect.json",
        "--table-key-provenance","keys.json",
        "--terminal-dispositions","terminal.json",
        "--property-factory-chain","property.json",
        "--property-consumer-chain","consumer.json",
        "--property-initializer-chain","initializer.json",
        "--evidence","operator.json",
    ])
    assert args.command=="verify"
    assert args.property_initializer_chain==Path("initializer.json")
    assert args.evidence==Path("operator.json")


def test_cli_immutable_writer(tmp_path,monkeypatch,values):
    monkeypatch.setattr(operator_cli,"_prepare_output_root",lambda:(tmp_path,tmp_path,object()))
    monkeypatch.setattr(operator_cli,"_recheck_output_root",lambda *args:None)
    destination=tmp_path/"operator.json"; value=copy.deepcopy(values["evidence"]); rendered=encode_native_lua_property_operator_dispatch_chain(value)
    operator_cli._write_immutably(destination,rendered,value)
    operator_cli._write_immutably(destination,rendered,value)
    changed=copy.deepcopy(value); changed["summary"]["target_reference_count"]=0
    with pytest.raises(NativeLuaPropertyOperatorDispatchChainError): operator_cli._write_immutably(destination,encode_native_lua_property_operator_dispatch_chain(changed),changed)
