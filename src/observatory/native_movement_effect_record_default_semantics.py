"""Actual-page default effect record and seven inline empty-string assignments.

This selected normal path has no allocator, copy, free, SSE or handler call.
The source has a saved cookie word but no normal cookie-check call.
"""

from __future__ import annotations

import copy

ANALYSIS_KIND = "pe_native_movement_effect_record_default_semantics"
BASE, U32 = 0x400000, 0xFFFFFFFF
REGISTERS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
COOKIE, LITERAL = 0x893F28, 0x80DFDC
RECORD_BYTES = 0x134
SOURCE_PINS = {
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
    "movement_binding": (
        "pe_native_movement_effect_binding",
        "54c060913d61f6bb5e4c1f2586f0d5186ea73ad6c058dd48b1cc056e64a410b9",
    ),
}
BODY_PINS = {
    0x1999A0: (669, "2f17cc9bd3616c14305fb7fc1871bf0e37d09262825a99213f5b0568d6c6045d"),
    0x7FD0: (245, "c49f0e24bd27ed5495ceddc13536ca6fbe85d8c97f207db817ce0642b8b01906"),
}
STRING_OFFSETS = (0x38, 0x50, 0x68, 0x80, 0xA4, 0xE0, 0x118)
INLINE_ONLY_OFFSET = 0xF8
STRING_RETURNS = (0x199A51, 0x199A84, 0x199AB4, 0x199AE7, 0x199B38, 0x199BC5, 0x199C1F)
EMPTY_TRACE = (
    0x7FD0,
    0x7FD1,
    0x7FD3,
    0x7FD4,
    0x7FD7,
    0x7FD8,
    0x7FDA,
    0x7FDC,
    0x7FDE,
    0x7FE1,
    0x7FE4,
    0x7FEA,
    0x7FEC,
    0x7FEE,
    0x8035,
    0x8036,
    0x8039,
    0x803C,
    0x803E,
    0x8041,
    0x805C,
    0x805E,
    0x8060,
    0x8064,
    0x8067,
    0x8077,
    0x8079,
    0x807A,
    0x807B,
    0x807C,
    0x807F,
    0x8080,
)
# Selected owner segments, with capacity15 branches fixed by earlier stores.
OWNER_SEGMENTS = (
    (
        0x1999A0,
        0x1999A1,
        0x1999A3,
        0x1999A5,
        0x1999AA,
        0x1999B0,
        0x1999B1,
        0x1999B2,
        0x1999B3,
        0x1999B8,
        0x1999BA,
        0x1999BB,
        0x1999BE,
        0x1999C4,
        0x1999C6,
        0x1999C9,
        0x1999CC,
        0x1999CF,
        0x1999D5,
        0x1999DC,
        0x1999DF,
        0x1999E6,
        0x1999ED,
        0x1999F1,
        0x1999F8,
        0x1999FF,
        0x199A06,
        0x199A0D,
        0x199A14,
        0x199A1B,
        0x199A21,
        0x199A28,
        0x199A2F,
        0x199A36,
        0x199A3A,
        0x199A40,
        0x199A42,
        0x199A44,
        0x199A49,
        0x199A4C,
    ),
    (
        0x199A51,
        0x199A54,
        0x199A5B,
        0x199A62,
        0x199A69,
        0x199A6D,
        0x199A73,
        0x199A75,
        0x199A77,
        0x199A7C,
        0x199A7F,
    ),
    (
        0x199A84,
        0x199A87,
        0x199A8B,
        0x199A92,
        0x199A99,
        0x199A9D,
        0x199AA3,
        0x199AA5,
        0x199AA7,
        0x199AAC,
        0x199AAF,
    ),
    (
        0x199AB4,
        0x199ABA,
        0x199ABE,
        0x199AC5,
        0x199ACC,
        0x199AD0,
        0x199AD6,
        0x199AD8,
        0x199ADA,
        0x199ADF,
        0x199AE2,
    ),
    (
        0x199AE7,
        0x199AEB,
        0x199AF1,
        0x199AFB,
        0x199B05,
        0x199B0F,
        0x199B16,
        0x199B1D,
        0x199B21,
        0x199B27,
        0x199B29,
        0x199B2B,
        0x199B30,
        0x199B33,
    ),
    (
        0x199B38,
        0x199B42,
        0x199B4C,
        0x199B56,
        0x199B60,
        0x199B6A,
        0x199B74,
        0x199B7E,
        0x199B82,
        0x199B88,
        0x199B92,
        0x199B9C,
        0x199BA3,
        0x199BAA,
        0x199BAE,
        0x199BB4,
        0x199BB6,
        0x199BB8,
        0x199BBD,
        0x199BC0,
    ),
    (
        0x199BC5,
        0x199BCB,
        0x199BD2,
        0x199BD9,
        0x199BDD,
        0x199BE1,
        0x199BE4,
        0x199BE8,
        0x199BEE,
        0x199BF8,
        0x199C02,
        0x199C04,
        0x199C0B,
        0x199C12,
        0x199C17,
        0x199C1A,
    ),
    (
        0x199C1F,
        0x199C29,
        0x199C2B,
        0x199C2E,
        0x199C35,
        0x199C36,
        0x199C37,
        0x199C39,
        0x199C3A,
    ),
)


