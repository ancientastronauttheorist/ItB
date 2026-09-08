"""Exact predecessor replay against an independent ordered traversal oracle."""

from __future__ import annotations
import hashlib, json
from pathlib import Path
from src.observatory import native_tree_predecessor_semantics as sem
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _load_executable,
    _point,
    _canonical_bytes,
    _canonical_sha256,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "pe_native_tree_predecessor_conformance"
SEALED_SHA256 = "be9b0a94dc4cb000ba2e7b87c5167e93b97ba83ca05c5ffe96f246ec7a493694"
START = 0x71850


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    return [
        dict(
            shape=shape,
            start=start,
            alignment=a,
            sentinel_byte=s,
            canonical_head=h,
            df=df,
        )
        for shape in sem.SHAPES
        for start in sorted(sem.tree_fixture(shape))
        for a in (range(16) if shape in ("balanced", "single", "empty") else (0, 7, 15))
        for s in (1, 128, 255)
        for h in (True, False)
        for df in (0, 1)
    ]


def oracle(vector, fixture):
    memory = dict(fixture["memory"])
    events = []
    slot = fixture["slot"]
    nodes = fixture["nodes"]

    def read(a, w=4):
        v = sum(memory[a + j] << (8 * j) for j in range(w))
        events.append(dict(access="read", address=a, width=w, value=v))
        return v

    def write(v):
        events.append(dict(access="write", address=slot, width=4, value=v))
        for j, b in enumerate(v.to_bytes(4, "little")):
            memory[slot + j] = b

    current = read(slot)
    flag = read(current + 13, 1)
    cursor = slot
    if flag:
        write(read(current + 8))
    else:
        cursor = read(current)
        flag = read(cursor + 13, 1)
        if not flag:
            child = read(cursor + 8)
            flag = read(child + 13, 1)
            while not flag:
                cursor = child
                child = read(cursor + 8)
                flag = read(child + 13, 1)
            write(cursor)
        else:
            cursor = read(current + 4)
            flag = read(cursor + 13, 1)
            while not flag:
                current = read(slot)
                left = read(cursor)
                if current != left:
                    break
                write(cursor)
                cursor = read(cursor + 4)
                flag = read(cursor + 13, 1)
            current = read(slot)
            flag = read(current + 13, 1)
            if not flag:
                write(cursor)
    read(fixture["stack"])
    # A separate recursive inorder list establishes the mathematical result.
    nil = next(a for a, n in nodes.items() if n["sentinel"])
    normal = [a for a in nodes if a != nil]
    ordered = []

    def visit(a):
        if a == nil:
            return
        visit(nodes[a]["left"])
        ordered.append(a)
        visit(nodes[a]["right"])

    if normal:
        visit(next(a for a in normal if nodes[a]["parent"] == nil))
    start = vector["start"]
    expected = (
        (ordered[-1] if ordered else nil)
        if start == nil
        else (ordered[ordered.index(start) - 1] if ordered.index(start) > 0 else nil)
    )
    canonical = nodes[nil]["right"] == (ordered[-1] if ordered else nil)
    result = sum(memory[slot + j] << (8 * j) for j in range(4))
    corollary = start != nil or canonical
    if corollary:
        _require(result == expected, "independent inorder result differs")
    regs = dict(fixture["registers"])
    regs.update(eax=slot, edx=slot, ecx=cursor, esp=fixture["stack"] + 4)
    flags = (
        (int(flag == 0) << 6)
        | ((flag >> 7) << 7)
        | (int(flag.bit_count() % 2 == 0) << 2)
    )
    return dict(
        memory=memory,
        events=events,
        registers=regs,
        flags=flags,
        corollary=corollary,
        result=result,
    )


