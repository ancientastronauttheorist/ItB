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
from src.observatory import native_movement_addmove_small_normal_semantics as c
from tests import (
    test_itb_native_movement_effect_record_default_semantics as constructor,
)
from tests import test_itb_native_movement_path_small_assign_semantics as assignment
from tests import test_itb_native_movement_effect_record_small_copy_semantics as record
from tests import (
    test_itb_native_movement_effect_record_small_append_semantics as append,
)
from tests import (
    test_itb_native_movement_effect_record_small_destroy_semantics as destructor,
)
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
    count=2,
    capacity_count=None,
    *,
    frame=0x30001000,
    receiver=0x10000100,
    insertion=0x10002FF0,
    source=0x20000FF9,
    allocations=(0x06001000, 0x06002000, 0x06003000),
    profile=0,
    parameter=0xBF800000,
    flags=0x246,
    return_address=0x04000000,
    previous=2,
    spare=2,
):
    capacity_count = count if capacity_count is None else capacity_count
    begin, capacity = insertion - previous * 308, insertion + spare * 308
    ranges = [
        (frame - 0x338, frame + 20),
        (receiver, receiver + 12),
        (begin, capacity),
        (source, source + capacity_count * 8),
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
        (frame + 8, source + count * 8),
        (frame + 12, source + capacity_count * 8),
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
    for i in range(capacity_count * 2):
        store(
            pages,
            source + 4 * i,
            (0xD15C0016 + i * 0x13572469 + profile * 0x7654321) & 0xFFFFFFFF,
        )
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


def sub_flags(left, right):
    result = (left - right) & 0xFFFFFFFF
    return (
        int(left < right)
        | logical_test_flags(result)
        | ((left ^ right ^ result) & 16)
        | (0x800 if (left ^ right) & (left ^ result) & 0x80000000 else 0)
    )


def independent(packet):
    """Actual selected parent: manual scalar transitions, handwritten child laws."""
    initial = packet["registers"]
    g, h = initial["esp"], initial["ecx"]
    a, b, d = packet["allocation_results"]
    source = word(packet["pages"], g + 4)
    count = (word(packet["pages"], g + 8) - source) // 8
    capacity_count = (word(packet["pages"], g + 12) - source) // 8
    size = count * 8
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
        ("read", g + 8, source + size),
        ("read", g + 4, source),
        ("write", g - 0x28C, 0),
        ("write", g - 0x290, 0x00657397),
    ):
        access(kind, at, v)
    regs.update(eax=count, ecx=first, edx=source, esi=h, ebp=g - 4, esp=g - 0x290)
    child = take(
        "default",
        constructor.independent_packet,
        0,
        0x005999A0,
        0x00657397,
        sub_flags(count, 1),
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
    access("read", g + 12, source + capacity_count * 8)
    for at, v in (
        (g - 0x28C, 8),
        (g - 0x290, capacity_count),
        (g - 0x294, source),
        (g - 0x298, 0x00657405),
    ):
        access("write", at, v)
    regs.update(ecx=capacity_count, edx=source, esp=g - 0x298)
    trace.extend(f"0x{pc:08x}" for pc in OWNER[6])
    capture(
        "free_caller", "entry", 0x00407800, logical_test_flags(capacity_count), 0xC5
    )
    before = copy.deepcopy(events)
    v = regs["esp"]
    base = min((g - 0x2B8) & ~4095, 0xFFFFE000)
    free = destructor.free_law(
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
            end=source + size,
            capacity=source + capacity_count * 8,
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
    equal(actual, expected)
    assert type(actual) is dict and set(actual) == KEYS and len(actual) == 14
    g, h = packet["registers"]["esp"], packet["registers"]["ecx"]
    source = word(packet["pages"], g + 4)
    n = (word(packet["pages"], g + 8) - source) // 8
    k = (word(packet["pages"], g + 12) - source) // 8
    size = n * 8
    assert set(actual["path"]) == {"begin", "end", "capacity", "parameter_bits"}
    assert (
        len(actual["trace_rvas"]) == 2029 + 30 * n
        and len(actual["events"]) == 1269 + 12 * n
    )
    assert len(actual["boundaries"]) == 16 and len(actual["imports"]) == 6
    assert [(s["name"], s["phase"]) for s in actual["boundaries"]] == [
        (name, phase) for name in STATES for phase in ("entry", "return")
    ]
    assert [len(s["events"]) for s in actual["boundaries"]] == [
        16,
        233,
        236,
        318 + 4 * n,
        322 + 4 * n,
        686 + 8 * n,
        689 + 8 * n,
        1082 + 12 * n,
        1083 + 12 * n,
        1157 + 12 * n,
        1158 + 12 * n,
        1232 + 12 * n,
        1238 + 12 * n,
        1258 + 12 * n,
        1265 + 12 * n,
        1267 + 12 * n,
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
        [0x789463, 0x12345678, 0, size]
    ] * 3 + [
        [0x789172, 0x12345678, 0, packet["allocation_results"][i]] for i in (1, 0)
    ] + [
        [0x789172, 0x12345678, 0, source]
    ]
    new = word(packet["pages"], h + 4)
    assert word(actual["pages"], h) == word(packet["pages"], h)
    assert word(actual["pages"], h + 4) == new + 308 and word(
        actual["pages"], h + 8
    ) == word(packet["pages"], h + 8)
    assert word(actual["pages"], new + 0xC8) == word(packet["pages"], g + 16)
    assert (
        word(actual["pages"], new + 0xD8) == 0 and word(actual["pages"], new + 12) == 4
    )
    d = packet["allocation_results"][2]
    assert [word(actual["pages"], new + off) for off in (0xCC, 0xD0, 0xD4)] == [
        d,
        d + size,
        d + size,
    ]
    assert read_bytes(actual["pages"], source, k * 8) == read_bytes(
        packet["pages"], source, k * 8
    )
    for d in packet["allocation_results"]:
        assert read_bytes(actual["pages"], d, size) == read_bytes(
            packet["pages"], source, size
        )
    assert read_bytes(actual["pages"], g, 20) == read_bytes(packet["pages"], g, 20)
    assert actual["xmm"]["xmm0"] == word(packet["pages"], g + 16) and all(
        actual["xmm"][x] == packet["xmm"][x] for x in XMM[1:]
    )
    for local in (g - 0x148, g - 0x27C):
        assert read_bytes(actual["pages"], local + 0xCC, 12) == bytes(12)
    assert (
        actual["boundaries"][12]["registers"]["ecx"] == k
        and actual["boundaries"][12]["flags"] == logical_test_flags(k)
        and actual["boundaries"][12]["flag_mask"] == 0xC5
    )
    return expected


@pytest.mark.parametrize(
    "n,k",
    ((2, 2), (2, 17), (3, 3), (7, 17), (17, 31), (127, 255), (128, 255), (511, 511)),
)
def test_selected_counts_capacity_and_all_full14_abi_states(n, k):
    packet = inputs(n, k)
    before = copy.deepcopy(packet)
    check(c.apply(**packet), packet)
    equal(packet, before)


@pytest.mark.parametrize("a", (0, 1, 7, 15))
@pytest.mark.parametrize("profile", range(3))
def test_selected_alignment_payload_and_caller_capacity(a, profile):
    packet = inputs(
        3,
        17,
        frame=0x30001000 + a,
        receiver=0x10000100 + a,
        insertion=0x10002FF0 + a,
        source=0x20000FF9 + a,
        allocations=(0x06001000 + a, 0x06002000 + a, 0x06003000 + a),
        profile=profile,
        parameter=(0xBF800000, 0x7FC01234, 0xFF800000)[profile],
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("flags", FLAGS)
def test_all128_ordinary_flags_at_count2(flags):
    packet = inputs(flags=flags)
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["boundaries"][0]["flags"] == 0


@pytest.mark.parametrize("flags", (2, 0x202, 0xAD7))
def test_selected_flags_at_maximum_without_full_max_matrix(flags):
    packet = inputs(511, flags=flags)
    check(c.apply(**packet), packet)
    assert sub_flags(511, 1) == 0


@pytest.mark.parametrize("a", (0, 7, 15))
@pytest.mark.parametrize("profile", range(3))
def test_count2_old_complete14_compatibility_after_independent_oracle(a, profile):
    from src.observatory import native_movement_addmove_normal_semantics as predecessor

    packet = inputs(frame=0x30001000 + a, profile=profile)
    actual = c.apply(**packet)
    check(actual, packet)
    equal(actual, predecessor.apply(**packet))


@pytest.mark.parametrize("parameter", (0, 0xFFFFFFFF, 0x7FC01234, 0xFF800000))
def test_movss_raw32_parameter_and_upper96_clear(parameter):
    packet = inputs(3, 17, parameter=parameter)
    packet["xmm"]["xmm0"] = 2**128 - 1
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["child_packets"]["default"]["xmm"]["xmm0"] == 2**128 - 1
    assert actual["child_packets"]["assignment"]["xmm"]["xmm0"] == 2**128 - 1
    assert actual["child_packets"]["record_copy"]["xmm"]["xmm0"] == parameter


@pytest.mark.parametrize("value", (0, 0x80000000, 0xFFFFFFFF))
def test_arbitrary_nonaddress_gpr_xmm_fs_cookie_and_spare_path(value):
    packet = inputs(3, 17)
    for name in GPR:
        if name not in ("ecx", "esp"):
            packet["registers"][name] = value
    for name in XMM:
        packet["xmm"][name] = sum(value << (32 * i) for i in range(4))
    store(packet["pages"], 0, value)
    store(packet["pages"], 0x893F28, value)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "n,k,g,h,new,o,ret",
    [
        (2, 3, 0x02000103, 0x10000FF9, 0x01000FF0, 0x20000FF9, 0x4000003),
        (3, 17, 0x80000010, 0x10000100, 0x20000FFB, 0x70000FF9, 0x6EB205),
        (17, 31, 0xFFFFFFEB, 0x10000100, 0x20000FF0, 0x80000FF9, 0xFFFFFFFF),
        (511, 511, 0x30000FFD, 0x10000FF9, 0x10002FF0, 0x7FFFFFF9, 0x4000000),
        (2, 17, 0x30001000, 0x30001014, 0x10002FF0, 0x20000FF9, 0x4000000),
        (2, 17, 0x30001000, 0x10000100, 0x10002FF0, 0x30001014, 0x4000000),
    ],
)
def test_bounded_actual_frames_crosspages_signed_edges_and_samepage_ancestors(
    n, k, g, h, new, o, ret
):
    packet = inputs(
        n, k, frame=g, receiver=h, insertion=new, source=o, return_address=ret
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("count", (2, 3, 511))
def test_nested_output_detachment_and_unmodified_actual_inputs(count):
    packet = inputs(count)
    before = copy.deepcopy(packet)
    wanted = independent(packet)
    actual = c.apply(**packet)
    actual["pages"].clear()
    actual["registers"].clear()
    actual["xmm"].clear()
    actual["events"].clear()
    actual["child_packets"]["assignment"]["allocation_packet"]["relation"].clear()
    actual["imports"][0]["pages"].clear()
    actual["boundaries"][0]["pages"].clear()
    equal(packet, before)
    equal(c.apply(**packet), wanted)


@pytest.mark.parametrize(
    "kind",
    (
        "pages_mapping",
        "page_float",
        "page_mutable",
        "gpr_alias",
        "gpr_bool",
        "gpr_extra",
        "xmm_mapping",
        "xmm_bool",
        "xmm_large",
        "allocations_tuple",
        "allocation_bool",
        "allocation_float",
        "allocation_short",
        "flags_bool",
        "flags_missingbit",
        "return_float",
    ),
)
def test_exact_top_input_types(kind):
    packet = inputs()
    if kind == "pages_mapping":
        packet["pages"] = UserDict(packet["pages"])
    elif kind == "page_float":
        packet["pages"][0.0] = packet["pages"].pop(0)
    elif kind == "page_mutable":
        packet["pages"][0] = bytearray(packet["pages"][0])
    elif kind == "gpr_alias":

        class Alias(str):
            pass

        packet["registers"] = {Alias(k): v for k, v in packet["registers"].items()}
    elif kind == "gpr_bool":
        packet["registers"]["eax"] = False
    elif kind == "gpr_extra":
        packet["registers"]["other"] = 0
    elif kind == "xmm_mapping":
        packet["xmm"] = UserDict(packet["xmm"])
    elif kind == "xmm_bool":
        packet["xmm"]["xmm7"] = False
    elif kind == "xmm_large":
        packet["xmm"]["xmm0"] = 2**128
    elif kind == "allocations_tuple":
        packet["allocation_results"] = tuple(packet["allocation_results"])
    elif kind == "allocation_bool":
        packet["allocation_results"][0] = False
    elif kind == "allocation_float":
        packet["allocation_results"][1] = float(packet["allocation_results"][1])
    elif kind == "allocation_short":
        packet["allocation_results"].pop()
    elif kind == "flags_bool":
        packet["entry_flags"] = True
    elif kind == "flags_missingbit":
        packet["entry_flags"] = 0x244
    else:
        packet["return_address"] = float(packet["return_address"])
    with pytest.raises(c.AddMoveSmallNormalError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    (
        "count1",
        "count512",
        "cap_under",
        "cap512",
        "end_fraction",
        "cap_fraction",
        "allocation_alias",
        "allocation_extent",
        "allocation_error",
        "alloc2_error",
        "source_spare_heap",
        "source_spare_iat",
        "source_spare_error",
        "header_runtime",
        "stack_window_heap",
        "stack_window_data",
        "source_missing",
        "data_missing",
        "wrong_heap",
        "wrong_alloc_iat",
        "wrong_free_iat",
        "receiver_full",
        "receiver_alias",
        "receiver_above_local",
        "caller_return",
        "return_source_spare",
        "literal_byte",
        "code_page",
        "lowframe",
        "wrapframe",
    ),
)
def test_upfront_whole_capacity_window_runtime_and_child_domain_guards(
    kind, monkeypatch
):
    packet = inputs(2, 17)
    g = packet["registers"]["esp"]
    o = word(packet["pages"], g + 4)
    h = packet["registers"]["ecx"]
    if kind == "count1":
        store(packet["pages"], g + 8, o + 8)
    elif kind == "count512":
        store(packet["pages"], g + 8, o + 4096)
        store(packet["pages"], g + 12, o + 4096)
    elif kind == "cap_under":
        store(packet["pages"], g + 12, o + 8)
    elif kind == "cap512":
        store(packet["pages"], g + 12, o + 4096)
    elif kind == "end_fraction":
        store(packet["pages"], g + 8, o + 15)
    elif kind == "cap_fraction":
        store(packet["pages"], g + 12, o + 17)
    elif kind == "allocation_alias":
        packet["allocation_results"][1] = packet["allocation_results"][0]
    elif kind == "allocation_extent":
        packet["allocation_results"][2] = 0x6003FF1
    elif kind in ("allocation_error", "alloc2_error"):
        packet["allocation_results"][0 if kind == "allocation_error" else 2] = 0x6000FF0
    elif kind == "source_spare_heap":
        packet = inputs(2, 33, source=0x8B6F00)
    elif kind == "source_spare_iat":
        packet = inputs(2, 3, source=0x7D5FF0)
    elif kind == "source_spare_error":
        packet = inputs(2, 3, source=0x5FFFFF0)
    elif kind == "header_runtime":
        packet = inputs(receiver=0x8B7004)
    elif kind == "stack_window_heap":
        packet = inputs(frame=0x8B6FE0)
    elif kind == "stack_window_data":
        packet = inputs(frame=0x5FFFFE0)
    elif kind == "source_missing":
        packet["pages"].pop(o & ~4095)
    elif kind == "data_missing":
        packet["pages"].pop(0x6003000)
    elif kind in ("wrong_heap", "wrong_alloc_iat", "wrong_free_iat"):
        store(
            packet["pages"],
            {
                "wrong_heap": 0x8B7634,
                "wrong_alloc_iat": 0x7D6220,
                "wrong_free_iat": 0x7D621C,
            }[kind],
            0,
        )
    elif kind == "receiver_full":
        store(packet["pages"], h + 8, word(packet["pages"], h + 4))
    elif kind == "receiver_alias":
        packet["registers"]["ecx"] = g - 100
    elif kind == "receiver_above_local":
        store(packet["pages"], h, 0x40000000)
        store(packet["pages"], h + 4, 0x40000000)
        store(packet["pages"], h + 8, 0x40000134)
    elif kind == "caller_return":
        store(packet["pages"], g, 0x4000004)
    elif kind == "return_source_spare":
        packet["return_address"] = o + 24
        store(packet["pages"], g, o + 24)
    elif kind == "literal_byte":
        store(packet["pages"], 0x80DFDC, 1, 1)
    elif kind == "code_page":
        packet["pages"][0x657000] = bytes(4096)
    elif kind == "lowframe":
        packet["registers"]["esp"] = 0x337
    else:
        packet["registers"]["esp"] = 0xFFFFFFEC
    calls = []

    def forbidden(*a, **k):
        calls.append("child")
        raise AssertionError("invalid domain reached child")

    for module in (c.default, c.assign, c.record, c.append, c.destroy):
        monkeypatch.setattr(module, "apply", forbidden)
    with pytest.raises(c.AddMoveSmallNormalError):
        c.apply(**packet)
    assert calls == []


@pytest.mark.parametrize("bit", [b for b in range(32) if not (0xAD7 >> b) & 1])
def test_each_forbidden_flag_bit_before_dependency(bit, monkeypatch):
    packet = inputs(flags=0x246 | (1 << bit))
    calls = []

    def forbidden(**k):
        calls.append("default")
        raise AssertionError("control flag reached child")

    monkeypatch.setattr(c.default, "apply", forbidden)
    with pytest.raises(c.AddMoveSmallNormalError):
        c.apply(**packet)
    assert calls == []


CHILD_MAP = {
    "default": ("default", constructor.independent_packet, 0x657397),
    "assignment": ("assign", assignment.independent, 0x6573A7),
    "record_copy": ("record", record.independent, 0x6573C3),
    "append": ("append", append.independent, 0x6573D5),
    "destroy_temp": ("destroy", destructor.independent, 0x6573E0),
    "destroy_original": ("destroy", destructor.independent, 0x6573ED),
}


@pytest.mark.parametrize("role", tuple(CHILD_MAP))
@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "extra",
        "key_alias",
        "gpr_bool",
        "gpr_mapping",
        "gpr_alias",
        "xmm_bool",
        "page_mapping",
        "page_mutable",
        "page_float",
        "event_tuple",
        "event_width_bool",
        "event_value_bool",
        "trace_tuple",
        "trace_alias",
        "flags_float",
        "mask_float",
        "endpoint_float",
        "df_bool",
    ),
)
def test_all_parent_common_child_closed_schema_roles(role, kind, monkeypatch):
    module, law, ret = CHILD_MAP[role]

    def child(**kwargs):
        packet = law(kwargs)
        if kwargs["return_address"] != ret:
            return packet
        if kind == "missing":
            packet.pop("registers")
        elif kind == "extra":
            packet["extra"] = 0
        elif kind == "key_alias":

            class Alias(str):
                pass

            packet = {Alias(k): v for k, v in packet.items()}
        elif kind == "gpr_bool":
            packet["registers"]["eax"] = False
        elif kind == "gpr_mapping":
            packet["registers"] = UserDict(packet["registers"])
        elif kind == "gpr_alias":

            class Alias(str):
                pass

            packet["registers"] = {Alias(k): v for k, v in packet["registers"].items()}
        elif kind == "xmm_bool":
            packet["xmm"]["xmm7"] = False
        elif kind == "page_mapping":
            packet["pages"] = UserDict(packet["pages"])
        elif kind == "page_mutable":
            packet["pages"][0] = bytearray(packet["pages"][0])
        elif kind == "page_float":
            packet["pages"][0.0] = packet["pages"].pop(0)
        elif kind == "event_tuple":
            packet["events"] = tuple(packet["events"])
        elif kind == "event_width_bool":
            packet["events"][0]["width"] = True
        elif kind == "event_value_bool":
            packet["events"][0]["value"] = False
        elif kind == "trace_tuple":
            packet["trace_rvas"] = tuple(packet["trace_rvas"])
        elif kind == "trace_alias":

            class Alias(str):
                pass

            packet["trace_rvas"][0] = Alias(packet["trace_rvas"][0])
        elif kind == "flags_float":
            packet["flags"] = float(packet["flags"])
        elif kind == "mask_float":
            packet["flag_mask"] = float(packet["flag_mask"])
        elif kind == "endpoint_float":
            packet["endpoint"] = float(packet["endpoint"])
        else:
            packet["df"] = False
        return packet

    monkeypatch.setattr(getattr(c, module), "apply", child)
    with pytest.raises(c.AddMoveSmallNormalError):
        c.apply(**inputs())


@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "extra",
        "flags_bool",
        "mask_float",
        "gpr_bool",
        "stack_mutable",
        "error_mutable",
        "event_tuple",
        "event_width_bool",
        "ret_early",
        "stop_float",
        "stop_early",
        "protocol_bool",
        "protocol_int",
        "coordinated_stack",
        "coordinated_error",
        "missing_read",
    ),
)
def test_full8_caller_free_checked_before_installed_ret_transport(kind, monkeypatch):
    packet = inputs(2, 17)
    source = word(packet["pages"], packet["registers"]["esp"] + 4)
    calls = []

    def free(vector, initial, stack, error, *, stack_base):
        wanted = destructor.free_law(
            vector, initial, stack, error, stack_base=stack_base
        )
        if vector["pointer"] != source:
            return wanted
        calls.append(copy.deepcopy(vector))
        if kind == "missing":
            wanted.pop("protocol")
        elif kind == "extra":
            wanted["extra"] = 0
        elif kind == "flags_bool":
            wanted["flags"] = False
        elif kind == "mask_float":
            wanted["flag_mask"] = float(wanted["flag_mask"])
        elif kind == "gpr_bool":
            wanted["registers"]["eax"] = True
        elif kind == "stack_mutable":
            wanted["stack"] = bytearray(wanted["stack"])
        elif kind == "error_mutable":
            wanted["error"] = bytearray(wanted["error"])
        elif kind == "event_tuple":
            wanted["events"] = tuple(wanted["events"])
        elif kind == "event_width_bool":
            wanted["events"][0]["width"] = True
        elif kind == "ret_early":
            wanted["events"][-1]["value"] = 0x657405
        elif kind == "stop_float":
            wanted["stop"] = float(wanted["stop"])
        elif kind == "stop_early":
            wanted["stop"] = 0x657405
        elif kind == "protocol_bool":
            wanted["protocol"]["result"] = True
        elif kind == "protocol_int":
            wanted["protocol"]["returned"] = 1
        elif kind == "coordinated_stack":
            wanted["stack"] = bytes([wanted["stack"][0] ^ 1]) + wanted["stack"][1:]
            wanted["events"][0]["value"] ^= 1
        elif kind == "coordinated_error":
            wanted["error"] = bytes([wanted["error"][0] ^ 1]) + wanted["error"][1:]
            wanted["protocol"]["last_error"] = 0
        else:
            wanted["events"].pop()
        return wanted

    monkeypatch.setattr(c.deallocator, "_expected", free)
    with pytest.raises(c.AddMoveSmallNormalError, match="primitive differs"):
        c.apply(**packet)
    assert len(calls) == 1 and calls[0]["count"] == 17


