from __future__ import annotations

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
