"""Native attachment through the bounded black-parent return path."""

from __future__ import annotations
import hashlib, json
from pathlib import Path
from src.observatory import native_lua_class_vector_append_semantics as append
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

from src.observatory import native_tree_attachment_conformance as attachment

ANALYSIS_KIND = "pe_native_tree_attachment_return_conformance"
SEALED_SHA256 = "83b9768de14bc2b8d4e79a63e229f50fb1089d34a294867feea18543c20f7f1d"
SOURCE_PINS = dict(
    attachment.SOURCE_PINS,
    attachment=(attachment.ANALYSIS_KIND, attachment.SEALED_SHA256),
)
START = attachment.START
RANGES = [(START, 0x7D104), (0x7D280, 0x7D294)]
OUTPUT = 0x20000100
ConformanceError = attachment.ConformanceError
_require = attachment._require


def vectors():
    return [
        dict(
            profile=p,
            count=0 if p == "empty" else 1,
            selector=int(p == "root_left"),
            node_alignment=n,
            frame_alignment=f,
            df=df,
            parent_color=c,
        )
        for p in ("empty", "root_left", "root_right")
        for n in (0, 7, 31)
        for f in (0, 15)
        for df in (0, 1)
        for c in (1, 255)
    ]


def _fixture(vector):
    _require(
        vector["profile"] in ("empty", "root_left", "root_right")
        and type(vector["parent_color"]) is int
        and vector["parent_color"] in (1, 255),
        "black-parent fixture differs",
    )
    f = attachment._fixture(vector)
    pages = {p: bytearray(v) for p, v in f["pages"].items()}
    pages[OUTPUT & ~0xFFF] = bytearray(b"\xa5" * 0x1000)
    p = f["parent"] + 12
    pages[p & ~0xFFF][p & 0xFFF] = vector["parent_color"]
    f["pages"] = {p: bytes(v) for p, v in pages.items()}
    return f


def _expected(vector, fixture):
    expected = attachment._expected(vector, fixture)
    pages = {p: bytearray(v) for p, v in expected["pages"].items()}
    events = list(expected["events"])
    s = fixture["s"]
    n = fixture["node"]
    parent = fixture["parent"]

    def read(a, w=4):
        v = sum(pages[(a + j) & ~0xFFF][(a + j) & 0xFFF] << (8 * j) for j in range(w))
        events.append(dict(access="read", address=a, width=w, value=v))
        return v

    def write(a, v, w=4):
        events.append(dict(access="write", address=a, width=w, value=v))
        for j, b in enumerate(v.to_bytes(w, "little")):
            pages[(a + j) & ~0xFFF][(a + j) & 0xFFF] = b

    _require(read(n + 4) == parent, "joined parent differs")
    color = read(parent + 12, 1)
    _require(color != 0, "red parent excluded")
    head = read(attachment.TREE)
    read(s - 12)
    root = read(head + 4)
    write(root + 12, 1, 1)
    _require(read(s + 4) == OUTPUT, "output slot differs")
    write(OUTPUT, n)
    read(s - 8)
    read(s - 4)
    endpoint = read(s)
    regs = dict(fixture["registers"])
    regs.update(eax=OUTPUT, ecx=parent, esp=s + 24)
    flags = ((color >> 7) << 7) | (int(color.bit_count() % 2 == 0) << 2)
    return dict(
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        flags=flags,
        endpoint=endpoint,
        root=root,
    )


