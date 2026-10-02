"""Actual-page small movement path clone with supplied ordinary allocation.

This logical instruction/access law creates no fixture and executes no native
helper. Its broader geometry is separate from the finite native48 checkpoint.
The successful imported response is supplied, with no ownership claim.
"""

from __future__ import annotations

import copy

from src.observatory import native_vector_allocation_conformance as allocator
from src.observatory import native_movement_path_scalar_semantics as scalar

ANALYSIS_KIND = "pe_native_movement_path_small_clone_semantics"
SOURCE_PINS = {
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
    "movement_binding": (
        "pe_native_movement_effect_binding",
        "54c060913d61f6bb5e4c1f2586f0d5186ea73ad6c058dd48b1cc056e64a410b9",
    ),
    "allocation_composition": (
        "pe_native_vector_allocation_composition",
        "a63d7ef54e07f8aa63449136988a237592704708ab35cbefb203ec843e8e5507",
    ),
    "allocation_conformance": (
        "pe_native_vector_allocation_conformance",
        "8a2af8e009d4f67b672e92e9fd12bce6a5c32feb609af95f2ee1dc61fb1e9d29",
    ),
    "clone2_conformance": (
        "pe_native_movement_path_clone2_conformance",
        "1cddf384c45fb50a60752656acd2560a7e243dd20f0d68b8a963a4a7bb3a739b",
    ),
}
BASE, DATA, U32 = 0x400000, 0x6000000, 0xFFFFFFFF
HEAP_GLOBAL, ALLOC_IAT, HEAP, IMPORT = 0x8B7634, 0x7D6220, 0x12345678, 0x5000000
REGISTERS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple(f"xmm{i}" for i in range(8))
CODE_RANGES = (
    (0x8A920, 0x8A97B),
    (0x8ABA0, 0x8ABCB),
    (0x9A8E0, 0x9A92F),
    (0x9AC40, 0x9AC97),
    (0x3574DB, 0x35750E),
    (0x379F52, 0x379F5D),
    (0x38942B, 0x389479),
)


class SmallPathCloneError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise SmallPathCloneError(message)


def _normalize(operation):
    try:
        return operation()
    except SmallPathCloneError:
        raise
    except Exception as exc:
        raise SmallPathCloneError(str(exc)) from exc


def _word(value, label):
    _require(
        type(value) is int and 0 <= value <= U32, "invalid small path clone " + label
    )


def _read(pages, address, size=4):
    _require(
        0 <= address
        and address + size <= 2**32
        and all((address + i) & ~4095 in pages for i in range(size)),
        "small path clone read unmapped or wraps",
    )
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def _write(pages, address, payload):
    for i, byte in enumerate(payload):
        pages[(address + i) & ~4095][(address + i) & 4095] = byte


def _pages(pages):
    return {base: bytes(data) for base, data in pages.items()}


def _add_flags(left, right):
    result = (left + right) & U32
    return (
        int(left + right > U32)
        | int((result & 255).bit_count() % 2 == 0) << 2
        | int(bool((left ^ right ^ result) & 16)) << 4
        | int(result == 0) << 6
        | (result >> 31) << 7
        | int(bool(~(left ^ right) & (left ^ result) & 0x80000000)) << 11
    )


def _test_flags(value):
    return (
        (int(value == 0) << 6)
        | ((value >> 31) << 7)
        | (int((value & 255).bit_count() % 2 == 0) << 2)
    )


def _sub_flags(left, right):
    result = (left - right) & U32
    return (
        int(left < right)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | (int(bool((left ^ right ^ result) & 16)) << 4)
        | (int(result == 0) << 6)
        | ((result >> 31) << 7)
        | (int(bool((left ^ right) & (left ^ result) & 0x80000000)) << 11)
    )


def _disjoint(left, right):
    return left[1] <= right[0] or right[1] <= left[0]


