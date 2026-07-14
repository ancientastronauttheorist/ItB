from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from src.bridge.protocol import BridgeError
from src.bridge.writer import _resolve_weapon_slot
from src.loop.commands import _refresh_board_weapon_slots_from_save
from src.model.board import Board, Unit
from src.solver.solver import MechAction


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def _punch_board(*, secondary: str = "") -> Board:
    board = Board()
    board.units = [
        Unit(
            uid=0,
            type="PunchMech",
            x=5,
            y=5,
            hp=6,
            max_hp=6,
            team=1,
            is_mech=True,
            move_speed=3,
            flying=False,
            massive=True,
            armor=False,
            pushable=True,
            weapon="Prime_Punchmech",
            weapon2=secondary,
        )
    ]
    return board


def _burst_action() -> MechAction:
    return MechAction(
        mech_uid=0,
        mech_type="PunchMech",
        move_to=(6, 6),
        weapon="Prime_Lasermech_A",
        target=(6, 5),
        description="fire Burst Beam",
    )


def test_save_overlay_restores_purchased_secondary_on_fresh_live_board(monkeypatch):
    board = _punch_board()
    bridge_data = {
        "units": [{
            "uid": 0,
            "type": "PunchMech",
            "mech": True,
            "weapons": ["Prime_Punchmech"],
        }],
    }
    state = SimpleNamespace(
        weapons=[
            "Prime_Punchmech_B",
            "Prime_Lasermech_A",
            "Ranged_Ignite",
            "Passive_Defenses",
            "Vek_Hornet",
            "",
        ],
        active_mission=None,
    )
    monkeypatch.setattr(
        "src.loop.commands.load_game_state",
        lambda profile="Alpha": state,
    )

    refreshed = _refresh_board_weapon_slots_from_save(board, bridge_data)

    assert refreshed is board
    assert board.units[0].weapon == "Prime_Punchmech_B"
    assert board.units[0].weapon2 == "Prime_Lasermech_A"
    assert _resolve_weapon_slot(_burst_action(), board) == 1


def test_explicit_unmatched_weapon_fails_closed_instead_of_firing_primary():
    with pytest.raises(BridgeError, match="Prime_Lasermech_A"):
        _resolve_weapon_slot(_burst_action(), _punch_board())


def test_unknown_weapon_only_infers_an_unambiguous_single_slot():
    action = _burst_action()
    action.weapon = "Unknown"

    assert _resolve_weapon_slot(action, _punch_board()) == 0

    with pytest.raises(BridgeError, match="Cannot resolve weapon"):
        _resolve_weapon_slot(
            action,
            _punch_board(secondary="Prime_Lasermech_A"),
        )

    action.weapon = ""
    assert _resolve_weapon_slot(action, _punch_board()) == 0


def test_lua_slot_resolver_accepts_save_backed_secondary_beyond_static_skill_list():
    lua = shutil.which("lua") or shutil.which("luajit")
    if lua is None:
        pytest.skip("Lua interpreter is not installed")

    source = MODLOADER.read_text()
    save_helper = source[
        source.index("local function effective_weapon_from_save"):
        source.index("local function tile_damage_snapshot")
    ]
    slot_helper = source[
        source.index("local function effective_weapon_name_by_slot"):
        source.index("local function pawn_is_guarding")
    ]
    harness = r'''
local function log_bridge(_msg) end
local save_data = {
    current_weapons = {"Prime_Punchmech_B", "Prime_Lasermech_A"},
}
local function _read_save_data() return save_data end
_G.PunchMech = { SkillList = {"Prime_Punchmech"} }
_G.Prime_Punchmech_B = {}
_G.Prime_Lasermech_A = {}
local pawn = {
    GetType = function() return "PunchMech" end,
    GetId = function() return 0 end,
}
''' + save_helper + slot_helper + r'''
local wname, base_wname, slot, err, source_name =
    effective_weapon_name_by_slot(pawn, 1)
assert(err == nil, tostring(err))
assert(wname == "Prime_Lasermech_A")
assert(base_wname == nil)
assert(slot == 2)
assert(source_name == "save")
'''
    result = subprocess.run(
        [lua, "-"],
        input=harness,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_lua_bridge_removes_temporary_append_and_checks_false_result():
    source = MODLOADER.read_text()
    execute_start = source.index("local function execute_weapon_by_slot")
    execute_end = source.index("-- Command executor", execute_start)
    execute_source = source[execute_start:execute_end]

    assert "local restore_skill_list = false" in execute_source
    assert "local ok, fired_or_err = pcall" in execute_source
    assert "if fired_or_err == false then" in execute_source
    assert execute_source.count(
        "pawn_def.SkillList[slot] = base_wname"
    ) == 2
    assert "restore_wname" not in execute_source
