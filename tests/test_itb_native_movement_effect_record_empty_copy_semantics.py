"""Independent actual-page empty-path record-copy source law.

All expected owner operations and child joins are handwritten from source. The
production apply function is only the actual value under test.
"""

from __future__ import annotations
import ast
import copy
import inspect
from collections import UserDict
import pytest
from src.observatory import native_movement_effect_record_empty_copy_semantics as c
from tests.test_itb_native_movement_empty_string_copy_semantics import (
    independent as string_law,
    assert_strict_packet as strict_equal,
    store,
    read_bytes,
    TRACE as STRING_TRACE,
)

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
COOKIE = 0x00893F28
FLAG_BITS = (0, 2, 4, 6, 7, 9, 11)
ORDINARY_FLAGS = tuple(
    2 | sum(1 << bit for index, bit in enumerate(FLAG_BITS) if selector >> index & 1)
    for selector in range(128)
)
STRINGS = (0x38, 0x50, 0x68, 0x80, 0xA4, 0xE0, 0xF8, 0x118)
RETURNS = (
    0x15BA65,
    0x15BA99,
    0x15BACA,
    0x15BB01,
    0x15BB5C,
    0x15BC19,
    0x15BC50,
    0x15BC93,
)
FIELDS = (
    (0, 4),
    (4, 4),
    (8, 4),
    (12, 4),
    (16, 4),
    (0x14, 1),
    (0x18, 4),
    (0x1C, 4),
    (0x20, 4),
    (0x24, 4),
    (0x28, 4),
    (0x2C, 4),
    (0x30, 1),
    (0x31, 1),
    (0x34, 4),
    (0x98, 4),
    (0x9C, 4),
    (0xA0, 4),
    (0xBC, 4),
    (0xC0, 4),
    (0xC4, 1),
    (0xC5, 1),
    (0xC6, 1),
    (0xC7, 1),
    (0xC8, 4),
    (0xD8, 4),
    (0xDC, 4),
    (0x110, 4),
    (0x114, 4),
    (0x130, 4),
)
KEYS = {
    "source_address",
    "record_address",
    "record_bytes",
    "source_snapshot",
    "registers",
    "xmm",
    "pages",
    "events",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "trace_rvas",
    "boundaries",
}
BOUNDARY_KEYS = {
    "kind",
    "name",
    "index",
    "registers",
    "xmm",
    "pages",
    "events",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
}
OWNER = tuple(int(x, 16) for x in """
15b9b0 15b9b1 15b9b3 15b9b5 15b9ba 15b9c0 15b9c1 15b9c2 15b9c3 15b9c4 15b9c9 15b9cb
15b9cc 15b9cf 15b9d5 15b9d7 15b9da 15b9dd 15b9e0 15b9e2 15b9e5 15b9e7 15b9ea 15b9ed
15b9f0 15b9f3 15b9f6 15b9f9 15b9fc 15b9ff 15ba03 15ba06 15ba09 15ba0c 15ba0f 15ba12
15ba15 15ba18 15ba1b 15ba1e 15ba21 15ba24 15ba27 15ba2a 15ba2e 15ba31 15ba35 15ba38
15ba3b 15ba3e 15ba45 15ba4c 15ba50 15ba56 15ba58 15ba5a 15ba5c 15ba5d 15ba60 15ba65
15ba68 15ba6f 15ba76 15ba79 15ba80 15ba84 15ba8a 15ba8c 15ba8e 15ba90 15ba91 15ba94
15ba99 15ba9c 15baa0 15baa7 15baaa 15bab1 15bab5 15babb 15babd 15babf 15bac1 15bac2
15bac5 15baca 15bad0 15bad4 15badb 15bae1 15bae8 15baec 15baf2 15baf4 15baf6 15baf8
15baf9 15bafc 15bb01 15bb05 15bb0b 15bb11 15bb17 15bb1d 15bb23 15bb29 15bb2f 15bb35
15bb3c 15bb43 15bb47 15bb4d 15bb4f 15bb51 15bb53 15bb54 15bb57 15bb5c 15bb60 15bb66
15bb6c 15bb72 15bb78 15bb7e 15bb85 15bb8b 15bb92 15bb98 15bb9f 15bba5 15bbac 15bbb2
15bbb8 15bbbe 15bbc4 15bbc5 15bbca 15bbce 15bbd4 15bbda 15bbe0 15bbe6 15bbec 15bbf2
15bbf9 15bc00 15bc04 15bc0a 15bc0c 15bc0e 15bc10 15bc11 15bc14 15bc19 15bc1f 15bc23
15bc2a 15bc30 15bc37 15bc3b 15bc41 15bc43 15bc45 15bc47 15bc48 15bc4b 15bc50 15bc54
15bc5a 15bc60 15bc66 15bc6c 15bc72 15bc78 15bc7a 15bc7c 15bc83 15bc8a 15bc8b 15bc8e
15bc93 15bc99 15bc9f 15bca1 15bca4 15bcab 15bcac 15bcad 15bcae 15bcb0 15bcb1
""".split())
ZERO_PATH = tuple(int(x, 16) for x in """
9a8e0 9a8e1 9a8e3 9a8e4 9a8e6 9a8e7 9a8ea 9a8f0 9a8f7 9a8fe 9a901 9a903 9a906 9a907
9ac40 9ac41 9ac43 9ac44 9ac46 9ac47 9ac4a 9ac50 9ac57 9ac5e 9ac60 9ac62 9ac63 9ac65 9ac66 9ac67
9a90c 9a90e 9a927 9a928 9a92a 9a92b 9a92c
""".split())
CALL_CHILD = {
    site: STRING_TRACE
    for site in (
        0x15BA60,
        0x15BA94,
        0x15BAC5,
        0x15BAFC,
        0x15BB57,
        0x15BC14,
        0x15BC4B,
        0x15BC8E,
    )
}
CALL_CHILD[0x15BBC5] = ZERO_PATH
TRACE = tuple(q for pc in OWNER for q in (pc,) + tuple(CALL_CHILD.get(pc, ())))


