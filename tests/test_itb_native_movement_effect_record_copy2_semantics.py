"""Independent actual-page two-entry movement record-copy source oracle.

Owner byte/access/trace equations reuse the handwritten empty-record test source;
the path replacement uses the independently handwritten generalized clone test.
Production apply is used only to obtain the actual packet under test.
"""

from __future__ import annotations
import ast
import copy
import inspect
from collections import UserDict
import pytest
from src.observatory import native_movement_effect_record_copy2_semantics as c
from tests import (
    test_itb_native_movement_effect_record_empty_copy_semantics as empty_law,
)
from tests import test_itb_native_movement_path_clone2_semantics as clone_law
from tests.test_itb_native_movement_empty_string_copy_semantics import (
    independent as string_law,
    assert_strict_packet as strict_equal,
    store,
    read_bytes,
)

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
COOKIE = 0x00893F28
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
FIELDS = empty_law.FIELDS
OWNER = empty_law.OWNER
CALL_CHILD = dict(empty_law.CALL_CHILD)
CALL_CHILD[0x15BBC5] = clone_law.TRACE
TRACE = tuple(q for pc in OWNER for q in (pc,) + tuple(CALL_CHILD.get(pc, ())))
KEYS = empty_law.KEYS | {"path_packet"}
BOUNDARY_KEYS = empty_law.BOUNDARY_KEYS
FLAG_BITS = (0, 2, 4, 6, 7, 9, 11)
ORDINARY_FLAGS = tuple(
    2 | sum(1 << bit for i, bit in enumerate(FLAG_BITS) if sel >> i & 1)
    for sel in range(128)
)


def inputs(
    *,
    frame=0x30001000,
    source=0x10000FF0,
    destination=0x10002FF0,
    path_source=0x06002803,
    allocation_result=0x06001007,
    profile=0,
    flags=0x246,
    return_address=0x04000000,
    capacity=0xFFFFFFFF,
):
    packet = empty_law.inputs(
        frame=frame,
        source=source,
        destination=destination,
        profile=profile,
        flags=flags,
        return_address=return_address,
    )
    pages = packet["pages"]
    stack_base = min((frame - 128) & ~4095, 0xFFFFE000)
    mapped = {
        stack_base,
        stack_base + 4096,
        0x06000000,
        0x06001000,
        0x06002000,
        0x06003000,
        0x008B7000,
        0x007D6000,
    }
    mapped.update(range(path_source & ~4095, ((path_source + 15) & ~4095) + 1, 4096))
    for base in sorted(mapped):
        if base not in pages:
            pages[base] = bytes(
                (j * 29 + (base >> 12) * 37 + profile * 71) & 255 for j in range(4096)
            )
    store(pages, source + 0xCC, path_source)
    store(pages, source + 0xD0, (path_source + 16) & 0xFFFFFFFF)
    store(pages, source + 0xD4, capacity)
    store(pages, 0x008B7634, 0x12345678)
    store(pages, 0x007D6220, 0x05000000)
    for i, word in enumerate((0xD15C0016, 0xFFFFFFFF, 0x80000000, 0x8765DD16)):
        store(pages, path_source + i * 4, word ^ ((profile * 0x7654321) & 0xFFFFFFFF))
    packet["allocation_result"] = allocation_result
    return packet


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
    child_input = dict(
        pages=dict(memory),
        registers=dict(regs),
        xmm=dict(packet["xmm"]),
        return_address=0x0055BBCA,
        entry_flags=(packet["entry_flags"] & ~0x8D5) | 0x85,
        allocation_result=packet["allocation_result"],
    )
    # The independent lower clone oracle contains the complete ordinary seven-
    # field allocation and ten-field scalar packets; no production helper runs.
    joined = clone_law.independent(child_input)
    prefix = copy.deepcopy(events)
    for index, (name, state) in enumerate(joined["boundaries"].items()):
        row = copy.deepcopy(state)
        row.update(kind="path", name=name, index=index, events=prefix + row["events"])
        boundaries.append(row)
    events.extend(copy.deepcopy(joined["events"]))
    memory = dict(joined["pages"])
    regs = dict(joined["registers"])
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
    final = clone_law.final_pages(child_input)
    record = bytearray(read_bytes(final, d, 308))
    for off, width in FIELDS:
        record[off : off + width] = read_bytes(packet["pages"], s + off, width)
    for off in STRINGS:
        record[off] = 0
        record[off + 16 : off + 20] = bytes(4)
        record[off + 20 : off + 24] = (15).to_bytes(4, "little")
    a = packet["allocation_result"]
    record[0xCC:0xD8] = b"".join(x.to_bytes(4, "little") for x in (a, a + 16, a + 16))
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
        path_packet=copy.deepcopy(joined),
    )


