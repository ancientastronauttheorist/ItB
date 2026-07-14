import json

from src.loop import commands
from src.loop.commands import (
    _annotate_pending_grid_debt,
    _capture_board_summary,
    _compute_deltas,
    _debt_covered_grid_settlement_delta,
    _evaluate_solution_safety,
    _lethal_end_turn_fire_mech_debts,
    _maybe_flag_grid_drop,
    _summary_with_pending_grid_debt,
)
from src.loop.session import RunSession, SolverAction
from src.model.board import Board
from src.research import orchestrator as research_orchestrator
from src.solver.plan_safety import audit_plan_safety
from src.solver.solver import Solution
from src.solver.verify import DiffResult


def _bridge_with_mech(*, flying=False, danger=None):
    return {
        "mission_id": "Mission_Test",
        "phase": "combat_player",
        "in_active_mission": True,
        "grid_power": 7,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 4,
        "remaining_spawns": 2,
        "is_infinite_spawn": False,
        "mission_kill_target": 0,
        "mission_kill_limit": 0,
        "mission_kills_done": 0,
        "mission_mountain_target": 0,
        "mission_mountains_destroyed": 0,
        "repair_platform_target": 0,
        "repair_platforms_used": 0,
        "freeze_building_target": 0,
        "tiles": [
            {"x": x, "y": y, "terrain": "ground"}
            for x in range(8)
            for y in range(8)
        ],
        "attack_order": [],
        "spawning_tiles": [],
        "environment_danger": [],
        "environment_danger_v2": danger or [],
        "environment_freeze": [],
        "freeze_building_tiles": [],
        "mission_mountain_tiles": [],
        "teleporter_pairs": [],
        "bonus_objective_unit_types": [],
        "destroy_objective_unit_types": [],
        "protect_objective_unit_types": [],
        "units": [{
            "uid": 11,
            "type": "TeleMech",
            "x": 2,
            "y": 5,
            "hp": 1,
            "max_hp": 2,
            "team": 1,
            "mech": True,
            "move": 4,
            "weapons": ["Science_Swap"],
            "active": True,
            "can_move": True,
            "flying": flying,
        }],
    }


def test_summary_carries_bridge_remaining_spawns_signal():
    data = _bridge_with_mech()
    data.update({
        "mission_id": "Mission_BurnbugBoss",
        "turn": 4,
        "total_turns": 4,
        "remaining_spawns": 1,
        "is_infinite_spawn": True,
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["remaining_spawns"] == 1


def test_summary_flags_mech_on_lethal_environment_danger():
    data = _bridge_with_mech(danger=[[2, 5, 1, 1, 0]])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mechs_on_danger"] == [{
        "uid": 11,
        "type": "TeleMech",
        "pos": [2, 5],
        "damage": 1,
    }]


def test_summary_honors_flying_immunity_for_environment_danger():
    data = _bridge_with_mech(flying=True, danger=[[2, 5, 1, 1, 1]])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mechs_on_danger"] == []


