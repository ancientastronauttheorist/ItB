"""Declarative frame overlay and finite exact-slice store conformance."""

from __future__ import annotations
import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import capstone.x86_const as x86
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    UNICORN_VERSION,
    UNICORN_CORE_VERSION,
    CPU_MODEL,
    _runtime,
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
ANALYSIS_KIND = "pe_native_assertion_helper_frame_stores"
SEALED_SHA256 = "69afa7ae52de9fe086d15f92350394518db88be433f7b9b3f5607c1a0a36d0b1"
OWNER, START, STOP = 0x379D28, 0x379D79, 0x379E20
STACK, STACK_SIZE = 0x2000000, 0x4000
SOURCE_PINS = {
    "pair": (
        "pe_native_assertion_helper_descendant_pair",
        "47421700f38e3dbf3f5283bf89d3beb5d6421d32eaf05938ad58989908f93d0b",
    ),
    "caller": (
        "pe_native_assertion_helper_caller_fill",
        "b89d1873e56c4afb27c96229c05a1a0516732a5bdc3d2151173baeb5d4a5b653",
    ),
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
}
# Independently authored overlay: offsets, byte widths, symbolic boundary values.
FIELDS = [
    (-808, 4, "frame_minus_800"),
    (-804, 4, "frame_minus_720"),
    (-544, 4, "frame_minus_720"),
    (-548, 4, "ecx"),
    (-552, 4, "edx"),
    (-556, 4, "ebx"),
    (-560, 4, "esi"),
    (-564, 4, "edi"),
    (-520, 2, "ss"),
    (-532, 2, "cs"),
    (-568, 2, "ds"),
    (-572, 2, "es"),
    (-576, 2, "fs"),
    (-580, 2, "gs"),
    (-816, 4, "pushed_flags_image"),
    (-528, 4, "pushed_flags_image"),
    (-536, 4, "return_word"),
    (-524, 4, "frame_plus_4"),
    (-720, 4, "constant_65537"),
    (-540, 4, "saved_ebp"),
    (-800, 4, "incoming_word_12"),
    (-796, 4, "incoming_word_16"),
    (-788, 4, "return_word"),
]
REGISTER_SETS = [
    {
        "ecx": 0x12345678,
        "edx": 0x23456789,
        "ebx": 0x3456789A,
        "esi": 0x456789AB,
        "edi": 0x56789ABC,
    },
    {
        "ecx": 0xFEDCBA98,
        "edx": 0xEDCBA987,
        "ebx": 0xDCBA9876,
        "esi": 0xCBA98765,
        "edi": 0xBA987654,
    },
]
INPUT_SETS = [
    {
        "saved_ebp": 0x456789AB,
        "return_word": 0x10203040,
        "incoming_word_12": 0x11223344,
        "incoming_word_16": 0x55667788,
        "slot_seed": 0,
    },
    {
        "saved_ebp": 0x98765432,
        "return_word": 0x20304050,
        "incoming_word_12": 0xFFEEDDCC,
        "incoming_word_16": 0xBBAA9988,
        "slot_seed": 0x6B8B4567,
    },
]
MATRIX = {
    "frame_alignments": list(range(16)),
    "register_sets": REGISTER_SETS,
    "input_sets": INPUT_SETS,
    "eflags_values": [2, 0x202, 0x246, 0x8D7],
    "segment_selectors": {"ss": 0, "cs": 0, "ds": 0, "es": 0, "fs": 0, "gs": 0},
}


