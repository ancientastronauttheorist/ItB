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


def test_threat_audit_blocks_current_threat_missing_from_initial_set():
    board = _board()

    audit = audit_threat_coverage([], board)

    assert audit["status"] == "WARN"
    assert audit["initial_threat_count"] == 0
    assert audit["current_threat_count"] == 1
    assert audit["new_current_threat_count"] == 1
    assert audit["still_threatened_count"] == 1
    assert audit["entries"][0]["coverage"]["reason"] == "still_threatened_current"


def test_threat_audit_credits_new_current_threat_killed_by_environment():
    board = _board()
    board.environment_danger_v2[(4, 4)] = (1, True)

    audit = audit_threat_coverage([], board)

    assert audit["status"] == "OK"
    assert audit["initial_threat_count"] == 0
    assert audit["current_threat_count"] == 1
    assert audit["new_current_threat_count"] == 1
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == (
        "attacker_will_die_to_environment"
    )


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


def test_threat_audit_attacker_will_die_to_prior_bouncer_bump():
    board = Board()
    board.tile(5, 6).terrain = "building"
    board.tile(5, 6).building_hp = 2
    board.units.append(_enemy(
        uid=10,
        pawn_type="Bouncer1",
        x=4,
        y=5,
        tx=4,
        ty=4,
        hp=4,
    ))
    board.units[-1].weapon = "BouncerAtk1"
    board.units[-1].fire = True
    board.units.append(_enemy(
        uid=20,
        pawn_type="Leaper1",
        x=4,
        y=6,
        tx=5,
        ty=6,
        hp=1,
    ))
    board.units[-1].weapon = "LeaperAtk1"
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == "attacker_will_die_to_prior_bump"


def test_threat_audit_attacker_will_die_to_prior_projectile():
    board = Board()
    board.attack_order = [10, 20]
    board.tile(3, 6).terrain = "building"
    board.tile(3, 6).building_hp = 2
    board.units.append(_enemy(
        uid=10,
        pawn_type="Firefly2",
        x=5,
        y=6,
        tx=4,
        ty=6,
        hp=1,
    ))
    board.units[-1].weapon = "FireflyAtk2"
    board.units[-1].max_hp = 5
    board.units.append(_enemy(
        uid=20,
        pawn_type="Mosquito1",
        x=4,
        y=6,
        tx=3,
        ty=6,
        hp=1,
    ))
    board.units[-1].weapon = "MosquitoAtk1"
    board.units[-1].max_hp = 2
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == (
        "attacker_will_die_to_prior_projectile"
    )


def test_threat_audit_attacker_will_die_to_prior_melee():
    board = Board()
    board.attack_order = [23716, 23719]
    board.mission_id = "Mission_Tides"
    board.tile(4, 3).terrain = "building"
    board.tile(4, 3).building_hp = 2
    board.units.append(_enemy(
        uid=23716,
        pawn_type="Scorpion1",
        x=4,
        y=5,
        tx=4,
        ty=4,
        hp=1,
    ))
    board.units[-1].weapon = "ScorpionAtk1"
    board.units[-1].weapon_damage = 1
    board.units.append(_enemy(
        uid=23719,
        pawn_type="Scorpion1",
        x=4,
        y=4,
        tx=4,
        ty=3,
        hp=1,
    ))
    board.units[-1].weapon = "ScorpionAtk1"
    board.units[-1].weapon_damage = 1
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == (
        "attacker_will_die_to_prior_melee"
    )


def test_threat_audit_dungboss_kills_bouncer_before_building_attack():
    board = Board()
    board.attack_order = [153, 202]
    board.tile(4, 6).terrain = "building"
    board.tile(4, 6).building_hp = 2
    board.units.append(_enemy(
        uid=153,
        pawn_type="DungBoss",
        x=6,
        y=6,
        tx=5,
        ty=6,
        hp=6,
    ))
    board.units[-1].weapon = "DungAtkB"
    board.units[-1].weapon_damage = 3
    board.units[-1].max_hp = 6
    board.units.append(_enemy(
        uid=202,
        pawn_type="Bouncer1",
        x=5,
        y=6,
        tx=4,
        ty=6,
        hp=3,
    ))
    board.units[-1].weapon = "BouncerAtk1"
    board.units[-1].weapon_damage = 1
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == (
        "attacker_will_die_to_prior_melee"
    )


