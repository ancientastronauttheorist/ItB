"""Finite heap-wrapper protocol with an exact flag reader and opaque callees."""

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
from src.observatory.native_heap_allocation_handoff import (
    SOURCE_PINS as HANDOFF_PINS,
    ANALYSIS_KIND as HANDOFF_KIND,
    SEALED_SHA256 as HANDOFF_SEAL,
    OPS as HANDOFF_OPS,
    SIZES as HANDOFF_SIZES,
    BODIES as HANDOFF_BODIES,
    START,
    WRAPPER,
    HEAP_CALL,
    ERROR_CALL,
    HEAP_WORD,
    IAT_SLOT,
    U32,
    LIMIT,
    R,
    I,
    M,
    _grammar as _handoff_grammar,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_heap_allocation_protocol"
SEALED_SHA256 = "61fbea27f458daf47e0f9aa894999af97829e8080ebbd9b1c596bcb6e8fdb68c"
SOURCE_PINS = {
    "program_facts": HANDOFF_PINS["program_facts"],
    "handoff": (HANDOFF_KIND, HANDOFF_SEAL),
}
FLAG_READER, FLAG_READER_END, RETRY_WORD = 0x38DCE2, 0x38DCE8, BASE + 0x4B7328
HANDLER_CALL, FLAG_CALL = 0x38944A, 0x389440
MAX_RESPONSES = 64
CALLS = {"heap": HEAP_CALL, "handler": HANDLER_CALL, "error": ERROR_CALL}
SITE_KINDS = {site: kind for kind, site in CALLS.items()}
OPS = {
    **HANDOFF_OPS,
    FLAG_READER: ("mov", R("eax"), M(None, RETRY_WORD)),
    FLAG_READER + 5: ("ret",),
}
ORDER = list(OPS)
SIZES = {**HANDOFF_SIZES, FLAG_READER: 5, FLAG_READER + 5: 1}
IAT_TARGET = 0x70001000


class HeapProtocolError(RuntimeError):
    """A finite opaque heap protocol or exact protected-state relation differs."""


def _require(ok, message):
    if not ok:
        raise HeapProtocolError(message)


def _normalize(fn):
    try:
        return fn()
    except HeapProtocolError:
        raise
    except Exception as exc:
        raise HeapProtocolError(str(exc)) from exc


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)
    return value


def heap_protocol_spec(size, retry_flag, responses, allow_frontier=False):
    _u32(size, "size word")
    _u32(retry_flag, "retry flag")
    _require(type(allow_frontier) is bool, "invalid frontier permission")
    _require(
        type(responses) is list and len(responses) <= MAX_RESPONSES,
        "invalid finite response transcript",
    )
    for response in responses:
        _require(
            isinstance(response, Mapping)
            and set(response) == {"kind", "eax"}
            and type(response["kind"]) is str
            and response["kind"] in CALLS,
            "invalid opaque response",
        )
        _u32(response["eax"], "opaque result")
    state = "error" if size > LIMIT else "heap"
    normalized = size if size > LIMIT else max(size, 1)
    calls = []
    flag_reads = 0
    for index in range(len(responses) + 1):
        if index == len(responses):
            _require(allow_frontier, "missing response before termination")
            return {
                "outcome": "frontier",
                "result": None,
                "error_cell": None,
                "normalized_size": normalized,
                "calls": calls,
                "flag_reads": flag_reads,
                "frontier_kind": state,
            }
        response = responses[index]
        _require(response["kind"] == state, "response kind does not match protocol")
        calls.append(dict(response))
        if state == "error" or state == "heap" and response["eax"]:
            _require(index + 1 == len(responses), "unused response records")
            return {
                "outcome": "returned",
                "result": 0 if state == "error" else response["eax"],
                "error_cell": response["eax"] if state == "error" else None,
                "normalized_size": normalized,
                "calls": calls,
                "flag_reads": flag_reads,
                "frontier_kind": None,
            }
        if state == "heap":
            flag_reads += 1
            state = "handler" if retry_flag else "error"
        else:
            state = "heap" if response["eax"] else "error"
    raise HeapProtocolError("unreachable transcript state")


