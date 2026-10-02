"""Handwritten same-object 80D0 wrapper around the independent erase TEST law."""

import copy
import inspect
from collections import UserDict
import pytest
from src.observatory import native_movement_inline_self_copy_semantics as c
from tests import test_itb_native_movement_inline_string_erase_semantics as e

m = e.m
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
    "erase_packet",
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
    0x80D0,
    0x80D1,
    0x80D3,
    0x80D4,
    0x80D7,
    0x80D8,
    0x80DA,
    0x80DD,
    0x80DE,
    0x80E1,
    0x80E3,
    0x80E9,
    0x80EC,
    0x80EE,
    0x80F0,
    0x80F3,
    0x80F5,
    0x80F7,
    0x80FA,
    0x80FD,
    0x8103,
    0x8106,
    0x810A,
    0x8125,
    0x8127,
    0x8128,
    0x812A,
    0x812C,
    0x8130,
)
SUFFIX = (0x8135, 0x8136, 0x8138, 0x8139, 0x813A, 0x813B)
RECIPES = [
    (length, off, req)
    for length in range(16)
    for off in range(length + 1)
    for req in (0, 1, 3, length - off, 0xFFFFFFFF)
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
        (frame - 68, frame + 16),
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
    for at, value in (
        (frame, return_address),
        (frame + 4, object_address),
        (frame + 8, offset),
        (frame + 12, requested),
        (object_address + 16, length),
        (object_address + 20, 15),
    ):
        m.put_word(pages, at, value)
    m.store(
        pages, object_address, bytes((i * 17 + profile * 53) & 255 for i in range(16))
    )
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmm,
        return_address=return_address,
        entry_flags=flags,
    )


def independent(packet):
    incoming = packet["registers"]
    g, h = incoming["esp"], incoming["ecx"]
    length = m.word(packet["pages"], h + 16)
    off = m.word(packet["pages"], g + 8)
    req = m.word(packet["pages"], g + 12)
    n = min(req, length - off)
    pages = dict(packet["pages"])
    events = []

    def write(at, value, width=4):
        m.store(pages, at, value.to_bytes(width, "little"))
        events.append(dict(access="write", address=at, width=width, value=value))

    def read(at):
        value = m.word(pages, at)
        events.append(dict(access="read", address=at, width=4, value=value))
        return value

    write(g - 4, incoming["ebp"])
    write(g - 8, incoming["ebx"])
    read(g + 4)
    write(g - 12, incoming["esi"])
    read(g + 8)
    write(g - 16, incoming["edi"])
    read(h + 16)
    read(g + 12)
    read(h + 16)
    write(h + 16, off + n)
    read(h + 20)
    write(g - 20, off)
    write(g - 24, 0)
    write(h + off + n, 0, 1)
    write(g - 28, 0x408135)
    regs = dict(
        incoming, eax=off + n, ebx=h, ecx=h, edx=h, esi=h, edi=n, ebp=g - 4, esp=g - 28
    )
    prefix = copy.deepcopy(events)
    states = [
        dict(
            registers=dict(regs),
            xmm=dict(packet["xmm"]),
            pages=dict(pages),
            events=copy.deepcopy(events),
            flags=0x85,
            flag_mask=0x8D5,
            df=0,
            endpoint=0x408410,
            phase="erase_entry",
        )
    ]
    child_input = dict(
        pages=dict(pages),
        registers=dict(regs),
        xmm=dict(packet["xmm"]),
        return_address=0x408135,
        entry_flags=(packet["entry_flags"] & 0x202) | 0x85,
    )
    child = e.independent(child_input)
    for state in child["boundaries"]:
        state = copy.deepcopy(state)
        state["events"] = prefix + state["events"]
        state["phase"] = "memmove_" + state["phase"]
        states.append(state)
    pages = dict(child["pages"])
    events += copy.deepcopy(child["events"])
    states.append(
        dict(
            registers=dict(child["registers"]),
            xmm=dict(packet["xmm"]),
            pages=dict(pages),
            events=copy.deepcopy(events),
            flags=child["flags"],
            flag_mask=child["flag_mask"],
            df=0,
            endpoint=0x408135,
            phase="erase_return",
        )
    )
    for at in (g - 16, g - 12, g - 8, g - 4, g):
        read(at)
    final = dict(
        incoming,
        eax=h,
        ecx=child["registers"]["ecx"],
        edx=child["registers"]["edx"],
        esp=g + 16,
    )
    # Byte equation uses the original object, not the child's output/events.
    original = m.read_bytes(packet["pages"], h, 24)
    direct = bytearray(original)
    direct[off + n] = 0
    if n:
        direct[:n] = original[off : off + n]
    direct[n] = 0
    direct[16:20] = n.to_bytes(4, "little")
    assert m.read_bytes(pages, h, 24) == bytes(direct)
    return dict(
        geometry=dict(
            entry=g,
            source_object=h,
            destination_object=h,
            source_length=length,
            offset=off,
            requested=req,
            count=n,
        ),
        registers=final,
        xmm=dict(packet["xmm"]),
        pages=pages,
        events=events,
        trace_rvas=[f"0x{pc:08x}" for pc in PREFIX]
        + child["trace_rvas"]
        + [f"0x{pc:08x}" for pc in SUFFIX],
        flags=child["flags"],
        flag_mask=child["flag_mask"],
        df=0,
        endpoint=packet["return_address"],
        source_snapshot=original,
        string_bytes=bytes(direct),
        erase_packet=copy.deepcopy(child),
        boundaries=states,
    )


