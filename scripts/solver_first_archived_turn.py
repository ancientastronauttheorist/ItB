#!/usr/bin/env python3
"""Replay sealed historical controls offline; report narrow original projections."""
from __future__ import annotations

import argparse
import faulthandler
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.private_output_dir.exists():
        parser.error("Outputs are create-only")
    faulthandler.disable()
    from scripts.solver_first_s0 import loaded_extension_path
    from src.observatory.solver_first_archived_turn import ROOT, compare_projection, digest, load_trials, require
    from src.solver.observation_contract import ObservationBoundaryError, player_observation
    import itb_solver

    require(itb_solver.simulator_version() == 409, "frozen diagnostic baseline requires simulator409")
    trials, source_pins = load_trials()
    args.private_output_dir.mkdir(parents=True)
    cases, failures = [], []
    for trial in trials:
        try:
            player_observation(trial["before"])
            fair = dict(status="admitted")
        except ObservationBoundaryError as exc:
            fair = dict(status="rejected", reason=str(exc))
        try:
            replay = json.loads(itb_solver.replay_solution(json.dumps(trial["before"]), json.dumps(trial["plan"])))
            with (args.private_output_dir / (trial["id"] + ".json")).open("x", encoding="utf-8", newline="\n") as out:
                json.dump(replay, out, indent=2, allow_nan=False)
                out.write("\n")
            comparison = compare_projection(trial["before"], replay["final_board"], trial["actual"])
            cases.append(dict(id=trial["id"], fair_input=fair, comparison=comparison,
                              recorded_plan=trial["plan"], input_timestamp=trial["input_timestamp"],
                              plan_timestamp=trial["plan_timestamp"], trial_timestamp=trial["trial_timestamp"],
                              raw_outcome_timestamp=trial["raw_outcome_timestamp"], original_simulator_version=trial["original_simulator_version"],
                              acknowledgements={k: trial[k] for k in ("delivery_confirmation", "end_turn_ack", "prepare_ack", "finish_ack")},
                              canonical_input_sha256=digest(json.dumps(trial["before"], sort_keys=True, separators=(",", ":")).encode()),
                              raw_replay_sha256=digest((args.private_output_dir / (trial["id"] + ".json")).read_bytes())))
        except Exception as exc:
            failures.append(dict(id=trial["id"], reason=str(exc), fair_input=fair))
    report = dict(schema_version=1, corpus_version="s1-archived-capsule-development-v1",
                  evidence_class="archived_original_game_turn_with_partial_oracle_diagnostic_replay",
                  original_build_sha256="31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9",
                  capture_track="owner_local_modified", simulator_version=itb_solver.simulator_version(),
                  solver_baseline_commit="77356e13d344bd639899cb5c6653784732c5d60d",
                  information_mode="historical_oracle_diagnostic_only_no_planner_invocation",
                  independent_scenario_families=1, original_cycle_outcome_snapshots=3,
                  diagnostic_replays_attempted=len(trials), diagnostic_replays_completed=len(cases),
                  projection_checks=sum(c["comparison"]["checks_attempted"] for c in cases),
                  projection_mismatches=sum(len(c["comparison"]["mismatches"]) for c in cases),
                  aligned_projection_admissions=sum(c["comparison"]["next_decision_ready"] for c in cases),
                  alignment_rejections=sum(not c["comparison"]["next_decision_ready"] for c in cases),
                  aligned_projection_checks=sum(c["comparison"]["checks_attempted"] for c in cases if c["comparison"]["next_decision_ready"]),
                  aligned_projection_mismatches=sum(len(c["comparison"]["mismatches"]) for c in cases if c["comparison"]["next_decision_ready"]),
                  fair_input_admissions=sum(c["fair_input"]["status"] == "admitted" for c in cases),
                  full_state_equivalence_admissions=0, legal_action_set_comparisons=0, ordered_event_comparisons=0,
                  ledger_promotions=0, search_evaluations=0, held_out_evaluations=0,
                  partition="entire related capsule campaign is development; no sibling control/dormant/armed trial is held out",
                  model_boundary="Rust simulates player actions/queued attacks and stationary heuristic requeue; actual next decision additionally contains original enemy movement, egg creation/webbing and spawn scheduling",
                  input_boundary="Historical full bridge/save/overlay/configuration payload is replayed as an oracle diagnostic; pending and hidden fields have not been admitted to fair planning",
                  intervention="Control observer unarmed; native RNG explicitly reseeded after player actions, before End Turn. This is not an unseeded or pristine-depot gameplay claim.",
                  exclusions=["individual action delivery ACKs", "complete actual post-player Board", "ordered original damage/status events",
                              "enemy movement/target policy and new spawn forecast", "nonempty environmental effect",
                              "live grid scalar/resistance outcome (bridge reads save/fallback)", "absent tile-status getter success",
                              "actual effective weapon/max-HP/move reconciliation at next decision", "fair-input provenance", "held-out practical strength or exhaustive search"],
                  source_pins=source_pins,
                  acquisition_source_sha256={p: digest((ROOT / p).read_bytes()) for p in ("scripts/solver_first_archived_turn.py", "src/observatory/solver_first_archived_turn.py", "src/solver/observation_contract.py", "scripts/solver_first_s0.py")},
                  information_contract_sha256=digest((ROOT / "data/solver_first/s0_information_contract.json").read_bytes()),
                  extension_sha256=digest(loaded_extension_path(itb_solver).read_bytes()),
                  python_runtime=list(sys.version_info[:3]),
                  cases=cases, failures=failures)
    with args.output.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(report, out, indent=2, sort_keys=True, allow_nan=False)
        out.write("\n")
    print(json.dumps({k: report[k] for k in ("diagnostic_replays_attempted", "diagnostic_replays_completed", "projection_checks", "projection_mismatches", "aligned_projection_admissions", "alignment_rejections", "aligned_projection_mismatches", "fair_input_admissions", "full_state_equivalence_admissions")}))
    return 1 if failures or report["projection_mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
