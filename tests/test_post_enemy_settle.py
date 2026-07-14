from __future__ import annotations

import json

from src.loop import commands
from src.loop.session import ActiveSolution, RunSession
from src.model.board import Board, Unit


def _board(grid_power: int) -> Board:
    board = Board()
    board.grid_power = grid_power
    board.grid_power_max = 7
    for x, y, hp in (
        (1, 6, 1),
        (2, 4, 1),
        (2, 6, 1),
        (3, 2, 1),
        (3, 4, 1),
        (5, 6, 2),
    ):
        tile = board.tiles[x][y]
        tile.terrain = "building"
        tile.building_hp = hp
    board.units.append(
        Unit(
            uid=0,
            type="JetMech",
            x=6,
            y=2,
            hp=2,
            max_hp=2,
            team=1,
            is_mech=True,
            move_speed=4,
            flying=True,
            massive=True,
            armor=False,
            pushable=True,
            weapon="Brute_Jetmech",
            active=True,
        )
    )
    return board


def _bridge(turn: int = 3) -> dict:
    return {
        "phase": "combat_player",
        "turn": turn,
        "active_mechs": 3,
        "units": [],
        "tiles": [],
    }


def _enemy(uid: int, x: int, y: int, *, minor: bool = False) -> Unit:
    return Unit(
        uid=uid,
        type="Leaper2",
        x=x,
        y=y,
        hp=3,
        max_hp=3,
        team=6,
        is_mech=False,
        move_speed=4,
        flying=False,
        massive=False,
        armor=False,
        pushable=True,
        weapon="LeaperAtk2",
        active=False,
        minor=minor,
    )


def _pod_checkpoints(
    positions: list[tuple[int, int]],
    enemy_uids: list[int] | None = None,
) -> dict:
    units = [
        {"uid": uid, "team": 6, "hp": 1, "x": 0, "y": 0}
        for uid in (enemy_uids or [])
    ]
    checkpoint = {
        "tiles": [
            {"x": x, "y": y, "terrain": "ground", "has_pod": True}
            for x, y in positions
        ],
        "units": units,
        "spawning_tiles": [[7, 4]],
    }
    return {
        "post_player_board": checkpoint,
        "final_board": json.loads(json.dumps(checkpoint)),
    }


def test_post_enemy_settle_waits_for_ready_player_actors(monkeypatch):
    inactive = _board(5)
    inactive.units[0].active = False
    ready = _board(3)
    reads = iter([
        (inactive, {"phase": "combat_player", "turn": 3}),
        (ready, {"phase": "combat_player", "turn": 3}),
        (ready, {"phase": "combat_player", "turn": 3}),
    ])
    clock = {"t": 0.0}

    monkeypatch.setattr(
        commands,
        "_load_solve_prediction_for_turn",
        lambda session, turn: {
            "grid_power": 3,
            "buildings_alive": 6,
            "building_hp_total": 7,
        },
    )

    def sleep(dt):
        clock["t"] += dt

    settled, data, info = commands._settle_post_enemy_board(
        RunSession(run_id="test"),
        inactive,
        {"phase": "combat_player", "turn": 3},
        solved_turn=2,
        max_wait=2.0,
        interval=0.25,
        read_fn=lambda: next(reads),
        refresh_fn=lambda: None,
        sleep_fn=sleep,
        now_fn=lambda: clock["t"],
    )

    assert settled.grid_power == 3
    assert commands._active_player_action_count(settled) == 1
    assert data["phase"] == "combat_player"
    assert info["samples"] == 4


def test_terminal_post_enemy_ready_accepts_exact_ordinary_mission_snapshot():
    board = _board(3)
    bridge = {
        "phase": "unknown",
        "turn": 4,
        "in_active_mission": False,
        "tiles": [{} for _ in range(64)],
        "units": [],
    }

    assert commands._terminal_post_enemy_ready_for_audit(
        board, bridge, solved_turn=3
    )
    assert commands._terminal_post_enemy_ready_for_audit(
        board, {**bridge, "turn": 3}, solved_turn=3
    )
    assert not commands._terminal_post_enemy_ready_for_audit(
        board, {**bridge, "in_active_mission": True}, solved_turn=3
    )
    assert not commands._terminal_post_enemy_ready_for_audit(
        board, {**bridge, "turn": 5}, solved_turn=3
    )
    assert not commands._terminal_post_enemy_ready_for_audit(
        board, {**bridge, "turn": 2}, solved_turn=3
    )
    assert not commands._terminal_post_enemy_ready_for_audit(
        board, {**bridge, "tiles": []}, solved_turn=3
    )


def test_cmd_read_records_same_turn_terminal_post_enemy_snapshot(monkeypatch):
    session = RunSession(run_id="run")
    session.current_mission = "Mission_Belt"
    session.active_solution = ActiveSolution(actions=[], score=1.0, turn=4)
    board = _board(2)
    bridge = {
        "phase": "unknown",
        "turn": 4,
        "mission_id": "Mission_Belt",
        "in_active_mission": False,
        "tiles": [{} for _ in range(64)],
        "units": [],
    }
    recorded = []

    monkeypatch.setattr(commands, "recalibrate", lambda: None)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(
        commands, "read_bridge_state", lambda: (board, bridge)
    )
    monkeypatch.setattr(
        commands, "detect_game_phase", lambda _profile: "between_missions"
    )
    monkeypatch.setattr(commands, "_record_turn_state", lambda *_a, **_k: None)
    monkeypatch.setattr(
        commands,
        "_record_post_enemy",
        lambda _session, _board, solved_turn, bridge_data=None: (
            recorded.append((solved_turn, bridge_data))
            or {"status": "POST_ENEMY_RECORDED", "blocking": False}
        ),
    )
    monkeypatch.setattr(RunSession, "save", lambda self: None)

    result = commands.cmd_read()

    assert result["phase"] == "unknown"
    assert recorded == [(4, bridge)]
    assert session.active_solution is None
    assert session.post_enemy_block is None


def test_active_player_action_count_accepts_secondary_only_mission_actor():
    board = _board(3)
    actor = board.mechs()[0]
    actor.is_mech = False
    actor.weapon = ""
    actor.weapon2 = "Missiles_OneDmg"

    assert commands._active_player_action_count(board) == 1


def test_same_turn_done_bridge_is_ambiguous_around_external_end_turn_click():
    session = RunSession(run_id="run")
    session.active_solution = ActiveSolution(actions=[], score=1.0, turn=3)
    bridge = {
        "phase": "combat_player",
        "turn": 3,
        "in_active_mission": True,
    }

    assert commands._same_turn_all_player_actors_done(session, bridge, 0)
    assert not commands._same_turn_all_player_actors_done(session, bridge, 3)
    assert not commands._same_turn_all_player_actors_done(
        session, {**bridge, "turn": 4}, 0
    )
    assert not commands._same_turn_all_player_actors_done(
        session, {**bridge, "phase": "combat_enemy"}, 0
    )


def test_terminal_post_enemy_audit_accounts_for_stale_grid_scalar(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(run_id="run")
    session.mission_index = 11
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "m11_turn_03_solve.json").write_text(json.dumps({
        "data": {
            "predicted_board_summary": {
                "buildings_alive": 6,
                "building_hp_total": 7,
                "grid_power": 3,
                "enemies_alive": 0,
                "mech_hp": [],
            },
            "search_stats": {},
        }
    }))

    actual = _board(3)
    actual.tiles[1][6].terrain = "rubble"
    actual.tiles[1][6].building_hp = 0
    actual.tiles[5][6].building_hp = 1
    bridge = {
        "phase": "unknown",
        "turn": 4,
        "in_active_mission": False,
        "tiles": [{} for _ in range(64)],
        "units": [],
    }

    result = commands._record_post_enemy(
        session,
        actual,
        solved_turn=3,
        bridge_data=bridge,
    )

    assert result["status"] == "INVESTIGATE_POST_ENEMY"
    assert result["blocking"] is True
    assert result["actual_outcome"]["visible_grid_power"] == 3
    assert result["actual_outcome"]["pending_grid_debt"] == 2
    assert result["actual_outcome"]["grid_power"] == 1
    assert result["deltas"]["grid_power_diff"] == -2
    assert result["deltas"]["buildings_alive_diff"] == -1
    assert result["deltas"]["building_hp_diff"] == -2


def test_terminal_grid_debt_uses_preplan_board_for_predicted_loss(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(run_id="run")
    session.mission_index = 11
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "m11_turn_03_solve.json").write_text(json.dumps({
        "data": {
            "current_outcome": {
                "buildings_alive": 6,
                "building_hp_total": 7,
                "grid_power": 3,
            },
            "predicted_board_summary": {
                "buildings_alive": 5,
                "building_hp_total": 5,
                "grid_power": 1,
                "enemies_alive": 0,
                "mech_hp": [],
            },
            "search_stats": {},
        }
    }))

    actual = _board(3)
    actual.tiles[1][6].terrain = "rubble"
    actual.tiles[1][6].building_hp = 0
    actual.tiles[5][6].building_hp = 1
    bridge = {
        "phase": "unknown",
        "turn": 4,
        "in_active_mission": False,
        "tiles": [{} for _ in range(64)],
        "units": [],
    }

    result = commands._record_post_enemy(
        session,
        actual,
        solved_turn=3,
        bridge_data=bridge,
    )

    assert result["status"] == "POST_ENEMY_RECORDED"
    assert result["blocking"] is False
    assert result["actual_outcome"]["visible_grid_power"] == 3
    assert result["actual_outcome"]["pending_grid_debt"] == 2
    assert result["actual_outcome"]["grid_power"] == 1
    assert result["deltas"]["grid_power_diff"] == 0
    assert result["deltas"]["buildings_alive_diff"] == 0
    assert result["deltas"]["building_hp_diff"] == 0


