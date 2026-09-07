"""Conditional resize owner protocol with explicit normal-return child summaries."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone.x86_const as x86
from src.observatory import native_lua_vector_allocation_semantics as allocation
from src.observatory import native_vector_deallocation_semantics as deallocation
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

ANALYSIS_KIND = "pe_native_vector_resize_semantics"
SEALED_SHA256 = "b36551ea1b1f943b9f0d1b5802c9239a136feadc2c52443109d8e48669a89f89"
SOURCE_PINS = {
    "program_facts": allocation.SOURCE_PINS["program_facts"],
    "allocation_semantics": (allocation.ANALYSIS_KIND, allocation.SEALED_SHA256),
    "deallocation_semantics": (deallocation.ANALYSIS_KIND, deallocation.SEALED_SHA256),
}
START, END, U32 = 0x2EB680, 0x2EB6E5, 0xFFFFFFFF
CALLS = {
    0x2EB690: ("allocation", 0x8A920, 4),
    0x2EB6A1: ("copy", 0x36E580, 0),
    0x2EB6C3: ("deallocation", 0x7800, 0),
}


def R(name):
    return ("reg", name)


def I(value):
    return ("imm", value)


def M(base, offset=0, index=None, scale=1):
    return ("mem", base, offset, index, scale)


OPS = {
    0x2EB680: ("push", R("ebp")),
    0x2EB681: ("mov", R("ebp"), R("esp")),
    0x2EB683: ("push", R("ecx")),
    0x2EB684: ("mov", R("eax"), M("ebp", 8)),
    0x2EB687: ("push", R("ebx")),
    0x2EB688: ("push", R("esi")),
    0x2EB689: ("push", R("edi")),
    0x2EB68A: ("push", R("eax")),
    0x2EB68B: ("mov", R("esi"), R("ecx")),
    0x2EB68D: ("mov", M("ebp", -4), R("eax")),
    0x2EB690: ("call", I(BASE + 0x8A920)),
    0x2EB695: ("mov", R("edx"), M("esi")),
    0x2EB697: ("mov", R("edi"), R("eax")),
    0x2EB699: ("mov", R("ecx"), M("esi", 4)),
    0x2EB69C: ("sub", R("ecx"), R("edx")),
    0x2EB69E: ("push", R("ecx")),
    0x2EB69F: ("push", R("edx")),
    0x2EB6A0: ("push", R("edi")),
    0x2EB6A1: ("call", I(BASE + 0x36E580)),
    0x2EB6A6: ("mov", R("ecx"), M("esi")),
    0x2EB6A8: ("add", R("esp"), I(12)),
    0x2EB6AB: ("mov", R("ebx"), M("esi", 4)),
    0x2EB6AE: ("sub", R("ebx"), R("ecx")),
    0x2EB6B0: ("sar", R("ebx"), I(3)),
    0x2EB6B3: ("test", R("ecx"), R("ecx")),
    0x2EB6B5: ("je", I(BASE + 0x2EB6CB)),
    0x2EB6B7: ("mov", R("eax"), M("esi", 8)),
    0x2EB6BA: ("sub", R("eax"), R("ecx")),
    0x2EB6BC: ("push", I(8)),
    0x2EB6BE: ("sar", R("eax"), I(3)),
    0x2EB6C1: ("push", R("eax")),
    0x2EB6C2: ("push", R("ecx")),
    0x2EB6C3: ("call", I(BASE + 0x7800)),
    0x2EB6C8: ("add", R("esp"), I(12)),
    0x2EB6CB: ("mov", R("eax"), M("ebp", -4)),
    0x2EB6CE: ("lea", R("eax"), M("edi", 0, "eax", 8)),
    0x2EB6D1: ("mov", M("esi", 8), R("eax")),
    0x2EB6D4: ("lea", R("eax"), M("edi", 0, "ebx", 8)),
    0x2EB6D7: ("mov", M("esi", 4), R("eax")),
    0x2EB6DA: ("mov", M("esi"), R("edi")),
    0x2EB6DC: ("pop", R("edi")),
    0x2EB6DD: ("pop", R("esi")),
    0x2EB6DE: ("pop", R("ebx")),
    0x2EB6DF: ("mov", R("esp"), R("ebp")),
    0x2EB6E1: ("pop", R("ebp")),
    0x2EB6E2: ("ret", I(4)),
}
ORDER = list(OPS)
SIZES = {
    p: (ORDER[i + 1] if i + 1 < len(ORDER) else END) - p for i, p in enumerate(ORDER)
}


class ResizeError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ResizeError(message)


def _u32(value):
    _require(type(value) is int and 0 <= value <= U32, "invalid unsigned input")
    return value


def _sar3(value):
    return ((value if value < 2**31 else value - 2**32) // 8) & U32


def resize_spec(begin, end, capacity, requested, new_pointer):
    for value in (begin, end, capacity, requested, new_pointer):
        _u32(value)
    length = (end - begin) & U32
    size = _sar3(length)
    return {
        "copy_arguments": [new_pointer, begin, length],
        "deallocation_arguments": (
            [begin, _sar3((capacity - begin) & U32), 8] if begin else None
        ),
        "new_begin": new_pointer,
        "new_end": (new_pointer + 8 * size) & U32,
        "new_capacity": (new_pointer + 8 * requested) & U32,
        "size_word": size,
        "write_order": ["capacity", "end", "begin"],
    }


def ordinary_geometry_spec(begin, end, capacity, requested, new_pointer):
    result = resize_spec(begin, end, capacity, requested, new_pointer)
    _require(
        begin <= end <= capacity
        and (end - begin) % 8 == 0
        and (capacity - begin) % 8 == 0,
        "ordinary geometry requires ordered eight-byte spans",
    )
    _require(
        capacity - begin < 2**31, "ordinary geometry requires nonnegative signed spans"
    )
    _require(begin != 0 or end == capacity == 0, "null old storage must be empty")
    _require(
        requested >= (end - begin) // 8 and requested <= 0x1FFFFFFF,
        "requested storage cannot truncate live elements or overflow byte count",
    )
    _require(
        new_pointer + 8 * requested <= U32 and (requested == 0 or new_pointer > 0),
        "new storage must have a positive nonwrapping payload extent",
    )
    return {
        **result,
        "copy_bytes": end - begin,
        "preserved_elements": (end - begin) // 8,
    }


def _arith(left, right, add=False):
    value = (left + right if add else left - right) & U32
    return {
        "cf": int(left + right > U32) if add else int(left < right),
        "pf": int((value & 255).bit_count() % 2 == 0),
        "af": ((left ^ right ^ value) >> 4) & 1,
        "zf": int(value == 0),
        "sf": value >> 31,
        "of": ((~(left ^ right) if add else left ^ right) & (left ^ value)) >> 31 & 1,
    }


def _test(value):
    return {
        "cf": 0,
        "pf": int((value & 255).bit_count() % 2 == 0),
        "af": None,
        "zf": int(value == 0),
        "sf": value >> 31,
        "of": 0,
    }


def case_fixture(
    begin,
    end,
    capacity,
    requested,
    new_pointer,
    frame_alignment=0,
    seed=1,
    object_address=0x10000000,
):
    resize_spec(begin, end, capacity, requested, new_pointer)
    _u32(seed)
    _u32(object_address)
    _require(
        type(frame_alignment) is int and 0 <= frame_alignment < 16, "invalid alignment"
    )
    stack = 0x30001000 + frame_alignment
    _require(
        object_address + 12 <= 2**32
        and (object_address + 12 <= stack - 40 or object_address >= stack + 16),
        "object overlaps protected frame or wraps",
    )
    regs = {
        r: (0xA1000000 + i * 0x10101 + seed) & U32
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs.update(ecx=object_address, esp=stack)
    memory = {stack + i: (0xBABE0000 + i + seed) & U32 for i in range(-40, 16, 4)}
    memory.update(
        {
            stack + 4: requested,
            object_address: begin,
            object_address + 4: end,
            object_address + 8: capacity,
        }
    )
    return {
        "stack": stack,
        "object": object_address,
        "registers": regs,
        "memory": memory,
    }


def oracle_state(
    begin,
    end,
    capacity,
    requested,
    new_pointer,
    frame_alignment=0,
    seed=1,
    object_address=0x10000000,
):
    """Frame equations and final words, independent of graph dispatch."""
    fixture = case_fixture(
        begin,
        end,
        capacity,
        requested,
        new_pointer,
        frame_alignment,
        seed,
        object_address,
    )
    s, obj = fixture["stack"], fixture["object"]
    initial = fixture["registers"]
    memory = dict(fixture["memory"])
    truncated = ((end - begin) & U32) & ~7
    new_end = (new_pointer + truncated) & U32
    new_cap = (new_pointer + 8 * requested) & U32
    memory.update(
        {
            s - 4: initial["ebp"],
            s - 8: requested,
            s - 12: initial["ebx"],
            s - 16: initial["esi"],
            s - 20: initial["edi"],
            s - 32: begin if begin else new_pointer,
            s - 28: _sar3((capacity - begin) & U32) if begin else begin,
            s - 24: 8 if begin else (end - begin) & U32,
            s - 36: BASE + (0x2EB6C8 if begin else 0x2EB6A6),
            obj: new_pointer,
            obj + 4: new_end,
            obj + 8: new_cap,
        }
    )
    regs = dict(initial)
    regs.update(
        eax=new_end,
        ecx=0xA0000003 if begin else 0,
        edx=0xB0000003 if begin else 0xB0000002,
        esp=s + 8,
    )
    return {
        "registers": regs,
        "memory": memory,
        "flags": _arith(s - 32, 12, True) if begin else _test(0),
    }


def model_case(
    begin,
    end,
    capacity,
    requested,
    new_pointer,
    frame_alignment=0,
    seed=1,
    object_address=0x10000000,
    ops=None,
):
    spec = resize_spec(begin, end, capacity, requested, new_pointer)
    fixture = case_fixture(
        begin,
        end,
        capacity,
        requested,
        new_pointer,
        frame_alignment,
        seed,
        object_address,
    )
    regs, memory = dict(fixture["registers"]), dict(fixture["memory"])
    events, trace, summaries = [], [], []
    pc, flags = START, None
    operations = OPS if ops is None else ops

    def address(arg):
        return (regs[arg[1]] + arg[2] + (regs[arg[3]] * arg[4] if arg[3] else 0)) & U32

    def load(addr):
        _require(addr in memory, "unmapped native read")
        value = memory[addr]
        events.append({"kind": "read", "address": addr, "width": 4, "value": value})
        return value

    def store(addr, value):
        _require(addr in memory, "unmapped native write")
        memory[addr] = value
        events.append({"kind": "write", "address": addr, "width": 4, "value": value})

    def read(arg):
        return (
            regs[arg[1]]
            if arg[0] == "reg"
            else arg[1] & U32 if arg[0] == "imm" else load(address(arg))
        )

    def write(arg, value):
        if arg[0] == "reg":
            regs[arg[1]] = value & U32
        else:
            store(address(arg), value & U32)

    def push(value):
        regs["esp"] -= 4
        store(regs["esp"], value)

    while pc != -1:
        _require(pc in operations and len(trace) < 80, "unexpected resize control path")
        trace.append(f"0x{pc:08x}")
        op, *args = operations[pc]
        nxt = pc + SIZES[pc]
        if op == "push":
            push(read(args[0]))
        elif op == "pop":
            write(args[0], load(regs["esp"]))
            regs["esp"] += 4
        elif op == "mov":
            write(args[0], read(args[1]))
        elif op == "lea":
            write(args[0], address(args[1]))
        elif op in ("sub", "add"):
            left, right = read(args[0]), read(args[1])
            flags = _arith(left, right, op == "add")
            write(args[0], left + right if op == "add" else left - right)
        elif op == "sar":
            _require(read(args[1]) == 3, "unexpected shift width")
            write(args[0], _sar3(read(args[0])))
            flags = None
        elif op == "test":
            flags = _test(read(args[0]) & read(args[1]))
        elif op == "je":
            if flags["zf"]:
                nxt = read(args[0]) - BASE
        elif op == "call":
            role, target, cleanup = CALLS[pc]
            _require(read(args[0]) == BASE + target, "child target changed")
            expected_args = (
                [requested]
                if role == "allocation"
                else (
                    spec["copy_arguments"]
                    if role == "copy"
                    else spec["deallocation_arguments"]
                )
            )
            _require(
                expected_args is not None
                and [memory[regs["esp"] + 4 * i] for i in range(len(expected_args))]
                == expected_args,
                "child argument relation differs",
            )
            push(BASE + nxt)
            ordinal = {"allocation": 1, "copy": 2, "deallocation": 3}[role]
            summaries.append(
                {
                    "role": role,
                    "entry_esp": regs["esp"],
                    "arguments": expected_args,
                    "continuation": BASE + nxt,
                    "callee_argument_cleanup": cleanup,
                }
            )
            regs.update(
                eax=new_pointer if ordinal == 1 else 0xC0000000 + ordinal,
                ecx=0xA0000000 + ordinal,
                edx=0xB0000000 + ordinal,
            )
            regs["esp"] += 4 + cleanup
            flags = {"cf": 0, "pf": 1, "af": 0, "zf": 1, "sf": 0, "of": 0}
        elif op == "ret":
            _require(
                load(regs["esp"]) == fixture["memory"][fixture["stack"]],
                "caller continuation changed",
            )
            regs["esp"] += 4 + read(args[0])
            nxt = -1
        else:
            raise ResizeError("unsupported graph operation")
        pc = nxt
    expected = oracle_state(
        begin,
        end,
        capacity,
        requested,
        new_pointer,
        frame_alignment,
        seed,
        object_address,
    )
    _require(
        regs == expected["registers"]
        and flags == expected["flags"]
        and memory == expected["memory"],
        "independent resize frame or final-state relation differs",
    )
    writes = [
        e
        for e in events
        if e["kind"] == "write"
        and fixture["object"] <= e["address"] < fixture["object"] + 12
    ]
    _require(
        [e["address"] - fixture["object"] for e in writes] == [8, 4, 0],
        "metadata publication order differs",
    )
    return {
        "inputs": dict(
            begin=begin,
            end=end,
            capacity=capacity,
            requested=requested,
            new_pointer=new_pointer,
            frame_alignment=frame_alignment,
            seed=seed,
            object_address=object_address,
        ),
        "registers": regs,
        "flags": flags,
        "memory": [{"address": a, "value": v} for a, v in sorted(memory.items())],
        "events": events,
        "trace_rvas": trace,
        "summaries": summaries,
        "specification": spec,
    }


def case_inputs():
    ordinary = [(0, 0, 0, n, p) for n in (0, 1, 8) for p in (0, 0x20000000)]
    ordinary += [
        (0x10001000, 0x10001000 + 8 * s, 0x10001000 + 8 * c, n, 0x20000000 + a)
        for s, c, n in (
            (0, 0, 1),
            (0, 4, 8),
            (1, 1, 2),
            (3, 4, 6),
            (511, 512, 768),
            (512, 512, 768),
        )
        for a in (0, 1, 31)
    ]
    machine = [
        (b, (b + d) & U32, (b + c) & U32, n, p)
        for b in (0, 0x10001000, 0xFFFFFFF0)
        for d, c in (
            (1, 7),
            (7, 8),
            (0x7FFFFFFF, 0x80000000),
            (0x80000000, 0xFFFFFFFF),
            (0xFFFFFFF9, 0xFFFFFFFF),
        )
        for n, p in ((0, 0), (U32, 0xFFFFFFF8))
    ]
    return sorted(set(ordinary + machine))


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    rows = _decode_body(data, image, sources["program_facts"], START)
    _require([r.address - BASE for r in rows] == ORDER, "owner points differ")
    for row in rows:
        operands = []
        for arg in row.operands:
            if arg.type == x86.X86_OP_REG:
                operands.append(R(row.reg_name(arg.reg)))
            elif arg.type == x86.X86_OP_IMM:
                operands.append(I(arg.imm))
            elif arg.type == x86.X86_OP_MEM:
                _require(not arg.mem.segment, "unexpected memory segment")
                operands.append(
                    M(
                        row.reg_name(arg.mem.base),
                        arg.mem.disp,
                        row.reg_name(arg.mem.index) if arg.mem.index else None,
                        arg.mem.scale,
                    )
                )
            else:
                raise ResizeError("unsupported operand")
        _require(
            (row.mnemonic, *operands) == OPS[row.address - BASE]
            and row.size == SIZES[row.address - BASE],
            "owner grammar differs",
        )
    witness = sources["allocation_semantics"]["resize_static_witness"]
    _require(
        [_point(r) for r in rows] == witness["points"],
        "incoming allocation witness differs",
    )
    inputs = case_inputs()
    cases = [
        model_case(*v, a, seed)
        for v in inputs
        for a in (0, 1, 7, 15)
        for seed in (0, U32)
    ]
    union = sorted({r for case in cases for r in case["trace_rvas"]})
    _require(union == [f"0x{p:08x}" for p in ORDER], "owner coverage differs")
    controls = []
    for name, pc, replacement in (
        ("wrong_pointer_stride", 0x2EB6CE, ("lea", R("eax"), M("edi", 0, "eax", 4))),
        ("wrong_copy_length", 0x2EB699, ("mov", R("ecx"), M("esi", 8))),
        ("wrong_free_stride", 0x2EB6BC, ("push", I(4))),
        ("wrong_new_begin", 0x2EB6DA, ("mov", M("esi"), R("eax"))),
    ):
        changed = dict(OPS)
        changed[pc] = replacement
        try:
            model_case(0x10001000, 0x10001018, 0x10001020, 6, 0x20000000, ops=changed)
        except ResizeError:
            controls.append({"mutation": name, "rejected": True})
        else:
            raise ResizeError("mutation survived")
    result = {
        "schema_version": 1,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "body": {
            "entry_rva": f"0x{START:08x}",
            "exclusive_end_rva": f"0x{END:08x}",
            "bytes": 101,
            "nodes": 46,
            "sha256": hashlib.sha256(
                b"".join(bytes(r.bytes) for r in rows)
            ).hexdigest(),
            "points": [_point(r) for r in rows],
        },
        "matrix": {
            "input_tuples": len(inputs),
            "inputs_sha256": _canonical_sha256([list(v) for v in inputs]),
            "alignments": [0, 1, 7, 15],
            "seeds": [0, U32],
        },
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
        },
        "summary": {
            "cases": len(cases),
            "modeled_sites": len(union),
            "opaque_summaries": sum(len(c["summaries"]) for c in cases),
            "actual_native_executions": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "premises": [
                "Three supplied normal-return child summaries preserve nonvolatile registers and every modeled frame and object word, including pushed arguments",
                "Allocation consumes four argument bytes on return; copy and deallocation consume none",
                "Allocation supplies the requested new pointer; child volatile registers and flags use declared independent fixed samples",
                "Synthetic machine words need not describe valid storage; ordinary ordered geometry is an additional separate contract",
            ],
            "relation": "The owner always calls copy, including zero byte count; it rereads old begin and end afterward, conditionally deallocates nonzero begin, writes new capacity then end then begin and restores the original frame with eight bytes consumed",
            "arithmetic": "Copy byte length is modular end minus begin; restored end uses the signed arithmetic-shift element count and therefore clears the low three length bits in 32-bit arithmetic",
            "not_claimed": [
                "Actual allocation, byte-copy or deallocation effects, ownership or valid mapped payload storage without premises",
                "Callee failure paths, changing object metadata across calls, arbitrary external volatile responses or integrated child execution",
                "Complete vector resize equivalence, game execution or whole-program accounting promotion",
            ],
        },
    }
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    _validate_json_tree(evidence, "evidence")
    ids = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == ids,
        "sealed resize receipt differs",
    )
    _assert_publication_safe(evidence)
    return {
        "status": "structurally_verified",
        "evidence_sha256": SEALED_SHA256,
        "summary": evidence["summary"],
    }


def build_semantics(executable, sources):
    result = _build_unsealed(executable, sources)
    validate_structure(result, sources)
    return result


def validate_semantics(executable, evidence, sources):
    validate_structure(evidence, sources)
    _require(
        _canonical_bytes(build_semantics(executable, sources))
        == _canonical_bytes(evidence),
        "exact resize receipt differs",
    )
    return {
        "status": "verified",
        "evidence_sha256": SEALED_SHA256,
        "summary": evidence["summary"],
    }


def encode_semantics(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
