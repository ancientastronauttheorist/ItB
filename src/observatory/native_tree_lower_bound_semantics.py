"""Bounded call-free byte-key tree traversal with a separate ordering corollary."""

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

ANALYSIS_KIND = "pe_native_tree_lower_bound_semantics"
SEALED_SHA256 = "6ea805600da016000532aa0a0da90ec08d598bc53e1778fe241beeed6afeeca9"
SOURCE_PINS = successor.SOURCE_PINS
START, END = 0x2E8290, 0x2E82F1
U32 = 0xFFFFFFFF
TREE, HEAD, NODES, KEYS, ARG, QUERY = (
    0x10000000,
    0x10000100,
    0x10001000,
    0x11000000,
    0x12000000,
    0x12001000,
)
OPS = {
    3048080: ("push", ("reg", "ebp")),
    3048081: ("mov", ("reg", "ebp"), ("reg", "esp")),
    3048083: ("push", ("reg", "esi")),
    3048084: ("push", ("reg", "edi")),
    3048085: ("mov", ("reg", "edi"), ("mem", "ecx", 0, None, 1, 4)),
    3048087: ("mov", ("reg", "esi"), ("mem", "edi", 4, None, 1, 4)),
    3048090: ("cmp", ("mem", "esi", 13, None, 1, 1), ("imm", 0)),
    3048094: ("jne", ("imm", 7242473)),
    3048096: ("mov", ("reg", "eax"), ("mem", "ebp", 8, None, 1, 4)),
    3048099: ("push", ("reg", "ebx")),
    3048100: ("mov", ("reg", "ebx"), ("mem", "eax", 0, None, 1, 4)),
    3048102: ("mov", ("reg", "ecx"), ("mem", "esi", 16, None, 1, 4)),
    3048105: ("mov", ("reg", "eax"), ("reg", "ebx")),
    3048107: ("nop", ("mem", "eax", 0, "eax", 1, 4)),
    3048112: ("mov", ("reg", "dl"), ("mem", "ecx", 0, None, 1, 1)),
    3048114: ("cmp", ("reg", "dl"), ("mem", "eax", 0, None, 1, 1)),
    3048116: ("jne", ("imm", 7242448)),
    3048118: ("test", ("reg", "dl"), ("reg", "dl")),
    3048120: ("je", ("imm", 7242444)),
    3048122: ("mov", ("reg", "dl"), ("mem", "ecx", 1, None, 1, 1)),
    3048125: ("cmp", ("reg", "dl"), ("mem", "eax", 1, None, 1, 1)),
    3048128: ("jne", ("imm", 7242448)),
    3048130: ("add", ("reg", "ecx"), ("imm", 2)),
    3048133: ("add", ("reg", "eax"), ("imm", 2)),
    3048136: ("test", ("reg", "dl"), ("reg", "dl")),
    3048138: ("jne", ("imm", 7242416)),
    3048140: ("xor", ("reg", "eax"), ("reg", "eax")),
    3048142: ("jmp", ("imm", 7242453)),
    3048144: ("sbb", ("reg", "eax"), ("reg", "eax")),
    3048146: ("or", ("reg", "eax"), ("imm", 1)),
    3048149: ("test", ("reg", "eax"), ("reg", "eax")),
    3048151: ("jns", ("imm", 7242462)),
    3048153: ("mov", ("reg", "esi"), ("mem", "esi", 8, None, 1, 4)),
    3048156: ("jmp", ("imm", 7242466)),
    3048158: ("mov", ("reg", "edi"), ("reg", "esi")),
    3048160: ("mov", ("reg", "esi"), ("mem", "esi", 0, None, 1, 4)),
    3048162: ("cmp", ("mem", "esi", 13, None, 1, 1), ("imm", 0)),
    3048166: ("je", ("imm", 7242406)),
    3048168: ("pop", ("reg", "ebx")),
    3048169: ("mov", ("reg", "eax"), ("reg", "edi")),
    3048171: ("pop", ("reg", "edi")),
    3048172: ("pop", ("reg", "esi")),
    3048173: ("pop", ("reg", "ebp")),
    3048174: ("ret", ("imm", 4)),
}
SIZES = {
    3048080: 1,
    3048081: 2,
    3048083: 1,
    3048084: 1,
    3048085: 2,
    3048087: 3,
    3048090: 4,
    3048094: 2,
    3048096: 3,
    3048099: 1,
    3048100: 2,
    3048102: 3,
    3048105: 2,
    3048107: 5,
    3048112: 2,
    3048114: 2,
    3048116: 2,
    3048118: 2,
    3048120: 2,
    3048122: 3,
    3048125: 3,
    3048128: 2,
    3048130: 3,
    3048133: 3,
    3048136: 2,
    3048138: 2,
    3048140: 2,
    3048142: 2,
    3048144: 2,
    3048146: 3,
    3048149: 2,
    3048151: 2,
    3048153: 3,
    3048156: 2,
    3048158: 2,
    3048160: 2,
    3048162: 4,
    3048166: 2,
    3048168: 1,
    3048169: 2,
    3048171: 1,
    3048172: 1,
    3048173: 1,
    3048174: 3,
}
WIDTHS = {
    3048080: [4],
    3048081: [4, 4],
    3048083: [4],
    3048084: [4],
    3048085: [4, 4],
    3048087: [4, 4],
    3048090: [1, 1],
    3048094: [4],
    3048096: [4, 4],
    3048099: [4],
    3048100: [4, 4],
    3048102: [4, 4],
    3048105: [4, 4],
    3048107: [4],
    3048112: [1, 1],
    3048114: [1, 1],
    3048116: [4],
    3048118: [1, 1],
    3048120: [4],
    3048122: [1, 1],
    3048125: [1, 1],
    3048128: [4],
    3048130: [4, 4],
    3048133: [4, 4],
    3048136: [1, 1],
    3048138: [4],
    3048140: [4, 4],
    3048142: [4],
    3048144: [4, 4],
    3048146: [4, 4],
    3048149: [4, 4],
    3048151: [4],
    3048153: [4, 4],
    3048156: [4],
    3048158: [4, 4],
    3048160: [4, 4],
    3048162: [1, 1],
    3048166: [4],
    3048168: [4],
    3048169: [4, 4],
    3048171: [4],
    3048172: [4],
    3048173: [4],
    3048174: [4],
}