def _terminal_filler_case(
    tmp_path,
    monkeypatch,
    *,
    run_id: str,
    include_filler: bool = True,
    final_mission_id: str = "Mission_Filler",
    terminal: bool = True,
    missing_mission_source: str | None = None,
    missing_objective_metadata: tuple[str, str] | None = None,
):
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(run_id=run_id)
    session.mission_index = 1
    session.current_mission = "Mission_Filler"
    if missing_mission_source == "session":
        session.current_mission = None
    run_dir = tmp_path / run_id
    run_dir.mkdir()

    board = _board(3)
    if include_filler:
        board.units.append(Unit(
            uid=778,
            type="Filler_Pawn",
            x=3,
            y=3,
            hp=2,
            max_hp=2,
            team=1,
            is_mech=False,
            move_speed=0,
            flying=False,
            massive=True,
            armor=False,
            pushable=False,
            weapon="Filler_Attack",
            active=False,
        ))

    protected = [{
        "uid": 778,
        "type": "Filler_Pawn",
        "pos": [3, 3],
        "hp": 2,
        "max_hp": 2,
        "alive": True,
        "frozen": False,
        "webbed": False,
        "team": 1,
    }]
    baseline = {
        "buildings_alive": 6,
        "building_hp_total": 7,
        "grid_power": 3,
        "enemies_alive": 0,
        "mech_hp": [{
            "uid": 0,
            "type": "JetMech",
            "hp": 2,
            "max_hp": 2,
        }],
        "mission_id": "Mission_Filler",
        "protected_objective_units": protected,
        "protected_objective_units_alive": 1,
        "protected_objective_units_frozen": 0,
    }
    checkpoint = {
        "mission_id": "Mission_Filler",
        "protect_objective_unit_types": ["Filler_Pawn"],
        "destroy_objective_unit_types": [],
        "bonus_objective_unit_types": [],
    }
    final_checkpoint = dict(checkpoint)
    final_checkpoint["mission_id"] = final_mission_id
    current_outcome = dict(baseline)
    predicted = dict(baseline)
    sources = {
        "predicted": predicted,
        "current": current_outcome,
        "post_player": checkpoint,
        "final": final_checkpoint,
    }
    if missing_mission_source in sources:
        del sources[missing_mission_source]["mission_id"]
    if missing_objective_metadata is not None:
        checkpoint_name, key = missing_objective_metadata
        del sources[checkpoint_name][key]
    (run_dir / "m01_turn_04_solve.json").write_text(json.dumps({
        "data": {
            "current_outcome": current_outcome,
            "predicted_board_summary": predicted,
            "post_player_board": checkpoint,
            "final_board": final_checkpoint,
            "search_stats": {},
        }
    }))
    bridge = {
        "phase": "unknown" if terminal else "combat_player",
        "turn": 4 if terminal else 5,
        "mission_id": "",
        "in_active_mission": not terminal,
        "tiles": [{} for _ in range(64)],
        "units": [],
    }
    return commands._record_post_enemy(
        session,
        board,
        solved_turn=4,
        bridge_data=bridge,
    )


def test_terminal_audit_restores_agreed_filler_context_and_recounts_live_pawn(
    tmp_path,
    monkeypatch,
):
    result = _terminal_filler_case(
        tmp_path,
        monkeypatch,
        run_id="filler_alive",
    )

    assert result["status"] == "POST_ENEMY_RECORDED"
    assert result["blocking"] is False
    assert result["actual_outcome"]["mission_id"] == "Mission_Filler"
    assert result["actual_outcome"]["protected_objective_units"] == [{
        "uid": 778,
        "type": "Filler_Pawn",
        "pos": [3, 3],
        "hp": 2,
        "max_hp": 2,
        "alive": True,
        "frozen": False,
        "webbed": False,
        "team": 1,
    }]
    assert result["deltas"]["protected_objective_units_alive_diff"] == 0


def test_terminal_filler_context_recovery_stays_fail_closed(
    tmp_path,
    monkeypatch,
):
    cases = (
        ("missing_pawn", {"include_filler": False}),
        ("conflicting_context", {"final_mission_id": "Mission_Train"}),
        ("nonterminal", {"terminal": False}),
    )
    cases += tuple(
        (
            f"missing_{source}_mission",
            {"missing_mission_source": source},
        )
        for source in ("predicted", "current", "post_player", "final", "session")
    )
    cases += tuple(
        (
            f"missing_{checkpoint_name}_{key}",
            {"missing_objective_metadata": (checkpoint_name, key)},
        )
        for checkpoint_name in ("post_player", "final")
        for key in (
            "protect_objective_unit_types",
            "destroy_objective_unit_types",
            "bonus_objective_unit_types",
        )
    )
    for run_id, kwargs in cases:
        result = _terminal_filler_case(
            tmp_path,
            monkeypatch,
            run_id=run_id,
            **kwargs,
        )

        assert result["status"] == "INVESTIGATE_POST_ENEMY", run_id
        assert result["blocking"] is True, run_id
        assert (
            result["deltas"]["protected_objective_units_alive_diff"] == -1
        ), run_id


def test_post_enemy_settle_waits_when_buildings_worse_but_grid_not_yet(monkeypatch):
    stale = _board(5)
    stale.tiles[1][6].terrain = "rubble"
    stale.tiles[1][6].building_hp = 0
    fresh = _board(3)
    fresh.tiles[1][6].terrain = "rubble"
    fresh.tiles[1][6].building_hp = 0
    reads = iter([
        (stale, _bridge()),
        (stale, _bridge()),
        (fresh, _bridge()),
        (fresh, _bridge()),
    ])
    clock = {"t": 0.0}

    monkeypatch.setattr(
        commands,
        "_load_solve_prediction_for_turn",
        lambda session, turn: {
            "grid_power": 5,
            "buildings_alive": 6,
            "building_hp_total": 8,
        },
    )

    def sleep(dt):
        clock["t"] += dt

    settled, _data, info = commands._settle_post_enemy_board(
        RunSession(run_id="test"),
        stale,
        _bridge(),
        solved_turn=2,
        max_wait=2.0,
        interval=0.25,
        read_fn=lambda: next(reads),
        refresh_fn=lambda: None,
        sleep_fn=sleep,
        now_fn=lambda: clock["t"],
    )

    assert settled.grid_power == 3
    assert info["samples"] == 5


def test_post_enemy_settle_waits_past_stale_favorable_grid(monkeypatch):
    stale = _board(5)
    fresh = _board(2)
    reads = iter([
        (stale, _bridge()),
        (fresh, _bridge()),
        (fresh, _bridge()),
    ])
    clock = {"t": 0.0}

    monkeypatch.setattr(
        commands,
        "_load_solve_prediction_for_turn",
        lambda session, turn: {
            "grid_power": 3,
            "buildings_alive": 6,
            "building_hp_total": 7,
        },
    )

    def sleep(dt):
        clock["t"] += dt

    settled, data, info = commands._settle_post_enemy_board(
        RunSession(run_id="test"),
        stale,
        _bridge(),
        solved_turn=2,
        max_wait=2.0,
        interval=0.25,
        read_fn=lambda: next(reads),
        refresh_fn=lambda: None,
        sleep_fn=sleep,
        now_fn=lambda: clock["t"],
    )

    assert settled.grid_power == 2
    assert data["turn"] == 3
    assert info["samples"] == 4


def test_post_enemy_settle_aborts_when_turn_window_changes(monkeypatch):
    start = _board(5)
    late = _board(3)
    reads = iter([
        (late, _bridge(turn=4)),
    ])
    clock = {"t": 0.0}

    monkeypatch.setattr(
        commands,
        "_load_solve_prediction_for_turn",
        lambda session, turn: {
            "grid_power": 5,
            "buildings_alive": 6,
            "building_hp_total": 7,
        },
    )

    def sleep(dt):
        clock["t"] += dt

    settled, data, info = commands._settle_post_enemy_board(
        RunSession(run_id="test"),
        start,
        _bridge(turn=3),
        solved_turn=2,
        max_wait=2.0,
        interval=0.25,
        read_fn=lambda: next(reads),
        refresh_fn=lambda: None,
        sleep_fn=sleep,
        now_fn=lambda: clock["t"],
    )

    assert settled.grid_power == 3
    assert data["turn"] == 4
    assert info["aborted"] is True
    assert info["reason"] == "turn_window_changed"
    assert info["expected_turn"] == 3
    assert info["actual_turn"] == 4


def test_post_enemy_settle_keeps_polling_favorable_resist_to_cap(monkeypatch):
    stale = _board(5)
    reads = iter([
        (stale, _bridge()),
        (stale, _bridge()),
        (stale, _bridge()),
        (stale, _bridge()),
    ])
    clock = {"t": 0.0}

    monkeypatch.setattr(
        commands,
        "_load_solve_prediction_for_turn",
        lambda session, turn: {
            "grid_power": 3,
            "buildings_alive": 6,
            "building_hp_total": 7,
        },
    )

    def sleep(dt):
        clock["t"] += dt

    settled, _data, info = commands._settle_post_enemy_board(
        RunSession(run_id="test"),
        stale,
        _bridge(),
        solved_turn=2,
        max_wait=1.0,
        interval=0.25,
        read_fn=lambda: next(reads),
        refresh_fn=lambda: None,
        sleep_fn=sleep,
        now_fn=lambda: clock["t"],
    )

    assert settled.grid_power == 5
    assert clock["t"] >= 1.0
    assert info["samples"] == 5


def test_record_post_enemy_returns_investigation_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(run_id="run")
    session.mission_index = 11
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    solve_file = run_dir / "m11_turn_01_solve.json"
    solve_file.write_text(json.dumps({
        "data": {
            "predicted_board_summary": {
                "buildings_alive": 6,
                "building_hp_total": 7,
                "grid_power": 6,
                "enemies_alive": 0,
                "mech_hp": [],
            },
            "search_stats": {},
        }
    }))

    actual = _board(4)
    result = commands._record_post_enemy(session, actual, 1)

    assert result["status"] == "INVESTIGATE_POST_ENEMY"
    assert result["blocking"] is True
    assert result["deltas"]["grid_power_diff"] == -2
    assert session.post_enemy_block is not None
    assert session.post_enemy_block["turn"] == 1
    assert session.post_enemy_block["deltas"]["grid_power_diff"] == -2
    assert (run_dir / "m11_turn_01_post_enemy.json").exists()


def test_record_post_enemy_blocks_unexpected_pod_loss(tmp_path, monkeypatch):
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(run_id="run")
    session.mission_index = 11
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    solve_file = run_dir / "m11_turn_01_solve.json"
    solve_file.write_text(json.dumps({
        "data": {
            "predicted_board_summary": {
                "buildings_alive": 6,
                "building_hp_total": 7,
                "grid_power": 6,
                "enemies_alive": 0,
                "pods_present": 1,
                "mech_hp": [],
            },
            "search_stats": {},
        }
    }))

    actual = _board(6)
    result = commands._record_post_enemy(
        session,
        actual,
        1,
        bridge_data={"phase": "combat_player", "turn": 2},
    )

    assert result["status"] == "INVESTIGATE_POST_ENEMY"
    assert result["blocking"] is True
    assert result["deltas"]["pods_present_diff"] == -1
    assert "Lost 1 unexpected pod(s)" in result["deltas"]["unexpected_events"]
    assert session.post_enemy_block is not None
    assert session.post_enemy_block["deltas"]["pods_present_diff"] == -1


