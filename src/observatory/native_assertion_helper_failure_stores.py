"""Independent fallback global overlay with unknown untouched memory preserved."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import capstone.x86_const as x86
from src.observatory import native_assertion_helper_failure_dispatch as dispatch
from src.observatory import windows_exception_layout as layout
from src.observatory.native_assertion_helper_descendant_pair import _witness
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _canonical_bytes,
    _canonical_sha256,
    _source_identity,
    _validate_json_tree,
    _assert_publication_safe,
    _load_executable,
    _decode_body,
    _point,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_assertion_helper_failure_stores"
SEALED_SHA256 = "9c572888c6cf4a50c4bd406c43c60cd455fdd57c59a0a57c0c832bfbbacfd240"
OWNER, START, STOP = 0x357B6A, 0x357B83, 0x357C5C
GLOBAL_START, GLOBAL_SIZE = BASE + 0x4B6000, 4096
STACK, STACK_SIZE = 0x02000000, 16384
PAIR, COOKIE, OTHER = 0x3F19F8, 0x493F28, 0x493F24
SOURCE_PINS = {
    "dispatch": (dispatch.ANALYSIS_KIND, dispatch.SEALED_SHA256),
    "frontier": dispatch.SOURCE_PINS["frontier"],
    "program_facts": dispatch.SOURCE_PINS["program_facts"],
    "layout": (layout.ANALYSIS_KIND, layout.SEALED_SHA256),
}
# Ordered global destination RVAs, byte widths and independent source labels.
FIELDS = [
    (0x4B6C28, 4, "zero_query_eax"),
    (0x4B6C24, 4, "ecx"),
    (0x4B6C20, 4, "edx"),
    (0x4B6C1C, 4, "ebx"),
    (0x4B6C18, 4, "esi"),
    (0x4B6C14, 4, "edi"),
    (0x4B6C40, 2, "ss"),
    (0x4B6C34, 2, "cs"),
    (0x4B6C10, 2, "ds"),
    (0x4B6C0C, 2, "es"),
    (0x4B6C08, 2, "fs"),
    (0x4B6C04, 2, "gs"),
    (0x4B6C38, 4, "flags"),
    (0x4B6C2C, 4, "saved_ebp"),
    (0x4B6C30, 4, "inherited_return"),
    (0x4B6C3C, 4, "frame_plus_8"),
    (0x4B6B78, 4, "context_flags"),
    (0x4B6B34, 4, "inherited_return"),
    (0x4B6B28, 4, "status_code"),
    (0x4B6B2C, 4, "one"),
    (0x4B6B38, 4, "one"),
    (0x4B6B3C, 4, "parameter_two"),
]
WRITE_SITES = [
    0x357B83,
    0x357B88,
    0x357B8E,
    0x357B94,
    0x357B9A,
    0x357BA0,
    0x357BA6,
    0x357BAD,
    0x357BB4,
    0x357BBB,
    0x357BC2,
    0x357BC9,
    0x357BD1,
    0x357BDA,
    0x357BE2,
    0x357BEA,
    0x357BF5,
    0x357C04,
    0x357C09,
    0x357C13,
    0x357C1D,
    0x357C2D,
]
STACK_WRITES = [
    (0x357BD0, -808, "flags"),
    (0x357C27, -808, "four"),
    (0x357C37, -808, "four"),
    (0x357C43, -8, "current_cookie"),
    (0x357C47, -808, "four"),
    (0x357C53, -4, "current_other"),
    (0x357C57, -808, "pair_address"),
]
READS = [
    (0x357BD1, "frame", -808, "flags"),
    (0x357BD7, "frame", 0, "saved_ebp"),
    (0x357BDF, "frame", 4, "inherited_return"),
    (0x357BEF, "frame", -804, "dead_local"),
    (0x357BFF, "global", 0x4B6C30, "inherited_return"),
    (0x357C29, "frame", -808, "four"),
    (0x357C39, "frame", -808, "four"),
    (0x357C3D, "global", COOKIE, "current_cookie"),
    (0x357C49, "frame", -808, "four"),
    (0x357C4D, "global", OTHER, "current_other"),
]
VALUE_KEYS = {
    "ecx",
    "edx",
    "ebx",
    "esi",
    "edi",
    "ss",
    "cs",
    "ds",
    "es",
    "fs",
    "gs",
    "flags",
    "saved_ebp",
    "inherited_return",
    "frame",
    "current_cookie",
    "current_other",
    "dead_local",
}
MATRIX = {
    "frame_alignments": list(range(16)),
    "input_sets": [0, 1],
    "pushed_flag_images": [0x46, 0x56, 0x246, 0x656],
    "initial_pattern_seeds": [0x31, 0xC7],
}


class FailureStoreError(RuntimeError):
    """An exact store grammar, independent memory oracle, or receipt differs."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise FailureStoreError(message)


