"""Independent actual-page default-record law; no native claim in this packet.

The literal owner/helper traces and access recipes below come from the reviewed
operand facts. Production apply is used only as the actual value under test.
"""

from __future__ import annotations

import ast
import copy
import inspect
import itertools

import pytest

from src.observatory import native_movement_effect_record_default_semantics as c

GPRS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMMS = tuple(f"xmm{i}" for i in range(8))
COOKIE = 0x893F28
LITERAL = 0x80DFDC
RET = 0x4000000
OFFSETS = (0x38, 0x50, 0x68, 0x80, 0xA4, 0xE0, 0x118)
RETURNS = (0x599A51, 0x599A84, 0x599AB4, 0x599AE7, 0x599B38, 0x599BC5, 0x599C1F)
CALLS = (0x199A4C, 0x199A7F, 0x199AAF, 0x199AE2, 0x199B33, 0x199BC0, 0x199C1A)
HELPER_TRACE = tuple(int(pc, 16) for pc in """
7fd0 7fd1 7fd3 7fd4 7fd7 7fd8 7fda 7fdc 7fde 7fe1 7fe4 7fea 7fec 7fee
8035 8036 8039 803c 803e 8041 805c 805e 8060 8064 8067 8077 8079 807a
807b 807c 807f 8080
""".split())
OWNER_TRACE = tuple(int(pc, 16) for pc in """
1999a0 1999a1 1999a3 1999a5 1999aa 1999b0 1999b1 1999b2 1999b3 1999b8
1999ba 1999bb 1999be 1999c4 1999c6 1999c9 1999cc 1999cf 1999d5 1999dc
1999df 1999e6 1999ed 1999f1 1999f8 1999ff 199a06 199a0d 199a14 199a1b
199a21 199a28 199a2f 199a36 199a3a 199a40 199a42 199a44 199a49 199a4c
199a51 199a54 199a5b 199a62 199a69 199a6d 199a73 199a75 199a77 199a7c
199a7f 199a84 199a87 199a8b 199a92 199a99 199a9d 199aa3 199aa5 199aa7
199aac 199aaf 199ab4 199aba 199abe 199ac5 199acc 199ad0 199ad6 199ad8
199ada 199adf 199ae2 199ae7 199aeb 199af1 199afb 199b05 199b0f 199b16
199b1d 199b21 199b27 199b29 199b2b 199b30 199b33 199b38 199b42 199b4c
199b56 199b60 199b6a 199b74 199b7e 199b82 199b88 199b92 199b9c 199ba3
199baa 199bae 199bb4 199bb6 199bb8 199bbd 199bc0 199bc5 199bcb 199bd2
199bd9 199bdd 199be1 199be4 199be8 199bee 199bf8 199c02 199c04 199c0b
199c12 199c17 199c1a 199c1f 199c29 199c2b 199c2e 199c35 199c36 199c37
199c39 199c3a
""".split())
PACKET_KEYS = {
    "record_address",
    "record_bytes",
    "argument",
    "registers",
    "xmm",
    "pages",
    "events",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "trace_rvas",
    "string_boundaries",
}
BOUNDARY_KEYS = {
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


def read_bytes(pages, address, width):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(width)
    )


def store(pages, address, value, width=4):
    for i, byte in enumerate(value.to_bytes(width, "little")):
        page = (address + i) & ~4095
        data = bytearray(pages[page])
        data[(address + i) & 4095] = byte
        pages[page] = bytes(data)


def inputs(
    *,
    frame=0x30001000,
    record=0x10000100,
    profile=0,
    argument=0,
    flags=0x246,
    return_address=RET,
    cookie=None,
    seh=None,
):
    spans = (
        (frame - 56, frame + 8),
        (record, record + 308),
        (0, 4),
        (COOKIE, COOKIE + 4),
        (LITERAL, LITERAL + 1),
    )
    addresses = {
        page
        for start, end in spans
        for page in range(start & ~4095, ((end - 1) & ~4095) + 1, 4096)
    }
    addresses.add(0x12340000)  # An unrelated complete page must preserve too.
    pages = {
        page: bytes((37 * i + 19 * j + profile * 53) & 255 for j in range(4096))
        for i, page in enumerate(sorted(addresses))
    }
    regs = {
        name: (0xA31F42D7 ^ (i * 0x13579BDF) ^ profile) & 0xFFFFFFFF
        for i, name in enumerate(GPRS)
    }
    regs.update(ecx=record, esp=frame)
    xmms = {
        name: int.from_bytes(
            bytes((i * 47 + j * 29 + profile * 61) & 255 for j in range(16)), "little"
        )
        for i, name in enumerate(XMMS)
    }
    store(pages, frame, return_address)
    store(pages, frame + 4, argument)
    store(
        pages,
        COOKIE,
        ((0xDCEFAB91 ^ profile * 0x314159) & 0xFFFFFFFF) if cookie is None else cookie,
    )
    store(
        pages,
        0,
        ((0x91EFCABD ^ profile * 0x812345) & 0xFFFFFFFF) if seh is None else seh,
    )
    store(pages, LITERAL, 0, 1)
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmms,
        return_address=return_address,
        entry_flags=flags,
    )


