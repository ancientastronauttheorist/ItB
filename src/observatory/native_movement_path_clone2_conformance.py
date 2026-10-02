"""Continuous finite native two-record movement path clone.

One supplied positive HeapAlloc response is a premise. This proof establishes
no allocator ownership, record construction, AddMove count>1 or gameplay.
"""

from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from src.observatory import native_assertion_helper_fill_conformance as common
from src.observatory import native_movement_effect_binding as binding
from src.observatory import native_vector_allocation_composition as allocation_contract
from src.observatory import native_vector_allocation_conformance as allocator
from src.observatory import native_movement_path_scalar_clone2_semantics as scalar
from src.observatory.native_lua_vector_allocation_return_conformance import _add_flags

BASE, EXE_SHA256 = common.BASE, common.EXE_SHA256
ANALYSIS_KIND = "pe_native_movement_path_clone2_conformance"
SEALED_SHA256 = "1cddf384c45fb50a60752656acd2560a7e243dd20f0d68b8a963a4a7bb3a739b"
SOURCE_PINS = {
    "program_facts": binding.SOURCE_PINS["program_facts"],
    "movement_binding": (binding.ANALYSIS_KIND, binding.SEALED_SHA256),
    "allocation_composition": (
        allocation_contract.ANALYSIS_KIND,
        allocation_contract.SEALED_SHA256,
    ),
    "allocation_conformance": (allocator.ANALYSIS_KIND, allocator.SEALED_SHA256),
}
STACK, DATA, HEADER_PAGE = 0x30000000, 0x06000000, 0x10000000
FEATURE_PAGE, HEAP_GLOBAL, ALLOC_IAT = 0x00893000, allocator.HEAP_GLOBAL, allocator.IAT
HEAP, IMPORT, RETURN = allocator.HEAP_HANDLE, allocator.IMPORT, allocator.RETURN
CPU_MODEL = 19
REGISTERS, XMM = scalar.REGISTERS, scalar.XMM
VECTOR_KEYS = {"alignment", "profile"}
FIXTURE_KEYS = {"pages", "registers", "xmm", "return_address", "entry_flags"}
BODY_PINS = {
    0x8ABA0: (43, "92494ea2dfd86d06ce373c9837f55d42e6c62746bd9c2c3c26d2a8af6abe938b"),
    0x9A8E0: (79, "4359ecaf051506bce97afe182b66c453ca8d13ac4091d72a810f9df43d14d2e0"),
    0x9AC40: (87, "29a0428ed018a85e4e0a76f283f10040cf9e084f49bee5706b58766b570cb9d1"),
    0x8A920: (91, "e13e3be9b5e53d78d61aaaacc91b9c7c3183b77ef1f005bd2010bc1aa9b9830e"),
    0x3574DB: (51, "452b4c981b0a2567c6f4fc35b20076deca45a6b3509707358212028d21db5bfa"),
    0x379F52: (11, "831e215b24984219b6d6d7ce812127a420a48782704f0fef1630b1b8050cabbd"),
    0x38942B: (78, "d97ee587f29bfdaf154ca653059e883b67b56713a5d96643356a4edf6e3edde8"),
}
BODIES = tuple(sorted((a, a + n) for a, (n, h) in BODY_PINS.items()))
_canonical_bytes, _canonical_sha256 = common._canonical_bytes, common._canonical_sha256


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def _normalize(operation):
    try:
        return operation()
    except ConformanceError:
        raise
    except Exception as exc:
        raise ConformanceError(str(exc)) from exc


