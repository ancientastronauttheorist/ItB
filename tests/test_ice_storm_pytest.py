"""Collected Ice Storm simulator regressions for the native Env_SnowStorm."""

import json

import itb_solver


def _board(*, units=None, tiles=None, freeze=None, danger=None):
    data = {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "tiles": tiles or [],
        "units": units or [],
        "spawning_tiles": [],
    }
    if freeze is not None:
        data["environment_freeze"] = freeze
    if danger is not None:
        data["environment_danger_v2"] = danger
    return data


def _project(board):
    result = json.loads(itb_solver.project_plan(json.dumps(board), "[]"))
    return json.loads(result["board_json"])


def _unit(board, uid):
    return next(unit for unit in board["units"] if unit["uid"] == uid)


def _tile(board, x, y):
    return next(tile for tile in board["tiles"] if tile["x"] == x and tile["y"] == y)


def _mech(**overrides):
    unit = {
        "uid": 0,
        "type": "PunchMech",
        "x": 7,
        "y": 7,
        "hp": 3,
        "max_hp": 3,
        "team": 1,
        "mech": True,
        "move": 0,
        "active": True,
        "weapons": ["Prime_Punchmech"],
    }
    unit.update(overrides)
    return unit


def test_ice_storm_freezes_mech_without_damage():
    post = _project(_board(units=[_mech(x=4, y=4)], freeze=[[4, 4]]))

    mech = _unit(post, 0)
    assert mech["hp"] == 3
    assert mech["frozen"] is True


def test_ice_storm_freezes_flying_enemy_and_cancels_attack():
    hornet = {
        "uid": 1,
        "type": "Hornet1",
        "x": 1,
        "y": 0,
        "hp": 2,
        "max_hp": 2,
        "team": 6,
        "mech": False,
        "flying": True,
        "move": 4,
        "active": False,
        "weapons": ["HornetAtk1"],
        "queued_target": [0, 0],
        "has_queued_attack": True,
    }
    post = _project(
        _board(
            units=[_mech(), hornet],
            tiles=[
                {"x": 0, "y": 0, "terrain": "building", "building_hp": 1},
            ],
            freeze=[[1, 0]],
        )
    )

    assert _unit(post, 1)["frozen"] is True
    assert _tile(post, 0, 0)["building_hp"] == 1


def test_ice_storm_freezes_building_without_grid_loss():
    post = _project(
        _board(
            units=[_mech()],
            tiles=[
                {"x": 3, "y": 3, "terrain": "building", "building_hp": 1},
            ],
            freeze=[[3, 3]],
        )
    )

    building = _tile(post, 3, 3)
    assert building["terrain"] == "building"
    assert building["building_hp"] == 1
    assert building["frozen"] is True
    assert post["grid_power"] == 5


def test_ice_storm_shield_blocks_freeze_and_is_consumed():
    post = _project(
        _board(
            units=[_mech(x=4, y=4, shield=True)],
            freeze=[[4, 4]],
        )
    )

    mech = _unit(post, 0)
    assert mech.get("shield", False) is False
    assert mech.get("frozen", False) is False
    assert mech["hp"] == 3


def test_nano_storm_remains_damage_without_freeze():
    post = _project(
        _board(
            units=[_mech(x=4, y=4, hp=2, max_hp=2)],
            danger=[[4, 4, 1, 0, 0]],
        )
    )

    mech = _unit(post, 0)
    assert mech["hp"] == 1
    assert mech.get("frozen", False) is False