def _normalize(fn: Any) -> Any:
    try:
        return fn()
    except FailureStoreError:
        raise
    except Exception as exc:
        raise FailureStoreError(str(exc)) from exc


def validate_values(values: Mapping[str, int]) -> None:
    _require(
        isinstance(values, Mapping) and set(values) == VALUE_KEYS,
        "store input partition differs",
    )
    _require(
        all(type(v) is int and 0 <= v <= 0xFFFFFFFF for v in values.values()),
        "store values require u32",
    )
    _require(
        all(values[n] <= 0xFFFF for n in ("ss", "cs", "ds", "es", "fs", "gs")),
        "selector values require u16",
    )
    _require(808 <= values["frame"] <= 0xFFFFFFF7, "frame arithmetic wraps")
    _require(
        values["flags"] & 0x308C7 == 0x46,
        "PUSHFD image conflicts with prior zero TEST or cleared RF and VM",
    )


def _value(source: str, values: Mapping[str, int]) -> int:
    constants = {
        "zero_query_eax": 0,
        "frame_plus_8": values["frame"] + 8,
        "context_flags": 65537,
        "status_code": 0xC0000409,
        "one": 1,
        "parameter_two": 2,
        "four": 4,
        "pair_address": BASE + PAIR,
    }
    return values[source] if source in values else constants[source]


def overlay_spec(before: bytes, values: Mapping[str, int]) -> bytes:
    """Write only specified bytes; all other bytes remain exactly as supplied."""
    _require(
        type(before) is bytes and len(before) == GLOBAL_SIZE,
        "global page buffer requires 4096 bytes",
    )
    validate_values(values)
    result = bytearray(before)
    for rva, width, source in FIELDS:
        at = BASE + rva - GLOBAL_START
        result[at : at + width] = (
            _value(source, values) & ((1 << (8 * width)) - 1)
        ).to_bytes(width, "little")
    return bytes(result)


def stack_overlay_spec(before: bytes, values: Mapping[str, int]) -> bytes:
    _require(
        type(before) is bytes and len(before) == STACK_SIZE,
        "stack buffer requires 16384 bytes",
    )
    validate_values(values)
    result = bytearray(before)
    for _, offset, source in STACK_WRITES:
        at = values["frame"] + offset - STACK
        _require(0 <= at and at + 4 <= len(result), "stack overlay outside buffer")
        result[at : at + 4] = _value(source, values).to_bytes(4, "little")
    return bytes(result)


def transfer_spec() -> dict[str, Any]:
    return {
        "entry_eax": 0,
        "entry_esp_G_offset": -804,
        "final_eax": 4,
        "final_ecx_source": "current word at global RVA 0x00493f24",
        "final_esp_G_offset": -808,
        "preserved_registers": ["edx", "ebx", "esi", "edi", "ebp"],
        "argument_at_final_esp": {
            "value_rva": f"0x{PAIR:08x}",
            "meaning": "address only; runtime pair contents are unspecified",
        },
        "stored_flags": {
            "known_mask": 0x308C7,
            "known_value": 0x46,
            "af": "undefined after TEST and unconstrained here",
            "rf_vm": "cleared in PUSHFD image",
            "other_bits": "opaque boundary image inputs",
        },
        "final_flags": "Not the stored image; IMUL defines CF and OF as zero for its zero result while SF ZF AF PF are undefined, then count-zero SHL preserves that state",
        "dead_read": {
            "instruction_rva": "0x00357bef",
            "G_offset": -804,
            "width": 4,
            "value_use": "overwritten before observable use",
        },
        "scratch_final": {
            "G_offset": -808,
            "value": "pair address replaces earlier flags and repeated four values",
        },
        "zero_fill_premise": False,
    }