def _validate(pages, registers, xmm, return_address, entry_flags, allocation_result):
    _require(
        type(pages) is dict
        and pages
        and all(
            type(base) is int
            and 0 <= base <= 0xFFFFF000
            and base % 4096 == 0
            and type(data) is bytes
            and len(data) == 4096
            for base, data in pages.items()
        ),
        "invalid small path clone immutable pages",
    )
    _require(
        type(registers) is dict
        and set(registers) == set(REGISTERS)
        and all(
            type(name) is str and type(value) is int and 0 <= value <= U32
            for name, value in registers.items()
        ),
        "invalid small path clone GPR schema",
    )
    _require(
        type(xmm) is dict
        and set(xmm) == set(XMM)
        and all(
            type(name) is str and type(value) is int and 0 <= value < 2**128
            for name, value in xmm.items()
        ),
        "invalid small path clone XMM schema",
    )
    for value, label in (
        (return_address, "return address"),
        (entry_flags, "entry flags"),
        (allocation_result, "allocation result"),
    ):
        _word(value, label)
    _require(
        entry_flags & ~0xAD7 == 0 and entry_flags & 2 == 2,
        "invalid small path clone ordinary flags",
    )
    g = registers["esp"]
    _require(88 <= g <= U32 - 8, "small path clone stack extent wraps")
    stack_base = min((g - 88) & ~4095, 0xFFFFE000)
    stack_window = (stack_base, stack_base + 8192)
    _read(pages, stack_base, 8192)
    h = registers["ecx"]
    j = int.from_bytes(_read(pages, g + 4), "little")
    _require(
        h > 0 and j > 0 and h + 12 <= U32 and j + 12 <= U32,
        "small path clone header extent wraps",
    )
    _read(pages, h, 12)
    source_header = _read(pages, j, 12)
    o = int.from_bytes(source_header[:4], "little")
    end = int.from_bytes(source_header[4:8], "little")
    _require(end >= o and (end - o) % 8 == 0, "small path clone source count differs")
    size = end - o
    count = size // 8
    _require(count <= 511, "small path clone count requires aligned allocation")
    globals_spans = ()
    if count:
        _require(
            o > 0 and end <= U32, "small path clone positive source extent differs"
        )
        _read(pages, DATA, 16384)
        _read(pages, HEAP_GLOBAL & ~4095, 4096)
        _read(pages, ALLOC_IAT & ~4095, 4096)
        _require(
            int.from_bytes(_read(pages, HEAP_GLOBAL), "little") == HEAP
            and int.from_bytes(_read(pages, ALLOC_IAT), "little") == IMPORT,
            "small path clone heap globals differ",
        )
        _require(
            DATA <= allocation_result <= DATA + 16384 - size,
            "small path clone allocation result outside ordinary domain",
        )
        globals_spans = (
            (HEAP_GLOBAL & ~4095, (HEAP_GLOBAL & ~4095) + 4096),
            (ALLOC_IAT & ~4095, (ALLOC_IAT & ~4095) + 4096),
        )
        _read(pages, o, size)
        _read(pages, allocation_result, size)
    else:
        _require(
            allocation_result == 0,
            "small path clone zero count requires zero allocation result",
        )
    touched = (
        (g - 88, g + 8),
        (h, h + 12),
        (j, j + 12),
        (o, end),
        (allocation_result, allocation_result + size),
    )
    active = tuple(span for span in touched if span[0] < span[1])
    _require(
        all(
            _disjoint(span, other)
            for i, span in enumerate(active)
            for other in active[i + 1 :]
        )
        and all(_disjoint(span, fixed) for span in active for fixed in globals_spans)
        and (not count or _disjoint(stack_window, (DATA, DATA + 16384)))
        and all(_disjoint(stack_window, fixed) for fixed in globals_spans),
        "small path clone protected extents overlap",
    )
    code_pages = {
        (BASE + address) & ~4095
        for start, end in CODE_RANGES
        for address in range(start, end)
    }
    _require(
        not code_pages.intersection(pages),
        "small path clone pages overlap selected code",
    )
    _require(
        return_address > 0
        and all(
            not (BASE + start <= return_address < BASE + end)
            for start, end in CODE_RANGES
        )
        and all(not (start <= return_address < end) for start, end in active),
        "small path clone return overlaps touched data or selected body",
    )
    _require(
        int.from_bytes(_read(pages, g), "little") == return_address,
        "small path clone caller return differs",
    )
    return (
        dict(
            entry=g,
            source=o,
            destination=allocation_result,
            source_header=j,
            destination_header=h,
        ),
        stack_base,
        count,
    )


