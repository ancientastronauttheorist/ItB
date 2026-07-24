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
  2. Diff the two unit lists to identify new enemy uids, then flag lifecycle
     candidates (for example, Spider eggs and hatchlings) before treating the
     remainder as possible direct spawns.
  3. Read `master_seed` and the active region's `ai_seed` from the pre-spawn
     bridge_state.
  4. Using `seed_replay.py`'s pure-Python Park-Miller reproducer for one
     sampled macOS libc / Lua 5.1 model, generate the requested number of
     candidate rolls from each seed.
  5. Print candidate stream prefixes for manual inspection. This tool does not
     implement a pool mapping or a formal call-order/offset fit.

Why this matters
----------------
If we can reliably predict spawn types/order from `ai_seed` alone, we unlock
offline corpus expansion: bulk-replay every recorded turn through the solver
against observed post-enemy boards instead of having to capture every
intermediate state. If we cannot — and the C++ engine may consume RNG in an
opaque order — that's also a useful answer: it tells us our offline tools
will need a different signal (e.g., observing live RNG outputs through the
mod bridge, not seed reconstruction).

What this is NOT
----------------
- NOT used in any live decision loop. The output is a printed report.
- NOT a cheating tool. It only consumes recordings already on disk and the
  read-only Steam game source. No future-state knowledge during play.
- NOT a Lua interpreter port. We rely on the existing pure-Python
  `seed_replay.py` (Park-Miller LCG). This CLI does not implement a predictor;
  the native-visible `random_int` binding, its state, and the engine call
  sequence remain unmapped.

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


def load_board(
    run_id: str, mission_idx: str, turn: int
) -> dict[str, Any] | None:
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


def classify_new_units(
    pre: list[dict], diff: dict[str, list]
) -> list[dict[str, Any]]:
    """Classify new UID evidence without claiming engine spawn provenance.

    The snapshots straddle an entire enemy phase. A new UID can be a direct
    alarm-tile spawn, a Spider-created egg, or a hatchling replacing an egg.
    These labels are deliberately conservative candidates, not engine truth.
    """
    pre_enemy_types = {
        str(unit.get("type", ""))
        for unit in pre
        if unit.get("team") == 6
    }
    removed_types = {str(unit.get("type", "")) for unit in diff["removed"]}
    classified: list[dict[str, Any]] = []
    for unit in diff["new"]:
        pawn_type = str(unit.get("type", ""))
        if pawn_type.startswith("Spiderling") and any(
            kind.startswith("WebbEgg") for kind in removed_types
        ):
            origin = "lifecycle_candidate:hatched_egg"
        elif pawn_type.startswith("WebbEgg") and any(
            kind.startswith("Spider") for kind in pre_enemy_types
        ):
            origin = "lifecycle_candidate:spider_created_egg"
        else:
            origin = "direct_spawn_candidate"
        classified.append({"unit": unit, "origin": origin})
    return classified


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
    # spawning_tiles plus 5 existing enemies; turn 2 shows 4 new uids, two
    # of which have clear Spider/egg lifecycle explanations.
    ("20260425_185532_218", "m05", 1),
]


# ---- analysis -----------------------------------------------------------


