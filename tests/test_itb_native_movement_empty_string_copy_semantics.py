"""Independent selected80D0 empty-source assignment, actual pages only.

Expected state and accesses are handwritten from the reviewed operand facts.
The production apply function is only the actual value under test.
"""

from __future__ import annotations

import ast
import copy
import inspect

import pytest

from src.observatory import native_movement_empty_string_copy_semantics as c

GPRS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMMS = tuple(f"xmm{i}" for i in range(8))
TRACE = tuple(int(word, 16) for word in """
80d0 80d1 80d3 80d4 80d7 80d8 80da 80dd 80de 80e1 80e3 80e9 80ec 80ee 80f0
80f3 80f5 813e 8141 8147 814a 8170 8172 8174 8178 817b 818b 818d 818e 818f
8190 8193 8194
""".split())
KEYS = {
    "source_address",
    "destination_address",
    "registers",
    "xmm",
    "pages",
    "events",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "trace_rvas",
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


def inputs(
    *,
    frame=0x30001000,
    source=0x10000100,
    destination=0x10000300,
    old_size=7,
    profile=0,
    flags=0x246,
    return_address=0x4000000,
):
    spans = (
        (frame - 16, frame + 16),
        (source, source + 24),
        (destination, destination + 24),
    )
    addresses = {
        page
        for start, end in spans
        for page in range(start & ~4095, ((end - 1) & ~4095) + 1, 4096)
    }
    addresses.update((0, 0x12340000))
    pages = {
        page: bytes((i * 43 + j * 29 + profile * 71) & 255 for j in range(4096))
        for i, page in enumerate(sorted(addresses))
    }
    regs = {
        name: (0xB31AE9F2 + i * 0x01234567 + profile * 0x4321) & 0xFFFFFFFF
        for i, name in enumerate(GPRS)
    }
    regs.update(ecx=destination, esp=frame)
    xmms = {
        name: int.from_bytes(
            bytes((i * 31 + j * 17 + profile * 97) & 255 for j in range(16)), "little"
        )
        for i, name in enumerate(XMMS)
    }
    store(pages, source, 0, 1)
    store(pages, source + 16, 0)
    store(pages, source + 20, 15)
    store(pages, destination + 16, old_size)
    store(pages, destination + 20, 15)
    for i, word in enumerate((return_address, source, 0, 0xFFFFFFFF)):
        store(pages, frame + i * 4, word)
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmms,
        return_address=return_address,
        entry_flags=flags,
    )


def independent(packet):
    regs = packet["registers"]
    g = regs["esp"]
    d = regs["ecx"]
    s = int.from_bytes(read_bytes(packet["pages"], g + 4, 4), "little")
    events = []
    for kind, address, width, value in (
        ("write", g - 4, 4, regs["ebp"]),
        ("write", g - 8, 4, regs["ebx"]),
        ("read", g + 4, 4, s),
        ("write", g - 12, 4, regs["esi"]),
        ("read", g + 8, 4, 0),
        ("write", g - 16, 4, regs["edi"]),
        ("read", s + 16, 4, 0),
        ("read", g + 12, 4, 0xFFFFFFFF),
        ("read", d + 20, 4, 15),
        ("read", d + 20, 4, 15),
        ("write", d + 16, 4, 0),
        ("read", g - 16, 4, regs["edi"]),
        ("read", g - 12, 4, regs["esi"]),
        ("read", g - 8, 4, regs["ebx"]),
        ("write", d, 1, 0),
        ("read", g - 4, 4, regs["ebp"]),
        ("read", g, 4, packet["return_address"]),
    ):
        events.append(dict(access=kind, address=address, width=width, value=value))
    # Complete pages use a separate final-store equation, not event replay.
    pages = dict(packet["pages"])
    for address, value, width in (
        (g - 4, regs["ebp"], 4),
        (g - 8, regs["ebx"], 4),
        (g - 12, regs["esi"], 4),
        (g - 16, regs["edi"], 4),
        (d + 16, 0, 4),
        (d, 0, 1),
    ):
        store(pages, address, value, width)
    return dict(
        source_address=s,
        destination_address=d,
        registers=dict(regs, eax=d, ecx=0, esp=g + 16),
        xmm=dict(packet["xmm"]),
        pages=pages,
        events=events,
        flags=0x85,
        flag_mask=0x8D5,
        df=0,
        endpoint=packet["return_address"],
        trace_rvas=[f"0x{pc:08x}" for pc in TRACE],
    )


