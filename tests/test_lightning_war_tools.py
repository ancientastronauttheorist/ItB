from __future__ import annotations

import json
import os
from types import SimpleNamespace

from src.loop import commands
from src.loop.session import ActiveSolution, RunSession, SolverAction
from src.strategy.mission_picker import score_mission


def _lightning_peek_resume_control() -> str:
    return "menu_continue" if os.name == "nt" else "pause_menu_escape"


def test_abandon_pilot_slot_targets_first_carry_forward_portrait():
    from src.control.mac_click import list_known_window_controls

    control = list_known_window_controls()["abandon_pilot_slot"]

    assert control["window_x"] == 500
    assert control["window_y"] == 329


def test_lightning_war_weight_overlay_penalizes_pod_pickup():
    session = RunSession(
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    weights, applied = commands._achievement_weight_overlay(
        session,
        {
            "pod_uncollected": -100.0,
            "pod_proximity": 50.0,
            "pod_collected": 0.0,
            "spawn_blocked": 1000.0,
        },
    )

    assert "lightning_war" in applied
    assert weights["pod_uncollected"] == 0.0
    assert weights["pod_proximity"] == 0.0
    assert weights["pod_collected"] == -4000.0
    assert weights["spawn_blocked"] == 1600.0


def test_lightning_war_routing_penalizes_forest_fire_friction():
    result = score_mission(
        {"mission_id": "Mission_ForestFire", "bonus_objective_ids": []},
        {"achievement"},
        grid_power=7,
        routing="lightning_war",
    )

    assert result["score"] <= -120
    assert any("Forest Fire post-enemy" in line for line in result["rationale_lines"])


def test_lightning_drain_known_behavior_research_marks_speed_entry_done(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        research_queue=[
            {
                "status": "pending",
                "type": "Bouncer1",
                "kind": "behavior_novelty",
                "diff_field": "alive",
                "diff_predicted": False,
                "diff_actual": True,
            }
        ],
    )

    monkeypatch.setattr(
        "src.solver.unknown_detector._load_known",
        lambda: {"pawn_types": {"Bouncer1"}},
    )

    resolved = commands._lightning_drain_known_behavior_research(session)

    assert resolved == ["Bouncer1"]
    entry = session.research_queue[0]
    assert entry["status"] == "done"
    assert entry["result"]["source"] == "lightning_auto_resolved"


def test_lightning_drain_known_behavior_research_requires_lightning_target(monkeypatch):
    session = RunSession(
        run_id="normal",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Chain Attack"],
        research_queue=[
            {
                "status": "pending",
                "type": "Bouncer1",
                "kind": "behavior_novelty",
            }
        ],
    )

    monkeypatch.setattr(
        "src.solver.unknown_detector._load_known",
        lambda: {"pawn_types": {"Bouncer1"}},
    )

    assert commands._lightning_drain_known_behavior_research(session) == []
    assert session.research_queue[0]["status"] == "pending"


def test_lightning_loop_clicks_end_turn_plan(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = {"auto_turn": 0, "clicks": 0}
    wait_polls = []

    def fake_auto_turn(**kwargs):
        calls["auto_turn"] += 1
        wait_polls.append(kwargs.get("wait_poll_interval"))
        if calls["auto_turn"] == 1:
            return {
                "status": "PLAN",
                "turn": 1,
                "actions_completed": 3,
                "score": 123,
                "batch": [{"type": "left_click", "x": 341, "y": 152}],
            }
        return {"status": "TERMINAL_OR_MISSION_END", "turn": 2}

    def fake_click(plan):
        calls["clicks"] += 1
        return {"status": "OK", "x": 341, "y": 152}

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "combat_screen"},
    )
    monkeypatch.setattr(commands, "_click_end_turn_from_plan_result", fake_click)
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda turn_result: {"status": "OK", "reason": "phase_changed"},
    )

    result = commands.cmd_lightning_loop(max_turns=3, pause_before_solve=False)

    assert result["reason"] == "TERMINAL_OR_MISSION_END"
    assert result["end_turn_clicks"] == 1
    assert result["turns"][0]["auto_turn_wall_seconds"] >= 0
    assert result["turns"][0]["turn_wall_seconds"] >= 0
    assert wait_polls == [0.35, 0.35]
    assert calls == {"auto_turn": 2, "clicks": 1}


def test_lightning_quiet_call_counts_output_without_result_json(capsys):
    def noisy_command():
        commands._print_result({"status": "OK", "bulk": "x" * 10_000})
        print("small progress line")
        return {"status": "OK"}

    result, output = commands._lightning_quiet_call(noisy_command, quiet=True)

    assert result == {"status": "OK"}
    assert output == {
        "captured_stdout_lines": 1,
        "captured_stdout_chars": len("small progress line\n"),
    }
    assert capsys.readouterr().out == ""


def test_lightning_loop_quiet_compacts_last_turn_result(monkeypatch, capsys):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    def fake_auto_turn(**kwargs):
        return {
            "status": "PLAN",
            "turn": 1,
            "actions_completed": 3,
            "score": 123,
            "batch": [{"type": "left_click", "window_x": 126, "window_y": 120}],
            "codex_computer_use_batch": [{"x": 126, "y": 120}],
            "fuzzy_detections": [{"large": "x" * 10_000}],
            "threat_audit": {"entries": [{}, {}]},
            "debug_bulk": "x" * 10_000,
        }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)

    result = commands.cmd_lightning_loop(
        max_turns=1,
        click_end_turn=False,
        quiet=True,
        pause_before_solve=False,
    )

    assert result["reason"] == "end_turn_plan_ready_no_click"
    assert result["last_turn_result"]["batch"][0]["window_x"] == 126
    assert result["last_turn_result"]["fuzzy_detections_count"] == 1
    assert result["last_turn_result"]["threat_audit_entries"] == 2
    assert "debug_bulk" not in result["last_turn_result"]
    assert "LIGHTNING LOOP START" not in capsys.readouterr().out


def test_lightning_loop_passes_dirty_consent_to_first_turn_only(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    def fake_auto_turn(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                "status": "PLAN",
                "turn": 4,
                "actions_completed": 3,
                "batch": [{"type": "left_click", "x": 341, "y": 152}],
            }
        return {"status": "TERMINAL_OR_MISSION_END", "turn": 5}

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "combat_screen"},
    )
    monkeypatch.setattr(
        commands,
        "_click_end_turn_from_plan_result",
        lambda plan: {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda turn_result: {"status": "OK", "reason": "phase_changed"},
    )

    result = commands.cmd_lightning_loop(
        max_turns=2,
        allow_dirty_plan=True,
        candidate_rank=7,
        dirty_consent_id="abc123",
        allow_protected_objective_loss=True,
        allow_objective_loss=True,
        pause_before_solve=False,
    )

    assert result["reason"] == "TERMINAL_OR_MISSION_END"
    assert calls[0]["allow_dirty_plan"] is True
    assert calls[0]["candidate_rank"] == 7
    assert calls[0]["dirty_consent_id"] == "abc123"
    assert calls[0]["allow_protected_objective_loss"] is True
    assert calls[0]["allow_objective_loss"] is True
    assert calls[1]["allow_dirty_plan"] is False
    assert calls[1]["candidate_rank"] is None
    assert calls[1]["dirty_consent_id"] is None


def test_lightning_loop_solves_when_pause_guard_reports_live_combat(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    def fake_auto_turn(**kwargs):
        calls.append(kwargs)
        return {
            "status": "PLAN",
            "turn": 3,
            "actions_completed": 3,
            "batch": [{"type": "left_click", "window_x": 126, "window_y": 120}],
        }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(
        commands,
        "_lightning_wait_for_player_turn_and_pause",
        lambda **kwargs: {
            "status": "BLOCKED",
            "reason": "live_combat_phase",
            "snapshot": {"phase": "combat_player", "active_mechs": 3},
        },
    )
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)

    result = commands.cmd_lightning_loop(
        max_turns=1,
        click_end_turn=False,
        quiet=True,
        pause_before_solve=True,
    )

    assert result["reason"] == "end_turn_plan_ready_no_click"
    assert calls[0]["wait_for_turn"] is False
    assert calls[0]["resume_before_execute"] is False


def test_lightning_loop_passes_speed_loss_policy_to_every_turn(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    def fake_auto_turn(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                "status": "PLAN",
                "turn": 1,
                "actions_completed": 3,
                "batch": [{"type": "left_click", "x": 341, "y": 152}],
            }
        return {"status": "TERMINAL_OR_MISSION_END", "turn": 2}

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "combat_screen"},
    )
    monkeypatch.setattr(
        commands,
        "_click_end_turn_from_plan_result",
        lambda plan: {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda turn_result: {"status": "OK", "reason": "phase_changed"},
    )

    result = commands.cmd_lightning_loop(
        max_turns=2,
        lightning_speed_loss_policy=True,
        pause_before_solve=False,
    )

    assert result["reason"] == "TERMINAL_OR_MISSION_END"
    assert [call["lightning_speed_loss_policy"] for call in calls] == [True, True]


def test_lightning_ui_clicks_known_control_dry_run():
    result = commands.cmd_lightning_ui("deploy_confirm", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "deploy_confirm"
    assert result["window_x"] == 106
    assert result["window_y"] == 164


def test_lightning_ui_clicks_deploy_slot_alias_dry_run():
    result = commands.cmd_lightning_ui("deploy1", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "deploy_slot_1"
    assert result["window_x"] == 102
    assert result["window_y"] == 388


def test_lightning_ui_clicks_understood_alias_dry_run():
    result = commands.cmd_lightning_ui("understood", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "modal_understood"
    assert result["window_x"] == 666
    assert result["window_y"] == 555


def test_lightning_ui_clicks_panel_continue_alias_dry_run():
    result = commands.cmd_lightning_ui("perfect_continue", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "panel_continue"
    assert result["window_x"] == 846
    assert result["window_y"] == 550


def test_lightning_ui_clicks_ceo_continue_alias_dry_run():
    result = commands.cmd_lightning_ui("ceo_continue", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "reward_continue"
    assert result["window_x"] == 1005
    assert result["window_y"] == 654


def test_lightning_ui_clicks_pod_open_alias_dry_run():
    result = commands.cmd_lightning_ui("open_pod", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "pod_open_door"
    assert result["window_x"] == 965
    assert result["window_y"] == 485


def test_lightning_ui_clicks_dialogue_textbox_alias_dry_run():
    result = commands.cmd_lightning_ui("dialogue", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "dialogue_textbox"
    assert result["window_x"] == 250
    assert result["window_y"] == 205


def test_lightning_ui_clicks_mission_preview_board_alias_dry_run():
    result = commands.cmd_lightning_ui("start_mission", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "mission_preview_board"
    assert result["window_x"] == 848
    assert result["window_y"] == 448


def test_lightning_ui_clicks_perfect_grid_reward_alias_dry_run():
    result = commands.cmd_lightning_ui("grid_reward", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "perfect_reward_grid"
    assert result["window_x"] == 817
    assert result["window_y"] == 480


def test_lightning_ui_clicks_leave_island_alias_dry_run():
    result = commands.cmd_lightning_ui("next_island", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "leave_island"
    assert result["window_x"] == 641
    assert result["window_y"] == 704


def test_lightning_ui_clicks_leave_confirm_alias_dry_run():
    result = commands.cmd_lightning_ui("confirm_leave", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "leave_confirm_yes"
    assert result["window_x"] == 568
    assert result["window_y"] == 444


def test_lightning_ui_clicks_rst_island_alias_dry_run():
    result = commands.cmd_lightning_ui("rst", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "island_rst"
    assert result["window_x"] == 345
    assert result["window_y"] == 508


def test_lightning_ui_clicks_known_control_sequence_dry_run():
    result = commands.cmd_lightning_ui("menu_continue+rst", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert [item["name"] for item in result["sequence"]] == [
        "menu_continue",
        "island_rst",
    ]
    assert result["sequence"][1]["window_x"] == 345


def test_lightning_ui_burst_to_rst_dry_run():
    result = commands.cmd_lightning_ui("to_rst", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["burst"] == "to_rst"
    assert [item["name"] for item in result["sequence"]] == [
        "menu_continue",
        "island_rst",
    ]


def test_lightning_ui_burst_region_secured_to_pause_dry_run():
    result = commands.cmd_lightning_ui("region_secured_to_pause", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["burst"] == "region_secured_to_pause"
    assert [item["name"] for item in result["sequence"]] == [
        "menu_continue",
        "reward_continue",
        "pause",
    ]


def test_lightning_ui_burst_first_island_to_rst_dry_run():
    result = commands.cmd_lightning_ui("first_island_to_rst_pause", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["burst"] == "first_island_to_rst_pause"
    assert [item["name"] for item in result["sequence"]] == [
        "menu_continue",
        "leave_island",
        "leave_confirm_yes",
        "island_rst",
        "bottom_continue",
        "pause",
    ]


def test_lightning_ui_burst_perfect_full_to_rst_dry_run():
    result = commands.cmd_lightning_ui(
        "first_island_perfect_full_to_rst_pause",
        dry_run=True,
    )

    assert result["status"] == "DRY_RUN"
    assert result["burst"] == "first_island_perfect_full_to_rst_pause"
    assert [item["name"] for item in result["sequence"]] == [
        "menu_continue",
        "panel_continue",
        "perfect_reward_grid",
        "leave_island",
        "leave_confirm_yes",
        "island_rst",
        "bottom_continue",
        "pause",
    ]


def test_lightning_ui_ensure_pause_dry_run_plans_pause(monkeypatch):
    session = RunSession(run_id="lw", squad="Blitzkrieg", difficulty=0)

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map_or_unknown"},
    )

    result = commands.cmd_lightning_ui("ensure_pause", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["planned_control"] == "pause"
    assert result["visible_ui"]["visible_ui"] == "island_map_or_unknown"


def test_lightning_ui_ensure_pause_blocks_deployment_screen(monkeypatch):
    session = RunSession(run_id="lw", squad="Blitzkrieg", difficulty=0)

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "deployment_screen",
            "recommended_control": "deploy_confirm",
            "non_pauseable": True,
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_write_guard",
        lambda *args, **kwargs: {"status": "BLOCKED", "path": "guard.json"},
    )

    result = commands.cmd_lightning_ui("ensure_pause")

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visible_ui_is_not_pauseable"
    assert "lightning_segment" in result["next_step"]


def test_lightning_ui_ensure_pause_recognizes_pause_menu(monkeypatch):
    session = RunSession(run_id="lw", squad="Blitzkrieg", difficulty=0)

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
            },
        ]
    )
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        commands,
        "_lightning_write_guard",
        lambda *args, **kwargs: {"status": "OK", "path": "guard.json"},
    )

    result = commands.cmd_lightning_ui("ensure_pause")

    assert result["status"] == "OK"
    assert result["already_paused"] is True
    assert result["reason"] == "already_paused"


def test_lightning_ui_ensure_pause_verifies_clicked_pause(monkeypatch):
    session = RunSession(run_id="lw", squad="Blitzkrieg", difficulty=0)
    visible_states = iter(
        [
            {"status": "OK", "visible_ui": "island_map"},
            {"status": "OK", "visible_ui": "pause_menu"},
        ]
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control: {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_write_guard",
        lambda *args, **kwargs: {"status": kwargs["guard_status"], "path": "guard.json"},
    )

    result = commands.cmd_lightning_ui("ensure_pause")

    assert result["status"] == "OK"
    assert result["reason"] == "pause_clicked"
    assert result["pause_verified"] is True
    assert result["pause_verify"]["visible_ui"] == "pause_menu"


def test_lightning_pause_guard_clicks_safe_panel(monkeypatch):
    session = RunSession(run_id="lw", squad="Blitzkrieg", difficulty=0)
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {"status": "OK", "visible_ui": "pause_menu"},
        ]
    )
    clicks = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(commands, "_lightning_live_snapshot", lambda: {"status": "NO_BRIDGE"})
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control: clicks.append(control) or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_write_guard",
        lambda *args, **kwargs: {"status": kwargs["guard_status"], "path": "guard.json"},
    )

    result = commands.cmd_lightning_pause_guard(seconds=0, once=True)

    assert result["status"] == "OK"
    assert result["reason"] == "pause_clicked"
    assert clicks == ["pause"]
    assert result["last_poll"]["pause_verified"] is True


def test_lightning_pause_guard_blocks_live_combat_panel():
    result = commands._lightning_pause_guard_decision(
        {
            "status": "OK",
            "visible_ui": "reward_panel",
            "recommended_control": "reward_continue",
        },
        {
            "status": "OK",
            "phase": "combat_player",
            "turn": 4,
            "active_mechs": 3,
            "deployment_zone_count": 0,
            "in_active_mission": True,
        },
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "live_combat_phase"
    assert result["pause_allowed"] is False


def test_lightning_pause_guard_allows_visible_map_over_stale_deployment():
    result = commands._lightning_pause_guard_decision(
        {
            "status": "OK",
            "visible_ui": "island_map",
            "recommended_control": None,
        },
        {
            "status": "OK",
            "phase": "unknown",
            "turn": 0,
            "deployment_zone_count": 10,
            "in_active_mission": True,
            "island_map_count": 0,
        },
    )

    assert result["status"] == "OK"
    assert result["reason"] == "safe_ui_pause_available"
    assert result["pause_allowed"] is True


def test_lightning_pause_after_stop_uses_timer_pause_guard(monkeypatch):
    calls = []

    monkeypatch.setattr(
        commands,
        "_lightning_timer_pause_guard_once",
        lambda **kwargs: calls.append(kwargs)
        or {"status": "OK", "reason": "pause_clicked"},
    )

    result = commands._lightning_pause_after_stop(
        {"status": "LIGHTNING_ATTEMPT_PANEL_READY", "next_step": "clear panel"},
        enabled=True,
        click_ui=True,
        dry_run=False,
        reason="mission_complete_panel",
    )

    assert result["pause_guard"]["reason"] == "pause_clicked"
    assert calls == [
        {
            "dry_run": False,
            "click_ui": True,
            "reason": "mission_complete_panel",
        }
    ]
    assert "Check pause_guard" in result["next_step"]


def test_lightning_ui_ensure_pause_blocks_when_click_not_verified(monkeypatch):
    session = RunSession(run_id="lw", squad="Blitzkrieg", difficulty=0)
    visible_states = iter(
        [
            {"status": "OK", "visible_ui": "island_map"},
            {"status": "OK", "visible_ui": "island_map"},
        ]
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control: {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_write_guard",
        lambda *args, **kwargs: {"status": kwargs["guard_status"], "path": "guard.json"},
    )

    result = commands.cmd_lightning_ui("ensure_pause")

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "pause_not_verified"
    assert result["pause_verified"] is False
    assert result["pause_verify"]["visible_ui"] == "island_map"


def test_lightning_ui_clear_tail_to_pause_resumes_clears_and_pauses(monkeypatch):
    session = RunSession(run_id="lw", squad="Blitzkrieg", difficulty=0)
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
            },
        ]
    )
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        commands,
        "_lightning_press_pause_escape",
        lambda **kwargs: calls.append("pause_menu_escape")
        or {"status": "OK", "control": "pause_menu_escape"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: calls.append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_clear_visible_panel_chain",
        lambda **kwargs: calls.append("clear_chain")
        or {"status": "OK", "reason": "panel_chain_cleared", "steps": []},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: calls.append("ensure_pause")
        or {"status": "OK", "reason": "pause_clicked"},
    )

    result = commands.cmd_lightning_ui("clear_tail_pause")

    assert result["status"] == "OK"
    assert result["reason"] == "tail_cleared_and_paused"
    expected_resume = "menu_continue" if os.name == "nt" else "pause_menu_escape"
    assert calls == [expected_resume, "clear_chain", "ensure_pause"]


def test_lightning_ui_clear_tail_blocks_when_resume_stays_paused(monkeypatch):
    session = RunSession(run_id="lw", squad="Blitzkrieg", difficulty=0)
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "pause_menu",
            "recommended_control": "menu_continue",
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: calls.append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_press_pause_escape",
        lambda **kwargs: calls.append("pause_menu_escape")
        or {"status": "OK", "control": "pause_menu_escape"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_clear_visible_panel_chain",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("should not clear while still paused")
        ),
    )

    result = commands.cmd_lightning_ui("clear_tail_pause")

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "resume_from_pause_not_verified"
    expected_resume = "menu_continue" if os.name == "nt" else "pause_menu_escape"
    assert calls == [expected_resume]


def test_lightning_ui_handle_screen_clicks_visible_panel(monkeypatch):
    calls = []

    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "promotion_panel",
            "recommended_control": "modal_understood",
        },
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: calls.append((control, kwargs))
        or {"status": "OK", "control": control},
    )

    result = commands.cmd_lightning_ui("handle_screen")

    assert result["status"] == "OK"
    assert result["control"] == "modal_understood"
    assert calls == [("modal_understood", {"dry_run": False})]


def test_lightning_ui_handle_screen_confirms_leave_island(monkeypatch):
    calls = []

    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "island_complete_leave",
            "recommended_control": "leave_island",
        },
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: calls.append((control, kwargs))
        or {"status": "OK", "control": control},
    )

    result = commands.cmd_lightning_ui("handle_screen")

    assert result["status"] == "OK"
    assert result["control"] == "leave_island"
    assert result["fallback_control"] == "leave_confirm_yes"
    assert calls == [
        ("leave_island", {"dry_run": False}),
        ("leave_confirm_yes", {"dry_run": False}),
    ]


def test_lightning_peek_dry_run_plans_micro_burst(monkeypatch, tmp_path):
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "pause_menu",
            "recommended_control": "menu_continue",
        },
    )

    result = commands.cmd_lightning_peek(
        "turn3",
        out_dir=str(tmp_path),
        dry_run=True,
    )

    assert result["status"] == "DRY_RUN"
    assert result["planned_controls"] == [
        _lightning_peek_resume_control(),
        "screenshot",
        "pause",
    ]
    assert result["screenshot_path"].endswith("_turn3.png")


def test_lightning_peek_refuses_when_not_paused(monkeypatch):
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "island_map_or_unknown",
            "recommended_control": None,
        },
    )

    result = commands.cmd_lightning_peek("not_paused")

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "not_in_pause_menu"


def test_lightning_peek_captures_between_continue_and_pause(monkeypatch, tmp_path):
    clicks = []
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
        ]
    )

    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click._get_window_bounds",
        lambda app_name: {"x": 10, "y": 20, "width": 1280, "height": 748},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: clicks.append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_press_pause_escape",
        lambda **kwargs: clicks.append("pause_menu_escape")
        or {"status": "OK", "control": "pause_menu_escape"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_capture_window_screenshot",
        lambda path, **kwargs: {"status": "OK", "screenshot_path": str(path)},
    )
    monkeypatch.setattr(
        commands,
        "_classify_lightning_ui_image",
        lambda path: {"status": "OK", "visible_ui": "island_map_or_unknown"},
    )

    result = commands.cmd_lightning_peek(
        "evidence",
        out_dir=str(tmp_path),
        note="micro peek test",
    )

    assert result["status"] == "OK"
    assert clicks == [_lightning_peek_resume_control(), "pause"]
    assert result["evidence_ui"]["visible_ui"] == "island_map_or_unknown"
    assert result["note_written"] is True
    assert (tmp_path / "notes.md").exists()


def test_lightning_peek_pauses_even_when_capture_fails(monkeypatch, tmp_path):
    clicks = []
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
        ]
    )

    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click._get_window_bounds",
        lambda app_name: {"x": 10, "y": 20, "width": 1280, "height": 748},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: clicks.append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_press_pause_escape",
        lambda **kwargs: clicks.append("pause_menu_escape")
        or {"status": "OK", "control": "pause_menu_escape"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_capture_window_screenshot",
        lambda path, **kwargs: {"status": "ERROR", "error": "boom"},
    )

    result = commands.cmd_lightning_peek("capture_fail", out_dir=str(tmp_path))

    assert result["status"] == "ERROR"
    assert result["reason"] == "screenshot_failed"
    assert clicks == [_lightning_peek_resume_control(), "pause"]
    assert result["note_written"] is False


