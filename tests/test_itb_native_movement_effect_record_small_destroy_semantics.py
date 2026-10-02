"""Independent actual-page inline-record destruction and ordinary free law."""

from __future__ import annotations
import ast
import copy
import inspect
from collections import UserDict
import pytest
from src.observatory import native_movement_effect_record_small_destroy_semantics as c
from tests.test_itb_native_movement_empty_string_copy_semantics import (
    store,
    read_bytes,
    assert_strict_packet as strict_equal,
)

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
STRINGS = (0x118, 0xF8, 0xE0, 0xA4, 0x80, 0x68, 0x50, 0x38)
FLAG_BITS = (0, 2, 4, 6, 7, 9, 11)
FLAGS = tuple(
    2 | sum(1 << bit for i, bit in enumerate(FLAG_BITS) if selector >> i & 1)
    for selector in range(128)
)
KEYS = {
    "record_address",
    "record_bytes",
    "path_pointer",
    "registers",
    "xmm",
    "pages",
    "events",
    "trace_rvas",
    "boundaries",
    "free_packet",
    "imported",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
}
BOUNDARY_KEYS = {
    "name",
    "registers",
    "xmm",
    "pages",
    "events",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
}
SEGMENTS = tuple(
    tuple(int(w, 16) for w in words.split())
    for words in (
        "10e2a0 10e2a1 10e2a3 10e2a9 10e2aa 10e2b0 10e2b3 10e2c3 10e2ca 10e2ce 10e2d5 10e2d9",
        "10e2dc 10e2e2 10e2e5 10e2e8 10e2f8 10e2ff 10e303 10e30a 10e30e",
        "10e311 10e317 10e31a 10e31d 10e32d 10e334 10e338 10e33f 10e343",
        "10e385 10e38b 10e391 10e394 10e3a4 10e3ab 10e3af 10e3b6 10e3ba",
        "10e3bd 10e3c3 10e3c6 10e3c9 10e3d9 10e3e0 10e3e4 10e3eb 10e3ef",
        "10e3f2 10e3f5 10e3f8 10e3fb 10e40b 10e412 10e416 10e41d 10e421",
        "10e424 10e427 10e42a 10e42d 10e43d 10e444 10e448 10e44f 10e453",
        "10e456 10e459 10e45c 10e46d 10e474 10e478 10e47f 10e48a 10e48b 10e48f 10e490",
    )
)
PATH_BEFORE = (0x10E346, 0x10E34C, 0x10E34E)
PATH_CALL = (0x10E350, 0x10E356, 0x10E358, 0x10E35A, 0x10E35D, 0x10E35E, 0x10E35F)
PATH_AFTER = (0x10E364, 0x10E36E, 0x10E371, 0x10E37B)
# The unchanged small guard + two jump thunks + HeapFree wrapper branch.
# This literal order is independently used by the earlier resize/AddMove tests.
FREE_TRACE = tuple(int(w, 16) for w in """
7800 7801 7803 7806 7809 780b 780e 7810 7816 781a 7820 784d 7850 7851
35785d 36fb17 389156 389158 389159 38915b 38915f 389161 389164 389166
38916c 389172 389174 38918e 38918f 7856 7859 785a
""".split())


def trace(owned):
    result = []
    for i, segment in enumerate(SEGMENTS):
        result.extend(segment)
        if i == 2:
            result.extend(PATH_BEFORE)
            if owned:
                result.extend(PATH_CALL + FREE_TRACE + PATH_AFTER)
    return result


def inputs(
    *,
    frame=0x30001000,
    record=0x10000FF0,
    path=0x20000FF8,
    owned=True,
    capacity=2,
    used=None,
    profile=0,
    size=7,
    flags=0x246,
    return_address=0x04000000,
):
    used = capacity if used is None else used
    extent = capacity * 8
    spans = [(frame - (56 if owned else 8), frame + 4), (record, record + 308)]
    if owned:
        spans.append((path, path + extent))
    bases = {
        b
        for start, end in spans
        for b in range(start & ~4095, ((end - 1) & ~4095) + 1, 4096)
    } | {0x12340000}
    if owned:
        stack_base = min((frame - 56) & ~4095, 0xFFFFE000)
        bases.update(
            (stack_base, stack_base + 4096, 0x06000000, 0x008B7000, 0x007D6000)
        )
    pages = {
        b: bytes((i * 37 + j * 29 + profile * 71) & 255 for j in range(4096))
        for i, b in enumerate(sorted(bases))
    }
    for off in STRINGS:
        store(pages, record + off + 16, size)
        store(pages, record + off + 20, 15)
    for off, value in (
        (0xCC, path if owned else 0),
        (0xD0, path + used * 8 if owned else 0),
        (0xD4, path + extent if owned else 0),
    ):
        store(pages, record + off, value)
    store(pages, frame, return_address)
    if owned:
        store(pages, 0x008B7634, 0x12345678)
        store(pages, 0x007D621C, 0x05000000)
        for i in range(capacity * 2):
            word = (0xD15C0016 + i * 0x29481736) & 0xFFFFFFFF
            store(pages, path + 4 * i, word ^ ((profile * 0x7654321) & 0xFFFFFFFF))
    regs = {
        name: (0x13579BDF + i * 0x1234567 + profile * 0x4321) & 0xFFFFFFFF
        for i, name in enumerate(GPR)
    }
    regs.update(esp=frame, ecx=record)
    xmm = {
        name: int.from_bytes(
            bytes((i * 31 + j * 19 + profile * 79) & 255 for j in range(16)), "little"
        )
        for i, name in enumerate(XMM)
    }
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmm,
        return_address=return_address,
        entry_flags=flags,
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


