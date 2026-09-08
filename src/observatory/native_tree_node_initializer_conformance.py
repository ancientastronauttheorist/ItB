"""Exact initializer replay with opaque return and ordered alias feedback oracle."""

from __future__ import annotations
import hashlib, json
from pathlib import Path
from src.observatory import native_tree_node_initializer_semantics as sem
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

ANALYSIS_KIND = "pe_native_tree_node_initializer_conformance"
SEALED_SHA256 = "da2ed4fde20e1df51447258edbcbd11e394442669554af9832881462c708bcc0"
START, TARGET = 0x7D060, 0x3574DB


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    pointers = (
        [0, 4, 8, 0xFFFFFFF8, 0xFFFFFFFC]
        + [0x20002000 + i for i in range(16)]
        + [0x10001000 + i for i in range(-11, 5)]
    )
    return [
        dict(
            pointer=p,
            head=h,
            frame_alignment=f,
            seed=7,
            source_address=0x10001000,
            df=df,
        )
        for p in pointers
        for h in (0, 0x11223344, 0xFFFFFFFF)
        for f in range(16)
        for df in (0, 1)
    ]


def oracle(vector, fixture):
    memory = dict(fixture["memory"])
    events = []
    stores = []
    regs = dict(fixture["registers"])
    s = fixture["stack"]
    p = vector["pointer"]
    source = vector["source_address"]
    sample = fixture["sample"]

    def write(at, value, origin="native"):
        events.append(
            dict(access="write", address=at, width=4, value=value, origin=origin)
        )
        for i, b in enumerate(value.to_bytes(4, "little")):
            memory[at + i] = b

    def read(at, origin="native"):
        value = sum(memory[at + i] << (8 * i) for i in range(4))
        events.append(
            dict(access="read", address=at, width=4, value=value, origin=origin)
        )
        return value

    write(s - 4, regs["esi"])
    write(s - 8, regs["edi"])
    write(s - 12, 24)
    write(s - 16, BASE + 0x7D06B)
    read(s - 16, "opaque_return")
    edx = sample["edx"]
    address = p
    for index in range(3):
        if address:
            value = read(source)
            if index == 0:
                edx = value
            write(address, value)
            stores.append(dict(address=address, value=value))
        address = (address + 4) % 0x100000000
    read(s - 8)
    read(s - 4)
    read(s)
    regs.update(eax=p, ecx=(p + 8) & 0xFFFFFFFF, edx=edx, esp=s + 4)
    final = (p + 8) & 0xFFFFFFFF
    flags = (
        (int(final == 0) << 6)
        | ((final >> 31) << 7)
        | (int((final & 255).bit_count() % 2 == 0) << 2)
    )
    ordinary = p != 0 and p + 24 <= 1 << 32 and (p + 24 <= source or source + 4 <= p)
    if ordinary:
        _require(
            bytes(memory[p + i] for i in range(12))
            == vector["head"].to_bytes(4, "little") * 3,
            "fresh block fields differ",
        )
        _require(
            all(memory[p + i] == fixture["memory"][p + i] for i in range(12, 24)),
            "fresh block tail changed",
        )
    return dict(
        memory=memory,
        events=events,
        registers=regs,
        flags=flags,
        stores=stores,
        ordinary=ordinary,
    )


