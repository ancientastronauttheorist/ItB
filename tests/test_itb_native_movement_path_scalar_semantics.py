"""Independent actual-page DWORD law; no fixture lookup in the model oracle."""

from __future__ import annotations

import copy
import inspect
import pytest
from src.observatory import native_movement_path_scalar_semantics as c

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
KEYS = {
    "pages",
    "registers",
    "xmm",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "source_snapshot",
    "events",
    "trace_rvas",
}
PREFIX = (0x8ABA0, 0x8ABA1, 0x8ABA3, 0x8ABA6, 0x8ABA7, 0x8ABA9, 0x8ABAB)
LOOP = (
    0x8ABB0,
    0x8ABB2,
    0x8ABB4,
    0x8ABB6,
    0x8ABB8,
    0x8ABBB,
    0x8ABBE,
    0x8ABC1,
    0x8ABC4,
    0x8ABC6,
)
SUFFIX = (0x8ABC8, 0x8ABC9, 0x8ABCA)
FLAGS = tuple(2 | bits for bits in range(0xAD8) if bits & ~0xAD5 == 0)


def read(pages, at, size):
    return bytes(pages[(at + i) & ~4095][(at + i) & 4095] for i in range(size))


def store(pages, at, value, size=4):
    raw = value.to_bytes(size, "little")
    for i, b in enumerate(raw):
        page = (at + i) & ~4095
        changed = bytearray(pages[page])
        changed[(at + i) & 4095] = b
        pages[page] = bytes(changed)


