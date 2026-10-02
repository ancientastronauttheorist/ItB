"""Independent selected right-overlap descending scalar CRT copy contract."""

import copy
import inspect
from collections import UserDict

import pytest

from src.observatory import native_movement_small_backward_copy_semantics as c
from tests import test_itb_native_movement_small_memcpy_semantics as m

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
}
PREFIX = (
    0x3703E0,
    0x3703E1,
    0x3703E2,
    0x3703E6,
    0x3703EA,
    0x3703EE,
    0x3703F0,
    0x3703F2,
    0x3703F4,
    0x3703F6,
    0x3703F8,
    0x3703FA,
    0x370694,
    0x370697,
    0x37069A,
    0x37069D,
    0x3707F4,
    0x3707FA,
)
WORD_LOOP = (0x3707FC, 0x3707FF, 0x370802, 0x370804, 0x370806, 0x370809, 0x37080F)
BYTE_LOOP = (0x370815, 0x370818, 0x37081B, 0x37081D, 0x37081F, 0x370822)
EXIT = (0x370824, 0x370828, 0x370829, 0x37082A)
PAIRS = [(n, shift) for n in range(2, 32) for shift in range(1, n)]


def inputs(
    count=31,
    shift=1,
    *,
    source=0x10000FF0,
    frame=0x30001003,
    flags=0x246,
    return_address=0x04000000,
    profile=0,
):
    return m.inputs(
        count,
        source=source,
        destination=source + shift,
        frame=frame,
        flags=flags,
        return_address=return_address,
        profile=profile,
    )


def independent(packet):
    """Original snapshot blit plus literal descending access and trace equations."""
    g = packet["registers"]["esp"]
    d, o, n = (m.word(packet["pages"], g + off) for off in (4, 8, 12))
    q, r = divmod(n, 4)
    source = m.read_bytes(packet["pages"], o, n)
    final = dict(packet["pages"])
    m.put_word(final, g - 4, packet["registers"]["edi"])
    m.put_word(final, g - 8, packet["registers"]["esi"])
    m.store(final, d, source)
    events = [
        dict(access="write", address=g - 4, width=4, value=packet["registers"]["edi"]),
        dict(access="write", address=g - 8, width=4, value=packet["registers"]["esi"]),
    ]
    for at in (g + 8, g + 12, g + 4):
        events.append(
            dict(access="read", address=at, width=4, value=m.word(packet["pages"], at))
        )
    trace = list(PREFIX)
    for i in range(q):
        off = n - 4 * (i + 1)
        value = int.from_bytes(source[off : off + 4], "little")
        events.extend(
            (
                dict(access="read", address=o + off, width=4, value=value),
                dict(access="write", address=d + off, width=4, value=value),
            )
        )
        trace += list(WORD_LOOP)
    trace += [0x370811, 0x370813]
    for i in range(r):
        off = r - i - 1
        value = source[off]
        events.extend(
            (
                dict(access="read", address=o + off, width=1, value=value),
                dict(access="write", address=d + off, width=1, value=value),
            )
        )
        trace += list(BYTE_LOOP)
    for at, value in (
        (g + 4, d),
        (g - 8, packet["registers"]["esi"]),
        (g - 4, packet["registers"]["edi"]),
        (g, packet["return_address"]),
    ):
        events.append(dict(access="read", address=at, width=4, value=value))
    trace += list(EXIT)
    # DWORD MOV changes EAX, never EDX: prefix MOV EDX,N survives both loops.
    return dict(
        geometry=dict(entry=g, source=o, destination=d, count=n),
        registers=dict(packet["registers"], eax=d, ecx=0, edx=n, esp=g + 4),
        xmm=dict(packet["xmm"]),
        pages=final,
        events=events,
        trace_rvas=[f"0x{pc:08x}" for pc in trace],
        flags=0x44,
        flag_mask=0x8D5 if r else 0x8C5,
        df=0,
        endpoint=packet["return_address"],
        source_snapshot=source,
    )


