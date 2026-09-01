"""Exact and adversarial tests for the query-handler first callee boundary."""
from __future__ import annotations
import copy, hashlib, json, os, threading
from pathlib import Path
import pytest
from scripts import itb_native_query_handler_first_callee_static_boundary as cli
from src.observatory import native_query_handler_first_callee_static_boundary as callee
from src.observatory.native_query_handler_first_callee_static_boundary import NativeQueryHandlerFirstCalleeStaticBoundaryError

ROOT = Path(__file__).resolve().parents[1]; PROGRAMS = ROOT / "data" / "observatory" / "programs"; INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"; EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
EXE_SHA = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"; RAW = "f4d43affe98441996f1d10086438c93136b181665c2039b9b1ae18beb618e6b4"; CANONICAL = "b08dc12a2f4951817e4e7c24dbdfc4afec03550c2828d7d14c1d757404517d73"
def _read(path): return json.loads(path.read_text(encoding="utf-8"))
@pytest.fixture(scope="module")
def values():
    paths = {"inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"), "facts": PROGRAMS / (PREFIX + "program_facts.json"), "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"), "query_handler": PROGRAMS / (PREFIX + "native_query_new_handler_static_boundary.json"), "evidence": PROGRAMS / (PREFIX + "native_query_handler_first_callee_static_boundary.json")}
    value = {key: _read(path) for key, path in paths.items()}; value["paths"] = paths; return value
def _common(v): return v["query_handler"], v["direct"], v["facts"]
def _structure(v, evidence=None): return callee.validate_native_query_handler_first_callee_static_boundary_structure(v["evidence"] if evidence is None else evidence, *_common(v))
def _replace(value, path, replacement):
    if not path: return replacement
    result = dict(value) if isinstance(value, dict) else list(value); result[path[0]] = _replace(value[path[0]], path[1:], replacement); return result
def _add(value, path, replacement):
    if len(path) == 1: result = dict(value); result[path[0]] = replacement; return result
    result = dict(value) if isinstance(value, dict) else list(value); result[path[0]] = _add(value[path[0]], path[1:], replacement); return result
def _changed(value):
    if isinstance(value, bool): return not value
    if isinstance(value, int): return value + 1
    if isinstance(value, str): return "changed"
    if isinstance(value, list): return [] if value else ["changed"]
    return {}
def _fast(monkeypatch, v, evidence):
    monkeypatch.setattr(callee, "validate_native_lua_direct_call_structure", lambda *a, **k: {"status": "structurally_verified", "evidence_sha256": callee._DIRECT})
    monkeypatch.setattr(callee, "_expected_scan", lambda *a, **k: copy.deepcopy(v["evidence"]["whole_atlas_reference_scan"]))
    return _structure(v, evidence)
def _reject(monkeypatch, v, evidence):
    with pytest.raises(NativeQueryHandlerFirstCalleeStaticBoundaryError): _fast(monkeypatch, v, evidence)

def test_receipts_partition_opaque_syntax_and_nonclaims(values):
    evidence = values["evidence"]; raw = values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW; assert raw == callee.encode_native_query_handler_first_callee_static_boundary(evidence).encode(); assert callee._canonical_sha256(evidence) == CANONICAL; assert _structure(values)["evidence_sha256"] == CANONICAL
    body, graph = evidence["function_bodies"][0], evidence["control_flow_graphs"][0]
    assert (body["entry_rva"], body["body_size"], body["body_sha256"], body["control_flow_graph_canonical_sha256"]) == ("0x003584b0", 70, callee._BODY, callee._CFG); assert (graph["node_count"], graph["edge_count"], len(body["reviewed_points"])) == (21, 20, 21)
    assert body["direct_lua_calls"] == [] and body["staged_lua_dispatches"] == [] and body["call_r32_audit"] == [{"register": name, "call_rvas": []} for name in callee._REGISTER_NAMES]
    scan = evidence["whole_atlas_reference_scan"]; assert scan["aggregates"] == {"reference_count": 66, "direct_call_count": 66, "comparison_count": 0, "other_address_count": 0, "memory_operand_count": 0, "owner_count": 66}; assert len(scan["references"]) == len(scan["owner_partition"]) == 66; assert len({row["owner_entry_rva"] for row in scan["owner_partition"]}) == 66
    assert all((row["instruction_size"], row["operand_class"], row["use_class"], row["call_form"]) == (5, "immediate", "direct_call", "x86_relative_near_call_e8") for row in scan["references"])
    predecessor = evidence["query_handler_first_callee_predecessor_edge"]; assert (predecessor["source_entry_rva"], predecessor["instruction"]["rva"], predecessor["target_entry_rva"]) == ("0x0038bc08", "0x0038bc0f", "0x003584b0")
    records = evidence["native_calls"]["opaque_instruction_syntax"]; assert [item["role"] for item in records] == ["opaque_absolute_immediate_push_syntax", "opaque_segment_relative_memory_push_syntax", "opaque_absolute_memory_read_syntax", "opaque_segment_relative_memory_write_syntax", "opaque_bnd_prefixed_return_syntax"]
    for word in ("SEH", "prolog", "exception", "stack", "register", "security-cookie", "ABI", "runtime", "normal return", "Lua-side"): assert any(word.lower() in text.lower() for text in evidence["method"]["not_claimed"])

