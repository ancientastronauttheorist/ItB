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
