"""Actual-page movement record copy with eight empty strings and a path count zero through511.

FS base is zero. This selected normal return saves a cookie but calls no cookie
checker, destructor, unwind or failure handler. One successful ordinary allocation
response is supplied; the path is copied through a complete logical child law.
"""

from __future__ import annotations
import copy
from src.observatory import native_movement_empty_string_copy_semantics as string
from src.observatory import native_movement_path_small_clone_semantics as path

BASE, U32 = 0x400000, 0xFFFFFFFF
REGISTERS, XMM = string.REGISTERS, string.XMM
COOKIE = 0x00893F28
ANALYSIS_KIND = "pe_native_movement_effect_record_small_copy_semantics"
IMPORT = path.IMPORT
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
BODY_PINS.update(
    {
        a: (b - a, h)
        for a, b, h in (
            (
                0x8ABA0,
                0x8ABCB,
                "92494ea2dfd86d06ce373c9837f55d42e6c62746bd9c2c3c26d2a8af6abe938b",
            ),
            (
                0x8A920,
                0x8A97B,
                "e13e3be9b5e53d78d61aaaacc91b9c7c3183b77ef1f005bd2010bc1aa9b9830e",
            ),
            (
                0x3574DB,
                0x35750E,
                "452b4c981b0a2567c6f4fc35b20076deca45a6b3509707358212028d21db5bfa",
            ),
            (
                0x379F52,
                0x379F5D,
                "831e215b24984219b6d6d7ce812127a420a48782704f0fef1630b1b8050cabbd",
            ),
            (
                0x38942B,
                0x389479,
                "d97ee587f29bfdaf154ca653059e883b67b56713a5d96643356a4edf6e3edde8",
            ),
        )
    }
)
_read, _write, _pages = string._read, string._write, string._pages


class SmallRecordCopyError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise SmallRecordCopyError(message)


for _key, _pin in path.SOURCE_PINS.items():
    _require(
        _key not in SOURCE_PINS or SOURCE_PINS[_key] == _pin,
        "small record copy source identity conflict",
    )
    SOURCE_PINS[_key] = _pin


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


COMMON = {"registers", "xmm", "pages", "events", "flags", "flag_mask", "df", "endpoint"}
CLONE_KEYS = COMMON | {
    "geometry",
    "trace_rvas",
    "boundaries",
    "allocation_packet",
    "scalar_packet",
    "imported",
    "source_snapshot",
}
_same_packet = _same


def _events_schema(events):
    _require(
        type(events) is list
        and all(
            type(row) is dict
            and set(row) == {"access", "address", "width", "value"}
            and all(type(k) is str for k in row)
            and type(row["access"]) is str
            and row["access"] in ("read", "write")
            and type(row["address"]) is int
            and 0 <= row["address"] <= U32
            and type(row["width"]) is int
            and row["width"] in (1, 2, 4)
            and row["address"] + row["width"] <= 2**32
            and type(row["value"]) is int
            and 0 <= row["value"] < 2 ** (8 * row["width"])
            for row in events
        ),
        "small record copy typed events differ",
    )


def _gpr_schema(registers):
    _require(
        type(registers) is dict
        and set(registers) == set(REGISTERS)
        and all(
            type(k) is str and type(v) is int and 0 <= v <= U32
            for k, v in registers.items()
        ),
        "small record copy typed GPR differs",
    )


