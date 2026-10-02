"""Independent selected inline substring-copy parent and handwritten CRT witness.

Literal parent operations and direct last-writer pages below are independent of
production. The reviewed child trace metadata remains an explicit trust scope.
"""

from __future__ import annotations

import ast
import copy
import inspect
from collections import UserDict
import pytest
from src.observatory import native_movement_inline_string_copy_semantics as c
from tests import test_itb_native_movement_small_memcpy_semantics as scalar

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
FLAGS = tuple(
    2
    | sum(1 << bit for i, bit in enumerate((0, 2, 4, 6, 7, 9, 11)) if selector >> i & 1)
    for selector in range(128)
)
KEYS = {
    "geometry",
    "registers",
    "xmm",
    "pages",
    "events",
    "trace_rvas",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "source_snapshot",
    "string_bytes",
    "memcpy_packet",
    "boundaries",
}
STATE_KEYS = {
    "registers",
    "xmm",
    "pages",
    "events",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "phase",
}
GEOMETRY = {
    "entry",
    "source_object",
    "destination_object",
    "source_length",
    "offset",
    "requested",
    "count",
}
PREFIX = tuple(
    int(v, 16)
    for v in "80d0 80d1 80d3 80d4 80d7 80d8 80da 80dd 80de 80e1 80e3 80e9 80ec 80ee 80f0 80f3 80f5 813e 8141 8147 814a 8170 8172".split()
)
ZERO = tuple(
    int(v, 16) for v in "8174 8178 817b 818b 818d 818e 818f 8190 8193 8194".split()
)
POSITIVE = tuple(
    int(v, 16)
    for v in "815e 8162 8166 816a 8197 8199 819b 819d 819e 81a1 81a2 81a3".split()
)
SUFFIX = tuple(
    int(v, 16)
    for v in "81a8 81ab 81af 81b2 81c3 81c5 81c9 81ca 81cc 81cd 81ce 81cf".split()
)
read_bytes, word, store, put_word, equal = (
    scalar.read_bytes,
    scalar.word,
    scalar.store,
    scalar.put_word,
    scalar.equal,
)


def inputs(
    length=15,
    offset=0,
    requested=0xFFFFFFFF,
    *,
    old_length=7,
    frame=0x30001003,
    source=0x10000FF0,
    destination=0x10002FF0,
    flags=0x246,
    profile=0,
    return_address=0x04000000,
):
    spans = (
        (frame - 40, frame + 16),
        (source, source + 24),
        (destination, destination + 24),
        (0x12340000, 0x12341000),
    )
    keys = {
        p
        for lo, hi in spans
        for p in range(lo & ~4095, ((hi - 1) & ~4095) + 4096, 4096)
    }
    pages = {
        p: bytes((j * 43 + (p >> 12) * 31 + profile * 97) & 255 for j in range(4096))
        for p in keys
    }
    for i, value in enumerate((return_address, source, offset, requested)):
        put_word(pages, frame + 4 * i, value)
    for at, value in (
        (source + 16, length),
        (source + 20, 15),
        (destination + 16, old_length),
        (destination + 20, 15),
    ):
        put_word(pages, at, value)
    registers = {
        key: (0x19C31A55 + i * 0x1234567 + profile * 0x4321) & 0xFFFFFFFF
        for i, key in enumerate(GPR)
    }
    registers.update(esp=frame, ecx=destination)
    xmm = {
        key: int.from_bytes(
            bytes((i * 31 + j * 19 + profile * 67) & 255 for j in range(16)), "little"
        )
        for i, key in enumerate(XMM)
    }
    return dict(
        pages=pages,
        registers=registers,
        xmm=xmm,
        return_address=return_address,
        entry_flags=flags,
    )


def logic(value):
    return (
        (4 if (value & 255).bit_count() % 2 == 0 else 0)
        | (0x40 if value == 0 else 0)
        | (0x80 if value & 0x80000000 else 0)
    )


