"""Conditional filtered Lua assignment loop, with explicit finite next transcripts."""

from __future__ import annotations
import hashlib
import itertools
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
ANALYSIS_KIND = "pe_native_lua_filtered_assignment_semantics"
SEALED_SHA256 = "b62b6409f2f3f3a003732bc106f5e4e3f0eaf543d2b246984a6513cc658a1b27"
START, END = 0x2EC050, 0x2EC104
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
IMPORTS = {
    0x3D64B8: "lua_pushnil",
    0x3D64B4: "lua_next",
    0x3D6494: "lua_pushstring",
    0x3D6510: "lua_settop",
    0x3D64C4: "lua_equal",
    0x3D64E4: "lua_pushvalue",
    0x3D6514: "lua_insert",
    0x3D6550: "lua_settable",
}
CALLS = {
    0x2EC054: 0x3D64B8,
    0x2EC05D: 0x3D64B4,
    0x2EC086: 0x3D6494,
    0x2EC08D: 0x3D64C4,
    0x2EC09D: 0x3D6510,
    0x2EC0A7: 0x3D6510,
    0x2EC0AF: 0x3D6494,
    0x2EC0B6: 0x3D64C4,
    0x2EC0C6: 0x3D6510,
    0x2EC0D0: 0x3D6510,
    0x2EC0D5: 0x3D64E4,
    0x2EC0DE: 0x3D6514,
    0x2EC0E7: 0x3D6550,
    0x2EC0F3: 0x3D64B4,
}
LITERALS = {0x420F68: "__init", 0x43C50C: "__finalize"}
# Independent exact-body grammar, never emitted as instruction text or bytes.
OPS = {
    0x2EC050: ("push", ("reg", "esi")),
    0x2EC051: ("mov", ("reg", "esi"), ("reg", "ecx")),
    0x2EC053: ("push", ("reg", "esi")),
    0x2EC054: ("call", ("mem", BASE + 0x3D64B8)),
    0x2EC05A: ("push", ("imm", -2)),
    0x2EC05C: ("push", ("reg", "esi")),
    0x2EC05D: ("call", ("mem", BASE + 0x3D64B4)),
    0x2EC063: ("add", ("reg", "esp"), ("imm", 12)),
    0x2EC066: ("test", ("reg", "eax"), ("reg", "eax")),
    0x2EC068: ("je", ("imm", BASE + 0x2EC102)),
    0x2EC06E: ("push", ("reg", "ebx")),
    0x2EC06F: ("mov", ("reg", "ebx"), ("mem", BASE + 0x3D6494)),
    0x2EC075: ("push", ("reg", "edi")),
    0x2EC076: ("mov", ("reg", "edi"), ("mem", BASE + 0x3D6510)),
    0x2EC07C: ("nop", ("address", "eax", 0)),
    0x2EC080: ("push", ("imm", BASE + 0x420F68)),
    0x2EC085: ("push", ("reg", "esi")),
    0x2EC086: ("call", ("reg", "ebx")),
    0x2EC088: ("push", ("imm", -3)),
    0x2EC08A: ("push", ("imm", -1)),
    0x2EC08C: ("push", ("reg", "esi")),
    0x2EC08D: ("call", ("mem", BASE + 0x3D64C4)),
    0x2EC093: ("add", ("reg", "esp"), ("imm", 20)),
    0x2EC096: ("test", ("reg", "eax"), ("reg", "eax")),
    0x2EC098: ("je", ("imm", BASE + 0x2EC0A4)),
    0x2EC09A: ("push", ("imm", -3)),
    0x2EC09C: ("push", ("reg", "esi")),
    0x2EC09D: ("call", ("reg", "edi")),
    0x2EC09F: ("add", ("reg", "esp"), ("imm", 8)),
    0x2EC0A2: ("jmp", ("imm", BASE + 0x2EC0F0)),
    0x2EC0A4: ("push", ("imm", -2)),
    0x2EC0A6: ("push", ("reg", "esi")),
    0x2EC0A7: ("call", ("reg", "edi")),
    0x2EC0A9: ("push", ("imm", BASE + 0x43C50C)),
    0x2EC0AE: ("push", ("reg", "esi")),
    0x2EC0AF: ("call", ("reg", "ebx")),
    0x2EC0B1: ("push", ("imm", -3)),
    0x2EC0B3: ("push", ("imm", -1)),
    0x2EC0B5: ("push", ("reg", "esi")),
    0x2EC0B6: ("call", ("mem", BASE + 0x3D64C4)),
    0x2EC0BC: ("add", ("reg", "esp"), ("imm", 28)),
    0x2EC0BF: ("test", ("reg", "eax"), ("reg", "eax")),
    0x2EC0C1: ("je", ("imm", BASE + 0x2EC0CD)),
    0x2EC0C3: ("push", ("imm", -3)),
    0x2EC0C5: ("push", ("reg", "esi")),
    0x2EC0C6: ("call", ("reg", "edi")),
    0x2EC0C8: ("add", ("reg", "esp"), ("imm", 8)),
    0x2EC0CB: ("jmp", ("imm", BASE + 0x2EC0F0)),
    0x2EC0CD: ("push", ("imm", -2)),
    0x2EC0CF: ("push", ("reg", "esi")),
    0x2EC0D0: ("call", ("reg", "edi")),
    0x2EC0D2: ("push", ("imm", -2)),
    0x2EC0D4: ("push", ("reg", "esi")),
    0x2EC0D5: ("call", ("mem", BASE + 0x3D64E4)),
    0x2EC0DB: ("push", ("imm", -2)),
    0x2EC0DD: ("push", ("reg", "esi")),
    0x2EC0DE: ("call", ("mem", BASE + 0x3D6514)),
    0x2EC0E4: ("push", ("imm", -5)),
    0x2EC0E6: ("push", ("reg", "esi")),
    0x2EC0E7: ("call", ("mem", BASE + 0x3D6550)),
    0x2EC0ED: ("add", ("reg", "esp"), ("imm", 32)),
    0x2EC0F0: ("push", ("imm", -2)),
    0x2EC0F2: ("push", ("reg", "esi")),
    0x2EC0F3: ("call", ("mem", BASE + 0x3D64B4)),
    0x2EC0F9: ("add", ("reg", "esp"), ("imm", 8)),
    0x2EC0FC: ("test", ("reg", "eax"), ("reg", "eax")),
    0x2EC0FE: ("jne", ("imm", BASE + 0x2EC080)),
    0x2EC100: ("pop", ("reg", "edi")),
    0x2EC101: ("pop", ("reg", "ebx")),
    0x2EC102: ("pop", ("reg", "esi")),
    0x2EC103: ("ret",),
}
ORDER = list(OPS)
SIZES = {
    p: (ORDER[i + 1] if i + 1 < len(ORDER) else END) - p for i, p in enumerate(ORDER)
}


