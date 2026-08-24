from copy import deepcopy
from pathlib import Path

import pytest

from src.loop import commands
from src.bridge.reader import _normalize_mission_pistons
from src.loop.commands import (
    _lookahead_forecast_gaps,
    _mission_piston_forecast_block,
)
from src.loop.session import RunSession
from src.model.board import Board, validate_mission_piston_payload
from src.model.pawn_stats import get_pawn_stats
from src.model.weapons import get_weapon_def
from src.solver import unknown_detector

try:
    from lupa import lua51
except ImportError:  # pragma: no cover - optional local test dependency
    lua51 = None


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def _piston(uid=41, piston_type="Pawn_Piston_U", x=3, y=4, hp=1, **overrides):
    unit = {
        "uid": uid,
        "type": piston_type,
        "x": x,
        "y": y,
        "hp": hp,
        "max_hp": 1,
        "team": 2,
        "move": 7,
        "base_move": 7,
        "pushable": True,
        "active": True,
        "has_queued_attack": True,
        "queued_target": [3, 3],
        "weapons": ["Piston_U_Atk"],
    }
    unit.update(overrides)
    return unit


def _payload(*, units=None, actions=None, complete=True, mission_id="Mission_Piston"):
    if units is None:
        units = [_piston()]
    if actions is None:
        actions = [{"uid": 41, "front": [3, 3]}]
    return {
        "mission_id": mission_id,
        "mission_pistons": {"complete": complete, "actions": actions},
        "tiles": [],
        "units": units,
        "spawning_tiles": [],
    }


def _load_lua_helper():
    if lua51 is None:
        pytest.skip("exact Lua 5.1 Mission_Piston harness requires lupa.lua51")
    source = MODLOADER.read_text()
    start = source.index("local function mission_pistons")
    end = source.index("\nlocal function dump_state()", start)
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    helper = runtime.execute(source[start:end] + "\nreturn mission_pistons")
    return helper, runtime


def _lua_units(runtime, units):
    return runtime.table_from([
        runtime.table_from(unit) for unit in units
    ])


def test_lua_helper_preserves_native_unit_order_and_complete_empty_state():
    helper, runtime = _load_lua_helper()
    units = [
        _piston(42, "Pawn_Piston_L", 6, 2),
        _piston(41, "Pawn_Piston_U", 3, 4),
        {"uid": 90, "type": "Scarab1", "x": 1, "y": 1, "hp": 2, "team": 6},
    ]

    result = helper("Mission_Piston", _lua_units(runtime, units))
    assert result["complete"] is True
    assert result["actions"][1]["uid"] == 42
    assert [result["actions"][1]["front"][1], result["actions"][1]["front"][2]] == [5, 2]
    assert result["actions"][2]["uid"] == 41
    assert [result["actions"][2]["front"][1], result["actions"][2]["front"][2]] == [3, 3]

    empty = helper("Mission_Piston", _lua_units(runtime, []))
    assert empty["complete"] is True
    assert len(empty["actions"]) == 0
    assert helper("Mission_Wind", _lua_units(runtime, units)) is None


def test_lua_helper_marks_malformed_or_impossible_state_incomplete():
    helper, runtime = _load_lua_helper()
    for units in (
        [_piston(team=6)],
        [_piston(x=0, piston_type="Pawn_Piston_L")],
        [_piston(), _piston()],
    ):
        result = helper("Mission_Piston", _lua_units(runtime, units))
        assert result["complete"] is False
        assert len(result["actions"]) == 0


def test_modloader_serializes_mission_scoped_pistons_atomically():
    source = MODLOADER.read_text()
    assert "local pistons = mission_pistons(mission.ID, state.units)" in source
    assert "state.mission_pistons = pistons" in source
    assert "complete = true, actions = actions" in source