def free_law(vector, initial, original_stack, original_error, *, stack_base):
    """Canonical full eight-field primitive prediction before installed RET join."""
    count = vector["count"]
    assert type(count) is int and 1 <= count <= 511
    o = vector["pointer"]
    v = initial["esp"]
    strict_equal(
        vector,
        dict(
            pointer=o,
            count=count,
            stride=8,
            metadata=None,
            responses=[dict(kind="heap_free", eax=1)],
            heap=0x12345678,
        ),
    )
    stack = bytearray(original_stack)
    accesses = (
        ("write", v - 4, initial["ebp"]),
        ("read", v + 8, count),
        ("read", v + 12, 8),
        ("read", v + 12, 8),
        ("read", v + 4, o),
        ("write", v - 8, o),
        ("write", v - 12, 0x00407856),
        ("write", v - 16, v - 4),
        ("read", v - 8, o),
        ("read", v - 8, o),
        ("write", v - 20, o),
        ("write", v - 24, 0),
        ("read", 0x008B7634, 0x12345678),
        ("write", v - 28, 0x12345678),
        ("read", 0x007D621C, 0x05000000),
        ("write", v - 32, 0x00789172),
        ("read", v - 16, v - 4),
        ("read", v - 12, 0x00407856),
        ("read", v - 4, initial["ebp"]),
        ("read", v, 0x04000000),
    )
    events = []
    for op, at, value in accesses:
        if op == "write":
            stack[at - stack_base : at - stack_base + 4] = value.to_bytes(4, "little")
        events.append(dict(access=op, address=at, width=4, value=value))
    return dict(
        registers=dict(initial, eax=1, ecx=0xA0000001, edx=0xB0000001, esp=v + 4),
        flags=add_flags(v - 8, 4),
        flag_mask=0x8D5,
        events=events,
        stack=bytes(stack),
        error=original_error,
        stop=0x04000000,
        protocol=dict(
            returned=True, result=1, next_kind=None, error_cell=None, last_error=None
        ),
    )


