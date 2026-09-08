"""Native insertion prefix through successful construction, stopping before tree mutation."""

from __future__ import annotations
import hashlib, json
from pathlib import Path
from src.observatory import native_tree_lower_bound_semantics as leaf
from src.observatory import native_tree_insert_decision_conformance as decision
from src.observatory import native_tree_node_factory_conformance as factory
from src.observatory.native_lua_vector_allocation_return_conformance import _add_flags
from src.observatory import native_tree_lower_bound_conformance as leaf_replay
from src.observatory.native_vector_deallocation_conformance import _sub_flags
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

ANALYSIS_KIND = "pe_native_tree_insert_construction_conformance"
SEALED_SHA256 = "9b81311ccbef89af7e789b491776f9930e3d7ae23e437db71bdba8d9033ad599"
SOURCE_PINS = {
    **decision.SOURCE_PINS,
    "decision_conformance": (decision.ANALYSIS_KIND, decision.SEALED_SHA256),
    "factory_conformance": (factory.ANALYSIS_KIND, factory.SEALED_SHA256),
}
STACK = 0x30000000
DATA, RETURN, HEAP_GLOBAL, IAT, HEAP, IMPORT = (
    factory.DATA,
    factory.RETURN,
    factory.HEAP_GLOBAL,
    factory.IAT,
    factory.HEAP,
    factory.IMPORT,
)

START, STOP = 0x2E81F0, 0x2E826B
OUTPUT = 0x20000100
CONTINUATION = BASE + 0x2E8204


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    return [
        {**v, "query": ([] if v["root"] is None else v["query"]), "node_alignment": a}
        for v in decision.vectors()
        if v["frame_alignment"] in (0, 15)
        for a in (0, 1, 7, 15, 31)
    ]


def frame_join(o):
    _require(type(o) is int and 96 <= o < 2**32 - 16, "invalid construction ancestor")
    f = decision.frame_join(o)
    f.update(
        heap_api=o - 96,
        hint_frontier=o - 36,
        future_hint_entry=o - 40,
        protected_start=o - 96,
    )
    return f


def _fixture(vector):
    _require(
        type(vector["node_alignment"]) is int and 0 <= vector["node_alignment"] < 32,
        "invalid node alignment",
    )
    f = decision._fixture(vector)
    o = f["stack"]
    pages = {p: bytearray(v) for p, v in f["pages"].items()}
    pages.setdefault(leaf.ARG & ~0xFFF, bytearray(b"\xa5" * 0x1000))
    pages.setdefault(leaf.QUERY & ~0xFFF, bytearray(b"\xa5" * 0x1000))
    for page in (HEAP_GLOBAL & ~0xFFF, IAT & ~0xFFF):
        pages[page] = bytearray(0x1000)
    for i in range(4):
        pages[DATA + 0x1000 * i] = bytearray(
            factory.DATA_TEMPLATE[0x1000 * i : 0x1000 * (i + 1)]
        )
    for address, value in (
        (o + 8, leaf.ARG),
        (leaf.ARG, leaf.QUERY),
        (HEAP_GLOBAL, HEAP),
        (IAT, IMPORT),
    ):
        for i, b in enumerate(value.to_bytes(4, "little")):
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = b
    if vector["root"] is None:
        pages[leaf.QUERY & ~0xFFF][leaf.QUERY & 0xFFF] = 0
    f.update(
        query_argument=leaf.ARG,
        pages={p: bytes(v) for p, v in pages.items()},
        node=DATA + 0x100 + vector["node_alignment"],
    )
    return f