def test_lightning_peek_blocks_when_pause_not_verified(monkeypatch, tmp_path):
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
            },
        ]
    )

    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click._get_window_bounds",
        lambda app_name: {"x": 10, "y": 20, "width": 1280, "height": 748},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_capture_window_screenshot",
        lambda path, **kwargs: {"status": "OK", "screenshot_path": str(path)},
    )
    monkeypatch.setattr(
        commands,
        "_classify_lightning_ui_image",
        lambda path: {"status": "OK", "visible_ui": "island_map_or_unknown"},
    )

    result = commands.cmd_lightning_peek("not_repaused", out_dir=str(tmp_path))

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "pause_not_verified_after_peek"


def test_lightning_parse_timer_seconds_variants():
    assert commands._lightning_parse_timer_seconds("0:37:09") == 2229
    assert commands._lightning_parse_timer_seconds("37:09") == 2229
    assert commands._lightning_parse_timer_seconds("0h 37m 09s") == 2229
    assert commands._lightning_parse_timer_seconds("bad") is None


def test_lightning_parse_visible_timer_ocr_variants():
    assert commands._lightning_parse_visible_timer_ocr_seconds("Oh 23m 495") == 1429
    assert commands._lightning_parse_visible_timer_ocr_seconds("0h 03m 04s") == 184
    assert commands._lightning_parse_visible_timer_ocr_seconds("bad") is None


def test_lightning_save_timer_reads_current_time_ms(tmp_path):
    profile_dir = tmp_path / "profile_Alpha"
    profile_dir.mkdir()
    (profile_dir / "profile.lua").write_text(
        'Profile = {["timer"] = 524288000.000000, '
        '["current"] = {["time"] = 999000.000000,}, }'
    )
    (profile_dir / "saveData.lua").write_text(
        'GameData = {["current"] = {["score"] = 0, '
        '["time"] = 454666.937500,}, }'
    )
    (profile_dir / "undoSave.lua").write_text(
        'GameData = {["current"] = {["score"] = 0, '
        '["time"] = 800000.000000,}, }'
    )

    result = commands._lightning_read_save_game_timer(profile_dir=profile_dir)

    assert result["status"] == "OK"
    assert result["source"] == "profile_current_time"
    assert result["game_timer_ms"] == 999000.0
    assert result["game_timer"] == "0:16:39"
    assert [candidate["source"] for candidate in result["candidates"]] == [
        "saveData_current_time",
        "profile_current_time",
        "undoSave_current_time",
    ]


def test_lightning_save_timer_ignores_stale_undo_after_fresh_run_advances(tmp_path):
    profile_dir = tmp_path / "profile_Alpha"
    profile_dir.mkdir()
    (profile_dir / "saveData.lua").write_text(
        'GameData = {["current"] = {["time"] = 33909.707000,}, }'
    )
    (profile_dir / "profile.lua").write_text(
        'Profile = {["current"] = {["time"] = 33909.707000,}, }'
    )
    (profile_dir / "undoSave.lua").write_text(
        'GameData = {["current"] = {["time"] = 16177021.000000,}, }'
    )

    result = commands._lightning_read_save_game_timer(profile_dir=profile_dir)

    assert result["status"] == "OK"
    assert result["source"] == "saveData_current_time"
    assert result["game_timer"] == "0:00:34"
    assert result["ignored_candidates"] == [
        {
            "source": "undoSave_current_time",
            "path": str(profile_dir / "undoSave.lua"),
            "game_timer_ms": 16177021.0,
            "game_seconds": 16177.021,
            "game_timer": "4:29:37",
            "reason": "stale_undo_after_new_timeline",
        }
    ]


