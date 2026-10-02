"""Mode-three assertion parent dispatch, stopped before the selected opaque child."""

from __future__ import annotations

import copy

BASE = 0x00400000
PARENT = 0x00379CC2
FIRST = 0x0038E392
SECOND = 0x0038C89F
THIRD = 0x00379550
FOURTH = 0x00379B31
FIRST_GLOBAL = 0x008B7534
SECOND_GLOBAL = 0x008B7318
REGISTERS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
SOURCE_PINS = {
    "parent": (
        "pe_native_assertion_helper_static_boundary",
        "beeebb2dadd0ef2a77742f9296760fd09afe5c566c7b46bf36d2dd3cf8e441b4",
    ),
    "first": (
        "pe_native_assertion_helper_first_callee_static_boundary",
        "e99d2b76879c1456c6ec44bf3fcbc38f2f50a456aae6416687f0cf1f09898da0",
    ),
    "second": (
        "pe_native_assertion_helper_second_callee_static_boundary",
        "ad26b7dddb2996fd69b53937de0ae8bdb6d694982df62c280c4a03430895e0d7",
    ),
}
CODE_SPANS = (
    (BASE + PARENT, 72),
    (BASE + FIRST, 63),
    (BASE + SECOND, 6),
    (BASE + THIRD, 1),
    (BASE + FOURTH, 1),
)


class AssertionParentDispatchError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise AssertionParentDispatchError(message)


def _word(value, label):
    _require(type(value) is int and 0 <= value <= 0xFFFFFFFF, label + " must be uint32")


def _comparison_one(value):
    """Defined flags from uint32 value minus one; input DF is separately preserved."""
    result = (value - 1) & 0xFFFFFFFF
    return (
        int(value == 0)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | (int((value & 15) == 0) << 4)
        | (int(result == 0) << 6)
        | ((result >> 31) << 7)
        | (int(value == 0x80000000) << 11)
    )


