"""Conditional failure-frontier feature dispatch with exclusive unexecuted stops."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import capstone.x86_const as x86
from src.observatory import native_assertion_helper_owner_composition as owner
from src.observatory.native_assertion_helper_descendant_pair import _import_binding
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
ANALYSIS_KIND = "pe_native_assertion_helper_failure_dispatch"
SEALED_SHA256 = "9cddbfb1e39e64523390c31bac7bdaa12b6906593495235527d406db465e4e13"
START, INTERRUPT, FALLBACK, THUNK, SLOT = (
    0x357B6A,
    0x357B81,
    0x357B83,
    0x39CB92,
    0x3D6010,
)
SOURCE_PINS = {
    "owner": (owner.ANALYSIS_KIND, owner.SEALED_SHA256),
    "frontier": owner.SOURCE_PINS["failure_frontier"],
    "pair": owner.SOURCE_PINS["pair"],
    "program_facts": owner.SOURCE_PINS["program_facts"],
}
MATRIX = {
    "inherited_frame_alignments": list(range(16)),
    "query_returns": [0, 1, 0xFFFFFFFF],
    "volatile_outputs": [
        {"ecx": 0x11223344, "edx": 0x55667788},
        {"ecx": 0xFFEEDDCC, "edx": 0xBBAA9988},
    ],
}
# Internal independent operation grammar; only normalized point and edge facts
# are emitted, never instruction bytes or textual disassembly.
OPS = {
    START: ("push", ("reg", "ebp")),
    0x357B6B: ("mov", ("reg", "ebp"), ("reg", "esp")),
    0x357B6D: ("sub", ("reg", "esp"), ("imm", 804)),
    0x357B73: ("push", ("imm", 23)),
    0x357B75: ("call", ("imm", BASE + THUNK)),
    0x357B7A: ("test", ("reg", "eax"), ("reg", "eax")),
    0x357B7C: ("je", ("imm", BASE + FALLBACK)),
    0x357B7E: ("push", ("imm", 2)),
    0x357B80: ("pop", ("reg", "ecx")),
    THUNK: ("jmp", ("mem", BASE + SLOT)),
}
SIZES = {
    START: 1,
    0x357B6B: 2,
    0x357B6D: 6,
    0x357B73: 2,
    0x357B75: 5,
    0x357B7A: 2,
    0x357B7C: 2,
    0x357B7E: 2,
    0x357B80: 1,
    THUNK: 6,
}


class DispatchError(RuntimeError):
    """An exact dispatch witness, abstract query return, or stop boundary differs."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise DispatchError(message)


def _normalize(fn: Any) -> Any:
    try:
        return fn()
    except DispatchError:
        raise
    except Exception as exc:
        raise DispatchError(str(exc)) from exc


def frame_spec() -> dict[str, Any]:
    return {
        "inherited_frame": "F from prior owner",
        "new_frame": "G equals F minus 816",
        "entry_esp_F_offset": -812,
        "new_frame_F_offset": -816,
        "entry_esp_G_offset": 4,
        "reserved_locals_G_interval": [-804, 0],
        "reserved_local_bytes": 804,
        "query_argument_G_offset": -808,
        "query_argument": 23,
        "query_callee_entry_esp_G_offset": -812,
        "query_return_esp_G_offset": -804,
        "query_return_esp_F_offset": -1620,
        "lowest_explicit_stack_G_offset": -812,
        "saved_old_ebp_G_offset": 0,
        "saved_old_ebp_value": "F",
        "inherited_return_G_offset": 4,
        "inherited_return_value": "prior caller continuation word",
        "nonzero_push_pop_scratch_G_offset": -808,
    }


def query_summary_spec() -> dict[str, Any]:
    return {
        "import_name": "IsProcessorFeaturePresent",
        "iat_slot_rva": "0x003d6010",
        "thunk_entry_rva": "0x0039cb92",
        "thunk_stack_effect": "tail jump adds no return word",
        "argument_value": 23,
        "argument_bytes": 4,
        "normal_return_assumed": True,
        "callee_argument_cleanup_bytes": 4,
        "return_to_call_continuation_rva": "0x00357b7a",
        "callee_entry_to_return_esp_increment": 8,
        "preserved_registers": ["ebx", "esi", "edi", "ebp"],
        "unknown_outputs": ["eax", "ecx", "edx", "eflags"],
        "protected_memory_G_intervals": [[0, 4], [4, 8]],
        "other_memory": "Unspecified; no preservation of new locals, outgoing scratch, inherited records or global memory",
    }