def _common_schema(packet, page_keys, *, trace=False):
    _gpr_schema(packet["registers"])
    _require(
        type(packet["xmm"]) is dict
        and set(packet["xmm"]) == set(XMM)
        and all(
            type(k) is str and type(v) is int and 0 <= v < 2**128
            for k, v in packet["xmm"].items()
        ),
        "small record copy typed XMM differs",
    )
    _require(
        type(packet["pages"]) is dict
        and set(packet["pages"]) == page_keys
        and all(
            type(p) is int
            and 0 <= p <= 0xFFFFF000
            and p % 4096 == 0
            and type(b) is bytes
            and len(b) == 4096
            for p, b in packet["pages"].items()
        ),
        "small record copy typed pages differ",
    )
    _events_schema(packet["events"])
    _require(
        type(packet["flags"]) is int
        and 0 <= packet["flags"] <= U32
        and type(packet["flag_mask"]) is int
        and packet["flag_mask"] in (0xC5, 0x8C5, 0x8D5, 0xFFFFFFFF)
        and packet["flags"] & ~packet["flag_mask"] == 0
        and _same_packet(packet["df"], 0)
        and type(packet["endpoint"]) is int
        and 0 < packet["endpoint"] <= U32,
        "small record copy typed state differs",
    )
    if trace:
        _require(
            type(packet["trace_rvas"]) is list
            and all(
                type(pc) is str
                and len(pc) == 10
                and pc.startswith("0x")
                and pc == f"0x{int(pc,16):08x}"
                for pc in packet["trace_rvas"]
            ),
            "small record copy typed trace differs",
        )


def _closed(packet, keys):
    _require(
        type(packet) is dict
        and set(packet) == keys
        and all(type(k) is str for k in packet),
        "small record copy child envelope differs",
    )


def _boundary_schema(packet, page_keys):
    _closed(packet, COMMON)
    _common_schema(packet, page_keys)


def _import_schema(packet, page_keys, extra):
    _closed(packet, COMMON | extra | {"entry_esp", "words"})
    _common_schema(packet, page_keys)
    _require(
        type(packet["entry_esp"]) is int
        and _same_packet(packet["endpoint"], IMPORT)
        and packet["entry_esp"] == packet["registers"]["esp"]
        and type(packet["words"]) is list
        and len(packet["words"]) == 4
        and all(type(v) is int and 0 <= v <= U32 for v in packet["words"]),
        "small record copy typed import differs",
    )


def _clone_schema(child, page_keys, count):
    _closed(child, CLONE_KEYS)
    _common_schema(child, page_keys, trace=True)
    _require(
        _same_packet(child["endpoint"], BASE + 0x15BBCA)
        and type(child["source_snapshot"]) is bytes
        and len(child["source_snapshot"]) == 8 * count,
        "small record copy clone return differs",
    )
    _closed(
        child["geometry"],
        {"entry", "source", "destination", "source_header", "destination_header"},
    )
    _require(
        all(type(v) is int and 0 <= v <= U32 for v in child["geometry"].values()),
        "small record copy typed clone geometry differs",
    )
    names = {"parent_entry", "reserve_entry", "reserve_return"}
    if count:
        names |= {
            "allocation_entry",
            "allocation_return",
            "scalar_entry",
            "scalar_return",
        }
    _closed(child["boundaries"], names)
    for state in child["boundaries"].values():
        _boundary_schema(state, page_keys)
    if not count:
        _require(
            child["allocation_packet"] is None
            and child["scalar_packet"] is None
            and child["imported"] is None,
            "small record copy empty clone children differ",
        )
    else:
        allocation = child["allocation_packet"]
        _closed(
            allocation,
            {
                "relation",
                "registers",
                "flags",
                "flag_mask",
                "stack",
                "payload",
                "events",
            },
        )
        _gpr_schema(allocation["registers"])
        _events_schema(allocation["events"])
        _closed(allocation["relation"], {"result", "request", "metadata"})
        _require(
            type(allocation["relation"]["result"]) is int
            and 0 <= allocation["relation"]["result"] <= U32
            and _same_packet(allocation["relation"]["request"], 8 * count)
            and allocation["relation"]["metadata"] is None
            and type(allocation["flags"]) is int
            and allocation["flags"] & ~0x8D5 == 0
            and _same_packet(allocation["flag_mask"], 0x8D5)
            and type(allocation["stack"]) is bytes
            and len(allocation["stack"]) == 8192
            and type(allocation["payload"]) is bytes
            and len(allocation["payload"]) == 16384,
            "small record copy typed allocation differs",
        )
        _closed(child["scalar_packet"], COMMON | {"trace_rvas", "source_snapshot"})
        _common_schema(child["scalar_packet"], page_keys, trace=True)
        _require(
            type(child["scalar_packet"]["source_snapshot"]) is bytes
            and len(child["scalar_packet"]["source_snapshot"]) == 8 * count,
            "small record copy typed scalar snapshot differs",
        )
        _import_schema(child["imported"], page_keys, set())


