"""Exact candidate-to-HeapAlloc handoff, stopping before import dereference."""

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

ANALYSIS_KIND = "pe_native_heap_allocation_handoff_conformance"
SEALED_SHA256 = "51ba7067f55e15a5870b6973f85a94967b2c0586cc5bba91963c155fb7f82958"
BODIES = {"thunk": (0x379F52, 0x379F5D), "heap_wrapper": (0x38942B, 0x389479)}
HEAP_CALL, ERROR = 0x38945D, 0x389469
HEAP_GLOBAL = BASE + 0x4B7634
STACK = 0x2000000
MASK = 0xFFFFFFFF


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    sizes = [0, 1, 8, 4131, 0xFFFFFFDB, 0xFFFFFFE0, *range(0xFFFFFFE1, 0x100000000)]
    return [
        dict(size=n, heap=h, alignment=a)
        for n in sizes
        for h in [0, 0x12345678, MASK]
        for a in range(16)
    ]


def oracle(size, heap):
    _require(
        all(type(v) is int and 0 <= v <= MASK for v in [size, heap]),
        "invalid u32 input",
    )
    if size > 0xFFFFFFE0:
        return dict(
            outcome="error_frontier",
            stop=ERROR,
            effective=size,
            arguments=[],
            stack_delta=-8,
            flags=_cmp_flags(size, 0xFFFFFFE0),
            flag_mask=0x8D5,
        )
    effective = max(size, 1)
    flags = (
        0
        if size == 0
        else (int((size & 255).bit_count() % 2 == 0) << 2) | (size >> 31) << 7
    )
    return dict(
        outcome="heap_call",
        stop=HEAP_CALL,
        effective=effective,
        arguments=[heap, 0, effective],
        stack_delta=-20,
        flags=flags,
        flag_mask=0x8D5 if size == 0 else 0x8C5,
    )


def _run_case(codes, points, vector, *, negative=False):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    expected = oracle(vector["size"], vector["heap"])
    entry = STACK + 0x2000 + vector["alignment"]
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for name, (start, end) in BODIES.items():
        machine.mem_map(BASE + (start & ~0xFFF), 0x1000)
        machine.mem_write(BASE + start, codes[name])
    machine.mem_map(STACK, 0x4000)
    heap_page = HEAP_GLOBAL & ~0xFFF
    machine.mem_map(heap_page, 0x1000)
    stack = bytearray(((i * 37) ^ (i >> 4) ^ 0xE9) & 255 for i in range(0x4000))
    stack[entry - STACK + 4 : entry - STACK + 8] = vector["size"].to_bytes(4, "little")
    machine.mem_write(STACK, bytes(stack))
    global_bytes = bytearray(((i * 13) ^ (i >> 3) ^ 0x49) & 255 for i in range(0x1000))
    global_bytes[HEAP_GLOBAL - heap_page : HEAP_GLOBAL - heap_page + 4] = vector[
        "heap"
    ].to_bytes(4, "little")
    machine.mem_write(heap_page, bytes(global_bytes))
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
    initial = {name: 0x16453278 + i * 0x1010101 for i, name in enumerate(ids)}
    initial["esp"] = entry
    for name, value in initial.items():
        machine.reg_write(ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 2)
    if negative:
        machine.mem_write(HEAP_GLOBAL, (vector["heap"] ^ 1).to_bytes(4, "little"))
    allowed = {int(p["rva"], 16) for rows in points.values() for p in rows}
    visited, events, stops = [], [], []

    def on_code(m, address, size, user):
        pc = address - BASE
        _require(pc in allowed, "execution escaped handoff bodies")
        if pc in [HEAP_CALL, ERROR]:
            stops.append(pc)
            m.emu_stop()
            return
        _require(
            pc < 0x389440 or 0x389454 <= pc < HEAP_CALL,
            "unexpected retry or return path",
        )
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, size, value, user):
        write = access == uc.UC_MEM_WRITE
        if write:
            _require(
                entry - 20 <= address and address + size <= entry and size == 4,
                "unexpected handoff write",
            )
        else:
            _require(
                address in [entry - 4, entry + 4, HEAP_GLOBAL] and size == 4,
                "unexpected handoff read or IAT dereference",
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
    machine.emu_start(BASE + BODIES["thunk"][0], BASE + 0x389479, count=60)
    _require(stops == [expected["stop"]], "handoff oracle stop differs")
    wanted = dict(
        initial,
        ebp=entry - 4,
        esi=expected["effective"],
        esp=entry + expected["stack_delta"],
    )
    actual = {name: machine.reg_read(reg) for name, reg in ids.items()}
    _require(actual == wanted, "handoff oracle registers differ")
    _require(
        machine.reg_read(x.UC_X86_REG_EFLAGS) & expected["flag_mask"]
        == expected["flags"],
        "handoff defined flags differ",
    )
    wanted_events = []
    wanted_stack = bytearray(stack)

    def write(address, value):
        wanted_stack[address - STACK : address - STACK + 4] = value.to_bytes(
            4, "little"
        )
        wanted_events.append(
            dict(access="write", address=address, width=4, value=value)
        )

    def read(address, value):
        wanted_events.append(dict(access="read", address=address, width=4, value=value))

    write(entry - 4, initial["ebp"])
    read(entry - 4, initial["ebp"])
    write(entry - 4, initial["ebp"])
    write(entry - 8, initial["esi"])
    read(entry + 4, vector["size"])
    if expected["outcome"] == "heap_call":
        write(entry - 12, expected["effective"])
        write(entry - 16, 0)
        read(HEAP_GLOBAL, vector["heap"])
        write(entry - 20, vector["heap"])
    _require(events == wanted_events, "handoff ordered argument oracle differs")
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == bytes(wanted_stack),
        "handoff full stack differs",
    )
    _require(
        bytes(machine.mem_read(heap_page, 0x1000)) == bytes(global_bytes),
        "heap global page changed",
    )
    return dict(
        vector=vector,
        visited=visited,
        stop_rva=f"0x{stops[0]:08x}",
        outcome=expected["outcome"],
        registers=actual,
        events_sha256=_canonical_sha256(events),
    )


