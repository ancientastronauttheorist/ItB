from src.loop.commands import (
    _candidate_dirty_frontier,
    _candidate_frontier_representatives,
    _is_harmless_active_state_diff,
    _is_expected_skip_state_diff,
    _prepare_projected_bridge,
    _select_safe_plan_candidate,
)
from src.solver.verify import DiffResult


def _candidate(rank: int, blocking: bool, status: str = "CLEAN") -> dict:
    return {
        "rank": rank,
        "plan_safety": {
            "status": "DIRTY" if blocking else status,
            "blocking": blocking,
            "violations": [],
        },
    }


def test_safe_candidate_selection_skips_dirty_top_plan():
    candidates = [
        _candidate(0, blocking=True),
        _candidate(1, blocking=False),
        _candidate(2, blocking=False),
    ]

    selected = _select_safe_plan_candidate(candidates)

    assert selected["rank"] == 1


def test_safe_candidate_selection_preserves_top_when_all_dirty():
    candidates = [
        _candidate(0, blocking=True),
        _candidate(1, blocking=True),
    ]

    selected = _select_safe_plan_candidate(candidates)

    assert selected["rank"] == 0


def test_safe_candidate_selection_accepts_warn_candidate():
    candidates = [
        _candidate(0, blocking=True),
        _candidate(1, blocking=False, status="WARN"),
    ]

    selected = _select_safe_plan_candidate(candidates)

    assert selected["rank"] == 1


def test_dirty_frontier_keeps_best_candidate_per_tradeoff():
    summaries = [
        {
            "rank": 0,
            "source": "top_k_safety",
            "score": 10.0,
            "blocking": True,
            "loss_profile": {
                "label": "grid_loss",
                "losses": {"grid_power": 1},
            },
            "violations": [{"kind": "grid_damage"}],
        },
        {
            "rank": 1,
            "source": "top_k_safety",
            "score": 8.0,
            "blocking": True,
            "loss_profile": {
                "label": "mech_loss",
                "losses": {"mechs_alive": 1},
            },
            "violations": [{"kind": "mech_lost"}],
        },
        {
            "rank": 2,
            "source": "top_k_safety",
            "score": 7.0,
            "blocking": True,
            "loss_profile": {
                "label": "grid_loss",
                "losses": {"grid_power": 1},
            },
            "violations": [{"kind": "grid_damage"}],
        },
    ]

    frontier = _candidate_dirty_frontier(summaries)

    assert [item["label"] for item in frontier] == ["grid_loss", "mech_loss"]
    assert frontier[0]["best_rank"] == 0
    assert frontier[0]["count"] == 2
    assert frontier[1]["best_rank"] == 1
    assert frontier[1]["losses"] == {"mechs_alive": 1}


def test_frontier_representatives_pick_one_per_label():
    def candidate(rank, label):
        return {
            "rank": rank,
            "plan_safety": {
                "status": "DIRTY",
                "blocking": True,
                "violations": [
                    {
                        "kind": "grid_damage" if label == "grid_loss" else "mech_lost",
                        "current": 3,
                        "predicted": 2,
                        "delta": -1,
                    },
                ],
            },
        }

    reps = _candidate_frontier_representatives([
        candidate(3, "grid_loss"),
        candidate(1, "mech_loss"),
        candidate(0, "grid_loss"),
    ])

    assert [c["rank"] for c in reps] == [0, 1]


def test_prepare_projected_bridge_preserves_solver_metadata():
    projected = {
        "tiles": [],
        "units": [],
        "eval_weights": {"pseudo_threat_eval": True},
    }
    source = {
        "disabled_actions": [{"weapon_id": "Prime_Punchmech"}],
        "weapon_overrides": [{"weapon_id": "Deploy_TankShot"}],
    }

    out = _prepare_projected_bridge(
        projected,
        source,
        {"grid_power": 123.0},
    )

    assert out["eval_weights"]["grid_power"] == 123.0
    assert out["eval_weights"]["pseudo_threat_eval"] is True
    assert out["disabled_actions"] == source["disabled_actions"]
    assert out["weapon_overrides"] == source["weapon_overrides"]


def test_skip_active_state_diff_is_expected():
    diff = DiffResult(unit_diffs=[
        {"uid": 7, "type": "FlameMech", "field": "active",
         "predicted": True, "actual": False},
    ])

    assert _is_expected_skip_state_diff(diff, mech_uid=7) is True


def test_skip_diff_with_position_change_is_not_ignored():
    diff = DiffResult(unit_diffs=[
        {"uid": 7, "type": "FlameMech", "field": "active",
         "predicted": True, "actual": False},
        {"uid": 7, "type": "FlameMech", "field": "pos",
         "predicted": [1, 1], "actual": [2, 1]},
    ])

    assert _is_expected_skip_state_diff(diff, mech_uid=7) is False


def test_skip_diff_with_tile_change_is_not_ignored():
    diff = DiffResult(
        unit_diffs=[
            {"uid": 7, "type": "FlameMech", "field": "active",
             "predicted": True, "actual": False},
        ],
        tile_diffs=[
            {"x": 2, "y": 3, "field": "building_hp",
             "predicted": 1, "actual": 0},
        ],
    )

    assert _is_expected_skip_state_diff(diff, mech_uid=7) is False


def test_prior_active_state_drift_is_harmless_for_completed_mech():
    diff = DiffResult(unit_diffs=[
        {"uid": 7, "type": "FlameMech", "field": "active",
         "predicted": True, "actual": False},
    ])

    assert _is_harmless_active_state_diff(diff, allowed_uids={7}) is True


def test_active_state_drift_for_unfinished_mech_is_not_ignored():
    diff = DiffResult(unit_diffs=[
        {"uid": 8, "type": "SwapMech", "field": "active",
         "predicted": True, "actual": False},
    ])

    assert _is_harmless_active_state_diff(diff, allowed_uids={7}) is False


def test_active_state_reactivation_is_not_harmless():
    diff = DiffResult(unit_diffs=[
        {"uid": 7, "type": "FlameMech", "field": "active",
         "predicted": False, "actual": True},
    ])

    assert _is_harmless_active_state_diff(diff, allowed_uids={7}) is False
