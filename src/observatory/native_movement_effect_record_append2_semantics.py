"""Selected external-source movement record append with existing capacity.

Eight empty strings and two path entries use the trusted complete record-copy
law. One allocation success is supplied; receiver growth and ownership are open.
"""

from __future__ import annotations
import copy
from src.observatory import native_movement_effect_record_copy2_semantics as record
from src.observatory import native_movement_path_clone2_semantics as path

BASE, U32, COOKIE = 0x400000, 0xFFFFFFFF, 0x893F28
REGISTERS, XMM = record.REGISTERS, record.XMM
BODY_PINS = dict(record.BODY_PINS)
BODY_PINS[0x259F00] = (
    183,
    "39a9908012609c47f77556aea5af0865f3eb36943b5a1860c4c338bb6ea6fbb7",
)
SOURCE_PINS = dict(record.SOURCE_PINS)
OWNER_PREFIX = tuple(
    0x259F00 + n
    for n in (
        0,
        1,
        3,
        5,
        0xA,
        0x10,
        0x11,
        0x12,
        0x13,
        0x14,
        0x19,
        0x1B,
        0x1C,
        0x1F,
        0x25,
        0x27,
        0x2A,
        0x2D,
        0x2F,
        0x76,
        0x79,
        0x83,
        0x86,
        0x89,
        0x8C,
        0x93,
        0x95,
        0x97,
        0x98,
    )
)
OWNER_SUFFIX = tuple(
    0x259F00 + n for n in (0x9D, 0xA4, 0xA7, 0xAE, 0xAF, 0xB0, 0xB1, 0xB3, 0xB4)
)
_read, _write, _pages, _same = record._read, record._write, record._pages, record._same


class RecordAppend2Error(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise RecordAppend2Error(message)


def _validate(pages, registers, xmm, return_address, entry_flags, allocation_result):
    _require(
        type(registers) is dict
        and set(registers) == set(REGISTERS)
        and all(
            type(k) is str and type(v) is int and 0 <= v <= U32
            for k, v in registers.items()
        ),
        "invalid append GPR schema",
    )
    _require(
        type(xmm) is dict
        and set(xmm) == set(XMM)
        and all(
            type(k) is str and type(v) is int and 0 <= v < 2**128
            for k, v in xmm.items()
        ),
        "invalid append XMM schema",
    )
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
        "invalid append immutable pages",
    )
    _require(
        type(entry_flags) is int
        and 0 <= entry_flags <= U32
        and entry_flags & ~0xAD7 == 0
        and entry_flags & 2 == 2,
        "invalid append ordinary DF-clear flags",
    )
    g, h = registers["esp"], registers["ecx"]
    _require(168 <= g and g + 8 <= U32, "append frame wraps")
    _require(0 < h and h + 12 <= U32, "append receiver wraps or null")
    r = int.from_bytes(_read(pages, g + 4, 4), "little")
    b, c, end = (int.from_bytes(_read(pages, h + n, 4), "little") for n in (0, 4, 8))
    _require(
        0 < b <= c
        and c + 308 <= end <= U32
        and (c - b) % 308 == 0
        and (end - b) % 308 == 0,
        "append receiver lacks complete existing capacity",
    )
    _require(r >= c and r > 0 and r + 308 <= U32, "append external source differs")
    _require(
        type(allocation_result) is int
        and 0x06000000 <= allocation_result <= 0x06003FF0,
        "append allocation result outside ordinary domain",
    )
    o = int.from_bytes(_read(pages, r + 0xCC, 4), "little")
    _require(0 < o and o + 16 <= U32, "append source path extent differs")
    spans = (
        (g - 168, g + 8),
        (h, h + 12),
        (r, r + 308),
        (c, c + 308),
        (o, o + 16),
        (allocation_result, allocation_result + 16),
        (0, 4),
        (COOKIE, COOKIE + 4),
    )
    for i, (left, right) in enumerate(spans):
        _read(pages, left, right - left)
        _require(
            all(right <= lo or hi <= left for lo, hi in spans[i + 1 :]),
            "append data spans overlap",
        )
        _require(
            all(
                right <= BASE + a or BASE + a + n <= left
                for a, (n, digest) in BODY_PINS.items()
            ),
            "append data overlaps code",
        )
    _require(
        type(return_address) is int
        and 0 < return_address <= U32
        and all(not (lo <= return_address < hi) for lo, hi in spans)
        and all(
            not (BASE + a <= return_address < BASE + a + n)
            for a, (n, digest) in BODY_PINS.items()
        ),
        "append return overlaps data or code",
    )
    _require(
        int.from_bytes(_read(pages, g, 4), "little") == return_address,
        "append installed return differs",
    )
    return g, h, r, c


def apply(*, pages, registers, xmm, return_address, entry_flags, allocation_result):
    try:
        return _apply(
            pages, registers, xmm, return_address, entry_flags, allocation_result
        )
    except RecordAppend2Error:
        raise
    except Exception as exc:
        raise RecordAppend2Error(str(exc)) from exc


