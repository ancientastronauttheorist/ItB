"""Selected normal AddCharge with ordinary small paths and existing capacity.

Four allocation and four free successes are supplied. Four disjoint eight-byte
entry buffers must fit the selected 12 KiB usable DATA extent; this conservatively
admits counts two through384. Child COMMON envelopes are typed; extra and
nested instruction metadata are trusted. Latest record mode becomes two.
Larger synthetic runtime geometry, gameplay and ownership remain separate.
"""

from __future__ import annotations
import copy
from src.observatory import native_movement_addmove_small_normal_semantics as move
from src.observatory import native_movement_path_small_clone_semantics as path

ANALYSIS_KIND = "pe_native_movement_addcharge_small_normal_semantics"
BASE, U32, COOKIE = move.BASE, move.U32, move.COOKIE
REGISTERS, XMM = move.REGISTERS, move.XMM
_read, _write, _pages, _same = move._read, move._write, move._pages, move._same
BODY_PINS = dict(move.BODY_PINS)
BODY_PINS[0x2576F0] = (
    138,
    "b4c477b2c8b460c7697bdb236c50c264cbacb68e55189048fc4b536847a6e90a",
)
SOURCE_PINS = dict(move.SOURCE_PINS)
OWNER_SEGMENTS = tuple(
    tuple(0x257000 + n for n in seg)
    for seg in (
        (
            0x6F0,
            0x6F1,
            0x6F3,
            0x6F5,
            0x6FA,
            0x700,
            0x701,
            0x702,
            0x707,
            0x709,
            0x70A,
            0x70D,
            0x713,
            0x715,
            0x71A,
            0x71D,
            0x720,
            0x727,
            0x729,
            0x72C,
            0x732,
            0x733,
        ),
        (0x738, 0x73A),
        (
            0x73F,
            0x741,
            0x743,
            0x746,
            0x74D,
            0x750,
            0x752,
            0x754,
            0x757,
            0x759,
            0x75B,
            0x75E,
            0x75F,
            0x760,
        ),
        (0x765, 0x768, 0x76B, 0x772, 0x773, 0x774, 0x776, 0x777),
    )
)


class AddChargeSmallNormalError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise AddChargeSmallNormalError(message)


def _normalize(fn):
    try:
        return fn()
    except AddChargeSmallNormalError:
        raise
    except Exception as exc:
        raise AddChargeSmallNormalError(str(exc)) from exc


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


HEAP_GLOBAL, FREE_IAT, HEAP, IMPORT, ERROR = (
    move.HEAP_GLOBAL,
    move.FREE_IAT,
    move.HEAP,
    move.IMPORT,
    move.ERROR,
)
deallocator = move.deallocator
_event_law = move._event_law
_same_packet = _same
_add_flags = path._add_flags


def _outer_free_law(regs, pages, pointer, stack_base, count):
    """Ordinary count2..511/stride8; exact8 fields against the unchanged generic law."""
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


def _validate(pages, registers, xmm, return_address, entry_flags, allocation_results):
    _require(
        type(allocation_results) is list
        and len(allocation_results) == 4
        and all(
            type(d) is int and 0x06000000 <= d <= 0x06003FF0 for d in allocation_results
        ),
        "normal AddCharge requires four ordinary allocation results",
    )
    # The complete outer shape shares the reviewed normal AddMove input law,
    # with a larger protected frame for its installed child and argument block.
    g, h, o, c, _, _, param, count, capacity_count = move._validate(
        pages, registers, xmm, return_address, entry_flags, allocation_results[1:]
    )
    size = count * 8
    _require(count <= 384, "normal AddCharge selected four-buffer geometry exceeds usable DATA")
    _require(all(d + size <= 0x06004000 for d in allocation_results), "normal AddCharge allocation extents differ")
    _require(g >= 0x364, "normal AddCharge frame wraps")
    _require(g - 0x2A8 >= c, "normal AddCharge append source precedes receiver end")
    spans = [
        (g - 0x364, g + 20),
        (h, h + 12),
        (c, c + 308),
        (o, o + capacity_count * 8),
        (0, 4),
        (COOKIE, COOKIE + 4),
        (move.LITERAL, move.LITERAL + 1),
    ]
    spans.extend((d, d + size) for d in allocation_results)
    for i, (lo, hi) in enumerate(spans):
        _read(pages, lo, hi - lo)
        _require(
            all(hi <= a or z <= lo for a, z in spans[i + 1 :]),
            "normal AddCharge data spans overlap",
        )
    for delta in (0x31C, 0x33C, 0x364, 0x2F0, 0x2E4, 136, 72):
        _read(pages, min((g - delta) & ~4095, 0xFFFFE000), 8192)
    fixed = (
        (ERROR, ERROR + 4096),
        (HEAP_GLOBAL & ~4095, (HEAP_GLOBAL & ~4095) + 4096),
        (FREE_IAT & ~4095, (FREE_IAT & ~4095) + 4096),
    )
    _require(all(hi <= a or z <= lo for lo, hi in spans for a, z in fixed),
             "normal AddCharge complete data spans overlap runtime")
    for delta in (0x31C, 0x33C, 0x364, 0x2F0, 0x2E4, 136, 72):
        base = min((g - delta) & ~4095, 0xFFFFE000)
        _require(all(base + 8192 <= a or z <= base for a, z in fixed)
                 and (base + 8192 <= 0x06000000 or 0x06004000 <= base),
                 "normal AddCharge full stack window overlaps runtime")
    codepages = {
        (BASE + a + i) & ~4095 for a, (n, digest) in BODY_PINS.items() for i in range(n)
    }
    _require(
        not codepages.intersection(pages), "normal AddCharge data pages overlap code"
    )
    _require(
        type(return_address) is int
        and all(not (lo <= return_address < hi) for lo, hi in spans)
        and all(
            not (BASE + a <= return_address < BASE + a + n)
            for a, (n, digest) in BODY_PINS.items()
        ),
        "normal AddCharge return overlaps data or code",
    )
    return g, h, o, c, param, count, capacity_count


