"""Exact and adversarial tests for the relationship-defined local-helper callee."""
from __future__ import annotations
import copy, hashlib, json, os, threading
from pathlib import Path
import pytest
from scripts import itb_native_query_local_helper_callee_static_boundary as cli
from src.observatory import native_query_local_helper_callee_static_boundary as callee
from src.observatory.native_query_local_helper_callee_static_boundary import NativeQueryLocalHelperCalleeStaticBoundaryError

ROOT = Path(__file__).resolve().parents[1]; PROGRAMS = ROOT / "data" / "observatory" / "programs"; INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"; EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
EXE_SHA = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"; RAW = "2a0f26e367e6527890757e7fdafa9f621e3a0b07566fd7624807a5781b44ef95"; CANONICAL = "c41457569fcc4f412c35de53f7830d6e4049791a4991062d341d73a756437310"
def _read(path): return json.loads(path.read_text(encoding="utf-8"))
@pytest.fixture(scope="module")
def values():
    paths = {"inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"), "facts": PROGRAMS / (PREFIX + "program_facts.json"), "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"), "helper": PROGRAMS / (PREFIX + "native_query_new_handler_local_helper_static_boundary.json"), "evidence": PROGRAMS / (PREFIX + "native_query_local_helper_callee_static_boundary.json")}
    value = {key: _read(path) for key, path in paths.items()}; value["paths"] = paths; return value
def _common(v): return v["helper"], v["direct"], v["facts"]
def _structure(v, evidence=None): return callee.validate_native_query_local_helper_callee_static_boundary_structure(v["evidence"] if evidence is None else evidence, *_common(v))
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
    with pytest.raises(NativeQueryLocalHelperCalleeStaticBoundaryError): _fast(monkeypatch, v, evidence)

def test_receipts_full_owner_partition_import_and_nonclaims(values):
    evidence = values["evidence"]; raw = values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW; assert raw == callee.encode_native_query_local_helper_callee_static_boundary(evidence).encode(); assert callee._canonical_sha256(evidence) == CANONICAL; assert _structure(values)["evidence_sha256"] == CANONICAL
    body, graph = evidence["function_bodies"][0], evidence["control_flow_graphs"][0]
    assert (body["entry_rva"], body["body_size"], body["body_sha256"], body["control_flow_graph_canonical_sha256"]) == ("0x00388c0d", 23, callee._BODY, callee._CFG); assert (graph["node_count"], graph["edge_count"], len(body["reviewed_points"])) == (9, 8, 9)
    assert body["direct_lua_calls"] == [] and body["staged_lua_dispatches"] == [] and body["call_r32_audit"] == [{"register": name, "call_rvas": []} for name in callee._REGISTER_NAMES]
    scan = evidence["whole_atlas_reference_scan"]; assert scan["aggregates"] == {"reference_count": 29, "direct_call_count": 29, "comparison_count": 0, "other_address_count": 0, "memory_operand_count": 0, "owner_count": 29}; assert len(scan["references"]) == len(scan["owner_partition"]) == 29; assert len({row["owner_entry_rva"] for row in scan["owner_partition"]}) == 29
    predecessor = evidence["local_helper_callee_predecessor_edge"]; assert (predecessor["source_entry_rva"], predecessor["instruction"]["rva"], predecessor["target_entry_rva"]) == ("0x0038bc51", "0x0038bc53", "0x00388c0d")
    records = evidence["native_calls"]["absolute_pointer_or_memory_syntax"]; assert records[0]["operand_rva"] == "0x004b70a8" and records[0]["file_backed"] is False; assert records[1]["pe_import_binding"] == {"evidence_class": "fact", "library": "KERNEL32.dll", "name": "LeaveCriticalSection", "hint": 825, "ordinal": None, "iat_rva": "0x003d6080"}
    for word in ("lock", "synchronization", "ABI", "runtime", "imported-function execution", "Lua-side"): assert any(word.lower() in text.lower() for text in evidence["method"]["not_claimed"])

def test_exact_rebuild(values):
    if not EXE.is_file() or hashlib.sha256(EXE.read_bytes()).hexdigest() != EXE_SHA: pytest.skip("sealed executable unavailable")
    rebuilt = callee.build_native_query_local_helper_callee_static_boundary(EXE, *_common(values), inventory=values["inventory"]); assert rebuilt == values["evidence"]; assert callee.validate_native_query_local_helper_callee_static_boundary(EXE, values["evidence"], *_common(values), inventory=values["inventory"])["status"] == "verified"

