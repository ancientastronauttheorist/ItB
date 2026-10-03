"""Reference graph checks; only the explicitly opt-in integration uses Rust."""
import json
import os

import pytest

from scripts.solver_first_primitive_search import (
    Counts, ReferenceError, build_case, closing_choices, destinations, encode,
    evaluate_case, project, reference, selected_policy, validate_domain,
    validate_projected_terrain,
)


@pytest.mark.parametrize("fault", ["inactive", "can_move", "pilot", "environment", "tile", "ally", "type"])
def test_exact_fixture_readiness_fails_closed(fault):
    board = build_case()
    if fault == "inactive":
        board["units"][0]["active"] = False
    elif fault == "can_move":
        board["units"][0]["can_move"] = False
    elif fault == "pilot":
        board["units"][0]["pilot"] = "unexpected"
    elif fault == "environment":
        board["environment_danger"] = []
    elif fault == "tile":
        board["tiles"][0]["acid"] = False
    elif fault == "ally":
        board["units"][0]["mech"] = False
    else:
        board["units"][0]["hp"] = True
    with pytest.raises(ReferenceError, match="exact"):
        validate_domain(board)


def test_bfs_friendly_transit_without_occupied_stop():
    board = build_case()
    assert (3, 3) not in destinations(board, 1)
    # Move the origin one tile closer to expose the stop past the friendly
    # occupant within the fixed three-step budget.
    board["units"][1].update(x=1, y=3)
    assert (3, 4) in destinations(board, 1)
    assert (3, 3) not in destinations(board, 1)
    assert (4, 3) not in destinations(board, 1)  # enemy blocks
    board["units"][0]["hp"] = 0  # wreck blocks friendly transit too
    assert (3, 4) not in destinations(board, 1)


def test_bfs_no_noop_or_hazard_stops_and_can_move_consumed():
    board = build_case()
    assert set(destinations(board, 0)) == {(0, 3), (1, 3), (2, 3), (3, 4), (4, 4), (5, 4)} - {(0, 3)}
    assert (3, 3) not in destinations(board, 0)
    board["units"][0]["can_move"] = False
    assert destinations(board, 0) == ()


def test_destroyed_building_rubble_is_a_reachable_stop():
    board = build_case()
    board["units"][2]["hp"] = 0  # current Rust projection supplies this death
    tile = next(t for t in board["tiles"] if (t["x"], t["y"]) == (4, 2))
    tile.update(terrain="rubble", building_hp=0)
    validate_projected_terrain(board)
    assert (4, 2) in destinations(board, 0)
    # Intact building is neither a stop nor a transit tile.
    tile.update(terrain="building", building_hp=1)
    assert (4, 2) not in destinations(board, 0)


@pytest.mark.parametrize("fault", ["unknown_terrain", "new_rubble", "rubble_hp", "duplicate"])
def test_projected_terrain_consequences_fail_closed(fault):
    board = build_case()
    if fault == "unknown_terrain":
        board["tiles"][0]["terrain"] = "water"
    elif fault == "new_rubble":
        board["tiles"][3]["terrain"] = "rubble"  # originally Ground
    elif fault == "rubble_hp":
        tile = next(t for t in board["tiles"] if t["terrain"] == "building")
        tile.update(terrain="rubble", building_hp=1)
    else:
        board["tiles"][1] = dict(board["tiles"][0])
    with pytest.raises(ReferenceError, match="projected|consequence"):
        validate_projected_terrain(board)


def test_four_directions_repair_and_wait_are_not_effect_pruned():
    actions = list(closing_choices(build_case(), 0))
    assert len(actions) == 6
    assert {tuple(a["target"]) for a in actions if a.get("weapon_id") == "Brute_Tankmech"} == {
        (3, 4), (4, 3), (3, 2), (2, 3)}
    assert any(a.get("weapon_id") == "_REPAIR" for a in actions)
    assert actions[-1] == dict(kind="wait", mech_uid=0)


