"""Window-selection regressions for combat click calibration."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from src.capture import detect_grid
from src.capture.detect_grid import WindowInfo
from src.control import executor


def _fake_quartz_windows():
    return [
        {
            "kCGWindowOwnerName": "Into the Breach",
            "kCGWindowName": "Window",
            "kCGWindowBounds": {
                "X": 225,
                "Y": 36,
                "Width": 66,
                "Height": 20,
            },
            "kCGWindowNumber": 11844,
        },
        {
            "kCGWindowOwnerName": "Into the Breach",
            "kCGWindowName": "Into the Breach",
            "kCGWindowBounds": {
                "X": 215,
                "Y": 32,
                "Width": 1280,
                "Height": 748,
            },
            "kCGWindowNumber": 11805,
        },
    ]


def _install_fake_quartz(monkeypatch) -> None:
    fake = SimpleNamespace(
        kCGWindowListOptionOnScreenOnly=1,
        kCGNullWindowID=0,
        CGWindowListCopyWindowInfo=lambda _options, _window_id: (
            _fake_quartz_windows()
        ),
    )
    monkeypatch.setattr(detect_grid.os, "name", "posix")
    monkeypatch.setitem(sys.modules, "Quartz", fake)


def test_find_game_window_prefers_main_quartz_surface(monkeypatch):
    _install_fake_quartz(monkeypatch)

    assert detect_grid.find_game_window() == WindowInfo(
        x=215,
        y=32,
        width=1280,
        height=748,
        window_id=11805,
    )


def test_find_game_window_uses_largest_surface_without_exact_title(monkeypatch):
    windows = _fake_quartz_windows()
    windows[1]["kCGWindowName"] = "SDL Application"
    fake = SimpleNamespace(
        kCGWindowListOptionOnScreenOnly=1,
        kCGNullWindowID=0,
        CGWindowListCopyWindowInfo=lambda _options, _window_id: windows,
    )
    monkeypatch.setattr(detect_grid.os, "name", "posix")
    monkeypatch.setitem(sys.modules, "Quartz", fake)

    assert detect_grid.find_game_window() == WindowInfo(
        x=215,
        y=32,
        width=1280,
        height=748,
        window_id=11805,
    )


def test_find_game_window_applescript_fallback_uses_named_window(monkeypatch):
    monkeypatch.setattr(detect_grid.os, "name", "posix")
    monkeypatch.setitem(sys.modules, "Quartz", None)
    captured = {}

    def fake_run(args, **_kwargs):
        captured["script"] = args[-1]
        return SimpleNamespace(returncode=0, stdout="215,32,1280,748\n")

    monkeypatch.setattr(detect_grid.subprocess, "run", fake_run)

    assert detect_grid.find_game_window() == WindowInfo(
        x=215,
        y=32,
        width=1280,
        height=748,
    )
    assert 'window "Into the Breach"' in captured["script"]


def test_end_turn_plan_keeps_calibrated_window_local_point(monkeypatch):
    _install_fake_quartz(monkeypatch)
    executor.recalibrate()

    try:
        click = executor.plan_end_turn()[0]
    finally:
        executor.recalibrate()

    assert (click["x"], click["y"]) == (341, 152)
    assert (click["window_x"], click["window_y"]) == (126, 120)
    assert click["codex_computer_use"] == {
        "type": "left_click",
        "x": 126,
        "y": 120,
        "coordinate_space": "window",
        "description": "Click End Turn",
    }
