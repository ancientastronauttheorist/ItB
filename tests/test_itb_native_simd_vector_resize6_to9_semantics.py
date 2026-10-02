"""Independent actual-page ordinary resize6-to9 adapter laws."""

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "src/observatory").is_dir()
)
sys.path.insert(0, str(ROOT))
from src.observatory import native_simd_vector_resize6_to9_semantics as m
from src.observatory import native_simd_vector_resize6_to9_conformance as c
from tests.test_itb_native_installed_simd_copy48_conformance import TRACE as COPY_TRACE

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")

XMM = tuple("xmm" + str(i) for i in range(8))

H, HEAP = 0x0FFFFFD0, 0x12345678
HEAP_GLOBAL, ALLOC_IAT, FREE_IAT = 0x008B7634, 0x007D6220, 0x007D621C

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

FREE_TRACE = (
    0x7800,
    0x7801,
    0x7803,
    0x7806,
    0x7809,
    0x780B,
    0x780E,
    0x7810,
    0x7816,
    0x781A,
    0x7820,
    0x784D,
    0x7850,
    0x7851,
    0x35785D,
    0x36FB17,
    0x389156,
    0x389158,
    0x389159,
    0x38915B,
    0x38915F,
    0x389161,
    0x389164,
    0x389166,
    0x38916C,
    0x389172,
    0x389174,
    0x38918E,
    0x38918F,
    0x7856,
    0x7859,
    0x785A,
)

TRACE = (
    (
        0x2EB680,
        0x2EB681,
        0x2EB683,
        0x2EB684,
        0x2EB687,
        0x2EB688,
        0x2EB689,
        0x2EB68A,
        0x2EB68B,
        0x2EB68D,
        0x2EB690,
    )
    + ALLOCATION_TRACE
    + (0x2EB695, 0x2EB697, 0x2EB699, 0x2EB69C, 0x2EB69E, 0x2EB69F, 0x2EB6A0, 0x2EB6A1)
    + COPY_TRACE
    + (
        0x2EB6A6,
        0x2EB6A8,
        0x2EB6AB,
        0x2EB6AE,
        0x2EB6B0,
        0x2EB6B3,
        0x2EB6B5,
        0x2EB6B7,
        0x2EB6BA,
        0x2EB6BC,
        0x2EB6BE,
        0x2EB6C1,
        0x2EB6C2,
        0x2EB6C3,
    )
    + FREE_TRACE
    + (
        0x2EB6C8,
        0x2EB6CB,
        0x2EB6CE,
        0x2EB6D1,
        0x2EB6D4,
        0x2EB6D7,
        0x2EB6DA,
        0x2EB6DC,
        0x2EB6DD,
        0x2EB6DE,
        0x2EB6DF,
        0x2EB6E1,
        0x2EB6E2,
    )
)


def blob(pages, address, size):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def add_flags(left, right):
    total = left + right
    result = total & 0xFFFFFFFF
    return (
        int(total > 0xFFFFFFFF)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | (int((left & 15) + (right & 15) > 15) << 4)
        | (int(result == 0) << 6)
        | ((result >> 31) << 7)
        | (int(bool((~(left ^ right) & (left ^ result)) & 0x80000000)) << 11)
    )


def sub_flags(left, right):
    result = (left - right) & 0xFFFFFFFF
    return (
        int(left < right)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | (int(bool((left ^ right ^ result) & 16)) << 4)
        | (int(result == 0) << 6)
        | (result >> 31 << 7)
        | (int(bool(((left ^ right) & (left ^ result)) & 0x80000000)) << 11)
    )


