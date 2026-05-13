from src.model.board import Board, Unit
from src.solver.threat_audit import (
    audit_threat_coverage,
    capture_building_threats,
)


def _enemy(uid=10, x=4, y=4, tx=4, ty=2, hp=3):
    return Unit(
        uid=uid,
        type="Firefly1",
        x=x,
        y=y,
        hp=hp,
        max_hp=3,
        team=6,
        is_mech=False,
        move_speed=3,
        flying=False,
        massive=False,
        armor=False,
        pushable=True,
        weapon="FireflyAtk1",
        active=False,
        target_x=tx,
        target_y=ty,
        has_queued_attack=True,
    )


def _board(attacker=None):
    board = Board()
    tile = board.tile(4, 2)
    tile.terrain = "building"
    tile.building_hp = 1
    board.units.append(attacker or _enemy())
    return board


def test_capture_building_threats_uses_visual_tiles():
    threats = capture_building_threats(_board())

    assert threats[0]["target"] == [4, 2]
    assert threats[0]["target_visual"] == "F4"
    assert threats[0]["attacker"]["target_visual"] == "F4"


def test_threat_audit_attacker_killed():
    initial = capture_building_threats(_board())
    after = _board(_enemy(hp=0))

    audit = audit_threat_coverage(initial, after)

    assert audit["status"] == "OK"
    assert audit["entries"][0]["coverage"]["reason"] == "attacker_killed"


def test_threat_audit_attacker_smoked():
    initial = capture_building_threats(_board())
    after = _board()
    after.tile(4, 4).smoke = True

    audit = audit_threat_coverage(initial, after)

    assert audit["entries"][0]["coverage"]["reason"] == "attacker_smoked"


def test_threat_audit_still_threatened_warns():
    initial = capture_building_threats(_board())

    audit = audit_threat_coverage(initial, _board())

    assert audit["status"] == "WARN"
    assert audit["still_threatened_count"] == 1
    assert audit["entries"][0]["coverage"]["reason"] == "still_threatened"


def test_threat_audit_retargeted_nonbuilding():
    initial = capture_building_threats(_board())
    after = _board(_enemy(tx=0, ty=0))

    audit = audit_threat_coverage(initial, after)

    assert audit["entries"][0]["coverage"]["reason"] == "retargeted_nonbuilding"
