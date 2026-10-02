"""Handwritten 7FD0 external inline assignment over a checked TEST witness."""

import copy
import inspect
from collections import UserDict

import pytest

from src.observatory import native_movement_inline_string_assign_semantics as c
from tests import test_itb_native_movement_small_memcpy_semantics as m

NAMES = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
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
    "memcpy_packet",
    "boundaries",
}
COMMON = {"registers", "xmm", "pages", "events", "flags", "flag_mask", "df", "endpoint"}
START = (0x7FD0, 0x7FD1, 0x7FD3, 0x7FD4, 0x7FD7, 0x7FD8, 0x7FDA, 0x7FDC)
NONNULL = (0x7FDE, 0x7FE1, 0x7FE4, 0x7FEA, 0x7FEC, 0x7FEE)
ABOVE = (0x7FF0, 0x7FF3, 0x7FF9, 0x7FFB, 0x7FFE, 0x8000, 0x8002)
SHARED = (0x8035, 0x8036, 0x8039, 0x803C, 0x803E, 0x8041, 0x805C, 0x805E)
CALL = (0x8052, 0x8056, 0x8083, 0x8085, 0x8087, 0x8089, 0x808A, 0x808B, 0x808C)
AFTER = (
    0x8091,
    0x8094,
    0x8098,
    0x809B,
    0x80AC,
    0x80AE,
    0x80B2,
    0x80B3,
    0x80B5,
    0x80B6,
    0x80B7,
    0x80B8,
)
ZERO = (0x8060, 0x8064, 0x8067, 0x8077, 0x8079, 0x807A, 0x807B, 0x807C, 0x807F, 0x8080)


def inputs(
    count=15,
    *,
    frame=0x30001003,
    source=0x10000FF0,
    destination=0x10002FF0,
    previous=7,
    flags=0x246,
    return_address=0x04000000,
    profile=0,
):
    spans = [
        (frame - 40, frame + 12),
        (destination, destination + 24),
        (0x12340000, 0x12341000),
    ]
    if 0 < count <= 15:
        spans.append((source, source + count))
    keys = {
        p
        for lo, hi in spans
        for p in range(lo & ~4095, ((hi - 1) & ~4095) + 4096, 4096)
    }
    pages = {
        p: bytes((i * 71 + (p >> 12) * 19 + profile * 53) & 255 for i in range(4096))
        for p in keys
    }
    regs = {
        name: (0x9ACE1234 + i * 0x13579B + profile * 0x77112233) & 0xFFFFFFFF
        for i, name in enumerate(NAMES)
    }
    regs.update(ecx=destination, esp=frame)
    xmm = {
        "xmm"
        + str(i): (
            0xF123456789ABCDEFFEDCBA98765432100
            + i * 0x33445566778899
            + profile * 0xABCDEF123456789
        )
        & ((1 << 128) - 1)
        for i in range(8)
    }
    for i, value in enumerate((return_address, source, count)):
        m.put_word(pages, frame + 4 * i, value)
    m.put_word(pages, destination + 16, previous)
    m.put_word(pages, destination + 20, 15)
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmm,
        return_address=return_address,
        entry_flags=flags,
    )


