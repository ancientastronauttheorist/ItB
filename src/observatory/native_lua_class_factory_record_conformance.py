"""Continuous factory, initializer, self-linked record and successful native allocator."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import (
    native_lua_class_factory_initializer_prefix_conformance as parent,
)
from src.observatory import native_vector_allocation_conformance as allocation
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

factory = parent.factory
ANALYSIS_KIND = "pe_native_lua_class_factory_record_conformance"
SEALED_SHA256 = "94fb1682f5d89c131e6fe2eab62e926f0f4b71494d0fa12a5e89762dd8253a79"
HELPER, HELPER_END, END = 0x7C600, 0x7C629, 0x2EAD94
HELPER_SHA256 = "bf6d8eea868843a089fcc2b74af1426c5f71328fc018f028310cc48259f0dda1"
RECORD = 0x16000000
SOURCE_PINS = {
    **parent.SOURCE_PINS,
    "initializer_prefix": (parent.ANALYSIS_KIND, parent.SEALED_SHA256),
    "record_helper_chain": (
        "pe_native_self_linked_record_helper_chain",
        "994b4af188a8017d0dce172a53a9598b9cdf7a48d2faef1fbcbfa5ffcbbf2ddb",
    ),
    "allocation": (allocation.ANALYSIS_KIND, allocation.SEALED_SHA256),
}
ConformanceError, _require = factory.ConformanceError, factory._require


def vectors():
    return [
        dict(v, record_bias=bias, record_alignment=alignment)
        for v in factory.vectors()
        for bias in (0x100, 0xFFF)
        for alignment in (0, 7, 15, 31)
    ]


def _base_vector(vector):
    _require(
        type(vector) is dict
        and set(vector)
        == set(factory.vectors()[0]) | {"record_bias", "record_alignment"}
        and type(vector["record_bias"]) is int
        and type(vector["record_alignment"]) is int
        and vector["record_bias"] in (0x100, 0xFFF)
        and vector["record_alignment"] in (0, 7, 15, 31),
        "factory record vector differs",
    )
    return {
        k: v for k, v in vector.items() if k not in ("record_bias", "record_alignment")
    }


def _extend_fixture(vector, fixture):
    _base_vector(vector)
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    for page in (RECORD, RECORD + 4096, allocation.HEAP_GLOBAL & ~4095):
        _require(page not in pages, "factory record mapping overlaps")
        pages[page] = bytearray(bytes([0xC7 if page >= RECORD else 0xA5]) * 4096)
    factory._put(pages, allocation.IAT, factory.IMPORT)
    factory._put(pages, allocation.HEAP_GLOBAL, allocation.HEAP_HANDLE)
    return dict(
        fixture,
        pages={p: bytes(v) for p, v in pages.items()},
        record=RECORD + vector["record_bias"] + vector["record_alignment"],
    )


def _extend_expected(vector, fixture, original):
    from src.observatory import native_self_linked_record_semantics as model

    expected = parent._extend_expected(vector, fixture, original)
    logical = model.apply(pointer=fixture["record"])
    pages = {p: bytearray(v) for p, v in expected["pages"].items()}
    regs = dict(expected["registers"])
    events = list(expected["events"])

    def read(address, width=4):
        value = factory._raw(pages, address, width)
        events.append(dict(access="read", address=address, width=width, value=value))
        return value

    def write(address, value, width=4):
        value &= (1 << (8 * width)) - 1
        events.append(dict(access="write", address=address, width=width, value=value))
        factory._put(pages, address, value, width)

    def push(value):
        regs["esp"] -= 4
        write(regs["esp"], value)

    def pop(register):
        regs[register] = read(regs["esp"])
        regs["esp"] += 4

    helper_entry = regs["esp"]
    frame = regs["ebp"]
    push(24)
    push(BASE + 0x7C607)
    retry_entry = regs["esp"]
    push(regs["ebp"])
    regs["ebp"] = regs["esp"]
    push(read(regs["ebp"] + 8))
    push(BASE + 0x357507)
    # The native thunk saves and immediately restores the retry frame.
    push(regs["ebp"])
    regs["ebp"] = regs["esp"]
    pop("ebp")
    # Its jump enters the real heap wrapper, which stages a 24-byte request.
    push(regs["ebp"])
    regs["ebp"] = regs["esp"]
    push(regs["esi"])
    regs["esi"] = read(regs["ebp"] + 8)
    push(regs["esi"])
    push(0)
    push(read(allocation.HEAP_GLOBAL))
    _require(
        read(allocation.IAT) == factory.IMPORT, "factory record heap binding differs"
    )
    push(BASE + 0x389463)
    response = dict(eax=fixture["record"], ecx=0xA0000001, edx=0xB0000001, eflags=0x246)
    heap_call = dict(
        entry_esp=regs["esp"],
        continuation=BASE + 0x389463,
        arguments=[allocation.HEAP_HANDLE, 0, 24],
        entry_registers=dict(regs),
        response=response,
    )
    regs.update({r: response[r] for r in ("eax", "ecx", "edx")})
    regs["esp"] += 16
    pop("esi")
    pop("ebp")
    _require(
        read(regs["esp"]) == BASE + 0x357507, "factory record heap continuation differs"
    )
    regs["esp"] += 4
    pop("ecx")
    pop("ebp")
    _require(
        read(regs["esp"]) == BASE + 0x7C607, "factory record retry continuation differs"
    )
    regs["esp"] += 8  # RET followed by the helper's ADD ESP,4.
    _require(
        regs["esp"] == helper_entry
        and regs["ebp"] == frame
        and retry_entry == helper_entry - 8,
        "factory record native frame relation differs",
    )
    record = fixture["record"]
    stores = []
    for offset, width, value in (
        (0, 4, record),
        (4, 4, record),
        (8, 4, record),
        (12, 2, 0x0101),
    ):
        if offset in (4, 8):
            regs["ecx"] = record + offset
        write(record + offset, value, width)
        stores.append(dict(offset=offset, size=width, value=value))
    _require(
        stores == logical["ordered_writes"], "factory record logical stores differ"
    )
    _require(
        read(regs["esp"]) == BASE + parent.END,
        "factory record helper continuation differs",
    )
    regs["esp"] += 4
    push(0)
    write(regs["esi"], regs["eax"])
    _require(
        regs["ecx"] == logical["final_ecx"] and regs["esi"] == fixture["userdata"] + 52,
        "factory record logical return differs",
    )
    return dict(
        pages={p: bytes(v) for p, v in pages.items()},
        registers=regs,
        flags=logical["flags_value"],
        calls=expected["calls"],
        events=events,
        heap_calls=[heap_call],
        record=record,
        logical=dict(prefix=expected["logical"], record=logical),
    )


def _corruption(fixture, expected):
    return dict(
        parent._corruption(fixture, expected),
        record_link=fixture["record"],
        record_marker=fixture["record"] + 12,
        record_padding=fixture["record"] + 14,
        record_tail=fixture["record"] + 23,
        heap_global=allocation.HEAP_GLOBAL,
        stored_record=fixture["userdata"] + 52,
    )


def _preflight(sources):
    _require(
        set(sources) == set(SOURCE_PINS), "factory record source partition differs"
    )
    return {
        key: _source_identity(sources[key], *pin, key)
        for key, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    payload, points, continuation = parent._load_code(data, image, sources)
    owner = _decode_body(data, image, sources["program_facts"], HELPER)
    helper = b"".join(bytes(r.bytes) for r in owner)
    _require(
        len(helper) == 41 and hashlib.sha256(helper).hexdigest() == HELPER_SHA256,
        "self-linked helper differs",
    )
    codes = dict(continuation["codes"])
    codes[BASE + HELPER] = helper
    points += [_point(r) for r in owner]
    initializer = _decode_body(data, image, sources["program_facts"], parent.START)
    suffix = [r for r in initializer if BASE + parent.END <= r.address < BASE + END]
    _require(
        len(suffix) == 2 and sum(r.size for r in suffix) == 4,
        "factory record initializer resume differs",
    )
    codes[BASE + parent.END] = b"".join(bytes(r.bytes) for r in suffix)
    points += [_point(r) for r in suffix]
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for name in ("retry", "thunk", "heap_wrapper"):
        body = sources["allocation"]["bodies"][name]
        a, b = (int(body[k], 16) for k in ("entry_rva", "exclusive_end_rva"))
        offset = image.rva_to_file_offset(a)
        code = data[offset : offset + b - a]
        decoded = [_point(r) for r in decoder.disasm(code, BASE + a)]
        _require(
            len(code) == body["bytes"]
            and hashlib.sha256(code).hexdigest() == body["sha256"]
            and decoded == body["points"],
            "factory record allocation code differs",
        )
        codes[BASE + a] = code
        points += decoded
    return (
        payload,
        sorted(points, key=lambda p: int(p["rva"], 16)),
        dict(
            codes=codes,
            endpoint=BASE + END,
            instruction_count=89,
            extend_expected=_extend_expected,
            corruption=_corruption,
            heap_target=factory.IMPORT,
        ),
    )


def _run_case(payload, points, continuation, vector, negative=None):
    base = _base_vector(vector)
    installed = dict(
        continuation, extend_fixture=lambda v, f: _extend_fixture(vector, f)
    )
    result = factory._run_case(payload, points, base, negative, continuation=installed)
    result.update(
        vector=vector,
        initializer_instructions=39,
        self_linked_helper_instructions=16,
        allocation_native_instructions=34,
    )
    return result


CONTROLS = dict(
    parent.CONTROLS,
    **{
        kind: "factory protected memory differs"
        for kind in (
            "record_link",
            "record_marker",
            "record_padding",
            "record_tail",
            "heap_global",
            "stored_record",
        )
    },
    heap_request="factory heap request or ABI differs",
    heap_response="factory registers or defined flags differ",
)


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE,
        "exact factory record executable differs",
    )
    payload, points, continuation = _load_code(data, image, sources)
    observations = [_run_case(payload, points, continuation, v) for v in vectors()]
    union = sorted({pc for o in observations for pc in o["trace_rvas"]})
    required = set(sources["initializer_prefix"]["executed_rvas"])
    required.update(
        p["rva"]
        for p in points
        if HELPER <= int(p["rva"], 16) < HELPER_END
        or parent.END <= int(p["rva"], 16) < END
    )
    allocation_ranges = [
        allocation.BODIES[k] for k in ("retry", "thunk", "heap_wrapper")
    ]
    required.update(
        pc
        for pc in sources["allocation"]["executed_rvas"]
        if any(a <= int(pc, 16) < b for a, b in allocation_ranges)
    )
    _require(
        set(union) == required and len(required) == 160,
        "factory record normal coverage differs",
    )
    sample = next(
        v
        for v in vectors()
        if v["length"] == 16
        and not v["equal_pointers"]
        and v["profile"] == 1
        and v["record_bias"] == 0xFFF
        and v["record_alignment"] == 0
    )
    controls = []
    for kind, reason in CONTROLS.items():
        try:
            _run_case(payload, points, continuation, sample, kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "factory record control failed incidentally: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("factory record control survived: " + kind)
    ranges = [
        dict(
            start_rva=f"0x{factory.START:08x}",
            end_rva=f"0x{factory.END:08x}",
            sha256=factory.PREFIX_SHA256,
        )
    ]
    ranges += [
        dict(
            start_rva=f"0x{a-BASE:08x}",
            end_rva=f"0x{a-BASE+len(b):08x}",
            sha256=hashlib.sha256(b).hexdigest(),
        )
        for a, b in sorted(continuation["codes"].items())
    ]
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(ranges=ranges, points=points),
        vectors=vectors(),
        executed_rvas=union,
        negative_controls=controls,
        observations_sha256=_canonical_sha256(observations),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=len(observations),
            static_sites=len(points),
            executed_sites=len(union),
            instruction_bytes=len(payload)
            + sum(map(len, continuation["codes"].values())),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            supplied_api_calls=7 * len(observations),
            heap_calls=len(observations),
            controls=len(controls),
            initializer_instructions=39 * len(observations),
            self_linked_helper_instructions=16 * len(observations),
            allocation_native_instructions=34 * len(observations),
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            continuous_machine=True,
            supplied_apis=sorted(factory.SLOTS.keys() - {"lua_pushstring"})
            + ["HeapAlloc"],
            checked=[
                "Actual factory and initializer frames flow continuously through record helper and native allocation machinery",
                "One exact stdcall 24-byte HeapAlloc request with native continuations and API-entry GPRs",
                "All three native self links, two-byte marker and original padding through byte 23",
                "Actual returned record stored at userdata offset 52",
                "All ordered native memory events, full mapped pages, original ancestors, active FS chain, registers and defined flags",
            ],
            premises=[
                "Normal sealed factory Lua responses and disjoint initialized userdata",
                "One successful supplied HeapAlloc pointer into a valid 24-byte writable record",
                "Eight finite record geometries including a page-crossing DWORD",
            ],
            excluded=[
                "Actual allocator DLL instructions, heap ownership and allocation failure or retry errors",
                "Later initializer Lua calls, initializer return and remaining factory body",
                "Real Lua VM, exception dispatch, cookie verification and arbitrary domains",
                "No accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory record executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    _validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors(),
        "sealed factory record conformance differs",
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
        "exact factory record conformance differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
