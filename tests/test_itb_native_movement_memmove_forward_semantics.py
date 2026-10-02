"""Independent memmove forward CRT copies including self-copy and leftward overlap.

Instruction addresses and access equations below are handwritten from the
pinned 36E580 scalar branch. Production is called only as the actual result.
"""

import copy
import inspect
from collections import UserDict

import pytest

from src.observatory import native_movement_memmove_forward_semantics as c

GPRS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMMS = tuple("xmm" + str(i) for i in range(8))
OUTPUT = {
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
}
PREFIX = (
    0x36E580,
    0x36E581,
    0x36E582,
    0x36E586,
    0x36E58A,
    0x36E58E,
    0x36E590,
    0x36E592,
    0x36E594,
    0x36E596,
)
WORD_LOOP = (0x36EA87, 0x36EA89, 0x36EA8B, 0x36EA8E, 0x36EA91, 0x36EA94)
BYTE_LOOP = (0x36EA9D, 0x36EA9F, 0x36EAA1, 0x36EAA2, 0x36EAA3, 0x36EAA4)
EXIT = (0x36EAB0, 0x36EAB4, 0x36EAB5, 0x36EAB6)
ORDINARY = [
    2 | sum(1 << bit for i, bit in enumerate((0, 2, 4, 6, 7, 9, 11)) if recipe >> i & 1)
    for recipe in range(128)
]


def read_bytes(pages, address, width):
    return bytes(
        pages[(address + i) // 4096 * 4096][(address + i) % 4096] for i in range(width)
    )


def word(pages, address):
    return int.from_bytes(read_bytes(pages, address, 4), "little")


def store(pages, address, payload):
    for i, byte in enumerate(payload):
        page, offset = divmod(address + i, 4096)
        key = page * 4096
        current = bytearray(pages[key])
        current[offset] = byte
        pages[key] = bytes(current)


def put_word(pages, address, value):
    store(pages, address, value.to_bytes(4, "little"))


def inputs(
    count=31,
    *,
    frame=0x30001003,
    source=0x10000FF0,
    destination=0x10002FF0,
    flags=0x246,
    return_address=0x04000000,
    profile=0,
):
    spans = [(frame - 8, frame + 16), (0x12340000, 0x12341000)]
    if count and count <= 31:
        spans += [(source, source + count), (destination, destination + count)]
    keys = {
        p
        for start, end in spans
        for p in range(start & ~4095, (end - 1 & ~4095) + 4096, 4096)
    }
    pages = {
        p: bytes((i * 53 + (p >> 12) * 17 + profile * 71) & 255 for i in range(4096))
        for p in keys
    }
    regs = {
        name: (0x91AB2345 + i * 0x13579B + profile * 0x314159) & 0xFFFFFFFF
        for i, name in enumerate(GPRS)
    }
    regs["esp"] = frame
    xmm = {
        name: (
            (
                0xFEDCBA98765432100123456789ABCDEF
                + i * 0x1122334455667789
                + profile * 0xABCDEF1234567890
            )
            & ((1 << 128) - 1)
        )
        for i, name in enumerate(XMMS)
    }
    for offset, value in enumerate((return_address, destination, source, count)):
        put_word(pages, frame + offset * 4, value)
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmm,
        return_address=return_address,
        entry_flags=flags,
    )