class LowerBoundError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise LowerBoundError(message)


def _u32(value):
    _require(type(value) is int and 0 <= value <= U32, "invalid unsigned word")


def _normalize(fn):
    try:
        return fn()
    except LowerBoundError:
        raise
    except Exception as exc:
        raise LowerBoundError(str(exc)) from exc


def _domain(nodes, root, query):
    _require(type(nodes) is list and len(nodes) <= 31, "invalid finite node list")
    _require(
        root is None or type(root) is int and 0 <= root < len(nodes), "invalid root"
    )
    for node in nodes:
        _require(
            type(node) is dict and set(node) == {"key", "left", "right"},
            "invalid node fields",
        )
        _require(
            type(node["key"]) is bytes
            and b"\0" not in node["key"]
            and len(node["key"]) <= 64,
            "invalid terminated key",
        )
        for child in (node["left"], node["right"]):
            _require(
                child is None or type(child) is int and 0 <= child < len(nodes),
                "invalid child",
            )
    seen = set()
    inorder = []

    def walk(index):
        if index is None:
            return
        _require(index not in seen, "cyclic or shared node")
        seen.add(index)
        walk(nodes[index]["left"])
        inorder.append(index)
        walk(nodes[index]["right"])

    walk(root)
    _require(len(seen) == len(nodes), "unreachable node")
    if root is not None:
        _require(
            type(query) is bytes and b"\0" not in query and len(query) <= 64,
            "invalid terminated query",
        )
    else:
        _require(
            query is None
            or type(query) is bytes
            and b"\0" not in query
            and len(query) <= 64,
            "invalid optional empty-tree query",
        )
    return inorder