def dispatch_spec(query_return: int) -> dict[str, Any]:
    """Independent branch interface over all u32 query return values."""
    _require(
        type(query_return) is int and 0 <= query_return <= 0xFFFFFFFF,
        "query result requires u32",
    )
    nonzero = query_return != 0
    return {
        "boundary": "before_interrupt" if nonzero else "before_fallback",
        "exclusive_stop_rva": f"0x{INTERRUPT if nonzero else FALLBACK:08x}",
        "eax": query_return,
        "ecx_value": 2 if nonzero else None,
        "ecx_source": (
            "constant two from push and pop" if nonzero else "opaque query clobber"
        ),
        "esp_G_offset": -804,
        "ebp_source": "new frame G",
        "query_argument": 23,
        "zero_flag": not nonzero,
        "interrupt_vector_if_reached": 41 if nonzero else None,
        "interrupt_executed": False,
        "fallback_instruction_executed": False,
    }


def branch_partition_spec() -> list[dict[str, Any]]:
    result = []
    for zero in (False, True):
        outcome = dispatch_spec(0 if zero else 1)
        del outcome["eax"]
        outcome["eax_source"] = "query return"
        result.append({"query_return_zero": zero, "outcome": outcome})
    return result


def cases() -> list[tuple[int, int, int]]:
    return [
        (a, q, v)
        for a in MATRIX["inherited_frame_alignments"]
        for q in MATRIX["query_returns"]
        for v in range(2)
    ]


def model_case(
    vector: tuple[int, int, int], actions: Mapping[int, tuple] | None = None
) -> dict[str, Any]:
    _require(
        type(vector) in (tuple, list) and len(vector) == 3, "invalid dispatch vector"
    )
    a, q, v = vector
    _require(
        type(a) is int and 0 <= a < 16 and type(v) is int and v in (0, 1),
        "invalid dispatch vector",
    )
    expected = dispatch_spec(q)
    if actions is None:
        actions = OPS
    _require(actions == OPS, "dispatch operations differ")
    f = 0x02002000 + a
    g = f - 816
    inherited_return = BASE + 0x379E5F
    regs = {
        "esp": f - 812,
        "ebp": f,
        "eax": 0x13579BDF,
        "ecx": 0x2468ACE0,
        "edx": 0x12345678,
        "ebx": 0x13579BDF,
        "esi": 0x2468ACE0,
        "edi": 0x3456789A,
    }
    memory = {g + 4: inherited_return}
    zf = None
    trace = []
    query_frame = None
    pc = START

    def read(operand: tuple) -> int:
        if operand[0] == "reg":
            return regs[operand[1]]
        return operand[1]

    for _ in range(40):
        if pc in (INTERRUPT, FALLBACK):
            break
        _require(pc in actions, "model escaped dispatch prefix")
        trace.append(pc)
        op, *args = actions[pc]
        next_pc = pc + SIZES[pc]
        if op == "push":
            value = read(args[0])
            regs["esp"] -= 4
            memory[regs["esp"]] = value
        elif op == "pop":
            value = memory[regs["esp"]]
            regs["esp"] += 4
            regs[args[0][1]] = value
        elif op == "mov":
            regs[args[0][1]] = read(args[1])
        elif op == "sub":
            regs[args[0][1]] -= read(args[1])
        elif op == "call":
            regs["esp"] -= 4
            memory[regs["esp"]] = BASE + next_pc
            next_pc = read(args[0]) - BASE
        elif op == "jmp":
            _require(
                pc == THUNK and args[0] == ("mem", BASE + SLOT), "query thunk differs"
            )
            sp = regs["esp"]
            _require(
                sp == g - 812
                and memory[sp] == BASE + 0x357B7A
                and memory[sp + 4] == 23,
                "query entry frame differs",
            )
            query_frame = {
                "entry_esp_G_offset": sp - g,
                "return_rva": "0x00357b7a",
                "argument": memory[sp + 4],
            }
            # The abstract imported implementation is never executed. Its only
            # retained memory facts are the two explicitly protected words.
            memory = {g: memory[g], g + 4: memory[g + 4]}
            regs.update(
                eax=q,
                ecx=MATRIX["volatile_outputs"][v]["ecx"],
                edx=MATRIX["volatile_outputs"][v]["edx"],
                esp=sp + 8,
            )
            zf = None
            next_pc = 0x357B7A
        elif op == "test":
            zf = (read(args[0]) & read(args[1])) == 0
        elif op == "je":
            _require(type(zf) is bool, "query branch flags unspecified")
            if zf:
                next_pc = read(args[0]) - BASE
        else:
            raise DispatchError("unsupported dispatch operation")
        pc = next_pc
    else:
        raise DispatchError("dispatch model did not stop")
    _require(
        memory[g] == f and memory[g + 4] == inherited_return,
        "protected inherited frame words differ",
    )
    _require(
        regs["ebp"] == g
        and regs["esp"] == g - 804
        and regs["ebx"] == 0x13579BDF
        and regs["esi"] == 0x2468ACE0
        and regs["edi"] == 0x3456789A,
        "dispatch frame or nonvolatile registers differ",
    )
    _require(
        regs["ecx"] == (2 if q else MATRIX["volatile_outputs"][v]["ecx"]),
        "dispatch ECX differs",
    )
    actual = {
        "boundary": "before_interrupt" if pc == INTERRUPT else "before_fallback",
        "exclusive_stop_rva": f"0x{pc:08x}",
        "eax": regs["eax"],
        "ecx_value": regs["ecx"] if q else None,
        "ecx_source": "constant two from push and pop" if q else "opaque query clobber",
        "esp_G_offset": regs["esp"] - g,
        "ebp_source": "new frame G",
        "query_argument": query_frame["argument"],
        "zero_flag": zf,
        "interrupt_vector_if_reached": 41 if pc == INTERRUPT else None,
        "interrupt_executed": False,
        "fallback_instruction_executed": False,
    }
    _require(
        actual == expected,
        "dispatch model differs from independent branch specification",
    )
    _require(
        INTERRUPT not in trace and FALLBACK not in trace,
        "exclusive stop instruction was modeled",
    )
    return {
        "vector": list(vector),
        "outcome": actual,
        "query_frame": query_frame,
        "trace_rvas": [f"0x{p:08x}" for p in trace],
        "protected_words": [
            {"G_offset": 0, "value": memory[g]},
            {"G_offset": 4, "value": memory[g + 4]},
        ],
        "post_query_scratch_value": memory.get(g - 808),
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
            for k in sources
            if k != "program_facts"
        ),
        "source build differs",
    )
    _require(
        sources["owner"]["open_failure_frontier"]["entry_rva"] == f"0x{START:08x}"
        and sources["owner"]["open_failure_frontier"]["source_canonical_sha256"]
        == SOURCE_PINS["frontier"][1],
        "owner mismatch frontier join differs",
    )
    return ids


