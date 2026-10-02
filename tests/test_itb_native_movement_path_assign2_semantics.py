"""Independent actual-page empty-destination count-two path assignment law.

The expected packet generalizes the previously handwritten finite source oracle.
Production apply supplies only actuals, never fixture or expected calculations.
"""

from __future__ import annotations
import ast
import copy
import inspect
from collections import UserDict
import pytest
from src.observatory import native_movement_path_assign2_semantics as c
from tests import test_itb_native_movement_path_scalar_clone2_semantics as p

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
FLAG_BITS = (0, 2, 4, 6, 7, 9, 11)
FLAGS = tuple(
    2 | sum(1 << b for i, b in enumerate(FLAG_BITS) if selector >> i & 1)
    for selector in range(128)
)
KEYS = {
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
BOUNDARY_KEYS = {
    "registers",
    "xmm",
    "pages",
    "events",
    "endpoint",
    "flags",
    "flag_mask",
    "df",
}
NAMES = (
    "parent_entry",
    "reserve_entry",
    "allocation_entry",
    "allocation_return",
    "reserve_return",
    "scalar_entry",
    "scalar_return",
)
RANGES = (
    (0x48A920, 0x48A97B),
    (0x48ABA0, 0x48ABCB),
    (0x4C5BB0, 0x4C5C92),
    (0x49AC40, 0x49AC97),
    (0x7574DB, 0x75750E),
    (0x779F52, 0x779F5D),
    (0x78942B, 0x789479),
)


def inputs(
    *,
    frame=0x30001003,
    source=0x10000FF8,
    destination=0x06001007,
    source_header=0x10000203,
    header=0x10000308,
    profile=0,
    flags=0x246,
    return_address=0x006573A7,
    capacity=0xFFFFFFFF,
):
    stack_base = min((frame - 96) & ~4095, 0xFFFFE000)
    spans = (
        (source, source + 16),
        (source_header, source_header + 12),
        (header, header + 12),
        (destination, destination + 16),
        (frame - 96, frame + 8),
    )
    mapped = {
        b
        for start, end in spans
        for b in range(start & ~4095, ((end - 1) & ~4095) + 1, 4096)
    }
    mapped.update(
        (
            stack_base,
            stack_base + 4096,
            0x06000000,
            0x06001000,
            0x06002000,
            0x06003000,
            0x008B7000,
            0x007D6000,
            0x00893000,
            0x12340000,
        )
    )
    pages = {
        b: bytes((i * 53 + j * 29 + profile * 71) & 255 for j in range(4096))
        for i, b in enumerate(sorted(mapped))
    }
    for at, value in (
        (frame, return_address),
        (frame + 4, source_header),
        (source_header, source),
        (source_header + 4, (source + 16) & 0xFFFFFFFF),
        (source_header + 8, capacity),
        (0x008B7634, 0x12345678),
        (0x007D6220, 0x05000000),
    ):
        p.store(pages, at, value)
    for i, value in enumerate((0xD15C0016, 0xFFFFFFFF, 0x80000000, 0x8765DD16)):
        p.store(pages, source + i * 4, value ^ ((profile * 0x7654321) & 0xFFFFFFFF))
    for offset in (0, 4, 8):
        p.store(pages, header + offset, 0)
    registers = {
        r: (0x13579BDF + i * 0x1234567 + profile * 0x4321) & 0xFFFFFFFF
        for i, r in enumerate(GPR)
    }
    registers.update(ecx=header, esp=frame)
    xmm = {
        r: int.from_bytes(
            bytes((i * 31 + j * 19 + profile * 79) & 255 for j in range(16)), "little"
        )
        for i, r in enumerate(XMM)
    }
    return dict(
        pages=pages,
        registers=registers,
        xmm=xmm,
        return_address=return_address,
        entry_flags=flags,
        allocation_result=destination,
    )


OWNER_PREFIX = tuple(int(w, 16) for w in """
c5bb0 c5bb1 c5bb3 c5bb4 c5bb5 c5bb8 c5bb9 c5bba c5bbc c5bbe c5bc4 c5bc6
c5bc9 c5bcb c5bdd c5be0 c5be2 c5be4 c5be6 c5be8 c5beb c5bee c5bf1 c5bf3 c5bf6
c5c20 c5c23 c5c25 c5c28 c5c2a c5c4c c5c4e c5c5c c5c5f c5c61 c5c63 c5c66 c5c67
""".split())
OWNER_MIDDLE = tuple(
    int(w, 16) for w in "c5c6c c5c6e c5c70 c5c71 c5c74 c5c75 c5c77 c5c79 c5c7c".split()
)
OWNER_SUFFIX = tuple(
    int(w, 16) for w in "c5c81 c5c84 c5c87 c5c89 c5c8a c5c8b c5c8c c5c8e c5c8f".split()
)
RESERVE_BEFORE = tuple(
    int(w, 16)
    for w in "9ac40 9ac41 9ac43 9ac44 9ac46 9ac47 9ac4a 9ac50 9ac57 9ac5e 9ac60 9ac6a 9ac70 9ac72 9ac73".split()
)
ALLOCATION = tuple(int(w, 16) for w in """
8a920 8a921 8a923 8a926 8a928 8a932 8a937 8a939 8a93c 8a941 8a962 8a963
3574db 3574dc 3574de 3574ff 357502 379f52 379f54 379f55 379f57 379f58
38942b 38942d 38942e 389430 389431 389434 389437 389439 38943b 389454
389455 389457 38945d 389463 389465 389467 389476 389477 389478
357507 357508 35750a 35750c 35750d 8a968 8a96b 8a96d 8a96e
""".split())
RESERVE_AFTER = tuple(
    int(w, 16)
    for w in "9ac78 9ac7a 9ac7d 9ac7f 9ac82 9ac85 9ac87 9ac88 9ac89 9ac8a".split()
)
TRACE = (
    OWNER_PREFIX
    + RESERVE_BEFORE
    + ALLOCATION
    + RESERVE_AFTER
    + OWNER_MIDDLE
    + p.TRACE
    + OWNER_SUFFIX
)


def add_flags(left, right):
    result = (left + right) & 0xFFFFFFFF
    return (
        int(left + right > 0xFFFFFFFF)
        | (4 if (result & 255).bit_count() % 2 == 0 else 0)
        | (0x10 if (left ^ right ^ result) & 0x10 else 0)
        | (0x40 if result == 0 else 0)
        | (0x80 if result & 0x80000000 else 0)
        | (0x800 if (~(left ^ right) & (left ^ result)) & 0x80000000 else 0)
    )


def independent(fixture):
    frame = fixture["registers"]["esp"]
    h = fixture["registers"]["ecx"]
    j = int.from_bytes(p.read_bytes(fixture["pages"], frame + 4, 4), "little")
    o = int.from_bytes(p.read_bytes(fixture["pages"], j, 4), "little")
    d = fixture["allocation_result"]
    stack_base = min((frame - 96) & ~4095, 0xFFFFE000)
    pages = dict(fixture["pages"])
    initial = fixture["registers"]
    xmm = fixture["xmm"]
    regs = dict(initial)
    events = []

    def event(op, at, value):
        if op == "write":
            p.store(pages, at, value)
        else:
            assert int.from_bytes(p.read_bytes(pages, at, 4), "little") == value
        events.append(dict(access=op, address=at, width=4, value=value))

    def write(at, value):
        event("write", at, value)

    def read(at, value):
        event("read", at, value)

    def boundary(endpoint, flags, mask):
        return dict(
            registers=dict(regs),
            xmm=dict(xmm),
            pages=dict(pages),
            events=copy.deepcopy(events),
            endpoint=endpoint,
            flags=flags,
            flag_mask=mask,
            df=0,
        )

    boundaries = {
        "parent_entry": boundary(0x4C5BB0, fixture["entry_flags"], 0xFFFFFFFF)
    }
    for at, value in (
        (frame - 4, initial["ebp"]),
        (frame - 8, h),
        (frame - 12, initial["ebx"]),
    ):
        write(at, value)
    read(frame + 4, j)
    write(frame - 16, initial["esi"])
    write(frame - 20, initial["edi"])
    read(j, o)
    read(j + 4, o + 16)
    read(h + 4, 0)
    read(h, 0)
    write(frame - 8, 0)
    read(frame + 4, j)
    read(h + 8, 0)
    read(j + 4, o + 16)
    read(j, o)
    write(frame - 24, 2)
    write(frame - 28, 0x4C5C6C)
    regs.update(eax=2, ebx=j, ecx=h, edx=0, esi=2, edi=h, ebp=frame - 4, esp=frame - 28)
    boundaries["reserve_entry"] = boundary(0x49AC40, 0, 0xC5)
    for at, value in ((frame - 32, frame - 4), (frame - 36, 2), (frame - 40, h)):
        write(at, value)
    read(frame - 24, 2)
    for at in (h, h + 4, h + 8):
        write(at, 0)
    write(frame - 44, 2)
    write(frame - 48, 0x49AC78)
    regs.update(esi=h, edi=2, ebp=frame - 32, esp=frame - 48)
    boundaries["allocation_entry"] = boundary(0x48A920, 0x95, 0x8D5)
    allocation_initial = dict(regs)
    at = frame - 48
    start = len(events)
    write(at - 4, regs["ebp"])
    read(at + 4, 2)
    for offset, value in ((-8, 16), (-12, 0x48A968), (-16, at - 4)):
        write(at + offset, value)
    read(at - 8, 16)
    for offset, value in ((-20, 16), (-24, 0x757507), (-28, at - 16)):
        write(at + offset, value)
    read(at - 28, at - 16)
    write(at - 28, at - 16)
    write(at - 32, regs["esi"])
    read(at - 20, 16)
    write(at - 36, 16)
    write(at - 40, 0)
    read(0x8B7634, 0x12345678)
    write(at - 44, 0x12345678)
    read(0x7D6220, 0x5000000)
    write(at - 48, 0x789463)
    regs.update(eax=16, esi=16, ebp=at - 28, esp=at - 48)
    imported = boundary(0x5000000, 0, 0x8C5)
    imported.update(entry_esp=frame - 96, words=[0x789463, 0x12345678, 0, 16])
    for address, value in (
        (at - 32, allocation_initial["esi"]),
        (at - 28, at - 16),
        (at - 24, 0x757507),
        (at - 20, 16),
        (at - 16, at - 4),
        (at - 12, 0x48A968),
        (at - 4, allocation_initial["ebp"]),
        (at, 0x49AC78),
    ):
        read(address, value)
    regs = dict(allocation_initial, eax=d, ecx=d, edx=0xB0000001, esp=at + 8)
    allocflags = add_flags(at - 8, 4)
    allocation_packet = dict(
        relation=dict(result=d, request=16, metadata=None),
        registers=dict(regs),
        flags=allocflags,
        flag_mask=0x8D5,
        stack=p.read_bytes(pages, stack_base, 8192),
        payload=p.read_bytes(pages, 0x6000000, 16384),
        events=copy.deepcopy(events[start:]),
    )
    boundaries["allocation_return"] = boundary(0x49AC78, allocflags, 0x8D5)
    write(h, d)
    write(h + 4, d)
    read(h, d)
    write(h + 8, d + 16)
    for at, value in (
        (frame - 40, h),
        (frame - 36, 2),
        (frame - 32, frame - 4),
        (frame - 28, 0x4C5C6C),
    ):
        read(at, value)
    regs.update(
        eax=((d + 16) & 0xFFFFFF00) | 1, esi=2, edi=h, ebp=frame - 4, esp=frame - 20
    )
    boundaries["reserve_return"] = boundary(0x4C5C6C, allocflags, 0x8D5)
    write(frame - 24, d)
    read(frame + 4, j)
    write(frame - 28, j)
    write(frame - 32, d)
    read(h, d)
    write(frame - 36, d)
    read(j, o)
    read(j + 4, o + 16)
    write(frame - 40, 0x4C5C81)
    regs.update(ecx=o, edx=o + 16, esp=frame - 40)
    boundaries["scalar_entry"] = boundary(0x48ABA0, 0, 0x8C5)
    scalar_packet = p.independent(
        dict(
            pages=dict(pages),
            registers=dict(regs),
            xmm=dict(xmm),
            source=o,
            destination=d,
            return_address=0x4C5C81,
            entry_flags=0x202,
        )
    )
    pages = dict(scalar_packet["pages"])
    events.extend(copy.deepcopy(scalar_packet["events"]))
    regs = dict(scalar_packet["registers"])
    boundaries["scalar_return"] = boundary(0x4C5C81, 0x44, 0x8D5)
    write(h + 4, d + 16)
    for at, value in (
        (frame - 20, initial["edi"]),
        (frame - 16, initial["esi"]),
        (frame - 12, initial["ebx"]),
        (frame - 4, initial["ebp"]),
        (frame, fixture["return_address"]),
    ):
        read(at, value)
    regs.update(
        eax=h,
        ebx=initial["ebx"],
        esi=initial["esi"],
        edi=initial["edi"],
        ebp=initial["ebp"],
        esp=frame + 8,
    )
    return dict(
        geometry=dict(
            entry=frame, source=o, destination=d, source_header=j, destination_header=h
        ),
        registers=regs,
        xmm=dict(xmm),
        flags=add_flags(frame - 36, 16),
        flag_mask=0x8D5,
        df=0,
        endpoint=fixture["return_address"],
        pages=pages,
        events=events,
        trace_rvas=[f"0x{pc:08x}" for pc in TRACE],
        boundaries=boundaries,
        allocation_packet=allocation_packet,
        scalar_packet=scalar_packet,
        imported=imported,
        source_snapshot=p.read_bytes(fixture["pages"], o, 16),
    )


def final_pages(packet):
    original = packet["pages"]
    g = packet["registers"]["esp"]
    h = packet["registers"]["ecx"]
    j = int.from_bytes(p.read_bytes(original, g + 4, 4), "little")
    o = int.from_bytes(p.read_bytes(original, j, 4), "little")
    d = packet["allocation_result"]
    pages = dict(original)
    for offset in (0, 4, 8, 12):
        p.store(
            pages,
            d + offset,
            int.from_bytes(p.read_bytes(original, o + offset, 4), "little"),
        )
    for offset, value in ((0, d), (4, d + 16), (8, d + 16)):
        p.store(pages, h + offset, value)
    values = (
        packet["registers"]["ebp"],
        0,
        packet["registers"]["ebx"],
        packet["registers"]["esi"],
        packet["registers"]["edi"],
        d,
        j,
        d,
        d,
        0x4C5C81,
        g - 4,
        2,
        g - 32,
        16,
        0x48A968,
        g - 52,
        16,
        0x757507,
        g - 64,
        h,
        16,
        0,
        0x12345678,
        0x789463,
    )
    for index, value in enumerate(values, 1):
        p.store(pages, g - 4 * index, value)
    return pages


def check(actual, packet):
    wanted = independent(packet)
    p.assert_strict_packet(actual, wanted)
    p.assert_strict_packet(actual["pages"], final_pages(packet))
    assert set(actual) == KEYS and len(KEYS) == 15
    assert len(actual["events"]) == 90 and len(actual["trace_rvas"]) == 162
    assert tuple(actual["boundaries"]) == NAMES
    assert [len(b["events"]) for b in actual["boundaries"].values()] == [
        0,
        17,
        26,
        53,
        61,
        70,
        84,
    ]
    assert all(set(b) == BOUNDARY_KEYS for b in actual["boundaries"].values())
    assert set(actual["imported"]) == BOUNDARY_KEYS | {"entry_esp", "words"}
    assert len(actual["imported"]["events"]) == 45
    assert set(actual["allocation_packet"]) == {
        "relation",
        "registers",
        "flags",
        "flag_mask",
        "stack",
        "payload",
        "events",
    }
    assert len(actual["allocation_packet"]["events"]) == 27
    assert set(actual["scalar_packet"]) == p.KEYS
    assert len(actual["scalar_packet"]["events"]) == 14
    g, o, d, j, h = (
        wanted["geometry"][name]
        for name in (
            "entry",
            "source",
            "destination",
            "source_header",
            "destination_header",
        )
    )
    assert p.read_bytes(actual["pages"], o, 16) == p.read_bytes(packet["pages"], o, 16)
    assert p.read_bytes(actual["pages"], j, 12) == p.read_bytes(packet["pages"], j, 12)
    assert p.read_bytes(actual["pages"], g, 8) == p.read_bytes(packet["pages"], g, 8)
    assert not any(row["address"] == j + 8 for row in actual["events"])
    writes = {
        row["address"] + i
        for row in actual["events"]
        if row["access"] == "write"
        for i in range(4)
    }
    assert writes == set(range(g - 96, g)) | set(range(h, h + 12)) | set(
        range(d, d + 16)
    )
    assert (
        actual["boundaries"]["reserve_return"]["registers"]["eax"]
        == ((d + 16) & 0xFFFFFF00) | 1
    )
    assert actual["registers"]["ecx"] == int.from_bytes(
        p.read_bytes(packet["pages"], o + 12, 4), "little"
    )
    assert all(row["width"] == 4 for row in actual["events"])
    assert not {"0x003435d9", "0x003435bc", "0x0036ea60"}.intersection(
        actual["trace_rvas"]
    )
    assert not {"0x0009a8e0", "0x0036e580", "0x00007800"}.intersection(
        actual["trace_rvas"]
    )
    assert read_word(actual["pages"], g - 8) == 0
    cframe = g - 40
    assert [
        read_word(actual["boundaries"]["scalar_entry"]["pages"], cframe + i)
        for i in (4, 8, 12, 16)
    ] == [d, d, j, d]
    assert actual["boundaries"]["reserve_return"]["registers"]["esi"] == 2
    assert actual["boundaries"]["reserve_return"]["registers"]["edi"] == h
    assert actual["boundaries"]["reserve_return"]["registers"]["ebx"] == j


def read_word(pages, address):
    return int.from_bytes(p.read_bytes(pages, address, 4), "little")


@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize("profile", range(3))
def test_full_generalized_packet_and_independent_final_pages(alignment, profile):
    packet = inputs(
        frame=0x30001000 + alignment,
        source=0x06002800 + alignment,
        destination=0x06001000 + alignment,
        source_header=0x10000080 + alignment,
        header=0x10000100 + alignment,
        profile=profile,
    )
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    p.assert_strict_packet(packet, before)


@pytest.mark.parametrize("flags", FLAGS)
def test_all_128_ordinary_flags_and_actual_parent_entry(flags):
    packet = inputs(flags=flags)
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["boundaries"]["parent_entry"]["flags"] == flags
    assert actual["boundaries"]["parent_entry"]["flag_mask"] == 0xFFFFFFFF


@pytest.mark.parametrize(
    "g,o,d,j,h",
    [
        (0x02000103, 0x10000FF8, 0x06000000, 0x10002001, 0x10002FFA),
        (0x80000010, 0x10000FF8, 0x06003FF0, 0x90000FFC, 0x90002FF9),
        (0x80001003, 0x7FFFFFF8, 0x06003FF0, 0x90000FFC, 0x90002FF9),
        (0xFFFFFFF0, 0x90000FFD, 0x06000FF8, 0x10000FFB, 0x10002FFB),
        (96, 0x10000001, 0x06002003, 0x10000200, 0x100003CC),
        (0xFFFFFFF7, 0x10000FF8, 0x06001007, 0x10000203, 0x100003CC),
        (0x30001003, 0xFFFFFFEF, 0x06001007, 0x10000203, 0x100003CC),
        (0x30001000, 0x10000FF8, 0x06001007, 0xFFFFFFF3, 0x100003CC),
        (0x30001000, 0x10000FF8, 0x06001007, 0x10000203, 0xFFFFFFF3),
        (0x30001003, 0x30000F80, 0x06001007, 0x30001020, 0x3000102C),
        (0x30001000, 0x06000000, 0x06000010, 0x06003001, 0x0600300D),
        (0x30000FFD, 0x90000FFC, 0x06001007, 0x10000203, 0x100003CC),
    ],
)
def test_crossing_extreme_low_frame_stack_locals_and_record_continuation(g, o, d, j, h):
    packet = inputs(frame=g, source=o, destination=d, source_header=j, header=h)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("capacity", (0, 1, 15, 16, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF))
def test_source_header_capacity_is_arbitrary_unread_and_preserved(capacity):
    packet = inputs(capacity=capacity)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("value", (0, 0xFFFFFFFF, 0x80000000))
def test_arbitrary_gpr_xmm_source_bits_and_destination_bytes(value):
    packet = inputs()
    for name in GPR:
        if name not in ("ecx", "esp"):
            packet["registers"][name] = value
    for name in XMM:
        packet["xmm"][name] = sum(value << (32 * i) for i in range(4))
    for offset in (0, 4, 8, 12):
        p.store(packet["pages"], 0x10000FF8 + offset, value)
    for offset in (0, 4, 8):
        p.store(packet["pages"], 0x06001007 + offset, value)
    check(c.apply(**packet), packet)


def test_all_outputs_child_packets_and_boundaries_are_detached():
    packet = inputs()
    before = copy.deepcopy(packet)
    first = c.apply(**packet)
    second = c.apply(**packet)
    first["pages"].clear()
    first["registers"].clear()
    first["xmm"].clear()
    first["events"].clear()
    first["allocation_packet"]["events"].clear()
    first["scalar_packet"]["pages"].clear()
    first["imported"]["events"].clear()
    for boundary in first["boundaries"].values():
        boundary["pages"].clear()
        boundary["registers"].clear()
        boundary["events"].clear()
    check(second, packet)
    p.assert_strict_packet(packet, before)
    third = c.apply(**packet)
    saved = copy.deepcopy(third)
    third["boundaries"]["parent_entry"]["pages"].clear()
    third["boundaries"]["parent_entry"]["xmm"].clear()
    p.assert_strict_packet(
        third["boundaries"]["reserve_entry"], saved["boundaries"]["reserve_entry"]
    )
    p.assert_strict_packet(third["pages"], saved["pages"])
    third["scalar_packet"]["events"][0]["value"] ^= 1
    p.assert_strict_packet(third["events"], saved["events"])


@pytest.mark.parametrize(
    "group,key,value",
    [
        ("registers", "eax", True),
        ("registers", "esp", False),
        ("registers", "ecx", -1),
        ("registers", "ebp", 2**32),
        ("registers", "edx", 1.0),
        ("xmm", "xmm0", True),
        ("xmm", "xmm1", -1),
        ("xmm", "xmm7", 2**128),
        ("xmm", "xmm2", 1.0),
    ],
)
def test_typed_full_registers(group, key, value):
    packet = inputs()
    packet[group][key] = value
    with pytest.raises(c.PathAssign2Error):
        c.apply(**packet)


@pytest.mark.parametrize("group", ("registers", "xmm"))
@pytest.mark.parametrize("kind", ("extra", "missing", "mapping", "key_subclass"))
def test_exact_mapping_schemas(group, kind):
    packet = inputs()
    if kind == "extra":
        packet[group]["extra"] = 0
    elif kind == "missing":
        packet[group].pop(next(iter(packet[group])))
    elif kind == "mapping":
        packet[group] = UserDict(packet[group])
    else:

        class Key(str):
            pass

        packet[group] = {Key(k): v for k, v in packet[group].items()}
    with pytest.raises(c.PathAssign2Error):
        c.apply(**packet)


@pytest.mark.parametrize("key", ("entry_flags", "allocation_result", "return_address"))
@pytest.mark.parametrize("value", (True, 1.0, -1, 2**32))
def test_typed_scalar_inputs(key, value):
    packet = inputs()
    packet[key] = value
    with pytest.raises(c.PathAssign2Error):
        c.apply(**packet)


@pytest.mark.parametrize(
    "flags", (0, 4, 0xAD5, 0x200, 0x646, 0x10246, 0x400246, 0xFFFFFFFF)
)
def test_required_bit1_and_forbidden_control_flags(flags):
    packet = inputs(flags=flags)
    with pytest.raises(c.PathAssign2Error):
        c.apply(**packet)


@pytest.mark.parametrize("bit", [i for i in range(32) if not (0xAD7 >> i) & 1])
def test_each_forbidden_flag_bit(bit):
    packet = inputs(flags=0x246 | (1 << bit))
    with pytest.raises(c.PathAssign2Error):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    (
        "empty",
        "mapping",
        "mutable",
        "bytes_subclass",
        "short",
        "address_bool",
        "address_unaligned",
        "address_subclass",
        "source",
        "source_header",
        "destination_header",
        "stack_first",
        "stack_second",
        "data",
        "heap",
        "iat",
        "source_unmapped",
        "header_unmapped",
    ),
)
def test_exact_complete_page_domains(kind):
    packet = inputs(source=0x10004003, source_header=0x10002001, header=0x10003001)
    pages = packet["pages"]
    if kind == "empty":
        packet["pages"] = {}
    elif kind == "mapping":
        packet["pages"] = UserDict(pages)
    elif kind == "mutable":
        pages[0x12340000] = bytearray(pages[0x12340000])
    elif kind == "bytes_subclass":

        class Page(bytes):
            pass

        pages[0x12340000] = Page(pages[0x12340000])
    elif kind == "short":
        pages[0x12340000] = pages[0x12340000][:-1]
    elif kind == "address_bool":
        pages[True] = pages.pop(0x12340000)
    elif kind == "address_unaligned":
        pages[0x12340001] = pages.pop(0x12340000)
    elif kind == "address_subclass":

        class Address(int):
            pass

        packet["pages"] = {Address(k): v for k, v in pages.items()}
    elif kind == "source_unmapped":
        p.store(pages, 0x10002001, 0x11110000)
        p.store(pages, 0x10002005, 0x11110010)
    elif kind == "header_unmapped":
        packet["registers"]["ecx"] = 0x11110000
    else:
        pages.pop(
            {
                "source": 0x10004000,
                "source_header": 0x10002000,
                "destination_header": 0x10003000,
                "stack_first": 0x30000000,
                "stack_second": 0x30001000,
                "data": 0x06002000,
                "heap": 0x008B7000,
                "iat": 0x007D6000,
            }[kind]
        )
    before = copy.deepcopy(packet)
    with pytest.raises(c.PathAssign2Error):
        c.apply(**packet)
    p.assert_strict_packet(packet, before)