def independent(packet):
    """Literal branch, ordered accesses, and separately predicted final bytes."""
    pages = dict(packet["pages"])
    regs = dict(packet["registers"])
    g = regs["esp"]
    d, o, n = (word(pages, g + offset) for offset in (4, 8, 12))
    q, tail = divmod(n, 4)
    original_source = read_bytes(pages, o, n) if n else b""
    # Final memory is derived directly, rather than by replaying expected events.
    final = dict(pages)
    put_word(final, g - 4, regs["edi"])
    put_word(final, g - 8, regs["esi"])
    if n:
        store(final, d, original_source)
    events = [
        dict(access="write", address=g - 4, width=4, value=regs["edi"]),
        dict(access="write", address=g - 8, width=4, value=regs["esi"]),
    ]
    for address in (g + 8, g + 12, g + 4):
        events.append(
            dict(access="read", address=address, width=4, value=word(pages, address))
        )
    for i in range(q):
        value = int.from_bytes(original_source[4 * i : 4 * i + 4], "little")
        events.extend(
            (
                dict(access="read", address=o + 4 * i, width=4, value=value),
                dict(access="write", address=d + 4 * i, width=4, value=value),
            )
        )
    for i in range(tail):
        value = original_source[4 * q + i]
        events.extend(
            (
                dict(access="read", address=o + 4 * q + i, width=1, value=value),
                dict(access="write", address=d + 4 * q + i, width=1, value=value),
            )
        )
    for address, value in (
        (g + 4, d),
        (g - 8, regs["esi"]),
        (g - 4, regs["edi"]),
        (g, packet["return_address"]),
    ):
        events.append(dict(access="read", address=address, width=4, value=value))
    trace = list(PREFIX)
    if d > o:
        trace += [0x36E598, 0x36E59A]
    trace += [0x36E5A0, 0x36E5A3, 0x36EA7B, 0x36EA7E]
    if n:
        trace += [0x36EA80, 0x36EA82, 0x36EA85]
        trace += list(WORD_LOOP) * q
        trace += [0x36EA96, 0x36EA98, 0x36EA9B]
        trace += list(BYTE_LOOP) * tail
        if tail:
            trace += [0x36EAA6, 0x36EAAD]
    trace += list(EXIT)
    regs.update(
        eax=d,
        ecx=0,
        edx=(int.from_bytes(original_source[4 * q - 4 : 4 * q], "little") if q else n),
        esp=g + 4,
    )
    # Last TEST0 yields ZF+PF with AF undefined; last SUB1-1 defines AF0.
    return dict(
        geometry=dict(entry=g, source=o, destination=d, count=n),
        registers=regs,
        xmm=dict(packet["xmm"]),
        pages=final,
        events=events,
        trace_rvas=[f"0x{rva:08x}" for rva in trace],
        flags=0x44,
        flag_mask=0x8D5 if tail else 0x8C5,
        df=0,
        endpoint=packet["return_address"],
        source_snapshot=original_source,
    )


def equal(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert len(actual) == len(expected)
        assert {(type(k), k) for k in actual} == {(type(k), k) for k in expected}
        for key in expected:
            equal(actual[key], expected[key])
    elif type(expected) in (list, tuple):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            equal(a, b)
    else:
        assert actual == expected


def check(actual, packet):
    assert type(actual) is dict and set(actual) == OUTPUT
    equal(actual, independent(packet))
    g = packet["registers"]["esp"]
    n = word(packet["pages"], g + 12)
    q, r = divmod(n, 4)
    assert len(actual["events"]) == 9 + 2 * q + 2 * r
    assert len(actual["trace_rvas"]) == (
        24 + 6 * q + 6 * r + 2 * bool(r) if n else 18
    ) + 2 * (word(packet["pages"], g + 4) > word(packet["pages"], g + 8))
    replay = dict(packet["pages"])
    for event in actual["events"]:
        assert set(event) == {"access", "address", "width", "value"}
        if event["access"] == "read":
            assert (
                int.from_bytes(
                    read_bytes(replay, event["address"], event["width"]), "little"
                )
                == event["value"]
            )
        else:
            store(
                replay,
                event["address"],
                event["value"].to_bytes(event["width"], "little"),
            )
    equal(replay, actual["pages"])
    equal(read_bytes(actual["pages"], g, 16), read_bytes(packet["pages"], g, 16))


@pytest.mark.parametrize("count", range(32))
@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize("reverse", (False, True))
def test_all_counts_alignments_and_pointer_order(count, alignment, reverse):
    o, d = 0x10000FF0 + alignment, 0x10002FF0 + alignment
    if reverse:
        o, d = d, o
    packet = inputs(
        count,
        frame=0x30000FF8 + alignment,
        source=o,
        destination=d,
        profile=alignment % 3,
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("source_alignment", range(16))
@pytest.mark.parametrize("destination_alignment", range(16))
def test_independent_source_destination_alignment(
    source_alignment, destination_alignment
):
    packet = inputs(
        source=0x10000FF0 + source_alignment,
        destination=0x10002FF0 + destination_alignment,
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("flags", ORDINARY)
@pytest.mark.parametrize("count", (0, 1, 4, 31))
def test_all_ordinary_flags(count, flags):
    packet = inputs(count, flags=flags)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("count", range(1, 32))
@pytest.mark.parametrize("after", (False, True))
def test_adjacent_extents(count, after):
    o = 0x10001000
    packet = inputs(count, source=o, destination=o + count if after else o - count)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "source,destination",
    (
        (0, 0),
        (0xFFFFFFFF, 0xFFFFFFFF),
        (0, 0xFFFFFFFF),
        (0xFFFFFFFF, 0),
        (0x76E580, 0x76EAB6),
        (0x30001003, 0x30000FFB),
        (0xDEAD1234, 0xBEEF5678),
        (0x04000000, 0x04000000),
    ),
)
def test_zero_pointers_unmapped_unread_and_aliases_allowed(source, destination):
    packet = inputs(0, source=source, destination=destination)
    assert set(packet["pages"]) == {0x30000000, 0x30001000, 0x12340000}
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("count", (1, 3, 4, 15, 31))
@pytest.mark.parametrize("which", ("source", "destination", "frame"))
def test_conservative_top_of_uint32_extent(count, which):
    kwargs = {which: 0xFFFFFFFF - (16 if which == "frame" else count)}
    packet = inputs(count, **kwargs)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "return_address", (1, 0xFFFFFFFF, 0x76E57F, 0x76EAF4, 0x05000000)
)
def test_logical_return_words_outside_selected_body_and_data(return_address):
    packet = inputs(return_address=return_address)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "frame,source,destination",
    (
        (8, 0x10000FF0, 0x10002FF0),
        (0x10000FF8, 0x10002011, 0x1000300F),
        (0x30001003, 0x7FFFFFF0, 0x80001000),
        (0x30001003, 0x80001000, 0x7FFFFFF0),
        (0x30001003, 1, 0x10002FF0),
    ),
)
def test_minimum_frame_signed_boundary_and_shared_page_geometry(
    frame, source, destination
):
    packet = inputs(frame=frame, source=source, destination=destination)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("which", ("source", "destination"))
