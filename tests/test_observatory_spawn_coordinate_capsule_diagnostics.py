from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = (
    ROOT
    / "data"
    / "observatory"
    / "captures"
    / "windows_build_13725832_owner_local_modified_20260829_"
    "spawn_coordinate_capsule_diagnostics"
)


def _load(name: str) -> dict:
    return json.loads((DIAGNOSTICS / name).read_text(encoding="utf-8"))


def test_missing_support_module_attempt_is_rejected_before_trial_and_restored():
    condition = _load("missing_support_modules_01_condition_lifecycle.json")
    campaign = _load("missing_support_modules_01_campaign_lifecycle.json")

    assert condition["status"] == "rejected"
    assert condition["valid_lifecycle"] is False
    assert condition["bridge_start"] is None
    assert condition["trial"] is None
    assert condition["errors"]["bridge_start"] == (
        "native Continue startup ACK differs: 'ERROR: Observatory native Continue "
        "cannot load callback game-flow helper: The specified module could not be "
        "found.'"
    )
    assert condition["close"]["method"] == "WM_CLOSE"
    assert condition["close"]["exited"] is True
    assert condition["close"]["forced_termination"] is False

    assert campaign["status"] == "rejected"
    assert campaign["condition_order"] == []
    assert campaign["errors"]["final_restore"] == ""
    assert campaign["final_restore"]["game_stopped"] is True
    assert campaign["final_restore"]["manifest"]["tree_sha256"] == (
        "4606b1c2668cde873e0d325ca1a77ed6215270815f65bea983d529e7a150af45"
    )


def test_tasklist_timeout_attempt_fails_closed_and_final_restores():
    condition = _load("tasklist_timeout_02_condition_lifecycle.json")
    campaign = _load("tasklist_timeout_02_campaign_lifecycle.json")

    timeout = (
        "cannot enumerate Breach.exe: Command '['tasklist', '/FI', "
        "'IMAGENAME eq Breach.exe', '/FO', 'CSV', '/NH']' timed out after 5 seconds"
    )
    assert condition["status"] == "rejected"
    assert condition["valid_lifecycle"] is False
    assert condition["native_continue"]["ack"] == (
        "OK OBS_NATIVE_CONTINUE_REQUEST invoked=true"
    )
    assert condition["bridge_start"] is None
    assert condition["trial"] is None
    assert condition["errors"]["bridge_start"] == timeout
    assert condition["errors"]["close"] == timeout
    assert condition["close"] is None

    assert campaign["status"] == "rejected"
    assert campaign["condition_order"] == []
    assert campaign["errors"]["final_restore"] == ""
    assert campaign["final_restore"]["game_stopped"] is True
    assert campaign["final_restore"]["manifest"]["tree_sha256"] == (
        "4606b1c2668cde873e0d325ca1a77ed6215270815f65bea983d529e7a150af45"
    )


def test_missing_raw_active_mechs_attempt_fails_closed_and_final_restores():
    condition = _load("missing_raw_active_mechs_03_condition_lifecycle.json")
    campaign = _load("missing_raw_active_mechs_03_campaign_lifecycle.json")

    assert condition["status"] == "rejected"
    assert condition["valid_lifecycle"] is False
    assert condition["native_continue"]["ack"] == (
        "OK OBS_NATIVE_CONTINUE_REQUEST invoked=true"
    )
    assert condition["bridge_start"] is None
    assert condition["trial"] is None
    assert condition["errors"]["bridge_start"] == (
        "native Continue did not reach a ready Mission_Power player turn; "
        "last phase='combat_player'"
    )
    assert condition["close"]["method"] == "WM_CLOSE"
    assert condition["close"]["exited"] is True
    assert condition["close"]["forced_termination"] is False

    assert campaign["status"] == "rejected"
    assert campaign["condition_order"] == []
    assert campaign["errors"]["final_restore"] == ""
    assert campaign["final_restore"]["game_stopped"] is True
    assert campaign["final_restore"]["manifest"]["tree_sha256"] == (
        "4606b1c2668cde873e0d325ca1a77ed6215270815f65bea983d529e7a150af45"
    )


def test_imported_trial_stdio_attempt_aborts_and_final_restores():
    condition = _load("imported_trial_stdio_04_condition_lifecycle.json")
    campaign = _load("imported_trial_stdio_04_campaign_lifecycle.json")
    trial = _load("imported_trial_stdio_04_trial.json")

    assert condition["status"] == "rejected"
    assert condition["valid_lifecycle"] is False
    assert condition["bridge_start"] == {
        "active_mechs": 3,
        "ai_seed_fingerprint": None,
        "master_seed": 664577925,
        "mission_id": "Mission_Power",
        "phase": "combat_player",
        "region_id": None,
        "timeline_fingerprint": None,
        "turn": 1,
    }
    assert condition["errors"]["trial"] == "capsule trial was rejected"
    assert condition["close"]["method"] == "WM_CLOSE"
    assert condition["close"]["exited"] is True
    assert condition["close"]["forced_termination"] is False

    assert trial["status"] == "rejected"
    assert trial["valid_trial"] is False
    assert trial["auto_turn"] == {"status": "invalid_result"}
    assert trial["boundary"]["state"] == "aborted"
    assert trial["errors"]["reservation"] == (
        "'charmap' codec can't encode character '\\u2192' in position 31: "
        "character maps to <undefined>"
    )
    assert trial["dispatch"] is None
    assert trial["snapshot"] is None
    assert trial["snapshot_consumed_from_bridge"] is True
    assert trial["pause_guard"]["pause_verified"] is True

    assert campaign["status"] == "rejected"
    assert campaign["condition_order"] == []
    assert campaign["errors"]["final_restore"] == ""
    assert campaign["final_restore"]["game_stopped"] is True
    assert campaign["final_restore"]["manifest"]["tree_sha256"] == (
        "4606b1c2668cde873e0d325ca1a77ed6215270815f65bea983d529e7a150af45"
    )
