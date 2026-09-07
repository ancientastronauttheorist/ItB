"""Backward overlapping large MOVDQU copy paths with an independent snapshot oracle."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import capstone
import capstone.x86_const as x86
from src.observatory import native_backward_simd_copy_semantics as prior
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
ANALYSIS_KIND = "pe_native_large_backward_simd_copy_semantics"
SEALED_SHA256 = "d111aeafa33b9eb54197008e27fb44b97c3151a3a726909637e32ab1ead9de57"
SOURCE_PINS = {
    "program_facts": resize.SOURCE_PINS["program_facts"],
    "backward_simd_copy_semantics": (prior.ANALYSIS_KIND, prior.SEALED_SHA256),
}
START = 0x36E580
SCALAR_RANGES = ((3597696, 3597728), (3598388, 3598417), (3598565, 3598795))
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
    3598388: ("lea", ("reg", "esi"), ("mem", "ecx", 0, "esi", 4, 1)),
    3598391: ("lea", ("reg", "edi"), ("mem", "ecx", 0, "edi", 4, 1)),
    3598394: ("cmp", ("reg", "ecx"), ("imm", 32)),
    3598397: ("jb", ("imm", 7793044)),
    3598403: ("bt", ("mem", None, 8994608, None, 4, 1), ("imm", 1)),
    3598411: ("jb", ("imm", 7792869)),
    3598565: ("test", ("reg", "edi"), ("imm", 15)),
    3598571: ("je", ("imm", 7792892)),
    3598573: ("dec", ("reg", "ecx")),
    3598574: ("dec", ("reg", "esi")),
    3598575: ("dec", ("reg", "edi")),
    3598576: ("mov", ("reg", "al"), ("mem", "esi", 0, None, 1, 1)),
    3598578: ("mov", ("mem", "edi", 0, None, 1, 1), ("reg", "al")),
    3598580: ("test", ("reg", "edi"), ("imm", 15)),
    3598586: ("jne", ("imm", 7792877)),
    3598588: ("cmp", ("reg", "ecx"), ("imm", 128)),
    3598594: ("jb", ("imm", 7793004)),
    3598596: ("sub", ("reg", "esi"), ("imm", 128)),
    3598602: ("sub", ("reg", "edi"), ("imm", 128)),
    3598608: ("movdqu", ("reg", "xmm0"), ("mem", "esi", 0, None, 16, 1)),
    3598612: ("movdqu", ("reg", "xmm1"), ("mem", "esi", 16, None, 16, 1)),
    3598617: ("movdqu", ("reg", "xmm2"), ("mem", "esi", 32, None, 16, 1)),
    3598622: ("movdqu", ("reg", "xmm3"), ("mem", "esi", 48, None, 16, 1)),
    3598627: ("movdqu", ("reg", "xmm4"), ("mem", "esi", 64, None, 16, 1)),
    3598632: ("movdqu", ("reg", "xmm5"), ("mem", "esi", 80, None, 16, 1)),
    3598637: ("movdqu", ("reg", "xmm6"), ("mem", "esi", 96, None, 16, 1)),
    3598642: ("movdqu", ("reg", "xmm7"), ("mem", "esi", 112, None, 16, 1)),
    3598647: ("movdqu", ("mem", "edi", 0, None, 16, 1), ("reg", "xmm0")),
    3598651: ("movdqu", ("mem", "edi", 16, None, 16, 1), ("reg", "xmm1")),
    3598656: ("movdqu", ("mem", "edi", 32, None, 16, 1), ("reg", "xmm2")),
    3598661: ("movdqu", ("mem", "edi", 48, None, 16, 1), ("reg", "xmm3")),
    3598666: ("movdqu", ("mem", "edi", 64, None, 16, 1), ("reg", "xmm4")),
    3598671: ("movdqu", ("mem", "edi", 80, None, 16, 1), ("reg", "xmm5")),
    3598676: ("movdqu", ("mem", "edi", 96, None, 16, 1), ("reg", "xmm6")),
    3598681: ("movdqu", ("mem", "edi", 112, None, 16, 1), ("reg", "xmm7")),
    3598686: ("sub", ("reg", "ecx"), ("imm", 128)),
    3598692: ("test", ("reg", "ecx"), ("imm", 4294967168)),
    3598698: ("jne", ("imm", 7792892)),
    3598700: ("cmp", ("reg", "ecx"), ("imm", 32)),
    3598703: ("jb", ("imm", 7793044)),
    3598705: ("sub", ("reg", "esi"), ("imm", 32)),
    3598708: ("sub", ("reg", "edi"), ("imm", 32)),
    3598711: ("movdqu", ("reg", "xmm0"), ("mem", "esi", 0, None, 16, 1)),
    3598715: ("movdqu", ("reg", "xmm1"), ("mem", "esi", 16, None, 16, 1)),
    3598720: ("movdqu", ("mem", "edi", 0, None, 16, 1), ("reg", "xmm0")),
    3598724: ("movdqu", ("mem", "edi", 16, None, 16, 1), ("reg", "xmm1")),
    3598729: ("sub", ("reg", "ecx"), ("imm", 32)),
    3598732: ("test", ("reg", "ecx"), ("imm", 4294967264)),
    3598738: ("jne", ("imm", 7793009)),
    3598740: ("test", ("reg", "ecx"), ("imm", 4294967292)),
    3598746: ("je", ("imm", 7793073)),
    3598748: ("sub", ("reg", "edi"), ("imm", 4)),
    3598751: ("sub", ("reg", "esi"), ("imm", 4)),
    3598754: ("mov", ("reg", "eax"), ("mem", "esi", 0, None, 4, 1)),
    3598756: ("mov", ("mem", "edi", 0, None, 4, 1), ("reg", "eax")),
    3598758: ("sub", ("reg", "ecx"), ("imm", 4)),
    3598761: ("test", ("reg", "ecx"), ("imm", 4294967292)),
    3598767: ("jne", ("imm", 7793052)),
    3598769: ("test", ("reg", "ecx"), ("reg", "ecx")),
    3598771: ("je", ("imm", 7793092)),
    3598773: ("sub", ("reg", "edi"), ("imm", 1)),
    3598776: ("sub", ("reg", "esi"), ("imm", 1)),
    3598779: ("mov", ("reg", "al"), ("mem", "esi", 0, None, 1, 1)),
    3598781: ("mov", ("mem", "edi", 0, None, 1, 1), ("reg", "al")),
    3598783: ("sub", ("reg", "ecx"), ("imm", 1)),
    3598786: ("jne", ("imm", 7793077)),
    3598788: ("mov", ("reg", "eax"), ("mem", "esp", 12, None, 4, 1)),
    3598792: ("pop", ("reg", "esi")),
    3598793: ("pop", ("reg", "edi")),
    3598794: ("ret",),
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
    3598388: 3,
    3598391: 3,
    3598394: 3,
    3598397: 6,
    3598403: 8,
    3598411: 6,
    3598565: 6,
    3598571: 2,
    3598573: 1,
    3598574: 1,
    3598575: 1,
    3598576: 2,
    3598578: 2,
    3598580: 6,
    3598586: 2,
    3598588: 6,
    3598594: 2,
    3598596: 6,
    3598602: 6,
    3598608: 4,
    3598612: 5,
    3598617: 5,
    3598622: 5,
    3598627: 5,
    3598632: 5,
    3598637: 5,
    3598642: 5,
    3598647: 4,
    3598651: 5,
    3598656: 5,
    3598661: 5,
    3598666: 5,
    3598671: 5,
    3598676: 5,
    3598681: 5,
    3598686: 6,
    3598692: 6,
    3598698: 2,
    3598700: 3,
    3598703: 2,
    3598705: 3,
    3598708: 3,
    3598711: 4,
    3598715: 5,
    3598720: 4,
    3598724: 5,
    3598729: 3,
    3598732: 6,
    3598738: 2,
    3598740: 6,
    3598746: 2,
    3598748: 3,
    3598751: 3,
    3598754: 2,
    3598756: 2,
    3598758: 3,
    3598761: 6,
    3598767: 2,
    3598769: 2,
    3598771: 2,
    3598773: 3,
    3598776: 3,
    3598779: 2,
    3598781: 2,
    3598783: 3,
    3598786: 2,
    3598788: 4,
    3598792: 1,
    3598793: 1,
    3598794: 1,
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
    3598388: [4, 4],
    3598391: [4, 4],
    3598394: [4, 4],
    3598397: [4],
    3598403: [4, 1],
    3598411: [4],
    3598565: [4, 4],
    3598571: [4],
    3598573: [4],
    3598574: [4],
    3598575: [4],
    3598576: [1, 1],
    3598578: [1, 1],
    3598580: [4, 4],
    3598586: [4],
    3598588: [4, 4],
    3598594: [4],
    3598596: [4, 4],
    3598602: [4, 4],
    3598608: [16, 16],
    3598612: [16, 16],
    3598617: [16, 16],
    3598622: [16, 16],
    3598627: [16, 16],
    3598632: [16, 16],
    3598637: [16, 16],
    3598642: [16, 16],
    3598647: [16, 16],
    3598651: [16, 16],
    3598656: [16, 16],
    3598661: [16, 16],
    3598666: [16, 16],
    3598671: [16, 16],
    3598676: [16, 16],
    3598681: [16, 16],
    3598686: [4, 4],
    3598692: [4, 4],
    3598698: [4],
    3598700: [4, 4],
    3598703: [4],
    3598705: [4, 4],
    3598708: [4, 4],
    3598711: [16, 16],
    3598715: [16, 16],
    3598720: [16, 16],
    3598724: [16, 16],
    3598729: [4, 4],
    3598732: [4, 4],
    3598738: [4],
    3598740: [4, 4],
    3598746: [4],
    3598748: [4, 4],
    3598751: [4, 4],
    3598754: [4, 4],
    3598756: [4, 4],
    3598758: [4, 4],
    3598761: [4, 4],
    3598767: [4],
    3598769: [4, 4],
    3598771: [4],
    3598773: [4, 4],
    3598776: [4, 4],
    3598779: [1, 1],
    3598781: [1, 1],
    3598783: [4, 4],
    3598786: [4],
    3598788: [4, 4],
    3598792: [4],
    3598793: [4],
    3598794: [],
}


class LargeBackwardSimdCopyError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise LargeBackwardSimdCopyError(message)


def _normalize(fn):
    try:
        return fn()
    except LargeBackwardSimdCopyError:
        raise
    except Exception as exc:
        raise LargeBackwardSimdCopyError(str(exc)) from exc


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
        128 <= length <= 2048
        and source + length <= U32
        and destination + length <= U32,
        "outside bounded byte copy domain",
    )
    _require(
        source < destination < source + length,
        "outside strict backward overlap domain",
    )
    _require(
        feature_word & 2 and type(df) is int and df == 0,
        "byte dispatch premises differ",
    )
    return dict(
        direction="backward",
        destination=destination,
        source=source,
        length=length,
        arithmetic_flags=dict(
            cf=0,
            zf=1,
            pf=1,
            af=None if (length - ((destination + length) & 15)) % 4 == 0 else 0,
            sf=0,
            of=0,
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
    edx = length
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
    destination_offset=2049,
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
    destination_offset=2049,
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
        _require(pc in operations and len(trace) < 1000, "copy escaped scalar domain")
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
            raise LargeBackwardSimdCopyError("unsupported scalar operation")
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

    position = length
    while (destination + position) & 15:
        position -= 1
        value = original(position, 1)
        expect("read", source + position, 1, value)
        expect("write", destination + position, 1, value)
    wanted_xmm = dict(fixture["xmm"])
    while position >= 128:
        position -= 128
        for offset in range(0, 128, 16):
            expect(
                "read", source + position + offset, 16, original(position + offset, 16)
            )
        for offset in range(0, 128, 16):
            expect(
                "write",
                destination + position + offset,
                16,
                original(position + offset, 16),
            )
            wanted_xmm[f"xmm{offset//16}"] = original(position + offset, 16)
    while position >= 32:
        position -= 32
        expect("read", source + position, 16, original(position, 16))
        expect("read", source + position + 16, 16, original(position + 16, 16))
        expect("write", destination + position, 16, original(position, 16))
        expect("write", destination + position + 16, 16, original(position + 16, 16))
        wanted_xmm.update(xmm0=original(position, 16), xmm1=original(position + 16, 16))
    while position >= 4:
        position -= 4
        value = original(position, 4)
        expect("read", source + position, 4, value)
        expect("write", destination + position, 4, value)
    while position:
        position -= 1
        value = original(position, 1)
        expect("read", source + position, 1, value)
        expect("write", destination + position, 1, value)
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
                raise LargeBackwardSimdCopyError("unexpected instruction operand")
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
        ranges == sources["backward_simd_copy_semantics"]["body"]["ranges"],
        "source full body witness differs",
    )
    lengths = [
        128,
        129,
        142,
        143,
        144,
        145,
        159,
        160,
        255,
        256,
        257,
        511,
        512,
        513,
        1023,
        1024,
        1025,
        2047,
        2048,
    ]
    vectors = [
        dict(
            length=n,
            source_offset=2052 + a,
            destination_offset=2052 + a + delta,
            frame_alignment=frame,
            feature_word=word,
        )
        for n in lengths
        for a in range(16)
        for delta in (1, 3, 17, 127)
        for frame in (0, 15)
        for word in (2, 0xFFFFFFFF)
    ]
    cases = []
    for vector in vectors:
        case = model_case(**vector)
        cases.append(
            dict(sha256=_canonical_sha256(case), trace_rvas=case["trace_rvas"])
        )
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(
        union == [f"0x{pc:08x}" for pc in ORDER], "large backward SIMD coverage differs"
    )
    controls = []
    for name, pc, replacement in [
        (
            "wrong_eighth_vector_source",
            0x36E932,
            ("movdqu", R("xmm7"), M("esi", 113, width=16)),
        ),
        (
            "wrong_eighth_vector_store",
            0x36E959,
            ("movdqu", M("edi", 112, width=16), R("xmm6")),
        ),
        ("wrong_block_step", 0x36E904, ("sub", R("esi"), I(127))),
    ]:
        changed = dict(OPS)
        changed[pc] = replacement
        try:
            model_case(512, 2052, 2053, ops=changed)
        except LargeBackwardSimdCopyError:
            controls.append(dict(name=name, rejected=True))
        else:
            raise LargeBackwardSimdCopyError("large backward SIMD mutation accepted")
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
            "forward_cases": 0,
            "backward_cases": len(cases),
            "actual_native_executions": 0,
            "calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "bounded_large_backward_MOVDQU_copy_graph_with_snapshot_oracle",
            "premises": [
                "Length is 128 through 2048 and source is below destination below source exclusive end; both exclusive ends are representable unsigned words",
                "Entry DF is zero and stable feature DWORD RVA 0x00493f30 has bit one set",
                "MOVDQU architectural execution and XMM register state are available",
                "Mapped payload source and destination may overlap but are disjoint from stable protected frame, code and feature word",
                "All byte alignments allowed without overread; finite frame base is 0x30001000",
            ],
            "relation": "Suffix bytes align the destination exclusive end to 16; descending 128 byte blocks load all eight source vectors before any of their stores; descending 32 byte blocks and scalar tail complete the original snapshot copy",
            "xmm_relation": "Each full 128 byte block replaces XMM0 through XMM7 with its original source vectors; each later 32 byte block replaces only XMM0 and XMM1; registers with no replacing block preserve their entry values",
            "registers": "EAX returns destination, ECX is zero, EDX remains length, other GPRs restore and cdecl ESP advances four",
            "flags": "CF OF SF zero and PF ZF one; AF undefined when post-alignment count is divisible by four, zero otherwise; DF stays clear",
            "not_claimed": [
                "Forward copy, other feature paths, greater lengths, or overread permissions",
                "Actual native execution, whole routine equivalence or global accounting promotion",
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
