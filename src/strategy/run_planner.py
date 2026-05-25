"""Run-level squad selection for achievement hunting.

The live loop used Balanced Roll while Solver 2.0 was being hardened because
randomized squads are excellent simulator stress tests. Achievement hunting has
a different goal: most remaining achievements are locked to named squads, so
the default should pick an actual unfinished squad unless the run is explicitly
for solver evaluation or random-squad achievements.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ACHIEVEMENTS_PATH = ROOT / "data" / "achievements_detailed.json"
SQUADS_PATH = ROOT / "data" / "squads.json"

BALANCED_ROLL = "Balanced Roll"
CUSTOM_SQUAD = "Custom Squad"

AUTO_SQUAD_ALIASES = {"", "auto", "achievement", "achievement hunt"}
BALANCED_ROLL_ALIASES = {
    "balanced",
    "balanced roll",
    "random",
    "random squad",
}
CUSTOM_SQUAD_ALIASES = {"custom", "custom squad"}

SOLVER_EVAL_TAGS = {"solver_eval", "normal_eval", "eval", "audit"}
ACHIEVEMENT_TAGS = {"achievement", "achievement_hunt", "hunt"}

# High-yield / lower-risk unfinished squads first. Random and Custom are
# deliberately after named squads; they need special setup and do not advance
# most squad-locked achievements.
ACHIEVEMENT_HUNT_PRIORITY = [
    "rusting_hulks",
    "zenith_guard",
    "rift_walkers",
    "flame_behemoths",
    "frozen_titans",
    "hazardous_mechs",
    "bombermechs",
    "mist_eaters",
    "heat_sinkers",
    "cataclysm",
    "arachnophiles",
    "blitzkrieg",
    "random_squad",
    "custom_squad",
]


@dataclass(frozen=True)
class RunSetupRecommendation:
    """Resolved setup intent for a new run."""

    squad: str
    squad_key: str
    mode: str
    reason: str
    requested_achievements: list[str] = field(default_factory=list)
    remaining_achievements: list[str] = field(default_factory=list)
    ui_setup: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "squad": self.squad,
            "squad_key": self.squad_key,
            "mode": self.mode,
            "reason": self.reason,
            "requested_achievements": self.requested_achievements,
            "remaining_achievements": self.remaining_achievements,
            "ui_setup": self.ui_setup,
            "warnings": self.warnings,
        }


def _norm(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_")


def _human_norm(value: str | None) -> str:
    return _norm(value).replace("_", " ")


def _load_squad_names(path: Path = SQUADS_PATH) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        payload = {}
    out: dict[str, str] = {}
    for entry in payload.get("squads", []):
        key = str(entry.get("id", "")).strip()
        name = str(entry.get("name", "")).strip()
        if key and name:
            out[key] = name
    out["random_squad"] = BALANCED_ROLL
    out["custom_squad"] = CUSTOM_SQUAD
    return out


def _load_achievement_groups(path: Path = ACHIEVEMENTS_PATH) -> dict[str, list[dict]]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    groups = payload.get("achievements", {})
    return groups if isinstance(groups, dict) else {}


def _achievement_index(groups: dict[str, list[dict]]) -> dict[str, tuple[str, dict]]:
    index: dict[str, tuple[str, dict]] = {}
    for group_key, achievements in groups.items():
        if not isinstance(achievements, list):
            continue
        for achievement in achievements:
            name = str(achievement.get("name", "")).strip()
            if name:
                index[_human_norm(name)] = (group_key, achievement)
    return index


def _is_global_group(group_key: str) -> bool:
    return group_key.startswith("global_")


def _canonical_explicit_squad(
    squad: str | None,
    squad_names: dict[str, str],
) -> tuple[str, str] | None:
    raw = _human_norm(squad)
    if raw in AUTO_SQUAD_ALIASES:
        return None
    if raw in BALANCED_ROLL_ALIASES:
        return ("random_squad", BALANCED_ROLL)
    if raw in CUSTOM_SQUAD_ALIASES:
        return ("custom_squad", CUSTOM_SQUAD)

    squashed = raw.replace(" ", "_")
    if squashed in squad_names:
        return (squashed, squad_names[squashed])
    for key, name in squad_names.items():
        if raw == _human_norm(name):
            return (key, name)
    # Preserve unknown explicit names so older call sites can still label a
    # session even before we have UI automation for that squad.
    if squad and squad.strip():
        return (_norm(squad), squad.strip())
    return None


def infer_run_mode(
    *,
    mode: str | None = None,
    tags: list[str] | None = None,
    achievements: list[str] | None = None,
) -> str:
    """Return ``achievement_hunt``, ``solver_eval``, ``random_squad``, or ``custom``."""
    mode_key = _norm(mode)
    if mode_key in {"solver_eval", "eval", "normal_eval", "audit"}:
        return "solver_eval"
    if mode_key in {"random", "random_squad", "balanced_roll"}:
        return "random_squad"
    if mode_key in {"custom", "custom_squad"}:
        return "custom"
    if mode_key in {"achievement", "achievement_hunt", "hunt"}:
        return "achievement_hunt"

    tag_keys = {_norm(t) for t in (tags or [])}
    if tag_keys & SOLVER_EVAL_TAGS:
        return "solver_eval"
    if tag_keys & {"random_squad", "balanced_roll"}:
        return "random_squad"
    if tag_keys & {"custom_squad"}:
        return "custom"
    if achievements:
        return "achievement_hunt"
    if tag_keys & ACHIEVEMENT_TAGS:
        return "achievement_hunt"
    return "achievement_hunt"


def _remaining_for_group(groups: dict[str, list[dict]], group_key: str) -> list[str]:
    return [
        str(a.get("name", ""))
        for a in groups.get(group_key, [])
        if not a.get("completed") and a.get("name")
    ]


def _setup_text(squad_key: str, squad_name: str) -> str:
    if squad_key == "random_squad":
        return "Click Balanced Roll, then Start."
    if squad_key == "custom_squad":
        return "Open Custom Squad, choose the required mech composition, then Start."
    return f"Select the {squad_name} squad card, then Start."


def _pick_next_unfinished_squad(
    groups: dict[str, list[dict]],
    squad_names: dict[str, str],
) -> tuple[str, str, list[str]]:
    for key in ACHIEVEMENT_HUNT_PRIORITY:
        remaining = _remaining_for_group(groups, key)
        if remaining and key in squad_names:
            return key, squad_names[key], remaining
    return "random_squad", BALANCED_ROLL, _remaining_for_group(groups, "random_squad")


def recommend_squad_for_run(
    squad: str | None = None,
    achievements: list[str] | None = None,
    *,
    tags: list[str] | None = None,
    mode: str | None = None,
    achievement_path: Path = ACHIEVEMENTS_PATH,
    squads_path: Path = SQUADS_PATH,
) -> RunSetupRecommendation:
    """Resolve the intended squad for a new run.

    Explicit named squads always win. Otherwise achievement-hunt mode picks a
    named squad with unfinished targets, while solver-eval/random-squad modes
    keep using Balanced Roll.
    """
    achievements = [a for a in (achievements or []) if a]
    squad_names = _load_squad_names(squads_path)
    explicit = _canonical_explicit_squad(squad, squad_names)
    resolved_mode = infer_run_mode(
        mode=mode,
        tags=tags,
        achievements=achievements,
    )

    groups = _load_achievement_groups(achievement_path)
    index = _achievement_index(groups)

    if explicit is not None:
        key, name = explicit
        return RunSetupRecommendation(
            squad=name,
            squad_key=key,
            mode=resolved_mode,
            reason="explicit squad requested",
            requested_achievements=achievements,
            remaining_achievements=_remaining_for_group(groups, key),
            ui_setup=_setup_text(key, name),
        )

    if resolved_mode == "solver_eval":
        return RunSetupRecommendation(
            squad=BALANCED_ROLL,
            squad_key="random_squad",
            mode=resolved_mode,
            reason="solver-eval/audit runs keep using Balanced Roll for broad coverage",
            requested_achievements=achievements,
            remaining_achievements=_remaining_for_group(groups, "random_squad"),
            ui_setup=_setup_text("random_squad", BALANCED_ROLL),
        )

    if resolved_mode == "random_squad":
        return RunSetupRecommendation(
            squad=BALANCED_ROLL,
            squad_key="random_squad",
            mode=resolved_mode,
            reason="random-squad target requires a random squad roll",
            requested_achievements=achievements,
            remaining_achievements=_remaining_for_group(groups, "random_squad"),
            ui_setup=_setup_text("random_squad", BALANCED_ROLL),
        )

    if resolved_mode == "custom":
        return RunSetupRecommendation(
            squad=CUSTOM_SQUAD,
            squad_key="custom_squad",
            mode=resolved_mode,
            reason="custom-squad target requires hand-picked mech composition",
            requested_achievements=achievements,
            remaining_achievements=_remaining_for_group(groups, "custom_squad"),
            ui_setup=_setup_text("custom_squad", CUSTOM_SQUAD),
            warnings=["Custom composition is not fully UI-automated yet."],
        )

    for target in achievements:
        hit = index.get(_human_norm(target))
        if hit is None:
            continue
        group_key, achievement = hit
        if group_key == "random_squad":
            return RunSetupRecommendation(
                squad=BALANCED_ROLL,
                squad_key=group_key,
                mode="random_squad",
                reason=f"target '{achievement['name']}' is a random-squad achievement",
                requested_achievements=achievements,
                remaining_achievements=_remaining_for_group(groups, group_key),
                ui_setup=_setup_text(group_key, BALANCED_ROLL),
            )
        if group_key == "custom_squad":
            return RunSetupRecommendation(
                squad=CUSTOM_SQUAD,
                squad_key=group_key,
                mode="custom",
                reason=f"target '{achievement['name']}' is a custom-squad achievement",
                requested_achievements=achievements,
                remaining_achievements=_remaining_for_group(groups, group_key),
                ui_setup=_setup_text(group_key, CUSTOM_SQUAD),
                warnings=["Custom composition is not fully UI-automated yet."],
            )
        if not _is_global_group(group_key) and group_key in squad_names:
            squad_name = squad_names[group_key]
            return RunSetupRecommendation(
                squad=squad_name,
                squad_key=group_key,
                mode=resolved_mode,
                reason=f"target '{achievement['name']}' requires {squad_name}",
                requested_achievements=achievements,
                remaining_achievements=_remaining_for_group(groups, group_key),
                ui_setup=_setup_text(group_key, squad_name),
            )

    key, name, remaining = _pick_next_unfinished_squad(groups, squad_names)
    return RunSetupRecommendation(
        squad=name,
        squad_key=key,
        mode=resolved_mode,
        reason="next high-priority squad with unfinished achievements",
        requested_achievements=achievements,
        remaining_achievements=remaining,
        ui_setup=_setup_text(key, name),
    )
