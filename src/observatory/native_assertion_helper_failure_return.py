"""Conditional import-wrapper and failure/owner return-chain specification."""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import capstone.x86_const as x86
from src.observatory import native_assertion_helper_failure_dispatch as dispatch
from src.observatory import native_assertion_helper_return_tail as tail
from src.observatory.native_assertion_helper_descendant_pair import (
    _import_binding,
    _witness,
)
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
ANALYSIS_KIND = "pe_native_assertion_helper_failure_return"
SEALED_SHA256 = "0971cfa63e07affc80e0574319382099d9c41b29b5a380d1eb70a40e832a3444"
SOURCE_PINS = {
    "dispatch": (dispatch.ANALYSIS_KIND, dispatch.SEALED_SHA256),
    "frontier": dispatch.SOURCE_PINS["frontier"],
    "tail": (tail.ANALYSIS_KIND, tail.SEALED_SHA256),
    "program_facts": dispatch.SOURCE_PINS["program_facts"],
}
WRAPPER, PARENT, OWNER = 0x357B42, 0x357C5C, 0x379E5F
IMPORTS = [
    (0x357B47, 0x3D60E4, "SetUnhandledExceptionFilter", 4),
    (0x357B50, 0x3D6018, "UnhandledExceptionFilter", 4),
    (0x357B5B, 0x3D60F0, "GetCurrentProcess", 0),
    (0x357B62, 0x3D6014, "TerminateProcess", 8),
]
# Independently authored integer/stack transfer grammar. No decoded bytes or
# disassembly are emitted in the artifact.
OPS = {
    PARENT: ("call", ("imm", BASE + WRAPPER)),
    WRAPPER: ("push", ("reg", "ebp")),
    0x357B43: ("mov", ("reg", "ebp"), ("reg", "esp")),
    0x357B45: ("push", ("imm", 0)),
    0x357B47: ("call", ("mem", "", BASE + 0x3D60E4)),
    0x357B4D: ("push", ("mem", "ebp", 8)),
    0x357B50: ("call", ("mem", "", BASE + 0x3D6018)),
    0x357B56: ("push", ("imm", 0xC0000409)),
    0x357B5B: ("call", ("mem", "", BASE + 0x3D60F0)),
    0x357B61: ("push", ("reg", "eax")),
    0x357B62: ("call", ("mem", "", BASE + 0x3D6014)),
    0x357B68: ("pop", ("reg", "ebp")),
    0x357B69: ("ret",),
    0x357C61: ("mov", ("reg", "esp"), ("reg", "ebp")),
    0x357C63: ("pop", ("reg", "ebp")),
    0x357C64: ("ret",),
    OWNER: ("mov", ("reg", "esp"), ("reg", "ebp")),
    0x379E61: ("pop", ("reg", "ebp")),
    0x379E62: ("ret",),
}
SIZES = dict(zip(OPS, [5, 1, 2, 2, 6, 3, 6, 5, 6, 1, 6, 1, 1, 2, 1, 1, 2, 1, 1]))


