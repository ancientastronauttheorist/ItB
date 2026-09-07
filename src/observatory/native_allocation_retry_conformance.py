"""Exact retry wrapper replay with explicit host-supplied callee responses."""

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

ANALYSIS_KIND = "pe_native_allocation_retry_conformance"
SEALED_SHA256 = "92c7ffc148c0a8898c5cc6cb3654282fc94ffe97ed052bbb7d453db8058d44dd"
START, END = 0x3574DB, 0x35750E
STACK, RETURN = 0x2000000, 0x4000000
CALLS = {
    "candidate": (0x357502, 0x379F52),
    "handler": (0x3574E3, 0x38BBC4),
    "failure": (0x3574FA, 0x3435BC),
    "minus_one_failure": (0x3574F3, 0x35848F),
}
MASK = 0xFFFFFFFF


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def protocol_oracle(requested, responses):
    _require(type(requested) is int and 0 <= requested <= MASK, "invalid request")
    _require(type(responses) is list and len(responses) <= 64, "invalid response list")
    expected = "candidate"
    result = None
    for row in responses:
        _require(result is None, "response after successful return")
        _require(
            type(row) is dict
            and set(row) == {"kind", "eax"}
            and row["kind"] == expected
            and type(row["eax"]) is int
            and 0 <= row["eax"] <= MASK,
            "response protocol differs",
        )
        if expected == "candidate":
            if row["eax"]:
                result = row["eax"]
            else:
                expected = "handler"
        elif expected == "handler":
            expected = (
                "candidate"
                if row["eax"]
                else ("minus_one_failure" if requested == MASK else "failure")
            )
        else:
            expected = "candidate"
    return dict(
        returned=result is not None,
        result=result,
        next_kind=None if result is not None else expected,
    )


def vectors():
    result = []
    for requested in [0, 8, 4131, 0xFFFFFFFB, MASK]:
        failure = "minus_one_failure" if requested == MASK else "failure"
        patterns = [
            [],
            [("candidate", 0)],
            [("candidate", 0), ("handler", 0)],
            [("candidate", 1)],
            [("candidate", 0), ("handler", 1), ("candidate", 0x80000000)],
            [("candidate", 0), ("handler", 0), (failure, 0), ("candidate", MASK)],
            [("candidate", 0), ("handler", 0), (failure, 0xABCD)],
            [
                ("candidate", 0),
                ("handler", 1),
                ("candidate", 0),
                ("handler", 0),
                (failure, 123),
                ("candidate", 7),
            ],
        ]
        for pattern in patterns:
            for alignment in range(16):
                result.append(
                    dict(
                        request=requested,
                        responses=[dict(kind=k, eax=v) for k, v in pattern],
                        alignment=alignment,
                    )
                )
    return result


def _test_flags(value):
    return (
        (int(value == 0) << 6)
        | (value >> 31) << 7
        | (int((value & 255).bit_count() % 2 == 0) << 2)
    )


def _expected(vector, initial, stack):
    requested, rows = vector["request"], vector["responses"]
    protocol = protocol_oracle(requested, rows)
    entry = initial["esp"]
    memory = bytearray(stack)
    events = []

    def write(address, value):
        memory[address - STACK : address - STACK + 4] = value.to_bytes(4, "little")
        events.append(dict(access="write", address=address, width=4, value=value))

    def read(address, value):
        events.append(dict(access="read", address=address, width=4, value=value))

    write(entry - 4, initial["ebp"])
    kind = "candidate"
    index = 0
    while True:
        has_argument = kind in ["candidate", "handler"]
        read(entry + 4, requested)
        if has_argument:
            write(entry - 8, requested)
        if index == len(rows):
            break
        callsite, _ = CALLS[kind]
        write(entry - 12 if has_argument else entry - 8, BASE + callsite + 5)
        row = rows[index]
        index += 1
        if has_argument:
            read(entry - 8, requested)
        if kind == "candidate" and row["eax"]:
            read(entry - 4, initial["ebp"])
            read(entry, RETURN)
            break
        if kind == "candidate":
            kind = "handler"
        elif kind == "handler":
            kind = (
                "candidate"
                if row["eax"]
                else ("minus_one_failure" if requested == MASK else "failure")
            )
        else:
            kind = "candidate"
    regs = dict(initial, ebp=entry - 4)
    if rows:
        regs.update(
            eax=rows[-1]["eax"],
            ecx=(
                requested
                if rows[-1]["kind"] in ["candidate", "handler"]
                else 0xA0000000 + len(rows)
            ),
            edx=0xB0000000 + len(rows),
        )
    if protocol["returned"]:
        regs.update(ebp=initial["ebp"], esp=entry + 4)
        flags, mask = _test_flags(protocol["result"]), 0x8C5
    else:
        regs["esp"] = (
            entry - 8
            if protocol["next_kind"] in ["candidate", "handler"]
            else entry - 4
        )
        if not rows:
            flags, mask = 0, 0x8D5
        elif rows[-1]["kind"] in ["failure", "minus_one_failure"]:
            flags, mask = 0x44, 0x8D5
        elif protocol["next_kind"] in ["failure", "minus_one_failure"]:
            flags, mask = _cmp_flags(requested, MASK), 0x8D5
        else:
            flags, mask = _test_flags(rows[-1]["eax"]), 0x8C5
    return dict(
        protocol=protocol,
        registers=regs,
        flags=flags,
        flag_mask=mask,
        memory=bytes(memory),
        events=events,
    )


