"""Installed Rust search reporting; no live/session operations."""
import json

import itb_solver

from scripts.solver_first_bounded_search import build_case


def parse_solve(board, budget=10.0):
    return json.loads(itb_solver.solve(json.dumps(board), budget))


def assert_best_found(solution):
    assert solution["proof_status"] == "best_found"
    assert solution["certificate"] is None
    assert solution["valid_bounds"] is None
    assert solution["horizon_player_turns"] == 1


def test_completed_search_reports_actual_counts_and_stable_output():
    board = build_case(3)
    first = parse_solve(board)
    assert_best_found(first)
    audit = first["stats"]["search_audit"]
    assert audit["order_passes_scheduled"] == 6
    assert audit["order_passes_started"] == audit["order_passes_completed"] == 6
    assert audit["terminal_plans_evaluated"] > 1000
    assert audit["nodes_visited"] > audit["terminal_plans_evaluated"]
    assert audit["deadline_cutoffs"] == audit["action_limit_pruned"] == 0
    assert first["stats"]["retained_candidate_tree_exhausted"]
    for _ in range(3):
        other = parse_solve(board)
        assert other["actions"] == first["actions"]
        assert other["score"] == first["score"]
        assert other["stats"]["search_audit"] == audit


def test_zero_budget_does_not_count_scheduled_orders_as_tried():
    solution = parse_solve(build_case(3), 0.0)
    assert_best_found(solution)
    assert solution["stats"]["permutations_tried"] == 0
    audit = solution["stats"]["search_audit"]
    assert audit["order_passes_scheduled"] == 6
    assert audit["order_passes_started"] == audit["order_passes_completed"] == 0
    assert audit["deadline_cutoffs"] == 6
    assert not solution["stats"]["retained_candidate_tree_exhausted"]


def test_top_k_preserves_shared_whole_invocation_audit():
    output = json.loads(itb_solver.solve_top_k(json.dumps(build_case(1)), 10.0, 2))
    assert len(output) == 2
    for solution in output:
        assert_best_found(solution)
    assert output[0]["stats"]["search_audit"] == output[1]["stats"]["search_audit"]
    assert output[0]["stats"]["search_audit"]["terminal_plans_evaluated"] == 16


def test_beam_reports_chain_scope_and_invocation_local_audits():
    board = build_case(1)
    board["total_turns"] = 4
    chains = json.loads(itb_solver.solve_beam(json.dumps(board), 2, 2, 10.0))
    assert len(chains) == 2
    assert chains[0]["level_0"]["stats"]["search_audit"] == chains[1]["level_0"]["stats"]["search_audit"]
    for chain in chains:
        assert chain["proof_status"] == "best_found"
        assert chain["certificate"] is None and chain["valid_bounds"] is None
        assert chain["requested_horizon_player_turns"] == 2
        assert_best_found(chain["level_0"])
        if chain["level_1_best"] is not None:
            assert_best_found(chain["level_1_best"])
            assert chain["level_1_best"]["stats"]["search_audit"]["passes_executed"] == 1
