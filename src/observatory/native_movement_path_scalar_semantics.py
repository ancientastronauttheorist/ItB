"""Actual-page law for the selected disjoint zero-or-positive-count 08ABA0 scalar clone.

This is a logical architectural DWORD-access law. It creates no fixture and
performs no allocation, native delegation, SIMD transfer or ownership change.
"""

from __future__ import annotations

BASE = 0x00400000
REGISTERS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
CODE_RANGES = (
    (0x8ABA0, 0x8ABCB),
    (0x9A8E0, 0x9A92F),
    (0x9AC40, 0x9AC97),
    (0x8A920, 0x8A97B),
    (0x3574DB, 0x35750E),
    (0x379F52, 0x379F5D),
    (0x38942B, 0x389479),
)
PREFIX_TRACE = (0x8ABA0, 0x8ABA1, 0x8ABA3, 0x8ABA6, 0x8ABA7, 0x8ABA9, 0x8ABAB, 0x8ABAD)
LOOP_TRACE = (
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
SUFFIX_TRACE = (0x8ABC8, 0x8ABC9, 0x8ABCA)
BODY_SIZE = 43
BODY_SHA256 = "92494ea2dfd86d06ce373c9837f55d42e6c62746bd9c2c3c26d2a8af6abe938b"


class ScalarCloneError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise ScalarCloneError(message)


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= 0xFFFFFFFF, "invalid " + label)
    return value


def _read(pages, address, size=4):
    _require(0 <= address and address + size <= 2**32, "scalar read wraps")
    _require(
        all((address + i) & ~4095 in pages for i in range(size)), "scalar read unmapped"
    )
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def apply(*, pages, registers, xmm, source, destination, return_address, entry_flags):
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
        "invalid scalar pages",
    )
    _require(
        type(registers) is dict
        and set(registers) == set(REGISTERS)
        and all(
            type(r) is str and type(v) is int and 0 <= v <= 0xFFFFFFFF
            for r, v in registers.items()
        ),
        "invalid scalar registers",
    )
    _require(
        type(xmm) is dict
        and set(xmm) == set(XMM)
        and all(
            type(r) is str and type(v) is int and 0 <= v < 2**128
            for r, v in xmm.items()
        ),
        "invalid scalar XMM",
    )
    for value, label in (
        (source, "source"),
        (destination, "destination"),
        (return_address, "return address"),
        (entry_flags, "entry flags"),
    ):
        _u32(value, label)
    _require(
        entry_flags & ~0xAD7 == 0 and entry_flags & 2 == 2,
        "invalid scalar ordinary flags",
    )
    c = registers["esp"]
    end = registers["edx"]
    _require(end >= source and (end - source) % 8 == 0, "scalar source count differs")
    size = end - source
    count = size // 8
    _require(
        8 <= c <= 0xFFFFFFFF - 20
        and end <= 0xFFFFFFFF
        and destination + size <= 0xFFFFFFFF
        and (count == 0 or source > 0 and destination > 0),
        "scalar extent wraps or positive copy is null",
    )
    spans = ((c - 8, c + 20), (source, end), (destination, destination + size))
    active_spans = tuple((a, b) for a, b in spans if a < b)
    _require(
        all(
            b <= d or e <= a
            for i, (a, b) in enumerate(active_spans)
            for d, e in active_spans[i + 1 :]
        ),
        "scalar extents overlap",
    )
    _require(
        return_address > 0
        and not (BASE + 0x8ABA0 <= return_address < BASE + 0x8ABCB)
        and all(not (a <= return_address < b) for a, b in active_spans),
        "scalar return overlaps data or scalar body",
    )
    code_pages = {(BASE + p) & ~4095 for a, b in CODE_RANGES for p in range(a, b)}
    _require(not code_pages.intersection(pages), "scalar pages overlap selected code")
    snapshot = _read(pages, source, size)
    _read(pages, destination, size)
    _read(pages, c - 8, 28)
    _require(
        registers["ecx"] == source
        and registers["edx"] == source + size
        and int.from_bytes(_read(pages, c), "little") == return_address
        and int.from_bytes(_read(pages, c + 4), "little") == destination,
        "scalar installed entry differs",
    )
    memory = {p: bytearray(b) for p, b in pages.items()}
    events = []

    def event(access, address, value):
        if access == "write":
            for i, b in enumerate(value.to_bytes(4, "little")):
                memory[(address + i) & ~4095][(address + i) & 4095] = b
        else:
            _require(
                int.from_bytes(_read(memory, address), "little") == value,
                "scalar expected read differs",
            )
        events.append(dict(access=access, address=address, width=4, value=value))

    event("write", c - 4, registers["ebp"])
    event("read", c + 4, destination)
    event("write", c - 8, registers["esi"])
    for offset in range(0, size, 4):
        word = int.from_bytes(snapshot[offset : offset + 4], "little")
        event("read", source + offset, word)
        event("write", destination + offset, word)
    event("read", c - 8, registers["esi"])
    event("read", c - 4, registers["ebp"])
    event("read", c, return_address)
    return dict(
        pages={p: bytes(b) for p, b in memory.items()},
        registers=dict(
            registers,
            eax=destination + size,
            ecx=int.from_bytes(snapshot[-4:], "little") if count else registers["ecx"],
            esp=c + 4,
        ),
        xmm=dict(xmm),
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
        source_snapshot=snapshot,
        events=events,
        trace_rvas=[
            f"0x{p:08x}"
            for p in (PREFIX_TRACE if count else PREFIX_TRACE[:-1])
            + LOOP_TRACE * count
            + SUFFIX_TRACE
        ],
    )
