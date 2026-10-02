"""Independent early AddCharge owner law with handwritten child test witnesses."""

from __future__ import annotations
import ast
import copy
import inspect
from collections import UserDict
import pytest
from src.observatory import native_movement_addcharge_early_semantics as c
from tests import test_itb_native_movement_path_small_clone_semantics as clone
from tests import test_itb_native_movement_addmove_early_semantics as move

strict_equal = move.strict_equal
read_bytes, word = move.blob, move.word


def store(pages, address, value, width=4):
    for i, byte in enumerate(value.to_bytes(width, "little")):
        at = address + i
        page = at & ~4095
        data = bytearray(pages[page])
        data[at & 4095] = byte
        pages[page] = bytes(data)


add_flags = move.add_flags
logical_flags = move.logical_test_flags
GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
FLAGS = tuple(2 | v for v in range(0xAD8) if v & ~0xAD5 == 0)
KEYS = {
    "geometry",
    "path",
    "registers",
    "xmm",
    "pages",
    "events",
    "trace_rvas",
    "boundaries",
    "imports",
    "child_packets",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
}
COMMON = {"registers", "xmm", "pages", "events", "flags", "flag_mask", "df", "endpoint"}
OWNER = (
    tuple(
        int(w, 16)
        for w in "2576f0 2576f1 2576f3 2576f5 2576fa 257700 257701 257702 257707 257709 25770a 25770d 257713 257715 25771a 25771d 257720 257727 257729 25772c 257732 257733".split()
    ),
    (0x257738, 0x25773A),
)
PREDICATE = (0x25773F, 0x257741, 0x25774D, 0x257750, 0x257752)
FREE_CALL = (0x257754, 0x257757, 0x257759, 0x25775B, 0x25775E, 0x25775F, 0x257760)
SUFFIX = (0x257768, 0x25776B, 0x257772, 0x257773, 0x257774, 0x257776, 0x257777)
OUTER_FREE_TRACE = tuple(
    int(w, 16)
    for w in "7800 7801 7803 7806 7809 780b 780e 7810 7816 781a 7820 784d 7850 7851 35785d 36fb17 389156 389158 389159 38915b 38915f 389161 389164 389166 38916c 389172 389174 38918e 38918f 7856 7859 785a".split()
)


def sub_flags(a, b):
    r = (a - b) & 0xFFFFFFFF
    return (
        int(a < b)
        | logical_flags(r)
        | ((a ^ b ^ r) & 0x10)
        | (0x800 if (a ^ b) & (a ^ r) & 0x80000000 else 0)
    )


