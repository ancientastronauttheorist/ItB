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
    assert not commands._terminal_post_enemy_ready_for_audit(
        board, {**bridge, "in_active_mission": True}, solved_turn=3
    )
    assert not commands._terminal_post_enemy_ready_for_audit(
        board, {**bridge, "turn": 5}, solved_turn=3
    )
    assert not commands._terminal_post_enemy_ready_for_audit(
        board, {**bridge, "tiles": []}, solved_turn=3
    )


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
