from src.loop.commands import _bridge_is_stale_post_mission


def test_stale_combat_bridge_ignored_after_save_leaves_mission():
    bridge = {"phase": "combat_player", "turn": 4}

    assert _bridge_is_stale_post_mission("between_missions", bridge)


def test_mission_ending_save_overrides_stale_enemy_bridge():
    bridge = {"phase": "combat_enemy", "turn": 2}

    assert _bridge_is_stale_post_mission("mission_ending", bridge)


def test_combat_save_keeps_bridge_authoritative():
    bridge = {"phase": "combat_player", "turn": 4}

    assert not _bridge_is_stale_post_mission("combat_player", bridge)


def test_turn_zero_bridge_not_treated_as_stale_deployment():
    bridge = {"phase": "combat_player", "turn": 0}

    assert not _bridge_is_stale_post_mission("between_missions", bridge)
