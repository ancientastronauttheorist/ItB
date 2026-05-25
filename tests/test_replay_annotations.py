from src.solver.solver import _replay_annotations_for_plan


def test_duplicate_sequential_move_to_annotation():
    annotations = _replay_annotations_for_plan([
        {"mech_uid": 1, "move_to": [5, 4], "target": [5, 2]},
        {"mech_uid": 0, "move_to": [5, 4], "target": [5, 2]},
    ])

    assert annotations == [{
        "kind": "duplicate_sequential_move_to",
        "action_index": 1,
        "previous_action_index": 0,
        "move_to": [5, 4],
        "mech_uid": 0,
        "previous_mech_uid": 1,
    }]


def test_non_sequential_duplicate_move_to_is_not_annotated():
    annotations = _replay_annotations_for_plan([
        {"mech_uid": 1, "move_to": [5, 4]},
        {"mech_uid": 2, "move_to": [6, 4]},
        {"mech_uid": 0, "move_to": [5, 4]},
    ])

    assert annotations == []
