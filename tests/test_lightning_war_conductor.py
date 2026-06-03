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


def test_watchdog_marks_verified_pause_safe():
    watchdog = conductor.TimerWatchdog()

    state = watchdog.observe(
        "segment",
        {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "pause_guard": {
                "status": "OK",
                "reason": "pause_clicked",
                "pause_verified": True,
                "pause_verify": {"status": "OK", "visible_ui": "pause_menu"},
            },
            "game_budget": {"game_seconds": 42, "game_timer": "0:00:42"},
        },
    )

    assert state.safe_to_think is True
    assert state.must_act_now is False
    assert state.visible_ui == "pause_menu"


def test_watchdog_marks_deployment_must_act():
    watchdog = conductor.TimerWatchdog()

    state = watchdog.observe(
        "guard",
        {
            "status": "BLOCKED",
            "reason": "visible_ui_is_not_pauseable",
            "visible_ui": {
                "status": "OK",
                "visible_ui": "deployment_screen",
                "non_pauseable": True,
            },
        },
    )

    assert state.safe_to_think is False
    assert state.must_act_now is True
    assert state.visible_ui == "deployment_screen"


def test_conductor_skips_initial_sync_when_guard_says_must_act(monkeypatch):
    calls = []

    def result(args, payload, returncode=0):
        return conductor.CommandResult(
            args=args,
            returncode=returncode,
            stdout="",
            stderr="",
            result=payload,
        )

    def fake_run_game_loop(args, *, timeout=None):
        calls.append(list(args))
        if args[:2] == ["lightning_pause_guard", "--once"]:
            return result(
                args,
                {
                    "status": "BLOCKED",
                    "reason": "visible_ui_is_not_pauseable",
                    "visible_ui": {
                        "status": "OK",
                        "visible_ui": "deployment_screen",
                        "non_pauseable": True,
                    },
                },
            )
        if args and args[0] == "lightning_segment":
            return result(
                args,
                {
                    "status": "LIGHTNING_SEGMENT_STOPPED",
                    "reason": "route_ready",
                    "pause_guard": {
                        "status": "OK",
                        "reason": "pause_clicked",
                        "pause_verified": True,
                        "pause_verify": {"status": "OK", "visible_ui": "pause_menu"},
                    },
                    "game_budget": {
                        "game_seconds": 12,
                        "game_timer": "0:00:12",
                    },
                },
            )
        if args and args[0] == "achievements":
            return result(
                args,
                {"status": "OK", "unlocked_list": ["Lightning War"]},
            )
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(conductor, "run_game_loop", fake_run_game_loop)

    args = conductor.build_parser().parse_args(
        [
            "--max-segments",
            "1",
            "--settle-seconds",
            "0",
            "--no-journal",
        ]
    )

    assert conductor.run_conductor(args) == 0
    assert calls[0] == ["lightning_pause_guard", "--once"]
    assert calls[1][0] == "lightning_segment"
    assert "--no-preflight" in calls[1]
    assert calls[2] == ["achievements", "--sync"]
