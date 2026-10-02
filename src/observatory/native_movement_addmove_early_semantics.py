"""Actual-page AddMove zero/one-count path with supplied ordinary free success.

This logical law constructs no fixture and performs no native delegation.
Record construction and parameter MOVSS are excluded from the selected arm.
"""

from __future__ import annotations
import copy
from src.observatory import native_movement_addmove_early_return_conformance as witness
from src.observatory import native_movement_addmove_normal_semantics as normal
from src.observatory import native_vector_deallocation_conformance_joined as deallocator

BASE, U32, COOKIE = 0x400000, 0xFFFFFFFF, 0x893F28
REGISTERS, XMM = witness.REGISTERS, witness.XMM
HEAP_GLOBAL, FREE_IAT, HEAP, IMPORT, ERROR = (
    normal.HEAP_GLOBAL,
    normal.FREE_IAT,
    normal.HEAP,
    normal.IMPORT,
    normal.ERROR,
)
PREFIX_TRACE, FREE_CALL_TRACE, FREE_TRACE, SUFFIX_TRACE = (
    witness.PREFIX_TRACE,
    witness.FREE_CALL_TRACE,
    witness.FREE_TRACE,
    witness.SUFFIX_TRACE,
)
BODY_PINS = {start: normal.BODY_PINS[start] for start, end in witness.BODIES}
SOURCE_PINS = dict(witness.SOURCE_PINS)
SOURCE_PINS["addmove_early"] = (witness.ANALYSIS_KIND, witness.SEALED_SHA256)
ANALYSIS_KIND = "pe_native_movement_addmove_early_semantics"


class EarlyMoveError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise EarlyMoveError(message)


def _normalize(operation):
    try:
        return operation()
    except EarlyMoveError:
        raise
    except Exception as exc:
        raise EarlyMoveError(str(exc)) from exc


_same_packet = normal._same_packet
_add_flags = normal._add_flags
_test = normal._test


def _read(pages, address, size=4):
    _require(
        type(address) is int
        and type(size) is int
        and 0 <= address
        and 0 <= size
        and address + size <= 2**32
        and all((address + i) & ~4095 in pages for i in range(size)),
        "early AddMove read unmapped or wraps",
    )
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def _write(pages, address, payload):
    for i, b in enumerate(payload):
        pages[(address + i) & ~4095][(address + i) & 4095] = b


def _pages(pages):
    return {p: bytes(b) for p, b in pages.items()}