def test_lightning_visible_pause_timer_reads_ocr(monkeypatch, tmp_path):
    screenshot = tmp_path / "pause.png"
    screenshot.write_text("placeholder")
    monkeypatch.setattr(
        commands,
        "_classify_lightning_ui_image",
        lambda path: {"status": "OK", "visible_ui": "perfect_reward_choice"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ocr_texts_from_image",
        lambda path: {
            "status": "OK",
            "texts": ["Timeline Playtime", "Oh 23m 495", "Easy"],
        },
    )

    result = commands._lightning_visible_pause_timer_from_screenshot(screenshot)

    assert result["status"] == "OK"
    assert result["source"] == "visible_pause_menu_timer"
    assert result["game_seconds"] == 1429.0
    assert result["game_timer"] == "0:23:49"
    assert result["ocr_text"] == "Oh 23m 495"
    assert result["classifier_visible_ui"] == "perfect_reward_choice"
    assert result["timeline_label_seen"] is True


def test_lightning_game_timer_budget_blocks_at_thirty_minutes(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    monkeypatch.setattr(
        commands,
        "_lightning_read_save_game_timer",
        lambda profile="Alpha": {
            "status": "OK",
            "source": "saveData_current_time",
            "game_seconds": 1800.0,
            "game_timer": "0:30:00",
        },
    )

    result = commands._lightning_budget_summary(session)

    assert result["status"] == "EXCEEDED"
    assert result["game_status"] == "EXCEEDED"
    assert result["remaining_game_seconds"] == 0.0


def _patch_clean_lightning_preflight(monkeypatch, settings):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_read_settings_lua", lambda: settings)
    monkeypatch.setattr(commands, "_read_save_file_difficulty", lambda profile: 0)
    monkeypatch.setattr(
        commands,
        "_lightning_read_save_game_timer",
        lambda profile="Alpha": {
            "status": "OK",
            "source": "saveData_current_time",
            "game_seconds": 600.0,
            "game_timer": "0:10:00",
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_read_visible_pause_timer",
        lambda: {"status": "UNKNOWN", "reason": "not_visible"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_research_gate_status",
        lambda session: {
            "status": "PASS",
            "pending_research_count": 0,
            "pending_research": [],
            "drained_stale_research": [],
        },
    )
    monkeypatch.setattr(commands, "_pending_diagnosis_entries", lambda session: [])
    monkeypatch.setattr(commands, "_post_enemy_block_result", lambda session: None)


def test_lightning_preflight_passes_fast_settings(monkeypatch):
    _patch_clean_lightning_preflight(
        monkeypatch,
        {"timer_ui": 1, "speed": 1057},
    )

    result = commands.cmd_lightning_preflight()

    assert result["status"] == "PASS"
    assert result["settings"]["speed_fast_ready"] is True


def test_lightning_preflight_blocks_slow_settings_speed(monkeypatch):
    _patch_clean_lightning_preflight(
        monkeypatch,
        {"timer_ui": 1, "speed": 500},
    )

    result = commands.cmd_lightning_preflight()

    assert result["status"] == "FAIL"
    assert result["settings"]["speed_fast_ready"] is False
    assert any("below Lightning War fast threshold" in issue for issue in result["issues"])


def test_lightning_preflight_blocks_exceeded_game_timer(monkeypatch):
    _patch_clean_lightning_preflight(
        monkeypatch,
        {"timer_ui": 1, "speed": 1057},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_read_save_game_timer",
        lambda profile="Alpha": {
            "status": "OK",
            "source": "saveData_current_time",
            "game_seconds": 1800.001,
            "game_timer": "0:30:00",
        },
    )

    result = commands.cmd_lightning_preflight()

    assert result["status"] == "FAIL"
    assert result["game_budget"]["game_status"] == "EXCEEDED"
    assert any("in-game timer" in issue for issue in result["issues"])


def test_lightning_preflight_uses_visible_timer_when_save_is_stale(monkeypatch):
    _patch_clean_lightning_preflight(
        monkeypatch,
        {"timer_ui": 1, "speed": 1057},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_read_save_game_timer",
        lambda profile="Alpha": {
            "status": "OK",
            "source": "profile_current_time",
            "game_seconds": 1219.0,
            "game_timer": "0:20:19",
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_read_visible_pause_timer",
        lambda: {
            "status": "OK",
            "source": "visible_pause_menu_timer",
            "game_seconds": 1429.0,
            "game_timer": "0:23:49",
            "ocr_text": "Oh 23m 495",
        },
    )

    result = commands.cmd_lightning_preflight()

    assert result["status"] == "WARN"
    assert result["effective_timer"]["source"] == "visible_pause_menu_timer"
    assert result["game_budget"]["game_timer"] == "0:23:49"
    assert any("visible pause-menu timer" in warning for warning in result["warnings"])


def test_lightning_preflight_blocks_exceeded_visible_timer(monkeypatch):
    _patch_clean_lightning_preflight(
        monkeypatch,
        {"timer_ui": 1, "speed": 1057},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_read_visible_pause_timer",
        lambda: {
            "status": "OK",
            "source": "visible_pause_menu_timer",
            "game_seconds": 1801.0,
            "game_timer": "0:30:01",
            "ocr_text": "Oh 30m 015",
        },
    )

    result = commands.cmd_lightning_preflight()

    assert result["status"] == "FAIL"
    assert result["effective_timer"]["source"] == "visible_pause_menu_timer"
    assert result["game_budget"]["game_status"] == "EXCEEDED"


def test_lightning_refine_rejects_terminal_panel_during_live_combat(monkeypatch):
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 4,
            "active_mechs": 3,
            "deployment_zone_count": 0,
            "in_active_mission": True,
        },
    )

    result = commands._lightning_refine_visible_ui_with_bridge(
        {
            "status": "OK",
            "visible_ui": "perfect_reward_choice",
            "recommended_control": "perfect_reward_grid",
        }
    )

    assert result["visible_ui"] == "combat_screen"
    assert result["recommended_control"] is None
    assert result["terminal_panel_false_positive"] is True


def test_lightning_refine_rejects_terminal_panel_during_enemy_animation(monkeypatch):
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 4,
            "active_mechs": 0,
            "deployment_zone_count": 0,
            "in_active_mission": True,
        },
    )

    result = commands._lightning_refine_visible_ui_with_bridge(
        {
            "status": "OK",
            "visible_ui": "perfect_reward_choice",
            "recommended_control": "perfect_reward_grid",
        }
    )

    assert result["visible_ui"] == "combat_screen"
    assert result["recommended_control"] is None
    assert result["terminal_panel_false_positive"] is True


def test_lightning_mark_records_timer_delta(monkeypatch, tmp_path):
    from PIL import Image

    source = tmp_path / "source.png"
    Image.new("RGB", (10, 10), (0, 0, 0)).save(source)
    monkeypatch.setattr(
        commands,
        "_classify_lightning_ui_image",
        lambda path: {
            "status": "OK",
            "visible_ui": "pause_menu",
            "recommended_control": "menu_continue",
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 1,
            "mission_id": "Mission_Tides",
            "grid_power": "6/7",
        },
    )

    first = commands.cmd_lightning_mark(
        "start",
        game_timer="0:10:00",
        out_dir=str(tmp_path),
        screenshot_path=str(source),
    )
    second = commands.cmd_lightning_mark(
        "map_return",
        game_timer="0:12:05",
        out_dir=str(tmp_path),
        screenshot_path=str(source),
    )

    assert first["status"] == "OK"
    assert second["status"] == "OK"
    assert second["event"]["timer_delta_seconds"] == 125
    events = [
        json.loads(line)
        for line in (tmp_path / "timing_events.jsonl").read_text().splitlines()
    ]
    timing_markdown = (tmp_path / "timing.md").read_text()
    assert [event["label"] for event in events] == ["start", "map_return"]
    assert "| map_return |" in timing_markdown
    assert "| start |" in timing_markdown
    assert "| s |" not in timing_markdown


def test_lightning_attempt_pause_on_stop_attaches_guard(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 0,
            "deployment_zone_count": 0,
            "island_map_count": 3,
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map_or_unknown"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "top3": [
                {
                    "mission_id": "Mission_Train",
                    "region_id": 5,
                    "save_region_name": "The Pasture",
                }
            ],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visual_regions_from_recommendation",
        lambda recommendation: {
            "status": "OK",
            "regions": [{"index": 0, "window_x": 430, "window_y": 320}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_timer_pause_guard_once",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )

    result = commands.cmd_lightning_attempt(pause_on_stop=True)

    assert result["status"] == "LIGHTNING_ATTEMPT_ROUTE_READY"
    assert result["pause_guard"] == {"status": "OK", "reason": "pause_clicked"}
    assert result["visual_regions"]["regions"][0]["window_x"] == 430
    assert result["route_start_candidates"][0]["command"].endswith(
        "--route-visual-region-index 0 "
        "--route-target-mission-id Mission_Train "
        "--route-start-mode dialogue-region-repeat-preview-board"
    )
    assert result["primary_next_command"].endswith(
        "--route-visual-region-index 0 "
        "--route-target-mission-id Mission_Train "
        "--route-start-mode dialogue-region-repeat-preview-board"
    )
    assert result["primary_route_candidate_index"] == 0
    assert result["route_start_candidates"][0]["route_start_command"].endswith(
        "--visual-region-index 0 "
        "--expected-mission-id Mission_Train "
        "--start-mode dialogue-region-repeat-preview-board"
    )
    assert result["route_start_candidates"][0]["coordinate_command"].endswith(
        "--window-x 430 --window-y 320 "
        "--expected-mission-id Mission_Train "
        "--start-mode dialogue-region-repeat-preview-board"
    )


def test_lightning_attempt_resumes_from_pause_before_routing(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    visible_states = [
        {
            "status": "OK",
            "visible_ui": "pause_menu",
            "recommended_control": "menu_continue",
        },
        {
            "status": "OK",
            "visible_ui": "island_map_or_unknown",
            "recommended_control": None,
        },
    ]

    def next_visible_state():
        if len(visible_states) > 1:
            return visible_states.pop(0)
        return visible_states[0]

    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", next_visible_state)
    monkeypatch.setattr(
        commands,
        "_lightning_press_pause_escape",
        lambda **kwargs: calls.append("pause_menu_escape")
        or {"status": "OK", "control": "pause_menu_escape"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: calls.append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 0,
            "deployment_zone_count": 0,
            "island_map_count": 3,
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "top3": [
                {
                    "mission_id": "Mission_Train",
                    "region_id": 5,
                    "save_region_name": "The Pasture",
                }
            ],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_timer_pause_guard_once",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )

    result = commands.cmd_lightning_attempt(
        resume_if_paused=True,
        pause_on_stop=True,
    )

    assert calls == [_lightning_peek_resume_control()]
    assert result["status"] == "LIGHTNING_ATTEMPT_ROUTE_READY"
    assert result["resume_guard"]["reason"] == "resumed_from_pause"


def test_lightning_attempt_resume_falls_back_when_continue_stays_paused(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
            },
        ]
    )
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: calls.append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_press_pause_escape",
        lambda **kwargs: calls.append("pause_menu_escape")
        or {"status": "OK", "control": "pause_menu_escape"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 0,
            "deployment_zone_count": 0,
            "island_map_count": 3,
        },
    )
    recommend_calls = []

    def fake_recommend_mission(**kwargs):
        recommend_calls.append(kwargs)
        return {
            "status": "OK",
            "top3": [
                {
                    "mission_id": "Mission_Train",
                    "region_id": 5,
                    "save_region_name": "The Pasture",
                }
            ],
        }

    monkeypatch.setattr(commands, "cmd_recommend_mission", fake_recommend_mission)
    monkeypatch.setattr(
        commands,
        "_lightning_extract_red_regions_from_image",
        lambda path: {
            "status": "OK",
            "regions": [{"index": 0, "window_x": 430, "window_y": 320}],
        },
    )

    result = commands.cmd_lightning_attempt(resume_if_paused=True)

    assert calls == [_lightning_peek_resume_control(), "pause_menu_escape"]
    assert result["status"] == "LIGHTNING_ATTEMPT_ROUTE_READY"
    assert result["resume_guard"]["reason"] == "resumed_from_pause_escape_fallback"


def test_lightning_attempt_dry_run_reports_resume_needed(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "pause_menu",
            "recommended_control": "menu_continue",
        },
    )

    result = commands.cmd_lightning_attempt(resume_if_paused=True, dry_run=True)

    assert result["status"] == "LIGHTNING_ATTEMPT_UI_READY"
    assert result["resume_guard"]["status"] == "DRY_RUN"
    assert result["resume_guard"]["planned_control"] == _lightning_peek_resume_control()


def test_lightning_ui_classifier_scales_retina_pause_menu(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (12, 14, 20))
    draw = ImageDraw.Draw(image)
    cx, cy = 491 * scale, 251 * scale
    w, h = 320 * scale, 100 * scale
    rect = [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2]
    draw.rectangle(rect, fill=(22, 29, 42), outline=(85, 110, 165), width=10)
    draw.rectangle(
        [cx - 90 * scale, cy - 18 * scale, cx + 90 * scale, cy + 18 * scale],
        fill=(235, 235, 235),
    )
    path = tmp_path / "pause_menu.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "pause_menu"
    assert result["recommended_control"] == "menu_continue"
    assert result["dark_overlay_fraction"] >= 0.70


def test_lightning_ui_classifier_rejects_dialogue_as_pause_menu(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (8, 10, 14))
    draw = ImageDraw.Draw(image)
    cx, cy = 491 * scale, 251 * scale
    w, h = 360 * scale, 80 * scale
    # Advisor text panels can sit under the pause-menu Continue crop. They
    # contain bright text but lack the heavy button border of the real menu.
    draw.rectangle(
        [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
        fill=(18, 24, 36),
        outline=(85, 110, 165),
        width=2,
    )
    draw.rectangle(
        [cx - 140 * scale, cy - 12 * scale, cx + 140 * scale, cy + 12 * scale],
        fill=(235, 235, 235),
    )
    path = tmp_path / "dialogue_not_pause.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "island_map_or_unknown"
    assert result["recommended_control"] is None


def test_lightning_ui_classifier_detects_new_game_setup_before_pause(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (8, 10, 14))
    draw = ImageDraw.Draw(image)
    for cx in (291 * scale, 1005 * scale):
        cy = 83 * scale
        w, h = 220 * scale, 80 * scale
        draw.rectangle(
            [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
            fill=(24, 32, 48),
            outline=(92, 122, 180),
            width=8,
        )
        draw.rectangle(
            [cx - 75 * scale, cy - 14 * scale, cx + 75 * scale, cy + 14 * scale],
            fill=(235, 235, 235),
        )

    # The setup hangar can put blue panels under the pause-menu crop. Keep a
    # pause-like shape here so the setup detector must win the classification.
    cx, cy = 491 * scale, 251 * scale
    w, h = 320 * scale, 100 * scale
    draw.rectangle(
        [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
        fill=(18, 24, 36),
        outline=(85, 110, 165),
        width=6,
    )
    draw.rectangle(
        [cx - 70 * scale, cy - 10 * scale, cx + 70 * scale, cy + 10 * scale],
        fill=(235, 235, 235),
    )

    path = tmp_path / "new_game_setup.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "new_game_setup"
    assert result["recommended_control"] is None


def test_lightning_ui_classifier_rejects_live_combat_button_shapes(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (70, 90, 70))
    draw = ImageDraw.Draw(image)
    cx, cy = 1005 * scale, 676 * scale
    w, h = 300 * scale, 100 * scale
    rect = [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2]
    draw.rectangle(rect, fill=(20, 28, 40), outline=(85, 110, 165), width=10)
    draw.rectangle(
        [cx - 80 * scale, cy - 16 * scale, cx + 80 * scale, cy + 16 * scale],
        fill=(240, 240, 240),
    )
    path = tmp_path / "combat_like.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "island_map_or_unknown"
    assert result["recommended_control"] is None
    assert result["dark_overlay_fraction"] < 0.60


def test_lightning_ui_classifier_detects_deployment_screen(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (70, 75, 80))
    draw = ImageDraw.Draw(image)
    draw.polygon(
        [
            (320 * scale, 180 * scale),
            (880 * scale, 160 * scale),
            (960 * scale, 500 * scale),
            (460 * scale, 610 * scale),
        ],
        fill=(212, 170, 78),
    )
    path = tmp_path / "deployment.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "deployment_screen"
    assert result["recommended_control"] == "deploy_confirm"
    assert result["non_pauseable"] is True


def test_lightning_refine_deployment_false_positive_with_bridge(monkeypatch):
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 4,
            "deployment_zone_count": 0,
            "in_active_mission": True,
        },
    )

    result = commands._lightning_refine_visible_ui_with_bridge(
        {
            "status": "OK",
            "visible_ui": "deployment_screen",
            "recommended_control": "deploy_confirm",
            "non_pauseable": True,
        }
    )

    assert result["visible_ui"] == "combat_screen"
    assert result["recommended_control"] is None
    assert result["non_pauseable"] is False
    assert result["deployment_false_positive"] is True


def test_lightning_refine_keeps_real_deployment_with_bridge(monkeypatch):
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "deployment_zone_count": 8,
            "in_active_mission": True,
        },
    )

    result = commands._lightning_refine_visible_ui_with_bridge(
        {
            "status": "OK",
            "visible_ui": "deployment_screen",
            "recommended_control": "deploy_confirm",
            "non_pauseable": True,
        }
    )

    assert result["visible_ui"] == "deployment_screen"
    assert result["recommended_control"] == "deploy_confirm"
    assert result["non_pauseable"] is True


def test_lightning_ui_classifier_detects_visible_island_map(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (24, 30, 42))
    draw = ImageDraw.Draw(image)
    draw.polygon(
        [
            (570 * scale, 250 * scale),
            (810 * scale, 220 * scale),
            (960 * scale, 520 * scale),
            (770 * scale, 650 * scale),
            (580 * scale, 500 * scale),
        ],
        fill=(185, 45, 50),
    )
    draw.polygon(
        [
            (900 * scale, 460 * scale),
            (1060 * scale, 500 * scale),
            (1020 * scale, 640 * scale),
            (880 * scale, 610 * scale),
        ],
        fill=(55, 135, 70),
    )
    path = tmp_path / "island_map.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "island_map"
    assert result["recommended_control"] is None


def test_lightning_ui_classifier_keeps_hq_warning_as_island_map(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (24, 30, 42))
    draw = ImageDraw.Draw(image)
    draw.polygon(
        [
            (570 * scale, 250 * scale),
            (810 * scale, 220 * scale),
            (960 * scale, 520 * scale),
            (770 * scale, 650 * scale),
            (580 * scale, 500 * scale),
        ],
        fill=(185, 45, 50),
    )
    draw.polygon(
        [
            (900 * scale, 460 * scale),
            (1060 * scale, 500 * scale),
            (1020 * scale, 640 * scale),
            (880 * scale, 610 * scale),
        ],
        fill=(55, 135, 70),
    )
    cx, cy = 817 * scale, 480 * scale
    draw.rectangle(
        [cx - 85 * scale, cy - 55 * scale, cx + 85 * scale, cy + 55 * scale],
        fill=(18, 25, 38),
        outline=(85, 110, 165),
        width=10,
    )
    draw.rectangle(
        [cx - 55 * scale, cy - 16 * scale, cx + 55 * scale, cy + 16 * scale],
        fill=(240, 240, 240),
    )
    path = tmp_path / "hq_warning_map.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "island_map"
    assert result["recommended_control"] is None


def test_lightning_ui_classifier_prioritizes_map_continue_panel(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (24, 30, 42))
    draw = ImageDraw.Draw(image)
    draw.polygon(
        [
            (570 * scale, 250 * scale),
            (810 * scale, 220 * scale),
            (960 * scale, 520 * scale),
            (770 * scale, 650 * scale),
            (580 * scale, 500 * scale),
        ],
        fill=(185, 45, 50),
    )
    cx, cy = 1005 * scale, 676 * scale
    draw.rectangle(
        [cx - 150 * scale, cy - 50 * scale, cx + 150 * scale, cy + 50 * scale],
        fill=(20, 28, 40),
        outline=(85, 110, 165),
        width=10,
    )
    draw.rectangle(
        [cx - 90 * scale, cy - 16 * scale, cx + 90 * scale, cy + 16 * scale],
        fill=(240, 240, 240),
    )
    path = tmp_path / "island_map_dialogue.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] in {"bottom_continue_panel", "reward_panel"}
    assert result["recommended_control"] == "bottom_continue"


def test_lightning_ui_classifier_prefers_bottom_continue_over_modal_overlap(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (12, 14, 20))
    draw = ImageDraw.Draw(image)

    def draw_button(cx: int, cy: int, w: int, h: int) -> None:
        x = cx * scale
        y = cy * scale
        half_w = w * scale // 2
        half_h = h * scale // 2
        draw.rectangle(
            [x - half_w, y - half_h, x + half_w, y + half_h],
            fill=(18, 25, 38),
            outline=(85, 110, 165),
            width=10,
        )
        draw.rectangle(
            [x - 90 * scale, y - 16 * scale, x + 90 * scale, y + 16 * scale],
            fill=(240, 240, 240),
        )

    draw_button(1005, 676, 300, 100)
    draw_button(666, 518, 300, 100)
    path = tmp_path / "pod_contents_modal_overlap.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "bottom_continue_panel"
    assert result["recommended_control"] == "bottom_continue"


def test_lightning_ui_classifier_prefers_perfect_island_continue(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (10, 12, 18))
    draw = ImageDraw.Draw(image)

    def draw_button(cx: int, cy: int, w: int, h: int) -> None:
        x = cx * scale
        y = cy * scale
        half_w = w * scale // 2
        half_h = h * scale // 2
        draw.rectangle(
            [x - half_w, y - half_h, x + half_w, y + half_h],
            fill=(18, 25, 38),
            outline=(85, 110, 165),
            width=8 * scale,
        )
        draw.rectangle(
            [x - 90 * scale, y - 16 * scale, x + 90 * scale, y + 16 * scale],
            fill=(240, 240, 240),
        )

    draw.rectangle(
        [
            (900 * scale, 625 * scale),
            (1110 * scale, 680 * scale),
        ],
        fill=(18, 25, 38),
        outline=(70, 90, 125),
        width=2 * scale,
    )
    draw_button(846, 550, 360, 130)
    path = tmp_path / "perfect_island_continue.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "perfect_island_panel"
    assert result["recommended_control"] == "panel_continue"


def test_lightning_ui_classifier_prefers_region_secured_continue(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (10, 12, 18))
    draw = ImageDraw.Draw(image)

    def draw_button(cx: int, cy: int, w: int, h: int) -> None:
        x = cx * scale
        y = cy * scale
        half_w = w * scale // 2
        half_h = h * scale // 2
        draw.rectangle(
            [x - half_w, y - half_h, x + half_w, y + half_h],
            fill=(18, 25, 38),
            outline=(85, 110, 165),
            width=8 * scale,
        )
        draw.rectangle(
            [x - 90 * scale, y - 16 * scale, x + 90 * scale, y + 16 * scale],
            fill=(240, 240, 240),
        )

    draw_button(1001, 653, 300, 90)
    draw.rectangle(
        [760 * scale, 485 * scale, 950 * scale, 610 * scale],
        fill=(18, 25, 38),
        outline=(85, 110, 165),
        width=5 * scale,
    )
    draw.rectangle(
        [800 * scale, 535 * scale, 890 * scale, 565 * scale],
        fill=(240, 240, 240),
    )
    path = tmp_path / "region_secured_continue.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] in {"reward_panel", "bottom_continue_panel"}
    assert result["recommended_control"] == "reward_continue"


def test_lightning_ui_classifier_selects_perfect_reward_grid(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (10, 12, 18))
    draw = ImageDraw.Draw(image)

    x = 817 * scale
    y = 470 * scale
    draw.rectangle(
        [x - 85 * scale, y - 55 * scale, x + 85 * scale, y + 55 * scale],
        fill=(18, 25, 38),
        outline=(85, 110, 165),
        width=8 * scale,
    )
    draw.rectangle(
        [x - 45 * scale, y - 22 * scale, x + 45 * scale, y + 22 * scale],
        fill=(235, 240, 245),
    )
    draw.rectangle(
        [x + 50 * scale, y - 35 * scale, x + 62 * scale, y + 35 * scale],
        fill=(80, 190, 230),
    )
    path = tmp_path / "perfect_reward_grid.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "perfect_reward_choice"
    assert result["recommended_control"] == "perfect_reward_grid"


def test_lightning_ui_classifier_detects_island_complete_leave(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (10, 12, 18))
    draw = ImageDraw.Draw(image)

    # Completed island map underneath the spend/leave panel. This produces
    # enough saturated map color for island-complete detection while the dim
    # background keeps the modal-overlay estimate high.
    draw.polygon(
        [
            (430 * scale, 170 * scale),
            (980 * scale, 150 * scale),
            (1060 * scale, 650 * scale),
            (540 * scale, 640 * scale),
        ],
        fill=(50, 130, 65),
    )
    draw.polygon(
        [
            (650 * scale, 250 * scale),
            (850 * scale, 250 * scale),
            (850 * scale, 560 * scale),
            (650 * scale, 560 * scale),
        ],
        fill=(82, 70, 150),
    )

    # Add a reward-card-like rectangle so the old broad crop would have been
    # tempted to classify this as a perfect reward choice.
    x = 817 * scale
    y = 470 * scale
    draw.rectangle(
        [x - 85 * scale, y - 55 * scale, x + 85 * scale, y + 55 * scale],
        fill=(18, 25, 38),
        outline=(85, 110, 165),
        width=8 * scale,
    )
    draw.rectangle(
        [x - 45 * scale, y - 22 * scale, x + 45 * scale, y + 22 * scale],
        fill=(235, 240, 245),
    )

    # Actual Leave Island button at the bottom of the completed-island panel.
    cx, cy = 641 * scale, 704 * scale
    w, h = 260 * scale, 70 * scale
    draw.rectangle(
        [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
        fill=(18, 25, 38),
        outline=(85, 110, 165),
        width=8 * scale,
    )
    draw.rectangle(
        [cx - 85 * scale, cy - 14 * scale, cx + 85 * scale, cy + 14 * scale],
        fill=(235, 240, 245),
    )

    path = tmp_path / "island_complete_leave.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "island_complete_leave"
    assert result["recommended_control"] == "leave_island"


def test_lightning_dialogue_box_score_requires_visible_dialogue(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    dialogue = Image.new("RGB", (1280 * scale, 748 * scale), (20, 24, 32))
    draw = ImageDraw.Draw(dialogue)
    draw.rectangle(
        [
            180 * scale,
            120 * scale,
            1100 * scale,
            235 * scale,
        ],
        fill=(12, 16, 28),
        outline=(88, 116, 166),
        width=6 * scale,
    )
    draw.rectangle(
        [
            250 * scale,
            155 * scale,
            900 * scale,
            190 * scale,
        ],
        fill=(238, 238, 238),
    )
    draw.rectangle(
        [
            930 * scale,
            130 * scale,
            1050 * scale,
            270 * scale,
        ],
        fill=(196, 102, 58),
        outline=(86, 116, 166),
        width=6 * scale,
    )
    dialogue_path = tmp_path / "dialogue.png"
    dialogue.save(dialogue_path)

    plain = Image.new("RGB", (1280 * scale, 748 * scale), (24, 30, 42))
    plain_path = tmp_path / "plain.png"
    plain.save(plain_path)

    assert commands._lightning_dialogue_box_score(dialogue_path)["visible"] is True
    assert commands._lightning_dialogue_box_score(plain_path)["visible"] is False

    muted = Image.new("RGB", (1280 * scale, 748 * scale), (20, 24, 32))
    draw = ImageDraw.Draw(muted)
    draw.rectangle(
        [
            180 * scale,
            120 * scale,
            1100 * scale,
            235 * scale,
        ],
        fill=(12, 16, 28),
        outline=(88, 116, 166),
        width=2 * scale,
    )
    draw.rectangle(
        [
            250 * scale,
            155 * scale,
            500 * scale,
            160 * scale,
        ],
        fill=(238, 238, 238),
    )
    draw.rectangle(
        [
            930 * scale,
            130 * scale,
            1050 * scale,
            270 * scale,
        ],
        fill=(196, 102, 58),
        outline=(86, 116, 166),
        width=4 * scale,
    )
    muted_path = tmp_path / "muted_dialogue.png"
    muted.save(muted_path)
    muted_result = commands._lightning_dialogue_box_score(muted_path)

    assert 3500 <= muted_result["bright"] < 6000
    assert muted_result["visible"] is True

    archive_ceo = Image.new("RGB", (1280 * scale, 748 * scale), (20, 24, 32))
    draw = ImageDraw.Draw(archive_ceo)
    draw.rectangle(
        [
            180 * scale,
            120 * scale,
            1100 * scale,
            235 * scale,
        ],
        fill=(12, 16, 28),
        outline=(88, 116, 166),
        width=3 * scale,
    )
    draw.rectangle(
        [
            250 * scale,
            155 * scale,
            500 * scale,
            160 * scale,
        ],
        fill=(238, 238, 238),
    )
    draw.rectangle(
        [
            940 * scale,
            130 * scale,
            1040 * scale,
            270 * scale,
        ],
        fill=(60, 50, 42),
        outline=(86, 116, 166),
        width=3 * scale,
    )
    archive_ceo_path = tmp_path / "archive_ceo_dialogue.png"
    archive_ceo.save(archive_ceo_path)
    archive_ceo_result = commands._lightning_dialogue_box_score(archive_ceo_path)

    assert 0.24 <= archive_ceo_result["portrait_score"]["score"] < 0.25
    assert archive_ceo_result["visible"] is True


def test_lightning_extract_red_regions_from_image(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (24, 30, 42))
    draw = ImageDraw.Draw(image)
    draw.polygon(
        [
            (310 * scale, 130 * scale),
            (520 * scale, 120 * scale),
            (520 * scale, 260 * scale),
            (320 * scale, 270 * scale),
        ],
        fill=(185, 45, 50),
    )
    draw.polygon(
        [
            (330 * scale, 430 * scale),
            (530 * scale, 420 * scale),
            (520 * scale, 560 * scale),
            (330 * scale, 570 * scale),
        ],
        fill=(190, 50, 55),
    )
    path = tmp_path / "red_regions.png"
    image.save(path)

    result = commands._lightning_extract_red_regions_from_image(path)

    assert result["status"] == "OK"
    assert result["region_count"] == 2
    assert result["regions"][0]["window_y"] < result["regions"][1]["window_y"]
    assert 380 <= result["regions"][0]["window_x"] <= 460
    assert 170 <= result["regions"][0]["window_y"] <= 230


def test_lightning_extract_red_regions_splits_adjacent_regions(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (24, 30, 42))
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        [760 * scale, 260 * scale, 890 * scale, 520 * scale],
        fill=(185, 45, 50),
    )
    draw.rectangle(
        [840 * scale, 522 * scale, 1060 * scale, 690 * scale],
        fill=(190, 50, 55),
    )
    draw.rectangle(
        [879 * scale, 520 * scale, 881 * scale, 522 * scale],
        fill=(190, 50, 55),
    )
    path = tmp_path / "adjacent_regions.png"
    image.save(path)

    result = commands._lightning_extract_red_regions_from_image(path)

    assert result["status"] == "OK"
    assert result["segmentation"] == "eroded"
    assert result["raw_region_count"] == 1
    assert result["region_count"] == 2
    assert result["regions"][0]["window_y"] < result["regions"][1]["window_y"]
    assert 790 <= result["regions"][0]["window_x"] <= 850
    assert 930 <= result["regions"][1]["window_x"] <= 990


def test_lightning_merge_visual_regions_merges_vertical_splits_only():
    regions = [
        {
            "window_x": 700,
            "window_y": 300,
            "bbox_window": [650, 240, 820, 390],
            "area_px": 1000,
            "area_window": 250.0,
        },
        {
            "window_x": 910,
            "window_y": 330,
            "bbox_window": [850, 290, 980, 410],
            "area_px": 700,
            "area_window": 175.0,
        },
        {
            "window_x": 905,
            "window_y": 455,
            "bbox_window": [845, 445, 975, 505],
            "area_px": 300,
            "area_window": 75.0,
        },
    ]

    result = commands._lightning_merge_visual_regions(regions)

    assert len(result) == 2
    merged = max(result, key=lambda region: region.get("merged_parts", 1))
    assert merged["merged_parts"] == 2
    assert 900 <= merged["window_x"] <= 910
    assert 360 <= merged["window_y"] <= 370


def test_lightning_map_regions_command_analyzes_existing_screenshot(monkeypatch):
    monkeypatch.setattr(
        commands,
        "_lightning_extract_red_regions_from_image",
        lambda path: {
            "status": "OK",
            "screenshot_path": str(path),
            "region_count": 1,
            "regions": [
                {
                    "index": 0,
                    "window_x": 735,
                    "window_y": 313,
                    "area_window": 1234.0,
                }
            ],
        },
    )

    result = commands.cmd_lightning_map_regions(
        "/tmp/map.png",
        start_mode="dialogue-region-repeat-preview-board-twice",
        target_name="The Pasture",
        target_mission_id="Mission_Armored_Train",
        target_region_id=5,
    )

    assert result["status"] == "OK"
    assert result["regions"][0]["window_x"] == 735
    assert result["route_target_hint"] == {
        "save_region_name": "The Pasture",
        "mission_id": "Mission_Armored_Train",
        "region_id": 5,
        "match_label": "The Pasture",
    }
    assert "route_start_candidates" in result
    assert result["route_start_candidates"][0]["target_hint"]["match_label"] == "The Pasture"
    assert result["route_start_candidates"][0]["command"].endswith(
        "--route-visual-region-index 0 "
        "--route-target-mission-id Mission_Armored_Train "
        "--route-start-mode dialogue-region-repeat-preview-board-twice"
    )
    assert result["primary_next_command"].endswith(
        "--route-visual-region-index 0 "
        "--route-target-mission-id Mission_Armored_Train "
        "--route-start-mode dialogue-region-repeat-preview-board-twice"
    )
    assert result["primary_route_target_hint"]["match_label"] == "The Pasture"
    assert result["route_start_candidates"][0]["route_start_command"].endswith(
        "--visual-region-index 0 "
        "--expected-mission-id Mission_Armored_Train "
        "--start-mode dialogue-region-repeat-preview-board-twice"
    )
    assert "candidate" in result["next_step"]


def test_lightning_ui_classifier_prioritizes_mission_preview(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (8, 10, 14))
    draw = ImageDraw.Draw(image)
    # A dialogue box can make the pause-menu crop look button-like; the
    # explicit Start Mission detector should win.
    draw.rectangle(
        [
            (491 - 160) * scale,
            (251 - 50) * scale,
            (491 + 160) * scale,
            (251 + 50) * scale,
        ],
        fill=(20, 26, 38),
        outline=(85, 110, 165),
        width=10,
    )
    cx, cy = 815 * scale, 468 * scale
    draw.rectangle(
        [cx - 160 * scale, cy - 32 * scale, cx + 160 * scale, cy + 32 * scale],
        fill=(235, 220, 35),
    )
    path = tmp_path / "mission_preview.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "mission_preview_panel"
    assert result["recommended_control"] == "mission_preview_board"


def test_lightning_ui_classifier_detects_advisor_masked_mission_preview(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (8, 10, 14))
    draw = ImageDraw.Draw(image)
    # Mission preview card with the yellow Start Mission text hidden by an
    # advisor dialogue. This appears on some first-click Train previews.
    draw.rectangle(
        [250 * scale, 350 * scale, 1060 * scale, 590 * scale],
        fill=(16, 20, 29),
        outline=(85, 110, 165),
        width=12 * scale,
    )
    draw.rectangle(
        [305 * scale, 395 * scale, 520 * scale, 430 * scale],
        fill=(210, 55, 55),
    )
    draw.rectangle(
        [130 * scale, 165 * scale, 1150 * scale, 285 * scale],
        fill=(14, 18, 28),
        outline=(85, 110, 165),
        width=10 * scale,
    )
    for index in range(12):
        left = (160 + index * 48) * scale
        draw.rectangle(
            [left, 200 * scale, left + 30 * scale, 218 * scale],
            fill=(220, 225, 232),
        )
    path = tmp_path / "advisor_masked_preview.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "mission_preview_panel"
    assert result["recommended_control"] == "dialogue_textbox"


def test_lightning_start_mission_target_detects_yellow_text(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (8, 10, 14))
    draw = ImageDraw.Draw(image)
    cx, cy = 930 * scale, 545 * scale
    draw.rectangle(
        [cx - 120 * scale, cy - 28 * scale, cx + 120 * scale, cy + 28 * scale],
        fill=(235, 220, 35),
    )
    path = tmp_path / "start_text.png"
    image.save(path)

    result = commands._lightning_start_mission_target(path)

    assert result["status"] == "OK"
    assert 900 <= result["window_x"] <= 960
    assert 520 <= result["window_y"] <= 570


def test_lightning_start_mission_target_prefers_text_over_board_outline(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (8, 10, 14))
    draw = ImageDraw.Draw(image)
    # Large yellow board outline should not pull the click down/right.
    draw.rectangle(
        [610 * scale, 335 * scale, 1070 * scale, 660 * scale],
        outline=(235, 220, 35),
        width=8,
    )
    # Approximate separated Start Mission glyphs.
    for x in range(740, 960, 28):
        draw.rectangle(
            [x * scale, 438 * scale, (x + 16) * scale, 460 * scale],
            fill=(235, 220, 35),
        )
    path = tmp_path / "start_with_outline.png"
    image.save(path)

    result = commands._lightning_start_mission_target(path)

    assert result["status"] == "OK"
    assert 830 <= result["window_x"] <= 880
    assert 435 <= result["window_y"] <= 465


def test_lightning_start_mission_target_ignores_warning_row(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (8, 10, 14))
    draw = ImageDraw.Draw(image)
    for x in range(560, 830, 24):
        draw.rectangle(
            [x * scale, 580 * scale, (x + 14) * scale, 598 * scale],
            fill=(235, 220, 35),
        )
    path = tmp_path / "warning_only.png"
    image.save(path)

    result = commands._lightning_start_mission_target(path)

    assert result["status"] == "NOT_FOUND"
    assert result["reason"] == "no_start_text_cluster"


def test_lightning_attempt_deploys_confirms_and_runs_loop(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 0,
            "active_mechs": 0,
            "mech_count": 0,
            "deployment_zone_count": 4,
        },
    )

    def fake_deploy(**kwargs):
        calls.append(("deploy", kwargs))
        return {"status": "OK"}

    def fake_click(name, **kwargs):
        calls.append(("click", name))
        return {"status": "OK", "control": name}

    def fake_loop(**kwargs):
        calls.append(("loop", kwargs))
        return {"status": "LIGHTNING_LOOP_STOPPED", "reason": "mission_end"}

    monkeypatch.setattr(commands, "cmd_deploy_recommended", fake_deploy)
    monkeypatch.setattr(commands, "cmd_lightning_loop", fake_loop)
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        fake_click,
    )

    result = commands.cmd_lightning_attempt(max_wait=10)

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert result["reason"] == "combat_loop_returned"
    assert [call[0] for call in calls] == ["deploy", "click", "loop"]
    assert calls[1] == ("click", "deploy_confirm")
    assert result["action"]["max_wait_floor"] == 30.0
    assert calls[2][1]["max_wait"] == 30.0


