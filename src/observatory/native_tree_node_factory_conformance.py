"""Native 24-byte tree-node construction with one supplied successful heap response."""

from __future__ import annotations
import hashlib, json
from pathlib import Path
import capstone
from src.observatory import native_vector_allocation_conformance as allocation
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

ANALYSIS_KIND = "pe_native_tree_node_factory_conformance"
SEALED_SHA256 = "8b1c632e4c818a06e1083d82fce3aabdbdc7a10046c9567f0a6bd59de29d339c"
SOURCE_PINS = {
    "program_facts": append.SOURCE_PINS["program_facts"],
    "allocation_conformance": (allocation.ANALYSIS_KIND, allocation.SEALED_SHA256),
}
STACK, DATA, RETURN, IMPORT = (
    allocation.STACK,
    allocation.DATA,
    allocation.RETURN,
    allocation.IMPORT,
)
TREE, ARG, KEY = 0x09000000, 0x01000000, 0x0A000000
HEAP_GLOBAL, IAT, HEAP = allocation.HEAP_GLOBAL, allocation.IAT, allocation.HEAP_HANDLE
BODIES = {
    "factory": (0x7CD90, 0x7CDB9),
    "initializer": (0x7D060, 0x7D093),
    **{k: v for k, v in allocation.BODIES.items() if k != "allocation"},
}
STACK_TEMPLATE = bytes(((i * 43) ^ (i >> 6) ^ 0xC7) & 255 for i in range(0x4000))
DATA_TEMPLATE = bytes(((i * 41) ^ (i >> 5) ^ 0x65) & 255 for i in range(0x4000))


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    return [
        dict(alignment=a, frame_alignment=f, head=head, key=key, seed=seed)
        for a in range(32)
        for f in (0, 1, 7, 15)
        for head in (0, 0x12345678, 0xFFFFFFFF)
        for key in (0, 0x87654321, 0xFFFFFFFF)
        for seed in (1, 7)
    ]


def frame_join(n):
    _require(type(n) is int and 60 <= n < 2**32 - 16, "invalid factory ancestor")
    return dict(
        factory=n,
        initializer=n - 8,
        retry=n - 24,
        heap_api=n - 60,
        protected_start=n - 60,
        protected_end=n + 16,
        returned=n + 16,
    )


