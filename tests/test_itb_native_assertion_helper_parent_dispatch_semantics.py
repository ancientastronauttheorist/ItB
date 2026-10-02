"""Independent fixed-mode getter, parent frame and opaque-call boundary laws."""

import copy

import pytest

from src.observatory import native_assertion_helper_parent_dispatch_semantics as m

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
FIRST_ADDRESS, SECOND_ADDRESS = 0x008B7534, 0x008B7318


def patch(pages, address, value):
    for i, byte in enumerate(value.to_bytes(4, "little")):
        page = (address + i) & ~4095
        data = bytearray(pages[page])
        data[(address + i) & 4095] = byte
        pages[page] = bytes(data)


def word(pages, address):
    return int.from_bytes(
        bytes(pages[(address + i) & ~4095][(address + i) & 4095] for i in range(4)),
        "little",
    )


def fixture(first=0, second=0, entry=0x02001002):
    pages = {
        page: bytes(
            ((i * 31 + (page >> 12) * 17) ^ (i >> 4)) & 255 for i in range(4096)
        )
        for page in {
            address & ~4095
            for address in range(max(0, entry - 28), min(2**32, entry + 16))
        }
        | {0x008B7000, 0x05000000}
    }
    registers = {name: 0x12340000 + i * 0x1111 for i, name in enumerate(GPR)}
    registers["esp"] = entry
    arguments = dict(
        registers=registers,
        entry=entry,
        condition=0x0830ABCD,
        file=0x08F0EF01,
        line=0xFFFFFFFF,
        caller_return=0x0078A5C3,
        first_global=first,
        second_global=second,
        pages=pages,
        entry_flags=0x246,
    )
    for address, value in (
        (entry, arguments["caller_return"]),
        (entry + 4, arguments["condition"]),
        (entry + 8, arguments["file"]),
        (entry + 12, arguments["line"]),
        (FIRST_ADDRESS, first),
        (SECOND_ADDRESS, second),
    ):
        if address + 4 <= 2**32:
            patch(pages, address, value)
    return arguments


def independent_events(arguments):
    s = arguments["entry"]
    initial = arguments["registers"]
    first, second = arguments["first_global"], arguments["second_global"]
    alt = first == 1 or (first == 0 and second == 1)
    rows = [
        ("write", s - 4, initial["ebp"], 0x379CC4),
        ("write", s - 8, initial["esi"], 0x379CC7),
        ("read", s, arguments["caller_return"], 0x379CC8),
        ("write", s - 12, 3, 0x379CCB),
        ("write", s - 16, 0x00779CD2, 0x379CCD),
        ("write", s - 20, s - 4, 0x38E394),
        ("read", s - 12, 3, 0x38E397),
        ("read", FIRST_ADDRESS, first, 0x38E3A8),
        ("read", s - 20, s - 4, 0x38E3AD),
        ("read", s - 16, 0x00779CD2, 0x38E3AE),
        ("read", s - 12, 3, 0x379CD2),
    ]
    if first == 0:
        rows += [
            ("write", s - 12, 0x00779CE1, 0x379CDC),
            ("read", SECOND_ADDRESS, second, 0x38C89F),
            ("read", s - 12, 0x00779CE1, 0x38C8A4),
        ]
    if alt:
        rows += [
            ("read", s + 12, arguments["line"], 0x379CFB),
            ("write", s - 12, arguments["line"], 0x379CFB),
            ("read", s + 8, arguments["file"], 0x379CFE),
            ("write", s - 16, arguments["file"], 0x379CFE),
            ("read", s + 4, arguments["condition"], 0x379D01),
            ("write", s - 20, arguments["condition"], 0x379D01),
            ("write", s - 24, 0x00779D09, 0x379D04),
        ]
    else:
        rows += [
            ("write", s - 12, arguments["caller_return"], 0x379CE6),
            ("read", s + 12, arguments["line"], 0x379CE7),
            ("write", s - 16, arguments["line"], 0x379CE7),
            ("read", s + 8, arguments["file"], 0x379CEA),
            ("write", s - 20, arguments["file"], 0x379CEA),
            ("read", s + 4, arguments["condition"], 0x379CED),
            ("write", s - 24, arguments["condition"], 0x379CED),
            ("write", s - 28, 0x00779CF5, 0x379CF0),
        ]
    return rows