def independent(packet):
    incoming = packet["registers"]
    g, d = incoming["esp"], incoming["ecx"]
    o, n = m.word(packet["pages"], g + 4), m.word(packet["pages"], g + 8)
    old = m.word(packet["pages"], d + 16)
    pages = dict(packet["pages"])
    regs = dict(incoming)
    events, trace, boundaries = [], list(START), {}
    child = None
    snapshot = m.read_bytes(pages, o, n) if n else b""

    def write(at, value, width=4):
        m.store(pages, at, value.to_bytes(width, "little"))
        events.append(dict(access="write", address=at, width=width, value=value))

    def read(at, width=4):
        value = int.from_bytes(m.read_bytes(pages, at, width), "little")
        events.append(dict(access="read", address=at, width=width, value=value))
        return value

    write(g - 4, incoming["ebp"])
    write(g - 8, incoming["ebx"])
    read(g + 4)
    write(g - 12, incoming["esi"])
    regs.update(ebp=g - 4, ebx=o, esi=d, esp=g - 12)
    if o:
        read(d + 20)
        regs.update(ecx=15, eax=d)
        trace += list(NONNULL)
        if o >= d:
            read(d + 16)
            regs.update(edx=d, eax=d + old)
            trace += list(ABOVE)
    write(g - 16, incoming["edi"])
    read(g + 8)
    read(d + 20)
    regs.update(edi=n, esp=g - 16)
    trace += list(SHARED)
    if n:
        read(d + 20)
        regs["eax"] = d
        for at, value in ((g - 20, n), (g - 24, o), (g - 28, d), (g - 32, 0x408091)):
            write(at, value)
        regs["esp"] = g - 32
        test_flags = 4 if n.bit_count() % 2 == 0 else 0
        boundaries["memcpy_entry"] = dict(
            registers=dict(regs),
            xmm=dict(packet["xmm"]),
            pages=dict(pages),
            events=copy.deepcopy(events),
            flags=test_flags,
            flag_mask=0x8C5,
            df=0,
            endpoint=0x7703E0,
        )
        child_input = dict(
            pages=dict(pages),
            registers=dict(regs),
            xmm=dict(packet["xmm"]),
            return_address=0x408091,
            entry_flags=(packet["entry_flags"] & 0x202) | test_flags,
        )
        child = m.independent(child_input)
        pages = dict(child["pages"])
        regs = dict(child["registers"])
        events += copy.deepcopy(child["events"])
        boundaries["memcpy_return"] = dict(
            registers=dict(regs),
            xmm=dict(packet["xmm"]),
            pages=dict(pages),
            events=copy.deepcopy(events),
            flags=0x44,
            flag_mask=0x8D5 if n % 4 else 0x8C5,
            df=0,
            endpoint=0x408091,
        )
        trace += list(CALL)
        trace += [int(point, 16) for point in child["trace_rvas"]]
        trace += list(AFTER)
        read(d + 20)
        write(d + 16, n)
        write(d + n, 0, 1)
        for at in (g - 16, g - 12, g - 8, g - 4, g):
            read(at)
    else:
        read(d + 20)
        write(d + 16, 0)
        for at in (g - 16, g - 12, g - 8):
            read(at)
        write(d, 0, 1)
        read(g - 4)
        read(g)
        trace += list(ZERO)
    final = dict(incoming, eax=d, ecx=regs["ecx"], edx=regs["edx"], esp=g + 12)
    # Separate full final byte equation, independent of parent event replay.
    direct = dict(packet["pages"])
    for at, value in (
        (g - 4, incoming["ebp"]),
        (g - 8, incoming["ebx"]),
        (g - 12, incoming["esi"]),
        (g - 16, incoming["edi"]),
    ):
        m.put_word(direct, at, value)
    if n:
        for at, value in (
            (g - 20, n),
            (g - 24, o),
            (g - 28, d),
            (g - 32, 0x408091),
            (g - 36, n),
            (g - 40, d),
        ):
            m.put_word(direct, at, value)
        m.store(direct, d, snapshot)
    m.put_word(direct, d + 16, n)
    m.store(direct, d + n, b"\0")
    m.equal(pages, direct)
    return dict(
        geometry=dict(entry=g, source=o, destination=d, count=n, previous_length=old),
        registers=final,
        xmm=dict(packet["xmm"]),
        pages=direct,
        events=events,
        trace_rvas=[f"0x{rva:08x}" for rva in trace],
        flags=0x85,
        flag_mask=0x8D5,
        df=0,
        endpoint=packet["return_address"],
        source_snapshot=snapshot,
        memcpy_packet=copy.deepcopy(child),
        boundaries=boundaries,
    )