def test_exact_rebuild(values):
    if not EXE.is_file() or hashlib.sha256(EXE.read_bytes()).hexdigest() != EXE_SHA: pytest.skip("sealed executable unavailable")
    rebuilt = callee.build_native_query_handler_first_callee_static_boundary(EXE, *_common(values), inventory=values["inventory"]); assert rebuilt == values["evidence"]; assert callee.validate_native_query_handler_first_callee_static_boundary(EXE, values["evidence"], *_common(values), inventory=values["inventory"])["status"] == "verified"

@pytest.mark.parametrize("path", [("unexpected",), ("function_bodies", 0, "unexpected"), ("native_calls", "opaque_instruction_syntax", 0, "unexpected"), ("whole_atlas_reference_scan", "references", 0, "unexpected"), ("whole_atlas_reference_scan", "owner_partition", 0, "unexpected")])
def test_unknown_keys_reject(values, monkeypatch, path): _reject(monkeypatch, values, _add(values["evidence"], path, True))
@pytest.mark.parametrize("key", ["returned_callback_reference_count", "alternate_owner_reference_count"])
def test_stale_inherited_reference_aggregate_keys_reject(values, monkeypatch, key): _reject(monkeypatch, values, _add(values["evidence"], ("whole_atlas_reference_scan", "aggregates", key), 0))
@pytest.mark.parametrize("path", [("schema_version",), ("function_bodies", 0, "body_size"), ("function_bodies", 0, "reviewed_points", 0, "sha256"), ("query_handler_first_callee_predecessor_edge", "instruction", "sha256"), ("whole_atlas_reference_scan", "owner_partition", 0, "owner_entry_rva")])
def test_core_tamper_rejects(values, monkeypatch, path):
    item = values["evidence"]
    for key in path: item = item[key]
    _reject(monkeypatch, values, _replace(values["evidence"], path, _changed(item)))
@pytest.mark.parametrize("record_index,field", [(index, field) for index, fields in enumerate((("role", "instruction", "operand_va", "operand_rva", "section_name", "section_characteristics", "section_writable", "file_backed", "contents_or_semantics_opaque"), ("role", "instruction", "source_memory_operand_index", "segment_register", "base_register", "index_register", "displacement", "contents_or_semantics_opaque"), ("role", "instruction", "operand_va", "operand_rva", "section_name", "section_characteristics", "section_writable", "file_backed", "contents_or_semantics_opaque"), ("role", "instruction", "destination_memory_operand_index", "segment_register", "base_register", "index_register", "displacement", "contents_or_semantics_opaque"), ("role", "instruction", "encoded_prefix_hex", "contents_or_semantics_opaque"))) for field in fields])
def test_every_opaque_operand_record_field_rejects(values, monkeypatch, record_index, field):
    item = values["evidence"]["native_calls"]["opaque_instruction_syntax"][record_index][field]; _reject(monkeypatch, values, _replace(values["evidence"], ("native_calls", "opaque_instruction_syntax", record_index, field), _changed(item)))
@pytest.mark.parametrize("path,replacement", [(("schema_version",), True), (("function_bodies", 0, "body_size"), True), (("control_flow_graphs", 0, "nodes", 0, "size"), True), (("whole_atlas_reference_scan", "references", 0, "operand_index"), True), (("whole_atlas_reference_scan", "owner_partition", 0, "reference_count"), True), (("native_calls", "opaque_instruction_syntax", 3, "destination_memory_operand_index"), True), (("native_calls", "opaque_instruction_syntax", 3, "contents_or_semantics_opaque"), 1), (("native_calls", "opaque_instruction_syntax", 1, "segment_register"), [])])
def test_bool_as_int_and_wrong_container_types_reject(values, monkeypatch, path, replacement): _reject(monkeypatch, values, _replace(values["evidence"], path, replacement))
def test_missing_or_tampered_owner_partition_rejects(values, monkeypatch):
    evidence = copy.deepcopy(values["evidence"]); del evidence["whole_atlas_reference_scan"]["owner_partition"]; _reject(monkeypatch, values, evidence)
    _reject(monkeypatch, values, _replace(values["evidence"], ("whole_atlas_reference_scan", "references", 6, "owner_atlas_record_sha256"), "changed"))
