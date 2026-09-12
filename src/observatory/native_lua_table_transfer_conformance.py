"""Native two-value Lua transfer helper with supplied normal API responses."""

from __future__ import annotations
import hashlib
import itertools
import json
from pathlib import Path
from src.observatory import native_lua_table_transfer_semantics as model
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _load_executable,
    _decode_body,
    _point,
    _source_identity,
    _canonical_bytes,
    _canonical_sha256,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "pe_native_lua_table_transfer_conformance"
SEALED_SHA256 = "c592340aaef40157af3330b0bdf096441ff7a3f25fa12902ce7f023e81772063"
SOURCE_PINS = {
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
    "class_chain": (
        "pe_native_lua_class_return_helper_chain",
        "33ad87a98131700dce12bd34a7febea3159b6f461710f0b8296d95ded1b37095",
    ),
}
START, END = 0x2EC050, 0x2EC104
BODY_SHA256 = "858858c41d39d402bbe07a163aa922c44453c99e6cae68c8b14437ee9d41328e"
STACK, RETURN, IMPORT = 0x02000000, 0x04000000, 0x05000000
LITERALS = {BASE + 0x420F68: b"__init\0", BASE + 0x43C50C: b"__finalize\0"}
APIS = (
    "lua_pushnil",
    "lua_next",
    "lua_pushstring",
    "lua_equal",
    "lua_settop",
    "lua_pushvalue",
    "lua_insert",
    "lua_settable",
)
TARGETS = {name: IMPORT + 0x100 * i for i, name in enumerate(APIS)}
SLOTS = {
    "lua_pushnil": 0x3D64B8,
    "lua_next": 0x3D64B4,
    "lua_pushstring": 0x3D6494,
    "lua_equal": 0x3D64C4,
    "lua_settop": 0x3D6510,
    "lua_pushvalue": 0x3D64E4,
    "lua_insert": 0x3D6514,
    "lua_settable": 0x3D6550,
}
CALLS = {
    0x2EC054: ("lua_pushnil", None),
    0x2EC05D: ("lua_next", None),
    0x2EC086: ("lua_pushstring", "ebx"),
    0x2EC08D: ("lua_equal", None),
    0x2EC09D: ("lua_settop", "edi"),
    0x2EC0A7: ("lua_settop", "edi"),
    0x2EC0AF: ("lua_pushstring", "ebx"),
    0x2EC0B6: ("lua_equal", None),
    0x2EC0C6: ("lua_settop", "edi"),
    0x2EC0D0: ("lua_settop", "edi"),
    0x2EC0D5: ("lua_pushvalue", None),
    0x2EC0DE: ("lua_insert", None),
    0x2EC0E7: ("lua_settable", None),
    0x2EC0F3: ("lua_next", None),
}
ConformanceError = model.TransferError


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    return [
        dict(kinds=list(kinds), alignment=alignment, prefix_length=length)
        for count in range(4)
        for kinds in itertools.product(model.KINDS, repeat=count)
        for alignment in (0, 1, 7, 15)
        for length in (0, 3)
    ]


def _model_contract():
    contract = [
        dict(
            kinds=list(kinds),
            prefix_length=length,
            relation=model.transfer_requests(list(kinds), length),
        )
        for count in range(4)
        for kinds in itertools.product(model.KINDS, repeat=count)
        for length in (0, 3)
    ]

    return json.loads(json.dumps(contract))


