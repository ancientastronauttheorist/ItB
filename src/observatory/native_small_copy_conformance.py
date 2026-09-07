"""Exact short scalar copy replay with a separate snapshot and ordered-access oracle."""

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

ANALYSIS_KIND = "pe_native_small_copy_conformance"
SEALED_SHA256 = "59f627925ad50c45ea6add7528137189dc39932582089cce6e381dcb90d485b9"
START = 0x36E580
RANGES = (
    (0x36E580, 0x36E5A9),
    (0x36E834, 0x36E843),
    (0x36E994, 0x36E9CB),
    (0x36EA7B, 0x36EAB7),
)
PAYLOAD, STACK, RETURN = 0x01000000, 0x02000000, 0x04000000
MASK = 0xFFFFFFFF
STACK_TEMPLATE = bytes(((i * 43) ^ (i >> 6) ^ 0xC7) & 255 for i in range(0x4000))
PAYLOAD_TEMPLATE = bytes(((i * 29) ^ (i >> 2) ^ 0xB3) & 255 for i in range(0x1000))


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    return [
        dict(
            length=n,
            source_offset=0x100 + source_alignment,
            destination_offset=0x100 + source_alignment + delta,
            alignment=frame_alignment,
            df=df,
        )
        for n in range(32)
        for source_alignment in range(4)
        for delta in (-40, -3, -1, 0, 1, 3, 40)
        for frame_alignment in range(16)
        for df in (0, 1)
    ]