def _test_flags(value):
    return {
        "cf": 0,
        "zf": int(value == 0),
        "sf": value >> 31,
        "of": 0,
        "af": None,
        "pf": int((value & 255).bit_count() % 2 == 0),
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


def summary_outputs(response, index, seed):
    word = (seed + 0x13579BDF + index * 0x1020304) & U32
    return {
        "eax": response["eax"],
        "ecx": word,
        "edx": word ^ 0xA5A55A5A,
        "arithmetic_flags": {
            name: (word >> bit) & 1
            for bit, name in enumerate(("cf", "zf", "sf", "of", "af", "pf"))
        },
    }


def case_fixture(size, heap_handle, retry_flag, responses, frame_alignment=0, seed=1):
    _u32(size, "size word")
    _u32(heap_handle, "heap word")
    _u32(retry_flag, "retry flag")
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
        for i in (-24, -20, -16, -12, -8, -4, 0, 4, 8)
    }
    memory[stack + 4] = size
    memory.update(
        {HEAP_WORD: heap_handle, RETRY_WORD: retry_flag, IAT_SLOT: IAT_TARGET}
    )
    protected = dict(memory)
    for response in responses:
        if response["kind"] == "error":
            pointer = response["eax"]
            _require(
                pointer <= U32 - 3
                and all(pointer + 4 <= a or a + 4 <= pointer for a in protected),
                "error cell overlaps protected storage or wraps",
            )
            memory[pointer] = (0xCCDD0011 + seed) & U32
    return {
        "registers": regs,
        "memory": memory,
        "stack": stack,
        "frame": stack - 4,
        "protected_addresses": sorted(protected),
        "return_address": memory[stack],
    }


def _expected_state(size, heap_handle, retry_flag, spec, fixture, seed):
    """Independent protocol-level oracle for the wrapper and exact flag-reader stack."""
    frame = fixture["frame"]
    initial = fixture["registers"]
    regs = dict(initial, ebp=frame, esi=spec["normalized_size"], esp=frame - 4)
    memory = dict(fixture["memory"])
    events = []
    if size > LIMIT:
        flags = _cmp_flags(size, LIMIT)
    elif size:
        flags = _test_flags(size)
    else:
        flags = {"cf": 0, "zf": 0, "sf": 0, "of": 0, "af": 0, "pf": 0}

    def event(kind, address, value, origin="instruction"):
        events.append(
            {
                "kind": kind,
                "address": address,
                "value": value,
                "width": 4,
                "origin": origin,
            }
        )
        if kind == "write":
            memory[address] = value

    event("write", frame, initial["ebp"])
    event("read", frame, initial["ebp"])
    event("write", frame, initial["ebp"])
    event("write", frame - 4, initial["esi"])
    event("read", frame + 8, size)
    planned = list(spec["calls"])
    if spec["frontier_kind"] is not None:
        planned.append({"kind": spec["frontier_kind"], "eax": None})
    for index, response in enumerate(planned):
        kind = response["kind"]
        if kind == "heap":
            event("write", frame - 8, spec["normalized_size"])
            event("write", frame - 12, 0)
            event("read", HEAP_WORD, heap_handle)
            event("write", frame - 16, heap_handle)
            regs["esp"] = frame - 16
        elif kind == "handler":
            event("write", frame - 8, spec["normalized_size"])
            regs["esp"] = frame - 8
        if response["eax"] is None:
            break
        if kind == "heap":
            event("read", IAT_SLOT, IAT_TARGET)
        continuation = BASE + CALLS[kind] + (6 if kind == "heap" else 5)
        return_slot = (
            frame - 20
            if kind == "heap"
            else frame - 12 if kind == "handler" else frame - 8
        )
        event("write", return_slot, continuation)
        output = summary_outputs(response, index, seed)
        regs.update({r: output[r] for r in ("eax", "ecx", "edx")})
        flags = output["arithmetic_flags"]
        event("read", return_slot, continuation, "opaque_normal_return")
        regs["esp"] = frame - 8 if kind == "handler" else frame - 4
        if kind == "handler":
            event("read", frame - 8, spec["normalized_size"])
            regs["ecx"] = spec["normalized_size"]
            regs["esp"] = frame - 4
            flags = _test_flags(response["eax"])
        elif kind == "heap":
            flags = _test_flags(response["eax"])
            if response["eax"] == 0:
                event("write", frame - 8, BASE + 0x389445)
                event("read", RETRY_WORD, retry_flag)
                event("read", frame - 8, BASE + 0x389445)
                regs["eax"] = retry_flag
                flags = _test_flags(retry_flag)
        else:
            event("write", response["eax"], 12)
            regs["eax"] = 0
            flags = _test_flags(0)
    if spec["outcome"] == "returned":
        event("read", frame - 4, initial["esi"])
        event("read", frame, initial["ebp"])
        event("read", frame + 4, fixture["return_address"])
        regs.update(esi=initial["esi"], ebp=initial["ebp"], esp=frame + 8)
    return regs, memory, flags, events