def _validate(pages, registers, xmm, return_address, entry_flags):
    _require(
        type(pages) is dict
        and pages
        and all(
            type(p) is int
            and 0 <= p <= 0xFFFFF000
            and p % 4096 == 0
            and type(b) is bytes
            and len(b) == 4096
            for p, b in pages.items()
        ),
        "early AddMove page schema differs",
    )
    _require(
        type(registers) is dict
        and set(registers) == set(REGISTERS)
        and all(
            type(k) is str and type(v) is int and 0 <= v <= U32
            for k, v in registers.items()
        ),
        "early AddMove GPR schema differs",
    )
    _require(
        type(xmm) is dict
        and set(xmm) == set(XMM)
        and all(
            type(k) is str and type(v) is int and 0 <= v < 2**128
            for k, v in xmm.items()
        ),
        "early AddMove XMM schema differs",
    )
    _require(
        type(return_address) is int
        and 0 < return_address <= U32
        and type(entry_flags) is int
        and 0 <= entry_flags <= U32
        and entry_flags & ~0xAD7 == 0
        and entry_flags & 2 == 2,
        "early AddMove endpoint or ordinary flags differ",
    )
    g, h = registers["esp"], registers["ecx"]
    _require(
        g >= 0x2B8 and g + 20 <= U32 and 0 < h and h + 12 <= U32,
        "early AddMove frame/header wraps",
    )
    stack_base = min((g - 0x2B8) & ~4095, 0xFFFFE000)
    _read(pages, stack_base, 8192)
    _read(pages, h, 12)
    _read(pages, 0, 4)
    _read(pages, COOKIE, 4)
    begin, end, capacity = (
        int.from_bytes(_read(pages, g + n), "little") for n in (4, 8, 12)
    )
    if begin:
        _require(
            stack_base + 8192 <= ERROR or ERROR + 4096 <= stack_base,
            "early AddMove stack window overlaps error mapping",
        )
        _require(
            begin <= end <= capacity <= U32
            and (end - begin) % 8 == 0
            and (capacity - begin) % 8 == 0
            and (end - begin) // 8 <= 1
            and 1 <= (capacity - begin) // 8 <= 511,
            "early AddMove selected owned path differs",
        )
        _read(pages, begin, capacity - begin)
        _read(pages, ERROR, 4096)
        _read(pages, HEAP_GLOBAL & ~4095, 4096)
        _read(pages, FREE_IAT & ~4095, 4096)
        _require(
            int.from_bytes(_read(pages, HEAP_GLOBAL), "little") == HEAP
            and int.from_bytes(_read(pages, FREE_IAT), "little") == IMPORT,
            "early AddMove ordinary heap globals differ",
        )
    else:
        _require(end == capacity == 0, "early AddMove requires null triple")
    spans = [(g - 0x2B8, g + 20), (h, h + 12), (0, 4), (COOKIE, COOKIE + 4)]
    if begin:
        spans.extend(
            [
                (begin, capacity),
                (ERROR, ERROR + 4096),
                (HEAP_GLOBAL & ~4095, (HEAP_GLOBAL & ~4095) + 4096),
                (FREE_IAT & ~4095, (FREE_IAT & ~4095) + 4096),
            ]
        )
    _require(
        all(
            b <= c or d <= a
            for i, (a, b) in enumerate(spans)
            for c, d in spans[i + 1 :]
        ),
        "early AddMove protected spans overlap",
    )
    code_pages = {
        (BASE + pc) & ~4095
        for start, (size, sha) in BODY_PINS.items()
        for pc in range(start, start + size)
    }
    _require(
        not code_pages.intersection(pages), "early AddMove pages overlap selected code"
    )
    _require(
        all(
            not (BASE + start <= return_address < BASE + start + size)
            for start, (size, sha) in BODY_PINS.items()
        )
        and all(not (a <= return_address < b) for a, b in spans),
        "early AddMove return overlaps protected data or selected body",
    )
    _require(
        int.from_bytes(_read(pages, g), "little") == return_address,
        "early AddMove installed return differs",
    )
    return stack_base


def apply(*, pages, registers, xmm, return_address, entry_flags):
    def run():
        base = _validate(pages, registers, xmm, return_address, entry_flags)
        return _apply(
            dict(
                pages=pages,
                registers=registers,
                xmm=xmm,
                return_address=return_address,
                entry_flags=entry_flags,
            ),
            base,
        )

    return _normalize(run)


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


def _free_packet_law(regs, pages, pointer, count, stack_base):
    """Ordinary positive capacity count and stride8; exact8 fields against the unchanged generic law."""
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
        int.from_bytes(_read(pages, v), "little") == BASE + 0x257405,
        "movement free installed continuation differs",
    )
    wanted["events"][-1]["value"] = BASE + 0x257405
    wanted["stop"] = BASE + 0x257405
    return wanted