def inputs(
    *,
    frame=0x30001000,
    source=0x10000200,
    destination=0x10000800,
    profile=0,
    flags=0x246,
    return_address=0x04000000,
):
    spans = (
        (frame - 72, frame + 8),
        (source, source + 308),
        (destination, destination + 308),
        (0, 4),
        (COOKIE, COOKIE + 4),
    )
    mapped = {
        p for a, b in spans for p in range(a & ~4095, ((b - 1) & ~4095) + 1, 4096)
    } | {0x12340000}
    pages = {
        p: bytes((i * 37 + j * 29 + profile * 71) & 255 for j in range(4096))
        for i, p in enumerate(sorted(mapped))
    }
    for at, width in FIELDS:
        store(
            pages,
            source + at,
            (0xC71D293B ^ (at * 0x7654321) ^ (profile * 0x1234567))
            & ((1 << (8 * width)) - 1),
            width,
        )
    for off in STRINGS:
        store(pages, source + off, 0, 1)
        store(pages, source + off + 16, 0)
        store(pages, source + off + 20, 15)
    for at in (0xCC, 0xD0, 0xD4):
        store(pages, source + at, 0)
    store(pages, frame, return_address)
    store(pages, frame + 4, source)
    store(pages, 0, (0x11223344 ^ profile * 0x2468ACE) & 0xFFFFFFFF)
    store(pages, COOKIE, (0x19A51C73 ^ profile * 0x1234567) & 0xFFFFFFFF)
    regs = {
        r: (0xB31AE9F2 + i * 0x1234567 + profile * 0x4321) & 0xFFFFFFFF
        for i, r in enumerate(GPR)
    }
    regs.update(ecx=destination, esp=frame)
    xmms = {
        r: int.from_bytes(
            bytes((i * 31 + j * 17 + profile * 97) & 255 for j in range(16)), "little"
        )
        for i, r in enumerate(XMM)
    }
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmms,
        return_address=return_address,
        entry_flags=flags,
    )


