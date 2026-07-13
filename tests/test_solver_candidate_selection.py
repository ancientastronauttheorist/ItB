import json
from types import SimpleNamespace

import src.loop.commands as commands
from src.loop.commands import (
    _blocks_mech_hp_loss_for_perfect_battle,
    _blocks_mech_status_loss_for_run,
    _candidate_dirty_frontier,
    _candidate_frontier_representatives,
    _is_harmless_active_state_diff,
    _is_expected_skip_state_diff,
    _is_implausible_stale_verify_actual,
    _lookahead_result_sort_key,
    _lookahead_forecast_gaps,
    _lookahead_robust_frontier,
    _lookahead_robust_summary,
    _prepare_projected_bridge,
    _recommend_dirty_candidate_from_robust,
    _safety_widening_top_k,
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


def test_dirty_candidate_prefers_overridable_loss_to_objective_loss():
    objective_loss = {
        "rank": 0,
        "plan_safety": {
            "status": "DIRTY",
            "blocking": True,
            "violations": [
                {
                    "kind": "protected_objective_unit_lost",
                    "blocking": True,
                    "current": 1,
                    "predicted": 0,
                }
            ],
        },
    }
    grid_loss = {
        "rank": 3694,
        "plan_safety": {
            "status": "DIRTY",
            "blocking": True,
            "violations": [
                {
                    "kind": "grid_damage",
                    "blocking": True,
                    "current": 4,
                    "predicted": 3,
                }
            ],
        },
    }

    selected = _select_safe_plan_candidate([objective_loss, grid_loss])

    assert selected["rank"] == 3694


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


def test_protected_objective_loss_uses_deeper_safety_widening():
    plan_safety = {
        "blocking": True,
        "violations": [
            {
                "kind": "protected_objective_unit_lost",
                "blocking": True,
            }
        ],
    }

    assert _safety_widening_top_k(plan_safety) > 1000


def test_protected_objective_degradation_uses_deeper_safety_widening():
    plan_safety = {
        "blocking": True,
        "violations": [
            {
                "kind": "protected_objective_unit_degraded",
                "blocking": True,
            }
        ],
    }

    assert _safety_widening_top_k(plan_safety) > 1000


def test_ordinary_safety_loss_keeps_default_widening():
    plan_safety = {
        "blocking": True,
        "violations": [{"kind": "grid_damage", "blocking": True}],
    }

    assert _safety_widening_top_k(plan_safety) == 1000


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


def test_untouchable_target_enables_mech_hp_safety_mode(tmp_path, monkeypatch):
    achievements_path = tmp_path / "achievements_detailed.json"
    achievements_path.write_text(
        '{"achievements": {"global": [{"name": "Untouchable", "completed": false}]}}'
    )
    monkeypatch.setattr(
        "src.loop.commands.ACHIEVEMENTS_PATH",
        achievements_path,
    )
    session = RunSession(achievement_targets=["Untouchable"])

    assert _blocks_mech_hp_loss_for_perfect_battle(session) is True


def test_lightning_war_target_enables_mech_hp_safety_mode(tmp_path, monkeypatch):
    achievements_path = tmp_path / "achievements_detailed.json"
    achievements_path.write_text(
        '{"achievements": {"global": [{"name": "Lightning War", "completed": false}]}}'
    )
    monkeypatch.setattr(
        "src.loop.commands.ACHIEVEMENTS_PATH",
        achievements_path,
    )
    session = RunSession(achievement_targets=["Lightning War"])

    assert _blocks_mech_hp_loss_for_perfect_battle(session) is True


def test_lightning_war_target_blocks_mech_status_loss():
    session = RunSession(achievement_targets=["Lightning War"], difficulty=0)

    assert _blocks_mech_status_loss_for_run(session) is True


def test_completed_untouchable_target_keeps_default_mech_hp_safety_mode(tmp_path, monkeypatch):
    achievements_path = tmp_path / "achievements_detailed.json"
    achievements_path.write_text(
        '{"achievements": {"global": [{"name": "Untouchable", "completed": true}]}}'
    )
    monkeypatch.setattr(
        "src.loop.commands.ACHIEVEMENTS_PATH",
        achievements_path,
    )
    session = RunSession(achievement_targets=["Untouchable"])

    assert _blocks_mech_hp_loss_for_perfect_battle(session) is False


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


def test_frontier_representatives_append_required_candidate_after_limit():
    def candidate(rank, grid_loss):
        return {
            "rank": rank,
            "plan_safety": {
                "status": "DIRTY",
                "blocking": True,
                "violations": [
                    {
                        "kind": "grid_damage",
                        "current": 10,
                        "predicted": 10 - grid_loss,
                        "delta": -grid_loss,
                    },
                ],
            },
        }

    candidates = [
        candidate(0, 1),
        candidate(1, 2),
        candidate(2, 3),
        candidate(3, 4),
        candidate(4, 5),
    ]
    required = candidate(183, 6)
    candidates.append(required)

    reps = _candidate_frontier_representatives(
        candidates,
        required_candidate=required,
    )
    already_included = _candidate_frontier_representatives(
        candidates,
        required_candidate=candidates[0],
    )

    assert [c["rank"] for c in reps] == [0, 1, 2, 3, 4, 183]
    assert [c["rank"] for c in already_included] == [0, 1, 2, 3, 4]


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


def test_lookahead_safety_uses_projected_spawn_markers(monkeypatch):
    projected = {
        "turn": 2,
        "total_turns": 5,
        "remaining_spawns": 1,
        "spawning_tiles": [[2, 2]],
        "tiles": [],
        "units": [],
    }
    scenario = {
        "label": "heuristic_requeue",
        "board_json": json.dumps(projected),
        "action_result": {"spawns_blocked": 1},
    }
    next_solution = SimpleNamespace(score=20.0, actions=[])
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        commands,
        "_projected_scenarios",
        lambda *_args, **_kwargs: [scenario],
    )
    monkeypatch.setattr(
        commands.Board,
        "from_bridge_data",
        lambda _bridge: object(),
    )
    monkeypatch.setattr(commands, "_active_player_action_count", lambda _board: 1)
    monkeypatch.setattr(
        commands,
        "_rust_result_to_solution",
        lambda *_args, **_kwargs: next_solution,
    )

    def fake_safety(_board, _bridge, _solution, spawns, **_kwargs):
        captured["spawns"] = spawns
        return {
            "plan_safety": {
                "status": "CLEAN",
                "blocking": False,
                "violations": [],
            },
        }

    monkeypatch.setattr(commands, "_evaluate_solution_safety", fake_safety)

    class FakeRust:
        @staticmethod
        def solve(_bridge_json, _time_limit):
            return "{}"

    preview = commands._candidate_lookahead_preview(
        FakeRust(),
        {"spawning_tiles": [[2, 2], [5, 5]]},
        {
            "rank": 0,
            "source": "test",
            "solution": SimpleNamespace(score=10.0, actions=[]),
            "plan_safety": {"status": "DIRTY", "blocking": True},
        },
        eval_weights_dict=None,
        breakdown_weights=SimpleNamespace(),
        time_limit=1.0,
    )

    assert preview["status"] == "OK"
    assert captured["spawns"] == [(2, 2)]


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


