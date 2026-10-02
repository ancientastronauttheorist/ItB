"""Selected two through31 byte copies into overlapping rightward destinations.

The actual cdecl words select the descending scalar CRT branch. This law has
no feature reads, imports, child calls, SIMD transfer, or direction-flag change.
"""

from __future__ import annotations

from src.observatory import native_movement_effect_record_default_semantics as memory

ANALYSIS_KIND = "pe_native_movement_memmove_backward_semantics"
SOURCE_PINS = {
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
}
BASE, U32, ENTRY = 0x400000, 0xFFFFFFFF, 0x36E580
REGISTERS, XMM = memory.REGISTERS, memory.XMM
BODY_PINS = {
    ENTRY: (
        1330,
        "8b0b052a9ad8d284940e5886d952cc89ebbcef586b2c46075afb6b4ce26dbc34",
    ),
}
_read, _write, _pages = memory._read, memory._write, memory._pages


class MemmoveBackwardError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise MemmoveBackwardError(message)


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
        "small backward copy immutable pages differ",
    )
    _require(
        type(registers) is dict
        and set(registers) == set(REGISTERS)
        and all(
            type(k) is str and type(v) is int and 0 <= v <= U32
            for k, v in registers.items()
        ),
        "small backward copy GPR schema differs",
    )
    _require(
        type(xmm) is dict
        and set(xmm) == set(XMM)
        and all(
            type(k) is str and type(v) is int and 0 <= v < 2**128
            for k, v in xmm.items()
        ),
        "small backward copy XMM schema differs",
    )
    _require(
        type(return_address) is int
        and 0 < return_address <= U32
        and type(entry_flags) is int
        and 0 <= entry_flags <= U32
        and entry_flags & ~0xAD7 == 0
        and entry_flags & 2 == 2,
        "small backward copy return or ordinary DF clear flags differ",
    )
    g = registers["esp"]
    _require(8 <= g and g + 16 <= U32, "small backward copy frame wraps")
    _read(pages, g - 8, 24)
    ret, d, o, n = (
        int.from_bytes(_read(pages, g + i, 4), "little") for i in (0, 4, 8, 12)
    )
    _require(
        ret == return_address and 2 <= n <= 31,
        "small backward copy caller words differ",
    )
    _require(
        0 < o < d < o + n and o + n <= U32 and d + n <= U32,
        "small backward copy overlapping rightward extents differ",
    )
    _read(pages, o, d + n - o)
    spans = ((g - 8, g + 16), (o, d + n))
    _require(
        g + 16 <= o or d + n <= g - 8,
        "small backward copy selected union overlaps stack",
    )
    _require(
        BASE + 0x36E000 not in pages,
        "small backward copy data pages overlap body code",
    )
    _require(
        all(not lo <= return_address < hi for lo, hi in spans)
        and not BASE + ENTRY <= return_address < BASE + 0x36EAF4,
        "small backward copy return overlaps selected data or body",
    )
    return g, d, o, n


def apply(*, pages, registers, xmm, return_address, entry_flags):
    try:
        return _apply(pages, registers, xmm, return_address, entry_flags)
    except MemmoveBackwardError:
        raise
    except Exception as exc:
        raise MemmoveBackwardError(str(exc)) from exc


def _apply(pages, registers, xmm, return_address, entry_flags):
    g, d, o, n = _validate(pages, registers, xmm, return_address, entry_flags)
    mutable = {p: bytearray(b) for p, b in pages.items()}
    events, trace = [], []
    source_snapshot = _read(pages, o, n)

    def pc(*rvas):
        trace.extend(f"0x{rva:08x}" for rva in rvas)

    def r(at, width=4):
        value = int.from_bytes(_read(mutable, at, width), "little")
        events.append(dict(access="read", address=at, width=width, value=value))
        return value

    def w(at, value, width=4):
        _write(mutable, at, value.to_bytes(width, "little"))
        events.append(dict(access="write", address=at, width=width, value=value))

    w(g - 4, registers["edi"])
    w(g - 8, registers["esi"])
    r(g + 8)
    r(g + 12)
    r(g + 4)
    pc(
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
        0x36E834,
        0x36E837,
        0x36E83A,
        0x36E83D,
        0x36E994,
        0x36E99A,
    )
    q, tail = divmod(n, 4)
    # Descending accesses read the actual evolving overlap, never regenerated
    # pages. Earlier higher writes cannot affect any later lower source read.
    for i in range(q):
        pc(0x36E99C, 0x36E99F, 0x36E9A2, 0x36E9A4, 0x36E9A6, 0x36E9A9, 0x36E9AF)
        offset = n - 4 * (i + 1)
        value = r(o + offset)
        _require(
            value == int.from_bytes(source_snapshot[offset : offset + 4], "little"),
            "small backward copy descending DWORD source differs",
        )
        w(d + offset, value)
    pc(0x36E9B1, 0x36E9B3)
    for i in range(tail):
        pc(0x36E9B5, 0x36E9B8, 0x36E9BB, 0x36E9BD, 0x36E9BF, 0x36E9C2)
        offset = tail - i - 1
        value = r(o + offset, 1)
        _require(
            value == source_snapshot[offset],
            "small backward copy descending byte source differs",
        )
        w(d + offset, value, 1)
    pc(0x36E9C4, 0x36E9C8, 0x36E9C9, 0x36E9CA)
    r(g + 4)
    r(g - 8)
    r(g - 4)
    r(g)
    # Independent direct last-writer law protects the whole overlapping union
    # and all ancestor bytes. Source overlap changes are legitimate D writes.
    final = {p: bytearray(b) for p, b in pages.items()}
    _write(final, g - 4, registers["edi"].to_bytes(4, "little"))
    _write(final, g - 8, registers["esi"].to_bytes(4, "little"))
    _write(final, d, source_snapshot)
    _require(_pages(mutable) == _pages(final), "small backward copy full pages differ")
    _require(
        len(trace) == 24 + 7 * q + 6 * tail and len(events) == 9 + 2 * q + 2 * tail,
        "small backward copy trace or access count differs",
    )
    return dict(
        geometry=dict(entry=g, source=o, destination=d, count=n),
        registers=dict(registers, eax=d, ecx=0, edx=n, esp=g + 4),
        xmm=dict(xmm),
        pages=_pages(mutable),
        events=events,
        trace_rvas=trace,
        flags=0x44,
        flag_mask=0x8D5 if tail else 0x8C5,
        df=0,
        endpoint=return_address,
        source_snapshot=source_snapshot,
    )
