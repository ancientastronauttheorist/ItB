"""Handwritten three-arm 8410 inline erase and independent memmove TEST joins."""

import copy
import inspect
from collections import UserDict

import pytest

from src.observatory import native_movement_inline_string_erase_semantics as c
from tests import test_itb_native_movement_memmove_forward_semantics as m

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
    "memmove_packet",
    "boundaries",
}
COMMON = {
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
PREFIX = (
    0x8410,
    0x8411,
    0x8413,
    0x8414,
    0x8416,
    0x8419,
    0x841A,
    0x841D,
    0x841F,
    0x8421,
    0x8424,
    0x8426,
    0x8428,
    0x842A,
)
TRUNCATE = (0x842C, 0x842F, 0x8433, 0x8443, 0x8445, 0x8446, 0x8447, 0x844B, 0x844C)
NOOP = (0x844F, 0x8451, 0x8497, 0x8498, 0x849A, 0x849B, 0x849C)
CALL = (
    0x844F,
    0x8451,
    0x8453,
    0x8457,
    0x845D,
    0x845F,
    0x8461,
    0x8462,
    0x8465,
    0x8467,
    0x8469,
    0x846B,
    0x846C,
    0x846F,
    0x8470,
    0x8471,
)
AFTER = (
    0x8476,
    0x8479,
    0x847D,
    0x8480,
    0x8481,
    0x8491,
    0x8493,
    0x8497,
    0x8498,
    0x849A,
    0x849B,
    0x849C,
)
RECIPES = [
    (length, offset, requested)
    for length in range(16)
    for offset in range(length + 1)
    for requested in (0, 1, 3, length - offset, 0xFFFFFFFF)
]


def inputs(
    length=15,
    offset=3,
    requested=4,
    *,
    frame=0x30001003,
    object_address=0x10000FF0,
    flags=0x246,
    return_address=0x04000000,
    profile=0,
):
    spans = (
        (frame - 40, frame + 12),
        (object_address, object_address + 24),
        (0x12340000, 0x12341000),
    )
    pages = {
        p: bytes((i * 43 + (p >> 12) * 17 + profile * 71) & 255 for i in range(4096))
        for lo, hi in spans
        for p in range(lo & ~4095, ((hi - 1) & ~4095) + 4096, 4096)
    }
    regs = {
        name: (0x91EF1234 + i * 0x13579B + profile * 0x77991234) & 0xFFFFFFFF
        for i, name in enumerate(m.GPRS)
    }
    regs.update(esp=frame, ecx=object_address)
    xmm = {
        name: (
            0xFEDCBA98765432100123456789ABCDEF
            + i * 0x1122334455667789
            + profile * 0x334455667788
        )
        & ((1 << 128) - 1)
        for i, name in enumerate(m.XMMS)
    }
    for off, value in ((0, return_address), (4, offset), (8, requested)):
        m.put_word(pages, frame + off, value)
    for i in range(16):
        m.store(pages, object_address + i, bytes([(i * 17 + profile * 53) & 255]))
    m.put_word(pages, object_address + 16, length)
    m.put_word(pages, object_address + 20, 15)
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmm,
        return_address=return_address,
        entry_flags=flags,
    )


def sub_flags(a, b):
    result = (a - b) & 0xFFFFFFFF
    return (
        int(a < b)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | (int(bool((a ^ b ^ result) & 16)) << 4)
        | (int(result == 0) << 6)
        | ((result >> 31) << 7)
        | (int(bool((a ^ b) & (a ^ result) & 0x80000000)) << 11)
    )