def traversal_spec(nodes, root, query):
    inorder = _domain(nodes, root, query)
    ordered = all(
        nodes[a]["key"] <= nodes[b]["key"] for a, b in zip(inorder, inorder[1:])
    )
    cursor = root
    candidate = None
    path = []
    while cursor is not None:
        key = nodes[cursor]["key"]
        less = key < query
        path.append(cursor)
        if not less:
            candidate = cursor
        cursor = nodes[cursor]["right" if less else "left"]
    minimum = (
        next((i for i in inorder if nodes[i]["key"] >= query), None)
        if ordered and root is not None
        else None
    )
    if ordered:
        _require(candidate == minimum, "ordered lower bound corollary differs")
    return dict(
        candidate=candidate,
        path=path,
        ordered=ordered,
        inorder=inorder,
        minimum_lower_bound=minimum if ordered else None,
    )


def _address(index):
    return HEAD if index is None else NODES + 64 * index


def _key_address(index):
    return KEYS + 256 * index


def case_fixture(nodes, root, query, frame_alignment=0, nil_flag=1, seed=1):
    relation = traversal_spec(nodes, root, query)
    _require(
        type(frame_alignment) is int and 0 <= frame_alignment < 16,
        "invalid frame alignment",
    )
    _require(type(nil_flag) is int and 1 <= nil_flag <= 255, "invalid sentinel byte")
    _u32(seed)
    stack = 0x30001000 + frame_alignment
    regs = {
        name: (0xA1000000 + i * 0x10101 + seed) & U32
        for i, name in enumerate(
            ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
        )
    }
    regs.update(ecx=TREE, esp=stack)
    memory = {stack + i: ((i * 23) ^ seed) & 255 for i in range(-24, 16)}

    def put(at, width, value):
        memory.update(
            {at + i: b for i, b in enumerate(value.to_bytes(width, "little"))}
        )

    ret = (0x44556677 + seed) & U32
    put(stack, 4, ret)
    put(stack + 4, 4, ARG if root is not None else 0xDEADF000)
    put(TREE, 4, HEAD)
    for at in [HEAD] + [_address(i) for i in range(len(nodes))]:
        memory.update({at + i: ((i * 17) ^ seed) & 255 for i in range(32)})
    put(HEAD + 4, 4, _address(root))
    put(HEAD + 13, 1, nil_flag)
    for i, node in enumerate(nodes):
        at = _address(i)
        put(at, 4, _address(node["left"]))
        put(at + 8, 4, _address(node["right"]))
        put(at + 13, 1, 0)
        put(at + 16, 4, _key_address(i))
        memory.update(
            {_key_address(i) + j: b for j, b in enumerate(node["key"] + b"\0")}
        )
    if root is not None:
        put(ARG, 4, QUERY)
        memory.update({QUERY + j: b for j, b in enumerate(query + b"\0")})
    return dict(
        registers=regs,
        memory=memory,
        stack=stack,
        return_address=ret,
        relation=relation,
    )


def _alu(left, right, width=4, carry=0):
    bits = 8 * width
    mask = (1 << bits) - 1
    value = (left - right - carry) & mask
    return value, dict(
        cf=int(left < right + carry),
        pf=int((value & 255).bit_count() % 2 == 0),
        af=((left ^ right ^ value) >> 4) & 1,
        zf=int(value == 0),
        sf=value >> (bits - 1),
        of=((left ^ right) & (left ^ value)) >> (bits - 1),
    )


def _logic(value, width=4):
    return dict(
        cf=0,
        pf=int((value & 255).bit_count() % 2 == 0),
        af=None,
        zf=int(value == 0),
        sf=value >> (width * 8 - 1),
        of=0,
    )