def independent(packet):
    initial = packet["registers"]
    g = initial["esp"]
    r = initial["ecx"]
    o = int.from_bytes(read_bytes(packet["pages"], r + 0xCC, 4), "little")
    capacity_word = int.from_bytes(read_bytes(packet["pages"], r + 0xD4, 4), "little")
    count = (capacity_word - o) // 8 if o else 0
    pages = dict(packet["pages"])
    events = []
    boundaries = []
    regs = dict(initial)
    child = None
    imported = None

    def event(access, at, value, width=4):
        if access == "write":
            store(pages, at, value, width)
        else:
            assert int.from_bytes(read_bytes(pages, at, width), "little") == value
        events.append(dict(access=access, address=at, width=width, value=value))

    def boundary(name, pc, flags, mask):
        boundaries.append(
            dict(
                name=name,
                registers=dict(regs),
                xmm=dict(packet["xmm"]),
                pages=dict(pages),
                events=copy.deepcopy(events),
                flags=flags,
                flag_mask=mask,
                df=0,
                endpoint=pc,
            )
        )

    event("write", g - 4, initial["esi"])
    event("read", r + 0x12C, 15)
    event("write", g - 8, initial["edi"])
    regs.update(esi=r, edi=r + 0x118, eax=15, esp=g - 8)

    def inline(index):
        off = STRINGS[index]
        if index:
            event("read", r + off + 20, 15)
        event("write", r + off + 20, 15)
        event("read", r + off + 20, 15)
        event("write", r + off + 16, 0)
        if index == 7:
            event("read", g - 8, initial["edi"])
        event("write", r + off, 0, 1)
        regs["eax"] = 15
        if index != 7:
            regs["edi"] = r + off

    for i in range(3):
        inline(i)
    event("read", r + 0xCC, o)
    regs["ecx"] = o
    if o:
        event("read", r + 0xD4, o + count * 8)
        for at, value in (
            (g - 12, 8),
            (g - 16, count),
            (g - 20, o),
            (g - 24, 0x0050E364),
        ):
            event("write", at, value)
        regs.update(eax=count, esp=g - 24)
        boundary(
            "free_entry",
            0x00407800,
            4 if (count & 255).bit_count() % 2 == 0 else 0,
            0xC5,
        )
        stack_base = min((g - 56) & ~4095, 0xFFFFE000)
        original_stack = read_bytes(pages, stack_base, 8192)
        child = free_law(
            dict(
                pointer=o,
                count=count,
                stride=8,
                metadata=None,
                responses=[dict(kind="heap_free", eax=1)],
                heap=0x12345678,
            ),
            regs,
            original_stack,
            pages[0x06000000],
            stack_base=stack_base,
        )
        # Transport only canonical outer RET/stop after the full eight fields.
        child["events"][-1]["value"] = 0x0050E364
        child["stop"] = 0x0050E364
        prefix = copy.deepcopy(events)
        importpages = dict(pages)
        for row in child["events"][:16]:
            if row["access"] == "write":
                store(importpages, row["address"], row["value"])
        imported = dict(
            registers=dict(regs, eax=0x1FFFFFFF, ecx=o, edx=7, ebp=g - 40, esp=g - 56),
            xmm=dict(packet["xmm"]),
            pages=importpages,
            events=prefix + copy.deepcopy(child["events"][:16]),
            flags=(4 if (o & 255).bit_count() % 2 == 0 else 0)
            | (0x80 if o & 0x80000000 else 0),
            flag_mask=0x8C5,
            df=0,
            endpoint=0x05000000,
            entry_esp=g - 56,
            words=[0x00789172, 0x12345678, 0, o],
        )
        events.extend(copy.deepcopy(child["events"]))
        pages[stack_base] = child["stack"][:4096]
        pages[stack_base + 4096] = child["stack"][4096:]
        regs = dict(child["registers"])
        boundary("free_return", 0x0050E364, child["flags"], 0x8D5)
        for off in (0xCC, 0xD0, 0xD4):
            event("write", r + off, 0)
        regs["esp"] = g - 8
    for i in range(3, 8):
        inline(i)
    event("read", g - 4, initial["esi"])
    event("read", g, packet["return_address"])
    # Separate last-writer equation includes no event replay.
    final = dict(packet["pages"])
    for off in STRINGS:
        store(final, r + off, 0, 1)
        store(final, r + off + 16, 0)
        store(final, r + off + 20, 15)
    values = {4: initial["esi"], 8: initial["edi"]}
    if o:
        for off in (0xCC, 0xD0, 0xD4):
            store(final, r + off, 0)
        values.update(
            {
                12: 8,
                16: count,
                20: o,
                24: 0x0050E364,
                28: initial["ebp"],
                32: o,
                36: 0x00407856,
                40: g - 28,
                44: o,
                48: 0,
                52: 0x12345678,
                56: 0x00789172,
            }
        )
    for off, value in values.items():
        store(final, g - off, value)
    strict_equal(pages, final)
    return dict(
        record_address=r,
        record_bytes=read_bytes(final, r, 308),
        path_pointer=o,
        registers=dict(
            initial,
            eax=15,
            ecx=0xA0000001 if o else 0,
            edx=0xB0000001 if o else initial["edx"],
            esp=g + 4,
        ),
        xmm=dict(packet["xmm"]),
        pages=final,
        events=events,
        trace_rvas=[f"0x{pc:08x}" for pc in trace(bool(o))],
        boundaries=boundaries,
        free_packet=child,
        imported=imported,
        flags=0x85,
        flag_mask=0x8D5,
        df=0,
        endpoint=packet["return_address"],
    )