def _fixture(vector, *, caller=None):
    a, length = vector["alignment"], vector["prefix_length"]
    _require(
        type(a) is int
        and a in (0, 1, 7, 15)
        and type(length) is int
        and length in (0, 1, 3),
        "invalid transfer frame geometry",
    )
    _require(
        type(vector["kinds"]) is list and len(vector["kinds"]) <= 3,
        "invalid transfer iterator bound",
    )
    relation = model.transfer_requests(vector["kinds"], length)
    entry = STACK + 0x2000 + a
    initial = {
        r: (0x11223344 + i * 0x1111111 + a) & 0xFFFFFFFF
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    initial.update(ecx=0x01001000 + 32 * a + length, esp=entry)
    endpoint = RETURN + 0x100 + 16 * length + a
    pages = {
        STACK
        + 4096
        * j: bytearray((i * 37 + j * 13 + (i >> 3) + 0x71) % 256 for i in range(4096))
        for j in range(4)
    }
    for literal in LITERALS:
        pages[literal & ~0xFFF] = bytearray((i * 11 + 0x69) % 256 for i in range(4096))
    iat_page = (BASE + SLOTS["lua_next"]) & ~0xFFF
    pages[iat_page] = bytearray((i * 17 + 0xA3) % 256 for i in range(4096))

    def put(address, value, width=4):
        for i, b in enumerate(value.to_bytes(width, "little")):
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = b

    put(entry, endpoint)
    for literal, payload in LITERALS.items():
        for i, b in enumerate(payload):
            put(literal + i, b, 1)
    for name, slot in SLOTS.items():
        put(BASE + slot, TARGETS[name])
    fixture = dict(
        entry=entry,
        registers=initial,
        pages={p: bytes(v) for p, v in pages.items()},
        endpoint=endpoint,
        relation=relation,
        iat_page=iat_page,
    )
    if caller is not None:
        _require(
            type(caller) is dict
            and set(caller) == {"entry", "return_address", "registers", "stack_pages"},
            "invalid transfer caller fields",
        )
        reserved = {
            (BASE + START) & ~0xFFF,
            IMPORT,
            iat_page,
            *{literal & ~0xFFF for literal in LITERALS},
        }
        supplied = caller["stack_pages"]
        _require(
            type(supplied) is dict and bool(supplied), "invalid transfer caller pages"
        )
        _require(
            all(type(p) is int and p not in reserved for p in supplied),
            "transfer caller pages alias reserved storage",
        )
        fixture.update(
            entry=caller["entry"],
            endpoint=caller["return_address"],
            registers=(
                dict(caller["registers"])
                if type(caller["registers"]) is dict
                else caller["registers"]
            ),
            pages={
                **{
                    p: v
                    for p, v in fixture["pages"].items()
                    if not STACK <= p < STACK + 0x4000
                },
                **supplied,
            },
        )
    _check_fixture(vector, fixture)
    return fixture


def _check_fixture(vector, fixture):
    entry, endpoint = fixture["entry"], fixture["endpoint"]
    _require(type(entry) is int and 48 <= entry < 2**32 - 4, "invalid transfer entry")
    _require(
        type(endpoint) is int and 0 <= endpoint < 2**32, "invalid transfer endpoint"
    )
    _require(
        not BASE + START <= endpoint < BASE + END and endpoint & ~0xFFF != IMPORT,
        "transfer endpoint aliases executed code",
    )
    regs = fixture["registers"]
    _require(
        type(regs) is dict
        and set(regs) == {"eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"}
        and all(type(v) is int and 0 <= v < 2**32 for v in regs.values())
        and regs["esp"] == entry
        and regs["ecx"] != 0,
        "invalid transfer caller registers",
    )
    pages = fixture["pages"]
    _require(
        type(pages) is dict
        and all(
            type(p) is int
            and 0 <= p <= 2**32 - 4096
            and p % 4096 == 0
            and type(v) is bytes
            and len(v) == 4096
            for p, v in pages.items()
        ),
        "invalid transfer mapped pages",
    )
    execution = {(BASE + START) & ~0xFFF, endpoint & ~0xFFF, IMPORT}
    _require(
        not execution.intersection(pages), "transfer execution pages alias storage"
    )
    _require(
        fixture["iat_page"] == (BASE + SLOTS["lua_next"]) & ~0xFFF,
        "transfer IAT page differs",
    )
    reserved = {
        *{(BASE + slot) & ~0xFFF for slot in SLOTS.values()},
        *{literal & ~0xFFF for literal in LITERALS},
    }
    _require(
        all(
            a & ~0xFFF in pages and a & ~0xFFF not in reserved
            for a in range(entry - 48, entry + 4)
        ),
        "transfer frame outside distinct mapped stack",
    )

    def raw(address, size):
        _require(
            all((address + i) & ~0xFFF in pages for i in range(size)),
            "transfer read outside mapped storage",
        )
        return bytes(
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] for i in range(size)
        )

    _require(
        int.from_bytes(raw(entry, 4), "little") == endpoint,
        "transfer caller return word differs",
    )
    _require(
        all(raw(a, len(v)) == v for a, v in LITERALS.items()),
        "transfer mapped literal differs",
    )
    _require(
        all(
            int.from_bytes(raw(BASE + slot, 4), "little") == TARGETS[name]
            for name, slot in SLOTS.items()
        ),
        "transfer mapped IAT differs",
    )
    _require(
        fixture["relation"]
        == model.transfer_requests(vector["kinds"], vector["prefix_length"]),
        "transfer caller relation differs",
    )


