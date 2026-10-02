"""Independent selected AddCharge owner around handwritten clone and Move laws.

Expected values never call production apply or packet helpers. Valid child
semantics are trusted, with malformed common envelopes rejected separately.
"""

from __future__ import annotations
import ast
import copy
import inspect
from collections import UserDict
import pytest
from src.observatory import native_movement_addcharge_normal_semantics as c
from tests import test_itb_native_movement_addmove_normal_semantics as move
from tests import test_itb_native_movement_path_clone2_semantics as clone
from tests import test_itb_native_movement_effect_record_destroy_semantics as destroy
from tests.test_itb_native_movement_empty_string_copy_semantics import (
    store,
    read_bytes,
    assert_strict_packet as equal,
)

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
FLAGS = move.FLAGS
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
OWNER = tuple(
    tuple(int(w, 16) for w in words.split())
    for words in (
        "2576f0 2576f1 2576f3 2576f5 2576fa 257700 257701 257702 257707 257709 25770a 25770d 257713 257715 25771a 25771d 257720 257727 257729 25772c 257732 257733",
        "257738 25773a",
        "25773f 257741 257743 257746 25774d 257750 257752 257754 257757 257759 25775b 25775e 25775f 257760",
        "257765 257768 25776b 257772 257773 257774 257776 257777",
    )
)


def word(pages, at):
    return int.from_bytes(read_bytes(pages, at, 4), "little")


def inputs(
    *,
    frame=0x30001000,
    receiver=0x10000100,
    insertion=0x10002FF0,
    source=0x06002FF9,
    allocations=(0x06001013, 0x06001103, 0x06002003, 0x06003033),
    profile=0,
    parameter=0xBF800000,
    flags=0x246,
    return_address=0x04000000,
    previous=2,
    spare=2,
):
    packet = move.inputs(
        frame=frame,
        receiver=receiver,
        insertion=insertion,
        source=source,
        allocations=allocations[1:],
        profile=profile,
        parameter=parameter,
        flags=flags,
        return_address=return_address,
        previous=previous,
        spare=spare,
    )
    ranges = [(frame - 0x364, frame + 20)]
    for depth in (0x31C, 0x33C, 0x364, 0x2F0, 0x2E4, 136, 72):
        base = min((frame - depth) & ~4095, 0xFFFFE000)
        ranges.append((base, base + 8192))
    for start, end in ranges:
        for page in range(start & ~4095, ((end - 1) & ~4095) + 1, 4096):
            if page not in packet["pages"]:
                packet["pages"][page] = bytes(
                    (j * 43 + (page >> 12) * 31 + profile * 97) & 255
                    for j in range(4096)
                )
    packet["allocation_results"] = list(allocations)
    return packet


def sub_flags(left, right):
    result = (left - right) & 0xFFFFFFFF
    return (
        int(left < right)
        | (4 if (result & 255).bit_count() % 2 == 0 else 0)
        | (0x10 if (left ^ right ^ result) & 0x10 else 0)
        | (0x40 if result == 0 else 0)
        | (0x80 if result & 0x80000000 else 0)
        | (0x800 if ((left ^ right) & (left ^ result)) & 0x80000000 else 0)
    )


