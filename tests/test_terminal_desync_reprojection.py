from __future__ import annotations

import json

from src.loop import commands
from src.loop.session import RunSession, SolverAction
from src.model.board import Board, Unit
from src.solver import fuzzy_detector
from src.solver.verify import snapshot_after_action


def _unit(
    uid: int,
    *,
    team: int,
    hp: int,
    active: bool,
    type_name: str,
    weapon: str = "",
    is_mech: bool = False,
) -> Unit:
    return Unit(
        uid=uid,
        type=type_name,
        x=4,
        y=4 if team != 1 else 2,
        hp=hp,
        max_hp=3,
        team=team,
        is_mech=is_mech,
        move_speed=3,
        flying=False,
        massive=is_mech,
        armor=False,
        pushable=True,
        weapon=weapon,
        active=active,
    )


def _board(*, enemy_hp: int, player_active: bool) -> Board:
    board = Board()
    board.grid_power = 5
    board.grid_power_max = 7
    board.units = [
        _unit(
            0,
            team=1,
            hp=3,
            active=player_active,
            type_name="PunchMech",
            weapon="Prime_Punchmech",
            is_mech=True,
        ),
        _unit(
            10,
            team=6,
            hp=enemy_hp,
            active=False,
            type_name="Firefly1",
            weapon="FireflyAtk1",
        ),
    ]
    return board


def _bridge_data(*, player_active: bool) -> dict:
    return {
        "phase": "combat_player",
        "turn": 1,
        "in_active_mission": True,
        "mission_id": "Mission_Survive",
        "grid_power": 5,
        "grid_power_max": 7,
        "total_turns": 4,
        "remaining_spawns": 1,
        "spawning_tiles": [],
        "units": [
            {
                "uid": 0,
                "type": "PunchMech",
                "x": 4,
                "y": 2,
                "hp": 3,
                "max_hp": 3,
                "team": 1,
                "mech": True,
                "active": player_active,
                "weapons": ["Prime_Punchmech"],
            },
            {
                "uid": 10,
                "type": "Firefly1",
                "x": 4,
                "y": 4,
                "hp": 2,
                "max_hp": 3,
                "team": 6,
                "mech": False,
                "active": False,
                "weapons": ["FireflyAtk1"],
            },
        ],
        "tiles": [],
    }


def _clean_projection() -> dict:
    current = {
        "grid_power": 5,
        "buildings_alive": 0,
        "building_hp_total": 0,
    }
    predicted = dict(current)
    return {
        "enriched": {
            "post_player_board": {"source": "settled_actual"},
            "final_board": {"source": "projected_enemy_phase"},
            "score_breakdown": {"total": 123},
        },
        "current_outcome": current,
        "predicted_outcome": predicted,
        "predicted_board_summary": predicted,
        "plan_safety": {
            "status": "CLEAN",
            "blocking": False,
            "violations": [],
            "current": current,
            "predicted": predicted,
        },
    }


def test_terminal_desync_settlement_accepts_matching_verify_snapshot():
    board = _board(enemy_hp=2, player_active=False)
    data = _bridge_data(player_active=False)
    data["timestamp"] = 100
    fingerprint = commands._terminal_desync_settle_fingerprint(board, data)
    audit_data = json.loads(json.dumps(data))
    audit_data["timestamp"] = 101

    settled_board, settled_data, info = (
        commands._settle_terminal_desync_post_player_board(
            board,
            audit_data,
            expected_turn=1,
            prior_fingerprint=fingerprint,
            read_fn=lambda: (_ for _ in ()).throw(
                AssertionError("matching verify snapshot must not reread")
            ),
        )
    )

    assert settled_board is board
    assert settled_data is audit_data
    assert info == {
        "status": "OK",
        "samples": 1,
        "elapsed_seconds": 0.0,
        "matched_verify_snapshot": True,
    }


def test_terminal_desync_settlement_does_not_ignore_queued_attack_drift():
    board = _board(enemy_hp=2, player_active=False)
    verify_data = _bridge_data(player_active=False)
    verify_data["timestamp"] = 100
    verify_data["units"][1]["queued_target_x"] = 4
    verify_data["units"][1]["queued_target_y"] = 4
    fingerprint = commands._terminal_desync_settle_fingerprint(
        board,
        verify_data,
    )

    audit_data = json.loads(json.dumps(verify_data))
    audit_data["timestamp"] = 101
    audit_data["units"][1]["queued_target_x"] = 3
    reads = []

    def reread():
        reads.append(True)
        return board, audit_data

    settled_board, settled_data, info = (
        commands._settle_terminal_desync_post_player_board(
            board,
            audit_data,
            expected_turn=1,
            prior_fingerprint=fingerprint,
            read_fn=reread,
            refresh_fn=lambda: None,
            sleep_fn=lambda _seconds: None,
            now_fn=lambda: 0.0,
        )
    )

    assert reads == [True]
    assert settled_board is board
    assert settled_data is audit_data
    assert info["status"] == "OK"
    assert info["samples"] == 2
    assert info["matched_verify_snapshot"] is False