@pytest.mark.parametrize(
    "data",
    [
        _payload(mission_id="Mission_Wind"),
        _payload(complete=False),
        _payload(actions=[]),
        _payload(actions=[{"uid": 41, "front": [3, 2]}]),
        _payload(actions=[{"uid": 41, "front": [3, 3]}, {"uid": 41, "front": [3, 3]}]),
        _payload(
            units=[
                _piston(42, "Pawn_Piston_L", 6, 2),
                _piston(41, "Pawn_Piston_U", 3, 4),
            ],
            actions=[
                {"uid": 41, "front": [3, 3]},
                {"uid": 42, "front": [5, 2]},
            ],
        ),
        _payload(units=[_piston(team=6)]),
        _payload(units=[], actions=[{"uid": 41, "front": [3, 3]}]),
    ],
)
def test_reader_drops_partial_stale_or_uncorroborated_payloads(data):
    data = deepcopy(data)
    _normalize_mission_pistons(data)
    assert "mission_pistons" not in data


def test_reader_canonicalizes_valid_payload_and_accepts_proven_empty_state():
    data = _payload(
        units=[
            _piston(42, "Pawn_Piston_L", 6, 2),
            _piston(41, "Pawn_Piston_U", 3, 4),
        ],
        actions=[
            {"uid": 42, "front": [5, 2]},
            {"uid": 41, "front": [3, 3]},
        ],
    )
    _normalize_mission_pistons(data)
    assert data["mission_pistons"] == {
        "complete": True,
        "actions": [
            {"uid": 42, "front": [5, 2]},
            {"uid": 41, "front": [3, 3]},
        ],
    }

    empty = _payload(units=[], actions=[])
    _normalize_mission_pistons(empty)
    assert validate_mission_piston_payload(empty) == []


def test_python_board_preserves_state_and_forces_exact_neutral_static_traits():
    board = Board.from_bridge_data(_payload())
    copied = board.copy()

    assert board.mission_pistons_known is True
    assert board.mission_piston_actions == [(41, 3, 3)]
    assert copied.mission_pistons_known is True
    assert copied.mission_piston_actions == [(41, 3, 3)]
    piston = board.units[0]
    assert piston.team == 2
    assert piston.move_speed == 0
    assert piston.base_move == 0
    assert piston.pushable is False
    assert piston.active is False
    assert piston.has_queued_attack is False
    assert (piston.queued_target_x, piston.queued_target_y) == (-1, -1)


def test_source_catalog_and_static_defs_cover_all_directional_pistons():
    known = __import__("json").loads(Path("data/known_types.json").read_text())
    pawn_types = {
        "Pawn_Piston_U", "Pawn_Piston_R", "Pawn_Piston_D", "Pawn_Piston_L",
    }
    weapon_ids = {
        "Piston_U_Atk", "Piston_R_Atk", "Piston_D_Atk", "Piston_L_Atk",
    }
    assert set(known["source_known_pawn_types"]) == pawn_types
    assert set(known["source_known_mission_weapons"]) == weapon_ids
    for pawn_type, weapon_id in zip(sorted(pawn_types), sorted(weapon_ids)):
        stats = get_pawn_stats(pawn_type)
        assert stats.move_speed == 0
        assert stats.pushable is False
        assert stats.default_weapon == weapon_id
        weapon = get_weapon_def(weapon_id)
        assert weapon.damage == 0
        assert weapon.push == "forward"
        assert weapon.range_max == 1

    unknown_detector.reset_cache()
    board = Board.from_bridge_data(_payload())
    assert unknown_detector.detect_unknowns(board, phase="combat_player") == {
        "types": [], "terrain_ids": [], "weapons": [], "screens": [],
    }


