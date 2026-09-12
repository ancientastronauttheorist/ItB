"""Exact lower-bound leaf replay with independent traversal and byte-read oracles."""

from __future__ import annotations
import hashlib, json
from pathlib import Path
from src.observatory import native_tree_lower_bound_semantics as sem
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _load_executable,
    _point,
    _canonical_bytes,
    _canonical_sha256,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "pe_native_tree_lower_bound_conformance"
SEALED_SHA256 = "e45e0ce4ccc42f13ddb3464be09fa3c2146deacfb0c4b738b557e34bc0a9e731"
START = 0x2E8290
TREE, HEAD, NODES, KEYS, ARG, QUERY = (
    0x10000000,
    0x10000100,
    0x10001000,
    0x11000000,
    0x12000000,
    0x12001000,
)


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    recipes = [
        v
        for v in sem.corpus()
        if v["frame_alignment"] == 0 and v["nil_flag"] == 1 and v["seed"] == 0
    ]
    return [
        dict(v, frame_alignment=frame, nil_flag=nil, seed=7)
        for v in recipes
        for frame in range(16)
        for nil in (1, 128, 255)
    ]


def _node(i, addresses=None):
    return HEAD if i is None else NODES + 64 * i if addresses is None else addresses[i]


def caller_mapping(vector, fixture):
    """Resolve explicit caller pointers without changing default synthetic storage."""
    count = len(vector["nodes"])
    addresses = fixture.get("node_addresses", fixture.get("addresses"))
    if addresses is None:
        addresses = [NODES + 64 * i for i in range(count)]
    _require(
        type(addresses) in (list, tuple) and len(addresses) >= count,
        "invalid caller node mapping",
    )
    addresses = list(addresses[:count])
    keys = fixture.get("key_pointers", [KEYS + 256 * i for i in range(count)])
    _require(
        type(keys) in (list, tuple) and len(keys) == count, "invalid caller key mapping"
    )
    query_argument = fixture.get("query_argument", ARG)
    query_pointer = fixture.get("query_pointer", QUERY)
    ranges = [(a, 24) for a in addresses] + [(HEAD, 24), (TREE, 8)]
    for address, width in (
        ranges
        + [(p, len(n["key"]) + 1) for p, n in zip(keys, vector["nodes"])]
        + [(query_argument, 4), (query_pointer, len(vector["query"] or []) + 1)]
    ):
        _require(
            type(address) is int and 0 <= address <= 2**32 - width,
            "invalid caller pointer",
        )
    for i, (address, width) in enumerate(ranges):
        _require(
            all(
                address + width <= other or other + size <= address
                for other, size in ranges[:i]
            ),
            "overlapping caller node mapping",
        )
    pages = fixture.get("pages")
    if pages is not None:
        required = list(ranges)
        required.extend((p, len(n["key"]) + 1) for p, n in zip(keys, vector["nodes"]))
        if vector["root"] is not None or "query_pointer" in fixture:
            required.extend(
                [(query_argument, 4), (query_pointer, len(vector["query"] or []) + 1)]
            )
        _require(
            all(
                ((a + j) & ~0xFFF) in pages
                and len(pages[(a + j) & ~0xFFF]) > ((a + j) & 0xFFF)
                for a, width in required
                for j in range(width)
            ),
            "unmapped caller storage",
        )
    return dict(
        addresses=addresses,
        key_pointers=list(keys),
        query_argument=query_argument,
        query_pointer=query_pointer,
        read_ranges=[(p, len(n["key"]) + 1) for p, n in zip(keys, vector["nodes"])]
        + [(query_pointer, len(vector["query"] or []) + 1)],
    )


