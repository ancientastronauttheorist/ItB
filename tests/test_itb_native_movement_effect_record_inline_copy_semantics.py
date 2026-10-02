"""Independent general inline movement record-copy source oracle.

Only handwritten prior TEST laws create expected values. Production apply is
called solely as the actual result. Full nested instruction labels remain the
parent's declared trust boundary; typed byte/access/checkpoint joins are closed.
"""

import copy
import inspect
from collections import UserDict
import pytest
from src.observatory import native_movement_effect_record_inline_copy_semantics as c
from tests import test_itb_native_movement_effect_record_small_copy_semantics as old
from tests import test_itb_native_movement_inline_string_copy_semantics as inline_law
from tests import test_itb_native_movement_path_small_clone_semantics as clone_law

store, read_bytes, strict_equal = old.store, old.read_bytes, old.strict_equal
STRINGS, RETURNS, FIELDS, OWNER, CALL_CHILD = (
    old.STRINGS,
    old.RETURNS,
    old.FIELDS,
    old.OWNER,
    old.CALL_CHILD,
)
COOKIE = 0x893F28
KEYS = old.KEYS | {"string_packets"}
COMMON = {"registers", "xmm", "pages", "events", "flags", "flag_mask", "df", "endpoint"}


def inputs(count=2, *, lengths=(0, 1, 2, 3, 4, 7, 8, 15), **kwargs):
    packet = old.inputs(count, **kwargs)
    g = packet["registers"]["esp"]
    s = int.from_bytes(read_bytes(packet["pages"], g + 4, 4), "little")
    for index, (off, length) in enumerate(zip(STRINGS, lengths)):
        for byte in range(16):
            # Raw inline bytes may contain NUL; count defines the selected copy.
            store(packet["pages"], s + off + byte, (index * 31 + byte * 17) & 255, 1)
        store(packet["pages"], s + off + 16, length)
        store(packet["pages"], s + off + 20, 15)
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
    string_packets = []
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
            edx=regs["edx"] if index == 7 else t,
            esp=cframe,
        )
        capture("string", "entry", index, 0x80D0, 0x85)
        # Compose only the independently handwritten full inline TEST law.
        child = inline_law.independent(
            dict(
                pages=dict(memory),
                registers=dict(regs),
                xmm=dict(packet["xmm"]),
                return_address=0x400000 + RETURNS[index],
                entry_flags=0x87,
            )
        )
        prefix = copy.deepcopy(events)
        for state in child["boundaries"]:
            row = copy.deepcopy(state)
            phase = row.pop("phase")
            row.update(
                kind="memcpy", name=phase, index=index, events=prefix + row["events"]
            )
            boundaries.append(row)
        string_packets.append(copy.deepcopy(child))
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
    regs.update(eax=j, ecx=h, esp=p)
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
        length = int.from_bytes(read_bytes(packet["pages"], s + off + 16, 4), "little")
        record[off : off + length] = read_bytes(packet["pages"], s + off, length)
        record[off + length] = 0
        record[off + 16 : off + 20] = length.to_bytes(4, "little")
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
    # Later inline helpers overwrite only their actual positive child slots.
    # The path oracle already independently supplied all earlier/deeper bytes.
    for index in (5, 6, 7):
        off = STRINGS[index]
        length = int.from_bytes(read_bytes(packet["pages"], s + off + 16, 4), "little")
        if length:
            for delta, value in (
                (68, length),
                (72, s + off),
                (76, d + off),
                (80, 0x4081A8),
                (84, length),
                (88, d + off),
            ):
                store(final, g - delta, value)
    store(final, 0, seh)
    strict_equal(memory, final)
    trace = []
    string_index = 0
    for pc in OWNER:
        trace.append(f"0x{pc:08x}")
        if pc == 0x15BBC5:
            trace.extend(joined["trace_rvas"])
        elif pc in CALL_CHILD:
            trace.extend(string_packets[string_index]["trace_rvas"])
            string_index += 1
    return dict(
        source_address=s,
        record_address=d,
        record_bytes=bytes(record),
        source_snapshot=read_bytes(packet["pages"], s, 308),
        registers=dict(initial, eax=d, ecx=cookie ^ f, edx=regs["edx"], esp=g + 8),
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
        string_packets=copy.deepcopy(string_packets),
    )


