#!/usr/bin/env python3
"""Source-shaped player AOE regressions and a single-actor search reference.

Synthetic development only: independent targeting/enumeration, shared Rust
transition and scoring. No original execution or complete tactical-loop claim.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.solver_first_bounded_search import encode, require, source_pins

VARIANTS = {"Brute_Splitshot": (2, 1), "Brute_Splitshot_A": (2, 2),
            "Brute_Splitshot_B": (3, 1), "Brute_Splitshot_AB": (3, 2)}
ARTEMIS = ("Ranged_Artillerymech", "Ranged_Artillerymech_A")
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
EVIDENCE = ROOT / "data/solver_first/s1_player_aoe_411_evidence.json"


def unit(uid, name, pos, hp, team, weapon, *, active=False, queued=None):
    item = dict(uid=uid, type=name, x=pos[0], y=pos[1], hp=hp, max_hp=hp,
                team=team, mech=team == 1, move=3, active=active,
                can_move=False, massive=team == 1, flying=False, armor=False,
                powered=True, pushable=True, weapons=[weapon])
    if queued is not None:
        item.update(has_queued_attack=True, queued_target=list(queued))
    return item


def board_base(terrain):
    return dict(tiles=[dict(x=x, y=y, terrain=terrain) for x in range(8) for y in range(8)],
                units=[], attack_order=[], grid_power=7, grid_power_max=7,
                turn=1, total_turns=1, remaining_spawns=0,
                spawning_tiles=[])


def tile(board, pos):
    return next(t for t in board["tiles"] if (t["x"], t["y"]) == tuple(pos))


def action(weapon, origin, target):
    return dict(mech_uid=0, move_to=list(origin), weapon_id=weapon, target=list(target))


def splitshot_case(weapon, direction):
    require(weapon in VARIANTS and direction in DIRECTIONS, "unknown Split Shot fixture")
    dx, dy = direction
    board = board_base("ground")
    origin = (3 - 2 * dx, 3 - 2 * dy)
    positions = ((3, 3), (3 + dy, 3 - dx), (3 - dy, 3 + dx),
                 (3 + dx + dy, 3 + dy - dx))
    board["units"] = [unit(0, "TankMech", origin, 3, 1, weapon, active=True)]
    board["units"] += [unit(uid, "Firefly2", pos, 5, 6, "FireflyAtk2")
                       for uid, pos in enumerate(positions, 1)]
    plan = [action(weapon, origin, (origin[0] + dx, origin[1] + dy))]
    damage = VARIANTS[weapon][0]
    expected = {1: dict(x=3 + dx, y=3 + dy, hp=5 - damage),
                2: dict(x=3 + 2 * dy, y=3 - 2 * dx, hp=5 - damage),
                3: dict(x=3 - 2 * dy, y=3 + 2 * dx, hp=5 - damage),
                4: dict(x=positions[3][0], y=positions[3][1], hp=5)}
    return board, plan, expected


def artemis_case(weapon):
    require(weapon in ARTEMIS, "unsupported Artemis fixture")
    board = board_base("chasm")
    for pos in ((3, 6), (3, 2), (2, 3)):
        tile(board, pos)["terrain"] = "ground"
    for pos, hp in (((3, 3), 1), ((3, 0), 2), ((0, 3), 2)):
        tile(board, pos).update(terrain="building", building_hp=hp)
    board["units"] = [unit(0, "ArtiMech", (3, 6), 2, 1, weapon, active=True),
                      unit(1, "Firefly2", (3, 2), 5, 6, "FireflyAtk2", queued=(3, 0)),
                      unit(2, "Firefly2", (2, 3), 5, 6, "FireflyAtk2", queued=(0, 3))]
    board.update(attack_order=[1, 2], grid_power=2)
    return board


def artemis_plans(board):
    """Independent source target law: valid cardinal tile at distance >= 2.

    Strict fixture equality bounds this to one actor whose move was spent.
    There are no primitive interleavings with another actor in this domain.
    Full-HP Repair is retained as a legal distinct choice, as is Wait.
    """
    require(type(board) is dict and type(board.get("units")) is list
            and len(board["units"]) == 3, "roster outside reference domain")
    weapons = board["units"][0].get("weapons")
    require(type(weapons) is list and len(weapons) == 1 and weapons[0] in ARTEMIS,
            "weapon outside reference domain")
    weapon = weapons[0]
    require(encode(board) == encode(artemis_case(weapon)), "board outside reference domain")
    origin = (3, 6)
    for x in range(8):
        for y in range(8):
            if (x == origin[0] or y == origin[1]) and abs(x - origin[0]) + abs(y - origin[1]) >= 2:
                yield [action(weapon, origin, (x, y))]
    yield [action("", origin, (255, 255))]
    yield [action("_REPAIR", origin, origin)]


def checked_result(native, board, plan):
    scored = json.loads(native.score_plan(encode(board), encode(plan)))
    require(type(scored.get("illegal_events")) is list and not scored["illegal_events"],
            "shared model rejected independently enumerated action")
    require(type(scored.get("score")) in (int, float) and math.isfinite(scored["score"]),
            "missing/nonfinite score")
    replay = json.loads(native.replay_solution(encode(board), encode(plan)))
    require(len(replay["action_results"]) == len(replay["predicted_states"]) == len(plan),
            "incomplete replay receipts")
    for result, snapshots in zip(replay["action_results"], replay["predicted_states"]):
        require(not any(e.startswith("illegal_") for e in result["events"]), "illegal replay event")
        for phase in ("post_move", "post_attack"):
            require("error" not in snapshots[phase], "error replay snapshot")
    require(type(replay["post_player_board"]) is dict and type(replay["final_board"]) is dict,
            "missing replay boards")
    return scored, replay


def assert_splitshot_projection(replay, expected):
    units = {u["uid"]: u for u in replay["post_player_board"]["units"]}
    for uid, values in expected.items():
        require(uid in units and all(units[uid][key] == value for key, value in values.items()),
                "Split Shot damage/push/saved-endpoint projection differs")


def clean_player_plan(board, replay):
    before = sum(t.get("building_hp", 0) > 0 and t["terrain"] == "building" for t in board["tiles"])
    after = sum(t.get("building_hp", 0) > 0 and t["terrain"] == "building"
                for t in replay["post_player_board"]["tiles"])
    return (before == after and all(r["buildings_damaged"] == 0 and r["buildings_lost"] == 0
                                   for r in replay["action_results"]))


def evaluate_artemis(native, weapon, budget):
    board = artemis_case(weapon)
    leaves = []
    for plan in artemis_plans(board):
        scored, replay = checked_result(native, board, plan)
        leaves.append(dict(plan=plan, score=scored["score"], clean=clean_player_plan(board, replay)))
    require(len(leaves) == 12, "reference cardinality differs")
    raw = max(leaves, key=lambda leaf: leaf["score"])
    clean = max((leaf for leaf in leaves if leaf["clean"]), key=lambda leaf: leaf["score"])
    threshold = max(abs(raw["score"]) * 0.05, 500.0)
    best = clean if raw["score"] - clean["score"] <= threshold else raw
    solution = json.loads(native.solve(encode(board), budget))
    require(solution["proof_status"] == "best_found" and solution["certificate"] is None
            and solution["valid_bounds"] is None, "unexpected unsubstantiated certificate")
    selected = [{k: a[k] for k in ("mech_uid", "move_to", "weapon_id", "target")}
                for a in solution["actions"]]
    # Exact leaf membership is an independent legality check; no dropping of
    # failed reference actions or unknown production encodings is permitted.
    require(encode(selected) in {encode(leaf["plan"]) for leaf in leaves}, "selected plan outside reference")
    scored, replay = checked_result(native, board, selected)
    require(abs(solution["score"] - scored["score"]) <= 1e-7, "objective parity differs")
    regret = best["score"] - scored["score"]
    require(abs(regret) <= 1e-7, "selected score differs from complete single-actor reference")
    require(selected[0]["target"] == [3, 3], "building-saving decision differs")
    final = replay["final_board"]
    expected_grid = 1 if weapon == ARTEMIS[0] else 2
    require(final["grid_power"] == expected_grid, "grid projection differs")
    for pos in ((3, 0), (0, 3)):
        require(tile(final, pos)["building_hp"] == 2, "protected building damaged")
    require(tile(final, (3, 3)).get("building_hp", 0) == (0 if weapon == ARTEMIS[0] else 1),
            "center building projection differs")
    return dict(id=weapon, input=board, reference_complete=True, reference_leaves=len(leaves),
                leaves=leaves, raw_best=raw, clean_best=clean, clean_threshold=threshold,
                reference_policy_best=best, selected_plan=selected, selected_evaluation=scored,
                final_projection=dict(grid_power=final["grid_power"], buildings_alive=scored["bldgs_alive"]),
                regret=regret, objective_parity=True, solver_stats=solution["stats"],
                proof_status="best_found", certificate=None, valid_bounds=None)


def pins():
    result = source_pins()
    for path in ("scripts/solver_first_player_aoe.py", "src/model/weapons.py", "src/solver/verify.py",
                 "rust_solver/src/replay.rs", "rust_solver/src/turn_projection.rs",
                 "data/solver_first/s1_player_aoe_411_evidence.json"):
        raw = (ROOT / path).read_bytes()
        result[path] = dict(raw_sha256=sha256(raw).hexdigest(),
                            lf_sha256=sha256(raw.replace(b"\r\n", b"\n")).hexdigest())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output is create-only")
    import itb_solver
    from scripts.solver_first_s0 import loaded_extension_path
    from src.solver.verify import SIMULATOR_VERSION
    require(itb_solver.simulator_version() == SIMULATOR_VERSION == 411, "installed model version differs")
    source_before = pins()
    extension = loaded_extension_path(itb_solver)
    extension_hash = sha256(extension.read_bytes()).hexdigest()
    cases = []
    for weapon in VARIANTS:
        for direction in DIRECTIONS:
            board, plan, expected = splitshot_case(weapon, direction)
            scored, replay = checked_result(itb_solver, board, plan)
            assert_splitshot_projection(replay, expected)
            cases.append(dict(weapon_id=weapon, direction=direction, input=board, plan=plan,
                              expected_post_player_units=expected, matched=True, score=scored["score"]))
    artemis = [evaluate_artemis(itb_solver, weapon, 10.0) for weapon in ARTEMIS]
    require(source_before == pins(), "checkout sources changed during comparison")
    require(extension_hash == sha256(extension.read_bytes()).hexdigest(), "extension changed during comparison")
    report = dict(schema_version=1, simulator_version=411,
                  evidence_class="synthetic_source_targeting_independent_enumeration_shared_Rust_model",
                  root_proof_status="best_found", certificate=None, valid_bounds=None,
                  horizon_player_turns=1, solver_budget_seconds=10.0,
                  objective="Pinned Rust default EvalWeights and player-building clean postfilter (5% or 500); default 15% expected grid-save credit, no original resistance draw.",
                  information_mode="synthetic visible fixtures; no archived fair-input admission",
                  reference_domain="Single Artemis actor, movement spent, 10 cardinal shots plus Wait and full-HP Repair; fixed Chasm terrain, no environment hazards/modifiers, pilots, spawns or mission modifiers.",
                  grid_defense_configuration=dict(effective_model_percent=15,
                      scope="Rust Board default; parser has no grid-defense input. Recorded before receipt's grid_defense=0 was also ignored. Actual resistance RNG is not modeled or admitted."),
                  reference_boundary="Independent target enumeration; shared Rust transitions and scoring. No multi-actor primitive-interleaving reduction.",
                  source_binding_scope="Inspected checkout hashes; not independent attestation of extension build linkage.",
                  source_hashes=source_before, checkout_sources_unchanged=True,
                  extension_sha256=extension_hash, extension_file_unchanged=True,
                  python_runtime=list(sys.version_info[:3]), splitshot_cases=cases, artemis_cases=artemis,
                  splitshot_projections_matched=len(cases), reference_leaf_scores=sum(c["reference_leaves"] for c in artemis),
                  original_runtime_comparisons=0, fair_archive_admissions=0, held_out_evaluations=0,
                  campaign_evaluations=0, ledger_promotions=0)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(report, output, sort_keys=True, indent=2, allow_nan=False)
        output.write("\n")
    print(encode({k: report[k] for k in ("simulator_version", "splitshot_projections_matched", "reference_leaf_scores", "root_proof_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
