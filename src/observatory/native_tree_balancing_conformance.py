"""Native accepted tree insertion with canonical recoloring and rotations."""

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
from src.observatory import native_tree_balancing_semantics as model
from functools import lru_cache
from itertools import permutations

ANALYSIS_KIND = "pe_native_tree_balancing_conformance"
SEALED_SHA256 = "58b41864a6b9f486adf139102e08bdb8d4620660963998bd43675800265b31ce"
SOURCE_PINS = dict(
    attachment.SOURCE_PINS,
    attachment=(attachment.ANALYSIS_KIND, attachment.SEALED_SHA256),
    semantics=(model.ANALYSIS_KIND, model.SEALED_SHA256),
)
START = attachment.START
RANGES = [(START, 0x7D294)]
CANONICAL_UNREACHABLE = {0x7D149, 0x7D14C, 0x7D159, 0x7D209, 0x7D20C, 0x7D21B}
OUTPUT = 0x20000100
ConformanceError = attachment.ConformanceError
_require = attachment._require


def _shuffle(size, seed):
    result = list(range(size))
    state = seed
    for i in range(size - 1, 0, -1):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        j = state % (i + 1)
        result[i], result[j] = result[j], result[i]
    return result


def vectors():
    sequences = [list(p) for n in range(1, 7) for p in permutations(range(n))]
    longs = [
        list(range(256)),
        list(reversed(range(256))),
        [v for i in range(128) for v in (i, 255 - i)],
        [int(f"{i:08b}"[::-1], 2) for i in range(256)],
    ]
    longs += [
        _shuffle(256, seed)
        for seed in (1, 7, 31, 127, 255, 65537, 0x12345678, 0xFEDCBA98)
    ]
    for seq in longs:
        for n in list(range(1, 33)) + [48, 64, 96, 128, 192, 256]:
            sequences.append(seq[:n])
    return [
        dict(
            keys=seq[:-1],
            key=seq[-1],
            node_alignment=(0, 1, 7, 15, 31)[i % 5],
            tree_alignment=(0, 1, 7, 15)[(i // 5) % 4],
            frame_alignment=(0, 1, 7, 15)[(i // 20) % 4],
            df=i % 2,
            nil_marker=(1, 128, 255)[(i // 80) % 3],
        )
        for i, seq in enumerate(sequences)
    ]


@lru_cache(maxsize=8192)
def _base_tree(keys):
    if not keys:
        return dict(root=None, nodes=[])
    return model.insert(_base_tree(keys[:-1]), keys[-1])["tree"]


def _fixture(vector):
    for k, limit in (
        ("node_alignment", 32),
        ("tree_alignment", 16),
        ("frame_alignment", 16),
        ("df", 2),
        ("nil_marker", 256),
    ):
        _require(
            type(vector[k]) is int and 0 <= vector[k] < limit,
            "invalid fixture alignment or flag",
        )
    _require(
        vector["nil_marker"] != 0
        and type(vector["keys"]) is list
        and len(vector["keys"]) <= 255,
        "invalid fixture size or nil marker",
    )
    _require(
        all(type(k) is int and 0 <= k < 2**32 for k in vector["keys"]),
        "invalid abstract keys",
    )
    tree = _base_tree(tuple(vector["keys"]))
    result = model.insert(tree, vector["key"])
    s = attachment.STACK + 0x1000 + vector["frame_alignment"]
    new = attachment.DATA + 0x100 + vector["node_alignment"]
    addresses = [
        attachment.ROOT + i * 32 + vector["tree_alignment"]
        for i in range(len(tree["nodes"]))
    ] + [new]
    at = lambda i: attachment.HEAD if i is None else addresses[i]
    pages = {}

    def ensure(a):
        page = a & ~0xFFF
        if page not in pages:
            pages[page] = bytearray(b"\xa5" * 0x1000)

    def put(a, v, w=4):
        for j, b in enumerate(v.to_bytes(w, "little")):
            ensure(a + j)
            pages[(a + j) & ~0xFFF][(a + j) & 0xFFF] = b

    for a in (
        attachment.STACK,
        attachment.STACK + 0x1000,
        attachment.TREE,
        OUTPUT,
        new,
    ):
        ensure(a)
    regs = {
        r: 0x16273849 + i * 0x1010101 + vector["frame_alignment"]
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs.update(ecx=attachment.TREE, esp=s)
    parent = None
    cursor = tree["root"]
    left = False
    while cursor is not None:
        parent = cursor
        left = vector["key"] < tree["nodes"][cursor]["key"]
        cursor = tree["nodes"][cursor]["left" if left else "right"]
    for i, node in enumerate(tree["nodes"]):
        a = addresses[i]
        for off, name in ((0, "left"), (4, "parent"), (8, "right")):
            put(a + off, at(node[name]))
        put(a + 12, node["color"], 1)
        put(a + 13, 0, 1)
        put(a + 16, node["key"])
        put(a + 20, 0x75310000 + i)
    for off in (0, 4, 8):
        put(new + off, attachment.HEAD)
    put(new + 12, 0, 2)
    put(new + 16, vector["key"])
    put(new + 20, 0x87654321)
    root = tree["root"]
    minimum = (
        min(range(len(tree["nodes"])), key=lambda i: tree["nodes"][i]["key"])
        if tree["nodes"]
        else None
    )
    maximum = (
        max(range(len(tree["nodes"])), key=lambda i: tree["nodes"][i]["key"])
        if tree["nodes"]
        else None
    )
    for off, value in ((0, at(minimum)), (4, at(root)), (8, at(maximum))):
        put(attachment.HEAD + off, value)
    put(attachment.HEAD + 12, 1, 1)
    put(attachment.HEAD + 13, vector["nil_marker"], 1)
    put(attachment.TREE, attachment.HEAD)
    put(attachment.TREE + 4, len(tree["nodes"]))
    for a, v in (
        (s, 0x44556677),
        (s + 4, OUTPUT),
        (s + 8, int(left)),
        (s + 12, at(parent)),
        (s + 16, new + 16),
        (s + 20, new),
    ):
        put(a, v)
    return dict(
        s=s,
        node=new,
        parent=at(parent),
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        relation=attachment.guard_spec(len(tree["nodes"])),
        selector=int(left),
        tree=tree,
        result=result,
        addresses=addresses,
    )


def _output_slot(fixture, live_start, live_end):
    output = fixture.get("output", OUTPUT)
    _require(type(output) is int and 0 <= output <= 0xFFFFFFFC, "invalid output slot")
    _require(
        all((output + i) & ~0xFFF in fixture["pages"] for i in range(4)),
        "unmapped output slot",
    )
    ranges = [
        (live_start, live_end),
        (attachment.TREE, attachment.TREE + 8),
        (attachment.HEAD, attachment.HEAD + 24),
    ]
    ranges.extend((a, a + 24) for a in fixture["addresses"])
    _require(
        all(output + 4 <= lo or output >= hi for lo, hi in ranges),
        "output overlaps live storage",
    )
    return output


def _expected(vector, fixture):
    output = _output_slot(fixture, fixture["s"] - 16, fixture["s"] + 24)
    v = dict(count=len(fixture["tree"]["nodes"]), selector=fixture["selector"])
    initial = attachment._expected(v, fixture)
    pages = {p: bytearray(v) for p, v in initial["pages"].items()}
    events = list(initial["events"])
    s = fixture["s"]
    n = fixture["node"]
    features = []

    def read(a, w=4):
        value = sum(
            pages[(a + j) & ~0xFFF][(a + j) & 0xFFF] << (8 * j) for j in range(w)
        )
        events.append(dict(access="read", address=a, width=w, value=value))
        return value

    def write(a, value, w=4):
        events.append(dict(access="write", address=a, width=w, value=value))
        for j, b in enumerate(value.to_bytes(w, "little")):
            pages[(a + j) & ~0xFFF][(a + j) & 0xFFF] = b

    def rotate(x, left, probe, kind):
        child, mid = (8, 0) if left else (0, 8)
        y = read(x + child)
        middle = read(y + mid)
        write(x + child, middle)
        middle = read(y + mid)
        nil = read(middle + 13, 1)
        if nil == 0:
            write(middle + 4, x)
            features.append(kind + "_nonnil_transfer")
        q = read(x + 4)
        write(y + 4, q)
        head = read(attachment.TREE)
        root = read(head + 4)
        if x == root:
            write(head + 4, y)
            features.append(kind + "_root")
        else:
            q = read(x + 4)
            slot = probe if read(q + probe) == x else 8 - probe
            write(q + slot, y)
            features.append(kind + ("_left_child" if slot == 0 else "_right_child"))
        write(y + mid, x)
        write(x + 4, y)
        return y

    cursor = n
    parent = read(n + 4)
    color = read(parent + 12, 1)
    edx = fixture["registers"]["edx"]
    iterations = 0
    rotations = 0
    if color == 0:
        write(s - 16, fixture["registers"]["esi"])
        while True:
            iterations += 1
            _require(
                iterations <= len(fixture["tree"]["nodes"]) + 1,
                "finite ancestry bound exceeded",
            )
            p = read(cursor + 4)
            g = read(p + 4)
            u = read(g)
            left = p == u
            if left:
                u = read(g + 8)
            uncle_color = read(u + 12, 1)
            edx = u
            if uncle_color == 0:
                features.append("red_uncle")
                write(p + 12, 1, 1)
                write(u + 12, 1, 1)
                p = read(cursor + 4)
                g = read(p + 4)
                write(g + 12, 0, 1)
                p = read(cursor + 4)
                cursor = read(p + 4)
            else:
                inner = read(p + (8 if left else 0))
                if cursor == inner:
                    cursor = p
                    rotate(
                        cursor,
                        left,
                        0 if left else 8,
                        "left_triangle" if left else "right_triangle",
                    )
                    rotations += 1
                p = read(cursor + 4)
                write(p + 12, 1, 1)
                p = read(cursor + 4)
                g = read(p + 4)
                write(g + 12, 0, 1)
                p = read(cursor + 4)
                g = read(p + 4)
                edx = g
                rotate(
                    g, not left, 8 if left else 0, "left_line" if left else "right_line"
                )
                rotations += 1
            parent = read(cursor + 4)
            color = read(parent + 12, 1)
            if color != 0:
                break
        read(s - 16)
    head = read(attachment.TREE)
    read(s - 12)
    root = read(head + 4)
    write(root + 12, 1, 1)
    _require(read(s + 4) == output, "result pointer differs")
    write(output, n)
    read(s - 8)
    read(s - 4)
    endpoint = read(s)
    _require(color == 1 and rotations <= 2, "canonical exit or rotation bound differs")
    regs = dict(fixture["registers"], eax=output, ecx=parent, edx=edx, esp=s + 24)
    expected = dict(
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        flags=0,
        endpoint=endpoint,
        features=features,
        iterations=iterations,
        rotations=rotations,
    )
    _require(
        expected["pages"] == _model_pages(fixture, expected),
        "independent red-black insertion differs",
    )
    return expected


def _model_pages(fixture, expected):
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    tree = fixture["result"]["tree"]
    addresses = fixture["addresses"]
    at = lambda i: attachment.HEAD if i is None else addresses[i]

    def put(a, value, w=4):
        for j, b in enumerate(value.to_bytes(w, "little")):
            pages[(a + j) & ~0xFFF][(a + j) & 0xFFF] = b

    for i, node in enumerate(tree["nodes"]):
        a = addresses[i]
        for off, name in ((0, "left"), (4, "parent"), (8, "right")):
            put(a + off, at(node[name]))
        put(a + 12, node["color"], 1)
    minimum = min(range(len(tree["nodes"])), key=lambda i: tree["nodes"][i]["key"])
    maximum = max(range(len(tree["nodes"])), key=lambda i: tree["nodes"][i]["key"])
    for off, value in ((0, at(minimum)), (4, at(tree["root"])), (8, at(maximum))):
        put(attachment.HEAD + off, value)
    put(attachment.TREE + 4, len(tree["nodes"]))
    for p in (attachment.STACK, attachment.STACK + 0x1000):
        pages[p] = bytearray(expected["pages"][p])
    put(fixture.get("output", OUTPUT), fixture["node"])
    return {p: bytes(v) for p, v in pages.items()}


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
        if negative == "saved_esi" and pc == 0x7D27F:
            saved = int.from_bytes(machine.mem_read(s - 16, 4), "little")
            machine.mem_write(s - 16, (saved ^ 1).to_bytes(4, "little"))
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
    m.emu_start(BASE + START, 0, count=256 + 64 * len(fixture["addresses"]))
    actual = {r: m.reg_read(i) for r, i in ids.items()}
    flags = m.reg_read(x.UC_X86_REG_EFLAGS)
    if negative == "saved_esi":
        _require(
            {r for r in actual if actual[r] != expected["registers"][r]} == {"esi"}
            and flags & 0x8D5 == expected["flags"],
            "saved ESI control failed incidentally",
        )
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
        features=expected["features"],
        iterations=expected["iterations"],
        rotations=expected["rotations"],
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
        sum(r.size for r in selected) == 500 and len(selected) == 181,
        "bounded return extent differs",
    )
    code = []
    for a, b in RANGES:
        o = image.rva_to_file_offset(a)
        code.append((a, data[o : o + b - a]))
    observations = [_run_case(code, points, v) for v in vectors()]
    union = sorted({p for o in observations for p in o["trace_rvas"]})
    expected_sites = {
        p["rva"] for p in points if int(p["rva"], 16) not in CANONICAL_UNREACHABLE
    }
    _require(set(union) == expected_sites, "canonical balancing coverage differs")
    controls = []
    for kind, message in [
        ("ancestor", "attachment ancestor memory differs"),
        ("padding", "attachment topology or padding differs"),
        ("saved_esi", "attachment registers or flags differ"),
    ]:
        try:
            sample = (
                next(
                    v for v in vectors() if _expected(v, _fixture(v))["rotations"] == 2
                )
                if kind == "saved_esi"
                else vectors()[0]
            )
            _run_case(code, points, sample, kind)
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
            instruction_bytes=500,
            static_sites=len(points),
            executed_sites=len(union),
            returned_cases=len(observations),
            max_iterations=max(o["iterations"] for o in observations),
            max_rotations=max(o["rotations"] for o in observations),
            feature_coverage=sorted({f for o in observations for f in o["features"]}),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact accepted attachment and canonical red-black rebalancing through RET20 for the sealed finite generated corpus",
            premises=[
                "Finite canonical rooted red-black trees generated by independent insertion semantics, distinct records and unique abstract keys",
                "Fresh disjoint red node and nil child, consistent count and head extrema, complete protected ancestor and output storage",
                "Independent abstract insertion agrees on complete tree node and output pages while ordered native equations separately check the entire ancestor",
            ],
            unreachable_rvas=[f"0x{r:08x}" for r in sorted(CANONICAL_UNREACHABLE)],
            not_claimed=[
                "Arbitrary malformed graphs or aliases, count failure, exceptions, hint dispatch or whole class-owner composition",
                "Native key comparison, actual hardware execution or whole-game accounting promotion",
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