def check(actual, packet):
    wanted = independent(packet)
    strict_equal(actual, wanted)
    assert type(actual) is dict and set(actual) == KEYS and len(KEYS) == 16
    g, s, d = (
        packet["registers"]["esp"],
        wanted["source_address"],
        wanted["record_address"],
    )
    o = int.from_bytes(read_bytes(packet["pages"], s + 0xCC, 4), "little")
    count = (
        int.from_bytes(read_bytes(packet["pages"], s + 0xD0, 4), "little") - o
    ) // 8
    lengths = [
        int.from_bytes(read_bytes(packet["pages"], s + off + 16, 4), "little")
        for off in STRINGS
    ]
    extra_trace = sum(
        38 + 6 * (n // 4) + 6 * (n % 4) + 2 * bool(n % 4) + 2 * (d > s)
        for n in lengths
        if n
    )
    extra_events = sum(15 + 2 * (n // 4) + 2 * (n % 4) for n in lengths if n)
    assert (
        len(actual["trace_rvas"]) == (571 + 10 * count if count else 492) + extra_trace
    )
    assert len(actual["events"]) == (364 + 4 * count if count else 315) + extra_events
    assert len(actual["boundaries"]) == (23 if count else 20) + 2 * sum(
        n > 0 for n in lengths
    )
    assert type(actual["string_packets"]) is list and len(actual["string_packets"]) == 8
    assert all(set(row) == old.BOUNDARY_KEYS for row in actual["boundaries"])
    replay = dict(packet["pages"])
    for ev in actual["events"]:
        at, width, value = ev["address"], ev["width"], ev["value"]
        if ev["access"] == "read":
            assert int.from_bytes(read_bytes(replay, at, width), "little") == value
        else:
            store(replay, at, value, width)
    strict_equal(replay, actual["pages"])
    assert read_bytes(actual["pages"], s, 308) == read_bytes(packet["pages"], s, 308)
    assert read_bytes(actual["pages"], g, 8) == read_bytes(packet["pages"], g, 8)
    assert read_bytes(actual["pages"], 0, 4) == read_bytes(packet["pages"], 0, 4)
    assert read_bytes(actual["pages"], COOKIE & ~4095, 4096) == read_bytes(
        packet["pages"], COOKIE & ~4095, 4096
    )
    for index, (off, length) in enumerate(zip(STRINGS, lengths)):
        field = actual["string_packets"][index]
        assert len(field["boundaries"]) == (2 if length else 0)
        assert field["geometry"]["count"] == length
        assert read_bytes(actual["pages"], d + off, length) == read_bytes(
            packet["pages"], s + off, length
        )
        assert read_bytes(actual["pages"], d + off + length, 1) == b"\0"
        assert read_bytes(
            actual["pages"], d + off + length + 1, 15 - length
        ) == read_bytes(packet["pages"], d + off + length + 1, 15 - length)
    # The copied scalar field mask plus NUL/length/capacity/path header predicts
    # all changed record bytes independently of the reported boundary metadata.
    written = {off + i for off, width in FIELDS for i in range(width)} | set(
        range(0xCC, 0xD8)
    )
    for off, length in zip(STRINGS, lengths):
        written.update(range(off, off + length + 1))
        written.update(range(off + 16, off + 24))
    assert len(written) == 183 + sum(lengths)
    assert all(
        actual["record_bytes"][i] == read_bytes(packet["pages"], d + i, 1)[0]
        for i in range(308)
        if i not in written
    )


PROFILES = ((0,) * 8, (15,) * 8, (0, 1, 2, 3, 4, 7, 8, 15), (15, 0, 9, 0, 2, 0, 4, 0))


@pytest.mark.parametrize("count", (0, 1, 2, 17, 511))
@pytest.mark.parametrize("lengths", PROFILES)
def test_full_sixteen_selected_path_counts_and_string_profiles(count, lengths):
    packet = inputs(count, lengths=lengths)
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    strict_equal(packet, before)


@pytest.mark.parametrize("field", range(8))
@pytest.mark.parametrize("length", range(16))
@pytest.mark.parametrize("count", (0, 2))
def test_each_inline_field_each_length_and_checkpoint_index(field, length, count):
    lengths = [0] * 8
    lengths[field] = length
    packet = inputs(count, lengths=lengths)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("flags", old.ORDINARY_FLAGS)
@pytest.mark.parametrize("count", (0, 2))
def test_all_ordinary_flags_with_mixed_inline_lengths(flags, count):
    packet = inputs(count, flags=flags)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("flags", (2, 0x202, 0xAD7))
def test_maximum_path_ordinary_flag_edges(flags):
    packet = inputs(511, lengths=PROFILES[3], flags=flags)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("count", (0, 1, 2, 17, 511))
def test_old_full_fifteen_projection_when_all_strings_empty(count):
    packet = inputs(count, lengths=(0,) * 8)
    g = packet["registers"]["esp"]
    s = int.from_bytes(read_bytes(packet["pages"], g + 4, 4), "little")
    for off in STRINGS:
        store(packet["pages"], s + off, 0, 1)
    actual = c.apply(**packet)
    common = {k: copy.deepcopy(v) for k, v in actual.items() if k != "string_packets"}
    strict_equal(common, old.independent(packet))
    check(actual, packet)


@pytest.mark.parametrize("count", (0, 3))
@pytest.mark.parametrize(
    "g,s,d,o,a",
    (
        (0x84, 0x10000FFF, 0x10002FFF, 0x20000FFF, 0x06003008),
        (0xFFFFFFF7, 0x10000FF0, 0x10002FF0, 0x80000FF0, 0x06001000),
        (0x80000000, 0x90000FF0, 0x90002FF0, 0x20000FF9, 0x06001000),
        (0x30000FFD, 0xFFFFFECB, 0x10000FF0, 0x20000FF0, 0x06003008),
        (0x30001000, 0x30001200, 0x30001600, 0x20000FF9, 0x06001000),
        (0x30001000, 0x10000200, 0x10000334, 0x20000FF9, 0x06001000),
        (0x30001000, 0x10000FF0, 0x10002FF0, 0x7FFFFFF9, 0x06001000),
    ),
)
def test_crosspages_signed_upper_bounds_adjacent_records_and_stack_pages(
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


@pytest.mark.parametrize("alignment", (0, 7, 15, 31))
@pytest.mark.parametrize("profile", range(4))
def test_selected_alignment_payload_and_page_patterns(alignment, profile):
    packet = inputs(
        3,
        frame=0x30001000 + alignment,
        source=0x10000FF0 + alignment,
        destination=0x10002FF0 + alignment,
        path_source=0x20000FF0 + alignment,
        allocation_result=0x06001000 + alignment,
        lengths=PROFILES[profile],
        profile=profile,
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "last,previous", ((0, 0), (0, 15), (1, 0), (3, 4), (4, 0), (15, 0))
)
@pytest.mark.parametrize("count", (0, 2))
def test_exact_edx_carry_at_path_entry_and_last_field(last, previous, count):
    lengths = [0] * 8
    lengths[4] = previous
    lengths[6] = previous
    lengths[7] = last
    packet = inputs(count, lengths=lengths)
    actual = c.apply(**packet)
    check(actual, packet)
    path_entry = next(
        row for row in actual["boundaries"] if row["endpoint"] == 0x49A8E0
    )
    assert (
        path_entry["registers"]["edx"]
        == actual["string_packets"][4]["registers"]["edx"]
    )
    last_entry = next(
        row
        for row in actual["boundaries"]
        if row["kind"] == "string" and row["name"] == "entry" and row["index"] == 7
    )
    assert (
        last_entry["registers"]["edx"]
        == actual["string_packets"][6]["registers"]["edx"]
    )
    assert actual["registers"]["edx"] == actual["string_packets"][7]["registers"]["edx"]


def reject(packet, monkeypatch):
    writes, children = [], []
    before = copy.deepcopy(packet)
    original = c._write

    def observed(*args, **kwargs):
        writes.append("write")
        return original(*args, **kwargs)

    def forbidden(**kwargs):
        children.append("child")
        raise AssertionError("invalid parent reached child")

    with monkeypatch.context() as patch:
        patch.setattr(c, "_write", observed)
        patch.setattr(c.string, "apply", forbidden)
        patch.setattr(c.path, "apply", forbidden)
        with pytest.raises(c.InlineRecordCopyError):
            c.apply(**packet)
        assert writes == [] and children == []
    strict_equal(packet, before)


@pytest.mark.parametrize("field", range(8))
@pytest.mark.parametrize("kind", ("length16", "capacity16", "capacity0"))
def test_each_string_header_premise_before_child(field, kind, monkeypatch):
    packet = inputs()
    g = packet["registers"]["esp"]
    s = int.from_bytes(read_bytes(packet["pages"], g + 4, 4), "little")
    store(
        packet["pages"],
        s + STRINGS[field] + (16 if kind == "length16" else 20),
        16 if kind != "capacity0" else 0,
    )
    reject(packet, monkeypatch)


@pytest.mark.parametrize("page", (0x408000, 0x770000))
def test_unrelated_code_page_rejected_before_any_owner_write_or_child(
    page, monkeypatch
):
    packet = inputs()
    packet["pages"][page] = bytes(4096)
    reject(packet, monkeypatch)


@pytest.mark.parametrize(
    "kind",
    (
        "pages_mapping",
        "pages_float",
        "pages_mutable",
        "pages_short",
        "gpr_bool",
        "gpr_alias",
        "gpr_extra",
        "xmm_bool",
        "xmm_large",
        "xmm_alias",
        "return_float",
        "return_bool",
        "return_zero",
        "flags_bool",
        "flags_missing_bit",
        "allocation_bool",
        "allocation_float",
        "allocation_zero",
        "heap_word",
        "iat_word",
        "count512",
        "path_fraction",
        "path_negative",
        "path_overlap",
        "record_overlap",
        "frame_wrap",
        "source_unmapped",
        "caller_return",
        "return_path",
        "return_runtime",
    ),
)
def test_typed_and_geometry_premises_before_writes(kind, monkeypatch):
    packet = inputs()
    g, d = packet["registers"]["esp"], packet["registers"]["ecx"]
    s = int.from_bytes(read_bytes(packet["pages"], g + 4, 4), "little")
    o = int.from_bytes(read_bytes(packet["pages"], s + 0xCC, 4), "little")
    if kind == "pages_mapping":
        packet["pages"] = UserDict(packet["pages"])
    elif kind == "pages_float":
        value = packet["pages"].pop(0x12340000, bytes(4096))
        packet["pages"][float(0x12340000)] = value
    elif kind == "pages_mutable":
        packet["pages"][0] = bytearray(packet["pages"][0])
    elif kind == "pages_short":
        packet["pages"][0] = bytes(4095)
    elif kind.startswith(("gpr_", "xmm_")):
        group, sub = kind.split("_", 1)
        key = "registers" if group == "gpr" else "xmm"
        name = "eax" if group == "gpr" else "xmm0"
        if sub == "bool":
            packet[key][name] = True
        elif sub == "large":
            packet[key][name] = 1 << 128
        elif sub == "extra":
            packet[key]["extra"] = 0
        elif sub == "alias":
            packet[key] = UserDict(packet[key])
    elif kind.startswith("return_") and kind in (
        "return_float",
        "return_bool",
        "return_zero",
    ):
        packet["return_address"] = {
            "return_float": float(packet["return_address"]),
            "return_bool": True,
            "return_zero": 0,
        }[kind]
    elif kind == "flags_bool":
        packet["entry_flags"] = True
    elif kind == "flags_missing_bit":
        packet["entry_flags"] = 0x244
    elif kind.startswith("allocation_"):
        packet["allocation_result"] = {
            "allocation_bool": True,
            "allocation_float": float(packet["allocation_result"]),
            "allocation_zero": 0,
        }[kind]
    elif kind == "heap_word":
        store(packet["pages"], 0x8B7634, 0)
    elif kind == "iat_word":
        store(packet["pages"], 0x7D6220, 0)
    elif kind == "count512":
        store(packet["pages"], s + 0xD0, o + 4096)
    elif kind == "path_fraction":
        store(packet["pages"], s + 0xD0, o + 17)
    elif kind == "path_negative":
        store(packet["pages"], s + 0xD0, o - 8)
    elif kind == "path_overlap":
        store(packet["pages"], s + 0xCC, d)
        store(packet["pages"], s + 0xD0, d + 16)
    elif kind == "record_overlap":
        packet["registers"]["ecx"] = s
    elif kind == "frame_wrap":
        packet["registers"]["esp"] = 0xFFFFFFF8
    elif kind == "source_unmapped":
        store(packet["pages"], g + 4, 0x50000000)
    elif kind == "caller_return":
        store(packet["pages"], g, 0x04000004)
    elif kind in ("return_path", "return_runtime"):
        at = o if kind == "return_path" else 0x8B7000
        packet["return_address"] = at
        store(packet["pages"], g, at)
    reject(packet, monkeypatch)


@pytest.mark.parametrize(
    "bit", [i for i in range(32) if i not in (0, 1, 2, 4, 6, 7, 9, 11)]
)
def test_each_forbidden_ordinary_flag_bit(bit, monkeypatch):
    reject(inputs(flags=2 | (1 << bit)), monkeypatch)


@pytest.mark.parametrize("field", (0, 4, 7))
@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "geometry_bool",
        "snapshot",
        "string_bytes",
        "gpr_bool",
        "xmm_bool",
        "df_bool",
        "endpoint_float",
        "flags_bool",
        "mask_bool",
        "events_tuple",
        "trace_tuple",
        "pages_mapping",
        "restored_write",
        "reordered_events",
        "coordinated_checkpoint",
        "boundary_phase",
        "boundary_extra",
        "boundary_pages",
        "prefix_value",
        "suffix_value",
    ),
)
def test_full_inline_field14_envelope_access_checkpoint_forgeries(
    field, kind, monkeypatch
):
    packet = inputs(lengths=(15,) * 8)
    before = copy.deepcopy(packet)
    calls = []

    def forged(**child_input):
        index = len(calls)
        calls.append(index)
        child = inline_law.independent(child_input)
        if index != field:
            return child
        q = child_input["registers"]["ecx"]
        if kind == "extra":
            child["extra"] = 0
        elif kind == "missing":
            child.pop("string_bytes")
        elif kind == "geometry_bool":
            child["geometry"]["offset"] = False
        elif kind == "snapshot":
            child["source_snapshot"] = bytes(24)
        elif kind == "string_bytes":
            child["string_bytes"] = bytes(24)
        elif kind == "gpr_bool":
            child["registers"]["ecx"] = False
        elif kind == "xmm_bool":
            child["xmm"]["xmm0"] = False
        elif kind == "df_bool":
            child["df"] = False
        elif kind == "endpoint_float":
            child["endpoint"] = float(child["endpoint"])
        elif kind == "flags_bool":
            child["flags"] = True
        elif kind == "mask_bool":
            child["flag_mask"] = True
        elif kind == "events_tuple":
            child["events"] = tuple(child["events"])
        elif kind == "trace_tuple":
            child["trace_rvas"] = tuple(child["trace_rvas"])
        elif kind == "pages_mapping":
            child["pages"] = UserDict(child["pages"])
        elif kind == "restored_write":
            child["events"].extend(
                (
                    dict(access="write", address=q + 15, width=1, value=99),
                    dict(access="write", address=q + 15, width=1, value=0),
                )
            )
        elif kind == "reordered_events":
            child["events"][1], child["events"][2] = (
                child["events"][2],
                child["events"][1],
            )
        elif kind == "coordinated_checkpoint":
            child["boundaries"][0]["registers"]["eax"] += 1
            child["memcpy_packet"]["geometry"]["source"] += 1
        elif kind == "boundary_phase":
            child["boundaries"][0]["phase"] = "return"
        elif kind == "boundary_extra":
            child["boundaries"][0]["extra"] = 0
        elif kind == "boundary_pages":
            child["boundaries"][0]["pages"][0] = bytes(4096)
        elif kind == "prefix_value":
            child["events"][6]["value"] -= 1
        elif kind == "suffix_value":
            child["events"][-7]["value"] -= 1
        return child

    monkeypatch.setattr(c.string, "apply", forged)
    with pytest.raises(c.InlineRecordCopyError):
        c.apply(**packet)
    assert calls == list(range(field + 1))
    strict_equal(packet, before)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "geometry_bool",
        "register_bool",
        "xmm_bool",
        "df_bool",
        "endpoint_float",
        "events_tuple",
        "pages_mapping",
        "snapshot",
        "copied_byte",
        "missing_event",
        "extra_event",
        "float_page",
        "coordinated_byte",
        "ancestor_page",
        "flags",
        "trace_schema",
    ),
)
def test_nested_memcpy11_closed_against_actual_input(kind, monkeypatch):
    packet = inputs(lengths=(15,) * 8)
    before = copy.deepcopy(packet)
    calls = []

    def forged(**child_input):
        child = inline_law.independent(child_input)
        calls.append("string")
        out = child["memcpy_packet"]
        q = child["geometry"]["destination_object"]
        if kind == "extra":
            out["extra"] = 0
        elif kind == "missing":
            out.pop("geometry")
        elif kind == "geometry_bool":
            out["geometry"]["count"] = True
        elif kind == "register_bool":
            out["registers"]["ecx"] = False
        elif kind == "xmm_bool":
            out["xmm"]["xmm0"] = False
        elif kind == "df_bool":
            out["df"] = False
        elif kind == "endpoint_float":
            out["endpoint"] = float(out["endpoint"])
        elif kind == "events_tuple":
            out["events"] = tuple(out["events"])
        elif kind == "pages_mapping":
            out["pages"] = UserDict(out["pages"])
        elif kind == "snapshot":
            out["source_snapshot"] = bytes(15)
        elif kind == "copied_byte":
            store(out["pages"], q, 99, 1)
        elif kind == "missing_event":
            out["events"].pop(0)
        elif kind == "extra_event":
            out["events"].append(copy.deepcopy(out["events"][-1]))
        elif kind == "float_page":
            out["pages"][float(0)] = out["pages"].pop(0)
        elif kind == "coordinated_byte":
            out["events"][5]["value"] ^= 1
            out["events"][6]["value"] ^= 1
            store(out["pages"], q, out["events"][6]["value"])
            out["source_snapshot"] = (
                out["events"][6]["value"].to_bytes(4, "little")
                + out["source_snapshot"][4:]
            )
        elif kind == "ancestor_page":
            store(out["pages"], child_input["registers"]["esp"], 0)
        elif kind == "flags":
            out["flags"] = 0
        elif kind == "trace_schema":
            out["trace_rvas"][0] = "not-a-rva"
        return child

    monkeypatch.setattr(c.string, "apply", forged)
    with pytest.raises(c.InlineRecordCopyError):
        c.apply(**packet)
    assert calls == ["string"]
    strict_equal(packet, before)


