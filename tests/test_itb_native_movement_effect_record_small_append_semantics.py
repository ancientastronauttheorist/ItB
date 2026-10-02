"""Independent external-source, existing-capacity movement record append law.

Expected parent equations are handwritten from the selected 0x259F00 branch;
the lower record-copy witness is an independent handwritten test oracle.
"""

from __future__ import annotations

import ast
import copy
import inspect
from collections import UserDict
import pytest
from tests import (
    test_itb_native_movement_effect_record_append2_semantics as older_append,
)
from src.observatory import native_movement_effect_record_small_append_semantics as c
from tests import (
    test_itb_native_movement_effect_record_small_copy_semantics as record_law,
)

store, read_bytes, strict_equal = (
    record_law.store,
    record_law.read_bytes,
    record_law.strict_equal,
)
GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
COOKIE = 0x00893F28
FLAG_BITS = (0, 2, 4, 6, 7, 9, 11)
FLAGS = tuple(
    2 | sum(1 << bit for i, bit in enumerate(FLAG_BITS) if selector >> i & 1)
    for selector in range(128)
)
PREFIX = tuple(int(w, 16) for w in """
259f00 259f01 259f03 259f05 259f0a 259f10 259f11 259f12 259f13 259f14
259f19 259f1b 259f1c 259f1f 259f25 259f27 259f2a 259f2d 259f2f
259f76 259f79 259f83 259f86 259f89 259f8c 259f93 259f95 259f97 259f98
""".split())
SUFFIX = tuple(
    int(w, 16)
    for w in "259f9d 259fa4 259fa7 259fae 259faf 259fb0 259fb1 259fb3 259fb4".split()
)
KEYS = {
    "receiver_address",
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
    "record_packet",
}


def inputs(
    count=2,
    *,
    frame=0x30001000,
    receiver=0x0FFFFFD0,
    source=0x10002FF0,
    insertion=0x10000FF0,
    path_source=0x06002803,
    allocation_result=0x06001007,
    previous=2,
    spare=1,
    profile=0,
    flags=0x246,
    return_address=0x04000000,
    capacity=0xFFFFFFFF,
):
    packet = record_law.inputs(
        count,
        capacity=capacity,
        frame=frame - 40,
        source=source,
        destination=insertion,
        path_source=path_source,
        allocation_result=allocation_result,
        profile=profile,
        flags=flags,
        return_address=0x00659F9D,
    )
    begin = insertion - previous * 308
    capacity = insertion + (spare + 1) * 308
    spans = ((receiver, receiver + 12), (begin, capacity), (frame, frame + 8))
    for start, end in spans:
        for base in range(start & ~4095, ((end - 1) & ~4095) + 1, 4096):
            if base not in packet["pages"]:
                packet["pages"][base] = bytes(
                    (j * 43 + (base >> 12) * 31 + profile * 97) & 255
                    for j in range(4096)
                )
    for at, value in (
        (frame, return_address),
        (frame + 4, source),
        (receiver, begin),
        (receiver + 4, insertion),
        (receiver + 8, capacity),
    ):
        store(packet["pages"], at, value)
    packet["registers"].update(esp=frame, ecx=receiver)
    packet["return_address"] = return_address
    return packet


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