def test_lightning_attempt_deploys_when_bridge_reports_enemy_phase(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "active_mechs": 0,
            "mech_count": 0,
            "deployment_zone_count": 11,
        },
    )

    monkeypatch.setattr(
        commands,
        "cmd_deploy_recommended",
        lambda **kwargs: calls.append(("deploy", kwargs)) or {"status": "OK"},
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda name, **kwargs: calls.append(("click", name)) or {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_loop",
        lambda **kwargs: calls.append(("loop", kwargs)) or {"status": "OK"},
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert [call[0] for call in calls] == ["deploy", "click", "loop"]


def test_lightning_attempt_blocks_route_mission_mismatch_before_deploy(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "active_mechs": 0,
            "mech_count": 0,
            "deployment_zone_count": 11,
            "mission_id": "Mission_Satellite",
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_deploy_recommended",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("route mismatch must block before deployment")
        ),
    )
    mismatch_blocks = []
    monkeypatch.setattr(
        commands,
        "_lightning_write_route_mismatch_block",
        lambda session, **kwargs: mismatch_blocks.append(kwargs)
        or {
            "expected_mission_id": kwargs["expected_mission_id"],
            "actual_mission_id": kwargs["actual_mission_id"],
            "next_step": "abandon",
        },
    )

    result = commands.cmd_lightning_attempt(
        expected_route_mission_id="Mission_Mines",
    )

    assert result["status"] == "LIGHTNING_ATTEMPT_BLOCKED"
    assert result["reason"] == "route_mission_mismatch_before_deploy"
    assert result["expected_route_mission_id"] == "Mission_Mines"
    assert result["actual_mission_id"] == "Mission_Satellite"
    assert mismatch_blocks == [
        {
            "expected_mission_id": "Mission_Mines",
            "actual_mission_id": "Mission_Satellite",
            "snapshot": result["snapshot"],
        }
    ]
    assert result["route_mismatch_block"]["expected_mission_id"] == "Mission_Mines"


def test_lightning_attempt_keeps_active_route_mismatch_blocked(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    snapshot = {
        "status": "OK",
        "phase": "combat_enemy",
        "turn": 0,
        "active_mechs": 0,
        "mech_count": 0,
        "deployment_zone_count": 11,
        "mission_id": "Mission_Survive",
    }

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(commands, "_lightning_live_snapshot", lambda: snapshot)
    monkeypatch.setattr(
        commands,
        "_lightning_active_route_mismatch_block",
        lambda session, snapshot: {
            "status": "BLOCKED",
            "reason": "route_mission_mismatch_before_deploy",
            "expected_mission_id": "Mission_Volatile",
            "actual_mission_id": "Mission_Survive",
            "next_step": "abandon",
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_deploy_recommended",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("active route mismatch must not deploy")
        ),
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_BLOCKED"
    assert result["reason"] == "route_mission_mismatch_still_active"
    assert result["expected_route_mission_id"] == "Mission_Volatile"
    assert result["actual_mission_id"] == "Mission_Survive"


def test_lightning_attempt_finishes_partial_deployment_before_waiting(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "active_mechs": 1,
            "mech_count": 1,
            "deployment_zone_count": 5,
            "in_active_mission": True,
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_deploy_recommended",
        lambda **kwargs: calls.append(("deploy", kwargs)) or {"status": "OK"},
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda name, **kwargs: calls.append(("click", name)) or {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_loop",
        lambda **kwargs: calls.append(("loop", kwargs)) or {"status": "OK"},
    )

    result = commands.cmd_lightning_attempt(max_wait=10)

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert result["action"]["action"] == "finish_deployment_then_combat"
    assert [call[0] for call in calls] == ["deploy", "click", "loop"]
    assert calls[2][1]["max_wait"] == 30.0


def test_lightning_attempt_does_not_deploy_from_unknown_phase(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 0,
            "active_mechs": 0,
            "mech_count": 0,
            "deployment_zone_count": 11,
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map_or_unknown"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_deploy_recommended",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not deploy")),
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_NEEDS_UI"
    assert result["reason"] == "deployment_visible_ui_not_deployment"


def test_lightning_attempt_does_not_deploy_from_visible_island_map(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 0,
            "active_mechs": 0,
            "mech_count": 0,
            "deployment_zone_count": 11,
            "in_active_mission": True,
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_map_route_plan",
        lambda **kwargs: {
            "recommendation": {"status": "NO_ISLAND_MAP"},
            "route_target_hint": None,
            "visual_regions": None,
            "route_start_candidates": [],
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_deploy_recommended",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not deploy")),
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_NEEDS_UI"
    assert result["reason"] == "deployment_bridge_state_uncertain"


def test_lightning_attempt_uses_visible_island_map_when_bridge_missing(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {"status": "NO_BRIDGE"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_map_route_plan",
        lambda **kwargs: {
            "recommendation": {"status": "NO_ISLAND_MAP"},
            "route_target_hint": None,
            "visual_regions": None,
            "route_start_candidates": [],
        },
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_NEEDS_UI"
    assert result["reason"] == "bridge_snapshot_unavailable_visible_island_map"
    assert result["snapshot"]["visible_ui"]["visible_ui"] == "island_map"


def test_lightning_attempt_clicks_mission_preview_dialogue_when_bridge_missing(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    clicks = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {"status": "NO_BRIDGE"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "mission_preview_panel",
            "recommended_control": "dialogue_textbox",
        },
    )
    monkeypatch.setattr(commands.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: clicks.append(control)
        or {"status": "OK", "control": control},
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_CLEARED"
    assert result["reason"] == "mission_preview_dialogue_cleared_without_bridge"
    assert result["action"]["control"] == "dialogue_textbox"
    assert clicks == ["dialogue_textbox"]


def test_lightning_attempt_clicks_reviewed_held_end_turn(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    session.current_turn = 3
    session.active_solution = ActiveSolution(
        actions=[
            SolverAction(
                mech_uid=0,
                mech_type="ElectricMech",
                move_to=(4, 4),
                weapon="Prime_Lightning",
                target=(3, 4),
                description="ElectricMech",
            )
        ],
        score=1.0,
        turn=3,
    )
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "grid_damage", "blocking": True},
            {"kind": "building_hp_loss", "blocking": True},
            {"kind": "mech_hp_loss", "blocking": True},
        ],
        "current": {
            "grid_power": 4,
            "building_hp_total": 9,
            "buildings_alive": 8,
            "mechs_alive": 3,
            "mech_hp_total": 8,
        },
        "predicted": {
            "grid_power": 3,
            "building_hp_total": 8,
            "buildings_alive": 8,
            "mechs_alive": 3,
            "mech_hp_total": 6,
        },
    }

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 3,
            "active_mechs": 0,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "in_active_mission": True,
        },
    )
    monkeypatch.setattr(
        commands,
        "_load_recorded_turn_state",
        lambda session, label, turn=None: {
            "plan_safety": plan_safety,
            "selected_candidate_rank": 0,
            "initial_building_threats": [],
        },
    )
    monkeypatch.setattr(commands, "_dirty_consent_gate", lambda *args, **kwargs: None)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (object(), {"phase": "combat_player"}),
    )
    monkeypatch.setattr(
        commands,
        "_capture_board_summary",
        lambda board, data: {"mechs_on_danger": []},
    )
    monkeypatch.setattr(
        "src.solver.threat_audit.audit_threat_coverage",
        lambda threats, board: {"still_threatened_count": 1, "entries": []},
    )
    monkeypatch.setattr(commands, "_record_turn_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        commands,
        "_end_turn_click_plan_result",
        lambda: {"status": "PLAN", "batch": [{"left_click": {"x": 1, "y": 2}}]},
    )
    monkeypatch.setattr(commands, "_lightning_resume_if_paused", lambda **kwargs: None)
    monkeypatch.setattr(
        commands,
        "_click_end_turn_from_plan_result",
        lambda result: {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda result: {"status": "OK", "phase": "combat_enemy"},
    )

    result = commands.cmd_lightning_attempt(
        allow_dirty_plan=True,
        candidate_rank=0,
        dirty_consent_id="token",
    )

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_CLEARED"
    assert result["reason"] == "held_end_turn_clicked"
    assert result["dirty_consent_validated"] is True


def test_lightning_attempt_routes_ambiguous_visible_map_when_bridge_missing(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    seen = {}

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {"status": "NO_BRIDGE"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "island_map_or_unknown",
            "screenshot_path": "map.png",
        },
    )

    def fake_route_plan(**kwargs):
        seen.update(kwargs)
        return {
            "recommendation": {"status": "OK"},
            "route_target_hint": {"mission_id": "Mission_Train"},
            "visual_regions": {"status": "OK", "regions": []},
            "route_start_candidates": [
                {
                    "index": 0,
                    "window_x": 430,
                    "window_y": 320,
                    "mission_id": "Mission_Train",
                    "command": (
                        "python game_loop.py lightning_route_start "
                        "--visual-region-index 0"
                    ),
                    "auto_route_allowed": True,
                }
            ],
        }

    monkeypatch.setattr(commands, "_lightning_visible_map_route_plan", fake_route_plan)

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_ROUTE_READY"
    assert result["reason"] == "visible_island_map_save_route_plan"
    assert seen["visible_ui"]["visible_ui"] == "island_map_or_unknown"
    assert result["primary_route_candidate_index"] == 0


def test_lightning_attempt_clicks_preview_then_deploys(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []
    snapshots = iter(
        [
            {
                "status": "OK",
                "phase": "unknown",
                "turn": 0,
                "active_mechs": 0,
                "mech_count": 0,
                "deployment_zone_count": 10,
                "in_active_mission": True,
            },
            {
                "status": "OK",
                "phase": "combat_player",
                "turn": 0,
                "active_mechs": 0,
                "mech_count": 0,
                "deployment_zone_count": 10,
                "in_active_mission": True,
            },
        ]
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(commands, "_lightning_live_snapshot", lambda: next(snapshots))
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "mission_preview_panel",
            "recommended_control": "mission_preview_board",
        },
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda name, **kwargs: calls.append(("click", name)) or {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_deploy_recommended",
        lambda **kwargs: calls.append(("deploy", kwargs)) or {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_loop",
        lambda **kwargs: calls.append(("loop", kwargs)) or {"status": "OK"},
    )

    result = commands.cmd_lightning_attempt(max_wait=10)

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert calls[0] == ("click", "mission_preview_board")
    assert calls[1][0] == "deploy"
    assert calls[2] == ("click", "deploy_confirm")
    assert calls[3][0] == "loop"


def test_lightning_attempt_runs_combat_loop_on_active_turn(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 2,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 0,
        },
    )

    def fake_loop(**kwargs):
        calls.append(kwargs)
        return {"status": "LIGHTNING_LOOP_STOPPED", "reason": "mission_end"}

    monkeypatch.setattr(commands, "cmd_lightning_loop", fake_loop)

    result = commands.cmd_lightning_attempt(
        time_limit=1.5,
        max_turns=4,
        allow_dirty_plan=True,
        candidate_rank=2,
        dirty_consent_id="dirty-ok",
        allow_protected_objective_loss=True,
        allow_objective_loss=True,
    )

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert result["action"]["action"] == "combat_loop"
    assert calls[0]["time_limit"] == 1.5
    assert calls[0]["max_turns"] == 4
    assert calls[0]["allow_dirty_plan"] is True
    assert calls[0]["candidate_rank"] == 2
    assert calls[0]["dirty_consent_id"] == "dirty-ok"
    assert calls[0]["allow_protected_objective_loss"] is True
    assert calls[0]["allow_objective_loss"] is True


def test_lightning_attempt_runs_loop_through_enemy_phase(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "active_mechs": 0,
            "mech_count": 3,
            "deployment_zone_count": 8,
        },
    )
    def fake_loop(**kwargs):
        calls.append(kwargs)
        return {"status": "LIGHTNING_LOOP_STOPPED", "reason": "mission_end"}

    monkeypatch.setattr(commands, "cmd_lightning_loop", fake_loop)

    result = commands.cmd_lightning_attempt(max_wait=10)

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert result["action"]["action"] == "wait_then_combat_loop"
    assert result["action"]["max_wait_floor"] == 30.0
    assert calls[0]["max_wait"] == 30.0


def test_lightning_attempt_stops_quickly_on_player_phase_without_active_mechs(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 2,
            "active_mechs": 0,
            "mech_count": 3,
            "deployment_zone_count": 0,
        },
    )
    def fake_loop(**kwargs):
        calls.append(kwargs)
        return {"status": "LIGHTNING_LOOP_STOPPED", "reason": "mission_end"}

    monkeypatch.setattr(commands, "cmd_lightning_loop", fake_loop)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "island_map_or_unknown",
            "recommended_control": None,
        },
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert result["reason"] == "player_turn_no_active_mechs"
    assert calls == []


def test_lightning_attempt_clicks_end_turn_when_no_active_mechs_for_speedrun(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    clicks = []
    observations = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 2,
            "active_mechs": 0,
            "mech_count": 3,
            "deployment_zone_count": 0,
            "in_active_mission": True,
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "island_map_or_unknown",
            "recommended_control": None,
        },
    )
    monkeypatch.setattr(
        commands,
        "_end_turn_click_plan_result",
        lambda: {
            "status": "PLAN",
            "batch": [{"type": "left_click", "window_x": 126, "window_y": 120}],
            "codex_computer_use_batch": [],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_resume_if_paused",
        lambda **kwargs: {"status": "OK"},
    )

    def fake_click(plan):
        clicks.append(plan)
        return {"status": "OK"}

    def fake_observe(plan):
        observations.append(plan)
        return {"status": "OK", "reason": "phase_changed"}

    monkeypatch.setattr(commands, "_click_end_turn_from_plan_result", fake_click)
    monkeypatch.setattr(commands, "_observe_end_turn_after_click", fake_observe)

    result = commands.cmd_lightning_attempt(lightning_speed_loss_policy=True)

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_CLEARED"
    assert result["reason"] == "no_active_mechs_end_turn_clicked"
    assert result["action"]["action"] == "click_no_active_mechs_end_turn"
    assert clicks
    assert observations[0]["turn"] == 2


def test_lightning_attempt_clears_safe_panel_when_no_active_mechs(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    clicks = []
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
            },
        ]
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 3,
            "active_mechs": 0,
            "mech_count": 3,
            "deployment_zone_count": 0,
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: next(visible_states),
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: clicks.append(control)
        or {"status": "OK", "control": control},
    )

    result = commands.cmd_lightning_attempt(auto_clear_panels=True)

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_CLEARED"
    assert result["reason"] == "auto_clear_safe_panel_during_no_active_mechs"
    assert result["action"]["clear_result"]["reason"] == "panel_chain_cleared"
    assert clicks == ["reward_continue", "bottom_continue"]


def test_lightning_attempt_recommends_route_on_island_map(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    recommend_calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 0,
            "deployment_zone_count": 0,
            "island_map_count": 3,
        },
    )
    def fake_island_map_recommend_mission(**kwargs):
        recommend_calls.append(kwargs)
        return {
            "status": "OK",
            "top3": [
                {
                    "mission_id": "Mission_Train",
                    "region_id": 5,
                    "save_region_name": "The Pasture",
                }
            ],
        }

    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        fake_island_map_recommend_mission,
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map_or_unknown"},
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_ROUTE_READY"
    assert result["recommendation"]["top3"][0]["mission_id"] == "Mission_Train"
    assert recommend_calls[-1]["pause_map_peek"] is True


def test_lightning_attempt_panel_precedes_route_recommendation(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 4,
            "deployment_zone_count": 0,
            "island_map_count": 3,
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "promotion_panel",
            "recommended_control": "modal_understood",
            "confidence": 1.2,
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not route")),
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_READY"
    assert result["recommended_control"] == "modal_understood"


def test_lightning_attempt_auto_clears_safe_panel(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 4,
            "deployment_zone_count": 0,
            "island_map_count": 3,
        },
    )
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
                "confidence": 1.2,
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
                "confidence": 1.2,
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
                "confidence": 1.2,
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
                "confidence": 0.1,
            },
        ]
    )
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: calls.append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_timer_pause_guard_once",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not route")),
    )

    result = commands.cmd_lightning_attempt(
        auto_clear_panels=True,
        pause_on_stop=True,
    )

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_CLEARED"
    assert result["action"]["control"] == "reward_continue"
    assert calls == ["reward_continue", "bottom_continue"]
    assert result["pause_guard"]["status"] == "OK"


def test_lightning_attempt_auto_clears_chained_pod_panels(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 4,
            "deployment_zone_count": 0,
            "island_map_count": 3,
        },
    )
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "pod_open_panel",
                "recommended_control": "pod_open_door",
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
            },
        ]
    )
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: calls.append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_timer_pause_guard_once",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not route")),
    )

    result = commands.cmd_lightning_attempt(
        auto_clear_panels=True,
        pause_on_stop=True,
    )

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_CLEARED"
    assert calls == ["reward_continue", "bottom_continue"]
    assert result["action"]["clear_result"]["visible_ui"]["visible_ui"] == (
        "pod_open_panel"
    )
    assert result["action"]["clear_result"]["reason"] == "panel_chain_cleared"


def test_lightning_clear_panel_chain_repeats_same_class(monkeypatch):
    states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "pod_open_panel",
                "recommended_control": "pod_open_door",
            },
        ]
    )
    calls = []

    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(states))
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: calls.append(control)
        or {"status": "OK", "control": control},
    )

    result = commands._lightning_clear_visible_panel_chain()

    assert result["status"] == "OK"
    assert result["reason"] == "panel_chain_cleared"
    assert calls == ["reward_continue", "bottom_continue"]
    assert result["visible_ui"]["visible_ui"] == "pod_open_panel"


def test_lightning_attempt_auto_clears_safe_panel_without_bridge(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {"status": "NO_BRIDGE"},
    )
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
            },
        ]
    )
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: calls.append(control)
        or {"status": "OK", "control": control},
    )

    result = commands.cmd_lightning_attempt(auto_clear_panels=True)

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_CLEARED"
    assert result["reason"] == "auto_clear_safe_panel_without_bridge"
    assert result["action"]["control"] == "reward_continue"
    assert calls == ["reward_continue", "bottom_continue"]


def test_lightning_attempt_auto_clears_post_combat_panels(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = {"clear": 0}

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 4,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 0,
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_loop",
        lambda **kwargs: {
            "status": "LIGHTNING_LOOP_STOPPED",
            "reason": "terminal_or_mission_end",
        },
    )

    def fake_clear(**kwargs):
        calls["clear"] += 1
        return {
            "status": "OK",
            "reason": "panel_chain_cleared",
            "steps": [
                {
                    "control": "reward_continue",
                    "click_result": {"status": "OK"},
                }
            ],
        }

    monkeypatch.setattr(commands, "_lightning_clear_visible_panel_chain", fake_clear)
    monkeypatch.setattr(
        commands,
        "_lightning_timer_pause_guard_once",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )

    result = commands.cmd_lightning_attempt(
        auto_clear_panels=True,
        pause_on_stop=True,
    )

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_CLEARED"
    assert result["reason"] == "post_combat_auto_clear_safe_panel"
    assert result["action"]["post_combat_clear_result"]["reason"] == "panel_chain_cleared"
    assert result["pause_guard"]["status"] == "OK"
    assert calls["clear"] == 1


def test_lightning_segment_continues_panel_clear_to_route_ready(monkeypatch):
    attempts = iter(
        [
            {
                "status": "LIGHTNING_ATTEMPT_PANEL_CLEARED",
                "reason": "auto_clear_safe_panel",
                "action": {
                    "action": "clear_visible_panel",
                    "clear_result": {"status": "OK", "steps": [{}]},
                },
            },
            {
                "status": "LIGHTNING_ATTEMPT_ROUTE_READY",
                "recommendation": {
                    "top3": [{"mission_id": "Mission_Train", "region_id": 2}],
                },
                "primary_next_command": (
                    "python3 game_loop.py lightning_segment "
                    "--route-visual-region-index 0 "
                    "--route-start-mode dialogue-region-repeat-preview-board"
                ),
                "primary_route_candidate_index": 0,
                "primary_route_target_hint": {
                    "mission_id": "Mission_Train",
                    "match_label": "Mission_Train",
                },
            },
        ]
    )
    calls = []

    def fake_attempt(**kwargs):
        calls.append(kwargs)
        return next(attempts)

    monkeypatch.setattr(commands, "cmd_lightning_attempt", fake_attempt)
    monkeypatch.setattr(
        commands,
        "_lightning_timer_pause_guard_once",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)

    result = commands.cmd_lightning_segment()

    assert result["reason"] == "route_ready"
    assert result["steps_attempted"] == 2
    assert result["steps"][0]["step_wall_seconds"] >= 0
    assert result["steps"][0]["segment_elapsed_seconds"] >= 0
    assert result["steps"][0]["panel_clear_steps"] == 1
    assert result["steps"][1]["top_mission"] == "Mission_Train"
    assert result["steps"][1]["primary_route_candidate_index"] == 0
    assert result["primary_next_command"].endswith(
        "--route-visual-region-index 0 --route-start-mode dialogue-region-repeat-preview-board"
    )
    assert result["primary_route_target_hint"]["match_label"] == "Mission_Train"
    assert calls[0]["run_preflight"] is True
    assert calls[1]["run_preflight"] is False
    assert all(call["pause_on_stop"] is False for call in calls)
    assert all(call["lightning_speed_loss_policy"] is True for call in calls)
    assert result["pause_guard"]["status"] == "OK"


def test_lightning_segment_dirty_consent_survives_panel_clear_until_combat(monkeypatch):
    attempts = iter(
        [
            {
                "status": "LIGHTNING_ATTEMPT_PANEL_CLEARED",
                "reason": "auto_clear_safe_panel",
                "action": {"action": "clear_visible_panel"},
            },
            {
                "status": "LIGHTNING_ATTEMPT_STOPPED",
                "reason": "combat_loop_returned",
                "action": {
                    "action": "combat_loop",
                    "combat_loop": {
                        "reason": "SAFETY_BLOCKED",
                        "wall_seconds": 12.5,
                        "turns_attempted": 2,
                        "end_turn_clicks": 1,
                        "turns": [
                            {
                                "loop_index": 0,
                                "turn": 1,
                                "status": "PLAN",
                                "auto_turn_wall_seconds": 3.2,
                                "turn_wall_seconds": 5.4,
                            }
                        ],
                    },
                },
            },
        ]
    )
    calls = []

    def fake_attempt(**kwargs):
        calls.append(kwargs)
        return next(attempts)

    monkeypatch.setattr(commands, "cmd_lightning_attempt", fake_attempt)
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)

    result = commands.cmd_lightning_segment(
        allow_dirty_plan=True,
        candidate_rank=17,
        dirty_consent_id="dirty-ok",
        allow_protected_objective_loss=True,
        allow_objective_loss=True,
    )

    assert result["reason"] == "combat_loop_returned"
    assert result["dirty_consent_still_pending"] is False
    assert result["steps"][1]["combat_loop_wall_seconds"] == 12.5
    assert result["steps"][1]["combat_turns_attempted"] == 2
    assert result["steps"][1]["combat_end_turn_clicks"] == 1
    assert result["steps"][1]["combat_turn_timings"] == [
        {
            "loop_index": 0,
            "turn": 1,
            "status": "PLAN",
            "auto_turn_wall_seconds": 3.2,
            "turn_wall_seconds": 5.4,
        }
    ]
    assert calls[0]["allow_dirty_plan"] is True
    assert calls[0]["candidate_rank"] == 17
    assert calls[0]["dirty_consent_id"] == "dirty-ok"
    assert calls[1]["allow_dirty_plan"] is True
    assert calls[1]["candidate_rank"] == 17
    assert calls[1]["dirty_consent_id"] == "dirty-ok"


def test_lightning_segment_limits_combat_burst_when_wall_cap_is_set(monkeypatch):
    calls = []
    attempts = iter(
        [
            {
                "status": "LIGHTNING_ATTEMPT_STOPPED",
                "reason": "combat_loop_returned",
                "action": {
                    "action": "combat_loop",
                    "combat_loop": {"reason": "max_turns_reached"},
                },
            },
            {"status": "LIGHTNING_ATTEMPT_ROUTE_READY"},
        ]
    )

    def fake_attempt(**kwargs):
        calls.append(kwargs)
        return next(attempts)

    monkeypatch.setattr(commands, "cmd_lightning_attempt", fake_attempt)
    monkeypatch.setattr(
        commands,
        "_lightning_timer_pause_guard_once",
        lambda **kwargs: {"status": "OK", "reason": "already_paused"},
    )
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)

    result = commands.cmd_lightning_segment(
        max_steps=2,
        max_turns=6,
        max_wall_seconds=120,
    )

    assert result["reason"] == "route_ready"
    assert [call["max_turns"] for call in calls] == [1, 1]


