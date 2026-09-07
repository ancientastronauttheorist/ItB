"""Join deallocation guards, finite free protocol and the native return tail."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from src.observatory import native_vector_deallocation_semantics as guard
from src.observatory import native_heap_free_protocol as free
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

ANALYSIS_KIND = "pe_native_vector_deallocation_composition"
SEALED_SHA256 = "1ac61cf845b48c512ceee4efa67a9a8585d3018b2a018bc8187297b7b264e2ba"
SOURCE_PINS = {
    "program_facts": guard.SOURCE_PINS["program_facts"],
    "guard_semantics": (guard.ANALYSIS_KIND, guard.SEALED_SHA256),
    "free_protocol": (free.ANALYSIS_KIND, free.SEALED_SHA256),
}
U32 = 0xFFFFFFFF


class CompositionError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise CompositionError(message)


def frame_join(entry_esp):
    _require(
        type(entry_esp) is int and 32 <= entry_esp <= 2**32 - 16,
        "invalid ancestor frame",
    )
    s = entry_esp
    return dict(
        guard_frame=s - 4,
        free_argument=s - 8,
        free_entry=s - 12,
        free_frame=s - 16,
        heap_entry=s - 32,
        error_entry=s - 24,
        last_error_entry=s - 24,
        mapper_entry=s - 28,
        free_return=s - 8,
        guard_return=s + 4,
        protected_start=s - 32,
        protected_end=s + 16,
    )


def joined_spec(
    pointer,
    count,
    stride,
    raw_metadata,
    responses,
    allow_frontier=False,
    entry_esp=0x30001000,
):
    frame = frame_join(entry_esp)
    try:
        g = guard.deallocation_spec(pointer, count, stride, raw_metadata)
    except Exception as exc:
        raise CompositionError(str(exc)) from exc
    _require(
        type(responses) is list and type(allow_frontier) is bool,
        "invalid response contract",
    )
    metadata = (pointer - 4) & U32 if g["metadata_read"] else None
    if metadata is not None:
        protected = [
            (frame["protected_start"], frame["protected_end"]),
            *[(a, a + 4) for a in (free.HEAP_WORD, free.FREE_IAT, free.LAST_IAT)],
            (BASE + guard.START, BASE + guard.END),
            *[(BASE + a, BASE + b) for a, b in free.BODIES.items()],
        ]
        _require(
            all(metadata + 4 <= a or b <= metadata for a, b in protected),
            "metadata aliases composed protected storage",
        )
    if g["outcome"] != "free_frontier":
        _require(not responses, "guard frontier cannot consume free responses")
        return dict(outcome=g["outcome"], guard=g, free=None, frame=frame, result=None)
    try:
        f = free.free_protocol_spec(g["free_argument"], responses, allow_frontier)
    except Exception as exc:
        raise CompositionError(str(exc)) from exc
    if f["error_cell"] is not None:
        cell = f["error_cell"]
        ranges = [
            (frame["protected_start"], frame["protected_end"]),
            *[(a, a + 4) for a in (free.HEAP_WORD, free.FREE_IAT, free.LAST_IAT)],
            (BASE + guard.START, BASE + guard.END),
            *[(BASE + a, BASE + b) for a, b in free.BODIES.items()],
        ]
        if metadata is not None:
            ranges.append((metadata, metadata + 4))
        _require(
            cell + 4 <= 2**32 and all(cell + 4 <= a or b <= cell for a, b in ranges),
            "error cell aliases composed storage or wraps",
        )
    result = f["result"]
    if f["outcome"] == "null_return":
        result = g["quotient"] if g["byte_count"] < 4096 else pointer - raw_metadata
    return dict(
        outcome="free_frontier" if f["outcome"] == "frontier" else "normal_return",
        guard=g,
        free=f,
        frame=frame,
        result=result,
    )


def tail_case(entry_esp=0x30001000, seed=1, increment=4):
    """Three native tail operations, checked against fresh caller-frame equations."""
    frame_join(entry_esp)
    _require(type(seed) is int and 0 <= seed <= U32, "invalid tail seed")
    original_ebp = (0x12345678 + seed) & U32
    continuation = (0x87654321 + seed) & U32
    memory = {
        entry_esp - 8: 0xABCD,
        entry_esp - 4: original_ebp,
        entry_esp: continuation,
        entry_esp + 4: 0xDEAD,
    }
    sp = entry_esp - 8
    flags = guard._cmp_flags(0, 0)
    left = sp
    sp += increment
    value = (left + increment) & U32
    flags = dict(
        cf=int(left + increment > U32),
        pf=int((value & 255).bit_count() % 2 == 0),
        af=((left ^ increment ^ value) >> 4) & 1,
        zf=int(value == 0),
        sf=value >> 31,
        of=((~(left ^ increment) & (left ^ value)) >> 31) & 1,
    )
    _require(sp in memory, "tail pop outside frame")
    ebp = memory[sp]
    sp += 4
    _require(sp in memory, "tail return outside frame")
    ip = memory[sp]
    sp += 4
    _require(
        ebp == original_ebp and ip == continuation and sp == entry_esp + 4,
        "tail frame relation differs",
    )
    return dict(
        entry_esp=entry_esp,
        seed=seed,
        restored_ebp=ebp,
        return_address=ip,
        exit_esp=sp,
        flags=flags,
    )


def contracts():
    result = []
    for p, n, s, raw in (
        (0, 0, 8, None),
        (1, 1, 8, None),
        (0x7000020, 512, 8, 0x7000000),
        (32, 512, 8, 0),
        (0x7000021, 512, 8, None),
        (0x7000020, 512, 8, 0x7000020),
        (0x7000020, 512, 8, 0x7000000 - 4),
        (1, 0, 0, None),
        (1, 0x20000000, 8, None),
    ):
        g = guard.deallocation_spec(p, n, s, raw)
        patterns = (
            [([], False)]
            if g["outcome"] != "free_frontier" or g["free_argument"] == 0
            else [([], True), ([dict(kind="heap_free", eax=1)], False)]
        )
        if g["outcome"] == "free_frontier" and g["free_argument"]:
            seq = [
                dict(kind=k, eax=v)
                for k, v in (
                    ("heap_free", 0),
                    ("error", 0x6000101),
                    ("get_last_error", 5),
                    ("map_error", 12),
                )
            ]
            patterns += [(seq[:i], i < 4) for i in range(1, 5)]
        for responses, allow in patterns:
            for a in range(16):
                result.append(
                    joined_spec(p, n, s, raw, responses, allow, 0x30001000 + a)
                )
    return result


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    guard_rows = _decode_body(data, image, sources["program_facts"], guard.START)
    _require(
        [_point(r) for r in guard_rows] == sources["guard_semantics"]["body"]["points"],
        "guard witness differs",
    )
    bodies = []
    for start, end in free.BODIES.items():
        rows = _decode_body(data, image, sources["program_facts"], start)
        bodies.append(
            dict(
                entry_rva=f"0x{start:08x}",
                exclusive_end_rva=f"0x{end:08x}",
                bytes=sum(r.size for r in rows),
                nodes=len(rows),
                sha256=hashlib.sha256(
                    b"".join(bytes(r.bytes) for r in rows)
                ).hexdigest(),
                points=[_point(r) for r in rows],
            )
        )
    _require(
        sum(b["bytes"] for b in bodies) == 68 and sum(b["nodes"] for b in bodies) == 24,
        "free body partition differs",
    )
    _require(
        bodies == sources["free_protocol"]["bodies"], "free source witness join differs"
    )
    cases = contracts()
    tails = [tail_case(0x30001000 + a, s) for a in range(16) for s in (0, 1, U32)]
    try:
        tail_case(increment=8)
    except CompositionError:
        pass
    else:
        raise CompositionError("tail cleanup mutation survived")
    for cell in (0x3000100C, 0x30000FE1, 0x700001F, free.FREE_IAT):
        seq = [
            dict(kind=k, eax=v)
            for k, v in (
                ("heap_free", 0),
                ("error", cell),
                ("get_last_error", 5),
                ("map_error", 12),
            )
        ]
        try:
            joined_spec(0x7000020, 512, 8, 0x7000000, seq)
        except CompositionError:
            pass
        else:
            raise CompositionError("ancestor or metadata alias survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=ids,
        build_identity=sources["program_facts"]["identity"],
        guard_body=sources["guard_semantics"]["body"],
        free_bodies=bodies,
        tail_points=[_point(r) for r in guard_rows if r.address - BASE >= 0x7856],
        contracts_sha256=_canonical_sha256(cases),
        tails_sha256=_canonical_sha256(tails),
        summary=dict(
            contracts=len(cases),
            tail_cases=len(tails),
            static_bytes=159,
            static_nodes=53,
            normal_returns=sum(c["outcome"] == "normal_return" for c in cases),
            tail_mutations=1,
            alias_controls=4,
            accounting_promotions=0,
        ),
        scope=dict(
            premises=[
                "Guard arguments and metadata are stable; metadata avoids frame, global, IAT and code bytes; error cells avoid all ancestor frame bytes, metadata, globals, IAT cells and modeled code",
                "Free protocol external responses return normally with its declared conventions and memory preservation",
            ],
            frame_relation="Guard entry S gives free entry S-12 and deepest heap call S-32; full ancestor interval is from S-32 through S+16 exclusive; final guard return leaves S+4",
            flags_relation="All normal outcomes finish with six flags from ADD of S-8 and four, overriding the free-wrapper result flags",
            null_relation="A numeric guard may pass raw zero; inner null preserves guard EAX, quotient for small products or metadata distance for large products",
            not_claimed=[
                "Actual free effects, provenance, universal failure behavior or division faults",
                "Standalone integrated execution in this composition receipt or whole-program accounting promotion",
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
        and evidence["source_receipts"] == ids,
        "sealed composition differs",
    )
    _assert_publication_safe(evidence)
    return dict(
        status="structurally_verified",
        evidence_sha256=SEALED_SHA256,
        summary=evidence["summary"],
    )


def build_composition(executable, sources):
    result = _build_unsealed(executable, sources)
    validate_structure(result, sources)
    return result


def validate_composition(executable, evidence, sources):
    validate_structure(evidence, sources)
    _require(
        _canonical_bytes(build_composition(executable, sources))
        == _canonical_bytes(evidence),
        "exact composition differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_composition(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