def independent(packet):
    initial = packet["registers"]
    g, h = initial["esp"], initial["ecx"]
    source = int.from_bytes(read_bytes(packet["pages"], g + 4, 4), "little")
    insertion = int.from_bytes(read_bytes(packet["pages"], h + 4, 4), "little")
    capacity = int.from_bytes(read_bytes(packet["pages"], h + 8, 4), "little")
    seh = int.from_bytes(read_bytes(packet["pages"], 0, 4), "little")
    cookie = int.from_bytes(read_bytes(packet["pages"], COOKIE, 4), "little")
    pages = dict(packet["pages"])
    events = []
    boundaries = []
    regs = dict(initial)

    def event(access, address, value):
        if access == "write":
            store(pages, address, value)
        else:
            assert int.from_bytes(read_bytes(pages, address, 4), "little") == value
        events.append(dict(access=access, address=address, width=4, value=value))

    def capture(name, flags, mask):
        boundaries.append(
            dict(
                kind="record",
                name=name,
                index=0,
                registers=dict(regs),
                xmm=dict(packet["xmm"]),
                pages=dict(pages),
                events=copy.deepcopy(events),
                flags=flags,
                flag_mask=mask,
                df=0,
                endpoint=0x0055B9B0 if name == "entry" else 0x00659F9D,
            )
        )

    prefix = (
        ("write", g - 4, initial["ebp"]),
        ("write", g - 8, 0xFFFFFFFF),
        ("write", g - 12, 0x007A19F2),
        ("read", 0, seh),
        ("write", g - 16, seh),
        ("write", g - 20, h),
        ("write", g - 24, initial["esi"]),
        ("write", g - 28, initial["edi"]),
        ("read", COOKIE, cookie),
        ("write", g - 32, cookie ^ (g - 4)),
        ("write", 0, g - 16),
        ("read", h + 4, insertion),
        ("read", g + 4, source),
        ("read", h + 8, capacity),
        ("read", h + 4, insertion),
        ("write", g + 4, insertion),
        ("write", g - 20, insertion),
        ("write", g - 8, 1),
        ("write", g - 36, source),
        ("write", g - 40, 0x00659F9D),
    )
    for row in prefix:
        event(*row)
    regs.update(eax=g - 16, ecx=insertion, esi=h, edi=source, ebp=g - 4, esp=g - 40)
    status = (4 if (insertion & 255).bit_count() % 2 == 0 else 0) | (
        0x80 if insertion & 0x80000000 else 0
    )
    capture("entry", status, 0x8C5)
    child_input = dict(
        pages=dict(pages),
        registers=dict(regs),
        xmm=dict(packet["xmm"]),
        return_address=0x00659F9D,
        entry_flags=(packet["entry_flags"] & ~0x8D5) | status,
        allocation_result=packet["allocation_result"],
    )
    child = record_law.independent(child_input)
    prefix_events = copy.deepcopy(events)
    for state in child["boundaries"]:
        row = copy.deepcopy(state)
        row["events"] = prefix_events + row["events"]
        boundaries.append(row)
    pages = dict(child["pages"])
    events.extend(copy.deepcopy(child["events"]))
    regs = dict(child["registers"])
    capture("return", 0x85, 0x8D5)
    event("read", h + 4, insertion)
    event("write", h + 4, insertion + 308)
    event("read", g - 16, seh)
    event("write", 0, seh)
    for at, value in (
        (g - 32, cookie ^ (g - 4)),
        (g - 28, initial["edi"]),
        (g - 24, initial["esi"]),
        (g - 4, initial["ebp"]),
        (g, packet["return_address"]),
    ):
        event("read", at, value)
    # Independent lower record pages already use field/padding/deep-stack
    # equations, not an event replay. Apply only the two outer last writers.
    final = dict(child["pages"])
    store(final, h + 4, insertion + 308)
    store(final, 0, seh)
    strict_equal(pages, final)
    return dict(
        receiver_address=h,
        source_address=source,
        record_address=insertion,
        record_bytes=read_bytes(final, insertion, 308),
        source_snapshot=read_bytes(packet["pages"], source, 308),
        registers=dict(
            initial, eax=insertion, ecx=cookie ^ (g - 4), edx=source + 0xF8, esp=g + 8
        ),
        xmm=dict(packet["xmm"]),
        pages=final,
        events=events,
        flags=add_flags(insertion, 308),
        flag_mask=0x8D5,
        df=0,
        endpoint=packet["return_address"],
        trace_rvas=[f"0x{pc:08x}" for pc in PREFIX]
        + child["trace_rvas"]
        + [f"0x{pc:08x}" for pc in SUFFIX],
        boundaries=boundaries,
        record_packet=copy.deepcopy(child),
    )


def check(actual, packet):
    wanted = independent(packet)
    strict_equal(actual, wanted)
    assert set(actual) == KEYS and len(KEYS) == 16
    source = int.from_bytes(
        read_bytes(packet["pages"], packet["registers"]["esp"] + 4, 4), "little"
    )
    begin = int.from_bytes(read_bytes(packet["pages"], source + 0xCC, 4), "little")
    finish = int.from_bytes(read_bytes(packet["pages"], source + 0xD0, 4), "little")
    count = (finish - begin) // 8
    assert len(PREFIX) == 29 and len(SUFFIX) == 9
    assert len(actual["trace_rvas"]) == (609 + 10 * count if count else 530)
    assert len(actual["events"]) == (393 + 4 * count if count else 344)
    assert len(actual["boundaries"]) == (25 if count else 22)
    common = [20, 71, 88, 97, 114, 123, 140, 149, 166, 181, 198, 215, 226]
    suffix = [
        303 + 4 * count,
        320 + 4 * count,
        329 + 4 * count,
        346 + 4 * count,
        358 + 4 * count,
        375 + 4 * count,
        384 + 4 * count,
    ]
    counts = (
        common + [235, 262, 270, 279, 285 + 4 * count] + suffix
        if count
        else common + [237, 241, 254, 271, 280, 297, 309, 326, 335]
    )
    assert [len(row["events"]) for row in actual["boundaries"]] == counts
    assert all(set(row) == record_law.BOUNDARY_KEYS for row in actual["boundaries"])
    assert actual["boundaries"][0]["flags"] == (
        (4 if (actual["record_address"] & 255).bit_count() % 2 == 0 else 0)
        | (0x80 if actual["record_address"] & 0x80000000 else 0)
    )
    assert actual["boundaries"][0]["flag_mask"] == 0x8C5
    g = packet["registers"]["esp"]
    h = wanted["receiver_address"]
    r = wanted["source_address"]
    at = wanted["record_address"]
    b = int.from_bytes(read_bytes(packet["pages"], h, 4), "little")
    end = int.from_bytes(read_bytes(packet["pages"], h + 8, 4), "little")
    assert read_bytes(actual["pages"], g, 4) == read_bytes(packet["pages"], g, 4)
    assert read_bytes(actual["pages"], g + 4, 4) == at.to_bytes(4, "little")
    assert read_bytes(actual["pages"], h, 4) == b.to_bytes(4, "little")
    assert read_bytes(actual["pages"], h + 4, 4) == (at + 308).to_bytes(4, "little")
    assert read_bytes(actual["pages"], h + 8, 4) == end.to_bytes(4, "little")
    assert read_bytes(actual["pages"], b, at - b) == read_bytes(
        packet["pages"], b, at - b
    )
    # A source in reserved capacity is permitted by this external branch;
    # source and spare remain preserved except the insertion record itself.
    assert read_bytes(actual["pages"], at + 308, end - at - 308) == read_bytes(
        packet["pages"], at + 308, end - at - 308
    )
    assert read_bytes(actual["pages"], r, 308) == read_bytes(packet["pages"], r, 308)
    assert len(actual["record_packet"]["events"]) == (364 + 4 * count if count else 315)
    if count:
        assert (
            actual["record_packet"]["path_packet"]["imported"]["entry_esp"] == g - 168
        )
        assert actual["record_packet"]["path_packet"]["imported"]["words"] == [
            0x789463,
            0x12345678,
            0,
            8 * count,
        ]
    else:
        assert actual["record_packet"]["path_packet"]["imported"] is None
    assert actual["flags"] == add_flags(at, 308)
    assert actual["registers"]["eax"] == at and actual["registers"]["edx"] == r + 0xF8
    assert actual["registers"]["esp"] == g + 8
    offsets = {
        offset + i for offset, width in record_law.FIELDS for i in range(width)
    } | set(range(0xCC, 0xD8))
    for offset in record_law.STRINGS:
        offsets.update({offset, *range(offset + 16, offset + 24)})
    assert len(offsets) == 183
    written = {
        row["address"] + i
        for row in actual["events"]
        if row["access"] == "write"
        for i in range(row["width"])
    }
    allocation = packet["allocation_result"]
    assert written == (
        set(range(g - (168 if count else 112), g))
        | set(range(g + 4, g + 8))
        | set(range(h + 4, h + 8))
        | set(range(4))
        | {at + i for i in offsets}
        | set(range(allocation, allocation + 8 * count))
    )


