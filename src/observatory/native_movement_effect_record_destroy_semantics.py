"""Actual-page inline movement record destruction with null or two-entry path.

Successful HeapFree is supplied for the nonnull path. No ownership, unmapping,
non-inline string, allocator failure or exception behavior is established.
"""

from __future__ import annotations
import copy
from src.observatory import native_vector_deallocation_conformance_joined as deallocator
from src.observatory import native_movement_empty_string_copy_semantics as string
from src.observatory.native_movement_path_clone2_semantics import _add_flags

BASE, U32 = 0x400000, 0xFFFFFFFF
HEAP_GLOBAL, FREE_IAT, HEAP, IMPORT, ERROR = (
    0x8B7634,
    0x7D621C,
    0x12345678,
    0x5000000,
    0x6000000,
)
REGISTERS, XMM = string.REGISTERS, string.XMM
_read, _write, _pages = string._read, string._write, string._pages
BODY_PINS = {
    0x10E2A0: (497, "641631ac31c522163cb141e846f21fa5e163ed176f042c3123762564c6d7d8ee"),
    0x7800: (91, "2d09033991193eea352dab418355232650d3aeb45906f909b384e0b662cd1ef6"),
    0x35785D: (5, "f45c1f23615da61aa6c903e18306f5628c975cfaf6027b37e45d2264c7ed477d"),
    0x36FB17: (5, "fafd106d4b0ce80368b3e080fb3be3b06582d8145fce2063305541cab5f65ea3"),
    0x389156: (58, "223079ea989dad987b5fdf47fc9c63d348f353dc2ab70257ae6dc53c62a9003c"),
}
SOURCE_PINS = dict(
    string.SOURCE_PINS,
    free_conformance=(deallocator.ANALYSIS_KIND, deallocator.SEALED_SHA256),
)
STRING_OFFSETS = (0x118, 0xF8, 0xE0, 0xA4, 0x80, 0x68, 0x50, 0x38)
STRING_SEGMENTS = tuple(
    tuple(0x10E000 + n for n in seq)
    for seq in (
        (
            0x2A0,
            0x2A1,
            0x2A3,
            0x2A9,
            0x2AA,
            0x2B0,
            0x2B3,
            0x2C3,
            0x2CA,
            0x2CE,
            0x2D5,
            0x2D9,
        ),
        (0x2DC, 0x2E2, 0x2E5, 0x2E8, 0x2F8, 0x2FF, 0x303, 0x30A, 0x30E),
        (0x311, 0x317, 0x31A, 0x31D, 0x32D, 0x334, 0x338, 0x33F, 0x343),
        (0x385, 0x38B, 0x391, 0x394, 0x3A4, 0x3AB, 0x3AF, 0x3B6, 0x3BA),
        (0x3BD, 0x3C3, 0x3C6, 0x3C9, 0x3D9, 0x3E0, 0x3E4, 0x3EB, 0x3EF),
        (0x3F2, 0x3F5, 0x3F8, 0x3FB, 0x40B, 0x412, 0x416, 0x41D, 0x421),
        (0x424, 0x427, 0x42A, 0x42D, 0x43D, 0x444, 0x448, 0x44F, 0x453),
        (0x456, 0x459, 0x45C, 0x46D, 0x474, 0x478, 0x47F, 0x48A, 0x48B, 0x48F, 0x490),
    )
)
PATH_PREFIX = (0x10E346, 0x10E34C, 0x10E34E)
PATH_CALL = (0x10E350, 0x10E356, 0x10E358, 0x10E35A, 0x10E35D, 0x10E35E, 0x10E35F)
PATH_SUFFIX = (0x10E364, 0x10E36E, 0x10E371, 0x10E37B)
FREE_TRACE = (
    30720,
    30721,
    30723,
    30726,
    30729,
    30731,
    30734,
    30736,
    30742,
    30746,
    30752,
    30797,
    30800,
    30801,
    3504221,
    3603223,
    3707222,
    3707224,
    3707225,
    3707227,
    3707231,
    3707233,
    3707236,
    3707238,
    3707244,
    3707250,
    3707252,
    3707278,
    3707279,
    30806,
    30809,
    30810,
)


