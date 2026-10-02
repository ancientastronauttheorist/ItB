"""Finite installed copy48 native proof, separate from sealed generic corpora."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from src.observatory import native_installed_simd_copy48_semantics as model
from src.observatory import native_short_simd_copy_semantics as generic_semantics
from src.observatory import native_short_simd_copy_conformance as generic_native
from src.observatory import native_assertion_helper_fill_conformance as common

BASE, EXE_SHA256 = common.BASE, common.EXE_SHA256
ANALYSIS_KIND = "pe_native_installed_simd_copy48_conformance"
SEALED_SHA256 = "cc7ba0512777a3d8ed06c5c720857d364296935fcaeb703ca9221938c7ca7cf7"
SOURCE_PINS = {
    "program_facts": generic_semantics.SOURCE_PINS["program_facts"],
    "short_simd_semantics": (
        generic_semantics.ANALYSIS_KIND,
        generic_semantics.SEALED_SHA256,
    ),
    "short_simd_conformance": (
        generic_native.ANALYSIS_KIND,
        generic_native.SEALED_SHA256,
    ),
}
START, RANGES = 0x36E580, model.RANGES
# Canonical SHA256 (including canonical LF) of the 59 ordered scalar-range
# point packets in the pinned generic semantics receipt, read as static JSON.
POINTS_SHA256 = "b0fc0cad3e399ba4b0d9f0f1e400b3fc299376898249f090be10b52d0f71ca07"
REGISTERS, XMM = model.REGISTERS, model.XMM
FEATURE_PAGE, FEATURE, FEATURE_WORD = (
    model.FEATURE_PAGE,
    model.FEATURE,
    model.FEATURE_WORD,
)
STACK, DATA, RETURN = 0x30000000, 0x06002000, 0x04000000
FIXTURE_KEYS = {
    "pages",
    "registers",
    "xmm",
    "source",
    "destination",
    "return_address",
    "entry_flags",
}
_canonical_bytes, _canonical_sha256 = common._canonical_bytes, common._canonical_sha256


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
        return set(left) == set(right) and all(
            _same_packet(left[key], right[key]) for key in left
        )
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(
            _same_packet(a, b) for a, b in zip(left, right)
        )
    return left == right


def vectors():
    return [dict(alignment=a, profile=p) for a in range(16) for p in range(3)]


def geometry(vector):
    _require(
        type(vector) is dict and set(vector) == {"alignment", "profile"},
        "invalid installed copy48 vector schema",
    )
    _require(
        all(type(value) is int for value in vector.values()) and vector in vectors(),
        "outside finite installed copy48 corpus",
    )
    a = vector["alignment"]
    return dict(
        entry=STACK + 0x1000 + a, source=DATA + 0x800 + a, destination=DATA + 0x2800 + a
    )


def _fixture(vector):
    g = geometry(vector)
    profile = vector["profile"]
    pages = {
        page: bytearray(
            ((i * (17 + profile * 12) + (i >> 3) + (page >> 12) + 73 * profile) ^ 0xA7)
            & 255
            for i in range(4096)
        )
        for page in (DATA, DATA + 4096, DATA + 8192, STACK, STACK + 4096)
    }
    feature = bytearray([0x93] * 4096)
    feature[0xF28:0xF2C] = (0x12345678 + profile * 0x10101).to_bytes(4, "little")
    pages[FEATURE_PAGE] = feature
    registers = {
        name: (0xF1234567 - i * 0x1020307 + profile * 0x13579) & 0xFFFFFFFF
        for i, name in enumerate(REGISTERS)
    }
    registers["esp"] = g["entry"]
    xmm = {
        name: int.from_bytes(
            bytes((i * 17 + j * 37 + profile * 71 + 1) & 255 for j in range(16)),
            "little",
        )
        for i, name in enumerate(XMM)
    }

    def put(address, payload):
        for i, byte in enumerate(payload):
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte

    for offset, word in (
        (0, RETURN),
        (4, g["destination"]),
        (8, g["source"]),
        (12, 48),
    ):
        put(g["entry"] + offset, word.to_bytes(4, "little"))
    if profile == 2:
        payload = b"".join(
            word.to_bytes(4, "little")
            for word in ([0, 0x06000100] * 5 + [0, 0xD15C0048])
        )
    else:
        payload = bytes(
            ((i * (41 if profile == 0 else 53)) ^ (i >> 1) ^ (0xC3 + profile)) & 255
            for i in range(44)
        ) + (0x1122AA48 if profile == 0 else 0xEEDDCB48).to_bytes(4, "little")
    put(g["source"], payload)
    return dict(
        pages={page: bytes(data) for page, data in pages.items()},
        registers=registers,
        xmm=xmm,
        source=g["source"],
        destination=g["destination"],
        return_address=RETURN,
        entry_flags=0x246,
    )


def _expected(vector, fixture):
    geometry(vector)
    _require(
        type(fixture) is dict and set(fixture) == FIXTURE_KEYS,
        "invalid installed copy48 fixture schema",
    )
    _require(
        _same_packet(fixture, _fixture(vector)),
        "installed copy48 fixture recipe differs",
    )
    return _normalize(lambda: model.apply(**fixture))


def _page_hashes(pages):
    return {
        f"0x{page:08x}": hashlib.sha256(data).hexdigest()
        for page, data in sorted(pages.items())
    }


def _preflight(sources):
    def run():
        _require(
            type(sources) is dict and set(sources) == set(SOURCE_PINS),
            "installed copy48 source partition differs",
        )
        common._validate_json_tree(sources, "sources")
        identities = {
            key: common._source_identity(sources[key], kind, digest, key)
            for key, (kind, digest) in SOURCE_PINS.items()
        }
        identity = sources["program_facts"]["identity"]
        _require(
            identity["executable_sha256"] == EXE_SHA256
            and all(
                _same_packet(sources[key]["build_identity"], identity)
                for key in ("short_simd_semantics", "short_simd_conformance")
            ),
            "installed copy48 source build differs",
        )
        _require(
            sources["short_simd_conformance"]["source_semantics_sha256"]
            == generic_semantics.SEALED_SHA256
            and _same_packet(
                sources["short_simd_conformance"]["scalar_ranges"],
                sources["short_simd_semantics"]["scalar_ranges"],
            )
            and sources["short_simd_conformance"]["full_body_sha256"]
            == sources["short_simd_semantics"]["body"]["sha256"],
            "installed copy48 predecessor join differs",
        )
        _require(SOURCE_PINS == model.SOURCE_PINS, "installed copy48 model pins differ")
        return identities

    return _normalize(run)


def _load_code(data, image, sources):
    """Load only the two selected ranges, checking sealed point and byte identity."""

    def run():
        import capstone

        _preflight(sources)
        _require(
            type(data) is bytes
            and hashlib.sha256(data).hexdigest() == EXE_SHA256
            and image.image_base == BASE
            and capstone.__version__ == "5.0.7",
            "installed copy48 executable or decoder differs",
        )
        witnesses = sources["short_simd_semantics"]["scalar_ranges"]
        _require(
            [
                (int(row["start_rva"], 16), int(row["exclusive_end_rva"], 16))
                for row in witnesses
            ]
            == list(RANGES),
            "installed copy48 range partition differs",
        )
        codes, points = {}, []
        decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for (start, end), witness in zip(RANGES, witnesses):
            at = image.rva_to_file_offset(start)
            chunk = data[at : at + end - start]
            rows = list(decoder.disasm(chunk, BASE + start))
            decoded = [common._point(row) for row in rows]
            _require(
                len(chunk) == end - start == witness["bytes"]
                and sum(row.size for row in rows) == len(chunk)
                and _same_packet(decoded, witness["points"]),
                "installed copy48 exact point bytes differ",
            )
            codes[start] = chunk
            points.extend(decoded)
        _require(
            len(points) == 59
            and sum(map(len, codes.values())) == 169
            and len({point["rva"] for point in points}) == len(points)
            and _canonical_sha256(points) == POINTS_SHA256,
            "installed copy48 loaded geometry differs",
        )
        return codes, points

    return _normalize(run)


CONTROLS = {
    **{"gpr_" + name: "installed copy48 GPR relation differs" for name in REGISTERS},
    **{"xmm_" + name: "installed copy48 XMM relation differs" for name in XMM},
    "flags": "installed copy48 defined flags or DF differ",
    "df": "installed copy48 defined flags or DF differ",
    "final_dword": "installed copy48 full pages differ",
    "source_outside": "installed copy48 full pages differ",
    "destination_outside": "installed copy48 full pages differ",
    "stack_ancestor": "installed copy48 full pages differ",
    "feature_padding": "installed copy48 full pages differ",
    "caller_word": "installed copy48 actual caller words differ",
    "entry_df": "installed copy48 actual entry DF differs",
    "wide_order_record": "installed copy48 ordered memory events differ",
    "scalar_order_record": "installed copy48 ordered memory events differ",
    "missing_half_record": "installed copy48 ordered memory events differ",
    "scalar_value_record": "installed copy48 ordered memory events differ",
    "restored_write_record": "installed copy48 ordered memory events differ",
    "trace_record": "installed copy48 exact native path differs",
}


def _run_case(codes, points, vector, negative=None, *, capture=None):
    _require(
        negative is None or type(negative) is str and negative in CONTROLS,
        "invalid installed copy48 control",
    )
    fixture = _fixture(vector)
    expected = _expected(vector, fixture)
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "installed copy48 reviewed Unicorn required")
    _require(
        type(codes) is dict
        and set(codes) == {start for start, end in RANGES}
        and all(
            type(codes[start]) is bytes and len(codes[start]) == end - start
            for start, end in RANGES
        )
        and type(points) is list
        and len(points) == 59,
        "invalid installed copy48 code packet",
    )
    _require(
        _normalize(lambda: _canonical_sha256(points)) == POINTS_SHA256,
        "installed copy48 point identity differs",
    )
    allowed = {int(point["rva"], 16): point for point in points}
    _require(
        set(allowed) == set(generic_semantics.ORDER)
        and all(allowed[pc]["size"] == generic_semantics.SIZES[pc] for pc in allowed),
        "installed copy48 code partition differs",
    )
    for pc, point in allowed.items():
        start = next(start for start, end in RANGES if start <= pc < end)
        _require(
            hashlib.sha256(
                codes[start][pc - start : pc - start + point["size"]]
            ).hexdigest()
            == point["sha256"],
            "installed copy48 point bytes differ",
        )
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    code_pages = {BASE + (start & ~0xFFF) for start, end in RANGES}
    for page in sorted(code_pages):
        machine.mem_map(page, 4096)
        machine.mem_write(page, bytes([0xCC]) * 4096)
    for start, body in codes.items():
        machine.mem_write(BASE + start, body)
    for page, data in fixture["pages"].items():
        machine.mem_map(page, 4096)
        machine.mem_write(page, data)
    endpoint = fixture["return_address"]
    machine.mem_map(endpoint & ~0xFFF, 4096)
    machine.mem_write(endpoint, bytes([0xCC]))
    ids = {name: getattr(x, "UC_X86_REG_" + name.upper()) for name in REGISTERS}
    xmm_ids = {name: getattr(x, "UC_X86_REG_" + name.upper()) for name in XMM}
    for name, value in fixture["registers"].items():
        machine.reg_write(ids[name], value)
    for name, value in fixture["xmm"].items():
        machine.reg_write(xmm_ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, fixture["entry_flags"])
    entry, source, destination = (
        fixture["registers"]["esp"],
        fixture["source"],
        fixture["destination"],
    )
    visited, events = [], []

    def flip(address):
        machine.mem_write(address, bytes([machine.mem_read(address, 1)[0] ^ 1]))

    def on_code(m, address, size, user):
        pc = address - BASE
        _require(
            pc in allowed and size == allowed[pc]["size"],
            "installed copy48 escaped selected code",
        )
        if pc == START:
            if negative == "caller_word":
                flip(entry + 12)
            if negative == "entry_df":
                m.reg_write(
                    x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) | 0x400
                )
            _require(
                [
                    int.from_bytes(m.mem_read(entry + offset, 4), "little")
                    for offset in (0, 4, 8, 12)
                ]
                == [endpoint, destination, source, 48],
                "installed copy48 actual caller words differ",
            )
            _require(
                m.reg_read(x.UC_X86_REG_EFLAGS) & 0x400 == 0,
                "installed copy48 actual entry DF differs",
            )
        visited.append(f"0x{pc:08x}")
        _require(
            visited == expected["trace_rvas"][: len(visited)],
            "installed copy48 exact native path differs",
        )

    def on_memory(m, access, address, width, value, user):
        writing = access == uc.UC_MEM_WRITE
        pc = m.reg_read(x.UC_X86_REG_EIP) - BASE
        _require(width in (4, 8), "installed copy48 access width differs")
        if width == 8:
            halves = {
                0x36EA60: (False, source),
                0x36EA64: (False, source + 16),
                0x36EA69: (True, destination),
                0x36EA6D: (True, destination + 16),
            }
            _require(
                pc in halves
                and writing == halves[pc][0]
                and address in (halves[pc][1], halves[pc][1] + 8),
                "installed copy48 wide site differs",
            )
        index = len(events)
        actual = dict(
            access="write" if writing else "read",
            address=address,
            width=width,
            value=(
                value & ((1 << (width * 8)) - 1)
                if writing
                else int.from_bytes(m.mem_read(address, width), "little")
            ),
        )
        _require(
            index < len(model.EVENT_RVAS)
            and pc == model.EVENT_RVAS[index]
            and _same_packet(actual, expected["events"][index]),
            "installed copy48 ordered memory events differ",
        )
        events.append(actual)

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    machine.emu_start(BASE + START, endpoint, count=200)
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == endpoint,
        "installed copy48 did not return",
    )
    # Final machine and record controls are explicit injected corruption witnesses.
    # They do not claim the native path executed their represented writes or sites.
    if negative and negative.startswith("gpr_"):
        name = negative[4:]
        machine.reg_write(ids[name], machine.reg_read(ids[name]) ^ 1)
    if negative and negative.startswith("xmm_"):
        name = negative[4:]
        machine.reg_write(xmm_ids[name], machine.reg_read(xmm_ids[name]) ^ 1)
    if negative in ("flags", "df"):
        machine.reg_write(
            x.UC_X86_REG_EFLAGS,
            machine.reg_read(x.UC_X86_REG_EFLAGS)
            ^ (1 if negative == "flags" else 0x400),
        )
    final_corruptions = {
        "final_dword": destination + 44,
        "source_outside": source + 48,
        "destination_outside": destination + 48,
        "stack_ancestor": entry + 16,
        "feature_padding": FEATURE_PAGE + 1,
    }
    if negative in final_corruptions:
        flip(final_corruptions[negative])
    if negative == "wide_order_record":
        events[6], events[7] = events[7], events[6]
    if negative == "scalar_order_record":
        events[14], events[16] = events[16], events[14]
    if negative == "missing_half_record":
        del events[6]
    if negative == "scalar_value_record":
        events[20]["value"] ^= 1
    if negative == "restored_write_record":
        original = int.from_bytes(fixture["pages"][FEATURE_PAGE][:4], "little")
        events.extend(
            [
                dict(access="write", address=FEATURE_PAGE, width=4, value=original ^ 1),
                dict(access="write", address=FEATURE_PAGE, width=4, value=original),
            ]
        )
    if negative == "trace_record":
        visited.append("0x0036ea9d")
    actual = {name: machine.reg_read(reg) for name, reg in ids.items()}
    actual_xmm = {name: machine.reg_read(reg) for name, reg in xmm_ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    actual_pages = {
        page: bytes(machine.mem_read(page, 4096)) for page in fixture["pages"]
    }
    _require(
        _same_packet(actual, expected["registers"]),
        "installed copy48 GPR relation differs",
    )
    _require(
        _same_packet(actual_xmm, expected["xmm"]),
        "installed copy48 XMM relation differs",
    )
    _require(
        flags & 0x8C5 == 0x44 and flags & 0x400 == 0,
        "installed copy48 defined flags or DF differ",
    )
    _require(
        _same_packet(actual_pages, expected["pages"]),
        "installed copy48 full pages differ",
    )
    _require(
        _same_packet(events, expected["events"]),
        "installed copy48 ordered memory events differ",
    )
    _require(
        _same_packet(visited, expected["trace_rvas"]),
        "installed copy48 exact native path differs",
    )
    observation = dict(
        vector=dict(vector),
        registers=actual,
        xmm=actual_xmm,
        flags=flags & 0x8C5,
        flag_mask=0x8C5,
        df=0,
        endpoint=endpoint,
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        pages_sha256=_page_hashes(actual_pages),
        source_snapshot_sha256=hashlib.sha256(expected["source_snapshot"]).hexdigest(),
    )
    if capture is not None:
        capture(machine, dict(ids), copy.deepcopy(expected), copy.deepcopy(fixture))
    return observation


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _normalize(lambda: common._load_executable(executable))
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, vector) for vector in vectors()]
    controls = []
    for name, reason in CONTROLS.items():
        try:
            _run_case(codes, points, dict(alignment=15, profile=2), negative=name)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "installed copy48 incidental control: " + name + ": " + str(exc),
            )
            controls.append(dict(name=name, reason=reason, rejected=True))
        else:
            raise ConformanceError("installed copy48 control survived: " + name)
    union = sorted(
        {pc for observation in observations for pc in observation["trace_rvas"]}
    )
    _require(
        union == [f"0x{pc:08x}" for pc in sorted(set(model.TRACE))]
        and len(union) == 51,
        "installed copy48 finite coverage differs",
    )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{start:08x}",
                    exclusive_end_rva=f"0x{end:08x}",
                    bytes=end - start,
                    sha256=hashlib.sha256(codes[start]).hexdigest(),
                )
                for start, end in RANGES
            ],
            points=points,
        ),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=union,
        negative_controls=controls,
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        decoder=dict(name="Capstone", version="5.0.7"),
        summary=dict(
            cases=len(observations),
            static_sites=len(points),
            executed_sites=len(union),
            instruction_bytes=sum(map(len, codes.values())),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            copied_bytes=48 * len(observations),
            memory_events=26 * len(observations),
            wide_reads=4 * len(observations),
            wide_writes=4 * len(observations),
            scalar_tail_reads=4 * len(observations),
            scalar_tail_writes=4 * len(observations),
            controls=len(controls),
            supplied_api_calls=0,
            allocations=0,
            frees=0,
            accounting_promotions=0,
        ),
        scope=dict(
            checked=[
                "One installed copy48 machine with actual caller words and original source snapshot",
                "All eight GPRs and XMM registers final DWORD EDX and independently defined flags plus DF",
                "Only four MOVDQU sites admit their ordered eight-byte halves before four scalar pairs",
                "Exact trace and all supplied data stack ancestor and feature page bytes",
            ],
            premises=[
                "Destination strictly exceeds source plus 48 and all live extents are disjoint",
                "Entry DF is zero and complete retained feature page contains DWORD 93939393",
                "Forty-eight cases couple source destination and stack alignment zero through fifteen across three synthetic profiles",
            ],
            excluded=[
                "Resize growth class callback allocation ownership or whole-program promotion",
                "Backward overlap aligned SIMD other lengths and arbitrary independent alignment combinations",
                "Record controls do not establish execution of their injected represented stores or sites",
            ],
            event_contract="Unicorn 2.1.4 normalized eight-byte hook halves; architectural MOVDQU width is sixteen bytes",
            flags="44 under 8C5; AF unclaimed and DF checked separately as zero",
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "installed copy48 executable changed",
    )
    common._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    def run():
        common._validate_json_tree(evidence, "evidence")
        identities = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256
            and _same_packet(evidence["source_receipts"], identities)
            and _same_packet(evidence["vectors"], vectors()),
            "sealed installed copy48 receipt differs",
        )
        common._assert_publication_safe(evidence)
        return dict(
            status="structurally_verified",
            evidence_sha256=SEALED_SHA256,
            summary=evidence["summary"],
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
        actual = build_conformance(executable, sources)
        _require(
            _canonical_bytes(actual) == _canonical_bytes(evidence),
            "exact installed copy48 receipt differs",
        )
        return dict(
            status="verified", evidence_sha256=SEALED_SHA256, summary=actual["summary"]
        )

    return _normalize(run)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