def _same_packet(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return (
            set(a) == set(b)
            and all(any(type(k) is type(j) and k == j for j in b) for k in a)
            and all(_same_packet(a[k], b[k]) for k in a)
        )
    if type(a) in (list, tuple):
        return len(a) == len(b) and all(_same_packet(x, y) for x, y in zip(a, b))
    return a == b


def _read(pages, address, size=4):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def _write(pages, address, payload):
    for i, byte in enumerate(payload):
        pages[(address + i) & ~4095][(address + i) & 4095] = byte


def _pages(pages):
    return {p: bytes(v) for p, v in pages.items()}


def _stack(pages):
    return _read(pages, STACK, 8192)


def _page_hashes(pages):
    return {
        f"0x{p:08x}": hashlib.sha256(data).hexdigest()
        for p, data in sorted(pages.items())
    }


def _event_law(original):
    memory = {p: bytearray(v) for p, v in original.items()}
    events = []

    def event(access, address, value):
        if access == "write":
            _write(memory, address, value.to_bytes(4, "little"))
        else:
            _require(
                int.from_bytes(_read(memory, address), "little") == value,
                "movement expected read differs",
            )
        events.append(dict(access=access, address=address, width=4, value=value))

    return memory, events, event


def _boundary(regs, xmm, pages, events, endpoint, flags, mask):
    return dict(
        registers=dict(regs),
        xmm=dict(xmm),
        pages=_pages(pages),
        events=copy.deepcopy(events),
        endpoint=endpoint,
        flags=flags,
        flag_mask=mask,
        df=0,
    )


STATIC_ORDERS = {
    0x9A8E0: (
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
        0x9A90C,
        0x9A90E,
        0x9A910,
        0x9A913,
        0x9A914,
        0x9A917,
        0x9A918,
        0x9A91A,
        0x9A91C,
        0x9A921,
        0x9A924,
        0x9A927,
        0x9A928,
        0x9A92A,
        0x9A92B,
        0x9A92C,
    ),
    0x9AC40: (
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
        0x9AC6A,
        0x9AC70,
        0x9AC72,
        0x9AC73,
        0x9AC78,
        0x9AC7A,
        0x9AC7D,
        0x9AC7F,
        0x9AC82,
        0x9AC85,
        0x9AC87,
        0x9AC88,
        0x9AC89,
        0x9AC8A,
        0x9AC8D,
        0x9AC92,
    ),
    0x8ABA0: (
        0x8ABA0,
        0x8ABA1,
        0x8ABA3,
        0x8ABA6,
        0x8ABA7,
        0x8ABA9,
        0x8ABAB,
        0x8ABAD,
        0x8ABB0,
        0x8ABB2,
        0x8ABB4,
        0x8ABB6,
        0x8ABB8,
        0x8ABBB,
        0x8ABBE,
        0x8ABC1,
        0x8ABC4,
        0x8ABC6,
        0x8ABC8,
        0x8ABC9,
        0x8ABCA,
    ),
}

ALLOCATION_TRACE = (
    0x8A920,
    0x8A921,
    0x8A923,
    0x8A926,
    0x8A928,
    0x8A932,
    0x8A937,
    0x8A939,
    0x8A93C,
    0x8A941,
    0x8A962,
    0x8A963,
    0x3574DB,
    0x3574DC,
    0x3574DE,
    0x3574FF,
    0x357502,
    0x379F52,
    0x379F54,
    0x379F55,
    0x379F57,
    0x379F58,
    0x38942B,
    0x38942D,
    0x38942E,
    0x389430,
    0x389431,
    0x389434,
    0x389437,
    0x389439,
    0x38943B,
    0x389454,
    0x389455,
    0x389457,
    0x38945D,
    0x389463,
    0x389465,
    0x389467,
    0x389476,
    0x389477,
    0x389478,
    0x357507,
    0x357508,
    0x35750A,
    0x35750C,
    0x35750D,
    0x8A968,
    0x8A96B,
    0x8A96D,
    0x8A96E,
)

PARENT_PREFIX = tuple(p for p in STATIC_ORDERS[0x9A8E0] if p <= 0x9A907)
PARENT_MIDDLE = tuple(p for p in STATIC_ORDERS[0x9A8E0] if 0x9A90C <= p <= 0x9A91C)
PARENT_SUFFIX = tuple(p for p in STATIC_ORDERS[0x9A8E0] if p >= 0x9A921)
RESERVE_PREFIX = tuple(
    p
    for p in STATIC_ORDERS[0x9AC40]
    if p <= 0x9AC73 and p not in (0x9AC62, 0x9AC63, 0x9AC65, 0x9AC66, 0x9AC67)
)
RESERVE_SUFFIX = tuple(p for p in STATIC_ORDERS[0x9AC40] if 0x9AC78 <= p <= 0x9AC8A)
TRACE = (
    PARENT_PREFIX
    + RESERVE_PREFIX
    + ALLOCATION_TRACE
    + RESERVE_SUFFIX
    + PARENT_MIDDLE
    + scalar.TRACE
    + PARENT_SUFFIX
)


def vectors():
    return [dict(alignment=a, profile=p) for a in range(16) for p in range(3)]


def _checked_vector(vector):
    _require(
        type(vector) is dict
        and set(vector) == VECTOR_KEYS
        and all(type(k) is str for k in vector)
        and all(type(v) is int for v in vector.values())
        and vector in vectors(),
        "outside fixed path clone2 geometry",
    )


def geometry(vector):
    _checked_vector(vector)
    a = vector["alignment"]
    return dict(
        entry=STACK + 4096 + a,
        source=DATA + 0x2800 + a,
        destination=DATA + 0x1000 + a,
        source_header=HEADER_PAGE + 0x80 + a,
        destination_header=HEADER_PAGE + 0x100 + a,
    )


def frame_join(entry):
    _require(
        type(entry) is int and 88 <= entry <= 2**32 - 8, "invalid path clone2 frame"
    )
    return dict(
        parent=entry,
        reserve=entry - 20,
        allocation=entry - 40,
        heap=entry - 88,
        scalar=entry - 32,
        returned=entry + 8,
        protected_start=entry - 88,
        protected_end=entry + 8,
    )


def _fixture(vector):
    g = geometry(vector)
    p = vector["profile"]
    mapped = (
        STACK,
        STACK + 4096,
        DATA,
        DATA + 4096,
        DATA + 8192,
        DATA + 12288,
        HEADER_PAGE,
        FEATURE_PAGE,
        HEAP_GLOBAL & ~4095,
        ALLOC_IAT & ~4095,
    )
    pages = {
        page: bytearray((i * 37 + j * 13 + p * 71) & 255 for j in range(4096))
        for i, page in enumerate(mapped)
    }
    for address, value in (
        (g["entry"], RETURN),
        (g["entry"] + 4, g["source_header"]),
        (g["source_header"], g["source"]),
        (g["source_header"] + 4, g["source"] + 16),
        (g["source_header"] + 8, g["source"] + 16),
        (HEAP_GLOBAL, HEAP),
        (ALLOC_IAT, IMPORT),
    ):
        _write(pages, address, value.to_bytes(4, "little"))
    for index, word in enumerate((0xD15C0016, 0x1234AA16, 0xF00D0016, 0x8765DD16)):
        _write(
            pages,
            g["source"] + 4 * index,
            ((word ^ (p * 0x7654321)) & 0xFFFFFFFF).to_bytes(4, "little"),
        )
    regs = {
        r: (0x12345678 + i * 0x11111111 + p * 0x1234) & 0xFFFFFFFF
        for i, r in enumerate(REGISTERS)
    }
    regs.update(ecx=g["destination_header"], esp=g["entry"])
    xmms = {
        r: int.from_bytes(
            bytes((i * 19 + j * 41 + p * 73) & 255 for j in range(16)), "little"
        )
        for i, r in enumerate(XMM)
    }
    return dict(
        pages=_pages(pages),
        registers=regs,
        xmm=xmms,
        return_address=RETURN,
        entry_flags=0x246,
    )


def _allocation_packet_law(registers, pages, destination, continuation):
    """Count2 ordinary allocation, with only the installed RET sentinel rebound."""
    a = registers["esp"]
    memory, events, event = _event_law(pages)
    w = lambda at, value: event("write", at, value)
    r = lambda at, value: event("read", at, value)
    w(a - 4, registers["ebp"])
    r(a + 4, 2)
    for at, value in ((a - 8, 16), (a - 12, BASE + 0x8A968), (a - 16, a - 4)):
        w(at, value)
    r(a - 8, 16)
    for at, value in ((a - 20, 16), (a - 24, BASE + 0x357507), (a - 28, a - 16)):
        w(at, value)
    r(a - 28, a - 16)
    w(a - 28, a - 16)
    w(a - 32, registers["esi"])
    r(a - 20, 16)
    w(a - 36, 16)
    w(a - 40, 0)
    r(HEAP_GLOBAL, HEAP)
    w(a - 44, HEAP)
    r(ALLOC_IAT, IMPORT)
    w(a - 48, BASE + 0x389463)
    imported = _boundary(
        dict(registers, eax=16, esi=16, ebp=a - 28, esp=a - 48),
        {},
        memory,
        events,
        IMPORT,
        0,
        0x8C5,
    )
    for at, value in (
        (a - 32, registers["esi"]),
        (a - 28, a - 16),
        (a - 24, BASE + 0x357507),
        (a - 20, 16),
        (a - 16, a - 4),
        (a - 12, BASE + 0x8A968),
        (a - 4, registers["ebp"]),
        (a, allocator.RETURN),
    ):
        if at == a:
            # The generic law has a fixed RETURN sentinel; actual installed bytes
            # are checked below and no other event/page/pointer cell is changed.
            events.append(dict(access="read", address=a, width=4, value=value))
        else:
            r(at, value)
    wanted = dict(
        relation=dict(result=destination, request=16, metadata=None),
        registers=dict(
            registers, eax=destination, ecx=destination, edx=0xB0000001, esp=a + 8
        ),
        flags=_add_flags(a - 8, 4),
        flag_mask=0x8D5,
        stack=_stack(memory),
        payload=_read(pages, DATA, 16384),
        events=events,
    )
    child = _normalize(
        lambda: allocator._expected(
            dict(count=2, pointer=destination),
            dict(registers),
            _stack(pages),
            _read(pages, DATA, 16384),
            stack_base=STACK,
            data_base=DATA,
        )
    )
    _require(_same_packet(child, wanted), "path clone2 allocation primitive differs")
    _require(
        int.from_bytes(_read(pages, a), "little") == continuation,
        "path clone2 allocation installed continuation differs",
    )
    wanted["events"][-1]["value"] = continuation
    return wanted, imported


def _scalar_packet_law(registers, xmm, pages, source, destination, continuation):
    """Independent handwritten prediction of the complete ten-field scalar child."""
    c = registers["esp"]
    snapshot = _read(pages, source, 16)
    memory, events, event = _event_law(pages)
    event("write", c - 4, registers["ebp"])
    event("read", c + 4, destination)
    event("write", c - 8, registers["esi"])
    for offset in (0, 4, 8, 12):
        word = int.from_bytes(snapshot[offset : offset + 4], "little")
        event("read", source + offset, word)
        event("write", destination + offset, word)
    for at, value in (
        (c - 8, registers["esi"]),
        (c - 4, registers["ebp"]),
        (c, continuation),
    ):
        event("read", at, value)
    wanted = dict(
        pages=_pages(memory),
        registers=dict(
            registers,
            eax=destination + 16,
            ecx=int.from_bytes(snapshot[12:], "little"),
            esp=c + 4,
        ),
        xmm=dict(xmm),
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=continuation,
        source_snapshot=snapshot,
        events=events,
        trace_rvas=[
            f"0x{pc:08x}"
            for pc in (
                0x8ABA0,
                0x8ABA1,
                0x8ABA3,
                0x8ABA6,
                0x8ABA7,
                0x8ABA9,
                0x8ABAB,
                0x8ABAD,
            )
            + (
                0x8ABB0,
                0x8ABB2,
                0x8ABB4,
                0x8ABB6,
                0x8ABB8,
                0x8ABBB,
                0x8ABBE,
                0x8ABC1,
                0x8ABC4,
                0x8ABC6,
            )
            * 2
            + (0x8ABC8, 0x8ABC9, 0x8ABCA)
        ],
    )
    child = _normalize(
        lambda: scalar.apply(
            pages=dict(pages),
            registers=dict(registers),
            xmm=dict(xmm),
            source=source,
            destination=destination,
            return_address=continuation,
            entry_flags=0x202,
        )
    )
    _require(_same_packet(child, wanted), "path clone2 scalar primitive differs")
    return wanted


def _expected(vector, fixture):
    g = geometry(vector)
    _require(
        type(fixture) is dict
        and set(fixture) == FIXTURE_KEYS
        and _same_packet(fixture, _fixture(vector)),
        "path clone2 fixture recipe differs",
    )
    initial, xmm = fixture["registers"], fixture["xmm"]
    p, h, j, o, d = (
        g[k]
        for k in (
            "entry",
            "destination_header",
            "source_header",
            "source",
            "destination",
        )
    )
    frame_join(p)
    memory, events, event = _event_law(fixture["pages"])
    boundaries = {
        "parent_entry": _boundary(
            initial, xmm, memory, events, BASE + 0x9A8E0, 0x246, 0xFFFFFFFF
        )
    }
    for at, value in (
        (p - 4, initial["ebp"]),
        (p - 8, initial["esi"]),
        (p - 12, initial["edi"]),
    ):
        event("write", at, value)
    event("read", p + 4, j)
    for at in (h, h + 4, h + 8):
        event("write", at, 0)
    event("read", j + 4, o + 16)
    event("read", j, o)
    event("write", p - 16, 2)
    event("write", p - 20, BASE + 0x9A90C)
    regs = dict(initial, eax=2, esi=h, edi=j, ebp=p - 4, esp=p - 20)
    boundaries["reserve_entry"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9AC40, 0, 0xC5
    )
    for at, value in ((p - 24, p - 4), (p - 28, h), (p - 32, j)):
        event("write", at, value)
    event("read", p - 16, 2)
    for at in (h, h + 4, h + 8):
        event("write", at, 0)
    event("write", p - 36, 2)
    event("write", p - 40, BASE + 0x9AC78)
    regs.update(edi=2, ebp=p - 24, esp=p - 40)
    boundaries["allocation_entry"] = _boundary(
        regs, xmm, memory, events, BASE + 0x8A920, 0x95, 0x8D5
    )
    allocated, imported = _allocation_packet_law(
        regs, _pages(memory), d, BASE + 0x9AC78
    )
    prefix = copy.deepcopy(events)
    imported["events"] = prefix + imported["events"]
    imported["xmm"] = dict(xmm)
    imported.update(entry_esp=p - 88, words=[BASE + 0x389463, HEAP, 0, 16])
    events.extend(copy.deepcopy(allocated["events"]))
    _write(memory, STACK, allocated["stack"])
    regs = dict(allocated["registers"])
    boundaries["allocation_return"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9AC78, allocated["flags"], 0x8D5
    )
    for at, value in ((h, d), (h + 4, d)):
        event("write", at, value)
    event("read", h, d)
    event("write", h + 8, d + 16)
    for at, value in (
        (p - 32, j),
        (p - 28, h),
        (p - 24, p - 4),
        (p - 20, BASE + 0x9A90C),
    ):
        event("read", at, value)
    regs.update(eax=((d + 16) & 0xFFFFFF00) | 1, edi=j, ebp=p - 4, esp=p - 12)
    boundaries["reserve_return"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9A90C, allocated["flags"], 0x8D5
    )
    event("read", j + 4, o + 16)
    event("write", p - 16, d)
    event("read", p + 4, j)
    event("write", p - 20, j)
    event("write", p - 24, d)
    event("read", h, d)
    event("write", p - 28, d)
    event("read", j, o)
    event("write", p - 32, BASE + 0x9A921)
    regs.update(edx=o + 16, ecx=o, esp=p - 32)
    boundaries["scalar_entry"] = _boundary(
        regs, xmm, memory, events, BASE + 0x8ABA0, 0, 0x8C5
    )
    copied = _scalar_packet_law(regs, xmm, _pages(memory), o, d, BASE + 0x9A921)
    events.extend(copy.deepcopy(copied["events"]))
    # The original event closure refers to memory: preserve that dictionary while
    # adopting all actual child pages, rather than reseeding any native fixture.
    for page, payload in copied["pages"].items():
        memory[page][:] = payload
    regs = dict(copied["registers"])
    boundaries["scalar_return"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9A921, 0x44, 0x8D5
    )
    event("write", h + 4, d + 16)
    for at, value in (
        (p - 12, initial["edi"]),
        (p - 8, initial["esi"]),
        (p - 4, initial["ebp"]),
        (p, RETURN),
    ):
        event("read", at, value)
    regs.update(
        eax=h, esi=initial["esi"], edi=initial["edi"], ebp=initial["ebp"], esp=p + 8
    )
    _require(
        len(TRACE) == 136 and len(events) == 83, "path clone2 source count differs"
    )
    return dict(
        geometry=g,
        registers=regs,
        xmm=dict(xmm),
        flags=_add_flags(p - 28, 16),
        flag_mask=0x8D5,
        df=0,
        endpoint=RETURN,
        pages=_pages(memory),
        events=events,
        trace_rvas=[f"0x{pc:08x}" for pc in TRACE],
        boundaries=boundaries,
        allocation_packet=allocated,
        scalar_packet=copied,
        imported=imported,
        source_snapshot=_read(fixture["pages"], o, 16),
    )


ALLOC_POINTS_SHA256 = "81d5140ea35625509678a4ca5204b8fb0dd6839199cf0f8673ee922fcb65ecbd"


def _preflight(sources):
    def run():
        _require(
            type(sources) is dict and set(sources) == set(SOURCE_PINS),
            "path clone2 source partition differs",
        )
        common._validate_json_tree(sources, "sources")
        identities = {
            k: common._source_identity(sources[k], *pin, k)
            for k, pin in SOURCE_PINS.items()
        }
        identity = sources["program_facts"]["identity"]
        _require(
            identity["executable_sha256"] == EXE_SHA256
            and all(
                _same_packet(sources[k]["build_identity"], identity)
                for k in SOURCE_PINS
                if k != "program_facts"
            ),
            "path clone2 source build differs",
        )
        indexed = {
            int(f["entry_rva"], 16): f for f in sources["program_facts"]["functions"]
        }
        _require(
            len(indexed) == len(sources["program_facts"]["functions"]),
            "path clone2 duplicate atlas entry",
        )
        for a, (n, h) in BODY_PINS.items():
            f = indexed[a]
            _require(
                f["body_size"] == n
                and f["body_sha256"] == h
                and f["ranges"] == [dict(start_rva=f"0x{a:08x}", size=n)],
                "path clone2 atlas body differs",
            )
        _require(
            sources["allocation_conformance"]["source_composition_sha256"]
            == SOURCE_PINS["allocation_composition"][1],
            "path clone2 allocation source join differs",
        )
        return identities

    return _normalize(run)


def _allocation_points(sources):
    points = sorted(
        [
            p
            for b in sources["allocation_conformance"]["bodies"].values()
            for p in b["points"]
        ],
        key=lambda p: int(p["rva"], 16),
    )
    _require(
        _canonical_sha256(points) == ALLOC_POINTS_SHA256,
        "path clone2 allocation point identity differs",
    )
    return points


def _checked_code_packet(codes, points):
    """Direct calls are anchored by sealed full-body hashes and exact extents.

    New point boundaries are literal source facts, not caller-selected labels.
    Existing allocation points also have their independently pinned packet hash.
    """

    def run():
        _require(
            type(codes) is dict
            and set(codes) == set(BODY_PINS)
            and all(type(k) is int for k in codes)
            and type(points) is list
            and all(
                type(p) is dict
                and set(p) == {"rva", "size", "sha256"}
                and all(type(k) is str for k in p)
                and type(p["rva"]) is str
                and type(p["size"]) is int
                and p["size"] > 0
                and type(p["sha256"]) is str
                for p in points
            ),
            "path clone2 direct code identity differs",
        )
        _require(
            points == sorted(points, key=lambda p: int(p["rva"], 16)),
            "path clone2 direct point order differs",
        )
        allocation = [
            p
            for p in points
            if int(p["rva"], 16)
            not in {pc for order in STATIC_ORDERS.values() for pc in order}
        ]
        _require(
            _canonical_sha256(allocation) == ALLOC_POINTS_SHA256,
            "path clone2 direct allocation points differ",
        )
        allowed = {}
        for a, b in BODIES:
            _require(
                type(codes[a]) is bytes
                and len(codes[a]) == b - a
                and hashlib.sha256(codes[a]).hexdigest() == BODY_PINS[a][1],
                "path clone2 direct body bytes differ",
            )
            rows = [p for p in points if a <= int(p["rva"], 16) < b]
            if a in STATIC_ORDERS:
                _require(
                    tuple(int(p["rva"], 16) for p in rows) == STATIC_ORDERS[a],
                    "path clone2 direct new point identity differs",
                )
            cursor = a
            for row in rows:
                pc = int(row["rva"], 16)
                _require(
                    row["rva"] == f"0x{pc:08x}"
                    and pc == cursor
                    and pc + row["size"] <= b
                    and hashlib.sha256(
                        codes[a][pc - a : pc - a + row["size"]]
                    ).hexdigest()
                    == row["sha256"],
                    "path clone2 direct instruction bytes differ",
                )
                allowed[pc] = row
                cursor += row["size"]
            _require(cursor == b, "path clone2 direct point extent differs")
        _require(
            len(allowed) == len(points) == 174,
            "path clone2 direct point partition differs",
        )
        return allowed

    return _normalize(run)


def _load_code(data, image, sources):
    def run():
        import capstone

        _preflight(sources)
        _require(
            type(data) is bytes
            and hashlib.sha256(data).hexdigest() == EXE_SHA256
            and image.image_base == BASE
            and capstone.__version__ == "5.0.7",
            "path clone2 executable differs",
        )
        old = {p["rva"]: p for p in _allocation_points(sources)}
        decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        codes, points = {}, []
        for a, b in BODIES:
            offset = image.rva_span_to_file_offset(a, b - a)
            _require(offset is not None, "path clone2 selected body unmapped")
            payload = data[offset : offset + b - a]
            rows = [common._point(r) for r in decoder.disasm(payload, BASE + a)]
            if a not in STATIC_ORDERS:
                _require(
                    all(_same_packet(p, old.get(p["rva"])) for p in rows),
                    "path clone2 loaded allocation point differs",
                )
            codes[a] = payload
            points.extend(rows)
        points.sort(key=lambda p: int(p["rva"], 16))
        _checked_code_packet(codes, points)
        return codes, points

    return _normalize(run)


def _check_boundary(machine, ids, xmm_ids, x, wanted, events, label):
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        _same_packet(
            {r: machine.reg_read(i) for r, i in ids.items()}, wanted["registers"]
        )
        and _same_packet(
            {r: machine.reg_read(i) for r, i in xmm_ids.items()}, wanted["xmm"]
        )
        and flags & wanted["flag_mask"] == wanted["flags"]
        and flags & 0x400 == 0
        and machine.reg_read(x.UC_X86_REG_EIP) == wanted["endpoint"]
        and _same_packet(events, wanted["events"])
        and all(
            bytes(machine.mem_read(p, 4096)) == v for p, v in wanted["pages"].items()
        ),
        "path clone2 " + label + " differs",
    )


