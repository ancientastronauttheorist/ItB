"""Integrated normal growth with native resize machinery for small live vectors."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_scalar_vector_resize_conformance as resize
from src.observatory import native_lua_vector_growth_semantics as growth
from src.observatory.native_vector_deallocation_conformance import _sub_flags
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

ANALYSIS_KIND = "pe_native_scalar_vector_growth_conformance"
SEALED_SHA256 = "74ed35d5c0d666416b1d2d1373c26563464dd54ab97f850225db475c3c967213"
SOURCE_PINS = {
    **resize.SOURCE_PINS,
    "resize_conformance": (resize.ANALYSIS_KIND, resize.SEALED_SHA256),
    "growth": (growth.ANALYSIS_KIND, growth.SEALED_SHA256),
}
STACK, NEW, OLD, OBJECT, RETURN, IMPORT = (
    resize.STACK,
    resize.NEW,
    resize.OLD,
    resize.OBJECT,
    resize.RETURN,
    resize.IMPORT,
)
HEAP_GLOBAL, ALLOC_IAT, FREE_IAT, HEAP = (
    resize.HEAP_GLOBAL,
    resize.ALLOC_IAT,
    resize.FREE_IAT,
    resize.HEAP,
)
STACK_TEMPLATE, NEW_TEMPLATE, OLD_TEMPLATE, OBJECT_TEMPLATE = (
    resize.STACK_TEMPLATE,
    resize.NEW_TEMPLATE,
    resize.OLD_TEMPLATE,
    resize.OBJECT_TEMPLATE,
)
BODIES = {"growth": (0x2EB620, 0x2EB67E), **resize.BODIES}


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    sizes = (4, 5, 7, 8, 15, 16, 17, 31, 32, 63, 64, 127, 128, 255, 256)
    return [
        dict(
            has_old=True,
            old_size=size,
            old_capacity=cap,
            requested=max(size + 1, cap + cap // 2) if size == cap else size,
            new_alignment=a,
            old_alignment=(13 * a + 7) % 32,
            stack_alignment=f,
        )
        for size in sizes
        for cap in (size, 512)
        for a in range(32)
        for f in (0, 7, 15)
    ]


def geometry(vector):
    try:
        g = resize.geometry(vector)
    except Exception as exc:
        raise ConformanceError(str(exc)) from exc
    size, cap = vector["old_size"], vector["old_capacity"]
    _require(cap <= 512, "outside bounded growth capacity")
    grows = size == cap
    requested = max(size + 1, cap + cap // 2) if grows else size
    _require(vector["requested"] == requested, "growth request differs")
    g["grows"] = grows
    if not grows:
        g.update(
            request=None,
            new_begin=g["old_begin"],
            new_end=g["old_end"],
            new_capacity=g["old_capacity"],
            new_metadata=None,
        )
    return g


def frame_join(g):
    _require(type(g) is int and 96 <= g < 2**32 - 8, "invalid growth ancestor frame")
    return dict(
        growth=g,
        resize_entry=g - 20,
        heap_allocation_entry=g - 96,
        heap_free_entry=g - 88,
        protected_start=g - 96,
        protected_end=g + 8,
        returned=g + 8,
    )


def _expected(
    vector, initial, original_stack, original_new, original_old, original_object
):
    g = geometry(vector)
    s = initial["esp"]
    obj = initial["ecx"]
    stack = bytearray(original_stack)
    events = []

    def event(access, address, value):
        events.append(dict(access=access, address=address, width=4, value=value))
        if access == "write":
            stack[address - STACK : address - STACK + 4] = value.to_bytes(4, "little")

    w = lambda a, v: event("write", a, v)
    r = lambda a, v: event("read", a, v)
    w(s - 4, initial["esi"])
    w(s - 8, initial["edi"])
    r(obj + 8, g["old_capacity"])
    r(obj + 4, g["old_end"])
    if not g["grows"]:
        r(s - 8, initial["edi"])
        r(s - 4, initial["esi"])
        r(s, RETURN)
        spare = vector["old_capacity"] - vector["old_size"]
        regs = dict(initial, eax=spare, edx=g["old_end"], esp=s + 8)
        return dict(
            geometry=g,
            registers=regs,
            flags=_sub_flags(spare, 1),
            flag_mask=0x8D5,
            events=events,
            stack=bytes(stack),
            new=bytes(original_new),
            old=bytes(original_old),
            object=bytes(original_object),
        )
    r(obj, g["old_begin"])
    w(s - 12, initial["ebx"])
    w(s - 16, vector["requested"])
    w(s - 20, BASE + 0x2EB66E)
    cap = vector["old_capacity"]
    half = cap // 2
    regs = dict(
        initial,
        eax=cap + half,
        ebx=0x1FFFFFFF - half,
        ecx=obj,
        edx=vector["requested"],
        esi=obj,
        edi=cap,
        esp=s - 20,
    )
    child = resize._expected(
        vector, regs, stack, original_new, original_old, original_object
    )
    _require(
        child["events"][-1]
        == dict(access="read", address=s - 20, width=4, value=RETURN),
        "resize oracle continuation differs",
    )
    child["events"][-1] = dict(
        access="read", address=s - 20, width=4, value=BASE + 0x2EB66E
    )
    events += child["events"]
    stack = bytearray(child["stack"])
    r(s - 12, initial["ebx"])
    r(s - 8, initial["edi"])
    r(s - 4, initial["esi"])
    r(s, RETURN)
    regs = child["registers"]
    regs.update(ebx=initial["ebx"], esi=initial["esi"], edi=initial["edi"], esp=s + 8)
    return dict(
        geometry=g,
        registers=regs,
        flags=child["flags"],
        flag_mask=child["flag_mask"],
        events=events,
        stack=bytes(stack),
        new=child["new"],
        old=child["old"],
        object=child["object"],
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
    for table, targets in resize.copy_replay.TABLES.items():
        offset = image.rva_to_file_offset(table)
        _require(
            data[offset : offset + 16]
            == b"".join((BASE + v).to_bytes(4, "little") for v in targets),
            "exact copy table differs",
        )
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({p for c in observations for p in c["trace_rvas"]})
    _require(
        all(
            p["rva"] in union for p in points["growth"] if int(p["rva"], 16) < 0x2EB674
        ),
        "normal growth coverage differs",
    )
    controls = []
    sample = next(v for v in vectors() if v["old_size"] == 4 and v["requested"] == 6)
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
            claim="Native growth executes resize, allocation, feature-zero scalar copy and deallocation; only successful heap API responses remain supplied",
            domain="Sampled live sizes four through 256; full capacities equal size and spare capacities equal 512; all block alignments paired over three stack alignments",
            frame_relation="Growth G reaches resize G-20, allocation API G-96 and free API G-88; all returns consume the unused argument and finish G+8",
            oracle_join="Fresh growth equations rebase the sealed scalar resize oracle and substitute the native continuation",
            premises=[
                "Disjoint object, old and new buffers and full ancestor stack; DF clear; copy feature words zero and tables immutable",
                "Stable heap and imports; successful stdcall API responses preserve memory and nonvolatile registers",
            ],
            not_claimed=[
                "Actual heap effects, failures, larger live vectors, SIMD modes or arbitrary geometry",
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
        "sealed integrated growth differs",
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
        "exact integrated growth differs",
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
        for t, targets in resize.copy_replay.TABLES.items()
    }
    for address, payload in table_payloads.items():
        machine.mem_write(address, payload)
    machine.mem_write(IMPORT, b"\xcc")
    s = STACK + 0x2000 + vector["stack_alignment"]
    obj = OBJECT + 0x100
    stack, new, old, objects = map(
        bytearray, (STACK_TEMPLATE, NEW_TEMPLATE, OLD_TEMPLATE, OBJECT_TEMPLATE)
    )
    for address, value in ((s, RETURN), (s + 4, vector["requested"])):
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
    initial.update(esp=s, ecx=obj)
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
                    and sp == s - 96
                    and words[1:] == [HEAP, 0, g["request"]],
                    "nested allocation handoff differs",
                )
                result = g["new_raw"]
            elif continuation == BASE + 0x389172:
                role = "free"
                _require(
                    vector["has_old"]
                    and sp == s - 88
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
    start = BASE + 0x2EB620
    for _ in range(3):
        resume = None
        machine.emu_start(start, RETURN, count=4000)
        if resume is None:
            break
        start = resume
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == RETURN, "integrated resize did not return"
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
        and bytes(machine.mem_read(OBJECT, 0x1000)) == expected["object"],
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
