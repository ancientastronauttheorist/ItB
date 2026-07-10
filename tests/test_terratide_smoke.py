from src.model.board import Board, Unit
from src.solver.threat_audit import (
    audit_threat_coverage,
    capture_building_threats,
)

def _terratide_bridge() -> dict:
    return {
        "mission_id": "Mission_Terratide",
        "env_type": "sandstorm",
        "grid_power": 3,
        "tiles": [],
        "units": [],
        "environment_danger": [[5, 3]],
        "environment_danger_v2": [[5, 3, 1, 0, 0]],
    }


def _scorpion() -> Unit:
    return Unit(
        uid=171,
        type="Scorpion1",
        x=5,
        y=3,
        hp=4,
        max_hp=4,
        team=6,
        is_mech=False,
        move_speed=3,
        flying=False,
        massive=False,
        armor=False,
        pushable=True,
        weapon="ScorpionAtk1",
        active=False,
        target_x=5,
        target_y=2,
        has_queued_attack=True,
    )


def _threat_board() -> Board:
    board = Board()
    board.tile(5, 2).terrain = "building"
    board.tile(5, 2).building_hp = 2
    board.units.append(_scorpion())
    return board


def test_terratide_warning_routes_to_pending_smoke_not_damage():
    board = Board.from_bridge_data(_terratide_bridge())

    assert board.environment_smoke == {(5, 3)}
    assert board.environment_danger == set()
    assert board.environment_danger_v2 == {}


def test_threat_audit_credits_attacker_on_pending_terratide_smoke():
    before = _threat_board()
    initial = capture_building_threats(before)

    after = before.copy()
    after.mission_id = "Mission_Terratide"
    after.environment_smoke.add((5, 3))
    audit = audit_threat_coverage(initial, after)

    assert audit["status"] == "OK"
    assert audit["still_threatened_count"] == 0
    assert audit["entries"][0]["coverage"]["reason"] == (
        "attacker_will_be_smoked_by_environment"
    )
