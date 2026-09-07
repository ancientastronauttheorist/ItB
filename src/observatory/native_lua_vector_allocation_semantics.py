"""Exact allocation-request arithmetic, with opaque allocator and failure calls."""

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
from src.observatory.native_lua_vector_growth_semantics import (
    SOURCE_PINS as GROWTH_SOURCE_PINS,
    ANALYSIS_KIND as GROWTH_KIND,
    SEALED_SHA256 as GROWTH_SEAL,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_vector_allocation_semantics"
SEALED_SHA256 = "9081f912a66487224a7924c126fad24a38d8cbdb4f37cb69e3e45902074f805c"
SOURCE_PINS = {k: GROWTH_SOURCE_PINS[k] for k in ("chain", "program_facts")}
SOURCE_PINS["growth_semantics"] = (GROWTH_KIND, GROWTH_SEAL)
START, END = 0x8A920, 0x8A97B
LARGE_CALL, SMALL_CALL, SIZE_FAILURE, PADDING_FAILURE = (
    0x8A94B,
    0x8A963,
    0x8A971,
    0x8A976,
)
STOPS = (LARGE_CALL, SMALL_CALL, SIZE_FAILURE, PADDING_FAILURE)
U32, MAX_ELEMENTS = 0xFFFFFFFF, 0x1FFFFFFF


def R(name):
    return ("reg", name)


def I(value):
    return ("imm", value)


def M(base, offset=0):
    return ("mem", base, offset)


OPS = {
    0x8A920: ("push", R("ebp")),
    0x8A921: ("mov", R("ebp"), R("esp")),
    0x8A923: ("mov", R("eax"), M("ebp", 8)),
    0x8A926: ("test", R("eax"), R("eax")),
    0x8A928: ("jne", I(BASE + 0x8A932)),
    0x8A92A: ("xor", R("ecx"), R("ecx")),
    0x8A92C: ("mov", R("eax"), R("ecx")),
    0x8A92E: ("pop", R("ebp")),
    0x8A92F: ("ret", I(4)),
    0x8A932: ("cmp", R("eax"), I(MAX_ELEMENTS)),
    0x8A937: ("ja", I(BASE + SIZE_FAILURE)),
    0x8A939: ("shl", R("eax"), I(3)),
    0x8A93C: ("cmp", R("eax"), I(0x1000)),
    0x8A941: ("jb", I(BASE + 0x8A962)),
    0x8A943: ("lea", R("ecx"), M("eax", 35)),
    0x8A946: ("cmp", R("ecx"), R("eax")),
    0x8A948: ("jbe", I(BASE + PADDING_FAILURE)),
    0x8A94A: ("push", R("ecx")),
    LARGE_CALL: ("call", I(BASE + 0x3574DB)),
    0x8A950: ("add", R("esp"), I(4)),
    0x8A953: ("lea", R("ecx"), M("eax", 35)),
    0x8A956: ("and", R("ecx"), I(0xFFFFFFE0)),
    0x8A959: ("mov", M("ecx", -4), R("eax")),
    0x8A95C: ("mov", R("eax"), R("ecx")),
    0x8A95E: ("pop", R("ebp")),
    0x8A95F: ("ret", I(4)),
    0x8A962: ("push", R("eax")),
    SMALL_CALL: ("call", I(BASE + 0x3574DB)),
    0x8A968: ("add", R("esp"), I(4)),
    0x8A96B: ("mov", R("ecx"), R("eax")),
    0x8A96D: ("pop", R("ebp")),
    0x8A96E: ("ret", I(4)),
    SIZE_FAILURE: ("call", I(BASE + 0x3435BC)),
    PADDING_FAILURE: ("call", I(BASE + 0x3435BC)),
}
ORDER = list(OPS)
SIZES = {
    p: (ORDER[i + 1] if i + 1 < len(ORDER) else END) - p for i, p in enumerate(ORDER)
}
MODELED_ORDER = [p for p in ORDER if p < LARGE_CALL or p == 0x8A962]


class AllocationError(RuntimeError):
    """A pinned allocation-request witness or bounded relation differs."""


def _require(ok, message):
    if not ok:
        raise AllocationError(message)


def _normalize(fn):
    try:
        return fn()
    except AllocationError:
        raise
    except Exception as exc:
        raise AllocationError(str(exc)) from exc


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)
    return value


