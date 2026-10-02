"""Actual-page empty-destination small positive-count movement path assignment.

This logical normal-return law supplies one successful ordinary allocation,
executes no native helper/API, and changes no ownership or old corpus domain.
"""

from __future__ import annotations
import copy
from src.observatory import native_vector_allocation_conformance as allocator
from src.observatory import native_movement_path_small_clone_semantics as primitives

ANALYSIS_KIND = "pe_native_movement_path_small_assign_semantics"
BASE, DATA, U32 = 0x400000, 0x6000000, 0xFFFFFFFF
HEAP_GLOBAL, ALLOC_IAT, HEAP, IMPORT = 0x8B7634, 0x7D6220, 0x12345678, 0x5000000


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


REGISTERS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")


XMM = tuple(f"xmm{i}" for i in range(8))


CODE_RANGES = (
    (0x8A920, 0x8A97B),
    (0x8ABA0, 0x8ABCB),
    (0xC5BB0, 0xC5C92),
    (0x9AC40, 0x9AC97),
    (0x3574DB, 0x35750E),
    (0x379F52, 0x379F5D),
    (0x38942B, 0x389479),
)
BODY_PINS = {
    0xC5BB0: (226, "62157759ee3564515e63f20e297c171de6444d84732bccf7414eb208d953eefe"),
    0x9AC40: (87, "29a0428ed018a85e4e0a76f283f10040cf9e084f49bee5706b58766b570cb9d1"),
    0x8ABA0: (43, "92494ea2dfd86d06ce373c9837f55d42e6c62746bd9c2c3c26d2a8af6abe938b"),
    0x8A920: (91, "e13e3be9b5e53d78d61aaaacc91b9c7c3183b77ef1f005bd2010bc1aa9b9830e"),
    0x3574DB: (51, "452b4c981b0a2567c6f4fc35b20076deca45a6b3509707358212028d21db5bfa"),
    0x379F52: (11, "831e215b24984219b6d6d7ce812127a420a48782704f0fef1630b1b8050cabbd"),
    0x38942B: (78, "d97ee587f29bfdaf154ca653059e883b67b56713a5d96643356a4edf6e3edde8"),
}


class SmallPathAssignError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise SmallPathAssignError(message)


def _normalize(operation):
    try:
        return operation()
    except SmallPathAssignError:
        raise
    except Exception as exc:
        raise SmallPathAssignError(str(exc)) from exc