def _fixture(vector):
    for k, limit in (("alignment", 32), ("frame_alignment", 16), ("seed", 16)):
        _require(
            type(vector[k]) is int and 0 <= vector[k] < limit,
            "invalid factory alignment or seed",
        )
    for k in ("head", "key"):
        _require(
            type(vector[k]) is int and 0 <= vector[k] < 2**32, "invalid factory word"
        )
    n = STACK + 0x2000 + vector["frame_alignment"]
    p = DATA + 0x100 + vector["alignment"]
    t = TREE + 0x100
    a = ARG + 0x100
    k = KEY + 0x200
    stack = bytearray(STACK_TEMPLATE)
    pages = {
        TREE: bytearray(0x1000),
        ARG: bytearray(0x1000),
        KEY: bytearray(0x1000),
        HEAP_GLOBAL & ~0xFFF: bytearray(0x1000),
        IAT & ~0xFFF: bytearray(0x1000),
    }
    for address, value in ((n, RETURN), (n + 8, a)):
        stack[address - STACK : address - STACK + 4] = value.to_bytes(4, "little")
    for address, value in (
        (t, vector["head"]),
        (a, k),
        (k, vector["key"]),
        (HEAP_GLOBAL, HEAP),
        (IAT, IMPORT),
    ):
        base = address & ~0xFFF
        pages[base][address - base : address - base + 4] = value.to_bytes(4, "little")
    regs = {
        r: (0x16273849 + i * 0x1010101 + vector["seed"]) & 0xFFFFFFFF
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs.update(esp=n, ecx=t)
    return dict(
        n=n,
        p=p,
        t=t,
        a=a,
        k=k,
        stack=bytes(stack),
        data=DATA_TEMPLATE,
        pages={p: bytes(v) for p, v in pages.items()},
        registers=regs,
    )


def _expected(vector, fixture):
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


def _run_case(codes, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector)
    expected = _expected(vector, fixture)
    n = fixture["n"]
    p = fixture["p"]
    m = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    pages = (
        {BASE + (a & ~0xFFF) for a, b in BODIES.values()}
        | set(fixture["pages"])
        | {RETURN, IMPORT}
    )
    for page in sorted(pages):
        m.mem_map(page, 0x1000)
    m.mem_map(STACK, 0x4000)
    m.mem_map(DATA, 0x4000)
    m.mem_write(STACK, fixture["stack"])
    m.mem_write(DATA, fixture["data"])
    for page, payload in fixture["pages"].items():
        m.mem_write(page, payload)
    for name, (a, b) in BODIES.items():
        m.mem_write(BASE + a, codes[name])
    m.mem_write(IMPORT, b"\xcc")
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in fixture["registers"]}
    for r, value in fixture["registers"].items():
        m.reg_write(ids[r], value)
    m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(p["rva"], 16) for rows in points.values() for p in rows}
    visited = []
    events = []
    summaries = []
    resume = None

    def code(machine, address, size, user):
        nonlocal resume
        if address == IMPORT:
            sp = machine.reg_read(x.UC_X86_REG_ESP)
            words = [
                int.from_bytes(machine.mem_read(sp + 4 * i, 4), "little")
                for i in range(4)
            ]
            _require(
                not summaries
                and sp == n - 60
                and words == [BASE + 0x389463, HEAP, 0, 24],
                "factory heap handoff differs",
            )
            machine.reg_write(x.UC_X86_REG_EAX, p)
            machine.reg_write(x.UC_X86_REG_ECX, 0xA0000001)
            machine.reg_write(x.UC_X86_REG_EDX, 0xB0000001)
            machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            machine.reg_write(x.UC_X86_REG_ESP, sp + 16)
            if negative == "ancestor":
                machine.mem_write(
                    n + 4,
                    (int.from_bytes(machine.mem_read(n + 4, 4), "little") ^ 1).to_bytes(
                        4, "little"
                    ),
                )
            if negative == "padding":
                machine.mem_write(
                    p + 14,
                    bytes([int.from_bytes(machine.mem_read(p + 14, 1), "little") ^ 1]),
                )
            summaries.append(dict(entry_esp=sp, request=24, continuation=words[0]))
            resume = words[0]
            machine.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "factory execution escaped successful native ranges")
        visited.append(f"0x{pc:08x}")

    def memory(machine, access, address, size, value, user):
        _require(size in (2, 4), "unexpected factory access width")
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

    m.hook_add(uc.UC_HOOK_CODE, code)
    m.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, memory)
    m.emu_start(BASE + 0x7CD90, RETURN, count=300)
    if resume is not None:
        m.emu_start(resume, RETURN, count=300)
    _require(
        m.reg_read(x.UC_X86_REG_EIP) == RETURN and len(summaries) == 1,
        "factory did not return",
    )
    actual = {r: m.reg_read(i) for r, i in ids.items()}
    flags = m.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        actual == expected["registers"]
        and flags & 0x8C5 == expected["flags"] & 0x8C5
        and not flags & 0x400,
        "factory registers or flags differ",
    )
    _require(events == expected["events"], "factory ordered events differ")
    _require(
        bytes(m.mem_read(STACK, 0x4000)) == expected["stack"],
        "factory ancestor memory differs",
    )
    _require(
        bytes(m.mem_read(DATA, 0x4000)) == expected["data"],
        "factory payload or padding differs",
    )
    _require(
        all(
            bytes(m.mem_read(page, len(payload))) == payload
            for page, payload in fixture["pages"].items()
        ),
        "factory source or global memory differs",
    )
    return dict(
        inputs=vector,
        registers=actual,
        flags=flags & 0x8C5,
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        stack_sha256=hashlib.sha256(expected["stack"]).hexdigest(),
        data_sha256=hashlib.sha256(expected["data"]).hexdigest(),
        summaries=summaries,
    )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256, "executable differs")
    codes = {}
    points = {}
    runtime = {
        p["rva"]: p
        for b in sources["allocation_conformance"]["bodies"].values()
        for p in b["points"]
    }
    for name, (a, b) in BODIES.items():
        rows = _decode_body(data, image, sources["program_facts"], a)
        points[name] = [_point(r) for r in rows]
        offset = image.rva_to_file_offset(a)
        codes[name] = data[offset : offset + b - a]
        _require(
            sum(p["size"] for p in points[name]) == b - a, "factory body extent differs"
        )
        if name not in ("factory", "initializer"):
            _require(
                all(runtime.get(p["rva"]) == p for p in points[name]),
                "runtime source witness differs",
            )
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({p for o in observations for p in o["trace_rvas"]})
    _require(
        all(
            p["rva"] in union
            for name in ("factory", "initializer")
            for p in points[name]
        ),
        "factory or initializer coverage differs",
    )
    controls = []
    for kind, message in (
        ("ancestor", "factory ancestor memory differs"),
        ("padding", "factory payload or padding differs"),
    ):
        try:
            _run_case(codes, points, vectors()[0], kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "factory control failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("factory mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=ids,
        build_identity=sources["program_facts"]["identity"],
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        vectors=vectors(),
        bodies={
            name: dict(
                start_rva=f"0x{a:08x}", end_rva=f"0x{b:08x}", points=points[name]
            )
            for name, (a, b) in BODIES.items()
        },
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=union,
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            loaded_bytes=sum(len(c) for c in codes.values()),
            loaded_sites=sum(len(p) for p in points.values()),
            executed_sites=len(union),
            heap_api_summaries=len(observations),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Native 24-byte tree node factory and link initializer execute retry and heap wrapper machinery; only one successful HeapAlloc response is supplied",
            domain="Positive disjoint writable 24-byte allocation, independent tree head and two-level key pointer chain; all32 blockalignments paired with four frames and two seeds",
            frame_relation="Factory N reaches initializer N-8, retry N-24 and heap API N-60, returning N+16 and consuming three arguments",
            oracle="Independent complete ordered native stack, repeated tree-head reads and node stores; runtime success frame follows previously sealed native allocation path with this caller continuation",
            premises=[
                "Stable tree and key sources, heap global and import slot; disjoint complete ancestor and allocation storage; DF clear",
                "Successful stdcall API response preserves all modeled storage and nonvolatile registers",
            ],
            not_claimed=[
                "Real allocation effects, null or wrapping returns, allocation failures or retries, arbitrary aliasing, insertion or tree topology changes",
                "Full game equivalence or accounting promotion",
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
        "sealed factory differs",
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
        "exact factory differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
