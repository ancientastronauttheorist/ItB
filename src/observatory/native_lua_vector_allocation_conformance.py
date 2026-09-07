"""Exact allocation-request decisions, without executing an allocator."""

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
from src.observatory.native_lua_vector_growth_conformance import _cmp_flags

ANALYSIS_KIND = "pe_native_lua_vector_allocation_conformance"
SEALED_SHA256 = "e76e77dec37818df255c4cde2c1fd1142628dc63be4b8bfbb02e79860b4b4cca"
START, END = 0x8A920, 0x8A97B
SMALL, LARGE, SIZE_FAILURE, PADDING_FAILURE = 0x8A963, 0x8A94B, 0x8A971, 0x8A976
STOPS = {SMALL, LARGE, SIZE_FAILURE, PADDING_FAILURE}
STACK, RETURN = 0x2000000, 0x4000000
MASK = 0xFFFFFFFF


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    counts = [
        0,
        1,
        2,
        255,
        510,
        511,
        512,
        513,
        514,
        0xFFFF,
        0x0FFFFFFF,
        0x10000000,
        0x1FFFFFFA,
        0x1FFFFFFB,
        0x1FFFFFFC,
        0x1FFFFFFD,
        0x1FFFFFFE,
        0x1FFFFFFF,
        0x20000000,
        0x80000000,
        0xFFFFFFFF,
    ]
    return [
        dict(count=n, alignment=a, seed=s)
        for n in counts
        for a in range(16)
        for s in [0, 1]
    ]


def oracle(count):
    _require(type(count) is int and 0 <= count <= MASK, "invalid count")
    # Partition derived from integer thresholds rather than replaying operations.
    if count == 0:
        return dict(
            path="zero_return",
            stop=None,
            requested=None,
            eax=0,
            ecx=0,
            flags=0x44,
            flag_mask=0x8C5,
            stack_delta=8,
        )
    if count > 0x1FFFFFFF:
        return dict(
            path="size_failure",
            stop=SIZE_FAILURE,
            requested=None,
            eax=count,
            ecx=None,
            flags=_cmp_flags(count, 0x1FFFFFFF),
            flag_mask=0x8D5,
            stack_delta=-4,
        )
    byte_count = count * 8
    if count < 512:
        return dict(
            path="small_request",
            stop=SMALL,
            requested=byte_count,
            eax=byte_count,
            ecx=None,
            flags=_cmp_flags(byte_count, 4096),
            flag_mask=0x8D5,
            stack_delta=-8,
        )
    padded = (byte_count + 35) & MASK
    failed = count >= 0x1FFFFFFC
    return dict(
        path="padding_failure" if failed else "large_request",
        stop=PADDING_FAILURE if failed else LARGE,
        requested=None if failed else padded,
        eax=byte_count,
        ecx=padded,
        flags=_cmp_flags(padded, byte_count),
        flag_mask=0x8D5,
        stack_delta=-4 if failed else -8,
    )


