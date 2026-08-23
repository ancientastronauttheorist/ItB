from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.final_cave_outcome import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    FinalCaveOutcomeError,
    validate_final_cave_outcome_map,
    validate_final_cave_outcome_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
OUTCOME_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_final_cave_outcome.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(OUTCOME_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_final_cave_countdown_outcome_boundary():
    value = _load()
    result = validate_final_cave_outcome_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "15e8c54660936296b3e5a4b76dbfa2f1"
            "70aabc13157932c39daec8ae0ba7c529"
        ),
        "cave_countdown_outcome_proven": True,
        "bomb_is_direct_terminal_loss": False,
        "forced_zero_mech_failure_proven": True,
        "campaign_result_join_proven": True,
        "simulator_change_required": False,
    }
    assert value["identity"]["executable_sha256"] == (
        EXPECTED_EXECUTABLE_SHA256
    )
    assert value["summary"] == {
        "lua_source_count": 1,
        "region_count": 10,
        "string_anchor_count": 8,
        "data_pointer_count": 4,
        "control_window_count": 18,
        "direct_edge_count": 8,
        "finding_count": 7,
        "unresolved_count": 3,
        "cave_countdown_outcome_proven": True,
        "bomb_is_direct_terminal_loss": False,
        "forced_zero_mech_failure_proven": True,
        "campaign_result_join_proven": True,
        "simulator_change_required": False,
    }
    assert value["supersedes"]["resolved_gap_ids"] == [
        "cave_countdown_outcome"
    ]

    dependencies = {
        item["artifact"]: item["artifact_sha256"]
        for item in value["dependencies"]
    }
    assert dependencies == {
        (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_final_end_settlement.json"
        ): (
            "541237f7e723c1ec56b0328cb1f137f2"
            "a6725bda55c588d0a7ebc74adc55be0c"
        ),
        (
            "data/observatory/native/"
            "windows_build_13725832_31fe35265598_final_campaign_settlement.json"
        ): (
            "cb3d8105929e0a428a66277609193023"
            "60ee7a0eb181dbb2e3b04531138a81a7"
        ),
    }

    contracts = value["contracts"]
    assert contracts["outcome_codes"] == {
        "storage_offset": "0x1900",
        "secondary_offset": "0x1904",
        "pending": 2,
        "victory": 1,
        "failure": 3,
        "initial_primary": 2,
        "initial_secondary": 2,
    }
    countdown = contracts["ordinary_final_cave_countdown"]
    assert countdown["transition_state"] == 2
    assert countdown["forced_evaluation"] is False
    assert countdown["result"] == "primary outcome code 1"
    assert countdown["is_end_blocked_invoked_on_ready_branch"] is False
    assert countdown["bomb_or_objective_query_between_ready_and_write"] is False

    failure = contracts["forced_no_mech_failure"]
    assert failure["transition_state"] == 0
    assert failure["query"] == "Board:GetPawnCount(TEAM_MECH)"
    assert failure["team_constant"] == 4
    assert failure["zero_result"] == "primary outcome code 3"

    findings = {item["id"]: item for item in value["findings"]}
    assert "writes code 1" in findings[
        "final_cave_limit_writes_victory"
    ]["claim"]
    assert "no bomb, objective, or IsEndBlocked query" in findings[
        "countdown_does_not_recheck_bomb_or_objectives"
    ]["claim"]
    assert "delay/replacement boundary" in findings[
        "missing_bomb_delays_instead_of_directly_losing"
    ]["claim"]
    assert "TEAM_MECH value 4" in findings[
        "forced_zero_mech_failure_is_separate"
    ]["claim"]
    assert "No Rust simulator semantic change" in findings[
        "solver_boundary"
    ]["claim"]

    unresolved = {item["id"] for item in value["unresolved"]}
    assert unresolved == {
        "replacement_materialization",
        "modified_outcome_paths",
        "non_windows_equivalence",
    }


def test_binding_rejects_pointer_source_or_prose_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["data_pointers"][0]["target_rva"] = "0x00000000"
    with pytest.raises(FinalCaveOutcomeError, match="fields differ"):
        validate_final_cave_outcome_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["sources"]["lua_files"][0]["sha256"] = "0" * 64
    with pytest.raises(FinalCaveOutcomeError, match="fields differ"):
        validate_final_cave_outcome_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["findings"][0]["claim"] += " overclaim"
    with pytest.raises(FinalCaveOutcomeError, match="fields differ"):
        validate_final_cave_outcome_map_binding(altered)


def test_exact_local_executable_and_source_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_final_cave_outcome_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["cave_countdown_outcome_proven"] is True
    assert result["bomb_is_direct_terminal_loss"] is False
    assert result["forced_zero_mech_failure_proven"] is True
    assert result["campaign_result_join_proven"] is True
