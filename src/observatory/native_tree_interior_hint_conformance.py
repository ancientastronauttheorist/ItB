"""Native interior lower-bound hint insertion through predecessor and rebalancing."""

from __future__ import annotations
import hashlib, json
from pathlib import Path
import capstone
from src.observatory import native_tree_balancing_conformance as balancing
from src.observatory import native_tree_key_compare_conformance as comparator
from src.observatory import native_tree_predecessor_conformance as predecessor
from src.observatory import native_lua_class_vector_return_conformance as cookie_return
from src.observatory.native_tree_key_compare_conformance import (
    _atlas_functions,
    _decode_range,
)
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

attachment = balancing.attachment
ANALYSIS_KIND = "pe_native_tree_interior_hint_conformance"
SEALED_SHA256 = "b4b8859192f3054ab33fbfe9e275e980c48571bb1dc57f88bb3a6aebd1876074"
SOURCE_PINS = {
    "program_facts": balancing.SOURCE_PINS["program_facts"],
    "balancing": (balancing.ANALYSIS_KIND, balancing.SEALED_SHA256),
    "comparator": (comparator.ANALYSIS_KIND, comparator.SEALED_SHA256),
    "predecessor": (predecessor.ANALYSIS_KIND, predecessor.SEALED_SHA256),
    "cookie_return": (cookie_return.ANALYSIS_KIND, cookie_return.SEALED_SHA256),
}
START = 0x2E8300
RANGES = [
    (0x2E8300, 0x2E834F),
    (0x2E8364, 0x2E8370),
    (0x2E8399, 0x2E839D),
    (0x2E83C9, 0x2E8428),
    (0x2E84BE, 0x2E84DE),
    (0x7D0A0, 0x7D294),
    (0x2E76A0, 0x2E76E9),
    (0x71850, 0x718AE),
    (0x3574CA, 0x3574D5),
]
COOKIE = cookie_return.COOKIE
OUTPUT = balancing.OUTPUT
ConformanceError = balancing.ConformanceError
_require = balancing._require


