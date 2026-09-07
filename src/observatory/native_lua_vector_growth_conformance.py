"""Bounded exact x86 growth-decision replay with an independent arithmetic oracle."""

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

ANALYSIS_KIND = "pe_native_lua_vector_growth_conformance"
SEALED_SHA256 = "e183ac0be6298ac190f4b4d83e0201366be59156e4f40ec04c7dd3f738105740"
START, END = 0x2EB620, 0x2EB67E
RESIZE, CLEANUP, FAILURE = 0x2EB669, 0x2EB66F, 0x2EB674
STACK, OBJECT = 0x2000000, 0x3000000
MASK = 0xFFFFFFFF
MAXIMUM = 0x1FFFFFFF


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    displacements = [
        0,
        1,
        7,
        8,
        16,
        0x7FFFFFF8,
        0x7FFFFFFF,
        0x80000000,
        0x80000007,
        0xFFFFFFF8,
        0xFFFFFFFF,
    ]
    return [
        dict(begin=b, end=(b + d) & MASK, capacity=(b + d + f) & MASK, alignment=a)
        for b in [0, 0x1000, 0xFFFFFFF0]
        for d in displacements
        for f in [0, 1, 7, 8, 0x80000000, MASK]
        for a in range(16)
    ]


def _signed(value):
    return value if value < 0x80000000 else value - 0x100000000


def _cmp_flags(left, right):
    result = (left - right) & MASK
    return (
        int(left < right)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | ((left ^ right ^ result) & 16)
        | (int(result == 0) << 6)
        | (result & 0x80000000) >> 24
        | (((left ^ right) & (left ^ result) & 0x80000000) >> 20)
    )


