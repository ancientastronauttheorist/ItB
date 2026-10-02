"""Selected normal AddMove with two through511 path entries and existing record capacity.

Reviewed complete child laws and their extra/nested instruction metadata are
trusted. Parent COMMON envelopes are typed; no recursively typed nested-child
claim follows. Three allocation and three free successes are supplied.
No gameplay, ownership or growth claim follows.
"""

from __future__ import annotations
import copy
from src.observatory import native_movement_effect_record_default_semantics as default
from src.observatory import native_movement_path_small_assign_semantics as assign
from src.observatory import native_movement_effect_record_small_copy_semantics as record
from src.observatory import native_movement_effect_record_small_append_semantics as append
from src.observatory import native_movement_effect_record_small_destroy_semantics as destroy
from src.observatory import native_movement_path_small_clone_semantics as path
from src.observatory import native_movement_addmove_early_return_conformance as early

ANALYSIS_KIND = "pe_native_movement_addmove_small_normal_semantics"
BASE, U32, COOKIE, LITERAL = 0x400000, 0xFFFFFFFF, 0x893F28, 0x80DFDC
REGISTERS, XMM = default.REGISTERS, default.XMM
_read, _write, _pages, _same = record._read, record._write, record._pages, record._same
SOURCE_PINS = dict(
    default.SOURCE_PINS,
    **{k: v for k, v in append.SOURCE_PINS.items() if k not in default.SOURCE_PINS},
)
SOURCE_PINS.update(assign.SOURCE_PINS)
SOURCE_PINS.update(destroy.SOURCE_PINS)
SOURCE_PINS["addmove_early"] = (early.ANALYSIS_KIND, early.SEALED_SHA256)
BODY_PINS = {
    30720: (91, "2d09033991193eea352dab418355232650d3aeb45906f909b384e0b662cd1ef6"),
    32720: (245, "c49f0e24bd27ed5495ceddc13536ca6fbe85d8c97f207db817ce0642b8b01906"),
    32976: (288, "062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333"),
    567584: (91, "e13e3be9b5e53d78d61aaaacc91b9c7c3183b77ef1f005bd2010bc1aa9b9830e"),
    568224: (43, "92494ea2dfd86d06ce373c9837f55d42e6c62746bd9c2c3c26d2a8af6abe938b"),
    633056: (79, "4359ecaf051506bce97afe182b66c453ca8d13ac4091d72a810f9df43d14d2e0"),
    633920: (87, "29a0428ed018a85e4e0a76f283f10040cf9e084f49bee5706b58766b570cb9d1"),
    809904: (226, "62157759ee3564515e63f20e297c171de6444d84732bccf7414eb208d953eefe"),
    1106592: (497, "641631ac31c522163cb141e846f21fa5e163ed176f042c3123762564c6d7d8ee"),
    1423792: (772, "3846fdb1ca2ebc1b4b6e83a64994f82d4907938345ff0d856c9bbea690957fc6"),
    1677728: (669, "2f17cc9bd3616c14305fb7fc1871bf0e37d09262825a99213f5b0568d6c6045d"),
    2454336: (231, "910d5418dbd9db30c75adcd8b74077c5c4e99119b2298c6c252045f8c9803d67"),
    2465536: (183, "39a9908012609c47f77556aea5af0865f3eb36943b5a1860c4c338bb6ea6fbb7"),
    3503306: (17, "5eafe60e37cdb82b85f6df218e4b490940c6fb2545895c2cef644fb38ab97375"),
    3503323: (51, "452b4c981b0a2567c6f4fc35b20076deca45a6b3509707358212028d21db5bfa"),
    3504221: (5, "f45c1f23615da61aa6c903e18306f5628c975cfaf6027b37e45d2264c7ed477d"),
    3603223: (5, "fafd106d4b0ce80368b3e080fb3be3b06582d8145fce2063305541cab5f65ea3"),
    3645266: (11, "831e215b24984219b6d6d7ce812127a420a48782704f0fef1630b1b8050cabbd"),
    3707222: (58, "223079ea989dad987b5fdf47fc9c63d348f353dc2ab70257ae6dc53c62a9003c"),
    3707947: (78, "d97ee587f29bfdaf154ca653059e883b67b56713a5d96643356a4edf6e3edde8"),
}
OWNER_SEGMENTS = tuple(
    tuple(0x257000 + n for n in seg)
    for seg in (
        (
            0x340,
            0x341,
            0x343,
            0x345,
            0x34A,
            0x350,
            0x351,
            0x357,
            0x35C,
            0x35E,
            0x361,
            0x362,
            0x363,
            0x364,
            0x367,
            0x36D,
            0x36F,
            0x376,
            0x379,
            0x37C,
            0x37E,
            0x381,
            0x384,
            0x38A,
            0x38C,
            0x392,
        ),
        (0x397, 0x39A, 0x39E, 0x39F, 0x3A2),
        (0x3A7, 0x3AC, 0x3B2, 0x3B3, 0x3B9, 0x3BE),
        (0x3C3, 0x3C9, 0x3CD, 0x3CE, 0x3D0),
        (0x3D5, 0x3DB),
        (0x3E0, 0x3E6, 0x3E8),
        (0x3ED, 0x3F0, 0x3F2, 0x3F4, 0x3F7, 0x3F9, 0x3FB, 0x3FE, 0x3FF, 0x400),
        (0x405, 0x408, 0x40A, 0x40D, 0x414, 0x415, 0x416, 0x417, 0x41A, 0x41C),
        (0x421, 0x423, 0x424),
    )
)


