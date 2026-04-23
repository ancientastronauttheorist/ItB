"""Tests for Python ``_sim_leap`` transit-DAMAGE emission parity with Rust.

Complements ``test_sim_leap_smoke.py`` (which covers status emission).

Parity reference: ``rust_solver/src/simulate.rs::sim_leap`` post-PR #11/#12
(commits 2723938 / 45bd059). Two leap weapons drop damage on every
transit tile (strictly between source and landing) along the cardinal
flight path instead of the legacy 4-cardinal-neighbours-of-landing AoE:

    - Jet_BombDrop / ``Brute_Jetmech`` (Aerial Bombs): SMOKE flag
    - Brute_Bombrun (Bombing Run): DAMAGES_TRANSIT flag

Other leap weapons (Prime_Leap "Hydraulic Legs": "damaging self and
adjacent tiles") must keep the legacy landing-adjacent damage. This is
the regression guard that ensures the Python gate didn't accidentally
redirect Prime_Leap into the transit branch.

Python ``_sim_leap`` is used only for ``predicted_states`` snapshots and
``replay_solution`` (the solver itself scores via Rust), so a gap here
causes verify_action diffs to falsely flag desyncs — not solver
misbehaviour. The commit that adds these tests (fix/python-leap-transit-
damage-emission) closes the Python-side transit-damage gap.
"""

from __future__ import annotations

from src.model.board import Board, Unit
from src.solver.simulate import simulate_weapon


# ── casters ─────────────────────────────────────────────────────────────────


def _jet(uid: int, x: int, y: int) -> Unit:
    """Jet Mech caster for Aerial Bombs (Brute_Jetmech, SMOKE flag)."""
    return Unit(
        uid=uid, type="JetMech", x=x, y=y, hp=2, max_hp=2,
        team=1, is_mech=True, move_speed=4, flying=True,
        massive=True, armor=False, pushable=True,
        weapon="Brute_Jetmech", weapon2="", active=True,
    )


def _brute(uid: int, x: int, y: int) -> Unit:
    """Brute mech caster for Bombing Run (Brute_Bombrun, DAMAGES_TRANSIT)."""
    return Unit(
        uid=uid, type="BruteMech", x=x, y=y, hp=3, max_hp=3,
        team=1, is_mech=True, move_speed=3, flying=False,
        massive=True, armor=False, pushable=True,
        weapon="Brute_Bombrun", weapon2="", active=True,
    )


def _prime(uid: int, x: int, y: int) -> Unit:
    """Prime mech caster for Hydraulic Legs (Prime_Leap, no transit flag)."""
    return Unit(
        uid=uid, type="PunchMech", x=x, y=y, hp=3, max_hp=3,
        team=1, is_mech=True, move_speed=3, flying=False,
        massive=True, armor=False, pushable=True,
        weapon="Prime_Leap", weapon2="", active=True,
    )


def _enemy(uid: int, x: int, y: int, hp: int = 3) -> Unit:
    """Generic 3-HP enemy used as a damage target. No armor/shield/acid so
    ``apply_damage`` deals raw damage and we can assert HP exactly."""
    return Unit(
        uid=uid, type="Scorpion1", x=x, y=y, hp=hp, max_hp=hp,
        team=6, is_mech=False, move_speed=0, flying=False,
        massive=False, armor=False, pushable=True,
        weapon="", weapon2="", active=False,
    )


# ── Aerial Bombs (smoke-flagged transit damage) ─────────────────────────────


def test_aerial_bombs_damages_transit_tile():
    """Base-range Aerial Bombs (range=2): source (3,3) → landing (3,5).
    Single transit tile (3,4) should take wdef.damage = 1."""
    caster = _jet(uid=1, x=3, y=3)
    transit_enemy = _enemy(uid=2, x=3, y=4, hp=3)
    board = Board()
    board.units = [caster, transit_enemy]

    result = simulate_weapon(board, caster, "Brute_Jetmech", 3, 5)

    assert transit_enemy.hp == 2, (
        f"transit-tile enemy should take 1 damage, got hp={transit_enemy.hp}"
    )
    assert result.enemy_damage_dealt == 1


def test_aerial_bombs_does_not_damage_landing_adjacent():
    """Regression guard for commit ea05707: Aerial Bombs must NOT fall
    through into the legacy landing-adjacent damage branch. Landing tile
    is (3,5); four cardinal neighbours are (2,5), (4,5), (3,4), (3,6).
    Of these, (3,4) is the transit tile and may receive damage; (4,5)
    and (3,6) are NOT transit tiles and must not be damaged."""
    caster = _jet(uid=1, x=3, y=3)
    # Enemy at (4,5) is landing-adjacent but NOT on the cardinal flight path.
    # If _sim_leap fell through to the legacy branch this would take 1 damage.
    adj_enemy = _enemy(uid=2, x=4, y=5, hp=3)
    board = Board()
    board.units = [caster, adj_enemy]

    simulate_weapon(board, caster, "Brute_Jetmech", 3, 5)

    assert adj_enemy.hp == 3, (
        "landing-adjacent enemy off the cardinal path must not be damaged — "
        "transit branch must not fall through to the legacy AoE"
    )


