"""Pinned original Lua interpretation of the stock Ground grass emitter chain.

Exact source slices are supplied, not a full game/bootstrap recreation. No live
game, image resource, particle constructor or complete movement is acquired.
"""
import bisect
from collections import Counter
import json
from pathlib import Path
import struct
import time

from src.observatory import solver_first_path_oracle as api
from src.observatory import solver_first_lua_vm as vm

MAP = api.ROOT / "data/solver_first/s1_lua_emitter_instruction_admission.json"
MAP_SHA = "4e5bcc3c410fb3e10c37fee8cbe417b8efe23fc4d5f9521ac4a98d55c7a2f6b3"
EXTRA_RETURNS = frozenset((0x1b51, 0xfee4, 0xcc7b, 0x11fdd, 0x160ff, 0x16170,
    0x161dd, 0x1624e, 0x162c2, 0x16327, 0x463a, 0xfbb1))
WINDOWS = (
    (6896, 263, "5f0b30473a705b24097ae3f563c4db552fdac286f1ab1857cec36052ee11a0e7"),
    (65152, 143, "8843120ccf8737c9c05fd25af8ed797bbc3f4ba3f01e1b4e6cfdd6a9c6f70db4"),
    (52320, 200, "f6cc5d269089d53159b350c9c681f13925e33f897e4f0e49d5a1f8f3559bd5ce"),
    (73568, 200, "c0fd648dca5952423b8b1e82c0ef91ec9c62f1ca73d2b1a548ce87f8ebf3d9f7"),
    (90224, 832, "770e2a0aa22fa0b9836bf35101a9ba4db223800a9262a0b779dbc42e848022ab"),
    (17808, 196, "c6856d243fce9ffc97e0f7fdf62bcda9058a2c6d7ec746ca34ee9e16bf7d4ee4"),
    (28224, 41, "5b3c329f05d042abcf39e35e574ee8f1c53c086f1e4f4059348b8a3596c25fc7"),
    (27584, 627, "bbedbe876976d8f4e56f8cc841da73b0eae54fc68338613a18d977004212e050"),
    (52528, 140, "dcbbfe80059907ec10d30e05ca4ede229d1a5b587e7efc289d408137945f09e9"),
    (144552, 195, "6dfa812168317667aea912e1cd85467f04c06d1dd5db2156677d2c4bda31748d"),
    (64336, 181, "296fc6f4f25f5685c536659970edc76e3d2e56e00cbfe57ab9e7b8f4eb79ba70"))
SOURCES = {
    "scripts/global.lua": "96d82d83a1620061e6fd013aa8462883e1f3764d03752757ad77fbbbd04bc9b2",
    "scripts/emitters.lua": "6e599b71006cde4ceb85ff4fa17c8bc88aa0e6173d7d16dff8139fa569f38cd1"}
SLICES = (
    ("CreateClass", "scripts/global.lua", 1776, 2208, "63ee31a0fc70240cf0046a0d6bb9da19c3ade31663d3c5455c86a413f90a4ee0"),
    ("Emitter", "scripts/emitters.lua", 2, 418, "b437eff1ccf469af47fa34ab6fcbacee51580bdfd67170b0496c7f6b70d2737d"),
    ("Emitter_Dust", "scripts/emitters.lua", 3565, 3822, "40cc7c687ffe1b7f2d872349e96e1aa7d2649b66a05dd0e435f0ac998b186a29"),
    ("Emitter_tiles_grass", "scripts/emitters.lua", 3866, 3951, "0b76358c15c3363ad3df502c516e6cde41c77f30798634d950475039fa5800aa"))
EXPECTED = {
    "Emitter": dict(image_count=1, max_particles=32, burst_count=0, layer=2, y=0, image=None),
    "Emitter_Dust": dict(image_count=1, max_particles=32, burst_count=15, layer=1, y=10, image="combat/tiles_grass/dust.png"),
    "Emitter_tiles_grass": dict(image_count=1, max_particles=32, burst_count=15, layer=1, y=10, image="combat/tiles_grass/dust.png")}


