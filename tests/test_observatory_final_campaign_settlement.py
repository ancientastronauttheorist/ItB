from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.observatory.final_campaign_settlement import (
    ANALYSIS_KIND,
    EXPECTED_EXECUTABLE_SHA256,
    FinalCampaignSettlementError,
    validate_final_campaign_settlement_map,
    validate_final_campaign_settlement_map_binding,
)


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_MAP = (
    ROOT
    / "data"
    / "observatory"
    / "native"
    / "windows_build_13725832_31fe35265598_final_campaign_settlement.json"
)
GAME_ROOT = Path(r"B:\SteamLibrary\steamapps\common\Into the Breach")


def _load() -> dict:
    return json.loads(CAMPAIGN_MAP.read_text(encoding="utf-8"))


def test_committed_map_closes_post_travel_campaign_settlement_boundary():
    value = _load()
    result = validate_final_campaign_settlement_map_binding(value)

    assert result == {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "status": "bound",
        "artifact_sha256": (
            "cb3d8105929e0a428a66277609193023"
            "60ee7a0eb181dbb2e3b04531138a81a7"
        ),
        "post_travel_campaign_victory_proven": True,
        "run_save_teardown_proven": True,
        "profile_result_write_path_proven": True,
        "final_victory_presentation_proven": True,
        "simulator_change_required": False,
    }
    assert value["identity"]["executable_sha256"] == (
        EXPECTED_EXECUTABLE_SHA256
    )
    assert value["summary"] == {
        "lua_source_count": 1,
        "region_count": 24,
        "string_anchor_count": 12,
        "data_pointer_count": 2,
        "control_window_count": 16,
        "direct_edge_count": 20,
        "finding_count": 10,
        "unresolved_count": 3,
        "post_travel_campaign_victory_proven": True,
        "run_save_teardown_proven": True,
        "profile_result_write_path_proven": True,
        "final_victory_presentation_proven": True,
        "simulator_change_required": False,
    }
    assert value["supersedes"]["resolved_gap_ids"] == [
        "post_travel_campaign_victory"
    ]

    contracts = value["contracts"]
    assert contracts["travel_settlement"]["final_script_order"] == [
        "Board:LockBomb()",
        "Board:Fade(FADE_EXPLODE)",
    ]
    assert contracts["campaign_terminal_result"]["result_mapping"] == {
        "outcome_code_3": 2,
        "every_other_outcome_code": 1,
    }
    assert contracts["campaign_terminal_result"]["consumer_semantics"] == {
        "result_1": "campaign win",
        "result_2": "campaign non-win/loss",
    }
    assert contracts["campaign_settlement"]["run_save_files_removed"] == [
        "saveData.lua",
        "saveData.lua.old",
        "saveData.lua.backup",
    ]
    assert contracts["profile_result"]["writer_precondition"] == (
        "profile serializer flag +0x54 is nonzero"
    )
    assert contracts["final_victory_presentation"][
        "gateway_result_required"
    ] == 1

    findings = {item["id"]: item for item in value["findings"]}
    assert "4.5 seconds" in findings[
        "start_mech_travel_initializes_native_queue"
    ]["claim"]
    assert "common completed-battle state" in findings[
        "final_campaign_bypasses_ordinary_cleanup"
    ]["claim"]
    assert "DeleteFileA" in findings[
        "completed_run_saves_are_removed"
    ]["claim"]
    assert "CREATE_ALWAYS" in findings[
        "profile_write_path_is_pinned"
    ]["claim"]
    assert "Campaign result 1 alone" in findings[
        "final_victory_renderer_handoff"
    ]["claim"]
    assert "No Rust combat-simulator semantic change" in findings[
        "solver_boundary"
    ]["claim"]

    unresolved = {item["id"] for item in value["unresolved"]}
    assert unresolved == {
        "runtime_campaign_settlement_timing",
        "profile_gateway_value_0x128",
        "non_windows_equivalence",
    }


def test_binding_rejects_pointer_source_or_prose_drift():
    value = _load()

    altered = copy.deepcopy(value)
    altered["data_pointers"][0]["target_rva"] = "0x00000000"
    with pytest.raises(FinalCampaignSettlementError, match="fields differ"):
        validate_final_campaign_settlement_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["sources"]["lua_files"][0]["sha256"] = "0" * 64
    with pytest.raises(FinalCampaignSettlementError, match="fields differ"):
        validate_final_campaign_settlement_map_binding(altered)

    altered = copy.deepcopy(value)
    altered["findings"][0]["claim"] += " overclaim"
    with pytest.raises(FinalCampaignSettlementError, match="fields differ"):
        validate_final_campaign_settlement_map_binding(altered)


def test_exact_local_executable_and_source_reproduce_map_when_available():
    executable = GAME_ROOT / "Breach.exe"
    if not executable.is_file():
        pytest.skip("exact local ITB executable is not available")
    result = validate_final_campaign_settlement_map(
        executable,
        GAME_ROOT,
        _load(),
    )
    assert result["status"] == "verified"
    assert result["post_travel_campaign_victory_proven"] is True
    assert result["run_save_teardown_proven"] is True
    assert result["profile_result_write_path_proven"] is True
    assert result["final_victory_presentation_proven"] is True
