from __future__ import annotations

import copy
import json

import pytest

from scripts.itb_observatory_rng_trial import main as rng_trial_cli
from src.observatory.rng_trial_outcome import (
    RngTrialOutcomeError,
    compare_rng_trial_outcomes,
)


def _state(timestamp: int = 100) -> dict:
    return {
        "timestamp": timestamp,
        "mission_id": "Mission_Test",
        "phase": "combat_player",
        "turn": 2,
        "grid_power": 4,
        "units": [{"id": 1, "hp": 2}],
        "tiles": [{"x": 0, "y": 0, "terrain": 0}],
        "spawning_tiles": [[6, 2]],
        "targeted_tiles": [],
    }


def test_outcome_comparison_ignores_only_timestamp():
    comparison = compare_rng_trial_outcomes(
        _state(100),
        _state(999),
        capture_id="rng-pair-001",
    )
    assert comparison["status"] == "matched"
    assert comparison["difference_count"] == 0
    assert comparison["ignored_top_level_fields"] == ["timestamp"]
    assert (
        comparison["control_semantic_sha256"]
        == comparison["exact_hook_semantic_sha256"]
    )
    assert comparison["control_state_sha256"] != comparison["exact_hook_state_sha256"]


def test_outcome_comparison_reports_spawn_drift_exactly():
    exact = copy.deepcopy(_state())
    exact["spawning_tiles"][0][0] = 5
    comparison = compare_rng_trial_outcomes(
        _state(),
        exact,
        capture_id="rng-pair-004",
    )
    assert comparison["status"] == "mismatched"
    assert comparison["difference_count"] == 1
    assert comparison["differences"] == [
        {
            "path": "/spawning_tiles/0/0",
            "kind": "value",
            "control": 6,
            "exact_hook": 5,
        }
    ]


def test_outcome_difference_cap_distinguishes_exact_limit_from_overflow():
    control = _state()
    exact = _state()
    control["diagnostic"] = list(range(128))
    exact["diagnostic"] = [value + 1 for value in range(128)]
    at_limit = compare_rng_trial_outcomes(
        control,
        exact,
        capture_id="rng-pair-limit",
    )
    assert at_limit["difference_count"] == 128
    assert at_limit["differences_truncated"] is False

    control["diagnostic"].append(128)
    exact["diagnostic"].append(129)
    overflow = compare_rng_trial_outcomes(
        control,
        exact,
        capture_id="rng-pair-overflow",
    )
    assert overflow["difference_count"] == 128
    assert overflow["differences_truncated"] is True


def test_outcome_comparison_rejects_missing_required_identity():
    invalid = _state()
    del invalid["mission_id"]
    with pytest.raises(RngTrialOutcomeError, match="mission_id"):
        compare_rng_trial_outcomes(invalid, _state(), capture_id="rng-pair-001")


def test_outcome_cli_publishes_mismatch_before_returning_nonzero(tmp_path, capsys):
    control_path = tmp_path / "control.json"
    exact_path = tmp_path / "exact.json"
    output_path = tmp_path / "comparison.json"
    exact = copy.deepcopy(_state())
    exact["spawning_tiles"] = [[5, 2]]
    control_path.write_text(json.dumps(_state()), encoding="utf-8")
    exact_path.write_text(json.dumps(exact), encoding="utf-8")
    assert rng_trial_cli(
        [
            "compare-outcomes",
            "--control",
            str(control_path),
            "--exact-hook",
            str(exact_path),
            "--capture-id",
            "rng-pair-004",
            "--output",
            str(output_path),
        ]
    ) == 3
    assert json.loads(output_path.read_text(encoding="utf-8"))["status"] == (
        "mismatched"
    )
    assert "status=mismatched" in capsys.readouterr().out