def check(actual, packet):
    wanted = independent(packet)
    strict_equal(actual, wanted)
    assert set(actual) == KEYS and len(KEYS) == 15
    r = packet["registers"]["ecx"]
    g = packet["registers"]["esp"]
    o = actual["path_pointer"]
    assert len(actual["events"]) == (74 if o else 46)
    assert len(actual["trace_rvas"]) == (123 if o else 80)
    written = {off + i for off in STRINGS for i in (0, *range(16, 24))}
    if o:
        written.update(range(0xCC, 0xD8))
    assert len(written) == (84 if o else 72)
    assert 308 - len(written) == (224 if o else 236)
    previous = read_bytes(packet["pages"], r, 308)
    assert all(
        actual["record_bytes"][i] == previous[i] for i in range(308) if i not in written
    )
    assert read_bytes(actual["pages"], g, 4) == read_bytes(packet["pages"], g, 4)
    actualwrites = {
        row["address"] + i
        for row in actual["events"]
        if row["access"] == "write"
        for i in range(row["width"])
    }
    assert actualwrites == {r + i for i in written} | set(
        range(g - (56 if o else 8), g)
    )
    assert not any(
        row["address"] == r + off + 16 and row["access"] == "read"
        for row in actual["events"]
        for off in STRINGS
    )
    assert not {0x3574CA, 0x3435D9, 0x80D0, 0x8ABA0}.intersection(
        int(pc, 16) for pc in actual["trace_rvas"]
    )
    if o:
        assert [len(row["events"]) for row in actual["boundaries"]] == [23, 43]
        assert all(set(row) == BOUNDARY_KEYS for row in actual["boundaries"])
        assert actual["boundaries"][0]["flag_mask"] == 0xC5
        assert len(actual["imported"]["events"]) == 39
        assert set(actual["imported"]) == (BOUNDARY_KEYS - {"name"}) | {
            "entry_esp",
            "words",
        }
        assert actual["imported"]["flag_mask"] == 0x8C5
        assert actual["imported"]["words"] == [0x00789172, 0x12345678, 0, o]
        assert set(actual["free_packet"]) == {
            "registers",
            "flags",
            "flag_mask",
            "events",
            "stack",
            "error",
            "stop",
            "protocol",
        }
        assert len(actual["free_packet"]["events"]) == 20
        assert actual["free_packet"]["events"][-1] == dict(
            access="read", address=g - 24, width=4, value=0x0050E364
        )
        assert actual["free_packet"]["stop"] == 0x0050E364
        capacity_word = int.from_bytes(
            read_bytes(packet["pages"], r + 0xD4, 4), "little"
        )
        extent = capacity_word - o
        assert read_bytes(actual["pages"], o, extent) == read_bytes(
            packet["pages"], o, extent
        )
        assert not any(o <= row["address"] < capacity_word for row in actual["events"])
        assert not any(
            row["access"] == "read" and row["address"] == r + 0xD0
            for row in actual["events"]
        )
    else:
        assert (
            actual["boundaries"] == []
            and actual["free_packet"] is None
            and actual["imported"] is None
        )
    assert actual["flags"] == 0x85 and actual["flag_mask"] == 0x8D5


@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize("profile", range(3))
@pytest.mark.parametrize("owned", (False, True))
def test_all_alignments_profiles_null_owned_complete15_and_full_pages(
    alignment, profile, owned
):
    packet = inputs(
        frame=0x30001000 + alignment,
        record=0x10000FF0 + alignment,
        path=0x20000FF8 + alignment,
        owned=owned,
        profile=profile,
        size=(0, 7, 15)[profile],
    )
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    strict_equal(packet, before)


@pytest.mark.parametrize("flags", FLAGS)
@pytest.mark.parametrize("owned", (False, True))
def test_all128_ordinary_flags(flags, owned):
    packet = inputs(flags=flags, owned=owned)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "g,r,o",
    [
        (0x30000FFD, 0x10000FFF, 0x20000FF8),
        (0xFFFFFFFB, 0x10000503, 0x20000FF8),
        (0x30001000, 0x7FFFFFF0, 0xFFFFFFEF),
        (0x30001000, 0xFFFFFECB, 0x20000FF8),
        (0x30001000, 0x10000200, 0x10000334),
        (0x30001000, 0x10000200, 0x100001F0),
        (0x30001000, 0x30001800, 0x30001E00),
        (56, 0x10000200, 0x20000FF8),
    ],
)
@pytest.mark.parametrize("owned", (False, True))
def test_cross_page_signed_high_end_low_frame_adjacency_and_stack_page_objects(
    g, r, o, owned
):
    packet = inputs(frame=g, record=r, path=o, owned=owned)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("value", (0, 1, 0x80000000, 0xFFFFFFFF))
@pytest.mark.parametrize("owned", (False, True))
def test_arbitrary_nonaddress_gpr_xmm_and_unread_string_payload(value, owned):
    packet = inputs(owned=owned)
    for name in GPR:
        if name not in ("ecx", "esp"):
            packet["registers"][name] = value
    packet["xmm"] = {
        name: (value << 96) | (value << 64) | (value << 32) | value for name in XMM
    }
    for off in STRINGS:
        for i in range(16):
            store(packet["pages"], 0x10000FF0 + off + i, (value + i * 37) & 255, 1)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("owned", (False, True))
def test_all_record_padding_and_unread_contents_arbitrary(owned):
    packet = inputs(owned=owned)
    r = packet["registers"]["ecx"]
    written = {off + i for off in STRINGS for i in (0, *range(16, 24))}
    # Both path triples are input premises even when the null branch preserves
    # their bytes. Unread does not imply unconstrained in this selected domain.
    written.update(range(0xCC, 0xD8))
    for i in range(308):
        if i not in written:
            store(packet["pages"], r + i, (i * 37 + 19) & 255, 1)
    check(c.apply(**packet), packet)