def test_record_post_enemy_explains_pod_lost_to_emergent_enemy(
    tmp_path,
    monkeypatch,
):
    from src.solver import analysis

    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    monkeypatch.setattr(analysis, "append_to_failure_db", lambda *args, **kwargs: None)
    session = RunSession(run_id="run")
    session.mission_index = 11
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    solve_data = {
        "predicted_board_summary": {
            "buildings_alive": 6,
            "building_hp_total": 7,
            "grid_power": 6,
            "enemies_alive": 0,
            "pods_present": 1,
            "mech_hp": [],
        },
        "search_stats": {},
        "actions": [{"mech_uid": 0}],
        **_pod_checkpoints([(5, 5)]),
    }
    (run_dir / "m11_turn_01_solve.json").write_text(json.dumps({"data": solve_data}))

    actual = _board(6)
    actual.units.append(_enemy(369, 5, 5))
    result = commands._record_post_enemy(
        session,
        actual,
        1,
        bridge_data={"phase": "combat_player", "turn": 2},
    )

    assert result["status"] == "POST_ENEMY_RECORDED"
    assert result["blocking"] is False
    assert result["deltas"]["pods_present_diff"] == -1
    assert result["deltas"]["pods_present_unexplained_diff"] == 0
    assert result["deltas"]["emergent_enemy_pod_losses"] == [{
        "pos": [5, 5],
        "uid": 369,
        "type": "Leaper2",
        "reason": "emergent_enemy_reachable_from_spawn_occupied_predicted_pod_tile",
    }]
    assert not any(
        "unexpected pod" in event
        for event in result["deltas"]["unexpected_events"]
    )
    assert session.post_enemy_block is None


def test_emergent_pod_classifier_fails_closed_for_known_or_wrong_tile_enemy():
    base = {
        "pods_present_diff": -1,
        "pods_present_unexplained_diff": -1,
        "unexpected_events": ["Lost 1 unexpected pod(s)"],
    }
    for enemy, known_uids in ((_enemy(100, 5, 5), [100]), (_enemy(369, 4, 5), [])):
        board = _board(6)
        board.units.append(enemy)
        result = commands._classify_emergent_enemy_pod_losses(
            dict(base),
            _pod_checkpoints([(5, 5)], known_uids),
            board,
            actual_turn=2,
            expected_turn=2,
        )
        assert result["pods_present_unexplained_diff"] == -1
        assert result["emergent_enemy_pod_losses"] == []
        assert commands._post_enemy_needs_investigation(result)


def test_surviving_destroy_objective_blocks_with_equal_enemy_aggregates():
    predicted = {
        "buildings_alive": 5,
        "building_hp_total": 6,
        "grid_power": 5,
        "enemies_alive": 3,
        "enemy_hp_total": 6,
        "mech_hp": [],
        "destroy_objective_units_alive": 0,
    }
    actual = {
        **predicted,
        "destroy_objective_units_alive": 1,
        "destroy_objective_units": [{
            "uid": 1124,
            "type": "BlobberBoss",
            "pos": [5, 6],
            "hp": 2,
            "alive": True,
        }],
    }

    deltas = commands._compute_deltas(predicted, actual)

    assert deltas["enemies_alive_diff"] == 0
    assert deltas["destroy_objective_units_alive_diff"] == 1
    assert (
        "Destroy-objective unit(s) survived unexpectedly"
        in deltas["unexpected_events"]
    )
    assert commands._post_enemy_needs_investigation(deltas)


def test_destroy_objective_dying_unexpectedly_is_better_not_blocking():
    predicted = {
        "buildings_alive": 5,
        "building_hp_total": 6,
        "grid_power": 5,
        "enemies_alive": 3,
        "mech_hp": [],
        "destroy_objective_units_alive": 1,
    }
    actual = {
        **predicted,
        "destroy_objective_units_alive": 0,
    }

    deltas = commands._compute_deltas(predicted, actual)

    assert deltas["destroy_objective_units_alive_diff"] == -1
    assert not commands._post_enemy_needs_investigation(deltas)


def test_record_post_enemy_blocks_surviving_destroy_objective_with_equal_aggregates(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(run_id="run")
    session.mission_index = 14
    session.current_mission = "Mission_BlobberBoss"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "m14_turn_01_solve.json").write_text(json.dumps({
        "data": {
            "predicted_board_summary": {
                "buildings_alive": 6,
                "building_hp_total": 7,
                "grid_power": 5,
                "enemies_alive": 3,
                "enemy_hp_total": 8,
                "mech_hp": [
                    {"uid": 0, "type": "JetMech", "hp": 2, "max_hp": 2}
                ],
                "mission_id": "Mission_BlobberBoss",
                "destroy_objective_units_alive": 0,
            },
            "search_stats": {},
        }
    }))

    actual = _board(5)
    actual.mission_id = "Mission_BlobberBoss"
    actual.destroy_objective_unit_types = ["BlobberBoss"]
    boss = _enemy(1124, 5, 6)
    boss.type = "BlobberBoss"
    boss.hp = 2
    boss.max_hp = 5
    actual.units.extend([boss, _enemy(1196, 5, 2), _enemy(1220, 3, 5)])

    result = commands._record_post_enemy(session, actual, 1)

    assert result["status"] == "INVESTIGATE_POST_ENEMY"
    assert result["blocking"] is True
    assert result["deltas"]["enemies_alive_diff"] == 0
    assert result["deltas"]["destroy_objective_units_alive_diff"] == 1
    assert result["deltas"]["unexpected_events"] == [
        "Destroy-objective unit(s) survived unexpectedly"
    ]
    assert session.post_enemy_block is not None


