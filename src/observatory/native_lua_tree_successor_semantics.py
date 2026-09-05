"""Exact call-free tree successor with a finite structural tree domain."""

from __future__ import annotations
import hashlib, json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import capstone.x86_const as x86
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
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
ANALYSIS_KIND = "pe_native_lua_tree_successor_semantics"
SEALED_SHA256 = "4d03a8bfc8ef34f5c700e7d5aa8a8a1a81967978a80d284b9342201c961ba7fd"
START, END = 0x6DF30, 0x6DF7F
SOURCE_PINS = {
    "chain": (
        "pe_native_lua_class_return_helper_chain",
        "33ad87a98131700dce12bd34a7febea3159b6f461710f0b8296d95ded1b37095",
    ),
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
}


def R(s):
    return ("reg", s)


def I(v):
    return ("imm", v)


def M(r, d=0, w=4):
    return ("mem", r, d, w)


OPS = {
    0x6DF30: ("mov", R("edx"), R("ecx")),
    0x6DF32: ("mov", R("eax"), M("edx")),
    0x6DF34: ("cmp", M("eax", 13, 1), I(0)),
    0x6DF38: ("jne", I(BASE + 0x6DF7C)),
    0x6DF3A: ("mov", R("ecx"), M("eax", 8)),
    0x6DF3D: ("cmp", M("ecx", 13, 1), I(0)),
    0x6DF41: ("jne", I(BASE + 0x6DF5F)),
    0x6DF43: ("mov", R("eax"), M("ecx")),
    0x6DF45: ("cmp", M("eax", 13, 1), I(0)),
    0x6DF49: ("jne", I(BASE + 0x6DF5A)),
    0x6DF4B: ("nop",),
    0x6DF50: ("mov", R("ecx"), R("eax")),
    0x6DF52: ("mov", R("eax"), M("ecx")),
    0x6DF54: ("cmp", M("eax", 13, 1), I(0)),
    0x6DF58: ("je", I(BASE + 0x6DF50)),
    0x6DF5A: ("mov", M("edx"), R("ecx")),
    0x6DF5C: ("mov", R("eax"), R("edx")),
    0x6DF5E: ("ret",),
    0x6DF5F: ("mov", R("eax"), M("eax", 4)),
    0x6DF62: ("cmp", M("eax", 13, 1), I(0)),
    0x6DF66: ("jne", I(BASE + 0x6DF7A)),
    0x6DF68: ("mov", R("ecx"), M("edx")),
    0x6DF6A: ("cmp", R("ecx"), M("eax", 8)),
    0x6DF6D: ("jne", I(BASE + 0x6DF7A)),
    0x6DF6F: ("mov", M("edx"), R("eax")),
    0x6DF71: ("mov", R("eax"), M("eax", 4)),
    0x6DF74: ("cmp", M("eax", 13, 1), I(0)),
    0x6DF78: ("je", I(BASE + 0x6DF68)),
    0x6DF7A: ("mov", M("edx"), R("eax")),
    0x6DF7C: ("mov", R("eax"), R("edx")),
    0x6DF7E: ("ret",),
}
ORDER = list(OPS)
SIZES = {
    p: (ORDER[i + 1] if i + 1 < len(ORDER) else END) - p for i, p in enumerate(ORDER)
}
SHAPES = ["balanced", "left_chain", "right_chain", "single", "empty"]


class SuccessorError(RuntimeError):
    pass


def _require(ok, msg):
    if not ok:
        raise SuccessorError(msg)


def _normalize(fn):
    try:
        return fn()
    except SuccessorError:
        raise
    except Exception as exc:
        raise SuccessorError(str(exc)) from exc


