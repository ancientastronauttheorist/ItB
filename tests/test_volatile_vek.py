"""Volatile Vek Explosive Decay tests.

Behavior under test: when a Volatile Vek dies (by any cause — weapon
damage, push-to-deadly, mine), it deals 1 bump-class damage to every
adjacent tile. Fires BEFORE the Blast Psion chain so both helpers see
a consistent snapshot of the board. Chain-kills (explosion kills
another adjacent volatile) recurse with a depth cap.

Mirror tests for the Rust solver live in test_regression_corpus /
the weapon_overrides regression boards; this file covers the Python
parity that ships alongside.

Per data/vek.json #262: damage=1, range=all 4 adjacent tiles. No
Alpha variant exists in the base-game data; the helper matches
``"Volatile_Vek" in unit.type`` so a future Volatile_Vek_Alpha
would Just Work.
"""

from __future__ import annotations

from src.model.board import Board, Unit
from src.solver.simulate import ActionResult, apply_damage, apply_push


def _make_unit(uid, x, y, hp=5, team=6, pushable=True, is_mech=False,
               flying=False, armor=False, utype="Scorpion1"):
    return Unit(
        uid=uid, type=utype, x=x, y=y, hp=hp, max_hp=hp,
        team=team, is_mech=is_mech, move_speed=3, flying=flying,
        massive=False, armor=armor, pushable=pushable,
        weapon="", weapon2="", active=True,
    )


def _make_board_with_units(*units) -> Board:
    board = Board()
    for u in units:
        board.units.append(u)
    return board


# ── weapon damage kill path ──────────────────────────────────────────────────


def test_volatile_vek_death_damages_four_adjacent_mechs():
    # Mechs N/S/E/W of the Volatile Vek. Kill the Vek → each mech loses 1 HP.
    vek = _make_unit(1, 3, 3, hp=1, utype="Volatile_Vek")
    n = _make_unit(2, 3, 4, hp=3, team=1, is_mech=True, utype="PunchMech")
    s = _make_unit(3, 3, 2, hp=3, team=1, is_mech=True, utype="LaserMech")
    e = _make_unit(4, 4, 3, hp=3, team=1, is_mech=True, utype="ChargeMech")
    w = _make_unit(5, 2, 3, hp=3, team=1, is_mech=True, utype="ScienceMech")
    board = _make_board_with_units(vek, n, s, e, w)
    result = ActionResult()

    apply_damage(board, 3, 3, 1, result)  # kill the volatile

    assert vek.hp == 0
    assert n.hp == 2
    assert s.hp == 2
    assert e.hp == 2
    assert w.hp == 2
    # Mech damage counter reflects the explosion fallout.
    assert result.mech_damage_taken == 4


def test_volatile_vek_survives_when_not_killed():
    # Vek HP > damage → no death → no explosion.
    vek = _make_unit(1, 3, 3, hp=2, utype="Volatile_Vek")
    neighbor = _make_unit(2, 4, 3, hp=3, team=1, is_mech=True, utype="PunchMech")
    board = _make_board_with_units(vek, neighbor)
    result = ActionResult()

    apply_damage(board, 3, 3, 1, result)

    assert vek.hp == 1  # survived
    assert neighbor.hp == 3  # no splash
    assert result.mech_damage_taken == 0


def test_volatile_decay_ignores_armor_and_acid():
    # Bump-class damage bypasses both, matching the game rules for
    # Explosive Decay and the Blast Psion aura.
    vek = _make_unit(1, 3, 3, hp=1, utype="Volatile_Vek")
    armored_mech = _make_unit(
        2, 4, 3, hp=3, team=1, is_mech=True,
        armor=True, utype="PunchMech",
    )
    acid_enemy = _make_unit(3, 2, 3, hp=3, utype="Scorpion1")
    acid_enemy.acid = True
    board = _make_board_with_units(vek, armored_mech, acid_enemy)
    result = ActionResult()

    apply_damage(board, 3, 3, 1, result)

    # Armor would normally reduce to 0; bump damage ignores it.
    assert armored_mech.hp == 2
    # ACID doubles weapon damage; bump ignores it, so 1 damage not 2.
    assert acid_enemy.hp == 2


def test_volatile_decay_does_not_chain_on_non_volatile():
    # Adjacent non-volatile enemy dies from the 1 damage; no second explosion.
    vek = _make_unit(1, 3, 3, hp=1, utype="Volatile_Vek")
    fragile = _make_unit(2, 4, 3, hp=1, utype="Scorpion1")
    bystander = _make_unit(
        3, 5, 3, hp=3, team=1, is_mech=True, utype="ChargeMech",
    )
    board = _make_board_with_units(vek, fragile, bystander)
    result = ActionResult()

    apply_damage(board, 3, 3, 1, result)

    assert fragile.hp == 0  # killed by decay
    assert bystander.hp == 3  # no second explosion from non-volatile death


def test_volatile_decay_chains_through_adjacent_volatile():
    # Chain: volatile A at (3,3) dies → hits volatile B at (4,3) for 1;
    # B now at 0 hp → its decay fires → hits mech at (5,3) for 1.
    a = _make_unit(1, 3, 3, hp=1, utype="Volatile_Vek")
    b = _make_unit(2, 4, 3, hp=1, utype="Volatile_Vek")
    mech = _make_unit(
        3, 5, 3, hp=3, team=1, is_mech=True, utype="ChargeMech",
    )
    board = _make_board_with_units(a, b, mech)
    result = ActionResult()

    apply_damage(board, 3, 3, 1, result)

    assert a.hp == 0
    assert b.hp == 0
    assert mech.hp == 2  # hit by B's chain explosion, not A's (not adjacent)


# ── push-to-deadly-terrain kill path ─────────────────────────────────────────


def test_volatile_vek_pushed_into_water_explodes():
    # Non-flying volatile pushed into water: drowns AND explodes.
    vek = _make_unit(1, 3, 3, hp=3, utype="Volatile_Vek", flying=False)
    mech = _make_unit(
        2, 5, 3, hp=3, team=1, is_mech=True, utype="PunchMech",
    )
    board = _make_board_with_units(vek, mech)
    # Make the destination tile water so the push kills the volatile.
    board.tiles[4][3].terrain = "water"
    result = ActionResult()

    # Push east: (3,3) -> (4,3) which is water.
    apply_push(board, 3, 3, 1, result)

    assert vek.hp == 0
    # Mech at (5,3) is adjacent to (4,3) — takes 1 from the decay.
    assert mech.hp == 2


def test_volatile_decay_attribution_in_events():
    # Event log records the explosion so post-turn analysis can
    # distinguish decay damage from direct hits.
    vek = _make_unit(1, 3, 3, hp=1, utype="Volatile_Vek")
    neighbor = _make_unit(2, 4, 3, hp=3, team=1, is_mech=True, utype="ScienceMech")
    board = _make_board_with_units(vek, neighbor)
    result = ActionResult()

    apply_damage(board, 3, 3, 1, result)

    assert any("Volatile decay" in e for e in result.events)