def independent(packet):
    initial = packet["registers"]
    g, h = initial["esp"], initial["ecx"]
    source = word(packet["pages"], g + 4)
    new = word(packet["pages"], h + 4)
    parameter = word(packet["pages"], g + 16)
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
            allocation_result=packet["allocation_results"][0],
        )
    )
    children["clone_argument"] = copy.deepcopy(child)
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
    snapshot("clone_argument", "return", 0x00657738, child["flags"])
    event("write", g - 44, 0x0065773F)
    regs.update(ecx=h, esp=g - 44)
    trace.extend(f"0x{pc:08x}" for pc in OWNER[1])
    snapshot("addmove", "entry", 0x00657340, child["flags"])
    prefix = copy.deepcopy(events)
    child = move.independent(
        dict(
            pages=dict(pages),
            registers=dict(regs),
            xmm=dict(vec),
            return_address=0x0065773F,
            entry_flags=(packet["entry_flags"] & ~0x8D5) | child["flags"],
            allocation_results=list(packet["allocation_results"][1:]),
        )
    )
    children["addmove"] = copy.deepcopy(child)
    for state in child["imports"]:
        imported = copy.deepcopy(state)
        imported["events"] = prefix + imported["events"]
        imports.append(imported)
    trace.extend(child["trace_rvas"])
    events.extend(copy.deepcopy(child["events"]))
    pages, regs, vec = (
        dict(child["pages"]),
        dict(child["registers"]),
        dict(child["xmm"]),
    )
    snapshot("addmove", "return", 0x0065773F, child["flags"])
    event("read", h + 4, new + 308)
    event("write", new + 0xD8, 2)
    event("read", g + 4, source)
    event("read", g + 12, source + 16)
    for at, value in ((g - 28, 8), (g - 32, 2), (g - 36, source), (g - 40, 0x00657765)):
        event("write", at, value)
    regs.update(eax=2, ecx=source, esp=g - 40)
    trace.extend(f"0x{pc:08x}" for pc in OWNER[2])
    snapshot("free_original", "entry", 0x00407800, 0, 0xC5)
    prefix = copy.deepcopy(events)
    base = min((g - 72) & ~4095, 0xFFFFE000)
    free = destroy.free_law(
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
    assert word(pages, g - 40) == 0x00657765
    free["events"][-1]["value"] = 0x00657765
    free["stop"] = 0x00657765
    children["free_original"] = copy.deepcopy(free)
    imported_pages = dict(pages)
    for row in free["events"][:16]:
        if row["access"] == "write":
            store(imported_pages, row["address"], row["value"])
    imports.append(
        dict(
            name="free_original",
            registers=dict(
                regs, eax=0x1FFFFFFF, ecx=source, edx=7, ebp=g - 56, esp=g - 72
            ),
            xmm=dict(vec),
            pages=imported_pages,
            events=prefix + copy.deepcopy(free["events"][:16]),
            flags=move.logical_test_flags(source),
            flag_mask=0x8C5,
            df=0,
            endpoint=0x05000000,
            entry_esp=g - 72,
            words=[0x00789172, 0x12345678, 0, source],
        )
    )
    trace.extend(f"0x{pc:08x}" for pc in move.FREE_TRACE)
    events.extend(copy.deepcopy(free["events"]))
    pages[base], pages[base + 4096] = free["stack"][:4096], free["stack"][4096:]
    regs = dict(free["registers"])
    snapshot("free_original", "return", 0x00657765, free["flags"])
    for kind, at, value in (
        ("read", g - 16, seh),
        ("write", 0, seh),
        ("read", g - 24, cookie ^ (g - 4)),
        ("read", g - 20, initial["esi"]),
        ("read", g - 4, initial["ebp"]),
        ("read", g, packet["return_address"]),
    ):
        event(kind, at, value)
    trace.extend(f"0x{pc:08x}" for pc in OWNER[3])
    return dict(
        geometry=dict(
            entry=g,
            receiver=h,
            source_path=source,
            argument_block=g - 40,
            new_record=new,
        ),
        path=dict(
            begin=source,
            end=source + 16,
            capacity=source + 16,
            parameter_bits=parameter,
        ),
        registers=dict(
            initial, eax=1, ecx=cookie ^ (g - 4), edx=0xB0000001, esp=g + 20
        ),
        xmm=vec,
        pages=pages,
        events=events,
        trace_rvas=trace,
        boundaries=states,
        imports=imports,
        child_packets=children,
        flags=append_add_flags(g - 36, 12),
        flag_mask=0x8D5,
        df=0,
        endpoint=packet["return_address"],
    )


def append_add_flags(left, right):
    result = (left + right) & 0xFFFFFFFF
    return (
        int(left + right > 0xFFFFFFFF)
        | (4 if (result & 255).bit_count() % 2 == 0 else 0)
        | (0x10 if (left ^ right ^ result) & 0x10 else 0)
        | (0x40 if result == 0 else 0)
        | (0x80 if result & 0x80000000 else 0)
        | (0x800 if (~(left ^ right) & (left ^ result)) & 0x80000000 else 0)
    )


def check(actual, packet):
    expected = independent(packet)
    assert type(actual) is dict and set(actual) == KEYS
    equal(actual, expected)
    assert len(actual["trace_rvas"]) == 2303 and len(actual["events"]) == 1426
    assert len(actual["boundaries"]) == 6 and len(actual["imports"]) == 8
    assert set(actual["child_packets"]) == {
        "clone_argument",
        "addmove",
        "free_original",
    }
    assert [(b["name"], b["phase"]) for b in actual["boundaries"]] == [
        (n, p)
        for n in ("clone_argument", "addmove", "free_original")
        for p in ("entry", "return")
    ]
    assert [len(b["events"]) for b in actual["boundaries"]] == [
        15,
        98,
        99,
        1392,
        1400,
        1420,
    ]
    g, h = packet["registers"]["esp"], packet["registers"]["ecx"]
    source = word(packet["pages"], g + 4)
    new = word(packet["pages"], h + 4)
    allocations = packet["allocation_results"]
    assert [state["words"] for state in actual["imports"]] == [
        [0x00789463, 0x12345678, 0, 16]
    ] * 4 + [
        [0x00789172, 0x12345678, 0, allocations[2]],
        [0x00789172, 0x12345678, 0, allocations[1]],
        [0x00789172, 0x12345678, 0, allocations[0]],
        [0x00789172, 0x12345678, 0, source],
    ]
    assert read_bytes(actual["pages"], g, 16) == read_bytes(packet["pages"], g, 16)
    assert word(actual["pages"], g + 16) == g - 40
    assert word(actual["pages"], new + 0xC8) == word(packet["pages"], g + 16)
    assert word(actual["pages"], new + 0xD8) == 2
    assert [word(actual["pages"], new + n) for n in (0xCC, 0xD0, 0xD4)] == [
        allocations[3],
        allocations[3] + 16,
        allocations[3] + 16,
    ]
    for d in allocations:
        assert read_bytes(actual["pages"], d, 16) == read_bytes(
            packet["pages"], source, 16
        )
    assert read_bytes(actual["pages"], source, 16) == read_bytes(
        packet["pages"], source, 16
    )
    assert word(actual["pages"], h) == word(packet["pages"], h)
    assert word(actual["pages"], h + 4) == new + 308
    assert word(actual["pages"], h + 8) == word(packet["pages"], h + 8)
    assert actual["xmm"]["xmm0"] == word(packet["pages"], g + 16)
    assert all(actual["xmm"][n] == packet["xmm"][n] for n in XMM[1:])
    assert actual["pages"][0x12340000] == packet["pages"][0x12340000]
    assert {e["width"] for e in actual["events"]} == {1, 2, 4}
    assert actual["child_packets"]["addmove"]["child_packets"]["default"]["xmm"][
        "xmm0"
    ] == word(packet["pages"], g + 16)
    return expected


@pytest.mark.parametrize("a", range(16))
@pytest.mark.parametrize("profile", range(3))
def test_all48_typed_profiles_complete14_6states_8imports(a, profile):
    packet = inputs(
        frame=0x30001000 + a,
        receiver=0x10000100 + a,
        insertion=0x10002FF0 + a,
        source=0x06002FF9 + a,
        allocations=(0x06001013 + a, 0x06001103 + a, 0x06002003 + a, 0x06003033 + a),
        profile=profile,
        parameter=(0xBF800000, 0x7FC01234, 0xFF800000)[profile],
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("flags", FLAGS)
def test_all128_ordinary_dfclear_bit1_entry_flags(flags):
    packet = inputs(flags=flags)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "parameter",
    (0, 1, 0xFFFFFFFF, 0x80000000, 0x7FFFFFFF, 0x7F800001, 0x7FA12345, 0x00000001),
)
def test_param_movss_zeroextension_before_clone_and_bitexact_mode_record(parameter):
    packet = inputs(parameter=parameter)
    packet["xmm"]["xmm0"] = (1 << 128) - 1
    actual = c.apply(**packet)
    check(actual, packet)
    assert actual["boundaries"][0]["xmm"]["xmm0"] == parameter
    assert actual["child_packets"]["addmove"]["path"]["parameter_bits"] == parameter


@pytest.mark.parametrize(
    "g,h,new,o,ret",
    (
        (0x02000103, 0x10000FF9, 0x01000FF0, 0x06002FF9, 0x04000003),
        (0x80000010, 0x10000100, 0x20000FFB, 0x06002801, 0x006EB205),
        (0xFFFFFFE0, 0x10000100, 0x20000FF0, 0xFFFFEFF0, 0x04000000),
        (0x30000088, 0x20000FF9, 0x10000FF0, 0x80000FF9, 0x04000107),
        (0x30000350, 0x10000100, 0x20000FF0, 0x06003FE0, 0x04000000),
    ),
)
def test_actual_general_frames_headers_crossings_and_three_page_stack(
    g, h, new, o, ret
):
    packet = inputs(frame=g, receiver=h, insertion=new, source=o, return_address=ret)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "allocations",
    (
        (0x06001103, 0x06001113, 0x06001123, 0x06001133),
        (0x06003FC0, 0x06003FD0, 0x06003FE0, 0x06003FF0),
    ),
)
def test_disjoint_allocation_adjacency_and_exact_data_window_end(allocations):
    packet = inputs(allocations=allocations)
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("which", ("source", "header"))
def test_same_stack_page_source_or_header_after_protected_end(which):
    packet = (
        inputs(source=0x30001014) if which == "source" else inputs(receiver=0x30001014)
    )
    check(c.apply(**packet), packet)


