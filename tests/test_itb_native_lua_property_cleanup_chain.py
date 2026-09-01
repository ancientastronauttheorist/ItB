from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import itb_native_lua_property_cleanup_chain as cleanup_cli
from src.observatory import native_lua_property_cleanup_chain as cleanup
from src.observatory.native_lua_property_cleanup_chain import (
    NativeLuaPropertyCleanupChainError,
    encode_native_lua_property_cleanup_chain,
    validate_native_lua_property_cleanup_chain_structure,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values() -> dict[str, dict]:
    names = {
        "inventory": "../inventories/" + PREFIX + "full_decompile_baseline_20260830.json",
        "facts": PREFIX + "program_facts.json", "direct": PREFIX + "native_lua_direct_call_census.json",
        "callbacks": PREFIX + "native_lua_cclosure_callbacks.json", "setfield": PREFIX + "native_lua_cclosure_setfield_publications.json",
        "direct_table": PREFIX + "native_lua_cclosure_table_setter_publications.json", "indirect": PREFIX + "native_lua_cclosure_indirect_settable_publications.json",
        "keys": PREFIX + "native_lua_cclosure_table_key_provenance.json", "terminal": PREFIX + "native_lua_cclosure_terminal_dispositions.json",
        "property": PREFIX + "native_lua_property_factory_chain.json", "consumer": PREFIX + "native_lua_property_consumer_chain.json",
        "initializer": PREFIX + "native_lua_property_initializer_chain.json", "evidence": PREFIX + "native_lua_property_cleanup_chain.json",
    }
    paths = {key: (PROGRAMS / value if not value.startswith("../") else INVENTORIES / value.split("/")[-1]) for key, value in names.items()}
    missing = [path for path in paths.values() if not path.is_file()]
    if missing: pytest.skip("cleanup-chain prerequisites are unavailable")
    return {key: _read(path) for key, path in paths.items()}


def _args(v: dict[str, dict]) -> tuple[dict, ...]:
    return (v["initializer"], v["consumer"], v["property"], v["direct"], v["callbacks"], v["setfield"], v["direct_table"], v["indirect"], v["keys"], v["terminal"], v["facts"])


def _receipt(v: dict[str, dict]) -> dict:
    return {"analysis_kind": cleanup.INITIALIZER_STRUCTURE_VERIFICATION_KIND, "status": "structurally_verified", "evidence_sha256": cleanup._PROFILE["initializer_canonical_sha256"], "build_identity": copy.deepcopy(v["initializer"]["build_identity"])}


def _fast(monkeypatch, evidence: dict, v: dict[str, dict]):
    monkeypatch.setattr(cleanup, "validate_native_lua_property_initializer_chain_structure", lambda *args, **kwargs: _receipt(v))
    return validate_native_lua_property_cleanup_chain_structure(evidence, *_args(v))


def test_encoding_and_summary(values):
    evidence = values["evidence"]
    assert evidence["analysis_kind"] == cleanup.ANALYSIS_KIND
    assert encode_native_lua_property_cleanup_chain(evidence).encode() == (PROGRAMS / (PREFIX + "native_lua_property_cleanup_chain.json")).read_bytes()
    assert evidence["summary"] == {"initializer_prerequisite_count": 1, "source_body_count": 2, "source_body_bytes": 201, "source_cfg_node_count": 83, "source_cfg_edge_count": 86, "direct_lua_call_count": 10, "staged_lua_call_count": 0, "literal_count": 1, "target_reference_count": 2, "helper_direct_call_count": 1, "cleanup_closure_producer_count": 1, "schema_violations": 0}
    assert [row["target_rva"] for row in evidence["target_reference_scan"]["references"]] == ["0x002e9f00", "0x002e9f40"]


def test_structure_and_semantics(monkeypatch, values):
    receipt = _fast(monkeypatch, values["evidence"], values)
    assert receipt["status"] == "structurally_verified"
    helper = values["evidence"]["semantics"]["helper_registry_nil_loop"]
    assert helper["registry_index"] == -10000 and helper["loop_branch"]["successor_rvas"] == ["0x002e9f12", "0x002e9f39"]
    tail = values["evidence"]["semantics"]["callback_lookup_and_tail"]
    assert tail["userdata_null_checked_before_native_tail"] is False
    assert tail["conditional_native_tail"]["target_label_semantic_evidence"] is False


@pytest.mark.parametrize("path,replacement", [
    (("initializer_chain", "canonical_sha256"), "0" * 64),
    (("source_bodies", 0, "body_sha256"), "1" * 64),
    (("source_bodies", 0, "direct_lua_calls"), []),
    (("literal", "text"), "__gc"),
    (("literal", "section_name"), ".data"),
    (("literal", "nul_terminated_bytes_sha256"), "2" * 64),
    (("target_reference_scan", "references", 0, "use_class"), "other"),
    (("target_reference_scan", "references", 0, "instruction_rva"), "0x002e9fa1"),
    (("semantics", "helper_registry_nil_loop", "zero_count_branch", "condition"), "signed_less_than_zero"),
    (("semantics", "helper_registry_nil_loop", "registry_index"), -9999),
    (("semantics", "helper_registry_nil_loop", "byte_offset_increment_rva"), "0x002e9f31"),
    (("semantics", "callback_lookup_and_tail", "nil_branch", "successor_rvas"), []),
    (("semantics", "callback_lookup_and_tail", "direct_helper_edge_rva"), "0x002e9fa1"),
    (("semantics", "callback_lookup_and_tail", "indirect_native_call", "instruction_rva"), "0x002e9fb0"),
    (("semantics", "callback_lookup_and_tail", "conditional_native_tail", "target_rva"), "0x0036fb18"),
    (("semantics", "callback_lookup_and_tail", "normal_result_count"), 1),
    (("semantics", "callback_lookup_and_tail", "userdata_null_checked_before_native_tail"), True),
    (("summary", "direct_lua_call_count"), 9),
])
def test_structure_rejects_mutation(monkeypatch, values, path, replacement):
    evidence=copy.deepcopy(values["evidence"]); cursor=evidence
    for key in path[:-1]: cursor=cursor[key]
    cursor[path[-1]]=replacement
    with pytest.raises(NativeLuaPropertyCleanupChainError): _fast(monkeypatch,evidence,values)


def test_structure_rejects_unknown_field(monkeypatch, values):
    evidence=copy.deepcopy(values["evidence"]); evidence["extra"]=True
    with pytest.raises(NativeLuaPropertyCleanupChainError): _fast(monkeypatch,evidence,values)


def test_cli_parser_surface():
    paths = []
    for name in (
        "--executable", "--inventory", "--program-facts", "--direct-calls", "--callbacks",
        "--setfield-publications", "--direct-table-setter-publications",
        "--indirect-settable-publications", "--table-key-provenance", "--terminal-dispositions",
        "--property-factory-chain", "--property-consumer-chain", "--property-initializer-chain",
    ):
        paths.extend((name, "input.json"))
    parsed = cleanup_cli.build_parser().parse_args(["build", *paths, "--output", "out.json"])
    assert parsed.command == "build" and parsed.output == Path("out.json")
    parsed = cleanup_cli.build_parser().parse_args(["verify", *paths, "--evidence", "evidence.json"])
    assert parsed.command == "verify" and parsed.evidence == Path("evidence.json")


def test_immutable_writer_idempotence_and_refusal(monkeypatch, tmp_path, values):
    monkeypatch.setattr(cleanup_cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, object()))
    monkeypatch.setattr(cleanup_cli, "_recheck_output_root", lambda *args: None)
    value = copy.deepcopy(values["evidence"])
    rendered = encode_native_lua_property_cleanup_chain(value)
    output = tmp_path / "cleanup.json"
    cleanup_cli._write_immutably(output, rendered, value)
    cleanup_cli._write_immutably(output, rendered, value)
    altered = copy.deepcopy(value)
    altered["summary"]["literal_count"] = 2
    with pytest.raises(NativeLuaPropertyCleanupChainError):
        cleanup_cli._write_immutably(output, encode_native_lua_property_cleanup_chain(altered), altered)
