"""Sensitivity checks for empty-result regression admission, isolated from live play."""
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def corpus_module():
    path = Path(__file__).with_name("test_regression_corpus.py")
    spec = importlib.util.spec_from_file_location("_itb_failure_corpus_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_board():
    return dict(turn=1, total_turns=5, tiles=[], units=[
        dict(uid=0, type="TankMech", x=3, y=3, hp=3, max_hp=3, team=1,
             mech=True, active=True, move=3, weapons=["Brute_Tankmech"]),
        dict(uid=1, type="Firefly1", x=4, y=4, hp=3, max_hp=3, team=6,
             mech=False, active=False, weapons=["FireflyAtk1"]),
    ])


def configure_single_case(module, monkeypatch, tmp_path, board):
    (tmp_path / "board.json").write_text(json.dumps(dict(data=dict(bridge_state=board))))
    weights = tmp_path / "weights.json"
    weights.write_text(json.dumps(dict(weights={})))
    monkeypatch.setattr(module, "REPO", tmp_path)
    monkeypatch.setattr(module, "ACTIVE_WEIGHTS_PATH", weights)
    monkeypatch.setattr(module, "_load_known_issues", lambda: set())
    monkeypatch.setattr(module, "_dedup_failure_corpus", lambda: [dict(
        run_id="guard_fixture", mission=0, turn=1, trigger="self_damage_building",
        replay_file="board.json")])


def test_injected_empty_solution_on_canonical_board_fails(corpus_module, monkeypatch, tmp_path):
    import itb_solver
    configure_single_case(corpus_module, monkeypatch, tmp_path, canonical_board())
    monkeypatch.setattr(itb_solver, "solve", lambda *_: json.dumps(dict(
        actions=[], score=0.0, stats=dict(timed_out=False))))
    with pytest.raises(AssertionError, match="empty solution on active board"):
        corpus_module.test_failure_corpus_not_regressed()


@pytest.mark.parametrize("actor,expected", [
    ({}, True),
    ({"active": False}, False),
    ({"hp": 0}, False),
    ({"team": 2}, False),
    ({"is_extra_tile": True}, False),
    ({"team": None}, True),
    ({"mech": False, "type": "Snowtank1_Player", "weapons": ["SnowtankAtk1"]}, True),
    ({"mech": False, "type": "VIP_Truck", "weapons": [], "move": 3}, True),
    ({"mech": False, "type": "VIP_Truck", "weapons": [], "move": 0}, False),
    ({"mech": False, "type": "Unarmed_Ally", "weapons": []}, False),
    ({"mech": False, "type": "Unknown_Ally", "weapons": ["unknown_weapon"]}, False),
    ({"frozen": True}, True),
])
def test_native_actor_admission_uses_parser_and_mission_actor_predicate(actor, expected):
    import itb_solver
    board = canonical_board()
    board["units"][0].update(actor)
    report = json.loads(itb_solver.inspect_admission(json.dumps(board)))
    assert report["schema_version"] == 1
    assert report["requires_actions"] is expected
    assert report["actor_uids"] == ([0] if expected else [])
    assert report["enemy_uids"] == [1]


def test_burrowed_enemy_is_counted_without_serialized_board_loss():
    import itb_solver
    board = canonical_board()
    board["units"][1].update(burrowed=True)
    report = json.loads(itb_solver.inspect_admission(json.dumps(board)))
    assert report["enemy_uids"] == [1] and report["requires_actions"]


def test_no_living_enemy_does_not_require_actions():
    import itb_solver
    board = canonical_board()
    board["units"][1]["hp"] = 0
    report = json.loads(itb_solver.inspect_admission(json.dumps(board)))
    assert report["actor_uids"] == [0]
    assert report["enemy_uids"] == [] and not report["requires_actions"]


def test_prepared_input_and_empty_native_timeout_survive_wrapper(corpus_module, monkeypatch):
    import itb_solver
    monkeypatch.setattr(itb_solver, "solve", lambda *_: json.dumps(dict(
        actions=[], score=10.0, stats=dict(timed_out=True))))
    solution, admission, raw = corpus_module._solve_with_admission(canonical_board(), {})
    assert not solution.actions and not solution.timed_out  # Existing wrapper drops it.
    assert admission["requires_actions"] and raw["stats"]["timed_out"]
    assert corpus_module._empty_result_error(admission, raw) is None


@pytest.mark.parametrize("score", [None, float("nan"), float("inf"), "10", True])
def test_nonfinite_empty_native_score_is_not_a_timeout_escape(corpus_module, score):
    reason = corpus_module._empty_result_error(dict(requires_actions=True), dict(
        score=score, stats=dict(timed_out=True)))
    assert reason and "score absent/nonfinite" in reason


@pytest.mark.parametrize("stats", [None, {}, dict(timed_out=False),
                                   dict(timed_out=1), dict(timed_out="true")])
def test_only_explicit_native_timeout_accepts_required_empty_result(corpus_module, stats):
    reason = corpus_module._empty_result_error(dict(requires_actions=True), dict(
        score=10.0, stats=stats))
    assert reason and "not timed out" in reason