def apply(*, pages, registers, xmm, return_address, entry_flags, allocation_results):
    return _normalize(
        lambda: _apply(
            pages, registers, xmm, return_address, entry_flags, allocation_results
        )
    )


def _apply(pages, registers, xmm, return_address, entry_flags, allocation_results):
    g, h, o, c, param, count, capacity_count = _validate(
        pages, registers, xmm, return_address, entry_flags, allocation_results
    )
    f = g - 4
    memory = {p: bytearray(b) for p, b in pages.items()}
    events, trace, boundaries, imports, packets = [], [], [], [], {}
    regs, vec = dict(registers), dict(xmm)
    seh = int.from_bytes(_read(pages, 0, 4), "little")
    cookie = int.from_bytes(_read(pages, COOKIE, 4), "little")

    def event(access, at, value, width=4):
        if access == "write":
            _write(memory, at, value.to_bytes(width, "little"))
        else:
            _require(
                int.from_bytes(_read(memory, at, width), "little") == value,
                "normal AddCharge expected read differs",
            )
        events.append(dict(access=access, address=at, width=width, value=value))

    def boundary(name, phase, endpoint, flags, mask=0x8D5):
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
    trace.extend(f"0x{pc:08x}" for pc in OWNER_SEGMENTS[0])
    boundary("clone_argument", "entry", BASE + 0x9A8E0, flags)
    prefix = copy.deepcopy(events)
    child = path.apply(
        pages=_pages(memory),
        registers=dict(regs),
        xmm=dict(vec),
        return_address=BASE + 0x257738,
        entry_flags=move._ordinary(entry_flags, flags),
        allocation_result=allocation_results[0],
    )
    _require(
        type(child) is dict
        and set(child)
        == {
            "geometry",
            "registers",
            "xmm",
            "flags",
            "flag_mask",
            "df",
            "endpoint",
            "pages",
            "events",
            "trace_rvas",
            "boundaries",
            "allocation_packet",
            "scalar_packet",
            "imported",
            "source_snapshot",
        }
        and _same(child["endpoint"], BASE + 0x257738)
        and _same(child["df"], 0),
        "normal AddCharge clone child envelope differs",
    )
    move._common_schema(child, set(memory))
    packets["clone_argument"] = copy.deepcopy(child)
    events.extend(copy.deepcopy(child["events"]))
    trace.extend(child["trace_rvas"])
    memory = {p: bytearray(b) for p, b in child["pages"].items()}
    regs, vec = dict(child["registers"]), dict(child["xmm"])
    boundary("clone_argument", "return", BASE + 0x257738, child["flags"])
    state = copy.deepcopy(child["imported"])
    state["events"] = prefix + state["events"]
    state["name"] = "clone_argument"
    imports.append(state)
    event("write", g - 44, BASE + 0x25773F)
    regs.update(ecx=h, esp=g - 44)
    trace.extend(f"0x{pc:08x}" for pc in OWNER_SEGMENTS[1])
    boundary("addmove", "entry", BASE + 0x257340, child["flags"])
    prefix = copy.deepcopy(events)
    child = move.apply(
        pages=_pages(memory),
        registers=dict(regs),
        xmm=dict(vec),
        return_address=BASE + 0x25773F,
        entry_flags=move._ordinary(entry_flags, child["flags"]),
        allocation_results=allocation_results[1:],
    )
    _require(
        type(child) is dict
        and set(child)
        == {
            "geometry",
            "path",
            "registers",
            "xmm",
            "pages",
            "events",
            "trace_rvas",
            "boundaries",
            "imports",
            "child_packets",
            "flags",
            "flag_mask",
            "df",
            "endpoint",
        }
        and _same(child["endpoint"], BASE + 0x25773F)
        and _same(child["df"], 0),
        "normal AddCharge AddMove child envelope differs",
    )
    move._common_schema(child, set(memory))
    _require(
        child["registers"]["eax"] & 255 == 1,
        "normal AddCharge requires successful AddMove",
    )
    packets["addmove"] = copy.deepcopy(child)
    events.extend(copy.deepcopy(child["events"]))
    trace.extend(child["trace_rvas"])
    memory = {p: bytearray(b) for p, b in child["pages"].items()}
    regs, vec = dict(child["registers"]), dict(child["xmm"])
    boundary("addmove", "return", BASE + 0x25773F, child["flags"])
    for state in child["imports"]:
        state = copy.deepcopy(state)
        state["events"] = prefix + state["events"]
        imports.append(state)
    event("read", h + 4, c + 308)
    event("write", c + 0xD8, 2)
    event("read", g + 4, o)
    event("read", g + 12, o + capacity_count * 8)
    for at, v in ((g - 28, 8), (g - 32, capacity_count), (g - 36, o), (g - 40, BASE + 0x257765)):
        event("write", at, v)
    regs.update(eax=capacity_count, ecx=o, esp=g - 40)
    trace.extend(f"0x{pc:08x}" for pc in OWNER_SEGMENTS[2])
    boundary("free_original", "entry", BASE + 0x7800, move._test(capacity_count), 0xC5)
    prefix = copy.deepcopy(events)
    stack_base = min((g - 72) & ~4095, 0xFFFFE000)
    free = _outer_free_law(regs, _pages(memory), o, stack_base, capacity_count)
    packets["free_original"] = copy.deepcopy(free)
    importpages = {p: bytearray(b) for p, b in memory.items()}
    for row in free["events"][:16]:
        if row["access"] == "write":
            _write(importpages, row["address"], row["value"].to_bytes(4, "little"))
    v = g - 40
    imports.append(
        dict(
            name="free_original",
            registers=dict(regs, eax=0x1FFFFFFF, ecx=o, edx=7, ebp=v - 16, esp=v - 32),
            xmm=dict(vec),
            pages=_pages(importpages),
            events=prefix + copy.deepcopy(free["events"][:16]),
            flags=move._test(o),
            flag_mask=0x8C5,
            df=0,
            endpoint=IMPORT,
            entry_esp=v - 32,
            words=[BASE + 0x389172, HEAP, 0, o],
        )
    )
    events.extend(copy.deepcopy(free["events"]))
    _write(memory, stack_base, free["stack"])
    regs = dict(free["registers"])
    trace.extend(f"0x{pc:08x}" for pc in move.destroy.FREE_TRACE)
    boundary("free_original", "return", BASE + 0x257765, free["flags"])
    for access, at, v in (
        ("read", g - 16, seh),
        ("write", 0, seh),
        ("read", g - 24, cookie ^ f),
        ("read", g - 20, registers["esi"]),
        ("read", g - 4, registers["ebp"]),
        ("read", g, return_address),
    ):
        event(access, at, v)
    trace.extend(f"0x{pc:08x}" for pc in OWNER_SEGMENTS[3])
    _require(
        len(trace) == 2223 + 40 * count
        and len(events) == 1394 + 16 * count
        and len(boundaries) == 6
        and len(imports) == 8,
        "normal AddCharge selected path count differs",
    )
    return dict(
        geometry=dict(
            entry=g, receiver=h, source_path=o, argument_block=g - 40, new_record=c
        ),
        path=dict(begin=o, end=o + count * 8, capacity=o + capacity_count * 8, parameter_bits=param),
        registers=dict(registers, eax=1, ecx=cookie ^ f, edx=0xB0000001, esp=g + 20),
        xmm=vec,
        pages=_pages(memory),
        events=events,
        trace_rvas=trace,
        boundaries=boundaries,
        imports=imports,
        child_packets=packets,
        flags=_add_flags(g - 36, 12),
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
    )