def independent_record(original, argument):
    """Final fields, independent of ordered owner/helper access recipes."""
    result = bytearray(original)
    dwords = {
        0: 0xFFFFFFFF,
        4: 0xFFFFFFFF,
        8: argument,
        12: 4,
        16: 0,
        24: 0,
        28: 0,
        32: 0,
        36: 0,
        40: 0,
        44: 0,
        52: 2,
        152: 0,
        156: 0xFFFFFFFF,
        160: 0xFFFFFFFF,
        188: 2,
        192: 2,
        196: 0,
        200: 0,
        204: 0,
        208: 0,
        212: 0,
        216: 0,
        220: 10,
        272: 0xFFFFFFFF,
        276: 0xFFFFFFFF,
        304: 3,
    }
    written = set()
    for offset, value in dwords.items():
        result[offset : offset + 4] = value.to_bytes(4, "little")
        written.update(range(offset, offset + 4))
    result[20] = 0
    result[48:50] = b"\0\0"
    written.update((20, 48, 49))
    for offset in (56, 80, 104, 128, 164, 224, 248, 280):
        result[offset] = 0
        result[offset + 16 : offset + 20] = bytes(4)
        result[offset + 20 : offset + 24] = (15).to_bytes(4, "little")
        written.update((offset,))
        written.update(range(offset + 16, offset + 24))
    assert len(written) == 183
    return bytes(result), written