def check_packet(actual, packet):
    wanted = independent(packet)
    assert type(actual) is dict and set(actual) == KEYS
    assert_strict_packet(actual, wanted)
    assert len(actual["events"]) == 17 and len(actual["trace_rvas"]) == 33
    s, d, g = (
        wanted["source_address"],
        wanted["destination_address"],
        packet["registers"]["esp"],
    )
    assert read_bytes(actual["pages"], s, 24) == read_bytes(packet["pages"], s, 24)
    initial = read_bytes(packet["pages"], d, 24)
    final = read_bytes(actual["pages"], d, 24)
    assert final == b"\0" + initial[1:16] + bytes(4) + initial[20:24]
    preserved = set(range(24)) - {0, 16, 17, 18, 19}
    assert len(preserved) == 19 and all(final[i] == initial[i] for i in preserved)
    assert read_bytes(actual["pages"], g, 16) == read_bytes(packet["pages"], g, 16)
    # Independently replay reads to verify each stack restore against prior stores.
    memory = dict(packet["pages"])
    for row in actual["events"]:
        if row["access"] == "write":
            store(memory, row["address"], row["value"], row["width"])
        else:
            assert (
                int.from_bytes(
                    read_bytes(memory, row["address"], row["width"]), "little"
                )
                == row["value"]
            )
    assert_strict_packet(memory, wanted["pages"])
    reads = [row["address"] for row in actual["events"] if row["access"] == "read"]
    assert s not in reads and s + 20 not in reads and d + 16 not in reads
    assert reads.count(d + 20) == 2
    writes = {
        row["address"] + i
        for row in actual["events"]
        if row["access"] == "write"
        for i in range(row["width"])
    }
    assert writes == set(range(g - 16, g)) | {d, d + 16, d + 17, d + 18, d + 19}
    excluded = {0x8117, 0x8130, 0x8152, 0x81A3, 0x81D7, 0x81E1, 0x81EB}
    assert not excluded.intersection(int(pc, 16) for pc in actual["trace_rvas"])


@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize("profile", range(3))
@pytest.mark.parametrize("order", ("source_before", "source_after"))
def test_full_independent_actual_page_law(alignment, profile, order):
    source, dest = (
        (0x10000100 + alignment, 0x10000300 + alignment)
        if order == "source_before"
        else (0x10000300 + alignment, 0x10000100 + alignment)
    )
    packet = inputs(
        frame=0x30001000 + alignment,
        source=source,
        destination=dest,
        profile=profile,
        old_size=(0, 7, 15)[profile],
    )
    original = copy.deepcopy(packet)
    check_packet(c.apply(**packet), packet)
    assert_strict_packet(packet, original)


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
def test_all_ordinary_flag_words(flags):
    packet = inputs(flags=flags)
    check_packet(c.apply(**packet), packet)


@pytest.mark.parametrize("old_size", range(16))
def test_every_admitted_unused_destination_size(old_size):
    packet = inputs(old_size=old_size)
    check_packet(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "frame,source,dest",
    [
        (0x30001003, 0x10000FF3, 0x20000FF9),
        (0x30001007, 0x7FFFFFF0, 0x80000100),
        (0x3000100F, 0x80000100, 0x7FFFFFF0),
        (0x30001FF0, 0xFFFFFFE7, 0x10000300),
        (0x30000010, 0x10000100, 0xFFFFFFE7),
        (0xFFFFFFEF, 0x10000100, 0x10000300),
        (16, 0x10000100, 0x10000300),
        (0x408200, 0x10000100, 0x10000300),
        (0x30001000, 1, 0x10000300),
        (0x30001000, 0x10000100, 1),
    ],
)
def test_cross_pages_signed_addresses_and_exact_exclusive_bounds(frame, source, dest):
    packet = inputs(
        frame=frame, source=source, destination=dest, old_size=15, flags=0xAD7
    )
    check_packet(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "source,destination",
    [
        (0x10000100, 0x10000118),
        (0x10000118, 0x10000100),
        (0x30001010, 0x10000100),
        (0x10000100, 0x30001010),
        (0x30000FD8, 0x10000100),
        (0x10000100, 0x30000FD8),
        (0x4081F0, 0x10000100),
        (0x10000100, 0x4081F0),
    ],
)
def test_object_frame_and_code_exact_adjacencies(source, destination):
    packet = inputs(source=source, destination=destination)
    check_packet(c.apply(**packet), packet)


@pytest.mark.parametrize(
    "return_address", [1, 0xFFFFFFFF, 0x4081F0, 0x55BA65, 0x55BA99, 0x30002000]
)
def test_external_and_record_copy_continuations(return_address):
    packet = inputs(return_address=return_address)
    check_packet(c.apply(**packet), packet)


