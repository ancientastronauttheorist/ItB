"""Bounded vector deallocation arithmetic and metadata guards; no free executes."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import capstone.x86_const as x86
from src.observatory import native_lua_vector_allocation_semantics as allocation
from src.observatory import native_lua_vector_allocation_return_semantics as returns
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
ANALYSIS_KIND = "pe_native_vector_deallocation_semantics"
SEALED_SHA256 = "7db0ff16946971f721c3d8246af544a5d009095004a63453285f72d4b05de351"
SOURCE_PINS = {
    "program_facts": allocation.SOURCE_PINS["program_facts"],
    "allocation_semantics": (allocation.ANALYSIS_KIND, allocation.SEALED_SHA256),
    "return_semantics": (returns.ANALYSIS_KIND, returns.SEALED_SHA256),
}
START, END, DIVISION, FREE_CALL, FAILURE = 0x7800, 0x785B, 0x780B, 0x7851, 0x379F02
U32 = 0xFFFFFFFF


def R(name):
    return ("reg", name)


def I(value):
    return ("imm", value)


def M(base, offset=0):
    return ("mem", base, offset)


OPS = {
    0x7800: ("push", R("ebp")),
    0x7801: ("mov", R("ebp"), R("esp")),
    0x7803: ("or", R("eax"), I(U32)),
    0x7806: ("mov", R("ecx"), M("ebp", 12)),
    0x7809: ("xor", R("edx"), R("edx")),
    DIVISION: ("div", M("ebp", 16)),
    0x780E: ("cmp", R("ecx"), R("eax")),
    0x7810: ("ja", I(BASE + FAILURE)),
    0x7816: ("imul", R("ecx"), M("ebp", 16)),
    0x781A: ("cmp", R("ecx"), I(4096)),
    0x7820: ("jb", I(BASE + 0x784D)),
    0x7822: ("mov", R("eax"), M("ebp", 8)),
    0x7825: ("test", R("al"), I(31)),
    0x7827: ("jne", I(BASE + FAILURE)),
    0x782D: ("mov", R("ecx"), M("eax", -4)),
    0x7830: ("cmp", R("ecx"), R("eax")),
    0x7832: ("jae", I(BASE + FAILURE)),
    0x7838: ("sub", R("eax"), R("ecx")),
    0x783A: ("cmp", R("eax"), I(4)),
    0x783D: ("jb", I(BASE + FAILURE)),
    0x7843: ("cmp", R("eax"), I(35)),
    0x7846: ("jbe", I(BASE + 0x7850)),
    0x7848: ("jmp", I(BASE + FAILURE)),
    0x784D: ("mov", R("ecx"), M("ebp", 8)),
    0x7850: ("push", R("ecx")),
    FREE_CALL: ("call", I(BASE + 0x35785D)),
    0x7856: ("add", R("esp"), I(4)),
    0x7859: ("pop", R("ebp")),
    0x785A: ("ret",),
}
ORDER = list(OPS)
SIZES = {
    p: (ORDER[i + 1] if i + 1 < len(ORDER) else END) - p for i, p in enumerate(ORDER)
}


class DeallocationError(RuntimeError):
    """A deallocation guard, independent inverse relation or exact witness differs."""


def _require(ok, message):
    if not ok:
        raise DeallocationError(message)


def _normalize(fn):
    try:
        return fn()
    except DeallocationError:
        raise
    except Exception as exc:
        raise DeallocationError(str(exc)) from exc


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)
    return value


def deallocation_spec(pointer, count, stride, raw_metadata=None):
    for name, value in (("pointer", pointer), ("count", count), ("stride", stride)):
        _u32(value, name)
    if raw_metadata is not None:
        _u32(raw_metadata, "metadata word")
    result = {
        "outcome": "guard_failure",
        "reason": None,
        "stop_rva": FAILURE,
        "quotient": None,
        "remainder": None,
        "byte_count": None,
        "free_argument": None,
        "metadata_read": False,
        "transfer_site": None,
    }
    if stride == 0:
        result.update(
            outcome="division_frontier", reason="zero_stride", stop_rva=DIVISION
        )
        return result
    quotient, remainder = divmod(U32, stride)
    result.update(quotient=quotient, remainder=remainder)
    if count > quotient:
        result.update(reason="count_overflow", transfer_site=0x7810)
        return result
    size = count * stride
    result["byte_count"] = size
    if size < 4096:
        result.update(
            outcome="free_frontier", stop_rva=FREE_CALL, free_argument=pointer
        )
        return result
    if pointer % 32:
        result.update(reason="misaligned_pointer", transfer_site=0x7827)
        return result
    _require(raw_metadata is not None, "large aligned pointer needs mapped metadata")
    result["metadata_read"] = True
    if raw_metadata >= pointer:
        result.update(reason="metadata_not_below_pointer", transfer_site=0x7832)
        return result
    delta = pointer - raw_metadata
    if delta < 4:
        result.update(reason="metadata_distance_below_four", transfer_site=0x783D)
        return result
    if delta > 35:
        result.update(
            reason="metadata_distance_above_thirty_five", transfer_site=0x7848
        )
        return result
    result.update(
        outcome="free_frontier", stop_rva=FREE_CALL, free_argument=raw_metadata
    )
    return result


def caller_stride8_spec(pointer, count, raw_metadata=None):
    return deallocation_spec(pointer, count, 8, raw_metadata)


def inverse_storage_spec(raw, payload_bytes):
    _u32(raw, "raw block pointer")
    _u32(payload_bytes, "payload bytes")
    _require(
        payload_bytes >= 4096 and payload_bytes % 8 == 0,
        "inverse requires large eight-byte-element payload",
    )
    layout = _normalize(lambda: returns.storage_layout_spec(raw, payload_bytes))
    guard = deallocation_spec(layout["aligned_pointer"], payload_bytes // 8, 8, raw)
    _require(
        guard["outcome"] == "free_frontier" and guard["free_argument"] == raw,
        "alignment inverse differs",
    )
    return {
        "raw_pointer": raw,
        "payload_bytes": payload_bytes,
        "aligned_pointer": layout["aligned_pointer"],
        "metadata_address": layout["metadata_address"],
        "metadata_word": raw,
        "leading_bytes": layout["leading_bytes"],
        "free_argument": guard["free_argument"],
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


def _logical_flags(value, width=32):
    return {
        "cf": 0,
        "zf": int(value == 0),
        "sf": (value >> (width - 1)) & 1,
        "of": 0,
        "af": None,
        "pf": int((value & 255).bit_count() % 2 == 0),
    }


def case_fixture(pointer, count, stride, raw_metadata=None, frame_alignment=0, seed=1):
    spec = deallocation_spec(pointer, count, stride, raw_metadata)
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
        stack + i: (0xBABE0000 + i + seed) & U32 for i in (-8, -4, 0, 4, 8, 12, 16)
    }
    memory.update({stack + 4: pointer, stack + 8: count, stack + 12: stride})
    if spec["metadata_read"]:
        address = (pointer - 4) & U32
        _require(
            all(address + 4 <= a or a + 4 <= address for a in memory),
            "metadata overlaps protected frame",
        )
        memory[address] = raw_metadata
    return {"registers": regs, "memory": memory, "stack": stack}


def model_case(
    pointer, count, stride, raw_metadata=None, frame_alignment=0, seed=1, ops=None
):
    spec = deallocation_spec(pointer, count, stride, raw_metadata)
    fixture = case_fixture(pointer, count, stride, raw_metadata, frame_alignment, seed)
    initial = fixture["registers"]
    regs, memory = dict(initial), dict(fixture["memory"])
    operations = OPS if ops is None else ops
    trace, events = [], []
    flags = None
    pc = START

    def access(address):
        _require(address in memory, "unmapped word read")
        value = memory[address]
        events.append({"kind": "read", "address": address, "value": value, "width": 4})
        return value

    def read(arg):
        if arg[0] == "reg":
            return regs["eax"] & 255 if arg[1] == "al" else regs[arg[1]]
        if arg[0] == "imm":
            return arg[1] & U32
        return access((regs[arg[1]] + arg[2]) & U32)

    while pc not in (FREE_CALL, FAILURE) and not (pc == DIVISION and stride == 0):
        _require(pc in operations and len(trace) < 60, "invalid guard path")
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
        elif op == "mov":
            regs[args[0][1]] = read(args[1])
        elif op in ("or", "xor", "test"):
            left, right = read(args[0]), read(args[1])
            value = (
                left | right
                if op == "or"
                else left ^ right if op == "xor" else left & right
            )
            if op != "test":
                regs[args[0][1]] = value
            flags = _logical_flags(value, 8 if args[0] == R("al") else 32)
        elif op == "div":
            denominator = read(args[0])
            _require(denominator > 0, "zero divisor outside explicit frontier")
            quotient, remainder = divmod((regs["edx"] << 32) | regs["eax"], denominator)
            _require(quotient <= U32, "division quotient overflow")
            regs.update(eax=quotient, edx=remainder)
            flags = None
        elif op == "imul":
            regs[args[0][1]] = (read(args[0]) * read(args[1])) & U32
            flags = None
        elif op == "sub":
            regs[args[0][1]] = (read(args[0]) - read(args[1])) & U32
            flags = None
        elif op == "cmp":
            flags = _cmp_flags(read(args[0]), read(args[1]))
        elif op in ("ja", "jb", "jae", "jbe", "jne", "jmp"):
            take = (
                op == "jmp"
                or op == "ja"
                and not (flags["cf"] or flags["zf"])
                or op == "jb"
                and flags["cf"]
                or op == "jae"
                and not flags["cf"]
                or op == "jbe"
                and (flags["cf"] or flags["zf"])
                or op == "jne"
                and not flags["zf"]
            )
            if take:
                next_pc = read(args[0]) - BASE
        else:
            raise DeallocationError("unsupported bounded guard operation")
        pc = next_pc
    stack = fixture["stack"]
    expected_regs = dict(
        initial, ebp=stack - 4, esp=stack - 4, eax=U32, ecx=count, edx=0
    )
    expected_events = [
        {"kind": "write", "address": stack - 4, "value": initial["ebp"], "width": 4},
        {"kind": "read", "address": stack + 8, "value": count, "width": 4},
    ]
    expected_flags = _logical_flags(0)
    if stride:
        expected_events.append(
            {"kind": "read", "address": stack + 12, "value": stride, "width": 4}
        )
        expected_regs.update(eax=spec["quotient"], edx=spec["remainder"])
        expected_flags = _cmp_flags(count, spec["quotient"])
        if spec["reason"] != "count_overflow":
            expected_events.append(
                {"kind": "read", "address": stack + 12, "value": stride, "width": 4}
            )
            expected_regs["ecx"] = spec["byte_count"]
            expected_flags = _cmp_flags(spec["byte_count"], 4096)
            expected_events.append(
                {"kind": "read", "address": stack + 4, "value": pointer, "width": 4}
            )
            if spec["byte_count"] < 4096:
                expected_regs["ecx"] = pointer
            else:
                expected_regs["eax"] = pointer
                expected_flags = _logical_flags(pointer & 31, 8)
                if spec["metadata_read"]:
                    expected_events.append(
                        {
                            "kind": "read",
                            "address": (pointer - 4) & U32,
                            "value": raw_metadata,
                            "width": 4,
                        }
                    )
                    expected_regs["ecx"] = raw_metadata
                    expected_flags = _cmp_flags(raw_metadata, pointer)
                    if raw_metadata < pointer:
                        delta = pointer - raw_metadata
                        expected_regs["eax"] = delta
                        expected_flags = _cmp_flags(delta, 4)
                        if delta >= 4:
                            expected_flags = _cmp_flags(delta, 35)
        if spec["outcome"] == "free_frontier":
            expected_regs["esp"] = stack - 8
            expected_events.append(
                {
                    "kind": "write",
                    "address": stack - 8,
                    "value": spec["free_argument"],
                    "width": 4,
                }
            )
    expected_memory = dict(fixture["memory"])
    for event in expected_events:
        if event["kind"] == "write":
            expected_memory[event["address"]] = event["value"]
    _require(
        pc == spec["stop_rva"] and regs == expected_regs and flags == expected_flags,
        "guard boundary register or flag relation differs",
    )
    _require(
        events == expected_events and memory == expected_memory,
        "guard ordered memory relation differs",
    )
    return {
        "inputs": {
            "pointer": pointer,
            "count": count,
            "stride": stride,
            "raw_metadata": raw_metadata,
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
    cases = set()
    for stride in (0, 1, 2, 7, 8, 16, 4096, 0x80000000, U32):
        quotient = U32 // stride if stride else 0
        counts = {0, 1, 511, 512, quotient}
        if quotient < U32:
            counts.add(quotient + 1)
        for count in counts:
            for pointer in (0, 0x10000020, 0x10000021, 0x80000000, 0xFFFFFFE0):
                for delta in (0, 1, 3, 4, 31, 32, 35, 36):
                    cases.add((pointer, count, stride, (pointer - delta) & U32))
    return sorted(cases)


def _preflight(sources):
    _require(
        isinstance(sources, Mapping) and set(sources) == set(SOURCE_PINS),
        "source partition differs",
    )
    ids = {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }
    _require(
        sources["allocation_semantics"]["body"] == sources["return_semantics"]["body"],
        "allocation-return witness join differs",
    )
    return ids


def _grammar(rows):
    _require(
        [r.address - BASE for r in rows] == ORDER, "deallocation body points differ"
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
                args.append(M(row.reg_name(arg.mem.base), arg.mem.disp))
            else:
                raise DeallocationError("unexpected operand")
        pc = row.address - BASE
        _require(
            (row.mnemonic, *args) == OPS[pc]
            and row.size == SIZES[pc]
            and [a.size for a in row.operands]
            == ([1, 1] if pc == 0x7825 else [4] * len(args)),
            "exact guard grammar differs",
        )


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    rows = _decode_body(data, image, sources["program_facts"], START)
    _grammar(rows)
    resize = _decode_body(data, image, sources["program_facts"], 0x2EB680)
    witness = sources["allocation_semantics"]["resize_static_witness"]
    _require(
        [_point(r) for r in resize] == witness["points"]
        and len(resize) == 46
        and sum(r.size for r in resize) == 101,
        "resize static witness differs",
    )
    incoming = next(r for r in resize if r.address - BASE == 0x2EB6C3)
    _require(
        incoming.id == x86.X86_INS_CALL and incoming.operands[0].imm == BASE + START,
        "deallocation incoming edge differs",
    )
    stride_push = next(r for r in resize if r.address - BASE == 0x2EB6BC)
    _require(
        stride_push.id == x86.X86_INS_PUSH
        and len(stride_push.operands) == 1
        and stride_push.operands[0].type == x86.X86_OP_IMM
        and stride_push.operands[0].imm == 8,
        "resize stride argument differs",
    )
    inputs = case_inputs()
    cases = [
        model_case(*values, a, s)
        for values in inputs
        for a in (0, 1, 7, 15)
        for s in (0, U32)
    ]
    union = sorted({p for case in cases for p in case["trace_rvas"]})
    _require(
        union == [f"0x{p:08x}" for p in ORDER if p < FREE_CALL],
        "guard coverage differs",
    )
    controls = []
    for name, pc, replacement, args in (
        (
            "wrong_alignment_mask",
            0x7825,
            ("test", R("al"), I(15)),
            (0x10000030, 512, 8, 0x10000010),
        ),
        (
            "wrong_metadata_address",
            0x782D,
            ("mov", R("ecx"), M("eax", -8)),
            (0x10000020, 512, 8, 0x10000000),
        ),
        (
            "wrong_minimum_slack",
            0x783A,
            ("cmp", R("eax"), I(3)),
            (0x10000020, 512, 8, 0x1000001D),
        ),
        (
            "wrong_maximum_slack",
            0x7843,
            ("cmp", R("eax"), I(36)),
            (0x10000040, 512, 8, 0x1000001C),
        ),
        (
            "wrong_small_pointer",
            0x784D,
            ("mov", R("ecx"), M("ebp", 12)),
            (0x10000020, 1, 8, None),
        ),
    ):
        changed = dict(OPS)
        changed[pc] = replacement
        try:
            model_case(*args, ops=changed)
        except DeallocationError:
            controls.append(
                {"name": name, "kind": "semantic_mutation", "rejected": True}
            )
        else:
            raise DeallocationError("semantic mutation accepted: " + name)
    inverse = [
        inverse_storage_spec(base + offset, payload)
        for base in (0, 0x10000000, 0x7FFFFFC0)
        for offset in range(32)
        for payload in (4096, 8192, 32768)
    ]
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "body": {
            "entry_rva": f"0x{START:08x}",
            "exclusive_end_rva": f"0x{END:08x}",
            "bytes": 91,
            "nodes": 29,
            "sha256": hashlib.sha256(
                b"".join(bytes(r.bytes) for r in rows)
            ).hexdigest(),
            "points": [_point(r) for r in rows],
        },
        "incoming_edge": {
            "instruction": _point(incoming),
            "target_entry_rva": f"0x{START:08x}",
            "caller_element_stride": 8,
        },
        "frontiers": {
            "division": f"0x{DIVISION:08x}",
            "free_call": f"0x{FREE_CALL:08x}",
            "guard_failure_target": f"0x{FAILURE:08x}",
        },
        "matrix": {
            "input_tuples": len(inputs),
            "inputs_sha256": _canonical_sha256([list(v) for v in inputs]),
            "entry_stack_base": 0x30001000,
            "frame_alignments": [0, 1, 7, 15],
            "seeds": [0, U32],
        },
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
            "inverse_cases_sha256": _canonical_sha256(inverse),
        },
        "summary": {
            "cases": len(cases),
            "static_bytes": 91,
            "static_nodes": 29,
            "modeled_nodes": len(union),
            "inverse_cases": len(inverse),
            "division_frontiers": sum(
                c["specification"]["outcome"] == "division_frontier" for c in cases
            ),
            "free_frontiers": sum(
                c["specification"]["outcome"] == "free_frontier" for c in cases
            ),
            "guard_failures": sum(
                c["specification"]["outcome"] == "guard_failure" for c in cases
            ),
            "actual_native_executions": 0,
            "actual_free_calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "exact_integer_graph_with_independent_division_product_metadata_guards_and_alignment_inverse",
            "premises": [
                "Stable mapped caller arguments and protected stack at the finite nonwrapping base and alignments",
                "Only large aligned pointers require a mapped preceding word, byte-disjoint from all protected frame words",
                "Inputs are strict unsigned words; synthetic machine states need not describe allocated storage",
            ],
            "relation": "Nonzero stride bounds count by unsigned maximum divided by stride; small products pass the original pointer, large products require alignment and a preceding raw word strictly below the pointer with distance four through thirty-five",
            "division_policy": "Zero stride stops before DIV and before reading its operand; no divide fault executes. Nonzero quotient always fits because EDX is zero. DIV and IMUL undefined flags are overwritten before any observed branch",
            "flags_policy": "The alignment TEST reads AL and uses eight-bit flag semantics; final guard flags and all general registers are checked",
            "inverse_relation": "Given the separate positive nonwrapping large allocation layout premise, its aligned payload pointer and stored raw pointer pass the stride-eight guard and recover that raw pointer",
            "not_claimed": [
                "Free-callee execution or return tail, failure-target behavior or actual division exceptions",
                "Ownership, allocation provenance, lifetime or validity inferred from pointer arithmetic and metadata",
                "API or game execution, full resize equivalence or accounting promotion",
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
            "sealed deallocation receipt differs",
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
            "exact deallocation receipt differs",
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
