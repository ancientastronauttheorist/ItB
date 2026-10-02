"""Selected external assignment into an inline capacity-fifteen string.

The actual caller supplies source and length zero through fifteen. Positive
sources are disjoint from the complete string object. Zero-length pointers are
unread but must select the actual external prefix. No allocator or alias child
is admitted; the positive scalar memcpy packet is independently reconstructed.
"""

from __future__ import annotations

import copy
from src.observatory import native_movement_effect_record_default_semantics as memory
from src.observatory import native_movement_small_memcpy_semantics as memcpy

ANALYSIS_KIND = "pe_native_movement_inline_string_assign_semantics"
BASE, U32, ENTRY = 0x400000, 0xFFFFFFFF, 0x7FD0
REGISTERS, XMM = memory.REGISTERS, memory.XMM
BODY_PINS = {
    ENTRY: (245, "c49f0e24bd27ed5495ceddc13536ca6fbe85d8c97f207db817ce0642b8b01906"),
    0x3703E0: (
        1330,
        "027f9747b24b79e7aa5a3511ddfd2890a8d50a72072ac6c7df83959091aa9ec5",
    ),
}
# The CRT body is a sparse atlas concatenation. Its summed byte count above is
# an identity witness, not a contiguous range; this envelope protects all sites.
CODE_EXTENTS = ((BASE + ENTRY, BASE + ENTRY + 245), (BASE + 0x3703E0, BASE + 0x370954))
SOURCE_PINS = dict(memory.SOURCE_PINS)
for _name, _identity in memcpy.SOURCE_PINS.items():
    if _name in SOURCE_PINS and SOURCE_PINS[_name] != _identity:
        raise ValueError("inline assignment source identity conflicts")
    SOURCE_PINS[_name] = _identity
_read, _write, _pages = memory._read, memory._write, memory._pages


class InlineStringAssignError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise InlineStringAssignError(message)


def _same(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return (
            len(actual) == len(expected)
            and all(
                any(type(k) is type(e) and k == e for e in expected) for k in actual
            )
            and all(k in actual and _same(actual[k], v) for k, v in expected.items())
        )
    if type(expected) in (list, tuple):
        return len(actual) == len(expected) and all(
            _same(a, e) for a, e in zip(actual, expected)
        )
    return actual == expected


def _logic(value):
    return (
        (4 if (value & 255).bit_count() % 2 == 0 else 0)
        | (0x40 if value == 0 else 0)
        | (0x80 if value & 0x80000000 else 0)
    )


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
        "inline assignment immutable pages differ",
    )
    _require(
        type(registers) is dict
        and set(registers) == set(REGISTERS)
        and all(
            type(k) is str and type(v) is int and 0 <= v <= U32
            for k, v in registers.items()
        ),
        "inline assignment GPR schema differs",
    )
    _require(
        type(xmm) is dict
        and set(xmm) == set(XMM)
        and all(
            type(k) is str and type(v) is int and 0 <= v < 2**128
            for k, v in xmm.items()
        ),
        "inline assignment XMM schema differs",
    )
    _require(
        type(return_address) is int
        and 0 < return_address <= U32
        and type(entry_flags) is int
        and 0 <= entry_flags <= U32
        and entry_flags & ~0xAD7 == 0
        and entry_flags & 2 == 2,
        "inline assignment return or ordinary DF-clear flags differ",
    )
    g, d = registers["esp"], registers["ecx"]
    _require(
        40 <= g and g + 12 <= U32 and 0 < d and d + 24 <= U32,
        "inline assignment frame or string wraps",
    )
    ret, o, n = (int.from_bytes(_read(pages, g + i, 4), "little") for i in (0, 4, 8))
    _require(ret == return_address and n <= 15, "inline assignment caller words differ")
    old = int.from_bytes(_read(pages, d + 16, 4), "little")
    _require(
        old <= 15 and int.from_bytes(_read(pages, d + 20, 4), "little") == 15,
        "inline assignment destination is not inline capacity fifteen",
    )
    _require(o == 0 or o < d or d + old <= o, "inline assignment selects alias child")
    spans = [(g - 40, g + 12), (d, d + 24)]
    if n:
        _require(
            o > 0 and o + n <= U32, "inline assignment positive source wraps or null"
        )
        spans.append((o, o + n))
    for i, (lo, hi) in enumerate(spans):
        _read(pages, lo, hi - lo)
        _require(
            all(hi <= a or z <= lo for a, z in spans[i + 1 :]),
            "inline assignment selected spans overlap",
        )
        _require(
            all(hi <= a or z <= lo for a, z in CODE_EXTENTS),
            "inline assignment data overlaps selected code",
        )
    _require(
        all(not lo <= return_address < hi for lo, hi in spans)
        and all(not a <= return_address < z for a, z in CODE_EXTENTS),
        "inline assignment return overlaps selected data or code",
    )
    code_pages = {
        p
        for lo, hi in CODE_EXTENTS
        for p in range(lo & ~4095, ((hi - 1) & ~4095) + 4096, 4096)
    }
    _require(
        not code_pages.intersection(pages), "inline assignment data pages overlap code"
    )
    return g, d, o, n, old


