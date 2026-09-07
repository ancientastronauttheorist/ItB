"""Exact bounded feature-zero scalar copy replay with a separate snapshot and ordered-access oracle."""

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

ANALYSIS_KIND = "pe_native_scalar_copy_conformance"
SEALED_SHA256 = "60ddfcb642d675f73c4b8991270400802f08b6d8f78faa9da55f80279d6171a9"
START = 0x36E580
RANGES = (
    (3597696, 3597737),
    (3597737, 3597774),
    (3597783, 3597822),
    (3598247, 3598300),
    (3598324, 3598331),
    (3598332, 3598343),
    (3598344, 3598361),
    (3598364, 3598387),
    (3598388, 3598403),
    (3598403, 3598479),
    (3598496, 3598503),
    (3598504, 3598517),
    (3598520, 3598539),
    (3598540, 3598565),
    (3598740, 3598795),
    (3598971, 3599031),
)
TABLES = {
    3598308: [3598324, 3598332, 3598344, 3598364],
    3598480: [3598496, 3598504, 3598520, 3598540],
}
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
            source_offset=0x810 + a,
            destination_offset=0x810 + a + delta,
            alignment=frame,
            df=0,
        )
        for n in (32, 33, 34, 35, 63, 64, 65, 127, 128, 129, 511, 512, 513, 2047, 2048)
        for a in range(4)
        for delta in (-2052, -17, -3, -1, 0, 1, 3, 17, 2052)
        for frame in (0, 7, 15)
    ]


