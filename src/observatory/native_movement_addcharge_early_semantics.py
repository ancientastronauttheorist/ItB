"""Actual-page AddCharge whose inner count-zero/one AddMove returns AL zero.

Reviewed child semantic internals are trusted behind closed typed envelopes.
A successful ordinary allocation/free response is a supplied logical premise.
"""

from __future__ import annotations
import copy
from src.observatory import native_movement_addmove_early_semantics as move
from src.observatory import native_movement_path_small_clone_semantics as path

BASE, U32, COOKIE = move.BASE, move.U32, move.COOKIE
REGISTERS, XMM = move.REGISTERS, move.XMM
HEAP_GLOBAL, FREE_IAT, HEAP, IMPORT, ERROR = (
    move.HEAP_GLOBAL,
    move.FREE_IAT,
    move.HEAP,
    move.IMPORT,
    move.ERROR,
)
ALLOC_IAT, DATA = path.ALLOC_IAT, path.DATA
_read, _write, _pages = move._read, move._write, move._pages
_same_packet, _add_flags, _test = move._same_packet, path._add_flags, move._test
deallocator, _event_law = move.deallocator, move._event_law
ANALYSIS_KIND = "pe_native_movement_addcharge_early_semantics"
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
MOVE_KEYS = COMMON | {
    "path",
    "trace_rvas",
    "free_entry",
    "free_return",
    "free_packet",
    "imported",
    "cookie_entry",
}
FREE_KEYS = {
    "registers",
    "flags",
    "flag_mask",
    "events",
    "stack",
    "error",
    "stop",
    "protocol",
}


class AddChargeEarlyError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise AddChargeEarlyError(message)


def _normalize(operation):
    try:
        return operation()
    except AddChargeEarlyError:
        raise
    except Exception as exc:
        raise AddChargeEarlyError(str(exc)) from exc


SOURCE_PINS = dict(move.SOURCE_PINS)
for _key, _pin in path.SOURCE_PINS.items():
    _require(
        _key not in SOURCE_PINS or SOURCE_PINS[_key] == _pin,
        "early AddCharge source identity conflict",
    )
    SOURCE_PINS[_key] = _pin
BODY_PINS = dict(move.BODY_PINS)
for _start, _end in path.CODE_RANGES:
    _body = move.normal.BODY_PINS[_start]
    _require(
        _body[0] == _end - _start
        and (_start not in BODY_PINS or BODY_PINS[_start] == _body),
        "early AddCharge body identity conflict",
    )
    BODY_PINS[_start] = _body
BODY_PINS[0x2576F0] = (
    138,
    "b4c477b2c8b460c7697bdb236c50c264cbacb68e55189048fc4b536847a6e90a",
)

OWNER_PREFIX = (
    0x2576F0,
    0x2576F1,
    0x2576F3,
    0x2576F5,
    0x2576FA,
    0x257700,
    0x257701,
    0x257702,
    0x257707,
    0x257709,
    0x25770A,
    0x25770D,
    0x257713,
    0x257715,
    0x25771A,
    0x25771D,
    0x257720,
    0x257727,
    0x257729,
    0x25772C,
    0x257732,
    0x257733,
)
OWNER_CALL = (0x257738, 0x25773A)
OWNER_PREDICATE = (0x25773F, 0x257741, 0x25774D, 0x257750, 0x257752)
OWNER_FREE_CALL = (0x257754, 0x257757, 0x257759, 0x25775B, 0x25775E, 0x25775F, 0x257760)
OWNER_SUFFIX = (0x257768, 0x25776B, 0x257772, 0x257773, 0x257774, 0x257776, 0x257777)


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
        "early AddCharge typed events differ",
    )


def _gpr_schema(registers):
    _require(
        type(registers) is dict
        and set(registers) == set(REGISTERS)
        and all(
            type(k) is str and type(v) is int and 0 <= v <= U32
            for k, v in registers.items()
        ),
        "early AddCharge typed GPR differs",
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
        "early AddCharge typed XMM differs",
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
        "early AddCharge typed pages differ",
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
        "early AddCharge typed state differs",
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
            "early AddCharge typed trace differs",
        )


