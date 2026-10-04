#!/usr/bin/env python3
"""Independent bounded primitive/compound enumeration over one synthetic fixture.

Python supplies Ground/Rubble BFS and all action choices; Rust alone projects prefixes
and scores complete turns. This establishes conditional model search comparisons,
not original-game fidelity, legal-action admission, or a full-loop certificate.
"""
from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DIRS = ((0, 1), (1, 0), (0, -1), (-1, 0))
ACTORS = (0, 1)
REPAIR = "_REPAIR"
BASELINE = "data/solver_first/s2_primitive_411_counterexample.json"
BASELINE_SHA = "b6045313a1b980ad297e25ea8521a11fc57f225a72ca5b4140955cd09fc476c1"
SOURCES = ("scripts/solver_first_primitive_search.py", "tests/test_solver_first_primitive_search.py",
           "rust_solver/src/lib.rs", "rust_solver/src/primitive.rs", "rust_solver/src/solver.rs",
           "rust_solver/src/simulate.rs", "rust_solver/src/movement.rs", "rust_solver/src/weapons.rs",
           "rust_solver/src/serde_bridge.rs", "rust_solver/src/evaluate.rs", "rust_solver/src/board.rs",
           "rust_solver/src/turn_projection.rs", "rust_solver/src/enemy.rs", "rust_solver/src/types.rs",
           "rust_solver/src/plan_evaluation.rs", "src/solver/verify.py")


class ReferenceError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise ReferenceError(reason)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def build_case():
    """Reconstruct only the normalized, pinned baseline input, including flags."""
    ground = {(x, 3) for x in range(6)} | {(3, 4), (4, 4), (5, 4)}
    buildings = {(4, 2), (6, 3)}
    tiles = []
    for x in range(8):
        for y in range(8):
            tile = dict(x=x, y=y, terrain="ground" if (x, y) in ground else "chasm")
            if (x, y) in buildings:
                tile.update(terrain="building", building_hp=2)
            tiles.append(tile)
    units = []
    for uid, name, xy, weapon in ((0, "TankMech", (3, 3), "Brute_Tankmech"),
                                   (1, "PunchMech", (0, 3), "Prime_Punchmech")):
        units.append(dict(uid=uid, type=name, x=xy[0], y=xy[1], hp=3, max_hp=3,
                          team=1, mech=True, move=3, active=True, can_move=True,
                          flying=False, massive=True, armor=False, powered=True,
                          pushable=True, weapons=[weapon]))
    units.append(dict(uid=2, type="Firefly1", x=4, y=3, hp=3, max_hp=3,
                      team=6, mech=False, move=3, active=False, can_move=False,
                      flying=False, massive=False, armor=False, powered=True,
                      pushable=True, weapons=["FireflyAtk1"], has_queued_attack=True,
                      queued_target=[6, 3]))
    return dict(tiles=tiles, units=units, attack_order=[2], grid_power=7,
                grid_power_max=7, turn=1, total_turns=1, remaining_spawns=0,
                spawning_tiles=[])


def validate_domain(board):
    require(type(board) is dict and encode(board) == encode(build_case()),
            "input differs from exact two-actor fixture; readiness/features fail closed")
    return ACTORS


def unit_by_uid(board, uid):
    units = board.get("units")
    require(type(units) is list and all(type(u) is dict for u in units), "projection units invalid")
    matches = [u for u in units if u.get("uid") == uid]
    require(len(matches) <= 1, "duplicate projected uid")
    return matches[0] if matches else None


def alive(unit):
    return unit is not None and type(unit.get("hp")) is int and unit["hp"] > 0


