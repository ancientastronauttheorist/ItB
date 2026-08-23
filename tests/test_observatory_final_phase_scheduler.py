from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.final_phase_scheduler import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    FinalPhaseSchedulerError,
    validate_final_phase_scheduler_map,
    validate_final_phase_scheduler_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEDULER_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_final_phase_scheduler.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(SCHEDULER_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_relative_handoff_without_claiming_trigger():
    value = _load()
    result = validate_final_phase_scheduler_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "93b022aa4d7c745805e68485d9a6fc36"
            "466ac3cb713b519d1cfe648d1a63a79a"
        ),
        "relative_handoff_order_proven": True,
        "final_surface_target_proven": True,
        "final_end_state_trigger_proven": False,
        "simulator_change_required": False,
    }
    assert value["identity"]["executable_sha256"] == (
        EXPECTED_EXECUTABLE_SHA256
    )
    assert value["summary"] == {
        "lua_source_count": 4,
        "region_count": 7,
        "string_anchor_count": 7,
        "control_window_count": 7,
        "direct_edge_count": 7,
        "finding_count": 6,
        "unresolved_count": 4,
        "relative_handoff_order_proven": True,
        "final_surface_target_proven": True,
        "final_end_state_trigger_proven": False,
        "mission_effect_settlement_proven": False,
        "simulator_change_required": False,
        "remaining_runtime_proof": [
            "Final end-state trigger",
            "MissionEnd queued-effect settlement",
            "cave startup callback and RNG order",
            "cave countdown outcome settlement",
            "non-Windows build equivalence",
        ],
    }

    findings = {item["id"]: item for item in value["findings"]}
    assert "MissionEnd" in findings["mission_end_callback_order"]["claim"]
    assert "IsNextPhase" in findings["native_phase_handoff_order"]["claim"]
    assert "Mission_Final_Cave" in findings["final_surface_target"]["claim"]
    assert "No current-turn combat simulation change" in findings[
        "solver_boundary"
    ]["claim"]

    unresolved = {item["id"] for item in value["unresolved"]}
    assert unresolved == {
        "final_end_state_trigger",
        "mission_end_effect_settlement",
        "cave_start_order",
        "cave_countdown_outcome",
    }


def test_binding_rejects_control_flow_source_or_prose_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["direct_call_edges"][0]["instruction_hex"] = "90"
    with pytest.raises(FinalPhaseSchedulerError, match="fields differ"):
        validate_final_phase_scheduler_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["sources"]["lua_files"][0]["sha256"] = "0" * 64
    with pytest.raises(FinalPhaseSchedulerError, match="fields differ"):
        validate_final_phase_scheduler_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["findings"][0]["claim"] += " overclaim"
    with pytest.raises(FinalPhaseSchedulerError, match="fields differ"):
        validate_final_phase_scheduler_map_binding(altered)


def test_exact_local_executable_and_sources_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_final_phase_scheduler_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["relative_handoff_order_proven"] is True
    assert result["final_end_state_trigger_proven"] is False