def check(actual, packet):
    assert type(actual) is dict and set(actual) == OUTPUT
    m.equal(actual, independent(packet))
    g, d = packet["registers"]["esp"], packet["registers"]["ecx"]
    o, n = m.word(packet["pages"], g + 4), m.word(packet["pages"], g + 8)
    prefix_instructions = 0 if o == 0 else 6 if o < d else 13
    prefix_events = 0 if o == 0 else 1 if o < d else 2
    if n:
        q, r = divmod(n, 4)
        assert len(actual["events"]) == 29 + prefix_events + 2 * q + 2 * r
        assert len(
            actual["trace_rvas"]
        ) == 37 + prefix_instructions + 24 + 6 * q + 6 * r + 2 * bool(r) + 2 * (d > o)
        assert set(actual["boundaries"]) == {"memcpy_entry", "memcpy_return"}
        for state in actual["boundaries"].values():
            assert type(state) is dict and set(state) == COMMON
    else:
        assert len(actual["events"]) == 15 + prefix_events
        assert len(actual["trace_rvas"]) == 26 + prefix_instructions
        assert actual["memcpy_packet"] is None and actual["boundaries"] == {}
    replay = dict(packet["pages"])
    for event in actual["events"]:
        at, w, v = event["address"], event["width"], event["value"]
        if event["access"] == "read":
            assert int.from_bytes(m.read_bytes(replay, at, w), "little") == v
        else:
            m.store(replay, at, v.to_bytes(w, "little"))
    m.equal(replay, actual["pages"])
    m.equal(m.read_bytes(actual["pages"], g, 12), m.read_bytes(packet["pages"], g, 12))


@pytest.mark.parametrize("count", range(16))
@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize("above", (False, True))
@pytest.mark.parametrize("previous", (0, 7, 15))
def test_all_lengths_alignments_orders_and_old_lengths(
    count, alignment, above, previous
):
    o, d = 0x10000FF0 + alignment, 0x10002FF0 + alignment
    if above:
        o, d = d, o
    packet = inputs(
        count,
        frame=0x30000FF0 + alignment,
        source=o,
        destination=d,
        previous=previous,
        profile=alignment % 3,
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("flags", m.ORDINARY)
@pytest.mark.parametrize("count", (0, 1, 4, 15))
def test_all_ordinary_flags(flags, count):
    packet = inputs(count, flags=flags)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "pointer,previous",
    (
        (0, 15),
        (0xFFFFFFFF, 15),
        (0xDEAD1234, 7),
        (0x10002FF0, 0),
        (0x10002FF5, 5),
        (0x10002FF0 - 1, 15),
        (0x7703E0, 15),
        (0x30001003, 15),
        (0x04000000, 15),
    ),
)
def test_zero_unmapped_null_and_external_interior_prefixes(
    pointer, previous, monkeypatch
):
    packet = inputs(0, source=pointer, previous=previous)
    ledger = []

    def forbidden(**kwargs):
        ledger.append("child")
        raise AssertionError("zero may not call memcpy")

    monkeypatch.setattr(c.memcpy, "apply", forbidden)
    actual = c.apply(**packet)
    assert ledger == []
    check(actual, packet)


@pytest.mark.parametrize(
    "source,destination,frame",
    (
        (0x10000FF0, 0x10002FF0, 40),
        (1, 0x10002FF0, 0x30001003),
        (0x7FFFFFF8, 0x80001000, 0x30001003),
        (0x80001000, 0x7FFFFFF8, 0x30001003),
        (0xFFFFFFFF - 15, 0x10002FF0, 0x30001003),
        (0x10000FF0, 0xFFFFFFFF - 24, 0x30001003),
        (0x10000FF0, 0x10002FF0, 0xFFFFFFFF - 12),
        (0x10000FF0, 0x10000FF0 + 15, 0x30001003),
        (0x10003000, 0x10003000 - 24, 0x30001003),
        (0x30001003 + 12, 0x10002FF0, 0x30001003),
        (0x30001003 - 55, 0x10002FF0, 0x30001003),
        (0x10000FF0, 0x30001003 + 12, 0x30001003),
        (0x10000FF0, 0x30001003 - 64, 0x30001003),
    ),
)
def test_cross_page_uint32_adjacency_and_stack_geometry(source, destination, frame):
    packet = inputs(source=source, destination=destination, frame=frame)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "endpoint", (1, 0xFFFFFFFF, 0x407FCF, 0x4080C5, 0x7703DF, 0x770954, 0x05000000)
)
def test_logical_return_endpoints(endpoint):
    packet = inputs(return_address=endpoint)
    check(c.apply(**packet), packet)


