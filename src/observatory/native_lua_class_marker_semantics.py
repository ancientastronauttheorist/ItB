"""Conditional Lua marker predicate with exact x86 and abstract Lua stack models."""

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
from src.observatory.native_assertion_helper_descendant_pair import _witness

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_class_marker_semantics"
SEALED_SHA256 = "fb30c2feb6bcbc4583ee415585405a130b1219952d23c9aecdf56103158a7c7d"
START, END, LITERAL = 0x2EB560, 0x2EB5B4, 0x43C738
SOURCE_PINS = {
    "chain": (
        "pe_native_lua_class_return_helper_chain",
        "33ad87a98131700dce12bd34a7febea3159b6f461710f0b8296d95ded1b37095",
    ),
    "direct_calls": (
        "pe_native_lua_direct_import_call_census",
        "07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608",
    ),
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
}
CALLS = {
    0x2EB565: (0x3D6534, "lua_getmetatable"),
    0x2EB578: (0x3D6494, "lua_pushstring"),
    0x2EB581: (0x3D64BC, "lua_gettable"),
    0x2EB58A: (0x3D64F8, "lua_toboolean"),
    0x2EB59A: (0x3D6510, "lua_settop"),
    0x2EB5A7: (0x3D6510, "lua_settop"),
}
# Independently authored operation grammar, private to validation and modeling.
OPS = {
    0x2EB560: ("push", ("reg", "esi")),
    0x2EB561: ("mov", ("reg", "esi"), ("reg", "ecx")),
    0x2EB563: ("push", ("reg", "edx")),
    0x2EB564: ("push", ("reg", "esi")),
    0x2EB565: ("call", ("mem", BASE + 0x3D6534)),
    0x2EB56B: ("add", ("reg", "esp"), ("imm", 8)),
    0x2EB56E: ("test", ("reg", "eax"), ("reg", "eax")),
    0x2EB570: ("je", ("imm", BASE + 0x2EB5B0)),
    0x2EB572: ("push", ("imm", BASE + LITERAL)),
    0x2EB577: ("push", ("reg", "esi")),
    0x2EB578: ("call", ("mem", BASE + 0x3D6494)),
    0x2EB57E: ("push", ("imm", -2)),
    0x2EB580: ("push", ("reg", "esi")),
    0x2EB581: ("call", ("mem", BASE + 0x3D64BC)),
    0x2EB587: ("push", ("imm", -1)),
    0x2EB589: ("push", ("reg", "esi")),
    0x2EB58A: ("call", ("mem", BASE + 0x3D64F8)),
    0x2EB590: ("add", ("reg", "esp"), ("imm", 24)),
    0x2EB593: ("push", ("imm", -3)),
    0x2EB595: ("push", ("reg", "esi")),
    0x2EB596: ("test", ("reg", "eax"), ("reg", "eax")),
    0x2EB598: ("je", ("imm", BASE + 0x2EB5A7)),
    0x2EB59A: ("call", ("mem", BASE + 0x3D6510)),
    0x2EB5A0: ("add", ("reg", "esp"), ("imm", 8)),
    0x2EB5A3: ("mov", ("reg", "al"), ("imm", 1)),
    0x2EB5A5: ("pop", ("reg", "esi")),
    0x2EB5A6: ("ret",),
    0x2EB5A7: ("call", ("mem", BASE + 0x3D6510)),
    0x2EB5AD: ("add", ("reg", "esp"), ("imm", 8)),
    0x2EB5B0: ("xor", ("reg", "al"), ("reg", "al")),
    0x2EB5B2: ("pop", ("reg", "esi")),
    0x2EB5B3: ("ret",),
}
ORDER = list(OPS)
SIZES = {
    pc: (ORDER[i + 1] if i + 1 < len(ORDER) else END) - pc for i, pc in enumerate(ORDER)
}


