"""Pinned growth-capacity decision: stop before either child or cleanup executes."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import capstone.x86_const as x86
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
from src.observatory.native_lua_class_vector_append_semantics import (
    SOURCE_PINS as APPEND_SOURCE_PINS,
    ANALYSIS_KIND as APPEND_KIND,
    SEALED_SHA256 as APPEND_SEAL,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_vector_growth_semantics"
SEALED_SHA256 = "6e442065281f9d7f1853dbb2d2dd91b3d5645cae16a5497db772b7a66f28ec69"
SOURCE_PINS = {**APPEND_SOURCE_PINS, "append_semantics": (APPEND_KIND, APPEND_SEAL)}
START, END = 0x2EB620, 0x2EB67E
RESIZE, NO_GROWTH, FAILURE = 0x2EB669, 0x2EB66F, 0x2EB674
STOPS = (RESIZE, NO_GROWTH, FAILURE)
U32, MAX_ELEMENTS = 0xFFFFFFFF, 0x1FFFFFFF


def R(name):
    return ("reg", name)


def I(value):
    return ("imm", value)


def M(base, offset=0):
    return ("mem", base, offset)


OPS = {
    0x2EB620: ("push", R("esi")),
    0x2EB621: ("mov", R("esi"), R("ecx")),
    0x2EB623: ("push", R("edi")),
    0x2EB624: ("mov", R("edi"), M("esi", 8)),
    0x2EB627: ("mov", R("eax"), R("edi")),
    0x2EB629: ("mov", R("edx"), M("esi", 4)),
    0x2EB62C: ("sub", R("eax"), R("edx")),
    0x2EB62E: ("sar", R("eax"), I(3)),
    0x2EB631: ("cmp", R("eax"), I(1)),
    0x2EB634: ("jae", I(BASE + NO_GROWTH)),
    0x2EB636: ("mov", R("ecx"), M("esi")),
    0x2EB638: ("sub", R("edx"), R("ecx")),
    0x2EB63A: ("push", R("ebx")),
    0x2EB63B: ("mov", R("ebx"), I(MAX_ELEMENTS)),
    0x2EB640: ("sar", R("edx"), I(3)),
    0x2EB643: ("mov", R("eax"), R("ebx")),
    0x2EB645: ("sub", R("eax"), R("edx")),
    0x2EB647: ("cmp", R("eax"), I(1)),
    0x2EB64A: ("jb", I(BASE + FAILURE)),
    0x2EB64C: ("sub", R("edi"), R("ecx")),
    0x2EB64E: ("inc", R("edx")),
    0x2EB64F: ("sar", R("edi"), I(3)),
    0x2EB652: ("xor", R("ecx"), R("ecx")),
    0x2EB654: ("mov", R("eax"), R("edi")),
    0x2EB656: ("shr", R("eax"), I(1)),
    0x2EB658: ("sub", R("ebx"), R("eax")),
    0x2EB65A: ("add", R("eax"), R("edi")),
    0x2EB65C: ("cmp", R("ebx"), R("edi")),
    0x2EB65E: ("cmovae", R("ecx"), R("eax")),
    0x2EB661: ("cmp", R("ecx"), R("edx")),
    0x2EB663: ("cmovae", R("edx"), R("ecx")),
    0x2EB666: ("mov", R("ecx"), R("esi")),
    0x2EB668: ("push", R("edx")),
    RESIZE: ("call", I(BASE + 0x2EB680)),
    0x2EB66E: ("pop", R("ebx")),
    NO_GROWTH: ("pop", R("edi")),
    0x2EB670: ("pop", R("esi")),
    0x2EB671: ("ret", I(4)),
    FAILURE: ("push", I(0x820938)),
    0x2EB679: ("call", I(BASE + 0x3435D9)),
}
ORDER = list(OPS)
SIZES = {
    p: (ORDER[i + 1] if i + 1 < len(ORDER) else END) - p for i, p in enumerate(ORDER)
}


class GrowthError(RuntimeError):
    """A pinned witness or independent capacity relation differs."""


def _require(ok, message):
    if not ok:
        raise GrowthError(message)


def _normalize(fn):
    try:
        return fn()
    except GrowthError:
        raise
    except Exception as exc:
        raise GrowthError(str(exc)) from exc


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)
    return value


def _sar3(value):
    # Division of the signed representative, rounded toward negative infinity.
    return ((value if value < 2**31 else value - 2**32) // 8) & U32


def growth_spec(begin: int, end: int, capacity: int) -> dict[str, Any]:
    for key, value in locals().copy().items():
        _u32(value, key)
    spare = _sar3((capacity - end) & U32)
    if ((capacity - end) & U32) >= 8:
        return {
            "outcome": "no_growth",
            "stop_rva": NO_GROWTH,
            "spare_word": spare,
            "requested": None,
        }
    size = _sar3((end - begin) & U32)
    old_capacity = _sar3((capacity - begin) & U32)
    half = old_capacity // 2
    available = (MAX_ELEMENTS - half) % 2**32
    proposed_sum = (old_capacity + half) % 2**32
    candidate = proposed_sum if old_capacity <= available else 0
    minimum = (size + 1) % 2**32
    # SAR3 cannot produce MAX_ELEMENTS: the failure comparison cannot succeed.
    _require(size != MAX_ELEMENTS, "impossible signed-shift image")
    return {
        "outcome": "resize_request",
        "stop_rva": RESIZE,
        "spare_word": spare,
        "size_word": size,
        "capacity_word": old_capacity,
        "half_word": half,
        "available_word": available,
        "sum_word": proposed_sum,
        "candidate_word": candidate,
        "minimum_word": minimum,
        "requested": max(minimum, candidate),
    }


def aligned_geometry_spec(begin: int, end: int, capacity: int) -> dict[str, Any]:
    """Ordinary nonwrapping geometry with nonnegative signed byte differences."""
    for key, value in locals().copy().items():
        _u32(value, key)
    _require(
        begin <= end <= capacity
        and (end - begin) % 8 == 0
        and (capacity - begin) % 8 == 0
        and capacity - begin < 2**31,
        "outside ordinary aligned geometry",
    )
    size, count = (end - begin) // 8, (capacity - begin) // 8
    requested = None if size < count else max(size + 1, count + count // 2)
    return {
        "size": size,
        "capacity": count,
        "requested": requested,
        "outcome": "no_growth" if requested is None else "resize_request",
    }


def _cmp_flags(left, right):
    result = (left - right) & U32
    return {
        "cf": int(left < right),
        "zf": int(result == 0),
        "sf": result >> 31,
        "of": ((left ^ right) & (left ^ result)) >> 31,
        "af": ((left ^ right ^ result) >> 4) & 1,
        "pf": int((result & 255).bit_count() % 2 == 0),
    }


def case_fixture(begin, end, capacity, frame_alignment=0, seed=1):
    growth_spec(begin, end, capacity)
    _require(
        type(frame_alignment) is int and 0 <= frame_alignment < 16,
        "invalid frame alignment",
    )
    _u32(seed, "seed")
    obj, stack = 0x10000040, 0x30001000 + frame_alignment
    regs = {
        r: (0xA1000000 + i * 0x10101 + seed) & U32
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs.update(ecx=obj, esp=stack)
    words = {
        obj: begin,
        obj + 4: end,
        obj + 8: capacity,
        **{stack + i: (0xBABE0000 + i + seed) & U32 for i in (-16, -12, -8, -4, 0, 4)},
    }
    return {"registers": regs, "memory": words, "object": obj, "stack": stack}


def model_case(begin, end, capacity, frame_alignment=0, seed=1, ops=None):
    spec = growth_spec(begin, end, capacity)
    fixture = case_fixture(begin, end, capacity, frame_alignment, seed)
    initial, memory = fixture["registers"], dict(fixture["memory"])
    regs = dict(initial)
    operations = OPS if ops is None else ops
    events, trace = [], []
    flags = None

    def read(arg):
        if arg[0] == "reg":
            return regs[arg[1]]
        if arg[0] == "imm":
            return arg[1]
        address = (regs[arg[1]] + arg[2]) & U32
        _require(address in memory, "unmapped word read")
        value = memory[address]
        events.append({"kind": "read", "address": address, "value": value, "width": 4})
        return value

    pc = START
    while pc not in STOPS:
        _require(pc in operations and len(trace) < 80, "invalid decision path")
        trace.append(f"0x{pc:08x}")
        op, *args = operations[pc]
        next_pc = pc + SIZES[pc]
        if op == "push":
            value = read(args[0])
            regs["esp"] = (regs["esp"] - 4) & U32
            _require(regs["esp"] in memory, "unmapped stack write")
            memory[regs["esp"]] = value
            events.append(
                {"kind": "write", "address": regs["esp"], "value": value, "width": 4}
            )
        elif op in ("jae", "jb"):
            _require(flags is not None, "missing comparison flags")
            if flags["cf"] == (0 if op == "jae" else 1):
                next_pc = read(args[0]) - BASE
        elif op == "cmp":
            flags = _cmp_flags(read(args[0]), read(args[1]))
        elif op == "cmovae":
            if flags["cf"] == 0:
                regs[args[0][1]] = read(args[1])
        elif op == "mov":
            regs[args[0][1]] = read(args[1])
        else:
            left = read(args[0])
            right = read(args[1]) if len(args) > 1 else 1
            if op == "sub":
                value = left - right
            elif op == "add":
                value = left + right
            elif op == "inc":
                value = left + 1
            elif op == "xor":
                value = left ^ right
            elif op == "shr":
                value = left >> right
            elif op == "sar":
                value = (left if left < 0x80000000 else left - 0x100000000) >> right
            else:
                raise GrowthError("unsupported decision operation")
            regs[args[0][1]] = value & U32
            # Only CMP-produced flags are consumed or observed in this exact graph.
            flags = None
        pc = next_pc

    obj, stack = fixture["object"], fixture["stack"]
    expected_regs = dict(
        initial, esi=obj, edi=capacity, eax=spec["spare_word"], edx=end, esp=stack - 8
    )
    expected_events = [
        {"kind": "write", "address": stack - 4, "value": initial["esi"], "width": 4},
        {"kind": "write", "address": stack - 8, "value": initial["edi"], "width": 4},
        {"kind": "read", "address": obj + 8, "value": capacity, "width": 4},
        {"kind": "read", "address": obj + 4, "value": end, "width": 4},
    ]
    expected_flags = _cmp_flags(spec["spare_word"], 1)
    if spec["outcome"] == "resize_request":
        expected_regs.update(
            edi=spec["capacity_word"],
            eax=spec["sum_word"],
            ebx=spec["available_word"],
            edx=spec["requested"],
            esp=stack - 16,
        )
        expected_events.extend(
            [
                {"kind": "read", "address": obj, "value": begin, "width": 4},
                {
                    "kind": "write",
                    "address": stack - 12,
                    "value": initial["ebx"],
                    "width": 4,
                },
                {
                    "kind": "write",
                    "address": stack - 16,
                    "value": spec["requested"],
                    "width": 4,
                },
            ]
        )
        expected_flags = _cmp_flags(spec["candidate_word"], spec["minimum_word"])
    expected_memory = dict(fixture["memory"])
    for event in expected_events:
        if event["kind"] == "write":
            expected_memory[event["address"]] = event["value"]
    _require(
        pc == spec["stop_rva"] and regs == expected_regs,
        "capacity boundary register relation differs",
    )
    _require(
        events == expected_events and memory == expected_memory,
        "ordered memory relation differs",
    )
    _require(flags == expected_flags, "boundary arithmetic flags differ")
    return {
        "inputs": {
            "begin": begin,
            "end": end,
            "capacity": capacity,
            "frame_alignment": frame_alignment,
            "seed": seed,
        },
        "specification": spec,
        "stop_rva": f"0x{pc:08x}",
        "registers": regs,
        "arithmetic_flags": flags,
        "events": events,
        "memory": [{"address": a, "value": v} for a, v in sorted(memory.items())],
        "trace_rvas": trace,
    }


def case_inputs():
    values = (
        0,
        1,
        7,
        8,
        15,
        16,
        0x7FFFFFF8,
        0x7FFFFFFF,
        0x80000000,
        0x80000007,
        0xFFFFFFF8,
        0xFFFFFFFF,
    )
    result = {(b, e, c) for b in values for e in values for c in values}
    # Cross every SAR sign/wrap boundary with each sub-element spare byte.
    for begin in (0, 7, 0x80000000, 0xFFFFFFF8):
        for span in values:
            end = (begin + span) & U32
            for spare in range(9):
                result.add((begin, end, (end + spare) & U32))
    return sorted(result)


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
    _require([r.address - BASE for r in rows] == ORDER, "growth body points differ")
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
                args.append(M(row.reg_name(arg.mem.base), arg.mem.disp))
            else:
                raise GrowthError("unexpected operand")
        pc = row.address - BASE
        widths = [4, 1] if row.mnemonic == "sar" else [4] * len(args)
        _require(
            (row.mnemonic, *args) == OPS[pc]
            and row.size == SIZES[pc]
            and [a.size for a in row.operands] == widths,
            "exact growth grammar differs",
        )


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    rows = _decode_body(data, image, sources["program_facts"], START)
    _grammar(rows)
    bodyhash = hashlib.sha256(b"".join(bytes(r.bytes) for r in rows)).hexdigest()
    witness = sources["append_semantics"]["growth_static_witness"]
    _require(
        witness["sha256"] == bodyhash
        and witness["points"] == [_point(r) for r in rows]
        and witness["bytes"] == 94
        and witness["nodes"] == 40,
        "append growth witness differs",
    )
    inputs = case_inputs()
    cases = [
        model_case(*values, alignment, seed)
        for values in inputs
        for alignment in (0, 1, 7, 15)
        for seed in (0, 0xFFFFFFFF)
    ]
    union = sorted({p for case in cases for p in case["trace_rvas"]})
    _require(
        union == [f"0x{p:08x}" for p in ORDER if p < RESIZE],
        "decision coverage differs",
    )
    controls = []
    for name, pc, replacement, values in (
        (
            "logical_size_shift",
            0x2EB640,
            ("shr", R("edx"), I(3)),
            (0, 0x80000000, 0x80000000),
        ),
        ("wrong_spare_shift", 0x2EB62E, ("sar", R("eax"), I(2)), (0, 0, 4)),
        ("wrong_capacity_half", 0x2EB656, ("shr", R("eax"), I(2)), (0, 32, 32)),
        ("wrong_minimum_increment", 0x2EB64E, ("add", R("edx"), I(2)), (0, 0, 0)),
        ("wrong_metadata_read", 0x2EB624, ("mov", R("edi"), M("esi", 4)), (0, 0, 8)),
    ):
        altered = dict(OPS)
        altered[pc] = replacement
        try:
            model_case(*values, ops=altered)
        except GrowthError:
            controls.append(
                {"name": name, "kind": "semantic_mutation", "rejected": True}
            )
        else:
            raise GrowthError("semantic mutation accepted: " + name)
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "body": {
            "entry_rva": f"0x{START:08x}",
            "exclusive_end_rva": f"0x{END:08x}",
            "bytes": 94,
            "nodes": 40,
            "sha256": bodyhash,
            "points": [_point(r) for r in rows],
        },
        "frontiers": {
            "resize_call": f"0x{RESIZE:08x}",
            "no_growth_cleanup": f"0x{NO_GROWTH:08x}",
            "unreachable_failure_block": f"0x{FAILURE:08x}",
        },
        "failure_unreachability": {
            "sar3_unsigned_image": [[0, 0x0FFFFFFF], [0xF0000000, U32]],
            "required_size_word": MAX_ELEMENTS,
            "reason": "Unsigned wrapped MAX_ELEMENTS minus size is below one exactly when size equals MAX_ELEMENTS, outside the SAR3 image",
        },
        "matrix": {
            "input_tuples": len(inputs),
            "inputs_sha256": _canonical_sha256([list(v) for v in inputs]),
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
            "static_bytes": 94,
            "static_nodes": 40,
            "modeled_nodes": len(union),
            "resize_frontiers": sum(c["stop_rva"] == f"0x{RESIZE:08x}" for c in cases),
            "no_growth_frontiers": sum(
                c["stop_rva"] == f"0x{NO_GROWTH:08x}" for c in cases
            ),
            "failure_frontiers": 0,
            "actual_native_executions": 0,
            "actual_child_calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "exact_integer_graph_model_with_independent_u32_capacity_specification",
            "premises": [
                "Mapped stable three-word object and disjoint mapped stack slots",
                "No asynchronous mutation or hardware faults during the bounded decision",
                "Synthetic u32 fields need not describe allocated storage",
            ],
            "ordinary_geometry": "Ordered nonwrapping fields with eight-byte element differences and total byte span below 2**31: retain spare capacity; at full capacity request the larger of size plus one and capacity plus floor of half capacity",
            "machine_relation": "No growth exactly when u32(capacity-end) >= 8; otherwise compute signed SAR3 size and capacity words and wrapped unsigned guarded growth, stopping before the resize call",
            "state_policy": "All eight general registers, six arithmetic flags at boundary, every explicit ordered word access, and unchanged fixture words checked; EIP is the stop RVA",
            "not_claimed": [
                "Resize child, allocator, failure callee or cleanup execution",
                "Successful allocation, element relocation, exception behavior or return convention semantics",
                "Actual API or game execution, replacement of append growth summaries, whole owner equivalence or accounting promotion",
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
            "sealed growth receipt differs",
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
            "exact growth receipt differs",
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
