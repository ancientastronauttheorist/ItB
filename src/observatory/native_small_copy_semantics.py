"""Exact short scalar copy paths with an independent overlap-safe snapshot oracle."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import capstone
import capstone.x86_const as x86
from src.observatory import native_vector_resize_semantics as resize
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
ANALYSIS_KIND = "pe_native_small_copy_semantics"
SEALED_SHA256 = "bc4fa2bd46fd46897897c6096fa7d5f04612a4de810dedbd6423da9c5a0b6319"
SOURCE_PINS = {
    "program_facts": resize.SOURCE_PINS["program_facts"],
    "resize_semantics": (resize.ANALYSIS_KIND, resize.SEALED_SHA256),
}
START = 0x36E580
SCALAR_RANGES = (
    (0x36E580, 0x36E5A9),
    (0x36E834, 0x36E843),
    (0x36E994, 0x36E9CB),
    (0x36EA7B, 0x36EAB7),
)
FULL_RANGES = (
    (0x36E580, 604),
    (0x36E7F4, 7),
    (0x36E7FC, 11),
    (0x36E808, 17),
    (0x36E81C, 23),
    (0x36E834, 91),
    (0x36E8A0, 7),
    (0x36E8A8, 13),
    (0x36E8B8, 19),
    (0x36E8CC, 255),
    (0x36E9D0, 231),
    (0x36EAC0, 52),
)
TABLES = {
    0x36E7E4: [0x36E7F4, 0x36E7FC, 0x36E808, 0x36E81C],
    0x36E890: [0x36E8A0, 0x36E8A8, 0x36E8B8, 0x36E8CC],
}
U32, PAYLOAD = 0xFFFFFFFF, 0x10000000


def R(name):
    return ("reg", name)


def I(value):
    return ("imm", value)


def M(base, offset=0, index=None, width=4):
    return ("mem", base, offset, index, width)


OPS = {
    0x36E580: ("push", R("edi")),
    0x36E581: ("push", R("esi")),
    0x36E582: ("mov", R("esi"), M("esp", 16)),
    0x36E586: ("mov", R("ecx"), M("esp", 20)),
    0x36E58A: ("mov", R("edi"), M("esp", 12)),
    0x36E58E: ("mov", R("eax"), R("ecx")),
    0x36E590: ("mov", R("edx"), R("ecx")),
    0x36E592: ("add", R("eax"), R("esi")),
    0x36E594: ("cmp", R("edi"), R("esi")),
    0x36E596: ("jbe", I(BASE + 0x36E5A0)),
    0x36E598: ("cmp", R("edi"), R("eax")),
    0x36E59A: ("jb", I(BASE + 0x36E834)),
    0x36E5A0: ("cmp", R("ecx"), I(32)),
    0x36E5A3: ("jb", I(BASE + 0x36EA7B)),
    0x36E834: ("lea", R("esi"), M("ecx", index="esi")),
    0x36E837: ("lea", R("edi"), M("ecx", index="edi")),
    0x36E83A: ("cmp", R("ecx"), I(32)),
    0x36E83D: ("jb", I(BASE + 0x36E994)),
    0x36E994: ("test", R("ecx"), I(0xFFFFFFFC)),
    0x36E99A: ("je", I(BASE + 0x36E9B1)),
    0x36E99C: ("sub", R("edi"), I(4)),
    0x36E99F: ("sub", R("esi"), I(4)),
    0x36E9A2: ("mov", R("eax"), M("esi")),
    0x36E9A4: ("mov", M("edi"), R("eax")),
    0x36E9A6: ("sub", R("ecx"), I(4)),
    0x36E9A9: ("test", R("ecx"), I(0xFFFFFFFC)),
    0x36E9AF: ("jne", I(BASE + 0x36E99C)),
    0x36E9B1: ("test", R("ecx"), R("ecx")),
    0x36E9B3: ("je", I(BASE + 0x36E9C4)),
    0x36E9B5: ("sub", R("edi"), I(1)),
    0x36E9B8: ("sub", R("esi"), I(1)),
    0x36E9BB: ("mov", R("al"), M("esi", width=1)),
    0x36E9BD: ("mov", M("edi", width=1), R("al")),
    0x36E9BF: ("sub", R("ecx"), I(1)),
    0x36E9C2: ("jne", I(BASE + 0x36E9B5)),
    0x36E9C4: ("mov", R("eax"), M("esp", 12)),
    0x36E9C8: ("pop", R("esi")),
    0x36E9C9: ("pop", R("edi")),
    0x36E9CA: ("ret",),
    0x36EA7B: ("and", R("ecx"), I(31)),
    0x36EA7E: ("je", I(BASE + 0x36EAB0)),
    0x36EA80: ("mov", R("eax"), R("ecx")),
    0x36EA82: ("shr", R("ecx"), I(2)),
    0x36EA85: ("je", I(BASE + 0x36EA96)),
    0x36EA87: ("mov", R("edx"), M("esi")),
    0x36EA89: ("mov", M("edi"), R("edx")),
    0x36EA8B: ("add", R("edi"), I(4)),
    0x36EA8E: ("add", R("esi"), I(4)),
    0x36EA91: ("sub", R("ecx"), I(1)),
    0x36EA94: ("jne", I(BASE + 0x36EA87)),
    0x36EA96: ("mov", R("ecx"), R("eax")),
    0x36EA98: ("and", R("ecx"), I(3)),
    0x36EA9B: ("je", I(BASE + 0x36EAB0)),
    0x36EA9D: ("mov", R("al"), M("esi", width=1)),
    0x36EA9F: ("mov", M("edi", width=1), R("al")),
    0x36EAA1: ("inc", R("esi")),
    0x36EAA2: ("inc", R("edi")),
    0x36EAA3: ("dec", R("ecx")),
    0x36EAA4: ("jne", I(BASE + 0x36EA9D)),
    0x36EAA6: ("lea", R("esp"), M("esp")),
    0x36EAAD: ("lea", R("ecx"), M("ecx")),
    0x36EAB0: ("mov", R("eax"), M("esp", 12)),
    0x36EAB4: ("pop", R("esi")),
    0x36EAB5: ("pop", R("edi")),
    0x36EAB6: ("ret",),
}
ORDER = list(OPS)
SIZES = {}
for start, end in SCALAR_RANGES:
    points = [p for p in ORDER if start <= p < end]
    SIZES.update(
        {
            p: (points[i + 1] if i + 1 < len(points) else end) - p
            for i, p in enumerate(points)
        }
    )


class SmallCopyError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise SmallCopyError(message)


def _normalize(fn):
    try:
        return fn()
    except SmallCopyError:
        raise
    except Exception as exc:
        raise SmallCopyError(str(exc)) from exc


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)


def copy_spec(destination, source, length):
    for name, value in (
        ("destination", destination),
        ("source", source),
        ("length", length),
    ):
        _u32(value, name)
    _require(
        length < 32 and source + length <= U32 and destination + length <= U32,
        "outside short nonwrapping copy domain",
    )
    return {
        "direction": (
            "backward" if source < destination < source + length else "forward"
        ),
        "length": length,
        "destination": destination,
        "source": source,
        "arithmetic_flags": {
            "cf": 0,
            "pf": 1,
            "af": None if length % 4 == 0 else 0,
            "zf": 1,
            "sf": 0,
            "of": 0,
        },
    }


def snapshot_spec(payload, base, destination, source, length):
    relation = copy_spec(destination, source, length)
    _u32(base, "payload base")
    _require(
        type(payload) is bytes and base + len(payload) <= U32, "invalid payload mapping"
    )
    _require(
        base <= source
        and source + length <= base + len(payload)
        and base <= destination
        and destination + length <= base + len(payload),
        "copy outside mapped buffer",
    )
    result = bytearray(payload)
    result[destination - base : destination - base + length] = payload[
        source - base : source - base + length
    ]
    edx = length
    if relation["direction"] == "forward" and length >= 4:
        at = source - base + 4 * (length // 4 - 1)
        edx = int.from_bytes(payload[at : at + 4], "little")
    return {"payload_after": bytes(result), "edx": edx, "relation": relation}


def _arithmetic(left, right, subtract):
    raw = left - right if subtract else left + right
    result = raw & U32
    overflow = (
        ((left ^ right) & (left ^ result)) >> 31
        if subtract
        else ((~(left ^ right)) & (left ^ result) & U32) >> 31
    )
    return result, {
        "cf": int(left < right) if subtract else int(raw > U32),
        "pf": int((result & 255).bit_count() % 2 == 0),
        "af": ((left ^ right ^ result) >> 4) & 1,
        "zf": int(result == 0),
        "sf": result >> 31,
        "of": overflow,
    }


def _logical(value):
    return {
        "cf": 0,
        "pf": int((value & 255).bit_count() % 2 == 0),
        "af": None,
        "zf": int(value == 0),
        "sf": value >> 31,
        "of": 0,
    }


def case_fixture(
    length, source_offset=64, destination_offset=65, frame_alignment=0, seed=1, df=0
):
    _require(
        type(source_offset) is int and type(destination_offset) is int,
        "invalid buffer offsets",
    )
    relation = copy_spec(PAYLOAD + destination_offset, PAYLOAD + source_offset, length)
    _require(
        0 <= source_offset <= 256 - length and 0 <= destination_offset <= 256 - length,
        "copy outside fixture payload",
    )
    _require(
        type(frame_alignment) is int and 0 <= frame_alignment < 16,
        "invalid frame alignment",
    )
    _u32(seed, "seed")
    _require(type(df) is int and df in (0, 1), "invalid direction flag")
    stack = 0x30001000 + frame_alignment
    regs = {
        r: (0xA1000000 + i * 0x10101 + seed) & U32
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs["esp"] = stack
    payload = bytes(((i * 37) ^ (i >> 3) ^ seed) & 255 for i in range(256))
    memory = {PAYLOAD + i: value for i, value in enumerate(payload)}
    memory.update({stack + i: ((i * 23) ^ seed) & 255 for i in range(-12, 20)})
    ret = (0x44556677 + seed) & U32
    for address, value in (
        (stack, ret),
        (stack + 4, relation["destination"]),
        (stack + 8, relation["source"]),
        (stack + 12, length),
    ):
        memory.update(
            {address + i: b for i, b in enumerate(value.to_bytes(4, "little"))}
        )
    return {
        "registers": regs,
        "memory": memory,
        "stack": stack,
        "payload": payload,
        "return_address": ret,
        "df": df,
    }


def model_case(
    length,
    source_offset=64,
    destination_offset=65,
    frame_alignment=0,
    seed=1,
    df=0,
    ops=None,
):
    fixture = case_fixture(
        length, source_offset, destination_offset, frame_alignment, seed, df
    )
    source, destination = PAYLOAD + source_offset, PAYLOAD + destination_offset
    expected = snapshot_spec(fixture["payload"], PAYLOAD, destination, source, length)
    initial = fixture["registers"]
    regs, memory = dict(initial), dict(fixture["memory"])
    operations = OPS if ops is None else ops
    flags = None
    pc = START
    returned = False
    return_address = None
    events, trace = [], []

    def access(address, width):
        _require(all(address + i in memory for i in range(width)), "unmapped copy read")
        value = int.from_bytes(
            bytes(memory[address + i] for i in range(width)), "little"
        )
        events.append(
            {"kind": "read", "address": address, "width": width, "value": value}
        )
        return value

    def address(arg):
        return (regs[arg[1]] + arg[2] + (regs[arg[3]] if arg[3] else 0)) & U32

    def read(arg):
        if arg[0] == "reg":
            return regs["eax"] & 255 if arg[1] == "al" else regs[arg[1]]
        if arg[0] == "imm":
            return arg[1] & U32
        return access(address(arg), arg[4])

    def write(arg, value):
        if arg[0] == "reg":
            if arg[1] == "al":
                regs["eax"] = (regs["eax"] & 0xFFFFFF00) | (value & 255)
            else:
                regs[arg[1]] = value & U32
        else:
            at = address(arg)
            width = arg[4]
            _require(all(at + i in memory for i in range(width)), "unmapped copy write")
            memory.update(
                {at + i: b for i, b in enumerate(value.to_bytes(width, "little"))}
            )
            events.append(
                {"kind": "write", "address": at, "width": width, "value": value}
            )

    while not returned:
        _require(pc in operations and len(trace) < 250, "copy escaped scalar domain")
        trace.append(f"0x{pc:08x}")
        op, *args = operations[pc]
        next_pc = pc + SIZES[pc]
        if op == "push":
            value = read(args[0])
            regs["esp"] = (regs["esp"] - 4) & U32
            write(M("esp"), value)
        elif op == "pop":
            write(args[0], access(regs["esp"], 4))
            regs["esp"] = (regs["esp"] + 4) & U32
        elif op == "mov":
            write(args[0], read(args[1]))
        elif op == "lea":
            write(args[0], address(args[1]))
        elif op in ("add", "sub", "cmp", "inc", "dec"):
            left = read(args[0])
            right = read(args[1]) if len(args) > 1 else 1
            value, newflags = _arithmetic(left, right, op in ("sub", "cmp", "dec"))
            if op in ("inc", "dec"):
                newflags["cf"] = flags["cf"]
            flags = newflags
            if op != "cmp":
                write(args[0], value)
        elif op in ("and", "test"):
            value = read(args[0]) & read(args[1])
            flags = _logical(value)
            if op == "and":
                write(args[0], value)
        elif op == "shr":
            old = read(args[0])
            shift = read(args[1])
            value = old >> shift
            flags = _logical(value)
            flags.update(cf=(old >> (shift - 1)) & 1, af=None, of=None)
            write(args[0], value)
        elif op in ("jb", "jbe", "je", "jne"):
            take = (
                op == "jb"
                and flags["cf"]
                or op == "jbe"
                and (flags["cf"] or flags["zf"])
                or op == "je"
                and flags["zf"]
                or op == "jne"
                and not flags["zf"]
            )
            if take:
                next_pc = read(args[0]) - BASE
        elif op == "ret":
            return_address = access(regs["esp"], 4)
            regs["esp"] = (regs["esp"] + 4) & U32
            returned = True
        else:
            raise SmallCopyError("unsupported scalar operation")
        pc = next_pc
    stack = fixture["stack"]
    wanted_memory = dict(fixture["memory"])
    wanted_events = []

    def expect(kind, at, width, value):
        wanted_events.append(
            {"kind": kind, "address": at, "width": width, "value": value}
        )
        if kind == "write":
            wanted_memory.update(
                {at + i: b for i, b in enumerate(value.to_bytes(width, "little"))}
            )

    expect("write", stack - 4, 4, initial["edi"])
    expect("write", stack - 8, 4, initial["esi"])
    expect("read", stack + 8, 4, source)
    expect("read", stack + 12, 4, length)
    expect("read", stack + 4, 4, destination)
    quotient, remainder = divmod(length, 4)
    spans = (
        [(4 * i, 4) for i in range(quotient)]
        + [(4 * quotient + i, 1) for i in range(remainder)]
        if expected["relation"]["direction"] == "forward"
        else [(length - 4 * (i + 1), 4) for i in range(quotient)]
        + [(remainder - i - 1, 1) for i in range(remainder)]
    )
    for offset, width in spans:
        value = int.from_bytes(
            fixture["payload"][source_offset + offset : source_offset + offset + width],
            "little",
        )
        expect("read", source + offset, width, value)
        expect("write", destination + offset, width, value)
    expect("read", stack + 4, 4, destination)
    expect("read", stack - 8, 4, initial["esi"])
    expect("read", stack - 4, 4, initial["edi"])
    expect("read", stack, 4, fixture["return_address"])
    wanted_regs = dict(
        initial, eax=destination, ecx=0, edx=expected["edx"], esp=stack + 4
    )
    _require(
        regs == wanted_regs
        and flags == expected["relation"]["arithmetic_flags"]
        and df == fixture["df"],
        "copy register or flag relation differs",
    )
    _require(return_address == fixture["return_address"], "copy return target differs")
    _require(
        memory == wanted_memory and events == wanted_events,
        "ordered scalar copy relation differs",
    )
    actual_payload = bytes(memory[PAYLOAD + i] for i in range(256))
    _require(
        actual_payload == expected["payload_after"], "independent snapshot copy differs"
    )
    return {
        "inputs": {
            "length": length,
            "source_offset": source_offset,
            "destination_offset": destination_offset,
            "frame_alignment": frame_alignment,
            "seed": seed,
            "df": df,
        },
        "direction": expected["relation"]["direction"],
        "registers": regs,
        "arithmetic_flags": flags,
        "df": df,
        "return_address": return_address,
        "events": events,
        "trace_rvas": trace,
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
    _require(
        [r.address - BASE for r in rows] == ORDER, "scalar instruction points differ"
    )
    for row in rows:
        args = []
        for arg in row.operands:
            if arg.type == x86.X86_OP_REG:
                args.append(R(row.reg_name(arg.reg)))
            elif arg.type == x86.X86_OP_IMM:
                args.append(I(arg.imm))
            elif arg.type == x86.X86_OP_MEM:
                _require(
                    not arg.mem.segment and arg.mem.scale == 1, "unexpected memory mode"
                )
                args.append(
                    M(
                        row.reg_name(arg.mem.base),
                        arg.mem.disp,
                        row.reg_name(arg.mem.index) if arg.mem.index else None,
                        arg.size,
                    )
                )
            else:
                raise SmallCopyError("unexpected operand")
        pc = row.address - BASE
        widths = (
            [1, 1]
            if pc in (0x36E9BB, 0x36E9BD, 0x36EA9D, 0x36EA9F)
            else [4, 1] if pc == 0x36EA82 else [4] * len(args)
        )
        _require(
            (row.mnemonic, *args) == OPS[pc]
            and row.size == SIZES[pc]
            and [a.size for a in row.operands] == widths,
            "exact scalar grammar differs",
        )


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    facts = next(
        body
        for body in sources["program_facts"]["functions"]
        if int(body["entry_rva"], 16) == START
    )
    _require(
        [(int(r["start_rva"], 16), r["size"]) for r in facts["ranges"]]
        == list(FULL_RANGES),
        "copy range partition differs",
    )
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    rows = []
    chunks = []
    ranges = []
    for start, size in FULL_RANGES:
        offset = image.rva_to_file_offset(start)
        chunk = data[offset : offset + size]
        decoded = list(decoder.disasm(chunk, BASE + start))
        _require(sum(r.size for r in decoded) == size, "range contains undecoded bytes")
        rows.extend(decoded)
        chunks.append(chunk)
        ranges.append(
            {
                "start_rva": f"0x{start:08x}",
                "bytes": size,
                "nodes": len(decoded),
                "sha256": hashlib.sha256(chunk).hexdigest(),
                "points": [_point(r) for r in decoded],
            }
        )
    _require(
        len(rows) == 404
        and sum(len(c) for c in chunks) == facts["body_size"] == 1330
        and hashlib.sha256(b"".join(chunks)).hexdigest() == facts["body_sha256"],
        "full discontiguous copy witness differs",
    )
    scalar = [
        r for r in rows if any(a <= r.address - BASE < b for a, b in SCALAR_RANGES)
    ]
    _grammar(scalar)
    tables = []
    for start, targets in TABLES.items():
        offset = image.rva_to_file_offset(start)
        chunk = data[offset : offset + 16]
        actual = [
            int.from_bytes(chunk[i : i + 4], "little") - BASE for i in range(0, 16, 4)
        ]
        _require(
            actual == targets
            and all(start + 16 <= a or a + size <= start for a, size in FULL_RANGES),
            "excluded table bounds differ",
        )
        tables.append(
            {
                "start_rva": f"0x{start:08x}",
                "bytes": 16,
                "sha256": hashlib.sha256(chunk).hexdigest(),
                "target_rvas": [f"0x{target:08x}" for target in targets],
                "read_by_scalar_slice": False,
            }
        )
    caller = _decode_body(data, image, sources["program_facts"], 0x2EB680)
    _require(
        [_point(r) for r in caller] == sources["resize_semantics"]["body"]["points"],
        "resize caller witness differs",
    )
    edge = next(r for r in caller if r.address - BASE == 0x2EB6A1)
    _require(
        edge.id == x86.X86_INS_CALL and edge.operands[0].imm == BASE + START,
        "copy incoming edge differs",
    )
    deltas = [-40, -8, -3, -1, 0, 1, 3, 8, 40]
    cases = [
        model_case(n, 64 + a, 64 + a + delta, frame, seed, df)
        for n in range(32)
        for a in range(4)
        for delta in deltas
        for frame in (0, 1, 7, 15)
        for seed in (0, 255)
        for df in (0, 1)
    ]
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(union == [f"0x{p:08x}" for p in ORDER], "scalar path coverage differs")
    controls = []
    for name, pc, replacement, args in (
        ("wrong_overlap_direction", 0x36E59A, ("je", I(BASE + 0x36E834)), (12, 64, 65)),
        (
            "wrong_forward_word_source",
            0x36EA87,
            ("mov", R("edx"), M("esi", 1)),
            (8, 64, 24),
        ),
        ("wrong_backward_word_step", 0x36E99F, ("sub", R("esi"), I(3)), (8, 64, 65)),
        (
            "wrong_byte_source",
            0x36EA9D,
            ("mov", R("al"), M("esi", 1, width=1)),
            (3, 64, 24),
        ),
        ("wrong_saved_register", 0x36EAB4, ("pop", R("edx")), (0, 64, 65)),
    ):
        changed = dict(OPS)
        changed[pc] = replacement
        try:
            model_case(*args, ops=changed)
        except SmallCopyError:
            controls.append(
                {"name": name, "kind": "semantic_mutation", "rejected": True}
            )
        else:
            raise SmallCopyError("semantic mutation accepted: " + name)
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "body": {
            "entry_rva": f"0x{START:08x}",
            "bytes": 1330,
            "nodes": 404,
            "sha256": facts["body_sha256"],
            "ranges": ranges,
        },
        "scalar_ranges": [
            {
                "start_rva": f"0x{a:08x}",
                "exclusive_end_rva": f"0x{b:08x}",
                "bytes": b - a,
                "points": [_point(r) for r in scalar if a <= r.address - BASE < b],
            }
            for a, b in SCALAR_RANGES
        ],
        "excluded_tables": tables,
        "incoming_edge": {
            "instruction": _point(edge),
            "target_entry_rva": f"0x{START:08x}",
        },
        "matrix": {
            "lengths": list(range(32)),
            "source_alignments": list(range(4)),
            "destination_deltas": deltas,
            "entry_stack_base": 0x30001000,
            "frame_alignments": [0, 1, 7, 15],
            "seeds": [0, 255],
            "direction_flags": [0, 1],
        },
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
        },
        "summary": {
            "cases": len(cases),
            "static_bytes": 1330,
            "static_nodes": 404,
            "modeled_bytes": 171,
            "modeled_nodes": 65,
            "forward_cases": sum(c["direction"] == "forward" for c in cases),
            "backward_cases": sum(c["direction"] == "backward" for c in cases),
            "actual_native_executions": 0,
            "calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "exact_short_scalar_graph_with_independent_snapshot_copy_oracle",
            "premises": [
                "Length is zero through thirty-one; source and destination exclusive ends remain representable unsigned words, excluding endpoint wrap to zero",
                "Mapped readable source and writable destination bytes may overlap inside the declared payload, disjoint from protected frame and code",
                "Stable mapped caller frame at the finite stack base and alignments; both direction-flag settings are preserved",
            ],
            "relation": "The destination equals the original source snapshot, all other payload bytes remain unchanged, overlapping higher destination copies backward, and EAX returns destination with ECX zero and saved registers restored",
            "edx_relation": "Backward EDX remains length; forward EDX remains length below four bytes, otherwise it is the final original source DWORD in the forward word sequence",
            "flags": "Final CF, OF and SF are zero and PF and ZF are one; AF is undefined when length is divisible by four and zero otherwise; DF is unchanged",
            "not_claimed": [
                "Any long-copy, vectorized, feature-global, REP or jump-table path",
                "Behavior for wrapping ranges, code or frame aliases, concurrent mutation or unmapped data",
                "Actual game execution, full copy routine equivalence or accounting promotion",
            ],
        },
    }
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "executable changed during build",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    def run():
        _validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256
            and evidence["source_receipts"] == ids,
            "sealed small copy differs",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_semantics(executable, sources):
    def run():
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_semantics(executable, evidence, sources):
    def run():
        validate_structure(evidence, sources)
        actual = build_semantics(executable, sources)
        _require(
            _canonical_bytes(actual) == _canonical_bytes(evidence),
            "exact small copy differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(actual["summary"]),
        }

    return _normalize(run)


def encode_semantics(value):
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
