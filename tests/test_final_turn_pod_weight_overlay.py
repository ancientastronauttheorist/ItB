from src.loop import commands


def _bridge(**overrides):
    data = {
        "turn": 4,
        "total_turns": 4,
        "victory_turns": 1,
        "remaining_spawns": 1,
        "spawning_tiles": [],
        "tiles": [{"x": 4, "y": 2, "has_pod": True}],
    }
    data.update(overrides)
    return data


def test_final_turn_live_pod_gets_pickup_frontier_bonus():
    weights, applied = commands._final_turn_pod_collection_weight_overlay(
        {"pod_uncollected": -100.0},
        _bridge(),
    )

    assert weights["pod_collected"] == 1_000_000.0
    assert weights["pod_uncollected"] == -100.0
    assert applied == ["final_turn_pod_collection"]


def test_nonfinal_or_already_recovered_pod_does_not_change_weights():
    base = {"pod_collected": 25.0}

    nonfinal, nonfinal_applied = (
        commands._final_turn_pod_collection_weight_overlay(
            base,
            _bridge(victory_turns=2, turn=3),
        )
    )
    recovered, recovered_applied = (
        commands._final_turn_pod_collection_weight_overlay(
            base,
            _bridge(tiles=[{"x": 4, "y": 2, "has_pod": False}]),
        )
    )

    assert nonfinal is base
    assert nonfinal_applied == []
    assert recovered is base
    assert recovered_applied == []


def test_visible_spawn_marker_defers_final_turn_pickup_overlay():
    base = {"pod_collected": 0.0}

    weights, applied = commands._final_turn_pod_collection_weight_overlay(
        base,
        _bridge(spawning_tiles=[[7, 7]]),
    )

    assert weights is base
    assert applied == []


def test_destroy_time_pods_policy_keeps_pickup_penalty():
    base = {"pod_collected": -2_000_000.0}

    weights, applied = commands._final_turn_pod_collection_weight_overlay(
        base,
        _bridge(),
        ["destroy_time_pods"],
        destroy_time_pods_active=True,
    )

    assert weights is base
    assert weights["pod_collected"] == -2_000_000.0
    assert applied == ["destroy_time_pods"]


def test_turn_limit_fallback_applies_without_victory_counter():
    weights, applied = commands._final_turn_pod_collection_weight_overlay(
        {},
        _bridge(victory_turns=None),
    )

    assert weights["pod_collected"] == 1_000_000.0
    assert applied == ["final_turn_pod_collection"]
