"""Finite continuous default movement record with seven empty-string helpers."""

from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from src.observatory import native_assertion_helper_fill_conformance as common
from src.observatory import native_movement_effect_record_default_semantics as model

BASE, EXE_SHA256 = common.BASE, common.EXE_SHA256
ANALYSIS_KIND = "pe_native_movement_effect_record_default_conformance"
SEALED_SHA256 = "942fc246105c941a46ac73e7be432acdacad1428322888b76c0164aca49e673f"
SOURCE_PINS = dict(model.SOURCE_PINS)
REGISTERS, XMM = model.REGISTERS, model.XMM
STACK, HEAP_PAGE, FEATURE_PAGE, LITERAL_PAGE = (
    0x30000000,
    0x10000000,
    0x893000,
    0x80D000,
)
RETURN, PARENT_RETURN = 0x04000000, BASE + 0x257397
POINTS_SHA256 = "14102b9cd0505d7c23fd0b31cab4d1d2865c0920cac89a37e976c2b571f95469"
BODIES = ((0x7FD0, 245), (0x1999A0, 669))
VECTOR_KEYS = {"alignment", "profile", "storage"}
FIXTURE_KEYS = {"pages", "registers", "xmm", "return_address", "entry_flags"}
EXPECTED_KEYS = {
    "record_address",
    "record_bytes",
    "argument",
    "registers",
    "xmm",
    "pages",
    "events",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "trace_rvas",
    "string_boundaries",
}
BOUNDARY_KEYS = {
    "name",
    "index",
    "registers",
    "xmm",
    "pages",
    "events",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
}
_canonical_sha256, _canonical_bytes = common._canonical_sha256, common._canonical_bytes


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


_read, _write, _pages = model._read, model._write, model._pages


def _page_hashes(pages):
    return {
        f"0x{p:08x}": hashlib.sha256(data).hexdigest()
        for p, data in sorted(pages.items())
    }


def vectors():
    return [
        dict(alignment=a, profile=p, storage=s)
        for a in range(16)
        for p in range(3)
        for s in ("heap", "parent_local")
    ]


def _checked_vector(vector):
    _require(
        type(vector) is dict
        and set(vector) == VECTOR_KEYS
        and all(type(k) is str for k in vector)
        and type(vector["alignment"]) is int
        and type(vector["profile"]) is int
        and type(vector["storage"]) is str
        and vector in vectors(),
        "outside fixed default record domain",
    )


