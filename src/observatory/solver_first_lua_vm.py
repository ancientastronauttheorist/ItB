"""Original Lua DLL plus game registry/value wrappers in one offline guest.

Custom allocator and empty SEH chain are explicit supplied normal boundaries.
This module does not run a game session or acquire gameplay action continuity.
"""
from collections import Counter
from pathlib import Path
import json
import struct

from src.observatory import solver_first_path_oracle as api
from src.observatory.pe_anchor_map import PEImage

DLL_SHA = "0157f0c34e72b32e63ebf3fdd9a21215de674b51b6d1750ebe545ef3093a0c14"
DLL_BASE, ALLOC, UD = 0x21000000, api.IMPORT + 0xff00, 0x1234
ALLOCATOR_RETURNS = frozenset((0x1206f, 0x19892, 0x198cd, 0x19ae5, 0x19b00, 0x19b4a, 0x19cb8))
INSTRUCTION_MAP = api.ROOT / "data/solver_first/s1_lua_vm_instruction_admission.json"
INSTRUCTION_MAP_SHA = "195c5c3858a5cbd63c7e4e6d0ca3acf567e8a8f6c69de57bd9a2c04889cf2b22"
RELOCATION_MAP_SHA = "390ef02c9abc5de67ea94d6e4353d84cb06c4b37328b9ad295dbab359e0bc752"
BODY_PINS = ((0x19ca0, 395, "921fed5c459eb271fdd37cf65be9872d7e7de3f929830133893c22a2ddd28ca8"),
             (0x13e0, 43, "ba9f487114a7f0870bc8ec0fbcbe0a5d82d6d833150c7d783a79874674417f63"),
             (0x47c60, 123, "c24e8aaed4de58907df11c265260404d68e8b92e1a6373d11e2db8e73238e755"))