def check(actual, packet):
    m.equal(actual, independent(packet))
    assert type(actual) is dict and set(actual) == KEYS
    g, h = packet["registers"]["esp"], packet["registers"]["ecx"]
    off = m.word(packet["pages"], g + 8)
    n = actual["geometry"]["count"]
    q, r = divmod(n, 4)
    assert len(actual["events"]) == (
        33 if not n else 30 if not off else 49 + 2 * q + 2 * r
    )
    assert len(actual["trace_rvas"]) == (
        58 if not n else 56 if not off else 101 + 6 * q + 6 * r + 2 * bool(r)
    )
    assert [s["phase"] for s in actual["boundaries"]] == (
        ["erase_entry", "memmove_entry", "memmove_return", "erase_return"]
        if n and off
        else ["erase_entry", "erase_return"]
    )
    assert all(type(s) is dict and set(s) == COMMON for s in actual["boundaries"])
    assert len(actual["boundaries"][0]["events"]) == 15
    assert actual["boundaries"][0]["registers"]["esp"] == g - 28
    assert actual["erase_packet"]["source_snapshot"] != actual[
        "source_snapshot"
    ] or off + n == m.word(packet["pages"], h + 16)
    assert m.read_bytes(actual["pages"], g, 16) == m.read_bytes(packet["pages"], g, 16)
    assert m.word(actual["pages"], h + 20) == 15
    replay = dict(packet["pages"])
    for row in actual["events"]:
        at, w, v = row["address"], row["width"], row["value"]
        if row["access"] == "read":
            assert int.from_bytes(m.read_bytes(replay, at, w), "little") == v
        else:
            m.store(replay, at, v.to_bytes(w, "little"))
    m.equal(replay, actual["pages"])


@pytest.mark.parametrize("length,offset,requested", RECIPES)
@pytest.mark.parametrize("alignment", (0, 15))
def test_all_lengths_offsets_unsigned_clamps(length, offset, requested, alignment):
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
    "recipe", ((0, 0, 0), (15, 15, 0), (15, 7, 0), (15, 0, 7), (15, 7, 3))
)
def test_all_ordinary_flags_on_all_three_arms(flags, recipe):
    packet = inputs(*recipe, flags=flags)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize(
    "recipe", ((15, 0, 1), (15, 4, 3), (9, 0, 1), (15, 7, 0), (15, 7, 0xFFFFFFFF))
)
def test_all_alignment_word_and_byte_tail_children(alignment, recipe):
    packet = inputs(
        *recipe,
        frame=0x30000FF8 + alignment,
        object_address=0x10000FF0 + alignment,
        profile=alignment % 4,
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "g,h",
    (
        (68, 0x10000FF0),
        (0x30001003, 1),
        (0xFFFFFFEF, 0x10000FF0),
        (0x30001003, 0xFFFFFFFF - 24),
        (0x30001003, 0x7FFFFFF8),
        (0x30001003, 0x30001003 + 16),
        (0x30001003, 0x30001003 - 92),
    ),
)
@pytest.mark.parametrize("recipe", ((15, 3, 4), (15, 7, 0), (15, 7, 0xFFFFFFFF)))
def test_conservative_frame_full_uint_signed_crossing_and_adjacency(g, h, recipe):
    packet = inputs(*recipe, frame=g, object_address=h, return_address=0xFFFFFFFF)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("profile", range(4))
def test_arbitrary_volatile_nonvolatile_xmm_and_unread_inline_bytes(profile):
    packet = inputs(15, 3, 7, profile=profile)
    h = packet["registers"]["ecx"]
    m.store(packet["pages"], h, bytes(range(16)))
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["string_bytes"][:16] == bytes(
        (3, 4, 5, 6, 7, 8, 9, 0, 8, 9, 0, 11, 12, 13, 14, 15)
    )
    assert actual["source_snapshot"][:16] == bytes(range(16))