def independent(packet):
    incoming = packet["registers"]
    g, h = incoming["esp"], incoming["ecx"]
    length = m.word(packet["pages"], h + 16)
    off = m.word(packet["pages"], g + 4)
    req = m.word(packet["pages"], g + 8)
    available = length - off
    removed = min(req, available)
    count = available - removed
    pages = dict(packet["pages"])
    events = []
    states = []
    trace = list(PREFIX)
    child = None
    regs = dict(
        incoming,
        eax=available,
        ecx=off,
        edx=req,
        ebp=g - 4,
        esi=h,
        edi=length,
        esp=g - 12,
    )

    def write(at, value, width=4):
        m.store(pages, at, value.to_bytes(width, "little"))
        events.append(dict(access="write", address=at, width=width, value=value))

    def read(at, width=4):
        value = int.from_bytes(m.read_bytes(pages, at, width), "little")
        events.append(dict(access="read", address=at, width=width, value=value))
        return value

    write(g - 4, incoming["ebp"])
    write(g - 8, incoming["esi"])
    read(g + 4)
    write(g - 12, incoming["edi"])
    read(h + 16)
    read(g + 8)
    if available <= req:
        trace += list(TRUNCATE)
        write(h + 16, off)
        read(h + 20)
        read(g - 12)
        read(g - 8)
        write(h + off, 0, 1)
        read(g - 4)
        read(g)
        final_flags, mask = 0x85, 0x8D5
    elif req == 0:
        trace += list(NOOP)
        for at in (g - 12, g - 8, g - 4, g):
            read(at)
        final_flags, mask = 0x44, 0x8C5
    else:
        newlength = length - req
        destination = h + off
        source = destination + req
        read(h + 20)
        write(g - 16, incoming["ebx"])
        for at, value in (
            (g - 20, count),
            (g - 24, source),
            (g - 28, destination),
            (g - 32, 0x408476),
        ):
            write(at, value)
        regs.update(eax=source, ebx=destination, edi=newlength, esp=g - 32)
        entry_status = sub_flags(newlength, off)
        states.append(
            dict(
                registers=dict(regs),
                xmm=dict(packet["xmm"]),
                pages=dict(pages),
                events=copy.deepcopy(events),
                flags=entry_status,
                flag_mask=0x8D5,
                df=0,
                endpoint=0x76E580,
                phase="entry",
            )
        )
        child_input = dict(
            pages=dict(pages),
            registers=dict(regs),
            xmm=dict(packet["xmm"]),
            return_address=0x408476,
            entry_flags=(packet["entry_flags"] & 0x202) | entry_status,
        )
        child = m.independent(child_input)
        pages = dict(child["pages"])
        events += copy.deepcopy(child["events"])
        regs = dict(child["registers"])
        states.append(
            dict(
                registers=dict(regs),
                xmm=dict(packet["xmm"]),
                pages=dict(pages),
                events=copy.deepcopy(events),
                flags=child["flags"],
                flag_mask=child["flag_mask"],
                df=0,
                endpoint=0x408476,
                phase="return",
            )
        )
        read(h + 20)
        write(h + 16, newlength)
        read(g - 16)
        write(h + newlength, 0, 1)
        for at in (g - 12, g - 8, g - 4, g):
            read(at)
        trace += list(CALL)
        trace += [int(pc, 16) for pc in child["trace_rvas"]]
        trace += list(AFTER)
        final_flags, mask = 0x85, 0x8D5
    # Direct object and saved-word equation from the original snapshot, separate
    # from the expected ordered access replay above.
    direct = dict(packet["pages"])
    for at, value in (
        (g - 4, incoming["ebp"]),
        (g - 8, incoming["esi"]),
        (g - 12, incoming["edi"]),
    ):
        m.put_word(direct, at, value)
    if available <= req:
        m.put_word(direct, h + 16, off)
        m.store(direct, h + off, b"\0")
    elif req:
        newlength = length - req
        destination = h + off
        source = destination + req
        for at, value in (
            (g - 16, incoming["ebx"]),
            (g - 20, count),
            (g - 24, source),
            (g - 28, destination),
            (g - 32, 0x408476),
            (g - 36, newlength),
            (g - 40, h),
        ):
            m.put_word(direct, at, value)
        m.store(direct, destination, m.read_bytes(packet["pages"], source, count))
        m.put_word(direct, h + 16, newlength)
        m.store(direct, h + newlength, b"\0")
    m.equal(pages, direct)
    return dict(
        geometry=dict(
            entry=g,
            object=h,
            old_length=length,
            offset=off,
            requested=req,
            removed=removed,
            count=count,
        ),
        registers=dict(
            incoming, eax=h, ecx=0 if child else off, edx=regs["edx"], esp=g + 12
        ),
        xmm=dict(packet["xmm"]),
        pages=direct,
        events=events,
        trace_rvas=[f"0x{pc:08x}" for pc in trace],
        flags=final_flags,
        flag_mask=mask,
        df=0,
        endpoint=packet["return_address"],
        source_snapshot=m.read_bytes(packet["pages"], h, 24),
        string_bytes=m.read_bytes(direct, h, 24),
        memmove_packet=copy.deepcopy(child),
        boundaries=states,
    )


