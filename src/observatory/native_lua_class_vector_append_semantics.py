"""Conditional exact append slice with ordered overlap-aware word copies."""

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

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_class_vector_append_semantics"
SEALED_SHA256 = "d17dc4796b23572e79a65784de0cc689a0f333005420997461a183c5a022a93c"
START, END, GROWTH = 0x2EB1BB, 0x2EB21A, 0x2EB620
SOURCE_PINS = {
    "chain": (
        "pe_native_lua_class_return_helper_chain",
        "33ad87a98131700dce12bd34a7febea3159b6f461710f0b8296d95ded1b37095",
    ),
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
}


# Memory grammar encodes base, index, scale, displacement. Never published as disassembly.
def R(name):
    return ("reg", name)


def I(value):
    return ("imm", value)


def M(base, offset=0, index=None, scale=1):
    return ("mem", base, index, scale, offset)


OPS = {
    0x2EB1BB: ("mov", R("esi"), M("ebp", -12)),
    0x2EB1BE: ("mov", R("eax"), M("esi", 8)),
    0x2EB1C1: ("cmp", R("edi"), R("eax")),
    0x2EB1C3: ("jae", I(BASE + 0x2EB1F7)),
    0x2EB1C5: ("mov", R("ecx"), M("esi", 4)),
    0x2EB1C8: ("cmp", R("ecx"), R("edi")),
    0x2EB1CA: ("ja", I(BASE + 0x2EB1F7)),
    0x2EB1CC: ("sub", R("edi"), R("ecx")),
    0x2EB1CE: ("sar", R("edi"), I(3)),
    0x2EB1D1: ("cmp", R("eax"), M("esi", 12)),
    0x2EB1D4: ("jne", I(BASE + 0x2EB1DF)),
    0x2EB1D6: ("push", R("ecx")),
    0x2EB1D7: ("lea", R("ecx"), M("esi", 4)),
    0x2EB1DA: ("call", I(BASE + GROWTH)),
    0x2EB1DF: ("mov", R("edx"), M("esi", 8)),
    0x2EB1E2: ("test", R("edx"), R("edx")),
    0x2EB1E4: ("je", I(BASE + 0x2EB216)),
    0x2EB1E6: ("mov", R("ecx"), M("esi", 4)),
    0x2EB1E9: ("mov", R("eax"), M("ecx", 0, "edi", 8)),
    0x2EB1EC: ("mov", M("edx"), R("eax")),
    0x2EB1EE: ("mov", R("eax"), M("ecx", 4, "edi", 8)),
    0x2EB1F2: ("mov", M("edx", 4), R("eax")),
    0x2EB1F5: ("jmp", I(BASE + 0x2EB216)),
    0x2EB1F7: ("cmp", R("eax"), M("esi", 12)),
    0x2EB1FA: ("jne", I(BASE + 0x2EB205)),
    0x2EB1FC: ("push", R("ecx")),
    0x2EB1FD: ("lea", R("ecx"), M("esi", 4)),
    0x2EB200: ("call", I(BASE + GROWTH)),
    0x2EB205: ("mov", R("ecx"), M("esi", 8)),
    0x2EB208: ("test", R("ecx"), R("ecx")),
    0x2EB20A: ("je", I(BASE + 0x2EB216)),
    0x2EB20C: ("mov", R("eax"), M("edi")),
    0x2EB20E: ("mov", M("ecx"), R("eax")),
    0x2EB210: ("mov", R("eax"), M("edi", 4)),
    0x2EB213: ("mov", M("ecx", 4), R("eax")),
    0x2EB216: ("add", M("esi", 8), I(8)),
}
ORDER = list(OPS)
SIZES = {
    p: (ORDER[i + 1] if i + 1 < len(ORDER) else END) - p for i, p in enumerate(ORDER)
}
U32 = 0xFFFFFFFF
PAYLOAD = 0x10000000
PROFILES = [
    "internal_first",
    "internal_second",
    "internal_unaligned",
    "internal_last_byte",
    "external_below",
    "external_at_end",
    "external_above",
    "external_forward_overlap",
    "null_destination",
    "growth_internal",
    "growth_unaligned",
    "growth_external",
    "growth_null",
]


