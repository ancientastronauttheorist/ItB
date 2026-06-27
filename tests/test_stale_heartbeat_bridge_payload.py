from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.loop import commands


def _phase_unknown_payload() -> dict:
    return {
        "phase": "unknown",
        "turn": 0,
        "in_active_mission": True,
        "mission_id": "Mission_DungBoss",
        "grid_power": 6,
        "tiles": [{"x": 0, "y": 0, "terrain": "ground"}],
        "units": [
            {
                "type": "DungBoss",
                "x": 3,
                "y": 4,
                "hp": 6,
                "max_hp": 6,
            }
        ],
        "spawning_tiles": [],
        "deployment_zone": [[6, 2], [6, 3]],
    }


def test_phase_unknown_bridge_payload_blocks_stale_save_fallback():
    payload = _phase_unknown_payload()
    enemy = SimpleNamespace(type="DungBoss", x=3, y=4, hp=6, max_hp=6)
    board = SimpleNamespace(
        grid_power=6,
        grid_power_max=7,
        enemies=lambda: [enemy],
    )
    session = SimpleNamespace(
        phase="between_missions",
        current_turn=None,
        save=Mock(),
    )

    with (
        patch.object(commands, "read_state", return_value=payload),
        patch.object(commands, "read_bridge_state", return_value=(board, payload)),
        patch.object(commands, "_record_turn_state") as record_turn_state,
    ):
        result = commands._read_stale_heartbeat_bridge_payload(session)

    assert result is not None
    assert result["status"] == "BRIDGE_HEARTBEAT_STALE"
    assert result["source"] == "bridge_stale_heartbeat"
    assert result["mission_id"] == "Mission_DungBoss"
    assert result["phase"] == "unknown"
    assert result["deployment_zone_count"] == 2
    assert result["enemies"] == [
        {"type": "DungBoss", "pos": "D5", "hp": "6/6"},
    ]
    assert session.phase == "unknown"
    assert session.current_turn == 0
    assert session.save.called
    assert record_turn_state.called


def test_phase_unknown_bridge_payload_requires_active_mission_shape():
    stale_save_like_payload = {
        "phase": "unknown",
        "turn": 0,
        "in_active_mission": False,
        "mission_id": "",
        "tiles": [],
        "units": [],
    }

    assert not commands._phase_unknown_bridge_payload_is_active(
        stale_save_like_payload
    )