def field_layout_spec() -> list[dict[str, Any]]:
    structures = layout.sdk_layout_spec()["structures"]
    result = []
    for rva, width, source in FIELDS:
        matches = [
            (name, f)
            for name, base in (("EXCEPTION_RECORD", 0x4B6B28), ("CONTEXT", 0x4B6B78))
            for f in structures[name]["fields"]
            if base + f["offset"] == rva and width <= f["width"]
        ]
        _require(len(matches) == 1, "global field layout match differs")
        name, f = matches[0]
        result.append(
            {
                "destination_rva": f"0x{rva:08x}",
                "write_width": width,
                "source": source,
                "sdk_structure": name,
                "sdk_field": f["name"],
                "sdk_field_width": f["width"],
                "remaining_field_bytes_preserved": f["width"] - width,
            }
        )
    return result


def cases() -> list[tuple[int, int, int, int]]:
    return [
        (a, i, f, p)
        for a in MATRIX["frame_alignments"]
        for i in MATRIX["input_sets"]
        for f in MATRIX["pushed_flag_images"]
        for p in MATRIX["initial_pattern_seeds"]
    ]


def _values(vector: tuple[int, int, int, int]) -> dict[str, int]:
    _require(type(vector) in (list, tuple) and len(vector) == 4, "invalid store vector")
    a, i, flags, pattern = vector
    _require(
        type(a) is int
        and a in range(16)
        and type(i) is int
        and i in (0, 1)
        and type(pattern) is int
        and 0 <= pattern <= 255,
        "invalid store vector",
    )
    g = STACK + 0x2000 - 816 + a
    values = {
        "frame": g,
        "saved_ebp": g + 816,
        "inherited_return": BASE + 0x379E5F,
        "ecx": [0x11223344, 0xFFEEDDCC][i],
        "edx": [0x55667788, 0xBBAA9988][i],
        "ebx": 0x13579BDF,
        "esi": 0x2468ACE0,
        "edi": 0x3456789A,
        "flags": flags,
        "current_cookie": [0x6B8B4567, 0x1234FEDC][i],
        "current_other": [0xABCD9876, 0x5678DCBA][i],
        "dead_local": [0xDEADBEEF, 0xCAFE1234][i],
    }
    values.update(
        {
            n: 0 if i == 0 else 0x103 + index * 0x104
            for index, n in enumerate(("ss", "cs", "ds", "es", "fs", "gs"))
        }
    )
    validate_values(values)
    return values


def _expected_events(values: Mapping[str, int]) -> list[tuple]:
    events = [
        (
            site,
            "write",
            BASE + rva,
            width,
            _value(source, values) & ((1 << (8 * width)) - 1),
        )
        for site, (rva, width, source) in zip(WRITE_SITES, FIELDS)
    ]
    events.extend(
        (site, "write", values["frame"] + offset, 4, _value(source, values))
        for site, offset, source in STACK_WRITES
    )
    events.extend(
        (
            site,
            "read",
            (values["frame"] if region == "frame" else BASE) + offset,
            4,
            _value(source, values),
        )
        for site, region, offset, source in READS
    )
    return sorted(events, key=lambda e: (e[0], e[1] == "write"))


def _grammar(rows: list[Any]) -> list[tuple]:
    ids = {
        getattr(x86, "X86_INS_" + n.upper()): n
        for n in ("mov", "pushfd", "pop", "lea", "push", "imul", "shl")
    }
    actions = []
    for row in rows:
        _require(row.id in ids, "unsupported fallback instruction")
        operands = []
        for op in row.operands:
            _require(op.size in (1, 2, 4), "fallback operand width differs")
            if op.type == x86.X86_OP_REG:
                operands.append(("reg", row.reg_name(op.reg), op.size))
            elif op.type == x86.X86_OP_IMM:
                operands.append(("imm", op.imm, op.size))
            else:
                _require(
                    op.type == x86.X86_OP_MEM and op.mem.segment == 0,
                    "fallback memory expression differs",
                )
                operands.append(
                    (
                        "mem",
                        row.reg_name(op.mem.base) if op.mem.base else None,
                        row.reg_name(op.mem.index) if op.mem.index else None,
                        op.mem.scale,
                        op.mem.disp,
                        op.size,
                    )
                )
        actions.append((row.address - BASE, ids[row.id], tuple(operands)))
    _require(len(actions) == 42, "fallback slice instruction count differs")
    return actions