def inputs(
    form="one",
    *,
    capacity_count=1,
    frame=0x30001003,
    receiver=0x10000FF9,
    source=0x20000FF9,
    allocation=0x06001FF8,
    return_address=0x04000000,
    flags=0x246,
    cookie=0x19A51C73,
    seh=0x1234ABCD,
    parameter=0xBF800000,
    profile=0,
):
    begin = 0 if form == "null" else source
    end = begin + (8 if form == "one" else 0)
    capacity = begin + (capacity_count * 8 if begin else 0)
    windows = {min((frame - d) & ~4095, 0xFFFFE000) for d in (0x2E4, 136, 72)}
    spans = [(base, base + 8192) for base in windows] + [(receiver, receiver + 12)]
    keys = {0, 0x00893000, 0x19000000}
    if begin:
        spans.append((begin, capacity))
        keys.update((0x06000000, 0x008B7000, 0x007D6000))
    if form == "one":
        keys.update((0x06000000, 0x06001000, 0x06002000, 0x06003000))
    for start, endspan in spans:
        keys.update(range(start & ~4095, ((endspan - 1) & ~4095) + 4096, 4096))
    pages = {
        base: bytes((i * 37 + j * 29 + profile * 71) & 255 for j in range(4096))
        for i, base in enumerate(sorted(keys))
    }
    regs = {
        n: (0x13579BDF + i * 0x11111111 + profile * 0x27481935) & 0xFFFFFFFF
        for i, n in enumerate(GPR)
    }
    regs.update(ecx=receiver, esp=frame)
    vec = {
        n: int.from_bytes(
            bytes((i * 17 + j * 41 + profile * 67) & 255 for j in range(16)), "little"
        )
        for i, n in enumerate(XMM)
    }
    for at, value in (
        (frame, return_address),
        (frame + 4, begin),
        (frame + 8, end),
        (frame + 12, capacity),
        (frame + 16, parameter),
        (0, seh),
        (0x00893F28, cookie),
        (receiver, 0xFFFFFFFF),
        (receiver + 4, 0x80000000),
        (receiver + 8, 0x12345678),
    ):
        store(pages, at, value)
    if begin:
        store(pages, 0x008B7634, 0x12345678)
        store(pages, 0x007D621C, 0x05000000)
    if form == "one":
        store(pages, 0x007D6220, 0x05000000)
    return dict(
        pages=pages,
        registers=regs,
        xmm=vec,
        return_address=return_address,
        entry_flags=flags,
        allocation_result=allocation if form == "one" else 0,
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
    g, h = initial["esp"], initial["ecx"]
    source = word(packet["pages"], g + 4)
    parameter = word(packet["pages"], g + 16)
    end, capacity = word(packet["pages"], g + 8), word(packet["pages"], g + 12)
    count = (end - source) // 8
    capacity_count = (capacity - source) // 8 if source else 0
    seh, cookie = word(packet["pages"], 0), word(packet["pages"], 0x00893F28)
    pages = dict(packet["pages"])
    regs, vec = dict(initial), dict(packet["xmm"])
    events, trace, states, imports, children = [], [], [], [], {}

    def event(kind, at, value, width=4):
        if kind == "write":
            store(pages, at, value, width)
        else:
            assert int.from_bytes(read_bytes(pages, at, width), "little") == value
        events.append(dict(access=kind, address=at, width=width, value=value))

    def snapshot(name, phase, endpoint, flags, mask=0x8D5):
        states.append(
            dict(
                name=name,
                phase=phase,
                registers=dict(regs),
                xmm=dict(vec),
                pages=dict(pages),
                events=copy.deepcopy(events),
                flags=flags,
                flag_mask=mask,
                df=0,
                endpoint=endpoint,
            )
        )

    for kind, at, value in (
        ("write", g - 4, initial["ebp"]),
        ("write", g - 8, 0xFFFFFFFF),
        ("write", g - 12, 0x007CAA08),
        ("read", 0, seh),
        ("write", g - 16, seh),
        ("write", g - 20, initial["esi"]),
        ("read", 0x00893F28, cookie),
        ("write", g - 24, cookie ^ (g - 4)),
        ("write", 0, g - 16),
        ("read", g + 16, parameter),
        ("write", g - 8, 0),
        ("write", g + 16, g - 40),
        ("write", g - 28, parameter),
        ("write", g - 44, g + 4),
        ("write", g - 48, 0x00657738),
    ):
        event(kind, at, value)
    vec["xmm0"] = parameter
    regs.update(eax=g + 4, ecx=g - 40, esi=h, ebp=g - 4, esp=g - 48)
    flags = sub_flags(g - 24, 16)
    trace.extend(f"0x{pc:08x}" for pc in OWNER[0])
    snapshot("clone_argument", "entry", 0x0049A8E0, flags)
    prefix = copy.deepcopy(events)
    child = clone.independent(
        dict(
            pages=dict(pages),
            registers=dict(regs),
            xmm=dict(vec),
            return_address=0x00657738,
            entry_flags=(packet["entry_flags"] & ~0x8D5) | flags,
            allocation_result=packet["allocation_result"],
        )
    )
    children["clone_argument"] = copy.deepcopy(child)
    if child["imported"] is not None:
        state = copy.deepcopy(child["imported"])
        state.update(name="clone_argument", events=prefix + state["events"])
        imports.append(state)
    trace.extend(child["trace_rvas"])
    events.extend(copy.deepcopy(child["events"]))
    pages, regs, vec = (
        dict(child["pages"]),
        dict(child["registers"]),
        dict(child["xmm"]),
    )
    snapshot("clone_argument", "return", 0x00657738, child["flags"], child["flag_mask"])
    event("write", g - 44, 0x0065773F)
    regs.update(ecx=h, esp=g - 44)
    trace.extend(f"0x{pc:08x}" for pc in OWNER[1])
    snapshot("addmove", "entry", 0x00657340, child["flags"], child["flag_mask"])
    prefix = copy.deepcopy(events)
    child = move.independent(
        dict(
            pages=dict(pages),
            registers=dict(regs),
            xmm=dict(vec),
            return_address=0x0065773F,
            entry_flags=(packet["entry_flags"] & ~0x8D5) | child["flags"],
        )
    )
    children["addmove"] = copy.deepcopy(child)
    if child["imported"] is not None:
        imported = copy.deepcopy(child["imported"])
        imported.pop("role")
        imported.update(name="free_clone", events=prefix + imported["events"])
        imports.append(imported)
    trace.extend(child["trace_rvas"])
    events.extend(copy.deepcopy(child["events"]))
    pages, regs, vec = (
        dict(child["pages"]),
        dict(child["registers"]),
        dict(child["xmm"]),
    )
    snapshot("addmove", "return", 0x0065773F, child["flags"])
    event("read", g + 4, source)
    regs["ecx"] = source
    trace.extend(f"0x{pc:08x}" for pc in PREDICATE)
    children["free_original"] = None
    final_flags, final_mask = 0x44, 0x8C5
    if source:
        event("read", g + 12, capacity)
        for at, value in (
            (g - 28, 8),
            (g - 32, capacity_count),
            (g - 36, source),
            (g - 40, 0x00657765),
        ):
            event("write", at, value)
        regs.update(eax=capacity_count, ecx=source, esp=g - 40)
        trace.extend(f"0x{pc:08x}" for pc in FREE_CALL)
        snapshot(
            "free_original", "entry", 0x00407800, logical_flags(capacity_count), 0xC5
        )
        prefix = copy.deepcopy(events)
        base = min((g - 72) & ~4095, 0xFFFFE000)
        free = free_law(
            dict(
                pointer=source,
                count=capacity_count,
                stride=8,
                metadata=None,
                responses=[dict(kind="heap_free", eax=1)],
                heap=0x12345678,
            ),
            regs,
            read_bytes(pages, base, 8192),
            pages[0x06000000],
            stack_base=base,
        )
        assert word(pages, g - 40) == 0x00657765
        free["events"][-1]["value"] = 0x00657765
        free["stop"] = 0x00657765
        children["free_original"] = copy.deepcopy(free)
        importpages = dict(pages)
        for row in free["events"][:16]:
            if row["access"] == "write":
                store(importpages, row["address"], row["value"])
        imports.append(
            dict(
                name="free_original",
                registers=dict(
                    regs, eax=0x1FFFFFFF, ecx=source, edx=7, ebp=g - 56, esp=g - 72
                ),
                xmm=dict(vec),
                pages=importpages,
                events=prefix + copy.deepcopy(free["events"][:16]),
                flags=logical_flags(source),
                flag_mask=0x8C5,
                df=0,
                endpoint=0x05000000,
                entry_esp=g - 72,
                words=[0x00789172, 0x12345678, 0, source],
            )
        )
        trace.extend(f"0x{pc:08x}" for pc in OUTER_FREE_TRACE)
        events.extend(copy.deepcopy(free["events"]))
        pages[base], pages[base + 4096] = free["stack"][:4096], free["stack"][4096:]
        regs = dict(free["registers"])
        snapshot("free_original", "return", 0x00657765, free["flags"])
        regs["esp"] += 12
        trace.append("0x00257765")
        final_flags, final_mask = add_flags(g - 36, 12), 0x8D5
    for kind, at, value in (
        ("read", g - 16, seh),
        ("write", 0, seh),
        ("read", g - 24, cookie ^ (g - 4)),
        ("read", g - 20, initial["esi"]),
        ("read", g - 4, initial["ebp"]),
        ("read", g, packet["return_address"]),
    ):
        event(kind, at, value)
    trace.extend(f"0x{pc:08x}" for pc in SUFFIX)
    return dict(
        geometry=dict(
            entry=g,
            receiver=h,
            source_path=source,
            argument_block=g - 40,
        ),
        path=dict(
            begin=source,
            end=end,
            capacity=capacity,
            count=count,
            parameter_bits=parameter,
        ),
        registers=dict(
            regs,
            ecx=cookie ^ (g - 4),
            esi=initial["esi"],
            ebp=initial["ebp"],
            esp=g + 20,
        ),
        xmm=vec,
        pages=pages,
        events=events,
        trace_rvas=trace,
        boundaries=states,
        imports=imports,
        child_packets=children,
        flags=final_flags,
        flag_mask=final_mask,
        df=0,
        endpoint=packet["return_address"],
    )


def check(actual, packet):
    expected = independent(packet)
    strict_equal(actual, expected)
    assert type(actual) is dict and set(actual) == KEYS
    g = packet["registers"]["esp"]
    h = packet["registers"]["ecx"]
    o, e, cap, param = [word(packet["pages"], g + x) for x in (4, 8, 12, 16)]
    n = (e - o) // 8
    assert len(actual["trace_rvas"]) == (284 if n else 155 if o else 115)
    assert len(actual["events"]) == (177 if n else 99 if o else 74)
    assert len(actual["boundaries"]) == (6 if o else 4)
    assert len(actual["imports"]) == (3 if n else 1 if o else 0)
    assert all(type(ev["width"]) is int and ev["width"] == 4 for ev in actual["events"])
    assert [len(b["events"]) for b in actual["boundaries"]] == (
        [15, 94, 95, 145, 151, 171]
        if n
        else [15, 41, 42, 67, 73, 93] if o else [15, 41, 42, 67]
    )
    assert [b["name"] for b in actual["imports"]] == (
        ["clone_argument", "free_clone", "free_original"]
        if n
        else ["free_original"] if o else []
    )
    assert [len(b["events"]) for b in actual["imports"]] == (
        [54, 130, 167] if n else [89] if o else []
    )
    assert read_bytes(actual["pages"], h, 12) == read_bytes(packet["pages"], h, 12)
    assert not any(h <= ev["address"] < h + 12 for ev in actual["events"])
    assert not {"0x00257743", "0x00257746"}.intersection(actual["trace_rvas"])
    assert read_bytes(actual["pages"], g, 16) == read_bytes(packet["pages"], g, 16)
    assert word(actual["pages"], g + 16) == g - 40
    assert actual["xmm"]["xmm0"] == param
    assert all(actual["xmm"][n] == packet["xmm"][n] for n in XMM[1:])
    assert actual["registers"]["ecx"] == word(packet["pages"], 0x893F28) ^ (g - 4)
    if o:
        assert read_bytes(actual["pages"], o, cap - o) == read_bytes(
            packet["pages"], o, cap - o
        )
    assert set(actual["child_packets"]) == {
        "clone_argument",
        "addmove",
        "free_original",
    }
    assert actual["child_packets"]["addmove"]["registers"]["eax"] & 255 == 0
    assert actual["registers"]["eax"] == (1 if o else 0)
    if n:
        assert actual["imports"][0]["words"] == [0x789463, 0x12345678, 0, 8]
        assert [state["words"][3] for state in actual["imports"][1:]] == [
            packet["allocation_result"],
            o,
        ]
    elif o:
        assert actual["imports"][0]["words"] == [0x789172, 0x12345678, 0, o]
    else:
        assert actual["child_packets"]["free_original"] is None


@pytest.mark.parametrize("form", ("null", "empty_owned", "one"))
@pytest.mark.parametrize("a", range(16))
@pytest.mark.parametrize("profile", range(3))
def test_all144_three_path_forms_independent_complete14(form, a, profile):
    packet = inputs(
        form,
        frame=0x30001000 + a,
        receiver=0x10000FF9 + a,
        source=0x20000FF9 + a,
        allocation=0x06001FF8 + a,
        profile=profile,
        parameter=(0xBF800000, 0x7FC01234, 0xFF800000)[profile],
    )
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    strict_equal(packet, before)


@pytest.mark.parametrize("form", ("null", "empty_owned", "one"))
@pytest.mark.parametrize("flags", FLAGS)
def test_all128_ordinary_words_three_forms(flags, form):
    packet = inputs(form, flags=flags, capacity_count=17, cookie=0)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("form", ("empty_owned", "one"))
@pytest.mark.parametrize("k", (1, 2, 3, 17, 511))
@pytest.mark.parametrize("cookie", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_original_capacity_based_free_and_outer_cached_cookie(form, k, cookie):
    packet = inputs(form, capacity_count=k, cookie=cookie)
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["boundaries"][-2]["registers"]["eax"] == k
    assert actual["boundaries"][-2]["flags"] == logical_flags(k)


@pytest.mark.parametrize(
    "parameter", (0, 1, 0x80000000, 0xFFFFFFFF, 0x7FC01234, 0xBF800000)
)
@pytest.mark.parametrize("form", ("null", "empty_owned", "one"))
def test_uninterpreted_parameter_bits_and_movss_upper_xmm_clear(parameter, form):
    packet = inputs(form, parameter=parameter)
    packet["xmm"]["xmm0"] = 2**128 - 1
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("form", ("null", "empty_owned", "one"))
@pytest.mark.parametrize("value", (0, 0x80000000, 0xFFFFFFFF))
def test_full_nonaddress_gpr_xmm_fs_cookie_and_unread_receiver(form, value):
    packet = inputs(form, cookie=value, seh=value)
    for n in GPR:
        if n not in ("ecx", "esp"):
            packet["registers"][n] = value
    for n in XMM:
        packet["xmm"][n] = sum(value << (32 * i) for i in range(4))
    for off in (0, 4, 8):
        store(packet["pages"], packet["registers"]["ecx"] + off, value)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("form", ("null", "empty_owned", "one"))
def test_nested_result_detachment_and_input_preservation(form):
    packet = inputs(form, capacity_count=17)
    before = copy.deepcopy(packet)
    actual = c.apply(**packet)
    expected = independent(packet)
    actual["pages"].clear()
    actual["registers"].clear()
    actual["xmm"].clear()
    actual["events"].clear()
    actual["boundaries"][0]["pages"].clear()
    actual["child_packets"]["clone_argument"]["events"].clear()
    if form != "null":
        actual["child_packets"]["free_original"]["protocol"].clear()
    strict_equal(packet, before)
    strict_equal(c.apply(**packet), expected)


@pytest.mark.parametrize(
    "kind",
    (
        "pages_mapping",
        "page_mutable",
        "page_float",
        "gpr_bool",
        "gpr_float",
        "gpr_extra",
        "gpr_alias",
        "xmm_bool",
        "xmm_large",
        "xmm_mapping",
        "flags_bool",
        "flags_missingbit",
        "flags_df",
        "flags_rf",
        "return_float",
        "return_bool",
        "allocation_bool",
        "allocation_float",
    ),
)
def test_closed_typed_actual_inputs(kind):
    packet = inputs()
    if kind == "pages_mapping":
        packet["pages"] = UserDict(packet["pages"])
    elif kind == "page_mutable":
        packet["pages"][0] = bytearray(packet["pages"][0])
    elif kind == "page_float":
        packet["pages"][0.0] = packet["pages"].pop(0)
    elif kind == "gpr_bool":
        packet["registers"]["eax"] = False
    elif kind == "gpr_float":
        packet["registers"]["edi"] = 0.0
    elif kind == "gpr_extra":
        packet["registers"]["other"] = 0
    elif kind == "gpr_alias":

        class Alias(str):
            pass

        packet["registers"] = {Alias(k): v for k, v in packet["registers"].items()}
    elif kind == "xmm_bool":
        packet["xmm"]["xmm0"] = False
    elif kind == "xmm_large":
        packet["xmm"]["xmm7"] = 2**128
    elif kind == "xmm_mapping":
        packet["xmm"] = UserDict(packet["xmm"])
    elif kind.startswith("flags"):
        packet["entry_flags"] = {
            "flags_bool": True,
            "flags_missingbit": 0x244,
            "flags_df": 0x646,
            "flags_rf": 0x10246,
        }[kind]
    elif kind == "return_float":
        packet["return_address"] = float(0x04000000)
    elif kind == "return_bool":
        packet["return_address"] = True
    elif kind == "allocation_bool":
        packet["allocation_result"] = False
    else:
        packet["allocation_result"] = float(0x06001FF8)
    with pytest.raises(c.AddChargeEarlyError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    (
        "count2",
        "end_under",
        "end_fraction",
        "cap512",
        "cap_under",
        "cap_fraction",
        "null_mixed",
        "owned_empty_alloc",
        "null_alloc",
        "allocation_high",
        "allocation_alias",
        "source_spare_unmapped",
        "missing_error",
        "missing_data",
        "missing_iat",
        "wrong_alloc_iat",
        "wrong_free_iat",
        "wrong_heap",
        "caller_return",
        "lowframe",
        "wrapframe",
        "receiver_frame",
        "return_source",
        "return_local",
        "selected_page",
    ),
)
def test_closed_domain_geometry_runtime_and_count(kind):
    form = (
        "null"
        if kind.startswith("null")
        else "empty_owned" if kind == "owned_empty_alloc" else "one"
    )
    packet = inputs(form, capacity_count=3)
    g = 0x30001003
    o = 0x20000FF9
    if kind == "count2":
        store(packet["pages"], g + 8, o + 16)
    elif kind == "end_under":
        store(packet["pages"], g + 8, o - 8)
    elif kind == "end_fraction":
        store(packet["pages"], g + 8, o + 7)
    elif kind == "cap512":
        store(packet["pages"], g + 12, o + 4096)
    elif kind == "cap_under":
        store(packet["pages"], g + 12, o)
    elif kind == "cap_fraction":
        store(packet["pages"], g + 12, o + 23)
    elif kind == "null_mixed":
        store(packet["pages"], g + 12, 8)
    elif kind in ("owned_empty_alloc", "null_alloc"):
        packet["allocation_result"] = 0x06001FF8
    elif kind == "allocation_high":
        packet["allocation_result"] = 0x06003FF9
    elif kind == "allocation_alias":
        # Original source extent inside DATA is still mapped; D aliases its used word.
        for off, val in ((4, 0x06001FF8), (8, 0x06002000), (12, 0x06002010)):
            store(packet["pages"], g + off, val)
    elif kind == "source_spare_unmapped":
        del packet["pages"][0x20001000]
    elif kind == "missing_error":
        del packet["pages"][0x06000000]
    elif kind == "missing_data":
        del packet["pages"][0x06003000]
    elif kind == "missing_iat":
        del packet["pages"][0x007D6000]
    elif kind in ("wrong_alloc_iat", "wrong_free_iat", "wrong_heap"):
        store(
            packet["pages"],
            {
                "wrong_alloc_iat": 0x7D6220,
                "wrong_free_iat": 0x7D621C,
                "wrong_heap": 0x8B7634,
            }[kind],
            0,
        )
    elif kind == "caller_return":
        store(packet["pages"], g, 0x04000004)
    elif kind == "lowframe":
        packet["registers"]["esp"] = 0x2E3
    elif kind == "wrapframe":
        packet["registers"]["esp"] = 0xFFFFFFEC
    elif kind == "receiver_frame":
        packet["registers"]["ecx"] = g - 40
    elif kind in ("return_source", "return_local"):
        value = o + 16 if kind == "return_source" else g - 40
        packet["return_address"] = value
        store(packet["pages"], g, value)
    else:
        packet["pages"][0x00657000] = bytes(4096)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("child")
        raise AssertionError("invalid input reached child")

    # The inherited validate is used but dependency apply must not be invoked.
    from unittest.mock import patch

    with patch.object(c.path, "apply", forbidden), patch.object(
        c.move, "apply", forbidden
    ):
        with pytest.raises(c.AddChargeEarlyError):
            c.apply(**packet)
    assert calls == []


@pytest.mark.parametrize("child", ("clone", "move"))
@pytest.mark.parametrize("form", ("null", "one"))
@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "gpr_bool",
        "gpr_alias",
        "xmm_bool",
        "pages_mapping",
        "pages_float",
        "page_mutable",
        "events_tuple",
        "event_width_float",
        "trace_tuple",
        "trace_noncanonical",
        "df_bool",
        "endpoint_float",
        "flags_float",
        "mask_float",
        "nested_extra",
        "nested_df",
        "nested_event_bool",
    ),
)
def test_closed_child_envelopes_common_states_and_nested_boundaries(
    child, form, kind, monkeypatch
):
    def forged(**kwargs):
        packet = (clone.independent if child == "clone" else move.independent)(kwargs)
        if kind == "extra":
            packet["extra"] = 0
        elif kind == "missing":
            packet.pop("xmm")
        elif kind == "gpr_bool":
            packet["registers"]["eax"] = False
        elif kind == "gpr_alias":

            class Alias(str):
                pass

            packet["registers"] = {Alias(k): v for k, v in packet["registers"].items()}
        elif kind == "xmm_bool":
            packet["xmm"]["xmm0"] = False
        elif kind == "pages_mapping":
            packet["pages"] = UserDict(packet["pages"])
        elif kind == "pages_float":
            packet["pages"][0.0] = packet["pages"].pop(0)
        elif kind == "page_mutable":
            packet["pages"][0] = bytearray(packet["pages"][0])
        elif kind == "events_tuple":
            packet["events"] = tuple(packet["events"])
        elif kind == "event_width_float":
            packet["events"][0]["width"] = 4.0
        elif kind == "trace_tuple":
            packet["trace_rvas"] = tuple(packet["trace_rvas"])
        elif kind == "trace_noncanonical":
            packet["trace_rvas"][0] = "0x00000ABC"
        elif kind == "df_bool":
            packet["df"] = False
        elif kind == "endpoint_float":
            packet["endpoint"] = float(packet["endpoint"])
        elif kind == "flags_float":
            packet["flags"] = float(packet["flags"])
        elif kind == "mask_float":
            packet["flag_mask"] = float(packet["flag_mask"])
        else:
            state = (
                packet["boundaries"]["parent_entry"]
                if child == "clone"
                else packet["cookie_entry"]
            )
            if kind == "nested_extra":
                state["extra"] = 0
            elif kind == "nested_df":
                state["df"] = False
            else:
                state["events"].append(
                    dict(access="read", address=0, width=True, value=0)
                )
        return packet

    monkeypatch.setattr(c.path if child == "clone" else c.move, "apply", forged)
    with pytest.raises(c.AddChargeEarlyError):
        c.apply(**inputs(form))


