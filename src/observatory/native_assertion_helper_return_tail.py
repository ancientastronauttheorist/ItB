"""Conditional exact tail paths and the independently specified equality checker."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import capstone.x86_const as x86
from src.observatory import native_assertion_helper_import_arguments as arguments
from src.observatory import native_assertion_helper_import_handoff as handoff
from src.observatory import native_assertion_helper_leaf_callees as leaves
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
ANALYSIS_KIND = "pe_native_assertion_helper_return_tail"
SEALED_SHA256 = "fd5c3c19346955ad9a667cdf1f53757fa98f29948f6a26216f431d8e267ec703"
OWNER, START, STOP, SMALL, CHECK, ESCAPE = (
    0x379D28,
    0x379E37,
    0x379E63,
    0x3586B6,
    0x3574CA,
    0x357B6A,
)
COOKIE, CLEAR = 0x493F28, 0x4B6E58
SOURCE_PINS = {
    "pair": arguments.SOURCE_PINS["pair"],
    "program_facts": arguments.SOURCE_PINS["program_facts"],
    "arguments": (arguments.ANALYSIS_KIND, arguments.SEALED_SHA256),
    "handoff": (handoff.ANALYSIS_KIND, handoff.SEALED_SHA256),
    "leaves": (leaves.ANALYSIS_KIND, leaves.SEALED_SHA256),
    "reused_check": leaves.SOURCE_PINS["reused_callee"],
}
MATRIX = {
    "frame_alignments": list(range(16)),
    "first_returns": [0, 1, 0xFFFFFFFF],
    "third_returns": [0, 1, 0xFFFFFFFF],
    "selectors": [0, 1, 0xFFFFFFFF],
    "prefix_cookie_seeds": [0, 0x6B8B4567],
    "current_global_equals_recovered": [0, 1],
}


# Independent operation grammar. These tuples stay in code; receipts publish
# hashed instruction witnesses and normalized control-flow edges only.
def R(name: str) -> tuple:
    return ("register", name)


def I(value: int) -> tuple:
    return ("immediate", value)


def M(base: str | None, offset: int) -> tuple:
    return ("memory", base, offset)


OPS = {
    0x379E37: ("call", M(None, BASE + 0x3D6018)),
    0x379E3D: ("test", R("eax"), R("eax")),
    0x379E3F: ("jne", I(BASE + 0x379E54)),
    0x379E41: ("test", R("edi"), R("edi")),
    0x379E43: ("jne", I(BASE + 0x379E54)),
    0x379E45: ("cmp", M("ebp", 8), I(-1)),
    0x379E49: ("je", I(BASE + 0x379E54)),
    0x379E4B: ("push", M("ebp", 8)),
    0x379E4E: ("call", I(BASE + SMALL)),
    0x379E53: ("pop", R("ecx")),
    0x379E54: ("mov", R("ecx"), M("ebp", -4)),
    0x379E57: ("xor", R("ecx"), R("ebp")),
    0x379E59: ("pop", R("edi")),
    0x379E5A: ("call", I(BASE + CHECK)),
    0x379E5F: ("mov", R("esp"), R("ebp")),
    0x379E61: ("pop", R("ebp")),
    0x379E62: ("ret",),
    SMALL: ("and", M(None, BASE + CLEAR), I(0)),
    SMALL + 7: ("ret",),
    CHECK: ("cmp", R("ecx"), M(None, BASE + COOKIE)),
    0x3574D0: ("jne", I(BASE + 0x3574D5)),
    0x3574D3: ("ret",),
    0x3574D5: ("jmp", I(BASE + ESCAPE)),
}
SIZES = {
    0x379E37: 6,
    0x379E3D: 2,
    0x379E3F: 2,
    0x379E41: 2,
    0x379E43: 2,
    0x379E45: 4,
    0x379E49: 2,
    0x379E4B: 3,
    0x379E4E: 5,
    0x379E53: 1,
    0x379E54: 3,
    0x379E57: 2,
    0x379E59: 1,
    0x379E5A: 5,
    0x379E5F: 2,
    0x379E61: 1,
    0x379E62: 1,
    SMALL: 7,
    SMALL + 7: 1,
    CHECK: 6,
    0x3574D0: 3,
    0x3574D3: 2,
    0x3574D5: 6,
}


class TailError(RuntimeError):
    """A pinned tail grammar, conditional path, or equality-check join differs."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise TailError(message)