@pytest.mark.parametrize("path", [("unexpected",), ("function_bodies", 0, "unexpected"), ("native_calls", "absolute_pointer_or_memory_syntax", 1, "pe_import_binding", "unexpected"), ("whole_atlas_reference_scan", "references", 0, "unexpected"), ("whole_atlas_reference_scan", "owner_partition", 0, "unexpected")])
def test_unknown_keys_reject(values, monkeypatch, path): _reject(monkeypatch, values, _add(values["evidence"], path, True))
@pytest.mark.parametrize("path", [("schema_version",), ("function_bodies", 0, "body_size"), ("function_bodies", 0, "reviewed_points", 0, "sha256"), ("local_helper_callee_predecessor_edge", "instruction", "sha256"), ("whole_atlas_reference_scan", "owner_partition", 0, "owner_entry_rva")])
def test_core_tamper_rejects(values, monkeypatch, path):
    item = values["evidence"]
    for key in path: item = item[key]
    _reject(monkeypatch, values, _replace(values["evidence"], path, _changed(item)))
@pytest.mark.parametrize("path,replacement", [
    (("schema_version",), True), (("function_bodies", 0, "body_size"), True),
    (("control_flow_graphs", 0, "nodes", 0, "size"), True),
    (("whole_atlas_reference_scan", "references", 0, "operand_index"), True),
    (("whole_atlas_reference_scan", "owner_partition", 0, "reference_count"), True),
    (("native_calls", "absolute_pointer_or_memory_syntax", 1, "pe_import_binding", "hint"), True),
    (("native_calls", "absolute_pointer_or_memory_syntax", 0, "section_writable"), 1),
    (("native_calls", "absolute_pointer_or_memory_syntax", 1, "file_backed"), 1),
])
def test_bool_as_int_and_wrong_container_types_reject(values, monkeypatch, path, replacement): _reject(monkeypatch, values, _replace(values["evidence"], path, replacement))
@pytest.mark.parametrize("field", ["evidence_class", "library", "name", "hint", "ordinal", "iat_rva"])
def test_every_import_binding_field_rejects(values, monkeypatch, field):
    path = ("native_calls", "absolute_pointer_or_memory_syntax", 1, "pe_import_binding", field); _reject(monkeypatch, values, _replace(values["evidence"], path, _changed(values["evidence"]["native_calls"]["absolute_pointer_or_memory_syntax"][1]["pe_import_binding"][field])))
@pytest.mark.parametrize("index,field", [(0, "section_name"), (0, "section_characteristics"), (0, "section_writable"), (0, "file_backed"), (1, "section_name"), (1, "section_characteristics"), (1, "section_writable"), (1, "file_backed")])
def test_every_absolute_section_and_backing_field_rejects(values, monkeypatch, index, field):
    path = ("native_calls", "absolute_pointer_or_memory_syntax", index, field); _reject(monkeypatch, values, _replace(values["evidence"], path, _changed(values["evidence"]["native_calls"]["absolute_pointer_or_memory_syntax"][index][field])))
def test_missing_or_tampered_owner_partition_rejects(values, monkeypatch):
    evidence = copy.deepcopy(values["evidence"]); del evidence["whole_atlas_reference_scan"]["owner_partition"]; _reject(monkeypatch, values, evidence)
    _reject(monkeypatch, values, _replace(values["evidence"], ("whole_atlas_reference_scan", "references", 6, "owner_atlas_record_sha256"), "changed"))
def test_structure_requires_direct_prerequisite_status(values, monkeypatch):
    monkeypatch.setattr(callee, "validate_native_lua_direct_call_structure", lambda *a, **k: {"status": "verified", "evidence_sha256": callee._DIRECT})
    with pytest.raises(NativeQueryLocalHelperCalleeStaticBoundaryError, match="prerequisite"): _structure(values)
@pytest.mark.parametrize("path", [("schema_version",), ("analysis_kind",), ("build_identity",), ("atlas",), ("direct_call_census",), ("local_helper_static_boundary",), ("local_helper_callee_predecessor_edge",), ("decoder",), ("function_bodies",), ("control_flow_graphs",), ("native_calls",), ("whole_atlas_reference_scan",), ("method",), ("summary",)])
def test_top_level_category_mutations_reject(values, monkeypatch, path):
    item = values["evidence"]
    for key in path: item = item[key]
    _reject(monkeypatch, values, _replace(values["evidence"], path, _changed(item)))