def independent(packet):
    initial = packet["registers"]
    g = initial["esp"]
    f = g - 4
    d = initial["ecx"]
    s = int.from_bytes(read_bytes(packet["pages"], g + 4, 4), "little")
    seh = int.from_bytes(read_bytes(packet["pages"], 0, 4), "little")
    cookie = int.from_bytes(read_bytes(packet["pages"], COOKIE, 4), "little")
    memory = dict(packet["pages"])
    events = []
    boundaries = []
    regs = dict(initial, esi=d, edi=s, ebp=f, esp=g - 32)

    def event(kind, at, value, width=4):
        if kind == "write":
            store(memory, at, value, width)
        else:
            assert int.from_bytes(read_bytes(memory, at, width), "little") == value
        events.append(dict(access=kind, address=at, width=width, value=value))

    def capture(kind, name, index, pc, flags, mask=0x8D5):
        boundaries.append(
            dict(
                kind=kind,
                name=name,
                index=index,
                registers=dict(regs),
                xmm=dict(packet["xmm"]),
                pages=dict(memory),
                events=copy.deepcopy(events),
                flags=flags,
                flag_mask=mask,
                df=0,
                endpoint=0x400000 + pc,
            )
        )

    def fields(rows):
        for off, width in rows:
            value = int.from_bytes(
                read_bytes(packet["pages"], s + off, width), "little"
            )
            event("read", s + off, value, width)
            event("write", d + off, value, width)

    prologue = (
        ("write", g - 4, initial["ebp"]),
        ("write", g - 8, 0xFFFFFFFF),
        ("write", g - 12, 0x007B5837),
        ("read", 0, seh),
        ("write", g - 16, seh),
        ("write", g - 20, d),
        ("write", g - 24, initial["esi"]),
        ("write", g - 28, initial["edi"]),
        ("read", COOKIE, cookie),
        ("write", g - 32, cookie ^ f),
        ("write", 0, g - 16),
        ("write", g - 20, d),
        ("read", g + 4, s),
    )
    for kind, at, value in prologue:
        event(kind, at, value)
    fields(FIELDS[:15])

    def one_string(index):
        nonlocal regs, memory
        off = STRINGS[index]
        q = d + off
        t = s + off
        cframe = g - 48
        if index == 7:
            owner = (
                ("write", g - 36, 0xFFFFFFFF),
                ("write", g - 40, 0),
                ("write", q + 20, 15),
                ("write", q + 16, 0),
                ("write", g - 44, t),
                ("write", q, 0, 1),
            )
        else:
            owner = (
                ("write", q + 20, 15),
                ("write", q + 16, 0),
                ("read", q + 20, 15),
                ("write", g - 36, 0xFFFFFFFF),
                ("write", g - 40, 0),
                ("write", g - 44, t),
                ("write", q, 0, 1),
            )
        for row in owner:
            event(*row)
        event("write", cframe, 0x400000 + RETURNS[index])
        regs.update(
            eax=t if index == 7 else q,
            ecx=q,
            edx=s + 0xF8 if index == 7 else t,
            esp=cframe,
        )
        capture("string", "entry", index, 0x80D0, 0x85)
        # Reuse only the previously handwritten independent seventeen-access law.
        child = string_law(
            dict(
                pages=dict(memory),
                registers=dict(regs),
                xmm=dict(packet["xmm"]),
                return_address=0x400000 + RETURNS[index],
                entry_flags=0x87,
            )
        )
        events.extend(copy.deepcopy(child["events"]))
        memory = dict(child["pages"])
        regs = dict(child["registers"])
        capture("string", "return", index, RETURNS[index], 0x85)

    one_string(0)
    for index, state in ((1, 0), (2, 1), (3, 2)):
        event("write", g - 8, state, 4 if index == 1 else 1)
        one_string(index)
    event("write", g - 8, 3, 1)
    fields(FIELDS[15:18])
    one_string(4)
    event("write", g - 8, 4, 1)
    fields(FIELDS[18:25])
    j, h, p = s + 0xCC, d + 0xCC, g - 40
    event("write", g - 36, j)
    event("write", p, 0x0055BBCA)
    regs.update(eax=j, ecx=h, edx=s + 0xA4, esp=p)
    capture("path", "entry", 0, 0x9A8E0, 0x85)
    path_prefix = (
        ("write", p - 4, f),
        ("write", p - 8, d),
        ("write", p - 12, s),
        ("read", p + 4, j),
        ("write", h, 0),
        ("write", h + 4, 0),
        ("write", h + 8, 0),
        ("read", j + 4, 0),
        ("read", j, 0),
        ("write", p - 16, 0),
        ("write", p - 20, 0x0049A90C),
    )
    for row in path_prefix:
        event(*row)
    regs.update(eax=0, esi=h, edi=j, ebp=p - 4, esp=p - 20)
    capture("reserve", "entry", 0, 0x9AC40, 0x44, 0xC5)
    reserve = (
        ("write", p - 24, p - 4),
        ("write", p - 28, h),
        ("write", p - 32, j),
        ("read", p - 16, 0),
        ("write", h, 0),
        ("write", h + 4, 0),
        ("write", h + 8, 0),
        ("read", p - 32, j),
        ("read", p - 28, h),
        ("read", p - 24, p - 4),
        ("read", p - 20, 0x0049A90C),
    )
    for row in reserve:
        event(*row)
    regs.update(esp=p - 12)
    capture("reserve", "return", 0, 0x9A90C, 0x44, 0x8C5)
    for at, value in ((p - 12, s), (p - 8, d), (p - 4, f), (p, 0x0055BBCA)):
        event("read", at, value)
    regs.update(eax=h, esi=d, edi=s, ebp=f, esp=g - 32)
    capture("path", "return", 0, 0x15BBCA, 0x44, 0x8C5)
    event("write", g - 8, 5, 1)
    fields(FIELDS[25:27])
    one_string(5)
    event("write", g - 8, 6, 1)
    one_string(6)
    event("write", g - 8, 7, 1)
    fields(FIELDS[27:29])
    one_string(7)
    fields(FIELDS[29:])
    event("read", g - 16, seh)
    event("write", 0, seh)
    for at, value in (
        (g - 32, cookie ^ f),
        (g - 28, initial["edi"]),
        (g - 24, initial["esi"]),
        (g - 4, initial["ebp"]),
        (g, packet["return_address"]),
    ):
        event("read", at, value)
    # Complete final pages use separate source byte/last-stack-writer equations.
    final = dict(packet["pages"])
    record = bytearray(read_bytes(final, d, 308))
    for off, width in FIELDS:
        record[off : off + width] = read_bytes(packet["pages"], s + off, width)
    for off in STRINGS:
        record[off] = 0
        record[off + 16 : off + 20] = bytes(4)
        record[off + 20 : off + 24] = (15).to_bytes(4, "little")
    record[0xCC:0xD8] = bytes(12)
    for index, byte in enumerate(record):
        store(final, d + index, byte, 1)
    stack_slots = {
        4: initial["ebp"],
        8: 7,
        12: 0x007B5837,
        16: seh,
        20: d,
        24: initial["esi"],
        28: initial["edi"],
        32: cookie ^ f,
        36: 0xFFFFFFFF,
        40: 0,
        44: s + 0x118,
        48: 0x0055BC93,
        52: f,
        56: initial["ebx"],
        60: d,
        64: s,
        68: h,
        72: j,
    }
    for offset, value in stack_slots.items():
        store(final, g - offset, value)
    store(final, 0, seh)
    strict_equal(memory, final)
    return dict(
        source_address=s,
        record_address=d,
        record_bytes=bytes(record),
        source_snapshot=read_bytes(packet["pages"], s, 308),
        registers=dict(initial, eax=d, ecx=cookie ^ f, edx=s + 0xF8, esp=g + 8),
        xmm=dict(packet["xmm"]),
        pages=final,
        events=events,
        flags=0x85,
        flag_mask=0x8D5,
        df=0,
        endpoint=packet["return_address"],
        trace_rvas=[f"0x{pc:08x}" for pc in TRACE],
        boundaries=boundaries,
    )