def test_null_path_needs_no_heap_iat_error_or_full_stack_window(monkeypatch):
    packet = inputs(owned=False)
    assert (
        0x06000000 not in packet["pages"]
        and 0x008B7000 not in packet["pages"]
        and 0x007D6000 not in packet["pages"]
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("null path delegated to deallocator")

    monkeypatch.setattr(c.deallocator, "_expected", forbidden)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("owned", (False, True))
def test_nested_result_and_input_detachment(owned):
    packet = inputs(owned=owned)
    before = copy.deepcopy(packet)
    wanted = independent(packet)
    actual = c.apply(**packet)
    actual["pages"][0x12340000] = bytes(4096)
    actual["events"][0]["value"] ^= 1
    actual["registers"]["eax"] ^= 1
    actual["xmm"]["xmm7"] ^= 1
    if owned:
        actual["free_packet"]["protocol"]["result"] = 0
        actual["boundaries"][0]["pages"][0x12340000] = bytes(4096)
        actual["imported"]["words"][3] ^= 1
    strict_equal(packet, before)
    strict_equal(c.apply(**packet), wanted)


@pytest.mark.parametrize(
    "bit", [b for b in range(32) if b not in (0, 1, 2, 4, 6, 7, 9, 11)]
)
def test_all_forbidden_reserved_control_df_flags(bit):
    packet = inputs()
    packet["entry_flags"] = 2 | (1 << bit)
    with pytest.raises(c.RecordDestroyError):
        c.apply(**packet)


@pytest.mark.parametrize("value", (0, 4, True, 2.0, -1, 2**32, None))
def test_required_bit1_and_exact_flag_word(value):
    packet = inputs()
    packet["entry_flags"] = value
    with pytest.raises(c.RecordDestroyError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "group,key,value",
    [
        ("registers", "eax", True),
        ("registers", "esp", float(0x30001000)),
        ("registers", "esi", -1),
        ("registers", "edi", 2**32),
        ("xmm", "xmm0", False),
        ("xmm", "xmm7", 0.0),
        ("xmm", "xmm3", -1),
        ("xmm", "xmm2", 2**128),
    ],
)
def test_exact_all8_gpr_xmm_word_schema(group, key, value):
    packet = inputs()
    packet[group][key] = value
    with pytest.raises(c.RecordDestroyError):
        c.apply(**packet)


@pytest.mark.parametrize("group", ("registers", "xmm"))
@pytest.mark.parametrize("kind", ("missing", "extra", "mapping", "str_alias"))
def test_closed_typed_state_dicts(group, kind):
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
    with pytest.raises(c.RecordDestroyError):
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
def test_strict_full_immutable_page_maps(kind):
    packet = inputs()
    pages = packet["pages"]
    base = 0x12340000
    if kind == "mapping":
        packet["pages"] = UserDict(pages)
    elif kind == "empty":
        packet["pages"] = {}
    elif kind == "short":
        pages[base] = pages[base][:-1]
    elif kind == "mutable":
        pages[base] = bytearray(pages[base])
    elif kind == "bool_key":
        pages[False] = bytes(4096)
    elif kind == "float_key":
        value = pages.pop(base)
        pages[float(base)] = value
    elif kind == "negative_key":
        pages[-4096] = bytes(4096)
    elif kind == "unaligned_key":
        pages[1] = bytes(4096)
    else:
        pages[2**32] = bytes(4096)
    with pytest.raises(c.RecordDestroyError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    (
        "caller",
        "path_end",
        "path_cap",
        "path_null_mixed",
        "size",
        "cap",
        "heap",
        "iat",
        "missing_error",
        "missing_stack",
        "missing_payload",
        "record_frame",
        "path_record",
        "path_frame",
        "record_error",
        "path_error",
        "record_heap",
        "path_iat",
        "selected_page",
    ),
)
def test_closed_path_inline_heap_global_mapping_and_alias_domains(kind):
    packet = inputs()
    pages = packet["pages"]
    g = 0x30001000
    r = 0x10000FF0
    o = 0x20000FF8
    if kind == "caller":
        store(pages, g, 0x04000004)
    elif kind == "path_end":
        store(pages, r + 0xD0, o + 24)
    elif kind == "path_cap":
        store(pages, r + 0xD4, o + 7)
    elif kind == "path_null_mixed":
        store(pages, r + 0xCC, 0)
    elif kind == "size":
        store(pages, r + 0x128, 16)
    elif kind == "cap":
        store(pages, r + 0x12C, 16)
    elif kind == "heap":
        store(pages, 0x008B7634, 0)
    elif kind == "iat":
        store(pages, 0x007D621C, 0)
    elif kind == "missing_error":
        del pages[0x06000000]
    elif kind == "missing_stack":
        del pages[0x30000000]
    elif kind == "missing_payload":
        del pages[0x20001000]
    elif kind == "record_frame":
        packet["registers"]["ecx"] = g - 8
    elif kind in ("path_record", "path_frame", "path_error", "path_iat"):
        pointer = {
            "path_record": r,
            "path_frame": g - 56,
            "path_error": 0x06000004,
            "path_iat": 0x007D6800,
        }[kind]
        for off, value in ((0xCC, pointer), (0xD0, pointer + 16), (0xD4, pointer + 16)):
            store(pages, r + off, value)
    elif kind == "record_error":
        packet["registers"]["ecx"] = 0x06000200
    elif kind == "record_heap":
        packet["registers"]["ecx"] = 0x008B7800
    else:
        pages[0x0050E000] = bytes(4096)
    with pytest.raises(c.RecordDestroyError):
        c.apply(**packet)


def test_owned_whole_stack_window_must_avoid_error_page():
    # Actual touched frame is below ERROR; the complete lower stack channel
    # still intersects ERROR and is rejected before primitive composition.
    packet = inputs(frame=0x05FFF080)
    with pytest.raises(c.RecordDestroyError, match="stack window overlaps error"):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind", ("frame_low", "frame_wrap", "record_null", "record_wrap", "path_wrap")
)
def test_conservative_unsigned_full_extent_guards(kind):
    packet = inputs()
    if kind == "frame_low":
        packet["registers"]["esp"] = 55
    elif kind == "frame_wrap":
        packet["registers"]["esp"] = 0xFFFFFFFC
    elif kind == "record_null":
        packet["registers"]["ecx"] = 0
    elif kind == "record_wrap":
        packet["registers"]["ecx"] = 0xFFFFFECC
    else:
        for off, value in ((0xCC, 0xFFFFFFF0), (0xD0, 0), (0xD4, 0)):
            store(packet["pages"], 0x10000FF0 + off, value)
    with pytest.raises(c.RecordDestroyError):
        c.apply(**packet)


