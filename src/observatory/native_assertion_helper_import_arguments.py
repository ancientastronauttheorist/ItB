"""Conditional symbolic import-argument construction from exact caller witnesses."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import capstone.x86_const as x86
from src.observatory import native_assertion_helper_import_handoff as handoff
from src.observatory import windows_exception_layout as layout
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
ANALYSIS_KIND = "pe_native_assertion_helper_import_arguments"
SEALED_SHA256 = "a5db0b615b94a1291132a500fd025a74aeb4b0f8b78409f5d91bb30a6d4e282f"
OWNER, START, STOP = 0x379D28, 0x379E20, 0x379E37
SOURCE_PINS = {
    "pair": (
        "pe_native_assertion_helper_descendant_pair",
        "47421700f38e3dbf3f5283bf89d3beb5d6421d32eaf05938ad58989908f93d0b",
    ),
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
    "handoff": (handoff.ANALYSIS_KIND, handoff.SEALED_SHA256),
    "layout": (layout.ANALYSIS_KIND, layout.SEALED_SHA256),
}
IMPORTS = [
    (0x379E20, 0x3D6008, "IsDebuggerPresent"),
    (0x379E2A, 0x3D60E4, "SetUnhandledExceptionFilter"),
    (0x379E37, 0x3D6018, "UnhandledExceptionFilter"),
]


class ArgumentError(RuntimeError):
    """An exact witness, symbolic premise, or sealed argument receipt differs."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ArgumentError(message)


def _normalize(fn: Any) -> Any:
    try:
        return fn()
    except ArgumentError:
        raise
    except Exception as exc:
        raise ArgumentError(str(exc)) from exc


def _frame(offset: int) -> dict[str, Any]:
    return {"kind": "frame_relative", "offset": offset}


def _symbol(name: str) -> dict[str, Any]:
    return {"kind": "opaque_u32", "name": name}


def _constant(value: int) -> dict[str, Any]:
    return {"kind": "u32_constant", "value": value}


def call_summary_spec() -> list[dict[str, Any]]:
    """Explicit assumed summaries, not observations of imported implementations."""
    return [
        {
            "call_index": index,
            "import_name": name,
            "argument_bytes": 4 * index,
            "normal_return_assumed": True,
            "return_address_popped": True,
            "callee_argument_cleanup_bytes": 4 * index,
            "preserved_registers": ["ebx", "esi", "edi", "ebp"],
            "unknown_outputs": ["eax", "ecx", "edx", "eflags"],
            "caller_owned_memory_preserved_from_frame_offset": -812,
            "lower_stack_memory": "unspecified even after return",
            "global_memory": "unspecified",
        }
        for index, (_, _, name) in enumerate(IMPORTS[:2])
    ]


def operation_spec() -> list[dict[str, Any]]:
    return [
        {"rva": "0x00379e20", "operation": "import_call", "call_index": 0},
        {"rva": "0x00379e26", "operation": "push", "value": _constant(0)},
        {
            "rva": "0x00379e28",
            "operation": "copy_register",
            "destination": "edi",
            "source": "eax",
        },
        {"rva": "0x00379e2a", "operation": "import_call", "call_index": 1},
        {
            "rva": "0x00379e30",
            "operation": "frame_address",
            "destination": "eax",
            "offset": -808,
        },
        {"rva": "0x00379e36", "operation": "push_register", "source": "eax"},
    ]