def test_emergent_pod_classifier_fails_closed_for_partial_checkpoint_identity():
    board = _board(6)
    board.units.append(_enemy(369, 5, 5))
    checkpoints = _pod_checkpoints([(5, 5)])
    checkpoints["post_player_board"]["units"] = [{"team": 6}]
    result = commands._classify_emergent_enemy_pod_losses(
        {
            "pods_present_diff": -1,
            "pods_present_unexplained_diff": -1,
            "unexpected_events": ["Lost 1 unexpected pod(s)"],
        },
        checkpoints,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    assert result["pods_present_unexplained_diff"] == -1
    assert result["emergent_enemy_pod_losses"] == []
    assert commands._post_enemy_needs_investigation(result)


def test_emergent_pod_classifier_does_not_explain_new_minor_or_unreachable_enemy():
    base = {
        "pods_present_diff": -1,
        "pods_present_unexplained_diff": -1,
        "unexpected_events": ["Lost 1 unexpected pod(s)"],
    }
    for enemy in (_enemy(369, 5, 5, minor=True), _enemy(370, 0, 0)):
        board = _board(6)
        board.units.append(enemy)
        result = commands._classify_emergent_enemy_pod_losses(
            dict(base),
            _pod_checkpoints([(enemy.x, enemy.y)]),
            board,
            actual_turn=2,
            expected_turn=2,
        )
        assert result["pods_present_unexplained_diff"] == -1
        assert result["emergent_enemy_pod_losses"] == []
        assert commands._post_enemy_needs_investigation(result)


def test_emergent_pod_classifier_only_suppresses_matched_loss():
    board = _board(6)
    board.units.append(_enemy(369, 5, 5))
    result = commands._classify_emergent_enemy_pod_losses(
        {
            "pods_present_diff": -2,
            "pods_present_unexplained_diff": -2,
            "unexpected_events": ["Lost 2 unexpected pod(s)"],
        },
        _pod_checkpoints([(5, 5), (4, 4)]),
        board,
        actual_turn=2,
        expected_turn=2,
    )

    assert result["pods_present_diff"] == -2
    assert result["pods_present_unexplained_diff"] == -1
    assert len(result["emergent_enemy_pod_losses"]) == 1
    assert "Lost 1 unexpected pod(s)" in result["unexpected_events"]
    assert commands._post_enemy_needs_investigation(result)


def test_explained_emergent_pod_loss_does_not_hide_grid_loss():
    board = _board(5)
    board.units.append(_enemy(369, 5, 5))
    result = commands._classify_emergent_enemy_pod_losses(
        {
            "grid_power_diff": -1,
            "pods_present_diff": -1,
            "pods_present_unexplained_diff": -1,
            "unexpected_events": [
                "Grid power dropped by 1 unexpectedly",
                "Lost 1 unexpected pod(s)",
            ],
        },
        _pod_checkpoints([(5, 5)]),
        board,
        actual_turn=2,
        expected_turn=2,
    )

    assert result["pods_present_unexplained_diff"] == 0
    assert commands._post_enemy_needs_investigation(result)


def test_unfair_post_enemy_gate_accepts_predicted_mech_status():
    session = RunSession(run_id="run", difficulty=3)
    deltas = {
        "mech_status_diff": [{
            "key": "mechs_acid",
            "status": "ACID",
            "predicted_count": 1,
            "actual_count": 1,
            "unexpected": [],
            "cleared": [],
        }],
    }

    assert not commands._post_enemy_needs_investigation(deltas, session)


def test_unfair_post_enemy_gate_blocks_unexpected_mech_status():
    session = RunSession(run_id="run", difficulty=3)
    acid_mech = {"uid": 1, "type": "JetMech", "pos": [6, 7]}
    deltas = {
        "mech_status_diff": [{
            "key": "mechs_acid",
            "status": "ACID",
            "predicted_count": 0,
            "actual_count": 1,
            "unexpected": [acid_mech],
            "cleared": [],
        }],
    }

    assert commands._post_enemy_needs_investigation(deltas, session)


def _next_turn_web_case(
    *,
    previous_target=(5, 2),
    current_target=(6, 2),
    previous_source_pos=(6, 1),
    previous_origin=None,
):
    board = _board(5)
    mech = board.units[0]
    mech.web = True
    mech.web_source_uid = 371
    source = _enemy(371, 5, 2)
    source.has_queued_attack = True
    source.queued_target_x, source.queued_target_y = current_target
    source.target_x, source.target_y = current_target
    board.units.append(source)
    solve_data = {
        "post_player_board": {
            "units": [
                {
                    "uid": mech.uid,
                    "type": mech.type,
                    "team": 1,
                    "hp": mech.hp,
                    "x": mech.x,
                    "y": mech.y,
                },
                ({
                    "uid": source.uid,
                    "type": source.type,
                    "team": 6,
                    "hp": 2,
                    "x": previous_source_pos[0],
                    "y": previous_source_pos[1],
                    "weapons": ["LeaperAtk2"],
                    "has_queued_attack": True,
                    "queued_target": list(previous_target),
                } | ({"queued_origin": list(previous_origin)}
                     if previous_origin is not None else {})),
            ],
        },
    }
    web_item = {
        "uid": mech.uid,
        "type": mech.type,
        "pos": [mech.x, mech.y],
    }
    deltas = {
        "mech_status_diff": [{
            "key": "mechs_webbed",
            "status": "Web",
            "predicted_count": 0,
            "actual_count": 1,
            "unexpected": [web_item],
            "cleared": [],
        }],
        "unexpected_events": [
            f"{mech.type} gained unexpected Web status"
        ],
    }
    return board, solve_data, deltas, web_item


def _emergent_next_turn_web_case():
    """Reproduce run 20260713_052159_731 turn 2 -> 3."""
    board = _board(5)
    mech = board.units[0]
    mech.type = "HornetMech"
    mech.x, mech.y = 5, 3
    mech.web = True
    mech.web_source_uid = 792

    source = _enemy(792, 6, 3)
    source.type = "Scorpion2"
    source.hp = source.max_hp = 5
    source.move_speed = 3
    source.weapon = "ScorpionAtk2"
    source.has_queued_attack = True
    source.queued_target_x, source.queued_target_y = mech.x, mech.y
    source.target_x, source.target_y = mech.x, mech.y
    board.units.append(source)

    mech_checkpoint = {
        "uid": mech.uid,
        "type": mech.type,
        "team": 1,
        "hp": mech.hp,
        "x": mech.x,
        "y": mech.y,
    }
    old_enemy_checkpoint = {
        "uid": 773,
        "type": "Bouncer1",
        "team": 6,
        "hp": 2,
        "x": 3,
        "y": 4,
    }
    solve_data = {
        "simulator_version": 352,
        "post_player_board": {
            "turn": 2,
            "units": [mech_checkpoint, old_enemy_checkpoint],
            "spawning_tiles": [[6, 3], [7, 3], [5, 5]],
        },
        "final_board": {
            "turn": 3,
            "units": [
                dict(mech_checkpoint),
                dict(old_enemy_checkpoint),
            ],
            "spawning_tiles": [[5, 5]],
        },
    }
    web_item = {
        "uid": mech.uid,
        "type": mech.type,
        "pos": [mech.x, mech.y],
    }
    deltas = {
        "mech_status_diff": [{
            "key": "mechs_webbed",
            "status": "Web",
            "predicted_count": 0,
            "actual_count": 1,
            "unexpected": [web_item],
            "cleared": [],
        }],
        "unexpected_events": [
            f"{mech.type} gained unexpected Web status"
        ],
    }
    return board, solve_data, deltas, web_item


def _projected_wind_web_case():
    """Reproduce Mission_Wind turn 2 -> 3 from run 20260713_052159_731."""
    board = _board(5)
    mech = board.units[0]
    mech.type = "PunchMech"
    mech.x, mech.y = 5, 6
    mech.web = True
    mech.web_source_uid = 808

    source = _enemy(808, 4, 6)
    source.type = "Scorpion2"
    source.hp = source.max_hp = 5
    source.weapon = "ScorpionAtk2"
    source.has_queued_attack = True
    source.queued_target_x, source.queued_target_y = mech.x, mech.y
    source.target_x, source.target_y = mech.x, mech.y
    board.units.append(source)

    post_mech = {
        "uid": mech.uid,
        "type": mech.type,
        "team": 1,
        "hp": mech.hp,
        "x": 5,
        "y": 5,
    }
    post_source = {
        "uid": source.uid,
        "type": source.type,
        "team": 6,
        "hp": source.hp,
        "x": 2,
        "y": 7,
        "weapons": ["ScorpionAtk2"],
        "has_queued_attack": True,
        "queued_origin": [2, 6],
        "queued_target": [2, 5],
        "move": source.move_speed,
    }
    solve_data = {
        "simulator_version": 353,
        "post_player_board": {
            "turn": 2,
            "units": [post_mech, post_source],
            "spawning_tiles": [[5, 2], [7, 4]],
        },
        "final_board": {
            "turn": 3,
            "units": [
                dict(post_mech, x=5, y=6),
                dict(post_source),
            ],
            "spawning_tiles": [],
        },
    }
    web_item = {
        "uid": mech.uid,
        "type": mech.type,
        "pos": [mech.x, mech.y],
    }
    deltas = {
        "mech_status_diff": [{
            "key": "mechs_webbed",
            "status": "Web",
            "predicted_count": 0,
            "actual_count": 1,
            "unexpected": [web_item],
            "cleared": [],
        }],
        "unexpected_events": [
            f"{mech.type} gained unexpected Web status"
        ],
    }
    return board, solve_data, deltas, web_item


def _next_turn_spider_egg_web_case():
    """Reproduce Detritus Mission_AcidStorm turn 1 -> 2."""
    board = _board(6)
    mech = board.units[0]
    mech.type = "IgniteMech"
    mech.x, mech.y = 4, 5
    mech.hp = mech.max_hp = 4
    mech.web = True
    mech.web_source_uid = 1319

    spider = _enemy(1262, 6, 4)
    spider.type = "Spider2"
    spider.hp = spider.max_hp = 4
    spider.move_speed = 2
    spider.weapon = "SpiderAtk2"
    spider.has_queued_attack = False
    spider.queued_target_x = spider.queued_target_y = -1
    # Live save/bridge retains piOrigin even though the special Spider setup
    # has no queued skill or queued target.
    spider.queued_origin_x, spider.queued_origin_y = spider.x, spider.y
    board.units.append(spider)

    egg = _enemy(1319, 4, 4, minor=True)
    egg.type = "WebbEgg1"
    egg.hp = egg.max_hp = 1
    egg.move_speed = 0
    egg.weapon = "WebeggHatch1"
    egg.has_queued_attack = True
    egg.queued_target_x, egg.queued_target_y = egg.x, egg.y
    egg.queued_origin_x, egg.queued_origin_y = egg.x, egg.y
    board.units.append(egg)

    mech_checkpoint = {
        "uid": mech.uid,
        "type": mech.type,
        "team": 1,
        "hp": mech.hp,
        "x": mech.x,
        "y": mech.y,
    }
    spider_checkpoint = {
        "uid": spider.uid,
        "type": spider.type,
        "team": 6,
        "hp": spider.hp,
        "x": spider.x,
        "y": spider.y,
        "weapons": [spider.weapon],
        "queued_origin": [-1, -1],
        "queued_target": [-1, -1],
    }
    solve_data = {
        "simulator_version": 360,
        "post_player_board": {
            "turn": 1,
            "units": [dict(mech_checkpoint), dict(spider_checkpoint)],
            "spawning_tiles": [[7, 4]],
        },
        "final_board": {
            "turn": 2,
            "units": [dict(mech_checkpoint), dict(spider_checkpoint)],
            "spawning_tiles": [],
        },
    }
    web_item = {
        "uid": mech.uid,
        "type": mech.type,
        "pos": [mech.x, mech.y],
    }
    deltas = {
        "mech_status_diff": [{
            "key": "mechs_webbed",
            "status": "Web",
            "predicted_count": 0,
            "actual_count": 1,
            "unexpected": [web_item],
            "cleared": [],
        }],
        "unexpected_events": [
            f"{mech.type} gained unexpected Web status"
        ],
    }
    return board, solve_data, deltas, web_item


def test_next_turn_retarget_web_is_explained_for_unfair_gate():
    board, solve_data, deltas, web_item = _next_turn_web_case()

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    web_delta = result["mech_status_diff"][0]
    assert web_delta["unexpected"] == [web_item]
    assert web_delta["unexplained_unexpected"] == []
    assert web_delta["next_turn_web_grapples"] == [{
        "uid": 0,
        "type": "JetMech",
        "pos": [6, 2],
        "source_uid": 371,
        "source_type": "Leaper2",
        "previous_target": [5, 2],
        "current_target": [6, 2],
        "reason": "next_turn_web_source_retargeted_stationary_mech",
    }]
    assert result["unexpected_events"] == []
    assert not commands._post_enemy_needs_investigation(
        result,
        RunSession(run_id="run", difficulty=3),
    )


def test_next_turn_spider_egg_web_is_explained_for_unfair_gate():
    board, solve_data, deltas, web_item = _next_turn_spider_egg_web_case()

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    web_delta = result["mech_status_diff"][0]
    assert web_delta["unexpected"] == [web_item]
    assert web_delta["unexplained_unexpected"] == []
    assert web_delta["next_turn_web_grapples"] == [{
        "uid": 0,
        "type": "IgniteMech",
        "pos": [4, 5],
        "source_uid": 1319,
        "source_type": "WebbEgg1",
        "spider_uid": 1262,
        "spider_type": "Spider2",
        "egg_position": [4, 4],
        "reason": "next_turn_surviving_spider_laid_adjacent_webb_egg",
    }]
    assert result["unexpected_events"] == []
    assert not commands._post_enemy_needs_investigation(
        result,
        RunSession(run_id="run", difficulty=3),
    )


def test_next_turn_spider_egg_web_requires_complete_fresh_evidence():
    cases = (
        "outside_turn_window",
        "old_simulator",
        "egg_known_post_player",
        "egg_known_final",
        "egg_not_adjacent",
        "egg_not_self_hatching",
        "egg_origin_not_self",
        "moved_mech",
        "mech_hp_drift",
        "missing_final_mech",
        "missing_post_player_spider",
        "missing_final_spider",
        "spider_hp_drift",
        "moved_spider",
        "post_player_spider_queued",
        "live_spider_queued",
        "live_spider_queue_sentinels_stale",
        "live_spider_origin_stale",
        "live_spider_frozen",
        "post_player_spider_frozen",
        "wrong_spider_weapon",
        "ambiguous_spider_parent",
        "competing_queued_spider",
        "spider_psion_present",
        "final_spider_psion_present",
        "actual_only_spider_boss",
        "extra_new_egg",
        "existing_adjacent_egg",
    )
    for case in cases:
        board, solve_data, deltas, web_item = _next_turn_spider_egg_web_case()
        actual_turn = 2
        mech = next(unit for unit in board.units if unit.uid == 0)
        spider = next(unit for unit in board.units if unit.uid == 1262)
        egg = next(unit for unit in board.units if unit.uid == 1319)
        post_units = solve_data["post_player_board"]["units"]
        final_units = solve_data["final_board"]["units"]

        if case == "outside_turn_window":
            actual_turn = 3
        elif case == "old_simulator":
            solve_data["simulator_version"] = 352
        elif case == "egg_known_post_player":
            post_units.append({
                "uid": egg.uid,
                "type": egg.type,
                "team": 6,
                "hp": egg.hp,
                "x": egg.x,
                "y": egg.y,
            })
        elif case == "egg_known_final":
            final_units.append({
                "uid": egg.uid,
                "type": egg.type,
                "team": 6,
                "hp": egg.hp,
                "x": egg.x,
                "y": egg.y,
            })
        elif case == "egg_not_adjacent":
            egg.x, egg.y = 4, 3
            egg.queued_target_x, egg.queued_target_y = egg.x, egg.y
        elif case == "egg_not_self_hatching":
            egg.queued_target_x, egg.queued_target_y = 3, 4
        elif case == "egg_origin_not_self":
            egg.queued_origin_x, egg.queued_origin_y = 3, 4
        elif case == "moved_mech":
            post_units[0]["x"] = 3
        elif case == "mech_hp_drift":
            post_units[0]["hp"] = mech.hp - 1
        elif case == "missing_final_mech":
            final_units.pop(0)
        elif case == "missing_post_player_spider":
            post_units.pop(1)
        elif case == "missing_final_spider":
            final_units.pop(1)
        elif case == "spider_hp_drift":
            final_units[1]["hp"] = spider.hp - 1
        elif case == "moved_spider":
            spider.x = 5
        elif case == "post_player_spider_queued":
            post_units[1]["has_queued_attack"] = True
            post_units[1]["queued_origin"] = [spider.x, spider.y]
            post_units[1]["queued_target"] = [egg.x, egg.y]
        elif case == "live_spider_queued":
            spider.has_queued_attack = True
            spider.queued_target_x, spider.queued_target_y = egg.x, egg.y
        elif case == "live_spider_queue_sentinels_stale":
            spider.queued_origin_x, spider.queued_origin_y = spider.x, spider.y
            spider.queued_target_x, spider.queued_target_y = egg.x, egg.y
        elif case == "live_spider_origin_stale":
            spider.queued_origin_x, spider.queued_origin_y = spider.x - 1, spider.y
        elif case == "live_spider_frozen":
            spider.frozen = True
        elif case == "post_player_spider_frozen":
            post_units[1]["frozen"] = True
        elif case == "wrong_spider_weapon":
            spider.weapon = "LeaperAtk2"
        elif case == "ambiguous_spider_parent":
            other = _enemy(1400, 4, 2)
            other.type = "Spider1"
            other.hp = other.max_hp = 2
            other.move_speed = 2
            other.weapon = "SpiderAtk1"
            other.has_queued_attack = False
            other.queued_target_x = other.queued_target_y = -1
            board.units.append(other)
            other_checkpoint = {
                "uid": other.uid,
                "type": other.type,
                "team": 6,
                "hp": other.hp,
                "x": other.x,
                "y": other.y,
                "weapons": [other.weapon],
                "queued_origin": [-1, -1],
                "queued_target": [-1, -1],
            }
            post_units.append(dict(other_checkpoint))
            final_units.append(dict(other_checkpoint))
        elif case == "competing_queued_spider":
            queued = _enemy(1401, 2, 4)
            queued.type = "Spider1"
            queued.hp = queued.max_hp = 2
            queued.weapon = "SpiderAtk1"
            queued.has_queued_attack = False
            queued.queued_target_x = queued.queued_target_y = -1
            board.units.append(queued)
            queued_checkpoint = {
                "uid": queued.uid,
                "type": queued.type,
                "team": 6,
                "hp": queued.hp,
                "x": queued.x,
                "y": queued.y,
                "weapons": [queued.weapon],
                "has_queued_attack": True,
                "queued_origin": [queued.x, queued.y],
                "queued_target": [egg.x, egg.y],
            }
            post_units.append(dict(queued_checkpoint))
            final_units.append(dict(
                queued_checkpoint,
                has_queued_attack=False,
                queued_origin=[-1, -1],
                queued_target=[-1, -1],
            ))
        elif case == "spider_psion_present":
            psion_checkpoint = {
                "uid": 1402,
                "type": "Jelly_Spider1",
                "team": 6,
                "hp": 2,
                "x": 1,
                "y": 1,
                "weapons": [],
                "queued_origin": [-1, -1],
                "queued_target": [-1, -1],
            }
            post_units.append(psion_checkpoint)
        elif case == "final_spider_psion_present":
            final_units.append({
                "uid": 1403,
                "type": "Jelly_Spider1",
                "team": 6,
                "hp": 2,
                "x": 1,
                "y": 1,
                "weapons": [],
                "queued_origin": [-1, -1],
                "queued_target": [-1, -1],
            })
        elif case == "actual_only_spider_boss":
            boss = _enemy(1404, 2, 2)
            boss.type = "SpiderBoss"
            boss.hp = boss.max_hp = 6
            boss.weapon = "SpiderAtk2"
            boss.has_queued_attack = False
            boss.queued_target_x = boss.queued_target_y = -1
            board.units.append(boss)
        elif case == "extra_new_egg":
            other_egg = _enemy(1405, 2, 2, minor=True)
            other_egg.type = "WebbEgg1"
            other_egg.hp = other_egg.max_hp = 1
            other_egg.weapon = "WebeggHatch1"
            other_egg.has_queued_attack = True
            other_egg.queued_origin_x = other_egg.queued_target_x = other_egg.x
            other_egg.queued_origin_y = other_egg.queued_target_y = other_egg.y
            board.units.append(other_egg)
        elif case == "existing_adjacent_egg":
            old_egg = _enemy(1406, 5, 5, minor=True)
            old_egg.type = "WebbEgg1"
            old_egg.hp = old_egg.max_hp = 1
            old_egg.weapon = "WebeggHatch1"
            old_egg.has_queued_attack = True
            old_egg.queued_origin_x = old_egg.queued_target_x = old_egg.x
            old_egg.queued_origin_y = old_egg.queued_target_y = old_egg.y
            board.units.append(old_egg)
            old_checkpoint = {
                "uid": old_egg.uid,
                "type": old_egg.type,
                "team": 6,
                "hp": old_egg.hp,
                "x": old_egg.x,
                "y": old_egg.y,
                "weapons": [old_egg.weapon],
                "has_queued_attack": True,
                "queued_origin": [old_egg.x, old_egg.y],
                "queued_target": [old_egg.x, old_egg.y],
            }
            post_units.append(dict(old_checkpoint))
            final_units.append(dict(old_checkpoint))

        result = commands._classify_next_turn_web_grapples(
            deltas,
            solve_data,
            board,
            actual_turn=actual_turn,
            expected_turn=2,
        )

        web_delta = result["mech_status_diff"][0]
        assert web_delta.get(
            "unexplained_unexpected",
            web_delta["unexpected"],
        ) == [web_item], case
        assert result["next_turn_web_grapples"] == [], case
        assert commands._post_enemy_needs_investigation(
            result,
            RunSession(run_id="run", difficulty=3),
        ), case


def test_explained_next_turn_spider_egg_web_does_not_hide_grid_loss():
    board, solve_data, deltas, _web_item = _next_turn_spider_egg_web_case()
    deltas["grid_power_diff"] = -1
    deltas["unexpected_events"].insert(
        0,
        "Grid power dropped by 1 unexpectedly",
    )

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    assert len(result["next_turn_web_grapples"]) == 1
    assert result["unexpected_events"] == [
        "Grid power dropped by 1 unexpectedly"
    ]
    assert commands._post_enemy_needs_investigation(
        result,
        RunSession(run_id="run", difficulty=3),
    )


def test_one_next_turn_spider_egg_can_explain_multiple_adjacent_webs():
    board, solve_data, deltas, _web_item = _next_turn_spider_egg_web_case()
    first = board.units[0]
    second = Unit(**vars(first))
    second.uid = 2
    second.x, second.y = 3, 4
    second.web_source_uid = 1319
    board.units.append(second)

    checkpoint = {
        "uid": second.uid,
        "type": second.type,
        "team": 1,
        "hp": second.hp,
        "x": second.x,
        "y": second.y,
    }
    solve_data["post_player_board"]["units"].append(dict(checkpoint))
    solve_data["final_board"]["units"].append(dict(checkpoint))
    second_item = {
        "uid": second.uid,
        "type": second.type,
        "pos": [second.x, second.y],
    }
    deltas["mech_status_diff"][0]["actual_count"] = 2
    deltas["mech_status_diff"][0]["unexpected"].append(second_item)
    deltas["unexpected_events"].append(
        f"{second.type} gained unexpected Web status"
    )

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    web_delta = result["mech_status_diff"][0]
    assert web_delta["unexplained_unexpected"] == []
    assert len(result["next_turn_web_grapples"]) == 2
    assert {
        (item["uid"], item["source_uid"], item["spider_uid"])
        for item in result["next_turn_web_grapples"]
    } == {(0, 1319, 1262), (2, 1319, 1262)}
    assert result["unexpected_events"] == []


def test_existing_queueless_leaper_first_web_is_explained_for_unfair_gate():
    """Archive m11 t3: existing E2 Leaper first-targets stationary G4."""
    board = _board(5)
    mech = board.units[0]
    mech.type = "HornetMech"
    mech.x, mech.y = 4, 1
    mech.web = True
    mech.web_source_uid = 1097

    source = _enemy(1097, 4, 2)
    source.type = "Leaper2"
    source.hp = source.max_hp = 3
    source.move_speed = 4
    source.weapon = "LeaperAtk2"
    source.has_queued_attack = True
    source.queued_target_x, source.queued_target_y = mech.x, mech.y
    source.target_x, source.target_y = mech.x, mech.y
    board.units.append(source)

    solve_data = {
        "simulator_version": 353,
        "post_player_board": {
            "turn": 3,
            "units": [
                {
                    "uid": mech.uid,
                    "type": mech.type,
                    "team": 1,
                    "hp": mech.hp,
                    "x": mech.x,
                    "y": mech.y,
                },
                {
                    "uid": source.uid,
                    "type": source.type,
                    "team": 6,
                    "hp": source.hp,
                    "x": 6,
                    "y": 3,
                    "move": 4,
                    "weapons": ["LeaperAtk2"],
                    # False is omitted by compact replay serialization; the
                    # paired sentinels are the canonical queueless proof.
                    "queued_origin": [-1, -1],
                    "queued_target": [-1, -1],
                },
            ],
        },
        "final_board": {
            "turn": 4,
            "units": [
                {
                    "uid": mech.uid,
                    "type": mech.type,
                    "team": 1,
                    "hp": mech.hp,
                    "x": mech.x,
                    "y": mech.y,
                },
                {
                    "uid": source.uid,
                    "type": source.type,
                    "team": 6,
                    "hp": source.hp,
                    "x": 6,
                    "y": 3,
                    "move": 4,
                    "can_move": True,
                    "weapons": ["LeaperAtk2"],
                },
            ],
        },
    }
    web_item = {
        "uid": mech.uid,
        "type": mech.type,
        "pos": [mech.x, mech.y],
    }
    deltas = {
        "mech_status_diff": [{
            "key": "mechs_webbed",
            "status": "Web",
            "predicted_count": 0,
            "actual_count": 1,
            "unexpected": [web_item],
            "cleared": [],
        }],
        "unexpected_events": [
            f"{mech.type} gained unexpected Web status"
        ],
    }

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=4,
        expected_turn=4,
    )

    web_delta = result["mech_status_diff"][0]
    assert web_delta["unexplained_unexpected"] == []
    assert web_delta["next_turn_web_grapples"] == [{
        "uid": 0,
        "type": "HornetMech",
        "pos": [4, 1],
        "source_uid": 1097,
        "source_type": "Leaper2",
        "previous_target": None,
        "current_target": [4, 1],
        "reason": (
            "next_turn_existing_queueless_web_source_first_queued_stationary_mech"
        ),
    }]
    assert result["unexpected_events"] == []
    assert not commands._post_enemy_needs_investigation(
        result,
        RunSession(run_id="run", difficulty=3),
    )


