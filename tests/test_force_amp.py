"""Tests for Passive_ForceAmp (Force Amp).

Force Amp is an any-class passive that adds +1 to bump-class damage dealt
to Vek (push-collision bumps + spawn-blocking damage). Per the wiki, the
Bot Leader is sentient and explicitly exempt from the bonus. Mechs and
allied units never get the bonus (only Vek take it).
"""

from __future__ import annotations

from src.model.board import Board, Unit, BoardTile
from src.solver.simulate import apply_push, ActionResult


def _vek(uid, x, y, hp=2, utype="Scorpion"):
    return Unit(
        uid=uid, type=utype, x=x, y=y, hp=hp, max_hp=hp,
        team=6, is_mech=False, move_speed=3, flying=False,
        massive=False, armor=False, pushable=True,
        weapon="", weapon2="", active=True,
    )


def _mech(uid, x, y, hp=3):
    return Unit(
        uid=uid, type=f"Mech{uid}", x=x, y=y, hp=hp, max_hp=hp,
        team=1, is_mech=True, move_speed=3, flying=False,
        massive=False, armor=False, pushable=True,
        weapon="", weapon2="", active=True,
    )


def _board_with_mountain(force_amp: bool):
    b = Board()
    b.tile(3, 4).terrain = "mountain"
    b.tile(3, 4).building_hp = 2
    b.force_amp = force_amp
    return b


def test_force_amp_amplifies_bump_to_vek():
    b = _board_with_mountain(force_amp=True)
    v = _vek(1, 3, 3, hp=2)
    b.units.append(v)
    apply_push(b, 3, 3, 0, ActionResult())  # push N into mountain
    assert v.hp == 0, "Force Amp: 1+1=2 bump damage kills 2-HP Vek"


def test_no_force_amp_normal_bump():
    b = _board_with_mountain(force_amp=False)
    v = _vek(1, 3, 3, hp=2)
    b.units.append(v)
    apply_push(b, 3, 3, 0, ActionResult())
    assert v.hp == 1, "No Force Amp: 1 bump damage"


def test_force_amp_does_not_amplify_mechs():
    b = _board_with_mountain(force_amp=True)
    m = _mech(99, 3, 3, hp=3)
    b.units.append(m)
    apply_push(b, 3, 3, 0, ActionResult())
    assert m.hp == 2, "Mechs take normal 1 bump damage, not amped"


def test_force_amp_bot_leader_exempt():
    # Bot Leader is a sentient enemy — exempt from Force Amp per wiki.
    b = _board_with_mountain(force_amp=True)
    bot = _vek(1, 3, 3, hp=5, utype="BotBoss")
    b.units.append(bot)
    apply_push(b, 3, 3, 0, ActionResult())
    assert bot.hp == 4, "Bot Leader takes normal 1 bump damage"


def test_force_amp_detected_from_bridge_data():
    # A bridge state with a mech carrying Passive_ForceAmp sets the flag.
    data = {
        "grid_power": 7,
        "tiles": [],
        "units": [
            {"type": "PunchMech", "x": 3, "y": 3, "hp": 3, "max_hp": 3,
             "team": 1, "mech": True, "is_mech": True, "move_speed": 3,
             "flying": False, "massive": False, "armor": False,
             "pushable": True, "active": True,
             "weapons": ["Prime_Punchmech", "Passive_ForceAmp"]},
        ],
    }
    b = Board.from_bridge_data(data)
    assert b.force_amp is True


def test_force_amp_not_detected_without_passive():
    data = {
        "grid_power": 7,
        "tiles": [],
        "units": [
            {"type": "PunchMech", "x": 3, "y": 3, "hp": 3, "max_hp": 3,
             "team": 1, "mech": True, "is_mech": True, "move_speed": 3,
             "flying": False, "massive": False, "armor": False,
             "pushable": True, "active": True,
             "weapons": ["Prime_Punchmech"]},
        ],
    }
    b = Board.from_bridge_data(data)
    assert b.force_amp is False


def test_force_amp_persists_through_board_copy():
    b = Board()
    b.force_amp = True
    b2 = b.copy()
    assert b2.force_amp is True