def _run_case(code, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = sem.case_fixture(**vector)
    expected = oracle(vector, fixture)
    memory = fixture["memory"]
    pages = {at & ~0xFFF: bytearray(b"\xa5" * 0x1000) for at in memory}
    for at, value in memory.items():
        pages[at & ~0xFFF][at & 0xFFF] = value
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, payload in pages.items():
        machine.mem_map(page, 0x1000)
        machine.mem_write(page, bytes(payload))
    for page in (
        (BASE + START) & ~0xFFF,
        (BASE + TARGET) & ~0xFFF,
        fixture["return_address"],
    ):
        machine.mem_map(page, 0x1000)
        machine.mem_write(page, b"\xcc" * 0x1000)
    machine.mem_write(BASE + START, code)
    ids = {
        name: getattr(x, "UC_X86_REG_" + name.upper()) for name in fixture["registers"]
    }
    for name, value in fixture["registers"].items():
        machine.reg_write(ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 2 | (vector["df"] << 10))
    allowed = {int(p["rva"], 16) for p in points}
    events = []
    visited = []
    calls = 0

    def on_code(m, address, size, _):
        nonlocal calls
        if address == BASE + TARGET:
            _require(
                calls == 0 and m.reg_read(x.UC_X86_REG_ESP) == fixture["stack"] - 16,
                "opaque call frame differs",
            )
            at = m.reg_read(x.UC_X86_REG_ESP)
            continuation = int.from_bytes(m.mem_read(at, 4), "little")
            _require(
                continuation == BASE + 0x7D06B
                and int.from_bytes(m.mem_read(at + 4, 4), "little") == 24,
                "opaque call continuation or argument differs",
            )
            events.append(
                dict(
                    access="read",
                    address=at,
                    width=4,
                    value=continuation,
                    origin="opaque_return",
                )
            )
            sample = fixture["sample"]
            m.reg_write(x.UC_X86_REG_EAX, vector["pointer"])
            m.reg_write(x.UC_X86_REG_ECX, sample["ecx"])
            m.reg_write(x.UC_X86_REG_EDX, sample["edx"])
            m.reg_write(
                x.UC_X86_REG_EFLAGS,
                (m.reg_read(x.UC_X86_REG_EFLAGS) & ~0x8D5) | sample["flags"],
            )
            m.reg_write(x.UC_X86_REG_ESP, at + 4)
            m.reg_write(x.UC_X86_REG_EIP, continuation)
            calls += 1
            return
        pc = address - BASE
        _require(pc in allowed, "initializer escaped exact body")
        if negative == "cached_head" and pc == 0x7D081:
            m.reg_write(x.UC_X86_REG_EAX, vector["head"])
        if negative == "return" and pc == 0x7D092:
            m.reg_write(x.UC_X86_REG_EAX, 0)
        visited.append(f"0x{pc:08x}")

    def on_memory(m, kind, at, width, value, _):
        _require(
            width == 4 and all(at + i in memory for i in range(4)),
            "initializer unmapped word access",
        )
        writing = kind == uc.UC_MEM_WRITE
        if writing:
            destinations = [
                (vector["pointer"] + i) & 0xFFFFFFFF
                for i in (0, 4, 8)
                if (vector["pointer"] + i) & 0xFFFFFFFF
            ]
            _require(
                at in destinations + [fixture["stack"] - i for i in (4, 8, 12, 16)],
                "unexpected initializer data write",
            )
        events.append(
            dict(
                access="write" if writing else "read",
                address=at,
                width=4,
                value=(
                    value & 0xFFFFFFFF
                    if writing
                    else int.from_bytes(m.mem_read(at, 4), "little")
                ),
                origin="native",
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    machine.emu_start(BASE + START, fixture["return_address"], count=60)
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == fixture["return_address"] and calls == 1,
        "initializer did not return after one summary",
    )
    regs = {name: machine.reg_read(reg) for name, reg in ids.items()}
    _require(regs == expected["registers"], "initializer register oracle differs")
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        flags & 0x8C5 == expected["flags"] and (flags >> 10) & 1 == vector["df"],
        "initializer defined flags or DF differ",
    )
    _require(events == expected["events"], "initializer ordered alias oracle differs")
    for at, value in expected["memory"].items():
        pages[at & ~0xFFF][at & 0xFFF] = value
    _require(
        all(
            bytes(machine.mem_read(page, 0x1000)) == bytes(payload)
            for page, payload in pages.items()
        ),
        "initializer full page memory differs",
    )
    return dict(
        vector=vector,
        registers=regs,
        flags=flags & 0x8C5,
        df=vector["df"],
        ordinary=expected["ordinary"],
        stores=expected["stores"],
        visited=visited,
        events_sha256=_canonical_sha256(events),
    )


def _build_unsealed(executable, semantics):
    import capstone

    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(semantics) == sem.SEALED_SHA256, "initializer source differs"
    )
    data, image, digest = _load_executable(executable)
    _require(
        digest == EXE_SHA256
        and image.image_base == BASE
        and capstone.__version__ == "5.0.7",
        "exact initializer build differs",
    )
    offset = image.rva_to_file_offset(START)
    code = data[offset : offset + 51]
    points = [
        _point(r)
        for r in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
            code, BASE + START
        )
    ]
    _require(
        points == semantics["body"]["points"] and len(points) == 25,
        "initializer code differs",
    )
    cases = [_run_case(code, points, v) for v in vectors()]
    controls = []
    for name, message, pointer in (
        ("cached_head", "ordered alias", 0x10000FFF),
        ("return", "register oracle", 0x20002000),
    ):
        vector = dict(
            pointer=pointer,
            head=0x11223344,
            frame_alignment=0,
            seed=7,
            source_address=0x10001000,
            df=0,
        )
        try:
            _run_case(code, points, vector, name)
        except ConformanceError as exc:
            _require(message in str(exc), "unrelated initializer mutation failure")
            controls.append(dict(name=name, rejected=True))
        else:
            raise ConformanceError("initializer mutation accepted")
    union = sorted({pc for case in cases for pc in case["visited"]})
    _require(
        union == semantics["model_evidence"]["instruction_union_rvas"],
        "initializer native coverage differs",
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
            executed_sites=25,
            executed_bytes=51,
            opaque_normal_returns=len(cases),
            executed_callee_instructions=0,
            ordinary_cases=sum(c["ordinary"] for c in cases),
            negative_controls=2,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact initializer instructions and native CALL frame match independent ordered byte-alias and full-register oracles under one opaque normal-return summary",
            premises=[
                "Shared declarative fixture layout, independent byte reconstruction and write oracle; source and destinations may partially alias",
                "Opaque retry summary preserves all memory and nonvolatile registers and DF, sets declared EAX ECX EDX and arithmetic flags, and returns cdecl without argument cleanup",
                "Every nonzero field address denotes a mapped nonwrapping DWORD disjoint from protected frame and code; low and highest pages are explicitly mapped for synthetic pointer cases",
            ],
            event_policy="Native CALL continuation write is checked separately from opaque normal-return continuation read; no retry target instruction executes",
            not_claimed=[
                "Actual allocation, native retry behavior, harmless null return, or factory composition",
                "Unmapped or word-crossing accesses, frame or code aliases, or accounting promotion",
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
        "sealed initializer replay differs",
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
        "exact initializer replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