def _tree(nodes, start):
    _require(
        isinstance(nodes, Mapping) and 1 <= len(nodes) <= 128, "invalid finite node map"
    )
    _require(type(start) is int and start in nodes, "invalid starting node")
    for a, n in nodes.items():
        _require(
            type(a) is int
            and 0 <= a <= 0xFFFFFFF2
            and isinstance(n, Mapping)
            and set(n) == {"left", "parent", "right", "sentinel"},
            "invalid node record",
        )
        _require(
            all(
                type(n[k]) is int and n[k] in nodes for k in ("left", "parent", "right")
            )
            and type(n["sentinel"]) is int
            and 0 <= n["sentinel"] <= 255,
            "invalid links or sentinel byte",
        )
    addresses = sorted(nodes)
    _require(
        all(a + 14 <= b for a, b in zip(addresses, addresses[1:])),
        "node records overlap",
    )
    sentinels = [a for a, n in nodes.items() if n["sentinel"]]
    _require(len(sentinels) == 1, "exactly one sentinel required")
    nil = sentinels[0]
    normal = set(nodes) - {nil}
    roots = [a for a in normal if nodes[a]["parent"] == nil]
    _require(len(roots) == int(bool(normal)), "invalid root partition")
    for a in normal:
        n = nodes[a]
        _require(n["left"] == nil or n["left"] != n["right"], "duplicate child link")
        for child in (n["left"], n["right"]):
            _require(
                child == nil or nodes[child]["parent"] == a, "child parent mismatch"
            )
        p = n["parent"]
        _require(
            p == nil or (nodes[p]["left"] == a) != (nodes[p]["right"] == a),
            "parent child mismatch",
        )
        seen = set()
        cur = a
        while cur != nil:
            _require(cur not in seen, "cyclic parent chain")
            seen.add(cur)
            cur = nodes[cur]["parent"]
    inorder = []
    visited = set()

    def visit(a):
        if a == nil:
            return
        _require(a not in visited, "cyclic or shared child topology")
        visited.add(a)
        visit(nodes[a]["left"])
        inorder.append(a)
        visit(nodes[a]["right"])

    if roots:
        visit(roots[0])
    _require(visited == normal, "disconnected topology")
    return nil, inorder


def successor_spec(
    nodes: Mapping[int, Mapping[str, int]], start: int
) -> dict[str, Any]:
    nil, order = _tree(nodes, start)
    successor = (
        nil
        if start == nil or order.index(start) == len(order) - 1
        else order[order.index(start) + 1]
    )
    writes = []
    if start == nil:
        path = "sentinel_unchanged"
    elif nodes[start]["right"] != nil:
        path = "right_subtree"
        writes = [successor]
    else:
        path = "parent_climb"
        cur = start
        p = nodes[cur]["parent"]
        while p != nil and nodes[p]["right"] == cur:
            writes.append(p)
            cur = p
            p = nodes[p]["parent"]
        writes.append(p)
    _require(
        not writes or writes[-1] == successor,
        "independent inorder and climb relation differ",
    )
    return {
        "successor": successor,
        "path": path,
        "slot_write_nodes": writes,
        "eax_source": "entry_slot_pointer",
        "edx_source": "entry_slot_pointer",
        "native_esp_delta": 4,
        "preserved_registers": ["ebx", "esi", "edi", "ebp"],
    }


def tree_fixture(shape: str, sentinel_byte: int = 1) -> dict[int, dict[str, int]]:
    _require(
        type(shape) is str
        and shape in SHAPES
        and type(sentinel_byte) is int
        and 1 <= sentinel_byte <= 255,
        "invalid tree fixture",
    )
    nil = 0x10000000
    layouts = {
        "balanced": {
            4: (2, 6),
            2: (1, 3),
            6: (5, 7),
            1: (0, 0),
            3: (0, 0),
            5: (0, 0),
            7: (0, 0),
        },
        "left_chain": {4: (3, 0), 3: (2, 0), 2: (1, 0), 1: (0, 0)},
        "right_chain": {1: (0, 2), 2: (0, 3), 3: (0, 4), 4: (0, 0)},
        "single": {1: (0, 0)},
        "empty": {},
    }
    layout = layouts[shape]
    addr = lambda k: nil + 64 * k
    nodes = {nil: {"left": nil, "parent": nil, "right": nil, "sentinel": sentinel_byte}}
    for k, (l, r) in layout.items():
        nodes[addr(k)] = {
            "left": addr(l),
            "right": addr(r),
            "parent": nil,
            "sentinel": 0,
        }
    for k, (l, r) in layout.items():
        for child in (l, r):
            if child:
                nodes[addr(child)]["parent"] = addr(k)
    return nodes


