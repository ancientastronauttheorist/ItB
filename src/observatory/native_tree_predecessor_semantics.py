"""Exact call-free predecessor on finite stable tree topology."""

from __future__ import annotations
import hashlib, json
from pathlib import Path
from collections.abc import Mapping
import capstone.x86_const as x86
from src.observatory import native_lua_tree_successor_semantics as successor
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

ANALYSIS_KIND = "pe_native_tree_predecessor_semantics"
SEALED_SHA256 = "52861d984526abd8a5108075fd25d07bf8043ba61de69aa53139e3c70d97b37f"
START, END = 0x71850, 0x718AE
SOURCE_PINS = {
    "successor_semantics": (successor.ANALYSIS_KIND, successor.SEALED_SHA256),
    "program_facts": successor.SOURCE_PINS["program_facts"],
}


class PredecessorError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise PredecessorError(message)


def _normalize(fn):
    try:
        return fn()
    except PredecessorError:
        raise
    except Exception as exc:
        raise PredecessorError(str(exc)) from exc


OPS = {
    464976: ("mov", ("reg", "edx"), ("reg", "ecx")),
    464978: ("mov", ("reg", "eax"), ("mem", "edx", 0, 4)),
    464980: ("cmp", ("mem", "eax", 13, 1), ("imm", 0)),
    464984: ("je", ("imm", 4659298)),
    464986: ("mov", ("reg", "eax"), ("mem", "eax", 8, 4)),
    464989: ("mov", ("mem", "edx", 0, 4), ("reg", "eax")),
    464991: ("mov", ("reg", "eax"), ("reg", "edx")),
    464993: ("ret",),
    464994: ("mov", ("reg", "ecx"), ("mem", "eax", 0, 4)),
    464996: ("cmp", ("mem", "ecx", 13, 1), ("imm", 0)),
    465000: ("jne", ("imm", 4659331)),
    465002: ("mov", ("reg", "eax"), ("mem", "ecx", 8, 4)),
    465005: ("cmp", ("mem", "eax", 13, 1), ("imm", 0)),
    465009: ("jne", ("imm", 4659369)),
    465011: ("mov", ("reg", "ecx"), ("reg", "eax")),
    465013: ("mov", ("reg", "eax"), ("mem", "ecx", 8, 4)),
    465016: ("cmp", ("mem", "eax", 13, 1), ("imm", 0)),
    465020: ("je", ("imm", 4659315)),
    465022: ("mov", ("mem", "edx", 0, 4), ("reg", "ecx")),
    465024: ("mov", ("reg", "eax"), ("reg", "edx")),
    465026: ("ret",),
    465027: ("mov", ("reg", "ecx"), ("mem", "eax", 4, 4)),
    465030: ("cmp", ("mem", "ecx", 13, 1), ("imm", 0)),
    465034: ("jne", ("imm", 4659361)),
    465036: ("nop",),
    465040: ("mov", ("reg", "eax"), ("mem", "edx", 0, 4)),
    465042: ("cmp", ("reg", "eax"), ("mem", "ecx", 0, 4)),
    465044: ("jne", ("imm", 4659361)),
    465046: ("mov", ("mem", "edx", 0, 4), ("reg", "ecx")),
    465048: ("mov", ("reg", "ecx"), ("mem", "ecx", 4, 4)),
    465051: ("cmp", ("mem", "ecx", 13, 1), ("imm", 0)),
    465055: ("je", ("imm", 4659344)),
    465057: ("mov", ("reg", "eax"), ("mem", "edx", 0, 4)),
    465059: ("cmp", ("mem", "eax", 13, 1), ("imm", 0)),
    465063: ("jne", ("imm", 4659371)),
    465065: ("mov", ("mem", "edx", 0, 4), ("reg", "ecx")),
    465067: ("mov", ("reg", "eax"), ("reg", "edx")),
    465069: ("ret",),
}
SIZES = {
    464976: 2,
    464978: 2,
    464980: 4,
    464984: 2,
    464986: 3,
    464989: 2,
    464991: 2,
    464993: 1,
    464994: 2,
    464996: 4,
    465000: 2,
    465002: 3,
    465005: 4,
    465009: 2,
    465011: 2,
    465013: 3,
    465016: 4,
    465020: 2,
    465022: 2,
    465024: 2,
    465026: 1,
    465027: 3,
    465030: 4,
    465034: 2,
    465036: 4,
    465040: 2,
    465042: 2,
    465044: 2,
    465046: 2,
    465048: 3,
    465051: 4,
    465055: 2,
    465057: 2,
    465059: 4,
    465063: 2,
    465065: 2,
    465067: 2,
    465069: 1,
}
ORDER = list(OPS)