def independent(packet):
    initial = packet["registers"]
    g, d = initial["esp"], initial["ecx"]
    s, offset, requested = (word(packet["pages"], g + i) for i in (4, 8, 12))
    length = word(packet["pages"], s + 16)
    count = min(requested, length - offset)
    pages = dict(packet["pages"])
    events, states = [], []
    regs = dict(
        initial,
        eax=length - offset,
        ebp=g - 4,
        ebx=s,
        esi=d,
        edi=count,
        ecx=offset,
        esp=g - 16,
    )
    child = None

    def event(kind, at, value, width=4):
        if kind == "write":
            store(pages, at, value.to_bytes(width, "little"))
        else:
            assert int.from_bytes(read_bytes(pages, at, width), "little") == value
        events.append(dict(access=kind, address=at, width=width, value=value))

    def state(phase, endpoint, flags, mask):
        states.append(
            dict(
                registers=dict(regs),
                xmm=dict(packet["xmm"]),
                pages=dict(pages),
                events=copy.deepcopy(events),
                flags=flags,
                flag_mask=mask,
                df=0,
                endpoint=endpoint,
                phase=phase,
            )
        )

    for kind, at, value in (
        ("write", g - 4, initial["ebp"]),
        ("write", g - 8, initial["ebx"]),
        ("read", g + 4, s),
        ("write", g - 12, initial["esi"]),
        ("read", g + 8, offset),
        ("write", g - 16, initial["edi"]),
        ("read", s + 16, length),
        ("read", g + 12, requested),
        ("read", d + 20, 15),
    ):
        event(kind, at, value)
    trace = [f"0x{p:08x}" for p in PREFIX]
    if count:
        event("read", s + 20, 15)
        event("read", d + 20, 15)
        for at, value in (
            (g - 20, count),
            (g - 24, s + offset),
            (g - 28, d),
            (g - 32, 0x004081A8),
        ):
            event("write", at, value)
        regs.update(eax=s + offset, edx=d, esp=g - 32)
        state("entry", 0x007703E0, logic(count), 0x8C5)
        child = scalar.independent(
            dict(
                pages=dict(pages),
                registers=dict(regs),
                xmm=dict(packet["xmm"]),
                return_address=0x004081A8,
                entry_flags=(packet["entry_flags"] & 0x202) | logic(count),
            )
        )
        pages = dict(child["pages"])
        events.extend(copy.deepcopy(child["events"]))
        regs = dict(child["registers"])
        state("return", 0x004081A8, child["flags"], child["flag_mask"])
        event("read", d + 20, 15)
        event("write", d + 16, count)
        event("write", d + count, 0, 1)
        for at, value in (
            (g - 16, initial["edi"]),
            (g - 12, initial["esi"]),
            (g - 8, initial["ebx"]),
            (g - 4, initial["ebp"]),
            (g, packet["return_address"]),
        ):
            event("read", at, value)
        trace += (
            [f"0x{p:08x}" for p in POSITIVE]
            + child["trace_rvas"]
            + [f"0x{p:08x}" for p in SUFFIX]
        )
    else:
        event("read", d + 20, 15)
        event("write", d + 16, 0)
        for at, value in (
            (g - 16, initial["edi"]),
            (g - 12, initial["esi"]),
            (g - 8, initial["ebx"]),
        ):
            event("read", at, value)
        event("write", d, 0, 1)
        event("read", g - 4, initial["ebp"])
        event("read", g, packet["return_address"])
        trace += [f"0x{p:08x}" for p in ZERO]
    # Separate full-page law, not an event replay: saved owner and scalar words,
    # exact substring blit, new length and terminal NUL are the only last writers.
    final = dict(packet["pages"])
    for at, value in (
        (g - 4, initial["ebp"]),
        (g - 8, initial["ebx"]),
        (g - 12, initial["esi"]),
        (g - 16, initial["edi"]),
    ):
        put_word(final, at, value)
    if count:
        for at, value in (
            (g - 20, count),
            (g - 24, s + offset),
            (g - 28, d),
            (g - 32, 0x004081A8),
            (g - 36, count),
            (g - 40, d),
        ):
            put_word(final, at, value)
        store(final, d, read_bytes(packet["pages"], s + offset, count))
    put_word(final, d + 16, count)
    store(final, d + count, bytes(1))
    equal(pages, final)
    return dict(
        geometry=dict(
            entry=g,
            source_object=s,
            destination_object=d,
            source_length=length,
            offset=offset,
            requested=requested,
            count=count,
        ),
        registers=dict(
            initial, eax=d, ecx=0 if count else offset, edx=regs["edx"], esp=g + 16
        ),
        xmm=dict(packet["xmm"]),
        pages=final,
        events=events,
        trace_rvas=trace,
        flags=0x85,
        flag_mask=0x8D5,
        df=0,
        endpoint=packet["return_address"],
        source_snapshot=read_bytes(packet["pages"], s, 24),
        string_bytes=read_bytes(final, d, 24),
        memcpy_packet=copy.deepcopy(child),
        boundaries=states,
    )


