import json

from src.loop import commands
from src.loop.session import RunSession
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


def test_record_post_enemy_blocks_unexpected_mech_damage_for_lightning_war(
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

    assert result["status"] == "INVESTIGATE_POST_ENEMY"
    assert result["blocking"] is True
    assert result["deltas"]["mech_hp_diff"] == [{
        "uid": 0,
        "type": "JetMech",
        "predicted_hp": 2,
        "actual_hp": 1,
        "diff": -1,
    }]
    assert session.post_enemy_block is not None


def test_record_post_enemy_blocks_unexpected_mech_status_for_lightning_war(
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

    assert result["status"] == "INVESTIGATE_POST_ENEMY"
    assert result["blocking"] is True
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
    assert session.post_enemy_block is not None


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
