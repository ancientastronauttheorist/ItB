from src.model.board import Board
from src.model.pawn_stats import get_pawn_stats
from src.solver.evaluate import EvalWeights, evaluate_breakdown


def _train_board(train_type: str) -> Board:
    data = {
        "mission_id": "Mission_Train",
        "grid_power": 4,
        "grid_power_max": 7,
        "protect_objective_unit_types": ["Train"],
        "tiles": [],
        "units": [
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
        ],
    }
    return Board.from_bridge_data(data)


def test_python_breakdown_scores_train_once_and_penalizes_degradation():
    weights = EvalWeights()
    intact = evaluate_breakdown(
        _train_board("Train_Pawn"),
        spawn_points=[],
        weights=weights,
    )["mission_unit_objectives"]
    damaged = evaluate_breakdown(
        _train_board("Train_Damaged"),
        spawn_points=[],
        weights=weights,
    )["mission_unit_objectives"]

    assert intact["protect_alive"] == 1
    assert intact["protect_degraded"] == 0
    assert damaged["protect_alive"] == 1
    assert damaged["protect_degraded"] == 1
    assert damaged["score"] - intact["score"] == (
        weights.mission_protect_unit_degraded_penalty
    )


def test_supply_train_static_stats_match_lua():
    intact = get_pawn_stats("Train_Pawn")
    damaged = get_pawn_stats("Train_Damaged")
    armored = get_pawn_stats("Train_Armored")
    armored_damaged = get_pawn_stats("Train_Armored_Damaged")

    assert intact.move_speed == 0
    assert intact.massive
    assert not intact.pushable
    assert intact.ignore_fire
    assert intact.ignore_smoke

    assert damaged.move_speed == 0
    assert damaged.massive
    assert not damaged.pushable
    assert damaged.ignore_fire
    assert not damaged.ignore_smoke

    assert armored.move_speed == 0
    assert armored.massive
    assert armored.armor
    assert not armored.pushable
    assert armored.ignore_fire
    assert armored.ignore_smoke

    assert armored_damaged.move_speed == 0
    assert armored_damaged.massive
    assert armored_damaged.armor
    assert not armored_damaged.pushable
    assert armored_damaged.ignore_fire
    assert not armored_damaged.ignore_smoke
