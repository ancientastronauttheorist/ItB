"""Native append slice with fully native bounded growth and relocation machinery."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_scalar_vector_growth_conformance as linked_growth
from src.observatory import native_lua_class_vector_append_semantics as append
from src.observatory.native_lua_vector_allocation_return_conformance import _add_flags
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _load_executable,
    _point,
    _source_identity,
    _canonical_bytes,
    _canonical_sha256,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "pe_native_scalar_vector_append_conformance"
SEALED_SHA256 = "df08d84b1392a9566a6c0f89b65332515e5faa1ca252c04718f6d8fcc69fcdcb"
SOURCE_PINS = {
    **linked_growth.SOURCE_PINS,
    "growth_conformance": (linked_growth.ANALYSIS_KIND, linked_growth.SEALED_SHA256),
    "append": (append.ANALYSIS_KIND, append.SEALED_SHA256),
}
STACK, NEW, OLD, OBJECT, RETURN, IMPORT = (
    linked_growth.STACK,
    linked_growth.NEW,
    linked_growth.OLD,
    linked_growth.OBJECT,
    linked_growth.RETURN,
    linked_growth.IMPORT,
)
HEAP_GLOBAL, ALLOC_IAT, FREE_IAT, HEAP = (
    linked_growth.HEAP_GLOBAL,
    linked_growth.ALLOC_IAT,
    linked_growth.FREE_IAT,
    linked_growth.HEAP,
)
STACK_TEMPLATE, NEW_TEMPLATE, OLD_TEMPLATE, OBJECT_TEMPLATE = (
    linked_growth.STACK_TEMPLATE,
    linked_growth.NEW_TEMPLATE,
    linked_growth.OLD_TEMPLATE,
    linked_growth.OBJECT_TEMPLATE,
)
ARG_LOW, ARG_HIGH = 0x01000000, 0x0A000000
LOW_TEMPLATE = bytes(((i * 47) ^ 0x35) & 255 for i in range(0x1000))
HIGH_TEMPLATE = bytes(((i * 53) ^ 0xD1) & 255 for i in range(0x1000))
STOP = BASE + 0x2EB21A
BODIES = {"append": (0x2EB1BB, 0x2EB21A), **linked_growth.BODIES}


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    result = []
    for v in linked_growth.vectors():
        result.extend(
            [
                {**v, "argument_kind": kind, "internal_index": 0}
                for kind in ("external_low", "external_high")
            ]
        )
        if v["old_size"]:
            result.extend(
                [
                    {**v, "argument_kind": "internal", "internal_index": i}
                    for i in sorted({0, v["old_size"] - 1})
                ]
            )
    return result


def geometry(vector):
    try:
        g = linked_growth.geometry(vector)
    except Exception as exc:
        raise ConformanceError(str(exc)) from exc
    kind = vector["argument_kind"]
    index = vector["internal_index"]
    _require(
        type(kind) is str and kind in ("internal", "external_low", "external_high"),
        "invalid argument kind",
    )
    _require(
        type(index) is int
        and (0 <= index < vector["old_size"] if kind == "internal" else index == 0),
        "invalid internal index",
    )
    argument = (
        g["old_begin"] + index * 8
        if kind == "internal"
        else (ARG_LOW if kind == "external_low" else ARG_HIGH) + 0x100
    )
    g.update(
        argument=argument,
        internal=kind == "internal",
        source=g["new_begin"] + index * 8 if kind == "internal" else argument,
        destination=g["new_end"],
        final_end=g["new_end"] + 8,
    )
    _require(
        g["destination"] > 0 and g["final_end"] <= g["new_capacity"],
        "append destination lacks a complete element",
    )
    return g


def frame_join(s):
    _require(type(s) is int and 104 <= s < 2**32 - 48, "invalid append ancestor frame")
    return dict(
        slice_esp=s,
        frame=s + 32,
        owner_local=s + 20,
        growth_entry=s - 8,
        resize_entry=s - 28,
        heap_allocation_entry=s - 104,
        heap_free_entry=s - 96,
        protected_start=s - 104,
        protected_end=s + 48,
        exit_esp=s,
    )


def _expected(
    vector, initial, original_stack, original_new, original_old, original_object
):
    g = geometry(vector)
    s = initial["esp"]
    f = initial["ebp"]
    o = OBJECT + 0x100
    v = o + 4
    stack, new, old, objects = map(
        bytearray, (original_stack, original_new, original_old, original_object)
    )
    events = []

    def event(access, address, value):
        events.append(dict(access=access, address=address, width=4, value=value))
        if access == "write":
            target, base = (
                (stack, STACK)
                if STACK <= address < STACK + 0x4000
                else (
                    (new, NEW)
                    if NEW <= address < NEW + 0x4000
                    else (
                        (old, OLD)
                        if OLD <= address < OLD + 0x4000
                        else (objects, OBJECT)
                    )
                )
            )
            target[address - base : address - base + 4] = value.to_bytes(4, "little")

    w = lambda a, value: event("write", a, value)
    r = lambda a, value: event("read", a, value)
    r(f - 12, o)
    r(o + 8, g["old_end"])
    regs = dict(initial, esi=o, eax=g["old_end"])
    if g["argument"] < g["old_end"]:
        r(o + 4, g["old_begin"])
        regs["ecx"] = g["old_begin"]
    if g["internal"]:
        regs["edi"] = vector["internal_index"]
    r(o + 12, g["old_capacity"])
    if g["grows"]:
        continuation = BASE + (0x2EB1DF if g["internal"] else 0x2EB205)
        w(s - 4, regs["ecx"])
        w(s - 8, continuation)
        regs.update(ecx=v, esp=s - 8)
        child = linked_growth._expected(vector, regs, stack, new, old, objects)
        _require(
            child["events"][-1]
            == dict(access="read", address=s - 8, width=4, value=RETURN),
            "growth oracle continuation differs",
        )
        child["events"][-1] = dict(
            access="read", address=s - 8, width=4, value=continuation
        )
        events += child["events"]
        stack, new, old, objects = map(
            bytearray, (child["stack"], child["new"], child["old"], child["object"])
        )
        regs = child["registers"]
    r(o + 8, g["destination"])
    if g["internal"]:
        r(o + 4, g["new_begin"])
        regs.update(edx=g["destination"], ecx=g["new_begin"])
    else:
        regs["ecx"] = g["destination"]
    copied = []
    for offset in (0, 4):
        address = g["source"] + offset
        source, base = (
            (new, NEW)
            if NEW <= address < NEW + 0x4000
            else (
                (old, OLD)
                if OLD <= address < OLD + 0x4000
                else (
                    (LOW_TEMPLATE, ARG_LOW)
                    if ARG_LOW <= address < ARG_LOW + 0x1000
                    else (HIGH_TEMPLATE, ARG_HIGH)
                )
            )
        )
        word = int.from_bytes(source[address - base : address - base + 4], "little")
        copied.append(word)
        r(address, word)
        w(g["destination"] + offset, word)
    r(o + 8, g["destination"])
    w(o + 8, g["final_end"])
    regs.update(
        eax=copied[-1],
        esi=o,
        edi=vector["internal_index"] if g["internal"] else g["argument"],
        esp=s,
    )
    return dict(
        geometry=g,
        registers=regs,
        flags=_add_flags(g["destination"], 8),
        flag_mask=0x8D5,
        events=events,
        stack=bytes(stack),
        new=bytes(new),
        old=bytes(old),
        object=bytes(objects),
        copy_values=copied,
    )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256, "executable differs")
    all_points = {}
    bodies = [
        sources["append"]["slice"],
        sources["growth"]["body"],
        sources["owner"]["body"],
        *sources["allocation_conformance"]["bodies"].values(),
        sources["deallocation_composition"]["guard_body"],
        *sources["deallocation_composition"]["free_bodies"],
        *sources["scalar_copy"]["body"]["ranges"],
    ]
    for body in bodies:
        for point in body["points"]:
            _require(point["rva"] not in all_points, "source point overlap")
            all_points[point["rva"]] = point
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    codes, points = {}, {}
    for name, (a, b) in BODIES.items():
        offset = image.rva_to_file_offset(a)
        codes[name] = data[offset : offset + b - a]
        points[name] = [_point(r) for r in decoder.disasm(codes[name], BASE + a)]
        _require(
            sum(p["size"] for p in points[name]) == b - a
            and all(all_points.get(p["rva"]) == p for p in points[name]),
            "integrated witness differs",
        )
    for table, targets in linked_growth.resize.copy_replay.TABLES.items():
        offset = image.rva_to_file_offset(table)
        _require(
            data[offset : offset + 16]
            == b"".join((BASE + v).to_bytes(4, "little") for v in targets),
            "exact copy table differs",
        )
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({p for c in observations for p in c["trace_rvas"]})
    _require(
        all(p["rva"] in union for p in points["append"]),
        "append coverage differs",
    )
    controls = []
    sample = next(
        v
        for v in vectors()
        if v["old_size"] == 4
        and v["requested"] == 6
        and v["argument_kind"] == "external_high"
    )
    for kind, message in (
        ("ancestor", "integrated ancestor memory differs"),
        ("payload", "integrated payload or metadata differs"),
    ):
        try:
            _run_case(codes, points, sample, kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "negative control failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("integrated mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=ids,
        build_identity=sources["owner"]["build_identity"],
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=union,
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            loaded_bytes=sum(len(c) for c in codes.values()),
            table_data_bytes=32,
            loaded_sites=sum(len(p) for p in points.values()),
            executed_sites=len(union),
            resized_cases=sum(geometry(v)["grows"] for v in vectors()),
            allocation_api_summaries=sum(
                c["role"] == "allocate" for o in observations for c in o["summaries"]
            ),
            free_api_summaries=sum(
                c["role"] == "free" for o in observations for c in o["summaries"]
            ),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="The append slice executes native growth, resize, allocation, feature-zero scalar copy and deallocation; only successful heap API responses are supplied",
            domain="Sampled live sizes four through 256; full vectors grow, capacity-512 vectors append directly; aligned internal first or last elements or independent external argument pages",
            frame_relation="Slice ESP S and EBP S+32; owner local S+20; growth entry S-8, allocation API S-104, free API S-96; exit before epilogue at unchanged ESP S",
            oracle_join="Fresh append equations rebase the sealed independent growth oracle with native continuations; ordered two-word copying uses relocated internal indices",
            premises=[
                "Disjoint mapped object, old and new buffers, external argument pages and full ancestor stack; DF clear; stable zero copy feature words and immutable tables",
                "Stable heap and imports; supplied successful stdcall responses preserve storage and nonvolatile registers",
            ],
            not_claimed=[
                "Parent tree prefix or cookie epilogue; actual heap effects; failures; larger live vectors; arbitrary geometry",
                "Full game equivalence or accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    _validate_json_tree(evidence, "evidence")
    ids = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == ids
        and evidence["vectors"] == vectors(),
        "sealed integrated append differs",
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
        "exact integrated append differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )


def _run_case(codes, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    g = geometry(vector)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    pages = {BASE + (a & ~0xFFF) for a, b in BODIES.values()}
    pages.update(
        (
            RETURN,
            IMPORT,
            HEAP_GLOBAL & ~0xFFF,
            ALLOC_IAT & ~0xFFF,
            OBJECT,
            ARG_LOW,
            ARG_HIGH,
            0x893000,
            0x8B6000,
        )
    )
    for page in sorted(pages):
        machine.mem_map(page, 0x1000)
    for page in (STACK, NEW, OLD):
        machine.mem_map(page, 0x4000)
    for name, (a, b) in BODIES.items():
        machine.mem_write(BASE + a, codes[name])
    table_payloads = {
        BASE + t: b"".join((BASE + v).to_bytes(4, "little") for v in targets)
        for t, targets in linked_growth.resize.copy_replay.TABLES.items()
    }
    for address, payload in table_payloads.items():
        machine.mem_write(address, payload)
    machine.mem_write(IMPORT, b"\xcc")
    s = STACK + 0x2000 + vector["stack_alignment"]
    obj = OBJECT + 0x104
    stack, new, old, objects = map(
        bytearray, (STACK_TEMPLATE, NEW_TEMPLATE, OLD_TEMPLATE, OBJECT_TEMPLATE)
    )
    for address, value in (
        (s, RETURN),
        (s + 4, vector["requested"]),
        (s + 20, OBJECT + 0x100),
    ):
        stack[address - STACK : address - STACK + 4] = value.to_bytes(4, "little")
    for i, key in enumerate(("old_begin", "old_end", "old_capacity")):
        objects[obj - OBJECT + 4 * i : obj - OBJECT + 4 * i + 4] = g[key].to_bytes(
            4, "little"
        )
    if g["old_metadata"] is not None:
        at = g["old_metadata"] - OLD
        old[at : at + 4] = g["old_raw"].to_bytes(4, "little")
    globals = bytearray(0x1000)
    offset = HEAP_GLOBAL & 0xFFF
    globals[offset : offset + 4] = HEAP.to_bytes(4, "little")
    iat = bytearray(0x1000)
    for address in (ALLOC_IAT, FREE_IAT):
        iat[address & 0xFFF : (address & 0xFFF) + 4] = IMPORT.to_bytes(4, "little")
    for page, payload in (
        (STACK, stack),
        (NEW, new),
        (OLD, old),
        (OBJECT, objects),
        (ARG_LOW, LOW_TEMPLATE),
        (ARG_HIGH, HIGH_TEMPLATE),
        (HEAP_GLOBAL & ~0xFFF, globals),
        (ALLOC_IAT & ~0xFFF, iat),
    ):
        machine.mem_write(page, bytes(payload))
    ids = {
        "eax": x.UC_X86_REG_EAX,
        "ebx": x.UC_X86_REG_EBX,
        "ecx": x.UC_X86_REG_ECX,
        "edx": x.UC_X86_REG_EDX,
        "esi": x.UC_X86_REG_ESI,
        "edi": x.UC_X86_REG_EDI,
        "ebp": x.UC_X86_REG_EBP,
        "esp": x.UC_X86_REG_ESP,
    }
    initial = {r: 0x16273849 + i * 0x1010101 for i, r in enumerate(ids)}
    initial.update(esp=s, ebp=s + 32, ecx=0x1A2B3C4D, edi=g["argument"])
    expected = _expected(vector, initial, stack, new, old, objects)
    for reg, value in initial.items():
        machine.reg_write(ids[reg], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(p["rva"], 16) for rows in points.values() for p in rows}
    visited, events, summaries = [], [], []
    resume = None

    def on_code(m, address, size, user):
        nonlocal resume
        if address == IMPORT:
            sp = m.reg_read(x.UC_X86_REG_ESP)
            words = [
                int.from_bytes(m.mem_read(sp + 4 * i, 4), "little") for i in range(4)
            ]
            continuation = words[0]
            if continuation == BASE + 0x389463:
                role = "allocate"
                _require(
                    g["request"] is not None
                    and sp == s - 104
                    and words[1:] == [HEAP, 0, g["request"]],
                    "nested allocation handoff differs",
                )
                result = g["new_raw"]
            elif continuation == BASE + 0x389172:
                role = "free"
                _require(
                    vector["has_old"]
                    and sp == s - 96
                    and words[1:] == [HEAP, 0, g["old_raw"]],
                    "nested free handoff differs",
                )
                result = 1
            else:
                raise ConformanceError("unexpected imported continuation")
            _require(role not in [c["role"] for c in summaries], "repeated API call")
            m.reg_write(x.UC_X86_REG_EAX, result)
            m.reg_write(x.UC_X86_REG_ECX, 0xA0000001)
            m.reg_write(x.UC_X86_REG_EDX, 0xB0000001)
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            m.reg_write(x.UC_X86_REG_ESP, sp + 16)
            if negative == "ancestor" and role == "allocate":
                m.mem_write(s + 4, (vector["requested"] ^ 1).to_bytes(4, "little"))
            if negative == "payload" and role == "free" and g["copy_bytes"]:
                first = int.from_bytes(m.mem_read(g["new_begin"], 1), "little")
                m.mem_write(g["new_begin"], bytes([first ^ 1]))
            summaries.append(dict(role=role, entry_esp=sp, continuation=continuation))
            resume = continuation
            m.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "execution escaped integrated successful resize")
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, size, value, user):
        _require(size in (1, 4), "unexpected integrated access width")
        write = access == uc.UC_MEM_WRITE
        _require(
            write
            or not (
                OLD <= address < OLD + 0x4000
                and any(c["role"] == "free" for c in summaries)
            ),
            "read from released old storage",
        )
        events.append(
            dict(
                access="write" if write else "read",
                address=address,
                width=size,
                value=(
                    value
                    if write
                    else int.from_bytes(m.mem_read(address, size), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    start = BASE + 0x2EB1BB
    for _ in range(3):
        resume = None
        machine.emu_start(start, STOP, count=4000)
        if resume is None:
            break
        start = resume
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == STOP, "integrated resize did not return"
    )
    _require(
        [c["role"] for c in summaries]
        == (["allocate"] if g["request"] is not None else [])
        + (["free"] if g["grows"] and vector["has_old"] else []),
        "API sequence differs",
    )
    actual = {r: machine.reg_read(i) for r, i in ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        actual == expected["registers"]
        and flags & expected["flag_mask"] == expected["flags"] & expected["flag_mask"]
        and not (flags & 0x400),
        "integrated register or flag oracle differs",
    )
    _require(events == expected["events"], "integrated ordered event oracle differs")
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == expected["stack"],
        "integrated ancestor memory differs",
    )
    _require(
        bytes(machine.mem_read(NEW, 0x4000)) == expected["new"]
        and bytes(machine.mem_read(OLD, 0x4000)) == expected["old"]
        and bytes(machine.mem_read(OBJECT, 0x1000)) == expected["object"]
        and bytes(machine.mem_read(ARG_LOW, 0x1000)) == LOW_TEMPLATE
        and bytes(machine.mem_read(ARG_HIGH, 0x1000)) == HIGH_TEMPLATE,
        "integrated payload or metadata differs",
    )
    _require(
        bytes(machine.mem_read(HEAP_GLOBAL & ~0xFFF, 0x1000)) == bytes(globals)
        and bytes(machine.mem_read(ALLOC_IAT & ~0xFFF, 0x1000)) == bytes(iat),
        "integrated global or IAT memory differs",
    )
    _require(
        all(
            bytes(machine.mem_read(page, 0x1000)) == bytes(0x1000)
            for page in (0x893000, 0x8B6000)
        ),
        "feature memory differs",
    )
    _require(
        all(
            bytes(machine.mem_read(address, len(payload))) == payload
            for address, payload in table_payloads.items()
        ),
        "copy table memory differs",
    )
    return dict(
        inputs=vector,
        registers=actual,
        flags=flags & expected["flag_mask"],
        flag_mask=expected["flag_mask"],
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        stack_sha256=hashlib.sha256(expected["stack"]).hexdigest(),
        new_sha256=hashlib.sha256(expected["new"]).hexdigest(),
        old_sha256=hashlib.sha256(expected["old"]).hexdigest(),
        object_sha256=hashlib.sha256(expected["object"]).hexdigest(),
        summaries=summaries,
    )