def test_lightning_segment_stops_between_steps_after_wall_cap(monkeypatch):
    calls = []
    ticks = iter([0.0, 0.0, 0.0, 2.0, 2.0])

    def fake_monotonic():
        return next(ticks, 2.0)

    def fake_attempt(**kwargs):
        calls.append(kwargs)
        return {
            "status": "LIGHTNING_ATTEMPT_PANEL_CLEARED",
            "reason": "auto_clear_safe_panel",
            "action": {"action": "clear_visible_panel"},
        }

    monkeypatch.setattr(commands.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(commands, "cmd_lightning_attempt", fake_attempt)
    monkeypatch.setattr(
        commands,
        "_lightning_timer_pause_guard_once",
        lambda **kwargs: {"status": "OK", "reason": "already_paused"},
    )

    result = commands.cmd_lightning_segment(
        max_steps=3,
        max_wall_seconds=1,
    )

    assert result["reason"] == "segment_wall_seconds_exceeded"
    assert result["steps_attempted"] == 1
    assert len(calls) == 1


def test_lightning_segment_stops_on_visible_map_without_bridge(monkeypatch):
    monkeypatch.setattr(
        commands,
        "cmd_lightning_attempt",
        lambda **kwargs: {
            "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
            "reason": "bridge_snapshot_unavailable_visible_island_map",
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_timer_pause_guard_once",
        lambda **kwargs: {"status": "OK", "reason": "already_paused"},
    )

    result = commands.cmd_lightning_segment(max_steps=3)

    assert result["reason"] == "visible_island_map_without_bridge"
    assert result["steps_attempted"] == 1
    assert result["pause_guard"]["status"] == "OK"


def test_lightning_segment_starts_route_from_stale_deployment_map(monkeypatch):
    attempts = iter(
        [
            {"status": "LIGHTNING_ATTEMPT_ROUTE_READY"},
        ]
    )
    route_calls = []

    monkeypatch.setattr(commands, "cmd_lightning_attempt", lambda **kwargs: next(attempts))
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda *args, **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_route_start",
        lambda **kwargs: route_calls.append(kwargs) or {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)

    result = commands.cmd_lightning_segment(
        max_steps=2,
        route_visual_region_index=1,
    )

    assert result["reason"] == "route_ready"
    assert result["route_start_performed"] is True
    assert route_calls[0]["visual_region_index"] == 1
    assert result["steps"][0]["phase"] == "route_start"
    assert result["steps"][1]["status"] == "LIGHTNING_ATTEMPT_ROUTE_READY"


def test_lightning_segment_auto_starts_scored_primary_route(monkeypatch):
    attempts = iter(
        [
            {
                "status": "LIGHTNING_ATTEMPT_ROUTE_READY",
                "primary_route_candidate": {
                    "index": 2,
                    "mission_id": "Mission_Train",
                    "score": 47,
                    "auto_route_allowed": True,
                },
            },
            {
                "status": "LIGHTNING_ATTEMPT_STOPPED",
                "reason": "deployment_waiting_for_ui_settle",
            },
        ]
    )
    route_calls = []
    attempt_calls = []

    def fake_attempt(**kwargs):
        attempt_calls.append(kwargs)
        return next(attempts)

    monkeypatch.setattr(commands, "cmd_lightning_attempt", fake_attempt)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_route_start",
        lambda **kwargs: route_calls.append(kwargs) or {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)

    result = commands.cmd_lightning_segment(max_steps=2, route_auto_start=True)

    assert result["reason"] == "deployment_waiting_for_ui_settle"
    assert result["route_start_performed"] is True
    assert route_calls[0]["visual_region_index"] == 2
    assert route_calls[0]["start_mode"] == "dialogue-region-repeat-preview-board"
    assert result["steps"][0]["route_auto_start_mission"] == "Mission_Train"
    assert attempt_calls[1]["expected_route_mission_id"] == "Mission_Train"


def test_lightning_segment_infers_expected_route_for_explicit_visual_start(monkeypatch):
    route_calls = []
    attempt_calls = []

    def fake_route_start(**kwargs):
        route_calls.append(kwargs)
        return {
            "status": "OK",
            "expected_route_mission_id": "Mission_Armored_Train",
            "inferred_expected_route_mission_id": "Mission_Armored_Train",
        }

    def fake_attempt(**kwargs):
        attempt_calls.append(kwargs)
        return {
            "status": "LIGHTNING_ATTEMPT_STOPPED",
            "reason": "deployment_waiting_for_ui_settle",
        }

    monkeypatch.setattr(commands, "cmd_lightning_route_start", fake_route_start)
    monkeypatch.setattr(commands, "cmd_lightning_attempt", fake_attempt)
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)

    result = commands.cmd_lightning_segment(
        max_steps=2,
        route_visual_region_index=0,
        run_preflight=False,
    )

    assert result["reason"] == "deployment_waiting_for_ui_settle"
    assert route_calls[0]["verify_route"] is True
    assert route_calls[0]["expected_route_mission_id"] is None
    assert attempt_calls[0]["expected_route_mission_id"] == "Mission_Armored_Train"


def test_lightning_segment_uses_actual_mission_after_playable_route_mismatch(monkeypatch):
    route_calls = []
    attempt_calls = []

    def fake_route_start(**kwargs):
        route_calls.append(kwargs)
        return {
            "status": "OK",
            "reason": "route_mission_mismatch_after_start_playable",
            "expected_route_mission_id": "Mission_Belt",
            "actual_started_mission_id": "Mission_Missiles",
            "click_result": {
                "status": "OK",
                "reason": "route_mission_mismatch_after_start_playable",
                "actual_started_mission_id": "Mission_Missiles",
                "route_mismatch_warning": {
                    "expected_mission_id": "Mission_Belt",
                    "actual_mission_id": "Mission_Missiles",
                    "policy": "continue_loaded_playable_mission",
                },
            },
        }

    def fake_attempt(**kwargs):
        attempt_calls.append(kwargs)
        return {
            "status": "LIGHTNING_ATTEMPT_STOPPED",
            "reason": "deployment_waiting_for_ui_settle",
        }

    monkeypatch.setattr(commands, "cmd_lightning_route_start", fake_route_start)
    monkeypatch.setattr(commands, "cmd_lightning_attempt", fake_attempt)
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)

    result = commands.cmd_lightning_segment(
        max_steps=2,
        route_visual_region_index=0,
        route_target_mission_id="Mission_Belt",
        run_preflight=False,
    )

    assert result["reason"] == "deployment_waiting_for_ui_settle"
    assert route_calls[0]["expected_route_mission_id"] == "Mission_Belt"
    assert attempt_calls[0]["expected_route_mission_id"] == "Mission_Missiles"
    assert result["steps"][0]["route_mismatch_warning"]["actual_mission_id"] == (
        "Mission_Missiles"
    )


def test_lightning_segment_auto_starts_former_slow_primary_route(monkeypatch):
    route_calls = []

    monkeypatch.setattr(
        commands,
        "cmd_lightning_attempt",
        lambda **kwargs: {
            "status": "LIGHTNING_ATTEMPT_ROUTE_READY",
            "primary_route_candidate": {
                "index": 1,
                "mission_id": "Mission_Artillery",
                "score": -42,
                "auto_route_allowed": False,
            },
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_route_start",
        lambda **kwargs: route_calls.append(kwargs)
        or {"status": "OK", "reason": "route_start_sequence_clicked"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )

    result = commands.cmd_lightning_segment(route_auto_start=True, max_steps=2)

    assert result["route_start_performed"] is True
    assert route_calls[0]["visual_region_index"] == 1
    assert route_calls[0]["expected_route_mission_id"] == "Mission_Artillery"


def test_lightning_segment_auto_start_allows_unverified_visual_route(monkeypatch):
    route_calls = []

    monkeypatch.setattr(
        commands,
        "cmd_lightning_attempt",
        lambda **kwargs: {
            "status": "LIGHTNING_ATTEMPT_ROUTE_READY",
            "primary_route_candidate": {
                "index": 0,
                "window_x": 938,
                "window_y": 417,
            },
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_route_start",
        lambda **kwargs: route_calls.append(kwargs)
        or {"status": "OK", "reason": "route_start_sequence_clicked"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )

    result = commands.cmd_lightning_segment(route_auto_start=True, max_steps=2)

    assert result["route_start_performed"] is True
    assert route_calls[0]["visual_region_index"] == 0
    assert route_calls[0]["expected_route_mission_id"] is None
    assert route_calls[0]["allow_unverified_preview_start"] is True


def test_lightning_segment_starts_selected_visual_route_then_continues(monkeypatch):
    attempts = iter(
        [
            {
                "status": "LIGHTNING_ATTEMPT_ROUTE_READY",
                "recommendation": {
                    "top3": [{"mission_id": "Mission_Tides", "region_id": 4}],
                },
            },
        ]
    )
    attempt_calls = []
    route_calls = []

    def fake_attempt(**kwargs):
        attempt_calls.append(kwargs)
        return next(attempts)

    def fake_route_start(**kwargs):
        route_calls.append(kwargs)
        return {
            "status": "OK",
            "reason": "route_start_sequence_clicked",
            "selected_visual_region": {
                "index": kwargs["visual_region_index"],
                "window_x": 743,
                "window_y": 316,
            },
            "click_result": {"status": "OK", "steps": [{}, {}, {}]},
        }

    monkeypatch.setattr(commands, "cmd_lightning_attempt", fake_attempt)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda *args, **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(commands, "cmd_lightning_route_start", fake_route_start)
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)

    result = commands.cmd_lightning_segment(
        max_steps=2,
        route_visual_region_index=3,
        route_target_mission_id="Mission_Tides",
        route_start_mode="dialogue-region-repeat-preview-board-twice",
    )

    assert result["reason"] == "route_ready"
    assert result["route_start_performed"] is True
    assert result["steps_attempted"] == 2
    assert result["steps"][0]["phase"] == "route_start"
    assert result["steps"][0]["visual_region_index"] == 3
    assert result["steps"][0]["click_steps"] == 3
    assert len(route_calls) == 1
    assert route_calls[0]["visual_region_index"] == 3
    assert route_calls[0]["run_preflight"] is False
    assert route_calls[0]["verify_route"] is False
    assert route_calls[0]["start_mode"] == "dialogue-region-repeat-preview-board-twice"
    assert len(attempt_calls) == 1
    assert attempt_calls[0]["run_preflight"] is False
    assert attempt_calls[0]["expected_route_mission_id"] == "Mission_Tides"


def test_lightning_segment_stops_when_visual_route_start_blocks(monkeypatch):
    monkeypatch.setattr(
        commands,
        "cmd_lightning_attempt",
        lambda **kwargs: {"status": "LIGHTNING_ATTEMPT_ROUTE_READY"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_route_start",
        lambda **kwargs: {
            "status": "BLOCKED",
            "reason": "visual_region_index_not_found",
            "requested_visual_region_index": kwargs["visual_region_index"],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )

    result = commands.cmd_lightning_segment(
        route_visual_region_index=8,
    )

    assert result["reason"] == "visual_region_index_not_found"
    assert result["route_start_performed"] is True
    assert result["last_route_start"]["requested_visual_region_index"] == 8
    assert result["steps"][-1]["phase"] == "route_start"


def test_deploy_recommended_skips_already_placed_mechs(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    placed = {0: (2, 3)}
    deploy_calls = []

    def board():
        return SimpleNamespace(
            units=[
                SimpleNamespace(uid=uid, type=f"Mech{uid}", is_mech=True, hp=3, x=x, y=y)
                for uid, (x, y) in placed.items()
            ]
        )

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (
            board(),
            {
                "turn": 0,
                "phase": "combat_player",
                "deployment_zone": [[2, 3], [2, 4], [3, 3], [3, 4]],
            },
        ),
    )
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "_deployable_mechs",
        lambda _board, _session, profile="Alpha": [
            {"uid": 0, "type": "ElectricMech"},
            {"uid": 1, "type": "WallMech"},
            {"uid": 2, "type": "RockartMech"},
        ],
    )
    monkeypatch.setattr(
        commands,
        "recommend_deploy_tiles",
        lambda _board, _zone: [
            {"x": 2, "y": 3, "hazard": None, "hazard_warning": False},
            {"x": 2, "y": 4, "hazard": None, "hazard_warning": False},
            {"x": 3, "y": 3, "hazard": None, "hazard_warning": False},
        ],
    )

    def fake_deploy(uid, x, y, *, timeout=None):
        deploy_calls.append((uid, x, y))
        placed[uid] = (x, y)
        return "OK"

    monkeypatch.setattr(commands, "deploy_mech", fake_deploy)

    result = commands.cmd_deploy_recommended()

    assert result["status"] == "OK"
    assert deploy_calls == [(1, 2, 4), (2, 3, 3)]
    assert [entry["uid"] for entry in result["deployments"]] == [1, 2]
    assert result["existing_deployments"] == {"0": [2, 3]}


def test_deploy_recommended_recovers_when_timeout_still_places_mech(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    placed = {}
    deploy_calls = []

    def board():
        return SimpleNamespace(
            units=[
                SimpleNamespace(uid=uid, type=f"Mech{uid}", is_mech=True, hp=3, x=x, y=y)
                for uid, (x, y) in placed.items()
            ]
        )

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (
            board(),
            {
                "turn": 0,
                "phase": "combat_player",
                "deployment_zone": [[2, 4], [3, 3], [3, 4]],
            },
        ),
    )
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(commands, "is_bridge_alive", lambda max_stale_sec=1.0: True)
    monkeypatch.setattr(
        commands,
        "_deployment_click_fallback",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("should recover through bridge read")
        ),
    )
    monkeypatch.setattr(
        commands,
        "_deployable_mechs",
        lambda _board, _session, profile="Alpha": [
            {"uid": 0, "type": "ElectricMech"},
            {"uid": 1, "type": "WallMech"},
        ],
    )
    monkeypatch.setattr(
        commands,
        "recommend_deploy_tiles",
        lambda _board, _zone: [
            {"x": 2, "y": 4, "hazard": None, "hazard_warning": False},
            {"x": 3, "y": 3, "hazard": None, "hazard_warning": False},
        ],
    )

    def fake_deploy(uid, x, y, *, timeout=None):
        deploy_calls.append((uid, x, y))
        placed[uid] = (x, y)
        if uid == 0:
            raise TimeoutError("late ACK")
        return "OK"

    monkeypatch.setattr(commands, "deploy_mech", fake_deploy)

    result = commands.cmd_deploy_recommended()

    assert result["status"] == "OK"
    assert deploy_calls == [(0, 2, 4), (1, 3, 3)]
    assert result["deployments"][0]["timeout_recovered"] is True
    assert result["deployments"][0]["ack"].startswith("ACK_TIMEOUT_BUT_PLACED")


def test_deploy_recommended_uses_ui_fallback_when_bridge_deploy_times_out(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    deploy_calls = []
    fallback_calls = []

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (
            SimpleNamespace(units=[]),
            {
                "turn": 0,
                "phase": "combat_player",
                "deployment_zone": [[2, 4], [3, 3], [3, 4]],
            },
        ),
    )
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "is_bridge_alive", lambda max_stale_sec=1.0: False)
    monkeypatch.setattr(
        commands,
        "_clear_pending_bridge_command",
        lambda reason: {"status": "OK", "reason": reason, "cleared": ["cmd"]},
    )
    monkeypatch.setattr(
        commands,
        "_deployable_mechs",
        lambda _board, _session, profile="Alpha": [
            {"uid": 0, "type": "ElectricMech"},
            {"uid": 1, "type": "WallMech"},
            {"uid": 2, "type": "RockartMech"},
        ],
    )
    monkeypatch.setattr(
        commands,
        "recommend_deploy_tiles",
        lambda _board, _zone: [
            {"x": 2, "y": 4, "hazard": None, "hazard_warning": False},
            {"x": 3, "y": 3, "hazard": None, "hazard_warning": False},
            {"x": 3, "y": 4, "hazard": None, "hazard_warning": False},
        ],
    )

    def fake_deploy(uid, x, y, *, timeout=None):
        deploy_calls.append((uid, x, y, timeout))
        raise TimeoutError("deployment bridge asleep")

    def fake_fallback(pairs, *, reason, dry_run=False):
        fallback_calls.append({
            "pairs": [
                (int(mech["uid"]), int(tile["x"]), int(tile["y"]))
                for mech, tile in pairs
            ],
            "reason": reason,
        })
        return {
            "status": "OK",
            "reason": reason,
            "steps": [
                {
                    "uid": int(mech["uid"]),
                    "mech_type": mech["type"],
                    "bridge": [int(tile["x"]), int(tile["y"])],
                    "visual": commands._visual_tile(int(tile["x"]), int(tile["y"])),
                }
                for mech, tile in pairs
            ],
        }

    monkeypatch.setattr(commands, "deploy_mech", fake_deploy)
    monkeypatch.setattr(commands, "_deployment_click_fallback", fake_fallback)

    result = commands.cmd_deploy_recommended()

    assert result["status"] == "WARN"
    assert result["reason"] == "bridge_deploy_timed_out_used_ui_fallback"
    assert deploy_calls == [
        (0, 2, 4, commands._LIGHTNING_DEPLOY_BRIDGE_TIMEOUT_SECONDS)
    ]
    assert fallback_calls == [
        {
            "pairs": [(0, 2, 4), (1, 3, 3), (2, 3, 4)],
            "reason": "bridge_deploy_timeout_uid_0",
        }
    ]
    assert [entry["uid"] for entry in result["deployments"]] == [0, 1, 2]
    assert all(entry["ui_fallback"] for entry in result["deployments"])
    assert result["stale_bridge_cleanup"]["cleared"] == ["cmd"]


def test_dirty_consented_ordinary_grid_loss_satisfies_threat_audit():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    threat_audit = {
        "still_threatened_count": 1,
        "entries": [{"target_visual": "D4"}],
    }
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "grid_damage", "blocking": True},
            {"kind": "building_hp_loss", "blocking": True},
        ],
        "current": {
            "grid_power": 5,
            "building_hp_total": 9,
            "buildings_alive": 6,
        },
        "predicted": {
            "grid_power": 4,
            "building_hp_total": 8,
            "buildings_alive": 6,
        },
    }

    assert commands._threat_audit_requires_block(
        threat_audit,
        plan_safety,
        session,
        dirty_consent_validated=False,
    ) is True
    assert commands._threat_audit_requires_block(
        threat_audit,
        plan_safety,
        session,
        dirty_consent_validated=True,
    ) is False


def test_dirty_consented_grid_loss_with_mech_hp_satisfies_threat_audit():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    threat_audit = {
        "still_threatened_count": 1,
        "entries": [{"target_visual": "F3"}],
    }
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "grid_damage", "blocking": True},
            {"kind": "building_hp_loss", "blocking": True},
            {"kind": "mech_hp_loss", "blocking": True},
        ],
        "current": {
            "grid_power": 4,
            "building_hp_total": 9,
            "buildings_alive": 8,
            "mechs_alive": 3,
            "mech_hp_total": 8,
        },
        "predicted": {
            "grid_power": 3,
            "building_hp_total": 8,
            "buildings_alive": 8,
            "mechs_alive": 3,
            "mech_hp_total": 6,
        },
    }

    assert commands._threat_audit_requires_block(
        threat_audit,
        plan_safety,
        session,
        dirty_consent_validated=True,
    ) is False


def test_lightning_speed_loss_policy_allows_train_speed_trade():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "grid_damage", "blocking": True},
            {"kind": "building_destroyed", "blocking": True},
            {"kind": "building_hp_loss", "blocking": True},
            {"kind": "protected_objective_unit_lost", "blocking": True},
        ],
        "current": {
            "mission_id": "Mission_Train",
            "grid_power": 2,
            "buildings_alive": 7,
            "building_hp_total": 9,
            "protected_objective_units_alive": 1,
            "mechs_alive": 3,
        },
        "predicted": {
            "mission_id": "Mission_Train",
            "grid_power": 1,
            "buildings_alive": 6,
            "building_hp_total": 8,
            "protected_objective_units_alive": 0,
            "mechs_alive": 3,
        },
    }

    assert commands._allow_lightning_war_speed_loss(session, plan_safety) is True
    summary = commands._lightning_speed_loss_summary(plan_safety)
    assert summary["status"] == "ALLOWED"
    assert summary["losses"]["grid_power"] == 1
    assert summary["losses"]["protected_objective_units_alive"] == 1


def test_lightning_speed_loss_policy_rejects_timeline_collapse():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "grid_damage", "blocking": True},
            {"kind": "grid_timeline_collapse", "blocking": True},
        ],
        "current": {"grid_power": 1, "mechs_alive": 3},
        "predicted": {"grid_power": 0, "mechs_alive": 3},
    }

    assert commands._allow_lightning_war_speed_loss(session, plan_safety) is False


def test_lightning_speed_loss_policy_rejects_mech_loss():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "grid_damage", "blocking": True},
            {"kind": "mech_lost", "blocking": True},
        ],
        "current": {"grid_power": 3, "mechs_alive": 3},
        "predicted": {"grid_power": 2, "mechs_alive": 2},
    }

    assert commands._allow_lightning_war_speed_loss(session, plan_safety) is False


def test_lightning_speed_loss_policy_allows_nonlethal_mech_hp_loss():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "mech_hp_loss", "blocking": True},
        ],
        "current": {"mechs_alive": 3, "mech_hp_total": 8},
        "predicted": {"mechs_alive": 3, "mech_hp_total": 7},
    }

    assert commands._allow_lightning_war_speed_loss(session, plan_safety) is True


def test_lightning_speed_policy_satisfies_threat_audit_without_dirty_consent():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    threat_audit = {
        "still_threatened_count": 1,
        "entries": [{"target_visual": "E7"}],
    }
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "grid_damage", "blocking": True},
            {"kind": "building_destroyed", "blocking": True},
            {"kind": "protected_objective_unit_lost", "blocking": True},
        ],
        "current": {
            "grid_power": 2,
            "buildings_alive": 7,
            "building_hp_total": 9,
            "protected_objective_units_alive": 1,
        },
        "predicted": {
            "grid_power": 1,
            "buildings_alive": 6,
            "building_hp_total": 8,
            "protected_objective_units_alive": 0,
        },
    }

    assert commands._threat_audit_requires_block(
        threat_audit,
        plan_safety,
        session,
        dirty_consent_validated=False,
        lightning_speed_loss_allowed=True,
    ) is False


def test_lightning_speed_policy_allows_clean_unplanned_building_threat():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    threat_audit = {
        "still_threatened_count": 1,
        "entries": [{"target_visual": "B5", "target_hp": 2}],
    }
    plan_safety = {
        "blocking": False,
        "violations": [],
        "current": {
            "grid_power": 6,
            "objective_buildings_alive": 0,
            "objective_building_hp_total": 0,
            "protected_objective_units_alive": 0,
            "pylons_alive": None,
            "pylon_hp_total": None,
            "bigbomb_alive": False,
        },
        "predicted": {"grid_power": 6},
    }

    assert commands._lightning_speed_policy_active_for_plan(session, plan_safety) is True
    assert commands._threat_audit_requires_block(
        threat_audit,
        plan_safety,
        session,
        lightning_speed_loss_allowed=True,
    ) is False


def test_lightning_speed_policy_ignores_covered_audit_entries():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    threat_audit = {
        "still_threatened_count": 1,
        "entries": [
            {
                "target_visual": "B7",
                "target_hp": 1,
                "coverage": {"reason": "attacker_killed"},
            },
            {
                "target_visual": "B3",
                "target_hp": 2,
                "coverage": {"reason": "still_threatened_current"},
            },
        ],
    }
    plan_safety = {
        "blocking": False,
        "violations": [],
        "current": {
            "grid_power": 5,
            "objective_buildings_alive": 1,
            "objective_building_hp_total": 1,
            "protected_objective_units_alive": 0,
            "pylons_alive": None,
            "pylon_hp_total": None,
            "bigbomb_alive": False,
        },
    }

    assert commands._threat_audit_requires_block(
        threat_audit,
        plan_safety,
        session,
        lightning_speed_loss_allowed=True,
    ) is False


def test_lightning_speed_policy_allows_legacy_still_threatened_reason():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    threat_audit = {
        "still_threatened_count": 1,
        "entries": [
            {
                "target_visual": "C3",
                "target_hp": 2,
                "coverage": {"reason": "still_threatened"},
            },
        ],
    }
    plan_safety = {
        "blocking": False,
        "violations": [],
        "current": {
            "grid_power": 5,
            "objective_buildings_alive": 1,
            "objective_building_hp_total": 1,
            "protected_objective_units_alive": 0,
            "pylons_alive": None,
            "pylon_hp_total": None,
            "bigbomb_alive": False,
        },
    }

    assert commands._threat_audit_requires_block(
        threat_audit,
        plan_safety,
        session,
        lightning_speed_loss_allowed=True,
    ) is False


def test_lightning_speed_policy_blocks_unplanned_threat_if_grid_would_collapse():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    threat_audit = {
        "still_threatened_count": 1,
        "entries": [{"target_visual": "B5", "target_hp": 2}],
    }
    plan_safety = {
        "blocking": False,
        "violations": [],
        "current": {
            "grid_power": 1,
            "objective_buildings_alive": 0,
            "objective_building_hp_total": 0,
            "protected_objective_units_alive": 0,
        },
    }

    assert commands._threat_audit_requires_block(
        threat_audit,
        plan_safety,
        session,
        lightning_speed_loss_allowed=True,
    ) is True


def test_lightning_speed_policy_blocks_unplanned_pylon_threat():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    threat_audit = {
        "still_threatened_count": 1,
        "entries": [{"target_visual": "B5", "target_hp": 2}],
    }
    plan_safety = {
        "blocking": False,
        "violations": [],
        "current": {
            "grid_power": 6,
            "pylons_alive": 1,
            "pylon_hp_total": 1,
        },
    }

    assert commands._threat_audit_requires_block(
        threat_audit,
        plan_safety,
        session,
        lightning_speed_loss_allowed=True,
    ) is True


def test_lightning_war_allows_pod_only_loss():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "pod_unrecovered_final", "blocking": True},
        ],
    }

    assert commands._allow_lightning_war_pod_loss(session, plan_safety) is True


def test_lightning_war_pod_loss_allowance_does_not_cover_grid_loss():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "pod_unrecovered_final", "blocking": True},
            {"kind": "grid_damage", "blocking": True},
        ],
    }

    assert commands._allow_lightning_war_pod_loss(session, plan_safety) is False