def check(actual, packet):
    equal(actual, independent(packet))
    assert type(actual) is dict and set(actual) == KEYS
    assert set(actual["geometry"]) == GEOMETRY
    g, d, s, n = (
        actual["geometry"][key]
        for key in ("entry", "destination_object", "source_object", "count")
    )
    q, r = divmod(n, 4)
    assert len(actual["events"]) == (32 + 2 * q + 2 * r if n else 17)
    assert len(actual["trace_rvas"]) == (
        47 + len(actual["memcpy_packet"]["trace_rvas"]) if n else 33
    )
    assert len(actual["boundaries"]) == (2 if n else 0)
    if n:
        assert [len(row["events"]) for row in actual["boundaries"]] == [
            15,
            24 + 2 * q + 2 * r,
        ]
        assert [row["phase"] for row in actual["boundaries"]] == ["entry", "return"]
        assert all(set(row) == STATE_KEYS for row in actual["boundaries"])
        assert actual["boundaries"][0]["flags"] == logic(n)
        assert actual["boundaries"][0]["flag_mask"] == 0x8C5
        assert actual["registers"]["edx"] == (
            word(packet["pages"], s + actual["geometry"]["offset"] + 4 * (q - 1))
            if q
            else n
        )
    else:
        assert actual["memcpy_packet"] is None
        assert actual["registers"]["ecx"] == actual["geometry"]["offset"]
        assert actual["registers"]["edx"] == packet["registers"]["edx"]
    assert read_bytes(actual["pages"], s, 24) == read_bytes(packet["pages"], s, 24)
    assert read_bytes(actual["pages"], g, 16) == read_bytes(packet["pages"], g, 16)
    assert word(actual["pages"], d + 16) == n and word(actual["pages"], d + 20) == 15
    assert read_bytes(actual["pages"], d + n, 1) == bytes(1)
    assert read_bytes(actual["pages"], d + n + 1, 15 - n) == read_bytes(
        packet["pages"], d + n + 1, 15 - n
    )
    writes = {
        event["address"] + i
        for event in actual["events"]
        if event["access"] == "write"
        for i in range(event["width"])
    }
    assert writes == set(range(g - (40 if n else 16), g)) | set(
        range(d, d + n + 1)
    ) | set(range(d + 16, d + 20))


@pytest.mark.parametrize("length", range(16))
@pytest.mark.parametrize("recipe", ("begin", "end", "half"))
@pytest.mark.parametrize("requested", (0, 1, 3, 15, 0xFFFFFFFF))
def test_all_inline_lengths_offsets_unsigned_clamp_and_full_fourteen(
    length, recipe, requested
):
    offset = 0 if recipe == "begin" else length if recipe == "end" else length // 2
    packet = inputs(length, offset, requested, old_length=(15 - length))
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    equal(packet, before)


