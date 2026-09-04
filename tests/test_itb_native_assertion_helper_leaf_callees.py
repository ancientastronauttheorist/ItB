"""Pinned frontier joins, conservative control flow, and immutable publication."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import itb_native_assertion_helper_leaf_callees as cli
from src.observatory import (
    native_assertion_helper_leaf_callees as helper,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CANONICAL = "1ef7c1874b83e871f3afa9d482c2c6f01cd541c50f81b342605d80946a93f3c2"
RAW = "0fbc28fb7e55a61538e74d07c667eb39796febe5ee181c345997f5f6180714ea"
Error = helper.LeafError


@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    suffixes = {
        "pair": "native_assertion_helper_descendant_pair",
        "reused_callee": "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary",
        "direct_calls": "native_lua_direct_call_census",
        "program_facts": "program_facts",
        "evidence": "native_assertion_helper_leaf_callees",
    }
    paths = {
        key: PROGRAMS / (PREFIX + suffix + ".json") for key, suffix in suffixes.items()
    }
    paths["inventory"] = (
        ROOT
        / "data/observatory/inventories"
        / (PREFIX + "full_decompile_baseline_20260830.json")
    )
    # These committed receipts are required; missing evidence must fail, not skip.
    loaded = {
        key: json.loads(path.read_text(encoding="utf-8")) for key, path in paths.items()
    }
    return {
        "paths": paths,
        "sources": {key: loaded[key] for key in helper.SOURCE_PINS},
        "evidence": loaded["evidence"],
        "inventory": loaded["inventory"],
    }


@pytest.fixture
def fast_preflight(monkeypatch: pytest.MonkeyPatch, values: dict[str, Any]) -> None:
    # Mutation cases still run JSON validation and the actual sealed hash check.
    monkeypatch.setattr(
        helper,
        "_preflight",
        lambda sources: copy.deepcopy(values["evidence"]["source_receipts"]),
    )


def _replace(value: Any, path: tuple[Any, ...], replacement: Any) -> Any:
    if not path:
        return replacement
    clone = dict(value) if isinstance(value, dict) else list(value)
    clone[path[0]] = (
        replacement
        if len(path) == 1
        else _replace(value[path[0]], path[1:], replacement)
    )
    return clone


def _args(values: dict[str, Any], command: str = "verify-structure") -> list[str]:
    args = [command, "--evidence", str(values["paths"]["evidence"])]
    for name in helper.SOURCE_PINS:
        args += ["--" + name.replace("_", "-"), str(values["paths"][name])]
    return args


def test_pinned_encoding_and_structural_replay(values: dict[str, Any]) -> None:
    evidence = values["evidence"]
    payload = values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(payload).hexdigest() == RAW
    assert helper._canonical_sha256(evidence) == CANONICAL == helper.SEALED_SHA256
    assert helper.encode_leaves(evidence).encode() == payload
    result = helper.validate_structure(evidence, values["sources"])
    assert result["status"] == "structurally_verified"
    assert result["evidence_sha256"] == CANONICAL
    assert result["summary"] == evidence["summary"]


def test_exact_target_partition_graphs_and_controls(values: dict[str, Any]) -> None:
    e = values["evidence"]
    assert e["summary"] == {
        "target_count": 2,
        "target_bytes": 354,
        "instructions": 91,
        "cfg_nodes": 91,
        "cfg_edges": 103,
        "parent_edges": 5,
        "reused_targets": 1,
        "outgoing_native_edges": 0,
        "import_controls": 0,
        "explicit_operands": 157,
        "ordinary_immediates": 29,
        "absolute_pe_address_operands": 4,
        "memory_expression_operands": 34,
        "segment_register_operands": 0,
        "highlow_sites": 4,
        "incoming_references": 159,
        "incoming_owners": 122,
    }
    assert [b["entry_rva"] for b in e["bodies"]] == ["0x003586b6", "0x00370960"]
    for body, expected in zip(e["bodies"], [(8, 2, 1), (346, 89, 102)]):
        graph = body["control_flow_graph"]
        nodes = graph["nodes"]
        assert (body["body_size"], graph["node_count"], graph["edge_count"]) == expected
        assert len(body["points"]) == len(nodes) == graph["node_count"]
        assert sum(n["size"] for n in nodes) == body["body_size"]
        assert sum(len(n["successor_rvas"]) for n in nodes) == graph["edge_count"]
        sites = {n["rva"] for n in nodes}
        assert len(sites) == len(nodes)
        assert all(s in sites for n in nodes for s in n["successor_rvas"])
        assert graph["repeat_micro_iterations_expanded"] is False
        profile = helper.TARGETS[int(body["entry_rva"], 16)]
        assert body["body_sha256"] == profile["body_sha256"]
        assert body["atlas_record_sha256"] == profile["atlas_sha256"]
        assert body["analysis_metadata"]["metadata_only"] is True
        controls = body["native_controls"]
        assert controls["partitions_complete_for_pinned_bodies"] is True
        assert (
            controls["interrupts"]
            == controls["direct_calls"]
            == controls["import_controls"]
            == []
        )
        assert all(r["call_rvas"] == [] for r in controls["register_calls"])
        assert all(set(p) == {"rva", "size", "sha256"} for p in body["points"])
    nodes = e["bodies"][1]["control_flow_graph"]["nodes"]
    assert sum(n["flow_kind"] == "direct_conditional_branch" for n in nodes) == 16
    assert sum(n["flow_kind"] == "direct_unconditional_branch" for n in nodes) == 1
    assert sum(n["flow_kind"] == "return_syntax" for n in nodes) == 3
    assert len(e["base_relocations"]["sites"]) == 4
    assert all(r["type"] == "HIGHLOW" for r in e["base_relocations"]["sites"])


def test_parent_edges_reused_receipt_and_whole_atlas_partitions(
    values: dict[str, Any],
) -> None:
    e, sources = values["evidence"], values["sources"]
    scan = e["whole_atlas_reference_scan"]
    assert scan["scope"] == {
        "functions": 25312,
        "ranges": 25490,
        "bytes": 3735718,
        "instructions": 1153814,
    }
    assert scan["target_partitions"] == [
        {"entry_rva": "0x003586b6", "reference_count": 2, "owner_count": 1},
        {"entry_rva": "0x00370960", "reference_count": 157, "owner_count": 122},
    ]
    refs = scan["references"]
    assert len(refs) == scan["reference_count"] == 159
    assert len({r["owner_entry_rva"] for r in refs}) == scan["owner_count"]
    assert helper._canonical_sha256(refs) == scan["references_canonical_sha256"]
    for part in scan["target_partitions"]:
        selected = [r for r in refs if r["target_entry_rva"] == part["entry_rva"]]
        assert len(selected) == part["reference_count"]
        assert len({r["owner_entry_rva"] for r in selected}) == part["owner_count"]
    assert [
        (p["edge"]["instruction"]["rva"], p["edge"]["target_entry_rva"])
        for p in e["parent_edges"]
    ] == [
        ("0x00379d47", "0x003586b6"),
        ("0x00379d58", "0x00370960"),
        ("0x00379d6b", "0x00370960"),
        ("0x00379e4e", "0x003586b6"),
        ("0x00379e5a", "0x003574ca"),
    ]
    for index, parent in enumerate(e["parent_edges"]):
        assert parent["source_path"] == [
            "bodies",
            0,
            "native_controls",
            "direct_calls",
            index,
        ]
        assert parent["source_canonical_sha256"] == helper.SOURCE_PINS["pair"][1]
        source = sources["pair"]
        for component in parent["source_path"]:
            source = source[component]
        assert parent["edge"] == source
        if index < 4:
            assert parent["target_evidence"] == "new_body"
            assert (
                sum(
                    r["instruction"] == source["instruction"]
                    and r["target_entry_rva"] == source["target_entry_rva"]
                    and r["owner_entry_rva"] == "0x00379d28"
                    for r in refs
                )
                == 1
            )
        else:
            assert parent["target_evidence"] == "reused_callee"
            assert (
                parent["reused_source_canonical_sha256"]
                == helper.SOURCE_PINS["reused_callee"][1]
            )
            reused = sources["reused_callee"]
            for component in parent["reference_path"]:
                reused = reused[component]
            assert parent["incoming_reference"] == reused
            assert reused["instruction_rva"] == source["instruction"]["rva"]
            assert reused["instruction_sha256"] == source["instruction"]["sha256"]
            assert reused["target_rva"] == source["target_entry_rva"]
            assert reused["owner_entry_rva"] == "0x00379d28"
            assert reused["ghidra_declared_direct_edge"] == source["declared_edge"]


def test_small_effect_is_conditional_and_location_joined(
    values: dict[str, Any],
) -> None:
    body = values["evidence"]["bodies"][0]
    effect = body["conditional_effect"]
    assert effect["instruction"] == body["points"][0]
    assert effect["following_return"] == body["points"][1]
    assert effect["width_bits"] == 32
    assert effect["operation_class"] == "read_modify_write"
    assert effect["result_on_normal_instruction_completion"] == "zero"
    assert effect["evidence_class"] == "static_instruction_semantics"
    destination = body["operands"][0]
    assert destination["size"] == 4
    assert destination["absolute_pe_address"] == effect["location"]
    assert effect["location"]["rva"] == "0x004b6e58"
    assert effect["location"]["contents_and_runtime_meaning_opaque"] is True
    assert effect["location"]["file_backed"] is False
    assert body["operands"][1]["value_u32"] == "0x00000000"
    for phrase in (
        "not proof of execution",
        "normal function return",
        "global purpose",
        "ownership",
        "concurrency",
        "accounting promotion",
    ):
        assert phrase in effect["scope"]


@pytest.mark.parametrize(
    "mutation", ["nonzero_mask", "ret_operand", "address", "opcode"]
)
def test_small_effect_rejects_other_instruction_grammar(mutation: str) -> None:
    memory = SimpleNamespace(base=0, index=0, segment=0, disp=helper.BASE + 0x4B6E58)
    destination = SimpleNamespace(type=helper.x86.X86_OP_MEM, size=4, mem=memory)
    immediate = SimpleNamespace(type=helper.x86.X86_OP_IMM, imm=0)
    first = SimpleNamespace(
        id=helper.x86.X86_INS_AND, operands=[destination, immediate]
    )
    last = SimpleNamespace(id=helper.x86.X86_INS_RET, operands=[])
    if mutation == "nonzero_mask":
        immediate.imm = 1
    elif mutation == "ret_operand":
        last.operands = [SimpleNamespace(type=helper.x86.X86_OP_IMM, imm=4)]
    elif mutation == "address":
        memory.disp += 1
    else:
        first.id = helper.x86.X86_INS_SUB
    # Minimal synthetic decoder objects must fail before byte or image access.
    with pytest.raises(Error, match="effect grammar differs"):
        helper._small_effect([first, last], None)


def test_repeat_and_simd_are_syntax_only(values: dict[str, Any]) -> None:
    e = values["evidence"]
    body = e["bodies"][1]
    nodes = body["control_flow_graph"]["nodes"]
    repeated = [n for n in nodes if n["repeat_prefix"]]
    assert len(repeated) == 1
    repeat = repeated[0]
    assert repeat["flow_kind"] == "repeated_string_possible_completion"
    assert repeat["successor_rvas"] == [
        f"0x{int(repeat['rva'], 16) + repeat['size']:08x}"
    ]
    operands = body["operands"]
    (destination,) = [
        o
        for o in operands
        if o["instruction"]["rva"] == repeat["rva"] and o["kind"] == "memory_expression"
    ]
    assert (destination["segment"], destination["base"], destination["size"]) == (
        "es",
        "edi",
        1,
    )
    assert "absolute_pe_address" not in destination
    prefixed = {n["rva"] for n in nodes if n["legacy_66_prefix"]}
    assert any(
        o["instruction"]["rva"] in prefixed and o["size"] == 16 for o in operands
    )
    addresses = [
        o["absolute_pe_address"]
        for b in e["bodies"]
        for o in b["operands"]
        if "absolute_pe_address" in o
    ]
    assert len(addresses) == 4
    assert all(a["contents_and_runtime_meaning_opaque"] is True for a in addresses)
    disclaimers = " ".join(e["method"]["not_claimed"])
    for phrase in (
        "LEA does not establish a memory read",
        "Legacy 66",
        "REP STOSB",
        "possible completion fallthrough",
        "normal completion",
        "accounting-level promotion",
        "CRT or memset identity",
    ):
        assert phrase in disclaimers
    assert "not independent binary evidence" in e["method"]["structural_validation"]


@pytest.mark.parametrize("source", list(helper.SOURCE_PINS))
def test_rejects_tampered_sources(values: dict[str, Any], source: str) -> None:
    sources = dict(values["sources"])
    sources[source] = dict(sources[source], unexpected=True)
    with pytest.raises(Error):
        helper.validate_structure(values["evidence"], sources)


@pytest.mark.parametrize("variant", ["missing", "extra", "parent_edge"])
def test_rejects_source_partition_and_parent_tampering(
    values: dict[str, Any], variant: str
) -> None:
    sources = dict(values["sources"])
    if variant == "missing":
        sources.pop("pair")
    elif variant == "extra":
        sources["extra"] = {}
    else:
        sources["pair"] = _replace(
            sources["pair"],
            ("bodies", 0, "native_controls", "direct_calls", 0, "target_entry_rva"),
            "0x00379f1f",
        )
    with pytest.raises(Error):
        helper.validate_structure(values["evidence"], sources)


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("schema_version",), True),
        (("schema_version",), 1.0),
        (("analysis_kind",), "other"),
        (("summary", "instructions"), True),
        (("bodies",), []),
        (("bodies", 0, "body_size"), 7),
        (
            (
                "bodies",
                0,
                "conditional_effect",
                "result_on_normal_instruction_completion",
            ),
            "one",
        ),
        (("bodies", 0, "conditional_effect", "scope"), "unconditional runtime fact"),
        (("bodies", 0, "body_sha256"), "0" * 64),
        (("source_receipts", "pair", "canonical_sha256"), "0" * 64),
        (("parent_edges", 4, "target_evidence"), "new_body"),
        (("parent_edges", 4, "incoming_reference", "target_rva"), "0x00370960"),
        (("parent_edges", 0, "edge", "behavior_opaque"), False),
        (("bodies", 1, "control_flow_graph", "edge_count"), 103),
        (("bodies", 1, "control_flow_graph", "repeat_micro_iterations_expanded"), True),
        (
            ("bodies", 0, "control_flow_graph", "nodes", 0, "successor_rvas"),
            ["0xffffffff"],
        ),
        (("bodies", 0, "control_flow_graph", "nodes", 0, "repeat_prefix"), True),
        (
            ("bodies", 0, "native_controls", "direct_calls"),
            [{"target_entry_rva": "0x003574ca"}],
        ),
        (("bodies", 1, "operands", 0, "size"), True),
        (("bodies", 1, "operands", 0, "decoder_access"), 99),
        (("base_relocations", "sites"), []),
        (("whole_atlas_reference_scan", "scope", "functions"), 25311),
        (("whole_atlas_reference_scan", "target_partitions"), []),
        (("whole_atlas_reference_scan", "references_canonical_sha256"), "0" * 64),
        (("whole_atlas_reference_scan", "references"), []),
        (("method", "not_claimed"), []),
        (("unknown",), "unrecognized"),
        (("bodies", 0, "raw_bytes"), "proprietary"),
    ],
)
def test_seal_rejects_mutations(
    values: dict[str, Any],
    fast_preflight: None,
    path: tuple[Any, ...],
    replacement: Any,
) -> None:
    changed = _replace(values["evidence"], path, replacement)
    with pytest.raises(Error):
        helper.validate_structure(changed, values["sources"])


@pytest.mark.parametrize(
    "bad", [None, [], {"bad": float("nan")}, {1: "non-string key"}]
)
def test_invalid_evidence_is_normalized(
    values: dict[str, Any], fast_preflight: None, bad: Any
) -> None:
    with pytest.raises(Error):
        helper.validate_structure(bad, values["sources"])


def _writer_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = tmp_path.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("immutable publication must not delete a pathname")

    monkeypatch.setattr(cli.os, "unlink", forbidden)
    monkeypatch.setattr(Path, "unlink", forbidden)


def test_writer_idempotent_and_preserves_different_destination(
    values: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _writer_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = cli.encode(values["evidence"])
    cli._write_immutably(output, rendered, values["evidence"])
    identity = output.stat().st_ino
    cli._write_immutably(output, rendered, values["evidence"])
    assert output.stat().st_ino == identity
    stage = cli._retained_stage_path(tmp_path, rendered.encode())
    assert os.path.samefile(stage, output)
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(rendered.encode() + b" ")
    os.replace(replacement, output)
    with pytest.raises(Error, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode() + b" "
    assert stage.read_bytes() == rendered.encode()


@pytest.mark.parametrize("matching", [True, False])
def test_writer_concurrent_winner_is_retained(
    values: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    matching: bool,
) -> None:
    _writer_root(monkeypatch, tmp_path)
    output = tmp_path / "winner.json"
    rendered = cli.encode(values["evidence"])
    winner = rendered.encode() if matching else rendered.encode() + b" "

    def concurrent_create(source: Path, destination: Path, **kwargs: Any) -> None:
        destination.write_bytes(winner)
        raise FileExistsError("another publisher won")

    monkeypatch.setattr(cli.os, "link", concurrent_create)
    if matching:
        cli._write_immutably(output, rendered, values["evidence"])
    else:
        with pytest.raises(Error, match="refusing to overwrite"):
            cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == winner
    assert (
        cli._retained_stage_path(tmp_path, rendered.encode()).read_bytes()
        == rendered.encode()
    )


def test_writer_detects_replaced_stage_identity(
    values: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _writer_root(monkeypatch, tmp_path)
    output = tmp_path / "race.json"
    rendered = cli.encode(values["evidence"])
    contender = tmp_path / "contender.json"
    contender.write_bytes(rendered.encode())
    original_link = cli.os.link

    def replace_then_link(source: Path, destination: Path, **kwargs: Any) -> None:
        os.replace(contender, source)
        original_link(source, destination, **kwargs)

    monkeypatch.setattr(cli.os, "link", replace_then_link)
    with pytest.raises(Error, match="identity check"):
        cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode()


@pytest.mark.parametrize("mutation", ["bool", "other", "payload"])
def test_writer_rejects_nonsealed_identity(
    values: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    _writer_root(monkeypatch, tmp_path)
    e = copy.deepcopy(values["evidence"])
    if mutation == "bool":
        e["schema_version"] = True
    elif mutation == "other":
        e["analysis_kind"] = "other"
    else:
        e["summary"]["instructions"] = 19
    with pytest.raises(Error, match="sealed leaf identity"):
        cli._write_immutably(tmp_path / "bad.json", cli.encode(e), e)
    assert list(tmp_path.iterdir()) == []


def test_cli_structure_is_deterministic(
    values: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(_args(values)) == 0
    first = capsys.readouterr()
    assert first.err == ""
    assert json.loads(first.out)["status"] == "structurally_verified"
    assert cli.main(_args(values)) == 0
    second = capsys.readouterr()
    assert second.out == first.out
    assert second.err == ""


@pytest.mark.parametrize(
    "payload", [b"{bad json", b'{"schema_version":1,"schema_version":1}', b"[]"]
)
def test_cli_malformed_evidence_fails(
    values: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    payload: bytes,
) -> None:
    evidence = tmp_path / "bad.json"
    evidence.write_bytes(payload)
    args = _args(values)
    args[2] = str(evidence)
    assert cli.main(args) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error:" in captured.err


def test_exact_rebuild_and_cli_verify(
    values: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    configured = os.environ.get("ITB_EXACT_EXE")
    if not configured:
        pytest.skip("set ITB_EXACT_EXE to enable exact PE replay")
    executable = Path(configured)
    assert hashlib.sha256(executable.read_bytes()).hexdigest() == helper.EXE_SHA256
    rebuilt = helper.build_leaves(
        executable, values["sources"], inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    assert (
        helper.encode_leaves(rebuilt).encode()
        == values["paths"]["evidence"].read_bytes()
    )
    args = _args(values, "verify") + [
        "--executable",
        str(executable),
        "--inventory",
        str(values["paths"]["inventory"]),
    ]
    assert cli.main(args) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out)["status"] == "verified"