def check(actual, packet):
    wanted = independent(packet)
    strict_equal(actual, wanted)
    assert set(actual) == KEYS and len(KEYS) == 15
    assert len(OWNER) == 191 and len(clone_law.TRACE) == 136 and len(TRACE) == 591
    assert len(actual["events"]) == 372 and len(actual["boundaries"]) == 23
    assert [len(row["events"]) for row in actual["boundaries"]] == [
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
        215,
        242,
        250,
        259,
        273,
        291,
        308,
        317,
        334,
        346,
        363,
    ]
    assert all(set(row) == BOUNDARY_KEYS for row in actual["boundaries"])
    g = packet["registers"]["esp"]
    s, d = wanted["source_address"], wanted["record_address"]
    o = int.from_bytes(read_bytes(packet["pages"], s + 0xCC, 4), "little")
    a = packet["allocation_result"]
    written = {off + i for off, width in FIELDS for i in range(width)}
    for off in STRINGS:
        written.update({off, *range(off + 16, off + 24)})
    written.update(range(0xCC, 0xD8))
    assert len(written) == 183 and 308 - len(written) == 125
    previous = read_bytes(packet["pages"], d, 308)
    assert all(
        actual["record_bytes"][i] == previous[i] for i in range(308) if i not in written
    )
    assert read_bytes(actual["pages"], s, 308) == read_bytes(packet["pages"], s, 308)
    assert read_bytes(actual["pages"], o, 16) == read_bytes(packet["pages"], o, 16)
    assert read_bytes(actual["pages"], a, 16) == read_bytes(packet["pages"], o, 16)
    assert read_bytes(actual["pages"], g, 8) == read_bytes(packet["pages"], g, 8)
    writes = {
        row["address"] + i
        for row in actual["events"]
        if row["access"] == "write"
        for i in range(row["width"])
    }
    assert writes == set(range(g - 128, g)) | set(range(4)) | {
        d + i for i in written
    } | set(range(a, a + 16))
    path = actual["path_packet"]
    assert len(path["events"]) == 83 and len(path["trace_rvas"]) == 136
    assert list(path["boundaries"]) == [
        "parent_entry",
        "reserve_entry",
        "allocation_entry",
        "allocation_return",
        "reserve_return",
        "scalar_entry",
        "scalar_return",
    ]
    assert (
        len(path["allocation_packet"]["events"]) == 27
        and len(path["scalar_packet"]["events"]) == 14
    )
    assert path["imported"]["words"] == [0x789463, 0x12345678, 0, 16]
    assert path["imported"]["entry_esp"] == g - 128
    assert read_bytes(actual["pages"], g - 68, 4) == a.to_bytes(4, "little")
    assert read_bytes(actual["pages"], g - 72, 4) == (0x0049A921).to_bytes(4, "little")
    reads = {row["address"] for row in actual["events"] if row["access"] == "read"}
    assert s + 0xD4 not in reads
    for off in STRINGS:
        assert s + off not in reads and s + off + 20 not in reads
    assert not {0x3574CA, 0x3435D9, 0x8270, 0x3703E0}.intersection(
        int(pc, 16) for pc in actual["trace_rvas"]
    )