def test_lookahead_result_sort_key_treats_incomplete_as_unresolved_evidence():
    incomplete = {
        "status": "OK",
        "forecast_complete": False,
        "next_score": 10_000.0,
        "next_plan_safety": {
            "blocking": False,
            "loss_profile": {"non_overridable": False},
        },
    }
    dirty = {
        "status": "OK",
        "forecast_complete": True,
        "next_score": -100.0,
        "next_plan_safety": {
            "blocking": True,
            "loss_profile": {"non_overridable": False},
        },
    }

    ordered = sorted([dirty, incomplete], key=_lookahead_result_sort_key)

    assert ordered == [incomplete, dirty]


def test_incomplete_forecast_preserves_known_objective_loss_severity():
    incomplete_objective_dirty = {
        "status": "OK",
        "forecast_complete": False,
        "next_score": 10_000.0,
        "next_plan_safety": {
            "blocking": True,
            "loss_profile": {"non_overridable": True},
        },
    }
    incomplete_clean = {
        "status": "OK",
        "forecast_complete": False,
        "next_score": -10_000.0,
        "next_plan_safety": {
            "blocking": False,
            "loss_profile": {"non_overridable": False},
        },
    }

    ordered = sorted(
        [incomplete_clean, incomplete_objective_dirty],
        key=_lookahead_result_sort_key,
    )

    assert ordered == [incomplete_objective_dirty, incomplete_clean]
    assert _lookahead_robust_summary(
        incomplete_objective_dirty
    )["robust_status"] == "incomplete_objective_dirty"