def _normalize(fn: Any) -> Any:
    try:
        return fn()
    except TailError:
        raise
    except Exception as exc:
        raise TailError(str(exc)) from exc


def tail_spec(
    first_return: int, third_return: int, selector: int, compare_equal: bool = True
) -> dict[str, Any]:
    """Independent total path predicate for u32 returns and selector values."""
    _require(
        all(
            type(v) is int and 0 <= v <= 0xFFFFFFFF
            for v in (first_return, third_return, selector)
        ),
        "tail inputs require u32",
    )
    _require(type(compare_equal) is bool, "compare equality requires bool")
    return {
        "small_helper_called": third_return == 0
        and first_return == 0
        and selector != 0xFFFFFFFF,
        "terminal": "caller_return" if compare_equal else "external_checker_transfer",
        "eax": third_return,
        "edi_source": "entry_saved_edi",
        "ecx_source": "protected_slot_xor_frame",
        "esp_frame_offset": 8 if compare_equal else -812,
        "ebp_source": "entry_saved_ebp" if compare_equal else "established_frame",
        "instruction_target": (
            "incoming_return_word" if compare_equal else f"0x{ESCAPE:08x}"
        ),
    }


def branch_partition_spec() -> list[dict[str, Any]]:
    return [
        {
            "first_is_zero": f,
            "third_is_zero": t,
            "selector_is_marker": s,
            "compare_equal": e,
            "outcome": {
                **{
                    k: v
                    for k, v in tail_spec(
                        0 if f else 1, 0 if t else 1, 0xFFFFFFFF if s else 0, e
                    ).items()
                    if k != "eax"
                },
                "eax_source": "third_return",
            },
        }
        for f in (False, True)
        for t in (False, True)
        for s in (False, True)
        for e in (False, True)
    ]


def call_summary_spec() -> dict[str, Any]:
    return {
        "import_name": "UnhandledExceptionFilter",
        "iat_slot_rva": "0x003d6018",
        "normal_return_assumed": True,
        "argument_bytes": 4,
        "callee_argument_cleanup_bytes": 4,
        "pre_call_esp_frame_offset": -816,
        "callee_entry_esp_frame_offset": -820,
        "return_esp_frame_offset": -812,
        "argument_frame_offset": -808,
        "preserved_registers": ["ebx", "esi", "edi", "ebp"],
        "unknown_outputs": ["eax", "ecx", "edx", "eflags"],
        "protected_words": [
            {"frame_offset": -812, "width": 4, "role": "entry saved EDI"},
            {"frame_offset": -4, "width": 4, "role": "protected prefix seed XOR frame"},
            {"frame_offset": 0, "width": 4, "role": "entry saved EBP"},
            {"frame_offset": 4, "width": 4, "role": "incoming return word"},
            {"frame_offset": 8, "width": 4, "role": "incoming selector word"},
        ],
        "record_memory_effects": "Unspecified throughout pair and record region from frame minus 808 through frame minus 4",
        "other_memory_effects": "Unspecified except protected words; current global compare word may differ from prefix seed",
    }


