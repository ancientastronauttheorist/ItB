#!/usr/bin/env python3
"""Full-click exhaustive reference and representative reduction over the pinned fixture.

Original query acquisition is a separate process consuming this report's cases.
Rust supplies transitions/scoring; Python supplies every 64-tile classification.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import solver_first_primitive_search as ref


def target_area(board, uid):
    """Classify every coordinate independently; never call Rust generation."""
    actor = ref.unit_by_uid(board, uid)
    x, y = actor["x"], actor["y"]
    tiles = {(t["x"], t["y"]): t["terrain"] for t in board["tiles"]}
    blocked = {pos for pos, terrain in tiles.items() if terrain in ("building", "mountain")}
    for unit in board["units"]:
        if ref.alive(unit) or (unit["hp"] <= 0 and (unit.get("corpse") is True
                or unit.get("corpse_on_death") is True
                or (unit.get("team") == 1 and unit.get("mech") is True))):
            blocked.add((unit["x"], unit["y"]))
    result = []
    for tx in range(8):
        for ty in range(8):
            distance = abs(tx - x) + abs(ty - y)
            if distance == 0 or (tx != x and ty != y):
                continue
            if uid == 1:
                if distance == 1:
                    result.append([tx, ty])
                continue
            dx, dy = (tx > x) - (tx < x), (ty > y) - (ty < y)
            if not any((x + dx * n, y + dy * n) in blocked for n in range(1, distance)):
                result.append([tx, ty])
    return result


def all_closing_choices(board, uid):
    weapon = {0: "Brute_Tankmech", 1: "Prime_Punchmech"}[uid]
    for target in target_area(board, uid):
        yield dict(kind="use", mech_uid=uid, weapon_id=weapon, target=target)
    for step in ref.closing_choices(board, uid):
        if step.get("weapon_id") != weapon:
            yield step


def query_case(board, uid):
    """Only native-query inputs; HP sign normalization is explicit in the report."""
    units = []
    for unit in sorted(board["units"], key=lambda u: u["uid"]):
        units.append(dict(uid=unit["uid"], x=unit["x"], y=unit["y"],
            hp=1 if ref.alive(unit) else 0, team=unit["team"], mech=unit.get("mech") is True,
            source_corpse=unit.get("corpse") is True or unit.get("corpse_on_death") is True))
    actor = ref.unit_by_uid(board, uid)
    return dict(origin=[actor["x"], actor["y"]], range=2147483647 if uid == 0 else 1,
                corners=False, tiles=sorted(board["tiles"], key=lambda t: (t["x"], t["y"])),
                units=units, expected_targets=target_area(board, uid))


class Audit:
    def __init__(self, board, replay, inspect):
        self.initial = ref.encode(board)
        self.replay, self.inspect = replay, inspect
        self.prefixes = self.actor_prefixes = self.tile_classifications = 0
        self.legal_acceptances = self.illegal_rejections = self.equivalence_checks = 0
        self.queries, self.failure = {}, None

    def observe(self, steps, summary):
        self.prefixes += 1
        state, ledger = summary["post_player_board"], ref.prefix_entitlements(steps)
        for uid in ref.ACTORS:
            actor = ref.unit_by_uid(state, uid)
            if not ref.alive(actor) or ledger[uid]["used"]:
                continue
            self.actor_prefixes += 1
            weapon = {0: "Brute_Tankmech", 1: "Prime_Punchmech"}[uid]
            expected = target_area(state, uid)
            inspected = json.loads(self.inspect(ref.encode(state), uid, weapon))
            ref.require(sorted(inspected["targets"]) == sorted(expected), "target-area membership mismatch")
            ref.require(sorted(inspected["search_representatives"]) == sorted(
                [s["target"] for s in ref.closing_choices(state, uid) if s.get("weapon_id") == weapon]),
                "production representatives differ from independent directions")
            case = query_case(state, uid)
            key = sha256(ref.encode(case).encode()).hexdigest()
            if key not in self.queries:
                self.queries[key] = dict(id=key, query=case,
                    representative_prefix_sha256=sha256(ref.encode(steps).encode()).hexdigest())
            outcomes = {}
            legal_set = {tuple(point) for point in expected}
            for tx in range(8):
                for ty in range(8):
                    self.tile_classifications += 1
                    step = dict(kind="use", mech_uid=uid, weapon_id=weapon, target=[tx, ty])
                    if (tx, ty) not in legal_set:
                        try:
                            self.replay(self.initial, ref.encode(steps + [step]))
                        except ValueError as exc:
                            ref.require(str(exc) == "invalid_weapon_target", "unexpected negative-target rejection")
                            self.illegal_rejections += 1
                        else:
                            raise ref.ReferenceError("illegal click accepted by primitive replay")
                        continue
                    outcome = ref.project(self.replay, self.initial, steps + [step], ref.Counts())
                    ref.require(type(outcome.get("model_internal_board")) is str
                                and type(outcome.get("objective_totals")) is dict,
                                "complete internal board/objective inspection missing")
                    self.legal_acceptances += 1
                    dx, dy = (tx > actor["x"]) - (tx < actor["x"]), (ty > actor["y"]) - (ty < actor["y"])
                    direction = (dx, dy)
                    if direction in outcomes:
                        ref.require(outcome == outcomes[direction],
                                    "same-direction complete state/event/objective reduction mismatch")
                        self.equivalence_checks += 1
                    else:
                        outcomes[direction] = outcome

    def counts(self):
        return dict(prefixes_observed=self.prefixes, ready_actor_prefixes=self.actor_prefixes,
                    coordinates_classified=self.tile_classifications, legal_click_acceptances=self.legal_acceptances,
                    illegal_click_rejections=self.illegal_rejections,
                    complete_projection_equivalence_checks=self.equivalence_checks,
                    unique_original_query_requests=len(self.queries))


def run(solver, *, reference_budget=600.0, max_nodes=1000000, solver_budget=10.0):
    board = ref.build_case()
    replay = lambda j, s: solver.replay_primitives(j, s, True)
    audit = Audit(board, replay, solver.inspect_base_target_area)
    full, members = ref.reference(board, replay, reference_budget=reference_budget, max_nodes=max_nodes,
                                  closing_generator=all_closing_choices, prefix_observer=audit.observe)
    reduced, _ = ref.reference(board, replay, reference_budget=reference_budget, max_nodes=max_nodes)
    compound, _ = ref.reference(board, replay, compound=True, reference_budget=reference_budget,
                                max_nodes=max_nodes, closing_generator=all_closing_choices)
    result = dict(full_click_reference=full, reduced_direction_reference=reduced,
                  full_click_compound_reference=compound, audit=audit.counts(),
                  original_query_requests=list(audit.queries.values()), status="incomplete",
                  reference_budget_seconds=reference_budget, max_nodes=max_nodes)
    if not (full["complete"] and reduced["complete"] and compound["complete"]):
        return result
    selected = json.loads(solver.solve_primitives(ref.encode(board), solver_budget))
    ref.require(ref.encode(selected["steps"]) in members, "production selected outside full-click pool")
    summary = ref.project(replay, ref.encode(board), selected["steps"], ref.Counts())
    ref.require(summary["complete"] and selected["proof_status"] == "best_found"
                and selected["certificate"] is None and selected["valid_bounds"] is None,
                "production proof contract mismatch")
    ref.require(selected["score"] == summary["score"], "production replay score mismatch")
    for key in ("raw_best", "clean_best", "policy_best"):
        ref.require(full[key]["score"] == reduced[key]["score"]
                    and full[key]["clean"] == reduced[key]["clean"], "full/reduced objective mismatch")
    ref.require(selected["score"] == full["policy_best"]["score"]
                and summary["clean"] == full["policy_best"]["clean"], "production reference regret")
    result.update(status="complete", production=selected, production_member_of_full_pool=True,
                  matches_full_reference_policy=True, direction_reduction_matches=True,
                  raw_regret=full["raw_best"]["score"]-selected["score"],
                  policy_regret=full["policy_best"]["score"]-selected["score"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-budget", type=float, default=600.0)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output is create-only")
    import faulthandler
    faulthandler.disable()
    import itb_solver
    from scripts.solver_first_s0 import loaded_extension_path
    ref.require(itb_solver.simulator_version() == 413, "requires simulator v413")
    baseline_raw = (ROOT / ref.BASELINE).read_bytes()
    ref.require(sha256(baseline_raw).hexdigest() == ref.BASELINE_SHA, "pinned old baseline differs")
    baseline = json.loads(baseline_raw)
    ref.require(ref.encode(baseline["input"]) == ref.encode(ref.build_case()), "fixture differs from old baseline")
    paths = ref.SOURCES + ("scripts/solver_first_target_completeness.py", "tests/test_solver_first_target_area.py")
    pins = {p: sha256((ROOT / p).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in paths}
    extension = loaded_extension_path(itb_solver)
    ext_hash = sha256(extension.read_bytes()).hexdigest()
    result = run(itb_solver, reference_budget=args.reference_budget)
    ref.require(pins == {p: sha256((ROOT / p).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in paths}
                and ext_hash == sha256(extension.read_bytes()).hexdigest(), "evaluation pins changed")
    report = dict(schema_version=1, corpus_version="s2-full-base-click-development-413-v1",
        evidence_class="independent_full_click_reference_shared_Rust_transitions_and_scoring",
        baseline_commit="f645e6be7fd68200c7d8d0709cd861924e8c83c7", simulator_version=413,
        original_baseline_receipt_sha256=ref.BASELINE_SHA,
        extension_sha256=ext_hash, source_lf_sha256=pins, input=ref.build_case(),
        information_mode="synthetic_development_not_fair_input_admitted",
        objective="frozen shared terminal objective and clean-selection policy; one player turn",
        supplied_query_normalization="HP positive->1/nonpositive->0 for query signature only; original IsDead depends on sign. Lifecycle0/commonPawn/sourceCorpse are supplied premises; no original death continuity.",
        original_query_execution="pending separate original-body oracle process",
        original_completed_action_transitions=0, full_turn_original_comparisons=0,
        held_out_cases=0, gate_promotions=0, ledger_promotions=0,
        certificate=None, valid_bounds=None, case=result)
    with args.output.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(report, out, indent=2, sort_keys=True, allow_nan=False)
        out.write("\n")
    print(ref.encode(dict(status=result["status"], **result["audit"])))
    return int(result["status"] != "complete")


if __name__ == "__main__":
    raise SystemExit(main())