def _run_case(code, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = sem.case_fixture(**vector)
    expected = oracle(vector, fixture)
    memory = fixture["memory"]
    pages = {a & ~0xFFF: bytearray(b"\xa5" * 0x1000) for a in memory}
    for a, v in memory.items():
        pages[a & ~0xFFF][a & 0xFFF] = v
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, payload in pages.items():
        machine.mem_map(page, 0x1000)
        machine.mem_write(page, bytes(payload))
    for page in ((BASE + START) & ~0xFFF, fixture["return_address"] & ~0xFFF):
        machine.mem_map(page, 0x1000)
        machine.mem_write(page, b"\xcc" * 0x1000)
    if negative == "ancestor_write":
        altered = bytearray(code)
        altered[0x71896 - START + 1] &= ~8
        code = bytes(altered)
    machine.mem_write(BASE + START, code)
    ids = {
        name: getattr(x, "UC_X86_REG_" + name.upper()) for name in fixture["registers"]
    }
    for name, v in fixture["registers"].items():
        machine.reg_write(ids[name], v)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 2 | (vector["df"] << 10))
    allowed = {int(p["rva"], 16) for p in points}
    events = []
    visited = []

    def on_code(m, address, size, _):
        pc = address - BASE
        _require(pc in allowed, "predecessor escaped exact body")
        if negative == "return" and pc == 0x718AD:
            m.reg_write(x.UC_X86_REG_EAX, 0)
        visited.append(f"0x{pc:08x}")

    def on_memory(m, kind, at, width, value, _):
        _require(
            width in (1, 4) and all(at + j in memory for j in range(width)),
            "unmapped native access",
        )
        writing = kind == uc.UC_MEM_WRITE
        if writing:
            _require(at == fixture["slot"] and width == 4, "write escaped slot")
        events.append(
            dict(
                access="write" if writing else "read",
                address=at,
                width=width,
                value=(
                    value & ((1 << (width * 8)) - 1)
                    if writing
                    else int.from_bytes(m.mem_read(at, width), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    machine.emu_start(BASE + START, fixture["return_address"], count=4000)
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == fixture["return_address"],
        "predecessor failed to return",
    )
    _require(events == expected["events"], "ordered predecessor event oracle differs")
    regs = {name: machine.reg_read(reg) for name, reg in ids.items()}
    _require(regs == expected["registers"], "predecessor register oracle differs")
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        flags & 0x8D5 == expected["flags"] and (flags >> 10) & 1 == vector["df"],
        "predecessor flags or DF differ",
    )
    for a, v in expected["memory"].items():
        pages[a & ~0xFFF][a & 0xFFF] = v
    _require(
        all(bytes(machine.mem_read(p, 0x1000)) == bytes(v) for p, v in pages.items()),
        "whole page memory differs",
    )
    return dict(
        vector=vector,
        registers=regs,
        flags=flags & 0x8D5,
        df=vector["df"],
        inorder_corollary=expected["corollary"],
        result=expected["result"],
        visited=visited,
        events_sha256=_canonical_sha256(events),
    )


def _build_unsealed(executable, semantics):
    import capstone

    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(semantics) == sem.SEALED_SHA256, "semantic source differs"
    )
    data, image, digest = _load_executable(executable)
    _require(
        digest == EXE_SHA256
        and image.image_base == BASE
        and capstone.__version__ == "5.0.7",
        "exact build differs",
    )
    offset = image.rva_to_file_offset(START)
    code = data[offset : offset + 94]
    points = [
        _point(r)
        for r in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
            code, BASE + START
        )
    ]
    _require(
        points == semantics["body"]["points"] and len(points) == 38,
        "exact predecessor code differs",
    )
    cases = [_run_case(code, points, v) for v in vectors()]
    controls = []
    for name in ("ancestor_write", "return"):
        vector = dict(
            shape="left_chain",
            start=0x10000040,
            alignment=0,
            sentinel_byte=255,
            canonical_head=True,
            df=1,
        )
        try:
            _run_case(code, points, vector, name)
        except ConformanceError as exc:
            _require(
                ("register oracle" if name == "return" else "ordered predecessor")
                in str(exc),
                "unrelated mutation failure",
            )
            controls.append(dict(name=name, rejected=True))
        else:
            raise ConformanceError("mutation accepted")
    union = sorted({p for c in cases for p in c["visited"]})
    _require(
        union == semantics["model_evidence"]["instruction_union_rvas"],
        "native union differs",
    )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=semantics["build_identity"],
        source_semantics_sha256=sem.SEALED_SHA256,
        body=semantics["body"],
        vectors=vectors(),
        executed_rvas=union,
        observations_sha256=_canonical_sha256(cases),
        negative_controls=controls,
        emulator=dict(name="Unicorn", version="2.1.4", mode_bits=32),
        summary=dict(
            cases=len(cases),
            executed_sites=38,
            executed_bytes=94,
            inorder_cases=sum(c["inorder_corollary"] for c in cases),
            negative_controls=2,
            calls=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact call-free predecessor matches independent ordered traversal and recursive inorder oracles, all GPRs, defined arithmetic flags, DF and whole mapped pages",
            premises=[
                "Stable finite tree topology, disjoint node records iterator slot and return word; shared declarative fixture layout only",
                "Full sixteen frame alignments for balanced single and empty fixtures, three representative alignments for deeper chains and zigzag; three nonzero nil byte values and both DF settings",
            ],
            event_policy="Native byte and DWORD reads, every iterator slot write and RET read are compared in order; NOP emits no access",
            not_claimed=[
                "Hardware or game execution, C++ underflow validity, malformed or aliased topology, key ordering, insertion composition or accounting promotion"
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, semantics):
    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(semantics) == sem.SEALED_SHA256
        and evidence["source_semantics_sha256"] == sem.SEALED_SHA256,
        "sealed predecessor replay differs",
    )
    _assert_publication_safe(evidence)
    return dict(
        status="structurally_verified",
        evidence_sha256=SEALED_SHA256,
        summary=evidence["summary"],
    )


def build_conformance(executable, semantics):
    result = _build_unsealed(executable, semantics)
    validate_structure(result, semantics)
    return result


def validate_conformance(executable, evidence, semantics):
    validate_structure(evidence, semantics)
    _require(
        _canonical_bytes(build_conformance(executable, semantics))
        == _canonical_bytes(evidence),
        "exact predecessor replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