def independent_packet(packet):
    """Handwritten constructor recipe with a distinct per-block access table."""
    original = packet["pages"]
    pages = dict(original)
    regs = packet["registers"]
    g, r = regs["esp"], regs["ecx"]
    f = g - 4
    cookie = int.from_bytes(read_bytes(original, COOKIE, 4), "little")
    seh = int.from_bytes(read_bytes(original, 0, 4), "little")
    arg = int.from_bytes(read_bytes(original, g + 4, 4), "little")
    events, boundaries = [], []

    def access(kind, address, width, value):
        if kind == "write":
            store(pages, address, value, width)
        else:
            assert int.from_bytes(read_bytes(pages, address, width), "little") == value
        events.append(dict(access=kind, address=address, width=width, value=value))

    def rows(recipe):
        for kind, address, width, value in recipe:
            access(kind, address, width, value)

    rows(
        (
            ("write", g - 4, 4, regs["ebp"]),
            ("write", g - 8, 4, 0xFFFFFFFF),
            ("write", g - 12, 4, 0x7B57A7),
            ("read", 0, 4, seh),
            ("write", g - 16, 4, seh),
            ("write", g - 20, 4, r),
            ("write", g - 24, 4, regs["esi"]),
            ("read", COOKIE, 4, cookie),
            ("write", g - 28, 4, cookie ^ f),
            ("write", 0, 4, g - 16),
            ("write", g - 20, 4, r),
            ("read", g + 4, 4, arg),
        )
    )
    for offset, width, value in (
        (0, 4, 0xFFFFFFFF),
        (4, 4, 0xFFFFFFFF),
        (8, 4, arg),
        (12, 4, 4),
        (16, 4, 0),
        (20, 1, 0),
        (24, 4, 0),
        (28, 4, 0),
        (32, 4, 0),
        (36, 4, 0),
        (40, 4, 0),
        (44, 4, 0),
        (48, 2, 0),
        (52, 4, 2),
    ):
        access("write", r + offset, width, value)
    # Each tuple is the exact owner access delta after the preceding helper.
    owner_deltas = (
        (),
        (("write", g - 8, 4, 0),),
        (("write", g - 8, 1, 1),),
        (("write", g - 8, 1, 2),),
        (
            ("write", g - 8, 1, 3),
            ("write", r + 152, 4, 0),
            ("write", r + 156, 4, 0xFFFFFFFF),
            ("write", r + 160, 4, 0xFFFFFFFF),
        ),
        tuple(
            ("write", r + off, 4, val)
            for off, val in (
                (188, 2),
                (192, 2),
                (196, 0),
                (200, 0),
                (204, 0),
                (208, 0),
                (212, 0),
            )
        )
        + (("write", g - 8, 1, 5), ("write", r + 216, 4, 0), ("write", r + 220, 4, 10)),
        (
            ("write", r + 268, 4, 15),
            ("write", r + 264, 4, 0),
            ("read", r + 268, 4, 15),
            ("write", r + 248, 1, 0),
            ("write", g - 8, 1, 7),
            ("write", r + 272, 4, 0xFFFFFFFF),
            ("write", r + 276, 4, 0xFFFFFFFF),
        ),
    )

    def save_boundary(name, i, state):
        boundaries.append(
            dict(
                name=name,
                index=i,
                registers=state,
                xmm=dict(packet["xmm"]),
                pages=dict(pages),
                events=copy.deepcopy(events),
                flags=0x85,
                flag_mask=0x8D5,
                df=0,
                endpoint=0x407FD0 if name == "entry" else RETURNS[i],
            )
        )

    for i, (offset, continuation) in enumerate(zip(OFFSETS, RETURNS)):
        s = r + offset
        rows(owner_deltas[i])
        if i == 6:
            rows(
                (
                    ("write", g - 32, 4, 0),
                    ("write", s + 20, 4, 15),
                    ("write", s + 16, 4, 0),
                )
            )
        else:
            rows(
                (
                    ("write", s + 20, 4, 15),
                    ("write", s + 16, 4, 0),
                    ("read", s + 20, 4, 15),
                    ("write", g - 32, 4, 0),
                )
            )
        rows(
            (
                ("write", g - 36, 4, LITERAL),
                ("write", s, 1, 0),
                ("write", g - 40, 4, continuation),
            )
        )
        save_boundary(
            "entry",
            i,
            dict(regs, eax=r + 248 if i == 6 else s, ecx=s, esi=r, ebp=f, esp=g - 40),
        )
        rows(
            (
                ("write", g - 44, 4, f),
                ("write", g - 48, 4, regs["ebx"]),
                ("read", g - 36, 4, LITERAL),
                ("write", g - 52, 4, r),
                ("read", s + 20, 4, 15),
                ("write", g - 56, 4, regs["edi"]),
                ("read", g - 32, 4, 0),
                ("read", s + 20, 4, 15),
                ("read", s + 20, 4, 15),
                ("write", s + 16, 4, 0),
                ("read", g - 56, 4, regs["edi"]),
                ("read", g - 52, 4, r),
                ("read", g - 48, 4, regs["ebx"]),
                ("write", s, 1, 0),
                ("read", g - 44, 4, f),
                ("read", g - 40, 4, continuation),
            )
        )
        save_boundary("return", i, dict(regs, eax=s, ecx=15, esi=r, ebp=f, esp=g - 28))
    rows(
        (
            ("write", r + 304, 4, 3),
            ("read", g - 16, 4, seh),
            ("write", 0, 4, seh),
            ("read", g - 28, 4, cookie ^ f),
            ("read", g - 24, 4, regs["esi"]),
            ("read", g - 4, 4, regs["ebp"]),
            ("read", g, 4, packet["return_address"]),
        )
    )
    trace = []
    for pc in OWNER_TRACE:
        trace.append(f"0x{pc:08x}")
        if pc in CALLS:
            trace.extend(f"0x{child:08x}" for child in HELPER_TRACE)
    return dict(
        record_address=r,
        record_bytes=read_bytes(pages, r, 308),
        argument=arg,
        registers=dict(regs, eax=r, ecx=cookie ^ f, esp=g + 8),
        xmm=dict(packet["xmm"]),
        pages=pages,
        events=events,
        flags=0x85,
        flag_mask=0x8D5,
        df=0,
        endpoint=packet["return_address"],
        trace_rvas=trace,
        string_boundaries=boundaries,
    )


