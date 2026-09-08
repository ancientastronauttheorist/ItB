"""Exact call-free unsigned byte-string comparison with independent ordered reads."""

from __future__ import annotations
import hashlib, json
import capstone
from src.observatory.native_lua_cclosure_setfield_publications import (
    _atlas_functions,
    _decode_range,
)
from pathlib import Path
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

ANALYSIS_KIND = "pe_native_tree_key_compare_conformance"
SEALED_SHA256 = "6d70712cc9751139147a5ea42940f20ccdf727d8d59274bed5acd7af1a099815"
SOURCE_PINS = {"program_facts": append.SOURCE_PINS["program_facts"]}
START, END = 0x2E76A0, 0x2E76E9
STACK, LEFT, RIGHT, RETURN = 0x02000000, 0x01000000, 0x06000000, 0x04000000
STACK_TEMPLATE = bytes(((i * 43) ^ (i >> 6) ^ 0xC7) & 255 for i in range(0x4000))


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def compare_spec(left, right):
    _require(
        type(left) is bytes and type(right) is bytes and 0 in left and 0 in right,
        "readable terminated byte strings required",
    )
    _require(len(left) <= 256 and len(right) <= 256, "outside bounded string storage")
    lhs = left.split(b"\0", 1)[0]
    rhs = right.split(b"\0", 1)[0]
    signed = -1 if lhs < rhs else 1 if lhs > rhs else 0
    reads = []
    for i, (a, b) in enumerate(zip(left, right)):
        reads.extend(
            [
                dict(side="left", offset=i, value=a),
                dict(side="right", offset=i, value=b),
            ]
        )
        if a != b or a == 0:
            break
    return dict(
        less=int(lhs < rhs),
        signed=signed,
        ecx=signed & 0xFFFFFFFF,
        last_left=reads[-2]["value"],
        reads=reads,
        flags={-1: 0x84, 0: 0x44, 1: 0}[signed],
        flag_mask=0x8C5,
    )


def vectors():
    keys = [
        b"",
        b"a",
        b"b",
        b"aa",
        b"ab",
        b"ac",
        b"a\x7f",
        b"a\x80",
        b"\xff",
        b"a" * 31,
        b"a" * 32,
        b"a" * 64,
        b"a" * 64 + b"b",
    ]
    return [
        dict(
            left=list(l + b"\0\xa5"),
            right=list(r + b"\0\x5a"),
            alignment=a,
            frame_alignment=f,
            df=df,
        )
        for l in keys
        for r in keys
        for a in range(4)
        for f in (0, 1, 7, 15)
        for df in (0, 1)
    ]