@pytest.mark.parametrize("a", range(16))
@pytest.mark.parametrize(
    "length,offset,requested",
    ((0, 0, 0xFFFFFFFF), (15, 0, 15), (15, 3, 7), (9, 8, 0xFFFFFFFF)),
)
@pytest.mark.parametrize("profile", range(3))
def test_alignments_profiles_whole_pages_and_exact_scalar_prefixes(
    a, length, offset, requested, profile
):
    packet = inputs(
        length,
        offset,
        requested,
        frame=0x30001000 + a,
        source=0x10000FF0 + a,
        destination=0x10002FF0 + a,
        profile=profile,
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("flags", FLAGS)
@pytest.mark.parametrize(
    "length,offset,requested", ((0, 0, 0xFFFFFFFF), (15, 4, 0), (15, 2, 8))
)
def test_all_ordinary_flags_zero_offset_zero_request_and_positive(
    flags, length, offset, requested
):
    packet = inputs(length, offset, requested, flags=flags)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("requested", (0x80000000, 0x80000001, 0xFFFFFFFE, 0xFFFFFFFF))
def test_requested_word_clamp_is_unsigned_not_signed(requested):
    packet = inputs(15, 9, requested)
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["geometry"]["count"] == 6


@pytest.mark.parametrize("old_length", range(16))
def test_old_destination_length_does_not_limit_or_mutate_source(old_length):
    packet = inputs(15, 3, 8, old_length=old_length)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "length,offset,requested", ((0, 0, 0xFFFFFFFF), (15, 15, 0xFFFFFFFF), (15, 7, 0))
)
def test_zero_selected_count_never_calls_primitive(
    length, offset, requested, monkeypatch
):
    packet = inputs(length, offset, requested)
    calls = []

    def forbidden(**kwargs):
        calls.append(kwargs)
        raise AssertionError("zero substring copy called memcpy")

    monkeypatch.setattr(c.memcpy, "apply", forbidden)
    check(c.apply(**packet), packet)
    assert calls == []


@pytest.mark.parametrize(
    "g,s,d",
    (
        (40, 0x10000FF0, 0x10002FF0),
        (0x90001003, 0x7FFFFFF8, 0x10002FF0),
        (0xFFFFFFEF, 0x10000FFF, 0x10002FFF),
        (0x30001003, 0xFFFFFFE7, 0x10002FFF),
        (0x30001003, 0x10000FF0, 0x10001008),
        (0x30001003, 0x10001008, 0x10000FF0),
        (0x30001003, 0x30001100, 0x30001200),
    ),
)
def test_page_signed_edges_exact_object_adjacency_and_stack_page(g, s, d):
    packet = inputs(15, 3, 9, frame=g, source=s, destination=d)
    check(c.apply(**packet), packet)


def test_source_and_destination_terminators_are_unread_premises_not_required():
    packet = inputs(8, 2, 5, old_length=11)
    s, d = (
        word(packet["pages"], packet["registers"]["esp"] + 4),
        packet["registers"]["ecx"],
    )
    store(packet["pages"], s + 8, bytes([0xA5]))
    store(packet["pages"], d + 11, bytes([0x5A]))
    actual = c.apply(**packet)
    check(actual, packet)
    assert read_bytes(actual["pages"], s + 8, 1) == bytes([0xA5])
    assert read_bytes(actual["pages"], d + 11, 1) == bytes([0x5A])


