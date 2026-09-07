"""Exact bounded x86 deallocation guard replay against an independent oracle."""

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

ANALYSIS_KIND = "pe_native_vector_deallocation_conformance"
SEALED_SHA256 = "d54d38e2d758d2166f850346b3850cb608cda13aabb317a688edae513499954a"
START, END, DIVISION, FREE_CALL, FAILURE = 0x7800, 0x785B, 0x780B, 0x7851, 0x379F02
MASK, STACK = 0xFFFFFFFF, 0x02000000


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def _u32(value):
    _require(type(value) is int and 0 <= value <= MASK, "invalid unsigned input")


def _sub_flags(left, right):
    difference = (left - right) & MASK
    signed = lambda value: value if value < 2**31 else value - 2**32
    overflow = not (-(2**31) <= signed(left) - signed(right) < 2**31)
    return (
        int(left < right)
        | int((difference & 255).bit_count() % 2 == 0) << 2
        | int((left & 15) < (right & 15)) << 4
        | int(difference == 0) << 6
        | (difference >> 31) << 7
        | int(overflow) << 11
    )


def oracle(pointer, count, stride, metadata=None):
    for value in (pointer, count, stride):
        _u32(value)
    if metadata is not None:
        _u32(metadata)
    result = dict(
        outcome="division_frontier",
        stop=DIVISION,
        eax=MASK,
        ecx=count,
        edx=0,
        flags=0x44,
        flag_mask=0x8C5,
        stride_reads=0,
        pointer_read=False,
        metadata_read=False,
        free_argument=None,
        stack_delta=-4,
    )
    if stride == 0:
        return result
    quotient, remainder = MASK // stride, MASK % stride
    result.update(
        outcome="count_overflow",
        stop=FAILURE,
        eax=quotient,
        edx=remainder,
        flags=_sub_flags(count, quotient),
        flag_mask=0x8D5,
        stride_reads=1,
    )
    total = count * stride
    if total > MASK:
        return result
    result.update(stride_reads=2, pointer_read=True)
    if total < 4096:
        result.update(
            outcome="small_free",
            stop=FREE_CALL,
            ecx=pointer,
            flags=_sub_flags(total, 4096),
            free_argument=pointer,
            stack_delta=-8,
        )
        return result
    result.update(
        outcome="misaligned",
        eax=pointer,
        ecx=total,
        flags=int(((pointer & 31).bit_count() % 2) == 0) << 2
        | int((pointer & 31) == 0) << 6,
        flag_mask=0x8C5,
    )
    if pointer & 31:
        return result
    _require(metadata is not None, "aligned large pointer needs metadata")
    result.update(
        outcome="metadata_not_below",
        ecx=metadata,
        metadata_read=True,
        flags=_sub_flags(metadata, pointer),
        flag_mask=0x8D5,
    )
    if metadata >= pointer:
        return result
    distance = pointer - metadata
    result.update(outcome="short_distance", eax=distance, flags=_sub_flags(distance, 4))
    if distance < 4:
        return result
    result.update(outcome="long_distance", flags=_sub_flags(distance, 35))
    if distance > 35:
        return result
    result.update(
        outcome="large_free", stop=FREE_CALL, free_argument=metadata, stack_delta=-8
    )
    return result


