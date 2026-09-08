"""Native count guard and node attachment, stopping before balancing."""

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

ANALYSIS_KIND = "pe_native_tree_attachment_conformance"
SEALED_SHA256 = "7881aafd141fe910567f693c0dbabe8cc17dfc487905a8ac5f331efba21d319a"
SOURCE_PINS = {"program_facts": append.SOURCE_PINS["program_facts"]}
START, STOP, FAILURE = 0x7D0A0, 0x7D0F5, 0x7D294
LIMIT = 0x0AAAAAA9
STACK, TREE, HEAD, ROOT, LEFT, RIGHT, DATA = (
    0x30000000,
    0x10000000,
    0x10000100,
    0x10001000,
    0x10001040,
    0x10001080,
    0x06000000,
)


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def guard_spec(count):
    _require(type(count) is int and 0 <= count < 2**32, "invalid unsigned node count")
    return dict(accepted=count < LIMIT, flags=_sub_flags(count, LIMIT), flag_mask=0x8D5)


def vectors():
    profiles = [("empty", 0, s) for s in (0, 1, 128, 255)]
    profiles += [
        (name, 1 if name.startswith("root") else 3, s)
        for name in (
            "root_left",
            "root_right",
            "min_left",
            "max_right",
            "max_left",
            "min_right",
        )
        for s in ((1, 128, 255) if name.endswith("left") else (0,))
    ]
    return [
        dict(
            profile=name,
            count=count,
            selector=selector,
            node_alignment=a,
            frame_alignment=f,
            df=df,
        )
        for name, count, selector in profiles
        for a in (0, 1, 7, 15, 31)
        for f in (0, 1, 7, 15)
        for df in (0, 1)
    ] + [
        dict(
            profile="failure",
            count=count,
            selector=0,
            node_alignment=0,
            frame_alignment=f,
            df=df,
        )
        for count in (LIMIT, LIMIT + 1, 0x80000000, 0xFFFFFFFF)
        for f in (0, 1, 7, 15)
        for df in (0, 1)
    ]


