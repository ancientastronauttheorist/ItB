"""Exact and adversarial checks for the first direct-callee-pair child."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from scripts import (
    itb_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary as cli,
)
from src.observatory import (
    native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary as helper,
)
from src.observatory.native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary import (
    NativeAssertionHelperFirstCalleeDirectCalleePairFirstTargetChildStaticBoundaryError as Error,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE_SHA256 = helper._EXE
RAW_SHA256 = "eac8de889925d07bc807f1ec676c143348d2729bc51d6ecbc402f08ca2ef3eab"
CANONICAL_SHA256 = "314c5817e3a1560c446853474cc0f86fbf3a8195fb60f48c85822a3ed8aca3bc"


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
            + "native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary.json"
        ),
    }
    if any(not path.is_file() for path in paths.values()):
        pytest.skip("first direct-callee-pair child prerequisites are unavailable")
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
    return helper.validate_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary_structure(
        values["evidence"] if evidence is None else evidence, *_common(values)
    )


def _fast_structure(
    monkeypatch: pytest.MonkeyPatch,
    values: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Exercise the receipt equality contract without rewalking prerequisites."""
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
    if value is None:
        return "tampered"
    if isinstance(value, list):
        return ["tampered"]
    if isinstance(value, dict):
        return {"tampered": True}
    raise AssertionError(f"unsupported mutation value {value!r}")


def test_pinned_body_cfg_calls_operands_imports_and_relocations(
    values: dict[str, Any],
) -> None:
    evidence = values["evidence"]
    body = evidence["function_body"]
    assert (body["entry_rva"], body["body_size"], len(body["reviewed_points"])) == (
        "0x0038edb6",
        133,
        53,
    )
    assert (
        body["body_sha256"],
        body["atlas_record_sha256"],
        body["control_flow_graph_canonical_sha256"],
    ) == (helper._BODY, helper._ATLAS, helper._CFG)
    graph = evidence["control_flow_graph"]
    assert (graph["caller_entry_rva"], graph["node_count"], graph["edge_count"]) == (
        "0x0038edb6",
        53,
        57,
    )
    assert helper._canonical_sha256(graph) == helper._CFG
    calls = evidence["native_calls"]
    assert [
        (row["instruction"]["rva"], row["target_entry_rva"])
        for row in calls["outgoing_direct"]
    ] == [
        ("0x0038edd0", "0x00391064"),
        ("0x0038ede2", "0x00388c36"),
        ("0x0038edf0", "0x00389156"),
        ("0x0038edff", "0x003910ba"),
        ("0x0038ee11", "0x0038eba4"),
        ("0x0038ee17", "0x00389156"),
    ]
    assert [
        (
            row["instruction"]["rva"],
            row["operand_class"],
            row["operand_rva"],
            row["file_backed"],
        )
        for row in calls["pe_address_operands"]
    ] == [
        ("0x0038edc5", "absolute_memory", "0x00494290", True),
        ("0x0038edf9", "absolute_memory", "0x00494290", True),
        ("0x0038ee0b", "immediate", "0x004b7550", False),
    ]
    assert [
        (row["instruction"]["rva"], row["value_u32"])
        for row in calls["non_pe_immediate_literals"]
    ] == [
        ("0x0038edca", "0xffffffff"),
        ("0x0038eddb", "0x00000364"),
        ("0x0038ede0", "0x00000001"),
        ("0x0038ee1c", "0x0000000c"),
    ]
    controls = calls["import_and_iat_body_controls"]
    assert [
        (
            row["instruction"]["rva"],
            row["iat_rva"],
            row["import_binding"]["import_name"],
            row["import_binding"]["hint"],
        )
        for row in controls
    ] == [
        ("0x0038edbb", "0x003d6114", "GetLastError", 514),
        ("0x0038ee24", "0x003d60dc", "SetLastError", 1139),
        ("0x0038ee2d", "0x003d60dc", "SetLastError", 1139),
    ]
    assert all(
        row["import_binding"]["descriptor_raw"]
        == "80ed48000000000000000000fe05490000603d00"
        for row in controls
    )
    relocations = calls["base_relocation_scan"]
    assert relocations["directory"] == {
        "rva": "0x00539000",
        "size": 218648,
        "file_offset": "0x00510a00",
        "sha256": "06630f9047636fb68afba81d89dbc1ef2f21c459b684d57d1d2bcaeb3750dfa3",
    }
    assert [row["site_rva"] for row in relocations["highlow_sites"]] == [
        "0x0038edbd",
        "0x0038edc6",
        "0x0038edfb",
        "0x0038ee0c",
        "0x0038ee26",
        "0x0038ee2f",
    ]