def checker_spec() -> dict[str, Any]:
    return {
        "entry_rva": f"0x{CHECK:08x}",
        "comparison_global_rva": f"0x{COOKIE:08x}",
        "input": "ECX equals protected slot XOR established frame",
        "equal_edge": "return to caller continuation at 0x00379e5f",
        "unequal_edge": f"external transfer to 0x{ESCAPE:08x}",
        "returning_path_preserved_registers": [
            "eax",
            "ebx",
            "ecx",
            "edx",
            "esi",
            "edi",
            "ebp",
        ],
        "return_stack_increment_bytes": 4,
        "writes_memory": False,
        "global_equality_is_independent_premise": True,
        "name_scope": "Address-selected four-instruction equality check; no external failure implementation semantics",
    }


def cases() -> list[tuple[int, int, int, int, int, int]]:
    return [
        (a, f, t, s, c, e)
        for a in MATRIX["frame_alignments"]
        for f in MATRIX["first_returns"]
        for t in MATRIX["third_returns"]
        for s in MATRIX["selectors"]
        for c in MATRIX["prefix_cookie_seeds"]
        for e in MATRIX["current_global_equals_recovered"]
    ]


def model_case(
    vector: tuple[int, int, int, int, int, int],
    actions: Mapping[int, tuple] | None = None,
) -> dict[str, Any]:
    """Finite integer interpreter of normalized operations and one assumed import."""
    _require(type(vector) in (list, tuple) and len(vector) == 6, "invalid tail vector")
    a, first, third, selector, seed, equal = vector
    _require(
        type(a) is int
        and 0 <= a < 16
        and type(equal) is int
        and equal in (0, 1)
        and type(seed) is int
        and 0 <= seed <= 0xFFFFFFFF,
        "invalid tail vector",
    )
    expected = tail_spec(first, third, selector, bool(equal))
    if actions is None:
        actions = OPS
    _require(actions == OPS, "normalized tail operations differ")
    frame = 0x02002000 + a
    old_edi, old_ebp, return_word = 0x3456789A, 0x456789AB, 0x30303030
    regs = {
        "eax": frame - 808,
        "ecx": 0x11111111,
        "edx": 0x22222222,
        "edi": first,
        "ebx": 0x13579BDF,
        "esi": 0x2468ACE0,
        "ebp": frame,
        "esp": frame - 816,
    }
    protected = {
        frame - 812: old_edi,
        frame - 4: seed ^ frame,
        frame: old_ebp,
        frame + 4: return_word,
        frame + 8: selector,
    }
    memory = dict(protected) | {
        frame - 816: frame - 808,
        BASE + COOKIE: seed if equal else seed ^ 1,
        BASE + CLEAR: 0xA55AA55A,
    }
    visited = []
    small = False
    zf = None
    pc = START

    def address(operand: tuple) -> int:
        return (regs[operand[1]] if operand[1] else 0) + operand[2]

    def read(operand: tuple) -> int:
        if operand[0] == "register":
            return regs[operand[1]]
        if operand[0] == "immediate":
            return operand[1] & 0xFFFFFFFF
        at = address(operand)
        _require(at in memory, "model read from unspecified memory")
        return memory[at]

    def write(operand: tuple, value: int) -> None:
        if operand[0] == "register":
            regs[operand[1]] = value & 0xFFFFFFFF
        else:
            memory[address(operand)] = value & 0xFFFFFFFF

    for _ in range(100):
        if pc == ESCAPE:
            terminal = "external_checker_transfer"
            break
        if pc == return_word - BASE:
            terminal = "caller_return"
            break
        _require(pc in actions, "model escaped reviewed nodes")
        visited.append(pc)
        op, *operands = actions[pc]
        next_pc = pc + SIZES[pc]
        if op == "call" and operands[0][0] == "memory":
            _require(
                pc == START and memory[regs["esp"]] == frame - 808,
                "third import argument differs",
            )
            # Arbitrary record and scratch mutations are represented by dropping
            # every unprotected stack word, not by pretending buffers unchanged.
            memory = {
                k: v
                for k, v in memory.items()
                if k in protected or k in (BASE + COOKIE, BASE + CLEAR)
            }
            regs.update(eax=third, ecx=0xCCCCCCCC, edx=0xDDDDDDDD, esp=regs["esp"] + 4)
            zf = None
        elif op == "call":
            regs["esp"] -= 4
            memory[regs["esp"]] = BASE + next_pc
            next_pc = read(operands[0]) - BASE
            if next_pc == SMALL:
                small = True
        elif op == "ret":
            _require(regs["esp"] in memory, "return word unspecified")
            next_pc = memory[regs["esp"]] - BASE
            regs["esp"] += 4
        elif op == "push":
            value = read(operands[0])
            regs["esp"] -= 4
            memory[regs["esp"]] = value
        elif op == "pop":
            value = memory[regs["esp"]]
            regs["esp"] += 4
            write(operands[0], value)
        elif op == "mov":
            write(operands[0], read(operands[1]))
        elif op in ("xor", "and"):
            left, right = read(operands[0]), read(operands[1])
            value = (left ^ right) if op == "xor" else (left & right)
            write(operands[0], value)
            zf = value == 0
        elif op in ("cmp", "test"):
            left, right = read(operands[0]), read(operands[1])
            zf = (left == right) if op == "cmp" else ((left & right) == 0)
        elif op in ("jne", "je"):
            _require(type(zf) is bool, "branch flags unspecified")
            if zf == (op == "je"):
                next_pc = read(operands[0]) - BASE
        elif op == "jmp":
            next_pc = read(operands[0]) - BASE
        else:
            raise TailError("unsupported tail operation")
        pc = next_pc
    else:
        raise TailError("tail model did not terminate")
    _require(
        regs["edi"] == old_edi
        and regs["ecx"] == seed
        and regs["ebx"] == 0x13579BDF
        and regs["esi"] == 0x2468ACE0,
        "restored register or recovered word differs",
    )
    _require(regs["ebp"] == (old_ebp if equal else frame), "frame restoration differs")
    outcome = {
        "small_helper_called": small,
        "terminal": terminal,
        "eax": regs["eax"],
        "edi_source": "entry_saved_edi",
        "ecx_source": "protected_slot_xor_frame",
        "esp_frame_offset": regs["esp"] - frame,
        "ebp_source": (
            "entry_saved_ebp" if regs["ebp"] == old_ebp else "established_frame"
        ),
        "instruction_target": (
            "incoming_return_word" if pc == return_word - BASE else f"0x{pc:08x}"
        ),
    }
    _require(outcome == expected, "tail outcome differs from independent predicate")
    _require(not small or memory[BASE + CLEAR] == 0, "small helper zero effect differs")
    return {
        "vector": list(vector),
        "outcome": outcome,
        "trace_rvas": [f"0x{p:08x}" for p in visited],
        "recovered_word": regs["ecx"],
        "record_contents": "unspecified after abstract import",
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
        sources["arguments"]["slice"]["exclusive_stop_rva"] == f"0x{START:08x}"
        and sources["arguments"]["symbolic_transfer"]["final_registers"]["esp"]
        == {"kind": "frame_relative", "offset": -816},
        "import argument entry differs",
    )
    _require(
        sources["reused_check"]["function_body"]["entry_rva"] == f"0x{CHECK:08x}",
        "checker source entry differs",
    )
    return ids