@pytest.mark.parametrize("value", (0, True, float(0x04000000), -1, 2**32))
def test_strict_positive_outer_return(value):
    packet = inputs()
    packet["return_address"] = value
    with pytest.raises(c.RecordDestroyError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "value",
    (
        0x30000FC8,
        0x10000FF0,
        0x20000FF8,
        0x0050E2A0,
        0x00407800,
        0x0075785D,
        0x0076FB17,
        0x00789156,
    ),
)
def test_returns_exclude_touched_spans_and_all_selected_bodies(value):
    packet = inputs(return_address=value)
    with pytest.raises(c.RecordDestroyError):
        c.apply(**packet)


@pytest.mark.parametrize("value", (0x006573A7, 0xFFFFFFFF, 0x05000000))
@pytest.mark.parametrize("owned", (False, True))
def test_permitted_words_are_logical_endpoints_only(value, owned):
    packet = inputs(return_address=value, owned=owned)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("capacity", (1, 511))
@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "extra",
        "eax_bool",
        "flag_bool",
        "stop_float",
        "mask_float",
        "protocol_returned_int",
        "protocol_result_bool",
        "stack_mutable",
        "error_mutable",
        "events_tuple",
        "missing_read",
        "early_ret_rebind",
        "early_stop_rebind",
        "coordinated_stack",
        "coordinated_error",
    ),
)
def test_entire8_free_packet_compared_before_installed_ret_transport(
    monkeypatch, kind, capacity
):
    def forged(vector, initial, stack, error, *, stack_base):
        result = free_law(vector, initial, stack, error, stack_base=stack_base)
        if kind == "missing":
            del result["protocol"]
        elif kind == "extra":
            result["other"] = 0
        elif kind == "eax_bool":
            result["registers"]["eax"] = True
        elif kind == "flag_bool":
            result["flags"] = bool(result["flags"])
        elif kind == "stop_float":
            result["stop"] = float(result["stop"])
        elif kind == "mask_float":
            result["flag_mask"] = float(result["flag_mask"])
        elif kind == "protocol_returned_int":
            result["protocol"]["returned"] = 1
        elif kind == "protocol_result_bool":
            result["protocol"]["result"] = True
        elif kind == "stack_mutable":
            result["stack"] = bytearray(result["stack"])
        elif kind == "error_mutable":
            result["error"] = bytearray(result["error"])
        elif kind == "events_tuple":
            result["events"] = tuple(result["events"])
        elif kind == "missing_read":
            result["events"].pop()
        elif kind == "early_ret_rebind":
            result["events"][-1]["value"] = 0x0050E364
        elif kind == "early_stop_rebind":
            result["stop"] = 0x0050E364
        elif kind == "coordinated_stack":
            value = bytearray(result["stack"])
            value[123] ^= 1
            result["stack"] = bytes(value)
            result["events"][0]["value"] ^= 1
        else:
            value = bytearray(result["error"])
            value[117] ^= 1
            result["error"] = bytes(value)
            result["protocol"]["last_error"] = 0
        return result

    monkeypatch.setattr(c.deallocator, "_expected", forged)
    with pytest.raises(c.RecordDestroyError, match="primitive differs"):
        c.apply(**inputs(capacity=capacity, used=0))