def check(actual, packet):
    assert type(actual) is dict and set(actual) == KEYS
    m.equal(actual, independent(packet))
    g = packet["registers"]["esp"]
    d, o, n = (m.word(packet["pages"], g + off) for off in (4, 8, 12))
    q, r = divmod(n, 4)
    assert len(actual["trace_rvas"]) == 24 + 7 * q + 6 * r
    assert len(actual["events"]) == 9 + 2 * q + 2 * r
    assert actual["registers"]["edx"] == n
    # Reads are replayed against evolving overlapping memory, rather than
    # assuming the whole original source remains unchanged after destination writes.
    replay = dict(packet["pages"])
    for ev in actual["events"]:
        at, w, value = ev["address"], ev["width"], ev["value"]
        assert type(ev) is dict and set(ev) == {"access", "address", "width", "value"}
        if ev["access"] == "read":
            assert int.from_bytes(m.read_bytes(replay, at, w), "little") == value
        else:
            m.store(replay, at, value.to_bytes(w, "little"))
    m.equal(replay, actual["pages"])
    assert m.read_bytes(actual["pages"], d, n) == m.read_bytes(packet["pages"], o, n)
    assert m.read_bytes(actual["pages"], o, d - o) == m.read_bytes(
        packet["pages"], o, d - o
    )
    assert m.read_bytes(actual["pages"], g, 16) == m.read_bytes(packet["pages"], g, 16)
    writes = {
        ev["address"] + i
        for ev in actual["events"]
        if ev["access"] == "write"
        for i in range(ev["width"])
    }
    assert writes == set(range(d, d + n)) | set(range(g - 8, g))
    reads = [
        (ev["address"], ev["width"])
        for ev in actual["events"][5:-4]
        if ev["access"] == "read"
    ]
    assert reads == [(o + n - 4 * (i + 1), 4) for i in range(q)] + [
        (o + r - i - 1, 1) for i in range(r)
    ]


@pytest.mark.parametrize("count,shift", PAIRS)
@pytest.mark.parametrize("alignment", range(16))
def test_all_counts_shifts_and_alignments(count, shift, alignment):
    packet = inputs(
        count,
        shift,
        source=0x10000FF0 + alignment,
        frame=0x30000FF8 + alignment,
        profile=alignment % 3,
    )
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    m.equal(packet, before)


@pytest.mark.parametrize("flags", m.ORDINARY)
@pytest.mark.parametrize("count,shift", ((2, 1), (4, 3), (15, 7), (31, 1)))
def test_all_ordinary_flags_on_word_byte_and_mixed_loops(flags, count, shift):
    packet = inputs(count, shift, flags=flags)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "count,shift", ((2, 1), (4, 1), (7, 3), (8, 7), (15, 1), (31, 30))
)
@pytest.mark.parametrize(
    "source,frame",
    (
        (1, 0x30001003),
        (0x10000FF0, 8),
        (0x7FFFFFF0, 0x30001003),
        (0x80000000, 0x30001003),
        (0x10000FF0, 0xFFFFFFFF - 16),
    ),
)
def test_broad_minimum_signed_crossing_and_frame_end_geometry(
    count, shift, source, frame
):
    packet = inputs(count, shift, source=source, frame=frame)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("count,shift", ((2, 1), (4, 3), (15, 7), (31, 30)))
def test_union_ends_at_conservative_uint32_maximum(count, shift):
    packet = inputs(count, shift, source=0xFFFFFFFF - count - shift)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("after", (False, True))
@pytest.mark.parametrize("count,shift", ((2, 1), (15, 7), (31, 30)))
def test_union_adjacent_to_frame_same_page(after, count, shift):
    g = 0x30001003
    o = g + 16 if after else g - 8 - count - shift
    packet = inputs(count, shift, source=o, frame=g)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("endpoint", (1, 0xFFFFFFFF, 0x7703DF, 0x770954, 0x05000000))
def test_positive_logical_return_endpoints(endpoint):
    packet = inputs(return_address=endpoint)
    check(c.apply(**packet), packet)


def test_no_tail_last_test_and_tail_last_sub_defined_flags():
    for count in range(2, 32):
        packet = inputs(count, 1)
        actual = c.apply(**packet)
        check(actual, packet)
        assert actual["flags"] == 0x44 and actual["df"] == 0
        assert actual["flag_mask"] == (0x8D5 if count % 4 else 0x8C5)