def _same_packet(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return (
            set(a) == set(b)
            and all(any(type(k) is type(j) and k == j for j in b) for k in a)
            and all(_same_packet(a[k], b[k]) for k in a)
        )
    if type(a) in (list, tuple):
        return len(a) == len(b) and all(_same_packet(x, y) for x, y in zip(a, b))
    return a == b


def _event_law(original):
    memory = {p: bytearray(v) for p, v in original.items()}
    events = []

    def event(access, address, value):
        if access == "write":
            _write(memory, address, value.to_bytes(4, "little"))
        else:
            _require(
                int.from_bytes(_read(memory, address), "little") == value,
                "movement expected read differs",
            )
        events.append(dict(access=access, address=address, width=4, value=value))

    return memory, events, event


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


STATIC_ORDERS = {
    0x9A8E0: (
        0x9A8E0,
        0x9A8E1,
        0x9A8E3,
        0x9A8E4,
        0x9A8E6,
        0x9A8E7,
        0x9A8EA,
        0x9A8F0,
        0x9A8F7,
        0x9A8FE,
        0x9A901,
        0x9A903,
        0x9A906,
        0x9A907,
        0x9A90C,
        0x9A90E,
        0x9A910,
        0x9A913,
        0x9A914,
        0x9A917,
        0x9A918,
        0x9A91A,
        0x9A91C,
        0x9A921,
        0x9A924,
        0x9A927,
        0x9A928,
        0x9A92A,
        0x9A92B,
        0x9A92C,
    ),
    0x9AC40: (
        0x9AC40,
        0x9AC41,
        0x9AC43,
        0x9AC44,
        0x9AC46,
        0x9AC47,
        0x9AC4A,
        0x9AC50,
        0x9AC57,
        0x9AC5E,
        0x9AC60,
        0x9AC62,
        0x9AC63,
        0x9AC65,
        0x9AC66,
        0x9AC67,
        0x9AC6A,
        0x9AC70,
        0x9AC72,
        0x9AC73,
        0x9AC78,
        0x9AC7A,
        0x9AC7D,
        0x9AC7F,
        0x9AC82,
        0x9AC85,
        0x9AC87,
        0x9AC88,
        0x9AC89,
        0x9AC8A,
        0x9AC8D,
        0x9AC92,
    ),
    0x8ABA0: (
        0x8ABA0,
        0x8ABA1,
        0x8ABA3,
        0x8ABA6,
        0x8ABA7,
        0x8ABA9,
        0x8ABAB,
        0x8ABAD,
        0x8ABB0,
        0x8ABB2,
        0x8ABB4,
        0x8ABB6,
        0x8ABB8,
        0x8ABBB,
        0x8ABBE,
        0x8ABC1,
        0x8ABC4,
        0x8ABC6,
        0x8ABC8,
        0x8ABC9,
        0x8ABCA,
    ),
}


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


PARENT_PREFIX = tuple(p for p in STATIC_ORDERS[0x9A8E0] if p <= 0x9A907)


PARENT_MIDDLE = tuple(p for p in STATIC_ORDERS[0x9A8E0] if 0x9A90C <= p <= 0x9A91C)


PARENT_SUFFIX = tuple(p for p in STATIC_ORDERS[0x9A8E0] if p >= 0x9A921)


RESERVE_PREFIX = tuple(
    p
    for p in STATIC_ORDERS[0x9AC40]
    if p <= 0x9AC73 and p not in (0x9AC62, 0x9AC63, 0x9AC65, 0x9AC66, 0x9AC67)
)


RESERVE_SUFFIX = tuple(p for p in STATIC_ORDERS[0x9AC40] if 0x9AC78 <= p <= 0x9AC8A)


def _scalar_trace(count):
    return (
        STATIC_ORDERS[0x8ABA0][:8]
        + STATIC_ORDERS[0x8ABA0][8:18] * count
        + STATIC_ORDERS[0x8ABA0][18:]
    )


def _trace(count):
    if count:
        return (
            PARENT_PREFIX
            + RESERVE_PREFIX
            + ALLOCATION_TRACE
            + RESERVE_SUFFIX
            + PARENT_MIDDLE
            + _scalar_trace(count)
            + PARENT_SUFFIX
        )
    zero_reserve = tuple(pc for pc in STATIC_ORDERS[0x9AC40] if pc <= 0x9AC67)
    return (
        PARENT_PREFIX
        + zero_reserve
        + (0x9A90C, 0x9A90E)
        + tuple(pc for pc in PARENT_SUFFIX if pc >= 0x9A927)
    )


def _allocation_packet_law(
    registers, pages, destination, continuation, stack_base, count
):
    """Compare all seven positive ordinary primitive fields before RET transport."""
    a = registers["esp"]
    size = count * 8
    memory, events, event = _event_law(pages)
    w = lambda at, value: event("write", at, value)
    r = lambda at, value: event("read", at, value)
    w(a - 4, registers["ebp"])
    r(a + 4, count)
    for at, value in ((a - 8, size), (a - 12, BASE + 0x8A968), (a - 16, a - 4)):
        w(at, value)
    r(a - 8, size)
    for at, value in ((a - 20, size), (a - 24, BASE + 0x357507), (a - 28, a - 16)):
        w(at, value)
    r(a - 28, a - 16)
    w(a - 28, a - 16)
    w(a - 32, registers["esi"])
    r(a - 20, size)
    w(a - 36, size)
    w(a - 40, 0)
    r(HEAP_GLOBAL, HEAP)
    w(a - 44, HEAP)
    r(ALLOC_IAT, IMPORT)
    w(a - 48, BASE + 0x389463)
    imported = _boundary(
        dict(registers, eax=size, esi=size, ebp=a - 28, esp=a - 48),
        {},
        memory,
        events,
        IMPORT,
        _test_flags(size),
        0x8C5,
    )
    for at, value in (
        (a - 32, registers["esi"]),
        (a - 28, a - 16),
        (a - 24, BASE + 0x357507),
        (a - 20, size),
        (a - 16, a - 4),
        (a - 12, BASE + 0x8A968),
        (a - 4, registers["ebp"]),
        (a, allocator.RETURN),
    ):
        if at == a:
            # The generic law has a fixed RETURN sentinel; actual installed bytes
            # are checked below and no other event/page/pointer cell is changed.
            events.append(dict(access="read", address=a, width=4, value=value))
        else:
            r(at, value)
    wanted = dict(
        relation=dict(result=destination, request=size, metadata=None),
        registers=dict(
            registers, eax=destination, ecx=destination, edx=0xB0000001, esp=a + 8
        ),
        flags=_add_flags(a - 8, 4),
        flag_mask=0x8D5,
        stack=_read(memory, stack_base, 8192),
        payload=_read(pages, DATA, 16384),
        events=events,
    )
    child = _normalize(
        lambda: allocator._expected(
            dict(count=count, pointer=destination),
            dict(registers),
            _read(pages, stack_base, 8192),
            _read(pages, DATA, 16384),
            stack_base=stack_base,
            data_base=DATA,
        )
    )
    _require(
        _same_packet(child, wanted), "small path clone allocation primitive differs"
    )
    _require(
        int.from_bytes(_read(pages, a), "little") == continuation,
        "small path clone allocation installed continuation differs",
    )
    wanted["events"][-1]["value"] = continuation
    return wanted, imported


def _scalar_packet_law(registers, xmm, pages, source, destination, continuation, count):
    """Independent handwritten prediction of the complete ten-field scalar child."""
    c = registers["esp"]
    size = count * 8
    snapshot = _read(pages, source, size)
    memory, events, event = _event_law(pages)
    event("write", c - 4, registers["ebp"])
    event("read", c + 4, destination)
    event("write", c - 8, registers["esi"])
    for offset in range(0, size, 4):
        word = int.from_bytes(snapshot[offset : offset + 4], "little")
        event("read", source + offset, word)
        event("write", destination + offset, word)
    for at, value in (
        (c - 8, registers["esi"]),
        (c - 4, registers["ebp"]),
        (c, continuation),
    ):
        event("read", at, value)
    wanted = dict(
        pages=_pages(memory),
        registers=dict(
            registers,
            eax=destination + size,
            ecx=int.from_bytes(snapshot[-4:], "little"),
            esp=c + 4,
        ),
        xmm=dict(xmm),
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=continuation,
        source_snapshot=snapshot,
        events=events,
        trace_rvas=[
            f"0x{pc:08x}"
            for pc in (
                0x8ABA0,
                0x8ABA1,
                0x8ABA3,
                0x8ABA6,
                0x8ABA7,
                0x8ABA9,
                0x8ABAB,
                0x8ABAD,
            )
            + (
                0x8ABB0,
                0x8ABB2,
                0x8ABB4,
                0x8ABB6,
                0x8ABB8,
                0x8ABBB,
                0x8ABBE,
                0x8ABC1,
                0x8ABC4,
                0x8ABC6,
            )
            * count
            + (0x8ABC8, 0x8ABC9, 0x8ABCA)
        ],
    )
    child = _normalize(
        lambda: scalar.apply(
            pages=dict(pages),
            registers=dict(registers),
            xmm=dict(xmm),
            source=source,
            destination=destination,
            return_address=continuation,
            entry_flags=0x202,
        )
    )
    _require(_same_packet(child, wanted), "small path clone scalar primitive differs")
    return wanted


def apply(*, pages, registers, xmm, return_address, entry_flags, allocation_result):
    """Predict zero or positive count below 512 with a supplied ordinary success.

    Pages/state are installed inputs; no fixture, native run or API is invoked.
    The source-header third word and unused scalar arguments are preserved.
    """
    g, stack_base, count = _validate(
        pages, registers, xmm, return_address, entry_flags, allocation_result
    )
    size = count * 8
    initial = registers
    p, h, j, o, d = (
        g[k]
        for k in (
            "entry",
            "destination_header",
            "source_header",
            "source",
            "destination",
        )
    )
    memory, events, event = _event_law(pages)
    boundaries = {
        "parent_entry": _boundary(
            initial, xmm, memory, events, BASE + 0x9A8E0, entry_flags, 0xFFFFFFFF
        )
    }
    for at, value in (
        (p - 4, initial["ebp"]),
        (p - 8, initial["esi"]),
        (p - 12, initial["edi"]),
    ):
        event("write", at, value)
    event("read", p + 4, j)
    for at in (h, h + 4, h + 8):
        event("write", at, 0)
    event("read", j + 4, o + size)
    event("read", j, o)
    event("write", p - 16, count)
    event("write", p - 20, BASE + 0x9A90C)
    regs = dict(initial, eax=count, esi=h, edi=j, ebp=p - 4, esp=p - 20)
    boundaries["reserve_entry"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9AC40, _test_flags(count), 0xC5
    )
    for at, value in ((p - 24, p - 4), (p - 28, h), (p - 32, j)):
        event("write", at, value)
    event("read", p - 16, count)
    for at in (h, h + 4, h + 8):
        event("write", at, 0)
    if count == 0:
        for at, value in (
            (p - 32, j),
            (p - 28, h),
            (p - 24, p - 4),
            (p - 20, BASE + 0x9A90C),
        ):
            event("read", at, value)
        regs.update(eax=0, edi=j, esi=h, ebp=p - 4, esp=p - 12)
        boundaries["reserve_return"] = _boundary(
            regs, xmm, memory, events, BASE + 0x9A90C, 0x44, 0x8C5
        )
        for at, value in (
            (p - 12, initial["edi"]),
            (p - 8, initial["esi"]),
            (p - 4, initial["ebp"]),
            (p, return_address),
        ):
            event("read", at, value)
        regs = dict(initial, eax=h, ecx=h, esp=p + 8)
        trace = _trace(0)
        _require(
            len(trace) == 37 and len(events) == 26,
            "small path clone zero path count differs",
        )
        return dict(
            geometry=g,
            registers=regs,
            xmm=dict(xmm),
            flags=0x44,
            flag_mask=0x8C5,
            df=0,
            endpoint=return_address,
            pages=_pages(memory),
            events=events,
            trace_rvas=[f"0x{pc:08x}" for pc in trace],
            boundaries=boundaries,
            allocation_packet=None,
            scalar_packet=None,
            imported=None,
            source_snapshot=b"",
        )
    event("write", p - 36, count)
    event("write", p - 40, BASE + 0x9AC78)
    regs.update(edi=count, ebp=p - 24, esp=p - 40)
    boundaries["allocation_entry"] = _boundary(
        regs, xmm, memory, events, BASE + 0x8A920, _sub_flags(count, 0x1FFFFFFF), 0x8D5
    )
    allocated, imported = _allocation_packet_law(
        regs, _pages(memory), d, BASE + 0x9AC78, stack_base, count
    )
    prefix = copy.deepcopy(events)
    imported["events"] = prefix + imported["events"]
    imported["xmm"] = dict(xmm)
    imported.update(entry_esp=p - 88, words=[BASE + 0x389463, HEAP, 0, size])
    events.extend(copy.deepcopy(allocated["events"]))
    _write(memory, stack_base, allocated["stack"])
    regs = dict(allocated["registers"])
    boundaries["allocation_return"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9AC78, allocated["flags"], 0x8D5
    )
    for at, value in ((h, d), (h + 4, d)):
        event("write", at, value)
    event("read", h, d)
    event("write", h + 8, d + size)
    for at, value in (
        (p - 32, j),
        (p - 28, h),
        (p - 24, p - 4),
        (p - 20, BASE + 0x9A90C),
    ):
        event("read", at, value)
    regs.update(eax=((d + size) & 0xFFFFFF00) | 1, edi=j, ebp=p - 4, esp=p - 12)
    boundaries["reserve_return"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9A90C, allocated["flags"], 0x8D5
    )
    event("read", j + 4, o + size)
    event("write", p - 16, d)
    event("read", p + 4, j)
    event("write", p - 20, j)
    event("write", p - 24, d)
    event("read", h, d)
    event("write", p - 28, d)
    event("read", j, o)
    event("write", p - 32, BASE + 0x9A921)
    regs.update(edx=o + size, ecx=o, esp=p - 32)
    boundaries["scalar_entry"] = _boundary(
        regs, xmm, memory, events, BASE + 0x8ABA0, 0, 0x8C5
    )
    copied = _scalar_packet_law(regs, xmm, _pages(memory), o, d, BASE + 0x9A921, count)
    events.extend(copy.deepcopy(copied["events"]))
    # The original event closure refers to memory: preserve that dictionary while
    # adopting all actual child pages, rather than reseeding any native fixture.
    for page, payload in copied["pages"].items():
        memory[page][:] = payload
    regs = dict(copied["registers"])
    boundaries["scalar_return"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9A921, 0x44, 0x8D5
    )
    event("write", h + 4, d + size)
    for at, value in (
        (p - 12, initial["edi"]),
        (p - 8, initial["esi"]),
        (p - 4, initial["ebp"]),
        (p, return_address),
    ):
        event("read", at, value)
    regs.update(
        eax=h, esi=initial["esi"], edi=initial["edi"], ebp=initial["ebp"], esp=p + 8
    )
    _require(
        len(_trace(count)) == 116 + 10 * count and len(events) == 75 + 4 * count,
        "small path clone source count differs",
    )
    return dict(
        geometry=g,
        registers=regs,
        xmm=dict(xmm),
        flags=_add_flags(p - 28, 16),
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
        pages=_pages(memory),
        events=events,
        trace_rvas=[f"0x{pc:08x}" for pc in _trace(count)],
        boundaries=boundaries,
        allocation_packet=allocated,
        scalar_packet=copied,
        imported=imported,
        source_snapshot=_read(pages, o, size),
    )