def model_case(
    vector: tuple[int, int, int, int],
    actions: list[tuple],
    *,
    negative: str | None = None,
) -> dict[str, Any]:
    values = _values(vector)
    g = values["frame"]
    pattern = vector[3]
    global_before = bytes((j * 37 + pattern) & 255 for j in range(GLOBAL_SIZE))
    stack_before = bytearray((j * 29 + pattern) & 255 for j in range(STACK_SIZE))
    for offset, source in (
        (0, "saved_ebp"),
        (4, "inherited_return"),
        (-804, "dead_local"),
    ):
        at = g + offset - STACK
        stack_before[at : at + 4] = values[source].to_bytes(4, "little")
    stack_before = bytes(stack_before)
    global_memory = bytearray(global_before)
    stack_memory = bytearray(stack_before)
    expected_global = overlay_spec(global_before, values)
    expected_stack = stack_overlay_spec(stack_before, values)
    expected_events = _expected_events(values)
    if negative == "widen_selector":
        i = next(i for i, e in enumerate(expected_events) if e[0] == 0x357BA6)
        pc, kind, address, _, value = expected_events[i]
        expected_events[i] = (pc, kind, address, 4, value)
    elif negative == "wrong_register":
        i = next(i for i, e in enumerate(expected_events) if e[0] == 0x357B88)
        pc, kind, address, width, _ = expected_events[i]
        expected_events[i] = (pc, kind, address, width, values["edx"])
    elif negative == "omit_dead_read":
        expected_events = [e for e in expected_events if e[0] != 0x357BEF]
    else:
        _require(negative is None, "unknown store oracle control")
    regs = {
        n: values[n]
        for n in ("ecx", "edx", "ebx", "esi", "edi", "ss", "cs", "ds", "es", "fs", "gs")
    }
    regs.update(eax=0, ebp=g, esp=g - 804)
    observed = []
    trace = []

    def event(pc: int, kind: str, address: int, width: int, value: int) -> None:
        actual = (pc, kind, address, width, value & ((1 << (8 * width)) - 1))
        _require(
            len(observed) < len(expected_events)
            and actual == expected_events[len(observed)],
            "memory event differs",
        )
        observed.append(actual)

    def buffer(address: int, width: int) -> tuple[bytearray, int]:
        if GLOBAL_START <= address and address + width <= GLOBAL_START + GLOBAL_SIZE:
            return global_memory, address - GLOBAL_START
        if STACK <= address and address + width <= STACK + STACK_SIZE:
            return stack_memory, address - STACK
        raise FailureStoreError("memory outside modeled buffers")

    def read_memory(pc: int, address: int, width: int) -> int:
        if address in (BASE + COOKIE, BASE + OTHER) and width == 4:
            value = values[
                "current_cookie" if address == BASE + COOKIE else "current_other"
            ]
        else:
            mem, at = buffer(address, width)
            value = int.from_bytes(mem[at : at + width], "little")
        event(pc, "read", address, width, value)
        return value

    def write_memory(pc: int, address: int, width: int, value: int) -> None:
        value &= (1 << (8 * width)) - 1
        event(pc, "write", address, width, value)
        mem, at = buffer(address, width)
        mem[at : at + width] = value.to_bytes(width, "little")

    def address(op: tuple) -> int:
        return (
            (regs[op[1]] if op[1] else 0)
            + (regs[op[2]] * op[3] if op[2] else 0)
            + op[4]
        )

    def read(pc: int, op: tuple) -> int:
        if op[0] == "reg":
            return regs[op[1]]
        if op[0] == "imm":
            return op[1] & 0xFFFFFFFF
        return read_memory(pc, address(op), op[5])

    def write(pc: int, op: tuple, value: int) -> None:
        if op[0] == "reg":
            regs[op[1]] = value & 0xFFFFFFFF
        else:
            write_memory(pc, address(op), op[5], value)

    for pc, op, args in actions:
        _require(START <= pc < STOP, "instruction escaped fallback slice")
        trace.append(pc)
        if op == "mov":
            write(pc, args[0], read(pc, args[1]))
        elif op == "lea":
            write(pc, args[0], address(args[1]))
        elif op in ("push", "pushfd"):
            value = values["flags"] if op == "pushfd" else read(pc, args[0])
            regs["esp"] -= 4
            write_memory(pc, regs["esp"], 4, value)
        elif op == "pop":
            value = read_memory(pc, regs["esp"], 4)
            regs["esp"] += 4
            write(pc, args[0], value)
        elif op == "imul":
            _require(len(args) == 3, "IMUL form differs")
            write(pc, args[0], read(pc, args[1]) * read(pc, args[2]))
        elif op == "shl":
            _require(
                len(args) == 2 and read(pc, args[1]) == 0,
                "only count-zero shift is specified",
            )
            write(pc, args[0], read(pc, args[0]))
        else:
            raise FailureStoreError("unsupported model instruction")
    _require(observed == expected_events, "event partition incomplete")
    _require(bytes(global_memory) == expected_global, "global overlay differs")
    _require(bytes(stack_memory) == expected_stack, "whole-stack overlay differs")
    _require(
        regs["eax"] == 4
        and regs["ecx"] == values["current_other"]
        and regs["esp"] == g - 808
        and regs["ebp"] == g
        and all(
            regs[n] == values[n]
            for n in ("edx", "ebx", "esi", "edi", "ss", "cs", "ds", "es", "fs", "gs")
        ),
        "final register interface differs",
    )
    return {
        "vector": list(vector),
        "trace_rvas": [f"0x{p:08x}" for p in trace],
        "global_sha256": hashlib.sha256(expected_global).hexdigest(),
        "stack_sha256": hashlib.sha256(expected_stack).hexdigest(),
        "events_sha256": _canonical_sha256([list(e) for e in observed]),
        "final_eax": regs["eax"],
        "final_ecx": regs["ecx"],
        "final_esp_G_offset": regs["esp"] - g,
    }