def check(actual, packet):
    wanted = independent(packet)
    strict_equal(actual, wanted)
    assert set(actual) == KEYS and len(KEYS) == 14
    assert (
        len(actual["events"]) == 315
        and len(actual["trace_rvas"]) == 492
        and len(actual["boundaries"]) == 20
    )
    assert len(OWNER) == 191 and len(ZERO_PATH) == 37 and len(STRING_TRACE) == 33
    g = packet["registers"]["esp"]
    s = wanted["source_address"]
    d = wanted["record_address"]
    writes = {at + i for at, width in FIELDS for i in range(width)}
    for off in STRINGS:
        writes.update({off, *range(off + 16, off + 24)})
    writes.update(range(0xCC, 0xD8))
    assert len(writes) == 183 and 308 - len(writes) == 125
    old = read_bytes(packet["pages"], d, 308)
    assert all(
        actual["record_bytes"][i] == old[i] for i in range(308) if i not in writes
    )
    assert read_bytes(actual["pages"], s, 308) == read_bytes(packet["pages"], s, 308)
    assert read_bytes(actual["pages"], g, 8) == read_bytes(packet["pages"], g, 8)
    assert {
        row["address"] + i
        for row in actual["events"]
        if row["access"] == "write"
        for i in range(row["width"])
    } == set(range(g - 72, g)) | set(range(4)) | {d + i for i in writes}
    prefixes = [len(b["events"]) for b in actual["boundaries"]]
    assert prefixes == [
        51,
        68,
        77,
        94,
        103,
        120,
        129,
        146,
        161,
        178,
        195,
        206,
        217,
        221,
        234,
        251,
        260,
        277,
        289,
        306,
    ]
    for boundary in actual["boundaries"]:
        assert set(boundary) == BOUNDARY_KEYS
    assert [b["flags"] for b in actual["boundaries"][10:14]] == [0x85, 0x44, 0x44, 0x44]
    assert [b["flag_mask"] for b in actual["boundaries"][10:14]] == [
        0x8D5,
        0xC5,
        0x8C5,
        0x8C5,
    ]
    source_reads = {
        row["address"] for row in actual["events"] if row["access"] == "read"
    }
    assert s + 0xD4 not in source_reads
    for off in STRINGS:
        assert s + off not in source_reads and s + off + 20 not in source_reads
    excluded = {0x8A920, 0x8ABA0, 0x3574CA, 0x3435D9, 0x8270, 0x3703E0}
    assert not excluded.intersection(int(pc, 16) for pc in actual["trace_rvas"])


