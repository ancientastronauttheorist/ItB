"""Bounded native growth: old size four to capacity six, SIMD copy32.

Allocation and free responses are supplied; no class, Lua, factory or ownership
behavior is claimed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import capstone

from src.observatory import native_small_vector_resize_conformance as small
from src.observatory import native_simd_vector_resize_conformance as resize
from src.observatory import native_lua_vector_growth_semantics as growth
from src.observatory import native_short_simd_copy_semantics as simd_contract
from src.observatory import native_short_simd_copy_conformance as simd

allocator, deallocator, owner = small.allocator, small.deallocator, small.owner
BASE, EXE_SHA256 = small.BASE, small.EXE_SHA256
_load_executable, _point, _source_identity = (
    small._load_executable,
    small._point,
    small._source_identity,
)
_canonical_bytes, _canonical_sha256 = small._canonical_bytes, small._canonical_sha256
_validate_json_tree, _assert_publication_safe = (
    small._validate_json_tree,
    small._assert_publication_safe,
)
_add_flags = small._add_flags
ANALYSIS_KIND = "pe_native_simd_vector_growth_conformance"
SEALED_SHA256 = "605dbce02a72434228128b45fbf008f05448c12f618af876b1cc27c920527bfb"
SOURCE_PINS = {
    **resize.SOURCE_PINS,
    "simd_resize": (resize.ANALYSIS_KIND, resize.SEALED_SHA256),
    "growth": (growth.ANALYSIS_KIND, growth.SEALED_SHA256),
    "small_resize": (small.ANALYSIS_KIND, small.SEALED_SHA256),
    "short_simd_semantics": (simd_contract.ANALYSIS_KIND, simd_contract.SEALED_SHA256),
    "short_simd_conformance": (simd.ANALYSIS_KIND, simd.SEALED_SHA256),
}
STACK, DATA = 0x30000000, 0x06000000
NEW, OLD, ERROR, OBJECT, OBJECT_ADDRESS = (
    DATA + 0x2000,
    DATA + 0x3000,
    DATA,
    0x0FFFF000,
    0x0FFFFFD0,
)
RETURN, IMPORT = small.RETURN, small.IMPORT
FEATURE_PAGE, FEATURE = 0x00893000, 0x00893F30
HEAP_GLOBAL, ALLOC_IAT, FREE_IAT, HEAP = (
    small.HEAP_GLOBAL,
    small.ALLOC_IAT,
    small.FREE_IAT,
    small.HEAP,
)
REGISTERS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple(f"xmm{i}" for i in range(8))
BODIES = {
    "growth": (0x2EB620, 0x2EB67E),
    **small.BODIES,
    **{"simd_" + str(i): bounds for i, bounds in enumerate(simd.RANGES)},
}
FIXTURE_KEYS = {
    "registers",
    "xmm",
    "stack",
    "new",
    "old",
    "object",
    "error",
    "feature_page",
}


class ConformanceError(RuntimeError):
    pass


def _require(condition, message):
    if not condition:
        raise ConformanceError(message)


def vectors():
    return [
        dict(profile=profile, vector_alignment=a, stack_alignment=s)
        for profile in (0, 1)
        for a in (0, 7, 31)
        for s in (0, 1, 7, 15)
    ]


def geometry(vector):
    _require(
        type(vector) is dict
        and set(vector) == {"profile", "vector_alignment", "stack_alignment"},
        "invalid SIMD growth vector schema",
    )
    _require(
        all(type(value) is int for value in vector.values()) and vector in vectors(),
        "outside fixed SIMD growth geometry",
    )
    a = vector["vector_alignment"]
    return dict(
        old_begin=OLD + 0x800 + a,
        old_end=OLD + 0x800 + a + 32,
        old_capacity=OLD + 0x800 + a + 32,
        new_begin=NEW + 0x800 + a,
        new_end=NEW + 0x800 + a + 32,
        new_capacity=NEW + 0x800 + a + 48,
        copy_bytes=32,
        request=48,
        old_size=4,
        requested=6,
    )


def frame_join(s):
    _require(
        type(s) is int and STACK + 96 <= s <= STACK + 0x2000 - 8,
        "SIMD growth frame outside fixed mapping",
    )
    return dict(
        growth=s,
        resize_entry=s - 20,
        copy_entry=s - 56,
        heap_allocation_entry=s - 96,
        heap_free_entry=s - 88,
        protected_start=s - 96,
        protected_end=s + 8,
        returned=s + 8,
    )


def _fixture(vector):
    g = geometry(vector)
    profile = vector["profile"]
    registers = {
        r: (0xF1234567 - i * 0x1020307 + profile * 0x13579) & 0xFFFFFFFF
        for i, r in enumerate(REGISTERS)
    }
    registers.update(esp=STACK + 0x1000 + vector["stack_alignment"], ecx=OBJECT_ADDRESS)
    xmm = {
        name: int.from_bytes(
            bytes((i * 17 + j * 37 + profile * 71) & 255 for j in range(16)), "little"
        )
        for i, name in enumerate(XMM)
    }
    pages = {
        name: bytearray(
            bytes((i * multiplier + (i >> 5) + 0xA7) & 255 for i in range(size))
        )
        for name, multiplier, size in (
            ("stack", 43, 0x2000),
            ("new", 29, 4096),
            ("old", 31, 4096),
            ("object", 11, 4096),
            ("error", 53, 4096),
        )
    }
    s = registers["esp"]
    for address, value in ((s, RETURN), (s + 4, 1)):
        at = address - STACK
        pages["stack"][at : at + 4] = value.to_bytes(4, "little")
    for offset, value in (
        (0, g["old_begin"]),
        (4, g["old_end"]),
        (8, g["old_capacity"]),
    ):
        at = OBJECT_ADDRESS - OBJECT + offset
        pages["object"][at : at + 4] = value.to_bytes(4, "little")
    feature = bytearray(b"\x93" * 4096)
    feature[0xF28:0xF2C] = (0x12345678 if not profile else 0xFFFFFFFF).to_bytes(
        4, "little"
    )
    return dict(
        registers=registers,
        xmm=xmm,
        feature_page=bytes(feature),
        **{name: bytes(buffer) for name, buffer in pages.items()},
    )


def _resize_memory_law(
    vector, incoming, initial_xmm, stack, new, old, objects, error, feature
):
    """Independent owner events around the three sealed primitive helpers."""
    t = incoming["esp"]
    obj = OBJECT_ADDRESS
    g = geometry(vector)
    stack = bytearray(stack)
    objects = bytearray(objects)
    events = []

    def put(address, value):
        events.append(dict(access="write", address=address, width=4, value=value))
        target, base = (
            (objects, OBJECT) if OBJECT <= address < OBJECT + 4096 else (stack, STACK)
        )
        target[address - base : address - base + 4] = value.to_bytes(4, "little")

    def read(address, value):
        events.append(dict(access="read", address=address, width=4, value=value))

    put(t - 4, incoming["ebp"])
    put(t - 8, obj)
    read(t + 4, 6)
    for address, value in (
        (t - 12, incoming["ebx"]),
        (t - 16, obj),
        (t - 20, 4),
        (t - 24, 6),
        (t - 8, 6),
        (t - 28, BASE + 0x2EB695),
    ):
        put(address, value)
    alloc = allocator._expected(
        dict(count=6, pointer=g["new_begin"]),
        dict(incoming, ebp=t - 4, esp=t - 28, eax=6, esi=obj),
        stack,
        new,
        stack_base=STACK,
        data_base=NEW,
    )
    alloc["events"][-1]["value"] = BASE + 0x2EB695
    events.extend(alloc["events"])
    stack = bytearray(alloc["stack"])
    read(obj, g["old_begin"])
    read(obj + 4, g["old_end"])
    for address, value in (
        (t - 24, 32),
        (t - 28, g["old_begin"]),
        (t - 32, g["new_begin"]),
        (t - 36, BASE + 0x2EB6A6),
    ):
        put(address, value)
    copy_regs = dict(
        alloc["registers"],
        eax=g["new_begin"],
        edi=g["new_begin"],
        ecx=32,
        edx=g["old_begin"],
        esi=obj,
        esp=t - 36,
    )
    copied = simd._expected(
        dict(
            length=32,
            source_offset=0x1800 + vector["vector_alignment"],
            destination_offset=0x800 + vector["vector_alignment"],
            alignment=vector["stack_alignment"],
            df=0,
            feature_word=0x93939393,
        ),
        copy_regs,
        initial_xmm,
        bytes(stack),
        bytes(new + old),
        stack_base=STACK,
        payload_base=NEW,
        return_address=BASE + 0x2EB6A6,
        feature_page=feature,
    )
    events.extend(copied["events"])
    stack = bytearray(copied["stack"])
    read(obj, g["old_begin"])
    read(obj + 4, g["old_end"])
    read(obj + 8, g["old_capacity"])
    for address, value in (
        (t - 24, 8),
        (t - 28, 4),
        (t - 32, g["old_begin"]),
        (t - 36, BASE + 0x2EB6C8),
    ):
        put(address, value)
    freed = deallocator._expected(
        dict(
            pointer=g["old_begin"],
            count=4,
            stride=8,
            metadata=None,
            responses=[dict(kind="heap_free", eax=1)],
            heap=HEAP,
        ),
        dict(copied["registers"], eax=4, ebx=4, ecx=g["old_begin"], esp=t - 36),
        stack,
        error,
        stack_base=STACK,
    )
    freed["events"][-1]["value"] = BASE + 0x2EB6C8
    events.extend(freed["events"])
    stack = bytearray(freed["stack"])
    read(t - 8, 6)
    for address, value in (
        (obj + 8, g["new_capacity"]),
        (obj + 4, g["new_end"]),
        (obj, g["new_begin"]),
    ):
        put(address, value)
    for address, value in (
        (t - 20, 4),
        (t - 16, obj),
        (t - 12, incoming["ebx"]),
        (t - 4, incoming["ebp"]),
        (t, BASE + 0x2EB66E),
    ):
        read(address, value)
    return bytes(stack), events


def _expected(
    vector,
    initial,
    initial_xmm,
    original_stack,
    original_new,
    original_old,
    original_object,
    original_error,
    feature_page,
    *,
    return_address=RETURN,
):
    g = geometry(vector)
    _require(
        type(return_address) is int and 0 < return_address <= 0xFFFFFFFF,
        "invalid growth return address",
    )
    _require(
        type(initial) is dict
        and set(initial) == set(REGISTERS)
        and all(type(v) is int and 0 <= v <= 0xFFFFFFFF for v in initial.values()),
        "invalid growth GPR schema or word",
    )
    _require(
        type(initial_xmm) is dict
        and set(initial_xmm) == set(XMM)
        and all(type(v) is int and 0 <= v < 2**128 for v in initial_xmm.values()),
        "invalid growth XMM schema or word",
    )
    for name, buffer, size in (
        ("stack", original_stack, 8192),
        ("new", original_new, 4096),
        ("old", original_old, 4096),
        ("object", original_object, 4096),
        ("error", original_error, 4096),
        ("feature", feature_page, 4096),
    ):
        _require(
            type(buffer) is bytes and len(buffer) == size,
            "invalid growth " + name + " buffer",
        )
    s, obj = initial["esp"], initial["ecx"]
    frame_join(s)
    _require(obj == OBJECT_ADDRESS, "growth object identity differs")
    _require(
        int.from_bytes(original_stack[s - STACK : s - STACK + 4], "little")
        == return_address,
        "installed growth return differs",
    )
    _require(
        [
            int.from_bytes(original_object[0xFD0 + i : 0xFD4 + i], "little")
            for i in (0, 4, 8)
        ]
        == [g["old_begin"], g["old_end"], g["old_capacity"]],
        "installed growth header differs",
    )
    _require(
        int.from_bytes(feature_page[0xF30:0xF34], "little") == 0x93939393,
        "retained growth feature differs",
    )
    stack = bytearray(original_stack)
    events = []

    def event(access, address, value):
        events.append(dict(access=access, address=address, width=4, value=value))
        if access == "write":
            at = address - STACK
            stack[at : at + 4] = value.to_bytes(4, "little")

    w = lambda a, v: event("write", a, v)
    r = lambda a, v: event("read", a, v)
    w(s - 4, initial["esi"])
    w(s - 8, initial["edi"])
    r(obj + 8, g["old_capacity"])
    r(obj + 4, g["old_end"])
    r(obj, g["old_begin"])
    w(s - 12, initial["ebx"])
    w(s - 16, 6)
    w(s - 20, BASE + 0x2EB66E)
    incoming = dict(
        initial, eax=6, ebx=0x1FFFFFFD, ecx=obj, edx=6, esi=obj, edi=4, esp=s - 20
    )
    child = resize._expected(
        vector,
        incoming,
        initial_xmm,
        bytes(stack),
        original_new,
        original_old,
        original_object,
        original_error,
        feature_page,
        return_address=BASE + 0x2EB66E,
    )
    predicted_stack, predicted_events = _resize_memory_law(
        vector,
        incoming,
        initial_xmm,
        bytes(stack),
        original_new,
        original_old,
        original_object,
        original_error,
        feature_page,
    )
    snapshot = original_old[
        0x800 + vector["vector_alignment"] : 0x820 + vector["vector_alignment"]
    ]
    predicted_new = bytearray(original_new)
    at = 0x800 + vector["vector_alignment"]
    predicted_new[at : at + 32] = snapshot
    predicted_object = bytearray(original_object)
    for offset, value in (
        (0, g["new_begin"]),
        (4, g["new_end"]),
        (8, g["new_capacity"]),
    ):
        at = OBJECT_ADDRESS - OBJECT + offset
        predicted_object[at : at + 4] = value.to_bytes(4, "little")
    _require(
        type(child) is dict
        and set(child)
        == {
            "geometry",
            "registers",
            "xmm",
            "flags",
            "flag_mask",
            "df",
            "events",
            "stack",
            "new",
            "old",
            "object",
            "error",
            "feature_page",
            "endpoint",
            "copy_entry",
            "allocation_request",
            "free_request",
        }
        and child["geometry"] == g
        and child["copy_entry"]
        == dict(
            incoming,
            eax=g["new_begin"],
            ecx=32,
            edx=g["old_begin"],
            esi=obj,
            edi=g["new_begin"],
            ebp=s - 24,
            esp=s - 56,
        )
        and child["allocation_request"]
        == dict(
            continuation=BASE + 0x389463,
            handle=HEAP,
            flags=0,
            bytes=48,
        )
        and child["free_request"]
        == dict(
            continuation=BASE + 0x389172,
            handle=HEAP,
            flags=0,
            pointer=g["old_begin"],
        )
        and child["registers"]
        == dict(incoming, eax=g["new_end"], ecx=0xA0000001, edx=0xB0000001, esp=s - 12)
        and child["stack"] == predicted_stack
        and child["events"] == predicted_events
        and child["endpoint"] == BASE + 0x2EB66E
        and child["events"][-1]
        == dict(access="read", address=s - 20, width=4, value=BASE + 0x2EB66E)
        and child["new"] == bytes(predicted_new)
        and child["old"] == original_old
        and child["object"] == bytes(predicted_object)
        and child["error"] == original_error
        and child["feature_page"] == feature_page
        and child["flags"] == _add_flags(s - 52, 12)
        and child["flag_mask"] == 0x8D5
        and child["df"] == 0
        and child["xmm"]
        == dict(
            initial_xmm,
            xmm0=int.from_bytes(snapshot[:16], "little"),
            xmm1=int.from_bytes(snapshot[16:], "little"),
        ),
        "SIMD growth resize join differs",
    )
    events.extend(child["events"])
    stack = bytearray(child["stack"])
    for address, value in (
        (s - 12, initial["ebx"]),
        (s - 8, initial["edi"]),
        (s - 4, initial["esi"]),
        (s, return_address),
    ):
        r(address, value)
    regs = dict(
        child["registers"],
        ebx=initial["ebx"],
        esi=initial["esi"],
        edi=initial["edi"],
        esp=s + 8,
    )
    return dict(
        child,
        registers=regs,
        events=events,
        stack=bytes(stack),
        endpoint=return_address,
        resize_entry=incoming,
    )


def _packet(vector, fixture, *, return_address=RETURN):
    _require(
        type(fixture) is dict and set(fixture) == FIXTURE_KEYS,
        "invalid resize fixture schema",
    )
    try:
        return _expected(
            vector,
            fixture["registers"],
            fixture["xmm"],
            fixture["stack"],
            fixture["new"],
            fixture["old"],
            fixture["object"],
            fixture["error"],
            fixture["feature_page"],
            return_address=return_address,
        )
    except (
        resize.ConformanceError,
        allocator.ConformanceError,
        deallocator.ConformanceError,
        simd.ConformanceError,
    ) as exc:
        raise ConformanceError(str(exc)) from exc


def _load_code(data, image, sources):
    # The small-resize witness loader is currently inline in its builder.
    source_bodies = [
        sources["growth"]["body"],
        sources["owner"]["body"],
        *sources["allocation_conformance"]["bodies"].values(),
        sources["deallocation_composition"]["guard_body"],
        *sources["deallocation_composition"]["free_bodies"],
        *sources["small_copy"]["body"]["ranges"],
        *sources["short_simd_semantics"]["body"]["ranges"],
    ]
    witnesses = {}
    for body in source_bodies:
        for point in body["points"]:
            _require(
                point["rva"] not in witnesses or witnesses[point["rva"]] == point,
                "SIMD growth witness conflict",
            )
            witnesses[point["rva"]] = point
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    codes, points, covered = {}, {}, {}
    for name, (start, end) in BODIES.items():
        at = image.rva_to_file_offset(start)
        body = data[at : at + end - start]
        rows = [_point(row) for row in decoder.disasm(body, BASE + start)]
        _require(
            sum(row["size"] for row in rows) == end - start
            and all(witnesses.get(row["rva"]) == row for row in rows),
            "exact SIMD growth witness differs",
        )
        for offset, value in enumerate(body):
            _require(
                start + offset not in covered or covered[start + offset] == value,
                "SIMD growth byte conflict",
            )
            covered[start + offset] = value
        codes[name], points[name] = body, rows
    return codes, points


CONTROLS = {
    "ancestor": "SIMD growth ancestor memory differs",
    "payload": "SIMD growth payload differs",
    "xmm": "SIMD growth XMM differs",
    "request": "SIMD growth allocation handoff differs",
    "free": "SIMD growth free handoff differs",
}


def _run_case(codes, points, vector, negative=None, *, fixture=None):
    installed = _fixture(vector) if fixture is None else fixture
    expected = _packet(vector, installed)
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    g, s = expected["geometry"], installed["registers"]["esp"]
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    code_pages = {
        BASE + (address & ~4095)
        for start, end in BODIES.values()
        for address in range(start, end)
    }
    globals_page, iat_page = HEAP_GLOBAL & ~4095, ALLOC_IAT & ~4095
    globals_bytes, iat_bytes = bytearray(4096), bytearray(4096)
    globals_bytes[HEAP_GLOBAL & 4095 : (HEAP_GLOBAL & 4095) + 4] = HEAP.to_bytes(
        4, "little"
    )
    for address in (ALLOC_IAT, FREE_IAT):
        iat_bytes[address & 4095 : (address & 4095) + 4] = IMPORT.to_bytes(4, "little")
    buffers = {
        STACK: installed["stack"],
        NEW: installed["new"],
        OLD: installed["old"],
        OBJECT: installed["object"],
        ERROR: installed["error"],
        FEATURE_PAGE: installed["feature_page"],
        globals_page: bytes(globals_bytes),
        iat_page: bytes(iat_bytes),
    }
    spans = [(base, base + len(buffer)) for base, buffer in buffers.items()]
    _require(
        len(buffers) == 8
        and all(
            b <= c or d <= a
            for i, (a, b) in enumerate(spans)
            for c, d in spans[i + 1 :]
        ),
        "SIMD growth mappings overlap",
    )
    _require(
        all(
            b <= p or p + 4096 <= a
            for a, b in spans
            for p in code_pages | {RETURN, IMPORT}
        ),
        "SIMD growth runtime mapping overlap",
    )
    for page in code_pages | {RETURN, IMPORT}:
        machine.mem_map(page, 4096)
        machine.mem_write(page, b"\xcc" * 4096)
    for base, buffer in buffers.items():
        machine.mem_map(base, len(buffer))
        machine.mem_write(base, buffer)
    for name, (start, end) in BODIES.items():
        machine.mem_write(BASE + start, codes[name])
    ids = {name: getattr(x, "UC_X86_REG_" + name.upper()) for name in REGISTERS}
    xmm_ids = {name: getattr(x, "UC_X86_REG_" + name.upper()) for name in XMM}
    for name, value in installed["registers"].items():
        machine.reg_write(ids[name], value)
    for name, value in installed["xmm"].items():
        machine.reg_write(xmm_ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(point["rva"], 16) for rows in points.values() for point in rows}
    events, visited, summaries, resume = [], [], [], None

    def on_code(m, address, size, user):
        nonlocal resume
        if address == IMPORT:
            sp = m.reg_read(ids["esp"])
            words = [
                int.from_bytes(m.mem_read(sp + 4 * i, 4), "little") for i in range(4)
            ]
            continuation = words[0]
            if continuation == BASE + 0x389463:
                role, result, handoff = (
                    "allocate",
                    g["new_begin"],
                    (s - 96, [HEAP, 0, 48]),
                )
                if negative == "request":
                    m.mem_write(sp + 12, (words[3] ^ 1).to_bytes(4, "little"))
                    words[3] ^= 1
            elif continuation == BASE + 0x389172:
                role, result, handoff = "free", 1, (s - 88, [HEAP, 0, g["old_begin"]])
                if negative == "free":
                    m.mem_write(sp + 12, (words[3] ^ 1).to_bytes(4, "little"))
                    words[3] ^= 1
            else:
                raise ConformanceError("unexpected SIMD growth imported continuation")
            _require(
                sp == handoff[0] and words[1:] == handoff[1],
                (
                    "SIMD growth allocation handoff differs"
                    if role == "allocate"
                    else "SIMD growth free handoff differs"
                ),
            )
            _require(
                role not in [item["role"] for item in summaries],
                "repeated SIMD growth API",
            )
            if role == "allocate":
                _require(not summaries, "SIMD growth allocation order differs")
            else:
                _require(
                    [item["role"] for item in summaries] == ["allocate"],
                    "SIMD growth free order differs",
                )
            for name, value in (
                ("eax", result),
                ("ecx", 0xA0000001),
                ("edx", 0xB0000001),
                ("esp", sp + 16),
            ):
                m.reg_write(ids[name], value)
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            if negative == "ancestor" and role == "allocate":
                m.mem_write(s + 4, (7).to_bytes(4, "little"))
            if negative == "payload" and role == "free":
                m.mem_write(
                    g["new_begin"], bytes([m.mem_read(g["new_begin"], 1)[0] ^ 1])
                )
            summaries.append(dict(role=role, entry_esp=sp, continuation=continuation))
            resume = continuation
            m.emu_stop()
            return
        if address == BASE + 0x2EB680:
            _require(
                {name: m.reg_read(identity) for name, identity in ids.items()}
                == expected["resize_entry"],
                "SIMD growth resize entry differs",
            )
        if address == BASE + simd.START:
            _require(
                {name: m.reg_read(identity) for name, identity in ids.items()}
                == expected["copy_entry"],
                "SIMD growth copy entry differs",
            )
        if negative == "xmm" and address == BASE + 0x2EB6E2:
            m.reg_write(xmm_ids["xmm7"], m.reg_read(xmm_ids["xmm7"]) ^ 1)
        pc = address - BASE
        _require(pc in allowed, "SIMD growth escaped selected code")
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, width, value, user):
        _require(width in (4, 8, 16), "unexpected SIMD growth access width")
        events.append(
            dict(
                access="write" if access == uc.UC_MEM_WRITE else "read",
                address=address,
                width=width,
                value=(
                    value & ((1 << (8 * width)) - 1)
                    if access == uc.UC_MEM_WRITE
                    else int.from_bytes(m.mem_read(address, width), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    start = BASE + 0x2EB620
    for _ in range(3):
        resume = None
        machine.emu_start(start, RETURN, count=1500)
        if resume is None:
            break
        start = resume
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == RETURN
        and [item["role"] for item in summaries] == ["allocate", "free"],
        "SIMD growth endpoint or API sequence differs",
    )
    actual = {name: machine.reg_read(identity) for name, identity in ids.items()}
    xmm = {name: machine.reg_read(identity) for name, identity in xmm_ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        actual == expected["registers"]
        and flags & expected["flag_mask"] == expected["flags"] & expected["flag_mask"]
        and not flags & 0x400,
        "SIMD growth registers flags or DF differ",
    )
    _require(xmm == expected["xmm"], "SIMD growth XMM differs")
    _require(events == expected["events"], "SIMD growth ordered events differ")
    _require(
        bytes(machine.mem_read(STACK, 0x2000)) == expected["stack"],
        "SIMD growth ancestor memory differs",
    )
    _require(
        all(
            bytes(machine.mem_read(base, 4096)) == expected[name]
            for base, name in (
                (NEW, "new"),
                (OLD, "old"),
                (OBJECT, "object"),
                (ERROR, "error"),
            )
        ),
        "SIMD growth payload differs",
    )
    _require(
        bytes(machine.mem_read(FEATURE_PAGE, 4096)) == expected["feature_page"]
        and bytes(machine.mem_read(globals_page, 4096)) == bytes(globals_bytes)
        and bytes(machine.mem_read(iat_page, 4096)) == bytes(iat_bytes),
        "SIMD growth features globals or imports differ",
    )
    return dict(
        inputs=dict(vector),
        registers=actual,
        xmm=xmm,
        flags=flags & expected["flag_mask"],
        flag_mask=expected["flag_mask"],
        df=(flags >> 10) & 1,
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        summaries=summaries,
        **{
            name + "_sha256": hashlib.sha256(expected[name]).hexdigest()
            for name in ("stack", "new", "old", "object", "error", "feature_page")
        },
    )


def _preflight(sources):
    _require(
        type(sources) is dict and set(sources) == set(SOURCE_PINS),
        "SIMD growth source partition differs",
    )
    try:
        return {
            key: _source_identity(sources[key], *pin, key)
            for key, pin in SOURCE_PINS.items()
        }
    except Exception as exc:
        raise ConformanceError(str(exc)) from exc


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256
        and image.image_base == BASE
        and capstone.__version__ == "5.0.7",
        "SIMD growth executable differs",
    )
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, vector) for vector in vectors()]
    controls = []
    for kind, message in CONTROLS.items():
        try:
            _run_case(codes, points, vectors()[-1], kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "SIMD growth control failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("SIMD growth mutation survived")
    covered = {
        start + i
        for name, (start, end) in BODIES.items()
        for i in range(len(codes[name]))
    }
    unique_points = {point["rva"]: point for rows in points.values() for point in rows}
    union = sorted(
        {rva for observation in observations for rva in observation["trace_rvas"]}
    )
    _require(
        set(union) <= set(unique_points)
        and all(point["rva"] in union for point in points["owner"])
        and all(
            point["rva"] in union
            for point in points["growth"]
            if int(point["rva"], 16) < 0x2EB674
        )
        and {"0x0036e5b1", "0x0036ea60", "0x0036ea64", "0x0036ea69", "0x0036ea6d"}
        <= set(union),
        "SIMD growth coverage differs",
    )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["owner"]["build_identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{start:08x}",
                    end_rva=f"0x{end:08x}",
                    sha256=hashlib.sha256(codes[name]).hexdigest(),
                )
                for name, (start, end) in BODIES.items()
            ],
            points=sorted(unique_points.values(), key=lambda row: int(row["rva"], 16)),
        ),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=union,
        negative_controls=controls,
        summary=dict(
            cases=24,
            loaded_bytes=len(covered),
            loaded_sites=len(unique_points),
            executed_sites=len(union),
            allocation_api_summaries=24,
            free_api_summaries=24,
            copied_bytes=768,
            allocated_bytes=1152,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Fixed full size four growth computes capacity six and joins native resize allocation exact32 SIMD copy and free",
            premises=[
                "Disjoint fixed complete buffers and installed owner arguments",
                "DF clear and retained feature0x93939393",
                "Only successful supplied heap responses; XMM preserved across API responses",
            ],
            not_claimed=[
                "Class append Lua factory fifth callback ownership allocator reuse failures or global accounting"
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "executable changed during SIMD growth build",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    _validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        SEALED_SHA256 != "PENDING"
        and _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors(),
        "sealed SIMD growth differs",
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
        "exact SIMD growth differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


encode_conformance = small.encode_conformance
