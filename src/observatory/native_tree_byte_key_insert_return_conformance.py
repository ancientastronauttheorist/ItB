"""Whole native tree insertion with order-preserving variable-length byte keys."""

from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_tree_insert_return_conformance as insertion
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

ANALYSIS_KIND = "pe_native_tree_byte_key_insert_return_conformance"
SEALED_SHA256 = "ba76ee4b53ab92804bdeef182e6e95c42ad64fb98a80b546f7714d76e2a3a7ff"
SOURCE_PINS = {
    "program_facts": insertion.SOURCE_PINS["program_facts"],
    "insertion_return": (insertion.ANALYSIS_KIND, insertion.SEALED_SHA256),
}
START = insertion.START
ConformanceError, _require = insertion.ConformanceError, insertion._require
PROFILES = ("prefixes", "unsigned_boundary", "long_common_prefix")


def vectors():
    return [
        dict(v, key_profile=profile)
        for v in insertion.vectors()
        for profile in PROFILES
    ]


def encoded_keys(vector):
    profile = vector["key_profile"]
    _require(profile in PROFILES, "invalid byte-key profile")
    keys = sorted(set(vector["keys"] + [vector["key"]]))
    _require(len(keys) <= 32, "byte-key rank corpus exceeded")
    encode = {
        "prefixes": lambda rank: b"a" * rank,
        "unsigned_boundary": lambda rank: bytes([0x70 + rank]),
        "long_common_prefix": lambda rank: b"Q" * 63 + bytes([rank + 1]),
    }[profile]
    mapping = {key: encode(rank) for rank, key in enumerate(keys)}
    strings = [mapping[key] for key in keys]
    _require(
        strings == sorted(set(strings))
        and all(len(s) <= 64 and b"\0" not in s for s in strings),
        "byte-key encoding does not preserve strict order",
    )
    return mapping


def _fixture(vector):
    fixture = insertion._fixture(vector)
    mapping = encoded_keys(vector)
    cv = copy.deepcopy(fixture["construction_vector"])
    for node, original in zip(cv["nodes"], fixture["tree"]["nodes"]):
        node["key"] = list(mapping[original["key"]])
    cv["query"] = list(mapping[vector["key"]])
    strings = {
        insertion.leaf.KEYS + 256 * i: bytes(n["key"]) + b"\0"
        for i, n in enumerate(cv["nodes"])
    }
    strings[insertion.leaf.QUERY] = bytes(cv["query"]) + b"\0"
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    for address, payload in strings.items():
        for i, byte in enumerate(payload):
            a = address + i
            _require(a & ~4095 in pages, "byte string outside mapped storage")
            pages[a & ~4095][a & 4095] = byte
    fixture.update(
        construction_vector=cv,
        strings=strings,
        pages={p: bytes(v) for p, v in pages.items()},
    )
    return fixture


def _expected(vector, fixture):
    return insertion._expected(vector, fixture)


def _run_case(codes, points, vector, negative=None):
    return insertion._run_case(
        codes, points, vector, negative, fixture=_fixture(vector)
    )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "byte-key source partition differs")
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _load_code(data, image, sources):
    source = sources["insertion_return"]["body"]
    witnesses = {p["rva"]: p for p in source["points"]}
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    codes, points = {}, []
    for span in source["ranges"]:
        a, b = (int(span[k], 16) for k in ("start_rva", "end_rva"))
        offset = image.rva_to_file_offset(a)
        payload = data[offset : offset + b - a]
        part = [_point(r) for r in decoder.disasm(payload, BASE + a)]
        _require(
            sum(p["size"] for p in part) == b - a
            and all(witnesses.get(p["rva"]) == p for p in part),
            "byte-key selected native body differs",
        )
        codes[a] = payload
        points.extend(part)
    owner = [p for p in points if START <= int(p["rva"], 16) < 0x2E8284]
    return codes, points, owner


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256 and image.image_base == BASE, "exact PE differs")
    codes, points, owner = _load_code(data, image, sources)
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({p for o in observations for p in o["trace_rvas"]})
    _require(
        {p["rva"] for p in owner} <= set(union),
        "whole insertion owner coverage differs",
    )
    controls = []
    for kind, message in (
        ("ancestor", "insertion ancestor memory differs"),
        ("padding", "insertion protected memory differs"),
        ("seh", "insertion protected memory differs"),
        ("local_result", "insertion ordered events differ"),
        ("cookie", "insertion endpoint differs"),
    ):
        try:
            _run_case(codes, points, vectors()[0], kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "insertion control failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("insertion mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        engine=dict(
            name="Unicorn",
            version="2.1.4",
            architecture="x86_32",
            fs_profile="Synthetic flat FS base zero; no exception delivery",
        ),
        body=dict(
            ranges=[
                dict(start_rva=f"0x{a:08x}", end_rva=f"0x{a+len(v):08x}")
                for a, v in codes.items()
            ],
            points=points,
        ),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=union,
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            instruction_bytes=sum(map(len, codes.values())),
            static_sites=len(points),
            executed_sites=len(union),
            owner_sites=len(owner),
            allocated_returns=sum(o["allocate"] for o in observations),
            existing_returns=sum(not o["allocate"] for o in observations),
            key_profiles={
                profile: sum(v["key_profile"] == profile for v in vectors())
                for profile in PROFILES
            },
            modes={
                mode: sum(o["mode"] == mode for o in observations)
                for mode in ("empty", "minimum", "end", "interior", "existing")
            },
            heap_api_summaries=sum(len(o["heap_api_summaries"]) for o in observations),
            max_child_iterations=max(o["child_iterations"] for o in observations),
            max_child_rotations=max(o["child_rotations"] for o in observations),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Whole insertion owner on a finite variable byte-key corpus, existing pair or native successful construction hint rebalancing and inserted pair",
            premises=[
                "At most31 existing nodes generated by independent red-black insertion, Order-preserving prefix, unsigned-boundary and 64-byte common-prefix keys, disjoint writable fresh allocation",
                "One supplied successful HeapAlloc response on construction; DF clear and all other instructions native",
                "Sealed construction and hint oracles join in real ancestor memory; local result O-8 survives hint return; full mapped pages checked",
                "Normal synthetic FS registration and stable cookie, no exception delivery",
            ],
            frame_relation="Owner O; heap O-96; hint O-40; attachment O-132 and deepest balancing save O-148; final RET8 O+12",
            not_claimed=[
                "Allocation failure, arbitrary hints, fallback wrapper, exceptions or hardware execution",
                "All canonical trees, whole class owner or global accounting promotion",
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
        "sealed insertion return differs",
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
        "exact insertion return differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
