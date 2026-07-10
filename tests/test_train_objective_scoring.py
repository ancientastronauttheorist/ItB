from src.model.board import Board
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