@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize("profile", range(3))
@pytest.mark.parametrize("order", ("before", "after"))
def test_complete_actual_record_path_and_23_boundaries(alignment, profile, order):
    s, d = 0x10000FF0 + alignment, 0x10002FF0 + alignment
    if order == "after":
        s, d = d, s
    packet = inputs(
        frame=0x30001000 + alignment,
        source=s,
        destination=d,
        path_source=0x06002800 + alignment,
        allocation_result=0x06001000 + alignment,
        profile=profile,
    )
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    strict_equal(packet, before)


@pytest.mark.parametrize("flags", ORDINARY_FLAGS)
def test_all_128_ordinary_flags(flags):
    packet = inputs(flags=flags)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "g,s,d,o,a",
    [
        (0x30000FFD, 0x10000FFF, 0x10002FFF, 0x20000FF8, 0x06000FF8),
        (0xFFFFFFF7, 0x10000200, 0x10000800, 0x7FFFFFF8, 0x06003FF0),
        (0x30001000, 0x7FFFFFF0, 0x90000FF0, 0xFFFFFFEF, 0x06000000),
        (0x30001000, 0xFFFFFECB, 0x10000303, 0x20000FF8, 0x06001003),
        (0x30001000, 0x10000303, 0xFFFFFECB, 0x20000FF8, 0x06001003),
        (0x30001000, 0x10000200, 0x10000334, 0x20000FF8, 0x06001003),
        (0x30001000, 0x10000334, 0x10000200, 0x06000FF0, 0x06001000),
        (0x30001000, 0x10000200, 0x10000800, 0x06001010, 0x06001000),
        (0x30001000, 0x30001800, 0x30001A00, 0x30001D00, 0x06001000),
        (132, 0x10000200, 0x10000800, 0x20000FF8, 0x06001000),
    ],
)
def test_cross_pages_signed_edges_adjacencies_and_parent_stack_objects(g, s, d, o, a):
    packet = inputs(
        frame=g, source=s, destination=d, path_source=o, allocation_result=a
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("value", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_arbitrary_gpr_xmm_and_unread_source_capacity(value):
    packet = inputs(capacity=value)
    for name in GPR:
        if name not in ("esp", "ecx"):
            packet["registers"][name] = value
    packet["xmm"] = {
        name: (value << 96) | (value << 64) | (value << 32) | value for name in XMM
    }
    check(c.apply(**packet), packet)


def test_all_source_and_destination_padding_preserved():
    packet = inputs()
    s, d = 0x10000FF0, 0x10002FF0
    fields = {off + i for off, width in FIELDS for i in range(width)} | set(
        range(0xCC, 0xD8)
    )
    for off in STRINGS:
        fields.update({off, *range(off + 16, off + 24)})
    for i in range(308):
        if i not in fields:
            store(packet["pages"], s + i, (i * 19 + 37) & 255, 1)
            store(packet["pages"], d + i, (i * 31 + 53) & 255, 1)
    check(c.apply(**packet), packet)


def test_input_result_path_and_boundary_detachment():
    packet = inputs()
    before = copy.deepcopy(packet)
    actual = c.apply(**packet)
    wanted = independent(packet)
    actual["pages"][0x12340000] = bytes(4096)
    actual["events"][0]["value"] ^= 1
    actual["registers"]["eax"] ^= 1
    actual["xmm"]["xmm7"] ^= 1
    actual["boundaries"][0]["pages"][0x12340000] = bytes(4096)
    actual["path_packet"]["allocation_packet"]["relation"]["request"] = 7
    strict_equal(packet, before)
    strict_equal(c.apply(**packet), wanted)
    assert (
        actual["path_packet"]["allocation_packet"]["relation"]["request"]
        != actual["path_packet"]["imported"]["words"][3]
    )


@pytest.mark.parametrize(
    "bit", [b for b in range(32) if b not in (0, 1, 2, 4, 6, 7, 9, 11)]
)
def test_each_forbidden_flag(bit):
    packet = inputs()
    packet["entry_flags"] = 2 | (1 << bit)
    with pytest.raises(c.RecordCopy2Error):
        c.apply(**packet)


@pytest.mark.parametrize("value", (0, 4, True, 2.0, -1, 2**32, None))
def test_missing_bit1_and_flag_type(value):
    packet = inputs()
    packet["entry_flags"] = value
    with pytest.raises(c.RecordCopy2Error):
        c.apply(**packet)


@pytest.mark.parametrize(
    "group,key,value",
    [
        ("registers", "eax", True),
        ("registers", "esp", float(0x30001000)),
        ("registers", "ebx", -1),
        ("registers", "edx", 2**32),
        ("xmm", "xmm0", False),
        ("xmm", "xmm7", 0.0),
        ("xmm", "xmm3", -1),
        ("xmm", "xmm2", 2**128),
    ],
)
def test_strict_full_gpr_and_xmm_values(group, key, value):
    packet = inputs()
    packet[group][key] = value
    with pytest.raises(c.RecordCopy2Error):
        c.apply(**packet)


@pytest.mark.parametrize("group", ("registers", "xmm"))
@pytest.mark.parametrize("kind", ("missing", "extra", "mapping", "subclass_key"))
def test_exact_typed_mappings(group, kind):
    packet = inputs()
    names = GPR if group == "registers" else XMM
    if kind == "missing":
        del packet[group][names[0]]
    elif kind == "extra":
        packet[group]["other"] = 0
    elif kind == "mapping":
        packet[group] = UserDict(packet[group])
    else:

        class Alias(str):
            pass

        value = packet[group].pop(names[0])
        packet[group][Alias(names[0])] = value
    with pytest.raises(c.RecordCopy2Error):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    (
        "mapping",
        "empty",
        "mutable",
        "short",
        "float_key",
        "bool_key",
        "unaligned",
        "negative",
        "oversize",
    ),
)
def test_strict_immutable_complete_pages(kind):
    packet = inputs()
    pages = packet["pages"]
    if kind == "mapping":
        packet["pages"] = UserDict(pages)
    elif kind == "empty":
        packet["pages"] = {}
    elif kind == "mutable":
        pages[0] = bytearray(pages[0])
    elif kind == "short":
        pages[0] = pages[0][:-1]
    elif kind == "float_key":
        value = pages.pop(0)
        pages[0.0] = value
    elif kind == "bool_key":
        value = pages.pop(0)
        pages[False] = value
    elif kind == "unaligned":
        pages[1] = bytes(4096)
    elif kind == "negative":
        pages[-4096] = bytes(4096)
    else:
        pages[2**32] = bytes(4096)
    with pytest.raises(c.RecordCopy2Error):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    (
        "caller",
        "source_size",
        "source_cap",
        "source_byte",
        "path_count",
        "path_null",
        "heap",
        "iat",
        "missing_stack",
        "missing_data",
        "missing_payload",
        "alias_records",
        "alias_payload",
        "alias_frame",
        "missing_cookie",
        "missing_fs",
        "allocation_low",
        "allocation_high",
        "allocation_bool",
        "allocation_float",
    ),
)
def test_required_actual_caller_record_clone_allocator_and_mapping_premises(kind):
    packet = inputs()
    pages = packet["pages"]
    g = packet["registers"]["esp"]
    s = 0x10000FF0
    o = 0x06002803
    if kind == "caller":
        store(pages, g, 0x04000004)
    elif kind == "source_size":
        store(pages, s + 0x48, 1)
    elif kind == "source_cap":
        store(pages, s + 0x4C, 16)
    elif kind == "source_byte":
        store(pages, s + 0x38, 1, 1)
    elif kind == "path_count":
        store(pages, s + 0xD0, o + 8)
    elif kind == "path_null":
        store(pages, s + 0xCC, 0)
        store(pages, s + 0xD0, 16)
    elif kind == "heap":
        store(pages, 0x008B7634, 0)
    elif kind == "iat":
        store(pages, 0x007D6220, 0)
    elif kind == "missing_stack":
        del pages[0x30000000]
    elif kind == "missing_data":
        del pages[0x06003000]
    elif kind == "missing_payload":
        del pages[0x06002000]
    elif kind == "alias_records":
        packet["registers"]["ecx"] = s
    elif kind == "alias_payload":
        packet["allocation_result"] = o
    elif kind == "alias_frame":
        store(pages, s + 0xCC, g - 128)
        store(pages, s + 0xD0, g - 112)
    elif kind == "missing_cookie":
        del pages[0x00893000]
    elif kind == "missing_fs":
        del pages[0]
    elif kind == "allocation_low":
        packet["allocation_result"] = 0x05FFFFFF
    elif kind == "allocation_high":
        packet["allocation_result"] = 0x06003FF1
    elif kind == "allocation_bool":
        packet["allocation_result"] = True
    else:
        packet["allocation_result"] = float(packet["allocation_result"])
    with pytest.raises(c.RecordCopy2Error):
        c.apply(**packet)


