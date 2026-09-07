"""Exact heap-wrapper protocol with supplied external call responses."""

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

ANALYSIS_KIND = "pe_native_heap_allocation_protocol_conformance"
SEALED_SHA256 = "f3a3a2ee0af914a5b23c2bf408d36f529563f275722dabc3a54596549f12d392"
BODIES = {
    "thunk": (0x379F52, 0x379F5D),
    "wrapper": (0x38942B, 0x389479),
    "flag_getter": (0x38DCE2, 0x38DCE8),
}
STACK, RETURN, IMPORT, ERROR_PAGE = 0x2000000, 0x4000000, 0x5000000, 0x6000000
HEAP_GLOBAL, FLAG_GLOBAL, IAT = BASE + 0x4B7634, BASE + 0x4B7328, BASE + 0x3D6220
CALLS = {
    "heap": (0x38945D, IMPORT),
    "handler": (0x38944A, BASE + 0x38BBC4),
    "error": (0x389469, BASE + 0x385BCC),
}
MASK = 0xFFFFFFFF


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def protocol_oracle(size, flag, responses):
    _require(
        all(type(v) is int and 0 <= v <= MASK for v in [size, flag]),
        "invalid input word",
    )
    _require(
        type(responses) is list and len(responses) <= 64, "invalid finite transcript"
    )
    kind = "error" if size > 0xFFFFFFE0 else "heap"
    result = None
    returned = False
    for row in responses:
        _require(
            not returned
            and type(row) is dict
            and set(row) == {"kind", "eax"}
            and row["kind"] == kind
            and type(row["eax"]) is int
            and 0 <= row["eax"] <= MASK,
            "protocol response differs",
        )
        if kind == "error":
            returned = True
            result = 0
        elif kind == "heap":
            if row["eax"]:
                returned = True
                result = row["eax"]
            else:
                kind = "handler" if flag else "error"
        else:
            kind = "heap" if row["eax"] else "error"
    return dict(returned=returned, result=result, next_kind=None if returned else kind)


def vectors():
    result = []
    for size in [0, 8, 0xFFFFFFE0, 0xFFFFFFE1]:
        for flag in [0, 1]:
            if size > 0xFFFFFFE0:
                patterns = [[], [("error", ERROR_PAGE + 0x100)]]
            else:
                patterns = [[], [("heap", 0x70001000)], [("heap", 0)]]
                if not flag:
                    patterns += [[("heap", 0), ("error", ERROR_PAGE + 0x100)]]
                else:
                    patterns += [
                        [("heap", 0), ("handler", 0)],
                        [("heap", 0), ("handler", 0), ("error", ERROR_PAGE + 0x100)],
                        [("heap", 0), ("handler", 1)],
                        [("heap", 0), ("handler", 1), ("heap", 0x80000000)],
                        [
                            ("heap", 0),
                            ("handler", 1),
                            ("heap", 0),
                            ("handler", 0),
                            ("error", ERROR_PAGE + 0x100),
                        ],
                    ]
            for pattern in patterns:
                for heap in [0, 0x12345678]:
                    for alignment in range(16):
                        result.append(
                            dict(
                                size=size,
                                flag=flag,
                                heap=heap,
                                alignment=alignment,
                                responses=[dict(kind=k, eax=v) for k, v in pattern],
                            )
                        )
    return result


def _logical_flags(value):
    return (
        (int(value == 0) << 6)
        | ((value >> 31) << 7)
        | (int((value & 255).bit_count() % 2 == 0) << 2)
    )