def check(actual, packet):
    m.equal(actual, independent(packet))
    assert type(actual) is dict and set(actual) == KEYS
    g, h = packet["registers"]["esp"], packet["registers"]["ecx"]
    length = m.word(packet["pages"], h + 16)
    off = m.word(packet["pages"], g + 4)
    req = m.word(packet["pages"], g + 8)
    available = length - off
    if available <= req:
        assert len(actual["events"]) == 13 and len(actual["trace_rvas"]) == 23
        assert actual["registers"]["ecx"] == off and actual["registers"]["edx"] == req
    elif req == 0:
        assert len(actual["events"]) == 10 and len(actual["trace_rvas"]) == 21
        assert actual["string_bytes"] == actual["source_snapshot"]
        assert actual["registers"]["ecx"] == off and actual["registers"]["edx"] == 0
    else:
        q, r = divmod(available - req, 4)
        assert len(actual["events"]) == 29 + 2 * q + 2 * r
        assert len(actual["trace_rvas"]) == 66 + 6 * q + 6 * r + 2 * bool(r)
        assert len(actual["boundaries"]) == 2
        assert all(
            type(row) is dict and set(row) == COMMON for row in actual["boundaries"]
        )
        assert actual["boundaries"][0]["flags"] == sub_flags(length - req, off)
        assert [len(row["events"]) for row in actual["boundaries"]] == [
            12,
            21 + 2 * q + 2 * r,
        ]
        assert (
            actual["memmove_packet"]["geometry"]["destination"]
            < actual["memmove_packet"]["geometry"]["source"]
        )
    if not 0 < req < available:
        assert actual["memmove_packet"] is None and actual["boundaries"] == []
    replay = dict(packet["pages"])
    for ev in actual["events"]:
        at, w, value = ev["address"], ev["width"], ev["value"]
        if ev["access"] == "read":
            assert int.from_bytes(m.read_bytes(replay, at, w), "little") == value
        else:
            m.store(replay, at, value.to_bytes(w, "little"))
    m.equal(replay, actual["pages"])
    assert m.read_bytes(actual["pages"], g, 12) == m.read_bytes(packet["pages"], g, 12)
    assert m.word(actual["pages"], h + 20) == 15


@pytest.mark.parametrize("length,offset,requested", RECIPES)
@pytest.mark.parametrize("alignment", (0, 15))
def test_all_lengths_offsets_and_unsigned_request_branches(
    length, offset, requested, alignment
):
    packet = inputs(
        length,
        offset,
        requested,
        frame=0x30001000 + alignment,
        object_address=0x10000FF0 + alignment,
    )
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    m.equal(packet, before)


@pytest.mark.parametrize("flags", m.ORDINARY)
@pytest.mark.parametrize(
    "length,offset,requested",
    ((0, 0, 0), (15, 15, 0), (15, 7, 0), (15, 7, 3), (15, 0, 7)),
)
def test_all_ordinary_flags_in_each_branch(flags, length, offset, requested):
    packet = inputs(length, offset, requested, flags=flags)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize(
    "recipe", ((15, 0, 1), (15, 4, 3), (9, 0, 1), (15, 7, 0), (15, 7, 0xFFFFFFFF))
)
def test_independent_alignments_word_and_byte_tail_children(alignment, recipe):
    packet = inputs(
        *recipe, frame=0x30000FF8 + alignment, object_address=0x10000FF0 + alignment
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "g,h",
    (
        (40, 0x10000FF0),
        (0x30001003, 1),
        (0xFFFFFFF3, 0x10000FF0),
        (0x30001003, 0xFFFFFFFF - 24),
        (0x30001003, 0x7FFFFFF8),
        (0x30001003, 0x30001003 + 12),
        (0x30001003, 0x30001003 - 64),
    ),
)
@pytest.mark.parametrize("recipe", ((15, 3, 4), (15, 7, 0), (15, 7, 0xFFFFFFFF)))
def test_cross_page_minimum_signed_uint32_and_adjacent_frame_geometry(g, h, recipe):
    packet = inputs(*recipe, frame=g, object_address=h, return_address=0xFFFFFFFF)
    check(c.apply(**packet), packet)


