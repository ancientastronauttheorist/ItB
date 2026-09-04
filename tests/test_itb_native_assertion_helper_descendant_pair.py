"""Pinned frontier joins, conservative control flow, and immutable publication."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from scripts import itb_native_assertion_helper_descendant_pair as cli
from src.observatory import (
    native_assertion_helper_descendant_pair as helper,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CANONICAL = "47421700f38e3dbf3f5283bf89d3beb5d6421d32eaf05938ad58989908f93d0b"
RAW = "0c7fbea632343e29a05e8e9ec67f695021bbc8154e2bc7d2661e6ac8c859c1bc"
Error = helper.PairError


@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    suffixes = {
        "frontier": "native_assertion_helper_second_child_callee_frontier",
        "direct_calls": "native_lua_direct_call_census",
        "program_facts": "program_facts",
        "evidence": "native_assertion_helper_descendant_pair",
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
    assert helper.encode_pair(evidence).encode() == payload
    result = helper.validate_structure(evidence, values["sources"])
    assert result["status"] == "structurally_verified"
    assert result["evidence_sha256"] == CANONICAL
    assert result["summary"] == evidence["summary"]


def test_exact_target_partition_graphs_and_controls(values: dict[str, Any]) -> None:
    e = values["evidence"]
    assert e["summary"] == {
        "target_count": 2,
        "target_bytes": 321,
        "instructions": 79,
        "cfg_nodes": 79,
        "cfg_edges": 81,
        "parent_edges": 2,
        "outgoing_native_edges": 5,
        "import_controls": 4,
        "explicit_operands": 124,
        "ordinary_immediates": 10,
        "absolute_pe_address_operands": 5,
        "memory_expression_operands": 44,
        "segment_register_operands": 6,
        "highlow_sites": 5,
        "incoming_references": 8,
        "incoming_owners": 6,
    }
    assert [b["entry_rva"] for b in e["bodies"]] == ["0x00379d28", "0x0039cb92"]
    for body, expected in zip(e["bodies"], [(315, 78, 81), (6, 1, 0)]):
        graph = body["control_flow_graph"]
        nodes = graph["nodes"]
        assert (body["body_size"], graph["node_count"], graph["edge_count"]) == expected
        assert len(body["points"]) == len(nodes) == graph["node_count"]
        assert sum(n["size"] for n in nodes) == body["body_size"]
        assert sum(len(n["successor_rvas"]) for n in nodes) == graph["edge_count"]
        sites = {n["rva"] for n in nodes}
        assert len(sites) == len(nodes)
        assert all(s in sites for n in nodes for s in n["successor_rvas"])
        profile = helper.TARGETS[int(body["entry_rva"], 16)]
        assert body["body_sha256"] == profile["body_sha256"]
        assert body["atlas_record_sha256"] == profile["atlas_sha256"]
        assert body["analysis_metadata"]["metadata_only"] is True
        controls = body["native_controls"]
        assert controls["partitions_complete_for_pinned_bodies"] is True
        assert controls["interrupts"] == []
        assert all(r["call_rvas"] == [] for r in controls["register_calls"])
        assert all(
            r["behavior_opaque"] is True
            for r in controls["direct_calls"] + controls["import_controls"]
        )
        assert all(set(p) == {"rva", "size", "sha256"} for p in body["points"])
    body, thunk = e["bodies"]
    nodes = body["control_flow_graph"]["nodes"]
    assert sum(n["flow_kind"] == "direct_conditional_branch" for n in nodes) == 4
    assert sum(n["flow_kind"] == "return_syntax" for n in nodes) == 1
    assert sum(n["flow_kind"] == "call_possible_fallthrough" for n in nodes) == 8
    assert thunk["control_flow_graph"]["nodes"][0]["flow_kind"] == "opaque_import_jump"
    assert [
        (r["instruction"]["rva"], r["target_entry_rva"])
        for r in body["native_controls"]["direct_calls"]
    ] == [
        ("0x00379d47", "0x003586b6"),
        ("0x00379d58", "0x00370960"),
        ("0x00379d6b", "0x00370960"),
        ("0x00379e4e", "0x003586b6"),
        ("0x00379e5a", "0x003574ca"),
    ]
    imports = [r for b in e["bodies"] for r in b["native_controls"]["import_controls"]]
    assert [(r["slot_rva"], r["control_kind"]) for r in imports] == [
        ("0x003d6008", "call"),
        ("0x003d60e4", "call"),
        ("0x003d6018", "call"),
        ("0x003d6010", "jump"),
    ]
    for row in imports:
        binding = row["binding"]
        assert binding["name_metadata_only"] is True
        assert binding["metadata"]["library"] == "KERNEL32.dll"
        assert binding["iat_slot"]["sha256"] == binding["ilt_entry"]["sha256"]
        assert binding["iat_slot"]["rva"] == row["slot_rva"]
        assert binding["descriptor"]["size"] == 20
    assert len(e["base_relocations"]["sites"]) == 5
    assert all(r["type"] == "HIGHLOW" for r in e["base_relocations"]["sites"])


def test_parent_edges_and_whole_atlas_partitions(values: dict[str, Any]) -> None:
    e, sources = values["evidence"], values["sources"]
    scan = e["whole_atlas_reference_scan"]
    assert scan["scope"] == {
        "functions": 25312,
        "ranges": 25490,
        "bytes": 3735718,
        "instructions": 1153814,
    }
    assert scan["target_partitions"] == [
        {"entry_rva": "0x00379d28", "reference_count": 2, "owner_count": 2},
        {"entry_rva": "0x0039cb92", "reference_count": 6, "owner_count": 6},
    ]
    refs = scan["references"]
    assert len(refs) == scan["reference_count"] == 8
    assert len({r["owner_entry_rva"] for r in refs}) == scan["owner_count"] == 6
    assert helper._canonical_sha256(refs) == scan["references_canonical_sha256"]
    for part in scan["target_partitions"]:
        selected = [r for r in refs if r["target_entry_rva"] == part["entry_rva"]]
        assert len(selected) == part["reference_count"]
        assert len({r["owner_entry_rva"] for r in selected}) == part["owner_count"]
    assert len(e["parent_edges"]) == 2
    for index, parent in enumerate(e["parent_edges"]):
        assert parent["source_path"] == ["native_controls", "direct_calls", index]
        assert parent["source_canonical_sha256"] == helper.SOURCE_PINS["frontier"][1]
        source = sources["frontier"]
        for component in parent["source_path"]:
            source = source[component]
        assert parent["edge"] == source
        assert (
            sum(
                r["instruction"] == source["instruction"]
                and r["target_entry_rva"] == source["target_entry_rva"]
                and r["owner_entry_rva"] == "0x00379f1f"
                for r in refs
            )
            == 1
        )
    assert [
        (p["edge"]["instruction"]["rva"], p["edge"]["target_entry_rva"])
        for p in e["parent_edges"]
    ] == [("0x00379f21", "0x0039cb92"), ("0x00379f3a", "0x00379d28")]


def test_segment_register_sources_are_not_segment_dereferences(
    values: dict[str, Any],
) -> None:
    e = values["evidence"]
    body = e["bodies"][0]
    operands = body["operands"]
    segments = [
        o for o in operands if o.get("register") in {"ss", "cs", "ds", "es", "fs", "gs"}
    ]
    assert [o["register"] for o in segments] == ["ss", "cs", "ds", "es", "fs", "gs"]
    nodes = {n["rva"]: n for n in body["control_flow_graph"]["nodes"]}
    for source in segments:
        assert (
            source["kind"],
            source["operand_index"],
            source["size"],
            source["decoder_access"],
        ) == ("register", 1, 2, 1)
        (destination,) = [
            o
            for o in operands
            if o["instruction"] == source["instruction"] and o["operand_index"] == 0
        ]
        assert (
            destination["kind"],
            destination["base"],
            destination["size"],
            destination["decoder_access"],
        ) == ("memory_expression", "ebp", 2, 2)
        assert destination["segment"] is None
        assert destination["index"] is None
        assert nodes[source["instruction"]["rva"]]["operand_size_override"] is True
    memory = [
        o
        for b in e["bodies"]
        for o in b["operands"]
        if o["kind"] == "memory_expression"
    ]
    assert len(memory) == 44
    assert all(o["segment"] is None for o in memory)
    addresses = [o["absolute_pe_address"] for o in memory if "absolute_pe_address" in o]
    assert len(addresses) == 5
    assert all(a["contents_and_runtime_meaning_opaque"] is True for a in addresses)
    disclaimers = " ".join(e["method"]["not_claimed"])
    for phrase in (
        "LEA does not establish a memory read",
        "segment-register operands",
        "CRT identity",
        "normal return",
        "Recursive closure",
        "accounting-level promotion",
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
        sources.pop("frontier")
    elif variant == "extra":
        sources["extra"] = {}
    else:
        sources["frontier"] = _replace(
            sources["frontier"],
            ("native_controls", "direct_calls", 0, "target_entry_rva"),
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
        (("summary", "incoming_owners"), 0),
        (("bodies",), []),
        (("bodies", 0, "body_size"), 314),
        (("bodies", 0, "body_sha256"), "0" * 64),
        (("bodies", 0, "analysis_metadata", "metadata_only"), 1),
        (("source_receipts", "frontier", "canonical_sha256"), "0" * 64),
        (("parent_edges", 0, "source_path"), ["native_controls", "direct_calls", 99]),
        (("parent_edges", 0, "edge", "behavior_opaque"), False),
        (("bodies", 0, "control_flow_graph", "edge_count"), 80),
        (
            ("bodies", 0, "control_flow_graph", "nodes", 0, "successor_rvas"),
            ["0xffffffff"],
        ),
        (("bodies", 1, "control_flow_graph", "nodes", 0, "flow_kind"), "return_syntax"),
        (("bodies", 0, "native_controls", "direct_calls"), []),
        (
            (
                "bodies",
                0,
                "native_controls",
                "import_controls",
                0,
                "binding",
                "iat_slot",
                "sha256",
            ),
            "0" * 64,
        ),
        (
            ("bodies", 1, "native_controls", "import_controls", 0, "control_kind"),
            "call",
        ),
        (("bodies", 0, "operands", 0, "size"), True),
        (("bodies", 0, "operands", 0, "decoder_access"), 99),
        (("bodies", 0, "operands", 0, "instruction", "rva"), "0xffffffff"),
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
    with pytest.raises(Error, match="sealed pair identity"):
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
    rebuilt = helper.build_pair(
        executable, values["sources"], inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    assert (
        helper.encode_pair(rebuilt).encode() == values["paths"]["evidence"].read_bytes()
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