def test_existing_queueless_first_web_requires_valid_move_range():
    board = _board(5)
    mech = board.units[0]
    mech.web = True
    mech.web_source_uid = 371
    source = _enemy(371, mech.x - 1, mech.y)
    source.has_queued_attack = True
    source.queued_target_x, source.queued_target_y = mech.x, mech.y
    source.target_x, source.target_y = mech.x, mech.y
    board.units.append(source)
    solve_data = {
        "simulator_version": 353,
        "post_player_board": {
            "turn": 1,
            "units": [
                {
                    "uid": mech.uid,
                    "type": mech.type,
                    "team": 1,
                    "hp": mech.hp,
                    "x": mech.x,
                    "y": mech.y,
                },
                {
                    "uid": source.uid,
                    "type": source.type,
                    "team": 6,
                    "hp": source.hp,
                    "x": 0,
                    "y": 0,
                    "move": 3,
                    "weapons": ["LeaperAtk2"],
                    "queued_origin": [-1, -1],
                    "queued_target": [-1, -1],
                },
            ],
        },
        "final_board": {
            "turn": 2,
            "units": [
                {
                    "uid": mech.uid,
                    "type": mech.type,
                    "team": 1,
                    "hp": mech.hp,
                    "x": mech.x,
                    "y": mech.y,
                },
                {
                    "uid": source.uid,
                    "type": source.type,
                    "team": 6,
                    "hp": source.hp,
                    "x": 0,
                    "y": 0,
                    "move": 3,
                    "can_move": True,
                    "weapons": ["LeaperAtk2"],
                },
            ],
        },
    }
    web_item = {"uid": mech.uid, "type": mech.type, "pos": [mech.x, mech.y]}
    def fresh_deltas():
        return {
            "mech_status_diff": [{
                "key": "mechs_webbed",
                "status": "Web",
                "predicted_count": 0,
                "actual_count": 1,
                "unexpected": [web_item],
                "cleared": [],
            }],
            "unexpected_events": [
                f"{mech.type} gained unexpected Web status"
            ],
        }

    result = commands._classify_next_turn_web_grapples(
        fresh_deltas(),
        solve_data,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    assert result["mech_status_diff"][0]["unexplained_unexpected"] == [web_item]
    assert result["next_turn_web_grapples"] == []

    # Even a stationary source needs a valid nonnegative movement bound. The
    # equality branch must not let malformed ``move=-1`` checkpoint data pass.
    final_source = solve_data["final_board"]["units"][1]
    final_source.update({"x": source.x, "y": source.y, "move": -1})
    result = commands._classify_next_turn_web_grapples(
        fresh_deltas(),
        solve_data,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    assert result["mech_status_diff"][0]["unexplained_unexpected"] == [web_item]
    assert result["next_turn_web_grapples"] == []

    # Malformed status payloads must also fail closed rather than raising.
    final_source.update({"move": source.move_speed, "frozen": []})
    result = commands._classify_next_turn_web_grapples(
        fresh_deltas(),
        solve_data,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    assert result["mech_status_diff"][0]["unexplained_unexpected"] == [web_item]
    assert result["next_turn_web_grapples"] == []


def test_existing_queueless_first_web_rejects_explicit_null_queue_flag():
    board = _board(5)
    mech = board.units[0]
    mech.web = True
    mech.web_source_uid = 371
    source = _enemy(371, mech.x - 1, mech.y)
    source.has_queued_attack = True
    source.queued_target_x, source.queued_target_y = mech.x, mech.y
    source.target_x, source.target_y = mech.x, mech.y
    board.units.append(source)
    previous_source = {
        "uid": source.uid,
        "type": source.type,
        "team": 6,
        "hp": source.hp,
        "x": source.x,
        "y": source.y,
        "move": source.move_speed,
        "weapons": ["LeaperAtk2"],
        "has_queued_attack": None,
        "queued_origin": [-1, -1],
        "queued_target": [-1, -1],
    }
    mech_checkpoint = {
        "uid": mech.uid,
        "type": mech.type,
        "team": 1,
        "hp": mech.hp,
        "x": mech.x,
        "y": mech.y,
    }
    solve_data = {
        "simulator_version": 353,
        "post_player_board": {
            "turn": 1,
            "units": [mech_checkpoint, previous_source],
        },
        "final_board": {
            "turn": 2,
            "units": [
                dict(mech_checkpoint),
                dict(previous_source, has_queued_attack=True),
            ],
        },
    }
    web_item = {"uid": mech.uid, "type": mech.type, "pos": [mech.x, mech.y]}
    deltas = {
        "mech_status_diff": [{
            "key": "mechs_webbed",
            "status": "Web",
            "predicted_count": 0,
            "actual_count": 1,
            "unexpected": [web_item],
            "cleared": [],
        }],
        "unexpected_events": [f"{mech.type} gained unexpected Web status"],
    }

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    assert result["mech_status_diff"][0]["unexplained_unexpected"] == [web_item]
    assert result["next_turn_web_grapples"] == []


def test_emergent_next_turn_web_is_explained_for_unfair_gate():
    board, solve_data, deltas, web_item = _emergent_next_turn_web_case()

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=3,
        expected_turn=3,
    )

    web_delta = result["mech_status_diff"][0]
    assert web_delta["unexpected"] == [web_item]
    assert web_delta["unexplained_unexpected"] == []
    assert web_delta["next_turn_web_grapples"] == [{
        "uid": 0,
        "type": "HornetMech",
        "pos": [5, 3],
        "source_uid": 792,
        "source_type": "Scorpion2",
        "previous_target": None,
        "current_target": [5, 3],
        "spawn_position": [6, 3],
        "reason": "next_turn_emergent_web_source_targeted_stationary_mech",
    }]
    assert result["unexpected_events"] == []
    assert not commands._post_enemy_needs_investigation(
        result,
        RunSession(run_id="run", difficulty=3),
    )


def test_projected_wind_shift_web_is_explained_for_unfair_gate():
    board, solve_data, deltas, web_item = _projected_wind_web_case()

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=3,
        expected_turn=3,
    )

    web_delta = result["mech_status_diff"][0]
    assert web_delta["unexpected"] == [web_item]
    assert web_delta["unexplained_unexpected"] == []
    assert web_delta["next_turn_web_grapples"] == [{
        "uid": 0,
        "type": "PunchMech",
        "pos": [5, 6],
        "source_uid": 808,
        "source_type": "Scorpion2",
        "previous_target": [2, 6],
        "current_target": [5, 6],
        "previous_mech_pos": [5, 5],
        "projected_mech_pos": [5, 6],
        "reason": "next_turn_web_source_retargeted_projected_mech",
    }]
    assert result["unexpected_events"] == []
    assert not commands._post_enemy_needs_investigation(
        result,
        RunSession(run_id="run", difficulty=3),
    )


def test_projected_wind_shift_web_ignores_explicit_extra_tile_rows():
    board, solve_data, deltas, _web_item = _projected_wind_web_case()
    for checkpoint in ("post_player_board", "final_board"):
        primary = solve_data[checkpoint]["units"][0]
        solve_data[checkpoint]["units"].append(dict(
            primary,
            is_extra_tile=True,
            x=primary["x"],
            y=primary["y"] + 1,
        ))

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=3,
        expected_turn=3,
    )

    assert len(result["next_turn_web_grapples"]) == 1
    assert result["mech_status_diff"][0]["unexplained_unexpected"] == []