def test_hard_forecast_gate_requires_exact_payload_then_accepts_living_and_corpses():
    unknown = Board.from_bridge_data({
        "mission_id": "Mission_Piston", "tiles": [], "units": [_piston()],
    })
    block = _mission_piston_forecast_block(unknown, None)
    assert block["error"] == "RESEARCH_REQUIRED"
    assert block["non_overridable"] is True
    assert block["forecast_gaps"][0]["kind"] == "mission_piston_state_unknown"

    active = Board.from_bridge_data(_payload())
    assert _mission_piston_forecast_block(active, _payload()) is None

    corpse = Board.from_bridge_data(_payload(
        units=[_piston(hp=0)], actions=[],
    ))
    assert _mission_piston_forecast_block(corpse, None) is None

    empty = Board.from_bridge_data(_payload(units=[], actions=[]))
    assert _mission_piston_forecast_block(empty, None) is None


def test_lookahead_only_surfaces_missing_ordered_piston_state():
    kwargs = {"source_spawning_tiles": []}
    unknown = _lookahead_forecast_gaps(
        {"mission_id": "Mission_Piston", "units": []}, **kwargs,
    )
    assert unknown[0]["kind"] == "mission_piston_state_unknown"

    active = _lookahead_forecast_gaps(_payload(), **kwargs)
    assert active == []

    assert _lookahead_forecast_gaps(
        _payload(units=[], actions=[]), **kwargs,
    ) == []


def test_auto_turn_preserves_piston_research_gate_metadata(monkeypatch):
    session = RunSession(run_id="piston-auto", squad="Random", difficulty=0)
    gate = {
        "error": "RESEARCH_REQUIRED",
        "requires_research": True,
        "blocking": True,
        "non_overridable": True,
        "reason": "mission_piston_forecast_unproven",
        "forecast_gaps": [{"kind": "mission_piston_state_unknown"}],
    }
    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_post_enemy_block_result", lambda _session: None)
    monkeypatch.setattr(commands, "_read_save_file_difficulty", lambda _profile: None)
    monkeypatch.setattr(
        commands,
        "cmd_read",
        lambda **_kwargs: {
            "status": "OK",
            "phase": "combat_player",
            "active_mechs": 1,
            "turn": 2,
        },
    )
    monkeypatch.setattr(commands, "cmd_solve", lambda **_kwargs: dict(gate))

    result = commands.cmd_auto_turn(wait_for_turn=False)

    assert result["error"] == "Solve: RESEARCH_REQUIRED"
    assert result["requires_research"] is True
    assert result["non_overridable"] is True
    assert result["reason"] == "mission_piston_forecast_unproven"
    assert result["forecast_gaps"] == gate["forecast_gaps"]
    assert result["turn"] == 2


@pytest.mark.parametrize("command_name", ["cmd_click_end_turn", "cmd_end_turn"])
def test_public_end_turn_paths_block_unproven_piston_phase(
    monkeypatch, command_name,
):
    data = _payload(complete=False)
    data.update({
        "phase": "combat_player",
        "in_active_mission": True,
        "turn": 2,
    })
    board = Board.from_bridge_data(data)
    session = RunSession(run_id="piston-held", squad="Random", difficulty=0)
    session.current_mission = "Mission_Piston"

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_post_enemy_block_result", lambda _session: None)
    monkeypatch.setattr(commands, "_refresh_end_turn_bridge_state", lambda: True)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: (board, data))
    monkeypatch.setattr(
        commands, "_enrich_bridge_mech_weapons_from_save", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        commands,
        "_enrich_bridge_limited_mission_weapons_from_save",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        commands,
        "plan_end_turn",
        lambda: (_ for _ in ()).throw(AssertionError("must not plan End Turn")),
    )
    monkeypatch.setattr(
        commands,
        "execute_bridge_end_turn",
        lambda: (_ for _ in ()).throw(AssertionError("must not dispatch End Turn")),
    )

    result = getattr(commands, command_name)()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "held_end_turn_mission_piston_unproven"
    assert result["piston_forecast"]["non_overridable"] is True
    assert result["piston_forecast"]["forecast_gaps"][0]["kind"] == (
        "mission_piston_state_unknown"
    )