class LuaMachine(api.Machine):
    def __init__(self, executable, instruction_map=None, *, allocator_returns=ALLOCATOR_RETURNS):
        self.executable = Path(executable)
        self.allocator_returns = frozenset(allocator_returns)
        super().__init__(api.OriginalSource(self.executable))
        data = (self.executable.parent / "lua5.1.dll").read_bytes()
        api.require(api.sha(data) == DLL_SHA, "DLL identity differs")
        self.dll_raw, self.dll = data, PEImage(data)
        api.require(self.dll.bits == 32 and self.dll.image_base == 0x10000000, "DLL layout differs")
        size = max(s.virtual_address + max(s.virtual_size, s.raw_size) for s in self.dll.sections)
        size = (size + 4095) & ~4095
        self.dll_memory = bytearray(size)
        self.dll_memory[:self.dll.size_of_headers] = data[:self.dll.size_of_headers]
        for section in self.dll.sections:
            self.dll_memory[section.virtual_address:section.virtual_address + section.raw_size] = \
                data[section.raw_offset:section.raw_offset + section.raw_size]
        reloc_rva, reloc_size = self.dll.data_directories[5]
        cursor, self.relocations = reloc_rva, []
        while cursor < reloc_rva + reloc_size:
            page, length = struct.unpack_from("<II", self.dll_memory, cursor)
            api.require(length >= 8 and length % 2 == 0 and cursor + length <= reloc_rva + reloc_size,
                        "invalid relocation block")
            for pos in range(cursor + 8, cursor + length, 2):
                word = struct.unpack_from("<H", self.dll_memory, pos)[0]
                kind, offset = word >> 12, word & 4095
                if kind == 0:
                    continue
                api.require(kind == 3, "unsupported PE relocation type")
                at = page + offset
                old = struct.unpack_from("<I", self.dll_memory, at)[0]
                new = (old + DLL_BASE - self.dll.image_base) & 0xffffffff
                struct.pack_into("<I", self.dll_memory, at, new)
                api.require(0 <= at <= size - 4, "relocation outside DLL image")
                api.require(at not in {r["rva"] for r in self.relocations}, "duplicate relocation target")
                self.relocations.append(dict(rva=at, before=old, after=new))
            cursor += length
        api.require(cursor == reloc_rva + reloc_size and len(self.relocations) == 5595, "relocation extent/count differs")
        self.relocation_sha256 = api.sha(api.canonical(self.relocations))
        api.require(self.relocation_sha256 == RELOCATION_MAP_SHA, "relocation map identity differs")
        self.uc.mem_map(DLL_BASE, size)
        self.uc.mem_write(DLL_BASE, bytes(self.dll_memory))
        for i, row in enumerate(self.dll.imports()):
            stub = api.IMPORT + 0x4000 + i * 16
            api.require(stub not in self.stubs and stub < ALLOC, "import address collision")
            self.stubs[stub] = {**row, "module": "lua5.1.dll"}
            self.put(DLL_BASE + int(row["iat_rva"], 16), stub)
        self.exports = self.export_map()
        self.bound_lua_imports = []
        for row in self.source.image.imports():
            if row["library"].lower() != "lua5.1.dll":
                continue
            api.require(row["name"] in self.exports, "EXE Lua import has no original export")
            rva = self.exports[row["name"]]
            self.put(api.BASE + int(row["iat_rva"], 16), DLL_BASE + rva)
            self.bound_lua_imports.append(dict(name=row["name"], exe_iat_rva=row["iat_rva"], dll_export_rva=rva))
        for section in self.dll.sections:
            if section.executable:
                self.uc.mem_protect((DLL_BASE + section.virtual_address) & ~4095,
                    (max(section.virtual_size, section.raw_size) + 4095) & ~4095,
                    self.u.UC_PROT_READ | self.u.UC_PROT_EXEC)
        self.dll_points = {}
        self.instruction_map = instruction_map
        self.allocator_calls = []
        # Explicit external allocator callback seam, never original DLL code.
        # A real RET bounds translation before the mapped callback page ends.
        self.uc.mem_write(ALLOC, b"\xc3")
        # Original _setjmp3 at DLL47c60 reads FS:[0], compares -1 at47c8f,
        # and takes its explicit empty-SEH-list branch. No custom handlers.
        self.put(0, 0xffffffff)

    def invalid(self, uc, kind, at, width, value, user):
        self.fail(f"unmapped/protected memory kind={kind}, address={at:#x}, width={width}, pc={uc.reg_read(self.x.UC_X86_REG_EIP):#x}")
        return False

    def export_map(self):
        er, es = self.dll.data_directories[0]
        fields = struct.unpack_from("<IIHHIIIIIII", self.dll_memory, er)
        _, _, _, _, _, _, _, nn, functions, names, ordinals = fields
        exports = {}
        for i in range(nn):
            name_rva = struct.unpack_from("<I", self.dll_memory, names + 4 * i)[0]
            end = self.dll_memory.index(0, name_rva)
            name = self.dll_memory[name_rva:end].decode("ascii")
            ordinal = struct.unpack_from("<H", self.dll_memory, ordinals + 2 * i)[0]
            rva = struct.unpack_from("<I", self.dll_memory, functions + 4 * ordinal)[0]
            api.require(not er <= rva < er + es, "forwarded DLL export unsupported")
            exports[name] = rva
        return exports

    def step(self, uc, at, size, user):
        try:
            if at == ALLOC:
                self.allocate_callback()
                return
            rva = at - DLL_BASE
            if 0 <= rva < len(self.dll_memory):
                api.require(any(s.executable and s.virtual_address <= rva
                    and rva + size <= s.virtual_address + s.raw_size for s in self.dll.sections),
                    "DLL instruction outside file-backed executable code")
                expected = bytes(self.dll_memory[rva:rva + size])
                api.require(bytes(uc.mem_read(at, size)) == expected, "relocated DLL instruction differs")
                decoded = list(self.source.decoder.disasm(expected, at, count=1))
                api.require(len(decoded) == 1 and decoded[0].size == size, "DLL decoder extent differs")
                raw_offset = self.dll.rva_to_file_offset(rva)
                observed = dict(size=size, raw_sha256=api.sha(self.dll_raw[raw_offset:raw_offset + size]))
                if self.instruction_map is not None:
                    api.require(self.instruction_map.get(str(rva)) == observed, "DLL instruction outside frozen admission map")
                self.dll_points[str(rva)] = observed
                self.trace.append(["lua5.1.dll", rva, size])
                return
            super().step(uc, at, size, user)
        except Exception as exc:
            self.fail(exc)

    def allocate_callback(self):
        esp = self.uc.reg_read(self.x.UC_X86_REG_ESP)
        api.require(api.STACK <= esp < api.STACK + 0x10000 - 20, "allocator stack invalid")
        ret = self.get(esp)
        api.require(ret - DLL_BASE in self.allocator_returns, "allocator caller outside frozen seams")
        api.require(self.trace and self.trace[-1][0] == "lua5.1.dll", "allocator call trace missing")
        _, call_rva, call_size = self.trace[-1]
        api.require(call_rva + call_size == ret - DLL_BASE, "allocator return does not follow original instruction")
        opcode = bytes(self.dll_memory[call_rva:call_rva + call_size])
        ins = list(self.source.decoder.disasm(opcode, DLL_BASE + call_rva, count=1))
        api.require(len(ins) == 1 and ins[0].mnemonic == "call", "allocator seam is not original call")
        ud, ptr, old_size, new_size = [self.get(esp + 4 + i * 4) for i in range(4)]
        api.require(ud == UD and new_size < 0x100000, "allocator premise differs")
        if ptr:
            api.require(ptr in self.live and self.allocations[ptr] == old_size, "allocator ownership/old size differs")
        else:
            api.require(old_size == 0, "null allocator pointer has nonzero old size")
        result = 0
        if new_size:
            result = self.next_alloc
            self.next_alloc += (new_size + 15) & ~15
            api.require(self.next_alloc < api.HEAP + 0x400000, "allocator heap exhausted")
            self.allocations[result] = new_size
            self.allocation_starts.append(result)
            self.live.add(result)
            if ptr:
                self.uc.mem_write(result, bytes(self.uc.mem_read(ptr, min(old_size, new_size))))
        if ptr:
            self.live.remove(ptr)
        self.allocator_calls.append(dict(caller_dll_rva=ret - DLL_BASE, arguments=[ud, ptr, old_size, new_size], result=result))
        self.uc.reg_write(self.x.UC_X86_REG_EAX, result)
        self.uc.reg_write(self.x.UC_X86_REG_ESP, esp + 4)
        self.uc.reg_write(self.x.UC_X86_REG_EIP, ret)

    def cdecl(self, name, args):
        entry = self.exports[name]
        self.trace, self.imports, self.failure = [], [], None
        allocation_start = len(self.allocator_calls)
        esp = api.STACK + 0x8000
        self.put(esp, api.RETURN)
        for i, arg in enumerate(args):
            self.put(esp + 4 + i * 4, arg)
        self.uc.reg_write(self.x.UC_X86_REG_ESP, esp)
        self.uc.reg_write(self.x.UC_X86_REG_ECX, 0)
        self.uc.reg_write(self.x.UC_X86_REG_EFLAGS, 0x202)
        try:
            self.uc.emu_start(DLL_BASE + entry, api.RETURN + 1, count=api.LIMIT, timeout=10_000_000)
        except Exception as exc:
            self.fail(exc)
        returned = self.uc.reg_read(self.x.UC_X86_REG_EIP) == api.RETURN
        stack_ok = self.uc.reg_read(self.x.UC_X86_REG_ESP) == esp + 4
        result = dict(name=name, dll_rva=entry, arguments=args, returned=returned, cdecl_stack_ok=stack_ok,
            eax=self.uc.reg_read(self.x.UC_X86_REG_EAX), instructions=len(self.trace),
            failure=self.failure if self.failure else None, trace=self.trace,
            imports=self.imports, allocator_calls=self.allocator_calls[allocation_start:])
        if not returned and not result["failure"]:
            result["failure"] = "instruction/time limit exhausted"
        return result

