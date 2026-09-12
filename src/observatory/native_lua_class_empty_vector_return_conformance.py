"""Finite native class transfer, first vector allocation, and normal caller return."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_lua_class_tree_conformance as prefix
from src.observatory import native_lua_class_spare_return_conformance as spare
from src.observatory import native_small_vector_growth_conformance as growth
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

ANALYSIS_KIND = "pe_native_lua_class_empty_vector_return_conformance"
SEALED_SHA256 = "557fb53f2566af2f8da35bdb48a1ca7038b0be65e648f696f3d78e978ed06c16"
SOURCE_PINS = {
    "program_facts": prefix.SOURCE_PINS["program_facts"],
    "spare_return": (spare.ANALYSIS_KIND, spare.SEALED_SHA256),
    "growth_conformance": (growth.ANALYSIS_KIND, growth.SEALED_SHA256),
    "growth_semantics": growth.SOURCE_PINS["growth"],
    "resize_semantics": growth.SOURCE_PINS["owner"],
    "allocation_conformance": growth.SOURCE_PINS["allocation_conformance"],
    "small_copy": growth.SOURCE_PINS["small_copy"],
}

START = prefix.START
RECEIVER, ARGUMENT, SOURCE_HEAD = prefix.RECEIVER, prefix.ARGUMENT, prefix.SOURCE_HEAD
construction = prefix.construction
ConformanceError, _require = prefix.ConformanceError, prefix._require
SPARE_RANGES = ((0x2EB1BB, 0x2EB1CC), (0x2EB1F7, 0x2EB1FC), (0x2EB205, 0x2EB22D))


def vectors():
    return [
        dict(v, vector_alignment=alignment)
        for v in prefix.vectors()
        for alignment in (0, 7, 31)
    ]


def _fixture(vector):
    alignment = vector["vector_alignment"]
    _require(type(alignment) is int and 0 <= alignment < 32, "invalid vector alignment")
    fixture = prefix._fixture(vector)
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    for offset in (4, 8, 12):
        for i in range(4):
            a = RECEIVER + offset + i
            pages[a & ~0xFFF][a & 0xFFF] = 0
    fresh = construction.DATA + 0x2000 + alignment
    fixture.update(
        pages={p: bytes(v) for p, v in pages.items()},
        vector_begin=fresh,
        vector_end=fresh,
        vector_capacity=fresh + 8,
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
        "external append receiver differs",
    )
    _require(
        read(receiver + 8) == read(receiver + 12) == 0, "initial vector is not null"
    )
    # PUSH ECX passes an unused dummy; growth and every allocation/copy instruction remain native.
    write(frame - 36, regs["ecx"])
    write(frame - 40, BASE + 0x2EB205)
    regs.update(eax=0, esi=receiver, ecx=receiver + 4, esp=frame - 40)
    child_vector = dict(
        has_old=False,
        old_size=0,
        old_capacity=0,
        requested=1,
        new_alignment=vector["vector_alignment"],
        old_alignment=0,
        stack_alignment=vector["frame_alignment"],
        new_pointer=fixture["vector_begin"],
    )
    child = growth._expected(
        child_vector,
        regs,
        b"".join(bytes(pages[construction.STACK + i * 4096]) for i in range(2)),
        b"".join(bytes(pages[construction.DATA + i * 4096]) for i in range(4)),
        b"",
        bytes(pages[RECEIVER & ~0xFFF]),
        stack_base=construction.STACK,
        object_base=RECEIVER & ~0xFFF,
    )
    _require(
        child["events"][-1]
        == dict(access="read", address=frame - 40, width=4, value=growth.RETURN),
        "class growth continuation differs",
    )
    child["events"][-1] = dict(
        access="read", address=frame - 40, width=4, value=BASE + 0x2EB205
    )
    events.extend(child["events"])
    for i in range(2):
        pages[construction.STACK + i * 4096] = bytearray(
            child["stack"][4096 * i : 4096 * (i + 1)]
        )
    for i in range(4):
        pages[construction.DATA + i * 4096] = bytearray(
            child["new"][4096 * i : 4096 * (i + 1)]
        )
    pages[RECEIVER & ~0xFFF] = bytearray(child["object"])
    regs = dict(child["registers"])
    _require(
        regs["esp"] == frame - 32 and regs["edi"] == ARGUMENT,
        "class growth ABI differs",
    )
    end = read(receiver + 8)
    _require(
        end == fixture["vector_begin"] and end != 0, "first vector allocation differs"
    )
    first = read(ARGUMENT)
    write(end, first)
    second = read(ARGUMENT + 4)
    write(end + 4, second)
    write(receiver + 8, read(receiver + 8) + 8)
    regs.update(eax=second, ecx=end, esi=receiver)
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
    result["tree_heap_count"] = len(result["heap_nodes"])
    result["heap_nodes"] = result["heap_nodes"] + [fixture["vector_begin"]]
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
    for offset, value in (
        (4, fixture["vector_begin"]),
        (8, fixture["vector_begin"] + 8),
        (12, fixture["vector_begin"] + 8),
    ):
        for i, b in enumerate(value.to_bytes(4, "little")):
            a = RECEIVER + offset + i
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
            if (
                negative == "heap_request"
                and len(allocations) == expected["tree_heap_count"]
            ):
                m.mem_write(sp + 12, (9).to_bytes(4, "little"))
            words = [
                int.from_bytes(m.mem_read(sp + i * 4, 4), "little") for i in range(4)
            ]
            tree_allocation = len(allocations) < expected["tree_heap_count"]
            request = 24 if tree_allocation else 8
            _require(
                len(allocations) < len(expected["heap_nodes"])
                and sp == frame - (140 if tree_allocation else 136)
                and words == [BASE + 0x389463, construction.HEAP, 0, request],
                "class heap handoff differs",
            )
            node = expected["heap_nodes"][len(allocations)]
            if negative == "heap_response" and not tree_allocation:
                node ^= 1
            for register, value in (
                (x.UC_X86_REG_EAX, node),
                (x.UC_X86_REG_ECX, 0xA0000001),
                (x.UC_X86_REG_EDX, 0xB0000001),
                (x.UC_X86_REG_EFLAGS, 0x246),
                (x.UC_X86_REG_ESP, sp + 16),
            ):
                m.reg_write(register, value)
            allocations.append(
                dict(node=node, entry_esp=sp, request=request, continuation=words[0])
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
    _require(set(sources) == set(SOURCE_PINS), "class spare source partition differs")
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
    bodies = [
        sources["spare_return"]["body"],
        sources["growth_semantics"]["body"],
        sources["resize_semantics"]["body"],
        *sources["allocation_conformance"]["bodies"].values(),
        *sources["small_copy"]["body"]["ranges"],
    ]
    witnesses = {}
    for body in bodies:
        for point in body["points"]:
            _require(
                point["rva"] not in witnesses or witnesses[point["rva"]] == point,
                "empty vector witness conflict",
            )
            witnesses[point["rva"]] = point
    # The newly reached push/call is independently pinned by the complete exact owner hash.
    for ins in owner:
        if 0x2EB1FC <= ins.address - BASE < 0x2EB205:
            witnesses[_point(ins)["rva"]] = _point(ins)
    ranges = [
        (int(r["start_rva"], 16), int(r["end_rva"], 16))
        for r in sources["spare_return"]["body"]["ranges"]
    ]
    ranges += [(0x2EB1FC, 0x2EB205)] + [
        span for name, span in growth.BODIES.items() if not name.startswith("free_")
    ]
    # Merge overlapping exact spans so common HeapAlloc wrappers/checkers are loaded and counted once.
    merged = []
    for a, b in sorted(ranges):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    codes, points = {}, []
    for a, b in merged:
        offset = image.rva_to_file_offset(a)
        payload = data[offset : offset + b - a]
        part = [_point(r) for r in decoder.disasm(payload, BASE + a)]
        _require(
            sum(p["size"] for p in part) == b - a
            and all(witnesses.get(p["rva"]) == p for p in part),
            "class empty vector selected code differs",
        )
        codes[a] = payload
        points.extend(part)
    selected = [
        _point(r)
        for r in owner
        if prefix.STOP <= r.address - BASE < 0x2EB22D
        and not 0x2EB1CC <= r.address - BASE < 0x2EB1F7
    ]
    return codes, points, selected


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE,
        "exact class spare executable differs",
    )
    codes, points, selected = _load_code(data, image, sources)
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({pc for o in observations for pc in o["trace_rvas"]})
    # Exact NULL-old path reaches allocation and the scalar zero-byte copy; no free or feature/table read occurs.
    required = {
        f"0x{pc:08x}"
        for pc in (
            0x2EB1BB,
            0x2EB1BE,
            0x2EB1C1,
            0x2EB1C3,
            0x2EB1F7,
            0x2EB1FA,
            0x2EB1FC,
            0x2EB1FD,
            0x2EB200,
            0x2EB205,
            0x2EB208,
            0x2EB20A,
            0x2EB20C,
            0x2EB20E,
            0x2EB210,
            0x2EB213,
            0x2EB216,
            0x2EB21A,
            0x2EB222,
            0x2EB22A,
            0x2EB620,
            0x2EB669,
            0x2EB680,
            0x2EB6A6,
            0x3574CA,
        )
    }
    required |= {
        p["rva"] for p in selected if not 0x2EB1C5 <= int(p["rva"], 16) < 0x2EB1CC
    }
    required |= {
        p["rva"]
        for p in points
        if START <= int(p["rva"], 16) < prefix.STOP
        and not 0x2EB15F <= int(p["rva"], 16) < 0x2EB179
    }
    _require(required <= set(union), "class empty vector normal coverage differs")
    _require(
        not any(
            0x2EB15F <= int(pc, 16) < 0x2EB179 or 0x2EB1C5 <= int(pc, 16) < 0x2EB1F7
            for pc in union
        ),
        "excluded class arm executed",
    )
    sample = next(
        v
        for v in vectors()
        if v["source_keys"]
        and v["profile"] == "all_new"
        and v["vector_alignment"] == 31
    )
    controls = []
    for kind, message in (
        ("ancestor", "class ancestor memory differs"),
        ("source", "class protected memory differs"),
        ("payload", "class protected memory differs"),
        ("vector", "class protected memory differs"),
        ("iterator", "class ancestor memory differs"),
        ("heap_request", "class heap handoff differs"),
        ("heap_response", "class ordered events differ"),
    ):
        try:
            _run_case(codes, points, sample, kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "class spare mutation failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("class spare mutation survived")
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
            empty_vector_return_points=selected,
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
            allocation_requests=len(observations),
            first_vector_records=len(observations),
            iterations=sum(len(o["insertions"]) for o in observations),
            allocated_insertions=sum(len(o["allocations"]) - 1 for o in observations),
            existing_insertions=sum(
                sum(not i["inserted"] for i in o["insertions"]) for o in observations
            ),
            max_iterations=max(len(o["insertions"]) for o in observations),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Native class transfer, initially null vector growth allocating its first record, and normal caller return on a finite canonical corpus",
            premises=[
                "Source and destination initially have at most seven canonical nodes with fixed hexadecimal keys and stable DWORD payloads",
                "Vector begins with three null pointers; one fresh eight-byte allocation is disjoint from every tree node and the external argument",
                "Independent tree transfer and record append models check all final protected pages; ordered reads and writes and final ABI are exact",
                "Every descendant instruction is native except supplied successful HeapAlloc responses; DF clear and final cookie equal",
            ],
            not_claimed=[
                "Assertion, internal argument, nonnull old vector growth or deallocation, failed allocation, exceptions, arbitrary strings, aliased trees, or hardware execution",
                "Cookie mismatch is checked only through the exact first failure frontier, not failure handler behavior or a normal return",
                "No accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "class spare executable changed",
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
        "sealed class spare return differs",
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
        "exact class spare return differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