def test_terminal_desync_settlement_rejects_ready_actor():
    board = _board(enemy_hp=2, player_active=True)
    _, _, info = commands._settle_terminal_desync_post_player_board(
        board,
        _bridge_data(player_active=True),
        expected_turn=1,
    )

    assert info["status"] == "ERROR"
    assert info["error"] == "terminal_desync_player_actors_still_active"
    assert info["active_player_actors"] == 1


def test_terminal_desync_reprojection_uses_empty_plan_and_stamps_provenance(
    monkeypatch,
):
    captured = {}

    def fake_evaluate(board, bridge_data, solution, spawns, *args, **kwargs):
        captured["board"] = board
        captured["bridge_data"] = bridge_data
        captured["solution"] = solution
        captured["spawns"] = spawns
        captured["args"] = args
        return _clean_projection()

    monkeypatch.setattr(commands, "_evaluate_solution_safety", fake_evaluate)
    monkeypatch.setattr(
        commands,
        "_annotate_pending_grid_debt",
        lambda *_args, **_kwargs: 0,
    )
    original = {
        "actions": [{"description": "executed original plan"}],
        "selected_candidate_source": "top_k_safety",
        "predicted_board_summary": {"grid_power": 7},
    }

    bridge_data = _bridge_data(player_active=False)
    bridge_data["remaining_spawns"] = 0
    replacement, error = commands._build_terminal_desync_reprojection(
        _board(enemy_hp=2, player_active=False),
        bridge_data,
        original,
        RunSession(run_id="terminal"),
        turn=1,
        desync={"phase": "attack", "action_index": 2, "mech_uid": 0},
        detected_desync_count=2,
        re_solve_count=1,
        settlement={"status": "OK", "samples": 2},
    )

    assert error is None
    assert captured["solution"].actions == []
    assert captured["solution"].active_mech_count == 0
    assert captured["args"][2] == 0
    assert replacement["actions"] == original["actions"]
    assert replacement["selected_candidate_source"] == "top_k_safety"
    assert replacement["post_enemy_prediction_source"] == (
        "terminal_desync_reprojection"
    )
    assert replacement["post_player_board"]["source"] == "settled_actual"
    assert replacement["final_board"]["source"] == "projected_enemy_phase"
    assert replacement["predicted_board_summary"]["grid_power"] == 5
    provenance = replacement["terminal_desync_reprojection"]
    assert provenance["source"] == "settled_actual_post_player_board"
    assert provenance["prior_selected_candidate_source"] == "top_k_safety"
    assert provenance["projection_action_count"] == 0
    assert provenance["desyncs_detected"] == 2
    assert provenance["actual_re_solves"] == 1
    assert original["predicted_board_summary"] == {"grid_power": 7}