CONTROLS = {
    **{
        stage + "_" + kind: "path clone2 " + stage.replace("_", " ") + " differs"
        for stage in (
            "parent_entry",
            "reserve_entry",
            "allocation_entry",
            "allocation_return",
            "reserve_return",
            "scalar_entry",
            "scalar_return",
        )
        for kind in ("gpr", "xmm", "flags", "df", "page")
    },
    "reserve_full_eax": "path clone2 reserve return differs",
    "heap_request": "path clone2 allocation handoff differs",
    **{
        name: "path clone2 supplied response preservation differs"
        for name in ("response_result", "response_gpr", "response_xmm", "response_page")
    },
    **{
        name: "path clone2 final pages differ"
        for name in (
            "ancestor",
            "source",
            "source_header",
            "destination",
            "header_padding",
            "feature_padding",
            "iat_padding",
            "unused_scalar_word",
        )
    },
    **{
        name: "path clone2 final ABI differs"
        for name in (
            "final_eax",
            "final_nonvolatile",
            "final_xmm",
            "final_flags",
            "final_df",
            "final_endpoint",
        )
    },
    **{
        name: "path clone2 final events differ"
        for name in (
            "missing_read_record",
            "restored_write_record",
            "duplicate_write_record",
        )
    },
    "trace_record": "path clone2 final native path differs",
}