@pytest.mark.parametrize(
    "target",
    (
        0x06002803,
        0x06002812,
        0x06001007,
        0x06001016,
        0x10000FF0,
        0x10002FF0,
        0x30000F80,
        0x00893F28,
        0x0055B9B0,
        0x004080D0,
        0x0049A8E0,
        0x0048ABA0,
        0x0048A920,
        0x007574DB,
        0x00779F52,
        0x0078942B,
    ),
)
def test_outer_return_disjoint_from_both_path_buffers_and_selected_bodies(target):
    packet = inputs(return_address=target)
    with pytest.raises(c.RecordCopy2Error):
        c.apply(**packet)


@pytest.mark.parametrize("target", (0, True, float(0x04000000), -1, 2**32))
def test_outer_return_strict_positive_uint(target):
    packet = inputs()
    packet["return_address"] = target
    with pytest.raises(c.RecordCopy2Error):
        c.apply(**packet)


@pytest.mark.parametrize("target", (0x006573A7, 0xFFFFFFFF, 0x05000000))
def test_positive_logical_outer_endpoints_do_not_claim_execution(target):
    packet = inputs(return_address=target)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "extra",
        "df_bool",
        "endpoint_float",
        "events_tuple",
        "trace_tuple",
        "pages_mapping",
        "registers_mapping",
        "xmm_mapping",
        "boundaries_mapping",
        "geometry_bool",
        "short_events",
        "short_trace",
    ),
)
def test_parent_exact_child_envelope_rejections(monkeypatch, kind):
    def forged(**kwargs):
        packet = clone_law.independent(kwargs)
        if kind == "missing":
            del packet["source_snapshot"]
        elif kind == "extra":
            packet["other"] = 0
        elif kind == "df_bool":
            packet["df"] = False
        elif kind == "endpoint_float":
            packet["endpoint"] = float(packet["endpoint"])
        elif kind == "events_tuple":
            packet["events"] = tuple(packet["events"])
        elif kind == "trace_tuple":
            packet["trace_rvas"] = tuple(packet["trace_rvas"])
        elif kind.endswith("_mapping"):
            key = kind[:-8]
            packet[key] = UserDict(packet[key])
        elif kind == "geometry_bool":
            packet["geometry"]["entry"] = True
        elif kind == "short_events":
            packet["events"].pop()
        else:
            packet["trace_rvas"].pop()
        return packet

    monkeypatch.setattr(c.path, "apply", forged)
    with pytest.raises(c.RecordCopy2Error):
        c.apply(**inputs())


