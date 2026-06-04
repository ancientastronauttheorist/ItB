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


def test_watchdog_uses_nested_pause_guard_poll():
    watchdog = conductor.TimerWatchdog()

    state = watchdog.observe(
        "pause_guard",
        {
            "status": "OK",
            "reason": "pause_clicked",
            "last_poll": {
                "status": "OK",
                "reason": "pause_clicked",
                "pause_verified": True,
                "visible_ui": {
                    "status": "OK",
                    "visible_ui": "reward_panel",
                    "screenshot_path": "reward.png",
                    "scores": {
                        "reward_panel": {"score": 0.9, "crop": [1, 2, 3, 4]},
                    },
                },
                "pause_verify": {
                    "status": "OK",
                    "visible_ui": "pause_menu",
                    "screenshot_path": "pause.png",
                },
                "live_snapshot": {
                    "status": "OK",
                    "phase": "unknown",
                    "turn": 0,
                    "deployment_zone_count": 0,
                },
                "decision": {
                    "status": "OK",
                    "reason": "safe_ui_pause_available",
                    "pause_allowed": True,
                },
                "guard": {"path": "guard.json"},
            },
        },
    )

    assert state.safe_to_think is True
    assert state.pause_verified is True
    assert state.visible_ui == "pause_menu"
    assert state.screenshot_path == "pause.png"
    assert state.guard_path == "guard.json"
    assert state.live_phase == "unknown"
    assert state.evidence["ui_scores"]["reward_panel"]["crop"] == [1, 2, 3, 4]


def test_watchdog_does_not_trust_plain_pause_clicked():
    watchdog = conductor.TimerWatchdog()

    state = watchdog.observe(
        "pause_guard",
        {"status": "OK", "reason": "pause_clicked"},
    )

    assert state.safe_to_think is False
    assert state.pause_verified is False
    assert state.timer_stop_verified is False
    assert state.status == "AMBIGUOUS"


def test_safe_timer_uses_nested_timer_probe():
    result = {
        "status": "OK",
        "last_poll": {
            "status": "OK",
            "stop_probe": {
                "status": "OK",
                "running": False,
                "second_timer": {
                    "source": "profile_current_time",
                    "game_seconds": 12.5,
                    "game_timer": "0:00:12",
                },
            },
        },
    }

    assert conductor.safe_timer(result) == (12.5, "0:00:12")


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


def test_conductor_starts_from_verified_setup_without_codex_gap(monkeypatch):
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
        if args == ["achievements", "--sync"]:
            return result(args, {"status": "OK", "unlocked_list": []})
        if args == ["verify_setup", "--difficulty", "0"]:
            return result(args, {"status": "PASS"})
        if args == ["lightning_ui", "setup_start"]:
            return result(args, {"status": "OK"})
        if args and args[0] == "lightning_segment":
            return result(
                args,
                {
                    "status": "LIGHTNING_SEGMENT_STOPPED",
                    "reason": "route_ready",
                    "pause_guard": {
                        "status": "OK",
                        "reason": "already_paused",
                        "visible_ui": {"status": "OK", "visible_ui": "pause_menu"},
                    },
                },
            )
        if args == ["lightning_ui", "ensure_pause"]:
            return result(args, {"status": "OK", "reason": "already_paused"})
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(conductor, "run_game_loop", fake_run_game_loop)

    args = conductor.build_parser().parse_args(
        [
            "--start-from-verified-setup",
            "--max-segments",
            "1",
            "--settle-seconds",
            "0",
            "--no-journal",
        ]
    )

    assert conductor.run_conductor(args) == 8
    assert calls[:3] == [
        ["achievements", "--sync"],
        ["verify_setup", "--difficulty", "0"],
        ["lightning_ui", "setup_start"],
    ]
    assert calls[3][0] == "lightning_segment"
    assert "--no-preflight" in calls[3]
    assert ["lightning_preflight"] not in calls
    assert calls.count(["achievements", "--sync"]) == 1


def test_conductor_continues_after_combat_loop_returned(monkeypatch):
    calls = []
    segment_calls = 0
    achievement_calls = 0

    def result(args, payload, returncode=0):
        return conductor.CommandResult(
            args=args,
            returncode=returncode,
            stdout="",
            stderr="",
            result=payload,
        )

    def safe_pause_payload(reason="already_paused"):
        return {
            "status": "OK",
            "reason": reason,
            "pause_guard": {
                "status": "OK",
                "reason": "already_paused",
                "visible_ui": {"status": "OK", "visible_ui": "pause_menu"},
            },
            "game_budget": {"game_seconds": 12, "game_timer": "0:00:12"},
        }

    def fake_run_game_loop(args, *, timeout=None):
        nonlocal segment_calls, achievement_calls
        calls.append(list(args))
        if args[:2] == ["lightning_pause_guard", "--once"]:
            return result(args, safe_pause_payload())
        if args and args[0] == "lightning_preflight":
            return result(args, {"status": "PASS", "game_budget": {"game_seconds": 12}})
        if args and args[0] == "achievements":
            achievement_calls += 1
            unlocked = ["Lightning War"] if achievement_calls >= 3 else []
            return result(args, {"status": "OK", "unlocked_list": unlocked})
        if args and args[0] == "lightning_segment":
            segment_calls += 1
            reason = "combat_loop_returned" if segment_calls == 1 else "route_ready"
            return result(args, safe_pause_payload(reason=reason))
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(conductor, "run_game_loop", fake_run_game_loop)

    args = conductor.build_parser().parse_args(
        [
            "--max-segments",
            "2",
            "--settle-seconds",
            "0",
            "--no-journal",
        ]
    )

    assert conductor.run_conductor(args) == 0
    assert [call[0] for call in calls].count("lightning_segment") == 2