class AddMoveSmallNormalError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise AddMoveSmallNormalError(message)


def _ordinary(word, flags):
    return (word & ~0x8D5) | flags


def _test(value):
    return (
        (int((value & 255).bit_count() % 2 == 0) << 2)
        | (int(value == 0) << 6)
        | ((value >> 31) << 7)
    )


def _common_schema(child, page_keys):
    """Close common packet types while trusting valid child semantics."""
    _require(
        type(child["registers"]) is dict
        and set(child["registers"]) == set(REGISTERS)
        and all(
            type(k) is str and type(v) is int and 0 <= v <= U32
            for k, v in child["registers"].items()
        )
        and type(child["xmm"]) is dict
        and set(child["xmm"]) == set(XMM)
        and all(
            type(k) is str and type(v) is int and 0 <= v < 2**128
            for k, v in child["xmm"].items()
        )
        and type(child["pages"]) is dict
        and set(child["pages"]) == page_keys
        and all(
            type(p) is int
            and 0 <= p <= 0xFFFFF000
            and p % 4096 == 0
            and type(b) is bytes
            and len(b) == 4096
            for p, b in child["pages"].items()
        )
        and type(child["events"]) is list
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
            for row in child["events"]
        )
        and type(child["trace_rvas"]) is list
        and all(
            type(pc) is str
            and len(pc) == 10
            and pc.startswith("0x")
            and pc == f"0x{int(pc, 16):08x}"
            for pc in child["trace_rvas"]
        )
        and type(child["flags"]) is int
        and 0 <= child["flags"] <= 0x8D5
        and child["flags"] & ~0x8D5 == 0
        and _same(child["flag_mask"], 0x8D5),
        "normal AddMove typed common child schema differs",
    )


