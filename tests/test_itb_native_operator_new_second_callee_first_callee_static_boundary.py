"""Focused fail-closed coverage for the opaque ``0x00358477`` boundary."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import struct
import threading
from pathlib import Path
from typing import Any

import pytest

from scripts import itb_native_operator_new_second_callee_first_callee_static_boundary as cli
from src.observatory import native_operator_new_second_callee_first_callee_static_boundary as helper
from src.observatory.native_operator_new_second_callee_first_callee_static_boundary import NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS, INVENTORIES = ROOT / "data" / "observatory" / "programs", ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
RAW_SHA256 = "7837f58f2f0b08968e29d42cb0e6da4aa405962e12b8ce956c9c8be187d2abc8"
CANONICAL_SHA256 = "a82567f379b942b53f80b1f739a488e7de2637ea39e318f7a928af37900ae262"

def _read(path: Path) -> dict[str, Any]: return json.loads(path.read_text(encoding="utf-8"))

@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    paths = {"inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"), "facts": PROGRAMS / (PREFIX + "program_facts.json"), "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"), "predecessor": PROGRAMS / (PREFIX + "native_operator_new_second_callee_static_boundary.json"), "evidence": PROGRAMS / (PREFIX + "native_operator_new_second_callee_first_callee_static_boundary.json")}
    if any(not path.is_file() for path in paths.values()): pytest.skip("first-callee receipt prerequisites are unavailable")
    result = {name: _read(path) for name, path in paths.items()}; result["paths"] = paths; return result

def _common(v): return v["predecessor"], v["direct"], v["facts"]
def _structure(v, e=None): return helper.validate_native_operator_new_second_callee_first_callee_static_boundary_structure(v["evidence"] if e is None else e, *_common(v))
def _replace(value, path, replacement):
    if not path: return replacement
    clone = dict(value) if isinstance(value, dict) else list(value); clone[path[0]] = _replace(value[path[0]], path[1:], replacement); return clone
def _add(value, path):
    clone = copy.deepcopy(value); cursor = clone
    for key in path[:-1]: cursor = cursor[key]
    cursor[path[-1]] = True; return clone
def _reject(v, e):
    with pytest.raises(NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError): _structure(v, e)
def _exact_executable():
    configured = os.environ.get("ITB_EXACT_EXE")
    if not configured: pytest.skip("set ITB_EXACT_EXE to run expensive exact PE checks")
    path = Path(configured)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != EXE_SHA256: pytest.skip("ITB_EXACT_EXE is not the sealed Breach.exe build")
    return path

def test_decoder_cfg_terminal_and_no_runtime_claim():
    rows = helper._decode()
    assert b"".join(bytes(row.bytes) for row in rows).hex() == helper._RAW
    assert [(row.address-helper._BASE, bytes(row.bytes).hex()) for row in rows] == [(0x358477,"83610400"),(0x35847b,"8bc1"),(0x35847d,"83610800"),(0x358481,"c741040c1a7f00"),(0x358488,"c701041a7f00"),(0x35848e,"c3")]
    graph = helper._graph(rows)
    assert (graph["node_count"], graph["edge_count"], helper._canonical_sha256(graph)) == (6,5,helper._CFG)
    assert graph["nodes"][-1]["flow_kind"] == "terminal" and graph["nodes"][-1]["successor_rvas"] == []

def test_committed_encoding_structure_and_empty_outgoing_partition(values):
    raw = values["paths"]["evidence"].read_bytes(); evidence = values["evidence"]
    assert raw == helper.encode_native_operator_new_second_callee_first_callee_static_boundary(evidence).encode()
    assert hashlib.sha256(raw).hexdigest() == RAW_SHA256 and helper._canonical_sha256(evidence) == CANONICAL_SHA256
    assert _structure(values)["status"] == "structurally_verified"
    calls = evidence["native_calls"]
    assert calls["outgoing_direct"] == [] and calls["outgoing_direct_partition_complete"] is True
    assert [(x["operand_va"],x["operand_rva"],x["file_offset"]) for x in calls["pe_address_operands"]] == [("0x007f1a0c","0x003f1a0c","0x003f0a0c"),("0x007f1a04","0x003f1a04","0x003f0a04")]
    assert calls["non_pe_immediate_literals"] == [{"instruction_rva":"0x00358477","operand_index":1,"value":"0x00000000"},{"instruction_rva":"0x0035847d","operand_index":1,"value":"0x00000000"}]

def test_reference_receipt_and_parent_join(values):
    scan = values["evidence"]["whole_atlas_reference_scan"]
    assert scan["scope"] == helper._SCOPE and scan["partition_sha256"] == helper._PARTITION_HASHES
    assert scan["references_canonical_sha256"] == helper._REFERENCE_HASH
    assert [(x["instruction_rva"],x["owner_entry_rva"],x["target_rva"],x["operand_class"]) for x in scan["references"]] == [("0x00358498","0x0035848f","0x00358477","immediate")]
    assert values["evidence"]["predecessor_parent_edges"][0]["instruction"]["rva"] == scan["references"][0]["instruction_rva"]

@pytest.mark.parametrize("path",[("analysis_kind",),("function_body","body_size"),("control_flow_graph","nodes",-1,"flow_kind"),("native_calls","outgoing_direct_partition_complete"),("native_calls","pe_address_operands",0,"file_backed"),("whole_atlas_reference_scan","references",0,"owner_entry_rva"),("summary","native_direct_edge_count")])
def test_structure_rejects_mutation(values,path): _reject(values,_replace(values["evidence"],path,False if path[-1] != "flow_kind" else "fallthrough"))

@pytest.mark.parametrize("path",[("unexpected",),("function_body","unexpected"),("native_calls","unexpected"),("whole_atlas_reference_scan","references",0,"unexpected")])
def test_structure_rejects_unknown_keys(values,path): _reject(values,_add(values["evidence"],path))

def test_empty_outgoing_partition_fails_if_program_facts_gain_source_edge(values):
    facts = copy.deepcopy(values["facts"])
    facts["ghidra_declared_direct_calls"].append({"instruction_rva":"0x00358477","source_entry_rva":"0x00358477","target_entry_rva":"0x00358477","target_rva":"0x00358477","target_name":"injected"})
    with pytest.raises(NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError,match="outgoing native"):
        helper._native_calls(facts)

def test_encoder_and_normalization_reject_bad_values():
    with pytest.raises(NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError): helper.encode_native_operator_new_second_callee_first_callee_static_boundary([])
    with pytest.raises(NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError): helper.encode_native_operator_new_second_callee_first_callee_static_boundary({"value":float("nan")})
    with pytest.raises(NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError,match="injected"):
        helper._normalize(lambda: (_ for _ in ()).throw(struct.error("injected")))

def test_cli_parser_surface():
    common=[]
    for flag in ("--operator-new-second-callee-static-boundary","--direct-calls","--program-facts"): common += [flag,"input.json"]
    assert cli.build_parser().parse_args(["build",*common,"--executable","Breach.exe","--inventory","inventory.json","--output","out.json"]).command == "build"
    assert cli.build_parser().parse_args(["verify-structure",*common,"--evidence","out.json"]).command == "verify-structure"

def test_exact_rebuild_verify_and_scanner_regressions(values,monkeypatch):
    executable = _exact_executable(); data,image,digest = helper._load_executable(executable); assert digest == EXE_SHA256
    rebuilt = helper.build_native_operator_new_second_callee_first_callee_static_boundary(executable,*_common(values),inventory=values["inventory"])
    assert rebuilt == values["evidence"]
    baseline,_ = helper._decoder(); assert helper._whole_atlas_reference_scan(data,image,baseline,values["facts"]) == helper._expected_scan(values["facts"])
    actual = helper._decode_range
    import capstone
    for injected in ("b877847500","a177847500"):
        def altered(data,image,start,size,decoder,injected=injected):
            rows=actual(data,image,start,size,decoder)
            if start == 0x35848F:
                d=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32); d.detail=True; replacement=list(d.disasm(bytes.fromhex(injected),image.image_base+0x35849D))
                assert len(replacement)==1 and replacement[0].size==rows[5].size; rows[5]=replacement[0]
            return rows
        monkeypatch.setattr(helper,"_decode_range",altered); decoder,_=helper._decoder()
        with pytest.raises(NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError,match="all-operand"): helper._whole_atlas_reference_scan(data,image,decoder,values["facts"])
        monkeypatch.setattr(helper,"_decode_range",actual)

@pytest.mark.parametrize("path",[
    ("schema_version",),("build_identity",),("program_facts",),("predecessor_static_boundary",),("direct_call_census",),("decoder",),("function_body",),("control_flow_graph",),("predecessor_parent_edges",),("native_calls",),("whole_atlas_reference_scan",),("method",),("summary",),
    ("function_body","reviewed_points",0,"sha256"),("function_body","ghidra_analysis_metadata","thunk"),("control_flow_graph","nodes",0,"successor_rvas"),("predecessor_parent_edges",0,"instruction","sha256"),("native_calls","pe_address_operands",0,"operand_rva"),("native_calls","non_pe_immediate_literals",0,"value"),("whole_atlas_reference_scan","owner_partition",0,"reference_count"),("whole_atlas_reference_scan","partition_sha256","owner_partition"),("method","not_claimed"),("summary","pe_address_operand_count"),
])
def test_structure_rejects_all_retained_categories(values,path):
    old=values["evidence"]
    for key in path: old=old[key]
    replacement = "changed" if not isinstance(old,(bool,int,list,dict)) else (not old if isinstance(old,bool) else (old+1 if isinstance(old,int) else ([] if isinstance(old,list) else {})))
    _reject(values,_replace(values["evidence"],path,replacement))

@pytest.mark.parametrize("value",[[],{"value":float("nan")}, {"value":float("inf")}, {"value":{1:"bad"}}])
def test_encoder_rejects_all_non_json_trees(value):
    with pytest.raises(NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError): helper.encode_native_operator_new_second_callee_first_callee_static_boundary(value)

def _patch_output_root(monkeypatch,tmp_path):
    info=tmp_path.stat(); monkeypatch.setattr(cli,"_prepare_output_root",lambda:(tmp_path,tmp_path,info)); monkeypatch.setattr(cli,"_recheck_output_root",lambda *args:None)

def test_cli_writer_immutable_and_preserves_differing_destination(tmp_path,monkeypatch,values):
    _patch_output_root(monkeypatch,tmp_path); output=tmp_path/"evidence.json"; rendered=helper.encode_native_operator_new_second_callee_first_callee_static_boundary(values["evidence"])
    cli._write_immutably(output,rendered,values["evidence"]); cli._write_immutably(output,rendered,values["evidence"])
    output.write_bytes(rendered.encode("utf-8")+b" ")
    with pytest.raises(NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError,match="refusing to overwrite"): cli._write_immutably(output,rendered,values["evidence"])
    assert output.read_text(encoding="utf-8").endswith(" ")

def test_cli_writer_detects_same_inode_race_and_preserves_destination(tmp_path,monkeypatch,values):
    _patch_output_root(monkeypatch,tmp_path); output=tmp_path/"evidence.json"; rendered=helper.encode_native_operator_new_second_callee_first_callee_static_boundary(values["evidence"]); output.write_bytes(rendered.encode("utf-8"))
    original,calls=cli._read_json_document,[]
    def mutate(path,label):
        result=original(path,label); calls.append(1)
        if len(calls)==1:
            with path.open("ab") as stream: stream.write(b" ")
        return result
    monkeypatch.setattr(cli,"_read_json_document",mutate)
    with pytest.raises(NativeOperatorNewSecondCalleeFirstCalleeStaticBoundaryError,match="final content validation"): cli._write_immutably(output,rendered,values["evidence"])
    assert output.exists()

def test_cli_writer_final_lock_blocks_cooperating_writer(tmp_path,monkeypatch,values):
    _patch_output_root(monkeypatch,tmp_path); output=tmp_path/"evidence.json"; rendered=helper.encode_native_operator_new_second_callee_first_callee_static_boundary(values["evidence"]); output.write_bytes(rendered.encode("utf-8"))
    reader,attempts=cli._read_locked_json_document,[]
    def contender():
        try:
            with output.open("ab") as stream: stream.write(b" ")
        except OSError: attempts.append("blocked")
        else: attempts.append("mutated")
    def during(fd,label):
        result=reader(fd,label); thread=threading.Thread(target=contender);thread.start();thread.join(5);return result
    monkeypatch.setattr(cli,"_read_locked_json_document",during); cli._write_immutably(output,rendered,values["evidence"])
    assert attempts == ["blocked"]

def test_cli_reports_strict_json_error(tmp_path,capsys):
    bad=tmp_path/"bad.json";bad.write_text('{"x":NaN}',encoding="utf-8")
    args=["verify","--operator-new-second-callee-static-boundary",str(bad),"--direct-calls",str(bad),"--program-facts",str(bad),"--executable",str(bad),"--inventory",str(bad),"--evidence",str(bad)]
    assert cli.main(args)==1 and capsys.readouterr().err.startswith("error: ")

def test_public_exact_validate_and_cli_verify(values,capsys):
    executable=_exact_executable()
    receipt=helper.validate_native_operator_new_second_callee_first_callee_static_boundary(executable,values["evidence"],*_common(values),inventory=values["inventory"])
    assert receipt["status"]=="verified" and receipt["evidence_sha256"]==CANONICAL_SHA256
    p=values["paths"]
    assert cli.main(["verify","--operator-new-second-callee-static-boundary",str(p["predecessor"]),"--direct-calls",str(p["direct"]),"--program-facts",str(p["facts"]),"--inventory",str(p["inventory"]),"--executable",str(executable),"--evidence",str(p["evidence"])])==0
    assert '"status": "verified"' in capsys.readouterr().out
