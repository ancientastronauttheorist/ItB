"""Pin the grid_to_mcp formula against live hover-measured tile centers.

Measured 2026-04-23 on a live Silicate Plains combat board, game window at
Quartz (215, 32, 1280, 748). User-hovered each tile to its visual center
and cursor_position returned image-pixel MCP coords:

    H8 save(0,0)  (707, 122)   top vertex
    A8 save(0,7)  (384, 359)   left vertex
    H1 save(7,0)  (1033, 364)  right vertex
    A1 save(7,7)  (705, 603)   bottom vertex
    B6 save(2,6)  (522, 396)   PunchMech tile (info panel confirmed)
    C5 save(3,5)  (615, 396)   JetMech tile (info panel confirmed)
    E5 save(3,3)  (707, 328)   RocketMech tile (info panel confirmed)

A least-squares isometric fit gives origin_win_rel=(492.25, 89.50),
step_x=46.357, step_y=34.357 with max residual 3.3 px.
"""

from __future__ import annotations

import pytest

import src.control.executor as executor


class _LiveWindow:
    """Window at the position where the corner measurements were taken."""
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
def _pin_window(monkeypatch):
    monkeypatch.setattr(executor, "_cached_window", _LiveWindow())
    monkeypatch.setattr(executor, "_cached_grid", object())


# Tolerance accounts for (a) human-hover precision (the corners were eyeballed
# to tile centers, ~2 px error expected) plus (b) integer rounding in the
# formula output. The mech tiles were computed FROM the fitted constants so
# they match the formula exactly; the corner tiles carry the fit residual.
_MAX_HOVER_ERR_PX = 4


@pytest.mark.parametrize("name,save_x,save_y,measured_x,measured_y", [
    ("H8_top",       0, 0,  707, 122),
    ("A8_left",      0, 7,  384, 359),
    ("H1_right",     7, 0, 1033, 364),
    ("A1_bottom",    7, 7,  705, 603),
    ("B6_PunchMech", 2, 6,  522, 396),
    ("C5_JetMech",   3, 5,  615, 396),
    ("E5_RocketMech", 3, 3, 707, 328),
])
def test_tile_center_matches_measurement(name, save_x, save_y,
                                          measured_x, measured_y):
    """grid_to_mcp reproduces each hover-measured tile center within tolerance."""
    px, py = executor.grid_to_mcp(save_x, save_y)
    err = ((px - measured_x) ** 2 + (py - measured_y) ** 2) ** 0.5
    assert err <= _MAX_HOVER_ERR_PX, (
        f"{name}: predicted ({px}, {py}) vs measured "
        f"({measured_x}, {measured_y}) — err={err:.2f}px exceeds "
        f"tolerance {_MAX_HOVER_ERR_PX}px"
    )


def test_vertical_axis_shares_x():
    """H8 and A1 both have save_x == save_y so their MCP x must be equal."""
    h8_x, _ = executor.grid_to_mcp(0, 0)
    a1_x, _ = executor.grid_to_mcp(7, 7)
    assert h8_x == a1_x


def test_horizontal_midline_shares_y():
    """A8 (save 0,7) and H1 (save 7,0) lie on the horizontal midline."""
    _, a8_y = executor.grid_to_mcp(0, 7)
    _, h1_y = executor.grid_to_mcp(7, 0)
    assert a8_y == h1_y


def test_window_offset_shifts_all_tiles(monkeypatch):
    """Moving the window shifts every tile coordinate by the window delta."""
    ref = {t: executor.grid_to_mcp(*t) for t in [(0, 0), (7, 7), (0, 7), (7, 0)]}
    monkeypatch.setattr(executor, "_cached_window", _ShiftedWindow())
    shifted = {t: executor.grid_to_mcp(*t) for t in ref}
    dx = _ShiftedWindow.x - _LiveWindow.x
    dy = _ShiftedWindow.y - _LiveWindow.y
    for t in ref:
        assert shifted[t] == (ref[t][0] + dx, ref[t][1] + dy), (
            f"tile {t}: shifted {shifted[t]} not equal to ref {ref[t]} + window delta ({dx},{dy})"
        )
