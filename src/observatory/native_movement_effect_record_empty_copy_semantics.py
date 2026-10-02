"""Actual-page movement record copy with eight empty strings and an empty path.

FS base is zero. This selected normal return saves a cookie but calls no cookie
checker, allocator, scalar path copy, destructor, unwind or failure handler.
"""

from __future__ import annotations
import copy
from src.observatory import native_movement_empty_string_copy_semantics as string

BASE, U32 = 0x400000, 0xFFFFFFFF
REGISTERS, XMM = string.REGISTERS, string.XMM
COOKIE = 0x00893F28
RECORD_BYTES = 308
STRING_OFFSETS = (0x38, 0x50, 0x68, 0x80, 0xA4, 0xE0, 0xF8, 0x118)
STRING_RETURNS = (
    0x15BA65,
    0x15BA99,
    0x15BACA,
    0x15BB01,
    0x15BB5C,
    0x15BC19,
    0x15BC50,
    0x15BC93,
)
BODY_PINS = {
    0x15B9B0: (772, "3846fdb1ca2ebc1b4b6e83a64994f82d4907938345ff0d856c9bbea690957fc6"),
    0x80D0: (288, "062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333"),
    0x9A8E0: (79, "4359ecaf051506bce97afe182b66c453ca8d13ac4091d72a810f9df43d14d2e0"),
    0x9AC40: (87, "29a0428ed018a85e4e0a76f283f10040cf9e084f49bee5706b58766b570cb9d1"),
}
SOURCE_PINS = dict(
    string.SOURCE_PINS,
    empty_string_copy=(
        "pe_native_movement_empty_string_copy_conformance",
        "c3d9d8598d7aa922157397a27a58aeabf86732e9bb620625d602481dd90c18b1",
    ),
)
OWNER_SEGMENTS = (
    (
        1423792,
        1423793,
        1423795,
        1423797,
        1423802,
        1423808,
        1423809,
        1423810,
        1423811,
        1423812,
        1423817,
        1423819,
        1423820,
        1423823,
        1423829,
        1423831,
        1423834,
        1423837,
        1423840,
        1423842,
        1423845,
        1423847,
        1423850,
        1423853,
        1423856,
        1423859,
        1423862,
        1423865,
        1423868,
        1423871,
        1423875,
        1423878,
        1423881,
        1423884,
        1423887,
        1423890,
        1423893,
        1423896,
        1423899,
        1423902,
        1423905,
        1423908,
        1423911,
        1423914,
        1423918,
        1423921,
        1423925,
        1423928,
        1423931,
        1423934,
        1423941,
        1423948,
        1423952,
        1423958,
        1423960,
        1423962,
        1423964,
        1423965,
        1423968,
    ),
    (
        1423973,
        1423976,
        1423983,
        1423990,
        1423993,
        1424000,
        1424004,
        1424010,
        1424012,
        1424014,
        1424016,
        1424017,
        1424020,
    ),
    (
        1424025,
        1424028,
        1424032,
        1424039,
        1424042,
        1424049,
        1424053,
        1424059,
        1424061,
        1424063,
        1424065,
        1424066,
        1424069,
    ),
    (
        1424074,
        1424080,
        1424084,
        1424091,
        1424097,
        1424104,
        1424108,
        1424114,
        1424116,
        1424118,
        1424120,
        1424121,
        1424124,
    ),
    (
        1424129,
        1424133,
        1424139,
        1424145,
        1424151,
        1424157,
        1424163,
        1424169,
        1424175,
        1424181,
        1424188,
        1424195,
        1424199,
        1424205,
        1424207,
        1424209,
        1424211,
        1424212,
        1424215,
    ),
    (
        1424220,
        1424224,
        1424230,
        1424236,
        1424242,
        1424248,
        1424254,
        1424261,
        1424267,
        1424274,
        1424280,
        1424287,
        1424293,
        1424300,
        1424306,
        1424312,
        1424318,
        1424324,
        1424325,
    ),
    (
        1424330,
        1424334,
        1424340,
        1424346,
        1424352,
        1424358,
        1424364,
        1424370,
        1424377,
        1424384,
        1424388,
        1424394,
        1424396,
        1424398,
        1424400,
        1424401,
        1424404,
    ),
    (
        1424409,
        1424415,
        1424419,
        1424426,
        1424432,
        1424439,
        1424443,
        1424449,
        1424451,
        1424453,
        1424455,
        1424456,
        1424459,
    ),
    (
        1424464,
        1424468,
        1424474,
        1424480,
        1424486,
        1424492,
        1424498,
        1424504,
        1424506,
        1424508,
        1424515,
        1424522,
        1424523,
        1424526,
    ),
    (
        1424531,
        1424537,
        1424543,
        1424545,
        1424548,
        1424555,
        1424556,
        1424557,
        1424558,
        1424560,
        1424561,
    ),
)
EMPTY_TRACE = (
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
PATH_PREFIX = (
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
)
RESERVE_ZERO_TRACE = (
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
)
PATH_SUFFIX = (0x9A90C, 0x9A90E, 0x9A927, 0x9A928, 0x9A92A, 0x9A92B, 0x9A92C)
_read, _write, _pages = string._read, string._write, string._pages


class EmptyRecordCopyError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise EmptyRecordCopyError(message)


def _same(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return set(a) == set(b) and all(
            any(type(k) is type(j) and k == j for j in b) and _same(a[k], b[k])
            for k in a
        )
    if type(a) in (list, tuple):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _validate(pages, registers, xmm, return_address, entry_flags):
    _require(
        type(registers) is dict
        and set(registers) == set(REGISTERS)
        and all(
            type(k) is str and type(v) is int and 0 <= v <= U32
            for k, v in registers.items()
        ),
        "invalid record copy registers",
    )
    _require(
        type(xmm) is dict
        and set(xmm) == set(XMM)
        and all(
            type(k) is str and type(v) is int and 0 <= v < 2**128
            for k, v in xmm.items()
        ),
        "invalid record copy XMM",
    )
    _require(
        type(entry_flags) is int
        and 0 <= entry_flags <= U32
        and entry_flags & ~0xAD7 == 0
        and entry_flags & 2 == 2,
        "record copy ordinary DF-clear flags differ",
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
        "invalid record copy pages",
    )
    g, d = registers["esp"], registers["ecx"]
    _require(72 <= g and g + 8 <= U32, "record copy frame wraps")
    s = int.from_bytes(_read(pages, g + 4, 4), "little")
    _require(
        s > 0 and d > 0 and s + RECORD_BYTES <= U32 and d + RECORD_BYTES <= U32,
        "record copy object extent wraps or null",
    )
    spans = (
        (g - 72, g + 8),
        (s, s + RECORD_BYTES),
        (d, d + RECORD_BYTES),
        (0, 4),
        (COOKIE, COOKIE + 4),
    )
    for i, (left, right) in enumerate(spans):
        _read(pages, left, right - left)
        _require(
            all(
                right <= BASE + a or BASE + a + n <= left
                for a, (n, h) in BODY_PINS.items()
            ),
            "record copy data overlaps selected code",
        )
        _require(
            all(right <= lo or hi <= left for lo, hi in spans[i + 1 :]),
            "record copy data spans overlap",
        )
    _require(
        type(return_address) is int
        and 0 < return_address <= U32
        and all(not (lo <= return_address < hi) for lo, hi in spans)
        and all(
            not (BASE + a <= return_address < BASE + a + n)
            for a, (n, h) in BODY_PINS.items()
        ),
        "record copy return overlaps data or selected code",
    )
    _require(
        int.from_bytes(_read(pages, g, 4), "little") == return_address,
        "record copy installed return differs",
    )
    for offset in STRING_OFFSETS:
        _require(
            _read(pages, s + offset, 1) == b"\0"
            and _read(pages, s + offset + 16, 4) == bytes(4)
            and int.from_bytes(_read(pages, s + offset + 20, 4), "little") == 15,
            "record copy source empty inline string differs",
        )
    _require(
        _read(pages, s + 0xCC, 12) == bytes(12), "record copy source path is not empty"
    )
    return g, s, d


def apply(*, pages, registers, xmm, return_address, entry_flags):
    try:
        return _apply(pages, registers, xmm, return_address, entry_flags)
    except EmptyRecordCopyError:
        raise
    except Exception as exc:
        raise EmptyRecordCopyError(str(exc)) from exc


def _apply(pages, registers, xmm, return_address, entry_flags):
    g, s, d = _validate(pages, registers, xmm, return_address, entry_flags)
    f = g - 4
    memory = {p: bytearray(b) for p, b in pages.items()}
    events, boundaries = [], []
    regs = dict(registers)
    seh = int.from_bytes(_read(pages, 0, 4), "little")
    cookie = int.from_bytes(_read(pages, COOKIE, 4), "little")

    def event(access, address, width, value):
        if access == "write":
            _write(memory, address, value.to_bytes(width, "little"))
        else:
            _require(
                int.from_bytes(_read(memory, address, width), "little") == value,
                "record copy expected read differs",
            )
        events.append(dict(access=access, address=address, width=width, value=value))

    def w(address, value, width=4):
        event("write", address, width, value)

    def r(address, value, width=4):
        event("read", address, width, value)

    def boundary(kind, name, index, endpoint, flags, mask=0x8D5):
        boundaries.append(
            dict(
                kind=kind,
                name=name,
                index=index,
                registers=dict(regs),
                xmm=dict(xmm),
                pages=_pages(memory),
                events=copy.deepcopy(events),
                flags=flags,
                flag_mask=mask,
                df=0,
                endpoint=BASE + endpoint,
            )
        )

    def fields(rows):
        for offset, width in rows:
            value = int.from_bytes(_read(memory, s + offset, width), "little")
            r(s + offset, value, width)
            w(d + offset, value, width)

    for at, value in ((g - 4, registers["ebp"]), (g - 8, U32), (g - 12, 0x7B5837)):
        w(at, value)
    r(0, seh)
    for at, value in (
        (g - 16, seh),
        (g - 20, d),
        (g - 24, registers["esi"]),
        (g - 28, registers["edi"]),
    ):
        w(at, value)
    r(COOKIE, cookie)
    w(g - 32, cookie ^ f)
    w(0, g - 16)
    w(g - 20, d)
    r(g + 4, s)
    regs.update(esi=d, edi=s, ebp=f, esp=g - 32)
    fields(
        tuple((at, 4) for at in (0, 4, 8, 12, 16))
        + ((0x14, 1),)
        + tuple((at, 4) for at in range(0x18, 0x30, 4))
        + ((0x30, 1), (0x31, 1), (0x34, 4))
    )

    def empty(index):
        offset, continuation = STRING_OFFSETS[index], STRING_RETURNS[index]
        q, t, c = d + offset, s + offset, g - 48
        if index == 1:
            w(g - 8, 0)
        elif index in (2, 3):
            w(g - 8, index - 1, 1)
        elif index == 6:
            w(g - 8, 6, 1)
        if index != 7:
            w(q + 20, 15)
            w(q + 16, 0)
            r(q + 20, 15)
            w(g - 36, U32)
            w(g - 40, 0)
            w(g - 44, t)
            w(q, 0, 1)
        else:
            w(g - 36, U32)
            w(g - 40, 0)
            w(q + 20, 15)
            w(q + 16, 0)
            w(g - 44, t)
            w(q, 0, 1)
        w(c, BASE + continuation)
        regs.update(
            eax=(t if index == 7 else q),
            ecx=q,
            edx=(s + STRING_OFFSETS[6] if index == 7 else t),
            esp=c,
        )
        boundary("string", "entry", index, 0x80D0, 0x85)
        child_args = dict(
            pages=_pages(memory),
            registers=dict(regs),
            xmm=dict(xmm),
            return_address=BASE + continuation,
            entry_flags=0x85 | 2,
        )
        rows = (
            ("write", c - 4, 4, f),
            ("write", c - 8, 4, registers["ebx"]),
            ("read", c + 4, 4, t),
            ("write", c - 12, 4, d),
            ("read", c + 8, 4, 0),
            ("write", c - 16, 4, s),
            ("read", t + 16, 4, 0),
            ("read", c + 12, 4, U32),
            ("read", q + 20, 4, 15),
            ("read", q + 20, 4, 15),
            ("write", q + 16, 4, 0),
            ("read", c - 16, 4, s),
            ("read", c - 12, 4, d),
            ("read", c - 8, 4, registers["ebx"]),
            ("write", q, 1, 0),
            ("read", c - 4, 4, f),
            ("read", c, 4, BASE + continuation),
        )
        before = len(events)
        for row in rows:
            event(*row)
        regs.update(eax=q, ecx=0, esp=g - 32)
        wanted = dict(
            source_address=t,
            destination_address=q,
            registers=dict(regs),
            xmm=dict(xmm),
            pages=_pages(memory),
            events=copy.deepcopy(events[before:]),
            flags=0x85,
            flag_mask=0x8D5,
            df=0,
            endpoint=BASE + continuation,
            trace_rvas=[f"0x{pc:08x}" for pc in EMPTY_TRACE],
        )
        child = string.apply(**child_args)
        _require(_same(child, wanted), "record copy empty string primitive differs")
        boundary("string", "return", index, continuation, 0x85)

    for index in range(5):
        if index == 4:
            w(g - 8, 3, 1)
            fields(((0x98, 4), (0x9C, 4), (0xA0, 4)))
        empty(index)
    w(g - 8, 4, 1)
    fields(
        ((0xBC, 4), (0xC0, 4), (0xC4, 1), (0xC5, 1), (0xC6, 1), (0xC7, 1), (0xC8, 4))
    )
    w(g - 36, s + 0xCC)
    w(g - 40, BASE + 0x15BBCA)
    p, j, h = g - 40, s + 0xCC, d + 0xCC
    regs.update(eax=j, ecx=h, edx=s + 0xA4, esp=p)
    boundary("path", "entry", 0, 0x9A8E0, 0x85)
    for at, value in ((p - 4, f), (p - 8, d), (p - 12, s)):
        w(at, value)
    r(p + 4, j)
    for at in (h, h + 4, h + 8):
        w(at, 0)
    r(j + 4, 0)
    r(j, 0)
    w(p - 16, 0)
    w(p - 20, BASE + 0x9A90C)
    regs.update(eax=0, esi=h, edi=j, ebp=p - 4, esp=p - 20)
    boundary("reserve", "entry", 0, 0x9AC40, 0x44, 0xC5)
    for at, value in ((p - 24, p - 4), (p - 28, h), (p - 32, j)):
        w(at, value)
    r(p - 16, 0)
    for at in (h, h + 4, h + 8):
        w(at, 0)
    for at, value in (
        (p - 32, j),
        (p - 28, h),
        (p - 24, p - 4),
        (p - 20, BASE + 0x9A90C),
    ):
        r(at, value)
    regs.update(esp=p - 12)
    boundary("reserve", "return", 0, 0x9A90C, 0x44, 0x8C5)
    for at, value in ((p - 12, s), (p - 8, d), (p - 4, f), (p, BASE + 0x15BBCA)):
        r(at, value)
    regs.update(eax=h, esi=d, edi=s, ebp=f, esp=g - 32)
    boundary("path", "return", 0, 0x15BBCA, 0x44, 0x8C5)
    w(g - 8, 5, 1)
    fields(((0xD8, 4), (0xDC, 4)))
    empty(5)
    empty(6)
    w(g - 8, 7, 1)
    fields(((0x110, 4), (0x114, 4)))
    empty(7)
    fields(((0x130, 4),))
    r(g - 16, seh)
    w(0, seh)
    for at, value in (
        (g - 32, cookie ^ f),
        (g - 28, registers["edi"]),
        (g - 24, registers["esi"]),
        (g - 4, registers["ebp"]),
        (g, return_address),
    ):
        r(at, value)
    trace = []
    for index, segment in enumerate(OWNER_SEGMENTS):
        trace.extend(segment)
        if index == 5:
            trace.extend(PATH_PREFIX + RESERVE_ZERO_TRACE + PATH_SUFFIX)
        elif index < 9:
            trace.extend(EMPTY_TRACE)
    _require(
        len(trace) == 492 and len(events) == 315 and len(boundaries) == 20,
        "record copy path accounting differs",
    )
    return dict(
        source_address=s,
        record_address=d,
        record_bytes=_read(memory, d, RECORD_BYTES),
        source_snapshot=_read(memory, s, RECORD_BYTES),
        registers=dict(registers, eax=d, ecx=cookie ^ f, edx=s + 0xF8, esp=g + 8),
        xmm=dict(xmm),
        pages=_pages(memory),
        events=events,
        flags=0x85,
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
        trace_rvas=[f"0x{pc:08x}" for pc in trace],
        boundaries=boundaries,
    )
