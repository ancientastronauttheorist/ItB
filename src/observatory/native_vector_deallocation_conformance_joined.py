"""One-state guard/free/tail replay with rebased sealed independent component oracles."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_vector_deallocation_conformance as guard_oracle
from src.observatory import native_heap_free_protocol_conformance as free_oracle
from src.observatory.native_lua_vector_allocation_return_conformance import _add_flags
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

ANALYSIS_KIND = "pe_native_vector_deallocation_conformance_joined"
SEALED_SHA256 = "8aba04f2be47f06284fbb3d00ebb7faa643613f99db3475fca54bd7f4cbc401a"
STACK, RETURN, ERROR_PAGE = (
    free_oracle.STACK,
    free_oracle.RETURN,
    free_oracle.ERROR_PAGE,
)
METADATA = 0x07000000
HEAP_GLOBAL, FREE_IAT, LAST_IAT = (
    free_oracle.HEAP_GLOBAL,
    free_oracle.FREE_IAT,
    free_oracle.LAST_IAT,
)
CALLS = free_oracle.CALLS
BODIES = {"guard": (0x7800, 0x785B), **free_oracle.BODIES}


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    p = METADATA + 0x100
    guards = [
        (0, 0, 8, None),
        (1, 1, 8, None),
        (p, 511, 8, None),
        (p, 512, 8, p - 32),
        (32, 512, 8, 0),
        (p + 1, 512, 8, None),
        (p, 512, 8, p),
        (p, 512, 8, p - 1),
        (p, 512, 8, p - 36),
        (p, 512, 8, p - 4),
        (p, 512, 8, p - 35),
        (1, 0x20000000, 8, None),
        (1, 0, 0, None),
        (1, 0, 7, None),
    ]
    result = []
    for pointer, count, stride, metadata in guards:
        g = guard_oracle.oracle(pointer, count, stride, metadata)
        patterns = [[]]
        if g["free_argument"]:
            patterns += [
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
            for last, mapped in ((0, 0), (5, 12), (0xFFFFFFFF, 0xFFFFFFFF)):
                patterns.append(
                    [
                        ("heap_free", 0),
                        ("error", ERROR_PAGE + 0x101),
                        ("get_last_error", last),
                        ("map_error", mapped),
                    ]
                )
        for pattern in patterns:
            for a in range(16):
                result.append(
                    dict(
                        pointer=pointer,
                        count=count,
                        stride=stride,
                        metadata=metadata,
                        alignment=a,
                        heap=0x12345678,
                        responses=[dict(kind=k, eax=v) for k, v in pattern],
                    )
                )
    return result


def _expected(vector, initial, original_stack, original_error):
    p, n, k, m = [vector[key] for key in ("pointer", "count", "stride", "metadata")]
    g = guard_oracle.oracle(p, n, k, m)
    s = initial["esp"]
    stack = bytearray(original_stack)
    events = []

    def event(access, address, value):
        events.append(dict(access=access, address=address, width=4, value=value))
        if access == "write":
            stack[address - STACK : address - STACK + 4] = value.to_bytes(4, "little")

    w = lambda a, v: event("write", a, v)
    r = lambda a, v: event("read", a, v)
    w(s - 4, initial["ebp"])
    r(s + 8, n)
    for _ in range(g["stride_reads"]):
        r(s + 12, k)
    if g["pointer_read"]:
        r(s + 4, p)
    if g["metadata_read"]:
        r((p - 4) & 0xFFFFFFFF, m)
    regs = dict(
        initial,
        ebp=s - 4,
        esp=s + g["stack_delta"],
        eax=g["eax"],
        ecx=g["ecx"],
        edx=g["edx"],
    )
    if g["free_argument"] is None:
        _require(not vector["responses"], "guard frontier has unused responses")
        return dict(
            registers=regs,
            flags=g["flags"],
            flag_mask=g["flag_mask"],
            events=events,
            stack=bytes(stack),
            error=original_error,
            stop=BASE + g["stop"],
            protocol=None,
        )
    w(s - 8, g["free_argument"])
    w(s - 12, BASE + 0x7856)
    inner_vector = dict(
        pointer=g["free_argument"], heap=vector["heap"], responses=vector["responses"]
    )
    inner = free_oracle._expected(
        inner_vector, dict(regs, esp=s - 12), stack, original_error
    )
    child_events = inner["events"]
    if inner["protocol"]["returned"]:
        _require(
            child_events[-1]
            == dict(access="read", address=s - 12, width=4, value=RETURN),
            "component continuation shape differs",
        )
        child_events[-1] = dict(
            access="read", address=s - 12, width=4, value=BASE + 0x7856
        )
    events += child_events
    regs = inner["registers"]
    if inner["protocol"]["returned"]:
        r(s - 4, initial["ebp"])
        r(s, RETURN)
        regs.update(ebp=initial["ebp"], esp=s + 4)
        flags, mask, stop = _add_flags(s - 8, 4), 0x8D5, RETURN
    else:
        flags, mask = inner["flags"], inner["flag_mask"]
        stop = BASE + CALLS[inner["protocol"]["next_kind"]][0]
    return dict(
        registers=regs,
        flags=flags,
        flag_mask=mask,
        events=events,
        stack=inner["stack"],
        error=inner["error"],
        stop=stop,
        protocol=inner["protocol"],
    )


def _run_case(codes, points, vector, negative=False):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    g = guard_oracle.oracle(
        vector["pointer"], vector["count"], vector["stride"], vector["metadata"]
    )
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    pages = {BASE + (a & ~0xFFF) for a, b in BODIES.values()}
    pages.update(target & ~0xFFF for site, target in CALLS.values())
    pages.update(
        (
            RETURN,
            ERROR_PAGE,
            HEAP_GLOBAL & ~0xFFF,
            FREE_IAT & ~0xFFF,
            (BASE + 0x379F02) & ~0xFFF,
        )
    )
    metadata_address = (
        (vector["pointer"] - 4) & 0xFFFFFFFF if g["metadata_read"] else None
    )
    if metadata_address is not None:
        pages.add(metadata_address & ~0xFFF)
    for page in sorted(pages):
        machine.mem_map(page, 0x1000)
    machine.mem_map(STACK, 0x4000)
    for name, (a, b) in BODIES.items():
        machine.mem_write(BASE + a, codes[name])
    for site, target in CALLS.values():
        machine.mem_write(target, b"\xcc")
    machine.mem_write(BASE + 0x379F02, b"\xcc")
    s = STACK + 0x2000 + vector["alignment"]
    stack = bytearray(((i * 43) ^ (i >> 6) ^ 0xC7) & 255 for i in range(0x4000))
    for address, value in (
        (s, RETURN),
        (s + 4, vector["pointer"]),
        (s + 8, vector["count"]),
        (s + 12, vector["stride"]),
    ):
        stack[address - STACK : address - STACK + 4] = value.to_bytes(4, "little")
    error = bytes(((i * 23) ^ (i >> 2) ^ 0x59) & 255 for i in range(0x1000))
    global_page = HEAP_GLOBAL & ~0xFFF
    iat_page = FREE_IAT & ~0xFFF
    global_bytes = bytearray(0x1000)
    global_bytes[HEAP_GLOBAL - global_page : HEAP_GLOBAL - global_page + 4] = vector[
        "heap"
    ].to_bytes(4, "little")
    iat = bytearray(0x1000)
    for address, role in ((FREE_IAT, "heap_free"), (LAST_IAT, "get_last_error")):
        iat[address - iat_page : address - iat_page + 4] = CALLS[role][1].to_bytes(
            4, "little"
        )
    metadata_bytes = None
    if metadata_address is not None:
        metadata_bytes = bytearray(((i * 17) ^ 0xD9) & 255 for i in range(0x1000))
        offset = metadata_address & 0xFFF
        metadata_bytes[offset : offset + 4] = vector["metadata"].to_bytes(4, "little")
        machine.mem_write(metadata_address & ~0xFFF, bytes(metadata_bytes))
    machine.mem_write(STACK, bytes(stack))
    machine.mem_write(ERROR_PAGE, error)
    machine.mem_write(global_page, bytes(global_bytes))
    machine.mem_write(iat_page, bytes(iat))
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
    initial["esp"] = s
    expected = _expected(vector, initial, stack, error)
    for r, v in initial.items():
        machine.reg_write(ids[r], v)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(p["rva"], 16) for rows in points.values() for p in rows}
    visited, events, summaries = [], [], []
    resume = None
    targets = {target: role for role, (site, target) in CALLS.items()}

    def on_code(m, address, size, user):
        nonlocal resume
        if address == expected["stop"]:
            m.emu_stop()
            return
        if address in targets:
            index = len(summaries)
            _require(index < len(vector["responses"]), "unexpected external call")
            response = vector["responses"][index]
            role = targets[address]
            _require(response["kind"] == role, "external order differs")
            sp = m.reg_read(x.UC_X86_REG_ESP)
            site = CALLS[role][0]
            continuation = (
                BASE + site + (6 if role in ("heap_free", "get_last_error") else 5)
            )
            args = (
                [vector["heap"], 0, g["free_argument"]]
                if role == "heap_free"
                else [expected["protocol"]["last_error"]] if role == "map_error" else []
            )
            _require(
                sp
                == s
                - {"heap_free": 32, "error": 24, "get_last_error": 24, "map_error": 28}[
                    role
                ],
                "composed external frame differs",
            )
            _require(
                [
                    int.from_bytes(m.mem_read(sp + 4 * i, 4), "little")
                    for i in range(len(args) + 1)
                ]
                == [continuation, *args],
                "composed arguments differ",
            )
            out = free_oracle._volatile(index + 1)
            m.reg_write(x.UC_X86_REG_EAX, response["eax"])
            m.reg_write(x.UC_X86_REG_ECX, out["ecx"])
            m.reg_write(x.UC_X86_REG_EDX, out["edx"])
            m.reg_write(x.UC_X86_REG_EFLAGS, out["flags"])
            m.reg_write(x.UC_X86_REG_ESP, sp + 4 + (12 if role == "heap_free" else 0))
            if negative and role == "heap_free":
                m.mem_write(s + 12, (vector["stride"] ^ 1).to_bytes(4, "little"))
            summaries.append(dict(kind=role, entry_esp=sp, continuation=continuation))
            resume = continuation
            m.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "execution escaped joined deallocation")
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, size, value, user):
        write = access == uc.UC_MEM_WRITE
        _require(size == 4, "nonword joined access")
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
    start = BASE + 0x7800
    for _ in range(5):
        resume = None
        machine.emu_start(start, RETURN, count=150)
        if resume is None:
            break
        start = resume
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == expected["stop"],
        "joined boundary differs",
    )
    _require(len(summaries) == len(vector["responses"]), "response count differs")
    actual = {r: machine.reg_read(i) for r, i in ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS) & expected["flag_mask"]
    _require(
        actual == expected["registers"]
        and flags == expected["flags"] & expected["flag_mask"],
        "joined register or flag oracle differs",
    )
    _require(events == expected["events"], "joined ordered event oracle differs")
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == expected["stack"]
        and bytes(machine.mem_read(ERROR_PAGE, 0x1000)) == expected["error"],
        "joined protected memory differs",
    )
    _require(
        bytes(machine.mem_read(global_page, 0x1000)) == bytes(global_bytes)
        and bytes(machine.mem_read(iat_page, 0x1000)) == bytes(iat),
        "joined global or IAT memory differs",
    )
    if metadata_bytes is not None:
        _require(
            bytes(machine.mem_read(metadata_address & ~0xFFF, 0x1000))
            == bytes(metadata_bytes),
            "joined metadata changed",
        )
    return dict(
        inputs=vector,
        registers=actual,
        flags=flags,
        flag_mask=expected["flag_mask"],
        stop=expected["stop"],
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        stack_sha256=hashlib.sha256(expected["stack"]).hexdigest(),
        error_sha256=hashlib.sha256(expected["error"]).hexdigest(),
        summaries=summaries,
    )


def _build_unsealed(executable, composition):
    from src.observatory import native_vector_deallocation_composition as comp

    _require(
        _canonical_sha256(composition) == comp.SEALED_SHA256, "composition seal differs"
    )
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256, "executable differs")
    codes, points = {}, {}
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    witnesses = {
        int(b["entry_rva"], 16): b
        for b in [composition["guard_body"], *composition["free_bodies"]]
    }
    for name, (a, b) in BODIES.items():
        offset = image.rva_to_file_offset(a)
        codes[name] = data[offset : offset + b - a]
        points[name] = [_point(r) for r in decoder.disasm(codes[name], BASE + a)]
        _require(
            points[name] == witnesses[a]["points"]
            and hashlib.sha256(codes[name]).hexdigest() == witnesses[a]["sha256"],
            "joined native witness differs",
        )
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({p for c in observations for p in c["trace_rvas"]})
    _require(
        union == sorted(p["rva"] for rows in points.values() for p in rows),
        "joined site coverage differs",
    )
    v = next(v for v in vectors() if v["responses"] == [dict(kind="heap_free", eax=1)])
    try:
        _run_case(codes, points, v, True)
    except ConformanceError as exc:
        _require(
            str(exc) == "joined protected memory differs",
            "negative control failed incidentally",
        )
    else:
        raise ConformanceError("ancestor mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=composition["build_identity"],
        source_composition_sha256=comp.SEALED_SHA256,
        oracle_sources=dict(
            guard=guard_oracle.SEALED_SHA256, free=free_oracle.SEALED_SHA256
        ),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        instruction_union_rvas=union,
        summary=dict(
            cases=len(observations),
            executed_instruction_sites=len(union),
            normal_returns=sum(c["stop"] == RETURN for c in observations),
            external_summaries=sum(len(c["summaries"]) for c in observations),
            opaque_instructions=0,
            negative_controls=1,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="One native state executes guard, free thunks, wrapper and guard return tail against rebased independent component oracles",
            oracle_join="The sealed free oracle is rebased at S-12; its caller-return event is explicitly replaced with the actual guard continuation; fresh tail equations then restore the outer caller",
            premises=[
                "External free, error-accessor, last-error and mapper responses preserve all modeled ancestor and metadata bytes with declared normal conventions",
                "Stable mapped metadata and separate error pages; synthetic numeric pointers need not be allocated",
            ],
            not_claimed=[
                "Actual API effects, provenance, fault execution, arbitrary external side effects or whole-program accounting promotion"
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
    from src.observatory import native_vector_deallocation_composition as comp

    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(composition, "composition")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(composition) == comp.SEALED_SHA256,
        "sealed joined replay differs",
    )
    _require(
        evidence["source_composition_sha256"] == comp.SEALED_SHA256
        and evidence["vectors"] == vectors(),
        "joined source relation differs",
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
