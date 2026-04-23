"""End-to-end tests for `itb_solver.solve_top_k`.

These cover the pyo3 binding + Rust top-K path on real recorded boards.
The unit-level invariants of `BoundedTopK` (tiebreak on equal scores,
bounded capacity, empty case) are tested directly in Rust — see
`rust_solver/src/solver.rs::top_k_tests`. What this file protects:

  - `solve_top_k(..., 1)` returns the same best plan that `solve(...)`
    would — beam search at k=1 must not silently drift from the stable
    single-plan search.
  - `solve_top_k(..., 5)` returns up to 5 plans sorted by score desc.
  - k larger than the available plan set returns all of them without
    crashing or repeating.
  - Output is deterministic across repeated calls on the same board,
    same as `test_solver_determinism.py` asserts for `solve(...)`.
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
    import itb_solver
    _HAVE_WHEEL = True
except ImportError:
    _HAVE_WHEEL = False


def _augment_for_rust(bridge_data: dict) -> dict:
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
    """Find a player-turn board with at least one ACTIVE mech.

    `active=false` mechs (MID_ACTION or DONE) contribute no search branches —
    the solver short-circuits to an empty solution. Filtering on `active`
    matches the same readiness check `auto_turn` applies before dispatching.
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
        active_mechs = [
            u for u in bridge.get("units", [])
            if u.get("mech") and u.get("active")
        ]
        if not active_mechs:
            continue
        return p
    return None


def _solve_input(board_file: pathlib.Path) -> str:
    with open(board_file) as f:
        bridge_data = json.load(f)["data"]["bridge_state"]
    return json.dumps(_augment_for_rust(bridge_data), sort_keys=True)


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_solve_top_k_k1_matches_solve_best_action_set():
    """k=1 must return the same plan that `solve()` would return.

    `solve()` applies the two-stage clean-plan filter, which may prefer
    a slightly lower-raw-score plan that preserves buildings. `solve_top_k`
    deliberately does NOT apply that filter (beam search wants raw top-K).
    We assert that both produce a VALID plan (same mech UIDs covered) and
    that the k=1 score is >= solve()'s score (raw max must dominate the
    filtered pick by construction).
    """
    board_file = _find_player_turn_board()
    if board_file is None:
        pytest.skip("no player-turn board recordings found")
    fixed_json = _solve_input(board_file)

    single = json.loads(itb_solver.solve(fixed_json, 10.0))
    top_k = json.loads(itb_solver.solve_top_k(fixed_json, 10.0, 1))

    assert isinstance(top_k, list), "solve_top_k must return a JSON array"
    assert len(top_k) == 1, f"k=1 must return exactly 1 plan, got {len(top_k)}"

    top = top_k[0]
    # Raw top-K dominates or matches: the clean-filtered score cannot
    # exceed the raw max by definition.
    assert top["score"] >= single["score"] - 1e-9, (
        f"top-K raw score {top['score']} must be >= solve() filtered score "
        f"{single['score']} (the filter only swaps to a LOWER-scoring clean plan)"
    )

    # Same active mechs covered in both.
    assert {a["mech_uid"] for a in top["actions"]} == {
        a["mech_uid"] for a in single["actions"]
    }


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_solve_top_k_returns_sorted_desc():
    """k=5 returns <=5 plans sorted by score descending."""
    board_file = _find_player_turn_board()
    if board_file is None:
        pytest.skip("no player-turn board recordings found")
    fixed_json = _solve_input(board_file)

    top_k = json.loads(itb_solver.solve_top_k(fixed_json, 10.0, 5))
    assert isinstance(top_k, list)
    assert 1 <= len(top_k) <= 5

    scores = [plan["score"] for plan in top_k]
    assert scores == sorted(scores, reverse=True), (
        f"scores not descending: {scores}"
    )


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_solve_top_k_large_k_returns_all_available():
    """k >> plan count must return all plans (no crash, no repeats)."""
    board_file = _find_player_turn_board()
    if board_file is None:
        pytest.skip("no player-turn board recordings found")
    fixed_json = _solve_input(board_file)

    # Request absurdly many — should cap at actual plan count.
    top_k = json.loads(itb_solver.solve_top_k(fixed_json, 10.0, 10000))
    assert isinstance(top_k, list)
    assert len(top_k) >= 1

    # No exact duplicates (same action sequence + same score).
    seen = set()
    for plan in top_k:
        key = (plan["score"], tuple(
            (a["mech_uid"], tuple(a["move_to"]), a["weapon_id"], tuple(a["target"]))
            for a in plan["actions"]
        ))
        assert key not in seen, "duplicate plan in top-K output"
        seen.add(key)


@pytest.mark.skipif(not _HAVE_WHEEL, reason="itb_solver wheel not installed")
def test_solve_top_k_deterministic():
    """Repeated calls on the same input produce byte-identical output.

    Same guarantee as `test_rust_solve_is_byte_deterministic` but for the
    top-K path. Beam search at depth 2+ will compound any flake here.
    """
    board_file = _find_player_turn_board()
    if board_file is None:
        pytest.skip("no player-turn board recordings found")
    fixed_json = _solve_input(board_file)

    def _strip_volatile(raw: str) -> str:
        arr = json.loads(raw)
        for entry in arr:
            for key in ("search_stats", "stats"):
                s = entry.get(key)
                if isinstance(s, dict):
                    s.pop("elapsed_seconds", None)
                    s.pop("elapsed", None)
        return json.dumps(arr, sort_keys=True)

    first = _strip_volatile(itb_solver.solve_top_k(fixed_json, 5.0, 5))
    for _ in range(4):
        again = _strip_volatile(itb_solver.solve_top_k(fixed_json, 5.0, 5))
        assert again == first, "solve_top_k output diverged across runs"