def test_summary_honors_board_flying_immunity_when_bridge_payload_is_stale():
    data = _bridge_with_mech(flying=True, danger=[[2, 5, 1, 1, 0]])
    data["mission_id"] = "Mission_Satellite"
    data["targeted_tiles"] = [[2, 5]]
    data["units"].append({
        "uid": 98,
        "type": "SatelliteRocket",
        "x": 2,
        "y": 4,
        "hp": 2,
        "max_hp": 2,
        "team": 1,
        "mech": False,
        "move": 0,
        "weapons": ["Rocket_Launch"],
        "active": False,
        "queued_launch": True,
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert (2, 5) in board.environment_danger_flying_immune
    assert summary["mechs_on_danger"] == []


def test_summary_satellite_fallback_ignores_non_queued_rockets():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Satellite"
    data["targeted_tiles"] = [[6, 1], [4, 2], [5, 2], [6, 2], [6, 3]]
    data["environment_danger"] = [[5, 2], [7, 2], [6, 1], [6, 3]]
    data["environment_danger_v2"] = [
        [5, 2, 1, 1, 1],
        [7, 2, 1, 1, 1],
        [6, 1, 1, 1, 1],
        [6, 3, 1, 1, 1],
    ]
    data["units"][0]["type"] = "ElectricMech"
    data["units"][0]["x"] = 4
    data["units"][0]["y"] = 3
    data["units"][0]["hp"] = 3
    data["units"].extend([
        {
            "uid": 98,
            "type": "SatelliteRocket",
            "x": 6,
            "y": 2,
            "hp": 2,
            "max_hp": 2,
            "team": 1,
            "mech": False,
            "move": 0,
            "weapons": ["Rocket_Launch"],
            "active": False,
            "queued_launch": True,
        },
        {
            "uid": 99,
            "type": "SatelliteRocket",
            "x": 4,
            "y": 2,
            "hp": 2,
            "max_hp": 2,
            "team": 1,
            "mech": False,
            "move": 0,
            "weapons": ["Rocket_Launch"],
            "active": False,
            "queued_launch": False,
        },
    ])

    board = Board.from_bridge_data(data)
    summary = _capture_board_summary(board, data)

    assert (4, 3) not in board.environment_danger
    assert summary["mechs_on_danger"] == []


def test_summary_does_not_treat_spent_action_as_disabled():
    data = _bridge_with_mech()
    data["units"][0]["active"] = False
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mechs_disabled"] == []


def test_summary_excludes_friendly_objective_units_from_mech_loss():
    data = _bridge_with_mech()
    data["units"].append({
        "uid": 492,
        "type": "Disposal_Unit",
        "x": 2,
        "y": 4,
        "hp": 2,
        "max_hp": 2,
        "team": 1,
        "mech": False,
        "move": 0,
        "weapons": ["Disposal_Attack"],
        "active": True,
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mechs_alive"] == 1
    assert summary["mech_hp_total"] == 1
    assert summary["mech_hp"] == [
        {"uid": 11, "type": "TeleMech", "hp": 1, "max_hp": 2}
    ]


def test_end_turn_fire_debt_flags_burning_one_hp_mech():
    data = _bridge_with_mech()
    data["units"][0]["fire"] = True
    board = Board.from_bridge_data(data)

    assert _lethal_end_turn_fire_mech_debts(board) == [{
        "uid": 11,
        "type": "TeleMech",
        "pos": [2, 5],
        "hp": 1,
        "max_hp": 2,
    }]


def test_end_turn_fire_debt_ignores_shielded_burning_mech():
    data = _bridge_with_mech()
    data["units"][0]["fire"] = True
    data["units"][0]["shield"] = True
    board = Board.from_bridge_data(data)

    assert _lethal_end_turn_fire_mech_debts(board) == []


def test_click_end_turn_blocks_lethal_fire_debt(monkeypatch):
    data = _bridge_with_mech()
    data.update({"phase": "combat_player", "active_mechs": 0})
    data["units"][0]["fire"] = True
    board = Board.from_bridge_data(data)
    session = RunSession(
        run_id="fire-stop",
        squad="Mist Eaters",
        difficulty=0,
        achievement_targets=["Let's Walk"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_held_end_turn_safety_block_result", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: (board, data))
    monkeypatch.setattr(
        commands,
        "recalibrate",
        lambda: (_ for _ in ()).throw(AssertionError("should not recalibrate")),
    )
    monkeypatch.setattr(
        commands,
        "plan_end_turn",
        lambda: (_ for _ in ()).throw(AssertionError("should not plan")),
    )

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "lethal_mech_fire_before_enemy_phase"
    assert result["fire_debt"][0]["uid"] == 11


def _held_end_turn_case(monkeypatch, *, plan_safety=None, solve_extra=None):
    data = _bridge_with_mech()
    data.update({
        "phase": "combat_player",
        "turn": 1,
        "in_active_mission": True,
    })
    data["units"][0]["active"] = False
    data["units"][0]["can_move"] = False
    board = Board.from_bridge_data(data)
    current_data = json.loads(json.dumps(data))
    current_data["units"][0]["active"] = True
    current_data["units"][0]["can_move"] = True
    current_board = Board.from_bridge_data(current_data)
    final_data = json.loads(json.dumps(data))
    final_data["turn"] = 2
    final_data["units"][0]["active"] = True
    final_data["units"][0]["can_move"] = True
    if isinstance(plan_safety, dict) and plan_safety.get("status") == "DIRTY":
        requested_grid = (plan_safety.get("predicted") or {}).get("grid_power")
        if type(requested_grid) is int:
            final_data["grid_power"] = requested_grid
    final_board = Board.from_bridge_data(final_data)
    current_summary = _capture_board_summary(current_board, current_data)
    final_summary = _capture_board_summary(final_board, final_data)
    projected_counters = {
        "enemies_killed_by_player": 0,
        "enemies_killed_by_enemy_phase": 0,
        "enemies_killed_by_spawn_block": 0,
        "enemies_killed_total_projected": 0,
        "unit_deaths_by_player": 0,
        "unit_deaths_by_enemy_phase": 0,
        "unit_deaths_by_spawn_block": 0,
        "unit_deaths_total_projected": 0,
        "mission_kills_by_player": 0,
        "mission_kills_by_enemy_phase": 0,
        "mission_kills_by_spawn_block": 0,
        "mission_kills_total_projected": 0,
    }
    final_summary.update(projected_counters)
    final_summary["pods_collected"] = 0
    action = SolverAction(
        mech_uid=11,
        mech_type="TeleMech",
        move_to=None,
        weapon="Science_Swap",
        target=(2, 4),
        description="TeleMech, fire Teleporter at D6",
    )
    session = RunSession(run_id="held-end-turn", squad="Flame Behemoths")
    session.current_mission = "Mission_Test"
    session.mission_index = 1
    session.set_solution([action], score=10.0, turn=1)
    monkeypatch.setattr(session, "save", lambda *_args, **_kwargs: None)
    safety = (
        audit_plan_safety(current_summary, final_summary)
        if isinstance(plan_safety, dict) and plan_safety.get("status") == "DIRTY"
        else plan_safety or audit_plan_safety(current_summary, final_summary)
    )
    solve_data = {
        "actions": [{
            "mech_uid": 11,
            "mech_type": "TeleMech",
            "move_to": None,
            "weapon_id": "Science_Swap",
            "target": [2, 4],
            "description": "TeleMech, fire Teleporter at D6",
        }],
        "initial_building_threats": [],
        "plan_safety": safety,
        "selected_candidate_rank": 0,
        "current_outcome": current_summary,
        "predicted_board_summary": final_summary,
        "predicted_outcome": dict(projected_counters),
        "predicted_states": [{
            "post_move": {"unstable_spawn_uids": []},
            "post_attack": {"unstable_spawn_uids": []},
        }],
        "post_player_board": json.loads(json.dumps(data)),
        "final_board": final_data,
        "action_results": [{
            "enemies_killed": 0,
            "unit_deaths": 0,
            "mission_kills": 0,
            "pods_collected": 0,
        }],
    }
    solve_data.update(solve_extra or {})

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_refresh_end_turn_bridge_state", lambda: True)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: (board, data))
    monkeypatch.setattr(
        commands,
        "_load_recorded_turn_state",
        lambda _session, label, **_kwargs: solve_data if label == "solve" else None,
    )
    monkeypatch.setattr(commands, "recalibrate", lambda: None)
    monkeypatch.setattr(
        commands,
        "plan_end_turn",
        lambda: [{
            "type": "left_click",
            "x": 341,
            "y": 152,
            "description": "Click End Turn",
            "codex_computer_use": {
                "type": "left_click",
                "x": 126,
                "y": 120,
            },
        }],
    )
    return session, action, solve_data


def _terminal_provenance(*, ledger):
    return {
        "version": 1,
        "source": "settled_actual_post_player_board",
        "turn": 1,
        "projection_action_count": 0,
        "desyncs_detected": 1,
        "actual_re_solves": 0,
        "desync": {"action_index": 0, "phase": "attack"},
        "settlement": {
            "status": "OK",
            "samples": 2,
            "matched_verify_snapshot": False,
            "freshness_proven": True,
        },
        "counter_ledger": ledger,
    }


def _counter_ledger(**updates):
    ledger = {
        "version": 1,
        "complete": False,
        "prefix_complete": False,
        "terminal_action_matched": False,
        "verified_action_results": 0,
        "player_enemy_kills": 0,
        "player_unit_deaths": 0,
        "player_mission_kills": 0,
        "player_pods_collected": 0,
        "missing_player_mission_kills": 0,
    }
    ledger.update(updates)
    return ledger


def test_click_end_turn_revalidates_clean_held_turn(monkeypatch):
    _held_end_turn_case(monkeypatch)

    result = commands.cmd_click_end_turn()

    assert result["status"] == "PLAN"
    assert result["codex_computer_use_batch"][0]["x"] == 126


def test_click_end_turn_blocks_changed_dirty_consent_for_held_turn(monkeypatch):
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [{"kind": "grid_power_loss", "blocking": True}],
        "compared": ["grid_power"],
        "current": {"grid_power": 7, "pods_present": 0},
        "predicted": {"grid_power": 6, "pods_present": 0},
    }
    session, _, _ = _held_end_turn_case(
        monkeypatch,
        plan_safety=safety,
    )
    session.dirty_consent_used.append("consent-for-an-earlier-loss-profile")
    monkeypatch.setattr(
        commands,
        "plan_end_turn",
        lambda: (_ for _ in ()).throw(AssertionError("must not plan")),
    )

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "held_end_turn_dirty_consent_invalid"


def test_click_end_turn_accepts_exact_consumed_dirty_consent(monkeypatch):
    safety = {
        "status": "DIRTY",
        "blocking": True,
        "violations": [{"kind": "grid_power_loss", "blocking": True}],
        "compared": ["grid_power"],
        "current": {"grid_power": 7, "pods_present": 0},
        "predicted": {"grid_power": 6, "pods_present": 0},
    }
    session, action, solve_data = _held_end_turn_case(
        monkeypatch,
        plan_safety=safety,
    )
    token = commands._dirty_consent_id(
        session,
        1,
        solve_data["plan_safety"],
        [action],
        candidate_rank=solve_data["selected_candidate_rank"],
    )
    session.dirty_consent_used.append(token)

    result = commands.cmd_click_end_turn()

    assert result["status"] == "PLAN"


def test_click_end_turn_blocks_legacy_pod_reprojection_without_ledger(
    monkeypatch,
):
    terminal = _terminal_provenance(ledger=_counter_ledger())
    terminal.pop("counter_ledger")
    _, _, solve_data = _held_end_turn_case(
        monkeypatch,
        solve_extra={
            "post_enemy_prediction_source": "terminal_desync_reprojection",
            "terminal_desync_reprojection": terminal,
        },
    )
    # Legacy M17 overwrote current_outcome.pods_present to zero, so the
    # action result is the surviving proof that this replay is pod-sensitive.
    solve_data["action_results"][0]["pods_collected"] = 1
    monkeypatch.setattr(
        commands,
        "plan_end_turn",
        lambda: (_ for _ in ()).throw(AssertionError("must not plan")),
    )

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "terminal_reprojection_counter_ledger_missing"


def test_click_end_turn_blocks_non_counter_sensitive_incomplete_ledger(
    monkeypatch,
):
    _held_end_turn_case(
        monkeypatch,
        solve_extra={
            "post_enemy_prediction_source": "terminal_desync_reprojection",
            "terminal_desync_reprojection": _terminal_provenance(
                ledger=_counter_ledger()
            ),
        },
    )

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "terminal_reprojection_counter_ledger_incomplete"


def test_click_end_turn_accepts_single_sample_matching_verify_snapshot(
    monkeypatch,
):
    provenance = _terminal_provenance(ledger=_counter_ledger(
        complete=True,
        prefix_complete=True,
        terminal_action_matched=True,
        verified_action_results=1,
    ))
    provenance["settlement"] = {
        "status": "OK",
        "samples": 1,
        "matched_verify_snapshot": True,
        "freshness_proven": True,
    }
    _held_end_turn_case(
        monkeypatch,
        solve_extra={
            "post_enemy_prediction_source": "terminal_desync_reprojection",
            "terminal_desync_reprojection": provenance,
        },
    )

    result = commands.cmd_click_end_turn()

    assert result["status"] == "PLAN"


def test_click_end_turn_requires_complete_ledger_for_pod_reprojection(
    monkeypatch,
):
    _, _, solve_data = _held_end_turn_case(
        monkeypatch,
        solve_extra={
            "post_enemy_prediction_source": "terminal_desync_reprojection",
            "terminal_desync_reprojection": _terminal_provenance(
                ledger=_counter_ledger()
            ),
        },
    )
    solve_data["action_results"][0]["pods_collected"] = 1
    monkeypatch.setattr(
        commands,
        "plan_end_turn",
        lambda: (_ for _ in ()).throw(AssertionError("must not plan")),
    )

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "terminal_reprojection_counter_ledger_incomplete"


def test_click_end_turn_accepts_complete_ledger_for_pod_reprojection(
    monkeypatch,
):
    complete = _counter_ledger(
        complete=True,
        prefix_complete=True,
        terminal_action_matched=True,
        verified_action_results=1,
        player_pods_collected=1,
    )
    _, _, solve_data = _held_end_turn_case(
        monkeypatch,
        solve_extra={
            "post_enemy_prediction_source": "terminal_desync_reprojection",
            "terminal_desync_reprojection": _terminal_provenance(
                ledger=complete
            ),
        },
    )
    solve_data["action_results"][0]["pods_collected"] = 1
    solve_data["current_outcome"]["pods_present"] = 1
    solve_data["predicted_outcome"]["mission_kills_done_projected"] = 0
    solve_data["predicted_board_summary"]["mission_kills_planned"] = 0
    solve_data["predicted_board_summary"]["pods_collected"] = 1
    solve_data["plan_safety"] = audit_plan_safety(
        solve_data["current_outcome"],
        solve_data["predicted_board_summary"],
    )

    result = commands.cmd_click_end_turn()

    assert result["status"] == "PLAN"


def test_click_end_turn_plan_emission_is_same_turn_one_shot(monkeypatch):
    _held_end_turn_case(monkeypatch)

    first = commands.cmd_click_end_turn()
    second = commands.cmd_click_end_turn()

    assert first["status"] == "PLAN"
    assert second["status"] == "END_TURN_BLOCKED"
    assert second["reason"] == "end_turn_plan_already_issued"


def test_dispatch_end_turn_does_not_retry_unconfirmed_delivery(monkeypatch):
    _held_end_turn_case(monkeypatch)
    dispatches = []
    monkeypatch.setattr(
        commands,
        "_dispatch_click_batch_locally",
        lambda *_args, **_kwargs: dispatches.append(True) or {
            "status": "DISPATCHED",
            "executed": True,
        },
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda _state: {
            "status": "END_TURN_CLICK_NOT_OBSERVED",
            "reason": "bridge_still_player_turn",
        },
    )
    monkeypatch.setattr(
        commands,
        "_prepare_local_dispatch_guard",
        lambda _label: {"status": "OK"},
    )

    first = commands.cmd_dispatch_end_turn(execute=True)
    second = commands.cmd_dispatch_end_turn(execute=True)

    assert first["dispatch"]["delivery_confirmation"] == "delivered_unconfirmed"
    assert first["dispatch"]["retry_allowed"] is False
    assert len(dispatches) == 1
    assert second["reason"] == "click_end_turn_plan_failed"
    assert second["plan"]["reason"] == "end_turn_plan_already_issued"


def test_dispatch_end_turn_rejects_previously_issued_external_plan(monkeypatch):
    session, _, _ = _held_end_turn_case(monkeypatch)
    dispatches = []
    monkeypatch.setattr(
        commands,
        "_dispatch_click_batch_locally",
        lambda *_args, **_kwargs: dispatches.append(True) or {
            "status": "DISPATCHED",
            "executed": True,
        },
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda _state: {"status": "OK", "reason": "phase_changed"},
    )
    monkeypatch.setattr(
        commands,
        "_prepare_local_dispatch_guard",
        lambda _label: {"status": "OK"},
    )

    issued = commands.cmd_click_end_turn()
    result = commands.cmd_dispatch_end_turn(execute=True)

    assert issued["status"] == "PLAN"
    assert result["status"] == "ERROR"
    assert result["plan"]["reason"] == "end_turn_plan_already_issued"
    assert dispatches == []
    assert session.end_turn_plan_ledger["status"] == "plan_issued"


def test_dispatch_end_turn_retries_only_proven_pre_delivery_failure(
    monkeypatch,
):
    session, _, _ = _held_end_turn_case(monkeypatch)
    dispatches = iter([
        {
            "status": "ERROR",
            "reason": "dispatch_guard_failed",
            "executed": False,
        },
        {"status": "DISPATCHED", "executed": True},
    ])
    monkeypatch.setattr(
        commands,
        "_dispatch_click_batch_locally",
        lambda *_args, **_kwargs: next(dispatches),
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda _state: {"status": "OK", "reason": "phase_changed"},
    )
    monkeypatch.setattr(
        commands,
        "_prepare_local_dispatch_guard",
        lambda _label: {"status": "OK"},
    )

    first = commands.cmd_dispatch_end_turn(execute=True)
    second = commands.cmd_dispatch_end_turn(execute=True)

    assert first["dispatch"]["delivery_confirmation"] == "not_delivered"
    assert first["dispatch"]["retry_allowed"] is True
    assert second["status"] == "DISPATCHED"
    assert session.end_turn_plan_ledger["status"] == "delivered_confirmed"


def test_click_end_turn_honors_persisted_same_turn_block(monkeypatch):
    session, _, _ = _held_end_turn_case(monkeypatch)
    session.held_end_turn_block = {
        "version": 1,
        "mission_index": session.mission_index,
        "mission_id": session.current_mission,
            "turn": 1,
            "status": "TERMINAL_DESYNC_REPROJECTION_BLOCKED",
            "reason": "terminal_desync_reprojection_blocked",
            "recorded_at": "2026-07-14T10:00:00",
        }

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "held_end_turn_persistent_block"


def test_click_end_turn_ignores_unscoped_historical_fuzzy_event(monkeypatch):
    session, _, _ = _held_end_turn_case(monkeypatch)
    session.failure_events_this_run.append({
        "asymmetry": ["enemy_survived_unexpectedly"],
        "context": {"turn": 1},
    })

    result = commands.cmd_click_end_turn()

    assert result["status"] == "PLAN"


def test_click_end_turn_blocks_live_post_player_checkpoint_drift(monkeypatch):
    _, _, solve_data = _held_end_turn_case(monkeypatch)
    solve_data["post_player_board"]["units"][0]["hp"] = 2

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "held_end_turn_post_player_mismatch"


def test_click_end_turn_requires_positive_active_mission_evidence(monkeypatch):
    _, _, solve_data = _held_end_turn_case(monkeypatch)
    live_data = json.loads(json.dumps(solve_data["post_player_board"]))
    live_data.pop("in_active_mission")
    live_board = Board.from_bridge_data(live_data)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (live_board, live_data),
    )

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "held_end_turn_active_mission_not_proven"


def test_click_end_turn_ignores_non_actionable_research_backlog(monkeypatch):
    session, _, _ = _held_end_turn_case(monkeypatch)
    session.research_queue.append({
        "type": "TeleMech",
        "kind": "mech_weapon",
        "status": "in_progress",
    })
    monkeypatch.setattr(
        research_orchestrator,
        "has_actionable_research",
        lambda *_args: False,
    )

    result = commands.cmd_click_end_turn()

    assert result["status"] == "PLAN"


def test_click_end_turn_blocks_actionable_research(monkeypatch):
    _held_end_turn_case(monkeypatch)
    monkeypatch.setattr(
        research_orchestrator,
        "has_actionable_research",
        lambda *_args: True,
    )

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "held_end_turn_research_actionable"


def test_click_end_turn_rejects_unknown_plan_safety(monkeypatch):
    safety = {
        "status": "UNKNOWN",
        "blocking": False,
        "violations": [],
        "compared": ["grid_power"],
        "current": {"grid_power": 7},
        "predicted": {"grid_power": 7},
    }
    _held_end_turn_case(monkeypatch, plan_safety=safety)

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "held_end_turn_plan_safety_missing"


def test_click_end_turn_rejects_terminal_source_without_provenance(monkeypatch):
    _held_end_turn_case(
        monkeypatch,
        solve_extra={
            "post_enemy_prediction_source": "terminal_desync_reprojection",
        },
    )

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "terminal_reprojection_provenance_missing"


def test_click_end_turn_rejects_terminal_action_cardinality_mismatch(
    monkeypatch,
):
    provenance = _terminal_provenance(ledger=_counter_ledger())
    provenance["desync"]["action_index"] = 1
    _held_end_turn_case(
        monkeypatch,
        solve_extra={
            "post_enemy_prediction_source": "terminal_desync_reprojection",
            "terminal_desync_reprojection": provenance,
        },
    )

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "terminal_reprojection_action_index_invalid"


def test_click_end_turn_audits_fire_on_proven_held_board(monkeypatch):
    _, _, solve_data = _held_end_turn_case(monkeypatch)
    live_data = json.loads(json.dumps(solve_data["post_player_board"]))
    live_data["units"][0]["fire"] = True
    solve_data["post_player_board"]["units"][0]["fire"] = True
    live_board = Board.from_bridge_data(live_data)
    reads = iter([(live_board, live_data), (None, {})])
    monkeypatch.setattr(commands, "read_bridge_state", lambda: next(reads))

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "lethal_mech_fire_before_enemy_phase"


def test_click_end_turn_blocks_partial_re_solve_reconstruction(monkeypatch):
    _, _, solve_data = _held_end_turn_case(monkeypatch)
    solve_data.update({
        "selected_candidate_source": "partial_re_solve",
        "partial_re_solve": {"done_uids": [], "mid_action_uid": None},
    })

    result = commands.cmd_click_end_turn()

    assert result["status"] == "END_TURN_BLOCKED"
    assert result["reason"] == "held_end_turn_partial_re_solve_requires_review"


def test_summary_tracks_mech_damage_objective_from_bonus_ids():
    data = _bridge_with_mech()
    data["bonus_objective_ids"] = [4, 1]
    data["units"].append({
        "uid": 12,
        "type": "IgniteMech",
        "x": 3,
        "y": 5,
        "hp": 3,
        "max_hp": 3,
        "team": 1,
        "mech": True,
        "move": 4,
        "weapons": ["Ranged_Ignite"],
        "active": True,
        "can_move": True,
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mech_damage_taken_total"] == 1
    assert summary["mech_damage_objective_limit"] == 4


def test_summary_ignores_save_overlay_gap_at_bridge_cap_for_mech_damage_objective():
    data = _bridge_with_mech()
    data["bonus_objective_ids"] = [4]
    data["mech_stat_overlays"] = [
        {"uid": 11, "bridge_max_hp": 2, "save_max_hp": 4},
    ]
    data["units"][0]["hp"] = 2
    data["units"][0]["max_hp"] = 4
    data["units"][0]["bridge_reported_max_hp"] = 2
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mech_damage_taken_total"] == 0
    assert summary["mech_damage_objective_limit"] == 4
    assert summary["mech_hp"] == [
        {"uid": 11, "type": "TeleMech", "hp": 2, "max_hp": 4}
    ]


def test_summary_counts_bridge_cap_damage_below_cap_for_mech_damage_objective():
    data = _bridge_with_mech()
    data["bonus_objective_ids"] = [4]
    data["mech_stat_overlays"] = [
        {"uid": 11, "bridge_max_hp": 2, "save_max_hp": 4},
    ]
    data["units"][0]["hp"] = 1
    data["units"][0]["max_hp"] = 4
    data["units"][0]["bridge_reported_max_hp"] = 2
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mech_damage_taken_total"] == 1
    assert summary["mech_damage_objective_limit"] == 4


def test_solution_safety_prefers_projected_board_summary(monkeypatch):
    data = _bridge_with_mech()
    data["bonus_objective_ids"] = [4]
    data["mech_stat_overlays"] = [
        {"uid": 11, "bridge_max_hp": 2, "save_max_hp": 4},
    ]
    data["units"][0]["hp"] = 2
    data["units"][0]["max_hp"] = 4
    data["units"][0]["bridge_reported_max_hp"] = 2
    board = Board.from_bridge_data(data)
    final_board_data = json.loads(json.dumps(data))
    final_board_data.pop("bonus_objective_ids", None)
    final_board_data.pop("mech_stat_overlays", None)
    final_board_data["environment_danger_v2"] = [[2, 5, 1, 1, 1]]
    final_board_data["units"][0]["x"] = 2
    final_board_data["units"][0]["y"] = 5
    final_board_data["units"][0].pop("bridge_reported_max_hp", None)
    stale_predicted = {
        "mission_id": "Mission_Tides",
        "turn": 1,
        "total_turns": 3,
        "grid_power": 7,
        "mechs_on_danger": [],
        "mech_damage_taken_total": 2,
        "mech_damage_objective_limit": None,
    }

    monkeypatch.setattr(
        "src.loop.commands.replay_solution",
        lambda *args, **kwargs: {
            "predicted_outcome": dict(stale_predicted),
            "final_board": final_board_data,
            "action_results": [],
        },
    )

    result = _evaluate_solution_safety(
        board,
        data,
        Solution(),
        [],
        current_turn=1,
        total_turns=3,
        remaining_spawns=0,
    )

    predicted = result["predicted_board_summary"]
    assert predicted["mechs_on_danger"] == [{
        "uid": 11,
        "type": "TeleMech",
        "pos": [2, 5],
        "damage": 1,
    }]
    assert predicted["mech_damage_taken_total"] == 0
    assert predicted["mech_damage_objective_limit"] == 4
    assert result["plan_safety"]["blocking"] is True
    assert [
        item["kind"] for item in result["plan_safety"]["violations"]
    ] == ["mech_on_danger"]


def test_summary_tracks_mission_kill_objective_progress():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_SnowStorm"
    data["mission_kill_target"] = 5
    data["mission_kill_limit"] = 4
    data["mission_kills_done"] = 4
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mission_kill_target"] == 5
    assert summary["mission_kill_limit"] == 4
    assert summary["mission_kills_done"] == 4


def test_summary_omits_mech_damage_objective_without_bonus_id():
    data = _bridge_with_mech()
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mech_damage_taken_total"] == 1
    assert summary["mech_damage_objective_limit"] is None


def test_summary_tracks_freeze_building_objective_progress():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_FreezeBldg"
    data["freeze_building_target"] = 3
    data["freeze_building_tiles"] = [[1, 1], [2, 1], [3, 1]]
    data["tiles"].extend([
        {
            "x": 1,
            "y": 1,
            "terrain": "building",
            "building_hp": 1,
            "frozen": True,
        },
        {
            "x": 2,
            "y": 1,
            "terrain": "building",
            "building_hp": 1,
            "frozen": False,
        },
        {
            "x": 3,
            "y": 1,
            "terrain": "rubble",
            "building_hp": 0,
            "frozen": False,
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["freeze_building_target"] == 3
    assert summary["freeze_buildings_alive"] == 2
    assert summary["freeze_buildings_frozen"] == 1
    assert summary["freeze_buildings_thawed"] == 1
    assert summary["freeze_buildings"] == [
        {"pos": [1, 1], "alive": True, "frozen": True, "hp": 1},
        {"pos": [2, 1], "alive": True, "frozen": False, "hp": 1},
        {"pos": [3, 1], "alive": False, "frozen": False, "hp": 0},
    ]


def test_summary_tracks_protected_objective_units_from_mission_metadata():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_FreezeBots"
    data["units"].extend([
        {
            "uid": 301,
            "type": "Snowtank1",
            "x": 1,
            "y": 2,
            "hp": 1,
            "max_hp": 1,
            "team": 6,
            "mech": False,
            "move": 4,
            "weapons": [],
            "frozen": True,
        },
        {
            "uid": 302,
            "type": "Snowlaser2",
            "x": 2,
            "y": 2,
            "hp": 0,
            "max_hp": 1,
            "team": 6,
            "mech": False,
            "move": 4,
            "weapons": [],
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["protected_objective_units_alive"] == 1
    assert summary["protected_objective_units_frozen"] == 1
    assert [u["type"] for u in summary["protected_objective_units"]] == [
        "Snowtank1",
        "Snowlaser2",
    ]


def test_botdefense_robot_loss_is_a_protected_objective_safety_block():
    def summary_for(include_second_robot):
        data = _bridge_with_mech()
        data["mission_id"] = "Mission_BotDefense"
        data["units"].append({
            "uid": 974,
            "type": "Snowmine1",
            "x": 5,
            "y": 2,
            "hp": 1,
            "max_hp": 1,
            "team": 1,
            "mech": False,
            "move": 0,
            "weapons": ["SnowmineAtk1"],
        })
        if include_second_robot:
            data["units"].append({
                "uid": 975,
                "type": "Snowmine1",
                "x": 6,
                "y": 0,
                "hp": 1,
                "max_hp": 1,
                "team": 1,
                "mech": False,
                "move": 0,
                "weapons": ["SnowmineAtk1"],
            })
        board = Board.from_bridge_data(data)
        return _capture_board_summary(board, data)

    current = summary_for(True)
    predicted = summary_for(False)
    safety = audit_plan_safety(current, predicted)

    assert current["protected_objective_units_alive"] == 2
    assert predicted["protected_objective_units_alive"] == 1
    assert any(
        violation["kind"] == "protected_objective_unit_lost"
        and violation["blocking"]
        for violation in safety["violations"]
    )


def test_summary_distinguishes_intact_and_damaged_train_value():
    def summary_for(train_type):
        data = _bridge_with_mech()
        data["mission_id"] = "Mission_Train"
        data["units"].extend([
            {
                "uid": 164,
                "type": train_type,
                "x": 4,
                "y": 6,
                "hp": 1,
                "max_hp": 1,
                "team": 1,
                "mech": False,
                "move": 0,
                "weapons": [],
            },
            {
                "uid": 164,
                "type": train_type,
                "x": 4,
                "y": 7,
                "hp": 1,
                "max_hp": 1,
                "team": 1,
                "mech": False,
                "move": 0,
                "weapons": [],
                "is_extra_tile": True,
            },
        ])
        board = Board.from_bridge_data(data)
        return _capture_board_summary(board, data)

    intact = summary_for("Train_Pawn")
    damaged = summary_for("Train_Damaged")

    assert intact["protected_objective_units_alive"] == 1
    assert damaged["protected_objective_units_alive"] == 1
    assert intact["train_objective_value"] == 2
    assert damaged["train_objective_value"] == 1


def test_post_enemy_delta_catches_unexpected_train_degradation():
    predicted = {
        "grid_power": 4,
        "buildings_alive": 6,
        "building_hp_total": 9,
        "enemies_alive": 4,
        "train_objective_value": 2,
    }
    actual = {
        **predicted,
        "train_objective_value": 1,
    }

    deltas = _compute_deltas(predicted, actual)

    assert deltas["train_objective_value_diff"] == -1
    assert "Supply Train objective degraded unexpectedly" in deltas["unexpected_events"]


def test_summary_tracks_filler_pawn_webbed_objective_state():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Filler"
    data["units"].append({
        "uid": 451,
        "type": "Filler_Pawn",
        "x": 3,
        "y": 3,
        "hp": 2,
        "max_hp": 2,
        "team": 1,
        "mech": False,
        "move": 3,
        "weapons": ["Filler_Attack"],
        "web": True,
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["protected_objective_units_alive"] == 1
    assert summary["protected_objective_units_webbed"] == 1
    assert summary["protected_objective_units"] == [
        {
            "uid": 451,
            "type": "Filler_Pawn",
            "pos": [3, 3],
            "hp": 2,
            "max_hp": 2,
            "alive": True,
            "frozen": False,
            "webbed": True,
            "team": 1,
        }
    ]


def test_summary_tracks_proto_bombs_from_mission_metadata():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Bomb"
    data["units"].extend([
        {
            "uid": 401,
            "type": "ProtoBomb",
            "x": 3,
            "y": 4,
            "hp": 1,
            "max_hp": 1,
            "team": 1,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
        {
            "uid": 402,
            "type": "ProtoBomb",
            "x": 4,
            "y": 2,
            "hp": 0,
            "max_hp": 1,
            "team": 1,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["protected_objective_units_alive"] == 1
    assert [u["type"] for u in summary["protected_objective_units"]] == [
        "ProtoBomb",
        "ProtoBomb",
    ]


def test_summary_tracks_archive_tanks_from_mission_metadata():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Tanks"
    data["units"].extend([
        {
            "uid": 501,
            "type": "Archive_Tank",
            "x": 3,
            "y": 4,
            "hp": 1,
            "max_hp": 1,
            "team": 1,
            "mech": False,
            "move": 3,
            "weapons": ["Deploy_TankShot"],
        },
        {
            "uid": 502,
            "type": "Archive_Tank",
            "x": 4,
            "y": 4,
            "hp": 0,
            "max_hp": 1,
            "team": 1,
            "mech": False,
            "move": 3,
            "weapons": ["Deploy_TankShot"],
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["protected_objective_units_alive"] == 1
    assert [u["type"] for u in summary["protected_objective_units"]] == [
        "Archive_Tank",
        "Archive_Tank",
    ]


def test_summary_tracks_destroy_objective_units_from_mission_metadata():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_AcidStorm"
    data["units"].extend([
        {
            "uid": 601,
            "type": "Storm_Generator",
            "x": 2,
            "y": 2,
            "hp": 3,
            "max_hp": 3,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
        {
            "uid": 602,
            "type": "Storm_Generator",
            "x": 4,
            "y": 2,
            "hp": 0,
            "max_hp": 3,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["destroy_objective_units_alive"] == 1
    assert [u["type"] for u in summary["destroy_objective_units"]] == [
        "Storm_Generator",
        "Storm_Generator",
    ]


def test_summary_tracks_dam_pawn_destroy_objective_from_metadata():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Dam"
    data["units"].extend([
        {
            "uid": 603,
            "type": "Dam_Pawn",
            "x": 0,
            "y": 0,
            "hp": 2,
            "max_hp": 2,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
        {
            "uid": 604,
            "type": "Dam_Pawn",
            "x": 1,
            "y": 0,
            "hp": 0,
            "max_hp": 2,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["destroy_objective_units_alive"] == 1
    assert [u["type"] for u in summary["destroy_objective_units"]] == [
        "Dam_Pawn",
        "Dam_Pawn",
    ]


def test_summary_tracks_acid_vats_destroy_objective_from_metadata():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Barrels"
    data["units"].extend([
        {
            "uid": 605,
            "type": "AcidVat",
            "x": 4,
            "y": 1,
            "hp": 2,
            "max_hp": 2,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
        {
            "uid": 606,
            "type": "AcidVat",
            "x": 4,
            "y": 2,
            "hp": 2,
            "max_hp": 2,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["destroy_objective_units_alive"] == 2
    assert [u["type"] for u in summary["destroy_objective_units"]] == [
        "AcidVat",
        "AcidVat",
    ]


def test_summary_tracks_bonus_debris_objective_from_bonus_id():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Survive"
    data["bonus_objective_ids"] = [7]
    data["destroy_objective_unit_types"] = ["BonusDebris"]
    data["units"].extend([
        {
            "uid": 701,
            "type": "BonusDebris",
            "x": 4,
            "y": 3,
            "hp": 1,
            "max_hp": 1,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
        {
            "uid": 702,
            "type": "BonusDebris",
            "x": 5,
            "y": 3,
            "hp": 0,
            "max_hp": 1,
            "team": 6,
            "mech": False,
            "move": 0,
            "weapons": [],
        },
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["destroy_objective_units_alive"] == 1
    assert [u["type"] for u in summary["destroy_objective_units"]] == [
        "BonusDebris",
        "BonusDebris",
    ]


def test_summary_tracks_terraform_grass_counter_tiles():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Terraform"
    data["tiles"].extend([
        {"x": 3, "y": 2, "terrain": "ground", "grass": True},
        {"x": 4, "y": 3, "terrain": "ground", "custom": "ground_grass.png"},
        {"x": 6, "y": 6, "terrain": "ground"},
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["terraform_grass_remaining"] == 2
    assert summary["terraform_grass_tiles"] == [[3, 2], [4, 3]]


def test_summary_tracks_mission_force_mountain_counter():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Force"
    data["mission_mountain_target"] = 2
    data["mission_mountains_destroyed"] = 1
    data["mission_mountain_tiles"] = [[2, 2], [4, 4]]
    data["tiles"].extend([
        {"x": 2, "y": 2, "terrain": "mountain", "building_hp": 1},
        {"x": 4, "y": 4, "terrain": "mountain", "building_hp": 2},
        {"x": 5, "y": 5, "terrain": "rubble", "building_hp": 0},
    ])
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mission_mountain_target"] == 2
    assert summary["mission_mountains_destroyed"] == 1
    assert summary["mission_mountain_tiles"] == [
        {"pos": [2, 2], "hp": 1},
        {"pos": [4, 4], "hp": 2},
    ]


def test_summary_tracks_infected_mechs_for_mite_counter():
    data = _bridge_with_mech()
    data["mission_id"] = "Mission_Holes"
    data["units"][0]["infected"] = True
    data["units"].append({
        "uid": 12,
        "type": "IgniteMech",
        "x": 4,
        "y": 5,
        "hp": 3,
        "max_hp": 3,
        "team": 1,
        "mech": True,
        "move": 4,
        "weapons": ["Ranged_Ignite"],
        "infected": False,
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mites_status_tracked"] is True
    assert summary["mites_remaining"] == 1
    assert summary["mechs_infected"] == [{
        "uid": 11,
        "type": "TeleMech",
        "pos": [2, 5],
    }]


def test_summary_keeps_dead_player_mechs_for_post_enemy_diff():
    data = _bridge_with_mech()
    data["units"][0]["hp"] = 0
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["mechs_alive"] == 0
    assert summary["mech_hp_total"] == 0
    assert summary["mech_hp"] == [
        {"uid": 11, "type": "TeleMech", "hp": 0, "max_hp": 2}
    ]


def test_summary_treats_missing_hp_unique_building_as_destroyed_projection():
    data = _bridge_with_mech()
    data["tiles"].append({
        "x": 4,
        "y": 6,
        "terrain": "building",
        "unique_building": True,
        "objective_name": "Str_Power",
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert board.tile(4, 6).building_hp == 0
    assert summary["objective_buildings_alive"] == 0
    assert summary["objective_building_hp_total"] == 0


def test_summary_counts_enemy_targets_on_objective_buildings():
    data = _bridge_with_mech()
    data["tiles"].append({
        "x": 4,
        "y": 2,
        "terrain": "building",
        "building_hp": 1,
        "unique_building": True,
        "objective_name": "Str_Power",
    })
    data["units"].append({
        "uid": 106,
        "type": "Moth1",
        "x": 6,
        "y": 2,
        "hp": 3,
        "max_hp": 3,
        "team": 6,
        "mech": False,
        "move": 3,
        "weapons": ["MothAtk1"],
        "queued_target": [4, 2],
        "has_queued_attack": True,
    })
    board = Board.from_bridge_data(data)

    summary = _capture_board_summary(board, data)

    assert summary["objective_buildings_targeted"] == 1
    assert summary["objective_building_targets"] == [{
        "uid": 106,
        "type": "Moth1",
        "pos": [6, 2],
        "target": [4, 2],
    }]


def test_bridge_terrain_id_overrides_stale_lava_name_for_ice():
    data = _bridge_with_mech()
    data["tiles"].append({
        "x": 5,
        "y": 5,
        "terrain": "lava",
        "terrain_id": 5,
    })
    board = Board.from_bridge_data(data)

    assert board.tile(5, 5).terrain == "ice"


def test_deltas_flags_predicted_mech_missing_from_actual_as_dead():
    predicted = {
        "buildings_alive": 7,
        "building_hp_total": 10,
        "grid_power": 6,
        "enemies_alive": 3,
        "mech_hp": [
            {"uid": 11, "type": "TeleMech", "hp": 2, "max_hp": 2}
        ],
    }
    actual = {
        "buildings_alive": 7,
        "building_hp_total": 10,
        "grid_power": 6,
        "enemies_alive": 3,
        "mech_hp": [],
    }

    deltas = _compute_deltas(predicted, actual)

    assert deltas["mech_hp_diff"] == [{
        "uid": 11,
        "type": "TeleMech",
        "predicted_hp": 2,
        "actual_hp": 0,
        "diff": -2,
    }]
    assert deltas["unexpected_events"] == [
        "TeleMech took 2 unexpected damage"
    ]


def test_pending_grid_debt_detects_delayed_grid_scalar(tmp_path, monkeypatch):
    board = Board()
    board.grid_power = 5
    board.grid_power_max = 7
    for x, y, hp in ((3, 4, 2), (4, 2, 1), (5, 6, 2)):
        board.tile(x, y).terrain = "building"
        board.tile(x, y).building_hp = hp
    bridge_data = {
        "turn": 2,
        "mission_seeds": {
            "region6": {"state": 0, "mission": "Mission4"}
        },
    }
    log_path = tmp_path / "resist_probe.jsonl"
    log_path.write_text(json.dumps({
        "run_id": "run",
        "region": "region6",
        "turn": 2,
        "grid_power": 5,
        "building_hp_map": {
            "D5": 2,
            "F4": 2,
            "B3": 2,
        },
    }) + "\n")
    monkeypatch.setattr(
        "src.loop.commands._recording_dir",
        lambda session: tmp_path,
    )

    debt = _annotate_pending_grid_debt(
        RunSession(run_id="run"),
        board,
        bridge_data,
    )

    assert debt == 1
    assert bridge_data["_pending_grid_debt"] == 1
    summary = _summary_with_pending_grid_debt(
        {"grid_power": 5, "building_hp_total": 5},
        debt,
    )
    assert summary["visible_grid_power"] == 5
    assert summary["grid_power"] == 4


def test_debt_covered_favorable_player_grid_scalar_is_unresolved_lag(capsys):
    investigations = []
    board = Board()
    board.grid_power = 3
    diff = DiffResult(scalar_diffs=[{
        "field": "grid_power",
        "predicted": 2,
        "actual": 3,
    }])

    _maybe_flag_grid_drop(
        investigations,
        diff,
        {"categories": ["grid_power"]},
        {"grid_power": 2},
        board,
        {"action_index": 0, "sub_action": "attack"},
        "run",
        3,
        "failure",
        pending_grid_debt=1,
    )

    output = capsys.readouterr().out
    assert investigations == []
    assert "covered by pending grid debt" in output
    assert "Grid Defense resist" not in output


def test_debt_covered_grid_settlement_predicate_is_exact():
    pure_grid_lag = DiffResult(scalar_diffs=[{
        "field": "grid_power",
        "predicted": 2,
        "actual": 3,
    }])

    assert _debt_covered_grid_settlement_delta(pure_grid_lag, 1) == 1
    assert _debt_covered_grid_settlement_delta(pure_grid_lag, 0) == 0

    pure_grid_lag.tile_diffs.append({
        "x": 2,
        "y": 3,
        "field": "building_hp",
        "predicted": 0,
        "actual": 1,
    })
    assert _debt_covered_grid_settlement_delta(pure_grid_lag, 1) == 0


def test_unproven_favorable_player_grid_scalar_queues_investigation(
    tmp_path,
    monkeypatch,
):
    investigations = []
    board = Board()
    board.grid_power = 3
    diff = DiffResult(scalar_diffs=[{
        "field": "grid_power",
        "predicted": 2,
        "actual": 3,
    }])
    monkeypatch.setattr(commands, "SNAPSHOT_DIR", tmp_path)

    _maybe_flag_grid_drop(
        investigations,
        diff,
        {"categories": ["grid_power"]},
        {"grid_power": 2},
        board,
        {"action_index": 0, "sub_action": "attack"},
        "run",
        3,
        "failure",
        pending_grid_debt=0,
    )

    assert len(investigations) == 1
    assert investigations[0]["failure_db_id"] == "failure"


def test_mixed_favorable_grid_diff_still_queues_investigation(
    tmp_path,
    monkeypatch,
):
    investigations = []
    board = Board()
    board.grid_power = 3
    diff = DiffResult(
        tile_diffs=[{
            "x": 2,
            "y": 3,
            "field": "building_hp",
            "predicted": 0,
            "actual": 1,
        }],
        scalar_diffs=[{
            "field": "grid_power",
            "predicted": 2,
            "actual": 3,
        }],
    )
    monkeypatch.setattr(commands, "SNAPSHOT_DIR", tmp_path)

    _maybe_flag_grid_drop(
        investigations,
        diff,
        {"categories": ["grid_power", "building"]},
        {"grid_power": 2},
        board,
        {"action_index": 0, "sub_action": "attack"},
        "run",
        3,
        "failure",
    )

    assert len(investigations) == 1
    assert investigations[0]["failure_db_id"] == "failure"
    assert "1 building hp diff(s)" in investigations[0]["reason"]


def test_pending_grid_debt_ignores_stale_same_region_turn(tmp_path, monkeypatch):
    board = Board()
    board.grid_power = 7
    board.grid_power_max = 7
    for x, y, hp in ((1, 2, 1), (1, 6, 1), (2, 6, 1), (4, 3, 2), (5, 3, 2), (5, 6, 1)):
        board.tile(x, y).terrain = "building"
        board.tile(x, y).building_hp = hp
    bridge_data = {
        "turn": 1,
        "mission_id": "Mission_Disposal",
        "master_seed": 113578278,
        "mission_seeds": {
            "region1": {"state": 0, "mission": "Mission1"}
        },
    }
    log_path = tmp_path / "resist_probe.jsonl"
    log_path.write_text(
        json.dumps({
            "run_id": "run",
            "mission_id": "Mission_Tides",
            "region": "region1",
            "mission_slot": "Mission3",
            "turn": 1,
            "master_seed": 814802298,
            "grid_power": 5,
            "building_hp_map": {
                "C8": 1,
                "B8": 1,
                "C7": 1,
                "B7": 1,
                "G6": 2,
                "F6": 2,
                "B5": 1,
                "B4": 2,
            },
        }) + "\n" + json.dumps({
            "run_id": "run",
            "mission_id": "Mission_Disposal",
            "region": "region1",
            "mission_slot": "Mission1",
            "turn": 1,
            "master_seed": 113578278,
            "grid_power": 7,
            "building_hp_map": {
                "F7": 1,
                "B7": 1,
                "B6": 1,
                "E4": 2,
                "E3": 2,
                "B3": 1,
            },
        }) + "\n"
    )
    monkeypatch.setattr(
        "src.loop.commands._recording_dir",
        lambda session: tmp_path,
    )

    debt = _annotate_pending_grid_debt(
        RunSession(run_id="run"),
        board,
        bridge_data,
    )

    assert debt == 0
    assert "_pending_grid_debt" not in bridge_data
