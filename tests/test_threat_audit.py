from src.model.board import Board, Unit
from src.solver.threat_audit import (
    audit_threat_coverage,
    capture_building_threats,
)


def _enemy(uid=10, pawn_type="Firefly1", x=4, y=4, tx=4, ty=2, hp=3):
    return Unit(
        uid=uid,
        type=pawn_type,
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


def _egg(uid=11, x=2, y=3, hp=1):
    return Unit(
        uid=uid,
        type="WebbEgg1",
        x=x,
        y=y,
        hp=hp,
        max_hp=1,
        team=6,
        is_mech=False,
        move_speed=0,
        flying=False,
        massive=False,
        armor=False,
        pushable=True,
        weapon="WebeggHatch1",
        active=False,
        target_x=x,
        target_y=y,
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


def test_threat_audit_attacker_will_die_to_fire():
    initial = capture_building_threats(_board(_enemy(pawn_type="Leaper1", hp=1)))
    after = _board(_enemy(pawn_type="Leaper1", hp=1))
    after.units[0].fire = True

    audit = audit_threat_coverage(initial, after)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == "attacker_will_die_to_fire"


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


def test_capture_building_threats_includes_egg_hatch_building():
    board = Board()
    board.tile(2, 2).terrain = "building"
    board.tile(2, 2).building_hp = 2
    board.units.append(_egg(x=2, y=3))

    threats = capture_building_threats(board)

    assert threats[0]["threat_kind"] == "hatch_projected_building"
    assert threats[0]["target"] == [2, 2]
    assert threats[0]["target_visual"] == "F6"


def test_threat_audit_hatching_egg_still_threatened_warns():
    board = Board()
    board.tile(2, 2).terrain = "building"
    board.tile(2, 2).building_hp = 2
    board.units.append(_egg(x=2, y=3))
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "WARN"
    assert audit["still_threatened_count"] == 1
    assert audit["entries"][0]["coverage"]["reason"] == "still_threatened_hatch"


def test_threat_audit_hatch_clears_when_egg_killed():
    board = Board()
    board.tile(2, 2).terrain = "building"
    board.tile(2, 2).building_hp = 2
    board.units.append(_egg(x=2, y=3))
    initial = capture_building_threats(board)

    after = Board()
    after.tile(2, 2).terrain = "building"
    after.tile(2, 2).building_hp = 2
    after.units.append(_egg(x=2, y=3, hp=0))
    audit = audit_threat_coverage(initial, after)

    assert audit["status"] == "OK"
    assert audit["entries"][0]["coverage"]["reason"] == "attacker_killed"