@pytest.mark.parametrize("path", [("whole_atlas_reference_scan", "references", 0, "owner_entry_rva"), ("whole_atlas_reference_scan", "references", 0, "owner_atlas_record_sha256")])
@pytest.mark.parametrize("replacement", [None, False, 7, []])
def test_missing_or_wrong_type_reference_owner_identity_is_domain_error(values, monkeypatch, path, replacement):
    evidence = copy.deepcopy(values["evidence"]); cursor = evidence
    for key in path[:-1]: cursor = cursor[key]
    if replacement is None: del cursor[path[-1]]
    else: cursor[path[-1]] = replacement
    _reject(monkeypatch, values, evidence)
def test_encoder_normalizes_inherited_json_tree_error(monkeypatch):
    monkeypatch.setattr(callee, "_validate_json_tree", lambda *a, **k: (_ for _ in ()).throw(callee.NativeLuaCClosurePublicationError("bad JSON tree")))
    with pytest.raises(NativeQueryLocalHelperCalleeStaticBoundaryError, match="bad JSON tree"): callee.encode_native_query_local_helper_callee_static_boundary({})
def _root(monkeypatch, temporary): info = temporary.stat(); monkeypatch.setattr(cli, "_prepare_output_root", lambda: (temporary, temporary, info)); monkeypatch.setattr(cli, "_recheck_output_root", lambda *a: None)
def test_cli_inherited_errors_and_existing_preservation(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path); output = tmp_path / "e.json"; rendered = callee.encode_native_query_local_helper_callee_static_boundary(values["evidence"]); cli._write_immutably(output, rendered, values["evidence"]); output.write_bytes(rendered.encode() + b" ")
    with pytest.raises(NativeQueryLocalHelperCalleeStaticBoundaryError, match="refusing to overwrite"): cli._write_immutably(output, rendered, values["evidence"])
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (_ for _ in ()).throw(cli.NativeLuaPropertyFactoryChainError("inherited root failure")))
    with pytest.raises(NativeQueryLocalHelperCalleeStaticBoundaryError, match="inherited root failure"): cli._write_immutably(tmp_path / "other.json", rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode() + b" "
def test_cli_assertion_helper_error_is_normalized_and_preserves_existing(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path); output = tmp_path / "e.json"; rendered = callee.encode_native_query_local_helper_callee_static_boundary(values["evidence"]); output.write_bytes(rendered.encode())
    monkeypatch.setattr(cli, "_regular_child", lambda *a, **k: (_ for _ in ()).throw(cli.NativeAssertionHelperStaticBoundaryError("inherited regular failure")))
    with pytest.raises(NativeQueryLocalHelperCalleeStaticBoundaryError, match="inherited regular failure"): cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode()
def test_cli_lock_contention(tmp_path, monkeypatch, values):
    _root(monkeypatch, tmp_path); output = tmp_path / "e.json"; rendered = callee.encode_native_query_local_helper_callee_static_boundary(values["evidence"]); output.write_bytes(rendered.encode()); seen = []; original = cli._read_locked_json_document
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
    def locked(fd, label):
        result = original(fd, label); thread = threading.Thread(target=writer); thread.start(); thread.join(5); assert not thread.is_alive(); return result
    monkeypatch.setattr(cli, "_read_locked_json_document", locked); cli._write_immutably(output, rendered, values["evidence"]); assert seen == ["blocked"]
    def corrupt(fd, label): value, payload = original(fd, label); return value, payload + b" "
@pytest.mark.parametrize("existing", [True, False])
def test_cli_final_corruption_preserves_existing_or_cleans_private_publication(tmp_path, monkeypatch, values, existing):
    _root(monkeypatch, tmp_path); output = tmp_path / "e.json"; rendered = callee.encode_native_query_local_helper_callee_static_boundary(values["evidence"])
    if existing: output.write_bytes(rendered.encode())
    original = cli._read_locked_json_document
    def corrupt(fd, label): value, payload = original(fd, label); return value, payload + b" "
    monkeypatch.setattr(cli, "_read_locked_json_document", corrupt)
    with pytest.raises(NativeQueryLocalHelperCalleeStaticBoundaryError, match="final content validation"): cli._write_immutably(output, rendered, values["evidence"])
    if existing: assert output.read_bytes() == rendered.encode()
    else: assert not output.exists()
