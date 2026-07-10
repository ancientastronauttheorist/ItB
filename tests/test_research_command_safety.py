"""Command-level safety regressions for live research capture plans."""

from types import SimpleNamespace

from src.capture.detect_grid import WindowInfo
from src.loop import commands
from src.loop.session import RunSession
from src.research import capture, orchestrator


def _unit(type_name, *, active=False, is_mech=False, weapon=""):
    return SimpleNamespace(
        type=type_name,
        x=3,
        y=2,
        hp=3,
        active=active,
        is_mech=is_mech,
        weapon=weapon,
    )


def test_research_next_is_click_free_with_active_player_actor(monkeypatch):
    session = RunSession()
    session.enqueue_research("NovelTrainDamaged", None, current_turn=3)
    actor = _unit("MirrorMech", active=True, is_mech=True, weapon="Brute_Mirrorshot")
    target = _unit("NovelTrainDamaged")
    board = SimpleNamespace(units=[actor, target], mechs=lambda: [actor])

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (board, {"phase": "combat_player"}),
    )
    monkeypatch.setattr(RunSession, "save", lambda self: None)
    monkeypatch.setattr(orchestrator, "grid_to_mcp", lambda x, y: (740, 366))

    raw_ui = capture.load_ui_regions()
    reference = raw_ui["reference_window"]
    resolved_ui = capture.resolve_ui_regions(
        raw_ui,
        current_window=WindowInfo(
            x=reference["x"],
            y=reference["y"],
            width=reference["width"],
            height=reference["height"],
        ),
    )
    monkeypatch.setattr(capture, "load_ui_regions", lambda: raw_ui)
    monkeypatch.setattr(capture, "resolve_ui_regions", lambda raw: resolved_ui)

    result = commands.cmd_research_next()

    actions = [item["action"] for item in result["plan"]["batch"]]
    assert result["status"] == "PLAN"
    assert result["phase"] == "combat_player"
    assert result["active_player_actors"] == 1
    assert result["unit_click_allowed"] is False
    assert result["plan"]["capture_mode"] == "hover_only"
    assert "left_click" not in actions
    assert session.research_queue[0]["status"] == "in_progress"