def test_real_primitive_receives_actual_full_stack_state_and_closed_protocol(
    monkeypatch,
):
    packet = inputs()
    calls = []

    def checked(vector, initial, stack, error, *, stack_base):
        calls.append(copy.deepcopy((vector, initial, stack, error, stack_base)))
        return free_law(vector, initial, stack, error, stack_base=stack_base)

    monkeypatch.setattr(c.deallocator, "_expected", checked)
    check(c.apply(**packet), packet)
    assert len(calls) == 1
    vector, initial, stack, error, base = calls[0]
    assert vector == dict(
        pointer=0x20000FF8,
        count=2,
        stride=8,
        metadata=None,
        responses=[dict(kind="heap_free", eax=1)],
        heap=0x12345678,
    )
    strict_equal(initial, independent(packet)["boundaries"][0]["registers"])
    assert (
        len(stack) == 8192
        and base == 0x30000000
        and error == packet["pages"][0x06000000]
    )
    assert (
        int.from_bytes(
            stack[initial["esp"] - base : initial["esp"] - base + 4], "little"
        )
        == 0x0050E364
    )


def test_installed_free_caller_word_is_checked_after_full_canonical_packet():
    packet = inputs()
    expected = independent(packet)
    entry = expected["boundaries"][0]
    pages = dict(entry["pages"])
    v = entry["registers"]["esp"]
    store(pages, v, 0x0050E368)
    with pytest.raises(c.RecordDestroyError, match="installed continuation differs"):
        c._free_packet_law(
            entry["registers"], pages, expected["path_pointer"], 2, 0x30000000
        )


def test_foreign_free_exception_is_normalized(monkeypatch):
    def failed(*args, **kwargs):
        raise ValueError("free failure")

    monkeypatch.setattr(c.deallocator, "_expected", failed)
    with pytest.raises(c.RecordDestroyError, match="free failure"):
        c.apply(**inputs())


def test_closed_actual_api_body_pins_dependencies_and_no_native_fixture():
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
    tree = ast.parse(inspect.getsource(c))
    assert not any(
        "unicorn" in ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    )
    assert not any(
        isinstance(node.func, ast.Attribute)
        and node.func.attr in ("_fixture", "_run_case")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    )
    assert set(c.BODY_PINS) == {0x10E2A0, 0x7800, 0x35785D, 0x36FB17, 0x389156}
    assert sum(n for n, h in c.BODY_PINS.values()) == 656
    assert c.BODY_PINS[0x10E2A0] == (
        497,
        "641631ac31c522163cb141e846f21fa5e163ed176f042c3123762564c6d7d8ee",
    )
    assert len(c.SOURCE_PINS) == 4
    assert c.SOURCE_PINS["free_conformance"] == (
        "pe_native_vector_deallocation_conformance_joined",
        "8aba04f2be47f06284fbb3d00ebb7faa643613f99db3475fca54bd7f4cbc401a",
    )


@pytest.mark.parametrize("capacity", (1, 2, 3, 17, 511))
@pytest.mark.parametrize("used_selector", (0, 1, 2))
@pytest.mark.parametrize("alignment", (0, 7, 15))
def test_owned_dynamic_capacity_and_used_count_full15(
    capacity, used_selector, alignment
):
    used = (0, 1, capacity)[used_selector]
    packet = inputs(
        capacity=capacity,
        used=used,
        frame=0x30001000 + alignment,
        record=0x10000FF0 + alignment,
        path=0x20000FF8 + alignment,
        profile=alignment % 3,
    )
    before = copy.deepcopy(packet)
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["boundaries"][0]["registers"]["eax"] == capacity
    assert actual["boundaries"][0]["flags"] == (
        4 if (capacity & 255).bit_count() % 2 == 0 else 0
    )
    assert actual["boundaries"][0]["flag_mask"] == 0xC5
    strict_equal(packet, before)