class AppendError(RuntimeError):
    """An append witness, arithmetic relation, call summary or memory event differs."""


def _require(ok, message):
    if not ok:
        raise AppendError(message)


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)
    return value


def _signed(value):
    return value if value < 0x80000000 else value - 0x100000000


def _normalize(fn):
    try:
        return fn()
    except AppendError:
        raise
    except Exception as exc:
        raise AppendError(str(exc)) from exc


def append_spec(
    begin: int, end: int, capacity: int, argument: int, post_begin: int, post_end: int
) -> dict[str, Any]:
    for name, value in locals().copy().items():
        _u32(value, name)
    growth = end == capacity
    _require(
        growth or (post_begin == begin and post_end == end),
        "post layout changed without growth",
    )
    internal = begin <= argument < end
    delta = (argument - begin) & U32
    index = (_signed(delta) >> 3) if internal else None
    source = (post_begin + index * 8) & U32 if internal else argument
    return {
        "branch": "internal" if internal else "external",
        "growth_requested": growth,
        "signed_index": index,
        "source": source,
        "destination": post_end,
        "copy_words": 2 if post_end else 0,
        "end_after": (post_end + 8) & U32,
        "edi_after": index & U32 if internal else argument,
        "native_esp_delta": 0,
        "relocation_element_qualification": bool(
            internal and delta < 0x80000000 and delta % 8 == 0
        ),
        "qualification_scope": "Corresponding element relocation additionally requires valid aligned element layout, preserved old elements and mapped disjoint metadata",
    }


def ordered_copy_spec(
    initial: bytes, source_offset: int, destination_offset: int
) -> dict[str, Any]:
    _require(
        type(initial) is bytes and len(initial) <= 65536, "invalid initial byte buffer"
    )
    _require(
        type(source_offset) is int
        and type(destination_offset) is int
        and 0 <= source_offset <= len(initial) - 8
        and 0 <= destination_offset <= len(initial) - 8,
        "copy outside buffer",
    )
    out = bytearray(initial)
    events = []
    for displacement in (0, 4):
        a = source_offset + displacement
        b = destination_offset + displacement
        value = int.from_bytes(out[a : a + 4], "little")
        events.append({"access": "read", "offset": a, "width": 4, "value": value})
        out[b : b + 4] = value.to_bytes(4, "little")
        events.append({"access": "write", "offset": b, "width": 4, "value": value})
    return {"after": bytes(out), "events": events}


def growth_summary_spec() -> dict[str, Any]:
    return {
        "target_rva": "0x002eb620",
        "this_object_offset": 4,
        "pushed_argument_bytes": 4,
        "normal_return_stack_delta_from_callee_entry": 8,
        "native_entry_frame_offset": -40,
        "native_return_frame_offset": -32,
        "preserved_registers": ["ebx", "esi", "edi", "ebp"],
        "volatile_outputs": ["eax", "ecx", "edx", "eflags"],
        "live_layout_fields": ["begin", "end", "capacity"],
        "pushed_word_sources": {
            "internal": "loaded_begin",
            "external_argument_below_begin": "loaded_begin",
            "external_argument_at_or_above_end": "entry_ecx",
        },
        "premises": [
            "Growth returns normally with its RET4 convention; imported allocation and nested callees are not executed",
            "The object identity, frame local object pointer, native saved words and ABI nonvolatiles survive",
            "Post-growth begin and end and mapped payload bytes are declared summary outputs",
            "Relocated old element contents are preserved only for vectors explicitly declaring that growth premise",
            "External source words remain readable when copied; pointer classification alone does not establish their lifetime",
            "The pushed word has no observable effect under the summary; the direct growth body has no explicit stack-argument memory operand",
        ],
        "not_claimed": [
            "Actual growth or allocator semantics, allocation success, exception behavior or full growth-body implementation"
        ],
    }


