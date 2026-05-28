from __future__ import annotations

import json

from src.loop import commands
from src.loop.session import RunSession


def test_lightning_loop_clicks_end_turn_plan(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = {"auto_turn": 0, "clicks": 0}

    def fake_auto_turn(**kwargs):
        calls["auto_turn"] += 1
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
    monkeypatch.setattr(commands, "_click_end_turn_from_plan_result", fake_click)
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda turn_result: {"status": "OK", "reason": "phase_changed"},
    )

    result = commands.cmd_lightning_loop(max_turns=3)

    assert result["reason"] == "TERMINAL_OR_MISSION_END"
    assert result["end_turn_clicks"] == 1
    assert calls == {"auto_turn": 2, "clicks": 1}


def test_lightning_ui_clicks_known_control_dry_run():
    result = commands.cmd_lightning_ui("deploy_confirm", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "deploy_confirm"
    assert result["window_x"] == 106
    assert result["window_y"] == 164


def test_lightning_ui_clicks_understood_alias_dry_run():
    result = commands.cmd_lightning_ui("understood", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "modal_understood"
    assert result["window_x"] == 666
    assert result["window_y"] == 518


def test_lightning_ui_clicks_panel_continue_alias_dry_run():
    result = commands.cmd_lightning_ui("perfect_continue", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "panel_continue"
    assert result["window_x"] == 846
    assert result["window_y"] == 550


def test_lightning_ui_clicks_ceo_continue_alias_dry_run():
    result = commands.cmd_lightning_ui("ceo_continue", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "bottom_continue"
    assert result["window_x"] == 1005
    assert result["window_y"] == 676


def test_lightning_ui_clicks_dialogue_textbox_alias_dry_run():
    result = commands.cmd_lightning_ui("dialogue", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "dialogue_textbox"
    assert result["window_x"] == 520
    assert result["window_y"] == 205


def test_lightning_ui_clicks_mission_preview_board_alias_dry_run():
    result = commands.cmd_lightning_ui("start_mission", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "mission_preview_board"
    assert result["window_x"] == 815
    assert result["window_y"] == 468


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

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert result["reason"] == "combat_loop_returned"
    assert [call[0] for call in calls] == ["deploy", "click", "loop"]
    assert calls[1] == ("click", "deploy_confirm")


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

    result = commands.cmd_lightning_attempt(time_limit=1.5, max_turns=4)

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert result["action"]["action"] == "combat_loop"
    assert calls[0]["time_limit"] == 1.5
    assert calls[0]["max_turns"] == 4


def test_lightning_attempt_waits_in_enemy_phase_instead_of_looping(monkeypatch):
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
            "mech_count": 3,
            "deployment_zone_count": 8,
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_loop",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not loop")),
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_WAITING"
    assert result["reason"] == "enemy_or_deployment_animation"


def test_lightning_attempt_waits_when_player_phase_has_no_active_mechs(monkeypatch):
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
            "phase": "combat_player",
            "turn": 2,
            "active_mechs": 0,
            "mech_count": 3,
            "deployment_zone_count": 0,
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_loop",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not loop")),
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_WAITING"
    assert result["reason"] == "no_active_mechs_yet"


def test_lightning_attempt_recommends_route_on_island_map(monkeypatch):
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
        "cmd_recommend_mission",
        lambda **kwargs: {"status": "OK", "top3": [{"mission_id": "Mission_Train"}]},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map_or_unknown"},
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_ROUTE_READY"
    assert result["recommendation"]["top3"][0]["mission_id"] == "Mission_Train"


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


def test_lightning_attempt_blocks_on_wall_budget(monkeypatch):
    old_session = RunSession(
        run_id="20000101_000000_000",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    monkeypatch.setattr(commands, "_load_session", lambda: old_session)

    result = commands.cmd_lightning_attempt(max_wall_seconds=1)

    assert result["status"] == "LIGHTNING_ATTEMPT_BUDGET_EXCEEDED"


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

    result = commands.cmd_lightning_loop(max_turns=1)

    assert result["status"] == "RESEARCH_REQUIRED"
    assert result["pending_research_count"] == 1


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

    result = commands.cmd_lightning_loop(max_turns=1)

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

    result = commands.cmd_lightning_loop(max_turns=3)

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

    result = commands.cmd_lightning_loop(max_turns=3)

    assert result["reason"] == "terminal_or_mission_end"
    assert result["end_turn_clicks"] == 1
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

    result = commands.cmd_lightning_loop(max_turns=1)

    assert result["reason"] == "terminal_or_mission_end"
    assert result["turns"][0]["terminal_transition"] is True


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
