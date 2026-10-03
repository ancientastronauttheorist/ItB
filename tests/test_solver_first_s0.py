"""Independent boundary tests; synthetic checks are not original-game traces."""

from copy import deepcopy
import json

import pytest

from scripts.solver_first_s0 import corridor, loaded_extension_path, verify_inventory
from src.solver.observation_contract import (
    ObservationBoundaryError, encode_observation, player_observation,
)
from src.solver.evidence_reconciliation import build_movement_index
from pathlib import Path


def test_contract_accounts_for_every_parser_wire_field_and_alias():
    assert verify_inventory() == {"JsonInput": 43, "JsonTile": 24, "JsonUnit": 49}


def test_oracle_changes_and_engine_identity_do_not_change_planner_input():
    a = corridor(True, 2)
    b = deepcopy(a)
    a.update(rng_state=1, future_spawns=[[7, 7]], remaining_spawns=0)
    b.update(rng_state=999, future_spawns=[[1, 1]], remaining_spawns=50)
    b["units"][0]["uid"] = 491
    assert encode_observation(a) == encode_observation(b)


def test_unit_order_and_private_identifiers_preserve_displayed_attack_order():
    a = {"units": [{"uid": 99, "x": 3, "y": 2, "type": "Scarab1"},
                   {"uid": 7, "x": 1, "y": 1, "type": "Firefly1"}], "attack_order": [99, 7]}
    b = {"units": [{"uid": 500, "x": 1, "y": 1, "type": "Firefly1"},
                   {"uid": 300, "x": 3, "y": 2, "type": "Scarab1"}], "attack_order": [300, 500]}
    assert encode_observation(a) == encode_observation(b)
    assert player_observation(a)["attack_order"] == [1, 0]


@pytest.mark.parametrize("patch", [
    {"mission_final_cave": {"planned": [[1, 1]]}},
    {"weapon_overrides_runtime": []}, {"eval_weights": {}},
    {"new_future_field": 1},
])
def test_unreviewed_or_state_supplied_configuration_fails_closed(patch):
    with pytest.raises(ObservationBoundaryError):
        player_observation({**corridor(True, 2), **patch})


def test_nested_unknown_field_is_not_hidden_by_top_level_filter():
    raw = corridor(True, 2)
    raw["units"][0]["secret_target"] = [7, 7]
    with pytest.raises(ObservationBoundaryError, match="secret_target"):
        player_observation(raw)


def test_structured_leaf_cannot_smuggle_oracle_fields():
    with pytest.raises(ObservationBoundaryError, match="structured leaf"):
        player_observation({"spawning_tiles": [{"rng_state": 1}]})


def test_projection_is_detached_and_visible_changes_still_matter():
    raw = corridor(True, 2)
    result = player_observation(raw)
    result["units"][0]["hp"] = 1
    assert raw["units"][0]["hp"] == 3
    other = deepcopy(raw)
    other["units"][0]["massive"] = False
    assert encode_observation(raw) != encode_observation(other)


def test_tile_order_and_grappled_alias_are_canonicalized():
    a = corridor(True, 2)
    b = deepcopy(a)
    a["units"][0]["grappled"] = False
    b["units"][0]["is_grappled"] = False
    b["tiles"].reverse()
    assert encode_observation(a) == encode_observation(b)


def test_loaded_extension_identity_is_the_implementation_module():
    import importlib
    import itb_solver
    from pathlib import Path
    assert loaded_extension_path(itb_solver) == Path(importlib.import_module(itb_solver.solve.__module__).__file__)


@pytest.mark.parametrize("field", ["tiles", "units"])
def test_duplicate_visible_identity_is_rejected(field):
    raw = corridor(True, 2)
    raw[field].append(deepcopy(raw[field][0]))
    with pytest.raises(ObservationBoundaryError, match="duplicate|ambiguous"):
        player_observation(raw)


def test_reconciliation_matches_atlas_without_promoting_functions():
    result = build_movement_index(Path(__file__).resolve().parents[1])
    assert result["ledger"] == {"atlas_functions": 25312, "level_L0": 25312,
                                "level_L1": 0, "level_L2": 0,
                                "reviewed_functions": 0, "reviewed_exclusions": 0}
    assert result["ledger_promotions"] == 0
    assert len(result["receipts"]) == 8
    assert result["retained_case_sum"] == 576
    assert result["retained_negative_control_sum"] == 502
    assert [len(row["matched_atlas_bodies"]) for row in result["atlas_joins"]] == [4, 20, 21]


def test_real_solver_receives_identical_inputs_for_oracle_pair():
    import itb_solver
    a = corridor(True, 2)
    b = deepcopy(a)
    a["rng_state"] = 1
    b["rng_state"] = 42
    # This tractable development board closes well within the budget. Compare
    # recommendations, not elapsed-time telemetry or broader search guarantees.
    first = json.loads(itb_solver.solve(encode_observation(a), 1.0))
    second = json.loads(itb_solver.solve(encode_observation(b), 1.0))
    assert first["actions"] == second["actions"]
    assert first["score"] == second["score"]


@pytest.mark.parametrize("massive,speed,destination,legal", [
    (True, 2, [0, 1], True), (True, 2, [0, 2], True),
    (False, 2, [0, 1], False), (False, 2, [0, 2], False),
    (True, 1, [0, 2], False), (True, 2, [0, 3], False),
])
def test_budget_and_water_rule_through_actual_rust_replay(massive, speed, destination, legal):
    import itb_solver
    plan = [{"mech_uid": 0, "move_to": destination, "weapon_id": "None", "target": destination}]
    replay = json.loads(itb_solver.replay_solution(encode_observation(corridor(massive, speed)), json.dumps(plan)))
    events = replay["action_results"][0]["events"]
    assert (not any(e.startswith("illegal_move:") for e in events)) == legal
    assert replay["predicted_states"][0]["post_move"]["units"][0]["pos"] == (destination if legal else [0, 0])