def _response(vector, record, index):
    return dict(
        eax=(
            record["truth"]
            if record["truth"] is not None
            else (0x91A2B300 + 17 * index + vector["alignment"]) & 0xFFFFFFFF
        ),
        ecx=0xA0000000 + 256 * vector["alignment"] + index,
        edx=0xB0000000 + 256 * vector["prefix_length"] + index,
        eflags=0x202 | ((index * 0x95) & 0x8D5),
    )


def _expected(vector, fixture):
    _check_fixture(vector, fixture)
    entry = fixture["entry"]
    regs = dict(fixture["registers"])
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    events, calls = [], []

    def write(address, value):
        events.append(dict(access="write", address=address, width=4, value=value))
        for i, b in enumerate(value.to_bytes(4, "little")):
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = b

    def read(address, value):
        events.append(dict(access="read", address=address, width=4, value=value))

    def push(value):
        regs["esp"] -= 4
        write(regs["esp"], value & 0xFFFFFFFF)

    def pop(register, offset):
        _require(regs["esp"] == entry + offset, "transfer saved frame differs")
        read(regs["esp"], fixture["registers"][register])
        regs[register] = fixture["registers"][register]
        regs["esp"] += 4

    def call(site, *args):
        name, staged = CALLS[site]
        index = len(calls)
        record = fixture["relation"]["calls"][index]
        logical = [
            (
                next(a for a, p in LITERALS.items() if p[:-1].decode() == arg)
                if type(arg) is str
                else arg & 0xFFFFFFFF
            )
            for arg in record["arguments"]
        ]
        native = [arg & 0xFFFFFFFF for arg in args]
        _require(
            record["api"] == name and native == logical,
            "independent transfer API request differs",
        )
        arguments = [fixture["registers"]["ecx"], *native]
        for value in reversed(arguments):
            push(value)
        if staged:
            _require(regs[staged] == TARGETS[name], "transfer staged target differs")
        else:
            read(BASE + SLOTS[name], TARGETS[name])
        continuation = BASE + site + (2 if staged else 6)
        push(continuation)
        response = _response(vector, record, index + 1)
        calls.append(
            dict(
                site_rva=f"0x{site:08x}",
                api=name,
                target=TARGETS[name],
                entry_esp=regs["esp"],
                arguments=arguments,
                continuation=continuation,
                entry_registers=dict(regs),
                response=response,
                lua_top_before=len(record["before"]),
                lua_top_after=len(record["after"]),
            )
        )
        regs.update({k: response[k] for k in ("eax", "ecx", "edx")})
        regs["esp"] += 4

    push(regs["esi"])
    regs["esi"] = fixture["registers"]["ecx"]
    call(0x2EC054)
    call(0x2EC05D, -2)
    regs["esp"] += 12
    frames = [-12, -20]
    if vector["kinds"]:
        push(regs["ebx"])
        read(BASE + SLOTS["lua_pushstring"], TARGETS["lua_pushstring"])
        regs["ebx"] = TARGETS["lua_pushstring"]
        push(regs["edi"])
        read(BASE + SLOTS["lua_settop"], TARGETS["lua_settop"])
        regs["edi"] = TARGETS["lua_settop"]
        for kind in vector["kinds"]:
            call(0x2EC086, BASE + 0x420F68)
            call(0x2EC08D, -1, -3)
            regs["esp"] += 20
            frames.extend([-24, -36])
            if kind == "init":
                call(0x2EC09D, -3)
                regs["esp"] += 8
                frames.append(-24)
            else:
                call(0x2EC0A7, -2)
                call(0x2EC0AF, BASE + 0x43C50C)
                call(0x2EC0B6, -1, -3)
                regs["esp"] += 28
                frames.extend([-24, -32, -44])
                if kind == "finalize":
                    call(0x2EC0C6, -3)
                    regs["esp"] += 8
                    frames.append(-24)
                else:
                    call(0x2EC0D0, -2)
                    call(0x2EC0D5, -2)
                    call(0x2EC0DE, -2)
                    call(0x2EC0E7, -5)
                    regs["esp"] += 32
                    frames.extend([-24, -32, -40, -48])
            call(0x2EC0F3, -2)
            regs["esp"] += 8
            frames.append(-24)
        pop("edi", -12)
        pop("ebx", -8)
    pop("esi", -4)
    read(entry, fixture["endpoint"])
    regs["esp"] += 4
    _require(
        regs["eax"] == 0
        and regs["esp"] == entry + 4
        and len(calls) == fixture["relation"]["api_count"],
        "transfer normal return relation differs",
    )
    _require(
        [c["entry_esp"] - entry for c in calls] == frames,
        "transfer cdecl frame equations differ",
    )
    return dict(
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        calls=calls,
        flags=0x44,
        flag_mask=0x8C5,
        endpoint=fixture["endpoint"],
        relation=fixture["relation"],
    )


