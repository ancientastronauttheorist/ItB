"""Exact class-vector owner return and caller-specific cookie failure boundary."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_lua_class_vector_append_semantics as append
from src.observatory import native_assertion_helper_return_tail as old_tail
from src.observatory.native_vector_deallocation_conformance import _sub_flags
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _load_executable,
    _point,
    _source_identity,
    _canonical_bytes,
    _canonical_sha256,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "pe_native_lua_class_vector_return_conformance"
SEALED_SHA256 = "29a519177fe92e7233cd81556f2b1ab6c3b08cb8136fc5463064d6c48805c060"
SOURCE_PINS = {
    "chain": append.SOURCE_PINS["chain"],
    "append": (append.ANALYSIS_KIND, append.SEALED_SHA256),
    "checker": old_tail.SOURCE_PINS["reused_check"],
    "prior_tail": (old_tail.ANALYSIS_KIND, old_tail.SEALED_SHA256),
}
STACK, RETURN = 0x02000000, 0x04000000
COOKIE = BASE + 0x493F28
ESCAPE = BASE + 0x357B6A
CONTINUATION = BASE + 0x2EB227
BODIES = {
    "epilogue": (0x2EB21A, 0x2EB22D),
    "checker_normal": (0x3574CA, 0x3574D5),
    "checker_escape": (0x3574D5, 0x3574DB),
}
STACK_TEMPLATE = bytes(((i * 43) ^ (i >> 6) ^ 0xC7) & 255 for i in range(0x4000))


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    return [
        dict(frame_alignment=f, cookie=c, global_delta=d, df=df, seed=seed)
        for f in range(16)
        for c in (0, 1, 0x6B8B4567, 0xFFFFFFFF)
        for d in (0, 1, 0x80000000, 0xFFFFFFFF)
        for df in (0, 1)
        for seed in (1, 7)
    ]


def return_spec(frame, cookie, current, *, return_address=RETURN):
    _require(type(frame) is int and 32 <= frame < 2**32 - 12, "invalid frame")
    _require(
        all(type(v) is int and 0 <= v < 2**32 for v in (cookie, current)),
        "invalid cookie word",
    )
    _require(
        type(return_address) is int and 0 <= return_address < 2**32,
        "invalid return address",
    )
    equal = cookie == current
    return dict(
        equal=equal,
        entry_esp=frame - 32,
        protected_cookie=frame - 4,
        checker_entry=frame - 24,
        continuation=CONTINUATION,
        final_esp=frame + 12 if equal else frame - 24,
        endpoint=return_address if equal else ESCAPE,
        flags=_sub_flags(cookie, current),
        flag_mask=0x8D5,
    )


def _fixture(vector):
    _require(
        type(vector["frame_alignment"]) is int and 0 <= vector["frame_alignment"] < 16,
        "invalid alignment",
    )
    _require(type(vector["df"]) is int and vector["df"] in (0, 1), "invalid DF")
    _require(type(vector["seed"]) is int and 0 <= vector["seed"] < 16, "invalid seed")
    _require(
        type(vector["global_delta"]) is int and 0 <= vector["global_delta"] < 2**32,
        "invalid global delta",
    )
    f = STACK + 0x2000 + vector["frame_alignment"]
    c = vector["cookie"]
    _require(type(c) is int and 0 <= c < 2**32, "invalid cookie word")
    current = (c + vector["global_delta"]) & 0xFFFFFFFF
    relation = return_spec(f, c, current)
    regs = {
        r: (0x16273849 + i * 0x1010101 + vector["seed"]) & 0xFFFFFFFF
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs.update(ebp=f, esp=f - 32)
    saved = {
        r: (0xA1B2C3D4 + i * 0x1010101 + vector["seed"]) & 0xFFFFFFFF
        for i, r in enumerate(("edi", "esi", "ebx", "ebp"))
    }
    stack = bytearray(STACK_TEMPLATE)
    for address, value in (
        (f - 32, saved["edi"]),
        (f - 28, saved["esi"]),
        (f - 24, saved["ebx"]),
        (f - 4, c ^ f),
        (f, saved["ebp"]),
        (f + 4, RETURN),
    ):
        stack[address - STACK : address - STACK + 4] = value.to_bytes(4, "little")
    globals = bytearray(0x1000)
    off = COOKIE & 0xFFF
    globals[off : off + 4] = current.to_bytes(4, "little")
    return dict(
        frame=f,
        cookie=c,
        current=current,
        relation=relation,
        registers=regs,
        saved=saved,
        stack=bytes(stack),
        globals=bytes(globals),
    )


def _expected(fixture):
    f = fixture["frame"]
    rel = fixture["relation"]
    saved = fixture["saved"]
    regs = dict(fixture["registers"])
    stack = bytearray(fixture["stack"])
    stack_base = fixture.get("stack_base", STACK)
    _require(
        type(stack_base) is int and 0 <= stack_base <= 2**32 - len(stack),
        "invalid stack mapping",
    )
    _require(
        stack_base <= f - 32 and f + 8 <= stack_base + len(stack),
        "return frame outside stack mapping",
    )
    events = []

    def event(access, address, value):
        events.append(dict(access=access, address=address, width=4, value=value))
        if access == "write":
            stack[address - stack_base : address - stack_base + 4] = value.to_bytes(
                4, "little"
            )

    r = lambda a, v: event("read", a, v)
    r(f - 4, fixture["cookie"] ^ f)
    for offset, reg in ((-32, "edi"), (-28, "esi"), (-24, "ebx")):
        r(f + offset, saved[reg])
    event("write", f - 24, CONTINUATION)
    r(COOKIE, fixture["current"])
    regs.update(
        ecx=fixture["cookie"],
        edi=saved["edi"],
        esi=saved["esi"],
        ebx=saved["ebx"],
        esp=rel["final_esp"],
    )
    if rel["equal"]:
        r(f - 24, CONTINUATION)
        r(f, saved["ebp"])
        r(f + 4, rel["endpoint"])
        regs["ebp"] = saved["ebp"]
    return dict(registers=regs, stack=bytes(stack), events=events, flags=rel["flags"])


def _run_case(codes, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector)
    expected = _expected(fixture)
    f = fixture["frame"]
    relation = fixture["relation"]
    m = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page in sorted(
        {BASE + (a & ~0xFFF) for a, b in BODIES.values()}
        | {RETURN, ESCAPE & ~0xFFF, COOKIE & ~0xFFF}
    ):
        m.mem_map(page, 0x1000)
    m.mem_map(STACK, 0x4000)
    m.mem_write(STACK, fixture["stack"])
    m.mem_write(COOKIE & ~0xFFF, fixture["globals"])
    for name, (a, b) in BODIES.items():
        m.mem_write(BASE + a, codes[name])
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in fixture["registers"]}
    for r, value in fixture["registers"].items():
        m.reg_write(ids[r], value)
    m.reg_write(x.UC_X86_REG_EFLAGS, 0x246 | (vector["df"] << 10))
    allowed = {int(p["rva"], 16) for rows in points.values() for p in rows}
    visited = []
    events = []

    def code(machine, address, size, user):
        if address in (RETURN, ESCAPE):
            machine.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "return execution escaped reviewed ranges")
        visited.append(f"0x{pc:08x}")
        if pc == 0x3574CA:
            if negative == "ancestor":
                word = int.from_bytes(machine.mem_read(f + 8, 4), "little")
                machine.mem_write(f + 8, (word ^ 1).to_bytes(4, "little"))
            if negative == "cookie":
                machine.mem_write(
                    COOKIE, (fixture["current"] ^ 1).to_bytes(4, "little")
                )

    def memory(machine, access, address, size, value, user):
        _require(size == 4, "unexpected return access width")
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
    m.emu_start(BASE + 0x2EB21A, 0, count=100)
    _require(
        m.reg_read(x.UC_X86_REG_EIP) == relation["endpoint"], "return endpoint differs"
    )
    actual = {r: m.reg_read(i) for r, i in ids.items()}
    flags = m.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        actual == expected["registers"]
        and flags & 0x8D5 == expected["flags"] & 0x8D5
        and (flags >> 10) & 1 == vector["df"],
        "return registers or flags differ",
    )
    _require(events == expected["events"], "return ordered events differ")
    _require(
        bytes(m.mem_read(STACK, 0x4000)) == expected["stack"],
        "return ancestor memory differs",
    )
    _require(
        bytes(m.mem_read(COOKIE & ~0xFFF, 0x1000)) == fixture["globals"],
        "return global memory differs",
    )
    return dict(
        inputs=vector,
        registers=actual,
        flags=flags & 0xCD5,
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        stack_sha256=hashlib.sha256(expected["stack"]).hexdigest(),
        endpoint=relation["endpoint"],
    )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256, "executable differs")
    owner = next(
        b for b in sources["chain"]["function_bodies"] if b["entry_rva"] == "0x002eb140"
    )
    witnessed = {
        p["rva"]: {k: p[k] for k in ("rva", "size", "sha256")}
        for p in owner["reviewed_points"]
        + sources["checker"]["function_body"]["reviewed_points"]
    }
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    start = int(owner["range_start_rva"], 16)
    size = owner["range_size"]
    offset = image.rva_to_file_offset(start)
    owner_bytes = data[offset : offset + size]
    _require(
        hashlib.sha256(owner_bytes).hexdigest() == owner["body_sha256"],
        "full owner body differs",
    )
    full_points = [_point(r) for r in decoder.disasm(owner_bytes, BASE + start)]
    _require(sum(p["size"] for p in full_points) == size, "full owner decode differs")
    witnessed.update({p["rva"]: p for p in full_points})
    codes = {}
    points = {}
    for name, (a, b) in BODIES.items():
        offset = image.rva_to_file_offset(a)
        codes[name] = data[offset : offset + b - a]
        points[name] = [_point(r) for r in decoder.disasm(codes[name], BASE + a)]
        _require(
            sum(p["size"] for p in points[name]) == b - a
            and all(witnessed.get(p["rva"]) == p for p in points[name]),
            "return witness differs",
        )
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({p for o in observations for p in o["trace_rvas"]})
    _require(
        set(union) == {p["rva"] for rows in points.values() for p in rows},
        "return site coverage differs",
    )
    controls = []
    sample = vectors()[0]
    for kind, message in (
        ("ancestor", "return ancestor memory differs"),
        ("cookie", "return endpoint differs"),
    ):
        try:
            _run_case(codes, points, sample, kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "return control failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("return mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=ids,
        build_identity=sources["chain"]["build_identity"],
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
            equal_returns=sum(_fixture(v)["relation"]["equal"] for v in vectors()),
            mismatch_frontiers=sum(
                not _fixture(v)["relation"]["equal"] for v in vectors()
            ),
            instruction_bytes=sum(len(v) for v in codes.values()),
            executed_sites=len(union),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Native class vector owner epilogue and cookie checker execute to caller return or the external mismatch boundary",
            frame_relation="Append slice ESP S equals frame F-32; checker CALL overwrites already-popped saved EBX at F-24 with this caller continuation; equal return finishes F+12; mismatch preserves F-24",
            premises=[
                "Mapped complete ancestor stack and stable cookie global; supplied prior saved registers and protected cookie slot",
                "Both initial direction flag values are modeled and preserved",
            ],
            not_claimed=[
                "Parent prefix or append execution, cookie initialization, mismatch failure implementation or other callers",
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
        "sealed return differs",
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
        "exact return differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