def test_raw_inline_data_unread_terminator_and_preserved_padding():
    packet = inputs(15, 3, 4)
    h = packet["registers"]["ecx"]
    m.store(packet["pages"], h, bytes(range(16)))
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["string_bytes"][:16] == bytes(
        (0, 1, 2, 7, 8, 9, 10, 11, 12, 13, 14, 0, 12, 13, 14, 15)
    )
    assert actual["source_snapshot"][:16] == bytes(range(16))
    assert actual["source_snapshot"] != actual["string_bytes"]


def reject(packet, monkeypatch):
    before = copy.deepcopy(packet)
    writes, children = [], []
    original = c._write

    def observed(*args, **kwargs):
        writes.append("write")
        return original(*args, **kwargs)

    def forbidden(**kwargs):
        children.append("child")
        raise AssertionError("invalid parent called child")

    with monkeypatch.context() as patch:
        patch.setattr(c, "_write", observed)
        patch.setattr(c.memmove, "apply", forbidden)
        with pytest.raises(c.InlineStringEraseError):
            c.apply(**packet)
        assert writes == [] and children == []
    m.equal(packet, before)


@pytest.mark.parametrize(
    "kind",
    (
        "offset16",
        "length16",
        "capacity16",
        "capacity0",
        "frame_underflow",
        "frame_wrap",
        "object_zero",
        "object_wrap",
        "object_unmapped",
        "frame_unmapped",
        "overlap",
        "caller_return",
        "return_frame",
        "return_object",
        "return_owner",
        "return_memmove",
        "owner_page",
        "memmove_page",
        "pages_userdict",
        "pages_float",
        "pages_mutable",
        "pages_short",
        "gpr_bool",
        "gpr_userdict",
        "gpr_missing",
        "xmm_bool",
        "xmm_large",
        "xmm_userdict",
        "return_bool",
        "return_float",
        "return_zero",
        "flags_bool",
        "flags_zero",
        "flags_four",
    ),
)
def test_typed_geometry_premises_before_write_and_child(kind, monkeypatch):
    packet = inputs()
    g, h = packet["registers"]["esp"], packet["registers"]["ecx"]
    if kind == "offset16":
        m.put_word(packet["pages"], g + 4, 16)
    elif kind == "length16":
        m.put_word(packet["pages"], h + 16, 16)
    elif kind in ("capacity16", "capacity0"):
        m.put_word(packet["pages"], h + 20, 16 if kind == "capacity16" else 0)
    elif kind == "frame_underflow":
        packet["registers"]["esp"] = 39
    elif kind == "frame_wrap":
        packet["registers"]["esp"] = 0xFFFFFFF4
    elif kind == "object_zero":
        packet["registers"]["ecx"] = 0
    elif kind == "object_wrap":
        packet["registers"]["ecx"] = 0xFFFFFFF0
    elif kind == "object_unmapped":
        packet["registers"]["ecx"] = 0x20000000
    elif kind == "frame_unmapped":
        packet["pages"].pop(g & ~4095)
    elif kind == "overlap":
        packet["registers"]["ecx"] = g - 40
        m.put_word(packet["pages"], g - 24, 15)
        m.put_word(packet["pages"], g - 20, 15)
    elif kind == "caller_return":
        m.put_word(packet["pages"], g, 0x04000004)
    elif kind.startswith("return_") and kind not in (
        "return_bool",
        "return_float",
        "return_zero",
    ):
        at = {
            "return_frame": g,
            "return_object": h,
            "return_owner": 0x408410,
            "return_memmove": 0x76E700,
        }[kind]
        packet["return_address"] = at
        m.put_word(packet["pages"], g, at)
    elif kind in ("owner_page", "memmove_page"):
        packet["pages"][0x408000 if kind == "owner_page" else 0x76E000] = bytes(4096)
    elif kind == "pages_userdict":
        packet["pages"] = UserDict(packet["pages"])
    elif kind == "pages_float":
        packet["pages"][float(0x12340000)] = packet["pages"].pop(0x12340000)
    elif kind == "pages_mutable":
        packet["pages"][0x12340000] = bytearray(4096)
    elif kind == "pages_short":
        packet["pages"][0x12340000] = bytes(4095)
    elif kind == "gpr_bool":
        packet["registers"]["eax"] = True
    elif kind == "gpr_userdict":
        packet["registers"] = UserDict(packet["registers"])
    elif kind == "gpr_missing":
        packet["registers"].pop("eax")
    elif kind == "xmm_bool":
        packet["xmm"]["xmm0"] = False
    elif kind == "xmm_large":
        packet["xmm"]["xmm0"] = 1 << 128
    elif kind == "xmm_userdict":
        packet["xmm"] = UserDict(packet["xmm"])
    elif kind in ("return_bool", "return_float", "return_zero"):
        packet["return_address"] = {
            "return_bool": True,
            "return_float": float(packet["return_address"]),
            "return_zero": 0,
        }[kind]
    elif kind in ("flags_bool", "flags_zero", "flags_four"):
        packet["entry_flags"] = {"flags_bool": True, "flags_zero": 0, "flags_four": 4}[
            kind
        ]
    reject(packet, monkeypatch)


