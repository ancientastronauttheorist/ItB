"""Native attachment, one red-uncle recoloring and the real return."""

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

ANALYSIS_KIND = "pe_native_tree_recolor_return_conformance"
SEALED_SHA256 = "5a17fee37ae6ae5d545d70e8268ae80b8b073321bb521339ec8cf989b5a6f6f3"
SOURCE_PINS = dict(
    attachment.SOURCE_PINS,
    attachment=(attachment.ANALYSIS_KIND, attachment.SEALED_SHA256),
)
START = attachment.START
RANGES = [(START, 0x7D122), (0x7D1C0, 0x7D1E3), (0x7D272, 0x7D294)]
OUTPUT = 0x20000100
ConformanceError = attachment.ConformanceError
_require = attachment._require


def vectors():
    return [
        dict(
            profile=p,
            count=3,
            selector=int(p.endswith("left")),
            node_alignment=n,
            frame_alignment=f,
            df=df,
            head_color=c,
        )
        for p in ("min_left", "min_right", "max_left", "max_right")
        for n in (0, 1, 7, 15, 31)
        for f in (0, 1, 7, 15)
        for df in (0, 1)
        for c in (1, 255)
    ]


def _fixture(vector):
    _require(
        vector["profile"] in ("min_left", "min_right", "max_left", "max_right")
        and type(vector["head_color"]) is int
        and vector["head_color"] in (1, 255),
        "recolor fixture differs",
    )
    f = attachment._fixture(vector)
    pages = {p: bytearray(v) for p, v in f["pages"].items()}
    pages[OUTPUT & ~0xFFF] = bytearray(b"\xa5" * 0x1000)
    for p, c in (
        (attachment.HEAD, vector["head_color"]),
        (attachment.ROOT, 1),
        (attachment.LEFT, 0),
        (attachment.RIGHT, 0),
    ):
        pages[p & ~0xFFF][(p & 0xFFF) + 12] = c
    f["pages"] = {p: bytes(v) for p, v in pages.items()}
    return f


def color_invariants(pages, node_addresses):
    """Validate rooted colored topology, independently of native event equations."""

    def read(a, w=4):
        return sum(
            pages[(a + j) & ~0xFFF][(a + j) & 0xFFF] << (8 * j) for j in range(w)
        )

    nodes = set(node_addresses)
    head = attachment.HEAD
    seen = set()
    _require(
        len(nodes) == len(node_addresses) and head not in nodes,
        "invalid node partition",
    )
    _require(
        read(head + 12, 1) == 1 and read(head + 13, 1) != 0,
        "canonical black sentinel required",
    )
    root = read(head + 4)
    _require(root in nodes and read(root + 12, 1) == 1, "root must be black")

    def visit(n, parent):
        if n == head:
            return 1
        _require(n in nodes and n not in seen, "cycle sharing or unknown child")
        seen.add(n)
        _require(
            read(n + 4) == parent and read(n + 13, 1) == 0,
            "parent or nil metadata differs",
        )
        c = read(n + 12, 1)
        _require(c in (0, 1), "noncanonical color")
        left, right = read(n), read(n + 8)
        if c == 0:
            _require(
                read(left + 12, 1) == 1 and read(right + 12, 1) == 1,
                "red parent violation",
            )
        l, r = visit(left, n), visit(right, n)
        _require(l == r, "unequal black height")
        return l + c

    height = visit(root, head)
    _require(
        seen == nodes and read(attachment.TREE + 4) == len(nodes),
        "membership or count differs",
    )
    return dict(nodes=len(nodes), black_height=height)


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

    _require(read(n + 4) == parent and read(parent + 12, 1) == 0, "red parent required")
    write(s - 16, fixture["registers"]["esi"])
    p = read(n + 4)
    g = read(p + 4)
    uncle = read(g)
    if p == uncle:
        uncle = read(g + 8)
    _require(read(uncle + 12, 1) == 0, "red uncle required")
    write(p + 12, 1, 1)
    write(uncle + 12, 1, 1)
    p = read(n + 4)
    g = read(p + 4)
    write(g + 12, 0, 1)
    p = read(n + 4)
    cursor = read(p + 4)
    final_parent = read(cursor + 4)
    color = read(final_parent + 12, 1)
    _require(color != 0, "second iteration excluded")
    read(s - 16)
    head = read(attachment.TREE)
    read(s - 12)
    root = read(head + 4)
    write(root + 12, 1, 1)
    _require(read(s + 4) == OUTPUT, "output slot differs")
    write(OUTPUT, n)
    read(s - 8)
    read(s - 4)
    endpoint = read(s)
    regs = dict(
        fixture["registers"], eax=OUTPUT, ecx=final_parent, edx=uncle, esp=s + 24
    )
    flags = ((color >> 7) << 7) | (int(color.bit_count() % 2 == 0) << 2)
    if vector["head_color"] == 1:
        color_invariants(
            fixture["pages"], [attachment.ROOT, attachment.LEFT, attachment.RIGHT]
        )
        color_invariants(pages, [attachment.ROOT, attachment.LEFT, attachment.RIGHT, n])
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
        sum(r.size for r in selected) == 199,
        "bounded return extent differs",
    )
    code = []
    for a, b in RANGES:
        o = image.rva_to_file_offset(a)
        code.append((a, data[o : o + b - a]))
    observations = [_run_case(code, points, v) for v in vectors()]
    union = sorted({p for o in observations for p in o["trace_rvas"]})
    _require(
        set(union)
        >= {p["rva"] for p in points if int(p["rva"], 16) >= attachment.STOP},
        "recolor coverage differs",
    )
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
            instruction_bytes=199,
            static_sites=len(points),
            executed_sites=len(union),
            returned_cases=len(observations),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Native accepted attachment through exactly one red-uncle recoloring and RET20",
            premises=[
                "Three existing nodes with black root with two red children, fresh disjoint red leaf attached to one of four child positions",
                "Head color one or255; one is canonical black and255 is only a numeric nonzero-branch case",
                "Full ancestor, output, topology and node pages checked; both DF values, five node and four frame alignments",
            ],
            registers="EAX output slot, ECX head, EDX uncle; nonvolatile registers restored and ESP entry plus24",
            flags="All arithmetic flags from final CMP8 head color with zero; DF preserved",
            not_claimed=[
                "Repeated recoloring, rotations, size failure or general balancing-loop theorem",
                "Sorted key order, hint caller composition, actual hardware execution or accounting promotion",
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