def _closed(packet, keys):
    _require(
        type(packet) is dict
        and set(packet) == keys
        and all(type(k) is str for k in packet),
        "early AddCharge child envelope differs",
    )


def _boundary_schema(packet, page_keys):
    _closed(packet, COMMON)
    _common_schema(packet, page_keys)


def _free_schema(packet):
    _closed(packet, FREE_KEYS)
    _gpr_schema(packet["registers"])
    _events_schema(packet["events"])
    _require(
        type(packet["flags"]) is int
        and packet["flags"] & ~0x8D5 == 0
        and _same_packet(packet["flag_mask"], 0x8D5)
        and type(packet["stack"]) is bytes
        and len(packet["stack"]) == 8192
        and type(packet["error"]) is bytes
        and len(packet["error"]) == 4096
        and type(packet["stop"]) is int
        and 0 < packet["stop"] <= U32
        and _same_packet(
            packet["protocol"],
            dict(
                returned=True,
                result=1,
                next_kind=None,
                error_cell=None,
                last_error=None,
            ),
        ),
        "early AddCharge typed free packet differs",
    )


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
        "early AddCharge typed import differs",
    )


def _clone_schema(child, page_keys, count):
    _closed(child, CLONE_KEYS)
    _common_schema(child, page_keys, trace=True)
    _require(
        _same_packet(child["endpoint"], BASE + 0x257738)
        and type(child["source_snapshot"]) is bytes
        and len(child["source_snapshot"]) == 8 * count,
        "early AddCharge clone return differs",
    )
    _closed(
        child["geometry"],
        {"entry", "source", "destination", "source_header", "destination_header"},
    )
    _require(
        all(type(v) is int and 0 <= v <= U32 for v in child["geometry"].values()),
        "early AddCharge typed clone geometry differs",
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
            "early AddCharge empty clone children differ",
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
            and _same_packet(allocation["relation"]["request"], 8)
            and allocation["relation"]["metadata"] is None
            and type(allocation["flags"]) is int
            and allocation["flags"] & ~0x8D5 == 0
            and _same_packet(allocation["flag_mask"], 0x8D5)
            and type(allocation["stack"]) is bytes
            and len(allocation["stack"]) == 8192
            and type(allocation["payload"]) is bytes
            and len(allocation["payload"]) == 16384,
            "early AddCharge typed allocation differs",
        )
        _closed(child["scalar_packet"], COMMON | {"trace_rvas", "source_snapshot"})
        _common_schema(child["scalar_packet"], page_keys, trace=True)
        _require(
            type(child["scalar_packet"]["source_snapshot"]) is bytes
            and len(child["scalar_packet"]["source_snapshot"]) == 8,
            "early AddCharge typed scalar snapshot differs",
        )
        _import_schema(child["imported"], page_keys, set())


def _move_schema(child, page_keys, count):
    _closed(child, MOVE_KEYS)
    _common_schema(child, page_keys, trace=True)
    _require(
        _same_packet(child["endpoint"], BASE + 0x25773F)
        and child["registers"]["eax"] & 255 == 0,
        "early AddCharge requires AL zero",
    )
    _closed(child["path"], {"begin", "end", "capacity", "count", "parameter_bits"})
    _require(
        all(type(v) is int and 0 <= v <= U32 for v in child["path"].values())
        and _same_packet(child["path"]["count"], count),
        "early AddCharge typed Move path differs",
    )
    _boundary_schema(child["cookie_entry"], page_keys)
    if count:
        _boundary_schema(child["free_entry"], page_keys)
        _boundary_schema(child["free_return"], page_keys)
        _free_schema(child["free_packet"])
        _import_schema(child["imported"], page_keys, {"role"})
        _require(
            _same_packet(child["imported"]["role"], "free"),
            "early AddCharge typed Move import role differs",
        )
    else:
        _require(
            all(
                child[k] is None
                for k in ("free_entry", "free_return", "free_packet", "imported")
            ),
            "early AddCharge null Move children differ",
        )


