"""Mode-three assertion dispatch through native getters to opaque call entry."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from src.observatory import native_assertion_helper_fill_conformance as common
from src.observatory import native_assertion_helper_parent_dispatch_semantics as model

BASE, EXE_SHA256 = common.BASE, common.EXE_SHA256
ConformanceError, _require = common.ConformanceError, common._require
_canonical_sha256, _canonical_bytes = common._canonical_sha256, common._canonical_bytes
ANALYSIS_KIND = "pe_native_assertion_helper_parent_dispatch_conformance"
SEALED_SHA256 = "88c1e3a7c73d276650c41cd5f356d7bc72c46c410e35ef84f50aac3ad0d3c5ed"
SOURCE_PINS = {
    **model.SOURCE_PINS,
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
}
BODIES = {
    model.PARENT: (
        72,
        29,
        "1f55c49efcf686fecf491fc4ac23411e373af8d7c38c0f076b070a417e7ddf13",
    ),
    model.FIRST: (
        63,
        23,
        "9ccce0d1b341bdf834edec2dc6c9626c73f97a7e4df7917e4c7d202ae906039d",
    ),
    model.SECOND: (
        6,
        2,
        "f664d3656a8c5a2735ac645e41a9bf134e95d47511b55d5466a3384f9d529fec",
    ),
}
GETTER_VALUES = (0, 1, 2, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFF)
STACK, GLOBAL_PAGE = 0x30000000, 0x008B7000
REGISTERS = model.REGISTERS
CONTROLS = {
    "mode": "assertion dispatch first handoff differs",
    "first_register": "assertion dispatch first handoff differs",
    "first_return": "assertion dispatch first return differs",
    "second_register": "assertion dispatch second handoff differs",
    "second_return": "assertion dispatch second return differs",
    "result": "assertion dispatch final ABI differs",
    "flags": "assertion dispatch final ABI differs",
    "df": "assertion dispatch initial DF differs",
    "argument": "assertion dispatch callee frame differs",
    "caller_return": "assertion dispatch callee frame differs",
    "call_return": "assertion dispatch callee frame differs",
    "ancestor": "assertion dispatch protected pages differ",
    "saved_ebp": "assertion dispatch protected pages differ",
    "global": "assertion dispatch protected pages differ",
    "global_padding": "assertion dispatch protected pages differ",
    "missing_read": "assertion dispatch ordered events differ",
    "extra_read": "assertion dispatch ordered events differ",
    "restored_global_write": "assertion dispatch ordered events differ",
    "trace": "assertion dispatch instruction path differs",
}


def vectors():
    return [
        dict(first_global=first, second_global=second, alignment=a, profile=p)
        for first in GETTER_VALUES
        for second in GETTER_VALUES
        for a in range(16)
        for p in range(3)
    ]


def _raw(pages, address, width=4):
    return int.from_bytes(
        bytes(pages[(address + i) & ~4095][(address + i) & 4095] for i in range(width)),
        "little",
    )


def _put(pages, address, value):
    for i, byte in enumerate(value.to_bytes(4, "little")):
        pages[(address + i) & ~4095][(address + i) & 4095] = byte


def _fixture(vector):
    _require(
        type(vector) is dict
        and set(vector) == {"first_global", "second_global", "alignment", "profile"}
        and all(type(v) is int for v in vector.values())
        and vector["first_global"] in GETTER_VALUES
        and vector["second_global"] in GETTER_VALUES
        and vector["alignment"] in range(16)
        and vector["profile"] in range(3),
        "assertion dispatch vector differs",
    )
    a, profile = vector["alignment"], vector["profile"]
    entry = STACK + 0x1000 + a
    pages = {
        p: bytearray(
            ((i * 31) ^ (i >> 3) ^ (p >> 12) ^ 0xA7) & 255 for i in range(4096)
        )
        for p in (STACK, STACK + 4096, GLOBAL_PAGE)
    }
    words = (
        (0x0400A000, 0, 0, 0),
        (0x006EC151, 0x0083CA00, 0x0083C9C8, 69),
        (0xFFFFFFFF, 0xFFFFFFFF, 0xFEFEFEFE, 0xFFFFFFFF),
    )[profile]
    for i, value in enumerate(words):
        _put(pages, entry + 4 * i, value)
    _put(pages, model.FIRST_GLOBAL, vector["first_global"])
    _put(pages, model.SECOND_GLOBAL, vector["second_global"])
    registers = {
        r: ((0x12345678 + 0x112233 * index) ^ (profile * 0x23232323)) & 0xFFFFFFFF
        for index, r in enumerate(REGISTERS)
    }
    registers["esp"] = entry
    return dict(
        pages={p: bytes(v) for p, v in pages.items()},
        registers=registers,
        entry_flags=(0x246, 0x202, 0x2D7)[profile],
    )


def _expected(fixture):
    _require(
        type(fixture) is dict and set(fixture) == {"pages", "registers", "entry_flags"},
        "assertion dispatch fixture schema differs",
    )
    try:
        return model.apply_to_pages(
            registers=fixture["registers"],
            pages=fixture["pages"],
            entry_flags=fixture["entry_flags"],
        )
    except model.AssertionParentDispatchError as exc:
        raise ConformanceError(str(exc)) from exc


def _preflight(sources):
    _require(
        type(sources) is dict
        and set(sources) == set(SOURCE_PINS)
        and all(type(v) is dict for v in sources.values()),
        "assertion dispatch source partition differs",
    )
    identities = common._normalize(
        lambda: {
            k: common._source_identity(sources[k], *pin, k)
            for k, pin in SOURCE_PINS.items()
        }
    )
    identity = sources["program_facts"]["identity"]
    _require(
        identity["executable_sha256"] == EXE_SHA256
        and all(sources[k]["build_identity"] == identity for k in model.SOURCE_PINS),
        "assertion dispatch build differs",
    )
    return identities


def _load_code(data, image, sources):
    _preflight(sources)
    codes, points = {}, []
    for entry, (size, count, digest) in BODIES.items():
        rows = common._decode_body(data, image, sources["program_facts"], entry)
        code = b"".join(bytes(r.bytes) for r in rows)
        _require(
            len(code) == size
            and len(rows) == count
            and hashlib.sha256(code).hexdigest() == digest,
            "assertion dispatch selected body differs",
        )
        codes[BASE + entry] = code
        points.extend(common._point(r) for r in rows)
    return codes, sorted(points, key=lambda p: p["rva"])


def _run_case(codes, points, vector, negative=None, *, capture=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector)
    expected = _expected(fixture)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for p, body in fixture["pages"].items():
        machine.mem_map(p, 4096)
        machine.mem_write(p, body)
    code_pages = {(a + i) & ~4095 for a, b in codes.items() for i in range(len(b))}
    code_pages |= {expected["endpoint"] & ~4095}
    _require(
        not code_pages & set(fixture["pages"]), "assertion dispatch mapping overlaps"
    )
    for p in sorted(code_pages):
        machine.mem_map(p, 4096)
        machine.mem_write(p, b"\xcc" * 4096)
    for a, body in codes.items():
        machine.mem_write(a, body)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in REGISTERS}
    for r, value in fixture["registers"].items():
        machine.reg_write(ids[r], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, fixture["entry_flags"])
    events, visited = [], []
    allowed = {int(p["rva"], 16) for p in points}
    counts = dict(first_entry=0, first_return=0, second_entry=0, second_return=0)
    finished = False
    entry = fixture["registers"]["esp"]

    def regs():
        return {r: machine.reg_read(i) for r, i in ids.items()}

    def words(address, n):
        return [
            int.from_bytes(machine.mem_read(address + 4 * i, 4), "little")
            for i in range(n)
        ]

    def flip_register(name):
        machine.reg_write(ids[name], machine.reg_read(ids[name]) ^ 1)

    def flip_word(address):
        machine.mem_write(address, (words(address, 1)[0] ^ 1).to_bytes(4, "little"))

    def on_code(m, address, size, user):
        nonlocal finished
        pc = address - BASE
        if pc == model.PARENT:
            if negative == "df":
                m.reg_write(
                    x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) | 0x400
                )
            _require(
                not m.reg_read(x.UC_X86_REG_EFLAGS) & 0x400,
                "assertion dispatch initial DF differs",
            )
        if pc == model.FIRST:
            counts["first_entry"] += 1
            if negative == "mode":
                flip_word(entry - 12)
            if negative == "first_register":
                flip_register("edx")
            _require(
                regs() == expected["first_getter"]["entry_registers"]
                and words(entry - 16, 2) == [BASE + 0x379CD2, 3],
                "assertion dispatch first handoff differs",
            )
        if pc == 0x379CD2:
            counts["first_return"] += 1
            if negative == "first_return":
                flip_register("eax")
            packet = expected["first_getter"]
            _require(
                regs() == packet["return_registers"]
                and m.reg_read(x.UC_X86_REG_EFLAGS) & packet["flag_mask"]
                == packet["flags"],
                "assertion dispatch first return differs",
            )
        if pc == model.SECOND:
            counts["second_entry"] += 1
            if negative == "second_register":
                flip_register("edx")
            packet = expected["second_getter"]
            _require(
                packet is not None
                and regs() == packet["entry_registers"]
                and words(entry - 12, 1) == [BASE + 0x379CE1],
                "assertion dispatch second handoff differs",
            )
        if pc == 0x379CE1:
            counts["second_return"] += 1
            if negative == "second_return":
                flip_register("eax")
            packet = expected["second_getter"]
            _require(
                packet is not None
                and regs() == packet["return_registers"]
                and m.reg_read(x.UC_X86_REG_EFLAGS) & packet["flag_mask"]
                == packet["flags"],
                "assertion dispatch second return differs",
            )
        if address in (BASE + model.THIRD, BASE + model.FOURTH):
            _require(
                address == expected["endpoint"],
                "assertion dispatch selected child differs",
            )
            call = expected["call"]
            if negative == "argument":
                flip_word(call["entry_esp"] + 4)
            if negative == "caller_return":
                flip_word(call["entry_esp"] + 16)
            if negative == "call_return":
                flip_word(call["entry_esp"])
            _require(
                words(call["entry_esp"], len(call["arguments"]) + 1)
                == [call["return_address"], *call["arguments"]],
                "assertion dispatch callee frame differs",
            )
            if negative == "result":
                flip_register("eax")
            if negative == "flags":
                m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 1)
            corrupt = {
                "ancestor": entry + 16,
                "saved_ebp": entry - 4,
                "global": model.FIRST_GLOBAL,
                "global_padding": GLOBAL_PAGE + 0x777,
            }
            if negative in corrupt:
                flip_word(corrupt[negative])
            if negative == "missing_read":
                events.pop(
                    next(
                        i
                        for i, e in enumerate(events)
                        if e["address"] == model.FIRST_GLOBAL
                    )
                )
            if negative == "extra_read":
                events.append(
                    dict(
                        access="read",
                        address=model.SECOND_GLOBAL,
                        width=4,
                        value=vector["second_global"],
                        rva=model.SECOND,
                    )
                )
            if negative == "restored_global_write":
                value = vector["first_global"]
                events.extend(
                    [
                        dict(
                            access="write",
                            address=model.FIRST_GLOBAL,
                            width=4,
                            value=value ^ 1,
                            rva=model.FIRST,
                        ),
                        dict(
                            access="write",
                            address=model.FIRST_GLOBAL,
                            width=4,
                            value=value,
                            rva=model.FIRST,
                        ),
                    ]
                )
            if negative == "trace":
                visited.append(model.THIRD)
            finished = True
            m.emu_stop()
            return
        _require(
            pc in allowed
            and len(visited) < len(expected["trace_rvas"])
            and pc == expected["trace_rvas"][len(visited)],
            "assertion dispatch instruction path differs",
        )
        visited.append(pc)

    def on_memory(m, access, address, width, value, user):
        _require(width == 4, "assertion dispatch unexpected memory width")
        writing = access == uc.UC_MEM_WRITE
        _require(
            not writing or not GLOBAL_PAGE <= address < GLOBAL_PAGE + 4096,
            "assertion dispatch global write",
        )
        events.append(
            dict(
                access="write" if writing else "read",
                address=address,
                width=width,
                value=(
                    (value & 0xFFFFFFFF)
                    if writing
                    else int.from_bytes(m.mem_read(address, width), "little")
                ),
                rva=m.reg_read(x.UC_X86_REG_EIP) - BASE,
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    machine.emu_start(BASE + model.PARENT, 0, count=200)
    _require(
        finished and machine.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "assertion dispatch frontier absent",
    )
    _require(
        counts
        == dict(
            first_entry=1,
            first_return=1,
            second_entry=int(expected["second_getter"] is not None),
            second_return=int(expected["second_getter"] is not None),
        ),
        "assertion dispatch getter counts differ",
    )
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        regs() == expected["registers"]
        and flags & expected["flag_mask"] == expected["flags"],
        "assertion dispatch final ABI differs",
    )
    _require(
        all(
            bytes(machine.mem_read(p, 4096)) == v for p, v in expected["pages"].items()
        ),
        "assertion dispatch protected pages differ",
    )
    _require(events == expected["events"], "assertion dispatch ordered events differ")
    _require(
        visited == expected["trace_rvas"], "assertion dispatch instruction path differs"
    )
    if capture is not None:
        capture(machine, ids, expected)
    return dict(
        vector=copy.deepcopy(vector),
        branch=expected["branch"],
        registers=regs(),
        flags=flags & expected["flag_mask"],
        flag_mask=expected["flag_mask"],
        endpoint=f"0x{expected['endpoint']-BASE:08x}",
        trace_rvas=[f"0x{pc:08x}" for pc in visited],
        events_sha256=_canonical_sha256(events),
        memory_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(v).hexdigest()
                for p, v in expected["pages"].items()
            }
        ),
        second_getter=expected["second_getter"] is not None,
        arguments=copy.deepcopy(expected["call"]["arguments"]),
        opaque_child_executed=False,
    )


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = common._load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE,
        "exact assertion dispatch executable differs",
    )
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, v) for v in vectors()]
    controls = []
    sample = dict(first_global=0, second_global=2, alignment=15, profile=2)
    for kind, reason in CONTROLS.items():
        try:
            _run_case(codes, points, sample, kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "incidental assertion dispatch control: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("assertion dispatch control survived: " + kind)
    sites = sorted({p for o in observations for p in o["trace_rvas"]})
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{a-BASE:08x}",
                    end_rva=f"0x{a+len(b)-BASE:08x}",
                    sha256=hashlib.sha256(b).hexdigest(),
                )
                for a, b in sorted(codes.items())
            ],
            points=points,
        ),
        vectors=vectors(),
        executed_rvas=sites,
        negative_controls=controls,
        observations_sha256=_canonical_sha256(observations),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=len(observations),
            static_sites=len(points),
            executed_sites=len(sites),
            instruction_bytes=sum(map(len, codes.values())),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            first_getters=len(observations),
            second_getters=sum(o["second_getter"] for o in observations),
            normal=sum(o["branch"] == "normal" for o in observations),
            alternate=sum(o["branch"] == "alternate" for o in observations),
            controls=len(controls),
            global_writes=0,
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            checked=[
                "Continuous native parent and mode-three first getter with conditional second getter",
                "Exact argument order includes original caller return only for the normal child",
                "All GPRs and independently defined CMP TEST flags preserve supplied clear DF",
                "Ordered native reads writes and all retained page bytes match the standalone model",
            ],
            premises=[
                "Synthetic aligned pages opaque caller words and supplied runtime getter DWORD values",
                "Entry flags are supplied with clear DF; no actual bootstrap global value is inferred",
            ],
            excluded=[
                "Other first-getter modes and setter failure descendants",
                "Opaque third and fourth child instructions normal return trap dialog abort or unwind",
                "CRT identity hardware execution ownership and whole-program accounting",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "assertion dispatch executable changed",
    )
    common._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    common._validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors(),
        "sealed assertion dispatch receipt differs",
    )
    common._assert_publication_safe(evidence)
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
        "exact assertion dispatch receipt differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


encode_conformance = common.encode_conformance