@pytest.mark.parametrize("child", ("clone", "move"))
@pytest.mark.parametrize(
    "kind",
    (
        "snapshot_type",
        "scalar_extra",
        "scalar_snapshot",
        "import_word_bool",
        "import_words_tuple",
        "import_role",
        "geometry_bool",
        "path_count_float",
        "free_protocol_bool",
        "empty_children",
    ),
)
def test_positive_child_extra_schemas_and_nullable_children(child, kind, monkeypatch):
    def forged(**kwargs):
        packet = (clone.independent if child == "clone" else move.independent)(kwargs)
        if child == "clone":
            if kind == "snapshot_type":
                packet["source_snapshot"] = bytearray(packet["source_snapshot"])
            elif kind == "scalar_extra":
                packet["scalar_packet"]["extra"] = 0
            elif kind == "scalar_snapshot":
                packet["scalar_packet"]["source_snapshot"] = bytes(7)
            elif kind == "import_word_bool":
                packet["imported"]["words"][2] = False
            elif kind == "import_words_tuple":
                packet["imported"]["words"] = tuple(packet["imported"]["words"])
            elif kind == "import_role":
                packet["imported"]["entry_esp"] = float(packet["imported"]["entry_esp"])
            elif kind == "geometry_bool":
                packet["geometry"]["source"] = True
            elif kind == "path_count_float":
                packet["allocation_packet"]["relation"]["request"] = 8.0
            elif kind == "free_protocol_bool":
                packet["allocation_packet"]["flag_mask"] = float(
                    packet["allocation_packet"]["flag_mask"]
                )
            else:
                packet["imported"] = None
        else:
            if kind == "snapshot_type":
                packet["free_packet"]["stack"] = bytearray(
                    packet["free_packet"]["stack"]
                )
            elif kind == "scalar_extra":
                packet["path"]["extra"] = 0
            elif kind == "scalar_snapshot":
                packet["free_packet"]["error"] = bytes(4095)
            elif kind == "import_word_bool":
                packet["imported"]["words"][2] = False
            elif kind == "import_words_tuple":
                packet["imported"]["words"] = tuple(packet["imported"]["words"])
            elif kind == "import_role":
                packet["imported"]["role"] = "allocate"
            elif kind == "geometry_bool":
                packet["path"]["capacity"] = True
            elif kind == "path_count_float":
                packet["path"]["count"] = 1.0
            elif kind == "free_protocol_bool":
                packet["free_packet"]["protocol"]["result"] = True
            else:
                packet["free_entry"] = None
        return packet

    monkeypatch.setattr(c.path if child == "clone" else c.move, "apply", forged)
    with pytest.raises(c.AddChargeEarlyError):
        c.apply(**inputs("one"))


