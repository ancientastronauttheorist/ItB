"""Continuous factory and initializer through the excluded context assertion call."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from src.observatory import native_lua_class_factory_conformance as full

factory, record, parent = full.factory, full.record, full.parent
BASE = full.BASE
ConformanceError, _require = full.ConformanceError, full._require
_canonical_sha256, _canonical_bytes = full._canonical_sha256, full._canonical_bytes
_validate_json_tree, _assert_publication_safe = (
    full._validate_json_tree,
    full._assert_publication_safe,
)
ANALYSIS_KIND = "pe_native_lua_class_factory_assertion_prefix_conformance"
SEALED_SHA256 = "c164d95f08507d66c26fae898a1f00dff84ce1db64a14b380122f66ed00ae59f"
END, BOUNDARY = 0x2EAE7B, BASE + 0x379CC2
SOURCE_PINS = {
    **full.SOURCE_PINS,
    "full_factory": (full.ANALYSIS_KIND, full.SEALED_SHA256),
}


def vectors():
    return full.vectors()


def _fixture(vector, fixture):
    extended = full._extend_fixture(vector, fixture)
    pages = {p: bytearray(v) for p, v in extended["pages"].items()}
    extended["spec"] = dict(extended["spec"], context_guard=0xFFFFFFFE)
    factory._put(pages, extended["spec"]["context_pointer"] + 12, 0xFFFFFFFE)
    return dict(extended, pages={p: bytes(v) for p, v in pages.items()})


def _extend_expected(vector, fixture, original):
    expected = full._extend_expected(vector, fixture, original, assertion_boundary=True)
    logical = expected["logical"]["factory"]
    sp = expected["registers"]["esp"]
    _require(
        sp
        == expected["registers"]["ebp"]
        + logical["frame"]["boundary_esp_delta_from_initializer_ebp"]
        and [factory._raw(expected["pages"], sp + 4 * i) for i in range(4)]
        == logical["frame"]["stack_words"],
        "factory assertion boundary model differs",
    )
    return expected


def _corruption(fixture, expected):
    outer = fixture["entry"] - 4
    inner = outer - 52
    return dict(
        full._corruption(fixture, expected),
        assertion_return=inner - 48,
        assertion_expression=inner - 44,
        assertion_file=inner - 40,
        assertion_scalar=inner - 36,
        context_guard_word=fixture["spec"]["context_pointer"] + 12,
    )


def _before_instruction(machine, address, negative, fixture, expected):
    if negative == "guard_response" and address == BASE + 0x2EAE64:
        machine.mem_write(
            fixture["spec"]["context_pointer"] + 12, (0xFFFFFFFD).to_bytes(4, "little")
        )


def _endpoint_mutation(machine, negative, fixture, expected, lua, ids):
    if negative == "lua_identity":
        lua.stack[-1] = ("userdata", fixture["userdata"] ^ 1)
    if negative == "boundary_register":
        machine.reg_write(ids["eax"], fixture["spec"]["context_pointer"] ^ 1)


CONTROLS = {
    k: v
    for k, v in full.CONTROLS.items()
    if k not in ("context_guard", "return_count", "closure_identity", "factory_return")
}
CONTROLS.update(
    {
        k: "factory protected memory differs"
        for k in (
            "assertion_return",
            "assertion_expression",
            "assertion_file",
            "assertion_scalar",
            "context_guard_word",
        )
    }
)
CONTROLS.update(
    guard_response="factory left normal prefix",
    boundary_register="factory registers or defined flags differ",
)


def _preflight(sources):
    _require(
        set(sources) == set(SOURCE_PINS),
        "factory assertion prefix source partition differs",
    )
    return {
        k: factory._source_identity(sources[k], *pin, k)
        for k, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    payload, points, continuation = full._load_code(data, image, sources)
    codes = {a: b for a, b in continuation["codes"].items() if a != BASE + parent.START}
    codes[BASE + parent.START] = continuation["codes"][BASE + parent.START][
        : END - parent.START
    ]
    payload = payload[: factory.END - factory.START]
    selected = [
        p
        for p in points
        if not (factory.END <= int(p["rva"], 16) < factory.START + 296)
        and not (END <= int(p["rva"], 16) < parent.START + 612)
    ]
    return (
        payload,
        selected,
        dict(
            codes=codes,
            endpoint=BOUNDARY,
            instruction_count=150,
            extend_expected=_extend_expected,
            corruption=_corruption,
            heap_target=factory.IMPORT,
            api_targets=full.TARGETS,
            flag_mask=0xCD5,
            excluded_ranges=full.EXCLUDED[:2],
            before_instruction=_before_instruction,
            endpoint_mutation=_endpoint_mutation,
        ),
    )


def _run_case(payload, points, continuation, vector, negative=None):
    rv = full._record_vector(vector)
    base = record._base_vector(rv)
    installed = dict(
        continuation,
        extend_fixture=lambda v, f: _fixture(vector, f),
        lua_observer=lambda v, f: full._Lua(base, f),
    )
    result = factory._run_case(payload, points, base, negative, continuation=installed)
    result.update(
        vector=vector,
        initializer_instructions=100,
        self_linked_helper_instructions=16,
        allocation_native_instructions=34,
    )
    return result


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = full._load_executable(Path(executable))
    _require(
        digest == full.EXE_SHA256 and image.image_base == BASE,
        "exact factory assertion prefix executable differs",
    )
    payload, points, continuation = _load_code(data, image, sources)
    observations = [_run_case(payload, points, continuation, v) for v in vectors()]
    union = sorted({r for o in observations for r in o["trace_rvas"]})
    required = set(sources["record_conformance"]["executed_rvas"])
    required.update(
        p["rva"]
        for p in points
        if record.END <= int(p["rva"], 16) < END
        and not any(a <= int(p["rva"], 16) < b for a, b in full.EXCLUDED[:2])
    )
    _require(
        set(union) == required and len(required) == 221,
        "factory assertion prefix coverage partition differs",
    )
    controls = []
    sample = next(
        v
        for v in vectors()
        if v["length"] == 16
        and not v["equal_pointers"]
        and v["profile"] == 1
        and v["record_bias"] == 0xFFF
        and v["record_alignment"] == 0
        and v["registry_profile"] == 2
    )
    for kind, reason in CONTROLS.items():
        try:
            _run_case(payload, points, continuation, sample, kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "factory assertion prefix control failed incidentally: "
                + kind
                + ": "
                + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("factory assertion prefix control survived: " + kind)
    codes = {BASE + factory.START: payload, **continuation["codes"]}
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{a-BASE:08x}",
                    end_rva=f"0x{a-BASE+len(b):08x}",
                    sha256=hashlib.sha256(b).hexdigest(),
                )
                for a, b in sorted(codes.items())
            ],
            points=points,
        ),
        vectors=vectors(),
        executed_rvas=union,
        negative_controls=controls,
        observations_sha256=_canonical_sha256(observations),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=len(observations),
            static_sites=len(points),
            executed_sites=len(union),
            instruction_bytes=sum(map(len, codes.values())),
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            supplied_api_calls=18 * len(observations),
            heap_calls=len(observations),
            initializer_instructions=100 * len(observations),
            assertion_boundaries=len(observations),
            controls=len(controls),
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            checked=[
                "Native factory, initializer, record helper and allocator execute continuously through context assertion call",
                "Guard minus two selects the actual three-word native assertion-helper boundary",
                "Independent reached Lua token trace, two registry references and userdata fields",
                "Ordered native events, all mapped pages and active nested FS chain",
            ],
            premises=[
                "Supplied normal cdecl Lua responses and one successful stdcall HeapAlloc response",
                "Readable compatible context with guard minus two",
            ],
            excluded=[
                "Assertion-helper execution or response, assertions, unwind and both function returns",
                "Expression and filename contents, later metatable or registry requests, closure creation",
                "Actual Lua VM or imported DLL behavior, cookie verification and accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory assertion prefix executable changed",
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
        "sealed factory assertion prefix conformance differs",
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
        "exact factory assertion prefix conformance differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
