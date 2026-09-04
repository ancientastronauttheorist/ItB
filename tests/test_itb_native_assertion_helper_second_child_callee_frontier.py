"""Pinned frontier joins, conservative control flow, and immutable publication."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from scripts import itb_native_assertion_helper_second_child_callee_frontier as cli
from src.observatory import (
    native_assertion_helper_second_child_callee_frontier as helper,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CANONICAL = "39a712704c58f0789580ebac647ce13ae23681a1df12f0dc93d549159e37ddeb"
RAW = "19a5d65db948083b985d0eca8757db5c4663d5892decdef69a1c87fb6b5de9f3"
Error = helper.FrontierError


@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    suffixes = {
        "second_child": "native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_v2",
        "first_child": "native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary",
        "reused_callee": "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary",
        "direct_calls": "native_lua_direct_call_census",
        "program_facts": "program_facts",
        "evidence": "native_assertion_helper_second_child_callee_frontier",
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
    assert helper.encode_frontier(evidence).encode() == payload
    result = helper.validate_structure(evidence, values["sources"])
    assert result["status"] == "structurally_verified"
    assert result["evidence_sha256"] == CANONICAL
    assert result["summary"] == evidence["summary"]


def test_new_body_scope_counts_and_interrupt_are_conservative(
    values: dict[str, Any],
) -> None:
    e = values["evidence"]
    body, graph, controls, scan = (
        e["function_body"],
        e["control_flow_graph"],
        e["native_controls"],
        e["whole_atlas_reference_scan"],
    )
    assert (body["entry_rva"], body["body_size"], len(body["points"])) == (
        "0x00379f1f",
        51,
        20,
    )
    assert body["body_sha256"] == helper.BODY_SHA256
    assert body["atlas_record_sha256"] == helper.ATLAS_SHA256
    assert graph["node_count"] == len(graph["nodes"]) == 20
    assert (
        graph["edge_count"]
        == sum(len(n["successor_rvas"]) for n in graph["nodes"])
        == 20
    )
    assert sum(n["size"] for n in graph["nodes"]) == 51
    sites = {n["rva"] for n in graph["nodes"]}
    assert all(s in sites for n in graph["nodes"] for s in n["successor_rvas"])
    interrupt = next(n for n in graph["nodes"] if n["rva"] == "0x00379f2d")
    assert interrupt["flow_kind"] == "opaque_interrupt_possible_fallthrough"
    assert interrupt["successor_rvas"] == ["0x00379f2f"]
    assert controls["interrupts"][0]["vector"] == 0x29
    assert controls["interrupts"][0]["runtime_behavior_opaque"] is True
    assert [
        (r["instruction"]["rva"], r["target_entry_rva"])
        for r in controls["direct_calls"]
    ] == [("0x00379f21", "0x0039cb92"), ("0x00379f3a", "0x00379d28")]
    assert len(controls["import_calls"]) == 2
    assert len(controls["ordinary_immediates"]) == 6
    assert all(r["meaning_opaque"] is True for r in controls["ordinary_immediates"])
    assert all(
        r["behavior_opaque"] is True
        for r in controls["direct_calls"] + controls["import_calls"]
    )
    assert all(r["call_rvas"] == [] for r in controls["register_calls"])
    assert [r["site_rva"] for r in e["base_relocations"]["sites"]] == [
        "0x00379f45",
        "0x00379f4c",
    ]
    assert scan["scope"] == {
        "functions": 25312,
        "ranges": 25490,
        "bytes": 3735718,
        "instructions": 1153814,
    }
    refs = scan["references"]
    assert scan["reference_count"] == len(refs) == 45
    assert scan["owner_count"] == len({r["owner_entry_rva"] for r in refs}) == 45
    assert scan["references_canonical_sha256"] == helper._canonical_sha256(refs)
    assert e["summary"] == {
        "parent_direct_edges": 3,
        "reused_target_bodies": 2,
        "new_target_bodies": 1,
        "new_body_bytes": 51,
        "instructions": 20,
        "cfg_nodes": 20,
        "cfg_edges": 20,
        "outgoing_native_edges": 2,
        "import_controls": 2,
        "interrupt_controls": 1,
        "ordinary_literals": 6,
        "highlow_sites": 2,
        "incoming_references": 45,
        "incoming_owners": 45,
    }
    disclaimers = " ".join(e["method"]["not_claimed"])
    for phrase in (
        "CRT identity",
        "runtime reachability",
        "normal return",
        "Recursive closure",
        "accounting-level promotion",
    ):
        assert phrase in disclaimers
    assert "no executable evidence is inferred" in e["method"]["structural_validation"]


def test_all_parent_edges_join_exact_source_reference_paths(
    values: dict[str, Any],
) -> None:
    e, sources = values["evidence"], values["sources"]
    joins = e["direct_callee_joins"]
    assert len(joins) == 3
    assert [j["evidence"] for j in joins] == [
        "first_child",
        "reused_callee",
        "new_function_body",
    ]
    for index, join in enumerate(joins):
        assert (
            join["parent_edge"]
            == sources["second_child"]["native_calls"]["outgoing_direct"][index]
        )
        assert join["behavior_opaque"] is True
        if index < 2:
            name = join["evidence"]
            reference = sources[name]
            path = join["reference_path"]
            assert path[:2] == ["whole_atlas_reference_scan", "references"]
            assert type(path[2]) is int
            for component in path:
                reference = reference[component]
            assert reference == join["incoming_reference"]
            assert join["source_canonical_sha256"] == helper.SOURCE_PINS[name][1]
            assert (
                reference["instruction_rva"]
                == join["parent_edge"]["instruction"]["rva"]
            )
    parent_refs = [
        r
        for r in e["whole_atlas_reference_scan"]["references"]
        if r["instruction"]["rva"] == "0x00379eec"
    ]
    assert len(parent_refs) == 1
    assert parent_refs[0]["owner_entry_rva"] == "0x00379e77"


@pytest.mark.parametrize("source", list(helper.SOURCE_PINS))
def test_rejects_tampered_sources(values: dict[str, Any], source: str) -> None:
    sources = dict(values["sources"])
    sources[source] = dict(sources[source], unexpected=True)
    with pytest.raises(Error):
        helper.validate_structure(values["evidence"], sources)


@pytest.mark.parametrize("variant", ["missing", "extra", "legacy", "parent_edge"])
def test_rejects_source_partition_and_parent_downgrade(
    values: dict[str, Any], variant: str
) -> None:
    sources = dict(values["sources"])
    if variant == "missing":
        sources.pop("reused_callee")
    elif variant == "extra":
        sources["extra"] = {}
    elif variant == "legacy":
        path = values["paths"]["second_child"]
        sources["second_child"] = json.loads(
            path.with_name(path.name.replace("_v2.json", ".json")).read_text(
                encoding="utf-8"
            )
        )
    else:
        sources["second_child"] = _replace(
            sources["second_child"],
            ("native_calls", "outgoing_direct", 0, "target_entry_rva"),
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
        (("summary", "incoming_owners"), 44),
        (("function_body", "body_size"), 50),
        (("function_body", "body_sha256"), "0" * 64),
        (("function_body", "analysis_metadata", "metadata_only"), 1),
        (("source_receipts", "second_child", "canonical_sha256"), "0" * 64),
        (
            ("direct_callee_joins", 0, "reference_path"),
            ["whole_atlas_reference_scan", "references", 999],
        ),
        (("direct_callee_joins", 1, "behavior_opaque"), False),
        (("control_flow_graph", "edge_count"), 19),
        (("control_flow_graph", "nodes", 6, "successor_rvas"), []),
        (("control_flow_graph", "nodes", 6, "flow_kind"), "noreturn"),
        (("control_flow_graph", "nodes", 0, "successor_rvas"), ["0xffffffff"]),
        (("native_controls", "interrupts", 0, "vector"), 29),
        (("native_controls", "ordinary_immediates"), []),
        (("base_relocations", "sites"), []),
        (("whole_atlas_reference_scan", "scope", "functions"), 25311),
        (("whole_atlas_reference_scan", "references_canonical_sha256"), "0" * 64),
        (("whole_atlas_reference_scan", "references"), []),
        (("method", "not_claimed"), []),
        (("unknown",), "unrecognized"),
        (("function_body", "raw_bytes"), "proprietary"),
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
    with pytest.raises(Error, match="sealed frontier identity"):
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
    rebuilt = helper.build_frontier(
        executable, values["sources"], inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    assert (
        helper.encode_frontier(rebuilt).encode()
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
