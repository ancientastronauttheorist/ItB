from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.observatory.callback_hook_plan import (
    CallbackHookPlanError,
    build_callback_hook_plan,
    validate_callback_hook_plan,
)


ROOT = Path(__file__).resolve().parents[1]
BINDINGS = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_"
    "20260822T021034Z_callback_bindings.json"
)
JOIN = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_"
    "20260821T201929Z_callback_join.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("kind", "installed_count"),
    [
        ("get_target_area", 11),
        ("enemy_target_score", 15),
        ("get_skill_effect", 38),
        ("score_positioning", 1),
    ],
)
def test_real_build_callback_plan_covers_exact_slots(kind, installed_count):
    plan = build_callback_hook_plan(
        _load(BINDINGS), _load(JOIN), installed_kind=kind
    )

    assert len(plan) == 69
    assert sum(entry["status"] == "installed" for entry in plan) == installed_count
    assert {
        entry["event_kind"] for entry in plan if entry["status"] == "installed"
    } == {kind}
    callback_entries = [
        entry for entry in plan if entry["hook_id"].startswith("callback.slot-")
    ]
    assert len(callback_entries) == 65
    assert plan == sorted(plan, key=lambda item: (item["event_kind"], item["target"]))
    assert validate_callback_hook_plan(
        plan, _load(BINDINGS), _load(JOIN), installed_kind=kind
    ) == plan


def test_plan_rejects_join_or_slot_drift():
    bindings = _load(BINDINGS)
    join = _load(JOIN)
    drifted = deepcopy(join)
    drifted["function_joins"][0]["source_sha256"] = "0" * 64
    plan = build_callback_hook_plan(
        bindings, join, installed_kind="get_target_area"
    )
    with pytest.raises(CallbackHookPlanError, match="exact source join"):
        build_callback_hook_plan(
            bindings, drifted, installed_kind="get_target_area"
        )

    changed_plan = deepcopy(plan)
    changed_plan[0]["target"] = "disabled.changed"
    with pytest.raises(CallbackHookPlanError, match="does not exactly match"):
        validate_callback_hook_plan(
            changed_plan,
            bindings,
            join,
            installed_kind="get_target_area",
        )


def test_plan_rejects_non_callback_family():
    with pytest.raises(CallbackHookPlanError, match="not a callback family"):
        build_callback_hook_plan(
            _load(BINDINGS), _load(JOIN), installed_kind="enemy_candidate"
        )
