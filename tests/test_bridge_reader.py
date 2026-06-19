from src.bridge.reader import _is_infinite_spawn_mission


def test_missing_metadata_ae_boss_mission_is_infinite_spawn():
    assert _is_infinite_spawn_mission("Mission_BlobberBoss") is True


def test_metadata_boss_mission_is_infinite_spawn():
    assert _is_infinite_spawn_mission("Mission_BeetleBoss") is True


def test_non_boss_fixed_roster_mission_is_not_infinite_spawn():
    assert _is_infinite_spawn_mission("Mission_Battle") is False