def _preflight(sources: Mapping[str, Any]) -> dict[str, Any]:
    _validate_json_tree(sources, "sources")
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    ids = {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }
    identity = sources["program_facts"]["identity"]
    _require(
        identity["executable_sha256"] == EXE_SHA256
        and all(
            _canonical_bytes(sources[k]["build_identity"]) == _canonical_bytes(identity)
            for k in ("dispatch", "frontier")
        ),
        "source build differs",
    )
    _require(
        sources["dispatch"]["exclusive_stops"]["zero_query"]["rva"] == f"0x{START:08x}"
        and sources["dispatch"]["frame"]["query_return_esp_G_offset"] == -804,
        "fallback entry join differs",
    )
    _require(
        sources["layout"]["sdk_layout"] == layout.sdk_layout_spec(),
        "SDK layout differs",
    )
    return ids


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    full = _decode_body(data, image, sources["program_facts"], OWNER)
    _require(
        [_point(r) for r in full]
        == [
            {k: p[k] for k in ("rva", "size", "sha256")}
            for p in sources["frontier"]["function_body"]["reviewed_points"]
        ],
        "complete frontier instruction witnesses differ",
    )
    rows = [r for r in full if START <= r.address - BASE < STOP]
    actions = _grammar(rows)
    stop = next(r for r in full if r.address - BASE == STOP)
    _require(
        stop.id == x86.X86_INS_CALL
        and stop.operands[0].type == x86.X86_OP_IMM
        and stop.operands[0].imm == BASE + 0x357B42,
        "exclusive next call differs",
    )
    witness = _witness(image, PAIR, 8)
    at = int(witness["file_offset"], 16)
    initial_targets = [
        int.from_bytes(data[at + i : at + i + 4], "little") - BASE for i in (0, 4)
    ]
    _require(
        initial_targets == [0x4B6B28, 0x4B6B78], "static pair initial words differ"
    )
    results = hashlib.sha256()
    trace = [f"0x{r.address-BASE:08x}" for r in rows]
    for vector in cases():
        result = model_case(vector, actions)
        _require(result["trace_rvas"] == trace, "linear trace differs")
        results.update(_canonical_bytes(result))
    controls = []
    for negative in ("widen_selector", "wrong_register", "omit_dead_read"):
        try:
            model_case(cases()[0], actions, negative=negative)
        except FailureStoreError as exc:
            _require(
                str(exc) == "memory event differs", "oracle control failed unexpectedly"
            )
        else:
            raise FailureStoreError("oracle mutation was not rejected")
        controls.append(
            {"mutation": negative, "expected_rejection": "memory event differs"}
        )
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed during store analysis",
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "slice": {
            "owner_entry_rva": f"0x{OWNER:08x}",
            "start_rva": f"0x{START:08x}",
            "exclusive_stop_rva": f"0x{STOP:08x}",
            "bytes": STOP - START,
            "points": [_point(r) for r in rows],
            "sha256": hashlib.sha256(
                b"".join(bytes(r.bytes) for r in rows)
            ).hexdigest(),
            "unexecuted_stop_instruction": _point(stop),
        },
        "global_fields": field_layout_spec(),
        "stack_writes": [
            {"instruction_rva": f"0x{p:08x}", "G_offset": o, "width": 4, "source": s}
            for p, o, s in STACK_WRITES
        ],
        "reads": [
            {
                "instruction_rva": f"0x{p:08x}",
                "region": region,
                "offset_or_rva": o,
                "width": 4,
                "source": s,
            }
            for p, region, o, s in READS
        ],
        "transfer": transfer_spec(),
        "static_pair": {
            "witness": witness,
            "initial_target_rvas": [f"0x{r:08x}" for r in initial_targets],
            "runtime_contents": "Unspecified after abstract query; slice pushes address without reading pair",
        },
        "matrix": MATRIX,
        "vector_sha256": _canonical_sha256([list(v) for v in cases()]),
        "results_sha256": results.hexdigest(),
        "oracle_controls": controls,
        "summary": {
            "instructions": 42,
            "bytes": 217,
            "cases": len(cases()),
            "global_writes_per_case": 22,
            "stack_writes_per_case": 7,
            "reads_per_case": 10,
            "global_written_bytes": 76,
            "stack_written_bytes": 12,
            "negative_controls": 3,
            "actual_import_executions": 0,
        },
        "scope": {
            "evidence_class": "exact_fallback_grammar_and_independent_global_and_stack_overlays",
            "premises": [
                "EAX is zero and ESP is G minus 804 after the abstract zero query return",
                "All read addresses including dead local G minus 804 are mapped; no external interference within slice",
                "Incoming global page and local scratch are arbitrary; only explicit bytes are overwritten",
                "Stored PUSHFD image is compatible with zero TEST, RF and VM clearing and bit-one convention; AF and remaining bits are opaque",
            ],
            "not_claimed": [
                "Zero-filled globals, zero selector upper halves or runtime pair contents",
                "Synthetic nonzero selectors and all other boundary samples are reachable through the original prefix",
                "Final flags equal the earlier stored PUSHFD image or represent an original context",
                "Actual CPU, game, import, interrupt or final direct-call execution; later return or reporting behavior",
                "Native fault behavior, concurrency or accounting promotion",
            ],
            "source_validation": "Canonical dispatch, frontier and SDK layout receipts plus fresh complete frontier decode and static pair file witness; prior matrices and SDK compiler are not rerun",
        },
    }
    _assert_publication_safe(result)
    return result


def validate_structure(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256,
            "sealed failure stores receipt differs",
        )
        _require(
            evidence["source_receipts"] == ids
            and evidence["transfer"] == transfer_spec()
            and evidence["global_fields"] == field_layout_spec()
            and evidence["matrix"] == MATRIX
            and evidence["vector_sha256"]
            == _canonical_sha256([list(v) for v in cases()]),
            "store specification or sources differ",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_stores(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_stores(
    executable: Path, evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        validate_structure(evidence, sources)
        actual = build_stores(executable, sources)
        _require(
            _canonical_bytes(evidence) == _canonical_bytes(actual),
            "exact failure stores analysis differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(actual["summary"]),
        }

    return _normalize(run)


def encode_stores(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
