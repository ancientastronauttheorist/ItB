"""Native insertion decision with lower-bound traversal, stopping before construction."""

from __future__ import annotations
import hashlib, json
from pathlib import Path
from src.observatory import native_tree_lower_bound_semantics as leaf
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

ANALYSIS_KIND = "pe_native_tree_insert_decision_conformance"
SEALED_SHA256 = "01dc9252982cac47b67691b2b20e41ea24b41876d07ef05cbbf91625ee6aaeb0"
SOURCE_PINS = {
    "program_facts": leaf.SOURCE_PINS["program_facts"],
    "lower_bound_semantics": (leaf.ANALYSIS_KIND, leaf.SEALED_SHA256),
    "lower_bound_conformance": (leaf_replay.ANALYSIS_KIND, leaf_replay.SEALED_SHA256),
}
START, STOP = 0x2E81F0, 0x2E825A
OUTPUT = 0x20000100
CONTINUATION = BASE + 0x2E8204


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    recipes = [
        v
        for v in leaf.corpus()
        if v["frame_alignment"] == 0 and v["nil_flag"] == 1 and v["seed"] == 0
    ]
    return [
        dict(v, frame_alignment=f, nil_flag=nil, seed=7)
        for v in recipes
        for f in (0, 1, 7, 15)
        for nil in (1, 128, 255)
    ]


def frame_join(o):
    _require(type(o) is int and 44 <= o < 2**32 - 16, "invalid decision ancestor")
    return dict(
        owner=o,
        frame=o - 4,
        lower_bound=o - 28,
        deepest_save=o - 44,
        existing_return=o + 12,
        factory_frontier=o - 32,
        future_factory_entry=o - 36,
        future_heap_entry=o - 96,
    )


def _fixture(vector):
    f = leaf.case_fixture(**leaf.unpack(vector))
    o = f["stack"]
    memory = dict(f["memory"])
    memory.update({o + i: ((i * 23) ^ vector["seed"]) & 255 for i in range(-64, 16)})
    memory.update({OUTPUT + i: ((i * 17) ^ 0x73) & 255 for i in range(16)})
    q = leaf.ARG if vector["root"] is not None else 0xDEADF000
    for address, value in ((o, f["return_address"]), (o + 4, OUTPUT), (o + 8, q)):
        memory.update(
            {address + i: b for i, b in enumerate(value.to_bytes(4, "little"))}
        )
    pages = {address & ~0xFFF: bytearray(b"\xa5" * 0x1000) for address in memory}
    for address, value in memory.items():
        pages[address & ~0xFFF][address & 0xFFF] = value
    f.update(
        memory=memory, pages={p: bytes(v) for p, v in pages.items()}, query_argument=q
    )
    return f