def test_predecessor_exact_byte_receipt_rejects(values):
    query_handler = copy.deepcopy(values["query_handler"]); edge = next(item for item in query_handler["native_calls"]["direct"] if item["instruction"]["rva"] == "0x0038bc0f"); edge["instruction"]["sha256"] = "changed"
    with pytest.raises(NativeQueryHandlerFirstCalleeStaticBoundaryError, match="instruction bytes"): callee._predecessor(query_handler, values["evidence"]["whole_atlas_reference_scan"])
def test_structure_requires_direct_prerequisite_status(values, monkeypatch):
    monkeypatch.setattr(callee, "validate_native_lua_direct_call_structure", lambda *a, **k: {"status": "verified", "evidence_sha256": callee._DIRECT})
    with pytest.raises(NativeQueryHandlerFirstCalleeStaticBoundaryError, match="prerequisite"): _structure(values)
@pytest.mark.parametrize("path", [("schema_version",), ("analysis_kind",), ("build_identity",), ("atlas",), ("direct_call_census",), ("query_handler_static_boundary",), ("query_handler_first_callee_predecessor_edge",), ("decoder",), ("function_bodies",), ("control_flow_graphs",), ("native_calls",), ("whole_atlas_reference_scan",), ("method",), ("summary",)])
def test_top_level_category_mutations_reject(values, monkeypatch, path):
    item = values["evidence"]
    for key in path: item = item[key]
    _reject(monkeypatch, values, _replace(values["evidence"], path, _changed(item)))
def _root(monkeypatch, temporary): info = temporary.stat(); monkeypatch.setattr(cli, "_prepare_output_root", lambda: (temporary, temporary, info)); monkeypatch.setattr(cli, "_recheck_output_root", lambda *a: None)
def test_cli_inherited_errors_and_existing_preservation(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path); output = tmp_path / "e.json"; rendered = callee.encode_native_query_handler_first_callee_static_boundary(values["evidence"]); cli._write_immutably(output, rendered, values["evidence"]); output.write_bytes(rendered.encode() + b" ")
    with pytest.raises(NativeQueryHandlerFirstCalleeStaticBoundaryError, match="refusing to overwrite"): cli._write_immutably(output, rendered, values["evidence"])
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (_ for _ in ()).throw(cli.NativeLuaPropertyFactoryChainError("inherited root failure")))
    with pytest.raises(NativeQueryHandlerFirstCalleeStaticBoundaryError, match="inherited root failure"): cli._write_immutably(tmp_path / "other.json", rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode() + b" "
def test_cli_lock_contention(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path); output = tmp_path / "e.json"; rendered = callee.encode_native_query_handler_first_callee_static_boundary(values["evidence"]); output.write_bytes(rendered.encode()); seen = []; original = cli._read_locked_json_document
    def writer():
        if os.name == "nt":
            try:
                with output.open("ab") as stream: stream.write(b" ")
            except OSError: seen.append("blocked")
            else: seen.append("mutated")
        else:
            import fcntl; fd = os.open(output, os.O_WRONLY | os.O_APPEND)
            try:
                try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError: seen.append("blocked")
                else: os.write(fd, b" "); seen.append("mutated")
            finally: os.close(fd)
    def locked(fd, label): result = original(fd, label); thread = threading.Thread(target=writer); thread.start(); thread.join(5); assert not thread.is_alive(); return result
    monkeypatch.setattr(cli, "_read_locked_json_document", locked); cli._write_immutably(output, rendered, values["evidence"]); assert seen == ["blocked"]
@pytest.mark.parametrize("existing", [True, False])
def test_cli_final_corruption_preserves_existing_or_cleans_private_publication(tmp_path, monkeypatch, values, existing):
    _root(monkeypatch, tmp_path); output = tmp_path / "e.json"; rendered = callee.encode_native_query_handler_first_callee_static_boundary(values["evidence"])
    if existing: output.write_bytes(rendered.encode())
    original = cli._read_locked_json_document
    def corrupt(fd, label): value, payload = original(fd, label); return value, payload + b" "
    monkeypatch.setattr(cli, "_read_locked_json_document", corrupt)
    with pytest.raises(NativeQueryHandlerFirstCalleeStaticBoundaryError, match="final content validation"): cli._write_immutably(output, rendered, values["evidence"])
    if existing: assert output.read_bytes() == rendered.encode()
    else: assert not output.exists()