def check_packet(actual, packet):
    wanted = independent_packet(packet)
    assert type(actual) is dict and set(actual) == PACKET_KEYS
    assert_strict_packet(actual, wanted)
    assert len(actual["events"]) == 217
    assert len(actual["trace_rvas"]) == 356
    assert len(set(actual["trace_rvas"])) == 164
    assert len(actual["string_boundaries"]) == 14
    assert [(b["name"], b["index"]) for b in actual["string_boundaries"]] == list(
        itertools.chain.from_iterable((("entry", i), ("return", i)) for i in range(7))
    )
    assert all(
        type(b) is dict and set(b) == BOUNDARY_KEYS for b in actual["string_boundaries"]
    )
    r = packet["registers"]["ecx"]
    record, written = independent_record(
        read_bytes(packet["pages"], r, 308), wanted["argument"]
    )
    assert actual["record_bytes"] == record
    assert all(
        actual["record_bytes"][i] == read_bytes(packet["pages"], r + i, 1)[0]
        for i in set(range(308)) - written
    )
    changed = {
        row["address"] + j - r
        for row in actual["events"]
        if row["access"] == "write"
        for j in range(row["width"])
        if r <= row["address"] + j < r + 308
    }
    assert changed == written and len(set(range(308)) - written) == 125
    assert not any(
        row["address"] == LITERAL and row["access"] == "read"
        for row in actual["events"]
    )
    forbidden = {
        0x008014,
        0x00802A,
        0x008049,
        0x00808C,
        0x0080C0,
        0x3574CA,
        0x3435D9,
        0x7800,
    }
    assert not forbidden.intersection(int(pc, 16) for pc in actual["trace_rvas"])


def assert_strict_packet(actual, wanted):
    assert type(actual) is type(wanted)
    if type(wanted) is dict:
        assert set(actual) == set(wanted)
        assert all(
            any(type(key) is type(other) and key == other for other in wanted)
            for key in actual
        )
        for key in wanted:
            assert_strict_packet(actual[key], wanted[key])
    elif type(wanted) in (list, tuple):
        assert len(actual) == len(wanted)
        for left, right in zip(actual, wanted):
            assert_strict_packet(left, right)
    else:
        assert actual == wanted


@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize("profile", range(3))
def test_complete_independent_law(alignment, profile):
    packet = inputs(
        frame=0x30001000 + alignment,
        record=0x10000100 + alignment,
        profile=profile,
        argument=(0xFFFFFFFF, 0x80000000, 0)[profile],
    )
    original = copy.deepcopy(packet)
    check_packet(c.apply(**packet), packet)
    assert packet == original


@pytest.mark.parametrize(
    "flags",
    [
        2
        | sum(
            1 << bit
            for i, bit in enumerate((0, 2, 4, 6, 7, 9, 11))
            if selector >> i & 1
        )
        for selector in range(128)
    ],
)
def test_all_ordinary_flags(flags):
    packet = inputs(flags=flags)
    check_packet(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "frame,record",
    [
        (0x30001004, 0x10000FE8),
        (0x30001037, 0x7FFFFFF0),
        (0x30001FF7, 0xFFFFFECB),
        (0x30000038, 0x10000100),
        (60, 0x10000100),
        (0xFFFFFFF7, 0x10000100),
        (0x4080FD, 0x10000100),  # Touched frame starts at the helper's exclusive end.
    ],
)
def test_cross_page_uint32_and_exact_frame_edges(frame, record):
    packet = inputs(frame=frame, record=record, argument=0x7FC01234, flags=0xAD7)
    check_packet(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "argument", [0, 1, 0xFFFFFFFF, 0x80000000, 0x7FC01234, 0xBF800000]
)
@pytest.mark.parametrize(
    "cookie,seh", [(0, 0), (0xFFFFFFFF, 0xFFFFFFFF), (0x80000000, 0x12345678)]
)
def test_uninterpreted_argument_saved_cookie_and_seh(argument, cookie, seh):
    packet = inputs(argument=argument, cookie=cookie, seh=seh)
    check_packet(c.apply(**packet), packet)


@pytest.mark.parametrize("seed", [0, 0xFFFFFFFF, 0x80000000])
def test_arbitrary_full_registers_and_xmm(seed):
    packet = inputs()
    for name in GPRS:
        if name not in ("ecx", "esp"):
            packet["registers"][name] = seed
    packet["xmm"] = {
        name: (seed << 96) | (seed << 64) | (seed << 32) | seed for name in XMMS
    }
    check_packet(c.apply(**packet), packet)