def analyze_case(run_id: str, mission: str, pre_turn: int, n_rolls: int = 60):
    if n_rolls < 1:
        raise ValueError("n_rolls must be positive")

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
    print(f"  active region (post): {region_post}")
    print(f"  ai_seed (post)  : {ai_seed_post}")
    print(f"  spawning_tiles  : "
          f"{[visual(tuple(t)) for t in pre.get('spawning_tiles', [])]} "
          f"raw={pre.get('spawning_tiles')}")
    print(f"  remaining_spawns: {pre.get('remaining_spawns')}")

    diff = diff_units(pre.get("units", []), post.get("units", []))
    print()
    classified = classify_new_units(pre.get("units", []), diff)
    print("  New-unit diff (new enemy uids in post-board):")
    if not diff["new"]:
        print("    <none — no new enemy uids appeared>")
        return None
    for item in classified:
        u = item["unit"]
        print(f"    uid={u['uid']:>4}  type={u['type']:<14}  "
              f"final_pos={visual((u['x'], u['y']))}  hp={u.get('hp')}  "
              f"origin={item['origin']}")
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
        rolls5 = seed_replay.rolls(s, n_rolls, upper=5)
        rollsN = seed_replay.rolls(
            s, n_rolls, upper=len(diff["new"]) or 1
        )
        print(f"  seed({label:<14}={s:>11}):")
        print(f"    math.random(5)  first {n_rolls}: {rolls5}")
        if len(diff["new"]):
            print(
                f"    math.random({len(diff['new'])})  first {n_rolls}: "
                f"{rollsN}"
            )

    # ---- naive type-prediction attempt ----
    # Hypothesis H_naive: The first random_int(5) call decides weak-vs-strong
    # (`random_int(curr_weakRatio[2]) < curr_weakRatio[1]`), the second call
    # picks an index into the choices list. We don't know:
    #   - whether and how many RNG calls other engine systems make before the
    #     first spawn pick; AI planning and animation are candidates, not facts.
    #   - whether random_int uses the same libc rand() stream as math.random,
    #     or whether random_int / random_bool are bound to a separate native
    #     std::mt19937 / xorshift or another generator.
    # We do not know the spawn pool mapping or native call order at the moment
    # of capture, so the report only exposes candidate prefixes.

    new_count = len(diff["new"])
    if new_count == 0:
        return None

    print()
    print("  --- candidate index streams (manual inspection only) ---")
    print("  (no pool mapping or formal call-order/offset fit is implemented)")

    # We don't know the exact pool or its order, so we try a few common pool
    # sizes (5 = num_weak choices, 7 = full enemy roster on later islands).
    observed_types = [u["type"] for u in diff["new"]]
    direct_candidates = [
        item["unit"]["type"]
        for item in classified
        if item["origin"] == "direct_spawn_candidate"
    ]
    print(f"    new-uid type sequence: {observed_types}")
    print(f"    possible direct-spawn subset: {direct_candidates}")

    for label, s in [("ai_seed (pre)", ai_seed),
                     ("ai_seed (post)", ai_seed_post)]:
        if s is None:
            continue
        for pool_size in (5, 7, 8):
            stream = seed_replay.rolls(s, n_rolls, upper=pool_size)
            print(
                f"    {label} · random({pool_size}) first {n_rolls} = "
                f"{stream}"
            )

    print()
    print("  --- honest verdict ---")
    print("  Without mapping the native-visible `random_int` binding and its "
          "state for an exact build, we cannot mechanically claim a match. "
          "The candidate display is "
          "for human inspection only. See docs/seed_replay_experiment.md for "
          "the full writeup of what offline tools this enables and what is "
          "blocked by the closed-source engine binding.")

    return {
        "run_id": run_id,
        "mission": mission,
        "pre_turn": pre_turn,
        "ai_seed": ai_seed,
        "master_seed": master_seed,
        "observed_new_units": [
            {
                "uid": item["unit"]["uid"],
                "type": item["unit"]["type"],
                "final_pos": visual(
                    (item["unit"]["x"], item["unit"]["y"])
                ),
                "origin": item["origin"],
            }
            for item in classified
        ],
        "spawning_tiles": [visual(tuple(t))
                           for t in pre.get("spawning_tiles", [])],
    }


# ---- CLI ---------------------------------------------------------------


def _parse_case(s: str) -> tuple[str, str, int]:
    """Parse RUN_ID:MISSION:TURN — e.g. 20260425_005049_742:m02:2."""
    parts = s.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"case must be RUN_ID:MISSION:TURN, got {s!r}")
    return parts[0], parts[1], int(parts[2])


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


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
        "--rolls", type=_positive_int, default=60,
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
    print("  mechanical matching: not implemented")
    print("  The native-visible `random_int` binding, hidden state, and engine "
          "call sequence remain unmapped. Captured `ai_seed` values are still "
          "useful for corpus indexing, run fingerprinting, and regression "
          "bisection; see docs/seed_replay_experiment.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