@pytest.mark.parametrize("child", ("clone", "move"))
def test_null_child_cannot_invent_nested_helpers(child, monkeypatch):
    def forged(**kwargs):
        packet = (clone.independent if child == "clone" else move.independent)(kwargs)
        packet["allocation_packet" if child == "clone" else "free_packet"] = {}
        return packet

    monkeypatch.setattr(c.path if child == "clone" else c.move, "apply", forged)
    with pytest.raises(c.AddChargeEarlyError):
        c.apply(**inputs("null"))


@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "extra",
        "flags_bool",
        "gpr_bool",
        "stack_mutable",
        "error_mutable",
        "events_tuple",
        "read_missing",
        "stop_float",
        "mask_float",
        "protocol_bool",
        "protocol_int",
        "ret_early",
        "stop_early",
        "coordinated_stack",
        "coordinated_error",
    ),
)
@pytest.mark.parametrize("capacity", (1, 511))
def test_full_outer_free8_join_before_installed_transport(kind, capacity, monkeypatch):
    def forged(vector, initial, stack, error, *, stack_base):
        packet = free_law(vector, initial, stack, error, stack_base=stack_base)
        if kind == "missing":
            packet.pop("protocol")
        elif kind == "extra":
            packet["extra"] = 0
        elif kind == "flags_bool":
            packet["flags"] = bool(packet["flags"])
        elif kind == "gpr_bool":
            packet["registers"]["eax"] = True
        elif kind == "stack_mutable":
            packet["stack"] = bytearray(packet["stack"])
        elif kind == "error_mutable":
            packet["error"] = bytearray(packet["error"])
        elif kind == "events_tuple":
            packet["events"] = tuple(packet["events"])
        elif kind == "read_missing":
            packet["events"].pop()
        elif kind == "stop_float":
            packet["stop"] = float(packet["stop"])
        elif kind == "mask_float":
            packet["flag_mask"] = float(packet["flag_mask"])
        elif kind == "protocol_bool":
            packet["protocol"]["result"] = True
        elif kind == "protocol_int":
            packet["protocol"]["returned"] = 1
        elif kind == "ret_early":
            packet["events"][-1]["value"] = 0x00657765
        elif kind == "stop_early":
            packet["stop"] = 0x00657765
        elif kind == "coordinated_stack":
            packet["stack"] = bytes([packet["stack"][0] ^ 1]) + packet["stack"][1:]
            packet["events"][0]["value"] ^= 1
        else:
            packet["error"] = bytes([packet["error"][0] ^ 1]) + packet["error"][1:]
            packet["protocol"]["last_error"] = 0
        return packet

    monkeypatch.setattr(c.deallocator, "_expected", forged)
    with pytest.raises(c.AddChargeEarlyError, match="primitive differs"):
        c.apply(**inputs("empty_owned", capacity_count=capacity))