def _expected(vector, initial, original_stack, original_error):
    size, flag, heap = vector["size"], vector["flag"], vector["heap"]
    rows = vector["responses"]
    relation = protocol_oracle(size, flag, rows)
    entry = initial["esp"]
    memory = bytearray(original_stack)
    error = bytearray(original_error)
    events = []

    def read(address, value):
        events.append(dict(access="read", address=address, width=4, value=value))

    def write(address, value):
        target, base = (
            (memory, STACK)
            if STACK <= address < STACK + 0x4000
            else (error, ERROR_PAGE)
        )
        target[address - base : address - base + 4] = value.to_bytes(4, "little")
        events.append(dict(access="write", address=address, width=4, value=value))

    write(entry - 4, initial["ebp"])
    read(entry - 4, initial["ebp"])
    write(entry - 4, initial["ebp"])
    write(entry - 8, initial["esi"])
    read(entry + 4, size)
    oversized = size > 0xFFFFFFE0
    effective = size if oversized else max(size, 1)
    regs = dict(initial, ebp=entry - 4, esi=effective, esp=entry - 8)
    kind = "error" if oversized else "heap"
    flags, flag_mask = (
        (_cmp_flags(size, 0xFFFFFFE0), 0x8D5)
        if oversized
        else ((0, 0x8D5) if size == 0 else (_logical_flags(size), 0x8C5))
    )
    index = 0
    getter_calls = 0
    while True:
        if kind == "heap":
            write(entry - 12, effective)
            write(entry - 16, 0)
            read(HEAP_GLOBAL, heap)
            write(entry - 20, heap)
            regs["esp"] = entry - 20
        elif kind == "handler":
            write(entry - 12, effective)
            regs["esp"] = entry - 12
        if index == len(rows):
            break
        site, _ = CALLS[kind]
        if kind == "heap":
            read(IAT, IMPORT)
        write(regs["esp"] - 4, BASE + site + (6 if kind == "heap" else 5))
        row = rows[index]
        index += 1
        regs.update(
            eax=row["eax"],
            ecx=0xA0000000 + index,
            edx=0xB0000000 + index,
            esp=entry - 8,
        )
        if kind == "error":
            _require(
                ERROR_PAGE <= row["eax"] <= ERROR_PAGE + 0xFFC,
                "error response outside replay page",
            )
            write(row["eax"], 12)
            regs["eax"] = 0
            flags, flag_mask = 0x44, 0x8C5
            break
        if kind == "handler":
            read(entry - 12, effective)
            regs["ecx"] = effective
            flags, flag_mask = _logical_flags(row["eax"]), 0x8C5
            kind = "heap" if row["eax"] else "error"
            continue
        flags, flag_mask = _logical_flags(row["eax"]), 0x8C5
        if row["eax"]:
            break
        # The flag getter executes CALL, MOV-global, RET natively.
        write(entry - 12, BASE + 0x389445)
        read(FLAG_GLOBAL, flag)
        read(entry - 12, BASE + 0x389445)
        getter_calls += 1
        regs["eax"] = flag
        flags, flag_mask = _logical_flags(flag), 0x8C5
        kind = "handler" if flag else "error"
    if relation["returned"]:
        read(entry - 8, initial["esi"])
        read(entry - 4, initial["ebp"])
        read(entry, RETURN)
        regs.update(esi=initial["esi"], ebp=initial["ebp"], esp=entry + 4)
    return dict(
        protocol=relation,
        registers=regs,
        flags=flags,
        flag_mask=flag_mask,
        stack=bytes(memory),
        error=bytes(error),
        events=events,
        getter_calls=getter_calls,
    )


