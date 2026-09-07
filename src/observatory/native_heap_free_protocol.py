"""Finite free-wrapper protocol with explicit opaque API and error summaries."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import capstone.x86_const as x86
import pefile
from src.observatory import native_vector_deallocation_semantics as deallocation
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
ANALYSIS_KIND = "pe_native_heap_free_protocol"
SEALED_SHA256 = "768d063a914e392138cb584fc50049b6481d545b8f58a49eca18bd85bcfafca5"
SOURCE_PINS = {
    "program_facts": deallocation.SOURCE_PINS["program_facts"],
    "deallocation_semantics": (deallocation.ANALYSIS_KIND, deallocation.SEALED_SHA256),
}
START = 0x35785D
BODIES = {START: 0x357862, 0x36FB17: 0x36FB1C, 0x389156: 0x389190}
CALLS = {
    "heap_free": 0x38916C,
    "error": 0x389177,
    "get_last_error": 0x38917E,
    "map_error": 0x389185,
}
SITE_KINDS = {site: kind for kind, site in CALLS.items()}
HEAP_WORD, FREE_IAT, LAST_IAT = BASE + 0x4B7634, BASE + 0x3D621C, BASE + 0x3D6114
FREE_TARGET, LAST_TARGET = 0x70001000, 0x70002000
U32 = 0xFFFFFFFF


def R(name):
    return ("reg", name)


def I(value):
    return ("imm", value)


def M(base, offset=0):
    return ("mem", base, offset)


OPS = {
    START: ("jmp", I(BASE + 0x36FB17)),
    0x36FB17: ("jmp", I(BASE + 0x389156)),
    0x389156: ("mov", R("edi"), R("edi")),
    0x389158: ("push", R("ebp")),
    0x389159: ("mov", R("ebp"), R("esp")),
    0x38915B: ("cmp", M("ebp", 8), I(0)),
    0x38915F: ("je", I(BASE + 0x38918E)),
    0x389161: ("push", M("ebp", 8)),
    0x389164: ("push", I(0)),
    0x389166: ("push", M(None, HEAP_WORD)),
    0x38916C: ("call", M(None, FREE_IAT)),
    0x389172: ("test", R("eax"), R("eax")),
    0x389174: ("jne", I(BASE + 0x38918E)),
    0x389176: ("push", R("esi")),
    0x389177: ("call", I(BASE + 0x385BCC)),
    0x38917C: ("mov", R("esi"), R("eax")),
    0x38917E: ("call", M(None, LAST_IAT)),
    0x389184: ("push", R("eax")),
    0x389185: ("call", I(BASE + 0x385B53)),
    0x38918A: ("pop", R("ecx")),
    0x38918B: ("mov", M("esi"), R("eax")),
    0x38918D: ("pop", R("esi")),
    0x38918E: ("pop", R("ebp")),
    0x38918F: ("ret",),
}
ORDER = list(OPS)
SIZES = {}
for start, end in BODIES.items():
    points = [p for p in ORDER if start <= p < end]
    SIZES.update(
        {
            p: (points[i + 1] if i + 1 < len(points) else end) - p
            for i, p in enumerate(points)
        }
    )


class HeapFreeError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise HeapFreeError(message)


def _normalize(fn):
    try:
        return fn()
    except HeapFreeError:
        raise
    except Exception as exc:
        raise HeapFreeError(str(exc)) from exc


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)
    return value


def free_protocol_spec(pointer, responses, allow_frontier=False):
    _u32(pointer, "pointer")
    _require(type(allow_frontier) is bool, "invalid frontier permission")
    _require(
        type(responses) is list and len(responses) <= 4,
        "invalid finite free transcript",
    )
    for response in responses:
        _require(
            isinstance(response, Mapping)
            and set(response) == {"kind", "eax"}
            and type(response["kind"]) is str
            and response["kind"] in CALLS,
            "invalid response record",
        )
        _u32(response["eax"], "opaque result")
    if pointer == 0:
        _require(not responses, "null pointer has no calls")
        return {
            "outcome": "null_return",
            "calls": [],
            "frontier_kind": None,
            "result": None,
            "error_cell": None,
            "last_error": None,
            "result_source": "entry EAX",
        }
    state = "heap_free"
    calls = []
    error_cell = None
    last_error = None
    for index in range(len(responses) + 1):
        if index == len(responses):
            _require(allow_frontier, "missing free protocol response")
            return {
                "outcome": "frontier",
                "calls": calls,
                "frontier_kind": state,
                "result": None,
                "error_cell": error_cell,
                "last_error": last_error,
                "result_source": None,
            }
        response = responses[index]
        _require(response["kind"] == state, "free response order differs")
        calls.append(dict(response))
        if state == "heap_free" and response["eax"] or state == "map_error":
            _require(index + 1 == len(responses), "unused free responses")
            return {
                "outcome": (
                    "heap_success_return"
                    if state == "heap_free"
                    else "mapped_error_return"
                ),
                "calls": calls,
                "frontier_kind": None,
                "result": response["eax"],
                "error_cell": error_cell,
                "last_error": last_error,
                "result_source": state,
            }
        if state == "heap_free":
            state = "error"
        elif state == "error":
            error_cell = response["eax"]
            state = "get_last_error"
        else:
            last_error = response["eax"]
            state = "map_error"
    raise HeapFreeError("unreachable protocol state")


def _cmp_flags(left, right):
    result = (left - right) & U32
    return {
        "cf": int(left < right),
        "zf": int(result == 0),
        "sf": result >> 31,
        "of": ((left ^ right) & (left ^ result)) >> 31,
        "af": ((left ^ right ^ result) >> 4) & 1,
        "pf": int((result & 255).bit_count() % 2 == 0),
    }


def _test_flags(value):
    return {
        "cf": 0,
        "zf": int(value == 0),
        "sf": value >> 31,
        "of": 0,
        "af": None,
        "pf": int((value & 255).bit_count() % 2 == 0),
    }


def summary_outputs(response, index, seed):
    word = (seed + 0x13579BDF + index * 0x1020304) & U32
    return {
        "eax": response["eax"],
        "ecx": word,
        "edx": word ^ 0xA5A55A5A,
        "arithmetic_flags": {
            name: (word >> bit) & 1
            for bit, name in enumerate(("cf", "zf", "sf", "of", "af", "pf"))
        },
    }


def case_fixture(pointer, heap_handle, responses, frame_alignment=0, seed=1):
    _u32(pointer, "pointer")
    _u32(heap_handle, "heap handle")
    _require(
        type(frame_alignment) is int and 0 <= frame_alignment < 16,
        "invalid frame alignment",
    )
    _u32(seed, "seed")
    stack = 0x30001000 + frame_alignment
    regs = {
        r: (0xA1000000 + i * 0x10101 + seed) & U32
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs["esp"] = stack
    memory = {
        stack + i: (0xBABE0000 + i + seed) & U32
        for i in (-24, -20, -16, -12, -8, -4, 0, 4, 8)
    }
    memory.update(
        {
            stack + 4: pointer,
            HEAP_WORD: heap_handle,
            FREE_IAT: FREE_TARGET,
            LAST_IAT: LAST_TARGET,
        }
    )
    protected = dict(memory)
    for response in responses:
        if response["kind"] == "error":
            cell = response["eax"]
            _require(
                cell <= U32 - 3
                and all(cell + 4 <= a or a + 4 <= cell for a in protected),
                "error cell aliases protected storage or wraps",
            )
            _require(
                all(
                    cell + 4 <= BASE + start or BASE + end <= cell
                    for start, end in BODIES.items()
                ),
                "error cell aliases modeled code",
            )
            memory[cell] = (0xCCDD0011 + seed) & U32
    return {
        "registers": regs,
        "memory": memory,
        "stack": stack,
        "frame": stack - 4,
        "return_address": memory[stack],
    }


def _expected_state(pointer, heap_handle, spec, fixture, seed):
    frame = fixture["frame"]
    initial = fixture["registers"]
    regs = dict(initial, ebp=frame, esp=frame)
    memory = dict(fixture["memory"])
    events = []
    flags = _cmp_flags(pointer, 0)

    def event(kind, address, value, origin="instruction"):
        events.append(
            {
                "kind": kind,
                "address": address,
                "value": value,
                "width": 4,
                "origin": origin,
            }
        )
        if kind == "write":
            memory[address] = value

    event("write", frame, initial["ebp"])
    event("read", frame + 8, pointer)
    planned = list(spec["calls"])
    if spec["frontier_kind"] is not None:
        planned.append({"kind": spec["frontier_kind"], "eax": None})
    for index, response in enumerate(planned):
        kind = response["kind"]
        if kind == "heap_free":
            event("read", frame + 8, pointer)
            event("write", frame - 4, pointer)
            event("write", frame - 8, 0)
            event("read", HEAP_WORD, heap_handle)
            event("write", frame - 12, heap_handle)
            regs["esp"] = frame - 12
        elif kind == "error":
            event("write", frame - 4, initial["esi"])
            regs["esp"] = frame - 4
        elif kind == "map_error":
            event("write", frame - 8, spec["last_error"])
            regs["esp"] = frame - 8
        if response["eax"] is None:
            break
        if kind in ("heap_free", "get_last_error"):
            event(
                "read",
                FREE_IAT if kind == "heap_free" else LAST_IAT,
                FREE_TARGET if kind == "heap_free" else LAST_TARGET,
            )
        continuation = (
            BASE + CALLS[kind] + (6 if kind in ("heap_free", "get_last_error") else 5)
        )
        return_slot = regs["esp"] - 4
        event("write", return_slot, continuation)
        output = summary_outputs(response, index, seed)
        regs.update({r: output[r] for r in ("eax", "ecx", "edx")})
        flags = output["arithmetic_flags"]
        event("read", return_slot, continuation, "opaque_normal_return")
        if kind == "heap_free":
            regs["esp"] = frame
            flags = _test_flags(response["eax"])
        elif kind == "error":
            regs["esi"] = response["eax"]
        elif kind == "map_error":
            event("read", frame - 8, spec["last_error"])
            regs["ecx"] = spec["last_error"]
            regs["esp"] = frame - 4
            event("write", spec["error_cell"], response["eax"])
            event("read", frame - 4, initial["esi"])
            regs["esi"] = initial["esi"]
            regs["esp"] = frame
    if spec["outcome"] != "frontier":
        event("read", frame, initial["ebp"])
        event("read", frame + 4, fixture["return_address"])
        regs.update(ebp=initial["ebp"], esp=frame + 8)
    return regs, memory, flags, events


def model_case(
    pointer,
    heap_handle,
    responses,
    allow_frontier=False,
    frame_alignment=0,
    seed=1,
    ops=None,
):
    spec = free_protocol_spec(pointer, responses, allow_frontier)
    fixture = case_fixture(pointer, heap_handle, responses, frame_alignment, seed)
    regs, memory = dict(fixture["registers"]), dict(fixture["memory"])
    operations = OPS if ops is None else ops
    pc = START
    flags = None
    index = 0
    returned = False
    return_address = None
    trace, events, calls = [], [], []

    def access(address, origin="instruction"):
        _require(address in memory, "unmapped word read")
        value = memory[address]
        events.append(
            {
                "kind": "read",
                "address": address,
                "value": value,
                "width": 4,
                "origin": origin,
            }
        )
        return value

    def read(arg):
        if arg[0] == "reg":
            return regs[arg[1]]
        if arg[0] == "imm":
            return arg[1] & U32
        return access(((regs[arg[1]] if arg[1] else 0) + arg[2]) & U32)

    def write(arg, value):
        if arg[0] == "reg":
            regs[arg[1]] = value
        else:
            address = ((regs[arg[1]] if arg[1] else 0) + arg[2]) & U32
            _require(address in memory, "unmapped word write")
            memory[address] = value
            events.append(
                {
                    "kind": "write",
                    "address": address,
                    "value": value,
                    "width": 4,
                    "origin": "instruction",
                }
            )

    def push(value):
        regs["esp"] = (regs["esp"] - 4) & U32
        write(M("esp"), value)

    while not returned:
        _require(pc in operations and len(trace) < 100, "invalid free protocol path")
        op, *args = operations[pc]
        if op == "call" and index == len(responses):
            _require(allow_frontier, "missing opaque free response")
            break
        trace.append(f"0x{pc:08x}")
        next_pc = pc + SIZES[pc]
        if op == "mov":
            write(args[0], read(args[1]))
        elif op == "push":
            push(read(args[0]))
        elif op == "pop":
            write(args[0], access(regs["esp"]))
            regs["esp"] = (regs["esp"] + 4) & U32
        elif op == "cmp":
            flags = _cmp_flags(read(args[0]), read(args[1]))
        elif op == "test":
            flags = _test_flags(read(args[0]) & read(args[1]))
        elif op in ("jmp", "je", "jne"):
            if (
                op == "jmp"
                or op == "je"
                and flags["zf"]
                or op == "jne"
                and not flags["zf"]
            ):
                next_pc = read(args[0]) - BASE
        elif op == "call":
            kind = SITE_KINDS[pc]
            response = responses[index]
            _require(response["kind"] == kind, "free response kind differs")
            target = read(args[0])
            wanted_target = {
                "heap_free": FREE_TARGET,
                "get_last_error": LAST_TARGET,
                "error": BASE + 0x385BCC,
                "map_error": BASE + 0x385B53,
            }[kind]
            _require(target == wanted_target, "opaque free target differs")
            before = dict(regs)
            push(BASE + next_pc)
            before_memory = dict(memory)
            call_esp = regs["esp"]
            output = summary_outputs(response, index, seed)
            regs.update({r: output[r] for r in ("eax", "ecx", "edx")})
            flags = output["arithmetic_flags"]
            _require(
                access(regs["esp"], "opaque_normal_return") == BASE + next_pc,
                "opaque continuation differs",
            )
            cleanup = 12 if kind == "heap_free" else 0
            regs["esp"] = (regs["esp"] + 4 + cleanup) & U32
            _require(
                all(regs[r] == before[r] for r in ("ebp", "ebx", "esi", "edi"))
                and memory == before_memory,
                "opaque free preservation differs",
            )
            _require(
                regs["esp"] == before["esp"] + cleanup, "opaque stack cleanup differs"
            )
            calls.append(
                {
                    "kind": kind,
                    "target": target,
                    "site_rva": f"0x{pc:08x}",
                    "callee_entry_esp": call_esp,
                    "callee_argument_cleanup": cleanup,
                    "outputs": output,
                }
            )
            index += 1
        elif op == "ret":
            return_address = access(regs["esp"])
            regs["esp"] = (regs["esp"] + 4) & U32
            returned = True
        else:
            raise HeapFreeError("unsupported free operation")
        pc = next_pc
    expected_regs, expected_memory, expected_flags, expected_events = _expected_state(
        pointer, heap_handle, spec, fixture, seed
    )
    _require(
        index == len(responses) and returned == (spec["outcome"] != "frontier"),
        "free termination differs",
    )
    if not returned:
        _require(pc == CALLS[spec["frontier_kind"]], "free frontier differs")
    _require(
        return_address == (fixture["return_address"] if returned else None),
        "free caller return differs",
    )
    _require(
        regs == expected_regs and flags == expected_flags,
        "free register or flag relation differs",
    )
    _require(
        memory == expected_memory and events == expected_events,
        "free ordered memory relation differs",
    )
    return {
        "inputs": {
            "pointer": pointer,
            "heap_handle": heap_handle,
            "responses": responses,
            "allow_frontier": allow_frontier,
            "frame_alignment": frame_alignment,
            "seed": seed,
        },
        "protocol": spec,
        "returned": returned,
        "return_address": return_address,
        "frontier_rva": None if returned else f"0x{pc:08x}",
        "registers": regs,
        "arithmetic_flags": flags,
        "events": events,
        "calls": calls,
        "trace_rvas": trace,
        "memory": [{"address": a, "value": v} for a, v in sorted(memory.items())],
    }


def case_profiles(pointer):
    if pointer == 0:
        return [([], False)]

    def r(kind, value):
        return {"kind": kind, "eax": value}

    result = []
    for last in (0, 5, U32):
        for mapped in (0, 12, U32):
            result.append(
                (
                    [
                        r("heap_free", 0),
                        r("error", 0x10000040),
                        r("get_last_error", last),
                        r("map_error", mapped),
                    ],
                    False,
                )
            )
    result.extend([([r("heap_free", 1)], False), ([r("heap_free", 0x80000000)], False)])
    sequence = [r("heap_free", 0), r("error", 0x10000040), r("get_last_error", 5)]
    result.extend((sequence[:n], True) for n in range(4))
    return result


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
    _require([r.address - BASE for r in rows] == ORDER, "free body points differ")
    for row in rows:
        args = []
        for arg in row.operands:
            if arg.type == x86.X86_OP_REG:
                args.append(R(row.reg_name(arg.reg)))
            elif arg.type == x86.X86_OP_IMM:
                args.append(I(arg.imm))
            elif arg.type == x86.X86_OP_MEM:
                _require(
                    not arg.mem.segment and not arg.mem.index, "unexpected memory mode"
                )
                args.append(
                    M(
                        row.reg_name(arg.mem.base) if arg.mem.base else None,
                        arg.mem.disp,
                    )
                )
            else:
                raise HeapFreeError("unexpected operand")
        pc = row.address - BASE
        _require(
            (row.mnemonic, *args) == OPS[pc]
            and row.size == SIZES[pc]
            and [a.size for a in row.operands] == [4] * len(args),
            "exact free grammar differs",
        )


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    rows = [
        r
        for start in BODIES
        for r in _decode_body(data, image, sources["program_facts"], start)
    ]
    _grammar(rows)
    caller = _decode_body(data, image, sources["program_facts"], 0x7800)
    _require(
        [_point(r) for r in caller]
        == sources["deallocation_semantics"]["body"]["points"],
        "deallocation caller differs",
    )
    incoming = next(r for r in caller if r.address - BASE == 0x7851)
    _require(
        incoming.id == x86.X86_INS_CALL and incoming.operands[0].imm == BASE + START,
        "free incoming edge differs",
    )
    pe = pefile.PE(data=data)
    imported = []
    for slot, name in ((FREE_IAT, "HeapFree"), (LAST_IAT, "GetLastError")):
        found = [
            (
                entry.dll.decode("ascii"),
                symbol.name.decode("ascii") if symbol.name else None,
                symbol.ordinal,
            )
            for entry in pe.DIRECTORY_ENTRY_IMPORT
            for symbol in entry.imports
            if symbol.address == slot
        ]
        _require(
            found == [("KERNEL32.dll", name, None)], "free import identity differs"
        )
        imported.append(
            {"iat_rva": f"0x{slot-BASE:08x}", "dll": "KERNEL32.dll", "name": name}
        )
    pointers = [0, 1, 0x10001000, U32]
    heaps = [0, 0x81230000]
    cases = [
        model_case(pointer, handle, responses, frontier, alignment, seed)
        for pointer in pointers
        for responses, frontier in case_profiles(pointer)
        for handle in heaps
        for alignment in (0, 1, 7, 15)
        for seed in (0, U32)
    ]
    union = sorted({pc for case in cases for pc in case["trace_rvas"]})
    _require(union == [f"0x{pc:08x}" for pc in ORDER], "free protocol coverage differs")
    controls = []
    for name, pc, replacement, pointer, profile in (
        ("wrong_null_guard", 0x38915B, ("cmp", M("ebp", 8), I(1)), 0, 0),
        ("wrong_free_flags", 0x389164, ("push", I(1)), 1, 9),
        ("wrong_error_store", 0x38918B, ("mov", M("esi"), R("ecx")), 1, 1),
        ("wrong_saved_register", 0x38918D, ("pop", R("edi")), 1, 1),
        ("wrong_mapper_argument", 0x389184, ("push", I(99)), 1, 1),
    ):
        changed = dict(OPS)
        changed[pc] = replacement
        responses, frontier = case_profiles(pointer)[profile]
        try:
            model_case(pointer, 0x81230000, responses, frontier, ops=changed)
        except HeapFreeError:
            controls.append(
                {"name": name, "kind": "semantic_mutation", "rejected": True}
            )
        else:
            raise HeapFreeError("semantic mutation accepted: " + name)
    try:
        model_case(
            1,
            0,
            [{"kind": "heap_free", "eax": 0}, {"kind": "error", "eax": FREE_IAT}],
            True,
        )
    except HeapFreeError:
        controls.append(
            {
                "name": "error_cell_iat_alias",
                "kind": "domain_rejection",
                "rejected": True,
            }
        )
    else:
        raise HeapFreeError("error-cell alias accepted")
    bodies = []
    for start, end in BODIES.items():
        body = [r for r in rows if start <= r.address - BASE < end]
        bodies.append(
            {
                "entry_rva": f"0x{start:08x}",
                "exclusive_end_rva": f"0x{end:08x}",
                "bytes": end - start,
                "nodes": len(body),
                "sha256": hashlib.sha256(
                    b"".join(bytes(r.bytes) for r in body)
                ).hexdigest(),
                "points": [_point(r) for r in body],
            }
        )
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "bodies": bodies,
        "incoming_edge": {
            "instruction": _point(incoming),
            "target_entry_rva": f"0x{START:08x}",
        },
        "imports": imported,
        "matrix": {
            "pointers": pointers,
            "heap_words": heaps,
            "entry_stack_base": 0x30001000,
            "frame_alignments": [0, 1, 7, 15],
            "seeds": [0, U32],
            "iat_samples": {"heap_free": FREE_TARGET, "get_last_error": LAST_TARGET},
        },
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
        },
        "summary": {
            "cases": len(cases),
            "static_bytes": 68,
            "static_nodes": 24,
            "modeled_nodes": 24,
            "returned_cases": sum(c["returned"] for c in cases),
            "frontier_cases": sum(not c["returned"] for c in cases),
            "summarized_calls": sum(len(c["calls"]) for c in cases),
            "actual_native_executions": 0,
            "actual_import_calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "conditional_exact_free_wrapper_graph_with_independent_finite_protocol",
            "premises": [
                "HeapFree-site responses normally remove twelve argument bytes, GetLastError-site responses remove none, accessor and mapper responses are normal cdecl returns",
                "Opaque responses preserve EBP, EBX, ESI, EDI and all modeled memory including pushed arguments, while EAX is supplied and ECX, EDX and arithmetic flags are sampled",
                "Stable mapped frame, heap global and both IAT words at the finite nonwrapping stack base and alignments",
                "The error accessor returns a writable nonwrapping four-byte cell byte-disjoint from modeled code and every protected frame and global word",
            ],
            "relation": "Null input returns without changing entry EAX; nonzero input attempts the free-site summary; nonzero response returns, zero response obtains an error cell and last-error word, calls the mapper with that word, stores its result, restores saved state and returns",
            "flags": "Null path preserves six CMP flags, successful free preserves defined TEST flags, mapped-error return preserves the sampled mapper flags through memory stores and stack pops",
            "iat_policy": "Both indirect CALL instructions read explicit supplied stable IAT target words; PE import names establish static identities only",
            "frontier_policy": "Missing responses are rejected unless explicit frontier mode stops before the next call; no call or actual API runs",
            "not_claimed": [
                "Real free success, actual API or mapper effects, heap ownership or pointer validity",
                "Error-cell provenance or safe aliasing outside the explicit protected-storage premise",
                "Actual game execution, whole deallocation composition or accounting promotion",
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
            "sealed free protocol differs",
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
            "exact free protocol differs",
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
