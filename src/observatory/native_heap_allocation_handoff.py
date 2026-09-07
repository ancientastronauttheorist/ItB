"""Exact initial candidate-to-HeapAlloc handoff, stopping before imported execution."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import capstone.x86_const as x86
import pefile
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
from src.observatory.native_allocation_retry_semantics import (
    SOURCE_PINS as RETRY_SOURCE_PINS,
    ANALYSIS_KIND as RETRY_KIND,
    SEALED_SHA256 as RETRY_SEAL,
    _grammar as _retry_grammar,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_heap_allocation_handoff"
SEALED_SHA256 = "5571de6ac2e97a838e3919219e7d6459eac8b28b5ec5e3834b9e6f134933fad1"
SOURCE_PINS = {
    "program_facts": RETRY_SOURCE_PINS["program_facts"],
    "retry_semantics": (RETRY_KIND, RETRY_SEAL),
}
START, WRAPPER = 0x379F52, 0x38942B
BODIES = {START: 0x379F5D, WRAPPER: 0x389479}
HEAP_CALL, ERROR_CALL = 0x38945D, 0x389469
HEAP_WORD, IAT_SLOT = BASE + 0x4B7634, BASE + 0x3D6220
U32, LIMIT = 0xFFFFFFFF, 0xFFFFFFE0


def R(name):
    return ("reg", name)


def I(value):
    return ("imm", value)


def M(base, offset=0):
    return ("mem", base, offset)


OPS = {
    0x379F52: ("mov", R("edi"), R("edi")),
    0x379F54: ("push", R("ebp")),
    0x379F55: ("mov", R("ebp"), R("esp")),
    0x379F57: ("pop", R("ebp")),
    0x379F58: ("jmp", I(BASE + WRAPPER)),
    0x38942B: ("mov", R("edi"), R("edi")),
    0x38942D: ("push", R("ebp")),
    0x38942E: ("mov", R("ebp"), R("esp")),
    0x389430: ("push", R("esi")),
    0x389431: ("mov", R("esi"), M("ebp", 8)),
    0x389434: ("cmp", R("esi"), I(-32)),
    0x389437: ("ja", I(BASE + ERROR_CALL)),
    0x389439: ("test", R("esi"), R("esi")),
    0x38943B: ("jne", I(BASE + 0x389454)),
    0x38943D: ("inc", R("esi")),
    0x38943E: ("jmp", I(BASE + 0x389454)),
    0x389440: ("call", I(BASE + 0x38DCE2)),
    0x389445: ("test", R("eax"), R("eax")),
    0x389447: ("je", I(BASE + ERROR_CALL)),
    0x389449: ("push", R("esi")),
    0x38944A: ("call", I(BASE + 0x38BBC4)),
    0x38944F: ("pop", R("ecx")),
    0x389450: ("test", R("eax"), R("eax")),
    0x389452: ("je", I(BASE + ERROR_CALL)),
    0x389454: ("push", R("esi")),
    0x389455: ("push", I(0)),
    0x389457: ("push", M(None, HEAP_WORD)),
    HEAP_CALL: ("call", M(None, IAT_SLOT)),
    0x389463: ("test", R("eax"), R("eax")),
    0x389465: ("je", I(BASE + 0x389440)),
    0x389467: ("jmp", I(BASE + 0x389476)),
    ERROR_CALL: ("call", I(BASE + 0x385BCC)),
    0x38946E: ("mov", M("eax"), I(12)),
    0x389474: ("xor", R("eax"), R("eax")),
    0x389476: ("pop", R("esi")),
    0x389477: ("pop", R("ebp")),
    0x389478: ("ret",),
}
ORDER = list(OPS)
SIZES = {}
for _start, _end in BODIES.items():
    _points = [p for p in ORDER if _start <= p < _end]
    SIZES.update(
        {
            p: (_points[i + 1] if i + 1 < len(_points) else _end) - p
            for i, p in enumerate(_points)
        }
    )
MODELED_ORDER = [p for p in ORDER if p < 0x389440 or 0x389454 <= p < HEAP_CALL]


class HeapHandoffError(RuntimeError):
    """An exact initial heap handoff or protected-state relation differs."""


def _require(ok, message):
    if not ok:
        raise HeapHandoffError(message)


def _normalize(fn):
    try:
        return fn()
    except HeapHandoffError:
        raise
    except Exception as exc:
        raise HeapHandoffError(str(exc)) from exc


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)
    return value


def handoff_spec(size: int, heap_handle: int) -> dict[str, Any]:
    _u32(size, "size word")
    _u32(heap_handle, "heap word")
    if size > LIMIT:
        return {
            "outcome": "error_frontier",
            "normalized_size": size,
            "arguments": [],
            "stop_rva": ERROR_CALL,
        }
    normalized = max(size, 1)
    return {
        "outcome": "heap_call",
        "normalized_size": normalized,
        "arguments": [heap_handle, 0, normalized],
        "stop_rva": HEAP_CALL,
    }


def _cmp_flags(left, right):
    value = (left - right) & U32
    return {
        "cf": int(left < right),
        "zf": int(value == 0),
        "sf": value >> 31,
        "of": ((left ^ right) & (left ^ value)) >> 31,
        "af": ((left ^ right ^ value) >> 4) & 1,
        "pf": int((value & 255).bit_count() % 2 == 0),
    }


def _test_flags(value):
    return {
        "cf": 0,
        "zf": int(value == 0),
        "sf": value >> 31,
        "of": 0,
        "af": None,
        "pf": int((value & 255).bit_count() % 2 == 0),
    }


def _inc_flags(value, carry):
    result = (value + 1) & U32
    return {
        "cf": carry,
        "zf": int(result == 0),
        "sf": result >> 31,
        "of": int(value == 0x7FFFFFFF),
        "af": int((value & 15) == 15),
        "pf": int((result & 255).bit_count() % 2 == 0),
    }


def case_fixture(size, heap_handle, frame_alignment=0, seed=1):
    handoff_spec(size, heap_handle)
    _require(
        type(frame_alignment) is int and 0 <= frame_alignment < 16,
        "invalid frame alignment",
    )
    _u32(seed, "seed")
    stack = 0x30001000 + frame_alignment
    regs = {
        r: (0xA1000000 + i * 0x10101 + seed) & U32
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs["esp"] = stack
    memory = {
        stack + i: (0xBABE0000 + i + seed) & U32
        for i in (-20, -16, -12, -8, -4, 0, 4, 8)
    }
    memory[stack + 4] = size
    memory[HEAP_WORD] = heap_handle
    return {"registers": regs, "memory": memory, "stack": stack}


def model_case(size, heap_handle, frame_alignment=0, seed=1, ops=None):
    spec = handoff_spec(size, heap_handle)
    fixture = case_fixture(size, heap_handle, frame_alignment, seed)
    initial = fixture["registers"]
    regs, memory = dict(initial), dict(fixture["memory"])
    operations = OPS if ops is None else ops
    events, trace = [], []
    flags = None

    def access(address):
        _require(address in memory, "unmapped word read")
        value = memory[address]
        events.append({"kind": "read", "address": address, "value": value, "width": 4})
        return value

    def read(arg):
        if arg[0] == "reg":
            return regs[arg[1]]
        if arg[0] == "imm":
            return arg[1] & U32
        return access(((regs[arg[1]] if arg[1] else 0) + arg[2]) & U32)

    pc = START
    while pc not in (HEAP_CALL, ERROR_CALL):
        _require(pc in operations and len(trace) < 50, "invalid initial handoff path")
        trace.append(f"0x{pc:08x}")
        op, *args = operations[pc]
        next_pc = pc + SIZES[pc]
        if op == "mov":
            regs[args[0][1]] = read(args[1])
        elif op == "push":
            value = read(args[0])
            regs["esp"] = (regs["esp"] - 4) & U32
            _require(regs["esp"] in memory, "unmapped stack write")
            memory[regs["esp"]] = value
            events.append(
                {"kind": "write", "address": regs["esp"], "value": value, "width": 4}
            )
        elif op == "pop":
            regs[args[0][1]] = access(regs["esp"])
            regs["esp"] = (regs["esp"] + 4) & U32
        elif op == "cmp":
            flags = _cmp_flags(read(args[0]), read(args[1]))
        elif op == "test":
            flags = _test_flags(read(args[0]) & read(args[1]))
        elif op == "inc":
            left = read(args[0])
            flags = _inc_flags(left, flags["cf"])
            regs[args[0][1]] = (left + 1) & U32
        elif op in ("jmp", "ja", "jne"):
            if (
                op == "jmp"
                or (op == "ja" and not (flags["cf"] or flags["zf"]))
                or (op == "jne" and not flags["zf"])
            ):
                next_pc = read(args[0]) - BASE
        else:
            raise HeapHandoffError("unexpected execution outside initial handoff")
        pc = next_pc
    stack = fixture["stack"]
    expected_regs = dict(
        initial, ebp=stack - 4, esi=spec["normalized_size"], esp=stack - 8
    )
    expected_events = [
        {"kind": "write", "address": stack - 4, "value": initial["ebp"], "width": 4},
        {"kind": "read", "address": stack - 4, "value": initial["ebp"], "width": 4},
        {"kind": "write", "address": stack - 4, "value": initial["ebp"], "width": 4},
        {"kind": "write", "address": stack - 8, "value": initial["esi"], "width": 4},
        {"kind": "read", "address": stack + 4, "value": size, "width": 4},
    ]
    if spec["outcome"] == "heap_call":
        expected_regs["esp"] = stack - 20
        expected_events.extend(
            [
                {
                    "kind": "write",
                    "address": stack - 12,
                    "value": spec["normalized_size"],
                    "width": 4,
                },
                {"kind": "write", "address": stack - 16, "value": 0, "width": 4},
                {
                    "kind": "read",
                    "address": HEAP_WORD,
                    "value": heap_handle,
                    "width": 4,
                },
                {
                    "kind": "write",
                    "address": stack - 20,
                    "value": heap_handle,
                    "width": 4,
                },
            ]
        )
        expected_flags = (
            _test_flags(size)
            if size
            else {"cf": 0, "zf": 0, "sf": 0, "of": 0, "af": 0, "pf": 0}
        )
    else:
        expected_flags = _cmp_flags(size, LIMIT)
    expected_memory = dict(fixture["memory"])
    for event in expected_events:
        if event["kind"] == "write":
            expected_memory[event["address"]] = event["value"]
    _require(
        pc == spec["stop_rva"] and regs == expected_regs and flags == expected_flags,
        "handoff register or flag relation differs",
    )
    _require(
        events == expected_events and memory == expected_memory,
        "handoff ordered memory relation differs",
    )
    return {
        "inputs": {
            "size": size,
            "heap_handle": heap_handle,
            "frame_alignment": frame_alignment,
            "seed": seed,
        },
        "specification": spec,
        "stop_rva": f"0x{pc:08x}",
        "registers": regs,
        "arithmetic_flags": flags,
        "events": events,
        "trace_rvas": trace,
        "memory": [{"address": a, "value": v} for a, v in sorted(memory.items())],
    }


def case_inputs():
    return sorted(
        {
            0,
            1,
            2,
            7,
            8,
            31,
            32,
            511,
            512,
            4096,
            0x7FFFFFFF,
            0x80000000,
            LIMIT - 1,
            LIMIT,
            *range(LIMIT + 1, U32 + 1),
        }
    )


def _preflight(sources):
    _require(
        isinstance(sources, Mapping) and set(sources) == set(SOURCE_PINS),
        "source partition differs",
    )
    return {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }


def _grammar(rows):
    _require(
        [r.address - BASE for r in rows] == ORDER, "heap wrapper body points differ"
    )
    for row in rows:
        args = []
        for arg in row.operands:
            if arg.type == x86.X86_OP_REG:
                args.append(R(row.reg_name(arg.reg)))
            elif arg.type == x86.X86_OP_IMM:
                args.append(I(arg.imm))
            elif arg.type == x86.X86_OP_MEM:
                _require(
                    not arg.mem.segment and not arg.mem.index, "unexpected memory mode"
                )
                args.append(
                    M(
                        row.reg_name(arg.mem.base) if arg.mem.base else None,
                        arg.mem.disp,
                    )
                )
            else:
                raise HeapHandoffError("unexpected operand")
        pc = row.address - BASE
        _require(
            (row.mnemonic, *args) == OPS[pc]
            and row.size == SIZES[pc]
            and [a.size for a in row.operands] == [4] * len(args),
            "exact handoff grammar differs",
        )


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    rows = [
        r
        for start in BODIES
        for r in _decode_body(data, image, sources["program_facts"], start)
    ]
    _grammar(rows)
    retry = _decode_body(data, image, sources["program_facts"], 0x3574DB)
    _retry_grammar(retry)
    _require(
        [_point(r) for r in retry] == sources["retry_semantics"]["body"]["points"],
        "retry source body differs",
    )
    incoming = next(r for r in retry if r.address - BASE == 0x357502)
    _require(
        incoming.id == x86.X86_INS_CALL and incoming.operands[0].imm == BASE + START,
        "candidate source edge differs",
    )
    pe = pefile.PE(data=data)
    imports = [
        (
            entry.dll.decode("ascii"),
            symbol.name.decode("ascii") if symbol.name else None,
            symbol.ordinal,
        )
        for entry in pe.DIRECTORY_ENTRY_IMPORT
        for symbol in entry.imports
        if symbol.address == IAT_SLOT
    ]
    _require(
        imports == [("KERNEL32.dll", "HeapAlloc", None)],
        "exact PE import identity differs",
    )
    inputs = case_inputs()
    heaps = [0, 1, 0x81230000, U32]
    cases = [
        model_case(size, heap, a, s)
        for size in inputs
        for heap in heaps
        for a in (0, 1, 7, 15)
        for s in (0, U32)
    ]
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(
        union == [f"0x{p:08x}" for p in MODELED_ORDER], "handoff graph coverage differs"
    )
    controls = []
    for name, pc, replacement, size in (
        ("wrong_size_limit", 0x389434, ("cmp", R("esi"), I(-31)), LIMIT + 1),
        ("wrong_zero_normalization", 0x38943D, ("mov", R("esi"), I(2)), 0),
        ("wrong_heap_flags", 0x389455, ("push", I(1)), 8),
        ("wrong_heap_word", 0x389457, ("push", I(0)), 8),
        ("wrong_thunk_restore", 0x379F57, ("pop", R("esi")), 8),
    ):
        altered = dict(OPS)
        altered[pc] = replacement
        try:
            model_case(size, 0x81230000, ops=altered)
        except HeapHandoffError:
            controls.append(
                {"name": name, "kind": "semantic_mutation", "rejected": True}
            )
        else:
            raise HeapHandoffError("semantic mutation accepted: " + name)
    witnesses = []
    for start, end in BODIES.items():
        body = [r for r in rows if start <= r.address - BASE < end]
        witnesses.append(
            {
                "entry_rva": f"0x{start:08x}",
                "exclusive_end_rva": f"0x{end:08x}",
                "bytes": end - start,
                "nodes": len(body),
                "points": [_point(r) for r in body],
                "sha256": hashlib.sha256(
                    b"".join(bytes(r.bytes) for r in body)
                ).hexdigest(),
            }
        )
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "bodies": witnesses,
        "incoming_edge": {
            "instruction": _point(incoming),
            "target_entry_rva": f"0x{START:08x}",
        },
        "import_boundary": {
            "instruction": _point(
                next(r for r in rows if r.address - BASE == HEAP_CALL)
            ),
            "iat_rva": f"0x{IAT_SLOT-BASE:08x}",
            "dll": "KERNEL32.dll",
            "name": "HeapAlloc",
            "identity_basis": "Exact PE import directory",
            "runtime_iat_read": False,
        },
        "frontiers": {
            "heap_call": f"0x{HEAP_CALL:08x}",
            "error_call": f"0x{ERROR_CALL:08x}",
        },
        "matrix": {
            "size_inputs": inputs,
            "heap_words": heaps,
            "entry_stack_base": 0x30001000,
            "frame_alignments": [0, 1, 7, 15],
            "seeds": [0, U32],
        },
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
        },
        "summary": {
            "cases": len(cases),
            "static_bytes": 89,
            "static_nodes": 37,
            "modeled_nodes": 19,
            "heap_frontiers": sum(
                c["specification"]["outcome"] == "heap_call" for c in cases
            ),
            "error_frontiers": sum(
                c["specification"]["outcome"] == "error_frontier" for c in cases
            ),
            "actual_native_executions": 0,
            "actual_import_calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "exact_initial_graph_model_with_independent_unsigned_size_and_import_argument_specification",
            "premises": [
                "Mapped stable caller request, frame words and heap-handle global; the global and frame are disjoint",
                "Finite stack base and alignments declared in the matrix; stack arithmetic does not wrap",
                "Heap-handle word is supplied data; no handle validity, heap ownership or allocation success is inferred",
            ],
            "relation": "The thunk restores EBP and ESP before entering the wrapper; requests above unsigned maximum minus thirty-one reach the error frontier, otherwise zero becomes one and the wrapper prepares HeapAlloc arguments heap handle, zero flags and normalized size",
            "state_policy": "All eight general registers, defined arithmetic flags and ordered word accesses checked; TEST auxiliary carry is undefined, zero normalization INC defines it",
            "not_claimed": [
                "Execution of the HeapAlloc instruction, runtime IAT contents, imported API behavior or allocation success",
                "Retry loop, error-pointer write, handler calls, return tails or enclosing owner behavior",
                "Third-party ownership inferred from import names, API or game execution, whole owner equivalence or accounting promotion",
            ],
        },
    }
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed during build",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run():
        _validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256
            and evidence["source_receipts"] == ids,
            "sealed handoff receipt differs",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_semantics(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    def run():
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_semantics(
    executable: Path, evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run():
        validate_structure(evidence, sources)
        actual = build_semantics(executable, sources)
        _require(
            _canonical_bytes(actual) == _canonical_bytes(evidence),
            "exact handoff receipt differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(actual["summary"]),
        }

    return _normalize(run)


def encode_semantics(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