def test_lookahead_forecast_gaps_expose_mobile_enemies_and_spawns():
    projected = {
        "remaining_spawns": 1,
        "spawning_tiles": [],
        "units": [
            {"uid": 10, "team": 6, "hp": 3, "move": 3},
            {"uid": 11, "team": 6, "hp": 3, "move": 3, "frozen": True},
            {"uid": 12, "team": 6, "hp": 3, "move": 3, "web": True},
            {"uid": 13, "team": 6, "hp": 3, "move": 0},
            {"uid": 0, "team": 1, "hp": 3, "move": 3},
        ],
    }

    gaps = _lookahead_forecast_gaps(
        projected,
        {"spawns_blocked": 0},
        source_spawning_tiles=[[5, 5]],
    )

    assert [gap["kind"] for gap in gaps] == [
        "enemy_movement_unmodeled",
        "enemy_retarget_unmodeled",
        "spawn_materialization_unmodeled",
    ]
    assert gaps[0]["enemy_uids"] == [10]
    assert gaps[1]["enemy_uids"] == [12]
    assert gaps[2]["unmodeled_emergence_count"] == 1
    assert gaps[2]["persisting_spawn_markers"] == []


def test_lookahead_forecast_is_complete_when_only_immobile_enemies_remain():
    projected = {
        "remaining_spawns": 0,
        "spawning_tiles": [],
        "units": [
            {"uid": 11, "team": 6, "hp": 3, "move": 3, "frozen": True},
            {"uid": 13, "team": 6, "hp": 3, "move": 0},
        ],
    }

    assert _lookahead_forecast_gaps(
        projected,
        {},
        source_spawning_tiles=[],
    ) == []


def test_lookahead_forecast_tracks_emerged_vek_after_marker_consumption():
    projected = {
        "remaining_spawns": 0,
        "spawning_tiles": [],
        "units": [],
    }

    gaps = _lookahead_forecast_gaps(
        projected,
        {"spawns_blocked": 0},
        source_spawning_tiles=[[5, 5]],
    )

    assert gaps == [{
        "kind": "spawn_materialization_unmodeled",
        "source_spawn_markers": [[5, 5]],
        "persisting_spawn_markers": [],
        "reported_spawns_blocked": 0,
        "unmodeled_emergence_count": 1,
        "unmodeled_emergence_tiles": [[5, 5]],
        "projected_remaining_spawns": 0,
    }]


def test_lookahead_forecast_keeps_persisting_spawn_pressure_incomplete():
    gaps = _lookahead_forecast_gaps(
        {
            "remaining_spawns": 0,
            "spawning_tiles": [[2, 2]],
            "units": [],
        },
        {"spawns_blocked": 1},
        source_spawning_tiles=[[2, 2]],
    )

    assert gaps[0]["kind"] == "spawn_materialization_unmodeled"
    assert gaps[0]["unmodeled_emergence_count"] == 0
    assert gaps[0]["persisting_spawn_markers"] == [[2, 2]]


def test_lookahead_forecast_separates_emerged_and_persisting_markers():
    gaps = _lookahead_forecast_gaps(
        {
            "remaining_spawns": 0,
            "spawning_tiles": [[2, 2]],
            "units": [],
        },
        {"spawns_blocked": 1},
        source_spawning_tiles=[[2, 2], [5, 5]],
    )

    assert gaps == [{
        "kind": "spawn_materialization_unmodeled",
        "source_spawn_markers": [[2, 2], [5, 5]],
        "persisting_spawn_markers": [[2, 2]],
        "reported_spawns_blocked": 1,
        "unmodeled_emergence_count": 1,
        "unmodeled_emergence_tiles": [[5, 5]],
        "projected_remaining_spawns": 0,
    }]


def test_lookahead_forecast_fails_closed_on_spawn_lifecycle_mismatch():
    gaps = _lookahead_forecast_gaps(
        {
            "remaining_spawns": 0,
            "spawning_tiles": [[2, 2]],
            "units": [],
        },
        {"spawns_blocked": 0},
        source_spawning_tiles=[[5, 5]],
    )

    assert gaps[0]["kind"] == "spawn_marker_lifecycle_inconsistent"
    assert gaps[0]["unexpected_projected_markers"] == [[2, 2]]
    assert gaps[0]["reported_spawns_blocked"] == 0
    assert gaps[1]["kind"] == "spawn_materialization_unmodeled"


