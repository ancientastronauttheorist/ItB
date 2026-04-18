"""P3-7: regression-board gate for data/weapon_overrides.json.

Every committed override must be backed by a board fixture that
demonstrates the override changes solver output. The test enforces:

1. Every entry in ``data/weapon_overrides.json`` has at least one
   matching ``tests/weapon_overrides/<weapon_id>_<case>.json`` fixture.
2. Running ``itb_solver.solve`` on the fixture's ``bridge_state``
   produces a different solution (actions, score, or both) with only
   that override applied vs. without it. An override that has no
   observable effect is almost certainly a misconfiguration — this
   test catches it before it ships.

Empty ``data/weapon_overrides.json`` (or no file at all) = no
parametrised cases = the test collects zero items and is a no-op.
This lets P3-7 land before the first real override.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.solver.weapon_overrides import (
    load_base_overrides,
    DEFAULT_OVERRIDES_PATH,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BOARDS_DIR = REPO_ROOT / "tests" / "weapon_overrides"


def _load_overrides() -> list[dict]:
    try:
        return load_base_overrides(DEFAULT_OVERRIDES_PATH)
    except Exception:
        # Schema failure surfaces via test_load_* in test_weapon_overrides.py;
        # here we just report no cases so the regression gate doesn't mask
        # a schema error with a confusing ``no boards matched`` failure.
        return []


def _boards_for(weapon_id: str) -> list[Path]:
    if not BOARDS_DIR.exists():
        return []
    return sorted(BOARDS_DIR.glob(f"{weapon_id}_*.json"))


def _override_cases() -> list[tuple[dict, Path]]:
    out: list[tuple[dict, Path]] = []
    for override in _load_overrides():
        wid = override["weapon_id"]
        for board in _boards_for(wid):
            out.append((override, board))
    return out


def _solve(bridge_state: dict, override: dict | None) -> dict:
    import itb_solver

    bd = json.loads(json.dumps(bridge_state))  # deep copy via JSON
    if override is not None:
        bd["weapon_overrides"] = [override]
    out = json.loads(itb_solver.solve(json.dumps(bd), 2.0))
    return out


@pytest.mark.parametrize("override", _load_overrides(),
                         ids=lambda o: o.get("weapon_id", "?"))
def test_override_has_regression_board(override):
    """Every committed override must have at least one board fixture."""
    wid = override["weapon_id"]
    boards = _boards_for(wid)
    assert boards, (
        f"no regression board found for {wid}. "
        f"Add at least one file matching "
        f"tests/weapon_overrides/{wid}_<case>.json"
    )


@pytest.mark.parametrize("override,board_path", _override_cases(),
                         ids=lambda v: v.stem if isinstance(v, Path) else v.get("weapon_id", "?"))
def test_override_produces_observable_change(override, board_path):
    """Each regression board must show the override actually does something.

    The bar is intentionally low: *some* observable change in the
    solver output (actions, score, or applied_overrides tag). The
    board + note are what encode intent — the test just guards against
    overrides that compile-in silently but have zero effect on any real
    board.
    """
    pytest.importorskip("itb_solver")
    data = json.loads(board_path.read_text())
    bridge_state = data.get("bridge_state")
    assert isinstance(bridge_state, dict), (
        f"{board_path}: bridge_state missing or not a dict"
    )

    stock = _solve(bridge_state, override=None)
    patched = _solve(bridge_state, override=override)

    # applied_overrides differs by construction: stock has none, patched has one.
    assert stock.get("applied_overrides", []) == []
    assert patched.get("applied_overrides", []), (
        f"{board_path}: patched solve did not report applied_overrides — "
        f"override did not enter the solve at all"
    )

    # Actions or score must differ. If neither moves, the override is
    # purely cosmetic (or targets a weapon not actually fired on this
    # board — author a different fixture).
    stock_plan = [(a["mech_uid"], a["weapon_id"], tuple(a["move_to"]),
                   tuple(a["target"])) for a in stock.get("actions", [])]
    patched_plan = [(a["mech_uid"], a["weapon_id"], tuple(a["move_to"]),
                     tuple(a["target"])) for a in patched.get("actions", [])]

    score_moved = abs((patched.get("score") or 0) - (stock.get("score") or 0)) > 1e-6
    plan_changed = stock_plan != patched_plan
    assert score_moved or plan_changed, (
        f"{board_path}: override for {override['weapon_id']} produced no "
        f"change in plan or score. The fixture needs to place the weapon "
        f"in a situation where the patched field actually matters."
    )
