"""Continuous full capacity6 growth to capacity9 with actual installed resize.

Heap responses are supplied premises. Class callback and heap ownership remain outside this finite proof.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from src.observatory import native_assertion_helper_fill_conformance as common
from src.observatory import native_vector_resize_semantics as owner
from src.observatory import native_lua_vector_growth_semantics as growth
from src.observatory import native_simd_vector_resize6_to9_conformance as resize
from src.observatory import native_simd_vector_resize6_to9_semantics as model
from src.observatory import native_vector_allocation_composition as allocation_contract
from src.observatory import native_vector_allocation_conformance as allocator
from src.observatory import native_vector_deallocation_composition as free_contract
from src.observatory import native_vector_deallocation_conformance_joined as deallocator
from src.observatory import native_installed_simd_copy48_conformance as installed_copy
from src.observatory import native_installed_simd_copy48_semantics as copy_model
from src.observatory.native_lua_vector_allocation_return_conformance import _add_flags

BASE, EXE_SHA256 = common.BASE, common.EXE_SHA256
ANALYSIS_KIND = "pe_native_simd_vector_growth6_to9_conformance"
SEALED_SHA256 = "23eeb7708d498a7f0187b6031835c07d62e6ec99e27326734460808edaceaf25"
# Canonical LF digest of sorted unique point packets from the selected sealed
# owner, allocation, free-composition and generic SIMD scalar source witnesses.
POINTS_SHA256 = "a2288f29ad9c57968d54196062f106d9111f45f28c75c80cf31db1964aa42b44"
SOURCE_PINS = {
    **model.SOURCE_PINS,
    "growth": (growth.ANALYSIS_KIND, growth.SEALED_SHA256),
}

STACK, DATA, ERROR, OBJECT, OBJECT_ADDRESS = (
    0x30000000,
    0x06002000,
    0x06000000,
    0x0FFFF000,
    0x0FFFFFD0,
)
RETURN, IMPORT, HEAP = allocator.RETURN, allocator.IMPORT, allocator.HEAP_HANDLE
HEAP_GLOBAL, ALLOC_IAT, FREE_IAT = (
    allocator.HEAP_GLOBAL,
    allocator.IAT,
    deallocator.FREE_IAT,
)
FEATURE_PAGE, FEATURE = copy_model.FEATURE_PAGE, copy_model.FEATURE
REGISTERS, XMM = copy_model.REGISTERS, copy_model.XMM
BODIES = {
    "growth": (0x2EB620, 0x2EB67E),
    "owner": (0x2EB680, 0x2EB6E5),
    **{"allocate_" + name: bounds for name, bounds in allocator.BODIES.items()},
    **{"free_" + name: bounds for name, bounds in deallocator.BODIES.items()},
    **{"copy_" + str(i): bounds for i, bounds in enumerate(copy_model.RANGES)},
}
FIXTURE_KEYS = {"pages", "registers", "xmm", "return_address", "entry_flags"}
_canonical_bytes, _canonical_sha256 = common._canonical_bytes, common._canonical_sha256
_same_packet = installed_copy._same_packet

# Ordered ordinary paths, copied as source facts rather than inferred from runtime.
ALLOCATION_TRACE = (
    0x8A920,
    0x8A921,
    0x8A923,
    0x8A926,
    0x8A928,
    0x8A932,
    0x8A937,
    0x8A939,
    0x8A93C,
    0x8A941,
    0x8A962,
    0x8A963,
    0x3574DB,
    0x3574DC,
    0x3574DE,
    0x3574FF,
    0x357502,
    0x379F52,
    0x379F54,
    0x379F55,
    0x379F57,
    0x379F58,
    0x38942B,
    0x38942D,
    0x38942E,
    0x389430,
    0x389431,
    0x389434,
    0x389437,
    0x389439,
    0x38943B,
    0x389454,
    0x389455,
    0x389457,
    0x38945D,
    0x389463,
    0x389465,
    0x389467,
    0x389476,
    0x389477,
    0x389478,
    0x357507,
    0x357508,
    0x35750A,
    0x35750C,
    0x35750D,
    0x8A968,
    0x8A96B,
    0x8A96D,
    0x8A96E,
)
FREE_TRACE = (
    0x7800,
    0x7801,
    0x7803,
    0x7806,
    0x7809,
    0x780B,
    0x780E,
    0x7810,
    0x7816,
    0x781A,
    0x7820,
    0x784D,
    0x7850,
    0x7851,
    0x35785D,
    0x36FB17,
    0x389156,
    0x389158,
    0x389159,
    0x38915B,
    0x38915F,
    0x389161,
    0x389164,
    0x389166,
    0x38916C,
    0x389172,
    0x389174,
    0x38918E,
    0x38918F,
    0x7856,
    0x7859,
    0x785A,
)
COPY_TRACE = (
    (
        0x36E580,
        0x36E581,
        0x36E582,
        0x36E586,
        0x36E58A,
        0x36E58E,
        0x36E590,
        0x36E592,
        0x36E594,
        0x36E596,
        0x36E598,
        0x36E59A,
        0x36E5A0,
        0x36E5A3,
        0x36E5A9,
        0x36E5AF,
        0x36E5B1,
        0x36E5B9,
        0x36EA4D,
        0x36EA4F,
        0x36EA51,
        0x36EA53,
        0x36EA56,
        0x36EA58,
        0x36EA5A,
        0x36EA60,
        0x36EA64,
        0x36EA69,
        0x36EA6D,
        0x36EA72,
        0x36EA75,
        0x36EA78,
        0x36EA79,
        0x36EA7B,
        0x36EA7E,
        0x36EA80,
        0x36EA82,
        0x36EA85,
    )
    + (0x36EA87, 0x36EA89, 0x36EA8B, 0x36EA8E, 0x36EA91, 0x36EA94) * 4
    + (
        0x36EA96,
        0x36EA98,
        0x36EA9B,
        0x36EAB0,
        0x36EAB4,
        0x36EAB5,
        0x36EAB6,
    )
)


class ConformanceError(RuntimeError):
    pass


def _require(condition, message):
    if not condition:
        raise ConformanceError(message)


def _normalize(operation):
    try:
        return operation()
    except ConformanceError:
        raise
    except Exception as exc:
        raise ConformanceError(str(exc)) from exc


def vectors():
    return [dict(alignment=a, profile=p) for a in range(16) for p in range(3)]


def geometry(vector):
    _require(
        type(vector) is dict
        and set(vector) == {"alignment", "profile"}
        and all(type(value) is int for value in vector.values())
        and vector in vectors(),
        "outside finite growth6 to9 geometry",
    )
    a = vector["alignment"]
    return dict(
        old_begin=DATA + 0x800 + a,
        old_end=DATA + 0x830 + a,
        old_capacity=DATA + 0x830 + a,
        new_begin=DATA + 0x2800 + a,
        new_end=DATA + 0x2830 + a,
        new_capacity=DATA + 0x2848 + a,
        copy_bytes=48,
        request=72,
        old_size=6,
        requested=9,
    )


def frame_join(entry):
    _require(
        type(entry) is int and STACK + 96 <= entry <= STACK + 8192 - 8,
        "growth6 to9 stack geometry differs",
    )
    return dict(
        protected_start=entry - 96,
        protected_end=entry + 8,
        resize=entry - 20,
        allocation=entry - 48,
        heap_allocate=entry - 96,
        copy=entry - 56,
        deallocation=entry - 56,
        heap_free=entry - 88,
        returned=entry + 8,
    )


def _read(pages, address, size):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def _write(pages, address, payload):
    for i, byte in enumerate(payload):
        pages[(address + i) & ~4095][(address + i) & 4095] = byte


def _fixture(vector):
    geometry(vector)
    fixture = copy.deepcopy(_normalize(lambda: resize._fixture(vector)))
    memory = {page: bytearray(data) for page, data in fixture["pages"].items()}
    _write(memory, fixture["registers"]["esp"] + 4, (1).to_bytes(4, "little"))
    fixture["pages"] = _pages(memory)
    return fixture


def _event_law(pages):
    memory = {page: bytearray(data) for page, data in pages.items()}
    events = []

    def emit(access, address, value, width=4):
        events.append(dict(access=access, address=address, width=width, value=value))
        if access == "write":
            _write(memory, address, value.to_bytes(width, "little"))

    return memory, events, emit


def _pages(memory):
    return {page: bytes(data) for page, data in memory.items()}


def _stack(pages):
    return _read(pages, STACK, 8192)


def _allocation_packet_law(regs, pages, destination, continuation):
    """Checked ordinary relocation; old generic pointer bounds stay unchanged."""
    a = regs["esp"]
    memory, events, e = _event_law(pages)
    w = lambda address, value: e("write", address, value)
    r = lambda address, value: e("read", address, value)
    w(a - 4, regs["ebp"])
    r(a + 4, 9)
    for address, value in ((a - 8, 72), (a - 12, BASE + 0x8A968), (a - 16, a - 4)):
        w(address, value)
    r(a - 8, 72)
    w(a - 20, 72)
    w(a - 24, BASE + 0x357507)
    w(a - 28, a - 16)
    r(a - 28, a - 16)
    w(a - 28, a - 16)
    w(a - 32, regs["esi"])
    r(a - 20, 72)
    w(a - 36, 72)
    w(a - 40, 0)
    r(HEAP_GLOBAL, HEAP)
    w(a - 44, HEAP)
    r(ALLOC_IAT, IMPORT)
    w(a - 48, BASE + 0x389463)
    for address, value in (
        (a - 32, regs["esi"]),
        (a - 28, a - 16),
        (a - 24, BASE + 0x357507),
        (a - 20, 72),
        (a - 16, a - 4),
        (a - 12, BASE + 0x8A968),
        (a - 4, regs["ebp"]),
        (a, allocator.RETURN),
    ):
        r(address, value)
    canonical = allocator.DATA + 0x800 + (destination & 15)
    wanted = dict(
        relation=dict(result=canonical, request=72, metadata=None),
        registers=dict(regs, eax=canonical, ecx=canonical, edx=0xB0000001, esp=a + 8),
        flags=_add_flags(a - 8, 4),
        flag_mask=0x8D5,
        stack=_stack(memory),
        payload=pages[destination & ~4095],
        events=events,
    )
    child = _normalize(
        lambda: allocator._expected(
            dict(count=9, pointer=canonical),
            dict(regs),
            _stack(pages),
            pages[destination & ~4095],
            stack_base=STACK,
            data_base=allocator.DATA,
        )
    )
    _require(_same_packet(child, wanted), "growth6 to9 allocation primitive differs")
    # These are the only pointer-bearing cells in the admitted ordinary packet.
    # No metadata event or payload write is transported, and caller RET is bound
    # separately to the actual stack word installed by the owner CALL.
    wanted["relation"]["result"] = destination
    wanted["registers"].update(eax=destination, ecx=destination)
    wanted["events"][-1]["value"] = continuation
    _require(
        int.from_bytes(_read(pages, a, 4), "little") == continuation,
        "growth6 to9 allocation installed continuation differs",
    )
    return wanted


def _copy_packet_law(regs, xmm, pages, source, destination):
    c = regs["esp"]
    snapshot = _read(pages, source, 48)
    memory, events, e = _event_law(pages)
    e("write", c - 4, regs["edi"])
    e("write", c - 8, regs["esi"])
    e("read", c + 8, source)
    e("read", c + 12, 48)
    e("read", c + 4, destination)
    e("read", FEATURE, 0x93939393)
    for access, base in (("read", source), ("write", destination)):
        for at in (0, 8, 16, 24):
            e(access, base + at, int.from_bytes(snapshot[at : at + 8], "little"), 8)
    for at in (32, 36, 40, 44):
        word = int.from_bytes(snapshot[at : at + 4], "little")
        e("read", source + at, word)
        e("write", destination + at, word)
    e("read", c + 4, destination)
    e("read", c - 8, regs["esi"])
    e("read", c - 4, regs["edi"])
    e("read", c, BASE + 0x2EB6A6)
    wanted = dict(
        pages=_pages(memory),
        source_snapshot=snapshot,
        registers=dict(
            regs,
            eax=destination,
            ecx=0,
            edx=int.from_bytes(snapshot[44:48], "little"),
            esp=c + 4,
        ),
        xmm=dict(
            xmm,
            xmm0=int.from_bytes(snapshot[:16], "little"),
            xmm1=int.from_bytes(snapshot[16:32], "little"),
        ),
        flags=0x44,
        flag_mask=0x8C5,
        df=0,
        endpoint=BASE + 0x2EB6A6,
        trace_rvas=[f"0x{pc:08x}" for pc in COPY_TRACE],
        events=events,
    )
    child = _normalize(
        lambda: copy_model.apply(
            pages=pages,
            registers=regs,
            xmm=xmm,
            source=source,
            destination=destination,
            return_address=BASE + 0x2EB6A6,
            entry_flags=4,
        )
    )
    _require(_same_packet(child, wanted), "growth6 to9 copy primitive differs")
    return wanted


def _free_packet_law(regs, pages, source, continuation):
    f = regs["esp"]
    memory, events, e = _event_law(pages)
    w = lambda address, value: e("write", address, value)
    r = lambda address, value: e("read", address, value)
    w(f - 4, regs["ebp"])
    r(f + 8, 6)
    r(f + 12, 8)
    r(f + 12, 8)
    r(f + 4, source)
    w(f - 8, source)
    w(f - 12, BASE + 0x7856)
    w(f - 16, f - 4)
    r(f - 8, source)
    r(f - 8, source)
    w(f - 20, source)
    w(f - 24, 0)
    r(HEAP_GLOBAL, HEAP)
    w(f - 28, HEAP)
    r(FREE_IAT, IMPORT)
    w(f - 32, BASE + 0x389172)
    r(f - 16, f - 4)
    r(f - 12, BASE + 0x7856)
    r(f - 4, regs["ebp"])
    r(f, deallocator.RETURN)
    wanted = dict(
        registers=dict(regs, eax=1, ecx=0xA0000001, edx=0xB0000001, esp=f + 4),
        flags=_add_flags(f - 8, 4),
        flag_mask=0x8D5,
        events=events,
        stack=_stack(memory),
        error=pages[ERROR],
        stop=deallocator.RETURN,
        protocol=dict(
            returned=True, result=1, next_kind=None, error_cell=None, last_error=None
        ),
    )
    child = _normalize(
        lambda: deallocator._expected(
            dict(
                pointer=source,
                count=6,
                stride=8,
                metadata=None,
                responses=[dict(kind="heap_free", eax=1)],
                heap=HEAP,
            ),
            dict(regs),
            _stack(pages),
            pages[ERROR],
            stack_base=STACK,
        )
    )
    _require(_same_packet(child, wanted), "growth6 to9 free primitive differs")
    wanted["events"][-1]["value"] = continuation
    wanted["stop"] = continuation
    _require(
        int.from_bytes(_read(pages, f, 4), "little") == continuation,
        "growth6 to9 free installed continuation differs",
    )
    return wanted


def _boundary(regs, xmm, pages, events, endpoint, flags, mask):
    return dict(
        registers=dict(regs),
        xmm=dict(xmm),
        pages=_pages(pages),
        events=copy.deepcopy(events),
        endpoint=endpoint,
        flags=flags,
        flag_mask=mask,
        df=0,
    )


def _resize_packet_law(vector, fixture):
    g = geometry(vector)
    initial, xmm = fixture["registers"], fixture["xmm"]
    s, obj = initial["esp"], OBJECT_ADDRESS
    _normalize(lambda: resize.frame_join(s))
    memory, events, e = _event_law(fixture["pages"])
    w = lambda address, value: e("write", address, value)
    r = lambda address, value: e("read", address, value)
    w(s - 4, initial["ebp"])
    w(s - 8, obj)
    r(s + 4, 9)
    for address, value in (
        (s - 12, initial["ebx"]),
        (s - 16, initial["esi"]),
        (s - 20, initial["edi"]),
        (s - 24, 9),
        (s - 8, 9),
        (s - 28, BASE + 0x2EB695),
    ):
        w(address, value)
    regs = dict(initial, ebp=s - 4, esp=s - 28, eax=9, esi=obj)
    allocation_entry = _boundary(
        regs, xmm, memory, events, BASE + 0x8A920, fixture["entry_flags"], 0xFFFFFFFF
    )
    allocated = _allocation_packet_law(
        regs, _pages(memory), g["new_begin"], BASE + 0x2EB695
    )
    events.extend(allocated["events"])
    _write(memory, STACK, allocated["stack"])
    regs = dict(allocated["registers"])
    r(obj, g["old_begin"])
    r(obj + 4, g["old_end"])
    for address, value in (
        (s - 24, 48),
        (s - 28, g["old_begin"]),
        (s - 32, g["new_begin"]),
        (s - 36, BASE + 0x2EB6A6),
    ):
        w(address, value)
    regs.update(
        eax=g["new_begin"],
        edi=g["new_begin"],
        esi=obj,
        ecx=48,
        edx=g["old_begin"],
        esp=s - 36,
    )
    copy_entry = _boundary(regs, xmm, memory, events, BASE + 0x36E580, 4, 0x8D5)
    copied = _copy_packet_law(regs, xmm, _pages(memory), g["old_begin"], g["new_begin"])
    events.extend(copied["events"])
    memory = {page: bytearray(data) for page, data in copied["pages"].items()}

    # Replace closure targets after child page transport, retaining all prior events.
    def owner_event(access, address, value):
        events.append(dict(access=access, address=address, width=4, value=value))
        if access == "write":
            _write(memory, address, value.to_bytes(4, "little"))

    w = lambda address, value: owner_event("write", address, value)
    r = lambda address, value: owner_event("read", address, value)
    regs, xmm = dict(copied["registers"]), dict(copied["xmm"])
    r(obj, g["old_begin"])
    r(obj + 4, g["old_end"])
    r(obj + 8, g["old_capacity"])
    for address, value in (
        (s - 24, 8),
        (s - 28, 6),
        (s - 32, g["old_begin"]),
        (s - 36, BASE + 0x2EB6C8),
    ):
        w(address, value)
    regs.update(eax=6, ebx=6, ecx=g["old_begin"], esp=s - 36)
    free_entry = _boundary(regs, xmm, memory, events, BASE + 0x7800, 0x4, 0xC5)
    # SAR6-capacity arithmetic leaves PF1 and CF0; AF is undefined.
    freed = _free_packet_law(regs, _pages(memory), g["old_begin"], BASE + 0x2EB6C8)
    events.extend(freed["events"])
    _write(memory, STACK, freed["stack"])
    regs = dict(freed["registers"])
    r(s - 8, 9)
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
        (s, fixture["return_address"]),
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
    trace = (
        tuple(pc for pc in owner.ORDER if pc <= 0x2EB690)
        + ALLOCATION_TRACE
        + tuple(pc for pc in owner.ORDER if 0x2EB695 <= pc <= 0x2EB6A1)
        + COPY_TRACE
        + tuple(pc for pc in owner.ORDER if 0x2EB6A6 <= pc <= 0x2EB6C3)
        + FREE_TRACE
        + tuple(pc for pc in owner.ORDER if pc >= 0x2EB6C8)
    )
    return dict(
        geometry=g,
        registers=regs,
        xmm=xmm,
        flags=_add_flags(s - 32, 12),
        flag_mask=0x8D5,
        df=0,
        events=events,
        pages=_pages(memory),
        endpoint=fixture["return_address"],
        allocation_entry=allocation_entry,
        allocation_packet=allocated,
        copy_entry=copy_entry,
        copy_packet=copied,
        free_entry=free_entry,
        free_packet=freed,
        allocation_request=dict(
            continuation=BASE + 0x389463, handle=HEAP, flags=0, bytes=72
        ),
        free_request=dict(
            continuation=BASE + 0x389172, handle=HEAP, flags=0, pointer=g["old_begin"]
        ),
        trace_rvas=[f"0x{pc:08x}" for pc in trace],
    )


def _expected(vector, fixture):
    g = geometry(vector)
    _require(
        type(fixture) is dict
        and set(fixture) == FIXTURE_KEYS
        and _same_packet(fixture, _fixture(vector)),
        "growth6 to9 fixture recipe differs",
    )
    initial, xmm = fixture["registers"], fixture["xmm"]
    entry, obj = initial["esp"], OBJECT_ADDRESS
    frame_join(entry)
    memory, prefix, e = _event_law(fixture["pages"])
    for access, address, value in (
        ("write", entry - 4, initial["esi"]),
        ("write", entry - 8, initial["edi"]),
        ("read", obj + 8, g["old_capacity"]),
        ("read", obj + 4, g["old_end"]),
        ("read", obj, g["old_begin"]),
        ("write", entry - 12, initial["ebx"]),
        ("write", entry - 16, 9),
        ("write", entry - 20, BASE + 0x2EB66E),
    ):
        e(access, address, value)
    # Full6/cap6: spare0, half3, minimum7, proposal9, room1FFFFFFC.
    # Selected source CMP9,7 defines arithmetic flags0 and preserves IF bit200.
    regs = dict(
        initial, eax=9, ebx=0x1FFFFFFC, ecx=obj, edx=9, esi=obj, edi=6, esp=entry - 20
    )
    incoming = _boundary(regs, xmm, memory, prefix, BASE + 0x2EB680, 0, 0x8D5)
    child_fixture = dict(
        pages=_pages(memory),
        registers=regs,
        xmm=dict(xmm),
        return_address=BASE + 0x2EB66E,
        entry_flags=0x202,
    )
    child = _resize_packet_law(vector, child_fixture)
    actual_child = _normalize(
        lambda: model.apply(
            pages=child_fixture["pages"],
            registers=regs,
            xmm=xmm,
            source=g["old_begin"],
            destination=g["new_begin"],
            object_address=obj,
            return_address=BASE + 0x2EB66E,
            entry_flags=0x202,
        )
    )
    _require(_same_packet(actual_child, child), "growth6 to9 resize primitive differs")
    joined = prefix + copy.deepcopy(child["events"])
    returned = _boundary(
        child["registers"],
        child["xmm"],
        child["pages"],
        joined,
        BASE + 0x2EB66E,
        child["flags"],
        child["flag_mask"],
    )
    events = copy.deepcopy(joined)
    events.extend(
        dict(access="read", address=address, width=4, value=value)
        for address, value in (
            (entry - 12, initial["ebx"]),
            (entry - 8, initial["edi"]),
            (entry - 4, initial["esi"]),
            (entry, fixture["return_address"]),
        )
    )
    result = copy.deepcopy(child)
    result.update(
        registers=dict(
            child["registers"],
            ebx=initial["ebx"],
            edi=initial["edi"],
            esi=initial["esi"],
            esp=entry + 8,
        ),
        events=events,
        endpoint=fixture["return_address"],
        resize_entry=incoming,
        resize_return=returned,
        resize_packet=copy.deepcopy(child),
    )
    for name in ("allocation_entry", "copy_entry", "free_entry"):
        result[name]["events"] = copy.deepcopy(prefix) + result[name]["events"]
    result["trace_rvas"] = (
        [f"0x{pc:08x}" for pc in growth.ORDER if pc <= 0x2EB669]
        + child["trace_rvas"]
        + [f"0x{pc:08x}" for pc in (0x2EB66E, 0x2EB66F, 0x2EB670, 0x2EB671)]
    )
    return result


def _preflight(sources):
    def run():
        _require(
            type(sources) is dict and set(sources) == set(SOURCE_PINS),
            "growth6 to9 source partition differs",
        )
        common._validate_json_tree(sources, "sources")
        result = {
            key: common._source_identity(sources[key], *pin, key)
            for key, pin in SOURCE_PINS.items()
        }
        identity = sources["program_facts"]["identity"]
        _require(
            identity["executable_sha256"] == EXE_SHA256
            and all(
                _same_packet(sources[key]["build_identity"], identity)
                for key in SOURCE_PINS
                if key != "program_facts"
            ),
            "growth6 to9 source build differs",
        )
        resize._preflight({key: sources[key] for key in resize.SOURCE_PINS})
        _require(
            _same_packet(
                sources["resize6_to9"]["source_receipts"],
                resize._preflight({key: sources[key] for key in resize.SOURCE_PINS}),
            ),
            "growth6 to9 resize source join differs",
        )
        return result

    return _normalize(run)


def _load_code(data, image, sources):
    def run():
        import capstone

        _preflight(sources)
        _require(
            type(data) is bytes
            and hashlib.sha256(data).hexdigest() == EXE_SHA256
            and image.image_base == BASE
            and capstone.__version__ == "5.0.7",
            "growth6 to9 executable differs",
        )
        bodies = [
            sources["growth"]["body"],
            sources["owner"]["body"],
            *sources["allocation_conformance"]["bodies"].values(),
            sources["deallocation_composition"]["guard_body"],
            *sources["deallocation_composition"]["free_bodies"],
            *sources["short_simd_semantics"]["scalar_ranges"],
        ]
        witnesses = {}
        for body in bodies:
            for point in body["points"]:
                _require(
                    point["rva"] not in witnesses
                    or _same_packet(witnesses[point["rva"]], point),
                    "growth6 to9 point conflict",
                )
                witnesses[point["rva"]] = point
        _require(
            _same_packet(
                sources["installed_copy48"]["body"]["points"],
                [
                    p
                    for body in sources["short_simd_semantics"]["scalar_ranges"]
                    for p in body["points"]
                ],
            ),
            "growth6 to9 installed copy point identity differs",
        )
        decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        codes, points, byte_map = {}, {}, {}
        for name, (start, end) in BODIES.items():
            offset = image.rva_to_file_offset(start)
            chunk = data[offset : offset + end - start]
            rows = [common._point(row) for row in decoder.disasm(chunk, BASE + start)]
            _require(
                len(chunk) == end - start == sum(row["size"] for row in rows)
                and all(_same_packet(row, witnesses.get(row["rva"])) for row in rows),
                "growth6 to9 exact instruction bytes differ",
            )
            for i, byte in enumerate(chunk):
                _require(
                    start + i not in byte_map or byte_map[start + i] == byte,
                    "growth6 to9 code byte conflict",
                )
                byte_map[start + i] = byte
            codes[name], points[name] = chunk, rows
        ordered = sorted(
            {
                point["rva"]: point for rows in points.values() for point in rows
            }.values(),
            key=lambda point: int(point["rva"], 16),
        )
        _require(
            _canonical_sha256(ordered) == POINTS_SHA256,
            "growth6 to9 selected point identity differs",
        )
        return codes, points

    return _normalize(run)


def _check_boundary(machine, ids, xmm_ids, x, boundary, events, label):
    _require(
        _same_packet(
            {name: machine.reg_read(reg) for name, reg in ids.items()},
            boundary["registers"],
        )
        and _same_packet(
            {name: machine.reg_read(reg) for name, reg in xmm_ids.items()},
            boundary["xmm"],
        )
        and machine.reg_read(x.UC_X86_REG_EFLAGS) & boundary["flag_mask"]
        == boundary["flags"] & boundary["flag_mask"]
        and machine.reg_read(x.UC_X86_REG_EFLAGS) & 0x400 == 0
        and machine.reg_read(x.UC_X86_REG_EIP) == boundary["endpoint"]
        and _same_packet(events, boundary["events"])
        and all(
            bytes(machine.mem_read(page, 4096)) == data
            for page, data in boundary["pages"].items()
        ),
        "growth6 to9 " + label + " differs",
    )


CONTROLS = {
    "resize_request": "growth6 to9 resize entry differs",
    "child_tail": "growth6 to9 copy return differs",
    "caller_argument": "growth6 to9 final pages differ",
    **{
        name: "growth6 to9 resize entry differs"
        for name in (
            "resize_entry_gpr",
            "resize_entry_xmm",
            "resize_entry_df",
            "resize_entry_flags",
            "resize_entry_page",
        )
    },
    **{
        name: "growth6 to9 resize return differs"
        for name in (
            "resize_return_gpr",
            "resize_return_xmm",
            "resize_return_df",
            "resize_return_flags",
            "resize_return_page",
        )
    },
    **{
        name: "growth6 to9 copy entry differs"
        for name in (
            "copy_entry_gpr",
            "copy_entry_xmm",
            "copy_entry_df",
            "copy_entry_flags",
            "copy_entry_page",
        )
    },
    **{
        name: "growth6 to9 copy return differs"
        for name in (
            "copy_return_gpr",
            "copy_return_xmm",
            "copy_return_flags",
            "copy_return_df",
            "copy_return_page",
        )
    },
    "allocation_request": "growth6 to9 allocation handoff differs",
    "free_request": "growth6 to9 free handoff differs",
    "allocation_entry": "growth6 to9 allocation entry differs",
    "allocation_return": "growth6 to9 allocation return differs",
    "free_entry": "growth6 to9 free entry differs",
    **{
        name: "growth6 to9 final pages differ"
        for name in (
            "header",
            "spare",
            "old",
            "feature_padding",
            "ancestor",
            "iat_padding",
            "error",
        )
    },
    "final_gpr": "growth6 to9 final ABI differs",
    "final_xmm": "growth6 to9 final ABI differs",
    "final_df": "growth6 to9 final ABI differs",
    "final_flags": "growth6 to9 final ABI differs",
    **{
        name: "growth6 to9 final events differ"
        for name in (
            "missing_half_record",
            "scalar_order_record",
            "restored_write_record",
        )
    },
    "trace_record": "growth6 to9 final native path differs",
}


def _checked_code_packet(codes, points):
    def run():
        _require(
            type(codes) is dict
            and set(codes) == set(BODIES)
            and type(points) is dict
            and set(points) == set(BODIES),
            "growth6 to9 code packet differs",
        )
        allowed = {}
        for name, (start, end) in BODIES.items():
            _require(
                type(codes[name]) is bytes
                and len(codes[name]) == end - start
                and type(points[name]) is list,
                "growth6 to9 code range differs",
            )
            cursor = start
            for point in points[name]:
                _require(
                    type(point) is dict
                    and set(point) == {"rva", "size", "sha256"}
                    and type(point["rva"]) is str
                    and type(point["size"]) is int
                    and point["size"] > 0
                    and type(point["sha256"]) is str,
                    "growth6 to9 direct point schema differs",
                )
                pc = int(point["rva"], 16)
                _require(
                    pc == cursor
                    and pc + point["size"] <= end
                    and hashlib.sha256(
                        codes[name][pc - start : pc - start + point["size"]]
                    ).hexdigest()
                    == point["sha256"],
                    "growth6 to9 direct point bytes differ",
                )
                cursor += point["size"]
                _require(
                    pc not in allowed or _same_packet(allowed[pc], point),
                    "growth6 to9 direct point conflict",
                )
                allowed[pc] = point
            _require(cursor == end, "growth6 to9 direct point extent differs")
        _require(
            _canonical_sha256([allowed[pc] for pc in sorted(allowed)]) == POINTS_SHA256,
            "growth6 to9 direct point identity differs",
        )
        return allowed

    return _normalize(run)


def _run_case(codes, points, vector, negative=None, *, capture=None):
    _require(
        negative is None or type(negative) is str and negative in CONTROLS,
        "invalid growth6 to9 control",
    )
    fixture = _fixture(vector)
    expected = _expected(vector, fixture)
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "growth6 to9 reviewed Unicorn required")
    allowed = _checked_code_packet(codes, points)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    code_pages = {
        BASE + ((start + i) & ~4095)
        for start, end in BODIES.values()
        for i in range(end - start)
    } | {RETURN, IMPORT}
    _require(
        not code_pages.intersection(fixture["pages"]),
        "growth6 to9 runtime mappings overlap",
    )
    for page in sorted(code_pages):
        machine.mem_map(page, 4096)
        machine.mem_write(page, bytes([0xCC]) * 4096)
    for page, data in fixture["pages"].items():
        machine.mem_map(page, 4096)
        machine.mem_write(page, data)
    for name, (start, end) in BODIES.items():
        machine.mem_write(BASE + start, codes[name])
    ids = {name: getattr(x, "UC_X86_REG_" + name.upper()) for name in REGISTERS}
    xmm_ids = {name: getattr(x, "UC_X86_REG_" + name.upper()) for name in XMM}
    for name, value in fixture["registers"].items():
        machine.reg_write(ids[name], value)
    for name, value in fixture["xmm"].items():
        machine.reg_write(xmm_ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, fixture["entry_flags"])
    g, s = expected["geometry"], fixture["registers"]["esp"] - 20
    events, visited, summaries, boundaries = [], [], [], []
    resume = None

    def flip(address):
        machine.mem_write(address, bytes([machine.mem_read(address, 1)[0] ^ 1]))

    def observe_boundary(name, boundary):
        flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
        boundaries.append(
            dict(
                name=name,
                registers={name: machine.reg_read(reg) for name, reg in ids.items()},
                xmm={name: machine.reg_read(reg) for name, reg in xmm_ids.items()},
                eflags=flags,
                flags=flags & boundary["flag_mask"],
                flag_mask=boundary["flag_mask"],
                df=(flags >> 10) & 1,
                endpoint=machine.reg_read(x.UC_X86_REG_EIP),
                pages_sha256=installed_copy._page_hashes(
                    {
                        page: bytes(machine.mem_read(page, 4096))
                        for page in fixture["pages"]
                    }
                ),
                events_sha256=_canonical_sha256(events),
            )
        )

    def mutate_boundary(prefix):
        if negative == prefix + "_gpr":
            machine.reg_write(ids["edx"], machine.reg_read(ids["edx"]) ^ 1)
        if negative == prefix + "_xmm":
            machine.reg_write(xmm_ids["xmm7"], machine.reg_read(xmm_ids["xmm7"]) ^ 1)
        if negative == prefix + "_df":
            machine.reg_write(
                x.UC_X86_REG_EFLAGS, machine.reg_read(x.UC_X86_REG_EFLAGS) ^ 0x400
            )
        if negative == prefix + "_flags":
            machine.reg_write(
                x.UC_X86_REG_EFLAGS, machine.reg_read(x.UC_X86_REG_EFLAGS) ^ 1
            )
        if negative == prefix + "_page":
            flip(ERROR + 1)

    def allocation_return_boundary():
        pages = {
            page: bytearray(data)
            for page, data in expected["allocation_entry"]["pages"].items()
        }
        _write(pages, STACK, expected["allocation_packet"]["stack"])
        return _boundary(
            expected["allocation_packet"]["registers"],
            fixture["xmm"],
            pages,
            expected["allocation_entry"]["events"]
            + expected["allocation_packet"]["events"],
            BASE + 0x2EB695,
            expected["allocation_packet"]["flags"],
            0x8D5,
        )

    def copy_return_boundary():
        p = expected["copy_packet"]
        return _boundary(
            p["registers"],
            p["xmm"],
            p["pages"],
            expected["copy_entry"]["events"] + p["events"],
            p["endpoint"],
            p["flags"],
            p["flag_mask"],
        )

    def on_code(m, address, size, user):
        nonlocal resume
        if address == IMPORT:
            sp = m.reg_read(ids["esp"])
            words = [
                int.from_bytes(m.mem_read(sp + 4 * i, 4), "little") for i in range(4)
            ]
            index = len(summaries)
            _require(index < 2, "growth6 to9 repeated heap response")
            role = "allocation" if index == 0 else "free"
            wanted = [
                BASE + (0x389463 if index == 0 else 0x389172),
                HEAP,
                0,
                72 if index == 0 else g["old_begin"],
            ]
            if negative == role + "_request":
                flip(sp + 12)
                words[3] ^= 1
            _require(
                sp == s - (76 if index == 0 else 68) and words == wanted,
                "growth6 to9 " + role + " handoff differs",
            )
            initial = expected["resize_entry"]["registers"]
            expected_gpr = (
                dict(
                    initial, eax=72, ecx=OBJECT_ADDRESS, esi=72, ebp=s - 56, esp=s - 76
                )
                if index == 0
                else dict(
                    expected["free_entry"]["registers"],
                    eax=0x1FFFFFFF,
                    edx=7,
                    ebp=s - 52,
                    esp=s - 68,
                )
            )
            _require(
                _same_packet(
                    {name: m.reg_read(reg) for name, reg in ids.items()}, expected_gpr
                )
                and _same_packet(
                    {name: m.reg_read(reg) for name, reg in xmm_ids.items()},
                    fixture["xmm"] if index == 0 else expected["xmm"],
                )
                and m.reg_read(x.UC_X86_REG_EFLAGS) & 0x400 == 0,
                "growth6 to9 " + role + " imported ABI differs",
            )
            flag_mask = 0x8C5 if index == 0 else 0x8D5
            flag_value = (
                4
                if index == 0
                else int((g["old_begin"] & 255).bit_count() % 2 == 0) << 2
            )
            _require(
                m.reg_read(x.UC_X86_REG_EFLAGS) & flag_mask == flag_value,
                "growth6 to9 " + role + " imported flags differ",
            )
            before = {page: bytes(m.mem_read(page, 4096)) for page in fixture["pages"]}
            imported = dict(
                role=role,
                entry_esp=sp,
                words=list(words),
                registers={name: m.reg_read(reg) for name, reg in ids.items()},
                xmm={name: m.reg_read(reg) for name, reg in xmm_ids.items()},
                eflags=m.reg_read(x.UC_X86_REG_EFLAGS),
                flags=m.reg_read(x.UC_X86_REG_EFLAGS) & flag_mask,
                flag_mask=flag_mask,
                df=(m.reg_read(x.UC_X86_REG_EFLAGS) >> 10) & 1,
                endpoint=m.reg_read(x.UC_X86_REG_EIP),
                pages_sha256=installed_copy._page_hashes(before),
                events_sha256=_canonical_sha256(events),
            )
            for name, value in (
                ("eax", g["new_begin"] if index == 0 else 1),
                ("ecx", 0xA0000001),
                ("edx", 0xB0000001),
                ("esp", sp + 16),
            ):
                m.reg_write(ids[name], value)
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            _require(
                all(
                    bytes(m.mem_read(page, 4096)) == data
                    for page, data in before.items()
                )
                and _same_packet(
                    {name: m.reg_read(reg) for name, reg in xmm_ids.items()},
                    fixture["xmm"] if index == 0 else expected["xmm"],
                )
                and _same_packet(
                    {name: m.reg_read(reg) for name, reg in ids.items()},
                    dict(
                        expected_gpr,
                        eax=g["new_begin"] if index == 0 else 1,
                        ecx=0xA0000001,
                        edx=0xB0000001,
                        esp=sp + 16,
                    ),
                )
                and m.reg_read(x.UC_X86_REG_EFLAGS) == 0x246,
                "growth6 to9 supplied response preservation differs",
            )
            summaries.append(imported)
            resume = words[0]
            m.emu_stop()
            return
        pc = address - BASE
        _require(
            pc in allowed and size == allowed[pc]["size"],
            "growth6 to9 escaped selected code",
        )
        if pc == 0x2EB680:
            mutate_boundary("resize_entry")
            if negative == "resize_request":
                flip(s + 4)
            _require(
                m.reg_read(x.UC_X86_REG_EFLAGS) == 0x202,
                "growth6 to9 resize entry differs",
            )
            _check_boundary(
                m, ids, xmm_ids, x, expected["resize_entry"], events, "resize entry"
            )
            observe_boundary("resize_entry", expected["resize_entry"])
        elif pc == 0x2EB66E:
            mutate_boundary("resize_return")
            _check_boundary(
                m, ids, xmm_ids, x, expected["resize_return"], events, "resize return"
            )
            observe_boundary("resize_return", expected["resize_return"])
        elif pc == 0x8A920:
            if negative == "allocation_entry":
                m.reg_write(ids["ecx"], 0)
            _check_boundary(
                m,
                ids,
                xmm_ids,
                x,
                expected["allocation_entry"],
                events,
                "allocation entry",
            )
            observe_boundary("allocation_entry", expected["allocation_entry"])
        elif pc == 0x2EB695:
            if negative == "allocation_return":
                m.reg_write(ids["ecx"], allocator.DATA + 0x800 + vector["alignment"])
            returned = allocation_return_boundary()
            _check_boundary(m, ids, xmm_ids, x, returned, events, "allocation return")
            observe_boundary("allocation_return", returned)
        elif pc == 0x36E580:
            mutate_boundary("copy_entry")
            _check_boundary(
                m, ids, xmm_ids, x, expected["copy_entry"], events, "copy entry"
            )
            observe_boundary("copy_entry", expected["copy_entry"])
        elif pc == 0x2EB6A6:
            mutate_boundary("copy_return")
            if negative == "child_tail":
                m.reg_write(
                    ids["edx"],
                    int.from_bytes(
                        _read(fixture["pages"], g["old_begin"] + 32, 4), "little"
                    ),
                )
            returned = copy_return_boundary()
            _check_boundary(m, ids, xmm_ids, x, returned, events, "copy return")
            observe_boundary("copy_return", returned)
        elif pc == 0x7800:
            if negative == "free_entry":
                m.reg_write(ids["eax"], 4)
            _check_boundary(
                m, ids, xmm_ids, x, expected["free_entry"], events, "free entry"
            )
            observe_boundary("free_entry", expected["free_entry"])
        visited.append(f"0x{pc:08x}")
        _require(
            visited == expected["trace_rvas"][: len(visited)],
            "growth6 to9 native path differs",
        )

    def on_memory(m, access, address, width, value, user):
        writing = access == uc.UC_MEM_WRITE
        _require(width in (4, 8), "growth6 to9 access width differs")
        if width == 8:
            pc = m.reg_read(x.UC_X86_REG_EIP) - BASE
            halves = {
                0x36EA60: (False, g["old_begin"]),
                0x36EA64: (False, g["old_begin"] + 16),
                0x36EA69: (True, g["new_begin"]),
                0x36EA6D: (True, g["new_begin"] + 16),
            }
            _require(
                pc in halves
                and writing == halves[pc][0]
                and address in (halves[pc][1], halves[pc][1] + 8),
                "growth6 to9 wide site differs",
            )
        actual = dict(
            access="write" if writing else "read",
            address=address,
            width=width,
            value=(
                value & ((1 << (8 * width)) - 1)
                if writing
                else int.from_bytes(m.mem_read(address, width), "little")
            ),
        )
        _require(
            len(events) < len(expected["events"])
            and _same_packet(actual, expected["events"][len(events)]),
            "growth6 to9 ordered memory events differ",
        )
        events.append(actual)

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    next_pc = BASE + 0x2EB620
    for _ in range(3):
        resume = None
        machine.emu_start(next_pc, RETURN, count=1000)
        if resume is None:
            break
        next_pc = resume
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == RETURN
        and [row["role"] for row in summaries] == ["allocation", "free"]
        and [row["name"] for row in boundaries]
        == [
            "resize_entry",
            "allocation_entry",
            "allocation_return",
            "copy_entry",
            "copy_return",
            "free_entry",
            "resize_return",
        ],
        "growth6 to9 endpoint or boundaries differ",
    )
    corrupt = {
        "header": OBJECT_ADDRESS,
        "spare": g["new_end"],
        "old": g["old_begin"] + 44,
        "feature_padding": FEATURE_PAGE + 1,
        "ancestor": s + 28,
        "caller_argument": s + 24,
        "iat_padding": (ALLOC_IAT & ~4095) + 1,
        "error": ERROR + 1,
    }
    if negative in corrupt:
        flip(corrupt[negative])
    if negative == "final_gpr":
        machine.reg_write(ids["edx"], 0)
    if negative == "final_xmm":
        machine.reg_write(xmm_ids["xmm2"], machine.reg_read(xmm_ids["xmm2"]) ^ 1)
    if negative in ("final_flags", "final_df"):
        machine.reg_write(
            x.UC_X86_REG_EFLAGS,
            machine.reg_read(x.UC_X86_REG_EFLAGS)
            ^ (1 if negative == "final_flags" else 0x400),
        )
    copy_start = len(expected["copy_entry"]["events"])
    if negative == "missing_half_record":
        del events[copy_start + 6]
    if negative == "scalar_order_record":
        events[copy_start + 14], events[copy_start + 16] = (
            events[copy_start + 16],
            events[copy_start + 14],
        )
    if negative == "restored_write_record":
        original = int.from_bytes(fixture["pages"][ERROR][:4], "little")
        events.extend(
            [
                dict(access="write", address=ERROR, width=4, value=original ^ 1),
                dict(access="write", address=ERROR, width=4, value=original),
            ]
        )
    if negative == "trace_record":
        visited.append("0x0036ea9d")
    regs = {name: machine.reg_read(reg) for name, reg in ids.items()}
    xmm = {name: machine.reg_read(reg) for name, reg in xmm_ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    pages = {page: bytes(machine.mem_read(page, 4096)) for page in fixture["pages"]}
    _require(
        _same_packet(regs, expected["registers"])
        and _same_packet(xmm, expected["xmm"])
        and flags & 0x8D5 == expected["flags"] & 0x8D5
        and flags & 0x400 == 0,
        "growth6 to9 final ABI differs",
    )
    _require(_same_packet(pages, expected["pages"]), "growth6 to9 final pages differ")
    _require(
        _same_packet(events, expected["events"]), "growth6 to9 final events differ"
    )
    _require(
        _same_packet(visited, expected["trace_rvas"]),
        "growth6 to9 final native path differs",
    )
    result = dict(
        vector=dict(vector),
        registers=regs,
        xmm=xmm,
        flags=flags & 0x8D5,
        flag_mask=0x8D5,
        df=0,
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        summaries=summaries,
        boundaries=boundaries,
        pages_sha256=installed_copy._page_hashes(pages),
        memory_event_count=len(events),
    )
    if capture is not None:
        capture(machine, dict(ids), copy.deepcopy(expected), copy.deepcopy(fixture))
    return result


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _normalize(lambda: common._load_executable(executable))
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, vector) for vector in vectors()]
    controls = []
    for name, reason in CONTROLS.items():
        try:
            _run_case(codes, points, vectors()[-1], name)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "growth6 to9 incidental control: " + name + ": " + str(exc),
            )
            controls.append(dict(name=name, rejected=True, reason=reason))
        else:
            raise ConformanceError("growth6 to9 control survived: " + name)
    all_points = {point["rva"]: point for rows in points.values() for point in rows}
    union = sorted(
        {pc for observation in observations for pc in observation["trace_rvas"]}
    )
    _require(
        set(union) <= set(all_points)
        and all(point["rva"] in union for point in points["owner"])
        and {f"0x{pc:08x}" for pc in growth.ORDER if pc <= 0x2EB671} <= set(union),
        "growth6 to9 coverage differs",
    )
    n = len(observations)
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=ids,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{start:08x}",
                    exclusive_end_rva=f"0x{end:08x}",
                    sha256=hashlib.sha256(codes[name]).hexdigest(),
                )
                for name, (start, end) in BODIES.items()
            ],
            points=sorted(all_points.values(), key=lambda point: int(point["rva"], 16)),
        ),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=union,
        negative_controls=controls,
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=n,
            loaded_sites=len(all_points),
            loaded_bytes=sum(map(len, codes.values())),
            executed_sites=len(union),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            allocation_api_summaries=n,
            free_api_summaries=n,
            copied_bytes=48 * n,
            allocated_bytes=72 * n,
            spare_bytes=24 * n,
            wide_reads=4 * n,
            wide_writes=4 * n,
            scalar_tail_reads=4 * n,
            scalar_tail_writes=4 * n,
            preserved_old_bytes=48 * n,
            memory_events=sum(o["memory_event_count"] for o in observations),
            controls=len(controls),
            accounting_promotions=0,
            resize_invocations=n,
        ),
        scope=dict(
            checked=[
                "Full capacity6 growth proposes9 and installs ordinary resize with allocation72 copy48 and successful ordinary pointer free",
                "Full installed allocation copy and free boundaries with eight GPRs eight XMM and protected pages",
                "Independent full child packet laws and exact ordered events path caller ancestors header spare24 and retained source",
            ],
            premises=[
                "Two successful supplied heap responses preserve all XMM nonvolatile GPRs and memory",
                "Finite coupled alignments zero through fifteen and three copy48 payload profiles",
                "Old canonical ordinary allocation oracle is narrowly relocated only in result EAX ECX and bound caller continuation",
            ],
            excluded=[
                "Class callback allocator ownership failure error paths metadata allocation or accounting promotion",
                "Injected machine and record controls do not establish native execution of their represented stores or sites",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "growth6 to9 executable changed",
    )
    common._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    def run():
        common._validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256
            and _same_packet(evidence["source_receipts"], ids)
            and _same_packet(evidence["vectors"], vectors()),
            "sealed growth6 to9 receipt differs",
        )
        common._assert_publication_safe(evidence)
        return dict(
            status="structurally_verified",
            evidence_sha256=SEALED_SHA256,
            summary=evidence["summary"],
        )

    return _normalize(run)


def build_conformance(executable, sources):
    def run():
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_conformance(executable, evidence, sources):
    def run():
        validate_structure(evidence, sources)
        _require(
            _canonical_bytes(build_conformance(executable, sources))
            == _canonical_bytes(evidence),
            "exact growth6 to9 receipt differs",
        )
        return dict(status="verified", evidence_sha256=SEALED_SHA256)

    return _normalize(run)


encode_conformance = installed_copy.encode_conformance
