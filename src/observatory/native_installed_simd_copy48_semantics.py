"""Installed forward copy48 snapshot law, with no fixture construction.

Events are the normalized Unicorn 2.1.4 eight-byte half-hook witness, not
architectural transfer widths. Architectural MOVDQU transfers are sixteen bytes.
Native execution, allocator ownership, resize and callback composition are separate.
"""

from __future__ import annotations

BASE, U32 = 0x00400000, 0xFFFFFFFF
ANALYSIS_KIND = "pe_native_installed_simd_copy48_semantics"
FEATURE_PAGE, FEATURE, FEATURE_WORD = 0x00893000, 0x00893F30, 0x93939393
REGISTERS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple(f"xmm{i}" for i in range(8))
RANGES = ((0x36E580, 0x36E5BF), (0x36EA4D, 0x36EAB7))
SOURCE_PINS = {
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
    "short_simd_semantics": (
        "pe_native_short_simd_copy_semantics",
        "ad1a4109a23a67bca5ae03b48dc3fe16cd2419000158a1d00f041c4fe488c17d",
    ),
    "short_simd_conformance": (
        "pe_native_short_simd_copy_conformance",
        "67e3ceefdb4b00bfab28653b34634f51a1ab5310fd27b2f2e4bdd75324de5865",
    ),
}
TRACE = (
    (
        0x36E580,
        0x36E581,
        0x36E582,
        0x36E586,
        0x36E58A,
        0x36E58E,
        0x36E590,
        0x36E592,
        0x36E594,
        0x36E596,
        0x36E598,
        0x36E59A,
        0x36E5A0,
        0x36E5A3,
        0x36E5A9,
        0x36E5AF,
        0x36E5B1,
        0x36E5B9,
        0x36EA4D,
        0x36EA4F,
        0x36EA51,
        0x36EA53,
        0x36EA56,
        0x36EA58,
        0x36EA5A,
        0x36EA60,
        0x36EA64,
        0x36EA69,
        0x36EA6D,
        0x36EA72,
        0x36EA75,
        0x36EA78,
        0x36EA79,
        0x36EA7B,
        0x36EA7E,
        0x36EA80,
        0x36EA82,
        0x36EA85,
    )
    + (0x36EA87, 0x36EA89, 0x36EA8B, 0x36EA8E, 0x36EA91, 0x36EA94) * 4
    + (
        0x36EA96,
        0x36EA98,
        0x36EA9B,
        0x36EAB0,
        0x36EAB4,
        0x36EAB5,
        0x36EAB6,
    )
)
EVENT_RVAS = (
    (
        0x36E580,
        0x36E581,
        0x36E582,
        0x36E586,
        0x36E58A,
        0x36E5B1,
        0x36EA60,
        0x36EA60,
        0x36EA64,
        0x36EA64,
        0x36EA69,
        0x36EA69,
        0x36EA6D,
        0x36EA6D,
    )
    + (0x36EA87, 0x36EA89) * 4
    + (0x36EAB0, 0x36EAB4, 0x36EAB5, 0x36EAB6)
)


class Copy48Error(ValueError):
    """An installed premise falls outside the exact forward copy48 domain."""


def _require(condition, message):
    if not condition:
        raise Copy48Error(message)


def _word(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)


def _span(address, size, label):
    _word(address, label)
    _require(address + size <= U32, label + " exclusive end wraps uint32")
    return address, address + size


def _disjoint(left, right):
    return left[1] <= right[0] or right[1] <= left[0]