@pytest.mark.parametrize("value", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_arbitrary_nonaddress_gpr_xmm_cookie_seh(value):
    packet = inputs()
    for name in GPR:
        if name not in ("ecx", "esp"):
            packet["registers"][name] = value
    for i, name in enumerate(XMM):
        packet["xmm"][name] = (value << 96) | (value << 64) | (value << 32) | value ^ i
    store(packet["pages"], 0, value)
    store(packet["pages"], 0x00893F28, value)
    check(c.apply(**packet), packet)


def test_nested_packets_states_imports_and_input_results_detached():
    packet = inputs()
    before = copy.deepcopy(packet)
    actual = c.apply(**packet)
    expected = independent(packet)
    packet["allocation_results"][0] ^= 1
    packet["registers"]["ebx"] ^= 1
    packet["xmm"]["xmm7"] ^= 1
    store(packet["pages"], 0x12340000, 0)
    equal(actual, expected)
    actual["child_packets"]["addmove"]["imports"][0]["registers"]["eax"] ^= 1
    actual["child_packets"]["clone_argument"]["events"][0]["value"] ^= 1
    actual["boundaries"][0]["registers"]["eax"] ^= 1
    actual["imports"][0]["events"][0]["value"] ^= 1
    equal(actual["events"], expected["events"])
    equal(actual["registers"], expected["registers"])
    equal(c.apply(**before), expected)


@pytest.mark.parametrize(
    "kind",
    (
        "first_alloc_duplicate",
        "source_extra_frame",
        "header_extra_frame",
        "return_extra_frame",
        "return_charge_code",
        "length3",
        "list_bool4",
    ),
)
def test_outer_frame_and_fourth_allocation_constraints_beyond_move(kind):
    packet = inputs()
    g, h = packet["registers"]["esp"], packet["registers"]["ecx"]
    if kind == "first_alloc_duplicate":
        packet["allocation_results"][0] = packet["allocation_results"][1]
    elif kind == "source_extra_frame":
        source = g - 0x360
        for off, v in ((4, source), (8, source + 16), (12, source + 16)):
            store(packet["pages"], g + off, v)
    elif kind == "header_extra_frame":
        header = g - 0x35C
        for off in (0, 4, 8):
            store(packet["pages"], header + off, word(packet["pages"], h + off))
        packet["registers"]["ecx"] = header
    elif kind in ("return_extra_frame", "return_charge_code"):
        ret = g - 0x350 if kind == "return_extra_frame" else 0x006576F0
        packet["return_address"] = ret
        store(packet["pages"], g, ret)
    elif kind == "length3":
        packet["allocation_results"].pop()
    else:
        packet["allocation_results"][0] = True
    with pytest.raises(c.AddChargeNormalError):
        c.apply(**packet)


@pytest.mark.parametrize("module", ("path", "move"))
@pytest.mark.parametrize("kind", move.COMMON_FORGERIES)
def test_closed_typed_clone_and_move_child_envelopes(monkeypatch, module, kind):
    dependency = getattr(c, module)
    real = dependency.apply

    def forged(**kw):
        child = copy.deepcopy(real(**kw))
        move.corrupt_common(child, kind)
        return child

    monkeypatch.setattr(dependency, "apply", forged)
    with pytest.raises(c.AddChargeNormalError):
        c.apply(**inputs())


@pytest.mark.parametrize("eax", (0, 2, 0x100, 0xFFFFFFFF, 0x80000000))
def test_selected_charge_requires_actual_lowbyte_success(monkeypatch, eax):
    real = c.move.apply

    def forged(**kw):
        child = copy.deepcopy(real(**kw))
        child["registers"]["eax"] = eax
        return child

    monkeypatch.setattr(c.move, "apply", forged)
    with pytest.raises(c.AddChargeNormalError, match="successful AddMove"):
        c.apply(**inputs())


def test_success_predicate_is_source_al_only_not_full_eax(monkeypatch):
    real = c.move.apply

    def highbits(**kw):
        child = copy.deepcopy(real(**kw))
        child["registers"]["eax"] = 0x80000001
        return child

    monkeypatch.setattr(c.move, "apply", highbits)
    actual = c.apply(**inputs())
    assert actual["child_packets"]["addmove"]["registers"]["eax"] == 0x80000001
    assert actual["registers"]["eax"] == 1
    # Valid nested child internals are trusted. This narrowly tests only the
    # owner's AL predicate; it is not a claim about native child high EAX bits.


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
def test_full8_original_free_before_installed_ret_transport(monkeypatch, kind):
    packet = inputs()
    entry = packet["registers"]["esp"] - 40
    real = c.deallocator._expected

    def forged(*args, **kw):
        child = copy.deepcopy(real(*args, **kw))
        if args[1]["esp"] != entry:
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
            child["stop"] = 0x00657765
        elif kind == "protocol":
            child["protocol"]["result"] = True
        elif kind == "event":
            child["events"][-1]["value"] = 0x00657765
        elif kind == "event_bool":
            child["events"][0]["width"] = True
        else:
            for event in child["events"]:
                if event["value"] == args[0]["pointer"]:
                    event["value"] ^= 1
        return child

    monkeypatch.setattr(c.deallocator, "_expected", forged)
    with pytest.raises(c.AddChargeNormalError):
        c.apply(**packet)


def test_all4_free_actual_frames_stack_and_closed_success_protocol(monkeypatch):
    packet = inputs()
    real = c.deallocator._expected
    seen = []

    def observe(vector, registers, stack, error, **kw):
        seen.append(copy.deepcopy((vector, registers, stack, error, kw)))
        return real(vector, registers, stack, error, **kw)

    monkeypatch.setattr(c.deallocator, "_expected", observe)
    actual = c.apply(**packet)
    check(actual, packet)
    assert len(seen) == 4
    expected_pointers = [packet["allocation_results"][i] for i in (2, 1, 0)] + [
        word(packet["pages"], packet["registers"]["esp"] + 4)
    ]
    assert [v[0]["pointer"] for v in seen] == expected_pointers
    for vector, regs, stack, error, kw in seen:
        assert vector == dict(
            pointer=vector["pointer"],
            count=2,
            stride=8,
            metadata=None,
            responses=[dict(kind="heap_free", eax=1)],
            heap=0x12345678,
        )
        assert len(stack) == 8192 and len(error) == 4096
        assert kw == dict(stack_base=min((regs["esp"] - 32) & ~4095, 0xFFFFE000))
    assert seen[-1][1]["esp"] == packet["registers"]["esp"] - 40


@pytest.mark.parametrize("module", ("path", "move"))
def test_foreign_child_error_normalized(monkeypatch, module):
    def failed(**kw):
        raise RuntimeError("independent AddCharge child failure")

    monkeypatch.setattr(getattr(c, module), "apply", failed)
    with pytest.raises(
        c.AddChargeNormalError, match="independent AddCharge child failure"
    ):
        c.apply(**inputs())


def test_source_only_model_exact_api_and_manual_outer_partition():
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
    assert sum(map(len, OWNER)) == 46
    assert 46 + 136 + 2089 + 32 == 2303
    assert 30 + 83 + 1293 + 20 == 1426
    assert not any(
        isinstance(n, ast.Import)
        and any(
            name.name.split(".")[0] in {"unicorn", "capstone", "subprocess"}
            for name in n.names
        )
        for n in ast.walk(tree)
    )


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
        ("allocation_results", [True, 0x6001100, 0x6002000, 0x6003000]),
        ("allocation_results", [0x5FFFFFF, 0x6001100, 0x6002000, 0x6003000]),
        ("allocation_results", [0x6003FF1, 0x6001100, 0x6002000, 0x6003000]),
    ),
)
def test_strict_keyword_word_and_result_list_domains(field, value):
    packet = inputs()
    packet[field] = value
    with pytest.raises(c.AddChargeNormalError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "bit", (3, 5, 8, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 31)
)
def test_unknown_reserved_control_rf_and_df_flags_rejected(bit):
    packet = inputs(flags=0x246 | (1 << bit))
    with pytest.raises(c.AddChargeNormalError):
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
    with pytest.raises(c.AddChargeNormalError):
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
    with pytest.raises(c.AddChargeNormalError):
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
    with pytest.raises(c.AddChargeNormalError):
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
    with pytest.raises(c.AddChargeNormalError):
        c.apply(**packet)


def test_receiver_above_actual_inner_move_temporary_is_outside_external_append():
    packet = inputs(frame=0x02000103, insertion=0x20000FF0)
    with pytest.raises(
        c.AddChargeNormalError, match="append source precedes receiver end"
    ):
        c.apply(**packet)