def model_case(
    size,
    heap_handle,
    retry_flag,
    responses,
    allow_frontier=False,
    frame_alignment=0,
    seed=1,
    ops=None,
):
    spec = heap_protocol_spec(size, retry_flag, responses, allow_frontier)
    fixture = case_fixture(
        size, heap_handle, retry_flag, responses, frame_alignment, seed
    )
    regs, memory = dict(fixture["registers"]), dict(fixture["memory"])
    operations = OPS if ops is None else ops
    flags = None
    pc = START
    index = 0
    returned = False
    return_address = None
    trace, events, calls = [], [], []
    flag_calls = 0

    def access(address, origin="instruction"):
        _require(address in memory, "unmapped word read")
        value = memory[address]
        events.append(
            {
                "kind": "read",
                "address": address,
                "value": value,
                "width": 4,
                "origin": origin,
            }
        )
        return value

    def read(arg):
        if arg[0] == "reg":
            return regs[arg[1]]
        if arg[0] == "imm":
            return arg[1] & U32
        return access(((regs[arg[1]] if arg[1] else 0) + arg[2]) & U32)

    def write(arg, value):
        if arg[0] == "reg":
            regs[arg[1]] = value
        else:
            address = ((regs[arg[1]] if arg[1] else 0) + arg[2]) & U32
            _require(address in memory, "unmapped word write")
            memory[address] = value
            events.append(
                {
                    "kind": "write",
                    "address": address,
                    "value": value,
                    "width": 4,
                    "origin": "instruction",
                }
            )

    def push(value):
        regs["esp"] = (regs["esp"] - 4) & U32
        write(M("esp"), value)

    while not returned:
        _require(
            pc in operations and len(trace) < 3000, "invalid finite heap protocol path"
        )
        op, *args = operations[pc]
        if op == "call" and pc in SITE_KINDS and index == len(responses):
            _require(allow_frontier, "missing opaque response")
            break
        trace.append(f"0x{pc:08x}")
        next_pc = pc + SIZES[pc]
        if op == "mov":
            write(args[0], read(args[1]))
        elif op == "push":
            push(read(args[0]))
        elif op == "pop":
            write(args[0], access(regs["esp"]))
            regs["esp"] = (regs["esp"] + 4) & U32
        elif op in ("test", "xor"):
            value = (
                read(args[0]) & read(args[1])
                if op == "test"
                else read(args[0]) ^ read(args[1])
            )
            if op == "xor":
                write(args[0], value)
            flags = _test_flags(value)
        elif op == "cmp":
            flags = _cmp_flags(read(args[0]), read(args[1]))
        elif op == "inc":
            value = read(args[0])
            output = (value + 1) & U32
            flags = {
                "cf": flags["cf"],
                "zf": int(output == 0),
                "sf": output >> 31,
                "of": int(value == 0x7FFFFFFF),
                "af": int((value & 15) == 15),
                "pf": int((output & 255).bit_count() % 2 == 0),
            }
            write(args[0], output)
        elif op in ("jmp", "ja", "je", "jne"):
            if (
                op == "jmp"
                or op == "ja"
                and not (flags["cf"] or flags["zf"])
                or op == "je"
                and flags["zf"]
                or op == "jne"
                and not flags["zf"]
            ):
                next_pc = read(args[0]) - BASE
        elif op == "call":
            target = read(args[0])
            before = dict(regs)
            push(BASE + next_pc)
            if pc == FLAG_CALL:
                _require(target == BASE + FLAG_READER, "flag reader target differs")
                next_pc = FLAG_READER
                flag_calls += 1
            else:
                kind = SITE_KINDS[pc]
                response = responses[index]
                _require(response["kind"] == kind, "opaque response kind differs")
                expected_target = (
                    IAT_TARGET
                    if kind == "heap"
                    else BASE + (0x38BBC4 if kind == "handler" else 0x385BCC)
                )
                _require(target == expected_target, "opaque target differs")
                call_esp = regs["esp"]
                before_memory = dict(memory)
                output = summary_outputs(response, index, seed)
                regs.update({r: output[r] for r in ("eax", "ecx", "edx")})
                flags = output["arithmetic_flags"]
                _require(
                    access(regs["esp"], "opaque_normal_return") == BASE + next_pc,
                    "summary return target differs",
                )
                regs["esp"] = (regs["esp"] + 4 + (12 if kind == "heap" else 0)) & U32
                _require(
                    all(regs[r] == before[r] for r in ("ebp", "ebx", "esi", "edi"))
                    and memory == before_memory,
                    "summary protected state differs",
                )
                _require(
                    regs["esp"] == before["esp"] + (12 if kind == "heap" else 0),
                    "summary stack cleanup differs",
                )
                calls.append(
                    {
                        "kind": kind,
                        "site_rva": f"0x{pc:08x}",
                        "target": target,
                        "callee_entry_esp": call_esp,
                        "callee_argument_cleanup": 12 if kind == "heap" else 0,
                        "outputs": output,
                    }
                )
                index += 1
        elif op == "ret":
            target = access(regs["esp"])
            regs["esp"] = (regs["esp"] + 4) & U32
            if pc == FLAG_READER + 5:
                next_pc = target - BASE
            else:
                return_address = target
                returned = True
        else:
            raise HeapProtocolError("unsupported protocol operation")
        pc = next_pc
    expected_regs, expected_memory, expected_flags, expected_events = _expected_state(
        size, heap_handle, retry_flag, spec, fixture, seed
    )
    _require(
        index == len(responses)
        and returned == (spec["outcome"] == "returned")
        and flag_calls == spec["flag_reads"],
        "protocol termination differs",
    )
    if not returned:
        _require(pc == CALLS[spec["frontier_kind"]], "protocol frontier differs")
    _require(
        return_address == (fixture["return_address"] if returned else None),
        "protocol caller return differs",
    )
    _require(
        regs == expected_regs and flags == expected_flags,
        "protocol register or flag relation differs",
    )
    _require(
        events == expected_events and memory == expected_memory,
        "protocol ordered memory relation differs",
    )
    return {
        "inputs": {
            "size": size,
            "heap_handle": heap_handle,
            "retry_flag": retry_flag,
            "responses": responses,
            "allow_frontier": allow_frontier,
            "frame_alignment": frame_alignment,
            "seed": seed,
        },
        "protocol": spec,
        "returned": returned,
        "return_address": return_address,
        "frontier_rva": None if returned else f"0x{pc:08x}",
        "registers": regs,
        "arithmetic_flags": flags,
        "events": events,
        "calls": calls,
        "flag_reader_calls": flag_calls,
        "trace_rvas": trace,
        "memory": [{"address": a, "value": v} for a, v in sorted(memory.items())],
    }