class EmitterMachine(vm.LuaMachine):
    def __init__(self, executable, admission):
        super().__init__(executable, admission, allocator_returns=vm.ALLOCATOR_RETURNS | EXTRA_RETURNS)
        self.padding_reads = []
        for rva, size, digest in WINDOWS:
            offset = self.dll.rva_to_file_offset(rva)
            api.require(api.sha(self.dll_raw[offset:offset + size]) == digest, "DLL script source window differs")
        for rva, value, digest in ((0x415578, 1, "67abdd721024f0ff4e0b3f4c2fc13bc5bad42d0b7851d456d88d203d15aaa450"),
                                  (0x41555c, 2, "26b25d457597a7b0463f9620f666dd10aa2c4373a505967c7c8d70922a2d6ece")):
            offset = self.source.image.rva_to_file_offset(rva)
            raw = self.source.data[offset:offset + 4]
            api.require(api.sha(raw) == digest and struct.unpack("<I", raw)[0] == value,
                        "original layer DWORD differs")
        self.source.verify(0x50890)
        api.require(self.source.verified[0x50890]["body_sha256"] ==
            "920d057dc1eb6a60a3e69515e084d79dbf944d873468870a0e58c6ea8a79c722", "integer consumer differs")
        for rva, size, digest in ((0x280b04, 66, "c71e28d2a7fdd87c2bf718423201baa49165b6bb2b66cebd6e0402a65a5c7228"),
                                 (0x280b46, 66, "6340830f2e34b17f070af96e523e1313f3fe7373c956ecac59d70e5655361a40")):
            self.source.check_window(rva, size, digest)

    def allocate_callback(self):
        super().allocate_callback()
        row = self.allocator_calls[-1]
        result, requested = row["result"], row["arguments"][3]
        if result:
            # Supplied allocator owns a 16-byte rounded block. Requests/liveness
            # still use exact Lua sizes; only pinned terminal-word reads below
            # may read this explicit zero padding, never write it as Lua data.
            capacity = (requested + 15) & ~15
            self.uc.mem_write(result + requested, b"\0" * (capacity - requested))

    def memory(self, uc, kind, at, width, value, user):
        i = bisect.bisect_right(self.allocation_starts, at) - 1
        begin = self.allocation_starts[i] if i >= 0 else None
        if begin in self.live and kind == self.u.UC_MEM_READ and width == 4:
            end = begin + self.allocations[begin]
            pc = uc.reg_read(self.x.UC_X86_REG_EIP) - vm.DLL_BASE
            if begin <= at < end < at + width and pc in (0x234e0, 0x23527):
                esp = uc.reg_read(self.x.UC_X86_REG_ESP)
                origin = self.get(esp + 16)
                if (at + width <= begin + ((self.allocations[begin] + 15) & ~15)
                        and at + width <= end + 3 and begin <= origin <= at
                        and b"\0" in bytes(uc.mem_read(at, end - at))):
                    self.padding_reads.append(dict(dll_rva=pc, address=at, width=width,
                        allocation=begin, requested=self.allocations[begin], string_origin=origin))
                    return
        super().memory(uc, kind, at, width, value, user)


