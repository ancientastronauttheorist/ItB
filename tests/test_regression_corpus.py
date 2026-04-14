"""End-to-end regression test over failure_db.jsonl.

For each historical turn-level failure, re-solve with current solver +
weights and check for solver-decision bugs in the resulting plan.

Without ground truth we can only catch self-consistent bugs — plans the
solver proposes that contain internal contradictions (e.g. pushing a
friendly mech into our own building). The trigger detection produces
`self_damage_building` etc. on the re-simulation. If any such trigger
fires on a new solve that the original bug was supposed to have fixed,
it's a regression.

Sub-action desync triggers (~75% of failure_db) cannot be reproduced via
turn-level re-solve.
State-based triggers (grid_critical, mech_on_danger) describe the board
state, not solver decisions — excluded as low-signal.
Prediction-mismatch triggers (grid_power_drop_unexpected,
mech_damage_unexpected, building_lost_unexpected) require comparison
vs recorded actual, but the actual was produced by a DIFFERENT plan than
what the new solver proposes — so mismatches are expected and not bugs.
"""
import json
from pathlib import Path

import pytest

from src.loop.commands import _load_board_from_recording, _solve_with_rust
from src.solver.analysis import detect_triggers, load_failure_db
from src.solver.solver import replay_solution

REPO = Path(__file__).resolve().parent.parent
KNOWN_ISSUES_PATH = REPO / "tests" / "known_issues.json"
ACTIVE_WEIGHTS_PATH = REPO / "weights" / "active.json"

# Triggers that fire on self-consistent simulation (no deltas) and indicate
# solver-decision bugs. These reproduce reliably across re-solves because
# they depend on the SOLVER'S plan, not on cross-plan deltas.
SELF_CONSISTENT_TRIGGERS = {
    "self_damage_building",  # solver pushed friendly unit into own building
}

# Triggers we USE to filter the failure_db corpus (we look at entries where
# the original bug was one of these categories — whether or not the trigger
# itself refires on self-consistency).
CORPUS_FILTER_TRIGGERS = {
    "self_damage_building",
    "grid_power_drop_unexpected",
    "mech_damage_unexpected",
    "building_lost_unexpected",
}


def _load_known_issues() -> set:
    if not KNOWN_ISSUES_PATH.exists():
        return set()
    data = json.loads(KNOWN_ISSUES_PATH.read_text())
    out = set()
    for e in data.get("entries", []):
        scope = e.get("scope", "both")
        if scope not in ("python", "both"):
            continue
        out.add((e["run_id"], e["mission"], e["turn"], e["trigger"]))
    return out


def _dedup_failure_corpus() -> list:
    """Filter failure_db to relevant triggers, dedup by (run_id, mission, trigger),
    skip audit-tagged runs."""
    records = load_failure_db()
    seen, corpus = set(), []
    for r in records:
        if r.get("trigger") not in CORPUS_FILTER_TRIGGERS:
            continue
        if "audit" in r.get("context", {}).get("tags", []):
            continue
        key = (r.get("run_id"), r.get("mission"), r.get("trigger"))
        if key in seen:
            continue
        seen.add(key)
        corpus.append(r)
    return corpus


@pytest.mark.regression
def test_failure_corpus_not_regressed():
    assert ACTIVE_WEIGHTS_PATH.exists(), f"Missing weights: {ACTIVE_WEIGHTS_PATH}"
    weights = json.loads(ACTIVE_WEIGHTS_PATH.read_text())["weights"]

    known = _load_known_issues()
    corpus = _dedup_failure_corpus()

    unexpected = []
    still_fires_known = 0
    fixed = 0
    skipped_missing_file = 0
    empty_sol_count = 0

    for rec in corpus:
        replay_rel = rec.get("replay_file", "")
        if not replay_rel:
            continue
        bf = REPO / replay_rel
        if not bf.exists():
            skipped_missing_file += 1
            continue

        try:
            bridge_data, board, spawns, _env = _load_board_from_recording(bf)
        except (ValueError, json.JSONDecodeError) as e:
            unexpected.append(f"{bf.name}: load failed: {e}")
            continue

        sol = _solve_with_rust(bridge_data, time_limit=2.0, weights=weights)

        # Empty solution on active board = regression
        if not sol.actions:
            empty_sol_count += 1
            active_mechs = any(
                u.get("team") == 0 and u.get("active")
                for u in bridge_data.get("units", [])
            )
            has_enemies = bool(bridge_data.get("enemies")) or any(
                u.get("team") == 1 for u in bridge_data.get("units", [])
            )
            key = (rec["run_id"], rec["mission"], rec["turn"], "empty_solution")
            if active_mechs and has_enemies and key not in known:
                unexpected.append(
                    f"{bf.name}: empty solution on active board")
            # Even if empty, check if the original trigger was an "empty" trigger;
            # usually these cases are not testable via detect_triggers anyway.
            continue

        # Re-simulate to get the enriched action results + NEW predicted outcome
        try:
            enriched = replay_solution(
                board.copy(),
                sol,
                spawns,
                current_turn=bridge_data.get("turn", 0),
                total_turns=bridge_data.get("total_turns", 5),
            )
        except Exception as e:
            unexpected.append(f"{bf.name}: replay_solution failed: {e}")
            continue

        new_predicted = enriched.get("predicted_outcome", {})
        solve_data = {
            "actions": [{"mech_type": a.mech_type} for a in sol.actions],
            "action_results": enriched.get("action_results", []),
            "search_stats": {
                "timed_out": sol.timed_out,
                "elapsed_seconds": getattr(sol, "elapsed_seconds", 0.0),
            },
        }

        # Self-consistency check: does the new plan contain internal
        # contradictions the solver should have avoided? Pass actual=predicted
        # so mismatch triggers don't fire — we only want solver-decision bugs.
        empty_deltas = {
            "buildings_alive_diff": 0,
            "grid_power_diff": 0,
            "mech_hp_diff": [],
        }
        new_triggers = {
            t["trigger"]
            for t in detect_triggers(
                actual=new_predicted,
                predicted=new_predicted,
                deltas=empty_deltas,
                solve_data=solve_data,
                board=board,
            )
        }

        # Only flag triggers that reliably indicate solver-decision bugs
        solver_bug_triggers = new_triggers & SELF_CONSISTENT_TRIGGERS
        if not solver_bug_triggers:
            fixed += 1
            continue

        # At least one solver-bug trigger fired on this plan
        for trig in solver_bug_triggers:
            key = (rec["run_id"], rec["mission"], rec["turn"], trig)
            if key in known:
                still_fires_known += 1
            else:
                unexpected.append(
                    f"{rec['run_id']} m{rec['mission']:02d} t{rec['turn']:02d}: "
                    f"{trig} fires on new plan"
                )

    print(
        f"\nCorpus: {len(corpus)}  fixed: {fixed}  known: {still_fires_known}  "
        f"unexpected: {len(unexpected)}  skipped_missing: {skipped_missing_file}  "
        f"empty_solutions: {empty_sol_count}"
    )

    assert not unexpected, (
        f"Unexpected regressions ({len(unexpected)}) — add to "
        f"tests/known_issues.json if acceptable:\n  "
        + "\n  ".join(unexpected[:20])
    )
