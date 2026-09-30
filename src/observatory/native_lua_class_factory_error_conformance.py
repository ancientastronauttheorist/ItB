"""Finite factory rejection prefixes, stopped at the lua_error import entry."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from src.observatory import native_lua_class_factory_prefix_conformance as factory

BASE = factory.BASE
ConformanceError = factory.ConformanceError
_require = factory._require
_canonical_sha256 = factory._canonical_sha256
_canonical_bytes = factory._canonical_bytes
_validate_json_tree = factory._validate_json_tree
_assert_publication_safe = factory._assert_publication_safe
ANALYSIS_KIND = "pe_native_lua_class_factory_error_conformance"
SEALED_SHA256 = "0e454398b0a47423e880932db975c82643358d6781115ced8989bb37a6a15952"
END = 0x2EC2CE
ERROR_SLOT = 0x3D6498
ERROR_TARGET = factory.IMPORT + 0xF00
SOURCE_PINS = {k: v for k, v in factory.SOURCE_PINS.items() if k != "initializer_chain"}
LITERALS = {
    "invalid_construct_message": (0x83CA60, "invalid construct, expected class name"),
    "embedded_nul_message": (
        0x83CA88,
        "luabind does not support class names with extra nulls",
    ),
}
PROLOGUE = (
    0x220,
    0x221,
    0x223,
    0x225,
    0x22A,
    0x230,
    0x231,
    0x234,
    0x235,
    0x236,
    0x237,
    0x23C,
    0x23E,
    0x23F,
    0x242,
    0x248,
    0x24B,
    0x24C,
    0x252,
    0x258,
    0x25B,
    0x25E,
)
TYPE = (0x260, 0x262, 0x263, 0x269, 0x26C, 0x26F)
NUMBER = (0x271, 0x273, 0x274, 0x27A, 0x27D, 0x27F)
STRING = (0x293, 0x295, 0x297, 0x298, 0x29E, 0x2A0, 0x2A3)
LOOP = (0x2A6, 0x2A8, 0x2A9, 0x2AB)
LENGTH = (0x2AD, 0x2AF, 0x2B0, 0x2B2, 0x2B8, 0x2BB, 0x2BD)
INVALID = (0x281, 0x286, 0x287, 0x289, 0x28A)
MISMATCH = (0x2BF, 0x2C4, 0x2C5, 0x2C7, 0x2C8)


def vectors():
    result = []
    for family, values in (
        ("count", (0, 2, 3, 0xFFFFFFFF)),
        ("type", (0, 3, 5, 0xFFFFFFFF)),
        ("number", (1, 0xFFFFFFFF)),
    ):
        for response in values:
            for profile in (0, 1):
                result.append(
                    dict(
                        family=family,
                        response=response,
                        length=0,
                        pattern="ascii",
                        name_alignment=0,
                        profile=profile,
                    )
                )
    for n in (0, 1, 2, 15, 16, 255):
        for pattern in ("ascii", "low", "high"):
            for alignment in (0, 7, 4095):
                for profile in (0, 1):
                    for response in (n + 1, n + 2, 0xFFFFFFFF):
                        result.append(
                            dict(
                                family="length",
                                response=response,
                                length=n,
                                pattern=pattern,
                                name_alignment=alignment,
                                profile=profile,
                            )
                        )
    return result


def _base_vector(vector):
    _require(
        type(vector) is dict
        and set(vector)
        == {"family", "response", "length", "pattern", "name_alignment", "profile"}
        and type(vector["family"]) is str
        and type(vector["pattern"]) is str
        and all(
            type(vector[k]) is int
            for k in ("response", "length", "name_alignment", "profile")
        )
        and vector in vectors(),
        "factory error vector differs",
    )
    return {
        k: vector[k] for k in ("length", "pattern", "name_alignment", "profile")
    } | {"equal_pointers": False}


def _fixture(vector):
    fixture = factory._fixture(_base_vector(vector))
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    fixture["pages"] = pages
    for pointer, text in LITERALS.values():
        for i, byte in enumerate(text.encode() + b"\0"):
            at = pointer + i
            pages.setdefault(at & ~4095, bytearray(b"\xe3" * 4096))[at & 4095] = byte
    factory._put(pages, BASE + ERROR_SLOT, ERROR_TARGET)
    fixture["pages"] = {p: bytes(v) for p, v in pages.items()}
    return fixture


def _trace(vector):
    family, n = vector["family"], vector["length"]
    rows = PROLOGUE
    if family != "count":
        rows += TYPE
    if family in ("number", "length"):
        rows += NUMBER
    if family == "length":
        rows += STRING + LOOP * (n + 1) + LENGTH + MISMATCH
    else:
        rows += INVALID
    return [f"0x{0x2EC000 + row:08x}" for row in rows]


class _Lua:
    """Separate supplied-response controller consuming actual argument words."""

    def __init__(self, vector, fixture):
        self.vector, self.fixture = vector, fixture
        count = vector["response"] if vector["family"] == "count" else 1
        self.stack = (
            [("argument", i + 1) for i in range(count)]
            if count <= 3
            else [("arguments", count)]
        )
        self.calls = []

    def apply(self, name, arguments):
        v, f = self.vector, self.fixture
        _require(
            arguments and arguments[0] == f["state"], "factory error Lua state differs"
        )
        before = list(self.stack)
        role = None
        if name == "lua_gettop":
            _require(arguments == [f["state"]], "factory error Lua arguments differ")
            result = v["response"] if v["family"] == "count" else 1
        elif name in ("lua_type", "lua_isnumber", "lua_objlen"):
            _require(arguments == [f["state"], 1], "factory error Lua arguments differ")
            result = {
                "lua_type": v["response"] if v["family"] == "type" else 4,
                "lua_isnumber": v["response"] if v["family"] == "number" else 0,
                "lua_objlen": v["response"],
            }[name]
        elif name == "lua_tolstring":
            _require(
                arguments == [f["state"], 1, 0], "factory error Lua arguments differ"
            )
            result = f["first_pointer"]
        elif name in ("lua_pushstring", "lua_error"):
            role = "extra_nulls" if v["family"] == "length" else "invalid_construct"
            literal = LITERALS[
                (
                    "embedded_nul_message"
                    if role == "extra_nulls"
                    else "invalid_construct_message"
                )
            ][0]
            wanted = [f["state"], literal] if name == "lua_pushstring" else [f["state"]]
            _require(arguments == wanted, "factory error Lua arguments differ")
            if name == "lua_pushstring":
                self.stack.append(("message", role))
                result = 0
            else:
                _require(
                    self.stack and self.stack[-1] == ("message", role),
                    "factory error Lua identity differs",
                )
                result = None
        else:
            raise ConformanceError("factory error Lua API differs")
        self.calls.append(
            dict(
                api=name,
                arguments=list(arguments),
                result=result,
                before=before,
                after=list(self.stack),
                literal_role=role,
            )
        )
        return result


def _expected(vector, fixture):
    """Independent physical frame and event law for each rejection family."""
    from src.observatory import native_lua_class_factory_error_semantics as model

    family = vector["family"]
    logical = model.apply(
        state=fixture["state"],
        argument_count=vector["response"] if family == "count" else 1,
        type_result=vector["response"] if family == "type" else 4,
        number_result=vector["response"] if family == "number" else 0,
        first_pointer=fixture["first_pointer"],
        name_bytes=factory._name(_base_vector(vector)),
        object_length=vector["response"] if family == "length" else None,
    )
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    regs, events, calls = dict(fixture["registers"]), [], []
    frame = fixture["entry"] - 4

    def read(address, width=4):
        value = factory._raw(pages, address, width)
        events.append(dict(access="read", address=address, width=width, value=value))
        return value

    def write(address, value, width=4):
        value &= (1 << (8 * width)) - 1
        events.append(dict(access="write", address=address, width=width, value=value))
        factory._put(pages, address, value, width)

    def push(value):
        regs["esp"] -= 4
        write(regs["esp"], value)

    def api(site, continuation, name, args, result, *, cleanup=True, staged=False):
        for value in reversed(args):
            push(value)
        if not staged:
            _require(
                read(BASE + factory.SLOTS[name]) == factory.TARGETS[name],
                "factory error IAT differs",
            )
        push(BASE + continuation)
        response = factory._response(len(calls), result, vector["profile"])
        calls.append(
            dict(
                api=name,
                site_rva=f"0x{site:08x}",
                target=factory.TARGETS[name],
                arguments=args,
                continuation=BASE + continuation,
                entry_esp=regs["esp"],
                entry_registers=dict(regs),
                response=response,
            )
        )
        regs.update({r: response[r] for r in ("eax", "ecx", "edx")})
        regs["esp"] += 4 + (4 * len(args) if cleanup else 0)

    push(regs["ebp"])
    regs["ebp"] = frame
    push(0xFFFFFFFF)
    push(BASE + 0x3A6111)
    regs["eax"] = read(0)
    push(regs["eax"])
    regs["esp"] -= 8
    for r in ("ebx", "esi", "edi"):
        push(regs[r])
    regs["eax"] = read(factory.COOKIE) ^ frame
    push(regs["eax"])
    regs["eax"] = frame - 12
    write(0, regs["eax"])
    regs["esi"] = read(frame + 8)
    state = fixture["state"]
    api(
        0x2EC24C,
        0x2EC252,
        "lua_gettop",
        [state],
        vector["response"] if family == "count" else 1,
    )
    regs["ebx"] = read(BASE + factory.SLOTS["lua_pushstring"])
    if family != "count":
        api(
            0x2EC263,
            0x2EC269,
            "lua_type",
            [state, 1],
            vector["response"] if family == "type" else 4,
        )
    if family in ("number", "length"):
        api(
            0x2EC274,
            0x2EC27A,
            "lua_isnumber",
            [state, 1],
            vector["response"] if family == "number" else 0,
        )
    if family == "length":
        api(
            0x2EC298, 0x2EC29E, "lua_tolstring", [state, 1, 0], fixture["first_pointer"]
        )
        regs["edi"] = fixture["first_pointer"]
        regs["eax"] = regs["edi"] + 1
        for offset in range(vector["length"] + 1):
            byte = read(fixture["first_pointer"] + offset, 1)
            regs["ecx"] = (regs["ecx"] & 0xFFFFFF00) | byte
            regs["edi"] += 1
        push(1)
        push(state)
        regs["edi"] -= regs["eax"]
        _require(
            read(BASE + factory.SLOTS["lua_objlen"]) == factory.TARGETS["lua_objlen"],
            "factory error IAT differs",
        )
        push(BASE + 0x2EC2B8)
        response = factory._response(len(calls), vector["response"], vector["profile"])
        calls.append(
            dict(
                api="lua_objlen",
                site_rva="0x002ec2b2",
                target=factory.TARGETS["lua_objlen"],
                arguments=[state, 1],
                continuation=BASE + 0x2EC2B8,
                entry_esp=regs["esp"],
                entry_registers=dict(regs),
                response=response,
            )
        )
        regs.update({r: response[r] for r in ("eax", "ecx", "edx")})
        regs["esp"] += 12
    role = "embedded_nul_message" if family == "length" else "invalid_construct_message"
    literal = LITERALS[role][0]
    site, after, error_after = (
        (0x2EC2C5, 0x2EC2C7, 0x2EC2CE)
        if family == "length"
        else (0x2EC287, 0x2EC289, 0x2EC290)
    )
    api(site, after, "lua_pushstring", [state, literal], 0, cleanup=False, staged=True)
    push(state)
    _require(read(BASE + ERROR_SLOT) == ERROR_TARGET, "factory error IAT differs")
    push(BASE + error_after)
    error_request = dict(
        target=ERROR_TARGET,
        arguments=[state],
        continuation=BASE + error_after,
        entry_esp=regs["esp"],
        entry_registers=dict(regs),
        retained_stack_words=[BASE + error_after, state, state, literal],
    )
    _require(
        [(c["api"], c["arguments"], c["response"]["eax"]) for c in calls]
        == [(c["api"], c["arguments"], c["result"]) for c in logical["calls"][:-1]],
        "factory error logical requests differ",
    )
    return dict(
        pages={p: bytes(v) for p, v in pages.items()},
        registers=regs,
        flags=calls[-1]["response"]["eflags"] & 0xCD5,
        events=events,
        calls=calls,
        error_request=error_request,
        logical=json.loads(json.dumps(logical)),
        trace_rvas=_trace(vector),
    )


CONTROLS = {
    **{
        kind: "factory error protected memory differs"
        for kind in (
            "ancestor",
            "name",
            "literal",
            "iat_padding",
            "cookie",
            "fs_chain",
            "saved_register",
            "error_return",
            "retained_literal",
        )
    },
    "result": "factory error registers or flags differ",
    "flags": "factory error registers or flags differ",
    "api_argument": "factory error API request or ABI differs",
    "push_response": "factory error boundary request or ABI differs",
    "error_argument": "factory error boundary request or ABI differs",
    "lua_identity": "factory error Lua identity differs",
}


def _run_case(payload, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector)
    expected = _expected(vector, fixture)
    lua = _Lua(vector, fixture)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, content in fixture["pages"].items():
        machine.mem_map(page, 4096)
        machine.mem_write(page, content)
    for page in sorted(
        {(BASE + factory.START + i) & ~4095 for i in range(len(payload))}
        | {factory.IMPORT}
    ):
        _require(page not in fixture["pages"], "factory error mapping overlaps")
        machine.mem_map(page, 4096)
        machine.mem_write(page, b"\xcc" * 4096)
    machine.mem_write(BASE + factory.START, payload)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in factory.REGISTERS}
    for r, v in fixture["registers"].items():
        machine.reg_write(ids[r], v)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    visited, events, calls = [], [], []
    allowed = {p["rva"] for p in points}
    resume, finished = None, False

    def registers():
        return {r: machine.reg_read(i) for r, i in ids.items()}

    def word(at):
        return int.from_bytes(machine.mem_read(at, 4), "little")

    def on_code(m, address, size, user):
        nonlocal resume, finished
        if address == ERROR_TARGET:
            request = expected["error_request"]
            sp = m.reg_read(ids["esp"])
            if negative == "error_argument":
                m.mem_write(sp + 4, (fixture["state"] ^ 1).to_bytes(4, "little"))
            _require(
                sp == request["entry_esp"]
                and [word(sp + 4 * i) for i in range(4)]
                == request["retained_stack_words"]
                and registers() == request["entry_registers"],
                "factory error boundary request or ABI differs",
            )
            if negative == "lua_identity":
                lua.stack[-1] = ("message", "wrong")
            _require(
                lua.apply("lua_error", [word(sp + 4)]) is None,
                "factory error response supplied",
            )
            corruption = dict(
                ancestor=fixture["entry"] + 8,
                name=fixture["first_pointer"] + vector["length"] + 2,
                literal=expected["logical"]["error_literal"]["pointer"],
                iat_padding=(BASE + factory.SLOTS["lua_type"]) & ~4095,
                cookie=factory.COOKIE,
                fs_chain=0,
                saved_register=fixture["entry"] - 28,
                error_return=sp,
                retained_literal=sp + 12,
            )
            if negative in corruption:
                at = corruption[negative]
                m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))
            if negative == "result":
                m.reg_write(ids["eax"], 1)
            if negative == "flags":
                m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 1)
            finished = True
            m.emu_stop()
            return
        if address in factory.TARGETS.values():
            _require(
                len(calls) < len(expected["calls"]), "extra factory error API call"
            )
            call = expected["calls"][len(calls)]
            sp = m.reg_read(ids["esp"])
            if negative == "api_argument" and not calls:
                m.mem_write(sp + 4, (fixture["state"] ^ 1).to_bytes(4, "little"))
            _require(
                address == call["target"]
                and sp == call["entry_esp"]
                and [word(sp + 4 * i) for i in range(1 + len(call["arguments"]))]
                == [call["continuation"], *call["arguments"]]
                and registers() == call["entry_registers"],
                "factory error API request or ABI differs",
            )
            response = dict(call["response"])
            _require(
                lua.apply(
                    call["api"],
                    [word(sp + 4 * i) for i in range(1, 1 + len(call["arguments"]))],
                )
                == response["eax"],
                "factory error Lua response differs",
            )
            if negative == "push_response" and call["api"] == "lua_pushstring":
                response["eax"] = 1
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
        rva = f"0x{address-BASE:08x}"
        _require(
            rva in allowed
            and len(visited) < len(expected["trace_rvas"])
            and rva == expected["trace_rvas"][len(visited)],
            "factory error native path differs",
        )
        visited.append(rva)

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
    pc = BASE + factory.START
    for _ in range(len(expected["calls"]) + 1):
        resume = None
        machine.emu_start(pc, 0, count=2000)
        if finished:
            break
        _require(resume is not None, "factory error missing continuation")
        pc = resume
    _require(
        finished and len(calls) == len(expected["calls"]),
        "factory error boundary absent",
    )
    _require(
        registers() == expected["registers"]
        and machine.reg_read(x.UC_X86_REG_EFLAGS) & 0xCD5 == expected["flags"],
        "factory error registers or flags differ",
    )
    _require(
        all(
            bytes(machine.mem_read(p, 4096)) == v for p, v in expected["pages"].items()
        ),
        "factory error protected memory differs",
    )
    _require(events == expected["events"], "factory error memory events differ")
    _require(visited == expected["trace_rvas"], "factory error native path differs")
    _require(
        json.loads(json.dumps(lua.calls)) == expected["logical"]["calls"],
        "factory error Lua trace differs",
    )
    return dict(
        vector=vector,
        trace_rvas=visited,
        api_calls=calls,
        error_request=expected["error_request"],
        registers=registers(),
        flags=expected["flags"],
        logical=expected["logical"],
        lua_calls=json.loads(json.dumps(lua.calls)),
        memory_events_sha256=_canonical_sha256(events),
        pages_sha256={
            f"0x{p:08x}": hashlib.sha256(v).hexdigest()
            for p, v in expected["pages"].items()
        },
    )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "factory error source partition differs")
    return {
        k: factory._source_identity(sources[k], *pin, k)
        for k, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    owner = factory._decode_body(data, image, sources["program_facts"], factory.START)
    whole = b"".join(bytes(r.bytes) for r in owner)
    _require(
        len(whole) == 296 and hashlib.sha256(whole).hexdigest() == factory.OWNER_SHA256,
        "factory owner differs",
    )
    for role, (pointer, text) in LITERALS.items():
        literal = next(
            r for r in sources["factory_chain"]["literals"] if r["role"] == role
        )
        raw = text.encode() + b"\0"
        _require(
            int(literal["rva"], 16) == pointer - BASE
            and literal["text"] == text
            and hashlib.sha256(raw).hexdigest()
            == literal["nul_terminated_bytes_sha256"],
            "factory error literal differs",
        )
        offset = image.rva_to_file_offset(pointer - BASE)
        _require(
            data[offset : offset + len(raw)] == raw,
            "factory error executable literal differs",
        )
    selected = [r for r in owner if r.address < BASE + END]
    payload = b"".join(bytes(r.bytes) for r in selected)
    _require(
        len(payload) == END - factory.START, "factory error selected extent differs"
    )
    return payload, [factory._point(r) for r in selected]


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = factory._load_executable(Path(executable))
    _require(
        digest == factory.EXE_SHA256 and image.image_base == BASE,
        "exact factory error executable differs",
    )
    payload, points = _load_code(data, image, sources)
    observations = [_run_case(payload, points, v) for v in vectors()]
    union = sorted({r for o in observations for r in o["trace_rvas"]})
    required = {
        f"0x{0x2EC000+r:08x}"
        for r in PROLOGUE + TYPE + NUMBER + STRING + LOOP + LENGTH + INVALID + MISMATCH
    }
    _require(set(union) == required, "factory error coverage partition differs")
    controls = []
    sample = next(
        v
        for v in vectors()
        if v["family"] == "length" and v["length"] == 16 and v["profile"] == 1
    )
    for kind, reason in CONTROLS.items():
        try:
            _run_case(payload, points, sample, kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "factory error control failed incidentally: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("factory error control survived: " + kind)
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            start_rva=f"0x{factory.START:08x}",
            end_rva=f"0x{END:08x}",
            sha256=hashlib.sha256(payload).hexdigest(),
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
            supplied_api_calls=sum(len(o["api_calls"]) for o in observations),
            error_boundaries=len(observations),
            controls=len(controls),
            families={
                f: sum(v["family"] == f for v in vectors())
                for f in ("count", "type", "number", "length")
            },
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            checked=[
                "Four exact rejection prefixes with independent short-circuit requests",
                "Physical cdecl frames, retained pushstring arguments and error continuation",
                "Native first-NUL loop, ordered data events and all mapped pages",
                "Independent runtime message identity and all reached Lua token transitions",
                "Active FS registration, cookie setup and preserved caller ancestors",
            ],
            premises=[
                "Supplied normal Lua response words and cdecl register preservation",
                "Readable bounded synthetic name and exact pinned error literal bytes",
            ],
            excluded=[
                "Execution or return of lua_error and exception unwinding",
                "Actual Lua VM or imported DLL behavior, allocation and initializer execution",
                "Cookie verification, unrestricted pointers and accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory error executable changed",
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
        "sealed factory error conformance differs",
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
        "exact factory error conformance differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
