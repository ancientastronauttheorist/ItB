"""Bounded original x86 path queries in a reconstructed offline world.

Original callbacks and helpers execute unchanged. The fixture and normal heap
responses are supplied boundaries, not original gameplay or allocator evidence.
"""
from __future__ import annotations

import bisect
from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path
import struct

from src.observatory.pe_anchor_map import PEImage

ROOT = Path(__file__).resolve().parents[2]
EXE_SHA = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
BASE, RETURN, IMPORT = 0x400000, 0x4000000, 0x5000000
STACK, BOARD, HEAP = 0x30000000, 0x10000000, 0x20000000
INIT_SHA = "4d2d793080eed2c8234ef3e4eaf3d64219e33a475b44fa51ca9faa182ca0479d"
FIXTURE = ROOT / "data/solver_first/s1_path_query_fixture.json"
ATLAS = ROOT / "data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json"
LIMIT = 2_000_000


class OracleError(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise OracleError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()


def recipes():
    # Handwritten expectations follow independently reviewed native predicates.
    rows = []
    def reachable(name, profile, budget, points, blocker=None, water=True, occupied=True):
        rows.append(dict(id=name, kind="reachable", profile=profile, budget=budget,
                         blocker_team=blocker, water=water, occupied=occupied, expected=points))
    reachable("ground_water", 16, 2, [])
    reachable("massive_water_one", 18, 1, [[0, 1]])
    reachable("massive_water_two", 18, 2, [[0, 1], [0, 2]])
    reachable("massive_friendly_water", 18, 2, [[0, 2]], 1)
    reachable("massive_enemy_water", 18, 2, [], 6)
    reachable("massive_friendly_budget_one", 18, 1, [], 1)
    reachable("ground_friendly", 16, 2, [[0, 2]], 1, False)
    reachable("ground_enemy", 16, 2, [], 6, False)
    reachable("ground_empty", 16, 2, [[0, 1], [0, 2]], None, False)
    reachable("unoccupied_origin_control", 18, 2, [[0, 0], [0, 1], [0, 2]], occupied=False)
    for name, profile, end, points in [
        ("ground_path_water_endpoint", 16, [0, 1], [[0, 0], [0, 1]]),
        ("ground_path_beyond_water", 16, [0, 2], []),
        ("massive_path_water", 18, [0, 1], [[0, 0], [0, 1]]),
        ("massive_path_beyond_water", 18, [0, 2], [[0, 0], [0, 1], [0, 2]]),
        ("same_point_path", 18, [0, 0], []),
    ]:
        rows.append(dict(id=name, kind="path", profile=profile, end=end,
                         blocker_team=None, water=True, occupied=True, expected=points))
    return rows


class OriginalSource:
    def __init__(self, executable):
        import capstone as cs
        require(cs.__version__ == "5.0.7", "unsupported decoder version")
        self.data = Path(executable).read_bytes()
        require(sha(self.data) == EXE_SHA, "executable identity differs")
        self.image = PEImage(self.data)
        require(self.image.image_base == BASE and self.image.bits == 32, "PE ABI differs")
        self.decoder = cs.Cs(cs.CS_ARCH_X86, cs.CS_MODE_32)
        self.decoder.detail = True
        atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
        require(atlas["identity"]["executable_sha256"] == EXE_SHA, "atlas build differs")
        self.atlas_sha = sha(canonical(atlas))
        require(self.atlas_sha == "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803", "atlas admission metadata differs")
        self.owners = {int(row["entry_rva"], 16): row for row in atlas["functions"]}
        self.ranges = sorted((int(r["start_rva"], 16), int(r["start_rva"], 16) + r["size"], entry)
                             for entry, row in self.owners.items() for r in row["ranges"])
        self.starts = [r[0] for r in self.ranges]
        self.points, self.verified, self.executed_rvas = {}, {}, set()
        self.verify(0x3030)
        # Decode/pin these semantic identities even when a particular recipe
        # takes another branch. Definition loading/GetPathProf is not executed.
        for entry in (0x174180, 0x1742d0, 0x232f90):
            self.verify(entry)
        # This registered getter is not an atlas owner. Pin its separate window.
        self.check_window(0x23d850, 7, "a33ed4c54f724b1cdd526b3c3e8bfc670f9881db0df0a549f9dd82f82745c8cf")
        self.check_window(0x27c1c1, 34, "ef6daf844d8d0df8bd6c920735f77996c14931c67e272b4e742ce32ea34a4de5")

    def bytes_at(self, rva, size):
        require(size > 0 and any(s.executable and s.virtual_address <= rva
                and rva + size <= s.virtual_address + s.raw_size for s in self.image.sections),
                "source span is not wholly file-backed executable code")
        offset = self.image.rva_to_file_offset(rva)
        require(offset is not None, "source is not file-backed")
        return self.data[offset:offset + size]

    def check_window(self, rva, size, digest):
        require(sha(self.bytes_at(rva, size)) == digest, "semantic window identity differs")

    def verify(self, entry):
        if entry in self.verified:
            return
        if entry == 0x3030:
            row = dict(entry_rva="0x00003030", body_size=81, body_sha256=INIT_SHA,
                       ranges=[dict(start_rva="0x00003030", size=81)])
        else:
            require(entry in self.owners, "unreviewed original range")
            row = self.owners[entry]
        pieces, points = [], {}
        for span in row["ranges"]:
            at, size = int(span["start_rva"], 16), span["size"]
            code = self.bytes_at(at, size)
            pieces.append(code)
            cursor = at
            for ins in self.decoder.disasm(code, BASE + at):
                require(ins.address == BASE + cursor, "decoder gap")
                points[cursor] = bytes(ins.bytes)
                cursor += ins.size
            require(cursor == at + size, "undecoded source bytes")
        require(sum(map(len, pieces)) == row["body_size"] and sha(b"".join(pieces)) == row["body_sha256"], "atlas body bytes differ")
        self.points.update(points)
        self.verified[entry] = {k: row[k] for k in ("entry_rva", "body_size", "body_sha256", "ranges")}

    def instruction(self, rva):
        if rva not in self.points:
            i = bisect.bisect_right(self.starts, rva) - 1
            require(i >= 0 and rva < self.ranges[i][1], "execution outside atlas/initializer")
            self.verify(self.ranges[i][2])
        require(rva in self.points, "execution at non-instruction boundary")
        return self.points[rva]


class Machine:
    def __init__(self, source):
        import unicorn as u
        from unicorn import x86_const as x
        require(u.__version__ == "2.1.4", "unsupported emulator version")
        self.u, self.x, self.source = u, x, source
        self.uc = u.Uc(u.UC_ARCH_X86, u.UC_MODE_32)
        self.uc.ctl_set_cpu_model(19)
        image = source.image
        size = max(s.virtual_address + max(s.virtual_size, s.raw_size) for s in image.sections)
        self.uc.mem_map(BASE, (size + 4095) & ~4095)
        self.uc.mem_write(BASE, source.data[:image.size_of_headers])
        for s in image.sections:
            self.uc.mem_write(BASE + s.virtual_address, source.data[s.raw_offset:s.raw_offset + s.raw_size])
        for s in image.sections:
            if s.executable:
                self.uc.mem_protect(BASE + s.virtual_address & ~4095, (max(s.virtual_size, s.raw_size) + 4095) & ~4095, u.UC_PROT_READ | u.UC_PROT_EXEC)
        for at, size in [(0, 4096), (RETURN, 4096), (IMPORT, 0x10000), (STACK, 0x10000), (BOARD, 0x200000), (HEAP, 0x400000)]:
            self.uc.mem_map(at, size)
        self.stubs = {}
        for i, row in enumerate(image.imports()):
            stub = IMPORT + i * 16
            self.stubs[stub] = row
            self.put(BASE + int(row["iat_rva"], 16), stub)
        self.put(0x8b7634, 0x12345678)
        self.next_alloc = HEAP + 0x1000
        self.allocations, self.allocation_starts, self.live = {}, [], set()
        self.trace, self.imports, self.failure = [], [], None
        self.uc.hook_add(u.UC_HOOK_CODE, self.step)
        self.uc.hook_add(u.UC_HOOK_MEM_INVALID, self.invalid)
        self.uc.hook_add(u.UC_HOOK_MEM_READ | u.UC_HOOK_MEM_WRITE, self.memory)

    def get(self, at):
        return struct.unpack("<I", self.uc.mem_read(at, 4))[0]

    def put(self, at, value):
        self.uc.mem_write(at, struct.pack("<I", value & 0xffffffff))

    def fail(self, message):
        if self.failure is None:
            self.failure = str(message)
        self.uc.emu_stop()

    def diagnostic(self):
        pc = self.uc.reg_read(self.x.UC_X86_REG_EIP)
        return dict(guest_pc=pc, instruction_count=len(self.trace), trace_sha256=sha(canonical(self.trace)),
                    import_counts=dict(Counter(r["name"] for r in self.imports)),
                    imports_sha256=sha(canonical(self.imports)))

    def invalid(self, uc, kind, at, width, value, user):
        self.fail(f"unmapped/protected guest memory kind={kind}, width={width}")
        return False

    def memory(self, uc, kind, at, width, value, user):
        try:
            if at < 4096:
                require(at == 0 and width == 4, "undeclared null-page access")
            if HEAP <= at < HEAP + 0x400000:
                i = bisect.bisect_right(self.allocation_starts, at) - 1
                require(i >= 0, "unallocated heap access")
                begin = self.allocation_starts[i]
                require(begin in self.live and at + width <= begin + self.allocations[begin], "freed/out-of-allocation heap access")
        except Exception as exc:
            self.fail(exc)

    def step(self, uc, at, size, user):
        try:
            if at == RETURN:
                uc.emu_stop()
                return
            if at in self.stubs:
                self.respond_import(at)
                return
            original = self.source.instruction(at - BASE)
            require(len(original) == size and bytes(uc.mem_read(at, size)) == original, "original instruction differs")
            self.source.executed_rvas.add(at - BASE)
            self.trace.append([at - BASE, size])
        except Exception as exc:
            self.fail(exc)

    def respond_import(self, at):
        row, x, uc = self.stubs[at], self.x, self.uc
        name = row["name"]
        seams = {"HeapAlloc": (0x3d6220, 0x389463), "HeapFree": (0x3d621c, 0x389172)}
        require(row["library"].lower() == "kernel32.dll" and name in seams, "unresolved import")
        slot, ret = seams[name]
        esp = uc.reg_read(x.UC_X86_REG_ESP)
        require(STACK <= esp < STACK + 0x10000 - 16, "import frame outside stack")
        require(int(row["iat_rva"], 16) == slot and self.get(BASE + slot) == at, "import slot identity differs")
        require(self.get(esp) == BASE + ret, "unadmitted import caller")
        require(self.trace and self.trace[-1] == [ret - 6, 6], "import call seam differs")
        require(self.source.bytes_at(ret - 6, 6) == b"\xff\x15" + struct.pack("<I", BASE + slot), "import opcode differs")
        args = [self.get(esp + 4 + 4 * i) for i in range(3)]
        require(args[:2] == [0x12345678, 0], "heap response premise differs")
        if name == "HeapAlloc":
            count = args[2]
            require(0 < count < 0x100000, "allocation size outside boundary")
            result = self.next_alloc
            self.next_alloc += (count + 15) & ~15
            require(self.next_alloc <= HEAP + 0x400000, "synthetic heap exhausted")
            self.allocations[result] = count
            self.allocation_starts.append(result)
            self.live.add(result)
        else:
            require(args[2] in self.live, "free without live allocation")
            self.live.remove(args[2])
            result = 1
        self.imports.append(dict(name=name, arguments=args, result=result, caller_return_rva=ret))
        uc.reg_write(x.UC_X86_REG_EAX, result)
        uc.reg_write(x.UC_X86_REG_ESP, esp + 16)
        uc.reg_write(x.UC_X86_REG_EIP, BASE + ret)

    def call(self, entry, args, *, receiver=BOARD, limit=LIMIT):
        self.trace, self.imports, self.failure = [], [], None
        esp = STACK + 0x8000
        self.put(esp, RETURN)
        for i, arg in enumerate(args):
            self.put(esp + 4 + 4 * i, arg)
        x = self.x
        self.uc.reg_write(x.UC_X86_REG_ESP, esp)
        self.uc.reg_write(x.UC_X86_REG_ECX, receiver)
        self.uc.reg_write(x.UC_X86_REG_EFLAGS, 0x202)
        try:
            self.uc.emu_start(BASE + entry, RETURN + 1, count=limit, timeout=10_000_000)
        except Exception as exc:
            self.fail(exc)
        returned = self.uc.reg_read(x.UC_X86_REG_EIP) == RETURN
        if not returned and self.failure is None:
            self.failure = "instruction or wall-time budget exhausted before original return"
        require(self.failure is None and returned, self.failure or "original return missing")
        require(self.uc.reg_read(x.UC_X86_REG_ESP) == esp + 4 + 4 * len(args), "return stack cleanup differs")
        return dict(entry_rva=f"0x{entry:08x}", argument_words=args, receiver=receiver,
                    instruction_count=len(self.trace), trace_sha256=sha(canonical(self.trace)),
                    import_counts=dict(Counter(r["name"] for r in self.imports)),
                    imports_sha256=sha(canonical(self.imports)), returned=True)

    def fixture(self, recipe):
        self.put(BOARD, BASE + 0x42e2fc)
        self.put(BOARD + 0xc, BASE + 0x42e258)
        head, columns = BOARD + 0x3000, BOARD + 0x4000
        self.put(BOARD + 4, head)
        for offset in (0, 4, 8):
            self.put(head + offset, head)
        self.uc.mem_write(head + 0xc, b"\1\1")
        self.put(BOARD + 0x48, 8); self.put(BOARD + 0x4c, 8)
        for offset, value in [(0x50, columns), (0x54, columns + 96), (0x58, columns + 96)]:
            self.put(BOARD + offset, value)
        for px in range(8):
            begin = BOARD + 0x10000 + px * 8 * 0x2bbc
            for offset, value in [(0, begin), (4, begin + 8 * 0x2bbc), (8, begin + 8 * 0x2bbc)]:
                self.put(columns + px * 12 + offset, value)
            for py in range(8):
                terrain = (3 if py == 1 and recipe["water"] else 0) if px == 0 and py <= 3 else 4
                self.put(begin + py * 0x2bbc + 0x2ae0, terrain)
        for py, team in [(0, 1 if recipe["occupied"] else None), (1, recipe["blocker_team"])]:
            if team is None:
                continue
            pawn, vector = BOARD + 0x100000 + py * 0x1000, BOARD + 0x6000 + py * 16
            self.put(pawn, BASE + 0x42e320); self.put(pawn + 0x8a8, 3)
            self.put(pawn + 0xb0, team); self.put(pawn + 0x8ec, 0); self.put(pawn + 0x8f0, py)
            self.put(vector, pawn)
            tile = BOARD + 0x10000 + py * 0x2bbc
            for offset, value in [(0xa0, vector), (0xa4, vector + 4), (0xa8, vector + 4)]:
                self.put(tile + offset, value)
        return sha(bytes(self.uc.mem_read(BOARD, 0x200000)))

    def output(self, out):
        require(self.uc.reg_read(self.x.UC_X86_REG_EAX) == out, "returned output object differs")
        begin, end, capacity = (self.get(out + 4 * i) for i in range(3))
        if begin == 0:
            require(end == capacity == 0, "null vector header differs")
            return []
        require(begin in self.live and begin <= end <= capacity, "vector ownership/order differs")
        require(capacity - begin <= self.allocations[begin] and (end - begin) % 8 == 0 and (capacity - begin) % 8 == 0, "vector geometry differs")
        require(end - begin <= 64 * 8, "vector exceeds board domain")
        points = [list(struct.unpack("<ii", self.uc.mem_read(at, 8))) for at in range(begin, end, 8)]
        require(all(0 <= px < 8 and 0 <= py < 8 for px, py in points), "point outside board")
        require(len({tuple(p) for p in points}) == len(points), "duplicate path point")
        return points


def runtime_identity():
    import unicorn
    import capstone
    from unicorn.unicorn_py3 import unicorn as binding
    lib = Path(binding.uclib._name)
    decoder_lib = Path(capstone._cs._name)
    require(lib.is_file(), "loaded emulator library identity unavailable")
    require(decoder_lib.is_file(), "loaded decoder library identity unavailable")
    return dict(unicorn_version=unicorn.__version__, loaded_library_sha256=sha(lib.read_bytes()),
                binding_sha256=sha(Path(binding.__file__).read_bytes()),
                unicorn_package_sha256=sha(Path(unicorn.__file__).read_bytes()),
                decoder_version=capstone.__version__, decoder_binding_sha256=sha(Path(capstone.__file__).read_bytes()),
                decoder_library_sha256=sha(decoder_lib.read_bytes()),
                cpu_model=19, instruction_limit=LIMIT, wall_time_limit_us=10_000_000)


def run(executable, *, private_dir=None):
    import itb_solver
    from scripts.solver_first_s0 import corridor, loaded_extension_path
    from src.solver.observation_contract import encode_observation
    source = OriginalSource(executable)
    result = dict(schema_version=1, corpus_version="s1-path-query-development-v1",
                  evidence_class="bounded_original_body_execution_with_reconstructed_world_and_supplied_heap",
                  original_build_sha256=EXE_SHA, static_layout_reference_sha256=sha(FIXTURE.read_bytes()),
                  tool_sha256=sha(Path(__file__).read_bytes()), runtime=runtime_identity(),
                  frontend_source_sha256={p: sha((ROOT / p).read_bytes()) for p in
                      ("scripts/solver_first_path_oracle.py", "scripts/solver_first_s0.py", "src/solver/observation_contract.py", "src/observatory/pe_anchor_map.py")},
                  rust_rule_source_lf_sha256={p: sha((ROOT / p).read_bytes().replace(b"\r\n", b"\n")) for p in
                      ("rust_solver/src/movement.rs", "rust_solver/src/lib.rs", "src/solver/verify.py")},
                  atlas_canonical_sha256=source.atlas_sha, original_game_observations=0,
                  observation_contract_sha256=sha((ROOT / "data/solver_first/s0_information_contract.json").read_bytes()),
                  information_mode="provisional_player_observation_v1_offline_only",
                  objective="distinct_movement_legality_and_post_move_coordinate_projection",
                  solver_baseline_commit="9e5f849ac9e6f5aad04cc721c33be06e89688a6f",
                  full_turn_original_comparisons=0, ledger_promotions=0,
                  held_out_evaluation="not_evaluated", search_quality="not_evaluated",
                  scope_exclusions=["corpse lifecycle", "burrowed/NonGrid occupants", "multiple occupants per tile",
                      "noncanonical team IDs", "directional walls", "statuses/items", "allocation failure"],
                  simulator_version=itb_solver.simulator_version(), extension_sha256=sha(loaded_extension_path(itb_solver).read_bytes()),
                  cases=[], failures=[], mismatches=[], rust_projection_attempted=0,
                  native_query_attempted=0, direction_initializer_attempted=0)
    for recipe in recipes():
        row = dict(recipe=recipe, admitted=False, completed=False)
        m, stage = None, "machine_setup"
        try:
            m = Machine(source)
            initial = m.fixture(recipe)
            row["initial_world_sha256"] = initial
            stage = "direction_initializer"
            result["direction_initializer_attempted"] += 1
            init = m.call(0x3030, [])
            row["initializer"] = init
            out = BOARD + 0x1000
            if recipe["kind"] == "reachable":
                entry, args = 0x174180, [out, 0, 0, recipe["budget"], recipe["profile"]]
            else:
                entry, args = 0x1742d0, [out, 0, 0, *recipe["end"], recipe["profile"]]
            stage = "original_query"
            result["native_query_attempted"] += 1
            query = m.call(entry, args)
            row["query"] = query
            stage = "output_extraction"
            points = m.output(out)
            if recipe["kind"] == "reachable":
                require(points == sorted(points), "reachable ordering differs")
            elif points:
                require(points[0] == [0, 0] and points[-1] == recipe["end"], "path endpoints differ")
            row.update(admitted=True, points=points, initial_world_sha256=initial, initializer=init, query=query)
            if points != recipe["expected"]:
                result["mismatches"].append(dict(id=recipe["id"], expected=recipe["expected"], original=points))
            if private_dir:
                with (private_dir / (recipe["id"] + ".json")).open("x", encoding="utf-8", newline="\n") as f:
                    json.dump(dict(trace=m.trace, imports=m.imports, recipe=recipe, points=points), f, indent=2)
                    f.write("\n")
            if recipe["kind"] == "reachable" and recipe["occupied"]:
                stage = "rust_projection"
                state = corridor(recipe["profile"] & 15 == 2, recipe["budget"])
                if not recipe["water"]:
                    next(t for t in state["tiles"] if t["x"] == 0 and t["y"] == 1)["terrain"] = "ground"
                if recipe["blocker_team"] is not None:
                    team = recipe["blocker_team"]
                    state["units"].append(dict(uid=1, type="CombatMech" if team == 1 else "Hornet1", x=0, y=1,
                                               hp=3, max_hp=3, team=team, mech=team == 1, massive=True,
                                               flying=team == 6, active=False, weapons=[]))
                clean = encode_observation(state)
                row["rust_observation_sha256"] = sha(clean.encode())
                accepted = []
                for px in range(8):
                    for py in range(8):
                        if [px, py] == [0, 0]:
                            continue
                        result["rust_projection_attempted"] += 1
                        plan = [dict(mech_uid=0, move_to=[px, py], weapon_id="None", target=[px, py])]
                        replay = json.loads(itb_solver.replay_solution(clean, json.dumps(plan)))
                        legal = not any(e.startswith("illegal_move:") for e in replay["action_results"][0]["events"])
                        if legal:
                            accepted.append([px, py])
                        position = next(u["pos"] for u in replay["predicted_states"][0]["post_move"]["units"] if u["uid"] == 0)
                        if legal != ([px, py] in points) or position != ([px, py] if legal else [0, 0]):
                            result["mismatches"].append(dict(id=recipe["id"], destination=[px, py], rust_legal=legal, rust_position=position))
                row["rust_distinct_destinations"] = accepted
            row["completed"] = True
        except Exception as exc:
            failure = dict(id=recipe["id"], stage=stage, reason=str(exc))
            if m is not None:
                failure["partial_execution"] = m.diagnostic()
                if private_dir:
                    with (private_dir / (recipe["id"] + "_failure.json")).open("x", encoding="utf-8", newline="\n") as f:
                        json.dump(dict(trace=m.trace, imports=m.imports, failure=failure), f, indent=2)
                        f.write("\n")
            result["failures"].append(failure)
            row["failure"] = str(exc)
        result["cases"].append(row)
    result.update(attempted=len(result["cases"]), admitted=sum(r["admitted"] for r in result["cases"]),
                  completed=sum(r["completed"] for r in result["cases"]), failed=len(result["failures"]), excluded=0,
                  native_query_admitted=sum(r["admitted"] for r in result["cases"]),
                  native_query_returned=sum("query" in r for r in result["cases"]),
                  direction_initializer_returned=sum("initializer" in r for r in result["cases"]),
                  distinct_native_reachable_vectors=sum(r["admitted"] and r["recipe"]["kind"] == "reachable" and r["recipe"]["occupied"] for r in result["cases"]),
                  unoccupied_origin_controls=sum(r["admitted"] and not r["recipe"]["occupied"] for r in result["cases"]),
                  path_constructor_controls=sum(r["admitted"] and r["recipe"]["kind"] == "path" for r in result["cases"]),
                  original_body_identities=[source.verified[k] | dict(executed=any(
                      int(span["start_rva"], 16) <= rva < int(span["start_rva"], 16) + span["size"]
                      for span in source.verified[k]["ranges"] for rva in source.executed_rvas))
                      for k in sorted(source.verified)])
    require(sha(Path(executable).read_bytes()) == EXE_SHA, "executable changed during evaluation")
    return result
