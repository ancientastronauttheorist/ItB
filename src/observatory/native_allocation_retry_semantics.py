"""Finite allocation-retry protocol under explicit opaque normal-return summaries."""

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
from src.observatory.native_lua_vector_allocation_semantics import (
    SOURCE_PINS as ALLOCATION_SOURCE_PINS,
    ANALYSIS_KIND as ALLOCATION_KIND,
    SEALED_SHA256 as ALLOCATION_SEAL,
    allocation_spec,
    _grammar as _allocation_grammar,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_allocation_retry_semantics"
SEALED_SHA256 = "e871c34df5d80d61c2bc8b26d24f053559b966f1d80d58e3df195cc831d2dbe2"
SOURCE_PINS = {
    "program_facts": ALLOCATION_SOURCE_PINS["program_facts"],
    "allocation_semantics": (ALLOCATION_KIND, ALLOCATION_SEAL),
}
START, END = 0x3574DB, 0x35750E
U32 = 0xFFFFFFFF
MAX_RESPONSES = 64
CALLS = {
    "candidate": (0x357502, 0x379F52),
    "handler": (0x3574E3, 0x38BBC4),
    "minus_one_failure": (0x3574F3, 0x35848F),
    "failure": (0x3574FA, 0x3435BC),
}
SITE_KINDS = {site: kind for kind, (site, target) in CALLS.items()}


def R(name):
    return ("reg", name)


def I(value):
    return ("imm", value)


def M(base, offset=0):
    return ("mem", base, offset)


OPS = {
    0x3574DB: ("push", R("ebp")),
    0x3574DC: ("mov", R("ebp"), R("esp")),
    0x3574DE: ("jmp", I(BASE + 0x3574FF)),
    0x3574E0: ("push", M("ebp", 8)),
    0x3574E3: ("call", I(BASE + 0x38BBC4)),
    0x3574E8: ("pop", R("ecx")),
    0x3574E9: ("test", R("eax"), R("eax")),
    0x3574EB: ("jne", I(BASE + 0x3574FF)),
    0x3574ED: ("cmp", M("ebp", 8), I(-1)),
    0x3574F1: ("jne", I(BASE + 0x3574FA)),
    0x3574F3: ("call", I(BASE + 0x35848F)),
    0x3574F8: ("jmp", I(BASE + 0x3574FF)),
    0x3574FA: ("call", I(BASE + 0x3435BC)),
    0x3574FF: ("push", M("ebp", 8)),
    0x357502: ("call", I(BASE + 0x379F52)),
    0x357507: ("pop", R("ecx")),
    0x357508: ("test", R("eax"), R("eax")),
    0x35750A: ("je", I(BASE + 0x3574E0)),
    0x35750C: ("pop", R("ebp")),
    0x35750D: ("ret",),
}
ORDER = list(OPS)
SIZES = {
    p: (ORDER[i + 1] if i + 1 < len(ORDER) else END) - p for i, p in enumerate(ORDER)
}


class AllocationRetryError(RuntimeError):
    """A bounded retry protocol, summary premise or exact witness differs."""


def _require(ok, message):
    if not ok:
        raise AllocationRetryError(message)


def _normalize(fn):
    try:
        return fn()
    except AllocationRetryError:
        raise
    except Exception as exc:
        raise AllocationRetryError(str(exc)) from exc


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)
    return value


def retry_spec(
    request: int, responses: list[dict[str, Any]], allow_frontier: bool = False
) -> dict[str, Any]:
    """Finite protocol, independent of native instruction and stack layout."""
    _u32(request, "request word")
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
            "invalid opaque response record",
        )
        _u32(response["eax"], "opaque result")
    state = "candidate"
    calls = []
    for index in range(len(responses) + 1):
        if index == len(responses):
            _require(allow_frontier, "missing response before termination")
            return {
                "outcome": "frontier",
                "result": None,
                "calls": calls,
                "frontier_kind": state,
            }
        response = responses[index]
        _require(response["kind"] == state, "response kind does not match protocol")
        calls.append(dict(response))
        if state == "candidate":
            if response["eax"]:
                _require(index + 1 == len(responses), "unused response records")
                return {
                    "outcome": "returned",
                    "result": response["eax"],
                    "calls": calls,
                    "frontier_kind": None,
                }
            state = "handler"
        elif state == "handler":
            state = (
                "candidate"
                if response["eax"]
                else ("minus_one_failure" if request == U32 else "failure")
            )
        else:
            state = "candidate"
    raise AllocationRetryError("unreachable transcript state")