def _validate(pages, registers, xmm, return_address, entry_flags, allocation_results):
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
        "invalid normal AddMove pages",
    )
    _require(
        type(registers) is dict
        and set(registers) == set(REGISTERS)
        and all(
            type(k) is str and type(v) is int and 0 <= v <= U32
            for k, v in registers.items()
        ),
        "invalid normal AddMove GPR schema",
    )
    _require(
        type(xmm) is dict
        and set(xmm) == set(XMM)
        and all(
            type(k) is str and type(v) is int and 0 <= v < 2**128
            for k, v in xmm.items()
        ),
        "invalid normal AddMove XMM schema",
    )
    _require(
        type(entry_flags) is int
        and 0 <= entry_flags <= U32
        and entry_flags & ~0xAD7 == 0
        and entry_flags & 2 == 2,
        "invalid normal AddMove ordinary DF-clear flags",
    )
    _require(
        type(allocation_results) is list
        and len(allocation_results) == 3
        and all(
            type(d) is int and 0x06000000 <= d <= 0x06003FF0 for d in allocation_results
        ),
        "normal AddMove requires three ordinary allocation results",
    )
    g, h = registers["esp"], registers["ecx"]
    _require(
        g >= 0x338 and g + 20 <= U32 and 0 < h and h + 12 <= U32,
        "normal AddMove frame or header wraps",
    )
    r1, r2 = g - 0x148, g - 0x27C
    _require(r1 > LITERAL, "normal AddMove local record precedes literal")
    o, e, cap, param = (
        int.from_bytes(_read(pages, g + n, 4), "little") for n in (4, 8, 12, 16)
    )
    _require(
        0 < o < e <= cap <= U32 and (e-o)%8 == 0 and (cap-o)%8 == 0 and 2 <= (e-o)//8 <= (cap-o)//8 <= 511,
        "normal AddMove requires ordinary small caller count2..511",
    )
    count = (e-o)//8
    capacity_count = (cap-o)//8
    size = count*8
    _require(all(d+size <= 0x06004000 for d in allocation_results), "normal AddMove allocation extents differ")
    b, c, end = (int.from_bytes(_read(pages, h + n, 4), "little") for n in (0, 4, 8))
    _require(
        0 < b <= c
        and c + 308 <= end <= U32
        and (c - b) % 308 == 0
        and (end - b) % 308 == 0,
        "normal AddMove receiver lacks existing capacity",
    )
    _require(r2 >= c, "normal AddMove append source precedes receiver end")
    spans = [
        (g - 0x338, g + 20),
        (h, h + 12),
        (c, c + 308),
        (o, cap),
        (0, 4),
        (COOKIE, COOKIE + 4),
        (LITERAL, LITERAL + 1),
    ]
    spans.extend((d, d + size) for d in allocation_results)
    for i, (lo, hi) in enumerate(spans):
        _read(pages, lo, hi - lo)
        _require(
            all(hi <= a or z <= lo for a, z in spans[i + 1 :]),
            "normal AddMove data spans overlap",
        )
    # Every lower allocator or free law carries its actual two-page window.
    for delta in (0x2F0, 0x310, 0x338, 0x2C4, 0x2B8):
        base = min((g - delta) & ~4095, 0xFFFFE000)
        _read(pages, base, 8192)
    _require(_read(pages, LITERAL, 1) == b"\0", "normal AddMove literal is not empty")
    fixed = (
        (destroy.ERROR, destroy.ERROR + 4096),
        (destroy.HEAP_GLOBAL & ~4095, (destroy.HEAP_GLOBAL & ~4095) + 4096),
        (destroy.FREE_IAT & ~4095, (destroy.FREE_IAT & ~4095) + 4096),
    )
    _require(
        all(hi <= a or z <= lo for lo, hi in spans for a, z in fixed),
        "normal AddMove complete data spans overlap runtime",
    )
    for delta in (0x2F0, 0x310, 0x338, 0x2C4, 0x2B8):
        base = min((g - delta) & ~4095, 0xFFFFE000)
        _require(
            all(base + 8192 <= a or z <= base for a, z in fixed)
            and (base + 8192 <= 0x06000000 or 0x06004000 <= base),
            "normal AddMove full stack window overlaps runtime",
        )
    _read(pages, 0x06000000, 16384)
    _require(
        int.from_bytes(_read(pages, destroy.HEAP_GLOBAL, 4), "little") == destroy.HEAP
        and int.from_bytes(_read(pages, destroy.FREE_IAT, 4), "little")
        == destroy.IMPORT
        and int.from_bytes(_read(pages, path.ALLOC_IAT, 4), "little") == path.IMPORT,
        "normal AddMove supplied heap interface differs",
    )
    # The reviewed free pure packet has a logical imported target; its IAT word
    # is transport-neutral, while the caller installs the same native stop.
    codepages = {
        (BASE + a + i) & ~4095 for a, (n, digest) in BODY_PINS.items() for i in range(n)
    }
    _require(
        not codepages.intersection(pages), "normal AddMove data pages overlap code"
    )
    _require(
        type(return_address) is int
        and 0 < return_address <= U32
        and all(not (lo <= return_address < hi) for lo, hi in spans)
        and all(
            not (BASE + a <= return_address < BASE + a + n)
            for a, (n, digest) in BODY_PINS.items()
        ),
        "normal AddMove return overlaps data or code",
    )
    _require(
        int.from_bytes(_read(pages, g, 4), "little") == return_address,
        "normal AddMove installed return differs",
    )
    return g, h, o, c, r1, r2, param, count, capacity_count