def acquire(executable, admission):
    machine = EmitterMachine(executable, admission)
    calls, observations, slices = [], {}, []
    def dll(name, args):
        started = time.perf_counter()
        row = machine.cdecl(name, args)
        row["wall_seconds"] = time.perf_counter() - started
        calls.append(row)
        api.require(row["returned"] and row["cdecl_stack_ok"] and row["failure"] is None,
                    f"original DLL call {name} failed: {row['failure']}")
        return row["eax"]
    def key(value):
        ptr = api.BOARD + 0x30000
        machine.uc.mem_write(ptr, value.encode("ascii") + b"\0")
        return ptr
    def typed():
        kind = dll("lua_type", [state, 0xffffffff])
        value = None
        if kind == 3:
            value = dll("lua_tointeger", [state, 0xffffffff])
            value = value if value < 0x80000000 else value - 0x100000000
            dll("lua_pushinteger", [state, value & 0xffffffff])
            api.require(dll("lua_equal", [state, -1 & 0xffffffff, -2 & 0xffffffff]) == 1,
                        "numeric property is not exactly its integer conversion")
            dll("lua_settop", [state, -2 & 0xffffffff])
        elif kind == 4:
            length = api.BOARD + 0x31000
            ptr = dll("lua_tolstring", [state, 0xffffffff, length])
            value = bytes(machine.uc.mem_read(ptr, machine.get(length))).decode("ascii")
        else:
            api.require(kind == 0, "unexpected property type")
        return dict(type=kind, value=value)
    status, failure = "failed", None
    try:
        source_bytes = {p: (Path(executable).parent / p).read_bytes() for p in SOURCES}
        api.require(all(api.sha(source_bytes[p]) == digest for p, digest in SOURCES.items()), "stock script differs")
        state = dll("lua_newstate", [vm.ALLOC, vm.UD])
        api.require(dll("luaopen_base", [state]) == 2, "base library result count differs")
        api.require(dll("lua_gettop", [state]) == 2, "base library stack differs")
        dll("lua_settop", [state, 0])
        for name, value in (("LAYER_FRONT", 1), ("LAYER_BACK", 2)):
            dll("lua_pushinteger", [state, value])
            dll("lua_setfield", [state, -10002 & 0xffffffff, key(name)])
        for name, source, begin, end, digest in SLICES:
            raw = source_bytes[source][begin:end]
            api.require(api.sha(raw) == digest, "exact stock slice differs")
            ptr, name_ptr = api.BOARD + 0x20000, api.BOARD + 0x28000
            machine.uc.mem_write(ptr, raw)
            machine.uc.mem_write(name_ptr, name.encode("ascii") + b"\0")
            api.require(dll("luaL_loadbuffer", [state, ptr, len(raw), name_ptr]) == 0, "compilation failed")
            api.require(dll("lua_pcall", [state, 0, 0, 0]) == 0, "execution failed")
            api.require(dll("lua_gettop", [state]) == 0, "script stack differs")
            slices.append(dict(name=name, source=source, begin=begin, end=end, raw_sha256=digest))
        for name, expected in EXPECTED.items():
            dll("lua_getfield", [state, -10002 & 0xffffffff, key(name)])
            api.require(dll("lua_type", [state, 0xffffffff]) == 5, "emitter global is not table")
            fields, getters = {}, {}
            for field, value in expected.items():
                dll("lua_getfield", [state, -1 & 0xffffffff, key(field)])
                fields[field] = typed()
                api.require(fields[field] == dict(type=0 if value is None else 4 if isinstance(value, str) else 3, value=value),
                            "stock inherited field differs")
                dll("lua_settop", [state, -2 & 0xffffffff])
                dll("lua_getfield", [state, -1 & 0xffffffff, key("Get" + field)])
                if field == "image":
                    api.require(dll("lua_type", [state, 0xffffffff]) == 0, "unexpected generated image getter")
                    getters[field] = dict(type=0, value=None)
                    dll("lua_settop", [state, -2 & 0xffffffff])
                else:
                    api.require(dll("lua_type", [state, 0xffffffff]) == 6, "generated getter is not function")
                    dll("lua_pushvalue", [state, -2 & 0xffffffff])
                    api.require(dll("lua_pcall", [state, 1, 1, 0]) == 0, "original generated getter failed")
                    getters[field] = typed()
                    api.require(getters[field] == fields[field], "getter/inherited field differs")
                    dll("lua_settop", [state, -2 & 0xffffffff])
            observations[name] = dict(fields=fields, getters=getters)
            dll("lua_settop", [state, 0])
        api.require(dll("lua_gettop", [state]) == 0, "final stack differs")
        dll("lua_close", [state])
        api.require(not machine.live, "close left live allocations")
        api.require(all((Path(executable).parent / p).read_bytes() == raw for p, raw in source_bytes.items()),
                    "stock scripts changed during acquisition")
        status = "complete"
    except Exception as exc:
        failure = str(exc)
    return dict(status=status, failure=failure, observations=observations, slices=slices, calls=calls,
                allocator_calls=machine.allocator_calls, padding_reads=machine.padding_reads,
                remaining_allocations=len(machine.live), instructions=machine.dll_points), machine


