"""Independent generalized actual-page zero-or-small-count movement path clone law.

The expected packet generalizes the previously handwritten finite source oracle.
Production apply supplies only actuals, never fixture or expected calculations.
"""

from __future__ import annotations
import ast
import copy
import inspect
from collections import UserDict
import pytest
from src.observatory import native_movement_path_small_clone_semantics as c
from tests import test_itb_native_movement_path_scalar_clone2_semantics as p
from tests import test_itb_native_movement_path_scalar_semantics as scalar_test

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
    (0x49A8E0, 0x49A92F),
    (0x49AC40, 0x49AC97),
    (0x7574DB, 0x75750E),
    (0x779F52, 0x779F5D),
    (0x78942B, 0x789479),
)


def inputs(
    count=2,
    *,
    frame=0x30001003,
    source=0x10000FF8,
    destination=0x06001007,
    source_header=0x10000203,
    header=0x10000308,
    profile=0,
    flags=0x246,
    return_address=0x0055BBCA,
    capacity=0xFFFFFFFF,
):
    size = count * 8
    stack_base = min((frame - 88) & ~4095, 0xFFFFE000)
    spans = (
        (source, source + size),
        (source_header, source_header + 12),
        (header, header + 12),
        (destination, destination + size),
        (frame - 88, frame + 8),
    )
    mapped = {
        b
        for start, end in spans
        if start < end
        for b in range(start & ~4095, ((end - 1) & ~4095) + 1, 4096)
    }
    mapped.update(
        (
            stack_base,
            stack_base + 4096,
            0x00893000,
            0x12340000,
        )
    )
    if count:
        mapped.update(
            (0x06000000, 0x06001000, 0x06002000, 0x06003000, 0x008B7000, 0x007D6000)
        )
    pages = {
        b: bytes((i * 53 + j * 29 + profile * 71) & 255 for j in range(4096))
        for i, b in enumerate(sorted(mapped))
    }
    for at, value in (
        (frame, return_address),
        (frame + 4, source_header),
        (source_header, source),
        (source_header + 4, (source + size) & 0xFFFFFFFF),
        (source_header + 8, capacity),
    ):
        p.store(pages, at, value)
    if count:
        p.store(pages, 0x008B7634, 0x12345678)
        p.store(pages, 0x007D6220, 0x05000000)
    for i in range(size // 4):
        value = (0xD15C0016 + i * 0x29481736) & 0xFFFFFFFF
        p.store(pages, source + i * 4, value ^ ((profile * 0x7654321) & 0xFFFFFFFF))
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
        allocation_result=destination if count else 0,
    )