def validate_projected_terrain(board):
    """Allow only the fixture's terrain and its destroyed-building consequence."""
    tiles = board.get("tiles")
    require(type(tiles) is list and len(tiles) <= 64, "projected tile coverage differs")
    expected = {(t["x"], t["y"]): t for t in build_case()["tiles"]}
    seen = set()
    for tile in tiles:
        require(type(tile) is dict and type(tile.get("x")) is int
                and type(tile.get("y")) is int, "projected tile coordinates invalid")
        pos = (tile["x"], tile["y"])
        require(pos in expected and pos not in seen, "projected tile identity differs")
        seen.add(pos)
        original = expected[pos]["terrain"]
        if original == "building":
            require(tile.get("terrain") in ("building", "rubble"),
                    "unsupported projected building terrain consequence")
            hp = tile.get("building_hp", 0)
            require(type(hp) is int and 0 <= hp <= 2, "projected building HP invalid")
            require((tile["terrain"] == "rubble") is (hp == 0),
                    "destroyed building/Rubble consequence disagrees")
        else:
            require(tile.get("terrain") == original,
                    "unsupported projected terrain consequence")
    # board_to_json omits only wholly default Ground tiles. Accept that
    # representation only at originally Ground coordinates; missing Chasm or
    # Building/Rubble is a domain failure, never a default-filled disappearance.
    missing = set(expected) - seen
    require(all(expected[pos]["terrain"] == "ground" for pos in missing),
            "projected non-default tile disappeared")
    return dict(board, tiles=tiles + [dict(x=x, y=y, terrain="ground")
                                     for x, y in sorted(missing)])


def destinations(board, uid):
    """Ground/Rubble BFS; friendly live transit, never an occupied stop."""
    actor = unit_by_uid(board, uid)
    require(alive(actor) and actor.get("team") == 1 and actor.get("active") is True,
            "movement actor unavailable")
    if actor.get("can_move") is not True:
        return ()
    origin = (actor["x"], actor["y"])
    terrain = {(t["x"], t["y"]): t["terrain"] for t in board["tiles"]}
    occupied = {(u["x"], u["y"]): u for u in board["units"]
                if u["uid"] != uid and (alive(u) or u.get("mech") is True)}
    queue, distance, stops = deque([origin]), {origin: 0}, set()
    while queue:
        x, y = queue.popleft()
        for dx, dy in DIRS:
            pos, cost = (x + dx, y + dy), distance[(x, y)] + 1
            if pos in distance or cost > 3 or terrain.get(pos) not in ("ground", "rubble"):
                continue
            blocker = occupied.get(pos)
            if blocker is not None and (not alive(blocker) or blocker.get("team") != 1):
                continue
            distance[pos] = cost
            queue.append(pos)
            if blocker is None:
                stops.add(pos)
    return tuple(sorted(stops))


def closing_choices(board, uid):
    actor = unit_by_uid(board, uid)
    require(alive(actor) and actor.get("active") is True and actor.get("team") == 1,
            "use actor unavailable")
    weapon = {0: "Brute_Tankmech", 1: "Prime_Punchmech"}[uid]
    x, y = actor["x"], actor["y"]
    for dx, dy in DIRS:
        target = [x + dx, y + dy]
        if all(0 <= n < 8 for n in target):
            yield dict(kind="use", mech_uid=uid, weapon_id=weapon, target=target)
    # Full-HP Repair is deliberately retained; no usefulness/effect pruning.
    yield dict(kind="use", mech_uid=uid, weapon_id=REPAIR, target=[x, y])
    yield dict(kind="wait", mech_uid=uid)


@dataclass
class Counts:
    prefix_attempts: int = 0
    prefix_admitted: int = 0
    oracle_failures: int = 0
    leaves_scored: int = 0
    steps_generated: int = 0
    deadline_cutoffs: int = 0


def prefix_entitlements(steps):
    """Independent ordinary action ledger; never accept oracle readiness as authority."""
    ledger = {uid: dict(uid=uid, moved=False, used=False) for uid in ACTORS}
    for step in steps:
        require(type(step) is dict and type(step.get("mech_uid")) is int
                and step["mech_uid"] in ledger, "prefix actor invalid")
        e = ledger[step["mech_uid"]]
        require(not e["used"], "prefix use entitlement already spent")
        kind = step.get("kind")
        if kind == "move":
            require(not e["moved"], "prefix movement entitlement already spent")
            require(set(step) == {"kind", "mech_uid", "to"}, "prefix Move fields invalid")
            e["moved"] = True
        elif kind in ("use", "wait"):
            require(set(step) == ({"kind", "mech_uid"} if kind == "wait" else
                                 {"kind", "mech_uid", "weapon_id", "target"}),
                    "prefix closing fields invalid")
            e["moved"] = e["used"] = True
        else:
            raise ReferenceError("prefix step kind invalid")
    return ledger