def _run_case(codes, points, vector, negative=None, *, capture=None):
    _require(
        negative is None or type(negative) is str and negative in CONTROLS,
        "invalid path clone2 control",
    )
    fixture = _fixture(vector)
    wanted = _expected(vector, fixture)
    allowed = _checked_code_packet(codes, points)
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "path clone2 reviewed Unicorn required")
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    machine.ctl_set_cpu_model(CPU_MODEL)
    _require(machine.ctl_get_cpu_model() == CPU_MODEL, "path clone2 CPU model differs")
    code_pages = {(BASE + pc) & ~4095 for a, b in BODIES for pc in range(a, b)} | {
        IMPORT,
        RETURN,
    }
    _require(
        not code_pages.intersection(fixture["pages"]),
        "path clone2 runtime mappings overlap",
    )
    for page in sorted(code_pages):
        machine.mem_map(page, 4096)
        machine.mem_write(page, bytes([0xCC]) * 4096)
    for page, payload in fixture["pages"].items():
        machine.mem_map(page, 4096)
        machine.mem_write(page, payload)
    for address, payload in codes.items():
        machine.mem_write(BASE + address, payload)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in REGISTERS}
    xmm_ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in XMM}
    for r, value in fixture["registers"].items():
        machine.reg_write(ids[r], value)
    for r, value in fixture["xmm"].items():
        machine.reg_write(xmm_ids[r], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, fixture["entry_flags"])
    events, trace, boundaries, summaries = [], [], [], []
    resume = None
    g = wanted["geometry"]

    def flip(address):
        machine.mem_write(address, bytes([machine.mem_read(address, 1)[0] ^ 1]))

    def observe(name, state):
        raw = machine.reg_read(x.UC_X86_REG_EFLAGS)
        return dict(
            name=name,
            registers={r: machine.reg_read(i) for r, i in ids.items()},
            xmm={r: machine.reg_read(i) for r, i in xmm_ids.items()},
            eflags=raw,
            flags=raw & state["flag_mask"],
            flag_mask=state["flag_mask"],
            df=(raw >> 10) & 1,
            endpoint=machine.reg_read(x.UC_X86_REG_EIP),
            pages_sha256=_page_hashes(
                {p: bytes(machine.mem_read(p, 4096)) for p in fixture["pages"]}
            ),
            events_sha256=_canonical_sha256(events),
        )

    def mutate(name):
        if negative == name + "_gpr":
            machine.reg_write(ids["edx"], machine.reg_read(ids["edx"]) ^ 1)
        if negative == name + "_xmm":
            machine.reg_write(xmm_ids["xmm7"], machine.reg_read(xmm_ids["xmm7"]) ^ 1)
        if negative in (name + "_flags", name + "_df"):
            machine.reg_write(
                x.UC_X86_REG_EFLAGS,
                machine.reg_read(x.UC_X86_REG_EFLAGS)
                ^ (0x400 if negative == name + "_df" else 1),
            )
        if negative == name + "_page":
            flip(FEATURE_PAGE + 1)
        if negative == "reserve_full_eax" and name == "reserve_return":
            machine.reg_write(ids["eax"], 1)

    def on_code(m, address, size, user):
        nonlocal resume
        if address == RETURN:
            m.emu_stop()
            return
        if address == IMPORT:
            state = wanted["imported"]
            _require(not summaries, "path clone2 repeated allocation response")
            sp = m.reg_read(ids["esp"])
            words = [
                int.from_bytes(m.mem_read(sp + 4 * i, 4), "little") for i in range(4)
            ]
            if negative == "heap_request":
                words[3] ^= 1
                flip(sp + 12)
            _require(
                sp == state["entry_esp"] and words == state["words"],
                "path clone2 allocation handoff differs",
            )
            _check_boundary(
                m, ids, xmm_ids, x, state, events, "allocation imported ABI"
            )
            record = observe("allocation", state)
            record.update(role="allocation", entry_esp=sp, words=list(words))
            record.pop("name")
            summaries.append(record)
            before = {p: bytes(m.mem_read(p, 4096)) for p in fixture["pages"]}
            response = dict(
                state["registers"],
                eax=g["destination"],
                ecx=0xA0000001,
                edx=0xB0000001,
                esp=sp + 16,
            )
            for r in ("eax", "ecx", "edx", "esp"):
                m.reg_write(ids[r], response[r])
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            if negative == "response_result":
                m.reg_write(ids["eax"], 0)
            if negative == "response_gpr":
                m.reg_write(ids["ebx"], m.reg_read(ids["ebx"]) ^ 1)
            if negative == "response_xmm":
                m.reg_write(xmm_ids["xmm6"], m.reg_read(xmm_ids["xmm6"]) ^ 1)
            if negative == "response_page":
                flip(FEATURE_PAGE + 1)
            _require(
                _same_packet({r: m.reg_read(i) for r, i in ids.items()}, response)
                and _same_packet(
                    {r: m.reg_read(i) for r, i in xmm_ids.items()}, fixture["xmm"]
                )
                and m.reg_read(x.UC_X86_REG_EFLAGS) == 0x246
                and all(bytes(m.mem_read(p, 4096)) == b for p, b in before.items()),
                "path clone2 supplied response preservation differs",
            )
            resume = words[0]
            m.emu_stop()
            return
        pc = address - BASE
        _require(
            pc in allowed and size == allowed[pc]["size"],
            "path clone2 escaped selected code",
        )
        for name, state in wanted["boundaries"].items():
            if address == state["endpoint"]:
                mutate(name)
                _check_boundary(
                    m, ids, xmm_ids, x, state, events, name.replace("_", " ")
                )
                boundaries.append(observe(name, state))
        trace.append(f"0x{pc:08x}")
        _require(
            trace == wanted["trace_rvas"][: len(trace)],
            "path clone2 native path differs",
        )

    def on_memory(m, access, address, width, value, user):
        writing = access == uc.UC_MEM_WRITE
        _require(width == 4, "path clone2 access width differs")
        row = dict(
            access="write" if writing else "read",
            address=address,
            width=width,
            value=(
                value & 0xFFFFFFFF
                if writing
                else int.from_bytes(m.mem_read(address, width), "little")
            ),
        )
        _require(
            len(events) < len(wanted["events"])
            and _same_packet(row, wanted["events"][len(events)]),
            "path clone2 ordered memory events differ",
        )
        events.append(row)

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    next_pc = BASE + 0x9A8E0
    for _ in range(2):
        resume = None
        machine.emu_start(next_pc, 0, count=10000)
        if resume is None:
            break
        next_pc = resume
    corrupt = {
        "ancestor": g["entry"] + 8,
        "source": g["source"],
        "source_header": g["source_header"] + 8,
        "destination": g["destination"] + 15,
        "header_padding": g["destination_header"] + 12,
        "feature_padding": FEATURE_PAGE + 1,
        "iat_padding": ALLOC_IAT & ~4095,
        "unused_scalar_word": g["entry"] - 24,
    }
    if negative in corrupt:
        flip(corrupt[negative])
    if negative == "final_eax":
        machine.reg_write(ids["eax"], machine.reg_read(ids["eax"]) ^ 1)
    if negative == "final_nonvolatile":
        machine.reg_write(ids["ebx"], machine.reg_read(ids["ebx"]) ^ 1)
    if negative == "final_xmm":
        machine.reg_write(xmm_ids["xmm0"], machine.reg_read(xmm_ids["xmm0"]) ^ 1)
    if negative in ("final_flags", "final_df"):
        machine.reg_write(
            x.UC_X86_REG_EFLAGS,
            machine.reg_read(x.UC_X86_REG_EFLAGS)
            ^ (0x400 if negative == "final_df" else 1),
        )
    if negative == "final_endpoint":
        machine.reg_write(x.UC_X86_REG_EIP, RETURN + 1)
    if negative == "missing_read_record":
        events.pop()
    if negative == "restored_write_record":
        events.extend(
            [
                dict(access="write", address=g["source"], width=4, value=1),
                dict(
                    access="write",
                    address=g["source"],
                    width=4,
                    value=int.from_bytes(
                        _read(fixture["pages"], g["source"]), "little"
                    ),
                ),
            ]
        )
    if negative == "duplicate_write_record":
        events.append(
            copy.deepcopy(
                next(
                    e
                    for e in wanted["events"]
                    if e["access"] == "write" and e["address"] == g["destination"]
                )
            )
        )
    if negative == "trace_record":
        trace.append("0x0009ac8d")
    regs = {r: machine.reg_read(i) for r, i in ids.items()}
    xmms = {r: machine.reg_read(i) for r, i in xmm_ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    pages = {p: bytes(machine.mem_read(p, 4096)) for p in fixture["pages"]}
    _require(
        _same_packet(regs, wanted["registers"])
        and _same_packet(xmms, wanted["xmm"])
        and flags & wanted["flag_mask"] == wanted["flags"]
        and flags & 0x400 == 0
        and machine.reg_read(x.UC_X86_REG_EIP) == RETURN,
        "path clone2 final ABI differs",
    )
    _require(_same_packet(pages, wanted["pages"]), "path clone2 final pages differ")
    _require(_same_packet(events, wanted["events"]), "path clone2 final events differ")
    _require(
        _same_packet(trace, wanted["trace_rvas"]),
        "path clone2 final native path differs",
    )
    _require(
        [b["name"] for b in boundaries] == list(wanted["boundaries"])
        and len(summaries) == 1,
        "path clone2 boundary or allocation count differs",
    )
    result = dict(
        vector=dict(vector),
        registers=regs,
        xmm=xmms,
        flags=flags & wanted["flag_mask"],
        flag_mask=wanted["flag_mask"],
        df=0,
        trace_rvas=trace,
        events_sha256=_canonical_sha256(events),
        pages_sha256=_page_hashes(pages),
        memory_event_count=len(events),
        boundaries=boundaries,
        summaries=summaries,
    )
    if capture is not None:
        capture(machine, dict(ids), copy.deepcopy(wanted), copy.deepcopy(fixture))
    return result


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _normalize(lambda: common._load_executable(Path(executable)))
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, v) for v in vectors()]
    controls = []
    for name, reason in CONTROLS.items():
        try:
            _run_case(codes, points, vectors()[-1], name)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "path clone2 incidental control: " + name + ": " + str(exc),
            )
            controls.append(dict(name=name, rejected=True, reason=reason))
        else:
            raise ConformanceError("path clone2 control survived: " + name)
    executed = sorted({pc for o in observations for pc in o["trace_rvas"]})
    _require(
        set(executed) == {f"0x{p:08x}" for p in TRACE},
        "path clone2 native coverage differs",
    )
    n = len(observations)
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=copy.deepcopy(sources["program_facts"]["identity"]),
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{a:08x}",
                    exclusive_end_rva=f"0x{b:08x}",
                    sha256=hashlib.sha256(codes[a]).hexdigest(),
                )
                for a, b in BODIES
            ],
            points=points,
        ),
        vectors=vectors(),
        engine=dict(
            name="Unicorn",
            version="2.1.4",
            architecture="x86_32",
            cpu_model=dict(id=CPU_MODEL, name="UC_CPU_X86_HASWELL"),
        ),
        executed_rvas=executed,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=n,
            loaded_sites=len(points),
            loaded_bytes=sum(map(len, codes.values())),
            executed_sites=len(executed),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            memory_events=sum(o["memory_event_count"] for o in observations),
            allocation_requests=sum(len(o["summaries"]) for o in observations),
            allocation_request_bytes=16 * n,
            free_requests=0,
            copied_bytes=16 * n,
            source_bytes_preserved=16 * n,
            xmm_preserved_cases=n,
            scalar_iterations=2 * n,
            wide_reads=0,
            wide_writes=0,
            controls=len(controls),
            opaque_instructions=0,
            effect_record_sites=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Finite continuous native two-record movement path clone with ordinary 16-byte supplied allocation and scalar DWORD copy",
            premises=[
                "Exactly 48 synthetic alignment and profile recipes with disjoint 16-byte source and positive destination extents",
                "One Unicorn executes path owner reserve ordinary allocation chain and scalar loop continuously",
                "One supplied successful HeapAlloc response preserves full pages, nonvolatile general registers, all eight XMM registers and DF zero",
                "Complete unchanged seven-field ordinary count-two allocation packet checked before its fixed RETURN event sentinel is bound to the installed continuation",
                "Complete independent ten-field actual-page scalar child predicts four ordered DWORD transfers and preserves all other pages",
                "Reserve success sets AL to one and retains pointer-derived high EAX bits; full ABI and pages checked at all seven native boundaries and the imported call",
                "Architecturally defined flag masks and DF zero are distinct from raw finite VM EFLAGS captures",
            ],
            not_claimed=[
                "Allocator ownership unmapping operating-system allocation failure retry unwind exception or hardware execution",
                "Arbitrary path lengths overlapping paths allocation pointer domains or general record-vector growth",
                "String copy record construction assignment append destruction AddMove count greater than one AddCharge gameplay or runtime Lua binding",
                "Injected event and path record mutations do not establish execution of represented writes or instructions",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "path clone2 executable changed",
    )
    common._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    def run():
        common._validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256
            and _same_packet(evidence["source_receipts"], ids)
            and _same_packet(evidence["vectors"], vectors()),
            "sealed path clone2 receipt differs",
        )
        common._assert_publication_safe(evidence)
        return dict(
            status="structurally_verified",
            evidence_sha256=SEALED_SHA256,
            summary=copy.deepcopy(evidence["summary"]),
        )

    return _normalize(run)


def build_conformance(executable, sources):
    def run():
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_conformance(executable, evidence, sources):
    def run():
        validate_structure(evidence, sources)
        _require(
            _same_packet(_build_unsealed(executable, sources), evidence),
            "path clone2 native rebuild differs",
        )
        return dict(
            status="verified",
            evidence_sha256=SEALED_SHA256,
            summary=copy.deepcopy(evidence["summary"]),
        )

    return _normalize(run)


def encode_conformance(value):
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