@pytest.mark.parametrize(
    "kind",
    (
        "heap",
        "iat",
        "count0",
        "count1",
        "count3",
        "source_null",
        "header_null",
        "caller_header_null",
        "caller_return",
        "allocation_low",
        "allocation_high",
    ),
)
def test_installed_globals_count_and_caller_law(kind):
    packet = inputs()
    pages = packet["pages"]
    if kind == "heap":
        p.store(pages, 0x008B7634, 0)
    elif kind == "iat":
        p.store(pages, 0x007D6220, 0)
    elif kind.startswith("count"):
        p.store(pages, 0x10000207, 0x10000FF8 + int(kind[-1]) * 8)
    elif kind == "source_null":
        p.store(pages, 0x10000203, 0)
        p.store(pages, 0x10000207, 16)
    elif kind == "header_null":
        packet["registers"]["ecx"] = 0
    elif kind == "caller_header_null":
        p.store(pages, 0x30001007, 0)
    elif kind == "caller_return":
        p.store(pages, 0x30001003, 0x0055BBCE)
    elif kind == "allocation_low":
        packet["allocation_result"] = 0x05FFFFFF
    else:
        packet["allocation_result"] = 0x06003FF1
    before = copy.deepcopy(packet)
    with pytest.raises(c.PathAssign2Error):
        c.apply(**packet)
    p.assert_strict_packet(packet, before)