def test_results_are_detached_from_inputs_and_each_other():
    packet = inputs()
    untouched = copy.deepcopy(packet)
    first = c.apply(**packet)
    second = c.apply(**packet)
    first["registers"]["edx"] ^= 1
    first["xmm"]["xmm3"] ^= 1
    first["pages"][0] = bytes(4096)
    first["events"][0]["value"] ^= 1
    first["string_boundaries"][0]["pages"][0] = bytes(4096)
    first["string_boundaries"][0]["events"][0]["value"] ^= 1
    assert packet == untouched
    check_packet(second, packet)
    assert (
        first["string_boundaries"][1]["pages"][0]
        == second["string_boundaries"][1]["pages"][0]
    )
    assert (
        first["string_boundaries"][1]["events"][0]
        == second["string_boundaries"][1]["events"][0]
    )


@pytest.mark.parametrize("bit", [bit for bit in range(32) if not (0xAD7 >> bit & 1)])
def test_forbidden_entry_flags(bit):
    packet = inputs(flags=2 | (1 << bit))
    with pytest.raises(c.DefaultRecordError):
        c.apply(**packet)


@pytest.mark.parametrize("flags", [0, 4, 0x200, 0xAD5, True, 2.0, -1, 2**32])
def test_missing_reserved_bit_and_malformed_flags(flags):
    packet = inputs(flags=flags)
    with pytest.raises(c.DefaultRecordError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "group,key,value",
    [
        ("registers", "eax", True),
        ("registers", "edx", 0.0),
        ("registers", "ebp", -1),
        ("registers", "edi", 2**32),
        ("xmm", "xmm0", True),
        ("xmm", "xmm7", 0.0),
        ("xmm", "xmm3", -1),
        ("xmm", "xmm4", 2**128),
    ],
)
def test_full_register_scalar_types(group, key, value):
    packet = inputs()
    packet[group][key] = value
    with pytest.raises(c.DefaultRecordError):
        c.apply(**packet)


@pytest.mark.parametrize("group", ["registers", "xmm"])
@pytest.mark.parametrize("kind", ["missing", "extra", "sequence"])
def test_closed_register_schemas(group, kind):
    packet = inputs()
    if kind == "missing":
        packet[group].pop(next(iter(packet[group])))
    elif kind == "extra":
        packet[group]["unexpected"] = 0
    else:
        packet[group] = list(packet[group].values())
    with pytest.raises(c.DefaultRecordError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    [
        "bool_address",
        "float_address",
        "negative_address",
        "unaligned_address",
        "wrapped_address",
        "short_page",
        "bytearray_page",
        "sequence",
        "empty",
        "missing_stack",
        "missing_record",
        "missing_cookie",
        "missing_literal",
        "missing_fs",
    ],
)
def test_page_types_and_complete_mapping(kind):
    packet = inputs()
    pages = packet["pages"]
    if kind in ("bool_address", "float_address"):
        value = pages.pop(0)
        pages[False if kind == "bool_address" else 0.0] = value
    elif kind in ("negative_address", "unaligned_address", "wrapped_address"):
        pages[
            {
                "negative_address": -1,
                "unaligned_address": 1,
                "wrapped_address": 2**32,
            }[kind]
        ] = bytes(4096)
    elif kind == "short_page":
        pages[0] = bytes(4095)
    elif kind == "bytearray_page":
        pages[0] = bytearray(pages[0])
    elif kind == "sequence":
        packet["pages"] = list(pages.values())
    elif kind == "empty":
        packet["pages"] = {}
    else:
        target = {
            "missing_stack": packet["registers"]["esp"] - 56,
            "missing_record": packet["registers"]["ecx"],
            "missing_cookie": COOKIE,
            "missing_literal": LITERAL,
            "missing_fs": 0,
        }[kind]
        pages.pop(target & ~4095)
    with pytest.raises(c.DefaultRecordError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    [
        "record_below_source",
        "record_equal_source",
        "record_wrap",
        "frame_low",
        "frame_wrap",
        "record_frame_overlap",
        "record_cookie_overlap",
        "frame_cookie_overlap",
        "record_literal_overlap",
        "record_selected_code",
        "frame_selected_code",
    ],
)
def test_geometry_and_alias_rejections(kind):
    packet = inputs()
    g = packet["registers"]["esp"]
    newrecord = {
        "record_below_source": LITERAL - 1,
        "record_equal_source": LITERAL,
        "record_wrap": 0xFFFFFECC,
        "record_frame_overlap": g - 20,
        "record_cookie_overlap": COOKIE - 16,
        "record_literal_overlap": LITERAL,
        "record_selected_code": 0x5999A0,
    }
    if kind in newrecord:
        packet["registers"]["ecx"] = newrecord[kind]
    else:
        packet["registers"]["esp"] = {
            "frame_low": 55,
            "frame_wrap": 0xFFFFFFF8,
            "frame_cookie_overlap": COOKIE + 20,
            "frame_selected_code": 0x408000,
        }[kind]
        if kind == "frame_selected_code":
            packet = inputs(frame=0x408000)
    with pytest.raises(c.DefaultRecordError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "return_address",
    [
        0,
        True,
        0.0,
        -1,
        2**32,
        0x5999A0,
        0x407FD0,
        COOKIE,
        LITERAL,
        0x30001000,
        0x10000100,
    ],
)
def test_return_address_rejections(return_address):
    packet = inputs()
    packet["return_address"] = return_address
    if type(return_address) is int and 0 <= return_address <= 0xFFFFFFFF:
        store(packet["pages"], packet["registers"]["esp"], return_address)
    with pytest.raises(c.DefaultRecordError):
        c.apply(**packet)


