"""Exact resize owner replay; all three child effects remain explicit summaries."""

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

ANALYSIS_KIND = "pe_native_vector_resize_conformance"
SEALED_SHA256 = "462fdaa9796d1c68ca53de46b0db4c38553486616e0f8314a240ef0546c1e13b"
START, END, MASK = 0x2EB680, 0x2EB6E5, 0xFFFFFFFF
STACK, OBJECT, RETURN = 0x02000000, 0x03000000, 0x04000000
CALLEES = {
    BASE + 0x8A920: (1, 0x2EB695, 4),
    BASE + 0x36E580: (2, 0x2EB6A6, 0),
    BASE + 0x7800: (3, 0x2EB6C8, 0),
}


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    values = [(0, 0, 0, 0, 0), (0, 0, 0, 1, 0x6000000)]
    values += [
        (0x5000000, 0x5000000 + 8 * s, 0x5000000 + 8 * c, n, 0x6000000 + p)
        for s, c, n in (
            (0, 0, 1),
            (0, 4, 8),
            (1, 1, 2),
            (3, 4, 6),
            (511, 512, 768),
            (512, 512, 768),
        )
        for p in (0, 1, 31)
    ]
    values += [
        (b, (b + d) & MASK, (b + c) & MASK, n, p)
        for b in (0, 0x5000000, 0xFFFFFFF0)
        for d, c in (
            (1, 7),
            (7, 8),
            (0x7FFFFFFF, 0x80000000),
            (0x80000000, 0xFFFFFFFF),
            (0xFFFFFFF9, 0xFFFFFFFF),
        )
        for n, p in ((0, 0), (MASK, 0xFFFFFFF8))
    ]
    return [
        dict(
            begin=b,
            end=e,
            capacity=c,
            requested=n,
            new_pointer=p,
            alignment=a,
            object_offset=o,
        )
        for b, e, c, n, p in sorted(set(values))
        for a in range(16)
        for o in (0, 1)
    ]