@pytest.mark.parametrize("capacity", (1, 3, 17, 511))
def test_outer_free_exact_actual_capacity_frame_and_canonical_word(
    capacity, monkeypatch
):
    packet = inputs("empty_owned", capacity_count=capacity)
    expected = independent(packet)
    calls = []

    def child(vector, initial, stack, error, *, stack_base):
        calls.append(copy.deepcopy((vector, initial, stack, error, stack_base)))
        assert vector == dict(
            pointer=0x20000FF9,
            count=capacity,
            stride=8,
            metadata=None,
            responses=[dict(kind="heap_free", eax=1)],
            heap=0x12345678,
        )
        strict_equal(initial, expected["boundaries"][-2]["registers"])
        result = free_law(vector, initial, stack, error, stack_base=stack_base)
        assert result["stop"] == result["events"][-1]["value"] == 0x04000000
        return result

    monkeypatch.setattr(c.deallocator, "_expected", child)
    check(c.apply(**packet), packet)
    assert len(calls) == 1


def test_installed_outer_free_ret_word_checked_after_full_canonical_join():
    packet = inputs("empty_owned")
    wanted = independent(packet)
    entry = wanted["boundaries"][-2]
    pages = dict(entry["pages"])
    g = packet["registers"]["esp"]
    store(pages, g - 40, 0x00657769)
    with pytest.raises(c.AddChargeEarlyError, match="installed continuation differs"):
        c._outer_free_law(
            entry["registers"], pages, 0x20000FF9, min((g - 72) & ~4095, 0xFFFFE000), 1
        )