@pytest.mark.parametrize(
    "first", (0, 1, 2, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFF)
)
@pytest.mark.parametrize(
    "second", (0, 1, 2, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFF)
)
def test_all_getter_dispatches_match_independent_arguments_registers_events_and_pages(
    first, second
):
    arguments = fixture(first, second)
    before = copy.deepcopy(arguments)
    result = m.apply(**arguments)
    alt = first == 1 or first == 0 and second == 1
    s = arguments["entry"]
    sp = s - (24 if alt else 28)
    eax = second if first == 0 else first
    expected_gpr = dict(
        arguments["registers"],
        eax=eax,
        ecx=3,
        esi=arguments["caller_return"],
        ebp=s - 4,
        esp=sp,
    )
    assert result["registers"] == expected_gpr
    assert result["branch"] == ("alternate" if alt else "normal")
    assert result["mode"] == result["first_getter"]["mode"] == 3
    assert result["endpoint"] == (0x00779B31 if alt else 0x00779550)
    assert result["call"] == dict(
        target_rva=0x379B31 if alt else 0x379550,
        target=0x00779B31 if alt else 0x00779550,
        call_site_rva=0x379D04 if alt else 0x379CF0,
        return_address=0x00779D09 if alt else 0x00779CF5,
        entry_esp=sp,
        arguments=[arguments["condition"], arguments["file"], arguments["line"]]
        + ([] if alt else [arguments["caller_return"]]),
        push_order=([] if alt else [arguments["caller_return"]])
        + [arguments["line"], arguments["file"], arguments["condition"]],
    )
    expected_rows = independent_events(arguments)
    actual_rows = [
        (row["access"], row["address"], row["value"], row["rva"])
        for row in result["events"]
    ]
    assert actual_rows == expected_rows
    assert all(
        set(row) == {"access", "address", "width", "value", "rva"} and row["width"] == 4
        for row in result["events"]
    )
    expected_pages = copy.deepcopy(arguments["pages"])
    for access, address, value, _ in expected_rows:
        if access == "write":
            patch(expected_pages, address, value)
    assert result["pages"] == expected_pages
    assert [
        word(result["pages"], sp + 4 * i)
        for i in range(1 + len(result["call"]["arguments"]))
    ] == [result["call"]["return_address"], *result["call"]["arguments"]]
    assert [word(result["pages"], s + 4 * i) for i in range(4)] == [
        arguments["caller_return"],
        arguments["condition"],
        arguments["file"],
        arguments["line"],
    ]
    assert word(result["pages"], FIRST_ADDRESS) == first
    assert word(result["pages"], SECOND_ADDRESS) == second
    assert result["global_writes"] == []
    assert result["opaque_child_executed"] is False
    assert result["pages"][0x05000000] == arguments["pages"][0x05000000]
    assert result["stack_extent"] == [sp, s + 16]
    assert arguments == before


@pytest.mark.parametrize(
    "first", (1, 2, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFF)
)
def test_nonzero_first_never_reads_second_or_changes_when_second_value_is_poisoned(
    first,
):
    packets = []
    for second in (0, 1, 2, 0xFFFFFFFF):
        packet = m.apply(**fixture(first, second))
        assert packet["second_getter"] is None
        assert not any(row["address"] == SECOND_ADDRESS for row in packet["events"])
        assert (
            0x38C89F not in packet["trace_rvas"]
            and 0x379CDC not in packet["trace_rvas"]
        )
        packets.append(
            {
                key: packet[key]
                for key in (
                    "call",
                    "registers",
                    "branch",
                    "flags",
                    "flag_mask",
                    "events",
                    "trace_rvas",
                )
            }
        )
    assert all(packet == packets[0] for packet in packets)


