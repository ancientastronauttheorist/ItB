from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lightning_war_conductor.py"
SPEC = importlib.util.spec_from_file_location("lightning_war_conductor", SCRIPT)
conductor = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = conductor
SPEC.loader.exec_module(conductor)


def test_extract_result_json_after_marker():
    output = """
noise
--- Result ---
{"status": "PASS", "game_budget": {"game_seconds": 12, "game_timer": "0:00:12"}}
"""

    assert conductor.extract_result_json(output) == {
        "status": "PASS",
        "game_budget": {"game_seconds": 12, "game_timer": "0:00:12"},
    }


def test_normalize_game_loop_command_uses_current_interpreter():
    assert conductor.normalize_game_loop_command(
        "python3 game_loop.py lightning_segment --route-visual-region-index 2"
    ) == ["lightning_segment", "--route-visual-region-index", "2"]


def test_route_command_from_primary_next_command():
    result = {
        "primary_next_command": (
            "python3 game_loop.py lightning_segment "
            "--route-visual-region-index 1 --route-start-mode preview-board"
        )
    }

    assert conductor.route_command_from_segment(result) == [
        "lightning_segment",
        "--route-visual-region-index",
        "1",
        "--route-start-mode",
        "preview-board",
    ]


def test_route_command_from_candidate_list():
    result = {
        "route_start_candidates": [
            {
                "command": (
                    "python3 game_loop.py lightning_segment "
                    "--route-visual-region-index 3"
                )
            }
        ]
    }

    assert conductor.route_command_from_segment(result) == [
        "lightning_segment",
        "--route-visual-region-index",
        "3",
    ]


def test_achievement_unlocked_detects_lightning_war():
    assert conductor.achievement_unlocked({"unlocked_list": ["Lightning War"]})
    assert not conductor.achievement_unlocked({"unlocked_list": ["Chain Attack"]})
