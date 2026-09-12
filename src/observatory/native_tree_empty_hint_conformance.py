"""Native empty-tree hint insertion with normal SEH registration and return."""

from __future__ import annotations
import hashlib, json
from pathlib import Path
import capstone
from src.observatory import native_tree_balancing_conformance as balancing
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
ANALYSIS_KIND = "pe_native_tree_empty_hint_conformance"
SEALED_SHA256 = "eda3e3b090fe4b36b40b2158c3c65767f3604b40574f3a89244c4995a4fde0bf"
SOURCE_PINS = {
    "program_facts": balancing.SOURCE_PINS["program_facts"],
    "balancing": (balancing.ANALYSIS_KIND, balancing.SEALED_SHA256),
    "cookie_return": (cookie_return.ANALYSIS_KIND, cookie_return.SEALED_SHA256),
}
START = 0x2E8300
RANGES = [
    (0x2E8300, 0x2E8364),
    (0x2E84C0, 0x2E84DE),
    (0x7D0A0, 0x7D294),
    (0x3574CA, 0x3574D5),
]
COOKIE = cookie_return.COOKIE
OUTPUT = balancing.OUTPUT
ConformanceError = balancing.ConformanceError
_require = balancing._require


def vectors():
    return [
        dict(
            node_alignment=n,
            frame_alignment=f,
            df=df,
            previous_seh=seh,
            cookie=cookie,
            nil_marker=nil,
        )
        for n in (0, 1, 7, 15, 31)
        for f in (0, 1, 7, 15)
        for df in (0, 1)
        for seh in (0, 0xFFFFFFFF, 0x18001000, 0x87654321)
        for cookie in (0, 1, 0x80000000, 0xFFFFFFFF, 0xA12598FD)
        for nil in (1, 255)
    ]


def _fixture(vector):
    for k in ("previous_seh", "cookie"):
        _require(
            type(vector[k]) is int and 0 <= vector[k] < 2**32, "invalid hint scalar"
        )
    v = dict(
        keys=[],
        key=0,
        node_alignment=vector["node_alignment"],
        tree_alignment=0,
        frame_alignment=vector["frame_alignment"],
        df=vector["df"],
        nil_marker=vector["nil_marker"],
    )
    f = balancing._fixture(v)
    pages = {p: bytearray(v) for p, v in f["pages"].items()}
    pages[0] = bytearray(b"\x6d" * 0x1000)
    pages[COOKIE & ~0xFFF] = bytearray(b"\xb7" * 0x1000)

    def put(a, v):
        for j, b in enumerate(v.to_bytes(4, "little")):
            pages[(a + j) & ~0xFFF][(a + j) & 0xFFF] = b

    put(0, vector["previous_seh"])
    put(COOKIE, vector["cookie"])
    put(f["s"] + 8, 0xDEADA000)
    put(f["s"] + 12, 0xDEADB000)
    put(f["s"] + 16, f["node"])
    f["pages"] = {p: bytes(v) for p, v in pages.items()}
    f["child_vector"] = v
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
    _require(read(attachment.TREE + 4) == 0, "empty tree required")
    write(h - 40, OUTPUT)
    write(h - 32, n)
    write(h - 48, n)
    write(h - 72, n)
    write(h - 76, n)
    head = read(attachment.TREE)
    write(h - 80, head)
    write(h - 84, 1)
    write(h - 88, OUTPUT)
    write(h - 92, BASE + 0x2E835D)
    child = dict(
        fixture,
        s=h - 92,
        selector=1,
        pages={p: bytes(v) for p, v in pages.items()},
        registers=dict(
            entry,
            eax=attachment.TREE,
            ecx=attachment.TREE,
            ebx=OUTPUT,
            ebp=h - 4,
            esp=h - 92,
        ),
    )
    expected = balancing._expected(fixture["child_vector"], child)
    _require(
        expected["endpoint"] == BASE + 0x2E835D
        and expected["registers"]["esp"] == h - 68,
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
    regs = dict(entry, eax=OUTPUT, ecx=restored, esp=h + 20)
    return dict(
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        flags=0x44,
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
        _require(pc in allowed, "empty hint escaped selected path")
        visited.append(f"0x{pc:08x}")
        if pc == START:
            at = (
                s + 8
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
    m.emu_start(BASE + START, 0, count=300)
    actual = {r: m.reg_read(i) for r, i in ids.items()}
    flags = m.reg_read(x.UC_X86_REG_EFLAGS)
    if negative == "cookie":
        _require(
            m.reg_read(x.UC_X86_REG_EIP) == BASE + 0x3574D5,
            "cookie control failed at an unrelated endpoint",
        )

    _require(
        m.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "empty hint endpoint differs",
    )
    _require(
        actual == expected["registers"]
        and flags & 0x8D5 == expected["flags"] & 0x8D5
        and (flags >> 10) & 1 == vector["df"],
        "empty hint registers or flags differ",
    )
    _require(events == expected["events"], "empty hint ordered events differ")
    _require(
        all(
            bytes(m.mem_read(p, 0x1000)) == expected["pages"][p]
            for p in (attachment.STACK, attachment.STACK + 0x1000)
        ),
        "empty hint ancestor memory differs",
    )
    _require(
        all(
            bytes(m.mem_read(p, 0x1000)) == payload
            for p, payload in expected["pages"].items()
            if p not in (attachment.STACK, attachment.STACK + 0x1000)
        ),
        "empty hint protected memory differs",
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
    _require(
        set(union)
        >= {p["rva"] for p in points if not 0x7D0A0 <= int(p["rva"], 16) < 0x7D294},
        "new hint or checker site coverage differs",
    )
    controls = []
    for kind, message in (
        ("ancestor", "empty hint ancestor memory differs"),
        ("padding", "empty hint protected memory differs"),
        ("seh", "empty hint protected memory differs"),
        ("cookie", "empty hint endpoint differs"),
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
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Native empty-tree hint insertion through real attachment and normal cookie return with complete normal exception-registration restoration",
            premises=[
                "Disjoint fresh node and output with initially empty canonical tree",
                "Synthetic flat FS registration page and arbitrary saved registration head; stored handler address never dereferenced",
                "Stable cookie global matching recovered local value; candidate and key-field argument pointees are unmapped and unread",
            ],
            not_claimed=[
                "Exception delivery or unwinding, nonempty hint dispatch, fallback wrapper, cookie failure implementation or outer construction composition",
                "Real Windows TEB or hardware execution and whole-game accounting promotion",
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
