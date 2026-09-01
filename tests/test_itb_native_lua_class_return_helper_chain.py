"""Exact, adversarial, and publication tests for class return-helper evidence."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import itb_native_lua_class_return_helper_chain as cli
from src.observatory import native_lua_class_return_helper_chain as helpers
from src.observatory.native_lua_class_return_helper_chain import (
    NativeLuaClassReturnHelperChainError,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe")
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
RAW_SHA256 = "aab9847af280484af26885f6390f586726fd173466b76d5f0b2cda104f836bec"
CANONICAL_SHA256 = "33ad87a98131700dce12bd34a7febea3159b6f461710f0b8296d95ded1b37095"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values() -> dict:
    paths = {
        "inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"),
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "class_factory": PROGRAMS / (PREFIX + "native_lua_class_factory_chain.json"),
        "evidence": PROGRAMS / (PREFIX + "native_lua_class_return_helper_chain.json"),
    }
    if any(not path.is_file() for path in paths.values()):
        pytest.skip("class return-helper evidence prerequisites are unavailable")
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    return result


def _common(values: dict) -> tuple[dict, dict, dict]:
    return values["class_factory"], values["direct"], values["facts"]


def _structure(values: dict, evidence: dict | None = None) -> dict:
    return helpers.validate_native_lua_class_return_helper_chain_structure(
        values["evidence"] if evidence is None else evidence,
        *_common(values),
    )


def _fast_structure(monkeypatch, values: dict, evidence: dict) -> dict:
    monkeypatch.setattr(
        helpers,
        "validate_native_lua_direct_call_structure",
        lambda *args, **kwargs: {
            "status": "structurally_verified",
            "evidence_sha256": helpers._DIRECT_SHA256,
        },
    )
    return _structure(values, evidence)


def _body(evidence: dict, entry_rva: str) -> dict:
    return next(
        item for item in evidence["function_bodies"]
        if item["entry_rva"] == entry_rva
    )


def _graph(evidence: dict, entry_rva: str) -> dict:
    return next(
        item for item in evidence["control_flow_graphs"]
        if item["caller_entry_rva"] == entry_rva
    )


def _point(body: dict, role: str) -> dict:
    return next(item for item in body["reviewed_points"] if item["role"] == role)


def test_committed_artifact_encoding_structure_and_summary(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert raw == helpers.encode_native_lua_class_return_helper_chain(evidence).encode("utf-8")
    assert hashlib.sha256(raw).hexdigest() == RAW_SHA256
    assert helpers._canonical_sha256(evidence) == CANONICAL_SHA256
    receipt = _structure(values)
    assert receipt["status"] == "structurally_verified"
    assert type(receipt["evidence_sha256"]) is str and len(receipt["evidence_sha256"]) == 64
    assert evidence["summary"] == {
        "reviewed_helper_count": 3,
        "reviewed_helper_bytes": 501,
        "sealed_control_flow_graph_count": 3,
        "sealed_control_flow_graph_node_count": 190,
        "sealed_control_flow_graph_edge_count": 201,
        "direct_lua_call_count": 14,
        "staged_lua_dispatch_count": 2,
        "staged_lua_call_count": 6,
        "total_lua_call_count": 20,
        "call_r32_count": 6,
        "literal_count": 3,
        "selected_native_edge_count": 6,
        "unique_native_edge_target_count": 5,
        "helper_target_count": 3,
        "class_factory_helper_edge_count": 5,
        "target_reference_count": 6,
        "target_reference_direct_call_count": 6,
        "target_reference_comparison_count": 0,
        "target_reference_other_address_count": 0,
        "target_reference_memory_operand_count": 0,
        "target_reference_owner_count": 2,
        "alternate_owner_reference_count": 1,
        "schema_violations": 0,
    }


def test_committed_artifact_exact_rebuild_and_verification(values):
    if not EXE.is_file() or hashlib.sha256(EXE.read_bytes()).hexdigest() != EXE_SHA256:
        pytest.skip("sealed Breach.exe is unavailable")
    rebuilt = helpers.build_native_lua_class_return_helper_chain(
        EXE, *_common(values), inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    receipt = helpers.validate_native_lua_class_return_helper_chain(
        EXE, values["evidence"], *_common(values), inventory=values["inventory"]
    )
    assert receipt["status"] == "verified"
    assert receipt["evidence_sha256"] == CANONICAL_SHA256


def test_expected_helper_contracts_and_complete_reference_frontier(values):
    evidence = values["evidence"]
    mutation = _body(evidence, "0x002eb140")["semantic_facts"]
    marker = _body(evidence, "0x002eb560")["semantic_facts"]
    assignment = _body(evidence, "0x002ec050")["semantic_facts"]
    assert mutation["append_record_width_bytes"] == 8
    assert mutation["capacity_helper_call_rvas"] == [
        "0x002eb1da", "0x002eb200",
    ]
    assert mutation["source_semantic_names_assigned"] is False
    assert marker["marker_literal"] == "__luabind_classrep"
    assert marker["marker_lookup_raw_claimed"] is False
    assert marker["metatable_arms_cleanup_index"] == -3
    assert marker["pre_helper_stack_restored_on_normal_return"] is True
    assert assignment["filtered_exact_keys"] == ["__init", "__finalize"]
    assert assignment["assignment_destination_index_at_call"] == -5
    assert assignment["assignment_raw_claimed"] is False
    scan = evidence["whole_atlas_reference_scan"]
    assert [item["instruction_rva"] for item in scan["references"]] == [
        "0x002e7ce0", "0x002ec15b", "0x002ec17f",
        "0x002ec1b8", "0x002ec1db", "0x002ec1fe",
    ]
    assert all(item["use_class"] == "direct_call" for item in scan["references"])
    assert scan["references"][0]["owner_entry_rva"] == "0x002e7970"
    assert [item["owner_entry_rva"] for item in scan["references"][1:]] == [
        "0x002ec110",
    ] * 5
    not_claimed = evidence["method"]["not_claimed"]
    assert any("alternate 0x002e7970 caller" in item for item in not_claimed)
    assert any("factory-side initializer" in item for item in not_claimed)


def _first_mapping(container: object) -> dict:
    if isinstance(container, list):
        assert container and isinstance(container[0], dict)
        return container[0]
    assert isinstance(container, dict)
    return container


def _mutate(evidence: dict, case: str) -> None:
    if case == "unknown":
        evidence["unexpected"] = True
    elif case == "class_factory":
        evidence["class_factory_chain"]["canonical_sha256"] = "0" * 64
    elif case == "atlas":
        evidence["atlas"]["canonical_sha256"] = "0" * 64
    elif case == "direct":
        evidence["direct_call_census"]["canonical_sha256"] = "0" * 64
    elif case == "decoder":
        evidence["decoder"]["capstone_version"] = "wrong"
    elif case == "helper_target":
        _first_mapping(evidence["helper_targets"])["entry_rva"] = "0x00000000"
    elif case == "literal":
        _first_mapping(evidence["literals"])["nul_terminated_bytes_sha256"] = "0" * 64
    elif case == "body":
        _first_mapping(evidence["function_bodies"])["body_sha256"] = "0" * 64
    elif case == "cfg":
        _first_mapping(evidence["control_flow_graphs"])["edge_count"] += 1
    elif case == "native_edge":
        _first_mapping(evidence["native_edges"])["target_entry_rva"] = "0x00000000"
    elif case == "reference":
        _first_mapping(evidence["whole_atlas_reference_scan"]["references"])["target_rva"] = "0x00000000"
    elif case == "reference_scope":
        evidence["whole_atlas_reference_scan"]["scope"]["decoded_instructions"] -= 1
    elif case == "method":
        _first_mapping(evidence["method"])["not_claimed"] = ["changed"]
    elif case == "summary":
        evidence["summary"]["target_reference_count"] = 0
    else:
        raise AssertionError(case)


@pytest.mark.parametrize(
    "case",
    [
        "unknown", "class_factory", "atlas", "direct", "decoder", "helper_target",
        "literal", "body", "cfg", "native_edge", "reference", "reference_scope",
        "method", "summary",
    ],
)
def test_structure_rejects_retained_category(values, monkeypatch, case):
    # The exact direct-call prerequisite has its own suite. Avoid replaying its
    # full structural census for every local evidence-only mutation.
    evidence = copy.deepcopy(values["evidence"])
    _mutate(evidence, case)
    with pytest.raises(NativeLuaClassReturnHelperChainError):
        _fast_structure(monkeypatch, values, evidence)


@pytest.mark.parametrize(
    ("entry_rva", "field", "replacement"),
    [
        ("0x002eb560", "import_name", "lua_pushnil"),
        ("0x002eb560", "iat_rva", "0x00000000"),
        ("0x002ec050", "call_form", "changed"),
        ("0x002ec050", "instruction_sha256", "0" * 64),
    ],
)
def test_structure_rejects_direct_lua_call_tamper(
    values, monkeypatch, entry_rva, field, replacement
):
    evidence = copy.deepcopy(values["evidence"])
    _body(evidence, entry_rva)["direct_lua_calls"][0][field] = replacement
    with pytest.raises(NativeLuaClassReturnHelperChainError):
        _fast_structure(monkeypatch, values, evidence)


@pytest.mark.parametrize(
    ("entry_rva", "semantic_field", "replacement"),
    [
        ("0x002eb140", "append_record_width_bytes", 4),
        ("0x002eb140", "capacity_helper_call_rvas", ["0x002eb1da"]),
        ("0x002eb560", "metatable_arms_cleanup_index", -2),
        ("0x002eb560", "marker_lookup_raw_claimed", True),
        ("0x002ec050", "filtered_exact_keys", ["__init"]),
        ("0x002ec050", "assignment_destination_index_at_call", -4),
        ("0x002ec050", "normal_exhaustion_retains_entry_values", 1),
    ],
)
def test_structure_rejects_semantic_contract_tamper(
    values, monkeypatch, entry_rva, semantic_field, replacement
):
    evidence = copy.deepcopy(values["evidence"])
    _body(evidence, entry_rva)["semantic_facts"][semantic_field] = replacement
    with pytest.raises(NativeLuaClassReturnHelperChainError):
        _fast_structure(monkeypatch, values, evidence)


@pytest.mark.parametrize(
    ("entry_rva", "role", "meaning_field", "replacement"),
    [
        ("0x002eb140", "input_alias_upper_compare", "left", "EAX"),
        ("0x002eb140", "external_capacity_helper", "target_rva", "0x00000000"),
        ("0x002eb560", "cleanup_index", "value", -2),
        ("0x002ec050", "first_entry_destination_index", "value", -4),
        ("0x002ec050", "init_skip_cleanup_index", "value", -2),
    ],
)
def test_structure_rejects_reviewed_point_meaning_tamper(
    values, monkeypatch, entry_rva, role, meaning_field, replacement
):
    evidence = copy.deepcopy(values["evidence"])
    _point(_body(evidence, entry_rva), role)["meaning"][meaning_field] = replacement
    with pytest.raises(NativeLuaClassReturnHelperChainError):
        _fast_structure(monkeypatch, values, evidence)


def _accept_mutated_cfg_identity(monkeypatch, evidence: dict, entry_rva: str) -> None:
    graph = _graph(evidence, entry_rva)
    digest = helpers._canonical_sha256(graph)
    _body(evidence, entry_rva)["control_flow_graph_canonical_sha256"] = digest
    profile = copy.deepcopy(helpers._SEALED_PROFILE)
    expected = next(
        item for item in profile["functions"]
        if helpers._hex(item["entry_rva"]) == entry_rva
    )
    expected["cfg_canonical_sha256"] = digest
    monkeypatch.setattr(helpers, "_PROFILES", {profile["executable_sha256"]: profile})


def test_structure_rejects_staged_register_writer(values, monkeypatch):
    evidence = copy.deepcopy(values["evidence"])
    graph = _graph(evidence, "0x002ec050")
    node = next(item for item in graph["nodes"] if item["rva"] == "0x002ec080")
    node["writes_ebx"] = True
    _accept_mutated_cfg_identity(monkeypatch, evidence, "0x002ec050")
    with pytest.raises(NativeLuaClassReturnHelperChainError, match="clobbered"):
        _fast_structure(monkeypatch, values, evidence)


@pytest.mark.parametrize("register_index", range(8))
def test_structure_rejects_ungrouped_call_r32(values, monkeypatch, register_index):
    evidence = copy.deepcopy(values["evidence"])
    graph = _graph(evidence, "0x002eb560")
    node = next(item for item in graph["nodes"] if item["rva"] == "0x002eb596")
    encoded = bytes((0xFF, 0xD0 + register_index))
    node["sha256"] = hashlib.sha256(encoded).hexdigest()
    _accept_mutated_cfg_identity(monkeypatch, evidence, "0x002eb560")
    with pytest.raises(NativeLuaClassReturnHelperChainError):
        _fast_structure(monkeypatch, values, evidence)


def test_structure_rejects_alternate_owner_reference_tamper(values, monkeypatch):
    evidence = copy.deepcopy(values["evidence"])
    reference = evidence["whole_atlas_reference_scan"]["references"][0]
    assert reference["instruction_rva"] == "0x002e7ce0"
    reference["owner_entry_rva"] = "0x002ec110"
    with pytest.raises(NativeLuaClassReturnHelperChainError):
        _fast_structure(monkeypatch, values, evidence)


@pytest.mark.parametrize(
    "mutation",
    ["literal_section", "returned_edge", "stage", "stage_call", "nested_unknown"],
)
def test_structure_rejects_nested_proof_tamper(values, monkeypatch, mutation):
    evidence = copy.deepcopy(values["evidence"])
    if mutation == "literal_section":
        evidence["literals"][0]["section_writable"] = True
    elif mutation == "returned_edge":
        evidence["returned_callback_edges"][0]["target_entry_rva"] = "0x00000000"
    elif mutation == "stage":
        _body(evidence, "0x002ec050")["staged_lua_dispatches"][0]["stage"]["sha256"] = "0" * 64
    elif mutation == "stage_call":
        call = _body(evidence, "0x002ec050")["staged_lua_dispatches"][0]["call_sites"][0]
        call["stage_to_call_path_node_count"] -= 1
    else:
        _body(evidence, "0x002eb560")["semantic_facts"]["unexpected"] = True
    with pytest.raises(NativeLuaClassReturnHelperChainError):
        _fast_structure(monkeypatch, values, evidence)


def _patch_output_root(monkeypatch, tmp_path: Path) -> None:
    info = tmp_path.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def test_cli_parser_exposes_complete_surface():
    common = []
    for flag in ("--class-factory", "--direct-calls", "--program-facts"):
        common += [flag, "input.json"]
    parser = cli.build_parser()
    execution = ["--executable", "Breach.exe", "--inventory", "inventory.json"]
    assert parser.parse_args(["build", *common, *execution, "--output", "out.json"]).command == "build"
    assert parser.parse_args(["verify", *common, *execution, "--evidence", "out.json"]).command == "verify"
    assert parser.parse_args(["verify-structure", *common, "--evidence", "out.json"]).command == "verify-structure"


@pytest.mark.parametrize("payload", ['{"a": 1, "a": 2}', '{"a": NaN}'])
def test_cli_main_reports_strict_json_errors(tmp_path, capsys, payload):
    malformed = tmp_path / "malformed.json"
    malformed.write_text(payload, encoding="utf-8")
    argv = ["verify"]
    for flag in ("--executable", "--inventory", "--class-factory", "--direct-calls", "--program-facts", "--evidence"):
        argv += [flag, str(malformed)]
    assert cli.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "Traceback" not in captured.err


def test_cli_writer_is_immutable(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    evidence = values["evidence"]
    rendered = helpers.encode_native_lua_class_return_helper_chain(evidence)
    output = tmp_path / "evidence.json"
    cli._write_immutably(output, rendered, evidence)
    cli._write_immutably(output, rendered, evidence)
    output.write_text(rendered + " ", encoding="utf-8")
    with pytest.raises(NativeLuaClassReturnHelperChainError, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, evidence)


@pytest.mark.parametrize("kind", ["symlink", "reparse", "directory"])
def test_cli_writer_rejects_nonregular_existing_output(tmp_path, monkeypatch, values, kind):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helpers.encode_native_lua_class_return_helper_chain(values["evidence"])
    if kind == "symlink":
        target = tmp_path / "target.json"
        target.write_text(rendered, encoding="utf-8")
        try:
            output.symlink_to(target)
        except OSError as exc:
            pytest.skip(f"symlink creation unavailable: {exc}")
    elif kind == "reparse":
        output.write_text(rendered, encoding="utf-8")
        monkeypatch.setattr(cli, "_is_reparse", lambda _info: True)
    else:
        output.mkdir()
    with pytest.raises(NativeLuaClassReturnHelperChainError, match="linked, reparse, or non-regular"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_cli_writer_detects_existing_inode_swap(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helpers.encode_native_lua_class_return_helper_chain(values["evidence"])
    output.write_text(rendered, encoding="utf-8")
    original_reader = cli._read_json_document

    def swapped_reader(path: Path, label: str):
        result = original_reader(path, label)
        path.unlink()
        path.write_text(rendered, encoding="utf-8")
        return result

    monkeypatch.setattr(cli, "_read_json_document", swapped_reader)
    with pytest.raises(NativeLuaClassReturnHelperChainError, match="changed during validation"):
        cli._write_immutably(output, rendered, values["evidence"])


def test_cli_writer_rejects_output_outside_programs(tmp_path, monkeypatch, values):
    _patch_output_root(monkeypatch, tmp_path)
    rendered = helpers.encode_native_lua_class_return_helper_chain(values["evidence"])
    with pytest.raises(NativeLuaClassReturnHelperChainError, match="direct child"):
        cli._write_immutably(tmp_path.parent / "evidence.json", rendered, values["evidence"])


@pytest.mark.parametrize("failure_site", ["prepare", "recheck"])
def test_cli_main_reports_output_root_failures(
    tmp_path, monkeypatch, capsys, values, failure_site
):
    output = tmp_path / "evidence.json"
    argv = [
        "build",
        "--executable", str(EXE),
        "--inventory", str(values["paths"]["inventory"]),
        "--class-factory", str(values["paths"]["class_factory"]),
        "--direct-calls", str(values["paths"]["direct"]),
        "--program-facts", str(values["paths"]["facts"]),
        "--output", str(output),
    ]
    monkeypatch.setattr(
        cli,
        "build_native_lua_class_return_helper_chain",
        lambda *args, **kwargs: values["evidence"],
    )
    if failure_site == "prepare":
        monkeypatch.setattr(
            cli,
            "_prepare_output_root",
            lambda: (_ for _ in ()).throw(
                cli.NativeLuaPropertyFactoryChainError("unsafe output root")
            ),
        )
    else:
        info = tmp_path.stat()
        monkeypatch.setattr(
            cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info)
        )
        monkeypatch.setattr(
            cli,
            "_recheck_output_root",
            lambda *args: (_ for _ in ()).throw(
                cli.NativeLuaPropertyFactoryChainError("changed output root")
            ),
        )
    assert cli.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "Traceback" not in captured.err
