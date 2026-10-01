"""Bounded native resize ingredient: old size four, request six, SIMD copy32.

Allocation and free responses are supplied; no class, Lua, factory or ownership
behavior is claimed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import capstone

from src.observatory import native_small_vector_resize_conformance as small
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
ANALYSIS_KIND = "pe_native_simd_vector_resize_conformance"
SEALED_SHA256 = "553ca197fff9214a2dba573c44174d3407acc804dcda6b9cf73352a0964f05c7"
SOURCE_PINS = {
    **small.SOURCE_PINS,
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
        "invalid SIMD resize vector schema",
    )
    _require(
        all(type(value) is int for value in vector.values()) and vector in vectors(),
        "outside fixed SIMD resize geometry",
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
        type(s) is int and STACK + 76 <= s <= STACK + 0x2000 - 8,
        "SIMD resize frame outside fixed mapping",
    )
    return small.frame_join(s)


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
    for address, value in ((s, RETURN), (s + 4, 6)):
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
        "invalid resize return address",
    )
    _require(
        type(initial) is dict and set(initial) == set(REGISTERS),
        "invalid resize GPR schema",
    )
    _require(
        all(
            type(value) is int and 0 <= value <= 0xFFFFFFFF
            for value in initial.values()
        ),
        "invalid resize GPR word",
    )
    _require(
        type(initial_xmm) is dict and set(initial_xmm) == set(XMM),
        "invalid resize XMM schema",
    )
    _require(
        all(
            type(value) is int and 0 <= value < 2**128 for value in initial_xmm.values()
        ),
        "invalid resize XMM word",
    )
    for name, buffer, size in (
        ("stack", original_stack, 0x2000),
        ("new", original_new, 4096),
        ("old", original_old, 4096),
        ("object", original_object, 4096),
        ("error", original_error, 4096),
        ("feature", feature_page, 4096),
    ):
        _require(
            type(buffer) is bytes and len(buffer) == size,
            "invalid resize " + name + " buffer",
        )
    s, obj = initial["esp"], initial["ecx"]
    frame_join(s)
    _require(obj == OBJECT_ADDRESS, "resize object identity differs")
    _require(
        int.from_bytes(original_stack[s - STACK : s - STACK + 4], "little")
        == return_address
        and int.from_bytes(original_stack[s - STACK + 4 : s - STACK + 8], "little")
        == 6,
        "installed resize arguments differ",
    )
    _require(
        [
            int.from_bytes(
                original_object[obj - OBJECT + i : obj - OBJECT + i + 4], "little"
            )
            for i in (0, 4, 8)
        ]
        == [g["old_begin"], g["old_end"], g["old_capacity"]],
        "installed resize header differs",
    )
    _require(
        int.from_bytes(feature_page[0xF30:0xF34], "little") == 0x93939393,
        "retained resize feature differs",
    )
    stack, new, old, objects = map(
        bytearray, (original_stack, original_new, original_old, original_object)
    )
    events = []

    def event(access, address, value, width=4):
        events.append(dict(access=access, address=address, width=width, value=value))
        if access == "write":
            target, base = (
                (stack, STACK)
                if STACK <= address < STACK + len(stack)
                else (objects, OBJECT)
            )
            _require(
                base <= address and address + width <= base + len(target),
                "owner write outside mappings",
            )
            target[address - base : address - base + width] = value.to_bytes(
                width, "little"
            )

    w = lambda address, value: event("write", address, value)
    r = lambda address, value: event("read", address, value)
    for address, value in ((s - 4, initial["ebp"]), (s - 8, obj)):
        w(address, value)
    r(s + 4, 6)
    for address, value in (
        (s - 12, initial["ebx"]),
        (s - 16, initial["esi"]),
        (s - 20, initial["edi"]),
        (s - 24, 6),
        (s - 8, 6),
        (s - 28, BASE + 0x2EB695),
    ):
        w(address, value)
    regs = dict(initial, ebp=s - 4, esp=s - 28, eax=6, esi=obj)
    allocated = allocator._expected(
        dict(count=6, pointer=g["new_begin"]),
        regs,
        stack,
        new,
        stack_base=STACK,
        data_base=NEW,
    )
    _require(
        allocated["events"][-1]
        == dict(access="read", address=s - 28, width=4, value=allocator.RETURN),
        "allocation continuation differs",
    )
    allocated["events"][-1] = dict(
        access="read", address=s - 28, width=4, value=BASE + 0x2EB695
    )
    events.extend(allocated["events"])
    stack, new, regs = (
        bytearray(allocated["stack"]),
        bytearray(allocated["payload"]),
        dict(allocated["registers"]),
    )
    r(obj, g["old_begin"])
    r(obj + 4, g["old_end"])
    for address, value in (
        (s - 24, 32),
        (s - 28, g["old_begin"]),
        (s - 32, g["new_begin"]),
        (s - 36, BASE + 0x2EB6A6),
    ):
        w(address, value)
    regs.update(
        eax=g["new_begin"],
        edi=g["new_begin"],
        esi=obj,
        ecx=32,
        edx=g["old_begin"],
        esp=s - 36,
    )
    copy_entry = dict(regs)
    copy_vector = dict(
        length=32,
        source_offset=0x1800 + vector["vector_alignment"],
        destination_offset=0x800 + vector["vector_alignment"],
        alignment=vector["stack_alignment"],
        df=0,
        feature_word=0x93939393,
    )
    copied = simd._expected(
        copy_vector,
        regs,
        initial_xmm,
        bytes(stack),
        bytes(new + old),
        stack_base=STACK,
        payload_base=NEW,
        return_address=BASE + 0x2EB6A6,
        feature_page=feature_page,
    )
    snapshot = original_old[
        0x800 + vector["vector_alignment"] : 0x820 + vector["vector_alignment"]
    ]
    copy_payload = bytearray(new + old)
    at = 0x800 + vector["vector_alignment"]
    copy_payload[at : at + 32] = snapshot
    copy_stack = bytearray(stack)
    for address, value in ((s - 40, regs["edi"]), (s - 44, regs["esi"])):
        copy_stack[address - STACK : address - STACK + 4] = value.to_bytes(4, "little")
    _require(
        copied["registers"] == dict(regs, eax=g["new_begin"], ecx=0, edx=0, esp=s - 32)
        and copied["feature_page"] == feature_page
        and copied["df"] == 0
        and copied["flags"] == 0x44
        and copied["flag_mask"] == 0x8C5
        and copied["endpoint"] == BASE + 0x2EB6A6
        and copied["stack"] == bytes(copy_stack)
        and copied["payload"] == bytes(copy_payload)
        and copied["xmm"]
        == dict(
            initial_xmm,
            xmm0=int.from_bytes(snapshot[:16], "little"),
            xmm1=int.from_bytes(snapshot[16:], "little"),
        ),
        "SIMD copy join differs",
    )
    _require(copied["payload"][0x1000:] == original_old, "SIMD copy changed old source")
    events.extend(copied["events"])
    stack, new, old = (
        bytearray(copied["stack"]),
        bytearray(copied["payload"][:4096]),
        bytearray(copied["payload"][4096:]),
    )
    regs, xmm = dict(copied["registers"]), dict(copied["xmm"])
    r(obj, g["old_begin"])
    r(obj + 4, g["old_end"])
    regs.update(ecx=g["old_begin"], ebx=4, esp=s - 20)
    r(obj + 8, g["old_capacity"])
    for address, value in (
        (s - 24, 8),
        (s - 28, 4),
        (s - 32, g["old_begin"]),
        (s - 36, BASE + 0x2EB6C8),
    ):
        w(address, value)
    regs.update(eax=4, esp=s - 36)
    freed = deallocator._expected(
        dict(
            pointer=g["old_begin"],
            count=4,
            stride=8,
            metadata=None,
            responses=[dict(kind="heap_free", eax=1)],
            heap=HEAP,
        ),
        regs,
        stack,
        original_error,
        stack_base=STACK,
    )
    _require(
        freed["events"][-1]
        == dict(access="read", address=s - 36, width=4, value=deallocator.RETURN),
        "free continuation differs",
    )
    freed["events"][-1] = dict(
        access="read", address=s - 36, width=4, value=BASE + 0x2EB6C8
    )
    _require(freed["error"] == original_error, "successful free changed error storage")
    events.extend(freed["events"])
    stack, regs = bytearray(freed["stack"]), dict(freed["registers"])
    r(s - 8, 6)
    for address, value in (
        (obj + 8, g["new_capacity"]),
        (obj + 4, g["new_end"]),
        (obj, g["new_begin"]),
    ):
        w(address, value)
    for address, value in (
        (s - 20, initial["edi"]),
        (s - 16, initial["esi"]),
        (s - 12, initial["ebx"]),
        (s - 4, initial["ebp"]),
        (s, return_address),
    ):
        r(address, value)
    regs.update(
        eax=g["new_end"],
        ebx=initial["ebx"],
        esi=initial["esi"],
        edi=initial["edi"],
        ebp=initial["ebp"],
        esp=s + 8,
    )
    _require(
        new[0x800 + vector["vector_alignment"] : 0x820 + vector["vector_alignment"]]
        == original_old[
            0x800 + vector["vector_alignment"] : 0x820 + vector["vector_alignment"]
        ],
        "resize snapshot join differs",
    )
    return dict(
        geometry=g,
        registers=regs,
        xmm=xmm,
        flags=_add_flags(s - 32, 12),
        flag_mask=0x8D5,
        df=0,
        events=events,
        stack=bytes(stack),
        new=bytes(new),
        old=bytes(old),
        object=bytes(objects),
        error=original_error,
        feature_page=feature_page,
        endpoint=return_address,
        copy_entry=copy_entry,
        allocation_request=dict(
            continuation=BASE + 0x389463, handle=HEAP, flags=0, bytes=48
        ),
        free_request=dict(
            continuation=BASE + 0x389172, handle=HEAP, flags=0, pointer=g["old_begin"]
        ),
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
        allocator.ConformanceError,
        deallocator.ConformanceError,
        simd.ConformanceError,
    ) as exc:
        raise ConformanceError(str(exc)) from exc


def _load_code(data, image, sources):
    # The small-resize witness loader is currently inline in its builder.
    source_bodies = [
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
                "SIMD resize witness conflict",
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
            "exact SIMD resize witness differs",
        )
        for offset, value in enumerate(body):
            _require(
                start + offset not in covered or covered[start + offset] == value,
                "SIMD resize byte conflict",
            )
            covered[start + offset] = value
        codes[name], points[name] = body, rows
    return codes, points


CONTROLS = {
    "ancestor": "SIMD resize ancestor memory differs",
    "payload": "SIMD resize payload differs",
    "xmm": "SIMD resize XMM differs",
    "request": "SIMD resize allocation handoff differs",
    "free": "SIMD resize free handoff differs",
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
        "SIMD resize mappings overlap",
    )
    _require(
        all(
            b <= p or p + 4096 <= a
            for a, b in spans
            for p in code_pages | {RETURN, IMPORT}
        ),
        "SIMD resize runtime mapping overlap",
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
                    (s - 76, [HEAP, 0, 48]),
                )
                if negative == "request":
                    m.mem_write(sp + 12, (words[3] ^ 1).to_bytes(4, "little"))
                    words[3] ^= 1
            elif continuation == BASE + 0x389172:
                role, result, handoff = "free", 1, (s - 68, [HEAP, 0, g["old_begin"]])
                if negative == "free":
                    m.mem_write(sp + 12, (words[3] ^ 1).to_bytes(4, "little"))
                    words[3] ^= 1
            else:
                raise ConformanceError("unexpected SIMD resize imported continuation")
            _require(
                sp == handoff[0] and words[1:] == handoff[1],
                (
                    "SIMD resize allocation handoff differs"
                    if role == "allocate"
                    else "SIMD resize free handoff differs"
                ),
            )
            _require(
                role not in [item["role"] for item in summaries],
                "repeated SIMD resize API",
            )
            if role == "allocate":
                _require(not summaries, "SIMD resize allocation order differs")
            else:
                _require(
                    [item["role"] for item in summaries] == ["allocate"],
                    "SIMD resize free order differs",
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
        if address == BASE + simd.START:
            _require(
                {name: m.reg_read(identity) for name, identity in ids.items()}
                == expected["copy_entry"],
                "SIMD resize copy entry differs",
            )
        if negative == "xmm" and address == BASE + 0x2EB6E2:
            m.reg_write(xmm_ids["xmm7"], m.reg_read(xmm_ids["xmm7"]) ^ 1)
        pc = address - BASE
        _require(pc in allowed, "SIMD resize escaped selected code")
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, width, value, user):
        _require(width in (4, 8, 16), "unexpected SIMD resize access width")
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
    start = BASE + 0x2EB680
    for _ in range(3):
        resume = None
        machine.emu_start(start, RETURN, count=1500)
        if resume is None:
            break
        start = resume
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == RETURN
        and [item["role"] for item in summaries] == ["allocate", "free"],
        "SIMD resize endpoint or API sequence differs",
    )
    actual = {name: machine.reg_read(identity) for name, identity in ids.items()}
    xmm = {name: machine.reg_read(identity) for name, identity in xmm_ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        actual == expected["registers"]
        and flags & expected["flag_mask"] == expected["flags"] & expected["flag_mask"]
        and not flags & 0x400,
        "SIMD resize registers flags or DF differ",
    )
    _require(xmm == expected["xmm"], "SIMD resize XMM differs")
    _require(events == expected["events"], "SIMD resize ordered events differ")
    _require(
        bytes(machine.mem_read(STACK, 0x2000)) == expected["stack"],
        "SIMD resize ancestor memory differs",
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
        "SIMD resize payload differs",
    )
    _require(
        bytes(machine.mem_read(FEATURE_PAGE, 4096)) == expected["feature_page"]
        and bytes(machine.mem_read(globals_page, 4096)) == bytes(globals_bytes)
        and bytes(machine.mem_read(iat_page, 4096)) == bytes(iat_bytes),
        "SIMD resize features globals or imports differ",
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
        "SIMD resize source partition differs",
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
        "SIMD resize executable differs",
    )
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, vector) for vector in vectors()]
    controls = []
    for kind, message in CONTROLS.items():
        try:
            _run_case(codes, points, vectors()[-1], kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "SIMD resize control failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("SIMD resize mutation survived")
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
        and {"0x0036e5b1", "0x0036ea60", "0x0036ea64", "0x0036ea69", "0x0036ea6d"}
        <= set(union),
        "SIMD resize coverage differs",
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
            claim="Fixed ordinary successful resize from size four to capacity six joins native allocation exact32 SIMD copy and native free",
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
        "executable changed during SIMD resize build",
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
        "sealed SIMD resize differs",
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
        "exact SIMD resize differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


encode_conformance = small.encode_conformance