def test_lightning_attempt_does_not_treat_session_age_as_game_budget(monkeypatch):
    old_session = RunSession(
        run_id="20000101_000000_000",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    monkeypatch.setattr(commands, "_load_session", lambda: old_session)
    monkeypatch.setattr(
        commands,
        "_lightning_read_save_game_timer",
        lambda profile="Alpha": {
            "status": "OK",
            "source": "saveData_current_time",
            "game_seconds": 0.0,
            "game_timer": "0:00:00",
        },
    )
    monkeypatch.setattr(commands, "is_bridge_active", lambda: False)

    result = commands.cmd_lightning_attempt(max_wall_seconds=1)

    assert result["status"] != "LIGHTNING_ATTEMPT_BUDGET_EXCEEDED"


def test_lightning_loop_blocks_pending_research(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        research_queue=[{"status": "pending", "type": "RockLauncher"}],
    )

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (_ for _ in ()).throw(RuntimeError("no live board")),
    )

    result = commands.cmd_lightning_loop(max_turns=1, pause_before_solve=False)

    assert result["status"] == "RESEARCH_REQUIRED"
    assert result["pending_research_count"] == 1


def test_lightning_loop_defers_stale_research_absent_from_board(monkeypatch):
    from src.research import orchestrator

    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        research_queue=[
            {
                "status": "pending",
                "type": "TotallyMadeUpEnemy",
                "kind": "behavior_novelty",
            }
        ],
    )

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (object(), {"phase": "combat_player"}),
    )
    monkeypatch.setattr(orchestrator, "drain_stale_behavior_novelty", lambda s: [])
    monkeypatch.setattr(orchestrator, "has_actionable_research", lambda s, b: False)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(
        commands,
        "cmd_auto_turn",
        lambda **kwargs: {"status": "TERMINAL_OR_MISSION_END", "turn": 1},
    )

    result = commands.cmd_lightning_loop(max_turns=1, pause_before_solve=False)

    assert result["reason"] == "TERMINAL_OR_MISSION_END"
    assert result["research_gate"]["status"] == "DEFERRED"
    assert result["research_gate"]["pending_research_count"] == 1


def test_lightning_loop_ignores_background_mech_weapon_research(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        research_queue=[
            {
                "status": "pending",
                "type": "ElectricMech",
                "kind": "mech_weapon",
                "slot": 1,
            }
        ],
    )

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(
        commands,
        "cmd_auto_turn",
        lambda **kwargs: {"status": "TERMINAL_OR_MISSION_END", "turn": 1},
    )

    result = commands.cmd_lightning_loop(max_turns=1, pause_before_solve=False)

    assert result["reason"] == "TERMINAL_OR_MISSION_END"
    assert result["turns_attempted"] == 1


def test_click_end_turn_prefers_window_local_coordinates(monkeypatch):
    calls = []

    def fake_window_click(x, y, **kwargs):
        calls.append((x, y, kwargs))
        return {"status": "OK", "window_x": x, "window_y": y}

    monkeypatch.setattr(
        "src.control.mac_click.click_window_point",
        fake_window_click,
    )

    result = commands._click_end_turn_from_plan_result(
        {
            "batch": [
                {
                    "type": "left_click",
                    "x": 341,
                    "y": 152,
                    "window_x": 126,
                    "window_y": 120,
                    "description": "Click End Turn",
                }
            ]
        }
    )

    assert result["status"] == "OK"
    assert calls == [(126, 120, {"description": "Click End Turn", "dry_run": False})]


def test_lightning_loop_stops_when_end_turn_click_not_observed(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = {"auto_turn": 0}

    def fake_auto_turn(**kwargs):
        calls["auto_turn"] += 1
        return {
            "status": "PLAN",
            "turn": 2,
            "actions_completed": 3,
            "batch": [
                {
                    "type": "left_click",
                    "x": 341,
                    "y": 152,
                    "window_x": 126,
                    "window_y": 120,
                }
            ],
        }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(
        commands,
        "_click_end_turn_from_plan_result",
        lambda plan: {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda turn_result: {"status": "END_TURN_CLICK_NOT_OBSERVED"},
    )

    result = commands.cmd_lightning_loop(max_turns=3, pause_before_solve=False)

    assert result["reason"] == "end_turn_click_not_observed"
    assert result["end_turn_clicks"] == 1
    assert result["turns"][0]["end_turn_observed"]["status"] == (
        "END_TURN_CLICK_NOT_OBSERVED"
    )
    assert calls["auto_turn"] == 1


def test_lightning_loop_treats_unknown_after_end_turn_as_mission_end(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = {"auto_turn": 0}

    def fake_auto_turn(**kwargs):
        calls["auto_turn"] += 1
        return {
            "status": "PLAN",
            "turn": 4,
            "actions_completed": 3,
            "batch": [
                {
                    "type": "left_click",
                    "x": 341,
                    "y": 152,
                    "window_x": 126,
                    "window_y": 120,
                }
            ],
        }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(
        commands,
        "_click_end_turn_from_plan_result",
        lambda plan: {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda turn_result: {
            "status": "OK",
            "reason": "phase_changed",
            "samples": [{"phase": "unknown", "turn": 4, "active_mechs": 0}],
        },
    )

    result = commands.cmd_lightning_loop(max_turns=3, pause_before_solve=False)

    assert result["reason"] == "terminal_or_mission_end"
    assert result["end_turn_clicks"] == 1
    assert calls["auto_turn"] == 1


def test_lightning_loop_stops_before_wait_when_terminal_panel_visible(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = {"auto_turn": 0}

    def fake_auto_turn(**kwargs):
        calls["auto_turn"] += 1
        return {
            "status": "PLAN",
            "turn": 4,
            "actions_completed": 3,
            "batch": [
                {
                    "type": "left_click",
                    "x": 341,
                    "y": 152,
                    "window_x": 126,
                    "window_y": 120,
                }
            ],
        }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(
        commands,
        "_click_end_turn_from_plan_result",
        lambda plan: {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda turn_result: {
            "status": "OK",
            "reason": "phase_changed",
            "samples": [{"phase": "combat_enemy", "turn": 4, "active_mechs": 0}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "reward_panel",
            "recommended_control": "reward_continue",
            "screenshot_path": "/tmp/region-secured.png",
        },
    )

    result = commands.cmd_lightning_loop(max_turns=3, pause_before_solve=False)

    assert result["reason"] == "terminal_or_mission_end"
    assert result["end_turn_clicks"] == 1
    assert result["turns_attempted"] == 2
    assert result["turns"][1]["status"] == "VISIBLE_TERMINAL_PANEL"
    assert calls["auto_turn"] == 1


def test_lightning_loop_treats_unknown_phase_error_as_mission_end(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(
        commands,
        "cmd_auto_turn",
        lambda **kwargs: {
            "error": "Not in combat_player phase: unknown",
            "phase": "unknown",
        },
    )

    result = commands.cmd_lightning_loop(max_turns=1, pause_before_solve=False)

    assert result["reason"] == "terminal_or_mission_end"
    assert result["turns"][0]["terminal_transition"] is True


def test_auto_turn_wait_stops_on_visible_terminal_panel(monkeypatch):
    calls = {"read": 0}

    def fake_read(**kwargs):
        calls["read"] += 1
        return {
            "status": "OK",
            "phase": "combat_enemy",
            "active_mechs": 0,
            "turn": 4,
        }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "cmd_read", fake_read)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "reward_panel",
            "recommended_control": "reward_continue",
            "screenshot_path": "/tmp/region-secured.png",
        },
    )

    result = commands.cmd_auto_turn(max_wait=30, wait_poll_interval=0.1)

    assert result["status"] == "TERMINAL_OR_MISSION_END"
    assert result["visible_ui"]["visible_ui"] == "reward_panel"
    assert calls["read"] == 1


def test_recommend_mission_reports_no_available_after_stale_filter(tmp_path):
    payload = {
        "grid_power": 7,
        "units": [
            {"mech": True, "hp": 3, "weapons": ["Prime_Lightning"]},
        ],
        "island_map": [
            {
                "region_id": 1,
                "mission_id": "Mission_Satellite",
                "bonus_objective_ids": [1],
                "environment": "Env_Null",
                "state": "hover_preview",
            },
            {
                "region_id": 2,
                "mission_id": "Mission_Repair",
                "bonus_objective_ids": [],
                "environment": "Env_RepairMission",
                "current": True,
            },
        ],
    }
    path = tmp_path / "stale_island_map.json"
    path.write_text(json.dumps(payload))

    result = commands.cmd_recommend_mission(
        island_map_json=str(path),
        routing="lightning_war",
    )

    assert result["status"] == "NO_AVAILABLE_MISSIONS"
    assert result["available"] == 2


def test_lightning_save_region_filter_marks_completed_and_overrun():
    save_text = """
    ["region0"] = {
        ["mission"] = "",
        ["state"] = 2,
        ["name"] = "Storage Vaults",
        ["objectives"] = {
            ["0"] = {["text"] = "Mission_ArmoredTrain_Obj", ["param1"] = "",},
        },
    },
    ["region5"] = {
        ["mission"] = "",
        ["state"] = 3,
        ["name"] = "Archivist Hall",
        ["objectives"] = {
            ["0"] = {["text"] = "Bonus_Simple_Grid", ["param1"] = "",},
            ["1"] = {["text"] = "Bonus_Simple_Asset", ["param1"] = "Str_Power_Name",},
        },
    },
    ["region4"] = {
        ["mission"] = "",
        ["state"] = 0,
        ["name"] = "Accord Repository",
        ["objectives"] = {
            ["0"] = {["text"] = "Mission_Satellite_Obj", ["param1"] = "",},
        },
    },
    """
    save_regions = commands._lightning_parse_save_region_entries(save_text)
    island_map = [
        {
            "region_id": 0,
            "mission_id": "Mission_Armored_Train",
            "bonus_objective_ids": [],
            "environment": "Env_Null",
        },
        {
            "region_id": 5,
            "mission_id": "Mission_Survive",
            "bonus_objective_ids": [3, 1],
            "asset_id": "Str_Power",
            "environment": "Env_Null",
        },
        {
            "region_id": 4,
            "mission_id": "Mission_Satellite",
            "bonus_objective_ids": [],
            "environment": "Env_Null",
        },
    ]

    annotated, summary = commands._lightning_annotate_island_map_with_save_regions(
        island_map,
        save_regions,
    )

    assert summary["status"] == "OK"
    assert summary["matched"] == 3
    assert summary["unavailable"] == 2
    assert annotated[0]["completed"] is True
    assert annotated[0]["save_region_name"] == "Storage Vaults"
    assert annotated[1]["overrun"] is True
    assert annotated[1]["save_region_name"] == "Archivist Hall"
    assert "completed" not in annotated[2]
    assert "overrun" not in annotated[2]
    assert annotated[2]["save_region_state_label"] == "available"


def _lightning_save_route_fixture() -> str:
    return """
    GameData = {["network"] = 6,
    ["current"] = {["weapons"] = {"Prime_Lightning", "", "Brute_Grapple", "", "Ranged_Rockthrow", ""},},}
    RegionData = {
    ["region1"] = {["mission"] = "Mission1", ["player"] = {["iCurrentTurn"] = 3,}, ["state"] = 1, ["name"] = "Old Fight", },
    ["region3"] = {["mission"] = "Mission3", ["player"] = {["iCurrentTurn"] = 0,}, ["state"] = 1, ["name"] = "Repair Flats", },
    ["region6"] = {["mission"] = "Mission6", ["player"] = {["iCurrentTurn"] = 0,}, ["state"] = 1, ["name"] = "Train Crossing", },
    ["iBattleRegion"] = 1,
    }
    GAME = {
    ["Missions"] = {
    [1] = {["ID"] = "Mission_Artillery", ["BonusObjs"] = {[1] = 1,}, ["AssetId"] = "Str_Battery", },
    [3] = {["ID"] = "Mission_Repair", ["BonusObjs"] = {}, ["DiffMod"] = 1, },
    [6] = {["ID"] = "Mission_Train", ["BonusObjs"] = {}, },
    },
    }
    """


def test_lightning_builds_routeable_save_island_map():
    result = commands._lightning_build_save_island_map_from_text(
        _lightning_save_route_fixture(),
    )

    assert result["status"] == "OK"
    assert result["grid_power"] == 6
    assert result["active_region_index"] == 1
    assert [entry["mission_id"] for entry in result["island_map"]] == [
        "Mission_Repair",
        "Mission_Train",
    ]
    assert result["island_map"][1]["save_region_name"] == "Train Crossing"


def test_recommend_mission_falls_back_to_save_route_slate(monkeypatch):
    save_result = commands._lightning_build_save_island_map_from_text(
        _lightning_save_route_fixture(),
    )

    monkeypatch.setattr(commands, "is_bridge_active", lambda: False)
    monkeypatch.setattr(
        commands,
        "_lightning_build_save_island_map",
        lambda profile: save_result,
    )

    result = commands.cmd_recommend_mission(routing="lightning_war")

    assert result["status"] == "OK"
    assert result["source"] == "saveData"
    assert result["top3"][0]["mission_id"] == "Mission_Train"
    assert result["speed_route_status"]["auto_start_allowed"] is True


def test_recommend_mission_scores_bridge_preview_when_slate_missing(monkeypatch):
    bridge_data = {
        "island_map": None,
        "mission_id": "Mission_Artillery",
        "in_active_mission": True,
        "phase": "unknown",
        "grid_power": 5,
        "units": [
            {"mech": True, "hp": 3, "weapons": ["Prime_Lightning"]},
        ],
    }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: (None, bridge_data))

    result = commands.cmd_recommend_mission(routing="lightning_war")

    assert result["status"] == "OK"
    assert result["source"] == "bridge_preview"
    assert result["top3"][0]["mission_id"] == "Mission_Artillery"
    assert result["speed_route_status"]["status"] == "AUTO_START_OK"
    assert result["speed_route_status"]["reason"] == "forced_bridge_preview_route"


def test_recommend_mission_allows_low_score_bridge_preview(monkeypatch):
    bridge_data = {
        "island_map": None,
        "mission_id": "Mission_Repair",
        "in_active_mission": True,
        "phase": "unknown",
        "grid_power": 5,
        "units": [
            {"mech": True, "hp": 3, "weapons": ["Prime_Lightning"]},
        ],
    }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: (None, bridge_data))

    result = commands.cmd_recommend_mission(routing="lightning_war")

    assert result["status"] == "OK"
    assert result["source"] == "bridge_preview"
    assert result["top3"][0]["mission_id"] == "Mission_Repair"
    assert result["speed_route_status"]["status"] == "AUTO_START_OK"
    assert result["speed_route_status"]["reason"] == "forced_bridge_preview_route"


def test_visible_map_route_plan_ignores_stale_bridge_preview(monkeypatch):
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "bridge_preview",
            "ranked": [{"mission_id": "Mission_Tides", "score": 23}],
            "top3": [{"mission_id": "Mission_Tides", "score": 23}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_recommend_save_routes",
        lambda **kwargs: {
            "status": "OK",
            "source": "saveData",
            "ranked": [
                {
                    "mission_id": "Mission_Train",
                    "save_region_index": 1,
                    "save_region_name": "Preserved Farms",
                    "score": 41,
                },
                {
                    "mission_id": "Mission_Repair",
                    "save_region_index": 0,
                    "save_region_name": "Archivist Hall",
                    "score": -12,
                },
            ],
            "top3": [
                {
                    "mission_id": "Mission_Train",
                    "save_region_index": 1,
                    "save_region_name": "Preserved Farms",
                    "score": 41,
                }
            ],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_extract_red_regions_from_image",
        lambda path: {
            "status": "OK",
            "regions": [
                {"index": 0, "window_x": 812, "window_y": 423},
                {"index": 1, "window_x": 938, "window_y": 417},
            ],
        },
    )

    result = commands._lightning_visible_map_route_plan(
        profile="Alpha",
        visible_ui={"status": "OK", "visible_ui": "island_map", "screenshot_path": "map.png"},
    )

    assert result["route_fallback"]["reason"] == (
        "visible_map_ignored_stale_bridge_preview"
    )
    assert result["recommendation"]["source"] == "saveData"
    assert result["route_start_candidates"][0]["mission_id"] == "Mission_Train"
    assert result["route_start_candidates"][0]["index"] == 1


def test_visual_route_candidates_sort_by_save_ranked_mission():
    recommendation = {
        "status": "OK",
        "ranked": [
            {
                "mission_id": "Mission_Train",
                "save_region_index": 6,
                "save_region_name": "Train Crossing",
                "score": 47,
            },
            {
                "mission_id": "Mission_Repair",
                "save_region_index": 3,
                "save_region_name": "Repair Flats",
                "score": -70,
            },
        ],
    }
    visual_regions = {
        "status": "OK",
        "regions": [
            {"index": 0, "window_x": 300, "window_y": 250},
            {"index": 1, "window_x": 800, "window_y": 520},
        ],
    }

    result = commands._lightning_route_start_candidates(
        visual_regions,
        recommendation=recommendation,
    )

    assert result[0]["index"] == 1
    assert result[0]["mission_id"] == "Mission_Train"
    assert result[0]["auto_route_allowed"] is True
    assert result[1]["index"] == 0
    assert result[1]["mission_id"] == "Mission_Repair"
    assert result[1]["auto_route_allowed"] is True


def test_visual_route_candidate_allows_single_forced_bridge_preview():
    recommendation = {
        "status": "OK",
        "source": "bridge_preview",
        "ranked": [
            {
                "mission_id": "Mission_Artillery",
                "score": -53,
            },
        ],
        "top3": [
            {
                "mission_id": "Mission_Artillery",
                "score": -53,
            },
        ],
    }
    visual_regions = {
        "status": "OK",
        "regions": [
            {"index": 0, "window_x": 873, "window_y": 497},
        ],
    }

    result = commands._lightning_route_start_candidates(
        visual_regions,
        recommendation=recommendation,
    )

    assert result[0]["mission_id"] == "Mission_Artillery"
    assert result[0]["forced_preview_route"] is True
    assert result[0]["auto_route_allowed"] is True


def test_visual_route_candidate_allows_ambiguous_forced_bridge_preview_above_floor():
    recommendation = {
        "status": "OK",
        "source": "bridge_preview",
        "ranked": [
            {
                "mission_id": "Mission_Tides",
                "score": 23,
            },
        ],
        "top3": [
            {
                "mission_id": "Mission_Tides",
                "score": 23,
            },
        ],
    }
    visual_regions = {
        "status": "OK",
        "regions": [
            {"index": 0, "window_x": 809, "window_y": 419},
            {"index": 1, "window_x": 949, "window_y": 588},
        ],
    }

    result = commands._lightning_route_start_candidates(
        visual_regions,
        recommendation=recommendation,
    )

    assert len(result) == 2
    assert all(candidate["mission_id"] == "Mission_Tides" for candidate in result)
    assert all(candidate["forced_preview_route"] is True for candidate in result)
    assert all(candidate["forced_preview_ambiguous"] is True for candidate in result)
    assert all(candidate["auto_route_allowed"] is True for candidate in result)
    assert all(
        "--route-target-mission-id" not in candidate["command"]
        for candidate in result
    )
    assert all(
        "--expected-mission-id" not in candidate["route_start_command"]
        for candidate in result
    )


def test_visual_route_candidate_allows_ambiguous_forced_bridge_preview_below_floor():
    recommendation = {
        "status": "OK",
        "source": "bridge_preview",
        "ranked": [
            {
                "mission_id": "Mission_Teleporter",
                "score": -90,
            },
        ],
        "top3": [
            {
                "mission_id": "Mission_Teleporter",
                "score": -90,
            },
        ],
    }
    visual_regions = {
        "status": "OK",
        "regions": [
            {"index": 0, "window_x": 809, "window_y": 419},
            {"index": 1, "window_x": 949, "window_y": 588},
        ],
    }

    result = commands._lightning_route_start_candidates(
        visual_regions,
        recommendation=recommendation,
    )

    assert len(result) == 2
    assert all(
        candidate.get("auto_route_allowed") is True
        for candidate in result
    )


def test_visual_route_candidate_omits_target_for_ambiguous_bridge_preview():
    recommendation = {
        "status": "OK",
        "source": "bridge_preview",
        "ranked": [
            {
                "mission_id": "Mission_Tanks",
                "score": -62,
            },
        ],
        "top3": [
            {
                "mission_id": "Mission_Tanks",
                "score": -62,
            },
        ],
    }
    visual_regions = {
        "status": "OK",
        "regions": [
            {"index": 0, "window_x": 813, "window_y": 401},
            {"index": 1, "window_x": 949, "window_y": 588},
        ],
    }
    target_hint = commands._lightning_route_target_hint_from_recommendation(
        recommendation,
    )

    result = commands._lightning_route_start_candidates(
        visual_regions,
        target_hint=target_hint,
        recommendation=recommendation,
    )

    assert len(result) == 2
    assert all(
        "--route-target-mission-id" not in candidate["command"]
        for candidate in result
    )
    assert all(
        "--expected-mission-id" not in candidate["route_start_command"]
        for candidate in result
    )


def test_recommend_mission_uses_save_filter_for_live_bridge(monkeypatch):
    save_text = """
    ["region0"] = {
        ["mission"] = "",
        ["state"] = 2,
        ["name"] = "Storage Vaults",
        ["objectives"] = {
            ["0"] = {["text"] = "Mission_ArmoredTrain_Obj", ["param1"] = "",},
        },
    },
    ["region5"] = {
        ["mission"] = "",
        ["state"] = 3,
        ["name"] = "Archivist Hall",
        ["objectives"] = {
            ["0"] = {["text"] = "Bonus_Simple_Grid", ["param1"] = "",},
            ["1"] = {["text"] = "Bonus_Simple_Asset", ["param1"] = "Str_Power_Name",},
        },
    },
    ["region4"] = {
        ["mission"] = "",
        ["state"] = 0,
        ["name"] = "Accord Repository",
        ["objectives"] = {
            ["0"] = {["text"] = "Mission_Satellite_Obj", ["param1"] = "",},
        },
    },
    """
    island_map = [
        {
            "region_id": 0,
            "mission_id": "Mission_Armored_Train",
            "bonus_objective_ids": [],
            "environment": "Env_Null",
        },
        {
            "region_id": 5,
            "mission_id": "Mission_Survive",
            "bonus_objective_ids": [3, 1],
            "asset_id": "Str_Power",
            "environment": "Env_Null",
        },
        {
            "region_id": 4,
            "mission_id": "Mission_Satellite",
            "bonus_objective_ids": [],
            "environment": "Env_Null",
        },
    ]
    bridge_data = {
        "island_map": island_map,
        "units": [
            {"mech": True, "hp": 3, "weapons": ["Prime_Lightning"]},
        ],
        "grid_power": 6,
        "phase": "unknown",
    }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: (None, bridge_data))
    monkeypatch.setattr(
        commands,
        "_lightning_read_save_region_entries",
        lambda profile: commands._lightning_parse_save_region_entries(save_text),
    )

    result = commands.cmd_recommend_mission(routing="lightning_war")

    assert result["status"] == "OK"
    assert result["save_region_filter"]["unavailable"] == 2
    assert [m["mission_id"] for m in result["ranked"]] == ["Mission_Satellite"]


def test_recommend_mission_can_peek_map_from_pause(monkeypatch):
    initial_bridge_data = {
        "island_map": None,
        "units": [
            {"mech": True, "hp": 3, "weapons": ["Prime_Lightning"]},
        ],
        "grid_power": 7,
        "phase": "unknown",
    }
    peek_bridge_data = {
        "island_map": [
            {
                "region_id": 9,
                "mission_id": "Mission_Sandstorm",
                "bonus_objective_ids": [],
                "environment": "Env_Sandstorm",
            },
        ],
        "units": initial_bridge_data["units"],
        "grid_power": 7,
        "phase": "unknown",
    }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: (None, initial_bridge_data))
    monkeypatch.setattr(
        commands,
        "_lightning_bridge_island_map_pause_peek",
        lambda: {
            "status": "OK",
            "reason": "pause_map_peek",
            "island_map_count": 1,
            "steps": [],
            "bridge_data": peek_bridge_data,
        },
    )
    monkeypatch.setattr(commands, "_lightning_read_save_region_entries", lambda profile: [])

    result = commands.cmd_recommend_mission(
        routing="lightning_war",
        pause_map_peek=True,
    )

    assert result["status"] == "OK"
    assert result["pause_map_peek"]["island_map_count"] == 1
    assert result["top3"][0]["mission_id"] == "Mission_Sandstorm"


def test_recommend_mission_peek_runs_when_bridge_initially_inactive(monkeypatch):
    peek_bridge_data = {
        "island_map": [
            {
                "region_id": 9,
                "mission_id": "Mission_Sandstorm",
                "bonus_objective_ids": [],
                "environment": "Env_Sandstorm",
            },
        ],
        "units": [
            {"mech": True, "hp": 3, "weapons": ["Prime_Lightning"]},
        ],
        "grid_power": 7,
        "phase": "unknown",
    }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: False)
    monkeypatch.setattr(
        commands,
        "_lightning_bridge_island_map_pause_peek",
        lambda: {
            "status": "OK",
            "reason": "pause_map_peek",
            "island_map_count": 1,
            "steps": [],
            "bridge_data": peek_bridge_data,
        },
    )
    monkeypatch.setattr(commands, "_lightning_read_save_region_entries", lambda profile: [])

    result = commands.cmd_recommend_mission(
        routing="lightning_war",
        pause_map_peek=True,
    )

    assert result["status"] == "OK"
    assert result["pause_map_peek"]["island_map_count"] == 1
    assert result["top3"][0]["mission_id"] == "Mission_Sandstorm"


def test_pause_map_peek_clears_safe_panel_before_second_read(monkeypatch):
    calls = {"reads": 0, "clears": 0, "clicks": []}
    map_bridge_data = {
        "island_map": [
            {
                "region_id": 9,
                "mission_id": "Mission_Sandstorm",
                "bonus_objective_ids": [],
                "environment": "Env_Sandstorm",
            },
        ],
        "units": [],
        "grid_power": 7,
        "phase": "unknown",
    }

    def fake_read_bridge_state():
        calls["reads"] += 1
        if calls["reads"] == 1:
            return None, {"island_map": [], "phase": "unknown"}
        return None, map_bridge_data

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr("src.control.mac_click._get_window_bounds", lambda app: {})
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(commands, "read_bridge_state", fake_read_bridge_state)
    visible_states = iter(
        [
            {"status": "OK", "visible_ui": "island_map"},
            {"status": "OK", "visible_ui": "pause_menu"},
        ]
    )
    monkeypatch.setattr(
        commands,
        "_lightning_capture_window_screenshot",
        lambda path, **kwargs: {"status": "OK", "path": str(path)},
    )
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: calls["clicks"].append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_clear_visible_panel_chain",
        lambda **kwargs: calls.update(clears=calls["clears"] + 1)
        or {"status": "OK", "reason": "panel_chain_cleared"},
    )

    result = commands._lightning_bridge_island_map_pause_peek(settle_seconds=0)

    assert result["status"] == "OK"
    assert result["island_map_count"] == 1
    assert calls["reads"] == 2
    assert calls["clears"] == 1
    assert calls["clicks"] == ["menu_continue", "pause"]
    assert result["pause_verified"] is True
    assert result["map_screenshot_path"]


