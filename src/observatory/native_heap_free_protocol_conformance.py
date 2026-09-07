"""Exact free-wrapper replay with four excluded opaque response targets."""

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

ANALYSIS_KIND = "pe_native_heap_free_protocol_conformance"
SEALED_SHA256 = "c2e07687b933726d0f64cb0c01898468a54ef2aecb4de5e01125f3b8809ad3a3"
BODIES = {
    "first_thunk": (0x35785D, 0x357862),
    "second_thunk": (0x36FB17, 0x36FB1C),
    "wrapper": (0x389156, 0x389190),
}
STACK, RETURN, IMPORT, ERROR_PAGE = 0x02000000, 0x04000000, 0x05000000, 0x06000000
HEAP_GLOBAL, FREE_IAT, LAST_IAT = BASE + 0x4B7634, BASE + 0x3D621C, BASE + 0x3D6114
CALLS = {
    "heap_free": (0x38916C, IMPORT),
    "error": (0x389177, BASE + 0x385BCC),
    "get_last_error": (0x38917E, IMPORT + 0x1000),
    "map_error": (0x389185, BASE + 0x385B53),
}
MASK = 0xFFFFFFFF


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def protocol_oracle(pointer, responses):
    _require(type(pointer) is int and 0 <= pointer <= MASK, "invalid pointer word")
    _require(
        type(responses) is list and len(responses) <= 4, "invalid finite responses"
    )
    returned = pointer == 0
    kind = "heap_free"
    result = None
    error_cell = None
    last_error = None
    for response in responses:
        _require(
            not returned
            and type(response) is dict
            and set(response) == {"kind", "eax"}
            and response["kind"] == kind
            and type(response["eax"]) is int
            and 0 <= response["eax"] <= MASK,
            "free protocol response differs",
        )
        value = response["eax"]
        if kind == "heap_free":
            if value:
                returned = True
                result = value
            else:
                kind = "error"
        elif kind == "error":
            error_cell = value
            kind = "get_last_error"
        elif kind == "get_last_error":
            last_error = value
            kind = "map_error"
        else:
            returned = True
            result = value
    return dict(
        returned=returned,
        result=result,
        next_kind=None if returned else kind,
        error_cell=error_cell,
        last_error=last_error,
    )


def vectors():
    values = []
    for pointer in (0, 1, 0x70001000, MASK):
        patterns = [[]]
        if pointer:
            patterns.extend(
                [
                    [("heap_free", 1)],
                    [("heap_free", 0x80000000)],
                    [("heap_free", 0)],
                    [("heap_free", 0), ("error", ERROR_PAGE + 0x101)],
                    [
                        ("heap_free", 0),
                        ("error", ERROR_PAGE + 0x101),
                        ("get_last_error", 5),
                    ],
                ]
            )
            for last in (0, 5, MASK):
                for mapped in (0, 12, MASK):
                    patterns.append(
                        [
                            ("heap_free", 0),
                            ("error", ERROR_PAGE + 0x101),
                            ("get_last_error", last),
                            ("map_error", mapped),
                        ]
                    )
        for pattern in patterns:
            for handle in (0, 0x12345678):
                for alignment in range(16):
                    values.append(
                        dict(
                            pointer=pointer,
                            heap=handle,
                            alignment=alignment,
                            responses=[
                                dict(kind=kind, eax=value) for kind, value in pattern
                            ],
                        )
                    )
    return values


def _logic_flags(value):
    return (
        int(value == 0) << 6
        | (value >> 31) << 7
        | int((value & 255).bit_count() % 2 == 0) << 2
    )


def _volatile(index):
    return dict(
        ecx=0xA0000000 + index,
        edx=0xB0000000 + index,
        flags=2 | ((index * 0x2D5) & 0x8D5),
    )