@pytest.mark.parametrize("value", [0, 0xFFFFFFFF, 0x80000000])
def test_full_arbitrary_gpr_and_xmm_values(value):
    packet = inputs()
    for name in GPRS:
        if name not in ("ecx", "esp"):
            packet["registers"][name] = value
    packet["xmm"] = {
        name: (value << 96) | (value << 64) | (value << 32) | value for name in XMMS
    }
    check_packet(c.apply(**packet), packet)


def test_result_detachment_and_nonmutating_inputs():
    packet = inputs()
    original = copy.deepcopy(packet)
    first = c.apply(**packet)
    second = c.apply(**packet)
    first["registers"]["edx"] ^= 1
    first["xmm"]["xmm7"] ^= 1
    first["pages"][0] = bytes(4096)
    first["events"][0]["value"] ^= 1
    first["trace_rvas"].append("forged")
    assert_strict_packet(packet, original)
    check_packet(second, packet)
    packet["registers"]["eax"] ^= 1
    packet["xmm"]["xmm0"] ^= 1
    packet["pages"].clear()
    check_packet(second, original)


@pytest.mark.parametrize("bit", [bit for bit in range(32) if not (0xAD7 >> bit & 1)])
def test_forbidden_control_or_reserved_flag_bits(bit):
    packet = inputs(flags=2 | (1 << bit))
    with pytest.raises(c.EmptyStringCopyError):
        c.apply(**packet)


@pytest.mark.parametrize("flags", [0, 4, 0xAD5, 0x200, True, 2.0, -1, 2**32])
def test_malformed_flags_and_required_bit1(flags):
    packet = inputs(flags=flags)
    with pytest.raises(c.EmptyStringCopyError):
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
def test_full_scalar_types(group, key, value):
    packet = inputs()
    packet[group][key] = value
    with pytest.raises(c.EmptyStringCopyError):
        c.apply(**packet)


@pytest.mark.parametrize("group", ["registers", "xmm"])
@pytest.mark.parametrize(
    "kind", ["missing", "extra", "sequence", "key_subclass", "dict_subclass"]
)
def test_exact_register_mappings(group, kind):
    class Alias(str):
        pass

    class MappingAlias(dict):
        pass

    packet = inputs()
    if kind == "missing":
        packet[group].pop(next(iter(packet[group])))
    elif kind == "extra":
        packet[group]["extra"] = 0
    elif kind == "sequence":
        packet[group] = list(packet[group].values())
    elif kind == "dict_subclass":
        packet[group] = MappingAlias(packet[group])
    else:
        key = next(iter(packet[group]))
        value = packet[group].pop(key)
        packet[group][Alias(key)] = value
    with pytest.raises(c.EmptyStringCopyError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    [
        "bool_page",
        "float_page",
        "negative_page",
        "unaligned_page",
        "wrapped_page",
        "short",
        "mutable",
        "sequence",
        "empty",
        "missing_source",
        "missing_dest",
        "missing_frame",
        "dict_subclass",
    ],
)
def test_page_schema_and_complete_mappings(kind):
    class Alias(dict):
        pass

    packet = inputs(source=0x10000100, destination=0x20000100)
    pages = packet["pages"]
    if kind in ("bool_page", "float_page"):
        data = pages.pop(0)
        pages[False if kind == "bool_page" else 0.0] = data
    elif kind in ("negative_page", "unaligned_page", "wrapped_page"):
        pages[
            {"negative_page": -1, "unaligned_page": 1, "wrapped_page": 2**32}[kind]
        ] = bytes(4096)
    elif kind == "short":
        pages[0] = bytes(4095)
    elif kind == "mutable":
        pages[0] = bytearray(pages[0])
    elif kind == "sequence":
        packet["pages"] = list(pages.items())
    elif kind == "empty":
        packet["pages"] = {}
    elif kind == "dict_subclass":
        packet["pages"] = Alias(pages)
    else:
        pages.pop(
            {
                "missing_source": 0x10000000,
                "missing_dest": 0x20000000,
                "missing_frame": 0x30000000,
            }[kind]
        )
    with pytest.raises(c.EmptyStringCopyError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "kind",
    [
        "return_word",
        "source_zero",
        "offset",
        "max",
        "source_size",
        "source_cap",
        "source_byte",
        "dest_cap",
        "dest_size",
    ],
)
def test_installed_caller_and_inline_shape_premises(kind):
    packet = inputs()
    g = packet["registers"]["esp"]
    d = packet["registers"]["ecx"]
    source = int.from_bytes(read_bytes(packet["pages"], g + 4, 4), "little")
    address, width, value = {
        "return_word": (g, 4, packet["return_address"] + 1),
        "source_zero": (g + 4, 4, 0),
        "offset": (g + 8, 4, 1),
        "max": (g + 12, 4, 0),
        "source_size": (source + 16, 4, 1),
        "source_cap": (source + 20, 4, 16),
        "source_byte": (source, 1, 1),
        "dest_cap": (d + 20, 4, 16),
        "dest_size": (d + 16, 4, 16),
    }[kind]
    store(packet["pages"], address, value, width)
    original = copy.deepcopy(packet)
    with pytest.raises(c.EmptyStringCopyError):
        c.apply(**packet)
    assert_strict_packet(packet, original)