def _run_case(codes, points, vector, *, negative=False):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for name, (start, end) in BODIES.items():
        machine.mem_map(BASE + (start & ~0xFFF), 0x1000)
        machine.mem_write(BASE + start, codes[name])
    for _, target in CALLS.values():
        machine.mem_map(target & ~0xFFF, 0x2000)
    for page, size in [
        (STACK, 0x4000),
        (RETURN, 0x1000),
        (ERROR_PAGE, 0x1000),
        (HEAP_GLOBAL & ~0xFFF, 0x1000),
        (IAT & ~0xFFF, 0x1000),
    ]:
        machine.mem_map(page, size)
    entry = STACK + 0x2000 + vector["alignment"]
    original_stack = bytearray(
        ((i * 43) ^ (i >> 6) ^ 0xC7) & 255 for i in range(0x4000)
    )
    original_stack[entry - STACK : entry - STACK + 4] = RETURN.to_bytes(4, "little")
    original_stack[entry - STACK + 4 : entry - STACK + 8] = vector["size"].to_bytes(
        4, "little"
    )
    original_error = bytes(((i * 23) ^ (i >> 2) ^ 0x59) & 255 for i in range(0x1000))
    machine.mem_write(STACK, bytes(original_stack))
    machine.mem_write(ERROR_PAGE, original_error)
    global_page = HEAP_GLOBAL & ~0xFFF
    original_global = bytearray(
        ((i * 7) ^ (i >> 3) ^ 0xAB) & 255 for i in range(0x1000)
    )
    for address, value in [
        (HEAP_GLOBAL, vector["heap"]),
        (FLAG_GLOBAL, vector["flag"]),
    ]:
        original_global[address - global_page : address - global_page + 4] = (
            value.to_bytes(4, "little")
        )
    machine.mem_write(global_page, bytes(original_global))
    original_iat = bytearray(0x1000)
    original_iat[IAT & 0xFFF : (IAT & 0xFFF) + 4] = IMPORT.to_bytes(4, "little")
    machine.mem_write(IAT & ~0xFFF, bytes(original_iat))
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
    initial = {name: 0x10293847 + i * 0x1010101 for i, name in enumerate(ids)}
    initial["esp"] = entry
    expected = _expected(vector, initial, original_stack, original_error)
    for name, value in initial.items():
        machine.reg_write(ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 2)
    if negative:
        machine.mem_write(FLAG_GLOBAL, (vector["flag"] ^ 1).to_bytes(4, "little"))
    allowed = {int(p["rva"], 16) for rows in points.values() for p in rows}
    target_kinds = {target: kind for kind, (_, target) in CALLS.items()}
    site_kinds = {site: kind for kind, (site, _) in CALLS.items()}
    visited, events, summaries, frontiers = [], [], [], []
    index = 0
    pending = None
    resume_at = None

    def on_code(m, address, size, user):
        nonlocal index, pending, resume_at
        if address in target_kinds:
            kind = target_kinds[address]
            _require(kind == pending, "unexpected opaque target")
            row = vector["responses"][index]
            slot = m.reg_read(x.UC_X86_REG_ESP)
            wanted_slot = entry - (
                24 if kind == "heap" else 16 if kind == "handler" else 12
            )
            _require(slot == wanted_slot, "opaque callee stack differs")
            continuation = int.from_bytes(m.mem_read(slot, 4), "little")
            _require(
                continuation == BASE + CALLS[kind][0] + (6 if kind == "heap" else 5),
                "opaque continuation differs",
            )
            if kind == "heap":
                args = [
                    int.from_bytes(m.mem_read(slot + 4 + 4 * i, 4), "little")
                    for i in range(3)
                ]
                _require(
                    args == [vector["heap"], 0, max(vector["size"], 1)],
                    "HeapAlloc arguments differ",
                )
            elif kind == "handler":
                _require(
                    int.from_bytes(m.mem_read(slot + 4, 4), "little")
                    == max(vector["size"], 1),
                    "handler size differs",
                )
            index += 1
            m.reg_write(x.UC_X86_REG_EAX, row["eax"])
            m.reg_write(x.UC_X86_REG_ECX, 0xA0000000 + index)
            m.reg_write(x.UC_X86_REG_EDX, 0xB0000000 + index)
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            m.reg_write(x.UC_X86_REG_ESP, slot + (16 if kind == "heap" else 4))
            summaries.append(dict(kind=kind, entry_esp=slot, continuation=continuation))
            resume_at = continuation
            pending = None
            m.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "execution escaped heap protocol")
        if pc in site_kinds:
            kind = site_kinds[pc]
            if index == len(vector["responses"]):
                frontiers.append(kind)
                m.emu_stop()
                return
            _require(
                vector["responses"][index]["kind"] == kind,
                "native heap protocol differs",
            )
            pending = kind
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, size, value, user):
        write = access == uc.UC_MEM_WRITE
        if write:
            _require(
                size == 4
                and (
                    entry - 24 <= address <= entry - 4
                    or ERROR_PAGE <= address <= ERROR_PAGE + 0xFFC
                ),
                "unexpected protocol write",
            )
        else:
            _require(
                size == 4
                and (
                    entry - 24 <= address <= entry + 4
                    or address in [HEAP_GLOBAL, FLAG_GLOBAL, IAT]
                ),
                "unexpected protocol read",
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
    next_pc = BASE + BODIES["thunk"][0]
    for _ in range(66):
        resume_at = None
        machine.emu_start(next_pc, RETURN, count=1000)
        if resume_at is None:
            break
        next_pc = resume_at
    else:
        raise ConformanceError("finite replay bound exceeded")
    protocol = expected["protocol"]
    _require(
        index == len(vector["responses"])
        and frontiers == ([] if protocol["returned"] else [protocol["next_kind"]]),
        "heap protocol oracle outcome differs",
    )
    wanted_ip = (
        RETURN if protocol["returned"] else BASE + CALLS[protocol["next_kind"]][0]
    )
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == wanted_ip,
        "heap protocol return target differs",
    )
    actual = {name: machine.reg_read(reg) for name, reg in ids.items()}
    _require(actual == expected["registers"], "heap protocol registers differ")
    _require(
        machine.reg_read(x.UC_X86_REG_EFLAGS) & expected["flag_mask"]
        == expected["flags"],
        "heap protocol defined flags differ",
    )
    _require(events == expected["events"], "heap protocol ordered memory differs")
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == expected["stack"],
        "heap protocol full stack differs",
    )
    _require(
        bytes(machine.mem_read(ERROR_PAGE, 0x1000)) == expected["error"],
        "heap protocol error page differs",
    )
    _require(
        bytes(machine.mem_read(global_page, 0x1000)) == bytes(original_global),
        "heap protocol globals changed",
    )
    _require(
        bytes(machine.mem_read(IAT & ~0xFFF, 0x1000)) == bytes(original_iat),
        "heap protocol IAT changed",
    )
    return dict(
        vector=vector,
        visited=visited,
        summaries=summaries,
        returned=protocol["returned"],
        frontiers=frontiers,
        getter_calls=expected["getter_calls"],
        registers=actual,
        events_sha256=_canonical_sha256(events),
    )