@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize("profile", range(3))
@pytest.mark.parametrize("previous,spare", ((0, 0), (2, 1)))
def test_complete_actual_external_append_25_boundaries_and_preserved_capacity(
    alignment, profile, previous, spare
):
    packet = inputs(
        frame=0x30001000 + alignment,
        receiver=0x0FFFFFD0 + alignment,
        source=0x10002FF0 + alignment,
        insertion=0x10000FF0 + alignment,
        path_source=0x06002800 + alignment,
        allocation_result=0x06001000 + alignment,
        previous=previous,
        spare=spare,
        profile=profile,
    )
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    strict_equal(packet, before)


@pytest.mark.parametrize("flags", FLAGS)
@pytest.mark.parametrize("count", (0, 511))
def test_all_128_ordinary_flags(flags, count):
    packet = inputs(count, flags=flags)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "g,h,r,at,o,a",
    [
        (0x30000FFD, 0x0FFFFFFD, 0x10005FFF, 0x10000FFF, 0x20000FF8, 0x06000FF8),
        (0xFFFFFFF7, 0x100005FF, 0x90000FF8, 0x7FFFFFF0, 0x20000FF8, 0x06003FF0),
        (0x30001000, 0x100005FF, 0x90000FF8, 0x7FFFFFF0, 0xFFFFFFEF, 0x06003FF0),
        (0x30001000, 0x10000503, 0xFFFFFECB, 0x90000FF8, 0x7FFFFFF8, 0x06000000),
        (0x30001000, 0x10000503, 0x10002134, 0x10002000, 0x20000FF8, 0x06001003),
        (0x30001000, 0x30001800, 0x30001C00, 0x30001A00, 0x30001E00, 0x06001000),
        (172, 0x10000503, 0x10005FF0, 0x10000FF0, 0x20000FF8, 0x06001003),
    ],
)
def test_cross_page_signed_edges_adjacency_and_stack_page_records(g, h, r, at, o, a):
    packet = inputs(
        frame=g,
        receiver=h,
        source=r,
        insertion=at,
        path_source=o,
        allocation_result=a,
        previous=0,
        spare=0,
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("value", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_arbitrary_nonaddress_gpr_xmm_and_source_capacity(value):
    packet = inputs()
    for name in GPR:
        if name not in ("esp", "ecx"):
            packet["registers"][name] = value
    packet["xmm"] = {
        name: (value << 96) | (value << 64) | (value << 32) | value for name in XMM
    }
    store(packet["pages"], 0x10002FF0 + 0xD4, value)
    check(c.apply(**packet), packet)


def test_unread_padding_source_inline_capacity_and_record_padding_preserved():
    packet = inputs()
    source = 0x10002FF0
    at = 0x10000FF0
    written = {
        offset + i for offset, width in record_law.FIELDS for i in range(width)
    } | set(range(0xCC, 0xD8))
    for off in record_law.STRINGS:
        written.update({off, *range(off + 16, off + 24)})
    for i in range(308):
        if i not in written:
            store(packet["pages"], source + i, (i * 37 + 17) & 255, 1)
            store(packet["pages"], at + i, (i * 29 + 53) & 255, 1)
    check(c.apply(**packet), packet)


def test_input_and_nested_result_detachment():
    packet = inputs()
    before = copy.deepcopy(packet)
    wanted = independent(packet)
    actual = c.apply(**packet)
    actual["pages"][0x12340000] = bytes(4096)
    actual["events"][0]["value"] ^= 1
    actual["registers"]["eax"] ^= 1
    actual["xmm"]["xmm7"] ^= 1
    actual["boundaries"][0]["pages"][0x12340000] = bytes(4096)
    actual["record_packet"]["path_packet"]["allocation_packet"]["relation"][
        "request"
    ] = 0
    strict_equal(packet, before)
    strict_equal(c.apply(**packet), wanted)


@pytest.mark.parametrize(
    "bit", [bit for bit in range(32) if bit not in (0, 1, 2, 4, 6, 7, 9, 11)]
)
def test_each_forbidden_flag(bit):
    packet = inputs()
    packet["entry_flags"] = 2 | (1 << bit)
    with pytest.raises(c.SmallRecordAppendError):
        c.apply(**packet)


@pytest.mark.parametrize("word", (0, 4, True, 2.0, -1, 2**32, None))
def test_bit1_and_strict_flag_type(word):
    packet = inputs()
    packet["entry_flags"] = word
    with pytest.raises(c.SmallRecordAppendError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "group,key,value",
    [
        ("registers", "eax", True),
        ("registers", "esp", float(0x30001000)),
        ("registers", "edx", -1),
        ("registers", "ebp", 2**32),
        ("xmm", "xmm0", False),
        ("xmm", "xmm7", 0.0),
        ("xmm", "xmm3", -1),
        ("xmm", "xmm5", 2**128),
    ],
)
def test_strict_all_eight_gpr_and_xmm(group, key, value):
    packet = inputs()
    packet[group][key] = value
    with pytest.raises(c.SmallRecordAppendError):
        c.apply(**packet)


@pytest.mark.parametrize("group", ("registers", "xmm"))
@pytest.mark.parametrize("kind", ("missing", "extra", "mapping", "str_alias"))
def test_closed_typed_state_mappings(group, kind):
    packet = inputs()
    name = GPR[0] if group == "registers" else XMM[0]
    if kind == "missing":
        del packet[group][name]
    elif kind == "extra":
        packet[group]["other"] = 0
    elif kind == "mapping":
        packet[group] = UserDict(packet[group])
    else:

        class Alias(str):
            pass

        value = packet[group].pop(name)
        packet[group][Alias(name)] = value
    with pytest.raises(c.SmallRecordAppendError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    (
        "mapping",
        "empty",
        "short",
        "mutable",
        "bool_key",
        "float_key",
        "negative_key",
        "unaligned_key",
        "large_key",
    ),
)
def test_typed_immutable_page_schema(kind):
    packet = inputs()
    pages = packet["pages"]
    if kind == "mapping":
        packet["pages"] = UserDict(pages)
    elif kind == "empty":
        packet["pages"] = {}
    elif kind == "short":
        pages[0] = pages[0][:-1]
    elif kind == "mutable":
        pages[0] = bytearray(pages[0])
    elif kind == "bool_key":
        value = pages.pop(0)
        pages[False] = value
    elif kind == "float_key":
        value = pages.pop(0)
        pages[0.0] = value
    elif kind == "negative_key":
        pages[-4096] = bytes(4096)
    elif kind == "unaligned_key":
        pages[1] = bytes(4096)
    else:
        pages[2**32] = bytes(4096)
    with pytest.raises(c.SmallRecordAppendError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    (
        "caller",
        "begin_null",
        "begin_after_end",
        "live_stride",
        "capacity_stride",
        "growth",
        "insufficient",
        "source_before_end",
        "source_alias",
        "header_alias",
        "payload_alias",
        "frame_alias",
        "heap",
        "iat",
        "source_count",
        "source_string",
        "missing_stack",
        "missing_data",
        "missing_fs",
        "missing_cookie",
        "allocation_low",
        "allocation_high",
        "allocation_bool",
        "allocation_float",
    ),
)
def test_selected_external_no_growth_caller_record_allocator_and_alias_guards(kind):
    packet = inputs()
    pages = packet["pages"]
    g = 0x30001000
    h = 0x0FFFFFD0
    r = 0x10002FF0
    at = 0x10000FF0
    if kind == "caller":
        store(pages, g, 0x04000004)
    elif kind == "begin_null":
        store(pages, h, 0)
    elif kind == "begin_after_end":
        store(pages, h, at + 308)
    elif kind == "live_stride":
        store(pages, h, at - 1)
    elif kind == "capacity_stride":
        store(pages, h + 8, at + 309)
    elif kind == "growth":
        store(pages, h + 8, at)
    elif kind == "insufficient":
        store(pages, h + 8, at + 307)
    elif kind == "source_before_end":
        store(pages, g + 4, at - 308)
    elif kind == "source_alias":
        store(pages, g + 4, at)
    elif kind == "header_alias":
        packet["registers"]["ecx"] = at
    elif kind == "payload_alias":
        packet["allocation_result"] = 0x06002803
    elif kind == "frame_alias":
        store(pages, r + 0xCC, g - 168)
        store(pages, r + 0xD0, g - 152)
    elif kind == "heap":
        store(pages, 0x008B7634, 0)
    elif kind == "iat":
        store(pages, 0x007D6220, 0)
    elif kind == "source_count":
        store(pages, r + 0xD0, 0x0600280A)
    elif kind == "source_string":
        store(pages, r + 0x38 + 16, 1)
    elif kind == "missing_stack":
        del pages[0x30000000]
    elif kind == "missing_data":
        del pages[0x06003000]
    elif kind == "missing_fs":
        del pages[0]
    elif kind == "missing_cookie":
        del pages[0x00893000]
    elif kind == "allocation_low":
        packet["allocation_result"] = 0x05FFFFFF
    elif kind == "allocation_high":
        packet["allocation_result"] = 0x06003FF1
    elif kind == "allocation_bool":
        packet["allocation_result"] = True
    else:
        packet["allocation_result"] = float(packet["allocation_result"])
    with pytest.raises(c.SmallRecordAppendError):
        c.apply(**packet)


@pytest.mark.parametrize("word", (0, True, float(0x04000000), -1, 2**32))
def test_strict_positive_outer_return(word):
    packet = inputs()
    packet["return_address"] = word
    with pytest.raises(c.SmallRecordAppendError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "word",
    (
        0x30000F58,
        0x0FFFFFD0,
        0x10002FF0,
        0x10000FF0,
        0x06002803,
        0x06001007,
        0x00893F28,
        0x00659F00,
        0x0055B9B0,
        0x004080D0,
        0x0049A8E0,
        0x0049AC40,
        0x0048ABA0,
        0x0048A920,
        0x007574DB,
        0x00779F52,
        0x0078942B,
    ),
)
def test_outer_return_disjoint_from_touched_data_and_all_selected_bodies(word):
    packet = inputs(return_address=word)
    with pytest.raises(c.SmallRecordAppendError):
        c.apply(**packet)


@pytest.mark.parametrize("word", (0x006573A7, 0xFFFFFFFF, 0x05000000))
def test_permitted_logical_outer_stop_words(word):
    packet = inputs(return_address=word)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "kind",
    (
        "frame_low",
        "frame_wrap",
        "header_null",
        "header_wrap",
        "insertion_wrap",
        "source_wrap",
        "path_wrap",
        "new_owner_code",
        "child_code",
    ),
)
def test_conservative_full_extents_and_selected_code_domains(kind):
    packet = inputs()
    pages = packet["pages"]
    h = packet["registers"]["ecx"]
    if kind == "frame_low":
        packet["registers"]["esp"] = 167
    elif kind == "frame_wrap":
        packet["registers"]["esp"] = 0xFFFFFFF8
    elif kind == "header_null":
        packet["registers"]["ecx"] = 0
    elif kind == "header_wrap":
        packet["registers"]["ecx"] = 0xFFFFFFF4
    elif kind == "insertion_wrap":
        store(pages, h, 0xFFFFFECC)
        store(pages, h + 4, 0xFFFFFECC)
        store(pages, h + 8, 0xFFFFFFFF)
    elif kind == "source_wrap":
        store(pages, 0x30001004, 0xFFFFFECC)
    elif kind == "path_wrap":
        store(pages, 0x10002FF0 + 0xCC, 0xFFFFFFF0)
    elif kind == "new_owner_code":
        packet["registers"]["ecx"] = 0x00659F00
    else:
        store(pages, 0x10002FF0 + 0xCC, 0x0048ABA0)
    with pytest.raises(c.SmallRecordAppendError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "extra",
        "df_bool",
        "endpoint_float",
        "source_float",
        "record_float",
        "events_tuple",
        "trace_tuple",
        "boundaries_tuple",
        "pages_mapping",
        "registers_mapping",
        "xmm_mapping",
        "short_events",
        "short_trace",
        "short_boundaries",
    ),
)
def test_exact_trusted_record_child_envelope_rejections(monkeypatch, kind):
    def forged(**kwargs):
        result = record_law.independent(kwargs)
        if kind == "missing":
            del result["record_bytes"]
        elif kind == "extra":
            result["other"] = 0
        elif kind == "df_bool":
            result["df"] = False
        elif kind == "endpoint_float":
            result["endpoint"] = float(result["endpoint"])
        elif kind == "source_float":
            result["source_address"] = float(result["source_address"])
        elif kind == "record_float":
            result["record_address"] = float(result["record_address"])
        elif kind.endswith("_tuple"):
            key = kind[:-6]
            result[key] = tuple(result[key])
        elif kind.endswith("_mapping"):
            key = kind[:-8]
            result[key] = UserDict(result[key])
        elif kind.startswith("short_"):
            result[kind[6:]].pop()
        return result

    monkeypatch.setattr(c.record, "apply", forged)
    with pytest.raises(c.SmallRecordAppendError):
        c.apply(**inputs())


