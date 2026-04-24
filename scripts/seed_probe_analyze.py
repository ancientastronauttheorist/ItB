#!/usr/bin/env python3
"""
seed_probe_analyze.py — Attempt to identify which Lua seed drives Grid Defense
(15%) resist outcomes in Into the Breach.

Reads `recordings/<run_id>/resist_probe.jsonl` (one JSON object per line; fields
described below), groups entries by `turn`, and for each turn prints:

    * `turn`
    * `ai_seed`
    * `master_seed`
    * the first N `math.random(100)` rolls from `seed(ai_seed)`
    * the first N `math.random(100)` rolls from `seed(master_seed)`
    * indices where a roll ≤ 15 appears (a "resist hit" under the naive model)
    * `had_attacks` — whether any building attacks were telegraphed at that turn
    * a placeholder for `grid_damage_observed` if it can be inferred from
      consecutive probe entries (Δ grid_power across turn boundaries).

The analyzer does NOT auto-confirm or reject any hypothesis — it exposes the
raw number stream so a human can inspect the first few candidate offsets K.
See docs/seed_replay_hypotheses.md for the formal H1/H2/H3 statements and
what decisive evidence would look like.

CLI:
    python3 scripts/seed_probe_analyze.py [--run-id ID] [-n N]

Defaults:
    run-id : newest subdirectory under `recordings/` containing a
             `resist_probe.jsonl` file.
    n      : 15 rolls shown per seed.

Probe JSONL schema (input):
    { "run_id", "mission_id", "region", "mission_slot",
      "turn", "master_seed", "ai_seed",
      "grid_defense_pct", "grid_power", "grid_power_max",
      "telegraphed_building_attacks": [{...}],  // attacks queued THIS turn
      "timestamp" }
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Make `seed_replay` importable whether invoked as `python scripts/...` or
# `python -m scripts....`.
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import seed_replay  # noqa: E402


# ---- helpers ------------------------------------------------------------


def _resolve_run_id(run_id: str | None, recordings_root: Path) -> str:
    if run_id:
        return run_id
    # Newest directory that contains resist_probe.jsonl
    candidates = []
    for p in recordings_root.iterdir():
        if p.is_dir() and (p / "resist_probe.jsonl").is_file():
            candidates.append(p)
    if not candidates:
        raise SystemExit(
            f"no recordings/<run_id>/resist_probe.jsonl found under {recordings_root}"
        )
    candidates.sort(key=lambda p: p.stat().st_mtime)
    return candidates[-1].name


def _load_probe(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"warning: skipping bad line: {e}", file=sys.stderr)
    return rows


def _dedupe_by_turn(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the LAST (freshest) entry per `turn`.

    The probe log can include multiple snapshots per turn when the harness
    re-reads state during diagnosis.  The last one is the most authoritative
    for "what the board looked like going into the enemy phase".
    """
    by_turn: dict[int, dict[str, Any]] = {}
    for row in rows:
        t = row.get("turn")
        if t is None:
            continue
        by_turn[t] = row
    return [by_turn[k] for k in sorted(by_turn)]


def _grid_damage_deltas(rows: list[dict[str, Any]]) -> dict[int, int]:
    """Best-effort reconstruction of "damage observed at turn T".

    probe entries record `grid_power` BEFORE the enemy phase of turn T
    resolves, so damage-at-turn-T ≈ grid_power[T] - grid_power[T+1] (when
    non-negative; buildings don't regenerate mid-mission).  Returns a dict
    {turn -> observed_damage} for turns where the next entry exists.
    """
    out: dict[int, int] = {}
    by_turn = {r["turn"]: r for r in rows if "turn" in r}
    for t, row in by_turn.items():
        nxt = by_turn.get(t + 1)
        if nxt is None:
            continue
        gp = row.get("grid_power")
        gp_next = nxt.get("grid_power")
        if isinstance(gp, int) and isinstance(gp_next, int):
            delta = gp - gp_next
            if delta >= 0:
                out[t] = delta
    return out


def _resist_hits(rolls: list[int], threshold: int = 15) -> list[int]:
    return [i for i, v in enumerate(rolls) if v <= threshold]