@pytest.mark.parametrize("capacity", (1, 3, 17, 511))
def test_used_end_word_is_never_architecturally_read_or_used_to_free(
    capacity, monkeypatch
):
    outputs = []
    vectors = []

    def child(vector, initial, stack, error, *, stack_base):
        vectors.append(copy.deepcopy(vector))
        return free_law(vector, initial, stack, error, stack_base=stack_base)

    monkeypatch.setattr(c.deallocator, "_expected", child)
    for used in (0, capacity // 2, capacity):
        packet = inputs(capacity=capacity, used=used)
        actual = c.apply(**packet)
        check(actual, packet)
        outputs.append(actual)
    assert [v["count"] for v in vectors] == [capacity] * 3
    for key in (
        "pages",
        "registers",
        "xmm",
        "events",
        "trace_rvas",
        "record_bytes",
        "free_packet",
    ):
        strict_equal(outputs[0][key], outputs[1][key])
        strict_equal(outputs[1][key], outputs[2][key])
    assert not any(
        e["access"] == "read" and e["address"] == 0x10000FF0 + 0xD0
        for e in outputs[0]["events"]
    )


@pytest.mark.parametrize(
    "g,r,o,k",
    [
        (0x30000FFD, 0x10000FFF, 0x20000FF8, 511),
        (0xFFFFFFFB, 0x10000503, 0x20000FF8, 17),
        (0x30001000, 0x7FFFFFF0, 0xFFFFF007, 511),
        (0x30001000, 0xFFFFFECB, 0x20000FF8, 3),
        (0x30001000, 0x10000001, 0x10000135, 511),
        (0x30001000, 0x10000FF8, 0x10000000, 511),
        (0x30001000, 0x30001800, 0x30001E00, 511),
        (56, 0x10000200, 0x20000FF8, 17),
        (0x30001000, 0x10000200, 0x7FFFFFF9, 17),
        (0x30001000, 0x10000200, 0xFFFFFFF7, 1),
    ],
)
def test_cross_pages_high_bounds_adjacency_and_full_stack_window(g, r, o, k):
    packet = inputs(frame=g, record=r, path=o, capacity=k, used=0)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("capacity", (1, 17, 511))
@pytest.mark.parametrize("value", (0, 0x80000000, 0xFFFFFFFF))
def test_arbitrary_live_and_spare_payload_all_preserved(capacity, value):
    packet = inputs(capacity=capacity, used=1)
    for i in range(capacity * 2):
        store(packet["pages"], 0x20000FF8 + 4 * i, value ^ i)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("capacity", (1, 3, 17, 511))
def test_complete_actual_free_vector_and_pretransport_channel(capacity, monkeypatch):
    packet = inputs(capacity=capacity, used=0, frame=0x02000103)
    wanted = independent(packet)
    calls = []

    def child(vector, initial, stack, error, *, stack_base):
        calls.append(copy.deepcopy((vector, initial, stack, error, stack_base)))
        assert vector == dict(
            pointer=0x20000FF8,
            count=capacity,
            stride=8,
            metadata=None,
            responses=[dict(kind="heap_free", eax=1)],
            heap=0x12345678,
        )
        strict_equal(initial, wanted["boundaries"][0]["registers"])
        assert (
            len(stack) == 8192
            and stack_base == 0x02000000
            and error == packet["pages"][0x06000000]
        )
        result = free_law(vector, initial, stack, error, stack_base=stack_base)
        assert (
            result["events"][-1]["value"] == 0x04000000 and result["stop"] == 0x04000000
        )
        return result

    monkeypatch.setattr(c.deallocator, "_expected", child)
    check(c.apply(**packet), packet)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "kind",
    (
        "cap0",
        "cap512",
        "cap513",
        "unaligned_cap",
        "end_under",
        "end_over",
        "unaligned_end",
        "unused_spare_unmapped",
        "return_spare",
        "fullcap_record_overlap",
        "fullcap_frame_overlap",
    ),
)
def test_capacity_boundary_and_unused_capacity_extent(kind, monkeypatch):
    packet = inputs(capacity=3, used=0)
    r = 0x10000FF0
    o = 0x20000FF8
    if kind in ("cap0", "cap512", "cap513"):
        k = {"cap0": 0, "cap512": 512, "cap513": 513}[kind]
        store(packet["pages"], r + 0xD4, o + k * 8)
    elif kind == "unaligned_cap":
        store(packet["pages"], r + 0xD4, o + 23)
    elif kind == "end_under":
        store(packet["pages"], r + 0xD0, o - 8)
    elif kind == "end_over":
        store(packet["pages"], r + 0xD0, o + 32)
    elif kind == "unaligned_end":
        store(packet["pages"], r + 0xD0, o + 1)
    elif kind == "unused_spare_unmapped":
        del packet["pages"][0x20001000]
    elif kind == "return_spare":
        packet["return_address"] = o + 16
        store(packet["pages"], 0x30001000, o + 16)
    else:
        ptr = r - 16 if kind == "fullcap_record_overlap" else 0x30000FC0
        for off, value in ((0xCC, ptr), (0xD0, ptr), (0xD4, ptr + 24)):
            store(packet["pages"], r + off, value)

    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("invalid capacity reached free")

    monkeypatch.setattr(c.deallocator, "_expected", forbidden)
    with pytest.raises(c.RecordDestroyError):
        c.apply(**packet)
    assert calls == []


@pytest.mark.parametrize("capacity", (1, 17, 511))
def test_spare_counts_detached_nested_state_and_unchanged_inputs(capacity):
    packet = inputs(capacity=capacity, used=0)
    before = copy.deepcopy(packet)
    actual = c.apply(**packet)
    wanted = independent(packet)
    actual["free_packet"]["events"].clear()
    actual["free_packet"]["protocol"].clear()
    actual["boundaries"][0]["pages"].clear()
    actual["imported"]["registers"].clear()
    actual["pages"].clear()
    actual["xmm"].clear()
    strict_equal(packet, before)
    strict_equal(c.apply(**packet), wanted)


@pytest.mark.parametrize("owned", (False, True))
def test_null_or_k2n2_matches_old_actual_law_complete_packet(owned):
    from src.observatory import native_movement_effect_record_destroy_semantics as old

    packet = inputs(owned=owned, capacity=2, used=2)
    actual = c.apply(**packet)
    check(actual, packet)
    strict_equal(actual, old.apply(**packet))
