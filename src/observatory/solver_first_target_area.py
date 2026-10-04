"""Complete original cardinal query vectors for model-derived supplied storage.

No Rust extension, original skill dispatch, or game session is used here.
"""
from pathlib import Path
import json

from src.observatory.solver_first_path_oracle import (
    BASE, BOARD, ROOT, EXE_SHA, OriginalSource, Machine, canonical, sha, require, runtime_identity,
)

WRAPPER_SHA = "59259634c2a99a3bb9b3219c3d824488130abbf2d5a4ff7126ad8c7c26e8282a"
CORE_SHA = "6e05f5d87e1f9cf5ac16eee5a9b249bf7e1e979d7e30ac35d9612c2fc4705689"
SCRIPT_PINS = {
    "global.lua": "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2",
    "weapons_base.lua": "bdb55457746d08b46e8b62ad7cfc27f0a08bde9fab7397a4780dfe945b5f8f38",
    "weapons_prime.lua": "ad82af253572fe7e86293592d0b670e5851e90842666062b919421e134173ac6",
    "weapons_brute.lua": "e5989a06676ee04827401007a825c7719048268fb8ff2303bce921a32441b265",
}


def verify_globals(source):
    # Exact independently extracted integer stores; bodies are not executed here.
    for rva, expected in ((0x27E14A, "68ffffff7f"), (0x27F199, "6a02"),
                          (0x27F5AC, "6a09"), (0x279DDF, "c745e860405700"),
                          (0x27E1E2, "6a03")):
        raw = bytes.fromhex(expected)
        require(source.bytes_at(rva, len(raw)) == raw, "constant/member store differs")
    source.verify(0x279880)
    require(source.verified[0x279880]["body_sha256"] ==
            "51f3a81b7b832098c11f81beb1c85e1fe488434adce745dd8af5cb5af64200c2",
            "namespace owner identity differs")


def fill_world(machine, query):
    machine.fixture(dict(water=False, occupied=False, blocker_team=None))
    terrain_ids = dict(ground=0, building=1, rubble=2, chasm=9)
    require(len(query["tiles"]) == 64, "query tile coverage differs")
    seen = set()
    for tile in query["tiles"]:
        point = (tile["x"], tile["y"])
        require(point not in seen and all(type(v) is int and 0 <= v < 8 for v in point),
                "invalid query tile")
        seen.add(point)
        require(tile["terrain"] in terrain_ids, "terrain outside fixture query domain")
        machine.put(BOARD + 0x10000 + (point[0] * 8 + point[1]) * 0x2BBC + 0x2AE0,
                    terrain_ids[tile["terrain"]])
    occupancy = {}
    require(len(query["units"]) <= 3, "actor count outside fixture query domain")
    for index, unit in enumerate(query["units"]):
        require(unit["hp"] in (0, 1) and type(unit["mech"]) is bool
                and type(unit["source_corpse"]) is bool, "query pawn premises differ")
        point = (unit["x"], unit["y"])
        require(all(type(v) is int and 0 <= v < 8 for v in point), "query pawn outside board")
        pawn = BOARD + 0x100000 + index * 0x1000
        for offset, value in ((0, BASE + 0x42E320), (0x8A8, unit["hp"]),
            (0xB0, unit["team"]), (0x8EC, point[0]), (0x8F0, point[1]),
            (0x9E4, int(unit["mech"])), (0xF80, int(unit["source_corpse"])),
            (0x9E0, 0), (0x10E8, 0)):
            machine.put(pawn + offset, value)
        occupancy.setdefault(point, []).append(pawn)
    for index, (point, pawns) in enumerate(sorted(occupancy.items())):
        vector = BOARD + 0x6000 + index * 32
        for i, pawn in enumerate(pawns):
            machine.put(vector + i * 4, pawn)
        tile = BOARD + 0x10000 + (point[0] * 8 + point[1]) * 0x2BBC
        for offset, value in ((0xA0, vector), (0xA4, vector + len(pawns) * 4),
                              (0xA8, vector + len(pawns) * 4)):
            machine.put(tile + offset, value)
    return sha(bytes(machine.uc.mem_read(BOARD, 0x200000)))


