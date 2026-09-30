"""Continuous factory and initializer prefix, ending at the record-helper entry."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from src.observatory import native_lua_class_factory_prefix_conformance as factory
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

ANALYSIS_KIND = "pe_native_lua_class_factory_initializer_prefix_conformance"
SEALED_SHA256 = "abd888a364076edd037f460a0515b9586610218f9e5437aa4f67ab0cd972c47e"
START, END, HELPER = 0x2EACF0, 0x2EAD90, 0x7C600
BODY_SHA256 = "b681567bb998cd2c86267435483c7763394bd4df7843dcd8be7ecfb9e326d712"
PREFIX_SHA256 = "bc354d047d85c42203b24717d802ed07790d4ca97ee922544c25a2b231740fda"
SOURCE_PINS = {
    **factory.SOURCE_PINS,
    "factory_prefix": (factory.ANALYSIS_KIND, factory.SEALED_SHA256),
}
ConformanceError, _require = factory.ConformanceError, factory._require
vectors = factory.vectors


def _extend_expected(vector, fixture, parent):
    """Independent prefix frame and fixed offset-write laws from initial state."""
    from src.observatory import native_lua_class_initializer_prefix_semantics as model

    logical = model.apply(
        userdata=fixture["userdata"], name_pointer=fixture["second_pointer"]
    )
    pages = {p: bytearray(v) for p, v in parent["pages"].items()}
    regs = dict(parent["registers"])
    events = list(parent["events"])

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

    entry = regs["esp"]
    frame = entry - 4
    push(regs["ebp"])
    regs["ebp"] = frame
    push(0xFFFFFFFF)
    push(BASE + 0x3D107C)
    regs["eax"] = read(0)
    push(regs["eax"])
    push(regs["ecx"])
    for r in ("ebx", "esi", "edi"):
        push(regs[r])
    cookie = read(factory.COOKIE) ^ frame
    regs["eax"] = cookie
    push(cookie)
    regs["eax"] = frame - 12
    write(0, regs["eax"])
    regs["edi"] = regs["ecx"]
    write(frame - 16, regs["edi"])
    userdata = fixture["userdata"]
    field_writes = []

    def field(offset, value):
        write(userdata + offset, value)
        field_writes.append(dict(offset=offset, size=4, value=value))

    for offset, value in ((0, BASE + 0x49D1D4), (4, 0), (8, 0), (12, 0)):
        field(offset, value)
    regs["eax"] = read(frame + 12)
    write(frame - 4, 0)
    field(16, regs["eax"])
    for offset, value in (
        (20, 0),
        (24, 0xFFFFFFFE),
        (28, 0),
        (32, 0xFFFFFFFE),
        (36, 0),
        (40, 0xFFFFFFFE),
    ):
        field(offset, value)
    write(frame - 4, 3, 1)
    regs["esi"] = userdata + 52
    field(44, 1)
    write(frame + 12, regs["esi"])
    field(52, 0)
    field(56, 0)
    push(BASE + END)
    _require(
        field_writes == logical["ordered_offset_writes"],
        "initializer prefix logical fields differ",
    )
    _require(
        all(
            regs[r] == value
            for r, value in logical["native_handoff"]["registers"].items()
        ),
        "initializer prefix logical registers differ",
    )
    flags = (
        (4 if (cookie & 255).bit_count() % 2 == 0 else 0)
        | (0x80 if cookie & 0x80000000 else 0)
        | (0x40 if cookie == 0 else 0)
    )
    return dict(
        pages={p: bytes(v) for p, v in pages.items()},
        registers=regs,
        flags=flags,
        calls=parent["calls"],
        events=events,
        logical=dict(factory=parent["logical"], initializer_prefix=logical),
    )


def _corruption(fixture, expected):
    frame = expected["registers"]["ebp"]
    return dict(
        initializer_name=fixture["userdata"] + 16,
        initializer_sentinel=fixture["userdata"] + 24,
        initializer_unwritten=fixture["userdata"] + 48,
        outer_fs=fixture["entry"] - 16,
        inner_fs=frame - 12,
        overwritten_argument=frame + 12,
        helper_return=expected["registers"]["esp"],
    )


def _preflight(sources):
    _require(
        set(sources) == set(SOURCE_PINS), "factory initializer source partition differs"
    )
    return {
        key: _source_identity(sources[key], *pin, key)
        for key, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    payload, points = factory._load_code(data, image, sources)
    owner = _decode_body(data, image, sources["program_facts"], START)
    whole = b"".join(bytes(r.bytes) for r in owner)
    _require(
        len(whole) == 612 and hashlib.sha256(whole).hexdigest() == BODY_SHA256,
        "initializer owner differs",
    )
    selected = [r for r in owner if r.address < BASE + END]
    prefix = b"".join(bytes(r.bytes) for r in selected)
    _require(
        len(selected) == 37
        and len(prefix) == 160
        and hashlib.sha256(prefix).hexdigest() == PREFIX_SHA256,
        "initializer prefix differs",
    )
    return (
        payload,
        points + [_point(r) for r in selected],
        dict(
            codes={BASE + START: prefix},
            endpoint=BASE + HELPER,
            instruction_count=37,
            extend_expected=_extend_expected,
            corruption=_corruption,
        ),
    )


def _run_case(payload, points, continuation, vector, negative=None):
    return factory._run_case(
        payload, points, vector, negative, continuation=continuation
    )


CONTROLS = dict(
    factory.CONTROLS,
    **{
        kind: "factory protected memory differs"
        for kind in (
            "initializer_name",
            "initializer_sentinel",
            "initializer_unwritten",
            "outer_fs",
            "inner_fs",
            "overwritten_argument",
            "helper_return",
        )
    },
)


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE,
        "exact factory initializer executable differs",
    )
    payload, points, continuation = _load_code(data, image, sources)
    observations = [_run_case(payload, points, continuation, v) for v in vectors()]
    union = sorted({pc for o in observations for pc in o["trace_rvas"]})
    required = {
        p["rva"]
        for p in points
        if not any(a <= int(p["rva"], 16) < b for a, b in factory.ERROR_RANGES)
    }
    _require(
        set(union) == required and len(required) == 108,
        "factory initializer normal coverage differs",
    )
    sample = next(
        v
        for v in vectors()
        if v["length"] == 16 and not v["equal_pointers"] and v["profile"] == 1
    )
    controls = []
    for kind, reason in CONTROLS.items():
        try:
            _run_case(payload, points, continuation, sample, kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "factory initializer control failed incidentally: "
                + kind
                + ": "
                + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("factory initializer control survived: " + kind)
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{factory.START:08x}",
                    end_rva=f"0x{factory.END:08x}",
                    sha256=factory.PREFIX_SHA256,
                ),
                dict(
                    start_rva=f"0x{START:08x}",
                    end_rva=f"0x{END:08x}",
                    sha256=PREFIX_SHA256,
                ),
            ],
            initializer_owner_sha256=BODY_SHA256,
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
            instruction_bytes=len(payload) + 160,
            native_instructions=sum(len(o["trace_rvas"]) for o in observations),
            supplied_api_calls=7 * len(observations),
            controls=len(controls),
            initializer_instructions=37 * len(observations),
            self_linked_helper_instructions=0,
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            continuous_machine=True,
            supplied_apis=sorted(factory.SLOTS.keys() - {"lua_pushstring"}),
            checked=[
                "Actual factory handoff flows directly into initializer native prefix",
                "Independent ordered fixed-offset userdata writes and preserved untouched fields",
                "Second string pointer stored at userdata offset 16",
                "Nested active FS registrations, original ancestors and overwritten second-argument cell",
                "Exact memory events, pages, seven API frames, registers and defined flags",
                "Stop at self-linked helper entry before its first instruction",
            ],
            premises=[
                "Normal supplied Lua contracts and nonzero userdata from the sealed factory prefix",
                "Disjoint valid synthetic userdata writable through offset 59",
            ],
            excluded=[
                "Self-linked helper, allocation retry and heap ownership",
                "Remaining initializer Lua calls, initializer return and remaining factory body",
                "Real Lua VM, exception dispatch, cookie verification and error paths",
                "Untouched later fields and arbitrary memory domains",
                "No accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory initializer executable changed",
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
        "sealed factory initializer prefix conformance differs",
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
        "exact factory initializer prefix conformance differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