def test_structural_parent_join_and_complete_frontier(values: dict[str, Any]) -> None:
    result = _structure(values)
    evidence = values["evidence"]
    assert result["status"] == "structurally_verified"
    assert [
        (row["instruction"]["rva"], row["source_entry_rva"], row["target_entry_rva"])
        for row in evidence["predecessor_parent_edges"]
    ] == [("0x00385bcc", "0x00385bcc", "0x0038edb6")]
    scan = evidence["whole_atlas_reference_scan"]
    assert [
        (row["instruction_rva"], row["owner_entry_rva"]) for row in scan["references"]
    ] == [
        ("0x00379e88", "0x00379e77"),
        ("0x00385bb9", "0x00385bb9"),
        ("0x00385bcc", "0x00385bcc"),
        ("0x0038928d", "0x00389287"),
        ("0x0038bc6c", "0x0038bc5a"),
        ("0x0038e812", "0x0038e7b8"),
    ]
    assert scan["partition_sha256"] == helper._SCAN_HASHES
    assert scan["aggregates"] == {
        "reference_count": 6,
        "target_count": 1,
        "owner_count": 6,
        "target_owner_count": 6,
        "direct_call_count": 6,
        "comparison_count": 0,
        "other_address_count": 0,
        "memory_operand_count": 0,
    }


TAMPER_PATHS = [
    ("schema_version",),
    ("analysis_kind",),
    ("build_identity", "architecture"),
    ("program_facts", "canonical_sha256"),
    ("direct_callee_pair_static_boundary", "canonical_sha256"),
    ("direct_call_census", "canonical_sha256"),
    ("decoder", "sealed_instruction_count"),
    ("function_body", "body_sha256"),
    ("function_body", "reviewed_points", 52, "sha256"),
    ("function_body", "semantic_facts", "relationship_defined_only"),
    ("control_flow_graph", "nodes", 9, "successor_rvas"),
    ("predecessor_parent_edges", 0, "target_atlas_record_sha256"),
    ("native_calls", "outgoing_direct", 5, "target_entry_rva"),
    ("native_calls", "outgoing_direct_partition_complete"),
    ("native_calls", "import_and_iat_body_controls", 1, "import_binding", "hint"),
    ("native_calls", "pe_address_operands", 2, "file_backed"),
    ("native_calls", "non_pe_immediate_literals", 0, "value_u32"),
    ("native_calls", "base_relocation_scan", "highlow_sites", 5, "entry_raw"),
    ("whole_atlas_reference_scan", "references", 5, "instruction_sha256"),
    ("whole_atlas_reference_scan", "owner_partition", 0, "owner_entry_rva"),
    ("whole_atlas_reference_scan", "partition_sha256", "references"),
    ("whole_atlas_reference_scan", "aggregates", "owner_count"),
    ("method", "not_claimed", 0),
    ("summary", "target_reference_count"),
]


@pytest.mark.parametrize("path", TAMPER_PATHS)
def test_structure_rejects_representative_nested_tampering(
    values: dict[str, Any], path: tuple[Any, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    current: Any = values["evidence"]
    for key in path:
        current = current[key]
    with pytest.raises(Error):
        _fast_structure(
            monkeypatch, values, _replace(values["evidence"], path, _changed(current))
        )


@pytest.mark.parametrize(
    "path",
    [
        ("unexpected",),
        ("function_body", "unexpected"),
        ("native_calls", "outgoing_direct", 0, "unexpected"),
        ("whole_atlas_reference_scan", "references", 0, "unexpected"),
        ("summary", "unexpected"),
    ],
)
def test_structure_rejects_unknown_keys(
    values: dict[str, Any], path: tuple[Any, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = copy.deepcopy(values["evidence"])
    node: Any = evidence
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = "injected"
    with pytest.raises(Error):
        _fast_structure(monkeypatch, values, evidence)


def test_deterministic_encoding_and_pinned_hashes(values: dict[str, Any]) -> None:
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary(
        values["evidence"]
    )
    assert rendered.encode() == values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(rendered.encode()).hexdigest() == RAW_SHA256
    assert helper._canonical_sha256(values["evidence"]) == CANONICAL_SHA256
    with pytest.raises(Error):
        helper.encode_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary(
            {"bad": float("nan")}
        )


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
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary(
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
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary(
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
    rebuilt = helper.build_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary(
        executable, *_common(values), inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    receipt = helper.validate_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary(
        executable, values["evidence"], *_common(values), inventory=values["inventory"]
    )
    assert receipt["status"] == "verified"
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