@pytest.mark.parametrize(
    "g,o,d,j,h",
    [
        (95, 0x10000FF8, 0x06001007, 0x10000203, 0x10000308),
        (0xFFFFFFF8, 0x10000FF8, 0x06001007, 0x10000203, 0x10000308),
        (0x30001003, 0xFFFFFFF0, 0x06001007, 0x10000203, 0x10000308),
        (0x30001003, 0x10000FF8, 0x06001007, 0xFFFFFFF4, 0x10000308),
        (0x30001003, 0x10000FF8, 0x06001007, 0x10000203, 0xFFFFFFF4),
        (0x30001003, 0x10000FF8, 0x06001007, 0x10000203, 0x10000203),
        (0x30001003, 0x10000FF8, 0x06001007, 0x10000203, 0x1000020E),
        (0x30001003, 0x10000FF8, 0x06001007, 0x10000203, 0x10001007),
        (0x30001003, 0x06001000, 0x06001007, 0x10000203, 0x10000308),
        (0x30001003, 0x3000100A, 0x06001007, 0x10000203, 0x10000308),
        (0x06000060, 0x10000FF8, 0x06001007, 0x10000203, 0x10000308),
        (0x008B7060, 0x10000FF8, 0x06001007, 0x10000203, 0x10000308),
        (0x007D6060, 0x10000FF8, 0x06001007, 0x10000203, 0x10000308),
        (0x30001003, 0x008B7100, 0x06001007, 0x10000203, 0x10000308),
        (0x30001003, 0x10000FF8, 0x06001007, 0x007D6100, 0x10000308),
    ],
)
def test_disjoint_wrap_and_dynamic_lower_stack_window(g, o, d, j, h):
    packet = inputs(frame=g, source=o, destination=d, source_header=j, header=h)
    with pytest.raises(c.PathAssign2Error):
        c.apply(**packet)