def _apply(pages, registers, xmm, return_address, entry_flags, allocation_result):
    g, h, r, c = _validate(
        pages, registers, xmm, return_address, entry_flags, allocation_result
    )
    memory = {p: bytearray(b) for p, b in pages.items()}
    events, boundaries = [], []
    seh = int.from_bytes(_read(pages, 0, 4), "little")
    cookie = int.from_bytes(_read(pages, COOKIE, 4), "little")
    regs = dict(registers)

    def event(access, address, value):
        if access == "write":
            _write(memory, address, value.to_bytes(4, "little"))
        else:
            _require(
                int.from_bytes(_read(memory, address, 4), "little") == value,
                "append expected read differs",
            )
        events.append(dict(access=access, address=address, width=4, value=value))

    def boundary(name, endpoint, flags, mask):
        boundaries.append(
            dict(
                kind="record",
                name=name,
                index=0,
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

    for at, value in ((g - 4, registers["ebp"]), (g - 8, U32), (g - 12, 0x7A19F2)):
        event("write", at, value)
    event("read", 0, seh)
    for at, value in (
        (g - 16, seh),
        (g - 20, h),
        (g - 24, registers["esi"]),
        (g - 28, registers["edi"]),
    ):
        event("write", at, value)
    event("read", COOKIE, cookie)
    event("write", g - 32, cookie ^ (g - 4))
    event("write", 0, g - 16)
    event("read", h + 4, c)
    event("read", g + 4, r)
    event("read", h + 8, int.from_bytes(_read(pages, h + 8, 4), "little"))
    event("read", h + 4, c)
    event("write", g + 4, c)
    event("write", g - 20, c)
    event("write", g - 8, 1)
    event("write", g - 36, r)
    event("write", g - 40, BASE + 0x259F9D)
    regs.update(eax=g - 16, ecx=c, esi=h, edi=r, ebp=g - 4, esp=g - 40)
    test_flags = (int((c & 255).bit_count() % 2 == 0) << 2) | (c >> 31) << 7
    boundary("entry", BASE + 0x15B9B0, test_flags, 0x8C5)
    prefix = copy.deepcopy(events)
    child = record.apply(
        pages=_pages(memory),
        registers=dict(regs),
        xmm=dict(xmm),
        return_address=BASE + 0x259F9D,
        entry_flags=(entry_flags & ~0x8D5) | test_flags,
        allocation_result=allocation_result,
    )
    _require(
        type(child) is dict
        and set(child)
        == {
            "source_address",
            "record_address",
            "record_bytes",
            "source_snapshot",
            "registers",
            "xmm",
            "pages",
            "events",
            "flags",
            "flag_mask",
            "df",
            "endpoint",
            "trace_rvas",
            "boundaries",
            "path_packet",
        },
        "append record child schema differs",
    )
    _require(
        _same(child["source_address"], r)
        and _same(child["record_address"], c)
        and _same(child["endpoint"], BASE + 0x259F9D)
        and _same(child["df"], 0)
        and type(child["pages"]) is dict
        and type(child["registers"]) is dict
        and type(child["xmm"]) is dict
        and type(child["events"]) is list
        and len(child["events"]) == 372
        and type(child["trace_rvas"]) is list
        and len(child["trace_rvas"]) == 591
        and type(child["boundaries"]) is list
        and len(child["boundaries"]) == 23,
        "append record child geometry or count differs",
    )
    for state in child["boundaries"]:
        state = copy.deepcopy(state)
        state["events"] = prefix + state["events"]
        boundaries.append(state)
    events.extend(copy.deepcopy(child["events"]))
    memory = {p: bytearray(b) for p, b in child["pages"].items()}
    regs = dict(child["registers"])
    boundary("return", BASE + 0x259F9D, 0x85, 0x8D5)
    event("read", h + 4, c)
    event("write", h + 4, c + 308)
    event("read", g - 16, seh)
    event("write", 0, seh)
    for at, value in (
        (g - 32, cookie ^ (g - 4)),
        (g - 28, registers["edi"]),
        (g - 24, registers["esi"]),
        (g - 4, registers["ebp"]),
        (g, return_address),
    ):
        event("read", at, value)
    trace = (
        [f"0x{pc:08x}" for pc in OWNER_PREFIX]
        + child["trace_rvas"]
        + [f"0x{pc:08x}" for pc in OWNER_SUFFIX]
    )
    _require(
        len(events) == 401 and len(trace) == 629 and len(boundaries) == 25,
        "append selected path count differs",
    )
    return dict(
        receiver_address=h,
        source_address=r,
        record_address=c,
        record_bytes=_read(memory, c, 308),
        source_snapshot=_read(memory, r, 308),
        registers=dict(registers, eax=c, ecx=cookie ^ (g - 4), edx=r + 0xF8, esp=g + 8),
        xmm=dict(xmm),
        pages=_pages(memory),
        events=events,
        flags=path._add_flags(c, 308),
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
        trace_rvas=trace,
        boundaries=boundaries,
        record_packet=copy.deepcopy(child),
    )
