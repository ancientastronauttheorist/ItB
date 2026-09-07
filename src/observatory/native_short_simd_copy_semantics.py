"""Forward short MOVDQU copy paths with an independent snapshot oracle."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import capstone
import capstone.x86_const as x86
from src.observatory import native_scalar_copy_semantics as scalar
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
ANALYSIS_KIND = "pe_native_short_simd_copy_semantics"
SEALED_SHA256 = "ad1a4109a23a67bca5ae03b48dc3fe16cd2419000158a1d00f041c4fe488c17d"
SOURCE_PINS = {
    "program_facts": resize.SOURCE_PINS["program_facts"],
    "scalar_copy_semantics": (scalar.ANALYSIS_KIND, scalar.SEALED_SHA256),
}
START = 0x36E580
SCALAR_RANGES = ((3597696, 3597759), (3598925, 3599031))
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
    3597696: ("push", ("reg", "edi")),
    3597697: ("push", ("reg", "esi")),
    3597698: ("mov", ("reg", "esi"), ("mem", "esp", 16, None, 4, 1)),
    3597702: ("mov", ("reg", "ecx"), ("mem", "esp", 20, None, 4, 1)),
    3597706: ("mov", ("reg", "edi"), ("mem", "esp", 12, None, 4, 1)),
    3597710: ("mov", ("reg", "eax"), ("reg", "ecx")),
    3597712: ("mov", ("reg", "edx"), ("reg", "ecx")),
    3597714: ("add", ("reg", "eax"), ("reg", "esi")),
    3597716: ("cmp", ("reg", "edi"), ("reg", "esi")),
    3597718: ("jbe", ("imm", 7792032)),
    3597720: ("cmp", ("reg", "edi"), ("reg", "eax")),
    3597722: ("jb", ("imm", 7792692)),
    3597728: ("cmp", ("reg", "ecx"), ("imm", 32)),
    3597731: ("jb", ("imm", 7793275)),
    3597737: ("cmp", ("reg", "ecx"), ("imm", 128)),
    3597743: ("jae", ("imm", 7792068)),
    3597745: ("bt", ("mem", None, 8994608, None, 4, 1), ("imm", 1)),
    3597753: ("jb", ("imm", 7793229)),
    3598925: ("test", ("reg", "ecx"), ("reg", "ecx")),
    3598927: ("je", ("imm", 7793328)),
    3598929: ("mov", ("reg", "edx"), ("reg", "ecx")),
    3598931: ("shr", ("reg", "edx"), ("imm", 5)),
    3598934: ("test", ("reg", "edx"), ("reg", "edx")),
    3598936: ("je", ("imm", 7793275)),
    3598938: ("lea", ("reg", "ebx"), ("mem", "ebx", 0, None, 4, 1)),
    3598944: ("movdqu", ("reg", "xmm0"), ("mem", "esi", 0, None, 16, 1)),
    3598948: ("movdqu", ("reg", "xmm1"), ("mem", "esi", 16, None, 16, 1)),
    3598953: ("movdqu", ("mem", "edi", 0, None, 16, 1), ("reg", "xmm0")),
    3598957: ("movdqu", ("mem", "edi", 16, None, 16, 1), ("reg", "xmm1")),
    3598962: ("lea", ("reg", "esi"), ("mem", "esi", 32, None, 4, 1)),
    3598965: ("lea", ("reg", "edi"), ("mem", "edi", 32, None, 4, 1)),
    3598968: ("dec", ("reg", "edx")),
    3598969: ("jne", ("imm", 7793248)),
    3598971: ("and", ("reg", "ecx"), ("imm", 31)),
    3598974: ("je", ("imm", 7793328)),
    3598976: ("mov", ("reg", "eax"), ("reg", "ecx")),
    3598978: ("shr", ("reg", "ecx"), ("imm", 2)),
    3598981: ("je", ("imm", 7793302)),
    3598983: ("mov", ("reg", "edx"), ("mem", "esi", 0, None, 4, 1)),
    3598985: ("mov", ("mem", "edi", 0, None, 4, 1), ("reg", "edx")),
    3598987: ("add", ("reg", "edi"), ("imm", 4)),
    3598990: ("add", ("reg", "esi"), ("imm", 4)),
    3598993: ("sub", ("reg", "ecx"), ("imm", 1)),
    3598996: ("jne", ("imm", 7793287)),
    3598998: ("mov", ("reg", "ecx"), ("reg", "eax")),
    3599000: ("and", ("reg", "ecx"), ("imm", 3)),
    3599003: ("je", ("imm", 7793328)),
    3599005: ("mov", ("reg", "al"), ("mem", "esi", 0, None, 1, 1)),
    3599007: ("mov", ("mem", "edi", 0, None, 1, 1), ("reg", "al")),
    3599009: ("inc", ("reg", "esi")),
    3599010: ("inc", ("reg", "edi")),
    3599011: ("dec", ("reg", "ecx")),
    3599012: ("jne", ("imm", 7793309)),
    3599014: ("lea", ("reg", "esp"), ("mem", "esp", 0, None, 4, 1)),
    3599021: ("lea", ("reg", "ecx"), ("mem", "ecx", 0, None, 4, 1)),
    3599024: ("mov", ("reg", "eax"), ("mem", "esp", 12, None, 4, 1)),
    3599028: ("pop", ("reg", "esi")),
    3599029: ("pop", ("reg", "edi")),
    3599030: ("ret",),
}
ORDER = sorted(OPS)
SIZES = {
    3597696: 1,
    3597697: 1,
    3597698: 4,
    3597702: 4,
    3597706: 4,
    3597710: 2,
    3597712: 2,
    3597714: 2,
    3597716: 2,
    3597718: 2,
    3597720: 2,
    3597722: 6,
    3597728: 3,
    3597731: 6,
    3597737: 6,
    3597743: 2,
    3597745: 8,
    3597753: 6,
    3598925: 2,
    3598927: 2,
    3598929: 2,
    3598931: 3,
    3598934: 2,
    3598936: 2,
    3598938: 6,
    3598944: 4,
    3598948: 5,
    3598953: 4,
    3598957: 5,
    3598962: 3,
    3598965: 3,
    3598968: 1,
    3598969: 2,
    3598971: 3,
    3598974: 2,
    3598976: 2,
    3598978: 3,
    3598981: 2,
    3598983: 2,
    3598985: 2,
    3598987: 3,
    3598990: 3,
    3598993: 3,
    3598996: 2,
    3598998: 2,
    3599000: 3,
    3599003: 2,
    3599005: 2,
    3599007: 2,
    3599009: 1,
    3599010: 1,
    3599011: 1,
    3599012: 2,
    3599014: 7,
    3599021: 3,
    3599024: 4,
    3599028: 1,
    3599029: 1,
    3599030: 1,
}
WIDTHS = {
    3597696: [4],
    3597697: [4],
    3597698: [4, 4],
    3597702: [4, 4],
    3597706: [4, 4],
    3597710: [4, 4],
    3597712: [4, 4],
    3597714: [4, 4],
    3597716: [4, 4],
    3597718: [4],
    3597720: [4, 4],
    3597722: [4],
    3597728: [4, 4],
    3597731: [4],
    3597737: [4, 4],
    3597743: [4],
    3597745: [4, 1],
    3597753: [4],
    3598925: [4, 4],
    3598927: [4],
    3598929: [4, 4],
    3598931: [4, 1],
    3598934: [4, 4],
    3598936: [4],
    3598938: [4, 4],
    3598944: [16, 16],
    3598948: [16, 16],
    3598953: [16, 16],
    3598957: [16, 16],
    3598962: [4, 4],
    3598965: [4, 4],
    3598968: [4],
    3598969: [4],
    3598971: [4, 4],
    3598974: [4],
    3598976: [4, 4],
    3598978: [4, 1],
    3598981: [4],
    3598983: [4, 4],
    3598985: [4, 4],
    3598987: [4, 4],
    3598990: [4, 4],
    3598993: [4, 4],
    3598996: [4],
    3598998: [4, 4],
    3599000: [4, 4],
    3599003: [4],
    3599005: [1, 1],
    3599007: [1, 1],
    3599009: [4],
    3599010: [4],
    3599011: [4],
    3599012: [4],
    3599014: [4, 4],
    3599021: [4, 4],
    3599024: [4, 4],
    3599028: [4],
    3599029: [4],
    3599030: [],
}


class ShortSimdCopyError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ShortSimdCopyError(message)


def _normalize(fn):
    try:
        return fn()
    except ShortSimdCopyError:
        raise
    except Exception as exc:
        raise ShortSimdCopyError(str(exc)) from exc


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)


def copy_spec(destination, source, length, feature_word=2, df=0):
    for name, value in (
        ("destination", destination),
        ("source", source),
        ("length", length),
        ("feature word", feature_word),
    ):
        _u32(value, name)
    _require(
        32 <= length <= 127 and source + length <= U32 and destination + length <= U32,
        "outside bounded byte copy domain",
    )
    _require(
        destination <= source or destination >= source + length,
        "backward overlap outside forward byte copy domain",
    )
    _require(
        feature_word & 2 and type(df) is int and df == 0,
        "byte dispatch premises differ",
    )
    return dict(
        direction="forward",
        destination=destination,
        source=source,
        length=length,
        arithmetic_flags=dict(
            cf=0, zf=1, pf=1, af=None if length % 4 == 0 else 0, sf=0, of=0
        ),
    )


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
    edx = 0
    remainder = length % 32
    if remainder >= 4:
        at = source - base + (length // 32) * 32 + 4 * (remainder // 4 - 1)
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
    length,
    source_offset=2048,
    destination_offset=1024,
    frame_alignment=0,
    seed=1,
    df=0,
    feature_word=2,
):
    _require(
        type(source_offset) is int and type(destination_offset) is int,
        "invalid buffer offsets",
    )
    relation = copy_spec(
        PAYLOAD + destination_offset, PAYLOAD + source_offset, length, feature_word, df
    )
    _require(
        0 <= source_offset <= 8192 - length
        and 0 <= destination_offset <= 8192 - length,
        "copy outside fixture payload",
    )
    _require(
        type(frame_alignment) is int and 0 <= frame_alignment < 16,
        "invalid frame alignment",
    )
    _u32(seed, "seed")
    _require(type(df) is int and df == 0, "invalid direction flag")
    stack = 0x30001000 + frame_alignment
    regs = {
        r: (0xA1000000 + i * 0x10101 + seed) & U32
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs["esp"] = stack
    payload = bytes(((i * 37) ^ (i >> 3) ^ seed) & 255 for i in range(8192))
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
    for at, value in [(0x893F30, feature_word)]:
        memory.update({at + i: b for i, b in enumerate(value.to_bytes(4, "little"))})
    xmm = {
        f"xmm{i}": int.from_bytes(
            bytes(((i * 31 + j * 17 + seed) & 255) for j in range(16)), "little"
        )
        for i in range(8)
    }
    return {
        "registers": regs,
        "xmm": xmm,
        "memory": memory,
        "stack": stack,
        "payload": payload,
        "return_address": ret,
        "df": df,
    }


def model_case(
    length,
    source_offset=2048,
    destination_offset=1024,
    frame_alignment=0,
    seed=1,
    df=0,
    feature_word=2,
    ops=None,
):
    fixture = case_fixture(
        length,
        source_offset,
        destination_offset,
        frame_alignment,
        seed,
        df,
        feature_word,
    )
    source, destination = PAYLOAD + source_offset, PAYLOAD + destination_offset
    expected = snapshot_spec(fixture["payload"], PAYLOAD, destination, source, length)
    initial = fixture["registers"]
    regs, memory = dict(initial), dict(fixture["memory"])
    xmm = dict(fixture["xmm"])
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
        return (
            (regs[arg[1]] if arg[1] else 0)
            + arg[2]
            + (regs[arg[3]] * (arg[5] if len(arg) > 5 else 1) if arg[3] else 0)
        ) & U32

    def read(arg):
        if arg[0] == "reg":
            if arg[1].startswith("xmm"):
                return xmm[arg[1]]
            return regs["eax"] & 255 if arg[1] == "al" else regs[arg[1]]
        if arg[0] == "imm":
            return arg[1] & U32
        return access(address(arg), arg[4])

    def write(arg, value):
        if arg[0] == "reg":
            if arg[1].startswith("xmm"):
                xmm[arg[1]] = value & ((1 << 128) - 1)
                return
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
        elif op in ("mov", "movdqu"):
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
        elif op in ("and", "test", "xor"):
            value = (
                read(args[0]) ^ read(args[1])
                if op == "xor"
                else read(args[0]) & read(args[1])
            )
            flags = _logical(value)
            if op in ("and", "xor"):
                write(args[0], value)
        elif op == "shr":
            old = read(args[0])
            shift = read(args[1])
            value = old >> shift
            flags = _logical(value)
            flags.update(cf=(old >> (shift - 1)) & 1, af=None, of=None)
            write(args[0], value)
        elif op in ("jb", "jbe", "je", "jne", "jae"):
            take = (
                op == "jae"
                and not flags["cf"]
                or op == "jb"
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
        elif op == "bt":
            prior_zf = flags["zf"]
            flags = {k: None for k in ("cf", "pf", "af", "zf", "sf", "of")}
            flags.update(cf=(read(args[0]) >> read(args[1])) & 1, zf=prior_zf)
        elif op == "jmp":
            next_pc = read(args[0]) - BASE
        elif op in ("std", "cld"):
            df = int(op == "std")
        elif op == "rep movsb":
            while regs["ecx"]:
                write(M("edi", width=1), access(regs["esi"], 1))
                step = -1 if df else 1
                regs["esi"] = (regs["esi"] + step) & U32
                regs["edi"] = (regs["edi"] + step) & U32
                regs["ecx"] -= 1
        elif op == "ret":
            return_address = access(regs["esp"], 4)
            regs["esp"] = (regs["esp"] + 4) & U32
            returned = True
        else:
            raise ShortSimdCopyError("unsupported scalar operation")
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
    expect("read", 0x893F30, 4, feature_word)

    def original(offset, width):
        return int.from_bytes(
            fixture["payload"][source_offset + offset : source_offset + offset + width],
            "little",
        )

    for offset in range(0, length - length % 32, 32):
        expect("read", source + offset, 16, original(offset, 16))
        expect("read", source + offset + 16, 16, original(offset + 16, 16))
        expect("write", destination + offset, 16, original(offset, 16))
        expect("write", destination + offset + 16, 16, original(offset + 16, 16))
    at = length - length % 32
    while at + 4 <= length:
        value = original(at, 4)
        expect("read", source + at, 4, value)
        expect("write", destination + at, 4, value)
        at += 4
    while at < length:
        value = original(at, 1)
        expect("read", source + at, 1, value)
        expect("write", destination + at, 1, value)
        at += 1
    wanted_xmm = dict(fixture["xmm"])
    final_chunk = 32 * (length // 32 - 1)
    wanted_xmm.update(
        xmm0=original(final_chunk, 16), xmm1=original(final_chunk + 16, 16)
    )
    _require(xmm == wanted_xmm, "SIMD register relation differs")
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
    actual_payload = bytes(memory[PAYLOAD + i] for i in range(8192))
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
            "feature_word": feature_word,
        },
        "direction": expected["relation"]["direction"],
        "registers": regs,
        "xmm": xmm,
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
        [r.address - BASE for r in rows] == ORDER,
        "scalar instruction partition differs",
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
                    arg.mem.segment
                    == (
                        x86.X86_REG_ES
                        if row.mnemonic == "rep movsb" and not args
                        else 0
                    ),
                    "unexpected memory segment",
                )
                args.append(
                    (
                        "mem",
                        row.reg_name(arg.mem.base) if arg.mem.base else None,
                        arg.mem.disp,
                        row.reg_name(arg.mem.index) if arg.mem.index else None,
                        arg.size,
                        arg.mem.scale,
                    )
                )
            else:
                raise ShortSimdCopyError("unexpected instruction operand")
        pc = row.address - BASE
        _require(
            (row.mnemonic, *args) == OPS[pc]
            and row.size == SIZES[pc]
            and [arg.size for arg in row.operands] == WIDTHS[pc],
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
    _require(
        ranges == sources["scalar_copy_semantics"]["body"]["ranges"],
        "source full body witness differs",
    )
    lengths = list(range(32, 128))
    deltas = [-128, -17, -3, -1, 0, 128]
    words = [2, 0xFFFFFFFF]
    vectors = [
        dict(
            length=n,
            source_offset=256,
            destination_offset=256 + delta,
            frame_alignment=0,
            feature_word=word,
        )
        for n in lengths
        for delta in (-1, 0, 128)
        for word in words
    ]
    vectors += [
        dict(
            length=n,
            source_offset=256 + a,
            destination_offset=256 + a + delta,
            frame_alignment=frame,
            feature_word=2,
        )
        for n in (32, 33, 35, 36, 63, 64, 65, 95, 96, 97, 127)
        for a in range(16)
        for delta in deltas
        for frame in (0, 15)
    ]
    cases = []
    for vector in vectors:
        case = model_case(**vector)
        cases.append(
            dict(sha256=_canonical_sha256(case), trace_rvas=case["trace_rvas"])
        )
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(union == [f"0x{pc:08x}" for pc in ORDER], "SIMD copy coverage differs")
    controls = []
    for name, pc, replacement in [
        ("wrong_vector_source", 0x36EA60, ("movdqu", R("xmm0"), M("esi", 1, width=16))),
        ("wrong_vector_store", 0x36EA6D, ("movdqu", M("edi", 16, width=16), R("xmm0"))),
        (
            "wrong_vector_clobber",
            0x36EA64,
            ("movdqu", R("xmm2"), M("esi", 16, width=16)),
        ),
    ]:
        changed = dict(OPS)
        changed[pc] = replacement
        try:
            model_case(64, 256, 128, ops=changed)
        except ShortSimdCopyError:
            controls.append(dict(name=name, rejected=True))
        else:
            raise ShortSimdCopyError("SIMD mutation accepted")
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
        "vectors": vectors,
        "feature_premise": {"rva": "0x00493f30", "required_set_bit": 1},
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
        },
        "summary": {
            "cases": len(cases),
            "static_bytes": 1330,
            "static_nodes": 404,
            "modeled_bytes": sum(SIZES[int(p, 16)] for p in union),
            "modeled_nodes": len(union),
            "forward_cases": len(cases),
            "backward_cases": 0,
            "actual_native_executions": 0,
            "calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "bounded_forward_MOVDQU_copy_graph_with_snapshot_oracle",
            "premises": [
                "Length is 32 through 127 and both exclusive buffer ends remain representable unsigned words",
                "Destination is at or below source or begins at or beyond the source exclusive end",
                "Entry DF is zero and stable mapped feature DWORD RVA 0x00493f30 has bit one set",
                "MOVDQU architectural execution and XMM register state are available under the declared instruction semantics",
                "All buffer byte alignments are permitted; accesses remain entirely inside the requested intervals",
                "Mapped payload is disjoint from stable protected caller frame, code and feature word; finite frame base is 0x30001000",
            ],
            "relation": "Destination equals original source snapshot and other payload bytes stay unchanged; each 32 byte iteration reads both 16 byte source halves before storing either half; EAX returns destination and saved GPRs restore",
            "xmm_relation": "XMM0 and XMM1 are the final original 32 byte block halves; XMM2 through XMM7 are preserved",
            "edx_relation": "EDX is zero when the scalar remainder is below four, otherwise the last original source DWORD in the scalar tail",
            "flags": "CF OF SF are zero and PF ZF are one; AF is undefined for remainder divisible by four and zero otherwise; DF remains zero",
            "not_claimed": [
                "Backward overlapping copy, aligned SIMD paths, other lengths or feature dispatch",
                "Any overread permission, actual native execution or global accounting promotion",
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
            "sealed scalar copy differs",
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
            "exact scalar copy differs",
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