def _expected(vector, initial, stack, error):
    relation = protocol_oracle(vector["pointer"], vector["responses"])
    entry = initial["esp"]
    frame = entry - 4
    pointer = vector["pointer"]
    memory = bytearray(stack)
    error_memory = bytearray(error)
    events = []

    def read(address, value):
        events.append(dict(access="read", address=address, width=4, value=value))

    def write(address, value):
        target, base = (
            (memory, STACK)
            if STACK <= address < STACK + 0x4000
            else (error_memory, ERROR_PAGE)
        )
        target[address - base : address - base + 4] = value.to_bytes(4, "little")
        events.append(dict(access="write", address=address, width=4, value=value))

    regs = dict(initial, ebp=frame, esp=frame)
    flags = _logic_flags(pointer)
    mask = 0x8D5
    write(frame, initial["ebp"])
    read(entry + 4, pointer)
    records = list(vector["responses"])
    if not relation["returned"]:
        records.append(dict(kind=relation["next_kind"], eax=None))
    for index, response in enumerate(records):
        kind = response["kind"]
        if kind == "heap_free":
            read(entry + 4, pointer)
            write(entry - 8, pointer)
            write(entry - 12, 0)
            read(HEAP_GLOBAL, vector["heap"])
            write(entry - 16, vector["heap"])
            regs["esp"] = entry - 16
        elif kind == "error":
            write(entry - 8, initial["esi"])
            regs["esp"] = entry - 8
        elif kind == "map_error":
            write(entry - 12, relation["last_error"])
            regs["esp"] = entry - 12
        if response["eax"] is None:
            break
        site, target = CALLS[kind]
        if kind == "heap_free":
            read(FREE_IAT, target)
        elif kind == "get_last_error":
            read(LAST_IAT, target)
        write(
            regs["esp"] - 4,
            BASE + site + (6 if kind in ("heap_free", "get_last_error") else 5),
        )
        output = _volatile(index + 1)
        regs.update(eax=response["eax"], ecx=output["ecx"], edx=output["edx"])
        flags = output["flags"] & 0x8D5
        mask = 0x8D5
        if kind == "heap_free":
            regs["esp"] = frame
            flags = _logic_flags(response["eax"])
            mask = 0x8C5
        elif kind == "error":
            regs["esi"] = response["eax"]
        elif kind == "map_error":
            read(entry - 12, relation["last_error"])
            regs["ecx"] = relation["last_error"]
            write(relation["error_cell"], response["eax"])
            read(entry - 8, initial["esi"])
            regs.update(esi=initial["esi"], esp=frame)
    if relation["returned"]:
        read(frame, initial["ebp"])
        read(entry, RETURN)
        regs.update(ebp=initial["ebp"], esp=entry + 4)
    return dict(
        protocol=relation,
        registers=regs,
        flags=flags,
        flag_mask=mask,
        stack=bytes(memory),
        error=bytes(error_memory),
        events=events,
    )


