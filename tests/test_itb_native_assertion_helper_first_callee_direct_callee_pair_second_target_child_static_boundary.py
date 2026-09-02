"""Focused structural and delegation checks for the second pair child."""

from __future__ import annotations

import copy
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
RAW_SHA256 = "25b174666130d3a5120dc4f01a66cdf3c5cdf657dd9010a2ba89f4137c902d0e"
CANONICAL_SHA256 = "149115c259e411889adc3acee6bccb5c84a09b7ac8acafa0060726d5ee3703ed"


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
            + "native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary.json"
        ),
    }
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
    monkeypatch.setattr(base, "_validate_json_tree", lambda *args, **kwargs: None)
    monkeypatch.setattr(base, "_assert_publication_safe", lambda *args: None)
    monkeypatch.setattr(
        base,
        "validate_native_lua_direct_call_structure",
        lambda *args, **kwargs: {
            "status": "structurally_verified",
            "evidence_sha256": base._DIRECT,
        },
    )
    monkeypatch.setattr(
        base,
        "_preflight",
        lambda *args, **kwargs: {
            "program_facts": copy.deepcopy(evidence["program_facts"]),
            "direct_callee_pair_static_boundary": copy.deepcopy(
                evidence["direct_callee_pair_static_boundary"]
            ),
            "direct_call_census": copy.deepcopy(evidence["direct_call_census"]),
        },
    )
    monkeypatch.setattr(base, "_target", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        base,
        "_expected_scan",
        lambda *args, **kwargs: copy.deepcopy(evidence["whole_atlas_reference_scan"]),
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
        for name in base._REGISTER_NAMES
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


def test_deterministic_encoding_and_delegated_globals_restore_on_success_and_exception(
    values: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_second_target_child_static_boundary(
        values["evidence"]
    )
    assert rendered.encode() == values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(rendered.encode()).hexdigest() == RAW_SHA256
    assert helper._canonical_sha256(values["evidence"]) == CANONICAL_SHA256
    names = ("ANALYSIS_KIND", "_ENTRY", "_OUTGOING", "_evidence")
    original = {name: getattr(base, name) for name in names}
    observed: list[dict[str, Any]] = []

    def success(*args: Any, **kwargs: Any) -> dict[str, Any]:
        observed.append({name: getattr(base, name) for name in names})
        return {"status": "structurally_verified"}

    monkeypatch.setattr(
        base,
        "validate_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary_structure",
        success,
    )
    assert _structure(values) == {"status": "structurally_verified"}
    assert (
        observed[0]["ANALYSIS_KIND"] == helper.ANALYSIS_KIND
        and observed[0]["_ENTRY"] == helper._ENTRY
    )
    assert {name: getattr(base, name) for name in names} == original

    def failure(*args: Any, **kwargs: Any) -> dict[str, Any]:
        assert (
            base.ANALYSIS_KIND == helper.ANALYSIS_KIND and base._ENTRY == helper._ENTRY
        )
        raise RuntimeError("delegated failure")

    monkeypatch.setattr(
        base,
        "validate_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary_structure",
        failure,
    )
    with pytest.raises(RuntimeError, match="delegated failure"):
        _structure(values)
    assert {name: getattr(base, name) for name in names} == original


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