def test_projected_wind_shift_web_requires_exact_final_checkpoint():
    for case in (
        "missing_final",
        "wrong_position",
        "wrong_type",
        "dead_mech",
        "wrong_hp",
        "wrong_team",
        "boolean_team",
        "boolean_previous_team",
        "out_of_bounds_previous_position",
        "missing_previous_source_position",
        "out_of_bounds_previous_source_position",
        "wrong_turn",
        "old_simulator",
        "duplicate_post_player_uid",
        "duplicate_final_uid",
        "missing_final_source",
        "dead_final_source",
        "wrong_final_source_hp",
        "wrong_final_source_type",
        "wrong_final_source_team",
        "frozen_final_source",
        "webbed_final_source",
        "missing_final_source_move",
        "far_final_source",
    ):
        board, solve_data, deltas, web_item = _projected_wind_web_case()
        if case == "missing_final":
            del solve_data["final_board"]
        elif case == "wrong_position":
            solve_data["final_board"]["units"][0]["y"] = 7
        elif case == "wrong_type":
            solve_data["final_board"]["units"][0]["type"] = "JetMech"
        elif case == "dead_mech":
            solve_data["final_board"]["units"][0]["hp"] = 0
        elif case == "wrong_hp":
            solve_data["final_board"]["units"][0]["hp"] = 1
        elif case == "wrong_team":
            solve_data["final_board"]["units"][0]["team"] = 2
        elif case == "boolean_team":
            solve_data["final_board"]["units"][0]["team"] = True
        elif case == "boolean_previous_team":
            solve_data["post_player_board"]["units"][0]["team"] = True
        elif case == "out_of_bounds_previous_position":
            solve_data["post_player_board"]["units"][0]["x"] = 8
        elif case == "missing_previous_source_position":
            source = solve_data["post_player_board"]["units"][1]
            del source["x"]
            del source["y"]
            del source["queued_origin"]
        elif case == "out_of_bounds_previous_source_position":
            solve_data["post_player_board"]["units"][1]["y"] = 8
        elif case == "wrong_turn":
            solve_data["final_board"]["turn"] = 4
        elif case == "old_simulator":
            solve_data["simulator_version"] = 352
        elif case == "duplicate_post_player_uid":
            units = solve_data["post_player_board"]["units"]
            units.append(dict(units[0]))
        elif case == "duplicate_final_uid":
            units = solve_data["final_board"]["units"]
            units.append(dict(units[0]))
        elif case == "missing_final_source":
            solve_data["final_board"]["units"].pop()
        elif case == "dead_final_source":
            solve_data["final_board"]["units"][1]["hp"] = 0
        elif case == "wrong_final_source_hp":
            solve_data["final_board"]["units"][1]["hp"] = 4
        elif case == "wrong_final_source_type":
            solve_data["final_board"]["units"][1]["type"] = "Leaper2"
        elif case == "wrong_final_source_team":
            solve_data["final_board"]["units"][1]["team"] = True
        elif case == "frozen_final_source":
            solve_data["final_board"]["units"][1]["frozen"] = True
        elif case == "webbed_final_source":
            solve_data["final_board"]["units"][1]["web"] = True
        elif case == "missing_final_source_move":
            del solve_data["final_board"]["units"][1]["move"]
        elif case == "far_final_source":
            solve_data["final_board"]["units"][1]["x"] = 0
            solve_data["final_board"]["units"][1]["y"] = 0
            next(
                unit for unit in board.units if unit.uid == 808
            ).move_speed = 99

        result = commands._classify_next_turn_web_grapples(
            deltas,
            solve_data,
            board,
            actual_turn=3,
            expected_turn=3,
        )

        web_delta = result["mech_status_diff"][0]
        assert web_delta.get(
            "unexplained_unexpected",
            web_delta["unexpected"],
        ) == [web_item], case
        assert result["next_turn_web_grapples"] == [], case
        assert commands._post_enemy_needs_investigation(
            result,
            RunSession(run_id="run", difficulty=3),
        ), case


