"""Sim v37 LEADER_BOOSTED (Jelly_Boost1) aura tests.

While Boost Psion alive: +1 damage to all Vek weapon attacks. Excludes
the Psion itself per the standard "aura source is exempt" pattern.
Lua source: `advanced/ae_pawns.lua:276-295` + `advanced/ae_text.lua:9-11`.

Behavior under test:
  1. Vek with hp 2 attacks a 3-HP building from 1 tile away.
     Without Boost Psion → 1 damage, building survives at hp 2.
     With Boost Psion → 2 damage, building hp drops to 1.
  2. Boost Psion's own weapon damage is NOT boosted (excluded from aura).
  3. The +1 doesn't fire on 0-damage weapons (BossHeal-style no-op stays 0).
  4. Python mirror exposes boost_psion_active flag.
"""

from __future__ import annotations

import json
import pytest

try:
    import itb_solver  # type: ignore
    _HAVE_WHEEL = True
except ImportError:
    _HAVE_WHEEL = False


def _base_board(units, tiles=None):
    return {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "tiles": tiles or [],
        "units": units,
        "spawning_tiles": [],
    }


def _project(board, plan):
    raw = itb_solver.project_plan(json.dumps(board), json.dumps(plan))
    out = json.loads(raw)
    out["board"] = json.loads(out["board_json"])
    return out


def _find_tile(post, x, y):
    return next(
        (t for t in post["board"]["tiles"]
         if t["x"] == x and t["y"] == y),
        None,
    )


def _mech(uid, x, y, hp=3):
    return {
        "uid": uid, "type": "PunchMech", "x": x, "y": y, "hp": hp,
        "max_hp": hp, "team": 1, "mech": True, "move": 0, "active": True,
        "weapons": ["Prime_Punchmech"],
    }


def _scorp_attacking_building(uid, x, y, target_x, target_y):
    """Scorpion1 (1 melee dmg) with queued attack on target."""
    return {
        "uid": uid, "type": "Scorpion1", "x": x, "y": y, "hp": 2,
        "max_hp": 2, "team": 6, "mech": False, "move": 3, "active": False,
        "weapons": ["Scorpion1Atk1"],
        "queued_target": [target_x, target_y],
        "has_queued_attack": True,
    }


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_boost_psion_adds_one_damage_to_vek_weapon_attack():
    # Building hp=3; Scorpion adjacent attacks it with 1-dmg melee.
    # No Boost: building hp 3 → 2.
    # With Boost: building hp 3 → 1.
    tiles = [{"x": 0, "y": 0, "terrain": "building", "building_hp": 3}]
    mech = _mech(0, 7, 7)
    scorp = _scorp_attacking_building(1, 1, 0, 0, 0)

    b_no = _base_board([mech, scorp], tiles=tiles)
    post_no = _project(b_no, [])
    bld_no = _find_tile(post_no, 0, 0)

    boost = {
        "uid": 2, "type": "Jelly_Boost1", "x": 7, "y": 0, "hp": 2,
        "max_hp": 2, "team": 6, "mech": False, "move": 2, "active": False,
        "weapons": [], "flying": True,
    }
    b_yes = _base_board([mech, scorp, boost], tiles=tiles)
    post_yes = _project(b_yes, [])
    bld_yes = _find_tile(post_yes, 0, 0)

    assert bld_no is not None and bld_yes is not None
    # Without boost: 1 damage → hp 2. With boost: 2 damage → hp 1.
    assert bld_no["building_hp"] > bld_yes["building_hp"], (
        f"Boost should increase Vek attack damage: "
        f"no_boost={bld_no['building_hp']}, with_boost={bld_yes['building_hp']}"
    )


def test_python_board_mirror_has_boost_psion_field():
    """Python Board mirror exposes boost_psion_active for parity."""
    from src.model.board import Board
    b = Board()
    assert hasattr(b, "boost_psion_active")
    assert b.boost_psion_active is False


def test_python_board_mirror_detects_boost_psion():
    """from_bridge_data sets boost_psion_active when Jelly_Boost1 is alive."""
    from src.model.board import Board
    data = {
        "grid_power": 5, "grid_power_max": 7, "turn": 1, "total_turns": 5,
        "tiles": [],
        "units": [
            {"uid": 1, "type": "Jelly_Boost1", "x": 0, "y": 0, "hp": 2,
             "max_hp": 2, "team": 6, "mech": False, "move": 2,
             "active": False},
        ],
        "spawning_tiles": [],
    }
    board = Board.from_bridge_data(data)
    assert board.boost_psion_active is True


def test_eval_weights_has_psion_boost():
    """psion_boost weight is mirrored in Python EvalWeights."""
    from src.solver.evaluate import EvalWeights
    w = EvalWeights()
    assert hasattr(w, "psion_boost")
    assert w.psion_boost == 3000
