"""Static interval arithmetic and finite exact-prefix caller/fill composition."""

from __future__ import annotations
import hashlib
import json
import struct
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import capstone.x86_const as x86
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    UNICORN_VERSION,
    UNICORN_CORE_VERSION,
    CPU_MODEL,
    GLOBAL_REP,
    GLOBAL_SIMD,
    _runtime,
    fill_spec,
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
ANALYSIS_KIND = "pe_native_assertion_helper_caller_fill"
SEALED_SHA256 = "b89d1873e56c4afb27c96229c05a1a0516732a5bdc3d2151173baeb5d4a5b653"
PARENT, STOP, FILL, SMALL = 0x379D28, 0x379D79, 0x370960, 0x3586B6
COOKIE, CLEAR = BASE + 0x493F28, BASE + 0x4B6E58
STACK, STACK_SIZE = 0x2000000, 0x4000
SOURCE_PINS = {
    "pair": (
        "pe_native_assertion_helper_descendant_pair",
        "47421700f38e3dbf3f5283bf89d3beb5d6421d32eaf05938ad58989908f93d0b",
    ),
    "leaves": (
        "pe_native_assertion_helper_leaf_callees",
        "1ef7c1874b83e871f3afa9d482c2c6f01cd541c50f81b342605d80946a93f3c2",
    ),
    "conformance": (
        "pe_native_assertion_helper_fill_conformance",
        "6f4bba8750713184f5de2bf119b36605078e4386e05712a2f686b6e744801246",
    ),
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
}
MATRIX = {
    "frame_alignments": list(range(16)),
    "dispatch_words": [[0, 0], [0, 2], [2, 0], [2, 2]],
    "selectors": [0, 0xFFFFFFFF],
    "cookies": [0, 0x6B8B4567],
}