@pytest.mark.parametrize("start,end", RANGES)
def test_all_selected_code_pages_are_excluded_even_for_untouched_mapping(start, end):
    packet = inputs()
    packet["pages"][start & ~4095] = bytes(4096)
    with pytest.raises(c.PathAssign2Error):
        c.apply(**packet)


@pytest.mark.parametrize(
    "ret",
    (
        0,
        0x30001003,
        0x10000FF8,
        0x06001007,
        0x10000203,
        0x10000308,
        *(start for start, end in RANGES),
    ),
)
def test_return_touched_data_and_actual_selected_bodies(ret):
    packet = inputs()
    packet["return_address"] = ret
    p.store(packet["pages"], 0x30001003, ret)
    with pytest.raises(c.PathAssign2Error):
        c.apply(**packet)


@pytest.mark.parametrize("ret", (1, 0xFFFFFFFF, 0x006573A7, 0x04000000))
def test_arbitrary_permitted_logical_return_word_and_actual_record_return(ret):
    packet = inputs(return_address=ret)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "kind",
    (
        "schema",
        "schema_missing",
        "relation_bool",
        "float_request",
        "float_flags",
        "request",
        "metadata",
        "gpr",
        "register_bool",
        "flags",
        "mask",
        "stack",
        "payload",
        "events",
        "ret_sentinel",
        "key_subclass",
        "coordinated_result",
        "restored_payload_events",
    ),
)
def test_complete_allocator_child_checked_before_only_return_transport(
    monkeypatch, kind
):
    original = c.allocator._expected

    def forged(*args, **kwargs):
        result = original(*args, **kwargs)
        if kind == "schema":
            result["opaque"] = 0
        elif kind == "schema_missing":
            result.pop("payload")
        elif kind == "relation_bool":
            result["relation"]["request"] = True
        elif kind == "float_request":
            result["relation"]["request"] = float(result["relation"]["request"])
        elif kind == "float_flags":
            result["flags"] = float(result["flags"])
        elif kind == "request":
            result["relation"]["request"] = 48
        elif kind == "metadata":
            result["relation"]["metadata"] = {}
        elif kind == "gpr":
            result["registers"]["edx"] ^= 1
        elif kind == "register_bool":
            result["registers"]["ebx"] = True
        elif kind == "flags":
            result["flags"] ^= 1
        elif kind == "mask":
            result["flag_mask"] = 0x8C5
        elif kind == "stack":
            result["stack"] = bytes([result["stack"][0] ^ 1]) + result["stack"][1:]
        elif kind == "payload":
            result["payload"] = (
                bytes([result["payload"][0] ^ 1]) + result["payload"][1:]
            )
        elif kind == "events":
            result["events"][0]["value"] ^= 1
        elif kind == "ret_sentinel":
            result["events"][-1]["value"] = 0x49AC78
        elif kind == "key_subclass":

            class Key(str):
                pass

            result = {Key(k): v for k, v in result.items()}
        elif kind == "coordinated_result":
            result["relation"]["result"] += 16
            result["registers"]["eax"] += 16
            result["registers"]["ecx"] += 16
        else:
            old = int.from_bytes(result["payload"][:4], "little")
            result["events"].extend(
                [
                    dict(access="write", address=0x06000000, width=4, value=old ^ 1),
                    dict(access="write", address=0x06000000, width=4, value=old),
                ]
            )
        return result

    monkeypatch.setattr(c.allocator, "_expected", forged)
    packet = inputs()
    before = copy.deepcopy(packet)
    with pytest.raises(c.PathAssign2Error, match="allocation primitive differs"):
        c.apply(**packet)
    p.assert_strict_packet(packet, before)