# ---- main ---------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Inspect candidate Lua math.random(100) streams against "
                    "telegraphed building attacks in resist_probe.jsonl.")
    ap.add_argument("--run-id", default=None,
                    help="run id under recordings/ (default: newest with "
                         "resist_probe.jsonl)")
    ap.add_argument("--recordings-root", default=None,
                    help="override recordings/ root (default: auto-detect "
                         "relative to this script)")
    ap.add_argument("-n", "--rolls", type=int, default=15,
                    help="how many rolls to show per seed (default: 15)")
    ap.add_argument("--threshold", type=int, default=15,
                    help="resist threshold: roll <= threshold is a resist "
                         "(default: 15, matching 15%% Grid Defense)")
    args = ap.parse_args(argv)

    # Locate recordings root: walk up from this file until we find a 'recordings' dir.
    if args.recordings_root:
        root = Path(args.recordings_root).resolve()
    else:
        here = Path(__file__).resolve()
        root = None
        for anc in [here.parent, *here.parents]:
            cand = anc / "recordings"
            if cand.is_dir():
                root = cand
                break
        if root is None:
            print("error: could not locate a `recordings/` directory; "
                  "pass --recordings-root", file=sys.stderr)
            return 2

    run_id = _resolve_run_id(args.run_id, root)
    probe_path = root / run_id / "resist_probe.jsonl"
    if not probe_path.is_file():
        print(f"error: no probe file at {probe_path}", file=sys.stderr)
        return 2

    raw_rows = _load_probe(probe_path)
    rows = _dedupe_by_turn(raw_rows)
    damage_by_turn = _grid_damage_deltas(rows)

    print(f"# run_id: {run_id}")
    print(f"# probe : {probe_path}")
    print(f"# rows  : {len(raw_rows)} raw, {len(rows)} unique turns")
    print(f"# rolls : first {args.rolls} of math.random(100); "
          f"resist = roll <= {args.threshold}")
    print()

    # Header
    cols = ["turn", "ai_seed", "master_seed",
            "#attacks", "grid_before", "grid_Δ",
            "ai_rolls (first N)", "ai_resist_idx",
            "master_rolls (first N)", "master_resist_idx"]
    print("\t".join(cols))

    for row in rows:
        turn = row.get("turn")
        ai = row.get("ai_seed")
        ms = row.get("master_seed")
        atks = row.get("telegraphed_building_attacks") or []
        n_atks = len(atks)
        gp = row.get("grid_power")
        gd = damage_by_turn.get(turn, None)

        if ai is not None:
            ai_rolls = seed_replay.rolls(int(ai), args.rolls, upper=100)
            ai_hits = _resist_hits(ai_rolls, args.threshold)
        else:
            ai_rolls, ai_hits = [], []

        if ms is not None:
            ms_rolls = seed_replay.rolls(int(ms), args.rolls, upper=100)
            ms_hits = _resist_hits(ms_rolls, args.threshold)
        else:
            ms_rolls, ms_hits = [], []

        print("\t".join([
            str(turn),
            "-" if ai is None else str(ai),
            "-" if ms is None else str(ms),
            str(n_atks),
            "-" if gp is None else str(gp),
            "-" if gd is None else str(gd),
            ",".join(map(str, ai_rolls)),
            ",".join(map(str, ai_hits)),
            ",".join(map(str, ms_rolls)),
            ",".join(map(str, ms_hits)),
        ]))

    # Turn-by-turn attack detail (for alignment with resist hits).
    print()
    print("# per-turn attack detail")
    for row in rows:
        turn = row.get("turn")
        atks = row.get("telegraphed_building_attacks") or []
        if not atks:
            continue
        print(f"turn {turn}:")
        for i, a in enumerate(atks):
            print(f"  [{i}] {a.get('attacker_type')} {a.get('attacker_pos')} "
                  f"-> {a.get('target_pos')}  bldg_hp_before="
                  f"{a.get('target_building_hp_before')}")

    # Outcome breakdown from resist_observations. The probe infers
    # per-attack outcomes on the next-turn diff. We separate "resisted"
    # (true roll-resist candidate) from disruption outcomes (attacker
    # killed/pushed/webbed, target smoked), which are what inflated the
    # apparent resist rate in the 2026-04-24 data (72% vs 15% expected).
    print()
    print("# resist_observations outcome breakdown (across run)")
    outcomes: dict[str, int] = {}
    for row in raw_rows:
        for o in row.get("resist_observations") or []:
            k = o.get("inferred_outcome", "unknown")
            outcomes[k] = outcomes.get(k, 0) + 1
    if outcomes:
        for k in sorted(outcomes, key=outcomes.get, reverse=True):
            print(f"  {k}: {outcomes[k]}")
        true_resists = outcomes.get("resisted", 0)
        disrupted = sum(outcomes.get(k, 0) for k in
                        ("attacker_killed", "attacker_pushed",
                         "attacker_webbed", "target_smoked"))
        hit = outcomes.get("destroyed", 0) + outcomes.get("damaged", 0)
        total = true_resists + disrupted + hit
        if total:
            print(f"  # true-resist rate (excl. disrupted + hits):"
                  f" {true_resists}/{true_resists + hit}"
                  f" ({100*true_resists/max(1, true_resists+hit):.1f}%)"
                  f" — disruption: {disrupted}")
    else:
        print("  (no observations yet — probe entries lack resist_observations)")

    # Hint about how to USE this output.
    print()
    print("# Notes")
    print("# - Compare resist_idx against known-outcome turns: if on turn T")
    print("#   exactly M buildings took damage out of K attacks, then (K-M)")
    print("#   of the first K rolls at some offset in one of the streams")
    print("#   should be <= 15.  See docs/seed_replay_hypotheses.md.")
    print("# - `grid_Δ` is grid_power[T] - grid_power[T+1] inferred from the")
    print("#   probe log; 0 is ambiguous (could be 0 damage OR all resisted).")
    print("# - Only turns with ai_seed != null can test H1.")
    print("# - For correlation: use only `inferred_outcome == resisted`")
    print("#   observations. Disrupted attacks never rolled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