@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize("profile", range(3))
@pytest.mark.parametrize("order", ("before", "after"))
def test_full_actual_pages_owner_eight_strings_zero_path_and_20_boundaries(
    alignment, profile, order
):
    s, d = (0x10000200 + alignment, 0x10000800 + alignment)
    if order == "after":
        s, d = d, s
    packet = inputs(
        frame=0x30001000 + alignment, source=s, destination=d, profile=profile
    )
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    strict_equal(packet, before)


@pytest.mark.parametrize("flags", ORDINARY_FLAGS)
def test_every_ordinary_flag_combination(flags):
    packet = inputs(flags=flags)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "frame,source,dest",
    [
        (0x3000103F, 0x10000FF0, 0x10002FF8),
        (0x30000FFD, 0x10002003, 0x10004FC0),
        (0x30001000, 0x7FFFFFF0, 0x90000FFD),
        (0x30001000, 0x90000FFD, 0x7FFFFFF0),
        (0xFFFFFFF7, 0x10000010, 0x10000803),
        (76, 0x10000010, 0x10000803),
        (0x30001000, 0xFFFFFECB, 0x10000803),
        (0x30001000, 0x10000803, 0xFFFFFECB),
        (0x30001000, 0x10000200, 0x10000334),
        (0x30001000, 0x10000334, 0x10000200),
    ],
)
def test_independent_cross_page_signed_extreme_and_adjacent_geometry(
    frame, source, dest
):
    packet = inputs(frame=frame, source=source, destination=dest)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("value", (0, 0xFFFFFFFF, 0x80000000))
