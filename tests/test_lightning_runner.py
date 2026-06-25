from __future__ import annotations

from types import SimpleNamespace

import pytest

import game_loop
from src.loop import commands as loop_commands
from src.loop import lightning_runner
from src.loop.lightning_runner import LightningRunnerConfig, LightningWarRunner


class FakeTelemetry:
    def __init__(self) -> None:
        self.run_id = "lw_runner_test"
        self.run_dir = "recordings/lw_runner_test"
        self.telemetry_dir = "recordings/lw_runner_test/telemetry"
        self.events: list[tuple[str, dict]] = []
        self.manifests: list[dict] = []

    def event(self, name: str, **payload):
        self.events.append((name, payload))

    def write_manifest(self, payload):
        self.manifests.append(payload)

    def summary(self, **payload):
        self.events.append(("summary", payload))


def make_runner(**kwargs) -> LightningWarRunner:
    config_kwargs = {
        "screenshots": False,
        "achievement_sync": False,
        "max_segments": 4,
    }
    config_kwargs.update(kwargs)
    runner = LightningWarRunner(
        LightningRunnerConfig(**config_kwargs)
    )
    runner.telemetry = FakeTelemetry()
    return runner


def unexpected(name):
    def _fail(*args, **kwargs):
        raise AssertionError(f"{name} should not be called")

    return _fail


def test_default_attempt_budget_allows_rng_route_rerolls():
    assert lightning_runner.DEFAULT_LIGHTNING_MAX_ATTEMPTS == 20
    assert LightningRunnerConfig().max_attempts == 20
    assert lightning_runner.DEFAULT_LIGHTNING_MAX_SEGMENTS == 40
    assert LightningRunnerConfig().max_segments == 40


def test_game_loop_lightning_autonomous_uses_runner_entrypoint():
    assert game_loop.cmd_lightning_autonomous is lightning_runner.cmd_lightning_autonomous
    assert game_loop.AutonomousLightningConfig is lightning_runner.LightningRunnerConfig
    assert game_loop.DEFAULT_LIGHTNING_MAX_ATTEMPTS == (
        lightning_runner.DEFAULT_LIGHTNING_MAX_ATTEMPTS
    )
    assert game_loop.DEFAULT_LIGHTNING_MAX_SEGMENTS == (
        lightning_runner.DEFAULT_LIGHTNING_MAX_SEGMENTS
    )


def test_route_probe_offset_advances_with_attempt_and_progress():
    session = SimpleNamespace(
        mission_index=2,
        islands_completed=["archive"],
    )

    assert lightning_runner._route_probe_offset(session, 3) == 5
    assert (
        lightning_runner._route_probe_offset_for_segment(
            session,
            3,
            speed_mode=True,
        )
        == 3
    )


def test_stop_token_evidence_ignores_diagnostic_stale_bridge_preview():
    segment = {
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "route_auto_start_not_allowed",
        "steps": [
            {
                "status": "LIGHTNING_ATTEMPT_ROUTE_READY",
                "reason": "paused_visible_island_map_save_route_plan",
                "route_auto_start_blocked_candidate": {
                    "auto_route_allowed": False,
                    "auto_route_block_reason": (
                        "multi_region_live_preview_probe_without_route_identity"
                    ),
                },
                "route_fallback": {
                    "ignored_bridge_preview": {
                        "reason": "stale_bridge_preview_ignored_for_route_scoring",
                        "bridge_heartbeat_stale": True,
                    },
                    "ignored_bridge_preview_diagnostic_only": True,
                },
            }
        ],
    }

    evidence = lightning_runner._stop_token_evidence(
        segment,
        lightning_runner.BASELINE_STOP_TOKENS,
    )

    assert evidence["token"] == "ROUTE_AUTO_START_NOT_ALLOWED"
    assert evidence["reason"] == "route_auto_start_not_allowed"


def test_first_island_for_attempt_rotates_after_preferred_island():
    assert lightning_runner._first_island_for_attempt("archive", 1) == "archive"
    assert lightning_runner._first_island_for_attempt("archive", 2) == "rst"
    assert lightning_runner._first_island_for_attempt("archive", 3) == "pinnacle"
    assert lightning_runner._first_island_for_attempt("archive", 4) == "detritus"
    assert lightning_runner._first_island_for_attempt("archive", 5) == "archive"
    assert lightning_runner._first_island_for_attempt("rst", 1) == "rst"
    assert lightning_runner._first_island_for_attempt("r.s.t.", 2) == "archive"


def test_first_island_for_attempt_speed_mode_cycles_archive_rst():
    assert lightning_runner._first_island_for_attempt(
        "archive",
        1,
        speed_mode=True,
    ) == "archive"
    assert lightning_runner._first_island_for_attempt(
        "archive",
        2,
        speed_mode=True,
    ) == "rst"
    assert lightning_runner._first_island_for_attempt(
        "archive",
        3,
        speed_mode=True,
    ) == "archive"
    assert lightning_runner._first_island_for_attempt(
        "rst",
        2,
        speed_mode=True,
    ) == "archive"
    assert lightning_runner._first_island_for_attempt(
        "pinnacle",
        2,
        speed_mode=True,
    ) == "archive"


def test_game_loop_lightning_autonomous_cli_forwards_safe_defaults(monkeypatch):
    calls: list[dict] = []

    monkeypatch.setattr(
        game_loop,
        "cmd_lightning_autonomous",
        lambda **kwargs: calls.append(kwargs) or {"status": "OK"},
    )
    monkeypatch.setattr(
        game_loop.sys,
        "argv",
        ["game_loop.py", "lightning_autonomous"],
    )

    game_loop.main()

    assert calls == [
        {
            "profile": "Alpha",
            "achievement": "Lightning War",
            "mode": "baseline",
            "target_islands": 2,
            "advanced_content": "off",
            "difficulty": 0,
            "first_island": "archive",
            "max_attempts": lightning_runner.DEFAULT_LIGHTNING_MAX_ATTEMPTS,
            "max_segments": lightning_runner.DEFAULT_LIGHTNING_MAX_SEGMENTS,
            "segment_steps": 12,
            "time_limit": None,
            "max_wall_seconds": None,
            "segment_timeout": 420.0,
            "abandon_seconds": 29 * 60,
            "mission_segment_gate_seconds": 3 * 60,
            "first_mission_route_start_gate_seconds": 30,
            "first_island_gate_seconds": 15 * 60,
            "second_island_start_gate_seconds": 16.75 * 60,
            "screenshot_cadence": 2.0,
            "collect_screenshot_cadence": 2.0,
            "race_screenshot_cadence": 5.0,
            "iteration_mode": "flipflop",
            "screenshots": True,
            "route_auto_start": True,
            "route_start_mode": "visible-text",
            "route_speed_vetoes": None,
            "allow_objective_loss": False,
            "lightning_speed_loss_policy": False,
            "pause_before_solve": True,
            "pause_between_actions": False,
            "start_from_verified_setup": False,
            "achievement_sync": True,
            "dry_run": False,
        }
    ]


def test_game_loop_lightning_autonomous_cli_forwards_speed_overrides(monkeypatch):
    calls: list[dict] = []

    monkeypatch.setattr(
        game_loop,
        "cmd_lightning_autonomous",
        lambda **kwargs: calls.append(kwargs) or {"status": "OK"},
    )
    monkeypatch.setattr(
        game_loop.sys,
        "argv",
        [
            "game_loop.py",
            "lightning_autonomous",
            "--mode",
            "speed",
            "--target-islands",
            "3",
            "--advanced-content",
            "any",
            "--difficulty",
            "1",
            "--first-island",
            "rst",
            "--max-attempts",
            "5",
            "--max-segments",
            "9",
            "--segment-steps",
            "4",
            "--time-limit",
            "3.5",
            "--max-wall-seconds",
            "1800",
            "--segment-timeout",
            "120",
            "--abandon-seconds",
            "1500",
            "--first-mission-route-start-gate-seconds",
            "120",
            "--first-island-gate-seconds",
            "700",
            "--second-island-start-gate-seconds",
            "900",
            "--screenshot-cadence",
            "0.5",
            "--no-screenshots",
            "--no-route-auto-start",
            "--baseline-route-policy",
            "--start-from-verified-setup",
            "--no-achievement-sync",
            "--dry-run",
        ],
    )

    game_loop.main()

    assert calls == [
        {
            "profile": "Alpha",
            "achievement": "Lightning War",
            "mode": "speed",
            "target_islands": 3,
            "advanced_content": "any",
            "difficulty": 1,
            "first_island": "rst",
            "max_attempts": 5,
            "max_segments": 9,
            "segment_steps": 4,
            "time_limit": 3.5,
            "max_wall_seconds": 1800.0,
            "segment_timeout": 120.0,
            "abandon_seconds": 1500.0,
            "mission_segment_gate_seconds": 180,
            "first_mission_route_start_gate_seconds": 120,
            "first_island_gate_seconds": 700.0,
            "second_island_start_gate_seconds": 900.0,
            "screenshot_cadence": 0.5,
            "collect_screenshot_cadence": 2.0,
            "race_screenshot_cadence": 5.0,
            "iteration_mode": "flipflop",
            "screenshots": False,
            "route_auto_start": False,
            "route_start_mode": "visible-text",
            "route_speed_vetoes": False,
            "allow_objective_loss": False,
            "lightning_speed_loss_policy": False,
            "pause_before_solve": True,
            "pause_between_actions": False,
            "start_from_verified_setup": True,
            "achievement_sync": False,
            "dry_run": True,
        }
    ]


def test_game_loop_lightning_select_first_island_cli_forwards_options(monkeypatch):
    calls: list[dict] = []

    monkeypatch.setattr(
        game_loop,
        "cmd_lightning_select_first_island",
        lambda **kwargs: calls.append(kwargs) or {"status": "OK"},
    )
    monkeypatch.setattr(
        game_loop.sys,
        "argv",
        [
            "game_loop.py",
            "lightning_select_first_island",
            "--profile",
            "Beta",
            "--first-island",
            "rst",
            "--advanced-content",
            "any",
            "--dry-run",
        ],
    )

    game_loop.main()

    assert calls == [
        {
            "profile": "Beta",
            "first_island": "rst",
            "advanced_content": "any",
            "dry_run": True,
        }
    ]


@pytest.fixture(autouse=True)
def blitzkrieg_save_state(monkeypatch):
    def fake_load_game_state(_profile):
        return SimpleNamespace(
            difficulty=0,
            grid_power=7,
            grid_power_max=7,
            mechs=["ElectricMech", "WallMech", "RockartMech"],
            weapons=["Prime_Lightning", "Brute_Grapple", "Ranged_Rockthrow"],
        )

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)


def pause_menu() -> dict:
    return {
        "status": "OK",
        "visible_ui": {"status": "OK", "visible_ui": "pause_menu"},
        "pause_verified": True,
    }


def completion_peek(visible_ui: str = "island_map", **extra):
    def _peek(**kwargs):
        return {
            "status": "OK",
            "reason": "micro_peek_captured_and_paused",
            "include_ocr": kwargs.get("include_ocr"),
            "evidence_ui": {"status": "OK", "visible_ui": visible_ui, **extra},
            "pause_verify": {"status": "OK", "visible_ui": "pause_menu"},
        }

    return _peek


def preflight_pass() -> dict:
    return {"status": "PASS", "warnings": [], "issues": []}


def preflight_with_timer(seconds: float) -> dict:
    return {
        "status": "PASS",
        "warnings": [],
        "issues": [],
        "game_budget": {
            "game_seconds": seconds,
            "game_timer": f"0:{int(seconds) // 60:02d}:{int(seconds) % 60:02d}",
        },
    }


def test_visibility_helpers_read_nested_guard_payloads():
    nested_guard = {
        "status": "BLOCKED",
        "reason": "external_system_prompt_visible",
        "guard": {
            "status": "BLOCKED",
            "visible_ui": {
                "status": "OK",
                "visible_ui": "system_privacy_prompt",
            },
        },
    }

    assert lightning_runner._visible_ui_name(nested_guard) == "system_privacy_prompt"
    assert lightning_runner._safe_to_think(
        {
            "status": "OK",
            "guard": {
                "status": "OK",
                "visible_ui": {"status": "OK", "visible_ui": "pause_menu"},
            },
        }
    )


def test_external_prompt_evidence_accepts_authorization_flags_and_prose():
    assert lightning_runner._external_system_prompt_evidence(
        {
            "requires_user_authorization": True,
            "external_prompt": {
                "matched": True,
                "kind": "macos_screen_audio_privacy_prompt",
                "regions": [{"x": 1, "y": 2}],
            },
        }
    ) == {
        "kind": "external_system_prompt",
        "path": "",
        "requires_user_authorization": True,
        "visible_ui": {
            "requires_user_authorization": True,
            "external_prompt": {
                "matched": True,
                "kind": "macos_screen_audio_privacy_prompt",
            },
        },
        "external_prompt": {
            "matched": True,
            "kind": "macos_screen_audio_privacy_prompt",
        },
    }
    assert lightning_runner._external_system_prompt_evidence(
        {"external_prompt": {"matched": True, "kind": "accessibility_prompt"}}
    ) == {
        "kind": "external_system_prompt",
        "path": "external_prompt",
        "external_prompt": {"matched": True, "kind": "accessibility_prompt"},
    }
    assert lightning_runner._external_system_prompt_evidence(
        {"message": "A macOS privacy prompt is covering Into the Breach"}
    ) == {
        "kind": "external_system_prompt",
        "path": "message",
        "text": "A macOS privacy prompt is covering Into the Breach",
    }


def test_terminal_outcome_evidence_handles_objective_failed_without_parentheses():
    evidence = lightning_runner._terminal_outcome_evidence(
        {
            "status": "OK",
            "visible_ui": "reward_panel",
            "objective_texts": [
                "Region Secured",
                "Protect the Train Failed",
            ],
        }
    )

    assert evidence == {
        "kind": "terminal_text",
        "path": "objective_texts.1",
        "phrase": "failed",
        "context": "objective_text",
        "text": "Protect the Train Failed",
    }


def test_terminal_outcome_evidence_handles_failed_mission_word_order():
    evidence = lightning_runner._terminal_outcome_evidence(
        {
            "status": "OK",
            "visible_ui": "reward_panel",
            "screen_text": "FAILED MISSION",
        }
    )

    assert evidence == {
        "kind": "terminal_text",
        "path": "screen_text",
        "phrase": "failed mission",
        "text": "FAILED MISSION",
    }


def test_terminal_outcome_evidence_handles_structured_failed_objective_rows():
    assert lightning_runner._terminal_outcome_evidence(
        {
            "status": "OK",
            "visible_ui": "reward_panel",
            "objectives": [
                {"text": "Protect the Train", "status": "failed"},
            ],
        }
    ) == {
        "kind": "objective_failure_field",
        "path": "objectives.0.status",
        "field": "status",
        "value": "failed",
    }
    assert lightning_runner._terminal_outcome_evidence(
        {
            "status": "OK",
            "visible_ui": "reward_panel",
            "bonus_objectives": [
                {"text": "Block Vek Spawning", "failed": True},
            ],
        }
    ) == {
        "kind": "objective_failure_field",
        "path": "bonus_objectives.0.failed",
        "field": "failed",
    }


def test_terminal_outcome_evidence_handles_string_terminal_flags():
    assert lightning_runner._terminal_outcome_evidence(
        {"terminal_outcome": "Killed in Action"}
    ) == {
        "kind": "terminal_flag",
        "path": "terminal_outcome",
        "flag": "terminal_outcome",
        "value": "Killed in Action",
        "phrase": "killed in action",
    }
    assert lightning_runner._terminal_outcome_evidence(
        {"terminal_outcome_visible": "failed_objective"}
    ) == {
        "kind": "terminal_flag",
        "path": "terminal_outcome_visible",
        "flag": "terminal_outcome_visible",
        "value": "failed_objective",
        "phrase": "failed objective",
    }
    assert lightning_runner._terminal_outcome_evidence({"kia_visible": "true"}) == {
        "kind": "terminal_flag",
        "path": "kia_visible",
        "flag": "kia_visible",
        "value": "true",
    }
    assert lightning_runner._terminal_outcome_evidence(
        {"failed_objective_visible": "yes"}
    ) == {
        "kind": "terminal_flag",
        "path": "failed_objective_visible",
        "flag": "failed_objective_visible",
        "value": "yes",
    }
    assert (
        lightning_runner._terminal_outcome_evidence({"terminal_outcome": "none"})
        is None
    )


def test_terminal_false_positive_does_not_suppress_explicit_terminal_text():
    assert (
        lightning_runner._terminal_outcome_evidence(
            {
                "visible_ui": "perfect_reward_choice",
                "terminal_panel_false_positive": True,
            }
        )
        is None
    )
    assert lightning_runner._terminal_outcome_evidence(
        {
            "visible_ui": "perfect_reward_choice",
            "terminal_panel_false_positive": True,
            "visible_text": "Region Secured\nKilled in Action",
        }
    ) == {
        "kind": "terminal_text",
        "path": "visible_text",
        "phrase": "killed in action",
        "text": "Region Secured\nKilled in Action",
    }
    assert lightning_runner._terminal_outcome_evidence(
        {
            "visible_ui": "perfect_reward_choice",
            "terminal_panel_false_positive": True,
            "objective_texts": ["Protect the Train", "FAILED"],
        }
    ) == {
        "kind": "split_objective_failure_text",
        "path": "objective_texts.1",
        "phrase": "failed",
        "context": "split_objective_text",
        "context_path": "objective_texts.0",
        "context_text": "Protect the Train",
        "text": "FAILED",
    }


def test_terminal_visible_ui_needs_unclean_text_audit():
    assert lightning_runner._terminal_visible_ui_evidence(
        {
            "status": "OK",
            "visible_ui": "kia_panel",
            "recommended_control": "kia_understood",
        }
    ) == {
        "kind": "terminal_visible_ui",
        "path": "visible_ui",
        "visible_ui": "kia_panel",
    }
    assert (
        lightning_runner._terminal_visible_ui_evidence(
            {
                "status": "OK",
                "visible_ui": "kia_panel",
                "recommended_control": "kia_understood",
                "ocr": {"status": "OK", "texts": ["Choose your first island"]},
                "ocr_texts": ["Choose your first island"],
            }
        )
        is None
    )


def test_terminal_outcome_evidence_handles_split_objective_failed_rows():
    evidence = lightning_runner._terminal_outcome_evidence(
        {
            "status": "OK",
            "visible_ui": "reward_panel",
            "objective_texts": [
                "Region Secured",
                "Protect the Train",
                "FAILED",
            ],
        }
    )

    assert evidence == {
        "kind": "split_objective_failure_text",
        "path": "objective_texts.2",
        "phrase": "failed",
        "context": "split_objective_text",
        "context_path": "objective_texts.1",
        "context_text": "Protect the Train",
        "text": "FAILED",
    }


def test_terminal_outcome_evidence_handles_split_ocr_failed_with_context():
    evidence = lightning_runner._terminal_outcome_evidence(
        {
            "status": "OK",
            "visible_ui": "reward_panel",
            "ocr_texts": [
                "Region Secured",
                "Defend the Tanks",
                "(Failed)",
            ],
        }
    )

    assert evidence == {
        "kind": "split_objective_failure_text",
        "path": "ocr_texts.2",
        "phrase": "failed",
        "context": "split_objective_text",
        "context_path": "ocr_texts.1",
        "context_text": "Defend the Tanks",
        "text": "(Failed)",
    }


def test_terminal_outcome_evidence_handles_raw_ocr_text_payloads():
    assert lightning_runner._terminal_outcome_evidence(
        {
            "status": "OK",
            "visible_ui": "reward_panel",
            "ocr": {
                "status": "OK",
                "texts": ["Region Secured", "Killed in Action"],
            },
        }
    ) == {
        "kind": "terminal_text",
        "path": "ocr.texts.1",
        "phrase": "killed in action",
        "text": "Killed in Action",
    }
    assert lightning_runner._terminal_outcome_evidence(
        {
            "status": "OK",
            "visible_ui": "reward_panel",
            "ocr": {
                "status": "OK",
                "texts": ["Region Secured", "Protect the Train", "FAILED"],
            },
        }
    ) == {
        "kind": "split_objective_failure_text",
        "path": "ocr.texts.2",
        "phrase": "failed",
        "context": "split_objective_text",
        "context_path": "ocr.texts.1",
        "context_text": "Protect the Train",
        "text": "FAILED",
    }
    assert lightning_runner._terminal_outcome_evidence(
        {
            "status": "OK",
            "visible_ui": "reward_panel",
            "ocr": {"status": "OK", "lines": ["K.I.A."]},
        }
    ) == {
        "kind": "terminal_text",
        "path": "ocr.lines.0",
        "phrase": "kia",
        "text": "K.I.A.",
    }


def test_terminal_outcome_evidence_ignores_non_objective_helper_failure_text():
    assert (
        lightning_runner._terminal_outcome_evidence(
            {"status": "ERROR", "message": "screenshot failed"}
        )
        is None
    )
    assert (
        lightning_runner._terminal_outcome_evidence(
            {"status": "failed", "reason": "classification helper failed"}
        )
        is None
    )
    assert (
        lightning_runner._terminal_outcome_evidence(
            {"status": "OK", "ocr_texts": ["helper", "FAILED"]}
        )
        is None
    )
    assert (
        lightning_runner._terminal_outcome_evidence(
            {"status": "OK", "texts": ["Protect the Train", "FAILED"]}
        )
        is None
    )
    assert (
        lightning_runner._terminal_outcome_evidence(
            {"status": "OK", "lines": ["KIA"]}
        )
        is None
    )


def test_terminal_outcome_evidence_requires_kia_token_boundaries():
    assert (
        lightning_runner._terminal_outcome_evidence(
            {"visible_text": "Time Pod reward: Akiane"}
        )
        is None
    )
    assert lightning_runner._terminal_outcome_evidence({"visible_text": "KIA"}) == {
        "kind": "terminal_text",
        "path": "visible_text",
        "phrase": "kia",
        "text": "KIA",
    }
    assert lightning_runner._terminal_outcome_evidence({"visible_text": "K.I.A."}) == {
        "kind": "terminal_text",
        "path": "visible_text",
        "phrase": "kia",
        "text": "K.I.A.",
    }
    assert lightning_runner._terminal_outcome_evidence(
        {"visible_text": "Region Secured\nKilled in Action"}
    ) == {
        "kind": "terminal_text",
        "path": "visible_text",
        "phrase": "killed in action",
        "text": "Region Secured\nKilled in Action",
    }
    assert lightning_runner._terminal_outcome_evidence(
        {"visible_text": "Region Secured\nPilot Lost"}
    ) == {
        "kind": "terminal_text",
        "path": "visible_text",
        "phrase": "pilot lost",
        "text": "Region Secured\nPilot Lost",
    }
    assert lightning_runner._terminal_outcome_evidence(
        {"visible_text": "Region Secured\nMech Lost"}
    ) == {
        "kind": "terminal_text",
        "path": "visible_text",
        "phrase": "mech lost",
        "text": "Region Secured\nMech Lost",
    }


def test_stop_token_evidence_requires_token_boundaries():
    assert (
        lightning_runner._stop_token_evidence(
            {"status": "OK", "reason": "renderer used Skia backend"},
            ("KIA",),
        )
        is None
    )
    assert lightning_runner._stop_token_evidence(
        {"logs": ["renderer used Skia backend"]},
        ("KIA",),
    ) is None
    assert lightning_runner._stop_token_evidence(
        {"status": "BLOCKED", "reason": "KIA: pilot killed"},
        ("KIA",),
    ) == {
        "token": "KIA",
        "path": "",
        "status": "BLOCKED",
        "reason": "KIA: pilot killed",
    }
    assert lightning_runner._stop_token_evidence(
        {"message": "Killed in Action"},
        ("KIA",),
    ) == {
        "token": "KIA",
        "path": "message",
        "text": "Killed in Action",
    }
    assert lightning_runner._stop_token_evidence(
        {"message": "Pilot Lost"},
        ("KIA",),
    ) == {
        "token": "KIA",
        "path": "message",
        "text": "Pilot Lost",
    }
    assert lightning_runner._stop_token_evidence(
        {"message": "Mech Lost"},
        ("KIA",),
    ) == {
        "token": "KIA",
        "path": "message",
        "text": "Mech Lost",
    }
    assert lightning_runner._stop_token_evidence(
        {"status": "THREAT_AUDIT_BLOCKED", "reason": "evidence required"},
        ("THREAT_AUDIT",),
    ) == {
        "token": "THREAT_AUDIT",
        "path": "",
        "status": "THREAT_AUDIT_BLOCKED",
        "reason": "evidence required",
    }
    assert lightning_runner._stop_token_evidence(
        {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "SAFETY_BLOCKED",
            "steps": [{"combat_loop_reason": "SAFETY_BLOCKED"}],
        },
        ("SAFETY_BLOCKED",),
    ) == {
        "token": "SAFETY_BLOCKED",
        "path": "",
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "SAFETY_BLOCKED",
    }
    assert lightning_runner._stop_token_evidence(
        {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "SAFETY_BLOCKED",
            "steps": [
                {
                    "combat_loop": {
                        "turns": [
                            {
                                "status": "SAFETY_BLOCKED",
                                "reason": "dirty frontier has mech_hp_loss",
                            }
                        ]
                    }
                }
            ],
        },
        ("SAFETY_BLOCKED",),
    ) == {
        "token": "SAFETY_BLOCKED",
        "path": "steps.0.combat_loop.turns.0",
        "status": "SAFETY_BLOCKED",
        "reason": "dirty frontier has mech_hp_loss",
    }
    assert lightning_runner._stop_token_evidence(
        {"steps": [{"stdout": "RESEARCH_REQUIRED: unknown Vek weapon"}]},
        ("RESEARCH_REQUIRED",),
    ) == {
        "token": "RESEARCH_REQUIRED",
        "path": "steps.0.stdout",
        "text": "RESEARCH_REQUIRED: unknown Vek weapon",
    }
    assert lightning_runner._stop_token_evidence(
        {
            "steps": [
                {
                    "status": "INVESTIGATE_POST_ENEMY",
                    "reason": "post-enemy audit mismatch",
                }
            ]
        },
        ("INVESTIGATE", "POST_ENEMY"),
    ) == {
        "token": "POST_ENEMY",
        "path": "steps.0",
        "status": "INVESTIGATE_POST_ENEMY",
        "reason": "post-enemy audit mismatch",
    }
    assert lightning_runner._stop_token_evidence(
        {
            "status": "INVESTIGATE",
            "reason": "see nested evidence",
            "post_enemy_result": {
                "status": "INVESTIGATE_POST_ENEMY",
                "reason": "post-enemy audit mismatch",
            },
        },
        ("INVESTIGATE", "POST_ENEMY"),
    ) == {
        "token": "POST_ENEMY",
        "path": "post_enemy_result",
        "status": "INVESTIGATE_POST_ENEMY",
        "reason": "post-enemy audit mismatch",
    }
    assert lightning_runner._stop_token_evidence(
        {
            "status": "INVESTIGATE",
            "reason": "generic investigation",
            "threat": {
                "message": "threat audit blocked: still targeted",
            },
        },
        ("INVESTIGATE", "THREAT_AUDIT"),
    ) == {
        "token": "THREAT_AUDIT",
        "path": "threat.message",
        "text": "threat audit blocked: still targeted",
    }
    assert lightning_runner._stop_token_evidence(
        {"stdout": "INVESTIGATE_POST_ENEMY: post-enemy audit mismatch"},
        ("INVESTIGATE", "POST_ENEMY"),
    ) == {
        "token": "POST_ENEMY",
        "path": "stdout",
        "text": "INVESTIGATE_POST_ENEMY: post-enemy audit mismatch",
    }
    assert lightning_runner._stop_token_evidence(
        {"stdout": "post-enemy audit mismatch"},
        ("POST_ENEMY",),
    ) == {
        "token": "POST_ENEMY",
        "path": "stdout",
        "text": "post-enemy audit mismatch",
    }
    assert lightning_runner._stop_token_evidence(
        {"stdout": "threat audit blocked: still targeted"},
        ("THREAT_AUDIT",),
    ) == {
        "token": "THREAT_AUDIT",
        "path": "stdout",
        "text": "threat audit blocked: still targeted",
    }
    assert lightning_runner._stop_token_evidence(
        {"stdout": "safety blocked by dirty frontier"},
        ("SAFETY_BLOCKED",),
    ) == {
        "token": "SAFETY_BLOCKED",
        "path": "stdout",
        "text": "safety blocked by dirty frontier",
    }
    assert lightning_runner._stop_token_evidence(
        {"stdout": "requires research: unknown weapon"},
        ("RESEARCH_REQUIRED",),
    ) == {
        "token": "RESEARCH_REQUIRED",
        "path": "stdout",
        "text": "requires research: unknown weapon",
    }
    assert lightning_runner._stop_token_evidence(
        {"stdout": "objective failed on reward screen"},
        ("FAILED_OBJECTIVE",),
    ) == {
        "token": "FAILED_OBJECTIVE",
        "path": "stdout",
        "text": "objective failed on reward screen",
    }
    assert lightning_runner._stop_token_evidence(
        {"stdout": "timeline lost after mission"},
        ("TIMELINE_COLLAPSE",),
    ) == {
        "token": "TIMELINE_COLLAPSE",
        "path": "stdout",
        "text": "timeline lost after mission",
    }


def test_stop_token_evidence_ignores_ui_metadata_labels():
    assert (
        lightning_runner._stop_token_evidence(
            {
                "status": "OK",
                "visible_ui": {
                    "status": "OK",
                    "visible_ui": "kia_panel",
                    "visible_name": "kia_panel",
                    "recommended_control": "kia_understood",
                },
            },
            ("KIA",),
        )
        is None
    )
    assert lightning_runner._stop_token_evidence(
        {
            "status": "BLOCKED",
            "reason": "KIA: pilot killed",
            "visible_ui": {"status": "OK", "visible_ui": "new_game_setup"},
        },
        ("KIA",),
    ) == {
        "token": "KIA",
        "path": "",
        "status": "BLOCKED",
        "reason": "KIA: pilot killed",
    }


def test_stop_token_evidence_ignores_dirty_frontier_violation_kind_metadata():
    evidence = {
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "combat_loop_returned",
        "last_attempt": {
            "action": {
                "combat_loop": {
                    "last_turn_result": {
                        "status": "SAFETY_BLOCKED",
                        "dirty_frontier": [
                            {
                                "label": "objective_loss",
                                "violations": [
                                    {"kind": "building_destroyed"},
                                    {"kind": "mech_hp_loss"},
                                ],
                            },
                            {
                                "label": "mech_loss",
                                "violations": [
                                    {"kind": "pod_unrecovered_final"},
                                    {"kind": "mech_lost"},
                                ],
                            },
                        ],
                    }
                }
            }
        },
    }

    assert lightning_runner._stop_token_evidence(evidence, ("KIA",)) is None
    assert lightning_runner._stop_token_evidence(evidence, ("SAFETY_BLOCKED",)) == {
        "token": "SAFETY_BLOCKED",
        "path": "last_attempt.action.combat_loop.last_turn_result",
        "status": "SAFETY_BLOCKED",
        "reason": "",
    }


def test_solver_timeout_evidence_ignores_recovered_deploy_ack_timeout():
    assert (
        lightning_runner._solver_or_combat_timeout_evidence(
            {
                "status": "OK",
                "deployments": [
                    {
                        "ack": "ACK_TIMEOUT_BUT_PLACED: command timed out",
                        "timeout_recovered": True,
                    }
                ],
            }
        )
        is None
    )


def test_solver_timeout_evidence_finds_nested_solver_timeout_warning():
    evidence = lightning_runner._solver_or_combat_timeout_evidence(
        {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "steps": [
                {
                    "action": "combat_loop",
                    "combat_loop": {
                        "turns": [
                            {
                                "warning": (
                                    "Solver returned empty solution "
                                    "(timeout or no valid actions)"
                                ),
                            }
                        ]
                    },
                }
            ],
        }
    )

    assert evidence == {
        "kind": "solver_timeout",
        "path": "steps.0.combat_loop.turns.0.warning",
        "text": "Solver returned empty solution (timeout or no valid actions)",
    }


def test_unexpected_menu_evidence_finds_nested_visible_ui():
    evidence = lightning_runner._unexpected_menu_evidence(
        {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "steps": [
                {
                    "visible_ui": {
                        "status": "OK",
                        "visible_ui": "title_screen",
                    }
                }
            ],
        }
    )

    assert evidence == {
        "kind": "unexpected_menu",
        "path": "steps.0.visible_ui.visible_ui",
        "visible_name": "title_screen",
    }


