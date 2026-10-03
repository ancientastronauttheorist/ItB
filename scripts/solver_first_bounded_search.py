#!/usr/bin/env python3
"""Independent exhaustive movement/Wait/Repair reference, with Rust leaf scoring.

This is a synthetic development search check. Rust remains the transition and
evaluation oracle; this tool supplies neither original-game fidelity evidence
nor an admitted fair observation, campaign result, or practical strength claim.
"""
from __future__ import annotations

import argparse
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
import math
from pathlib import Path
import sys
import time
from typing import Callable, Iterator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))
STARTERS = (("PunchMech", (3, 2), 3), ("TankMech", (4, 2), 3),
            ("ArtiMech", (3, 4), 2))
WAIT = ""
REPAIR = "_REPAIR"
TOP_KEYS = {"tiles", "units", "attack_order", "grid_power", "grid_power_max",
            "turn", "total_turns", "remaining_spawns", "spawning_tiles"}
UNIT_KEYS = {"uid", "type", "x", "y", "hp", "max_hp", "team", "mech", "move",
             "active", "can_move", "flying", "massive", "armor", "powered",
             "pushable", "weapons", "has_queued_attack", "queued_target"}
SOURCE_PATHS = ("scripts/solver_first_bounded_search.py", "rust_solver/src/lib.rs",
                "rust_solver/src/solver.rs", "rust_solver/src/movement.rs",
                "rust_solver/src/simulate.rs", "rust_solver/src/serde_bridge.rs",
                "rust_solver/src/evaluate.rs", "rust_solver/src/weapons.rs",
                "rust_solver/src/search_audit.rs", "rust_solver/src/enemy.rs",
                "rust_solver/src/board.rs", "rust_solver/src/types.rs")