def argument_transfer_spec() -> dict[str, Any]:
    """Independently authored expected symbolic transfer at the exclusive stop."""
    return {
        "entry_esp_offset": -812,
        "call_frames": [
            {
                "call_index": 0,
                "pre_call_esp_offset": -812,
                "callee_entry_esp_offset": -816,
                "return_esp_offset": -812,
                "arguments": [],
            },
            {
                "call_index": 1,
                "pre_call_esp_offset": -816,
                "callee_entry_esp_offset": -820,
                "return_esp_offset": -812,
                "arguments": [_constant(0)],
            },
        ],
        "caller_writes": [
            {
                "rva": "0x00379e26",
                "frame_offset": -816,
                "width": 4,
                "value": _constant(0),
            },
            {
                "rva": "0x00379e36",
                "frame_offset": -816,
                "width": 4,
                "value": _frame(-808),
            },
        ],
        "final_registers": {
            "eax": _frame(-808),
            "ecx": _symbol("call_1_ecx"),
            "edx": _symbol("call_1_edx"),
            "eflags": _symbol("call_1_eflags"),
            "edi": _symbol("call_0_eax"),
            "ebx": _symbol("entry_ebx"),
            "esi": _symbol("entry_esi"),
            "ebp": _frame(0),
            "esp": _frame(-816),
        },
        "final_known_outgoing_words": [
            {"frame_offset": -816, "width": 4, "value": _frame(-808)}
        ],
        "unexecuted_call_argument": {
            "call_rva": "0x00379e37",
            "iat_slot_rva": "0x003d6018",
            "import_name": "UnhandledExceptionFilter",
            "argument_index": 0,
            "at_pre_call_esp_offset": 0,
            "value": _frame(-808),
            "callee_entry_argument_offset_if_call_occurs": 4,
        },
        "preserved_frame_regions": [[-808, -800], [-800, -720], [-720, -4]],
    }


