"""Independent selected AddMove owner law composed from handwritten child tests.

No production apply or packet helper supplies expected results. Child test laws
are independently handwritten witnesses; the parent closes typed envelopes and
trusts their valid nested semantics, rather than proving all coordinated forgeries.
"""

from __future__ import annotations
import ast
import copy
import inspect
from collections import UserDict
import pytest
from src.observatory import native_movement_addmove_normal_semantics as c
from tests import (
    test_itb_native_movement_effect_record_default_semantics as constructor,
)
from tests import test_itb_native_movement_path_assign2_semantics as assignment
from tests import test_itb_native_movement_effect_record_copy2_semantics as record
from tests import test_itb_native_movement_effect_record_append2_semantics as append
from tests import test_itb_native_movement_effect_record_destroy_semantics as destructor
from tests.test_itb_native_movement_empty_string_copy_semantics import (
    store,
    read_bytes,
    assert_strict_packet as equal,
)

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
BITS = (0, 2, 4, 6, 7, 9, 11)
FLAGS = tuple(
    2 | sum(1 << bit for i, bit in enumerate(BITS) if n >> i & 1) for n in range(128)
)
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
STATES = (
    "default",
    "assignment",
    "record_copy",
    "append",
    "destroy_temp",
    "destroy_original",
    "free_caller",
    "cookie",
)
OWNER = tuple(
    tuple(int(w, 16) for w in line.split())
    for line in (
        "257340 257341 257343 257345 25734a 257350 257351 257357 25735c 25735e 257361 257362 257363 257364 257367 25736d 25736f 257376 257379 25737c 25737e 257381 257384 25738a 25738c 257392",
        "257397 25739a 25739e 25739f 2573a2",
        "2573a7 2573ac 2573b2 2573b3 2573b9 2573be",
        "2573c3 2573c9 2573cd 2573ce 2573d0",
        "2573d5 2573db",
        "2573e0 2573e6 2573e8",
        "2573ed 2573f0 2573f2 2573f4 2573f7 2573f9 2573fb 2573fe 2573ff 257400",
        "257405 257408 25740a 25740d 257414 257415 257416 257417 25741a 25741c",
        "257421 257423 257424",
    )
)
FREE_TRACE = tuple(
    int(w, 16)
    for w in "7800 7801 7803 7806 7809 780b 780e 7810 7816 781a 7820 784d 7850 7851 35785d 36fb17 389156 389158 389159 38915b 38915f 389161 389164 389166 38916c 389172 389174 38918e 38918f 7856 7859 785a".split()
)


def word(pages, at):
    return int.from_bytes(read_bytes(pages, at, 4), "little")


def inputs(
    *,
    frame=0x30001000,
    receiver=0x10000100,
    insertion=0x10002FF0,
    source=0x06002FF9,
    allocations=(0x06001103, 0x06002003, 0x06003033),
    profile=0,
    parameter=0xBF800000,
    flags=0x246,
    return_address=0x04000000,
    previous=2,
    spare=2,
):
    begin, capacity = insertion - previous * 308, insertion + spare * 308
    ranges = [
        (frame - 0x338, frame + 20),
        (receiver, receiver + 12),
        (begin, capacity),
        (source, source + 16),
        (0, 4),
        (0x00893F28, 0x00893F2C),
        (0x0080DFDC, 0x0080DFDD),
        (0x06000000, 0x06004000),
        (0x008B7000, 0x008B8000),
        (0x007D6000, 0x007D7000),
    ]
    for delta in (0x2F0, 0x310, 0x338, 0x2C4, 0x2B8):
        base = min((frame - delta) & ~4095, 0xFFFFE000)
        ranges.append((base, base + 8192))
    bases = {
        p
        for start, end in ranges
        for p in range(start & ~4095, ((end - 1) & ~4095) + 1, 4096)
    } | {0x12340000}
    pages = {
        p: bytes((i * 37 + j * 29 + profile * 79) & 255 for j in range(4096))
        for i, p in enumerate(sorted(bases))
    }
    for at, v in (
        (frame, return_address),
        (frame + 4, source),
        (frame + 8, source + 16),
        (frame + 12, source + 16),
        (frame + 16, parameter),
        (receiver, begin),
        (receiver + 4, insertion),
        (receiver + 8, capacity),
        (0, 0x1234ABCD ^ profile),
        (0x00893F28, 0x19A51C73 ^ (profile * 0x7654321)),
        (0x008B7634, 0x12345678),
        (0x007D6220, 0x05000000),
        (0x007D621C, 0x05000000),
    ):
        store(pages, at, v)
    store(pages, 0x0080DFDC, 0, 1)
    for i, v in enumerate((0xD15C0016, 0xFFFFFFFF, 0x80000000, 0x8765DD16)):
        store(pages, source + 4 * i, v ^ ((profile * 0x7654321) & 0xFFFFFFFF))
    regs = {
        n: (0x12345678 + i * 0x11111111 + profile * 0x4321) & 0xFFFFFFFF
        for i, n in enumerate(GPR)
    }
    regs.update(esp=frame, ecx=receiver)
    xmm = {
        n: int.from_bytes(
            bytes((i * 31 + j * 19 + profile * 67) & 255 for j in range(16)), "little"
        )
        for i, n in enumerate(XMM)
    }
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmm,
        return_address=return_address,
        entry_flags=flags,
        allocation_results=list(allocations),
    )


