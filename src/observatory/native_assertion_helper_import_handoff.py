"""Same-instance caller/fill/store composition to the exclusive import boundary."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from src.observatory import native_assertion_helper_caller_fill as caller
from src.observatory import native_assertion_helper_frame_stores as stores
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    UNICORN_VERSION,
    UNICORN_CORE_VERSION,
    CPU_MODEL,
    _canonical_bytes,
    _canonical_sha256,
    _source_identity,
    _validate_json_tree,
    _assert_publication_safe,
    _load_executable,
    _decode_body,
    _point,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_assertion_helper_import_handoff"
SEALED_SHA256 = "21ed5942d039ec0e16c94f40447f0e15bebea6d74298a1af448eb93f55ce7712"
PARENT, JOIN, STOP = caller.PARENT, caller.STOP, stores.STOP
SOURCE_PINS = dict(caller.SOURCE_PINS) | {
    "caller": (caller.ANALYSIS_KIND, caller.SEALED_SHA256),
    "stores": (stores.ANALYSIS_KIND, stores.SEALED_SHA256),
}
MATRIX = caller.MATRIX


class HandoffError(RuntimeError):
    """A sealed join, independent boundary specification, or replay differs."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise HandoffError(message)


def _normalize(fn: Any) -> Any:
    try:
        return fn()
    except HandoffError:
        raise
    except Exception as exc:
        raise HandoffError(str(exc)) from exc


def cases() -> list[tuple[int, int, int, int, int]]:
    return caller.cases()


def boundary_spec(frame: int, rep: int, simd: int) -> dict[str, int]:
    """Independent arithmetic for the declared caller matrix, with DF clear."""
    _require(
        type(frame) is int and caller.STACK + 0x2000 <= frame < caller.STACK + 0x2010,
        "frame outside finite matrix",
    )
    _require(
        type(rep) is int and type(simd) is int and rep in (0, 2) and simd in (0, 2),
        "dispatch outside finite matrix",
    )
    a = frame & 15
    # Final shared cleanup ADD ESP,24: compute status bits independently.
    left, right = frame - 836, 24
    result = (left + right) & 0xFFFFFFFF
    flags = (
        2
        | (int(left + right > 0xFFFFFFFF))
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | (int(((left & 15) + (right & 15)) > 15) << 4)
        | (int(result == 0) << 6)
        | ((result >> 31) << 7)
        | (int(bool((~(left ^ right) & (left ^ result)) & 0x80000000)) << 11)
    )
    return {
        "eax": frame - 800,
        "ecx": 0 if rep or not simd else (28 + a) % 32,
        "edx": 0x3456789A,
        "eflags": flags,
        "ebp": frame,
        "esp": result,
    }


def boundary_writers(rep: int, simd: int) -> dict[str, str]:
    return {
        "ecx": "0x0037099c" if rep else ("0x00370a41" if simd else "0x00370aa8"),
        "edx": "0x00370969",
        "eflags": "0x00379d76",
    }


def _preflight(sources: Mapping[str, Any]) -> dict[str, Any]:
    _validate_json_tree(sources, "sources")
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    ids = {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }
    caller._preflight({k: sources[k] for k in caller.SOURCE_PINS})
    stores._preflight({k: sources[k] for k in stores.SOURCE_PINS})
    _require(
        sources["stores"]["slice"]["start_rva"] == f"0x{JOIN:08x}"
        and sources["stores"]["slice"]["exclusive_stop_rva"] == f"0x{STOP:08x}",
        "store boundary join differs",
    )
    return ids