def _build_unsealed(executable, semantics):
    from src.observatory import native_heap_allocation_protocol as sem

    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "heap protocol semantics differs",
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
    _require(sum(len(p) for p in points.values()) == 39, "body extent differs")
    observations = [_run_case(codes, points, v) for v in vectors()]
    caught = False
    try:
        _run_case(
            codes,
            points,
            dict(
                size=8,
                flag=0,
                heap=0,
                alignment=0,
                responses=[dict(kind="heap", eax=0)],
            ),
            negative=True,
        )
    except ConformanceError as exc:
        caught = "heap protocol oracle outcome" in str(exc)
    _require(caught, "changed retry flag control accepted")
    visited = sorted({p for row in observations for p in row["visited"]})
    _require(len(visited) == 39, "full protocol coverage differs")
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
            executed_instruction_sites=39,
            returned=sum(r["returned"] for r in observations),
            frontier_stops=sum(not r["returned"] for r in observations),
            opaque_call_instructions=sum(len(r["summaries"]) for r in observations),
            executed_flag_getter_calls=sum(r["getter_calls"] for r in observations),
            opaque_callee_instructions=0,
            negative_controls=1,
            accounting_promotions=0,
        ),
        summaries=dict(
            runtime_iat_target=IMPORT,
            heap_return="Host consumes return word plus twelve argument bytes",
            other_returns="Host consumes return word only",
            volatile_outputs="EAX supplied; ECX and EDX sampled by response index; flags set to 0x246",
            preserves="All other registers and all mapped memory, including temporary arguments and globals",
        ),
        scope=dict(
            claim="Exact wrapper, candidate thunk and flag getter agree with independent finite protocol and memory oracle",
            boundary="CALL instructions and flag getter execute; imported allocator, handler and error accessor instructions do not",
            flags="TEST and XOR omit undefined AF; initial zero INC and oversized CMP compare all six arithmetic flags",
            not_claimed=[
                "HeapAlloc success or actual heap state",
                "Handler or error accessor effects beyond supplied response",
                "Termination beyond finite transcript",
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
    from src.observatory import native_heap_allocation_protocol as sem

    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "sealed heap replay differs",
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
        "exact heap protocol replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