def vectors():
    cases = []
    for size in (2, 3, 4, 7, 15, 31, 63, 127, 255):
        seqs = [
            list(range(size)),
            list(reversed(range(size))),
            [i // 2 if i % 2 == 0 else size - 1 - i // 2 for i in range(size)],
            balancing._shuffle(size, 0x12345678),
        ]
        gaps = (
            list(range(1, size))
            if size <= 7
            else sorted({1, 2, size // 3, size // 2, size - 2, size - 1})
        )
        for seq in seqs:
            for gap in gaps:
                for n in (0, 7, 31):
                    for frame in (0, 15):
                        for df in (0, 1):
                            i = len(cases)
                            cases.append(
                                dict(
                                    keys=[2 * x + 1 for x in seq],
                                    key=2 * gap,
                                    mode="interior",
                                    node_alignment=n,
                                    tree_alignment=(0, 1, 7, 15)[i % 4],
                                    frame_alignment=frame,
                                    df=df,
                                    previous_seh=(
                                        0,
                                        0xFFFFFFFF,
                                        0x18001000,
                                        0x87654321,
                                    )[(i // 4) % 4],
                                    cookie=(0, 1, 0x80000000, 0xFFFFFFFF, 0xA12598FD)[
                                        (i // 16) % 5
                                    ],
                                    nil_marker=(1, 255)[(i // 80) % 2],
                                    string_alignment=(0, 1, 3)[(i // 160) % 3],
                                )
                            )
    return cases


def _fixture(vector):
    for k in ("previous_seh", "cookie"):
        _require(
            type(vector[k]) is int and 0 <= vector[k] < 2**32, "invalid hint scalar"
        )
    _require(
        vector["mode"] == "interior"
        and type(vector["string_alignment"]) is int
        and 0 <= vector["string_alignment"] < 4,
        "invalid extreme mode or string alignment",
    )
    _require(
        vector["keys"]
        and min(vector["keys"]) < vector["key"] < max(vector["keys"])
        and vector["key"] not in vector["keys"],
        "absent interior key required",
    )
    v = {
        k: vector[k]
        for k in (
            "keys",
            "key",
            "node_alignment",
            "tree_alignment",
            "frame_alignment",
            "df",
            "nil_marker",
        )
    }
    f = balancing._fixture(v)
    pages = {p: bytearray(v) for p, v in f["pages"].items()}
    for p, fill in (
        (0, 0x6D),
        (COOKIE & ~0xFFF, 0xB7),
        (0x11000000, 0x93),
        (0x12001000, 0x79),
    ):
        pages[p] = bytearray([fill] * 0x1000)

    def put(a, value, w=4):
        for j, b in enumerate(value.to_bytes(w, "little")):
            pages[(a + j) & ~0xFFF][(a + j) & 0xFFF] = b

    strings = {}
    for i, node in enumerate(f["tree"]["nodes"]):
        ptr = 0x11000000 + 16 * i + vector["string_alignment"]
        payload = f'{node["key"]:08x}'.encode() + b"\0"
        strings[ptr] = payload
        for j, b in enumerate(payload):
            put(ptr + j, b, 1)
        put(f["addresses"][i] + 16, ptr)
    ptr = 0x12001000 + vector["string_alignment"]
    payload = f'{vector["key"]:08x}'.encode() + b"\0"
    strings[ptr] = payload
    for j, b in enumerate(payload):
        put(ptr + j, b, 1)
    put(f["node"] + 16, ptr)
    put(0, vector["previous_seh"])
    put(COOKIE, vector["cookie"])
    index = min(
        (i for i, node in enumerate(f["tree"]["nodes"]) if node["key"] > vector["key"]),
        key=lambda i: f["tree"]["nodes"][i]["key"],
    )
    candidate = f["addresses"][index]
    put(f["s"] + 8, candidate)
    put(f["s"] + 12, f["node"] + 16)
    put(f["s"] + 16, f["node"])
    f["pages"] = {p: bytes(v) for p, v in pages.items()}
    f["child_vector"] = v
    f["strings"] = strings
    return f


def _expected(vector, fixture):
    h = fixture["s"]
    n = fixture["node"]
    entry = fixture["registers"]
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    events = []

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

    write(h - 4, entry["ebp"])
    write(h - 8, 0xFFFFFFFF)
    write(h - 12, 0x007D0EA0)
    previous = read(0)
    write(h - 16, previous)
    cookie = read(COOKIE)
    encoded = cookie ^ (h - 4)
    write(h - 24, encoded)
    for off, reg in ((-56, "ebx"), (-60, "esi"), (-64, "edi")):
        write(h + off, entry[reg])
    write(h - 68, encoded)
    write(0, h - 16)
    write(h - 20, h - 68)
    write(h - 36, attachment.TREE)
    _require(read(h + 16) == n and read(h + 4) == OUTPUT, "hint arguments differ")
    write(h - 8, 0)
    _require(
        read(attachment.TREE + 4) == len(fixture["tree"]["nodes"]), "tree count differs"
    )
    write(h - 40, OUTPUT)
    write(h - 32, n)
    write(h - 48, n)
    head = read(attachment.TREE)
    candidate = read(h + 8)
    keyfield = read(h + 12)
    minimum = read(head)
    _require(candidate not in (minimum, head), "interior lower-bound hint required")

    def compare_call(left, right, return_rva, old_edx):
        write(h - 80, BASE + return_rva)
        write(h - 84, h - 4)
        _require(
            read(h - 72) == right and read(h - 76) == left,
            "comparator arguments differ",
        )
        rel = comparator.compare_spec(
            fixture["strings"][left], fixture["strings"][right]
        )
        _require(rel["less"] == 1, "strict interior ordering required")
        for e in rel["reads"]:
            _require(
                read((left if e["side"] == "left" else right) + e["offset"], 1)
                == e["value"],
                "byte relation differs",
            )
        _require(
            read(h - 84) == h - 4 and read(h - 80) == BASE + return_rva,
            "comparator return frame differs",
        )
        return rel, (old_edx & 0xFFFFFF00) | rel["last_left"]

    right = read(candidate + 16)
    write(h - 72, right)
    query = read(keyfield)
    write(h - 76, query)
    write(h - 44, query)
    first, edx = compare_call(query, right, 0x2E83D7, entry["edx"])
    slot = h - 28
    write(slot, candidate)
    write(h - 72, BASE + 0x2E83E6)
    nodes = {}
    for i, node in enumerate(fixture["tree"]["nodes"]):
        at = lambda j: head if j is None else fixture["addresses"][j]
        nodes[fixture["addresses"][i]] = dict(
            left=at(node["left"]),
            right=at(node["right"]),
            parent=at(node["parent"]),
            sentinel=False,
        )

    def raw(a, w=4):
        return sum(
            pages[(a + j) & ~0xFFF][(a + j) & 0xFFF] << (8 * j) for j in range(w)
        )

    nodes[head] = dict(
        left=raw(head), right=raw(head + 8), parent=raw(head + 4), sentinel=True
    )
    memory = {
        a + j: pages[(a + j) & ~0xFFF][(a + j) & 0xFFF]
        for a in nodes
        for j in range(24)
    }
    for a in (slot, h - 72):
        for j in range(4):
            memory[a + j] = pages[(a + j) & ~0xFFF][(a + j) & 0xFFF]
    pf = dict(
        memory=memory,
        slot=slot,
        stack=h - 72,
        nodes=nodes,
        registers=dict(
            entry,
            eax=1,
            ecx=slot,
            edx=edx,
            ebx=query,
            esi=candidate,
            edi=head,
            ebp=h - 4,
            esp=h - 72,
        ),
    )
    pe = predecessor.oracle(dict(start=candidate), pf)
    pred = pe["result"]
    _require(
        pred != head
        and pe["registers"]["eax"] == slot
        and pe["registers"]["edx"] == slot
        and pe["registers"]["esp"] == h - 68,
        "predecessor frame or result differs",
    )
    for address, value in pe["memory"].items():
        pages[address & ~0xFFF][address & 0xFFF] = value
    events.extend(pe["events"])
    write(h - 72, query)
    _require(read(slot) == pred, "predecessor slot differs")
    left = read(pred + 16)
    write(h - 76, left)
    second, edx = compare_call(left, query, 0x2E83F2, pe["registers"]["edx"])
    pred_right = read(pred + 8)
    _require(read(h - 32) == n, "fresh node local differs")
    write(h - 72, n)
    write(h - 76, second["ecx"])
    nil = read(pred_right + 13, 1)
    _require(read(h - 36) == attachment.TREE, "tree local differs")
    if nil:
        _require(read(h - 40) == OUTPUT, "output local differs")
        parent = pred
        selector = 0
        write(h - 80, parent)
        write(h - 84, 0)
        write(h - 88, OUTPUT)
        child_return = BASE + 0x2E8412
    else:
        parent = candidate
        selector = 1
        write(h - 80, parent)
        _require(read(h - 40) == OUTPUT, "output local differs")
        write(h - 84, 1)
        write(h - 88, OUTPUT)
        child_return = BASE + 0x2E8423
    _require(
        parent == fixture["parent"] and selector == fixture["selector"],
        "selected nil-child insertion position differs",
    )
    write(h - 92, child_return)
    child = dict(
        fixture,
        s=h - 92,
        selector=selector,
        pages={p: bytes(v) for p, v in pages.items()},
        registers=dict(
            entry,
            eax=pred_right,
            ecx=attachment.TREE,
            edx=edx,
            ebx=pred,
            esi=OUTPUT,
            edi=head,
            ebp=h - 4,
            esp=h - 92,
        ),
    )
    expected = balancing._expected(fixture["child_vector"], child)
    _require(
        expected["endpoint"] == child_return and expected["registers"]["esp"] == h - 68,
        "child return frame differs",
    )
    pages = {p: bytearray(v) for p, v in expected["pages"].items()}
    events.extend(expected["events"])
    previous = read(h - 16)
    write(0, previous)
    for off in (-68, -64, -60, -56):
        read(h + off)
    restored = read(h - 24) ^ (h - 4)
    write(h - 56, BASE + 0x2E84D8)
    _require(read(COOKIE) == restored, "normal cookie equality required")
    _require(read(h - 56) == BASE + 0x2E84D8, "checker return differs")
    read(h - 4)
    endpoint = read(h)
    regs = dict(
        entry, eax=OUTPUT, ecx=restored, edx=expected["registers"]["edx"], esp=h + 20
    )
    return dict(
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        flags=0x44,
        endpoint=endpoint,
        child_features=expected["features"],
        child_iterations=expected["iterations"],
        child_rotations=expected["rotations"],
        predecessor_writes=sum(e["access"] == "write" for e in pe["events"]),
        selected_right=bool(nil),
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
    for page in sorted(
        {(BASE + a + i) & ~0xFFF for a, payload in code for i in range(len(payload))}
    ):
        m.mem_map(page, 0x1000)
        m.mem_write(page, b"\xcc" * 0x1000)
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
        if pc == 0x3574D5:
            machine.emu_stop()
            return
        if negative == "seh" and pc == 0x2E84CE:
            machine.mem_write(0, (vector["previous_seh"] ^ 1).to_bytes(4, "little"))
        if negative == "cookie" and pc == 0x3574CA:
            machine.mem_write(COOKIE, (vector["cookie"] ^ 1).to_bytes(4, "little"))
        _require(pc in allowed, "interior hint escaped selected path")
        visited.append(f"0x{pc:08x}")
        if pc == START:
            at = (
                s + 20
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
    m.emu_start(BASE + START, 0, count=1000)
    actual = {r: m.reg_read(i) for r, i in ids.items()}
    flags = m.reg_read(x.UC_X86_REG_EFLAGS)
    if negative == "cookie":
        _require(
            m.reg_read(x.UC_X86_REG_EIP) == BASE + 0x3574D5,
            "cookie control failed at an unrelated endpoint",
        )

    _require(
        m.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "interior hint endpoint differs",
    )
    _require(
        actual == expected["registers"]
        and flags & 0x8D5 == expected["flags"] & 0x8D5
        and (flags >> 10) & 1 == vector["df"],
        "interior hint registers or flags differ",
    )
    _require(events == expected["events"], "interior hint ordered events differ")
    _require(
        all(
            bytes(m.mem_read(p, 0x1000)) == expected["pages"][p]
            for p in (attachment.STACK, attachment.STACK + 0x1000)
        ),
        "interior hint ancestor memory differs",
    )
    _require(
        all(
            bytes(m.mem_read(p, 0x1000)) == payload
            for p, payload in expected["pages"].items()
            if p not in (attachment.STACK, attachment.STACK + 0x1000)
        ),
        "interior hint protected memory differs",
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
        child_entry=fixture["s"] - 92,
        seh_restored=True,
        child_features=expected["child_features"],
        child_iterations=expected["child_iterations"],
        child_rotations=expected["child_rotations"],
        predecessor_writes=expected["predecessor_writes"],
        selected_right=expected["selected_right"],
    )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256 and image.image_base == BASE, "exact PE differs")
    owner = _atlas_functions(sources["program_facts"])[START]
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    rows = [
        r
        for span in owner["ranges"]
        for r in _decode_range(
            data, image, int(span["start_rva"], 16), span["size"], decoder
        )
    ]
    _require(
        hashlib.sha256(b"".join(bytes(r.bytes) for r in rows)).hexdigest()
        == owner["body_sha256"],
        "complete discontiguous hint body differs",
    )
    witnessed = {p["rva"]: p for p in map(_point, rows)}
    child = [
        _point(r)
        for r in _decode_body(data, image, sources["program_facts"], 0x7D0A0)
        if r.address < BASE + 0x7D294
    ]
    _require(
        child == sources["balancing"]["body"]["points"], "balancing child body differs"
    )
    witnessed.update({p["rva"]: p for p in child})
    witnessed.update(
        {
            p["rva"]: p
            for p in sources["cookie_return"]["bodies"]["checker_normal"]["points"]
        }
    )
    compare_points = [
        _point(r)
        for r in _decode_body(data, image, sources["program_facts"], comparator.START)
    ]
    _require(
        compare_points == sources["comparator"]["body"]["points"],
        "comparator body differs",
    )
    witnessed.update({p["rva"]: p for p in compare_points})
    predecessor_points = [
        _point(r)
        for r in _decode_body(data, image, sources["program_facts"], predecessor.START)
    ]
    _require(
        predecessor_points == sources["predecessor"]["body"]["points"],
        "predecessor body differs",
    )
    witnessed.update({p["rva"]: p for p in predecessor_points})
    code = []
    points = []
    for a, b in RANGES:
        off = image.rva_to_file_offset(a)
        payload = data[off : off + b - a]
        part = [_point(r) for r in decoder.disasm(payload, BASE + a)]
        _require(
            sum(p["size"] for p in part) == b - a
            and all(witnessed.get(p["rva"]) == p for p in part),
            "selected native hint witness differs",
        )
        code.append((a, payload))
        points.extend(part)
    observations = [_run_case(code, points, v) for v in vectors()]
    union = sorted({p for o in observations for p in o["trace_rvas"]})
    required = {
        p["rva"]
        for p in points
        if any(
            a <= int(p["rva"], 16) < b
            for a, b in RANGES
            if 0x2E8300 <= a < 0x2E8500 or a == 0x3574CA
        )
    }
    _require(set(union) >= required, "interior hint or checker coverage differs")
    controls = []
    for kind, message in (
        ("ancestor", "interior hint ancestor memory differs"),
        ("padding", "interior hint protected memory differs"),
        ("seh", "interior hint protected memory differs"),
        ("cookie", "interior hint endpoint differs"),
    ):
        try:
            _run_case(code, points, vectors()[0], kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "hint control failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("hint mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=ids,
        build_identity=sources["program_facts"]["identity"],
        engine=dict(
            name="Unicorn",
            version="2.1.4",
            architecture="x86_32",
            fs_profile="Flat synthetic FS base zero with isolated mapped registration page",
        ),
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
            instruction_bytes=sum(len(p) for a, p in code),
            static_sites=len(points),
            executed_sites=len(union),
            normal_returns=len(observations),
            max_child_iterations=max(o["child_iterations"] for o in observations),
            max_child_rotations=max(o["child_rotations"] for o in observations),
            predecessor_max_writes=max(o["predecessor_writes"] for o in observations),
            predecessor_right_insertions=sum(o["selected_right"] for o in observations),
            candidate_left_insertions=sum(
                not o["selected_right"] for o in observations
            ),
            child_features=sorted(
                {f for o in observations for f in o["child_features"]}
            ),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Native absent interior lower-bound hinted insertion through both comparisons predecessor canonical rebalancing and normal registration and cookie return",
            premises=[
                "Canonical disjoint nonempty trees with fresh key strictly between existing keys and exact nonminimum lower-bound candidate",
                "Fixed-width hexadecimal strings preserve abstract key order; all node string output ancestor and registration pages checked",
                "Predecessor uses its independently sealed ordered oracle and recursive inorder corollary in the real caller slot",
            ],
            not_claimed=[
                "Arbitrary hints or equal keys, successor-side dispatch, fallback wrapper, exceptions or enclosing construction composition",
                "Native hardware execution or whole-game accounting promotion",
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