def _factory_expected(vector, fixture):
    n, p, t, a, k = (fixture[x] for x in ("n", "p", "t", "a", "k"))
    initial = fixture["registers"]
    stack = bytearray(fixture["stack"])
    data = bytearray(fixture["data"])
    events = []

    def event(access, address, value, width=4):
        events.append(dict(access=access, address=address, width=width, value=value))
        if access == "write":
            target, base = (
                (stack, STACK) if STACK <= address < STACK + 0x4000 else (data, DATA)
            )
            target[address - base : address - base + width] = value.to_bytes(
                width, "little"
            )

    r = lambda a, v: event("read", a, v)
    w = lambda a, v: event("write", a, v)
    w(n - 4, initial["ebp"])
    w(n - 8, BASE + 0x7CD98)
    h = n - 8
    rentry = n - 24
    w(h - 4, initial["esi"])
    w(h - 8, initial["edi"])
    w(h - 12, 24)
    w(h - 16, BASE + 0x7D06B)
    w(rentry - 4, n - 4)
    r(rentry + 4, 24)
    w(rentry - 8, 24)
    w(rentry - 12, BASE + 0x357507)
    w(rentry - 16, rentry - 4)
    r(rentry - 16, rentry - 4)
    w(rentry - 16, rentry - 4)
    w(rentry - 20, initial["esi"])
    r(rentry - 8, 24)
    w(rentry - 24, 24)
    w(rentry - 28, 0)
    r(HEAP_GLOBAL, HEAP)
    w(rentry - 32, HEAP)
    r(IAT, IMPORT)
    w(rentry - 36, BASE + 0x389463)
    r(rentry - 20, initial["esi"])
    r(rentry - 16, rentry - 4)
    r(rentry - 12, BASE + 0x357507)
    r(rentry - 8, 24)
    r(rentry - 4, n - 4)
    r(rentry, BASE + 0x7D06B)
    for offset in (0, 4, 8):
        r(t, vector["head"])
        w(p + offset, vector["head"])
    r(h - 8, initial["edi"])
    r(h - 4, initial["esi"])
    r(h, BASE + 0x7CD98)
    event("write", p + 12, 0, 2)
    r(n + 8, a)
    r(a, k)
    r(k, vector["key"])
    w(p + 16, vector["key"])
    w(p + 20, 0)
    r(n - 4, initial["ebp"])
    r(n, RETURN)
    regs = dict(initial, eax=p, ecx=vector["key"], edx=p + 16, esp=n + 16)
    flags = (
        (int(((p + 16) & 255).bit_count() % 2 == 0) << 2)
        | (int(p + 16 == 0) << 6)
        | (((p + 16) >> 31) << 7)
    )
    return dict(
        registers=regs, stack=bytes(stack), data=bytes(data), events=events, flags=flags
    )


def _expected(vector, fixture):
    result = decision._expected(vector, fixture)
    if not result["allocate"]:
        return result
    o = fixture["stack"]
    p = fixture["node"]
    n = o - 36
    pages = {p: bytearray(v) for p, v in result["pages"].items()}
    events = list(result["events"])

    def event(access, address, value, width=4):
        events.append(dict(access=access, address=address, width=width, value=value))
        if access == "write":
            for i, b in enumerate(value.to_bytes(width, "little")):
                pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = b

    event("write", n, BASE + 0x2E825F)
    stack = b"".join(bytes(pages[STACK + i * 0x1000]) for i in range(2))
    data = b"".join(bytes(pages[DATA + i * 0x1000]) for i in range(4))
    child = _factory_expected(
        dict(head=leaf.HEAD, key=leaf.QUERY),
        dict(
            n=n,
            p=p,
            t=leaf.TREE,
            a=o - 8,
            k=leaf.ARG,
            registers=dict(result["registers"], esp=n),
            stack=stack,
            data=data,
        ),
    )
    _require(
        child["events"][-1] == dict(access="read", address=n, width=4, value=RETURN),
        "factory continuation oracle differs",
    )
    child["events"][-1] = dict(access="read", address=n, width=4, value=BASE + 0x2E825F)
    for e in child["events"]:
        event(e["access"], e["address"], e["value"], e["width"])
    _require(
        b"".join(bytes(pages[STACK + i * 0x1000]) for i in range(2)) == child["stack"],
        "factory stack rebasing differs",
    )
    _require(
        b"".join(bytes(pages[DATA + i * 0x1000]) for i in range(4)) == child["data"],
        "factory payload rebasing differs",
    )
    for address, value in (
        (o - 24, p),
        (o - 28, p + 16),
        (o - 32, leaf_replay._node(result["candidate"])),
        (o - 36, o - 8),
    ):
        event("write", address, value)
    regs = dict(child["registers"], eax=o - 8, ecx=leaf.TREE, esp=o - 36)
    result.update(
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        flags=_add_flags(p, 16),
        flag_mask=0x8D5,
        endpoint=BASE + STOP,
    )
    return result


