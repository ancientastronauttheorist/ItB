"""Continuous callback and native marker helpers through argument lua_error entry."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from src.observatory import native_lua_class_factory_prefix_conformance as common
from src.observatory import native_lua_class_marker_conformance as marker
from src.observatory import native_lua_shared_api_layout as layout

BASE = common.BASE
ConformanceError, _require = common.ConformanceError, common._require
_canonical_sha256 = common._canonical_sha256
_canonical_bytes = common._canonical_bytes
_assert_publication_safe = common._assert_publication_safe
_validate_json_tree = common._validate_json_tree
ANALYSIS_KIND = "pe_native_lua_class_callback_error_conformance"
SEALED_SHA256 = "1c720f1a11c848aa2e5c9ef31dbb4aea6eb9e24bcb1867b30f463cb2d35ff988"
START, END, ERROR_SLOT, ERROR_TARGET = (
    0x2EC110,
    0x2EC19B,
    0x3D6498,
    layout.IMPORT + 0xF00,
)
OWNER_SHA256 = "a138a00ca47281aa3b4fb0db11a3aa5e875616a57b3684f7598e4b0517b900e3"
MESSAGE, MESSAGE_BYTES = 0x83C99C, b"expected class to derive from or a newline\0"
SOURCE_PINS = {
    **{k: v for k, v in common.SOURCE_PINS.items() if k != "initializer_chain"},
    "marker_semantics": marker.SOURCE_PINS["marker_semantics"],
    "marker_conformance": (marker.ANALYSIS_KIND, marker.SEALED_SHA256),
}
PARENT_START = (
    0x110,
    0x111,
    0x113,
    0x116,
    0x11B,
    0x11D,
    0x120,
    0x121,
    0x124,
    0x125,
    0x126,
    0x12C,
    0x131,
    0x132,
    0x134,
    0x136,
    0x139,
    0x13C,
    0x13E,
    0x154,
    0x159,
    0x15B,
)
PARENT_MIDDLE = (0x160, 0x162, 0x178, 0x17D, 0x17F)
PARENT_END = (0x184, 0x186, 0x188, 0x18D, 0x18E, 0x194, 0x195)
MARKER_START = (0x560, 0x561, 0x563, 0x564, 0x565, 0x56B, 0x56E, 0x570)
MARKER_META = (
    0x572,
    0x577,
    0x578,
    0x57E,
    0x580,
    0x581,
    0x587,
    0x589,
    0x58A,
    0x590,
    0x593,
    0x595,
    0x596,
    0x598,
)
MARKER_TRUE = (0x59A, 0x5A0, 0x5A3, 0x5A5, 0x5A6)
MARKER_FALSE = (0x5A7, 0x5AD, 0x5B0, 0x5B2, 0x5B3)
MARKER_ABSENT = (0x5B0, 0x5B2, 0x5B3)


def vectors():
    return [
        dict(alignment=a, profile=p, upvalue_kind=u, argument_mode=m)
        for a in range(16)
        for p in range(3)
        for u in ("zero", "empty_string", "table")
        for m in ("absent", "nil", "false")
    ]


def _fixture(vector):
    _require(
        type(vector) is dict
        and set(vector) == {"alignment", "profile", "upvalue_kind", "argument_mode"}
        and type(vector["alignment"]) is int
        and type(vector["profile"]) is int
        and type(vector["upvalue_kind"]) is str
        and type(vector["argument_mode"]) is str
        and vector in vectors(),
        "callback error vector differs",
    )
    entry = common.STACK + 0x1000 + vector["alignment"]
    state = 0x12001000 + 0x100 * vector["profile"]
    userdata = 0x11000FFF + 7 * vector["profile"]
    pages = {
        p: bytearray(bytes([(p >> 12) & 255]) * 4096)
        for p in (
            common.STACK,
            common.STACK + 4096,
            common.COOKIE & ~4095,
            0x11000000,
            0x11001000,
        )
    }
    pages.update({p: bytearray(v) for p, v in layout.make_layout()["pages"].items()})
    regs = {
        r: (0x81720304 + 0x10203 * i + 0x12345 * vector["profile"]) & 0xFFFFFFFF
        for i, r in enumerate(common.REGISTERS)
    }
    regs["esp"] = entry
    common._put(pages, entry, 0x0400A000)
    common._put(pages, entry + 4, state)
    common._put(pages, common.COOKIE, (0, 0x12345678, 0xFFFFFFFF)[vector["profile"]])
    common._put(pages, BASE + ERROR_SLOT, ERROR_TARGET)
    for i, b in enumerate(MESSAGE_BYTES):
        common._put(pages, MESSAGE + i, b, 1)
    return dict(
        entry=entry,
        state=state,
        userdata=userdata,
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
    )


def _marker_vector(vector, index):
    return dict(
        alignment=vector["alignment"],
        prefix_length=1,
        has_metatable=index == 0 or vector["argument_mode"] != "absent",
        value_kind=(
            vector["upvalue_kind"]
            if index == 0
            else (
                "nil"
                if vector["argument_mode"] == "absent"
                else vector["argument_mode"]
            )
        ),
        final_void_eax=(
            (0, 0x12345678, 0xFFFFFFFF) if index == 0 else (0xFFFFFFFF, 0, 0x12345678)
        )[vector["profile"]],
    )


def _marker_trace(present, truth):
    rows = MARKER_START + (
        MARKER_META + (MARKER_TRUE if truth else MARKER_FALSE)
        if present
        else MARKER_ABSENT
    )
    return [f"0x{0x2EB000+r:08x}" for r in rows]


def _trace(vector):
    parent = lambda rows: [f"0x{0x2EC000+r:08x}" for r in rows]
    return (
        parent(PARENT_START)
        + _marker_trace(True, True)
        + parent(PARENT_MIDDLE)
        + _marker_trace(vector["argument_mode"] != "absent", False)
        + parent(PARENT_END)
    )


def _expected(vector, fixture):
    from src.observatory import native_lua_class_callback_error_semantics as model

    logical = model.apply(
        state=fixture["state"],
        userdata=fixture["userdata"],
        upvalue_kind=vector["upvalue_kind"],
        argument_has_metatable=vector["argument_mode"] != "absent",
        argument_kind=(
            "nil" if vector["argument_mode"] == "absent" else vector["argument_mode"]
        ),
    )
    regs = dict(fixture["registers"])
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    events, calls, children = [], [], []
    frame = fixture["entry"] - 4

    def read(at):
        value = common._raw(pages, at)
        events.append(dict(access="read", address=at, width=4, value=value))
        return value

    def write(at, value):
        events.append(
            dict(access="write", address=at, width=4, value=value & 0xFFFFFFFF)
        )
        common._put(pages, at, value & 0xFFFFFFFF)

    def push(value):
        regs["esp"] -= 4
        write(regs["esp"], value)

    def direct(site, continuation, name, args, result, staged=None):
        target = layout.TARGETS[name]
        if staged:
            _require(regs[staged] == target, "callback error staged binding differs")
        else:
            _require(
                read(BASE + layout.SLOTS[name]) == target, "callback error IAT differs"
            )
        push(BASE + continuation)
        response = common._response(1 if not calls else 2, result, vector["profile"])
        calls.append(
            dict(
                api=name,
                site_rva=f"0x{site:08x}",
                target=target,
                arguments=args,
                continuation=BASE + continuation,
                entry_esp=regs["esp"],
                entry_registers=dict(regs),
                response=response,
                group="direct",
            )
        )
        regs.update({r: response[r] for r in ("eax", "ecx", "edx")})
        regs["esp"] += 4

    def child(index, continuation):
        nonlocal regs, pages
        push(BASE + continuation)
        mv = _marker_vector(vector, index)
        frozen = {p: bytes(v) for p, v in pages.items()}
        mf = marker._fixture(
            mv,
            api_layout=layout.make_layout(),
            caller=dict(
                entry=regs["esp"],
                return_address=BASE + continuation,
                registers=dict(regs),
                stack_pages={p: frozen[p] for p in (common.STACK, common.STACK + 4096)},
            ),
        )
        mf["pages"] = frozen
        result = marker._expected(mv, mf)
        calls.extend(
            dict(c, group="upvalue_marker" if index == 0 else "argument_marker")
            for c in result["calls"]
        )
        events.extend(result["events"])
        pages = {p: bytearray(v) for p, v in result["pages"].items()}
        regs = dict(result["registers"])
        children.append(dict(vector=mv, fixture=mf, result=result))

    push(regs["ebp"])
    regs["ebp"] = frame
    regs["esp"] -= 24
    regs["eax"] = read(common.COOKIE) ^ frame
    write(frame - 8, regs["eax"])
    push(regs["ebx"])
    regs["ebx"] = read(frame + 8)
    push(regs["esi"])
    push(regs["edi"])
    regs["edi"] = read(BASE + layout.SLOTS["lua_touserdata"])
    push(0xFFFFD8ED)
    push(regs["ebx"])
    direct(
        0x2EC132,
        0x2EC134,
        "lua_touserdata",
        [fixture["state"], 0xFFFFD8ED],
        fixture["userdata"],
        "edi",
    )
    regs["esi"] = regs["eax"]
    regs["esp"] += 8
    write(frame - 20, regs["esi"])
    regs.update(edx=0xFFFFD8ED, ecx=regs["ebx"])
    child(0, 0x2EC160)
    _require(regs["eax"] & 255 == 1, "callback error upvalue marker differs")
    regs.update(edx=1, ecx=regs["ebx"])
    child(1, 0x2EC184)
    _require(regs["eax"] & 255 == 0, "callback error argument marker differs")
    push(MESSAGE)
    push(regs["ebx"])
    direct(0x2EC18E, 0x2EC194, "lua_pushstring", [fixture["state"], MESSAGE], 0)
    push(regs["ebx"])
    _require(read(BASE + ERROR_SLOT) == ERROR_TARGET, "callback error IAT differs")
    push(BASE + END)
    request = dict(
        target=ERROR_TARGET,
        arguments=[fixture["state"]],
        continuation=BASE + END,
        entry_esp=regs["esp"],
        entry_registers=dict(regs),
        retained_stack_words=[BASE + END, fixture["state"], fixture["state"], MESSAGE],
    )
    _require(
        [(c["api"], [_signed(a) for a in c["arguments"]]) for c in calls]
        == [(c["api"], c["arguments"]) for c in logical["calls"][:-1]],
        "callback error logical requests differ",
    )
    return dict(
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        calls=calls,
        children=children,
        error_request=request,
        logical=json.loads(json.dumps(logical)),
        flags=calls[-1]["response"]["eflags"] & 0xCD5,
        trace_rvas=_trace(vector),
    )


def _signed(value):
    return value if value < 0x80000000 else value - 0x100000000


class _Lua:
    """Runtime identity observer, independent of the native child/frame oracle."""

    def __init__(self, vector, fixture):
        self.v, self.f = vector, fixture
        self.stack, self.calls = [("argument", 1)], []
        self.markers = 0

    def apply(self, name, args):
        _require(
            args and args[0] == self.f["state"], "callback error Lua state differs"
        )
        before = list(self.stack)
        role = None
        phase = "direct"
        result = 0
        if name == "lua_touserdata":
            _require(
                args == [self.f["state"], 0xFFFFD8ED],
                "callback error Lua arguments differ",
            )
            result = self.f["userdata"]
        elif name == "lua_getmetatable":
            index = self.markers
            _require(
                index < 2
                and args == [self.f["state"], 0xFFFFD8ED if index == 0 else 1],
                "callback error Lua arguments differ",
            )
            self.markers += 1
            phase = "upvalue_marker" if index == 0 else "argument_marker"
            token_role = "upvalue" if index == 0 else "argument"
            result = int(index == 0 or self.v["argument_mode"] != "absent")
            if result:
                self.stack.append(("metatable", token_role))
        elif name in (
            "lua_pushstring",
            "lua_gettable",
            "lua_toboolean",
            "lua_settop",
        ) and (name != "lua_pushstring" or args[1] == marker.LITERAL):
            phase = "upvalue_marker" if self.markers == 1 else "argument_marker"
            token_role = "upvalue" if self.markers == 1 else "argument"
            kind = (
                self.v["upvalue_kind"] if self.markers == 1 else self.v["argument_mode"]
            )
            wanted = {
                "lua_pushstring": marker.LITERAL,
                "lua_gettable": 0xFFFFFFFE,
                "lua_toboolean": 0xFFFFFFFF,
                "lua_settop": 0xFFFFFFFD,
            }[name]
            _require(
                args == [self.f["state"], wanted], "callback error Lua arguments differ"
            )
            if name == "lua_pushstring":
                role = "marker_key"
                self.stack.append(("literal", role))
            elif name == "lua_gettable":
                _require(
                    self.stack[-2:]
                    == [("metatable", token_role), ("literal", "marker_key")],
                    "callback error Lua identity differs",
                )
                self.stack[-1] = ("marker_value", token_role, kind)
            elif name == "lua_toboolean":
                _require(
                    self.stack[-1] == ("marker_value", token_role, kind),
                    "callback error Lua identity differs",
                )
                result = int(kind not in ("nil", "false"))
            else:
                _require(
                    self.stack[-2:]
                    == [("metatable", token_role), ("marker_value", token_role, kind)],
                    "callback error Lua identity differs",
                )
                del self.stack[-2:]
        elif name in ("lua_pushstring", "lua_error"):
            phase = "error"
            role = "argument_marker_error"
            _require(
                args
                == (
                    [self.f["state"], MESSAGE]
                    if name == "lua_pushstring"
                    else [self.f["state"]]
                ),
                "callback error Lua arguments differ",
            )
            if name == "lua_pushstring":
                self.stack.append(("message", role))
            else:
                _require(
                    self.stack == [("argument", 1), ("message", role)],
                    "callback error Lua identity differs",
                )
                result = None
        else:
            raise ConformanceError("callback error Lua API differs")
        self.calls.append(
            dict(
                api=name,
                arguments=[_signed(a) for a in args],
                result=result,
                before=before,
                after=list(self.stack),
                phase=phase,
                literal_role=role,
            )
        )
        return result


CONTROLS = {
    **{
        k: "callback error protected memory differs"
        for k in (
            "ancestor",
            "userdata",
            "message",
            "marker_literal",
            "cookie",
            "saved_register",
            "local_userdata",
            "error_return",
            "retained_literal",
            "iat_padding",
        )
    },
    "result": "callback error registers or flags differ",
    "flags": "callback error registers or flags differ",
    "api_argument": "callback error API request or ABI differs",
    "error_argument": "callback error boundary request or ABI differs",
    "push_response": "callback error boundary request or ABI differs",
    "lua_identity": "callback error Lua identity differs",
    "upvalue_guard": "callback error native path differs",
    "argument_guard": "callback error native path differs",
}


def _run_case(codes, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector)
    expected = _expected(vector, fixture)
    lua = _Lua(vector, fixture)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for p, v in fixture["pages"].items():
        machine.mem_map(p, 4096)
        machine.mem_write(p, v)
    for p in sorted(
        {(a + i) & ~4095 for a, b in codes.items() for i in range(len(b))}
        | {layout.IMPORT}
    ):
        _require(p not in fixture["pages"], "callback error mapping overlaps")
        machine.mem_map(p, 4096)
        machine.mem_write(p, b"\xcc" * 4096)
    for a, b in codes.items():
        machine.mem_write(a, b)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in common.REGISTERS}
    for r, v in fixture["registers"].items():
        machine.reg_write(ids[r], v)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    visited, events, calls = [], [], []
    resume, finished = None, False
    allowed = {p["rva"] for p in points}

    def registers():
        return {r: machine.reg_read(i) for r, i in ids.items()}

    def word(at):
        return int.from_bytes(machine.mem_read(at, 4), "little")

    def on_code(m, address, size, user):
        nonlocal resume, finished
        if address == ERROR_TARGET:
            req = expected["error_request"]
            sp = m.reg_read(ids["esp"])
            if negative == "error_argument":
                m.mem_write(sp + 4, (fixture["state"] ^ 1).to_bytes(4, "little"))
            _require(
                sp == req["entry_esp"]
                and [word(sp + 4 * i) for i in range(4)] == req["retained_stack_words"]
                and registers() == req["entry_registers"],
                "callback error boundary request or ABI differs",
            )
            if negative == "lua_identity":
                lua.stack[-1] = ("message", "wrong")
            _require(
                lua.apply("lua_error", [word(sp + 4)]) is None,
                "callback error response supplied",
            )
            f = fixture["entry"] - 4
            corruption = dict(
                ancestor=fixture["entry"] + 8,
                userdata=fixture["userdata"],
                message=MESSAGE,
                marker_literal=marker.LITERAL,
                cookie=common.COOKIE,
                saved_register=f - 28,
                local_userdata=f - 20,
                error_return=sp,
                retained_literal=sp + 12,
                iat_padding=layout.IAT_PAGE,
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
        if address in layout.TARGETS.values():
            _require(
                len(calls) < len(expected["calls"]), "extra callback error API call"
            )
            call = expected["calls"][len(calls)]
            sp = m.reg_read(ids["esp"])
            if negative == "api_argument" and not calls:
                m.mem_write(sp + 4, (fixture["state"] ^ 1).to_bytes(4, "little"))
            args = [word(sp + 4 * i) for i in range(1, 1 + len(call["arguments"]))]
            _require(
                address == call["target"]
                and sp == call["entry_esp"]
                and [word(sp), *args] == [call["continuation"], *call["arguments"]]
                and registers() == call["entry_registers"],
                "callback error API request or ABI differs",
            )
            result = lua.apply(call["api"], args)
            if call["api"] in ("lua_touserdata", "lua_getmetatable", "lua_toboolean"):
                _require(
                    result == call["response"]["eax"],
                    "callback error Lua response differs",
                )
            response = dict(call["response"])
            if negative == "push_response" and len(calls) == len(expected["calls"]) - 1:
                response["eax"] = 1
            for r in ("eax", "ecx", "edx"):
                m.reg_write(ids[r], response[r])
            m.reg_write(x.UC_X86_REG_EFLAGS, response["eflags"])
            m.reg_write(ids["esp"], sp + 4)
            calls.append(dict(api=call["api"], arguments=args, response=response))
            resume = call["continuation"]
            m.emu_stop()
            return
        if negative == "upvalue_guard" and address == BASE + 0x2EC160:
            m.reg_write(ids["eax"], m.reg_read(ids["eax"]) & 0xFFFFFF00)
        if negative == "argument_guard" and address == BASE + 0x2EC184:
            m.reg_write(ids["eax"], m.reg_read(ids["eax"]) | 1)
        rva = f"0x{address-BASE:08x}"
        _require(
            rva in allowed
            and len(visited) < len(expected["trace_rvas"])
            and rva == expected["trace_rvas"][len(visited)],
            "callback error native path differs",
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
    pc = BASE + START
    for _ in range(len(expected["calls"]) + 1):
        resume = None
        machine.emu_start(pc, 0, count=1000)
        if finished:
            break
        _require(resume is not None, "callback error missing continuation")
        pc = resume
    _require(
        finished and len(calls) == len(expected["calls"]),
        "callback error boundary absent",
    )
    _require(
        registers() == expected["registers"]
        and machine.reg_read(x.UC_X86_REG_EFLAGS) & 0xCD5 == expected["flags"],
        "callback error registers or flags differ",
    )
    _require(
        all(
            bytes(machine.mem_read(p, 4096)) == v for p, v in expected["pages"].items()
        ),
        "callback error protected memory differs",
    )
    _require(events == expected["events"], "callback error memory events differ")
    _require(visited == expected["trace_rvas"], "callback error native path differs")
    _require(
        json.loads(json.dumps(lua.calls)) == expected["logical"]["calls"],
        "callback error Lua trace differs",
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
    _require(
        set(sources) == set(SOURCE_PINS), "callback error source partition differs"
    )
    return {
        k: common._source_identity(sources[k], *pin, k)
        for k, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    owner = common._decode_body(data, image, sources["program_facts"], START)
    whole = b"".join(bytes(r.bytes) for r in owner)
    _require(
        len(whole) == 269 and hashlib.sha256(whole).hexdigest() == OWNER_SHA256,
        "callback error owner differs",
    )
    selected = [r for r in owner if r.address < BASE + END]
    payload = b"".join(bytes(r.bytes) for r in selected)
    _require(len(payload) == END - START, "callback error selected extent differs")
    mc, mp = marker._load_code(data, image, sources)
    _require(
        mp == sources["marker_conformance"]["body"]["points"],
        "callback error marker receipt differs",
    )
    literal = next(
        r
        for r in sources["factory_chain"]["literals"]
        if r["role"] == "returned_callback_error_message"
    )
    offset = image.rva_to_file_offset(MESSAGE - BASE)
    _require(
        int(literal["rva"], 16) == MESSAGE - BASE
        and data[offset : offset + len(MESSAGE_BYTES)] == MESSAGE_BYTES
        and hashlib.sha256(MESSAGE_BYTES).hexdigest()
        == literal["nul_terminated_bytes_sha256"],
        "callback error message differs",
    )
    return {BASE + START: payload, BASE + marker.START: mc}, sorted(
        [common._point(r) for r in selected] + mp, key=lambda p: p["rva"]
    )


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = common._load_executable(Path(executable))
    _require(
        digest == common.EXE_SHA256 and image.image_base == BASE,
        "exact callback error executable differs",
    )
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({r for o in observations for r in o["trace_rvas"]})
    required = {
        f"0x{0x2EC000+r:08x}" for r in PARENT_START + PARENT_MIDDLE + PARENT_END
    }
    required.update(
        f"0x{0x2EB000+r:08x}"
        for r in MARKER_START + MARKER_META + MARKER_TRUE + MARKER_FALSE + MARKER_ABSENT
    )
    _require(set(union) == required, "callback error coverage partition differs")
    sample = next(
        v
        for v in vectors()
        if v["alignment"] == 15 and v["profile"] == 2 and v["argument_mode"] == "false"
    )
    controls = []
    for kind, reason in CONTROLS.items():
        try:
            _run_case(codes, points, sample, kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "callback error control failed incidentally: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("callback error control survived: " + kind)
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{a-BASE:08x}",
                    end_rva=f"0x{a-BASE+len(b):08x}",
                    sha256=hashlib.sha256(b).hexdigest(),
                )
                for a, b in sorted(codes.items())
            ],
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
            instruction_bytes=sum(map(len, codes.values())),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            supplied_api_calls=sum(len(o["api_calls"]) for o in observations),
            error_boundaries=len(observations),
            marker_calls=2 * len(observations),
            controls=len(controls),
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            checked=[
                "Native callback and both actual marker helpers execute continuously",
                "Truthy closure upvalue and absent or false argument markers with AL-only native guards",
                "Independent Lua token transitions and restored argument prefix before message push",
                "Physical import frames, child return GPRs, deferred parent cleanup and retained error arguments",
                "Ordered native events, all mapped pages, caller ancestors and cookie setup",
            ],
            premises=[
                "Normal cdecl Lua responses preserve nonvolatile GPRs and mapped pages",
                "Supplied nonzero closure-upvalue userdata and compatible marker lookup values",
            ],
            excluded=[
                "Execution or response of lua_error, unwinding and callback return",
                "Assertion paths, class operation, table transfers and cookie verification",
                "Actual Lua VM or imported DLL behavior, unrestricted domains and accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "callback error executable changed",
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
        "sealed callback error conformance differs",
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
        "exact callback error conformance differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