class DefaultRecordError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise DefaultRecordError(message)


def _normalize(operation):
    try:
        return operation()
    except DefaultRecordError:
        raise
    except Exception as exc:
        raise DefaultRecordError(str(exc)) from exc


def _word(value, label):
    _require(
        type(value) is int and 0 <= value <= U32, "invalid default record " + label
    )


def _read(pages, address, width):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(width)
    )


def _write(pages, address, payload):
    for i, value in enumerate(payload):
        pages[(address + i) & ~4095][(address + i) & 4095] = value


def _pages(pages):
    return {page: bytes(data) for page, data in pages.items()}


def _validate(pages, registers, xmm, return_address, entry_flags):
    _require(
        type(registers) is dict
        and all(type(key) is str for key in registers)
        and set(registers) == set(REGISTERS),
        "invalid default record GPR schema",
    )
    for key, value in registers.items():
        _word(value, key)
    _require(
        type(xmm) is dict
        and all(type(key) is str for key in xmm)
        and set(xmm) == set(XMM)
        and all(type(value) is int and 0 <= value < 2**128 for value in xmm.values()),
        "invalid default record XMM schema",
    )
    _word(entry_flags, "entry flags")
    _require(
        entry_flags & ~0xAD7 == 0 and entry_flags & 2 == 2,
        "default record ordinary DF-clear entry flags differ",
    )
    _require(type(pages) is dict and bool(pages), "invalid default record pages schema")
    for page, data in pages.items():
        _word(page, "page address")
        _require(
            page % 4096 == 0
            and page + 4096 <= 2**32
            and type(data) is bytes
            and len(data) == 4096,
            "invalid default record immutable page",
        )
    g, r = registers["esp"], registers["ecx"]
    _require(56 <= g and g + 8 <= U32, "default record frame wraps")
    _require(
        r > LITERAL and r + RECORD_BYTES <= U32,
        "default record inline object/source ordering or extent differs",
    )
    spans = (
        (g - 56, g + 8),
        (r, r + RECORD_BYTES),
        (0, 4),
        (COOKIE, COOKIE + 4),
        (LITERAL, LITERAL + 1),
    )
    for i, left in enumerate(spans):
        for right in spans[i + 1 :]:
            _require(
                left[1] <= right[0] or right[1] <= left[0],
                "default record data spans overlap",
            )
    for left, right in spans:
        _read(pages, left, right - left)
        for start, (size, _) in BODY_PINS.items():
            _require(
                right <= BASE + start or BASE + start + size <= left,
                "default record data overlaps selected code",
            )
    _word(return_address, "return address")
    _require(
        return_address > 0
        and all(not (left <= return_address < right) for left, right in spans),
        "default record return overlaps data",
    )
    _require(
        all(
            not (BASE + start <= return_address < BASE + start + size)
            for start, (size, _) in BODY_PINS.items()
        ),
        "default record return overlaps selected code",
    )
    _require(
        int.from_bytes(_read(pages, g, 4), "little") == return_address,
        "default record installed return differs",
    )
    _require(
        _read(pages, LITERAL, 1) == b"\0",
        "default record selected complete literal differs",
    )


def apply(*, pages, registers, xmm, return_address, entry_flags):
    """Return detached complete pages/state/accesses for the admitted normal path."""
    return _normalize(
        lambda: _apply(pages, registers, xmm, return_address, entry_flags)
    )