@pytest.mark.parametrize("value", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_arbitrary_nonaddress_gpr_and_full_xmm_states(value):
    packet = inputs(15, 2, 9)
    for key in GPR:
        if key not in ("ecx", "esp"):
            packet["registers"][key] = value
    packet["xmm"] = {
        key: (value << 96) | (value << 64) | (value << 32) | value for key in XMM
    }
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("requested", (0, 7))
def test_actual_input_output_child_and_boundary_detachment(requested):
    packet = inputs(15, 3, requested)
    before = copy.deepcopy(packet)
    actual = c.apply(**packet)
    saved = copy.deepcopy(actual)
    actual["geometry"]["count"] ^= 1
    actual["events"][0]["value"] ^= 1
    actual["pages"].clear()
    actual["registers"]["eax"] ^= 1
    actual["xmm"]["xmm7"] ^= 1
    if requested:
        actual["memcpy_packet"]["pages"].clear()
        actual["boundaries"][0]["events"].clear()
        actual["boundaries"][1]["registers"]["edx"] ^= 1
    equal(packet, before)
    equal(c.apply(**packet), saved)


@pytest.mark.parametrize(
    "kind",
    (
        "source_length",
        "destination_length",
        "source_capacity",
        "destination_capacity",
        "offset",
        "self",
        "object_overlap",
        "source_frame",
        "destination_frame",
        "frame_low",
        "frame_wrap",
        "source_null",
        "source_wrap",
        "destination_null",
        "destination_wrap",
        "caller_return",
        "return_frame",
        "return_source",
        "return_destination",
        "return_owner_code",
        "return_child_code",
        "source_page_missing",
        "destination_page_missing",
        "stack_page_missing",
        "owner_code_page",
        "child_code_page",
    ),
)
def test_selected_domain_rejections_precede_writes_and_primitive(kind, monkeypatch):
    packet = inputs()
    g, s, d = (
        packet["registers"]["esp"],
        word(packet["pages"], packet["registers"]["esp"] + 4),
        packet["registers"]["ecx"],
    )
    if kind in ("source_length", "destination_length"):
        put_word(packet["pages"], (s if kind.startswith("source") else d) + 16, 16)
    elif kind in ("source_capacity", "destination_capacity"):
        put_word(packet["pages"], (s if kind.startswith("source") else d) + 20, 16)
    elif kind == "offset":
        put_word(packet["pages"], g + 8, 16)
    elif kind == "self":
        put_word(packet["pages"], g + 4, d)
    elif kind == "object_overlap":
        put_word(packet["pages"], g + 4, d - 1)
    elif kind == "source_frame":
        put_word(packet["pages"], g + 4, g - 32)
    elif kind == "destination_frame":
        packet["registers"]["ecx"] = g - 32
    elif kind == "frame_low":
        packet["registers"]["esp"] = 39
    elif kind == "frame_wrap":
        packet["registers"]["esp"] = 0xFFFFFFF0
    elif kind in ("source_null", "source_wrap"):
        put_word(packet["pages"], g + 4, 0 if kind.endswith("null") else 0xFFFFFFE8)
    elif kind in ("destination_null", "destination_wrap"):
        packet["registers"]["ecx"] = 0 if kind.endswith("null") else 0xFFFFFFE8
    elif kind == "caller_return":
        put_word(packet["pages"], g, packet["return_address"] ^ 1)
    elif kind.startswith("return_"):
        endpoint = {
            "return_frame": g - 1,
            "return_source": s,
            "return_destination": d,
            "return_owner_code": 0x004080D0,
            "return_child_code": 0x00770916,
        }[kind]
        packet["return_address"] = endpoint
        put_word(packet["pages"], g, endpoint)
    elif kind.endswith("page_missing"):
        packet["pages"].pop(
            {
                "source_page_missing": s & ~4095,
                "destination_page_missing": d & ~4095,
                "stack_page_missing": (g - 40) & ~4095,
            }[kind]
        )
    else:
        packet["pages"][0x00408000 if kind.startswith("owner") else 0x00770000] = bytes(
            4096
        )
    reject_without_writes_or_child(packet, monkeypatch)


def reject_without_writes_or_child(packet, monkeypatch):
    before = copy.deepcopy(packet)
    calls = []
    original = c._write

    def observed(*args):
        calls.append("write")
        return original(*args)

    def forbidden(**kwargs):
        calls.append("child")
        raise AssertionError("primitive reached invalid parent domain")

    monkeypatch.setattr(c, "_write", observed)
    monkeypatch.setattr(c.memcpy, "apply", forbidden)
    with pytest.raises(c.InlineStringCopyError):
        c.apply(**packet)
    assert calls == []
    equal(packet, before)


@pytest.mark.parametrize(
    "group,key,value",
    (
        ("registers", "eax", True),
        ("registers", "esp", 0.0),
        ("registers", "edx", -1),
        ("registers", "edi", 2**32),
        ("xmm", "xmm0", False),
        ("xmm", "xmm1", 0.0),
        ("xmm", "xmm4", -1),
        ("xmm", "xmm7", 2**128),
    ),
)
def test_all_typed_state_values_reject_before_owner_mutation(
    group, key, value, monkeypatch
):
    packet = inputs()
    packet[group][key] = value
    reject_without_writes_or_child(packet, monkeypatch)


@pytest.mark.parametrize("group", ("registers", "xmm"))
@pytest.mark.parametrize("kind", ("missing", "extra", "mapping", "string_alias"))
def test_exact_state_maps_and_key_types(group, kind, monkeypatch):
    packet = inputs()
    key = next(iter(packet[group]))
    if kind == "missing":
        packet[group].pop(key)
    elif kind == "extra":
        packet[group]["opaque"] = 0
    elif kind == "mapping":
        packet[group] = UserDict(packet[group])
    else:

        class Alias(str):
            pass

        value = packet[group].pop(key)
        packet[group][Alias(key)] = value
    reject_without_writes_or_child(packet, monkeypatch)


@pytest.mark.parametrize(
    "kind",
    (
        "empty",
        "mapping",
        "mutable",
        "short",
        "unaligned",
        "bool_key",
        "float_key",
        "negative_key",
        "wrap_key",
    ),
)
def test_complete_immutable_page_types_before_write(kind, monkeypatch):
    packet = inputs()
    pages = packet["pages"]
    key = next(iter(pages))
    if kind == "empty":
        packet["pages"] = {}
    elif kind == "mapping":
        packet["pages"] = UserDict(pages)
    elif kind == "mutable":
        pages[key] = bytearray(pages[key])
    elif kind == "short":
        pages[key] = pages[key][:-1]
    elif kind == "unaligned":
        pages[1] = bytes(4096)
    elif kind == "bool_key":
        pages[False] = bytes(4096)
    elif kind == "float_key":
        pages[0.0] = bytes(4096)
    elif kind == "negative_key":
        pages[-4096] = bytes(4096)
    else:
        pages[2**32] = bytes(4096)
    reject_without_writes_or_child(packet, monkeypatch)


@pytest.mark.parametrize("field", ("entry_flags", "return_address"))
@pytest.mark.parametrize("value", (True, 0.0, -1, 2**32, None))
def test_strict_keyword_word_types(field, value, monkeypatch):
    packet = inputs()
    packet[field] = value
    reject_without_writes_or_child(packet, monkeypatch)


@pytest.mark.parametrize("flags", (0, 4))
def test_required_reserved_bit_one(flags, monkeypatch):
    packet = inputs(flags=flags)
    reject_without_writes_or_child(packet, monkeypatch)


@pytest.mark.parametrize(
    "bit", tuple(bit for bit in range(32) if bit not in (0, 1, 2, 4, 6, 7, 9, 11))
)
def test_every_forbidden_control_and_reserved_flag(bit, monkeypatch):
    packet = inputs(flags=2 | (1 << bit))
    reject_without_writes_or_child(packet, monkeypatch)


@pytest.mark.parametrize("count", (4, 7))
@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "mapping",
        "geometry",
        "geometry_bool",
        "gpr",
        "gpr_bool",
        "xmm",
        "xmm_bool",
        "flags",
        "mask",
        "df_bool",
        "endpoint",
        "endpoint_float",
        "snapshot",
        "snapshot_type",
        "pages",
        "pages_extra",
        "pages_mutable",
        "events_tuple",
        "event_access",
        "event_bool",
        "event_width2",
        "event_width3",
        "event_width8",
        "event_extra",
        "event_read",
        "event_write",
        "outside_write",
        "ordered_read",
        "duplicate_read",
        "write_restore",
        "trace_tuple",
        "trace_value",
        "trace_case",
    ),
)
def test_complete_eleven_child_join_rejections(count, kind, monkeypatch):
    packet = inputs(15, 2, count)

    def forged(**kwargs):
        child = scalar.independent(kwargs)
        if kind == "extra":
            child["opaque"] = 0
        elif kind == "missing":
            child.pop("source_snapshot")
        elif kind == "mapping":
            child = UserDict(child)
        elif kind == "geometry":
            child["geometry"]["count"] += 1
        elif kind == "geometry_bool":
            child["geometry"]["count"] = True
        elif kind == "gpr":
            child["registers"]["ebx"] ^= 1
        elif kind == "gpr_bool":
            child["registers"]["eax"] = True
        elif kind == "xmm":
            child["xmm"]["xmm7"] ^= 1
        elif kind == "xmm_bool":
            child["xmm"]["xmm0"] = False
        elif kind == "flags":
            child["flags"] ^= 1
        elif kind == "mask":
            child["flag_mask"] = 0xC5
        elif kind == "df_bool":
            child["df"] = False
        elif kind == "endpoint":
            child["endpoint"] ^= 1
        elif kind == "endpoint_float":
            child["endpoint"] = float(child["endpoint"])
        elif kind == "snapshot":
            child["source_snapshot"] = (
                bytes([child["source_snapshot"][0] ^ 1]) + child["source_snapshot"][1:]
            )
        elif kind == "snapshot_type":
            child["source_snapshot"] = bytearray(child["source_snapshot"])
        elif kind == "pages":
            put_word(child["pages"], 0x12340000, word(child["pages"], 0x12340000) ^ 1)
        elif kind == "pages_extra":
            child["pages"][0x12341000] = bytes(4096)
        elif kind == "pages_mutable":
            child["pages"][0x12340000] = bytearray(4096)
        elif kind == "events_tuple":
            child["events"] = tuple(child["events"])
        elif kind == "event_access":
            child["events"][0]["access"] = "execute"
        elif kind == "event_bool":
            child["events"][0]["address"] = True
        elif kind.startswith("event_width"):
            child["events"][0]["width"] = int(kind[11:])
        elif kind == "event_extra":
            child["events"][0]["opaque"] = 0
        elif kind == "event_read":
            next(row for row in child["events"] if row["access"] == "read")[
                "value"
            ] ^= 1
        elif kind == "event_write":
            child["events"][0]["value"] ^= 1
        elif kind == "outside_write":
            child["events"][0]["address"] = 0x12340000
        elif kind == "ordered_read":
            child["events"][2], child["events"][3] = (
                child["events"][3],
                child["events"][2],
            )
        elif kind == "duplicate_read":
            child["events"].append(copy.deepcopy(child["events"][-1]))
        elif kind == "write_restore":
            d = child["geometry"]["destination"]
            old = word(kwargs["pages"], d)
            child["events"][2:2] = [
                dict(access="write", address=d, width=4, value=old ^ 1),
                dict(access="write", address=d, width=4, value=old),
            ]
        elif kind == "trace_tuple":
            child["trace_rvas"] = tuple(child["trace_rvas"])
        elif kind == "trace_value":
            child["trace_rvas"][0] = 0
        else:
            child["trace_rvas"][0] = "0x0000ABCD"
        return child

    before = copy.deepcopy(packet)
    monkeypatch.setattr(c.memcpy, "apply", forged)
    with pytest.raises(c.InlineStringCopyError):
        c.apply(**packet)
    equal(packet, before)


