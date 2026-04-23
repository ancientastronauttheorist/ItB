"""Tests for push mechanics in Into the Breach.

Game rules (from CLAUDE.md Core Game Rules):
- Push moves a unit 1 tile in a direction
- If blocked (unit, mountain, building, edge): pushed unit takes 1 bump damage
- If blocked by another unit: BOTH units take 1 bump damage, neither moves
- Push/bump damage ignores Armor and ACID
- Water and Chasm kill non-flying ground units
- Lava kills like water but also sets flying units on Fire
- Mountains have 2 HP and take 1 damage when bumped into
- Buildings do NOT take damage from push collisions
- There is NO chain pushing: A pushed into B = collision, B stays
"""

from __future__ import annotations

import pytest
from src.model.board import Board, Unit, BoardTile
from src.solver.simulate import apply_push, apply_damage, ActionResult


def _make_unit(uid, x, y, hp=5, team=6, pushable=True, is_mech=False,
               flying=False, armor=False, utype="Scorpion"):
    return Unit(
        uid=uid, type=utype, x=x, y=y, hp=hp, max_hp=hp,
        team=team, is_mech=is_mech, move_speed=3, flying=flying,
        massive=False, armor=armor, pushable=pushable,
        weapon="", weapon2="", active=True,
    )


def _make_board_with_units(*units):
    board = Board()
    for u in units:
        board.units.append(u)
    return board


# ---------- Basic Push ----------

class TestBasicPush:
    def test_push_into_empty(self):
        """Basic push into empty tile: unit moves, no damage."""
        u = _make_unit(1, 3, 3)
        board = _make_board_with_units(u)
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)  # push East
        assert u.x == 4 and u.y == 3
        assert u.hp == 5  # no damage

    def test_push_north(self):
        """Push in North direction."""
        u = _make_unit(1, 3, 3)
        board = _make_board_with_units(u)
        result = ActionResult()
        apply_push(board, 3, 3, 0, result)  # push North
        assert u.x == 3 and u.y == 4

    def test_push_south(self):
        """Push in South direction."""
        u = _make_unit(1, 3, 3)
        board = _make_board_with_units(u)
        result = ActionResult()
        apply_push(board, 3, 3, 2, result)  # push South
        assert u.x == 3 and u.y == 2

    def test_push_west(self):
        """Push in West direction."""
        u = _make_unit(1, 3, 3)
        board = _make_board_with_units(u)
        result = ActionResult()
        apply_push(board, 3, 3, 3, result)  # push West
        assert u.x == 2 and u.y == 3

    def test_non_pushable_non_mech_immune(self):
        """Non-pushable, non-mech unit is completely immune to push."""
        psion = _make_unit(1, 3, 3, pushable=False, is_mech=False, utype="Psion")
        board = _make_board_with_units(psion)
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert psion.x == 3 and psion.hp == 5  # unchanged

    def test_mech_always_pushable(self):
        """Mechs can always be pushed, even if pushable=False (massive)."""
        mech = _make_unit(1, 3, 3, team=1, is_mech=True, pushable=False)
        board = _make_board_with_units(mech)
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert mech.x == 4 and mech.y == 3


# ---------- Bump Damage (Blocked Push) ----------