def oracle(begin, end, capacity, requested, new_pointer):
    for v in (begin, end, capacity, requested, new_pointer):
        _require(type(v) is int and 0 <= v <= MASK, "invalid unsigned input")
    length = (end - begin) & MASK
    span = (capacity - begin) & MASK
    free_count = ((span if span < 2**31 else span - 2**32) // 8) & MASK
    return dict(
        copy_arguments=[new_pointer, begin, length],
        free_arguments=[begin, free_count, 8] if begin else None,
        new_capacity=(new_pointer + 8 * requested) & MASK,
        new_end=(new_pointer + (length & ~7)) & MASK,
        new_begin=new_pointer,
    )


def _expected(vector, initial, original_stack, original_object):
    b, e, c, n, p = [
        vector[k] for k in ("begin", "end", "capacity", "requested", "new_pointer")
    ]
    relation = oracle(b, e, c, n, p)
    s = initial["esp"]
    obj = initial["ecx"]
    stack, object_bytes = bytearray(original_stack), bytearray(original_object)
    events = []

    def event(kind, address, value):
        events.append(dict(kind=kind, address=address, width=4, value=value))
        if kind == "write":
            buffer, base = (
                (stack, STACK)
                if STACK <= address < STACK + len(stack)
                else (object_bytes, OBJECT)
            )
            buffer[address - base : address - base + 4] = value.to_bytes(4, "little")

    w = lambda a, v: event("write", a, v)
    r = lambda a, v: event("read", a, v)
    w(s - 4, initial["ebp"])
    w(s - 8, obj)
    r(s + 4, n)
    w(s - 12, initial["ebx"])
    w(s - 16, initial["esi"])
    w(s - 20, initial["edi"])
    w(s - 24, n)
    w(s - 8, n)
    w(s - 28, BASE + 0x2EB695)
    r(obj, b)
    r(obj + 4, e)
    w(s - 24, relation["copy_arguments"][2])
    w(s - 28, b)
    w(s - 32, p)
    w(s - 36, BASE + 0x2EB6A6)
    r(obj, b)
    r(obj + 4, e)
    if b:
        r(obj + 8, c)
        w(s - 24, 8)
        w(s - 28, relation["free_arguments"][1])
        w(s - 32, b)
        w(s - 36, BASE + 0x2EB6C8)
    r(s - 8, n)
    w(obj + 8, relation["new_capacity"])
    w(obj + 4, relation["new_end"])
    w(obj, p)
    r(s - 20, initial["edi"])
    r(s - 16, initial["esi"])
    r(s - 12, initial["ebx"])
    r(s - 4, initial["ebp"])
    r(s, RETURN)
    regs = dict(initial)
    regs.update(
        eax=relation["new_end"],
        ecx=0xA0000003 if b else 0,
        edx=0xB0000003 if b else 0xB0000002,
        esp=s + 8,
    )
    return dict(
        relation=relation,
        registers=regs,
        flags=_add_flags(s - 32, 12) if b else 0x44,
        flag_mask=0x8D5 if b else 0x8C5,
        events=events,
        stack=bytes(stack),
        object=bytes(object_bytes),
    )


def _run_case(code, points, vector, negative=False):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    machine.mem_map(BASE + (START & ~0xFFF), 0x1000)
    machine.mem_write(BASE + START, code)
    for target in CALLEES:
        machine.mem_map(target & ~0xFFF, 0x2000)
        machine.mem_write(target, b"\xcc")
    for page, length in ((STACK, 0x4000), (OBJECT, 0x1000), (RETURN, 0x1000)):
        machine.mem_map(page, length)
    s = STACK + 0x2000 + vector["alignment"]
    obj = OBJECT + 0x100 + vector["object_offset"]
    stack = bytearray(((i * 19) ^ (i >> 6) ^ 0xD3) & 255 for i in range(0x4000))
    stack[s - STACK : s - STACK + 4] = RETURN.to_bytes(4, "little")
    stack[s - STACK + 4 : s - STACK + 8] = vector["requested"].to_bytes(4, "little")
    object_bytes = bytearray(((i * 41) ^ (i >> 5) ^ 0x65) & 255 for i in range(0x1000))
    for i, key in enumerate(("begin", "end", "capacity")):
        object_bytes[obj - OBJECT + 4 * i : obj - OBJECT + 4 * i + 4] = vector[
            key
        ].to_bytes(4, "little")
    machine.mem_write(STACK, bytes(stack))
    machine.mem_write(OBJECT, bytes(object_bytes))
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
    initial = {r: 0x16273849 + i * 0x1010101 for i, r in enumerate(ids)}
    initial.update(esp=s, ecx=obj)
    expected = _expected(vector, initial, stack, object_bytes)
    for r, v in initial.items():
        machine.reg_write(ids[r], v)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    visited, events, summaries = [], [], []
    resume = None
    allowed = {int(p["rva"], 16) for p in points}

    def on_code(m, address, size, user):
        nonlocal resume
        if address in CALLEES:
            ordinal, continuation, cleanup = CALLEES[address]
            _require(ordinal == len(summaries) + 1, "child order differs")
            sp = m.reg_read(x.UC_X86_REG_ESP)
            args = (
                [vector["requested"]]
                if ordinal == 1
                else (
                    expected["relation"]["copy_arguments"]
                    if ordinal == 2
                    else expected["relation"]["free_arguments"]
                )
            )
            _require(
                args is not None and sp == s - (28 if ordinal == 1 else 36),
                "child frame differs",
            )
            words = [
                int.from_bytes(m.mem_read(sp + 4 * i, 4), "little")
                for i in range(len(args) + 1)
            ]
            _require(
                words == [BASE + continuation, *args],
                "child arguments or continuation differ",
            )
            m.reg_write(
                x.UC_X86_REG_EAX,
                (
                    vector["new_pointer"] + (int(negative) if ordinal == 1 else 0)
                    if ordinal == 1
                    else 0xC0000000 + ordinal
                ),
            )
            m.reg_write(x.UC_X86_REG_ECX, 0xA0000000 + ordinal)
            m.reg_write(x.UC_X86_REG_EDX, 0xB0000000 + ordinal)
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            m.reg_write(x.UC_X86_REG_ESP, sp + 4 + cleanup)
            summaries.append(
                dict(
                    ordinal=ordinal,
                    entry_esp=sp,
                    arguments=args,
                    continuation=BASE + continuation,
                )
            )
            resume = BASE + continuation
            m.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "execution escaped resize owner")
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, size, value, user):
        write = access == uc.UC_MEM_WRITE
        _require(
            size == 4 and (s - 36 <= address <= s + 4 or obj <= address <= obj + 8),
            "unexpected native access",
        )
        events.append(
            dict(
                kind="write" if write else "read",
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
    start = BASE + START
    for _ in range(4):
        resume = None
        machine.emu_start(start, RETURN, count=100)
        if resume is None:
            break
        start = resume
    _require(machine.reg_read(x.UC_X86_REG_EIP) == RETURN, "owner did not return")
    _require(len(summaries) == 2 + int(vector["begin"] != 0), "child count differs")
    actual = {r: machine.reg_read(i) for r, i in ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS) & expected["flag_mask"]
    _require(
        actual == expected["registers"]
        and flags == expected["flags"] & expected["flag_mask"],
        "resize register or flag oracle differs",
    )
    _require(
        events == expected["events"]
        and bytes(machine.mem_read(STACK, 0x4000)) == expected["stack"]
        and bytes(machine.mem_read(OBJECT, 0x1000)) == expected["object"],
        "resize ordered memory oracle differs",
    )
    return dict(
        inputs=vector,
        registers=actual,
        flags=flags,
        flag_mask=expected["flag_mask"],
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        stack_sha256=hashlib.sha256(expected["stack"]).hexdigest(),
        object_sha256=hashlib.sha256(expected["object"]).hexdigest(),
        summaries=summaries,
    )


def _build_unsealed(executable, semantics):
    from src.observatory import native_vector_resize_semantics as sem

    _validate_json_tree(semantics, "semantics")
    _require(_canonical_sha256(semantics) == sem.SEALED_SHA256, "source seal differs")
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256, "executable differs")
    offset = image.rva_to_file_offset(START)
    code = data[offset : offset + END - START]
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    points = [_point(r) for r in decoder.disasm(code, BASE + START)]
    _require(
        points == semantics["body"]["points"]
        and hashlib.sha256(code).hexdigest() == semantics["body"]["sha256"],
        "owner witness differs",
    )
    cases = [_run_case(code, points, v) for v in vectors()]
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(union == [p["rva"] for p in points], "native coverage differs")
    v = dict(
        begin=0x5000000,
        end=0x5000008,
        capacity=0x5000008,
        requested=2,
        new_pointer=0x6000000,
        alignment=0,
        object_offset=0,
    )
    try:
        _run_case(code, points, v, negative=True)
    except ConformanceError:
        pass
    else:
        raise ConformanceError("wrong allocation response survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_semantics_sha256=sem.SEALED_SHA256,
        build_identity=semantics["build_identity"],
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(cases),
        instruction_union_rvas=union,
        summary=dict(
            cases=len(cases),
            executed_instruction_sites=len(union),
            opaque_call_summaries=sum(len(c["summaries"]) for c in cases),
            callee_instructions=0,
            negative_controls=1,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact resize owner instructions match independent frame, pointer arithmetic and ordered memory equations",
            premises=[
                "Every child returns normally and preserves modeled stack and object bytes plus nonvolatile registers",
                "Allocation returns the supplied pointer with four argument bytes consumed; copy and deallocation consume none",
                "Volatile child outputs use explicit fixed samples; payload memory is not mapped or accessed",
            ],
            stop_policy="Actual CALLs enter excluded synthetic stop bytes; hooks stop before these execute and supply declared returns",
            not_claimed=[
                "Actual allocation, byte copy or free effects and validity of synthetic payload addresses",
                "Failure paths, object mutation across calls, arbitrary volatile responses or complete resize equivalence",
                "Game execution or accounting promotion",
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
    from src.observatory import native_vector_resize_semantics as sem

    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "sealed resize replay differs",
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