def test_overlap_changes_source_suffix_without_changing_source_snapshot():
    packet = inputs(31, 1)
    g = packet["registers"]["esp"]
    o = m.word(packet["pages"], g + 8)
    m.store(packet["pages"], o, bytes(range(31)))
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["source_snapshot"] == bytes(range(31))
    assert m.read_bytes(actual["pages"], o, 31) == b"\0" + bytes(range(30))
    assert m.read_bytes(actual["pages"], o, 31) != actual["source_snapshot"]


def test_arbitrary_gpr_xmm_and_ancestor_page_values():
    packet = inputs()
    for i, name in enumerate(m.GPRS[:-1]):
        packet["registers"][name] = 0 if i % 2 else 0xFFFFFFFF
    packet["xmm"] = {
        name: 0 if i % 2 else (1 << 128) - 1 for i, name in enumerate(m.XMMS)
    }
    packet["pages"][0x12340000] = bytes(range(256)) * 16
    check(c.apply(**packet), packet)


def reject(packet, monkeypatch):
    before = copy.deepcopy(packet)
    ledger = []
    original = c._write

    def observed(*args, **kwargs):
        ledger.append("write")
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(c, "_write", observed)
        with pytest.raises(c.SmallBackwardCopyError):
            c.apply(**packet)
        assert ledger == []
    m.equal(packet, before)


@pytest.mark.parametrize(
    "kind",
    (
        "count0",
        "count1",
        "count32",
        "countmax",
        "equal",
        "leftward",
        "adjacent",
        "disjoint",
        "source_zero",
        "source_wrap",
        "destination_wrap",
        "unmapped_union",
        "last_union_page",
        "union_frame",
        "frame_underflow",
        "frame_wrap",
        "frame_unmapped",
        "bad_return_word",
        "return_frame",
        "return_union",
        "return_body",
        "return_body_hole",
        "code_page",
    ),
)
def test_branch_geometry_and_mapping_rejected_before_write(kind, monkeypatch):
    p = inputs()
    g = p["registers"]["esp"]
    o = m.word(p["pages"], g + 8)
    if kind.startswith("count"):
        m.put_word(
            p["pages"],
            g + 12,
            {"count0": 0, "count1": 1, "count32": 32, "countmax": 0xFFFFFFFF}[kind],
        )
    elif kind in ("equal", "leftward", "adjacent", "disjoint"):
        m.put_word(
            p["pages"],
            g + 4,
            o + {"equal": 0, "leftward": -1, "adjacent": 31, "disjoint": 32}[kind],
        )
    elif kind == "source_zero":
        m.put_word(p["pages"], g + 8, 0)
    elif kind == "source_wrap":
        m.put_word(p["pages"], g + 8, 0xFFFFFFF0)
        m.put_word(p["pages"], g + 4, 0xFFFFFFF1)
    elif kind == "destination_wrap":
        m.put_word(p["pages"], g + 8, 0xFFFFFFDC)
        m.put_word(p["pages"], g + 4, 0xFFFFFFED)
    elif kind == "unmapped_union":
        m.put_word(p["pages"], g + 8, 0x20000000)
        m.put_word(p["pages"], g + 4, 0x20000001)
    elif kind == "last_union_page":
        p["pages"].pop((o + 31) & ~4095)
    elif kind == "union_frame":
        m.put_word(p["pages"], g + 8, g - 8)
        m.put_word(p["pages"], g + 4, g - 7)
    elif kind == "frame_underflow":
        p["registers"]["esp"] = 7
    elif kind == "frame_wrap":
        p["registers"]["esp"] = 0xFFFFFFF0
    elif kind == "frame_unmapped":
        p["pages"].pop(g & ~4095)
    elif kind == "bad_return_word":
        m.put_word(p["pages"], g, 0x04000004)
    elif kind in ("return_frame", "return_union", "return_body", "return_body_hole"):
        endpoint = {
            "return_frame": g,
            "return_union": o,
            "return_body": 0x7703E0,
            "return_body_hole": 0x770900,
        }[kind]
        p["return_address"] = endpoint
        m.put_word(p["pages"], g, endpoint)
    elif kind == "code_page":
        p["pages"][0x770000] = bytes(4096)
    reject(p, monkeypatch)


