#!/usr/bin/env python3
"""
seed_replay_experiment.py — Offline post-hoc validation: can we reproduce
recorded ITB spawn outcomes from the captured master_seed + ai_seed?

This is a STANDALONE forensic tool. It reads existing recordings, NEVER
modifies them, and never integrates with the live game loop. Its only
purpose is to test the hypothesis that we can replay enemy-phase RNG
deterministically given the seeds we already capture in
`bridge_state.mission_seeds[<region>].ai_seed`.

What it does
------------
For one or more (run_id, mission_index, turn) triples on the command line:

  1. Load the pre-spawn board (turn N's `m<NN>_turn_<NN>_board.json`) and the
     post-spawn board (turn N+1's `m<NN>_turn_<NN+1>_board.json`).
  2. Diff the two unit lists to compute the "ground-truth spawn outcome":
     which uids are new, what types, where they ended up.
  3. Read `master_seed` and the active region's `ai_seed` from the pre-spawn
     bridge_state.
  4. Using `seed_replay.py`'s pure-Python Park-Miller (macOS libc / Lua 5.1
     `math.random` reproducer), generate the first ~200 raw rolls from each
     candidate seed.
  5. Try several "consume-offset" hypotheses for where in the stream the
     spawner picks (a) the weak/strong branch and (b) a pawn type.
  6. Print a side-by-side report: ground truth vs each candidate prediction.

Why this matters
----------------
If we can reliably predict spawn types/order from `ai_seed` alone, we unlock
offline corpus expansion: bulk-replay every recorded turn through the solver
against ground-truth post-enemy boards instead of having to capture every
intermediate state. If we cannot — and the C++ engine consumes RNG in an
opaque order — that's also a useful answer: it tells us our offline tools
will need a different signal (e.g., observing live RNG outputs through the
mod bridge, not seed reconstruction).

What this is NOT
----------------
- NOT used in any live decision loop. The output is a printed report.
- NOT a cheating tool. It only consumes recordings already on disk and the
  read-only Steam game source. No future-state knowledge during play.
- NOT a Lua interpreter port. We rely on the existing pure-Python
  `seed_replay.py` (Park-Miller LCG) and report honestly when prediction
  fails — likely because `random_int` lives in `itb_test.dylib` and we
  can't see the C++ call sequence.

Usage
-----
    python3 scripts/seed_replay_experiment.py
        # default: runs the two pre-canned cases below

    python3 scripts/seed_replay_experiment.py \\
        --case 20260425_005049_742:m02:2 \\
        --case 20260425_185532_218:m05:1

Pre-canned cases (chosen by inspection — see docs/seed_replay_experiment.md):
    20260425_005049_742:m02:2   (Mission_HornetBoss, 0 enemies → 4)
    20260425_185532_218:m05:1   (Mission_Train, telegraphed 2 spawns)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import seed_replay  # noqa: E402

REPO_ROOT = _THIS_DIR.parent
RECORDINGS = REPO_ROOT / "recordings"


# ---- helpers ------------------------------------------------------------


def visual(p: tuple[int, int]) -> str:
    """Convert bridge (x, y) → visual A1–H8 (Row=8-x, Col=chr(72-y))."""
    return f"{chr(72 - p[1])}{8 - p[0]}"


def load_board(run_id: str, mission_idx: str, turn: int) -> dict[str, Any]:
    """Load `recordings/<run>/m<mm>_turn_<tt>_board.json` and return its
    bridge_state. Returns None if the file is missing or malformed."""
    path = RECORDINGS / run_id / f"{mission_idx}_turn_{turn:02d}_board.json"
    if not path.exists():
        return None
    with open(path) as f:
        d = json.load(f)
    bs = d.get("data", {}).get("bridge_state")
    if not bs:
        return None
    return bs


def diff_units(pre: list[dict], post: list[dict]) -> dict[str, list]:
    """Return new/removed/moved/changed-type uids between pre and post."""
    pre_by_uid = {u["uid"]: u for u in pre if u.get("team") == 6}
    post_by_uid = {u["uid"]: u for u in post if u.get("team") == 6}
    new_uids = sorted(set(post_by_uid) - set(pre_by_uid))
    removed_uids = sorted(set(pre_by_uid) - set(post_by_uid))
    return {
        "new": [post_by_uid[u] for u in new_uids],
        "removed": [pre_by_uid[u] for u in removed_uids],
    }


def active_region_seed(bridge_state: dict) -> tuple[str | None, int | None]:
    """Return (region_key, ai_seed) for the region with iState == 0."""
    ms = bridge_state.get("mission_seeds") or {}
    for region, info in ms.items():
        if info.get("state") == 0:
            return region, info.get("ai_seed")
    return None, None


# ---- experiment cases ---------------------------------------------------


# Pre-canned cases identified from the two specified runs. Each tuple is
# (run_id, mission_idx, pre_turn). The "pre" turn is the board snapshot
# whose subsequent enemy phase will materialize the spawns we want to predict.
DEFAULT_CASES = [
    # Run 1, mission 2 (Mission_HornetBoss). Turn 2 board has 0 enemies and
    # 3 spawning_tiles; turn 3 board shows 4 new enemy uids. The 4th uid
    # likely came from the same enemy phase (remaining_spawns=1).
    ("20260425_005049_742", "m02", 2),
    # Run 2, mission 5 (Mission_Train). Turn 1 (combat_player) has 2
    # spawning_tiles plus 5 existing enemies; turn 2 shows 3 new uids.
    ("20260425_185532_218", "m05", 1),
]


# ---- analysis -----------------------------------------------------------


def analyze_case(run_id: str, mission: str, pre_turn: int, n_rolls: int = 60):
    print("\n" + "=" * 78)
    print(f"CASE: run_id={run_id}  mission={mission}  pre_turn={pre_turn}")
    print("=" * 78)

    pre = load_board(run_id, mission, pre_turn)
    post = load_board(run_id, mission, pre_turn + 1)
    if pre is None:
        print(f"  [SKIP] pre-board missing: {mission}_turn_{pre_turn:02d}_board.json")
        return None
    if post is None:
        print(f"  [SKIP] post-board missing: {mission}_turn_{pre_turn+1:02d}_board.json")
        return None

    region, ai_seed = active_region_seed(pre)
    master_seed = pre.get("master_seed")

    print(f"  mission_id      : {pre.get('mission_id')}")
    print(f"  pre.phase       : {pre.get('phase')} (turn={pre.get('turn')})")
    print(f"  post.phase      : {post.get('phase')} (turn={post.get('turn')})")
    print(f"  master_seed     : {master_seed}")
    print(f"  active region   : {region}")
    print(f"  ai_seed (pre)   : {ai_seed}")
    region_post, ai_seed_post = active_region_seed(post)
    print(f"  ai_seed (post)  : {ai_seed_post}  (engine reseeded after enemy phase)")
    print(f"  spawning_tiles  : "
          f"{[visual(tuple(t)) for t in pre.get('spawning_tiles', [])]} "
          f"raw={pre.get('spawning_tiles')}")
    print(f"  remaining_spawns: {pre.get('remaining_spawns')}")

    diff = diff_units(pre.get("units", []), post.get("units", []))
    print()
    print("  Ground-truth spawn diff (new uids in post-board):")
    if not diff["new"]:
        print("    <none — no new enemy uids appeared>")
        return None
    for u in diff["new"]:
        print(f"    uid={u['uid']:>4}  type={u['type']:<14}  "
              f"final_pos={visual((u['x'], u['y']))}  hp={u.get('hp')}")
    if diff["removed"]:
        print("  (also removed during enemy phase: "
              f"{[(u['type'], u['uid']) for u in diff['removed']]})")

    # ---- candidate prediction ----
    if ai_seed is None:
        print("\n  [SKIP prediction] no ai_seed captured for active region.")
        return None

    print()
    print("  --- candidate Park-Miller streams (Lua/macOS libc rand()) ---")
    for label, s in [("ai_seed (pre)", ai_seed),
                     ("ai_seed (post)", ai_seed_post),
                     ("master_seed", master_seed)]:
        if s is None:
            continue
        rolls5 = seed_replay.rolls(s, 12, upper=5)
        rollsN = seed_replay.rolls(s, 12, upper=len(diff["new"]) or 1)
        print(f"  seed({label:<14}={s:>11}):")
        print(f"    math.random(5)  first 12: {rolls5}")
        if len(diff["new"]):
            print(f"    math.random({len(diff['new'])})  first 12: {rollsN}")

    # ---- naive type-prediction attempt ----
    # Hypothesis H_naive: The first random_int(5) call decides weak-vs-strong
    # (`random_int(curr_weakRatio[2]) < curr_weakRatio[1]`), the second call
    # picks an index into the choices list. We don't know:
    #   - how many RNG calls the engine consumes BEFORE the first spawn-pick
    #     (AI move planning, attack ordering, animations all consume random_int
    #      from the same stream OR a different stream — unverified).
    #   - whether random_int uses the same libc rand() stream as math.random,
    #     or whether random_int / random_bool are bound to a separate
    #     std::mt19937 / xorshift inside itb_test.dylib (the .dylib is
    #     stripped of useful symbols beyond luaopen_itb_test).
    # The test below seeds Park-Miller and asks: given the SECOND random_int(N)
    # in the stream (offset K=0..50), does the index match any plausible pawn
    # in the mission's spawn list? We don't know the spawn list mapping at the
    # moment of capture, so we just print the candidate index sequences and
    # let a human eyeball whether anything looks structured.

    new_count = len(diff["new"])
    if new_count == 0:
        return None

    # Try matching: for each offset K in [0..40], take rolls K..K+new_count
    # from each candidate stream and print as "indices into a hypothetical
    # 8-slot pawn pool". This is intentionally coarse — we are NOT claiming
    # any of these constitute a match, just exposing the structure.
    print()
    print("  --- offset scan (does any stream window match observed types?) ---")
    print("  (we can only declare MATCH if there is an obvious structural "
          "alignment — none expected without engine RNG visibility.)")

    # We don't know the exact pool or its order, so we try a few common pool
    # sizes (5 = num_weak choices, 7 = full enemy roster on later islands).
    OBSERVED_TYPES = [u["type"] for u in diff["new"]]
    print(f"    observed type sequence: {OBSERVED_TYPES}")

    for label, s in [("ai_seed (pre)", ai_seed),
                     ("ai_seed (post)", ai_seed_post)]:
        if s is None:
            continue
        for pool_size in (5, 7, 8):
            stream = seed_replay.rolls(s, 50, upper=pool_size)
            # show first 30 indices for human inspection
            head = stream[:30]
            print(f"    {label} · random({pool_size}) head[0..29] = {head}")

    print()
    print("  --- honest verdict ---")
    print("  Without knowing how `random_int` (defined in itb_test.dylib, C++) "
          "is wired we cannot mechanically claim a match. The offset scan is "
          "for human inspection only. See docs/seed_replay_experiment.md for "
          "the full writeup of what offline tools this enables and what is "
          "blocked by the closed-source engine binding.")

    return {
        "run_id": run_id,
        "mission": mission,
        "pre_turn": pre_turn,
        "ai_seed": ai_seed,
        "master_seed": master_seed,
        "ground_truth_new_units": [
            {"uid": u["uid"], "type": u["type"],
             "final_pos": visual((u["x"], u["y"]))} for u in diff["new"]
        ],
        "spawning_tiles": [visual(tuple(t))
                           for t in pre.get("spawning_tiles", [])],
        "match_declared": False,
    }


# ---- CLI ---------------------------------------------------------------


def _parse_case(s: str) -> tuple[str, str, int]:
    """Parse RUN_ID:MISSION:TURN — e.g. 20260425_005049_742:m02:2."""
    parts = s.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"case must be RUN_ID:MISSION:TURN, got {s!r}")
    return parts[0], parts[1], int(parts[2])


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--case", action="append", type=_parse_case, default=None,
        help="(repeatable) RUN_ID:MISSION:TURN, e.g. 20260425_005049_742:m02:2",
    )
    ap.add_argument(
        "--rolls", type=int, default=60,
        help="number of RNG rolls to print per seed (default: 60)",
    )
    args = ap.parse_args()

    cases = args.case or DEFAULT_CASES
    results = []
    for run_id, mission, turn in cases:
        r = analyze_case(run_id, mission, turn, n_rolls=args.rolls)
        if r:
            results.append(r)

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  cases analyzed: {len(results)}")
    matches = [r for r in results if r["match_declared"]]
    print(f"  matches declared: {len(matches)}")
    if not matches:
        print("  No mechanical match was declared. This is the expected "
              "outcome given that `random_int` lives in C++ (itb_test.dylib) "
              "and we cannot see the engine's RNG call sequence. The "
              "captured `ai_seed` is still a useful artifact for OTHER "
              "offline uses (corpus indexing, run-fingerprinting, "
              "regression bisection); see docs/seed_replay_experiment.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