@pytest.mark.parametrize("n,k", ((2, 3), (3, 17), (511, 511)))
def test_exact_supplied_free_frames_capacity_and_complete_canonical8(n, k, monkeypatch):
    packet = inputs(n, k)
    wanted = independent(packet)
    source = word(packet["pages"], packet["registers"]["esp"] + 4)
    calls = []

    def free(vector, initial, stack, error, *, stack_base):
        calls.append(copy.deepcopy((vector, initial, stack, error, stack_base)))
        lower = destructor.free_law(
            vector, initial, stack, error, stack_base=stack_base
        )
        assert lower["stop"] == lower["events"][-1]["value"] == 0x4000000
        if vector["pointer"] == source:
            assert vector["count"] == k
            equal(initial, wanted["boundaries"][12]["registers"])
        return lower

    monkeypatch.setattr(c.deallocator, "_expected", free)
    check(c.apply(**packet), packet)
    assert [(q[0]["pointer"], q[0]["count"]) for q in calls] == [
        (packet["allocation_results"][1], n),
        (packet["allocation_results"][0], n),
        (source, k),
    ]


def test_actual_caller_free_ret_checked_after_complete_canonical_join():
    packet = inputs(2, 17)
    wanted = independent(packet)
    entry = wanted["boundaries"][12]
    pages = dict(entry["pages"])
    g = packet["registers"]["esp"]
    store(pages, g - 0x298, 0x657409)
    with pytest.raises(
        c.AddMoveSmallNormalError, match="installed continuation differs"
    ):
        c._outer_free_law(
            entry["registers"],
            pages,
            word(packet["pages"], g + 4),
            min((g - 0x2B8) & ~4095, 0xFFFFE000),
            17,
        )


