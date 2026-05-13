from src.loop.commands import (
    _blocks_mech_hp_loss_for_perfect_battle,
    _candidate_dirty_frontier,
    _candidate_frontier_representatives,
    _is_harmless_active_state_diff,
    _is_expected_skip_state_diff,
    _lookahead_result_sort_key,
    _lookahead_robust_frontier,
    _lookahead_robust_summary,
    _prepare_projected_bridge,
    _select_candidate_by_rank,
    _select_safe_plan_candidate,
)
from src.loop.session import RunSession
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


def test_dirty_candidate_selection_minimizes_mech_hp_with_same_blocking_loss():
    def dirty(rank: int, mech_hp_total: int) -> dict:
        return {
            "rank": rank,
            "plan_safety": {
                "status": "DIRTY",
                "blocking": True,
                "violations": [
                    {
                        "kind": "grid_damage",
                        "blocking": True,
                        "current": 5,
                        "predicted": 4,
                        "delta": -1,
                    },
                    {
                        "kind": "building_hp_loss",
                        "blocking": True,
                        "current": 5,
                        "predicted": 4,
                        "delta": -1,
                    },
                    {
                        "kind": "mech_hp_loss",
                        "blocking": False,
                        "current": 7,
                        "predicted": mech_hp_total,
                        "delta": mech_hp_total - 7,
                    },
                ],
                "current": {"mech_hp_total": 7},
                "predicted": {"mech_hp_total": mech_hp_total},
            },
        }

    selected = _select_safe_plan_candidate([
        dirty(0, mech_hp_total=6),
        dirty(110, mech_hp_total=7),
    ])

    assert selected["rank"] == 110


def test_safe_candidate_selection_accepts_warn_candidate():
    candidates = [
        _candidate(0, blocking=True),
        _candidate(1, blocking=False, status="WARN"),
    ]

    selected = _select_safe_plan_candidate(candidates)

    assert selected["rank"] == 1


def test_requested_candidate_selection_uses_exact_rank():
    candidates = [
        _candidate(0, blocking=True),
        _candidate(3, blocking=True),
    ]

    selected = _select_candidate_by_rank(candidates, 3)

    assert selected["rank"] == 3


def test_requested_candidate_selection_missing_rank_returns_none():
    candidates = [_candidate(0, blocking=True)]

    assert _select_candidate_by_rank(candidates, 3) is None


def test_perfect_battle_target_enables_mech_hp_safety_mode(tmp_path, monkeypatch):
    achievements_path = tmp_path / "achievements_detailed.json"
    achievements_path.write_text(
        '{"achievements": {"squad": [{"name": "Perfect Battle", "completed": false}]}}'
    )
    monkeypatch.setattr(
        "src.loop.commands.ACHIEVEMENTS_PATH",
        achievements_path,
    )
    session = RunSession(achievement_targets=["Perfect Battle"])

    assert _blocks_mech_hp_loss_for_perfect_battle(session) is True


def test_non_perfect_battle_target_keeps_default_mech_hp_safety_mode():
    session = RunSession(achievement_targets=["Stormy Weather"])

    assert _blocks_mech_hp_loss_for_perfect_battle(session) is False


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


def test_dirty_frontier_splits_grid_loss_by_magnitude():
    def summary(rank, grid_loss):
        return {
            "rank": rank,
            "source": "top_k_safety",
            "score": 100.0 - rank,
            "blocking": True,
            "loss_profile": {
                "label": "grid_loss",
                "blocking": True,
                "losses": {"grid_power": grid_loss},
            },
            "violations": [{"kind": "grid_damage"}],
        }

    frontier = _candidate_dirty_frontier([
        summary(0, 2),
        summary(1, 1),
        summary(2, 2),
    ])

    assert [item["losses"] for item in frontier] == [
        {"grid_power": 2},
        {"grid_power": 1},
    ]
    assert frontier[0]["count"] == 2
    assert frontier[1]["count"] == 1


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


def test_frontier_representatives_split_same_label_by_loss_magnitude():
    def candidate(rank, grid_loss):
        return {
            "rank": rank,
            "plan_safety": {
                "status": "DIRTY",
                "blocking": True,
                "violations": [
                    {
                        "kind": "grid_damage",
                        "current": 5,
                        "predicted": 5 - grid_loss,
                        "delta": -grid_loss,
                    },
                ],
            },
        }

    reps = _candidate_frontier_representatives([
        candidate(0, 2),
        candidate(1, 1),
        candidate(2, 2),
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


def test_lookahead_result_sort_key_orders_dirty_before_clean():
    dirty = {
        "status": "OK",
        "next_score": 100.0,
        "next_plan_safety": {
            "blocking": True,
            "loss_profile": {"non_overridable": False},
        },
    }
    clean = {
        "status": "OK",
        "next_score": -100.0,
        "next_plan_safety": {
            "blocking": False,
            "loss_profile": {"non_overridable": False},
        },
    }
    error = {"status": "ERROR"}

    ordered = sorted([clean, dirty, error], key=_lookahead_result_sort_key)

    assert ordered == [error, dirty, clean]


def test_lookahead_robust_summary_combines_current_and_worst_next_score():
    item = {
        "status": "OK",
        "candidate_label": "grid_loss",
        "candidate_rank": 4,
        "candidate_score": 1000.0,
        "scenario_count": 3,
        "worst_scenario": "retarget_building_uid10_4_3",
        "next_score": -250.0,
        "next_plan_safety": {
            "blocking": False,
            "loss_profile": {"label": "clean", "non_overridable": False},
        },
    }

    summary = _lookahead_robust_summary(item)

    assert summary["robust_status"] == "clean"
    assert summary["robust_score"] == 750.0
    assert summary["next_loss_label"] == "clean"


def test_lookahead_robust_frontier_sorts_by_status_then_score():
    clean_low = {
        "status": "OK",
        "candidate_label": "grid_loss",
        "candidate_rank": 0,
        "candidate_score": 100.0,
        "next_score": 10.0,
        "next_plan_safety": {
            "blocking": False,
            "loss_profile": {"label": "clean", "non_overridable": False},
        },
    }
    dirty_high = {
        "status": "OK",
        "candidate_label": "mech_loss",
        "candidate_rank": 1,
        "candidate_score": 10_000.0,
        "next_score": 10_000.0,
        "next_plan_safety": {
            "blocking": True,
            "loss_profile": {"label": "grid_loss", "non_overridable": False},
        },
    }
    clean_high = {
        "status": "OK",
        "candidate_label": "building_loss",
        "candidate_rank": 2,
        "candidate_score": 200.0,
        "next_score": 20.0,
        "next_plan_safety": {
            "blocking": False,
            "loss_profile": {"label": "clean", "non_overridable": False},
        },
    }

    frontier = _lookahead_robust_frontier([clean_low, dirty_high, clean_high])

    assert [item["candidate_label"] for item in frontier] == [
        "building_loss",
        "grid_loss",
        "mech_loss",
    ]


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