def _expected(nodes, root, query, fixture, nil_flag):
    relation = traversal_spec(nodes, root, query)
    regs = dict(fixture["registers"])
    memory = dict(fixture["memory"])
    events = []
    stack = fixture["stack"]

    def event(kind, at, width, value):
        events.append(dict(kind=kind, address=at, width=width, value=value))
        if kind == "write":
            memory.update(
                {at + i: b for i, b in enumerate(value.to_bytes(width, "little"))}
            )

    for offset, name in ((-4, "ebp"), (-8, "esi"), (-12, "edi")):
        event("write", stack + offset, 4, regs[name])
    event("read", TREE, 4, HEAD)
    event("read", HEAD + 4, 4, _address(root))
    event("read", _address(root) + 13, 1, nil_flag if root is None else 0)
    if root is not None:
        event("read", stack + 4, 4, ARG)
        event("write", stack - 16, 4, regs["ebx"])
        event("read", ARG, 4, QUERY)
    for index in relation["path"]:
        node = nodes[index]
        key = node["key"]
        event("read", _address(index) + 16, 4, _key_address(index))
        # Built-in unsigned bytes ordering decides the branch; sequential
        # first-difference reads independently determine the cursor and DL.
        mismatch = 0
        for j, (left, right) in enumerate(zip(key + b"\0", query + b"\0")):
            event("read", _key_address(index) + j, 1, left)
            event("read", QUERY + j, 1, right)
            mismatch = j
            if left != right or left == 0:
                break
        cursor = (mismatch // 2) * 2
        if key == query and mismatch % 2:
            cursor += 2
        regs["ecx"] = _key_address(index) + cursor
        regs["edx"] = (regs["edx"] & 0xFFFFFF00) | left
        child = node["right"] if key < query else node["left"]
        event("read", _address(index) + (8 if key < query else 0), 4, _address(child))
        event("read", _address(child) + 13, 1, nil_flag if child is None else 0)
    if root is not None:
        event("read", stack - 16, 4, regs["ebx"])
    for offset, name in ((-12, "edi"), (-8, "esi"), (-4, "ebp")):
        event("read", stack + offset, 4, regs[name])
    event("read", stack, 4, fixture["return_address"])
    regs.update(eax=_address(relation["candidate"]), esp=stack + 8)
    return dict(
        registers=regs,
        memory=memory,
        events=events,
        flags=_alu(nil_flag, 0, 1)[1],
        relation=relation,
    )


def model_case(nodes, root, query, frame_alignment=0, nil_flag=1, seed=1, ops=None):
    fixture = case_fixture(nodes, root, query, frame_alignment, nil_flag, seed)
    expected = _expected(nodes, root, query, fixture, nil_flag)
    regs = dict(fixture["registers"])
    memory = dict(fixture["memory"])
    events = []
    trace = []
    flags = None
    pc = START
    operations = OPS if ops is None else ops

    def access(at, width):
        _require(all(at + i in memory for i in range(width)), "unmapped tree read")
        value = int.from_bytes(bytes(memory[at + i] for i in range(width)), "little")
        events.append(dict(kind="read", address=at, width=width, value=value))
        return value

    def address(arg):
        return (regs[arg[1]] + arg[2] + (regs[arg[3]] * arg[4] if arg[3] else 0)) & U32

    def read(arg):
        if arg[0] == "imm":
            return arg[1] & U32
        if arg[0] == "reg":
            return regs["edx"] & 255 if arg[1] == "dl" else regs[arg[1]]
        return access(address(arg), arg[5])

    def write(arg, value):
        if arg[0] == "reg":
            if arg[1] == "dl":
                regs["edx"] = (regs["edx"] & 0xFFFFFF00) | (value & 255)
            else:
                regs[arg[1]] = value & U32
        else:
            at = address(arg)
            width = arg[5]
            _require(all(at + i in memory for i in range(width)), "unmapped tree write")
            memory.update(
                {at + i: b for i, b in enumerate(value.to_bytes(width, "little"))}
            )
            events.append(dict(kind="write", address=at, width=width, value=value))

    while True:
        _require(
            pc in operations and len(trace) < 20000, "tree model escaped bounded graph"
        )
        trace.append(f"0x{pc:08x}")
        op, *args = operations[pc]
        nxt = pc + SIZES[pc]
        if op == "push":
            value = read(args[0])
            regs["esp"] -= 4
            write(("mem", "esp", 0, None, 1, 4), value)
        elif op == "pop":
            write(args[0], access(regs["esp"], 4))
            regs["esp"] += 4
        elif op == "mov":
            write(args[0], read(args[1]))
        elif op == "nop":
            pass
        elif op in ("cmp", "sbb"):
            width = (
                1
                if args[0] == ("reg", "dl") or args[0][0] == "mem" and args[0][5] == 1
                else 4
            )
            value, flags = _alu(
                read(args[0]), read(args[1]), width, flags["cf"] if op == "sbb" else 0
            )
            if op == "sbb":
                write(args[0], value)
        elif op == "add":
            left, right = read(args[0]), read(args[1])
            value = (left + right) & U32
            flags = dict(
                cf=int(left + right > U32),
                pf=int((value & 255).bit_count() % 2 == 0),
                af=((left ^ right ^ value) >> 4) & 1,
                zf=int(value == 0),
                sf=value >> 31,
                of=((~(left ^ right) & (left ^ value) & U32) >> 31),
            )
            write(args[0], value)
        elif op in ("test", "xor", "or"):
            left, right = read(args[0]), read(args[1])
            value = (
                left & right
                if op == "test"
                else left ^ right if op == "xor" else left | right
            )
            flags = _logic(value, 1 if args[0] == ("reg", "dl") else 4)
            if op != "test":
                write(args[0], value)
        elif op in ("je", "jne", "jns", "jmp"):
            take = (
                op == "jmp"
                or op == "je"
                and flags["zf"]
                or op == "jne"
                and not flags["zf"]
                or op == "jns"
                and not flags["sf"]
            )
            if take:
                nxt = read(args[0]) - BASE
        elif op == "ret":
            returned = access(regs["esp"], 4)
            regs["esp"] += 4 + read(args[0])
            break
        else:
            raise LowerBoundError("unsupported tree operation")
        pc = nxt
    _require(
        regs == expected["registers"] and flags == expected["flags"],
        "tree register or flag oracle differs",
    )
    _require(
        events == expected["events"] and memory == expected["memory"],
        "tree ordered memory oracle differs",
    )
    _require(returned == fixture["return_address"], "tree return target differs")
    return dict(
        registers=regs,
        arithmetic_flags=flags,
        events=events,
        trace_rvas=trace,
        relation=expected["relation"],
        memory_sha256=_canonical_sha256(
            [list(item) for item in sorted(memory.items())]
        ),
    )


def corpus():
    keys = [b"", b"a", b"aa", b"ab", b"b", b"\x80", b"\xff"]
    trees = []
    for shape in ("balanced", "left", "right"):
        nodes = [dict(key=k, left=None, right=None) for k in keys]

        def connect(ids):
            if not ids:
                return None
            slot = (
                len(ids) - 1
                if shape == "left"
                else 0 if shape == "right" else len(ids) // 2
            )
            i = ids[slot]
            nodes[i].update(left=connect(ids[:slot]), right=connect(ids[slot + 1 :]))
            return i

        trees.append((shape, nodes, connect(list(range(len(keys))))))
    trees += [
        ("empty", [], None),
        ("single", [dict(key=b"a", left=None, right=None)], 0),
        (
            "duplicates",
            [
                dict(key=b"a", left=1, right=2),
                dict(key=b"a", left=None, right=None),
                dict(key=b"a", left=None, right=None),
            ],
            0,
        ),
        (
            "unordered",
            [
                dict(key=b"a", left=1, right=2),
                dict(key=b"z", left=None, right=None),
                dict(key=b"", left=None, right=None),
            ],
            0,
        ),
        (
            "prefix",
            [
                dict(key=b"q" * 32 + b"b", left=1, right=2),
                dict(key=b"q" * 32 + b"a", left=None, right=None),
                dict(key=b"q" * 32 + b"c", left=None, right=None),
            ],
            0,
        ),
    ]
    trees.append(
        (
            "deep",
            [
                dict(
                    key=b"p" * 63 + bytes([i + 1]),
                    left=None,
                    right=i + 1 if i < 30 else None,
                )
                for i in range(31)
            ],
            0,
        )
    )
    queries = [
        b"",
        b"a",
        b"aa",
        b"aaa",
        b"ab",
        b"b",
        b"\x7f",
        b"\x80",
        b"\xff",
        b"\xff\xff",
        b"q" * 32 + b"a",
        b"q" * 32 + b"b",
        b"q" * 32 + b"z",
        b"p" * 63 + b"\x10",
        b"p" * 63 + b"\xff",
    ]
    return [
        dict(
            shape=shape,
            nodes=[dict(n, key=list(n["key"])) for n in nodes],
            root=root,
            query=None if root is None else list(query),
            frame_alignment=frame,
            nil_flag=nil,
            seed=seed,
        )
        for shape, nodes, root in trees
        for query in (queries if root is not None else [None])
        for frame in (0, 1, 7, 15)
        for nil in (1, 128, 255)
        for seed in (0, 255)
    ]


def unpack(vector):
    return dict(
        nodes=[dict(n, key=bytes(n["key"])) for n in vector["nodes"]],
        root=vector["root"],
        query=None if vector["query"] is None else bytes(vector["query"]),
        frame_alignment=vector["frame_alignment"],
        nil_flag=vector["nil_flag"],
        seed=vector["seed"],
    )


def _preflight(sources):
    _require(
        isinstance(sources, Mapping) and set(sources) == set(SOURCE_PINS),
        "source partition differs",
    )
    return {
        key: _source_identity(sources[key], kind, digest, key)
        for key, (kind, digest) in SOURCE_PINS.items()
    }


def _grammar(rows):
    _require(
        [r.address - BASE for r in rows] == list(OPS),
        "tree instruction partition differs",
    )
    for row in rows:
        args = []
        for arg in row.operands:
            if arg.type == x86.X86_OP_REG:
                args.append(("reg", row.reg_name(arg.reg)))
            elif arg.type == x86.X86_OP_IMM:
                args.append(("imm", arg.imm))
            else:
                _require(
                    arg.type == x86.X86_OP_MEM and not arg.mem.segment,
                    "unexpected tree operand",
                )
                args.append(
                    (
                        "mem",
                        row.reg_name(arg.mem.base),
                        arg.mem.disp,
                        row.reg_name(arg.mem.index) if arg.mem.index else None,
                        arg.mem.scale,
                        arg.size,
                    )
                )
        pc = row.address - BASE
        _require(
            (row.mnemonic, *args) == OPS[pc]
            and row.size == SIZES[pc]
            and [a.size for a in row.operands] == WIDTHS[pc],
            "tree exact grammar differs",
        )


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(
        digest == EXE_SHA256 and image.image_base == BASE, "exact executable differs"
    )
    rows = _decode_body(data, image, sources["program_facts"], START)
    _grammar(rows)
    owner = _decode_body(data, image, sources["program_facts"], 0x2E81F0)
    call = next(r for r in owner if r.address - BASE == 0x2E81FF)
    _require(
        call.id == x86.X86_INS_CALL and call.operands[0].imm == BASE + START,
        "incoming leaf edge differs",
    )
    chain = next(
        e
        for e in sources["chain"]["native_edges"]
        if e["target_entry_rva"] == "0x002e81f0"
    )
    _require(
        sum(r.size for r in owner) == chain["target_body_size"] == 148
        and hashlib.sha256(b"".join(r.bytes for r in owner)).hexdigest()
        == chain["target_body_sha256"],
        "pinned insertion owner differs",
    )
    grandparent = _decode_body(data, image, sources["program_facts"], 0x2EB140)
    edge = next(r for r in grandparent if r.address - BASE == 0x2EB19A)
    _require(
        _point(edge) == chain["instruction"]
        and edge.operands[0].imm == BASE + 0x2E81F0,
        "chain owner edge differs",
    )
    vectors = corpus()
    cases = []
    for vector in vectors:
        case = model_case(**unpack(vector))
        cases.append(
            dict(
                sha256=_canonical_sha256(case),
                trace=case["trace_rvas"],
                ordered=case["relation"]["ordered"],
            )
        )
    union = sorted({p for c in cases for p in c["trace"]})
    _require(union == [f"0x{p:08x}" for p in OPS], "tree case coverage differs")
    controls = []
    node = [dict(key=b"a", left=None, right=None)]
    for name, pc, operation in [
        ("wrong_branch", 0x2E82D7, ("jne", ("imm", BASE + 0x2E82DE))),
        (
            "wrong_query_byte",
            0x2E82BD,
            ("cmp", ("reg", "dl"), ("mem", "eax", 0, None, 1, 1)),
        ),
        ("wrong_saved_register", 0x2E82EB, ("pop", ("reg", "edx"))),
    ]:
        changed = dict(OPS)
        changed[pc] = operation
        try:
            model_case(node, 0, b"a", ops=changed)
        except LowerBoundError:
            controls.append(dict(name=name, rejected=True))
        else:
            raise LowerBoundError("tree mutation accepted")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=sources["program_facts"]["identity"],
        source_receipts=ids,
        body=dict(
            entry_rva=f"0x{START:08x}",
            bytes=sum(r.size for r in rows),
            nodes=len(rows),
            points=[_point(r) for r in rows],
        ),
        static_lineage=dict(
            chain_edge=_point(edge),
            insertion_owner=dict(
                entry_rva="0x002e81f0", bytes=148, points=[_point(r) for r in owner]
            ),
            leaf_call=_point(call),
        ),
        vectors=vectors,
        model_evidence=dict(
            cases_sha256=_canonical_sha256(cases),
            instruction_union_rvas=union,
            negative_controls=controls,
        ),
        summary=dict(
            cases=len(cases),
            modeled_nodes=44,
            modeled_bytes=97,
            ordered_cases=sum(c["ordered"] for c in cases),
            unordered_cases=sum(not c["ordered"] for c in cases),
            actual_native_executions=0,
            calls=0,
            accounting_promotions=0,
        ),
        scope=dict(
            premises=[
                "Finite rooted binary tree with at most 31 nodes, no sharing or cycles and a common nonzero-byte sentinel",
                "Readable stable keys and nonempty-tree query are NUL terminated byte strings of at most 64 bytes before the terminator",
                "Tree, key, query and protected stable caller frame storage are disjoint; finite frame base is 0x30001000 with listed alignments",
            ],
            structural_relation="Unsigned lexicographic node key below query follows right child; otherwise node becomes candidate and traversal follows left child until sentinel",
            ordering_corollary="Only when inorder keys are nondecreasing does the result equal the first inorder node with key at least query; duplicate keys are allowed",
            registers="EAX returns candidate or head, ECX retains entry tree on empty root otherwise the final node-key cursor; EDX upper 24 bits preserve and DL is the last compared node byte; saved registers restore and RET4 advances ESP eight",
            flags="Final arithmetic flags are the eight bit compare of nonzero sentinel byte with zero, including its sign and parity",
            empty="Empty root performs no query argument or query string read; memory-shaped NOP performs no data access",
            not_claimed=[
                "Insertion owner composition, allocation, balancing, comparator callbacks, arbitrary invalid pointers or whole library equivalence",
                "Actual native execution or global accounting promotion",
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
            "sealed lower bound differs",
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
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_semantics(executable, evidence, sources):
    validate_structure(evidence, sources)
    _require(
        _canonical_bytes(build_semantics(executable, sources))
        == _canonical_bytes(evidence),
        "exact lower bound differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_semantics(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