def test_arbitrary_nonaddress_gpr_xmm_and_scalar_bits(value):
    packet = inputs()
    for key in GPR:
        if key not in ("ecx", "esp"):
            packet["registers"][key] = value
    for key in XMM:
        packet["xmm"][key] = (
            0 if value == 0 else ((value << 96) | (value << 64) | (value << 32) | value)
        )
    s = int.from_bytes(
        read_bytes(packet["pages"], packet["registers"]["esp"] + 4, 4), "little"
    )
    for off, width in FIELDS:
        store(packet["pages"], s + off, value & ((1 << (width * 8)) - 1), width)
    check(c.apply(**packet), packet)


def test_all_source_and_destination_padding_are_arbitrary_and_preserved():
    packet = inputs()
    g = packet["registers"]["esp"]
    s = int.from_bytes(read_bytes(packet["pages"], g + 4, 4), "little")
    d = packet["registers"]["ecx"]
    for off in STRINGS:
        for index in range(1, 16):
            store(packet["pages"], s + off + index, (index * 23 + off) & 255, 1)
    for index in range(308):
        store(packet["pages"], d + index, (index * 43 + 11) & 255, 1)
    check(c.apply(**packet), packet)


def test_all_output_input_boundary_detachment():
    packet = inputs()
    before = copy.deepcopy(packet)
    first = c.apply(**packet)
    second = c.apply(**packet)
    first["pages"].clear()
    first["registers"].clear()
    first["xmm"].clear()
    first["events"].clear()
    for b in first["boundaries"]:
        b["pages"].clear()
        b["registers"].clear()
        b["events"].clear()
    check(second, packet)
    strict_equal(packet, before)
    # Boundary prefixes must be detached from one another and from the final packet.
    third = c.apply(**packet)
    saved = copy.deepcopy(third)
    third["boundaries"][0]["events"].clear()
    third["boundaries"][0]["pages"].clear()
    strict_equal(third["boundaries"][1:], saved["boundaries"][1:])
    strict_equal(third["pages"], saved["pages"])


@pytest.mark.parametrize("bit", [b for b in range(32) if not (0xAD7 >> b) & 1])
def test_forbidden_reserved_control_and_df_flags(bit):
    packet = inputs(flags=0x246 | (1 << bit))
    with pytest.raises(c.EmptyRecordCopyError):
        c.apply(**packet)


@pytest.mark.parametrize("flags", (0, 4, 0xAD5, 0x200, True, 2.0, -1, 2**32))
def test_required_bit1_and_typed_flag_guard(flags):
    packet = inputs(flags=flags)
    with pytest.raises(c.EmptyRecordCopyError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "group,key,value",
    [
        ("registers", "eax", True),
        ("registers", "esp", False),
        ("registers", "ecx", -1),
        ("registers", "edx", 2**32),
        ("registers", "ebp", 1.0),
        ("xmm", "xmm0", True),
        ("xmm", "xmm7", -1),
        ("xmm", "xmm6", 2**128),
        ("xmm", "xmm5", 1.0),
    ],
)
def test_full_gpr_xmm_scalar_type_bounds(group, key, value):
    packet = inputs()
    packet[group][key] = value
    with pytest.raises(c.EmptyRecordCopyError):
        c.apply(**packet)


