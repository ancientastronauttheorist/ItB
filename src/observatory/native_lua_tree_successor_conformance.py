"""Native call-free successor with an address-generic ordered-memory oracle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.observatory import native_lua_tree_successor_semantics as sem
from src.observatory.native_vector_deallocation_conformance import _sub_flags
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _canonical_sha256,
    _canonical_bytes,
    _source_identity,
    _validate_json_tree,
    _assert_publication_safe,
    _load_executable,
    _point,
)

ANALYSIS_KIND = "pe_native_lua_tree_successor_conformance"
SEALED_SHA256 = "f1429d740a09a4c46d0cec2f4049bb684f44d358ad24dd5ac51774a0ac554422"
START, END = sem.START, sem.END
SOURCE_PINS = {"semantics": (sem.ANALYSIS_KIND, sem.SEALED_SHA256)}
ConformanceError = sem.SuccessorError
_require = sem._require


def _cmp8_zero(value):
    return (
        (int(value == 0) << 6)
        | ((value >> 7) << 7)
        | (int(value.bit_count() % 2 == 0) << 2)
    )


def oracle(vector, fixture):
    """Run at caller-supplied addresses; fixture memory is an actual byte map.

    `nodes` uses the sealed structural schema, `slot` is entry ECX, `stack` is
    entry ESP, and `registers` supplies all eight x86 general registers.
    """
    memory = dict(fixture["memory"])
    nodes, slot, stack = fixture["nodes"], fixture["slot"], fixture["stack"]
    spec = sem.successor_spec(nodes, vector["start"])
    regs = dict(fixture["registers"])
    _require(
        set(regs) == {"eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"}
        and all(type(v) is int and 0 <= v < 2**32 for v in regs.values()),
        "invalid successor registers",
    )
    _require(
        all(
            type(a) is int and 0 <= a < 2**32 and type(v) is int and 0 <= v < 256
            for a, v in memory.items()
        ),
        "invalid successor byte map",
    )
    _require(
        all(type(a) is int and 0 <= a <= 0xFFFFFFFC for a in (slot, stack))
        and stack <= 0xFFFFFFFB
        and regs["ecx"] == slot
        and regs["esp"] == stack,
        "invalid slot or return frame",
    )
    footprints = [(a, a + 14) for a in nodes] + [(slot, slot + 4), (stack, stack + 4)]
    footprints.sort()
    _require(
        all(a[1] <= b[0] for a, b in zip(footprints, footprints[1:])),
        "slot return or nodes overlap",
    )

    def raw(address, width=4):
        _require(
            all(address + i in memory for i in range(width)), "unmapped successor read"
        )
        return sum(memory[address + i] << (8 * i) for i in range(width))

    for address, node in nodes.items():
        _require(
            all(
                raw(address + offset) == node[field]
                for offset, field in ((0, "left"), (4, "parent"), (8, "right"))
            )
            and raw(address + 13, 1) == node["sentinel"],
            "node description and memory differ",
        )
    _require(raw(slot) == vector["start"], "starting slot differs")
    raw(stack)
    events = []

    def read(address, width=4):
        value = raw(address, width)
        events.append(dict(access="read", address=address, width=width, value=value))
        return value

    def write(value):
        events.append(dict(access="write", address=slot, width=4, value=value))
        for i, byte in enumerate(value.to_bytes(4, "little")):
            memory[slot + i] = byte

    current = read(slot)
    marker = read(current + 13, 1)
    flags = _cmp8_zero(marker)
    ecx = slot
    if marker == 0:
        ecx = read(current + 8)
        marker = read(ecx + 13, 1)
        flags = _cmp8_zero(marker)
        if marker == 0:
            child = read(ecx)
            marker = read(child + 13, 1)
            flags = _cmp8_zero(marker)
            while marker == 0:
                ecx = child
                child = read(ecx)
                marker = read(child + 13, 1)
                flags = _cmp8_zero(marker)
            write(ecx)
        else:
            parent = read(current + 4)
            marker = read(parent + 13, 1)
            flags = _cmp8_zero(marker)
            while marker == 0:
                ecx = read(slot)
                right = read(parent + 8)
                flags = _sub_flags(ecx, right)
                if ecx != right:
                    break
                write(parent)
                parent = read(parent + 4)
                marker = read(parent + 13, 1)
                flags = _cmp8_zero(marker)
            write(parent)
    endpoint = read(stack)
    _require(
        raw(slot) == spec["successor"]
        and [e["value"] for e in events if e["access"] == "write"]
        == spec["slot_write_nodes"],
        "independent inorder or ordered ancestor writes differ",
    )
    regs.update(eax=slot, edx=slot, ecx=ecx, esp=stack + 4)
    return dict(
        memory=memory,
        events=events,
        registers=regs,
        flags=flags,
        result=spec["successor"],
        endpoint=endpoint,
        path=spec["path"],
    )


SHAPES = sem.SHAPES + ["deep_right_subtree"]


def _nodes(shape, marker):
    if shape != "deep_right_subtree":
        nodes = sem.tree_fixture(shape, marker)
    else:
        head = 0x10000000
        at = lambda i: head + 64 * i
        layout = {1: (0, 5), 5: (4, 0), 4: (3, 0), 3: (2, 0), 2: (0, 0)}
        nodes = {head: dict(left=head, right=head, parent=head, sentinel=marker)}
        for i, (left, right) in layout.items():
            nodes[at(i)] = dict(left=at(left), right=at(right), parent=head, sentinel=0)
        for i, (left, right) in layout.items():
            for child in (left, right):
                if child:
                    nodes[at(child)]["parent"] = at(i)
    head, order = sem._tree(nodes, next(iter(nodes)))
    if order:
        nodes[head].update(
            left=order[0],
            right=order[-1],
            parent=next(a for a in order if nodes[a]["parent"] == head),
        )
    return nodes


def vectors():
    result = []
    for shape in SHAPES:
        for start in sorted(_nodes(shape, 1)):
            for node_alignment in (0, 7, 15):
                for alignment in (0, 1, 15):
                    for sentinel_byte in (1, 255):
                        for df in (0, 1):
                            result.append(
                                dict(
                                    shape=shape,
                                    start=start + node_alignment,
                                    node_alignment=node_alignment,
                                    alignment=alignment,
                                    sentinel_byte=sentinel_byte,
                                    df=df,
                                    seed=len(result) % 3,
                                )
                            )
    return result


def case_fixture(shape, start, node_alignment, alignment, sentinel_byte, df, seed):
    _require(
        shape in SHAPES
        and all(
            type(value) is int and 0 <= value < limit
            for value, limit in (
                (node_alignment, 16),
                (alignment, 16),
                (sentinel_byte, 256),
                (df, 2),
                (seed, 3),
            )
        )
        and sentinel_byte != 0,
        "invalid successor fixture",
    )
    original = _nodes(shape, sentinel_byte)
    nodes = {
        a
        + node_alignment: {
            key: value if key == "sentinel" else value + node_alignment
            for key, value in node.items()
        }
        for a, node in original.items()
    }
    sem.successor_spec(nodes, start)
    slot, stack = 0x03001000 + node_alignment, 0x02002000 + alignment
    pages = {
        a & ~0xFFF: bytearray(b"\xa5" * 0x1000) for a in list(nodes) + [slot, stack]
    }

    def put(address, value, width=4):
        for i, byte in enumerate(value.to_bytes(width, "little")):
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte

    for address, node in nodes.items():
        for offset, field in ((0, "left"), (4, "parent"), (8, "right")):
            put(address + offset, node[field])
        put(address + 13, node["sentinel"], 1)
    put(slot, start)
    put(stack, 0x44556677)
    regs = {
        r: (0x16273849 + i * 0x01010101 + seed * 0x12345) & 0xFFFFFFFF
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs.update(ecx=slot, esp=stack)
    return dict(
        memory={
            p + i: value
            for p, payload in pages.items()
            for i, value in enumerate(payload)
        },
        nodes=nodes,
        slot=slot,
        stack=stack,
        registers=regs,
    )


def _pages(memory):
    pages = {a & ~0xFFF: bytearray(b"\xa5" * 0x1000) for a in memory}
    for address, value in memory.items():
        pages[address & ~0xFFF][address & 0xFFF] = value
    return {p: bytes(payload) for p, payload in pages.items()}


def _run_case(code, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = case_fixture(**vector)
    expected = oracle(vector, fixture)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    pages = _pages(fixture["memory"])
    for page, payload in pages.items():
        machine.mem_map(page, 0x1000)
        machine.mem_write(page, payload)
    machine.mem_map((BASE + START) & ~0xFFF, 0x1000)
    machine.mem_write((BASE + START) & ~0xFFF, b"\xcc" * 0x1000)
    machine.mem_write(BASE + START, code)
    machine.mem_map(expected["endpoint"] & ~0xFFF, 0x1000)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in fixture["registers"]}
    for register, value in fixture["registers"].items():
        machine.reg_write(ids[register], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246 | (vector["df"] << 10))
    allowed = {int(p["rva"], 16) for p in points}
    visited, events = [], []

    def on_code(m, address, size, user):
        if address == expected["endpoint"]:
            m.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "successor escaped selected body")
        visited.append(f"0x{pc:08x}")
        if pc == START and negative in ("ancestor", "node_padding"):
            at = (
                fixture["stack"] + 4 if negative == "ancestor" else vector["start"] + 14
            )
            m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))
        if negative == "slot" and pc in (0x6DF5E, 0x6DF7E):
            m.mem_write(fixture["slot"], (expected["result"] ^ 1).to_bytes(4, "little"))

    def on_memory(m, access, address, width, value, user):
        _require(
            width in (1, 4)
            and all(address + i in fixture["memory"] for i in range(width)),
            "unmapped native successor access",
        )
        write = access == uc.UC_MEM_WRITE
        events.append(
            dict(
                access="write" if write else "read",
                address=address,
                width=width,
                value=(
                    value
                    if write
                    else int.from_bytes(m.mem_read(address, width), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    machine.emu_start(BASE + START, 0, count=16 * len(fixture["nodes"]) + 40)
    actual = {r: machine.reg_read(i) for r, i in ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "successor endpoint differs",
    )
    _require(
        actual == expected["registers"]
        and flags & 0x8D5 == expected["flags"]
        and (flags >> 10) & 1 == vector["df"],
        "successor registers or flags differ",
    )
    _require(events == expected["events"], "ordered successor events differ")
    _require(
        all(
            bytes(machine.mem_read(page, 0x1000)) == payload
            for page, payload in _pages(expected["memory"]).items()
        ),
        "successor protected memory differs",
    )
    return dict(
        vector=vector,
        registers=actual,
        flags=flags & 0x8D5,
        trace_rvas=visited,
        result=expected["result"],
        path=expected["path"],
        events_sha256=_canonical_sha256(events),
        memory_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(payload).hexdigest()
                for p, payload in _pages(expected["memory"]).items()
            }
        ),
    )


def _preflight(sources):
    _require(
        type(sources) is dict and set(sources) == set(SOURCE_PINS),
        "source partition differs",
    )
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _build_unsealed(executable, sources):
    import capstone

    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE, "exact executable differs"
    )
    offset = image.rva_to_file_offset(START)
    code = data[offset : offset + END - START]
    points = [
        _point(r)
        for r in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
            code, BASE + START
        )
    ]
    body = sources["semantics"]["body"]
    _require(
        points == body["points"]
        and len(code) == 79
        and len(points) == 31
        and hashlib.sha256(code).hexdigest() == body["sha256"],
        "sealed successor body differs",
    )
    observations = [_run_case(code, points, vector) for vector in vectors()]
    union = sorted(
        {pc for observation in observations for pc in observation["trace_rvas"]}
    )
    _require(union == [p["rva"] for p in points], "successor coverage differs")
    controls = []
    for kind in ("ancestor", "node_padding", "slot"):
        try:
            _run_case(code, points, vectors()[0], kind)
        except ConformanceError as exc:
            _require(
                str(exc) == "successor protected memory differs",
                "control failed incidentally",
            )
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("successor mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["semantics"]["build_identity"],
        body=body,
        vectors=vectors(),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        executed_rvas=union,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            instruction_bytes=79,
            static_sites=31,
            executed_sites=len(union),
            normal_returns=len(observations),
            paths=sorted({o["path"] for o in observations}),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Native call-free successor and ordered iterator writes over a finite structural corpus",
            premises=[
                "Stable finite disjoint node records with one nonzero sentinel, consistent links and an independent inorder successor",
                "Address-generic protected byte map with distinct iterator slot and return word",
                "Three node and slot alignments, three stack alignments, three register seeds, two sentinel bytes and both DF values",
            ],
            not_claimed=[
                "Malformed or cyclic graphs, aliases, concurrent mutations, source key ordering or balancing",
                "Caller insertion composition, hardware execution, Lua or game behavior or accounting promotion",
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
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors(),
        "sealed successor evidence differs",
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
        "exact successor evidence differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