class TestBumpDamage:
    def test_bump_against_edge(self):
        """Push into map edge: 1 bump damage, no movement."""
        u = _make_unit(1, 7, 3, hp=5)
        board = _make_board_with_units(u)
        result = ActionResult()
        apply_push(board, 7, 3, 1, result)  # push East off edge
        assert u.hp == 4
        assert u.x == 7  # didn't move

    def test_bump_against_mountain(self):
        """Push into mountain: 1 bump to pushed unit, mountain takes 1 damage."""
        u = _make_unit(1, 3, 3, hp=5)
        board = _make_board_with_units(u)
        board.tile(4, 3).terrain = "mountain"
        board.tile(4, 3).building_hp = 2  # mountains have 2 HP
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert u.hp == 4  # 1 bump damage
        assert u.x == 3   # didn't move
        assert board.tile(4, 3).building_hp == 1  # mountain damaged
        assert board.tile(4, 3).terrain == "mountain"  # still standing

    def test_bump_destroys_mountain(self):
        """Push into 1-HP mountain: mountain becomes rubble."""
        u = _make_unit(1, 3, 3, hp=5)
        board = _make_board_with_units(u)
        board.tile(4, 3).terrain = "mountain"
        board.tile(4, 3).building_hp = 1  # already damaged
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert u.hp == 4
        assert board.tile(4, 3).terrain == "rubble"

    def test_bump_against_building(self):
        """Push into non-unique multi-HP building: unit takes bump, building
        loses 1 HP but grid_power is unchanged (non-unique buildings
        contribute exactly 1 grid regardless of HP — grid only drops on
        full destruction).

        Regression: grid_drop_20260421_161809_372_t02_a0 (Taurus Cannon push
        into bhp=2 Residential: actual bhp 2→1 with grid preserved).
        """
        u = _make_unit(1, 3, 3, hp=5)
        board = _make_board_with_units(u)
        board.tile(4, 3).terrain = "building"
        board.tile(4, 3).building_hp = 2
        board.grid_power = 7
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert u.hp == 4  # bump damage
        assert u.x == 3   # didn't move
        assert board.tile(4, 3).building_hp == 1  # building takes 1 bump damage
        # Non-unique building damaged but not destroyed → grid unchanged.
        assert board.grid_power == 7

    def test_bump_destroys_1hp_building_drops_grid(self):
        """Bumping a 1-HP building destroys it and drops grid by 1."""
        u = _make_unit(1, 3, 3, hp=5)
        board = _make_board_with_units(u)
        board.tile(4, 3).terrain = "building"
        board.tile(4, 3).building_hp = 1
        board.grid_power = 7
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert u.hp == 4
        assert board.tile(4, 3).building_hp == 0
        assert board.tile(4, 3).terrain == "rubble"
        assert board.grid_power == 6

    def test_bump_against_unique_2hp_building_drops_grid_per_hp(self):
        """Unique objective buildings lose 1 grid per HP (each HP is worth a
        grid power reward)."""
        u = _make_unit(1, 3, 3, hp=5)
        board = _make_board_with_units(u)
        board.tile(4, 3).terrain = "building"
        board.tile(4, 3).building_hp = 2
        board.tile(4, 3).unique_building = True
        board.grid_power = 7
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert u.hp == 4
        assert board.tile(4, 3).building_hp == 1
        assert board.tile(4, 3).terrain == "building"  # unique stays "building"
        assert board.grid_power == 6  # unique: grid -1 per HP

    def test_bump_against_unit_both_take_damage(self):
        """Push A into B: BOTH take 1 bump damage, neither moves."""
        a = _make_unit(1, 3, 3, hp=5)
        b = _make_unit(2, 4, 3, hp=5)
        board = _make_board_with_units(a, b)
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert a.hp == 4 and b.hp == 4  # both took 1 bump
        assert a.x == 3 and b.x == 4   # neither moved

    def test_bump_against_unpushable_unit(self):
        """Push into non-pushable unit (Psion): both take 1 bump damage."""
        a = _make_unit(1, 3, 3, hp=5)
        psion = _make_unit(2, 4, 3, hp=5, pushable=False, is_mech=False,
                           utype="Psion")
        board = _make_board_with_units(a, psion)
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert a.hp == 4 and psion.hp == 4
        assert a.x == 3 and psion.x == 4

    def test_bump_kills_1hp_unit(self):
        """Bump damage can kill a 1 HP unit."""
        u = _make_unit(1, 7, 3, hp=1)
        board = _make_board_with_units(u)
        result = ActionResult()
        apply_push(board, 7, 3, 1, result)
        assert u.hp == 0
        assert result.enemies_killed == 1


# ---------- Bump Damage vs Armor ----------