def apply(
    *, pages, registers, xmm, source, destination, return_address, entry_flags=0x246
):
    """Predict an actual installed frame without synthesizing or relabeling pages.

    Entry is registers['esp']; caller words must already be return,D,O,48.
    Arbitrary uint32 DF-clear entry flags are accepted; final AF is unclaimed.
    Supplied pages are complete data pages. Copy code and return code are external.
    """
    _require(
        type(registers) is dict and set(registers) == set(REGISTERS),
        "invalid copy48 GPR schema",
    )
    for name, value in registers.items():
        _word(value, "copy48 " + name)
    _require(type(xmm) is dict and set(xmm) == set(XMM), "invalid copy48 XMM schema")
    _require(
        all(type(value) is int and 0 <= value < 2**128 for value in xmm.values()),
        "invalid copy48 XMM word",
    )
    _word(entry_flags, "copy48 entry flags")
    _require(entry_flags & 0x400 == 0, "copy48 entry DF differs")
    _require(type(pages) is dict and bool(pages), "invalid copy48 pages schema")
    for page, data in pages.items():
        _word(page, "copy48 page address")
        _require(
            page % 4096 == 0
            and page + 4096 <= 2**32
            and type(data) is bytes
            and len(data) == 4096,
            "invalid copy48 immutable page",
        )
    source_span = _span(source, 48, "copy48 source")
    destination_span = _span(destination, 48, "copy48 destination")
    entry = registers["esp"]
    _require(entry >= 8, "copy48 stack underflows")
    frame = _span(entry - 8, 24, "copy48 frame")
    _word(return_address, "copy48 return address")
    _require(return_address > 0, "copy48 zero return address")
    _require(destination > source + 48, "copy48 forward disjoint domain differs")
    protected = (
        source_span,
        destination_span,
        frame,
        (FEATURE_PAGE, FEATURE_PAGE + 4096),
    )
    code = tuple((BASE + start, BASE + end) for start, end in RANGES)
    _require(
        all(
            _disjoint(left, right)
            for i, left in enumerate(protected)
            for right in protected[i + 1 :]
        ),
        "copy48 live extents overlap",
    )
    _require(
        all(_disjoint(span, body) for span in protected for body in code),
        "copy48 extent overlaps code",
    )
    code_pages = {BASE + (start & ~0xFFF) for start, end in RANGES}
    _require(not code_pages.intersection(pages), "copy48 data page overlaps code page")
    _require(
        return_address & ~0xFFF not in pages
        and all(not start <= return_address < end for start, end in code),
        "copy48 return address overlaps storage or selected code",
    )

    def read(address, size):
        _require(
            all((address + i) & ~0xFFF in pages for i in range(size)),
            "copy48 extent is unmapped",
        )
        return bytes(
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] for i in range(size)
        )

    for start, end in protected:
        read(start, end - start)
    _require(
        int.from_bytes(read(FEATURE, 4), "little") == FEATURE_WORD,
        "copy48 feature premise differs",
    )
    for offset, wanted in (
        (0, return_address),
        (4, destination),
        (8, source),
        (12, 48),
    ):
        _require(
            int.from_bytes(read(entry + offset, 4), "little") == wanted,
            "copy48 installed caller words differ",
        )
    snapshot = read(source, 48)
    result = {page: bytearray(data) for page, data in pages.items()}
    events = []

    def emit(access, address, width, value):
        events.append(dict(access=access, address=address, width=width, value=value))
        if access == "write":
            for i, byte in enumerate(value.to_bytes(width, "little")):
                result[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte

    emit("write", entry - 4, 4, registers["edi"])
    emit("write", entry - 8, 4, registers["esi"])
    emit("read", entry + 8, 4, source)
    emit("read", entry + 12, 4, 48)
    emit("read", entry + 4, 4, destination)
    emit("read", FEATURE, 4, FEATURE_WORD)
    for access, base in (("read", source), ("write", destination)):
        for offset in (0, 8, 16, 24):
            emit(
                access,
                base + offset,
                8,
                int.from_bytes(snapshot[offset : offset + 8], "little"),
            )
    for offset in (32, 36, 40, 44):
        value = int.from_bytes(snapshot[offset : offset + 4], "little")
        emit("read", source + offset, 4, value)
        emit("write", destination + offset, 4, value)
    emit("read", entry + 4, 4, destination)
    emit("read", entry - 8, 4, registers["esi"])
    emit("read", entry - 4, 4, registers["edi"])
    emit("read", entry, 4, return_address)
    return dict(
        pages={page: bytes(data) for page, data in result.items()},
        source_snapshot=snapshot,
        registers=dict(
            registers,
            eax=destination,
            ecx=0,
            edx=int.from_bytes(snapshot[44:48], "little"),
            esp=entry + 4,
        ),
        xmm=dict(
            xmm,
            xmm0=int.from_bytes(snapshot[:16], "little"),
            xmm1=int.from_bytes(snapshot[16:32], "little"),
        ),
        flags=0x44,
        flag_mask=0x8C5,
        df=0,
        endpoint=return_address,
        trace_rvas=[f"0x{pc:08x}" for pc in TRACE],
        events=events,
    )
