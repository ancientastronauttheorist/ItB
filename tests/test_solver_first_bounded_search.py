"""Independent reference sensitivity; these tests never import the Rust runtime."""
from copy import deepcopy
import json
import math

import pytest

from scripts.solver_first_bounded_search import (
    Counts, REPAIR, WAIT, ReferenceError, advance, build_case, choices,
    destinations, evaluate_case, plans, validate_domain, validate_plan,
)


def player(board, name="PunchMech"):
    return next(u for u in board["units"] if u["type"] == name)


def action(uid, pos, weapon=WAIT):
    return dict(mech_uid=uid, move_to=list(pos), weapon_id=weapon,
                target=list(pos) if weapon == REPAIR else [255, 255])


def test_single_actor_has_all_eight_stops_and_both_choices():
    board = build_case(1)
    uid = player(board)["uid"]
    expected = {(x, y) for x in range(2, 5) for y in range(2, 5)} - {(2, 3)}
    assert set(destinations(board, uid)) == expected
    counts = Counts()
    leaves = list(plans(board, counts))
    assert len(leaves) == counts.leaves_emitted == 16
    assert {(tuple(p[0]["move_to"]), p[0]["weapon_id"]) for p in leaves} == {
        (pos, weapon) for pos in expected for weapon in (WAIT, REPAIR)}


def test_friendly_corridor_transit_does_not_admit_occupied_stop():
    # A hand-calculated corridor has no alternate route around its occupant.
    board = build_case(2)
    for tile in board["tiles"]:
        tile["terrain"] = "ground" if tile["x"] == 0 and tile["y"] < 4 else "mountain"
    first, second = player(board), player(board, "TankMech")
    first.update(x=0, y=0)
    second.update(x=0, y=1)
    assert set(destinations(board, first["uid"])) == {(0, 0), (0, 2), (0, 3)}
    second["team"] = 6
    assert destinations(board, first["uid"]) == ((0, 0),)


def test_budget_and_can_move_are_independent_constraints():
    board = build_case(1)
    actor = player(board)
    actor["move"] = 1
    assert set(destinations(board, actor["uid"])) == {(3, 2), (2, 2), (4, 2), (3, 3)}
    actor["can_move"] = False
    assert destinations(board, actor["uid"]) == ((3, 2),)


def test_vacated_start_can_be_used_only_after_its_occupant_moves():
    board = build_case(2)
    first, second = player(board), player(board, "TankMech")
    assert (3, 2) not in destinations(board, second["uid"])
    moved = advance(board, action(first["uid"], (3, 3)))
    assert (3, 2) in destinations(moved, second["uid"])
    with pytest.raises(ReferenceError, match="unavailable"):
        destinations(moved, first["uid"])


@pytest.mark.parametrize("count", [1, 2, 3])
def test_orders_and_complete_unique_actor_coverage(count):
    board, counters = build_case(count), Counts()
    actors = set(validate_domain(board))
    for plan in plans(board, counters):
        assert len(plan) == count
        assert {a["mech_uid"] for a in plan} == actors
    assert len(counters.orders) == math.factorial(count)
    assert counters.leaves_emitted <= math.factorial(count) * (2 * (9 - count)) ** count


def test_full_hp_repair_remains_legal_and_wounded_repair_heals():
    board = build_case(1, full_hp=True)
    actor = player(board)
    no_op = action(actor["uid"], (3, 2), REPAIR)
    assert no_op in list(choices(board, actor["uid"]))
    assert player(advance(board, no_op))["hp"] == 3
    board = build_case(1)
    assert player(advance(board, no_op))["hp"] == 2


@pytest.mark.parametrize("fault", ["duplicate", "omit", "target", "target2", "weapon", "far"])
def test_returned_plan_fails_closed(fault):
    board = build_case(2)
    plan = [action(player(board)["uid"], (3, 2)),
            action(player(board, "TankMech")["uid"], (4, 2))]
    if fault == "duplicate":
        plan[1] = deepcopy(plan[0])
    elif fault == "omit":
        plan.pop()
    elif fault == "target":
        plan[0]["target"] = [3, 2]
    elif fault == "target2":
        plan[0]["target2"] = [3, 2]
    elif fault == "weapon":
        plan[0]["weapon_id"] = "Prime_Punchmech"
    else:
        plan[0]["move_to"] = [0, 0]
    with pytest.raises(ReferenceError):
        validate_plan(board, plan)