@pytest.mark.parametrize(
    "role", ("default", "assignment", "record_copy", "append", "destroy_original")
)
def test_valid_extra_nested_semantic_metadata_is_explicitly_trusted(role, monkeypatch):
    module, law, ret = CHILD_MAP[role]
    packet = inputs()
    wanted = independent(packet)

    def change(child):
        if role == "default":
            child["argument"] = 1
        elif role == "assignment":
            child["source_snapshot"] = bytes(len(child["source_snapshot"]))
        elif role == "record_copy":
            child["path_packet"]["scalar_packet"]["trace_rvas"][0] = "0x00123456"
        elif role == "append":
            child["record_packet"]["path_packet"]["scalar_packet"]["trace_rvas"][
                0
            ] = "0x00123456"
        else:
            child["free_packet"]["protocol"]["last_error"] = 0

    def child(**kwargs):
        result = law(kwargs)
        if kwargs["return_address"] == ret:
            change(result)
        return result

    monkeypatch.setattr(getattr(c, module), "apply", child)
    change(wanted["child_packets"][role])
    equal(c.apply(**packet), wanted)


@pytest.mark.parametrize("role", tuple(CHILD_MAP))
def test_foreign_child_errors_are_normalized(role, monkeypatch):
    module, law, ret = CHILD_MAP[role]

    def child(**kwargs):
        if kwargs["return_address"] == ret:
            raise RuntimeError("foreign child failure")
        return law(kwargs)

    monkeypatch.setattr(getattr(c, module), "apply", child)
    with pytest.raises(c.AddMoveSmallNormalError, match="foreign child failure"):
        c.apply(**inputs())


def test_closed_actual_api_source_pins_and_no_fixture_or_native_delegate():
    sig = inspect.signature(c.apply)
    assert tuple(sig.parameters) == (
        "pages",
        "registers",
        "xmm",
        "return_address",
        "entry_flags",
        "allocation_results",
    )
    assert all(
        p.kind == inspect.Parameter.KEYWORD_ONLY
        and p.default == inspect.Parameter.empty
        for p in sig.parameters.values()
    )
    assert c.ANALYSIS_KIND == "pe_native_movement_addmove_small_normal_semantics"
    assert c.BODY_PINS[0x257340] == (
        231,
        "910d5418dbd9db30c75adcd8b74077c5c4e99119b2298c6c252045f8c9803d67",
    )
    assert len(c.BODY_PINS) == 20 and sum(n for n, h in c.BODY_PINS.values()) == 3727
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
