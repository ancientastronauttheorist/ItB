"""Finite single-body disjoint inline empty-string assignment conformance."""

from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from src.observatory import native_assertion_helper_fill_conformance as common
from src.observatory import native_movement_empty_string_copy_semantics as model

BASE, EXE_SHA256 = common.BASE, common.EXE_SHA256
ANALYSIS_KIND = "pe_native_movement_empty_string_copy_conformance"
SEALED_SHA256 = "c3d9d8598d7aa922157397a27a58aeabf86732e9bb620625d602481dd90c18b1"
SOURCE_PINS = dict(model.SOURCE_PINS)
ENTRY, SIZE, BODY_SHA256 = 0x80D0, 288, model.BODY_SHA256
POINTS_SHA256 = "bd0122e721665f06a92d7a1d28a7b218e471ed26ed688f3f6d5bfee8b9662dcb"
NATIVE_TRACE = (
    0x80D0,
    0x80D1,
    0x80D3,
    0x80D4,
    0x80D7,
    0x80D8,
    0x80DA,
    0x80DD,
    0x80DE,
    0x80E1,
    0x80E3,
    0x80E9,
    0x80EC,
    0x80EE,
    0x80F0,
    0x80F3,
    0x80F5,
    0x813E,
    0x8141,
    0x8147,
    0x814A,
    0x8170,
    0x8172,
    0x8174,
    0x8178,
    0x817B,
    0x818B,
    0x818D,
    0x818E,
    0x818F,
    0x8190,
    0x8193,
    0x8194,
)
REGISTERS, XMM = model.REGISTERS, model.XMM
PAGES = (0x30000000, 0x30001000, 0x06002000, 0x06003000, 0x06004000, 0x06005000)
RETURN, COPY_RETURN = 0x04000000, BASE + 0x15BA65
VECTOR_KEYS = {"alignment", "profile", "return_form"}
FIXTURE_KEYS = {"pages", "registers", "xmm", "return_address", "entry_flags"}
EXPECTED_KEYS = {
    "source_address",
    "destination_address",
    "registers",
    "xmm",
    "pages",
    "events",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "trace_rvas",
}
_canonical_sha256, _canonical_bytes = common._canonical_sha256, common._canonical_bytes
_read, _write, _pages = model._read, model._write, model._pages


class ConformanceError(RuntimeError):
    pass


def _require(condition, message):
    if not condition:
        raise ConformanceError(message)


def _normalize(operation):
    try:
        return operation()
    except ConformanceError:
        raise
    except Exception as exc:
        raise ConformanceError(str(exc)) from exc