PARENT_BEFORE = tuple(
    int(w, 16)
    for w in "9a8e0 9a8e1 9a8e3 9a8e4 9a8e6 9a8e7 9a8ea 9a8f0 9a8f7 9a8fe 9a901 9a903 9a906 9a907".split()
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
PARENT_MIDDLE = tuple(
    int(w, 16) for w in "9a90c 9a90e 9a910 9a913 9a914 9a917 9a918 9a91a 9a91c".split()
)
PARENT_AFTER = tuple(
    int(w, 16) for w in "9a921 9a924 9a927 9a928 9a92a 9a92b 9a92c".split()
)
SCALAR_BEFORE = (0x8ABA0, 0x8ABA1, 0x8ABA3, 0x8ABA6, 0x8ABA7, 0x8ABA9, 0x8ABAB, 0x8ABAD)
SCALAR_LOOP = (
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
SCALAR_AFTER = (0x8ABC8, 0x8ABC9, 0x8ABCA)
ZERO_RESERVE = (
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
)


def trace(count):
    if count == 0:
        return (
            PARENT_BEFORE
            + ZERO_RESERVE
            + (0x9A90C, 0x9A90E, 0x9A927, 0x9A928, 0x9A92A, 0x9A92B, 0x9A92C)
        )
    return (
        PARENT_BEFORE
        + RESERVE_BEFORE
        + ALLOCATION
        + RESERVE_AFTER
        + PARENT_MIDDLE
        + SCALAR_BEFORE
        + SCALAR_LOOP * count
        + SCALAR_AFTER
        + PARENT_AFTER
    )


def logical_flags(word):
    return (
        (0x40 if word == 0 else 0)
        | (0x80 if word & 0x80000000 else 0)
        | (4 if (word & 255).bit_count() % 2 == 0 else 0)
    )


def sub_flags(left, right):
    result = (left - right) & 0xFFFFFFFF
    return (
        int(left < right)
        | logical_flags(result)
        | (0x10 if (left ^ right ^ result) & 16 else 0)
        | (0x800 if (left ^ right) & (left ^ result) & 0x80000000 else 0)
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
    size = int.from_bytes(p.read_bytes(fixture["pages"], j + 4, 4), "little") - o
    count = size // 8
    stack_base = min((frame - 88) & ~4095, 0xFFFFE000)
    pages = dict(fixture["pages"])
    events = []
    initial = fixture["registers"]
    xmm = fixture["xmm"]
    regs = dict(initial)

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
        "parent_entry": boundary(0x49A8E0, fixture["entry_flags"], 0xFFFFFFFF)
    }
    for at, value in (
        (frame - 4, initial["ebp"]),
        (frame - 8, initial["esi"]),
        (frame - 12, initial["edi"]),
    ):
        write(at, value)
    read(frame + 4, j)
    for at in (h, h + 4, h + 8):
        write(at, 0)
    read(j + 4, o + size)
    read(j, o)
    write(frame - 16, count)
    write(frame - 20, 0x49A90C)
    regs.update(eax=count, esi=h, edi=j, ebp=frame - 4, esp=frame - 20)
    boundaries["reserve_entry"] = boundary(0x49AC40, logical_flags(count), 0xC5)
    for at, value in ((frame - 24, frame - 4), (frame - 28, h), (frame - 32, j)):
        write(at, value)
    read(frame - 16, count)
    for at in (h, h + 4, h + 8):
        write(at, 0)
    if count == 0:
        for address, value in (
            (frame - 32, j),
            (frame - 28, h),
            (frame - 24, frame - 4),
            (frame - 20, 0x49A90C),
        ):
            read(address, value)
        regs.update(eax=0, edi=j, esi=h, ebp=frame - 4, esp=frame - 12)
        boundaries["reserve_return"] = boundary(0x49A90C, 0x44, 0x8C5)
        for address, value in (
            (frame - 12, initial["edi"]),
            (frame - 8, initial["esi"]),
            (frame - 4, initial["ebp"]),
            (frame, fixture["return_address"]),
        ):
            read(address, value)
        return dict(
            geometry=dict(
                entry=frame,
                source=o,
                destination=0,
                source_header=j,
                destination_header=h,
            ),
            registers=dict(initial, eax=h, ecx=h, esp=frame + 8),
            xmm=dict(xmm),
            flags=0x44,
            flag_mask=0x8C5,
            df=0,
            endpoint=fixture["return_address"],
            pages=pages,
            events=events,
            trace_rvas=[f"0x{pc:08x}" for pc in trace(0)],
            boundaries=boundaries,
            allocation_packet=None,
            scalar_packet=None,
            imported=None,
            source_snapshot=b"",
        )
    write(frame - 36, count)
    write(frame - 40, 0x49AC78)
    regs.update(edi=count, ebp=frame - 24, esp=frame - 40)
    boundaries["allocation_entry"] = boundary(
        0x48A920, sub_flags(count, 0x1FFFFFFF), 0x8D5
    )
    allocation_initial = dict(regs)
    at = frame - 40
    start = len(events)
    write(at - 4, regs["ebp"])
    read(at + 4, count)
    for offset, value in ((-8, size), (-12, 0x48A968), (-16, at - 4)):
        write(at + offset, value)
    read(at - 8, size)
    for offset, value in ((-20, size), (-24, 0x757507), (-28, at - 16)):
        write(at + offset, value)
    read(at - 28, at - 16)
    write(at - 28, at - 16)
    write(at - 32, regs["esi"])
    read(at - 20, size)
    write(at - 36, size)
    write(at - 40, 0)
    read(0x8B7634, 0x12345678)
    write(at - 44, 0x12345678)
    read(0x7D6220, 0x5000000)
    write(at - 48, 0x789463)
    regs.update(eax=size, esi=size, ebp=at - 28, esp=at - 48)
    imported = boundary(0x5000000, logical_flags(size), 0x8C5)
    imported.update(entry_esp=frame - 88, words=[0x789463, 0x12345678, 0, size])
    for address, value in (
        (at - 32, allocation_initial["esi"]),
        (at - 28, at - 16),
        (at - 24, 0x757507),
        (at - 20, size),
        (at - 16, at - 4),
        (at - 12, 0x48A968),
        (at - 4, allocation_initial["ebp"]),
        (at, 0x49AC78),
    ):
        read(address, value)
    regs = dict(allocation_initial, eax=d, ecx=d, edx=0xB0000001, esp=at + 8)
    allocflags = add_flags(at - 8, 4)
    allocation_packet = dict(
        relation=dict(result=d, request=size, metadata=None),
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
    write(h + 8, d + size)
    for address, value in (
        (frame - 32, j),
        (frame - 28, h),
        (frame - 24, frame - 4),
        (frame - 20, 0x49A90C),
    ):
        read(address, value)
    regs.update(eax=((d + size) & 0xFFFFFF00) | 1, edi=j, ebp=frame - 4, esp=frame - 12)
    boundaries["reserve_return"] = boundary(0x49A90C, allocflags, 0x8D5)
    read(j + 4, o + size)
    write(frame - 16, d)
    read(frame + 4, j)
    write(frame - 20, j)
    write(frame - 24, d)
    read(h, d)
    write(frame - 28, d)
    read(j, o)
    write(frame - 32, 0x49A921)
    regs.update(edx=o + size, ecx=o, esp=frame - 32)
    boundaries["scalar_entry"] = boundary(0x48ABA0, 0, 0x8C5)
    scalar_packet = scalar_test.independent(
        dict(
            pages=dict(pages),
            registers=dict(regs),
            xmm=dict(xmm),
            source=o,
            destination=d,
            return_address=0x49A921,
            entry_flags=0x202,
        )
    )
    pages = dict(scalar_packet["pages"])
    events.extend(copy.deepcopy(scalar_packet["events"]))
    regs = dict(scalar_packet["registers"])
    boundaries["scalar_return"] = boundary(0x49A921, 0x44, 0x8D5)
    write(h + 4, d + size)
    for address, value in (
        (frame - 12, initial["edi"]),
        (frame - 8, initial["esi"]),
        (frame - 4, initial["ebp"]),
        (frame, fixture["return_address"]),
    ):
        read(address, value)
    regs.update(
        eax=h, esi=initial["esi"], edi=initial["edi"], ebp=initial["ebp"], esp=frame + 8
    )
    return dict(
        geometry=dict(
            entry=frame, source=o, destination=d, source_header=j, destination_header=h
        ),
        registers=regs,
        xmm=dict(xmm),
        flags=add_flags(frame - 28, 16),
        flag_mask=0x8D5,
        df=0,
        endpoint=fixture["return_address"],
        pages=pages,
        events=events,
        trace_rvas=[f"0x{pc:08x}" for pc in trace(count)],
        boundaries=boundaries,
        allocation_packet=allocation_packet,
        scalar_packet=scalar_packet,
        imported=imported,
        source_snapshot=p.read_bytes(fixture["pages"], o, size),
    )


def final_pages(packet):
    original = packet["pages"]
    g, h = packet["registers"]["esp"], packet["registers"]["ecx"]
    j = int.from_bytes(p.read_bytes(original, g + 4, 4), "little")
    o = int.from_bytes(p.read_bytes(original, j, 4), "little")
    size = int.from_bytes(p.read_bytes(original, j + 4, 4), "little") - o
    d = packet["allocation_result"]
    pages = dict(original)
    for offset in range(0, size, 4):
        p.store(
            pages,
            d + offset,
            int.from_bytes(p.read_bytes(original, o + offset, 4), "little"),
        )
    for offset, value in ((0, d), (4, d + size), (8, d + size)):
        p.store(pages, h + offset, value)
    if size:
        values = (
            packet["registers"]["ebp"],
            packet["registers"]["esi"],
            packet["registers"]["edi"],
            d,
            j,
            d,
            d,
            0x49A921,
            g - 4,
            h,
            g - 24,
            size,
            0x48A968,
            g - 44,
            size,
            0x757507,
            g - 56,
            h,
            size,
            0,
            0x12345678,
            0x789463,
        )
    else:
        values = (
            packet["registers"]["ebp"],
            packet["registers"]["esi"],
            packet["registers"]["edi"],
            0,
            0x49A90C,
            g - 4,
            h,
            j,
        )
    for index, value in enumerate(values, 1):
        p.store(pages, g - 4 * index, value)
    return pages


def check(actual, packet):
    wanted = independent(packet)
    p.assert_strict_packet(actual, wanted)
    p.assert_strict_packet(actual["pages"], final_pages(packet))
    assert type(actual) is dict and set(actual) == KEYS
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
    size = int.from_bytes(p.read_bytes(packet["pages"], j + 4, 4), "little") - o
    n = size // 8
    assert len(actual["events"]) == (75 + 4 * n if n else 26)
    assert len(actual["trace_rvas"]) == (116 + 10 * n if n else 37)
    assert tuple(actual["boundaries"]) == (
        NAMES if n else ("parent_entry", "reserve_entry", "reserve_return")
    )
    assert [len(b["events"]) for b in actual["boundaries"].values()] == (
        [0, 11, 20, 47, 55, 64, 70 + 4 * n] if n else [0, 11, 22]
    )
    assert all(set(b) == BOUNDARY_KEYS for b in actual["boundaries"].values())
    assert p.read_bytes(actual["pages"], j, 12) == p.read_bytes(packet["pages"], j, 12)
    assert p.read_bytes(actual["pages"], g, 8) == p.read_bytes(packet["pages"], g, 8)
    assert not any(row["address"] == j + 8 for row in actual["events"])
    assert all(
        type(row["width"]) is int and row["width"] == 4 for row in actual["events"]
    )
    assert [
        row["address"]
        for row in actual["events"]
        if row["access"] == "write" and h <= row["address"] < h + 12
    ][:6] == [h, h + 4, h + 8] * 2
    if n:
        assert p.read_bytes(actual["pages"], o, size) == p.read_bytes(
            packet["pages"], o, size
        )
        assert set(actual["imported"]) == BOUNDARY_KEYS | {"entry_esp", "words"}
        assert len(actual["imported"]["events"]) == 39
        assert len(actual["allocation_packet"]["events"]) == 27
        assert len(actual["scalar_packet"]["events"]) == 6 + 4 * n
        assert actual["allocation_packet"]["relation"] == dict(
            result=d, request=size, metadata=None
        )
        assert (
            actual["boundaries"]["reserve_return"]["registers"]["eax"]
            == ((d + size) & 0xFFFFFF00) | 1
        )
        assert actual["registers"]["ecx"] == int.from_bytes(
            p.read_bytes(packet["pages"], o + size - 4, 4), "little"
        )
    else:
        assert (
            actual["allocation_packet"]
            is actual["scalar_packet"]
            is actual["imported"]
            is None
        )
        assert actual["source_snapshot"] == b""
        assert actual["registers"]["edx"] == packet["registers"]["edx"]
        assert not any(
            row["address"] in (0x8B7634, 0x7D6220) for row in actual["events"]
        )


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
    with pytest.raises(c.SmallPathCloneError):
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
    with pytest.raises(c.SmallPathCloneError):
        c.apply(**packet)


@pytest.mark.parametrize("key", ("entry_flags", "allocation_result", "return_address"))
@pytest.mark.parametrize("value", (True, 1.0, -1, 2**32))
def test_typed_scalar_inputs(key, value):
    packet = inputs()
    packet[key] = value
    with pytest.raises(c.SmallPathCloneError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "flags", (0, 4, 0xAD5, 0x200, 0x646, 0x10246, 0x400246, 0xFFFFFFFF)
)
def test_required_bit1_and_forbidden_control_flags(flags):
    packet = inputs(flags=flags)
    with pytest.raises(c.SmallPathCloneError):
        c.apply(**packet)


@pytest.mark.parametrize("bit", [i for i in range(32) if not (0xAD7 >> i) & 1])
def test_each_forbidden_flag_bit(bit):
    packet = inputs(flags=0x246 | (1 << bit))
    with pytest.raises(c.SmallPathCloneError):
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
    with pytest.raises(c.SmallPathCloneError):
        c.apply(**packet)
    p.assert_strict_packet(packet, before)


@pytest.mark.parametrize(
    "kind",
    (
        "heap",
        "iat",
        "count512",
        "count_negative",
        "count_fraction",
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
        delta = {"count512": 4096, "count_negative": -8, "count_fraction": 7}[kind]
        p.store(pages, 0x10000207, 0x10000FF8 + delta)
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
    with pytest.raises(c.SmallPathCloneError):
        c.apply(**packet)
    p.assert_strict_packet(packet, before)


@pytest.mark.parametrize(
    "g,o,d,j,h",
    [
        (87, 0x10000FF8, 0x06001007, 0x10000203, 0x10000308),
        (0xFFFFFFF8, 0x10000FF8, 0x06001007, 0x10000203, 0x10000308),
        (0x30001003, 0xFFFFFFF0, 0x06001007, 0x10000203, 0x10000308),
        (0x30001003, 0x10000FF8, 0x06001007, 0xFFFFFFF4, 0x10000308),
        (0x30001003, 0x10000FF8, 0x06001007, 0x10000203, 0xFFFFFFF4),
        (0x30001003, 0x10000FF8, 0x06001007, 0x10000203, 0x10000203),
        (0x30001003, 0x10000FF8, 0x06001007, 0x10000203, 0x1000020E),
        (0x30001003, 0x10000FF8, 0x06001007, 0x10000203, 0x10001007),
        (0x30001003, 0x06001000, 0x06001007, 0x10000203, 0x10000308),
        (0x30001003, 0x3000100A, 0x06001007, 0x10000203, 0x10000308),
        (0x06000058, 0x10000FF8, 0x06001007, 0x10000203, 0x10000308),
        (0x008B7058, 0x10000FF8, 0x06001007, 0x10000203, 0x10000308),
        (0x007D6058, 0x10000FF8, 0x06001007, 0x10000203, 0x10000308),
        (0x30001003, 0x008B7100, 0x06001007, 0x10000203, 0x10000308),
        (0x30001003, 0x10000FF8, 0x06001007, 0x007D6100, 0x10000308),
    ],
)
def test_disjoint_wrap_and_dynamic_lower_stack_window(g, o, d, j, h):
    packet = inputs(frame=g, source=o, destination=d, source_header=j, header=h)
    with pytest.raises(c.SmallPathCloneError):
        c.apply(**packet)


@pytest.mark.parametrize("start,end", RANGES)
def test_all_selected_code_pages_are_excluded_even_for_untouched_mapping(start, end):
    packet = inputs()
    packet["pages"][start & ~4095] = bytes(4096)
    with pytest.raises(c.SmallPathCloneError):
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
    with pytest.raises(c.SmallPathCloneError):
        c.apply(**packet)


@pytest.mark.parametrize("ret", (1, 0xFFFFFFFF, 0x0055BBCA, 0x004C5C6C))
def test_arbitrary_permitted_logical_return_word_and_actual_record_return(ret):
    packet = inputs(return_address=ret)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("count", (1, 511))
@pytest.mark.parametrize(
    "kind",
    (
        "schema",
        "schema_missing",
        "relation_bool",
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
    monkeypatch, kind, count
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
    packet = inputs(count)
    before = copy.deepcopy(packet)
    with pytest.raises(c.SmallPathCloneError, match="allocation primitive differs"):
        c.apply(**packet)
    p.assert_strict_packet(packet, before)


@pytest.mark.parametrize("count", (1, 511))
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
def test_complete_scalar_child_independently_checked(monkeypatch, kind, count):
    def forged(**kwargs):
        result = scalar_test.independent(kwargs)
        if kind == "schema":
            result["opaque"] = 0
        elif kind == "gpr_bool":
            result["registers"]["ebx"] = True
        elif kind == "xmm":
            result["xmm"]["xmm7"] ^= 1
        elif kind == "pages":
            p.store(result["pages"], 0x12340000, 1)
        elif kind == "source":
            result["source_snapshot"] = (
                bytes([result["source_snapshot"][0] ^ 1])
                + result["source_snapshot"][1:]
            )
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
    packet = inputs(count)
    before = copy.deepcopy(packet)
    with pytest.raises(c.SmallPathCloneError, match="scalar primitive differs"):
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
    with pytest.raises(c.SmallPathCloneError, match="foreign child"):
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
    assert args[1]["esp"] == 0x02000103 - 40
    assert len(args[2]) == 8192 and len(args[3]) == 16384
    assert calls[1][1]["registers"]["esp"] == 0x02000103 - 32
    assert calls[1][1]["return_address"] == 0x49A921
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
    assert c.ANALYSIS_KIND == "pe_native_movement_path_small_clone_semantics"
    assert len(c.SOURCE_PINS) == 5
    assert c.SOURCE_PINS["clone2_conformance"] == (
        "pe_native_movement_path_clone2_conformance",
        "1cddf384c45fb50a60752656acd2560a7e243dd20f0d68b8a963a4a7bb3a739b",
    )


@pytest.mark.parametrize("count", (0, 1, 2, 3, 7, 31, 127, 255, 256, 511))
@pytest.mark.parametrize("alignment", (0, 7, 15))
def test_full_dynamic_packet_boundary_trace_and_separate_byte_law(count, alignment):
    packet = inputs(
        count,
        frame=0x30001000 + alignment,
        source=0x10000FF8 + alignment,
        destination=0x06001000 + alignment,
        profile=alignment % 3,
    )
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    p.assert_strict_packet(packet, before)


@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize("profile", range(3))
def test_established_count2_geometry_full_independent_law(alignment, profile):
    packet = inputs(
        2,
        frame=0x30001000 + alignment,
        source=0x06002800 + alignment,
        destination=0x06001000 + alignment,
        source_header=0x10000080 + alignment,
        header=0x10000100 + alignment,
        profile=profile,
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("flags", FLAGS)
@pytest.mark.parametrize("count", (0, 7))
def test_all_ordinary_flags_both_branches_and_full_entry(flags, count):
    packet = inputs(count, flags=flags)
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["boundaries"]["parent_entry"]["flags"] == flags
    assert actual["boundaries"]["parent_entry"]["flag_mask"] == 0xFFFFFFFF


@pytest.mark.parametrize("source", (0, 1, 0x12345678, 0xFFFFFFFF))
@pytest.mark.parametrize("capacity", (0, 15, 0x80000000, 0xFFFFFFFF))
def test_zero_unmapped_empty_source_arbitrary_capacity_no_runtime(
    source, capacity, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("zero branch invoked primitive")

    monkeypatch.setattr(c.allocator, "_expected", forbidden)
    monkeypatch.setattr(c.scalar, "apply", forbidden)
    packet = inputs(0, source=source, capacity=capacity)
    assert not set(
        (0x06000000, 0x06001000, 0x06002000, 0x06003000, 0x8B7000, 0x7D6000)
    ).intersection(packet["pages"])
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "g,o,d,j,h,count",
    [
        (0x02000103, 0x10000FF8, 0x06000000, 0x10002001, 0x10002FFA, 511),
        (0x80000010, 0x10000FF8, 0x06003008, 0x90000FFC, 0x90002FF9, 511),
        (0x80001003, 0x7FFFFFF8, 0x06003FF8, 0x90000FFC, 0x90002FF9, 1),
        (0xFFFFFFF7, 0x90000FFD, 0x06000FF8, 0x10000FFB, 0x10002FFB, 3),
        (88, 0x10000001, 0x06002003, 0x10000200, 0x100003CC, 7),
        (0x30001003, 0xFFFFFFF7, 0x06001007, 0x10000203, 0x100003CC, 1),
        (0x30001000, 0x10000FF8, 0x06001007, 0xFFFFFFF3, 0x100003CC, 7),
        (0x30001000, 0x10000FF8, 0x06001007, 0x10000203, 0xFFFFFFF3, 7),
        (0x30001003, 0x30000F80, 0x06001007, 0x30001020, 0x3000102C, 1),
        (0x30001000, 0x06000000, 0x06001000, 0x06003001, 0x0600300D, 511),
        (0x30000FFD, 0x90000FFC, 0x06001007, 0x10000203, 0x100003CC, 7),
        (0x30001003, 0xFFFFFFFF, 0, 0x3000100B, 0x30001017, 0),
    ],
)
def test_dynamic_frame_signed_crossings_headers_adjacency_and_maximum(
    g, o, d, j, h, count
):
    packet = inputs(count, frame=g, source=o, destination=d, source_header=j, header=h)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("count", (0, 1, 511))
@pytest.mark.parametrize("capacity", (0, 1, 15, 16, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF))
def test_source_header_capacity_unread_for_dynamic_counts(count, capacity):
    packet = inputs(count, capacity=capacity)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("count", (0, 3))
@pytest.mark.parametrize("value", (0, 0x80000000, 0xFFFFFFFF))
def test_all_full_register_and_payload_bits(count, value):
    packet = inputs(count)
    for name in GPR:
        if name not in ("esp", "ecx"):
            packet["registers"][name] = value
    for name in XMM:
        packet["xmm"][name] = sum(value << (32 * i) for i in range(4))
    for offset in range(0, count * 8, 4):
        p.store(packet["pages"], 0x10000FF8 + offset, value)
    for offset in (0, 4, 8):
        p.store(packet["pages"], 0x10000308 + offset, value)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("count", (0, 7))
def test_nested_output_detachment_and_unchanged_inputs(count):
    packet = inputs(count)
    before = copy.deepcopy(packet)
    first = c.apply(**packet)
    second = c.apply(**packet)
    first["pages"].clear()
    first["registers"].clear()
    first["xmm"].clear()
    first["events"].clear()
    for row in first["boundaries"].values():
        row["pages"].clear()
        row["registers"].clear()
        row["events"].clear()
    if count:
        first["allocation_packet"]["events"].clear()
        first["scalar_packet"]["pages"].clear()
        first["imported"]["events"].clear()
    check(second, packet)
    p.assert_strict_packet(packet, before)
    third = c.apply(**packet)
    saved = copy.deepcopy(third)
    third["boundaries"]["parent_entry"]["pages"].clear()
    p.assert_strict_packet(
        third["boundaries"]["reserve_entry"], saved["boundaries"]["reserve_entry"]
    )
    p.assert_strict_packet(third["pages"], saved["pages"])
    if count:
        third["scalar_packet"]["events"][0]["value"] ^= 1
        p.assert_strict_packet(third["events"], saved["events"])


@pytest.mark.parametrize("count", (512, 513, 0x1000, 0x1FFFFFFF))
def test_count_boundary_rejects_before_any_child(count, monkeypatch):
    packet = inputs()
    j = 0x10000203
    p.store(packet["pages"], j, 0)
    p.store(packet["pages"], j + 4, count * 8)

    def forbidden(*args, **kwargs):
        raise AssertionError("unsupported count reached primitive")

    monkeypatch.setattr(c.allocator, "_expected", forbidden)
    monkeypatch.setattr(c.scalar, "apply", forbidden)
    with pytest.raises(
        c.SmallPathCloneError, match="count requires aligned allocation"
    ):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    (
        "zero_allocation",
        "zero_bool",
        "zero_float",
        "positive_null",
        "reversed",
        "unaligned",
        "allocation_last",
        "caller_header_alias",
    ),
)
def test_zero_positive_domain_boundaries(kind):
    count = 0 if kind.startswith("zero") else 1
    packet = inputs(count)
    if kind == "zero_allocation":
        packet["allocation_result"] = 0x06001007
    elif kind == "zero_bool":
        packet["allocation_result"] = False
    elif kind == "zero_float":
        packet["allocation_result"] = 0.0
    elif kind == "positive_null":
        p.store(packet["pages"], 0x10000203, 0)
        p.store(packet["pages"], 0x10000207, 8)
    elif kind == "reversed":
        p.store(packet["pages"], 0x10000207, 0x10000FF7)
    elif kind == "unaligned":
        p.store(packet["pages"], 0x10000207, 0x10001001)
    elif kind == "allocation_last":
        packet["allocation_result"] = 0x06003FF9
    else:
        packet["registers"]["ecx"] = 0x10000203
    with pytest.raises(c.SmallPathCloneError):
        c.apply(**packet)


@pytest.mark.parametrize("count", (1, 7, 511))
def test_dynamic_primitive_packets_independent_and_actual_child_arguments(
    count, monkeypatch
):
    packet = inputs(count, frame=0x02000103)
    wanted = independent(packet)
    calls = []

    def allocation(vector, registers, stack, payload, **kwargs):
        calls.append(
            ("allocation", copy.deepcopy((vector, registers, stack, payload, kwargs)))
        )
        assert vector == dict(count=count, pointer=packet["allocation_result"])
        assert registers == wanted["boundaries"]["allocation_entry"]["registers"]
        assert kwargs == dict(stack_base=0x02000000, data_base=0x06000000)
        result = copy.deepcopy(wanted["allocation_packet"])
        result["events"][-1]["value"] = 0x04000000
        return result

    def scalar(**kwargs):
        calls.append(("scalar", copy.deepcopy(kwargs)))
        assert kwargs["registers"] == wanted["boundaries"]["scalar_entry"]["registers"]
        assert kwargs["entry_flags"] == 0x202 and kwargs["return_address"] == 0x49A921
        return scalar_test.independent(kwargs)

    monkeypatch.setattr(c.allocator, "_expected", allocation)
    monkeypatch.setattr(c.scalar, "apply", scalar)
    check(c.apply(**packet), packet)
    assert [row[0] for row in calls] == ["allocation", "scalar"]
