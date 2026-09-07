"""Conditional post-call allocation tails; opaque allocator effects are premises."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
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
from src.observatory.native_lua_vector_allocation_semantics import (
    SOURCE_PINS as ALLOCATION_SOURCE_PINS,
    ANALYSIS_KIND as ALLOCATION_KIND,
    SEALED_SHA256 as ALLOCATION_SEAL,
    OPS as ALLOCATION_OPS,
    SIZES,
    R,
    I,
    M,
    _grammar,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_vector_allocation_return_semantics"
SEALED_SHA256 = "c759a7f4c53e6382b5a3361ad5971aeaa9cefad21fb8912e05e02b29295af7ff"
SOURCE_PINS = {
    "program_facts": ALLOCATION_SOURCE_PINS["program_facts"],
    "allocation_semantics": (ALLOCATION_KIND, ALLOCATION_SEAL),
}
U32 = 0xFFFFFFFF
TAILS = {"large": (0x8A950, 0x8A962), "small": (0x8A968, 0x8A971)}
OPS = {
    pc: op
    for pc, op in ALLOCATION_OPS.items()
    if any(start <= pc < end for start, end in TAILS.values())
}
ORDER = list(OPS)


class AllocationReturnError(RuntimeError):
    """A conditional allocation return or storage relation differs."""


def _require(ok, message):
    if not ok:
        raise AllocationReturnError(message)


def _normalize(fn):
    try:
        return fn()
    except AllocationReturnError:
        raise
    except Exception as exc:
        raise AllocationReturnError(str(exc)) from exc


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)
    return value


def pointer_spec(pointer: int) -> dict[str, Any]:
    _u32(pointer, "post-call pointer")
    aligned = ((pointer + 35) % 2**32) // 32 * 32
    return {
        "aligned_pointer": aligned,
        "metadata_address": (aligned - 4) % 2**32,
        "displacement_word": (aligned - pointer) % 2**32,
    }


def storage_layout_spec(pointer: int, payload_bytes: int) -> dict[str, Any]:
    """Conditional geometry of an existing mapped block; no allocation promise."""
    _u32(pointer, "block pointer")
    _u32(payload_bytes, "payload byte count")
    _require(
        payload_bytes > 0 and pointer + payload_bytes + 35 <= 2**32,
        "outside positive nonwrapping block geometry",
    )
    aligned = ((pointer + 4 + 31) // 32) * 32
    metadata = aligned - 4
    block_end = pointer + payload_bytes + 35
    _require(
        pointer <= metadata and aligned + payload_bytes <= block_end and aligned <= U32,
        "storage geometry does not fit",
    )
    return {
        "block_begin": pointer,
        "block_exclusive_end": block_end,
        "aligned_pointer": aligned,
        "metadata_address": metadata,
        "payload_exclusive_end": aligned + payload_bytes,
        "payload_bytes": payload_bytes,
        "leading_bytes": aligned - pointer,
        "alignment": 32,
    }


def _add_flags(left, right):
    value = (left + right) & U32
    return {
        "cf": int(left + right > U32),
        "zf": int(value == 0),
        "sf": value >> 31,
        "of": ((~(left ^ right)) & (left ^ value) & U32) >> 31,
        "af": ((left ^ right ^ value) >> 4) & 1,
        "pf": int((value & 255).bit_count() % 2 == 0),
    }


def _and_flags(value):
    return {
        "cf": 0,
        "zf": int(value == 0),
        "sf": value >> 31,
        "of": 0,
        "af": None,
        "pf": int((value & 255).bit_count() % 2 == 0),
    }


def case_fixture(path, pointer, frame_alignment=0, seed=1):
    _require(path in TAILS, "invalid return path")
    relation = pointer_spec(pointer)
    _require(
        type(frame_alignment) is int and 0 <= frame_alignment < 16,
        "invalid frame alignment",
    )
    _u32(seed, "seed")
    frame = 0x30001000 + frame_alignment
    regs = {
        r: (0xA1000000 + i * 0x10101 + seed) & U32
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs.update(eax=pointer, ebp=frame, esp=frame - 4)
    saved_ebp = (0x55667788 + seed) & U32
    return_address = (0x44556677 + seed) & U32
    memory = {
        frame - 4: (0xBABE0000 + seed) & U32,
        frame: saved_ebp,
        frame + 4: return_address,
        frame + 8: (0xBABE0008 + seed) & U32,
    }
    if path == "large":
        metadata = relation["metadata_address"]
        _require(
            all(
                metadata + 4 <= address or address + 4 <= metadata for address in memory
            ),
            "metadata overlaps protected frame",
        )
        memory[metadata] = (0xCCDD0011 + seed) & U32
    return {
        "registers": regs,
        "memory": memory,
        "frame": frame,
        "saved_ebp": saved_ebp,
        "return_address": return_address,
    }


def model_case(path, pointer, frame_alignment=0, seed=1, ops=None):
    relation = pointer_spec(pointer)
    fixture = case_fixture(path, pointer, frame_alignment, seed)
    regs, memory = dict(fixture["registers"]), dict(fixture["memory"])
    initial = dict(regs)
    operations = OPS if ops is None else ops
    trace, events = [], []
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
            return arg[1]
        return access((regs[arg[1]] + arg[2]) & U32)

    def write(arg, value):
        if arg[0] == "reg":
            regs[arg[1]] = value
        else:
            address = (regs[arg[1]] + arg[2]) & U32
            _require(address in memory, "unmapped word write")
            memory[address] = value
            events.append(
                {"kind": "write", "address": address, "value": value, "width": 4}
            )

    pc = TAILS[path][0]
    return_address = None
    while return_address is None:
        _require(pc in operations and len(trace) < 20, "invalid return tail path")
        trace.append(f"0x{pc:08x}")
        op, *args = operations[pc]
        if op == "add":
            left, right = read(args[0]), read(args[1])
            write(args[0], (left + right) & U32)
            flags = _add_flags(left, right)
        elif op == "lea":
            write(args[0], (regs[args[1][1]] + args[1][2]) & U32)
        elif op == "and":
            value = read(args[0]) & read(args[1])
            write(args[0], value)
            flags = _and_flags(value)
        elif op == "mov":
            write(args[0], read(args[1]))
        elif op == "pop":
            write(args[0], access(regs["esp"]))
            regs["esp"] = (regs["esp"] + 4) & U32
        elif op == "ret":
            return_address = access(regs["esp"])
            regs["esp"] = (regs["esp"] + 4 + read(args[0])) & U32
        else:
            raise AllocationReturnError("unsupported return tail operation")
        pc += SIZES[pc]
    frame = fixture["frame"]
    result_pointer = relation["aligned_pointer"] if path == "large" else pointer
    expected_regs = dict(
        initial,
        eax=result_pointer,
        ecx=result_pointer,
        ebp=fixture["saved_ebp"],
        esp=frame + 12,
    )
    expected_events = []
    if path == "large":
        expected_events.append(
            {
                "kind": "write",
                "address": relation["metadata_address"],
                "value": pointer,
                "width": 4,
            }
        )
    expected_events.extend(
        [
            {
                "kind": "read",
                "address": frame,
                "value": fixture["saved_ebp"],
                "width": 4,
            },
            {
                "kind": "read",
                "address": frame + 4,
                "value": fixture["return_address"],
                "width": 4,
            },
        ]
    )
    expected_memory = dict(fixture["memory"])
    if path == "large":
        expected_memory[relation["metadata_address"]] = pointer
    expected_flags = (
        _and_flags(result_pointer) if path == "large" else _add_flags(frame - 4, 4)
    )
    _require(
        regs == expected_regs and flags == expected_flags,
        "return register or flag relation differs",
    )
    _require(
        events == expected_events and memory == expected_memory,
        "return ordered memory relation differs",
    )
    _require(return_address == fixture["return_address"], "return target differs")
    return {
        "inputs": {
            "path": path,
            "pointer": pointer,
            "frame_alignment": frame_alignment,
            "seed": seed,
        },
        "pointer_relation": relation,
        "return_address": return_address,
        "registers": regs,
        "arithmetic_flags": flags,
        "events": events,
        "memory": [{"address": a, "value": v} for a, v in sorted(memory.items())],
        "trace_rvas": trace,
    }


def case_inputs():
    return sorted(
        {
            base + offset
            for base in (0, 0x10000000, 0x7FFFFFC0, 0xFFFFFFC0)
            for offset in range(64)
            if base + offset <= U32
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


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    rows = _decode_body(data, image, sources["program_facts"], 0x8A920)
    _grammar(rows)
    _require(
        [_point(r) for r in rows] == sources["allocation_semantics"]["body"]["points"],
        "allocation source body differs",
    )
    inputs = case_inputs()
    cases = [
        model_case(path, pointer, a, s)
        for path in TAILS
        for pointer in inputs
        for a in range(16)
        for s in (0, U32)
    ]
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(union == [f"0x{p:08x}" for p in ORDER], "return tail coverage differs")
    controls = []
    for name, pc, replacement, path, pointer in (
        (
            "wrong_alignment_padding",
            0x8A953,
            ("lea", R("ecx"), M("eax", 34)),
            "large",
            29,
        ),
        (
            "wrong_alignment_mask",
            0x8A956,
            ("and", R("ecx"), I(0xFFFFFFF0)),
            "large",
            16,
        ),
        (
            "wrong_metadata_value",
            0x8A959,
            ("mov", M("ecx", -4), R("ecx")),
            "large",
            0x10000001,
        ),
        ("wrong_small_cleanup", 0x8A968, ("add", R("esp"), I(8)), "small", 0),
        ("wrong_return_pop", 0x8A95F, ("ret", I(0)), "large", 0),
    ):
        altered = dict(OPS)
        altered[pc] = replacement
        try:
            model_case(path, pointer, ops=altered)
        except AllocationReturnError:
            controls.append(
                {"name": name, "kind": "semantic_mutation", "rejected": True}
            )
        else:
            raise AllocationReturnError("semantic mutation accepted: " + name)
    try:
        case_fixture("large", 0x30000FDD)
    except AllocationReturnError:
        controls.append(
            {
                "name": "metadata_frame_overlap",
                "kind": "domain_rejection",
                "rejected": True,
            }
        )
    else:
        raise AllocationReturnError("metadata alias accepted")
    layouts = []
    for pointer in inputs:
        for size in (1, 4096, 0x10000):
            if pointer + size + 35 <= 2**32:
                layout = storage_layout_spec(pointer, size)
                _require(
                    layout["aligned_pointer"]
                    == pointer_spec(pointer)["aligned_pointer"],
                    "storage machine join differs",
                )
                layouts.append(layout)
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "body": dict(sources["allocation_semantics"]["body"]),
        "tails": [
            {
                "path": path,
                "entry_rva": f"0x{start:08x}",
                "exclusive_end_rva": f"0x{end:08x}",
                "bytes": end - start,
                "nodes": sum(start <= r.address - BASE < end for r in rows),
                "points": [_point(r) for r in rows if start <= r.address - BASE < end],
            }
            for path, (start, end) in TAILS.items()
        ],
        "matrix": {
            "pointer_inputs": inputs,
            "frame_base": 0x30001000,
            "frame_alignments": list(range(16)),
            "seeds": [0, U32],
        },
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
            "storage_cases_sha256": _canonical_sha256(layouts),
        },
        "summary": {
            "cases": len(cases),
            "storage_geometry_cases": len(layouts),
            "static_bytes": 91,
            "static_nodes": 34,
            "modeled_bytes": 27,
            "modeled_nodes": 11,
            "actual_native_executions": 0,
            "actual_allocator_calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "conditional_exact_integer_graph_model_of_post_allocator_return_tails",
            "entry_premises": [
                "An opaque allocator has returned to the selected tail with EAX pointer P",
                "EBP is F and ESP is F minus four; saved caller EBP and continuation are mapped at F and F plus four",
                "This finite model uses F equal to the declared frame base plus one of sixteen alignments; frame arithmetic does not wrap",
                "Large path metadata word at wrapped aligned pointer minus four is mapped and byte-disjoint from protected frame words",
                "No concurrent mutation or hardware faults; all preservation is relative to post-call entry state",
            ],
            "machine_relation": "Large path returns wrapped pointer P plus thirty-five rounded down to a multiple of thirty-two and writes P in the preceding word; small path returns P; both restore caller EBP and finish ESP at F plus twelve",
            "storage_relation": "Given an existing positive payload block of payload bytes plus thirty-five with no address wrap, aligned pointer is thirty-two times ceiling of P plus four divided by thirty-two, leading slack is four through thirty-five, and metadata and payload fit inside the block",
            "flags_policy": "Large AND leaves auxiliary carry undefined and recorded null; small path preserves six flags from the stack ADD",
            "not_claimed": [
                "Allocator execution, allocation success, mapped memory validity inferred from pointer arithmetic or original caller volatile-register preservation",
                "Aliasing metadata with protected frame words, full resize behavior, release behavior or exceptions",
                "API or game execution, replacement of append growth premises, whole owner equivalence or accounting promotion",
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
            "sealed allocation return receipt differs",
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
            "exact allocation return receipt differs",
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
