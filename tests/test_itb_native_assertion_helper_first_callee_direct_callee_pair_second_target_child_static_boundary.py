"""Standalone replay, successor provenance, and immutable publication checks."""

from __future__ import annotations

import copy
import ast
import inspect
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from scripts import (
    itb_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary as cli,
)
from src.observatory import (
    native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary as base,
)
from src.observatory import (
    native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary as helper,
)
from src.observatory.native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary import (
    NativeAssertionHelperFirstCalleeDirectCalleePairSecondTargetChildStaticBoundaryError as Error,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
LEGACY_RAW_SHA256 = "25b174666130d3a5120dc4f01a66cdf3c5cdf657dd9010a2ba89f4137c902d0e"
LEGACY_CANONICAL_SHA256 = (
    "149115c259e411889adc3acee6bccb5c84a09b7ac8acafa0060726d5ee3703ed"
)

RAW_SHA256 = "9d5def6e41d69c2e2e231110c494f8a9f0e763c51b2df67102a73f133d27c1b5"
CANONICAL_SHA256 = "918628e05e4579a40127416853ed5e1af91fa6516e86798a48107a65f433be19"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    paths = {
        "inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"),
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "predecessor": PROGRAMS
        / (
            PREFIX
            + "native_assertion_helper_first_callee_direct_callee_pair_static_boundary.json"
        ),
        "evidence": PROGRAMS
        / (
            PREFIX
            + "native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_v2.json"
        ),
    }
    paths["legacy"] = paths["evidence"].with_name(
        paths["evidence"].name.replace("_v2.json", ".json")
    )
    if any(not path.is_file() for path in paths.values()):
        pytest.skip("second direct-callee-pair child prerequisites are unavailable")
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    return result