def _fixture(vector):
    for k, limit in (("alignment", 4), ("frame_alignment", 16), ("df", 2)):
        _require(
            type(vector[k]) is int and 0 <= vector[k] < limit,
            "invalid comparator alignment or DF",
        )
    for k in ("left", "right"):
        _require(
            type(vector[k]) is list
            and all(type(b) is int and 0 <= b < 256 for b in vector[k]),
            "invalid byte storage",
        )
    relation = compare_spec(bytes(vector["left"]), bytes(vector["right"]))
    s = STACK + 0x2000 + vector["frame_alignment"]
    l = LEFT + 0x100 + vector["alignment"]
    r = RIGHT + 0x100 + (3 * vector["alignment"] + 1) % 4
    stack = bytearray(STACK_TEMPLATE)
    left = bytearray(((i * 19) ^ 0xA5) & 255 for i in range(0x1000))
    right = bytearray(((i * 31) ^ 0x5A) & 255 for i in range(0x1000))
    left[l - LEFT : l - LEFT + len(vector["left"])] = bytes(vector["left"])
    right[r - RIGHT : r - RIGHT + len(vector["right"])] = bytes(vector["right"])
    for address, value in ((s, RETURN), (s + 4, l), (s + 8, r)):
        stack[address - STACK : address - STACK + 4] = value.to_bytes(4, "little")
    regs = {
        r: (0x16273849 + i * 0x1010101 + vector["alignment"]) & 0xFFFFFFFF
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs["esp"] = s
    return dict(
        s=s,
        l=l,
        r=r,
        stack=bytes(stack),
        left=bytes(left),
        right=bytes(right),
        registers=regs,
        relation=relation,
    )


def _expected(fixture):
    s, l, r = (fixture[k] for k in ("s", "l", "r"))
    initial = fixture["registers"]
    rel = fixture["relation"]
    stack = bytearray(fixture["stack"])
    stack[s - 4 - STACK : s - STACK] = initial["ebp"].to_bytes(4, "little")
    events = [
        dict(access="write", address=s - 4, width=4, value=initial["ebp"]),
        dict(access="read", address=s + 8, width=4, value=r),
        dict(access="read", address=s + 4, width=4, value=l),
    ]
    events += [
        dict(
            access="read",
            address=(l if e["side"] == "left" else r) + e["offset"],
            width=1,
            value=e["value"],
        )
        for e in rel["reads"]
    ]
    events += [
        dict(access="read", address=s - 4, width=4, value=initial["ebp"]),
        dict(access="read", address=s, width=4, value=RETURN),
    ]
    return dict(
        stack=bytes(stack),
        events=events,
        registers=dict(
            initial,
            eax=rel["less"],
            ecx=rel["ecx"],
            edx=(initial["edx"] & 0xFFFFFF00) | rel["last_left"],
            esp=s + 12,
        ),
        flags=rel["flags"],
    )


def _run_case(code, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector)
    expected = _expected(fixture)
    s = fixture["s"]
    m = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page in (BASE + (START & ~0xFFF), LEFT, RIGHT, RETURN):
        m.mem_map(page, 0x1000)
    m.mem_map(STACK, 0x4000)
    m.mem_write(BASE + START, code)
    m.mem_write(STACK, fixture["stack"])
    m.mem_write(LEFT, fixture["left"])
    m.mem_write(RIGHT, fixture["right"])
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in fixture["registers"]}
    for r, value in fixture["registers"].items():
        m.reg_write(ids[r], value)
    m.reg_write(x.UC_X86_REG_EFLAGS, 0x246 | (vector["df"] << 10))
    allowed = {int(p["rva"], 16) for p in points}
    visited = []
    events = []

    def on_code(machine, address, size, user):
        pc = address - BASE
        _require(pc in allowed, "comparator escaped body")
        visited.append(f"0x{pc:08x}")
        if pc == START:
            if negative == "ancestor":
                machine.mem_write(
                    s + 12,
                    (
                        int.from_bytes(machine.mem_read(s + 12, 4), "little") ^ 1
                    ).to_bytes(4, "little"),
                )
            if negative == "source":
                machine.mem_write(fixture["l"] + len(vector["left"]) + 4, b"\x00")

    def memory(machine, access, address, size, value, user):
        _require(size in (1, 4), "unexpected comparator access width")
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
    m.emu_start(BASE + START, RETURN, count=2000)
    _require(m.reg_read(x.UC_X86_REG_EIP) == RETURN, "comparator did not return")
    actual = {r: m.reg_read(i) for r, i in ids.items()}
    flags = m.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        actual == expected["registers"]
        and flags & 0x8C5 == expected["flags"]
        and (flags >> 10) & 1 == vector["df"],
        "comparator registers or flags differ",
    )
    _require(events == expected["events"], "comparator ordered reads differ")
    _require(
        bytes(m.mem_read(STACK, 0x4000)) == expected["stack"],
        "comparator ancestor memory differs",
    )
    _require(
        bytes(m.mem_read(LEFT, 0x1000)) == fixture["left"]
        and bytes(m.mem_read(RIGHT, 0x1000)) == fixture["right"],
        "comparator source memory differs",
    )
    return dict(
        inputs=vector,
        registers=actual,
        flags=flags & 0xCC5,
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        stack_sha256=hashlib.sha256(expected["stack"]).hexdigest(),
    )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256, "executable differs")
    rows = _decode_body(data, image, sources["program_facts"], START)
    points = [_point(r) for r in rows]
    offset = image.rva_to_file_offset(START)
    code = data[offset : offset + END - START]
    _require(sum(p["size"] for p in points) == END - START, "comparator extent differs")
    caller_record = _atlas_functions(sources["program_facts"])[0x2E8300]
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    caller = [
        r
        for span in caller_record["ranges"]
        for r in _decode_range(
            data, image, int(span["start_rva"], 16), span["size"], decoder
        )
    ]
    _require(
        hashlib.sha256(b"".join(bytes(r.bytes) for r in caller)).hexdigest()
        == caller_record["body_sha256"],
        "comparator caller body differs",
    )
    calls = [
        r for r in caller if r.mnemonic == "call" and r.op_str == hex(BASE + START)
    ]
    _require(
        [r.address - BASE for r in calls]
        == [0x2E8375, 0x2E83A5, 0x2E83D2, 0x2E83ED, 0x2E842F, 0x2E8450],
        "comparator caller lineage differs",
    )
    observations = [_run_case(code, points, v) for v in vectors()]
    union = sorted({p for o in observations for p in o["trace_rvas"]})
    _require(set(union) == {p["rva"] for p in points}, "comparator coverage differs")
    controls = []
    for kind, message in (
        ("ancestor", "comparator ancestor memory differs"),
        ("source", "comparator source memory differs"),
    ):
        try:
            _run_case(code, points, vectors()[0], kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "comparator control failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("comparator mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=ids,
        build_identity=sources["program_facts"]["identity"],
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        body=dict(start_rva=f"0x{START:08x}", end_rva=f"0x{END:08x}", points=points),
        caller_lineage=dict(
            owner_rva="0x002e8300",
            calls=[_point(r) for r in calls],
            target_rva=f"0x{START:08x}",
        ),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=union,
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            instruction_bytes=len(code),
            executed_sites=len(union),
            less_cases=sum(o["registers"]["eax"] == 1 for o in observations),
            equal_cases=sum(o["registers"]["ecx"] == 0 for o in observations),
            greater_cases=sum(o["registers"]["ecx"] == 1 for o in observations),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Native call-free unsigned byte-string less comparator returns through RET8 with independently specified ordered reads",
            premises=[
                "Disjoint readable NUL-terminated byte storage of at most256bytes, protected ancestor, no asynchronous writes",
                "Both entry DF values are modeled and preserved; no null-pointer special case is inferred",
            ],
            not_claimed=[
                "Insertion behavior, locale or Unicode collation, missing terminators or arbitrary aliases",
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
        "sealed comparator differs",
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
        "exact comparator differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
