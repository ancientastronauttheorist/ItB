"""Phase 4 P4-1c — regression-board extraction & observable-change verification.

Two small side-effectful helpers on top of the pure P4-1a miner:

- ``extract_regression_board(candidate)`` copies
  ``recordings/<run_id>/m<NN>_turn_<NN>_board.json`` into
  ``tests/weapon_overrides/<weapon_id>_<hash8>.json`` in the
  format the P3-7 regression gate expects.

- ``verify_observable_change(board_path, override)`` runs
  ``itb_solver`` twice (stock vs patched) and returns a dict
  describing whether the override made the solver pick a
  different plan or produce a different score.

Why a separate module: the pattern miner (P4-1a) is intentionally
pure. Board extraction copies files; verification imports the Rust
solver. Keeping both out of ``pattern_miner.py`` lets callers
import it from build scripts without pulling in the solver wheel.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.research.pattern_miner import (
    DEFAULT_RECORDINGS_ROOT,
    MinedCandidate,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tests" / "weapon_overrides"


# ── extraction ──────────────────────────────────────────────────────────────


def extract_regression_board(
    candidate: MinedCandidate,
    *,
    recordings_root: Path | str | None = None,
    output_dir: Path | str | None = None,
    overwrite: bool = False,
) -> Path | None:
    """Write a regression fixture from ``candidate`` and return its path.

    Picks the first ``(run_id, mission, turn)`` in ``candidate.board_refs``
    whose recorded ``m<NN>_turn_<NN>_board.json`` exists, extracts the
    ``data.bridge_state`` dict, and writes it with the regression-gate
    schema:

    ```json
    {
      "weapon_id": "...",
      "case": "<hash8>",
      "bridge_state": { ... },
      "note": "auto-extracted from <run>/<mission>/<turn> by pattern miner"
    }
    ```

    Returns the output path on success; ``None`` when no board_ref has
    a recording on disk or the candidate's weapon_id isn't a real
    WEAPON_DEFS key (unknown_weapon entries are not fixture-extractable).

    ``overwrite=False`` leaves an existing file untouched and returns
    its path — lets P4-1d idempotently re-run the miner between PRs.
    """
    weapon_id = candidate.signature.weapon_id
    if not weapon_id or weapon_id.startswith("?:"):
        return None

    rr = Path(recordings_root) if recordings_root is not None else DEFAULT_RECORDINGS_ROOT
    od = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR

    case_tag = candidate.signature.hash8()
    out_path = od / f"{weapon_id}_{case_tag}.json"
    if out_path.exists() and not overwrite:
        return out_path

    # Walk board_refs in order (already sorted by the miner) until we
    # find one whose recording exists. Vision-only candidates have
    # board_refs tagged with (run_id, -1, -1) — no recording path to
    # resolve; those return None and the caller must author a fixture
    # by hand.
    for run_id, mission, turn in candidate.board_refs:
        if mission < 0 or turn < 0 or not run_id:
            continue
        src = rr / run_id / f"m{int(mission):02d}_turn_{int(turn):02d}_board.json"
        if not src.exists():
            continue
        bridge_state = _read_bridge_state(src)
        if bridge_state is None:
            continue

        od.mkdir(parents=True, exist_ok=True)
        fixture = {
            "weapon_id": weapon_id,
            "case": case_tag,
            "bridge_state": bridge_state,
            "note": (
                f"auto-extracted by pattern_miner P4-1c from "
                f"recordings/{run_id}/m{int(mission):02d}_turn_{int(turn):02d}_board.json "
                f"(signature={candidate.signature.source}/{candidate.signature.field}, "
                f"count={candidate.count})"
            ),
            "source_board_ref": {
                "run_id": run_id,
                "mission": int(mission),
                "turn": int(turn),
            },
            "signature_hash": candidate.signature.hash8(),
        }
        out_path.write_text(json.dumps(fixture, indent=2))
        return out_path

    return None


def _read_bridge_state(board_path: Path) -> dict | None:
    try:
        raw = json.loads(board_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    data = raw.get("data") if isinstance(raw, dict) else {}
    bs = data.get("bridge_state") if isinstance(data, dict) else None
    return bs if isinstance(bs, dict) else None


# ── verification ────────────────────────────────────────────────────────────


@dataclass
class VerificationResult:
    """Outcome of running the solver with/without an override.

    ``observable_change`` is True iff the override actually moved the
    solver's decision — either the plan sequence or the score. An
    override that leaves both identical would silently pass P3-7
    without this check, but the regression-board gate would reject
    it as useless; we surface that verdict here so P4-1d can skip
    publishing the draft PR instead of creating then failing CI.
    """

    observable_change: bool
    reason: str                    # human-readable description
    plan_changed: bool
    score_delta: float
    stock_score: float
    patched_score: float
    applied_overrides: list[dict]


def verify_observable_change(
    board_path: Path | str,
    override: dict,
    *,
    time_limit: float = 2.0,
) -> VerificationResult:
    """Solve twice and compare. Raises if ``itb_solver`` is missing.

    Mirrors the comparator in P3-7's
    ``test_override_produces_observable_change`` so the drafter's
    gate matches CI exactly — if the draft passes this, the PR will
    pass the same check in CI (barring nondeterminism, which the
    solver's ``time_limit`` can in rare cases introduce).
    """
    import itb_solver

    path = Path(board_path)
    data = json.loads(path.read_text())
    bridge_state = data.get("bridge_state")
    if not isinstance(bridge_state, dict):
        raise ValueError(f"{path}: bridge_state missing or not a dict")

    def _solve(override_entry: dict | None) -> dict:
        bd = json.loads(json.dumps(bridge_state))
        if override_entry is not None:
            bd["weapon_overrides"] = [override_entry]
        return json.loads(itb_solver.solve(json.dumps(bd), time_limit))

    stock = _solve(None)
    patched = _solve(override)

    stock_plan = _plan_tuple(stock)
    patched_plan = _plan_tuple(patched)
    plan_changed = stock_plan != patched_plan

    stock_score = float(stock.get("score") or 0.0)
    patched_score = float(patched.get("score") or 0.0)
    score_delta = patched_score - stock_score
    score_moved = abs(score_delta) > 1e-6

    applied = patched.get("applied_overrides") or []
    if not applied:
        return VerificationResult(
            observable_change=False,
            reason="patched solve reported no applied_overrides — "
                   "override schema didn't enter the solve",
            plan_changed=plan_changed,
            score_delta=score_delta,
            stock_score=stock_score,
            patched_score=patched_score,
            applied_overrides=[],
        )

    if plan_changed or score_moved:
        bits = []
        if plan_changed:
            bits.append("plan differs")
        if score_moved:
            bits.append(f"score Δ={score_delta:+.3f}")
        return VerificationResult(
            observable_change=True,
            reason=", ".join(bits),
            plan_changed=plan_changed,
            score_delta=score_delta,
            stock_score=stock_score,
            patched_score=patched_score,
            applied_overrides=applied,
        )

    return VerificationResult(
        observable_change=False,
        reason="override applied but neither plan nor score moved — "
               "fixture doesn't exercise the patched field",
        plan_changed=False,
        score_delta=0.0,
        stock_score=stock_score,
        patched_score=patched_score,
        applied_overrides=applied,
    )


def _plan_tuple(solution: dict) -> tuple:
    actions = solution.get("actions") or []
    return tuple(
        (
            a.get("mech_uid"),
            a.get("weapon_id"),
            tuple(a.get("move_to") or ()),
            tuple(a.get("target") or ()),
        )
        for a in actions
        if isinstance(a, dict)
    )