@pytest.mark.parametrize(
    "bit", [i for i in range(32) if i not in (0, 1, 2, 4, 6, 7, 9, 11)]
)
def test_each_forbidden_ordinary_flag_bit(bit, monkeypatch):
    reject(inputs(flags=2 | (1 << bit)), monkeypatch)


@pytest.mark.parametrize("flags", [f & ~2 for f in m.ORDINARY])
def test_required_reserved_flag_bit(flags, monkeypatch):
    reject(inputs(flags=flags), monkeypatch)


@pytest.mark.parametrize(
    "kind",
    (
        "page_intalias",
        "page_unaligned",
        "gpr_stralias",
        "gpr_intalias",
        "xmm_stralias",
        "xmm_intalias",
        "return_intalias",
        "flags_intalias",
    ),
)
def test_subclass_aliases_and_page_alignment_before_mutation(kind, monkeypatch):
    packet = inputs()
    if kind == "page_intalias":
        value = packet["pages"].pop(0x12340000)
        packet["pages"][m.IntAlias(0x12340000)] = value
    elif kind == "page_unaligned":
        packet["pages"][0x12340001] = bytes(4096)
    elif kind in ("gpr_stralias", "xmm_stralias"):
        key = "registers" if kind.startswith("gpr") else "xmm"
        name = "eax" if key == "registers" else "xmm0"
        value = packet[key].pop(name)
        packet[key][m.StrAlias(name)] = value
    elif kind in ("gpr_intalias", "xmm_intalias"):
        key = "registers" if kind.startswith("gpr") else "xmm"
        name = "eax" if key == "registers" else "xmm0"
        packet[key][name] = m.IntAlias(packet[key][name])
    elif kind == "return_intalias":
        packet["return_address"] = m.IntAlias(packet["return_address"])
    elif kind == "flags_intalias":
        packet["entry_flags"] = m.IntAlias(packet["entry_flags"])
    reject(packet, monkeypatch)


