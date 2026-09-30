"""Finite normal factory execution, stopped before native initializer execution."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
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

ANALYSIS_KIND = "pe_native_lua_class_factory_prefix_conformance"
SEALED_SHA256 = "cebf742aac9945f22829e2d3b1b387ff618840217b3c9a2330a8335ca3a0d0ed"
START, END, INITIALIZER = 0x2EC220, 0x2EC307, 0x2EACF0
OWNER_SHA256 = "8a9c01de90919d67efa728e4ed9e41e9f9d68fa7f0faf0e8abbdd809cce91f9e"
PREFIX_SHA256 = "e2c23a81fc721e20d333ada784b7e7c7dd7660782794b8e510ba824c311b299f"
SOURCE_PINS = {
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
    "factory_chain": (
        "pe_native_lua_class_factory_chain",
        "824883dddbf0573c26c556d19501027c01b3031d1723ac8a493374bbf63204fc",
    ),
    "initializer_chain": (
        "pe_native_lua_class_initializer_chain",
        "799ab272966a317f27c0fbaf25df7d47821650a6f5e0b1a914c98eb40dcfece9",
    ),
}
SLOTS = dict(
    lua_gettop=0x3D650C,
    lua_type=0x3D64FC,
    lua_isnumber=0x3D6480,
    lua_tolstring=0x3D6500,
    lua_objlen=0x3D64A8,
    lua_newuserdata=0x3D6528,
    lua_pushstring=0x3D6494,
)
IMPORT = 0x05000000
TARGETS = {name: IMPORT + 0x100 * (i + 1) for i, name in enumerate(sorted(SLOTS))}
STACK, FIRST, SECOND, USERDATA = 0x30000000, 0x13000000, 0x15000000, 0x14000000
COOKIE = BASE + 0x493F28
REGISTERS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
ERROR_RANGES = ((0x2EC281, 0x2EC293), (0x2EC2BF, 0x2EC2D1))
FLAG_MASK = 0x8C5  # TEST defines CF, PF, ZF, SF and OF; AF is undefined.


class ConformanceError(RuntimeError):
    pass


def _require(condition, reason):
    if not condition:
        raise ConformanceError(reason)


def vectors():
    result = []
    for length in (0, 1, 2, 15, 16, 255):
        for pattern in ("ascii", "low", "high"):
            for alignment in (0, 7, 4095):
                for equal in (False, True):
                    for profile in (0, 1):
                        result.append(
                            dict(
                                length=length,
                                pattern=pattern,
                                name_alignment=alignment,
                                equal_pointers=equal,
                                profile=profile,
                            )
                        )
    return result


def _name(vector):
    n = vector["length"]
    payload = dict(ascii=b"Class", low=b"\x01\x02", high=b"\x80\xff")[vector["pattern"]]
    return (payload * (n // len(payload) + 1))[:n] + b"\0opaque\xff\0"


def _raw(pages, address, width=4):
    return int.from_bytes(
        bytes(pages[(address + i) & ~4095][(address + i) & 4095] for i in range(width)),
        "little",
    )


def _put(pages, address, value, width=4):
    for i, byte in enumerate(value.to_bytes(width, "little")):
        pages[(address + i) & ~4095][(address + i) & 4095] = byte


def _fixture(vector):
    _require(
        type(vector) is dict
        and set(vector)
        == {"length", "pattern", "name_alignment", "equal_pointers", "profile"}
        and all(type(vector[k]) is int for k in ("length", "name_alignment", "profile"))
        and type(vector["pattern"]) is str
        and type(vector["equal_pointers"]) is bool,
        "factory vector differs",
    )
    _require(vector in vectors(), "factory vector differs")
    variant = vector["profile"]
    entry = STACK + 0x1000 + 15 * variant
    p1 = FIRST + vector["name_alignment"]
    p2 = p1 if vector["equal_pointers"] else SECOND + 7 * variant
    userdata = USERDATA + 0x80 + 7 * variant
    state = 0x12001000 + 0x100 * variant
    pages = {
        p: bytearray(bytes([(p >> 12) & 255]) * 4096)
        for p in (
            0,
            STACK,
            STACK + 4096,
            FIRST,
            FIRST + 4096,
            SECOND,
            USERDATA,
            COOKIE & ~4095,
            (BASE + 0x3D6500) & ~4095,
        )
    }
    registers = {
        r: (0x81720304 + 0x010203 * i + 0x12345 * variant) & 0xFFFFFFFF
        for i, r in enumerate(REGISTERS)
    }
    registers["esp"] = entry
    _put(pages, entry, 0x0400A000)
    _put(pages, entry + 4, state)
    _put(pages, 0, (0, 0xF1234567)[variant])
    _put(pages, COOKIE, (0x12345678, 0xFFFFFFFF)[variant])
    for name, slot in SLOTS.items():
        _put(pages, BASE + slot, TARGETS[name])
    for i, byte in enumerate(_name(vector)):
        _put(pages, p1 + i, byte, 1)
    return dict(
        entry=entry,
        registers=registers,
        pages={p: bytes(v) for p, v in pages.items()},
        state=state,
        first_pointer=p1,
        second_pointer=p2,
        userdata=userdata,
    )


def _response(index, eax, profile):
    return dict(
        eax=eax,
        ecx=0xA1000000 + 0x100 * profile + index,
        edx=0xB1000000 + 0x100 * profile + index,
        eflags=0x202 | ((index * 0x95) & 0x8D5),
    )


def _expected(vector, fixture):
    """Closed-form frame and length law; no decoded-instruction interpreter."""
    from src.observatory import native_lua_class_factory_prefix_semantics as model

    logical = model.apply(
        _name(vector),
        state=fixture["state"],
        first_pointer=fixture["first_pointer"],
        second_pointer=fixture["second_pointer"],
        userdata=fixture["userdata"],
    )
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    regs = dict(fixture["registers"])
    events, calls = [], []
    frame = fixture["entry"] - 4

    def read(address, width=4):
        value = _raw(pages, address, width)
        events.append(dict(access="read", address=address, width=width, value=value))
        return value

    def write(address, value, width=4):
        value &= (1 << (8 * width)) - 1
        events.append(dict(access="write", address=address, width=width, value=value))
        _put(pages, address, value, width)

    def push(value):
        regs["esp"] -= 4
        write(regs["esp"], value)

    def api(site, continuation, name, args, result):
        for value in reversed(args):
            push(value)
        _require(read(BASE + SLOTS[name]) == TARGETS[name], "factory IAT differs")
        push(BASE + continuation)
        response = _response(len(calls), result, vector["profile"])
        calls.append(
            dict(
                api=name,
                site_rva=f"0x{site:08x}",
                target=TARGETS[name],
                arguments=args,
                continuation=BASE + continuation,
                entry_esp=regs["esp"],
                entry_registers=dict(regs),
                response=response,
            )
        )
        regs.update({r: response[r] for r in ("eax", "ecx", "edx")})
        regs["esp"] += 4 + 4 * len(args)

    push(regs["ebp"])
    regs["ebp"] = frame
    push(0xFFFFFFFF)
    push(BASE + 0x3A6111)
    regs["eax"] = read(0)
    push(regs["eax"])
    regs["esp"] -= 8
    for r in ("ebx", "esi", "edi"):
        push(regs[r])
    regs["eax"] = read(COOKIE) ^ frame
    push(regs["eax"])
    regs["eax"] = frame - 12
    write(0, regs["eax"])
    regs["esi"] = read(frame + 8)
    state = fixture["state"]
    api(0x2EC24C, 0x2EC252, "lua_gettop", [state], 1)
    regs["ebx"] = read(BASE + SLOTS["lua_pushstring"])
    api(0x2EC263, 0x2EC269, "lua_type", [state, 1], 4)
    api(0x2EC274, 0x2EC27A, "lua_isnumber", [state, 1], 0)
    api(0x2EC298, 0x2EC29E, "lua_tolstring", [state, 1, 0], fixture["first_pointer"])
    regs["edi"] = fixture["first_pointer"]
    regs["eax"] = regs["edi"] + 1
    for offset in range(vector["length"] + 1):
        byte = read(fixture["first_pointer"] + offset, 1)
        regs["ecx"] = (regs["ecx"] & 0xFFFFFF00) | byte
        regs["edi"] += 1
    # The argument pushes precede the length subtraction in the native body.
    for value in (1, state):
        push(value)
    regs["edi"] -= regs["eax"]
    _require(
        read(BASE + SLOTS["lua_objlen"]) == TARGETS["lua_objlen"], "factory IAT differs"
    )
    push(BASE + 0x2EC2B8)
    response = _response(4, vector["length"], vector["profile"])
    calls.append(
        dict(
            api="lua_objlen",
            site_rva="0x002ec2b2",
            target=TARGETS["lua_objlen"],
            arguments=[state, 1],
            continuation=BASE + 0x2EC2B8,
            entry_esp=regs["esp"],
            entry_registers=dict(regs),
            response=response,
        )
    )
    regs.update({r: response[r] for r in ("eax", "ecx", "edx")})
    regs["esp"] += 12
    api(0x2EC2D6, 0x2EC2DC, "lua_tolstring", [state, 1, 0], fixture["second_pointer"])
    regs["edi"] = fixture["second_pointer"]
    api(0x2EC2E4, 0x2EC2EA, "lua_newuserdata", [state, 72], fixture["userdata"])
    write(frame - 16, regs["eax"])
    write(frame - 20, regs["eax"])
    write(frame - 4, 0)
    push(regs["edi"])
    push(regs["esi"])
    regs["ecx"] = regs["eax"]
    push(BASE + END)
    _require(
        [(c["api"], c["arguments"], c["response"]["eax"]) for c in calls]
        == [(c["api"], c["arguments"], c["result"]) for c in logical["calls"]],
        "factory logical request model differs",
    )
    parity = int((fixture["userdata"] & 255).bit_count() % 2 == 0)
    return dict(
        pages={p: bytes(v) for p, v in pages.items()},
        registers=regs,
        flags=(parity * 4) | (0x80 if fixture["userdata"] & 0x80000000 else 0),
        calls=calls,
        events=events,
        logical=logical,
    )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "factory source partition differs")
    return {
        key: _source_identity(sources[key], *pin, key)
        for key, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    owner = _decode_body(data, image, sources["program_facts"], START)
    whole = b"".join(bytes(r.bytes) for r in owner)
    _require(
        len(whole) == 296 and hashlib.sha256(whole).hexdigest() == OWNER_SHA256,
        "factory owner differs",
    )
    selected = [r for r in owner if r.address < BASE + END]
    payload = b"".join(bytes(r.bytes) for r in selected)
    _require(
        len(payload) == END - START
        and hashlib.sha256(payload).hexdigest() == PREFIX_SHA256,
        "factory prefix differs",
    )
    return payload, [_point(r) for r in selected]


CONTROLS = {
    "ancestor": "factory protected memory differs",
    "name": "factory protected memory differs",
    "second_buffer": "factory protected memory differs",
    "userdata": "factory protected memory differs",
    "iat_padding": "factory protected memory differs",
    "cookie": "factory protected memory differs",
    "fs_chain": "factory protected memory differs",
    "saved_register": "factory protected memory differs",
    "local_userdata": "factory protected memory differs",
    "handoff_pointer": "factory protected memory differs",
    "result": "factory registers or defined flags differ",
    "flags": "factory registers or defined flags differ",
    "api_argument": "factory API request or ABI differs",
    "second_response": "factory API request or ABI differs",
    "length_response": "factory left normal prefix",
}


def _run_case(payload, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector)
    expected = _expected(vector, fixture)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, contents in fixture["pages"].items():
        machine.mem_map(page, 4096)
        machine.mem_write(page, contents)
    for page in ((BASE + START) & ~4095, (BASE + INITIALIZER) & ~4095, IMPORT):
        _require(page not in fixture["pages"], "factory mapping overlaps")
        machine.mem_map(page, 4096)
        machine.mem_write(page, b"\xcc" * 4096)
    machine.mem_write(BASE + START, payload)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in REGISTERS}
    for r, value in fixture["registers"].items():
        machine.reg_write(ids[r], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {
        int(p["rva"], 16)
        for p in points
        if not any(a <= int(p["rva"], 16) < b for a, b in ERROR_RANGES)
    }
    visited, events, calls = [], [], []
    resume = None
    finished = False

    def registers():
        return {r: machine.reg_read(i) for r, i in ids.items()}

    def word(address):
        return int.from_bytes(machine.mem_read(address, 4), "little")

    def on_code(m, address, size, user):
        nonlocal resume, finished
        if address in TARGETS.values():
            _require(len(calls) < len(expected["calls"]), "extra factory API call")
            call = expected["calls"][len(calls)]
            sp = m.reg_read(ids["esp"])
            if negative == "api_argument" and len(calls) == 6:
                m.mem_write(sp + 8, (73).to_bytes(4, "little"))
            _require(
                address == call["target"]
                and sp == call["entry_esp"]
                and [word(sp + 4 * i) for i in range(1 + len(call["arguments"]))]
                == [call["continuation"], *call["arguments"]]
                and registers() == call["entry_registers"],
                "factory API request or ABI differs",
            )
            response = dict(call["response"])
            if negative == "second_response" and len(calls) == 5:
                response["eax"] = fixture["first_pointer"]
            if negative == "length_response" and len(calls) == 4:
                response["eax"] ^= 1
            for r in ("eax", "ecx", "edx"):
                m.reg_write(ids[r], response[r])
            m.reg_write(x.UC_X86_REG_EFLAGS, response["eflags"])
            m.reg_write(ids["esp"], sp + 4)
            calls.append(
                dict(api=call["api"], arguments=call["arguments"], response=response)
            )
            resume = call["continuation"]
            m.emu_stop()
            return
        if address == BASE + INITIALIZER:
            corruption = dict(
                ancestor=fixture["entry"] + 8,
                name=fixture["first_pointer"] + vector["length"] + 2,
                second_buffer=SECOND + 0x300,
                userdata=fixture["userdata"],
                iat_padding=(BASE + 0x3D6500) & ~4095,
                cookie=COOKIE,
                fs_chain=0,
                saved_register=fixture["entry"] - 28,
                local_userdata=fixture["entry"] - 20,
                handoff_pointer=m.reg_read(ids["esp"]) + 8,
            )
            if negative in corruption:
                at = corruption[negative]
                m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))
            if negative == "result":
                m.reg_write(ids["ecx"], fixture["userdata"] ^ 1)
            if negative == "flags":
                m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 1)
            finished = True
            m.emu_stop()
            return
        rva = address - BASE
        _require(rva in allowed, "factory left normal prefix")
        visited.append(f"0x{rva:08x}")
        _require(
            len(visited) <= 71 + 4 * vector["length"],
            "factory instruction limit exceeded",
        )

    def on_memory(m, access, address, width, value, user):
        events.append(
            dict(
                access="read" if access == uc.UC_MEM_READ else "write",
                address=address,
                width=width,
                value=(
                    int.from_bytes(m.mem_read(address, width), "little")
                    if access == uc.UC_MEM_READ
                    else value & ((1 << (8 * width)) - 1)
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    pc = BASE + START
    for _ in range(9):
        resume = None
        machine.emu_start(pc, 0, count=2000)
        if finished:
            break
        _require(resume is not None, "factory missing continuation")
        pc = resume
    _require(finished and len(calls) == 7, "factory initializer handoff absent")
    _require(
        registers() == expected["registers"]
        and machine.reg_read(x.UC_X86_REG_EFLAGS) & FLAG_MASK == expected["flags"],
        "factory registers or defined flags differ",
    )
    _require(
        all(
            bytes(machine.mem_read(p, 4096)) == v for p, v in expected["pages"].items()
        ),
        "factory protected memory differs",
    )
    _require(events == expected["events"], "factory memory events differ")
    _require(
        len(visited) == 71 + 4 * vector["length"], "factory instruction count differs"
    )
    return dict(
        vector=vector,
        trace_rvas=visited,
        api_calls=calls,
        registers=registers(),
        flags=expected["flags"],
        memory_events_sha256=_canonical_sha256(events),
        pages_sha256={
            f"0x{p:08x}": hashlib.sha256(v).hexdigest()
            for p, v in expected["pages"].items()
        },
        logical=json.loads(json.dumps(expected["logical"])),
        initializer_instructions=0,
    )


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE,
        "exact factory executable differs",
    )
    payload, points = _load_code(data, image, sources)
    observations = [_run_case(payload, points, v) for v in vectors()]
    union = sorted({pc for o in observations for pc in o["trace_rvas"]})
    required = {
        p["rva"]
        for p in points
        if not any(a <= int(p["rva"], 16) < b for a, b in ERROR_RANGES)
    }
    _require(
        set(union) == required and len(required) == 71,
        "factory normal coverage differs",
    )
    sample = next(
        v
        for v in vectors()
        if v["length"] == 16 and not v["equal_pointers"] and v["profile"] == 1
    )
    controls = []
    for kind, reason in CONTROLS.items():
        try:
            _run_case(payload, points, sample, kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "factory control failed incidentally: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("factory control survived: " + kind)
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            start_rva=f"0x{START:08x}",
            end_rva=f"0x{END:08x}",
            sha256=PREFIX_SHA256,
            owner_sha256=OWNER_SHA256,
            points=points,
        ),
        vectors=vectors(),
        executed_rvas=union,
        negative_controls=controls,
        observations_sha256=_canonical_sha256(observations),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=len(observations),
            static_sites=len(points),
            executed_sites=len(union),
            instruction_bytes=len(payload),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            supplied_api_calls=7 * len(observations),
            controls=len(controls),
            initializer_instructions=0,
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            continuous_machine=True,
            supplied_apis=sorted(SLOTS.keys() - {"lua_pushstring"}),
            checked=[
                "First pointer inline NUL measurement and second pointer initializer routing",
                "Exact seven API frames and normal response contracts",
                "All native memory events, mapped data pages, registers and defined flags",
                "Active FS registration, saved caller cells and cookie setup",
                "Stop at initializer entry before its first instruction",
            ],
            premises=[
                "One nonnumeric Lua string with object length equal to measured NUL length",
                "Nonzero supplied userdata response and normal cdecl API preservation",
                "Readable synthetic name and disjoint mapped memory domains",
            ],
            excluded=[
                "Actual Lua VM, imports, allocator ownership or host execution",
                "Initializer behavior, full factory return and returned closure creation",
                "Error arms, null userdata bypass, exceptions and cookie verification",
                "Equality of separately returned string pointers or their bytes",
                "Arbitrary memory domains and accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    _validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors(),
        "sealed factory prefix conformance differs",
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
        "exact factory prefix conformance differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