@pytest.mark.parametrize("fault", ["hidden", "pilot", "tile", "roster", "hp"])
def test_domain_rejects_feature_expansion(fault):
    board = build_case(1)
    if fault == "hidden":
        board["rng_state"] = 17
    elif fault == "pilot":
        player(board)["pilot_id"] = "Pilot_Repairman"
    elif fault == "tile":
        board["tiles"][0]["acid"] = False
    elif fault == "roster":
        board["units"].append(deepcopy(board["units"][0]))
    else:
        player(board)["hp"] = 0
    with pytest.raises(ReferenceError):
        validate_domain(board)


def synthetic_score(_board_json, plan_json):
    # An intentional selection oracle, not a replacement combat simulator.
    act = json.loads(plan_json)[0]
    return json.dumps(dict(score=1 if act["move_to"] == [3, 3] and act["weapon_id"] == REPAIR else 0,
                           illegal_events=[]))


def fixed_solver(board, *, block=False, reported_score=None):
    uid = player(board)["uid"]
    chosen = action(uid, (3, 3) if block else (3, 2), REPAIR if block else WAIT)
    score = (1 if block else 0) if reported_score is None else reported_score
    return lambda *_: json.dumps(dict(actions=[chosen], score=score, stats={"timed_out": True}))


def test_regret_uses_rescore_and_detects_missing_best_selection():
    board = build_case(1)
    result = evaluate_case(board, synthetic_score, fixed_solver(board), solver_budget=1)
    assert result["reference_complete"] and result["status"] == "complete"
    assert result["counts"]["leaves_scored"] == 16
    assert result["regret"] == 1 and not result["matches_reference_best"]
    assert result["root_best_found"] and result["root_proof_status"] == "best_found"
    assert result["objective_parity_established"]
    assert result["solver_reported_minus_rescored"] == 0
    result = evaluate_case(board, synthetic_score, fixed_solver(board, block=True), solver_budget=1)
    assert result["regret"] == 0 and result["matches_reference_best"]
    # A timed-out solver may still find the known optimum of this complete
    # reference; its telemetry is retained without becoming exhaustive proof.
    assert result["solver_stats"]["timed_out"]


def test_reported_objective_mismatch_prevents_admission_even_at_reference_best():
    board = build_case(1)
    result = evaluate_case(board, synthetic_score, fixed_solver(board, block=True, reported_score=42), solver_budget=1)
    assert result["reference_complete"] and result["regret"] == 0
    assert result["matches_reference_best"]
    assert result["status"] == "objective_mismatch" and not result["objective_parity_established"]
    assert not result["root_best_found"] and result["solver_reported_minus_rescored"] == 41


def test_leaf_limit_cannot_be_reported_as_exhaustive():
    board = build_case(1)
    result = evaluate_case(board, synthetic_score, fixed_solver(board), solver_budget=1, max_leaves=1)
    assert result["status"] == "incomplete" and not result["root_best_found"]
    assert not result["reference_complete"] and result["counts"]["leaves_scored"] == 1
    assert "exhaustive_best_score" not in result


@pytest.mark.parametrize("response", [dict(score=float("nan"), illegal_events=[]),
                                      dict(score=0), dict(score=0, illegal_events=["illegal_move"])] )
def test_oracle_failures_are_visible_and_never_silently_pruned(response):
    board = build_case(1)
    result = evaluate_case(board, lambda *_: json.dumps(response), fixed_solver(board), solver_budget=1)
    assert result["status"] == "incomplete" and not result["reference_complete"]
    assert result["counts"]["reference_oracle_failures"] == 1 and result["counts"]["leaves_scored"] == 0