def oracle(vector, fixture):
    mapping = caller_mapping(vector, fixture)
    node_at = lambda i: _node(i, mapping["addresses"])
    query_argument, query_pointer = mapping["query_argument"], mapping["query_pointer"]
    nodes = vector["nodes"]
    query = None if vector["query"] is None else bytes(vector["query"])
    root = vector["root"]
    nil = vector["nil_flag"]
    s = fixture["stack"]
    regs = dict(fixture["registers"])
    events = []
    writes = []

    def read(at, width, value):
        events.append(dict(access="read", address=at, width=width, value=value))

    def write(at, width, value):
        events.append(dict(access="write", address=at, width=width, value=value))
        writes.append((at, width, value))

    write(s - 4, 4, regs["ebp"])
    write(s - 8, 4, regs["esi"])
    write(s - 12, 4, regs["edi"])
    read(TREE, 4, HEAD)
    read(HEAD + 4, 4, node_at(root))
    read(node_at(root) + 13, 1, nil if root is None else 0)
    if root is not None:
        read(s + 4, 4, query_argument)
        write(s - 16, 4, regs["ebx"])
        read(query_argument, 4, query_pointer)
    candidate = None
    node = root
    path = []
    while node is not None:
        path.append(node)
        key = bytes(nodes[node]["key"])
        key_address = mapping["key_pointers"][node]
        read(node_at(node) + 16, 4, key_address)
        matched = 0
        while (
            matched < len(key)
            and matched < len(query)
            and key[matched] == query[matched]
        ):
            matched += 1
        # Each compared position is read from node first, then query. The
        # first unequal position or equal terminator is read exactly once.
        for j in range(matched + 1):
            read(key_address + j, 1, key[j] if j < len(key) else 0)
            read(query_pointer + j, 1, query[j] if j < len(query) else 0)
        dl = key[matched] if matched < len(key) else 0
        displacement = matched - (matched % 2)
        if key == query and matched % 2:
            displacement += 2
        regs["ecx"] = key_address + displacement
        regs["edx"] = (regs["edx"] & 0xFFFFFF00) | dl
        if key >= query:
            candidate = node
            offset = 0
            child = nodes[node]["left"]
        else:
            offset = 8
            child = nodes[node]["right"]
        read(node_at(node) + offset, 4, node_at(child))
        read(node_at(child) + 13, 1, nil if child is None else 0)
        node = child
    # Check the stronger interpretation independently through an inorder list,
    # retaining the path result when that ordering premise does not hold.
    inorder = []
    pending = []
    node = root
    while pending or node is not None:
        while node is not None:
            pending.append(node)
            node = nodes[node]["left"]
        node = pending.pop()
        inorder.append(node)
        node = nodes[node]["right"]
    keys = [bytes(nodes[i]["key"]) for i in inorder]
    ordered = keys == sorted(keys)
    if ordered:
        expected = (
            next((i for i in inorder if bytes(nodes[i]["key"]) >= query), None)
            if root is not None
            else None
        )
        _require(candidate == expected, "ordered minimum oracle differs")
    if root is not None:
        read(s - 16, 4, regs["ebx"])
    read(s - 12, 4, regs["edi"])
    read(s - 8, 4, regs["esi"])
    read(s - 4, 4, regs["ebp"])
    read(s, 4, fixture["return_address"])
    regs.update(eax=node_at(candidate), esp=s + 8)
    flags = (int(nil.bit_count() % 2 == 0) << 2) | ((nil >> 7) << 7)
    return dict(
        registers=regs,
        events=events,
        writes=writes,
        flags=flags,
        candidate=candidate,
        path=path,
        ordered=ordered,
    )


