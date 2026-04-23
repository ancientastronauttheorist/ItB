"""Solver determinism regression — depth-5 beam prerequisite.

A depth-5 beam search over a nondeterministic solver compounds the
drift exponentially. This test runs the Rust solver N times on the
same bridge state with the same time budget and asserts the outputs
are byte-identical.

Hazards we guard against:
  - Unstable sort on equal-score actions (fixed at solver.rs:541 with
    a tiebreak on original index).
  - rayon par_iter that could observably reorder by thread scheduling
    (rayon.collect preserves input order — guarded by this test).
  - HashMap/HashSet iteration order (none exist in rust_solver/src).
  - Any time-deadline race that causes early return at different
    points — budget is set generously so the search should complete.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Optional

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    import itb_solver  # noqa: F401
    _HAVE_WHEEL = True
except ImportError:
    _HAVE_WHEEL = False


def _augment_for_rust(bridge_data: dict) -> dict:
    """Minimal augmentation mirroring what cmd_solve does — just enough
    for the Rust solver to accept the JSON. Copied here rather than
    importing cmd_solve to keep the test isolated from session state.
    """
    from src.model.pawn_stats import get_pawn_stats
    from src.model.board import _compute_pilot_value

    data = json.loads(json.dumps(bridge_data))
    for u in data.get("units", []):
        stats = get_pawn_stats(u.get("type", ""))
        u["ranged"] = stats.ranged
        if not stats.pushable:
            u["pushable"] = False
        for k in ("weapon_damage", "weapon_push", "hp", "max_hp"):
            if k in u and isinstance(u[k], int) and u[k] > 255:
                u[k] = 255
        if u.get("mech"):
            u["pilot_value"] = _compute_pilot_value(
                u.get("pilot_id", ""),
                u.get("pilot_skills", []),
                u.get("max_hp", 0),
                u.get("type", ""),
                u.get("pilot_level", 0),
            )
    return data


def _find_player_turn_board() -> Optional[pathlib.Path]:
    """Find any recorded board where bridge_state.phase == combat_player
    and at least one mech is present. Determinism applies regardless of
    the specific board, so take the first match.
    """
    recordings = REPO_ROOT / "recordings"
    for p in sorted(recordings.glob("*/m*_turn_*_board.json")):
        try:
            with open(p) as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        bridge = d.get("data", {}).get("bridge_state") or {}
        if bridge.get("phase") != "combat_player":
            continue
        if not any(u.get("mech") for u in bridge.get("units", [])):
            continue
        return p
    return None


def _strip_volatile(raw: str) -> str:
    """Strip fields that legitimately vary run-to-run (wall clock).
    Anything else that differs signals real nondeterminism.
    """
    d = json.loads(raw)
    for key in ("search_stats", "stats"):
        s = d.get(key)
        if isinstance(s, dict):
            s.pop("elapsed_seconds", None)
            s.pop("elapsed", None)
    return json.dumps(d, sort_keys=True)


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_rust_solve_is_byte_deterministic():
    """Same input → same output across N independent solve calls."""
    board_file = _find_player_turn_board()
    if board_file is None:
        pytest.skip("no player-turn board recordings found")

    with open(board_file) as f:
        bridge_data = json.load(f)["data"]["bridge_state"]

    augmented = _augment_for_rust(bridge_data)
    fixed_json = json.dumps(augmented, sort_keys=True)

    TIME_LIMIT = 10.0
    N_RUNS = 10

    outputs = [itb_solver.solve(fixed_json, TIME_LIMIT) for _ in range(N_RUNS)]
    first = _strip_volatile(outputs[0])
    for i, out in enumerate(outputs[1:], start=1):
        out_norm = _strip_volatile(out)
        assert out_norm == first, (
            f"Run {i} diverged from run 0 on {board_file.name}. "
            f"Nondeterminism will compound at depth 5 — chase the source "
            f"(HashMap order, unstable sort tie, shared RNG, deadline race) "
            f"before building beam."
        )


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_rust_solve_is_deterministic_across_several_boards():
    """Sanity: multiple boards to catch edge cases specific to board shape."""
    recordings = REPO_ROOT / "recordings"
    checked = 0
    for p in sorted(recordings.glob("*/m*_turn_*_board.json"))[:50]:
        with open(p) as f:
            d = json.load(f)
        bridge = d.get("data", {}).get("bridge_state") or {}
        if bridge.get("phase") != "combat_player":
            continue
        if not any(u.get("mech") for u in bridge.get("units", [])):
            continue

        augmented = _augment_for_rust(bridge)
        fixed_json = json.dumps(augmented, sort_keys=True)

        a = itb_solver.solve(fixed_json, 5.0)
        b = itb_solver.solve(fixed_json, 5.0)
        assert _strip_volatile(a) == _strip_volatile(b), (
            f"Nondeterministic output for {p.name}"
        )
        checked += 1
        if checked >= 5:
            break

    if checked == 0:
        pytest.skip("no suitable boards found in recordings/")