def symbolic_transfer(
    operations: list[dict[str, Any]], summaries: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Compute the conditional transfer without invoking any imported function."""
    _validate_json_tree(operations, "operations")
    if summaries is None:
        summaries = call_summary_spec()
    _validate_json_tree(summaries, "summaries")
    _require(
        _canonical_bytes(summaries) == _canonical_bytes(call_summary_spec()),
        "call-summary premise differs",
    )
    _require(
        _canonical_bytes(operations) == _canonical_bytes(operation_spec()),
        "instruction operation specification differs",
    )
    regs = {
        n: _symbol("entry_" + n)
        for n in ("eax", "ebx", "ecx", "edx", "esi", "edi", "eflags")
    }
    regs.update(ebp=_frame(0), esp=_frame(-812))
    sp = -812
    words: dict[int, dict[str, Any]] = {}
    frames, writes = [], []
    for op in operations:
        kind = op["operation"]
        if kind == "import_call":
            index = op["call_index"]
            summary = summaries[index]
            count = summary["argument_bytes"] // 4
            args = [words[sp + 4 * i] for i in range(count)]
            frames.append(
                {
                    "call_index": index,
                    "pre_call_esp_offset": sp,
                    "callee_entry_esp_offset": sp - 4,
                    "return_esp_offset": sp + summary["callee_argument_cleanup_bytes"],
                    "arguments": args,
                }
            )
            sp += summary["callee_argument_cleanup_bytes"]
            for name in summary["unknown_outputs"]:
                regs[name] = _symbol(f"call_{index}_{name}")
            # Opaque callees may overwrite outgoing arguments and all lower
            # scratch bytes. Do not invent stale return-address memory facts.
            words = {offset: value for offset, value in words.items() if offset >= -812}
        elif kind in ("push", "push_register"):
            value = op["value"] if kind == "push" else regs[op["source"]]
            sp -= 4
            _require(sp + 4 <= -812, "caller write overlaps protected frame")
            words[sp] = value
            writes.append(
                {"rva": op["rva"], "frame_offset": sp, "width": 4, "value": value}
            )
        elif kind == "copy_register":
            regs[op["destination"]] = regs[op["source"]]
        elif kind == "frame_address":
            regs[op["destination"]] = _frame(op["offset"])
        else:
            raise ArgumentError("unsupported symbolic instruction")
        regs["esp"] = _frame(sp)
    expected = argument_transfer_spec()
    actual = {
        "entry_esp_offset": -812,
        "call_frames": frames,
        "caller_writes": writes,
        "final_registers": regs,
        "final_known_outgoing_words": [
            {"frame_offset": o, "width": 4, "value": v}
            for o, v in sorted(words.items())
        ],
        "unexecuted_call_argument": {
            "call_rva": f"0x{STOP:08x}",
            "iat_slot_rva": f"0x{IMPORTS[2][1]:08x}",
            "import_name": IMPORTS[2][2],
            "argument_index": 0,
            "at_pre_call_esp_offset": 0,
            "value": words[sp],
            "callee_entry_argument_offset_if_call_occurs": 4,
        },
        "preserved_frame_regions": [[-808, -800], [-800, -720], [-720, -4]],
    }
    _require(
        actual == expected, "symbolic transfer differs from independent specification"
    )
    return actual


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
            for k in ("pair", "handoff")
        ),
        "source build differs",
    )
    _require(
        sources["handoff"]["prefix"]["exclusive_stop_rva"] == f"0x{START:08x}",
        "entry handoff differs",
    )
    _require(
        sources["layout"]["sdk_layout"] == layout.sdk_layout_spec()
        and sources["layout"]["frame_overlap"] == layout.frame_overlap_spec(),
        "layout join differs",
    )
    return ids


def _grammar(rows: list[Any], stop_row: Any) -> list[dict[str, Any]]:
    _require(len(rows) == 6, "slice instruction count differs")

    def reg(op: Any, name: int) -> bool:
        return op.type == x86.X86_OP_REG and op.reg == name and op.size == 4

    def mem(op: Any, base: int, disp: int) -> bool:
        return (
            op.type == x86.X86_OP_MEM
            and op.size == 4
            and op.mem.base == base
            and op.mem.disp == disp
            and op.mem.index == op.mem.segment == 0
        )

    def imported(row: Any, index: int) -> None:
        site, slot, _ = IMPORTS[index]
        _require(
            row.address - BASE == site
            and row.id == x86.X86_INS_CALL
            and len(row.operands) == 1
            and mem(row.operands[0], 0, BASE + slot),
            "import instruction grammar differs",
        )

    imported(rows[0], 0)
    imported(rows[3], 1)
    imported(stop_row, 2)
    r = rows[1]
    _require(
        r.id == x86.X86_INS_PUSH
        and len(r.operands) == 1
        and r.operands[0].type == x86.X86_OP_IMM
        and r.operands[0].imm == 0
        and r.operands[0].size == 4,
        "zero argument push differs",
    )
    r = rows[2]
    _require(
        r.id == x86.X86_INS_MOV
        and len(r.operands) == 2
        and reg(r.operands[0], x86.X86_REG_EDI)
        and reg(r.operands[1], x86.X86_REG_EAX),
        "first return preservation differs",
    )
    r = rows[4]
    _require(
        r.id == x86.X86_INS_LEA
        and len(r.operands) == 2
        and reg(r.operands[0], x86.X86_REG_EAX)
        and mem(r.operands[1], x86.X86_REG_EBP, -808),
        "pointer-pair address differs",
    )
    r = rows[5]
    _require(
        r.id == x86.X86_INS_PUSH
        and len(r.operands) == 1
        and reg(r.operands[0], x86.X86_REG_EAX),
        "pointer-pair argument push differs",
    )
    operations = operation_spec()
    _require(
        [f"0x{r.address-BASE:08x}" for r in rows] == [o["rva"] for o in operations],
        "operation sites differ",
    )
    return operations


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    all_rows = _decode_body(data, image, sources["program_facts"], OWNER)
    _require(
        [_point(r) for r in all_rows] == sources["pair"]["bodies"][0]["points"],
        "owner instruction witnesses differ",
    )
    rows = [r for r in all_rows if START <= r.address - BASE < STOP]
    stop_row = next(r for r in all_rows if r.address - BASE == STOP)
    operations = _grammar(rows, stop_row)
    controls = sources["pair"]["bodies"][0]["native_controls"]["import_controls"]
    joins = []
    for index, (site, slot, name) in enumerate(IMPORTS):
        control = controls[index]
        row = next(r for r in all_rows if r.address - BASE == site)
        binding = _import_binding(image, slot)
        _require(
            control["instruction"] == _point(row)
            and control["slot_rva"] == f"0x{slot:08x}"
            and control["binding"] == binding
            and binding["metadata"]["name"] == name,
            "exact import join differs",
        )
        joins.append(
            {
                "source_path": [
                    "bodies",
                    0,
                    "native_controls",
                    "import_controls",
                    index,
                ],
                "instruction": _point(row),
                "iat_slot_rva": f"0x{slot:08x}",
                "binding": binding,
                "treatment": (
                    "assumed abstract normal-return summary"
                    if index < 2
                    else "unexecuted argument boundary"
                ),
            }
        )
    transfer = symbolic_transfer(operations)
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed during analysis",
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "slice": {
            "owner_entry_rva": f"0x{OWNER:08x}",
            "start_rva": f"0x{START:08x}",
            "exclusive_stop_rva": f"0x{STOP:08x}",
            "size": STOP - START,
            "sha256": hashlib.sha256(
                b"".join(bytes(r.bytes) for r in rows)
            ).hexdigest(),
            "points": [_point(r) for r in rows],
            "unexecuted_stop_instruction": _point(stop_row),
        },
        "operations": operations,
        "import_joins": joins,
        "assumed_call_summaries": call_summary_spec(),
        "symbolic_transfer": transfer,
        "layout_compatibility_join": {
            "pair_frame_offset": -808,
            "pair_size": 8,
            "record_frame_offset": -800,
            "context_frame_offset": -720,
            "sdk_layout_receipt_sha256": layout.SEALED_SHA256,
            "argument_description": "Address of the previously populated pair with byte layout compatible with SDK EXCEPTION_POINTERS",
        },
        "summary": {
            "instructions": 6,
            "bytes": 23,
            "abstract_import_calls": 2,
            "unexecuted_import_boundaries": 1,
            "explicit_caller_stack_writes": 2,
            "final_esp_offset": -816,
            "argument_frame_offset": -808,
        },
        "scope": {
            "evidence_class": "exact_instruction_grammar_and_conditional_symbolic_call_summary_transfer",
            "domain": [
                "32-bit nonwrapping mapped frame and outgoing stack including frame minus 820",
                "Entry EBP denotes frame and ESP equals frame minus 812 from sealed handoff",
                "Both imported calls return normally under explicitly assumed x86 stdcall summaries",
                "Abstract callees preserve caller-owned stack memory at and above frame minus 812",
                "Return and volatile register outputs are opaque symbols; flags denote an opaque architectural flag image",
            ],
            "not_claimed": [
                "Actual imported implementation effects, normal return or runtime call execution",
                "Runtime record validity or original CPU context capture",
                "Contents of lower stack scratch or global memory after either abstract call",
                "Third imported call execution, whole-function return, reporting effects or accounting promotion",
            ],
            "source_validation": "Canonical-pinned handoff and layout receipts plus fresh complete owner decode and raw PE import binding witnesses; earlier dynamic matrices and SDK compilation are not rerun",
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
            "sealed import-arguments receipt differs",
        )
        _require(
            evidence["source_receipts"] == ids
            and evidence["assumed_call_summaries"] == call_summary_spec()
            and evidence["operations"] == operation_spec()
            and evidence["symbolic_transfer"] == symbolic_transfer(operation_spec()),
            "transfer or source differs",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_arguments(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_arguments(
    executable: Path, evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        validate_structure(evidence, sources)
        actual = build_arguments(executable, sources)
        _require(
            _canonical_bytes(evidence) == _canonical_bytes(actual),
            "exact argument analysis differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(actual["summary"]),
        }

    return _normalize(run)


def encode_arguments(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
