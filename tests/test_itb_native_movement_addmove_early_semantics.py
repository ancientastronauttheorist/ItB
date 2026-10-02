"""Independent actual-page AddMove early-return owner/free/cookie laws."""

from __future__ import annotations
import copy
import inspect
from collections import UserDict
import pytest
from src.observatory import native_movement_addmove_early_semantics as c

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")

XMM = tuple("xmm" + str(i) for i in range(8))

PREFIX_TRACE = (
    0x257340,
    0x257341,
    0x257343,
    0x257345,
    0x25734A,
    0x257350,
    0x257351,
    0x257357,
    0x25735C,
    0x25735E,
    0x257361,
    0x257362,
    0x257363,
    0x257364,
    0x257367,
    0x25736D,
    0x25736F,
    0x257376,
    0x257379,
    0x25737C,
    0x25737E,
    0x257381,
    0x257384,
    0x257386,
    0x257388,
    0x2573F0,
    0x2573F2,
)

OWNED_TRACE = (
    0x2573F4,
    0x2573F7,
    0x2573F9,
    0x2573FB,
    0x2573FE,
    0x2573FF,
    0x257400,
    0x7800,
    0x7801,
    0x7803,
    0x7806,
    0x7809,
    0x780B,
    0x780E,
    0x7810,
    0x7816,
    0x781A,
    0x7820,
    0x784D,
    0x7850,
    0x7851,
    0x35785D,
    0x36FB17,
    0x389156,
    0x389158,
    0x389159,
    0x38915B,
    0x38915F,
    0x389161,
    0x389164,
    0x389166,
    0x38916C,
    0x389172,
    0x389174,
    0x38918E,
    0x38918F,
    0x7856,
    0x7859,
    0x785A,
    0x257405,
)

SUFFIX_TRACE = (
    0x257408,
    0x25740A,
    0x25740D,
    0x257414,
    0x257415,
    0x257416,
    0x257417,
    0x25741A,
    0x25741C,
    0x3574CA,
    0x3574D0,
    0x3574D3,
    0x257421,
    0x257423,
    0x257424,
)

BODY_RANGES = (
    (0x7800, 0x785B),
    (0x257340, 0x257427),
    (0x3574CA, 0x3574D5),
    (0x35785D, 0x357862),
    (0x36FB17, 0x36FB1C),
    (0x389156, 0x389190),
)

PACKET_KEYS = {
    "path",
    "registers",
    "xmm",
    "pages",
    "events",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "trace_rvas",
    "free_entry",
    "free_return",
    "free_packet",
    "imported",
    "cookie_entry",
}


def strict_equal(a, b):
    assert type(a) is type(b), (type(a), type(b))
    if type(a) is dict:
        assert set(a) == set(b)
        assert all(any(type(k) is type(j) and k == j for j in b) for k in a)
        for k in a:
            strict_equal(a[k], b[k])
    elif type(a) in (list, tuple):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            strict_equal(x, y)
    else:
        assert a == b


def blob(pages, address, size):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def word(pages, address):
    return int.from_bytes(blob(pages, address, 4), "little")


def install(pages, address, value):
    for i, byte in enumerate(value.to_bytes(4, "little")):
        page = (address + i) & ~4095
        data = bytearray(pages[page])
        data[(address + i) & 4095] = byte
        pages[page] = bytes(data)


def add_flags(a, b):
    result = (a + b) & 0xFFFFFFFF
    return (
        int(a + b > 0xFFFFFFFF)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | ((a ^ b ^ result) & 0x10)
        | (int(result == 0) << 6)
        | ((result >> 31) << 7)
        | (int((~(a ^ b) & (a ^ result) & 0x80000000) != 0) << 11)
    )


FLAGS = tuple(2 | v for v in range(0xAD8) if v & ~0xAD5 == 0)


def logical_test_flags(value):
    return (
        (0x40 if value == 0 else 0)
        | (0x80 if value & 0x80000000 else 0)
        | (4 if (value & 255).bit_count() % 2 == 0 else 0)
    )


