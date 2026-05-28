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