def test_child_receives_actual_outer_prefix_pages_gprs_and_flags(monkeypatch):
    packet = inputs(flags=0xAD7)
    wanted = independent(packet)
    calls = []

    def checked(**kwargs):
        calls.append(copy.deepcopy(kwargs))
        child = record_law.independent(kwargs)
        strict_equal(child, wanted["record_packet"])
        return child

    monkeypatch.setattr(c.record, "apply", checked)
    check(c.apply(**packet), packet)
    assert len(calls) == 1
    actual = calls[0]
    g = packet["registers"]["esp"]
    assert set(actual) == {
        "pages",
        "registers",
        "xmm",
        "return_address",
        "entry_flags",
        "allocation_result",
    }
    assert actual["registers"] == dict(
        packet["registers"],
        eax=g - 16,
        ecx=0x10000FF0,
        esi=packet["registers"]["ecx"],
        edi=0x10002FF0,
        ebp=g - 4,
        esp=g - 40,
    )
    assert actual["entry_flags"] == 0x206
    assert actual["return_address"] == 0x00659F9D
    assert read_bytes(actual["pages"], g + 4, 4) == (0x10000FF0).to_bytes(4, "little")


def test_valid_typed_nested_instruction_metadata_is_trusted(monkeypatch):
    def changed(**kwargs):
        child = record_law.independent(kwargs)
        child["path_packet"]["trace_rvas"][0] = "0x0009a8e1"
        return child

    monkeypatch.setattr(c.record, "apply", changed)
    actual = c.apply(**inputs())
    assert actual["record_packet"]["path_packet"]["trace_rvas"][0] == "0x0009a8e1"