def project(replay, board_json, steps, counts):
    counts.prefix_attempts += 1
    try:
        ledger = prefix_entitlements(steps)
        raw = replay(board_json, encode(steps))
        result = json.loads(raw) if isinstance(raw, str) else raw
        require(type(result) is dict and result.get("schema_version") == 1
                and type(result.get("scope")) is dict
                and result["scope"].get("readiness") == "ordinary_once_per_turn; no extra movement/use grants",
                "oracle schema/readiness scope differs")
        require(type(result) is dict and type(result.get("complete")) is bool,
                "oracle completeness invalid")
        require(type(result.get("post_player_board")) is dict, "oracle prefix board missing")
        require(type(result.get("actor_entitlements")) is list, "oracle entitlements missing")
        entries = result["actor_entitlements"]
        require(len(entries) == 2 and {e.get("uid") for e in entries} == set(ACTORS),
                "oracle original actor coverage differs")
        for e in entries:
            require(type(e.get("moved")) is bool and type(e.get("used")) is bool,
                    "oracle entitlement flags invalid")
            expected = ledger[e["uid"]]
            require(e["moved"] is expected["moved"] and e["used"] is expected["used"],
                    "oracle readiness differs from independent prefix ledger")
        require(type(result.get("admissions")) is list and type(result.get("action_results")) is list,
                "oracle admission/action result arrays missing")
        require(len(result["action_results"]) == len(steps), "oracle step result coverage differs")
        for action in result["action_results"]:
            require(type(action) is dict and type(action.get("events")) is list
                    and all(type(event) is str for event in action["events"]),
                    "oracle action events invalid")
            require(not any(event.lower().startswith(("illegal_", "invalid_"))
                            for event in action["events"]), "oracle returned rejected action event")
            require(type(action.get("buildings_damaged")) is int
                    and action["buildings_damaged"] >= 0, "player building damage receipt invalid")
        state = validate_projected_terrain(result["post_player_board"])
        result = dict(result, post_player_board=state)
        require({u.get("uid") for u in state.get("units", [])} <= {0, 1, 2},
                "unexpected actor creation outside fixture")
        ready = []
        for e in ledger.values():
            actor = unit_by_uid(state, e["uid"])
            original = unit_by_uid(build_case(), e["uid"])
            require(actor is not None, "persistent actor/wreck disappeared")
            require(type(actor.get("hp")) is int and 0 <= actor["hp"] <= 3,
                    "actor HP outside fixture")
            require(all(actor.get(key) == original[key]
                        for key in ("team", "type", "mech", "move", "max_hp", "weapons")),
                    "projected actor identity changed")
            require(all(type(actor.get(key)) is int and 0 <= actor[key] < 8 for key in ("x", "y")),
                    "projected actor coordinates invalid")
            if alive(actor):
                require(actor.get("team") == 1, "original actor team changed")
                require(actor.get("active") is (not e["used"]), "readiness/entitlement disagreement")
                require(actor.get("can_move") is (not (e["moved"] or e["used"])),
                        "movement readiness/entitlement disagreement")
                if not e["used"]:
                    ready.append(e["uid"])
        require(result["complete"] is (not ready), "oracle terminal/readiness disagreement")
        if result["complete"]:
            require(type(result.get("final_board")) is dict, "terminal final board missing")
            require(type(result.get("score")) in (int, float) and math.isfinite(result["score"]),
                    "terminal score invalid")
            require(type(result.get("clean")) is bool, "terminal clean flag invalid")
            damage = 0
            for action in result["action_results"]:
                damage += action["buildings_damaged"]
            initial_buildings = sum(t["terrain"] == "building" and t.get("building_hp", 0) > 0
                                    for t in build_case()["tiles"])
            remaining_buildings = sum(t["terrain"] == "building" and t.get("building_hp", 0) > 0
                                      for t in state["tiles"])
            require(result["clean"] is (initial_buildings == remaining_buildings and damage == 0),
                    "clean flag differs from independent building classification")
        else:
            require(result.get("score") is None and result.get("clean") is None,
                    "prefix was prematurely scored")
        counts.prefix_admitted += 1
        return result
    except Exception:
        counts.oracle_failures += 1
        raise


def check_budget(counts, deadline, max_nodes):
    if time.monotonic() > deadline or counts.prefix_attempts >= max_nodes:
        counts.deadline_cutoffs += 1
        raise ReferenceError("reference deadline/node budget exhausted; incomplete traversal")