def run(executable, report_path, *, private_dir=None):
    source = OriginalSource(executable)
    source.verify(0x174060)
    source.verify(0xCFA40)
    require(source.verified[0x174060]["body_sha256"] == WRAPPER_SHA
            and source.verified[0xCFA40]["body_sha256"] == CORE_SHA, "query body identity differs")
    verify_globals(source)
    scripts = Path(executable).parent / "scripts"
    require(all(sha((scripts / p).read_bytes()) == pin for p, pin in SCRIPT_PINS.items()),
            "shipped script identities differ")
    input_sha = sha(report_path.read_bytes())
    supplied = json.loads(report_path.read_text())
    require(supplied["case"]["status"] == "complete" and supplied["simulator_version"] == 413,
            "full-click reference report is incomplete or wrong version")
    requests = supplied["case"]["original_query_requests"]
    runtime = runtime_identity()
    report = dict(schema_version=1, corpus_version="s2-original-base-query-storage-413-v1",
        evidence_class="bounded_original_query_execution_on_model_derived_supplied_storage",
        executable_sha256=EXE_SHA, atlas_canonical_sha256=source.atlas_sha,
        reference_report_sha256=input_sha, shipped_script_sha256=SCRIPT_PINS,
        constant_registration_packet_sha256="48df6ccf680e2fc1ab0e625d37fd0e3b0391da21b4b2d71d086cea55d7a4ef49",
        original_static_target_packet_sha256="a2bb6f80bf716521b7ce41c2f0aad3f93da1758793d4a3fe8d0ec8ce20549c71",
        runtime=runtime, tool_source_sha256={p: sha((ROOT / p).read_bytes()) for p in (
            "src/observatory/solver_first_target_area.py", "scripts/solver_first_target_area_oracle.py",
            "src/observatory/solver_first_path_oracle.py", "src/observatory/pe_anchor_map.py")},
        supplied_boundaries=["zero initialized Board/Tile storage and original vtables; no original constructors",
            "model-derived terrain/occupancy; HP sign normalization for IsDead only",
            "commonPawn plus supplied mech/sourceCorpse bytes, lifecycle0/currentMutation0",
            "zero global available-mutation vector; no mutation eligibility substitution",
            "successful existing HeapAlloc/HeapFree import responses; all original callbacks unchanged"],
        exclusions=["original death/removal continuity", "actual-game before/action/after provenance",
            "Lua marshalling/skill effect dispatch", "complete original action outcomes",
            "upgrades/phase/custom getters", "other terrain/status/mutation families", "held-out acquisition"],
        original_completed_action_transitions=0, full_turn_original_comparisons=0,
        fair_input_admissions=0, held_out_cases=0, ledger_promotions=0, gate_promotions=0,
        cases=[], failures=[], mismatches=[])
    for request in requests:
        row = dict(id=request["id"], admitted=False, matched=False)
        machine = None
        try:
            query = request["query"]
            require(sha(json.dumps(query, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
                    == request["id"], "query request identity differs")
            machine = Machine(source)
            before = fill_world(machine, query)
            initializer = machine.call(0x3030, [])
            out = BOARD + 0x7000
            x, y = query["origin"]
            receipt = machine.call(0x174060, [out, x, y, query["range"], 0])
            points = machine.output(out)
            row.update(admitted=True, original_initializer=initializer, original_query=receipt,
                       supplied_world_sha256=before, points=points,
                       expected_targets_sha256=sha(canonical(query["expected_targets"])))
            require(sorted(points) == sorted(query["expected_targets"]), "full target membership mismatch")
            if private_dir:
                with (private_dir / (request["id"] + ".json")).open("x", encoding="utf-8", newline="\n") as out_file:
                    out_file.write(canonical(dict(request=request, trace=machine.trace, imports=machine.imports,
                                                  points=points)).decode())
            row["matched"] = True
        except Exception as exc:
            failure = dict(id=request["id"], reason=str(exc))
            if machine is not None:
                failure["diagnostic"] = machine.diagnostic()
            report["failures"].append(failure)
            if row["admitted"]:
                report["mismatches"].append(failure)
            row["failure"] = str(exc)
        report["cases"].append(row)
    require(sha(Path(executable).read_bytes()) == EXE_SHA and input_sha == sha(report_path.read_bytes())
            and runtime == runtime_identity()
            and all(sha((scripts / p).read_bytes()) == pin for p, pin in SCRIPT_PINS.items()),
            "oracle provenance changed")
    report.update(attempted=len(requests), admitted=sum(r["admitted"] for r in report["cases"]),
                  matched=sum(r["matched"] for r in report["cases"]), failed=len(report["failures"]),
                  excluded=0, original_body_identities=list(source.verified.values()))
    return report