@pytest.mark.parametrize("group", ("registers", "xmm"))
@pytest.mark.parametrize("kind", ("extra", "missing", "mapping", "key_subclass"))
def test_closed_typed_register_mappings(group, kind):
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
    with pytest.raises(c.EmptyRecordCopyError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    (
        "empty",
        "mapping",
        "address_bool",
        "address_subclass",
        "address_unaligned",
        "mutable",
        "short",
        "frame",
        "source",
        "destination",
        "fs",
        "cookie",
    ),
)
def test_immutable_complete_typed_page_schema(kind):
    packet = inputs(destination=0x10001800)
    pages = packet["pages"]
    if kind == "empty":
        packet["pages"] = {}
    elif kind == "mapping":
        packet["pages"] = UserDict(pages)
    elif kind == "address_bool":
        pages[False] = pages.pop(0)
    elif kind == "address_subclass":

        class Address(int):
            pass

        packet["pages"] = {Address(k): v for k, v in pages.items()}
    elif kind == "address_unaligned":
        pages[1] = pages.pop(0)
    elif kind == "mutable":
        pages[0] = bytearray(pages[0])
    elif kind == "short":
        pages[0] = pages[0][:-1]
    else:
        page = {
            "frame": 0x30001000,
            "source": 0x10000000,
            "destination": 0x10001000,
            "fs": 0,
            "cookie": 0x00893000,
        }[kind]
        pages.pop(page)
    before = copy.deepcopy(packet)
    with pytest.raises(c.EmptyRecordCopyError):
        c.apply(**packet)
    strict_equal(packet, before)


@pytest.mark.parametrize(
    "kind",
    (
        "caller",
        "source_null",
        "destination_null",
        "size",
        "capacity",
        "terminator",
        "path_begin",
        "path_end",
        "path_cap",
    ),
)
def test_installed_caller_empty_strings_and_path_premises(kind):
    packet = inputs()
    g = packet["registers"]["esp"]
    s = 0x10000200
    if kind == "caller":
        store(packet["pages"], g, 0x04000001)
    elif kind == "source_null":
        store(packet["pages"], g + 4, 0)
    elif kind == "destination_null":
        packet["registers"]["ecx"] = 0
    elif kind == "size":
        store(packet["pages"], s + 0x38 + 16, 1)
    elif kind == "capacity":
        store(packet["pages"], s + 0x118 + 20, 16)
    elif kind == "terminator":
        store(packet["pages"], s + 0xF8, 1, 1)
    else:
        store(
            packet["pages"],
            s + {"path_begin": 0xCC, "path_end": 0xD0, "path_cap": 0xD4}[kind],
            1,
        )
    before = copy.deepcopy(packet)
    with pytest.raises(c.EmptyRecordCopyError):
        c.apply(**packet)
    strict_equal(packet, before)


@pytest.mark.parametrize(
    "frame,source,dest",
    [
        (71, 0x10000200, 0x10000800),
        (0xFFFFFFF8, 0x10000200, 0x10000800),
        (0x30001000, 0xFFFFFECC, 0x10000800),
        (0x30001000, 0x10000200, 0xFFFFFECC),
        (0x30001000, 0x10000200, 0x10000333),
        (0x30001000, 0x10000200, 0x10000200),
        (0x30001000, 0x30000FFF, 0x10000800),
        (0x30001000, 0x10000200, 0x30001007),
        (0x30001000, 0x00893F28, 0x10000800),
        (0x30001000, 1, 0x10000800),
        (0x30001000, 0x004080D0, 0x10000800),
        (0x30001000, 0x10000200, 0x0055B9B0),
    ],
)
def test_disjoint_nowrap_global_code_and_frame_domains(frame, source, dest):
    packet = inputs(frame=frame, source=source, destination=dest)
    before = copy.deepcopy(packet)
    with pytest.raises(c.EmptyRecordCopyError):
        c.apply(**packet)
    strict_equal(packet, before)


