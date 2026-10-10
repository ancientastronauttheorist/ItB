#!/usr/bin/env python3
"""Offline check of the C++ solver adapter on recorded boards (no game).

For each recordings/<run>/m*_turn_*_solve_input.json (an even sample):
  1. solve with the engine through src/solver/cpp_solver.py, exactly as
     cmd_solve does (same bridge JSON);
  2. check the plan converts to executable bot actions: one MechAction per
     entry, move_to on the board, weapon in the unit's loadout (the slot the
     bridge fires), repairs in place, no sub-action of a unit after its
     attack/repair, move-only entries followed by the unit's action only when
     interleaving was kept;
  3. round-trip every predicted state through verify.diff_states against a
     Board built from the same predicted board (must be empty: the snapshot
     and the comparator agree on every field);
  4. cross-check field conventions against the old solver: simulate the
     recorded (Rust) plan with the engine and diff the engine's snapshots
     against the Rust predicted_states recorded for that plan. Differences
     here are real model differences or convention mismatches; a systematic
     field (on every board) would be a convention bug.

Imports only the adapter, the model and verify (no capture/control/desktop
modules). Usage:
    python3 scripts/validate_cpp_solver.py [--sample N] [--time T] [--threads K]
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ.setdefault("ITB_SAVE_DIR", tempfile.mkdtemp(prefix="itb_cpp_validate_save_"))

from src.solver import cpp_solver  # noqa: E402
from src.solver.verify import diff_states  # noqa: E402
from src.model.board import Board  # noqa: E402


VERBOSE = False


def check_actions(sol, bridge, meta) -> list[str]:
    problems = []
    units = {u["uid"]: u for u in bridge["units"] if not u.get("is_extra_tile")}
    acted = set()
    uids = [a.mech_uid for a in sol.actions]
    for i, a in enumerate(sol.actions):
        u = units.get(a.mech_uid)
        if u is None:
            problems.append(f"a{i}: uid {a.mech_uid} not on board")
            continue
        if not (0 <= a.move_to[0] < 8 and 0 <= a.move_to[1] < 8):
            problems.append(f"a{i}: move_to off board {a.move_to}")
        if a.mech_uid in acted:
            problems.append(f"a{i}: sub-action after the unit's attack/repair")
        if a.weapon == "_REPAIR":
            acted.add(a.mech_uid)
            if tuple(a.target) != tuple(a.move_to):
                problems.append(f"a{i}: repair not in place")
        elif a.weapon not in ("None", "", "Unknown"):
            acted.add(a.mech_uid)
            if a.weapon not in (u.get("weapons") or []):
                problems.append(f"a{i}: weapon {a.weapon} not in loadout {u.get('weapons')}")
            if not (0 <= a.target[0] < 8 and 0 <= a.target[1] < 8):
                problems.append(f"a{i}: target off board {a.target}")
        else:
            later = a.mech_uid in uids[i + 1:]
            if later and not meta.get("interleaved"):
                problems.append(f"a{i}: move-only with a later entry in a non-interleaved plan")
    # Every active player unit ends the plan inactive (End Turn gate).
    for uid in cpp_solver.idle_units(bridge, [{"uid": a.mech_uid} for a in sol.actions]):
        problems.append(f"unit {uid} active but absent from the plan")
    return problems


def roundtrip(engine, bridge: dict, out) -> list[str]:
    """Each predicted snapshot vs a Board rebuilt from the predicted board it
    was taken from: must be empty (snapshot and comparator agree)."""
    problems = []
    plan = out.meta["executed_plan"]
    sim = json.loads(engine.simulate(json.dumps(bridge), cpp_solver._plan_payload(plan)))
    last = {int(e["uid"]): i for i, e in enumerate(plan)}
    skipped = set()
    for i, step in enumerate(sim["steps"]):
        entry = out.enriched["predicted_states"][i]
        checks = []
        if step.get("after_move"):
            checks.append(("post_move", step["after_move"]))
        elif entry.get("post_move") is not None:
            problems.append(f"a{i}: post_move without a move")
        checks.append(("post_attack", step["after_action"]))
        for key, eng_board in checks:
            board = Board.from_bridge_data(cpp_solver.bridge_board(eng_board, bridge))
            if key == "post_attack" and plan[i]["kind"] == "none" and last[int(plan[i]["uid"])] == i:
                skipped.add(int(plan[i]["uid"]))  # the bot SKIPs it
            for u in board.units:
                if u.uid in skipped:
                    u.active = False
            d = diff_states(entry[key], board)
            problems.extend(f"a{i} {key}: {x}" for x in d.unit_diffs + d.tile_diffs + d.scalar_diffs)
    return problems


def rust_plan_to_engine(actions: list[dict], bridge: dict) -> list[dict]:
    pos = {u["uid"]: (u["x"], u["y"]) for u in bridge["units"]}
    plan = []
    for a in actions:
        mv = a.get("move_to")
        w = a.get("weapon_id") or ""
        t = a.get("target")
        entry = {"uid": a["mech_uid"], "move": mv if mv and tuple(mv) != pos.get(a["mech_uid"]) else None,
                 "kind": "none", "weapon": "", "target": None, "target2": a.get("target2")}
        if w == "_REPAIR":
            entry.update(kind="repair", weapon="Skill_Repair", target=mv)
        elif w and w not in ("Unknown", "None") and t and 0 <= t[0] < 8 and 0 <= t[1] < 8:
            entry.update(kind="weapon", weapon=w, target=t)
        plan.append(entry)
    return plan


def cross_check(engine, bridge: dict, solve_path: Path, counter: collections.Counter) -> str:
    try:
        rec = json.loads(solve_path.read_text())["data"]
    except Exception:
        return "no recorded solve"
    rust_states = rec.get("predicted_states") or []
    actions = rec.get("actions") or []
    if not rust_states or len(rust_states) != len(actions):
        return "no rust predictions"
    plan = rust_plan_to_engine(actions, bridge)
    sim = json.loads(engine.simulate(json.dumps(bridge), json.dumps(plan)))
    if sim.get("refused", -1) >= 0:
        return f"engine refused recorded plan: {sim.get('refused_reason')}"
    for i, step in enumerate(sim["steps"]):
        rust = rust_states[i]
        rust_post = rust.get("post_attack") if isinstance(rust, dict) and "post_attack" in rust else rust
        board = Board.from_bridge_data(cpp_solver.bridge_board(step["after_action"], bridge))
        if plan[i]["kind"] == "none":
            for u in board.units:
                if u.uid == plan[i]["uid"]:
                    u.active = False
        d = diff_states(rust_post, board)
        if VERBOSE and not d.is_empty():
            print(f"  cross {solve_path.parent.name}/{solve_path.name} a{i}: "
                  f"{(d.unit_diffs + d.tile_diffs + d.scalar_diffs)[:4]}")
        for ud in d.unit_diffs:
            counter[f"unit.{ud['field']}"] += 1
        for td in d.tile_diffs:
            counter[f"tile.{td['field']}"] += 1
        for sd in d.scalar_diffs:
            counter[f"scalar.{sd['field']}"] += 1
        counter["steps"] += 1
        if d.is_empty():
            counter["steps_identical"] += 1
    return "ok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--time", type=float, default=3.0)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--json", type=str, default="")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    global VERBOSE
    VERBOSE = args.verbose

    files = sorted(REPO.glob("recordings/*/m*_turn_*_solve_input.json"))
    if args.sample and args.sample < len(files):
        files = [files[i * len(files) // args.sample] for i in range(args.sample)]
    engine = cpp_solver.get_engine(args.threads, 0)
    print(f"engine: {engine.game_root} threads={engine.threads} load={engine.load_seconds:.2f}s")

    stats = collections.Counter()
    cross = collections.Counter()
    rows = []
    for f in files:
        bridge = json.loads(f.read_text())["data"]["bridge_state"]
        active = [u for u in bridge["units"] if u.get("team") == 1 and u.get("active") and u.get("hp", 0) > 0]
        t0 = time.time()
        out = cpp_solver.solve(bridge, args.time, spawns=[tuple(s) for s in bridge.get("spawning_tiles", [])],
                               current_turn=bridge.get("turn", 0), total_turns=bridge.get("total_turns", 5),
                               active_mech_count=len(active), threads=args.threads)
        dt = time.time() - t0
        row = {"file": str(f.relative_to(REPO)), "ok": out.ok, "reason": out.reason, "time": round(dt, 2)}
        if VERBOSE:
            print(f"{row['file']}: {dt:.2f}s ok={out.ok} {out.meta.get('proven_optimal')} "
                  f"{out.meta.get('worst_case')}")
        stats["boards"] += 1
        if not out.ok:
            stats["fallback"] += 1
            stats[f"fallback: {out.reason.split(':')[0]}"] += 1
            print(f"FALLBACK {row['file']}: {out.reason}")
            rows.append(row)
            continue
        meta = out.meta
        stats["ok"] += 1
        stats["proven"] += int(bool(meta.get("proven_optimal")))
        stats["interleaved_raw"] += int(bool(meta.get("interleaved")))
        stats["interleaved_kept"] += int(bool(meta.get("interleaved")) and not (meta.get("regroup") or {}).get("equivalent"))
        stats["dropped_after_action"] += int(bool(meta.get("dropped_after_unit_action")))
        stats["time_over_budget"] += int(dt > args.time + 0.5)
        problems = check_actions(out.solution, bridge, meta)
        rt = roundtrip(engine, bridge, out)
        if len(out.enriched["predicted_states"]) != len(out.solution.actions):
            problems.append("predicted_states length mismatch")
        for p in problems:
            print(f"ACTION PROBLEM {row['file']}: {p}")
        for p in rt:
            print(f"ROUNDTRIP {row['file']}: {p}")
        stats["action_problems"] += len(problems)
        stats["roundtrip_diffs"] += len(rt)
        cc = cross_check(engine, bridge, f.with_name(f.name.replace("_solve_input", "_solve")), cross)
        stats[f"cross: {cc.split(':')[0]}"] += 1
        row.update(proven=meta.get("proven_optimal"), worst=meta.get("worst_case"),
                   actions=[a.description for a in out.solution.actions], cross=cc)
        rows.append(row)
    print("\n== summary ==")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    print("== engine vs recorded Rust predictions (recorded plans, per sub-action) ==")
    for k, v in sorted(cross.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")
    if args.json:
        Path(args.json).write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return 0 if stats["action_problems"] == 0 and stats["roundtrip_diffs"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
