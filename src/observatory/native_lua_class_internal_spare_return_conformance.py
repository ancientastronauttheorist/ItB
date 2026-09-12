"""Finite native class transfer, internal spare append, and normal caller return."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_lua_class_tree_conformance as prefix
from src.observatory import native_lua_class_vector_return_conformance as returned
from src.observatory import native_lua_class_vector_append_semantics as append
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _load_executable,
    _decode_body,
    _point,
    _source_identity,
    _canonical_bytes,
    _canonical_sha256,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "pe_native_lua_class_internal_spare_return_conformance"
SEALED_SHA256 = "a81cdc78469e20dda9413247141190d4ffe0b59229aa8123f231d7b4a1c20cbe"
SOURCE_PINS = {
    "program_facts": prefix.SOURCE_PINS["program_facts"],
    "prefix": (prefix.ANALYSIS_KIND, prefix.SEALED_SHA256),
    "append_semantics": (append.ANALYSIS_KIND, append.SEALED_SHA256),
    "class_return": (returned.ANALYSIS_KIND, returned.SEALED_SHA256),
}
START = prefix.START
RECEIVER, ARGUMENT, SOURCE_HEAD = prefix.RECEIVER, prefix.ARGUMENT, prefix.SOURCE_HEAD
construction = prefix.construction
ConformanceError, _require = prefix.ConformanceError, prefix._require
SPARE_RANGES = ((0x2EB1BB, 0x2EB1D6), (0x2EB1DF, 0x2EB1F7), (0x2EB216, 0x2EB22D))


def vectors():
    return [
        dict(v, old_size=size, argument_index=index, spare_records=1 + size % 2)
        for v in prefix.vectors()
        for size in (1, 3, 7)
        for index in sorted({0, size // 2, size - 1})
    ]


def _fixture(vector):
    size, index, spare = (
        vector[k] for k in ("old_size", "argument_index", "spare_records")
    )
    _require(
        type(size) is int
        and 1 <= size <= 7
        and type(index) is int
        and 0 <= index < size
        and type(spare) is int
        and 1 <= spare <= 8,
        "invalid internal spare vector bounds",
    )
    address = ARGUMENT - 8 * index
    fixture = prefix._fixture(vector)
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    # This vector owns complete records around ARGUMENT within existing source storage.
    # It remains disjoint from the source object, head, nodes, strings and tree outputs.
    _require(
        address >= ARGUMENT - 48 and address + 8 * (size + spare) <= ARGUMENT + 120,
        "internal vector storage escaped reserved records",
    )
    for offset, value in (
        (4, address),
        (8, address + 8 * size),
        (12, address + 8 * (size + spare)),
    ):
        for i, b in enumerate(value.to_bytes(4, "little")):
            a = RECEIVER + offset + i
            pages[a & ~0xFFF][a & 0xFFF] = b
    fixture.update(
        pages={p: bytes(v) for p, v in pages.items()},
        vector_begin=address,
        vector_end=address + 8 * size,
        vector_capacity=address + 8 * (size + spare),
    )
    return fixture


def _expected(vector, fixture):
    result = prefix._expected(vector, fixture)
    pages = {p: bytearray(v) for p, v in result["pages"].items()}
    events = list(result["events"])
    regs = dict(result["registers"])

    def read(a):
        value = int.from_bytes(
            bytes(pages[(a + i) & ~0xFFF][(a + i) & 0xFFF] for i in range(4)), "little"
        )
        events.append(dict(access="read", address=a, width=4, value=value))
        return value

    def write(a, value):
        events.append(dict(access="write", address=a, width=4, value=value))
        for i, b in enumerate(value.to_bytes(4, "little")):
            pages[(a + i) & ~0xFFF][(a + i) & 0xFFF] = b

    frame = fixture["stack"] - 4
    receiver = read(frame - 12)
    _require(
        receiver == RECEIVER and regs["edi"] == ARGUMENT,
        "internal append receiver differs",
    )
    end = read(receiver + 8)
    _require(ARGUMENT < end, "argument is not internal")
    begin = read(receiver + 4)
    _require(
        begin <= ARGUMENT and (ARGUMENT - begin) % 8 == 0,
        "argument is not a complete internal record",
    )
    index = (ARGUMENT - begin) // 8
    _require(index == vector["argument_index"], "internal record index differs")
    _require(
        end < read(receiver + 12) and end != 0, "spare nonzero vector end required"
    )
    _require(read(receiver + 8) == end, "vector end changed")
    current_begin = read(receiver + 4)
    _require(current_begin == begin, "vector begin changed without growth")
    first = read(current_begin + index * 8)
    write(end, first)
    second = read(current_begin + index * 8 + 4)
    write(end + 4, second)
    write(receiver + 8, read(receiver + 8) + 8)
    regs.update(eax=second, ecx=begin, edx=end, esi=receiver, edi=index)
    cookie = vector["cookie"]
    suffix = returned._expected(
        dict(
            frame=frame,
            cookie=cookie,
            current=cookie,
            relation=returned.return_spec(
                frame, cookie, cookie, return_address=fixture["return_address"]
            ),
            saved={r: fixture["registers"][r] for r in ("edi", "esi", "ebx", "ebp")},
            registers=regs,
            stack=bytes(pages[construction.STACK] + pages[construction.STACK + 0x1000]),
            stack_base=construction.STACK,
        )
    )
    events.extend(suffix["events"])
    for i, p in enumerate((construction.STACK, construction.STACK + 0x1000)):
        pages[p] = bytearray(suffix["stack"][4096 * i : 4096 * (i + 1)])
    result.update(
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        registers=suffix["registers"],
        flags=suffix["flags"],
        endpoint=fixture["return_address"],
    )
    _require(
        result["pages"] == _model_pages(fixture, result),
        "independent class append differs",
    )
    return result


def _model_pages(fixture, expected):
    pages = {p: bytearray(v) for p, v in prefix._model_pages(fixture, expected).items()}
    # The vector model appends the unchanged two-word argument as a record.
    record = bytes(
        fixture["pages"][(ARGUMENT + i) & ~0xFFF][(ARGUMENT + i) & 0xFFF]
        for i in range(8)
    )
    for i, b in enumerate(record):
        a = fixture["vector_end"] + i
        pages[a & ~0xFFF][a & 0xFFF] = b
    for i, b in enumerate((fixture["vector_end"] + 8).to_bytes(4, "little")):
        a = RECEIVER + 8 + i
        pages[a & ~0xFFF][a & 0xFFF] = b
    return {p: bytes(v) for p, v in pages.items()}


def _run_case(codes, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector)
    expected = _expected(vector, fixture)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, payload in fixture["pages"].items():
        machine.mem_map(page, 0x1000)
        machine.mem_write(page, payload)
    code_pages = {
        (BASE + a + i) & ~0xFFF
        for a, payload in codes.items()
        for i in range(len(payload))
    }
    for page in sorted(code_pages):
        _require(page not in fixture["pages"], "class code overlaps data")
        machine.mem_map(page, 0x1000)
        machine.mem_write(page, b"\xcc" * 0x1000)
    for address, payload in codes.items():
        machine.mem_write(BASE + address, payload)
    endpoint_page = expected["endpoint"] & ~0xFFF
    _require(
        endpoint_page not in code_pages and endpoint_page not in fixture["pages"],
        "return endpoint overlaps mapping",
    )
    machine.mem_map(endpoint_page, 0x1000)
    machine.mem_write(endpoint_page, b"\xcc" * 0x1000)
    machine.mem_map(construction.IMPORT, 0x1000)
    machine.mem_write(construction.IMPORT, b"\xcc")
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in fixture["registers"]}
    for register, value in fixture["registers"].items():
        machine.reg_write(ids[register], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(p["rva"], 16) for p in points}
    events, visited, allocations = [], [], []
    frame = fixture["stack"] - 4
    resume = None

    def on_code(m, address, size, user):
        nonlocal resume
        if address == construction.IMPORT:
            sp = m.reg_read(x.UC_X86_REG_ESP)
            words = [
                int.from_bytes(m.mem_read(sp + i * 4, 4), "little") for i in range(4)
            ]
            _require(
                len(allocations) < len(expected["heap_nodes"])
                and sp == frame - 140
                and words == [BASE + 0x389463, construction.HEAP, 0, 24],
                "class heap handoff differs",
            )
            node = expected["heap_nodes"][len(allocations)]
            for register, value in (
                (x.UC_X86_REG_EAX, node),
                (x.UC_X86_REG_ECX, 0xA0000001),
                (x.UC_X86_REG_EDX, 0xB0000001),
                (x.UC_X86_REG_EFLAGS, 0x246),
                (x.UC_X86_REG_ESP, sp + 16),
            ):
                m.reg_write(register, value)
            allocations.append(
                dict(node=node, entry_esp=sp, request=24, continuation=words[0])
            )
            resume = words[0]
            m.emu_stop()
            return
        if address == BASE + 0x3574D5 and negative == "cookie":
            m.emu_stop()
            return
        if address == BASE + 0x2EB222 and negative == "cookie":
            m.mem_write(returned.COOKIE, (vector["cookie"] ^ 1).to_bytes(4, "little"))
        if address == expected["endpoint"]:
            if negative == "iterator":
                m.mem_write(frame - 8, (SOURCE_HEAD ^ 1).to_bytes(4, "little"))
            if negative == "payload":
                last = expected["insertions"][-1]
                m.mem_write(
                    last["destination_address"] + 20,
                    (last["payload"] ^ 1).to_bytes(4, "little"),
                )
            if negative == "vector":
                at = fixture["vector_end"]
                m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))
            m.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "class prefix escaped selected bodies")
        visited.append(f"0x{pc:08x}")
        if pc == START and negative in ("ancestor", "source"):
            at = fixture["stack"] + 8 if negative == "ancestor" else SOURCE_HEAD + 14
            m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))

    def on_memory(m, access, address, width, value, user):
        _require(width in (1, 2, 4), "unexpected class memory width")
        writing = access == uc.UC_MEM_WRITE
        events.append(
            dict(
                access="write" if writing else "read",
                address=address,
                width=width,
                value=(
                    value
                    if writing
                    else int.from_bytes(m.mem_read(address, width), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    next_pc = BASE + START
    for _ in range(len(expected["heap_nodes"]) + 1):
        resume = None
        machine.emu_start(next_pc, 0, count=50000)
        if resume is None:
            break
        next_pc = resume
    if negative == "cookie":
        _require(
            machine.reg_read(x.UC_X86_REG_EIP) == BASE + 0x3574D5
            and machine.reg_read(x.UC_X86_REG_ESP) == frame - 24,
            "class cookie failure frontier differs",
        )
        _require(
            events
            == expected["events"][: -3 - 1]
            + [
                dict(
                    access="read",
                    address=returned.COOKIE,
                    width=4,
                    value=vector["cookie"] ^ 1,
                )
            ],
            "class cookie prefix events differ",
        )
        failure_regs = dict(expected["registers"], ebp=frame, esp=frame - 24)
        failure_flags = returned.return_spec(
            frame, vector["cookie"], vector["cookie"] ^ 1
        )["flags"]
        _require(
            {r: machine.reg_read(i) for r, i in ids.items()} == failure_regs
            and machine.reg_read(x.UC_X86_REG_EFLAGS) & 0x8D5 == failure_flags
            and not machine.reg_read(x.UC_X86_REG_EFLAGS) & 0x400,
            "class cookie failure ABI differs",
        )
        failure_pages = {p: bytearray(v) for p, v in expected["pages"].items()}
        for i, b in enumerate((vector["cookie"] ^ 1).to_bytes(4, "little")):
            at = returned.COOKIE + i
            failure_pages[at & ~0xFFF][at & 0xFFF] = b
        _require(
            all(
                bytes(machine.mem_read(p, 4096)) == bytes(v)
                for p, v in failure_pages.items()
            ),
            "class cookie failure memory differs",
        )
        return dict(kind="cookie", rejected=True, endpoint="0x003574d5")
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "class prefix endpoint differs",
    )
    _require(
        len(allocations) == len(expected["heap_nodes"]),
        "class allocation count differs",
    )
    actual = {r: machine.reg_read(i) for r, i in ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        actual == expected["registers"]
        and flags & 0x8D5 == expected["flags"]
        and not flags & 0x400,
        "class registers or flags differ",
    )
    _require(events == expected["events"], "class ordered events differ")
    _require(
        all(
            bytes(machine.mem_read(p, 0x1000)) == expected["pages"][p]
            for p in (construction.STACK, construction.STACK + 0x1000)
        ),
        "class ancestor memory differs",
    )
    _require(
        all(
            bytes(machine.mem_read(p, 0x1000)) == payload
            for p, payload in expected["pages"].items()
            if p not in (construction.STACK, construction.STACK + 0x1000)
        ),
        "class protected memory differs",
    )
    return dict(
        vector=vector,
        registers=actual,
        flags=flags & 0x8D5,
        trace_rvas=visited,
        insertions=expected["insertions"],
        allocations=allocations,
        events_sha256=_canonical_sha256(events),
        memory_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(v).hexdigest()
                for p, v in expected["pages"].items()
            }
        ),
    )


def _preflight(sources):
    _require(
        set(sources) == set(SOURCE_PINS),
        "class internal spare source partition differs",
    )
    return {
        key: _source_identity(sources[key], *pin, key)
        for key, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    owner = _decode_body(data, image, sources["program_facts"], START)
    _require(
        sum(r.size for r in owner) == 237
        and hashlib.sha256(b"".join(bytes(r.bytes) for r in owner)).hexdigest()
        == prefix.OWNER_SHA256,
        "class owner differs",
    )
    witnesses = {p["rva"]: p for p in sources["prefix"]["body"]["points"]}
    for p in (
        sources["append_semantics"]["slice"]["points"]
        + sources["class_return"]["bodies"]["epilogue"]["points"]
        + sources["class_return"]["bodies"]["checker_normal"]["points"]
    ):
        _require(
            p["rva"] not in witnesses or witnesses[p["rva"]] == p,
            "class internal spare witness conflict",
        )
        witnesses[p["rva"]] = p
    ranges = [
        (int(s["start_rva"], 16), int(s["end_rva"], 16))
        for s in sources["prefix"]["body"]["ranges"]
    ] + list(SPARE_RANGES)
    covered = {a + i for a, b in ranges for i in range(b - a)}
    _require(
        all(i in covered for i in range(0x3574CA, 0x3574D5)),
        "normal checker missing from prefix",
    )
    codes, points = {}, []
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for a, b in sorted(ranges):
        offset = image.rva_to_file_offset(a)
        payload = data[offset : offset + b - a]
        part = [_point(r) for r in decoder.disasm(payload, BASE + a)]
        _require(
            sum(p["size"] for p in part) == b - a
            and all(witnesses.get(p["rva"]) == p for p in part),
            "class internal spare selected code differs",
        )
        codes[a] = payload
        points.extend(part)
    selected = [
        _point(r)
        for r in owner
        if any(a <= r.address - BASE < b for a, b in SPARE_RANGES)
    ]
    return codes, points, selected


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE,
        "exact class internal spare executable differs",
    )
    codes, points, selected = _load_code(data, image, sources)
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({pc for o in observations for pc in o["trace_rvas"]})
    required = {p["rva"] for p in selected} | {
        p["rva"] for p in sources["class_return"]["bodies"]["checker_normal"]["points"]
    }
    required |= {
        p["rva"]
        for p in sources["prefix"]["body"]["prefix_points"]
        if not 0x2EB15F <= int(p["rva"], 16) < 0x2EB179
    }
    _require(
        required <= set(union), "class internal spare selected normal coverage differs"
    )
    _require(
        not any(
            0x2EB15F <= int(pc, 16) < 0x2EB179
            or 0x2EB1D6 <= int(pc, 16) < 0x2EB1DF
            or 0x2EB1F7 <= int(pc, 16) < 0x2EB216
            for pc in union
        ),
        "excluded class arm executed",
    )
    sample = next(
        v
        for v in vectors()
        if v["source_keys"] and v["profile"] == "all_new" and v["old_size"] == 3
    )
    controls = []
    for kind, message in (
        ("ancestor", "class ancestor memory differs"),
        ("source", "class protected memory differs"),
        ("payload", "class protected memory differs"),
        ("vector", "class protected memory differs"),
        ("iterator", "class ancestor memory differs"),
    ):
        try:
            _run_case(codes, points, sample, kind)
        except ConformanceError as exc:
            _require(
                str(exc) == message, "class internal spare mutation failed incidentally"
            )
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("class internal spare mutation survived")
    controls.append(_run_case(codes, points, sample, "cookie"))
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(start_rva=f"0x{a:08x}", end_rva=f"0x{a+len(b):08x}")
                for a, b in codes.items()
            ],
            points=points,
            spare_return_points=selected,
        ),
        vectors=vectors(),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        executed_rvas=union,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            instruction_bytes=sum(map(len, codes.values())),
            static_sites=len(points),
            executed_sites=len(union),
            spare_return_bytes=sum(b - a for a, b in SPARE_RANGES),
            spare_return_sites=len(selected),
            iterations=sum(len(o["insertions"]) for o in observations),
            allocated_insertions=sum(len(o["allocations"]) for o in observations),
            existing_insertions=sum(
                sum(not i["inserted"] for i in o["insertions"]) for o in observations
            ),
            max_iterations=max(len(o["insertions"]) for o in observations),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Native class transfer followed by internal argument append into spare vector capacity and normal caller return on a finite canonical corpus",
            premises=[
                "Source and destination initially have at most seven canonical nodes with fixed hexadecimal keys and stable DWORD payloads",
                "Aligned eight-byte argument is the first, middle or last live record; old sizes one, three or seven have spare capacity",
                "Independent tree transfer and record append models check all final protected pages; ordered reads and writes and final ABI are exact",
                "Every descendant instruction is native except supplied successful HeapAlloc responses; DF clear and final cookie equal",
            ],
            not_claimed=[
                "Assertion, unaligned internal argument, vector growth, failed allocation, exceptions, arbitrary strings, aliased trees, or hardware execution",
                "Cookie mismatch is checked only through the exact first failure frontier, not failure handler behavior or a normal return",
                "No accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "class internal spare executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    _validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors(),
        "sealed class internal spare return differs",
    )
    _assert_publication_safe(evidence)
    return dict(
        status="structurally_verified",
        evidence_sha256=SEALED_SHA256,
        summary=evidence["summary"],
    )


def build_conformance(executable, sources):
    result = _build_unsealed(executable, sources)
    validate_structure(result, sources)
    return result


def validate_conformance(executable, evidence, sources):
    validate_structure(evidence, sources)
    _require(
        _canonical_bytes(build_conformance(executable, sources))
        == _canonical_bytes(evidence),
        "exact class internal spare return differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