def test_threat_audit_attacker_will_die_to_prior_artillery():
    board = Board()
    board.attack_order = [10, 20]
    board.tile(0, 6).terrain = "building"
    board.tile(0, 6).building_hp = 1
    board.units.append(_enemy(
        uid=10,
        pawn_type="Moth2",
        x=5,
        y=3,
        tx=5,
        ty=6,
        hp=5,
    ))
    board.units[-1].weapon = "MothAtk2"
    board.units[-1].max_hp = 5
    board.units.append(_enemy(
        uid=20,
        pawn_type="Moth1",
        x=5,
        y=6,
        tx=0,
        ty=6,
        hp=3,
    ))
    board.units[-1].weapon = "MothAtk1"
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == (
        "attacker_will_die_to_prior_artillery"
    )


def test_threat_audit_attacker_will_die_to_soldier_psion_fire_teardown():
    board = Board()
    board.tile(5, 6).terrain = "building"
    board.tile(5, 6).building_hp = 2
    board.units.append(_enemy(
        uid=10,
        pawn_type="Bouncer1",
        x=4,
        y=6,
        tx=5,
        ty=6,
        hp=2,
    ))
    board.units[-1].weapon = "BouncerAtk1"
    board.units[-1].fire = True
    board.units.append(_enemy(
        uid=20,
        pawn_type="Jelly_Health1",
        x=5,
        y=5,
        tx=-1,
        ty=-1,
        hp=1,
    ))
    board.units[-1].weapon = ""
    board.units[-1].fire = True
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == (
        "attacker_will_die_to_soldier_psion_teardown"
    )


def test_threat_audit_attacker_will_die_to_boss_psion_fire_teardown():
    board = Board()
    board.tile(5, 6).terrain = "building"
    board.tile(5, 6).building_hp = 2
    board.units.append(_enemy(
        uid=10,
        pawn_type="Bouncer1",
        x=4,
        y=6,
        tx=5,
        ty=6,
        hp=2,
    ))
    board.units[-1].weapon = "BouncerAtk1"
    board.units[-1].fire = True
    board.units.append(_enemy(
        uid=20,
        pawn_type="Jelly_Boss",
        x=5,
        y=5,
        tx=-1,
        ty=-1,
        hp=1,
    ))
    board.units[-1].weapon = ""
    board.units[-1].fire = True
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == (
        "attacker_will_die_to_soldier_psion_teardown"
    )


def test_threat_audit_boss_fire_teardown_blocked_by_surviving_soldier_psion():
    board = Board()
    board.tile(5, 6).terrain = "building"
    board.tile(5, 6).building_hp = 2
    board.units.append(_enemy(
        uid=10,
        pawn_type="Bouncer1",
        x=4,
        y=6,
        tx=5,
        ty=6,
        hp=2,
    ))
    board.units[-1].weapon = "BouncerAtk1"
    board.units[-1].fire = True
    board.units.append(_enemy(
        uid=20,
        pawn_type="Jelly_Boss",
        x=5,
        y=5,
        tx=-1,
        ty=-1,
        hp=1,
    ))
    board.units[-1].weapon = ""
    board.units[-1].fire = True
    board.units.append(_enemy(
        uid=30,
        pawn_type="Jelly_Health1",
        x=5,
        y=4,
        tx=-1,
        ty=-1,
        hp=2,
    ))
    board.units[-1].weapon = ""
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "WARN"
    assert audit["still_threatened_count"] == 1


def test_threat_audit_attacker_will_be_frozen_by_environment():
    board = _board()
    board.environment_freeze.add((4, 4))
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == (
        "attacker_will_be_frozen_by_environment"
    )


def test_threat_audit_attacker_will_die_to_lethal_environment():
    board = _board()
    board.environment_danger_v2[(4, 4)] = (1, True)
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == (
        "attacker_will_die_to_environment"
    )


def test_threat_audit_satellite_launch_does_not_cover_pre_attack_threat():
    board = _board()
    board.mission_id = "Mission_Satellite"
    board.environment_danger.add((4, 4))
    board.environment_danger_v2[(4, 4)] = (1, True)
    board.environment_danger_flying_immune.add((4, 4))
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "WARN"
    assert audit["still_threatened_count"] == 1
    assert audit["entries"][0]["coverage"]["reason"] == "still_threatened"


def test_threat_audit_tides_does_not_cover_pre_attack_threat():
    board = _board()
    board.mission_id = "Mission_Tides"
    board.environment_danger.add((4, 4))
    board.environment_danger_v2[(4, 4)] = (1, True)
    board.environment_danger_flying_immune.add((4, 4))
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "WARN"
    assert audit["still_threatened_count"] == 1
    assert audit["entries"][0]["coverage"]["reason"] == "still_threatened"