@pytest.mark.parametrize("after", (False, True))
def test_data_adjacent_to_protected_frame(which, after):
    frame = 0x30001003
    address = frame + 16 if after else frame - 8 - 31
    packet = inputs(frame=frame, **{which: address})
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("which", ("source", "destination", "frame"))
def test_return_at_exclusive_extent_end(which):
    packet = inputs()
    g = packet["registers"]["esp"]
    endpoint = {
        "source": word(packet["pages"], g + 8) + 31,
        "destination": word(packet["pages"], g + 4) + 31,
        "frame": g + 16,
    }[which]
    packet["return_address"] = endpoint
    put_word(packet["pages"], g, endpoint)
    check(c.apply(**packet), packet)


def test_full_gpr_xmm_arbitrary_extremes_and_padding():
    packet = inputs()
    for i, name in enumerate(GPRS[:-1]):
        packet["registers"][name] = 0 if i % 2 else 0xFFFFFFFF
    packet["xmm"] = {
        name: 0 if i % 2 else (1 << 128) - 1 for i, name in enumerate(XMMS)
    }
    packet["pages"][0x12340000] = bytes(range(256)) * 16
    before = copy.deepcopy(packet)
    actual = c.apply(**packet)
    check(actual, packet)
    equal(packet, before)


def test_source_tail_dword_and_byte_edx_cases():
    for count in (0, 1, 3, 4, 7, 8, 28, 31):
        packet = inputs(count)
        g = packet["registers"]["esp"]
        o = word(packet["pages"], g + 8)
        if count:
            store(packet["pages"], o, bytes((0xA7 - i * 7) & 255 for i in range(count)))
        actual = c.apply(**packet)
        check(actual, packet)
        assert actual["registers"]["edx"] == (
            word(packet["pages"], o + 4 * (count // 4 - 1)) if count >= 4 else count
        )


class IntAlias(int):
    pass


class StrAlias(str):
    pass


def reject(packet, monkeypatch):
    ledger = []
    original = c._write

    def observed(*args, **kwargs):
        ledger.append("write")
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(c, "_write", observed)
        before = copy.deepcopy(packet)
        with pytest.raises(c.MemmoveForwardError):
            c.apply(**packet)
        assert ledger == []
        equal(packet, before)


@pytest.mark.parametrize(
    "kind",
    (
        "pages_userdict",
        "pages_empty",
        "pages_float_key",
        "pages_bool_key",
        "pages_intalias_key",
        "pages_unaligned",
        "pages_negative",
        "pages_large",
        "pages_bytearray",
        "pages_short",
        "pages_code",
        "gpr_userdict",
        "gpr_missing",
        "gpr_extra",
        "gpr_bool",
        "gpr_float",
        "gpr_negative",
        "gpr_large",
        "gpr_intalias",
        "gpr_stralias",
        "xmm_userdict",
        "xmm_missing",
        "xmm_extra",
        "xmm_bool",
        "xmm_float",
        "xmm_negative",
        "xmm_large",
        "xmm_intalias",
        "xmm_stralias",
        "return_bool",
        "return_float",
        "return_zero",
        "return_negative",
        "return_large",
        "return_intalias",
        "flags_bool",
        "flags_float",
        "flags_negative",
        "flags_large",
        "flags_intalias",
        "flags_zero",
        "flags_four",
    ),
)
def test_typed_input_schemas_reject_before_write(kind, monkeypatch):
    p = inputs()
    if kind.startswith("pages_"):
        sub = kind[6:]
        if sub == "userdict":
            p["pages"] = UserDict(p["pages"])
        elif sub == "empty":
            p["pages"] = {}
        elif sub in ("float_key", "bool_key", "intalias_key"):
            old = 0x12340000
            value = p["pages"].pop(old)
            p["pages"][
                (
                    float(old)
                    if sub == "float_key"
                    else True if sub == "bool_key" else IntAlias(old)
                )
            ] = value
        elif sub == "unaligned":
            p["pages"][0x12340001] = bytes(4096)
        elif sub == "negative":
            p["pages"][-4096] = bytes(4096)
        elif sub == "large":
            p["pages"][1 << 32] = bytes(4096)
        elif sub == "bytearray":
            p["pages"][0x12340000] = bytearray(4096)
        elif sub == "short":
            p["pages"][0x12340000] = bytes(4095)
        elif sub == "code":
            p["pages"][0x76E000] = bytes(4096)
    elif kind.startswith(("gpr_", "xmm_")):
        group, sub = kind.split("_", 1)
        key = "registers" if group == "gpr" else "xmm"
        name = "eax" if group == "gpr" else "xmm0"
        if sub == "userdict":
            p[key] = UserDict(p[key])
        elif sub == "missing":
            p[key].pop(name)
        elif sub == "extra":
            p[key]["extra"] = 0
        elif sub == "stralias":
            value = p[key].pop(name)
            p[key][StrAlias(name)] = value
        else:
            p[key][name] = {
                "bool": True,
                "float": 0.0,
                "negative": -1,
                "large": 1 << (32 if group == "gpr" else 128),
                "intalias": IntAlias(0),
            }[sub]
    else:
        group, sub = kind.split("_", 1)
        key = "return_address" if group == "return" else "entry_flags"
        p[key] = {
            "bool": True,
            "float": 2.0,
            "zero": 0,
            "four": 4,
            "negative": -1,
            "large": 1 << 32,
            "intalias": IntAlias(2),
        }[sub]
    reject(p, monkeypatch)


@pytest.mark.parametrize(
    "bit", [i for i in range(32) if i not in (0, 1, 2, 4, 6, 7, 9, 11)]
)
def test_each_forbidden_flag_bit_before_write(bit, monkeypatch):
    reject(inputs(flags=2 | (1 << bit)), monkeypatch)


@pytest.mark.parametrize("flags", [v & ~2 for v in ORDINARY])
def test_required_reserved_bit_before_write(flags, monkeypatch):
    reject(inputs(flags=flags), monkeypatch)


@pytest.mark.parametrize(
    "kind",
    (
        "count32",
        "countmax",
        "bad_return_word",
        "frame_underflow",
        "frame_wrap",
        "source_zero",
        "destination_zero",
        "source_wrap",
        "destination_wrap",
        "source_unmapped",
        "destination_unmapped",
        "frame_unmapped",
        "source_last_page",
        "destination_last_page",
        "overlap_forward",
        "source_frame",
        "destination_frame",
        "return_frame",
        "return_source",
        "return_destination",
        "return_code_entry",
        "return_code_hole",
        "return_code_last",
    ),
)
def test_geometry_and_caller_premises_before_write(kind, monkeypatch):
    p = inputs()
    g = p["registers"]["esp"]
    o, d = word(p["pages"], g + 8), word(p["pages"], g + 4)
    if kind == "count32":
        put_word(p["pages"], g + 12, 32)
    elif kind == "countmax":
        put_word(p["pages"], g + 12, 0xFFFFFFFF)
    elif kind == "bad_return_word":
        put_word(p["pages"], g, 0x04000004)
    elif kind == "frame_underflow":
        p["registers"]["esp"] = 7
    elif kind == "frame_wrap":
        p["registers"]["esp"] = 0xFFFFFFF0
    elif kind in ("source_zero", "destination_zero", "source_wrap", "destination_wrap"):
        offset = 8 if kind.startswith("source") else 4
        put_word(p["pages"], g + offset, 0 if kind.endswith("zero") else 0xFFFFFFF0)
    elif kind in ("source_unmapped", "destination_unmapped"):
        put_word(p["pages"], g + (8 if kind.startswith("source") else 4), 0x20000000)
    elif kind == "frame_unmapped":
        p["pages"].pop(g & ~4095)
    elif kind == "source_last_page":
        p["pages"].pop((o + 30) & ~4095)
    elif kind == "destination_last_page":
        p["pages"].pop((d + 30) & ~4095)
    elif kind == "overlap_forward":
        put_word(p["pages"], g + 4, o + 1)
    elif kind in ("source_frame", "destination_frame"):
        put_word(p["pages"], g + (8 if kind.startswith("source") else 4), g - 8)
    else:
        endpoint = {
            "return_frame": g,
            "return_source": o,
            "return_destination": d,
            "return_code_entry": 0x76E580,
            "return_code_hole": 0x76E6A0,
            "return_code_last": 0x76EAF3,
        }[kind]
        p["return_address"] = endpoint
        put_word(p["pages"], g, endpoint)
    reject(p, monkeypatch)


def test_input_and_result_detachment():
    packet = inputs()
    before = copy.deepcopy(packet)
    first = c.apply(**packet)
    second = c.apply(**packet)
    check(first, before)
    equal(packet, before)
    first["registers"]["eax"] = 0
    first["xmm"]["xmm0"] = 0
    first["pages"][0x12340000] = bytes(4096)
    first["events"][0]["value"] = 0
    first["trace_rvas"][0] = "changed"
    first["geometry"]["count"] = 32
    packet["registers"]["eax"] = 0
    packet["xmm"]["xmm0"] = 0
    packet["pages"][0x12340000] = bytes(4096)
    check(second, before)


def test_exact_api_and_pinned_provenance():
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
    equal(
        c.BODY_PINS,
        {
            0x36E580: (
                1330,
                "8b0b052a9ad8d284940e5886d952cc89ebbcef586b2c46075afb6b4ce26dbc34",
            )
        },
    )
    equal(
        c.SOURCE_PINS,
        {
            "program_facts": (
                "pe_ghidra_program_facts",
                "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
            )
        },
    )


LEFT_CASES = tuple((n, shift) for n in range(1, 32) for shift in range(n))
RIGHT_CASES = tuple((n, shift) for n in range(2, 32) for shift in range(1, n))


@pytest.mark.parametrize("count,shift", LEFT_CASES)
@pytest.mark.parametrize("alignment", (0, 1, 7, 15))
def test_every_leftward_overlap_and_self_copy_full_eleven(count, shift, alignment):
    source = 0x10000FF0 + alignment
    packet = inputs(
        count,
        frame=0x30001000 + alignment,
        source=source,
        destination=source - shift,
        profile=(count + shift + alignment) % 3,
    )
    before = copy.deepcopy(packet)
    actual = c.apply(**packet)
    check(actual, packet)
    equal(packet, before)
    assert actual["source_snapshot"] == read_bytes(before["pages"], source, count)
    assert (
        read_bytes(actual["pages"], source - shift, count) == actual["source_snapshot"]
    )
    assert "0x0036e598" not in actual["trace_rvas"]
    assert "0x0036e834" not in actual["trace_rvas"]
    assert len(actual["trace_rvas"]) == (
        24 + 6 * (count // 4) + 6 * (count % 4) + 2 * bool(count % 4)
    )


@pytest.mark.parametrize("flags", ORDINARY)
@pytest.mark.parametrize("count,shift", ((4, 0), (4, 1), (7, 3)))
def test_all_flags_self_and_overlapping_word_and_tail_paths(flags, count, shift):
    packet = inputs(
        count, source=0x10000FFF, destination=0x10000FFF - shift, flags=flags
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("count,shift", RIGHT_CASES)
def test_every_rightward_overlap_is_rejected_before_first_write(
    count, shift, monkeypatch
):
    source = 0x10000FF0
    reject(inputs(count, source=source, destination=source + shift), monkeypatch)


@pytest.mark.parametrize(
    "frame,source,destination,count",
    (
        (8, 1 << 20, (1 << 20) - 1, 31),
        (0xFFFFFFEF, 0x10000FFF, 0x10000FFD, 31),
        (0x90001003, 0x7FFFFFF8, 0x7FFFFFF5, 31),
        (0x30001003, 0xFFFFFFE0, 0xFFFFFFDF, 31),
        (0x30001003, 0xFFFFFFE0, 0xFFFFFFE0, 31),
        (0x30001003, 0x30001013, 0x30001013, 31),
        (0x30001003, 0x30000FFB - 31, 0x30000FFA - 31, 31),
        (0x30001003, 0x30001014, 0x30001013, 31),
    ),
)
def test_overlapping_union_page_signed_top_and_stack_adjacency(
    frame, source, destination, count
):
    packet = inputs(count, frame=frame, source=source, destination=destination)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("reverse", (False, True))
def test_disjoint_buffers_can_straddle_stack_and_return_in_unread_gap(reverse):
    source, destination = 0x10000FF0, 0x30002FF0
    if reverse:
        source, destination = destination, source
    packet = inputs(
        31,
        frame=0x20001003,
        source=source,
        destination=destination,
        return_address=0x18000000,
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("delta", (0, 1, 15, 30))
def test_overlap_union_cannot_intersect_actual_frame_or_return(delta, monkeypatch):
    source = 0x10001000
    packet = inputs(31, source=source, destination=source - 1)
    frame = packet["registers"]["esp"]
    endpoint = source + delta
    packet["return_address"] = endpoint
    put_word(packet["pages"], frame, endpoint)
    reject(packet, monkeypatch)
    # A separate input puts the union against the live frame; caller words
    # are written last by inputs, so the fixture itself remains well formed.
    packet = inputs(31, frame=source + delta, source=source, destination=source - 1)
    reject(packet, monkeypatch)


def test_leftward_overlap_changes_source_region_but_preserves_original_snapshot():
    source = 0x10000FF0
    packet = inputs(31, source=source, destination=source - 1)
    original = bytes(range(1, 32))
    store(packet["pages"], source, original)
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["source_snapshot"] == original
    assert read_bytes(actual["pages"], source, 31) == original[1:] + original[-1:]
    assert actual["registers"]["edx"] == int.from_bytes(original[24:28], "little")
    assert read_bytes(packet["pages"], source, 31) == original


@pytest.mark.parametrize("shift", (0, 1))
def test_overlap_result_snapshot_events_and_pages_are_detached(shift):
    source = 0x10000FFF
    packet = inputs(31, source=source, destination=source - shift)
    before = copy.deepcopy(packet)
    first = c.apply(**packet)
    second = c.apply(**packet)
    saved = copy.deepcopy(first)
    first["pages"].clear()
    first["events"].clear()
    first["trace_rvas"].clear()
    first["registers"]["edx"] ^= 1
    first["xmm"]["xmm7"] ^= 1
    first["geometry"]["source"] ^= 1
    first["source_snapshot"] = bytes(31)
    equal(second, saved)
    equal(packet, before)


def test_selected_forward_source_identity_and_no_child_or_machine_delegation():
    assert c.ANALYSIS_KIND == "pe_native_movement_memmove_forward_semantics"
    assert len(LEFT_CASES) == 496 and len(RIGHT_CASES) == 465
    # The source freeze bound by HANDOFF is memmove cfd10fbf...f5df1. Provenance
    # here binds the selected atlas and actual API, without treating text
    # formatting as executable semantics or adding a new receipt identity.
    text = inspect.getsource(c)
    assert not any(value in text for value in ("unicorn", "capstone", "subprocess"))
    assert not any(value in text for value in ("_fixture(", "_run_case(", ".apply("))