def inputs(
    form="one",
    *,
    count_capacity=1,
    frame=0x30001003,
    receiver=0x10000FF9,
    source=0x06002FF9,
    return_address=0x0065773F,
    flags=0x246,
    cookie=0x19A51C73,
    seh=0x1234ABCD,
    parameter=0xBF800000,
    profile=0,
):
    begin = 0 if form == "null" else source
    end = begin + (8 if form == "one" else 0)
    capacity = begin + (8 * count_capacity if begin else 0)
    base = min((frame - 0x2B8) & ~4095, 0xFFFFE000)
    keys = {0, 0x00893000, 0x19000000}
    spans = [(base, base + 8192), (receiver, receiver + 12)]
    if begin:
        keys.update((0x06000000, 0x008B7000, 0x007D6000))
        spans.append((begin, capacity))
    for a, b in spans:
        keys.update(range(a & ~4095, ((b - 1) & ~4095) + 4096, 4096))
    pages = {
        p: bytes((i * 37 + j * 29 + profile * 71) & 255 for j in range(4096))
        for i, p in enumerate(sorted(keys))
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
    for a, v in (
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
        install(pages, a, v)
    if begin:
        install(pages, 0x008B7634, 0x12345678)
        install(pages, 0x007D621C, 0x05000000)
    return dict(
        pages=pages,
        registers=regs,
        xmm=vec,
        return_address=return_address,
        entry_flags=flags,
    )


def check(packet):
    before = copy.deepcopy(packet)
    expected = independent(packet)
    actual = c.apply(**packet)
    strict_equal(actual, expected)
    strict_equal(packet, before)
    assert set(actual) == PACKET_KEYS and len(actual) == 15
    frame = packet["registers"]["esp"]
    owned = word(packet["pages"], frame + 4) != 0
    assert len(actual["trace_rvas"]) == (82 if owned else 42)
    assert len(actual["events"]) == (50 if owned else 25)
    assert all(
        row["width"] == 4 and row["address"] != frame + 16 for row in actual["events"]
    )
    assert blob(actual["pages"], frame, 20) == blob(before["pages"], frame, 20)
    receiver = packet["registers"]["ecx"]
    assert blob(actual["pages"], receiver, 12) == blob(before["pages"], receiver, 12)
    assert actual["pages"][0x19000000] == before["pages"][0x19000000]
    assert not any(
        receiver <= row["address"] < receiver + 12 for row in actual["events"]
    )
    if owned:
        begin, capacity = (word(before["pages"], frame + k) for k in (4, 12))
        assert blob(actual["pages"], begin, capacity - begin) == blob(
            before["pages"], begin, capacity - begin
        )
        assert actual["imported"]["flag_mask"] == 0x8C5
        assert len(actual["free_packet"]) == 8
    return actual


def independent(fixture):
    initial, pages, events = dict(fixture["registers"]), dict(fixture["pages"]), []
    g, f = initial["esp"], initial["esp"] - 4
    begin, end, capacity = [word(pages, g + k) for k in (4, 8, 12)]
    cookie, seh = word(pages, 0x00893F28), word(pages, 0)
    xmms = dict(fixture["xmm"])

    def emit(access, address, value=None):
        if access == "read":
            actual = word(pages, address)
            if value is not None:
                assert actual == value
            value = actual
        else:
            install(pages, address, value)
        events.append(dict(access=access, address=address, width=4, value=value))

    def boundary(regs, endpoint, flags, mask):
        return dict(
            registers=dict(regs),
            xmm=dict(xmms),
            pages=dict(pages),
            events=copy.deepcopy(events),
            endpoint=endpoint,
            flags=flags,
            flag_mask=mask,
            df=0,
        )

    # Exact parent prologue, SEH registration and count inputs, before cleanup.
    prologue = (
        ("write", g - 4, initial["ebp"]),
        ("write", g - 8, 0xFFFFFFFF),
        ("write", g - 12, 0x007CA95E),
        ("read", 0, seh),
        ("write", g - 16, seh),
        ("read", 0x00893F28, cookie),
        ("write", g - 20, cookie ^ f),
        ("write", g - 0x280, initial["ebx"]),
        ("write", g - 0x284, initial["esi"]),
        ("write", g - 0x288, cookie ^ f),
        ("write", 0, g - 16),
        ("write", g - 8, 0),
        ("read", g + 8, end),
        ("read", g + 4, begin),
    )
    for row in prologue:
        emit(*row)
    count = (end - begin) // 8
    assert end - begin == count * 8
    regs = dict(
        initial,
        eax=count,
        ebx=initial["ebx"] & 0xFFFFFF00,
        edx=begin,
        esi=initial["ecx"],
        ebp=f,
        esp=g - 0x288,
    )
    free_entry = free_return = free_packet = imported = None
    if begin:
        emit("read", g + 12, capacity)
        capacity_count = (capacity - begin) // 8
        for address, value in (
            (g - 0x28C, 8),
            (g - 0x290, capacity_count),
            (g - 0x294, begin),
            (g - 0x298, 0x00657405),
        ):
            emit("write", address, value)
        v_sp = g - 0x298
        regs.update(ecx=capacity_count, esp=v_sp)
        free_entry = boundary(
            regs, 0x00407800, logical_test_flags(capacity_count), 0xC5
        )
        child_start = len(events)
        # Stride8 with small positive capacity selects ordinary free and DIV remainder7.
        free_rows = (
            ("write", v_sp - 4, f),
            ("read", v_sp + 8, capacity_count),
            ("read", v_sp + 12, 8),
            ("read", v_sp + 12, 8),
            ("read", v_sp + 4, begin),
            ("write", v_sp - 8, begin),
            ("write", v_sp - 12, 0x00407856),
            ("write", v_sp - 16, v_sp - 4),
            ("read", v_sp - 8, begin),
            ("read", v_sp - 8, begin),
            ("write", v_sp - 20, begin),
            ("write", v_sp - 24, 0),
            ("read", 0x008B7634, 0x12345678),
            ("write", v_sp - 28, 0x12345678),
            ("read", 0x007D621C, 0x05000000),
            ("write", v_sp - 32, 0x00789172),
        )
        for row in free_rows:
            emit(*row)
        imported = dict(
            role="free",
            entry_esp=v_sp - 32,
            words=[0x00789172, 0x12345678, 0, begin],
            **boundary(
                dict(
                    regs, eax=0x1FFFFFFF, ecx=begin, edx=7, ebp=v_sp - 16, esp=v_sp - 32
                ),
                0x05000000,
                logical_test_flags(begin),
                0x8C5,
            ),
        )
        for row in (
            ("read", v_sp - 16, v_sp - 4),
            ("read", v_sp - 12, 0x00407856),
            ("read", v_sp - 4, f),
            ("read", v_sp, 0x00657405),
        ):
            emit(*row)
        regs.update(eax=1, ecx=0xA0000001, edx=0xB0000001, esp=v_sp + 4)
        free_packet = dict(
            registers=dict(regs),
            flags=add_flags(v_sp - 8, 4),
            flag_mask=0x8D5,
            events=copy.deepcopy(events[child_start:]),
            stack=blob(pages, min((g - 0x2B8) & ~4095, 0xFFFFE000), 8192),
            error=pages[0x06000000],
            stop=0x00657405,
            protocol=dict(
                returned=True,
                result=1,
                next_kind=None,
                error_cell=None,
                last_error=None,
            ),
        )
        free_return = boundary(regs, 0x00657405, free_packet["flags"], 0x8D5)
        regs["esp"] += 12
    for row in (
        ("read", g - 16, seh),
        ("write", 0, seh),
        ("read", g - 0x288, cookie ^ f),
        ("read", g - 0x284, initial["esi"]),
        ("read", g - 0x280, initial["ebx"]),
        ("read", g - 20, cookie ^ f),
        ("write", g - 0x280, 0x00657421),
    ):
        emit(*row)
    final = dict(initial, eax=0, ecx=cookie, edx=0xB0000001 if begin else 0, esp=g + 20)
    cookie_entry = boundary(
        dict(final, ebp=f, esp=g - 0x280), 0x007574CA, logical_test_flags(cookie), 0x8C5
    )
    for row in (
        ("read", 0x00893F28, cookie),
        ("read", g - 0x280, 0x00657421),
        ("read", g - 4, initial["ebp"]),
        ("read", g, fixture["return_address"]),
    ):
        emit(*row)
    return dict(
        path=dict(
            begin=begin,
            end=end,
            capacity=capacity,
            count=count,
            parameter_bits=word(fixture["pages"], g + 16),
        ),
        registers=final,
        xmm=xmms,
        pages=pages,
        events=events,
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=fixture["return_address"],
        trace_rvas=[
            f"0x{pc:08x}"
            for pc in PREFIX_TRACE + (OWNED_TRACE if begin else ()) + SUFFIX_TRACE
        ],
        free_entry=free_entry,
        free_return=free_return,
        free_packet=free_packet,
        imported=imported,
        cookie_entry=cookie_entry,
    )


@pytest.mark.parametrize("form", ("null", "empty_owned", "one"))
@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize("profile", range(3))
def test144_original_forms_with_actual_crossing_receiver_and_nonzero_profiles(
    form, alignment, profile
):
    check(
        inputs(
            form,
            frame=0x30001000 + alignment,
            receiver=0x10000FF9 + alignment,
            source=0x06002FF9 + alignment,
            profile=profile,
        )
    )


@pytest.mark.parametrize("form", ("empty_owned", "one"))
@pytest.mark.parametrize("capacity_count", (1, 2, 3, 17, 511))
@pytest.mark.parametrize("cookie", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_capacity_based_free_empty_and_one_paths_cookie_flags_and_full_pages(
    form, capacity_count, cookie
):
    packet = inputs(form, count_capacity=capacity_count, cookie=cookie)
    result = check(packet)
    assert result["free_entry"]["registers"]["ecx"] == capacity_count
    assert result["free_entry"]["flags"] == logical_test_flags(capacity_count)
    assert result["free_entry"]["flag_mask"] == 0xC5
    assert result["cookie_entry"]["flags"] == logical_test_flags(cookie)
    assert result["cookie_entry"]["flag_mask"] == 0x8C5
    assert result["imported"]["words"] == [
        0x00789172,
        0x12345678,
        0,
        word(packet["pages"], packet["registers"]["esp"] + 4),
    ]


@pytest.mark.parametrize("flags", FLAGS)
@pytest.mark.parametrize("form", ("null", "one"))
def test_all128_ordinary_dfclear_flags_for_both_machine_paths(flags, form):
    assert len(FLAGS) == 128
    check(inputs(form, count_capacity=17, flags=flags, cookie=0))


@pytest.mark.parametrize(
    "frame,header,source,ret",
    (
        (0x000002BC, 0x10000FF9, 0x80000FF9, 0x0065773F),
        (0x02000103, 0x20000FF9, 0x06002FF9, 0xFFFFFFFF),
        (0x80000010, 0x10000FF9, 0xFFFFEFF0, 0x00400003),
        (0xFFFFFFEB, 0x10000FF9, 0x80000FF9, 0x0065773F),
        (0x30001003, 0x10000FF9, 0x7FFFFFFC, 0x00400000),
    ),
)
def test_actual_low_high_signed_crossing_frame_source_receiver_and_caller_return(
    frame, header, source, ret
):
    result = check(
        inputs(
            count_capacity=1,
            frame=frame,
            receiver=header,
            source=source,
            return_address=ret,
            cookie=0xFFFFFFFF,
        )
    )
    assert result["imported"]["flags"] == logical_test_flags(source)


@pytest.mark.parametrize(
    "which,above",
    (("receiver", True), ("receiver", False), ("source", True), ("source", False)),
)
def test_exact_active_frame_adjacency_and_one_byte_overlap(which, above):
    frame = 0x30001003
    size = 12 if which == "receiver" else 24
    at = frame + 20 if above else frame - 0x2B8 - size
    packet = inputs(count_capacity=3, **{which: at})
    check(packet)
    at += -1 if above else 1
    with pytest.raises(c.EarlyMoveError, match="overlap"):
        c.apply(**inputs(count_capacity=3, **{which: at}))


@pytest.mark.parametrize("form", ("null", "one"))
@pytest.mark.parametrize("parameter", (0, 1, 0xFFFFFFFF, 0x80000000, 0x7FC01234))
def test_ignored_parameter_is_metadata_only_no_movss_or_record_or_xmm_change(
    form, parameter
):
    packet = inputs(form, parameter=parameter)
    result = check(packet)
    assert result["path"]["parameter_bits"] == parameter
    assert result["xmm"] == packet["xmm"]
    assert not any(
        row["address"] == packet["registers"]["esp"] + 16 for row in result["events"]
    )
    assert not any(
        int(pc, 16) in (0x15B9B0, 0x7FD0, 0x80D0, 0x9A8E0, 0xC5BB0)
        for pc in result["trace_rvas"]
    )


@pytest.mark.parametrize("value", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_arbitrary_nonpointer_gprs_all8xmm_cookie_and_seh_preserved(value):
    packet = inputs(cookie=value, seh=value)
    for n in GPR:
        if n not in ("ecx", "esp"):
            packet["registers"][n] = value
    for i, n in enumerate(XMM):
        packet["xmm"][n] = (value << 96) | (value << 64) | (value << 32) | value ^ i
    check(packet)


def test_null_has_no_runtime_heap_error_or_path_mapping_premise():
    packet = inputs("null", receiver=0x06000003)
    assert 0x008B7000 not in packet["pages"] and 0x007D6000 not in packet["pages"]
    result = check(packet)
    assert all(
        result[k] is None
        for k in ("free_entry", "free_return", "free_packet", "imported")
    )
    assert result["cookie_entry"] is not None


@pytest.mark.parametrize("field", ("return_address", "entry_flags"))
@pytest.mark.parametrize("value", (True, False, -1, 2**32, 1.0, "1", None))
def test_direct_argument_bool_type_and_uint32_bounds(field, value):
    packet = inputs()
    packet[field] = value
    with pytest.raises(c.EarlyMoveError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "container,names,limit", (("registers", GPR, 2**32), ("xmm", XMM, 2**128))
)
@pytest.mark.parametrize(
    "bad",
    (
        "missing",
        "extra",
        "bool",
        "negative",
        "wrap",
        "float",
        "list",
        "facade",
        "key_type",
    ),
)
def test_exact8_gpr_xmm_types_and_key_schema(container, names, limit, bad):
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
    elif bad == "list":
        packet[container] = list(packet[container].values())
    elif bad == "facade":
        packet[container] = UserDict(packet[container])
    else:

        class Alias(str):
            pass

        packet[container] = {Alias(k): v for k, v in packet[container].items()}
    with pytest.raises(c.EarlyMoveError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "bad",
    (
        "empty",
        "list",
        "facade",
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
def test_complete_page_schema_and_immutable_bytes(bad):
    packet = inputs()
    key = next(iter(packet["pages"]))
    raw = packet["pages"][key]
    if bad == "empty":
        packet["pages"] = {}
    elif bad == "list":
        packet["pages"] = list(packet["pages"].items())
    elif bad == "facade":
        packet["pages"] = UserDict(packet["pages"])
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
    with pytest.raises(c.EarlyMoveError):
        c.apply(**packet)


@pytest.mark.parametrize("flags", (0, 4, 0x402, 0x10002, 0x20002, 0xFFFFFFFF))
def test_nonordinary_df_rf_vm_and_missing_reserved_bit_rejected(flags):
    with pytest.raises(c.EarlyMoveError):
        c.apply(**inputs(flags=flags))


@pytest.mark.parametrize(
    "bad",
    (
        "null_end",
        "null_capacity",
        "owned_empty_capacity",
        "capacity512",
        "capacity_stride",
        "size_stride",
        "count2",
        "capacity_before_end",
        "end_before_begin",
        "unmapped_capacity",
        "return_word",
        "return_zero",
        "return_frame",
        "return_source",
        "return_header",
        "return_body",
        "frame_low",
        "frame_wrap",
        "header_zero",
        "header_wrap",
        "missing_cookie",
        "missing_fs",
        "missing_error",
        "missing_heap",
        "missing_iat",
        "heap_value",
        "iat_target",
        "code_page",
        "source_cookie",
        "source_error",
        "header_source",
        "frame_error_window",
    ),
)
def test_owned_null_triplet_mapping_runtime_geometry_and_return_guards(bad):
    packet = inputs()
    g = packet["registers"]["esp"]
    begin = word(packet["pages"], g + 4)
    if bad == "null_end":
        packet = inputs("null")
        install(packet["pages"], g + 8, 8)
    elif bad == "null_capacity":
        packet = inputs("null")
        install(packet["pages"], g + 12, 8)
    elif bad == "owned_empty_capacity":
        packet = inputs("empty_owned", count_capacity=0)
    elif bad == "capacity512":
        packet = inputs(count_capacity=512)
    elif bad == "capacity_stride":
        install(packet["pages"], g + 12, begin + 9)
    elif bad == "size_stride":
        install(packet["pages"], g + 8, begin + 1)
    elif bad == "count2":
        packet = inputs(count_capacity=3)
        install(packet["pages"], g + 8, begin + 16)
    elif bad == "capacity_before_end":
        install(packet["pages"], g + 12, begin)
    elif bad == "end_before_begin":
        install(packet["pages"], g + 8, begin - 1)
    elif bad == "unmapped_capacity":
        del packet["pages"][begin & ~4095]
    elif bad == "return_word":
        install(packet["pages"], g, packet["return_address"] ^ 1)
    elif bad.startswith("return_"):
        address = {
            "return_zero": 0,
            "return_frame": g - 1,
            "return_source": begin,
            "return_header": packet["registers"]["ecx"],
            "return_body": 0x00657340,
        }[bad]
        packet = inputs(return_address=address)
    elif bad == "frame_low":
        packet = inputs("null", frame=0x2B7)
    elif bad == "frame_wrap":
        packet = inputs("null", frame=0xFFFFFFEC)
    elif bad == "header_zero":
        packet["registers"]["ecx"] = 0
    elif bad == "header_wrap":
        packet["registers"]["ecx"] = 0xFFFFFFF4
    elif bad.startswith("missing_"):
        key = {
            "missing_cookie": 0x00893000,
            "missing_fs": 0,
            "missing_error": 0x06000000,
            "missing_heap": 0x008B7000,
            "missing_iat": 0x007D6000,
        }[bad]
        del packet["pages"][key]
    elif bad == "heap_value":
        install(packet["pages"], 0x008B7634, 0x87654321)
    elif bad == "iat_target":
        install(packet["pages"], 0x007D621C, 0x05000001)
    elif bad == "code_page":
        packet["pages"][0x00657000] = bytes(4096)
    elif bad == "source_cookie":
        packet = inputs(source=0x00893F28)
    elif bad == "source_error":
        packet = inputs(source=0x06000004)
    elif bad == "header_source":
        packet = inputs(receiver=begin)
    elif bad == "frame_error_window":
        packet = inputs(frame=0x05FFFFEC)
    with pytest.raises(c.EarlyMoveError):
        c.apply(**packet)


@pytest.mark.parametrize(
    "bad",
    (
        "extra",
        "missing",
        "gpr_bool",
        "gpr_extra",
        "flags_bool",
        "mask_bool",
        "mask_value",
        "stop",
        "stop_bool",
        "stack_byte",
        "stack_type",
        "error_byte",
        "event_missing",
        "event_bool",
        "event_order",
        "event_ret",
        "protocol_result",
        "protocol_result_bool",
        "protocol_extra",
        "key_type",
        "coordinated_page_event",
    ),
)
def test_complete8_free_packet_forgery_rejected_before_installed_transport(
    monkeypatch, bad
):
    original = c.deallocator._expected

    def forged(*args, **kwargs):
        result = copy.deepcopy(original(*args, **kwargs))
        if bad == "extra":
            result["extra"] = 0
        elif bad == "missing":
            del result["events"]
        elif bad == "gpr_bool":
            result["registers"]["eax"] = True
        elif bad == "gpr_extra":
            result["registers"]["extra"] = 0
        elif bad == "flags_bool":
            result["flags"] = bool(result["flags"])
        elif bad == "mask_bool":
            result["flag_mask"] = True
        elif bad == "mask_value":
            result["flag_mask"] ^= 0x10
        elif bad == "stop":
            result["stop"] = 0x00657405
        elif bad == "stop_bool":
            result["stop"] = True
        elif bad == "stack_byte":
            raw = bytearray(result["stack"])
            raw[123] ^= 1
            result["stack"] = bytes(raw)
        elif bad == "stack_type":
            result["stack"] = bytearray(result["stack"])
        elif bad == "error_byte":
            raw = bytearray(result["error"])
            raw[99] ^= 1
            result["error"] = bytes(raw)
        elif bad == "event_missing":
            result["events"].pop()
        elif bad == "event_bool":
            result["events"][0]["width"] = True
        elif bad == "event_order":
            result["events"][0], result["events"][1] = (
                result["events"][1],
                result["events"][0],
            )
        elif bad == "event_ret":
            result["events"][-1]["value"] = 0x00657405
        elif bad == "protocol_result":
            result["protocol"]["result"] = 0
        elif bad == "protocol_result_bool":
            result["protocol"]["result"] = True
        elif bad == "protocol_extra":
            result["protocol"]["extra"] = 0
        elif bad == "key_type":

            class Alias(str):
                pass

            result = {Alias(k): v for k, v in result.items()}
        else:
            result["events"][0]["value"] ^= 1
            raw = bytearray(result["stack"])
            at = result["events"][0]["address"] - kwargs["stack_base"]
            raw[at : at + 4] = result["events"][0]["value"].to_bytes(4, "little")
            result["stack"] = bytes(raw)
        return result

    monkeypatch.setattr(c.deallocator, "_expected", forged)
    with pytest.raises(c.EarlyMoveError, match="primitive differs"):
        c.apply(**inputs(count_capacity=17))


def test_canonical_complete_free_packet_checked_before_sentinel_transport(monkeypatch):
    original = c.deallocator._expected
    calls = []

    def observed(vector, registers, stack, error, **kwargs):
        result = original(vector, registers, stack, error, **kwargs)
        calls.append(
            (copy.deepcopy(vector), dict(registers), copy.deepcopy(result), result)
        )
        return result

    monkeypatch.setattr(c.deallocator, "_expected", observed)
    packet = inputs(count_capacity=511)
    actual = check(packet)
    assert len(calls) == 1
    vector, regs, snapshot, live = calls[0]
    assert (
        vector["count"] == 511 and vector["stride"] == 8 and vector["metadata"] is None
    )
    assert vector["responses"] == [dict(kind="heap_free", eax=1)]
    assert regs["esp"] == packet["registers"]["esp"] - 0x298
    assert snapshot["events"][-1]["value"] == c.deallocator.RETURN
    assert snapshot["stop"] == c.deallocator.RETURN
    strict_equal(snapshot, live)
    assert actual["free_packet"]["events"][-1]["value"] == 0x00657405
    assert actual["free_packet"]["stop"] == 0x00657405


def test_detached_full_packet_state_pages_events_and_caller_inputs():
    packet = inputs(count_capacity=17)
    before = copy.deepcopy(packet)
    first = check(packet)
    second = c.apply(**packet)
    first["free_entry"]["registers"]["eax"] ^= 1
    first["free_return"]["xmm"]["xmm3"] ^= 1
    first["imported"]["words"][3] ^= 1
    first["free_packet"]["events"][0]["value"] ^= 1
    first["cookie_entry"]["pages"][0x19000000] = bytes(4096)
    first["path"]["parameter_bits"] ^= 1
    first["trace_rvas"].clear()
    first["events"].clear()
    strict_equal(second, independent(before))
    strict_equal(packet, before)
    packet["registers"]["eax"] ^= 1
    packet["xmm"]["xmm1"] ^= 1
    packet["pages"][0x19000000] = bytes(4096)
    strict_equal(second, independent(before))


def test_exact_actual_page_keyword_api_and_same_finite_source_receipts():
    sig = inspect.signature(c.apply)
    assert tuple(sig.parameters) == (
        "pages",
        "registers",
        "xmm",
        "return_address",
        "entry_flags",
    )
    assert all(
        p.kind is inspect.Parameter.KEYWORD_ONLY for p in sig.parameters.values()
    )
    assert len(c.BODY_PINS) == 6
    assert c.SOURCE_PINS["addmove_early"] == (
        "pe_native_movement_addmove_early_return_conformance",
        "c2448f75dc5c50f3e4de7f6bc0f412016cdb07bbe7becc491d5bd1b31f840079",
    )
    with pytest.raises(TypeError):
        c.apply(**inputs(), allocation_result=1)
    with pytest.raises(TypeError):
        c.apply(inputs())