@pytest.mark.parametrize(
    "kind",
    (
        "schema",
        "gpr_bool",
        "xmm",
        "pages",
        "source",
        "events",
        "trace",
        "flags",
        "mask",
        "df",
        "endpoint",
        "coordinated_page_and_events",
    ),
)
def test_complete_scalar_child_independently_checked(monkeypatch, kind):
    def forged(**kwargs):
        result = p.independent(kwargs)
        if kind == "schema":
            result["opaque"] = 0
        elif kind == "gpr_bool":
            result["registers"]["ebx"] = True
        elif kind == "xmm":
            result["xmm"]["xmm7"] ^= 1
        elif kind == "pages":
            p.store(result["pages"], 0x12340000, 1)
        elif kind == "source":
            result["source_snapshot"] = bytes(16)
        elif kind == "events":
            result["events"][4]["value"] ^= 1
        elif kind == "trace":
            result["trace_rvas"][0] = "0x0008aba1"
        elif kind == "flags":
            result["flags"] ^= 1
        elif kind == "mask":
            result["flag_mask"] = 0x8C5
        elif kind == "df":
            result["df"] = False
        elif kind == "endpoint":
            result["endpoint"] += 1
        else:
            row = result["events"][4]
            row["value"] ^= 1
            p.store(result["pages"], row["address"], row["value"])
        return result

    monkeypatch.setattr(c.scalar, "apply", forged)
    packet = inputs()
    before = copy.deepcopy(packet)
    with pytest.raises(c.PathAssign2Error, match="scalar primitive differs"):
        c.apply(**packet)
    p.assert_strict_packet(packet, before)


