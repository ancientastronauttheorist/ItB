"""Integrated vector allocation replay through one supplied successful heap response."""

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
from src.observatory.native_lua_vector_allocation_return_conformance import _add_flags

ANALYSIS_KIND = "pe_native_vector_allocation_conformance"
SEALED_SHA256 = "8a2af8e009d4f67b672e92e9fd12bce6a5c32feb609af95f2ee1dc61fb1e9d29"
BODIES = {
    "allocation": (0x8A920, 0x8A97B),
    "retry": (0x3574DB, 0x35750E),
    "thunk": (0x379F52, 0x379F5D),
    "heap_wrapper": (0x38942B, 0x389479),
}
STACK, RETURN, IMPORT, DATA = 0x2000000, 0x4000000, 0x5000000, 0x6000000
HEAP_GLOBAL, IAT = BASE + 0x4B7634, BASE + 0x3D6220
HEAP_HANDLE = 0x12345678


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    return [dict(count=0, pointer=DATA + 0x100, alignment=a) for a in range(16)] + [
        dict(count=n, pointer=DATA + 0x100 + p, alignment=a)
        for n in [1, 511, 512, 513, 1024]
        for p in range(32)
        for a in range(16)
    ]


def successful_oracle(count, pointer):
    _require(type(count) is int and 0 <= count <= 1024, "outside bounded count domain")
    _require(
        type(pointer) is int and DATA <= pointer < DATA + 0x4000,
        "outside supplied allocation buffer",
    )
    if count == 0:
        return dict(result=0, request=None, metadata=None)
    request = count * 8 + (35 if count >= 512 else 0)
    _require(pointer + request <= DATA + 0x4000, "supplied writable block too short")
    result = 32 * ((pointer + 35) // 32) if count >= 512 else pointer
    return dict(
        result=result, request=request, metadata=result - 4 if count >= 512 else None
    )


def _expected(vector, initial, original_stack, original_data):
    expected = successful_oracle(vector["count"], vector["pointer"])
    entry = initial["esp"]
    stack = bytearray(original_stack)
    payload = bytearray(original_data)
    events = []

    def read(address, value):
        events.append(dict(access="read", address=address, width=4, value=value))

    def write(address, value):
        target, base = (
            (stack, STACK) if STACK <= address < STACK + 0x4000 else (payload, DATA)
        )
        target[address - base : address - base + 4] = value.to_bytes(4, "little")
        events.append(dict(access="write", address=address, width=4, value=value))

    write(entry - 4, initial["ebp"])
    read(entry + 4, vector["count"])
    if expected["request"] is not None:
        requested = expected["request"]
        continuation = BASE + (0x8A950 if vector["count"] >= 512 else 0x8A968)
        write(entry - 8, requested)
        write(entry - 12, continuation)
        write(entry - 16, entry - 4)
        read(entry - 8, requested)
        write(entry - 20, requested)
        write(entry - 24, BASE + 0x357507)
        write(entry - 28, entry - 16)
        read(entry - 28, entry - 16)
        write(entry - 28, entry - 16)
        write(entry - 32, initial["esi"])
        read(entry - 20, requested)
        write(entry - 36, requested)
        write(entry - 40, 0)
        read(HEAP_GLOBAL, HEAP_HANDLE)
        write(entry - 44, HEAP_HANDLE)
        read(IAT, IMPORT)
        write(entry - 48, BASE + 0x389463)
        read(entry - 32, initial["esi"])
        read(entry - 28, entry - 16)
        read(entry - 24, BASE + 0x357507)
        read(entry - 20, requested)
        read(entry - 16, entry - 4)
        read(entry - 12, continuation)
        if expected["metadata"] is not None:
            write(expected["metadata"], vector["pointer"])
    read(entry - 4, initial["ebp"])
    read(entry, RETURN)
    regs = dict(initial, eax=expected["result"], ecx=expected["result"], esp=entry + 8)
    if expected["request"] is not None:
        regs["edx"] = 0xB0000001
    if vector["count"] == 0:
        flags, mask = 0x44, 0x8C5
    elif expected["metadata"] is not None:
        q = expected["result"]
        flags = (
            (int(q == 0) << 6)
            | ((q >> 31) << 7)
            | (int((q & 255).bit_count() % 2 == 0) << 2)
        )
        mask = 0x8C5
    else:
        flags, mask = _add_flags(entry - 8, 4), 0x8D5
    return dict(
        relation=expected,
        registers=regs,
        flags=flags,
        flag_mask=mask,
        stack=bytes(stack),
        payload=bytes(payload),
        events=events,
    )


def _run_case(codes, points, vector, *, negative=False):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for name, (start, end) in BODIES.items():
        machine.mem_map(BASE + (start & ~0xFFF), 0x1000)
        machine.mem_write(BASE + start, codes[name])
    for page, length in [
        (STACK, 0x4000),
        (DATA, 0x4000),
        (RETURN, 0x1000),
        (IMPORT, 0x2000),
        (IAT & ~0xFFF, 0x1000),
        (HEAP_GLOBAL & ~0xFFF, 0x1000),
    ]:
        machine.mem_map(page, length)
    entry = STACK + 0x2000 + vector["alignment"]
    original_stack = bytearray(
        ((i * 19) ^ (i >> 6) ^ 0xD3) & 255 for i in range(0x4000)
    )
    original_stack[entry - STACK : entry - STACK + 4] = RETURN.to_bytes(4, "little")
    original_stack[entry - STACK + 4 : entry - STACK + 8] = vector["count"].to_bytes(
        4, "little"
    )
    original_data = bytes(((i * 41) ^ (i >> 5) ^ 0x65) & 255 for i in range(0x4000))
    machine.mem_write(STACK, bytes(original_stack))
    machine.mem_write(DATA, original_data)
    iat = bytearray(0x1000)
    iat[IAT & 0xFFF : (IAT & 0xFFF) + 4] = IMPORT.to_bytes(4, "little")
    global_bytes = bytearray(0x1000)
    global_bytes[HEAP_GLOBAL & 0xFFF : (HEAP_GLOBAL & 0xFFF) + 4] = (
        HEAP_HANDLE.to_bytes(4, "little")
    )
    machine.mem_write(IAT & ~0xFFF, bytes(iat))
    machine.mem_write(HEAP_GLOBAL & ~0xFFF, bytes(global_bytes))
    ids = {
        "eax": x.UC_X86_REG_EAX,
        "ebx": x.UC_X86_REG_EBX,
        "ecx": x.UC_X86_REG_ECX,
        "edx": x.UC_X86_REG_EDX,
        "esi": x.UC_X86_REG_ESI,
        "edi": x.UC_X86_REG_EDI,
        "ebp": x.UC_X86_REG_EBP,
        "esp": x.UC_X86_REG_ESP,
    }
    initial = {name: 0x16273849 + i * 0x1010101 for i, name in enumerate(ids)}
    initial["esp"] = entry
    expected = _expected(vector, initial, original_stack, original_data)
    for name, value in initial.items():
        machine.reg_write(ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 2)
    allowed = {int(p["rva"], 16) for rows in points.values() for p in rows}
    visited, events, summaries = [], [], []
    resume_at = None

    def on_code(m, address, size, user):
        nonlocal resume_at
        if address == IMPORT:
            _require(
                not summaries and expected["relation"]["request"] is not None,
                "unexpected heap invocation",
            )
            sp = m.reg_read(x.UC_X86_REG_ESP)
            _require(sp == entry - 48, "nested heap frame differs")
            words = [
                int.from_bytes(m.mem_read(sp + 4 * i, 4), "little") for i in range(4)
            ]
            _require(
                words
                == [BASE + 0x389463, HEAP_HANDLE, 0, expected["relation"]["request"]],
                "nested heap handoff differs",
            )
            m.reg_write(x.UC_X86_REG_EAX, vector["pointer"] + int(negative))
            m.reg_write(x.UC_X86_REG_ECX, 0xA0000001)
            m.reg_write(x.UC_X86_REG_EDX, 0xB0000001)
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            m.reg_write(x.UC_X86_REG_ESP, sp + 16)
            summaries.append(
                dict(callee_entry_esp=sp, request=words[3], continuation=words[0])
            )
            resume_at = words[0]
            m.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "execution escaped joined allocation")
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, size, value, user):
        write = access == uc.UC_MEM_WRITE
        if write:
            _require(
                size == 4
                and (
                    entry - 48 <= address <= entry - 4
                    or DATA <= address <= DATA + 0x3FFC
                ),
                "unexpected joined write",
            )
        else:
            _require(
                size == 4
                and (
                    entry - 48 <= address <= entry + 4 or address in [IAT, HEAP_GLOBAL]
                ),
                "unexpected joined read",
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
    machine.emu_start(BASE + 0x8A920, RETURN, count=200)
    if resume_at is not None:
        machine.emu_start(resume_at, RETURN, count=200)
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == RETURN, "joined allocation did not return"
    )
    _require(
        len(summaries) == int(vector["count"] != 0), "joined heap call count differs"
    )
    actual = {name: machine.reg_read(reg) for name, reg in ids.items()}
    _require(
        actual == expected["registers"], "joined allocation register oracle differs"
    )
    _require(
        machine.reg_read(x.UC_X86_REG_EFLAGS) & expected["flag_mask"]
        == expected["flags"],
        "joined defined flags differ",
    )
    _require(
        bytes(machine.mem_read(DATA, 0x4000)) == expected["payload"],
        "joined metadata oracle differs",
    )
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == expected["stack"],
        "joined full stack differs",
    )
    _require(events == expected["events"], "joined ordered memory differs")
    _require(
        bytes(machine.mem_read(IAT & ~0xFFF, 0x1000)) == bytes(iat)
        and bytes(machine.mem_read(HEAP_GLOBAL & ~0xFFF, 0x1000))
        == bytes(global_bytes),
        "joined static globals changed",
    )
    return dict(
        vector=vector,
        visited=visited,
        summaries=summaries,
        registers=actual,
        events_sha256=_canonical_sha256(events),
    )