@pytest.mark.parametrize("kind", ("labels", "length"))
def test_valid_canonical_child_instruction_metadata_is_explicitly_trusted(
    kind, monkeypatch
):
    def annotated(**kwargs):
        child = scalar.independent(kwargs)
        if kind == "labels":
            child["trace_rvas"][0] = "0x003703e1"
        else:
            child["trace_rvas"].append("0x00370916")
        return child

    monkeypatch.setattr(c.memcpy, "apply", annotated)
    actual = c.apply(**inputs(15, 2, 7))
    assert (
        actual["memcpy_packet"]["trace_rvas"][0] == "0x003703e1"
        if kind == "labels"
        else actual["memcpy_packet"]["trace_rvas"][-1] == "0x00370916"
    )
    assert len(actual["trace_rvas"]) == 47 + len(actual["memcpy_packet"]["trace_rvas"])
    # Canonical reviewed labels and length are trusted, not an independent
    # executed-instruction proof. Page, ABI and exact-access guards still apply.


@pytest.mark.parametrize("count", (1, 4, 15))
def test_primitive_receives_actual_prefix_full_state_and_installed_words(
    count, monkeypatch
):
    packet = inputs(15, 0, count, flags=0xAD7)
    wanted = independent(packet)
    calls = []

    def observe(**kwargs):
        calls.append(copy.deepcopy(kwargs))
        return scalar.independent(kwargs)

    monkeypatch.setattr(c.memcpy, "apply", observe)
    check(c.apply(**packet), packet)
    assert len(calls) == 1
    expected = wanted["boundaries"][0]
    equal(calls[0]["registers"], expected["registers"])
    equal(calls[0]["pages"], expected["pages"])
    equal(calls[0]["xmm"], expected["xmm"])
    assert calls[0]["return_address"] == 0x004081A8
    assert calls[0]["entry_flags"] == 0x202 | logic(count)
    frame = calls[0]["registers"]["esp"]
    assert [word(calls[0]["pages"], frame + i) for i in (0, 4, 8, 12)] == [
        0x004081A8,
        packet["registers"]["ecx"],
        word(packet["pages"], packet["registers"]["esp"] + 4),
        count,
    ]


