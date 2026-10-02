"""Actual-page disjoint inline empty string assignment, offset0/maxFFFFFFFF.

Source inline capacity/terminator are domain premises, not native accesses on
this selected branch. Only source size and destination capacity are read.
"""

from __future__ import annotations

ANALYSIS_KIND = "pe_native_movement_empty_string_copy_semantics"
BASE, U32 = 0x400000, 0xFFFFFFFF
ENTRY, SIZE = 0x80D0, 288
BODY_SHA256 = "062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333"
REGISTERS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
SOURCE_PINS = {
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
    "movement_binding": (
        "pe_native_movement_effect_binding",
        "54c060913d61f6bb5e4c1f2586f0d5186ea73ad6c058dd48b1cc056e64a410b9",
    ),
    "default_record": (
        "pe_native_movement_effect_record_default_conformance",
        "942fc246105c941a46ac73e7be432acdacad1428322888b76c0164aca49e673f",
    ),
}
TRACE = (
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
    0x813E,
    0x8141,
    0x8147,
    0x814A,
    0x8170,
    0x8172,
    0x8174,
    0x8178,
    0x817B,
    0x818B,
    0x818D,
    0x818E,
    0x818F,
    0x8190,
    0x8193,
    0x8194,
)


class EmptyStringCopyError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise EmptyStringCopyError(message)


def _normalize(operation):
    try:
        return operation()
    except EmptyStringCopyError:
        raise
    except Exception as exc:
        raise EmptyStringCopyError(str(exc)) from exc


def _word(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid empty string " + label)


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
        and all(type(k) is str for k in registers)
        and set(registers) == set(REGISTERS),
        "invalid empty string GPR schema",
    )
    for key, value in registers.items():
        _word(value, key)
    _require(
        type(xmm) is dict
        and all(type(k) is str for k in xmm)
        and set(xmm) == set(XMM)
        and all(type(v) is int and 0 <= v < 2**128 for v in xmm.values()),
        "invalid empty string XMM schema",
    )
    _word(entry_flags, "entry flags")
    _require(
        entry_flags & ~0xAD7 == 0 and entry_flags & 2 == 2,
        "empty string ordinary DF-clear entry flags differ",
    )
    _require(type(pages) is dict and bool(pages), "invalid empty string pages schema")
    for page, data in pages.items():
        _word(page, "page address")
        _require(
            page % 4096 == 0
            and page + 4096 <= 2**32
            and type(data) is bytes
            and len(data) == 4096,
            "invalid empty string immutable page",
        )
    g, d = registers["esp"], registers["ecx"]
    _require(16 <= g and g + 16 <= U32, "empty string frame wraps")
    s = int.from_bytes(_read(pages, g + 4, 4), "little")
    _require(
        s > 0 and d > 0 and s + 24 <= U32 and d + 24 <= U32,
        "empty string object extent wraps or null",
    )
    spans = ((g - 16, g + 16), (s, s + 24), (d, d + 24))
    for i, left in enumerate(spans):
        _read(pages, left[0], left[1] - left[0])
        _require(
            left[1] <= BASE + ENTRY or BASE + ENTRY + SIZE <= left[0],
            "empty string data overlaps selected code",
        )
        for right in spans[i + 1 :]:
            _require(
                left[1] <= right[0] or right[1] <= left[0],
                "empty string data spans overlap",
            )
    _word(return_address, "return address")
    _require(
        return_address > 0
        and not (BASE + ENTRY <= return_address < BASE + ENTRY + SIZE)
        and all(not (a <= return_address < b) for a, b in spans),
        "empty string return overlaps data or selected code",
    )
    _require(
        int.from_bytes(_read(pages, g, 4), "little") == return_address
        and _read(pages, g + 8, 4) == bytes(4)
        and _read(pages, g + 12, 4) == b"\xff" * 4,
        "empty string installed caller words differ",
    )
    _require(
        _read(pages, s, 1) == b"\0"
        and _read(pages, s + 16, 4) == bytes(4)
        and int.from_bytes(_read(pages, s + 20, 4), "little") == 15,
        "empty string source inline object differs",
    )
    _require(
        int.from_bytes(_read(pages, d + 20, 4), "little") == 15
        and int.from_bytes(_read(pages, d + 16, 4), "little") <= 15,
        "empty string destination inline object differs",
    )
    return s, d, g


def apply(*, pages, registers, xmm, return_address, entry_flags):
    """Return detached full state/pages/events for the admitted empty assignment."""
    return _normalize(
        lambda: _apply(pages, registers, xmm, return_address, entry_flags)
    )


def _apply(pages, registers, xmm, return_address, entry_flags):
    s, d, g = _validate(pages, registers, xmm, return_address, entry_flags)
    memory = {page: bytearray(data) for page, data in pages.items()}
    events = []
    rows = (
        ("write", g - 4, 4, registers["ebp"]),
        ("write", g - 8, 4, registers["ebx"]),
        ("read", g + 4, 4, s),
        ("write", g - 12, 4, registers["esi"]),
        ("read", g + 8, 4, 0),
        ("write", g - 16, 4, registers["edi"]),
        ("read", s + 16, 4, 0),
        ("read", g + 12, 4, U32),
        ("read", d + 20, 4, 15),
        ("read", d + 20, 4, 15),
        ("write", d + 16, 4, 0),
        ("read", g - 16, 4, registers["edi"]),
        ("read", g - 12, 4, registers["esi"]),
        ("read", g - 8, 4, registers["ebx"]),
        ("write", d, 1, 0),
        ("read", g - 4, 4, registers["ebp"]),
        ("read", g, 4, return_address),
    )
    for access, address, width, value in rows:
        payload = value.to_bytes(width, "little")
        if access == "write":
            _write(memory, address, payload)
        else:
            _require(
                _read(memory, address, width) == payload,
                "empty string expected read differs",
            )
        events.append(dict(access=access, address=address, width=width, value=value))
    return dict(
        source_address=s,
        destination_address=d,
        registers=dict(registers, eax=d, ecx=0, esp=g + 16),
        xmm=dict(xmm),
        pages=_pages(memory),
        events=events,
        flags=0x85,
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
        trace_rvas=[f"0x{pc:08x}" for pc in TRACE],
    )
