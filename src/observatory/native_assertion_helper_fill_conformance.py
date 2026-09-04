"""Finite isolated exact-body conformance against an independent byte-fill spec.

Unicorn is optional until exact replay. No game process is attached or modified.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_assertion_helper_leaf_callees import (
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
ANALYSIS_KIND = "pe_native_assertion_helper_fill_conformance"
SEALED_SHA256 = "6f4bba8750713184f5de2bf119b36605078e4386e05712a2f686b6e744801246"
ENTRY, SIZE = 0x370960, 346
BODY_SHA256 = "2607fbcc1ed351e6ec2189f6d8dbc41cd852954cce218e92cd8bf4b6aa976aa9"
UNICORN_VERSION = "2.1.4"
UNICORN_CORE_VERSION = (2, 1, 33621247)
CPU_MODEL = 19  # Unicorn's UC_CPU_X86_HASWELL, explicitly selected.
SOURCE_PINS = {
    "leaves": (
        "pe_native_assertion_helper_leaf_callees",
        "1ef7c1874b83e871f3afa9d482c2c6f01cd541c50f81b342605d80946a93f3c2",
    ),
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
}
BUFFER, BUFFER_SIZE = 0x1000000, 0x4000
STACK, SP, STOP = 0x2000000, 0x2000800, 0x3000000
GLOBAL_REP, GLOBAL_SIMD = BASE + 0x4B6E48, BASE + 0x493F30
MATRIX = {
    "alignments": list(range(16)),
    "dense_lengths": [0, 40],
    "boundary_centers": [64, 96, 128, 256, 384, 512, 1024, 4096],
    "boundary_deltas": [-1, 0, 1],
    "alignment_dependent_centers": [144, 400],
    "primary_values": [0, 0x123456AB, 0xFFFFFFFF],
    "dispatch_words": [[0, 0], [0, 2], [2, 0], [2, 2]],
    "extra_value_lengths": [1, 33, 129],
    "extra_values": [1, 0x7F, 0x80, 0xFF, 0x100],
    "noise_words": [
        [0xFFFFFFFD, 0xFFFFFFFD],
        [0xFFFFFFFD, 0xFFFFFFFF],
        [0xFFFFFFFF, 0xFFFFFFFD],
        [0xFFFFFFFF, 0xFFFFFFFF],
    ],
    "noise_lengths": [0, 1, 32, 33, 127, 128, 129, 512],
    "noise_alignments": [0, 1, 15],
}


class ConformanceError(RuntimeError):
    """A source, emulation check, or finite-domain receipt differs."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConformanceError(message)


def _normalize(operation: Any) -> Any:
    try:
        return operation()
    except ConformanceError:
        raise
    except Exception as exc:
        raise ConformanceError(str(exc)) from exc


def fill_spec(before: bytes, offset: int, length: int, value: int) -> bytes:
    """Independent finite-buffer contract, without the native path algorithm."""
    _require(isinstance(before, bytes), "buffer must be bytes")
    _require(
        all(type(v) is int for v in (offset, length, value)),
        "arguments must be integers",
    )
    _require(
        0 <= offset <= len(before) and 0 <= length <= len(before) - offset,
        "fill range differs",
    )
    _require(0 <= value <= 0xFFFFFFFF, "value is outside u32")
    return before[:offset] + bytes([value & 255]) * length + before[offset + length :]


def cases() -> list[tuple[int, int, int, int, int]]:
    result = set()
    for alignment in MATRIX["alignments"]:
        lengths = set(range(41))
        for center in MATRIX["boundary_centers"]:
            lengths.update(center + d for d in MATRIX["boundary_deltas"])
        for center in MATRIX["alignment_dependent_centers"]:
            lengths.update(center - alignment + d for d in MATRIX["boundary_deltas"])
        for length in lengths:
            for value in MATRIX["primary_values"]:
                for rep, simd in MATRIX["dispatch_words"]:
                    result.add((alignment, length, value, rep, simd))
        for length in MATRIX["extra_value_lengths"]:
            for value in MATRIX["extra_values"]:
                for rep, simd in MATRIX["dispatch_words"]:
                    result.add((alignment, length, value, rep, simd))
    for alignment in MATRIX["noise_alignments"]:
        for length in MATRIX["noise_lengths"]:
            for rep, simd in MATRIX["noise_words"]:
                result.add((alignment, length, 0x123456AB, rep, simd))
    return sorted(result)


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
        and _canonical_bytes(identity)
        == _canonical_bytes(sources["leaves"]["build_identity"]),
        "build identity differs",
    )
    body = sources["leaves"]["bodies"][1]
    _require(
        body["entry_rva"] == "0x00370960"
        and body["body_size"] == SIZE
        and body["body_sha256"] == BODY_SHA256,
        "source body differs",
    )
    return identities