def test_foreign_child_failure_normalized(monkeypatch):
    def failed(**kwargs):
        raise ValueError("record failure")

    monkeypatch.setattr(c.record, "apply", failed)
    with pytest.raises(c.SmallRecordAppendError, match="record failure"):
        c.apply(**inputs())


def test_closed_actual_api_source_body_and_dependencies():
    signature = inspect.signature(c.apply)
    assert tuple(signature.parameters) == (
        "pages",
        "registers",
        "xmm",
        "return_address",
        "entry_flags",
        "allocation_result",
    )
    assert all(
        p.kind is inspect.Parameter.KEYWORD_ONLY
        and p.default is inspect.Parameter.empty
        for p in signature.parameters.values()
    )
    tree = ast.parse(inspect.getsource(c))
    assert not any(
        "unicorn" in ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    )
    assert not any(
        isinstance(node.func, ast.Attribute)
        and node.func.attr in ("_fixture", "_expected", "_run_case")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    )
    assert len(c.BODY_PINS) == 10 and sum(n for n, h in c.BODY_PINS.values()) == 1683
    assert c.BODY_PINS[0x259F00] == (
        183,
        "39a9908012609c47f77556aea5af0865f3eb36943b5a1860c4c338bb6ea6fbb7",
    )
    assert len(c.SOURCE_PINS) == 7