@pytest.mark.parametrize(
    "first,second,flags,mask",
    (
        (1, 0, 0x44, 0xCD5),
        (2, 1, 0, 0xCC5),
        (0xFFFFFFFF, 1, 0x84, 0xCC5),
        (0x80000000, 0, 0x84, 0xCC5),
        (0, 0, 0x95, 0xCD5),
        (0, 1, 0x44, 0xCD5),
        (0, 2, 0, 0xCD5),
        (0, 0xFFFFFFFF, 0x80, 0xCD5),
        (0, 0x80000000, 0x814, 0xCD5),
        (0, 0x80000001, 0x84, 0xCD5),
        (0, 0x7FFFFFFF, 0, 0xCD5),
        (0x80000001, 0, 0x80, 0xCC5),
        (0x7FFFFFFF, 0, 0x4, 0xCC5),
    ),
)
def test_defined_flags_include_preserved_clear_df_and_leave_test_af_unclaimed(
    first, second, flags, mask
):
    result = m.apply(**fixture(first, second))
    assert (result["flags"], result["flag_mask"]) == (flags, mask)
    assert result["flag_mask"] & 0x400 and result["flags"] & 0x400 == 0
    assert bool(result["flag_mask"] & 0x10) == (first in (0, 1))
    assert result["first_getter"]["flags"] == 0x44
    assert result["first_getter"]["flag_mask"] == 0xCD5


def test_actual_getter_frames_and_ordered_reachable_instruction_frontiers():
    arguments = fixture(0, 1)
    result = m.apply(**arguments)
    s = arguments["entry"]
    assert result["first_getter"]["entry_registers"] == dict(
        arguments["registers"],
        ebp=s - 4,
        esi=arguments["caller_return"],
        esp=s - 16,
    )
    assert result["first_getter"]["return_registers"] == dict(
        arguments["registers"],
        eax=0,
        ecx=3,
        ebp=s - 4,
        esi=arguments["caller_return"],
        esp=s - 12,
    )
    assert result["second_getter"]["entry_registers"] == dict(
        arguments["registers"],
        eax=0,
        ecx=3,
        ebp=s - 4,
        esi=arguments["caller_return"],
        esp=s - 12,
    )
    assert result["second_getter"]["return_registers"] == dict(
        arguments["registers"],
        eax=1,
        ecx=3,
        ebp=s - 4,
        esi=arguments["caller_return"],
        esp=s - 8,
    )
    assert result["trace_rvas"] == [
        0x379CC2,
        0x379CC4,
        0x379CC5,
        0x379CC7,
        0x379CC8,
        0x379CCB,
        0x379CCD,
        0x38E392,
        0x38E394,
        0x38E395,
        0x38E397,
        0x38E39A,
        0x38E39C,
        0x38E39E,
        0x38E3A1,
        0x38E3A3,
        0x38E3A6,
        0x38E3A8,
        0x38E3AD,
        0x38E3AE,
        0x379CD2,
        0x379CD3,
        0x379CD6,
        0x379CD8,
        0x379CDA,
        0x379CDC,
        0x38C89F,
        0x38C8A4,
        0x379CE1,
        0x379CE4,
        0x379CFB,
        0x379CFE,
        0x379D01,
        0x379D04,
    ]
    assert not any(
        pc in result["trace_rvas"]
        for pc in (
            0x38E3AF,
            0x38E3BC,
            0x38E3C7,
            0x379CF5,
            0x379CF8,
            0x379CF9,
            0x379CFA,
            0x379D09,
            0x379550,
            0x379B31,
        )
    )


@pytest.mark.parametrize(
    "field",
    (
        "entry",
        "condition",
        "file",
        "line",
        "caller_return",
        "first_global",
        "second_global",
    ),
)
@pytest.mark.parametrize("bad", (False, True, -1, 2**32, 1.0, None))
def test_all_input_words_are_strict_uint32_even_for_skipped_second_getter(field, bad):
    arguments = fixture(2, 0)
    arguments[field] = bad
    with pytest.raises(m.AssertionParentDispatchError):
        m.apply(**arguments)