def upstream_request_spec(n: int) -> dict[str, Any]:
    _u32(n, "element count")
    source = allocation_spec(n)
    requested = source["requested"]
    _require(requested is not None, "allocation decision does not emit a request")
    _require(0 < requested < U32, "upstream request invariant differs")
    return {
        "element_count": n,
        "request": requested,
        "request_modulo_eight": requested % 8,
        "nonzero": True,
        "not_minus_one": True,
        "minus_one_failure_excluded_under_stable_request": True,
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


def summary_outputs(response, index, seed):
    """Sample opaque volatile outputs; these are assumptions, not measured effects."""
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


def case_fixture(request, frame_alignment=0, seed=1):
    _u32(request, "request word")
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
    memory = {
        stack - 12: (0xBABE0000 + seed) & U32,
        stack - 8: (0xBABE0004 + seed) & U32,
        stack - 4: (0xBABE0008 + seed) & U32,
        stack: return_address,
        stack + 4: request,
        stack + 8: (0xBABE000C + seed) & U32,
    }
    return {
        "registers": regs,
        "memory": memory,
        "stack": stack,
        "frame": stack - 4,
        "return_address": return_address,
        "arithmetic_flags": summary_outputs({"eax": 0}, 0, seed)["arithmetic_flags"],
    }


def _expected_state(request, spec, fixture, seed):
    """Protocol-level stack oracle, not an instruction interpreter."""
    frame = fixture["frame"]
    regs = dict(fixture["registers"], ebp=frame, esp=frame)
    memory = dict(fixture["memory"])
    flags = dict(fixture["arithmetic_flags"])
    events = []

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

    event("write", frame, fixture["registers"]["ebp"])
    planned = [*spec["calls"]]
    if spec["frontier_kind"] is not None:
        planned.append({"kind": spec["frontier_kind"], "eax": None})
    for index, response in enumerate(planned):
        kind = response["kind"]
        has_argument = kind in ("candidate", "handler")
        if has_argument:
            event("read", frame + 8, request)
            event("write", frame - 4, request)
            regs["esp"] = frame - 4
        else:
            # The failed handler's zero result selects a failure via this reread.
            event("read", frame + 8, request)
            flags = _cmp_flags(request, U32)
        if response["eax"] is None:
            break
        continuation = BASE + CALLS[kind][0] + 5
        return_slot = frame - 8 if has_argument else frame - 4
        event("write", return_slot, continuation)
        output = summary_outputs(response, index, seed)
        regs.update({r: output[r] for r in ("eax", "ecx", "edx")})
        flags = output["arithmetic_flags"]
        event("read", return_slot, continuation, "opaque_normal_return")
        if has_argument:
            event("read", frame - 4, request)
            regs["ecx"] = request
            flags = _logical_flags(response["eax"])
        regs["esp"] = frame
    if spec["outcome"] == "returned":
        event("read", frame, fixture["registers"]["ebp"])
        event("read", frame + 4, fixture["return_address"])
        regs.update(ebp=fixture["registers"]["ebp"], esp=frame + 8)
    return regs, memory, flags, events


def model_case(
    request, responses, allow_frontier=False, frame_alignment=0, seed=1, ops=None
):
    spec = retry_spec(request, responses, allow_frontier)
    fixture = case_fixture(request, frame_alignment, seed)
    regs, memory = dict(fixture["registers"]), dict(fixture["memory"])
    flags = dict(fixture["arithmetic_flags"])
    operations = OPS if ops is None else ops
    events, trace, calls = [], [], []
    index = 0
    pc = START
    returned = False
    return_address = None

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
        return access((regs[arg[1]] + arg[2]) & U32)

    def push(value):
        regs["esp"] = (regs["esp"] - 4) & U32
        _require(regs["esp"] in memory, "unmapped stack write")
        memory[regs["esp"]] = value
        events.append(
            {
                "kind": "write",
                "address": regs["esp"],
                "value": value,
                "width": 4,
                "origin": "instruction",
            }
        )

    while not returned:
        _require(pc in operations and len(trace) < 2000, "invalid bounded retry path")
        op, *args = operations[pc]
        if op == "call" and index == len(responses):
            _require(allow_frontier, "missing opaque response")
            break
        trace.append(f"0x{pc:08x}")
        next_pc = pc + SIZES[pc]
        if op == "push":
            push(read(args[0]))
        elif op == "mov":
            regs[args[0][1]] = read(args[1])
        elif op == "pop":
            regs[args[0][1]] = access(regs["esp"])
            regs["esp"] = (regs["esp"] + 4) & U32
        elif op == "test":
            flags = _logical_flags(read(args[0]) & read(args[1]))
        elif op == "cmp":
            flags = _cmp_flags(read(args[0]), read(args[1]))
        elif op in ("jmp", "je", "jne"):
            if (
                op == "jmp"
                or (op == "je" and flags["zf"])
                or (op == "jne" and not flags["zf"])
            ):
                next_pc = read(args[0]) - BASE
        elif op == "call":
            kind = SITE_KINDS[pc]
            _require(read(args[0]) == BASE + CALLS[kind][1], "opaque target differs")
            response = responses[index]
            _require(response["kind"] == kind, "opaque response kind differs")
            before = dict(regs)
            push(BASE + next_pc)
            call_esp = regs["esp"]
            output = summary_outputs(response, index, seed)
            regs.update({r: output[r] for r in ("eax", "ecx", "edx")})
            flags = output["arithmetic_flags"]
            _require(
                access(regs["esp"], "opaque_normal_return") == BASE + next_pc,
                "summary continuation differs",
            )
            regs["esp"] = (regs["esp"] + 4) & U32
            _require(
                all(regs[r] == before[r] for r in ("ebp", "ebx", "esi", "edi", "esp")),
                "summary preservation differs",
            )
            frame = fixture["frame"]
            _require(
                memory[frame + 8] == request
                and memory[frame] == fixture["registers"]["ebp"]
                and memory[frame + 4] == fixture["return_address"],
                "summary protected frame differs",
            )
            calls.append(
                {
                    "kind": kind,
                    "site_rva": f"0x{pc:08x}",
                    "target_rva": f"0x{CALLS[kind][1]:08x}",
                    "request_argument": (
                        request if kind in ("candidate", "handler") else None
                    ),
                    "callee_entry_esp": call_esp,
                    "continuation": BASE + next_pc,
                    "outputs": output,
                }
            )
            index += 1
        elif op == "ret":
            return_address = access(regs["esp"])
            regs["esp"] = (regs["esp"] + 4) & U32
            returned = True
        else:
            raise AllocationRetryError("unsupported retry operation")
        pc = next_pc
    expected_regs, expected_memory, expected_flags, expected_events = _expected_state(
        request, spec, fixture, seed
    )
    _require(
        index == len(responses) and returned == (spec["outcome"] == "returned"),
        "retry termination differs",
    )
    if not returned:
        _require(pc == CALLS[spec["frontier_kind"]][0], "retry frontier differs")
    _require(
        return_address == (fixture["return_address"] if returned else None),
        "retry return target differs",
    )
    _require(
        regs == expected_regs and flags == expected_flags,
        "retry register or flag relation differs",
    )
    _require(
        memory == expected_memory and events == expected_events,
        "retry ordered memory relation differs",
    )
    return {
        "inputs": {
            "request": request,
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
        "memory": [{"address": a, "value": v} for a, v in sorted(memory.items())],
        "trace_rvas": trace,
    }


def case_profiles(request):
    failure = "minus_one_failure" if request == U32 else "failure"

    def response(kind, eax):
        return {"kind": kind, "eax": eax}

    c0 = response("candidate", 0)
    h0 = response("handler", 0)
    h1 = response("handler", 1)
    f = response(failure, 0xFFFFFFFF)
    success = response("candidate", 0x80001001)
    return [
        ([success], False),
        ([c0, h1, success], False),
        ([c0, h0, f, success], False),
        ([c0, h1, c0, h0, f, c0, h1, success], False),
        ([], True),
        ([c0], True),
        ([c0, h0], True),
        ([c0, h0, f], True),
        ([c0, h1], True),
    ]


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
    _require([r.address - BASE for r in rows] == ORDER, "retry body points differ")
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
                raise AllocationRetryError("unexpected operand")
        pc = row.address - BASE
        _require(
            (row.mnemonic, *args) == OPS[pc]
            and row.size == SIZES[pc]
            and [a.size for a in row.operands] == [4] * len(args),
            "exact retry grammar differs",
        )


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    rows = _decode_body(data, image, sources["program_facts"], START)
    _grammar(rows)
    caller = _decode_body(data, image, sources["program_facts"], 0x8A920)
    _allocation_grammar(caller)
    _require(
        [_point(r) for r in caller]
        == sources["allocation_semantics"]["body"]["points"],
        "allocation source body differs",
    )
    edges = []
    for site in (0x8A94B, 0x8A963):
        row = next(r for r in caller if r.address - BASE == site)
        _require(
            row.id == x86.X86_INS_CALL and row.operands[0].imm == BASE + START,
            "incoming retry edge differs",
        )
        edges.append({"instruction": _point(row), "target_entry_rva": f"0x{START:08x}"})
    requests = [0, 1, 8, 4088, 4131, 0xFFFFFFFB, U32]
    cases = [
        model_case(request, responses, frontier, a, s)
        for request in requests
        for responses, frontier in case_profiles(request)
        for a in (0, 1, 7, 15)
        for s in (0, U32)
    ]
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(union == [f"0x{p:08x}" for p in ORDER], "retry graph coverage differs")
    controls = []
    for name, pc, replacement, request, profile in (
        ("wrong_request_push", 0x3574FF, ("push", I(0)), 8, 0),
        ("wrong_handler_test", 0x3574E9, ("test", R("ecx"), R("ecx")), 8, 2),
        ("wrong_minus_one_guard", 0x3574ED, ("cmp", M("ebp", 8), I(0)), U32, 2),
        ("wrong_retry_branch", 0x35750A, ("jne", I(BASE + 0x3574E0)), 8, 0),
        ("wrong_cleanup_register", 0x357507, ("pop", R("edx")), 8, 0),
    ):
        altered = dict(OPS)
        altered[pc] = replacement
        responses, frontier = case_profiles(request)[profile]
        try:
            model_case(request, responses, frontier, ops=altered)
        except AllocationRetryError:
            controls.append(
                {"name": name, "kind": "semantic_mutation", "rejected": True}
            )
        else:
            raise AllocationRetryError("semantic mutation accepted: " + name)
    upstream = [
        upstream_request_spec(n) for n in (1, 2, 511, 512, 513, 0x1FFFFFFA, 0x1FFFFFFB)
    ]
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "body": {
            "entry_rva": f"0x{START:08x}",
            "exclusive_end_rva": f"0x{END:08x}",
            "bytes": 51,
            "nodes": 20,
            "sha256": hashlib.sha256(
                b"".join(bytes(r.bytes) for r in rows)
            ).hexdigest(),
            "points": [_point(r) for r in rows],
        },
        "incoming_edges": edges,
        "opaque_calls": [
            {
                "kind": kind,
                "site_rva": f"0x{site:08x}",
                "target_rva": f"0x{target:08x}",
                "request_argument": kind in ("candidate", "handler"),
            }
            for kind, (site, target) in CALLS.items()
        ],
        "matrix": {
            "requests": requests,
            "profiles_per_request": 9,
            "maximum_responses": MAX_RESPONSES,
            "entry_stack_base": 0x30001000,
            "frame_alignments": [0, 1, 7, 15],
            "seeds": [0, U32],
        },
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
            "upstream_request_examples": upstream,
        },
        "summary": {
            "cases": len(cases),
            "static_bytes": 51,
            "static_nodes": 20,
            "modeled_nodes": 20,
            "returned_cases": sum(c["returned"] for c in cases),
            "frontier_cases": sum(not c["returned"] for c in cases),
            "summarized_calls": sum(len(c["calls"]) for c in cases),
            "actual_native_executions": 0,
            "actual_callee_calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "conditional_exact_graph_model_with_independent_finite_retry_protocol",
            "summary_premises": [
                "Every supplied response is an opaque normal cdecl return with specified EAX and sampled ECX, EDX and arithmetic flags",
                "All callees preserve EBP, EBX, ESI, EDI, the caller request word, saved EBP and caller continuation",
                "Apart from the caller CALL continuation write, every opaque summary leaves every modeled memory word unchanged, including the pushed argument word later popped into ECX",
                "Mapped stable disjoint frame words at the declared finite stack base and alignments; no asynchronous mutation or faults",
                "CALL writes its continuation and the opaque normal-return summary reads that word and restores caller ESP without argument cleanup",
            ],
            "protocol_relation": "Try candidate first; zero candidate invokes handler with the same stable request; nonzero handler retries; zero handler selects one of two opaque failure calls by request equality to minus one; either failure retries if its supplied response returns normally",
            "success_relation": "A nonzero candidate response returns with EAX that response, ECX the request, EDX its last sampled output, caller EBP restored and entry ESP advanced four",
            "upstream_corollary": "Allocation-decision emitted requests are positive and below the maximum unsigned word; the minus-one failure arm is excluded only while the caller request remains stable",
            "termination_policy": "At most sixty-four supplied responses; reject missing, unused or out-of-order records unless explicit frontier mode stops before the next unsupplied call; no universal termination claim",
            "event_policy": "Instruction word accesses and CALL continuation writes are distinguished from opaque normal-return continuation reads; these reads do not execute a real callee",
            "not_claimed": [
                "Actual heap allocation, handler effects, exception behavior or failure-callee nonreturn",
                "Preservation or valid pointer lifetime absent the explicit opaque summaries",
                "API or game execution, allocation success, full resize behavior, whole owner equivalence or accounting promotion",
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
            "sealed retry receipt differs",
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
            "exact retry receipt differs",
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