class AssignmentError(RuntimeError):
    """An exact witness, call premise, loop invariant or independent relation differs."""


def _require(ok, message):
    if not ok:
        raise AssignmentError(message)


def _normalize(fn):
    try:
        return fn()
    except AssignmentError:
        raise
    except Exception as exc:
        raise AssignmentError(str(exc)) from exc


def iteration_spec(key_class: str) -> dict[str, Any]:
    _require(
        type(key_class) is str and key_class in ("init", "finalize", "other"),
        "invalid key class",
    )
    return {
        "key_class": key_class,
        "path": "assign" if key_class == "other" else "skip_" + key_class,
        "assignment_requested": key_class == "other",
        "assignment_destination_entry_index": -2,
        "assignment_call_index": -5,
        "iterator_key_retained": True,
        "value_consumed": True,
        "lua_stack_delta_before_next": -1,
        "api_calls_including_next": {"init": 4, "finalize": 7, "other": 10}[key_class],
    }


def assignment_spec(key_classes: list[str]) -> dict[str, Any]:
    _require(
        type(key_classes) is list and len(key_classes) <= 10000,
        "invalid finite next transcript",
    )
    rows = [iteration_spec(k) for k in key_classes]
    return {
        "iterations": len(rows),
        "assignment_iteration_indices": [
            i for i, r in enumerate(rows) if r["assignment_requested"]
        ],
        "assignment_requests": sum(r["assignment_requested"] for r in rows),
        "eax": 0,
        "eax_source": "exhausted_lua_next",
        "lua_stack_delta": 0,
        "entry_stack_values_restored": True,
        "native_esp_delta": 4,
        "preserved_registers": ["ebx", "esi", "edi", "ebp"],
        "api_calls": 2 + sum(r["api_calls_including_next"] for r in rows),
        "termination_premise": "The declared valid next transcript ends with normal exhaustion",
    }