def oracle(vector, payload=PAYLOAD_TEMPLATE):
    n, source, destination = (
        vector[k] for k in ("length", "source_offset", "destination_offset")
    )
    _require(type(n) is int and 0 <= n < 32, "invalid short length")
    _require(
        type(source) is int
        and type(destination) is int
        and 0 <= source <= len(payload) - n
        and 0 <= destination <= len(payload) - n,
        "invalid mapped payload offsets",
    )
    _require(
        type(vector["alignment"]) is int and 0 <= vector["alignment"] < 16,
        "invalid frame alignment",
    )
    _require(
        type(vector["df"]) is int and vector["df"] in (0, 1), "invalid direction flag"
    )
    backward = source < destination and destination - source < n
    result = bytearray(payload)
    source_snapshot = bytes(payload[source : source + n])
    result[destination : destination + n] = source_snapshot
    edx = n
    if not backward and n >= 4:
        last = 4 * (n // 4 - 1)
        edx = int.from_bytes(source_snapshot[last : last + 4], "little")
    chunks = []
    if backward:
        position = n
        while position >= 4:
            position -= 4
            chunks.append((position, 4))
        while position:
            position -= 1
            chunks.append((position, 1))
    else:
        position = 0
        while position + 4 <= n:
            chunks.append((position, 4))
            position += 4
        while position < n:
            chunks.append((position, 1))
            position += 1
    return dict(
        direction="backward" if backward else "forward",
        payload=bytes(result),
        source_snapshot=source_snapshot,
        edx=edx,
        chunks=chunks,
        flags=0x44,
        flag_mask=0x8C5 if n % 4 == 0 else 0x8D5,
    )


def _run_case(codes, points, vector, *, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    expected = oracle(vector)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    code_pages = {BASE + (start & ~0xFFF) for start, end in RANGES}
    for page in code_pages:
        machine.mem_map(page, 0x1000)
        machine.mem_write(page, b"\xcc" * 0x1000)
    for start, end in RANGES:
        machine.mem_write(BASE + start, codes[start])
    machine.mem_map(PAYLOAD, 0x1000)
    machine.mem_write(PAYLOAD, PAYLOAD_TEMPLATE)
    machine.mem_map(STACK, 0x4000)
    machine.mem_map(RETURN, 0x1000)
    machine.mem_write(RETURN, b"\xcc")
    entry = STACK + 0x2000 + vector["alignment"]
    source, destination = (
        PAYLOAD + vector["source_offset"],
        PAYLOAD + vector["destination_offset"],
    )
    original_stack = bytearray(STACK_TEMPLATE)
    for address, value in (
        (entry, RETURN),
        (entry + 4, destination),
        (entry + 8, source),
        (entry + 12, vector["length"]),
    ):
        original_stack[address - STACK : address - STACK + 4] = value.to_bytes(
            4, "little"
        )
    machine.mem_write(STACK, bytes(original_stack))
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
    for name, value in initial.items():
        machine.reg_write(ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 2 | (vector["df"] << 10))
    allowed = {int(p["rva"], 16) for p in points}
    visited, events = [], []

    def on_code(m, address, size, user):
        pc = address - BASE
        _require(pc in allowed, "copy escaped exact scalar ranges")
        if negative == "direction" and pc == 0x36E59A:
            m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) & ~1)
        if negative == "return" and pc in (0x36E9CA, 0x36EAB6):
            m.reg_write(x.UC_X86_REG_EAX, destination + 1)
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, size, value, user):
        write = access == uc.UC_MEM_WRITE
        _require(size in (1, 4), "unexpected scalar access width")
        if write:
            _require(
                address in (entry - 4, entry - 8)
                and size == 4
                or destination <= address
                and address + size <= destination + vector["length"],
                "unexpected scalar write",
            )
        else:
            _require(
                address
                in (entry, entry + 4, entry + 8, entry + 12, entry - 4, entry - 8)
                and size == 4
                or source <= address
                and address + size <= source + vector["length"],
                "unexpected scalar read, feature or table access",
            )
        events.append(
            dict(
                access="write" if write else "read",
                address=address,
                width=size,
                value=(
                    value & ((1 << (8 * size)) - 1)
                    if write
                    else int.from_bytes(m.mem_read(address, size), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    machine.emu_start(BASE + START, RETURN, count=250)
    _require(machine.reg_read(x.UC_X86_REG_EIP) == RETURN, "scalar copy did not return")
    actual = {name: machine.reg_read(reg) for name, reg in ids.items()}
    wanted = dict(initial, eax=destination, ecx=0, edx=expected["edx"], esp=entry + 4)
    _require(actual == wanted, "scalar register oracle differs")
    eflags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        eflags & expected["flag_mask"] == expected["flags"]
        and (eflags >> 10) & 1 == vector["df"],
        "scalar defined flags or DF differ",
    )
    _require(
        bytes(machine.mem_read(PAYLOAD, 0x1000)) == expected["payload"],
        "independent snapshot payload differs",
    )
    wanted_stack = bytearray(original_stack)
    wanted_events = []

    def write(address, width, value):
        if STACK <= address < STACK + 0x4000:
            wanted_stack[address - STACK : address - STACK + width] = value.to_bytes(
                width, "little"
            )
        wanted_events.append(
            dict(access="write", address=address, width=width, value=value)
        )

    def read(address, width, value):
        wanted_events.append(
            dict(access="read", address=address, width=width, value=value)
        )

    write(entry - 4, 4, initial["edi"])
    write(entry - 8, 4, initial["esi"])
    read(entry + 8, 4, source)
    read(entry + 12, 4, vector["length"])
    read(entry + 4, 4, destination)
    for offset, width in expected["chunks"]:
        value = int.from_bytes(
            expected["source_snapshot"][offset : offset + width], "little"
        )
        read(source + offset, width, value)
        write(destination + offset, width, value)
    read(entry + 4, 4, destination)
    read(entry - 8, 4, initial["esi"])
    read(entry - 4, 4, initial["edi"])
    read(entry, 4, RETURN)
    _require(events == wanted_events, "ordered scalar accessor oracle differs")
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == bytes(wanted_stack),
        "full scalar stack differs",
    )
    return dict(
        vector=vector,
        direction=expected["direction"],
        visited=visited,
        registers=actual,
        flags=eflags & expected["flag_mask"],
        df=(eflags >> 10) & 1,
        events_sha256=_canonical_sha256(events),
        payload_sha256=hashlib.sha256(expected["payload"]).hexdigest(),
        stack_sha256=hashlib.sha256(wanted_stack).hexdigest(),
    )


def _build_unsealed(executable, semantics):
    from src.observatory import native_small_copy_semantics as sem

    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "small copy semantics differs",
    )
    data, image, digest = _load_executable(executable)
    _require(
        capstone.__version__ == "5.0.7"
        and digest == EXE_SHA256
        and image.image_base == BASE,
        "exact build differs",
    )
    all_chunks = []
    all_nodes = 0
    for witness in semantics["body"]["ranges"]:
        start = int(witness["start_rva"], 16)
        size = witness["bytes"]
        offset = image.rva_to_file_offset(start)
        chunk = data[offset : offset + size]
        all_chunks.append(chunk)
        points = [
            _point(row)
            for row in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
                chunk, BASE + start
            )
        ]
        _require(
            points == witness["points"]
            and hashlib.sha256(chunk).hexdigest() == witness["sha256"],
            "full discontiguous witness differs",
        )
        all_nodes += len(points)
    _require(
        all_nodes == 404
        and sum(len(c) for c in all_chunks) == 1330
        and hashlib.sha256(b"".join(all_chunks)).hexdigest()
        == semantics["body"]["sha256"],
        "full copy body digest differs",
    )
    codes = {}
    points = []
    for start, end in RANGES:
        offset = image.rva_to_file_offset(start)
        codes[start] = data[offset : offset + end - start]
        decoded = [
            _point(row)
            for row in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
                codes[start], BASE + start
            )
        ]
        witness = next(
            w for w in semantics["scalar_ranges"] if int(w["start_rva"], 16) == start
        )
        _require(decoded == witness["points"], "exact scalar range differs")
        points.extend(decoded)
    observations = [_run_case(codes, points, vector) for vector in vectors()]
    controls = []
    for negative, message, vector in (
        (
            "direction",
            "snapshot payload",
            dict(
                length=3,
                source_offset=0x100,
                destination_offset=0x101,
                alignment=0,
                df=1,
            ),
        ),
        (
            "return",
            "register oracle",
            dict(
                length=0,
                source_offset=0x100,
                destination_offset=0x101,
                alignment=0,
                df=0,
            ),
        ),
    ):
        try:
            _run_case(codes, points, vector, negative=negative)
        except ConformanceError as exc:
            _require(
                message in str(exc),
                "scalar negative control failed for unrelated reason",
            )
            controls.append(dict(name=negative, rejected=True))
        else:
            raise ConformanceError("scalar negative control accepted")
    visited = sorted(
        {p for observation in observations for p in observation["visited"]}
    )
    _require(
        visited == semantics["model_evidence"]["instruction_union_rvas"]
        and len(visited) == 65,
        "scalar replay coverage differs",
    )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=semantics["build_identity"],
        source_semantics_sha256=sem.SEALED_SHA256,
        scalar_ranges=semantics["scalar_ranges"],
        full_body_sha256=semantics["body"]["sha256"],
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
            executed_instruction_sites=65,
            executed_bytes=171,
            forward_cases=sum(o["direction"] == "forward" for o in observations),
            backward_cases=sum(o["direction"] == "backward" for o in observations),
            executed_calls=0,
            feature_or_table_reads=0,
            negative_controls=2,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact short scalar paths match independent snapshot and ordered chunk oracles",
            matrix="All lengths zero through thirty-one, four source word alignments, seven destination offsets, sixteen frame alignments and both direction flags",
            premises=[
                "Nonwrapping mapped source and destination intervals within one writable payload page; overlapping ranges are allowed",
                "Protected stack and exact scalar code are disjoint from payload storage",
            ],
            memory_policy="Only four scalar code ranges are loaded; every byte or word access is checked, full payload and stack pages are compared, and no feature global or jump table is read",
            flags="EAX and all general registers are checked; AF is omitted only for zero byte remainder, and DF must retain each supplied input value",
            not_claimed=[
                "Any long-copy, REP, SIMD or feature-dispatch path",
                "Wrapping or unmapped ranges, frame aliases or complete copy-library equivalence",
                "Actual game execution or accounting promotion",
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
    from src.observatory import native_small_copy_semantics as sem

    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "sealed scalar replay differs",
    )
    _require(
        evidence["source_semantics_sha256"] == sem.SEALED_SHA256
        and evidence["vectors"] == vectors(),
        "scalar replay source differs",
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
        "exact scalar replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