def _run_case(code, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    # Only declarative storage and initial-register fixtures are shared. No
    # graph-model result or semantic expected-state helper enters this oracle.
    fixture = sem.case_fixture(**sem.unpack(vector))
    expected = oracle(vector, fixture)
    memory = fixture["memory"]
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    pages = {at & ~0xFFF: bytearray(b"\xa5" * 0x1000) for at in memory}
    for at, value in memory.items():
        pages[at & ~0xFFF][at & 0xFFF] = value
    for page, payload in pages.items():
        machine.mem_map(page, 0x1000)
        machine.mem_write(page, bytes(payload))
    code_page = (BASE + START) & ~0xFFF
    machine.mem_map(code_page, 0x1000)
    machine.mem_write(code_page, b"\xcc" * 0x1000)
    machine.mem_write(BASE + START, code)
    ret = fixture["return_address"]
    machine.mem_map(ret & ~0xFFF, 0x1000)
    machine.mem_write(ret, b"\xcc")
    ids = {
        name: getattr(x, "UC_X86_REG_" + name.upper()) for name in fixture["registers"]
    }
    for name, value in fixture["registers"].items():
        machine.reg_write(ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x402)
    allowed = {int(p["rva"], 16) for p in points}
    visited = []
    events = []

    def on_code(m, address, size, _):
        pc = address - BASE
        _require(pc in allowed, "lower bound escaped leaf graph")
        if negative == "unsigned" and pc == 0x2E82D0:
            m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) & ~1)
        if negative == "upper_edx" and pc == 0x2E82EE:
            m.reg_write(x.UC_X86_REG_EDX, m.reg_read(x.UC_X86_REG_EDX) ^ 0x100)
        visited.append(f"0x{pc:08x}")

    def on_memory(m, kind, at, width, value, _):
        _require(
            width in (1, 4) and all(at + j in memory for j in range(width)),
            "unmapped or oversized leaf data access",
        )
        writing = kind == uc.UC_MEM_WRITE
        if writing:
            _require(
                width == 4
                and at
                in (
                    fixture["stack"] - 4,
                    fixture["stack"] - 8,
                    fixture["stack"] - 12,
                    fixture["stack"] - 16,
                ),
                "unexpected tree mutation",
            )
        events.append(
            dict(
                access="write" if writing else "read",
                address=at,
                width=width,
                value=(
                    value & ((1 << (8 * width)) - 1)
                    if writing
                    else int.from_bytes(m.mem_read(at, width), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    machine.emu_start(BASE + START, ret, count=20000)
    _require(machine.reg_read(x.UC_X86_REG_EIP) == ret, "lower bound did not return")
    regs = {name: machine.reg_read(reg) for name, reg in ids.items()}
    _require(regs == expected["registers"], "lower bound register oracle differs")
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        flags & 0x8D5 == expected["flags"] and flags & 0x400,
        "lower bound flags or unchanged DF differ",
    )
    _require(events == expected["events"], "lower bound ordered read oracle differs")
    for at, width, value in expected["writes"]:
        for j, b in enumerate(value.to_bytes(width, "little")):
            pages[(at + j) & ~0xFFF][(at + j) & 0xFFF] = b
    _require(
        all(
            bytes(machine.mem_read(page, 0x1000)) == bytes(payload)
            for page, payload in pages.items()
        ),
        "lower bound full memory oracle differs",
    )
    return dict(
        vector=vector,
        registers=regs,
        flags=flags & 0x8D5,
        df=1,
        candidate=expected["candidate"],
        ordered=expected["ordered"],
        visited=visited,
        events_sha256=_canonical_sha256(events),
        memory_sha256=_canonical_sha256(
            {
                str(page): hashlib.sha256(payload).hexdigest()
                for page, payload in pages.items()
            }
        ),
    )


def _build_unsealed(executable, semantics):
    import capstone

    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(semantics) == sem.SEALED_SHA256, "lower bound source differs"
    )
    data, image, digest = _load_executable(executable)
    _require(
        digest == EXE_SHA256
        and image.image_base == BASE
        and capstone.__version__ == "5.0.7",
        "exact leaf executable differs",
    )
    offset = image.rva_to_file_offset(START)
    code = data[offset : offset + 97]
    points = [
        _point(r)
        for r in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
            code, BASE + START
        )
    ]
    _require(
        points == semantics["body"]["points"] and len(points) == 44,
        "exact leaf body differs",
    )
    cases = [_run_case(code, points, v) for v in vectors()]
    controls = []
    negative_vector = dict(
        shape="negative",
        nodes=[dict(key=[128], left=None, right=None)],
        root=0,
        query=[255],
        frame_alignment=0,
        nil_flag=128,
        seed=7,
    )
    for control in ("unsigned", "upper_edx"):
        try:
            _run_case(code, points, negative_vector, control)
        except ConformanceError as exc:
            _require(
                "register oracle" in str(exc), "unrelated lower bound mutation failure"
            )
            controls.append(dict(name=control, rejected=True))
        else:
            raise ConformanceError("lower bound mutation accepted")
    union = sorted({pc for case in cases for pc in case["visited"]})
    _require(
        union == semantics["model_evidence"]["instruction_union_rvas"],
        "leaf native coverage differs",
    )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=semantics["build_identity"],
        source_semantics_sha256=sem.SEALED_SHA256,
        body=semantics["body"],
        vectors=vectors(),
        executed_rvas=union,
        observations_sha256=_canonical_sha256(cases),
        negative_controls=controls,
        emulator=dict(name="Unicorn", version="2.1.4", mode_bits=32),
        summary=dict(
            cases=len(cases),
            executed_sites=44,
            executed_bytes=97,
            ordered_cases=sum(c["ordered"] for c in cases),
            unordered_cases=sum(not c["ordered"] for c in cases),
            executed_calls=0,
            negative_controls=2,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact finite tree leaf matches independent unsigned byte traversal, register, flag and ordered read oracles",
            premises=[
                "Same finite tree and terminated stable string domain as sealed semantics, with all sixteen frame alignments and nonzero sentinel bytes 1 128 255",
                "Shared declarative fixture layout, independent replay traversal and state oracle; only exact leaf instructions execute",
                "All mapped pages including padding are preserved except expected saved register stack writes; entry DF is set and checked unchanged",
            ],
            not_claimed=[
                "Parent insertion composition, arbitrary invalid pointers, native balancing or allocations",
                "Actual game execution or accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, semantics):
    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(semantics) == sem.SEALED_SHA256
        and evidence["source_semantics_sha256"] == sem.SEALED_SHA256,
        "sealed leaf replay differs",
    )
    _assert_publication_safe(evidence)
    return dict(
        status="structurally_verified",
        evidence_sha256=SEALED_SHA256,
        summary=evidence["summary"],
    )


def build_conformance(executable, semantics):
    result = _build_unsealed(executable, semantics)
    validate_structure(result, semantics)
    return result


def validate_conformance(executable, evidence, semantics):
    validate_structure(evidence, semantics)
    _require(
        _canonical_bytes(build_conformance(executable, semantics))
        == _canonical_bytes(evidence),
        "exact leaf replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