@pytest.mark.parametrize("count", (0, 1, 2, 3, 17, 511))
@pytest.mark.parametrize("alignment", (0, 7, 15))
@pytest.mark.parametrize("profile", range(3))
def test_complete_dynamic_parent_child_packet_and_access_projection(
    count, alignment, profile
):
    packet = inputs(
        count,
        frame=0x30001000 + alignment,
        receiver=0x0FFFFFD0 + alignment,
        source=0x10002FF0 + alignment,
        insertion=0x10000FF0 + alignment,
        path_source=0x06002800 + alignment,
        allocation_result=0x06001000 + alignment,
        profile=profile,
    )
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    strict_equal(packet, before)


@pytest.mark.parametrize("profile", range(3))
def test_full_old_count_two_packet_remains_compatible(profile):
    packet = inputs(2, profile=profile)
    actual = c.apply(**packet)
    check(actual, packet)
    strict_equal(actual, older_append.independent(packet))


@pytest.mark.parametrize("begin", (0, 1, 0xFFFFFFFF))
def test_zero_path_needs_no_runtime_or_allocator_and_preserves_unmapped_begin(
    begin, monkeypatch
):
    packet = inputs(0, path_source=begin, capacity=0xFFFFFFFF)
    for page in (
        0x06000000,
        0x06001000,
        0x06002000,
        0x06003000,
        0x008B7000,
        0x007D6000,
    ):
        packet["pages"].pop(page, None)

    def forbidden(*args, **kwargs):
        raise AssertionError("zero append used ordinary allocator or scalar")

    monkeypatch.setattr(c.record.path.allocator, "_expected", forbidden)
    monkeypatch.setattr(c.record.path.scalar, "apply", forbidden)
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["record_packet"]["path_packet"]["source_snapshot"] == b""
    assert all(
        actual["record_packet"]["path_packet"][k] is None
        for k in ("allocation_packet", "scalar_packet", "imported")
    )


