from src.strategy.run_planner import (
    BALANCED_ROLL,
    CUSTOM_SQUAD,
    recommend_squad_for_run,
)


def _fixtures(tmp_path):
    squads_path = tmp_path / "squads.json"
    achievements_path = tmp_path / "achievements.json"
    squads_path.write_text(
        """
{
  "squads": [
    {"id": "rusting_hulks", "name": "Rusting Hulks"},
    {"id": "zenith_guard", "name": "Zenith Guard"},
    {"id": "blitzkrieg", "name": "Blitzkrieg"}
  ]
}
""".strip()
    )
    achievements_path.write_text(
        """
{
  "achievements": {
    "rusting_hulks": [
      {"name": "Perfect Battle", "completed": false},
      {"name": "Stormy Weather", "completed": false}
    ],
    "zenith_guard": [
      {"name": "Shield Mastery", "completed": false}
    ],
    "blitzkrieg": [
      {"name": "Chain Attack", "completed": false}
    ],
    "random_squad": [
      {"name": "Lucky Start", "completed": false}
    ],
    "custom_squad": [
      {"name": "Flight Specialist", "completed": false}
    ],
    "global_victories": [
      {"name": "Complete Victory", "completed": false}
    ]
  }
}
""".strip()
    )
    return achievements_path, squads_path


def _recommend(tmp_path, *args, **kwargs):
    achievement_path, squads_path = _fixtures(tmp_path)
    return recommend_squad_for_run(
        *args,
        achievement_path=achievement_path,
        squads_path=squads_path,
        **kwargs,
    )


def test_default_achievement_hunt_picks_named_squad(tmp_path):
    rec = _recommend(tmp_path, tags=["achievement"])

    assert rec.mode == "achievement_hunt"
    assert rec.squad == "Rusting Hulks"
    assert rec.squad != BALANCED_ROLL
    assert "Perfect Battle" in rec.remaining_achievements


def test_solver_eval_keeps_balanced_roll(tmp_path):
    rec = _recommend(tmp_path, mode="solver_eval")

    assert rec.squad == BALANCED_ROLL
    assert rec.squad_key == "random_squad"


def test_named_achievement_targets_required_squad(tmp_path):
    rec = _recommend(tmp_path, achievements=["Shield Mastery"])

    assert rec.squad == "Zenith Guard"
    assert rec.squad_key == "zenith_guard"
    assert "Shield Mastery" in rec.remaining_achievements


def test_random_achievement_uses_balanced_roll(tmp_path):
    rec = _recommend(tmp_path, achievements=["Lucky Start"])

    assert rec.squad == BALANCED_ROLL
    assert rec.mode == "random_squad"


def test_custom_achievement_reports_custom_setup(tmp_path):
    rec = _recommend(tmp_path, achievements=["Flight Specialist"])

    assert rec.squad == CUSTOM_SQUAD
    assert rec.mode == "custom"
    assert rec.warnings


def test_explicit_squad_overrides_auto_strategy(tmp_path):
    rec = _recommend(tmp_path, "Blitzkrieg", achievements=["Shield Mastery"])

    assert rec.squad == "Blitzkrieg"
    assert rec.reason == "explicit squad requested"