def _grammar(rows: Mapping[int, Any], interrupt: Any) -> dict[int, tuple]:
    ids = {
        getattr(x86, "X86_INS_" + n.upper()): n
        for n in ("push", "mov", "sub", "call", "test", "je", "pop", "jmp")
    }
    actions = {}
    for pc, row in rows.items():
        _require(
            row.id in ids and row.size == SIZES.get(pc), "dispatch instruction differs"
        )
        operands = []
        for op in row.operands:
            _require(op.size == 4, "dispatch operand width differs")
            if op.type == x86.X86_OP_REG:
                operands.append(("reg", row.reg_name(op.reg)))
            elif op.type == x86.X86_OP_IMM:
                operands.append(("imm", op.imm))
            else:
                _require(
                    op.type == x86.X86_OP_MEM
                    and op.mem.base == op.mem.index == op.mem.segment == 0,
                    "query import operand differs",
                )
                operands.append(("mem", op.mem.disp))
        actions[pc] = (ids[row.id], *operands)
    _require(actions == OPS, "exact dispatch grammar differs")
    _require(
        interrupt.address - BASE == INTERRUPT
        and interrupt.id == x86.X86_INS_INT
        and len(interrupt.operands) == 1
        and interrupt.operands[0].type == x86.X86_OP_IMM
        and interrupt.operands[0].imm == 41,
        "unexecuted interrupt witness differs",
    )
    return actions


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    frontier = _decode_body(data, image, sources["program_facts"], START)
    thunk = _decode_body(data, image, sources["program_facts"], THUNK)
    _require(
        [_point(r) for r in frontier]
        == [
            {k: p[k] for k in ("rva", "size", "sha256")}
            for p in sources["frontier"]["function_body"]["reviewed_points"]
        ],
        "complete frontier witnesses differ",
    )
    _require(
        [_point(r) for r in thunk] == sources["pair"]["bodies"][1]["points"],
        "thunk witnesses differ",
    )
    static_prefix = [r for r in frontier if START <= r.address - BASE < FALLBACK]
    interrupt = next(r for r in frontier if r.address - BASE == INTERRUPT)
    fallback = next(r for r in frontier if r.address - BASE == FALLBACK)
    rows = {
        r.address - BASE: r
        for r in static_prefix + thunk
        if r.address - BASE != INTERRUPT
    }
    actions = _grammar(rows, interrupt)
    import_control = sources["pair"]["bodies"][1]["native_controls"]["import_controls"][
        0
    ]
    _require(
        import_control["binding"] == _import_binding(image, SLOT)
        and import_control["instruction"] == _point(thunk[0]),
        "exact query import binding differs",
    )
    edge = sources["frontier"]["native_calls"]["outgoing_direct"][0]
    _require(
        edge["instruction"] == _point(rows[0x357B75])
        and edge["target_entry_rva"] == f"0x{THUNK:08x}",
        "query direct edge differs",
    )
    results = hashlib.sha256()
    visited = set()
    counts = {"before_interrupt": 0, "before_fallback": 0}
    for vector in cases():
        result = model_case(vector, actions)
        results.update(_canonical_bytes(result))
        visited.update(result["trace_rvas"])
        counts[result["outcome"]["boundary"]] += 1
    _require(
        visited == {f"0x{p:08x}" for p in rows},
        "modeled dispatch node coverage differs",
    )
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed during dispatch analysis",
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "static_prefix": {
            "start_rva": f"0x{START:08x}",
            "exclusive_end_rva": f"0x{FALLBACK:08x}",
            "bytes": 25,
            "instruction_points": [_point(r) for r in static_prefix],
            "sha256": hashlib.sha256(
                b"".join(bytes(r.bytes) for r in static_prefix)
            ).hexdigest(),
            "contains_unexecuted_interrupt_witness": True,
        },
        "exclusive_stops": {
            "nonzero_query": _point(interrupt),
            "zero_query": _point(fallback),
        },
        "query_thunk": {
            "entry_rva": f"0x{THUNK:08x}",
            "points": [_point(r) for r in thunk],
            "stack_effect": "Indirect tail jump with no additional return address",
        },
        "query_call_join": {
            "source_path": ["native_calls", "outgoing_direct", 0],
            "instruction": edge["instruction"],
            "target_entry_rva": edge["target_entry_rva"],
        },
        "query_import_join": import_control,
        "frame": frame_spec(),
        "assumed_query_summary": query_summary_spec(),
        "branch_partitions": branch_partition_spec(),
        "matrix": MATRIX,
        "vector_sha256": _canonical_sha256([list(v) for v in cases()]),
        "results_sha256": results.hexdigest(),
        "modeled_visited_rvas": sorted(visited),
        "summary": {
            "static_prefix_bytes": 25,
            "static_prefix_nodes": 10,
            "modeled_prefix_nodes": 9,
            "modeled_thunk_nodes": 1,
            "model_cases": len(cases()),
            **counts,
            "interrupt_executions": 0,
            "fallback_instruction_executions": 0,
            "actual_import_executions": 0,
        },
        "scope": {
            "evidence_class": "exact_dispatch_grammar_and_conditional_finite_integer_model",
            "premises": [
                "Entry arrives from the previously modeled mismatch transfer with inherited frame and continuation word",
                "Query returns normally under the declared x86 stdcall summary and protects the two frame-header words",
                "Nonwrapping mapped ordinary 32-bit integer and stack semantics; other query memory effects are unspecified",
            ],
            "not_claimed": [
                "Actual query import execution, feature availability or imported side effects",
                "Interrupt execution, termination, exception dispatch or hardware behavior",
                "Fallback instruction execution or later global record writes and reporting behavior",
                "Unchanged local buffers or globals, full failure-function semantics or accounting promotion",
            ],
            "source_validation": "Canonical owner and static frontier receipts plus freshly decoded complete frontier and thunk and raw query import binding witnesses; earlier matrices are not rerun",
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
            "sealed dispatch receipt differs",
        )
        _require(
            evidence["source_receipts"] == ids
            and evidence["frame"] == frame_spec()
            and evidence["assumed_query_summary"] == query_summary_spec()
            and evidence["branch_partitions"] == branch_partition_spec()
            and evidence["matrix"] == MATRIX
            and evidence["vector_sha256"]
            == _canonical_sha256([list(v) for v in cases()]),
            "dispatch specification or source differs",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_dispatch(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_dispatch(
    executable: Path, evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        validate_structure(evidence, sources)
        actual = build_dispatch(executable, sources)
        _require(
            _canonical_bytes(evidence) == _canonical_bytes(actual),
            "exact dispatch analysis differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(actual["summary"]),
        }

    return _normalize(run)


def encode_dispatch(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