@pytest.mark.parametrize("recipe", ((0, 0, 0), (15, 7, 0), (15, 7, 0xFFFFFFFF)))
def test_no_child_on_truncation_or_noop(recipe, monkeypatch):
    packet = inputs(*recipe)
    calls = []

    def forbidden(**kwargs):
        calls.append("child")
        raise AssertionError("non-interior arm called child")

    monkeypatch.setattr(c.memmove, "apply", forbidden)
    check(c.apply(**packet), packet)
    assert calls == []


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
        "flags",
        "mask",
        "snapshot",
        "pages_mapping",
        "pages_mutable",
        "events_tuple",
        "trace_tuple",
        "trace_bad",
        "trace_short",
        "missing_event",
        "extra_restored_write",
        "coordinated_value",
        "ancestor_page",
        "wrong_source_page",
    ),
)
def test_child11_full_terminal_ordered_access_page_and_schema_forgeries(
    kind, monkeypatch
):
    packet = inputs()
    before = copy.deepcopy(packet)
    calls = []

    def forged(**child_input):
        calls.append(copy.deepcopy(child_input))
        out = m.independent(child_input)
        g = child_input["registers"]["esp"]
        d = m.word(child_input["pages"], g + 4)
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
        elif kind == "flags":
            out["flags"] ^= 4
        elif kind == "mask":
            out["flag_mask"] = 0xFFFFFFFF
        elif kind == "snapshot":
            out["source_snapshot"] = bytes(8)
        elif kind == "pages_mapping":
            out["pages"] = UserDict(out["pages"])
        elif kind == "pages_mutable":
            out["pages"][0x12340000] = bytearray(4096)
        elif kind == "events_tuple":
            out["events"] = tuple(out["events"])
        elif kind == "trace_tuple":
            out["trace_rvas"] = tuple(out["trace_rvas"])
        elif kind == "trace_bad":
            out["trace_rvas"][0] = "not-rva"
        elif kind == "trace_short":
            out["trace_rvas"].pop(0)
        elif kind == "missing_event":
            out["events"].pop(0)
        elif kind == "extra_restored_write":
            at = d + 7
            original = m.read_bytes(out["pages"], at, 1)[0]
            out["events"].extend(
                (
                    dict(access="write", address=at, width=1, value=99),
                    dict(access="write", address=at, width=1, value=original),
                )
            )
        elif kind == "coordinated_value":
            out["events"][5]["value"] ^= 1
            out["events"][6]["value"] ^= 1
            m.store(out["pages"], d, out["events"][6]["value"].to_bytes(4, "little"))
            out["source_snapshot"] = (
                out["events"][6]["value"].to_bytes(4, "little")
                + out["source_snapshot"][4:]
            )
        elif kind == "ancestor_page":
            m.put_word(out["pages"], g + 16, 0)
        elif kind == "wrong_source_page":
            out["pages"][0x12340000] = bytes(4096)
        return out

    monkeypatch.setattr(c.memmove, "apply", forged)
    with pytest.raises(c.InlineStringEraseError):
        c.apply(**packet)
    assert len(calls) == 1
    m.equal(packet, before)


def test_actual_child_entry_sub_flags_and_interface_against_independent_stub(
    monkeypatch,
):
    packet = inputs(15, 7, 3)
    calls = []

    def supplied(**child_input):
        calls.append(copy.deepcopy(child_input))
        return m.independent(child_input)

    monkeypatch.setattr(c.memmove, "apply", supplied)
    actual = c.apply(**packet)
    check(actual, packet)
    assert (
        len(calls) == 1
        and calls[0]["registers"]["esp"] == packet["registers"]["esp"] - 32
    )
    assert calls[0]["return_address"] == 0x408476
    assert actual["boundaries"][0]["flags"] == sub_flags(12, 7) == 4
    assert calls[0]["entry_flags"] == 0x206


def test_valid_same_length_instruction_label_metadata_is_trusted(monkeypatch):
    packet = inputs()
    calls = []

    def supplied(**child_input):
        calls.append("child")
        out = m.independent(child_input)
        out["trace_rvas"][0] = "0x0036e581"
        return out

    monkeypatch.setattr(c.memmove, "apply", supplied)
    actual = c.apply(**packet)
    wanted = independent(packet)
    wanted["memmove_packet"]["trace_rvas"][0] = "0x0036e581"
    at = wanted["trace_rvas"].index("0x0036e580")
    wanted["trace_rvas"][at] = "0x0036e581"
    m.equal(actual, wanted)
    assert calls == ["child"]


@pytest.mark.parametrize("recipe", ((0, 0, 0), (15, 7, 0), (15, 3, 4)))
def test_inputs_results_child_and_boundary_detachment(recipe):
    packet = inputs(*recipe)
    before = copy.deepcopy(packet)
    first = c.apply(**packet)
    second = c.apply(**packet)
    check(first, before)
    m.equal(packet, before)
    first["registers"].clear()
    first["pages"].clear()
    first["events"].clear()
    first["geometry"].clear()
    if first["memmove_packet"]:
        first["memmove_packet"]["pages"].clear()
        first["boundaries"][0]["registers"].clear()
    packet["xmm"]["xmm0"] = 0
    packet["pages"][0x12340000] = bytes(4096)
    check(second, before)


def test_exact_api_and_owner_body_identity():
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
    assert c.BODY_PINS[0x8410] == (
        153,
        "fb7238468a109aeabf0d45ce924e0591ab679bf07e3882f08605a15ae18af0b7",
    )