class CallerError(RuntimeError):
    """An exact setup, isolated replay, or sealed receipt check differs."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise CallerError(message)


def _normalize(fn: Any) -> Any:
    try:
        return fn()
    except CallerError:
        raise
    except Exception as exc:
        raise CallerError(str(exc)) from exc


def frame_layout() -> dict[str, Any]:
    regions = [
        {
            "call_rva": "0x00379d58",
            "start": -800,
            "end": -720,
            "length": 80,
            "callee_sp": -828,
            "return_rva": "0x00379d5d",
        },
        {
            "call_rva": "0x00379d6b",
            "start": -720,
            "end": -4,
            "length": 716,
            "callee_sp": -840,
            "return_rva": "0x00379d70",
        },
    ]
    _require(
        all(r["end"] - r["start"] == r["length"] for r in regions),
        "region length differs",
    )
    _require(
        -808 <= regions[0]["start"]
        and regions[0]["end"] == regions[1]["start"]
        and regions[1]["end"] == -4,
        "interval partition differs",
    )
    return {
        "coordinate": "offset from established EBP, equal to caller entry ESP minus four",
        "allocation": [-808, 0],
        "regions": regions,
        "zero_union": [-800, -4],
        "zero_bytes": 796,
        "untouched_locals": [-808, -800],
        "protected_cookie": [-4, 0],
        "saved_edi": [-812, -808],
        "saved_ebp": [0, 4],
        "lowest_outgoing_stack_offset": -840,
        "cleanup_bytes": 24,
        "stop_sp_offset": -812,
        "stop_eax_offset": -800,
        "alignment_shared_with_ebp": True,
    }


def cases() -> list[tuple[int, int, int, int, int]]:
    return [
        (a, r, s, v, c)
        for a in MATRIX["frame_alignments"]
        for r, s in MATRIX["dispatch_words"]
        for v in MATRIX["selectors"]
        for c in MATRIX["cookies"]
    ]


def _preflight(sources: Mapping[str, Any]) -> dict[str, Any]:
    _validate_json_tree(sources, "sources")
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    ids = {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }
    identity = sources["program_facts"]["identity"]
    _require(identity["executable_sha256"] == EXE_SHA256, "build differs")
    _require(
        all(
            _canonical_bytes(sources[k]["build_identity"]) == _canonical_bytes(identity)
            for k in ("pair", "leaves", "conformance")
        ),
        "source build differs",
    )
    return ids


def _setup(rows: list[Any], sources: Mapping[str, Any]) -> dict[str, Any]:
    by = {r.address - BASE: r for r in rows}

    def reg(o: Any, name: int) -> bool:
        return o.type == x86.X86_OP_REG and o.reg == name

    def immediate(site: int, opcode: int, value: int) -> None:
        r = by[site]
        _require(
            r.id == opcode
            and r.operands[-1].type == x86.X86_OP_IMM
            and r.operands[-1].imm == value,
            "setup immediate differs",
        )

    _require(
        by[0x379D2A].id == x86.X86_INS_PUSH
        and reg(by[0x379D2A].operands[0], x86.X86_REG_EBP),
        "frame save differs",
    )
    r = by[0x379D2B]
    _require(
        r.id == x86.X86_INS_MOV
        and reg(r.operands[0], x86.X86_REG_EBP)
        and reg(r.operands[1], x86.X86_REG_ESP),
        "frame establishment differs",
    )
    immediate(0x379D2D, x86.X86_INS_SUB, 808)
    _require(
        reg(by[0x379D2D].operands[0], x86.X86_REG_ESP), "allocation register differs"
    )
    immediate(0x379D76, x86.X86_INS_ADD, 24)
    _require(reg(by[0x379D76].operands[0], x86.X86_REG_ESP), "cleanup register differs")
    for push, lea, zero, arg, call, offset, length in [
        (0x379D4D, 0x379D4F, 0x379D55, 0x379D57, 0x379D58, -800, 80),
        (0x379D5D, 0x379D62, 0x379D68, 0x379D6A, 0x379D6B, -720, 716),
    ]:
        immediate(push, x86.X86_INS_PUSH, length)
        immediate(zero, x86.X86_INS_PUSH, 0)
        immediate(call, x86.X86_INS_CALL, BASE + FILL)
        r = by[lea]
        o = r.operands[1]
        _require(
            r.id == x86.X86_INS_LEA
            and reg(r.operands[0], x86.X86_REG_EAX)
            and o.type == x86.X86_OP_MEM
            and o.mem.base == x86.X86_REG_EBP
            and o.mem.index == o.mem.segment == 0
            and o.mem.disp == offset,
            "destination expression differs",
        )
        _require(
            by[arg].id == x86.X86_INS_PUSH
            and reg(by[arg].operands[0], x86.X86_REG_EAX),
            "argument register differs",
        )
    parent = sources["pair"]["bodies"][0]
    edges = parent["native_controls"]["direct_calls"]
    joins = []
    for index, site in ((1, 0x379D58), (2, 0x379D6B)):
        edge = edges[index]
        _require(
            edge["instruction"] == _point(by[site])
            and edge["target_entry_rva"] == "0x00370960",
            "parent fill edge differs",
        )
        leaf = sources["leaves"]["parent_edges"][index]
        _require(leaf["edge"] == edge, "leaf parent join differs")
        joins.append(
            {
                "pair_path": ["bodies", 0, "native_controls", "direct_calls", index],
                "leaf_path": ["parent_edges", index],
                "edge": edge,
            }
        )
    return {
        "exclusive_stop_rva": f"0x{STOP:08x}",
        "prefix_points": [_point(r) for r in rows],
        "prefix_size": STOP - PARENT,
        "prefix_sha256": hashlib.sha256(
            b"".join(bytes(r.bytes) for r in rows)
        ).hexdigest(),
        "layout": frame_layout(),
        "source_joins": joins,
        "claim": "Selected frame and fill-argument grammar, exact pinned prefix witnesses, and static interval arithmetic; concrete branch, protected-slot and call effects are checked only on the finite emulation matrix.",
    }


def _execute(
    code: Mapping[int, bytes],
    points: set[int],
    vector: tuple[int, int, int, int, int],
    *,
    direction: bool = False,
    _extension: Any = None,
) -> dict[str, Any]:
    # A private additive continuation may inspect executed boundaries and reuse
    # this instance only after every original prefix oracle has passed. Default
    # execution and receipt values remain unchanged.
    u = _runtime()
    from unicorn import x86_const as x

    alignment, rep, simd, selector, cookie = vector
    f = STACK + 0x2000 + alignment
    entry_sp = f + 4
    uc = u.Uc(u.UC_ARCH_X86, u.UC_MODE_32)
    uc.ctl_set_cpu_model(CPU_MODEL)
    _require(uc.ctl_get_cpu_model() == CPU_MODEL, "CPU model differs")
    for entry, payload in code.items():
        address = BASE + entry
        page = address & ~0xFFF
        uc.mem_map(page, 0x1000, u.UC_PROT_ALL)
        uc.mem_write(address, payload)
        uc.mem_protect(page, 0x1000, u.UC_PROT_READ | u.UC_PROT_EXEC)
    uc.mem_map(STACK, STACK_SIZE, u.UC_PROT_READ | u.UC_PROT_WRITE)
    initial = bytes((i * 37 + 19) & 255 for i in range(STACK_SIZE))
    uc.mem_write(STACK, initial)
    incoming = struct.pack("<IIII", 0x30303030, selector, 0x12345678, 0x90ABCDEF)
    uc.mem_write(entry_sp, incoming)
    expected = bytearray(uc.mem_read(STACK, STACK_SIZE))
    for page in sorted({a & ~0xFFF for a in (COOKIE, CLEAR, GLOBAL_REP, GLOBAL_SIMD)}):
        uc.mem_map(page, 0x1000, u.UC_PROT_READ | u.UC_PROT_WRITE)
        uc.mem_write(page, bytes([0xA7]) * 0x1000)
    for address, value in (
        (COOKIE, cookie),
        (CLEAR, 0xA55AA55A),
        (GLOBAL_REP, rep),
        (GLOBAL_SIMD, simd),
    ):
        uc.mem_write(address, struct.pack("<I", value))
    global_before = {
        page: bytes(uc.mem_read(page, 0x1000))
        for page in sorted({COOKIE & ~0xFFF, CLEAR & ~0xFFF})
    }
    preserved = {
        x.UC_X86_REG_EBX: 0x13579BDF,
        x.UC_X86_REG_ESI: 0x2468ACE0,
        x.UC_X86_REG_EDI: 0x3456789A,
    }
    old_ebp = 0x456789AB
    for r, v in preserved.items():
        uc.reg_write(r, v)
    uc.reg_write(x.UC_X86_REG_EBP, old_ebp)
    uc.reg_write(x.UC_X86_REG_ESP, entry_sp)
    uc.reg_write(x.UC_X86_REG_EAX, 0x56789ABC)
    uc.reg_write(x.UC_X86_REG_ECX, 0x6789ABCD)
    uc.reg_write(x.UC_X86_REG_EDX, 0x789ABCDE)
    uc.reg_write(x.UC_X86_REG_EFLAGS, 2 | (0x400 if direction else 0))
    stores = {
        0x379D2A: (0, old_ebp),
        0x379D3A: (-4, cookie ^ f),
        0x379D41: (-812, preserved[x.UC_X86_REG_EDI]),
        0x379D44: (-816, selector),
        0x379D47: (-820, BASE + 0x379D4C),
        0x379D4D: (-816, 80),
        0x379D55: (-820, 0),
        0x379D57: (-824, f - 800),
        0x379D58: (-828, BASE + 0x379D5D),
        0x379D5D: (-828, 716),
        0x379D68: (-832, 0),
        0x379D6A: (-836, f - 720),
        0x379D6B: (-840, BASE + 0x379D70),
    }
    reads = {
        0x379D33: COOKIE,
        0x379D3D: f + 8,
        0x379D44: f + 8,
        0x379D4C: f - 816,
        SMALL: CLEAR,
        SMALL + 7: f - 820,
    }
    pc = None
    active = None
    outcomes = []
    visited = set()
    parent_writes = Counter()
    small_writes = 0
    failure = []

    def fail(message: str) -> None:
        failure.append(message)
        uc.emu_stop()

    def instruction(_uc: Any, address: int, size: int, _data: Any) -> None:
        nonlocal pc, active
        pc = address - BASE
        if _extension is not None:
            _extension.observe(uc, pc)
        if pc not in points:
            fail("instruction escaped sealed prefix or callees")
            return
        visited.add(pc)
        if pc in (0x379D5D, 0x379D70):
            if active is None:
                fail("missing active fill")
                return
            index = len(outcomes)
            region = frame_layout()["regions"][index]
            if pc != int(region["return_rva"], 16):
                fail("unexpected fill continuation")
                return
            current = bytes(uc.mem_read(STACK, STACK_SIZE))
            if current != fill_spec(
                active["before"], f + region["start"] - STACK, region["length"], 0
            ):
                fail("caller fill specification differs")
                return
            if active["written"] != set(range(region["length"])):
                fail("fill write union differs")
                return
            if (
                uc.reg_read(x.UC_X86_REG_ESP) != active["sp"] + 4
                or uc.reg_read(x.UC_X86_REG_EAX) != f + region["start"]
            ):
                fail("fill return values differ")
                return
            if any(uc.reg_read(r) != v for r, v in active["registers"].items()):
                fail("fill preserved registers differ")
                return
            outcomes.append(
                {
                    "call_rva": region["call_rva"],
                    "normalized_argument_frame": {
                        "return_rva": region["return_rva"],
                        "destination_ebp_offset": region["start"],
                        "fill_value": 0,
                        "length": region["length"],
                    },
                    "entry_sp_offset": region["callee_sp"],
                    "return_sp_offset": region["callee_sp"] + 4,
                    "stack_sha256": hashlib.sha256(current).hexdigest(),
                    "write_union_bytes": len(active["written"]),
                }
            )
            active = None
        if pc == FILL:
            if active is not None or len(outcomes) >= 2:
                fail("unexpected fill entry")
                return
            region = frame_layout()["regions"][len(outcomes)]
            sp = uc.reg_read(x.UC_X86_REG_ESP)
            args = struct.unpack("<IIII", bytes(uc.mem_read(sp, 16)))
            if sp != f + region["callee_sp"] or args != (
                BASE + int(region["return_rva"], 16),
                f + region["start"],
                0,
                region["length"],
            ):
                fail("call argument frame differs")
                return
            active = {
                "sp": sp,
                "region": region,
                "before": bytes(uc.mem_read(STACK, STACK_SIZE)),
                "written": set(),
                "registers": {
                    r: uc.reg_read(r) for r in (*preserved, x.UC_X86_REG_EBP)
                },
            }

    def memory(
        _uc: Any, access: int, address: int, size: int, value: int, _data: Any
    ) -> None:
        nonlocal small_writes
        if access == u.UC_MEM_WRITE:
            if FILL <= pc < FILL + 346:
                if active is None:
                    fail("fill write without frame")
                    return
                r = active["region"]
                start = f + r["start"]
                if not (start <= address and address + size <= start + r["length"]):
                    fail("fill write escaped destination")
                    return
                active["written"].update(range(address - start, address - start + size))
            elif pc == SMALL:
                if (address, size, value & 0xFFFFFFFF) != (CLEAR, 4, 0):
                    fail("small helper write differs")
                    return
                small_writes += 1
            else:
                if pc not in stores:
                    fail("unreviewed caller write")
                    return
                offset, want = stores[pc]
                if (address, size, value & 0xFFFFFFFF) != (f + offset, 4, want):
                    fail("caller stack write differs")
                    return
                parent_writes[pc] += 1
                expected[address - STACK : address - STACK + 4] = struct.pack(
                    "<I", want
                )
        else:
            if FILL <= pc < FILL + 346:
                okay = active is not None and (
                    (active["sp"] <= address and address + size <= active["sp"] + 16)
                    or any(
                        a <= address and address + size <= a + 4
                        for a in (GLOBAL_REP, GLOBAL_SIMD)
                    )
                )
            else:
                okay = pc in reads and address == reads[pc] and size == 4
            if not okay:
                fail("data read escaped declared inputs")

    instruction_hook = uc.hook_add(u.UC_HOOK_CODE, instruction)
    memory_hook = uc.hook_add(u.UC_HOOK_MEM_READ | u.UC_HOOK_MEM_WRITE, memory)
    uc.emu_start(BASE + PARENT, BASE + STOP, timeout=5000000, count=200000)
    _require(not failure, failure[0] if failure else "replay failed")
    _require(
        uc.reg_read(x.UC_X86_REG_EIP) == BASE + STOP
        and active is None
        and len(outcomes) == 2,
        "exclusive stop differs",
    )
    _require(
        uc.reg_read(x.UC_X86_REG_EBP) == f
        and uc.reg_read(x.UC_X86_REG_ESP) == f - 812
        and uc.reg_read(x.UC_X86_REG_EAX) == f - 800,
        "final frame state differs",
    )
    _require(
        all(uc.reg_read(r) == v for r, v in preserved.items()),
        "prefix preserved register differs",
    )
    wanted_sites = set(stores) - (
        {0x379D44, 0x379D47} if selector == 0xFFFFFFFF else set()
    )
    _require(
        parent_writes == Counter({k: 1 for k in wanted_sites}),
        "caller write partition differs",
    )
    _require(
        small_writes == int(selector != 0xFFFFFFFF), "optional helper path differs"
    )
    expected = fill_spec(bytes(expected), f - 800 - STACK, 796, 0)
    actual = bytes(uc.mem_read(STACK, STACK_SIZE))
    _require(actual == expected, "whole-stack oracle differs")
    for page, before in global_before.items():
        want = bytearray(before)
        if page == (CLEAR & ~0xFFF) and selector != 0xFFFFFFFF:
            want[CLEAR - page : CLEAR - page + 4] = bytes(4)
        _require(
            bytes(uc.mem_read(page, 0x1000)) == bytes(want),
            "global page oracle differs",
        )
    extension_result = None
    if _extension is not None:
        _extension.observe(uc, STOP)
        uc.hook_del(instruction_hook)
        uc.hook_del(memory_hook)
        extension_result = _extension.finish(uc, f, actual)
    result = {
        "vector": list(vector),
        "fill_observations": outcomes,
        "visited_rvas": [f"0x{p:08x}" for p in sorted(visited)],
        "parent_write_sites": [f"0x{p:08x}" for p in sorted(parent_writes)],
        "small_write_count": small_writes,
        "stack_sha256": hashlib.sha256(actual).hexdigest(),
    }
    if _extension is not None:
        result["extension"] = extension_result
    return result


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    identities = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    facts = sources["program_facts"]
    rows = {e: _decode_body(data, image, facts, e) for e in (PARENT, FILL, SMALL)}
    for entry, body in (
        (PARENT, sources["pair"]["bodies"][0]),
        (SMALL, sources["leaves"]["bodies"][0]),
        (FILL, sources["leaves"]["bodies"][1]),
    ):
        _require(
            [_point(r) for r in rows[entry]] == body["points"],
            "source instruction witnesses differ",
        )
    prefix = [r for r in rows[PARENT] if r.address - BASE < STOP]
    setup = _setup(prefix, sources)
    code = {
        e: b"".join(bytes(r.bytes) for r in (prefix if e == PARENT else rows[e]))
        for e in rows
    }
    points = {
        r.address - BASE for e in rows for r in (prefix if e == PARENT else rows[e])
    }
    vectors = cases()
    results = hashlib.sha256()
    visited = set()
    counts = Counter()
    for vector in vectors:
        result = _execute(code, points, vector)
        results.update(_canonical_bytes(result))
        visited.update(result["visited_rvas"])
        counts["fill_observations"] += len(result["fill_observations"])
        counts["optional_helper_executions"] += result["small_write_count"]
    try:
        _execute(code, points, (0, 2, 0, 0xFFFFFFFF, 0), direction=True)
    except CallerError as exc:
        _require(
            str(exc) == "fill write escaped destination",
            "direction control failed unexpectedly",
        )
    else:
        raise CallerError("direction control did not reject")
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed during replay",
    )
    _require(
        {f"0x{r.address-BASE:08x}" for r in prefix} <= visited,
        "prefix node coverage incomplete",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(facts["identity"]),
        "source_receipts": identities,
        "setup": setup,
        "emulator": {
            "name": "Unicorn",
            "version": UNICORN_VERSION,
            "native_core_version": list(UNICORN_CORE_VERSION),
            "cpu_model": {"id": CPU_MODEL, "name": "UC_CPU_X86_HASWELL"},
            "bits": 32,
            "flat_segments": True,
            "instruction_limit": 200000,
            "timeout_microseconds": 5000000,
        },
        "matrix": MATRIX,
        "vector_sha256": _canonical_sha256([list(v) for v in vectors]),
        "results_sha256": results.hexdigest(),
        "summary": {
            "prefix_cases": len(vectors),
            "fill_observations": counts["fill_observations"],
            "optional_helper_executions": counts["optional_helper_executions"],
            "prefix_nodes": len(prefix),
            "all_visited_nodes": len(visited),
            "zero_region_bytes": 796,
            "negative_controls": 1,
        },
        "visited_rvas": sorted(visited),
        "checks": [
            "Each exact fill-entry stack frame and return continuation",
            "Each fill's independent full-stack byte oracle, exact permitted write union and preserved registers",
            "Parent writes checked individually against expected frame values; whole-stack final oracle protects locals saved registers cookie and incoming frame",
            "Data reads restricted by executing component; full global-page oracle permits only the optional four-byte zero effect",
            "Exclusive stop before instruction at 0x00379d79, after the shared 24-byte cleanup",
        ],
        "direction_control": {
            "input_df": 1,
            "vector": [0, 2, 0, 0xFFFFFFFF, 0],
            "expected_rejection": "fill write escaped destination",
        },
        "scope": {
            "evidence_class": "static_frame_arithmetic_and_finite_exact_prefix_conformance",
            "positive_df": 0,
            "frame_base": "synthetic mapped nonwrapping stack with all sixteen EBP residues",
            "not_claimed": [
                "All caller inputs or addresses, all selector values, all CPU states or flags",
                "Whole caller return, later pointer stores, context identity or reporting behavior",
                "Real game execution, real hardware, CPU feature availability, faults, concurrency or timing",
                "Global purpose, CRT identity, ownership or accounting promotion",
            ],
            "source_validation": "Canonical source receipts plus exact PE and body instruction witnesses; earlier whole-atlas and 14620-case fill analyses are not rerun.",
        },
    }


def validate_structure(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256,
            "sealed caller receipt differs",
        )
        _require(
            evidence["source_receipts"] == ids
            and evidence["setup"]["layout"] == frame_layout()
            and evidence["matrix"] == MATRIX,
            "source or layout differs",
        )
        _require(
            evidence["vector_sha256"] == _canonical_sha256([list(v) for v in cases()]),
            "vector identity differs",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_caller(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_caller(
    executable: Path, evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        validate_structure(evidence, sources)
        result = build_caller(executable, sources)
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


def encode_caller(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