def test_threat_audit_flying_attacker_survives_flying_immune_environment():
    board = _board()
    board.units[0].flying = True
    board.environment_danger.add((4, 4))
    board.environment_danger_v2[(4, 4)] = (1, True)
    board.environment_danger_flying_immune.add((4, 4))
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "WARN"
    assert audit["still_threatened_count"] == 1
    assert audit["entries"][0]["coverage"]["reason"] == "still_threatened"


def test_threat_audit_shield_blocks_environment_freeze_credit():
    board = _board()
    board.environment_freeze.add((4, 4))
    board.units[0].shield = True
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "WARN"
    assert audit["entries"][0]["coverage"]["reason"] == "still_threatened"


def test_threat_audit_attacker_will_be_moved_by_prior_moth_attack():
    board = Board()
    board.tile(5, 2).terrain = "building"
    board.tile(5, 2).building_hp = 2
    board.units.append(_enemy(
        uid=10,
        pawn_type="Moth1",
        x=6,
        y=5,
        tx=6,
        ty=2,
        hp=3,
    ))
    board.units[-1].weapon = "MothAtk1"
    board.units.append(_enemy(
        uid=20,
        pawn_type="Bouncer1",
        x=6,
        y=2,
        tx=5,
        ty=2,
        hp=3,
    ))
    board.units[-1].weapon = "BouncerAtk1"
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == (
        "attacker_will_be_moved_by_prior_attack"
    )


def test_threat_audit_prior_moth_blocked_push_still_warns():
    board = Board()
    board.tile(5, 2).terrain = "building"
    board.tile(5, 2).building_hp = 2
    board.tile(6, 1).terrain = "building"
    board.tile(6, 1).building_hp = 1
    board.units.append(_enemy(
        uid=10,
        pawn_type="Moth1",
        x=6,
        y=5,
        tx=6,
        ty=2,
        hp=3,
    ))
    board.units[-1].weapon = "MothAtk1"
    board.units.append(_enemy(
        uid=20,
        pawn_type="Bouncer1",
        x=6,
        y=2,
        tx=5,
        ty=2,
        hp=3,
    ))
    board.units[-1].weapon = "BouncerAtk1"
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "WARN"
    assert audit["entries"][0]["coverage"]["reason"] == "still_threatened"


def test_threat_audit_attacker_will_be_moved_by_conveyor():
    board = Board()
    board.mission_id = "Mission_Belt"
    board.tile(6, 3).terrain = "building"
    board.tile(6, 3).building_hp = 2
    board.tile(5, 3).conveyor = 0  # raw engine DIR_UP, solver direction y - 1
    board.units.append(_enemy(
        uid=136,
        pawn_type="Scorpion1",
        x=5,
        y=3,
        tx=6,
        ty=3,
        hp=3,
    ))
    board.units[-1].weapon = "ScorpionAtk1"
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == "attacker_will_be_moved_by_conveyor"


def test_threat_audit_beltrandom_conveyor_does_not_cover_attack():
    board = Board()
    board.mission_id = "Mission_BeltRandom"
    board.tile(6, 3).terrain = "building"
    board.tile(6, 3).building_hp = 2
    board.tile(5, 3).conveyor = 0
    board.units.append(_enemy(
        uid=136,
        pawn_type="Scorpion1",
        x=5,
        y=3,
        tx=6,
        ty=3,
        hp=3,
    ))
    board.units[-1].weapon = "ScorpionAtk1"
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "WARN"
    assert audit["still_threatened_count"] == 1
    assert audit["entries"][0]["coverage"]["reason"] == "still_threatened"


def test_threat_audit_attacker_will_be_moved_by_wind():
    board = Board()
    board.mission_id = "Mission_Wind"
    board.environment_wind_dir = 2  # raw engine DIR_DOWN -> solver direction y + 1
    board.environment_danger.add((2, 1))
    board.environment_danger_v2[(2, 1)] = (1, False)
    board.tile(3, 1).terrain = "building"
    board.tile(3, 1).building_hp = 2
    board.units.append(_enemy(
        uid=2476,
        pawn_type="Scorpion1",
        x=2,
        y=1,
        tx=3,
        ty=1,
        hp=1,
    ))
    board.units[-1].weapon = "ScorpionAtk1"
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == (
        "attacker_will_be_moved_by_wind"
    )