def _fixture(vector):
    rel = guard_spec(vector["count"])
    name = vector["profile"]
    _require(
        name
        in (
            "empty",
            "root_left",
            "root_right",
            "min_left",
            "max_right",
            "max_left",
            "min_right",
            "failure",
        ),
        "invalid attachment profile",
    )
    for k, limit in (
        ("selector", 256),
        ("node_alignment", 32),
        ("frame_alignment", 16),
        ("df", 2),
    ):
        _require(
            type(vector[k]) is int and 0 <= vector[k] < limit,
            "invalid attachment selector or alignment",
        )
    _require(
        (name == "failure") == (not rel["accepted"]), "profile and count guard differ"
    )
    s = STACK + 0x1000 + vector["frame_alignment"]
    node = DATA + 0x100 + vector["node_alignment"]
    pages = {
        STACK: bytearray(b"\xa5" * 0x1000),
        STACK + 0x1000: bytearray(b"\xa5" * 0x1000),
        TREE: bytearray(b"\xa5" * 0x1000),
    }
    regs = {
        r: 0x16273849 + i * 0x1010101 + vector["frame_alignment"]
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs.update(ecx=TREE, esp=s)

    def put(address, value, width=4):
        for i, b in enumerate(value.to_bytes(width, "little")):
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = b

    put(TREE + 4, vector["count"])
    parent = None
    if rel["accepted"]:
        population = 0 if name == "empty" else 1 if name.startswith("root") else 3
        _require(
            vector["count"] == population,
            "accepted count must match fixture population",
        )
        _require(
            name == "empty" or bool(vector["selector"]) == name.endswith("left"),
            "selector and chosen child differ",
        )
        pages[ROOT & ~0xFFF] = bytearray(b"\xa5" * 0x1000)
        pages[DATA] = bytearray(
            ((i * 41) ^ (i >> 5) ^ 0x65) & 255 for i in range(0x1000)
        )
        parent = (
            HEAD
            if name == "empty"
            else (
                ROOT
                if name.startswith("root")
                else LEFT if name.startswith("min") else RIGHT
            )
        )
        minimum = HEAD if population == 0 else ROOT if population == 1 else LEFT
        maximum = HEAD if population == 0 else ROOT if population == 1 else RIGHT
        put(TREE, HEAD)
        put(HEAD, minimum)
        put(HEAD + 4, HEAD if population == 0 else ROOT)
        put(HEAD + 8, maximum)
        put(HEAD + 13, 1, 1)
        for at, par, l, r in (
            (
                ROOT,
                HEAD,
                HEAD if population == 1 else LEFT,
                HEAD if population == 1 else RIGHT,
            ),
            (LEFT, ROOT, HEAD, HEAD),
            (RIGHT, ROOT, HEAD, HEAD),
        ):
            put(at, l)
            put(at + 4, par)
            put(at + 8, r)
            put(at + 13, 0, 1)
        for off in (0, 4, 8):
            put(node + off, HEAD)
        put(node + 12, 0, 2)
        put(node + 16, 0x12001000)
        put(node + 20, 0)
        if parent != HEAD:
            child_offset = 0 if vector["selector"] else 8
            _require(
                int.from_bytes(
                    pages[parent & ~0xFFF][
                        (parent & 0xFFF)
                        + child_offset : (parent & 0xFFF)
                        + child_offset
                        + 4
                    ],
                    "little",
                )
                == HEAD,
                "chosen child must be sentinel",
            )
    for address, value in (
        (s, 0x44556677),
        (s + 4, 0x20000100),
        (s + 8, vector["selector"]),
        (s + 12, parent if parent is not None else 0xDEADF000),
        (s + 16, 0x12001000),
        (s + 20, node),
    ):
        put(address, value)
    return dict(
        s=s,
        node=node,
        parent=parent,
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        relation=rel,
    )


def _expected(vector, fixture):
    s = fixture["s"]
    node = fixture["node"]
    parent = fixture["parent"]
    initial = fixture["registers"]
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    events = []

    def event(access, address, value, width=4):
        events.append(dict(access=access, address=address, width=width, value=value))
        if access == "write":
            for i, b in enumerate(value.to_bytes(width, "little")):
                pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = b

    r = lambda a, v: event("read", a, v)
    w = lambda a, v: event("write", a, v)
    for off, reg in ((-4, "ebp"), (-8, "ebx"), (-12, "edi")):
        w(s + off, initial[reg])
    r(TREE + 4, vector["count"])
    regs = dict(initial, eax=vector["count"], edi=TREE, ebp=s - 4, esp=s - 12)
    flags = fixture["relation"]["flags"]
    endpoint = BASE + FAILURE
    if fixture["relation"]["accepted"]:
        r(s + 20, node)
        w(TREE + 4, vector["count"] + 1)
        r(s + 12, parent)
        w(node + 4, parent)
        r(TREE, HEAD)
        if parent == HEAD:
            w(HEAD + 4, node)
            r(TREE, HEAD)
            w(HEAD, node)
            r(TREE, HEAD)
            w(HEAD + 8, node)
            flags = _sub_flags(parent, HEAD)
        else:
            event("read", s + 8, vector["selector"], 1)
            offset = 0 if vector["selector"] else 8
            w(parent + offset, node)
            r(TREE, HEAD)
            old = int.from_bytes(
                pages[HEAD & ~0xFFF][
                    (HEAD & 0xFFF) + offset : (HEAD & 0xFFF) + offset + 4
                ],
                "little",
            )
            r(HEAD + offset, old)
            flags = _sub_flags(parent, old)
            if parent == old:
                w(HEAD + offset, node)
        regs.update(eax=parent, ecx=HEAD, ebx=node)
        endpoint = BASE + STOP
    return dict(
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        flags=flags,
        endpoint=endpoint,
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
    m.mem_write(BASE + START, code)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in fixture["registers"]}
    for r, value in fixture["registers"].items():
        m.reg_write(ids[r], value)
    m.reg_write(x.UC_X86_REG_EFLAGS, 0x246 | (vector["df"] << 10))
    allowed = {int(p["rva"], 16) for p in points}
    visited = []
    events = []

    def on_code(machine, address, size, user):
        if address in (BASE + STOP, BASE + FAILURE):
            machine.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "attachment escaped prefix")
        visited.append(f"0x{pc:08x}")
        if pc == START:
            at = (
                s + 4
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
    m.emu_start(BASE + START, 0, count=100)
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
            for p in (STACK, STACK + 0x1000)
        ),
        "attachment ancestor memory differs",
    )
    _require(
        all(
            bytes(m.mem_read(p, 0x1000)) == payload
            for p, payload in expected["pages"].items()
            if p not in (STACK, STACK + 0x1000)
        ),
        "attachment topology or padding differs",
    )
    return dict(
        inputs=vector,
        registers=actual,
        flags=flags & 0xCD5,
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
    _require(digest == EXE_SHA256, "executable differs")
    rows = _decode_body(data, image, sources["program_facts"], START)
    points = [_point(r) for r in rows if r.address < BASE + STOP]
    offset = image.rva_to_file_offset(START)
    code = data[offset : offset + STOP - START]
    _require(
        sum(p["size"] for p in points) == STOP - START, "attachment extent differs"
    )
    observations = [_run_case(code, points, v) for v in vectors()]
    union = sorted({p for o in observations for p in o["trace_rvas"]})
    _require(set(union) == {p["rva"] for p in points}, "attachment coverage differs")
    controls = []
    for kind, message in (
        ("ancestor", "attachment ancestor memory differs"),
        ("padding", "attachment topology or padding differs"),
    ):
        try:
            _run_case(code, points, vectors()[0], kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "attachment control failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("attachment mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=ids,
        build_identity=sources["program_facts"]["identity"],
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        body=dict(start_rva=f"0x{START:08x}", end_rva=f"0x{STOP:08x}", points=points),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=union,
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            instruction_bytes=len(code),
            executed_sites=len(union),
            accepted_attachments=sum(o["accepted"] for o in observations),
            size_failure_frontiers=sum(not o["accepted"] for o in observations),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Native node-count guard and attachment prefix updates count, parent link and head extrema, stopping before balancing or size-failure handling",
            premises=[
                "Accepted finite fixtures have zero, one or three existing nodes, correct head root and extrema, consistent count and a fresh disjoint sentinel-child node; chosen parent child is sentinel",
                "Disjoint ancestor and stable tree context; both DF values preserved; synthetic rejected counts require no node argument access",
            ],
            not_claimed=[
                "Balancing, node colors, sorted-key attachment correctness, failure deallocation or exception behavior",
                "Global tree validity beyond the specified attachment or whole-game accounting promotion",
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