@pytest.mark.parametrize("child", ("allocation", "scalar"))
def test_foreign_child_errors_are_normalized(child, monkeypatch):
    def failed(*args, **kwargs):
        raise RuntimeError("foreign child")

    monkeypatch.setattr(
        c.allocator if child == "allocation" else c.scalar,
        "_expected" if child == "allocation" else "apply",
        failed,
    )
    with pytest.raises(c.PathAssign2Error, match="foreign child"):
        c.apply(**inputs())


def test_exact_actual_child_arguments_and_source_only_dependencies(monkeypatch):
    calls = []
    alloc = c.allocator._expected
    scalar = c.scalar.apply

    def track_alloc(*args, **kwargs):
        calls.append(("alloc", copy.deepcopy(args), copy.deepcopy(kwargs)))
        return alloc(*args, **kwargs)

    def track_scalar(**kwargs):
        calls.append(("scalar", copy.deepcopy(kwargs)))
        return scalar(**kwargs)

    monkeypatch.setattr(c.allocator, "_expected", track_alloc)
    monkeypatch.setattr(c.scalar, "apply", track_scalar)
    packet = inputs(frame=0x02000103)
    check(c.apply(**packet), packet)
    assert [call[0] for call in calls] == ["alloc", "scalar"]
    _, args, kwargs = calls[0]
    assert args[0] == {"count": 2, "pointer": 0x06001007}
    assert kwargs == {"stack_base": 0x02000000, "data_base": 0x06000000}
    assert args[1]["esp"] == 0x02000103 - 48
    assert len(args[2]) == 8192 and len(args[3]) == 16384
    assert calls[1][1]["registers"]["esp"] == 0x02000103 - 40
    assert calls[1][1]["return_address"] == 0x4C5C81
    assert calls[1][1]["entry_flags"] == 0x202
    source = inspect.getsource(c)
    tree = ast.parse(source)
    assert {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} == {
        "__future__",
        "src.observatory",
    }
    assert not any(word in source for word in ("unicorn", "subprocess", "capstone"))
    assert not any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id in ("open", "eval", "exec")
        for n in ast.walk(tree)
    )
    assert c.ANALYSIS_KIND == "pe_native_movement_path_assign2_semantics"
    assert len(c.SOURCE_PINS) == 5
    assert c.SOURCE_PINS["clone2_conformance"] == (
        "pe_native_movement_path_clone2_conformance",
        "1cddf384c45fb50a60752656acd2560a7e243dd20f0d68b8a963a4a7bb3a739b",
    )