def _run_case(codes, points, vector, *, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    _require(
        type(vector["alignment"]) is int and 0 <= vector["alignment"] < 16,
        "invalid alignment",
    )
    _require(
        type(vector["heap"]) is int and 0 <= vector["heap"] <= MASK, "invalid heap word"
    )
    protocol_oracle(vector["pointer"], vector["responses"])
    for response in vector["responses"]:
        if response["kind"] == "error":
            _require(
                ERROR_PAGE <= response["eax"] <= ERROR_PAGE + 0xFFC,
                "error cell outside private replay page",
            )
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    pages = {BASE + (start & ~0xFFF) for start, end in BODIES.values()}
    pages.update(target & ~0xFFF for site, target in CALLS.values())
    pages.update((RETURN, ERROR_PAGE, HEAP_GLOBAL & ~0xFFF, FREE_IAT & ~0xFFF))
    for page in sorted(pages):
        machine.mem_map(page, 0x1000)
    machine.mem_map(STACK, 0x4000)
    for name, (start, end) in BODIES.items():
        machine.mem_write(BASE + start, codes[name])
    for site, target in CALLS.values():
        machine.mem_write(target, b"\xcc")
    machine.mem_write(RETURN, b"\xcc")
    entry = STACK + 0x2000 + vector["alignment"]
    original_stack = bytearray(
        ((i * 43) ^ (i >> 6) ^ 0xC7) & 255 for i in range(0x4000)
    )
    for address, value in ((entry, RETURN), (entry + 4, vector["pointer"])):
        original_stack[address - STACK : address - STACK + 4] = value.to_bytes(
            4, "little"
        )
    original_error = bytes(((i * 23) ^ (i >> 2) ^ 0x59) & 255 for i in range(0x1000))
    global_page = HEAP_GLOBAL & ~0xFFF
    iat_page = FREE_IAT & ~0xFFF
    original_global = bytearray(
        ((i * 7) ^ (i >> 3) ^ 0xAB) & 255 for i in range(0x1000)
    )
    original_global[HEAP_GLOBAL - global_page : HEAP_GLOBAL - global_page + 4] = vector[
        "heap"
    ].to_bytes(4, "little")
    original_iat = bytearray(((i * 11) ^ 0x6D) & 255 for i in range(0x1000))
    for address, kind in ((FREE_IAT, "heap_free"), (LAST_IAT, "get_last_error")):
        original_iat[address - iat_page : address - iat_page + 4] = CALLS[kind][
            1
        ].to_bytes(4, "little")
    machine.mem_write(STACK, bytes(original_stack))
    machine.mem_write(ERROR_PAGE, original_error)
    machine.mem_write(global_page, bytes(original_global))
    machine.mem_write(iat_page, bytes(original_iat))
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
    allowed = {int(p["rva"], 16) for rows in points.values() for p in rows}
    target_kinds = {target: kind for kind, (site, target) in CALLS.items()}
    site_kinds = {site: kind for kind, (site, target) in CALLS.items()}
    visited, events, summaries, frontiers = [], [], [], []
    index = 0
    pending = None
    resume = None
    protected_regions = (
        (STACK, 0x4000),
        (ERROR_PAGE, 0x1000),
        (global_page, 0x1000),
        (iat_page, 0x1000),
    )

    def on_code(m, address, size, user):
        nonlocal index, pending, resume
        if address in target_kinds:
            kind = target_kinds[address]
            _require(kind == pending, "unexpected opaque free target")
            slot = m.reg_read(x.UC_X86_REG_ESP)
            _require(
                slot
                == entry
                - (
                    {
                        "heap_free": 20,
                        "error": 12,
                        "get_last_error": 12,
                        "map_error": 16,
                    }[kind]
                ),
                "opaque free stack differs",
            )
            continuation = int.from_bytes(m.mem_read(slot, 4), "little")
            _require(
                continuation
                == BASE
                + CALLS[kind][0]
                + (6 if kind in ("heap_free", "get_last_error") else 5),
                "opaque continuation differs",
            )
            if kind == "heap_free":
                args = [
                    int.from_bytes(m.mem_read(slot + 4 + 4 * i, 4), "little")
                    for i in range(3)
                ]
                _require(
                    args == [vector["heap"], 0, vector["pointer"]],
                    "HeapFree arguments differ",
                )
            elif kind == "map_error":
                _require(
                    int.from_bytes(m.mem_read(slot + 4, 4), "little")
                    == expected["protocol"]["last_error"],
                    "mapper argument differs",
                )
            before = [bytes(m.mem_read(a, n)) for a, n in protected_regions]
            nonvolatile = {r: m.reg_read(ids[r]) for r in ("ebp", "ebx", "esi", "edi")}
            row = vector["responses"][index]
            index += 1
            output = _volatile(index)
            value = row["eax"] ^ (
                1 if negative == "mapper_result" and kind == "map_error" else 0
            )
            m.reg_write(x.UC_X86_REG_EAX, value)
            m.reg_write(x.UC_X86_REG_ECX, output["ecx"])
            m.reg_write(x.UC_X86_REG_EDX, output["edx"])
            m.reg_write(x.UC_X86_REG_EFLAGS, output["flags"])
            m.reg_write(x.UC_X86_REG_ESP, slot + (16 if kind == "heap_free" else 4))
            _require(
                before == [bytes(m.mem_read(a, n)) for a, n in protected_regions]
                and nonvolatile == {r: m.reg_read(ids[r]) for r in nonvolatile},
                "opaque callback changed protected state",
            )
            summaries.append(
                dict(
                    kind=kind,
                    entry_esp=slot,
                    continuation=continuation,
                    argument_cleanup=12 if kind == "heap_free" else 0,
                )
            )
            resume = continuation
            pending = None
            m.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "execution escaped exact free bodies")
        if pc in site_kinds:
            kind = site_kinds[pc]
            if index == len(vector["responses"]):
                frontiers.append(kind)
                m.emu_stop()
                return
            _require(
                vector["responses"][index]["kind"] == kind,
                "native free protocol differs",
            )
            if negative == "mapper_argument" and kind == "map_error":
                m.mem_write(
                    m.reg_read(x.UC_X86_REG_ESP),
                    (expected["protocol"]["last_error"] ^ 1).to_bytes(4, "little"),
                )
            pending = kind
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, size, value, user):
        write = access == uc.UC_MEM_WRITE
        _require(size == 4, "unexpected native memory width")
        if write:
            _require(
                entry - 20 <= address <= entry - 4
                or ERROR_PAGE <= address <= ERROR_PAGE + 0xFFC,
                "unexpected native free write",
            )
        else:
            _require(
                entry - 20 <= address <= entry + 4
                or address in (HEAP_GLOBAL, FREE_IAT, LAST_IAT),
                "unexpected native free read",
            )
        events.append(
            dict(
                access="write" if write else "read",
                address=address,
                width=size,
                value=(
                    value & MASK
                    if write
                    else int.from_bytes(m.mem_read(address, size), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    next_pc = BASE + BODIES["first_thunk"][0]
    for _ in range(6):
        resume = None
        machine.emu_start(next_pc, RETURN, count=100)
        if resume is None:
            break
        next_pc = resume
    else:
        raise ConformanceError("finite free replay bound exceeded")
    relation = expected["protocol"]
    _require(
        index == len(vector["responses"])
        and frontiers == ([] if relation["returned"] else [relation["next_kind"]]),
        "free oracle outcome differs",
    )
    target = RETURN if relation["returned"] else BASE + CALLS[relation["next_kind"]][0]
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == target, "free oracle final EIP differs"
    )
    actual = {name: machine.reg_read(reg) for name, reg in ids.items()}
    _require(actual == expected["registers"], "free oracle registers differ")
    _require(
        machine.reg_read(x.UC_X86_REG_EFLAGS) & expected["flag_mask"]
        == expected["flags"],
        "free defined flags differ",
    )
    _require(events == expected["events"], "free ordered native memory differs")
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == expected["stack"],
        "free full stack differs",
    )
    _require(
        bytes(machine.mem_read(ERROR_PAGE, 0x1000)) == expected["error"],
        "free full error page differs",
    )
    _require(
        bytes(machine.mem_read(global_page, 0x1000)) == bytes(original_global),
        "free global page changed",
    )
    _require(
        bytes(machine.mem_read(iat_page, 0x1000)) == bytes(original_iat),
        "free IAT page changed",
    )
    return dict(
        vector=vector,
        visited=visited,
        summaries=summaries,
        returned=relation["returned"],
        frontiers=frontiers,
        registers=actual,
        flags=expected["flags"],
        events_sha256=_canonical_sha256(events),
        stack_sha256=hashlib.sha256(expected["stack"]).hexdigest(),
        error_sha256=hashlib.sha256(expected["error"]).hexdigest(),
    )


def _build_unsealed(executable, semantics):
    from src.observatory import native_heap_free_protocol as sem

    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(semantics) == sem.SEALED_SHA256, "free semantics differs"
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
        witness = next(
            w for w in semantics["bodies"] if int(w["entry_rva"], 16) == start
        )
        _require(
            points[name] == witness["points"]
            and hashlib.sha256(codes[name]).hexdigest() == witness["sha256"],
            "exact free witness differs",
        )
    observations = [_run_case(codes, points, vector) for vector in vectors()]
    control_vector = dict(
        pointer=1,
        heap=0x12345678,
        alignment=0,
        responses=[
            dict(kind=k, eax=v)
            for k, v in [
                ("heap_free", 0),
                ("error", ERROR_PAGE + 0x101),
                ("get_last_error", 5),
                ("map_error", 12),
            ]
        ],
    )
    controls = []
    for negative, message in (
        ("mapper_result", "oracle registers"),
        ("mapper_argument", "mapper argument"),
    ):
        try:
            _run_case(codes, points, control_vector, negative=negative)
        except ConformanceError as exc:
            _require(
                message in str(exc), "negative control failed for unrelated reason"
            )
            controls.append(dict(name=negative, rejected=True))
        else:
            raise ConformanceError("free negative control accepted")
    visited = sorted(
        {p for observation in observations for p in observation["visited"]}
    )
    _require(
        visited == semantics["model_evidence"]["instruction_union_rvas"]
        and len(visited) == 24,
        "free replay coverage differs",
    )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=semantics["build_identity"],
        source_semantics_sha256=sem.SEALED_SHA256,
        bodies=semantics["bodies"],
        emulator=dict(
            name="Unicorn", version="2.1.4", architecture="x86", mode_bits=32
        ),
        decoder=dict(name="Capstone", version="5.0.7"),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=visited,
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            executed_instruction_sites=24,
            returned_cases=sum(o["returned"] for o in observations),
            frontier_cases=sum(not o["returned"] for o in observations),
            summarized_calls=sum(len(o["summaries"]) for o in observations),
            actual_import_executions=0,
            actual_accessor_or_mapper_instructions=0,
            negative_controls=2,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact thunks and free wrapper match an independent finite protocol and complete memory oracle",
            premises=[
                "Supplied heap-free responses remove twelve argument bytes, other supplied responses remove none",
                "Callbacks preserve complete stack, global, IAT and error pages plus nonvolatile registers",
                "Error cells lie in the mapped page disjoint from frames, globals, IAT and exact code",
            ],
            call_policy="Actual CALL instructions and indirect IAT reads execute; callbacks stop at excluded target bytes before any API, accessor or mapper instruction, then resume normal-return continuations",
            memory_policy="Native word accesses are compared in order; host continuation and argument checks are summary operations, not fabricated native read events",
            flags="Null CMP checks six flags, successful TEST omits undefined AF, mapped-error path preserves all six sampled mapper flags",
            not_claimed=[
                "Real freeing, API behavior, error-cell provenance or heap ownership",
                "Failure exceptions, original library execution or full resize equivalence",
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
    from src.observatory import native_heap_free_protocol as sem

    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "sealed free replay differs",
    )
    _require(
        evidence["source_semantics_sha256"] == sem.SEALED_SHA256
        and evidence["vectors"] == vectors(),
        "free replay source differs",
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
        "exact free replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