def predecessor_spec(nodes, start):
    nil, order = _normalize(lambda: successor._tree(nodes, start))
    writes = []
    if start == nil:
        result = nodes[nil]["right"]
        writes = [result]
        cursor = None
        flag = nodes[nil]["sentinel"]
        path = "sentinel_right"
    elif nodes[start]["left"] != nil:
        cursor = nodes[start]["left"]
        while nodes[cursor]["right"] != nil:
            cursor = nodes[cursor]["right"]
        result = cursor
        writes = [result]
        flag = nodes[nil]["sentinel"]
        path = "left_subtree"
    else:
        current = start
        cursor = nodes[current]["parent"]
        while cursor != nil and current == nodes[cursor]["left"]:
            current = cursor
            writes.append(current)
            cursor = nodes[cursor]["parent"]
        result = cursor
        writes.append(result)
        flag = 0
        path = "parent_climb"
    canonical = nodes[nil]["right"] == (order[-1] if order else nil)
    inorder_result = (
        (order[-1] if order else nil)
        if start == nil
        else (order[order.index(start) - 1] if order.index(start) > 0 else nil)
    )
    if start != nil or canonical:
        _require(result == inorder_result, "inorder predecessor differs")
    return dict(
        predecessor=result,
        slot_write_nodes=writes,
        ecx_node=cursor,
        final_nil_byte=flag,
        path=path,
        inorder_corollary=start != nil or canonical,
    )


SHAPES = successor.SHAPES + ["zigzag", "deep_left", "deep_right"]


def tree_fixture(shape, sentinel_byte=1, canonical_head=True):
    _require(type(canonical_head) is bool, "invalid head premise")
    if shape in successor.SHAPES:
        nodes = successor.tree_fixture(shape, sentinel_byte)
    else:
        _require(shape in SHAPES, "unknown shape")
        _require(
            type(sentinel_byte) is int and 1 <= sentinel_byte <= 255, "invalid nil byte"
        )
        nil = 0x10000000
        nodes = {nil: dict(left=nil, parent=nil, right=nil, sentinel=sentinel_byte)}
        for k in range(1, 18):
            a = nil + 64 * k
            nodes[a] = dict(left=nil, parent=nil + 64 * (k - 1), right=nil, sentinel=0)
            if k > 1:
                nodes[nil + 64 * (k - 1)][
                    (
                        "left"
                        if shape == "deep_left" or (shape == "zigzag" and k % 2 == 0)
                        else "right"
                    )
                ] = a
    nil, order = successor._tree(nodes, next(iter(nodes)))
    nodes[nil]["right"] = (order[-1] if canonical_head else order[0]) if order else nil
    return nodes


def vectors():
    return [
        dict(
            shape=shape,
            start=start,
            alignment=a,
            sentinel_byte=s,
            canonical_head=h,
            df=df,
        )
        for shape in SHAPES
        for start in sorted(tree_fixture(shape))
        for a in range(16)
        for s in (1, 128, 255)
        for h in (True, False)
        for df in (0, 1)
    ]


def case_fixture(shape, start, alignment=0, sentinel_byte=1, canonical_head=True, df=0):
    _require(
        type(alignment) is int
        and 0 <= alignment < 16
        and type(df) is int
        and df in (0, 1),
        "invalid frame or DF",
    )
    nodes = tree_fixture(shape, sentinel_byte, canonical_head)
    predecessor_spec(nodes, start)
    slot = 0x03001000
    s = 0x02002000 + alignment
    regs = dict(
        eax=0x11223344,
        ecx=slot,
        edx=0x12345678,
        ebx=0x22334455,
        esi=0x33445566,
        edi=0x44556677,
        ebp=0x55667788,
        esp=s,
    )
    memory = {}

    def put(a, v, w):
        for j, b in enumerate(v.to_bytes(w, "little")):
            memory[a + j] = b

    for a, node in nodes.items():
        for k, d in [("left", 0), ("parent", 4), ("right", 8)]:
            put(a + d, node[k], 4)
        put(a + 12, 0, 1)
        put(a + 13, node["sentinel"], 1)
    put(slot, start, 4)
    put(s, 0x30303030, 4)
    return dict(
        nodes=nodes,
        registers=regs,
        memory=memory,
        stack=s,
        slot=slot,
        return_address=0x30303030,
    )


