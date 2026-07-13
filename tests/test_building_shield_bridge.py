from pathlib import Path
import shutil
import subprocess

import pytest

from src.bridge import reader
from src.model.board import Board, BoardTile
from src.solver.verify import classify_diff, diff_states, snapshot_after_action


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def _shield_helper_source() -> str:
    source = MODLOADER.read_text()
    start = source.index("local function get_runtime_region_tile_shields()")
    end = source.index("local function dump_state()", start)
    return source[start:end]


def test_building_shield_fallback_uses_live_region_data_not_disk_save():
    helper = _shield_helper_source()

    assert 'region.player.map_data.map' in helper
    assert 'entry.shield == true' in helper
    assert helper.index("Board:IsShield(pt)") < helper.index(
        "runtime_region_shields[pt.x"
    )
    assert "_read_save_data" not in helper
    assert "io.open" not in helper


def test_building_shield_fallback_tracks_runtime_shield_pop_when_lua_available():
    lua = shutil.which("lua") or shutil.which("luajit")
    if lua is None:
        pytest.skip("Lua interpreter is not installed")

    harness = _shield_helper_source() + r'''
local entry = { loc = { x = 1, y = 5 }, shield = true }
RegionData = {
    iBattleRegion = 2,
    region2 = { player = { map_data = { map = { entry } } } },
}
Board = {
    IsShield = function() error("memedit unavailable") end,
}
local pt = { x = 1, y = 5 }
local runtime_shields = get_runtime_region_tile_shields()

assert(get_live_tile_shield(pt, runtime_shields) == true)
entry.shield = false
runtime_shields = get_runtime_region_tile_shields()
assert(get_live_tile_shield(pt, runtime_shields) == false)

-- A real memedit result is authoritative in both directions.
Board.IsShield = function() return false end
entry.shield = true
assert(get_live_tile_shield(pt, runtime_shields) == false)

-- Retain compatibility with extensions that provide IsShielded instead.
Board.IsShield = nil
RegionData = nil
Board.IsShielded = function() return true end
assert(get_live_tile_shield(pt, nil) == true)
'''
    result = subprocess.run(
        [lua, "-"],
        input=harness,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_board_tile_declares_and_imports_bridge_shield_status():
    assert BoardTile(shield=True).shield is True

    board = Board.from_bridge_data({
        "tiles": [{
            "x": 1,
            "y": 5,
            "terrain": "building",
            "terrain_id": 1,
            "building_hp": 1,
            "shield": True,
        }],
        "units": [],
    })
    assert board.tile(1, 5).shield is True


def test_verify_reports_consumed_building_shield_as_tile_status():
    predicted = Board()
    predicted.tile(1, 5).terrain = "building"
    predicted.tile(1, 5).building_hp = 1
    predicted.tile(1, 5).shield = True
    snapshot = snapshot_after_action(
        predicted,
        action_index=0,
        mech_uid=-1,
        events=["building shield at (1,5)"],
    )

    actual = Board()
    actual.tile(1, 5).terrain = "building"
    actual.tile(1, 5).building_hp = 1
    actual.tile(1, 5).shield = False

    diff = diff_states(snapshot, actual)
    assert diff.tile_diffs == [{
        "x": 1,
        "y": 5,
        "field": "shield",
        "predicted": True,
        "actual": False,
    }]
    assert classify_diff(diff)["top_category"] == "tile_status"


def _bridge_payload(*, live_capability=False, acted=False):
    return {
        "mission_id": "Mission_Belt",
        "phase": "combat_player",
        "active_mechs": 2 if acted else 3,
        "tile_shields_live": live_capability,
        "units": [
            {
                "team": 1,
                "hp": 3,
                "active": not (acted and uid == 0),
                "weapons": ["weapon"],
            }
            for uid in range(3)
        ],
        "tiles": [
            {"x": 1, "y": 5, "terrain_id": 1},
            {"x": 1, "y": 6, "terrain": "building"},
            {"x": 4, "y": 3, "terrain_id": 1},
        ],
    }


def test_save_shield_fallback_is_fresh_turn_only_and_live_capability_wins(monkeypatch):
    monkeypatch.setattr(
        reader,
        "_read_active_building_shields_from_save",
        lambda: ("Mission_Belt", {(1, 5), (1, 6), (4, 3)}),
    )

    fresh = _bridge_payload()
    assert reader._apply_save_building_shield_overlay(fresh) == [
        [1, 5], [1, 6], [4, 3]
    ]
    assert all(tile["shield"] is True for tile in fresh["tiles"])

    mid_turn = _bridge_payload(acted=True)
    assert reader._apply_save_building_shield_overlay(mid_turn) == []
    assert all("shield" not in tile for tile in mid_turn["tiles"])

    live = _bridge_payload(live_capability=True)
    assert reader._apply_save_building_shield_overlay(live) == []
    assert all("shield" not in tile for tile in live["tiles"])
