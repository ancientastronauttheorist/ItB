"""Native-derived target admission regressions; no live game operations."""
import json

import pytest

from scripts.solver_first_primitive_search import build_case, encode


def test_distant_tank_clicks_accept_same_ray_outcome():
    import itb_solver
    board = encode(build_case())
    results = []
    for target in ([2, 3], [1, 3], [0, 3]):
        results.append(json.loads(itb_solver.replay_primitives(board, encode([
            dict(kind="use", mech_uid=0, weapon_id="Brute_Tankmech", target=target)]))))
    assert results[0] == results[1] == results[2]
    with pytest.raises(ValueError, match="invalid_weapon_target"):
        itb_solver.replay_primitives(board, encode([
            dict(kind="use", mech_uid=0, weapon_id="Brute_Tankmech", target=[5, 3])]))


def corpse_case():
    return dict(tiles=[], units=[
        dict(uid=0, type="TankMech", x=3, y=3, hp=3, max_hp=3, team=1,
             mech=True, active=True, can_move=True, move=3, weapons=["Brute_Tankmech"]),
        dict(uid=1, type="PunchMech", x=1, y=3, hp=0, max_hp=3, team=1,
             mech=True, active=False, can_move=False, weapons=["Prime_Punchmech"]),
        dict(uid=2, type="Firefly1", x=0, y=3, hp=3, max_hp=3, team=6,
             mech=False, active=False, weapons=["FireflyAtk1"]),
    ], turn=1, total_turns=1, grid_power=7, spawning_tiles=[])


def test_base_tank_stops_at_existing_persistent_corpse():
    import itb_solver
    replay = json.loads(itb_solver.replay_solution(encode(corpse_case()), encode([
        dict(mech_uid=0, move_to=[3, 3], weapon_id="Brute_Tankmech", target=[2, 3])])))
    post = replay["predicted_states"][0]["post_attack"]
    assert next(u["hp"] for u in post["units"] if u["uid"] == 2) == 3


def test_target_area_is_distinct_from_search_representatives():
    import itb_solver
    report = json.loads(itb_solver.inspect_base_target_area(encode(build_case()), 0, "Brute_Tankmech"))
    assert len(report["targets"]) == 11
    assert len(report["search_representatives"]) == 4
    assert [1, 3] in report["targets"] and [5, 3] not in report["targets"]


@pytest.mark.parametrize("corpse", [False, True])
def test_dead_nonmech_occupancy_requires_persistent_corpse(corpse):
    import itb_solver
    board = corpse_case()
    board["units"][1].update(mech=False, corpse=corpse)
    report = json.loads(itb_solver.inspect_base_target_area(encode(board), 0, "Brute_Tankmech"))
    assert ([0, 3] in report["targets"]) is (not corpse)


def test_target_area_exposes_unsupported_weapon_family():
    import itb_solver
    with pytest.raises(ValueError, match="unsupported_base_target_area"):
        itb_solver.inspect_base_target_area(encode(build_case()), 0, "Brute_Tankmech_A")