def cmp_flags(left, right, width):
    mask = (1 << (width * 8)) - 1
    sign = 1 << (width * 8 - 1)
    value = (left - right) & mask
    return dict(
        CF=int(left < right),
        PF=int((value & 255).bit_count() % 2 == 0),
        AF=int(bool((left ^ right ^ value) & 16)),
        ZF=int(value == 0),
        SF=int(bool(value & sign)),
        OF=int(bool((left ^ right) & (left ^ value) & sign)),
    )


def model_case(
    shape, start, alignment=0, sentinel_byte=1, canonical_head=True, df=0, ops=None
):
    f = case_fixture(shape, start, alignment, sentinel_byte, canonical_head, df)
    expected = predecessor_spec(f["nodes"], start)
    regs = dict(f["registers"])
    memory = dict(f["memory"])
    events = []
    trace = []
    pc = START
    flags = None
    ops = OPS if ops is None else ops
    _require(set(ops) == set(OPS), "operation partition differs")

    def read(arg):
        if arg[0] == "reg":
            return regs[arg[1]]
        if arg[0] == "imm":
            return arg[1]
        _, r, d, w = arg
        a = regs[r] + d
        _require(all(a + j in memory for j in range(w)), "unmapped read")
        v = sum(memory[a + j] << (8 * j) for j in range(w))
        events.append(dict(access="read", address=a, width=w, value=v))
        return v

    def write(arg, v):
        if arg[0] == "reg":
            regs[arg[1]] = v
            return
        _, r, d, w = arg
        a = regs[r] + d
        _require(a == f["slot"] and w == 4, "write escaped slot")
        for j, b in enumerate(v.to_bytes(w, "little")):
            memory[a + j] = b
        events.append(dict(access="write", address=a, width=w, value=v))

    for _ in range(4000):
        _require(pc in ops, "model escaped body")
        trace.append(f"0x{pc:08x}")
        op, *args = ops[pc]
        nxt = pc + SIZES[pc]
        if op == "mov":
            write(args[0], read(args[1]))
        elif op == "cmp":
            flags = cmp_flags(
                read(args[0]), read(args[1]), args[0][3] if args[0][0] == "mem" else 4
            )
        elif op in ("je", "jne"):
            if flags["ZF"] == int(op == "je"):
                nxt = args[0][1] - BASE
        elif op == "nop":
            pass
        elif op == "ret":
            target = read(("mem", "esp", 0, 4))
            regs["esp"] += 4
            break
        else:
            raise PredecessorError("unsupported operation")
        pc = nxt
    else:
        raise PredecessorError("bounded traversal failed")
    final = dict(f["registers"])
    final.update(
        eax=f["slot"],
        edx=f["slot"],
        ecx=f["slot"] if expected["ecx_node"] is None else expected["ecx_node"],
        esp=f["stack"] + 4,
    )
    _require(regs == final and target == f["return_address"], "register oracle differs")
    _require(
        flags == cmp_flags(expected["final_nil_byte"], 0, 1), "flags oracle differs"
    )
    _require(
        [e["value"] for e in events if e["access"] == "write"]
        == expected["slot_write_nodes"],
        "ordered slot write oracle differs",
    )
    desired = dict(f["memory"])
    for j, b in enumerate(expected["predecessor"].to_bytes(4, "little")):
        desired[f["slot"] + j] = b
    _require(memory == desired, "whole memory oracle differs")
    return dict(
        input=dict(
            shape=shape,
            start=start,
            alignment=alignment,
            sentinel_byte=sentinel_byte,
            canonical_head=canonical_head,
            df=df,
        ),
        outcome=expected,
        registers=regs,
        flags=flags,
        df=df,
        events=events,
        trace_rvas=trace,
    )


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
    _require([r.address - BASE for r in rows] == ORDER, "body sites differ")
    for r in rows:
        pc = r.address - BASE
        if r.mnemonic == "nop":
            a = r.operands[0]
            _require(
                pc == 0x7188C
                and r.size == 4
                and len(r.operands) == 1
                and a.type == x86.X86_OP_MEM
                and a.size == 4
                and r.reg_name(a.mem.base) == "eax"
                and not a.mem.index
                and not a.mem.segment
                and a.mem.disp == 0,
                "NOP differs",
            )
            continue
        args = []
        for a in r.operands:
            if a.type == x86.X86_OP_REG:
                args.append(("reg", r.reg_name(a.reg)))
            elif a.type == x86.X86_OP_IMM:
                args.append(("imm", a.imm))
            else:
                _require(
                    a.type == x86.X86_OP_MEM and not a.mem.index and not a.mem.segment,
                    "memory mode differs",
                )
                args.append(("mem", r.reg_name(a.mem.base), a.mem.disp, a.size))
        width = 1 if r.mnemonic == "cmp" and args[0][0] == "mem" else 4
        _require(
            (r.mnemonic, *args) == OPS[pc]
            and r.size == SIZES[pc]
            and [a.size for a in r.operands] == [width] * len(args),
            "exact grammar differs",
        )


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(
        digest == EXE_SHA256 and image.image_base == BASE, "exact executable differs"
    )
    rows = _decode_body(data, image, sources["program_facts"], START)
    _grammar(rows)
    bodyhash = hashlib.sha256(b"".join(bytes(r.bytes) for r in rows)).hexdigest()
    _require(
        bodyhash == "58e3e282d2a5f91126b275aa29a26eb9769d995ca68cb75b619aa2a97d89c192",
        "body digest differs",
    )
    cases = [model_case(**v) for v in vectors()]
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(union == [f"0x{p:08x}" for p in OPS], "modeled union differs")
    controls = []
    for name, pc, op, start in [
        (
            "wrong_ancestor_slot",
            0x71896,
            ("mov", ("mem", "edx", 0, 4), ("reg", "edx")),
            0x10000040,
        ),
        ("wrong_return", 0x718AB, ("mov", ("reg", "eax"), ("imm", 0)), 0x10000100),
    ]:
        changed = dict(OPS)
        changed[pc] = op
        try:
            model_case("left_chain", start, ops=changed)
        except PredecessorError:
            controls.append(dict(name=name, rejected=True))
        else:
            raise PredecessorError("mutation accepted")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=sources["program_facts"]["identity"],
        source_receipts=ids,
        body=dict(
            entry_rva=f"0x{START:08x}",
            exclusive_end_rva=f"0x{END:08x}",
            bytes=94,
            nodes=38,
            sha256=bodyhash,
            points=[_point(r) for r in rows],
        ),
        matrix=dict(
            shapes=SHAPES,
            frame_base=0x02002000,
            alignments=list(range(16)),
            nil_bytes=[1, 128, 255],
            canonical_head=[True, False],
            df=[0, 1],
        ),
        model_evidence=dict(
            cases_sha256=_canonical_sha256(cases),
            instruction_union_rvas=union,
            negative_controls=controls,
        ),
        summary=dict(
            cases=len(cases),
            modeled_nodes=38,
            modeled_bytes=94,
            inorder_cases=sum(c["outcome"]["inorder_corollary"] for c in cases),
            calls=0,
            accounting_promotions=0,
        ),
        scope=dict(
            premises=[
                "Finite acyclic consistent parent and child topology with one nonzero-byte sentinel; stable mapped disjoint node records, iterator slot and caller return word",
                "Finite fixture frame base and all sixteen low alignments; DF is preserved for either entry value",
            ],
            relation="Sentinel selects its right link; ordinary node selects the inorder previous node or sentinel, including every intermediate ancestor slot write",
            corollary="Sentinel entry selects inorder maximum only when its right link names that maximum or itself for the empty tree; structural noncanonical head cases are separate",
            registers="EAX and EDX are the iterator slot; ECX is unchanged at sentinel entry, otherwise last descent node or climb parent; nonvolatiles preserve and ESP advances four",
            flags="Six arithmetic flags follow final byte comparison with zero; DF preserves; NOP has no data access",
            provenance="Exact standalone body pinned by program facts and executable; successor receipt supplies reviewed topology conventions without claiming caller insertion composition",
            not_claimed=[
                "C++ iterator underflow validity, key ordering, balancing, tree ownership, insertion behavior or accounting promotion",
                "Malformed cyclic aliased concurrently modified storage or actual game execution",
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
    def run():
        _validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256
            and evidence["source_receipts"] == ids,
            "sealed predecessor differs",
        )
        _assert_publication_safe(evidence)
        return dict(
            status="structurally_verified",
            evidence_sha256=SEALED_SHA256,
            summary=evidence["summary"],
        )

    return _normalize(run)


def build_semantics(executable, sources):
    def run():
        value = _build_unsealed(executable, sources)
        validate_structure(value, sources)
        return value

    return _normalize(run)


def validate_semantics(executable, evidence, sources):
    validate_structure(evidence, sources)
    _require(
        _canonical_bytes(build_semantics(executable, sources))
        == _canonical_bytes(evidence),
        "exact predecessor differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_semantics(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