def oracle(vector, payload=PAYLOAD_TEMPLATE):
    n, source, destination = (
        vector[k] for k in ("length", "source_offset", "destination_offset")
    )
    _require(type(n) is int and 32 <= n <= 2048, "invalid short length")
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
    _require(type(vector["df"]) is int and vector["df"] == 0, "invalid direction flag")
    backward = source < destination and destination - source < n
    result = bytearray(payload)
    source_snapshot = bytes(payload[source : source + n])
    result[destination : destination + n] = source_snapshot
    # Derive the alignment schedule independently from the native graph model.
    position = n if backward else 0
    prefix = []
    if backward:
        while (destination + position) % 4:
            position -= 1
            prefix.append((position, 1))
        remaining = position
    else:
        while (destination + position) % 4:
            prefix.append((position, 1))
            position += 1
        remaining = n - position
    h = n - remaining
    words = []
    if backward:
        while position >= 4:
            position -= 4
            words.append((position, 4))
    else:
        while position + 4 <= n:
            words.append((position, 4))
            position += 4
    tail = []
    if backward:
        while position:
            position -= 1
            tail.append((position, 1))
    else:
        while position < n:
            tail.append((position, 1))
            position += 1
    r = remaining % 4
    edx = r
    flags = 0
    flag_mask = 0x8C5
    if remaining < 32:
        flags = 0x44
        flag_mask = 0x8C5 if r == 0 else 0x8D5
        edx = (
            0
            if backward
            else int.from_bytes(
                source_snapshot[words[-1][0] : words[-1][0] + 4], "little"
            )
        )
    elif backward:
        left = PAYLOAD + destination + remaining
        subresult = left - 4
        flags = (
            int(left < 4)
            | (int((subresult & 255).bit_count() % 2 == 0) << 2)
            | (((left ^ 4 ^ subresult) & 16))
            | (int(subresult == 0) << 6)
            | ((subresult >> 31) << 7)
            | (((left ^ 4) & (left ^ subresult) & 0x80000000) >> 20)
        )
        flag_mask = 0x8D5
    else:
        flags = (int(r.bit_count() % 2 == 0) << 2) | (int(r == 0) << 6)
    feature_reads = (
        [0x893F30]
        if backward or n < 128
        else [0x8B6E48]
        + ([0x893F30] if (source ^ destination) & 15 == 0 else [])
        + [0x8B6E48]
    )
    return dict(
        direction="backward" if backward else "forward",
        payload=bytes(result),
        source_snapshot=source_snapshot,
        edx=edx,
        chunks=prefix + words + ([(-1, 0)] if remaining >= 32 else []) + tail,
        flags=flags,
        flag_mask=flag_mask,
        feature_reads=feature_reads,
        remainder=r,
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
    for page in (0x893000, 0x8B6000):
        machine.mem_map(page, 0x1000)
    for table, targets in TABLES.items():
        machine.mem_write(
            BASE + table,
            b"".join((BASE + target).to_bytes(4, "little") for target in targets),
        )
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
    machine.reg_write(x.UC_X86_REG_EFLAGS, 2 | (vector["df"] << 10))
    allowed = {int(p["rva"], 16) for p in points}
    visited, events = [], []

    def on_code(m, address, size, user):
        pc = address - BASE
        _require(pc in allowed, "copy escaped exact scalar ranges")
        if negative == "direction" and pc == 0x36E59A:
            m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) & ~1)
        if (
            negative == "return"
            and size == 1
            and bytes(m.mem_read(address, 1)) == b"\xc3"
        ):
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
                and address + size <= source + vector["length"]
                or size == 4
                and (
                    address in (0x893F30, 0x8B6E48)
                    or any(
                        BASE + table <= address < BASE + table + 16
                        and (address - BASE - table) % 4 == 0
                        for table in TABLES
                    )
                ),
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
    machine.emu_start(BASE + START, RETURN, count=2000)
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
    for address in expected["feature_reads"]:
        read(address, 4, 0)
    for offset, width in expected["chunks"]:
        if width == 0:
            table = 0x36E890 if expected["direction"] == "backward" else 0x36E7E4
            r = expected["remainder"]
            read(BASE + table + 4 * r, 4, BASE + TABLES[table][r])
            continue
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
    _require(
        all(bytes(machine.mem_read(at, 4)) == bytes(4) for at in (0x893F30, 0x8B6E48)),
        "feature word changed",
    )
    _require(
        all(
            bytes(machine.mem_read(BASE + table, 16))
            == b"".join((BASE + target).to_bytes(4, "little") for target in targets)
            for table, targets in TABLES.items()
        ),
        "tail table changed",
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
    from src.observatory import native_scalar_copy_semantics as sem

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
    for table, targets in TABLES.items():
        offset = image.rva_to_file_offset(table)
        _require(
            data[offset : offset + 16]
            == b"".join((BASE + target).to_bytes(4, "little") for target in targets),
            "exact tail table differs",
        )
    observations = [_run_case(codes, points, vector) for vector in vectors()]
    controls = []
    for negative, message, vector in (
        (
            "direction",
            "register oracle",
            dict(
                length=128,
                source_offset=0x100,
                destination_offset=0x101,
                alignment=0,
                df=0,
            ),
        ),
        (
            "return",
            "register oracle",
            dict(
                length=128,
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
        and len(visited) == 176,
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
            executed_instruction_sites=176,
            executed_bytes=498,
            forward_cases=sum(o["direction"] == "forward" for o in observations),
            backward_cases=sum(o["direction"] == "backward" for o in observations),
            executed_calls=0,
            feature_and_table_reads_checked=True,
            negative_controls=2,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact bounded feature-zero scalar and REP paths match independent snapshot and ordered access oracles",
            premises=[
                "Length is in the explicit 32 through 2048 matrix with nonwrapping mapped payload intervals",
                "Both named feature words are zero and entry DF is zero",
                "Payload, protected stack, exact code, tables and feature storage are disjoint",
            ],
            memory_policy="Only admitted code ranges and exact tail tables are loaded, all accesses checked, full payload and stack plus feature words and tables compared",
            not_claimed=[
                "Other feature values, SIMD, REP MOVSB or full library equivalence",
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
    from src.observatory import native_scalar_copy_semantics as sem

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
