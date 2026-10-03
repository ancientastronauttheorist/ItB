#!/usr/bin/env python3
"""Compare original coordinate/arrival stages; retain the unresolved full route."""
from __future__ import annotations

import argparse
import faulthandler
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def acquire(executable, private_dir):
    import itb_solver
    from scripts.solver_first_s0 import corridor, loaded_extension_path
    from src.solver.observation_contract import encode_observation
    from src.observatory.solver_first_path_oracle import (
        BOARD, HEAP, Machine, OriginalSource, recipes, require, runtime_identity, sha,
    )

    source = OriginalSource(executable)
    # Source-backed data identities for constructed idle and empty-pilot objects.
    for rva, size, digest in [
        (0x42e11c, 24, "3fe875c430c03e05291d09a05d04083c949dedd63061566bf3fb57c5024e2e9d"),
        (0x42b804, 8, "8d92a86ccf8dd030d281dc6ebb9cccecbcf39e6811d05e73e88d9f4c02c9643d"),
        (0x435dcc, 20, "1121ae7316942f849384eebe16569a22928bda57262c3fce7fd5b756ff207c37"),
    ]:
        offset = source.image.rva_to_file_offset(rva)
        require(offset is not None and sha(source.data[offset:offset + size]) == digest, "object vtable differs")

    def make(massive=True, water=True):
        m = Machine(source)
        recipe = dict(recipes()[2], water=water)
        m.fixture(recipe)
        m.call(0x3030, [])
        pawn, definition, control = BOARD + 0x100000, BOARD + 0x110000, BOARD + 0x113000
        m.put(pawn + 0x944, BOARD)
        m.put(pawn + 0x874, definition)
        m.put(pawn + 0x1168, 0x7fffffff)
        m.uc.mem_write(pawn + 0x99d, bytes([int(massive)]))
        setup = m.call(0x15dfb0, [], receiver=pawn + 0xa74)
        pilot = control + 12
        m.put(pawn + 0xa6c, pilot); m.put(pawn + 0xa70, control)
        m.put(control, 0x82b804); m.put(control + 4, 1); m.put(control + 8, 1)
        m.put(pilot, 0x835dcc); m.put(pilot + 0x74, 15)
        flying = m.call(0x23e490, [], receiver=pawn)
        require(m.uc.reg_read(m.x.UC_X86_REG_EAX) & 255 == 0, "supplied grounded ability state differs")
        require([m.get(control + 4), m.get(control + 8)] == [1, 1], "pilot ownership differs")
        return m, pawn, dict(embedded_constructor=setup, grounded_getter=flying,
                             world_sha256=sha(bytes(m.uc.mem_read(BOARD, 0x200000))))

    def snapshot(m, pawn):
        memberships = []
        for px in range(8):
            for py in range(8):
                tile = BOARD + 0x10000 + px * 8 * 0x2bbc + py * 0x2bbc
                begin, end, cap = [m.get(tile + off) for off in (0xa0, 0xa4, 0xa8)]
                require(begin <= end <= cap and (end - begin) % 4 == 0 and end - begin <= 4, "unexpected tile membership vector")
                if begin == 0:
                    require(end == cap == 0, "null membership header differs")
                elif HEAP <= begin < HEAP + 0x400000:
                    require(begin in m.live and cap <= begin + m.allocations[begin], "membership allocation ownership differs")
                for at in range(begin, end, 4):
                    require(m.get(at) == pawn, "unadmitted pawn in tile vector")
                    memberships.append([px, py])
        pos = [m.get(pawn + 0x8ec), m.get(pawn + 0x8f0)]
        require(memberships == [pos], "coordinate/membership conservation differs")
        control = m.get(pawn + 0xa70)
        counts = [m.get(control + 4), m.get(control + 8)]
        require(counts == [1, 1], "persistent pilot ownership differs after stage")
        return dict(position=pos, hp=m.get(pawn + 0x8a8), native_membership=memberships, native_pilot_refcounts=counts)

    def save(m, name):
        with (private_dir / (name + ".json")).open("x", encoding="utf-8", newline="\n") as out:
            json.dump(dict(trace=m.trace, imports=m.imports), out, indent=2)
            out.write("\n")

    result = dict(schema_version=1, corpus_version="s1-coordinate-arrival-development-v1",
                  evidence_class="bounded_original_stage_execution_with_supplied_world",
                  original_build_sha256=sha(source.data),
                  simulator_version=itb_solver.simulator_version(),
                  solver_baseline_commit="d26e94519fb15b14d1692a26169c9ffac8596b28",
                  extension_sha256=sha(loaded_extension_path(itb_solver).read_bytes()), runtime=runtime_identity(),
                  source_sha256={p: sha((ROOT / p).read_bytes()) for p in (
                      "scripts/solver_first_movement_stages.py", "src/observatory/solver_first_path_oracle.py",
                      "scripts/solver_first_s0.py", "src/solver/observation_contract.py", "src/observatory/pe_anchor_map.py")},
                  observation_contract_sha256=sha((ROOT / "data/solver_first/s0_information_contract.json").read_bytes()),
                  information_mode="provisional_player_observation_v1_offline_only",
                  graded_fields=["moving_pawn.position", "moving_pawn.hp"],
                  native_invariant="one tile membership agrees with the coordinate after every stage",
                  supplied_world=dict(
                      basis="query fixture plus mapped zeroed Pawn/definition/pilot storage; unmentioned bytes are supplied zeros",
                      pawn_fields={"+944": "Board pointer", "+874": "zeroed mapped definition", "+1168": "INT_MAX idle sentinel",
                                   "+99d": "recipe Massive byte", "+3c": "null detached base/render-grid", "+920": "zero",
                                   "+8d0/+8d1/+8d3": "zero Fire/Frozen/ACID", "+1314": "zero Pawn Flying flag",
                                   "+c6c/+c70/+c74": "empty extra-tile vector"},
                      pilot_fields="owner C: vtable82b804,strong/weak1/1; Q=C+12: vtable835dcc, empty Skill string length0/cap15, extra abilities0, power gate0; Pawn+a6c=Q/a70=C, alternate+980/+984 null",
                      executed_constructor="15dfb0 constructs only the embedded Pawn+a74 object; complete Pawn/pilot/definition loading is excluded"),
                  exclusions=["full route/animation/Lua execution", "action readiness/consumption", "ordered effects and status settlement",
                              "complete Pawn/Board update", "enemy/environment/spawn continuation", "full pilot/definition loading",
                              "nonnull base/render-grid attachment", "held-out or search evaluation"],
                  original_game_observations=0, full_turn_comparisons=0, ledger_promotions=0,
                  cases=[], failures=[], mismatches=[])
    cases = [
        dict(id="massive_water_adjacent", massive=True, water=True, budget=1, points=[[0, 1]]),
        dict(id="massive_water_ground", massive=True, water=True, budget=2, points=[[0, 1], [0, 2]]),
        dict(id="ground_ground_adjacent", massive=False, water=False, budget=1, points=[[0, 1]]),
        dict(id="ground_water_illegal_control", massive=False, water=True, budget=1, points=[[0, 1]]),
    ]
    for case in cases:
        row = dict(recipe=case, completed=False)
        m = None
        try:
            m, pawn, setup = make(case["massive"], case["water"])
            row["setup"] = setup
            out, target = BOARD + 0x1000, case["points"][-1]
            row["query"] = m.call(0x174180, [out, 0, 0, case["budget"], 18 if case["massive"] else 16])
            reachable = m.output(out)
            save(m, case["id"] + "_query")
            row.update(reachable=reachable, legal=target in reachable, before=snapshot(m, pawn), stages=[])
            if row["legal"]:
                for index, point in enumerate(case["points"]):
                    call = m.call(0x230320, point, receiver=pawn)
                    row["stages"].append(dict(kind="coordinate_writer", call=call, after=snapshot(m, pawn)))
                    save(m, case["id"] + "_writer_" + str(index))
                call = m.call(0x162140, target, receiver=BOARD)
                row["stages"].append(dict(kind="final_arrival", call=call, after=snapshot(m, pawn)))
                save(m, case["id"] + "_arrival")
            row["after"] = snapshot(m, pawn)
            state = corridor(case["massive"], case["budget"])
            if not case["water"]:
                next(t for t in state["tiles"] if t["x"] == 0 and t["y"] == 1)["terrain"] = "ground"
            clean = encode_observation(state)
            plan = [dict(mech_uid=0, move_to=target, weapon_id="None", target=target)]
            replay = json.loads(itb_solver.replay_solution(clean, json.dumps(plan)))
            actor = next(u for u in replay["predicted_states"][0]["post_move"]["units"] if u["uid"] == 0)
            legal = not any(e.startswith("illegal_move:") for e in replay["action_results"][0]["events"])
            row["rust"] = dict(legal=legal, position=actor["pos"], hp=actor["hp"], observation_sha256=sha(clean.encode()))
            if legal != row["legal"] or actor["pos"] != row["after"]["position"] or actor["hp"] != row["after"]["hp"]:
                result["mismatches"].append(case["id"])
            row["completed"] = True
        except Exception as exc:
            failure = dict(id=case["id"], reason=str(exc), partial=m.diagnostic() if m else None)
            result["failures"].append(failure)
            row["failure"] = failure
        result["cases"].append(row)

    # Keep the primary full-route case in its own failed-acquisition denominator.
    m, pawn, setup = make()
    m.put(0x8d57e4, 17); m.put(0x8d57ec, 0x3f800000)
    pending = BOARD + 0x7000
    m.uc.mem_write(pending, struct.pack("<iiii", 0, 1, 0, 2))
    for off, value in [(0x8fc, pending), (0x900, pending + 16), (0x904, pending + 64)]:
        m.put(pawn + off, value)
    route = dict(attempted=1, admitted=0, id="grounded_massive_pending_two_point_entry",
                 admission_claim="original entry-pump return only; route/timer/animation completion is not established",
                 supplied_speed_map={"bucket_count": 17, "size": 0, "load_factor": 1.0,
                 "threshold": 0, "bucket_array": None}, setup=setup, before=snapshot(m, pawn))
    try:
        route["call"] = m.call(0x233110, [], receiver=pawn)
        route["admitted"] = 1
    except Exception as exc:
        pc = m.uc.reg_read(m.x.UC_X86_REG_EIP)
        stop = m.stubs.get(pc)
        expected = (str(exc) == "unresolved import" and stop is not None and stop["name"] == "lua_pushvalue"
                    and int(stop["iat_rva"], 16) == 0x3d64e4 and m.trace[-1] == [0x6c3ec, 6])
        route.update(reason=str(exc), partial=m.diagnostic(), unresolved_import=stop,
                     after=snapshot(m, pawn), expected_boundary=expected)
    save(m, "full_ground_route_acquisition")
    route["failed"] = 1 - route["admitted"]
    result.update(full_route_acquisition=route, stage_recipe_attempted=len(cases),
                  stage_recipe_completed=sum(r["completed"] for r in result["cases"]),
                  legal_stage_recipes=sum(r["completed"] and r.get("legal", False) for r in result["cases"]),
                  query_accepted_recipes=sum(r.get("legal", False) for r in result["cases"]),
                  original_query_rejected_controls=sum(r.get("legal") is False for r in result["cases"]),
                  coordinate_writer_returns=sum(s["kind"] == "coordinate_writer" for r in result["cases"] for s in r.get("stages", [])),
                  final_arrival_returns=sum(s["kind"] == "final_arrival" for r in result["cases"] for s in r.get("stages", [])),
                  atlas_canonical_sha256=source.atlas_sha,
                  original_body_identities=[source.verified[k] for k in sorted(source.verified)])
    require(sha(Path(executable).read_bytes()) == sha(source.data), "executable changed during acquisition")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.private_output_dir.exists():
        parser.error("Outputs are create-only")
    sys.path.insert(0, str(args.runtime_path.resolve()))
    faulthandler.disable()
    args.private_output_dir.mkdir(parents=True)
    result = acquire(args.executable, args.private_output_dir)
    with args.output.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(result, out, indent=2, sort_keys=True, allow_nan=False)
        out.write("\n")
    print(json.dumps({k: result[k] for k in ("stage_recipe_attempted", "stage_recipe_completed", "legal_stage_recipes", "original_query_rejected_controls")} |
                     dict(failures=len(result["failures"]), mismatches=len(result["mismatches"]), entry_pump_returned=result["full_route_acquisition"]["admitted"],
                          entry_pump_failed=result["full_route_acquisition"]["failed"])))
    route = result["full_route_acquisition"]
    return 1 if result["failures"] or result["mismatches"] or (route["failed"] and not route["expected_boundary"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