def _same_packet(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return (
            set(left) == set(right)
            and all(any(type(k) is type(j) and k == j for j in right) for k in left)
            and all(_same_packet(left[k], right[k]) for k in left)
        )
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(
            _same_packet(a, b) for a, b in zip(left, right)
        )
    return left == right


def _page_hashes(pages):
    return {
        f"0x{page:08x}": hashlib.sha256(data).hexdigest()
        for page, data in sorted(pages.items())
    }


def vectors():
    return [
        dict(alignment=a, profile=p, return_form=r)
        for a in range(16)
        for p in range(3)
        for r in ("external", "record_copy")
    ]


def _checked_vector(vector):
    _require(
        type(vector) is dict
        and set(vector) == VECTOR_KEYS
        and all(type(k) is str for k in vector)
        and type(vector["alignment"]) is int
        and type(vector["profile"]) is int
        and type(vector["return_form"]) is str
        and vector in vectors(),
        "outside fixed empty string domain",
    )


def _fixture(vector):
    _checked_vector(vector)
    a, p = vector["alignment"], vector["profile"]
    g, s, d = 0x30001000 + a, 0x06002FF0 + a, 0x06004FF0 + a
    stop = RETURN if vector["return_form"] == "external" else COPY_RETURN
    memory = {
        page: bytearray(bytes((i * 31 + j * 17 + p * 53) & 255 for j in range(4096)))
        for i, page in enumerate(PAGES)
    }
    for address, word in (
        (g, stop),
        (g + 4, s),
        (g + 8, 0),
        (g + 12, 0xFFFFFFFF),
        (s + 16, 0),
        (s + 20, 15),
        (d + 16, (0, 7, 15)[p]),
        (d + 20, 15),
    ):
        _write(memory, address, word.to_bytes(4, "little"))
    _write(memory, s, b"\0")
    _write(memory, d + (0, 7, 15)[p], b"\0")
    registers = {
        name: (0x12345678 + i * 0x11111111 + p * 0x1234) & 0xFFFFFFFF
        for i, name in enumerate(REGISTERS)
    }
    registers.update(ecx=d, esp=g)
    xmm = {
        name: int.from_bytes(
            bytes((i * 19 + j * 41 + p * 73) & 255 for j in range(16)), "little"
        )
        for i, name in enumerate(XMM)
    }
    return dict(
        pages=_pages(memory),
        registers=registers,
        xmm=xmm,
        return_address=stop,
        entry_flags=0x246,
    )


def _expected(vector, fixture):
    def run():
        _checked_vector(vector)
        _require(
            type(fixture) is dict
            and set(fixture) == FIXTURE_KEYS
            and _same_packet(fixture, _fixture(vector)),
            "empty string fixture differs",
        )
        result = model.apply(**fixture)
        _require(
            type(result) is dict and set(result) == EXPECTED_KEYS,
            "empty string model schema differs",
        )
        g = fixture["registers"]["esp"]
        d = fixture["registers"]["ecx"]
        s = 0x06002FF0 + vector["alignment"]
        expected = dict(
            source_address=s,
            destination_address=d,
            registers=dict(fixture["registers"], eax=d, ecx=0, esp=g + 16),
            xmm=fixture["xmm"],
            flags=0x85,
            flag_mask=0x8D5,
            df=0,
            endpoint=fixture["return_address"],
        )
        _require(
            _same_packet({key: result[key] for key in expected}, expected),
            "empty string model ABI differs",
        )
        memory = {page: bytearray(data) for page, data in fixture["pages"].items()}
        for address, name in (
            (g - 4, "ebp"),
            (g - 8, "ebx"),
            (g - 12, "esi"),
            (g - 16, "edi"),
        ):
            _write(memory, address, fixture["registers"][name].to_bytes(4, "little"))
        _write(memory, d, b"\0")
        _write(memory, d + 16, bytes(4))
        _require(
            _same_packet(result["pages"], _pages(memory)),
            "empty string model full pages differ",
        )
        rows = (
            ("write", g - 4, 4, fixture["registers"]["ebp"]),
            ("write", g - 8, 4, fixture["registers"]["ebx"]),
            ("read", g + 4, 4, s),
            ("write", g - 12, 4, fixture["registers"]["esi"]),
            ("read", g + 8, 4, 0),
            ("write", g - 16, 4, fixture["registers"]["edi"]),
            ("read", s + 16, 4, 0),
            ("read", g + 12, 4, 0xFFFFFFFF),
            ("read", d + 20, 4, 15),
            ("read", d + 20, 4, 15),
            ("write", d + 16, 4, 0),
            ("read", g - 16, 4, fixture["registers"]["edi"]),
            ("read", g - 12, 4, fixture["registers"]["esi"]),
            ("read", g - 8, 4, fixture["registers"]["ebx"]),
            ("write", d, 1, 0),
            ("read", g - 4, 4, fixture["registers"]["ebp"]),
            ("read", g, 4, fixture["return_address"]),
        )
        expected.update(
            pages=_pages(memory),
            events=[
                dict(access=access, address=address, width=width, value=value)
                for access, address, width, value in rows
            ],
            trace_rvas=[f"0x{pc:08x}" for pc in NATIVE_TRACE],
        )
        _require(_same_packet(result, expected), "empty string model path differs")
        return copy.deepcopy(result)

    return _normalize(run)


def _preflight(sources):
    def run():
        _require(
            type(sources) is dict and set(sources) == set(SOURCE_PINS),
            "empty string source partition differs",
        )
        common._validate_json_tree(sources, "sources")
        identities = {
            key: common._source_identity(sources[key], *pin, key)
            for key, pin in SOURCE_PINS.items()
        }
        identity = sources["program_facts"]["identity"]
        _require(
            identity["executable_sha256"] == EXE_SHA256
            and all(
                _same_packet(sources[key]["build_identity"], identity)
                for key in SOURCE_PINS
                if key != "program_facts"
            ),
            "empty string source build differs",
        )
        return identities

    return _normalize(run)


def _checked_code_packet(codes, points):
    def run():
        _require(
            type(codes) is dict
            and all(type(k) is int for k in codes)
            and set(codes) == {ENTRY}
            and type(codes[ENTRY]) is bytes
            and len(codes[ENTRY]) == SIZE
            and hashlib.sha256(codes[ENTRY]).hexdigest() == BODY_SHA256,
            "empty string direct code differs",
        )
        _require(
            type(points) is list and _canonical_sha256(points) == POINTS_SHA256,
            "empty string direct points differ",
        )
        cursor = ENTRY
        allowed = {}
        for point in points:
            _require(
                type(point) is dict
                and set(point) == {"rva", "size", "sha256"}
                and type(point["size"]) is int
                and point["size"] > 0,
                "empty string direct point schema differs",
            )
            pc = int(point["rva"], 16)
            _require(
                pc == cursor
                and pc + point["size"] <= ENTRY + SIZE
                and hashlib.sha256(
                    codes[ENTRY][pc - ENTRY : pc - ENTRY + point["size"]]
                ).hexdigest()
                == point["sha256"],
                "empty string direct instruction differs",
            )
            allowed[pc] = point
            cursor += point["size"]
        _require(cursor == ENTRY + SIZE, "empty string direct extent differs")
        return allowed

    return _normalize(run)


def _load_code(data, image, sources):
    def run():
        _preflight(sources)
        _require(
            hashlib.sha256(data).hexdigest() == EXE_SHA256 and image.image_base == BASE,
            "empty string executable differs",
        )
        rows = common._decode_body(data, image, sources["program_facts"], ENTRY)
        codes = {ENTRY: b"".join(bytes(row.bytes) for row in rows)}
        points = [common._point(row) for row in rows]
        _checked_code_packet(codes, points)
        return codes, points

    return _normalize(run)


CONTROLS = {
    **{
        name: "empty string native entry differs"
        for name in ("entry_gpr", "entry_xmm", "entry_flags", "entry_df", "entry_page")
    },
    **{
        name: "empty string ordered memory differs"
        for name in ("source_size", "offset", "maximum", "destination_capacity")
    },
    **{
        name: "empty string final pages differ"
        for name in (
            "source_capacity",
            "source_terminator",
            "source_padding",
            "destination_size",
            "destination_byte",
            "destination_padding",
            "stack_ancestor",
            "stack_padding",
            "caller_word",
        )
    },
    **{
        name: "empty string final ABI differs"
        for name in (
            "final_gpr",
            "final_xmm",
            "final_flags",
            "final_df",
            "final_endpoint",
        )
    },
    **{
        name: "empty string final events differ"
        for name in ("missing_read_record", "restored_write_record")
    },
    "trace_record": "empty string final native path differs",
}


def _run_case(codes, points, vector, negative=None, *, capture=None):
    _require(
        negative is None or type(negative) is str and negative in CONTROLS,
        "invalid empty string control",
    )
    fixture = _fixture(vector)
    wanted = _expected(vector, fixture)
    allowed = _checked_code_packet(codes, points)
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "empty string reviewed Unicorn required")
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    machine.ctl_set_cpu_model(19)
    _require(machine.ctl_get_cpu_model() == 19, "empty string CPU differs")
    stop = fixture["return_address"]
    g = fixture["registers"]["esp"]
    s = wanted["source_address"]
    d = wanted["destination_address"]
    code_pages = {(BASE + pc) & ~4095 for pc in range(ENTRY, ENTRY + SIZE)} | {
        stop & ~4095
    }
    _require(
        not code_pages.intersection(fixture["pages"]),
        "empty string runtime mappings overlap",
    )
    for page in sorted(code_pages):
        machine.mem_map(page, 4096)
        machine.mem_write(page, bytes([0xCC]) * 4096)
    for page, data in fixture["pages"].items():
        machine.mem_map(page, 4096)
        machine.mem_write(page, data)
    machine.mem_write(BASE + ENTRY, codes[ENTRY])
    ids = {name: getattr(x, "UC_X86_REG_" + name.upper()) for name in REGISTERS}
    xmm_ids = {name: getattr(x, "UC_X86_REG_" + name.upper()) for name in XMM}
    for name, value in fixture["registers"].items():
        machine.reg_write(ids[name], value)
    for name, value in fixture["xmm"].items():
        machine.reg_write(xmm_ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, fixture["entry_flags"])
    trace = []
    events = []
    boundaries = []

    def flip(address):
        machine.mem_write(address, bytes([machine.mem_read(address, 1)[0] ^ 1]))

    def on_code(m, address, size, user):
        if address == stop:
            m.emu_stop()
            return
        pc = address - BASE
        _require(
            pc in allowed and size == allowed[pc]["size"],
            "empty string escaped selected code",
        )
        if pc == ENTRY:
            if negative == "entry_gpr":
                m.reg_write(ids["edx"], m.reg_read(ids["edx"]) ^ 1)
            if negative == "entry_xmm":
                m.reg_write(xmm_ids["xmm7"], m.reg_read(xmm_ids["xmm7"]) ^ 1)
            if negative in ("entry_flags", "entry_df"):
                m.reg_write(
                    x.UC_X86_REG_EFLAGS,
                    m.reg_read(x.UC_X86_REG_EFLAGS)
                    ^ (1 if negative == "entry_flags" else 0x400),
                )
            if negative == "entry_page":
                flip(g + 16)
            flags = m.reg_read(x.UC_X86_REG_EFLAGS)
            pages = {p: bytes(m.mem_read(p, 4096)) for p in PAGES}
            observed_registers = {name: m.reg_read(i) for name, i in ids.items()}
            observed_xmm = {name: m.reg_read(i) for name, i in xmm_ids.items()}
            _require(
                _same_packet(
                    observed_registers,
                    fixture["registers"],
                )
                and _same_packet(observed_xmm, fixture["xmm"])
                and flags == 0x246
                and _same_packet(pages, fixture["pages"])
                and not events,
                "empty string native entry differs",
            )
            boundaries.append(
                dict(
                    name="entry",
                    registers=observed_registers,
                    xmm=observed_xmm,
                    eflags=flags,
                    flags=flags & 0x8D5,
                    flag_mask=0x8D5,
                    df=(flags >> 10) & 1,
                    endpoint=address,
                    pages_sha256=_page_hashes(pages),
                    events_sha256=_canonical_sha256(events),
                )
            )
        if negative == "source_size" and pc == 0x80DE:
            flip(s + 16)
        if negative == "offset" and pc == 0x80DA:
            flip(g + 8)
        if negative == "maximum" and pc == 0x80E9:
            flip(g + 12)
        if negative == "destination_capacity" and pc == 0x8147:
            flip(d + 20)
        trace.append(f"0x{pc:08x}")
        _require(
            trace == wanted["trace_rvas"][: len(trace)],
            "empty string native path differs",
        )

    def on_memory(m, access, address, width, value, user):
        writing = access == uc.UC_MEM_WRITE
        row = dict(
            access="write" if writing else "read",
            address=address,
            width=width,
            value=(
                value & ((1 << (8 * width)) - 1)
                if writing
                else int.from_bytes(m.mem_read(address, width), "little")
            ),
        )
        _require(
            len(events) < 17 and _same_packet(row, wanted["events"][len(events)]),
            "empty string ordered memory differs",
        )
        events.append(row)

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    machine.emu_start(BASE + ENTRY, 0, count=1000)
    corrupt = dict(
        source_capacity=s + 20,
        source_terminator=s,
        source_padding=s + 1,
        destination_size=d + 16,
        destination_byte=d,
        destination_padding=d + 1,
        stack_ancestor=g + 16,
        stack_padding=g - 20,
        caller_word=g + 12,
    )
    if negative in corrupt:
        flip(corrupt[negative])
    if negative == "final_gpr":
        machine.reg_write(ids["eax"], machine.reg_read(ids["eax"]) ^ 1)
    if negative == "final_xmm":
        machine.reg_write(xmm_ids["xmm0"], machine.reg_read(xmm_ids["xmm0"]) ^ 1)
    if negative in ("final_flags", "final_df"):
        machine.reg_write(
            x.UC_X86_REG_EFLAGS,
            machine.reg_read(x.UC_X86_REG_EFLAGS)
            ^ (1 if negative == "final_flags" else 0x400),
        )
    if negative == "final_endpoint":
        machine.reg_write(x.UC_X86_REG_EIP, stop + 1)
    if negative == "missing_read_record":
        events.pop()
    if negative == "restored_write_record":
        events.extend(
            [
                dict(access="write", address=d + 1, width=1, value=0),
                dict(
                    access="write",
                    address=d + 1,
                    width=1,
                    value=_read(wanted["pages"], d + 1, 1)[0],
                ),
            ]
        )
    if negative == "trace_record":
        trace.append("0x00008152")
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    registers = {name: machine.reg_read(i) for name, i in ids.items()}
    xmm = {name: machine.reg_read(i) for name, i in xmm_ids.items()}
    pages = {p: bytes(machine.mem_read(p, 4096)) for p in PAGES}
    _require(
        _same_packet(registers, wanted["registers"])
        and _same_packet(xmm, wanted["xmm"])
        and flags & 0x8D5 == 0x85
        and flags & 0x400 == 0
        and machine.reg_read(x.UC_X86_REG_EIP) == stop,
        "empty string final ABI differs",
    )
    _require(_same_packet(pages, wanted["pages"]), "empty string final pages differ")
    _require(_same_packet(events, wanted["events"]), "empty string final events differ")
    _require(
        _same_packet(trace, wanted["trace_rvas"]),
        "empty string final native path differs",
    )
    _require(len(boundaries) == 1, "empty string boundary count differs")
    result = dict(
        vector=dict(vector),
        registers=registers,
        xmm=xmm,
        eflags=flags,
        flags=flags & 0x8D5,
        flag_mask=0x8D5,
        df=0,
        endpoint=stop,
        trace_rvas=trace,
        events_sha256=_canonical_sha256(events),
        pages_sha256=_page_hashes(pages),
        memory_event_count=len(events),
        boundaries=boundaries,
    )
    if capture is not None:
        capture(machine, dict(ids), copy.deepcopy(wanted), copy.deepcopy(fixture))
    return result


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = common._load_executable(Path(executable))
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, vector) for vector in vectors()]
    controls = []
    for name, reason in CONTROLS.items():
        try:
            _run_case(codes, points, vectors()[-1], name)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "empty string incidental control " + name + ": " + str(exc),
            )
            controls.append(dict(name=name, rejected=True, reason=reason))
        else:
            raise ConformanceError("empty string control survived: " + name)
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "empty string executable changed",
    )
    n = len(observations)
    executed = sorted({pc for o in observations for pc in o["trace_rvas"]})
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=copy.deepcopy(sources["program_facts"]["identity"]),
        source_receipts=identities,
        engine=dict(
            name="Unicorn",
            version="2.1.4",
            architecture="x86_32",
            cpu_model=dict(id=19, name="UC_CPU_X86_HASWELL"),
        ),
        body=dict(
            ranges=[
                dict(
                    start_rva="0x000080d0",
                    exclusive_end_rva="0x000081f0",
                    sha256=BODY_SHA256,
                )
            ],
            points=points,
        ),
        vectors=vectors(),
        executed_rvas=executed,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=n,
            external_cases=n // 2,
            record_copy_cases=n // 2,
            loaded_sites=119,
            loaded_bytes=288,
            executed_sites=len(executed),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            memory_events=sum(o["memory_event_count"] for o in observations),
            source_preserved_bytes=24 * n,
            destination_written_bytes=5 * n,
            destination_preserved_bytes=19 * n,
            xmm_preserved_cases=n,
            child_calls=0,
            allocation_requests=0,
            copy_requests=0,
            free_requests=0,
            opaque_instructions=0,
            accounting_promotions=0,
            controls=len(controls),
        ),
        scope=dict(
            claim="Finite disjoint inline empty-string copy with offset0 and maximumFFFFFFFF",
            premises=[
                "Exact96 recipes with crossing source and destination pages and destination old sizes zero seven and fifteen",
                "Source capacity15 and terminator0 are domain premises not native reads; only source size is read",
                "Destination initialsize is a domain premise not a native read; destination capacity is read twice",
                "One CPU19 machine executes exact33 instructions17 accesses with all8XMM and full pages preserved outside five destination bytes and saved stack",
            ],
            not_claimed=[
                "Actual record-copy caller or AddMove execution general strings alias growth nonempty copy allocator ownership failure unwind gameplay",
                "Injected event and trace record mutations do not prove represented native execution",
            ],
        ),
    )
    common._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    def run():
        common._validate_json_tree(evidence, "evidence")
        identities = _preflight(sources)
        _require(
            type(evidence) is dict
            and evidence.get("analysis_kind") == ANALYSIS_KIND
            and _canonical_sha256(evidence) == SEALED_SHA256
            and _same_packet(evidence["source_receipts"], identities),
            "sealed empty string receipt differs",
        )
        common._assert_publication_safe(evidence)
        return dict(
            status="structurally_verified",
            evidence_sha256=SEALED_SHA256,
            summary=copy.deepcopy(evidence["summary"]),
        )

    return _normalize(run)


def build_conformance(executable, sources):
    def run():
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_conformance(executable, evidence, sources):
    def run():
        validate_structure(evidence, sources)
        _require(
            _same_packet(_build_unsealed(executable, sources), evidence),
            "empty string native rebuild differs",
        )
        return dict(
            status="verified",
            evidence_sha256=SEALED_SHA256,
            summary=copy.deepcopy(evidence["summary"]),
        )

    return _normalize(run)


def encode_conformance(value):
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