class MarkerError(RuntimeError):
    """A source, exact instruction, call contract or model observation differs."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise MarkerError(message)


def _normalize(fn: Any) -> Any:
    try:
        return fn()
    except MarkerError:
        raise
    except Exception as exc:
        raise MarkerError(str(exc)) from exc


def marker_spec(
    has_metatable: bool, marker_truth: bool, final_void_eax: int = 0
) -> dict[str, Any]:
    _require(
        type(has_metatable) is bool and type(marker_truth) is bool,
        "marker predicates must be booleans",
    )
    _require(
        type(final_void_eax) is int and 0 <= final_void_eax <= 0xFFFFFFFF,
        "invalid void return register",
    )
    low = int(has_metatable and marker_truth)
    return {
        "path": (
            "no_metatable"
            if not has_metatable
            else "truthy_marker" if marker_truth else "false_marker"
        ),
        "al": low,
        "eax": (final_void_eax & 0xFFFFFF00) | low if has_metatable else 0,
        "eax_upper_source": (
            "last_void_settop_clobber" if has_metatable else "zero_getmetatable_result"
        ),
        "lua_stack_delta": 0,
        "lua_stack_prefix_restored": True,
        "native_esp_delta": 4,
        "preserved_registers": ["ebx", "esi", "edi", "ebp"],
        "api_calls": 5 if has_metatable else 1,
    }


def lua_truth(kind: str) -> bool:
    _require(
        type(kind) is str
        and kind
        in (
            "nil",
            "false",
            "true",
            "zero",
            "empty_string",
            "table",
            "function",
            "userdata",
            "thread",
        ),
        "invalid abstract Lua value kind",
    )
    return kind not in ("nil", "false")


def call_summary_spec() -> dict[str, Any]:
    return {
        "convention": "x86 cdecl",
        "arguments_bytes_each_call": 8,
        "callee_return_pop_bytes": 4,
        "callee_argument_cleanup_bytes": 0,
        "preserved_registers": ["ebx", "esi", "edi", "ebp"],
        "volatile_outputs": ["eax", "ecx", "edx", "eflags"],
        "protected_entry_esp_relative_words": [-4, 0],
        "memory_policy": "After each abstract API return retain only saved ESI and incoming return words; later arguments are freshly pushed",
        "lua_effects": [
            {
                "api": "lua_getmetatable",
                "arguments": ["state", "incoming_index"],
                "effect": "Absent metatable leaves stack unchanged and returns zero; present metatable pushes it and returns one",
            },
            {
                "api": "lua_pushstring",
                "arguments": ["state", "marker_literal"],
                "effect": "Push marker string",
            },
            {
                "api": "lua_gettable",
                "arguments": ["state", "minus_two"],
                "effect": "Consume key and push lookup result; ordinary indexing may invoke metamethods",
            },
            {
                "api": "lua_toboolean",
                "arguments": ["state", "minus_one"],
                "effect": "Return zero for nil or false, one otherwise; no stack change",
            },
            {
                "api": "lua_settop",
                "arguments": ["state", "minus_three"],
                "effect": "Remove lookup result and metatable; EAX is an arbitrary void-call clobber",
            },
        ],
        "premises": [
            "All called APIs return normally without errors or nonlocal exits",
            "Lua state, incoming index and stack capacity are valid for the declared API operations",
            "Cdecl preservation and protected native words hold; ordinary integer and mapped stack semantics apply",
            "Abstract Lua stack effects preserve the entry prefix; heap and global side effects are unconstrained",
        ],
    }


def model_case(
    alignment: int,
    prefix_length: int,
    has_metatable: bool,
    value_kind: str,
    final_void_eax: int,
    actions: Mapping[int, tuple] | None = None,
) -> dict[str, Any]:
    _require(
        type(alignment) is int
        and 0 <= alignment < 16
        and type(prefix_length) is int
        and prefix_length in (1, 3),
        "invalid synthetic stack domain",
    )
    expected = marker_spec(has_metatable, lua_truth(value_kind), final_void_eax)
    actions = OPS if actions is None else actions
    _require(
        isinstance(actions, Mapping) and set(actions) == set(OPS),
        "marker operation sites differ",
    )
    entry = 0x02002000 + alignment
    initial = {
        "eax": 0x11223344,
        "ecx": 0x01001000,
        "edx": 0xFFFFFFFF,
        "ebx": 0x22334455,
        "esi": 0x33445566,
        "edi": 0x44556677,
        "ebp": 0x55667788,
        "esp": entry,
    }
    regs = dict(initial)
    memory = {entry: 0x30303030}
    prefix = [("entry", i) for i in range(prefix_length)]
    lua = list(prefix)
    trace = []
    calls = []
    zf = None
    pc = START

    def read(arg):
        if arg[0] == "imm":
            return arg[1] & 0xFFFFFFFF
        return regs["eax"] & 255 if arg[1] == "al" else regs[arg[1]]

    def write(arg, value):
        if arg[1] == "al":
            regs["eax"] = (regs["eax"] & 0xFFFFFF00) | (value & 255)
        else:
            regs[arg[1]] = value & 0xFFFFFFFF

    for _ in range(40):
        _require(pc in actions, "marker escaped exact body")
        trace.append(pc)
        op, *args = actions[pc]
        nxt = pc + SIZES[pc]
        if op == "push":
            regs["esp"] -= 4
            memory[regs["esp"]] = read(args[0])
        elif op == "pop":
            _require(regs["esp"] in memory, "unproved native pop word")
            write(args[0], memory[regs["esp"]])
            regs["esp"] += 4
        elif op == "mov":
            write(args[0], read(args[1]))
        elif op == "add":
            write(args[0], read(args[0]) + read(args[1]))
            zf = None
        elif op == "xor":
            write(args[0], read(args[0]) ^ read(args[1]))
            zf = True
        elif op == "test":
            zf = (read(args[0]) & read(args[1])) == 0
        elif op == "je":
            _require(type(zf) is bool, "undefined branch predicate")
            if zf:
                nxt = read(args[0]) - BASE
        elif op == "call":
            slot, name = CALLS[pc]
            _require(args[0] == ("mem", BASE + slot), "import target differs")
            regs["esp"] -= 4
            memory[regs["esp"]] = BASE + nxt
            sp = regs["esp"]
            state, index = memory[sp + 4], memory[sp + 8]
            _require(state == initial["ecx"], "Lua state argument differs")
            before = len(lua)
            eax = 0xA1B2C3D4
            if name == "lua_getmetatable":
                _require(index == initial["edx"], "incoming Lua index differs")
                if has_metatable:
                    lua.append(("metatable", 0))
                eax = int(has_metatable)
            elif name == "lua_pushstring":
                _require(index == BASE + LITERAL, "marker literal differs")
                lua.append(("key", "__luabind_classrep"))
            elif name == "lua_gettable":
                _require(
                    index == 0xFFFFFFFE
                    and lua[-2:] == [("metatable", 0), ("key", "__luabind_classrep")],
                    "lookup arguments differ",
                )
                lua.pop()
                lua.append(("value", value_kind))
            elif name == "lua_toboolean":
                _require(
                    index == 0xFFFFFFFF and lua[-1] == ("value", value_kind),
                    "truth arguments differ",
                )
                # Independent implementation of Lua false values, not Python truthiness.
                eax = 0 if lua[-1][1] in ("nil", "false") else 1
            else:
                _require(index == 0xFFFFFFFD, "cleanup index differs")
                newtop = len(lua) + (index - 0x100000000) + 1
                del lua[newtop:]
                eax = final_void_eax
            calls.append(
                {
                    "site_rva": f"0x{pc:08x}",
                    "api": name,
                    "callee_esp_delta": sp - entry,
                    "arguments": [state, index],
                    "lua_top_before": before,
                    "lua_top_after": len(lua),
                }
            )
            regs["esp"] += 4
            regs.update(eax=eax, ecx=0x98765432, edx=0xABCDEF01)
            memory = {k: v for k, v in memory.items() if k in (entry - 4, entry)}
            zf = None
        elif op == "ret":
            _require(regs["esp"] in memory, "unproved native return word")
            target = memory[regs["esp"]]
            regs["esp"] += 4
            break
        else:
            raise MarkerError("unsupported operation")
        pc = nxt
    else:
        raise MarkerError("marker model did not return")
    _require(
        regs["eax"] == expected["eax"]
        and regs["esp"] == entry + 4
        and target == 0x30303030,
        "return relation differs",
    )
    _require(
        lua == prefix
        and all(regs[r] == initial[r] for r in expected["preserved_registers"]),
        "stack or nonvolatile preservation differs",
    )
    offsets = [-16] if not has_metatable else [-16, -16, -24, -32, -16]
    _require(
        [c["callee_esp_delta"] for c in calls] == offsets,
        "independent native call stack relation differs",
    )
    _require(
        [c["api"] for c in calls]
        == (
            ["lua_getmetatable"]
            if not has_metatable
            else [
                "lua_getmetatable",
                "lua_pushstring",
                "lua_gettable",
                "lua_toboolean",
                "lua_settop",
            ]
        ),
        "API ordering differs",
    )
    return {
        "input": {
            "alignment": alignment,
            "prefix_length": prefix_length,
            "has_metatable": has_metatable,
            "value_kind": value_kind,
            "final_void_eax": final_void_eax,
        },
        "outcome": expected,
        "trace_rvas": [f"0x{p:08x}" for p in trace],
        "calls": calls,
    }


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
    _require(
        [r.address - BASE for r in rows] == ORDER,
        "exact marker instruction points differ",
    )
    for row in rows:
        actual = []
        for arg in row.operands:
            if arg.type == x86.X86_OP_REG:
                actual.append(("reg", row.reg_name(arg.reg)))
            elif arg.type == x86.X86_OP_IMM:
                actual.append(("imm", arg.imm))
            elif arg.type == x86.X86_OP_MEM:
                _require(
                    not arg.mem.base and not arg.mem.index and not arg.mem.segment,
                    "unexpected memory addressing",
                )
                actual.append(("mem", arg.mem.disp))
            else:
                raise MarkerError("unsupported operand")
        pc = row.address - BASE
        _require(
            (row.mnemonic, *actual) == OPS[pc] and row.size == SIZES[pc],
            "exact marker operation differs",
        )
        width = 1 if pc in (0x2EB5A3, 0x2EB5B0) else 4
        _require(
            all(arg.size == width for arg in row.operands), "operand width differs"
        )


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    rows = _decode_body(data, image, sources["program_facts"], START)
    _grammar(rows)
    points = [_point(r) for r in rows]
    chain = sources["chain"]
    body = chain["function_bodies"][1]
    cfg = chain["control_flow_graphs"][1]
    _require(
        points == [{k: n[k] for k in ("rva", "size", "sha256")} for n in cfg["nodes"]],
        "chain complete instruction join differs",
    )
    bodyhash = hashlib.sha256(b"".join(bytes(r.bytes) for r in rows)).hexdigest()
    _require(
        bodyhash == body["body_sha256"] and body["body_size"] == 84,
        "chain body join differs",
    )
    imports = []
    for slot, name in sorted(set(CALLS.values())):
        matches = [r for r in image.imports() if r["iat_rva"] == f"0x{slot:08x}"]
        _require(
            len(matches) == 1
            and matches[0]["name"] == name
            and matches[0]["library"].lower() == "lua5.1.dll"
            and matches[0]["ordinal"] is None,
            "fresh Lua import binding differs",
        )
        census = [
            r
            for r in sources["direct_calls"]["lua_imports"]
            if r["iat_rva"] == f"0x{slot:08x}"
        ]
        _require(
            len(census) == 1
            and census[0]["name"] == name
            and census[0]["hint"] == matches[0]["hint"],
            "census import join differs",
        )
        imports.append(
            {
                "metadata": matches[0],
                "iat_slot": _witness(image, slot, 4),
                "name_metadata_only": True,
            }
        )
    freshcalls = []
    for row in rows:
        pc = row.address - BASE
        if pc in CALLS:
            slot, name = CALLS[pc]
            freshcalls.append(
                {
                    "call_form": "x86_absolute_iat_indirect_call_ff15",
                    "call_rva": f"0x{pc:08x}",
                    "iat_rva": f"0x{slot:08x}",
                    "import_name": name,
                    "instruction_sha256": _point(row)["sha256"],
                    "instruction_size": row.size,
                    "library": "lua5.1.dll",
                }
            )
    _require(
        freshcalls == body["direct_lua_calls"], "chain six import call joins differ"
    )
    literal = _witness(image, LITERAL, 19)
    ref = chain["literals"][0]
    _require(
        literal["sha256"] == ref["nul_terminated_bytes_sha256"]
        and ref["text"] == "__luabind_classrep",
        "marker literal differs",
    )
    cases = []
    kinds = [
        (False, "nil"),
        (True, "nil"),
        (True, "false"),
        (True, "zero"),
        (True, "empty_string"),
        (True, "table"),
    ]
    for alignment in range(16):
        for length in (1, 3):
            for present, kind in kinds:
                for value in (0, 0x12345678, 0xFFFFFFFF):
                    cases.append(model_case(alignment, length, present, kind, value))
    union = sorted({r for case in cases for r in case["trace_rvas"]})
    _require(
        union == [p["rva"] for p in points], "finite model instruction union differs"
    )
    negative = []
    for name, pc, replacement in [
        ("wide_result", 0x2EB5A3, ("mov", ("reg", "eax"), ("imm", 1))),
        ("wrong_cleanup", 0x2EB590, ("add", ("reg", "esp"), ("imm", 16))),
        ("wrong_lookup_index", 0x2EB57E, ("push", ("imm", -1))),
    ]:
        changed = dict(OPS)
        changed[pc] = replacement
        try:
            model_case(0, 1, True, "zero", 0x12345678, changed)
        except MarkerError:
            negative.append({"name": name, "rejected": True})
        else:
            raise MarkerError("negative semantic control accepted")
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "body": {
            "entry_rva": f"0x{START:08x}",
            "exclusive_end_rva": f"0x{END:08x}",
            "bytes": 84,
            "nodes": 32,
            "sha256": bodyhash,
            "points": points,
        },
        "imports": imports,
        "direct_lua_calls": freshcalls,
        "marker_literal": {"witness": literal, "text": ref["text"]},
        "call_summary": call_summary_spec(),
        "path_partition_representative_final_void_eax": 0,
        "path_partitions": [
            marker_spec(False, False),
            marker_spec(True, False),
            marker_spec(True, True),
        ],
        "matrix": {
            "native_alignments": list(range(16)),
            "lua_prefix_lengths": [1, 3],
            "abstract_cases": [{"has_metatable": p, "value_kind": k} for p, k in kinds],
            "last_void_eax": [0, 0x12345678, 0xFFFFFFFF],
        },
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": negative,
        },
        "summary": {
            "cases": len(cases),
            "static_bytes": 84,
            "static_nodes": 32,
            "modeled_nodes": len(union),
            "path_classes": 3,
            "direct_import_sites": 6,
            "unique_imports": 5,
            "actual_import_executions": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "conditional_exact_integer_and_abstract_Lua_stack_model",
            "semantic_basis": "Lua 5.1 reference manual C API stack effects, under explicit normal-return summaries",
            "not_claimed": [
                "Actual Lua or game execution, class identity, raw table lookup or absence of metamethod side effects",
                "Heap or globals preserved merely because stack prefix values are restored",
                "Whole EAX is a Boolean on metatable paths; only AL is normalized",
                "Errors, nonlocal exits, hardware faults, arbitrary native alignment validity or unconditional API behavior",
                "Full game recreation or atlas accounting promotion",
            ],
            "upstream_matrices_rerun": False,
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
            _canonical_sha256(evidence) == SEALED_SHA256,
            "sealed marker receipt differs",
        )
        _require(
            evidence["source_receipts"] == ids
            and evidence["call_summary"] == call_summary_spec(),
            "marker specification differs",
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
            "exact marker receipt differs",
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