@pytest.mark.parametrize("count", (0, 1, 511))
@pytest.mark.parametrize("capacity", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_unread_source_path_capacity_across_selected_branches(count, capacity):
    packet = inputs(count, capacity=capacity)
    actual = c.apply(**packet)
    check(actual, packet)
    source = int.from_bytes(
        read_bytes(packet["pages"], packet["registers"]["esp"] + 4, 4), "little"
    )
    assert not any(row["address"] == source + 0xD4 for row in actual["events"])
    assert read_bytes(actual["pages"], source + 0xD4, 4) == capacity.to_bytes(
        4, "little"
    )


@pytest.mark.parametrize("count", (0, 1))
def test_receiver_capacity_511_records_does_not_grow_or_touch_spare_records(count):
    packet = inputs(count, receiver=0x20000500, previous=0, spare=510)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("count", (0, 1, 511))
@pytest.mark.parametrize(
    "frame,source,insertion,path_source,allocation,receiver",
    (
        (172, 0x10005FF0, 0x10000FF0, 0x20000FF8, 0x06001003, 0x10000503),
        (0xFFFFFFF7, 0x90000FF8, 0x7FFFFFF0, 0x20000FF8, 0x06001007, 0x100005FF),
        (0x30001003, 0xFFFFFECB, 0x90000FF8, 0x20000FF8, 0x06001007, 0x10000503),
        (0x30001003, 0x10002134, 0x10002000, 0x20000FF8, 0x06001007, 0x10000503),
    ),
)
def test_dynamic_signed_record_crossings_max_frames_and_exact_record_adjacency(
    count, frame, source, insertion, path_source, allocation, receiver
):
    packet = inputs(
        count,
        frame=frame,
        source=source,
        insertion=insertion,
        path_source=path_source,
        allocation_result=allocation,
        receiver=receiver,
        previous=0,
        spare=0,
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "kind",
    (
        "count512",
        "stride",
        "closed_gpr",
        "closed_page",
        "allocation_bool",
        "zero_nonzero_allocation",
        "growth",
        "external_alias",
        "caller",
    ),
)
def test_parent_rejects_invalid_closed_premises_before_record_delegate(
    kind, monkeypatch
):
    packet = inputs(0 if kind == "zero_nonzero_allocation" else 2)
    g = packet["registers"]["esp"]
    h = packet["registers"]["ecx"]
    source = int.from_bytes(read_bytes(packet["pages"], g + 4, 4), "little")
    insertion = int.from_bytes(read_bytes(packet["pages"], h + 4, 4), "little")
    if kind == "count512":
        begin = int.from_bytes(read_bytes(packet["pages"], source + 0xCC, 4), "little")
        store(packet["pages"], source + 0xD0, begin + 4096)
    elif kind == "stride":
        begin = int.from_bytes(read_bytes(packet["pages"], source + 0xCC, 4), "little")
        store(packet["pages"], source + 0xD0, begin + 15)
    elif kind == "closed_gpr":
        packet["registers"]["eax"] = True
    elif kind == "closed_page":
        packet["pages"][0x12340000] = bytearray(4096)
    elif kind == "allocation_bool":
        packet["allocation_result"] = True
    elif kind == "zero_nonzero_allocation":
        packet["allocation_result"] = 0x06001007
    elif kind == "growth":
        store(packet["pages"], h + 8, insertion)
    elif kind == "external_alias":
        store(packet["pages"], g + 4, insertion)
    else:
        store(packet["pages"], g, 0x04000001)
    before = copy.deepcopy(packet)
    calls = []

    def forbidden(**kwargs):
        calls.append(True)
        raise AssertionError("record delegate reached invalid parent premise")

    monkeypatch.setattr(c.record, "apply", forbidden)
    with pytest.raises(c.SmallRecordAppendError):
        c.apply(**packet)
    assert calls == []
    strict_equal(packet, before)


@pytest.mark.parametrize("count", (0, 1, 511))
@pytest.mark.parametrize(
    "kind",
    (
        "gpr",
        "xmm",
        "flags",
        "mask",
        "df",
        "endpoint",
        "source_snapshot",
        "record_bytes",
        "pages",
        "read",
        "outside_write",
        "width",
        "record_mapping",
        "boundary_prefix",
        "boundary_pages",
        "boundary_bool_gpr",
        "boundary_xmm",
        "boundary_index_bool",
        "boundary_name_float",
    ),
)
def test_complete_record_terminal_page_event_and_prefix_corruption_rejected(
    count, kind, monkeypatch
):
    def forged(**kwargs):
        child = record_law.independent(kwargs)
        if kind == "gpr":
            child["registers"]["ebx"] ^= 1
        elif kind == "xmm":
            child["xmm"]["xmm7"] ^= 1
        elif kind == "flags":
            child["flags"] ^= 1
        elif kind == "mask":
            child["flag_mask"] = 0x8C5
        elif kind == "df":
            child["df"] = False
        elif kind == "endpoint":
            child["endpoint"] += 1
        elif kind == "source_snapshot":
            child["source_snapshot"] = (
                bytes([child["source_snapshot"][0] ^ 1]) + child["source_snapshot"][1:]
            )
        elif kind == "record_bytes":
            child["record_bytes"] = (
                bytes([child["record_bytes"][0] ^ 1]) + child["record_bytes"][1:]
            )
        elif kind == "pages":
            store(child["pages"], 0x12340000, read_word(child["pages"], 0x12340000) ^ 1)
        elif kind == "read":
            next(row for row in child["events"] if row["access"] == "read")[
                "value"
            ] ^= 1
        elif kind == "outside_write":
            child["events"][0]["address"] = COOKIE
        elif kind == "width":
            child["events"][0]["width"] = 3
        elif kind == "record_mapping":
            child["pages"] = UserDict(child["pages"])
        else:
            state = child["boundaries"][0]
            if kind == "boundary_prefix":
                state["events"][0]["value"] ^= 1
            elif kind == "boundary_pages":
                store(
                    state["pages"],
                    0x12340000,
                    read_word(state["pages"], 0x12340000) ^ 1,
                )
            elif kind == "boundary_bool_gpr":
                state["registers"]["eax"] = True
            elif kind == "boundary_xmm":
                state["xmm"]["xmm0"] ^= 1
            elif kind == "boundary_index_bool":
                state["index"] = False
            else:
                state["name"] = 0.0
        return child

    packet = inputs(count)
    before = copy.deepcopy(packet)
    monkeypatch.setattr(c.record, "apply", forged)
    with pytest.raises(c.SmallRecordAppendError):
        c.apply(**packet)
    strict_equal(packet, before)


def read_word(pages, address):
    return int.from_bytes(read_bytes(pages, address, 4), "little")


@pytest.mark.parametrize(
    "kind",
    (
        "path_extra",
        "path_missing",
        "path_geometry_bool",
        "path_df_bool",
        "path_mutable_page",
        "path_snapshot_size",
        "allocator_extra",
        "allocator_request_float",
        "allocator_metadata",
        "allocator_bool_gpr",
        "allocator_mutable_stack",
        "scalar_extra",
        "scalar_bool_xmm",
        "scalar_df_bool",
        "scalar_mutable_page",
    ),
)
def test_nested_fifteen_seven_ten_closed_typed_envelopes(kind, monkeypatch):
    def forged(**kwargs):
        child = record_law.independent(kwargs)
        pathpacket = child["path_packet"]
        if kind == "path_extra":
            pathpacket["other"] = 0
        elif kind == "path_missing":
            pathpacket.pop("source_snapshot")
        elif kind == "path_geometry_bool":
            pathpacket["geometry"]["source"] = True
        elif kind == "path_df_bool":
            pathpacket["df"] = False
        elif kind == "path_mutable_page":
            pathpacket["pages"][0x12340000] = bytearray(4096)
        elif kind == "path_snapshot_size":
            pathpacket["source_snapshot"] = b""
        elif kind.startswith("allocator"):
            packet = pathpacket["allocation_packet"]
            if kind == "allocator_extra":
                packet["other"] = 0
            elif kind == "allocator_request_float":
                packet["relation"]["request"] = float(packet["relation"]["request"])
            elif kind == "allocator_metadata":
                packet["relation"]["metadata"] = {}
            elif kind == "allocator_bool_gpr":
                packet["registers"]["eax"] = True
            else:
                packet["stack"] = bytearray(packet["stack"])
        else:
            packet = pathpacket["scalar_packet"]
            if kind == "scalar_extra":
                packet["other"] = 0
            elif kind == "scalar_bool_xmm":
                packet["xmm"]["xmm1"] = False
            elif kind == "scalar_df_bool":
                packet["df"] = False
            else:
                packet["pages"][0x12340000] = bytearray(4096)
        return child

    monkeypatch.setattr(c.record, "apply", forged)
    with pytest.raises(c.SmallRecordAppendError):
        c.apply(**inputs(1))


@pytest.mark.parametrize("count", (0, 1, 511))
def test_record_delegate_receives_actual_prefix_and_all_closed_arguments(
    count, monkeypatch
):
    packet = inputs(count, flags=0xAD7)
    wanted = independent(packet)
    calls = []

    def child(**kwargs):
        calls.append(copy.deepcopy(kwargs))
        value = record_law.independent(kwargs)
        strict_equal(value, wanted["record_packet"])
        return value

    monkeypatch.setattr(c.record, "apply", child)
    check(c.apply(**packet), packet)
    assert len(calls) == 1
    called = calls[0]
    entry = wanted["boundaries"][0]
    strict_equal(called["registers"], entry["registers"])
    strict_equal(called["pages"], entry["pages"])
    strict_equal(called["xmm"], packet["xmm"])
    assert called["return_address"] == 0x00659F9D
    assert called["entry_flags"] == (0x202 | entry["flags"])
    assert called["allocation_result"] == packet["allocation_result"]


@pytest.mark.parametrize("count", (0, 511))
def test_zero_and_positive_nested_outputs_are_detached(count):
    packet = inputs(count)
    before = copy.deepcopy(packet)
    first = c.apply(**packet)
    saved = copy.deepcopy(first)
    first["record_packet"]["pages"].clear()
    first["record_packet"]["path_packet"]["pages"].clear()
    first["boundaries"][0]["events"].clear()
    first["boundaries"][-1]["registers"].clear()
    strict_equal(first["pages"], saved["pages"])
    strict_equal(first["events"], saved["events"])
    strict_equal(packet, before)
    check(c.apply(**packet), packet)