def model_case(
    shape: str,
    start: int,
    alignment: int,
    sentinel_byte: int = 1,
    actions: Mapping[int, tuple] | None = None,
) -> dict[str, Any]:
    _require(type(alignment) is int and 0 <= alignment < 16, "invalid stack alignment")
    nodes = tree_fixture(shape, sentinel_byte)
    expected = successor_spec(nodes, start)
    actions = OPS if actions is None else actions
    _require(
        isinstance(actions, Mapping) and set(actions) == set(OPS),
        "operation site set differs",
    )
    slot = 0x03001000
    entry = 0x02002000 + alignment
    regs = {
        "eax": 0x11223344,
        "ecx": slot,
        "edx": 0x12345678,
        "ebx": 0x22334455,
        "esi": 0x33445566,
        "edi": 0x44556677,
        "ebp": 0x55667788,
        "esp": entry,
    }
    initial = dict(regs)
    memory = {}

    def raw(a, v, w):
        for i, b in enumerate(v.to_bytes(w, "little")):
            memory[a + i] = b

    for a, n in nodes.items():
        for k, d in (("left", 0), ("parent", 4), ("right", 8)):
            raw(a + d, n[k], 4)
        raw(a + 12, 0, 1)
        raw(a + 13, n["sentinel"], 1)
    raw(slot, start, 4)
    raw(entry, 0x30303030, 4)
    original = dict(memory)
    events = []
    trace = []
    pc = START
    zf = None

    def read(arg):
        if arg[0] == "reg":
            return regs[arg[1]]
        if arg[0] == "imm":
            return arg[1]
        _, r, d, w = arg
        a = regs[r] + d
        _require(all(a + i in memory for i in range(w)), "unmapped read")
        value = int.from_bytes(bytes(memory[a + i] for i in range(w)), "little")
        events.append(
            {
                "site_rva": f"0x{pc:08x}",
                "access": "read",
                "address": a,
                "width": w,
                "value": value,
            }
        )
        return value

    def write(arg, value):
        if arg[0] == "reg":
            regs[arg[1]] = value
        else:
            _, r, d, w = arg
            a = regs[r] + d
            _require(a == slot and w == 4, "write escaped iterator slot")
            raw(a, value, w)
            events.append(
                {
                    "site_rva": f"0x{pc:08x}",
                    "access": "write",
                    "address": a,
                    "width": w,
                    "value": value,
                }
            )

    for _ in range(16 * len(nodes) + 40):
        _require(pc in actions, "model escaped helper")
        trace.append(pc)
        op, *args = actions[pc]
        nxt = pc + SIZES[pc]
        if op == "mov":
            write(args[0], read(args[1]))
        elif op == "cmp":
            zf = read(args[0]) == read(args[1])
        elif op in ("je", "jne"):
            _require(type(zf) is bool, "undefined branch predicate")
            if zf == (op == "je"):
                nxt = read(args[0]) - BASE
        elif op == "nop":
            pass
        elif op == "ret":
            target = read(M("esp"))
            regs["esp"] += 4
            break
        else:
            raise SuccessorError("unsupported operation")
        pc = nxt
    else:
        raise SuccessorError("bounded helper failed to return")
    writes = [e["value"] for e in events if e["access"] == "write"]
    _require(
        writes == expected["slot_write_nodes"], "ordered slot write relation differs"
    )
    _require(
        int.from_bytes(bytes(memory[slot + i] for i in range(4)), "little")
        == expected["successor"],
        "independent inorder successor differs",
    )
    _require(
        regs["eax"] == slot
        and regs["edx"] == slot
        and regs["esp"] == entry + 4
        and target == 0x30303030,
        "return relation differs",
    )
    _require(
        all(regs[r] == initial[r] for r in expected["preserved_registers"]),
        "nonvolatile register changed",
    )
    _require(
        all(memory[a] == v for a, v in original.items() if not slot <= a < slot + 4),
        "memory escaped slot",
    )
    return {
        "input": {
            "shape": shape,
            "start": start,
            "alignment": alignment,
            "sentinel_byte": sentinel_byte,
        },
        "outcome": expected,
        "trace_rvas": [f"0x{r:08x}" for r in trace],
        "events": events,
    }


def _preflight(sources):
    _require(
        isinstance(sources, Mapping) and set(sources) == set(SOURCE_PINS),
        "source partition differs",
    )
    return {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }


def _grammar(rows):
    _require([r.address - BASE for r in rows] == ORDER, "exact body points differ")
    for r in rows:
        pc = r.address - BASE
        if pc == 0x6DF4B:
            a = r.operands[0]
            _require(
                r.mnemonic == "nop"
                and len(r.operands) == 1
                and a.type == x86.X86_OP_MEM
                and a.size == 4
                and r.reg_name(a.mem.base) == "eax"
                and r.reg_name(a.mem.index) == "eax"
                and a.mem.scale == 1
                and a.mem.disp == 0,
                "NOP shape differs",
            )
            continue
        args = []
        for a in r.operands:
            if a.type == x86.X86_OP_REG:
                args.append(R(r.reg_name(a.reg)))
            elif a.type == x86.X86_OP_IMM:
                args.append(I(a.imm))
            elif a.type == x86.X86_OP_MEM:
                _require(
                    not a.mem.index and not a.mem.segment, "unexpected memory mode"
                )
                args.append(M(r.reg_name(a.mem.base), a.mem.disp, a.size))
            else:
                raise SuccessorError("unexpected operand")
        widths = [a.size for a in r.operands]
        _require(
            (r.mnemonic, *args) == OPS[pc]
            and r.size == SIZES[pc]
            and widths
            == (
                [1, 1]
                if OPS[pc][0] == "cmp" and OPS[pc][1][0] == "mem"
                else [4] * len(args)
            ),
            "exact instruction differs",
        )