def apply(
    *,
    registers,
    entry,
    condition,
    file,
    line,
    caller_return,
    first_global,
    second_global,
    pages,
    entry_flags=0x246,
):
    """Return detached GPR/page/event laws for this exact mode-three parent.

    The condition/file/line/return words are opaque uint32 values, never
    dereferenced here. Getter values are typed uint32 inputs reflected at their
    two fixed addresses. Entry flags are a strict uint32 with clear DF.
    CMP/TEST preserve that clear DF; TEST leaves AF unclaimed. No other entry
    flag bit selects the fixed mode-three path.
    """
    _require(
        type(registers) is dict and set(registers) == set(REGISTERS),
        "invalid register schema",
    )
    for name, value in registers.items():
        _word(value, name)
    for name, value in (
        ("entry", entry),
        ("condition", condition),
        ("file", file),
        ("line", line),
        ("caller_return", caller_return),
        ("first_global", first_global),
        ("second_global", second_global),
    ):
        _word(value, name)
    _require(
        type(entry_flags) is int
        and 0 <= entry_flags <= 0xFFFFFFFF
        and entry_flags & 0x400 == 0,
        "invalid entry flags or DF",
    )
    alternate = first_global == 1 or (first_global == 0 and second_global == 1)
    lowest = entry - (24 if alternate else 28)
    _require(
        lowest >= 0 and entry <= 0xFFFFFFF0 and registers["esp"] == entry,
        "invalid assertion stack extent",
    )
    _require(
        all(
            entry + 16 <= address or address + width <= lowest
            for address, width in CODE_SPANS + ((FIRST_GLOBAL, 4), (SECOND_GLOBAL, 4))
        ),
        "assertion stack overlaps fixed code or globals",
    )
    _require(
        type(pages) is dict
        and bool(pages)
        and all(
            type(p) is int
            and 0 <= p <= 0xFFFFF000
            and p % 4096 == 0
            and type(data) is bytes
            and len(data) == 4096
            for p, data in pages.items()
        ),
        "invalid page schema",
    )
    needed = {address & ~4095 for address in range(lowest, entry + 16)}
    needed |= {FIRST_GLOBAL & ~4095, SECOND_GLOBAL & ~4095}
    _require(needed <= set(pages), "missing assertion memory page")
    memory = {p: bytearray(data) for p, data in pages.items()}

    def raw(address):
        return int.from_bytes(
            bytes(
                memory[(address + i) & ~4095][(address + i) & 4095] for i in range(4)
            ),
            "little",
        )

    _require(
        [raw(entry + 4 * i) for i in range(4)] == [caller_return, condition, file, line]
        and raw(FIRST_GLOBAL) == first_global
        and raw(SECOND_GLOBAL) == second_global,
        "assertion entry memory contract differs",
    )
    events = []

    def read(address, rva):
        value = raw(address)
        events.append(
            dict(access="read", address=address, width=4, value=value, rva=rva)
        )
        return value

    def write(address, value, rva):
        for index, byte in enumerate(value.to_bytes(4, "little")):
            memory[(address + index) & ~4095][(address + index) & 4095] = byte
        events.append(
            dict(access="write", address=address, width=4, value=value, rva=rva)
        )

    current = dict(registers)
    write(entry - 4, current["ebp"], 0x379CC4)
    current["ebp"] = entry - 4
    write(entry - 8, current["esi"], 0x379CC7)
    current["esi"] = read(entry, 0x379CC8)
    write(entry - 12, 3, 0x379CCB)
    write(entry - 16, BASE + 0x379CD2, 0x379CCD)
    current["esp"] = entry - 16
    first_entry = dict(current)
    write(entry - 20, current["ebp"], 0x38E394)
    current["ebp"] = entry - 20
    current["ecx"] = read(entry - 12, 0x38E397)
    _require(current["ecx"] == 3, "internal fixed getter mode differs")
    current["eax"] = read(FIRST_GLOBAL, 0x38E3A8)
    current["ebp"] = read(entry - 20, 0x38E3AD)
    _require(
        read(entry - 16, 0x38E3AE) == BASE + 0x379CD2, "internal first return differs"
    )
    current["esp"] = entry - 12
    first_return = dict(current)
    current["ecx"] = read(entry - 12, 0x379CD2)
    current["esp"] = entry - 8
    second_packet = None
    trace = [
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
    ]
    if first_global != 1:
        trace += [0x379CD8, 0x379CDA]
    if first_global == 0:
        write(entry - 12, BASE + 0x379CE1, 0x379CDC)
        current["esp"] = entry - 12
        second_entry = dict(current)
        current["eax"] = read(SECOND_GLOBAL, 0x38C89F)
        _require(
            read(entry - 12, 0x38C8A4) == BASE + 0x379CE1,
            "internal second return differs",
        )
        current["esp"] = entry - 8
        second_packet = dict(
            entry_registers=second_entry,
            return_registers=dict(current),
            global_address=SECOND_GLOBAL,
            value=second_global,
            return_address=BASE + 0x379CE1,
            flags=0x44,
            flag_mask=0xCC5,
        )
        trace += [0x379CDC, 0x38C89F, 0x38C8A4, 0x379CE1, 0x379CE4]
    if first_global not in (0, 1):
        flags = (int((first_global & 255).bit_count() % 2 == 0) << 2) | (
            (first_global >> 31) << 7
        )
        flag_mask = 0xCC5
    else:
        flags = _comparison_one(current["eax"])
        flag_mask = 0xCD5

    if alternate:
        argument_sites = (0x379CFB, 0x379CFE, 0x379D01)
        call_site, return_address, target = 0x379D04, BASE + 0x379D09, FOURTH
        arguments = [condition, file, line]
        push_order = [line, file, condition]
        scratch = entry - 8
    else:
        write(entry - 12, current["esi"], 0x379CE6)
        argument_sites = (0x379CE7, 0x379CEA, 0x379CED)
        call_site, return_address, target = 0x379CF0, BASE + 0x379CF5, THIRD
        arguments = [condition, file, line, caller_return]
        push_order = [caller_return, line, file, condition]
        scratch = entry - 12
        trace += [0x379CE6]
    for address, rva in zip((entry + 12, entry + 8, entry + 4), argument_sites):
        value = read(address, rva)
        scratch -= 4
        write(scratch, value, rva)
    scratch -= 4
    write(scratch, return_address, call_site)
    current["esp"] = scratch
    trace += list(argument_sites) + [call_site]
    return copy.deepcopy(
        dict(
            schema_version=1,
            mode=3,
            branch="alternate" if alternate else "normal",
            endpoint=BASE + target,
            registers=current,
            flags=flags,
            flag_mask=flag_mask,
            call=dict(
                target_rva=target,
                target=BASE + target,
                call_site_rva=call_site,
                return_address=return_address,
                entry_esp=scratch,
                arguments=arguments,
                push_order=push_order,
            ),
            first_getter=dict(
                mode=3,
                global_address=FIRST_GLOBAL,
                value=first_global,
                entry_registers=first_entry,
                return_registers=first_return,
                return_address=BASE + 0x379CD2,
                flags=0x44,
                flag_mask=0xCD5,
            ),
            second_getter=second_packet,
            events=events,
            trace_rvas=trace,
            pages={p: bytes(data) for p, data in memory.items()},
            stack_extent=[lowest, entry + 16],
            entry_words=[caller_return, condition, file, line],
            global_writes=[],
            preserved_registers=["ebx", "edx", "edi"],
            opaque_child_executed=False,
        )
    )


def apply_to_pages(*, registers, pages, entry_flags=0x246):
    """Adapt actual retained caller Q without fixing alignment or caller words.

    Q is the supplied ESP. Its four words and the two fixed globals are read
    as premises from typed pages. Adapter premise validation adds no executed
    event; apply describes only actual selected instruction reads and writes.
    There is no fixture construction or host patch here.
    """
    _require(
        type(registers) is dict and set(registers) == set(REGISTERS),
        "invalid register schema",
    )
    for name, value in registers.items():
        _word(value, name)
    entry = registers["esp"]
    _require(entry <= 0xFFFFFFF0, "invalid assertion stack extent")
    _require(
        type(pages) is dict
        and bool(pages)
        and all(
            type(p) is int
            and 0 <= p <= 0xFFFFF000
            and p % 4096 == 0
            and type(data) is bytes
            and len(data) == 4096
            for p, data in pages.items()
        ),
        "invalid page schema",
    )

    def read_word(address):
        _require(
            all(((address + i) & ~4095) in pages for i in range(4)),
            "missing assertion memory page",
        )
        return int.from_bytes(
            bytes(pages[(address + i) & ~4095][(address + i) & 4095] for i in range(4)),
            "little",
        )

    return apply(
        registers=registers,
        entry=entry,
        condition=read_word(entry + 4),
        file=read_word(entry + 8),
        line=read_word(entry + 12),
        caller_return=read_word(entry),
        first_global=read_word(FIRST_GLOBAL),
        second_global=read_word(SECOND_GLOBAL),
        pages=pages,
        entry_flags=entry_flags,
    )
