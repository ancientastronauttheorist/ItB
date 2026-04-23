"""Tests for Python ``_sim_leap`` smoke emission parity with Rust.

Matches ``rust_solver/src/simulate.rs`` commit 37fbcb4: Aerial Bombs
(``Brute_Jetmech``, the only SMOKE-flagged leap weapon in the registry)
drops smoke along the cardinal flight path — strictly between source
and landing tile — not on the landing tile itself. Other leap weapons
(``Prime_Leap``, ``Brute_Bombrun``) have no smoke flag and must not
emit smoke at all.

Gated on ``WeaponDef.smoke`` in ``src/model/weapons.py``.
"""

from __future__ import annotations

from src.model.board import Board, Unit
from src.model.weapons import get_weapon_def
from src.solver.simulate import simulate_weapon


def _jet(uid: int, x: int, y: int) -> Unit:
    """Jet Mech caster for Aerial Bombs (Brute_Jetmech)."""
    return Unit(
        uid=uid, type="JetMech", x=x, y=y, hp=2, max_hp=2,
        team=1, is_mech=True, move_speed=4, flying=True,
        massive=True, armor=False, pushable=True,
        weapon="Brute_Jetmech", weapon2="", active=True,
    )


def _prime(uid: int, x: int, y: int) -> Unit:
    """Prime mech caster for Hydraulic Legs (Prime_Leap)."""
    return Unit(
        uid=uid, type="PunchMech", x=x, y=y, hp=3, max_hp=3,
        team=1, is_mech=True, move_speed=3, flying=False,
        massive=True, armor=False, pushable=True,
        weapon="Prime_Leap", weapon2="", active=True,
    )


def _brute(uid: int, x: int, y: int) -> Unit:
    """Brute mech caster for Bombing Run (Brute_Bombrun)."""
    return Unit(
        uid=uid, type="BruteMech", x=x, y=y, hp=3, max_hp=3,
        team=1, is_mech=True, move_speed=3, flying=False,
        massive=True, armor=False, pushable=True,
        weapon="Brute_Bombrun", weapon2="", active=True,
    )


def test_aerial_bombs_has_smoke_flag():
    """Regression guard: the transit-smoke path is gated on ``smoke`` in
    weapons.py. If the flag is ever moved/renamed, parity breaks silently
    unless this assertion catches it first."""
    wdef = get_weapon_def("Brute_Jetmech")
    assert wdef is not None
    assert wdef.weapon_type == "leap"
    assert wdef.smoke is True


def test_aerial_bombs_smoke_on_transit_tile_not_landing():
    """Aerial Bombs has range_min=range_max=2, so caster→landing is two
    tiles apart and the single transit tile (the one strictly between)
    should get smoke. Landing tile does NOT get smoke."""
    caster = _jet(uid=1, x=3, y=3)
    board = Board()
    board.units = [caster]

    # Leap east: source (3,3) → landing (3,5). Transit tile: (3,4).
    simulate_weapon(board, caster, "Brute_Jetmech", 3, 5)

    assert board.tile(3, 4).smoke is True, "transit tile should have smoke"
    assert board.tile(3, 5).smoke is False, "landing tile must NOT have smoke"
    assert board.tile(3, 3).smoke is False, "source tile must NOT have smoke"
    # Caster moved
    assert (caster.x, caster.y) == (3, 5)


def test_aerial_bombs_smoke_replaces_fire_on_transit():
    """Parity with ``apply_weapon_status``: smoke replaces fire when both
    would coexist — transit tile is cleared of fire and set to smoke."""
    caster = _jet(uid=1, x=3, y=3)
    board = Board()
    board.units = [caster]
    board.tile(3, 4).on_fire = True  # pre-existing fire on transit tile

    simulate_weapon(board, caster, "Brute_Jetmech", 3, 5)

    assert board.tile(3, 4).smoke is True
    assert board.tile(3, 4).on_fire is False


def test_aerial_bombs_upgraded_range_smokes_every_transit_tile():
    """+1 range Jetmech (range_max=3): source (3,2) → landing (3,5) has
    two transit tiles, (3,3) and (3,4). Both should get smoke. Rust walks
    every intermediate step on the cardinal path."""
    caster = _jet(uid=1, x=3, y=2)
    # Patch damage=0 so no enemies die from AoE clutter in this bounds test.
    # (Not strictly necessary — board is empty — but documents intent.)
    board = Board()
    board.units = [caster]

    simulate_weapon(board, caster, "Brute_Jetmech", 3, 5)

    # Transit tiles: (3,3) and (3,4). Landing: (3,5). Source: (3,2).
    assert board.tile(3, 3).smoke is True
    assert board.tile(3, 4).smoke is True
    assert board.tile(3, 5).smoke is False, "landing must not have smoke"
    assert board.tile(3, 2).smoke is False, "source must not have smoke"


def test_prime_leap_emits_no_smoke():
    """``Prime_Leap`` has no smoke flag — no tile in the flight path,
    including landing, should have smoke after the leap."""
    caster = _prime(uid=1, x=3, y=3)
    board = Board()
    board.units = [caster]

    simulate_weapon(board, caster, "Prime_Leap", 3, 6)

    for step in range(4, 7):  # 3,4 / 3,5 / 3,6 — transit + landing
        assert board.tile(3, step).smoke is False, f"tile (3,{step}) must not have smoke"
    assert board.tile(3, 3).smoke is False


def test_brute_bombrun_emits_no_smoke():
    """``Brute_Bombrun`` (Bombing Run) is a leap with no smoke flag —
    no tile along the cardinal path gets smoke, matching current Rust."""
    caster = _brute(uid=1, x=3, y=3)
    board = Board()
    board.units = [caster]

    simulate_weapon(board, caster, "Brute_Bombrun", 3, 6)

    for step in range(3, 7):
        assert board.tile(3, step).smoke is False, f"tile (3,{step}) must not have smoke"