def _fixture(vector):
    _checked_vector(vector)
    a, p = vector["alignment"], vector["profile"]
    pages = {
        page: bytearray(bytes((i * 29 + j * 17 + p * 53) & 255 for j in range(4096)))
        for i, page in enumerate(
            (0, STACK, STACK + 4096, HEAP_PAGE, FEATURE_PAGE, LITERAL_PAGE)
        )
    }
    g = STACK + 4096 + a
    r = HEAP_PAGE + 0x800 + a if vector["storage"] == "heap" else g + 0x148
    stop = RETURN if vector["storage"] == "heap" else PARENT_RETURN
    cookie = (0x19A51C73 ^ (p * 0x2468ACE)) & 0xFFFFFFFF
    seh = (0x11112222 ^ (p * 0x1020304)) & 0xFFFFFFFF
    for address, word in ((0, seh), (model.COOKIE, cookie), (g, stop), (g + 4, 0)):
        _write(pages, address, word.to_bytes(4, "little"))
    _write(pages, model.LITERAL, b"\0")
    regs = {
        name: (0x12345678 + i * 0x11111111 + p * 0x1234) & 0xFFFFFFFF
        for i, name in enumerate(REGISTERS)
    }
    regs.update(ecx=r, esp=g)
    xmm = {
        name: int.from_bytes(
            bytes((i * 19 + j * 41 + p * 73) & 255 for j in range(16)), "little"
        )
        for i, name in enumerate(XMM)
    }
    return dict(
        pages=_pages(pages),
        registers=regs,
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
            "default record fixture differs",
        )
        result = model.apply(**fixture)
        _require(
            type(result) is dict and set(result) == EXPECTED_KEYS,
            "default record model schema differs",
        )
        _require(
            type(result["events"]) is list
            and len(result["events"]) == 217
            and type(result["trace_rvas"]) is list
            and len(result["trace_rvas"]) == 356,
            "default record model path differs",
        )
        g, r = fixture["registers"]["esp"], fixture["registers"]["ecx"]
        cookie = int.from_bytes(_read(fixture["pages"], model.COOKIE, 4), "little")
        wanted = dict(
            record_address=r,
            argument=0,
            registers=dict(
                fixture["registers"], eax=r, ecx=cookie ^ (g - 4), esp=g + 8
            ),
            xmm=fixture["xmm"],
            flags=0x85,
            flag_mask=0x8D5,
            df=0,
            endpoint=fixture["return_address"],
        )
        _require(
            _same_packet({k: result[k] for k in wanted}, wanted),
            "default record model ABI differs",
        )
        record = bytearray(_read(fixture["pages"], r, 308))
        written = set()
        defaults = (
            (0, 0xFFFFFFFF, 4),
            (4, 0xFFFFFFFF, 4),
            (8, 0, 4),
            (12, 4, 4),
            (16, 0, 4),
            (20, 0, 1),
            (24, 0, 4),
            (28, 0, 4),
            (32, 0, 4),
            (36, 0, 4),
            (40, 0, 4),
            (44, 0, 4),
            (48, 0, 2),
            (52, 2, 4),
            (0x98, 0, 4),
            (0x9C, 0xFFFFFFFF, 4),
            (0xA0, 0xFFFFFFFF, 4),
            (0xBC, 2, 4),
            (0xC0, 2, 4),
            (0xC4, 0, 4),
            (0xC8, 0, 4),
            (0xCC, 0, 4),
            (0xD0, 0, 4),
            (0xD4, 0, 4),
            (0xD8, 0, 4),
            (0xDC, 10, 4),
            (0x110, 0xFFFFFFFF, 4),
            (0x114, 0xFFFFFFFF, 4),
            (0x130, 3, 4),
        )
        for offset in (0x38, 0x50, 0x68, 0x80, 0xA4, 0xE0, 0xF8, 0x118):
            defaults += ((offset, 0, 1), (offset + 16, 0, 4), (offset + 20, 15, 4))
        for offset, value, width in defaults:
            record[offset : offset + width] = value.to_bytes(width, "little")
            written.update(range(offset, offset + width))
        _require(
            len(written) == 183
            and type(result["record_bytes"]) is bytes
            and result["record_bytes"] == bytes(record),
            "default record model field or padding differs",
        )
        memory = {p: bytearray(data) for p, data in fixture["pages"].items()}
        for event in result["events"]:
            _require(
                type(event) is dict
                and set(event) == {"access", "address", "width", "value"}
                and type(event["access"]) is str
                and event["access"] in ("read", "write")
                and type(event["address"]) is int
                and type(event["width"]) is int
                and event["width"] in (1, 2, 4)
                and type(event["value"]) is int
                and 0 <= event["value"] < 2 ** (8 * event["width"]),
                "default record model event differs",
            )
            payload = event["value"].to_bytes(event["width"], "little")
            if event["access"] == "write":
                _write(memory, event["address"], payload)
            else:
                _require(
                    _read(memory, event["address"], event["width"]) == payload,
                    "default record model read differs",
                )
        _require(
            _same_packet(result["pages"], _pages(memory))
            and _read(result["pages"], r, 308) == bytes(record),
            "default record model full pages differ",
        )
        _require(
            type(result["string_boundaries"]) is list
            and len(result["string_boundaries"]) == 14,
            "default record model boundary count differs",
        )
        for i, row in enumerate(result["string_boundaries"]):
            _require(
                type(row) is dict
                and set(row) == BOUNDARY_KEYS
                and type(row["index"]) is int
                and row["index"] == i // 2
                and row["name"] == ("entry" if i % 2 == 0 else "return"),
                "default record model boundary schema differs",
            )
        return copy.deepcopy(result)

    return _normalize(run)