def run_case(executable, case, admission):
    machine = LuaMachine(executable, admission)
    calls, observations = [], {}
    def dll(name, args):
        row = machine.cdecl(name, args)
        calls.append(row)
        api.require(row["returned"] and row["cdecl_stack_ok"] and row["failure"] is None,
                    "original DLL call did not return within declared boundary")
        return row["eax"]
    def game(entry, args, receiver, edx=0):
        begin = len(machine.allocator_calls)
        machine.uc.reg_write(machine.x.UC_X86_REG_EDX, edx)
        failure = None
        try:
            summary = machine.call(entry, args, receiver=receiver)
        except Exception as exc:
            failure = str(exc)
            summary = machine.diagnostic()
        row = dict(module="Breach.exe", entry_rva=entry, arguments=args, ecx=receiver, edx=edx,
                   failure=failure, summary=summary, trace=list(machine.trace),
                   imports=list(machine.imports), allocator_calls=machine.allocator_calls[begin:],
                   eax=machine.uc.reg_read(machine.x.UC_X86_REG_EAX))
        calls.append(row)
        api.require(failure is None, "original game wrapper did not return")
        return row["eax"]
    status, failure = "failed", None
    try:
        for rva, size, digest in BODY_PINS:
            at = machine.dll.rva_to_file_offset(rva)
            api.require(api.sha(machine.dll_raw[at:at + size]) == digest, "DLL body pin differs")
        state = dll("lua_newstate", [ALLOC, UD])
        api.require(state in machine.live, "constructor returned no live owned state")
        api.require(dll("lua_gettop", [state]) == 0, "new state stack is not empty")
        value = case["value"]
        dll("lua_pushinteger", [state, value & 0xffffffff])
        dll("lua_pushvalue", [state, 0xffffffff])
        api.require(dll("lua_gettop", [state]) == 2, "duplicate stack depth differs")
        api.require(dll("lua_type", [state, 0xffffffff]) == 3, "duplicate is not a Lua number")
        api.require(dll("lua_tointeger", [state, 0xffffffff]) == value & 0xffffffff, "duplicate integer differs")
        dll("lua_settop", [state, 0])
        key = b"ProbeValue"
        key_ptr, obj, value_obj = api.BOARD + 0x9000, api.BOARD + 0x9100, api.BOARD + 0x9200
        machine.uc.mem_write(key_ptr, key + b"\0")
        if case["define_marker"]:
            dll("lua_pushinteger", [state, value & 0xffffffff])
            dll("lua_setfield", [state, -10002 & 0xffffffff, key_ptr])
        api.require(game(0x6c3e0, [], obj, state) == obj and machine.get(obj) == state,
                    "global registry wrapper differs")
        global_ref = machine.get(obj + 4)
        machine.put(0x896048, state)
        words = list(struct.unpack("<IIII", (key + b"\0").ljust(16, b"\0"))) + [len(key), 15]
        api.require(game(0x4e800, words, value_obj) == value_obj and machine.get(value_obj + 0x18) == state,
                    "value wrapper receiver/state differs")
        value_ref = machine.get(value_obj + 0x1c)
        dll("lua_rawgeti", [state, -10000 & 0xffffffff, global_ref])
        global_type = dll("lua_type", [state, 0xffffffff])
        api.require(global_type == 5, "global handle is not a table")
        dll("lua_settop", [state, 0])
        dll("lua_rawgeti", [state, -10000 & 0xffffffff, value_ref])
        value_type = dll("lua_type", [state, 0xffffffff])
        integer_bits = dll("lua_tointeger", [state, 0xffffffff])
        expected_type = 3 if case["define_marker"] else 0
        expected_bits = value & 0xffffffff if case["define_marker"] else 0
        api.require(value_type == expected_type and integer_bits == expected_bits, "typed registry value differs")
        dll("lua_settop", [state, 0])
        dll("luaL_unref", [state, -10000 & 0xffffffff, global_ref])
        dll("luaL_unref", [state, -10000 & 0xffffffff, value_ref])
        api.require(dll("lua_gettop", [state]) == 0, "wrappers leaked stack entries")
        observations.update(global_type=global_type, value_type=value_type,
            value_integer=integer_bits if integer_bits < 0x80000000 else integer_bits - 0x100000000,
            final_stack_depth=0, global_ref=global_ref, value_ref=value_ref)
        dll("lua_close", [state])
        api.require(not machine.live, "close left live Lua allocations")
        status = "complete"
    except Exception as exc:
        failure = str(exc)
    private = dict(case=case, status=status, failure=failure, observations=observations, calls=calls,
        allocations=machine.allocator_calls, remaining_allocations=len(machine.live),
        dll_instruction_admission=machine.dll_points, relocations=machine.relocations)
    return private, machine