def test_valid_nested_semantic_metadata_is_explicitly_trusted(monkeypatch):
    def child(**kwargs):
        packet = clone.independent(kwargs)
        packet["source_snapshot"] = (
            bytes([packet["source_snapshot"][0] ^ 1]) + packet["source_snapshot"][1:]
        )
        return packet

    monkeypatch.setattr(c.path, "apply", child)
    packet = inputs("one")
    wanted = independent(packet)
    wanted["child_packets"]["clone_argument"]["source_snapshot"] = (
        bytes([wanted["child_packets"]["clone_argument"]["source_snapshot"][0] ^ 1])
        + wanted["child_packets"]["clone_argument"]["source_snapshot"][1:]
    )
    strict_equal(c.apply(**packet), wanted)


@pytest.mark.parametrize("child", ("clone", "move", "free"))
def test_foreign_dependency_exceptions_are_normalized(child, monkeypatch):
    def failed(*args, **kwargs):
        raise RuntimeError("foreign child")

    monkeypatch.setattr(
        c.path if child == "clone" else c.move if child == "move" else c.deallocator,
        "_expected" if child == "free" else "apply",
        failed,
    )
    with pytest.raises(c.AddChargeEarlyError, match="foreign child"):
        c.apply(**inputs("empty_owned" if child == "free" else "one"))