def test_arbitrary_all_registers_xmm_payload_padding_and_source_preservation():
    packet = inputs()
    for i, name in enumerate(NAMES):
        if name not in ("ecx", "esp"):
            packet["registers"][name] = 0 if i % 2 else 0xFFFFFFFF
    packet["xmm"] = {"xmm" + str(i): 0 if i % 2 else (1 << 128) - 1 for i in range(8)}
    o = m.word(packet["pages"], packet["registers"]["esp"] + 4)
    m.store(packet["pages"], o, bytes(range(15)))
    packet["pages"][0x12340000] = bytes(range(256)) * 16
    before = copy.deepcopy(packet)
    actual = c.apply(**packet)
    check(actual, packet)
    m.equal(packet, before)
    m.equal(m.read_bytes(actual["pages"], o, 15), bytes(range(15)))


def reject(packet, monkeypatch):
    writes, children = [], []
    original_write = c._write

    def observed(*args, **kwargs):
        writes.append("write")
        return original_write(*args, **kwargs)

    def forbidden(**kwargs):
        children.append("child")
        raise AssertionError("invalid parent called child")

    before = copy.deepcopy(packet)
    with monkeypatch.context() as patch:
        patch.setattr(c, "_write", observed)
        patch.setattr(c.memcpy, "apply", forbidden)
        with pytest.raises(c.InlineStringAssignError):
            c.apply(**packet)
        assert writes == [] and children == []
    m.equal(packet, before)


@pytest.mark.parametrize(
    "kind",
    (
        "count16",
        "countmax",
        "bad_return_word",
        "old16",
        "capacity16",
        "capacity0",
        "frame_underflow",
        "frame_wrap",
        "destination_zero",
        "destination_wrap",
        "source_zero",
        "source_wrap",
        "source_unmapped",
        "destination_unmapped",
        "frame_unmapped",
        "overlap_equal",
        "overlap_forward",
        "overlap_backward",
        "source_stack",
        "destination_stack",
        "return_source",
        "return_destination",
        "return_stack",
        "return_owner",
        "return_crt",
        "owner_page",
        "crt_page",
        "zero_alias_before_end",
    ),
)
def test_geometry_premises_before_writes_and_child(kind, monkeypatch):
    p = inputs()
    g, d = p["registers"]["esp"], p["registers"]["ecx"]
    if kind in ("count16", "countmax"):
        m.put_word(p["pages"], g + 8, 16 if kind == "count16" else 0xFFFFFFFF)
    elif kind == "bad_return_word":
        m.put_word(p["pages"], g, 0x04000004)
    elif kind == "old16":
        m.put_word(p["pages"], d + 16, 16)
    elif kind.startswith("capacity"):
        m.put_word(p["pages"], d + 20, 16 if kind == "capacity16" else 0)
    elif kind.startswith("frame_") and kind != "frame_unmapped":
        p["registers"]["esp"] = 39 if kind == "frame_underflow" else 0xFFFFFFF4
    elif kind == "destination_zero":
        p["registers"]["ecx"] = 0
    elif kind == "destination_wrap":
        p["registers"]["ecx"] = 0xFFFFFFF0
    elif kind in ("source_zero", "source_wrap", "source_unmapped"):
        m.put_word(
            p["pages"],
            g + 4,
            {
                "source_zero": 0,
                "source_wrap": 0xFFFFFFF8,
                "source_unmapped": 0x20000000,
            }[kind],
        )
    elif kind == "destination_unmapped":
        p["pages"].pop(d & ~4095)
    elif kind == "frame_unmapped":
        p["pages"].pop(g & ~4095)
    elif kind.startswith("overlap"):
        m.put_word(
            p["pages"],
            g + 4,
            d
            + {"overlap_equal": 0, "overlap_forward": 1, "overlap_backward": -1}[kind],
        )
    elif kind == "source_stack":
        m.put_word(p["pages"], g + 4, g - 40)
    elif kind == "destination_stack":
        p["registers"]["ecx"] = g - 40
        m.put_word(p["pages"], g - 40 + 16, 7)
        m.put_word(p["pages"], g - 40 + 20, 15)
    elif kind.startswith("return_"):
        at = {
            "return_source": m.word(p["pages"], g + 4),
            "return_destination": d,
            "return_stack": g,
            "return_owner": 0x408000,
            "return_crt": 0x770500,
        }[kind]
        p["return_address"] = at
        m.put_word(p["pages"], g, at)
    elif kind in ("owner_page", "crt_page"):
        p["pages"][0x407000 if kind == "owner_page" else 0x770000] = bytes(4096)
    elif kind == "zero_alias_before_end":
        m.put_word(p["pages"], g + 8, 0)
        m.put_word(p["pages"], g + 4, d + 6)
    reject(p, monkeypatch)