class _Continuation:
    def __init__(
        self,
        rows: Mapping[int, Any],
        grammar: Mapping[str, Any],
        vector: tuple,
        negative: bool = False,
    ):
        self.rows, self.grammar, self.vector, self.negative = (
            rows,
            grammar,
            vector,
            negative,
        )
        self.previous = None
        self.writers: dict[str, str] = {}

    def observe(self, uc: Any, pc: int) -> None:
        # Record the last dynamically executed declared writer, even when its
        # architectural result equals the previous value (not change detection).
        if self.previous is not None:
            row = self.rows[self.previous]
            for reg in row.regs_access()[1]:
                name = row.reg_name(reg)
                name = {"cl": "ecx", "cx": "ecx", "dl": "edx", "dx": "edx"}.get(
                    name, name
                )
                if name in ("ecx", "edx", "eflags"):
                    self.writers[name] = f"0x{self.previous:08x}"
        self.previous = pc

    def finish(self, uc: Any, frame: int, before: bytes) -> dict[str, Any]:
        import unicorn as u
        from unicorn import x86_const as x

        ids = {
            n: getattr(x, "UC_X86_REG_" + n.upper())
            for n in (
                "eax",
                "ecx",
                "edx",
                "ebx",
                "esi",
                "edi",
                "ebp",
                "esp",
                "eflags",
                "ss",
                "cs",
                "ds",
                "es",
                "fs",
                "gs",
            )
        }
        if self.negative:
            uc.reg_write(ids["ecx"], uc.reg_read(ids["ecx"]) ^ 1)
        boundary = {n: uc.reg_read(r) for n, r in ids.items()}
        spec = boundary_spec(frame, self.vector[1], self.vector[2])
        _require(
            all(boundary[n] == v for n, v in spec.items()), "handoff register differs"
        )
        _require(
            self.writers == boundary_writers(self.vector[1], self.vector[2]),
            "volatile writer provenance differs",
        )
        _require(
            all(boundary[n] == 0 for n in ("ss", "cs", "ds", "es", "fs", "gs")),
            "segment selectors differ",
        )
        values = {
            n: boundary[n]
            for n in (
                "ecx",
                "edx",
                "ebx",
                "esi",
                "edi",
                "ss",
                "cs",
                "ds",
                "es",
                "fs",
                "gs",
            )
        }
        # Incoming words are specified caller inputs, not read-back oracle inputs.
        values.update(
            frame_minus_800=frame - 800,
            frame_minus_720=frame - 720,
            frame_plus_4=frame + 4,
            constant_65537=65537,
            pushed_flags_image=spec["eflags"],
            saved_ebp=0x456789AB,
            return_word=0x30303030,
            incoming_word_12=0x12345678,
            incoming_word_16=0x90ABCDEF,
        )
        expected = stores.overlay_spec(before, frame - caller.STACK, values)
        events = []
        # Independent overlay fixes widths, order, values; exact grammar fixes sites.
        for event, (offset, width, source) in zip(
            self.grammar["stores"], stores.FIELDS
        ):
            events.append(
                (
                    int(event["instruction"]["rva"], 16),
                    "write",
                    offset,
                    width,
                    values[source] & ((1 << (8 * width)) - 1),
                )
            )
        for event in self.grammar["reads"]:
            events.append(
                (
                    int(event["instruction"]["rva"], 16),
                    "read",
                    event["offset"],
                    event["width"],
                    values[event["source"]],
                )
            )
        events.sort(key=lambda e: (e[0], e[1] == "write"))
        observed, trace, failures = [], [], []
        current = None

        def fail(message: str) -> None:
            failures.append(message)
            uc.emu_stop()

        def instruction(_uc: Any, address: int, size: int, _data: Any) -> None:
            nonlocal current
            current = address - BASE
            if current not in self.rows or not JOIN <= current < STOP:
                fail("instruction escaped store slice")
                return
            trace.append(current)

        def memory(
            _uc: Any, access: int, address: int, size: int, value: int, _data: Any
        ) -> None:
            mode = "write" if access == u.UC_MEM_WRITE else "read"
            if mode == "read":
                value = int.from_bytes(uc.mem_read(address, size), "little")
            actual = (
                current,
                mode,
                address - frame,
                size,
                value & ((1 << (8 * size)) - 1),
            )
            if len(observed) >= len(events) or actual != events[len(observed)]:
                fail("store memory event differs")
                return
            observed.append(actual)

        ih = uc.hook_add(u.UC_HOOK_CODE, instruction)
        mh = uc.hook_add(u.UC_HOOK_MEM_READ | u.UC_HOOK_MEM_WRITE, memory)
        uc.emu_start(BASE + JOIN, BASE + STOP, timeout=5000000, count=1000)
        uc.hook_del(ih)
        uc.hook_del(mh)
        _require(not failures, failures[0] if failures else "slice replay failed")
        _require(
            uc.reg_read(x.UC_X86_REG_EIP) == BASE + STOP and observed == events,
            "exclusive import boundary differs",
        )
        _require(
            trace == [p for p in sorted(self.rows) if JOIN <= p < STOP],
            "store trace differs",
        )
        _require(
            bytes(uc.mem_read(caller.STACK, caller.STACK_SIZE)) == expected,
            "composed whole-stack oracle differs",
        )
        _require(
            all(
                uc.reg_read(r) == (0x30303030 if n == "eax" else boundary[n])
                for n, r in ids.items()
            ),
            "store final register differs",
        )
        return {
            "boundary_values": spec,
            "last_volatile_writers": self.writers,
            "store_trace_rvas": [f"0x{p:08x}" for p in trace],
            "memory_events_sha256": _canonical_sha256([list(e) for e in events]),
            "stack_sha256": hashlib.sha256(expected).hexdigest(),
        }


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    decoded = {
        e: _decode_body(data, image, sources["program_facts"], e)
        for e in (PARENT, caller.FILL, caller.SMALL)
    }
    for e, body in (
        (PARENT, sources["pair"]["bodies"][0]),
        (caller.SMALL, sources["leaves"]["bodies"][0]),
        (caller.FILL, sources["leaves"]["bodies"][1]),
    ):
        _require(
            [_point(r) for r in decoded[e]] == body["points"],
            "source instruction witnesses differ",
        )
    prefix = [r for r in decoded[PARENT] if r.address - BASE < STOP]
    early = [r for r in prefix if r.address - BASE < JOIN]
    late = [r for r in prefix if r.address - BASE >= JOIN]
    _require(
        caller._setup(early, sources) == sources["caller"]["setup"],
        "caller setup differs",
    )
    grammar = stores._grammar(late)
    _require(grammar == sources["stores"]["grammar"], "store grammar differs")
    rows = {
        r.address - BASE: r
        for e in decoded
        for r in (prefix if e == PARENT else decoded[e])
    }
    code = {
        e: b"".join(bytes(r.bytes) for r in (prefix if e == PARENT else decoded[e]))
        for e in decoded
    }
    results, boundaries, visited = hashlib.sha256(), [], set()
    fills = optional = 0
    for vector in cases():
        continuation = _Continuation(rows, grammar, vector)
        result = caller._execute(code, set(rows), vector, _extension=continuation)
        extension = result["extension"]
        boundaries.append(
            {
                "vector": list(vector),
                "values": extension["boundary_values"],
                "last_writers": extension["last_volatile_writers"],
            }
        )
        results.update(_canonical_bytes(result))
        visited.update(result["visited_rvas"])
        visited.update(extension["store_trace_rvas"])
        fills += len(result["fill_observations"])
        optional += result["small_write_count"]
    negative_vector = cases()[0]
    try:
        caller._execute(
            code,
            set(rows),
            negative_vector,
            _extension=_Continuation(rows, grammar, negative_vector, True),
        )
    except HandoffError as exc:
        _require(
            str(exc) == "handoff register differs",
            "handoff control failed unexpectedly",
        )
    else:
        raise HandoffError("handoff control did not reject")
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed during replay",
    )
    _require(
        {f"0x{r.address-BASE:08x}" for r in prefix} <= visited,
        "prefix node coverage differs",
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "prefix": {
            "entry_rva": f"0x{PARENT:08x}",
            "join_rva": f"0x{JOIN:08x}",
            "exclusive_stop_rva": f"0x{STOP:08x}",
            "size": STOP - PARENT,
            "sha256": hashlib.sha256(code[PARENT]).hexdigest(),
            "points": [_point(r) for r in prefix],
            "unexecuted_stop_instruction": sources["stores"]["slice"][
                "unexecuted_stop_instruction"
            ],
        },
        "matrix": MATRIX,
        "vector_sha256": _canonical_sha256([list(v) for v in cases()]),
        "results_sha256": results.hexdigest(),
        "boundary_observations": boundaries,
        "summary": {
            "prefix_cases": len(cases()),
            "fill_observations": fills,
            "optional_helper_executions": optional,
            "prefix_nodes": len(prefix),
            "all_visited_nodes": len(visited),
            "store_instructions_per_case": len(late),
            "store_write_events_per_case": 23,
            "store_read_events_per_case": 6,
            "negative_controls": 1,
        },
        "visited_rvas": sorted(visited),
        "boundary_provenance": {
            "ecx": "Second fill uses REP consumes count to zero; scalar decrements to zero; SIMD leaves (28 + frame_alignment) modulo 32",
            "edx": "Second fill copies the preserved entry EDI value 0x3456789a",
            "eflags": "Status bits from final ADD of 24 to ESP; independently computed 32-bit arithmetic and low-byte parity",
            "eax": "Caller LEA restores frame minus 800 before the join; slice overwrites it with incoming frame-plus-four word",
            "writers": "Last dynamically executed declared architectural writers, including equal-value writes",
        },
        "emulator": dict(sources["caller"]["emulator"])
        | {
            "store_segment_instruction_limit": 1000,
            "store_segment_timeout_microseconds": 5000000,
        },
        "negative_control": {
            "vector": list(negative_vector),
            "mutation": "xor_boundary_ecx_with_one",
            "expected_rejection": "handoff register differs",
        },
        "scope": {
            "evidence_class": "finite_same_instance_exact_prefix_composition",
            "execution": "Same Unicorn instance and unchanged architectural state across two emu_start calls; prefix checks and hook replacement at join; no positive-case register or memory reseeding",
            "checks": [
                "Original complete caller and fill stack, write-region, read-region and global-page guards before join",
                "Independent volatile boundary arithmetic before accepting store inputs",
                "Independent whole-stack overlay and ordered store read and write events with instruction sites widths and values",
                "Preserved boundary registers flags and selectors; stop before import instruction",
            ],
            "not_claimed": [
                "Whole-function return, import execution, reporting behavior or context or record ABI identity",
                "All inputs, flags or segment selectors; real game or hardware execution",
                "Faults, concurrency, timing, ownership or accounting promotion",
            ],
            "source_validation": "Canonical-pinned receipts and redecoded exact PE body witnesses; prior full receipt matrices are not rerun",
        },
    }
    _assert_publication_safe(result)
    return result


def validate_structure(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256,
            "sealed handoff receipt differs",
        )
        _require(
            evidence["source_receipts"] == ids
            and evidence["matrix"] == MATRIX
            and evidence["vector_sha256"]
            == _canonical_sha256([list(v) for v in cases()]),
            "source or matrix differs",
        )
        expected = [
            {
                "vector": list(v),
                "values": boundary_spec(caller.STACK + 0x2000 + v[0], v[1], v[2]),
                "last_writers": boundary_writers(v[1], v[2]),
            }
            for v in cases()
        ]
        _require(
            evidence["boundary_observations"] == expected,
            "boundary specification differs",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_handoff(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_handoff(
    executable: Path, evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        validate_structure(evidence, sources)
        result = build_handoff(executable, sources)
        _require(
            _canonical_bytes(evidence) == _canonical_bytes(result),
            "exact replay differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(result["summary"]),
        }

    return _normalize(run)


def encode_handoff(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