def _add_flags(left, right):
    result = (left + right) & U32
    return (
        int(left + right > U32)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | (int(bool((left ^ right ^ result) & 16)) << 4)
        | (int(result == 0) << 6)
        | ((result >> 31) << 7)
        | (int(bool(~(left ^ right) & (left ^ result) & 0x80000000)) << 11)
    )


def _replay_path(original, events, allowed):
    """Bind actual page bytes and reads; nested instruction semantics stay trusted."""
    memory = {p: bytearray(raw) for p, raw in original.items()}
    for row in events:
        access, at, width, value = (
            row[k] for k in ("access", "address", "width", "value")
        )
        _require(width == 4, "small record copy path DWORD width differs")
        if access == "read":
            _require(
                int.from_bytes(_read(memory, at, width), "little") == value,
                "small record copy path read differs",
            )
        else:
            _read(memory, at, width)
            _require(
                any(lo <= at and at + width <= hi for lo, hi in allowed),
                "small record copy path write outside selected extents",
            )
            _write(memory, at, value.to_bytes(width, "little"))
    return _pages(memory)


def _check_path_join(child, initial, p, j, h, o, destination, count):
    """Close types and the installed owner join before adopting any child pages.

    Full nested instruction and primitive semantics are the reviewed child's
    trust boundary; this does not reject every coordinated semantic forgery.
    """
    original = initial["pages"]
    size = count * 8
    _clone_schema(child, set(original), count)
    _require(
        _same(
            child["geometry"],
            dict(
                entry=p,
                source=o,
                destination=destination,
                source_header=j,
                destination_header=h,
            ),
        ),
        "small record copy path geometry differs",
    )
    snapshot = _read(original, o, size)
    _require(
        _same(child["source_snapshot"], snapshot),
        "small record copy path snapshot differs",
    )
    wanted_regs = dict(initial["registers"], eax=h, ecx=h, esp=p + 8)
    if count:
        wanted_regs.update(ecx=int.from_bytes(snapshot[-4:], "little"), edx=o + size)
    _require(
        _same(child["registers"], wanted_regs)
        and _same(child["xmm"], initial["xmm"])
        and _same(child["flags"], _add_flags(p - 28, 16) if count else 0x44)
        and _same(child["flag_mask"], 0x8D5 if count else 0x8C5),
        "small record copy complete path return differs",
    )
    _require(
        len(child["events"]) == (75 + 4 * count if count else 26)
        and len(child["trace_rvas"]) == (116 + 10 * count if count else 37),
        "small record copy path count differs",
    )
    allowed = [(p - 88, p), (h, h + 12)]
    if count:
        allowed.append((destination, destination + size))
    replayed = _replay_path(original, child["events"], allowed)
    _require(
        _same(replayed, child["pages"]), "small record copy complete path pages differ"
    )
    end = destination + size
    _require(
        _read(replayed, h, 12)
        == b"".join(v.to_bytes(4, "little") for v in (destination, end, end)),
        "small record copy path header differs",
    )
    if count:
        _require(
            _read(replayed, destination, size) == snapshot,
            "small record copy copied path bytes differ",
        )
        _require(
            _same(
                child["allocation_packet"]["relation"],
                dict(result=destination, request=size, metadata=None),
            )
            and _same(child["scalar_packet"]["source_snapshot"], snapshot),
            "small record copy nested request or snapshot differs",
        )
        allocated = child["allocation_packet"]
        ae = child["boundaries"]["allocation_entry"]
        ar = child["boundaries"]["allocation_return"]
        stack_base = min((p - 88) & ~4095, 0xFFFFE000)
        _require(
            _same(allocated["registers"], ar["registers"])
            and _same(allocated["flags"], ar["flags"])
            and _same(allocated["flag_mask"], ar["flag_mask"])
            and _same(allocated["events"], ar["events"][len(ae["events"]) :])
            and allocated["stack"] == _read(ar["pages"], stack_base, 8192)
            and allocated["payload"] == _read(ar["pages"], path.DATA, 16384)
            and _same(ar["endpoint"], BASE + 0x9AC78),
            "small record copy allocation checkpoint join differs",
        )
        scalar = child["scalar_packet"]
        se = child["boundaries"]["scalar_entry"]
        sr = child["boundaries"]["scalar_return"]
        _require(
            all(_same(scalar[key], sr[key]) for key in COMMON - {"events"})
            and _same(scalar["events"], sr["events"][len(se["events"]) :])
            and len(scalar["events"]) == 6 + 4 * count
            and len(scalar["trace_rvas"]) == 11 + 10 * count
            and _same(sr["endpoint"], BASE + 0x9A921),
            "small record copy scalar checkpoint join differs",
        )
    names = ["parent_entry", "reserve_entry"]
    if count:
        names += ["allocation_entry", "allocation_return"]
    names += ["reserve_return"]
    if count:
        names += ["scalar_entry", "scalar_return"]
    _require(
        list(child["boundaries"]) == names,
        "small record copy path boundary order differs",
    )
    wanted_entry = dict(
        registers=dict(initial["registers"]),
        xmm=dict(initial["xmm"]),
        pages=dict(original),
        events=[],
        flags=initial["entry_flags"],
        flag_mask=0xFFFFFFFF,
        df=0,
        endpoint=BASE + 0x9A8E0,
    )
    _require(
        _same(child["boundaries"]["parent_entry"], wanted_entry),
        "small record copy actual path entry differs",
    )
    states = list(child["boundaries"].values())
    if child["imported"] is not None:
        state = child["imported"]
        _require(
            _same(state["entry_esp"], p - 88)
            and _same(state["words"], [BASE + 0x389463, path.HEAP, 0, size]),
            "small record copy installed allocation frame differs",
        )
        states.append(state)
    for state in states:
        prefix = state["events"]
        _require(
            _same(prefix, child["events"][: len(prefix)])
            and _same(state["pages"], _replay_path(original, prefix, allowed))
            and _same(state["xmm"], initial["xmm"]),
            "small record copy actual path checkpoint differs",
        )


