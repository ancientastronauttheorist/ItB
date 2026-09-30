"""Native factory output retained across a supplied closure invocation boundary."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from src.observatory import native_lua_class_factory_conformance as full
from src.observatory import native_lua_class_callback_conformance as callback
from src.observatory import native_lua_shared_api_layout as layout

factory, record, marker = full.factory, full.record, callback.marker
BASE = full.BASE
ConformanceError, _require = full.ConformanceError, full._require
_canonical_sha256, _canonical_bytes = full._canonical_sha256, full._canonical_bytes
_validate_json_tree, _assert_publication_safe = (
    full._validate_json_tree,
    full._assert_publication_safe,
)
ANALYSIS_KIND = "pe_native_lua_class_factory_callback_entry_conformance"
SEALED_SHA256 = "cca405ff5c16dfebb85f23c07e5333c14b300c209ad24dfab42033d17c89b94e"
END, ENDPOINT = 0x2EC1BD, BASE + 0x2EB140
SOURCE_PINS = {
    **full.SOURCE_PINS,
    "full_factory": (full.ANALYSIS_KIND, full.SEALED_SHA256),
    "callback": (callback.ANALYSIS_KIND, callback.SEALED_SHA256),
    "marker": (marker.ANALYSIS_KIND, marker.SEALED_SHA256),
}


def vectors():
    return [
        v
        for v in full.vectors()
        if v["length"] in (0, 1, 16, 255)
        and v["pattern"] == "high"
        and v["name_alignment"] == 4095
        and not v["equal_pointers"]
        and v["record_alignment"] == 0
    ]


def _load_code(data, image, sources):
    payload, points, continuation = full._load_code(data, image, sources)
    owner = full._decode_body(data, image, sources["program_facts"], callback.START)
    body = b"".join(bytes(r.bytes) for r in owner)
    _require(
        len(body) == 269 and hashlib.sha256(body).hexdigest() == callback.BODY_SHA256,
        "factory callback owner differs",
    )
    a = marker.START
    b = marker.END
    offset = image.rva_to_file_offset(a)
    child = data[offset : offset + b - a]
    marker_rows = full._decode_body(data, image, sources["program_facts"], marker.START)
    _require(
        b"".join(bytes(r.bytes) for r in marker_rows) == child
        and [full._point(r) for r in marker_rows]
        == sources["marker"]["body"]["points"],
        "factory callback marker differs",
    )
    selected = [full._point(r) for r in owner if r.address < BASE + END]
    selected += sources["marker"]["body"]["points"]
    codes = {callback.START: body[: END - callback.START], marker.START: child}
    return payload, points, continuation, codes, selected


def _produce(payload, points, continuation, vector):
    captured = {}

    def capture(machine, negative, fixture, expected, lua, ids):
        captured.update(
            fixture=fixture,
            pages={p: bytes(machine.mem_read(p, 4096)) for p in fixture["pages"]},
            closure=lua.stack[-1],
            lua_result=lua.result(),
            registers={r: machine.reg_read(i) for r, i in ids.items()},
        )

    observation = full._run_case(
        payload, points, dict(continuation, endpoint_mutation=capture), vector
    )
    _require(
        captured["closure"]
        == (
            "closure",
            BASE + callback.START,
            ("userdata", captured["fixture"]["userdata"]),
        ),
        "factory returned closure differs",
    )
    return captured, observation


def _resume(produced, vector):
    original = produced["pages"]
    pages = {p: bytearray(v) for p, v in original.items()}
    patches = []

    def put_bytes(address, data):
        for i, byte in enumerate(data):
            p, off = (address + i) & ~4095, (address + i) & 4095
            if p not in pages:
                pages[p] = bytearray(b"\xa5" * 4096)
            before = pages[p][off]
            pages[p][off] = byte
            patches.append(dict(address=address + i, before=before, after=byte))

    # The host boundary installs only named slot and literal bytes, never pages.
    for api, slot in layout.SLOTS.items():
        put_bytes(BASE + slot, layout.TARGETS[api].to_bytes(4, "little"))
    for address, value in layout.LITERALS.items():
        put_bytes(address, value)
    entry = factory.STACK + 0x800 + 15 * vector["profile"]
    state = produced["fixture"]["state"]
    put_bytes(entry, full.RETURN.to_bytes(4, "little"))
    put_bytes(entry + 4, state.to_bytes(4, "little"))
    registers = dict(produced["registers"], esp=entry)
    _require(
        all(
            pages[p] == original[p]
            for p in original
            if p not in {x["address"] & ~4095 for x in patches}
        ),
        "host boundary changed unrelated pages",
    )
    frozen = {p: bytes(v) for p, v in pages.items()}
    layout.validate_targets_and_pages(layout.TARGETS, frozen)
    u, p = produced["fixture"]["userdata"], produced["fixture"]["record"]
    _require(
        all(
            factory._raw(frozen, a, 1) == factory._raw(original, a, 1)
            for start, size in ((u, 72), (p, 24))
            for a in range(start, start + size)
        ),
        "host boundary changed factory storage",
    )
    return dict(
        entry=entry,
        state=state,
        receiver=u,
        source_pointer=0x18000001 + vector["profile"],
        registers=registers,
        pages=frozen,
        endpoint=ENDPOINT,
        patches=patches,
    )


def _logical(fixture, produced, vector):
    from src.observatory import (
        native_lua_class_factory_callback_entry_semantics as model,
    )

    return model.apply(
        state=fixture["state"],
        userdata=fixture["receiver"],
        record_pointer=produced["fixture"]["record"],
        source_pointer=fixture["source_pointer"],
        callback_entry=fixture["entry"],
        registers=fixture["registers"],
        closure_target=produced["closure"][1],
        closure_upvalues=[produced["closure"][2][1]],
        upvalue_has_metatable=True,
        argument_has_metatable=True,
        upvalue_marker_kind="zero",
        argument_marker_kind="table",
    )


def _run_prefix(codes, points, fixture, produced, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    logical = _logical(fixture, produced, vector)
    v = dict(
        frame_alignment=vector["profile"] * 15,
        marker_words=[(0, 0x12345678)[vector["profile"]], 0xFFFFFFFF],
    )
    expected = callback._expected(v, fixture, class_entry_only=True)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for p, b in fixture["pages"].items():
        machine.mem_map(p, 4096)
        machine.mem_write(p, b)
    code_pages = {
        (BASE + a + i) & ~4095 for a, b in codes.items() for i in range(len(b))
    }
    for p in code_pages | {ENDPOINT & ~4095, layout.IMPORT}:
        _require(p not in fixture["pages"], "callback entry mapping overlaps")
        machine.mem_map(p, 4096)
        machine.mem_write(p, b"\xcc" * 4096)
    for a, b in codes.items():
        machine.mem_write(BASE + a, b)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in factory.REGISTERS}
    for r, value in fixture["registers"].items():
        machine.reg_write(ids[r], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(p["rva"], 16) for p in points}
    events, visited, calls = [], [], []
    lua_stack = [("argument", fixture["source_pointer"])]
    lua_trace = []

    def apply_lua(call):
        api, group = call["api"], call["group"]
        args = list(call["arguments"])
        if len(args) > 1 and args[1] >= 0x80000000:
            args[1] -= 0x100000000
        before = list(lua_stack)
        result = 0
        if api == "lua_touserdata":
            result = call["response"]["eax"]
            _require(
                result
                == (
                    fixture["receiver"]
                    if args[1] == -10003
                    else fixture["source_pointer"]
                ),
                "callback entry userdata identity differs",
            )
        else:
            index = int(group[-1])
            identity = (fixture["receiver"], fixture["source_pointer"])[index]
            if api == "lua_getmetatable":
                lua_stack.append(("metatable", identity))
                result = call["response"]["eax"]
                _require(result == 1, "callback entry metatable contract differs")
            elif api == "lua_pushstring":
                lua_stack.append(("marker_key", identity))
            elif api == "lua_gettable":
                _require(
                    lua_stack[-2:]
                    == [("metatable", identity), ("marker_key", identity)],
                    "callback entry marker identity differs",
                )
                lua_stack[-1] = ("marker_value", identity, ("zero", "table")[index])
            elif api == "lua_toboolean":
                _require(
                    lua_stack[-1]
                    == ("marker_value", identity, ("zero", "table")[index]),
                    "callback entry marker identity differs",
                )
                result = call["response"]["eax"]
                _require(result == 1, "callback entry marker truth differs")
            elif api == "lua_settop":
                _require(
                    lua_stack[-2:]
                    == [
                        ("metatable", identity),
                        ("marker_value", identity, ("zero", "table")[index]),
                    ],
                    "callback entry marker identity differs",
                )
                del lua_stack[-2:]
            else:
                raise ConformanceError("callback entry unexpected Lua API")
        lua_trace.append(
            dict(
                api=api,
                arguments=args,
                result=result,
                before=before,
                after=list(lua_stack),
                group=group,
            )
        )

    resume = None

    def regs():
        return {r: machine.reg_read(i) for r, i in ids.items()}

    def words(address, count):
        return [
            int.from_bytes(machine.mem_read(address + 4 * i, 4), "little")
            for i in range(count)
        ]

    def on_code(m, address, size, user):
        nonlocal resume
        if negative == "marker_response" and address == BASE + 0x2EC160:
            m.reg_write(ids["eax"], m.reg_read(ids["eax"]) & 0xFFFFFF00)
        if negative == "argument_marker" and address == BASE + 0x2EC184:
            m.reg_write(ids["eax"], m.reg_read(ids["eax"]) & 0xFFFFFF00)
        if address in layout.TARGETS.values():
            _require(len(calls) < len(expected["calls"]), "callback entry extra API")
            call = expected["calls"][len(calls)]
            sp = m.reg_read(ids["esp"])
            _require(
                address == call["target"]
                and sp == call["entry_esp"]
                and words(sp, 1 + len(call["arguments"]))
                == [call["continuation"], *call["arguments"]]
                and regs() == call["entry_registers"],
                "callback entry API request differs",
            )
            response = dict(call["response"])
            if negative == "upvalue_response" and len(calls) == 0:
                response["eax"] ^= 1
            apply_lua(
                dict(
                    call,
                    arguments=words(sp + 4, len(call["arguments"])),
                    response=response,
                    api=next(k for k, v in layout.TARGETS.items() if v == address),
                )
            )
            for r in ("eax", "ecx", "edx"):
                m.reg_write(ids[r], response[r])
            m.reg_write(ids["esp"], sp + 4)
            m.reg_write(x.UC_X86_REG_EFLAGS, response["eflags"])
            calls.append(call)
            resume = call["continuation"]
            m.emu_stop()
            return
        if address == ENDPOINT:
            corrupt = {
                "userdata": fixture["receiver"],
                "record": produced["fixture"]["record"] + 13,
                "local_record": fixture["entry"] - 16,
                "continuation": fixture["entry"] - 48,
                "ancestor": fixture["entry"] + 8,
                "reference": fixture["receiver"] + 32,
            }
            if negative in corrupt:
                a = corrupt[negative]
                m.mem_write(a, bytes([m.mem_read(a, 1)[0] ^ 1]))
            if negative == "receiver_register":
                m.reg_write(ids["ecx"], fixture["receiver"] ^ 1)
            if negative == "flags":
                m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 0x10)
            m.emu_stop()
            return
        _require(
            address - BASE in allowed
            and not any(
                a <= address - BASE < b
                for a, b in (
                    (0x2EC140, 0x2EC154),
                    (0x2EC164, 0x2EC178),
                    (0x2EC188, 0x2EC19E),
                )
            ),
            "callback entry left prefix",
        )
        visited.append(f"0x{address-BASE:08x}")

    def on_memory(m, access, address, width, value, user):
        _require(width in (1, 2, 4), "callback entry memory width differs")
        events.append(
            dict(
                access="write" if access == uc.UC_MEM_WRITE else "read",
                address=address,
                width=width,
                value=(
                    value
                    if access == uc.UC_MEM_WRITE
                    else int.from_bytes(m.mem_read(address, width), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    pc = BASE + callback.START
    for _ in range(len(expected["calls"]) + 1):
        resume = None
        machine.emu_start(pc, 0, count=500)
        if resume is None:
            break
        pc = resume
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == ENDPOINT,
        "callback entry endpoint differs",
    )
    _require(
        calls == expected["calls"] and len(calls) == 12,
        "callback entry API count differs",
    )
    _require(
        regs() == expected["registers"]
        and machine.reg_read(x.UC_X86_REG_EFLAGS) & 0xCD5 == expected["flags"],
        "callback entry registers or flags differ",
    )
    _require(events == expected["events"], "callback entry ordered events differ")
    _require(
        all(
            bytes(machine.mem_read(p, 4096)) == b for p, b in expected["pages"].items()
        ),
        "callback entry protected pages differ",
    )
    normalized = lambda value: json.loads(json.dumps(value))
    _require(
        normalized(lua_trace) == normalized(logical["calls"])
        and normalized(lua_stack) == normalized(logical["boundary_lua_stack"]),
        "callback entry Lua prefix differs",
    )
    caller = logical["class_caller"]
    _require(
        regs() == caller["registers"]
        and words(regs()["esp"], 2) == [caller["return_address"], caller["argaddress"]]
        and words(caller["argaddress"], 2) == caller["argument_record"],
        "callback entry independent caller model differs",
    )
    return dict(
        vector=vector,
        trace_rvas=visited,
        registers=regs(),
        flags=expected["flags"],
        api_calls=12,
        events_sha256=_canonical_sha256(events),
        factory_pages_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(b).hexdigest()
                for p, b in produced["pages"].items()
            }
        ),
        host_patches_sha256=_canonical_sha256(fixture["patches"]),
        memory_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(b).hexdigest()
                for p, b in expected["pages"].items()
            }
        ),
    )


def _preflight(sources):
    _require(
        set(sources) == set(SOURCE_PINS), "factory callback source partition differs"
    )
    return {
        k: factory._source_identity(sources[k], *pin, k)
        for k, pin in SOURCE_PINS.items()
    }


CONTROLS = {
    "userdata": "callback entry protected pages differ",
    "record": "callback entry protected pages differ",
    "local_record": "callback entry protected pages differ",
    "continuation": "callback entry protected pages differ",
    "ancestor": "callback entry protected pages differ",
    "reference": "callback entry protected pages differ",
    "receiver_register": "callback entry registers or flags differ",
    "flags": "callback entry registers or flags differ",
    "upvalue_response": "callback entry userdata identity differs",
    "marker_response": "callback entry left prefix",
    "argument_marker": "callback entry left prefix",
}


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = full._load_executable(Path(executable))
    _require(
        digest == full.EXE_SHA256 and image.image_base == BASE,
        "exact factory callback executable differs",
    )
    payload, fp, continuation, codes, points = _load_code(data, image, sources)
    observations = []
    producer = []
    sample = None
    for vector in vectors():
        produced, observation = _produce(payload, fp, continuation, vector)
        fixture = _resume(produced, vector)
        observations.append(_run_prefix(codes, points, fixture, produced, vector))
        producer.append(observation)
        if sample is None:
            sample = (produced, fixture, vector)
    controls = []
    for kind, reason in CONTROLS.items():
        try:
            _run_prefix(codes, points, sample[1], sample[0], sample[2], kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "factory callback control failed incidentally: "
                + kind
                + ": "
                + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("factory callback control survived: " + kind)
    union = sorted({r for o in observations for r in o["trace_rvas"]})
    forbidden = (
        (0x2EC140, 0x2EC154),
        (0x2EC164, 0x2EC178),
        (0x2EC188, 0x2EC19E),
        (0x2EB5A7, 0x2EB5B4),
    )
    required = {
        p["rva"]
        for p in points
        if not any(a <= int(p["rva"], 16) < b for a, b in forbidden)
    }
    _require(
        set(union) == required
        and len(points) == 88
        and len(required) == 67
        and all(len(o["trace_rvas"]) == 94 for o in observations)
        and f"0x{ENDPOINT-BASE:08x}" not in union,
        "factory callback prefix coverage differs",
    )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{a:08x}",
                    end_rva=f"0x{a+len(b):08x}",
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
        producer_observations_sha256=_canonical_sha256(producer),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=len(observations),
            static_sites=len(points),
            executed_sites=len(union),
            instruction_bytes=sum(map(len, codes.values())),
            factory_instructions=sum(len(o["trace_rvas"]) for o in producer),
            callback_instructions=sum(len(o["trace_rvas"]) for o in observations),
            factory_api_calls=34 * len(observations),
            callback_api_calls=12 * len(observations),
            heap_calls=len(observations),
            marker_calls=2 * len(observations),
            controls=len(controls),
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            continuous_factory=True,
            continuous_callback_and_markers=True,
            continuous_across_host=False,
            checked=[
                "Actual native factory output pages retained into the callback prefix",
                "Actual userdata becomes class receiver and original local pair becomes its argument",
                "All native API frames ordered data events pages GPRs and defined ADD flags",
            ],
            premises=[
                "Explicit host closure invocation with one argument",
                "Byte scoped shared API and literal bindings",
                "Two compatible truthy marker responses and supplied userdata identities",
            ],
            excluded=[
                "Lua VM invocation and metatable or registry effects",
                "Class helper execution and callback return",
                "Heap ownership assertion delivery and accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory callback executable changed",
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
        "sealed factory callback entry differs",
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
        "exact factory callback entry differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