class RecordDestroyError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise RecordDestroyError(message)


def _normalize(fn):
    try:
        return fn()
    except RecordDestroyError:
        raise
    except Exception as exc:
        raise RecordDestroyError(str(exc)) from exc


def _same_packet(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return set(a) == set(b) and all(
            any(type(k) is type(j) and k == j for j in b) and _same_packet(a[k], b[k])
            for k in a
        )
    if type(a) in (list, tuple):
        return len(a) == len(b) and all(_same_packet(x, y) for x, y in zip(a, b))
    return a == b


def _event_law(pages):
    memory = {p: bytearray(b) for p, b in pages.items()}
    events = []

    def event(access, address, value):
        if access == "write":
            _write(memory, address, value.to_bytes(4, "little"))
        else:
            _require(
                int.from_bytes(_read(memory, address, 4), "little") == value,
                "destroy free read differs",
            )
        events.append(dict(access=access, address=address, width=4, value=value))

    return memory, events, event


def _free_packet_law(regs, pages, pointer, stack_base):
    """Ordinary count2/stride8; exact8 fields against the unchanged generic law."""
    v = regs["esp"]
    memory, events, e = _event_law(pages)
    for access, address, value in (
        ("write", v - 4, regs["ebp"]),
        ("read", v + 8, 2),
        ("read", v + 12, 8),
        ("read", v + 12, 8),
        ("read", v + 4, pointer),
        ("write", v - 8, pointer),
        ("write", v - 12, BASE + 0x7856),
        ("write", v - 16, v - 4),
        ("read", v - 8, pointer),
        ("read", v - 8, pointer),
        ("write", v - 20, pointer),
        ("write", v - 24, 0),
        ("read", HEAP_GLOBAL, HEAP),
        ("write", v - 28, HEAP),
        ("read", FREE_IAT, IMPORT),
        ("write", v - 32, BASE + 0x389172),
        ("read", v - 16, v - 4),
        ("read", v - 12, BASE + 0x7856),
        ("read", v - 4, regs["ebp"]),
        ("read", v, deallocator.RETURN),
    ):
        # The primitive's canonical outer RET word is rebound only after the
        # complete source model comparison. All stack/page bytes are actual.
        if address == v and access == "read":
            events.append(dict(access=access, address=address, width=4, value=value))
        else:
            e(access, address, value)
    wanted = dict(
        registers=dict(regs, eax=1, ecx=0xA0000001, edx=0xB0000001, esp=v + 4),
        flags=_add_flags(v - 8, 4),
        flag_mask=0x8D5,
        events=events,
        stack=_read(memory, stack_base, 8192),
        error=pages[ERROR],
        stop=deallocator.RETURN,
        protocol=dict(
            returned=True, result=1, next_kind=None, error_cell=None, last_error=None
        ),
    )
    child = _normalize(
        lambda: deallocator._expected(
            dict(
                pointer=pointer,
                count=2,
                stride=8,
                metadata=None,
                responses=[dict(kind="heap_free", eax=1)],
                heap=HEAP,
            ),
            dict(regs),
            _read(pages, stack_base, 8192),
            pages[ERROR],
            stack_base=stack_base,
        )
    )
    _require(_same_packet(child, wanted), "movement free primitive differs")
    _require(
        int.from_bytes(_read(pages, v, 4), "little") == BASE + 0x10E364,
        "movement free installed continuation differs",
    )
    wanted["events"][-1]["value"] = BASE + 0x10E364
    wanted["stop"] = BASE + 0x10E364
    return wanted


def _validate(pages, registers, xmm, return_address, entry_flags):
    _require(
        type(pages) is dict
        and bool(pages)
        and all(
            type(p) is int
            and 0 <= p <= 0xFFFFF000
            and p % 4096 == 0
            and type(b) is bytes
            and len(b) == 4096
            for p, b in pages.items()
        ),
        "invalid destroy immutable pages",
    )
    _require(
        type(registers) is dict
        and set(registers) == set(REGISTERS)
        and all(
            type(k) is str and type(v) is int and 0 <= v <= U32
            for k, v in registers.items()
        ),
        "invalid destroy GPR schema",
    )
    _require(
        type(xmm) is dict
        and set(xmm) == set(XMM)
        and all(
            type(k) is str and type(v) is int and 0 <= v < 2**128
            for k, v in xmm.items()
        ),
        "invalid destroy XMM schema",
    )
    _require(
        type(entry_flags) is int
        and 0 <= entry_flags <= U32
        and entry_flags & ~0xAD7 == 0
        and entry_flags & 2 == 2,
        "invalid destroy ordinary DF-clear flags",
    )
    g, r = registers["esp"], registers["ecx"]
    _require(
        56 <= g and g + 4 <= U32 and 0 < r and r + 308 <= U32,
        "destroy frame or record extent differs",
    )
    o, e, c = (
        int.from_bytes(_read(pages, r + n, 4), "little") for n in (0xCC, 0xD0, 0xD4)
    )
    owned = o != 0
    _require(
        (not owned and e == c == 0) or (0 < o and o + 16 <= U32 and e == c == o + 16),
        "destroy path must be null or ordinary count2 capacity2",
    )
    for off in STRING_OFFSETS:
        _require(
            int.from_bytes(_read(pages, r + off + 20, 4), "little") == 15
            and int.from_bytes(_read(pages, r + off + 16, 4), "little") <= 15,
            "destroy source inline string differs",
        )
    spans = [(g - (56 if owned else 8), g + 4), (r, r + 308)]
    stack_base = min((g - 56) & ~4095, 0xFFFFE000)
    if owned:
        spans.append((o, o + 16))
        _read(pages, stack_base, 8192)
        _read(pages, ERROR, 4096)
        for at, value in ((HEAP_GLOBAL, HEAP), (FREE_IAT, IMPORT)):
            _require(
                int.from_bytes(_read(pages, at, 4), "little") == value,
                "destroy supplied heap interface differs",
            )
        for left, right in spans:
            _require(
                all(
                    right <= lo or hi <= left
                    for lo, hi in (
                        (ERROR, ERROR + 4096),
                        (HEAP_GLOBAL & ~4095, (HEAP_GLOBAL & ~4095) + 4096),
                        (FREE_IAT & ~4095, (FREE_IAT & ~4095) + 4096),
                    )
                ),
                "destroy data overlaps error or interface pages",
            )
        _require(
            stack_base + 8192 <= ERROR or ERROR + 4096 <= stack_base,
            "destroy stack window overlaps error page",
        )
    for i, (left, right) in enumerate(spans):
        _read(pages, left, right - left)
        _require(
            all(right <= lo or hi <= left for lo, hi in spans[i + 1 :]),
            "destroy data spans overlap",
        )
    codepages = {
        (BASE + a + i) & ~4095 for a, (n, h) in BODY_PINS.items() for i in range(n)
    }
    _require(
        not codepages.intersection(pages), "destroy data pages overlap selected code"
    )
    _require(
        type(return_address) is int
        and 0 < return_address <= U32
        and all(not (lo <= return_address < hi) for lo, hi in spans)
        and all(
            not (BASE + a <= return_address < BASE + a + n)
            for a, (n, h) in BODY_PINS.items()
        ),
        "destroy return overlaps data or code",
    )
    _require(
        int.from_bytes(_read(pages, g, 4), "little") == return_address,
        "destroy installed return differs",
    )
    return g, r, o, stack_base


def apply(*, pages, registers, xmm, return_address, entry_flags):
    return _normalize(
        lambda: _apply(pages, registers, xmm, return_address, entry_flags)
    )


def _apply(pages, registers, xmm, return_address, entry_flags):
    g, r, o, stack_base = _validate(pages, registers, xmm, return_address, entry_flags)
    memory = {p: bytearray(b) for p, b in pages.items()}
    events, boundaries = [], []
    regs = dict(registers)
    free_packet, imported = None, None

    def event(access, address, value, width=4):
        if access == "write":
            _write(memory, address, value.to_bytes(width, "little"))
        else:
            _require(
                int.from_bytes(_read(memory, address, width), "little") == value,
                "destroy expected read differs",
            )
        events.append(dict(access=access, address=address, width=width, value=value))

    def boundary(name, endpoint, flags, mask):
        boundaries.append(
            dict(
                name=name,
                registers=dict(regs),
                xmm=dict(xmm),
                pages=_pages(memory),
                events=copy.deepcopy(events),
                flags=flags,
                flag_mask=mask,
                df=0,
                endpoint=endpoint,
            )
        )

    event("write", g - 4, registers["esi"])
    event("read", r + 0x12C, 15)
    event("write", g - 8, registers["edi"])
    regs.update(esi=r, edi=r + 0x118, eax=15, esp=g - 8)

    def inline(index):
        off = STRING_OFFSETS[index]
        if index != 0:
            event("read", r + off + 20, 15)
        event("write", r + off + 20, 15)
        event("read", r + off + 20, 15)
        event("write", r + off + 16, 0)
        if index == 7:
            event("read", g - 8, registers["edi"])
        event("write", r + off, 0, 1)
        regs.update(eax=15)
        if index != 7:
            regs.update(edi=r + off)

    inline(0)
    inline(1)
    inline(2)
    event("read", r + 0xCC, o)
    regs.update(ecx=o)
    if o:
        event("read", r + 0xD4, o + 16)
        for at, value in (
            (g - 12, 8),
            (g - 16, 2),
            (g - 20, o),
            (g - 24, BASE + 0x10E364),
        ):
            event("write", at, value)
        regs.update(eax=2, esp=g - 24)
        boundary("free_entry", BASE + 0x7800, 0, 0xC5)
        prefix = copy.deepcopy(events)
        free_packet = _free_packet_law(regs, _pages(memory), o, stack_base)
        # Imported success preserves every page and XMM. The wrapper's actual
        # volatile GPR and stack state is predicted at its installed call frame.
        importmemory = {p: bytearray(b) for p, b in memory.items()}
        for row in free_packet["events"][:16]:
            if row["access"] == "write":
                _write(importmemory, row["address"], row["value"].to_bytes(4, "little"))
        v = g - 24
        imported = dict(
            registers=dict(regs, eax=0x1FFFFFFF, ecx=o, edx=7, ebp=v - 16, esp=v - 32),
            xmm=dict(xmm),
            pages=_pages(importmemory),
            events=prefix + copy.deepcopy(free_packet["events"][:16]),
            flags=(int((o & 255).bit_count() % 2 == 0) << 2) | ((o >> 31) << 7),
            flag_mask=0x8C5,
            df=0,
            endpoint=IMPORT,
            entry_esp=v - 32,
            words=[BASE + 0x389172, HEAP, 0, o],
        )
        events.extend(copy.deepcopy(free_packet["events"]))
        _write(memory, stack_base, free_packet["stack"])
        regs = dict(free_packet["registers"])
        boundary("free_return", BASE + 0x10E364, free_packet["flags"], 0x8D5)
        for off in (0xCC, 0xD0, 0xD4):
            event("write", r + off, 0)
        regs["esp"] = g - 8
    for i in range(3, 8):
        inline(i)
    event("read", g - 4, registers["esi"])
    event("read", g, return_address)
    trace = []
    for i, segment in enumerate(STRING_SEGMENTS):
        trace.extend(segment)
        if i == 2:
            trace.extend(PATH_PREFIX)
            if o:
                trace.extend(PATH_CALL + FREE_TRACE + PATH_SUFFIX)
    _require(
        len(trace) == (123 if o else 80) and len(events) == (74 if o else 46),
        "destroy selected path count differs",
    )
    return dict(
        record_address=r,
        record_bytes=_read(memory, r, 308),
        path_pointer=o,
        registers=dict(
            registers,
            eax=15,
            ecx=(0xA0000001 if o else 0),
            edx=(0xB0000001 if o else registers["edx"]),
            esp=g + 4,
        ),
        xmm=dict(xmm),
        pages=_pages(memory),
        events=events,
        trace_rvas=[f"0x{pc:08x}" for pc in trace],
        boundaries=boundaries,
        free_packet=copy.deepcopy(free_packet),
        imported=imported,
        flags=0x85,
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
    )