def oracle(vector):
    """Mathematical partition independent of the instruction-model producer."""
    _require(
        set(vector) == {"begin", "end", "capacity", "alignment"}, "vector keys differ"
    )
    _require(
        all(
            type(vector[k]) is int and 0 <= vector[k] <= MASK
            for k in ["begin", "end", "capacity"]
        ),
        "invalid u32 vector",
    )
    _require(
        type(vector["alignment"]) is int and 0 <= vector["alignment"] < 16,
        "invalid alignment",
    )
    b, e, c = (vector[k] for k in ["begin", "end", "capacity"])
    free = (c - e) & MASK
    if free >= 8:
        q = (_signed(free) // 8) & MASK
        return dict(
            path="no_growth",
            stop=CLEANUP,
            eax=q,
            edx=e,
            edi=c,
            ebx=0x12345678,
            flags=_cmp_flags(q, 1),
            stack_delta=-8,
            requested=None,
        )
    size = (_signed((e - b) & MASK) // 8) & MASK
    count = (_signed((c - b) & MASK) // 8) & MASK
    # SAR3 cannot produce MAXIMUM, so the size-limit failure test cannot fire.
    _require(size != MAXIMUM, "impossible signed quotient")
    geometric = count + count // 2 if count <= 0x0FFFFFFF else 0
    desired = (size + 1) & MASK
    return dict(
        path="resize_frontier",
        stop=RESIZE,
        eax=(count + count // 2) & MASK,
        edi=count,
        ebx=(MAXIMUM - count // 2) & MASK,
        edx=max(desired, geometric),
        flags=_cmp_flags(geometric, desired),
        stack_delta=-16,
        requested=max(desired, geometric),
    )


def _run_case(code, points, vector, *, negative=False):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn 2.1.4 required")
    expected = oracle(vector)
    entry = STACK + 0x2000 + vector["alignment"]
    obj = OBJECT + 0x100
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    machine.mem_map(BASE + 0x2EB000, 0x1000)
    machine.mem_write(BASE + START, code)
    machine.mem_map(STACK, 0x4000)
    machine.mem_map(OBJECT, 0x1000)
    stack = bytes(((i * 41) ^ (i >> 5) ^ 0xB3) & 255 for i in range(0x4000))
    metadata = bytearray(((i * 23) ^ (i >> 3) ^ 0x69) & 255 for i in range(0x1000))
    for offset, key in [(0, "begin"), (4, "end"), (8, "capacity")]:
        metadata[0x100 + offset : 0x104 + offset] = vector[key].to_bytes(4, "little")
    machine.mem_write(STACK, stack)
    machine.mem_write(OBJECT, bytes(metadata))
    register_ids = {
        "eax": x.UC_X86_REG_EAX,
        "ebx": x.UC_X86_REG_EBX,
        "ecx": x.UC_X86_REG_ECX,
        "edx": x.UC_X86_REG_EDX,
        "esi": x.UC_X86_REG_ESI,
        "edi": x.UC_X86_REG_EDI,
        "ebp": x.UC_X86_REG_EBP,
        "esp": x.UC_X86_REG_ESP,
    }
    initial = dict(
        eax=0x3456789A,
        ebx=0x12345678,
        ecx=obj,
        edx=0x56789ABC,
        esi=0x23456789,
        edi=0x6789ABCD,
        ebp=0x456789AB,
        esp=entry,
    )
    for key, value in initial.items():
        machine.reg_write(register_ids[key], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 2)
    if negative:
        # Keep the oracle input fixed while changing one machine field.
        machine.mem_write(obj + 8, ((vector["end"] + 8) & MASK).to_bytes(4, "little"))
    allowed = {int(p["rva"], 16) for p in points}
    visited, events = [], []
    stopped = []

    def on_code(m, address, size, user):
        pc = address - BASE
        _require(pc in allowed, "execution escaped reviewed body")
        if pc in [RESIZE, CLEANUP, FAILURE]:
            stopped.append(pc)
            m.emu_stop()
            return
        _require(pc < RESIZE, "unexpected child or epilogue execution")
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, size, value, user):
        write = access == uc.UC_MEM_WRITE
        if write:
            _require(
                entry - 16 <= address and address + size <= entry,
                "write escaped save/argument words",
            )
        else:
            _require(
                obj <= address and address + size <= obj + 12,
                "read escaped vector metadata",
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
    machine.emu_start(BASE + START, BASE + END, count=100)
    _require(stopped == [expected["stop"]], "arithmetic oracle stop differs")
    output = dict(initial)
    output.update({key: expected[key] for key in ["eax", "ebx", "edx", "edi"]})
    output.update(ecx=obj, esi=obj, esp=entry + expected["stack_delta"])
    actual = {key: machine.reg_read(reg) for key, reg in register_ids.items()}
    _require(actual == output, "arithmetic oracle registers differ")
    _require(
        machine.reg_read(x.UC_X86_REG_EFLAGS) & 0x8D5 == expected["flags"],
        "arithmetic oracle flags differ",
    )
    wanted_stack = bytearray(stack)
    writes = [(entry - 4, initial["esi"]), (entry - 8, initial["edi"])]
    if expected["requested"] is not None:
        writes += [(entry - 12, initial["ebx"]), (entry - 16, expected["requested"])]
    for address, value in writes:
        wanted_stack[address - STACK : address - STACK + 4] = value.to_bytes(
            4, "little"
        )
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == bytes(wanted_stack),
        "stack oracle differs",
    )
    _require(
        bytes(machine.mem_read(OBJECT, 0x1000)) == bytes(metadata), "metadata changed"
    )
    expected_events = [
        dict(access="write", address=entry - 4, width=4, value=initial["esi"]),
        dict(access="write", address=entry - 8, width=4, value=initial["edi"]),
        dict(access="read", address=obj + 8, width=4, value=vector["capacity"]),
        dict(access="read", address=obj + 4, width=4, value=vector["end"]),
    ]
    if expected["requested"] is not None:
        expected_events += [
            dict(access="read", address=obj, width=4, value=vector["begin"]),
            dict(access="write", address=entry - 12, width=4, value=initial["ebx"]),
            dict(
                access="write", address=entry - 16, width=4, value=expected["requested"]
            ),
        ]
    _require(events == expected_events, "ordered operand events differ")
    return dict(
        vector=vector,
        path=expected["path"],
        stop_rva=f"0x{stopped[0]:08x}",
        visited=visited,
        registers=actual,
        flags=expected["flags"],
        events_sha256=_canonical_sha256(events),
    )


def _build_unsealed(executable, semantics):
    from src.observatory import native_lua_vector_growth_semantics as sem

    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(semantics) == sem.SEALED_SHA256, "growth semantics differs"
    )
    data, image, digest = _load_executable(executable)
    _require(capstone.__version__ == "5.0.7", "reviewed Capstone required")
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    offset = image.rva_to_file_offset(START)
    code = data[offset : offset + END - START]
    rows = list(
        capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
            code, BASE + START
        )
    )
    points = [_point(r) for r in rows]
    _require(len(rows) == 40 and sum(r.size for r in rows) == 94, "body extent differs")
    _require(points == semantics["body"]["points"], "source body points differ")
    observations = [_run_case(code, points, v) for v in vectors()]
    caught = False
    try:
        _run_case(code, points, vectors()[0], negative=True)
    except ConformanceError as exc:
        caught = "arithmetic oracle stop" in str(exc)
    _require(caught, "changed field control was not rejected")
    visited = sorted({pc for row in observations for pc in row["visited"]})
    _require(len(visited) == 33, "decision coverage differs")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=semantics["build_identity"],
        source_semantics_sha256=sem.SEALED_SHA256,
        body=dict(
            entry_rva=f"0x{START:08x}",
            exclusive_end_rva=f"0x{END:08x}",
            bytes=94,
            nodes=40,
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
            no_growth=sum(r["path"] == "no_growth" for r in observations),
            resize_frontier=sum(r["path"] == "resize_frontier" for r in observations),
            failure_frontier=0,
            executed_calls=0,
            negative_controls=1,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact x86 capacity decision agrees with independent arithmetic and ordered-memory oracle on finite vectors",
            stops=[f"0x{p:08x}" for p in [RESIZE, CLEANUP, FAILURE]],
            stop_instructions_executed=False,
            flags="CF PF AF ZF SF OF from final CMP are compared; other EFLAGS not claimed",
            memory="Full mapped stack and metadata checked; payload pointers are integer words and never dereferenced",
            not_claimed=[
                "Allocation, copying, freeing, failure helper or epilogue execution",
                "Validity of arbitrary u32 fields as C++ objects",
                "Whole-owner or whole-game completion",
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
    from src.observatory import native_lua_vector_growth_semantics as sem

    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "sealed growth conformance differs",
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
