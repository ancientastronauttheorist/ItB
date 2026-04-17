"""Tests for Support_Repair (Repair Drop).

Covers the heal-all semantics derived from the game's Lua source
(`weapons_support.lua` — `Support_Repair`, ZONE_ALL, SpaceDamage(-10)):

- Heals every TEAM_PLAYER pawn to max_hp in a single cast.
- Clears fire, acid, and frozen on each healed unit.
- Revives disabled mechs (hp<=0) to max_hp.
- Does NOT touch enemies or their statuses.
- Does NOT extinguish a burning tile under a healed unit.
- Deduplicates multi-tile pawns (Dam_Pawn) by uid so they heal once.
"""

from __future__ import annotations

from src.model.board import Board, Unit
from src.solver.simulate import simulate_weapon
from src.model.weapons import get_weapon_def


def _mech(uid, x, y, hp=3, max_hp=3, weapon="", fire=False, acid=False, frozen=False):
    return Unit(
        uid=uid, type=f"Mech{uid}", x=x, y=y, hp=hp, max_hp=max_hp,
        team=1, is_mech=True, move_speed=3, flying=False, massive=False,
        armor=False, pushable=True, weapon=weapon, weapon2="", active=True,
        fire=fire, acid=acid, frozen=frozen,
    )


def _enemy(uid, x, y, hp=2, fire=False):
    return Unit(
        uid=uid, type=f"Enemy{uid}", x=x, y=y, hp=hp, max_hp=hp,
        team=6, is_mech=False, move_speed=3, flying=False, massive=False,
        armor=False, pushable=True, weapon="", weapon2="", active=False,
        fire=fire,
    )


def _board(*units):
    b = Board()
    b.units = list(units)
    return b


def test_weapon_def_registered():
    wdef = get_weapon_def("Support_Repair")
    assert wdef is not None
    assert wdef.weapon_type == "heal_all"
    assert wdef.limited == 1
    assert wdef.targets_allies is True
    assert wdef.building_damage is False


def test_heals_damaged_mechs_and_clears_statuses():
    caster = _mech(1, 3, 3)
    ally1 = _mech(2, 4, 3, hp=1, max_hp=3, fire=True)
    ally2 = _mech(3, 5, 3, hp=3, max_hp=3, acid=True, frozen=True)
    enemy = _enemy(99, 6, 3, hp=2, fire=True)
    board = _board(caster, ally1, ally2, enemy)

    simulate_weapon(board, caster, "Support_Repair", 3, 3)

    assert ally1.hp == 3
    assert not ally1.fire
    assert not ally2.acid
    assert not ally2.frozen
    # Enemy untouched
    assert enemy.hp == 2
    assert enemy.fire is True


def test_revives_disabled_mech():
    # A disabled mech (hp=0) sits as a wreck. Another mech's Repair Drop
    # brings it back to full HP — matching the Steam-forum consensus that
    # the disabled mech itself cannot cast it, but an ally can revive it.
    caster = _mech(1, 3, 3)
    disabled = _mech(2, 4, 3, hp=0, max_hp=3)
    board = _board(caster, disabled)

    simulate_weapon(board, caster, "Support_Repair", 3, 3)

    assert disabled.hp == 3


def test_does_not_affect_buildings_or_terrain_fire():
    caster = _mech(1, 3, 3)
    ally = _mech(2, 4, 3, hp=1, max_hp=3, fire=True)
    board = _board(caster, ally)
    # Damaged building and burning tile — both should remain unchanged.
    board.tile(5, 5).terrain = "building"
    board.tile(5, 5).building_hp = 1
    board.tile(4, 3).on_fire = True

    simulate_weapon(board, caster, "Support_Repair", 3, 3)

    assert ally.hp == 3 and not ally.fire
    assert board.tile(5, 5).building_hp == 1
    assert board.tile(4, 3).on_fire is True


def test_dedupe_multi_tile_pawn():
    # Dam_Pawn / Train_Pawn: bridge emits one entry per occupied tile
    # sharing a uid. The heal must only hit each uid once (no double-add).
    caster = _mech(1, 3, 3)
    dam_a = Unit(
        uid=42, type="Dam_Pawn", x=5, y=0, hp=2, max_hp=4,
        team=1, is_mech=False, move_speed=0, flying=False, massive=True,
        armor=False, pushable=False, weapon="", weapon2="", active=False,
    )
    dam_b = Unit(
        uid=42, type="Dam_Pawn", x=5, y=1, hp=2, max_hp=4,
        team=1, is_mech=False, move_speed=0, flying=False, massive=True,
        armor=False, pushable=False, weapon="", weapon2="", active=False,
        is_extra_tile=True,
    )
    board = _board(caster, dam_a, dam_b)

    simulate_weapon(board, caster, "Support_Repair", 3, 3)

    # Both entries get the heal applied (hp set to max_hp), but the loop
    # doesn't visit the duplicate uid twice — verify via the events log.
    # The simpler observable: first-hit entry at max_hp, second still stale.
    assert dam_a.hp == 4
    # dam_b was skipped by the dedup guard — still at pre-heal value.
    assert dam_b.hp == 2