def _run_case(code, points, vector, negative=None, *, fixture=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector) if fixture is None else fixture
    expected = _expected(vector, fixture)
    m = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, payload in fixture["pages"].items():
        m.mem_map(page, 4096)
        m.mem_write(page, payload)
    for page in sorted({(BASE + START) & ~0xFFF, fixture["endpoint"] & ~0xFFF, IMPORT}):
        m.mem_map(page, 4096)
        m.mem_write(page, b"\xcc" * 4096)
    m.mem_write(BASE + START, code)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in fixture["registers"]}
    for r, v in fixture["registers"].items():
        m.reg_write(ids[r], v)
    m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(p["rva"], 16) for p in points}
    visited, events, summaries = [], [], []
    resume = None

    def on_code(machine, address, size, user):
        nonlocal resume
        if address in TARGETS.values():
            _require(
                len(summaries) < len(expected["calls"]), "unexpected transfer API call"
            )
            call = expected["calls"][len(summaries)]
            sp = machine.reg_read(x.UC_X86_REG_ESP)
            if negative == "argument" and not summaries:
                machine.mem_write(
                    sp + 4, (call["arguments"][0] ^ 1).to_bytes(4, "little")
                )
            words = [
                int.from_bytes(machine.mem_read(sp + 4 * i, 4), "little")
                for i in range(1 + len(call["arguments"]))
            ]
            _require(
                address == call["target"]
                and sp == call["entry_esp"]
                and words == [call["continuation"], *call["arguments"]],
                "transfer API arguments differ",
            )
            _require(
                {r: machine.reg_read(i) for r, i in ids.items()}
                == call["entry_registers"],
                "transfer API entry registers differ",
            )
            if call["api"] == "lua_pushstring":
                literal = call["arguments"][1]
                payload = LITERALS[literal]
                _require(
                    bytes(machine.mem_read(literal, len(payload))) == payload,
                    "transfer literal argument differs",
                )
            for r in ("eax", "ecx", "edx"):
                machine.reg_write(ids[r], call["response"][r])
            machine.reg_write(x.UC_X86_REG_EFLAGS, call["response"]["eflags"])
            machine.reg_write(x.UC_X86_REG_ESP, sp + 4)
            summaries.append(call)
            resume = call["continuation"]
            machine.emu_stop()
            return
        if (
            address == expected["endpoint"]
            or negative == "return"
            and address == (expected["endpoint"] ^ 1)
        ):
            if negative == "result":
                machine.reg_write(
                    x.UC_X86_REG_EAX, machine.reg_read(x.UC_X86_REG_EAX) ^ 0x100
                )
            machine.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "transfer escaped exact owner")
        visited.append(f"0x{pc:08x}")
        at = None
        if pc == START:
            if negative == "ancestor":
                at = fixture["entry"] + 4
            elif negative == "return":
                at = fixture["entry"]
            elif negative == "literal_padding":
                at = next(iter(LITERALS)) + 64
            elif negative == "iat_padding":
                at = fixture["iat_page"] + 16
        if pc == 0x2EC051 and negative == "saved_esi":
            at = fixture["entry"] - 4
        if pc == 0x2EC06F and negative == "saved_ebx":
            at = fixture["entry"] - 8
        if pc == 0x2EC080 and negative == "staged_ebx":
            machine.reg_write(x.UC_X86_REG_EBX, TARGETS["lua_settop"])
        if pc == 0x2EC080 and negative == "staged_edi":
            machine.reg_write(x.UC_X86_REG_EDI, TARGETS["lua_pushstring"])
        if at is not None:
            machine.mem_write(at, bytes([machine.mem_read(at, 1)[0] ^ 1]))

    def on_memory(machine, access, address, width, value, user):
        _require(width == 4, "unexpected transfer memory width")
        writing = access == uc.UC_MEM_WRITE
        events.append(
            dict(
                access="write" if writing else "read",
                address=address,
                width=width,
                value=(
                    value
                    if writing
                    else int.from_bytes(machine.mem_read(address, width), "little")
                ),
            )
        )

    m.hook_add(uc.UC_HOOK_CODE, on_code)
    m.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    pc = BASE + START
    for _ in range(len(expected["calls"]) + 1):
        resume = None
        m.emu_start(pc, 0, count=1000)
        if resume is None:
            break
        pc = resume
    _require(
        m.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "transfer endpoint differs",
    )
    registers = {r: m.reg_read(i) for r, i in ids.items()}
    flags = m.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        registers == expected["registers"]
        and flags & expected["flag_mask"] == expected["flags"]
        and not flags & 0x400,
        "transfer final ABI differs",
    )
    _require(
        events == expected["events"] and summaries == expected["calls"],
        "transfer ordered events differ",
    )
    _require(
        all(bytes(m.mem_read(p, 4096)) == v for p, v in expected["pages"].items()),
        "transfer protected memory differs",
    )
    return dict(
        vector=vector,
        assignments=expected["relation"]["assignments"],
        registers=registers,
        flags=flags & expected["flag_mask"],
        flag_mask=expected["flag_mask"],
        trace_rvas=visited,
        calls=summaries,
        events_sha256=_canonical_sha256(events),
        memory_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(v).hexdigest()
                for p, v in expected["pages"].items()
            }
        ),
    )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "transfer source partition differs")
    return {
        key: _source_identity(sources[key], *pin, key)
        for key, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    rows = _decode_body(data, image, sources["program_facts"], START)
    code = b"".join(bytes(r.bytes) for r in rows)
    points = [_point(r) for r in rows]
    _require(
        len(code) == 180 and hashlib.sha256(code).hexdigest() == BODY_SHA256,
        "transfer exact owner differs",
    )
    # The full owner digest and every import/staged target are pinned by the sealed class chain.
    chain = sources["class_chain"]
    bodies = [
        body
        for body in chain["function_bodies"]
        if body["entry_rva"] == f"0x{START:08x}"
    ]
    _require(
        len(bodies) == 1
        and bodies[0]["body_sha256"] == BODY_SHA256
        and bodies[0]["body_size"] == 180,
        "transfer chain body differs",
    )
    body = bodies[0]
    lookup = {p["rva"]: p for p in points}
    direct = {int(call["call_rva"], 16): call for call in body["direct_lua_calls"]}
    _require(
        set(direct) == {pc for pc, (_, reg) in CALLS.items() if reg is None},
        "transfer direct call partition differs",
    )
    for pc, call in direct.items():
        name, _ = CALLS[pc]
        point = lookup[f"0x{pc:08x}"]
        _require(
            call["import_name"] == name
            and int(call["iat_rva"], 16) == SLOTS[name]
            and call["instruction_sha256"] == point["sha256"]
            and call["instruction_size"] == point["size"]
            and call["library"] == "lua5.1.dll",
            "transfer direct import binding differs",
        )
    staged = body["staged_lua_dispatches"]
    _require(len(staged) == 2, "transfer staged partition differs")
    for stage in staged:
        name, reg = stage["api_name"], stage["register"]
        _require(
            name in SLOTS
            and int(stage["iat_rva"], 16) == SLOTS[name]
            and stage["library"] == "lua5.1.dll"
            and stage["stage"] == lookup[stage["stage"]["rva"]],
            "transfer staged load binding differs",
        )
        _require(
            {int(c["call"]["rva"], 16) for c in stage["call_sites"]}
            == {pc for pc, pair in CALLS.items() if pair == (name, reg)}
            and all(c["call"] == lookup[c["call"]["rva"]] for c in stage["call_sites"]),
            "transfer staged calls differ",
        )
    for literal, payload in LITERALS.items():
        offset = image.rva_to_file_offset(literal - BASE)
        _require(
            data[offset : offset + len(payload)] == payload,
            "transfer literal bytes differ",
        )
        matches = [r for r in chain["literals"] if r["text"] == payload[:-1].decode()]
        _require(
            len(matches) == 1
            and matches[0]["nul_terminated_bytes_sha256"]
            == hashlib.sha256(payload).hexdigest(),
            "transfer literal witness differs",
        )
    return code, points


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE, "transfer exact PE differs"
    )
    code, points = _load_code(data, image, sources)
    observations = [_run_case(code, points, v) for v in vectors()]
    union = sorted({pc for o in observations for pc in o["trace_rvas"]})
    _require(
        union == [p["rva"] for p in points], "transfer full native coverage differs"
    )
    _require(
        {c["site_rva"] for o in observations for c in o["calls"]}
        == {f"0x{pc:08x}" for pc in CALLS},
        "transfer all call sites not covered",
    )
    sample = dict(kinds=["other", "init", "finalize"], alignment=7, prefix_length=3)
    controls = []
    for kind, message in (
        ("ancestor", "transfer protected memory differs"),
        ("saved_esi", "transfer final ABI differs"),
        ("saved_ebx", "transfer final ABI differs"),
        ("argument", "transfer API arguments differ"),
        ("return", "transfer endpoint differs"),
        ("result", "transfer final ABI differs"),
        ("literal_padding", "transfer protected memory differs"),
        ("iat_padding", "transfer protected memory differs"),
        ("staged_ebx", "transfer API arguments differ"),
        ("staged_edi", "transfer API entry registers differ"),
    ):
        try:
            _run_case(code, points, sample, kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "transfer mutation failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("transfer mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            start_rva=f"0x{START:08x}",
            end_rva=f"0x{END:08x}",
            points=points,
            sha256=BODY_SHA256,
        ),
        literals=[
            dict(
                rva=f"0x{a-BASE:08x}", size=len(v), sha256=hashlib.sha256(v).hexdigest()
            )
            for a, v in LITERALS.items()
        ],
        model_contract=dict(
            module="native_lua_table_transfer_semantics",
            cases=len(_model_contract()),
            sha256=_canonical_sha256(_model_contract()),
        ),
        vectors=vectors(),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        executed_rvas=union,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            instruction_bytes=len(code),
            static_sites=len(points),
            executed_sites=len(union),
            call_sites=len(CALLS),
            imported_functions=len(TARGETS),
            supplied_api_returns=sum(len(o["calls"]) for o in observations),
            assignment_requests=sum(len(o["assignments"]) for o in observations),
            iterations=sum(len(v["kinds"]) for v in vectors()),
            max_iterations=3,
            native_lua_api_instructions=0,
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact native two-value transfer helper through normal caller return under supplied Lua API contracts",
            premises=[
                "All category sequences of length zero through three and two entry prefix lengths; independent abstract stack model checks retained iterator, filtered keys and settable requests",
                "All native owner instructions and fourteen direct or staged call sites execute; EBX and EDI bind stable pushstring and settop targets",
                "Supplied normal cdecl API responses preserve complete mapped native memory and nonvolatile registers, vary volatile outputs and keep DF clear",
                "Every retained argument group, saved register, import page, literal page, return word and final EAX zero is checked",
            ],
            not_claimed=[
                "Actual Lua DLL, VM, destination mutation, metamethod execution, errors or nonlocal exits, arbitrary iterator sizes, hardware execution or accounting promotion"
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "transfer executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    _validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors()
        and evidence["model_contract"]["sha256"]
        == _canonical_sha256(_model_contract()),
        "sealed native transfer differs",
    )
    _assert_publication_safe(evidence)
    return dict(
        status="structurally_verified",
        evidence_sha256=SEALED_SHA256,
        summary=evidence["summary"],
    )


def build_conformance(executable, sources):
    result = _build_unsealed(executable, sources)
    validate_structure(result, sources)
    return result


def validate_conformance(executable, evidence, sources):
    validate_structure(evidence, sources)
    _require(
        _canonical_bytes(build_conformance(executable, sources))
        == _canonical_bytes(evidence),
        "exact native transfer differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