def _memcpy_law(pages, registers, xmm, source, destination, count):
    """Independent complete eleven-field prediction at actual installed frame."""
    c = registers["esp"]
    q, tail = divmod(count, 4)
    snapshot = _read(pages, source, count)
    mutable = {p: bytearray(b) for p, b in pages.items()}
    events = []
    trace = []

    def pcs(*rvas):
        trace.extend(f"0x{rva:08x}" for rva in rvas)

    def event(kind, at, width, value):
        if kind == "write":
            _write(mutable, at, value.to_bytes(width, "little"))
        else:
            _require(
                int.from_bytes(_read(mutable, at, width), "little") == value,
                "inline assignment primitive expected read differs",
            )
        events.append(dict(access=kind, address=at, width=width, value=value))

    event("write", c - 4, 4, registers["edi"])
    event("write", c - 8, 4, registers["esi"])
    for at, value in ((c + 8, source), (c + 12, count), (c + 4, destination)):
        event("read", at, 4, value)
    pcs(
        0x3703E0,
        0x3703E1,
        0x3703E2,
        0x3703E6,
        0x3703EA,
        0x3703EE,
        0x3703F0,
        0x3703F2,
        0x3703F4,
        0x3703F6,
    )
    if destination > source:
        pcs(0x3703F8, 0x3703FA)
    pcs(0x370400, 0x370403, 0x3708DB, 0x3708DE, 0x3708E0, 0x3708E2, 0x3708E5)
    for i in range(q):
        pcs(0x3708E7, 0x3708E9, 0x3708EB, 0x3708EE, 0x3708F1, 0x3708F4)
        value = int.from_bytes(snapshot[4 * i : 4 * i + 4], "little")
        event("read", source + 4 * i, 4, value)
        event("write", destination + 4 * i, 4, value)
    pcs(0x3708F6, 0x3708F8, 0x3708FB)
    for i in range(tail):
        pcs(0x3708FD, 0x3708FF, 0x370901, 0x370902, 0x370903, 0x370904)
        value = snapshot[4 * q + i]
        event("read", source + 4 * q + i, 1, value)
        event("write", destination + 4 * q + i, 1, value)
    if tail:
        pcs(0x370906, 0x37090D)
    pcs(0x370910, 0x370914, 0x370915, 0x370916)
    for at, value in (
        (c + 4, destination),
        (c - 8, registers["esi"]),
        (c - 4, registers["edi"]),
        (c, BASE + 0x8091),
    ):
        event("read", at, 4, value)
    final_pages = dict(pages)
    direct = {p: bytearray(b) for p, b in final_pages.items()}
    _write(direct, c - 4, registers["edi"].to_bytes(4, "little"))
    _write(direct, c - 8, registers["esi"].to_bytes(4, "little"))
    _write(direct, destination, snapshot)
    _require(
        _same(_pages(mutable), _pages(direct)),
        "inline assignment primitive page law differs",
    )
    return dict(
        geometry=dict(entry=c, source=source, destination=destination, count=count),
        registers=dict(
            registers,
            eax=destination,
            ecx=0,
            edx=int.from_bytes(snapshot[4 * (q - 1) : 4 * q], "little") if q else count,
            esp=c + 4,
        ),
        xmm=dict(xmm),
        pages=_pages(direct),
        events=events,
        trace_rvas=trace,
        flags=0x44,
        flag_mask=0x8D5 if tail else 0x8C5,
        df=0,
        endpoint=BASE + 0x8091,
        source_snapshot=snapshot,
    )