def equal(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert set(actual) == set(expected)
        assert all(any(type(k) is type(j) and k == j for j in actual) for k in expected)
        for k in expected:
            equal(actual[k], expected[k])
    elif type(expected) in (list, tuple):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            equal(a, b)
    else:
        assert actual == expected


def inputs(
    count=2,
    *,
    source=0x10001FF9,
    destination=0x20002FFB,
    frame=0x30001003,
    return_address=0x0049A921,
    flags=0x246,
    profile=0,
):
    spans = [(frame - 8, frame + 20)]
    if count:
        spans.extend(
            ((source, source + count * 8), (destination, destination + count * 8))
        )
    keys = {0x19000000}
    for a, b in spans:
        keys.update(range(a & ~4095, ((b - 1) & ~4095) + 4096, 4096))
    pages = {
        page: bytes(
            (j * 43 + (page >> 12) * 17 + profile * 79) & 255 for j in range(4096)
        )
        for page in sorted(keys)
    }
    regs = {
        n: (0x13579BDF + i * 0x11111111 + profile * 0x29481736) & 0xFFFFFFFF
        for i, n in enumerate(GPR)
    }
    regs.update(esp=frame, ecx=source, edx=source + count * 8)
    vec = {
        n: int.from_bytes(
            bytes((i * 37 + j * 23 + profile * 59) & 255 for j in range(16)), "little"
        )
        for i, n in enumerate(XMM)
    }
    store(pages, frame, return_address)
    store(pages, frame + 4, destination)
    return dict(
        pages=pages,
        registers=regs,
        xmm=vec,
        source=source,
        destination=destination,
        return_address=return_address,
        entry_flags=flags,
    )


def independent(packet):
    incoming = packet["registers"]
    frame = incoming["esp"]
    source, destination = packet["source"], packet["destination"]
    size = incoming["edx"] - source
    count = size // 8
    snapshot = read(packet["pages"], source, size)
    memory = dict(packet["pages"])
    events = []

    def event(access, at, value):
        events.append(dict(access=access, address=at, width=4, value=value))
        if access == "write":
            store(memory, at, value)
        else:
            assert int.from_bytes(read(memory, at, 4), "little") == value

    event("write", frame - 4, incoming["ebp"])
    event("read", frame + 4, destination)
    event("write", frame - 8, incoming["esi"])
    for i in range(count):
        first = int.from_bytes(snapshot[8 * i : 8 * i + 4], "little")
        second = int.from_bytes(snapshot[8 * i + 4 : 8 * i + 8], "little")
        event("read", source + 8 * i, first)
        event("write", destination + 8 * i, first)
        event("read", source + 8 * i + 4, second)
        event("write", destination + 8 * i + 4, second)
    event("read", frame - 8, incoming["esi"])
    event("read", frame - 4, incoming["ebp"])
    event("read", frame, packet["return_address"])
    trace = PREFIX + ((0x8ABAD,) + LOOP * count if count else ()) + SUFFIX
    return dict(
        pages=memory,
        registers=dict(
            incoming,
            eax=destination + size,
            ecx=int.from_bytes(snapshot[-4:], "little") if count else source,
            esp=frame + 4,
        ),
        xmm=dict(packet["xmm"]),
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=packet["return_address"],
        source_snapshot=snapshot,
        events=events,
        trace_rvas=[f"0x{pc:08x}" for pc in trace],
    )


def check(packet):
    before = copy.deepcopy(packet)
    result = c.apply(**packet)
    equal(result, independent(packet))
    equal(packet, before)
    assert set(result) == KEYS
    count = (packet["registers"]["edx"] - packet["source"]) // 8
    assert len(result["events"]) == 6 + 4 * count
    assert len(result["trace_rvas"]) == (11 + 10 * count if count else 10)
    assert (
        result["flags"] == 0x44 and result["flag_mask"] == 0x8D5 and result["df"] == 0
    )
    assert all(row["width"] == 4 for row in result["events"])
    assert (
        read(result["pages"], packet["source"], 8 * count) == result["source_snapshot"]
    )
    assert (
        read(result["pages"], packet["destination"], 8 * count)
        == result["source_snapshot"]
    )
    assert result["pages"][0x19000000] == before["pages"][0x19000000]
    return result


@pytest.mark.parametrize("count", (0, 1, 2, 3, 17, 131, 513))
@pytest.mark.parametrize("profile", range(3))
def test_complete10_packet_arbitrary_count_and_nonzero_profiles(count, profile):
    check(inputs(count, profile=profile))


@pytest.mark.parametrize("count", (0, 1, 2, 3))
@pytest.mark.parametrize("alignment", range(16))
def test_each_pointer_alignment_full_event_order_pages_and_trace(count, alignment):
    result = check(
        inputs(
            count,
            source=0x10001FF0 + alignment,
            destination=0x20002FF0 + alignment,
            frame=0x30001000 + alignment,
        )
    )
    assert result["trace_rvas"][:7] == [f"0x{pc:08x}" for pc in PREFIX]
    if count:
        assert result["trace_rvas"][7] == "0x0008abad"
    else:
        assert "0x0008abad" not in result["trace_rvas"]


@pytest.mark.parametrize("flags", FLAGS)
def test_all128_ordinary_dfclear_input_flag_combinations(flags):
    assert len(FLAGS) == 128
    check(inputs(3, flags=flags))


@pytest.mark.parametrize(
    "source,destination",
    (
        (0, 0),
        (0xFFFFFFFF, 0),
        (0, 0xFFFFFFFF),
        (0xFFFFFFFF, 0xFFFFFFFF),
        (0x30001003, 0x30001002),
    ),
)
def test_zero_count_unmapped_or_frame_alias_pointers_never_read_storage(
    source, destination
):
    result = check(inputs(0, source=source, destination=destination))
    assert result["source_snapshot"] == b""
    assert result["registers"]["ecx"] == source
    assert result["registers"]["eax"] == destination
    assert [row["access"] for row in result["events"]] == [
        "write",
        "read",
        "write",
        "read",
        "read",
        "read",
    ]
    assert {int(pc, 16) for pc in result["trace_rvas"]} == set(PREFIX + SUFFIX)


@pytest.mark.parametrize(
    "count,source,destination,frame,ret",
    (
        (1, 0x7FFFFFFC, 0x80001001, 0x02000103, 0x0049A921),
        (3, 0xFFFFEFE7, 0x10002FFF, 0x80000010, 0x006EB205),
        (2, 0x10001FF9, 0x80000FF9, 0xFFFFFFEB, 0x04000000),
        (1, 0x10001FF9, 0xFFFFFFF7, 8, 0x04000003),
        (1, 0xFFFFFFF7, 0x10001FF9, 0x30001003, 0x04000000),
        (3, 0x10001000, 0x10001018, 0x30001003, 0x10001030),
        (3, 0x10001018, 0x10001000, 0x30001003, 0x10001030),
    ),
)
def test_signed_crossing_uint32_edges_and_adjacent_data(
    count, source, destination, frame, ret
):
    check(
        inputs(
            count,
            source=source,
            destination=destination,
            frame=frame,
            return_address=ret,
        )
    )


@pytest.mark.parametrize(
    "which,above",
    (
        ("source", True),
        ("source", False),
        ("destination", True),
        ("destination", False),
    ),
)
def test_exact_stack_span_adjacency_and_one_byte_overlap(which, above):
    frame = 0x30001003
    at = frame + 20 if above else frame - 8 - 16
    packet = inputs(2, **{which: at})
    check(packet)
    at += -1 if above else 1
    bad = inputs(2, **{which: at})
    with pytest.raises(c.ScalarCloneError, match="overlap"):
        c.apply(**bad)


@pytest.mark.parametrize("which", ("source", "destination"))
def test_return_at_data_end_allowed_but_last_data_byte_rejected(which):
    packet = inputs(2)
    packet["return_address"] = packet[which] + 16
    store(packet["pages"], packet["registers"]["esp"], packet["return_address"])
    check(packet)
    packet["return_address"] -= 1
    store(packet["pages"], packet["registers"]["esp"], packet["return_address"])
    with pytest.raises(c.ScalarCloneError, match="return"):
        c.apply(**packet)


@pytest.mark.parametrize("value", (0, 1, 0xFFFFFFFF, 0x80000000))
def test_all_arbitrary_gpr_xmm_values_except_selected_pointer_registers(value):
    packet = inputs(17)
    for name in GPR:
        if name not in ("esp", "ecx", "edx"):
            packet["registers"][name] = value
    for i, name in enumerate(XMM):
        packet["xmm"][name] = (value << 96) | (value << 64) | (value << 32) | value ^ i
    check(packet)


@pytest.mark.parametrize("count", (0, 1, 3))
@pytest.mark.parametrize("word", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_unused_caller_words_preserve_arbitrary_uint32_values(count, word):
    packet = inputs(count)
    frame = packet["registers"]["esp"]
    for offset in (8, 12, 16):
        store(packet["pages"], frame + offset, word)
    result = check(packet)
    assert all(
        int.from_bytes(read(result["pages"], frame + offset, 4), "little") == word
        for offset in (8, 12, 16)
    )
    assert not any(
        row["access"] == "read"
        and row["address"] in (frame + 8, frame + 12, frame + 16)
        for row in result["events"]
    )


@pytest.mark.parametrize("word", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_last_copied_dword_controls_ecx_and_not_prior_record(word):
    packet = inputs(3)
    store(packet["pages"], packet["source"] + 20, word)
    result = check(packet)
    assert result["registers"]["ecx"] == word
    assert result["registers"]["edx"] == packet["source"] + 24


@pytest.mark.parametrize(
    "field", ("source", "destination", "return_address", "entry_flags")
)
@pytest.mark.parametrize("value", (True, False, -1, 2**32, 1.0, "1", None))
def test_uint32_argument_type_and_range_rejections(field, value):
    packet = inputs()
    packet[field] = value
    with pytest.raises(c.ScalarCloneError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "container,names,limit", (("registers", GPR, 2**32), ("xmm", XMM, 2**128))
)
@pytest.mark.parametrize(
    "bad",
    ("missing", "extra", "bool", "negative", "wrap", "float", "mutable", "key_type"),
)
def test_exact8_typed_gpr_and_xmm_schemas(container, names, limit, bad):
    packet = inputs()
    if bad == "missing":
        del packet[container][names[0]]
    elif bad == "extra":
        packet[container]["unknown"] = 0
    elif bad == "bool":
        packet[container][names[0]] = True
    elif bad == "negative":
        packet[container][names[0]] = -1
    elif bad == "wrap":
        packet[container][names[0]] = limit
    elif bad == "float":
        packet[container][names[0]] = 1.0
    elif bad == "mutable":
        packet[container] = list(packet[container].values())
    else:

        class Alias(str):
            pass

        packet[container] = {Alias(k): v for k, v in packet[container].items()}
    with pytest.raises(c.ScalarCloneError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "bad",
    (
        "empty",
        "list",
        "bool_key",
        "float_key",
        "unaligned",
        "negative",
        "wrap",
        "bytearray",
        "short",
        "long",
        "memoryview",
        "text",
    ),
)
def test_complete_immutable_aligned_page_schema(bad):
    packet = inputs()
    key = next(iter(packet["pages"]))
    raw = packet["pages"][key]
    if bad == "empty":
        packet["pages"] = {}
    elif bad == "list":
        packet["pages"] = list(packet["pages"].items())
    elif bad in ("bool_key", "float_key", "unaligned", "negative", "wrap"):
        del packet["pages"][key]
        replacement = {
            "bool_key": False,
            "float_key": float(key),
            "unaligned": key + 1,
            "negative": -4096,
            "wrap": 2**32,
        }[bad]
        packet["pages"][replacement] = raw
    else:
        packet["pages"][key] = {
            "bytearray": bytearray(raw),
            "short": raw[:-1],
            "long": raw + b"x",
            "memoryview": memoryview(raw),
            "text": "x" * 4096,
        }[bad]
    with pytest.raises(c.ScalarCloneError):
        c.apply(**packet)


@pytest.mark.parametrize("flag", (0, 4, 0x400, 0x402, 0x10002, 0x20002, 0xFFFFFFFF))
def test_df_rf_vm_reserved_and_missing_bit1_flags_rejected(flag):
    packet = inputs(flags=flag)
    with pytest.raises(c.ScalarCloneError, match="flags"):
        c.apply(**packet)


@pytest.mark.parametrize(
    "bad",
    (
        "ecx",
        "end_before",
        "stride",
        "caller_return",
        "caller_destination",
        "null_source",
        "null_destination",
        "destination_wrap",
        "stack_low",
        "stack_high",
        "source_unmapped",
        "destination_unmapped",
        "stack_unmapped",
        "data_same",
        "data_partial",
        "return_zero",
        "return_stack",
        "return_scalar_body",
    ),
)
def test_installed_words_geometry_no_wrap_disjointness_and_mapping(bad):
    packet = inputs()
    frame = packet["registers"]["esp"]
    if bad == "ecx":
        packet["registers"]["ecx"] ^= 1
    elif bad == "end_before":
        packet["registers"]["edx"] = packet["source"] - 1
    elif bad == "stride":
        packet["registers"]["edx"] += 1
    elif bad == "caller_return":
        store(packet["pages"], frame, packet["return_address"] ^ 1)
    elif bad == "caller_destination":
        store(packet["pages"], frame + 4, packet["destination"] ^ 1)
    elif bad == "null_source":
        packet = inputs(2, source=0)
    elif bad == "null_destination":
        packet = inputs(2, destination=0)
    elif bad == "destination_wrap":
        packet["destination"] = 0xFFFFFFF8
        store(packet["pages"], frame + 4, packet["destination"])
    elif bad == "stack_low":
        packet = inputs(0, frame=7)
    elif bad == "stack_high":
        packet = inputs(0, frame=0xFFFFFFEC)
    elif bad == "source_unmapped":
        del packet["pages"][packet["source"] & ~4095]
    elif bad == "destination_unmapped":
        del packet["pages"][packet["destination"] & ~4095]
    elif bad == "stack_unmapped":
        del packet["pages"][(frame - 8) & ~4095]
    elif bad == "data_same":
        packet = inputs(2, destination=packet["source"])
    elif bad == "data_partial":
        packet = inputs(2, destination=packet["source"] + 15)
    elif bad == "return_zero":
        packet = inputs(return_address=0)
    elif bad == "return_stack":
        packet = inputs(return_address=frame - 1)
    elif bad == "return_scalar_body":
        packet = inputs(return_address=0x0048ABA0)
    with pytest.raises(c.ScalarCloneError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "page", (0x0048A000, 0x0049A000, 0x00757000, 0x00779000, 0x00789000)
)
def test_all_selected_dependency_code_pages_excluded_even_unread(page):
    packet = inputs(0, source=0, destination=0)
    packet["pages"][page] = bytes([0x93]) * 4096
    with pytest.raises(c.ScalarCloneError, match="code"):
        c.apply(**packet)


def test_exact10_packet_and_no_input_output_or_cross_call_mutable_aliases():
    packet = inputs(3)
    before = copy.deepcopy(packet)
    first = check(packet)
    second = c.apply(**packet)
    first["registers"]["ebx"] ^= 1
    first["xmm"]["xmm7"] ^= 1
    first["events"][0]["value"] ^= 1
    first["events"].append(dict(access="write", address=1, width=4, value=1))
    first["trace_rvas"].clear()
    first["pages"][0x19000000] = bytes(4096)
    equal(second, independent(before))
    equal(packet, before)
    packet["registers"]["eax"] ^= 1
    packet["xmm"]["xmm7"] ^= 1
    packet["pages"][0x19000000] = bytes(4096)
    equal(second, independent(before))


def test_keyword_only_exact_actual_page_api_and_static_source_anchor():
    signature = inspect.signature(c.apply)
    assert tuple(signature.parameters) == (
        "pages",
        "registers",
        "xmm",
        "source",
        "destination",
        "return_address",
        "entry_flags",
    )
    assert all(
        p.kind is inspect.Parameter.KEYWORD_ONLY for p in signature.parameters.values()
    )
    assert c.BODY_SIZE == 43
    assert (
        c.BODY_SHA256
        == "92494ea2dfd86d06ce373c9837f55d42e6c62746bd9c2c3c26d2a8af6abe938b"
    )
    packet = inputs()
    with pytest.raises(TypeError):
        c.apply(**packet, count=2)
    with pytest.raises(TypeError):
        c.apply(packet)