def case_vector(profile: str, alignment: int, seed: int) -> dict[str, int | str]:
    _require(type(profile) is str and profile in PROFILES, "invalid profile")
    _require(
        type(alignment) is int
        and 0 <= alignment < 16
        and type(seed) is int
        and seed in (0, 1),
        "invalid finite vector",
    )
    b, e = PAYLOAD + 64, PAYLOAD + 96
    c = e + 32
    a = b
    if profile == "internal_second":
        a = b + 8
    elif profile == "internal_unaligned":
        a = b + 3
    elif profile == "internal_last_byte":
        a = e - 1
    elif profile == "external_below":
        a = b - 8
    elif profile == "external_at_end":
        a = e
    elif profile == "external_above":
        a = e + 8
    elif profile == "external_forward_overlap":
        b = e + 16
        a = e - 4
    elif profile == "null_destination":
        b = e = 0
        c = 8
        a = PAYLOAD + 224
    elif profile.startswith("growth_"):
        c = e
        a = (
            b + 8
            if profile == "growth_internal"
            else (
                b + 3
                if profile == "growth_unaligned"
                else PAYLOAD + 224 if profile == "growth_external" else b
            )
        )
    pb, pe = (b + 128, e + 128) if c == e else (b, e)
    if profile == "growth_null":
        pb = pe = 0
    return {
        "profile": profile,
        "alignment": alignment,
        "seed": seed,
        "begin": b,
        "end": e,
        "capacity": c,
        "argument": a,
        "post_begin": pb,
        "post_end": pe,
    }


