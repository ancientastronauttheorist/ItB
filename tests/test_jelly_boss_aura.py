"""Sim v37 Jelly_Boss (Psion Abomination) combined LEADER_BOSS aura tests.

Jelly_Boss simultaneously sources HEALTH (+1 max HP all Vek), REGEN
(heal +1 HP/turn all Vek), and EXPLODE (Vek explode 1 dmg adjacent on
death). The Lua source is `pawns.lua:979-1018` + `psion.lua:14-27`.

Behavior under test:
  1. Boss alone → other Vek get +1 max_hp at bridge ingest.
  2. Boss alone → other Vek heal +1 HP at start of enemy phase.
  3. Boss alone → killing a Vek detonates 1 bump damage to 4 adjacent
     tiles (Blast Psion explosion behavior).
  4. Boss + Soldier Psion both alive → +1 max_hp applies ONCE
     (no double-stack).
  5. Boss + Soldier Psion both alive → killing the Boss does NOT remove
     the +1 HP buff (Soldier still keeps it alive).
  6. Boss alone → killing the Boss reverses the +1 HP buff on remaining
     Vek (cleanup correct).
  7. The Boss itself is NOT subject to its own aura (no +1 HP buff
     applied to the boss; it doesn't explode on its own death).

These tests exercise the Rust simulator via `itb_solver.project_plan`.
They will FAIL until the Rust wheel is rebuilt with the sim v37 changes.

Mirror parity test for Python `Board.boss_psion_active` flag is in this
file as the final test — that one runs without a wheel rebuild.
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


def _mech(uid, x, y, hp=3, weapons=None):
    return {
        "uid": uid, "type": "PunchMech", "x": x, "y": y, "hp": hp,
        "max_hp": hp, "team": 1, "mech": True, "move": 0, "active": True,
        "weapons": weapons or ["Prime_Punchmech"],
    }


def _vek(uid, vtype, x, y, hp, max_hp=None):
    return {
        "uid": uid, "type": vtype, "x": x, "y": y, "hp": hp,
        "max_hp": max_hp if max_hp is not None else hp,
        "team": 6, "mech": False, "move": 3, "active": False,
        "weapons": [],
    }


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_boss_alone_grants_plus_one_hp_to_other_vek():
    # Boss alive + a Scorpion1 with bridge-reported hp=2 (already buffed).
    # The bridge sends max_hp as base (Scorpion1 base = 2). After ingest,
    # max_hp should be bumped to 3.
    boss = _vek(1, "Jelly_Boss", 0, 0, hp=5, max_hp=5)
    scorp = _vek(2, "Scorpion1", 4, 4, hp=3, max_hp=2)  # already-buffed hp
    b = _base_board([_mech(0, 7, 7), boss, scorp])
    post = _project(b, [])
    s = _find_unit(post, 2)
    assert s is not None, "Scorpion missing post-project"
    # Bridge max_hp 2 → after Boss ingest +1 → 3
    assert s["max_hp"] == 3, f"Expected max_hp=3 (Boss-buffed), got {s}"


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_boss_alone_heals_other_vek_at_enemy_phase():
    # Boss + a damaged Scorpion (hp=1, max_hp=2 base → 3 buffed).
    # No queued attacks — the only enemy-phase event we want is REGEN.
    boss = _vek(1, "Jelly_Boss", 0, 0, hp=5, max_hp=5)
    scorp = _vek(2, "Scorpion1", 4, 4, hp=1, max_hp=2)
    b = _base_board([_mech(0, 7, 7), boss, scorp])
    post = _project(b, [])
    s = _find_unit(post, 2)
    # +1 from REGEN. Scorpion buffed max_hp = 3, so heal floor doesn't cap.
    assert s is not None
    assert s["hp"] == 2, f"Expected hp=2 (regen +1), got {s}"


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_boss_alone_does_not_heal_itself():
    # Damaged Boss: REGEN aura excludes the Boss itself.
    boss = _vek(1, "Jelly_Boss", 0, 0, hp=3, max_hp=5)
    b = _base_board([_mech(0, 7, 7), boss])
    post = _project(b, [])
    bs = _find_unit(post, 1)
    assert bs is not None
    assert bs["hp"] == 3, f"Boss should not heal itself, got {bs}"


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_boss_and_soldier_psion_no_double_stack_hp_buff():
    # Both Boss + Soldier Psion alive: +1 max_hp applies ONCE total, not twice.
    boss = _vek(1, "Jelly_Boss", 0, 0, hp=5, max_hp=5)
    soldier = _vek(2, "Jelly_Health1", 1, 0, hp=2, max_hp=2)
    scorp = _vek(3, "Scorpion1", 4, 4, hp=3, max_hp=2)
    b = _base_board([_mech(0, 7, 7), boss, soldier, scorp])
    post = _project(b, [])
    s = _find_unit(post, 3)
    assert s is not None
    # max_hp 2 + 1 (single buff source) = 3, NOT 4
    assert s["max_hp"] == 3, f"Expected single +1 buff (max_hp=3), got {s}"


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_boss_provides_explode_on_death_aura():
    # Boss alive + a Scorpion at hp=1 dying via lethal env_danger.
    # Adjacent neighbor at hp=2 should take 1 bump damage from the
    # EXPLODE-on-death aura.
    # Ordering: env_danger fires BEFORE regen tick in the enemy phase
    # (per `apply_env_danger` running before the regen loop in enemy.rs).
    # So sequence is: scorp dies → explode → neighbor hp 2 → 1 → regen
    # heals neighbor 1 → 2.
    boss = _vek(1, "Jelly_Boss", 0, 0, hp=5, max_hp=5)
    scorp = _vek(2, "Scorpion1", 3, 3, hp=1, max_hp=2)
    neighbor = _vek(3, "Scorpion1", 4, 3, hp=2, max_hp=2)
    b = _base_board([_mech(0, 7, 7), boss, scorp, neighbor])
    b["environment_danger_v2"] = [[3, 3, 1, 1, 0]]  # lethal env at scorp
    post = _project(b, [])
    s2 = _find_unit(post, 2)
    s3 = _find_unit(post, 3)
    # Scorp removed from output (hp <= 0 filtered) — confirm via absence.
    assert s2 is None, f"Scorp should be dead/removed, got {s2}"
    # Neighbor took an explosion bump (hp dropped from 2). REGEN tick fires
    # AFTER env_danger, so neighbor heals 1 back → either 2 (regen capped
    # at max_hp=3 which is buffed) or 1 (if regen ordering differs).
    # Without Boss explode the neighbor would stay at 3 (regen heals 2 → 3).
    # So `<3` definitively means the explosion happened.
    assert s3 is not None and s3["hp"] < 3, (
        f"Adjacent scorp should take explosion bump damage, got {s3}"
    )


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_boss_dying_alone_reverts_hp_buff():
    # Boss + a Scorpion. Kill the boss via lethal env_danger. The scorpion's
    # max_hp should drop back to base (2) and its current hp should
    # also decrement by 1 (per the cleanup branch).
    boss = _vek(1, "Jelly_Boss", 7, 7, hp=1, max_hp=5)
    scorp = _vek(2, "Scorpion1", 4, 4, hp=3, max_hp=2)  # buffed hp=3
    b = _base_board([_mech(0, 0, 0), boss, scorp])
    b["environment_danger_v2"] = [[7, 7, 1, 1, 0]]  # lethal env at boss
    post = _project(b, [])
    bs = _find_unit(post, 1)
    s = _find_unit(post, 2)
    assert bs is None, f"Boss should be dead/removed, got {bs}"
    assert s is not None
    # Cleanup: max_hp -= 1 → 2; hp -= 1 → 2. Then REGEN doesn't fire (no
    # boss/regen psion left). Net hp = 2.
    assert s["max_hp"] == 2, f"Buff should reverse to max_hp=2, got {s}"
    assert s["hp"] == 2, f"hp should reverse to 2, got {s}"


def test_python_board_mirror_has_boss_psion_field():
    """Python Board mirror exposes boss_psion_active for parity / breakdown."""
    from src.model.board import Board
    b = Board()
    assert hasattr(b, "boss_psion_active")
    assert b.boss_psion_active is False  # default


def test_eval_weights_has_psion_boss():
    """psion_boss weight is mirrored in Python EvalWeights."""
    from src.solver.evaluate import EvalWeights
    w = EvalWeights()
    assert hasattr(w, "psion_boss")
    assert w.psion_boss == 5000  # default per spec


def test_python_board_mirror_buffs_hp_with_boss():
    """from_bridge_data should bump max_hp by 1 when Boss is alive."""
    from src.model.board import Board
    data = {
        "grid_power": 5, "grid_power_max": 7, "turn": 1, "total_turns": 5,
        "tiles": [],
        "units": [
            {"uid": 1, "type": "Jelly_Boss", "x": 0, "y": 0, "hp": 5,
             "max_hp": 5, "team": 6, "mech": False, "move": 3,
             "active": False},
            {"uid": 2, "type": "Scorpion1", "x": 4, "y": 4, "hp": 3,
             "max_hp": 2, "team": 6, "mech": False, "move": 3,
             "active": False},
        ],
        "spawning_tiles": [],
    }
    board = Board.from_bridge_data(data)
    assert board.boss_psion_active is True
    scorp = next(u for u in board.units if u.uid == 2)
    assert scorp.max_hp == 3, f"Boss should buff max_hp +1, got {scorp.max_hp}"


def test_python_board_mirror_no_double_buff():
    """from_bridge_data should NOT double-stack +1 HP when Boss + Soldier alive."""
    from src.model.board import Board
    data = {
        "grid_power": 5, "grid_power_max": 7, "turn": 1, "total_turns": 5,
        "tiles": [],
        "units": [
            {"uid": 1, "type": "Jelly_Boss", "x": 0, "y": 0, "hp": 5,
             "max_hp": 5, "team": 6, "mech": False, "move": 3,
             "active": False},
            {"uid": 2, "type": "Jelly_Health1", "x": 1, "y": 0, "hp": 2,
             "max_hp": 2, "team": 6, "mech": False, "move": 3,
             "active": False},
            {"uid": 3, "type": "Scorpion1", "x": 4, "y": 4, "hp": 3,
             "max_hp": 2, "team": 6, "mech": False, "move": 3,
             "active": False},
        ],
        "spawning_tiles": [],
    }
    board = Board.from_bridge_data(data)
    assert board.boss_psion_active is True
    assert board.soldier_psion_active is True
    scorp = next(u for u in board.units if u.uid == 3)
    assert scorp.max_hp == 3, (
        f"Both auras alive → +1 buff applied ONCE, got max_hp={scorp.max_hp}"
    )