def _apply(pages, registers, xmm, return_address, entry_flags):
    _validate(pages, registers, xmm, return_address, entry_flags)
    memory = {p: bytearray(v) for p, v in pages.items()}
    events = []
    g, r = registers["esp"], registers["ecx"]
    f = g - 4
    cookie = int.from_bytes(_read(pages, COOKIE, 4), "little")
    seh = int.from_bytes(_read(pages, 0, 4), "little")
    argument = int.from_bytes(_read(pages, g + 4, 4), "little")

    def event(access, address, width, value):
        if access == "write":
            _write(memory, address, value.to_bytes(width, "little"))
        else:
            _require(
                int.from_bytes(_read(memory, address, width), "little") == value,
                "default record expected read differs",
            )
        events.append(dict(access=access, address=address, width=width, value=value))

    def write(address, value, width=4):
        event("write", address, width, value)

    def read(address, value, width=4):
        event("read", address, width, value)

    for address, value in ((g - 4, registers["ebp"]), (g - 8, U32), (g - 12, 0x7B57A7)):
        write(address, value)
    read(0, seh)
    write(g - 16, seh)
    write(g - 20, r)
    write(g - 24, registers["esi"])
    read(COOKIE, cookie)
    write(g - 28, cookie ^ f)
    write(0, g - 16)
    write(g - 20, r)
    read(g + 4, argument)
    fields = (
        (0, U32, 4),
        (4, U32, 4),
        (8, argument, 4),
        (0xC, 4, 4),
        (0x10, 0, 4),
        (0x14, 0, 1),
        (0x18, 0, 4),
        (0x1C, 0, 4),
        (0x20, 0, 4),
        (0x24, 0, 4),
        (0x28, 0, 4),
        (0x2C, 0, 4),
        (0x30, 0, 2),
        (0x34, 2, 4),
    )
    for offset, value, width in fields:
        write(r + offset, value, width)
    boundaries = []

    def boundary(name, index, state):
        boundaries.append(
            dict(
                name=name,
                index=index,
                registers=state,
                xmm=dict(xmm),
                pages=_pages(memory),
                events=copy.deepcopy(events),
                flags=0x85,
                flag_mask=0x8D5,
                df=0,
                endpoint=(
                    BASE + 0x7FD0 if name == "entry" else BASE + STRING_RETURNS[index]
                ),
            )
        )

    for index, offset in enumerate(STRING_OFFSETS):
        s = r + offset
        if index == 1:
            write(g - 8, 0)
        elif index in (2, 3, 4):
            write(g - 8, index - 1, 1)
        elif index == 5:
            for field, value in (
                (0xBC, 2),
                (0xC0, 2),
                (0xC4, 0),
                (0xC8, 0),
                (0xCC, 0),
                (0xD0, 0),
                (0xD4, 0),
            ):
                write(r + field, value)
            write(g - 8, 5, 1)
            write(r + 0xD8, 0)
            write(r + 0xDC, 10)
        elif index == 6:
            q = r + INLINE_ONLY_OFFSET
            write(q + 20, 15)
            write(q + 16, 0)
            read(q + 20, 15)
            write(q, 0, 1)
            write(g - 8, 7, 1)
            write(r + 0x110, U32)
            write(r + 0x114, U32)
        if index == 4:
            for field, value in ((0x98, 0), (0x9C, U32), (0xA0, U32)):
                write(r + field, value)
        if index == 6:
            write(g - 32, 0)
        write(s + 20, 15)
        write(s + 16, 0)
        if index != 6:
            read(s + 20, 15)
            write(g - 32, 0)
        write(g - 36, LITERAL)
        write(s, 0, 1)
        write(g - 40, BASE + STRING_RETURNS[index])
        child_entry = dict(
            registers,
            eax=(r + INLINE_ONLY_OFFSET if index == 6 else s),
            ecx=s,
            esi=r,
            ebp=f,
            esp=g - 40,
        )
        boundary("entry", index, child_entry)
        # Standalone selected empty assignment: source lies below inline object,
        # requested length0 and just-written capacity15 exclude every child call.
        write(g - 44, f)
        write(g - 48, registers["ebx"])
        read(g - 36, LITERAL)
        write(g - 52, r)
        read(s + 20, 15)
        write(g - 56, registers["edi"])
        read(g - 32, 0)
        read(s + 20, 15)
        read(s + 20, 15)
        write(s + 16, 0)
        read(g - 56, registers["edi"])
        read(g - 52, r)
        read(g - 48, registers["ebx"])
        write(s, 0, 1)
        read(g - 44, f)
        read(g - 40, BASE + STRING_RETURNS[index])
        boundary(
            "return", index, dict(registers, eax=s, ecx=15, esi=r, ebp=f, esp=g - 28)
        )
    write(r + 0x130, 3)
    read(g - 16, seh)
    write(0, seh)
    read(g - 28, cookie ^ f)
    read(g - 24, registers["esi"])
    read(g - 4, registers["ebp"])
    read(g, return_address)
    trace = []
    for segment in OWNER_SEGMENTS[:-1]:
        trace.extend(segment)
        trace.extend(EMPTY_TRACE)
    trace.extend(OWNER_SEGMENTS[-1])
    result = dict(
        record_address=r,
        record_bytes=_read(memory, r, RECORD_BYTES),
        argument=argument,
        registers=dict(registers, eax=r, ecx=cookie ^ f, esp=g + 8),
        xmm=dict(xmm),
        pages=_pages(memory),
        events=events,
        flags=0x85,
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
        trace_rvas=[f"0x{pc:08x}" for pc in trace],
        string_boundaries=boundaries,
    )
    _require(
        len(events) == 217 and len(trace) == 356,
        "default record selected path accounting differs",
    )
    return result