def test_pause_map_peek_retries_pause_until_verified(monkeypatch):
    calls = {"clicks": []}
    visible_states = iter(
        [
            {"status": "OK", "visible_ui": "island_map"},
            {"status": "OK", "visible_ui": "island_map"},
            {"status": "OK", "visible_ui": "pause_menu"},
        ]
    )
    map_bridge_data = {
        "island_map": [
            {
                "region_id": 9,
                "mission_id": "Mission_Sandstorm",
                "bonus_objective_ids": [],
                "environment": "Env_Sandstorm",
            },
        ],
        "units": [],
        "grid_power": 7,
        "phase": "unknown",
    }

    monkeypatch.setattr("src.control.mac_click._get_window_bounds", lambda app: {})
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: (None, map_bridge_data))
    monkeypatch.setattr(
        commands,
        "_lightning_capture_window_screenshot",
        lambda path, **kwargs: {"status": "OK", "path": str(path)},
    )
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: calls["clicks"].append(control)
        or {"status": "OK", "control": control},
    )

    result = commands._lightning_bridge_island_map_pause_peek(settle_seconds=0)

    assert result["status"] == "OK"
    assert result["pause_verified"] is True
    assert calls["clicks"] == ["menu_continue", "pause", "pause"]
    assert [step["pause_verify"]["visible_ui"] for step in result["steps"][1:]] == [
        "island_map",
        "pause_menu",
    ]


def test_pause_map_peek_blocks_when_pause_never_verified(monkeypatch):
    calls = {"clicks": []}
    map_bridge_data = {
        "island_map": [
            {
                "region_id": 9,
                "mission_id": "Mission_Sandstorm",
                "bonus_objective_ids": [],
                "environment": "Env_Sandstorm",
            },
        ],
        "units": [],
        "grid_power": 7,
        "phase": "unknown",
    }

    monkeypatch.setattr("src.control.mac_click._get_window_bounds", lambda app: {})
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: (None, map_bridge_data))
    monkeypatch.setattr(
        commands,
        "_lightning_capture_window_screenshot",
        lambda path, **kwargs: {"status": "OK", "path": str(path)},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: calls["clicks"].append(control)
        or {"status": "OK", "control": control},
    )

    result = commands._lightning_bridge_island_map_pause_peek(settle_seconds=0)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "pause_not_verified_after_map_peek"
    assert result["pause_verified"] is False
    assert calls["clicks"] == ["menu_continue", "pause", "pause"]


def test_lightning_route_start_blocks_failed_preflight(monkeypatch):
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "FAIL", "failures": ["timer_hidden"]},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_route_start_sequence",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not click")
        ),
    )

    result = commands.cmd_lightning_route_start(
        region_window_x=300,
        region_window_y=400,
        dry_run=True,
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "preflight_failed_before_route_start"


def test_lightning_route_start_blocks_failed_route_check(monkeypatch):
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {"status": "NO_AVAILABLE_MISSIONS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_route_start_sequence",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not click")
        ),
    )

    result = commands.cmd_lightning_route_start(
        region_window_x=300,
        region_window_y=400,
        dry_run=True,
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "route_check_failed_before_start"


def test_lightning_route_start_auto_pauses_before_route_check(monkeypatch):
    visible_states = iter(
        [
            {"status": "OK", "visible_ui": "island_map"},
            {"status": "OK", "visible_ui": "pause_menu"},
        ]
    )

    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "top3": [
                {
                    "mission_id": "Mission_Train",
                    "region_id": 5,
                    "save_region_name": "The Pasture",
                }
            ],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visual_regions_from_recommendation",
        lambda recommendation: {
            "status": "OK",
            "regions": [{"index": 0, "window_x": 902, "window_y": 349}],
        },
    )

    result = commands.cmd_lightning_route_start()

    assert result["status"] == "ROUTE_READY"
    assert result["auto_pause"]["reason"] == "pause_clicked"
    assert result["route_target_hint"]["match_label"] == "The Pasture"
    assert result["visual_regions"]["regions"][0]["window_x"] == 902
    assert (
        result["route_start_candidates"][0]["target_hint"]["save_region_name"]
        == "The Pasture"
    )
    assert result["route_start_candidates"][0]["command"].endswith(
        "--route-visual-region-index 0 "
        "--route-target-mission-id Mission_Train "
        "--route-start-mode dialogue-region-repeat-preview-board"
    )
    assert result["primary_next_command"].endswith(
        "--route-visual-region-index 0 "
        "--route-target-mission-id Mission_Train "
        "--route-start-mode dialogue-region-repeat-preview-board"
    )
    assert result["primary_route_target_hint"]["match_label"] == "The Pasture"
    assert result["route_start_candidates"][0]["route_start_command"].endswith(
        "--visual-region-index 0 "
        "--expected-mission-id Mission_Train "
        "--start-mode dialogue-region-repeat-preview-board"
    )
    assert result["route_start_candidates"][0]["coordinate_command"].endswith(
        "--window-x 902 --window-y 349 "
        "--expected-mission-id Mission_Train "
        "--start-mode dialogue-region-repeat-preview-board"
    )


def test_lightning_route_start_returns_visual_regions_when_route_check_unavailable(monkeypatch):
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "NO_BRIDGE",
            "pause_map_peek": {
                "panel_clear": {
                    "visible_ui": {"screenshot_path": "/tmp/map.png"},
                },
            },
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_extract_red_regions_from_image",
        lambda path: {
            "status": "OK",
            "screenshot_path": path,
            "region_count": 1,
            "regions": [{"index": 0, "window_x": 420, "window_y": 210}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_route_start_sequence",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not click")
        ),
    )

    result = commands.cmd_lightning_route_start()

    assert result["status"] == "ROUTE_READY_VISUAL"
    assert result["visual_regions"]["regions"][0]["window_x"] == 420
    assert result["route_start_candidates"][0]["command"].endswith(
        "--route-visual-region-index 0 --route-start-mode dialogue-region-repeat-preview-board"
    )
    assert result["primary_next_command"].endswith(
        "--route-visual-region-index 0 --route-start-mode dialogue-region-repeat-preview-board"
    )
    assert result["route_start_candidates"][0]["route_start_command"].endswith(
        "--visual-region-index 0 --start-mode dialogue-region-repeat-preview-board"
    )
    assert result["route_start_candidates"][0]["coordinate_command"].endswith(
        "--window-x 420 --window-y 210 --start-mode dialogue-region-repeat-preview-board"
    )


def test_lightning_route_start_visual_index_can_use_unavailable_route_check(monkeypatch):
    calls = []
    pauses = []

    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "NO_BRIDGE",
            "pause_map_peek": {
                "map_screenshot_path": "/tmp/map.png",
            },
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_extract_red_regions_from_image",
        lambda path: {
            "status": "OK",
            "screenshot_path": path,
            "regions": [{"index": 0, "window_x": 420, "window_y": 210}],
        },
    )

    def fake_execute(sequence, **kwargs):
        calls.append(sequence)
        return {"status": "OK", "steps": []}

    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        fake_execute,
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: pauses.append(kwargs)
        or {"status": "OK", "reason": "pause_clicked"},
    )

    result = commands.cmd_lightning_route_start(visual_region_index=0)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "route_preview_mission_unverified_before_start"
    assert result["recommendation"]["status"] == "NO_BRIDGE"
    assert result["selected_visual_region"]["window_x"] == 420
    assert result["pause_after_block"]["status"] == "OK"
    assert len(calls) == 1
    assert not any(
        step.get("control") == "mission_preview_board"
        for step in calls[0]
        if isinstance(step, dict)
    )
    assert pauses == [{"reason": "route_preview_unverified_before_start"}]


def test_lightning_route_start_visual_index_accepts_exact_bridge_match(monkeypatch):
    calls = []
    starts = []
    pauses = []

    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "bridge",
            "pause_map_peek": {"map_screenshot_path": "/tmp/map.png"},
            "top3": [
                {
                    "mission_id": "Mission_Armored_Train",
                    "region_id": 6,
                    "score": 35,
                }
            ],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_extract_red_regions_from_image",
        lambda path: {
            "status": "OK",
            "screenshot_path": path,
            "regions": [{"index": 0, "window_x": 809, "window_y": 420}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_route_start_sequence_parts",
        lambda *args, **kwargs: {
            "status": "OK",
            "preview_sequence": [
                {
                    "kind": "point",
                    "window_x": 809,
                    "window_y": 420,
                    "description": "Lightning route region",
                }
            ],
            "commit_sequence": [
                {
                    "kind": "control",
                    "control": "mission_preview_board",
                }
            ],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        lambda sequence, **kwargs: calls.append(sequence) or {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_visible_start_mission",
        lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "visible_start_clicked"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "in_active_mission": True,
            "mission_id": "Mission_Armored_Train",
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: pauses.append(kwargs) or {"status": "OK"},
    )

    result = commands.cmd_lightning_route_start(visual_region_index=0)

    assert result["status"] == "OK"
    assert result["reason"] == "route_preview_validated_start_clicked"
    assert result["expected_route_mission_id"] == "Mission_Armored_Train"
    assert result["click_result"]["actual_preview_mission_id"] == "Mission_Armored_Train"
    assert starts
    assert calls == [
        [
            {
                "kind": "point",
                "window_x": 809,
                "window_y": 420,
                "description": "Lightning route region",
            }
        ]
    ]
    assert pauses == []


def test_lightning_route_start_raw_coordinates_can_force_unverified_preview(
    monkeypatch,
):
    calls = []
    starts = []
    pauses = []

    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_route_start_sequence_parts",
        lambda *args, **kwargs: {
            "status": "OK",
            "preview_sequence": [
                {
                    "kind": "point",
                    "window_x": 690,
                    "window_y": 350,
                    "description": "Lightning route region",
                }
            ],
            "commit_sequence": [
                {
                    "kind": "control",
                    "control": "mission_preview_board",
                }
            ],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        lambda sequence, **kwargs: calls.append(sequence) or {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "NO_ISLAND_MAP",
            "source": "bridge",
            "top3": [],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_visible_start_mission",
        lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "visible_start_clicked"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "in_active_mission": True,
            "mission_id": "Mission_Artillery",
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: pauses.append(kwargs) or {"status": "OK"},
    )

    result = commands.cmd_lightning_route_start(
        region_window_x=690,
        region_window_y=350,
        run_preflight=False,
        verify_route=False,
    )

    assert result["status"] == "OK"
    assert result["reason"] == "route_preview_validated_start_clicked"
    assert result["expected_route_mission_id"] is None
    assert result["click_result"]["actual_preview_mission_id"] is None
    assert starts
    assert calls == [
        [
            {
                "kind": "point",
                "window_x": 690,
                "window_y": 350,
                "description": "Lightning route region",
            }
        ]
    ]
    assert pauses == []


def test_lightning_route_start_policy_can_force_unverified_visual_preview(
    monkeypatch,
):
    calls = []
    starts = []
    pauses = []

    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_route_start_sequence_parts",
        lambda *args, **kwargs: {
            "status": "OK",
            "preview_sequence": [
                {
                    "kind": "point",
                    "window_x": 812,
                    "window_y": 423,
                    "description": "Lightning route region",
                }
            ],
            "commit_sequence": [
                {
                    "kind": "control",
                    "control": "mission_preview_board",
                }
            ],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        lambda sequence, **kwargs: calls.append(sequence) or {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visual_regions_from_recommendation",
        lambda recommendation: {
            "status": "OK",
            "regions": [{"index": 0, "window_x": 812, "window_y": 423}],
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "NO_ISLAND_MAP",
            "source": "bridge",
            "top3": [],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_visible_start_mission",
        lambda **kwargs: starts.append(kwargs)
        or {"status": "OK", "reason": "visible_start_clicked"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "in_active_mission": True,
            "mission_id": "Mission_Unknown",
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: pauses.append(kwargs) or {"status": "OK"},
    )

    result = commands.cmd_lightning_route_start(
        visual_region_index=0,
        run_preflight=False,
        allow_unverified_preview_start=True,
    )

    assert result["status"] == "OK"
    assert result["reason"] == "route_preview_validated_start_clicked"
    assert result["expected_route_mission_id"] is None
    assert starts
    assert calls == [
        [
            {
                "kind": "point",
                "window_x": 812,
                "window_y": 423,
                "description": "Lightning route region",
            }
        ]
    ]
    assert pauses == []


def test_lightning_visual_regions_prefer_map_peek_screenshot(monkeypatch):
    seen_paths = []

    monkeypatch.setattr(
        commands,
        "_lightning_extract_red_regions_from_image",
        lambda path: seen_paths.append(path)
        or {
            "status": "OK",
            "screenshot_path": path,
            "region_count": 1,
            "regions": [{"index": 0, "window_x": 420, "window_y": 210}],
        },
    )

    result = commands._lightning_visual_regions_from_recommendation(
        {
            "pause_map_peek": {
                "map_screenshot_path": "/tmp/live-map.png",
                "panel_clear": {
                    "visible_ui": {"screenshot_path": "/tmp/panel-clear.png"},
                },
            },
        }
    )

    assert result["screenshot_path"] == "/tmp/live-map.png"
    assert seen_paths == ["/tmp/live-map.png"]


def test_lightning_route_start_candidates_from_visual_regions():
    result = commands._lightning_route_start_candidates(
        {
            "status": "OK",
            "regions": [
                {"index": 2, "window_x": 743, "window_y": 316},
                {"index": 3, "window_x": 902, "window_y": 349},
            ],
        },
        start_mode="dialogue-region-repeat-preview-board-twice",
    )

    assert result == [
        {
            "index": 2,
            "window_x": 743,
            "window_y": 316,
            "command": (
                "python3 game_loop.py lightning_segment "
                "--route-visual-region-index 2 "
                "--route-start-mode dialogue-region-repeat-preview-board-twice"
            ),
            "route_start_command": (
                "python3 game_loop.py lightning_route_start "
                "--visual-region-index 2 "
                "--start-mode dialogue-region-repeat-preview-board-twice"
            ),
            "coordinate_command": (
                "python3 game_loop.py lightning_route_start --no-route-check "
                "--window-x 743 --window-y 316 "
                "--start-mode dialogue-region-repeat-preview-board-twice"
            ),
        },
        {
            "index": 3,
            "window_x": 902,
            "window_y": 349,
            "command": (
                "python3 game_loop.py lightning_segment "
                "--route-visual-region-index 3 "
                "--route-start-mode dialogue-region-repeat-preview-board-twice"
            ),
            "route_start_command": (
                "python3 game_loop.py lightning_route_start "
                "--visual-region-index 3 "
                "--start-mode dialogue-region-repeat-preview-board-twice"
            ),
            "coordinate_command": (
                "python3 game_loop.py lightning_route_start --no-route-check "
                "--window-x 902 --window-y 349 "
                "--start-mode dialogue-region-repeat-preview-board-twice"
            ),
        },
    ]


def test_lightning_route_candidates_include_recommendation_target_hint():
    target_hint = commands._lightning_route_target_hint_from_recommendation(
        {
            "top3": [
                {
                    "mission_id": "Mission_Armored_Train",
                    "region_id": 5,
                    "save_region_name": "The Pasture",
                    "save_region_index": 5,
                    "environment": "Env_Null",
                    "score": 31,
                }
            ]
        }
    )
    result = commands._lightning_route_start_candidates(
        {
            "status": "OK",
            "regions": [{"index": 0, "window_x": 935, "window_y": 430}],
        },
        target_hint=target_hint,
    )

    assert target_hint == {
        "mission_id": "Mission_Armored_Train",
        "region_id": 5,
        "save_region_name": "The Pasture",
        "save_region_index": 5,
        "environment": "Env_Null",
        "score": 31,
        "match_label": "The Pasture",
    }
    assert result[0]["target_hint"]["match_label"] == "The Pasture"
    assert result[0]["target_hint"]["mission_id"] == "Mission_Armored_Train"


def test_lightning_route_start_preview_only_sequence_repauses():
    result = commands._lightning_click_route_start_sequence(
        543,
        585,
        dry_run=True,
        include_start_click=False,
    )

    assert result["status"] == "DRY_RUN"
    expected_keys = [] if os.name == "nt" else ["esc"]
    expected_controls = (
        ["menu_continue", "pause"] if os.name == "nt" else ["pause"]
    )
    assert [step["key"] for step in result["sequence"] if step["kind"] == "key"] == expected_keys
    assert [step["control"] for step in result["sequence"] if step["kind"] == "control"] == expected_controls


def test_lightning_route_start_dismiss_dialogue_sequence():
    result = commands._lightning_click_route_start_sequence(
        541,
        244,
        dry_run=True,
        dismiss_dialogue=True,
        start_mode="preview-board",
    )

    assert result["status"] == "DRY_RUN"
    controls = [
        step.get("control") for step in result["sequence"]
        if step["kind"] == "control"
    ]
    expected_controls = (
        ["menu_continue"] if os.name == "nt" else []
    ) + ["dialogue_textbox", "mission_preview_board"]
    assert controls == expected_controls


def test_lightning_route_start_visible_text_sequence():
    result = commands._lightning_click_route_start_sequence(
        541,
        244,
        dry_run=True,
        dismiss_dialogue=True,
        start_mode="visible-text",
    )

    assert result["status"] == "DRY_RUN"
    start_steps = [
        step for step in result["sequence"]
        if step["kind"] == "start_visible"
    ]
    assert start_steps == [{"kind": "start_visible", "dismiss_dialogue": True}]


def test_lightning_route_start_preview_board_twice_sequence():
    result = commands._lightning_click_route_start_sequence(
        541,
        244,
        dry_run=True,
        dismiss_dialogue=True,
        start_mode="preview-board-twice",
    )

    assert result["status"] == "DRY_RUN"
    controls = [
        step.get("control") for step in result["sequence"]
        if step["kind"] == "control"
    ]
    expected_controls = (
        ["menu_continue"] if os.name == "nt" else []
    ) + [
        "dialogue_textbox",
        "mission_preview_board",
        "mission_preview_board",
    ]
    assert controls == expected_controls


def test_lightning_paused_preview_start_sequence():
    result = commands._lightning_click_paused_preview_start_sequence(
        dry_run=True,
        start_clicks=2,
    )

    assert result["status"] == "DRY_RUN"
    assert [step.get("key") for step in result["sequence"] if step["kind"] == "key"] == [
        "esc",
    ]
    assert [
        step.get("control") for step in result["sequence"] if step["kind"] == "control"
    ] == ["mission_preview_board", "mission_preview_board"]


def test_lightning_paused_preview_dialogue_start_sequence():
    result = commands._lightning_click_paused_preview_start_sequence(
        dry_run=True,
        dismiss_dialogue=True,
        start_clicks=2,
    )

    assert result["status"] == "DRY_RUN"
    assert [
        step.get("control") for step in result["sequence"] if step["kind"] == "control"
    ] == ["dialogue_textbox", "mission_preview_board", "mission_preview_board"]


def test_lightning_route_start_region_repeat_sequence():
    result = commands._lightning_click_route_start_sequence(
        541,
        244,
        dry_run=True,
        start_mode="region-repeat",
    )

    assert result["status"] == "DRY_RUN"
    points = [
        step for step in result["sequence"]
        if step["kind"] == "point"
    ]
    assert [point["description"] for point in points] == [
        "Lightning route region",
        "Lightning route repeat region start",
    ]


def test_lightning_route_start_dialogue_region_repeat_sequence():
    result = commands._lightning_click_route_start_sequence(
        541,
        244,
        dry_run=True,
        start_mode="dialogue-region-repeat-preview-board-twice",
    )

    assert result["status"] == "DRY_RUN"
    kinds = [step["kind"] for step in result["sequence"]]
    expected_kinds = [
        "control" if os.name == "nt" else "key",
        "point",
        "dialogue_then_region_repeat",
        "control",
        "control",
    ]
    assert kinds == expected_kinds
    if os.name == "nt":
        assert result["sequence"][0]["hold_seconds"] == 0.30
    dialogue_step = result["sequence"][2]
    assert dialogue_step["window_x"] == 541
    assert dialogue_step["window_y"] == 244
    assert dialogue_step["hold_seconds"] == 0.30
    assert [
        step.get("control") for step in result["sequence"] if step["kind"] == "control"
    ] == ((["menu_continue"] if os.name == "nt" else []) + [
        "mission_preview_board",
        "mission_preview_board",
    ])


def test_lightning_dialogue_region_repeat_skips_when_no_dialogue(monkeypatch):
    clicks = []
    bounds = {"x": 100, "y": 50, "width": 1280, "height": 748}

    monkeypatch.setattr(
        "src.capture.window.take_screenshot",
        lambda path: None,
    )
    monkeypatch.setattr(
        commands,
        "_lightning_dialogue_box_score",
        lambda path: {"status": "OK", "visible": False},
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_screen_point",
        lambda *args, **kwargs: clicks.append((args, kwargs)) or {"status": "OK"},
    )

    result = commands._lightning_click_dialogue_then_region_repeat(
        bounds=bounds,
        region_window_x=541,
        region_window_y=244,
    )

    assert result["status"] == "OK"
    assert result["reason"] == "dialogue_not_visible_region_repeat_skipped"
    assert clicks == []


def test_lightning_dialogue_region_repeat_reopens_region(monkeypatch):
    dialogue_clicks = []
    region_clicks = []
    bounds = {"x": 100, "y": 50, "width": 1280, "height": 748}

    monkeypatch.setattr(
        "src.capture.window.take_screenshot",
        lambda path: None,
    )
    monkeypatch.setattr(
        commands,
        "_lightning_dialogue_box_score",
        lambda path: {"status": "OK", "visible": True},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: dialogue_clicks.append((control, kwargs))
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_screen_point",
        lambda x, y, **kwargs: region_clicks.append((x, y, kwargs))
        or {"status": "OK"},
    )

    result = commands._lightning_click_dialogue_then_region_repeat(
        bounds=bounds,
        region_window_x=541,
        region_window_y=244,
    )

    assert result["status"] == "OK"
    assert result["reason"] == "dialogue_dismissed_region_repeated"
    assert result["dialogue_click"]["control"] == "dialogue_textbox"
    assert dialogue_clicks[0][1]["hold_seconds"] == 0.30
    assert dialogue_clicks[0][1]["settle_seconds"] >= 0.30
    assert result["second_dialogue_click"]["control"] == "dialogue_textbox"
    assert dialogue_clicks[1][1]["hold_seconds"] == 0.30
    assert region_clicks[0][0:2] == (641, 294)
    assert region_clicks[0][2]["hold_seconds"] == 0.30
    assert result["region_repeat_click"]["window_x"] == 541
    assert result["region_repeat_click"]["window_y"] == 244


def test_lightning_route_start_manual_start_sequence():
    result = commands._lightning_click_route_start_sequence(
        541,
        244,
        dry_run=True,
        dismiss_dialogue=True,
        start_window_x=870,
        start_window_y=300,
    )

    assert result["status"] == "DRY_RUN"
    controls = [
        step.get("control") for step in result["sequence"]
        if step["kind"] == "control"
    ]
    points = [
        step for step in result["sequence"]
        if step["kind"] == "point"
    ]
    expected_controls = (
        ["menu_continue"] if os.name == "nt" else []
    ) + ["dialogue_textbox"]
    assert controls == expected_controls
    assert points[-1]["description"] == "Lightning route manual start"
    assert points[-1]["window_x"] == 870
    assert points[-1]["window_y"] == 300


def test_lightning_route_start_dry_run_plans_click_sequence(monkeypatch):
    calls = []

    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Train"}],
        },
    )

    def fake_sequence(x, y, **kwargs):
        calls.append((x, y, kwargs))
        return {"status": "DRY_RUN", "planned": [{"window_x": x, "window_y": y}]}

    monkeypatch.setattr(commands, "_lightning_click_route_start_sequence", fake_sequence)

    result = commands.cmd_lightning_route_start(
        region_window_x=311,
        region_window_y=477,
        dry_run=True,
    )

    assert result["status"] == "DRY_RUN"
    assert result["reason"] == "dry_run_route_start_sequence"
    assert calls == [
        (
            311,
            477,
                {
                    "dry_run": True,
                    "include_start_click": True,
                    "dismiss_dialogue": False,
                    "start_mode": "dialogue-region-repeat-preview-board",
                    "start_window_x": None,
                    "start_window_y": None,
                    "resume_from_pause": True,
                },
            )
        ]


def test_lightning_route_start_uses_visual_region_index(monkeypatch):
    calls = []

    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Train"}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visual_regions_from_recommendation",
        lambda recommendation: {
            "status": "OK",
            "regions": [
                {"index": 2, "window_x": 311, "window_y": 477},
                {"index": 3, "window_x": 902, "window_y": 349},
            ],
        },
    )

    def fake_sequence(x, y, **kwargs):
        calls.append((x, y, kwargs))
        return {"status": "DRY_RUN", "planned": [{"window_x": x, "window_y": y}]}

    monkeypatch.setattr(commands, "_lightning_click_route_start_sequence", fake_sequence)

    result = commands.cmd_lightning_route_start(
        visual_region_index=3,
        dry_run=True,
    )

    assert result["status"] == "DRY_RUN"
    assert result["selected_visual_region"] == {
        "index": 3,
        "window_x": 902,
        "window_y": 349,
    }
    assert result["inferred_expected_route_mission_id"] is None
    assert calls[0][0:2] == (902, 349)


def test_lightning_route_start_blocks_preview_mismatch_before_commit(monkeypatch):
    calls = []

    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )

    def fake_execute(sequence, **kwargs):
        calls.append(sequence)
        return {"status": "OK", "steps": [{"count": len(sequence)}]}

    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        fake_execute,
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Trapped"}],
        },
    )

    result = commands.cmd_lightning_route_start(
        region_window_x=542,
        region_window_y=244,
        run_preflight=False,
        verify_route=False,
        expected_route_mission_id="Mission_Bomb",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "route_preview_mission_mismatch_before_start"
    assert result["expected_route_mission_id"] == "Mission_Bomb"
    assert result["actual_preview_mission_id"] == "Mission_Trapped"
    assert len(calls) == 1
    assert not any(
        step.get("control") == "mission_preview_board"
        for step in calls[0]
        if isinstance(step, dict)
    )


def test_lightning_route_start_accepts_explicit_save_backed_preview_match(
    monkeypatch,
):
    calls = []
    visible_start_calls = []

    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )

    def fake_execute(sequence, **kwargs):
        calls.append(sequence)
        return {"status": "OK", "steps": [{"count": len(sequence)}]}

    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        fake_execute,
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "saveData",
            "top3": [{"mission_id": "Mission_Mines"}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_visible_start_mission",
        lambda **kwargs: visible_start_calls.append(kwargs)
        or {
            "status": "OK",
            "target": {"window_x": 848, "window_y": 448},
            "click_result": {"status": "OK"},
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {"status": "NO_BRIDGE"},
    )

    result = commands.cmd_lightning_route_start(
        region_window_x=697,
        region_window_y=354,
        run_preflight=False,
        verify_route=False,
        expected_route_mission_id="Mission_Mines",
    )

    assert result["status"] == "OK"
    assert result["reason"] == "route_preview_validated_start_clicked"
    click_result = result["click_result"]
    assert click_result["expected_route_mission_id"] == "Mission_Mines"
    assert click_result["actual_preview_mission_id"] == "Mission_Mines"
    assert len(calls) == 1
    assert visible_start_calls == [{"dry_run": False, "dismiss_dialogue": False}]


def test_lightning_route_start_accepts_live_boss_preview_over_stale_expected(
    monkeypatch,
):
    calls = []
    visible_start_calls = []

    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )

    def fake_execute(sequence, **kwargs):
        calls.append(sequence)
        return {"status": "OK", "steps": [{"count": len(sequence)}]}

    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        fake_execute,
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_DungBoss", "boss": True}],
            "speed_route_status": {"reason": "forced_boss_route"},
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_visible_start_mission",
        lambda **kwargs: visible_start_calls.append(kwargs)
        or {
            "status": "OK",
            "target": {"window_x": 848, "window_y": 448},
            "click_result": {"status": "OK"},
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {"status": "NO_BRIDGE"},
    )

    result = commands.cmd_lightning_route_start(
        region_window_x=544,
        region_window_y=579,
        run_preflight=False,
        verify_route=False,
        expected_route_mission_id="Mission_Wind",
    )

    assert result["status"] == "OK"
    assert result["reason"] == "route_preview_validated_start_clicked"
    click_result = result["click_result"]
    assert click_result["expected_route_mission_id"] == "Mission_DungBoss"
    assert click_result["actual_preview_mission_id"] == "Mission_DungBoss"
    assert click_result["stale_route_target_override"] == {
        "expected_route_mission_id": "Mission_Wind",
        "actual_preview_mission_id": "Mission_DungBoss",
        "reason": "live_bridge_boss_preview_overrode_stale_route_target",
    }
    assert len(calls) == 1
    assert visible_start_calls == [{"dry_run": False, "dismiss_dialogue": False}]


def test_lightning_route_start_commits_preview_without_expected_target(
    monkeypatch,
):
    calls = []
    visible_start_calls = []

    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )

    def fake_execute(sequence, **kwargs):
        calls.append(sequence)
        return {"status": "OK", "steps": [{"count": len(sequence)}]}

    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        fake_execute,
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Dam"}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_visible_start_mission",
        lambda **kwargs: visible_start_calls.append(kwargs)
        or {
            "status": "OK",
            "target": {"window_x": 848, "window_y": 448},
            "click_result": {"status": "OK"},
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {"status": "NO_BRIDGE"},
    )

    result = commands.cmd_lightning_route_start(
        region_window_x=542,
        region_window_y=244,
        run_preflight=False,
        verify_route=False,
    )

    assert result["status"] == "OK"
    assert result["reason"] == "route_preview_validated_start_clicked"
    assert result["click_result"]["actual_preview_mission_id"] == "Mission_Dam"
    assert len(calls) == 1
    assert visible_start_calls == [{"dry_run": False, "dismiss_dialogue": False}]