def run(executable, private_dir, *, exploratory=False):
    private_dir = Path(private_dir)
    api.require(not private_dir.exists(), "private directory is create-only")
    private_dir.mkdir(parents=True)
    map_raw = None if exploratory else INSTRUCTION_MAP.read_bytes()
    api.require(exploratory or api.sha(map_raw) == INSTRUCTION_MAP_SHA, "frozen instruction map identity differs")
    admission = None if exploratory else json.loads(map_raw)["instructions"]
    if admission is not None:
        api.require(json.loads(map_raw)["dll_sha256"] == DLL_SHA, "admission map DLL differs")
    code_paths = ["src/observatory/solver_first_lua_vm.py", "scripts/solver_first_lua_vm.py",
                  "src/observatory/solver_first_path_oracle.py", "src/observatory/pe_anchor_map.py"]
    source_pins = {p: api.sha((api.ROOT / p).read_bytes().replace(b"\r\n", b"\n")) for p in code_paths}
    runtime = api.runtime_identity()
    cases, instructions, machines = [], {}, []
    for case in [dict(id="positive", value=37, define_marker=True),
                 dict(id="negative", value=-7, define_marker=True),
                 dict(id="missing_nil", value=0, define_marker=False)]:
        private, machine = run_case(executable, case, admission)
        machines.append(machine)
        path = private_dir / (case["id"] + ".json")
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(private, handle, indent=2, sort_keys=True)
            handle.write("\n")
        instructions.update(machine.dll_points)
        cases.append(dict(case=case, status=private["status"], failure=private["failure"],
            observations=private["observations"], call_count=len(private["calls"]),
            allocator_call_count=len(machine.allocator_calls), remaining_allocations=len(machine.live),
            import_counts=dict(Counter(row["name"] for call in private["calls"] for row in call["imports"])),
            private_receipt_sha256=api.sha(path.read_bytes())))
    api.require(source_pins == {p: api.sha((api.ROOT / p).read_bytes().replace(b"\r\n", b"\n"))
                               for p in code_paths}, "tool source changed during acquisition")
    api.require(api.runtime_identity() == runtime, "runtime changed during acquisition")
    api.require(exploratory or INSTRUCTION_MAP.read_bytes() == map_raw, "instruction map changed during acquisition")
    api.require(api.sha(Path(executable).read_bytes()) == api.EXE_SHA and
                api.sha((Path(executable).parent / "lua5.1.dll").read_bytes()) == DLL_SHA,
                "original binaries changed during acquisition")
    report = dict(schema_version=1, corpus_version="s1-original-lua-registry-development-v1",
        baseline_solver_commit="84c186ae440163056c5c39b9aea9c20e6f49983e", game_build=13725832,
        information_mode="synthetic offline oracle storage; no fair player admission",
        objective="original VM/registry typed observations and normal allocator ownership closure",
        original_EXE_body_identities=[machines[0].source.verified[rva] for rva in (0x6c3e0, 0x4e800)],
        original_DLL_body_pins=[dict(rva=rva, size=size, raw_sha256=digest) for rva, size, digest in BODY_PINS],
        evidence_class="bounded original DLL and EXE bodies with genuine guest VM and supplied allocator",
        executable_sha256=api.EXE_SHA, dll_sha256=DLL_SHA, runtime=runtime, source_lf_sha256=source_pins,
        attempted=len(cases), admitted=sum(c["status"] == "complete" for c in cases),
        matched=sum(c["status"] == "complete" for c in cases),
        failed=sum(c["status"] != "complete" for c in cases), excluded=0, cases=cases,
        relocation_count=len(machines[0].relocations), relocation_map_sha256=machines[0].relocation_sha256,
        relocated_base=DLL_BASE, bound_exe_lua_imports=machines[0].bound_lua_imports,
        allocator_return_rvas=sorted(ALLOCATOR_RETURNS), instruction_admission_mode="exploratory" if exploratory else "frozen observed instruction map",
        instruction_admission_sha256=None if exploratory else api.sha(map_raw),
        executed_DLL_instruction_points=len(instructions),
        supplied_boundaries=["Normal successful custom lua_Alloc callback; allocator is supplied, original Lua initialization and APIs execute unchanged.",
            "FS:[0]=ffffffff follows original empty-SEH-list branch; default luaL_newstate/CRT loader startup is unacquired.",
            "Actual Lua global ProbeValue is synthetic positive/negative/nil development input; source-correct emitter tables are not loaded.",
            "Mapped Board scratch objects and inline MSVC string records are supplied; game registry/value wrapper bodies execute unchanged.",
            "DLL instruction map freezes observed decoded paths, not a function atlas or universal Lua correctness proof.",
            "Private ordered instruction/import/allocator traces are retained; no full ordered read/write or whole-native-state comparison is claimed."],
        original_completed_action_transitions=0, full_turn_original_comparisons=0,
        held_out_cases=0, fair_input_admissions=0, gate_promotions=0, ledger_promotions=0,
        next_blocker="Stock Ground emitter Lua definitions and actual image/resource objects, then loaded Move/dispatch context and joined N2 action settlement.")
    return report, dict(schema_version=1, dll_sha256=DLL_SHA, instructions=instructions,
                        provenance="exploratory positive/negative/nil VM and game-wrapper paths, source bytes independently checked")
