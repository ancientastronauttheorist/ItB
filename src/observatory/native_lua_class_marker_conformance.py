"""Native Lua class marker owner with supplied normal Lua API return contracts."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_lua_class_marker_semantics as semantics
from src.observatory.native_lua_vector_allocation_return_conformance import _add_flags
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

ANALYSIS_KIND = "pe_native_lua_class_marker_conformance"
SEALED_SHA256 = "d8f146cc7b6666a53348465065e7f6f7768f3d803fb6e4ea38bc9d72662515b9"
SOURCE_PINS = {
    "program_facts": semantics.SOURCE_PINS["program_facts"],
    "marker_semantics": (semantics.ANALYSIS_KIND, semantics.SEALED_SHA256),
}
START, END, LITERAL = semantics.START, semantics.END, BASE + semantics.LITERAL
STACK, RETURN, IMPORT = 0x02000000, 0x04000000, 0x05000000
LITERAL_BYTES = b"__luabind_classrep\0"
APIS = (
    "lua_getmetatable",
    "lua_pushstring",
    "lua_gettable",
    "lua_toboolean",
    "lua_settop",
)
TARGETS = {name: IMPORT + 0x100 * i for i, name in enumerate(APIS)}
CALLS = dict(semantics.CALLS)
ConformanceError = semantics.MarkerError
_require = semantics._require


def vectors():
    return [
        dict(
            alignment=alignment,
            prefix_length=length,
            has_metatable=present,
            value_kind=kind,
            final_void_eax=value,
        )
        for alignment in range(16)
        for length in (1, 3)
        for present, kind in (
            (False, "nil"),
            (True, "nil"),
            (True, "false"),
            (True, "zero"),
            (True, "empty_string"),
            (True, "table"),
        )
        for value in (0, 0x12345678, 0xFFFFFFFF)
    ]


def _fixture(vector):
    a, length = vector["alignment"], vector["prefix_length"]
    _require(
        type(a) is int and 0 <= a < 16 and type(length) is int and length in (1, 3),
        "invalid marker frame geometry",
    )
    relation = semantics.marker_spec(
        vector["has_metatable"],
        semantics.lua_truth(vector["value_kind"]),
        vector["final_void_eax"],
    )
    entry = STACK + 0x2000 + a
    initial = {
        r: (0x11223344 + i * 0x1111111 + a) & 0xFFFFFFFF
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    initial.update(
        ecx=0x01001000 + 32 * a + length, edx=(1 if a % 2 else 0xFFFFFFFF), esp=entry
    )
    endpoint = RETURN + 0x100 + 16 * length + a
    pages = {
        STACK
        + 4096
        * j: bytearray((i * 37 + j * 13 + (i >> 3) + 0x71) % 256 for i in range(4096))
        for j in range(4)
    }
    pages[LITERAL & ~0xFFF] = bytearray((i * 11 + 0x69) % 256 for i in range(4096))
    iat_page = (BASE + next(iter(CALLS.values()))[0]) & ~0xFFF
    pages[iat_page] = bytearray((i * 17 + 0xA3) % 256 for i in range(4096))

    def put(address, value, width=4):
        for i, b in enumerate(value.to_bytes(width, "little")):
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = b

    put(entry, endpoint)
    for i, b in enumerate(LITERAL_BYTES):
        put(LITERAL + i, b, 1)
    for slot, name in CALLS.values():
        put(BASE + slot, TARGETS[name])
    return dict(
        entry=entry,
        registers=initial,
        pages={p: bytes(v) for p, v in pages.items()},
        endpoint=endpoint,
        relation=relation,
        iat_page=iat_page,
    )


def _response(vector, name, index):
    eax = (0x91A2B300 + 17 * index + vector["alignment"]) & 0xFFFFFFFF
    if name == "lua_getmetatable":
        eax = int(vector["has_metatable"])
    elif name == "lua_toboolean":
        eax = int(semantics.lua_truth(vector["value_kind"]))
    elif name == "lua_settop":
        eax = vector["final_void_eax"]
    return dict(
        eax=eax,
        ecx=0xA0000000 + 256 * vector["alignment"] + index,
        edx=0xB0000000 + 256 * vector["prefix_length"] + index,
        eflags=0x202 | ((index * 0x95) & 0x8D5),
    )


def _expected(vector, fixture):
    entry = fixture["entry"]
    regs = dict(fixture["registers"])
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    events, calls = [], []
    lua = [("entry", i) for i in range(vector["prefix_length"])]
    original_lua = list(lua)

    def write(address, value):
        events.append(dict(access="write", address=address, width=4, value=value))
        for i, b in enumerate(value.to_bytes(4, "little")):
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = b

    def read(address, value):
        events.append(dict(access="read", address=address, width=4, value=value))

    def push(value):
        regs["esp"] -= 4
        write(regs["esp"], value)

    def call(site, index):
        slot, name = CALLS[site]
        read(BASE + slot, TARGETS[name])
        push(BASE + site + 6)
        before = len(lua)
        if name == "lua_getmetatable":
            if vector["has_metatable"]:
                lua.append(("metatable", 0))
        elif name == "lua_pushstring":
            lua.append(("key", 0))
        elif name == "lua_gettable":
            _require(
                lua[-2:] == [("metatable", 0), ("key", 0)],
                "marker abstract lookup stack differs",
            )
            lua[-1] = ("value", vector["value_kind"])
        elif name == "lua_toboolean":
            _require(
                lua[-1] == ("value", vector["value_kind"]),
                "marker abstract truth stack differs",
            )
        else:
            del lua[-2:]
        response = _response(vector, name, len(calls) + 1)
        calls.append(
            dict(
                site_rva=f"0x{site:08x}",
                api=name,
                target=TARGETS[name],
                entry_esp=regs["esp"],
                arguments=[fixture["registers"]["ecx"], index],
                continuation=BASE + site + 6,
                entry_registers=dict(regs),
                response=response,
                lua_top_before=before,
                lua_top_after=len(lua),
            )
        )
        regs.update({k: response[k] for k in ("eax", "ecx", "edx")})
        regs["esp"] += 4

    push(regs["esi"])
    regs["esi"] = fixture["registers"]["ecx"]
    push(regs["edx"])
    push(regs["esi"])
    call(0x2EB565, fixture["registers"]["edx"])
    regs["esp"] += 8
    if vector["has_metatable"]:
        push(LITERAL)
        push(regs["esi"])
        call(0x2EB578, LITERAL)
        push(0xFFFFFFFE)
        push(regs["esi"])
        call(0x2EB581, 0xFFFFFFFE)
        push(0xFFFFFFFF)
        push(regs["esi"])
        call(0x2EB58A, 0xFFFFFFFF)
        regs["esp"] += 24
        push(0xFFFFFFFD)
        push(regs["esi"])
        truth = semantics.lua_truth(vector["value_kind"])
        call(0x2EB59A if truth else 0x2EB5A7, 0xFFFFFFFD)
        flags, mask = (_add_flags(entry - 12, 8), 0x8D5) if truth else (0x44, 0x8C5)
        regs["esp"] += 8
    else:
        flags, mask = 0x44, 0x8C5
    regs["eax"] = fixture["relation"]["eax"]
    read(entry - 4, fixture["registers"]["esi"])
    regs["esi"] = fixture["registers"]["esi"]
    regs["esp"] += 4
    read(entry, fixture["endpoint"])
    regs["esp"] += 4
    _require(
        lua == original_lua
        and regs["esp"] == entry + 4
        and len(calls) == fixture["relation"]["api_calls"],
        "marker abstract return relation differs",
    )
    _require(
        [c["entry_esp"] - entry for c in calls]
        == ([-16, -16, -24, -32, -16] if vector["has_metatable"] else [-16]),
        "marker cdecl frame equations differ",
    )
    result = dict(
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        calls=calls,
        flags=flags,
        flag_mask=mask,
        endpoint=fixture["endpoint"],
        relation=fixture["relation"],
    )
    _require(
        result["pages"] == _stack_model(vector, fixture),
        "marker final stack corollary differs",
    )
    return result


def _stack_model(vector, fixture):
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    entry = fixture["entry"]
    cells = {
        -4: fixture["registers"]["esi"],
        -8: fixture["registers"]["edx"],
        -12: fixture["registers"]["ecx"],
        -16: BASE + 0x2EB56B,
    }
    if vector["has_metatable"]:
        cells.update(
            {
                -8: 0xFFFFFFFD,
                -16: BASE
                + (0x2EB5A0 if semantics.lua_truth(vector["value_kind"]) else 0x2EB5AD),
                -20: fixture["registers"]["ecx"],
                -24: 0xFFFFFFFF,
                -28: fixture["registers"]["ecx"],
                -32: BASE + 0x2EB590,
            }
        )
    for offset, value in cells.items():
        for i, b in enumerate(value.to_bytes(4, "little")):
            a = entry + offset + i
            pages[a & ~0xFFF][a & 0xFFF] = b
    return {p: bytes(v) for p, v in pages.items()}


def _run_case(code, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector)
    expected = _expected(vector, fixture)
    m = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, payload in fixture["pages"].items():
        m.mem_map(page, 4096)
        m.mem_write(page, payload)
    for page in ((BASE + START) & ~0xFFF, RETURN, IMPORT):
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
                len(summaries) < len(expected["calls"]), "unexpected marker API call"
            )
            call = expected["calls"][len(summaries)]
            sp = machine.reg_read(x.UC_X86_REG_ESP)
            if negative == "argument" and not summaries:
                machine.mem_write(
                    sp + 8, (call["arguments"][1] ^ 1).to_bytes(4, "little")
                )
            words = [
                int.from_bytes(machine.mem_read(sp + 4 * i, 4), "little")
                for i in range(3)
            ]
            _require(
                address == call["target"]
                and sp == call["entry_esp"]
                and words == [call["continuation"], *call["arguments"]],
                "marker API arguments differ",
            )
            _require(
                {r: machine.reg_read(i) for r, i in ids.items()}
                == call["entry_registers"],
                "marker API entry registers differ",
            )
            if call["api"] == "lua_pushstring":
                _require(
                    bytes(machine.mem_read(LITERAL, len(LITERAL_BYTES)))
                    == LITERAL_BYTES,
                    "marker literal argument differs",
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
            if negative == "al_upper":
                machine.reg_write(
                    x.UC_X86_REG_EAX, machine.reg_read(x.UC_X86_REG_EAX) ^ 0x100
                )
            machine.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "marker escaped exact owner")
        visited.append(f"0x{pc:08x}")
        at = None
        if pc == START:
            if negative == "ancestor":
                at = fixture["entry"] + 4
            elif negative == "return":
                at = fixture["entry"]
            elif negative == "literal_padding":
                at = LITERAL + 64
            elif negative == "iat_padding":
                at = fixture["iat_page"] + 16
        if pc == 0x2EB561 and negative == "saved_esi":
            at = fixture["entry"] - 4
        if at is not None:
            machine.mem_write(at, bytes([machine.mem_read(at, 1)[0] ^ 1]))

    def on_memory(machine, access, address, width, value, user):
        _require(width == 4, "unexpected marker memory width")
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
        m.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"], "marker endpoint differs"
    )
    registers = {r: m.reg_read(i) for r, i in ids.items()}
    flags = m.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        registers == expected["registers"]
        and flags & expected["flag_mask"] == expected["flags"]
        and not flags & 0x400,
        "marker final ABI differs",
    )
    _require(
        events == expected["events"] and summaries == expected["calls"],
        "marker ordered events differ",
    )
    _require(
        all(bytes(m.mem_read(p, 4096)) == v for p, v in expected["pages"].items()),
        "marker protected memory differs",
    )
    return dict(
        vector=vector,
        path=expected["relation"]["path"],
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
    _require(set(sources) == set(SOURCE_PINS), "marker source partition differs")
    return {
        key: _source_identity(sources[key], *pin, key)
        for key, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    rows = _decode_body(data, image, sources["program_facts"], START)
    code = b"".join(bytes(r.bytes) for r in rows)
    points = [_point(r) for r in rows]
    body = sources["marker_semantics"]["body"]
    _require(
        len(code) == 84
        and points == body["points"]
        and hashlib.sha256(code).hexdigest() == body["sha256"],
        "marker exact owner differs",
    )
    offset = image.rva_to_file_offset(semantics.LITERAL)
    literal = data[offset : offset + len(LITERAL_BYTES)]
    _require(
        literal == LITERAL_BYTES
        and hashlib.sha256(literal).hexdigest()
        == sources["marker_semantics"]["marker_literal"]["witness"]["sha256"],
        "marker exact literal differs",
    )
    return code, points


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE, "marker exact PE differs"
    )
    code, points = _load_code(data, image, sources)
    observations = [_run_case(code, points, v) for v in vectors()]
    union = sorted({pc for o in observations for pc in o["trace_rvas"]})
    _require(union == [p["rva"] for p in points], "marker full native coverage differs")
    sample = next(
        v
        for v in vectors()
        if v["has_metatable"]
        and v["value_kind"] == "zero"
        and v["final_void_eax"] == 0x12345678
    )
    controls = []
    for kind, message in (
        ("ancestor", "marker protected memory differs"),
        ("saved_esi", "marker final ABI differs"),
        ("argument", "marker API arguments differ"),
        ("return", "marker endpoint differs"),
        ("al_upper", "marker final ABI differs"),
        ("literal_padding", "marker protected memory differs"),
        ("iat_padding", "marker protected memory differs"),
    ):
        try:
            _run_case(code, points, sample, kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "marker mutation failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("marker mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(start_rva=f"0x{START:08x}", end_rva=f"0x{END:08x}", points=points),
        marker_literal=sources["marker_semantics"]["marker_literal"],
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
            paths={
                path: sum(o["path"] == path for o in observations)
                for path in ("no_metatable", "false_marker", "truthy_marker")
            },
            native_lua_api_instructions=0,
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact native marker helper through its caller return with supplied normal Lua API response contracts",
            premises=[
                "Lua API functions are opaque cdecl summaries preserving mapped native storage and nonvolatile registers; declared Lua stack effects restore the entry prefix",
                "No actual Lua DLL, VM, heap or metamethod instructions execute; lookup results and normal returns are supplied",
                "Exact literal bytes and import slots are pinned; complete synthetic literal, IAT and ancestor pages remain protected",
                "Only AL is a boolean; full EAX retains the final void settop response upper24bits, while absent metatable returns zero",
                "All three native paths and six call sites execute across the finite corpus; DF remains clear",
            ],
            not_claimed=[
                "Lua API implementation, errors or nonlocal exits, metamethod behavior, arbitrary native stack mappings, hardware execution or accounting promotion"
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "marker executable changed",
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
        "sealed native marker differs",
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
        "exact native marker differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