def _run_case(code, points, vector, *, negative=False):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    machine.mem_map(BASE + (START & ~0xFFF), 0x1000)
    machine.mem_write(BASE + START, code)
    for target in sorted({(BASE + t) & ~0xFFF for _, t in CALLS.values()}):
        # A second mapped page accommodates Unicorn translation lookahead;
        # the target hook stops before any callee instruction executes.
        machine.mem_map(target, 0x2000)
    machine.mem_map(STACK, 0x4000)
    machine.mem_map(RETURN, 0x1000)
    entry = STACK + 0x2000 + vector["alignment"]
    stack = bytearray(((i * 47) ^ (i >> 4) ^ 0xC9) & 255 for i in range(0x4000))
    stack[entry - STACK : entry - STACK + 4] = RETURN.to_bytes(4, "little")
    stack[entry - STACK + 4 : entry - STACK + 8] = vector["request"].to_bytes(
        4, "little"
    )
    machine.mem_write(STACK, bytes(stack))
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
    initial = {name: 0x10203040 + i * 0x1010101 for i, name in enumerate(ids)}
    initial["esp"] = entry
    expected = _expected(vector, initial, stack)
    for name, value in initial.items():
        machine.reg_write(ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 2)
    allowed = {int(p["rva"], 16) for p in points}
    call_by_pc = {pc: kind for kind, (pc, _) in CALLS.items()}
    target_kind = {BASE + target: kind for kind, (_, target) in CALLS.items()}
    visited, events, summaries = [], [], []
    index = 0
    pending = None
    resume_at = None
    frontier = []

    def on_code(m, address, size, user):
        nonlocal index, pending, resume_at
        if address in target_kind:
            kind = target_kind[address]
            _require(pending == kind, "unexpected callee target")
            row = vector["responses"][index]
            slot = m.reg_read(x.UC_X86_REG_ESP)
            has_argument = kind in ["candidate", "handler"]
            _require(
                slot == entry - (12 if has_argument else 8),
                "callee stack pointer differs",
            )
            continuation = int.from_bytes(m.mem_read(slot, 4), "little")
            _require(
                continuation == BASE + CALLS[kind][0] + 5, "callee continuation differs"
            )
            if has_argument:
                _require(
                    int.from_bytes(m.mem_read(slot + 4, 4), "little")
                    == vector["request"],
                    "callee request differs",
                )
            index += 1
            m.reg_write(
                x.UC_X86_REG_EAX, row["eax"] if not negative else (row["eax"] ^ 1)
            )
            m.reg_write(x.UC_X86_REG_ECX, 0xA0000000 + index)
            m.reg_write(x.UC_X86_REG_EDX, 0xB0000000 + index)
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            m.reg_write(x.UC_X86_REG_ESP, slot + 4)
            resume_at = continuation
            summaries.append(
                dict(
                    kind=kind,
                    return_word=continuation,
                    callee_entry_esp=slot,
                    has_request_argument=has_argument,
                )
            )
            pending = None
            m.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "execution escaped wrapper")
        if pc in call_by_pc:
            kind = call_by_pc[pc]
            if index == len(vector["responses"]):
                frontier.append(kind)
                m.emu_stop()
                return
            _require(
                vector["responses"][index]["kind"] == kind,
                "native response protocol differs",
            )
            pending = kind
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, size, value, user):
        write = access == uc.UC_MEM_WRITE
        _require(
            entry - 12 <= address and address + size <= entry + 8 and size == 4,
            "stack access escaped protected words",
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
    next_pc = BASE + START
    for _ in range(66):
        resume_at = None
        try:
            machine.emu_start(next_pc, RETURN, count=500)
        except uc.UcError as exc:
            raise ConformanceError(
                f"bounded emulator failed at {machine.reg_read(x.UC_X86_REG_EIP):08x}, "
                f"after {len(visited)} wrapper sites and {len(summaries)} summaries: {exc}"
            ) from exc
        if resume_at is None:
            break
        next_pc = resume_at
    else:
        raise ConformanceError("retry replay exceeded finite response bound")
    protocol = expected["protocol"]
    _require(
        index == len(vector["responses"])
        and frontier == ([] if protocol["returned"] else [protocol["next_kind"]]),
        "retry oracle outcome differs",
    )
    wanted_ip = (
        RETURN if protocol["returned"] else BASE + CALLS[protocol["next_kind"]][0]
    )
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == wanted_ip,
        "retry oracle instruction pointer differs",
    )
    actual = {name: machine.reg_read(reg) for name, reg in ids.items()}
    _require(actual == expected["registers"], "retry oracle registers differ")
    _require(
        machine.reg_read(x.UC_X86_REG_EFLAGS) & expected["flag_mask"]
        == expected["flags"],
        "retry oracle defined flags differ",
    )
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == expected["memory"],
        "retry full stack differs",
    )
    _require(events == expected["events"], "retry ordered accesses differ")
    return dict(
        vector=vector,
        visited=visited,
        summaries=summaries,
        returned=protocol["returned"],
        frontier=frontier,
        registers=actual,
        events_sha256=_canonical_sha256(events),
    )


