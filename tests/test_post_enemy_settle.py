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
