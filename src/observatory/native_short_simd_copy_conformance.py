"""Exact short forward SIMD copy replay with a separate snapshot and ordered-access oracle."""

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

ANALYSIS_KIND = "pe_native_short_simd_copy_conformance"
SEALED_SHA256 = "67e3ceefdb4b00bfab28653b34634f51a1ab5310fd27b2f2e4bdd75324de5865"
START = 0x36E580
RANGES = ((3597696, 3597759), (3598925, 3599031))
PAYLOAD, STACK, RETURN = 0x01000000, 0x02000000, 0x04000000
MASK = 0xFFFFFFFF
STACK_TEMPLATE = bytes(((i * 43) ^ (i >> 6) ^ 0xC7) & 255 for i in range(0x4000))
PAYLOAD_TEMPLATE = bytes(((i * 29) ^ (i >> 2) ^ 0xB3) & 255 for i in range(0x2000))


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    return [
        dict(
            length=n,
            source_offset=0x100 + a,
            destination_offset=0x100 + a + delta,
            alignment=frame,
            df=0,
            feature_word=word,
        )
        for n in (32, 33, 34, 35, 36, 47, 63, 64, 65, 95, 96, 97, 127)
        for a in range(16)
        for delta in (-128, -17, -3, -1, 0, 128)
        for frame in (0, 15)
        for word in (2, 0xFFFFFFFF)
    ]


def oracle(vector, payload=PAYLOAD_TEMPLATE):
    n, source, destination = (
        vector[k] for k in ("length", "source_offset", "destination_offset")
    )
    _require(type(n) is int and 32 <= n <= 127, "invalid short SIMD length")
    _require(
        type(source) is int
        and type(destination) is int
        and 0 <= source <= len(payload) - n
        and 0 <= destination <= len(payload) - n,
        "invalid payload interval",
    )
    _require(
        destination <= source or destination - source >= n,
        "backward overlapping SIMD interval",
    )
    _require(
        type(vector["alignment"]) is int and 0 <= vector["alignment"] < 16,
        "invalid frame alignment",
    )
    _require(type(vector["df"]) is int and vector["df"] == 0, "invalid direction flag")
    word = vector["feature_word"]
    _require(
        type(word) is int and 0 <= word <= MASK and word & 2,
        "feature bit premise differs",
    )
    snapshot = bytes(payload[source : source + n])
    result = bytearray(payload)
    result[destination : destination + n] = snapshot
    position = 0
    accesses = []
    while position + 32 <= n:
        accesses.extend(
            (kind, position + offset, 16)
            for kind, offset in (("read", 0), ("read", 16), ("write", 0), ("write", 16))
        )
        position += 32
    last = position - 32
    edx = 0
    while position + 4 <= n:
        accesses.extend((("read", position, 4), ("write", position, 4)))
        edx = int.from_bytes(snapshot[position : position + 4], "little")
        position += 4
    while position < n:
        accesses.extend((("read", position, 1), ("write", position, 1)))
        position += 1
    return dict(
        direction="forward",
        payload=bytes(result),
        source_snapshot=snapshot,
        edx=edx,
        accesses=accesses,
        xmm0=int.from_bytes(snapshot[last : last + 16], "little"),
        xmm1=int.from_bytes(snapshot[last + 16 : last + 32], "little"),
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
    machine.mem_map(0x893000, 0x1000)
    machine.mem_write(0x893F30, vector["feature_word"].to_bytes(4, "little"))
    machine.mem_map(PAYLOAD, 0x2000)
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
    xmm_ids = {f"xmm{i}": getattr(x, f"UC_X86_REG_XMM{i}") for i in range(8)}
    initial_xmm = {
        name: int.from_bytes(
            bytes((i * 29 + j * 31 + 7) & 255 for j in range(16)), "little"
        )
        for i, name in enumerate(xmm_ids)
    }
    for name, value in initial_xmm.items():
        machine.reg_write(xmm_ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 2 | (vector["df"] << 10))
    allowed = {int(p["rva"], 16) for p in points}
    visited, events = [], []

    def on_code(m, address, size, user):
        pc = address - BASE
        _require(pc in allowed, "copy escaped exact scalar ranges")
        if (
            negative == "byte"
            and pc == 0x36EA60
            and m.reg_read(x.UC_X86_REG_ESI) == source
        ):
            m.mem_write(source, bytes([m.mem_read(source, 1)[0] ^ 1]))
        if negative == "xmm" and pc == 0x36EAB6:
            m.reg_write(x.UC_X86_REG_XMM2, m.reg_read(x.UC_X86_REG_XMM2) ^ 1)
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, size, value, user):
        write = access == uc.UC_MEM_WRITE
        _require(size in (1, 4, 8, 16), "unexpected scalar access width")
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
                and address + size <= source + vector["length"]
                or size == 4
                and address == 0x893F30,
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
    machine.emu_start(BASE + START, RETURN, count=2200)
    _require(machine.reg_read(x.UC_X86_REG_EIP) == RETURN, "scalar copy did not return")
    actual = {name: machine.reg_read(reg) for name, reg in ids.items()}
    wanted = dict(initial, eax=destination, ecx=0, edx=expected["edx"], esp=entry + 4)
    _require(actual == wanted, "scalar register oracle differs")
    actual_xmm = {name: machine.reg_read(reg) for name, reg in xmm_ids.items()}
    wanted_xmm = dict(initial_xmm, xmm0=expected["xmm0"], xmm1=expected["xmm1"])
    _require(actual_xmm == wanted_xmm, "XMM register oracle differs")
    eflags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        eflags & expected["flag_mask"] == expected["flags"]
        and (eflags >> 10) & 1 == vector["df"],
        "scalar defined flags or DF differ",
    )
    _require(
        bytes(machine.mem_read(PAYLOAD, 0x2000)) == expected["payload"],
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
    read(0x893F30, 4, vector["feature_word"])
    for kind, offset, width in expected["accesses"]:
        # This pinned emulator reports each architectural 16-byte transfer as
        # two ordered 8-byte hooks. Preserve the architectural operation order.
        for part, size in ((0, 8), (8, 8)) if width == 16 else ((0, width),):
            at = (source if kind == "read" else destination) + offset + part
            value = int.from_bytes(
                expected["source_snapshot"][offset + part : offset + part + size],
                "little",
            )
            (read if kind == "read" else write)(at, size, value)
    read(entry + 4, 4, destination)
    read(entry - 8, 4, initial["esi"])
    read(entry - 4, 4, initial["edi"])
    read(entry, 4, RETURN)
    _require(events == wanted_events, "ordered scalar accessor oracle differs")
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == bytes(wanted_stack),
        "full scalar stack differs",
    )
    _require(
        bytes(machine.mem_read(0x893F30, 4))
        == vector["feature_word"].to_bytes(4, "little"),
        "feature word changed",
    )
    return dict(
        vector=vector,
        direction=expected["direction"],
        visited=visited,
        registers=actual,
        xmm=actual_xmm,
        flags=eflags & expected["flag_mask"],
        df=(eflags >> 10) & 1,
        events_sha256=_canonical_sha256(events),
        payload_sha256=hashlib.sha256(expected["payload"]).hexdigest(),
        stack_sha256=hashlib.sha256(wanted_stack).hexdigest(),
    )