def test_actual_path_call_receives_complete_pages_and_exact_parent_boundary(
    monkeypatch,
):
    packet = inputs(flags=0xAD7)
    wanted = independent(packet)
    calls = []

    def checked(**kwargs):
        calls.append(copy.deepcopy(kwargs))
        lower = clone_law.independent(kwargs)
        strict_equal(lower, wanted["path_packet"])
        return lower

    monkeypatch.setattr(c.path, "apply", checked)
    check(c.apply(**packet), packet)
    assert len(calls) == 1
    assert set(calls[0]) == {
        "pages",
        "registers",
        "xmm",
        "return_address",
        "entry_flags",
        "allocation_result",
    }
    assert calls[0]["entry_flags"] == 0x287
    assert calls[0]["registers"]["esp"] == packet["registers"]["esp"] - 40
    assert calls[0]["registers"]["ecx"] == packet["registers"]["ecx"] + 0xCC
    assert calls[0]["return_address"] == 0x0055BBCA


def test_trusted_child_scope_does_not_claim_independent_recomputation(monkeypatch):
    # A same-schema nested snapshot is transported; the parent checks its join
    # envelope, while the independently sealed lower law owns this field.
    def changed(**kwargs):
        result = clone_law.independent(kwargs)
        result["source_snapshot"] = bytes(16)
        return result

    monkeypatch.setattr(c.path, "apply", changed)
    actual = c.apply(**inputs())
    assert actual["path_packet"]["source_snapshot"] == bytes(16)
    assert actual["source_snapshot"] != bytes(308)