def logical_test_flags(value):
    return (
        (4 if (value & 255).bit_count() % 2 == 0 else 0)
        | (0x40 if value == 0 else 0)
        | (0x80 if value & 0x80000000 else 0)
    )


def independent(packet):
    """Actual selected parent: manual scalar transitions, handwritten child laws."""
    initial = packet["registers"]
    g, h = initial["esp"], initial["ecx"]
    a, b, d = packet["allocation_results"]
    source = word(packet["pages"], g + 4)
    insertion = word(packet["pages"], h + 4)
    parameter = word(packet["pages"], g + 16)
    first, second = g - 0x148, g - 0x27C
    cookie, seh = word(packet["pages"], 0x00893F28), word(packet["pages"], 0)
    pages = dict(packet["pages"])
    regs, vec = dict(initial), dict(packet["xmm"])
    events, trace, states, imports, children = [], [], [], [], {}

    def access(kind, at, value, width=4):
        if kind == "write":
            store(pages, at, value, width)
        else:
            assert int.from_bytes(read_bytes(pages, at, width), "little") == value
        events.append(dict(access=kind, address=at, width=width, value=value))

    def capture(name, phase, endpoint, flags, mask=0x8D5):
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

    def take(name, law, segment, entry, ret, flags, **extra):
        nonlocal pages, regs, vec
        trace.extend(f"0x{pc:08x}" for pc in OWNER[segment])
        capture(name, "entry", entry, flags)
        prefix = copy.deepcopy(events)
        fixture = dict(
            pages=dict(pages),
            registers=dict(regs),
            xmm=dict(vec),
            return_address=ret,
            entry_flags=(packet["entry_flags"] & ~0x8D5) | flags,
            **extra,
        )
        child = law(fixture)
        children[name] = copy.deepcopy(child)
        if child.get("imported") is not None:
            state = copy.deepcopy(child["imported"])
            state.update(name=name, events=prefix + state["events"])
            imports.append(state)
        if name in ("record_copy", "append"):
            rc = child if name == "record_copy" else child["record_packet"]
            path = rc["path_packet"]
            lead = [] if name == "record_copy" else child["boundaries"][0]["events"]
            state = copy.deepcopy(path["imported"])
            state.update(
                name=name,
                events=prefix
                + copy.deepcopy(lead)
                + copy.deepcopy(rc["boundaries"][10]["events"])
                + state["events"],
            )
            imports.append(state)
        trace.extend(child["trace_rvas"])
        events.extend(copy.deepcopy(child["events"]))
        pages, regs, vec = (
            dict(child["pages"]),
            dict(child["registers"]),
            dict(child["xmm"]),
        )
        capture(name, "return", ret, child["flags"], child["flag_mask"])
        return child

    for kind, at, v in (
        ("write", g - 4, initial["ebp"]),
        ("write", g - 8, 0xFFFFFFFF),
        ("write", g - 12, 0x007CA95E),
        ("read", 0, seh),
        ("write", g - 16, seh),
        ("read", 0x00893F28, cookie),
        ("write", g - 20, cookie ^ (g - 4)),
        ("write", g - 0x280, initial["ebx"]),
        ("write", g - 0x284, initial["esi"]),
        ("write", g - 0x288, cookie ^ (g - 4)),
        ("write", 0, g - 16),
        ("write", g - 8, 0),
        ("read", g + 8, source + 16),
        ("read", g + 4, source),
        ("write", g - 0x28C, 0),
        ("write", g - 0x290, 0x00657397),
    ):
        access(kind, at, v)
    regs.update(eax=2, ecx=first, edx=source, esi=h, ebp=g - 4, esp=g - 0x290)
    child = take(
        "default", constructor.independent_packet, 0, 0x005999A0, 0x00657397, 0
    )
    access("write", g - 8, 1, 1)
    access("write", g - 0x28C, g + 4)
    access("write", g - 0x290, 0x006573A7)
    regs.update(eax=g + 4, ecx=first + 0xCC, esp=g - 0x290)
    child = take(
        "assignment",
        assignment.independent,
        1,
        0x004C5BB0,
        0x006573A7,
        child["flags"],
        allocation_result=a,
    )
    access("read", g + 16, parameter)
    vec["xmm0"] = parameter
    access("write", g - 0x28C, first)
    access("write", first + 0xC8, parameter)
    access("write", g - 0x290, 0x006573C3)
    regs.update(eax=first, ecx=second, esp=g - 0x290)
    child = take(
        "record_copy",
        record.independent,
        2,
        0x0055B9B0,
        0x006573C3,
        child["flags"],
        allocation_result=b,
    )
    access("write", g - 8, 2, 1)
    access("write", g - 0x28C, second)
    access("write", g - 0x290, 0x006573D5)
    regs.update(eax=second, ecx=h, esp=g - 0x290)
    child = take(
        "append",
        append.independent,
        3,
        0x00659F00,
        0x006573D5,
        child["flags"],
        allocation_result=d,
    )
    access("write", g - 0x28C, 0x006573E0)
    regs.update(ecx=second, esp=g - 0x28C)
    child = take(
        "destroy_temp",
        destructor.independent,
        4,
        0x0050E2A0,
        0x006573E0,
        child["flags"],
    )
    access("write", g - 0x28C, 0x006573ED)
    regs.update(ecx=first, ebx=(regs["ebx"] & 0xFFFFFF00) | 1, esp=g - 0x28C)
    child = take(
        "destroy_original",
        destructor.independent,
        5,
        0x0050E2A0,
        0x006573ED,
        child["flags"],
    )
    access("read", g + 4, source)
    access("read", g + 12, source + 16)
    for at, v in (
        (g - 0x28C, 8),
        (g - 0x290, 2),
        (g - 0x294, source),
        (g - 0x298, 0x00657405),
    ):
        access("write", at, v)
    regs.update(ecx=2, edx=source, esp=g - 0x298)
    trace.extend(f"0x{pc:08x}" for pc in OWNER[6])
    capture("free_caller", "entry", 0x00407800, 0, 0xC5)
    before = copy.deepcopy(events)
    v = regs["esp"]
    base = min((g - 0x2B8) & ~4095, 0xFFFFE000)
    free = destructor.free_law(
        dict(
            pointer=source,
            count=2,
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
    assert word(pages, v) == 0x00657405
    free["events"][-1]["value"] = 0x00657405
    free["stop"] = 0x00657405
    children["free_caller"] = copy.deepcopy(free)
    imported_pages = dict(pages)
    for row in free["events"][:16]:
        if row["access"] == "write":
            store(imported_pages, row["address"], row["value"])
    imports.append(
        dict(
            name="free_caller",
            registers=dict(
                regs, eax=0x1FFFFFFF, ecx=source, edx=7, ebp=v - 16, esp=v - 32
            ),
            xmm=dict(vec),
            pages=imported_pages,
            events=before + copy.deepcopy(free["events"][:16]),
            flags=logical_test_flags(source),
            flag_mask=0x8C5,
            df=0,
            endpoint=0x05000000,
            entry_esp=v - 32,
            words=[0x00789172, 0x12345678, 0, source],
        )
    )
    events.extend(copy.deepcopy(free["events"]))
    pages[base] = free["stack"][:4096]
    pages[base + 4096] = free["stack"][4096:]
    regs = dict(free["registers"])
    trace.extend(f"0x{pc:08x}" for pc in FREE_TRACE)
    capture("free_caller", "return", 0x00657405, free["flags"])
    regs["esp"] += 12
    regs["eax"] = (regs["eax"] & 0xFFFFFF00) | 1
    for kind, at, v in (
        ("read", g - 16, seh),
        ("write", 0, seh),
        ("read", g - 0x288, cookie ^ (g - 4)),
        ("read", g - 0x284, initial["esi"]),
        ("read", g - 0x280, initial["ebx"]),
        ("read", g - 20, cookie ^ (g - 4)),
        ("write", g - 0x280, 0x00657421),
    ):
        access(kind, at, v)
    regs.update(ecx=cookie, ebx=initial["ebx"], esi=initial["esi"], esp=g - 0x280)
    trace.extend(f"0x{pc:08x}" for pc in OWNER[7])
    capture("cookie", "entry", 0x007574CA, logical_test_flags(cookie), 0x8C5)
    access("read", 0x00893F28, cookie)
    access("read", g - 0x280, 0x00657421)
    trace.extend(("0x003574ca", "0x003574d0", "0x003574d3"))
    regs["esp"] = g - 0x27C
    capture("cookie", "return", 0x00657421, 0x44)
    access("read", g - 4, initial["ebp"])
    access("read", g, packet["return_address"])
    trace.extend(f"0x{pc:08x}" for pc in OWNER[8])
    return dict(
        geometry=dict(
            entry=g,
            receiver=h,
            source_path=source,
            original_record=first,
            temporary_record=second,
            new_record=insertion,
        ),
        path=dict(
            begin=source,
            end=source + 16,
            capacity=source + 16,
            parameter_bits=parameter,
        ),
        registers=dict(initial, eax=1, ecx=cookie, edx=0xB0000001, esp=g + 20),
        xmm=vec,
        pages=pages,
        events=events,
        trace_rvas=trace,
        boundaries=states,
        imports=imports,
        child_packets=children,
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=packet["return_address"],
    )


def check(actual, packet):
    expected = independent(packet)
    assert type(actual) is dict and set(actual) == KEYS
    equal(actual, expected)
    assert len(actual["trace_rvas"]) == 2089 and len(actual["events"]) == 1293
    assert len(actual["boundaries"]) == 16 and len(actual["imports"]) == 6
    assert [(s["name"], s["phase"]) for s in actual["boundaries"]] == [
        (n, p) for n in STATES for p in ("entry", "return")
    ]
    assert [s["name"] for s in actual["imports"]] == [
        "assignment",
        "record_copy",
        "append",
        "destroy_temp",
        "destroy_original",
        "free_caller",
    ]
    assert [s["words"] for s in actual["imports"]] == [
        [0x00789463, 0x12345678, 0, 16]
    ] * 3 + [
        [0x00789172, 0x12345678, 0, packet["allocation_results"][1]],
        [0x00789172, 0x12345678, 0, packet["allocation_results"][0]],
        [
            0x00789172,
            0x12345678,
            0,
            word(packet["pages"], packet["registers"]["esp"] + 4),
        ],
    ]
    g, h = packet["registers"]["esp"], packet["registers"]["ecx"]
    new = word(packet["pages"], h + 4)
    source = word(packet["pages"], g + 4)
    assert word(actual["pages"], h) == word(packet["pages"], h)
    assert word(actual["pages"], h + 4) == new + 308
    assert word(actual["pages"], h + 8) == word(packet["pages"], h + 8)
    assert word(actual["pages"], new + 0xC8) == word(packet["pages"], g + 16)
    assert (
        word(actual["pages"], new + 0xD8) == 0 and word(actual["pages"], new + 12) == 4
    )
    assert [word(actual["pages"], new + off) for off in (0xCC, 0xD0, 0xD4)] == [
        packet["allocation_results"][2],
        packet["allocation_results"][2] + 16,
        packet["allocation_results"][2] + 16,
    ]
    assert read_bytes(
        actual["pages"], packet["allocation_results"][2], 16
    ) == read_bytes(packet["pages"], source, 16)
    assert read_bytes(actual["pages"], source, 16) == read_bytes(
        packet["pages"], source, 16
    )
    assert read_bytes(actual["pages"], g, 20) == read_bytes(packet["pages"], g, 20)
    assert actual["xmm"]["xmm0"] == word(packet["pages"], g + 16)
    assert all(actual["xmm"][n] == packet["xmm"][n] for n in XMM[1:])
    assert actual["pages"][0x12340000] == packet["pages"][0x12340000]
    for local in (g - 0x148, g - 0x27C):
        assert read_bytes(actual["pages"], local + 0xCC, 12) == bytes(12)
    for i in (0, 1):
        assert read_bytes(
            actual["pages"], packet["allocation_results"][i], 16
        ) == read_bytes(packet["pages"], source, 16)
    for event in actual["events"]:
        assert event["width"] in (1, 2, 4)
    return expected


@pytest.mark.parametrize("a", range(16))
@pytest.mark.parametrize("profile", range(3))
def test_all48_alignment_profiles_complete_owner_and_children(a, profile):
    packet = inputs(
        frame=0x30001000 + a,
        receiver=0x10000100 + a,
        insertion=0x10002FF0 + a,
        source=0x06002FF9 + a,
        allocations=(0x06001103 + a, 0x06002003 + a, 0x06003033 + a),
        profile=profile,
        parameter=(0xBF800000, 0x7FC01234, 0xFF800000)[profile],
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("flags", FLAGS)
def test_all128_ordinary_entry_flags(flags):
    packet = inputs(flags=flags)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "parameter",
    (0, 1, 0x80000000, 0x7FFFFFFF, 0xFFFFFFFF, 0x7F800001, 0x7FA12345, 0x00000001),
)
def test_parameter_raw32_and_legacy_movss_zero_upper96(parameter):
    packet = inputs(parameter=parameter)
    packet["xmm"]["xmm0"] = (1 << 128) - 1
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["xmm"]["xmm0"] == parameter
    assert actual["child_packets"]["default"]["xmm"]["xmm0"] == (1 << 128) - 1
    assert actual["child_packets"]["assignment"]["xmm"]["xmm0"] == (1 << 128) - 1
    assert actual["child_packets"]["record_copy"]["xmm"]["xmm0"] == parameter


@pytest.mark.parametrize(
    "g,h,new,o,ret",
    (
        (0x02000103, 0x10000FF9, 0x01000FF0, 0x06002FF9, 0x04000003),
        (0x80000010, 0x10000100, 0x20000FFB, 0x06002801, 0x006EB205),
        (0xFFFFFFE0, 0x10000100, 0x20000FF0, 0xFFFFEFF0, 0x04000000),
        (0x30000088, 0x20000FF9, 0x10000FF0, 0x80000FF9, 0x04000107),
        (0x10000103, 0x20000100, 0x02000FF0, 0x06003FE0, 0x04000003),
    ),
)
def test_arbitrary_actual_frames_headers_crossings_sources_and_returns(
    g, h, new, o, ret
):
    packet = inputs(frame=g, receiver=h, insertion=new, source=o, return_address=ret)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "allocations",
    (
        (0x06001103, 0x06001113, 0x06001123),
        (0x06003FD0, 0x06003FE0, 0x06003FF0),
    ),
)
def test_disjoint_allocation_adjacency_and_exact_data_window_end(allocations):
    packet = inputs(allocations=allocations)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("which", ("source_ancestor", "header_ancestor"))
def test_actual_same_stack_page_data_beyond_parent_protected_end(which):
    packet = (
        inputs(source=0x30001014)
        if which == "source_ancestor"
        else inputs(receiver=0x30001014)
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("value", (0, 0xFFFFFFFF, 0x80000000, 1))
def test_arbitrary_preserved_nonaddress_gpr_xmm_cookie_seh(value):
    packet = inputs()
    for n in GPR:
        if n not in ("ecx", "esp"):
            packet["registers"][n] = value
    for i, n in enumerate(XMM):
        packet["xmm"][n] = ((value << 96) | (value << 64) | (value << 32) | value) ^ i
    store(packet["pages"], 0, value)
    store(packet["pages"], 0x00893F28, value)
    check(c.apply(**packet), packet)


def test_outputs_are_recursively_detached_from_inputs_and_each_other():
    packet = inputs()
    before = copy.deepcopy(packet)
    actual = c.apply(**packet)
    expected = independent(packet)
    packet["registers"]["eax"] ^= 1
    packet["xmm"]["xmm7"] ^= 1
    store(packet["pages"], 0x12340000, 0)
    packet["allocation_results"][0] ^= 1
    equal(actual, expected)
    actual["child_packets"]["record_copy"]["registers"]["eax"] ^= 1
    actual["child_packets"]["record_copy"]["path_packet"]["events"][0]["value"] ^= 1
    actual["boundaries"][0]["registers"]["eax"] ^= 1
    actual["imports"][0]["registers"]["eax"] ^= 1
    equal(actual["registers"], expected["registers"])
    equal(actual["events"], expected["events"])
    equal(c.apply(**before), expected)


@pytest.mark.parametrize(
    "field,value",
    (
        ("return_address", True),
        ("return_address", -1),
        ("return_address", 1 << 32),
        ("entry_flags", True),
        ("entry_flags", -1),
        ("entry_flags", 1 << 32),
        ("entry_flags", 0),
        ("entry_flags", 4),
        ("entry_flags", 0x646),
        ("allocation_results", ()),
        ("allocation_results", [0x6001000] * 2),
        ("allocation_results", [True, 0x6002000, 0x6003000]),
        ("allocation_results", [0x5FFFFFF, 0x6002000, 0x6003000]),
        ("allocation_results", [0x6003FF1, 0x6002000, 0x6003000]),
    ),
)
def test_strict_keyword_word_and_result_list_domains(field, value):
    packet = inputs()
    packet[field] = value
    with pytest.raises(c.AddMoveNormalError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "bit", (3, 5, 8, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 31)
)
def test_unknown_reserved_control_rf_and_df_flags_rejected(bit):
    packet = inputs(flags=0x246 | (1 << bit))
    with pytest.raises(c.AddMoveNormalError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "group,name,value",
    (
        ("registers", "eax", True),
        ("registers", "eax", -1),
        ("registers", "edx", 1 << 32),
        ("registers", "ebp", 0.0),
        ("xmm", "xmm1", True),
        ("xmm", "xmm4", -1),
        ("xmm", "xmm7", 1 << 128),
        ("xmm", "xmm2", 0.0),
    ),
)
def test_exact_all8_gpr_xmm_value_domains(group, name, value):
    packet = inputs()
    packet[group][name] = value
    with pytest.raises(c.AddMoveNormalError):
        c.apply(**packet)


@pytest.mark.parametrize("group", ("registers", "xmm"))
@pytest.mark.parametrize("kind", ("missing", "extra", "mapping", "key_alias"))
def test_closed_typed_input_state_maps(group, kind):
    packet = inputs()
    state = packet[group]
    if kind == "missing":
        state.pop(next(iter(state)))
    elif kind == "extra":
        state["other"] = 0
    elif kind == "mapping":
        packet[group] = UserDict(state)
    else:

        class Alias(str):
            pass

        name = next(iter(state))
        value = state.pop(name)
        state[Alias(name)] = value
    with pytest.raises(c.AddMoveNormalError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind", ("empty", "mapping", "mutable", "short", "unaligned", "boolkey", "wrap")
)
def test_immutable_full_complete_typed_pages(kind):
    packet = inputs()
    page = next(iter(packet["pages"]))
    if kind == "empty":
        packet["pages"] = {}
    elif kind == "mapping":
        packet["pages"] = UserDict(packet["pages"])
    elif kind == "mutable":
        packet["pages"][page] = bytearray(packet["pages"][page])
    elif kind == "short":
        packet["pages"][page] = packet["pages"][page][:-1]
    elif kind == "unaligned":
        packet["pages"][page + 1] = packet["pages"][page]
    elif kind == "boolkey":
        packet["pages"][False] = packet["pages"].pop(0)
    else:
        packet["pages"][1 << 32] = bytes(4096)
    with pytest.raises(c.AddMoveNormalError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    (
        "caller_return",
        "caller_count",
        "caller_capacity",
        "source_null",
        "source_wrap",
        "receiver_null",
        "receiver_order",
        "receiver_stride",
        "receiver_full",
        "duplicate_alloc",
        "alloc_overlap",
        "source_alloc_overlap",
        "receiver_alloc_overlap",
        "frame_alloc_overlap",
        "header_frame",
        "source_frame",
        "record_frame",
        "literal",
        "heap",
        "alloc_iat",
        "free_iat",
        "missing_stack",
        "missing_data",
        "code_page",
        "return_frame",
        "return_record",
        "return_global",
        "return_code",
        "low_frame",
        "frame_wrap",
        "header_wrap",
    ),
)
def test_closed_selected_geometry_runtime_and_installed_caller_domains(kind):
    packet = inputs()
    g, h = packet["registers"]["esp"], packet["registers"]["ecx"]
    source = word(packet["pages"], g + 4)
    new = word(packet["pages"], h + 4)
    if kind == "caller_return":
        store(packet["pages"], g, 0x4000001)
    elif kind == "caller_count":
        store(packet["pages"], g + 8, source + 8)
    elif kind == "caller_capacity":
        store(packet["pages"], g + 12, source + 24)
    elif kind == "source_null":
        store(packet["pages"], g + 4, 0)
    elif kind == "source_wrap":
        store(packet["pages"], g + 4, 0xFFFFFFF8)
    elif kind == "receiver_null":
        store(packet["pages"], h, 0)
    elif kind == "receiver_order":
        store(packet["pages"], h, new + 1)
    elif kind == "receiver_stride":
        store(packet["pages"], h, new - 1)
    elif kind == "receiver_full":
        store(packet["pages"], h + 8, new)
    elif kind == "duplicate_alloc":
        packet["allocation_results"][1] = packet["allocation_results"][0]
    elif kind == "alloc_overlap":
        packet["allocation_results"][1] = packet["allocation_results"][0] + 15
    elif kind == "source_alloc_overlap":
        packet["allocation_results"][0] = source
    elif kind == "receiver_alloc_overlap":
        packet = inputs(insertion=0x06001103, previous=0)
    elif kind == "frame_alloc_overlap":
        packet = inputs(frame=0x06001280)
    elif kind == "header_frame":
        packet["registers"]["ecx"] = g - 32
    elif kind == "source_frame":
        for off in (4, 8, 12):
            store(packet["pages"], g + off, g - 32 + (0 if off == 4 else 16))
    elif kind == "record_frame":
        for off, v in ((0, g - 0x148), (4, g - 0x148), (8, g - 0x148 + 616)):
            store(packet["pages"], h + off, v)
    elif kind == "literal":
        store(packet["pages"], 0x0080DFDC, 1, 1)
    elif kind in ("heap", "alloc_iat", "free_iat"):
        store(
            packet["pages"],
            {"heap": 0x008B7634, "alloc_iat": 0x007D6220, "free_iat": 0x007D621C}[kind],
            1,
        )
    elif kind == "missing_stack":
        packet["pages"].pop(0x30000000)
    elif kind == "missing_data":
        packet["pages"].pop(0x06001000)
    elif kind == "code_page":
        packet["pages"][0x00657000] = bytes(4096)
    elif kind.startswith("return_"):
        ret = {
            "return_frame": g - 1,
            "return_record": new + 1,
            "return_global": 0x00893F28,
            "return_code": 0x00657340,
        }[kind]
        packet["return_address"] = ret
        store(packet["pages"], g, ret)
    elif kind == "low_frame":
        packet["registers"]["esp"] = 0x337
    elif kind == "frame_wrap":
        packet["registers"]["esp"] = 0xFFFFFFF0
    else:
        packet["registers"]["ecx"] = 0xFFFFFFF8
    with pytest.raises(c.AddMoveNormalError):
        c.apply(**packet)


COMMON_FORGERIES = (
    "missing",
    "extra",
    "gpr_bool",
    "gpr_wrap",
    "gpr_missing",
    "gpr_alias",
    "xmm_bool",
    "xmm_wrap",
    "xmm_extra",
    "pages_mutable",
    "pages_missing",
    "pages_extra",
    "event_access",
    "event_bool",
    "event_width",
    "event_width3",
    "event_width8",
    "event_wrap",
    "event_value",
    "event_extra",
    "trace_case",
    "trace_type",
    "trace_wrap",
    "flag_bool",
    "flag_mask_bool",
    "flag_outside_mask",
    "df_bool",
    "endpoint_bool",
    "endpoint_other",
)


def corrupt_common(child, kind):
    if kind == "missing":
        child.pop("flags")
    elif kind == "extra":
        child["extra"] = 0
    elif kind == "gpr_bool":
        child["registers"]["eax"] = True
    elif kind == "gpr_wrap":
        child["registers"]["eax"] = 1 << 32
    elif kind == "gpr_missing":
        child["registers"].pop("ebx")
    elif kind == "gpr_alias":

        class Alias(str):
            pass

        child["registers"][Alias("eax")] = child["registers"].pop("eax")
    elif kind == "xmm_bool":
        child["xmm"]["xmm1"] = True
    elif kind == "xmm_wrap":
        child["xmm"]["xmm3"] = 1 << 128
    elif kind == "xmm_extra":
        child["xmm"]["extra"] = 0
    elif kind == "pages_mutable":
        child["pages"][0] = bytearray(child["pages"][0])
    elif kind == "pages_missing":
        child["pages"].pop(0x12340000)
    elif kind == "pages_extra":
        child["pages"][0x12341000] = bytes(4096)
    elif kind.startswith("event_"):
        event = child["events"][0]
        if kind == "event_access":
            event["access"] = "execute"
        elif kind == "event_bool":
            event["address"] = True
        elif kind == "event_width":
            event["width"] = True
        elif kind == "event_width3":
            event["width"] = 3
        elif kind == "event_width8":
            event["width"] = 8
        elif kind == "event_wrap":
            event.update(address=0xFFFFFFFF, width=4)
        elif kind == "event_value":
            event["value"] = 1 << (8 * event["width"])
        else:
            event["extra"] = 0
    elif kind == "trace_case":
        child["trace_rvas"][0] = "0x0000ABCD"
    elif kind == "trace_type":
        child["trace_rvas"][0] = 0
    elif kind == "trace_wrap":
        child["trace_rvas"][0] = "0x100000000"
    elif kind == "flag_bool":
        child["flags"] = True
    elif kind == "flag_mask_bool":
        child["flag_mask"] = True
    elif kind == "flag_outside_mask":
        child["flags"] = 0x20
    elif kind == "df_bool":
        child["df"] = False
    elif kind == "endpoint_bool":
        child["endpoint"] = True
    else:
        child["endpoint"] ^= 1


@pytest.mark.parametrize("module", ("default", "assign", "record", "append", "destroy"))
@pytest.mark.parametrize("kind", COMMON_FORGERIES)
def test_all_trusted_child_common_envelopes_closed_before_adoption(
    monkeypatch, module, kind
):
    dependency = getattr(c, module)
    real = dependency.apply

    def forged(**kw):
        child = copy.deepcopy(real(**kw))
        corrupt_common(child, kind)
        return child

    monkeypatch.setattr(dependency, "apply", forged)
    with pytest.raises(c.AddMoveNormalError):
        c.apply(**inputs())


@pytest.mark.parametrize(
    "kind",
    (
        "keys",
        "eax_bool",
        "ecx",
        "flags",
        "mask",
        "stack",
        "error",
        "stop",
        "protocol",
        "event",
        "event_bool",
        "coordinated_pointer",
    ),
)
def test_full8_caller_free_packet_is_independently_checked_before_ret_rebind(
    monkeypatch, kind
):
    packet = inputs()
    caller_entry = packet["registers"]["esp"] - 0x298
    real = c.deallocator._expected

    def forged(*args, **kw):
        child = copy.deepcopy(real(*args, **kw))
        if args[1]["esp"] != caller_entry:
            return child
        if kind == "keys":
            child["extra"] = 0
        elif kind == "eax_bool":
            child["registers"]["eax"] = True
        elif kind == "ecx":
            child["registers"]["ecx"] ^= 1
        elif kind == "flags":
            child["flags"] ^= 1
        elif kind == "mask":
            child["flag_mask"] ^= 1
        elif kind == "stack":
            child["stack"] = bytes([child["stack"][0] ^ 1]) + child["stack"][1:]
        elif kind == "error":
            child["error"] = bytes([child["error"][0] ^ 1]) + child["error"][1:]
        elif kind == "stop":
            child["stop"] = 0x00657405
        elif kind == "protocol":
            child["protocol"]["result"] = True
        elif kind == "event":
            child["events"][-1]["value"] = 0x00657405
        elif kind == "event_bool":
            child["events"][0]["width"] = True
        else:
            for event in child["events"]:
                if event["value"] == args[0]["pointer"]:
                    event["value"] ^= 1
        return child

    monkeypatch.setattr(c.deallocator, "_expected", forged)
    with pytest.raises(c.AddMoveNormalError):
        c.apply(**inputs())


def test_free_actual_frame_actual_stack_and_full_closed_response_protocol(monkeypatch):
    packet = inputs()
    real = c.deallocator._expected
    seen = []

    def checked(vector, registers, stack, error, **kw):
        seen.append(copy.deepcopy((vector, registers, stack, error, kw)))
        return real(vector, registers, stack, error, **kw)

    monkeypatch.setattr(c.deallocator, "_expected", checked)
    actual = c.apply(**packet)
    check(actual, packet)
    g = packet["registers"]["esp"]
    assert len(seen) == 3
    for index, (vector, regs, stack, error, kw) in enumerate(seen):
        assert set(vector) == {
            "pointer",
            "count",
            "stride",
            "metadata",
            "responses",
            "heap",
        }
        assert vector["responses"] == [dict(kind="heap_free", eax=1)]
        assert (
            vector["count"] == 2
            and vector["stride"] == 8
            and vector["metadata"] is None
        )
        assert len(stack) == 8192 and len(error) == 4096
        assert kw == dict(stack_base=min((regs["esp"] - 32) & ~4095, 0xFFFFE000))
    assert seen[-1][1]["esp"] == g - 0x298
    assert seen[-1][0]["pointer"] == word(packet["pages"], g + 4)


@pytest.mark.parametrize("module", ("default", "assign", "record", "append", "destroy"))
def test_foreign_trusted_child_failure_is_normalized(monkeypatch, module):
    def failed(**kw):
        raise RuntimeError("independent child failure")

    monkeypatch.setattr(getattr(c, module), "apply", failed)
    with pytest.raises(c.AddMoveNormalError, match="independent child failure"):
        c.apply(**inputs())


def test_selected_source_shape_and_no_native_fixture_or_general_dispatch():
    tree = ast.parse(inspect.getsource(c))
    signature = inspect.signature(c.apply)
    assert tuple(signature.parameters) == (
        "pages",
        "registers",
        "xmm",
        "return_address",
        "entry_flags",
        "allocation_results",
    )
    assert all(
        p.kind is inspect.Parameter.KEYWORD_ONLY for p in signature.parameters.values()
    )
    assert not any(
        isinstance(node, ast.Import)
        and any(
            name.name.split(".")[0] in {"unicorn", "capstone", "subprocess"}
            for name in node.names
        )
        for node in ast.walk(tree)
    )
    assert len(OWNER) == 9 and sum(map(len, OWNER)) == 70
    assert len(FREE_TRACE) == 32


def test_receiver_above_actual_temporary_record_is_outside_external_append_domain():
    packet = inputs(frame=0x02000103, insertion=0x20000FF0)
    with pytest.raises(
        c.AddMoveNormalError, match="append source precedes receiver end"
    ):
        c.apply(**packet)