@pytest.mark.parametrize(
    "ret",
    (
        True,
        1.0,
        0,
        -1,
        2**32,
        0x30001000,
        0x10000200,
        0x10000800,
        0x004080D0,
        0x0049A8E0,
        0x0055B9B0,
        0x00893F28,
    ),
)
def test_return_type_and_disjoint_selected_targets(ret):
    packet = inputs()
    packet["return_address"] = ret
    if type(ret) is int and 0 <= ret <= 0xFFFFFFFF:
        store(packet["pages"], 0x30001000, ret)
    with pytest.raises(c.EmptyRecordCopyError):
        c.apply(**packet)


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
        "df",
        "endpoint",
    ),
)
def test_complete_independent_11_field_string_join_rejects_child_forgeries(
    monkeypatch, kind
):
    def forged(**kwargs):
        result = string_law(kwargs)
        if kind == "schema":
            result["opaque"] = 0
        elif kind == "gpr_bool":
            result["registers"]["ecx"] = False
        elif kind == "xmm":
            result["xmm"]["xmm7"] ^= 1
        elif kind == "pages":
            store(result["pages"], 0x12340000, 1)
        elif kind == "source":
            result["source_address"] += 1
        elif kind == "events":
            result["events"][8]["value"] ^= 1
        elif kind == "trace":
            result["trace_rvas"][0] = "0x00008152"
        elif kind == "flags":
            result["flags"] ^= 1
        elif kind == "df":
            result["df"] = False
        else:
            result["endpoint"] += 1
        return result

    monkeypatch.setattr(c.string, "apply", forged)
    packet = inputs()
    before = copy.deepcopy(packet)
    with pytest.raises(c.EmptyRecordCopyError, match="primitive differs"):
        c.apply(**packet)
    strict_equal(packet, before)


def test_exact_eight_real_child_calls_and_source_only_dependencies(monkeypatch):
    called = []
    original = c.string.apply

    def tracked(**kwargs):
        called.append(copy.deepcopy(kwargs))
        return original(**kwargs)

    monkeypatch.setattr(c.string, "apply", tracked)
    packet = inputs()
    check(c.apply(**packet), packet)
    assert len(called) == 8
    for index, child in enumerate(called):
        assert child["return_address"] == 0x400000 + RETURNS[index]
        assert child["registers"]["esp"] == packet["registers"]["esp"] - 48
        assert child["registers"]["eax"] == (
            0x10000200 + 0x118 if index == 7 else 0x10000800 + STRINGS[index]
        )
        assert child["registers"]["edx"] == 0x10000200 + (
            0xF8 if index == 7 else STRINGS[index]
        )
    source = inspect.getsource(c)
    tree = ast.parse(source)
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imports == {"__future__", "src.observatory"}
    assert (
        "unicorn" not in source
        and "capstone" not in source
        and "subprocess" not in source
    )
    assert not any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id in ("open", "eval", "exec")
        for n in ast.walk(tree)
    )


def test_selected_body_and_receipt_identity_contract():
    assert c.BODY_PINS == {
        0x15B9B0: (
            772,
            "3846fdb1ca2ebc1b4b6e83a64994f82d4907938345ff0d856c9bbea690957fc6",
        ),
        0x80D0: (
            288,
            "062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333",
        ),
        0x9A8E0: (
            79,
            "4359ecaf051506bce97afe182b66c453ca8d13ac4091d72a810f9df43d14d2e0",
        ),
        0x9AC40: (
            87,
            "29a0428ed018a85e4e0a76f283f10040cf9e084f49bee5706b58766b570cb9d1",
        ),
    }
    assert len(c.SOURCE_PINS) == 4
    assert c.SOURCE_PINS["empty_string_copy"] == (
        "pe_native_movement_empty_string_copy_conformance",
        "c3d9d8598d7aa922157397a27a58aeabf86732e9bb620625d602481dd90c18b1",
    )
    assert len(set(ORDINARY_FLAGS)) == 128
    assert all(flags & 2 and flags & ~0xAD7 == 0 for flags in ORDINARY_FLAGS)
