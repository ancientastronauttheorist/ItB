"""Actual-page full6 capacity6 growth to9; no synthetic fixture or native transport."""

from __future__ import annotations
import copy
from src.observatory import native_simd_vector_resize6_to9_semantics as child
from src.observatory import native_lua_vector_growth_semantics as growth

ANALYSIS_KIND = "pe_native_simd_vector_growth6_to9_semantics"
SOURCE_PINS = {
    **child.SOURCE_PINS,
    "growth": (growth.ANALYSIS_KIND, growth.SEALED_SHA256),
}
BASE, U32 = child.BASE, 0xFFFFFFFF
STACK, ERROR = child.STACK, child.ERROR
FEATURE_PAGE, FEATURE = child.FEATURE_PAGE, child.FEATURE
HEAP_GLOBAL, ALLOC_IAT, FREE_IAT, HEAP, IMPORT = (
    child.HEAP_GLOBAL,
    child.ALLOC_IAT,
    child.FREE_IAT,
    child.HEAP,
    child.IMPORT,
)
REGISTERS, XMM = child.REGISTERS, child.XMM
_add_flags = child._add_flags
RANGES = ((0x2EB620, 0x2EB67E),) + tuple(child.primitive.BODIES.values())
ALLOCATION_TRACE, FREE_TRACE, COPY_TRACE = (
    child.ALLOCATION_TRACE,
    child.FREE_TRACE,
    child.COPY_TRACE,
)
OWNER_TRACE = child.OWNER_TRACE
GROWTH_PREFIX = (
    0x2EB620,
    0x2EB621,
    0x2EB623,
    0x2EB624,
    0x2EB627,
    0x2EB629,
    0x2EB62C,
    0x2EB62E,
    0x2EB631,
    0x2EB634,
    0x2EB636,
    0x2EB638,
    0x2EB63A,
    0x2EB63B,
    0x2EB640,
    0x2EB643,
    0x2EB645,
    0x2EB647,
    0x2EB64A,
    0x2EB64C,
    0x2EB64E,
    0x2EB64F,
    0x2EB652,
    0x2EB654,
    0x2EB656,
    0x2EB658,
    0x2EB65A,
    0x2EB65C,
    0x2EB65E,
    0x2EB661,
    0x2EB663,
    0x2EB666,
    0x2EB668,
    0x2EB669,
)


class Growth6To9Error(ValueError):
    pass


primitive = child.primitive


def _require(condition, message):
    if not condition:
        raise Growth6To9Error(message)


def _normalize(operation):
    try:
        return operation()
    except Growth6To9Error:
        raise
    except Exception as exc:
        raise Growth6To9Error(str(exc)) from exc