def test_foreign_child_failure_normalized(monkeypatch):
    def fail(**kwargs):
        raise ValueError("lower failure")

    monkeypatch.setattr(c.path, "apply", fail)
    with pytest.raises(c.RecordCopy2Error, match="lower failure"):
        c.apply(**inputs())


def test_closed_actual_api_pinned_dependencies_and_no_fixture_substitution():
    assert tuple(inspect.signature(c.apply).parameters) == (
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
        for p in inspect.signature(c.apply).parameters.values()
    )
    tree = ast.parse(inspect.getsource(c))
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not any("unicorn" in ast.unparse(n) for n in imports)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert not any(
        isinstance(n.func, ast.Attribute)
        and n.func.attr in ("_fixture", "_expected", "_run_case")
        for n in calls
    )
    assert set(c.BODY_PINS) == {
        0x15B9B0,
        0x80D0,
        0x9A8E0,
        0x9AC40,
        0x8ABA0,
        0x8A920,
        0x3574DB,
        0x379F52,
        0x38942B,
    }
    assert sum(n for n, h in c.BODY_PINS.values()) == 1500
    assert len(c.SOURCE_PINS) == 7
    assert c.SOURCE_PINS["clone2_conformance"] == (
        "pe_native_movement_path_clone2_conformance",
        "1cddf384c45fb50a60752656acd2560a7e243dd20f0d68b8a963a4a7bb3a739b",
    )


@pytest.mark.parametrize(
    "g,s,d,o",
    [
        (127, 0x10000FF0, 0x10002FF0, 0x06002803),
        (0xFFFFFFF8, 0x10000FF0, 0x10002FF0, 0x06002803),
        (0x30001000, 0, 0x10002FF0, 0x06002803),
        (0x30001000, 0x10000FF0, 0, 0x06002803),
        (0x30001000, 0xFFFFFECC, 0x10002FF0, 0x06002803),
        (0x30001000, 0x10000FF0, 0xFFFFFECC, 0x06002803),
        (0x30001000, 0x10000FF0, 0x10002FF0, 0xFFFFFFF0),
        (0x30001000, 0x0055B9B0, 0x10002FF0, 0x06002803),
        (0x30001000, 0x10000FF0, 0x004080D0, 0x06002803),
        (0x30001000, 0x10000FF0, 0x10002FF0, 0x0048ABA0),
    ],
)
def test_conservative_nonwrap_null_and_code_domain(g, s, d, o):
    # Build valid bytes first; install only the disputed geometry afterward.
    packet = inputs()
    old = packet["registers"]["esp"]
    if g != old:
        packet["registers"]["esp"] = g
    if s != 0x10000FF0:
        store(packet["pages"], old + 4, s)
    if d != 0x10002FF0:
        packet["registers"]["ecx"] = d
    if o != 0x06002803:
        store(packet["pages"], 0x10000FF0 + 0xCC, o)
        store(packet["pages"], 0x10000FF0 + 0xD0, (o + 16) & 0xFFFFFFFF)
    with pytest.raises(c.RecordCopy2Error):
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
def test_entire_empty_string_child_checked_independently(monkeypatch, kind):
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
    before = inputs()
    snapshot = copy.deepcopy(before)
    with pytest.raises(c.RecordCopy2Error):
        c.apply(**before)
    strict_equal(before, snapshot)
