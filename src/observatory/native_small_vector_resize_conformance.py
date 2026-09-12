"""Integrated successful resize for zero through three live eight-byte elements."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_vector_resize_semantics as owner
from src.observatory import native_vector_allocation_composition as allocation_contract
from src.observatory import native_vector_allocation_conformance as allocator
from src.observatory import native_small_copy_semantics as copy_contract
from src.observatory import native_small_copy_conformance as copy_replay
from src.observatory import native_vector_deallocation_composition as free_contract
from src.observatory import native_vector_deallocation_conformance_joined as deallocator
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

ANALYSIS_KIND = "pe_native_small_vector_resize_conformance"
SEALED_SHA256 = "d4782f1090f4b946000fecdca97898e6eb803acc477541e0891df01767c59a39"
SOURCE_PINS = {
    "owner": (owner.ANALYSIS_KIND, owner.SEALED_SHA256),
    "allocation_composition": (
        allocation_contract.ANALYSIS_KIND,
        allocation_contract.SEALED_SHA256,
    ),
    "allocation_conformance": (allocator.ANALYSIS_KIND, allocator.SEALED_SHA256),
    "small_copy": (copy_contract.ANALYSIS_KIND, copy_contract.SEALED_SHA256),
    "deallocation_composition": (
        free_contract.ANALYSIS_KIND,
        free_contract.SEALED_SHA256,
    ),
    "deallocation_conformance": (deallocator.ANALYSIS_KIND, deallocator.SEALED_SHA256),
}
STACK, NEW, RETURN, IMPORT = (
    allocator.STACK,
    allocator.DATA,
    allocator.RETURN,
    allocator.IMPORT,
)
OLD, OBJECT = 0x08000000, 0x09000000
HEAP_GLOBAL, ALLOC_IAT, FREE_IAT = (
    allocator.HEAP_GLOBAL,
    allocator.IAT,
    deallocator.FREE_IAT,
)
HEAP = allocator.HEAP_HANDLE
BODIES = {
    "owner": (0x2EB680, 0x2EB6E5),
    **{"allocate_" + k: v for k, v in allocator.BODIES.items()},
    **{"copy_" + str(i): v for i, v in enumerate(copy_replay.RANGES)},
    **{"free_" + k: v for k, v in deallocator.BODIES.items()},
}
STACK_TEMPLATE = bytes(((i * 43) ^ (i >> 6) ^ 0xC7) & 255 for i in range(0x4000))
NEW_TEMPLATE = bytes(((i * 29) ^ (i >> 2) ^ 0xB3) & 255 for i in range(0x4000))
OLD_TEMPLATE = bytes(((i * 31) ^ (i >> 4) ^ 0x67) & 255 for i in range(0x4000))
OBJECT_TEMPLATE = bytes(((i * 11) ^ 0x6D) & 255 for i in range(0x1000))


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    profiles = {(False, 0, 0, n) for n in (0, 1, 512, 513)}
    profiles.update(
        (True, s, c, n) for s in range(4) for c in (4, 512) for n in (s, 4, 512, 513)
    )
    profiles.update((True, 0, 0, n) for n in (0, 4, 512, 513))
    return [
        dict(
            has_old=old,
            old_size=s,
            old_capacity=c,
            requested=n,
            new_alignment=a,
            old_alignment=(13 * a + 7) % 32,
            stack_alignment=f,
        )
        for old, s, c, n in sorted(profiles)
        for a in range(32)
        for f in (0, 1, 7, 15)
    ]


def geometry(vector):
    _require(type(vector["has_old"]) is bool, "invalid old-storage presence")
    for key in (
        "old_size",
        "old_capacity",
        "requested",
        "new_alignment",
        "old_alignment",
        "stack_alignment",
    ):
        _require(type(vector[key]) is int, "invalid integral geometry")
    size, cap, n = vector["old_size"], vector["old_capacity"], vector["requested"]
    _require(
        0 <= size <= 3 and size <= cap <= 512 and size <= n <= 513,
        "outside small resize geometry",
    )
    _require(
        0 <= vector["new_alignment"] < 32
        and 0 <= vector["old_alignment"] < 32
        and 0 <= vector["stack_alignment"] < 16,
        "invalid alignment",
    )
    _require(vector["has_old"] or size == cap == 0, "null old storage must be empty")
    new_raw = vector.get("new_pointer", NEW + 0x100 + vector["new_alignment"])
    try:
        allocator.successful_oracle(n, new_raw)
    except Exception as exc:
        raise ConformanceError(str(exc)) from exc
    old_raw = OLD + 0x100 + vector["old_alignment"] if vector["has_old"] else 0
    if "old_pointer" in vector:
        old_raw = vector["old_pointer"]
        _require(
            vector["has_old"]
            and cap <= 4
            and type(old_raw) is int
            and 0 < old_raw <= 0xFFFFFFFF - 8 * cap,
            "invalid explicit old pointer",
        )
    old_begin = (
        32 * ((old_raw + 35) // 32) if vector["has_old"] and cap >= 512 else old_raw
    )
    new_begin = 0 if n == 0 else 32 * ((new_raw + 35) // 32) if n >= 512 else new_raw
    request = None if n == 0 else 8 * n + (35 if n >= 512 else 0)
    return dict(
        old_raw=old_raw,
        old_begin=old_begin,
        old_end=old_begin + 8 * size,
        old_capacity=old_begin + 8 * cap,
        old_metadata=old_begin - 4 if vector["has_old"] and cap >= 512 else None,
        new_raw=new_raw,
        new_begin=new_begin,
        new_end=new_begin + 8 * size,
        new_capacity=new_begin + 8 * n,
        new_metadata=new_begin - 4 if n >= 512 else None,
        request=request,
        copy_bytes=8 * size,
    )


def frame_join(s):
    _require(type(s) is int and 76 <= s < 2**32 - 8, "invalid integrated frame")
    return dict(
        owner=s,
        allocation_entry=s - 28,
        heap_allocation_entry=s - 76,
        copy_entry=s - 36,
        copy_saved_edi=s - 40,
        copy_saved_esi=s - 44,
        deallocation_entry=s - 36,
        heap_free_entry=s - 68,
        protected_start=s - 76,
        protected_end=s + 8,
        returned=s + 8,
    )


def _expected(
    vector,
    initial,
    original_stack,
    original_new,
    original_old,
    original_object,
    *,
    stack_base=STACK,
    object_base=OBJECT,
    old_base=OLD,
):
    g = geometry(vector)
    s = initial["esp"]
    obj = initial["ecx"]
    _require(
        type(stack_base) is int and 0 <= stack_base <= 2**32 - len(original_stack),
        "invalid stack mapping",
    )
    _require(
        type(object_base) is int and 0 <= object_base <= 2**32 - len(original_object),
        "invalid object mapping",
    )
    _require(
        type(s) is int
        and stack_base <= s - 76
        and s + 8 <= stack_base + len(original_stack),
        "resize frame outside stack mapping",
    )
    _require(
        type(obj) is int
        and object_base <= obj
        and obj + 12 <= object_base + len(original_object),
        "resize object outside mapping",
    )
    spans = sorted(
        (
            (stack_base, stack_base + len(original_stack)),
            (object_base, object_base + len(original_object)),
            (NEW, NEW + len(original_new)),
        )
    )
    _require(
        all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), "resize mappings overlap"
    )
    _require(
        type(old_base) is int and 0 <= old_base <= 2**32 - len(original_old),
        "invalid old buffer mapping",
    )
    relocated = (
        stack_base != STACK
        or object_base != OBJECT
        or old_base != OLD
        or "new_pointer" in vector
        or "old_pointer" in vector
    )
    if vector["has_old"]:
        _require(
            len(original_old) <= 2**32 - old_base
            and old_base
            <= g["old_begin"]
            <= g["old_end"]
            <= old_base + len(original_old),
            "old live storage outside mapped buffer",
        )
        old_span = (old_base, old_base + len(original_old))
        _require(
            all(old_span[1] <= a or b <= old_span[0] for a, b in spans),
            "old storage overlaps resize mappings",
        )
        _require(
            g["old_capacity"] <= old_base + len(original_old),
            "old capacity outside mapped buffer",
        )
        _require(
            g["old_metadata"] is None
            or old_base <= g["old_metadata"]
            and g["old_metadata"] + 4 <= old_base + len(original_old),
            "old metadata outside mapped buffer",
        )
        if relocated:
            _require(
                vector["old_capacity"] <= 4
                and vector["requested"] <= 4
                and g["old_capacity"] <= old_base + len(original_old),
                "relocated old storage outside small geometry",
            )
    stack, new, old, objects = map(
        bytearray, (original_stack, original_new, original_old, original_object)
    )
    events = []

    def event(access, address, value, width=4):
        events.append(dict(access=access, address=address, width=width, value=value))
        if access == "write":
            target, base = (
                (stack, stack_base)
                if stack_base <= address < stack_base + len(stack)
                else (
                    (new, NEW)
                    if NEW <= address < NEW + len(new)
                    else (objects, object_base)
                )
            )
            target[address - base : address - base + width] = value.to_bytes(
                width, "little"
            )

    w = lambda a, v: event("write", a, v)
    r = lambda a, v: event("read", a, v)
    w(s - 4, initial["ebp"])
    w(s - 8, obj)
    r(s + 4, vector["requested"])
    w(s - 12, initial["ebx"])
    w(s - 16, initial["esi"])
    w(s - 20, initial["edi"])
    w(s - 24, vector["requested"])
    w(s - 8, vector["requested"])
    w(s - 28, BASE + 0x2EB695)
    regs = dict(initial, ebp=s - 4, esp=s - 28, eax=vector["requested"], esi=obj)
    allocated = allocator._expected(
        dict(count=vector["requested"], pointer=g["new_raw"]),
        regs,
        stack,
        new,
        stack_base=stack_base,
    )
    _require(
        allocated["events"][-1]
        == dict(access="read", address=s - 28, width=4, value=RETURN),
        "allocation oracle continuation differs",
    )
    allocated["events"][-1] = dict(
        access="read", address=s - 28, width=4, value=BASE + 0x2EB695
    )
    events += allocated["events"]
    stack = bytearray(allocated["stack"])
    new = bytearray(allocated["payload"])
    regs = allocated["registers"]
    r(obj, g["old_begin"])
    r(obj + 4, g["old_end"])
    w(s - 24, g["copy_bytes"])
    w(s - 28, g["old_begin"])
    w(s - 32, g["new_begin"])
    w(s - 36, BASE + 0x2EB6A6)
    w(s - 40, g["new_begin"])
    w(s - 44, obj)
    r(s - 28, g["old_begin"])
    r(s - 24, g["copy_bytes"])
    r(s - 32, g["new_begin"])
    last_word = 0
    for offset in range(0, g["copy_bytes"], 4):
        at = g["old_begin"] - old_base + offset
        last_word = int.from_bytes(old[at : at + 4], "little")
        r(g["old_begin"] + offset, last_word)
        w(g["new_begin"] + offset, last_word)
    r(s - 32, g["new_begin"])
    r(s - 44, obj)
    r(s - 40, g["new_begin"])
    r(s - 36, BASE + 0x2EB6A6)
    regs.update(
        eax=g["new_begin"],
        ecx=0,
        edx=last_word,
        edi=g["new_begin"],
        esi=obj,
        esp=s - 32,
    )
    r(obj, g["old_begin"])
    r(obj + 4, g["old_end"])
    regs.update(ecx=g["old_begin"], ebx=vector["old_size"], esp=s - 20)
    if vector["has_old"]:
        r(obj + 8, g["old_capacity"])
        w(s - 24, 8)
        w(s - 28, vector["old_capacity"])
        w(s - 32, g["old_begin"])
        w(s - 36, BASE + 0x2EB6C8)
        regs.update(eax=vector["old_capacity"], esp=s - 36)
        free_vector = dict(
            pointer=g["old_begin"],
            count=vector["old_capacity"],
            stride=8,
            metadata=g["old_raw"] if g["old_metadata"] is not None else None,
            responses=[dict(kind="heap_free", eax=1)],
            heap=HEAP,
        )
        freed = deallocator._expected(
            free_vector, regs, stack, new[:0x1000], stack_base=stack_base
        )
        _require(
            freed["events"][-1]
            == dict(access="read", address=s - 36, width=4, value=RETURN),
            "deallocation oracle continuation differs",
        )
        freed["events"][-1] = dict(
            access="read", address=s - 36, width=4, value=BASE + 0x2EB6C8
        )
        events += freed["events"]
        stack = bytearray(freed["stack"])
        regs = freed["registers"]
        _require(
            freed["error"] == bytes(new[:0x1000]),
            "success oracle unexpectedly changed error storage",
        )
    r(s - 8, vector["requested"])
    w(obj + 8, g["new_capacity"])
    w(obj + 4, g["new_end"])
    w(obj, g["new_begin"])
    r(s - 20, initial["edi"])
    r(s - 16, initial["esi"])
    r(s - 12, initial["ebx"])
    r(s - 4, initial["ebp"])
    r(s, RETURN)
    regs.update(
        eax=g["new_end"],
        ebx=initial["ebx"],
        esi=initial["esi"],
        edi=initial["edi"],
        ebp=initial["ebp"],
        esp=s + 8,
    )
    flags, mask = (
        (_add_flags(s - 32, 12), 0x8D5) if vector["has_old"] else (0x44, 0x8C5)
    )
    _require(
        (
            new[g["new_begin"] - NEW : g["new_end"] - NEW]
            == old[g["old_begin"] - old_base : g["old_end"] - old_base]
            if g["copy_bytes"]
            else True
        ),
        "snapshot payload oracle differs",
    )
    return dict(
        geometry=g,
        registers=regs,
        flags=flags,
        flag_mask=mask,
        events=events,
        stack=bytes(stack),
        new=bytes(new),
        old=bytes(old),
        object=bytes(objects),
    )


def _run_case(codes, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    g = geometry(vector)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    pages = {BASE + (a & ~0xFFF) for a, b in BODIES.values()}
    pages.update((RETURN, IMPORT, HEAP_GLOBAL & ~0xFFF, ALLOC_IAT & ~0xFFF, OBJECT))
    for page in sorted(pages):
        machine.mem_map(page, 0x1000)
    for page in (STACK, NEW, OLD):
        machine.mem_map(page, 0x4000)
    for name, (a, b) in BODIES.items():
        machine.mem_write(BASE + a, codes[name])
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
                    and sp == s - 76
                    and words[1:] == [HEAP, 0, g["request"]],
                    "nested allocation handoff differs",
                )
                result = g["new_raw"]
            elif continuation == BASE + 0x389172:
                role = "free"
                _require(
                    vector["has_old"]
                    and sp == s - 68
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
        _require(size == 4, "unexpected integrated access width")
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
    start = BASE + 0x2EB680
    for _ in range(3):
        resume = None
        machine.emu_start(start, RETURN, count=1000)
        if resume is None:
            break
        start = resume
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == RETURN, "integrated resize did not return"
    )
    _require(
        [c["role"] for c in summaries]
        == (["allocate"] if g["request"] is not None else [])
        + (["free"] if vector["has_old"] else []),
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


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256, "executable differs")
    all_points = {}
    source_bodies = [
        sources["owner"]["body"],
        *sources["allocation_conformance"]["bodies"].values(),
        sources["deallocation_composition"]["guard_body"],
        *sources["deallocation_composition"]["free_bodies"],
        *sources["small_copy"]["body"]["ranges"],
    ]
    for body in source_bodies:
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
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({p for c in observations for p in c["trace_rvas"]})
    _require(
        all(p["rva"] in union for p in points["owner"]), "resize owner coverage differs"
    )
    controls = []
    sample = next(v for v in vectors() if v["old_size"] == 1 and v["requested"] == 512)
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
            loaded_sites=sum(len(p) for p in points.values()),
            executed_sites=len(union),
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
            claim="Native resize, allocation chain, short copy and deallocation chain execute in one state; only successful heap API responses remain supplied",
            domain="Zero through three live eight-byte elements, sampled old capacities zero, four or five hundred twelve, requested counts through five hundred thirteen, paired complete block alignments and four stack alignments",
            frame_relation="Owner S reaches allocation API at S-76, short-copy saved state at S-44, deallocation API at S-68 and restores S+8",
            oracle_join="Sealed allocation and deallocation oracles are rebased with explicit caller continuation replacements; fresh outer-frame and forward DWORD snapshot equations connect their complete memory states",
            premises=[
                "Disjoint mapped old and new blocks, object and complete ancestor stack; valid preceding metadata for large old storage",
                "Stable heap and supplied runtime import targets; normal stdcall success responses preserve all modeled memory and nonvolatile registers",
                "Entry direction flag is clear; zero byte copy may use null pointers because it performs no payload access",
            ],
            not_claimed=[
                "Actual allocation or free API execution, failure or retry integration, larger payload copies or arbitrary aliasing",
                "Complete vector resize equivalence beyond this sampled domain or whole-program accounting promotion",
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
        "sealed integrated resize differs",
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
        "exact integrated resize differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