def test_lightning_route_start_commits_matching_preview(monkeypatch):
    calls = []
    visible_start_calls = []
    dialogue_dismiss_calls = []

    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )

    def fake_execute(sequence, **kwargs):
        calls.append(sequence)
        return {"status": "OK", "steps": [{"count": len(sequence)}]}

    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        fake_execute,
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Bomb"}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_dismiss_visible_dialogue",
        lambda **kwargs: dialogue_dismiss_calls.append(kwargs)
        or {"status": "NO_ACTION", "reason": "dialogue_not_visible"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_visible_start_mission",
        lambda **kwargs: visible_start_calls.append(kwargs)
        or {
            "status": "OK",
            "target": {"window_x": 848, "window_y": 448},
            "click_result": {"status": "OK"},
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {"status": "NO_BRIDGE"},
    )

    result = commands.cmd_lightning_route_start(
        region_window_x=542,
        region_window_y=244,
        run_preflight=False,
        verify_route=False,
        expected_route_mission_id="Mission_Bomb",
    )

    assert result["status"] == "OK"
    assert result["reason"] == "route_preview_validated_start_clicked"
    assert result["click_result"]["actual_preview_mission_id"] == "Mission_Bomb"
    assert len(calls) == 1
    assert dialogue_dismiss_calls == []
    assert visible_start_calls == [{"dry_run": False, "dismiss_dialogue": False}]


def test_lightning_route_start_continues_playable_post_start_mismatch(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )

    def fake_execute(sequence, **kwargs):
        calls.append(sequence)
        return {"status": "OK", "steps": [{"count": len(sequence)}]}

    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        fake_execute,
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Belt"}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_visible_start_mission",
        lambda **kwargs: {
            "status": "OK",
            "target": {"window_x": 848, "window_y": 448},
            "click_result": {"status": "OK"},
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "mission_id": "Mission_Missiles",
            "deployment_zone_count": 10,
            "mech_count": 0,
            "in_active_mission": True,
            "grid_power": "6/7",
        },
    )

    monkeypatch.setattr(
        commands,
        "_lightning_write_route_mismatch_block",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("playable mismatch should not write a block")
        ),
    )
    monkeypatch.setattr(
        commands,
        "_lightning_recover_started_route_mismatch",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("playable mismatch should not abandon the timeline")
        ),
    )

    result = commands.cmd_lightning_route_start(
        region_window_x=542,
        region_window_y=244,
        run_preflight=False,
        verify_route=False,
        expected_route_mission_id="Mission_Belt",
    )

    assert result["status"] == "OK"
    assert result["reason"] == "route_mission_mismatch_after_start_playable"
    click_result = result["click_result"]
    assert click_result["post_start_snapshot"]["mission_id"] == "Mission_Missiles"
    assert click_result["actual_started_mission_id"] == "Mission_Missiles"
    assert click_result["route_mismatch_warning"] == {
        "expected_mission_id": "Mission_Belt",
        "actual_mission_id": "Mission_Missiles",
        "policy": "continue_loaded_playable_mission",
    }
    assert len(calls) == 1


def test_lightning_route_start_continues_former_veto_post_start_mismatch(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []
    blocks = []
    recoveries = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )

    def fake_execute(sequence, **kwargs):
        calls.append(sequence)
        return {"status": "OK", "steps": [{"count": len(sequence)}]}

    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        fake_execute,
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Tides"}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_visible_start_mission",
        lambda **kwargs: {
            "status": "OK",
            "target": {"window_x": 848, "window_y": 448},
            "click_result": {"status": "OK"},
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "mission_id": "Mission_ForestFire",
            "deployment_zone_count": 10,
            "mech_count": 0,
            "in_active_mission": True,
            "grid_power": "6/7",
        },
    )

    def fake_write_block(session_arg, **kwargs):
        blocks.append((session_arg, kwargs))
        return {"status": "BLOCKED", **kwargs}

    def fake_recovery(session_arg, **kwargs):
        recoveries.append((session_arg, kwargs))
        return {"status": "OK", "reason": "route_mismatch_abandoned_to_safe_state"}

    monkeypatch.setattr(commands, "_lightning_write_route_mismatch_block", fake_write_block)
    monkeypatch.setattr(
        commands,
        "_lightning_recover_started_route_mismatch",
        fake_recovery,
    )

    result = commands.cmd_lightning_route_start(
        region_window_x=542,
        region_window_y=244,
        run_preflight=False,
        verify_route=False,
        expected_route_mission_id="Mission_Tides",
    )

    assert result["status"] == "OK"
    assert result["reason"] == "route_mission_mismatch_after_start_playable"
    click_result = result["click_result"]
    assert click_result["post_start_snapshot"]["mission_id"] == "Mission_ForestFire"
    assert click_result["route_mismatch_warning"] == {
        "expected_mission_id": "Mission_Tides",
        "actual_mission_id": "Mission_ForestFire",
        "policy": "continue_loaded_playable_mission",
    }
    assert not blocks
    assert not recoveries
    assert len(calls) == 1


def test_lightning_route_mismatch_recovery_retries_sticky_deploy_confirm(
    monkeypatch,
):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    clicks = []
    pauses = iter(
        [
            {
                "status": "BLOCKED",
                "reason": "visible_ui_is_not_pauseable",
                "visible_ui": {
                    "visible_ui": "deployment_screen",
                    "recommended_control": "deploy_confirm",
                    "non_pauseable": True,
                },
            },
            {
                "status": "OK",
                "reason": "pause_clicked",
                "pause_verify": {"visible_ui": "pause_menu"},
            },
        ]
    )

    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        commands,
        "cmd_deploy_recommended",
        lambda **kwargs: {"status": "OK", "deployments": [1, 2, 3]},
    )
    monkeypatch.setattr(commands, "_lightning_ensure_pause_state", lambda **kwargs: next(pauses))
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "new_game_setup"},
    )

    def fake_click(control):
        clicks.append(control)
        return {"status": "OK", "control": control}

    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        fake_click,
    )

    result = commands._lightning_recover_started_route_mismatch(
        session,
        profile="default",
        expected_mission_id="Mission_Train",
        actual_mission_id="Mission_Solar",
        snapshot={
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "mission_id": "Mission_Solar",
            "deployment_zone_count": 12,
        },
    )

    assert result["status"] == "OK"
    assert result["reason"] == "route_mismatch_abandoned_to_safe_state"
    assert clicks == [
        "deploy_confirm",
        "deploy_confirm",
        "abandon_timeline",
        "abandon_confirm_yes",
        "abandon_pilot_slot",
    ]
    assert result["deploy_confirm_retries"][0]["control"] == "deploy_confirm"
    assert len(result["pause_attempts"]) == 2


def test_lightning_route_start_clicks_verified_board_before_dialogue_dismiss(
    monkeypatch,
):
    calls = []
    visible_start_calls = []

    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )

    def fake_execute(sequence, **kwargs):
        calls.append(sequence)
        return {"status": "OK", "steps": [{"count": len(sequence)}]}

    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        fake_execute,
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_SnowStorm"}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_dismiss_visible_dialogue",
        lambda **kwargs: pytest.fail("dialogue should remain open"),
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_visible_start_mission",
        lambda **kwargs: visible_start_calls.append(kwargs)
        or {"status": "NOT_FOUND", "reason": "start_mission_text_not_found"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {"status": "NO_BRIDGE"},
    )

    result = commands.cmd_lightning_route_start(
        region_window_x=600,
        region_window_y=360,
        run_preflight=False,
        verify_route=False,
        expected_route_mission_id="Mission_SnowStorm",
        start_mode="preview-board",
    )

    assert result["status"] == "OK"
    commit = result["click_result"]["commit_click"]
    assert commit["reason"] == "verified_preview_board_clicked_before_dialogue"
    assert len(calls) == 2
    assert any(
        step.get("control") == "mission_preview_board"
        for step in calls[1]
        if isinstance(step, dict)
    )
    assert visible_start_calls == [{"dry_run": False, "dismiss_dialogue": False}]


def test_lightning_route_start_reopens_region_after_sticky_dialogue(monkeypatch):
    calls = []
    visible_start_calls = []
    dialogue_dismiss_calls = []
    recommendations = [
        {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Terraform"}],
        },
        {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Terraform"}],
        },
        {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Terraform"}],
        },
    ]

    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )

    def fake_execute(sequence, **kwargs):
        calls.append(sequence)
        if len(calls) == 2:
            return {
                "status": "ERROR",
                "reason": "preview_board_click_failed",
            }
        return {"status": "OK", "steps": [{"count": len(sequence)}]}

    def fake_visible_start(**kwargs):
        visible_start_calls.append(kwargs)
        if len(visible_start_calls) < 3:
            return {
                "status": "NOT_FOUND",
                "reason": "start_mission_text_not_found",
            }
        return {
            "status": "OK",
            "target": {"window_x": 848, "window_y": 448},
            "click_result": {"status": "OK"},
        }

    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        fake_execute,
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: recommendations.pop(0),
    )
    monkeypatch.setattr(
        commands,
        "_lightning_dismiss_visible_dialogue",
        lambda **kwargs: dialogue_dismiss_calls.append(kwargs)
        or {"status": "OK", "dialogue_click": {"status": "OK"}},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_visible_start_mission",
        fake_visible_start,
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {"status": "NO_BRIDGE"},
    )

    result = commands.cmd_lightning_route_start(
        region_window_x=542,
        region_window_y=244,
        run_preflight=False,
        verify_route=False,
        expected_route_mission_id="Mission_Terraform",
    )

    assert result["status"] == "OK"
    assert result["reason"] == "route_preview_validated_start_clicked"
    commit = result["click_result"]["commit_click"]
    assert commit["reason"] == "sticky_dialogue_region_reopened_start_clicked"
    assert (
        commit["initial_start_click"]["reason"]
        == "start_mission_text_not_found"
    )
    assert commit["sticky_dialogue_retry"]["retry_actual_mission_id"] == (
        "Mission_Terraform"
    )
    assert len(calls) == 3
    assert any(
        step.get("control") == "mission_preview_board"
        for step in calls[1]
        if isinstance(step, dict)
    )
    assert calls[2][0]["description"] == (
        "Lightning route region after sticky dialogue"
    )
    assert visible_start_calls == [
        {"dry_run": False, "dismiss_dialogue": False},
        {"dry_run": False, "dismiss_dialogue": False},
        {"dry_run": False, "dismiss_dialogue": True},
    ]
    assert dialogue_dismiss_calls == [{"dry_run": False}]


def test_lightning_route_start_blocks_post_dialogue_preview_mismatch(monkeypatch):
    calls = []
    recommendations = [
        {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Tides"}],
        },
        {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Mines"}],
        },
    ]

    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )

    def fake_execute(sequence, **kwargs):
        calls.append(sequence)
        if len(calls) == 2:
            return {
                "status": "ERROR",
                "reason": "preview_board_click_failed",
            }
        return {"status": "OK", "steps": [{"count": len(sequence)}]}

    monkeypatch.setattr(
        commands,
        "_lightning_execute_route_start_sequence",
        fake_execute,
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: recommendations.pop(0),
    )
    monkeypatch.setattr(
        commands,
        "_lightning_dismiss_visible_dialogue",
        lambda **kwargs: {"status": "OK", "dialogue_click": {"status": "OK"}},
    )
    visible_start_calls = []

    monkeypatch.setattr(
        commands,
        "_lightning_click_visible_start_mission",
        lambda **kwargs: visible_start_calls.append(kwargs)
        or {"status": "NOT_FOUND", "reason": "start_mission_text_not_found"},
    )

    result = commands.cmd_lightning_route_start(
        region_window_x=542,
        region_window_y=244,
        run_preflight=False,
        verify_route=False,
        expected_route_mission_id="Mission_Tides",
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "route_preview_mission_mismatch_after_dialogue"
    assert result["click_result"]["actual_preview_mission_id"] == "Mission_Tides"
    assert result["click_result"]["post_dialogue_actual_mission_id"] == "Mission_Mines"
    assert result["click_result"]["commit_click"]["status"] == "BLOCKED"
    assert visible_start_calls == [{"dry_run": False, "dismiss_dialogue": False}]
    assert len(calls) == 2
    assert any(
        step.get("control") == "mission_preview_board"
        for step in calls[1]
        if isinstance(step, dict)
    )


def test_lightning_route_start_blocks_unknown_visual_region_index(monkeypatch):
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Train"}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visual_regions_from_recommendation",
        lambda recommendation: {
            "status": "OK",
            "regions": [{"index": 0, "window_x": 311, "window_y": 477}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_route_start_sequence",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not click")
        ),
    )

    result = commands.cmd_lightning_route_start(
        visual_region_index=9,
        dry_run=True,
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "visual_region_index_not_found"
    assert result["requested_visual_region_index"] == 9


def test_lightning_route_start_visual_index_uses_pause_map_peek(monkeypatch):
    calls = []

    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "pause_menu"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {
            "status": "OK",
            "source": "bridge_preview",
            "top3": [{"mission_id": "Mission_Train"}],
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_bridge_island_map_pause_peek",
        lambda: {"status": "OK", "map_screenshot_path": "/tmp/map.png"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_extract_red_regions_from_image",
        lambda path: {
            "status": "OK",
            "screenshot_path": path,
            "regions": [{"index": 1, "window_x": 420, "window_y": 210}],
        },
    )

    def fake_sequence(x, y, **kwargs):
        calls.append((x, y))
        return {"status": "OK", "steps": []}

    monkeypatch.setattr(commands, "_lightning_click_route_start_sequence", fake_sequence)

    result = commands.cmd_lightning_route_start(
        visual_region_index=1,
        validate_preview_mission=False,
    )

    assert result["status"] == "OK"
    assert result["visual_region_peek"]["map_screenshot_path"] == "/tmp/map.png"
    assert calls == [(420, 210)]