def independent(
    *,
    pages,
    registers,
    xmm,
    source,
    destination,
    object_address,
    return_address,
    entry_flags,
):
    """Predict all writes/events from an already installed, complete fixture."""
    original, output = copy.deepcopy(pages), copy.deepcopy(pages)
    r, o, d = registers["esp"], source, destination
    H = object_address
    snapshot = blob(original, o, 48)
    events, boundaries = [], {}

    def event(access, address, value, width=4):
        row = dict(access=access, address=address, width=width, value=value)
        events.append(row)
        if access == "write":
            for i, byte in enumerate(value.to_bytes(width, "little")):
                page = (address + i) & ~4095
                data = bytearray(output[page])
                data[(address + i) & 4095] = byte
                output[page] = bytes(data)
        else:
            assert int.from_bytes(blob(output, address, width), "little") == value

    w = lambda address, value: event("write", address, value)
    rd = lambda address, value: event("read", address, value)

    def boundary(name, regs, endpoint, flags, mask, xmms):
        boundaries[name] = dict(
            registers=copy.deepcopy(regs),
            xmm=copy.deepcopy(xmms),
            pages=copy.deepcopy(output),
            events=copy.deepcopy(events),
            endpoint=endpoint,
            flags=flags,
            flag_mask=mask,
            df=0,
        )

    assert [int.from_bytes(blob(original, H + i, 4), "little") for i in (0, 4, 8)] == [
        o,
        o + 48,
        o + 48,
    ]
    assert [int.from_bytes(blob(original, r + i, 4), "little") for i in (0, 4)] == [
        return_address,
        9,
    ]
    for address, value in ((r - 4, registers["ebp"]), (r - 8, H)):
        w(address, value)
    rd(r + 4, 9)
    for address, value in (
        (r - 12, registers["ebx"]),
        (r - 16, registers["esi"]),
        (r - 20, registers["edi"]),
        (r - 24, 9),
        (r - 8, 9),
        (r - 28, 0x006EB695),
    ):
        w(address, value)
    allocated_entry = dict(registers, eax=9, esi=H, ebp=r - 4, esp=r - 28)
    boundary(
        "allocation_entry", allocated_entry, 0x0048A920, entry_flags, 0xFFFFFFFF, xmm
    )
    a = r - 28
    # Ordinary allocation: requested count9, bytes72, no pointer metadata.
    w(a - 4, r - 4)
    rd(a + 4, 9)
    for address, value in ((a - 8, 72), (a - 12, 0x0048A968), (a - 16, a - 4)):
        w(address, value)
    rd(a - 8, 72)
    for address, value in ((a - 20, 72), (a - 24, 0x00757507), (a - 28, a - 16)):
        w(address, value)
    rd(a - 28, a - 16)
    w(a - 28, a - 16)
    w(a - 32, H)
    rd(a - 20, 72)
    w(a - 36, 72)
    w(a - 40, 0)
    rd(HEAP_GLOBAL, HEAP)
    w(a - 44, HEAP)
    alloc_target = int.from_bytes(blob(output, ALLOC_IAT, 4), "little")
    rd(ALLOC_IAT, alloc_target)
    w(a - 48, 0x00789463)
    allocation_request = dict(
        entry_esp=r - 76, words=[0x00789463, HEAP, 0, 72], target=alloc_target
    )
    for address, value in (
        (a - 32, H),
        (a - 28, a - 16),
        (a - 24, 0x00757507),
        (a - 20, 72),
        (a - 16, a - 4),
        (a - 12, 0x0048A968),
        (a - 4, r - 4),
        (a, 0x006EB695),
    ):
        rd(address, value)
    allocated_return = dict(allocated_entry, eax=d, ecx=d, edx=0xB0000001, esp=r - 20)
    boundary(
        "allocation_return",
        allocated_return,
        0x006EB695,
        add_flags(a - 8, 4),
        0x8D5,
        xmm,
    )
    rd(H, o)
    rd(H + 4, o + 48)
    for address, value in (
        (r - 24, 48),
        (r - 28, o),
        (r - 32, d),
        (r - 36, 0x006EB6A6),
    ):
        w(address, value)
    copy_entry = dict(allocated_return, eax=d, ecx=48, edx=o, edi=d, esp=r - 36)
    # SUB gives48; OF also sets when source+48 crosses the signed boundary.
    boundary("copy_entry", copy_entry, 0x0076E580, sub_flags(o + 48, o), 0x8D5, xmm)
    c = r - 36
    w(c - 4, d)
    w(c - 8, H)
    rd(c + 8, o)
    rd(c + 12, 48)
    rd(c + 4, d)
    rd(0x00893F30, 0x93939393)
    for access, address in (("read", o), ("write", d)):
        for offset in (0, 8, 16, 24):
            event(
                access,
                address + offset,
                int.from_bytes(snapshot[offset : offset + 8], "little"),
                8,
            )
    for offset in (32, 36, 40, 44):
        value = int.from_bytes(snapshot[offset : offset + 4], "little")
        rd(o + offset, value)
        w(d + offset, value)
    for address, value in ((c + 4, d), (c - 8, H), (c - 4, d), (c, 0x006EB6A6)):
        rd(address, value)
    copied_xmm = dict(
        xmm,
        xmm0=int.from_bytes(snapshot[:16], "little"),
        xmm1=int.from_bytes(snapshot[16:32], "little"),
    )
    copied_return = dict(
        copy_entry,
        eax=d,
        ecx=0,
        edx=int.from_bytes(snapshot[44:48], "little"),
        esp=r - 32,
    )
    boundary("copy_return", copied_return, 0x006EB6A6, 0x44, 0x8C5, copied_xmm)
    rd(H, o)
    rd(H + 4, o + 48)
    rd(H + 8, o + 48)
    for address, value in ((r - 24, 8), (r - 28, 6), (r - 32, o), (r - 36, 0x006EB6C8)):
        w(address, value)
    free_entry = dict(copied_return, eax=6, ebx=6, ecx=o, esp=r - 36)
    # SAR count3 leaves AF/OF unclaimed; only CF/PF/ZF/SF are defined.
    boundary("free_entry", free_entry, 0x00407800, 4, 0xC5, copied_xmm)
    f = r - 36
    # Successful ordinary guard: two stride reads, no raw-pointer metadata.
    w(f - 4, r - 4)
    rd(f + 8, 6)
    rd(f + 12, 8)
    rd(f + 12, 8)
    rd(f + 4, o)
    w(f - 8, o)
    w(f - 12, 0x00407856)
    inner = f - 12
    w(inner - 4, f - 4)
    rd(inner + 4, o)
    rd(inner + 4, o)
    w(inner - 8, o)
    w(inner - 12, 0)
    rd(HEAP_GLOBAL, HEAP)
    w(inner - 16, HEAP)
    free_target = int.from_bytes(blob(output, FREE_IAT, 4), "little")
    rd(FREE_IAT, free_target)
    w(inner - 20, 0x00789172)
    free_request = dict(
        entry_esp=r - 68, words=[0x00789172, HEAP, 0, o], target=free_target
    )
    for address, value in (
        (inner - 4, f - 4),
        (inner, 0x00407856),
        (f - 4, r - 4),
        (f, 0x006EB6C8),
    ):
        rd(address, value)
    freed_return = dict(free_entry, eax=1, ecx=0xA0000001, edx=0xB0000001, esp=f + 4)
    boundary(
        "free_return", freed_return, 0x006EB6C8, add_flags(f - 8, 4), 0x8D5, copied_xmm
    )
    rd(r - 8, 9)
    for address, value in ((H + 8, d + 72), (H + 4, d + 48), (H, d)):
        w(address, value)
    for address, value in (
        (r - 20, registers["edi"]),
        (r - 16, registers["esi"]),
        (r - 12, registers["ebx"]),
        (r - 4, registers["ebp"]),
        (r, return_address),
    ):
        rd(address, value)
    assert len(events) == 104
    return dict(
        pages=output,
        events=events,
        source_snapshot=snapshot,
        registers=dict(
            registers, eax=d + 48, ecx=0xA0000001, edx=0xB0000001, esp=r + 8
        ),
        xmm=copied_xmm,
        flags=add_flags(r - 32, 12),
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
        boundaries=boundaries,
        allocation_request=allocation_request,
        free_request=free_request,
        stack_extent=[r - 76, r + 8],
    )


