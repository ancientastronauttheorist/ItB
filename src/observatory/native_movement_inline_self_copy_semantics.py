"""Selected inline self-substring copy through the actual erase continuation.

The same object is both receiver and source. Its original snapshot is retained
as evidence; the selected in-place page changes are modeled explicitly.
"""

from __future__ import annotations

import copy

from src.observatory import native_movement_inline_string_erase_semantics as erase
from src.observatory import native_movement_effect_record_default_semantics as memory

ANALYSIS_KIND = "pe_native_movement_inline_self_copy_semantics"
BASE, U32, ENTRY = 0x400000, 0xFFFFFFFF, 0x80D0
REGISTERS, XMM = memory.REGISTERS, memory.XMM
_read, _write, _pages = memory._read, memory._write, memory._pages
SOURCE_PINS = dict(erase.SOURCE_PINS)
BODY_PINS = dict(erase.BODY_PINS)
BODY_PINS[ENTRY] = (
    288,
    "062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333",
)


class InlineSelfCopyError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise InlineSelfCopyError(message)


def _logic(n):
    return (4 if (n & 255).bit_count() % 2 == 0 else 0) | (0x40 if n == 0 else 0)


def _packet_same(actual, expected):
    """Complete typed join, with canonical trace labels explicitly trusted."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        if {(type(k), k) for k in actual} != {(type(k), k) for k in expected}:
            return False
        for key, value in expected.items():
            if key == "trace_rvas":
                rows = actual[key]
                if not (
                    type(rows) is list
                    and len(rows) == len(value)
                    and all(
                        type(t) is str
                        and len(t) == 10
                        and t[:2] == "0x"
                        and all(ch in "0123456789abcdef" for ch in t[2:])
                        for t in rows
                    )
                ):
                    return False
            elif not _packet_same(actual[key], value):
                return False
        return True
    if type(expected) in (list, tuple):
        return len(actual) == len(expected) and all(
            _packet_same(a, b) for a, b in zip(actual, expected)
        )
    return actual == expected


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
        "inline self copy immutable pages differ",
    )
    _require(
        type(registers) is dict
        and set(registers) == set(REGISTERS)
        and all(
            type(k) is str and type(v) is int and 0 <= v <= U32
            for k, v in registers.items()
        ),
        "inline self copy GPR schema differs",
    )
    _require(
        type(xmm) is dict
        and set(xmm) == set(XMM)
        and all(
            type(k) is str and type(v) is int and 0 <= v < 2**128
            for k, v in xmm.items()
        ),
        "inline self copy XMM schema differs",
    )
    _require(
        type(return_address) is int
        and 0 < return_address <= U32
        and type(entry_flags) is int
        and 0 <= entry_flags <= U32
        and entry_flags & ~0xAD7 == 0
        and entry_flags & 2 == 2,
        "inline self copy return or ordinary flags differ",
    )
    g, h = registers["esp"], registers["ecx"]
    _require(
        68 <= g and g + 16 <= U32 and 0 < h and h + 24 <= U32,
        "inline self copy frame or object wraps",
    )
    _read(pages, g - 68, 84)
    _read(pages, h, 24)
    ret, source, off, requested = (
        int.from_bytes(_read(pages, g + i, 4), "little") for i in (0, 4, 8, 12)
    )
    length = int.from_bytes(_read(pages, h + 16, 4), "little")
    _require(
        ret == return_address
        and source == h
        and length <= 15
        and off <= length
        and int.from_bytes(_read(pages, h + 20, 4), "little") == 15,
        "inline self copy caller size capacity or identity differs",
    )
    spans = ((g - 68, g + 16), (h, h + 24))
    _require(
        g + 16 <= h or h + 24 <= g - 68,
        "inline self copy selected stack and object overlap",
    )
    _require(
        not ({0x408000, 0x76E000} & set(pages)),
        "inline self copy data overlaps selected code pages",
    )
    _require(
        all(not lo <= return_address < hi for lo, hi in spans)
        and not 0x4080D0 <= return_address < 0x4081F0
        and not 0x408410 <= return_address < 0x4084A9
        and not 0x76E580 <= return_address < 0x76EAF4,
        "inline self copy return overlaps selected data or body",
    )
    return g, h, length, off, requested, min(requested, length - off)


def _erase_law(packet):
    """Independent complete erase owner and scalar child equations at E."""
    initial = packet["registers"]
    e, h = initial["esp"], initial["ecx"]
    off = int.from_bytes(_read(packet["pages"], e + 8, 4), "little")
    length = int.from_bytes(_read(packet["pages"], h + 16, 4), "little")
    n = length - off
    mutable = {p: bytearray(b) for p, b in packet["pages"].items()}
    events, trace, states = [], [], []
    nested = None
    regs = dict(
        initial, ebp=e - 4, esi=h, edi=length, ecx=0, edx=off, eax=length, esp=e - 12
    )

    def pc(*rvas):
        trace.extend(f"0x{rva:08x}" for rva in rvas)

    def r(at, width=4):
        v = int.from_bytes(_read(mutable, at, width), "little")
        events.append(dict(access="read", address=at, width=width, value=v))
        return v

    def w(at, value, width=4):
        _write(mutable, at, value.to_bytes(width, "little"))
        events.append(dict(access="write", address=at, width=width, value=value))

    def state(phase, endpoint, flags, mask):
        states.append(
            dict(
                registers=dict(regs),
                xmm=dict(packet["xmm"]),
                pages=_pages(mutable),
                events=copy.deepcopy(events),
                flags=flags,
                flag_mask=mask,
                df=0,
                endpoint=endpoint,
                phase=phase,
            )
        )

    w(e - 4, initial["ebp"])
    w(e - 8, initial["esi"])
    r(e + 4)
    w(e - 12, initial["edi"])
    r(h + 16)
    r(e + 8)
    pc(
        0x8410,
        0x8411,
        0x8413,
        0x8414,
        0x8416,
        0x8419,
        0x841A,
        0x841D,
        0x841F,
        0x8421,
        0x8424,
        0x8426,
        0x8428,
        0x842A,
    )
    if n == 0:
        pc(0x842C, 0x842F, 0x8433, 0x8443, 0x8445, 0x8446, 0x8447, 0x844B, 0x844C)
        w(h + 16, 0)
        r(h + 20)
        r(e - 12)
        r(e - 8)
        w(h, 0, 1)
        r(e - 4)
        r(e)
        final_flags, mask = 0x85, 0x8D5
    elif off == 0:
        pc(0x844F, 0x8451, 0x8497, 0x8498, 0x849A, 0x849B, 0x849C)
        for at in (e - 12, e - 8, e - 4, e):
            r(at)
        final_flags, mask = 0x44, 0x8C5
    else:
        pc(
            0x844F,
            0x8451,
            0x8453,
            0x8457,
            0x845D,
            0x845F,
            0x8461,
            0x8462,
            0x8465,
            0x8467,
            0x8469,
            0x846B,
            0x846C,
            0x846F,
            0x8470,
            0x8471,
        )
        r(h + 20)
        w(e - 16, initial["ebx"])
        for at, value in (
            (e - 20, n),
            (e - 24, h + off),
            (e - 28, h),
            (e - 32, 0x408476),
        ):
            w(at, value)
        regs.update(ebx=h, edi=n, eax=h + off, esp=e - 32)
        state("entry", 0x76E580, _logic(n), 0x8D5)
        c = e - 32
        entry_pages, entry_regs = _pages(mutable), dict(regs)
        original = _read(entry_pages, h + off, n)
        scalar_events, scalar_trace = [], []

        def sr(at, width=4):
            v = int.from_bytes(_read(mutable, at, width), "little")
            scalar_events.append(dict(access="read", address=at, width=width, value=v))
            return v

        def sw(at, value, width=4):
            _write(mutable, at, value.to_bytes(width, "little"))
            scalar_events.append(
                dict(access="write", address=at, width=width, value=value)
            )

        sw(c - 4, entry_regs["edi"])
        sw(c - 8, entry_regs["esi"])
        for at in (c + 8, c + 12, c + 4):
            sr(at)
        scalar_trace.extend(
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
                0x36E5A0,
                0x36E5A3,
                0x36EA7B,
                0x36EA7E,
                0x36EA80,
                0x36EA82,
                0x36EA85,
            )
        )
        q, tail = divmod(n, 4)
        for i in range(q):
            scalar_trace.extend(
                (0x36EA87, 0x36EA89, 0x36EA8B, 0x36EA8E, 0x36EA91, 0x36EA94)
            )
            sw(h + 4 * i, sr(h + off + 4 * i))
        scalar_trace.extend((0x36EA96, 0x36EA98, 0x36EA9B))
        for i in range(tail):
            scalar_trace.extend(
                (0x36EA9D, 0x36EA9F, 0x36EAA1, 0x36EAA2, 0x36EAA3, 0x36EAA4)
            )
            sw(h + 4 * q + i, sr(h + off + 4 * q + i, 1), 1)
        if tail:
            scalar_trace.extend((0x36EAA6, 0x36EAAD))
        scalar_trace.extend((0x36EAB0, 0x36EAB4, 0x36EAB5, 0x36EAB6))
        for at in (c + 4, c - 8, c - 4, c):
            sr(at)
        edx = int.from_bytes(original[4 * q - 4 : 4 * q], "little") if q else n
        regs = dict(entry_regs, eax=h, ecx=0, edx=edx, esp=c + 4)
        nested = dict(
            geometry=dict(entry=c, source=h + off, destination=h, count=n),
            registers=dict(regs),
            xmm=dict(packet["xmm"]),
            pages=_pages(mutable),
            events=scalar_events,
            trace_rvas=[f"0x{t:08x}" for t in scalar_trace],
            flags=0x44,
            flag_mask=0x8D5 if tail else 0x8C5,
            df=0,
            endpoint=0x408476,
            source_snapshot=original,
        )
        events.extend(copy.deepcopy(scalar_events))
        trace.extend(nested["trace_rvas"])
        state("return", 0x408476, 0x44, nested["flag_mask"])
        pc(
            0x8476,
            0x8479,
            0x847D,
            0x8480,
            0x8481,
            0x8491,
            0x8493,
            0x8497,
            0x8498,
            0x849A,
            0x849B,
            0x849C,
        )
        r(h + 20)
        w(h + 16, n)
        r(e - 16)
        w(h + n, 0, 1)
        for at in (e - 12, e - 8, e - 4, e):
            r(at)
        final_flags, mask = 0x85, 0x8D5
    regs.update(
        eax=h,
        ebx=initial["ebx"],
        esi=initial["esi"],
        edi=initial["edi"],
        ebp=initial["ebp"],
        esp=e + 12,
    )
    # Independent final-page equations include every saved and argument word.
    direct = {p: bytearray(b) for p, b in packet["pages"].items()}
    for at, value in (
        (e - 4, initial["ebp"]),
        (e - 8, initial["esi"]),
        (e - 12, initial["edi"]),
    ):
        _write(direct, at, value.to_bytes(4, "little"))
    if n == 0:
        _write(direct, h + 16, bytes(4))
        _write(direct, h, b"\x00")
    elif off:
        for at, value in (
            (e - 16, initial["ebx"]),
            (e - 20, n),
            (e - 24, h + off),
            (e - 28, h),
            (e - 32, 0x408476),
            (e - 36, n),
            (e - 40, h),
        ):
            _write(direct, at, value.to_bytes(4, "little"))
        _write(direct, h, _read(packet["pages"], h + off, n))
        _write(direct, h + 16, n.to_bytes(4, "little"))
        _write(direct, h + n, b"\x00")
    _require(
        _pages(direct) == _pages(mutable),
        "inline self copy independent erase pages differ",
    )
    return dict(
        geometry=dict(
            entry=e,
            object=h,
            old_length=length,
            offset=0,
            requested=off,
            removed=off,
            count=n,
        ),
        registers=regs,
        xmm=dict(packet["xmm"]),
        pages=_pages(mutable),
        events=events,
        trace_rvas=trace,
        flags=final_flags,
        flag_mask=mask,
        df=0,
        endpoint=0x408135,
        source_snapshot=_read(packet["pages"], h, 24),
        string_bytes=_read(mutable, h, 24),
        memmove_packet=nested,
        boundaries=states,
    )


def apply(*, pages, registers, xmm, return_address, entry_flags):
    try:
        return _apply(pages, registers, xmm, return_address, entry_flags)
    except InlineSelfCopyError:
        raise
    except Exception as exc:
        raise InlineSelfCopyError(str(exc)) from exc


def _apply(pages, registers, xmm, return_address, entry_flags):
    g, h, length, off, requested, n = _validate(
        pages, registers, xmm, return_address, entry_flags
    )
    mutable = {p: bytearray(b) for p, b in pages.items()}
    events, states = [], []
    trace = [
        f"0x{t:08x}"
        for t in (
            0x80D0,
            0x80D1,
            0x80D3,
            0x80D4,
            0x80D7,
            0x80D8,
            0x80DA,
            0x80DD,
            0x80DE,
            0x80E1,
            0x80E3,
            0x80E9,
            0x80EC,
            0x80EE,
            0x80F0,
            0x80F3,
            0x80F5,
            0x80F7,
            0x80FA,
            0x80FD,
            0x8103,
            0x8106,
            0x810A,
            0x8125,
            0x8127,
            0x8128,
            0x812A,
            0x812C,
            0x8130,
        )
    ]

    def r(at):
        v = int.from_bytes(_read(mutable, at, 4), "little")
        events.append(dict(access="read", address=at, width=4, value=v))
        return v

    def w(at, value, width=4):
        _write(mutable, at, value.to_bytes(width, "little"))
        events.append(dict(access="write", address=at, width=width, value=value))

    for at, value in ((g - 4, registers["ebp"]), (g - 8, registers["ebx"])):
        w(at, value)
    r(g + 4)
    w(g - 12, registers["esi"])
    r(g + 8)
    w(g - 16, registers["edi"])
    r(h + 16)
    r(g + 12)
    r(h + 16)
    w(h + 16, off + n)
    r(h + 20)
    w(g - 20, off)
    w(g - 24, 0)
    w(h + off + n, 0, 1)
    w(g - 28, 0x408135)
    regs = dict(
        registers, eax=off + n, ebx=h, ecx=h, edx=h, esi=h, edi=n, ebp=g - 4, esp=g - 28
    )
    states.append(
        dict(
            registers=dict(regs),
            xmm=dict(xmm),
            pages=_pages(mutable),
            events=copy.deepcopy(events),
            flags=0x85,
            flag_mask=0x8D5,
            df=0,
            endpoint=0x408410,
            phase="erase_entry",
        )
    )
    packet = dict(
        pages=_pages(mutable),
        registers=dict(regs),
        xmm=dict(xmm),
        return_address=0x408135,
        entry_flags=(entry_flags & 0x202) | 0x85,
    )
    expected = _erase_law(packet)
    child = erase.apply(**packet)
    _require(
        _packet_same(child, expected), "inline self copy complete erase packet differs"
    )
    prefix = copy.deepcopy(events)
    for state in child["boundaries"]:
        state = copy.deepcopy(state)
        state["events"] = prefix + state["events"]
        state["phase"] = "memmove_" + state["phase"]
        states.append(state)
    events.extend(copy.deepcopy(child["events"]))
    trace.extend(child["trace_rvas"])
    mutable = {p: bytearray(b) for p, b in child["pages"].items()}
    regs = dict(child["registers"])
    states.append(
        dict(
            registers=dict(regs),
            xmm=dict(xmm),
            pages=_pages(mutable),
            events=copy.deepcopy(events),
            flags=child["flags"],
            flag_mask=child["flag_mask"],
            df=0,
            endpoint=0x408135,
            phase="erase_return",
        )
    )
    for at in (g - 16, g - 12, g - 8, g - 4, g):
        r(at)
    trace.extend(f"0x{t:08x}" for t in (0x8135, 0x8136, 0x8138, 0x8139, 0x813A, 0x813B))
    final = dict(registers, eax=h, ecx=regs["ecx"], edx=regs["edx"], esp=g + 16)
    q, tail = divmod(n, 4)
    _require(
        len(events) == (33 if n == 0 else 30 if off == 0 else 49 + 2 * q + 2 * tail),
        "inline self copy access count differs",
    )
    _require(
        len(trace)
        == (
            58
            if n == 0
            else 56 if off == 0 else 101 + 6 * q + 6 * tail + 2 * bool(tail)
        ),
        "inline self copy trace count differs",
    )
    return dict(
        geometry=dict(
            entry=g,
            source_object=h,
            destination_object=h,
            source_length=length,
            offset=off,
            requested=requested,
            count=n,
        ),
        registers=final,
        xmm=dict(xmm),
        pages=_pages(mutable),
        events=events,
        trace_rvas=trace,
        flags=child["flags"],
        flag_mask=child["flag_mask"],
        df=0,
        endpoint=return_address,
        source_snapshot=_read(pages, h, 24),
        string_bytes=_read(mutable, h, 24),
        erase_packet=copy.deepcopy(child),
        boundaries=states,
    )