def _apply(fixture, stack_base):
    regs = dict(fixture["registers"])
    initial = dict(regs)
    xmm = dict(fixture["xmm"])
    g, f = regs["esp"], regs["esp"] - 4
    begin = int.from_bytes(_read(fixture["pages"], g + 4), "little")
    end = int.from_bytes(_read(fixture["pages"], g + 8), "little")
    capacity = int.from_bytes(_read(fixture["pages"], g + 12), "little")
    cookie = int.from_bytes(_read(fixture["pages"], COOKIE), "little")
    seh = int.from_bytes(_read(fixture["pages"], 0), "little")
    memory, events, e = _event_law(fixture["pages"])
    for access, address, value in (
        ("write", g - 4, initial["ebp"]),
        ("write", g - 8, 0xFFFFFFFF),
        ("write", g - 12, 0x007CA95E),
        ("read", 0, seh),
        ("write", g - 16, seh),
        ("read", COOKIE, cookie),
        ("write", g - 20, cookie ^ f),
        ("write", g - 0x280, initial["ebx"]),
        ("write", g - 0x284, initial["esi"]),
        ("write", g - 0x288, cookie ^ f),
        ("write", 0, g - 16),
        ("write", g - 8, 0),
        ("read", g + 8, end),
        ("read", g + 4, begin),
    ):
        e(access, address, value)
    count = (end - begin) // 8
    capacity_count = (capacity - begin) // 8
    regs.update(
        eax=count,
        ebx=initial["ebx"] & 0xFFFFFF00,
        edx=begin,
        esi=initial["ecx"],
        ebp=f,
        esp=g - 0x288,
    )
    free_entry, free_return, free_packet, imported = None, None, None, None
    trace = PREFIX_TRACE
    if begin:
        for access, address, value in (
            ("read", g + 12, capacity),
            ("write", g - 0x28C, 8),
            ("write", g - 0x290, capacity_count),
            ("write", g - 0x294, begin),
            ("write", g - 0x298, BASE + 0x257405),
        ):
            e(access, address, value)
        regs.update(ecx=capacity_count, esp=g - 0x298)
        free_entry = _boundary(
            regs, xmm, memory, events, BASE + 0x7800, _test(capacity_count), 0xC5
        )
        before = copy.deepcopy(events)
        free_packet = _free_packet_law(
            regs, _pages(memory), begin, capacity_count, stack_base
        )
        events.extend(copy.deepcopy(free_packet["events"]))
        _write(memory, stack_base, free_packet["stack"])
        regs = dict(free_packet["registers"])
        free_return = _boundary(
            regs, xmm, memory, events, BASE + 0x257405, free_packet["flags"], 0x8D5
        )
        import_pages = {p: bytearray(v) for p, v in free_entry["pages"].items()}
        for row in free_packet["events"][:16]:
            if row["access"] == "write":
                _write(import_pages, row["address"], row["value"].to_bytes(4, "little"))
        v = g - 0x298
        imported = dict(
            role="free",
            entry_esp=v - 32,
            words=[BASE + 0x389172, HEAP, 0, begin],
            **_boundary(
                dict(
                    free_entry["registers"],
                    eax=0x1FFFFFFF,
                    ecx=begin,
                    edx=7,
                    ebp=v - 16,
                    esp=v - 32,
                ),
                xmm,
                import_pages,
                before + free_packet["events"][:16],
                IMPORT,
                _test(begin),
                0x8C5,
            ),
        )
        regs["esp"] += 12
        trace = trace + FREE_CALL_TRACE + FREE_TRACE + (0x257405,)
    suffix_rows = (
        ("read", g - 16, seh),
        ("write", 0, seh),
        ("read", g - 0x288, cookie ^ f),
        ("read", g - 0x284, initial["esi"]),
        ("read", g - 0x280, initial["ebx"]),
        ("read", g - 20, cookie ^ f),
        ("write", g - 0x280, BASE + 0x257421),
        ("read", COOKIE, cookie),
        ("read", g - 0x280, BASE + 0x257421),
        ("read", g - 4, initial["ebp"]),
        ("read", g, fixture["return_address"]),
    )
    for access, address, value in suffix_rows[:7]:
        e(access, address, value)
    final = dict(
        initial, eax=0, ecx=cookie, edx=(0xB0000001 if begin else 0), esp=g + 20
    )
    checker_flags = _test(cookie)
    cookie_entry = _boundary(
        dict(final, ebp=f, esp=g - 0x280),
        xmm,
        memory,
        events,
        BASE + 0x3574CA,
        checker_flags,
        0x8C5,
    )
    for access, address, value in suffix_rows[7:]:
        e(access, address, value)
    pages = _pages(memory)
    # Reconstruct complete pages independently, using only source-derived frame
    # stores plus the primitive's checked stack transport for the owned path.
    _require(
        all(row["address"] != g + 16 for row in events),
        "movement ignored parameter was read",
    )
    result = dict(
        path=dict(
            begin=begin,
            end=end,
            capacity=capacity,
            count=count,
            parameter_bits=int.from_bytes(_read(fixture["pages"], g + 16), "little"),
        ),
        registers=final,
        xmm=xmm,
        pages=pages,
        events=events,
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=fixture["return_address"],
        trace_rvas=[f"0x{pc:08x}" for pc in trace + SUFFIX_TRACE],
        free_entry=free_entry,
        free_return=free_return,
        free_packet=free_packet,
        imported=imported,
        cookie_entry=cookie_entry,
    )
    _require(
        len(result["trace_rvas"]) == (82 if begin else 42)
        and len(events) == (50 if begin else 25),
        "early AddMove selected count differs",
    )
    return result