def case_profiles(size, retry_flag):
    def r(kind, value):
        return {"kind": kind, "eax": value}

    error = r("error", 0x10000040)
    success = r("heap", 0x80002001)
    zero = r("heap", 0)
    if size > LIMIT:
        return [([error], False), ([], True)]
    profiles = [([success], False), ([], True), ([zero], True)]
    if retry_flag:
        profiles.extend(
            [
                ([zero, r("handler", 0), error], False),
                ([zero, r("handler", 1), success], False),
                ([zero, r("handler", U32), zero, r("handler", 0), error], False),
                ([zero, r("handler", 0)], True),
                ([zero, r("handler", 1)], True),
            ]
        )
    else:
        profiles.append(([zero, error], False))
    return profiles


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
    main = [
        r
        for start in HANDOFF_BODIES
        for r in _decode_body(data, image, sources["program_facts"], start)
    ]
    _handoff_grammar(main)
    for witness in sources["handoff"]["bodies"]:
        start, end = int(witness["entry_rva"], 16), int(
            witness["exclusive_end_rva"], 16
        )
        _require(
            [_point(r) for r in main if start <= r.address - BASE < end]
            == witness["points"],
            "handoff source body differs",
        )
    reader = _decode_body(data, image, sources["program_facts"], FLAG_READER)
    _require(
        len(reader) == 2 and sum(r.size for r in reader) == 6,
        "flag reader extent differs",
    )
    a, b = reader
    _require(
        a.address == BASE + FLAG_READER
        and a.mnemonic == "mov"
        and a.size == 5
        and len(a.operands) == 2
        and a.operands[0].type == x86.X86_OP_REG
        and a.operands[0].reg == x86.X86_REG_EAX
        and a.operands[1].type == x86.X86_OP_MEM
        and not a.operands[1].mem.base
        and not a.operands[1].mem.index
        and not a.operands[1].mem.segment
        and a.operands[1].mem.disp == RETRY_WORD
        and [v.size for v in a.operands] == [4, 4]
        and b.address == BASE + FLAG_READER + 5
        and b.id == x86.X86_INS_RET
        and b.size == 1
        and not b.operands,
        "exact flag reader differs",
    )
    sizes = [0, 1, 8, 4096, LIMIT, LIMIT + 1, U32]
    flags = [0, 1, U32]
    heaps = [0, 0x81230000]
    cases = [
        model_case(size, heap, flag, responses, frontier, alignment, seed)
        for size in sizes
        for flag in flags
        for responses, frontier in case_profiles(size, flag)
        for heap in heaps
        for alignment in (0, 1, 7, 15)
        for seed in (0, U32)
    ]
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(
        union == [f"0x{p:08x}" for p in sorted(ORDER)],
        "full heap protocol coverage differs",
    )
    controls = []
    for name, pc, replacement, size, flag, profile in (
        ("wrong_error_code", 0x38946E, ("mov", M("eax"), I(11)), LIMIT + 1, 0, 0),
        (
            "wrong_flag_global",
            FLAG_READER,
            ("mov", R("eax"), M(None, HEAP_WORD)),
            8,
            0,
            3,
        ),
        ("wrong_handler_test", 0x389450, ("test", R("ecx"), R("ecx")), 8, 1, 3),
        ("wrong_saved_register", 0x389476, ("pop", R("edi")), 8, 1, 0),
        ("wrong_failure_result", 0x389474, ("mov", R("eax"), I(1)), LIMIT + 1, 0, 0),
    ):
        altered = dict(OPS)
        altered[pc] = replacement
        responses, frontier = case_profiles(size, flag)[profile]
        try:
            model_case(size, 0x81230000, flag, responses, frontier, ops=altered)
        except HeapProtocolError:
            controls.append(
                {"name": name, "kind": "semantic_mutation", "rejected": True}
            )
        else:
            raise HeapProtocolError("semantic mutation accepted: " + name)
    try:
        model_case(U32, 0, 0, [{"kind": "error", "eax": HEAP_WORD}])
    except HeapProtocolError:
        controls.append(
            {
                "name": "error_cell_global_alias",
                "kind": "domain_rejection",
                "rejected": True,
            }
        )
    else:
        raise HeapProtocolError("error-cell alias accepted")
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "bodies": [
            *sources["handoff"]["bodies"],
            {
                "entry_rva": f"0x{FLAG_READER:08x}",
                "exclusive_end_rva": f"0x{FLAG_READER_END:08x}",
                "bytes": 6,
                "nodes": 2,
                "sha256": hashlib.sha256(
                    b"".join(bytes(r.bytes) for r in reader)
                ).hexdigest(),
                "points": [_point(r) for r in reader],
            },
        ],
        "import_boundary": dict(sources["handoff"]["import_boundary"]),
        "matrix": {
            "sizes": sizes,
            "retry_flags": flags,
            "heap_words": heaps,
            "entry_stack_base": 0x30001000,
            "frame_alignments": [0, 1, 7, 15],
            "seeds": [0, U32],
            "iat_target_sample": IAT_TARGET,
            "maximum_responses": MAX_RESPONSES,
        },
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
        },
        "summary": {
            "cases": len(cases),
            "static_bytes": 95,
            "static_nodes": 39,
            "modeled_nodes": 39,
            "returned_cases": sum(c["returned"] for c in cases),
            "frontier_cases": sum(not c["returned"] for c in cases),
            "summarized_calls": sum(len(c["calls"]) for c in cases),
            "modeled_flag_reader_calls": sum(c["flag_reader_calls"] for c in cases),
            "actual_native_executions": 0,
            "actual_import_calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "conditional_exact_full_wrapper_graph_with_independent_finite_heap_protocol",
            "summary_premises": [
                "Heap-site supplied responses are opaque normal returns with twelve argument bytes popped; handler and error responses are opaque normal cdecl returns with no argument cleanup",
                "Opaque summaries preserve EBP, EBX, ESI, EDI and every modeled memory word including pushed argument words; EAX is supplied and ECX, EDX and arithmetic flags are sampled",
                "The heap global, retry-flag global, IAT target word and caller frame remain stable, mapped and disjoint at the finite nonwrapping stack base and alignments",
                "An error response supplies a mapped nonwrapping writable four-byte cell disjoint from all protected frame and global words",
            ],
            "protocol_relation": "Oversized requests reach the error helper; otherwise zero normalizes to one and the heap call is attempted first; nonzero heap results return, zero results read the exact retry-flag helper, and enabled retry invokes the handler; nonzero handler retries, otherwise the error helper result receives twelve and the wrapper returns zero",
            "flag_reader_relation": "The six-byte helper reads the stable retry word into EAX and returns without changing other registers or flags except stack and continuation effects",
            "iat_policy": "Unlike the preceding handoff slice, each modeled indirect CALL reads the supplied stable IAT target; the imported symbol identity is inherited static evidence and no API executes",
            "termination_policy": "Finite supplied transcripts may return or stop before an explicitly permitted unsupplied opaque call; missing, unused or out-of-order responses are rejected; universal termination is not claimed",
            "event_policy": "Instruction memory accesses and continuation writes are separate from opaque normal-return continuation reads; the flag-reader MOV and RET are modeled directly",
            "not_claimed": [
                "Actual HeapAlloc execution or behavior, valid heap ownership, successful allocation or real handler effects",
                "Error-helper implementation, error-cell provenance or pointer validity without the mapped-cell premise",
                "API or game execution, removal of opaque caller premises, whole owner equivalence or accounting promotion",
            ],
        },
    }
    # Preserve original handoff evidence as provenance, but describe this broader model accurately.
    result["import_boundary"]["runtime_iat_read"] = True
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
            "sealed heap protocol receipt differs",
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
            "exact heap protocol receipt differs",
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
