"""Sim v37 LEADER_SPIDER (Jelly_Spider1) aura tests.

While Spider Psion alive: every Vek that dies leaves a SpiderEgg
(WebbEgg1) on its tile. The egg-hatch logic (per
`project_egg_spawn_sim`) turns it into a Spiderling at the next enemy
phase. Excludes the Psion itself.

Lua source: `advanced/ae_pawns.lua:276-295` + `advanced/ae_text.lua:9-11`.

Behavior under test:
  1. Vek dying with Spider Psion alive → WebbEgg1 spawns at the tile.
  2. Vek dying WITHOUT Spider Psion → no egg spawn (baseline).
  3. Python mirror exposes spider_psion_active flag.
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


def _unit_at(post, x, y):
    """Find any (alive) unit at coords, returning the first match."""
    for u in post["board"]["units"]:
        if u["x"] == x and u["y"] == y and u["hp"] > 0:
            return u
    return None


def _find_unit(post, uid):
    return next((u for u in post["board"]["units"] if u["uid"] == uid), None)


def _mech(uid, x, y, hp=3):
    return {
        "uid": uid, "type": "PunchMech", "x": x, "y": y, "hp": hp,
        "max_hp": hp, "team": 1, "mech": True, "move": 0, "active": True,
        "weapons": ["Prime_Punchmech"],
    }


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_vek_death_with_spider_psion_spawns_egg():
    # Spider Psion + a Scorpion at hp=1 dying via lethal env_danger.
    # Result: WebbEgg1 should appear at scorp's tile.
    spider_psion = {
        "uid": 1, "type": "Jelly_Spider1", "x": 7, "y": 0, "hp": 2,
        "max_hp": 2, "team": 6, "mech": False, "move": 2, "active": False,
        "weapons": [], "flying": True,
    }
    scorp = {
        "uid": 2, "type": "Scorpion1", "x": 4, "y": 4, "hp": 1,
        "max_hp": 2, "team": 6, "mech": False, "move": 3, "active": False,
        "weapons": [],
    }
    b = _base_board([_mech(0, 7, 7), spider_psion, scorp])
    b["environment_danger_v2"] = [[4, 4, 1, 1, 0]]
    post = _project(b, [])
    # Scorp should be dead (filtered from output).
    s = _find_unit(post, 2)
    assert s is None, f"Scorp should be dead/removed, got {s}"
    # WebbEgg1 should have spawned at (4, 4).
    tile_unit = _unit_at(post, 4, 4)
    assert tile_unit is not None, "Expected egg at scorp's tile"
    assert "WebbEgg" in tile_unit["type"] or "Egg" in tile_unit["type"], (
        f"Expected SpiderEgg/WebbEgg at scorp's tile, got {tile_unit}"
    )


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_vek_death_without_spider_psion_no_egg():
    # Baseline: Scorpion dies the same way without Spider Psion → tile empty.
    scorp = {
        "uid": 2, "type": "Scorpion1", "x": 4, "y": 4, "hp": 1,
        "max_hp": 2, "team": 6, "mech": False, "move": 3, "active": False,
        "weapons": [],
    }
    b = _base_board([_mech(0, 7, 7), scorp])
    b["environment_danger_v2"] = [[4, 4, 1, 1, 0]]
    post = _project(b, [])
    s = _find_unit(post, 2)
    assert s is None, f"Scorp should be dead/removed, got {s}"
    # No live unit should occupy (4, 4).
    tile_unit = _unit_at(post, 4, 4)
    assert tile_unit is None, (
        f"Expected NO egg/spawn without Spider Psion, got {tile_unit}"
    )


def test_python_board_mirror_has_spider_psion_field():
    """Python Board mirror exposes spider_psion_active for parity."""
    from src.model.board import Board
    b = Board()
    assert hasattr(b, "spider_psion_active")
    assert b.spider_psion_active is False


def test_python_board_mirror_detects_spider_psion():
    """from_bridge_data sets spider_psion_active when Jelly_Spider1 is alive."""
    from src.model.board import Board
    data = {
        "grid_power": 5, "grid_power_max": 7, "turn": 1, "total_turns": 5,
        "tiles": [],
        "units": [
            {"uid": 1, "type": "Jelly_Spider1", "x": 0, "y": 0, "hp": 2,
             "max_hp": 2, "team": 6, "mech": False, "move": 2,
             "active": False},
        ],
        "spawning_tiles": [],
    }
    board = Board.from_bridge_data(data)
    assert board.spider_psion_active is True


def test_eval_weights_has_psion_spider():
    """psion_spider weight is mirrored in Python EvalWeights."""
    from src.solver.evaluate import EvalWeights
    w = EvalWeights()
    assert hasattr(w, "psion_spider")
    assert w.psion_spider == 2200


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_spider_psion_egg_does_not_hatch_in_same_enemy_phase():
    """Sim v38: Vek dying mid-enemy-phase via env_danger → egg spawned, but
    NOT hatched in the same phase.

    Pre-v38: on_enemy_death's spawn_enemy fired immediately, then enemy.rs's
    hatch loop transformed the just-placed WebbEgg1 into a Spiderling1
    before the phase returned. That mismatched the game's
    AddQueuedDamage-based hatch (weapons_enemy.lua:857), which defers
    hatching to the NEXT enemy phase.

    v38 fix: spawn is deferred via Board.pending_spider_eggs and drained
    AFTER the hatch loop. Result: a WebbEgg1 must remain on the tile
    after this single enemy phase resolves.
    """
    spider_psion = {
        "uid": 1, "type": "Jelly_Spider1", "x": 7, "y": 0, "hp": 2,
        "max_hp": 2, "team": 6, "mech": False, "move": 2, "active": False,
        "weapons": [], "flying": True,
    }
    scorp = {
        "uid": 2, "type": "Scorpion1", "x": 4, "y": 4, "hp": 1,
        "max_hp": 2, "team": 6, "mech": False, "move": 3, "active": False,
        "weapons": [],
    }
    b = _base_board([_mech(0, 7, 7), spider_psion, scorp])
    # Lethal env_danger at scorp's tile triggers the on_enemy_death egg
    # spawn DURING the enemy phase. Pre-v38 the egg would hatch into a
    # Spiderling1 in the same phase; post-v38 it stays an egg.
    b["environment_danger_v2"] = [[4, 4, 1, 1, 0]]
    post = _project(b, [])
    tile_unit = _unit_at(post, 4, 4)
    assert tile_unit is not None, "Expected egg/spawn at scorp's tile"
    assert "Egg" in tile_unit["type"], (
        f"Egg must NOT hatch in the same enemy phase as spawn (v38). "
        f"Got type={tile_unit['type']}"
    )