@pytest.mark.parametrize("register", GPR)
def test_all_eight_input_register_words_are_strict(register):
    arguments = fixture()
    arguments["registers"][register] = False
    with pytest.raises(m.AssertionParentDispatchError):
        m.apply(**arguments)


@pytest.mark.parametrize(
    "kind",
    (
        "register_missing",
        "register_extra",
        "register_tuple",
        "esp_mismatch",
        "flags_bool",
        "flags_df",
        "flags_negative",
        "flags_wide",
        "pages_tuple",
        "page_bool",
        "page_alignment",
        "page_wrap",
        "page_bytearray",
        "page_short",
        "page_missing",
        "caller_memory",
        "condition_memory",
        "file_memory",
        "line_memory",
        "first_global_memory",
        "second_global_memory",
    ),
)
def test_closed_input_memory_and_register_contracts_reject(kind):
    arguments = fixture(2, 1)
    if kind == "register_missing":
        arguments["registers"].pop("eax")
    elif kind == "register_extra":
        arguments["registers"]["eip"] = 0
    elif kind == "register_tuple":
        arguments["registers"] = tuple(arguments["registers"].items())
    elif kind == "esp_mismatch":
        arguments["registers"]["esp"] += 1
    elif kind.startswith("flags_"):
        arguments["entry_flags"] = {
            "flags_bool": True,
            "flags_df": 0x646,
            "flags_negative": -1,
            "flags_wide": 2**32,
        }[kind]
    elif kind == "pages_tuple":
        arguments["pages"] = tuple(arguments["pages"].items())
    elif kind == "page_bool":
        arguments["pages"][False] = bytes(4096)
    elif kind == "page_alignment":
        arguments["pages"][0x05000001] = bytes(4096)
    elif kind == "page_wrap":
        arguments["pages"][2**32] = bytes(4096)
    elif kind in ("page_bytearray", "page_short"):
        arguments["pages"][0x05000000] = (
            bytearray(4096) if kind == "page_bytearray" else bytes(4095)
        )
    elif kind == "page_missing":
        arguments["pages"].pop(arguments["entry"] & ~4095)
    else:
        address = {
            "caller_memory": arguments["entry"],
            "condition_memory": arguments["entry"] + 4,
            "file_memory": arguments["entry"] + 8,
            "line_memory": arguments["entry"] + 12,
            "first_global_memory": FIRST_ADDRESS,
            "second_global_memory": SECOND_ADDRESS,
        }[kind]
        patch(arguments["pages"], address, word(arguments["pages"], address) ^ 1)
    with pytest.raises(m.AssertionParentDispatchError):
        m.apply(**arguments)


@pytest.mark.parametrize("first,depth", ((1, 24), (2, 28)))
def test_stack_address_edges_and_opaque_words_allow_zero_and_maximum(first, depth):
    for s in (depth, 0xFFFFFFF0, 0x02000FFF, 0x02001001):
        arguments = fixture(first, 0, s)
        assert m.apply(**arguments)["registers"]["esp"] == s - depth
    for s in (depth - 1, 0xFFFFFFF1):
        arguments = fixture(first, 0, s)
        with pytest.raises(m.AssertionParentDispatchError):
            m.apply(**arguments)
    arguments = fixture(first, 0)
    for name, offset, value in (
        ("caller_return", 0, 0),
        ("condition", 4, 0),
        ("file", 8, 0xFFFFFFFF),
        ("line", 12, 0),
    ):
        arguments[name] = value
        patch(arguments["pages"], arguments["entry"] + offset, value)
    assert m.apply(**arguments)["call"]["arguments"][:3] == [0, 0xFFFFFFFF, 0]


@pytest.mark.parametrize("first,depth", ((1, 24), (2, 28)))
@pytest.mark.parametrize(
    "address,width", ((FIRST_ADDRESS, 4), (SECOND_ADDRESS, 4), (0x00779CC2, 72))
)
def test_stack_disjoint_fixed_spans_allow_adjacency_but_reject_one_byte_overlap(
    first, depth, address, width
):
    for s in (address - 16, address + width + depth):
        arguments = fixture(first, 0, s)
        assert m.apply(**arguments)["stack_extent"] == [s - depth, s + 16]
    for s in (address - 15, address + width + depth - 1):
        arguments = fixture(first, 0, s)
        with pytest.raises(m.AssertionParentDispatchError, match="overlaps"):
            m.apply(**arguments)


