"""Independent actual-page zero through511 movement record-copy source oracle.

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
from src.observatory import native_movement_effect_record_small_copy_semantics as c
from tests import (
    test_itb_native_movement_effect_record_empty_copy_semantics as empty_law,
)
from tests import test_itb_native_movement_path_small_clone_semantics as clone_law
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

KEYS = empty_law.KEYS | {"path_packet"}
BOUNDARY_KEYS = empty_law.BOUNDARY_KEYS
FLAG_BITS = (0, 2, 4, 6, 7, 9, 11)
ORDINARY_FLAGS = tuple(
    2 | sum(1 << bit for i, bit in enumerate(FLAG_BITS) if sel >> i & 1)
    for sel in range(128)
)


def inputs(
    count=2,
    *,
    frame=0x30001000,
    source=0x10000FF0,
    destination=0x10002FF0,
    path_source=0x20000FF9,
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
    base = min((frame - 128) & ~4095, 0xFFFFE000)
    mapped = {base, base + 4096}
    if count:
        mapped.update(
            (0x06000000, 0x06001000, 0x06002000, 0x06003000, 0x008B7000, 0x007D6000)
        )
        mapped.update(
            range(
                path_source & ~4095,
                ((path_source + count * 8 - 1) & ~4095) + 4096,
                4096,
            )
        )
    for page in sorted(mapped):
        if page not in pages:
            pages[page] = bytes(
                (j * 29 + (page >> 12) * 37 + profile * 71) & 255 for j in range(4096)
            )
    store(pages, source + 0xCC, path_source)
    store(pages, source + 0xD0, path_source + count * 8)
    store(pages, source + 0xD4, capacity)
    if count:
        store(pages, 0x8B7634, 0x12345678)
        store(pages, 0x7D6220, 0x05000000)
        for i in range(count * 2):
            store(
                pages,
                path_source + 4 * i,
                (0xD15C0016 + i * 0x13572469 + profile * 0x7654321) & 0xFFFFFFFF,
            )
    packet["allocation_result"] = allocation_result if count else 0
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
    o = int.from_bytes(read_bytes(packet["pages"], s + 0xCC, 4), "little")
    size = int.from_bytes(read_bytes(packet["pages"], s + 0xD0, 4), "little") - o
    count = size // 8
    if count:
        for index, (name, state) in enumerate(joined["boundaries"].items()):
            row = copy.deepcopy(state)
            row.update(
                kind="path", name=name, index=index, events=prefix + row["events"]
            )
            boundaries.append(row)
    else:
        for name, kind, phase in (
            ("parent_entry", "path", "entry"),
            ("reserve_entry", "reserve", "entry"),
            ("reserve_return", "reserve", "return"),
        ):
            row = copy.deepcopy(joined["boundaries"][name])
            row.update(kind=kind, name=phase, index=0, events=prefix + row["events"])
            if name == "parent_entry":
                row.update(flags=0x85, flag_mask=0x8D5)
            boundaries.append(row)
        row = {
            k: copy.deepcopy(joined[k])
            for k in (
                "registers",
                "xmm",
                "pages",
                "events",
                "flags",
                "flag_mask",
                "df",
                "endpoint",
            )
        }
        row.update(kind="path", name="return", index=0, events=prefix + row["events"])
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
    record[0xCC:0xD8] = b"".join(
        x.to_bytes(4, "little") for x in (a, a + size, a + size)
    )
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
    trace = []
    for pc in OWNER:
        trace.append(f"0x{pc:08x}")
        if pc == 0x15BBC5:
            trace.extend(joined["trace_rvas"])
        elif pc in CALL_CHILD:
            trace.extend(f"0x{x:08x}" for x in CALL_CHILD[pc])
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
        trace_rvas=trace,
        boundaries=boundaries,
        path_packet=copy.deepcopy(joined),
    )


def check(actual, packet):
    wanted = independent(packet)
    strict_equal(actual, wanted)
    assert type(actual) is dict and set(actual) == KEYS and len(KEYS) == 15
    s, d = wanted["source_address"], wanted["record_address"]
    g = packet["registers"]["esp"]
    o = int.from_bytes(read_bytes(packet["pages"], s + 0xCC, 4), "little")
    size = int.from_bytes(read_bytes(packet["pages"], s + 0xD0, 4), "little") - o
    n = size // 8
    a = packet["allocation_result"]
    assert len(OWNER) == 191
    assert len(actual["trace_rvas"]) == (571 + 10 * n if n else 492)
    assert len(actual["events"]) == (364 + 4 * n if n else 315)
    assert len(actual["boundaries"]) == (23 if n else 20)
    assert all(set(state) == BOUNDARY_KEYS for state in actual["boundaries"])
    prefixes = (
        [
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
            265 + 4 * n,
            283 + 4 * n,
            300 + 4 * n,
            309 + 4 * n,
            326 + 4 * n,
            338 + 4 * n,
            355 + 4 * n,
        ]
        if n
        else [
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
    )
    assert [len(state["events"]) for state in actual["boundaries"]] == prefixes
    written = {off + i for off, w in FIELDS for i in range(w)} | set(range(0xCC, 0xD8))
    for off in STRINGS:
        written.update({off, *range(off + 16, off + 24)})
    assert len(written) == 183 and 308 - len(written) == 125
    old = read_bytes(packet["pages"], d, 308)
    assert all(
        actual["record_bytes"][i] == old[i] for i in range(308) if i not in written
    )
    assert (
        actual["source_snapshot"]
        == read_bytes(packet["pages"], s, 308)
        == read_bytes(actual["pages"], s, 308)
    )
    assert read_bytes(actual["pages"], g, 8) == read_bytes(packet["pages"], g, 8)
    pathpacket = actual["path_packet"]
    assert len(pathpacket["events"]) == (75 + 4 * n if n else 26)
    assert len(pathpacket["trace_rvas"]) == (116 + 10 * n if n else 37)
    assert read_bytes(actual["pages"], d + 0xCC, 12) == b"".join(
        x.to_bytes(4, "little") for x in (a, a + size, a + size)
    )
    if n:
        assert (
            read_bytes(actual["pages"], o, size)
            == read_bytes(packet["pages"], o, size)
            == read_bytes(actual["pages"], a, size)
        )
        assert pathpacket["imported"]["entry_esp"] == g - 128
        assert pathpacket["imported"]["words"] == [0x789463, 0x12345678, 0, size]
        assert len(pathpacket["allocation_packet"]["events"]) == 27
        assert len(pathpacket["scalar_packet"]["events"]) == 6 + 4 * n
    else:
        assert all(
            pathpacket[k] is None
            for k in ("allocation_packet", "scalar_packet", "imported")
        )
    reads = {r["address"] for r in actual["events"] if r["access"] == "read"}
    assert s + 0xD4 not in reads
    for off in STRINGS:
        assert s + off not in reads and s + off + 20 not in reads
    assert not {0x3574CA, 0x3435D9, 0x8270, 0x3703E0}.intersection(
        int(pc, 16) for pc in actual["trace_rvas"]
    )


@pytest.mark.parametrize("count", (0, 1, 2, 3, 17, 511))
@pytest.mark.parametrize("a", range(16))
def test_dynamic_counts_allalign_full15_and_separate_lastwriter_pages(count, a):
    packet = inputs(
        count,
        frame=0x30001000 + a,
        source=0x10000FF0 + a,
        destination=0x10002FF0 + a,
        path_source=0x20000FF9 + a,
        allocation_result=0x06001007 + a,
        profile=a % 3,
    )
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    strict_equal(packet, before)


@pytest.mark.parametrize("count", (0, 1, 511))
@pytest.mark.parametrize("flags", ORDINARY_FLAGS)
def test_all128_ordinary_flags_zero_and_positive_full_entry(count, flags):
    packet = inputs(count, flags=flags)
    actual = c.apply(**packet)
    check(actual, packet)
    assert (
        actual["path_packet"]["boundaries"]["parent_entry"]["flags"]
        == (flags & ~0x8D5) | 0x85
    )


@pytest.mark.parametrize("count", (0, 1, 2, 17, 511))
@pytest.mark.parametrize("capacity", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_source_capacity_physically_preserved_but_architecturally_unread(
    count, capacity
):
    packet = inputs(count, capacity=capacity)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("source_word", (0, 1, 0xDEAD0010, 0xFFFFFFFF))
@pytest.mark.parametrize("capacity", (0, 0xFFFFFFFF))
def test_zero_unmapped_empty_path_no_allocator_pages_or_children(
    source_word, capacity, monkeypatch
):
    packet = inputs(0, path_source=source_word, capacity=capacity)
    calls = []

    def forbidden(*a, **k):
        calls.append("allocation")
        raise AssertionError("zero reached allocation")

    monkeypatch.setattr(c.path.allocator, "_expected", forbidden)
    monkeypatch.setattr(c.path.scalar, "apply", forbidden)
    assert not {0x6000000, 0x8B7000, 0x7D6000}.intersection(packet["pages"])
    check(c.apply(**packet), packet)
    assert calls == []


@pytest.mark.parametrize("count", (0, 2))
@pytest.mark.parametrize("a", range(16))
@pytest.mark.parametrize("profile", range(3))
def test_common_old_empty14_and_copy2_complete15_after_independent_law(
    count, a, profile
):
    packet = inputs(
        count,
        frame=0x30001000 + a,
        profile=profile,
        path_source=0 if count == 0 else 0x20000FF9 + a,
        capacity=0 if count == 0 else 0xFFFFFFFF,
    )
    actual = c.apply(**packet)
    check(actual, packet)
    if count:
        from src.observatory import (
            native_movement_effect_record_copy2_semantics as predecessor,
        )

        strict_equal(actual, predecessor.apply(**packet))
    else:
        from src.observatory import (
            native_movement_effect_record_empty_copy_semantics as predecessor,
        )

        lower = {k: v for k, v in packet.items() if k != "allocation_result"}
        strict_equal(
            {k: v for k, v in actual.items() if k != "path_packet"},
            predecessor.apply(**lower),
        )


@pytest.mark.parametrize("count", (0, 1, 511))
@pytest.mark.parametrize("value", (0, 0x80000000, 0xFFFFFFFF))
def test_arbitrary_gpr_xmm_seh_cookie_and_padding(count, value):
    packet = inputs(count)
    for name in GPR:
        if name not in ("ecx", "esp"):
            packet["registers"][name] = value
    for name in XMM:
        packet["xmm"][name] = sum(value << (32 * i) for i in range(4))
    store(packet["pages"], 0, value)
    store(packet["pages"], COOKIE, value)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("count", (0, 1, 511))
def test_detached_top_child_boundary_and_primitive_snapshots(count):
    packet = inputs(count)
    before = copy.deepcopy(packet)
    wanted = independent(packet)
    actual = c.apply(**packet)
    actual["pages"].clear()
    actual["registers"].clear()
    actual["xmm"].clear()
    actual["events"].clear()
    actual["boundaries"][0]["pages"].clear()
    actual["path_packet"]["boundaries"]["parent_entry"]["pages"].clear()
    if count:
        actual["path_packet"]["allocation_packet"]["relation"].clear()
    strict_equal(packet, before)
    strict_equal(c.apply(**packet), wanted)


@pytest.mark.parametrize("count", (0, 1, 511))
@pytest.mark.parametrize(
    "g,s,d,o,a",
    [
        (0x84, 0x10000FFF, 0x10002FFF, 0x20000FFF, 0x06003008),
        (0xFFFFFFF7, 0x10000FF0, 0x10002FF0, 0x80000FF0, 0x06001000),
        (0x80000000, 0x90000FF0, 0x90002FF0, 0x20000FF9, 0x06001000),
        (0x30000FFD, 0xFFFFFECB, 0x10000FF0, 0x20000FF0, 0x06003008),
        (0x30001000, 0x30001200, 0x30001600, 0x20000FF9, 0x06001000),
        (0x30001000, 0x10000200, 0x10000334, 0x20000FF9, 0x06001000),
        (0x30001000, 0x10000FF0, 0x10002FF0, 0x7FFFFFF9, 0x06001000),
    ],
)
def test_crosspages_signed_end_bounds_parent_stack_headers_and_adjacent_records(
    count, g, s, d, o, a
):
    packet = inputs(
        count,
        frame=g,
        source=s,
        destination=d,
        path_source=o,
        allocation_result=a,
        return_address=0xFFFFFFFF,
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "kind",
    (
        "page_mapping",
        "page_mutable",
        "page_float",
        "page_short",
        "gpr_mapping",
        "gpr_bool",
        "gpr_alias",
        "gpr_extra",
        "xmm_bool",
        "xmm_large",
        "xmm_alias",
        "flags_bool",
        "missing_bit",
        "return_float",
        "return_zero",
        "allocation_bool",
        "allocation_float",
    ),
)
def test_exact_actual_input_schemas(kind):
    packet = inputs()
    if kind == "page_mapping":
        packet["pages"] = UserDict(packet["pages"])
    elif kind == "page_mutable":
        packet["pages"][0] = bytearray(packet["pages"][0])
    elif kind == "page_float":
        packet["pages"][0.0] = packet["pages"].pop(0)
    elif kind == "page_short":
        packet["pages"][0] = bytes(4095)
    elif kind == "gpr_mapping":
        packet["registers"] = UserDict(packet["registers"])
    elif kind == "gpr_bool":
        packet["registers"]["eax"] = False
    elif kind == "gpr_alias" or kind == "xmm_alias":

        class Alias(str):
            pass

        key = "registers" if kind == "gpr_alias" else "xmm"
        packet[key] = {Alias(k): v for k, v in packet[key].items()}
    elif kind == "gpr_extra":
        packet["registers"]["other"] = 0
    elif kind == "xmm_bool":
        packet["xmm"]["xmm0"] = False
    elif kind == "xmm_large":
        packet["xmm"]["xmm7"] = 2**128
    elif kind == "flags_bool":
        packet["entry_flags"] = True
    elif kind == "missing_bit":
        packet["entry_flags"] = 0x244
    elif kind == "return_float":
        packet["return_address"] = float(packet["return_address"])
    elif kind == "return_zero":
        packet["return_address"] = 0
    elif kind == "allocation_bool":
        packet["allocation_result"] = False
    else:
        packet["allocation_result"] = float(packet["allocation_result"])
    with pytest.raises(c.SmallRecordCopyError):
        c.apply(**packet)


@pytest.mark.parametrize("bit", [b for b in range(32) if not (0xAD7 >> b) & 1])
def test_each_forbidden_cpu_control_reserved_bit_before_child(bit, monkeypatch):
    packet = inputs(flags=0x246 | (1 << bit))
    calls = []

    def forbidden(**kwargs):
        calls.append("child")
        raise AssertionError("flags reached child")

    monkeypatch.setattr(c.path, "apply", forbidden)
    with pytest.raises(c.SmallRecordCopyError):
        c.apply(**packet)
    assert calls == []


@pytest.mark.parametrize(
    "kind",
    (
        "count512",
        "end_under",
        "end_fraction",
        "null_positive",
        "zero_alloc",
        "positive_zero_alloc",
        "alloc_high",
        "source_missing",
        "spare_missing",
        "data_missing",
        "heap_missing",
        "iat_missing",
        "wrong_heap",
        "wrong_iat",
        "source_overlap",
        "record_alias",
        "record_frame",
        "path_frame",
        "path_record",
        "buffers_alias",
        "source_size",
        "source_cap",
        "source_byte",
        "caller_ret",
        "return_source",
        "return_destination",
        "return_code",
        "lowframe",
        "wrapframe",
    ),
)
def test_domain_premises_reject_before_any_path_child(kind, monkeypatch):
    packet = inputs(0 if kind == "zero_alloc" else 2)
    g = packet["registers"]["esp"]
    s = 0x10000FF0
    d = 0x10002FF0
    o = 0x20000FF9
    if kind == "count512":
        store(packet["pages"], s + 0xD0, o + 4096)
    elif kind == "end_under":
        store(packet["pages"], s + 0xD0, o - 8)
    elif kind == "end_fraction":
        store(packet["pages"], s + 0xD0, o + 15)
    elif kind == "null_positive":
        store(packet["pages"], s + 0xCC, 0)
    elif kind == "zero_alloc":
        packet["allocation_result"] = 0x06001007
    elif kind == "positive_zero_alloc":
        packet["allocation_result"] = 0
    elif kind == "alloc_high":
        packet["allocation_result"] = 0x06003FF1
    elif kind in ("source_missing", "spare_missing"):
        packet["pages"].pop(0x20000000 if kind == "source_missing" else 0x20001000)
    elif kind in ("data_missing", "heap_missing", "iat_missing"):
        packet["pages"].pop(
            {
                "data_missing": 0x06003000,
                "heap_missing": 0x8B7000,
                "iat_missing": 0x7D6000,
            }[kind]
        )
    elif kind in ("wrong_heap", "wrong_iat"):
        store(packet["pages"], 0x8B7634 if kind == "wrong_heap" else 0x7D6220, 0)
    elif kind == "source_overlap":
        store(packet["pages"], s + 0xCC, d)
        store(packet["pages"], s + 0xD0, d + 16)
    elif kind == "record_alias":
        packet["registers"]["ecx"] = s
    elif kind == "record_frame":
        packet["registers"]["ecx"] = g - 32
    elif kind == "path_frame":
        store(packet["pages"], s + 0xCC, g - 128)
        store(packet["pages"], s + 0xD0, g - 112)
    elif kind == "path_record":
        store(packet["pages"], s + 0xCC, s + 0x130)
        store(packet["pages"], s + 0xD0, s + 0x140)
    elif kind == "buffers_alias":
        store(packet["pages"], s + 0xCC, 0x06001007)
        store(packet["pages"], s + 0xD0, 0x06001017)
    elif kind in ("source_size", "source_cap", "source_byte"):
        store(
            packet["pages"],
            s + 0x38 + {"source_size": 16, "source_cap": 20, "source_byte": 0}[kind],
            1,
            1 if kind == "source_byte" else 4,
        )
    elif kind == "caller_ret":
        store(packet["pages"], g, 0x4000004)
    elif kind.startswith("return"):
        value = {
            "return_source": o + 3,
            "return_destination": 0x06001009,
            "return_code": 0x0055B9B0,
        }[kind]
        packet["return_address"] = value
        store(packet["pages"], g, value)
    elif kind == "lowframe":
        packet["registers"]["esp"] = 127
    else:
        packet["registers"]["esp"] = 0xFFFFFFF8
    calls = []

    def forbidden(**kwargs):
        calls.append("child")
        raise AssertionError("bad domain reached child")

    monkeypatch.setattr(c.path, "apply", forbidden)
    with pytest.raises(c.SmallRecordCopyError):
        c.apply(**packet)
    assert calls == []


@pytest.mark.parametrize("count", (0, 511))
@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "extra",
        "gpr_bool",
        "gpr_mapping",
        "gpr_alias",
        "xmm_bool",
        "xmm_mapping",
        "pages_mapping",
        "page_float",
        "page_mutable",
        "events_tuple",
        "event_width_bool",
        "trace_tuple",
        "trace_noncanonical",
        "df_bool",
        "endpoint_float",
        "flags_float",
        "mask_float",
        "boundary_extra",
        "boundary_mapping",
        "boundary_df_bool",
        "boundary_page_float",
        "geometry_bool",
        "snapshot_mutable",
        "snapshot_wrong",
        "count_short",
        "trace_short",
        "parent_entry_gpr",
        "parent_entry_flags",
    ),
)
def test_full15_child_closed_schema_and_parent_boundary(count, kind, monkeypatch):
    def forged(**kwargs):
        child = clone_law.independent(kwargs)
        if kind == "missing":
            child.pop("source_snapshot")
        elif kind == "extra":
            child["extra"] = 0
        elif kind == "gpr_bool":
            child["registers"]["eax"] = False
        elif kind == "gpr_mapping":
            child["registers"] = UserDict(child["registers"])
        elif kind == "gpr_alias":

            class Alias(str):
                pass

            child["registers"] = {Alias(k): v for k, v in child["registers"].items()}
        elif kind == "xmm_bool":
            child["xmm"]["xmm0"] = False
        elif kind == "xmm_mapping":
            child["xmm"] = UserDict(child["xmm"])
        elif kind == "pages_mapping":
            child["pages"] = UserDict(child["pages"])
        elif kind == "page_float":
            child["pages"][0.0] = child["pages"].pop(0)
        elif kind == "page_mutable":
            child["pages"][0] = bytearray(child["pages"][0])
        elif kind == "events_tuple":
            child["events"] = tuple(child["events"])
        elif kind == "event_width_bool":
            child["events"][0]["width"] = True
        elif kind == "trace_tuple":
            child["trace_rvas"] = tuple(child["trace_rvas"])
        elif kind == "trace_noncanonical":
            child["trace_rvas"][0] = "0x00000ABC"
        elif kind == "df_bool":
            child["df"] = False
        elif kind == "endpoint_float":
            child["endpoint"] = float(child["endpoint"])
        elif kind == "flags_float":
            child["flags"] = float(child["flags"])
        elif kind == "mask_float":
            child["flag_mask"] = float(child["flag_mask"])
        elif kind == "boundary_extra":
            child["boundaries"]["parent_entry"]["extra"] = 0
        elif kind == "boundary_mapping":
            child["boundaries"] = UserDict(child["boundaries"])
        elif kind == "boundary_df_bool":
            child["boundaries"]["reserve_return"]["df"] = False
        elif kind == "boundary_page_float":
            pages = child["boundaries"]["reserve_return"]["pages"]
            pages[0.0] = pages.pop(0)
        elif kind == "geometry_bool":
            child["geometry"]["source"] = True
        elif kind == "snapshot_mutable":
            child["source_snapshot"] = bytearray(child["source_snapshot"])
        elif kind == "snapshot_wrong":
            child["source_snapshot"] = bytes(1)
        elif kind == "count_short":
            child["events"].pop()
        elif kind == "trace_short":
            child["trace_rvas"].pop()
        elif kind == "parent_entry_gpr":
            child["boundaries"]["parent_entry"]["registers"]["ebx"] ^= 1
        else:
            child["boundaries"]["parent_entry"]["flags"] ^= 4
        return child

    monkeypatch.setattr(c.path, "apply", forged)
    with pytest.raises(c.SmallRecordCopyError):
        c.apply(**inputs(count))


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "relation_extra",
        "request_float",
        "result_bool",
        "metadata",
        "flags_bool",
        "mask_float",
        "register_bool",
        "stack_mutable",
        "payload_mutable",
        "events_tuple",
        "event_value_bool",
        "stack_corrupt",
        "payload_corrupt",
        "events_wrong",
        "return_register_diverges",
    ),
)
@pytest.mark.parametrize("count", (1, 511))
def test_seven_field_allocator_packet_and_actual_return_join(count, kind, monkeypatch):
    def forged(**kwargs):
        child = clone_law.independent(kwargs)
        allocated = child["allocation_packet"]
        if kind == "extra":
            allocated["extra"] = 0
        elif kind == "relation_extra":
            allocated["relation"]["extra"] = 0
        elif kind == "request_float":
            allocated["relation"]["request"] = float(allocated["relation"]["request"])
        elif kind == "result_bool":
            allocated["relation"]["result"] = True
        elif kind == "metadata":
            allocated["relation"]["metadata"] = 0
        elif kind == "flags_bool":
            allocated["flags"] = False
        elif kind == "mask_float":
            allocated["flag_mask"] = float(allocated["flag_mask"])
        elif kind == "register_bool":
            allocated["registers"]["eax"] = True
        elif kind == "stack_mutable":
            allocated["stack"] = bytearray(allocated["stack"])
        elif kind == "payload_mutable":
            allocated["payload"] = bytearray(allocated["payload"])
        elif kind == "events_tuple":
            allocated["events"] = tuple(allocated["events"])
        elif kind == "event_value_bool":
            allocated["events"][0]["value"] = False
        elif kind == "stack_corrupt":
            allocated["stack"] = (
                bytes([allocated["stack"][0] ^ 1]) + allocated["stack"][1:]
            )
        elif kind == "payload_corrupt":
            allocated["payload"] = (
                bytes([allocated["payload"][0] ^ 1]) + allocated["payload"][1:]
            )
        elif kind == "events_wrong":
            allocated["events"][0]["value"] ^= 1
        else:
            allocated["registers"]["eax"] ^= 4
        return child

    monkeypatch.setattr(c.path, "apply", forged)
    with pytest.raises(c.SmallRecordCopyError):
        c.apply(**inputs(count))


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "snapshot_short",
        "snapshot_corrupt",
        "snapshot_mutable",
        "df_bool",
        "pages_mapping",
        "trace_tuple",
        "trace_short",
        "events_tuple",
        "events_short",
        "return_flag_diverges",
        "return_gpr_diverges",
        "return_pages_diverge",
        "endpoint_wrong",
    ),
)
@pytest.mark.parametrize("count", (1, 511))
def test_ten_field_scalar_packet_actual_snapshot_and_checkpoint_join(
    count, kind, monkeypatch
):
    def forged(**kwargs):
        child = clone_law.independent(kwargs)
        scalar = child["scalar_packet"]
        if kind == "extra":
            scalar["extra"] = 0
        elif kind == "snapshot_short":
            scalar["source_snapshot"] = scalar["source_snapshot"][:-1]
        elif kind == "snapshot_corrupt":
            scalar["source_snapshot"] = (
                bytes([scalar["source_snapshot"][0] ^ 1])
                + scalar["source_snapshot"][1:]
            )
        elif kind == "snapshot_mutable":
            scalar["source_snapshot"] = bytearray(scalar["source_snapshot"])
        elif kind == "df_bool":
            scalar["df"] = False
        elif kind == "pages_mapping":
            scalar["pages"] = UserDict(scalar["pages"])
        elif kind == "trace_tuple":
            scalar["trace_rvas"] = tuple(scalar["trace_rvas"])
        elif kind == "trace_short":
            scalar["trace_rvas"].pop()
        elif kind == "events_tuple":
            scalar["events"] = tuple(scalar["events"])
        elif kind == "events_short":
            scalar["events"].pop()
        elif kind == "return_flag_diverges":
            scalar["flags"] ^= 4
        elif kind == "return_gpr_diverges":
            scalar["registers"]["ecx"] ^= 1
        elif kind == "return_pages_diverge":
            scalar["pages"][0] = (
                bytes([scalar["pages"][0][0] ^ 1]) + scalar["pages"][0][1:]
            )
        else:
            scalar["endpoint"] += 4
        return child

    monkeypatch.setattr(c.path, "apply", forged)
    with pytest.raises(c.SmallRecordCopyError):
        c.apply(**inputs(count))


@pytest.mark.parametrize("count", (0, 1, 511))
@pytest.mark.parametrize(
    "kind",
    (
        "gpr",
        "xmm",
        "flags",
        "geometry",
        "read_wrong",
        "write_forbidden",
        "pages_without_event",
        "header",
        "source_snapshot",
        "boundary_order",
        "boundary_prefix",
        "boundary_page",
        "boundary_xmm",
    ),
)
def test_complete_terminal_replay_geometry_and_checkpoint_byte_joins(
    count, kind, monkeypatch
):
    def forged(**kwargs):
        child = clone_law.independent(kwargs)
        if kind == "gpr":
            child["registers"]["edx"] ^= 1
        elif kind == "xmm":
            child["xmm"]["xmm7"] ^= 1
        elif kind == "flags":
            child["flags"] ^= 4
        elif kind == "geometry":
            child["geometry"]["destination_header"] += 4
        elif kind == "read_wrong":
            next(e for e in child["events"] if e["access"] == "read")["value"] ^= 1
        elif kind == "write_forbidden":
            e = next(e for e in child["events"] if e["access"] == "write")
            e["address"] = kwargs["registers"]["edi"]
        elif kind == "pages_without_event":
            child["pages"][0x12340000] = (
                bytes([child["pages"][0x12340000][0] ^ 1])
                + child["pages"][0x12340000][1:]
            )
        elif kind == "header":
            at = kwargs["registers"]["ecx"]
            store(child["pages"], at, 1)
        elif kind == "source_snapshot":
            child["source_snapshot"] = (
                bytes(1)
                if not count
                else bytes([child["source_snapshot"][0] ^ 1])
                + child["source_snapshot"][1:]
            )
        elif kind == "boundary_order":
            child["boundaries"] = {
                k: child["boundaries"][k] for k in reversed(child["boundaries"])
            }
        elif kind == "boundary_prefix":
            child["boundaries"]["reserve_return"]["events"][0]["value"] ^= 1
        elif kind == "boundary_page":
            q = child["boundaries"]["reserve_return"]["pages"]
            q[0x12340000] = bytes([q[0x12340000][0] ^ 1]) + q[0x12340000][1:]
        else:
            child["boundaries"]["reserve_entry"]["xmm"]["xmm0"] ^= 1
        return child

    monkeypatch.setattr(c.path, "apply", forged)
    with pytest.raises(c.SmallRecordCopyError):
        c.apply(**inputs(count))


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "word_bool",
        "words_tuple",
        "esp_float",
        "gpr_bool",
        "page_mapping",
        "event_tuple",
        "flags_bool",
        "word_wrong",
        "esp_wrong",
        "prefix_wrong",
    ),
)
def test_actual_heapalloc_import_frame_and_closed_state(kind, monkeypatch):
    def forged(**kwargs):
        child = clone_law.independent(kwargs)
        state = child["imported"]
        if kind == "extra":
            state["extra"] = 0
        elif kind == "word_bool":
            state["words"][2] = False
        elif kind == "words_tuple":
            state["words"] = tuple(state["words"])
        elif kind == "esp_float":
            state["entry_esp"] = float(state["entry_esp"])
        elif kind == "gpr_bool":
            state["registers"]["edx"] = False
        elif kind == "page_mapping":
            state["pages"] = UserDict(state["pages"])
        elif kind == "event_tuple":
            state["events"] = tuple(state["events"])
        elif kind == "flags_bool":
            state["flags"] = True
        elif kind == "word_wrong":
            state["words"][3] += 8
        elif kind == "esp_wrong":
            state["entry_esp"] -= 4
        else:
            state["events"][0]["value"] ^= 1
        return child

    monkeypatch.setattr(c.path, "apply", forged)
    with pytest.raises(c.SmallRecordCopyError):
        c.apply(**inputs(3))


@pytest.mark.parametrize("count", (0, 1, 511))
def test_checked_actual_child_transport_one_call_complete_input_and_terminal(
    count, monkeypatch
):
    packet = inputs(count, flags=0xAD7)
    wanted = independent(packet)
    calls = []

    def child(**kwargs):
        calls.append(copy.deepcopy(kwargs))
        lower = clone_law.independent(kwargs)
        strict_equal(lower, wanted["path_packet"])
        return lower

    monkeypatch.setattr(c.path, "apply", child)
    check(c.apply(**packet), packet)
    assert len(calls) == 1
    assert calls[0]["registers"]["esp"] == packet["registers"]["esp"] - 40
    assert calls[0]["registers"]["ecx"] == packet["registers"]["ecx"] + 0xCC
    assert calls[0]["entry_flags"] == 0x287 and calls[0]["return_address"] == 0x55BBCA


def test_valid_nested_trace_semantics_are_explicitly_trusted(monkeypatch):
    def child(**kwargs):
        result = clone_law.independent(kwargs)
        result["scalar_packet"]["trace_rvas"][0] = "0x00123456"
        return result

    monkeypatch.setattr(c.path, "apply", child)
    packet = inputs(3)
    wanted = independent(packet)
    wanted["path_packet"]["scalar_packet"]["trace_rvas"][0] = "0x00123456"
    strict_equal(c.apply(**packet), wanted)


def test_foreign_dependency_error_normalized(monkeypatch):
    def child(**kwargs):
        raise RuntimeError("foreign logical child")

    monkeypatch.setattr(c.path, "apply", child)
    with pytest.raises(c.SmallRecordCopyError, match="foreign logical child"):
        c.apply(**inputs())


def test_closed_actual_api_source_body_pins_and_no_execution_or_fixture():
    sig = inspect.signature(c.apply)
    assert tuple(sig.parameters) == (
        "pages",
        "registers",
        "xmm",
        "return_address",
        "entry_flags",
        "allocation_result",
    )
    assert all(
        p.kind == inspect.Parameter.KEYWORD_ONLY
        and p.default == inspect.Parameter.empty
        for p in sig.parameters.values()
    )
    assert c.ANALYSIS_KIND == "pe_native_movement_effect_record_small_copy_semantics"
    assert c.BODY_PINS[0x15B9B0] == (
        772,
        "3846fdb1ca2ebc1b4b6e83a64994f82d4907938345ff0d856c9bbea690957fc6",
    )
    assert len(c.BODY_PINS) == 9 and sum(n for n, h in c.BODY_PINS.values()) == 1500
    tree = ast.parse(inspect.getsource(c))
    assert not any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in ("_fixture", "_run_case")
        for n in ast.walk(tree)
    )
    assert not any(
        isinstance(n, (ast.Import, ast.ImportFrom)) and "unicorn" in ast.unparse(n)
        for n in ast.walk(tree)
    )