WITNESS = [dict(kind="move", mech_uid=0, to=[5, 4]),
           dict(kind="move", mech_uid=1, to=[3, 3]),
           dict(kind="use", mech_uid=1, weapon_id="Prime_Punchmech", target=[4, 3]),
           dict(kind="use", mech_uid=0, weapon_id="Brute_Tankmech", target=[5, 3])]


def graph_only_oracle(board_json, steps_json):
    """Mock readiness/movement only, no combat simulator or damage model."""
    board, steps = json.loads(board_json), json.loads(steps_json)
    flags = {uid: dict(uid=uid, moved=False, used=False) for uid in (0, 1)}
    for step in steps:
        uid, kind = step["mech_uid"], step["kind"]
        unit, entitlement = board["units"][uid], flags[uid]
        if entitlement["used"]:
            raise ValueError("already used")
        if kind == "move":
            if entitlement["moved"]:
                raise ValueError("already moved")
            unit["x"], unit["y"] = step["to"]
            entitlement["moved"] = True
        else:
            entitlement["moved"] = entitlement["used"] = True
            unit["active"] = False
        unit["can_move"] = not (entitlement["moved"] or entitlement["used"])
    complete = all(e["used"] for e in flags.values())
    return dict(schema_version=1,
                scope={"readiness": "ordinary_once_per_turn; no extra movement/use grants"},
                post_player_board=board, actor_entitlements=list(flags.values()),
                complete=complete, score=(1 if steps == WITNESS else 0) if complete else None,
                clean=True if complete else None, final_board=board if complete else None,
                admissions=[{} for _ in steps],
                action_results=[dict(buildings_damaged=0, events=[]) for _ in steps])


def test_prefix_move_keeps_use_entitlement():
    counts = Counts()
    result = project(graph_only_oracle, encode(build_case()), WITNESS[:1], counts)
    assert not result["complete"]
    assert result["post_player_board"]["units"][0]["active"] is True
    assert result["post_player_board"]["units"][0]["can_move"] is False
    assert counts.prefix_attempts == counts.prefix_admitted == 1


def test_oracle_failure_is_retained_not_skipped():
    def broken(*_):
        raise ValueError("native rejection")
    result, _ = reference(build_case(), broken)
    assert not result["complete"]
    assert result["counts"]["prefix_attempts"] == result["counts"]["oracle_failures"] == 1
    assert result["counts"]["prefix_admitted"] == 0


def test_readiness_disagreement_fails_closed():
    def broken(board, steps):
        value = graph_only_oracle(board, steps)
        value["post_player_board"]["units"][0]["active"] = False
        return value
    with pytest.raises(ReferenceError, match="readiness"):
        project(broken, encode(build_case()), [], Counts())


def test_consistently_wrong_oracle_readiness_cannot_shrink_reference_graph():
    def broken(board, steps):
        value = graph_only_oracle(board, steps)
        if steps:
            value["actor_entitlements"][0].update(moved=True, used=True)
            value["post_player_board"]["units"][0].update(active=False, can_move=False)
        return value
    with pytest.raises(ReferenceError, match="independent prefix ledger"):
        project(broken, encode(build_case()), WITNESS[:1], Counts())


def test_missing_actor_is_not_silently_treated_as_dead():
    def broken(board, steps):
        value = graph_only_oracle(board, steps)
        value["post_player_board"]["units"].pop(0)
        return value
    with pytest.raises(ReferenceError, match="actor/wreck disappeared"):
        project(broken, encode(build_case()), [], Counts())


def test_sparse_default_ground_normalization_preserves_topology():
    def sparse(board, steps):
        value = graph_only_oracle(board, steps)
        value["post_player_board"]["tiles"] = [t for t in value["post_player_board"]["tiles"]
                                                 if t["terrain"] != "ground"]
        return value
    result = project(sparse, encode(build_case()), [], Counts())
    assert len(result["post_player_board"]["tiles"]) == 64
    assert destinations(result["post_player_board"], 0) == destinations(build_case(), 0)