def _sub_flags(left, right):
    result = (left - right) & U32
    return (
        int(left < right)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | (int(bool((left ^ right ^ result) & 16)) << 4)
        | (int(result == 0) << 6)
        | ((result >> 31) << 7)
        | (int(bool((left ^ right) & (left ^ result) & 0x80000000)) << 11)
    )


def _outer_free_law(regs, pages, pointer, stack_base, count):
    """Ordinary capacity below512 and stride8; exact8 fields against the unchanged generic law."""
    v = regs["esp"]
    memory, events, e = _event_law(pages)
    for access, address, value in (
        ("write", v - 4, regs["ebp"]),
        ("read", v + 8, count),
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
                count=count,
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
        int.from_bytes(_read(pages, v, 4), "little") == BASE + 0x257765,
        "movement free installed continuation differs",
    )
    wanted["events"][-1]["value"] = BASE + 0x257765
    wanted["stop"] = BASE + 0x257765
    return wanted


def _validate(pages, registers, xmm, return_address, entry_flags, allocation_result):
    _normalize(
        lambda: move._validate(pages, registers, xmm, return_address, entry_flags)
    )
    _require(
        type(allocation_result) is int and 0 <= allocation_result <= U32,
        "early AddCharge allocation result differs",
    )
    g, h = registers["esp"], registers["ecx"]
    _require(g >= 0x2E4, "early AddCharge frame wraps")
    o, end, capacity, param = (
        int.from_bytes(_read(pages, g + offset), "little") for offset in (4, 8, 12, 16)
    )
    count = (end - o) // 8
    k = (capacity - o) // 8
    windows = {min((g - depth) & ~4095, 0xFFFFE000) for depth in (0x2E4, 136, 72)}
    for base in windows:
        _read(pages, base, 8192)
    spans = [(g - 0x2E4, g + 20), (h, h + 12), (0, 4), (COOKIE, COOKIE + 4)]
    if o:
        spans.extend(
            (
                (o, capacity),
                (ERROR, ERROR + 4096),
                (HEAP_GLOBAL & ~4095, (HEAP_GLOBAL & ~4095) + 4096),
                (FREE_IAT & ~4095, (FREE_IAT & ~4095) + 4096),
            )
        )
        _require(
            all(base + 8192 <= ERROR or ERROR + 4096 <= base for base in windows),
            "early AddCharge stack window overlaps error mapping",
        )
    if count:
        _require(
            DATA <= allocation_result <= DATA + 16384 - 8,
            "early AddCharge allocation outside ordinary DATA",
        )
        _read(pages, DATA, 16384)
        _read(pages, ALLOC_IAT & ~4095, 4096)
        _require(
            int.from_bytes(_read(pages, ALLOC_IAT), "little") == IMPORT,
            "early AddCharge allocation IAT differs",
        )
        spans.append((allocation_result, allocation_result + 8))
        base = min((g - 136) & ~4095, 0xFFFFE000)
        _require(
            base + 8192 <= DATA or DATA + 16384 <= base,
            "early AddCharge allocation stack overlaps DATA",
        )
        _require(
            all(
                base + 8192 <= a or z <= base
                for a, z in spans
                if a in (HEAP_GLOBAL & ~4095, FREE_IAT & ~4095)
            ),
            "early AddCharge allocation stack overlaps runtime globals",
        )
    else:
        _require(
            allocation_result == 0,
            "early AddCharge zero count requires zero allocation",
        )
    for i, (a, b) in enumerate(spans):
        _read(pages, a, b - a)
        _require(
            all(b <= d or z <= a for d, z in spans[i + 1 :]),
            "early AddCharge protected spans overlap",
        )
    codepages = {
        (BASE + a + i) & ~4095
        for a, (size, sha) in BODY_PINS.items()
        for i in range(size)
    }
    _require(
        not codepages.intersection(pages), "early AddCharge pages overlap selected code"
    )
    _require(
        all(not (a <= return_address < b) for a, b in spans)
        and all(
            not (BASE + a <= return_address < BASE + a + size)
            for a, (size, sha) in BODY_PINS.items()
        ),
        "early AddCharge return overlaps protected data or selected body",
    )
    return g, h, o, end, capacity, count, k, param