def allocation_spec(n: int) -> dict[str, Any]:
    """Independent interval partition; no callee execution or nonreturn premise."""
    _u32(n, "element count")
    if n == 0:
        return {
            "outcome": "zero_return",
            "requested": None,
            "byte_count": None,
            "padded_count": None,
            "stop_rva": None,
        }
    if n > MAX_ELEMENTS:
        return {
            "outcome": "size_failure",
            "requested": None,
            "byte_count": None,
            "padded_count": None,
            "stop_rva": SIZE_FAILURE,
        }
    byte_count = n * 8
    if n <= 511:
        return {
            "outcome": "small_request",
            "requested": byte_count,
            "byte_count": byte_count,
            "padded_count": None,
            "stop_rva": SMALL_CALL,
        }
    padded = (n * 8 + 35) % 2**32
    if n >= 0x1FFFFFFC:
        return {
            "outcome": "padding_failure",
            "requested": None,
            "byte_count": byte_count,
            "padded_count": padded,
            "stop_rva": PADDING_FAILURE,
        }
    return {
        "outcome": "large_request",
        "requested": n * 8 + 35,
        "byte_count": byte_count,
        "padded_count": padded,
        "stop_rva": LARGE_CALL,
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


def _logical_flags(value):
    return {
        "cf": 0,
        "zf": int(value == 0),
        "sf": value >> 31,
        "of": 0,
        "af": None,
        "pf": int((value & 255).bit_count() % 2 == 0),
    }


def case_fixture(n, frame_alignment=0, seed=1):
    allocation_spec(n)
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
    return_address = (0x44556677 + seed) & U32
    return {
        "registers": regs,
        "stack": stack,
        "return_address": return_address,
        "memory": {
            stack - 8: (0xBABE0000 + seed) & U32,
            stack - 4: (0xBABE0004 + seed) & U32,
            stack: return_address,
            stack + 4: n,
            stack + 8: (0xBABE0008 + seed) & U32,
        },
    }


def model_case(n, frame_alignment=0, seed=1, ops=None):
    spec = allocation_spec(n)
    fixture = case_fixture(n, frame_alignment, seed)
    initial = fixture["registers"]
    regs, memory = dict(initial), dict(fixture["memory"])
    operations = OPS if ops is None else ops
    events, trace = [], []
    flags, returned, return_address = None, False, None

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

    pc = START
    while pc not in STOPS and not returned:
        _require(
            pc in operations and len(trace) < 50, "invalid allocation decision path"
        )
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
        elif op == "pop":
            regs[args[0][1]] = access(regs["esp"])
            regs["esp"] = (regs["esp"] + 4) & U32
        elif op == "ret":
            return_address = access(regs["esp"])
            regs["esp"] = (regs["esp"] + 4 + read(args[0])) & U32
            returned = True
        elif op == "mov":
            regs[args[0][1]] = read(args[1])
        elif op == "lea":
            regs[args[0][1]] = (regs[args[1][1]] + args[1][2]) & U32
        elif op == "cmp":
            flags = _cmp_flags(read(args[0]), read(args[1]))
        elif op in ("test", "xor"):
            value = (
                read(args[0]) & read(args[1])
                if op == "test"
                else read(args[0]) ^ read(args[1])
            )
            if op == "xor":
                regs[args[0][1]] = value
            flags = _logical_flags(value)
        elif op == "shl":
            regs[args[0][1]] = (read(args[0]) << read(args[1])) & U32
            flags = None  # The next CMP overwrites every observed arithmetic flag.
        elif op in ("jne", "ja", "jb", "jbe"):
            _require(flags is not None, "missing branch flags")
            condition = {
                "jne": not flags["zf"],
                "ja": not (flags["cf"] or flags["zf"]),
                "jb": flags["cf"],
                "jbe": flags["cf"] or flags["zf"],
            }[op]
            if condition:
                next_pc = read(args[0]) - BASE
        else:
            raise AllocationError("unsupported bounded operation")
        pc = next_pc

    stack = fixture["stack"]
    expected_regs = dict(initial, eax=n, ebp=stack - 4, esp=stack - 4)
    expected_events = [
        {"kind": "write", "address": stack - 4, "value": initial["ebp"], "width": 4},
        {"kind": "read", "address": stack + 4, "value": n, "width": 4},
    ]
    expected_returned = spec["outcome"] == "zero_return"
    if expected_returned:
        expected_regs.update(eax=0, ecx=0, ebp=initial["ebp"], esp=stack + 8)
        expected_events.extend(
            [
                {
                    "kind": "read",
                    "address": stack - 4,
                    "value": initial["ebp"],
                    "width": 4,
                },
                {
                    "kind": "read",
                    "address": stack,
                    "value": fixture["return_address"],
                    "width": 4,
                },
            ]
        )
        expected_flags = _logical_flags(0)
    elif spec["outcome"] == "size_failure":
        expected_flags = _cmp_flags(n, MAX_ELEMENTS)
    else:
        expected_regs["eax"] = spec["byte_count"]
        if spec["outcome"] == "small_request":
            expected_flags = _cmp_flags(spec["byte_count"], 4096)
        else:
            expected_regs["ecx"] = spec["padded_count"]
            expected_flags = _cmp_flags(spec["padded_count"], spec["byte_count"])
        if spec["requested"] is not None:
            expected_regs["esp"] = stack - 8
            expected_events.append(
                {
                    "kind": "write",
                    "address": stack - 8,
                    "value": spec["requested"],
                    "width": 4,
                }
            )
    expected_memory = dict(fixture["memory"])
    for event in expected_events:
        if event["kind"] == "write":
            expected_memory[event["address"]] = event["value"]
    _require(
        returned == expected_returned and (returned or pc == spec["stop_rva"]),
        "allocation boundary differs",
    )
    _require(
        return_address == (fixture["return_address"] if returned else None),
        "return target differs",
    )
    _require(
        regs == expected_regs and flags == expected_flags,
        "allocation boundary register or flag relation differs",
    )
    _require(
        memory == expected_memory and events == expected_events,
        "allocation ordered memory relation differs",
    )
    return {
        "inputs": {"n": n, "frame_alignment": frame_alignment, "seed": seed},
        "specification": spec,
        "returned": returned,
        "return_address": return_address,
        "stop_rva": None if returned else f"0x{pc:08x}",
        "registers": regs,
        "arithmetic_flags": flags,
        "events": events,
        "memory": [{"address": a, "value": v} for a, v in sorted(memory.items())],
        "trace_rvas": trace,
    }


def case_inputs():
    values = set(range(520))
    values.update(range(MAX_ELEMENTS - 16, MAX_ELEMENTS + 17))
    values.update((0x3FFFFFFF, 0x40000000, 0x7FFFFFFF, 0x80000000, U32))
    # Powers and their neighbors stress both multiplication and byte-size comparison.
    for exponent in range(32):
        for delta in (-1, 0, 1):
            value = (1 << exponent) + delta
            if 0 <= value <= U32:
                values.add(value)
    return sorted(values)


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
    _require([r.address - BASE for r in rows] == ORDER, "allocation body points differ")
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
                raise AllocationError("unexpected operand")
        pc = row.address - BASE
        widths = [4, 1] if row.mnemonic == "shl" else [4] * len(args)
        _require(
            (row.mnemonic, *args) == OPS[pc]
            and row.size == SIZES[pc]
            and [a.size for a in row.operands] == widths,
            "exact allocation grammar differs",
        )


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    rows = _decode_body(data, image, sources["program_facts"], START)
    _grammar(rows)
    growth = _decode_body(data, image, sources["program_facts"], 0x2EB620)
    _require(
        [_point(r) for r in growth] == sources["growth_semantics"]["body"]["points"],
        "growth source body differs",
    )
    growth_call = next(r for r in growth if r.address - BASE == 0x2EB669)
    _require(
        growth_call.id == x86.X86_INS_CALL
        and len(growth_call.operands) == 1
        and growth_call.operands[0].type == x86.X86_OP_IMM
        and growth_call.operands[0].imm == BASE + 0x2EB680,
        "growth child edge differs",
    )
    child = _decode_body(data, image, sources["program_facts"], 0x2EB680)
    _require(
        len(child) == 46 and sum(r.size for r in child) == 101,
        "resize body extent differs",
    )
    edges = []
    for site, target in ((0x2EB690, START), (0x2EB6A1, 0x36E580), (0x2EB6C3, 0x7800)):
        row = next(r for r in child if r.address - BASE == site)
        _require(
            row.id == x86.X86_INS_CALL
            and len(row.operands) == 1
            and row.operands[0].type == x86.X86_OP_IMM
            and row.operands[0].imm == BASE + target,
            "resize child edge differs",
        )
        edges.append(
            {"instruction": _point(row), "target_entry_rva": f"0x{target:08x}"}
        )
    _require(
        sum(r.id == x86.X86_INS_CALL for r in child) == 3,
        "resize call partition differs",
    )
    inputs = case_inputs()
    cases = [model_case(n, a, s) for n in inputs for a in range(16) for s in (0, U32)]
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(
        union == [f"0x{p:08x}" for p in MODELED_ORDER],
        "allocation decision coverage differs",
    )
    controls = []
    for name, pc, replacement, n in (
        ("wrong_zero_return_cleanup", 0x8A92F, ("ret", I(0)), 0),
        ("wrong_element_size", 0x8A939, ("shl", R("eax"), I(2)), 1),
        ("wrong_large_threshold", 0x8A93C, ("cmp", R("eax"), I(4097)), 512),
        ("wrong_padding", 0x8A943, ("lea", R("ecx"), M("eax", 34)), 512),
        (
            "wrong_size_guard",
            0x8A932,
            ("cmp", R("eax"), I(MAX_ELEMENTS + 1)),
            MAX_ELEMENTS + 1,
        ),
        ("wrong_stack_argument", 0x8A923, ("mov", R("eax"), M("ebp", 4)), 1),
    ):
        altered = dict(OPS)
        altered[pc] = replacement
        try:
            model_case(n, ops=altered)
        except AllocationError:
            controls.append(
                {"name": name, "kind": "semantic_mutation", "rejected": True}
            )
        else:
            raise AllocationError("semantic mutation accepted: " + name)
    counts = {
        outcome: sum(c["specification"]["outcome"] == outcome for c in cases)
        for outcome in (
            "zero_return",
            "small_request",
            "large_request",
            "size_failure",
            "padding_failure",
        )
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "body": {
            "entry_rva": f"0x{START:08x}",
            "exclusive_end_rva": f"0x{END:08x}",
            "bytes": 91,
            "nodes": 34,
            "sha256": hashlib.sha256(
                b"".join(bytes(r.bytes) for r in rows)
            ).hexdigest(),
            "points": [_point(r) for r in rows],
        },
        "resize_static_witness": {
            "entry_rva": "0x002eb680",
            "bytes": 101,
            "nodes": 46,
            "sha256": hashlib.sha256(
                b"".join(bytes(r.bytes) for r in child)
            ).hexdigest(),
            "points": [_point(r) for r in child],
            "native_edges": edges,
            "implementation_modeled": False,
        },
        "incoming_growth_edge": {
            "instruction": _point(growth_call),
            "target_entry_rva": "0x002eb680",
        },
        "partition": [
            {"outcome": "zero_return", "minimum": 0, "maximum": 0},
            {"outcome": "small_request", "minimum": 1, "maximum": 511},
            {"outcome": "large_request", "minimum": 512, "maximum": 0x1FFFFFFB},
            {
                "outcome": "padding_failure",
                "minimum": 0x1FFFFFFC,
                "maximum": MAX_ELEMENTS,
            },
            {"outcome": "size_failure", "minimum": MAX_ELEMENTS + 1, "maximum": U32},
        ],
        "frontiers": {
            "large_call": f"0x{LARGE_CALL:08x}",
            "small_call": f"0x{SMALL_CALL:08x}",
            "size_failure": f"0x{SIZE_FAILURE:08x}",
            "padding_failure": f"0x{PADDING_FAILURE:08x}",
            "zero_return": "Reads caller return word and advances entry ESP by eight",
        },
        "matrix": {
            "input_counts": inputs,
            "frame_alignments": list(range(16)),
            "seeds": [0, U32],
        },
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
        },
        "summary": {
            "cases": len(cases),
            "static_bytes": 91,
            "static_nodes": 34,
            "modeled_nodes": len(union),
            "outcomes": counts,
            "actual_native_executions": 0,
            "actual_allocator_calls": 0,
            "actual_failure_calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "exact_integer_graph_model_with_independent_allocation_request_interval_specification",
            "premises": [
                "Mapped stable disjoint caller return, argument and saved-register stack words",
                "No asynchronous mutation or hardware faults during the bounded decision",
            ],
            "normal_relation": "Zero count returns zero with RET4; small positive count requests eight times count; large count requests eight times count plus thirty-five; overflow branches stop before opaque failure calls",
            "state_policy": "All eight general registers, defined arithmetic flags, ordered explicit stack accesses and unchanged fixture words checked; zero-path XOR auxiliary carry is undefined and recorded as null",
            "not_claimed": [
                "Allocator behavior, allocation success, alignment or allocation pointer metadata",
                "Post-allocator return tails, failure callee nonreturn, resize copy or release semantics",
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
            "sealed allocation receipt differs",
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
            "exact allocation receipt differs",
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