@pytest.mark.parametrize("form", ("null", "empty_owned", "one"))
@pytest.mark.parametrize(
    "g,h,o,d",
    [
        (0x2E8, 0x10000FF9, 0x20000FF9, 0x06003FF8),
        (0x30000FFD, 0x10000FFF, 0x7FFFFFF9, 0x06001FFC),
        (0xFFFFFFEB, 0x10000200, 0x90000FF9, 0x06001007),
        (0x30001003, 0xFFFFFFF3, 0x20000FF9, 0x06001000),
        (0x80000000, 0x90000FFC, 0x20000FF9, 0x06003FF8),
    ],
)
def test_crossing_signed_last_bounds_and_logical_returns(form, g, h, o, d):
    packet = inputs(
        form,
        frame=g,
        receiver=h,
        source=o,
        allocation=d,
        capacity_count=511,
        return_address=0xFFFFFFFF,
    )
    check(c.apply(**packet), packet)


def test_actual_api_pins_and_no_fixture_or_native_execution():
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
    assert c.ANALYSIS_KIND == "pe_native_movement_addcharge_early_semantics"
    assert c.BODY_PINS[0x2576F0] == (
        138,
        "b4c477b2c8b460c7697bdb236c50c264cbacb68e55189048fc4b536847a6e90a",
    )
    assert c.SOURCE_PINS["clone2_conformance"] == (
        "pe_native_movement_path_clone2_conformance",
        "1cddf384c45fb50a60752656acd2560a7e243dd20f0d68b8a963a4a7bb3a739b",
    )


@pytest.mark.parametrize("bit", [b for b in range(32) if not (0xAD7 >> b) & 1])
def test_each_control_reserved_bit_rejected_before_children(bit, monkeypatch):
    packet = inputs(flags=0x246 | (1 << bit))
    calls = []

    def child(*args, **kwargs):
        calls.append("child")
        raise AssertionError("forbidden flag reached child")

    monkeypatch.setattr(c.path, "apply", child)
    monkeypatch.setattr(c.move, "apply", child)
    with pytest.raises(c.AddChargeEarlyError):
        c.apply(**packet)
    assert calls == []


def test_flags_corpus_exact128_status_if_words_required_bit1():
    assert len(FLAGS) == len(set(FLAGS)) == 128
    assert all(v & 2 and not v & ~0xAD7 for v in FLAGS)
    assert {2, 6, 0x202, 0x246, 0x256, 0xAD7}.issubset(FLAGS)
