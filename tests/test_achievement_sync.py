import json

from src.strategy.achievement_sync import (
    canonical_achievement_name,
    sync_achievement_details,
)


def test_canonical_achievement_name_normalizes_quotes_and_spaces():
    assert (
        canonical_achievement_name("  I\u2019m   getting too old for this... ")
        == "i'm getting too old for this..."
    )


def test_sync_achievement_details_updates_completed_flags(tmp_path):
    path = tmp_path / "achievements_detailed.json"
    path.write_text(json.dumps({
        "meta": {"total_achievements": 2},
        "achievements": {
            "rusting_hulks": [
                {"name": "Perfect Battle", "completed": False},
                {"name": "Stormy Weather", "completed": True},
            ],
            "global_victories": [
                {"name": "Complete Victory", "completed": False},
            ],
        },
    }))
    steam = [
        {"name": "Perfect Battle", "achieved": 1},
        {"name": "Stormy Weather", "achieved": 0},
        {"name": "Complete Victory", "achieved": 1},
    ]

    result = sync_achievement_details(
        steam,
        path=path,
        synced_at="2026-05-06T12:00:00",
    )

    updated = json.loads(path.read_text())
    assert result["matched"] == 3
    assert result["status_changed"] == 3
    assert result["local_completed"] == 2
    assert updated["meta"]["last_steam_sync"] == "2026-05-06T12:00:00"
    assert updated["achievements"]["rusting_hulks"][0]["completed"] is True
    assert updated["achievements"]["rusting_hulks"][1]["completed"] is False
    assert updated["achievements"]["global_victories"][0]["completed"] is True