def model_case(
    profile: str, alignment: int, seed: int, actions: Mapping[int, tuple] | None = None
) -> dict[str, Any]:
    vector = case_vector(profile, alignment, seed)
    spec = append_spec(
        *(
            vector[k]
            for k in ("begin", "end", "capacity", "argument", "post_begin", "post_end")
        )
    )
    actions = OPS if actions is None else actions
    _require(
        isinstance(actions, Mapping) and set(actions) == set(OPS),
        "operation sites differ",
    )
    frame = 0x02002000 + alignment
    obj = 0x03001000
    initial = {
        "eax": 0x11223344,
        "ecx": 0x77665544,
        "edx": 0x12345678,
        "ebx": 0x22334455,
        "esi": 0x33445566,
        "edi": vector["argument"],
        "ebp": frame,
        "esp": frame - 32,
    }
    regs = dict(initial)
    memory = {}
    events = []
    trace = []
    calls = []
    unreadable = set()
    payload = bytes((i * 37 + seed * 19) & 255 for i in range(512))
    oracle = bytearray(payload)
    for i, v in enumerate(payload):
        memory[PAYLOAD + i] = v

    def raw_write(address, value):
        for i, v in enumerate((value & U32).to_bytes(4, "little")):
            memory[(address + i) & U32] = v

    for address, value in (
        (frame - 12, obj),
        (frame - 24, initial["ebx"]),
        (frame - 28, initial["esi"]),
        (frame - 32, initial["edi"]),
        (obj + 4, vector["begin"]),
        (obj + 8, vector["end"]),
        (obj + 12, vector["capacity"]),
    ):
        raw_write(address, value)
    if spec["growth_requested"] and vector["post_begin"]:
        lo = vector["begin"] - PAYLOAD
        hi = vector["end"] - PAYLOAD
        new = vector["post_begin"] - PAYLOAD
        oracle[new : new + hi - lo] = payload[lo:hi]
    before_copy = bytes(oracle)
    expected_copy = (
        None
        if not spec["copy_words"]
        else ordered_copy_spec(
            before_copy, spec["source"] - PAYLOAD, spec["destination"] - PAYLOAD
        )
    )
    expected_payload = before_copy if expected_copy is None else expected_copy["after"]
    pc = START
    comparison = None

    def address(arg):
        _, base, index, scale, disp = arg
        return (
            (regs[base] if base else 0) + (regs[index] * scale if index else 0) + disp
        ) & U32

    def memread(a):
        _require(
            all(
                (a + i) & U32 in memory and (a + i) & U32 not in unreadable
                for i in range(4)
            ),
            "unproved memory read",
        )
        value = int.from_bytes(bytes(memory[(a + i) & U32] for i in range(4)), "little")
        events.append(
            {
                "site_rva": f"0x{pc:08x}",
                "access": "read",
                "address": a,
                "width": 4,
                "value": value,
            }
        )
        return value

    def memwrite(a, value):
        _require(
            all((a + i) & U32 in memory for i in range(4)), "unproved memory write"
        )
        raw_write(a, value)
        events.append(
            {
                "site_rva": f"0x{pc:08x}",
                "access": "write",
                "address": a,
                "width": 4,
                "value": value & U32,
            }
        )

    def read(arg):
        return (
            regs[arg[1]]
            if arg[0] == "reg"
            else arg[1] & U32 if arg[0] == "imm" else memread(address(arg))
        )

    def write(arg, value):
        if arg[0] == "reg":
            regs[arg[1]] = value & U32
        else:
            memwrite(address(arg), value)

    for _ in range(50):
        if pc == END:
            break
        _require(pc in actions, "append escaped slice")
        trace.append(pc)
        op, *args = actions[pc]
        nxt = pc + SIZES[pc]
        if op == "mov":
            write(args[0], read(args[1]))
        elif op == "lea":
            write(args[0], address(args[1]))
        elif op == "sub":
            write(args[0], read(args[0]) - read(args[1]))
            comparison = None
        elif op == "sar":
            write(args[0], _signed(read(args[0])) >> (read(args[1]) & 31))
            comparison = None
        elif op == "cmp":
            comparison = (read(args[0]), read(args[1]))
        elif op == "test":
            comparison = (read(args[0]) & read(args[1]), 0)
        elif op in ("jae", "ja", "jne", "je"):
            _require(comparison is not None, "unproved branch flags")
            a, b = comparison
            taken = {"jae": a >= b, "ja": a > b, "jne": a != b, "je": a == b}[op]
            if taken:
                nxt = read(args[0]) - BASE
        elif op == "jmp":
            nxt = read(args[0]) - BASE
        elif op == "push":
            regs["esp"] -= 4
            raw_write(regs["esp"], read(args[0]))
        elif op == "call":
            _require(
                args[0] == I(BASE + GROWTH) and spec["growth_requested"],
                "unexpected growth call",
            )
            regs["esp"] -= 4
            raw_write(regs["esp"], BASE + nxt)
            _require(
                regs["esp"] == frame - 40 and regs["ecx"] == obj + 4,
                "growth native frame differs",
            )
            pushed = int.from_bytes(
                bytes(memory[frame - 36 + i] for i in range(4)), "little"
            )
            expected_arg = (
                initial["ecx"]
                if vector["argument"] >= vector["end"]
                else vector["begin"]
            )
            _require(pushed == expected_arg, "growth pushed word provenance differs")
            calls.append(
                {
                    "site_rva": f"0x{pc:08x}",
                    "callee_frame_offset": -40,
                    "this_object_offset": 4,
                    "pushed_word": pushed,
                }
            )
            raw_write(obj + 4, vector["post_begin"])
            raw_write(obj + 8, vector["post_end"])
            if vector["post_begin"]:
                lo = vector["begin"] - PAYLOAD
                hi = vector["end"] - PAYLOAD
                new = vector["post_begin"] - PAYLOAD
                for i, v in enumerate(payload[lo:hi]):
                    memory[PAYLOAD + new + i] = v
                unreadable.update(range(vector["begin"], vector["end"]))
            regs["esp"] += 8
            regs.update(eax=0xAABBCCDD, ecx=0x778899AA, edx=0x12341234)
            comparison = None
        elif op == "add":
            write(args[0], read(args[0]) + read(args[1]))
            comparison = None
        else:
            raise AppendError("unsupported operation")
        pc = nxt
    else:
        raise AppendError("append failed to reach exclusive boundary")
    actual_payload = bytes(memory[PAYLOAD + i] for i in range(512))
    _require(actual_payload == expected_payload, "ordered payload oracle differs")
    payload_events = [
        {
            "access": e["access"],
            "offset": e["address"] - PAYLOAD,
            "width": 4,
            "value": e["value"],
        }
        for e in events
        if PAYLOAD <= e["address"] < PAYLOAD + 512
    ]
    _require(
        payload_events == ([] if expected_copy is None else expected_copy["events"]),
        "ordered payload event oracle differs",
    )
    final_end = int.from_bytes(bytes(memory[obj + 8 + i] for i in range(4)), "little")
    for a, value in (
        (frame - 12, obj),
        (frame - 24, initial["ebx"]),
        (frame - 28, initial["esi"]),
        (frame - 32, initial["edi"]),
        (obj + 4, vector["post_begin"]),
        (obj + 12, vector["capacity"]),
    ):
        _require(
            int.from_bytes(bytes(memory[a + i] for i in range(4)), "little") == value,
            "protected frame or declared metadata differs",
        )
    _require(
        final_end == spec["end_after"]
        and regs["esp"] == frame - 32
        and regs["esi"] == obj
        and regs["edi"] == spec["edi_after"],
        "append boundary relation differs",
    )
    _require(
        regs["ebx"] == initial["ebx"]
        and regs["ebp"] == frame
        and len(calls) == int(spec["growth_requested"]),
        "preservation or growth count differs",
    )
    _require(
        events[-1]["access"] == "write"
        and events[-1]["address"] == obj + 8
        and events[-2]["access"] == "read"
        and events[-2]["address"] == obj + 8,
        "final end update order differs",
    )
    return {
        "input": vector,
        "outcome": spec,
        "trace_rvas": [f"0x{r:08x}" for r in trace],
        "events": events,
        "growth_calls": calls,
        "payload_after_sha256": hashlib.sha256(actual_payload).hexdigest(),
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
    _require([r.address - BASE for r in rows] == ORDER, "slice points differ")
    for r in rows:
        args = []
        for a in r.operands:
            if a.type == x86.X86_OP_REG:
                args.append(R(r.reg_name(a.reg)))
            elif a.type == x86.X86_OP_IMM:
                args.append(I(a.imm))
            elif a.type == x86.X86_OP_MEM:
                _require(not a.mem.segment, "unexpected segment override")
                args.append(
                    M(
                        r.reg_name(a.mem.base) if a.mem.base else None,
                        a.mem.disp,
                        r.reg_name(a.mem.index) if a.mem.index else None,
                        a.mem.scale,
                    )
                )
            else:
                raise AppendError("unexpected operand")
        _require(
            (r.mnemonic, *args) == OPS[r.address - BASE]
            and r.size == SIZES[r.address - BASE]
            and [a.size for a in r.operands]
            == ([4, 1] if r.address - BASE == 0x2EB1CE else [4] * len(r.operands)),
            "exact append grammar differs",
        )


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    owner = _decode_body(data, image, sources["program_facts"], 0x2EB140)
    rows = [r for r in owner if START <= r.address - BASE < END]
    _grammar(rows)
    chain = sources["chain"]
    body = chain["function_bodies"][0]
    cfg = chain["control_flow_graphs"][0]
    ownerpoints = [_point(r) for r in owner]
    _require(
        ownerpoints
        == [{k: n[k] for k in ("rva", "size", "sha256")} for n in cfg["nodes"]]
        and hashlib.sha256(b"".join(bytes(r.bytes) for r in owner)).hexdigest()
        == body["body_sha256"],
        "full source owner join differs",
    )
    growth = _decode_body(data, image, sources["program_facts"], GROWTH)
    ret = [r for r in growth if r.id == x86.X86_INS_RET]
    _require(
        len(growth) == 40
        and sum(r.size for r in growth) == 94
        and len(ret) == 1
        and ret[0].address - BASE == 0x2EB671
        and len(ret[0].operands) == 1
        and ret[0].operands[0].imm == 4,
        "growth return shape differs",
    )
    _require(
        all(
            not (
                a.type == x86.X86_OP_MEM
                and a.mem.base in (x86.X86_REG_ESP, x86.X86_REG_EBP)
            )
            for r in growth
            for a in r.operands
        ),
        "direct growth body addresses stack argument",
    )
    cases = [model_case(p, a, s) for p in PROFILES for a in range(16) for s in (0, 1)]
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(union == [_point(r)["rva"] for r in rows], "model union differs")
    controls = []
    for name, pc, replacement, profile in [
        ("wrong_element_shift", 0x2EB1CE, ("sar", R("edi"), I(2)), "growth_internal"),
        (
            "wrong_second_source_word",
            0x2EB210,
            ("mov", R("eax"), M("edi")),
            "external_above",
        ),
        (
            "wrong_end_increment",
            0x2EB216,
            ("add", M("esi", 8), I(4)),
            "null_destination",
        ),
    ]:
        changed = dict(OPS)
        changed[pc] = replacement
        try:
            model_case(profile, 0, 0, changed)
        except AppendError:
            controls.append({"name": name, "rejected": True})
        else:
            raise AppendError("semantic mutation accepted")
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "slice": {
            "entry_rva": f"0x{START:08x}",
            "exclusive_end_rva": f"0x{END:08x}",
            "bytes": 95,
            "nodes": 36,
            "sha256": hashlib.sha256(
                b"".join(bytes(r.bytes) for r in rows)
            ).hexdigest(),
            "points": [_point(r) for r in rows],
        },
        "owner_join": {
            "entry_rva": "0x002eb140",
            "bytes": 237,
            "nodes": 87,
            "sha256": body["body_sha256"],
            "points_sha256": _canonical_sha256(ownerpoints),
        },
        "growth_static_witness": {
            "entry_rva": f"0x{GROWTH:08x}",
            "bytes": 94,
            "nodes": 40,
            "sha256": hashlib.sha256(
                b"".join(bytes(r.bytes) for r in growth)
            ).hexdigest(),
            "points": [_point(r) for r in growth],
            "return_point": _point(ret[0]),
            "explicit_stack_argument_memory_operands": 0,
            "implementation_modeled": False,
        },
        "growth_summary": growth_summary_spec(),
        "matrix": {
            "profiles": PROFILES,
            "frame_alignments": list(range(16)),
            "payload_seeds": [0, 1],
        },
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
        },
        "summary": {
            "cases": len(cases),
            "slice_bytes": 95,
            "slice_nodes": 36,
            "modeled_nodes": len(union),
            "modeled_growth_calls": sum(len(c["growth_calls"]) for c in cases),
            "actual_growth_calls": 0,
            "actual_import_executions": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "conditional_exact_integer_and_ordered_memory_append_slice",
            "entry_premises": [
                "Owner frame is established with slice ESP at frame minus32 and local object pointer at frame minus12",
                "EDI holds the source argument and object fields at offsets4,8,12 give begin,end,capacity",
                "Frame and object metadata do not overlap copied payload or modeled growth buffers; every accessed word is mapped",
            ],
            "integer_domain": "Unsigned32 range classification, signed arithmetic shift of wrapped difference and modulo32 effective addresses and end update",
            "event_policy": "Events record explicit data operands; growth argument and return-word construction are represented separately by the growth call frame observations",
            "copy_order": [
                "read_first_word",
                "write_first_word",
                "read_second_word",
                "write_second_word",
                "read_current_end",
                "write_end_plus_eight",
            ],
            "null_destination": "Skips both payload words but still increments the end field from zero to eight",
            "not_claimed": [
                "Alignment, valid vector geometry, available capacity or memory safety from pointer classification alone",
                "A snapshot copy when words overlap; the second source read may observe the first write",
                "Actual growth, allocator or full owner semantics, tree insertion, cookie epilogue or Lua execution",
                "Validity of external source after arbitrary growth; each read needs its declared mapped-memory premise",
                "Unconditional alias safety or atlas accounting promotion",
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
            "sealed append receipt differs",
        )
        _require(
            evidence["source_receipts"] == ids
            and evidence["growth_summary"] == growth_summary_spec(),
            "append specification differs",
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
            "exact append receipt differs",
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