def reject(packet, monkeypatch):
    before = copy.deepcopy(packet)
    writes, children = [], []
    original = c._write

    def observed(*args, **kwargs):
        writes.append("write")
        return original(*args, **kwargs)

    def forbidden(**kwargs):
        children.append("child")
        raise AssertionError("invalid parent called erase")

    with monkeypatch.context() as patch:
        patch.setattr(c, "_write", observed)
        patch.setattr(c.erase, "apply", forbidden)
        with pytest.raises(c.InlineSelfCopyError):
            c.apply(**packet)
        assert writes == [] and children == []
    m.equal(packet, before)


INVALID = (
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
    "source_not_self",
    "return_frame",
    "return_object",
    "return_owner",
    "return_erase",
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
)


@pytest.mark.parametrize("kind", INVALID)
def test_typed_geometry_before_write_or_child(kind, monkeypatch):
    packet = inputs()
    g, h = packet["registers"]["esp"], packet["registers"]["ecx"]
    if kind == "offset16":
        m.put_word(packet["pages"], g + 8, 16)
    elif kind == "length16":
        m.put_word(packet["pages"], h + 16, 16)
    elif kind in ("capacity16", "capacity0"):
        m.put_word(packet["pages"], h + 20, 16 if kind == "capacity16" else 0)
    elif kind == "frame_underflow":
        packet["registers"]["esp"] = 67
    elif kind == "frame_wrap":
        packet["registers"]["esp"] = 0xFFFFFFF0
    elif kind == "object_zero":
        packet["registers"]["ecx"] = 0
    elif kind == "object_wrap":
        packet["registers"]["ecx"] = 0xFFFFFFF0
    elif kind == "object_unmapped":
        packet["registers"]["ecx"] = 0x20000000
    elif kind == "frame_unmapped":
        packet["pages"].pop(g & ~4095)
    elif kind == "overlap":
        packet["registers"]["ecx"] = g - 68
        m.put_word(packet["pages"], g + 4, g - 68)
        m.put_word(packet["pages"], g - 52, 15)
        m.put_word(packet["pages"], g - 48, 15)
    elif kind == "caller_return":
        m.put_word(packet["pages"], g, 0x4000004)
    elif kind == "source_not_self":
        m.put_word(packet["pages"], g + 4, h + 1)
    elif kind in (
        "return_frame",
        "return_object",
        "return_owner",
        "return_erase",
        "return_memmove",
    ):
        at = {
            "return_frame": g,
            "return_object": h,
            "return_owner": 0x4080D0,
            "return_erase": 0x408410,
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
def test_each_forbidden_flag_bit(bit, monkeypatch):
    reject(inputs(flags=2 | (1 << bit)), monkeypatch)


@pytest.mark.parametrize("flags", [f & ~2 for f in m.ORDINARY])
def test_required_bit1(flags, monkeypatch):
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
def test_exact_keys_and_subclass_words(kind, monkeypatch):
    packet = inputs()
    if kind == "page_intalias":
        packet["pages"][m.IntAlias(0x12340000)] = packet["pages"].pop(0x12340000)
    elif kind == "page_unaligned":
        packet["pages"][0x12340001] = bytes(4096)
    elif kind in ("gpr_stralias", "xmm_stralias"):
        key = "registers" if kind.startswith("gpr") else "xmm"
        name = "eax" if key == "registers" else "xmm0"
        packet[key][m.StrAlias(name)] = packet[key].pop(name)
    elif kind in ("gpr_intalias", "xmm_intalias"):
        key = "registers" if kind.startswith("gpr") else "xmm"
        name = "eax" if key == "registers" else "xmm0"
        packet[key][name] = m.IntAlias(packet[key][name])
    elif kind == "return_intalias":
        packet["return_address"] = m.IntAlias(packet["return_address"])
    elif kind == "flags_intalias":
        packet["entry_flags"] = m.IntAlias(packet["entry_flags"])
    reject(packet, monkeypatch)


FORGERIES = (
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
    "unrelated_page",
    "boundary_phase",
    "boundary_flags",
    "boundary_events",
    "boundary_pages",
    "nested_geometry",
    "nested_df",
    "nested_endpoint",
    "nested_event",
    "nested_pages",
    "nested_trace_short",
)


@pytest.mark.parametrize("kind", FORGERIES)
def test_complete_erase14_and_nested_memmove11_forgeries(kind, monkeypatch):
    packet = inputs()
    before = copy.deepcopy(packet)
    calls = []

    def forged(**child_input):
        calls.append(copy.deepcopy(child_input))
        out = e.independent(child_input)
        g, h = child_input["registers"]["esp"], child_input["registers"]["ecx"]
        if kind == "extra":
            out["extra"] = 0
        elif kind == "missing":
            out.pop("geometry")
        elif kind == "geometry_bool":
            out["geometry"]["offset"] = False
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
            out["source_snapshot"] = bytes(24)
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
            old = m.read_bytes(out["pages"], h + 14, 1)[0]
            out["events"].extend(
                (
                    dict(access="write", address=h + 14, width=1, value=99),
                    dict(access="write", address=h + 14, width=1, value=old),
                )
            )
        elif kind == "coordinated_value":
            out["events"][0]["value"] ^= 1
            m.put_word(out["pages"], g - 4, out["events"][0]["value"])
        elif kind == "ancestor_page":
            m.put_word(out["pages"], g + 28, 0)
        elif kind == "unrelated_page":
            out["pages"][0x12340000] = bytes(4096)
        elif kind == "boundary_phase":
            out["boundaries"][0]["phase"] = "return"
        elif kind == "boundary_flags":
            out["boundaries"][0]["flags"] ^= 4
        elif kind == "boundary_events":
            out["boundaries"][0]["events"][0]["value"] ^= 1
        elif kind == "boundary_pages":
            out["boundaries"][0]["pages"][0x12340000] = bytes(4096)
        elif kind == "nested_geometry":
            out["memmove_packet"]["geometry"]["count"] = True
        elif kind == "nested_df":
            out["memmove_packet"]["df"] = False
        elif kind == "nested_endpoint":
            out["memmove_packet"]["endpoint"] = float(out["memmove_packet"]["endpoint"])
        elif kind == "nested_event":
            out["memmove_packet"]["events"][0]["value"] ^= 1
        elif kind == "nested_pages":
            out["memmove_packet"]["pages"][0x12340000] = bytes(4096)
        elif kind == "nested_trace_short":
            out["memmove_packet"]["trace_rvas"].pop(0)
        return out

    monkeypatch.setattr(c.erase, "apply", forged)
    with pytest.raises(c.InlineSelfCopyError):
        c.apply(**packet)
    assert len(calls) == 1
    m.equal(packet, before)


@pytest.mark.parametrize("recipe", ((0, 0, 0), (15, 7, 0), (15, 0, 7), (15, 7, 3)))
def test_actual_child_input_interface_with_independent_supplied_stub(
    recipe, monkeypatch
):
    packet = inputs(*recipe)
    calls = []

    def supplied(**child_input):
        calls.append(copy.deepcopy(child_input))
        return e.independent(child_input)

    monkeypatch.setattr(c.erase, "apply", supplied)
    actual = c.apply(**packet)
    check(actual, packet)
    g, h = packet["registers"]["esp"], packet["registers"]["ecx"]
    assert len(calls) == 1
    assert set(calls[0]) == {
        "pages",
        "registers",
        "xmm",
        "return_address",
        "entry_flags",
    }
    assert calls[0]["registers"]["esp"] == g - 28
    assert calls[0]["entry_flags"] == 0x287
    assert calls[0]["return_address"] == 0x408135
    assert m.word(calls[0]["pages"], g - 24) == 0
    assert m.word(calls[0]["pages"], g - 20) == recipe[1]
    assert actual["boundaries"][0]["flags"] == 0x85
    assert actual["boundaries"][0]["pages"] == calls[0]["pages"]
    if actual["geometry"]["count"] and recipe[1]:
        assert actual["boundaries"][1]["registers"]["esp"] == g - 60
        assert actual["boundaries"][1]["flags"] == e.sub_flags(
            actual["geometry"]["count"], 0
        )


@pytest.mark.parametrize("nested", (False, True))
def test_canonical_same_length_child_trace_labels_remain_trusted(nested, monkeypatch):
    packet = inputs()

    def supplied(**child_input):
        out = e.independent(child_input)
        if nested:
            out["memmove_packet"]["trace_rvas"][0] = "0x0036e581"
        else:
            out["trace_rvas"][0] = "0x00008411"
        return out

    monkeypatch.setattr(c.erase, "apply", supplied)
    actual = c.apply(**packet)
    wanted = independent(packet)
    if nested:
        wanted["erase_packet"]["memmove_packet"]["trace_rvas"][0] = "0x0036e581"
    else:
        wanted["erase_packet"]["trace_rvas"][0] = "0x00008411"
        wanted["trace_rvas"][29] = "0x00008411"
    m.equal(actual, wanted)


@pytest.mark.parametrize("recipe", ((0, 0, 0), (15, 0, 7), (15, 7, 3)))
def test_input_child_boundary_and_result_detachment(recipe):
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
    first["erase_packet"]["pages"].clear()
    first["boundaries"][0]["registers"].clear()
    if first["erase_packet"]["memmove_packet"]:
        first["erase_packet"]["memmove_packet"]["pages"].clear()
    packet["xmm"]["xmm0"] = 0
    packet["pages"][0x12340000] = bytes(4096)
    check(second, before)


def test_exact_api_and_pinned_body_identity():
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