def enumerate_leaves(board, replay, *, compound=False, counts=None,
                     reference_budget=120.0, max_nodes=1000000,
                     closing_generator=closing_choices, prefix_observer=None):
    """Yield every complete schedule, never production action generation."""
    validate_domain(board)
    require(type(reference_budget) in (int, float) and math.isfinite(reference_budget)
            and reference_budget > 0 and type(max_nodes) is int and max_nodes > 0,
            "invalid reference budget")
    counts = counts if counts is not None else Counts()
    deadline, board_json = time.monotonic() + reference_budget, encode(board)

    def visit(steps, locked=None):
        check_budget(counts, deadline, max_nodes)
        result = project(replay, board_json, steps, counts)
        if prefix_observer is not None:
            prefix_observer(steps, result)
        if result["complete"]:
            counts.leaves_scored += 1
            yield steps, result
            return
        require(len(steps) < 4, "nonterminal after maximum fixture entitlements")
        state = result["post_player_board"]
        entitlements = prefix_entitlements(steps)
        ready = [uid for uid in ACTORS if alive(unit_by_uid(state, uid))
                 and not entitlements[uid]["used"]]
        if locked is not None:
            require(locked in ready, "compound move unexpectedly lost its actor")
            ready = [locked]
        for uid in ready:
            if not entitlements[uid]["moved"] and locked is None:
                for pos in destinations(state, uid):
                    counts.steps_generated += 1
                    yield from visit(steps + [dict(kind="move", mech_uid=uid, to=list(pos))],
                                     uid if compound else None)
            for step in closing_generator(state, uid):
                counts.steps_generated += 1
                yield from visit(steps + [step], None)

    yield from visit([])


def selected_policy(raw_best, clean_best):
    if clean_best is not None and raw_best["score"] - clean_best["score"] <= max(
            abs(raw_best["score"]) * 0.05, 500.0):
        return clean_best
    return raw_best


def reference(board, replay, **kwargs):
    counts, membership = Counts(), set()
    raw_best = clean_best = None
    try:
        for steps, summary in enumerate_leaves(board, replay, counts=counts, **kwargs):
            membership.add(encode(steps))
            candidate = dict(steps=steps, score=summary["score"], clean=summary["clean"])
            if raw_best is None or candidate["score"] > raw_best["score"]:
                raw_best = candidate
            if candidate["clean"] and (clean_best is None or candidate["score"] > clean_best["score"]):
                clean_best = candidate
        require(raw_best is not None and counts.leaves_scored > 0, "no complete leaves")
        return dict(complete=True, counts=asdict(counts), raw_best=raw_best,
                    clean_best=clean_best, policy_best=selected_policy(raw_best, clean_best)), membership
    except Exception as exc:
        return dict(complete=False, counts=asdict(counts), reason=str(exc),
                    partial_raw_best=raw_best, partial_clean_best=clean_best), membership


def evaluate_case(board, replay, solve, *, solver_budget=10.0, reference_budget=120.0,
                  max_nodes=1000000, tolerance=1e-7):
    validate_domain(board)
    atomic, members = reference(board, replay, reference_budget=reference_budget, max_nodes=max_nodes)
    compound, _ = reference(board, replay, compound=True, reference_budget=reference_budget, max_nodes=max_nodes)
    result = dict(status="incomplete", primitive_reference=atomic, compound_reference=compound,
                  original_execution_admissions=0, held_out_cases=0, fair_archive_admissions=0,
                  ledger_promotions=0, certificate=None, valid_bounds=None, horizon_player_turns=1)
    if not (atomic["complete"] and compound["complete"]):
        return result
    selected_counts = Counts()
    try:
        raw = solve(encode(board), solver_budget)
        solution = json.loads(raw) if isinstance(raw, str) else raw
        require(type(solution) is dict and type(solution.get("steps")) is list, "solver steps invalid")
        require(solution.get("proof_status") == "best_found" and solution.get("certificate") is None
                and solution.get("valid_bounds") is None, "unexpected production proof contract")
        require(encode(solution["steps"]) in members, "production selection outside independent schedule pool")
        summary = project(replay, encode(board), solution["steps"], selected_counts)
        require(summary["complete"], "production selected incomplete prefix")
        require(type(solution.get("score")) in (int, float) and math.isfinite(solution["score"]),
                "production score invalid")
        parity = abs(solution["score"] - summary["score"]) <= tolerance
        raw_regret = atomic["raw_best"]["score"] - summary["score"]
        policy_regret = atomic["policy_best"]["score"] - summary["score"]
        require(raw_regret >= -tolerance, "selection exceeds exhaustive raw reference")
        result.update(status="complete" if parity else "objective_mismatch",
                      production=solution, selected_replay=summary, selected_membership=True,
                      score_parity=parity, raw_regret=raw_regret, policy_regret=policy_regret,
                      matches_reference_policy=parity and abs(policy_regret) <= tolerance
                      and summary["clean"] == atomic["policy_best"]["clean"],
                      primitive_minus_compound_raw=atomic["raw_best"]["score"] - compound["raw_best"]["score"],
                      root_proof_status=solution["proof_status"], comparison_tolerance=tolerance)
    except Exception as exc:
        result.update(status="failed", reason=str(exc))
    result["selected_counts"] = asdict(selected_counts)
    return result