def test_lookahead_forecast_is_incomplete_for_webbed_enemy_retarget():
    gaps = _lookahead_forecast_gaps({
        "remaining_spawns": 0,
        "spawning_tiles": [],
        "units": [
            {"uid": 12, "team": 6, "hp": 3, "move": 3, "web": True},
        ],
    }, source_spawning_tiles=[])

    assert gaps == [{
        "kind": "enemy_retarget_unmodeled",
        "reason": "webbed_enemy_skipped_by_stationary_retarget",
        "enemy_count": 1,
        "enemy_uids": [12],
    }]


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


def test_lookahead_robust_summary_does_not_call_incomplete_forecast_clean():
    item = {
        "status": "OK",
        "forecast_model": "stationary_retarget_v1",
        "forecast_complete": False,
        "forecast_gaps": [{"kind": "enemy_movement_unmodeled"}],
        "candidate_label": "grid_loss",
        "candidate_rank": 4,
        "candidate_score": 1000.0,
        "next_score": 250.0,
        "next_plan_safety": {
            "blocking": False,
            "loss_profile": {"label": "clean", "non_overridable": False},
        },
    }

    summary = _lookahead_robust_summary(item)

    assert summary["robust_status"] == "incomplete"
    assert summary["forecast_complete"] is False
    assert summary["forecast_gaps"] == item["forecast_gaps"]