def _build_unsealed(executable, semantics):
    from src.observatory import native_heap_allocation_handoff as sem

    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(semantics) == sem.SEALED_SHA256, "handoff semantics differs"
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
    _require(
        sum(len(rows) for rows in points.values()) == 37, "handoff body extent differs"
    )
    observations = [_run_case(codes, points, v) for v in vectors()]
    caught = False
    try:
        _run_case(
            codes, points, dict(size=8, heap=0x12345678, alignment=0), negative=True
        )
    except ConformanceError as exc:
        caught = "ordered argument oracle" in str(exc)
    _require(caught, "changed heap handle control accepted")
    visited = sorted({p for row in observations for p in row["visited"]})
    _require(len(visited) == 19, "handoff coverage differs")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=semantics["build_identity"],
        source_semantics_sha256=sem.SEALED_SHA256,
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
            executed_instruction_sites=19,
            heap_frontiers=sum(r["outcome"] == "heap_call" for r in observations),
            error_frontiers=sum(r["outcome"] == "error_frontier" for r in observations),
            executed_calls=0,
            iat_dereferences=0,
            negative_controls=1,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact transparent thunk and initial heap handoff match an independent size and argument oracle",
            premises=[
                "Mapped stable request, caller frame and heap-handle global",
                "Global storage disjoint from stack",
            ],
            import_boundary="IAT page is deliberately unmapped; replay stops before either import or error CALL",
            flags="Nonzero TEST omits undefined AF; zero INC and oversize CMP compare six arithmetic flags",
            not_claimed=[
                "HeapAlloc execution, success or heap-handle validity",
                "Error callee, retry loop or return effects",
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
    from src.observatory import native_heap_allocation_handoff as sem

    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "sealed handoff replay differs",
    )
    _require(
        evidence["source_semantics_sha256"] == sem.SEALED_SHA256
        and evidence["vectors"] == vectors(),
        "source relation differs",
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
        "exact handoff replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