def _validate(pages, registers, xmm, return_address, entry_flags, allocation_result):
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
    _require(128 <= g and g + 8 <= U32, "record copy frame wraps")
    s = int.from_bytes(_read(pages, g + 4, 4), "little")
    _require(
        s > 0 and d > 0 and s + RECORD_BYTES <= U32 and d + RECORD_BYTES <= U32,
        "record copy object extent wraps or null",
    )
    spans = (
        (g - 128, g + 8),
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
        type(allocation_result) is int and 0 <= allocation_result <= U32,
        "small record copy allocation result differs",
    )
    o = int.from_bytes(_read(pages, s + 0xCC, 4), "little")
    end = int.from_bytes(_read(pages, s + 0xD0, 4), "little")
    _require(end >= o and (end - o) % 8 == 0, "small record copy path count differs")
    count, size = (end - o) // 8, end - o
    _require(count <= 511, "small record copy requires ordinary small count")
    # The clone child requires a complete two-page allocator stack window even
    # when count zero executes no allocation. No runtime global is read here.
    base = min((g - 128) & ~4095, 0xFFFFE000)
    _read(pages, base, 8192)
    if count:
        _require(
            o > 0
            and allocation_result >= path.DATA
            and allocation_result + size <= path.DATA + 16384,
            "small record copy positive path geometry differs",
        )
        _read(pages, path.DATA, 16384)
        runtime = tuple(
            (word & ~4095, (word & ~4095) + 4096)
            for word in (path.HEAP_GLOBAL, path.ALLOC_IAT)
        )
        for lo, hi in runtime:
            _read(pages, lo, hi - lo)
        _require(
            int.from_bytes(_read(pages, path.HEAP_GLOBAL, 4), "little") == path.HEAP
            and int.from_bytes(_read(pages, path.ALLOC_IAT, 4), "little") == IMPORT,
            "small record copy ordinary runtime words differ",
        )
        _require(
            base + 8192 <= path.DATA or path.DATA + 16384 <= base,
            "small record copy allocation stack overlaps DATA",
        )
        _require(
            all(
                right <= lo or hi <= left for left, right in spans for lo, hi in runtime
            )
            and all(base + 8192 <= lo or hi <= base for lo, hi in runtime),
            "small record copy protected data overlaps runtime globals",
        )
        _require(
            all(not (lo <= return_address < hi) for lo, hi in runtime),
            "small record copy return overlaps runtime globals",
        )
        buffers = ((o, end), (allocation_result, allocation_result + size))
        for left, right in buffers:
            _read(pages, left, size)
            _require(
                not (left <= return_address < right),
                "small record copy return overlaps path buffer",
            )
            _require(
                all(right <= lo or hi <= left for lo, hi in spans + runtime),
                "small record copy path buffer overlaps protected data",
            )
            _require(
                all(
                    right <= BASE + a or BASE + a + n <= left
                    for a, (n, h) in BODY_PINS.items()
                ),
                "small record copy path buffer overlaps code",
            )
        _require(
            end <= allocation_result or allocation_result + size <= o,
            "small record copy path buffers overlap",
        )
    else:
        _require(
            allocation_result == 0,
            "small record copy zero count requires zero allocation",
        )
    return g, s, d, o, count