def _grammar(rows: Mapping[int, Any]) -> dict[int, tuple]:
    ids = {
        getattr(x86, "X86_INS_" + n.upper()): n
        for n in (
            "call",
            "test",
            "jne",
            "cmp",
            "je",
            "push",
            "pop",
            "mov",
            "xor",
            "ret",
            "and",
            "jmp",
        )
    }
    result = {}
    for pc, row in rows.items():
        _require(row.id in ids, "unsupported tail instruction")
        operands = []
        for operand in row.operands:
            _require(operand.size == 4, "tail operand width differs")
            if operand.type == x86.X86_OP_REG:
                operands.append(R(row.reg_name(operand.reg)))
            elif operand.type == x86.X86_OP_IMM:
                operands.append(I(operand.imm))
            else:
                _require(
                    operand.type == x86.X86_OP_MEM
                    and operand.mem.index == operand.mem.segment == 0,
                    "tail memory addressing differs",
                )
                operands.append(
                    M(
                        row.reg_name(operand.mem.base) if operand.mem.base else None,
                        operand.mem.disp,
                    )
                )
        result[pc] = (ids[row.id], *operands)
        _require(row.size == SIZES.get(pc), "tail instruction size differs")
    _require(result == OPS, "exact tail operation grammar differs")
    return result