def test_installed_return_and_complete_literal_are_bound():
    packet = inputs()
    store(packet["pages"], packet["registers"]["esp"], RET + 1)
    with pytest.raises(c.DefaultRecordError):
        c.apply(**packet)
    packet = inputs()
    store(packet["pages"], LITERAL, 1, 1)
    with pytest.raises(c.DefaultRecordError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "return_address", [4, 0x599C3D, 0x4080C5, 0x30002000, 0xFFFFFFFF, 0x657397]
)
def test_external_and_selected_body_adjacent_returns(return_address):
    packet = inputs(return_address=return_address)
    check_packet(c.apply(**packet), packet)


def test_record_and_frame_exact_adjacency_are_admitted():
    for record in (0x30001008, 0x30001000 - 56 - 308):
        packet = inputs(record=record)
        check_packet(c.apply(**packet), packet)


@pytest.mark.parametrize("group", ["registers", "xmm"])
def test_register_key_subclasses_are_rejected(group):
    class Alias(str):
        pass

    packet = inputs()
    key = next(iter(packet[group]))
    value = packet[group].pop(key)
    packet[group][Alias(key)] = value
    with pytest.raises(c.DefaultRecordError):
        c.apply(**packet)


@pytest.mark.parametrize("group", ["pages", "registers", "xmm"])
def test_mapping_subclasses_are_rejected(group):
    class Alias(dict):
        pass

    packet = inputs()
    packet[group] = Alias(packet[group])
    with pytest.raises(c.DefaultRecordError):
        c.apply(**packet)


def test_invalid_input_rejection_preserves_supplied_state():
    packet = inputs()
    store(packet["pages"], LITERAL, 1, 1)
    original = copy.deepcopy(packet)
    with pytest.raises(c.DefaultRecordError):
        c.apply(**packet)
    assert_strict_packet(packet, original)


def test_exact_source_contract_and_no_execution_dependencies():
    assert c.SOURCE_PINS == {
        "program_facts": (
            "pe_ghidra_program_facts",
            "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
        ),
        "movement_binding": (
            "pe_native_movement_effect_binding",
            "54c060913d61f6bb5e4c1f2586f0d5186ea73ad6c058dd48b1cc056e64a410b9",
        ),
    }
    assert c.BODY_PINS == {
        0x1999A0: (
            669,
            "2f17cc9bd3616c14305fb7fc1871bf0e37d09262825a99213f5b0568d6c6045d",
        ),
        0x7FD0: (
            245,
            "c49f0e24bd27ed5495ceddc13536ca6fbe85d8c97f207db817ce0642b8b01906",
        ),
    }
    tree = ast.parse(inspect.getsource(c))
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert all(
        (isinstance(node, ast.ImportFrom) and node.module == "__future__")
        or (
            isinstance(node, ast.Import)
            and [name.name for name in node.names] == ["copy"]
        )
        for node in imports
    )
    assert not any(
        isinstance(node, ast.Name)
        and node.id in ("_fixture", "_run_case", "unicorn", "pefile", "capstone")
        for node in ast.walk(tree)
    )