def test_emergent_next_turn_web_fails_closed_without_complete_spawn_proof():
    for case in (
        "missing_final",
        "retained_marker",
        "known_source",
        "unreachable_marker",
        "moved_final_mech",
        "boolean_marker",
        "wrong_checkpoint_turn",
        "pre_consumed_marker_version",
    ):
        board, solve_data, deltas, web_item = _emergent_next_turn_web_case()
        if case == "missing_final":
            del solve_data["final_board"]
        elif case == "retained_marker":
            solve_data["final_board"]["spawning_tiles"] = [
                [6, 3], [7, 3], [5, 5]
            ]
        elif case == "known_source":
            solve_data["final_board"]["units"].append({
                "uid": 792,
                "type": "Scorpion2",
                "team": 6,
                "hp": 5,
                "x": 6,
                "y": 3,
            })
        elif case == "unreachable_marker":
            solve_data["post_player_board"]["spawning_tiles"] = [[0, 0]]
            solve_data["final_board"]["spawning_tiles"] = []
        elif case == "moved_final_mech":
            solve_data["final_board"]["units"][0]["x"] = 4
        elif case == "boolean_marker":
            solve_data["post_player_board"]["spawning_tiles"] = [[6, False]]
            solve_data["final_board"]["spawning_tiles"] = []
        elif case == "wrong_checkpoint_turn":
            solve_data["final_board"]["turn"] = 4
        elif case == "pre_consumed_marker_version":
            solve_data["simulator_version"] = 349

        result = commands._classify_next_turn_web_grapples(
            deltas,
            solve_data,
            board,
            actual_turn=3,
            expected_turn=3,
        )

        assert result["mech_status_diff"][0]["unexplained_unexpected"] == [
            web_item
        ], case
        assert result["next_turn_web_grapples"] == [], case
        assert commands._post_enemy_needs_investigation(
            result,
            RunSession(run_id="run", difficulty=3),
        ), case


def test_emergent_next_turn_web_requires_exact_live_grapple_evidence():
    for case in ("wrong_owner", "wrong_target", "wrong_weapon", "minor_source"):
        board, solve_data, deltas, web_item = _emergent_next_turn_web_case()
        mech = next(unit for unit in board.units if unit.uid == 0)
        source = next(unit for unit in board.units if unit.uid == 792)
        if case == "wrong_owner":
            mech.web_source_uid = 999
        elif case == "wrong_target":
            source.queued_target_x, source.queued_target_y = 5, 2
        elif case == "wrong_weapon":
            source.weapon = "FireflyAtk1"
        elif case == "minor_source":
            source.minor = True

        result = commands._classify_next_turn_web_grapples(
            deltas,
            solve_data,
            board,
            actual_turn=3,
            expected_turn=3,
        )

        assert result["mech_status_diff"][0]["unexplained_unexpected"] == [
            web_item
        ], case
        assert result["next_turn_web_grapples"] == [], case


def test_explained_emergent_next_turn_web_does_not_hide_grid_loss():
    board, solve_data, deltas, _web_item = _emergent_next_turn_web_case()
    deltas["grid_power_diff"] = -1
    deltas["unexpected_events"].insert(
        0,
        "Grid power dropped by 1 unexpectedly",
    )

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=3,
        expected_turn=3,
    )

    assert len(result["next_turn_web_grapples"]) == 1
    assert result["unexpected_events"] == [
        "Grid power dropped by 1 unexpectedly"
    ]
    assert commands._post_enemy_needs_investigation(
        result,
        RunSession(run_id="run", difficulty=3),
    )


def test_emergent_next_turn_web_matches_multiple_sources_to_consumed_spawns():
    board, solve_data, deltas, _web_item = _emergent_next_turn_web_case()
    solve_data["post_player_board"]["spawning_tiles"] = [
        [6, 3], [7, 4], [5, 5]
    ]

    second_mech = Unit(
        uid=1,
        type="JetMech",
        x=4,
        y=2,
        hp=2,
        max_hp=2,
        team=1,
        is_mech=True,
        move_speed=4,
        flying=True,
        massive=True,
        armor=False,
        pushable=True,
        weapon="Brute_Jetmech",
        active=True,
    )
    second_mech.web = True
    second_mech.web_source_uid = 793
    board.units.append(second_mech)
    second_source = _enemy(793, 4, 3)
    second_source.type = "Scorpion1"
    second_source.move_speed = 3
    second_source.weapon = "ScorpionAtk1"
    second_source.has_queued_attack = True
    second_source.queued_target_x = second_mech.x
    second_source.queued_target_y = second_mech.y
    board.units.append(second_source)

    second_checkpoint = {
        "uid": second_mech.uid,
        "type": second_mech.type,
        "team": 1,
        "hp": second_mech.hp,
        "x": second_mech.x,
        "y": second_mech.y,
    }
    solve_data["post_player_board"]["units"].append(second_checkpoint)
    solve_data["final_board"]["units"].append(dict(second_checkpoint))
    deltas["mech_status_diff"][0]["actual_count"] = 2
    deltas["mech_status_diff"][0]["unexpected"].append({
        "uid": second_mech.uid,
        "type": second_mech.type,
        "pos": [second_mech.x, second_mech.y],
    })
    deltas["unexpected_events"].append(
        f"{second_mech.type} gained unexpected Web status"
    )

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=3,
        expected_turn=3,
    )

    assert result["mech_status_diff"][0]["unexplained_unexpected"] == []
    by_source = {
        item["source_uid"]: item["spawn_position"]
        for item in result["next_turn_web_grapples"]
    }
    assert by_source == {792: [7, 4], 793: [6, 3]}


def test_next_turn_web_classifier_fails_closed_without_changed_queue():
    board, solve_data, deltas, web_item = _next_turn_web_case(
        previous_target=(6, 2),
    )

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    web_delta = result["mech_status_diff"][0]
    assert web_delta["unexplained_unexpected"] == [web_item]
    assert web_delta["next_turn_web_grapples"] == []
    assert commands._post_enemy_needs_investigation(
        result,
        RunSession(run_id="run", difficulty=3),
    )


def test_next_turn_web_classifier_normalizes_displaced_source_target():
    board, solve_data, deltas, web_item = _next_turn_web_case(
        previous_target=(6, 2),
        previous_source_pos=(4, 2),
        previous_origin=(5, 2),
    )

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    web_delta = result["mech_status_diff"][0]
    assert web_delta["unexpected"] == [web_item]
    assert web_delta["unexplained_unexpected"] == []
    assert web_delta["next_turn_web_grapples"] == [{
        "uid": 0,
        "type": "JetMech",
        "pos": [6, 2],
        "source_uid": 371,
        "source_type": "Leaper2",
        "previous_target": [5, 2],
        "current_target": [6, 2],
        "reason": "next_turn_web_source_retargeted_stationary_mech",
    }]
    assert result["unexpected_events"] == []
    assert not commands._post_enemy_needs_investigation(
        result,
        RunSession(run_id="run", difficulty=3),
    )


def test_next_turn_web_classifier_fails_closed_on_wrong_live_target():
    board, solve_data, deltas, web_item = _next_turn_web_case(
        current_target=(5, 2),
    )

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    assert result["mech_status_diff"][0]["unexplained_unexpected"] == [web_item]
    assert result["next_turn_web_grapples"] == []


def test_next_turn_web_classifier_fails_closed_outside_exact_turn_window():
    board, solve_data, deltas, web_item = _next_turn_web_case()

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=3,
        expected_turn=2,
    )

    assert result["next_turn_web_grapples"] == []
    assert result["mech_status_diff"][0]["unexpected"] == [web_item]
    assert commands._post_enemy_needs_investigation(
        result,
        RunSession(run_id="run", difficulty=3),
    )