def _graph(rows: Mapping[int, Any]) -> list[dict[str, Any]]:
    result = []
    for pc in sorted(rows):
        op, *operands = OPS[pc]
        next_pc = pc + SIZES[pc]
        if op in ("jne", "je"):
            edges = [
                {
                    "condition": "ZF is clear" if op == "jne" else "ZF is set",
                    "target_rva": f"0x{operands[0][1]-BASE:08x}",
                },
                {"condition": "complementary flag", "target_rva": f"0x{next_pc:08x}"},
            ]
        elif op == "jmp":
            edges = [
                {
                    "condition": "unconditional external transfer",
                    "target_rva": f"0x{ESCAPE:08x}",
                }
            ]
        elif op == "ret":
            edges = [
                {"condition": "stack return address", "target": "dynamic return word"}
            ]
        elif op == "call":
            edges = [
                {
                    "condition": (
                        "assumed import return"
                        if pc == START
                        else "exact direct callee entry"
                    ),
                    "target_rva": f"0x{next_pc if pc==START else operands[0][1]-BASE:08x}",
                }
            ]
        else:
            edges = [{"condition": "fallthrough", "target_rva": f"0x{next_pc:08x}"}]
        result.append({"instruction": _point(rows[pc]), "edges": edges})
    return result


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    decoded = {
        e: _decode_body(data, image, sources["program_facts"], e)
        for e in (OWNER, SMALL, CHECK)
    }
    _require(
        [_point(r) for r in decoded[OWNER]] == sources["pair"]["bodies"][0]["points"],
        "owner witnesses differ",
    )
    _require(
        [_point(r) for r in decoded[SMALL]] == sources["leaves"]["bodies"][0]["points"],
        "small helper witnesses differ",
    )
    check_body = sources["reused_check"]["function_body"]
    _require(
        [_point(r) for r in decoded[CHECK]]
        == [
            {k: p[k] for k in ("rva", "size", "sha256")}
            for p in check_body["reviewed_points"]
        ],
        "checker witnesses differ",
    )
    tail = [r for r in decoded[OWNER] if START <= r.address - BASE < STOP]
    rows = {
        r.address - BASE: r
        for e in decoded
        for r in (tail if e == OWNER else decoded[e])
    }
    actions = _grammar(rows)
    control = sources["pair"]["bodies"][0]["native_controls"]["import_controls"][2]
    _require(
        control["binding"] == _import_binding(image, 0x3D6018)
        and control["instruction"] == _point(rows[START]),
        "third import binding differs",
    )
    direct = sources["pair"]["bodies"][0]["native_controls"]["direct_calls"]
    joins = []
    for index, site, target in ((3, 0x379E4E, SMALL), (4, 0x379E5A, CHECK)):
        edge = direct[index]
        _require(
            edge["instruction"] == _point(rows[site])
            and edge["target_entry_rva"] == f"0x{target:08x}",
            "tail direct edge differs",
        )
        joins.append(
            {
                "source_path": ["bodies", 0, "native_controls", "direct_calls", index],
                "edge": edge,
            }
        )
    results = hashlib.sha256()
    visited = set()
    counts = {
        "caller_returns": 0,
        "external_checker_transfers": 0,
        "small_helper_calls": 0,
    }
    for vector in cases():
        result = model_case(vector, actions)
        results.update(_canonical_bytes(result))
        visited.update(result["trace_rvas"])
        counts[
            (
                "caller_returns"
                if result["outcome"]["terminal"] == "caller_return"
                else "external_checker_transfers"
            )
        ] += 1
        counts["small_helper_calls"] += int(result["outcome"]["small_helper_called"])
    _require(
        visited == {f"0x{p:08x}" for p in rows}, "finite model node coverage differs"
    )
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed during analysis",
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "tail": {
            "owner_entry_rva": f"0x{OWNER:08x}",
            "start_rva": f"0x{START:08x}",
            "exclusive_end_rva": f"0x{STOP:08x}",
            "return_instruction_rva": "0x00379e62",
            "size": STOP - START,
            "sha256": hashlib.sha256(
                b"".join(bytes(r.bytes) for r in tail)
            ).hexdigest(),
            "points": [_point(r) for r in tail],
        },
        "direct_source_joins": joins,
        "third_import_join": control,
        "checker": checker_spec(),
        "small_helper": {
            "entry_rva": f"0x{SMALL:08x}",
            "global_rva": f"0x{CLEAR:08x}",
            "write_width": 4,
            "write_value": 0,
            "selector_argument_read": False,
            "effect_scope": "Exact AND and return under the same ordinary instruction premises",
        },
        "assumed_import_summary": call_summary_spec(),
        "control_flow": _graph(rows),
        "predicate_partitions": branch_partition_spec(),
        "matrix": MATRIX,
        "vector_sha256": _canonical_sha256([list(v) for v in cases()]),
        "results_sha256": results.hexdigest(),
        "visited_rvas": sorted(visited),
        "summary": {
            "tail_instructions": len(tail),
            "tail_bytes": 44,
            "small_helper_instructions": 2,
            "checker_instructions": 4,
            "boolean_partitions": 16,
            "model_cases": len(cases()),
            **counts,
        },
        "scope": {
            "evidence_class": "exact_grammar_and_conditional_integer_model_with_independent_boolean_predicate",
            "domain": [
                "Third import normal x86 stdcall return with four argument bytes removed",
                "Nonvolatile registers and five explicitly listed frame words survive the abstract import",
                "Current comparison global is independent of prefix seed; both equality outcomes are modeled",
                "Nonwrapping mapped 32-bit frame addresses; only the declared finite frame and numeric samples are replayed",
                "Ordinary integer and stack effects with no prefix-specific diversion; MPX and BND hardware effects are outside this model",
            ],
            "not_claimed": [
                "Actual import effects or normal return; record buffers may be mutated",
                "Behavior after external equality-check mismatch transfer at 0x00357b6a",
                "Native CPU execution, complete architectural flags, concurrency, faults or timing",
                "Authentic context capture, full imported reporting behavior or accounting promotion",
            ],
            "source_validation": "Canonical source joins and fresh owner, tiny helper, equality checker and third import binding witnesses; earlier full matrices and whole-atlas scans are not rerun",
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
            _canonical_sha256(evidence) == SEALED_SHA256, "sealed tail receipt differs"
        )
        _require(
            evidence["source_receipts"] == ids
            and evidence["checker"] == checker_spec()
            and evidence["assumed_import_summary"] == call_summary_spec()
            and evidence["predicate_partitions"] == branch_partition_spec()
            and evidence["matrix"] == MATRIX
            and evidence["vector_sha256"]
            == _canonical_sha256([list(v) for v in cases()]),
            "tail specification or source differs",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_tail(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_tail(
    executable: Path, evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        validate_structure(evidence, sources)
        actual = build_tail(executable, sources)
        _require(
            _canonical_bytes(evidence) == _canonical_bytes(actual),
            "exact tail analysis differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(actual["summary"]),
        }

    return _normalize(run)


def encode_tail(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