def _runtime() -> Any:
    import unicorn

    _require(unicorn.__version__ == UNICORN_VERSION, "Unicorn version differs")
    _require(
        unicorn.uc_version() == UNICORN_CORE_VERSION, "Unicorn core version differs"
    )
    return unicorn


def _execute(
    code: bytes,
    vector: tuple[int, int, int, int, int],
    *,
    direction: bool = False,
    null_zero: bool = False,
) -> dict[str, Any]:
    u = _runtime()
    from unicorn import x86_const as x

    alignment, length, value, rep, simd = vector
    _require(
        0 <= alignment < 16
        and 0 <= length <= 4097
        and 0 <= value <= 0xFFFFFFFF
        and all(type(v) is int and 0 <= v <= 0xFFFFFFFF for v in (rep, simd)),
        "emulation vector outside finite domain",
    )
    _require(not null_zero or length == 0, "null destination requires zero length")
    uc = u.Uc(u.UC_ARCH_X86, u.UC_MODE_32)
    uc.ctl_set_cpu_model(CPU_MODEL)
    _require(uc.ctl_get_cpu_model() == CPU_MODEL, "Unicorn CPU model differs")
    start = BASE + ENTRY
    uc.mem_map(start & ~0xFFF, 0x1000, u.UC_PROT_ALL)
    uc.mem_write(start, code)
    uc.mem_protect(start & ~0xFFF, 0x1000, u.UC_PROT_READ | u.UC_PROT_EXEC)
    uc.mem_map(STOP, 0x1000, u.UC_PROT_READ | u.UC_PROT_EXEC)
    uc.mem_map(STACK, 0x1000, u.UC_PROT_READ | u.UC_PROT_WRITE)
    for address, word in ((GLOBAL_REP, rep), (GLOBAL_SIMD, simd)):
        uc.mem_map(address & ~0xFFF, 0x1000, u.UC_PROT_READ | u.UC_PROT_WRITE)
        uc.mem_write(address, struct.pack("<I", word))
        uc.mem_protect(address & ~0xFFF, 0x1000, u.UC_PROT_READ)
    before = bytes((i * 37 + 19) & 255 for i in range(BUFFER_SIZE))
    offset = 0x100 + alignment
    destination = 0 if null_zero else BUFFER + offset
    if not null_zero:
        uc.mem_map(BUFFER, BUFFER_SIZE, u.UC_PROT_READ | u.UC_PROT_WRITE)
        uc.mem_write(BUFFER, before)
    frame = struct.pack("<IIII", STOP, destination, value, length)
    uc.mem_write(SP, frame)
    preserved = {
        x.UC_X86_REG_EBX: 0x13579BDF,
        x.UC_X86_REG_ESI: 0x2468ACE0,
        x.UC_X86_REG_EDI: 0x3456789A,
        x.UC_X86_REG_EBP: 0x456789AB,
    }
    for reg, v in preserved.items():
        uc.reg_write(reg, v)
    uc.reg_write(x.UC_X86_REG_EAX, 0x56789ABC)
    uc.reg_write(x.UC_X86_REG_ECX, 0x6789ABCD)
    uc.reg_write(x.UC_X86_REG_EDX, 0x789ABCDE)
    uc.reg_write(x.UC_X86_REG_ESP, SP)
    uc.reg_write(x.UC_X86_REG_EFLAGS, 0x2 | (0x400 if direction else 0))
    nodes = set()
    edges = set()
    previous = None
    events = Counter()
    written = set()
    failure = []

    def fail(message: str) -> None:
        failure.append(message)
        uc.emu_stop()

    def instruction(_uc: Any, address: int, size: int, _data: Any) -> None:
        nonlocal previous
        if not start <= address < start + SIZE:
            fail("instruction escaped exact body")
            return
        rva = address - BASE
        nodes.add(rva)
        if previous is not None and previous != rva:
            edges.add((previous, rva))
        previous = rva

    def memory(
        _uc: Any, access: int, address: int, size: int, _value: int, _data: Any
    ) -> None:
        if access == u.UC_MEM_WRITE:
            if not (destination <= address and address + size <= destination + length):
                fail("write escaped destination")
                return
            written.update(range(address - destination, address - destination + size))
            events["writes"] += 1
        else:
            allowed = (SP <= address and address + size <= SP + 16) or any(
                a <= address and address + size <= a + 4
                for a in (GLOBAL_REP, GLOBAL_SIMD)
            )
            if not allowed:
                fail("read escaped declared inputs")
                return
            events["reads"] += 1

    uc.hook_add(u.UC_HOOK_CODE, instruction)
    uc.hook_add(u.UC_HOOK_MEM_READ | u.UC_HOOK_MEM_WRITE, memory)
    uc.emu_start(start, STOP, timeout=5000000, count=200000)
    _require(not failure, failure[0] if failure else "emulation failure")
    _require(uc.reg_read(x.UC_X86_REG_EIP) == STOP, "return sentinel not reached")
    _require(uc.reg_read(x.UC_X86_REG_ESP) == SP + 4, "stack return differs")
    _require(uc.reg_read(x.UC_X86_REG_EAX) == destination, "destination return differs")
    _require(
        all(uc.reg_read(r) == v for r, v in preserved.items()),
        "preserved register differs",
    )
    _require(bytes(uc.mem_read(SP, 16)) == frame, "input frame changed")
    _require(written == set(range(length)), "write union differs")
    if null_zero:
        output = b""
    else:
        output = bytes(uc.mem_read(BUFFER, BUFFER_SIZE))
        _require(
            output == fill_spec(before, offset, length, value),
            "fill specification differs",
        )
    return {
        "vector": list(vector),
        "null_zero": null_zero,
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "nodes": sorted(nodes),
        "edges": [list(e) for e in sorted(edges)],
        "memory_events": dict(sorted(events.items())),
    }


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    identities = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    rows = _decode_body(data, image, sources["program_facts"], ENTRY)
    body = sources["leaves"]["bodies"][1]
    _require(
        [_point(r) for r in rows] == body["points"],
        "source instruction witnesses differ",
    )
    code = b"".join(bytes(r.bytes) for r in rows)
    _require(
        len(code) == SIZE and hashlib.sha256(code).hexdigest() == BODY_SHA256,
        "exact body differs",
    )
    vectors = cases()
    results_hash = hashlib.sha256()
    nodes = set()
    edges = set()
    modes = {}

    def record(result: dict[str, Any]) -> None:
        results_hash.update(_canonical_bytes(result))
        nodes.update(result["nodes"])
        edges.update(tuple(e) for e in result["edges"])
        rep, simd = result["vector"][3:]
        key = f"{(rep>>1)&1}{(simd>>1)&1}"
        group = modes.setdefault(key, {"cases": 0, "nodes": set(), "edges": set()})
        group["cases"] += 1
        group["nodes"].update(result["nodes"])
        group["edges"].update(tuple(e) for e in result["edges"])

    for vector in vectors:
        record(_execute(code, vector))
    for rep, simd in MATRIX["dispatch_words"]:
        record(_execute(code, (0, 0, 0x123456AB, rep, simd), null_zero=True))
    try:
        _execute(code, (0, 128, 0xAB, 2, 0), direction=True)
    except ConformanceError as exc:
        _require(
            str(exc) == "write escaped destination",
            "direction negative control failed unexpectedly",
        )
    else:
        raise ConformanceError("direction negative control did not reject")
    declared_nodes = {int(n["rva"], 16) for n in body["control_flow_graph"]["nodes"]}
    declared_edges = {
        (int(n["rva"], 16), int(s, 16))
        for n in body["control_flow_graph"]["nodes"]
        for s in n["successor_rvas"]
    }
    _require(
        nodes <= declared_nodes and edges <= declared_edges,
        "dynamic trace escaped sealed CFG",
    )
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed during replay",
    )

    def hexnodes(values: Any) -> Any:
        return [f"0x{v:08x}" for v in sorted(values)]

    def hexedges(values: Any) -> Any:
        return [[f"0x{a:08x}", f"0x{b:08x}"] for a, b in sorted(values)]

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": identities,
        "body": {"entry_rva": f"0x{ENTRY:08x}", "size": SIZE, "sha256": BODY_SHA256},
        "emulator": {
            "name": "Unicorn",
            "version": UNICORN_VERSION,
            "native_core_version": list(UNICORN_CORE_VERSION),
            "cpu_model": {"id": CPU_MODEL, "name": "UC_CPU_X86_HASWELL"},
            "architecture": "x86",
            "bits": 32,
            "flat_segments": True,
            "instruction_limit": 200000,
            "timeout_microseconds": 5000000,
        },
        "matrix": MATRIX,
        "vector_sha256": _canonical_sha256([list(v) for v in vectors]),
        "results_sha256": results_hash.hexdigest(),
        "summary": {
            "ordinary_cases": len(vectors),
            "null_zero_cases": 4,
            "conforming_cases": len(vectors) + 4,
            "negative_controls": 1,
            "covered_nodes": len(nodes),
            "covered_edges": len(edges),
            "sealed_nodes": len(declared_nodes),
            "sealed_edges": len(declared_edges),
        },
        "coverage": {
            "nodes": hexnodes(nodes),
            "edges": hexedges(edges),
            "uncovered_nodes": hexnodes(declared_nodes - nodes),
            "uncovered_edges": hexedges(declared_edges - edges),
            "dispatch_groups": {
                k: {
                    "cases": v["cases"],
                    "nodes": hexnodes(v["nodes"]),
                    "edges": hexedges(v["edges"]),
                }
                for k, v in sorted(modes.items())
            },
        },
        "specification": {
            "output": "For each finite vector, preserve bytes outside the destination interval and set every destination byte to the low eight bits of the value argument.",
            "checks": [
                "Exact permitted write union, allowing repeated and overlapping writes",
                "Data reads limited to the argument and return frame and two four-byte dispatch inputs",
                "Return sentinel, EAX destination, ESP increment of four, unchanged EBX ESI EDI EBP and input frame",
                "No instruction execution outside the exact body before the return sentinel",
            ],
            "direction_control": {
                "input_df": 1,
                "length": 128,
                "rep_word": 2,
                "simd_word": 0,
                "expected_rejection": "write escaped destination",
            },
        },
        "scope": {
            "evidence_class": "finite_exact_body_emulation_conformance",
            "positive_direction_flag": 0,
            "specification_independent_of_native_path_algorithm": True,
            "not_claimed": [
                "Native game or real CPU execution; CRT identity; ownership; accounting promotion",
                "All lengths, values, addresses, register states or flags; proof beyond the finite matrix",
                "Signed oversized lengths, address wrapping, nonempty inaccessible buffers, overlapping stack code or globals, non-flat segments",
                "CPU feature availability, faults, exceptions, concurrency, timing, flags or volatile register outputs",
                "REP micro-iteration CFG coverage; repeated same-address events are excluded from branch coverage",
            ],
            "source_validation": "Source receipts are canonical-pinned; exact PE hash, body bytes and instruction witnesses are rechecked, without rerunning the original whole-atlas analysis.",
        },
    }


def validate_structure(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        identities = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256,
            "sealed conformance receipt differs",
        )
        _require(
            evidence["source_receipts"] == identities and evidence["matrix"] == MATRIX,
            "source or matrix differs",
        )
        _require(
            evidence["vector_sha256"] == _canonical_sha256([list(v) for v in cases()]),
            "vector hash differs",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_conformance(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_conformance(
    executable: Path, evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        validate_structure(evidence, sources)
        result = build_conformance(executable, sources)
        _require(
            _canonical_bytes(result) == _canonical_bytes(evidence),
            "exact replay differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(result["summary"]),
        }

    return _normalize(run)


def encode_conformance(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