class FailureReturnError(RuntimeError):
    """Exact return grammar or conditional interface differs."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FailureReturnError(message)


def _normalize(fn):
    try:
        return fn()
    except FailureReturnError:
        raise
    except Exception as exc:
        raise FailureReturnError(str(exc)) from exc


def _u32(value: Any) -> int:
    _require(type(value) is int and 0 <= value <= 0xFFFFFFFF, "expected u32")
    return value


def call_summary_spec() -> dict[str, Any]:
    return {
        "normal_return_assumed_for_each_import": True,
        "preserved_registers": ["ebx", "esi", "edi", "ebp"],
        "volatile_outputs": ["eax", "ecx", "edx", "eflags"],
        "protected_memory_G_intervals": [[-816, -804], [0, 8], [816, 824]],
        "get_current_process_additional_protected_G_interval": [-820, -816],
        "pending_status_word": 0xC0000409,
        "outer_words": "Values at this slice entry; earlier query may already have changed original owner words",
        "other_memory": "Unspecified including globals, pair contents and record contents",
        "model_memory_policy": "Forget every unprotected word after each abstract import",
        "imports": [
            {"name": name, "argument_bytes": n, "return_stack_increment": n + 4}
            for _, _, name, n in IMPORTS
        ],
        "nonreturn": "If any import fails to return normally, later instructions and final return are not established",
    }


def return_spec(
    final_eax: int, outer_ebp_word: int, outer_return_word: int
) -> dict[str, Any]:
    """Independent final interface conditional on the explicit call summaries."""
    return {
        "eax": _u32(final_eax),
        "ebp": _u32(outer_ebp_word),
        "instruction_pointer": _u32(outer_return_word),
        "esp_G_offset": 824,
        "esp_F_offset": 8,
        "ecx_edx_flags": "Last imported call's opaque volatile outputs",
        "nonvolatile_source": "Slice entry EBX ESI EDI",
        "original_owner_return_guaranteed": False,
        "termination_guaranteed": False,
    }


def cases() -> list[tuple[int, int, int, int]]:
    return [
        (a, h, t, o)
        for a in range(16)
        for h in (0, 0xFFFFFFFF)
        for t in (0, 1, 0xFFFFFFFF)
        for o in range(2)
    ]


def model_case(case: tuple[int, int, int, int], actions=None) -> dict[str, Any]:
    a, handle, last, outer = case
    _require(case in cases() and all(type(v) is int for v in case), "case differs")
    actions = OPS if actions is None else actions
    G = 0x2003000 + a
    F = G + 816
    H = G - 816
    old = [0x11223344, 0xAABBCCDD][outer]
    target = [0x12345678, 0x23456789][outer]
    mem = {G: F, G + 4: BASE + OWNER, F: old, F + 4: target, G - 808: BASE + 0x3F19F8}
    reg = dict(
        esp=G - 808,
        ebp=G,
        eax=4,
        ecx=0x91929394,
        edx=0x81828384,
        ebx=0x31415926,
        esi=0x27182818,
        edi=0x16180339,
    )
    trace = []
    calls = []
    pc = PARENT

    def push(v):
        reg["esp"] -= 4
        mem[reg["esp"]] = v

    def value(op):
        kind, *args = op
        if kind == "imm":
            return args[0]
        if kind == "reg":
            return reg[args[0]]
        base, disp = args
        return mem[(reg[base] if base else 0) + disp]

    for _ in range(30):
        if pc not in actions:
            break
        trace.append(f"0x{pc:08x}")
        op, *operands = actions[pc]
        nxt = pc + SIZES[pc]
        if op == "push":
            push(value(operands[0]))
        elif op == "pop":
            reg[operands[0][1]] = mem[reg["esp"]]
            reg["esp"] += 4
        elif op == "mov":
            reg[operands[0][1]] = value(operands[1])
        elif op == "ret":
            nxt = mem[reg["esp"]] - BASE
            reg["esp"] += 4
        elif op == "call":
            push(BASE + nxt)
            if pc == PARENT:
                nxt = WRAPPER
            else:
                index = next(i for i, row in enumerate(IMPORTS) if row[0] == pc)
                _, _, name, n = IMPORTS[index]
                arguments = [mem[reg["esp"] + 4 + i] for i in range(0, n, 4)]
                expected = [[0], [BASE + 0x3F19F8], [], [handle, 0xC0000409]][index]
                _require(arguments == expected, "import argument transfer differs")
                calls.append(
                    dict(name=name, arguments=arguments, esp_G_offset=reg["esp"] - G)
                )
                _require(reg["ebp"] == H, "wrapper frame differs")
                reg["eax"] = [0x13579BDF, 0x2468ACE0, handle, last][index]
                reg["ecx"] = 0xC0000000 + index
                reg["edx"] = 0xD0000000 + index
                protected = list(call_summary_spec()["protected_memory_G_intervals"])
                if index == 2:
                    protected.append([-820, -816])
                # Forget every unprotected word. A later read of one will fail,
                # rather than silently inheriting a stronger memory contract.
                mem = {
                    address: word
                    for address, word in mem.items()
                    if any(
                        G + lo <= address and address + 4 <= G + hi
                        for lo, hi in protected
                    )
                }
                reg["esp"] += 4 + n
        else:
            raise FailureReturnError("unmodeled return instruction")
        pc = nxt
    _require(len(trace) == 19 and pc + BASE == target, "return trace differs")
    expected = return_spec(last, old, target)
    _require(
        reg["eax"] == expected["eax"]
        and reg["ebp"] == expected["ebp"]
        and reg["esp"] == G + 824,
        "final return interface differs",
    )
    _require(
        (reg["ebx"], reg["esi"], reg["edi"]) == (0x31415926, 0x27182818, 0x16180339),
        "nonvolatile return registers differ",
    )
    return dict(
        case=list(case),
        trace_rvas=trace,
        calls=calls,
        final=expected,
        final_ecx=reg["ecx"],
        final_edx=reg["edx"],
    )


def _grammar(rows):
    names = {
        getattr(x86, "X86_INS_" + s.upper()): s
        for s in ("push", "pop", "mov", "call", "ret")
    }
    actions = {}
    for row in rows:
        pc = row.address - BASE
        _require(row.id in names and row.size == SIZES.get(pc), "instruction differs")
        operands = []
        for op in row.operands:
            _require(op.size == 4, "operand width differs")
            if op.type == x86.X86_OP_REG:
                operands.append(("reg", row.reg_name(op.reg)))
            elif op.type == x86.X86_OP_IMM:
                operands.append(("imm", op.imm & 0xFFFFFFFF))
            else:
                _require(
                    op.type == x86.X86_OP_MEM and op.mem.index == op.mem.segment == 0,
                    "unreviewed memory operand",
                )
                operands.append(
                    (
                        "mem",
                        row.reg_name(op.mem.base) if op.mem.base else "",
                        op.mem.disp,
                    )
                )
        actions[pc] = (names[row.id], *operands)
    _require(actions == OPS, "exact return grammar differs")
    return actions


def _preflight(sources):
    _validate_json_tree(sources, "sources")
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    identities = {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }
    identity = sources["program_facts"]["identity"]
    _require(
        identity["executable_sha256"] == EXE_SHA256
        and all(
            _canonical_bytes(sources[k]["build_identity"]) == _canonical_bytes(identity)
            for k in ("dispatch", "frontier", "tail")
        ),
        "build identity differs",
    )
    return identities


def _wrapper_binding(image, slot):
    if slot in (0x3D60E4, 0x3D6018):
        return _import_binding(image, slot)
    expected = {0x3D60F0: "GetCurrentProcess", 0x3D6014: "TerminateProcess"}
    matches = [r for r in image.imports() if r["iat_rva"] == f"0x{slot:08x}"]
    _require(slot in expected and len(matches) == 1, "unreviewed wrapper import")
    item = matches[0]
    _require(
        item["name"] == expected[slot]
        and item["library"] == "KERNEL32.dll"
        and item["ordinal"] is None,
        "wrapper import metadata differs",
    )
    descriptor = _witness(image, 0x48ED30, 20)
    original, timestamp, forwarder, name, first = struct.unpack_from(
        "<IIIII", image.data, int(descriptor["file_offset"], 16)
    )
    _require(
        (original, timestamp, forwarder, name, first)
        == (0x48ED80, 0, 0, 0x4905FE, 0x3D6000),
        "descriptor differs",
    )
    ilt = _witness(image, original + slot - first, 4)
    iat = _witness(image, slot, 4)
    offset = int(ilt["file_offset"], 16)
    target = struct.unpack_from("<I", image.data, offset)[0]
    _require(
        not target & 0x80000000
        and image.data[offset : offset + 4]
        == image.data[int(iat["file_offset"], 16) : int(iat["file_offset"], 16) + 4],
        "raw IAT ILT differs",
    )
    by_name = _witness(image, target, len(item["name"]) + 3)
    offset = int(by_name["file_offset"], 16)
    _require(
        struct.unpack_from("<H", image.data, offset)[0] == item["hint"]
        and image.data[offset + 2 : offset + by_name["size"]]
        == item["name"].encode("ascii") + b"\0",
        "raw import name differs",
    )
    return dict(
        metadata=item,
        descriptor=descriptor,
        ilt_entry=ilt,
        iat_slot=iat,
        import_by_name=by_name,
        name_metadata_only=True,
    )


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    identities = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    wrapper = _decode_body(data, image, sources["program_facts"], WRAPPER)
    frontier = _decode_body(data, image, sources["program_facts"], 0x357B6A)
    owner = _decode_body(data, image, sources["program_facts"], 0x379D28)
    parent = [r for r in frontier if r.address - BASE >= PARENT]
    continuation = [r for r in owner if r.address - BASE >= OWNER]
    _require(
        [_point(r) for r in frontier]
        == [
            {k: p[k] for k in ("rva", "size", "sha256")}
            for p in sources["frontier"]["function_body"]["reviewed_points"]
        ],
        "frontier points differ",
    )
    _require(
        [_point(r) for r in continuation]
        == [p for p in sources["tail"]["tail"]["points"] if int(p["rva"], 16) >= OWNER],
        "owner continuation differs",
    )
    edge = sources["frontier"]["native_calls"]["outgoing_direct"][1]
    wrapper_hash = hashlib.sha256(b"".join(bytes(r.bytes) for r in wrapper)).hexdigest()
    _require(
        edge["instruction"] == _point(parent[0])
        and edge["target_entry_rva"] == f"0x{WRAPPER:08x}"
        and edge["target_body_size"] == 40
        and edge["target_body_sha256"] == wrapper_hash,
        "wrapper direct edge differs",
    )
    actions = _grammar(wrapper + parent + continuation)
    bindings = []
    for site, slot, name, n in IMPORTS:
        binding = _wrapper_binding(image, slot)
        _require(binding["metadata"]["name"] == name, "import name differs")
        bindings.append(
            dict(
                instruction=_point(
                    next(r for r in wrapper if r.address - BASE == site)
                ),
                binding=binding,
                argument_bytes=n,
            )
        )
    results = hashlib.sha256()
    for case in cases():
        results.update(_canonical_bytes(model_case(case, actions)))
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=dict(sources["program_facts"]["identity"]),
        source_receipts=identities,
        wrapper=dict(
            points=[_point(r) for r in wrapper], bytes=40, sha256=wrapper_hash
        ),
        parent_tail=dict(points=[_point(r) for r in parent], bytes=9),
        owner_continuation=dict(points=[_point(r) for r in continuation], bytes=4),
        import_bindings=bindings,
        assumed_import_summaries=call_summary_spec(),
        relation=dict(
            final_eax_source="TerminateProcess normal return",
            final_ebp_source="outer word at F at this slice entry",
            final_target_source="outer word at F+4 at this slice entry",
            final_esp_F_offset=8,
            original_owner_words_not_assumed=True,
        ),
        vector_sha256=_canonical_sha256([list(c) for c in cases()]),
        results_sha256=results.hexdigest(),
        summary=dict(
            wrapper_nodes=12,
            parent_tail_nodes=4,
            owner_continuation_nodes=3,
            decoded_bytes=53,
            model_cases=len(cases()),
            actual_import_executions=0,
        ),
        scope=dict(
            evidence_class="exact_grammar_and_conditional_integer_model",
            premises=[
                "Mapped nonwrapping ordinary 32-bit integer and stack semantics",
                "All four imports return under declared summaries",
                "F equals G plus 816; parent and wrapper headers and observed outer words remain protected",
                "Argument is the declared pair address; pair contents and globals are unspecified",
            ],
            not_claimed=[
                "Actual imported behavior or termination",
                "Original outer words survived the preceding query",
                "Global record preservation or object validity",
                "Unconditional failure-owner semantics or accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    def run():
        _validate_json_tree(evidence, "evidence")
        identities = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256,
            "sealed return receipt differs",
        )
        _require(
            evidence["source_receipts"] == identities
            and evidence["assumed_import_summaries"] == call_summary_spec()
            and evidence["vector_sha256"]
            == _canonical_sha256([list(c) for c in cases()]),
            "return specification differs",
        )
        _assert_publication_safe(evidence)
        return dict(
            status="structurally_verified",
            evidence_sha256=SEALED_SHA256,
            summary=evidence["summary"],
        )

    return _normalize(run)


def build_return(executable, sources):
    def run():
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_return(executable, evidence, sources):
    def run():
        validate_structure(evidence, sources)
        _require(
            _canonical_bytes(build_return(executable, sources))
            == _canonical_bytes(evidence),
            "exact return analysis differs",
        )
        return dict(
            status="verified",
            evidence_sha256=SEALED_SHA256,
            summary=evidence["summary"],
        )

    return _normalize(run)


def encode_return(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