@pytest.mark.parametrize(
    "kind",
    [
        "source_dest_equal",
        "objects_overlap",
        "source_frame",
        "dest_frame",
        "source_code",
        "dest_code",
        "frame_code",
        "source_wrap",
        "dest_wrap",
        "frame_wrap",
        "frame_low",
        "dest_zero",
    ],
)
def test_disjoint_extent_and_selected_code_guards(kind):
    frame, source, dest = 0x30001000, 0x10000100, 0x10000300
    if kind == "source_dest_equal":
        dest = source
    elif kind == "objects_overlap":
        dest = source + 20
    elif kind == "source_frame":
        source = frame + 8
    elif kind == "dest_frame":
        dest = frame - 4
    elif kind == "source_code":
        source = 0x4080D0
    elif kind == "dest_code":
        dest = 0x4081E8
    elif kind == "frame_code":
        frame = 0x408100
    # Wrapping cases cannot be constructed as byte-addressed valid inputs; move
    # only their installed pointer/frame after making a normal complete mapping.
    packet = inputs(frame=frame, source=source, destination=dest)
    g = packet["registers"]["esp"]
    if kind == "source_wrap":
        store(packet["pages"], g + 4, 0xFFFFFFE8)
    elif kind == "dest_wrap":
        packet["registers"]["ecx"] = 0xFFFFFFE8
    elif kind == "frame_wrap":
        packet["registers"]["esp"] = 0xFFFFFFF0
    elif kind == "frame_low":
        packet["registers"]["esp"] = 15
    elif kind == "dest_zero":
        packet["registers"]["ecx"] = 0
    with pytest.raises(c.EmptyStringCopyError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "return_address",
    [0, True, 0.0, -1, 2**32, 0x4080D0, 0x4081EF, 0x30001000, 0x10000100, 0x10000300],
)
def test_return_typed_data_and_code_exclusions(return_address):
    packet = inputs()
    packet["return_address"] = return_address
    if type(return_address) is int and 0 <= return_address <= 0xFFFFFFFF:
        store(packet["pages"], packet["registers"]["esp"], return_address)
    with pytest.raises(c.EmptyStringCopyError):
        c.apply(**packet)


def test_unchanged_unused_inline_bytes_are_arbitrary():
    packet = inputs(old_size=15)
    g = packet["registers"]["esp"]
    s = int.from_bytes(read_bytes(packet["pages"], g + 4, 4), "little")
    d = packet["registers"]["ecx"]
    for i in range(1, 16):
        store(packet["pages"], s + i, 255 - i, 1)
        store(packet["pages"], d + i, 128 + i, 1)
    check_packet(c.apply(**packet), packet)


def test_source_contract_and_no_fixture_or_execution_dependency():
    assert c.SOURCE_PINS == {
        "program_facts": (
            "pe_ghidra_program_facts",
            "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
        ),
        "movement_binding": (
            "pe_native_movement_effect_binding",
            "54c060913d61f6bb5e4c1f2586f0d5186ea73ad6c058dd48b1cc056e64a410b9",
        ),
        "default_record": (
            "pe_native_movement_effect_record_default_conformance",
            "942fc246105c941a46ac73e7be432acdacad1428322888b76c0164aca49e673f",
        ),
    }
    assert (c.ENTRY, c.SIZE, c.BODY_SHA256) == (
        0x80D0,
        288,
        "062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333",
    )
    tree = ast.parse(inspect.getsource(c))
    assert all(
        isinstance(node, ast.ImportFrom) and node.module == "__future__"
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    )
    assert not any(
        isinstance(node, ast.Name)
        and node.id in ("_fixture", "_run_case", "unicorn", "pefile", "capstone")
        for node in ast.walk(tree)
    )
    signature = inspect.signature(c.apply)
    assert list(signature.parameters) == [
        "pages",
        "registers",
        "xmm",
        "return_address",
        "entry_flags",
    ]
    assert all(
        param.kind is inspect.Parameter.KEYWORD_ONLY
        and param.default is inspect.Parameter.empty
        for param in signature.parameters.values()
    )