def _run_case(code, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector)
    expected = _expected(vector, fixture)
    s = fixture["s"]
    m = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, payload in fixture["pages"].items():
        m.mem_map(page, 0x1000)
        m.mem_write(page, payload)
    m.mem_map((BASE + START) & ~0xFFF, 0x1000)
    m.mem_write((BASE + START) & ~0xFFF, b"\xcc" * 0x1000)
    for address, payload in code:
        m.mem_write(BASE + address, payload)
    m.mem_map(expected["endpoint"] & ~0xFFF, 0x1000)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in fixture["registers"]}
    for r, value in fixture["registers"].items():
        m.reg_write(ids[r], value)
    m.reg_write(x.UC_X86_REG_EFLAGS, 0x246 | (vector["df"] << 10))
    allowed = {int(p["rva"], 16) for p in points}
    visited = []
    events = []

    def on_code(machine, address, size, user):
        if address == expected["endpoint"]:
            machine.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "attachment escaped prefix")
        visited.append(f"0x{pc:08x}")
        if pc == START:
            at = (
                s + 16
                if negative == "ancestor"
                else fixture["node"] + 14 if negative == "padding" else None
            )
            if at is not None:
                machine.mem_write(
                    at, bytes([int.from_bytes(machine.mem_read(at, 1), "little") ^ 1])
                )

    def memory(machine, access, address, size, value, user):
        _require(size in (1, 4), "unexpected attachment access width")
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
    m.emu_start(BASE + START, 0, count=150)
    actual = {r: m.reg_read(i) for r, i in ids.items()}
    flags = m.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        m.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "attachment endpoint differs",
    )
    _require(
        actual == expected["registers"]
        and flags & 0x8D5 == expected["flags"] & 0x8D5
        and (flags >> 10) & 1 == vector["df"],
        "attachment registers or flags differ",
    )
    _require(events == expected["events"], "attachment ordered events differ")
    _require(
        all(
            bytes(m.mem_read(p, 0x1000)) == expected["pages"][p]
            for p in (attachment.STACK, attachment.STACK + 0x1000)
        ),
        "attachment ancestor memory differs",
    )
    _require(
        all(
            bytes(m.mem_read(p, 0x1000)) == payload
            for p, payload in expected["pages"].items()
            if p not in (attachment.STACK, attachment.STACK + 0x1000)
        ),
        "attachment topology or padding differs",
    )
    return dict(
        inputs=vector,
        registers=actual,
        flags=flags & 0x8D5,
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        memory_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(v).hexdigest()
                for p, v in expected["pages"].items()
            }
        ),
        accepted=fixture["relation"]["accepted"],
    )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256 and image.image_base == BASE, "exact PE differs")
    rows = _decode_body(data, image, sources["program_facts"], START)
    prefix = [_point(r) for r in rows if r.address < BASE + attachment.STOP]
    _require(
        prefix == sources["attachment"]["body"]["points"],
        "attachment source body differs",
    )
    selected = [r for r in rows if any(a <= r.address - BASE < b for a, b in RANGES)]
    points = [_point(r) for r in selected]
    _require(
        sum(r.size for r in selected) == 120 and len(selected) == 48,
        "bounded return extent differs",
    )
    code = []
    for a, b in RANGES:
        o = image.rva_to_file_offset(a)
        code.append((a, data[o : o + b - a]))
    observations = [_run_case(code, points, v) for v in vectors()]
    union = sorted({p for o in observations for p in o["trace_rvas"]})
    controls = []
    for kind, message in [
        ("ancestor", "attachment ancestor memory differs"),
        ("padding", "attachment topology or padding differs"),
    ]:
        try:
            _run_case(code, points, vectors()[0], kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "control failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=ids,
        build_identity=sources["program_facts"]["identity"],
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        body=dict(
            ranges=[
                dict(start_rva=f"0x{a:08x}", end_rva=f"0x{b:08x}") for a, b in RANGES
            ],
            points=points,
        ),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=union,
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            instruction_bytes=120,
            static_sites=48,
            executed_sites=len(union),
            returned_cases=len(observations),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Native accepted attachment through black-parent bypass and RET20 with explicit output and root-color writes",
            premises=[
                "Sealed attachment fixture and independent prefix oracle joined to fresh ordered return equations",
                "Only empty and single-root left or right attachment profiles with parent color one or 255; result slot disjoint from complete ancestor tree and node storage",
                "Both DF values, three node alignments and two frame alignments; all data pages including padding preserved except specified native writes",
            ],
            registers="EAX returns output slot, ECX parent, EDX and ESI preserve and other nonvolatile registers restore; ESP is entry plus24",
            flags="Final CMP8 parent color with zero defines all arithmetic flags and preserves DF",
            not_claimed=[
                "Red-parent balancing, rotations, size-failure handling, general red-black invariants or caller insertion composition",
                "Game or hardware execution and accounting promotion",
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
        "sealed attachment differs",
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
        "exact attachment differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