def test_all_mutable_output_packets_are_detached_and_inputs_are_untouched():
    arguments = fixture(0, 1)
    before = copy.deepcopy(arguments)
    first = m.apply(**arguments)
    second = m.apply(**arguments)
    first["registers"]["eax"] ^= 1
    first["call"]["arguments"].append(0)
    first["first_getter"]["entry_registers"]["edx"] ^= 1
    first["second_getter"]["return_registers"]["esi"] ^= 1
    first["events"][0]["value"] ^= 1
    first["trace_rvas"].clear()
    first["pages"].clear()
    first["stack_extent"].clear()
    assert arguments == before
    assert second == m.apply(**arguments)


@pytest.mark.parametrize("entry", (0x02000FEF, 0x02001001, 0x02001002, 0x0200100F))
@pytest.mark.parametrize(
    "first,second", ((0, 1), (0, 0x80000000), (1, 0xFFFFFFFF), (2, 1))
)
@pytest.mark.parametrize("flags", (0, 0x44, 0x54, 0x246, 0x247, 0xFFFFFBFF))
def test_actual_caller_page_adapter_accepts_unaligned_Q_and_entry_AF_variation(
    entry, first, second, flags
):
    arguments = fixture(first, second, entry)
    arguments["entry_flags"] = flags
    before = copy.deepcopy(arguments)
    expected = m.apply(**arguments)
    result = m.apply_to_pages(
        registers=arguments["registers"],
        pages=arguments["pages"],
        entry_flags=flags,
    )
    assert result == expected
    assert result["flags"] & 0x400 == 0
    assert arguments == before


def test_actual_caller_adapter_derives_opaque_words_and_globals_from_retained_pages():
    arguments = fixture(0, 0)
    for address, value in (
        (arguments["entry"], 0xDEADBEEF),
        (arguments["entry"] + 4, 0),
        (arguments["entry"] + 8, 0xFFFFFFFF),
        (arguments["entry"] + 12, 17),
        (FIRST_ADDRESS, 0),
        (SECOND_ADDRESS, 1),
    ):
        patch(arguments["pages"], address, value)
    result = m.apply_to_pages(
        registers=arguments["registers"], pages=arguments["pages"], entry_flags=0x54
    )
    assert result["branch"] == "alternate"
    assert result["entry_words"] == [0xDEADBEEF, 0, 0xFFFFFFFF, 17]
    assert result["call"]["arguments"] == [0, 0xFFFFFFFF, 17]
    assert result["registers"]["esi"] == 0xDEADBEEF
    assert result["second_getter"]["value"] == 1


@pytest.mark.parametrize(
    "kind",
    (
        "register_bool",
        "register_missing",
        "page_short",
        "page_bytearray",
        "page_missing",
        "flags_bool",
        "flags_df",
        "stack_wrap",
    ),
)
def test_actual_page_adapter_rejects_malformed_inputs_with_model_error(kind):
    arguments = fixture(0, 1)
    if kind == "register_bool":
        arguments["registers"]["eax"] = False
    elif kind == "register_missing":
        arguments["registers"].pop("ebp")
    elif kind == "page_short":
        arguments["pages"][0x008B7000] = bytes(4095)
    elif kind == "page_bytearray":
        arguments["pages"][0x008B7000] = bytearray(4096)
    elif kind == "page_missing":
        arguments["pages"].pop(0x008B7000)
    elif kind == "flags_bool":
        arguments["entry_flags"] = False
    elif kind == "flags_df":
        arguments["entry_flags"] = 0x454
    else:
        arguments["registers"]["esp"] = 0xFFFFFFF1
    with pytest.raises(m.AssertionParentDispatchError):
        m.apply_to_pages(
            registers=arguments["registers"],
            pages=arguments["pages"],
            entry_flags=arguments["entry_flags"],
        )