class StoreError(RuntimeError):
    """A pinned grammar, independent overlay, or exact replay differs."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise StoreError(message)


def _normalize(fn: Any) -> Any:
    try:
        return fn()
    except StoreError:
        raise
    except Exception as exc:
        raise StoreError(str(exc)) from exc


def cases() -> list[tuple[int, int, int, int]]:
    return [
        (a, r, i, f)
        for a in range(16)
        for r in range(2)
        for i in range(2)
        for f in MATRIX["eflags_values"]
    ]


def overlay_spec(before: bytes, frame_offset: int, values: Mapping[str, int]) -> bytes:
    _require(
        isinstance(before, bytes) and type(frame_offset) is int, "invalid frame buffer"
    )
    _require(isinstance(values, Mapping), "overlay inputs must be a mapping")
    _require(
        set(values) == {s for _, _, s in FIELDS}, "overlay input partition differs"
    )
    _require(
        all(type(v) is int and 0 <= v <= 0xFFFFFFFF for v in values.values()),
        "overlay values require u32",
    )
    result = bytearray(before)
    for offset, width, source in FIELDS:
        at = frame_offset + offset
        _require(0 <= at and at + width <= len(result), "overlay outside buffer")
        result[at : at + width] = (values[source] & ((1 << (8 * width)) - 1)).to_bytes(
            width, "little"
        )
    return bytes(result)


def _preflight(sources: Mapping[str, Any]) -> dict[str, Any]:
    _validate_json_tree(sources, "sources")
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    identities = {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }
    identity = sources["program_facts"]["identity"]
    _require(
        identity["executable_sha256"] == EXE_SHA256
        and all(
            _canonical_bytes(sources[k]["build_identity"]) == _canonical_bytes(identity)
            for k in ("pair", "caller")
        ),
        "source build differs",
    )
    previous = sources["caller"]["setup"]
    _require(
        previous["exclusive_stop_rva"] == "0x00379d79"
        and previous["layout"]["stop_sp_offset"] == -812
        and previous["layout"]["stop_eax_offset"] == -800
        and previous["layout"]["zero_union"] == [-800, -4],
        "entry boundary join differs",
    )
    return identities


def _grammar(rows: list[Any]) -> dict[str, Any]:
    registers = {
        name: name
        for name in (
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
        )
    }
    registers.update(eax=("frame", -800), ebp=("frame", 0), esp=("frame", -812))
    reads = {
        0: "saved_ebp",
        4: "return_word",
        12: "incoming_word_12",
        16: "incoming_word_16",
    }
    events = []
    read_events = []
    pending = None

    def address(row: Any, operand: Any) -> int:
        _require(
            operand.type == x86.X86_OP_MEM
            and operand.mem.index == operand.mem.segment == 0,
            "unreviewed memory expression",
        )
        base = registers[row.reg_name(operand.mem.base)]
        _require(
            isinstance(base, tuple) and base[0] == "frame", "unreviewed address base"
        )
        return base[1] + operand.mem.disp

    def value(row: Any, operand: Any) -> Any:
        if operand.type == x86.X86_OP_REG:
            return registers[row.reg_name(operand.reg)]
        if operand.type == x86.X86_OP_IMM:
            _require(operand.imm == 65537, "unreviewed immediate")
            return "constant_65537"
        offset = address(row, operand)
        _require(offset in reads and operand.size == 4, "unreviewed frame read")
        read_events.append(
            {
                "instruction": _point(row),
                "offset": offset,
                "width": 4,
                "source": reads[offset],
            }
        )
        return reads[offset]

    def store(
        row: Any, offset: int, width: int, source: Any, temporary: bool = False
    ) -> None:
        if isinstance(source, tuple):
            _require(
                source[0] == "frame" and source[1] in (-800, -720, 4),
                "unreviewed pointer source",
            )
            source = {
                -800: "frame_minus_800",
                -720: "frame_minus_720",
                4: "frame_plus_4",
            }[source[1]]
        events.append(
            {
                "instruction": _point(row),
                "offset": offset,
                "width": width,
                "source": source,
                "temporary": temporary,
            }
        )

    for row in rows:
        if row.id == x86.X86_INS_MOV:
            dest, src = row.operands
            source = value(row, src)
            if dest.type == x86.X86_OP_REG:
                registers[row.reg_name(dest.reg)] = source
            else:
                store(row, address(row, dest), dest.size, source)
        elif row.id == x86.X86_INS_LEA:
            dest, src = row.operands
            _require(dest.type == x86.X86_OP_REG, "LEA destination differs")
            registers[row.reg_name(dest.reg)] = ("frame", address(row, src))
        elif row.id == x86.X86_INS_PUSHFD:
            _require(
                pending is None and registers["esp"] == ("frame", -812),
                "flags push state differs",
            )
            registers["esp"] = ("frame", -816)
            pending = "pushed_flags_image"
            store(row, -816, 4, pending, True)
        elif row.id == x86.X86_INS_POP:
            _require(
                pending is not None and registers["esp"] == ("frame", -816),
                "flags pop state differs",
            )
            read_events.append(
                {
                    "instruction": _point(row),
                    "offset": -816,
                    "width": 4,
                    "source": pending,
                }
            )
            store(row, address(row, row.operands[0]), row.operands[0].size, pending)
            registers["esp"] = ("frame", -812)
            pending = None
        else:
            raise StoreError("unreviewed slice instruction")
    _require(
        [(e["offset"], e["width"], e["source"]) for e in events] == FIELDS,
        "decoded stores differ from independent overlay",
    )
    _require(
        pending is None
        and registers["esp"] == ("frame", -812)
        and registers["eax"] == "return_word",
        "final symbolic state differs",
    )
    _require(
        len(rows) == 30 and len(events) == 23 and len(read_events) == 6,
        "slice partition differs",
    )
    return {
        "stores": events,
        "reads": read_events,
        "final_eax": "return_word",
        "final_esp_offset": -812,
        "flags_source": "opaque PUSHFD image of slice-boundary flags, not original caller-entry flags",
        "source_provenance": "Boundary ECX and EDX are free inputs here; their reachability through the preceding fill prefix is not proved.",
    }


def _values(
    frame: int, register_index: int, input_index: int, flags: int
) -> dict[str, int]:
    inputs = INPUT_SETS[input_index]
    return (
        REGISTER_SETS[register_index]
        | MATRIX["segment_selectors"]
        | {
            k: inputs[k]
            for k in (
                "saved_ebp",
                "return_word",
                "incoming_word_12",
                "incoming_word_16",
            )
        }
        | {
            "frame_minus_800": frame - 800,
            "frame_minus_720": frame - 720,
            "frame_plus_4": frame + 4,
            "constant_65537": 65537,
            "pushed_flags_image": flags,
        }
    )


def _execute(
    code: bytes,
    grammar: Mapping[str, Any],
    vector: tuple[int, int, int, int],
    *,
    negative: str | None = None,
) -> dict[str, Any]:
    u = _runtime()
    from unicorn import x86_const as x

    alignment, rindex, iindex, flags = vector
    frame = STACK + 0x2000 + alignment
    uc = u.Uc(u.UC_ARCH_X86, u.UC_MODE_32)
    uc.ctl_set_cpu_model(CPU_MODEL)
    _require(uc.ctl_get_cpu_model() == CPU_MODEL, "CPU model differs")
    uc.mem_map((BASE + START) & ~0xFFF, 0x1000, u.UC_PROT_ALL)
    uc.mem_write(BASE + START, code)
    uc.mem_protect((BASE + START) & ~0xFFF, 0x1000, u.UC_PROT_READ | u.UC_PROT_EXEC)
    uc.mem_map(STACK, STACK_SIZE, u.UC_PROT_READ | u.UC_PROT_WRITE)
    before = bytearray((i * 37 + 19) & 255 for i in range(STACK_SIZE))
    at = frame - STACK
    before[at - 800 : at - 4] = bytes(796)
    inputs = INPUT_SETS[iindex]
    regs = REGISTER_SETS[rindex]
    values = _values(frame, rindex, iindex, flags)
    for offset, word in (
        (0, inputs["saved_ebp"]),
        (4, inputs["return_word"]),
        (8, 0),
        (12, inputs["incoming_word_12"]),
        (16, inputs["incoming_word_16"]),
        (-4, inputs["slot_seed"] ^ frame),
        (-812, regs["edi"]),
    ):
        before[at + offset : at + offset + 4] = struct.pack("<I", word)
    before = bytes(before)
    uc.mem_write(STACK, before)
    ids = {
        name: getattr(x, "UC_X86_REG_" + name.upper())
        for name in (*regs, "eax", "ebp", "esp", "eflags", *MATRIX["segment_selectors"])
    }
    for name, v in regs.items():
        uc.reg_write(ids[name], v)
    uc.reg_write(ids["eax"], frame - 800)
    uc.reg_write(ids["ebp"], frame)
    uc.reg_write(ids["esp"], frame - 812)
    uc.reg_write(ids["eflags"], flags)
    _require(
        uc.reg_read(ids["eflags"]) == flags
        and all(uc.reg_read(ids[n]) == 0 for n in MATRIX["segment_selectors"]),
        "boundary flags or segment values differ",
    )
    expected = overlay_spec(before, at, values)
    expected_writes = [(o, w, values[s] & ((1 << (8 * w)) - 1)) for o, w, s in FIELDS]
    if negative == "widen_segment":
        index = next(i for i, (o, _, _) in enumerate(expected_writes) if o == -520)
        o, _, v = expected_writes[index]
        expected_writes[index] = (o, 4, v)
    elif negative == "wrong_register":
        index = next(i for i, (o, _, _) in enumerate(expected_writes) if o == -548)
        o, w, _ = expected_writes[index]
        expected_writes[index] = (o, w, values["edx"])
    else:
        _require(negative is None, "unknown oracle control")
    expected_reads = [(r["offset"], r["width"]) for r in grammar["reads"]]
    trace = []
    writes = []
    reads = []
    failure = []

    def fail(message: str) -> None:
        failure.append(message)
        uc.emu_stop()

    def instruction(_uc: Any, address: int, size: int, _data: Any) -> None:
        if not (BASE + START <= address and address + size <= BASE + STOP):
            fail("instruction escaped slice")
            return
        trace.append(address - BASE)

    def memory(
        _uc: Any, access: int, address: int, size: int, value: int, _data: Any
    ) -> None:
        if access == u.UC_MEM_WRITE:
            event = (address - frame, size, value & ((1 << (8 * size)) - 1))
            index = len(writes)
            if index >= len(expected_writes) or event != expected_writes[index]:
                fail("write event differs")
                return
            writes.append(event)
        else:
            event = (address - frame, size)
            index = len(reads)
            if index >= len(expected_reads) or event != expected_reads[index]:
                fail("read event differs")
                return
            reads.append(event)

    uc.hook_add(u.UC_HOOK_CODE, instruction)
    uc.hook_add(u.UC_HOOK_MEM_READ | u.UC_HOOK_MEM_WRITE, memory)
    uc.emu_start(BASE + START, BASE + STOP, timeout=5000000, count=1000)
    _require(not failure, failure[0] if failure else "emulation failure")
    _require(
        uc.reg_read(x.UC_X86_REG_EIP) == BASE + STOP
        and writes == expected_writes
        and reads == expected_reads,
        "slice boundary or event partition differs",
    )
    _require(
        bytes(uc.mem_read(STACK, STACK_SIZE)) == expected, "independent overlay differs"
    )
    _require(
        all(uc.reg_read(ids[n]) == v for n, v in regs.items())
        and uc.reg_read(ids["ebp"]) == frame
        and uc.reg_read(ids["esp"]) == frame - 812
        and uc.reg_read(ids["eax"]) == inputs["return_word"]
        and uc.reg_read(ids["eflags"]) == flags,
        "final register or flags state differs",
    )
    return {
        "vector": list(vector),
        "trace_rvas": [f"0x{r:08x}" for r in trace],
        "write_events": [list(w) for w in writes],
        "read_events": [list(r) for r in reads],
        "stack_sha256": hashlib.sha256(expected).hexdigest(),
    }


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    all_rows = _decode_body(data, image, sources["program_facts"], OWNER)
    _require(
        [_point(r) for r in all_rows] == sources["pair"]["bodies"][0]["points"],
        "source instruction witnesses differ",
    )
    rows = [r for r in all_rows if START <= r.address - BASE < STOP]
    code = b"".join(bytes(r.bytes) for r in rows)
    _require(len(code) == 167, "slice size differs")
    grammar = _grammar(rows)
    vectors = cases()
    results = hashlib.sha256()
    trace = [f"0x{r.address-BASE:08x}" for r in rows]
    for vector in vectors:
        result = _execute(code, grammar, vector)
        _require(result["trace_rvas"] == trace, "linear instruction coverage differs")
        results.update(_canonical_bytes(result))
    for negative in ("widen_segment", "wrong_register"):
        try:
            _execute(code, grammar, vectors[0], negative=negative)
        except StoreError as exc:
            _require(
                str(exc) == "write event differs", "oracle control failed unexpectedly"
            )
        else:
            raise StoreError("oracle control failed to reject")
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed during replay",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "slice": {
            "owner_entry_rva": f"0x{OWNER:08x}",
            "start_rva": f"0x{START:08x}",
            "exclusive_stop_rva": f"0x{STOP:08x}",
            "size": len(code),
            "sha256": hashlib.sha256(code).hexdigest(),
            "points": [_point(r) for r in rows],
            "unexecuted_stop_instruction": _point(
                next(r for r in all_rows if r.address - BASE == STOP)
            ),
        },
        "entry_join": {
            "caller_stop_rva": sources["caller"]["setup"]["exclusive_stop_rva"],
            "eax_ebp_offset": -800,
            "esp_ebp_offset": -812,
            "zero_union": [-800, -4],
            "volatile_inputs": "ECX EDX and boundary flags sampled independently; full-prefix reachability is unproved",
        },
        "grammar": grammar,
        "overlay_fields": [
            {"offset": o, "width": w, "source": s} for o, w, s in FIELDS
        ],
        "matrix": MATRIX,
        "vector_sha256": _canonical_sha256([list(v) for v in vectors]),
        "results_sha256": results.hexdigest(),
        "summary": {
            "cases": len(vectors),
            "instructions_per_case": 30,
            "frame_stores_per_case": 22,
            "temporary_stores_per_case": 1,
            "write_events_per_case": 23,
            "read_events_per_case": 6,
            "frame_written_bytes": 76,
            "temporary_written_bytes": 4,
            "negative_controls": 2,
        },
        "emulator": {
            "name": "Unicorn",
            "version": UNICORN_VERSION,
            "native_core_version": list(UNICORN_CORE_VERSION),
            "cpu_model": {"id": CPU_MODEL, "name": "UC_CPU_X86_HASWELL"},
            "bits": 32,
            "flat_segments": True,
            "instruction_limit": 1000,
            "timeout_microseconds": 5000000,
        },
        "oracle_controls": [
            {"mutation": "widen_segment", "expected_rejection": "write event differs"},
            {"mutation": "wrong_register", "expected_rejection": "write event differs"},
        ],
        "scope": {
            "evidence_class": "normalized_store_transfer_grammar_and_finite_boundary_state_emulation",
            "checks": [
                "Exact ordered read and write events and complete linear slice trace",
                "Independent whole-stack overlay including the stale PUSHFD temporary",
                "Unchanged non-EAX general registers, EBP ESP and sampled flags; final EAX equals incoming return word",
            ],
            "not_claimed": [
                "Arbitrary sampled volatile inputs are reachable after the preceding fill prefix",
                "Original caller-entry register or flag capture; context identity or ABI classification",
                "Nonzero segment-selector runtime behavior; RF VM or other unsampled flag images",
                "First import call or later code execution; whole-function return or reporting behavior",
                "Real game or hardware execution, faults, concurrency, timing, ownership or accounting promotion",
            ],
            "source_validation": "Canonical source receipts plus exact PE and complete owner instruction witnesses; earlier emulation matrices and whole-atlas analyses are not rerun.",
        },
    }


def validate_structure(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256,
            "sealed stores receipt differs",
        )
        _require(
            evidence["source_receipts"] == ids
            and evidence["matrix"] == MATRIX
            and evidence["overlay_fields"]
            == [{"offset": o, "width": w, "source": s} for o, w, s in FIELDS],
            "source or overlay differs",
        )
        _require(
            evidence["vector_sha256"] == _canonical_sha256([list(v) for v in cases()]),
            "vector identity differs",
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
        result = build_stores(executable, sources)
        _require(
            _canonical_bytes(evidence) == _canonical_bytes(result),
            "exact replay differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(result["summary"]),
        }

    return _normalize(run)


def encode_stores(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