def _build_unsealed(executable, semantics):
    from src.observatory import native_allocation_retry_semantics as sem

    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(semantics) == sem.SEALED_SHA256, "retry semantics differs"
    )
    data, image, digest = _load_executable(executable)
    _require(
        capstone.__version__ == "5.0.7"
        and digest == EXE_SHA256
        and image.image_base == BASE,
        "exact build differs",
    )
    offset = image.rva_to_file_offset(START)
    code = data[offset : offset + END - START]
    points = [
        _point(r)
        for r in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
            code, BASE + START
        )
    ]
    _require(
        len(points) == 20 and points == semantics["body"]["points"],
        "wrapper body differs",
    )
    observations = [_run_case(code, points, v) for v in vectors()]
    caught = False
    try:
        _run_case(
            code,
            points,
            dict(request=8, responses=[dict(kind="candidate", eax=1)], alignment=0),
            negative=True,
        )
    except ConformanceError as exc:
        caught = "retry oracle outcome" in str(exc)
    _require(caught, "changed response control accepted")
    visited = sorted({p for row in observations for p in row["visited"]})
    _require(len(visited) == 20, "wrapper coverage differs")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=semantics["build_identity"],
        source_semantics_sha256=sem.SEALED_SHA256,
        body=dict(
            entry_rva=f"0x{START:08x}",
            exclusive_end_rva=f"0x{END:08x}",
            bytes=51,
            nodes=20,
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
            executed_instruction_sites=20,
            returned=sum(r["returned"] for r in observations),
            frontier_stops=sum(not r["returned"] for r in observations),
            native_call_instructions=sum(len(r["summaries"]) for r in observations),
            callee_instruction_executions=0,
            negative_controls=1,
            accounting_promotions=0,
        ),
        callee_summary=dict(
            call_instruction_executed=True,
            callee_instructions_executed=False,
            return_relation="Host reads actual CALL return word, sets ESP to callee-entry plus four and resumes continuation",
            eax="Supplied finite response",
            ecx="0xa0000000 plus one-based response index",
            edx="0xb0000000 plus one-based response index",
            eflags=0x246,
            preserved="EBX ESI EDI EBP and all memory, including stable caller request and frame",
        ),
        scope=dict(
            claim="Exact retry wrapper with explicitly supplied normally returning callees agrees with finite protocol and ordered stack oracle",
            flags="Final TEST paths omit undefined AF; CMP and sampled opaque flags compare six arithmetic flags",
            not_claimed=[
                "Callee allocation, handler or failure semantics",
                "Actual heap operations or failure throwing",
                "Termination beyond supplied transcript",
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
    from src.observatory import native_allocation_retry_semantics as sem

    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "sealed retry replay differs",
    )
    _require(
        evidence["source_semantics_sha256"] == sem.SEALED_SHA256
        and evidence["vectors"] == vectors(),
        "replay sources differ",
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
        "exact retry replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