@pytest.mark.parametrize("kind", ("pages", "registers", "xmm"))
def test_container_aliases_rejected_before_writes(kind, monkeypatch):
    p = inputs()
    p[kind] = UserDict(p[kind])
    reject(p, monkeypatch)


@pytest.mark.parametrize(
    "kind",
    (
        "pages_float_key",
        "pages_mutable",
        "pages_short",
        "pages_unaligned",
        "gpr_bool",
        "gpr_stralias",
        "gpr_missing",
        "gpr_large",
        "xmm_bool",
        "xmm_stralias",
        "xmm_extra",
        "xmm_large",
        "return_bool",
        "return_zero",
        "return_float",
        "flags_bool",
        "flags_zero",
        "flags_four",
        "flags_float",
    ),
)
def test_exact_key_value_types(kind, monkeypatch):
    p = inputs()
    if kind == "pages_float_key":
        p["pages"][float(0x12340000)] = p["pages"].pop(0x12340000)
    elif kind == "pages_mutable":
        p["pages"][0x12340000] = bytearray(4096)
    elif kind == "pages_short":
        p["pages"][0x12340000] = bytes(4095)
    elif kind == "pages_unaligned":
        p["pages"][0x12340001] = bytes(4096)
    elif kind.startswith(("gpr_", "xmm_")):
        group, sub = kind.split("_", 1)
        key = "registers" if group == "gpr" else "xmm"
        name = "eax" if group == "gpr" else "xmm0"
        if sub == "bool":
            p[key][name] = True
        elif sub == "stralias":
            p[key][m.StrAlias(name)] = p[key].pop(name)
        elif sub == "missing":
            p[key].pop(name)
        elif sub == "extra":
            p[key]["extra"] = 0
        elif sub == "large":
            p[key][name] = 1 << (32 if group == "gpr" else 128)
    else:
        group, sub = kind.split("_", 1)
        p["return_address" if group == "return" else "entry_flags"] = {
            "bool": True,
            "zero": 0,
            "four": 4,
            "float": 2.0,
        }[sub]
    reject(p, monkeypatch)


@pytest.mark.parametrize(
    "bit", [i for i in range(32) if i not in (0, 1, 2, 4, 6, 7, 9, 11)]
)
def test_each_forbidden_flags_bit(bit, monkeypatch):
    reject(inputs(flags=2 | (1 << bit)), monkeypatch)