def source_pins():
    pins = {}
    for name in SOURCES:
        path = ROOT / name
        require(path.is_file(), "required source pin missing: " + name)
        raw = path.read_bytes()
        pins[name] = dict(size=len(raw), raw_sha256=sha256(raw).hexdigest(),
                          lf_sha256=sha256(raw.replace(b"\r\n", b"\n")).hexdigest())
    return pins


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-simulator-version", type=int, required=True)
    parser.add_argument("--solver-budget", type=float, default=10.0)
    parser.add_argument("--reference-budget", type=float, default=120.0)
    parser.add_argument("--max-nodes", type=int, default=1000000)
    args = parser.parse_args()
    require(not args.output.exists(), "output is create-only")
    require(math.isfinite(args.solver_budget) and args.solver_budget > 0
            and math.isfinite(args.reference_budget) and args.reference_budget > 0
            and args.max_nodes > 0, "invalid budget")
    raw_baseline = (ROOT / BASELINE).read_bytes()
    require(sha256(raw_baseline).hexdigest() == BASELINE_SHA, "old baseline receipt changed")
    before = json.loads(raw_baseline)
    board = build_case()
    require(encode(before["input"]) == encode(board) and before["version"] == 411,
            "normalized fixture differs from pinned before receipt")
    import itb_solver
    from scripts.solver_first_s0 import loaded_extension_path
    require(itb_solver.simulator_version() == args.expected_simulator_version, "model version differs")
    extension = loaded_extension_path(itb_solver)
    extension_hash = sha256(extension.read_bytes()).hexdigest()
    sources = source_pins()
    case = evaluate_case(board, itb_solver.replay_primitives, itb_solver.solve_primitives,
                         solver_budget=args.solver_budget, reference_budget=args.reference_budget,
                         max_nodes=args.max_nodes)
    stable = sources == source_pins() and extension_hash == sha256(extension.read_bytes()).hexdigest()
    report = dict(schema_version=1, evidence_class="synthetic_independent_primitive_enumeration_shared_Rust_model",
                  simulator_version=args.expected_simulator_version, input=board,
                  input_sha256=sha256(encode(board).encode()).hexdigest(),
                  extension_sha256=extension_hash, source_pins=sources, pins_stable=stable,
                  before_receipt_sha256=BASELINE_SHA,
                  before_compound=before["compound_solver"],
                  before_primitive_diagnostic=before["primitive_diagnostic"],
                  claim="Conditional exhaustive enumeration over this exact synthetic readiness fixture; production remains best_found. No original-game or full-goal claim.",
                  action_scope="Ordinary once-per-turn Move before Use/Wait readiness, with interleaving; no live executor integration.",
                  terrain_scope="Independent movement traverses and stops on Ground and Rubble, including destroyed initially intact buildings. Other initial terrain is Chasm; unexpected projected terrain changes fail closed.",
                  original_execution_admissions=0, held_out_cases=0, fair_archive_admissions=0,
                  gate_promotions=0, certificate=None, valid_bounds=None, horizon_player_turns=1,
                  case=case)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(encode(dict(status=case["status"], pins_stable=stable,
                      matches_reference_policy=case.get("matches_reference_policy", False))))
    return 0 if stable and case["status"] == "complete" and case.get("matches_reference_policy") else 1


if __name__ == "__main__":
    raise SystemExit(main())