def _build_unsealed(executable, composition):
    from src.observatory import native_vector_allocation_composition as composed

    _validate_json_tree(composition, "composition")
    _require(
        _canonical_sha256(composition) == composed.SEALED_SHA256,
        "allocation composition differs",
    )
    data, image, digest = _load_executable(executable)
    _require(
        capstone.__version__ == "5.0.7"
        and digest == EXE_SHA256
        and image.image_base == BASE,
        "exact build differs",
    )
    codes, points = {}, {}
    for name, (start, end) in BODIES.items():
        offset = image.rva_to_file_offset(start)
        codes[name] = data[offset : offset + end - start]
        points[name] = [
            _point(r)
            for r in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
                codes[name], BASE + start
            )
        ]
    _require(sum(len(p) for p in points.values()) == 91, "joined body extent differs")
    observations = [_run_case(codes, points, v) for v in vectors()]
    caught = False
    try:
        _run_case(
            codes,
            points,
            dict(count=512, pointer=DATA + 0x100, alignment=0),
            negative=True,
        )
    except ConformanceError as exc:
        caught = "joined metadata oracle" in str(exc)
    _require(caught, "changed supplied raw pointer control accepted")
    visited = sorted({p for row in observations for p in row["visited"]})
    _require(len(visited) == 66, "joined success coverage differs")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=composition["build_identity"],
        source_composition_sha256=composed.SEALED_SHA256,
        bodies={
            name: dict(
                entry_rva=f"0x{start:08x}",
                exclusive_end_rva=f"0x{end:08x}",
                bytes=end - start,
                points=points[name],
                sha256=hashlib.sha256(codes[name]).hexdigest(),
            )
            for name, (start, end) in BODIES.items()
        },
        emulator=dict(
            name="Unicorn", version="2.1.4", architecture="x86", mode_bits=32
        ),
        decoder=dict(name="Capstone", version="5.0.7"),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=visited,
        summary=dict(
            cases=len(observations),
            executed_instruction_sites=66,
            heap_summaries=sum(len(r["summaries"]) for r in observations),
            zero_returns=16,
            imported_callee_instructions=0,
            negative_controls=1,
            accounting_promotions=0,
        ),
        heap_summary=dict(
            runtime_iat_target=IMPORT,
            return_value="Vector pointer inside supplied writable nonwrapping buffer",
            callee_entry_esp="outer entry minus forty-eight",
            cleanup_bytes=12,
            preserved="All memory and nonvolatile registers",
            ecx=0xA0000001,
            edx=0xB0000001,
            eflags=0x246,
        ),
        scope=dict(
            claim="One integrated exact execution joins vector allocation, outer retry and candidate heap wrapper through zero return or one supplied positive heap response",
            checks="Full ancestor stack, payload metadata, IAT and heap-global pages, all general registers, defined flags and ordered native accesses",
            not_claimed=[
                "Actual operating-system allocation",
                "Integrated retries, handler or error paths",
                "Arbitrary counts or pointer domains",
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


def validate_structure(evidence, composition):
    from src.observatory import native_vector_allocation_composition as composed

    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(composition, "composition")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(composition) == composed.SEALED_SHA256,
        "sealed joined replay differs",
    )
    _require(
        evidence["source_composition_sha256"] == composed.SEALED_SHA256
        and evidence["vectors"] == vectors(),
        "joined source differs",
    )
    _assert_publication_safe(evidence)
    return dict(
        status="structurally_verified",
        evidence_sha256=SEALED_SHA256,
        summary=evidence["summary"],
    )


def build_conformance(executable, composition):
    result = _build_unsealed(executable, composition)
    validate_structure(result, composition)
    return result


def validate_conformance(executable, evidence, composition):
    validate_structure(evidence, composition)
    _require(
        _canonical_bytes(build_conformance(executable, composition))
        == _canonical_bytes(evidence),
        "exact joined replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