@pytest.mark.parametrize(
    "kind",
    (
        "pages_userdict",
        "pages_empty",
        "pages_float",
        "pages_intalias",
        "pages_mutable",
        "pages_short",
        "pages_unaligned",
        "pages_large",
        "gpr_userdict",
        "gpr_missing",
        "gpr_extra",
        "gpr_bool",
        "gpr_float",
        "gpr_intalias",
        "gpr_stralias",
        "gpr_negative",
        "gpr_large",
        "xmm_userdict",
        "xmm_missing",
        "xmm_extra",
        "xmm_bool",
        "xmm_float",
        "xmm_intalias",
        "xmm_stralias",
        "xmm_negative",
        "xmm_large",
        "return_bool",
        "return_float",
        "return_intalias",
        "return_zero",
        "return_negative",
        "return_large",
        "flags_bool",
        "flags_float",
        "flags_intalias",
        "flags_zero",
        "flags_four",
        "flags_negative",
        "flags_large",
    ),
)
def test_strict_input_types_before_write(kind, monkeypatch):
    p = inputs()
    if kind.startswith("pages_"):
        sub = kind[6:]
        if sub == "userdict":
            p["pages"] = UserDict(p["pages"])
        elif sub == "empty":
            p["pages"] = {}
        elif sub in ("float", "intalias"):
            key = 0x12340000
            raw = p["pages"].pop(key)
            p["pages"][float(key) if sub == "float" else m.IntAlias(key)] = raw
        elif sub == "mutable":
            p["pages"][0x12340000] = bytearray(4096)
        elif sub == "short":
            p["pages"][0x12340000] = bytes(4095)
        elif sub == "unaligned":
            p["pages"][0x12340001] = bytes(4096)
        elif sub == "large":
            p["pages"][1 << 32] = bytes(4096)
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
            p[key][m.StrAlias(name)] = p[key].pop(name)
        else:
            p[key][name] = {
                "bool": True,
                "float": 0.0,
                "intalias": m.IntAlias(0),
                "negative": -1,
                "large": 1 << (32 if group == "gpr" else 128),
            }[sub]
    else:
        group, sub = kind.split("_", 1)
        key = "return_address" if group == "return" else "entry_flags"
        p[key] = {
            "bool": True,
            "float": 2.0,
            "intalias": m.IntAlias(2),
            "zero": 0,
            "four": 4,
            "negative": -1,
            "large": 1 << 32,
        }[sub]
    reject(p, monkeypatch)


@pytest.mark.parametrize(
    "bit", [i for i in range(32) if i not in (0, 1, 2, 4, 6, 7, 9, 11)]
)
def test_each_forbidden_ordinary_flag_bit(bit, monkeypatch):
    reject(inputs(flags=2 | (1 << bit)), monkeypatch)


@pytest.mark.parametrize("flags", [f & ~2 for f in m.ORDINARY])
def test_required_reserved_flag_bit(flags, monkeypatch):
    reject(inputs(flags=flags), monkeypatch)


def test_inputs_and_each_result_detached():
    p = inputs()
    before = copy.deepcopy(p)
    first = c.apply(**p)
    second = c.apply(**p)
    check(first, before)
    m.equal(p, before)
    first["geometry"]["count"] = 0
    first["registers"]["edx"] = 0
    first["xmm"]["xmm0"] = 0
    first["pages"][0x12340000] = bytes(4096)
    first["events"][0]["value"] = 0
    first["trace_rvas"].clear()
    p["registers"]["eax"] = 0
    p["xmm"]["xmm0"] = 0
    p["pages"][0x12340000] = bytes(4096)
    check(second, before)


def test_exact_api_and_pinned_crt_identity():
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
    m.equal(
        c.BODY_PINS,
        {
            0x3703E0: (
                1330,
                "027f9747b24b79e7aa5a3511ddfd2890a8d50a72072ac6c7df83959091aa9ec5",
            )
        },
    )
    m.equal(
        c.SOURCE_PINS,
        {
            "program_facts": (
                "pe_ghidra_program_facts",
                "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
            )
        },
    )