def _preflight(sources):
    def run():
        _require(
            type(sources) is dict and set(sources) == set(SOURCE_PINS),
            "default record source partition differs",
        )
        common._validate_json_tree(sources, "sources")
        result = {
            key: common._source_identity(sources[key], *pin, key)
            for key, pin in SOURCE_PINS.items()
        }
        identity = sources["program_facts"]["identity"]
        _require(
            identity["executable_sha256"] == EXE_SHA256
            and _same_packet(identity, sources["movement_binding"]["build_identity"]),
            "default record source build differs",
        )
        return result

    return _normalize(run)


def _checked_code_packet(codes, points):
    def run():
        _require(
            type(codes) is dict
            and all(type(k) is int for k in codes)
            and set(codes) == dict(BODIES).keys()
            and type(points) is list
            and _canonical_sha256(points) == POINTS_SHA256,
            "default record direct code identity differs",
        )
        allowed = {}
        for start, size in BODIES:
            _require(
                type(codes[start]) is bytes
                and len(codes[start]) == size
                and hashlib.sha256(codes[start]).hexdigest()
                == model.BODY_PINS[start][1],
                "default record direct body differs",
            )
            cursor = start
            for point in (
                p for p in points if start <= int(p["rva"], 16) < start + size
            ):
                _require(
                    type(point) is dict
                    and set(point) == {"rva", "size", "sha256"}
                    and type(point["size"]) is int
                    and point["size"] > 0,
                    "default record direct point differs",
                )
                pc = int(point["rva"], 16)
                _require(
                    pc == cursor
                    and pc + point["size"] <= start + size
                    and hashlib.sha256(
                        codes[start][pc - start : pc - start + point["size"]]
                    ).hexdigest()
                    == point["sha256"],
                    "default record direct bytes differ",
                )
                allowed[pc] = point
                cursor += point["size"]
            _require(cursor == start + size, "default record direct extent differs")
        _require(len(allowed) == len(points), "default record direct partition differs")
        return allowed

    return _normalize(run)


def _load_code(data, image, sources):
    def run():
        _preflight(sources)
        _require(
            hashlib.sha256(data).hexdigest() == EXE_SHA256 and image.image_base == BASE,
            "default record executable differs",
        )
        codes = {}
        points = []
        for start, size in BODIES:
            rows = common._decode_body(data, image, sources["program_facts"], start)
            codes[start] = b"".join(bytes(row.bytes) for row in rows)
            points.extend(common._point(row) for row in rows)
        points.sort(key=lambda p: int(p["rva"], 16))
        _checked_code_packet(codes, points)
        offset = image.rva_span_to_file_offset(0x40DFDC, 1)
        _require(
            offset is not None and data[offset : offset + 1] == b"\0",
            "default record complete literal differs",
        )
        return codes, points

    return _normalize(run)


CONTROLS = {
    **{
        name: "default record string boundary differs"
        for name in (
            "entry_gpr",
            "entry_xmm",
            "entry_flags",
            "entry_df",
            "entry_page",
            "return_gpr",
            "return_xmm",
            "return_flags",
            "return_df",
            "return_page",
        )
    },
    **{
        name: "default record ordered memory differs"
        for name in ("source_word", "length_word", "capacity_word")
    },
    **{
        name: "default record final pages differ"
        for name in (
            "field",
            "padding",
            "stack_ancestor",
            "stack_padding",
            "seh",
            "cookie",
            "literal",
            "heap_padding",
        )
    },
    **{
        name: "default record final ABI differs"
        for name in (
            "final_gpr",
            "final_xmm",
            "final_flags",
            "final_df",
            "final_endpoint",
        )
    },
    **{
        name: "default record final events differ"
        for name in ("missing_read_record", "restored_write_record")
    },
    "trace_record": "default record final native path differs",
}