def run(executable, private_dir, *, exploratory=False):
    private_dir = Path(private_dir)
    api.require(not private_dir.exists(), "private directory is create-only")
    private_dir.mkdir(parents=True)
    map_raw = None if exploratory else MAP.read_bytes()
    api.require(exploratory or api.sha(map_raw) == MAP_SHA, "emitter instruction map identity differs")
    admission = None if exploratory else json.loads(map_raw)["instructions"]
    api.require(exploratory or json.loads(map_raw)["dll_sha256"] == vm.DLL_SHA, "map DLL differs")
    paths = ["src/observatory/solver_first_lua_emitters.py", "scripts/solver_first_lua_emitters.py",
             "src/observatory/solver_first_lua_vm.py", "src/observatory/solver_first_path_oracle.py",
             "src/observatory/pe_anchor_map.py"]
    pins = {p: api.sha((api.ROOT / p).read_bytes().replace(b"\r\n", b"\n")) for p in paths}
    runtime = api.runtime_identity()
    private, machine = acquire(executable, admission)
    receipt = private_dir / "stock_grass.json"
    with receipt.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(private, handle, sort_keys=True, indent=2, allow_nan=False); handle.write("\n")
    api.require(pins == {p: api.sha((api.ROOT / p).read_bytes().replace(b"\r\n", b"\n")) for p in paths}, "sources changed")
    api.require(api.runtime_identity() == runtime, "runtime changed")
    api.require(exploratory or MAP.read_bytes() == map_raw, "map changed")
    api.require(api.sha(Path(executable).read_bytes()) == api.EXE_SHA and
        api.sha((Path(executable).parent / "lua5.1.dll").read_bytes()) == vm.DLL_SHA, "binaries changed")
    complete = private["status"] == "complete"
    report = dict(schema_version=1, corpus_version="s1-original-stock-grass-lua-development-v1",
        game_build=13725832, baseline_solver_commit="84c186ae440163056c5c39b9aea9c20e6f49983e",
        information_mode="source-correct supplied offline oracle; no fair-player admission",
        objective="actual stock grass emitter Lua inheritance/getter and allocator ownership closure",
        executable_sha256=api.EXE_SHA, dll_sha256=vm.DLL_SHA, runtime=runtime, source_lf_sha256=pins,
        game_source_sha256=SOURCES, exact_slices=private["slices"], DLL_source_windows=WINDOWS,
        attempted=1, admitted=int(complete), matched=int(complete), failed=int(not complete), excluded=0,
        status=private["status"], failure=private["failure"], observations=private["observations"],
        call_count=len(private["calls"]), instruction_count=sum(c["instructions"] for c in private["calls"]),
        call_wall_seconds=[c["wall_seconds"] for c in private["calls"]],
        allocator_call_count=len(private["allocator_calls"]), remaining_allocations=len(machine.live),
        padding_read_count=len(machine.padding_reads), allocator_return_rvas=sorted(machine.allocator_returns),
        import_counts=dict(Counter(r["name"] for c in private["calls"] for r in c["imports"])),
        private_receipt_sha256=api.sha(receipt.read_bytes()), instruction_admission_mode="exploratory" if exploratory else "frozen",
        instruction_admission_sha256=None if exploratory else api.sha(map_raw), executed_DLL_instruction_points=len(machine.dll_points),
        supplied_boundaries=["Exact original CreateClass plus complete ordered Emitter/Dust/grass source slices, not whole emitters.lua/global.lua or native bootstrap.",
            "Actual original luaopen_base supplies pairs/setmetatable; layer globals1/2 are seeded by actual Lua APIs from original pinned registration values.",
            "Successful normal custom allocator and empty SEH chain; 16-byte rounded supplied storage has explicit zero padding. Exact oldsize/liveness remains enforced.",
            "Only original scalar character-search terminal DWORD reads at234e0/23527 may read up to3 padding bytes, with same live block/original pointer and requested-region NUL.",
            "Ordered private instruction/import/allocator call receipts retained; no complete ordered memory comparison or native particle/image construction."],
        original_completed_action_transitions=0, full_turn_original_comparisons=0, fair_input_admissions=0,
        held_out_cases=0, gate_promotions=0, ledger_promotions=0,
        next_blocker="Actual source-correct image cache/resource dimensions, then native emitter and loaded Move/dispatch context for joined Ground N2 settlement.")
    instruction_map = dict(schema_version=1, dll_sha256=vm.DLL_SHA, instructions=machine.dll_points,
        provenance="Source-checked exploratory actual base library plus exact stock CreateClass/Emitter/Dust/grass interpreter/getter paths.")
    return report, instruction_map