def vectors():
    cases = {(0x10000040, 0, 0, None), (0x10000040, 512, 0, None)}
    for stride in (1, 2, 3, 7, 8, 16, 4096, 0x80000000, MASK):
        counts = {0, 1, 4095 // stride, (4096 + stride - 1) // stride, MASK // stride}
        if MASK // stride < MASK:
            counts.add(MASK // stride + 1)
        for count in counts:
            cases.add((0x10000040, count, stride, 0x10000020))
    for offset in range(32):
        cases.add((0x10000040 + offset, 512, 8, 0x10000020))
    for pointer in (0, 0x10000040, 0x80000000, 0xFFFFFFE0):
        for delta in (0, 1, 3, 4, 31, 32, 35, 36, MASK):
            cases.add((pointer, 512, 8, (pointer - delta) & MASK))
    # Independently reconstruct all allocation alignments using ceiling division.
    for offset in range(32):
        raw = 0x10010000 + offset
        aligned = 32 * ((raw + 4 + 31) // 32)
        for count in (512, 1024):
            cases.add((aligned, count, 8, raw))
    ordered = sorted(
        cases, key=lambda row: (*row[:3], -1 if row[3] is None else row[3])
    )
    return [
        dict(pointer=p, count=n, stride=s, metadata=m, alignment=a)
        for p, n, s, m in ordered
        for a in range(16)
    ]


def _run_case(code, points, vector, *, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    p, n, s, m = (vector[k] for k in ("pointer", "count", "stride", "metadata"))
    expected = oracle(p, n, s, m)
    _require(
        type(vector["alignment"]) is int and 0 <= vector["alignment"] < 16,
        "invalid stack alignment",
    )
    entry = STACK + 0x2000 + vector["alignment"]
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    machine.mem_map(BASE + (START & ~0xFFF), 0x1000)
    machine.mem_write(BASE + START, code)
    machine.mem_map(BASE + (FAILURE & ~0xFFF), 0x1000)
    # Excluded one-byte stop marker bounds Unicorn translation at the external target.
    # The code hook stops before this byte executes; it is not callee evidence.
    machine.mem_write(BASE + FAILURE, b"\xcc")
    machine.mem_map(STACK, 0x4000)
    stack = bytearray(((i * 37) ^ (i >> 4) ^ 0xE9) & 255 for i in range(0x4000))
    for displacement, value in ((4, p), (8, n), (12, s)):
        at = entry - STACK + displacement
        stack[at : at + 4] = value.to_bytes(4, "little")
    machine.mem_write(STACK, bytes(stack))
    metadata_address = (p - 4) & MASK
    metadata_page = None
    metadata_bytes = None
    if expected["metadata_read"]:
        metadata_page = metadata_address & ~0xFFF
        _require(
            metadata_page not in (BASE + (START & ~0xFFF), BASE + (FAILURE & ~0xFFF))
            and (metadata_page + 0x1000 <= STACK or metadata_page >= STACK + 0x4000),
            "metadata storage aliases replay code or stack",
        )
        machine.mem_map(metadata_page, 0x1000)
        metadata_bytes = bytearray(
            ((i * 13) ^ (i >> 3) ^ 0x49) & 255 for i in range(0x1000)
        )
        at = metadata_address - metadata_page
        metadata_bytes[at : at + 4] = m.to_bytes(4, "little")
        machine.mem_write(metadata_page, bytes(metadata_bytes))
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
    if negative == "pointer":
        machine.mem_write(entry + 4, (p ^ 8).to_bytes(4, "little"))
    elif negative == "metadata":
        _require(metadata_bytes is not None, "metadata control needs a read")
        machine.mem_write(metadata_address, (m ^ 1).to_bytes(4, "little"))
    else:
        _require(negative is None, "unknown negative control")
    allowed = {int(point["rva"], 16) for point in points}
    visited, events, stops = [], [], []

    def on_code(machine, address, size, user):
        pc = address - BASE
        if pc == FAILURE or pc == FREE_CALL or pc == DIVISION and s == 0:
            stops.append(pc)
            machine.emu_stop()
            return
        _require(pc in allowed and pc < FREE_CALL, "execution escaped bounded guard")
        visited.append(f"0x{pc:08x}")

    def on_memory(machine, access, address, size, value, user):
        write = access == uc.UC_MEM_WRITE
        _require(size == 4, "unexpected memory width")
        if write:
            _require(address in (entry - 4, entry - 8), "unexpected guard memory write")
        else:
            permitted = [entry + 8]
            if expected["stride_reads"]:
                permitted.append(entry + 12)
            if expected["pointer_read"]:
                permitted.append(entry + 4)
            if expected["metadata_read"]:
                permitted.append(metadata_address)
            _require(address in permitted, "unexpected guard memory read")
        events.append(
            dict(
                access="write" if write else "read",
                address=address,
                width=size,
                value=(
                    value & MASK
                    if write
                    else int.from_bytes(machine.mem_read(address, size), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    try:
        machine.emu_start(BASE + START, BASE + END, count=60)
    except uc.UcError as exc:
        raise ConformanceError(
            f"bounded replay fault at {machine.reg_read(x.UC_X86_REG_EIP):08x} for {vector}: {exc}"
        ) from exc
    _require(stops == [expected["stop"]], "deallocation oracle stop differs")
    wanted = dict(
        initial,
        ebp=entry - 4,
        esp=entry + expected["stack_delta"],
        eax=expected["eax"],
        ecx=expected["ecx"],
        edx=expected["edx"],
    )
    actual = {name: machine.reg_read(reg) for name, reg in ids.items()}
    _require(actual == wanted, "deallocation oracle registers differ")
    _require(
        machine.reg_read(x.UC_X86_REG_EFLAGS) & expected["flag_mask"]
        == expected["flags"],
        "deallocation defined arithmetic flags differ",
    )
    wanted_events = []
    wanted_stack = bytearray(stack)

    def write(address, value):
        at = address - STACK
        wanted_stack[at : at + 4] = value.to_bytes(4, "little")
        wanted_events.append(
            dict(access="write", address=address, width=4, value=value)
        )

    def read(address, value):
        wanted_events.append(dict(access="read", address=address, width=4, value=value))

    write(entry - 4, initial["ebp"])
    read(entry + 8, n)
    for _ in range(expected["stride_reads"]):
        read(entry + 12, s)
    if expected["pointer_read"]:
        read(entry + 4, p)
    if expected["metadata_read"]:
        read(metadata_address, m)
    if expected["free_argument"] is not None:
        write(entry - 8, expected["free_argument"])
    _require(events == wanted_events, "deallocation ordered memory oracle differs")
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == bytes(wanted_stack),
        "deallocation full stack differs",
    )
    if metadata_bytes is not None:
        _require(
            bytes(machine.mem_read(metadata_page, 0x1000)) == bytes(metadata_bytes),
            "metadata page changed",
        )
    return dict(
        vector=vector,
        visited=visited,
        stop_rva=f"0x{stops[0]:08x}",
        outcome=expected["outcome"],
        registers=actual,
        flags=machine.reg_read(x.UC_X86_REG_EFLAGS) & expected["flag_mask"],
        events_sha256=_canonical_sha256(events),
        stack_sha256=hashlib.sha256(wanted_stack).hexdigest(),
        metadata_sha256=(
            hashlib.sha256(metadata_bytes).hexdigest()
            if metadata_bytes is not None
            else None
        ),
    )


def _build_unsealed(executable, semantics):
    from src.observatory import native_vector_deallocation_semantics as sem

    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "deallocation semantics differs",
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
        _point(row)
        for row in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
            code, BASE + START
        )
    ]
    _require(
        points == semantics["body"]["points"]
        and hashlib.sha256(code).hexdigest() == semantics["body"]["sha256"],
        "exact source body differs",
    )
    observations = [_run_case(code, points, vector) for vector in vectors()]
    controls = []
    for name, vector in (
        (
            "pointer",
            dict(pointer=0x10000040, count=1, stride=8, metadata=None, alignment=0),
        ),
        (
            "metadata",
            dict(
                pointer=0x10000040,
                count=512,
                stride=8,
                metadata=0x10000020,
                alignment=0,
            ),
        ),
    ):
        try:
            _run_case(code, points, vector, negative=name)
        except ConformanceError as exc:
            _require(
                "oracle registers" in str(exc),
                "negative control failed for unrelated reason",
            )
            controls.append(dict(name="changed_" + name, rejected=True))
        else:
            raise ConformanceError("changed-input negative control accepted")
    visited = sorted(
        {point for observation in observations for point in observation["visited"]}
    )
    _require(
        visited == semantics["model_evidence"]["instruction_union_rvas"]
        and len(visited) == 25,
        "replay guard coverage differs",
    )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=semantics["build_identity"],
        source_semantics_sha256=sem.SEALED_SHA256,
        body=dict(semantics["body"]),
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
            executed_instruction_sites=25,
            division_frontiers=sum(
                o["outcome"] == "division_frontier" for o in observations
            ),
            free_frontiers=sum(
                o["outcome"] in ("small_free", "large_free") for o in observations
            ),
            guard_failures=sum(
                o["outcome"] not in ("division_frontier", "small_free", "large_free")
                for o in observations
            ),
            executed_calls=0,
            executed_division_faults=0,
            negative_controls=len(controls),
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact guarded x86 instructions match an independent product and metadata oracle",
            premises=[
                "Stable mapped pointer, count and stride arguments on a protected stack with sixteen sampled alignments",
                "Large aligned pointer metadata is mapped separately and disjoint from stack and code",
            ],
            stop_policy="Zero stride stops before DIV, valid guards stop before free CALL, failures stop at the external jump target before its first instruction",
            failure_mapping="An excluded synthetic stop byte bounds translation at the external failure target and never executes; no target implementation is loaded",
            flags="Six arithmetic flags are compared after CMP; undefined AF is omitted after TEST or XOR, including the eight-bit AL test",
            memory_policy="Every native word read and write is ordered against an independent oracle; complete stack and metadata pages are compared",
            not_claimed=[
                "Actual free, failure-callee execution, division faults or deallocation return tail",
                "Metadata provenance, ownership, allocation validity or full resize behavior",
                "API or game execution and whole-game accounting promotion",
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
    from src.observatory import native_vector_deallocation_semantics as sem

    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "sealed deallocation replay differs",
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
        "exact deallocation replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
