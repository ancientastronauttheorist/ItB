"""Native callback validation failures stopped before assertion-helper execution."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from src.observatory import native_lua_class_callback_error_conformance as parent

common, marker, layout = parent.common, parent.marker, parent.layout
BASE = common.BASE
ConformanceError, _require = common.ConformanceError, common._require
_canonical_sha256, _canonical_bytes = common._canonical_sha256, common._canonical_bytes
_assert_publication_safe, _validate_json_tree = (
    common._assert_publication_safe,
    common._validate_json_tree,
)
ANALYSIS_KIND = "pe_native_lua_class_callback_assertion_prefix_conformance"
SEALED_SHA256 = "b6486105640001ae644f9ea2023c98ca62626df5f1ab2c2041ba2dea2879484e"
START, END, BOUNDARY = parent.START, 0x2EC175, BASE + 0x379CC2
SOURCE_PINS = {
    **parent.SOURCE_PINS,
    "callback_error": (parent.ANALYSIS_KIND, parent.SEALED_SHA256),
}


def vectors():
    return [
        dict(alignment=a, profile=p, family=f)
        for a in range(16)
        for p in range(3)
        for f in ("null", "absent", "nil", "false")
    ]


def _fixture(vector):
    _require(
        type(vector) is dict
        and set(vector) == {"alignment", "profile", "family"}
        and type(vector["alignment"]) is int
        and type(vector["profile"]) is int
        and type(vector["family"]) is str
        and vector in vectors(),
        "callback assertion prefix vector differs",
    )
    fixture = parent._fixture(
        dict(
            alignment=vector["alignment"],
            profile=vector["profile"],
            upvalue_kind="zero",
            argument_mode="nil",
        )
    )
    if vector["family"] == "null":
        fixture["userdata"] = 0
    return fixture


def _marker_vector(vector):
    return dict(
        alignment=vector["alignment"],
        prefix_length=1,
        has_metatable=vector["family"] != "absent",
        value_kind="false" if vector["family"] == "false" else "nil",
        final_void_eax=(0, 0x12345678, 0xFFFFFFFF)[vector["profile"]],
    )


def _trace(vector):
    prefix = (
        parent.PARENT_START[:19] if vector["family"] == "null" else parent.PARENT_START
    )
    suffix = (
        (0x140, 0x142, 0x147, 0x14C)
        if vector["family"] == "null"
        else (0x160, 0x162, 0x164, 0x166, 0x16B, 0x170)
    )
    rows = [f"0x{0x2EC000+r:08x}" for r in prefix]
    if vector["family"] != "null":
        rows += parent._marker_trace(vector["family"] != "absent", False)
    return rows + [f"0x{0x2EC000+r:08x}" for r in suffix]


def _expected(vector, fixture):
    from src.observatory import (
        native_lua_class_callback_assertion_prefix_semantics as model,
    )

    logical = model.apply(
        state=fixture["state"],
        userdata=fixture["userdata"],
        has_metatable=vector["family"] != "absent",
        value_kind="false" if vector["family"] == "false" else "nil",
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
    push(BASE + 0x2EC134)
    response = common._response(1, fixture["userdata"], vector["profile"])
    calls.append(
        dict(
            api="lua_touserdata",
            site_rva="0x002ec132",
            target=layout.TARGETS["lua_touserdata"],
            arguments=[fixture["state"], 0xFFFFD8ED],
            continuation=BASE + 0x2EC134,
            entry_esp=regs["esp"],
            entry_registers=dict(regs),
            response=response,
            group="direct",
        )
    )
    regs.update({r: response[r] for r in ("eax", "ecx", "edx")})
    regs["esi"] = regs["eax"]
    regs["esp"] += 12
    write(frame - 20, regs["esi"])
    if fixture["userdata"]:
        regs.update(edx=0xFFFFD8ED, ecx=regs["ebx"])
        push(BASE + 0x2EC160)
        mv = _marker_vector(vector)
        frozen = {p: bytes(v) for p, v in pages.items()}
        mf = marker._fixture(
            mv,
            api_layout=layout.make_layout(),
            caller=dict(
                entry=regs["esp"],
                return_address=BASE + 0x2EC160,
                registers=dict(regs),
                stack_pages={p: frozen[p] for p in (common.STACK, common.STACK + 4096)},
            ),
        )
        mf["pages"] = frozen
        result = marker._expected(mv, mf)
        _require(
            result["registers"]["eax"] & 255 == 0,
            "callback assertion prefix marker differs",
        )
        events.extend(result["events"])
        calls.extend(dict(c, group="upvalue_marker") for c in result["calls"])
        regs = dict(result["registers"])
        pages = {p: bytearray(v) for p, v in result["pages"].items()}
        children.append(dict(vector=mv, fixture=mf, result=result))
    boundary = logical["native_boundary"]
    for word in reversed(boundary["arguments"]):
        push(word)
    push(boundary["continuation"])
    request = dict(
        target=BOUNDARY,
        arguments=boundary["arguments"],
        continuation=boundary["continuation"],
        entry_esp=regs["esp"],
        entry_registers=dict(regs),
        retained_stack_words=[boundary["continuation"], *boundary["arguments"]],
    )
    _require(
        [(c["api"], [parent._signed(a) for a in c["arguments"]]) for c in calls]
        == [(c["api"], c["arguments"]) for c in logical["calls"]],
        "callback assertion prefix logical requests differ",
    )
    return dict(
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        calls=calls,
        children=children,
        boundary_request=request,
        logical=json.loads(json.dumps(logical)),
        flags=0x44,
        trace_rvas=_trace(vector),
    )


class _Lua(parent._Lua):
    def __init__(self, vector, fixture):
        super().__init__(
            dict(
                upvalue_kind="false" if vector["family"] == "false" else "nil",
                argument_mode="nil",
            ),
            fixture,
        )
        self.present = vector["family"] != "absent"

    def apply(self, name, args):
        if name != "lua_getmetatable":
            return super().apply(name, args)
        _require(
            self.markers == 0 and args == [self.f["state"], 0xFFFFD8ED],
            "callback assertion prefix Lua arguments differ",
        )
        before = list(self.stack)
        self.markers += 1
        if self.present:
            self.stack.append(("metatable", "upvalue"))
        self.calls.append(
            dict(
                api=name,
                arguments=[parent._signed(a) for a in args],
                result=int(self.present),
                before=before,
                after=list(self.stack),
                phase="upvalue_marker",
                literal_role=None,
            )
        )
        return int(self.present)


CONTROLS = {
    **{
        k: "callback assertion prefix protected memory differs"
        for k in (
            "ancestor",
            "userdata",
            "expression_page",
            "cookie",
            "saved_register",
            "local_userdata",
            "boundary_return",
            "boundary_word",
            "iat_padding",
        )
    },
    "result": "callback assertion prefix registers or flags differ",
    "flags": "callback assertion prefix registers or flags differ",
    "api_argument": "callback assertion prefix API request or ABI differs",
    "boundary_argument": "callback assertion prefix boundary request or ABI differs",
    "api_response": "callback assertion prefix boundary request or ABI differs",
    "lua_identity": "callback assertion prefix Lua identity differs",
    "upvalue_guard": "callback assertion prefix native path differs",
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
        | {layout.IMPORT, BOUNDARY & ~4095}
    ):
        _require(
            p not in fixture["pages"], "callback assertion prefix mapping overlaps"
        )
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
        if address == BOUNDARY:
            req = expected["boundary_request"]
            sp = m.reg_read(ids["esp"])
            if negative == "boundary_argument":
                m.mem_write(sp + 4, (word(sp + 4) ^ 1).to_bytes(4, "little"))
            _require(
                sp == req["entry_esp"]
                and [word(sp + 4 * i) for i in range(4)] == req["retained_stack_words"]
                and registers() == req["entry_registers"],
                "callback assertion prefix boundary request or ABI differs",
            )
            if negative == "lua_identity":
                lua.stack[-1] = ("message", "wrong")
            f = fixture["entry"] - 4
            corruption = dict(
                ancestor=fixture["entry"] + 8,
                userdata=fixture["userdata"],
                expression_page=expected["logical"]["native_boundary"]["arguments"][0],
                cookie=common.COOKIE,
                saved_register=f - 28,
                local_userdata=f - 20,
                boundary_return=sp,
                boundary_word=sp + 12,
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
                len(calls) < len(expected["calls"]),
                "extra callback assertion prefix API call",
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
                "callback assertion prefix API request or ABI differs",
            )
            result = lua.apply(call["api"], args)
            if call["api"] in ("lua_touserdata", "lua_getmetatable", "lua_toboolean"):
                _require(
                    result == call["response"]["eax"],
                    "callback assertion prefix Lua response differs",
                )
            response = dict(call["response"])
            if negative == "api_response" and len(calls) == len(expected["calls"]) - 1:
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
            m.reg_write(ids["eax"], m.reg_read(ids["eax"]) | 1)
        rva = f"0x{address-BASE:08x}"
        _require(
            rva in allowed
            and len(visited) < len(expected["trace_rvas"])
            and rva == expected["trace_rvas"][len(visited)],
            "callback assertion prefix native path differs",
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
        _require(resume is not None, "callback assertion prefix missing continuation")
        pc = resume
    _require(
        finished and len(calls) == len(expected["calls"]),
        "callback assertion prefix boundary absent",
    )
    _require(
        registers() == expected["registers"]
        and machine.reg_read(x.UC_X86_REG_EFLAGS) & 0xCC5 == expected["flags"],
        "callback assertion prefix registers or flags differ",
    )
    _require(
        all(
            bytes(machine.mem_read(p, 4096)) == v for p, v in expected["pages"].items()
        ),
        "callback assertion prefix protected memory differs",
    )
    _require(
        events == expected["events"], "callback assertion prefix memory events differ"
    )
    _require(
        visited == expected["trace_rvas"],
        "callback assertion prefix native path differs",
    )
    _require(
        json.loads(json.dumps(lua.calls)) == expected["logical"]["calls"],
        "callback assertion prefix Lua trace differs",
    )
    _require(
        json.loads(json.dumps(lua.stack)) == expected["logical"]["final_lua_stack"],
        "callback assertion prefix Lua identity differs",
    )
    return dict(
        vector=vector,
        trace_rvas=visited,
        api_calls=calls,
        boundary_request=expected["boundary_request"],
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
        set(sources) == set(SOURCE_PINS),
        "callback assertion prefix source partition differs",
    )
    return {
        k: common._source_identity(sources[k], *pin, k)
        for k, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    owner = common._decode_body(data, image, sources["program_facts"], START)
    whole = b"".join(bytes(r.bytes) for r in owner)
    _require(
        len(whole) == 269 and hashlib.sha256(whole).hexdigest() == parent.OWNER_SHA256,
        "callback assertion prefix owner differs",
    )
    selected = [r for r in owner if r.address < BASE + END]
    payload = b"".join(bytes(r.bytes) for r in selected)
    _require(
        len(payload) == END - START, "callback assertion prefix selected extent differs"
    )
    mc, mp = marker._load_code(data, image, sources)
    _require(
        mp == sources["marker_conformance"]["body"]["points"],
        "callback assertion prefix marker receipt differs",
    )
    return {BASE + START: payload, BASE + marker.START: mc}, sorted(
        [common._point(r) for r in selected] + mp, key=lambda p: p["rva"]
    )


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = common._load_executable(Path(executable))
    _require(
        digest == common.EXE_SHA256 and image.image_base == BASE,
        "exact callback assertion prefix executable differs",
    )
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({r for o in observations for r in o["trace_rvas"]})
    required = {r for v in vectors() for r in _trace(v)}
    _require(
        set(union) == required, "callback assertion prefix coverage partition differs"
    )
    controls = []
    sample = next(
        v
        for v in vectors()
        if v["alignment"] == 15 and v["profile"] == 2 and v["family"] == "false"
    )
    for kind, reason in CONTROLS.items():
        try:
            _run_case(codes, points, sample, kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "callback assertion prefix control failed incidentally: "
                + kind
                + ": "
                + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError(
                "callback assertion prefix control survived: " + kind
            )
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
            assertion_boundaries=len(observations),
            marker_calls=sum(v["family"] != "null" for v in vectors()),
            controls=len(controls),
            families={
                f: sum(v["family"] == f for v in vectors())
                for f in ("null", "absent", "nil", "false")
            },
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            checked=[
                "Native null-upvalue and false-upvalue-marker validation prefixes",
                "Actual marker body executes continuously and preserves high words before parent AL guard",
                "Independent Lua prefix restoration and exact physical API frames",
                "Three native boundary argument words, actual continuations and incoming GPRs",
                "Ordered native data events, all mapped pages, caller ancestors and cookie setup",
            ],
            premises=[
                "Supplied normal cdecl Lua response words preserve nonvolatile GPRs and mapped pages",
                "Compatible false marker lookup contracts for nonzero supplied userdata",
            ],
            excluded=[
                "Assertion-helper execution, imported DLL behavior, unwind, recovery and callback return",
                "Interpretation or validation of expression and filename pointer contents",
                "Argument marker, class operation, table transfer, cookie verification and accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "callback assertion prefix executable changed",
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
        "sealed callback assertion prefix conformance differs",
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
        "exact callback assertion prefix conformance differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