@pytest.mark.parametrize("offset", (0, 4, 8))
@pytest.mark.parametrize("value", (1, 16, 0xFFFFFFFF))
def test_all_three_destination_words_must_be_zero(offset, value):
    packet = inputs()
    p.store(packet["pages"], packet["registers"]["ecx"] + offset, value)
    before = copy.deepcopy(packet)
    with pytest.raises(c.PathAssign2Error, match="destination is not empty"):
        c.apply(**packet)
    p.assert_strict_packet(packet, before)


@pytest.mark.parametrize("g", (96, 0x02000103, 0x30000FFD, 0x80000010, 0xFFFFFFF7))
def test_source_derived_frame_join_and_owner_trace(g):
    assert c.frame_join(g) == dict(
        parent=g,
        reserve=g - 28,
        allocation=g - 48,
        heap=g - 96,
        scalar=g - 40,
        returned=g + 8,
        protected_start=g - 96,
        protected_end=g + 8,
    )
    assert len(OWNER_PREFIX) == 38 and len(OWNER_MIDDLE) == 9 and len(OWNER_SUFFIX) == 9
    assert len(TRACE) == 162 and len(set(TRACE)) == 152
    assert c.BODY_PINS[0xC5BB0] == (
        226,
        "62157759ee3564515e63f20e297c171de6444d84732bccf7414eb208d953eefe",
    )
    assert (
        len(c.BODY_PINS) == 7
        and sum(size for size, digest in c.BODY_PINS.values()) == 587
    )


@pytest.mark.parametrize("g", (True, 1.0, -1, 95, 0xFFFFFFF8, 2**32))
def test_frame_join_typed_conservative_bounds(g):
    with pytest.raises(c.PathAssign2Error):
        c.frame_join(g)
