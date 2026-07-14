import sys
from types import SimpleNamespace

from src.control import mac_click
from src.loop import commands


def test_pyautogui_click_dwells_after_move_before_mouse_down(monkeypatch):
    events = []
    fake_pyautogui = SimpleNamespace(
        moveTo=lambda x, y, duration: events.append(("move", x, y, duration)),
        mouseDown=lambda x, y: events.append(("down", x, y)),
        mouseUp=lambda x, y: events.append(("up", x, y)),
    )
    monkeypatch.setitem(sys.modules, "pyautogui", fake_pyautogui)
    monkeypatch.setattr(
        mac_click.time,
        "sleep",
        lambda seconds: events.append(("sleep", seconds)),
    )

    result = mac_click._pyautogui_click(
        10,
        20,
        hold_seconds=0.12,
        pre_click_seconds=0.20,
    )

    assert result["status"] == "OK"
    assert result["pre_click_seconds"] == 0.20
    assert events == [
        ("move", 10, 20, 0.05),
        ("sleep", 0.20),
        ("down", 10, 20),
        ("sleep", 0.12),
        ("up", 10, 20),
    ]


def test_click_window_point_forwards_pre_click_dwell(monkeypatch):
    calls = []
    monkeypatch.setattr(
        mac_click,
        "_get_window_bounds",
        lambda _app: {"x": 215, "y": 32, "width": 1280, "height": 748},
    )
    monkeypatch.setattr(
        mac_click,
        "click_screen_point",
        lambda x, y, **kwargs: calls.append((x, y, kwargs))
        or {"status": "OK"},
    )

    result = mac_click.click_window_point(
        126,
        120,
        pre_click_seconds=0.20,
    )

    assert result["status"] == "OK"
    assert calls[0][0:2] == (341, 152)
    assert calls[0][2]["pre_click_seconds"] == 0.20


def test_local_end_turn_dispatch_uses_targeted_dwell(monkeypatch):
    calls = []
    monkeypatch.setattr(
        commands,
        "_prepare_local_dispatch_guard",
        lambda _label: {"status": "OK"},
    )
    monkeypatch.setattr(
        mac_click,
        "click_window_point",
        lambda x, y, **kwargs: calls.append((x, y, kwargs))
        or {"status": "OK"},
    )

    result = commands._dispatch_click_batch_locally(
        [
            {
                "type": "left_click",
                "window_x": 126,
                "window_y": 120,
                "description": "Click End Turn",
            }
        ],
        execute=True,
        label="end_turn",
    )

    assert result["status"] == "DISPATCHED"
    assert len(calls) == 1
    assert calls[0][2]["pre_click_seconds"] == 0.20


def test_dispatch_end_turn_records_confirmed_one_shot_delivery(monkeypatch):
    monkeypatch.setattr(
        commands,
        "cmd_click_end_turn",
        lambda: {"status": "PLAN", "batch": [{"type": "left_click"}]},
    )
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (None, {"phase": "combat_player", "turn": 1}),
    )
    monkeypatch.setattr(
        commands,
        "_dispatch_click_batch_locally",
        lambda *_args, **_kwargs: {"status": "DISPATCHED", "executed": True},
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda state: {"status": "OK", "reason": "phase_changed", "state": state},
    )
    monkeypatch.setattr(
        commands,
        "_prepare_local_dispatch_guard",
        lambda _label: {"status": "OK", "screenshot": {"status": "OK"}},
    )

    result = commands.cmd_dispatch_end_turn(execute=True)

    assert result["dispatch"]["delivery_confirmation"] == "delivered_confirmed"
    assert result["dispatch"]["retry_allowed"] is False
    assert result["next_step"] == "read"


def test_dispatch_end_turn_marks_ambiguous_delivery_non_retryable(monkeypatch):
    monkeypatch.setattr(
        commands,
        "cmd_click_end_turn",
        lambda: {"status": "PLAN", "batch": [{"type": "left_click"}]},
    )
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (None, {"phase": "combat_player", "turn": 1}),
    )
    monkeypatch.setattr(
        commands,
        "_dispatch_click_batch_locally",
        lambda *_args, **_kwargs: {"status": "DISPATCHED", "executed": True},
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda _state: {
            "status": "END_TURN_CLICK_NOT_OBSERVED",
            "reason": "bridge_still_player_turn",
        },
    )
    monkeypatch.setattr(
        commands,
        "_prepare_local_dispatch_guard",
        lambda _label: {"status": "OK", "screenshot": {"status": "OK"}},
    )

    result = commands.cmd_dispatch_end_turn(execute=True)

    assert result["dispatch"]["delivery_confirmation"] == "delivered_unconfirmed"
    assert result["dispatch"]["retry_allowed"] is False
    assert "do not retry" in result["next_step"]
