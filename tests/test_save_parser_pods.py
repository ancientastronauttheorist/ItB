from src.capture.save_parser import Point, extract_mission_state


def _mission_with_pod_value(value):
    return extract_mission_state(
        {"sMission": "Mission_Test"},
        {"map": [{"loc": Point(2, 3), "terrain": 0, "pod": value}]},
    )


def test_numeric_one_is_live_pod():
    mission = _mission_with_pod_value(1)

    assert mission.get_tile(2, 3).has_pod is True


def test_numeric_three_is_recovered_pod_not_live_board_pod():
    mission = _mission_with_pod_value(3)

    assert mission.get_tile(2, 3).has_pod is False


def test_bool_true_still_means_live_pod_for_legacy_inputs():
    mission = _mission_with_pod_value(True)

    assert mission.get_tile(2, 3).has_pod is True