def loop_invariant_spec() -> dict[str, Any]:
    return {
        "entry_lua_stack": ["prefix", "destination", "source"],
        "loop_body_entry": ["prefix", "destination", "source", "iterator_key", "value"],
        "before_next": ["prefix", "destination", "source", "iterator_key"],
        "assignment_before_call": [
            "prefix",
            "destination",
            "source",
            "iterator_key",
            "duplicate_key",
            "value",
        ],
        "normal_return": ["prefix", "destination", "source"],
        "native_loop_esp_entry_delta": -12,
        "native_loop_back_rva": "0x002ec080",
        "source_index_at_next": -2,
        "assignment_index": -5,
        "induction": "Initialization establishes the loop suffix; each of three local paths consumes value and retains the same iterator key; a normal next step either reestablishes the suffix or removes the key on exhaustion",
    }


def call_summary_spec() -> dict[str, Any]:
    return {
        "convention": "x86 cdecl",
        "callee_return_pop_bytes": 4,
        "callee_argument_cleanup_bytes": 0,
        "argument_bytes": {
            "lua_pushnil": 4,
            "lua_next": 8,
            "lua_pushstring": 8,
            "lua_equal": 12,
            "lua_settop": 8,
            "lua_pushvalue": 8,
            "lua_insert": 8,
            "lua_settable": 8,
        },
        "preserved_registers": ["ebx", "esi", "edi", "ebp"],
        "volatile_outputs": ["eax", "ecx", "edx", "eflags"],
        "memory_policy": "Retain only incoming return word and actually established saved ESI, EBX and EDI words after each normal API summary",
        "staged_binding_premise": "Loaded EBX and EDI callable values implement their named Lua summaries and survive calls as nonvolatile values",
        "api_effects": [
            {"api": "lua_pushnil", "effect": "Push nil seed"},
            {
                "api": "lua_next",
                "effect": "Pop key and either push the next key and value with nonzero result or push nothing with zero result",
            },
            {
                "api": "lua_pushstring",
                "effect": "Push the selected exact string literal",
            },
            {
                "api": "lua_equal",
                "effect": "Compare exact Lua values without stack change; this helper compares string literals so only equal string keys match",
            },
            {
                "api": "lua_settop",
                "effect": "Remove the specified suffix using a valid negative top index",
            },
            {"api": "lua_pushvalue", "effect": "Push a copy of the indexed value"},
            {
                "api": "lua_insert",
                "effect": "Move the top value into the indexed position",
            },
            {
                "api": "lua_settable",
                "effect": "Consume key and value and request normal assignment; newindex behavior may redirect or have side effects",
            },
        ],
        "premises": [
            "Normal APIs with valid state, source table, indices and sufficient Lua and native stack capacity",
            "Destination supports each requested normal assignment; errors and nonlocal exits are outside the relation",
            "The next transcript consists of valid successive calls and eventually exhausts; it is not a fixed initial source snapshot",
            "Source mutation or aliasing from assignment side effects must still satisfy each later next call premise",
            "Live imported targets match the named summaries; the PE IAT witnesses prove static bindings only",
            "Caller saved native words and ABI nonvolatiles survive; abstract API stack effects preserve the lower entry values",
        ],
        "not_assumed": [
            "Raw assignment, absent metamethods, destination table contents after side effects",
            "Iteration order, source immutability, distinct source and destination, or unconditional termination",
        ],
    }