@pytest.mark.parametrize("kind", ("inline_label", "memcpy_label", "path_scalar_label"))
def test_declared_canonical_instruction_metadata_trusted_and_transported(
    kind, monkeypatch
):
    packet = inputs()
    seen = []
    if kind in ("inline_label", "memcpy_label"):

        def supplied(**child_input):
            child = inline_law.independent(child_input)
            if (kind == "inline_label" and not seen) or (
                kind == "memcpy_label" and len(seen) == 1
            ):
                if kind == "inline_label":
                    child["trace_rvas"][0] = "0x000080d1"
                else:
                    child["memcpy_packet"]["trace_rvas"][0] = "0x003703e1"
            seen.append("string")
            return child

        monkeypatch.setattr(c.string, "apply", supplied)
    else:

        def supplied(**child_input):
            child = clone_law.independent(child_input)
            child["scalar_packet"]["trace_rvas"][0] = "0x0008aba1"
            seen.append("path")
            return child

        monkeypatch.setattr(c.path, "apply", supplied)
    actual = c.apply(**packet)
    wanted = independent(packet)
    if kind == "inline_label":
        wanted["string_packets"][0]["trace_rvas"][0] = "0x000080d1"
        at = wanted["trace_rvas"].index("0x000080d0")
        wanted["trace_rvas"][at] = "0x000080d1"
    elif kind == "memcpy_label":
        wanted["string_packets"][1]["memcpy_packet"]["trace_rvas"][0] = "0x003703e1"
    elif kind == "path_scalar_label":
        wanted["path_packet"]["scalar_packet"]["trace_rvas"][0] = "0x0008aba1"
    strict_equal(actual, wanted)
    assert seen