def test_dirty_robust_recommendation_can_spend_hp_for_same_irreversible_loss():
    def candidate(
        rank,
        score,
        mech_hp_loss,
        *,
        building_destroyed=True,
        pod_lost=False,
    ):
        violations = [
            {
                "kind": "grid_damage",
                "blocking": True,
                "current": 4,
                "predicted": 2,
            },
            {
                "kind": "building_hp_loss",
                "blocking": True,
                "current": 9,
                "predicted": 7,
            },
        ]
        if building_destroyed:
            violations.append({
                "kind": "building_destroyed",
                "blocking": True,
                "current": 7,
                "predicted": 6,
            })
        if pod_lost:
            violations.append({
                "kind": "pod_lost",
                "blocking": True,
                "current": 1,
                "predicted": 0,
            })
        if mech_hp_loss:
            violations.append({
                "kind": "mech_hp_loss",
                "blocking": False,
                "current": 8,
                "predicted": 8 - mech_hp_loss,
            })
        return {
            "rank": rank,
            "source": "top_k_safety",
            "solution": SimpleNamespace(
                score=score,
                actions=[SimpleNamespace(description=f"candidate {rank}")],
            ),
            "plan_safety": {
                "status": "DIRTY",
                "blocking": True,
                "current": {"mech_hp_total": 8},
                "predicted": {"mech_hp_total": 8 - mech_hp_loss},
                "violations": violations,
            },
        }

    selected = candidate(183, -177_643.0, 0)
    reserve = candidate(4, -124_643.0, 1)
    robust = [
        {
            "candidate_rank": 4,
            "candidate_source": "top_k_safety",
            "candidate_losses": {
                "grid_power": 2,
                "buildings_alive": 1,
                "building_hp_total": 2,
                "mech_hp_total": 1,
            },
            "robust_status": "incomplete",
            "robust_score": -115_118.0,
            "forecast_complete": False,
            "forecast_gaps": [{"kind": "enemy_movement_unmodeled"}],
        },
        {
            "candidate_rank": 183,
            "candidate_source": "top_k_safety",
            "candidate_losses": {
                "grid_power": 2,
                "buildings_alive": 1,
                "building_hp_total": 2,
            },
            "robust_status": "incomplete",
            "robust_score": -211_118.0,
            "forecast_complete": False,
            "forecast_gaps": [{"kind": "enemy_movement_unmodeled"}],
        },
    ]

    recommendation = _recommend_dirty_candidate_from_robust(
        selected,
        [selected, reserve],
        robust,
        explicit_candidate_rank=False,
    )

    assert recommendation["candidate_rank"] == 4
    assert recommendation["selected_candidate_rank"] == 183
    assert recommendation["same_irreversible_loss"] is True
    assert recommendation["forecast_complete"] is False
    assert recommendation["actions"] == ["candidate 4"]
    assert _recommend_dirty_candidate_from_robust(
        selected,
        [selected, reserve],
        robust,
        explicit_candidate_rank=True,
    ) is None
    tied = [dict(robust[0], robust_score=-211_118.0), robust[1]]
    assert _recommend_dirty_candidate_from_robust(
        selected,
        [selected, reserve],
        tied,
        explicit_candidate_rank=False,
    ) is None

    pod_default = candidate(
        0,
        -124_236.0,
        1,
        building_destroyed=False,
        pod_lost=True,
    )
    cross_signature_robust = [
        robust[0],
        {
            "candidate_rank": 0,
            "candidate_source": "top_k_safety",
            "candidate_losses": {
                "grid_power": 2,
                "building_hp_total": 2,
                "pods_present": 1,
                "mech_hp_total": 1,
            },
            "robust_status": "incomplete_objective_dirty",
            "robust_score": -242_692.0,
            "forecast_complete": False,
            "forecast_gaps": [{"kind": "enemy_movement_unmodeled"}],
        },
    ]
    tradeoff = _recommend_dirty_candidate_from_robust(
        pod_default,
        [pod_default, reserve],
        cross_signature_robust,
        explicit_candidate_rank=False,
    )

    assert tradeoff["candidate_rank"] == 4
    assert tradeoff["same_irreversible_loss"] is False
    assert tradeoff["reason"] == "best_evaluated_robust_overridable_tradeoff"
    assert tradeoff["selected_candidate_losses"]["pods_present"] == 1

    worse_grid = candidate(5, 1_000_000.0, 1)
    next(
        violation for violation in worse_grid["plan_safety"]["violations"]
        if violation["kind"] == "grid_damage"
    )["predicted"] = 1
    unsafe_cross_signature = [
        {
            "candidate_rank": 5,
            "candidate_source": "top_k_safety",
            "candidate_losses": {
                "grid_power": 3,
                "buildings_alive": 1,
                "building_hp_total": 2,
                "mech_hp_total": 1,
            },
            "robust_status": "clean",
            "robust_score": 2_000_000.0,
            "forecast_complete": True,
            "forecast_gaps": [],
        },
        cross_signature_robust[1],
    ]
    assert _recommend_dirty_candidate_from_robust(
        pod_default,
        [pod_default, worse_grid],
        unsafe_cross_signature,
        explicit_candidate_rank=False,
    ) is None


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
    incomplete_huge = {
        "status": "OK",
        "forecast_complete": False,
        "forecast_gaps": [{"kind": "enemy_movement_unmodeled"}],
        "candidate_label": "incomplete_grid_loss",
        "candidate_rank": 3,
        "candidate_score": 1_000_000.0,
        "next_score": 1_000_000.0,
        "next_plan_safety": {
            "blocking": False,
            "loss_profile": {"label": "clean", "non_overridable": False},
        },
    }

    frontier = _lookahead_robust_frontier([
        clean_low,
        dirty_high,
        clean_high,
        incomplete_huge,
    ])

    assert [item["candidate_label"] for item in frontier] == [
        "building_loss",
        "grid_loss",
        "mech_loss",
        "incomplete_grid_loss",
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


def test_verify_actual_mission_mismatch_is_stale():
    diff = DiffResult(unit_diffs=[
        {"uid": 1, "type": "MirrorMech", "field": "pos",
         "predicted": [2, 5], "actual": [2, 3]},
    ])

    assert _is_implausible_stale_verify_actual(
        diff,
        {"mission_id": "Mission_Acid"},
        "Mission_MosquitoBoss",
    ) is True


def test_broad_grid_verify_diff_is_stale_even_without_mission_id():
    diff = DiffResult(
        unit_diffs=[
            {"uid": i, "type": f"Unit{i}", "field": "pos",
             "predicted": [0, i % 8], "actual": [1, i % 8]}
            for i in range(5)
        ],
        tile_diffs=[
            {"x": i % 8, "y": i // 8, "field": "terrain",
             "predicted": "building", "actual": "ground"}
            for i in range(6)
        ],
        scalar_diffs=[
            {"field": "grid_power", "predicted": 7, "actual": 6},
        ],
    )

    assert _is_implausible_stale_verify_actual(
        diff,
        {"mission_id": "Mission_MosquitoBoss"},
        "Mission_MosquitoBoss",
    ) is True


def test_small_verify_diff_is_not_stale():
    diff = DiffResult(unit_diffs=[
        {"uid": 1, "type": "MirrorMech", "field": "active",
         "predicted": True, "actual": False},
    ])

    assert _is_implausible_stale_verify_actual(
        diff,
        {"mission_id": "Mission_MosquitoBoss"},
        "Mission_MosquitoBoss",
    ) is False
