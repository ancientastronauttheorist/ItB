"""Exact bounded x86 append replay with a declared, unexecuted growth summary."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _load_executable,
    _point,
    _canonical_bytes,
    _canonical_sha256,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "pe_native_lua_class_vector_append_conformance"
SEALED_SHA256 = "f5fad9a1bf7b10cb90fb6731a47906592f80089caa4805592d2ad0e7ce75075a"
START, STOP = 0x2EB1BB, 0x2EB21A
DATA = 0x4000000
OBJECT = 0x3000000
STACK = 0x2000000


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    b = DATA + 0x1000
    n = DATA + 0x3000
    specs = [
        ("internal", b, b + 16, b + 32, b + 8, b, b + 16),
        ("unaligned_internal", b, b + 16, b + 32, b + 9, b, b + 16),
        ("external_before", b, b + 16, b + 32, DATA + 0x800, b, b + 16),
        ("external_after", b, b + 16, b + 32, b + 24, b, b + 16),
        ("destination_alias", b, b + 16, b + 32, b + 16, b, b + 16),
        ("ordered_overlap", b, b, b + 16, b - 4, b, b),
        ("null_destination", 0, 0, 8, DATA + 0x800, 0, 0),
        ("internal_growth", b, b + 16, b + 16, b + 8, n, n + 16),
        ("external_growth", b, b + 16, b + 16, DATA + 0x800, n, n + 16),
    ]
    return [
        dict(
            name=name,
            alignment=a,
            begin=B,
            end=E,
            capacity=C,
            argument=A,
            post_begin=P,
            post_end=Q,
        )
        for name, B, E, C, A, P, Q in specs
        for a in range(16)
    ]


def oracle(vector, initial):
    v = vector
    result = bytearray(initial)
    B, E, A = v["begin"], v["end"], v["argument"]
    growth = E == v["capacity"]
    internal = B <= A < E
    P, Q = v["post_begin"], v["post_end"]
    if growth:
        result[P - DATA : P - DATA + E - B] = initial[B - DATA : E - DATA]
    displacement = (A - B) & 0xFFFFFFFF
    signed = displacement if displacement < 0x80000000 else displacement - 0x100000000
    source = ((P + 8 * (signed >> 3)) & 0xFFFFFFFF) if internal else A
    reads = []
    if Q:
        for delta in (0, 4):
            at = source + delta - DATA
            to = Q + delta - DATA
            _require(
                0 <= at <= len(result) - 4 and 0 <= to <= len(result) - 4,
                "oracle memory outside data",
            )
            word = bytes(result[at : at + 4])
            reads.append(int.from_bytes(word, "little"))
            result[to : to + 4] = word
    return dict(
        memory=bytes(result),
        end_after=(Q + 8) & 0xFFFFFFFF,
        internal=internal,
        index=signed >> 3 if internal else None,
        source=source,
        copy_values=reads,
        growth=growth,
    )


def _run_case(code, points, vector, *, negative=False):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn 2.1.4 required")
    v = vector
    F = STACK + 0x2000 + v["alignment"]
    O = OBJECT + 0x100
    original = bytes(((i * 37) ^ ((i >> 8) * 19) ^ 0x53) % 256 for i in range(0x10000))
    expected = oracle(v, original)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    machine.mem_map(BASE + 0x2EB000, 0x1000)
    machine.mem_write(BASE + START, code)
    machine.mem_map(STACK, 0x4000)
    machine.mem_map(OBJECT, 0x1000)
    machine.mem_map(DATA, 0x10000)
    machine.mem_write(DATA, original)

    def word(address, value):
        machine.mem_write(address, int(value & 0xFFFFFFFF).to_bytes(4, "little"))

    word(F - 12, O)
    for off, key in [(4, "begin"), (8, "end"), (12, "capacity")]:
        word(O + off, v[key])
    initial_regs = {
        x.UC_X86_REG_EBP: F,
        x.UC_X86_REG_ESP: F - 32,
        x.UC_X86_REG_EDI: v["argument"],
        x.UC_X86_REG_EBX: 0x12345678,
        x.UC_X86_REG_ESI: 0x23456789,
        x.UC_X86_REG_EAX: 0x3456789A,
        x.UC_X86_REG_ECX: 0x456789AB,
        x.UC_X86_REG_EDX: 0x56789ABC,
        x.UC_X86_REG_EFLAGS: 2,
    }
    for reg, value in initial_regs.items():
        machine.reg_write(reg, value)
    if negative:
        machine.reg_write(x.UC_X86_REG_EDI, v["argument"] + 4)
    visited = []
    growth_calls = []
    events = []
    allowed = {int(p["rva"], 16) for p in points}

    def on_code(m, address, size, user):
        pc = address - BASE
        _require(pc in allowed, "execution escaped sealed append interval")
        visited.append(f"0x{pc:08x}")
        if pc in (0x2EB1DA, 0x2EB200):
            _require(expected["growth"] and not growth_calls, "unexpected growth call")
            _require(
                m.reg_read(x.UC_X86_REG_ECX) == O + 4
                and m.reg_read(x.UC_X86_REG_ESP) == F - 36,
                "growth ABI differs",
            )
            growth_calls.append(f"0x{pc:08x}")
            if v["end"] > v["begin"]:
                m.mem_write(
                    v["post_begin"],
                    bytes(m.mem_read(v["begin"], v["end"] - v["begin"])),
                )
                m.mem_protect(v["begin"] & ~0xFFF, 0x1000, uc.UC_PROT_NONE)
            word(O + 4, v["post_begin"])
            word(O + 8, v["post_end"])
            word(O + 12, v["post_end"] + 16)
            # CALL itself is skipped. Discard its already-pushed four-byte
            # argument, matching the abstract callee's RET 4 contract.
            m.reg_write(x.UC_X86_REG_ESP, F - 32)
            m.reg_write(x.UC_X86_REG_EAX, 0xAABBCCDD)
            m.reg_write(x.UC_X86_REG_ECX, 0xBBCCDDEE)
            m.reg_write(x.UC_X86_REG_EDX, 0xCCDDEEFF)
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            m.reg_write(x.UC_X86_REG_EIP, address + 5)

    def memory(m, access, address, size, value, user):
        valid = (
            STACK <= address
            and address + size <= STACK + 0x4000
            or OBJECT <= address
            and address + size <= OBJECT + 0x1000
            or DATA <= address
            and address + size <= DATA + 0x10000
        )
        _require(valid, "unexpected data access")
        events.append([int(access), address, size])

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, memory)
    machine.emu_start(BASE + START, BASE + STOP, count=100)
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == BASE + STOP, "exclusive stop not reached"
    )
    if expected["growth"]:
        machine.mem_protect(v["begin"] & ~0xFFF, 0x1000, uc.UC_PROT_ALL)
    actual = bytes(machine.mem_read(DATA, len(original)))
    _require(actual == expected["memory"], "independent ordered memory oracle differs")
    _require(
        int.from_bytes(machine.mem_read(O + 8, 4), "little") == expected["end_after"],
        "end update differs",
    )
    object_expected = bytearray(0x1000)
    for at, value in [
        (0x104, v["post_begin"]),
        (0x108, expected["end_after"]),
        (0x10C, v["post_end"] + 16 if expected["growth"] else v["capacity"]),
    ]:
        object_expected[at : at + 4] = value.to_bytes(4, "little")
    _require(
        bytes(machine.mem_read(OBJECT, 0x1000)) == bytes(object_expected),
        "object metadata changed unexpectedly",
    )
    frame_expected = bytearray(48)
    frame_expected[20:24] = O.to_bytes(4, "little")
    _require(
        bytes(machine.mem_read(F - 32, 48)) == bytes(frame_expected),
        "protected frame changed",
    )
    _require(
        machine.reg_read(x.UC_X86_REG_ESP) == F - 32
        and machine.reg_read(x.UC_X86_REG_EBP) == F
        and machine.reg_read(x.UC_X86_REG_ESI) == O
        and machine.reg_read(x.UC_X86_REG_EBX) == 0x12345678,
        "preserved slice registers differ",
    )
    _require(
        machine.reg_read(x.UC_X86_REG_EDI)
        == (
            (expected["index"] & 0xFFFFFFFF) if expected["internal"] else v["argument"]
        ),
        "saved alias index differs",
    )
    _require(len(growth_calls) == int(expected["growth"]), "growth count differs")
    return dict(
        vector=v,
        visited=visited,
        growth_calls=growth_calls,
        memory_sha256=hashlib.sha256(actual).hexdigest(),
        events_sha256=_canonical_sha256(events),
        end_after=expected["end_after"],
    )


def _build_unsealed(executable, semantics):
    from src.observatory import native_lua_class_vector_append_semantics as sem

    _validate_json_tree(semantics, "semantics")
    _require(_canonical_sha256(semantics) == sem.SEALED_SHA256, "append source differs")
    data, image, digest = _load_executable(executable)
    _require(capstone.__version__ == "5.0.7", "reviewed Capstone version required")
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    offset = image.rva_to_file_offset(START)
    code = data[offset : offset + STOP - START]
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    rows = list(decoder.disasm(code, BASE + START))
    points = [_point(r) for r in rows]
    _require(
        len(rows) == 36 and sum(r.size for r in rows) == 95, "append decode differs"
    )
    _require(points == semantics["slice"]["points"], "sealed append points differ")
    observations = [_run_case(code, points, v) for v in vectors()]
    caught = False
    try:
        _run_case(
            code,
            points,
            next(v for v in vectors() if v["name"] == "external_before"),
            negative=True,
        )
    except ConformanceError as exc:
        caught = "ordered memory oracle" in str(exc)
    _require(caught, "negative oracle control was not rejected")
    visited = sorted({pc for r in observations for pc in r["visited"]})
    _require(
        visited == sorted(p["rva"] for p in points), "instruction coverage differs"
    )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=semantics["build_identity"],
        source_semantics_sha256=sem.SEALED_SHA256,
        emulator=dict(
            name="Unicorn", version="2.1.4", architecture="x86", mode_bits=32
        ),
        decoder=dict(name="Capstone", version="5.0.7"),
        slice=dict(
            start_rva=f"0x{START:08x}",
            exclusive_stop_rva=f"0x{STOP:08x}",
            points=points,
            bytes=95,
        ),
        vectors=vectors(),
        growth_summary=dict(
            call_instruction_executed=False,
            entry_esp_F_offset=-36,
            return_esp_F_offset=-32,
            effect="Copy old element byte range to declared post_begin before making old page inaccessible",
            field_outputs={
                "begin": "vector post_begin",
                "end": "vector post_end",
                "capacity": "post_end plus sixteen",
            },
            preserved_registers=["ebx", "esi", "edi", "ebp"],
            protected_memory="All memory except relocated payload, three vector fields and inaccessible old payload page",
            volatile_outputs={
                "eax": 0xAABBCCDD,
                "ecx": 0xBBCCDDEE,
                "edx": 0xCCDDEEFF,
                "eflags": 0x246,
            },
            continuation="Instruction immediately following intercepted CALL",
        ),
        observations_sha256=_canonical_sha256(observations),
        visited_rvas=visited,
        summary=dict(
            cases=len(observations),
            visited_instruction_sites=len(visited),
            executed_noncall_instruction_sites=len(visited) - 2,
            summarized_call_sites=2,
            growth_summaries=sum(len(r["growth_calls"]) for r in observations),
            actual_growth_helper_executions=0,
            negative_controls=1,
        ),
        scope=dict(
            claim="Bounded exact x86 append replay against independent ordered byte oracle",
            growth="At two CALL sites skip call and simulate explicitly declared relocating growth summary; real helper not executed",
            relocation_guard="Old payload page becomes inaccessible after abstract growth until replay stops",
            cases="Mapped ordinary machine states include unaligned internal input, null destination and external overlap; not all are valid C++ object states",
            not_claimed=[
                "Real growth implementation or allocator behavior",
                "Whole enclosing owner execution",
                "Native object validity or universal pointer domains",
                "Whole-game accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, semantics):
    from src.observatory import native_lua_class_vector_append_semantics as sem

    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "sealed conformance source differs",
    )
    _require(
        evidence["source_semantics_sha256"] == sem.SEALED_SHA256
        and evidence["vectors"] == vectors(),
        "conformance vector partition differs",
    )
    return dict(
        status="structurally_verified",
        evidence_sha256=SEALED_SHA256,
        summary=evidence["summary"],
    )


def build_conformance(executable, semantics):
    result = _build_unsealed(executable, semantics)
    validate_structure(result, semantics)
    return result


def validate_conformance(executable, evidence, semantics):
    validate_structure(evidence, semantics)
    _require(
        _canonical_bytes(build_conformance(executable, semantics))
        == _canonical_bytes(evidence),
        "exact append replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