def test_sparse_nondefault_tile_disappearance_fails_closed():
    def broken(board, steps):
        value = graph_only_oracle(board, steps)
        value["post_player_board"]["tiles"].pop(0)
        return value
    with pytest.raises(ReferenceError, match="non-default tile disappeared"):
        project(broken, encode(build_case()), [], Counts())


def test_nonlethal_building_damage_cannot_be_marked_clean():
    def broken(board, steps):
        value = graph_only_oracle(board, steps)
        tile = next(t for t in value["post_player_board"]["tiles"] if t["terrain"] == "building")
        tile["building_hp"] = 1
        value["action_results"][0]["buildings_damaged"] = 1
        return value
    waits = [dict(kind="wait", mech_uid=0), dict(kind="wait", mech_uid=1)]
    with pytest.raises(ReferenceError, match="independent building classification"):
        project(broken, encode(build_case()), waits, Counts())


def test_returned_rejection_event_cannot_be_an_admitted_leaf():
    def broken(board, steps):
        value = graph_only_oracle(board, steps)
        value["action_results"][0]["events"] = ["illegal_move: rejected"]
        return value
    with pytest.raises(ReferenceError, match="rejected action event"):
        project(broken, encode(build_case()), WITNESS[:1], Counts())


def test_interleaving_reference_and_compound_sensitivity():
    atomic, members = reference(build_case(), graph_only_oracle)
    compound, compound_members = reference(build_case(), graph_only_oracle, compound=True)
    assert atomic["complete"] and compound["complete"]
    assert encode(WITNESS) in members and encode(WITNESS) not in compound_members
    assert atomic["raw_best"]["score"] == 1 and compound["raw_best"]["score"] == 0
    assert atomic["counts"]["leaves_scored"] > compound["counts"]["leaves_scored"]


def test_production_rescore_detects_regret_without_claim_promotion():
    def solve(*_):
        return dict(steps=[dict(kind="wait", mech_uid=0), dict(kind="wait", mech_uid=1)],
                    score=0, proof_status="best_found", certificate=None, valid_bounds=None)
    result = evaluate_case(build_case(), graph_only_oracle, solve)
    assert result["status"] == "complete" and result["score_parity"]
    assert result["raw_regret"] == 1 and not result["matches_reference_policy"]
    assert result["root_proof_status"] == "best_found"
    assert result["original_execution_admissions"] == result["held_out_cases"] == 0


def test_clean_policy_threshold_and_raw_fallback():
    raw = dict(score=10000, clean=False)
    assert selected_policy(raw, dict(score=9500, clean=True))["clean"]
    assert selected_policy(raw, dict(score=9499, clean=True)) is raw
    assert selected_policy(dict(score=100, clean=False), dict(score=-400, clean=True))["clean"]


def test_budget_failure_does_not_claim_exhaustion():
    result, _ = reference(build_case(), graph_only_oracle, max_nodes=1)
    assert not result["complete"] and result["counts"]["deadline_cutoffs"] == 1


@pytest.mark.skipif(os.environ.get("ITB_RUN_PRIMITIVE_NATIVE") != "1",
                    reason="Primary explicitly enables after native extension build")
def test_native_corridor_witness_differential():
    import itb_solver
    require_api = getattr(itb_solver, "replay_primitives", None)
    assert require_api is not None
    board_json = encode(build_case())
    witness = project(require_api, board_json, WITNESS, Counts())
    assert witness["complete"] and witness["clean"]
    assert witness["score"] == pytest.approx(70420.0)
    result = evaluate_case(build_case(), require_api, itb_solver.solve_primitives,
                           reference_budget=120.0)
    assert result["status"] == "complete" and result["score_parity"]
    assert result["selected_membership"] and result["matches_reference_policy"]
    assert result["primitive_minus_compound_raw"] > 500