def _word(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid small path assignment " + label)


def _read(pages, address, size=4):
    _require(
        0 <= address
        and address + size <= 2**32
        and all((address + i) & ~4095 in pages for i in range(size)),
        "small path assignment read unmapped or wraps",
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
        "invalid small path assignment immutable pages",
    )
    _require(
        type(registers) is dict
        and set(registers) == set(REGISTERS)
        and all(
            type(name) is str and type(value) is int and 0 <= value <= U32
            for name, value in registers.items()
        ),
        "invalid small path assignment GPR schema",
    )
    _require(
        type(xmm) is dict
        and set(xmm) == set(XMM)
        and all(
            type(name) is str and type(value) is int and 0 <= value < 2**128
            for name, value in xmm.items()
        ),
        "invalid small path assignment XMM schema",
    )
    for value, label in (
        (return_address, "return address"),
        (entry_flags, "entry flags"),
        (allocation_result, "allocation result"),
    ):
        _word(value, label)
    _require(
        entry_flags & ~0xAD7 == 0 and entry_flags & 2 == 2,
        "invalid small path assignment ordinary flags",
    )
    g = registers["esp"]
    _require(96 <= g <= U32 - 8, "small path assignment stack extent wraps")
    stack_base = min((g - 96) & ~4095, 0xFFFFE000)
    stack_window = (stack_base, stack_base + 8192)
    _read(pages, stack_base, 8192)
    _read(pages, DATA, 16384)
    _read(pages, HEAP_GLOBAL & ~4095, 4096)
    _read(pages, ALLOC_IAT & ~4095, 4096)
    _require(
        int.from_bytes(_read(pages, HEAP_GLOBAL), "little") == HEAP
        and int.from_bytes(_read(pages, ALLOC_IAT), "little") == IMPORT,
        "small path assignment heap globals differ",
    )
    _require(
        DATA <= allocation_result <= DATA + 16384 - 8,
        "small path assignment allocation result outside ordinary domain",
    )
    h = registers["ecx"]
    j = int.from_bytes(_read(pages, g + 4), "little")
    _require(
        h > 0 and j > 0 and h + 12 <= U32 and j + 12 <= U32,
        "small path assignment header extent wraps",
    )
    _require(_read(pages, h, 12) == bytes(12), "small path assignment destination is not empty")
    source_header = _read(pages, j, 12)
    o = int.from_bytes(source_header[:4], "little")
    end = int.from_bytes(source_header[4:8], "little")
    _require(
        o > 0 and o < end <= U32 and (end - o) % 8 == 0
        and 1 <= (end - o) // 8 <= 511,
        "small path assignment source count differs",
    )
    count = (end - o) // 8
    size = count * 8
    _require(
        allocation_result + size <= DATA + 16384,
        "small path assignment allocation extent differs",
    )
    _read(pages, o, size)
    _read(pages, allocation_result, size)
    touched = (
        (g - 96, g + 8),
        (h, h + 12),
        (j, j + 12),
        (o, o + size),
        (allocation_result, allocation_result + size),
    )
    globals_spans = (
        (HEAP_GLOBAL & ~4095, (HEAP_GLOBAL & ~4095) + 4096),
        (ALLOC_IAT & ~4095, (ALLOC_IAT & ~4095) + 4096),
    )
    _require(
        all(
            _disjoint(span, other)
            for i, span in enumerate(touched)
            for other in touched[i + 1 :]
        )
        and all(_disjoint(span, fixed) for span in touched for fixed in globals_spans)
        and _disjoint(stack_window, (DATA, DATA + 16384))
        and all(_disjoint(stack_window, fixed) for fixed in globals_spans),
        "small path assignment protected extents overlap",
    )
    code_pages = {
        (BASE + address) & ~4095
        for start, end in CODE_RANGES
        for address in range(start, end)
    }
    _require(
        not code_pages.intersection(pages), "small path assignment pages overlap selected code"
    )
    _require(
        return_address > 0
        and all(
            not (BASE + start <= return_address < BASE + end)
            for start, end in CODE_RANGES
        )
        and all(not (start <= return_address < end) for start, end in touched),
        "small path assignment return overlaps touched data or selected body",
    )
    _require(
        int.from_bytes(_read(pages, g), "little") == return_address,
        "small path assignment caller return differs",
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


def _allocation_packet_law(registers, pages, destination, continuation, stack_base, count):
    return _normalize(lambda: primitives._allocation_packet_law(
        registers, pages, destination, continuation, stack_base, count
    ))


def _scalar_packet_law(registers, xmm, pages, source, destination, continuation, count):
    return _normalize(lambda: primitives._scalar_packet_law(
        registers, xmm, pages, source, destination, continuation, count
    ))

OWNER_PREFIX = (
    0xC5BB0,
    0xC5BB1,
    0xC5BB3,
    0xC5BB4,
    0xC5BB5,
    0xC5BB8,
    0xC5BB9,
    0xC5BBA,
    0xC5BBC,
    0xC5BBE,
    0xC5BC4,
    0xC5BC6,
    0xC5BC9,
    0xC5BCB,
    0xC5BDD,
    0xC5BE0,
    0xC5BE2,
    0xC5BE4,
    0xC5BE6,
    0xC5BE8,
    0xC5BEB,
    0xC5BEE,
    0xC5BF1,
    0xC5BF3,
    0xC5BF6,
    0xC5C20,
    0xC5C23,
    0xC5C25,
    0xC5C28,
    0xC5C2A,
    0xC5C4C,
    0xC5C4E,
    0xC5C5C,
    0xC5C5F,
    0xC5C61,
    0xC5C63,
    0xC5C66,
    0xC5C67,
)
RESERVE_PREFIX = (
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
    0x9AC6A,
    0x9AC70,
    0x9AC72,
    0x9AC73,
)
RESERVE_SUFFIX = (
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
)
OWNER_MIDDLE = (
    0xC5C6C,
    0xC5C6E,
    0xC5C70,
    0xC5C71,
    0xC5C74,
    0xC5C75,
    0xC5C77,
    0xC5C79,
    0xC5C7C,
)
OWNER_SUFFIX = (
    0xC5C81,
    0xC5C84,
    0xC5C87,
    0xC5C89,
    0xC5C8A,
    0xC5C8B,
    0xC5C8C,
    0xC5C8E,
    0xC5C8F,
)


def frame_join(entry):
    _word(entry, "frame")
    _require(96 <= entry <= U32 - 8, "small path assignment frame wraps")
    return dict(
        parent=entry,
        reserve=entry - 28,
        allocation=entry - 48,
        heap=entry - 96,
        scalar=entry - 40,
        returned=entry + 8,
        protected_start=entry - 96,
        protected_end=entry + 8,
    )


def apply(*, pages, registers, xmm, return_address, entry_flags, allocation_result):
    """Normal selected assignment from one through 511 entries into a complete empty header.

    Inputs are installed pages/state. The supplied allocation response is a premise,
    not API execution or an ownership transition; source capacity is never read.
    """
    geometry, stack_base, count = _validate(
        pages, registers, xmm, return_address, entry_flags, allocation_result
    )
    g, h, j, o, d = (
        geometry[k]
        for k in (
            "entry",
            "destination_header",
            "source_header",
            "source",
            "destination",
        )
    )
    size = count * 8
    frame_join(g)
    memory, events, event = _event_law(pages)
    regs = dict(registers)
    boundaries = {
        "parent_entry": _boundary(
            regs, xmm, memory, events, BASE + 0xC5BB0, entry_flags, 0xFFFFFFFF
        )
    }
    for at, value in (
        (g - 4, registers["ebp"]),
        (g - 8, h),
        (g - 12, registers["ebx"]),
    ):
        event("write", at, value)
    event("read", g + 4, j)
    event("write", g - 16, registers["esi"])
    event("write", g - 20, registers["edi"])
    event("read", j, o)
    event("read", j + 4, o + size)
    event("read", h + 4, 0)
    event("read", h, 0)
    event("write", g - 8, 0)
    event("read", g + 4, j)
    event("read", h + 8, 0)
    event("read", j + 4, o + size)
    event("read", j, o)
    event("write", g - 24, count)
    event("write", g - 28, BASE + 0xC5C6C)
    regs.update(eax=count, ebx=j, ecx=h, edx=0, esi=count, edi=h, ebp=g - 4, esp=g - 28)
    boundaries["reserve_entry"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9AC40, primitives._test_flags(count), 0xC5
    )
    for at, value in ((g - 32, g - 4), (g - 36, count), (g - 40, h)):
        event("write", at, value)
    event("read", g - 24, count)
    for at in (h, h + 4, h + 8):
        event("write", at, 0)
    event("write", g - 44, count)
    event("write", g - 48, BASE + 0x9AC78)
    regs.update(esi=h, edi=count, ebp=g - 32, esp=g - 48)
    boundaries["allocation_entry"] = _boundary(
        regs, xmm, memory, events, BASE + 0x8A920, primitives._sub_flags(count, 0x1FFFFFFF), 0x8D5
    )
    allocated, imported = _allocation_packet_law(
        regs, _pages(memory), d, BASE + 0x9AC78, stack_base, count
    )
    imported["events"] = copy.deepcopy(events) + imported["events"]
    imported["xmm"] = dict(xmm)
    imported.update(entry_esp=g - 96, words=[BASE + 0x389463, HEAP, 0, size])
    events.extend(copy.deepcopy(allocated["events"]))
    _write(memory, stack_base, allocated["stack"])
    regs = dict(allocated["registers"])
    boundaries["allocation_return"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9AC78, allocated["flags"], 0x8D5
    )
    event("write", h, d)
    event("write", h + 4, d)
    event("read", h, d)
    event("write", h + 8, d + size)
    for at, value in (
        (g - 40, h),
        (g - 36, count),
        (g - 32, g - 4),
        (g - 28, BASE + 0xC5C6C),
    ):
        event("read", at, value)
    regs.update(eax=((d + size) & 0xFFFFFF00) | 1, edi=h, esi=count, ebp=g - 4, esp=g - 20)
    boundaries["reserve_return"] = _boundary(
        regs, xmm, memory, events, BASE + 0xC5C6C, allocated["flags"], 0x8D5
    )
    event("write", g - 24, d)
    event("read", g + 4, j)
    event("write", g - 28, j)
    event("write", g - 32, d)
    event("read", h, d)
    event("write", g - 36, d)
    event("read", j, o)
    event("read", j + 4, o + size)
    event("write", g - 40, BASE + 0xC5C81)
    regs.update(ecx=o, edx=o + size, esp=g - 40)
    boundaries["scalar_entry"] = _boundary(
        regs, xmm, memory, events, BASE + 0x8ABA0, 0, 0x8C5
    )
    copied = _scalar_packet_law(regs, xmm, _pages(memory), o, d, BASE + 0xC5C81, count)
    events.extend(copy.deepcopy(copied["events"]))
    for page, payload in copied["pages"].items():
        memory[page][:] = payload
    regs = dict(copied["registers"])
    boundaries["scalar_return"] = _boundary(
        regs, xmm, memory, events, BASE + 0xC5C81, 0x44, 0x8D5
    )
    event("write", h + 4, d + size)
    for at, value in (
        (g - 20, registers["edi"]),
        (g - 16, registers["esi"]),
        (g - 12, registers["ebx"]),
        (g - 4, registers["ebp"]),
        (g, return_address),
    ):
        event("read", at, value)
    regs.update(
        eax=h,
        edi=registers["edi"],
        esi=registers["esi"],
        ebx=registers["ebx"],
        ebp=registers["ebp"],
        esp=g + 8,
    )
    trace = (
        OWNER_PREFIX + RESERVE_PREFIX + ALLOCATION_TRACE + RESERVE_SUFFIX
        + OWNER_MIDDLE + primitives._scalar_trace(count) + OWNER_SUFFIX
    )
    _require(
        len(trace) == 142 + 10 * count and len(events) == 82 + 4 * count,
        "small path assignment source count differs",
    )
    return dict(
        geometry=geometry,
        registers=regs,
        xmm=dict(xmm),
        flags=_add_flags(g - 36, 16),
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
        pages=_pages(memory),
        events=events,
        trace_rvas=[f"0x{pc:08x}" for pc in trace],
        boundaries=boundaries,
        allocation_packet=allocated,
        scalar_packet=copied,
        imported=imported,
        source_snapshot=_read(pages, o, size),
    )