def apply(*, pages, registers, xmm, return_address, entry_flags, allocation_results):
    try:
        return _apply(
            pages, registers, xmm, return_address, entry_flags, allocation_results
        )
    except AddMoveSmallNormalError:
        raise
    except Exception as exc:
        raise AddMoveSmallNormalError(str(exc)) from exc


def _apply(pages, registers, xmm, return_address, entry_flags, allocation_results):
    g, h, o, c, r1, r2, param, count, capacity_count = _validate(
        pages, registers, xmm, return_address, entry_flags, allocation_results
    )
    size = count*8
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
                "normal AddMove expected read differs",
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

    def join(name, owner_segment, function, entry, continuation, flags, extra):
        nonlocal regs, vec, memory
        trace.extend(f"0x{pc:08x}" for pc in OWNER_SEGMENTS[owner_segment])
        boundary(name, "entry", BASE + entry, flags)
        prefix = copy.deepcopy(events)
        child = function(
            pages=_pages(memory),
            registers=dict(regs),
            xmm=dict(vec),
            return_address=BASE + continuation,
            entry_flags=_ordinary(entry_flags, flags),
            **extra,
        )
        common_keys = {
            "registers",
            "xmm",
            "pages",
            "events",
            "flags",
            "flag_mask",
            "df",
            "endpoint",
            "trace_rvas",
        }
        extra_keys = {
            "default": {
                "record_address",
                "record_bytes",
                "argument",
                "string_boundaries",
            },
            "assignment": {
                "geometry",
                "boundaries",
                "allocation_packet",
                "scalar_packet",
                "imported",
                "source_snapshot",
            },
            "record_copy": {
                "source_address",
                "record_address",
                "record_bytes",
                "source_snapshot",
                "boundaries",
                "path_packet",
            },
            "append": {
                "receiver_address",
                "source_address",
                "record_address",
                "record_bytes",
                "source_snapshot",
                "boundaries",
                "record_packet",
            },
            "destroy_temp": {
                "record_address",
                "record_bytes",
                "path_pointer",
                "boundaries",
                "free_packet",
                "imported",
            },
            "destroy_original": {
                "record_address",
                "record_bytes",
                "path_pointer",
                "boundaries",
                "free_packet",
                "imported",
            },
        }
        _require(
            type(child) is dict
            and set(child) == common_keys | extra_keys[name]
            and all(type(k) is str for k in child)
            and type(child["flags"]) is int
            and type(child["flag_mask"]) is int
            and type(child["pages"]) is dict
            and type(child["registers"]) is dict
            and type(child["xmm"]) is dict
            and type(child["events"]) is list
            and type(child["trace_rvas"]) is list
            and _same(child["endpoint"], BASE + continuation)
            and _same(child["df"], 0),
            "normal AddMove trusted child envelope differs",
        )
        _common_schema(child, set(memory))
        packets[name] = copy.deepcopy(child)
        trace.extend(child["trace_rvas"])
        events.extend(copy.deepcopy(child["events"]))
        memory = {p: bytearray(b) for p, b in child["pages"].items()}
        regs, vec = dict(child["registers"]), dict(child["xmm"])
        boundary(
            name, "return", BASE + continuation, child["flags"], child["flag_mask"]
        )
        state = child.get("imported")
        if state is not None:
            state = copy.deepcopy(state)
            state["events"] = prefix + state["events"]
            state["name"] = name
            imports.append(state)
        if name in ("record_copy", "append"):
            nested = (
                child["path_packet"]
                if name == "record_copy"
                else child["record_packet"]["path_packet"]
            )
            # Prefix before the nested path comes from the actual record boundary.
            record_child = child if name == "record_copy" else child["record_packet"]
            path_prefix = record_child["boundaries"][10]["events"]
            parent_prefix = (
                [] if name == "record_copy" else child["boundaries"][0]["events"]
            )
            state = copy.deepcopy(nested["imported"])
            state["events"] = prefix + parent_prefix + path_prefix + state["events"]
            state["name"] = name
            imports.append(state)
        return child

    for at, v in ((g - 4, registers["ebp"]), (g - 8, U32), (g - 12, 0x7CA95E)):
        event("write", at, v)
    event("read", 0, seh)
    event("write", g - 16, seh)
    event("read", COOKIE, cookie)
    event("write", g - 20, cookie ^ f)
    for at, v in (
        (g - 0x280, registers["ebx"]),
        (g - 0x284, registers["esi"]),
        (g - 0x288, cookie ^ f),
        (0, g - 16),
        (g - 8, 0),
    ):
        event("write", at, v)
    event("read", g + 8, o + size)
    event("read", g + 4, o)
    event("write", g - 0x28C, 0)
    event("write", g - 0x290, BASE + 0x257397)
    regs.update(eax=count, ecx=r1, edx=o, esi=h, ebp=f, esp=g - 0x290)
    child = join("default", 0, default.apply, 0x1999A0, 0x257397, path._sub_flags(count, 1), {})
    event("write", g - 8, 1, 1)
    event("write", g - 0x28C, g + 4)
    event("write", g - 0x290, BASE + 0x2573A7)
    regs.update(eax=g + 4, ecx=r1 + 0xCC, esp=g - 0x290)
    child = join(
        "assignment",
        1,
        assign.apply,
        0xC5BB0,
        0x2573A7,
        child["flags"],
        dict(allocation_result=allocation_results[0]),
    )
    event("read", g + 16, param)
    vec["xmm0"] = param
    event("write", g - 0x28C, r1)
    event("write", r1 + 0xC8, param)
    event("write", g - 0x290, BASE + 0x2573C3)
    regs.update(eax=r1, ecx=r2, esp=g - 0x290)
    child = join(
        "record_copy",
        2,
        record.apply,
        0x15B9B0,
        0x2573C3,
        child["flags"],
        dict(allocation_result=allocation_results[1]),
    )
    event("write", g - 8, 2, 1)
    event("write", g - 0x28C, r2)
    event("write", g - 0x290, BASE + 0x2573D5)
    regs.update(eax=r2, ecx=h, esp=g - 0x290)
    child = join(
        "append",
        3,
        append.apply,
        0x259F00,
        0x2573D5,
        child["flags"],
        dict(allocation_result=allocation_results[2]),
    )
    event("write", g - 0x28C, BASE + 0x2573E0)
    regs.update(ecx=r2, esp=g - 0x28C)
    child = join(
        "destroy_temp", 4, destroy.apply, 0x10E2A0, 0x2573E0, child["flags"], {}
    )
    event("write", g - 0x28C, BASE + 0x2573ED)
    regs.update(ecx=r1, ebx=(regs["ebx"] & 0xFFFFFF00) | 1, esp=g - 0x28C)
    child = join(
        "destroy_original", 5, destroy.apply, 0x10E2A0, 0x2573ED, child["flags"], {}
    )
    event("read", g + 4, o)
    event("read", g + 12, o + capacity_count*8)
    for at, v in (
        (g - 0x28C, 8),
        (g - 0x290, capacity_count),
        (g - 0x294, o),
        (g - 0x298, BASE + 0x257405),
    ):
        event("write", at, v)
    regs.update(ecx=capacity_count, edx=o, esp=g - 0x298)
    trace.extend(f"0x{pc:08x}" for pc in OWNER_SEGMENTS[6])
    boundary("free_caller", "entry", BASE + 0x7800, _test(capacity_count), 0xC5)
    before = copy.deepcopy(events)
    stack_base = min((g - 0x2B8) & ~4095, 0xFFFFE000)
    free = _outer_free_law(regs, _pages(memory), o, stack_base, capacity_count)
    packets["free_caller"] = copy.deepcopy(free)
    importpages = {p: bytearray(b) for p, b in memory.items()}
    for row in free["events"][:16]:
        if row["access"] == "write":
            _write(importpages, row["address"], row["value"].to_bytes(4, "little"))
    v = g - 0x298
    imports.append(
        dict(
            name="free_caller",
            registers=dict(regs, eax=0x1FFFFFFF, ecx=o, edx=7, ebp=v - 16, esp=v - 32),
            xmm=dict(vec),
            pages=_pages(importpages),
            events=before + copy.deepcopy(free["events"][:16]),
            flags=_test(o),
            flag_mask=0x8C5,
            df=0,
            endpoint=destroy.IMPORT,
            entry_esp=v - 32,
            words=[BASE + 0x389172, destroy.HEAP, 0, o],
        )
    )
    events.extend(copy.deepcopy(free["events"]))
    _write(memory, stack_base, free["stack"])
    regs = dict(free["registers"])
    trace.extend(f"0x{pc:08x}" for pc in destroy.FREE_TRACE)
    boundary("free_caller", "return", BASE + 0x257405, free["flags"])
    regs["esp"] += 12
    regs["eax"] = (regs["eax"] & 0xFFFFFF00) | 1
    for access, at, v in (
        ("read", g - 16, seh),
        ("write", 0, seh),
        ("read", g - 0x288, cookie ^ f),
        ("read", g - 0x284, registers["esi"]),
        ("read", g - 0x280, registers["ebx"]),
        ("read", g - 20, cookie ^ f),
        ("write", g - 0x280, BASE + 0x257421),
    ):
        event(access, at, v)
    regs.update(ecx=cookie, ebx=registers["ebx"], esi=registers["esi"], esp=g - 0x280)
    trace.extend(f"0x{pc:08x}" for pc in OWNER_SEGMENTS[7])
    boundary("cookie", "entry", BASE + 0x3574CA, _test(cookie), 0x8C5)
    event("read", COOKIE, cookie)
    event("read", g - 0x280, BASE + 0x257421)
    trace.extend(("0x003574ca", "0x003574d0", "0x003574d3"))
    regs["esp"] = g - 0x27C
    boundary("cookie", "return", BASE + 0x257421, 0x44)
    event("read", g - 4, registers["ebp"])
    event("read", g, return_address)
    trace.extend(f"0x{pc:08x}" for pc in OWNER_SEGMENTS[8])
    final = dict(registers, eax=1, ecx=cookie, edx=0xB0000001, esp=g + 20)
    _require(
        len(trace) == 2029 + 30 * count
        and len(events) == 1269 + 12 * count
        and len(boundaries) == 16
        and len(imports) == 6,
        "normal AddMove selected path count differs",
    )
    return dict(
        geometry=dict(
            entry=g,
            receiver=h,
            source_path=o,
            original_record=r1,
            temporary_record=r2,
            new_record=c,
        ),
        path=dict(begin=o, end=o + size, capacity=o + capacity_count*8, parameter_bits=param),
        registers=final,
        xmm=vec,
        pages=_pages(memory),
        events=events,
        trace_rvas=trace,
        boundaries=boundaries,
        imports=imports,
        child_packets=packets,
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
    )


HEAP_GLOBAL, FREE_IAT, HEAP, IMPORT, ERROR = (
    destroy.HEAP_GLOBAL,
    destroy.FREE_IAT,
    destroy.HEAP,
    destroy.IMPORT,
    destroy.ERROR,
)
deallocator = destroy.deallocator
_event_law = destroy._event_law
_same_packet = _same
_add_flags = path._add_flags


def _normalize(fn):
    try:
        return fn()
    except AddMoveSmallNormalError:
        raise
    except Exception as exc:
        raise AddMoveSmallNormalError(str(exc)) from exc


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
        int.from_bytes(_read(pages, v, 4), "little") == BASE + 0x257405,
        "movement free installed continuation differs",
    )
    wanted["events"][-1]["value"] = BASE + 0x257405
    wanted["stop"] = BASE + 0x257405
    return wanted