def _common(
    values: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return values["predecessor"], values["direct"], values["facts"]


def _structure(
    values: dict[str, Any], evidence: dict[str, Any] | None = None
) -> dict[str, Any]:
    return helper.validate_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary_structure(
        values["evidence"] if evidence is None else evidence, *_common(values)
    )


def _fast_structure(
    monkeypatch: pytest.MonkeyPatch, values: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    monkeypatch.setattr(helper, "_validate_json_tree", lambda *args, **kwargs: None)
    monkeypatch.setattr(helper, "_assert_publication_safe", lambda *args: None)
    monkeypatch.setattr(
        helper,
        "validate_native_lua_direct_call_structure",
        lambda *args, **kwargs: {
            "status": "structurally_verified",
            "evidence_sha256": helper._DIRECT,
        },
    )
    monkeypatch.setattr(
        helper,
        "_preflight",
        lambda *args, **kwargs: {
            "program_facts": copy.deepcopy(values["evidence"]["program_facts"]),
            "direct_callee_pair_static_boundary": copy.deepcopy(
                values["evidence"]["direct_callee_pair_static_boundary"]
            ),
            "direct_call_census": copy.deepcopy(
                values["evidence"]["direct_call_census"]
            ),
        },
    )
    monkeypatch.setattr(helper, "_target", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        helper,
        "_expected_scan",
        lambda *args, **kwargs: copy.deepcopy(
            values["evidence"]["whole_atlas_reference_scan"]
        ),
    )
    return _structure(values, evidence)


def _replace(value: Any, path: tuple[Any, ...], replacement: Any) -> Any:
    if not path:
        return replacement
    clone = dict(value) if isinstance(value, dict) else list(value)
    clone[path[0]] = _replace(value[path[0]], path[1:], replacement)
    return clone


def _changed(value: Any) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        return "tampered"
    if isinstance(value, list):
        return ["tampered"]
    raise AssertionError(f"unsupported mutation {value!r}")


def test_pinned_boundary_facts_and_explicit_noreturn_disclaimer(
    values: dict[str, Any],
) -> None:
    evidence = values["evidence"]
    body, graph, calls = (
        evidence["function_body"],
        evidence["control_flow_graph"],
        evidence["native_calls"],
    )
    assert (body["entry_rva"], body["body_size"], len(body["reviewed_points"])) == (
        "0x00379e77",
        122,
        43,
    )
    assert (
        body["body_sha256"],
        body["atlas_record_sha256"],
        body["control_flow_graph_canonical_sha256"],
    ) == (helper._BODY, helper._ATLAS, helper._CFG)
    assert (
        graph["node_count"],
        graph["edge_count"],
        helper._canonical_sha256(graph),
    ) == (43, 44, helper._CFG)
    assert graph["nodes"][-1] == {
        "rva": "0x00379eec",
        "size": 5,
        "sha256": "bab6c3367edd05a0223aff63cfc2700e26d271f72bd9a3d9a7c0128aa38713e0",
        "writes_esi": False,
        "writes_ebx": False,
        "writes_edi": False,
        "writes_esp": True,
        "flow_kind": "terminal",
        "successor_rvas": [],
    }
    assert any(
        "noreturn property for the final E8" in item
        for item in evidence["method"]["not_claimed"]
    )
    assert [
        (row["instruction"]["rva"], row["target_entry_rva"])
        for row in calls["outgoing_direct"]
    ] == [
        ("0x00379e88", "0x0038edb6"),
        ("0x00379ebd", "0x003574ca"),
        ("0x00379eec", "0x00379f1f"),
    ]
    assert body["call_r32_audit"] == [
        {"register": name, "call_rvas": ["0x00379eb2"] if name == "ESI" else []}
        for name in helper._REGISTER_NAMES
    ]
    assert calls["import_and_iat_body_controls"] == []
    controls = calls["opaque_indirect_controls"]
    assert controls[1]["control_slot"] == {
        "slot_va": "0x007d6580",
        "slot_rva": "0x003d6580",
        "slot_file_offset": "0x003d5580",
        "slot_raw": "707e4000",
        "slot_raw_sha256": "1a72a46736a7f349cfdc7c8851816c53aabe6830052b8b24e431d93ee4e8f52b",
        "section_name": ".rdata",
        "section_rva": "0x003d6000",
        "section_characteristics": "0x40000040",
        "section_writable": False,
        "contents_or_runtime_behavior_opaque": True,
    }
    assert [
        (row["instruction"]["rva"], row["operand_rva"], row["file_backed"])
        for row in calls["pe_address_operands"]
    ] == [
        ("0x00379e7d", "0x00493f28", True),
        ("0x00379ec9", "0x00493f28", True),
        ("0x00379ed4", "0x004b7080", False),
        ("0x00379eac", "0x003d6580", True),
    ]
    assert [
        (row["instruction"]["rva"], row["value_u32"])
        for row in calls["non_pe_immediate_literals"]
    ] == [("0x00379eb7", "0x00000014"), ("0x00379eda", "0x0000001f")]
    assert [
        row["site_rva"] for row in calls["base_relocation_scan"]["highlow_sites"]
    ] == ["0x00379e7e", "0x00379eae", "0x00379ecb", "0x00379ed6"]


def test_structural_replay_and_pinned_frontier(values: dict[str, Any]) -> None:
    result, scan = _structure(values), values["evidence"]["whole_atlas_reference_scan"]
    assert result["status"] == "structurally_verified"
    assert [
        (row["instruction_rva"], row["owner_entry_rva"]) for row in scan["references"]
    ] == [("0x00379ef9", "0x00379ef2"), ("0x00379f0c", "0x00379f02")]
    assert scan["partition_sha256"] == {
        "references": "103813edd926fdbe90a75084e1621aaaef7dbd835ff38e1e4b5cbc117f47c5a1",
        "target_partition": "927e9046e125d796824488475519f5bf30c9cffac4d299b51c90e256c6c618c3",
        "owner_partition": "df6b0ef6c827ee977efeddb2691f621fc82972a600cc97f67e772097ae80d03d",
        "target_owner_partition": "12ee3418d1fe375c9da0748390706d33462ee68b81ce8fd2951ddda55f09f06a",
        "target_reference_partition": "9b2ba111f293cbe554d961c7056e966a8fa57d689177b629c622bfb93ef461a0",
    }


@pytest.mark.parametrize(
    "path",
    [
        ("supersedes", "artifact"),
        ("supersedes", "raw_sha256"),
        ("supersedes", "canonical_sha256"),
        ("supersedes", "reason"),
        ("supersedes", "corrected_path"),
        ("build_identity", "architecture"),
        ("program_facts", "canonical_sha256"),
        ("direct_callee_pair_static_boundary", "canonical_sha256"),
        ("direct_call_census", "canonical_sha256"),
        ("function_body", "call_r32_audit", 6, "call_rvas"),
        ("function_body", "body_sha256"),
        ("control_flow_graph", "nodes", 42, "flow_kind"),
        ("native_calls", "outgoing_direct", 2, "target_entry_rva"),
        ("native_calls", "opaque_indirect_controls", 1, "control_slot", "slot_raw"),
        ("native_calls", "call_r32_audit", 6, "call_rvas"),
        ("native_calls", "pe_address_operands", 3, "section_name"),
        ("native_calls", "base_relocation_scan", "highlow_sites", 3, "entry_raw"),
        ("whole_atlas_reference_scan", "references", 1, "instruction_sha256"),
        ("whole_atlas_reference_scan", "partition_sha256", "references"),
        ("method", "not_claimed", 1),
    ],
)
def test_structure_rejects_representative_tampering(
    values: dict[str, Any], path: tuple[Any, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    current: Any = values["evidence"]
    for key in path:
        current = current[key]
    with pytest.raises(Error):
        _fast_structure(
            monkeypatch, values, _replace(values["evidence"], path, _changed(current))
        )


def test_deterministic_encoding_and_pinned_hashes(values: dict[str, Any]) -> None:
    rendered = cli.encode(values["evidence"])
    assert rendered.encode() == values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(rendered.encode()).hexdigest() == RAW_SHA256
    assert helper._canonical_sha256(values["evidence"]) == CANONICAL_SHA256
    assert (
        hashlib.sha256(values["paths"]["legacy"].read_bytes()).hexdigest()
        == LEGACY_RAW_SHA256
    )
    assert helper._canonical_sha256(values["legacy"]) == LEGACY_CANONICAL_SHA256


def _delta(left: Any, right: Any, path: tuple[Any, ...] = ()) -> set[tuple[Any, ...]]:
    if isinstance(left, dict) and isinstance(right, dict):
        changed = {path + (key,) for key in left.keys() ^ right.keys()}
        for key in left.keys() & right.keys():
            changed |= _delta(left[key], right[key], path + (key,))
        return changed
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return set().union(
            *(_delta(a, b, path + (i,)) for i, (a, b) in enumerate(zip(left, right)))
        )
    return set() if left == right else {path}


def test_exact_successor_delta_and_register_audits(values: dict[str, Any]) -> None:
    legacy, evidence = values["legacy"], values["evidence"]
    assert _delta(legacy, evidence) == {
        ("schema_version",),
        ("analysis_kind",),
        ("supersedes",),
        ("native_calls", "call_r32_audit", 6, "call_rvas"),
    }
    assert evidence["schema_version"] == 2
    assert evidence["analysis_kind"] == legacy["analysis_kind"] + "_v2"
    assert evidence["supersedes"] == {
        "artifact": values["paths"]["legacy"].name,
        "raw_sha256": LEGACY_RAW_SHA256,
        "canonical_sha256": LEGACY_CANONICAL_SHA256,
        "reason": "Correct the case-sensitive ESI register-call audit generator; executable and structural boundary unchanged.",
        "corrected_path": "native_calls.call_r32_audit[6].call_rvas",
    }
    expected = [
        {"register": name, "call_rvas": ["0x00379eb2"] if name == "ESI" else []}
        for name in helper._REGISTER_NAMES
    ]
    assert evidence["function_body"]["call_r32_audit"] == expected
    assert evidence["native_calls"]["call_r32_audit"] == expected
    assert all(not row["call_rvas"] for row in legacy["native_calls"]["call_r32_audit"])


def test_no_first_child_dependencies_or_mutable_configuration() -> None:
    for module in (helper, cli):
        tree = ast.parse(inspect.getsource(module))
        imports = [
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        imports += [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        assert not any("first_target_child" in name for name in imports)
        assert not hasattr(module, "_configured")
        assert not hasattr(module, "_ORIGINAL_EVIDENCE")
        assert not hasattr(module, "_writer")


def test_first_child_poison_does_not_affect_second_child(
    values: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("second child accessed the first child")

    for name, value in vars(base).copy().items():
        if inspect.isfunction(value) or name in (
            "ANALYSIS_KIND",
            "_ENTRY",
            "_OUTGOING",
        ):
            monkeypatch.setattr(base, name, forbidden)
    assert (
        _fast_structure(monkeypatch, values, values["evidence"])["status"]
        == "structurally_verified"
    )
    assert cli._identity(values["evidence"])


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("schema_version", 1),
        ("schema_version", True),
        ("analysis_kind", base.ANALYSIS_KIND),
    ],
)
def test_rejects_legacy_and_first_child_identity(
    values: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: Any,
) -> None:
    evidence = _replace(values["evidence"], (field,), replacement)
    with pytest.raises(Error):
        _fast_structure(monkeypatch, values, evidence)
    with pytest.raises(Error):
        cli._identity(evidence)


def test_schema_one_receipt_is_not_accepted_as_successor(
    values: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(Error):
        _fast_structure(monkeypatch, values, values["legacy"])
    with pytest.raises(Error):
        cli._identity(values["legacy"])


@pytest.mark.parametrize("operation", ["build", "verify"])
def test_exact_entrypoints_normalize_dependency_errors(
    values: dict[str, Any], monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    failure = ValueError("malformed prerequisite")

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise failure

    monkeypatch.setattr(helper, "_validate_json_tree", fail)
    with pytest.raises(Error, match="malformed prerequisite") as caught:
        if operation == "build":
            cli.build(
                Path("unused.exe"), *_common(values), inventory=values["inventory"]
            )
        else:
            cli.validate(
                Path("unused.exe"),
                values["evidence"],
                *_common(values),
                inventory=values["inventory"],
            )
    assert caught.value.__cause__ is failure


def test_normalizes_prerequisite_and_encoding_errors(
    values: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    failure = RuntimeError("prerequisite exploded")

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise failure

    monkeypatch.setattr(helper, "validate_native_lua_direct_call_structure", fail)
    with pytest.raises(Error, match="prerequisite exploded") as caught:
        _structure(values)
    assert caught.value.__cause__ is failure
    with pytest.raises(Error):
        cli.encode({"bad": float("nan")})
    with pytest.raises(Error):
        cli.encode({"bad": object()})


def test_deterministic_interleaved_first_and_second_child(
    values: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _fast_structure(monkeypatch, values, values["evidence"])
    gate = Barrier(2)
    original = helper._evidence
    first_entry, first_kind = base._ENTRY, base.ANALYSIS_KIND

    def interleaved(*args: Any, **kwargs: Any) -> Any:
        gate.wait(timeout=10)
        result = original(*args, **kwargs)
        gate.wait(timeout=10)
        return result

    monkeypatch.setattr(helper, "_evidence", interleaved)

    def first() -> tuple[str, int]:
        gate.wait(timeout=10)
        graph = base._graph()
        assert base._ENTRY == first_entry and base.ANALYSIS_KIND == first_kind
        gate.wait(timeout=10)
        return base._canonical_sha256(graph), graph["node_count"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        other = pool.submit(first)
        second = pool.submit(_structure, values)
        assert second.result(timeout=20)["evidence_sha256"] == helper._canonical_sha256(
            values["evidence"]
        )
        assert other.result(timeout=20) == (base._CFG, 53)
    assert base._ENTRY == first_entry and base.ANALYSIS_KIND == first_kind


def _patch_output_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = tmp_path.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def _forbid_unlink(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("immutable publication must not delete a pathname")

    monkeypatch.setattr(cli.os, "unlink", forbidden)
    monkeypatch.setattr(Path, "unlink", forbidden)


def test_writer_is_immutable_idempotent_and_preserves_different_output(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    _forbid_unlink(monkeypatch)
    output = tmp_path / "evidence.json"
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary(
        values["evidence"]
    )
    cli._write_immutably(output, rendered, values["evidence"])
    stage = cli._retained_stage_path(tmp_path, rendered.encode())
    assert stage.is_file() and os.path.samefile(stage, output)
    cli._write_immutably(output, rendered, values["evidence"])
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(rendered.encode() + b" ")
    os.replace(replacement, output)
    with pytest.raises(Error, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode() + b" "
    assert stage.read_bytes() == rendered.encode()


def test_writer_retains_stage_and_detects_stage_or_destination_races(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    _forbid_unlink(monkeypatch)
    output = tmp_path / "race.json"
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary(
        values["evidence"]
    )
    stage = cli._retained_stage_path(tmp_path, rendered.encode())
    stage.write_bytes(rendered.encode())
    contender = tmp_path / "contender.json"
    contender.write_bytes(b"contender")
    original_link = cli.os.link

    def replace_stage_then_link(source: Path, destination: Path, **kwargs: Any) -> None:
        os.replace(contender, source)
        original_link(source, destination, **kwargs)

    monkeypatch.setattr(cli.os, "link", replace_stage_then_link)
    with pytest.raises(Error, match="identity check"):
        cli._write_immutably(output, rendered, values["evidence"])
    assert stage.read_bytes() == b"contender"
    assert output.read_bytes() == b"contender"


@pytest.mark.parametrize("matching", [True, False])
def test_writer_destination_race_preserves_winner(
    values: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    matching: bool,
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    _forbid_unlink(monkeypatch)
    output = tmp_path / "winner.json"
    rendered = cli.encode(values["evidence"])
    winner = rendered.encode() if matching else rendered.encode() + b" "

    def concurrent_create(source: Path, destination: Path, **kwargs: Any) -> None:
        destination.write_bytes(winner)
        raise FileExistsError("concurrent publisher won")

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


def test_writer_rejects_first_child_before_publishing(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    _forbid_unlink(monkeypatch)
    evidence = _replace(values["evidence"], ("analysis_kind",), base.ANALYSIS_KIND)
    with pytest.raises(Error):
        cli._write_immutably(
            tmp_path / "wrong-child.json", cli.encode(evidence), evidence
        )
    assert list(tmp_path.iterdir()) == []


def test_writer_normalizes_shared_helper_error(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failure = cli.NativeLuaPropertyFactoryChainError("root changed")

    def fail() -> Any:
        raise failure

    monkeypatch.setattr(cli, "_prepare_output_root", fail)
    with pytest.raises(Error, match="root changed") as caught:
        cli._write_immutably(
            tmp_path / "evidence.json",
            cli.encode(values["evidence"]),
            values["evidence"],
        )
    assert caught.value.__cause__ is failure


@pytest.mark.parametrize(
    "path",
    [
        ("unexpected",),
        ("supersedes", "unexpected"),
        ("native_calls", "opaque_indirect_controls", 1, "control_slot", "unexpected"),
    ],
)
def test_structure_rejects_unknown_keys(
    values: dict[str, Any], monkeypatch: pytest.MonkeyPatch, path: tuple[Any, ...]
) -> None:
    evidence = copy.deepcopy(values["evidence"])
    node = evidence
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = "injected"
    with pytest.raises(Error):
        _fast_structure(monkeypatch, values, evidence)


def test_cli_parser_and_strict_json_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    parsed = cli.build_parser().parse_args(
        [
            "build",
            "--direct-callee-pair-static-boundary",
            "a.json",
            "--direct-calls",
            "b.json",
            "--program-facts",
            "c.json",
            "--inventory",
            "d.json",
            "--executable",
            "Breach.exe",
        ]
    )
    assert parsed.command == "build"
    bad = tmp_path / "bad.json"
    bad.write_bytes(b'{"x":NaN}')
    assert (
        cli.main(
            [
                "verify-structure",
                "--direct-callee-pair-static-boundary",
                str(bad),
                "--direct-calls",
                str(bad),
                "--program-facts",
                str(bad),
                "--evidence",
                str(bad),
            ]
        )
        == 1
    )
    assert capsys.readouterr().err.startswith("error: ")


def _exact_executable() -> Path:
    configured = os.environ.get("ITB_EXACT_EXE")
    if not configured:
        pytest.skip("set ITB_EXACT_EXE to run expensive exact PE checks")
    path = Path(configured)
    if (
        not path.is_file()
        or hashlib.sha256(path.read_bytes()).hexdigest() != EXE_SHA256
    ):
        pytest.skip("exact installed Breach.exe is unavailable")
    return path


def test_exact_build_verify_and_cli(
    values: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    executable = _exact_executable()
    rebuilt = helper.build_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary(
        executable, *_common(values), inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    assert (
        helper.validate_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary(
            executable,
            values["evidence"],
            *_common(values),
            inventory=values["inventory"],
        )[
            "status"
        ]
        == "verified"
    )
    paths = values["paths"]
    assert (
        cli.main(
            [
                "verify",
                "--direct-callee-pair-static-boundary",
                str(paths["predecessor"]),
                "--direct-calls",
                str(paths["direct"]),
                "--program-facts",
                str(paths["facts"]),
                "--inventory",
                str(paths["inventory"]),
                "--executable",
                str(executable),
                "--evidence",
                str(paths["evidence"]),
            ]
        )
        == 0
    )
    assert '"status": "verified"' in capsys.readouterr().out