@pytest.mark.parametrize("count", (0, 2, 511))
def test_detached_all_top_field_child_and_boundary_snapshots(count):
    packet = inputs(count)
    before = copy.deepcopy(packet)
    wanted = independent(packet)
    first = c.apply(**packet)
    second = c.apply(**packet)
    first["registers"].clear()
    first["pages"].clear()
    first["events"].clear()
    first["string_packets"][1]["memcpy_packet"]["pages"].clear()
    first["string_packets"][1]["boundaries"][0]["registers"].clear()
    first["boundaries"][0]["pages"].clear()
    first["path_packet"]["registers"].clear()
    if count:
        first["path_packet"]["allocation_packet"]["relation"].clear()
    strict_equal(second, wanted)
    strict_equal(packet, before)
    strict_equal(c.apply(**packet), wanted)


@pytest.mark.parametrize("pointer", (0, 0xFFFFFFFF, 0xDEAD1234))
@pytest.mark.parametrize("capacity", (0, 7, 0xFFFFFFFF))
def test_zero_path_unmapped_begin_and_unread_capacity_with_positive_strings(
    pointer, capacity
):
    packet = inputs(0, lengths=(15,) * 8)
    g = packet["registers"]["esp"]
    s = int.from_bytes(read_bytes(packet["pages"], g + 4, 4), "little")
    store(packet["pages"], s + 0xCC, pointer)
    store(packet["pages"], s + 0xD0, pointer)
    store(packet["pages"], s + 0xD4, capacity)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "kind",
    (
        "top_extra",
        "top_df_bool",
        "geometry_bool",
        "tuple_events",
        "terminal_edx",
        "checkpoint_pages",
        "checkpoint_registers",
        "checkpoint_order",
        "allocation_extra",
        "allocation_request_bool",
        "allocation_payload_mutable",
        "allocation_return_flags",
        "scalar_extra",
        "scalar_df_bool",
        "scalar_snapshot",
        "scalar_return_events",
        "import_words_bool",
        "import_endpoint_float",
    ),
)
def test_inherited_path15_allocation7_scalar10_join_closure(kind, monkeypatch):
    packet = inputs(2)
    before = copy.deepcopy(packet)
    calls = []

    def forged(**child_input):
        calls.append("path")
        out = clone_law.independent(child_input)
        if kind == "top_extra":
            out["extra"] = 0
        elif kind == "top_df_bool":
            out["df"] = False
        elif kind == "geometry_bool":
            out["geometry"]["source"] = True
        elif kind == "tuple_events":
            out["events"] = tuple(out["events"])
        elif kind == "terminal_edx":
            out["registers"]["edx"] -= 8
        elif kind == "checkpoint_pages":
            out["boundaries"]["reserve_entry"]["pages"][0] = bytes(4096)
        elif kind == "checkpoint_registers":
            out["boundaries"]["parent_entry"]["registers"]["edx"] = 0
        elif kind == "checkpoint_order":
            out["boundaries"] = dict(reversed(list(out["boundaries"].items())))
        elif kind == "allocation_extra":
            out["allocation_packet"]["extra"] = 0
        elif kind == "allocation_request_bool":
            out["allocation_packet"]["relation"]["request"] = True
        elif kind == "allocation_payload_mutable":
            out["allocation_packet"]["payload"] = bytearray(
                out["allocation_packet"]["payload"]
            )
        elif kind == "allocation_return_flags":
            out["allocation_packet"]["flags"] ^= 4
        elif kind == "scalar_extra":
            out["scalar_packet"]["extra"] = 0
        elif kind == "scalar_df_bool":
            out["scalar_packet"]["df"] = False
        elif kind == "scalar_snapshot":
            out["scalar_packet"]["source_snapshot"] = bytes(16)
        elif kind == "scalar_return_events":
            out["scalar_packet"]["events"].pop(0)
        elif kind == "import_words_bool":
            out["imported"]["words"][2] = False
        elif kind == "import_endpoint_float":
            out["imported"]["endpoint"] = float(out["imported"]["endpoint"])
        return out

    monkeypatch.setattr(c.path, "apply", forged)
    with pytest.raises(c.InlineRecordCopyError):
        c.apply(**packet)
    assert calls == ["path"]
    strict_equal(packet, before)


def test_exact_api_and_bound_owner_body():
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
    assert c.BODY_PINS[0x15B9B0] == (
        772,
        "3846fdb1ca2ebc1b4b6e83a64994f82d4907938345ff0d856c9bbea690957fc6",
    )
