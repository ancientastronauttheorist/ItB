"""Pin grid_to_mcp to the shared live grid calibration.

The live Detritus deployment on 2026-04-30 exposed a stale hardcoded
isometric formula: ``read`` printed D5 as roughly (661, 362), but the visible
tile center and ``cmd_calibrate`` both landed near (653, 447). These tests keep
``grid_to_mcp`` on the same ``GridConfig`` path used by calibration.
"""

from __future__ import annotations

import pytest

import src.control.executor as executor
from src.capture.detect_grid import grid_from_window


class _LiveWindow:
    """Window position from the live deployment calibration."""
    x = 215
    y = 32
    width = 1280
    height = 748


class _ShiftedWindow:
    x = 100
    y = 0
    width = 1280
    height = 748


@pytest.fixture(autouse=True)
def _pin_grid(monkeypatch):
    win = _LiveWindow()
    monkeypatch.setattr(executor, "_cached_window", win)
    monkeypatch.setattr(executor, "_cached_grid", grid_from_window(win))


@pytest.mark.parametrize("name,save_x,save_y,expected_x,expected_y", [
    ("H8_top", 0, 0, 679, 602),
    ("D5_live_deploy_regression", 3, 4, 653, 447),
    ("C5_live_deploy_neighbor", 3, 5, 682, 436),
    ("D7_live_deploy_zone", 1, 4, 749, 522),
    ("A1_bottom", 7, 7, 549, 266),
])
def test_tile_center_matches_shared_calibration(name, save_x, save_y,
                                                expected_x, expected_y):
    """grid_to_mcp reproduces cmd_calibrate's GridConfig tile centers."""
    assert executor.grid_to_mcp(save_x, save_y) == (expected_x, expected_y), name


def test_grid_to_mcp_delegates_to_grid_config():
    """The executor output matches GridConfig for representative board points."""
    grid = grid_from_window(_LiveWindow())
    for save_x, save_y in [(0, 0), (3, 4), (3, 5), (1, 4), (7, 7)]:
        raw_x, raw_y = grid.tile_to_pixel(save_x + 1, save_y + 1)
        assert executor.grid_to_mcp(save_x, save_y) == (
            int(round(raw_x)),
            int(round(raw_y)),
        )


def test_window_offset_shifts_all_tiles(monkeypatch):
    """Moving the window shifts every tile coordinate by the window delta."""
    ref = {t: executor.grid_to_mcp(*t) for t in [(0, 0), (7, 7), (3, 4)]}
    win = _ShiftedWindow()
    monkeypatch.setattr(executor, "_cached_window", win)
    monkeypatch.setattr(executor, "_cached_grid", grid_from_window(win))
    shifted = {t: executor.grid_to_mcp(*t) for t in ref}
    dx = _ShiftedWindow.x - _LiveWindow.x
    dy = _ShiftedWindow.y - _LiveWindow.y
    for t in ref:
        assert shifted[t] == (ref[t][0] + dx, ref[t][1] + dy), (
            f"tile {t}: shifted {shifted[t]} not equal to ref {ref[t]} "
            f"+ window delta ({dx},{dy})"
        )