class TestBumpIgnoresArmor:
    def test_bump_ignores_armor_edge(self):
        """Bump damage from edge push ignores Armor."""
        u = _make_unit(1, 7, 3, hp=5, armor=True)
        board = _make_board_with_units(u)
        result = ActionResult()
        apply_push(board, 7, 3, 1, result)
        assert u.hp == 4  # took 1 damage despite Armor

    def test_bump_ignores_armor_unit_collision(self):
        """Bump damage from unit collision ignores Armor on both."""
        a = _make_unit(1, 3, 3, hp=5, armor=True)
        b = _make_unit(2, 4, 3, hp=5, armor=True)
        board = _make_board_with_units(a, b)
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert a.hp == 4 and b.hp == 4  # both took full 1 damage

    def test_normal_damage_reduced_by_armor(self):
        """Verify that normal weapon damage IS reduced by Armor."""
        u = _make_unit(1, 3, 3, hp=5, armor=True)
        board = _make_board_with_units(u)
        result = ActionResult()
        apply_damage(board, 3, 3, 2, result)  # normal weapon damage
        assert u.hp == 4  # 2 damage - 1 armor = 1 actual


# ---------- Deadly Terrain ----------

class TestDeadlyTerrain:
    def test_push_into_water_kills_ground(self):
        """Ground unit pushed into water dies."""
        u = _make_unit(1, 3, 3, hp=5)
        board = _make_board_with_units(u)
        board.tile(4, 3).terrain = "water"
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert u.hp == 0
        assert result.enemies_killed == 1

    def test_push_into_chasm_kills_ground(self):
        """Ground unit pushed into chasm dies."""
        u = _make_unit(1, 3, 3, hp=5)
        board = _make_board_with_units(u)
        board.tile(4, 3).terrain = "chasm"
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert u.hp == 0
        assert result.enemies_killed == 1

    def test_push_into_lava_kills_ground(self):
        """Ground unit pushed into lava dies."""
        u = _make_unit(1, 3, 3, hp=5)
        board = _make_board_with_units(u)
        board.tile(4, 3).terrain = "lava"
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert u.hp == 0
        assert result.enemies_killed == 1

    def test_flying_survives_water(self):
        """Flying unit pushed into water survives."""
        flyer = _make_unit(1, 3, 3, hp=5, flying=True)
        board = _make_board_with_units(flyer)
        board.tile(4, 3).terrain = "water"
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert flyer.x == 4 and flyer.hp == 5

    def test_flying_survives_chasm(self):
        """Flying unit pushed into chasm survives."""
        flyer = _make_unit(1, 3, 3, hp=5, flying=True)
        board = _make_board_with_units(flyer)
        board.tile(4, 3).terrain = "chasm"
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert flyer.x == 4 and flyer.hp == 5

    def test_flying_survives_lava(self):
        """Flying unit pushed into lava survives (should set fire, TODO)."""
        flyer = _make_unit(1, 3, 3, hp=5, flying=True)
        board = _make_board_with_units(flyer)
        board.tile(4, 3).terrain = "lava"
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert flyer.x == 4 and flyer.hp == 5
        # TODO: flying units over lava should be set on Fire


# ---------- No Chain Push ----------

class TestNoChainPush:
    """Verify that chain pushing does NOT happen.
    A pushed into B = collision (both take bump), B does NOT move.
    """

    def test_push_into_unit_is_collision(self):
        """A pushed into B: both take bump, neither moves."""
        a = _make_unit(1, 3, 3, hp=5)
        b = _make_unit(2, 4, 3, hp=5)
        board = _make_board_with_units(a, b)
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert a.x == 3 and a.y == 3  # A didn't move
        assert b.x == 4 and b.y == 3  # B didn't move
        assert a.hp == 4  # A took bump
        assert b.hp == 4  # B took bump

    def test_no_chain_even_with_space_behind(self):
        """Even if there's space behind B, B does NOT move when A bumps it."""
        a = _make_unit(1, 3, 3, hp=5)
        b = _make_unit(2, 4, 3, hp=5)
        # tile (5,3) is empty — but B should NOT be pushed there
        board = _make_board_with_units(a, b)
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert b.x == 4  # B stayed put
        assert a.x == 3  # A stayed put

    def test_no_chain_into_water(self):
        """A pushed into B with water behind: B does NOT get pushed into water."""
        a = _make_unit(1, 3, 3, hp=5)
        b = _make_unit(2, 4, 3, hp=5)
        board = _make_board_with_units(a, b)
        board.tile(5, 3).terrain = "water"
        result = ActionResult()
        apply_push(board, 3, 3, 1, result)
        assert b.hp == 4   # B took bump damage only
        assert b.x == 4    # B did NOT move into water
        assert a.x == 3    # A didn't move either