# ── Bombing Run (damages_transit-flagged) ───────────────────────────────────


def test_bombing_run_damages_every_transit_tile():
    """Bombing Run leap (range_max=8): source (3,1) → landing (3,6) has
    four transit tiles (3,2), (3,3), (3,4), (3,5). Each should take
    wdef.damage = 1. Matches Rust test
    ``test_aerial_bombs_damages_transit_tile_base_range`` extended for
    the no-range-limit Bombing Run."""
    caster = _brute(uid=1, x=3, y=1)
    e1 = _enemy(uid=2, x=3, y=2, hp=3)
    e2 = _enemy(uid=3, x=3, y=3, hp=3)
    e3 = _enemy(uid=4, x=3, y=4, hp=3)
    e4 = _enemy(uid=5, x=3, y=5, hp=3)
    board = Board()
    board.units = [caster, e1, e2, e3, e4]

    result = simulate_weapon(board, caster, "Brute_Bombrun", 3, 6)

    assert e1.hp == 2, f"transit (3,2) enemy should take 1 dmg, got {e1.hp}"
    assert e2.hp == 2, f"transit (3,3) enemy should take 1 dmg, got {e2.hp}"
    assert e3.hp == 2, f"transit (3,4) enemy should take 1 dmg, got {e3.hp}"
    assert e4.hp == 2, f"transit (3,5) enemy should take 1 dmg, got {e4.hp}"
    assert result.enemy_damage_dealt == 4


def test_bombing_run_does_not_damage_landing_tile():
    """Transit is strictly between source and landing — landing tile
    itself must not be damaged by the transit branch (the caster lands
    on it)."""
    caster = _brute(uid=1, x=3, y=2)
    # Place an enemy on the LANDING tile? No — caster lands there, enumerator
    # would have filtered. Test with an enemy adjacent to landing instead, at
    # (4,5): landing (3,5), adj (4,5) is off the cardinal path and must NOT
    # be damaged.
    adj_enemy = _enemy(uid=2, x=4, y=5, hp=3)
    board = Board()
    board.units = [caster, adj_enemy]

    simulate_weapon(board, caster, "Brute_Bombrun", 3, 5)

    assert adj_enemy.hp == 3, "landing-adjacent off-path enemy must not be hit"


# ── Prime_Leap regression: legacy landing-adjacent damage preserved ────────


def test_prime_leap_keeps_landing_adjacent_damage():
    """Prime_Leap (Hydraulic Legs) has neither ``smoke`` nor
    ``damages_transit`` — it must still fall into the legacy branch that
    damages the four cardinal neighbours of the landing tile (skipping
    the tile we jumped from). Matches Rust test
    ``test_prime_leap_keeps_landing_adjacent_damage``."""
    caster = _prime(uid=1, x=3, y=3)
    # Adjacent leap: landing (3,4). Neighbours = (2,4), (4,4), (3,3), (3,5).
    # (3,3) is the source we came from — skipped.
    west_enemy = _enemy(uid=2, x=2, y=4, hp=3)
    east_enemy = _enemy(uid=3, x=4, y=4, hp=3)
    forward_enemy = _enemy(uid=4, x=3, y=5, hp=3)
    board = Board()
    board.units = [caster, west_enemy, east_enemy, forward_enemy]

    simulate_weapon(board, caster, "Prime_Leap", 3, 4)

    assert west_enemy.hp == 2, "landing-adjacent west enemy should take 1 dmg"
    assert east_enemy.hp == 2, "landing-adjacent east enemy should take 1 dmg"
    assert forward_enemy.hp == 2, "landing-adjacent forward enemy should take 1 dmg"


def test_prime_leap_does_not_damage_transit_tile():
    """Inverse of the smoke/transit tests: Prime_Leap must NOT apply
    transit-path damage. Long leap source (3,3) → landing (3,6); the
    transit tiles (3,4) and (3,5) are not in the legacy landing-adjacent
    ring and must not be hit (landing-adjacent is around (3,6), so (3,5)
    IS adjacent and will be damaged — but (3,4) is NOT). This regression
    guard checks the strictly-in-transit tile (3,4) stays intact."""
    caster = _prime(uid=1, x=3, y=3)
    mid_transit_enemy = _enemy(uid=2, x=3, y=4, hp=3)
    board = Board()
    board.units = [caster, mid_transit_enemy]

    simulate_weapon(board, caster, "Prime_Leap", 3, 6)

    # (3,4) is two tiles away from landing (3,6) — outside the
    # landing-adjacent ring — so must be untouched.
    assert mid_transit_enemy.hp == 3, (
        "Prime_Leap must not damage mid-transit tile (3,4); only "
        "landing-adjacent tiles should take damage"
    )