def _same_packet(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(
            _same_packet(left[key], right[key]) for key in left
        )
    if type(left) in (tuple, list):
        return len(left) == len(right) and all(
            _same_packet(a, b) for a, b in zip(left, right)
        )
    return left == right


def _word(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid actual growth " + label)


def _span(address, size, label):
    _word(address, label)
    _require(address + size <= U32, "actual growth " + label + " exclusive end wraps")
    return address, address + size


def _disjoint(left, right):
    return left[1] <= right[0] or right[1] <= left[0]


def _sub_flags(left, right):
    result = (left - right) & U32
    return (
        int(left < right)
        | int((result & 255).bit_count() % 2 == 0) << 2
        | int((left & 15) < (right & 15)) << 4
        | int(result == 0) << 6
        | (result >> 31) << 7
        | int(bool((left ^ right) & (left ^ result) & 0x80000000)) << 11
    )


def _validate(
    pages,
    registers,
    xmm,
    source,
    destination,
    object_address,
    return_address,
    entry_flags,
):
    _require(
        type(registers) is dict and set(registers) == set(REGISTERS),
        "invalid actual growth GPR schema",
    )
    for name, value in registers.items():
        _word(value, name)
    _require(
        type(xmm) is dict
        and set(xmm) == set(XMM)
        and all(type(value) is int and 0 <= value < 2**128 for value in xmm.values()),
        "invalid actual growth XMM schema or word",
    )
    _word(entry_flags, "entry flags")
    _require(
        entry_flags & ~0xAD7 == 0 and entry_flags & 2 == 2,
        "actual growth ordinary entry flags differ",
    )
    _require(type(pages) is dict and bool(pages), "invalid actual growth pages schema")
    for page, data in pages.items():
        _word(page, "page address")
        _require(
            page % 4096 == 0
            and page + 4096 <= 2**32
            and type(data) is bytes
            and len(data) == 4096,
            "invalid actual growth immutable page",
        )
    r = registers["esp"]
    _require(
        STACK + 96 <= r <= STACK + 8192 - 8,
        "actual growth frame outside fixed stack mapping",
    )
    _word(return_address, "return address")
    _require(return_address > 0, "actual growth zero return address")
    data_spans = (
        _span(source, 48, "source"),
        _span(destination, 72, "destination capacity"),
        _span(object_address, 12, "object header"),
    )
    _require(source > 0, "actual growth old storage must be nonzero for ordinary free")
    _require(
        destination > source + 48, "actual growth forward disjoint copy domain differs"
    )
    _require(registers["ecx"] == object_address, "actual growth object ECX differs")
    protected = (
        (STACK, STACK + 8192),
        (ERROR, ERROR + 4096),
        (FEATURE_PAGE, FEATURE_PAGE + 4096),
        (HEAP_GLOBAL & ~4095, (HEAP_GLOBAL & ~4095) + 4096),
        (ALLOC_IAT & ~4095, (ALLOC_IAT & ~4095) + 4096),
    )
    code = tuple((BASE + start, BASE + end) for start, end in RANGES)
    _require(
        all(
            _disjoint(a, b)
            for i, a in enumerate(data_spans)
            for b in data_spans[i + 1 :]
        )
        and all(_disjoint(span, fixed) for span in data_spans for fixed in protected)
        and all(
            _disjoint(span, body) for span in data_spans + protected for body in code
        ),
        "actual growth protected extents overlap",
    )
    code_pages = {
        (BASE + address) & ~4095
        for start, end in RANGES
        for address in range(start, end)
    }
    _require(
        not set(pages).intersection(code_pages | {IMPORT & ~4095})
        and return_address & ~4095 not in pages
        and return_address & ~4095 != IMPORT & ~4095
        and all(not start <= return_address < end for start, end in code),
        "actual growth data mapping or return overlaps code",
    )
    for start, end in protected + data_spans:
        _require(
            all((address & ~4095) in pages for address in range(start, end)),
            "actual growth required extent is unmapped",
        )
    _require(
        int.from_bytes(_read(pages, r, 4), "little") == return_address,
        "actual growth installed caller words differ",
    )
    _read(
        pages, r + 4, 4
    )  # Admitted arbitrary caller word; RET4 consumes it without native read.
    _require(
        [
            int.from_bytes(_read(pages, object_address + offset, 4), "little")
            for offset in (0, 4, 8)
        ]
        == [source, source + 48, source + 48],
        "actual growth installed header differs",
    )
    _require(
        int.from_bytes(_read(pages, FEATURE, 4), "little") == 0x93939393
        and int.from_bytes(_read(pages, HEAP_GLOBAL, 4), "little") == HEAP
        and all(
            int.from_bytes(_read(pages, address, 4), "little") == IMPORT
            for address in (ALLOC_IAT, FREE_IAT)
        ),
        "actual growth feature heap or IAT premise differs",
    )


def _read(pages, address, size):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def _write(pages, address, payload):
    for i, byte in enumerate(payload):
        pages[(address + i) & ~4095][(address + i) & 4095] = byte


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
        (a, continuation),
    ):
        r(address, value)
    wanted = dict(
        relation=dict(result=destination, request=72, metadata=None),
        registers=dict(
            regs, eax=destination, ecx=destination, edx=0xB0000001, esp=a + 8
        ),
        flags=_add_flags(a - 8, 4),
        flag_mask=0x8D5,
        stack=_stack(memory),
        payload=pages[destination & ~4095],
        events=events,
    )
    child = _normalize(
        lambda: primitive._allocation_packet_law(
            dict(regs), dict(pages), destination, continuation
        )
    )
    _require(_same_packet(child, wanted), "growth6 to9 allocation primitive differs")
    _require(
        int.from_bytes(_read(pages, a, 4), "little") == continuation,
        "actual growth allocation continuation differs",
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
        lambda: primitive._copy_packet_law(
            dict(regs), dict(xmm), dict(pages), source, destination
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
    r(f, continuation)
    wanted = dict(
        registers=dict(regs, eax=1, ecx=0xA0000001, edx=0xB0000001, esp=f + 4),
        flags=_add_flags(f - 8, 4),
        flag_mask=0x8D5,
        events=events,
        stack=_stack(memory),
        error=pages[ERROR],
        stop=continuation,
        protocol=dict(
            returned=True, result=1, next_kind=None, error_cell=None, last_error=None
        ),
    )
    child = _normalize(
        lambda: primitive._free_packet_law(
            dict(regs), dict(pages), source, continuation
        )
    )
    _require(_same_packet(child, wanted), "growth6 to9 free primitive differs")
    _require(
        int.from_bytes(_read(pages, f, 4), "little") == continuation,
        "actual growth free continuation differs",
    )
    return wanted


def _resize_packet_law(g, incoming, obj):
    initial, xmm = incoming["registers"], incoming["xmm"]
    s = initial["esp"]
    memory, events, e = _event_law(incoming["pages"])
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
        regs, xmm, memory, events, BASE + 0x8A920, incoming["entry_flags"], 0xFFFFFFFF
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
    copy_entry = _boundary(
        regs,
        xmm,
        memory,
        events,
        BASE + 0x36E580,
        _sub_flags(g["old_end"], g["old_begin"]),
        0x8D5,
    )
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
        (s, incoming["return_address"]),
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
        tuple(pc for pc in OWNER_TRACE if pc <= 0x2EB690)
        + ALLOCATION_TRACE
        + tuple(pc for pc in OWNER_TRACE if 0x2EB695 <= pc <= 0x2EB6A1)
        + COPY_TRACE
        + tuple(pc for pc in OWNER_TRACE if 0x2EB6A6 <= pc <= 0x2EB6C3)
        + FREE_TRACE
        + tuple(pc for pc in OWNER_TRACE if pc >= 0x2EB6C8)
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
        endpoint=incoming["return_address"],
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


def apply(
    *,
    pages,
    registers,
    xmm,
    source,
    destination,
    object_address,
    return_address,
    entry_flags,
):
    """Detached21-key growth owner law from actual installed pages and state."""
    return _normalize(
        lambda: _apply(
            pages,
            registers,
            xmm,
            source,
            destination,
            object_address,
            return_address,
            entry_flags,
        )
    )


def _apply(
    pages,
    registers,
    xmm,
    source,
    destination,
    object_address,
    return_address,
    entry_flags,
):
    _validate(
        pages,
        registers,
        xmm,
        source,
        destination,
        object_address,
        return_address,
        entry_flags,
    )
    g = dict(
        old_begin=source,
        old_end=source + 48,
        old_capacity=source + 48,
        new_begin=destination,
        new_end=destination + 48,
        new_capacity=destination + 72,
        copy_bytes=48,
        request=72,
        old_size=6,
        requested=9,
    )
    initial, xmm = dict(registers), dict(xmm)
    entry, obj = initial["esp"], object_address
    memory, prefix, e = _event_law(pages)
    for access, address, value in (
        ("write", entry - 4, initial["esi"]),
        ("write", entry - 8, initial["edi"]),
        ("read", obj + 8, source + 48),
        ("read", obj + 4, source + 48),
        ("read", obj, source),
        ("write", entry - 12, initial["ebx"]),
        ("write", entry - 16, 9),
        ("write", entry - 20, BASE + 0x2EB66E),
    ):
        e(access, address, value)
    regs = dict(
        initial, eax=9, ebx=0x1FFFFFFC, ecx=obj, edx=9, esi=obj, edi=6, esp=entry - 20
    )
    # Selected CMP9vs7 clears arithmetic bits and preserves admitted IF/reservedbit1.
    full_flags = entry_flags & 0x202
    incoming = _boundary(regs, xmm, memory, prefix, BASE + 0x2EB680, 0, 0x8D5)
    actual_pages = _pages(memory)
    supplied = dict(
        pages=actual_pages,
        registers=regs,
        xmm=xmm,
        return_address=BASE + 0x2EB66E,
        entry_flags=full_flags,
    )
    predicted = _resize_packet_law(g, supplied, obj)
    observed = _normalize(
        lambda: child.apply(
            pages=actual_pages,
            registers=regs,
            xmm=xmm,
            source=source,
            destination=destination,
            object_address=obj,
            return_address=BASE + 0x2EB66E,
            entry_flags=full_flags,
        )
    )
    _require(_same_packet(observed, predicted), "growth6 to9 resize primitive differs")
    joined = prefix + copy.deepcopy(predicted["events"])
    returned = _boundary(
        predicted["registers"],
        predicted["xmm"],
        predicted["pages"],
        joined,
        BASE + 0x2EB66E,
        predicted["flags"],
        predicted["flag_mask"],
    )
    events = copy.deepcopy(joined)
    events.extend(
        dict(access="read", address=address, width=4, value=value)
        for address, value in (
            (entry - 12, initial["ebx"]),
            (entry - 8, initial["edi"]),
            (entry - 4, initial["esi"]),
            (entry, return_address),
        )
    )
    result = copy.deepcopy(predicted)
    result.update(
        registers=dict(
            predicted["registers"],
            ebx=initial["ebx"],
            edi=initial["edi"],
            esi=initial["esi"],
            esp=entry + 8,
        ),
        events=events,
        endpoint=return_address,
        resize_entry=incoming,
        resize_return=returned,
        resize_packet=copy.deepcopy(predicted),
    )
    for name in ("allocation_entry", "copy_entry", "free_entry"):
        result[name]["events"] = copy.deepcopy(prefix) + result[name]["events"]
    result["trace_rvas"] = (
        [f"0x{pc:08x}" for pc in GROWTH_PREFIX]
        + predicted["trace_rvas"]
        + [f"0x{pc:08x}" for pc in (0x2EB66E, 0x2EB66F, 0x2EB670, 0x2EB671)]
    )
    return result