def test_threat_audit_wind_shift_into_building_still_warns():
    board = Board()
    board.mission_id = "Mission_Wind"
    board.environment_wind_dir = 2  # raw engine DIR_DOWN -> solver direction y + 1
    board.environment_danger.add((2, 1))
    board.environment_danger_v2[(2, 1)] = (1, False)
    board.tile(3, 1).terrain = "building"
    board.tile(3, 1).building_hp = 2
    board.tile(3, 2).terrain = "building"
    board.tile(3, 2).building_hp = 2
    board.units.append(_enemy(
        uid=2476,
        pawn_type="Scorpion1",
        x=2,
        y=1,
        tx=3,
        ty=1,
        hp=1,
    ))
    board.units[-1].weapon = "ScorpionAtk1"
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "WARN"
    assert audit["still_threatened_count"] == 1
    assert audit["entries"][0]["coverage"]["reason"] == (
        "still_threatened_after_wind"
    )


def test_threat_audit_captures_wind_projected_threat_after_fire_clears_blocker():
    board = Board()
    board.mission_id = "Mission_Wind"
    board.environment_wind_dir = 2  # raw engine DIR_DOWN -> solver direction y + 1
    board.environment_danger.update({(5, 4), (5, 5)})
    board.environment_danger_v2[(5, 4)] = (1, False)
    board.environment_danger_v2[(5, 5)] = (1, False)
    board.tile(3, 5).terrain = "building"
    board.tile(3, 5).building_hp = 1
    board.tile(5, 6).terrain = "building"
    board.tile(5, 6).building_hp = 2
    board.units.append(_enemy(
        uid=931,
        pawn_type="Scorpion1",
        x=5,
        y=5,
        tx=5,
        ty=6,
        hp=1,
    ))
    board.units[-1].weapon = "ScorpionAtk1"
    board.units[-1].fire = True
    board.units.append(_enemy(
        uid=955,
        pawn_type="Firefly1",
        x=5,
        y=4,
        tx=4,
        ty=4,
        hp=3,
    ))
    board.units[-1].weapon = "FireflyAtk1"

    threats = capture_building_threats(board)
    wind_threats = [
        threat for threat in threats
        if threat.get("threat_kind") == "wind_projected_building"
    ]

    assert wind_threats
    assert wind_threats[0]["target"] == [3, 5]
    assert wind_threats[0]["projected_attacker_pos"] == [5, 5]


def test_threat_audit_conveyor_projected_building_still_warns():
    board = Board()
    board.mission_id = "Mission_Belt"
    board.tile(6, 3).terrain = "building"
    board.tile(6, 3).building_hp = 2
    board.tile(6, 2).terrain = "building"
    board.tile(6, 2).building_hp = 1
    board.tile(5, 3).conveyor = 0
    board.units.append(_enemy(
        uid=136,
        pawn_type="Scorpion1",
        x=5,
        y=3,
        tx=6,
        ty=3,
        hp=3,
    ))
    board.units[-1].weapon = "ScorpionAtk1"
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "WARN"
    assert audit["still_threatened_count"] == 1
    assert audit["entries"][0]["coverage"]["reason"] == "still_threatened_after_conveyor"


def test_threat_audit_frozen_building_target_is_thaw_covered():
    board = Board()
    tile = board.tile(2, 3)
    tile.terrain = "building"
    tile.building_hp = 1
    tile.frozen = True
    board.units.append(_enemy(
        uid=973,
        pawn_type="Scarab1",
        x=4,
        y=3,
        tx=2,
        ty=3,
        hp=2,
    ))
    board.units[-1].weapon = "ScarabAtk1"
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == "target_frozen_building"


def test_threat_audit_still_threatened_warns():
    initial = capture_building_threats(_board())

    audit = audit_threat_coverage(initial, _board())

    assert audit["status"] == "WARN"
    assert audit["still_threatened_count"] == 1
    assert audit["entries"][0]["coverage"]["reason"] == "still_threatened"


def test_threat_audit_single_shielded_building_target_is_covered():
    board = _board()
    board.tile(4, 2).shield = True
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == (
        "target_shielded_building"
    )


def test_threat_audit_shield_does_not_cover_multiple_building_threats():
    board = _board()
    board.tile(4, 2).shield = True
    board.units.append(_enemy(uid=11))
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

    assert audit["status"] == "WARN"
    assert audit["still_threatened_count"] == 2
    assert {
        entry["coverage"]["reason"] for entry in audit["entries"]
    } == {"still_threatened"}


def test_threat_audit_environment_hit_can_consume_building_shield_first():
    board = _board()
    board.tile(4, 2).shield = True
    board.environment_danger_v2[(4, 2)] = (1, False)
    initial = capture_building_threats(board)

    audit = audit_threat_coverage(initial, board)

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