def apply(*, pages, registers, xmm, return_address, entry_flags, allocation_result):
    try:
        return _apply(
            pages, registers, xmm, return_address, entry_flags, allocation_result
        )
    except SmallRecordCopyError:
        raise
    except Exception as exc:
        raise SmallRecordCopyError(str(exc)) from exc


def _apply(pages, registers, xmm, return_address, entry_flags, allocation_result):
    g, s, d, o, count = _validate(
        pages, registers, xmm, return_address, entry_flags, allocation_result
    )
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
    prefix = copy.deepcopy(events)
    child_input = dict(
        pages=_pages(memory),
        registers=dict(regs),
        xmm=dict(xmm),
        return_address=BASE + 0x15BBCA,
        entry_flags=(entry_flags & ~0x8D5) | 0x85,
        allocation_result=allocation_result,
    )
    joined = path.apply(**child_input)
    _check_path_join(joined, child_input, p, j, h, o, allocation_result, count)
    if count:
        for index, (name, state) in enumerate(joined["boundaries"].items()):
            b = copy.deepcopy(state)
            b.update(kind="path", name=name, index=index, events=prefix + b["events"])
            boundaries.append(b)
    else:
        zero_names = (
            ("parent_entry", "path", "entry"),
            ("reserve_entry", "reserve", "entry"),
            ("reserve_return", "reserve", "return"),
        )
        for name, kind, phase in zero_names:
            b = copy.deepcopy(joined["boundaries"][name])
            b.update(kind=kind, name=phase, index=0, events=prefix + b["events"])
            if name == "parent_entry":
                b.update(flags=0x85, flag_mask=0x8D5)
            boundaries.append(b)
        b = {key: copy.deepcopy(joined[key]) for key in COMMON}
        b.update(kind="path", name="return", index=0, events=prefix + b["events"])
        boundaries.append(b)
    events.extend(copy.deepcopy(joined["events"]))
    for page, raw in joined["pages"].items():
        memory[page][:] = raw
    regs = dict(joined["registers"])
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
            trace.extend(int(pc, 16) for pc in joined["trace_rvas"])
        elif index < 9:
            trace.extend(EMPTY_TRACE)
    _require(
        len(trace) == (571 + 10 * count if count else 492)
        and len(events) == (364 + 4 * count if count else 315)
        and len(boundaries) == (23 if count else 20),
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
        path_packet=copy.deepcopy(joined),
    )