def test_current_unexpected_menu_evidence_detects_live_visible_ui():
    evidence = lightning_runner._current_unexpected_menu_evidence(
        {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "visible_ui": {
                "status": "OK",
                "visible_ui": "title_screen",
            },
            "pause_guard": pause_menu(),
        }
    )

    assert evidence == {
        "kind": "unexpected_menu",
        "path": "visible_ui.visible_ui",
        "visible_name": "title_screen",
    }


def test_current_unexpected_menu_evidence_ignores_stale_resume_guard_title():
    evidence = lightning_runner._current_unexpected_menu_evidence(
        {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "visible_ui": {
                "status": "OK",
                "visible_ui": "pause_menu",
            },
            "last_attempt": {
                "resume_guard": {
                    "post_click_visible_ui": {
                        "status": "OK",
                        "visible_ui": "title_screen",
                    }
                }
            },
            "pause_guard": pause_menu(),
        }
    )

    assert evidence is None


def test_current_unexpected_menu_evidence_ignores_stale_pause_guard_after_resume_to_map():
    evidence = lightning_runner._current_unexpected_menu_evidence(
        {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "route_mission_mismatch_after_start_recovered",
            "last_attempt": {
                "resume_guard": {
                    "post_click_visible_ui": {
                        "status": "OK",
                        "visible_ui": "island_map_or_unknown",
                    }
                }
            },
            "pause_guard": {
                "status": "OK",
                "reason": "new_game_setup_visible",
                "visible_ui": {
                    "status": "OK",
                    "visible_ui": "new_game_setup",
                },
            },
        }
    )

    assert evidence is None