def _patch_terminal_auto_turn_harness(tmp_path, monkeypatch, *, persist=True):
    session = RunSession(run_id="terminal", difficulty=0)
    session.mission_index = 0
    session.current_turn = 1
    action = SolverAction(
        mech_uid=0,
        mech_type="PunchMech",
        move_to=(-1, -1),
        weapon="Prime_Punchmech",
        target=(4, 4),
        description="Punch the Firefly",
    )
    session.set_solution([action], 10.0, 1, input_fingerprint="fp")

    predicted_board = _board(enemy_hp=1, player_active=False)
    predicted = snapshot_after_action(predicted_board, 0, 0, [])
    clean_safety = _clean_projection()["plan_safety"]
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    solve_path = tmp_path / "terminal" / "m00_turn_01_solve.json"
    solve_path.parent.mkdir(parents=True)
    solve_path.write_text(json.dumps({
        "data": {
            "selected_candidate_source": "top_k_safety",
            "actions": [action.to_dict()],
            "predicted_states": [{
                "post_move": predicted,
                "post_attack": predicted,
            }],
            "predicted_outcome": {"grid_power": 7},
            "predicted_board_summary": {"grid_power": 7},
            "current_outcome": {"grid_power": 5},
            "plan_safety": clean_safety,
            "initial_building_threats": [],
        }
    }))

    current_board = _board(enemy_hp=2, player_active=True)
    actual_board = _board(enemy_hp=2, player_active=False)
    reads = iter([
        (current_board, _bridge_data(player_active=True)),
        (actual_board, _bridge_data(player_active=False)),
        (actual_board, _bridge_data(player_active=False)),
    ])
    end_turn_calls = []

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "read_state", lambda: None)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_read_save_file_difficulty", lambda _p: None)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: next(reads))
    monkeypatch.setattr(commands, "attack_mech", lambda *_args: "OK")
    monkeypatch.setattr(
        commands,
        "cmd_read",
        lambda **_kwargs: {
            "status": "OK",
            "phase": "combat_player",
            "active_mechs": 1,
            "turn": 1,
            "grid_power": "5/7",
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_solve",
        lambda **_kwargs: {
            "score": 10.0,
            "plan_safety": clean_safety,
            "predicted_outcome": {"grid_power": 7},
            "selected_candidate_rank": 0,
            "selected_candidate_source": "top_k_safety",
            "candidate_count": 1,
        },
    )
    monkeypatch.setattr(
        fuzzy_detector,
        "evaluate",
        lambda *_args, **_kwargs: {
            "signature": "damage_amount|Prime_Punchmech|attack",
            "model_gap": False,
            "asymmetry": [],
            "confidence": 0.5,
            "proposed_tier": 1,
            "context": {},
        },
    )
    monkeypatch.setattr(commands, "_maybe_soft_disable", lambda *_a, **_k: None)
    monkeypatch.setattr(
        commands, "_enqueue_behavior_novelty", lambda *_a, **_k: None
    )
    monkeypatch.setattr(commands, "_log_sub_action_desync", lambda *_a, **_k: None)
    monkeypatch.setattr(commands, "_maybe_flag_grid_drop", lambda *_a, **_k: None)
    monkeypatch.setattr(commands, "_maybe_flag_pod_state_diff", lambda *_a, **_k: None)
    monkeypatch.setattr(
        commands,
        "_annotate_pending_grid_debt",
        lambda *_args, **_kwargs: 0,
    )
    monkeypatch.setattr(
        commands,
        "_evaluate_solution_safety",
        lambda *_args, **_kwargs: _clean_projection(),
    )
    monkeypatch.setattr(
        commands,
        "_lightning_drain_known_behavior_research",
        lambda _session: [],
    )
    monkeypatch.setattr(commands, "_research_peek", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(commands, "_narrate_fuzzy", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        commands,
        "_log_post_action_resist_probe",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        commands,
        "cmd_end_turn",
        lambda: end_turn_calls.append(True) or {
            "status": "PLAN",
            "batch": [{"type": "left_click", "x": 1, "y": 2}],
            "codex_computer_use_batch": [],
            "bridge_ack": None,
        },
    )
    if not persist:
        monkeypatch.setattr(
            commands,
            "_record_turn_state",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError("disk full")
            ),
        )
    return solve_path, end_turn_calls


def test_auto_turn_terminal_desync_reprojects_without_counting_fake_resolve(
    tmp_path,
    monkeypatch,
):
    solve_path, end_turn_calls = _patch_terminal_auto_turn_harness(
        tmp_path,
        monkeypatch,
    )

    result = commands.cmd_auto_turn(wait_for_turn=False)

    assert result["status"] == "PLAN"
    assert result["desyncs_detected"] == 1
    assert result["re_solves"] == 0
    assert end_turn_calls == [True]
    recorded = json.loads(solve_path.read_text())["data"]
    assert recorded["selected_candidate_source"] == "top_k_safety"
    assert recorded["post_enemy_prediction_source"] == (
        "terminal_desync_reprojection"
    )
    assert recorded["terminal_desync_reprojection"]["actual_re_solves"] == 0
    assert recorded["predicted_board_summary"]["grid_power"] == 5


def test_auto_turn_terminal_desync_fails_closed_when_projection_not_persisted(
    tmp_path,
    monkeypatch,
):
    _, end_turn_calls = _patch_terminal_auto_turn_harness(
        tmp_path,
        monkeypatch,
        persist=False,
    )

    result = commands.cmd_auto_turn(wait_for_turn=False)

    assert result["status"] == "TERMINAL_DESYNC_REPROJECTION_BLOCKED"
    assert result["desyncs_detected"] == 1
    assert result["re_solves"] == 0
    assert result["reprojection_error"]["error"] == (
        "terminal_desync_reprojection_persist_failed"
    )
    assert end_turn_calls == []