def _run_case(code, points, vector, *, negative=False):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    expected = oracle(vector["count"])
    entry = STACK + 0x2000 + vector["alignment"]
    seed = vector["seed"]
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    machine.mem_map(BASE + 0x8A000, 0x1000)
    machine.mem_write(BASE + START, code)
    machine.mem_map(STACK, 0x4000)
    machine.mem_map(RETURN, 0x1000)
    original = bytearray(
        ((i * 29) ^ (i >> 7) ^ 0xAD ^ seed) & 255 for i in range(0x4000)
    )
    original[entry - STACK : entry - STACK + 4] = RETURN.to_bytes(4, "little")
    original[entry - STACK + 4 : entry - STACK + 8] = vector["count"].to_bytes(
        4, "little"
    )
    machine.mem_write(STACK, bytes(original))
    registers = {
        "eax": x.UC_X86_REG_EAX,
        "ebx": x.UC_X86_REG_EBX,
        "ecx": x.UC_X86_REG_ECX,
        "edx": x.UC_X86_REG_EDX,
        "esi": x.UC_X86_REG_ESI,
        "edi": x.UC_X86_REG_EDI,
        "ebp": x.UC_X86_REG_EBP,
        "esp": x.UC_X86_REG_ESP,
    }
    initial = {
        name: (0x10203040 + i * 0x1111111 + seed) & MASK
        for i, name in enumerate(registers)
    }
    initial["esp"] = entry
    for name, value in initial.items():
        machine.reg_write(registers[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 2)
    if negative:
        machine.mem_write(entry + 4, (512).to_bytes(4, "little"))
    allowed = {int(p["rva"], 16) for p in points}
    visited, events, stopped = [], [], []

    def on_code(m, address, size, user):
        pc = address - BASE
        _require(pc in allowed, "execution escaped allocation body")
        if pc in STOPS:
            stopped.append(pc)
            m.emu_stop()
            return
        _require(pc <= 0x8A94A or pc == 0x8A962, "allocator return tail executed")
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, size, value, user):
        write = access == uc.UC_MEM_WRITE
        if write:
            _require(
                entry - 8 <= address and address + size <= entry,
                "write escaped save/request words",
            )
        else:
            _require(
                address in [entry - 4, entry, entry + 4] and size == 4,
                "unexpected stack read",
            )
        events.append(
            dict(
                access="write" if write else "read",
                address=address,
                width=size,
                value=(
                    value
                    if write
                    else int.from_bytes(m.mem_read(address, size), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    machine.emu_start(BASE + START, RETURN, count=100)
    _require(
        stopped == ([] if expected["stop"] is None else [expected["stop"]]),
        "request oracle frontier differs",
    )
    _require(
        machine.reg_read(x.UC_X86_REG_EIP)
        == (RETURN if expected["stop"] is None else BASE + expected["stop"]),
        "request oracle instruction pointer differs",
    )
    wanted = dict(initial, eax=expected["eax"], esp=entry + expected["stack_delta"])
    if expected["ecx"] is not None:
        wanted["ecx"] = expected["ecx"]
    if expected["stop"] is not None:
        wanted["ebp"] = entry - 4
    actual = {name: machine.reg_read(reg) for name, reg in registers.items()}
    _require(actual == wanted, "request oracle registers differ")
    actual_flags = machine.reg_read(x.UC_X86_REG_EFLAGS) & expected["flag_mask"]
    _require(actual_flags == expected["flags"], "request oracle defined flags differ")
    memory = bytearray(original)
    memory[entry - STACK - 4 : entry - STACK] = initial["ebp"].to_bytes(4, "little")
    expected_events = [
        dict(access="write", address=entry - 4, width=4, value=initial["ebp"]),
        dict(access="read", address=entry + 4, width=4, value=vector["count"]),
    ]
    if expected["requested"] is not None:
        memory[entry - STACK - 8 : entry - STACK - 4] = expected["requested"].to_bytes(
            4, "little"
        )
        expected_events.append(
            dict(
                access="write", address=entry - 8, width=4, value=expected["requested"]
            )
        )
    if expected["stop"] is None:
        expected_events += [
            dict(access="read", address=entry - 4, width=4, value=initial["ebp"]),
            dict(access="read", address=entry, width=4, value=RETURN),
        ]
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == bytes(memory), "full stack differs"
    )
    _require(events == expected_events, "ordered stack events differ")
    return dict(
        vector=vector,
        path=expected["path"],
        visited=visited,
        stop_rva=None if expected["stop"] is None else f"0x{expected['stop']:08x}",
        returned=expected["stop"] is None,
        registers=actual,
        flags=actual_flags,
        flag_mask=expected["flag_mask"],
        events_sha256=_canonical_sha256(events),
    )


def _build_unsealed(executable, semantics):
    from src.observatory import native_lua_vector_allocation_semantics as sem

    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "allocation semantics differs",
    )
    data, image, digest = _load_executable(executable)
    _require(capstone.__version__ == "5.0.7", "reviewed Capstone required")
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    offset = image.rva_to_file_offset(START)
    code = data[offset : offset + END - START]
    points = [
        _point(r)
        for r in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
            code, BASE + START
        )
    ]
    _require(
        len(points) == 34 and points == semantics["body"]["points"],
        "allocation body differs",
    )
    observations = [_run_case(code, points, v) for v in vectors()]
    caught = False
    try:
        _run_case(code, points, dict(count=511, alignment=0, seed=0), negative=True)
    except ConformanceError as exc:
        caught = "request oracle frontier" in str(exc)
    _require(caught, "changed count control accepted")
    visited = sorted({pc for row in observations for pc in row["visited"]})
    _require(len(visited) == 19, "decision coverage differs")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=semantics["build_identity"],
        source_semantics_sha256=sem.SEALED_SHA256,
        body=dict(
            entry_rva=f"0x{START:08x}",
            exclusive_end_rva=f"0x{END:08x}",
            bytes=91,
            nodes=34,
            points=points,
            sha256=hashlib.sha256(code).hexdigest(),
        ),
        emulator=dict(
            name="Unicorn", version="2.1.4", architecture="x86", mode_bits=32
        ),
        decoder=dict(name="Capstone", version="5.0.7"),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=visited,
        summary=dict(
            cases=len(observations),
            executed_instruction_sites=len(visited),
            outcomes={
                path: sum(r["path"] == path for r in observations)
                for path in [
                    "zero_return",
                    "small_request",
                    "large_request",
                    "size_failure",
                    "padding_failure",
                ]
            },
            executed_calls=0,
            negative_controls=1,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact bounded allocation request decisions and call-free zero return match an independent threshold oracle",
            call_stops=[f"0x{p:08x}" for p in sorted(STOPS)],
            call_instructions_executed=False,
            zero_flags="CF PF ZF SF OF compared; AF undefined after XOR and deliberately excluded",
            other_flags="CF PF AF ZF SF OF from final CMP compared",
            memory="Full stack and exact ordered accesses checked, including caller return and count word",
            not_claimed=[
                "Allocator or failure callee execution",
                "Postallocator pointer alignment and memory writes",
                "Whole resize or owner execution",
                "Whole-game accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, semantics):
    from src.observatory import native_lua_vector_allocation_semantics as sem

    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "sealed allocation replay differs",
    )
    _require(
        evidence["source_semantics_sha256"] == sem.SEALED_SHA256
        and evidence["vectors"] == vectors(),
        "replay source differs",
    )
    _assert_publication_safe(evidence)
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
        "exact replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