def apply(*, pages, registers, xmm, return_address, entry_flags):
    """Consume actual pages; return detached full selected owner and child state."""
    try:
        return _apply(pages, registers, xmm, return_address, entry_flags)
    except InlineStringAssignError:
        raise
    except Exception as exc:
        raise InlineStringAssignError(str(exc)) from exc


def _apply(pages, registers, xmm, return_address, entry_flags):
    g, d, o, n, old = _validate(pages, registers, xmm, return_address, entry_flags)
    mutable = {p: bytearray(b) for p, b in pages.items()}
    events, trace, boundaries = [], [], {}
    regs = dict(registers)
    source_snapshot = _read(pages, o, n) if n else b""
    packet = None

    def pcs(*rvas):
        trace.extend(f"0x{rva:08x}" for rva in rvas)

    def event(kind, at, width, value):
        if kind == "write":
            _write(mutable, at, value.to_bytes(width, "little"))
        else:
            _require(
                int.from_bytes(_read(mutable, at, width), "little") == value,
                "inline assignment actual read differs",
            )
        events.append(dict(access=kind, address=at, width=width, value=value))

    def boundary(endpoint, flags, mask):
        return dict(
            registers=dict(regs),
            xmm=dict(xmm),
            pages=_pages(mutable),
            events=copy.deepcopy(events),
            flags=flags,
            flag_mask=mask,
            df=0,
            endpoint=endpoint,
        )

    for access, at, value in (
        ("write", g - 4, registers["ebp"]),
        ("write", g - 8, registers["ebx"]),
        ("read", g + 4, o),
        ("write", g - 12, registers["esi"]),
    ):
        event(access, at, 4, value)
    regs.update(ebp=g - 4, ebx=o, esi=d, esp=g - 12)
    pcs(0x7FD0, 0x7FD1, 0x7FD3, 0x7FD4, 0x7FD7, 0x7FD8, 0x7FDA, 0x7FDC)
    if o:
        event("read", d + 20, 4, 15)
        regs.update(ecx=15, eax=d)
        pcs(0x7FDE, 0x7FE1, 0x7FE4, 0x7FEA, 0x7FEC, 0x7FEE)
        if o >= d:
            event("read", d + 16, 4, old)
            regs.update(edx=d, eax=d + old)
            pcs(0x7FF0, 0x7FF3, 0x7FF9, 0x7FFB, 0x7FFE, 0x8000, 0x8002)
    event("write", g - 16, 4, registers["edi"])
    event("read", g + 8, 4, n)
    event("read", d + 20, 4, 15)
    regs.update(edi=n, esp=g - 16)
    pcs(0x8035, 0x8036, 0x8039, 0x803C, 0x803E, 0x8041, 0x805C, 0x805E)
    if n:
        event("read", d + 20, 4, 15)
        pcs(0x8052, 0x8056, 0x8083, 0x8085, 0x8087)
        regs["eax"] = d
        for at, value in (
            (g - 20, n),
            (g - 24, o),
            (g - 28, d),
            (g - 32, BASE + 0x8091),
        ):
            event("write", at, 4, value)
        regs["esp"] = g - 32
        pcs(0x8089, 0x808A, 0x808B, 0x808C)
        boundaries["memcpy_entry"] = boundary(BASE + 0x3703E0, _logic(n), 0x8C5)
        primitive_pages = _pages(mutable)
        wanted = _memcpy_law(primitive_pages, dict(regs), xmm, o, d, n)
        child = memcpy.apply(
            pages=primitive_pages,
            registers=dict(regs),
            xmm=dict(xmm),
            return_address=BASE + 0x8091,
            entry_flags=(entry_flags & ~0x8D5) | _logic(n),
        )
        _require(
            _same(child, wanted), "inline assignment complete memcpy packet differs"
        )
        packet = copy.deepcopy(wanted)
        prefix = copy.deepcopy(events)
        events = prefix + copy.deepcopy(wanted["events"])
        trace.extend(wanted["trace_rvas"])
        mutable = {p: bytearray(b) for p, b in wanted["pages"].items()}
        regs = dict(wanted["registers"])
        boundaries["memcpy_return"] = boundary(
            BASE + 0x8091, wanted["flags"], wanted["flag_mask"]
        )
        regs["esp"] = g - 16
        pcs(0x8091, 0x8094, 0x8098, 0x809B, 0x80AC, 0x80AE)
        event("read", d + 20, 4, 15)
        event("write", d + 16, 4, n)
        event("write", d + n, 1, 0)
        for at, value in (
            (g - 16, registers["edi"]),
            (g - 12, registers["esi"]),
            (g - 8, registers["ebx"]),
            (g - 4, registers["ebp"]),
            (g, return_address),
        ):
            event("read", at, 4, value)
        pcs(0x80B2, 0x80B3, 0x80B5, 0x80B6, 0x80B7, 0x80B8)
    else:
        event("read", d + 20, 4, 15)
        event("write", d + 16, 4, 0)
        pcs(0x8060, 0x8064, 0x8067, 0x8077, 0x8079, 0x807A, 0x807B, 0x807C)
        for at, value in (
            (g - 16, registers["edi"]),
            (g - 12, registers["esi"]),
            (g - 8, registers["ebx"]),
        ):
            event("read", at, 4, value)
        event("write", d, 1, 0)
        event("read", g - 4, 4, registers["ebp"])
        event("read", g, 4, return_address)
        pcs(0x807F, 0x8080)
    final_registers = dict(
        registers, eax=d, ecx=regs["ecx"], edx=regs["edx"], esp=g + 12
    )
    direct = {p: bytearray(b) for p, b in pages.items()}
    for at, value in (
        (g - 4, registers["ebp"]),
        (g - 8, registers["ebx"]),
        (g - 12, registers["esi"]),
        (g - 16, registers["edi"]),
    ):
        _write(direct, at, value.to_bytes(4, "little"))
    if n:
        for at, value in (
            (g - 20, n),
            (g - 24, o),
            (g - 28, d),
            (g - 32, BASE + 0x8091),
            (g - 36, n),
            (g - 40, d),
        ):
            _write(direct, at, value.to_bytes(4, "little"))
        _write(direct, d, source_snapshot)
    _write(direct, d + 16, n.to_bytes(4, "little"))
    _write(direct, d + n, bytes(1))
    _require(
        _same(_pages(mutable), _pages(direct)),
        "inline assignment full owner page law differs",
    )
    _require(
        not n or _read(direct, o, n) == source_snapshot,
        "inline assignment source bytes changed",
    )
    return dict(
        geometry=dict(entry=g, source=o, destination=d, count=n, previous_length=old),
        registers=final_registers,
        xmm=dict(xmm),
        pages=_pages(direct),
        events=events,
        trace_rvas=trace,
        flags=0x85,
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
        source_snapshot=source_snapshot,
        memcpy_packet=copy.deepcopy(packet),
        boundaries=copy.deepcopy(boundaries),
    )