def _build_unsealed(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    rows = _decode_body(data, image, sources["program_facts"], START)
    _grammar(rows)
    edges = [
        e
        for e in sources["chain"]["native_edges"]
        if e["target_entry_rva"] == f"0x{START:08x}"
    ]
    _require(len(edges) == 1, "chain iterator edge differs")
    edge = edges[0]
    bodyhash = hashlib.sha256(b"".join(bytes(r.bytes) for r in rows)).hexdigest()
    _require(
        bodyhash == edge["target_body_sha256"]
        and sum(r.size for r in rows) == edge["target_body_size"] == 79,
        "chain target body differs",
    )
    owner = _decode_body(data, image, sources["program_facts"], 0x2EB140)
    site = next(r for r in owner if r.address - BASE == 0x2EB1AB)
    _require(
        _point(site) == edge["instruction"]
        and site.id == x86.X86_INS_CALL
        and site.operands[0].imm == BASE + START,
        "incoming edge differs",
    )
    cases = [
        model_case(shape, start, a, s)
        for shape in SHAPES
        for start in sorted(tree_fixture(shape))
        for a in range(16)
        for s in (1, 255)
    ]
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(union == [_point(r)["rva"] for r in rows], "model body union differs")
    controls = []
    bad = tree_fixture("single")
    a = 0x10000040
    bad[a]["parent"] = a
    bad[a]["right"] = a
    try:
        successor_spec(bad, a)
    except SuccessorError:
        controls.append(
            {"name": "cyclic_topology", "kind": "domain_rejection", "rejected": True}
        )
    else:
        raise SuccessorError("cycle accepted")
    altered = dict(OPS)
    altered[0x6DF6F] = ("mov", M("edx"), R("edx"))
    try:
        model_case("right_chain", 0x10000100, 0, 1, altered)
    except SuccessorError:
        controls.append(
            {
                "name": "wrong_intermediate_slot_write",
                "kind": "semantic_mutation",
                "rejected": True,
            }
        )
    else:
        raise SuccessorError("semantic mutation accepted")
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "body": {
            "entry_rva": f"0x{START:08x}",
            "exclusive_end_rva": f"0x{END:08x}",
            "bytes": 79,
            "nodes": 31,
            "sha256": bodyhash,
            "points": [_point(r) for r in rows],
        },
        "incoming_edge": edge,
        "domain": {
            "maximum_nodes": 128,
            "sentinel_flag_offset": 13,
            "link_offsets": {"left": 0, "parent": 4, "right": 8},
            "node_bytes_read_domain": 14,
            "requirements": [
                "One nonzero-byte sentinel and normal nodes with zero sentinel byte",
                "Mapped disjoint node records with consistent parent and child links, one root and finite acyclic topology",
                "Iterator slot and native return word are disjoint from nodes and from each other",
                "Static tree links remain unchanged during this call-free helper",
            ],
        },
        "matrix": {
            "shapes": SHAPES,
            "starts": "Every fixture node including sentinel",
            "frame_alignments": list(range(16)),
            "sentinel_bytes": [1, 255],
        },
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
        },
        "summary": {
            "cases": len(cases),
            "static_bytes": 79,
            "static_nodes": 31,
            "modeled_nodes": len(union),
            "actual_native_executions": 0,
            "calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "exact_integer_graph_model_with_independent_inorder_successor_oracle",
            "normal_relation": "Slot becomes inorder successor or sentinel, with exact intermediate ancestor writes; sentinel entry leaves slot unchanged; EAX and EDX return the slot pointer and ESP advances four",
            "event_policy": "Explicit data operands and RET stack read are recorded; the multibyte NOP makes no data-memory access",
            "not_claimed": [
                "Tree ordering by keys, balancing, container identity or generic validity of arbitrary native pointers",
                "Behavior or termination on cyclic, malformed, aliased or concurrently mutated links",
                "Hardware execution, native fault behavior, caller tree insertion semantics or full owner recreation",
                "Lua or game execution and atlas accounting promotion",
            ],
        },
    }
    _require(
        hashlib.sha256(executable.read_bytes()).hexdigest() == digest,
        "executable changed during build",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run():
        _validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256
            and evidence["source_receipts"] == ids,
            "sealed successor receipt differs",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_semantics(executable: Path, sources: Mapping[str, Any]) -> dict[str, Any]:
    def run():
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_semantics(
    executable: Path, evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run():
        validate_structure(evidence, sources)
        actual = build_semantics(executable, sources)
        _require(
            _canonical_bytes(actual) == _canonical_bytes(evidence),
            "exact successor receipt differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(actual["summary"]),
        }

    return _normalize(run)


def encode_semantics(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