def _expected(vector, fixture):
    o = fixture["stack"]
    initial = fixture["registers"]
    qarg = fixture["query_argument"]
    events = []
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}

    def event(access, address, value, width=4):
        events.append(dict(access=access, address=address, width=width, value=value))
        if access == "write":
            for i, b in enumerate(value.to_bytes(width, "little")):
                pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = b

    r = lambda a, v: event("read", a, v)
    w = lambda a, v: event("write", a, v)
    for offset, reg in (
        (-4, "ebp"),
        (-8, "ecx"),
        (-12, "ebx"),
        (-16, "esi"),
        (-20, "edi"),
    ):
        w(o + offset, initial[reg])
    r(o + 8, qarg)
    w(o - 24, qarg)
    r(o + 4, OUTPUT)
    w(o - 28, CONTINUATION)
    child_initial = dict(initial, ebp=o - 4, ebx=leaf.TREE, edi=OUTPUT, esp=o - 28)
    child = leaf_replay.oracle(
        vector, dict(registers=child_initial, stack=o - 28, return_address=CONTINUATION)
    )
    for e in child["events"]:
        event(e["access"], e["address"], e["value"], e["width"])
    regs = dict(child["registers"])
    candidate = leaf_replay._node(child["candidate"])
    regs["esi"] = candidate
    r(leaf.TREE, leaf.HEAD)
    allocate = candidate == leaf.HEAD
    classification = None
    flags = _sub_flags(candidate, leaf.HEAD)
    mask = 0x8D5
    if not allocate:
        key = bytes(vector["nodes"][child["candidate"]]["key"])
        query = bytes(vector["query"])
        key_address = leaf.KEYS + 256 * child["candidate"]
        r(o + 8, qarg)
        r(candidate + 16, key_address)
        r(qarg, leaf.QUERY)
        match = 0
        while match < len(query) and match < len(key) and query[match] == key[match]:
            match += 1
        for i in range(match + 1):
            event("read", leaf.QUERY + i, query[i] if i < len(query) else 0, 1)
            event("read", key_address + i, key[i] if i < len(key) else 0, 1)
        classification = -1 if query < key else 1 if query > key else 0
        _require(
            classification <= 0, "stable lower-bound candidate cannot be below query"
        )
        displacement = 2 * (match // 2) + (2 if query == key and match % 2 else 0)
        regs.update(
            eax=classification & 0xFFFFFFFF,
            ecx=key_address + displacement,
            edx=(regs["edx"] & 0xFFFFFF00)
            | (query[match] if match < len(query) else 0),
        )
        flags = {-1: 0x84, 0: 0x44, 1: 0}[classification]
        mask = 0x8C5
        allocate = classification < 0
    if allocate:
        r(o + 8, qarg)
        dummy = regs["ecx"]
        w(o - 24, dummy)
        w(o - 8, qarg)
        w(o - 28, o - 8)
        w(o - 32, dummy)
        regs.update(eax=o - 8, ecx=leaf.TREE, esp=o - 32)
        endpoint = BASE + STOP
    else:
        w(OUTPUT, candidate)
        event("write", OUTPUT + 4, 0, 1)
        for offset, reg in ((-20, "edi"), (-16, "esi"), (-12, "ebx"), (-4, "ebp")):
            r(o + offset, initial[reg])
        r(o, fixture["return_address"])
        regs.update(
            eax=OUTPUT,
            ebx=initial["ebx"],
            esi=initial["esi"],
            edi=initial["edi"],
            ebp=initial["ebp"],
            esp=o + 12,
        )
        endpoint = fixture["return_address"]
        _require(
            classification == 0,
            "stable existing-key corollary differs",
        )
    return dict(
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        flags=flags,
        flag_mask=mask,
        endpoint=endpoint,
        allocate=allocate,
        classification=classification,
        ordered=child["ordered"],
        candidate=child["candidate"],
    )


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
    code_page = (BASE + START) & ~0xFFF
    m.mem_map(code_page, 0x1000)
    m.mem_write(code_page, b"\xcc" * 0x1000)
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

    def on_code(machine, address, size, user):
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
        _require(size in (1, 4), "unexpected decision access width")
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
    m.emu_start(BASE + START, 0, count=20000)
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
    stack_pages = {(o + i) & ~0xFFF for i in range(-64, 16)}
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
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({p for o in observations for p in o["trace_rvas"]})
    _require(
        set(union) == {p["rva"] for rows in points.values() for p in rows},
        "decision coverage differs",
    )
    controls = []
    for kind, message in (
        ("ancestor", "decision ancestor memory differs"),
        ("tree", "decision source or output memory differs"),
    ):
        try:
            _run_case(codes, points, vectors()[0], kind)
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
            claim="Insertion owner prefix executes native lower-bound traversal and returns existing candidate or stops before node-factory CALL",
            frame_relation="Owner O reaches lower-bound O-28 and deepest save O-44; existing return O+12; factory frontier O-32 with localqueryslot O-8 and pointertodummyarguments prepared",
            premises=[
                "Finite bounded rooted byte-key trees and stable query storage inherited from lower-bound domain; disjoint ancestor and output storage; DF clear",
                "Stable candidate selection implies equality on every existing return; sorted inorder keys additionally justify global minimum and absence guarantees",
            ],
            not_claimed=[
                "Node construction, insertion hint, topology mutations or allocation failure effects",
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