def _run_case(codes, points, vector, negative=None, *, capture=None):
    _require(
        negative is None or type(negative) is str and negative in CONTROLS,
        "invalid default record control",
    )
    fixture = _fixture(vector)
    wanted = _expected(vector, fixture)
    allowed = _checked_code_packet(codes, points)
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "default record reviewed Unicorn required")
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    machine.ctl_set_cpu_model(19)
    _require(machine.ctl_get_cpu_model() == 19, "default record CPU differs")
    stop = fixture["return_address"]
    g = fixture["registers"]["esp"]
    r = fixture["registers"]["ecx"]
    code_pages = {
        (BASE + pc) & ~4095
        for start, size in BODIES
        for pc in range(start, start + size)
    } | {stop & ~4095}
    _require(
        not code_pages.intersection(fixture["pages"]), "default record mappings overlap"
    )
    for page in sorted(code_pages):
        machine.mem_map(page, 4096)
        machine.mem_write(page, bytes([0xCC]) * 4096)
    for page, data in fixture["pages"].items():
        machine.mem_map(page, 4096)
        machine.mem_write(page, data)
    for start, data in codes.items():
        machine.mem_write(BASE + start, data)
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
            "default record escaped selected code",
        )
        if len(boundaries) == 1:
            if negative == "source_word" and pc == 0x7FD4:
                flip(g - 36)
            if negative == "length_word" and pc == 0x8036:
                flip(g - 32)
            if negative == "capacity_word" and pc == 0x7FDE:
                flip(r + 0x38 + 20)
        if len(boundaries) < 14:
            expected = wanted["string_boundaries"][len(boundaries)]
            if address == expected["endpoint"]:
                role = expected["name"]
                if expected["index"] == 6:
                    if negative == role + "_gpr":
                        m.reg_write(ids["edx"], m.reg_read(ids["edx"]) ^ 1)
                    if negative == role + "_xmm":
                        m.reg_write(xmm_ids["xmm7"], m.reg_read(xmm_ids["xmm7"]) ^ 1)
                    if negative in (role + "_flags", role + "_df"):
                        m.reg_write(
                            x.UC_X86_REG_EFLAGS,
                            m.reg_read(x.UC_X86_REG_EFLAGS)
                            ^ (1 if negative == role + "_flags" else 0x400),
                        )
                    if negative == role + "_page":
                        flip(r + 0x15)
                flags = m.reg_read(x.UC_X86_REG_EFLAGS)
                actual = dict(
                    registers={name: m.reg_read(i) for name, i in ids.items()},
                    xmm={name: m.reg_read(i) for name, i in xmm_ids.items()},
                    pages={
                        page: bytes(m.mem_read(page, 4096)) for page in fixture["pages"]
                    },
                    events=events,
                    flags=flags & 0x8D5,
                    flag_mask=0x8D5,
                    df=(flags >> 10) & 1,
                    endpoint=address,
                    name=expected["name"],
                    index=expected["index"],
                )
                _require(
                    _same_packet(actual, expected),
                    "default record string boundary differs",
                )
                boundaries.append(
                    dict(
                        name=role,
                        index=expected["index"],
                        registers=actual["registers"],
                        xmm=actual["xmm"],
                        eflags=flags,
                        flags=actual["flags"],
                        flag_mask=0x8D5,
                        df=actual["df"],
                        endpoint=address,
                        pages_sha256=_page_hashes(actual["pages"]),
                        events_sha256=_canonical_sha256(events),
                    )
                )
        trace.append(f"0x{pc:08x}")
        _require(
            trace == wanted["trace_rvas"][: len(trace)],
            "default record native path differs",
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
            len(events) < 217 and _same_packet(row, wanted["events"][len(events)]),
            "default record ordered memory differs",
        )
        events.append(row)

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    machine.emu_start(BASE + 0x1999A0, 0, count=10000)
    corrupt = dict(
        field=r + 12,
        padding=r + 0x15,
        stack_ancestor=g + 8,
        stack_padding=g - 60,
        seh=0,
        cookie=model.COOKIE,
        literal=model.LITERAL,
        heap_padding=HEAP_PAGE + 1,
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
                dict(access="write", address=r + 0x15, width=1, value=0),
                dict(
                    access="write",
                    address=r + 0x15,
                    width=1,
                    value=wanted["record_bytes"][0x15],
                ),
            ]
        )
    if negative == "trace_record":
        trace.append("0x00008014")
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    regs = {name: machine.reg_read(i) for name, i in ids.items()}
    xmm = {name: machine.reg_read(i) for name, i in xmm_ids.items()}
    pages = {page: bytes(machine.mem_read(page, 4096)) for page in fixture["pages"]}
    _require(
        _same_packet(regs, wanted["registers"])
        and _same_packet(xmm, wanted["xmm"])
        and flags & 0x8D5 == 0x85
        and flags & 0x400 == 0
        and machine.reg_read(x.UC_X86_REG_EIP) == stop,
        "default record final ABI differs",
    )
    _require(_same_packet(pages, wanted["pages"]), "default record final pages differ")
    _require(
        _same_packet(events, wanted["events"]), "default record final events differ"
    )
    _require(
        _same_packet(trace, wanted["trace_rvas"]),
        "default record final native path differs",
    )
    _require(len(boundaries) == 14, "default record missing boundaries")
    result = dict(
        vector=dict(vector),
        registers=regs,
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
                "default record incidental control " + name + ": " + str(exc),
            )
            controls.append(dict(name=name, rejected=True, reason=reason))
        else:
            raise ConformanceError("default record control survived: " + name)
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "default record executable changed",
    )
    executed = sorted(
        {pc for observation in observations for pc in observation["trace_rvas"]}
    )
    n = len(observations)
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
                    start_rva=f"0x{start:08x}",
                    exclusive_end_rva=f"0x{start+size:08x}",
                    sha256=hashlib.sha256(codes[start]).hexdigest(),
                )
                for start, size in BODIES
            ],
            points=points,
        ),
        vectors=vectors(),
        executed_rvas=executed,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=n,
            heap_cases=n // 2,
            parent_local_cases=n // 2,
            loaded_sites=len(points),
            loaded_bytes=914,
            executed_sites=len(executed),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            memory_events=sum(o["memory_event_count"] for o in observations),
            string_calls=7 * n,
            string_boundaries=14 * n,
            record_bytes=308 * n,
            record_written_bytes=183 * n,
            record_padding_bytes=125 * n,
            allocation_requests=0,
            copy_requests=0,
            free_requests=0,
            opaque_instructions=0,
            accounting_promotions=0,
            controls=len(controls),
        ),
        scope=dict(
            claim="Finite continuous default308-byte record constructor and seven source-below-inline length-zero string assignments",
            premises=[
                "Exact96 recipes with heap or AddMove-shaped stack-local record and argument0",
                "One machine executes both exact selected bodies without API summaries or helper replay",
                "DF-clear entry246 and all8 nonzero XMM preserve; complete fields padding pages accesses and14 boundaries checked",
            ],
            not_claimed=[
                "Actual caller AddMove execution reachability ownership gameplay general strings record copy append destruction or AddCharge",
                "Cookie checking handler unwind or failure paths; constructor only saves a cookie",
                "Injected event or trace mutations do not claim represented instructions executed",
            ],
        ),
    )
    common._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    def run():
        common._validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            type(evidence) is dict
            and evidence.get("analysis_kind") == ANALYSIS_KIND
            and _canonical_sha256(evidence) == SEALED_SHA256
            and _same_packet(evidence["source_receipts"], ids),
            "sealed default record receipt differs",
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
            "default record rebuilt receipt differs",
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