def canonical_hash(value):
    return hashlib.sha256(
        (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode()
    ).hexdigest()


def page_hashes(pages):
    return {
        f"0x{page:08x}": hashlib.sha256(data).hexdigest()
        for page, data in sorted(pages.items())
    }


def install(pages, address, payload):
    for i, byte in enumerate(payload):
        page = (address + i) & ~4095
        if page not in pages:
            pages[page] = bytes(
                ((j * 19 + (page >> 12) + (j >> 3)) ^ 0xAD) & 255 for j in range(4096)
            )
        data = bytearray(pages[page])
        data[(address + i) & 4095] = byte
        pages[page] = bytes(data)


def actual_input(
    alignment=7,
    profile=2,
    *,
    header=0x0FFFFFD0,
    entry=None,
    source=None,
    destination=None,
    return_address=0x006EB66E,
    entry_flags=0x2,
):
    base = c._fixture(dict(alignment=alignment, profile=profile))
    pages = copy.deepcopy(base["pages"])
    old = 0x06002800 + alignment
    source = old if source is None else source
    destination = 0x06004800 + alignment if destination is None else destination
    entry = 0x30001000 + alignment if entry is None else entry
    payload = blob(pages, old, 48)
    install(pages, source, payload)
    # Ensure every admitted capacity byte is mapped, preserving mapped padding.
    for address in range(destination, destination + 72):
        if address & ~4095 not in pages:
            install(pages, address, b"\xa5")
    for offset, value in ((0, source), (4, source + 48), (8, source + 48)):
        install(pages, header + offset, value.to_bytes(4, "little"))
    for offset, value in ((0, return_address), (4, 9)):
        install(pages, entry + offset, value.to_bytes(4, "little"))
    return dict(
        pages=pages,
        registers=dict(base["registers"], ecx=header, esp=entry),
        xmm=copy.deepcopy(base["xmm"]),
        source=source,
        destination=destination,
        object_address=header,
        return_address=return_address,
        entry_flags=entry_flags,
    )


def check_result(input_packet, result, wanted):
    assert set(result) == {
        "geometry",
        "registers",
        "xmm",
        "flags",
        "flag_mask",
        "df",
        "events",
        "pages",
        "endpoint",
        "allocation_entry",
        "allocation_packet",
        "copy_entry",
        "copy_packet",
        "free_entry",
        "free_packet",
        "allocation_request",
        "free_request",
        "trace_rvas",
    }
    for key in (
        "registers",
        "xmm",
        "flags",
        "flag_mask",
        "df",
        "events",
        "pages",
        "endpoint",
    ):
        assert result[key] == wanted[key], key
    o, d = input_packet["source"], input_packet["destination"]
    assert result["geometry"] == dict(
        old_begin=o,
        old_end=o + 48,
        old_capacity=o + 48,
        new_begin=d,
        new_end=d + 48,
        new_capacity=d + 72,
        copy_bytes=48,
        request=72,
        old_size=6,
        requested=9,
    )
    for name in ("allocation_entry", "copy_entry", "free_entry"):
        assert result[name] == wanted["boundaries"][name], name
    a = wanted["boundaries"]["allocation_return"]
    assert result["allocation_packet"] == dict(
        relation=dict(result=d, request=72, metadata=None),
        registers=a["registers"],
        flags=a["flags"],
        flag_mask=0x8D5,
        stack=blob(a["pages"], 0x30000000, 8192),
        payload=input_packet["pages"][d & ~4095],
        events=wanted["events"][9:36],
    )
    cp = wanted["boundaries"]["copy_return"]
    assert result["copy_packet"] == dict(
        pages=cp["pages"],
        source_snapshot=wanted["source_snapshot"],
        registers=cp["registers"],
        xmm=cp["xmm"],
        flags=0x44,
        flag_mask=0x8C5,
        df=0,
        endpoint=0x006EB6A6,
        trace_rvas=[f"0x{pc:08x}" for pc in COPY_TRACE],
        events=wanted["events"][42:68],
    )
    f = wanted["boundaries"]["free_return"]
    assert result["free_packet"] == dict(
        registers=f["registers"],
        flags=f["flags"],
        flag_mask=0x8D5,
        events=wanted["events"][75:95],
        stack=blob(f["pages"], 0x30000000, 8192),
        error=input_packet["pages"][0x06000000],
        stop=0x006EB6C8,
        protocol=dict(
            returned=True, result=1, next_kind=None, error_cell=None, last_error=None
        ),
    )
    assert result["allocation_request"] == dict(
        continuation=0x00789463, handle=HEAP, flags=0, bytes=72
    )
    assert result["free_request"] == dict(
        continuation=0x00789172, handle=HEAP, flags=0, pointer=o
    )
    assert result["trace_rvas"] == [f"0x{pc:08x}" for pc in TRACE]
    assert len(result["events"]) == 104
    assert blob(result["pages"], o, 48) == wanted["source_snapshot"]
    assert blob(result["pages"], d + 48, 24) == blob(input_packet["pages"], d + 48, 24)
    h = input_packet["object_address"]
    assert [
        row
        for row in result["events"]
        if row["access"] == "write" and h <= row["address"] < h + 12
    ] == [
        dict(access="write", address=h + 8, width=4, value=d + 72),
        dict(access="write", address=h + 4, width=4, value=d + 48),
        dict(access="write", address=h, width=4, value=d),
    ]


@pytest.mark.parametrize("alignment", range(16))
def test_all_profiles_actual_growth_continuation_independent_complete_law(alignment):
    for profile in range(3):
        packet = actual_input(
            alignment,
            profile,
            header=0x10000104,
            entry=0x30001000 + alignment - 20,
            entry_flags=0x2,
        )
        before = copy.deepcopy(packet)
        wanted = independent(**packet)
        result = m.apply(**packet)
        check_result(packet, result, wanted)
        assert (
            result["allocation_entry"]["flags"] == 0x2
            and result["allocation_entry"]["flag_mask"] == 0xFFFFFFFF
        )
        assert result["endpoint"] == 0x006EB66E
        assert packet == before
        result["registers"]["eax"] ^= 1
        result["xmm"]["xmm7"] ^= 1
        result["events"][0]["value"] ^= 1
        assert packet == before


@pytest.mark.parametrize("flags", (0x2, 0x6, 0x202, 0x246, 0x256, 0xAD7))
def test_actual_entry_flags_are_preserved_as_premises_then_independently_replaced(
    flags,
):
    packet = actual_input(header=0x10000104, entry_flags=flags)
    wanted = independent(**packet)
    result = m.apply(**packet)
    check_result(packet, result, wanted)
    assert result["allocation_entry"]["flags"] == flags


@pytest.mark.parametrize(
    "geometry",
    (
        dict(
            header=0x10000FFA,
            source=0x06002FF0,
            destination=0x06004FE7,
            entry=0x30001003,
        ),
        dict(header=0x10000104, entry=0x30000000 + 76),
        dict(header=0x10000104, entry=0x30002000 - 8),
        dict(header=0x10000104, destination=0xFFFFFFB7),
        dict(header=0x10000104, source=0x7FFFFFF0, destination=0x80002000),
    ),
)
def test_admitted_cross_page_extents_stack_boundaries_and_strict_uint32_end(geometry):
    packet = actual_input(**geometry)
    before = copy.deepcopy(packet)
    result = m.apply(**packet)
    check_result(packet, result, independent(**packet))
    if packet["source"] == 0x7FFFFFF0:
        assert result["copy_entry"]["flags"] == 0x804
    assert packet == before


def test_no_constructor_or_finite_fixture_transport(monkeypatch):
    packet = actual_input(header=0x10000104)

    def forbidden(*args, **kwargs):
        raise AssertionError("fixture creation attempted")

    monkeypatch.setattr(c, "_fixture", forbidden)
    monkeypatch.setattr(c.installed_copy, "_fixture", forbidden)
    check_result(packet, m.apply(**packet), independent(**packet))


@pytest.mark.parametrize(
    "kind",
    (
        "gpr_bool",
        "gpr_missing",
        "gpr_extra",
        "xmm_bool",
        "xmm_overflow",
        "xmm_missing",
        "pages_list",
        "page_bool",
        "page_mutable",
        "page_short",
        "missing_stack",
        "missing_error",
        "missing_feature",
        "source_bool",
        "source_zero",
        "source_wrap",
        "destination_wrap",
        "header_wrap",
        "destination_overlap",
        "destination_adjacent",
        "header_source",
        "header_destination",
        "source_stack",
        "header_global",
        "destination_error",
        "source_feature",
        "header_iat",
        "stack_low",
        "stack_high",
        "ecx_header",
        "return_zero",
        "return_bool",
        "return_data",
        "return_import",
        "return_selected_code",
        "flags_bool",
        "df",
        "caller_return",
        "caller_request",
        "header_end",
        "header_capacity",
        "feature",
        "heap",
        "iat",
        "code_page",
        "import_page",
    ),
)
def test_typed_bounds_aliases_frames_globals_and_installed_premises_reject(kind):
    packet = actual_input()
    if kind == "gpr_bool":
        packet["registers"]["eax"] = False
    elif kind == "gpr_missing":
        packet["registers"].pop("eax")
    elif kind == "gpr_extra":
        packet["registers"]["unused"] = 0
    elif kind == "xmm_bool":
        packet["xmm"]["xmm0"] = False
    elif kind == "xmm_overflow":
        packet["xmm"]["xmm7"] = 2**128
    elif kind == "xmm_missing":
        packet["xmm"].pop("xmm0")
    elif kind == "pages_list":
        packet["pages"] = list(packet["pages"].items())
    elif kind == "page_bool":
        packet["pages"][False] = bytes(4096)
    elif kind == "page_mutable":
        packet["pages"][0x06004000] = bytearray(packet["pages"][0x06004000])
    elif kind == "page_short":
        packet["pages"][0x06004000] = packet["pages"][0x06004000][:-1]
    elif kind.startswith("missing_"):
        packet["pages"].pop(
            dict(
                missing_stack=0x30000000,
                missing_error=0x06000000,
                missing_feature=0x00893000,
            )[kind]
        )
    elif kind == "source_bool":
        packet["source"] = True
    elif kind == "source_zero":
        packet["source"] = 0
    elif kind == "source_wrap":
        packet["source"] = 0xFFFFFFF0
    elif kind == "destination_wrap":
        packet["destination"] = 0xFFFFFFB8
    elif kind == "header_wrap":
        packet["object_address"] = 0xFFFFFFF8
        packet["registers"]["ecx"] = 0xFFFFFFF8
    elif kind in ("destination_overlap", "destination_adjacent"):
        packet["destination"] = packet["source"] + (
            32 if kind == "destination_overlap" else 48
        )
    elif kind in ("header_source", "header_destination", "header_global", "header_iat"):
        h = dict(
            header_source=packet["source"],
            header_destination=packet["destination"],
            header_global=HEAP_GLOBAL,
            header_iat=ALLOC_IAT,
        )[kind]
        packet["object_address"] = h
        packet["registers"]["ecx"] = h
    elif kind == "source_stack":
        packet["source"] = 0x30000100
        packet["destination"] = 0x30000200
    elif kind == "destination_error":
        packet["source"] = 0x05002800
        packet["destination"] = 0x06000080
    elif kind == "source_feature":
        packet["source"] = 0x00893080
    elif kind == "stack_low":
        packet["registers"]["esp"] = 0x30000000 + 75
    elif kind == "stack_high":
        packet["registers"]["esp"] = 0x30002000 - 7
    elif kind == "ecx_header":
        packet["registers"]["ecx"] ^= 1
    elif kind == "return_zero":
        packet["return_address"] = 0
    elif kind == "return_bool":
        packet["return_address"] = True
    elif kind == "return_data":
        packet["return_address"] = packet["source"]
    elif kind == "return_import":
        packet["return_address"] = 0x05000000
    elif kind == "return_selected_code":
        packet["return_address"] = 0x006EB680
    elif kind == "flags_bool":
        packet["entry_flags"] = False
    elif kind == "df":
        packet["entry_flags"] |= 0x400
    elif kind in ("code_page", "import_page"):
        packet["pages"][0x006EB000 if kind == "code_page" else 0x05000000] = bytes(4096)
    else:
        at = dict(
            caller_return=packet["registers"]["esp"],
            caller_request=packet["registers"]["esp"] + 4,
            header_end=packet["object_address"] + 4,
            header_capacity=packet["object_address"] + 8,
            feature=0x00893F30,
            heap=HEAP_GLOBAL,
            iat=ALLOC_IAT,
        )[kind]
        install(packet["pages"], at, bytes([blob(packet["pages"], at, 1)[0] ^ 1]))
    before = copy.deepcopy(packet)
    with pytest.raises(m.Resize6To9Error):
        m.apply(**packet)
    assert packet == before


@pytest.mark.parametrize(
    "kind",
    (
        "allocation_bool",
        "allocation_extra",
        "allocation_spare",
        "copy_edx32",
        "copy_df_bool",
        "copy_spare",
        "copy_ancestor",
        "free_returned_int",
        "free_result_bool",
        "free_error",
    ),
)
def test_full_child_packets_reject_bool_aliases_and_coordinated_page_corruption(
    monkeypatch, kind
):
    packet = actual_input(header=0x10000104)
    before = copy.deepcopy(packet)
    role = kind.split("_", 1)[0]
    name = "_" + role + "_packet_law"
    original = getattr(c, name)

    def corrupted(*args, **kwargs):
        result = original(*args, **kwargs)
        if kind == "allocation_bool":
            result["relation"]["metadata"] = False
        elif kind == "allocation_extra":
            result["unused"] = 0
        elif kind == "allocation_spare":
            result["payload"] = (
                bytes([result["payload"][0] ^ 1]) + result["payload"][1:]
            )
            result["events"].append(
                dict(
                    access="write", address=packet["destination"] + 48, width=4, value=0
                )
            )
        elif kind == "copy_edx32":
            result["registers"]["edx"] = 0
        elif kind == "copy_df_bool":
            result["df"] = False
        elif kind in ("copy_spare", "copy_ancestor"):
            at = (
                packet["destination"] + 48
                if kind == "copy_spare"
                else packet["registers"]["esp"] + 8
            )
            value = int.from_bytes(blob(result["pages"], at, 4), "little") ^ 1
            install(result["pages"], at, value.to_bytes(4, "little"))
            result["events"].append(
                dict(access="write", address=at, width=4, value=value)
            )
        elif kind == "free_returned_int":
            result["protocol"]["returned"] = 1
        elif kind == "free_result_bool":
            result["protocol"]["result"] = True
        else:
            result["error"] = bytes([result["error"][0] ^ 1]) + result["error"][1:]
        return result

    monkeypatch.setattr(c, name, corrupted)
    with pytest.raises(m.Resize6To9Error, match=role + " primitive"):
        m.apply(**packet)
    assert packet == before


@pytest.mark.parametrize("kind", ("extra", "missing"))
def test_apply_keyword_schema_is_closed(kind):
    packet = actual_input()
    if kind == "extra":
        packet["unused"] = 0
    else:
        packet.pop("entry_flags")
    with pytest.raises(TypeError):
        m.apply(**packet)


def test_output_packets_detach_from_actual_installed_inputs():
    packet = actual_input(header=0x10000104, entry_flags=0x256)
    result = m.apply(**packet)
    before = copy.deepcopy(result)
    packet["registers"]["ebx"] ^= 1
    packet["xmm"]["xmm7"] ^= 1
    packet["pages"].clear()
    assert result == before


def test_prior_native_evidence_pins_are_preserved_and_actual_adapter_is_distinct():
    assert m.SOURCE_PINS["resize6_to9"] == (
        c.ANALYSIS_KIND,
        "009f36e1b254058ec21f7af157f6e86ebfa18039abe24fce1690f9df97bc2949",
    )
    for key, pin in c.SOURCE_PINS.items():
        assert m.SOURCE_PINS[key] == pin
    assert m.ANALYSIS_KIND == "pe_native_simd_vector_resize6_to9_semantics"


@pytest.mark.parametrize(
    "bit", tuple(bit for bit in range(32) if not (0xAD7 & (1 << bit)))
)
def test_actual_flags_reject_every_nonordinary_reserved_or_control_bit(bit):
    # Status0x8D5, IF0x200 and fixed bit1 are the entire admitted raw domain.
    # This covers TF, DF, IOPL, NT, RF, VM, AC, VIF, VIP, ID and reserved bits.
    packet = actual_input(header=0x10000104, entry_flags=0x2 | (1 << bit))
    before = copy.deepcopy(packet)
    with pytest.raises(m.Resize6To9Error):
        m.apply(**packet)
    assert packet == before


@pytest.mark.parametrize("flags", (0, 4, 0x200, 0x8D5))
def test_actual_full_flags_require_fixed_bit1_and_reject_abstract_status_words(flags):
    packet = actual_input(header=0x10000104, entry_flags=flags)
    before = copy.deepcopy(packet)
    with pytest.raises(m.Resize6To9Error):
        m.apply(**packet)
    assert packet == before


def test_former_arbitrary_df_clear_uint32_flags_are_outside_ordinary_domain():
    packet = actual_input(header=0x10000104, entry_flags=0xFFFFFBFF)
    before = copy.deepcopy(packet)
    with pytest.raises(m.Resize6To9Error):
        m.apply(**packet)
    assert packet == before
