from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.final_end_settlement import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    FinalEndSettlementError,
    validate_final_end_settlement_map,
    validate_final_end_settlement_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
SETTLEMENT_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_final_end_settlement.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(SETTLEMENT_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_final_end_and_effect_settlement_boundaries():
    value = _load()
    result = validate_final_end_settlement_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "541237f7e723c1ec56b0328cb1f137f2"
            "a6725bda55c588d0a7ebc74adc55be0c"
        ),
        "final_end_state_trigger_proven": True,
        "mission_effect_handoff_gate_proven": True,
        "post_travel_campaign_victory_proven": False,
        "simulator_change_required": False,
    }
    assert value["identity"]["executable_sha256"] == (
        EXPECTED_EXECUTABLE_SHA256
    )
    assert value["summary"] == {
        "lua_source_count": 3,
        "region_count": 15,
        "string_anchor_count": 4,
        "data_pointer_count": 2,
        "control_window_count": 11,
        "direct_edge_count": 8,
        "finding_count": 7,
        "unresolved_count": 3,
        "final_end_state_trigger_proven": True,
        "mission_effect_handoff_gate_proven": True,
        "post_travel_campaign_victory_proven": False,
        "simulator_change_required": False,
    }
    assert value["supersedes"]["resolved_gap_ids"] == [
        "final_end_state_trigger",
        "mission_end_effect_settlement",
    ]

    contracts = value["contracts"]
    assert contracts["ordinary_final_end_trigger"] == {
        "inputs": [
            "active Board pointer is nonzero",
            "current turn equals Mission:GetTurnLimit()",
            "BoardPlayer state equals 2",
        ],
        "result": "end_readiness returns true",
        "is_end_blocked_invoked_on_this_branch": False,
        "applies_to": ["Mission_Final", "Mission_Final_Cave"],
        "cave_extension_behavior": (
            "Mission_Final_Cave may increase TurnLimit by 2 after a "
            "missing bomb; the equality check uses the current Lua value."
        ),
    }
    assert contracts["mission_end_effect_handoff"][
        "nonempty_activity_reason"
    ] == 6
    assert contracts["mission_end_effect_handoff"][
        "handoff_requires_activity_clear"
    ] is True

    findings = {item["id"]: item for item in value["findings"]}
    assert "before constructing or invoking IsEndBlocked" in findings[
        "final_limit_bypasses_end_block"
    ]["claim"]
    assert "Board activity reason 6" in findings[
        "queued_effect_is_board_activity"
    ]["claim"]
    assert "state 5" in findings[
        "phase_handoff_waits_for_activity_clear"
    ]["claim"]
    assert "No Rust simulator semantic change" in findings[
        "solver_boundary"
    ]["claim"]

    unresolved = {item["id"] for item in value["unresolved"]}
    assert unresolved == {
        "post_travel_campaign_victory",
        "arbitrary_effect_cancellation",
        "non_windows_equivalence",
    }


def test_binding_rejects_pointer_source_or_prose_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["data_pointers"][0]["target_rva"] = "0x00000000"
    with pytest.raises(FinalEndSettlementError, match="fields differ"):
        validate_final_end_settlement_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["sources"]["lua_files"][0]["sha256"] = "0" * 64
    with pytest.raises(FinalEndSettlementError, match="fields differ"):
        validate_final_end_settlement_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["findings"][0]["claim"] += " overclaim"
    with pytest.raises(FinalEndSettlementError, match="fields differ"):
        validate_final_end_settlement_map_binding(altered)


def test_exact_local_executable_and_sources_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_final_end_settlement_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["final_end_state_trigger_proven"] is True
    assert result["mission_effect_handoff_gate_proven"] is True
    assert result["post_travel_campaign_victory_proven"] is False