class ReferenceError(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ReferenceError(reason)


def encode(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def source_pins() -> dict:
    pins = {}
    for path in SOURCE_PATHS:
        raw = (ROOT / path).read_bytes()
        pins[path] = dict(raw_sha256=sha256(raw).hexdigest(),
                          lf_sha256=sha256(raw.replace(b"\r\n", b"\n")).hexdigest())
    return pins


def build_case(actor_count: int, *, full_hp: bool = False) -> dict:
    require(type(actor_count) is int and 1 <= actor_count <= 3, "actor count outside domain")
    tiles = []
    for x in range(8):
        for y in range(8):
            tile = dict(x=x, y=y, terrain="ground" if 2 <= x <= 4 and 2 <= y <= 4 else "mountain")
            if (x, y) == (5, 3):
                tile.update(terrain="building", building_hp=1)
            elif tile["terrain"] == "mountain":
                tile["building_hp"] = 2
            tiles.append(tile)
    units = []
    for uid, (name, pos, maximum) in enumerate(STARTERS[:actor_count]):
        units.append(dict(uid=uid, type=name, x=pos[0], y=pos[1],
                          hp=maximum if full_hp else 1, max_hp=maximum,
                          team=1, mech=True, move=3, active=True, can_move=True,
                          flying=False, massive=True, armor=False, powered=True,
                          pushable=True, weapons=[]))
    units.append(dict(uid=99, type="Firefly1", x=2, y=3, hp=3, max_hp=3,
                      team=6, mech=False, move=3, active=False, can_move=True,
                      flying=False, massive=False, armor=False, powered=True,
                      pushable=True, weapons=["FireflyAtk1"],
                      has_queued_attack=True, queued_target=[5, 3]))
    # Labels are fixture identities, not engine identifiers. Canonicalize all
    # units by visible identity before feeding either search or the reference.
    units.sort(key=lambda u: (u["x"], u["y"], u["type"]))
    for label, unit in enumerate(units):
        unit["uid"] = label
    enemy = next(u for u in units if u["team"] == 6)
    return dict(tiles=tiles, units=units, attack_order=[enemy["uid"]],
                grid_power=7, grid_power_max=7, turn=1, total_turns=1,
                remaining_spawns=0, spawning_tiles=[])


def validate_domain(board: dict) -> tuple[int, ...]:
    """Fail closed to the declared fixture domain, including absent hazards."""
    require(type(board) is dict and set(board) == TOP_KEYS, "unknown or missing board fields")
    require(type(board["units"]) is list and type(board["tiles"]) is list, "invalid board arrays")
    require(all(type(u) is dict for u in board["units"]), "invalid unit objects")
    actors = [u for u in board["units"] if u.get("team") == 1]
    require(1 <= len(actors) <= 3 and len(board["units"]) == len(actors) + 1, "actor/roster domain differs")
    expected = build_case(len(actors))
    require(encode(board["tiles"]) == encode(expected["tiles"]), "terrain, tile status, or geometry outside domain")
    for key in TOP_KEYS - {"tiles", "units", "attack_order"}:
        require(type(board[key]) is type(expected[key]) and board[key] == expected[key], "boundary differs: " + key)
    require(all(type(u) is dict and set(u) <= UNIT_KEYS for u in board["units"]), "unknown unit fields")
    ids = [u.get("uid") for u in board["units"]]
    require(all(type(uid) is int and uid >= 0 for uid in ids) and len(set(ids)) == len(ids), "invalid unit identity")
    positions = [(u.get("x"), u.get("y")) for u in board["units"]]
    require(all(type(x) is int and type(y) is int for x, y in positions) and len(set(positions)) == len(positions), "invalid or duplicate position")
    templates = {u["type"]: u for u in expected["units"]}
    require(len({u["type"] for u in board["units"]}) == len(board["units"]), "duplicate actor type")
    for unit in board["units"]:
        require(unit.get("type") in templates, "unknown unit type")
        template = templates[unit["type"]]
        require(set(unit) == set(template), "missing or extra declared unit fields")
        if unit["team"] == 6:
            require(encode({k: v for k, v in unit.items() if k != "uid"}) == encode({k: v for k, v in template.items() if k != "uid"}), "enemy outside domain")
        else:
            for key in set(template) - {"uid", "x", "y", "hp", "can_move"}:
                require(type(unit[key]) is type(template[key]) and unit[key] == template[key], "actor feature outside domain: " + key)
            require(type(unit["hp"]) is int and 0 < unit["hp"] <= unit["max_hp"], "actor HP outside domain")
            require(type(unit["can_move"]) is bool, "invalid movement eligibility")
            require(2 <= unit["x"] <= 4 and 2 <= unit["y"] <= 4 and (unit["x"], unit["y"]) != (2, 3), "actor outside Ground arena")
    enemy = next(u for u in board["units"] if u["team"] == 6)
    require(type(board["attack_order"]) is list and encode(board["attack_order"]) == encode([enemy["uid"]]), "queued attack order differs")
    return tuple(sorted(u["uid"] for u in actors))


def destinations(board: dict, uid: int) -> tuple[tuple[int, int], ...]:
    """Independent BFS; never calls Rust legality, action generation, or pruning."""
    actor = next((u for u in board["units"] if u["uid"] == uid), None)
    require(actor is not None and actor["team"] == 1 and actor["hp"] > 0 and actor["active"], "actor unavailable")
    origin = (actor["x"], actor["y"])
    if not actor["can_move"]:
        return (origin,)
    terrain = {(t["x"], t["y"]): t["terrain"] for t in board["tiles"]}
    occupied = {(u["x"], u["y"]): u for u in board["units"] if u["hp"] > 0 and u["uid"] != uid}
    distance = {origin: 0}
    queue = deque([origin])
    stops = {origin}
    while queue:
        pos = queue.popleft()
        for dx, dy in NEIGHBORS:
            candidate = (pos[0] + dx, pos[1] + dy)
            cost = distance[pos] + 1
            if candidate in distance or cost > actor["move"]:
                continue
            if not (0 <= candidate[0] < 8 and 0 <= candidate[1] < 8):
                continue
            if terrain.get(candidate) != "ground":
                continue
            blocker = occupied.get(candidate)
            if blocker is not None and blocker["team"] != actor["team"]:
                continue
            distance[candidate] = cost
            queue.append(candidate)
            if blocker is None:
                stops.add(candidate)
    return tuple(sorted(stops))


def choices(board: dict, uid: int) -> Iterator[dict]:
    for pos in destinations(board, uid):
        # These are self-action encodings, not a restricted weapon target pool.
        yield dict(mech_uid=uid, move_to=list(pos), weapon_id=WAIT, target=[255, 255])
        yield dict(mech_uid=uid, move_to=list(pos), weapon_id=REPAIR, target=list(pos))


def advance(board: dict, action: dict) -> dict:
    result = deepcopy(board)
    actor = next(u for u in result["units"] if u["uid"] == action["mech_uid"])
    actor["x"], actor["y"] = action["move_to"]
    if action["weapon_id"] == REPAIR:
        actor["hp"] = min(actor["max_hp"], actor["hp"] + 1)
    # Independent completion tracking; score_plan's Wait does not clear ACTIVE.
    actor["active"] = False
    actor["can_move"] = False
    return result


@dataclass
class Counts:
    nodes: int = 0
    generated_choices: int = 0
    leaves_emitted: int = 0
    leaves_scored: int = 0
    reference_oracle_failures: int = 0
    orders: set[tuple[int, ...]] = field(default_factory=set)

    def report(self) -> dict:
        return dict(nodes=self.nodes, generated_choices=self.generated_choices,
                    raw_leaves_emitted=self.leaves_emitted, leaves_scored=self.leaves_scored,
                    reference_oracle_failures=self.reference_oracle_failures, actor_orders=len(self.orders),
                    semantic_deduplication=False, skipped_duplicate_leaves=0)


def plans(board: dict, counts: Counts) -> Iterator[list[dict]]:
    actors = validate_domain(board)

    def visit(current: dict, remaining: tuple[int, ...], prefix: list[dict]):
        counts.nodes += 1
        if not remaining:
            counts.leaves_emitted += 1
            counts.orders.add(tuple(a["mech_uid"] for a in prefix))
            yield prefix
            return
        for uid in remaining:
            for action in choices(current, uid):
                counts.generated_choices += 1
                yield from visit(advance(current, action), tuple(u for u in remaining if u != uid), prefix + [action])

    yield from visit(board, actors, [])


def validate_plan(board: dict, raw: list[dict]) -> list[dict]:
    remaining = set(validate_domain(board))
    require(type(raw) is list and len(raw) == len(remaining), "plan must include each actor once")
    current, normalized = board, []
    for action in raw:
        require(type(action) is dict, "invalid plan action")
        require(set(action) <= {"mech_uid", "mech_type", "move_to", "weapon", "weapon_id", "target", "target2", "description"}, "unknown action fields")
        require({"mech_uid", "move_to", "weapon_id", "target"} <= set(action), "action fields missing")
        uid = action["mech_uid"]
        require(type(uid) is int and uid in remaining, "duplicate or unknown actor")
        require(action.get("target2") is None, "secondary target outside domain")
        for key in ("move_to", "target"):
            require(type(action[key]) is list and len(action[key]) == 2 and all(type(v) is int for v in action[key]), "invalid coordinates: " + key)
        weapon = action["weapon_id"]
        require(type(weapon) is str and weapon in {WAIT, "None", "Unknown", REPAIR}, "equipped attack outside domain")
        item = {k: deepcopy(action[k]) for k in ("mech_uid", "move_to", "weapon_id", "target")}
        item["weapon_id"] = REPAIR if weapon == REPAIR else WAIT
        require(tuple(item["move_to"]) in destinations(current, uid), "independently illegal move")
        require(item["target"] == (item["move_to"] if item["weapon_id"] == REPAIR else [255, 255]), "invalid self-action target")
        normalized.append(item)
        current = advance(current, item)
        remaining.remove(uid)
    return normalized


def oracle_result(score_plan: Callable, board_json: str, plan: list[dict]) -> dict:
    result = json.loads(score_plan(board_json, encode(plan)))
    require(type(result) is dict and type(result.get("illegal_events")) is list, "oracle legality receipt missing")
    require(not result["illegal_events"], "oracle rejected independent plan: " + str(result["illegal_events"]))
    require(type(result.get("score")) in (int, float) and math.isfinite(result["score"]), "oracle score nonfinite or missing")
    return result


def evaluate_case(board: dict, score_plan: Callable, solve: Callable, *, solver_budget: float,
                  reference_budget: float = 120.0, max_leaves: int = 20000,
                  tolerance: float = 1e-7) -> dict:
    require(all(type(v) in (int, float) and math.isfinite(v) for v in (solver_budget, reference_budget, tolerance))
            and solver_budget > 0 and reference_budget > 0
            and type(max_leaves) is int and max_leaves > 0 and tolerance >= 0,
            "invalid evaluation budget")
    counts = Counts()
    start = time.monotonic()
    result = dict(status="incomplete", reference_complete=False, root_best_found=False,
                  root_proof_status=None, matches_reference_best=False,
                  objective_parity_established=False,
                  selected_rescore_attempts=0, selected_rescore_completed=0,
                  selected_rescore_failures=0)
    best_score, best_plan, best_summary, ties = None, None, None, 0
    try:
        actors = validate_domain(board)
        upper_bound = math.factorial(len(actors)) * (2 * (9 - len(actors))) ** len(actors)
        result.update(actor_count=len(actors), leaf_upper_bound=upper_bound,
                      expected_actor_orders=math.factorial(len(actors)), input_sha256=sha256(encode(board).encode()).hexdigest())
        board_json = encode(board)
        for plan in plans(board, counts):
            require(counts.leaves_emitted <= max_leaves and time.monotonic() - start <= reference_budget,
                    "reference budget exhausted; traversal incomplete")
            try:
                summary = oracle_result(score_plan, board_json, plan)
            except Exception:
                counts.reference_oracle_failures += 1
                raise
            counts.leaves_scored += 1
            score = summary["score"]
            if best_score is None or score > best_score:
                best_score, best_plan, best_summary, ties = score, plan, summary, 1
            elif score == best_score:
                ties += 1
        require(time.monotonic() - start <= reference_budget, "reference budget expired before completion")
        require(0 < counts.leaves_scored == counts.leaves_emitted <= upper_bound,
                "reference leaf accounting incomplete")
        require(len(counts.orders) == math.factorial(len(actors)), "actor order coverage incomplete")
        result.update(reference_complete=True, reference_seconds=time.monotonic() - start,
                      exhaustive_best_score=best_score, exhaustive_best_plan=best_plan,
                      exhaustive_best_current_evaluation=best_summary, exact_best_score_ties=ties)
        solution = json.loads(solve(board_json, solver_budget))
        require(type(solution) is dict and type(solution.get("score")) in (int, float)
                and math.isfinite(solution["score"]), "solver result/score invalid")
        selected = validate_plan(board, solution.get("actions"))
        result["selected_rescore_attempts"] = 1
        try:
            selected_summary = oracle_result(score_plan, board_json, selected)
        except Exception:
            result["selected_rescore_failures"] = 1
            raise
        result["selected_rescore_completed"] = 1
        regret = best_score - selected_summary["score"]
        require(regret >= -tolerance, "selected score exceeds exhaustive reference; oracle/domain differs")
        parity = abs(solution["score"] - selected_summary["score"]) <= tolerance
        result.update(status="complete" if parity else "objective_mismatch", selected_plan=selected,
                      selected_current_evaluation=selected_summary,
                      solver_reported_score=solution["score"],
                      solver_reported_minus_rescored=solution["score"] - selected_summary["score"],
                      objective_parity_established=parity,
                      regret=regret, comparison_tolerance=tolerance,
                      root_best_found=parity, root_proof_status="best_found",
                      matches_reference_best=abs(regret) <= tolerance,
                      certificate=None, valid_bounds=None, horizon_player_turns=1,
                      solver_stats=solution.get("stats"), solver_budget_seconds=solver_budget)
    except Exception as exc:
        result.update(reason=str(exc), status="failed" if result["reference_complete"] else "incomplete")
    result.update(counts=counts.report(), total_seconds=time.monotonic() - start)
    # A partial traversal may retain a useful diagnostic, but never an optimum.
    if not result["reference_complete"]:
        result.update(partial_best_score=best_score, partial_best_plan=best_plan)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-simulator-version", type=int, required=True)
    parser.add_argument("--solver-budget", type=float, default=10.0)
    parser.add_argument("--reference-budget", type=float, default=120.0)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output is create-only")
    import itb_solver
    from scripts.solver_first_s0 import loaded_extension_path
    require(itb_solver.simulator_version() == args.expected_simulator_version, "installed model version differs")
    source_hashes = source_pins()
    extension_path = loaded_extension_path(itb_solver)
    extension_hash = sha256(extension_path.read_bytes()).hexdigest()
    cases = []
    for count, full_hp in ((1, False), (2, False), (3, False), (3, True)):
        board = build_case(count, full_hp=full_hp)
        result = evaluate_case(board, itb_solver.score_plan, itb_solver.solve,
                               solver_budget=args.solver_budget, reference_budget=args.reference_budget)
        cases.append(dict(id=f"disarmed_{count}_{'full_hp' if full_hp else 'wounded'}", input=board, **result))
    stable_sources = source_hashes == source_pins()
    stable_extension = extension_hash == sha256(extension_path.read_bytes()).hexdigest()
    matched = stable_sources and stable_extension and all(c["status"] == "complete" and c["objective_parity_established"] and c["matches_reference_best"] for c in cases)
    report = dict(schema_version=1, evidence_class="synthetic_independent_enumeration_shared_Rust_model",
                  root_proof_status="best_found" if all(c["root_best_found"] for c in cases) else None,
                  reference_regret_status="matched_reference_best" if matched else "not_established",
                  certificate=None, valid_bounds=None, horizon_player_turns=1,
                  claim="Conditional search-only regret over this bounded composite turn domain and current Rust transition/evaluation oracle.",
                  action_contract="One complete movement-before-Wait/Repair choice per actor, every actor order; no after-action movement, repeated actors, pilots, hazards or equipped attacks.",
                  interleaving_reduction="Self Repair/Wait cannot alter another actor's position/path eligibility in this domain; each self action commutes next to its own movement. All movement orders remain enumerated.",
                  wait_model_boundary="score_plan leaves ACTIVE true for Wait; independent actor completion prevents duplicates. Replay's explicit skip endpoint differs. No Wait/Repair semantic deduplication.",
                  objective_configuration="Frozen current Rust default EvalWeights, identified by extension bytes and inspected source hashes; no state-supplied weights or overlays.",
                  source_hashes=source_hashes, checkout_sources_unchanged=stable_sources,
                  source_binding_scope="Checkout snapshots identify inspected source; they do not independently attest extension build linkage.",
                  extension_sha256=extension_hash, extension_file_unchanged=stable_extension,
                  simulator_version=itb_solver.simulator_version(), python_runtime=list(sys.version_info[:3]),
                  reference_complete_cases=sum(c["reference_complete"] for c in cases),
                  reference_leaf_scores=sum(c["counts"]["leaves_scored"] for c in cases),
                  original_runtime_comparisons=0, fair_archive_admissions=0, held_out_evaluations=0,
                  campaign_evaluations=0, ledger_promotions=0, cases=cases)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(report, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")
    print(encode({k: report[k] for k in ("root_proof_status", "reference_regret_status", "reference_complete_cases", "reference_leaf_scores")}))
    return 0 if matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