def _build_unsealed(executable, semantics):
    from src.observatory import native_short_simd_copy_semantics as sem

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
            "byte",
            "snapshot payload",
            dict(
                length=64,
                source_offset=0x100,
                destination_offset=0x80,
                alignment=0,
                df=0,
                feature_word=2,
            ),
        ),
        (
            "xmm",
            "XMM register oracle",
            dict(
                length=64,
                source_offset=0x100,
                destination_offset=0x80,
                alignment=0,
                df=0,
                feature_word=2,
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
        and len(visited) == 59,
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
            executed_instruction_sites=59,
            executed_bytes=169,
            forward_cases=sum(o["direction"] == "forward" for o in observations),
            backward_cases=sum(o["direction"] == "backward" for o in observations),
            executed_calls=0,
            feature_reads_checked=True,
            negative_controls=2,
            accounting_promotions=0,
        ),
        scope=dict(
            instrumentation="Unicorn 2.1.4 emits two ordered 8 byte hooks for each architectural 16 byte MOVDQU transfer; the oracle expands only that transfer while preserving paired load before store ordering",
            claim="Exact short forward MOVDQU path matches independent snapshot, XMM and ordered access oracles",
            premises=[
                "Explicit lengths 32 through 127 with forward-safe mapped intervals",
                "DF is zero and stable feature word RVA 0x00493f30 has bit one set",
                "Protected frame, exact code, feature storage and payload are disjoint",
            ],
            memory_policy="All accesses stay inside exact requested payload intervals or declared frame and feature word; full payload and stack plus feature word compared",
            xmm_policy="All eight XMM registers checked; last original 32 byte chunk replaces XMM0 and XMM1 and all other XMM registers preserve",
            not_claimed=[
                "Backward overlapping copy, other feature paths, aligned SIMD or overread permissions",
                "Actual game execution or complete library equivalence",
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
    from src.observatory import native_short_simd_copy_semantics as sem

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