def _run_case(codes, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector)
    expected = _expected(vector, fixture)
    o = fixture["stack"]
    m = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, payload in fixture["pages"].items():
        m.mem_map(page, 0x1000)
        m.mem_write(page, payload)
    for code_page in {((BASE + a) & ~0xFFF) for a in codes}:
        m.mem_map(code_page, 0x1000)
        m.mem_write(code_page, b"\xcc" * 0x1000)
    m.mem_map(IMPORT, 0x1000)
    m.mem_write(IMPORT, b"\xcc")
    for start, code in codes.items():
        m.mem_write(BASE + start, code)
    m.mem_map(fixture["return_address"] & ~0xFFF, 0x1000)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in fixture["registers"]}
    for r, value in fixture["registers"].items():
        m.reg_write(ids[r], value)
    m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(p["rva"], 16) for rows in points.values() for p in rows}
    visited = []
    events = []
    summaries = []
    resume = None

    def on_code(machine, address, size, user):
        nonlocal resume
        if address == IMPORT:
            sp = machine.reg_read(x.UC_X86_REG_ESP)
            words = [
                int.from_bytes(machine.mem_read(sp + 4 * i, 4), "little")
                for i in range(4)
            ]
            _require(
                expected["allocate"]
                and not summaries
                and sp == o - 96
                and words == [BASE + 0x389463, HEAP, 0, 24],
                "construction heap handoff differs",
            )
            machine.reg_write(x.UC_X86_REG_EAX, fixture["node"])
            machine.reg_write(x.UC_X86_REG_ECX, 0xA0000001)
            machine.reg_write(x.UC_X86_REG_EDX, 0xB0000001)
            machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            machine.reg_write(x.UC_X86_REG_ESP, sp + 16)
            if negative == "padding":
                at = fixture["node"] + 14
                machine.mem_write(
                    at, bytes([int.from_bytes(machine.mem_read(at, 1), "little") ^ 1])
                )
            summaries.append(dict(entry_esp=sp, request=24, continuation=words[0]))
            resume = words[0]
            machine.emu_stop()
            return
        if address in (fixture["return_address"], BASE + STOP):
            machine.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "decision escaped reviewed ranges")
        visited.append(f"0x{pc:08x}")
        if pc == START:
            at = (
                o + 12
                if negative == "ancestor"
                else leaf.HEAD + 14 if negative == "tree" else None
            )
            if at is not None:
                machine.mem_write(
                    at, bytes([int.from_bytes(machine.mem_read(at, 1), "little") ^ 1])
                )

    def memory(machine, access, address, size, value, user):
        _require(size in (1, 2, 4), "unexpected decision access width")
        write = access == uc.UC_MEM_WRITE
        events.append(
            dict(
                access="write" if write else "read",
                address=address,
                width=size,
                value=(
                    value
                    if write
                    else int.from_bytes(machine.mem_read(address, size), "little")
                ),
            )
        )

    m.hook_add(uc.UC_HOOK_CODE, on_code)
    m.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, memory)
    m.emu_start(BASE + START, 0, count=50000)
    if resume is not None:
        m.emu_start(resume, 0, count=50000)
    _require(
        len(summaries) == int(expected["allocate"]), "construction API count differs"
    )
    _require(
        m.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "decision endpoint differs",
    )
    actual = {r: m.reg_read(i) for r, i in ids.items()}
    flags = m.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        actual == expected["registers"]
        and flags & expected["flag_mask"] == expected["flags"] & expected["flag_mask"]
        and not flags & 0x400,
        "decision registers or flags differ",
    )
    _require(events == expected["events"], "decision ordered events differ")
    stack_pages = {(o + i) & ~0xFFF for i in range(-96, 16)}
    _require(
        all(
            bytes(m.mem_read(page, 0x1000)) == expected["pages"][page]
            for page in stack_pages
        ),
        "decision ancestor memory differs",
    )
    _require(
        all(
            bytes(m.mem_read(page, 0x1000)) == payload
            for page, payload in expected["pages"].items()
            if page not in stack_pages
        ),
        "decision source or output memory differs",
    )
    return dict(
        inputs=vector,
        summaries=summaries,
        registers=actual,
        flags=flags & expected["flag_mask"],
        flag_mask=expected["flag_mask"],
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        memory_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(v).hexdigest()
                for p, v in expected["pages"].items()
            }
        ),
        allocate=expected["allocate"],
        classification=expected["classification"],
        ordered=expected["ordered"],
    )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256, "executable differs")
    owner = _decode_body(data, image, sources["program_facts"], START)
    lower = _decode_body(data, image, sources["program_facts"], leaf.START)
    points = {
        START: [_point(r) for r in owner if r.address < BASE + STOP],
        leaf.START: [_point(r) for r in lower],
    }
    _require(
        points[leaf.START] == sources["lower_bound_semantics"]["body"]["points"],
        "lower-bound source witness differs",
    )
    codes = {}
    for a, b in ((START, STOP), (leaf.START, leaf.END)):
        offset = image.rva_to_file_offset(a)
        codes[a] = data[offset : offset + b - a]
        _require(
            sum(p["size"] for p in points[a]) == b - a, "decision body extent differs"
        )
    for name, (a, b) in factory.BODIES.items():
        offset = image.rva_to_file_offset(a)
        codes[a] = data[offset : offset + b - a]
        points[a] = sources["factory_conformance"]["bodies"][name]["points"]
        actual = [
            _point(r) for r in _decode_body(data, image, sources["program_facts"], a)
        ]
        _require(points[a] == actual, "factory source witness differs")
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({p for o in observations for p in o["trace_rvas"]})
    _require(
        all(
            p["rva"] in union
            for a in (START, leaf.START, 0x7CD90, 0x7D060)
            for p in points[a]
        ),
        "decision coverage differs",
    )
    controls = []
    control_vector = next(v for v in vectors() if v["root"] is None)
    _require(
        _expected(control_vector, _fixture(control_vector))["allocate"],
        "padding control requires allocation",
    )
    for kind, message in (
        ("ancestor", "decision ancestor memory differs"),
        ("tree", "decision source or output memory differs"),
        ("padding", "decision source or output memory differs"),
    ):
        try:
            _run_case(codes, points, control_vector, kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "decision control failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("decision mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=ids,
        build_identity=sources["program_facts"]["identity"],
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        bodies={
            f"0x{a:08x}": dict(points=points[a], instruction_bytes=len(c))
            for a, c in codes.items()
        },
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=union,
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            loaded_sites=sum(len(p) for p in points.values()),
            heap_api_summaries=sum(len(o["summaries"]) for o in observations),
            instruction_bytes=sum(len(c) for c in codes.values()),
            executed_sites=len(union),
            allocation_frontiers=sum(o["allocate"] for o in observations),
            existing_returns=sum(not o["allocate"] for o in observations),
            unordered_existing_greater=sum(
                not o["allocate"] and o["classification"] == 1 for o in observations
            ),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Insertion owner executes native lower-bound and successful node construction, returning existing candidate or stopping before insertion-hint CALL",
            frame_relation="Owner O reaches lower-bound O-28, factory O-36 and heap API O-96; existing return O+12, hint frontier O-36 with result slot, candidate, key field and node arguments",
            premises=[
                "Finite bounded rooted byte-key trees and stable query storage inherited from lower-bound domain; disjoint ancestor and output storage; DF clear",
                "Stable candidate selection implies equality on every existing return; sorted inorder keys additionally justify global minimum and absence guarantees",
                "Independent positive writable24-byte node and successful HeapAlloc response preserving complete ancestor, tree, query and imports; five node alignments and two owner frames",
            ],
            not_claimed=[
                "Insertion hint and topology mutations, actual heap effects or allocation failures",
                "Whole game equivalence or accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    _validate_json_tree(evidence, "evidence")
    ids = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == ids
        and evidence["vectors"] == vectors(),
        "sealed decision differs",
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
        "exact decision differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