@pytest.mark.parametrize("flags", [v & ~2 for v in m.ORDINARY])
def test_reserved_bit_required(flags, monkeypatch):
    reject(inputs(flags=flags), monkeypatch)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "geometry_bool",
        "gpr_bool",
        "xmm_bool",
        "df_bool",
        "endpoint_float",
        "flags_bool",
        "mask_bool",
        "snapshot",
        "tuple_events",
        "tuple_trace",
        "float_page",
        "mutable_page",
        "restored_write",
        "missing_event",
        "coordinated_value",
        "bad_trace",
        "trace_label",
        "trace_empty",
        "caller_ancestor",
        "destination_padding",
        "source_padding",
    ),
)
def test_complete_child11_forgeries_rejected(kind, monkeypatch):
    parent = inputs()
    before = copy.deepcopy(parent)
    calls = []

    def forged(**packet):
        calls.append("child")
        out = m.independent(packet)
        g = packet["registers"]["esp"]
        d = m.word(packet["pages"], g + 4)
        o = m.word(packet["pages"], g + 8)
        if kind == "extra":
            out["extra"] = 0
        elif kind == "missing":
            out.pop("geometry")
        elif kind == "geometry_bool":
            out["geometry"]["count"] = True
        elif kind == "gpr_bool":
            out["registers"]["ecx"] = False
        elif kind == "xmm_bool":
            out["xmm"]["xmm0"] = False
        elif kind == "df_bool":
            out["df"] = False
        elif kind == "endpoint_float":
            out["endpoint"] = float(out["endpoint"])
        elif kind == "flags_bool":
            out["flags"] = True
        elif kind == "mask_bool":
            out["flag_mask"] = True
        elif kind == "snapshot":
            out["source_snapshot"] = b"x" * 15
        elif kind == "tuple_events":
            out["events"] = tuple(out["events"])
        elif kind == "tuple_trace":
            out["trace_rvas"] = tuple(out["trace_rvas"])
        elif kind == "float_page":
            key = next(iter(out["pages"]))
            out["pages"][float(key)] = out["pages"].pop(key)
        elif kind == "mutable_page":
            out["pages"][0x12340000] = bytearray(out["pages"][0x12340000])
        elif kind == "restored_write":
            out["events"].extend(
                (
                    dict(access="write", address=d + 15, width=1, value=99),
                    dict(
                        access="write",
                        address=d + 15,
                        width=1,
                        value=m.read_bytes(out["pages"], d + 15, 1)[0],
                    ),
                )
            )
        elif kind == "missing_event":
            out["events"].pop(0)
        elif kind == "coordinated_value":
            out["events"][5]["value"] ^= 1
            out["events"][6]["value"] ^= 1
            value = out["events"][6]["value"]
            m.store(out["pages"], d, value.to_bytes(4, "little"))
            out["source_snapshot"] = (
                value.to_bytes(4, "little") + out["source_snapshot"][4:]
            )
        elif kind == "bad_trace":
            out["trace_rvas"][0] = "not-a-rva"
        elif kind == "trace_label":
            out["trace_rvas"][0] = "0x003703e1"
        elif kind == "trace_empty":
            out["trace_rvas"] = []
        else:
            at = {
                "caller_ancestor": g + 16,
                "destination_padding": d + 15,
                "source_padding": o + 14,
            }[kind]
            m.store(out["pages"], at, bytes([m.read_bytes(out["pages"], at, 1)[0] ^ 1]))
        return out

    monkeypatch.setattr(c.memcpy, "apply", forged)
    with pytest.raises(
        c.InlineStringAssignError, match="complete memcpy packet differs"
    ):
        c.apply(**parent)
    assert calls == ["child"]
    m.equal(parent, before)


def test_correct_independent_child_admitted_and_actual_interface(monkeypatch):
    parent = inputs()
    calls = []

    def supplied(**packet):
        calls.append(copy.deepcopy(packet))
        return m.independent(packet)

    monkeypatch.setattr(c.memcpy, "apply", supplied)
    actual = c.apply(**parent)
    check(actual, parent)
    assert len(calls) == 1
    assert calls[0]["registers"]["esp"] == parent["registers"]["esp"] - 32
    assert calls[0]["return_address"] == 0x408091
    assert calls[0]["entry_flags"] == 0x206


def test_input_results_and_boundary_detachment():
    parent = inputs()
    before = copy.deepcopy(parent)
    first = c.apply(**parent)
    second = c.apply(**parent)
    check(first, before)
    m.equal(parent, before)
    first["boundaries"]["memcpy_entry"]["registers"]["eax"] = 0
    first["boundaries"]["memcpy_return"]["events"][0]["value"] = 0
    first["memcpy_packet"]["pages"][0x12340000] = bytes(4096)
    check(second, before)
    assert first["registers"] == second["registers"]
    assert first["events"] == second["events"]
    assert first["pages"] == second["pages"]
    parent["registers"]["eax"] = 0
    parent["pages"][0x12340000] = bytes(4096)
    check(second, before)


def test_api_and_source_body_identity():
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
            0x7FD0: (
                245,
                "c49f0e24bd27ed5495ceddc13536ca6fbe85d8c97f207db817ce0642b8b01906",
            ),
            0x3703E0: (
                1330,
                "027f9747b24b79e7aa5a3511ddfd2890a8d50a72072ac6c7df83959091aa9ec5",
            ),
        },
    )