# Independently tabulated callee stack offsets for one body iteration, including next.
ITERATION_CALL_OFFSETS = {
    "init": [-24, -36, -24, -24],
    "finalize": [-24, -36, -24, -32, -44, -24, -24],
    "other": [-24, -36, -24, -32, -44, -24, -32, -40, -48, -24],
}


def model_case(
    alignment: int,
    prefix_length: int,
    key_classes: list[str],
    volatile_eax: int,
    actions: Mapping[int, tuple] | None = None,
) -> dict[str, Any]:
    _require(
        type(alignment) is int
        and 0 <= alignment < 16
        and type(prefix_length) is int
        and prefix_length in (0, 2),
        "invalid synthetic stacks",
    )
    _require(
        type(volatile_eax) is int and 0 <= volatile_eax <= 0xFFFFFFFF,
        "invalid volatile clobber",
    )
    expected = assignment_spec(key_classes)
    _require(len(key_classes) <= 8, "model transcript exceeds finite limit")
    actions = OPS if actions is None else actions
    _require(
        isinstance(actions, Mapping) and set(actions) == set(OPS),
        "operation site set differs",
    )
    entry = 0x02002000 + alignment
    initial = {
        "eax": 0x11223344,
        "ecx": 0x01001000,
        "edx": 0x12345678,
        "ebx": 0x22334455,
        "esi": 0x33445566,
        "edi": 0x44556677,
        "ebp": 0x55667788,
        "esp": entry,
    }
    regs = dict(initial)
    memory = {entry: 0x30303030}
    protected = {entry}
    prefix = [("prefix", i) for i in range(prefix_length)]
    dest = ("destination", 0)
    source = ("source", 0)
    original = prefix + [dest, source]
    lua = list(original)
    items = [
        (
            (
                ("string", "__init")
                if c == "init"
                else ("string", "__finalize") if c == "finalize" else ("number", i)
            ),
            ("value", i),
        )
        for i, c in enumerate(key_classes)
    ]
    cursor = 0
    previous_key = ("nil",)
    trace = []
    calls = []
    requests = []
    invariants = []
    pc = START
    zf = None
    bindings = {BASE + slot: 0x10000000 + slot for slot in IMPORTS}

    def read(arg):
        if arg[0] == "reg":
            return regs[arg[1]]
        if arg[0] == "imm":
            return arg[1] & 0xFFFFFFFF
        _require(arg[0] == "mem" and arg[1] in bindings, "unproved import data read")
        return bindings[arg[1]]

    for _ in range(100 + 80 * len(items)):
        _require(pc in actions, "model escaped body")
        if pc == 0x2EC080:
            _require(
                cursor > 0
                and lua == original + list(items[cursor - 1])
                and regs["esp"] == entry - 12,
                "loop entry invariant differs",
            )
            invariants.append({"iteration": cursor - 1, "entry_suffix_verified": True})
        if pc == 0x2EC0F0:
            _require(
                cursor > 0
                and lua == original + [items[cursor - 1][0]]
                and regs["esp"] == entry - 12,
                "loop handoff invariant differs",
            )
        trace.append(pc)
        op, *args = actions[pc]
        nxt = pc + SIZES[pc]
        if op == "push":
            regs["esp"] -= 4
            memory[regs["esp"]] = read(args[0])
            if pc in (0x2EC050, 0x2EC06E, 0x2EC075):
                protected.add(regs["esp"])
        elif op == "pop":
            _require(regs["esp"] in memory, "unproved native pop")
            regs[args[0][1]] = memory[regs["esp"]]
            regs["esp"] += 4
        elif op == "mov":
            regs[args[0][1]] = read(args[1])
        elif op == "add":
            regs[args[0][1]] = (read(args[0]) + read(args[1])) & 0xFFFFFFFF
            zf = None
        elif op == "test":
            zf = (read(args[0]) & read(args[1])) == 0
        elif op in ("je", "jne"):
            _require(type(zf) is bool, "unproved branch predicate")
            if zf == (op == "je"):
                nxt = read(args[0]) - BASE
        elif op == "jmp":
            nxt = read(args[0]) - BASE
        elif op == "nop":
            pass
        elif op == "call":
            slot = CALLS[pc]
            name = IMPORTS[slot]
            _require(
                read(args[0]) == bindings[BASE + slot],
                "staged or direct call binding differs",
            )
            regs["esp"] -= 4
            sp = regs["esp"]
            memory[sp] = BASE + nxt
            argc = 1 if name == "lua_pushnil" else 3 if name == "lua_equal" else 2
            _require(
                all(sp + 4 * i in memory for i in range(1, argc + 1)),
                "missing native arguments",
            )
            argv = [memory[sp + 4 * i] for i in range(1, argc + 1)]
            _require(argv[0] == initial["ecx"], "Lua state argument differs")
            before = len(lua)
            eax = volatile_eax
            index = (
                None
                if argc == 1
                else argv[1] - (0x100000000 if argv[1] & 0x80000000 else 0)
            )
            if name == "lua_pushnil":
                lua.append(("nil",))
            elif name == "lua_next":
                _require(
                    index == -2 and lua[-2] == source and lua[-1] == previous_key,
                    "next source or key differs",
                )
                lua.pop()
                if cursor < len(items):
                    pair = items[cursor]
                    lua.extend(pair)
                    previous_key = pair[0]
                    cursor += 1
                    eax = 1
                else:
                    eax = 0
            elif name == "lua_pushstring":
                _require(argv[1] - BASE in LITERALS, "unproved string literal")
                lua.append(("string", LITERALS[argv[1] - BASE]))
            elif name == "lua_equal":
                _require(
                    index == -1 and argv[2] == 0xFFFFFFFD, "comparison indices differ"
                )
                _require(
                    lua[-1][0] == "string" and lua[-1][1] in LITERALS.values(),
                    "comparison literal differs",
                )
                eax = int(lua[-1] == lua[-3])
            elif name == "lua_settop":
                _require(index in (-2, -3), "unsupported top change")
                del lua[len(lua) + index + 1 :]
            elif name == "lua_pushvalue":
                _require(index == -2, "key copy index differs")
                lua.append(lua[index])
            elif name == "lua_insert":
                _require(index == -2, "key insertion index differs")
                at = len(lua) + index
                value = lua.pop()
                lua.insert(at, value)
            else:
                _require(
                    index == -5 and lua[index] == dest, "assignment destination differs"
                )
                _require(
                    lua[-3] == lua[-2] == items[cursor - 1][0]
                    and lua[-1] == items[cursor - 1][1],
                    "assignment key or value differs",
                )
                requests.append(
                    {
                        "iteration": cursor - 1,
                        "destination_role": "entry_destination",
                        "key": list(lua[-2]),
                        "value": list(lua[-1]),
                    }
                )
                del lua[-2:]
            calls.append(
                {
                    "site_rva": f"0x{pc:08x}",
                    "api": name,
                    "callee_esp_delta": sp - entry,
                    "arguments": argv,
                    "lua_top_before": before,
                    "lua_top_after": len(lua),
                }
            )
            regs["esp"] += 4
            regs.update(eax=eax, ecx=0x98765432, edx=0xABCDEF01)
            zf = None
            memory = {a: v for a, v in memory.items() if a in protected}
        elif op == "ret":
            _require(regs["esp"] in memory, "unproved native return")
            target = memory[regs["esp"]]
            regs["esp"] += 4
            break
        else:
            raise AssignmentError("unsupported model operation")
        pc = nxt
    else:
        raise AssignmentError("finite transcript failed to return")
    _require(
        lua == original and cursor == len(items), "normal Lua stack relation differs"
    )
    _require(
        [r["iteration"] for r in requests] == expected["assignment_iteration_indices"],
        "independent assignment predicate differs",
    )
    _require(
        regs["eax"] == 0 and regs["esp"] == entry + 4 and target == 0x30303030,
        "normal native return differs",
    )
    _require(
        all(regs[r] == initial[r] for r in expected["preserved_registers"]),
        "nonvolatile restoration differs",
    )
    offsets = [-12, -20] + [v for c in key_classes for v in ITERATION_CALL_OFFSETS[c]]
    _require(
        [c["callee_esp_delta"] for c in calls] == offsets
        and len(calls) == expected["api_calls"],
        "independent call-stack relation differs",
    )
    return {
        "input": {
            "alignment": alignment,
            "prefix_length": prefix_length,
            "key_classes": key_classes,
            "volatile_eax": volatile_eax,
        },
        "outcome": expected,
        "requests": requests,
        "calls": calls,
        "trace_rvas": [f"0x{r:08x}" for r in trace],
        "loop_invariants": invariants,
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
        [r.address - BASE for r in rows] == ORDER, "exact instruction points differ"
    )
    for r in rows:
        args = []
        for a in r.operands:
            if a.type == x86.X86_OP_REG:
                args.append(("reg", r.reg_name(a.reg)))
            elif a.type == x86.X86_OP_IMM:
                args.append(("imm", a.imm))
            elif a.type == x86.X86_OP_MEM:
                _require(
                    not a.mem.index and not a.mem.segment, "unexpected indexed memory"
                )
                args.append(
                    ("address", r.reg_name(a.mem.base), a.mem.disp)
                    if a.mem.base
                    else ("mem", a.mem.disp)
                )
            else:
                raise AssignmentError("unexpected operand")
        pc = r.address - BASE
        _require(
            (r.mnemonic, *args) == OPS[pc]
            and r.size == SIZES[pc]
            and all(a.size == 4 for a in r.operands),
            "exact operation grammar differs",
        )


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    rows = _decode_body(data, image, sources["program_facts"], START)
    _grammar(rows)
    points = [_point(r) for r in rows]
    chain = sources["chain"]
    body = chain["function_bodies"][2]
    cfg = chain["control_flow_graphs"][2]
    _require(
        points == [{k: n[k] for k in ("rva", "size", "sha256")} for n in cfg["nodes"]],
        "complete source points differ",
    )
    bodyhash = hashlib.sha256(b"".join(bytes(r.bytes) for r in rows)).hexdigest()
    _require(
        bodyhash == body["body_sha256"] and body["body_size"] == 180,
        "whole source body differs",
    )
    imports = []
    for slot, name in sorted(IMPORTS.items()):
        matches = [r for r in image.imports() if r["iat_rva"] == f"0x{slot:08x}"]
        _require(
            len(matches) == 1
            and matches[0]["name"] == name
            and matches[0]["library"].lower() == "lua5.1.dll"
            and matches[0]["ordinal"] is None,
            "fresh import binding differs",
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
            "census binding differs",
        )
        imports.append(
            {
                "metadata": matches[0],
                "iat_slot": _witness(image, slot, 4),
                "name_metadata_only": True,
            }
        )
    fresh = []
    staged = []
    for r in rows:
        pc = r.address - BASE
        if pc in CALLS:
            slot = CALLS[pc]
            name = IMPORTS[slot]
            if OPS[pc][1][0] == "mem":
                fresh.append(
                    {
                        "call_form": "x86_absolute_iat_indirect_call_ff15",
                        "call_rva": f"0x{pc:08x}",
                        "iat_rva": f"0x{slot:08x}",
                        "import_name": name,
                        "instruction_sha256": _point(r)["sha256"],
                        "instruction_size": r.size,
                        "library": "lua5.1.dll",
                    }
                )
            else:
                staged.append(
                    {
                        "point": _point(r),
                        "register": OPS[pc][1][1],
                        "iat_rva": f"0x{slot:08x}",
                        "api": name,
                    }
                )
    _require(fresh == body["direct_lua_calls"], "direct source calls differ")
    for audit in body["staged_lua_dispatches"]:
        selected = [r for r in staged if r["register"] == audit["register"]]
        _require(
            [r["point"] for r in selected] == [s["call"] for s in audit["call_sites"]]
            and all(
                r["iat_rva"] == audit["iat_rva"] and r["api"] == audit["api_name"]
                for r in selected
            ),
            "staged source call joins differ",
        )
    literals = []
    for ref in chain["literals"][1:]:
        rva = int(ref["rva"], 16)
        _require(
            rva in LITERALS and ref["text"] == LITERALS[rva], "literal metadata differs"
        )
        witness = _witness(image, rva, len(ref["text"]) + 1)
        _require(
            witness["sha256"] == ref["nul_terminated_bytes_sha256"],
            "literal bytes witness differs",
        )
        literals.append({"witness": witness, "text": ref["text"]})
    transcripts = [
        list(t)
        for n in range(4)
        for t in itertools.product(("init", "finalize", "other"), repeat=n)
    ]
    cases = [
        model_case(a, p, t, v)
        for a in range(16)
        for p in (0, 2)
        for t in transcripts
        for v in (0, 0xFFFFFFFF)
    ]
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(union == [p["rva"] for p in points], "model union differs")
    controls = []
    for name, pc, replacement in [
        ("wrong_assignment_index", 0x2EC0E4, ("push", ("imm", -4))),
        ("wrong_iterator_cleanup", 0x2EC09A, ("push", ("imm", -2))),
        ("wrong_native_cleanup", 0x2EC0ED, ("add", ("reg", "esp"), ("imm", 24))),
    ]:
        actions = dict(OPS)
        actions[pc] = replacement
        try:
            model_case(0, 0, ["init", "finalize", "other"], 0xFFFFFFFF, actions)
        except AssignmentError:
            controls.append({"name": name, "rejected": True})
        else:
            raise AssignmentError("semantic mutation accepted")
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "body": {
            "entry_rva": f"0x{START:08x}",
            "exclusive_end_rva": f"0x{END:08x}",
            "bytes": 180,
            "nodes": 71,
            "sha256": bodyhash,
            "points": points,
        },
        "imports": imports,
        "direct_lua_calls": fresh,
        "staged_lua_calls": staged,
        "literals": literals,
        "call_summary": call_summary_spec(),
        "loop_invariant": loop_invariant_spec(),
        "iteration_partitions": [
            iteration_spec(c) for c in ("init", "finalize", "other")
        ],
        "matrix": {
            "native_alignments": list(range(16)),
            "lua_prefix_lengths": [0, 2],
            "key_class_transcripts": transcripts,
            "volatile_eax": [0, 0xFFFFFFFF],
        },
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
        },
        "summary": {
            "cases": len(cases),
            "finite_transcripts": len(transcripts),
            "static_bytes": 180,
            "static_nodes": 71,
            "modeled_nodes": len(union),
            "direct_import_sites": 8,
            "staged_import_sites": 6,
            "unique_imports": 8,
            "actual_import_executions": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "conditional_exact_integer_and_abstract_Lua_loop_model",
            "semantic_basis": "Lua 5.1 reference manual C API effects under declared normal-return summaries",
            "finite_domain": "All three key classes at lengths zero through three, with separate loop invariant for any finite valid transcript",
            "not_claimed": [
                "Actual game or Lua execution, complete class identity or caller semantics",
                "Raw assignment, preserved destination contents, source immutability or predetermined traversal order",
                "Arbitrary source mutation remains valid for next, unconditional exhaustion, or absence of errors and nonlocal exits",
                "ABI validity of every synthetic stack residue, hardware faults or full game recreation",
                "Atlas accounting promotion or rerun of upstream matrices",
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
            _canonical_sha256(evidence) == SEALED_SHA256,
            "sealed assignment receipt differs",
        )
        _require(
            evidence["source_receipts"] == ids
            and evidence["call_summary"] == call_summary_spec()
            and evidence["loop_invariant"] == loop_invariant_spec(),
            "assignment specification differs",
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
            "exact assignment receipt differs",
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
