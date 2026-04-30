"""Sim v37 LEADER_FIRE (Jelly_Fire1) aura tests.

Two parts:
  1. Fire immunity: while Fire Psion alive, Vek don't take fire damage
     and don't gain Fire status.
  2. On-death fire: when a Vek dies (any cause, except the Psion itself),
     the tile catches fire.

Lua source: `advanced/ae_pawns.lua:276-295` + `advanced/ae_text.lua:9-11`.

Behavior under test:
  1. Burning Vek with Fire Psion alive → fire-tick deals 0 damage.
  2. Burning Vek WITHOUT Fire Psion → fire-tick deals 1 damage.
  3. Vek dying via fire-tick (Fire Psion absent) → leaves fire on tile.
  4. Python mirror exposes fire_psion_active flag.
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


def _find_unit(post, uid):
    return next((u for u in post["board"]["units"] if u["uid"] == uid), None)


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


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_burning_vek_takes_no_damage_with_fire_psion():
    # Burning Scorpion + Fire Psion: fire-tick should NOT damage scorp.
    fire_psion = {
        "uid": 1, "type": "Jelly_Fire1", "x": 7, "y": 0, "hp": 2,
        "max_hp": 2, "team": 6, "mech": False, "move": 2, "active": False,
        "weapons": [], "flying": True,
    }
    scorp = {
        "uid": 2, "type": "Scorpion1", "x": 4, "y": 4, "hp": 2,
        "max_hp": 2, "team": 6, "mech": False, "move": 3, "active": False,
        "weapons": [], "fire": True,
    }
    b = _base_board([_mech(0, 7, 7), fire_psion, scorp])
    post = _project(b, [])
    s = _find_unit(post, 2)
    assert s is not None
    # Scorpion should keep its hp (Fire Psion blocks fire damage).
    assert s["hp"] == 2, f"Scorp should be immune to fire damage, got {s}"


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_burning_vek_takes_damage_without_fire_psion():
    # Baseline: burning Scorpion WITHOUT Fire Psion — fire-tick damages it.
    scorp = {
        "uid": 2, "type": "Scorpion1", "x": 4, "y": 4, "hp": 2,
        "max_hp": 2, "team": 6, "mech": False, "move": 3, "active": False,
        "weapons": [], "fire": True,
    }
    b = _base_board([_mech(0, 7, 7), scorp])
    post = _project(b, [])
    s = _find_unit(post, 2)
    assert s is not None
    assert s["hp"] == 1, f"Burning scorp should take 1 fire dmg, got {s}"


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_vek_death_with_fire_psion_creates_fire_on_tile():
    # Fire Psion alive + a Scorpion at hp=1 dying via cracked-ground chasm.
    # We force the death via env_danger lethal at the scorp's tile.
    # Result: scorp's tile should be on fire (from the LEADER_FIRE aura).
    fire_psion = {
        "uid": 1, "type": "Jelly_Fire1", "x": 7, "y": 0, "hp": 2,
        "max_hp": 2, "team": 6, "mech": False, "move": 2, "active": False,
        "weapons": [], "flying": True,
    }
    scorp = {
        "uid": 2, "type": "Scorpion1", "x": 4, "y": 4, "hp": 1,
        "max_hp": 2, "team": 6, "mech": False, "move": 3, "active": False,
        "weapons": [],
    }
    b = _base_board([_mech(0, 7, 7), fire_psion, scorp])
    # Lethal env_danger at scorp's tile (kill_int=1) — scorp dies in env-tick.
    b["environment_danger_v2"] = [[4, 4, 1, 1, 0]]
    post = _project(b, [])
    s = _find_unit(post, 2)
    assert s is None, f"Scorp should be dead/removed, got {s}"
    tile = _find_tile(post, 4, 4)
    # The tile should have on_fire=True from LEADER_FIRE. board_to_json emits
    # `fire: true` (not `on_fire`) for tiles with the on_fire flag set.
    assert tile is not None and tile.get("fire", False), (
        f"Expected fire on tile after Vek death with Fire Psion, got {tile}"
    )


def test_python_board_mirror_has_fire_psion_field():
    """Python Board mirror exposes fire_psion_active for parity."""
    from src.model.board import Board
    b = Board()
    assert hasattr(b, "fire_psion_active")
    assert b.fire_psion_active is False


def test_python_board_mirror_detects_fire_psion():
    """from_bridge_data sets fire_psion_active when Jelly_Fire1 is alive."""
    from src.model.board import Board
    data = {
        "grid_power": 5, "grid_power_max": 7, "turn": 1, "total_turns": 5,
        "tiles": [],
        "units": [
            {"uid": 1, "type": "Jelly_Fire1", "x": 0, "y": 0, "hp": 2,
             "max_hp": 2, "team": 6, "mech": False, "move": 2,
             "active": False},
        ],
        "spawning_tiles": [],
    }
    board = Board.from_bridge_data(data)
    assert board.fire_psion_active is True


def test_eval_weights_has_psion_fire():
    """psion_fire weight is mirrored in Python EvalWeights."""
    from src.solver.evaluate import EvalWeights
    w = EvalWeights()
    assert hasattr(w, "psion_fire")
    assert w.psion_fire == 2200
