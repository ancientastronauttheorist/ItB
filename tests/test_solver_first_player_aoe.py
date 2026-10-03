"""Bounded v411 integration and reference sensitivity, never live play."""
from hashlib import sha256
import json

import itb_solver
import pytest

from scripts.solver_first_bounded_search import ReferenceError, encode
from scripts.solver_first_player_aoe import (
    ARTEMIS, DIRECTIONS, EVIDENCE, ROOT, VARIANTS, artemis_case,
    artemis_plans, assert_splitshot_projection, checked_result,
    evaluate_artemis, splitshot_case,
)
from src.model.weapons import get_weapon_def, weapon_name_to_id
from src.solver.verify import SIMULATOR_VERSION


def test_source_receipts_and_variant_model_definitions():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["simulator_version"] == 411
    assert evidence["original_execution_admissions"] == evidence["held_out_cases"] == 0
    assert all(value == 0 for value in evidence["accounting"].values())
    for pin in evidence["inventory_pins"]:
        path = (ROOT / pin["path"]).resolve()
        assert path.is_relative_to(ROOT)
        assert sha256(path.read_bytes()).hexdigest() == pin["raw_sha256"]
    inventory = json.loads((ROOT / evidence["inventory_pins"][0]["path"]).read_text(encoding="utf-8"))
    members = {item["path"]: item for item in inventory["content"]["scripts"]["files"]}
    for path, receipt in evidence["game_sources"].items():
        assert (members[path]["sha256"], members[path]["size"]) == (receipt["raw_sha256"], receipt["size"])
    assert evidence["laws"]["splitshot"]["side_offsets"] == ["(dy,-dx)", "(-dy,dx)"]
    assert tuple(evidence["laws"]["artemis"]["supported_ids"]) == ARTEMIS
    known = json.loads((ROOT / "data/known_types.json").read_text(encoding="utf-8"))
    for weapon, (damage, limited) in VARIANTS.items():
        definition = get_weapon_def(weapon)
        assert (definition.damage, definition.limited, definition.push,
                definition.aoe_perpendicular) == (damage, limited, "outward", True)
        assert evidence["laws"]["splitshot"]["variants"][weapon] == dict(damage=damage, limited=limited)
        assert weapon.replace("_", "") in known["weapon_enum"]
    assert weapon_name_to_id("Split Shot") == "Brute_Splitshot"


@pytest.mark.parametrize("weapon", VARIANTS)
@pytest.mark.parametrize("direction", DIRECTIONS)
def test_splitshot_all_variants_rotations_saved_endpoint(weapon, direction):
    assert itb_solver.simulator_version() == SIMULATOR_VERSION >= 411
    board, plan, expected = splitshot_case(weapon, direction)
    _, replay = checked_result(itb_solver, board, plan)
    assert_splitshot_projection(replay, expected)


@pytest.mark.parametrize("weapon", ARTEMIS)
def test_source_targets_include_buildings_and_all_ten_shots(weapon):
    board = artemis_case(weapon)
    plans = list(artemis_plans(board))
    assert len(plans) == len({encode(plan) for plan in plans}) == 12
    shots = {tuple(p[0]["target"]) for p in plans if p[0]["weapon_id"] == weapon}
    assert shots == {(3, 0), (3, 1), (3, 2), (3, 3), (3, 4),
                     (0, 6), (1, 6), (5, 6), (6, 6), (7, 6)}
    assert {p[0]["weapon_id"] for p in plans} == {weapon, "", "_REPAIR"}


@pytest.mark.parametrize("mutation", ["can_move", "extra_field", "ignored_grid_defense", "missing_enemy", "building_hp", "variant"])
def test_armed_reference_fails_closed_outside_frozen_domain(mutation):
    board = artemis_case(ARTEMIS[0])
    if mutation == "can_move":
        board["units"][0]["can_move"] = True
    elif mutation == "extra_field":
        board["hidden_rng"] = 5
    elif mutation == "ignored_grid_defense":
        board["grid_defense"] = 0
    elif mutation == "missing_enemy":
        board["units"].pop()
    elif mutation == "building_hp":
        next(t for t in board["tiles"] if (t["x"], t["y"]) == (3, 3))["building_hp"] = 2
    else:
        board["units"][0]["weapons"] = ["Ranged_Artillerymech_B"]
    with pytest.raises(ReferenceError):
        list(artemis_plans(board))


def test_archived_counterexample_keeps_old_legality_failure_and_configuration_boundary():
    raw = (ROOT / "data/solver_first/s2_artemis_410_counterexample.json").read_bytes()
    assert sha256(raw).hexdigest() == "99d39977f4c6bb4a81b48a3b9ac296969b65b6926fd60d4f27f0e15377956446"
    before = json.loads(raw)
    assert before["version"] == 410
    assert before["scored"]["illegal_events"] == ["illegal_weapon_target:3:3:Artemis Artillery"]
    assert before["scored"]["grid_power"] == 0
    assert before["scored"]["bldgs_alive"] == 1
    assert before["input"]["grid_defense"] == 0  # ignored by the historical parser
    assert "grid_defense" not in artemis_case(ARTEMIS[0])


@pytest.mark.parametrize("weapon", ARTEMIS)
def test_artemis_complete_single_actor_reference_matches_sacrifice_decision(weapon):
    result = evaluate_artemis(itb_solver, weapon, 10.0)
    assert result["reference_complete"] and result["reference_leaves"] == 12
    assert result["objective_parity"] and result["regret"] == 0
    assert result["selected_plan"][0]["target"] == [3, 3]
    assert result["proof_status"] == "best_found"
    assert result["certificate"] is result["valid_bounds"] is None
    if weapon == ARTEMIS[0]:
        assert not result["reference_policy_best"]["clean"]
        assert result["raw_best"]["score"] - result["clean_best"]["score"] > result["clean_threshold"]
        assert result["final_projection"] == dict(grid_power=1, buildings_alive=2)
    else:
        assert result["reference_policy_best"]["clean"]
        assert result["final_projection"] == dict(grid_power=2, buildings_alive=3)


@pytest.mark.parametrize("mutation", ["main_push", "side_damage", "moved_anchor"])
def test_splitshot_projection_detects_semantic_perturbation(mutation):
    _, _, expected = splitshot_case("Brute_Splitshot", (1, 0))
    units = [dict(uid=uid, **values) for uid, values in expected.items()]
    if mutation == "main_push":
        units[0]["x"] -= 1
    elif mutation == "side_damage":
        units[1]["hp"] += 1
    else:
        units[3]["hp"] -= 2
    with pytest.raises(ReferenceError, match="projection differs"):
        assert_splitshot_projection(dict(post_player_board=dict(units=units)), expected)


@pytest.mark.parametrize("mutation", ["illegal_score", "error_snapshot", "illegal_replay"])
def test_shared_oracle_rejection_is_never_silently_dropped(mutation):
    class InvalidOracle:
        def score_plan(self, board, plan):
            return encode(dict(score=0.0, illegal_events=["illegal_weapon_target"] if mutation == "illegal_score" else []))

        def replay_solution(self, board, plan):
            snapshot = {"error": "mech_not_found"} if mutation == "error_snapshot" else {}
            return encode(dict(action_results=[dict(events=["illegal_move"] if mutation == "illegal_replay" else [])],
                               predicted_states=[dict(post_move=snapshot, post_attack={})],
                               post_player_board={}, final_board={}))

    board = artemis_case(ARTEMIS[0])
    with pytest.raises(ReferenceError):
        checked_result(InvalidOracle(), board, next(artemis_plans(board)))