def apply(*, pages, registers, xmm, return_address, entry_flags, allocation_result):
    return _normalize(
        lambda: _apply(
            pages, registers, xmm, return_address, entry_flags, allocation_result
        )
    )


def _apply(pages, registers, xmm, return_address, entry_flags, allocation_result):
    g, h, o, end, capacity, count, k, param = _validate(
        pages, registers, xmm, return_address, entry_flags, allocation_result
    )
    f = g - 4
    memory = {p: bytearray(b) for p, b in pages.items()}
    events, trace, boundaries, imports, packets = [], [], [], [], {}
    regs, vec = dict(registers), dict(xmm)
    seh = int.from_bytes(_read(pages, 0), "little")
    cookie = int.from_bytes(_read(pages, COOKIE), "little")

    def event(access, at, value):
        if access == "write":
            _write(memory, at, value.to_bytes(4, "little"))
        else:
            _require(
                int.from_bytes(_read(memory, at), "little") == value,
                "early AddCharge expected read differs",
            )
        events.append(dict(access=access, address=at, width=4, value=value))

    def boundary(name, phase, endpoint, flags, mask):
        boundaries.append(
            dict(
                name=name,
                phase=phase,
                registers=dict(regs),
                xmm=dict(vec),
                pages=_pages(memory),
                events=copy.deepcopy(events),
                flags=flags,
                flag_mask=mask,
                df=0,
                endpoint=endpoint,
            )
        )

    for at, v in ((g - 4, registers["ebp"]), (g - 8, U32), (g - 12, 0x7CAA08)):
        event("write", at, v)
    event("read", 0, seh)
    event("write", g - 16, seh)
    event("write", g - 20, registers["esi"])
    event("read", COOKIE, cookie)
    event("write", g - 24, cookie ^ f)
    event("write", 0, g - 16)
    event("read", g + 16, param)
    vec["xmm0"] = param
    for at, v in (
        (g - 8, 0),
        (g + 16, g - 40),
        (g - 28, param),
        (g - 44, g + 4),
        (g - 48, BASE + 0x257738),
    ):
        event("write", at, v)
    regs.update(eax=g + 4, ecx=g - 40, esi=h, ebp=f, esp=g - 48)
    flags = _sub_flags(g - 24, 16)
    trace.extend(f"0x{pc:08x}" for pc in OWNER_PREFIX)
    boundary("clone_argument", "entry", BASE + 0x9A8E0, flags, 0x8D5)
    prefix = copy.deepcopy(events)
    child = _normalize(
        lambda: path.apply(
            pages=_pages(memory),
            registers=dict(regs),
            xmm=dict(vec),
            return_address=BASE + 0x257738,
            entry_flags=move.normal._ordinary(entry_flags, flags),
            allocation_result=allocation_result,
        )
    )
    _clone_schema(child, set(memory), count)
    packets["clone_argument"] = copy.deepcopy(child)
    events.extend(copy.deepcopy(child["events"]))
    trace.extend(child["trace_rvas"])
    memory = {p: bytearray(b) for p, b in child["pages"].items()}
    regs, vec = dict(child["registers"]), dict(child["xmm"])
    boundary(
        "clone_argument", "return", BASE + 0x257738, child["flags"], child["flag_mask"]
    )
    if child["imported"] is not None:
        state = copy.deepcopy(child["imported"])
        state.update(name="clone_argument", events=prefix + state["events"])
        imports.append(state)
    event("write", g - 44, BASE + 0x25773F)
    regs.update(ecx=h, esp=g - 44)
    trace.extend(f"0x{pc:08x}" for pc in OWNER_CALL)
    boundary("addmove", "entry", BASE + 0x257340, child["flags"], child["flag_mask"])
    prefix = copy.deepcopy(events)
    child = _normalize(
        lambda: move.apply(
            pages=_pages(memory),
            registers=dict(regs),
            xmm=dict(vec),
            return_address=BASE + 0x25773F,
            entry_flags=move.normal._ordinary(entry_flags, child["flags"]),
        )
    )
    _move_schema(child, set(memory), count)
    packets["addmove"] = copy.deepcopy(child)
    events.extend(copy.deepcopy(child["events"]))
    trace.extend(child["trace_rvas"])
    memory = {p: bytearray(b) for p, b in child["pages"].items()}
    regs, vec = dict(child["registers"]), dict(child["xmm"])
    boundary("addmove", "return", BASE + 0x25773F, child["flags"], child["flag_mask"])
    if child["imported"] is not None:
        state = copy.deepcopy(child["imported"])
        del state["role"]
        state.update(name="free_clone", events=prefix + state["events"])
        imports.append(state)
    # TEST AL zero skips both latest-record instructions, then TEST original begin.
    event("read", g + 4, o)
    regs["ecx"] = o
    trace.extend(f"0x{pc:08x}" for pc in OWNER_PREDICATE)
    packets["free_original"] = None
    final_flags, final_mask = 0x44, 0x8C5
    if o:
        event("read", g + 12, capacity)
        for at, v in ((g - 28, 8), (g - 32, k), (g - 36, o), (g - 40, BASE + 0x257765)):
            event("write", at, v)
        regs.update(eax=k, ecx=o, esp=g - 40)
        trace.extend(f"0x{pc:08x}" for pc in OWNER_FREE_CALL)
        boundary("free_original", "entry", BASE + 0x7800, _test(k), 0xC5)
        prefix = copy.deepcopy(events)
        base = min((g - 72) & ~4095, 0xFFFFE000)
        free = _outer_free_law(regs, _pages(memory), o, base, k)
        _free_schema(free)
        packets["free_original"] = copy.deepcopy(free)
        importpages = {p: bytearray(b) for p, b in memory.items()}
        for row in free["events"][:16]:
            if row["access"] == "write":
                _write(importpages, row["address"], row["value"].to_bytes(4, "little"))
        v = g - 40
        imports.append(
            dict(
                name="free_original",
                registers=dict(
                    regs, eax=0x1FFFFFFF, ecx=o, edx=7, ebp=v - 16, esp=v - 32
                ),
                xmm=dict(vec),
                pages=_pages(importpages),
                events=prefix + copy.deepcopy(free["events"][:16]),
                flags=_test(o),
                flag_mask=0x8C5,
                df=0,
                endpoint=IMPORT,
                entry_esp=v - 32,
                words=[BASE + 0x389172, HEAP, 0, o],
            )
        )
        events.extend(copy.deepcopy(free["events"]))
        _write(memory, base, free["stack"])
        regs = dict(free["registers"])
        trace.extend(f"0x{pc:08x}" for pc in move.FREE_TRACE)
        boundary(
            "free_original", "return", BASE + 0x257765, free["flags"], free["flag_mask"]
        )
        regs["esp"] += 12
        trace.append("0x00257765")
        final_flags, final_mask = _add_flags(g - 36, 12), 0x8D5
    for access, at, v in (
        ("read", g - 16, seh),
        ("write", 0, seh),
        ("read", g - 24, cookie ^ f),
        ("read", g - 20, registers["esi"]),
        ("read", g - 4, registers["ebp"]),
        ("read", g, return_address),
    ):
        event(access, at, v)
    trace.extend(f"0x{pc:08x}" for pc in OWNER_SUFFIX)
    regs.update(ecx=cookie ^ f, esi=registers["esi"], ebp=registers["ebp"], esp=g + 20)
    _require(
        len(trace) == (284 if count else 155 if o else 115)
        and len(events) == (177 if count else 99 if o else 74)
        and len(boundaries) == (6 if o else 4)
        and len(imports) == (3 if count else 1 if o else 0),
        "early AddCharge selected count differs",
    )
    return dict(
        geometry=dict(entry=g, receiver=h, source_path=o, argument_block=g - 40),
        path=dict(
            begin=o, end=end, capacity=capacity, count=count, parameter_bits=param
        ),
        registers=regs,
        xmm=vec,
        pages=_pages(memory),
        events=events,
        trace_rvas=trace,
        boundaries=boundaries,
        imports=imports,
        child_packets=packets,
        flags=final_flags,
        flag_mask=final_mask,
        df=0,
        endpoint=return_address,
    )