def test_next_turn_web_classifier_rejects_non_web_source():
    board, solve_data, deltas, web_item = _next_turn_web_case()
    source = next(unit for unit in board.units if unit.uid == 371)
    source.weapon = "FireflyAtk1"

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    assert result["mech_status_diff"][0]["unexplained_unexpected"] == [web_item]
    assert result["next_turn_web_grapples"] == []


def test_explained_next_turn_web_does_not_hide_independent_grid_loss():
    board, solve_data, deltas, _web_item = _next_turn_web_case()
    deltas["grid_power_diff"] = -1
    deltas["unexpected_events"].insert(
        0,
        "Grid power dropped by 1 unexpectedly",
    )

    result = commands._classify_next_turn_web_grapples(
        deltas,
        solve_data,
        board,
        actual_turn=2,
        expected_turn=2,
    )

    assert len(result["next_turn_web_grapples"]) == 1
    assert result["unexpected_events"] == [
        "Grid power dropped by 1 unexpectedly"
    ]
    assert commands._post_enemy_needs_investigation(
        result,
        RunSession(run_id="run", difficulty=3),
    )


def test_record_post_enemy_records_nonlethal_mech_damage_for_lightning_war(
    tmp_path,
    monkeypatch,
):
    achievements_path = tmp_path / "achievements_detailed.json"
    achievements_path.write_text(json.dumps({
        "achievements": {
            "global": [{"name": "Lightning War", "completed": False}]
        }
    }))
    monkeypatch.setattr(commands, "ACHIEVEMENTS_PATH", achievements_path)
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(
        run_id="run",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    session.mission_index = 11
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    solve_file = run_dir / "m11_turn_01_solve.json"
    solve_file.write_text(json.dumps({
        "data": {
            "predicted_board_summary": {
                "buildings_alive": 6,
                "building_hp_total": 7,
                "grid_power": 5,
                "enemies_alive": 0,
                "mech_hp": [
                    {"uid": 0, "type": "JetMech", "hp": 2, "max_hp": 2}
                ],
            },
            "search_stats": {},
        }
    }))

    actual = _board(5)
    actual.units[0].hp = 1
    result = commands._record_post_enemy(session, actual, 1)

    assert result["status"] == "POST_ENEMY_RECORDED"
    assert result["blocking"] is False
    assert result["deltas"]["mech_hp_diff"] == [{
        "uid": 0,
        "type": "JetMech",
        "predicted_hp": 2,
        "actual_hp": 1,
        "diff": -1,
    }]
    assert (
        result["deltas"]["unexpected_events"]
        == ["JetMech took 1 unexpected damage"]
    )
    assert session.post_enemy_block is None


def test_record_post_enemy_blocks_mech_death_for_lightning_war(
    tmp_path,
    monkeypatch,
):
    achievements_path = tmp_path / "achievements_detailed.json"
    achievements_path.write_text(json.dumps({
        "achievements": {
            "global": [{"name": "Lightning War", "completed": False}]
        }
    }))
    monkeypatch.setattr(commands, "ACHIEVEMENTS_PATH", achievements_path)
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(
        run_id="run",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    session.mission_index = 11
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    solve_file = run_dir / "m11_turn_01_solve.json"
    solve_file.write_text(json.dumps({
        "data": {
            "predicted_board_summary": {
                "buildings_alive": 6,
                "building_hp_total": 7,
                "grid_power": 5,
                "enemies_alive": 0,
                "mech_hp": [
                    {"uid": 0, "type": "JetMech", "hp": 2, "max_hp": 2}
                ],
            },
            "search_stats": {},
        }
    }))

    actual = _board(5)
    actual.units[0].hp = 0
    result = commands._record_post_enemy(session, actual, 1)

    assert result["status"] == "INVESTIGATE_POST_ENEMY"
    assert result["blocking"] is True
    assert result["deltas"]["mech_hp_diff"] == [{
        "uid": 0,
        "type": "JetMech",
        "predicted_hp": 2,
        "actual_hp": 0,
        "diff": -2,
    }]
    assert session.post_enemy_block is not None


def test_record_post_enemy_blocks_unexpected_mech_death_for_unfair(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(
        run_id="run",
        difficulty=3,
        tags=["solver_eval", "chaos", "unfair"],
    )
    session.mission_index = 11
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    solve_file = run_dir / "m11_turn_01_solve.json"
    solve_file.write_text(json.dumps({
        "data": {
            "predicted_board_summary": {
                "buildings_alive": 6,
                "building_hp_total": 7,
                "grid_power": 5,
                "enemies_alive": 0,
                "mech_hp": [
                    {"uid": 0, "type": "JetMech", "hp": 1, "max_hp": 2}
                ],
            },
            "search_stats": {},
        }
    }))

    actual = _board(5)
    actual.units[0].hp = 0
    result = commands._record_post_enemy(session, actual, 1)

    assert result["status"] == "INVESTIGATE_POST_ENEMY"
    assert result["blocking"] is True
    assert result["deltas"]["mech_hp_diff"] == [{
        "uid": 0,
        "type": "JetMech",
        "predicted_hp": 1,
        "actual_hp": 0,
        "diff": -1,
    }]
    assert session.post_enemy_block is not None


def test_record_post_enemy_accepts_predicted_mech_death_for_unfair(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(
        run_id="run",
        difficulty=3,
        tags=["solver_eval", "chaos", "unfair"],
    )
    session.mission_index = 11
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    solve_file = run_dir / "m11_turn_01_solve.json"
    solve_file.write_text(json.dumps({
        "data": {
            "predicted_board_summary": {
                "buildings_alive": 6,
                "building_hp_total": 7,
                "grid_power": 5,
                "enemies_alive": 0,
                "mech_hp": [
                    {"uid": 0, "type": "JetMech", "hp": 0, "max_hp": 2}
                ],
            },
            "search_stats": {},
        }
    }))

    actual = _board(5)
    actual.units[0].hp = 0
    result = commands._record_post_enemy(session, actual, 1)

    assert result["status"] == "POST_ENEMY_RECORDED"
    assert result["blocking"] is False
    assert result["deltas"]["mech_hp_diff"] == [{
        "uid": 0,
        "type": "JetMech",
        "predicted_hp": 0,
        "actual_hp": 0,
        "diff": 0,
    }]
    assert session.post_enemy_block is None


def test_record_post_enemy_records_unexpected_mech_status_for_lightning_war(
    tmp_path,
    monkeypatch,
):
    achievements_path = tmp_path / "achievements_detailed.json"
    achievements_path.write_text(json.dumps({
        "achievements": {
            "global": [{"name": "Lightning War", "completed": False}]
        }
    }))
    monkeypatch.setattr(commands, "ACHIEVEMENTS_PATH", achievements_path)
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(
        run_id="run",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    session.mission_index = 11
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    solve_file = run_dir / "m11_turn_01_solve.json"
    solve_file.write_text(json.dumps({
        "data": {
            "predicted_board_summary": {
                "buildings_alive": 6,
                "building_hp_total": 7,
                "grid_power": 5,
                "enemies_alive": 0,
                "mech_hp": [
                    {"uid": 0, "type": "JetMech", "hp": 2, "max_hp": 2}
                ],
                "mechs_webbed": [],
            },
            "search_stats": {},
        }
    }))

    actual = _board(5)
    actual.units[0].web = True
    result = commands._record_post_enemy(session, actual, 1)

    assert result["status"] == "POST_ENEMY_RECORDED"
    assert result["blocking"] is False
    assert result["deltas"]["mech_status_diff"] == [{
        "key": "mechs_webbed",
        "status": "Web",
        "predicted_count": 0,
        "actual_count": 1,
        "unexpected": [{
            "uid": 0,
            "type": "JetMech",
            "pos": [6, 2],
        }],
        "cleared": [],
    }]
    assert (
        result["deltas"]["unexpected_events"]
        == ["JetMech gained unexpected Web status"]
    )
    assert session.post_enemy_block is None


def test_record_post_enemy_blocks_late_turn_window_without_comparing(tmp_path, monkeypatch):
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(run_id="run")
    session.mission_index = 11
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    solve_file = run_dir / "m11_turn_01_solve.json"
    solve_file.write_text(json.dumps({
        "data": {
            "predicted_board_summary": {
                "buildings_alive": 6,
                "building_hp_total": 7,
                "grid_power": 6,
                "enemies_alive": 0,
                "mech_hp": [],
            },
            "search_stats": {},
        }
    }))

    result = commands._record_post_enemy(
        session,
        _board(4),
        1,
        bridge_data={"phase": "combat_player", "turn": 3},
    )

    assert result["status"] == "POST_ENEMY_AUDIT_MISSED_WINDOW"
    assert result["blocking"] is True
    assert result["expected_actual_turn"] == 2
    assert result["actual_turn"] == 3
    assert result["reason"] == "actual_turn_past_expected_post_enemy_window"
    assert result["post_enemy_block"]["source"] == "post_enemy_turn_window_guard"
    assert session.post_enemy_block is not None
    assert not (run_dir / "m11_turn_01_post_enemy.json").exists()


def test_post_enemy_block_round_trips_and_blocks_commands(tmp_path, monkeypatch):
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(run_id="run")
    session.mission_index = 2
    block = commands._install_post_enemy_block(
        session,
        {
            "status": "INVESTIGATE_POST_ENEMY",
            "mission_index": 2,
            "turn": 3,
            "deltas": {"grid_power_diff": -1},
        },
    )

    restored = RunSession.from_dict(session.to_dict())
    assert restored.post_enemy_block == block

    result = commands._post_enemy_block_result(restored)
    assert result["status"] == "INVESTIGATE_POST_ENEMY"
    assert result["blocking"] is True
    assert result["turn"] == 3


def test_final_post_enemy_audit_gate_backfills_missing_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(commands, "RECORDING_DIR", tmp_path)
    session = RunSession(run_id="run")
    session.mission_index = 11
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "m11_turn_01_solve.json").write_text(json.dumps({
        "data": {
            "predicted_board_summary": {
                "buildings_alive": 6,
                "building_hp_total": 7,
                "grid_power": 6,
                "enemies_alive": 0,
                "mech_hp": [],
            },
            "search_stats": {},
        }
    }))
    actual = _board(4)
    actual.mission_id = "Mission_Final"

    result = commands._final_post_enemy_audit_gate(
        session,
        actual,
        {"mission_id": "Mission_Final", "turn": 2},
    )

    assert result["status"] == "INVESTIGATE_POST_ENEMY"
    assert result["source"] == "final_post_enemy_audit_gate"