def test_foreign_primitive_error_normalized(monkeypatch):
    def failed(**kwargs):
        raise RuntimeError("independent substring primitive failure")

    monkeypatch.setattr(c.memcpy, "apply", failed)
    with pytest.raises(
        c.InlineStringCopyError, match="independent substring primitive failure"
    ):
        c.apply(**inputs())


def test_exact_actual_api_body_identity_and_no_machine_delegation():
    signature = inspect.signature(c.apply)
    assert tuple(signature.parameters) == (
        "pages",
        "registers",
        "xmm",
        "return_address",
        "entry_flags",
    )
    assert all(
        p.kind is inspect.Parameter.KEYWORD_ONLY
        and p.default is inspect.Parameter.empty
        for p in signature.parameters.values()
    )
    assert c.BODY_PINS[0x80D0] == (
        288,
        "062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333",
    )
    assert c.BODY_PINS[0x3703E0] == (
        1330,
        "027f9747b24b79e7aa5a3511ddfd2890a8d50a72072ac6c7df83959091aa9ec5",
    )
    assert c.SOURCE_PINS == {
        "program_facts": (
            "pe_ghidra_program_facts",
            "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
        )
    }
    source = ast.parse(inspect.getsource(c))
    assert not any(
        isinstance(n, (ast.Import, ast.ImportFrom))
        and any(v in ast.unparse(n) for v in ("unicorn", "capstone", "subprocess"))
        for n in ast.walk(source)
    )
    assert not any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in ("_fixture", "_expected", "_run_case")
        for n in ast.walk(source)
    )
    assert (
        len(PREFIX) == 23
        and len(ZERO) == 10
        and len(POSITIVE) == 12
        and len(SUFFIX) == 12
    )