def test_baseline_runner_starts_from_title_and_completes_two_islands():
    calls: list[tuple[str, dict]] = []
    session = SimpleNamespace(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segment_kwargs: list[dict] = []
    classify_after_title = False

    def record(name, payload):
        def fn(*args, **kwargs):
            calls.append((name, {"args": args, **kwargs}))
            return payload

        return fn

    def lightning_ui(*args, **kwargs):
        nonlocal classify_after_title
        control = kwargs.get("control") or (args[0] if args else None)
        calls.append(("lightning_ui", {"args": args, **kwargs}))
        if control == "classify" and classify_after_title:
            classify_after_title = False
            return {"status": "OK", "visible_ui": "new_game_setup"}
        if control == "title_new_game":
            classify_after_title = True
        if control == "setup_start":
            return {"status": "OK"}
        if control == "classify":
            return pause_menu()
        return {"status": "OK"}

    def start_run(*args, **kwargs):
        calls.append(("start_run", {"args": args, **kwargs}))
        session.run_id = "20260606_101010_001"
        return {"status": "OK"}

    def segment(*args, **kwargs):
        calls.append(("segment", {"args": args, **kwargs}))
        segment_kwargs.append(kwargs)
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=record(
            "pause_guard",
            {"status": "OK", "visible_ui": {"status": "OK", "visible_ui": "title_screen"}},
        ),
        cmd_lightning_ui=lightning_ui,
        cmd_verify_setup_screen=record("verify_setup", {"status": "PASS"}),
        cmd_lightning_start_run=start_run,
        cmd_lightning_preflight=record("preflight", preflight_pass()),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner()
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert [name for name, _ in calls[:6]] == [
        "pause_guard",
        "lightning_ui",
        "lightning_ui",
        "lightning_ui",
        "verify_setup",
        "start_run",
    ]
    assert calls[1][1]["control"] == "title_new_game"
    assert calls[3][1]["control"] == "setup_start"
    classify_calls = [
        payload
        for name, payload in calls
        if name == "lightning_ui" and payload.get("control") == "classify"
    ]
    assert classify_calls
    assert all(payload.get("include_ocr") is True for payload in classify_calls)
    assert segment_kwargs[0]["time_limit"] == 10.0
    assert segment_kwargs[0]["auto_clear_panels"] is False
    assert segment_kwargs[0]["lightning_speed_loss_policy"] is False
    assert segment_kwargs[0]["route_routing"] == "lightning_baseline"
    assert segment_kwargs[0]["route_speed_vetoes"] is False
    assert segment_kwargs[0]["allow_objective_loss"] is False


def test_runner_blocks_when_title_new_game_raises():
    session = SimpleNamespace(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )

    def lightning_ui(**kwargs):
        assert kwargs["control"] == "title_new_game"
        raise RuntimeError("title click crashed")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: {
            "status": "OK",
            "visible_ui": {"status": "OK", "visible_ui": "title_screen"},
        },
        cmd_lightning_ui=lightning_ui,
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "title_new_game_exception"
    assert result["span"] == "title_new_game"
    assert result["exception_type"] == "RuntimeError"
    assert result["error"] == "title click crashed"
    assert "title click crashed" in result["traceback"]
    assert any(
        name == "title_new_game_exception"
        and payload["span"] == "title_new_game"
        and payload["error"] == "title click crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_when_classify_after_title_raises():
    session = SimpleNamespace(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )

    def lightning_ui(**kwargs):
        if kwargs["control"] == "title_new_game":
            return {"status": "OK", "reason": "clicked_title_new_game"}
        assert kwargs["control"] == "classify"
        assert kwargs["include_ocr"] is True
        raise RuntimeError("post-title classify crashed")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: {
            "status": "OK",
            "visible_ui": {"status": "OK", "visible_ui": "title_screen"},
        },
        cmd_lightning_ui=lightning_ui,
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "classify_after_title_new_game_exception"
    assert result["span"] == "classify_after_title_new_game"
    assert result["exception_type"] == "RuntimeError"
    assert result["error"] == "post-title classify crashed"
    assert "post-title classify crashed" in result["traceback"]
    assert result["title"]["reason"] == "clicked_title_new_game"
    assert any(
        name == "classify_after_title_new_game_exception"
        and payload["span"] == "classify_after_title_new_game"
        and payload["error"] == "post-title classify crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_setup_start_when_verify_setup_fails():
    calls: list[tuple[str, dict]] = []
    session = SimpleNamespace(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    classify_after_title = False

    def lightning_ui(*args, **kwargs):
        nonlocal classify_after_title
        control = kwargs.get("control") or (args[0] if args else None)
        calls.append(("lightning_ui", {"args": args, **kwargs}))
        if control == "title_new_game":
            classify_after_title = True
            return {"status": "OK"}
        if control == "classify" and classify_after_title:
            classify_after_title = False
            return {"status": "OK", "visible_ui": "new_game_setup"}
        if control == "setup_start":
            return {"status": "OK"}
        if control == "classify":
            return pause_menu()
        return {"status": "OK"}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: {
            "status": "OK",
            "visible_ui": {"status": "OK", "visible_ui": "title_screen"},
        },
        cmd_lightning_ui=lightning_ui,
        cmd_verify_setup_screen=lambda **kwargs: calls.append(
            ("verify_setup", kwargs)
        )
        or {
            "status": "FAIL",
            "window_focus_verified": False,
            "screenshot_path": "/tmp/not_itb.png",
        },
        cmd_lightning_start_run=unexpected("lightning_start_run"),
        cmd_lightning_preflight=unexpected("preflight"),
        cmd_lightning_segment=unexpected("segment"),
    )

    runner = make_runner()
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "start_from_setup_failed"
    assert result["start"]["reason"] == "setup_not_verified"
    assert result["start"]["setup"]["screenshot_path"] == "/tmp/not_itb.png"
    assert [name for name, _ in calls] == [
        "lightning_ui",
        "lightning_ui",
        "lightning_ui",
        "verify_setup",
    ]
    assert calls[2][1]["control"] == "setup_start"


def test_runner_top_level_promotes_external_prompt_during_start():
    calls = []

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        calls.append(control)
        if control == "setup_start":
            return {"status": "OK"}
        return {"status": "OK", "visible_ui": "new_game_setup"}

    commands = SimpleNamespace(
        cmd_lightning_pause_guard=lambda **_: {
            "status": "OK",
            "visible_ui": {"status": "OK", "visible_ui": "new_game_setup"},
        },
        cmd_lightning_ui=lightning_ui,
        cmd_verify_setup_screen=lambda **_kwargs: {"status": "PASS"},
        cmd_lightning_start_run=lambda **_kwargs: {
            "status": "BLOCKED",
            "reason": "external_system_prompt_visible",
            "post_setup_start_ui": {
                "status": "OK",
                "visible_ui": "system_privacy_prompt",
                "requires_user_authorization": True,
            },
        },
        _load_session=unexpected("load_session_after_blocked_start"),
    )

    runner = make_runner()
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "external_system_prompt_visible"
    assert result["start"]["reason"] == "external_system_prompt_visible"
    assert calls == ["setup_start", "ensure_pause"]


def test_runner_resumes_first_island_selection_after_prompt_block():
    session = SimpleNamespace(
        run_id="20260606_101112_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    select_calls = []
    segment_calls = []

    def select_first_island(**kwargs):
        select_calls.append(kwargs)
        session.current_island = "archive"
        return {
            "status": "OK",
            "reason": "first_island_paused",
            "session_current_island": {
                "status": "OK",
                "current_island": "archive",
            },
            "pause_after_first_island": {
                "status": "OK",
                "pause_verify": {"status": "OK", "visible_ui": "pause_menu"},
            },
        }

    def segment(**kwargs):
        segment_calls.append(kwargs)
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: {
            "status": "SKIPPED",
            "reason": "unknown_screen_without_bridge",
            "visible_ui": {"status": "OK", "visible_ui": "island_map_or_unknown"},
        },
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_verify_setup_screen=lambda **_kwargs: {"status": "PASS"},
        cmd_lightning_select_first_island=select_first_island,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert select_calls == [
        {
            "profile": "Alpha",
            "first_island": "archive",
            "advanced_content": "off",
            "dry_run": False,
        }
    ]
    assert len(segment_calls) == 1
    assert session.current_island == "archive"


def test_runner_resumes_first_island_selection_after_segment_reveals_picker():
    session = SimpleNamespace(
        run_id="20260606_101112_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="",
        current_mission="",
        mission_index=0,
        islands_completed=[],
        tags=[],
    )
    select_calls = []
    segment_calls = []

    def select_first_island(**kwargs):
        select_calls.append(kwargs)
        session.current_island = "archive"
        return {
            "status": "OK",
            "reason": "first_island_paused",
            "session_current_island": {
                "status": "OK",
                "current_island": "archive",
            },
            "pause_after_first_island": {
                "status": "OK",
                "pause_verify": {"status": "OK", "visible_ui": "pause_menu"},
            },
        }

    def segment(**kwargs):
        segment_calls.append(kwargs)
        if len(segment_calls) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "first_island_selection_map_without_route_context",
                "pause_guard": {
                    "status": "SKIPPED",
                    "reason": "unknown_screen_without_bridge",
                    "visible_ui": {
                        "status": "OK",
                        "visible_ui": "island_map_or_unknown",
                    },
                },
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_verify_setup_screen=lambda **_kwargs: {"status": "PASS"},
        cmd_lightning_select_first_island=select_first_island,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert select_calls == [
        {
            "profile": "Alpha",
            "first_island": "archive",
            "advanced_content": "off",
            "dry_run": False,
        }
    ]
    assert len(segment_calls) == 2
    assert session.current_island == "archive"


def test_runner_confirms_pending_first_island_before_preflight():
    session = SimpleNamespace(
        run_id="20260606_101112_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="",
        current_mission="",
        mission_index=0,
        islands_completed=[],
        tags=["achievement", "lightning_first_island_clicked:archive"],
    )
    select_calls = []
    preflight_calls = []
    segment_calls = []

    def select_first_island(**kwargs):
        select_calls.append(kwargs)
        session.current_island = "archive"
        session.tags = ["achievement"]
        return {
            "status": "OK",
            "reason": "first_island_pending_confirmed",
            "session_current_island": {
                "status": "OK",
                "current_island": "archive",
            },
        }

    def preflight(**kwargs):
        preflight_calls.append(kwargs)
        return preflight_pass()

    def segment(**kwargs):
        segment_calls.append(kwargs)
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_verify_setup_screen=lambda **_kwargs: {"status": "PASS"},
        cmd_lightning_select_first_island=select_first_island,
        cmd_lightning_preflight=preflight,
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert select_calls == [
        {
            "profile": "Alpha",
            "first_island": "archive",
            "advanced_content": "off",
            "dry_run": False,
        }
    ]
    assert preflight_calls
    assert len(segment_calls) == 1
    assert session.current_island == "archive"
    assert session.tags == ["achievement"]


def test_runner_preserves_pending_first_island_unverified_reason():
    session = SimpleNamespace(
        run_id="20260606_101112_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="",
        current_mission="",
        mission_index=0,
        islands_completed=[],
        tags=["achievement", "lightning_first_island_clicked:archive"],
    )
    select_calls = []
    preflight_called = False

    def select_first_island(**kwargs):
        select_calls.append(kwargs)
        return {
            "status": "BLOCKED",
            "reason": "first_island_selection_pending_unverified",
            "pending_first_island": "archive",
            "visible_ui": {"status": "OK", "visible_ui": "island_map_or_unknown"},
        }

    def preflight(**_kwargs):
        nonlocal preflight_called
        preflight_called = True
        return preflight_pass()

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_verify_setup_screen=lambda **_kwargs: {"status": "PASS"},
        cmd_lightning_select_first_island=select_first_island,
        cmd_lightning_preflight=preflight,
        cmd_lightning_segment=unexpected("segment"),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "first_island_selection_pending_unverified"
    assert result["first_island_resume"]["reason"] == (
        "first_island_selection_pending_unverified"
    )
    assert select_calls == [
        {
            "profile": "Alpha",
            "first_island": "archive",
            "advanced_content": "off",
            "dry_run": False,
        }
    ]
    assert preflight_called is False


@pytest.mark.parametrize(
    "helper_reason",
    [
        "first_island_selection_screen_unverified",
        "first_island_click_failed",
        "first_island_save_state_unverified",
        "first_island_session_unverified",
    ],
)
def test_runner_preserves_first_island_helper_specific_reasons(helper_reason):
    session = SimpleNamespace(
        run_id="20260606_101112_004",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="",
        current_mission="",
        mission_index=0,
        islands_completed=[],
        tags=[],
    )
    preflight_called = False

    def preflight(**_kwargs):
        nonlocal preflight_called
        preflight_called = True
        return preflight_pass()

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: {
            "status": "SKIPPED",
            "reason": "unknown_screen_without_bridge",
            "visible_ui": {"status": "OK", "visible_ui": "island_map_or_unknown"},
        },
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_verify_setup_screen=lambda **_kwargs: {"status": "PASS"},
        cmd_lightning_select_first_island=lambda **_kwargs: {
            "status": "BLOCKED",
            "reason": helper_reason,
            "visible_ui": {"status": "OK", "visible_ui": "island_map_or_unknown"},
        },
        cmd_lightning_preflight=preflight,
        cmd_lightning_segment=unexpected("segment"),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == helper_reason
    assert result["first_island_resume"]["reason"] == helper_reason
    assert preflight_called is False


def test_runner_blocks_when_setup_start_raises():
    def lightning_ui(**kwargs):
        assert kwargs["control"] == "setup_start"
        raise RuntimeError("setup panel crashed")

    commands = SimpleNamespace(
        cmd_lightning_ui=lightning_ui,
        cmd_verify_setup_screen=unexpected("verify_setup"),
        cmd_lightning_start_run=unexpected("lightning_start_run"),
    )
    runner = make_runner()

    result = runner._start_from_setup(commands, "new_game_setup")

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "setup_start_exception"
    assert result["span"] == "setup_start"
    assert result["exception_type"] == "RuntimeError"
    assert result["error"] == "setup panel crashed"
    assert "setup panel crashed" in result["traceback"]
    assert any(
        name == "command_span"
        and payload["label"] == "setup_start"
        and payload["status"] == "exception"
        and payload["error"] == "setup panel crashed"
        for name, payload in runner.telemetry.events
    )
    assert any(
        name == "setup_start_exception"
        and payload["span"] == "setup_start"
        and payload["error"] == "setup panel crashed"
        for name, payload in runner.telemetry.events
    )


def test_span_preserves_helper_result_when_finish_event_raises():
    class FinishSpanTelemetryRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "command_span" and payload.get("status") == "finish":
                raise RuntimeError("span finish write crashed")
            super().event(name, **payload)

    runner = make_runner()
    runner.telemetry = FinishSpanTelemetryRaises()

    result = runner._span(
        "finish_event_failure",
        lambda **_kwargs: {"status": "OK", "reason": "helper_finished"},
    )

    assert result["status"] == "OK"
    assert result["reason"] == "helper_finished"
    assert result["command_span_finish_event_exception_type"] == "RuntimeError"
    assert result["command_span_finish_event_error"] == "span finish write crashed"
    assert any(
        name == "command_span"
        and payload["label"] == "finish_event_failure"
        and payload["status"] == "start"
        for name, payload in runner.telemetry.events
    )


def test_span_preserves_helper_result_when_start_event_raises():
    class StartSpanTelemetryRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "command_span" and payload.get("status") == "start":
                raise RuntimeError("span start write crashed")
            super().event(name, **payload)

    helper_calls = 0
    runner = make_runner()
    runner.telemetry = StartSpanTelemetryRaises()

    def helper(**_kwargs):
        nonlocal helper_calls
        helper_calls += 1
        return {"status": "OK", "reason": "helper_finished"}

    result = runner._span("start_event_failure", helper)

    assert helper_calls == 1
    assert result["status"] == "OK"
    assert result["reason"] == "helper_finished"
    assert result["command_span_start_event_exception_type"] == "RuntimeError"
    assert result["command_span_start_event_error"] == "span start write crashed"
    assert runner.telemetry_event_errors == [
        {
            "event_name": "command_span",
            "exception_type": "RuntimeError",
            "error": "span start write crashed",
        }
    ]
    assert any(
        name == "command_span"
        and payload["label"] == "start_event_failure"
        and payload["status"] == "finish"
        for name, payload in runner.telemetry.events
    )


def test_span_preserves_helper_exception_when_exception_event_raises():
    class ExceptionSpanTelemetryRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "command_span" and payload.get("status") == "exception":
                raise RuntimeError("span exception write crashed")
            super().event(name, **payload)

    runner = make_runner()
    runner.telemetry = ExceptionSpanTelemetryRaises()

    def helper(**_kwargs):
        raise ValueError("helper crashed")

    with pytest.raises(ValueError, match="helper crashed"):
        runner._span("exception_event_failure", helper)

    assert runner.telemetry_event_errors == [
        {
            "event_name": "command_span",
            "exception_type": "RuntimeError",
            "error": "span exception write crashed",
        }
    ]
    assert any(
        name == "command_span"
        and payload["label"] == "exception_event_failure"
        and payload["status"] == "start"
        for name, payload in runner.telemetry.events
    )


def test_span_preserves_helper_exception_when_start_event_raises():
    class StartSpanTelemetryRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "command_span" and payload.get("status") == "start":
                raise RuntimeError("span start write crashed")
            super().event(name, **payload)

    helper_calls = 0
    runner = make_runner()
    runner.telemetry = StartSpanTelemetryRaises()

    def helper(**_kwargs):
        nonlocal helper_calls
        helper_calls += 1
        raise ValueError("helper crashed")

    with pytest.raises(ValueError, match="helper crashed"):
        runner._span("start_event_failure_exception", helper)

    assert helper_calls == 1
    assert runner.telemetry_event_errors == [
        {
            "event_name": "command_span",
            "exception_type": "RuntimeError",
            "error": "span start write crashed",
        }
    ]
    assert any(
        name == "command_span"
        and payload["label"] == "start_event_failure_exception"
        and payload["status"] == "exception"
        and payload["error"] == "helper crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_preserves_pause_guard_exception_when_event_write_raises():
    class PauseGuardEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "pause_guard_initial_exception":
                raise RuntimeError("pause guard event write crashed")
            super().event(name, **payload)

    def pause_guard(**_kwargs):
        raise RuntimeError("pause guard helper crashed")

    commands = SimpleNamespace(
        cmd_lightning_pause_guard=pause_guard,
    )
    runner = make_runner()
    runner.telemetry = PauseGuardEventRaises()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "pause_guard_initial_exception"
    assert result["error"] == "pause guard helper crashed"
    assert result["telemetry_event_errors"] == [
        {
            "event_name": "pause_guard_initial_exception",
            "exception_type": "RuntimeError",
            "error": "pause guard event write crashed",
        }
    ]
    assert any(
        name == "runner_finish"
        and payload["reason"] == "pause_guard_initial_exception"
        for name, payload in runner.telemetry.events
    )
    assert not any(
        name == "runner_finish" and payload["reason"] == "runner_exception"
        for name, payload in runner.telemetry.events
    )


def test_preflight_exception_preserved_when_event_write_raises():
    class PreflightEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "preflight_exception":
                raise RuntimeError("preflight event write crashed")
            super().event(name, **payload)

    def preflight(**_kwargs):
        raise RuntimeError("preflight helper crashed")

    commands = SimpleNamespace(cmd_lightning_preflight=preflight)
    runner = make_runner()
    runner.telemetry = PreflightEventRaises()

    result = runner._run_preflight(commands, label="preflight_initial")

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "preflight_exception"
    assert result["error"] == "preflight helper crashed"
    assert result["telemetry_event_errors"] == [
        {
            "event_name": "preflight_exception",
            "exception_type": "RuntimeError",
            "error": "preflight event write crashed",
        }
    ]


def test_visible_classifier_exception_preserved_when_event_write_raises():
    class ClassifierEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "screen_classification_exception":
                raise RuntimeError("classifier event write crashed")
            super().event(name, **payload)

    def lightning_ui(**_kwargs):
        raise RuntimeError("classifier helper crashed")

    commands = SimpleNamespace(cmd_lightning_ui=lightning_ui)
    runner = make_runner()
    runner.telemetry = ClassifierEventRaises()

    result = runner._handle_visible_panel(commands, segment_index=4)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "screen_classification_exception"
    assert result["error"] == "classifier helper crashed"
    assert result["telemetry_event_errors"] == [
        {
            "event_name": "screen_classification_exception",
            "exception_type": "RuntimeError",
            "error": "classifier event write crashed",
        }
    ]


def test_handle_visible_panel_does_not_block_ocr_clean_kia_crop():
    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        assert control == "classify"
        return {
            "status": "OK",
            "visible_ui": "kia_panel",
            "recommended_control": "kia_understood",
            "ocr": {"status": "OK", "texts": ["Choose your first island"]},
            "ocr_texts": ["Choose your first island"],
            "screenshot_path": "/tmp/intro_kia_crop_false_positive.png",
        }

    commands = SimpleNamespace(cmd_lightning_ui=lightning_ui)

    result = make_runner()._handle_visible_panel(commands, segment_index=1)

    assert result["status"] == "NO_ACTION"
    assert result["reason"] == "no_known_panel_visible"
    assert result["visible_name"] == "kia_panel"
    assert result["visible_ui"]["screenshot_path"] == (
        "/tmp/intro_kia_crop_false_positive.png"
    )


def test_runner_preserves_success_when_progress_event_write_raises():
    session = SimpleNamespace(
        run_id="20260606_191919_006",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    progress_event_calls = 0

    class RunnerProgressEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            nonlocal progress_event_calls
            if name == "runner_progress":
                progress_event_calls += 1
                raise RuntimeError("runner progress event write crashed")
            super().event(name, **payload)

    def segment(**_kwargs):
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )
    runner = make_runner()
    runner.telemetry = RunnerProgressEventRaises()

    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert progress_event_calls == 1
    assert result["telemetry_event_errors"] == [
        {
            "event_name": "runner_progress",
            "exception_type": "RuntimeError",
            "error": "runner progress event write crashed",
        }
    ]


def test_runner_preserves_pace_gate_when_pace_event_write_raises():
    session = SimpleNamespace(
        run_id="20260606_191919_007",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )

    class PaceGateEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "pace_gate":
                raise RuntimeError("pace gate event write crashed")
            super().event(name, **payload)

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_with_timer(16 * 60),
        cmd_lightning_segment=unexpected("segment"),
    )
    runner = make_runner(mode="speed", max_attempts=1)
    runner.telemetry = PaceGateEventRaises()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "first_mission_start_pace_gate"
    assert result["pace_gate"]["telemetry_event_errors"] == [
        {
            "event_name": "pace_gate",
            "exception_type": "RuntimeError",
            "error": "pace gate event write crashed",
        }
    ]


def test_post_segment_panel_block_preserved_when_panel_event_write_raises():
    class PostSegmentPanelEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "post_segment_panel_blocked":
                raise RuntimeError("post-segment panel event write crashed")
            super().event(name, **payload)

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify":
            return {
                "status": "OK",
                "visible_ui": "reward_panel",
                "visible_text": "Region Secured\nProtect the Train (Failed)",
                "screenshot_path": "/tmp/post_segment_failed_reward.png",
            }
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(cmd_lightning_ui=lightning_ui)
    runner = make_runner()
    runner.telemetry = PostSegmentPanelEventRaises()

    result = runner._handle_post_segment_panel(
        commands,
        segment={
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "LIGHTNING_ATTEMPT_PANEL_READY",
        },
        segment_index=2,
    )

    assert result is not None
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "terminal_outcome_visible"
    assert result["terminal_evidence"]["phrase"] == "(failed)"
    assert result["telemetry_event_errors"] == [
        {
            "event_name": "post_segment_panel_blocked",
            "exception_type": "RuntimeError",
            "error": "post-segment panel event write crashed",
        }
    ]


def test_runner_blocks_when_setup_verifier_raises_before_start():
    def verify_setup(**_kwargs):
        raise RuntimeError("setup screenshot crashed")

    commands = SimpleNamespace(
        cmd_verify_setup_screen=verify_setup,
        cmd_lightning_start_run=unexpected("lightning_start_run"),
    )
    runner = make_runner()

    result = runner._start_from_setup(commands, None)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "setup_not_verified"
    setup = result["setup"]
    assert setup["reason"] == "setup_verification_exception"
    assert setup["span"] == "verify_setup"
    assert setup["exception_type"] == "RuntimeError"
    assert setup["error"] == "setup screenshot crashed"
    assert "setup screenshot crashed" in setup["traceback"]
    assert any(
        name == "setup_verification_exception"
        and payload["span"] == "verify_setup"
        and payload["error"] == "setup screenshot crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_when_lightning_start_run_raises():
    def start_run(**_kwargs):
        raise RuntimeError("start helper crashed")

    commands = SimpleNamespace(
        cmd_verify_setup_screen=lambda **_kwargs: {"status": "PASS"},
        cmd_lightning_start_run=start_run,
    )
    runner = make_runner()

    result = runner._start_from_setup(commands, None)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "lightning_start_run_exception"
    assert result["span"] == "lightning_start_run"
    assert result["exception_type"] == "RuntimeError"
    assert result["error"] == "start helper crashed"
    assert "start helper crashed" in result["traceback"]
    assert any(
        name == "command_span"
        and payload["label"] == "lightning_start_run"
        and payload["status"] == "exception"
        and payload["error"] == "start helper crashed"
        for name, payload in runner.telemetry.events
    )
    assert any(
        name == "lightning_start_run_exception"
        and payload["span"] == "lightning_start_run"
        and payload["error"] == "start helper crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_promotes_external_prompt_from_start_run_failure():
    commands = SimpleNamespace(
        cmd_verify_setup_screen=lambda **_kwargs: {"status": "PASS"},
        cmd_lightning_start_run=lambda **_kwargs: {
            "status": "BLOCKED",
            "reason": "external_system_prompt_visible",
            "post_setup_start_ui": {
                "status": "OK",
                "visible_ui": "system_privacy_prompt",
                "requires_user_authorization": True,
                "external_prompt": {
                    "matched": True,
                    "kind": "macos_screen_audio_privacy_prompt",
                },
            },
        },
    )
    runner = make_runner()

    result = runner._start_from_setup(commands, None)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "external_system_prompt_visible"
    assert result["external_prompt_evidence"]["path"] == "post_setup_start_ui"
    assert result["external_prompt_evidence"]["requires_user_authorization"] is True
    assert result["external_prompt_evidence"]["visible_ui"]["visible_ui"] == (
        "system_privacy_prompt"
    )
    assert result["start"]["reason"] == "external_system_prompt_visible"


def test_runner_blocks_when_setup_verifier_raises_after_adjustment(monkeypatch):
    calls = {"verify": 0}

    def verify_setup(**_kwargs):
        calls["verify"] += 1
        if calls["verify"] == 1:
            return {
                "status": "FAIL",
                "click_plan": [
                    {
                        "x": 100,
                        "y": 200,
                        "description": "fix difficulty",
                    }
                ],
            }
        raise RuntimeError("setup recheck crashed")

    monkeypatch.setattr(
        "src.control.mac_click.click_window_point",
        lambda *args, **kwargs: {"status": "OK"},
    )
    commands = SimpleNamespace(
        cmd_verify_setup_screen=verify_setup,
        cmd_lightning_start_run=unexpected("lightning_start_run"),
    )
    runner = make_runner()

    result = runner._start_from_setup(commands, None)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "setup_not_verified"
    setup = result["setup"]
    assert setup["reason"] == "setup_verification_exception"
    assert setup["span"] == "verify_setup_after_clicks"
    assert setup["exception_type"] == "RuntimeError"
    assert setup["error"] == "setup recheck crashed"
    assert calls["verify"] == 2
    assert any(
        name == "setup_click"
        and payload["click_result"]["status"] == "OK"
        for name, payload in runner.telemetry.events
    )
    assert any(
        name == "setup_verification_exception"
        and payload["span"] == "verify_setup_after_clicks"
        and payload["error"] == "setup recheck crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_when_setup_adjustment_click_raises(monkeypatch):
    def verify_setup(**_kwargs):
        return {
            "status": "FAIL",
            "screenshot_path": "/tmp/setup_click.png",
            "click_plan": [
                {
                    "x": 100,
                    "y": 200,
                    "description": "fix advanced content",
                }
            ],
        }

    def click_window_point(*_args, **_kwargs):
        raise RuntimeError("mac click crashed")

    monkeypatch.setattr(
        "src.control.mac_click.click_window_point",
        click_window_point,
    )
    commands = SimpleNamespace(
        cmd_verify_setup_screen=verify_setup,
        cmd_lightning_start_run=unexpected("lightning_start_run"),
    )
    runner = make_runner()

    result = runner._start_from_setup(commands, None)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "setup_not_verified"
    setup = result["setup"]
    assert setup["reason"] == "setup_click_exception"
    assert setup["click"]["description"] == "fix advanced content"
    assert setup["setup"]["screenshot_path"] == "/tmp/setup_click.png"
    assert setup["exception_type"] == "RuntimeError"
    assert setup["error"] == "mac click crashed"
    assert "mac click crashed" in setup["traceback"]
    assert any(
        name == "setup_click_exception"
        and payload["error"] == "mac click crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_when_setup_click_plan_is_malformed():
    def verify_setup(**_kwargs):
        return {
            "status": "FAIL",
            "click_plan": [
                {
                    "x": "not-an-int",
                    "y": 200,
                    "description": "bad emitted click",
                }
            ],
        }

    commands = SimpleNamespace(
        cmd_verify_setup_screen=verify_setup,
        cmd_lightning_start_run=unexpected("lightning_start_run"),
    )
    runner = make_runner()

    result = runner._start_from_setup(commands, None)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "setup_not_verified"
    setup = result["setup"]
    assert setup["reason"] == "setup_click_exception"
    assert setup["click"]["description"] == "bad emitted click"
    assert setup["exception_type"] == "ValueError"
    assert "not-an-int" in setup["error"]
    assert any(
        name == "setup_click_exception"
        and payload["exception_type"] == "ValueError"
        for name, payload in runner.telemetry.events
    )


def test_verify_run_setup_blocks_when_save_reader_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )

    def fake_load_game_state(_profile):
        raise RuntimeError("setup save parser crashed")

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)
    runner = make_runner()

    result = runner._verify_run_setup(SimpleNamespace(_load_session=lambda: session))

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "setup_state_mismatch"
    assert result["save_state"]["reason"] == "setup_save_state_reader_exception"
    assert result["save_state"]["exception_type"] == "RuntimeError"
    assert result["save_state"]["error"] == "setup save parser crashed"
    assert "setup save parser crashed" in result["save_state"]["traceback"]
    assert "save state reader raised during setup proof" in result["issues"]
    assert any(
        name == "setup_state_proof"
        and payload["save_state"]["reason"] == "setup_save_state_reader_exception"
        for name, payload in runner.telemetry.events
    )


def test_speed_mode_uses_speed_policy_and_short_budget():
    session = SimpleNamespace(
        run_id="20260606_111111_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_kwargs: list[dict] = []

    def segment(*args, **kwargs):
        segment_kwargs.append(kwargs)
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner(mode="speed")._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert segment_kwargs[0]["time_limit"] == 2.0
    assert segment_kwargs[0]["lightning_speed_loss_policy"] is True
    assert segment_kwargs[0]["route_routing"] == "lightning_war"
    assert segment_kwargs[0]["route_speed_vetoes"] is True
    assert segment_kwargs[0]["allow_dirty_plan"] is False
    assert (
        segment_kwargs[0]["max_wall_seconds"]
        == lightning_runner.DEFAULT_LIGHTNING_SPEED_SEGMENT_TIMEOUT
    )


def test_runner_resumes_hot_combat_without_startup_pause_or_panel_clear():
    session = SimpleNamespace(
        run_id="20260606_111113_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Artillery",
        mission_index=2,
        islands_completed=[],
    )
    calls: list[str] = []
    segment_kwargs: list[dict] = []

    def live_combat_guard(**_kwargs):
        calls.append("pause_guard")
        return {
            "status": "BLOCKED",
            "reason": "live_combat_phase",
            "visible_ui": {"status": "OK", "visible_ui": "combat_screen"},
            "last_poll": {
                "status": "BLOCKED",
                "reason": "live_combat_phase",
                "visible_ui": {
                    "status": "OK",
                    "visible_ui": "perfect_reward_choice",
                    "terminal_panel_false_positive": True,
                    "bridge_refine_snapshot": {
                        "status": "OK",
                        "phase": "combat_player",
                        "active_mechs": 3,
                        "in_active_mission": True,
                    },
                },
                "live_snapshot": {
                    "status": "OK",
                    "phase": "combat_player",
                    "active_mechs": 3,
                    "in_active_mission": True,
                },
                "decision": {
                    "status": "BLOCKED",
                    "reason": "live_combat_phase",
                },
            },
        }

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        calls.append(f"ui:{control}")
        if control == "classify":
            return {
                "status": "OK",
                "visible_ui": "perfect_reward_choice",
                "terminal_panel_false_positive": True,
                "bridge_refine_snapshot": {
                    "status": "OK",
                    "phase": "combat_player",
                    "active_mechs": 3,
                    "in_active_mission": True,
                },
            }
        return {"status": "OK", "reason": f"{control}_clicked"}

    def segment(*_args, **kwargs):
        calls.append("segment")
        segment_kwargs.append(kwargs)
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    def unexpected(name):
        def fn(*_args, **_kwargs):
            raise AssertionError(f"{name} should be deferred during hot combat")

        return fn

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=live_combat_guard,
        cmd_lightning_ui=lightning_ui,
        cmd_verify_setup_screen=unexpected("verify_setup"),
        cmd_lightning_preflight=unexpected("preflight"),
        cmd_lightning_segment=segment,
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert calls == ["pause_guard", "ui:classify", "segment", "ui:classify"]
    assert segment_kwargs[0]["pause_before_solve"] is True
    assert segment_kwargs[0]["route_routing"] == "lightning_baseline"
    assert segment_kwargs[0]["route_speed_vetoes"] is False


def test_runner_resumes_initial_reward_panel_hidden_under_pause():
    controls: list[str] = []
    session = SimpleNamespace(
        run_id="20260606_111116_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Artillery",
        mission_index=2,
        islands_completed=[],
    )
    resumed_from_pause = False
    segment_calls = 0

    def lightning_ui(*args, **kwargs):
        nonlocal resumed_from_pause
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "menu_continue":
            resumed_from_pause = True
            return {"status": "OK", "reason": "pause_menu_resumed"}
        if control == "classify" and resumed_from_pause:
            resumed_from_pause = False
            return {"status": "OK", "visible_ui": "reward_panel"}
        if control == "classify":
            return pause_menu()
        if control == "handle_screen":
            return {"status": "OK", "reason": "reward_panel_cleared"}
        if control == "ensure_pause":
            return pause_menu()
        return {"status": "OK"}

    def segment(*args, **kwargs):
        nonlocal segment_calls
        segment_calls += 1
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: {
            "status": "OK",
            "reason": "pause_clicked",
            "visible_ui": {"status": "OK", "visible_ui": "reward_panel"},
            "pause_verified": True,
            "pause_verify": {"status": "OK", "visible_ui": "pause_menu"},
        },
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner()
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert segment_calls == 1
    assert controls[:3] == ["menu_continue", "classify", "handle_screen"]
    assert "ensure_pause" in controls
    assert any(
        name == "startup_hidden_panel_handled"
        and payload["reason"] == "paused_segment_panel_handled"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_when_ensure_pause_raises_after_hidden_panel():
    controls: list[str] = []
    resumed_from_pause = False

    def lightning_ui(*args, **kwargs):
        nonlocal resumed_from_pause
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "menu_continue":
            resumed_from_pause = True
            return {"status": "OK", "reason": "pause_menu_resumed"}
        if control == "classify" and resumed_from_pause:
            resumed_from_pause = False
            return {"status": "OK", "visible_ui": "reward_panel"}
        if control == "classify":
            return pause_menu()
        if control == "handle_screen":
            return {"status": "OK", "reason": "reward_panel_cleared"}
        if control == "ensure_pause":
            raise RuntimeError("ensure pause crashed")
        return {"status": "OK"}

    commands = SimpleNamespace(cmd_lightning_ui=lightning_ui)
    runner = make_runner()

    result = runner._handle_paused_segment_panel(
        commands,
        segment_index=1,
        expected_visible_name="reward_panel",
        paused_panel=pause_menu(),
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "pause_after_segment_panel_failed"
    assert result["ensure_pause"]["reason"] == "ensure_pause_exception"
    assert result["ensure_pause"]["error"] == "ensure pause crashed"
    assert controls == ["menu_continue", "classify", "handle_screen", "ensure_pause"]
    assert any(
        name == "ensure_pause_exception"
        and payload["error"] == "ensure pause crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_does_not_autostart_initial_mission_preview_hidden_under_pause():
    controls: list[str] = []
    session = SimpleNamespace(
        run_id="20260606_111117_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=1,
        islands_completed=[],
    )

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify":
            return pause_menu()
        return {"status": "OK"}

    def segment(*_args, **_kwargs):
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: {
            "status": "OK",
            "reason": "pause_clicked",
            "visible_ui": {"status": "OK", "visible_ui": "mission_preview_panel"},
            "pause_verified": True,
            "pause_verify": {"status": "OK", "visible_ui": "pause_menu"},
        },
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert "menu_continue" not in controls
    assert "handle_screen" not in controls


def test_runner_blocks_on_stale_bridge_heartbeat():
    session = SimpleNamespace(
        run_id="20260606_111114_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Artillery",
        mission_index=2,
        islands_completed=[],
    )
    calls: list[str] = []

    def segment(*_args, **_kwargs):
        calls.append("segment")
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "steps": [
                {
                    "action": "combat_loop",
                    "combat_loop_reason": "error",
                    "combat_loop": {
                        "turns": [
                            {
                                "error": (
                                    "Attack 1: Bridge heartbeat stale after 20s "
                                    "-- Lua stopped ticking"
                                ),
                                "actions_completed": 1,
                            }
                        ]
                    },
                }
            ],
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "stale_bridge_heartbeat"
    assert result["heartbeat_evidence"] == {
        "kind": "stale_bridge_heartbeat",
        "path": "steps.0.combat_loop.turns.0.error",
        "text": (
            "Attack 1: Bridge heartbeat stale after 20s "
            "-- Lua stopped ticking"
        ),
    }
    assert "fresh read plus solve" in result["next_step"]
    assert calls == ["segment"]


@pytest.mark.parametrize("token", ["STALE_HEARTBEAT", "STALE_BRIDGE"])
def test_runner_promotes_stale_bridge_stop_tokens_without_pause(token):
    session = SimpleNamespace(
        run_id="20260606_111114_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Artillery",
        mission_index=2,
        islands_completed=[],
    )
    ensure_pause_called = False

    def lightning_ui(*args, **kwargs):
        nonlocal ensure_pause_called
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensure_pause_called = True
            raise AssertionError("stale bridge token should not click/pause")
        return pause_menu()

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "steps": [
                {
                    "action": "combat_loop",
                    "combat_loop": {
                        "turns": [
                            {
                                "status": "BLOCKED",
                                "reason": f"{token}: bridge state stale",
                            }
                        ]
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
    )

    runner = make_runner()
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "stale_bridge_heartbeat"
    assert result["stop_token"] == token
    assert result["stop_evidence"] == {
        "token": token,
        "path": "steps.0.combat_loop.turns.0",
        "status": "BLOCKED",
        "reason": f"{token}: bridge state stale",
    }
    assert "fresh read plus solve" in result["next_step"]
    assert ensure_pause_called is False
    assert "ensure_pause" not in result
    assert any(
        name == "stale_bridge_heartbeat"
        and payload["status"] == "BLOCKED"
        and payload["stop_token"] == token
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_on_solver_timeout_nested_in_segment():
    session = SimpleNamespace(
        run_id="20260606_111115_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Artillery",
        mission_index=2,
        islands_completed=[],
    )
    calls: list[str] = []

    def segment(*_args, **_kwargs):
        calls.append("segment")
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "steps": [
                {
                    "action": "combat_loop",
                    "combat_loop": {
                        "turns": [
                            {
                                "warning": (
                                    "Solver returned empty solution "
                                    "(timeout or no valid actions)"
                                )
                            }
                        ]
                    },
                }
            ],
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "solver_or_combat_timeout"
    assert result["timeout_evidence"]["kind"] == "solver_timeout"
    assert "fresh read plus solve" in result["next_step"]
    assert calls == ["segment"]


def test_runner_blocks_on_external_prompt_nested_in_segment():
    session = SimpleNamespace(
        run_id="20260606_111115_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Artillery",
        mission_index=2,
        islands_completed=[],
    )
    calls: list[str] = []

    def segment(*_args, **_kwargs):
        calls.append("segment")
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "panel_ready",
            "steps": [
                {
                    "status": "BLOCKED",
                    "reason": "external_system_prompt_visible",
                    "visible_ui": {
                        "status": "OK",
                        "visible_ui": "system_privacy_prompt",
                        "screenshot_path": "/tmp/segment_system_prompt.png",
                    },
                }
            ],
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "external_system_prompt_visible"
    assert result["external_prompt_evidence"]["path"] == "steps.0.visible_ui"
    assert result["external_prompt_evidence"]["visible_name"] == "system_privacy_prompt"
    assert result["external_prompt_evidence"]["visible_ui"]["screenshot_path"] == (
        "/tmp/segment_system_prompt.png"
    )
    assert result["segment"]["steps"][0]["visible_ui"]["screenshot_path"] == (
        "/tmp/segment_system_prompt.png"
    )
    assert "Allow button" in result["next_step"]
    assert result["system_prompt_allow"]["status"] != "OK"
    assert result["system_prompt_allow"]["status"] != "OK"
    assert calls == ["segment"]


def test_runner_blocks_on_external_prompt_authorization_flag_nested_in_segment():
    session = SimpleNamespace(
        run_id="20260606_111115_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Artillery",
        mission_index=2,
        islands_completed=[],
    )
    ui_calls: list[str] = []

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        ui_calls.append(str(control))
        if control == "classify":
            return pause_menu()
        raise AssertionError("external prompt evidence should stop before UI clicks")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "panel_ready",
            "steps": [
                {
                    "status": "BLOCKED",
                    "message": "A macOS privacy prompt is covering the game",
                    "visible_ui": {
                        "status": "OK",
                        "requires_user_authorization": True,
                        "screenshot_path": "/tmp/segment_prompt_flag.png",
                        "external_prompt": {
                            "matched": True,
                            "kind": "macos_screen_audio_privacy_prompt",
                            "regions": [{"x": 10, "y": 20}],
                        },
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "external_system_prompt_visible"
    assert result["external_prompt_evidence"]["path"] == "steps.0.visible_ui"
    assert result["external_prompt_evidence"]["requires_user_authorization"] is True
    assert result["external_prompt_evidence"]["external_prompt"] == {
        "matched": True,
        "kind": "macos_screen_audio_privacy_prompt",
    }
    assert result["external_prompt_evidence"]["visible_ui"]["screenshot_path"] == (
        "/tmp/segment_prompt_flag.png"
    )
    assert "regions" not in result["external_prompt_evidence"]["external_prompt"]
    assert "Allow button" in result["next_step"]
    assert result["system_prompt_allow"]["status"] != "OK"
    assert ui_calls == ["classify"]


def test_runner_blocks_on_nested_reload_main_menu_evidence():
    session = SimpleNamespace(
        run_id="20260606_111117_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Artillery",
        mission_index=2,
        islands_completed=[],
    )
    calls: list[str] = []

    def segment(*_args, **_kwargs):
        calls.append("segment")
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "visible_ui": {
                "status": "OK",
                "visible_ui": "title_screen",
                "screenshot_path": "/tmp/reloaded_title.png",
            },
            "steps": [
                {
                    "action": "visible_ui_snapshot",
                    "visible_ui": {
                        "status": "OK",
                        "visible_ui": "title_screen",
                        "screenshot_path": "/tmp/reloaded_title.png",
                    },
                }
            ],
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "reload_or_main_menu_visible"
    assert result["menu_evidence"]["visible_name"] == "title_screen"
    assert result["menu_evidence"]["path"] == "visible_ui.visible_ui"
    assert "Inspect the visible screen" in result["next_step"]
    assert "Do not trust stale session progress" in result["next_step"]
    assert "fresh read plus solve" in result["next_step"]
    assert "fresh setup verification" in result["next_step"]
    assert calls == ["segment"]


def test_runner_blocks_on_terminal_evidence_nested_in_segment():
    session = SimpleNamespace(
        run_id="20260606_111117_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Train",
        mission_index=2,
        islands_completed=[],
    )
    ui_calls: list[str] = []

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        ui_calls.append(str(control))
        if control == "classify":
            return pause_menu()
        raise AssertionError("terminal segment evidence should stop before UI clicks")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "steps": [
                {
                    "action": "combat_loop",
                    "visible_ui": {
                        "status": "OK",
                        "visible_ui": "reward_panel",
                        "visible_text": "Region Secured\nKIA",
                        "screenshot_path": "/tmp/nested_kia_reward.png",
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
    )

    runner = make_runner()
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "terminal_outcome_visible"
    assert result["terminal_evidence"] == {
        "kind": "terminal_text",
        "path": "steps.0.visible_ui.visible_text",
        "phrase": "kia",
        "text": "Region Secured\nKIA",
    }
    assert result["segment"]["steps"][0]["visible_ui"]["screenshot_path"] == (
        "/tmp/nested_kia_reward.png"
    )
    assert "syncing achievements" in result["next_step"]
    assert ui_calls == ["classify"]
    assert any(
        name == "terminal_outcome_visible"
        and payload["terminal_evidence"]["path"] == "steps.0.visible_ui.visible_text"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_on_killed_in_action_reward_text_nested_in_segment():
    session = SimpleNamespace(
        run_id="20260606_111117_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Train",
        mission_index=2,
        islands_completed=[],
    )
    ui_calls: list[str] = []

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        ui_calls.append(str(control))
        if control == "classify":
            return pause_menu()
        raise AssertionError("terminal segment evidence should stop before UI clicks")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "steps": [
                {
                    "action": "combat_loop",
                    "visible_ui": {
                        "status": "OK",
                        "visible_ui": "reward_panel",
                        "visible_text": "Region Secured\nKilled in Action",
                        "screenshot_path": "/tmp/nested_killed_in_action_reward.png",
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "terminal_outcome_visible"
    assert result["terminal_evidence"] == {
        "kind": "terminal_text",
        "path": "steps.0.visible_ui.visible_text",
        "phrase": "killed in action",
        "text": "Region Secured\nKilled in Action",
    }
    assert result["segment"]["steps"][0]["visible_ui"]["screenshot_path"] == (
        "/tmp/nested_killed_in_action_reward.png"
    )
    assert "syncing achievements" in result["next_step"]
    assert ui_calls == ["classify"]


def test_runner_blocks_on_string_terminal_flag_nested_in_segment():
    session = SimpleNamespace(
        run_id="20260606_111117_003b",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Train",
        mission_index=2,
        islands_completed=[],
    )
    ui_calls: list[str] = []

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        ui_calls.append(str(control))
        if control == "classify":
            return pause_menu()
        raise AssertionError("terminal segment evidence should stop before UI clicks")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "steps": [
                {
                    "action": "combat_loop",
                    "visible_ui": {
                        "status": "OK",
                        "visible_ui": "reward_panel",
                        "terminal_outcome": "Killed in Action",
                        "screenshot_path": "/tmp/nested_terminal_flag_reward.png",
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "terminal_outcome_visible"
    assert result["terminal_evidence"] == {
        "kind": "terminal_flag",
        "path": "steps.0.visible_ui.terminal_outcome",
        "flag": "terminal_outcome",
        "value": "Killed in Action",
        "phrase": "killed in action",
    }
    assert result["segment"]["steps"][0]["visible_ui"]["screenshot_path"] == (
        "/tmp/nested_terminal_flag_reward.png"
    )
    assert ui_calls == ["classify"]


def test_runner_preserves_segment_stop_when_stop_telemetry_events_raise():
    session = SimpleNamespace(
        run_id="20260606_111117_004",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Train",
        mission_index=2,
        islands_completed=[],
    )

    class SegmentStopTelemetryRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name in {"segment_result", "terminal_outcome_visible"}:
                raise RuntimeError(f"{name} write crashed")
            super().event(name, **payload)

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "steps": [
                {
                    "action": "combat_loop",
                    "visible_ui": {
                        "status": "OK",
                        "visible_ui": "reward_panel",
                        "visible_text": "Region Secured\nKIA",
                        "screenshot_path": "/tmp/nested_kia_reward.png",
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
    )

    runner = make_runner()
    runner.telemetry = SegmentStopTelemetryRaises()
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "terminal_outcome_visible"
    assert result["terminal_evidence"]["path"] == "steps.0.visible_ui.visible_text"
    errors = result["telemetry_event_errors"]
    assert errors[0] == {
        "event_name": "terminal_outcome_visible",
        "exception_type": "RuntimeError",
        "error": "terminal_outcome_visible write crashed",
    }
    assert errors[1] == {
        "event_name": "segment_result",
        "exception_type": "RuntimeError",
        "error": "segment_result write crashed",
    }
    assert any(
        name == "runner_finish" and payload["reason"] == "terminal_outcome_visible"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_on_split_failed_objective_nested_in_segment():
    session = SimpleNamespace(
        run_id="20260606_111117_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Train",
        mission_index=2,
        islands_completed=[],
    )

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else unexpected("lightning_ui")(*args, **kwargs),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "steps": [
                {
                    "action": "combat_loop",
                    "visible_ui": {
                        "status": "OK",
                        "visible_ui": "reward_panel",
                        "ocr_texts": [
                            "Region Secured",
                            "Protect the Train",
                            "FAILED",
                        ],
                        "screenshot_path": "/tmp/nested_failed_objective.png",
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "terminal_outcome_visible"
    assert result["terminal_evidence"]["kind"] == "split_objective_failure_text"
    assert result["terminal_evidence"]["path"] == "steps.0.visible_ui.ocr_texts.2"
    assert result["terminal_evidence"]["context_path"] == (
        "steps.0.visible_ui.ocr_texts.1"
    )
    assert result["terminal_evidence"]["context_text"] == "Protect the Train"


def test_runner_blocks_on_initial_system_privacy_prompt():
    commands = SimpleNamespace(
        cmd_lightning_pause_guard=lambda **_: {
            "status": "BLOCKED",
            "reason": "external_system_prompt_visible",
            "visible_ui": {
                "status": "OK",
                "visible_ui": "system_privacy_prompt",
                "requires_user_authorization": True,
                "screenshot_path": "/tmp/system_prompt.png",
                "external_prompt": {
                    "status": "OK",
                    "matched": True,
                    "score": 1.0,
                    "kind": "macos_screen_audio_privacy_prompt",
                },
            },
        },
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "external_system_prompt_visible"
    assert result["visible_name"] == "system_privacy_prompt"
    assert result["guard"]["visible_ui"]["screenshot_path"] == "/tmp/system_prompt.png"
    assert "Allow button" in result["next_step"]
    assert result["system_prompt_allow"]["status"] != "OK"


def test_runner_blocks_on_initial_system_prompt_nested_in_guard():
    commands = SimpleNamespace(
        cmd_lightning_pause_guard=lambda **_: {
            "status": "BLOCKED",
            "reason": "external_system_prompt_visible",
            "guard": {
                "status": "BLOCKED",
                "visible_ui": {
                    "status": "OK",
                    "visible_ui": "system_privacy_prompt",
                    "screenshot_path": "/tmp/nested_system_prompt.png",
                },
            },
        },
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "external_system_prompt_visible"
    assert result["visible_name"] == "system_privacy_prompt"
    assert result["guard"]["guard"]["visible_ui"]["screenshot_path"] == (
        "/tmp/nested_system_prompt.png"
    )


def test_segment_result_telemetry_keeps_compact_speed_timing():
    session = SimpleNamespace(
        run_id="20260606_111112_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Train",
        mission_index=2,
        islands_completed=[],
    )

    def segment(*args, **kwargs):
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "wall_seconds": 12.34,
            "steps_attempted": 1,
            "steps": [
                {
                    "step": 0,
                    "status": "LIGHTNING_ATTEMPT_STOPPED",
                    "reason": "combat_loop_returned",
                    "action": "combat_loop",
                    "combat_loop_reason": "terminal_or_mission_end",
                    "combat_loop_wall_seconds": 11.7,
                    "combat_turns_attempted": 4,
                    "combat_end_turn_clicks": 3,
                    "combat_turn_timings": [
                        {
                            "loop_index": 1,
                            "turn": 1,
                            "status": "PLAN",
                            "auto_turn_wall_seconds": 1.5,
                            "turn_wall_seconds": 4.1,
                        }
                    ],
                    "quiet_output": "large hidden stdout blob",
                }
            ],
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )
    runner = make_runner(mode="speed")

    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    segment_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "segment_result"
    ]
    assert segment_events
    event = segment_events[0]
    assert event["wall_seconds"] == 12.34
    assert event["steps"][0]["combat_loop_wall_seconds"] == 11.7
    assert event["steps"][0]["combat_turn_timings"][0]["turn"] == 1
    assert "quiet_output" not in event["steps"][0]
    phase_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "speed_phase_timing"
    ]
    assert phase_events
    phase = phase_events[0]
    assert phase["phase"] == "target_complete"
    assert phase["island_number"] == 2
    assert phase["completed_island_count"] == 2
    assert phase["current_mission"] == "Mission_Train"
    assert phase["combat_turns"] == {
        "attempted_turn_count": 4,
        "timed_turn_count": 1,
        "last_turn": 1,
        "end_turn_clicks": 3,
        "turn_wall_seconds_total": 4.1,
    }


def test_speed_phase_timing_survives_segment_result_event_failure():
    session = SimpleNamespace(
        run_id="20260606_111112_004",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Train",
        mission_index=2,
        islands_completed=[],
    )

    class SegmentResultEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "segment_result":
                raise RuntimeError("segment_result write crashed")
            super().event(name, **payload)

    def segment(*args, **kwargs):
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "wall_seconds": 12.34,
            "steps_attempted": 1,
            "steps": [
                {
                    "step": 0,
                    "action": "combat_loop",
                    "combat_turns_attempted": 4,
                    "combat_end_turn_clicks": 3,
                    "combat_turn_timings": [
                        {
                            "loop_index": 1,
                            "turn": 1,
                            "turn_wall_seconds": 4.1,
                        }
                    ],
                }
            ],
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )
    runner = make_runner(mode="speed")
    runner.telemetry = SegmentResultEventRaises()

    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert result["telemetry_event_errors"] == [
        {
            "event_name": "segment_result",
            "exception_type": "RuntimeError",
            "error": "segment_result write crashed",
        }
    ]
    phase_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "speed_phase_timing"
    ]
    assert phase_events
    assert phase_events[0]["phase"] == "target_complete"
    assert phase_events[0]["combat_turns"]["turn_wall_seconds_total"] == 4.1


@pytest.mark.parametrize(
    ("session", "segment", "expected_phase", "expected_island"),
    [
        (
            SimpleNamespace(
                islands_completed=[],
                current_mission="",
                current_island="",
                mission_index=0,
            ),
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "route_ready",
            },
            "route",
            1,
        ),
        (
            SimpleNamespace(
                islands_completed=["archive"],
                current_mission="",
                current_island="rst",
                mission_index=4,
            ),
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "max_steps_reached",
                "visible_ui": {
                    "status": "OK",
                    "visible_ui": "island_complete_leave",
                },
            },
            "reward_shop",
            2,
        ),
        (
            SimpleNamespace(
                islands_completed=["archive"],
                current_mission="Mission_Train",
                current_island="rst",
                mission_index=5,
            ),
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "max_steps_reached",
            },
            "mission",
            2,
        ),
        (
            SimpleNamespace(
                islands_completed=["archive"],
                current_mission="",
                current_island="",
                mission_index=4,
            ),
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "max_steps_reached",
            },
            "between_missions",
            2,
        ),
        (
            SimpleNamespace(
                islands_completed=["archive", "rst"],
                current_mission="",
                current_island="rst",
                mission_index=8,
            ),
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "max_steps_reached",
            },
            "target_complete",
            2,
        ),
    ],
)
def test_speed_phase_label_covers_timing_buckets(
    session,
    segment,
    expected_phase,
    expected_island,
):
    assert (
        lightning_runner._speed_phase_label(
            session,
            segment,
            target_islands=2,
        )
        == expected_phase
    )
    assert (
        lightning_runner._speed_island_number(
            session,
            target_islands=2,
        )
        == expected_island
    )


def test_runner_run_returns_blocked_result_on_helper_exception(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_111112_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    created_telemetry: list[FakeTelemetry] = []

    def fake_telemetry(_run_id):
        telemetry = FakeTelemetry()
        created_telemetry.append(telemetry)
        return telemetry

    def exploding_guard(**_):
        raise RuntimeError("bridge helper crashed")

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    monkeypatch.setattr(lightning_runner, "_load_current_session", lambda _commands: session)
    monkeypatch.setattr(loop_commands, "cmd_lightning_pause_guard", exploding_guard)

    runner = LightningWarRunner(
        LightningRunnerConfig(screenshots=False, achievement_sync=False)
    )
    result = runner.run()

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "pause_guard_initial_exception"
    assert result["span"] == "pause_guard_initial"
    assert result["exception_type"] == "RuntimeError"
    assert "bridge helper crashed" in result["traceback"]
    assert any(name == "runner_finish" for name, _ in created_telemetry[0].events)
    assert any(
        name == "pause_guard_initial_exception"
        and payload["error"] == "bridge helper crashed"
        for name, payload in created_telemetry[0].events
    )


def test_runner_run_blocks_when_initial_session_load_raises(monkeypatch):
    created_telemetry: list[FakeTelemetry] = []

    def fake_telemetry(_run_id):
        telemetry = FakeTelemetry()
        created_telemetry.append(telemetry)
        return telemetry

    def load_session(_commands):
        raise RuntimeError("session reader crashed")

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    monkeypatch.setattr(lightning_runner, "_load_current_session", load_session)

    runner = LightningWarRunner(
        LightningRunnerConfig(screenshots=False, achievement_sync=False)
    )
    result = runner.run()

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "session_load_exception"
    assert result["session_load"]["stage"] == "run_start"
    assert result["session_load"]["exception_type"] == "RuntimeError"
    assert result["session_load"]["error"] == "session reader crashed"
    assert "session reader crashed" in result["session_load"]["traceback"]
    assert created_telemetry[0].manifests[0]["squad"] is None
    assert any(
        name == "session_load_exception"
        and payload["stage"] == "run_start"
        and payload["error"] == "session reader crashed"
        for name, payload in created_telemetry[0].events
    )
    assert any(name == "summary" for name, _payload in created_telemetry[0].events)


def test_runner_blocks_before_live_actions_when_telemetry_start_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_111112_006",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )

    def exploding_telemetry(_run_id):
        raise RuntimeError("telemetry path crashed")

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", exploding_telemetry)
    monkeypatch.setattr(lightning_runner, "_load_current_session", lambda _commands: session)
    monkeypatch.setattr(LightningWarRunner, "_run_inner", unexpected("_run_inner"))

    runner = LightningWarRunner(
        LightningRunnerConfig(screenshots=False, achievement_sync=False)
    )
    result = runner.run()

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "telemetry_start_exception"
    assert result["telemetry_run_id"] == "20260606_111112_006"
    assert result["exception_type"] == "RuntimeError"
    assert result["error"] == "telemetry path crashed"
    assert "telemetry path crashed" in result["traceback"]


def test_runner_blocks_before_live_actions_when_screenshot_start_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_111112_006",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    created_telemetry: list[FakeTelemetry] = []

    class ExplodingStartScreenshotRecorder:
        def __init__(self, *_args, **_kwargs):
            pass

        def start(self):
            raise RuntimeError("screenshot start crashed")

        def stop(self):
            raise AssertionError("stop should not run after start failure")

    def fake_telemetry(_run_id):
        telemetry = FakeTelemetry()
        created_telemetry.append(telemetry)
        return telemetry

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    monkeypatch.setattr(
        lightning_runner,
        "ScreenshotRecorder",
        ExplodingStartScreenshotRecorder,
    )
    monkeypatch.setattr(lightning_runner, "_load_current_session", lambda _commands: session)
    monkeypatch.setattr(LightningWarRunner, "_run_inner", unexpected("_run_inner"))

    runner = LightningWarRunner(
        LightningRunnerConfig(screenshots=True, achievement_sync=False)
    )
    result = runner.run()

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "screenshot_start_exception"
    assert result["span"] == "screenshot_start"
    assert result["exception_type"] == "RuntimeError"
    assert result["error"] == "screenshot start crashed"
    telemetry = created_telemetry[0]
    assert any(
        name == "screenshot_start_exception"
        and payload["error"] == "screenshot start crashed"
        for name, payload in telemetry.events
    )
    assert any(name == "runner_finish" for name, _payload in telemetry.events)
    assert any(
        name == "frame_delta_report"
        and payload["status"] == "SKIPPED"
        and payload["reason"] == "unsafe_to_generate_frame_deltas"
        for name, payload in telemetry.events
    )
    assert any(name == "summary" for name, _payload in telemetry.events)


def test_runner_preserves_result_when_frame_delta_report_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_111112_007",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=8,
        islands_completed=["archive", "rst"],
    )
    created_telemetry: list[FakeTelemetry] = []

    def fake_telemetry(_run_id):
        telemetry = FakeTelemetry()
        created_telemetry.append(telemetry)
        return telemetry

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    monkeypatch.setattr(lightning_runner, "_load_current_session", lambda _commands: session)
    monkeypatch.setattr(
        LightningWarRunner,
        "_run_inner",
        lambda self, commands: {
            "status": "SUCCESS",
            "reason": "target_islands_completed",
        },
    )

    def frame_report(_run_dir):
        raise RuntimeError("frame report crashed")

    monkeypatch.setattr(lightning_runner, "generate_frame_delta_report", frame_report)

    runner = LightningWarRunner(
        LightningRunnerConfig(screenshots=False, achievement_sync=False)
    )
    result = runner.run()

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    frame_events = [
        payload
        for name, payload in created_telemetry[0].events
        if name == "frame_delta_report"
    ]
    assert frame_events[-1]["status"] == "ERROR"
    assert frame_events[-1]["reason"] == "frame_delta_report_exception"
    assert frame_events[-1]["error"] == "frame report crashed"
    assert any(
        name == "summary" and payload["extra"]["frame_report"] == "ERROR"
        for name, payload in created_telemetry[0].events
    )


def test_runner_preserves_result_when_frame_delta_event_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_111112_017",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=8,
        islands_completed=["archive", "rst"],
    )
    created_telemetry: list[FakeTelemetry] = []

    class FrameEventRaisesTelemetry(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "frame_delta_report":
                raise RuntimeError("frame event write crashed")
            super().event(name, **payload)

    def fake_telemetry(_run_id):
        telemetry = FrameEventRaisesTelemetry()
        created_telemetry.append(telemetry)
        return telemetry

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    monkeypatch.setattr(lightning_runner, "_load_current_session", lambda _commands: session)
    monkeypatch.setattr(
        LightningWarRunner,
        "_run_inner",
        lambda self, commands: {
            "status": "SUCCESS",
            "reason": "target_islands_completed",
        },
    )
    monkeypatch.setattr(
        lightning_runner,
        "generate_frame_delta_report",
        lambda _run_dir: {"status": "OK"},
    )

    runner = LightningWarRunner(
        LightningRunnerConfig(screenshots=False, achievement_sync=False)
    )
    result = runner.run()

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    summary_events = [
        payload for name, payload in created_telemetry[0].events if name == "summary"
    ]
    assert summary_events[-1]["extra"]["frame_report"] == "OK"
    assert (
        summary_events[-1]["extra"]["frame_report_event_exception_type"]
        == "RuntimeError"
    )
    assert (
        summary_events[-1]["extra"]["frame_report_event_error"]
        == "frame event write crashed"
    )


def test_runner_preserves_result_when_summary_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_111112_018",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=8,
        islands_completed=["archive", "rst"],
    )
    created_telemetry: list[FakeTelemetry] = []

    class SummaryRaisesTelemetry(FakeTelemetry):
        def summary(self, **payload):
            self.events.append(("summary_attempt", payload))
            raise RuntimeError("summary write crashed")

    def fake_telemetry(_run_id):
        telemetry = SummaryRaisesTelemetry()
        created_telemetry.append(telemetry)
        return telemetry

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    monkeypatch.setattr(lightning_runner, "_load_current_session", lambda _commands: session)
    monkeypatch.setattr(
        LightningWarRunner,
        "_run_inner",
        lambda self, commands: {
            "status": "SUCCESS",
            "reason": "target_islands_completed",
        },
    )
    monkeypatch.setattr(
        lightning_runner,
        "generate_frame_delta_report",
        lambda _run_dir: {"status": "OK"},
    )

    runner = LightningWarRunner(
        LightningRunnerConfig(screenshots=False, achievement_sync=False)
    )
    result = runner.run()

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert any(
        name == "frame_delta_report" and payload["status"] == "OK"
        for name, payload in created_telemetry[0].events
    )
    assert any(name == "summary_attempt" for name, _ in created_telemetry[0].events)


def test_runner_preserves_result_when_runner_finish_event_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_111112_020",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=8,
        islands_completed=["archive", "rst"],
    )
    created_telemetry: list[FakeTelemetry] = []

    class FinishEventRaisesTelemetry(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "runner_finish":
                raise RuntimeError("runner finish write crashed")
            super().event(name, **payload)

    def fake_telemetry(_run_id):
        telemetry = FinishEventRaisesTelemetry()
        created_telemetry.append(telemetry)
        return telemetry

    def run_inner(self, commands):
        return self._finish(
            "SUCCESS",
            "target_islands_completed",
            islands_completed=["archive", "rst"],
        )

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    monkeypatch.setattr(lightning_runner, "_load_current_session", lambda _commands: session)
    monkeypatch.setattr(LightningWarRunner, "_run_inner", run_inner)
    monkeypatch.setattr(
        lightning_runner,
        "generate_frame_delta_report",
        lambda _run_dir: {"status": "OK"},
    )

    runner = LightningWarRunner(
        LightningRunnerConfig(screenshots=False, achievement_sync=False)
    )
    result = runner.run()

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert result["runner_finish_event_exception_type"] == "RuntimeError"
    assert result["runner_finish_event_error"] == "runner finish write crashed"
    assert any(
        name == "frame_delta_report" and payload["status"] == "OK"
        for name, payload in created_telemetry[0].events
    )
    assert any(name == "summary" for name, _ in created_telemetry[0].events)


def test_runner_preserves_session_load_block_when_final_telemetry_raises(monkeypatch):
    created_telemetry: list[FakeTelemetry] = []

    class FinalTelemetryRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "frame_delta_report":
                raise RuntimeError("frame event write crashed")
            super().event(name, **payload)

        def summary(self, **payload):
            raise RuntimeError("summary write crashed")

    def fake_telemetry(_run_id):
        telemetry = FinalTelemetryRaises()
        created_telemetry.append(telemetry)
        return telemetry

    def load_session(_commands):
        raise RuntimeError("session reader crashed")

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    monkeypatch.setattr(lightning_runner, "_load_current_session", load_session)

    runner = LightningWarRunner(
        LightningRunnerConfig(screenshots=False, achievement_sync=False)
    )
    result = runner.run()

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "session_load_exception"
    assert result["session_load"]["error"] == "session reader crashed"
    assert any(
        name == "runner_finish" and payload["reason"] == "session_load_exception"
        for name, payload in created_telemetry[0].events
    )


def test_runner_preserves_startup_session_load_block_when_event_write_raises(monkeypatch):
    created_telemetry: list[FakeTelemetry] = []

    class SessionLoadEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "session_load_exception":
                raise RuntimeError("session load event write crashed")
            super().event(name, **payload)

    def fake_telemetry(_run_id):
        telemetry = SessionLoadEventRaises()
        created_telemetry.append(telemetry)
        return telemetry

    def load_session(_commands):
        raise RuntimeError("startup session reader crashed")

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    monkeypatch.setattr(lightning_runner, "_load_current_session", load_session)

    runner = LightningWarRunner(
        LightningRunnerConfig(screenshots=False, achievement_sync=False)
    )
    result = runner.run()

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "session_load_exception"
    assert result["session_load"]["error"] == "startup session reader crashed"
    assert result["session_load"]["telemetry_event_errors"] == [
        {
            "event_name": "session_load_exception",
            "exception_type": "RuntimeError",
            "error": "session load event write crashed",
        }
    ]
    assert any(
        name == "runner_finish" and payload["reason"] == "session_load_exception"
        for name, payload in created_telemetry[0].events
    )
    assert not any(
        name == "runner_finish" and payload["reason"] == "runner_exception"
        for name, payload in created_telemetry[0].events
    )


def test_runner_preserves_result_when_final_screenshot_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_111112_008",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=8,
        islands_completed=["archive", "rst"],
    )
    created_telemetry: list[FakeTelemetry] = []

    class ExplodingScreenshotRecorder:
        def __init__(self, *_args, **_kwargs):
            pass

        def start(self):
            pass

        def stop(self):
            raise RuntimeError("screenshot stop crashed")

        def capture_once(self, **_kwargs):
            raise AssertionError("capture_once should not run after stop crash")

    def fake_telemetry(_run_id):
        telemetry = FakeTelemetry()
        created_telemetry.append(telemetry)
        return telemetry

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    monkeypatch.setattr(
        lightning_runner,
        "ScreenshotRecorder",
        ExplodingScreenshotRecorder,
    )
    monkeypatch.setattr(lightning_runner, "_load_current_session", lambda _commands: session)
    monkeypatch.setattr(
        LightningWarRunner,
        "_run_inner",
        lambda self, commands: {
            "status": "SUCCESS",
            "reason": "target_islands_completed",
        },
    )
    monkeypatch.setattr(
        lightning_runner,
        "generate_frame_delta_report",
        lambda _run_dir: {"status": "OK"},
    )

    runner = LightningWarRunner(
        LightningRunnerConfig(screenshots=True, achievement_sync=False)
    )
    result = runner.run()

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert any(
        name == "screenshot_finalization_exception"
        and payload["error"] == "screenshot stop crashed"
        for name, payload in created_telemetry[0].events
    )
    assert any(
        name == "frame_delta_report" and payload["status"] == "OK"
        for name, payload in created_telemetry[0].events
    )


def test_runner_preserves_result_when_screenshot_exception_event_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_111112_019",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=8,
        islands_completed=["archive", "rst"],
    )
    created_telemetry: list[FakeTelemetry] = []

    class ExplodingScreenshotRecorder:
        def __init__(self, *_args, **_kwargs):
            pass

        def start(self):
            pass

        def stop(self):
            raise RuntimeError("screenshot stop crashed")

        def capture_once(self, **_kwargs):
            raise AssertionError("capture_once should not run after stop crash")

    class ScreenshotEventRaisesTelemetry(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "screenshot_finalization_exception":
                raise RuntimeError("screenshot event write crashed")
            super().event(name, **payload)

    def fake_telemetry(_run_id):
        telemetry = ScreenshotEventRaisesTelemetry()
        created_telemetry.append(telemetry)
        return telemetry

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    monkeypatch.setattr(
        lightning_runner,
        "ScreenshotRecorder",
        ExplodingScreenshotRecorder,
    )
    monkeypatch.setattr(lightning_runner, "_load_current_session", lambda _commands: session)
    monkeypatch.setattr(
        LightningWarRunner,
        "_run_inner",
        lambda self, commands: {
            "status": "SUCCESS",
            "reason": "target_islands_completed",
        },
    )
    monkeypatch.setattr(
        lightning_runner,
        "generate_frame_delta_report",
        lambda _run_dir: {"status": "OK"},
    )

    runner = LightningWarRunner(
        LightningRunnerConfig(screenshots=True, achievement_sync=False)
    )
    result = runner.run()

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert any(
        name == "frame_delta_report" and payload["status"] == "OK"
        for name, payload in created_telemetry[0].events
    )


def test_telemetry_rehome_keeps_old_recorder_when_screenshot_stop_raises():
    session = SimpleNamespace(
        run_id="20260606_222222_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )

    class ExplodingScreenshots:
        def stop(self):
            raise RuntimeError("old screenshot stop crashed")

    commands = SimpleNamespace(_load_session=lambda: session)
    runner = make_runner(screenshots=True)
    old_telemetry = runner.telemetry
    old_telemetry.run_id = "old_run"
    runner.screenshots = ExplodingScreenshots()

    runner._rehome_telemetry_if_session_changed(commands, reason="test_rehome")

    assert runner.telemetry is old_telemetry
    assert runner.screenshots is not None
    assert any(
        name == "telemetry_rehome_exception"
        and payload["old_run_id"] == "old_run"
        and payload["new_run_id"] == "20260606_222222_001"
        and payload["error"] == "old screenshot stop crashed"
        for name, payload in old_telemetry.events
    )


def test_telemetry_rehome_keeps_old_recorder_when_new_recorder_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_222222_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )

    def exploding_telemetry(_run_id):
        raise RuntimeError("new telemetry crashed")

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", exploding_telemetry)
    commands = SimpleNamespace(_load_session=lambda: session)
    runner = make_runner(screenshots=False)
    old_telemetry = runner.telemetry
    old_telemetry.run_id = "old_run"

    runner._rehome_telemetry_if_session_changed(commands, reason="test_rehome")

    assert runner.telemetry is old_telemetry
    assert any(
        name == "telemetry_rehome_exception"
        and payload["old_run_id"] == "old_run"
        and payload["new_run_id"] == "20260606_222222_002"
        and payload["error"] == "new telemetry crashed"
        for name, payload in old_telemetry.events
    )


def test_telemetry_rehome_preserves_old_recorder_when_exception_event_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_222222_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )

    class RehomeExceptionEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "telemetry_rehome_exception":
                raise RuntimeError("rehome exception event crashed")
            super().event(name, **payload)

    def exploding_telemetry(_run_id):
        raise RuntimeError("new telemetry crashed")

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", exploding_telemetry)
    commands = SimpleNamespace(_load_session=lambda: session)
    runner = make_runner(screenshots=False)
    old_telemetry = RehomeExceptionEventRaises()
    old_telemetry.run_id = "old_run"
    runner.telemetry = old_telemetry

    runner._rehome_telemetry_if_session_changed(commands, reason="test_rehome")

    assert runner.telemetry is old_telemetry
    assert runner.telemetry_event_errors == [
        {
            "event_name": "telemetry_rehome_exception",
            "exception_type": "RuntimeError",
            "error": "rehome exception event crashed",
        }
    ]
    assert any(
        name == "telemetry_rehome"
        and payload["status"] == "REHOMING"
        and payload["new_run_id"] == "20260606_222222_003"
        for name, payload in old_telemetry.events
    )


def test_telemetry_rehome_skipped_event_failure_is_best_effort():
    class RehomeSkippedEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "telemetry_rehome_skipped":
                raise RuntimeError("rehome skipped event crashed")
            super().event(name, **payload)

    def load_session():
        raise RuntimeError("rehome session crashed")

    commands = SimpleNamespace(_load_session=load_session)
    runner = make_runner(screenshots=False)
    runner.telemetry = RehomeSkippedEventRaises()

    runner._rehome_telemetry_if_session_changed(commands, reason="test_rehome")

    assert runner.telemetry_event_errors == [
        {
            "event_name": "telemetry_rehome_skipped",
            "exception_type": "RuntimeError",
            "error": "rehome skipped event crashed",
        }
    ]
    assert any(
        name == "session_load_exception"
        and payload["stage"] == "telemetry_rehome"
        and payload["error"] == "rehome session crashed"
        for name, payload in runner.telemetry.events
    )


def test_telemetry_rehome_succeeds_when_old_rehoming_event_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_222222_004",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    created_telemetry: list[FakeTelemetry] = []

    class OldRehomingEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "telemetry_rehome" and payload.get("status") == "REHOMING":
                raise RuntimeError("old rehome start event crashed")
            super().event(name, **payload)

    def fake_telemetry(_run_id):
        telemetry = FakeTelemetry()
        created_telemetry.append(telemetry)
        return telemetry

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    commands = SimpleNamespace(_load_session=lambda: session)
    runner = make_runner(screenshots=False)
    old_telemetry = OldRehomingEventRaises()
    old_telemetry.run_id = "old_run"
    runner.telemetry = old_telemetry

    runner._rehome_telemetry_if_session_changed(commands, reason="test_rehome")

    assert runner.telemetry is created_telemetry[0]
    assert runner.telemetry.run_id == "lw_runner_test"
    assert runner.telemetry_event_errors == [
        {
            "event_name": "telemetry_rehome",
            "exception_type": "RuntimeError",
            "error": "old rehome start event crashed",
        }
    ]
    assert any(
        name == "telemetry_rehome"
        and payload["status"] == "OK"
        and payload["previous_run_id"] == "old_run"
        for name, payload in runner.telemetry.events
    )


def test_telemetry_rehome_succeeds_when_old_summary_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_222222_005",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    created_telemetry: list[FakeTelemetry] = []

    class OldSummaryRaises(FakeTelemetry):
        def summary(self, **payload):
            raise RuntimeError("old rehome summary crashed")

    def fake_telemetry(_run_id):
        telemetry = FakeTelemetry()
        created_telemetry.append(telemetry)
        return telemetry

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    commands = SimpleNamespace(_load_session=lambda: session)
    runner = make_runner(screenshots=False)
    old_telemetry = OldSummaryRaises()
    old_telemetry.run_id = "old_run"
    runner.telemetry = old_telemetry

    runner._rehome_telemetry_if_session_changed(commands, reason="test_rehome")

    assert runner.telemetry is created_telemetry[0]
    assert runner.telemetry_event_errors == [
        {
            "event_name": "telemetry_rehome_summary",
            "exception_type": "RuntimeError",
            "error": "old rehome summary crashed",
        }
    ]
    assert any(
        name == "telemetry_rehome" and payload["status"] == "OK"
        for name, payload in runner.telemetry.events
    )


def test_telemetry_rehome_keeps_new_recorder_when_ok_event_raises(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_222222_006",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    created_telemetry: list[FakeTelemetry] = []

    class NewOkEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "telemetry_rehome" and payload.get("status") == "OK":
                raise RuntimeError("new rehome ok event crashed")
            super().event(name, **payload)

    def fake_telemetry(_run_id):
        telemetry = NewOkEventRaises()
        created_telemetry.append(telemetry)
        return telemetry

    monkeypatch.setattr(lightning_runner, "TelemetryRecorder", fake_telemetry)
    commands = SimpleNamespace(_load_session=lambda: session)
    runner = make_runner(screenshots=False)
    old_telemetry = runner.telemetry
    old_telemetry.run_id = "old_run"

    runner._rehome_telemetry_if_session_changed(commands, reason="test_rehome")

    assert runner.telemetry is created_telemetry[0]
    assert runner.telemetry_event_errors == [
        {
            "event_name": "telemetry_rehome",
            "exception_type": "RuntimeError",
            "error": "new rehome ok event crashed",
        }
    ]
    assert any(
        name == "telemetry_rehome"
        and payload["status"] == "REHOMING"
        and payload["new_run_id"] == "20260606_222222_006"
        for name, payload in old_telemetry.events
    )


def test_verify_run_setup_blocks_when_session_load_raises():
    def load_session():
        raise RuntimeError("active session crashed")

    runner = make_runner()

    result = runner._verify_run_setup(SimpleNamespace(_load_session=load_session))

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "session_load_exception"
    assert result["stage"] == "verify_run_setup"
    assert result["error"] == "active session crashed"
    assert "active session crashed" in result["traceback"]
    assert any(
        name == "session_load_exception"
        and payload["stage"] == "verify_run_setup"
        and payload["error"] == "active session crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_promotes_setup_proof_session_load_exception():
    session = SimpleNamespace(
        run_id="20260606_111112_006",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    load_calls = 0

    def load_session():
        nonlocal load_calls
        load_calls += 1
        if load_calls >= 2:
            raise RuntimeError("setup session reload crashed")
        return session

    commands = SimpleNamespace(
        _load_session=load_session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "session_load_exception"
    assert result["session_load"]["stage"] == "verify_run_setup"
    assert result["session_load"]["error"] == "setup session reload crashed"


def test_runner_blocks_when_initial_achievement_sync_raises():
    session = SimpleNamespace(
        run_id="20260606_111112_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )

    def achievements(**_kwargs):
        raise RuntimeError("achievement sync crashed")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_achievements=achievements,
    )
    runner = make_runner(achievement_sync=True)

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "achievement_sync_exception"
    assert result["span"] == "achievements_initial"
    assert result["exception_type"] == "RuntimeError"
    assert result["error"] == "achievement sync crashed"
    assert "achievement sync crashed" in result["traceback"]
    assert any(
        name == "achievement_sync_exception"
        and payload["span"] == "achievements_initial"
        and payload["error"] == "achievement sync crashed"
        for name, payload in runner.telemetry.events
    )


def test_run_preflight_blocks_when_helper_raises():
    def preflight(**_kwargs):
        raise RuntimeError("preflight crashed")

    commands = SimpleNamespace(cmd_lightning_preflight=preflight)
    runner = make_runner()

    result = runner._run_preflight(commands, label="preflight_segment_3")

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "preflight_exception"
    assert result["span"] == "preflight_segment_3"
    assert result["exception_type"] == "RuntimeError"
    assert result["error"] == "preflight crashed"
    assert "preflight crashed" in result["traceback"]
    assert any(
        name == "preflight_exception"
        and payload["span"] == "preflight_segment_3"
        and payload["error"] == "preflight crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_when_lightning_segment_raises():
    session = SimpleNamespace(
        run_id="20260606_111112_004",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )

    def segment(**_kwargs):
        raise RuntimeError("segment helper crashed")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "lightning_segment_exception"
    assert result["span"] == "lightning_segment"
    assert result["segment_index"] == 1
    assert result["attempt_index"] == 1
    assert result["exception_type"] == "RuntimeError"
    assert result["error"] == "segment helper crashed"
    assert "segment helper crashed" in result["traceback"]
    assert any(
        name == "lightning_segment_exception"
        and payload["segment_index"] == 1
        and payload["error"] == "segment helper crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_when_session_load_raises_after_segment():
    session = SimpleNamespace(
        run_id="20260606_111112_005",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    load_calls = 0

    def load_session():
        nonlocal load_calls
        load_calls += 1
        if load_calls >= 5:
            raise RuntimeError("session read failed after segment")
        return session

    commands = SimpleNamespace(
        _load_session=load_session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        },
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "session_load_exception"
    assert result["session_load"]["stage"] == "after_lightning_segment"
    assert result["session_load"]["error"] == "session read failed after segment"
    assert result["session_load"]["context"]["segment_index"] == 1
    assert "segment" in result
    assert any(
        name == "session_load_exception"
        and payload["stage"] == "record_segment_result"
        for name, payload in runner.telemetry.events
    )
    assert any(
        name == "session_load_exception"
        and payload["stage"] == "after_lightning_segment"
        for name, payload in runner.telemetry.events
    )


def test_runner_promotes_terminal_segment_before_after_segment_session_read():
    session = SimpleNamespace(
        run_id="20260606_111112_015",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    load_calls = 0

    def load_session():
        nonlocal load_calls
        load_calls += 1
        if load_calls >= 6:
            raise RuntimeError("post-terminal session read crashed")
        return session

    commands = SimpleNamespace(
        _load_session=load_session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "steps": [
                {
                    "action": "combat_loop",
                    "visible_ui": {
                        "status": "OK",
                        "visible_ui": "reward_panel",
                        "visible_text": "Timeline Lost",
                        "screenshot_path": "/tmp/timeline_lost_before_session.png",
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "terminal_outcome_visible"
    assert result["terminal_evidence"] == {
        "kind": "terminal_text",
        "path": "steps.0.visible_ui.visible_text",
        "phrase": "timeline lost",
        "text": "Timeline Lost",
    }
    assert load_calls == 5
    assert not any(
        name == "session_load_exception"
        and payload["stage"] == "after_lightning_segment"
        for name, payload in runner.telemetry.events
    )


@pytest.mark.parametrize(
    ("segment", "expected_reason"),
    [
        (
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "combat_loop_returned",
                "steps": [
                    {
                        "action": "combat_loop",
                        "combat_loop": {
                            "turns": [
                                {
                                    "error": (
                                        "Bridge heartbeat stale after 20s "
                                        "-- Lua stopped ticking"
                                    )
                                }
                            ]
                        },
                    }
                ],
                "pause_guard": pause_menu(),
            },
            "stale_bridge_heartbeat",
        ),
        (
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "combat_loop_returned",
                "steps": [
                    {
                        "action": "combat_loop",
                        "combat_loop": {
                            "turns": [
                                {
                                    "status": "BLOCKED",
                                    "reason": "RESEARCH_REQUIRED",
                                }
                            ]
                        },
                    }
                ],
                "pause_guard": pause_menu(),
            },
            "research_required",
        ),
        (
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "combat_loop_returned",
                "steps": [
                    {
                        "action": "combat_loop",
                        "combat_loop": {
                            "turns": [
                                {
                                    "status": "BLOCKED",
                                    "reason": "DESYNC",
                                }
                            ]
                        },
                    }
                ],
                "pause_guard": pause_menu(),
            },
            "combat_desync",
        ),
        (
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "combat_loop_returned",
                "steps": [
                    {
                        "action": "combat_loop",
                        "combat_loop": {
                            "turns": [
                                {
                                    "warning": (
                                        "Solver returned empty solution "
                                        "(timeout or no valid actions)"
                                    )
                                }
                            ]
                        },
                    }
                ],
                "pause_guard": pause_menu(),
            },
            "solver_or_combat_timeout",
        ),
        (
            {
                "status": "ERROR",
                "reason": "helper_failed",
                "message": "lower helper failed",
            },
            "segment_failed",
        ),
    ],
)
def test_runner_promotes_segment_stop_before_after_segment_session_read(
    segment,
    expected_reason,
):
    session = SimpleNamespace(
        run_id="20260606_111112_016",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    load_calls = 0

    def load_session():
        nonlocal load_calls
        load_calls += 1
        if load_calls >= 6:
            raise RuntimeError("post-stop session read crashed")
        return session

    commands = SimpleNamespace(
        _load_session=load_session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: segment,
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == expected_reason
    assert load_calls == 5
    assert not any(
        name == "session_load_exception"
        and payload["stage"] == "after_lightning_segment"
        for name, payload in runner.telemetry.events
    )


def test_speed_mode_blocks_on_first_island_pace_gate():
    session = SimpleNamespace(
        run_id="20260606_111113_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=2,
        islands_completed=[],
    )
    segment_called = False

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_with_timer(901.0),
        cmd_lightning_segment=segment,
    )

    runner = make_runner(
        mode="speed",
        first_island_gate_seconds=900.0,
        max_attempts=1,
    )

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "mission_segment_pace_gate"
    assert result["pace_gate"]["game_seconds"] == 901.0
    assert any(
        name == "pace_gate" and payload["reason"] == "mission_segment_pace_gate"
        for name, payload in runner.telemetry.events
    )
    assert segment_called is False


def test_speed_mode_second_island_gate_allows_started_mission():
    session = SimpleNamespace(
        run_id="20260606_111114_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="Mission_Train",
        mission_index=5,
        islands_completed=["archive"],
    )
    segment_kwargs: list[dict] = []

    def segment(*args, **kwargs):
        segment_kwargs.append(kwargs)
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_with_timer(1006.0),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner(mode="speed", second_island_start_gate_seconds=1005.0)._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert segment_kwargs


def test_speed_mode_blocks_when_second_island_not_started_by_gate():
    session = SimpleNamespace(
        run_id="20260606_111115_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="",
        current_mission="",
        mission_index=4,
        islands_completed=["archive"],
    )
    segment_called = False

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_with_timer(1006.0),
        cmd_lightning_segment=segment,
    )
    runner = make_runner(mode="speed", second_island_start_gate_seconds=1005.0)

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "second_island_start_pace_gate"
    assert segment_called is False


def test_runner_buys_grid_before_leaving_island(monkeypatch):
    controls: list[str] = []
    grid = {"value": 5}
    classify_count = 0
    session = SimpleNamespace(
        run_id="20260606_121212_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=4,
        islands_completed=["archive"],
    )

    def fake_load_game_state(_profile):
        return SimpleNamespace(
            difficulty=0,
            grid_power=grid["value"],
            grid_power_max=7,
            mechs=["ElectricMech", "WallMech", "RockartMech"],
            weapons=["Prime_Lightning", "Brute_Grapple", "Ranged_Rockthrow"],
        )

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify":
            classify_count += 1
            if classify_count < 3:
                return {"status": "OK", "visible_ui": "island_complete_leave"}
            return {"status": "OK", "visible_ui": "island_map"}
        if control == "shop_grid_power":
            grid["value"] += 1
        if control == "leave_confirm_yes":
            session.islands_completed = ["archive", "rst"]
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        },
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert controls[:9] == [
        "classify",
        "spend_reputation",
        "shop_grid_power",
        "shop_grid_power",
        "shop_continue",
        "classify",
        "leave_island",
        "leave_confirm_yes",
        "classify",
    ]


def test_runner_blocks_if_grid_purchase_click_raises(monkeypatch):
    grid = {"value": 6}
    session = SimpleNamespace(
        run_id="20260606_121212_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=4,
        islands_completed=["archive"],
    )

    def fake_load_game_state(_profile):
        return SimpleNamespace(
            difficulty=0,
            grid_power=grid["value"],
            grid_power_max=7,
            mechs=["ElectricMech", "WallMech", "RockartMech"],
            weapons=["Prime_Lightning", "Brute_Grapple", "Ranged_Rockthrow"],
        )

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify":
            return {"status": "OK", "visible_ui": "island_complete_leave"}
        if control == "shop_grid_power":
            raise RuntimeError("grid click crashed")
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=unexpected("cmd_lightning_segment"),
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_handling_failed"
    assert result["panel"]["reason"] == "shop_grid_power_click_exception"
    assert result["panel"]["exception_evidence"]["span"] == "shop_buy_grid_power"
    assert result["panel"]["exception_evidence"]["error"] == "grid click crashed"
    assert result["panel"]["grid_state"]["grid_power"] == 6
    assert result["panel"]["steps"][-1]["control"] == "shop_grid_power"
    assert result["panel"]["steps"][-1]["result"]["exception_type"] == "RuntimeError"
    assert any(
        name == "shop_grid_power_click_exception"
        and payload["exception_evidence"]["error"] == "grid click crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_if_grid_state_reader_raises_before_shop(monkeypatch):
    load_calls = 0
    session = SimpleNamespace(
        run_id="20260606_121212_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=4,
        islands_completed=["archive"],
    )

    def fake_load_game_state(_profile):
        nonlocal load_calls
        load_calls += 1
        if load_calls == 1:
            return SimpleNamespace(
                difficulty=0,
                grid_power=7,
                grid_power_max=7,
                mechs=["ElectricMech", "WallMech", "RockartMech"],
                weapons=["Prime_Lightning", "Brute_Grapple", "Ranged_Rockthrow"],
            )
        raise RuntimeError("save parser crashed")

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: {
            "status": "OK",
            "visible_ui": "island_complete_leave",
        },
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=unexpected("cmd_lightning_segment"),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_handling_failed"
    assert result["panel"]["reason"] == "grid_state_unavailable_before_shop"
    assert result["panel"]["grid_state"]["reason"] == "grid_state_reader_exception"
    assert result["panel"]["grid_state"]["error"] == "save parser crashed"
    assert "save parser crashed" in result["panel"]["grid_state"]["traceback"]


def test_runner_blocks_if_shop_continue_does_not_return_to_leave_screen(monkeypatch):
    controls: list[str] = []
    grid = {"value": 6}
    classify_count = 0
    session = SimpleNamespace(
        run_id="20260606_121213_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=4,
        islands_completed=["archive"],
    )

    def fake_load_game_state(_profile):
        return SimpleNamespace(
            difficulty=0,
            grid_power=grid["value"],
            grid_power_max=7,
            mechs=["ElectricMech", "WallMech", "RockartMech"],
            weapons=["Prime_Lightning", "Brute_Grapple", "Ranged_Rockthrow"],
        )

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify":
            classify_count += 1
            if classify_count == 1:
                return {"status": "OK", "visible_ui": "island_complete_leave"}
            return {"status": "OK", "visible_ui": "reward_panel"}
        if control == "shop_grid_power":
            grid["value"] += 1
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        },
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_handling_failed"
    assert result["panel"]["reason"] == "shop_exit_not_at_leave_screen"
    assert result["panel"]["observed_visible_ui"]["visible_ui"] == "reward_panel"
    assert "leave_island" not in controls


def test_runner_propagates_external_prompt_after_shop_continue(monkeypatch):
    grid = {"value": 6}
    classify_count = 0
    session = SimpleNamespace(
        run_id="20260606_121214_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=4,
        islands_completed=["archive"],
    )

    def fake_load_game_state(_profile):
        return SimpleNamespace(
            difficulty=0,
            grid_power=grid["value"],
            grid_power_max=7,
            mechs=["ElectricMech", "WallMech", "RockartMech"],
            weapons=["Prime_Lightning", "Brute_Grapple", "Ranged_Rockthrow"],
        )

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify":
            classify_count += 1
            if classify_count == 1:
                return {"status": "OK", "visible_ui": "island_complete_leave"}
            return {
                "status": "OK",
                "visible_ui": "system_privacy_prompt",
                "screenshot_path": "/tmp/shop_prompt.png",
                "requires_user_authorization": True,
            }
        if control == "shop_grid_power":
            grid["value"] += 1
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        },
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "external_system_prompt_visible"
    assert result["panel"]["reason"] == "external_system_prompt_visible"
    assert result["panel"]["observed_visible_ui"]["screenshot_path"] == "/tmp/shop_prompt.png"


def test_runner_blocks_if_leave_confirm_lands_on_setup(monkeypatch):
    controls: list[str] = []
    classify_count = 0
    session = SimpleNamespace(
        run_id="20260606_121215_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=4,
        islands_completed=["archive"],
    )

    def fake_load_game_state(_profile):
        return SimpleNamespace(
            difficulty=0,
            grid_power=7,
            grid_power_max=7,
            mechs=["ElectricMech", "WallMech", "RockartMech"],
            weapons=["Prime_Lightning", "Brute_Grapple", "Ranged_Rockthrow"],
        )

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify":
            classify_count += 1
            if classify_count == 1:
                return {"status": "OK", "visible_ui": "island_complete_leave"}
            return {"status": "OK", "visible_ui": "new_game_setup"}
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        },
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_handling_failed"
    assert result["panel"]["reason"] == "post_leave_unexpected_terminal_or_menu"
    assert result["panel"]["observed_visible_ui"]["visible_ui"] == "new_game_setup"
    assert controls[:4] == [
        "classify",
        "leave_island",
        "leave_confirm_yes",
        "classify",
    ]


def test_runner_blocks_ambiguous_post_leave_handoff_before_target(monkeypatch):
    controls: list[str] = []
    classify_count = 0
    session = SimpleNamespace(
        run_id="20260606_121215_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=4,
        islands_completed=["archive"],
    )

    def fake_load_game_state(_profile):
        return SimpleNamespace(
            difficulty=0,
            grid_power=7,
            grid_power_max=7,
            mechs=["ElectricMech", "WallMech", "RockartMech"],
            weapons=["Prime_Lightning", "Brute_Grapple", "Ranged_Rockthrow"],
        )

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify":
            classify_count += 1
            if classify_count == 1:
                return {"status": "OK", "visible_ui": "island_complete_leave"}
            return {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "screenshot_path": "/tmp/post_leave_unknown.png",
            }
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        },
    )

    result = make_runner(target_islands=2)._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_handling_failed"
    assert result["panel"]["reason"] == "post_leave_handoff_ambiguous_before_target"
    assert result["panel"]["observed_visible_ui"]["visible_ui"] == "island_map_or_unknown"
    assert result["panel"]["observed_visible_ui"]["screenshot_path"] == (
        "/tmp/post_leave_unknown.png"
    )
    assert controls[:4] == [
        "classify",
        "leave_island",
        "leave_confirm_yes",
        "classify",
    ]


def test_runner_propagates_external_prompt_after_leave_confirm(monkeypatch):
    classify_count = 0
    session = SimpleNamespace(
        run_id="20260606_121216_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=4,
        islands_completed=["archive"],
    )

    def fake_load_game_state(_profile):
        return SimpleNamespace(
            difficulty=0,
            grid_power=7,
            grid_power_max=7,
            mechs=["ElectricMech", "WallMech", "RockartMech"],
            weapons=["Prime_Lightning", "Brute_Grapple", "Ranged_Rockthrow"],
        )

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify":
            classify_count += 1
            if classify_count == 1:
                return {"status": "OK", "visible_ui": "island_complete_leave"}
            return {
                "status": "OK",
                "visible_ui": "system_privacy_prompt",
                "screenshot_path": "/tmp/leave_prompt.png",
                "requires_user_authorization": True,
            }
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        },
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "external_system_prompt_visible"
    assert result["panel"]["reason"] == "external_system_prompt_visible"
    assert result["panel"]["observed_visible_ui"]["screenshot_path"] == "/tmp/leave_prompt.png"


def test_runner_blocks_terminal_evidence_after_leave_confirm(monkeypatch):
    classify_count = 0
    session = SimpleNamespace(
        run_id="20260606_121217_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=4,
        islands_completed=["archive"],
    )

    def fake_load_game_state(_profile):
        return SimpleNamespace(
            difficulty=0,
            grid_power=7,
            grid_power_max=7,
            mechs=["ElectricMech", "WallMech", "RockartMech"],
            weapons=["Prime_Lightning", "Brute_Grapple", "Ranged_Rockthrow"],
        )

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify":
            classify_count += 1
            if classify_count == 1:
                return {"status": "OK", "visible_ui": "island_complete_leave"}
            return {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
                "ocr_text": "Timeline Lost",
                "screenshot_path": "/tmp/post_leave_terminal.png",
            }
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        },
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_handling_failed"
    assert result["panel"]["reason"] == "post_leave_terminal_outcome_visible"
    assert result["panel"]["terminal_evidence"]["phrase"] == "timeline lost"
    assert result["panel"]["terminal_evidence"]["path"] == "ocr_text"
    assert result["panel"]["observed_visible_ui"]["screenshot_path"] == (
        "/tmp/post_leave_terminal.png"
    )


def test_runner_blocks_if_post_leave_classification_raises(monkeypatch):
    classify_count = 0
    session = SimpleNamespace(
        run_id="20260606_121217_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=4,
        islands_completed=["archive"],
    )

    def fake_load_game_state(_profile):
        return SimpleNamespace(
            difficulty=0,
            grid_power=7,
            grid_power_max=7,
            mechs=["ElectricMech", "WallMech", "RockartMech"],
            weapons=["Prime_Lightning", "Brute_Grapple", "Ranged_Rockthrow"],
        )

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify":
            classify_count += 1
            if classify_count == 1:
                return {"status": "OK", "visible_ui": "island_complete_leave"}
            raise RuntimeError("post-leave classify crashed")
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=unexpected("cmd_lightning_segment"),
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_handling_failed"
    assert result["panel"]["reason"] == "post_leave_classification_exception"
    assert result["panel"]["exception_evidence"]["span"] == (
        "classify_after_leave_confirm"
    )
    assert result["panel"]["exception_evidence"]["error"] == (
        "post-leave classify crashed"
    )
    assert result["panel"]["steps"][-1]["control"] == "classify_after_leave_confirm"
    assert classify_count == 2
    assert any(
        name == "post_leave_classification_exception"
        and payload["exception_evidence"]["error"] == "post-leave classify crashed"
        for name, payload in runner.telemetry.events
    )


def test_shop_leave_blocks_when_post_leave_session_load_raises(monkeypatch):
    def fake_load_game_state(_profile):
        return SimpleNamespace(
            difficulty=0,
            grid_power=7,
            grid_power_max=7,
            mechs=["ElectricMech", "WallMech", "RockartMech"],
            weapons=["Prime_Lightning", "Brute_Grapple", "Ranged_Rockthrow"],
        )

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)

    classify_count = 0

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify":
            classify_count += 1
            return {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "screenshot_path": "/tmp/post_leave_session_load.png",
            }
        return {"status": "OK", "control": control}

    def load_session():
        raise RuntimeError("post-leave session crashed")

    runner = make_runner()
    result = runner._handle_shop_then_leave(
        SimpleNamespace(
            _load_session=load_session,
            cmd_lightning_ui=lightning_ui,
        ),
        {"status": "OK", "visible_ui": "island_complete_leave"},
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "post_leave_session_load_exception"
    assert result["exception_evidence"]["reason"] == "session_load_exception"
    assert result["exception_evidence"]["stage"] == "post_leave_handoff_session"
    assert result["exception_evidence"]["error"] == "post-leave session crashed"
    assert result["observed_visible_ui"]["screenshot_path"] == (
        "/tmp/post_leave_session_load.png"
    )
    assert classify_count == 1
    assert result["steps"][-1]["control"] == "classify_after_leave_confirm"
    assert any(
        name == "session_load_exception"
        and payload["stage"] == "post_leave_handoff_session"
        and payload["error"] == "post-leave session crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_clears_panel_immediately_after_segment_stop():
    controls: list[str] = []
    session = SimpleNamespace(
        run_id="20260606_121313_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=2,
        islands_completed=[],
    )
    segment_calls = 0
    classify_reward = {"next": False}

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify" and classify_reward["next"]:
            classify_reward["next"] = False
            return {"status": "OK", "visible_ui": "reward_panel"}
        if control == "classify":
            return pause_menu()
        if control == "handle_screen":
            return {"status": "OK", "reason": "reward_panel_cleared"}
        return {"status": "OK"}

    def segment(*args, **kwargs):
        nonlocal segment_calls
        segment_calls += 1
        if segment_calls == 1:
            classify_reward["next"] = True
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "LIGHTNING_ATTEMPT_PANEL_READY",
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner()
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert segment_calls == 2
    assert "handle_screen" in controls
    post_panel_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "post_segment_panel_handled"
    ]
    assert post_panel_events[0]["status"] == "OK"


def test_runner_blocks_when_safe_panel_handler_raises_after_segment_stop():
    session = SimpleNamespace(
        run_id="20260606_121313_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=2,
        islands_completed=[],
    )
    segment_calls = 0
    classify_reward = {"next": False}

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify" and classify_reward["next"]:
            classify_reward["next"] = False
            return {"status": "OK", "visible_ui": "reward_panel"}
        if control == "classify":
            return pause_menu()
        if control == "handle_screen":
            raise RuntimeError("panel handler crashed")
        return {"status": "OK"}

    def segment(*args, **kwargs):
        nonlocal segment_calls
        segment_calls += 1
        classify_reward["next"] = True
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "LIGHTNING_ATTEMPT_PANEL_READY",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "post_segment_panel_blocked"
    assert result["panel"]["reason"] == "visible_panel_handle_exception"
    assert result["panel"]["span"] == "handle_visible_panel"
    assert result["panel"]["error"] == "panel handler crashed"
    assert result["panel"]["visible_name"] == "reward_panel"
    assert segment_calls == 1
    assert any(
        name == "visible_panel_handle_exception"
        and payload["error"] == "panel handler crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_failed_objective_reward_after_segment_stop():
    controls: list[str] = []
    session = SimpleNamespace(
        run_id="20260606_121314_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Train",
        mission_index=2,
        islands_completed=[],
    )
    segment_calls = 0
    classify_reward = {"next": False}

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify" and classify_reward["next"]:
            classify_reward["next"] = False
            return {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
                "visible_text": "Region Secured\nProtect the Train (Failed)",
                "screenshot_path": "/tmp/failed_objective_reward.png",
            }
        if control == "classify":
            return pause_menu()
        if control == "handle_screen":
            return {"status": "OK", "reason": "should_not_clear_failed_objective"}
        return {"status": "OK"}

    def segment(*args, **kwargs):
        nonlocal segment_calls
        segment_calls += 1
        classify_reward["next"] = True
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "LIGHTNING_ATTEMPT_PANEL_READY",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner()
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "post_segment_panel_blocked"
    assert result["panel"]["reason"] == "terminal_outcome_visible"
    assert result["panel"]["terminal_evidence"]["phrase"] == "(failed)"
    assert result["panel"]["terminal_evidence"]["path"] == "visible_text"
    assert result["panel"]["visible_ui"]["screenshot_path"] == (
        "/tmp/failed_objective_reward.png"
    )
    assert segment_calls == 1
    assert "handle_screen" not in controls


def test_runner_blocks_terminal_evidence_before_declaring_target_success():
    session = SimpleNamespace(
        run_id="20260606_121314_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="Mission_Train",
        mission_index=8,
        islands_completed=["archive"],
    )
    classify_count = 0

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify":
            classify_count += 1
            if classify_count == 1:
                return pause_menu()
            return {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
                "objective_texts": [
                    "Region Secured",
                    "Protect the Train (Failed)",
                ],
                "screenshot_path": "/tmp/failed_success_guard.png",
            }
        return {"status": "OK", "control": control}

    def segment(*args, **kwargs):
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "terminal_outcome_visible_before_success"
    assert result["completion_block"]["terminal_evidence"]["path"] == (
        "objective_texts.1"
    )
    assert result["completion_block"]["visible_ui"]["screenshot_path"] == (
        "/tmp/failed_success_guard.png"
    )


def test_runner_blocks_classification_failure_before_declaring_target_success():
    session = SimpleNamespace(
        run_id="20260606_121314_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="Mission_Train",
        mission_index=8,
        islands_completed=["archive"],
    )
    classify_count = 0

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify":
            classify_count += 1
            if classify_count == 1:
                return pause_menu()
            return {
                "status": "ERROR",
                "error": "screenshot failed: window not found",
            }
        return {"status": "OK", "control": control}

    def segment(*args, **kwargs):
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "completion_screen_classification_failed"
    assert result["completion_block"]["visible_ui"]["status"] == "ERROR"
    assert result["completion_block"]["visible_ui"]["error"] == (
        "screenshot failed: window not found"
    )


def test_completion_proof_blocks_when_classifier_raises():
    def lightning_ui(*args, **kwargs):
        raise RuntimeError("classify helper crashed")

    commands = SimpleNamespace(cmd_lightning_ui=lightning_ui)
    runner = make_runner()

    result = runner._completion_screen_block(
        commands,
        completed=["archive", "rst"],
        label="classify_raises",
    )

    assert result["reason"] == "completion_screen_classification_exception"
    assert result["exception_type"] == "RuntimeError"
    assert result["error"] == "classify helper crashed"
    assert "classify helper crashed" in result["traceback"]
    proof_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "completion_screen_proof"
    ]
    assert proof_events == [
        {
            "label": "classify_raises",
            "source": "classify",
            "status": "BLOCKED",
            "visible_name": None,
            "reason": "completion_screen_classification_exception",
            "islands_completed": ["archive", "rst"],
            "exception_type": "RuntimeError",
            "error": "classify helper crashed",
        }
    ]


def test_completion_proof_preserves_classifier_exception_when_event_write_raises():
    class CompletionProofEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "completion_screen_proof":
                raise RuntimeError("completion proof event write crashed")
            super().event(name, **payload)

    def lightning_ui(*args, **kwargs):
        raise RuntimeError("classify helper crashed")

    commands = SimpleNamespace(cmd_lightning_ui=lightning_ui)
    runner = make_runner()
    runner.telemetry = CompletionProofEventRaises()

    result = runner._completion_screen_block(
        commands,
        completed=["archive", "rst"],
        label="classify_raises_event_fails",
    )

    assert result["reason"] == "completion_screen_classification_exception"
    assert result["error"] == "classify helper crashed"
    assert result["telemetry_event_errors"] == [
        {
            "event_name": "completion_screen_proof",
            "exception_type": "RuntimeError",
            "error": "completion proof event write crashed",
        }
    ]


def test_completion_proof_accepts_visible_island_map_without_peek():
    classify_calls: list[dict] = []

    def lightning_ui(*args, **kwargs):
        classify_calls.append(kwargs)
        return {
            "status": "OK",
            "visible_ui": "island_map",
            "screenshot_path": "/tmp/final_map.png",
        }

    commands = SimpleNamespace(
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_peek=unexpected("completion peek"),
    )
    runner = make_runner()

    result = runner._completion_screen_block(
        commands,
        completed=["archive", "rst"],
        label="classify_visible_success",
    )

    assert result is None
    assert classify_calls == [{"control": "classify", "include_ocr": True}]
    assert not any(name == "completion_pause_peek" for name, _ in runner.telemetry.events)
    proof_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "completion_screen_proof"
    ]
    assert proof_events == [
        {
            "label": "classify_visible_success",
            "source": "classify",
            "status": "OK",
            "visible_name": "island_map",
            "reason": None,
            "islands_completed": ["archive", "rst"],
            "visible_ui": {
                "visible_ui": "island_map",
                "screenshot_path": "/tmp/final_map.png",
                "status": "OK",
            },
        }
    ]


def test_runner_preserves_target_success_when_completion_proof_event_raises():
    session = SimpleNamespace(
        run_id="20260606_121314_009",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=8,
        islands_completed=["archive", "rst"],
    )

    class CompletionProofEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "completion_screen_proof":
                raise RuntimeError("completion proof event write crashed")
            super().event(name, **payload)

    def lightning_ui(*args, **kwargs):
        return {
            "status": "OK",
            "visible_ui": "island_map",
            "screenshot_path": "/tmp/final_map.png",
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=unexpected("preflight"),
        cmd_lightning_segment=unexpected("segment"),
        cmd_lightning_peek=unexpected("completion peek"),
    )
    runner = make_runner()
    runner.telemetry = CompletionProofEventRaises()

    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_already_completed"
    assert result["telemetry_event_errors"] == [
        {
            "event_name": "completion_screen_proof",
            "exception_type": "RuntimeError",
            "error": "completion proof event write crashed",
        }
    ]
    assert any(
        name == "runner_finish"
        and payload["reason"] == "target_islands_already_completed"
        for name, payload in runner.telemetry.events
    )


def test_runner_deduplicates_nested_completion_proof_event_error():
    session = SimpleNamespace(
        run_id="20260606_121314_011",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=8,
        islands_completed=["archive", "rst"],
    )

    class CompletionProofEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "completion_screen_proof":
                raise RuntimeError("completion proof event write crashed")
            super().event(name, **payload)

    def lightning_ui(*args, **kwargs):
        return {
            "status": "OK",
            "visible_ui": "island_map_or_unknown",
            "screenshot_path": "/tmp/ambiguous_final_map.png",
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=unexpected("preflight"),
        cmd_lightning_segment=unexpected("segment"),
        cmd_lightning_peek=unexpected("completion peek"),
    )
    runner = make_runner()
    runner.telemetry = CompletionProofEventRaises()

    result = runner._run_inner(commands)

    expected_error = {
        "event_name": "completion_screen_proof",
        "exception_type": "RuntimeError",
        "error": "completion proof event write crashed",
    }
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "completion_screen_unverified"
    assert result["completion_block"]["telemetry_event_errors"] == [expected_error]
    assert result["telemetry_event_errors"] == [expected_error]


def test_completion_proof_accepts_clean_pause_peek():
    classify_calls: list[dict] = []
    peek_calls: list[dict] = []

    def lightning_ui(*args, **kwargs):
        classify_calls.append(kwargs)
        return pause_menu()

    def peek(**kwargs):
        peek_calls.append(kwargs)
        return {
            "status": "OK",
            "reason": "micro_peek_captured_and_paused",
            "evidence_ui": {
                "status": "OK",
                "visible_ui": "island_map",
                "screenshot_path": "/tmp/peek_final_map.png",
            },
            "pause_verify": {"status": "OK", "visible_ui": "pause_menu"},
        }

    commands = SimpleNamespace(
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_peek=peek,
    )
    runner = make_runner()

    result = runner._completion_screen_block(
        commands,
        completed=["archive", "rst"],
        label="classify_pause_success",
    )

    assert result is None
    assert classify_calls == [{"control": "classify", "include_ocr": True}]
    assert peek_calls == [
        {
            "label": "classify_pause_success_completion",
            "note": "completion proof peek before Lightning War success",
            "dry_run": False,
            "require_paused": True,
            "include_ocr": True,
        }
    ]
    assert any(
        name == "completion_pause_peek"
        and payload["status"] == "OK"
        and payload["visible_name"] == "island_map"
        for name, payload in runner.telemetry.events
    )
    proof_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "completion_screen_proof"
    ]
    assert proof_events[0]["source"] == "classify"
    assert proof_events[0]["status"] == "BLOCKED"
    assert proof_events[0]["reason"] == "completion_pause_menu_visible"
    assert proof_events[1]["source"] == "completion_pause_peek"
    assert proof_events[1]["status"] == "OK"
    assert proof_events[1]["visible_name"] == "island_map"


def test_runner_preserves_target_success_when_completion_pause_peek_event_raises():
    session = SimpleNamespace(
        run_id="20260606_121314_010",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=8,
        islands_completed=["archive", "rst"],
    )

    class CompletionPausePeekEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "completion_pause_peek":
                raise RuntimeError("completion pause peek event write crashed")
            super().event(name, **payload)

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_preflight=unexpected("preflight"),
        cmd_lightning_segment=unexpected("segment"),
        cmd_lightning_peek=completion_peek(),
    )
    runner = make_runner()
    runner.telemetry = CompletionPausePeekEventRaises()

    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_already_completed"
    assert result["telemetry_event_errors"] == [
        {
            "event_name": "completion_pause_peek",
            "exception_type": "RuntimeError",
            "error": "completion pause peek event write crashed",
        }
    ]
    assert any(
        name == "runner_finish"
        and payload["reason"] == "target_islands_already_completed"
        for name, payload in runner.telemetry.events
    )


def test_completion_proof_logs_unavailable_pause_peek():
    commands = SimpleNamespace(cmd_lightning_ui=lambda *args, **kwargs: pause_menu())
    runner = make_runner()

    result = runner._completion_screen_block(
        commands,
        completed=["archive", "rst"],
        label="classify_pause_no_peek",
    )

    assert result["reason"] == "completion_pause_peek_unavailable"
    proof_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "completion_screen_proof"
    ]
    assert [event["reason"] for event in proof_events] == [
        "completion_pause_menu_visible",
        "completion_pause_peek_unavailable",
    ]
    assert proof_events[1]["source"] == "completion_pause_peek"
    assert proof_events[1]["visible_name"] == "pause_menu"


def test_completion_proof_logs_failed_pause_peek():
    def peek(**kwargs):
        return {
            "status": "BLOCKED",
            "reason": "pause_not_verified_after_peek",
            "screenshot_path": "/tmp/peek_unpaused.png",
        }

    commands = SimpleNamespace(
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_peek=peek,
    )
    runner = make_runner()

    result = runner._completion_screen_block(
        commands,
        completed=["archive", "rst"],
        label="classify_pause_failed_peek",
    )

    assert result["reason"] == "completion_pause_peek_failed"
    assert result["peek"]["screenshot_path"] == "/tmp/peek_unpaused.png"
    proof_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "completion_screen_proof"
    ]
    assert [event["reason"] for event in proof_events] == [
        "completion_pause_menu_visible",
        "completion_pause_peek_failed",
    ]
    assert proof_events[1]["source"] == "completion_pause_peek"
    assert proof_events[1]["peek"]["screenshot_path"] == "/tmp/peek_unpaused.png"


def test_completion_proof_blocks_when_pause_peek_raises():
    def peek(**kwargs):
        raise RuntimeError("peek helper crashed")

    commands = SimpleNamespace(
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_peek=peek,
    )
    runner = make_runner()

    result = runner._completion_screen_block(
        commands,
        completed=["archive", "rst"],
        label="classify_pause_peek_raises",
    )

    assert result["reason"] == "completion_pause_peek_exception"
    assert result["exception_type"] == "RuntimeError"
    assert result["error"] == "peek helper crashed"
    assert "peek helper crashed" in result["traceback"]
    proof_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "completion_screen_proof"
    ]
    assert [event["reason"] for event in proof_events] == [
        "completion_pause_menu_visible",
        "completion_pause_peek_exception",
    ]
    assert proof_events[1]["source"] == "completion_pause_peek"
    assert proof_events[1]["exception_type"] == "RuntimeError"
    assert proof_events[1]["error"] == "peek helper crashed"


def test_runner_blocks_ambiguous_screen_before_declaring_target_success():
    session = SimpleNamespace(
        run_id="20260606_121314_006",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="Mission_Train",
        mission_index=8,
        islands_completed=["archive"],
    )
    classify_count = 0

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify":
            classify_count += 1
            if classify_count == 1:
                return pause_menu()
            return {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "screenshot_path": "/tmp/ambiguous_success_guard.png",
            }
        return {"status": "OK", "control": control}

    def segment(*args, **kwargs):
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=unexpected("completion peek"),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "completion_screen_unverified"
    assert result["completion_block"]["visible_name"] == "island_map_or_unknown"
    assert result["completion_block"]["visible_ui"]["screenshot_path"] == (
        "/tmp/ambiguous_success_guard.png"
    )


def test_runner_peeks_pause_menu_before_declaring_target_success():
    session = SimpleNamespace(
        run_id="20260606_121314_007",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="Mission_Train",
        mission_index=8,
        islands_completed=["archive"],
    )
    peek_calls: list[dict] = []

    def segment(*args, **kwargs):
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    def peek(**kwargs):
        peek_calls.append(kwargs)
        return {
            "status": "OK",
            "reason": "micro_peek_captured_and_paused",
            "label": kwargs.get("label"),
            "screenshot_path": "/tmp/peek_failed_success_guard.png",
            "notes_path": "/tmp/notes.md",
            "note_written": True,
            "live_burst_seconds": 0.071,
            "include_ocr": kwargs.get("include_ocr"),
            "evidence_ui": {
                "status": "OK",
                "visible_ui": "reward_panel",
                "visible_text": "Region Secured\nProtect the Train (Failed)",
                "screenshot_path": "/tmp/peek_failed_success_guard.png",
            },
            "pause_verify": {"status": "OK", "visible_ui": "pause_menu"},
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=peek,
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "terminal_outcome_visible_before_success"
    assert result["completion_block"]["source"] == "completion_pause_peek"
    assert result["completion_block"]["terminal_evidence"]["path"] == "visible_text"
    assert result["completion_block"]["peek"]["evidence_ui"]["screenshot_path"] == (
        "/tmp/peek_failed_success_guard.png"
    )
    assert result["completion_block"]["peek"]["label"].endswith("_completion")
    assert result["completion_block"]["peek"]["notes_path"] == "/tmp/notes.md"
    assert result["completion_block"]["peek"]["include_ocr"] is True
    assert result["completion_block"]["peek"]["live_burst_seconds"] == 0.071
    assert result["completion_block"]["peek"]["pause_verify"]["visible_ui"] == (
        "pause_menu"
    )
    assert peek_calls[0]["include_ocr"] is True


def test_runner_blocks_terminal_screen_before_initial_achievement_sync_success():
    session = SimpleNamespace(
        run_id="20260606_121314_004",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: {
            "status": "OK",
            "visible_ui": {"status": "OK", "visible_ui": "title_screen"},
            "pause_verified": True,
        },
        cmd_achievements=lambda **_: {
            "status": "OK",
            "unlocked_list": ["Lightning War"],
        },
        cmd_lightning_ui=lambda *args, **kwargs: {
            "status": "OK",
            "visible_ui": "reward_panel",
            "objective_texts": ["Region Secured", "Protect the Train Failed"],
            "screenshot_path": "/tmp/achievement_sync_failed.png",
        },
        cmd_verify_setup_screen=unexpected("cmd_verify_setup_screen"),
        cmd_lightning_start_run=unexpected("cmd_lightning_start_run"),
        cmd_lightning_preflight=unexpected("cmd_lightning_preflight"),
        cmd_lightning_segment=unexpected("cmd_lightning_segment"),
    )

    result = make_runner(achievement_sync=True)._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "terminal_outcome_visible_before_success"
    assert result["completion_block"]["terminal_evidence"]["path"] == (
        "objective_texts.1"
    )
    assert result["sync"]["unlocked_list"] == ["Lightning War"]


def test_runner_blocks_terminal_screen_before_segment_achievement_sync_success():
    session = SimpleNamespace(
        run_id="20260606_121314_005",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="Mission_Train",
        mission_index=7,
        islands_completed=["archive"],
    )
    achievement_calls = 0
    classify_count = 0

    def achievements(**_):
        nonlocal achievement_calls
        achievement_calls += 1
        if achievement_calls == 1:
            return {"status": "OK", "unlocked_list": []}
        return {"status": "OK", "unlocked_list": ["Lightning War"]}

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify":
            classify_count += 1
            if classify_count == 1:
                return pause_menu()
            return {
                "status": "OK",
                "visible_ui": "reward_panel",
                "objective_texts": ["Region Secured", "Protect the Train Failed"],
                "screenshot_path": "/tmp/segment_sync_failed.png",
            }
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_achievements=achievements,
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        },
    )

    result = make_runner(achievement_sync=True)._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "terminal_outcome_visible_before_success"
    assert result["completion_block"]["terminal_evidence"]["path"] == (
        "objective_texts.1"
    )
    assert result["sync"]["unlocked_list"] == ["Lightning War"]


def test_runner_blocks_when_segment_achievement_sync_raises():
    session = SimpleNamespace(
        run_id="20260606_121314_006",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="Mission_Train",
        mission_index=7,
        islands_completed=["archive"],
    )
    achievement_calls = 0

    def achievements(**_kwargs):
        nonlocal achievement_calls
        achievement_calls += 1
        if achievement_calls == 1:
            return {"status": "OK", "unlocked_list": []}
        raise RuntimeError("post-segment sync crashed")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_achievements=achievements,
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        },
    )
    runner = make_runner(achievement_sync=True)

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "achievement_sync_exception"
    assert result["span"] == "achievements_segment"
    assert result["segment_index"] == 1
    assert result["exception_type"] == "RuntimeError"
    assert result["error"] == "post-segment sync crashed"
    assert "post-segment sync crashed" in result["traceback"]
    assert achievement_calls == 2
    assert any(
        name == "achievement_sync_exception"
        and payload["span"] == "achievements_segment"
        and payload["error"] == "post-segment sync crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_resumes_to_clear_segment_panel_hidden_under_pause():
    controls: list[str] = []
    session = SimpleNamespace(
        run_id="20260606_121315_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=2,
        islands_completed=[],
    )
    segment_calls = 0
    resumed_from_pause = False
    resume_control = "menu_continue"

    def lightning_ui(*args, **kwargs):
        nonlocal resumed_from_pause
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify" and resumed_from_pause:
            resumed_from_pause = False
            return {"status": "OK", "visible_ui": "reward_panel"}
        if control == "classify":
            return pause_menu()
        if control == resume_control:
            resumed_from_pause = True
            return {"status": "OK", "reason": "pause_menu_resumed"}
        if control == "handle_screen":
            return {"status": "OK", "reason": "reward_panel_cleared"}
        if control == "ensure_pause":
            return pause_menu()
        return {"status": "OK"}

    def segment(*args, **kwargs):
        nonlocal segment_calls
        segment_calls += 1
        if segment_calls == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "LIGHTNING_ATTEMPT_PANEL_READY",
                "pause_guard": {
                    "status": "OK",
                    "visible_ui": {"status": "OK", "visible_ui": "reward_panel"},
                },
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner()
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert segment_calls == 2
    assert controls.index(resume_control) < controls.index("handle_screen")
    assert "ensure_pause" in controls
    post_panel_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "post_segment_panel_handled"
    ]
    assert post_panel_events[0]["status"] == "OK"
    assert post_panel_events[0]["reason"] == "paused_segment_panel_handled"


def test_runner_blocks_when_resume_paused_segment_panel_raises():
    session = SimpleNamespace(
        run_id="20260606_121315_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=2,
        islands_completed=[],
    )
    segment_called = False

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify":
            return pause_menu()
        if control == "menu_continue":
            raise RuntimeError("resume click crashed")
        return {"status": "OK"}

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "LIGHTNING_ATTEMPT_PANEL_READY",
            "pause_guard": {
                "status": "OK",
                "visible_ui": {"status": "OK", "visible_ui": "reward_panel"},
            },
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "post_segment_panel_blocked"
    assert result["panel"]["reason"] == "resume_paused_segment_panel_exception"
    assert result["panel"]["span"] == "resume_paused_segment_panel"
    assert result["panel"]["exception_type"] == "RuntimeError"
    assert result["panel"]["error"] == "resume click crashed"
    assert "resume click crashed" in result["panel"]["traceback"]
    assert segment_called is True
    assert any(
        name == "resume_paused_segment_panel_exception"
        and payload["error"] == "resume click crashed"
        for name, payload in runner.telemetry.events
    )


def test_paused_segment_panel_clears_chained_panels_before_pause():
    controls: list[str] = []
    classify_results = [
        {"status": "OK", "visible_ui": "perfect_island_panel"},
        {"status": "OK", "visible_ui": "bottom_continue_panel"},
    ]
    ensure_calls = 0

    def lightning_ui(*args, **kwargs):
        nonlocal ensure_calls
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "menu_continue":
            return {"status": "OK"}
        if control == "classify":
            return classify_results.pop(0)
        if control == "handle_screen":
            return {"status": "OK", "reason": "panel_cleared"}
        if control == "ensure_pause":
            ensure_calls += 1
            if ensure_calls == 1:
                return {
                    "status": "BLOCKED",
                    "reason": "visible_panel_should_be_cleared_first",
                    "recommended_control": "panel_continue",
                }
            return {"status": "OK", "reason": "pause_clicked"}
        raise AssertionError(f"unexpected control {control}")

    commands = SimpleNamespace(cmd_lightning_ui=lightning_ui)
    runner = make_runner()

    result = runner._handle_paused_segment_panel(
        commands,
        segment_index=3,
        expected_visible_name="perfect_island_panel",
        paused_panel={"status": "NO_ACTION", "visible_name": "pause_menu"},
    )

    assert result["status"] == "OK"
    assert result["reason"] == "paused_segment_panel_handled"
    assert result["panel_chain_index"] == 1
    assert len(result["panel_chain"]) == 2
    assert controls == [
        "menu_continue",
        "classify",
        "handle_screen",
        "ensure_pause",
        "classify",
        "handle_screen",
        "ensure_pause",
    ]


def test_post_segment_clears_paused_deployment_continue_panel():
    controls: list[str] = []
    classify_results = [
        {"status": "OK", "visible_ui": "pause_menu"},
        {
            "status": "OK",
            "visible_ui": "bottom_continue_panel",
            "recommended_control": "bottom_continue",
        },
    ]

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify":
            return classify_results.pop(0)
        if control in {"menu_continue", "handle_screen", "ensure_pause"}:
            return {"status": "OK", "reason": f"{control}_ok"}
        raise AssertionError(f"unexpected control {control}")

    commands = SimpleNamespace(cmd_lightning_ui=lightning_ui)
    runner = make_runner()
    segment = {
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "deployment_visible_ui_not_deployment",
        "last_attempt": {
            "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
            "reason": "deployment_visible_ui_not_deployment",
            "action": {
                "deployment_visible_ui_recheck": {
                    "initial_visible_ui": {
                        "status": "OK",
                        "visible_ui": "bottom_continue_panel",
                        "recommended_control": "bottom_continue",
                    }
                }
            },
        },
        "pause_guard": pause_menu(),
    }

    result = runner._handle_post_segment_panel(
        commands,
        segment=segment,
        segment_index=2,
    )

    assert result is not None
    assert result["status"] == "OK"
    assert result["reason"] == "paused_segment_panel_handled"
    assert result["expected_visible_name"] == "bottom_continue_panel"
    assert controls == [
        "classify",
        "menu_continue",
        "classify",
        "handle_screen",
        "ensure_pause",
    ]
    assert any(
        name == "post_segment_panel_handled"
        and payload["visible_name"] == "bottom_continue_panel"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_visible_mission_preview_start_without_route_validation():
    controls: list[str] = []
    session = SimpleNamespace(
        run_id="20260606_121316_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=1,
        islands_completed=[],
    )

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify":
            return {
                "status": "OK",
                "visible_ui": "mission_preview_panel",
                "recommended_control": "mission_preview_board",
            }
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=unexpected("segment"),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_blocked"
    assert result["panel"]["reason"] == "mission_preview_requires_route_validation"
    assert result["panel"]["recommended_control"] == "mission_preview_board"
    assert controls == ["classify"]


def test_runner_clears_mission_preview_dialogue_then_blocks_start():
    controls: list[str] = []
    classify_count = 0
    session = SimpleNamespace(
        run_id="20260606_121317_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=1,
        islands_completed=[],
    )

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify":
            classify_count += 1
            if classify_count == 1:
                return {
                    "status": "OK",
                    "visible_ui": "mission_preview_panel",
                    "recommended_control": "dialogue_textbox",
                }
            return {
                "status": "OK",
                "visible_ui": "mission_preview_panel",
                "recommended_control": "mission_preview_board",
            }
        if control == "dialogue_textbox":
            return {"status": "OK", "control": control}
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=unexpected("segment"),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_blocked"
    assert result["panel"]["reason"] == "mission_preview_requires_route_validation"
    assert controls[:3] == ["classify", "dialogue_textbox", "classify"]
    assert controls[-1] == "classify"
    assert "mission_preview_board" not in controls


def test_runner_blocks_when_mission_preview_dialogue_clear_raises():
    controls: list[str] = []
    session = SimpleNamespace(
        run_id="20260606_121317_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=1,
        islands_completed=[],
    )

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify":
            return {
                "status": "OK",
                "visible_ui": "mission_preview_panel",
                "recommended_control": "dialogue_textbox",
            }
        if control == "dialogue_textbox":
            raise RuntimeError("dialogue clear crashed")
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=unexpected("segment"),
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_blocked"
    assert result["panel"]["reason"] == "mission_preview_dialogue_clear_exception"
    assert result["panel"]["span"] == "clear_mission_preview_dialogue"
    assert result["panel"]["error"] == "dialogue clear crashed"
    assert result["panel"]["visible_name"] == "mission_preview_panel"
    assert controls == ["classify", "dialogue_textbox"]
    assert any(
        name == "mission_preview_dialogue_clear_exception"
        and payload["error"] == "dialogue clear crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_when_mission_preview_post_classify_raises():
    controls: list[str] = []
    classify_count = 0
    session = SimpleNamespace(
        run_id="20260606_121317_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=1,
        islands_completed=[],
    )

    def lightning_ui(*args, **kwargs):
        nonlocal classify_count
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify":
            classify_count += 1
            if classify_count == 1:
                return {
                    "status": "OK",
                    "visible_ui": "mission_preview_panel",
                    "recommended_control": "dialogue_textbox",
                }
            raise RuntimeError("post-dialogue classify crashed")
        if control == "dialogue_textbox":
            return {"status": "OK", "control": control}
        return {"status": "OK", "control": control}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=unexpected("segment"),
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_handling_failed"
    assert result["panel"]["reason"] == (
        "mission_preview_dialogue_post_classify_exception"
    )
    assert result["panel"]["span"] == "classify_after_mission_preview_dialogue"
    assert result["panel"]["error"] == "post-dialogue classify crashed"
    assert result["panel"]["handle_result"]["status"] == "OK"
    assert controls == ["classify", "dialogue_textbox", "classify"]
    assert any(
        name == "mission_preview_dialogue_post_classify_exception"
        and payload["error"] == "post-dialogue classify crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_restarts_route_gate_attempt_from_setup():
    session = SimpleNamespace(
        run_id="20260606_161616_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "route_auto_start_not_allowed",
                "route_start_performed": False,
                "steps": [
                    {
                        "step": 0,
                        "route_auto_start_blocked_candidate": {
                            "index": 0,
                            "mission_id": "Mission_Mines",
                            "auto_route_allowed": False,
                            "auto_route_block_reason": "vetoed_mission_Mission_Mines",
                        },
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    def start_run(*args, **kwargs):
        starts.append(kwargs)
        return {"status": "OK", "reason": "started"}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=start_run,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert segments[0]["route_probe_offset"] == 0
    assert segments[1]["route_probe_offset"] == 1
    assert len(abandons) == 1
    assert abandons[0]["reason"] == "route_gate_attempt_1"
    assert len(starts) == 1
    assert starts[0]["first_island"] == "rst"
    assert starts[0]["route_auto_start"] is False
    assert any(
        name == "attempt_restart"
        and payload["status"] == "OK"
        and payload["next_attempt_index"] == 2
        and payload["next_first_island"] == "rst"
        for name, payload in runner.telemetry.events
    )


def test_speed_runner_does_not_rotate_first_route_probe_across_restarts():
    session = SimpleNamespace(
        run_id="lw_route_probe_speed",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        islands_completed=[],
        current_island="rst",
        current_mission="",
        mission_index=0,
    )
    segments: list[dict] = []
    starts: list[dict] = []
    abandons: list[dict] = []
    segment_results = iter(
        [
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "first_mission_route_start_pace_gate",
                "visible_timer": {
                    "game_seconds": 30.0,
                    "game_timer": "0:00:30",
                },
                "pause_guard": pause_menu(),
            },
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "max_steps_reached",
                "pause_guard": pause_menu(),
            },
        ]
    )

    def segment(*args, **kwargs):
        segments.append(kwargs)
        return next(segment_results)

    def start_run(*args, **kwargs):
        starts.append(kwargs)
        return {"status": "OK", "reason": "started"}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=start_run,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2, mode="speed")
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert len(segments) >= 2
    assert {segment["route_probe_offset"] for segment in segments} == {0}


def test_runner_does_not_restart_route_gate_after_subcall_timeout():
    session = SimpleNamespace(
        run_id="20260620_235458_744",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    abandons = []

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "route_auto_start_not_allowed",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
                    "reason": "deployment_bridge_state_uncertain",
                }
            ],
            "last_attempt": {
                "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
                "reason": "deployment_bridge_state_uncertain",
                "recommendation": {
                    "status": "BLOCKED",
                    "reason": "lightning_subcall_timeout",
                    "error": "attempt_subcall_timeout after 30.0s",
                },
            },
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK"},
    )

    runner = make_runner(max_attempts=3)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "deployment_bridge_state_uncertain"
    assert abandons == []
    assert not any(name == "attempt_restart" for name, _payload in runner.telemetry.events)


def test_runner_restarts_visible_map_no_bridge_route_gate_with_stale_preview():
    session = SimpleNamespace(
        run_id="20260607_175155_052",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="pinnacle",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "route_auto_start_not_allowed",
                "route_start_performed": False,
                "last_attempt": {
                    "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
                    "reason": "bridge_snapshot_unavailable_visible_island_map",
                    "recommendation": {
                        "speed_route_status": {
                            "status": "AUTO_START_BLOCKED",
                            "reason": "stale_bridge_preview",
                            "top_mission_id": "Mission_Artillery",
                        },
                    },
                },
                "steps": [
                    {
                        "step": 0,
                        "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
                        "reason": "bridge_snapshot_unavailable_visible_island_map",
                        "top_mission": "Mission_Artillery",
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["pinnacle", "archive"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert len(abandons) == 1
    assert len(starts) == 1
    assert any(
        name == "attempt_restart"
        and payload["reason"] == "route_auto_start_not_allowed"
        for name, payload in runner.telemetry.events
    )
    assert not any(
        name == "stale_bridge_heartbeat"
        for name, _payload in runner.telemetry.events
    )


def test_runner_restarts_over_budget_initial_preflight_from_setup():
    session = SimpleNamespace(
        run_id="20260606_161616_007",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Slow",
        mission_index=4,
        islands_completed=[],
    )
    preflight_calls = []
    segments = []
    abandons = []
    starts = []

    def preflight(**kwargs):
        preflight_calls.append(kwargs)
        if len(preflight_calls) == 1:
            return {
                "status": "FAIL",
                "issues": [
                    "save-file in-game timer is 4:34:16, "
                    "at/over the Lightning War limit of 0:30:00"
                ],
                "warnings": [],
                "session": {
                    "run_id": session.run_id,
                    "squad": "Blitzkrieg",
                    "difficulty": 0,
                    "achievement_targets": ["Lightning War"],
                },
                "game_budget": {
                    "game_status": "EXCEEDED",
                    "game_seconds": 16456.0,
                    "game_timer": "4:34:16",
                },
            }
        return preflight_pass()

    def start_run(**kwargs):
        starts.append(kwargs)
        session.current_island = "archive"
        session.current_mission = ""
        session.mission_index = 0
        session.islands_completed = []
        return {"status": "OK", "reason": "first_island_paused"}

    def segment(**kwargs):
        segments.append(kwargs)
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=start_run,
        cmd_lightning_preflight=preflight,
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert len(preflight_calls) == 2
    assert len(abandons) == 1
    assert abandons[0]["reason"] == "preflight_timer_exceeded_attempt_1"
    assert len(starts) == 1
    assert len(segments) == 1
    assert any(
        name == "attempt_restart"
        and payload["status"] == "OK"
        and payload["reason"] == "preflight_timer_attempt_restarted"
        and payload["next_attempt_index"] == 2
        for name, payload in runner.telemetry.events
    )


def test_runner_does_not_restart_over_budget_when_attempts_exhausted():
    session = SimpleNamespace(
        run_id="20260606_161616_008",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Slow",
        mission_index=4,
        islands_completed=[],
    )
    abandoned = False
    segment_called = False

    def abandon(**_):
        nonlocal abandoned
        abandoned = True
        return {"status": "OK"}

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: {
            "status": "FAIL",
            "issues": [
                "save-file in-game timer is 4:34:16, "
                "at/over the Lightning War limit of 0:30:00"
            ],
            "warnings": [],
            "session": {
                "run_id": session.run_id,
                "squad": "Blitzkrieg",
                "difficulty": 0,
                "achievement_targets": ["Lightning War"],
            },
            "game_budget": {
                "game_status": "EXCEEDED",
                "game_seconds": 16456.0,
                "game_timer": "4:34:16",
            },
        },
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=abandon,
    )

    result = make_runner(max_attempts=1)._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "preflight_failed"
    assert abandoned is False
    assert segment_called is False


def test_runner_restarts_first_mission_start_pace_gate_from_setup():
    session = SimpleNamespace(
        run_id="20260620_223500_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    preflight_calls = []
    abandons = []
    starts = []
    segments = []

    def preflight(**kwargs):
        preflight_calls.append(kwargs)
        if len(preflight_calls) == 1:
            return preflight_with_timer(191.0)
        return preflight_pass()

    def start_run(**kwargs):
        starts.append(kwargs)
        session.current_island = kwargs.get("first_island") or "archive"
        session.current_mission = ""
        session.mission_index = 0
        session.islands_completed = []
        return {"status": "OK", "reason": "first_island_paused"}

    def segment(**kwargs):
        segments.append(kwargs)
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=start_run,
        cmd_lightning_preflight=preflight,
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(mode="speed", max_attempts=2)
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert len(abandons) == 1
    assert abandons[0]["reason"] == "first_mission_start_pace_gate_attempt_1"
    assert starts[0]["first_island"] == "rst"
    assert len(segments) == 1
    assert len(preflight_calls) == 2


def test_runner_restarts_first_mission_route_start_pace_gate_from_setup():
    session = SimpleNamespace(
        run_id="20260620_223500_004",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    preflight_calls = []
    abandons = []
    starts = []
    segments = []

    def preflight(**kwargs):
        preflight_calls.append(kwargs)
        if len(preflight_calls) == 1:
            return preflight_with_timer(121.0)
        return preflight_pass()

    def start_run(**kwargs):
        starts.append(kwargs)
        session.current_island = kwargs.get("first_island") or "archive"
        session.current_mission = ""
        session.mission_index = 0
        session.islands_completed = []
        return {"status": "OK", "reason": "first_island_paused"}

    def segment(**kwargs):
        segments.append(kwargs)
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=start_run,
        cmd_lightning_preflight=preflight,
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner(mode="speed", max_attempts=2)._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert len(abandons) == 1
    assert abandons[0]["reason"] == "first_mission_route_start_pace_gate_attempt_1"
    assert starts[0]["first_island"] == "rst"
    assert len(segments) == 1
    assert len(preflight_calls) == 2


def test_runner_restarts_segment_first_mission_route_start_pace_gate():
    session = SimpleNamespace(
        run_id="20260621_005015_837",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    abandons = []
    starts = []
    segments = []

    def start_run(**kwargs):
        starts.append(kwargs)
        session.current_island = kwargs.get("first_island") or "archive"
        session.current_mission = ""
        session.mission_index = 0
        session.islands_completed = []
        return {"status": "OK", "reason": "first_island_paused"}

    def segment(**kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "first_mission_route_start_pace_gate",
                "first_mission_route_start_gate": {
                    "status": "BLOCKED",
                    "reason": "first_mission_route_start_pace_gate",
                    "visible_timer": {
                        "status": "OK",
                        "game_seconds": 122.0,
                        "game_timer": "0:02:02",
                    },
                },
                "visible_timer": {
                    "status": "OK",
                    "game_seconds": 122.0,
                    "game_timer": "0:02:02",
                },
                "pause_guard": pause_menu(),
                "steps": [
                    {
                        "step": 0,
                        "status": "LIGHTNING_ATTEMPT_ROUTE_READY",
                        "reason": "visible_island_map_save_route_plan",
                    },
                    {
                        "step": 1,
                        "status": "BLOCKED",
                        "reason": "first_mission_route_start_pace_gate",
                    },
                ],
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=start_run,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner(mode="speed", max_attempts=2)._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert len(abandons) == 1
    assert abandons[0]["reason"] == "first_mission_route_start_pace_gate_attempt_1"
    assert len(starts) == 1
    assert starts[0]["first_island"] == "rst"
    assert len(segments) == 2


def test_runner_carries_pending_route_retry_after_segment_wall_cap():
    session = SimpleNamespace(
        run_id="20260621_015027_668",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []

    def segment(**kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "segment_wall_seconds_exceeded",
                "route_start_performed": True,
                "route_visual_region_index_pending": 0,
                "route_start_pending_context": {
                    "visual_region_index": 0,
                    "region_window_x": 396,
                    "region_window_y": 438,
                    "verify_route": False,
                    "close_existing_preview_before_region_click": True,
                    "start_mode": "visible-text",
                },
                "pause_guard": pause_menu(),
                "steps": [
                    {
                        "step": 0,
                        "status": "LIGHTNING_ATTEMPT_ROUTE_READY",
                        "reason": "visible_island_map_save_route_plan",
                    },
                    {
                        "step": 1,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": "route_preview_auto_start_vetoed_before_start",
                        "route_auto_start_rejected_candidate": {
                            "index": 1,
                            "mission_id": "Mission_Satellite",
                            "auto_route_allowed": False,
                            "auto_route_block_reason": (
                                "vetoed_mission:Mission_Satellite"
                            ),
                            "window_x": 836,
                            "window_y": 456,
                            "visible_label": "Secondary Archives",
                            "route_click_target": {
                                "source": "ocr_label_below",
                                "window_x": 836,
                                "window_y": 456,
                            },
                        },
                        "route_auto_start_retry_index": 0,
                    },
                ],
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=unexpected("cmd_lightning_start_run"),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=unexpected("cmd_lightning_abandon_to_setup"),
        cmd_lightning_peek=completion_peek(),
        _lightning_route_probe_cache_entry_from_segment=(
            loop_commands._lightning_route_probe_cache_entry_from_segment
        ),
    )

    runner = make_runner(mode="speed", max_attempts=1)
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert [call["route_visual_region_index"] for call in segments] == [None, 0]
    assert [call.get("route_region_window_x") for call in segments] == [None, 396]
    assert [call.get("route_region_window_y") for call in segments] == [None, 438]
    assert [call.get("route_start_verify_route") for call in segments] == [
        None,
        False,
    ]
    assert [call.get("route_close_existing_preview") for call in segments] == [
        False,
        True,
    ]
    pending_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "route_auto_start_pending_retry"
    ]
    assert pending_events[0]["visual_region_index"] == 0
    assert pending_events[0]["route_start_pending_context"]["region_window_x"] == 396
    assert pending_events[0]["route_probe_cache_record"]["status"] == "OK"
    assert runner.route_probe_cache[0]["signature"]["label_key"] == (
        "secondaryarchives"
    )
    assert segments[1]["route_probe_cache"][0]["signature"]["label_key"] == (
        "secondaryarchives"
    )
    assert segments[1]["route_probe_cache"][0]["visible_label"] == (
        "Secondary Archives"
    )


def test_runner_records_pending_route_retry_cache_without_command_builder():
    session = SimpleNamespace(
        run_id="20260621_191955_014",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []

    def segment(**kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "segment_wall_seconds_exceeded",
                "game_timer": "0:00:59",
                "game_seconds": 59.0,
                "route_start_performed": True,
                "route_start_pending_context": {
                    "visual_region_index": 1,
                    "region_window_x": 984,
                    "region_window_y": 593,
                    "verify_route": False,
                    "close_existing_preview_before_region_click": True,
                    "start_mode": "visible-text",
                },
                "pause_guard": pause_menu(),
                "steps": [
                    {
                        "step": 0,
                        "status": "LIGHTNING_ATTEMPT_ROUTE_READY",
                        "reason": "visible_island_map_save_route_plan",
                        "route_auto_start_index": 0,
                    },
                    {
                        "step": 1,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": "route_preview_not_opened_before_start",
                        "route_auto_start_rejected_candidate": {
                            "index": 0,
                            "auto_route_allowed": False,
                            "auto_route_block_reason": (
                                "route_preview_not_opened_before_start"
                            ),
                        },
                        "route_auto_start_retry_index": 1,
                        "route_auto_start_retry_probe": "live_preview_required",
                    },
                ],
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=unexpected("cmd_lightning_start_run"),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=unexpected("cmd_lightning_abandon_to_setup"),
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(mode="speed", max_attempts=1)
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    pending_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "route_auto_start_pending_retry"
    ]
    assert pending_events[0]["route_probe_cache_record"]["status"] == "OK"
    assert pending_events[0]["route_probe_cache_record"]["entry_summary"][
        "auto_route_block_reason"
    ] == "route_preview_not_opened_before_start"
    assert pending_events[0]["route_probe_cache_record"]["entry_summary"][
        "signature"
    ]["index"] == 0
    assert runner.route_probe_cache[0]["signature"]["index"] == 0
    assert segments[1]["route_probe_cache"][0]["auto_route_block_reason"] == (
        "route_preview_not_opened_before_start"
    )


def test_runner_records_pending_route_retry_cache_when_command_builder_returns_none():
    session = SimpleNamespace(
        run_id="20260621_200612_470",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []

    def segment(**kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "segment_wall_seconds_exceeded",
                "game_timer": "0:00:52",
                "game_seconds": 52.0,
                "route_start_performed": True,
                "route_start_pending_context": {
                    "visual_region_index": 1,
                    "region_window_x": 560,
                    "region_window_y": 387,
                    "verify_route": False,
                    "close_existing_preview_before_region_click": True,
                    "start_mode": "visible-text",
                },
                "pause_guard": pause_menu(),
                "steps": [
                    {
                        "step": 0,
                        "status": "LIGHTNING_ATTEMPT_ROUTE_READY",
                        "reason": "visible_island_map_save_route_plan",
                        "route_auto_start_index": 0,
                    },
                    {
                        "step": 1,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": "route_preview_not_opened_before_start",
                        "route_auto_start_rejected_candidate": {
                            "index": 0,
                            "auto_route_allowed": False,
                            "auto_route_block_reason": (
                                "route_preview_not_opened_before_start"
                            ),
                        },
                        "route_auto_start_retry_index": 1,
                        "route_auto_start_retry_probe": "live_preview_required",
                    },
                ],
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=unexpected("cmd_lightning_start_run"),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=unexpected("cmd_lightning_abandon_to_setup"),
        cmd_lightning_peek=completion_peek(),
        _lightning_route_probe_cache_entry_from_segment=lambda *_args, **_kwargs: None,
    )

    runner = make_runner(mode="speed", max_attempts=1)
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    pending_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "route_auto_start_pending_retry"
    ]
    assert pending_events[0]["route_probe_cache_record"]["status"] == "OK"
    assert pending_events[0]["route_probe_cache_record"]["entry_summary"][
        "signature"
    ]["index"] == 0
    assert pending_events[0]["route_probe_cache_record"]["entry_summary"][
        "auto_route_block_reason"
    ] == "route_preview_not_opened_before_start"
    assert segments[1]["route_probe_cache"][0]["signature"]["index"] == 0


def test_runner_records_pending_route_retry_cache_from_retained_route_candidate():
    session = SimpleNamespace(
        run_id="20260621_210122_921",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []

    def segment(**kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "segment_wall_seconds_exceeded",
                "game_timer": "0:00:54",
                "game_seconds": 54.0,
                "route_start_performed": True,
                "route_start_pending_context": {
                    "visual_region_index": 0,
                    "region_window_x": 766,
                    "region_window_y": 308,
                    "verify_route": False,
                    "close_existing_preview_before_region_click": True,
                    "start_mode": "visible-text",
                },
                "pause_guard": pause_menu(),
                "last_attempt": {
                    "route_fallback": {
                        "blocked_route_start_candidates": [
                            {
                                "index": 0,
                                "window_x": 766,
                                "window_y": 308,
                                "visible_label": "Gamma Trench Crater Bay",
                                "visible_label_texts": [
                                    "Gamma Trench",
                                    "Crater Bay",
                                ],
                                "route_click_target": {
                                    "source": "ocr_label_below",
                                    "window_x": 766,
                                    "window_y": 308,
                                },
                            },
                            {
                                "index": 1,
                                "window_x": 398,
                                "window_y": 421,
                                "visible_label": "Kern's Folly",
                            },
                        ],
                    },
                },
                "steps": [
                    {
                        "step": 0,
                        "status": "LIGHTNING_ATTEMPT_ROUTE_READY",
                        "reason": "visible_island_map_save_route_plan",
                        "route_auto_start_index": 0,
                    },
                    {
                        "step": 1,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": "route_preview_not_opened_before_start",
                        "route_auto_start_retry_index": 1,
                        "route_auto_start_retry_probe": "live_preview_required",
                    },
                ],
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=unexpected("cmd_lightning_start_run"),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=unexpected("cmd_lightning_abandon_to_setup"),
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(mode="speed", max_attempts=1)
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    pending_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "route_auto_start_pending_retry"
    ]
    record = pending_events[0]["route_probe_cache_record"]
    assert record["status"] == "OK"
    assert record["entry_summary"]["signature"]["label_key"] == (
        "gammatrenchcraterbay"
    )
    assert record["entry_summary"]["auto_route_block_reason"] == (
        "route_preview_not_opened_before_start"
    )
    assert segments[1]["route_probe_cache"][0]["visible_label"] == (
        "Gamma Trench Crater Bay"
    )


def test_runner_does_not_cache_same_index_pending_alternate_click():
    session = SimpleNamespace(
        run_id="20260621_210710_517",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []

    def segment(**kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "segment_wall_seconds_exceeded",
                "game_timer": "0:00:57",
                "game_seconds": 57.0,
                "route_start_performed": True,
                "route_start_pending_context": {
                    "visual_region_index": 1,
                    "region_window_x": 984,
                    "region_window_y": 590,
                    "verify_route": False,
                    "close_existing_preview_before_region_click": True,
                    "start_mode": "visible-text",
                },
                "pause_guard": pause_menu(),
                "last_attempt": {
                    "route_fallback": {
                        "blocked_route_start_candidates": [
                            {
                                "index": 1,
                                "window_x": 984,
                                "window_y": 590,
                                "visible_label": "Exhibits Archive",
                                "route_click_target": {
                                    "source": "ocr_label_below",
                                    "window_x": 984,
                                    "window_y": 590,
                                },
                            },
                        ],
                    },
                },
                "steps": [
                    {
                        "step": 0,
                        "status": "LIGHTNING_ATTEMPT_ROUTE_READY",
                        "reason": "visible_island_map_save_route_plan",
                        "route_auto_start_index": 1,
                    },
                    {
                        "step": 1,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": "route_preview_not_opened_before_start",
                        "route_auto_start_retry_index": 1,
                        "route_auto_start_retry_probe": "live_preview_required",
                        "route_auto_start_retry_reason": "alternate_click_target",
                        "route_auto_start_alternate_click_candidate": {
                            "index": 1,
                            "window_x": 994,
                            "window_y": 595,
                        },
                    },
                ],
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=unexpected("cmd_lightning_start_run"),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=unexpected("cmd_lightning_abandon_to_setup"),
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(mode="speed", max_attempts=1)
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    pending_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "route_auto_start_pending_retry"
    ]
    assert pending_events[0]["route_probe_cache_record"]["status"] == "SKIPPED"
    step = pending_events[0]["segment"]["steps"][1]
    assert step["route_auto_start_retry_reason"] == "alternate_click_target"
    assert step["route_auto_start_alternate_click_candidate"]["window_x"] == 994


def test_runner_blocks_first_mission_start_pace_gate_when_attempts_exhausted():
    session = SimpleNamespace(
        run_id="20260620_223500_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    abandoned = False
    segment_called = False

    def abandon(**_):
        nonlocal abandoned
        abandoned = True
        return {"status": "OK"}

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_with_timer(191.0),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=abandon,
    )

    result = make_runner(mode="speed", max_attempts=1)._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "first_mission_start_pace_gate"
    assert result["pace_gate"]["game_seconds"] == 191.0
    assert result["pace_gate"]["gate_seconds"] == 180.0
    assert abandoned is False
    assert segment_called is False


def test_runner_blocks_when_first_mission_restart_timer_does_not_reset():
    session = SimpleNamespace(
        run_id="20260620_223500_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    starts = []
    segments = []

    def start_run(**kwargs):
        starts.append(kwargs)
        return {
            "status": "BLOCKED",
            "reason": "first_mission_start_timer_not_reset",
            "first_mission_start_timer_guard": {
                "status": "BLOCKED",
                "reason": "first_mission_start_timer_not_reset",
                "game_budget": {
                    "game_seconds": 316.0,
                    "game_timer": "0:05:16",
                    "max_game_seconds": 180,
                    "max_game_timer": "0:03:00",
                    "game_status": "EXCEEDED",
                },
                "visible_timer": {
                    "status": "OK",
                    "source": "visible_pause_menu_timer",
                    "game_seconds": 316.0,
                    "game_timer": "0:05:16",
                    "ocr_text": "Oh 5m 165",
                },
            },
        }

    def segment(**kwargs):
        segments.append(kwargs)
        return {"status": "LIGHTNING_SEGMENT_STOPPED", "reason": "max_steps_reached"}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=start_run,
        cmd_lightning_preflight=lambda **_: preflight_with_timer(191.0),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **_: {
            "status": "OK",
            "reason": "abandoned_to_new_game_setup",
        },
    )

    result = make_runner(mode="speed", max_attempts=2)._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "first_mission_start_timer_not_reset"
    assert result["restart"]["reason"] == "first_mission_start_timer_not_reset"
    assert result["restart"]["start"]["reason"] == "first_mission_start_timer_not_reset"
    assert starts[0]["first_island"] == "rst"
    assert segments == []


def test_runner_promotes_external_prompt_during_route_gate_restart():
    session = SimpleNamespace(
        run_id="20260606_161616_005",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    starts = []

    def segment(*args, **kwargs):
        segments.append(kwargs)
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "route_auto_start_not_allowed",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "route_auto_start_blocked_candidate": {
                        "index": 0,
                        "mission_id": "Mission_Mines",
                        "auto_route_allowed": False,
                        "auto_route_block_reason": "vetoed_mission_Mission_Mines",
                    },
                }
            ],
            "pause_guard": pause_menu(),
        }

    def start_run(*args, **kwargs):
        starts.append(kwargs)
        return {
            "status": "BLOCKED",
            "reason": "external_system_prompt_visible",
            "post_setup_start_ui": {
                "status": "OK",
                "visible_ui": "system_privacy_prompt",
                "requires_user_authorization": True,
                "external_prompt": {
                    "matched": True,
                    "kind": "macos_screen_audio_privacy_prompt",
                },
            },
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=start_run,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **_: {
            "status": "OK",
            "reason": "abandoned_to_new_game_setup",
        },
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "external_system_prompt_visible"
    assert result["restart"]["reason"] == "external_system_prompt_visible"
    assert result["restart"]["start"]["reason"] == "external_system_prompt_visible"
    assert result["restart"]["start"]["external_prompt_evidence"]["path"] == (
        "post_setup_start_ui"
    )
    assert result["restart"]["start"]["external_prompt_evidence"][
        "requires_user_authorization"
    ] is True
    assert len(segments) == 1
    assert len(starts) == 1
    assert any(
        name == "attempt_restart"
        and payload["status"] == "BLOCKED"
        and payload["reason"] == "external_system_prompt_visible"
        for name, payload in runner.telemetry.events
    )


def test_runner_preserves_first_island_mismatch_during_route_gate_restart():
    session = SimpleNamespace(
        run_id="20260606_161616_006",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    starts = []

    def segment(*args, **kwargs):
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "route_auto_start_not_allowed",
            "route_start_performed": False,
            "steps": [{"step": 0}],
            "pause_guard": pause_menu(),
        }

    def start_run(*args, **kwargs):
        starts.append(kwargs)
        return {
            "status": "BLOCKED",
            "reason": "first_island_selected_mismatch",
            "preselected_first_island": {
                "status": "OK",
                "selected_island": "detritus",
            },
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=start_run,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **_: {
            "status": "OK",
            "reason": "abandoned_to_new_game_setup",
        },
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "route_gate_restart_failed"
    assert result["restart"]["reason"] == "first_island_selected_mismatch"
    assert result["restart"]["start"]["reason"] == "first_island_selected_mismatch"
    assert starts[0]["first_island"] == "rst"
    assert any(
        name == "attempt_restart"
        and payload["status"] == "BLOCKED"
        and payload["reason"] == "first_island_selected_mismatch"
        for name, payload in runner.telemetry.events
    )


def test_runner_restarts_route_gate_when_attempt_restart_start_event_raises():
    session = SimpleNamespace(
        run_id="20260606_161616_004",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []

    class AttemptRestartStartEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "attempt_restart" and payload.get("status") == "STARTED":
                raise RuntimeError("attempt restart start event crashed")
            super().event(name, **payload)

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "route_auto_start_not_allowed",
                "route_start_performed": False,
                "steps": [{"step": 0}],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **_: {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **_: {
            "status": "OK",
            "reason": "abandoned_to_new_game_setup",
        },
        cmd_lightning_peek=completion_peek(),
    )
    runner = make_runner(max_attempts=2)
    runner.telemetry = AttemptRestartStartEventRaises()
    runner.telemetry.run_id = session.run_id

    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert result["reason"] == "target_islands_completed"
    assert len(segments) == 2
    assert result["telemetry_event_errors"] == [
        {
            "event_name": "attempt_restart",
            "exception_type": "RuntimeError",
            "error": "attempt restart start event crashed",
        }
    ]
    assert any(
        name == "attempt_restart"
        and payload["status"] == "OK"
        and payload["reason"] == "route_gate_attempt_restarted"
        for name, payload in runner.telemetry.events
    )


def test_runner_reports_route_retry_session_load_exception():
    session = SimpleNamespace(
        run_id="20260606_161616_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    load_calls = 0

    def load_session():
        nonlocal load_calls
        load_calls += 1
        if load_calls >= 7:
            raise RuntimeError("retry setup session crashed")
        return session

    commands = SimpleNamespace(
        _load_session=load_session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **_: {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "route_auto_start_not_allowed",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "route_auto_start_blocked_candidate": {
                        "index": 0,
                        "mission_id": "Mission_Mines",
                        "auto_route_allowed": False,
                        "auto_route_block_reason": "vetoed_mission_Mission_Mines",
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=lambda **_: {
            "status": "OK",
            "reason": "abandoned_to_new_game_setup",
        },
    )
    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "route_gate_restart_failed"
    assert result["restart"]["reason"] == "restart_session_load_exception"
    assert result["restart"]["setup_proof"]["reason"] == "session_load_exception"
    assert result["restart"]["setup_proof"]["error"] == "retry setup session crashed"
    assert any(
        name == "attempt_restart"
        and payload["reason"] == "restart_session_load_exception"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_when_route_gate_abandon_raises():
    session = SimpleNamespace(
        run_id="20260606_161616_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )

    def segment(**_kwargs):
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "route_auto_start_not_allowed",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "route_auto_start_blocked_candidate": {
                        "index": 0,
                        "mission_id": "Mission_Mines",
                        "auto_route_allowed": False,
                        "auto_route_block_reason": "vetoed_mission_Mission_Mines",
                    },
                }
            ],
            "pause_guard": pause_menu(),
        }

    def abandon(**_kwargs):
        raise RuntimeError("abandon helper crashed")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=abandon,
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "route_gate_restart_failed"
    restart = result["restart"]
    assert restart["reason"] == "abandon_to_setup_exception"
    assert restart["span"] == "abandon_to_setup"
    assert restart["exception_type"] == "RuntimeError"
    assert restart["error"] == "abandon helper crashed"
    assert "abandon helper crashed" in restart["traceback"]
    assert any(
        name == "command_span"
        and payload["label"] == "abandon_to_setup"
        and payload["status"] == "exception"
        and payload["error"] == "abandon helper crashed"
        for name, payload in runner.telemetry.events
    )
    assert any(
        name == "attempt_restart"
        and payload["status"] == "BLOCKED"
        and payload["reason"] == "abandon_to_setup_exception"
        and payload["error"] == "abandon helper crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_preserves_route_gate_abandon_exception_when_restart_event_raises():
    session = SimpleNamespace(
        run_id="20260606_161616_005",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )

    class AttemptRestartBlockedEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if (
                name == "attempt_restart"
                and payload.get("reason") == "abandon_to_setup_exception"
            ):
                raise RuntimeError("attempt restart blocked event crashed")
            super().event(name, **payload)

    def segment(**_kwargs):
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "route_auto_start_not_allowed",
            "route_start_performed": False,
            "steps": [{"step": 0}],
            "pause_guard": pause_menu(),
        }

    def abandon(**_kwargs):
        raise RuntimeError("abandon helper crashed")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=abandon,
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry = AttemptRestartBlockedEventRaises()
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "route_gate_restart_failed"
    assert result["restart"]["reason"] == "abandon_to_setup_exception"
    assert result["restart"]["error"] == "abandon helper crashed"
    assert result["telemetry_event_errors"] == [
        {
            "event_name": "attempt_restart",
            "exception_type": "RuntimeError",
            "error": "attempt restart blocked event crashed",
        }
    ]
    assert any(
        name == "runner_finish"
        and payload["reason"] == "route_gate_restart_failed"
        for name, payload in runner.telemetry.events
    )


@pytest.mark.parametrize(
    ("route_gate_reason", "blocked_candidate"),
    [
        (
            "route_preview_auto_start_vetoed_before_start",
            {
                "index": 1,
                "mission_id": "Mission_Tanks",
                "auto_route_allowed": False,
                "auto_route_block_reason": "vetoed_mission:Mission_Tanks",
            },
        ),
        (
            "route_preview_unassigned_multi_region_before_start",
            {
                "index": 0,
                "mission_id": "Mission_Tides",
                "auto_route_allowed": False,
                "auto_route_block_reason": "unassigned_multi_region_preview",
                "visual_region_count": 2,
            },
        ),
        (
            "route_preview_unassigned_multi_region_start_button_missing_before_start",
            {
                "index": 1,
                "mission_id": "Mission_Tides",
                "auto_route_allowed": False,
                "auto_route_block_reason": "unassigned_multi_region_preview",
                "visual_region_count": 2,
                "commit_requirement": "visible_start_mission_button",
            },
        ),
        (
            "route_preview_start_text_missing_before_start",
            {
                "index": 0,
                "mission_id": "Mission_Force",
                "auto_route_allowed": False,
                "auto_route_block_reason": (
                    "route_preview_start_text_missing_before_start"
                ),
            },
        ),
        (
            "route_preview_start_text_missing_after_dialogue",
            {
                "index": 0,
                "mission_id": "Mission_Force",
                "auto_route_allowed": False,
                "auto_route_block_reason": (
                    "route_preview_start_text_missing_after_dialogue"
                ),
            },
        ),
    ],
)
def test_runner_restarts_preview_only_route_gate_after_route_start(
    route_gate_reason,
    blocked_candidate,
):
    session = SimpleNamespace(
        run_id="20260606_161616_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "route_auto_start_not_allowed",
                "route_start_performed": True,
                "steps": [
                    {
                        "step": 2,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": route_gate_reason,
                        "route_auto_start_blocked_candidate": blocked_candidate,
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert len(abandons) == 1
    assert len(starts) == 1
    restart_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "attempt_restart"
    ]
    assert restart_events[0]["blocked_candidate"] == blocked_candidate


def test_runner_restarts_top_level_preview_only_route_gate_after_route_start():
    session = SimpleNamespace(
        run_id="20260606_224005_699",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []
    route_gate_reason = (
        "route_preview_unassigned_multi_region_start_button_missing_before_start"
    )
    blocked_candidate = {
        "index": 0,
        "mission_id": "Mission_Tides",
        "auto_route_allowed": False,
        "auto_route_block_reason": "unassigned_multi_region_preview",
        "visual_region_count": 2,
        "commit_requirement": "visible_start_mission_button",
    }

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": route_gate_reason,
                "route_start_performed": True,
                "steps": [
                    {
                        "step": 1,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": route_gate_reason,
                        "route_auto_start_blocked_candidate": blocked_candidate,
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert len(abandons) == 1
    assert len(starts) == 1
    restart_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "attempt_restart"
    ]
    assert restart_events[0]["blocked_candidate"] == blocked_candidate
    assert restart_events[0]["reason"] == "route_auto_start_not_allowed"


def test_runner_restarts_route_gate_despite_stale_resume_guard_title():
    session = SimpleNamespace(
        run_id="20260606_161616_012",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="pinnacle",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "route_auto_start_not_allowed",
                "route_start_performed": True,
                "visible_ui": {
                    "status": "OK",
                    "visible_ui": "pause_menu",
                },
                "last_attempt": {
                    "resume_guard": {
                        "post_click_visible_ui": {
                            "status": "OK",
                            "visible_ui": "title_screen",
                        }
                    }
                },
                "steps": [
                    {
                        "step": 2,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": "route_preview_auto_start_vetoed_before_start",
                        "route_auto_start_blocked_candidate": {
                            "index": 1,
                            "mission_id": "Mission_Dam",
                            "auto_route_allowed": False,
                            "auto_route_block_reason": "vetoed_mission:Mission_Dam",
                        },
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["pinnacle", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert len(abandons) == 1
    assert len(starts) == 1
    assert any(
        name == "attempt_restart"
        and payload["reason"] == "route_gate_attempt_restarted"
        for name, payload in runner.telemetry.events
    )
    assert not any(
        name == "reload_or_main_menu_visible"
        for name, _payload in runner.telemetry.events
    )


def test_runner_restarts_stale_map_deployment_bridge_gate():
    session = SimpleNamespace(
        run_id="20260606_161616_013",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []
    visible_map = {
        "status": "OK",
        "visible_ui": "island_map",
        "screenshot_path": "/tmp/rst_map.png",
    }

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "route_auto_start_not_allowed",
                "route_start_performed": False,
                "visible_ui": {
                    "status": "OK",
                    "visible_ui": "pause_menu",
                },
                "last_attempt": {
                    "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
                    "reason": "deployment_bridge_state_uncertain",
                    "snapshot": {
                        "status": "OK",
                        "phase": "unknown",
                        "turn": 0,
                        "mission_id": "Mission_Crack",
                        "active_mechs": 0,
                        "mech_count": 0,
                        "deployment_zone_count": 15,
                        "in_active_mission": True,
                        "visible_ui": visible_map,
                    },
                    "stale_active_mission_warning": {
                        "reason": "visible_map_overrides_stale_active_mission",
                        "mission_id": "Mission_Crack",
                        "visible_ui": visible_map,
                    },
                },
                "steps": [
                    {
                        "step": 0,
                        "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
                        "reason": "deployment_bridge_state_uncertain",
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["rst", "archive"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert len(abandons) == 1
    assert len(starts) == 1
    assert any(
        name == "attempt_restart"
        and payload["reason"] == "stale_map_deployment_bridge_state"
        for name, payload in runner.telemetry.events
    )
    assert not any(
        name == "deployment_bridge_state_uncertain"
        for name, _payload in runner.telemetry.events
    )


def test_runner_restarts_nested_stale_deployment_cleanup_gate():
    session = SimpleNamespace(
        run_id="20260607_170340_944",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="pinnacle",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []
    stale_snapshot = {
        "status": "OK",
        "phase": "unknown",
        "turn": 0,
        "mission_id": "Mission_SnowStorm",
        "deployment_zone_count": 12,
        "active_mechs": 0,
        "mech_count": 0,
        "in_active_mission": True,
        "bridge_heartbeat_alive": False,
        "bridge_heartbeat_stale": True,
    }
    visible_map = {
        "status": "OK",
        "visible_ui": "island_map_or_unknown",
        "screenshot_path": "/tmp/pinnacle_map.png",
    }

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "deployment_bridge_state_uncertain",
                "route_start_performed": False,
                "last_attempt": {
                    "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
                    "reason": "deployment_bridge_state_uncertain",
                    "snapshot": {**stale_snapshot, "visible_ui": visible_map},
                    "action": {
                        "deployment_visible_ui_warning": {
                            "reason": (
                                "stale_active_mission_visible_map_blocks_deployment"
                            ),
                            "visible_ui": visible_map,
                            "mission_id": "Mission_SnowStorm",
                            "route_plan": {
                                "recommendation": {
                                    "speed_route_status": {
                                        "status": "AUTO_START_BLOCKED",
                                        "reason": "stale_bridge_preview",
                                    },
                                },
                            },
                        }
                    },
                    "stale_bridge_cleanup": {
                        "status": "OK",
                        "reason": "stale_active_mission_visible_map_before_deploy",
                        "policy": "visible_map_route_discards_stale_combat_bridge_files",
                        "visible_ui": "island_map_or_unknown",
                        "snapshot": stale_snapshot,
                    },
                },
                "steps": [
                    {
                        "step": 0,
                        "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
                        "reason": "deployment_bridge_state_uncertain",
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["pinnacle", "archive"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert len(abandons) == 1
    assert len(starts) == 1
    assert any(
        name == "attempt_restart"
        and payload["reason"] == "stale_map_deployment_bridge_state"
        for name, payload in runner.telemetry.events
    )
    assert not any(
        name == "deployment_bridge_state_uncertain"
        for name, _payload in runner.telemetry.events
    )


def test_runner_restarts_stale_map_active_route_handoff_gate():
    session = SimpleNamespace(
        run_id="20260607_042336_041",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []
    snapshot = {
        "status": "OK",
        "phase": "unknown",
        "turn": 0,
        "mission_id": "Mission_Tides",
        "deployment_zone_count": 12,
        "active_mechs": 0,
        "mech_count": 0,
        "in_active_mission": True,
    }
    stale_warning = {
        "reason": "visible_map_overrides_stale_active_mission",
        "mission_id": "Mission_Tides",
        "visible_ui": "island_map",
        "policy": "block_visible_map_active_split_before_route_region_click",
    }

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "visible_island_map_with_stale_deployment_bridge",
                "route_start_performed": True,
                "steps": [
                    {
                        "step": 1,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": "visible_island_map_with_stale_deployment_bridge",
                        "stale_active_mission_warning": stale_warning,
                        "post_preview_snapshot": snapshot,
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert len(abandons) == 1
    assert len(starts) == 1
    assert any(
        name == "attempt_restart"
        and payload["reason"] == "stale_map_deployment_bridge_state"
        for name, payload in runner.telemetry.events
    )
    assert not any(
        name == "visible_island_map_with_stale_deployment_bridge"
        and payload.get("status") == "BLOCKED"
        for name, payload in runner.telemetry.events
    )


def test_runner_restarts_active_mission_before_route_region_click_gate():
    session = SimpleNamespace(
        run_id="20260607_035107_784",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []
    active_deployment = {
        "status": "OK",
        "phase": "unknown",
        "turn": 0,
        "mission_id": "Mission_Mines",
        "active_mechs": 0,
        "mech_count": 0,
        "deployment_zone_count": 12,
        "bridge_heartbeat_stale": True,
        "in_active_mission": True,
    }

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "route_preview_active_mission_before_region_click",
                "route_start_performed": True,
                "steps": [
                    {
                        "step": 1,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": "route_preview_active_mission_before_region_click",
                        "live_snapshot": active_deployment,
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert len(abandons) == 1
    assert len(starts) == 1
    assert any(
        name == "attempt_restart"
        and payload["reason"] == "route_preview_active_mission_before_region_click"
        for name, payload in runner.telemetry.events
    )
    assert not any(
        name == "route_preview_active_mission_before_region_click"
        and payload.get("status") == "BLOCKED"
        for name, payload in runner.telemetry.events
    )


def test_runner_restarts_recovered_active_mission_mismatch_gate():
    session = SimpleNamespace(
        run_id="20260607_041806_961",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []
    route_mismatch_block = {
        "status": "BLOCKED",
        "reason": "route_preview_active_mission_before_region_click",
        "expected_mission_id": "auto_start_safe_preview",
        "actual_mission_id": "Mission_Tanks",
        "turn": 0,
        "phase": "unknown",
        "deployment_zone_count": 12,
        "active_mechs": 0,
        "mech_count": 0,
        "in_active_mission": True,
    }

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "route_mission_mismatch_after_start_recovered",
                "route_start_performed": True,
                "steps": [
                    {
                        "step": 1,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": "route_mission_mismatch_after_start_recovered",
                        "route_mismatch_block": route_mismatch_block,
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert len(abandons) == 1
    assert len(starts) == 1
    assert any(
        name == "attempt_restart"
        and payload["reason"] == "route_preview_active_mission_before_region_click"
        for name, payload in runner.telemetry.events
    )
    assert not any(
        name == "route_preview_active_mission_before_region_click"
        and payload.get("status") == "BLOCKED"
        for name, payload in runner.telemetry.events
    )


def test_runner_restarts_stale_deploy_confirm_bridge_gate():
    session = SimpleNamespace(
        run_id="20260607_010101_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="rst",
        current_mission="Mission_Filler",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "deployment_bridge_state_uncertain",
                "route_start_performed": False,
                "last_attempt": {
                    "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
                    "reason": "deployment_bridge_state_uncertain",
                    "action": {
                        "action": "deploy_confirm_bridge_not_live",
                        "post_deploy_confirm_live_wait": {
                            "status": "TIMEOUT",
                            "reason": "deploy_confirm_bridge_not_live",
                        },
                    },
                    "snapshot": {
                        "status": "OK",
                        "phase": "unknown",
                        "turn": 0,
                        "mission_id": "Mission_Filler",
                        "active_mechs": 0,
                        "mech_count": 0,
                        "deployment_zone_count": 12,
                        "bridge_heartbeat_stale": True,
                        "in_active_mission": True,
                    },
                },
                "steps": [
                    {
                        "step": 0,
                        "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
                        "reason": "deployment_bridge_state_uncertain",
                        "action": "deploy_confirm_bridge_not_live",
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.current_mission = ""
        session.islands_completed = ["rst", "archive"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert len(abandons) == 1
    assert len(starts) == 1
    assert any(
        name == "attempt_restart"
        and payload["reason"] == "stale_deploy_confirm_bridge_state"
        for name, payload in runner.telemetry.events
    )
    assert not any(
        name == "deployment_bridge_state_uncertain"
        for name, _payload in runner.telemetry.events
    )


def test_runner_restarts_strict_route_mismatch_after_start():
    session = SimpleNamespace(
        run_id="20260606_161616_009",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []
    mismatch_warning = {
        "expected_mission_id": "Mission_Dam",
        "actual_mission_id": "Mission_Tides",
        "policy": "continue_loaded_playable_mission",
    }

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "route_mission_mismatch_after_start_playable",
                "route_start_performed": True,
                "steps": [
                    {
                        "step": 1,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": "route_mission_mismatch_after_start_playable",
                        "route_mismatch_warning": mismatch_warning,
                        "route_mismatch_strict_block": mismatch_warning,
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert segments[0]["route_strict_mismatch"] is True
    assert len(abandons) == 1
    assert len(starts) == 1
    restart_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "attempt_restart"
    ]
    assert restart_events[0]["reason"] == "route_mission_mismatch_after_start"
    assert restart_events[0]["route_mismatch_warning"] == mismatch_warning
    assert restart_events[-1]["reason"] == "route_gate_attempt_restarted"


def test_runner_restarts_recovered_route_mismatch_after_start():
    session = SimpleNamespace(
        run_id="20260606_231251_721",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="detritus",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []
    mismatch_block = {
        "status": "BLOCKED",
        "reason": "route_mission_mismatch_after_start",
        "expected_mission_id": "Mission_Tides",
        "actual_mission_id": "Mission_Volatile",
        "turn": 0,
        "phase": "combat_enemy",
        "deployment_zone_count": 10,
        "mech_count": 0,
        "in_active_mission": True,
    }

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "route_mission_mismatch_after_start_recovered",
                "route_start_performed": True,
                "last_route_start": {
                    "click_result": {
                        "status": "BLOCKED",
                        "reason": "route_mission_mismatch_after_start_recovered",
                        "route_mismatch_block": mismatch_block,
                        "mismatch_recovery": {
                            "status": "OK",
                            "reason": "route_mismatch_abandoned_to_safe_state",
                        },
                    },
                },
                "steps": [
                    {
                        "step": 1,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": "route_mission_mismatch_after_start_recovered",
                        "route_mismatch_block": mismatch_block,
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["detritus", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert len(abandons) == 1
    assert len(starts) == 1
    restart_events = [
        payload for name, payload in runner.telemetry.events if name == "attempt_restart"
    ]
    assert restart_events[0]["reason"] == "route_mission_mismatch_after_start"
    assert restart_events[0]["route_mismatch_warning"] == mismatch_block
    assert restart_events[-1]["reason"] == "route_gate_attempt_restarted"


def test_runner_blocks_recovered_route_mismatch_without_kia_metadata_false_positive():
    session = SimpleNamespace(
        run_id="20260606_231251_721",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="detritus",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    mismatch_block = {
        "status": "BLOCKED",
        "reason": "route_mission_mismatch_after_start",
        "expected_mission_id": "Mission_Tides",
        "actual_mission_id": "Mission_Volatile",
    }

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            raise AssertionError("exhausted route mismatch should not click/pause")
        return pause_menu()

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "route_mission_mismatch_after_start_recovered",
            "route_start_performed": True,
            "last_route_start": {
                "click_result": {
                    "status": "BLOCKED",
                    "reason": "route_mission_mismatch_after_start_recovered",
                    "route_mismatch_block": mismatch_block,
                    "mismatch_recovery": {
                        "status": "OK",
                        "reason": "route_mismatch_abandoned_to_safe_state",
                        "pause": {
                            "status": "OK",
                            "visible_ui": {
                                "status": "OK",
                                "visible_ui": "kia_panel",
                                "recommended_control": "kia_understood",
                            },
                        },
                        "final_ui": {
                            "status": "OK",
                            "visible_ui": "new_game_setup",
                        },
                    },
                },
            },
            "steps": [
                {
                    "step": 1,
                    "phase": "route_start",
                    "status": "BLOCKED",
                    "reason": "route_mission_mismatch_after_start_recovered",
                    "route_mismatch_block": mismatch_block,
                }
            ],
            "pause_guard": {
                "status": "OK",
                "visible_ui": {"status": "OK", "visible_ui": "new_game_setup"},
            },
        },
        cmd_lightning_abandon_to_setup=unexpected("cmd_lightning_abandon_to_setup"),
    )

    runner = make_runner(max_attempts=1)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "route_mission_mismatch_after_start"
    assert result["stop_token"] == "ROUTE_MISSION_MISMATCH"
    assert result["route_mismatch_warning"] == mismatch_block
    assert not any(name == "kia_detected" for name, _payload in runner.telemetry.events)


def test_runner_does_not_restart_route_gate_when_attempts_exhausted():
    session = SimpleNamespace(
        run_id="20260606_171717_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    abandoned = False
    ensure_pause_called = False

    def lightning_ui(*args, **kwargs):
        nonlocal ensure_pause_called
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensure_pause_called = True
            raise AssertionError("exhausted route gate should not click/pause")
        return pause_menu()

    def abandon(**_):
        nonlocal abandoned
        abandoned = True
        return {"status": "OK"}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "route_auto_start_not_allowed",
            "route_start_performed": False,
            "steps": [{"step": 0}],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=abandon,
    )

    runner = make_runner(max_attempts=1)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "route_auto_start_not_allowed"
    assert result["stop_token"] == "ROUTE_AUTO_START_NOT_ALLOWED"
    assert result["attempt_index"] == 1
    assert result["max_attempts"] == 1
    assert "Start Mission" in result["next_step"]
    assert abandoned is False
    assert ensure_pause_called is False
    assert "ensure_pause" not in result
    assert any(
        name == "route_auto_start_not_allowed"
        and payload["status"] == "BLOCKED"
        and payload["attempt_index"] == 1
        and payload["max_attempts"] == 1
        for name, payload in runner.telemetry.events
    )


def test_runner_reports_route_gate_before_after_segment_session_read():
    session = SimpleNamespace(
        run_id="20260606_161616_005",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    load_calls = 0

    def load_session():
        nonlocal load_calls
        load_calls += 1
        if load_calls >= 6:
            raise RuntimeError("post-route session read crashed")
        return session

    commands = SimpleNamespace(
        _load_session=load_session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "route_auto_start_not_allowed",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "route_auto_start_blocked_candidate": {
                        "index": 0,
                        "mission_id": "Mission_Mines",
                        "auto_route_allowed": False,
                        "auto_route_block_reason": "vetoed_mission_Mission_Mines",
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
    )

    runner = make_runner(max_attempts=1)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "route_auto_start_not_allowed"
    assert result["stop_token"] == "ROUTE_AUTO_START_NOT_ALLOWED"
    assert result["stop_evidence"]["path"] == ""
    assert result["attempt_index"] == 1
    assert result["max_attempts"] == 1
    assert load_calls == 5
    assert not any(
        name == "session_load_exception"
        and payload["stage"] == "after_lightning_segment"
        for name, payload in runner.telemetry.events
    )


def test_runner_ignores_earlier_preview_gate_after_later_route_map_guard():
    segment = {
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "route_preview_not_on_map_before_region_click",
        "steps": [
            {
                "step": 1,
                "phase": "route_start",
                "status": "BLOCKED",
                "reason": "route_preview_baseline_start_button_missing_before_start",
            },
            {
                "step": 2,
                "phase": "route_start",
                "status": "BLOCKED",
                "reason": "route_preview_not_on_map_before_region_click",
            },
        ],
    }

    assert lightning_runner._segment_preview_only_route_gate_evidence(segment) is None


def test_runner_treats_route_start_subcall_timeout_as_precombat_route_gate():
    segment = {
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "route_start_subcall_timeout",
        "route_start_performed": True,
        "steps": [
            {
                "step": 1,
                "phase": "route_start",
                "status": "BLOCKED",
                "reason": "route_start_subcall_timeout",
            }
        ],
    }

    evidence = lightning_runner._segment_preview_only_route_gate_evidence(segment)

    assert evidence == {
        "token": "ROUTE_AUTO_START_NOT_ALLOWED",
        "path": "reason",
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "route_start_subcall_timeout",
        "source": "preview_only_route_gate",
    }


def test_runner_treats_plain_route_mismatch_after_start_as_restart_gate():
    segment = {
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "route_mission_mismatch_after_start",
        "route_start_performed": True,
        "steps": [
            {
                "step": 0,
                "phase": "route_start",
                "status": "BLOCKED",
                "reason": "route_mission_mismatch_after_start",
                "route_mismatch_block": {
                    "expected_mission_id": "Mission_Force",
                    "actual_mission_id": "Mission_Survive",
                },
            }
        ],
    }

    assert lightning_runner._segment_route_mismatch_after_start_gate(segment) is True
    assert lightning_runner._segment_entered_combat(segment) is False


def test_runner_treats_route_preview_not_opened_as_precombat_route_gate():
    segment = {
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "route_auto_start_not_allowed",
        "route_start_performed": True,
        "steps": [
            {
                "step": 1,
                "phase": "route_start",
                "status": "BLOCKED",
                "reason": "route_preview_not_opened_before_start",
            }
        ],
    }

    evidence = lightning_runner._segment_preview_only_route_gate_evidence(segment)

    assert evidence == {
        "token": "ROUTE_AUTO_START_NOT_ALLOWED",
        "path": "steps.1.reason",
        "status": "BLOCKED",
        "reason": "route_preview_not_opened_before_start",
        "source": "preview_only_route_gate",
    }


def test_runner_treats_missing_start_text_after_dialogue_as_precombat_route_gate():
    segment = {
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "route_auto_start_not_allowed",
        "route_start_performed": True,
        "steps": [
            {
                "step": 1,
                "phase": "route_start",
                "status": "BLOCKED",
                "reason": "route_preview_start_text_missing_after_dialogue",
            }
        ],
    }

    evidence = lightning_runner._segment_preview_only_route_gate_evidence(segment)

    assert evidence == {
        "token": "ROUTE_AUTO_START_NOT_ALLOWED",
        "path": "steps.1.reason",
        "status": "BLOCKED",
        "reason": "route_preview_start_text_missing_after_dialogue",
        "source": "preview_only_route_gate",
    }


def test_runner_restarts_precombat_route_start_subcall_timeout():
    session = SimpleNamespace(
        run_id="20260606_181818_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="pinnacle",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "route_start_subcall_timeout",
                "route_start_performed": True,
                "steps": [
                    {
                        "step": 1,
                        "phase": "route_start",
                        "status": "BLOCKED",
                        "reason": "route_start_subcall_timeout",
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2)
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert len(abandons) == 1
    assert len(starts) == 1
    restart_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "attempt_restart"
    ]
    assert restart_events[0]["reason"] == "route_auto_start_not_allowed"
    assert restart_events[-1]["reason"] == "route_gate_attempt_restarted"


def test_speed_runner_restarts_unvalidated_mission_preview_gate():
    session = SimpleNamespace(
        run_id="20260606_181818_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segments = []
    abandons = []
    starts = []

    def segment(*args, **kwargs):
        segments.append(kwargs)
        if len(segments) == 1:
            return {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "mission_preview_requires_route_validation",
                "route_start_performed": True,
                "steps": [
                    {
                        "step": 0,
                        "status": "LIGHTNING_ATTEMPT_BLOCKED",
                        "reason": "mission_preview_requires_route_validation",
                    }
                ],
                "pause_guard": pause_menu(),
            }
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_verify_setup_screen=lambda **_: {"status": "PASS"},
        cmd_lightning_start_run=lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "started"},
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=lambda **kwargs: abandons.append(kwargs)
        or {"status": "OK", "reason": "abandoned_to_new_game_setup"},
        cmd_lightning_peek=completion_peek(),
    )

    runner = make_runner(max_attempts=2, mode="speed")
    runner.telemetry.run_id = session.run_id
    result = runner._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert len(segments) == 2
    assert len(abandons) == 1
    assert len(starts) == 1
    restart_events = [
        payload
        for name, payload in runner.telemetry.events
        if name == "attempt_restart"
    ]
    assert restart_events[0]["reason"] == "mission_preview_requires_route_validation"
    assert restart_events[-1]["reason"] == "route_gate_attempt_restarted"


def test_runner_treats_unvalidated_mission_preview_as_hard_gate():
    session = SimpleNamespace(
        run_id="20260606_181717_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    abandoned = False
    ensured_pause = False

    def lightning_ui(*args, **kwargs):
        nonlocal ensured_pause
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensured_pause = True
            return {"status": "OK", "reason": "already_paused"}
        return pause_menu()

    def abandon(**_):
        nonlocal abandoned
        abandoned = True
        return {"status": "OK"}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "mission_preview_requires_route_validation",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "status": "LIGHTNING_ATTEMPT_BLOCKED",
                    "reason": "mission_preview_requires_route_validation",
                }
            ],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=abandon,
    )

    result = make_runner(max_attempts=2)._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "mission_preview_requires_route_validation"
    assert result["stop_token"] == "MISSION_PREVIEW_REQUIRES_ROUTE_VALIDATION"
    assert abandoned is False
    assert ensured_pause is False
    assert "Start Mission" in result["next_step"]


def test_runner_does_not_pause_unvalidated_mission_preview_stop():
    session = SimpleNamespace(
        run_id="20260606_181717_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    abandoned = False

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            raise RuntimeError("pause helper crashed")
        return pause_menu()

    def abandon(**_):
        nonlocal abandoned
        abandoned = True
        return {"status": "OK"}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "mission_preview_requires_route_validation",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "status": "LIGHTNING_ATTEMPT_BLOCKED",
                    "reason": "mission_preview_requires_route_validation",
                }
            ],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=abandon,
    )
    runner = make_runner(max_attempts=2)

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "mission_preview_requires_route_validation"
    assert result["stop_token"] == "MISSION_PREVIEW_REQUIRES_ROUTE_VALIDATION"
    assert "ensure_pause" not in result
    assert abandoned is False
    assert not any(name == "ensure_pause_exception" for name, _ in runner.telemetry.events)


@pytest.mark.parametrize(
    ("segment_reason", "expected_stop_token", "expected_reason"),
    [
        (
            "deployment_bridge_state_uncertain",
            "DEPLOYMENT_BRIDGE_STATE_UNCERTAIN",
            "deployment_bridge_state_uncertain",
        ),
        (
            "visible_island_map_without_bridge",
            "VISIBLE_ISLAND_MAP_WITHOUT_BRIDGE",
            "visible_island_map_without_bridge",
        ),
        (
            "visible_island_map_with_stale_deployment_bridge",
            "VISIBLE_ISLAND_MAP_WITH_STALE_DEPLOYMENT_BRIDGE",
            "visible_island_map_with_stale_deployment_bridge",
        ),
        (
            "ambiguous_route_start_region",
            "AMBIGUOUS_ROUTE_START_REGION",
            "ambiguous_route_start_region",
        ),
    ],
)
def test_runner_promotes_map_deployment_and_route_ambiguity_without_pause(
    segment_reason,
    expected_stop_token,
    expected_reason,
):
    session = SimpleNamespace(
        run_id="20260606_181717_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segment_calls = 0
    ensured_pause = False

    def segment(**_):
        nonlocal segment_calls
        segment_calls += 1
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": segment_reason,
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
                    "reason": segment_reason,
                    "snapshot": {
                        "visible_ui": {
                            "status": "OK",
                            "visible_ui": "island_map_or_unknown",
                        }
                    },
                }
            ],
            "pause_guard": pause_menu(),
        }

    def lightning_ui(*args, **kwargs):
        nonlocal ensured_pause
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensured_pause = True
            return {"status": "OK", "reason": "already_paused"}
        return pause_menu()

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
        cmd_lightning_abandon_to_setup=unexpected("cmd_lightning_abandon_to_setup"),
    )

    runner = make_runner(max_attempts=2)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == expected_reason
    assert result["stop_token"] == expected_stop_token
    assert segment_calls == 1
    assert ensured_pause is False
    assert "ensure_pause" not in result
    assert any(
        name == expected_reason
        and payload["status"] == "BLOCKED"
        and payload["stop_token"] == expected_stop_token
        for name, payload in runner.telemetry.events
    )


def test_runner_does_not_restart_safety_gate():
    session = SimpleNamespace(
        run_id="20260606_181818_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    abandoned = False

    def abandon(**_):
        nonlocal abandoned
        abandoned = True
        return {"status": "OK"}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "SAFETY_BLOCKED",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "action": "combat_loop",
                    "combat_loop_reason": "SAFETY_BLOCKED",
                }
            ],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=abandon,
    )

    result = make_runner(max_attempts=2)._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "safety_blocked"
    assert result["stop_token"] == "SAFETY_BLOCKED"
    assert result["stop_evidence"] == {
        "token": "SAFETY_BLOCKED",
        "path": "",
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "SAFETY_BLOCKED",
    }
    assert "dirty-frontier" in result["next_step"]
    assert abandoned is False


def test_runner_prefers_nested_safety_evidence_over_segment_wrapper():
    session = SimpleNamespace(
        run_id="20260606_181818_008",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    ensured_pause = False

    def lightning_ui(*args, **kwargs):
        nonlocal ensured_pause
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensured_pause = True
            raise AssertionError("safety block should not pause")
        return pause_menu()

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "SAFETY_BLOCKED",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "action": "combat_loop",
                    "combat_loop": {
                        "turns": [
                            {
                                "status": "SAFETY_BLOCKED",
                                "reason": "dirty frontier has mech_hp_loss",
                            }
                        ]
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=unexpected("cmd_lightning_abandon_to_setup"),
    )

    result = make_runner(max_attempts=2)._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "safety_blocked"
    assert result["stop_token"] == "SAFETY_BLOCKED"
    assert result["stop_evidence"] == {
        "token": "SAFETY_BLOCKED",
        "path": "steps.0.combat_loop.turns.0",
        "status": "SAFETY_BLOCKED",
        "reason": "dirty frontier has mech_hp_loss",
    }
    assert "dirty-frontier" in result["next_step"]
    assert ensured_pause is False


def test_runner_prefers_safety_block_over_title_like_pause_guard_noise():
    session = SimpleNamespace(
        run_id="20260606_181818_009",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Tides",
        mission_index=1,
        islands_completed=[],
    )

    def title_like_pause_guard():
        return {
            "status": "OK",
            "reason": "title_screen_visible",
            "decision": {
                "status": "OK",
                "reason": "title_screen_visible",
                "pause_allowed": False,
            },
            "live_snapshot": {
                "status": "OK",
                "phase": "combat_player",
                "active_mechs": 3,
                "mech_count": 3,
                "in_active_mission": True,
                "mission_id": "Mission_Tides",
            },
            "visible_ui": {
                "status": "OK",
                "visible_ui": "title_screen",
            },
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "action": "deploy_then_combat",
                    "combat_loop_reason": "SAFETY_BLOCKED",
                    "combat_loop": {
                        "status": "LIGHTNING_LOOP_STOPPED",
                        "reason": "SAFETY_BLOCKED",
                        "turns": [
                            {
                                "status": "SAFETY_BLOCKED",
                                "reason": "mech_on_danger",
                            }
                        ],
                    },
                }
            ],
            "pause_guard": title_like_pause_guard(),
        },
        cmd_lightning_abandon_to_setup=unexpected("cmd_lightning_abandon_to_setup"),
    )

    runner = make_runner(max_attempts=2)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "safety_blocked"
    assert result["stop_token"] == "SAFETY_BLOCKED"
    assert result["stop_evidence"] == {
        "token": "SAFETY_BLOCKED",
        "path": "steps.0.combat_loop.turns.0",
        "status": "SAFETY_BLOCKED",
        "reason": "mech_on_danger",
    }
    assert "menu_evidence" not in result
    assert any(
        name == "safety_blocked"
        and payload["status"] == "BLOCKED"
        and payload["stop_token"] == "SAFETY_BLOCKED"
        for name, payload in runner.telemetry.events
    )
    assert not any(
        name == "reload_or_main_menu_visible"
        for name, _payload in runner.telemetry.events
    )


@pytest.mark.parametrize(
    ("nested_reason", "expected_reason", "expected_token", "next_step_phrase"),
    [
        (
            "FAILED_OBJECTIVE: objective loss",
            "failed_objective_detected",
            "FAILED_OBJECTIVE",
            "failed objective",
        ),
        ("KIA: pilot killed", "kia_detected", "KIA", "KIA"),
        (
            "TIMELINE_COLLAPSE: timeline lost",
            "timeline_collapse_detected",
            "TIMELINE_COLLAPSE",
            "timeline collapse",
        ),
    ],
)
def test_runner_promotes_terminal_stop_evidence_without_pause_or_restart(
    nested_reason,
    expected_reason,
    expected_token,
    next_step_phrase,
):
    session = SimpleNamespace(
        run_id="20260606_181818_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    abandon_called = False
    ensure_pause_called = False

    def lightning_ui(*args, **kwargs):
        nonlocal ensure_pause_called
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensure_pause_called = True
            raise AssertionError("terminal stop evidence should not click/pause")
        return pause_menu()

    def abandon(**_):
        nonlocal abandon_called
        abandon_called = True
        raise AssertionError("terminal stop evidence should not restart")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "action": "combat_loop",
                    "combat_loop": {
                        "turns": [
                            {
                                "status": "BLOCKED",
                                "reason": nested_reason,
                            }
                        ]
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=abandon,
    )

    runner = make_runner(max_attempts=2)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == expected_reason
    assert result["stop_token"] == expected_token
    assert result["stop_evidence"] == {
        "token": expected_token,
        "path": "steps.0.combat_loop.turns.0",
        "status": "BLOCKED",
        "reason": nested_reason,
    }
    assert next_step_phrase in result["next_step"]
    assert ensure_pause_called is False
    assert abandon_called is False
    assert any(
        name == expected_reason
        and payload["status"] == "BLOCKED"
        and payload["stop_token"] == expected_token
        for name, payload in runner.telemetry.events
    )


@pytest.mark.parametrize(
    ("nested_status", "expected_reason", "expected_token", "next_step_phrase"),
    [
        ("RESEARCH_REQUIRED", "research_required", "RESEARCH_REQUIRED", "research_next"),
        ("POST_ENEMY_BLOCKED", "post_enemy_blocked", "POST_ENEMY", "post-enemy"),
        (
            "THREAT_AUDIT_BLOCKED",
            "threat_audit_blocked",
            "THREAT_AUDIT",
            "threat-audit",
        ),
        ("INVESTIGATE", "investigation_required", "INVESTIGATE", "diagnosis"),
    ],
)
def test_runner_promotes_named_stop_sign_gates(
    nested_status,
    expected_reason,
    expected_token,
    next_step_phrase,
):
    session = SimpleNamespace(
        run_id="20260606_181818_004",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    ensured_pause = False

    def lightning_ui(*args, **kwargs):
        nonlocal ensured_pause
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensured_pause = True
            raise AssertionError("stop-sign gates should not click/pause")
        return pause_menu()

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "action": "combat_loop",
                    "combat_loop": {
                        "turns": [
                            {
                                "status": nested_status,
                                "reason": f"{nested_status}: evidence required",
                            }
                        ]
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=unexpected("cmd_lightning_abandon_to_setup"),
    )

    runner = make_runner(max_attempts=2)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == expected_reason
    assert result["stop_token"] == expected_token
    assert result["stop_evidence"]["path"] == "steps.0.combat_loop.turns.0"
    assert next_step_phrase in result["next_step"]
    assert ensured_pause is False
    assert any(
        name == expected_reason
        and payload["status"] == "BLOCKED"
        and payload["stop_token"] == expected_token
        for name, payload in runner.telemetry.events
    )


def test_runner_promotes_string_carried_research_stop_sign_without_pause():
    session = SimpleNamespace(
        run_id="20260606_181818_005",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    ensured_pause = False

    def lightning_ui(*args, **kwargs):
        nonlocal ensured_pause
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensured_pause = True
            raise AssertionError("string-carried research gate should not pause")
        return pause_menu()

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "action": "combat_loop",
                    "combat_loop": {
                        "turns": [
                            {
                                "stdout": (
                                    "bridge read completed\n"
                                    "RESEARCH_REQUIRED: unknown Vek weapon"
                                )
                            }
                        ]
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=unexpected("cmd_lightning_abandon_to_setup"),
    )

    runner = make_runner(max_attempts=2)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "research_required"
    assert result["stop_token"] == "RESEARCH_REQUIRED"
    assert result["stop_evidence"] == {
        "token": "RESEARCH_REQUIRED",
        "path": "steps.0.combat_loop.turns.0.stdout",
        "text": "bridge read completed\nRESEARCH_REQUIRED: unknown Vek weapon",
    }
    assert "research_next" in result["next_step"]
    assert ensured_pause is False


def test_runner_promotes_string_carried_post_enemy_investigation_specifically():
    session = SimpleNamespace(
        run_id="20260606_181818_006",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    ensured_pause = False

    def lightning_ui(*args, **kwargs):
        nonlocal ensured_pause
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensured_pause = True
            raise AssertionError("post-enemy gate should not pause")
        return pause_menu()

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "action": "combat_loop",
                    "combat_loop": {
                        "turns": [
                            {
                                "stdout": (
                                    "turn settled\n"
                                    "INVESTIGATE_POST_ENEMY: post-enemy audit mismatch"
                                )
                            }
                        ]
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=unexpected("cmd_lightning_abandon_to_setup"),
    )

    runner = make_runner(max_attempts=2)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "post_enemy_blocked"
    assert result["stop_token"] == "POST_ENEMY"
    assert result["stop_evidence"] == {
        "token": "POST_ENEMY",
        "path": "steps.0.combat_loop.turns.0.stdout",
        "text": (
            "turn settled\n"
            "INVESTIGATE_POST_ENEMY: post-enemy audit mismatch"
        ),
    }
    assert "post-enemy" in result["next_step"]
    assert ensured_pause is False


@pytest.mark.parametrize(
    ("stdout", "expected_reason", "expected_token", "next_step_phrase"),
    [
        (
            "post-enemy audit mismatch",
            "post_enemy_blocked",
            "POST_ENEMY",
            "post-enemy",
        ),
        (
            "threat audit blocked: still targeted",
            "threat_audit_blocked",
            "THREAT_AUDIT",
            "threat-audit",
        ),
        (
            "safety blocked by dirty frontier",
            "safety_blocked",
            "SAFETY_BLOCKED",
            "dirty-frontier",
        ),
    ],
)
def test_runner_promotes_string_carried_prose_stop_signs(
    stdout,
    expected_reason,
    expected_token,
    next_step_phrase,
):
    session = SimpleNamespace(
        run_id="20260606_181818_007",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    ensured_pause = False

    def lightning_ui(*args, **kwargs):
        nonlocal ensured_pause
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensured_pause = True
            raise AssertionError("prose stop sign should not pause")
        return pause_menu()

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "action": "combat_loop",
                    "combat_loop": {
                        "turns": [
                            {
                                "stdout": stdout,
                            }
                        ]
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=unexpected("cmd_lightning_abandon_to_setup"),
    )

    runner = make_runner(max_attempts=2)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == expected_reason
    assert result["stop_token"] == expected_token
    assert result["stop_evidence"] == {
        "token": expected_token,
        "path": "steps.0.combat_loop.turns.0.stdout",
        "text": stdout,
    }
    assert next_step_phrase in result["next_step"]
    assert ensured_pause is False


def test_runner_blocks_desync_without_pause_or_restart():
    session = SimpleNamespace(
        run_id="20260606_181818_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    abandoned = False

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            raise AssertionError("desync block should not click/pause")
        return pause_menu()

    def abandon(**_):
        nonlocal abandoned
        abandoned = True
        return {"status": "OK"}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "route_start_performed": False,
            "steps": [
                {
                    "step": 0,
                    "action": "combat_loop",
                    "combat_loop": {
                        "turns": [
                            {
                                "status": "DESYNC",
                                "reason": "per_sub_action_desync_attack_a1",
                            }
                        ]
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=abandon,
    )

    runner = make_runner(max_attempts=2)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "combat_desync"
    assert result["stop_token"] == "DESYNC"
    assert result["stop_evidence"] == {
        "token": "DESYNC",
        "path": "steps.0.combat_loop.turns.0",
        "status": "DESYNC",
        "reason": "per_sub_action_desync_attack_a1",
    }
    assert "fresh read plus solve" in result["next_step"]
    assert abandoned is False
    assert any(
        name == "combat_desync"
        and payload["status"] == "BLOCKED"
        and payload["stop_evidence"]["path"] == "steps.0.combat_loop.turns.0"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_immediately_on_segment_repeated_progress_state():
    session = SimpleNamespace(
        run_id="20260606_191919_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="",
        mission_index=0,
        islands_completed=[],
    )
    segment_calls = 0
    ensure_pause_called = False

    def segment(**_):
        nonlocal segment_calls
        segment_calls += 1
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "repeated_progress_state",
            "steps": [
                {
                    "step": 0,
                    "status": "LIGHTNING_ATTEMPT_STOPPED",
                    "reason": "combat_loop_returned",
                }
            ],
            "pause_guard": pause_menu(),
        }

    def lightning_ui(*args, **kwargs):
        nonlocal ensure_pause_called
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensure_pause_called = True
            raise AssertionError("repeated progress state should not click/pause")
        return pause_menu()

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
    )

    runner = make_runner(max_attempts=3)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "repeated_progress_state"
    assert result["stop_token"] == "REPEATED_PROGRESS_STATE"
    assert segment_calls == 1
    assert ensure_pause_called is False
    assert "fresh read/classify" in result["next_step"]
    assert any(
        name == "repeated_progress_state"
        and payload["status"] == "BLOCKED"
        and payload["stop_token"] == "REPEATED_PROGRESS_STATE"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_bridge_snapshot_unavailable_without_pause_or_restart():
    session = SimpleNamespace(
        run_id="20260606_191919_005",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    abandon_called = False
    ensure_pause_called = False

    def lightning_ui(*args, **kwargs):
        nonlocal ensure_pause_called
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensure_pause_called = True
            raise AssertionError("bridge snapshot block should not click/pause")
        return pause_menu()

    def abandon(**_):
        nonlocal abandon_called
        abandon_called = True
        raise AssertionError("bridge snapshot block should not restart")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "combat_loop_returned",
            "steps": [
                {
                    "step": 0,
                    "action": "combat_loop",
                    "combat_loop": {
                        "turns": [
                            {
                                "status": "BLOCKED",
                                "reason": (
                                    "BRIDGE_SNAPSHOT_UNAVAILABLE: "
                                    "no live bridge state"
                                ),
                            }
                        ]
                    },
                }
            ],
            "pause_guard": pause_menu(),
        },
        cmd_lightning_abandon_to_setup=abandon,
    )

    runner = make_runner(max_attempts=2)
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "bridge_snapshot_unavailable"
    assert result["stop_token"] == "BRIDGE_SNAPSHOT_UNAVAILABLE"
    assert result["stop_evidence"] == {
        "token": "BRIDGE_SNAPSHOT_UNAVAILABLE",
        "path": "steps.0.combat_loop.turns.0",
        "status": "BLOCKED",
        "reason": "BRIDGE_SNAPSHOT_UNAVAILABLE: no live bridge state",
    }
    assert "fresh read plus solve" in result["next_step"]
    assert ensure_pause_called is False
    assert abandon_called is False
    assert any(
        name == "bridge_snapshot_unavailable"
        and payload["status"] == "BLOCKED"
        and payload["stop_token"] == "BRIDGE_SNAPSHOT_UNAVAILABLE"
        for name, payload in runner.telemetry.events
    )


def test_runner_reports_session_load_exception_when_max_segments_progress_read_fails():
    session = SimpleNamespace(
        run_id="20260606_191919_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    ensure_pause_called = False

    def load_session():
        return session

    def lightning_ui(*args, **kwargs):
        nonlocal ensure_pause_called
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensure_pause_called = True
            return {"status": "OK", "reason": "already_paused"}
        if control == "classify":
            return {"status": "OK", "visible_ui": "island_map"}
        return pause_menu()

    commands = SimpleNamespace(
        _load_session=load_session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "parked_safe",
            "pause_guard": pause_menu(),
        },
    )

    runner = make_runner(max_segments=1)
    original_load_session_or_block = runner._load_session_or_block

    def load_session_or_block(commands_arg, stage, **context):
        if stage == "max_segments_reached":
            block = {
                "status": "BLOCKED",
                "reason": "session_load_exception",
                "stage": stage,
                "exception_type": "RuntimeError",
                "error": "final progress read crashed",
                "traceback": "Traceback ... final progress read crashed",
                "next_step": "Do not trust stale progress.",
            }
            runner.telemetry.event("session_load_exception", **block)
            return None, block
        return original_load_session_or_block(commands_arg, stage, **context)

    runner._load_session_or_block = load_session_or_block
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "max_segments_reached"
    assert result["islands_completed"] == []
    assert result["session_load"]["reason"] == "session_load_exception"
    assert result["session_load"]["stage"] == "max_segments_reached"
    assert result["session_load"]["error"] == "final progress read crashed"
    assert ensure_pause_called is True
    assert any(
        name == "session_load_exception"
        and payload["stage"] == "max_segments_reached"
        and payload["error"] == "final progress read crashed"
        for name, payload in runner.telemetry.events
    )


def test_load_session_block_preserves_result_when_event_write_raises():
    class SessionLoadEventRaises(FakeTelemetry):
        def event(self, name: str, **payload):
            if name == "session_load_exception":
                raise RuntimeError("session load event write crashed")
            super().event(name, **payload)

    def load_session():
        raise RuntimeError("loop session reader crashed")

    runner = make_runner()
    runner.telemetry = SessionLoadEventRaises()
    commands = SimpleNamespace(_load_session=load_session)

    session, block = runner._load_session_or_block(
        commands,
        "segment_loop_start",
        segment_index=3,
    )

    assert session is None
    assert block is not None
    assert block["status"] == "BLOCKED"
    assert block["reason"] == "session_load_exception"
    assert block["stage"] == "segment_loop_start"
    assert block["error"] == "loop session reader crashed"
    assert block["context"]["segment_index"] == 3
    assert block["telemetry_event_errors"] == [
        {
            "event_name": "session_load_exception",
            "exception_type": "RuntimeError",
            "error": "session load event write crashed",
        }
    ]
    assert runner.telemetry.events == []


def test_runner_blocks_on_non_dict_segment_return_without_span_exception():
    session = SimpleNamespace(
        run_id="20260606_191919_004",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=lambda **_: None,
    )

    runner = make_runner()
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "segment_failed"
    assert result["segment_failure"] == {
        "status": "ERROR",
        "reason": "command_returned_non_dict",
        "span": "lightning_segment",
        "value_type": "NoneType",
        "value_repr": "None",
    }
    assert result["segment"]["span"] == "lightning_segment"
    assert result["segment"]["value_type"] == "NoneType"
    assert any(
        name == "command_span"
        and payload["label"] == "lightning_segment"
        and payload["status"] == "finish"
        and payload["result_status"] == "ERROR"
        and payload["result_reason"] == "command_returned_non_dict"
        for name, payload in runner.telemetry.events
    )
    assert not any(
        name == "lightning_segment_exception"
        for name, _payload in runner.telemetry.events
    )


@pytest.mark.parametrize("segment_status", ["ERROR", "BLOCKED"])
def test_runner_blocks_immediately_on_tokenless_segment_failure(segment_status):
    session = SimpleNamespace(
        run_id="20260606_191919_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_calls = 0
    ensure_pause_called = False

    def segment(**_):
        nonlocal segment_calls
        segment_calls += 1
        return {
            "status": segment_status,
            "reason": "classification_helper_failed",
            "error": "screenshot failed",
            "screenshot_path": "/tmp/segment_failure.png",
            "pause_guard": pause_menu(),
        }

    def lightning_ui(*args, **kwargs):
        nonlocal ensure_pause_called
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "ensure_pause":
            ensure_pause_called = True
        return pause_menu()

    runner = make_runner()
    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
    )

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "segment_failed"
    assert result["segment_failure"] == {
        "status": segment_status,
        "reason": "classification_helper_failed",
        "error": "screenshot failed",
        "screenshot_path": "/tmp/segment_failure.png",
    }
    assert "do not loop" in result["next_step"]
    assert segment_calls == 1
    assert ensure_pause_called is False
    assert any(
        name == "segment_failed"
        and payload["segment_failure"]["status"] == segment_status
        for name, payload in runner.telemetry.events
    )


def test_runner_propagates_blocked_post_segment_panel():
    session = SimpleNamespace(
        run_id="20260606_121414_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=2,
        islands_completed=[],
    )
    segment_calls = 0
    classify_after_segment = {"blocked": False}

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        if control == "classify" and classify_after_segment["blocked"]:
            return {"status": "OK", "visible_ui": "title_screen"}
        if control == "classify":
            return pause_menu()
        return {"status": "OK"}

    def segment(*args, **kwargs):
        nonlocal segment_calls
        segment_calls += 1
        classify_after_segment["blocked"] = True
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "LIGHTNING_ATTEMPT_PANEL_READY",
            "pause_guard": pause_menu(),
        }

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_segment=segment,
    )

    runner = make_runner()
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "post_segment_panel_blocked"
    assert result["panel"]["reason"] == "unexpected_menu_or_setup_visible_mid_run"
    assert segment_calls == 1
    assert any(
        name == "post_segment_panel_blocked"
        and payload["reason"] == "unexpected_menu_or_setup_visible_mid_run"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_on_preflight_gate():
    session = SimpleNamespace(
        run_id="20260606_131313_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_called = False

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: {
            "status": "FAIL",
            "issues": ["RESEARCH_REQUIRED: unknown unit type"],
        },
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_segment=segment,
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "research_required"
    assert result["preflight"]["reason"] == "research_required"
    assert result["preflight"]["blocking_warning"] == "research_required"
    assert "research_next" in result["preflight"]["next_step"]
    assert segment_called is False


def test_runner_reports_nested_stop_evidence_for_preflight_gate():
    session = SimpleNamespace(
        run_id="20260606_131313_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_called = False

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: {
            "status": "PASS",
            "warnings": [],
            "issues": [],
            "checks": {
                "research": {
                    "status": "BLOCKED",
                    "reason": "RESEARCH_REQUIRED: unknown Vek attack",
                }
            },
        },
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_segment=segment,
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "research_required"
    assert result["preflight"]["reason"] == "research_required"
    assert result["preflight"]["stop_token"] == "RESEARCH_REQUIRED"
    assert result["preflight"]["stop_evidence"] == {
        "token": "RESEARCH_REQUIRED",
        "path": "checks.research",
        "status": "BLOCKED",
        "reason": "RESEARCH_REQUIRED: unknown Vek attack",
    }
    assert "research_next" in result["preflight"]["next_step"]
    assert segment_called is False


def test_runner_prefers_specific_nested_preflight_stop_over_generic_parent():
    session = SimpleNamespace(
        run_id="20260606_131313_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_called = False

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: {
            "status": "INVESTIGATE",
            "reason": "see nested evidence",
            "warnings": [],
            "issues": [],
            "post_enemy_result": {
                "status": "INVESTIGATE_POST_ENEMY",
                "reason": "post-enemy audit mismatch",
            },
        },
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_segment=segment,
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "post_enemy_blocked"
    assert result["preflight"]["reason"] == "post_enemy_blocked"
    assert result["preflight"]["stop_token"] == "POST_ENEMY"
    assert result["preflight"]["stop_evidence"] == {
        "token": "POST_ENEMY",
        "path": "post_enemy_result",
        "status": "INVESTIGATE_POST_ENEMY",
        "reason": "post-enemy audit mismatch",
    }
    assert "post-enemy" in result["preflight"]["next_step"]
    assert segment_called is False


def test_runner_blocks_on_research_warning_from_preflight():
    session = SimpleNamespace(
        run_id="20260606_131314_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_called = False

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: {
            "status": "PASS",
            "warnings": ["requires_research: true for unknown mission pawn"],
            "issues": [],
        },
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_segment=segment,
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "research_required"
    assert result["preflight"]["reason"] == "research_required"
    assert result["preflight"]["blocking_warning"] == "requires_research"
    assert "research_next" in result["preflight"]["next_step"]
    assert segment_called is False


def test_runner_keeps_setup_preflight_issues_generic():
    session = SimpleNamespace(
        run_id="20260606_131314_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_called = False

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: {
            "status": "FAIL",
            "warnings": [],
            "issues": ["save difficulty mismatch"],
        },
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_segment=segment,
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "preflight_failed"
    assert result["preflight"]["reason"] == "preflight_failed"
    assert result["preflight"]["blocking_warning"] == "save difficulty"
    assert result["preflight"]["next_step"] is None
    assert segment_called is False


@pytest.mark.parametrize("visible_ui", ["title_screen", "new_game_setup"])
def test_runner_blocks_when_menu_or_setup_reappears_mid_run(visible_ui):
    session = SimpleNamespace(
        run_id="20260606_131414_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_called = False

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_ui=lambda *args, **kwargs: {
            "status": "OK",
            "visible_ui": visible_ui,
            "recommended_control": "title_new_game"
            if visible_ui == "title_screen"
            else "setup_start",
        },
        cmd_lightning_segment=segment,
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_blocked"
    assert result["panel"]["reason"] == "unexpected_menu_or_setup_visible_mid_run"
    assert result["panel"]["visible_name"] == visible_ui
    assert segment_called is False


def test_runner_blocks_when_failed_objective_reward_visible_mid_run():
    session = SimpleNamespace(
        run_id="20260606_131413_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Train",
        mission_index=1,
        islands_completed=[],
    )
    controls: list[str] = []
    segment_called = False

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        controls.append(str(control))
        if control == "classify":
            return {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
                "objective_texts": [
                    "Region Secured",
                    "Protect the Train (Failed)",
                ],
                "screenshot_path": "/tmp/failed_objective_midrun.png",
            }
        return {"status": "OK", "reason": f"{control}_clicked"}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_segment=segment,
    )

    runner = make_runner()
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_blocked"
    assert result["panel"]["reason"] == "terminal_outcome_visible"
    assert result["panel"]["visible_name"] == "reward_panel"
    assert result["panel"]["terminal_evidence"]["path"] == "objective_texts.1"
    assert result["panel"]["visible_ui"]["screenshot_path"] == (
        "/tmp/failed_objective_midrun.png"
    )
    assert segment_called is False
    assert "handle_screen" not in controls


def test_runner_blocks_when_visible_classification_fails_mid_run():
    session = SimpleNamespace(
        run_id="20260606_131412_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_called = False

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_ui=lambda *args, **kwargs: {
            "status": "ERROR",
            "error": "screenshot failed: no game window",
        },
        cmd_lightning_segment=segment,
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_blocked"
    assert result["panel"]["reason"] == "screen_classification_failed"
    assert result["panel"]["visible_ui"]["error"] == "screenshot failed: no game window"
    assert segment_called is False


def test_runner_blocks_when_visible_classification_raises_mid_run():
    session = SimpleNamespace(
        run_id="20260606_131414_002",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_called = False

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    def lightning_ui(*_args, **_kwargs):
        raise RuntimeError("classifier crashed")

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_segment=segment,
    )
    runner = make_runner()

    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_panel_blocked"
    assert result["panel"]["reason"] == "screen_classification_exception"
    assert result["panel"]["span"] == "classify_visible"
    assert result["panel"]["exception_type"] == "RuntimeError"
    assert result["panel"]["error"] == "classifier crashed"
    assert "classifier crashed" in result["panel"]["traceback"]
    assert segment_called is False
    assert any(
        name == "screen_classification_exception"
        and payload["error"] == "classifier crashed"
        for name, payload in runner.telemetry.events
    )


def test_runner_skips_visible_classify_after_deployment_confirmed_pause():
    session = SimpleNamespace(
        run_id="20260606_131414_003",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    ui_calls: list[str] = []
    segments = iter(
        [
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "deployment_confirmed_paused",
                "game_seconds": 26.0,
                "game_timer": "0:00:26",
            },
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "SAFETY_BLOCKED",
                "safety": {"status": "BLOCKED"},
            },
        ]
    )
    segment_calls = 0

    def lightning_ui(*args, **kwargs):
        control = kwargs.get("control") or (args[0] if args else None)
        ui_calls.append(str(control))
        return pause_menu()

    def segment(**_):
        nonlocal segment_calls
        segment_calls += 1
        return next(segments)

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_ui=lightning_ui,
        cmd_lightning_segment=segment,
    )

    runner = make_runner()
    result = runner._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "safety_blocked"
    assert segment_calls == 2
    assert ui_calls == ["classify"]
    assert any(
        name == "visible_panel_skipped"
        and payload["reason"] == "deployment_confirmed_paused"
        for name, payload in runner.telemetry.events
    )


def test_runner_blocks_when_system_privacy_prompt_reappears_mid_run():
    session = SimpleNamespace(
        run_id="20260606_131415_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_called = False

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_ui=lambda *args, **kwargs: {
            "status": "OK",
            "visible_ui": "system_privacy_prompt",
            "recommended_control": None,
            "requires_user_authorization": True,
            "screenshot_path": "/tmp/system_prompt_midrun.png",
            "external_prompt": {
                "status": "OK",
                "matched": True,
                "score": 1.0,
                "kind": "macos_screen_audio_privacy_prompt",
                "checks": {"button_gray": 1.5},
                "regions": {"large_pixel_dump": {"pixels": 999999}},
            },
        },
        cmd_lightning_segment=segment,
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "external_system_prompt_visible"
    assert result["panel"]["reason"] == "external_system_prompt_visible"
    assert result["panel"]["visible_name"] == "system_privacy_prompt"
    visible_ui = result["panel"]["visible_ui"]
    assert visible_ui["screenshot_path"] == "/tmp/system_prompt_midrun.png"
    assert visible_ui["requires_user_authorization"] is True
    assert visible_ui["external_prompt"]["kind"] == "macos_screen_audio_privacy_prompt"
    assert "regions" not in visible_ui["external_prompt"]
    assert segment_called is False


def test_runner_blocks_when_save_loadout_is_not_blitzkrieg(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_141414_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_called = False

    def fake_load_game_state(_profile):
        return SimpleNamespace(
            difficulty=0,
            grid_power=7,
            grid_power_max=7,
            mechs=["PunchMech", "TankMech", "ArtiMech"],
            weapons=["Prime_Punchmech", "Brute_Tankmech", "Ranged_Artillerymech"],
        )

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)
    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_segment=segment,
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "setup_state_unverified"
    assert "ElectricMech" in " ".join(result["setup_proof"]["issues"])
    assert segment_called is False


def test_runner_blocks_when_resumed_save_advanced_content_mismatches():
    session = SimpleNamespace(
        run_id="20260606_141415_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_called = False

    def segment(**_):
        nonlocal segment_called
        segment_called = True
        return {}

    commands = SimpleNamespace(
        _load_session=lambda: session,
        _read_save_advanced_content=lambda _profile: {
            "status": "OK",
            "source": "saveData",
            "state": {
                "new_enemies": 1,
                "new_missions": 1,
                "new_equip": 1,
                "new_abilities": 1,
            },
        },
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu(),
        cmd_lightning_segment=segment,
    )

    result = make_runner(advanced_content="off")._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "setup_state_unverified"
    issue_text = " ".join(result["setup_proof"]["issues"]).lower()
    assert "advanced content state mismatch" in issue_text
    assert result["setup_proof"]["advanced_content"]["source"] == "saveData"
    assert segment_called is False


def test_runner_accepts_active_mission_loadout_fallback(monkeypatch):
    session = SimpleNamespace(
        run_id="20260606_151515_001",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        current_island="archive",
        current_mission="Mission_Test",
        mission_index=1,
        islands_completed=[],
    )
    segment_kwargs: list[dict] = []

    class FakeMission:
        def get_mechs(self):
            return [
                SimpleNamespace(
                    type="ElectricMech",
                    primary_weapon="Prime_Lightning_A",
                    secondary_weapon="",
                ),
                SimpleNamespace(
                    type="WallMech",
                    primary_weapon="Brute_Grapple",
                    secondary_weapon="",
                ),
                SimpleNamespace(
                    type="RockartMech",
                    primary_weapon="Ranged_Rockthrow",
                    secondary_weapon="",
                ),
            ]

    def fake_load_game_state(_profile):
        return SimpleNamespace(
            difficulty=0,
            grid_power=7,
            grid_power_max=7,
            mechs=[],
            weapons=[],
            active_mission=FakeMission(),
        )

    def segment(*args, **kwargs):
        segment_kwargs.append(kwargs)
        session.islands_completed = ["archive", "rst"]
        return {
            "status": "LIGHTNING_SEGMENT_STOPPED",
            "reason": "max_steps_reached",
            "pause_guard": pause_menu(),
        }

    monkeypatch.setattr(lightning_runner, "load_game_state", fake_load_game_state)
    commands = SimpleNamespace(
        _load_session=lambda: session,
        cmd_lightning_pause_guard=lambda **_: pause_menu(),
        cmd_lightning_preflight=lambda **_: preflight_pass(),
        cmd_lightning_ui=lambda *args, **kwargs: pause_menu()
        if (kwargs.get("control") or (args[0] if args else None)) == "classify"
        else {"status": "OK"},
        cmd_lightning_segment=segment,
        cmd_lightning_peek=completion_peek(),
    )

    result = make_runner()._run_inner(commands)

    assert result["status"] == "SUCCESS"
    assert segment_kwargs
