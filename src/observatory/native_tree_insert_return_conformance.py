"""Whole native insertion owner with bounded canonical successful hint joins."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_tree_insert_construction_conformance as construction
from src.observatory import native_tree_balancing_conformance as balancing
from src.observatory import native_tree_empty_hint_conformance as empty
from src.observatory import native_tree_extreme_hint_conformance as extreme
from src.observatory import native_tree_interior_hint_conformance as interior
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

ANALYSIS_KIND = "pe_native_tree_insert_return_conformance"
SEALED_SHA256 = "3fe78f6dac77180f9098dced2624beb51524202e50bed7952de6ec17e20a682b"
SOURCE_PINS = {
    "program_facts": construction.SOURCE_PINS["program_facts"],
    "construction": (construction.ANALYSIS_KIND, construction.SEALED_SHA256),
    "empty_hint": (empty.ANALYSIS_KIND, empty.SEALED_SHA256),
    "extreme_hint": (extreme.ANALYSIS_KIND, extreme.SEALED_SHA256),
    "interior_hint": (interior.ANALYSIS_KIND, interior.SEALED_SHA256),
}
START, END = 0x2E81F0, 0x2E8284
OUTPUT = construction.OUTPUT
leaf = construction.leaf
model = balancing.model
ConformanceError = balancing.ConformanceError
_require = balancing._require


def vectors():
    cases = []
    recipes = [([], 0, "empty")]
    for size in (1, 2, 3, 7, 15, 31):
        sequences = [
            list(range(size)),
            list(reversed(range(size))),
            [i // 2 if i % 2 == 0 else size - 1 - i // 2 for i in range(size)],
            balancing._shuffle(size, 0x12345678),
        ]
        for sequence in sequences:
            keys = [2 * i + 1 for i in sequence]
            recipes.extend([(keys, 0, "minimum"), (keys, 2 * size + 1, "end")])
            for gap in sorted({1, size // 2, size - 1} - {0}):
                if gap < size:
                    recipes.append((keys, 2 * gap, "interior"))
            recipes.extend(
                (keys, key, "existing")
                for key in sorted({1, 2 * (size // 2) + 1, 2 * size - 1})
            )
    for keys, key, mode in recipes:
        for node_alignment in (0, 7, 31):
            for frame in (0, 15):
                i = len(cases)
                cases.append(
                    dict(
                        keys=keys,
                        key=key,
                        mode=mode,
                        node_alignment=node_alignment,
                        frame_alignment=frame,
                        nil_flag=(1, 255)[i % 2],
                        previous_seh=(0, 0xFFFFFFFF, 0x18001000, 0x87654321)[
                            (i // 2) % 4
                        ],
                        cookie=(0, 1, 0x80000000, 0xFFFFFFFF, 0xA12598FD)[(i // 8) % 5],
                    )
                )
    return cases


def _fixture(vector):
    for name in ("key", "previous_seh", "cookie"):
        _require(
            type(vector[name]) is int and 0 <= vector[name] < 2**32,
            "invalid insertion scalar",
        )
    _require(
        type(vector["keys"]) is list
        and len(vector["keys"]) <= 31
        and all(type(key) is int and 0 <= key < 2**32 for key in vector["keys"]),
        "invalid insertion key list",
    )
    _require(
        vector["mode"] in ("empty", "minimum", "end", "interior", "existing"),
        "invalid insertion mode",
    )
    expected_mode = (
        "empty"
        if not vector["keys"]
        else (
            "existing"
            if vector["key"] in vector["keys"]
            else (
                "minimum"
                if vector["key"] < min(vector["keys"])
                else "end" if vector["key"] > max(vector["keys"]) else "interior"
            )
        )
    )
    _require(vector["mode"] == expected_mode, "insertion mode and key bounds differ")
    tree = balancing._base_tree(tuple(vector["keys"]))
    _require(len(tree["nodes"]) <= 31, "construction fixture domain exceeded")
    cv = dict(
        nodes=[
            dict(key=list(f'{n["key"]:08x}'.encode()), left=n["left"], right=n["right"])
            for n in tree["nodes"]
        ],
        root=tree["root"],
        query=list(f'{vector["key"]:08x}'.encode()),
        frame_alignment=vector["frame_alignment"],
        nil_flag=vector["nil_flag"],
        seed=7,
        node_alignment=vector["node_alignment"],
    )
    f = construction._fixture(cv)
    pages = {p: bytearray(v) for p, v in f["pages"].items()}
    pages[0] = bytearray(b"\x6d" * 0x1000)
    pages[empty.COOKIE & ~0xFFF] = bytearray(b"\xb7" * 0x1000)

    def put(a, value, width=4):
        for j, b in enumerate(value.to_bytes(width, "little")):
            pages[(a + j) & ~0xFFF][(a + j) & 0xFFF] = b

    addresses = [
        construction.leaf_replay._node(i) for i in range(len(tree["nodes"]))
    ] + [f["node"]]
    at = lambda i: leaf.HEAD if i is None else addresses[i]
    put(leaf.TREE + 4, len(tree["nodes"]))
    put(leaf.HEAD + 12, 1, 1)
    for i, node in enumerate(tree["nodes"]):
        put(addresses[i] + 4, at(node["parent"]))
        put(addresses[i] + 12, node["color"], 1)
    minimum = (
        min(range(len(tree["nodes"])), key=lambda i: tree["nodes"][i]["key"])
        if tree["nodes"]
        else None
    )
    maximum = (
        max(range(len(tree["nodes"])), key=lambda i: tree["nodes"][i]["key"])
        if tree["nodes"]
        else None
    )
    put(leaf.HEAD, at(minimum))
    put(leaf.HEAD + 8, at(maximum))
    put(0, vector["previous_seh"])
    put(empty.COOKIE, vector["cookie"])
    strings = {
        leaf.KEYS + 256 * i: bytes(n["key"]) + b"\0" for i, n in enumerate(cv["nodes"])
    }
    strings[leaf.QUERY] = bytes(cv["query"]) + b"\0"
    for j, b in enumerate(strings[leaf.QUERY]):
        put(leaf.QUERY + j, b, 1)
    existing = vector["key"] in vector["keys"]
    _require(existing == (vector["mode"] == "existing"), "existing profile differs")
    parent, cursor, selector = None, tree["root"], 0
    while cursor is not None:
        parent = cursor
        selector = int(vector["key"] < tree["nodes"][cursor]["key"])
        cursor = tree["nodes"][cursor]["left" if selector else "right"]
    f.update(
        pages={p: bytes(v) for p, v in pages.items()},
        construction_vector=cv,
        tree=tree,
        result=None if existing else model.insert(tree, vector["key"]),
        addresses=addresses,
        strings=strings,
        parent=at(parent),
        selector=selector,
        relation=balancing.attachment.guard_spec(len(tree["nodes"])),
    )
    return f


def _expected(vector, fixture):
    output = fixture.get("output", OUTPUT)
    prefix = construction._expected(fixture["construction_vector"], fixture)
    o = fixture["stack"]
    _require(prefix["ordered"], "canonical lower-bound order required")
    if not prefix["allocate"]:
        _require(vector["mode"] == "existing", "unexpected existing return")
        return dict(
            prefix,
            mode="existing",
            hint_entry=None,
            child_iterations=0,
            child_rotations=0,
        )
    pages = {p: bytearray(v) for p, v in prefix["pages"].items()}
    events = list(prefix["events"])

    def read(a, width=4):
        value = sum(
            pages[(a + j) & ~0xFFF][(a + j) & 0xFFF] << (8 * j) for j in range(width)
        )
        events.append(dict(access="read", address=a, width=width, value=value))
        return value

    def write(a, value, width=4):
        events.append(dict(access="write", address=a, width=width, value=value))
        for j, b in enumerate(value.to_bytes(width, "little")):
            pages[(a + j) & ~0xFFF][(a + j) & 0xFFF] = b

    h = o - 40
    write(h, BASE + 0x2E8270)
    hf = dict(
        fixture,
        s=h,
        output=o - 8,
        pages={p: bytes(v) for p, v in pages.items()},
        registers=dict(prefix["registers"], esp=h),
        child_vector=vector,
    )
    helper = {"empty": empty, "minimum": extreme, "end": extreme, "interior": interior}[
        vector["mode"]
    ]
    joined = helper._expected(vector, hf)
    _require(
        joined["endpoint"] == BASE + 0x2E8270 and joined["registers"]["esp"] == o - 20,
        "hint ancestor join differs",
    )
    pages = {p: bytearray(v) for p, v in joined["pages"].items()}
    events.extend(joined["events"])
    node = read(o - 8)
    _require(node == fixture["node"], "local hint result differs")
    write(output, node)
    write(output + 4, 1, 1)
    for off in (-20, -16, -12, -4):
        read(o + off)
    endpoint = read(o)
    regs = dict(
        fixture["registers"],
        eax=output,
        ecx=joined["registers"]["ecx"],
        edx=joined["registers"]["edx"],
        esp=o + 12,
    )
    return dict(
        registers=regs,
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        flags=0x44,
        flag_mask=0x8D5,
        endpoint=endpoint,
        allocate=True,
        classification=prefix["classification"],
        ordered=True,
        mode=vector["mode"],
        hint_entry=h,
        child_iterations=joined.get("child_iterations", 0),
        child_rotations=joined.get("child_rotations", 0),
    )


def _run_case(codes, points, vector, negative=None, fixture=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector) if fixture is None else fixture
    expected = _expected(vector, fixture)
    o = fixture["stack"]
    m = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, payload in fixture["pages"].items():
        m.mem_map(page, 0x1000)
        m.mem_write(page, payload)
    code_pages = {
        (BASE + a + i) & ~0xFFF
        for a, payload in codes.items()
        for i in range(len(payload))
    }
    for page in sorted(code_pages):
        _require(page not in fixture["pages"], "code and fixture overlap")
        m.mem_map(page, 0x1000)
        m.mem_write(page, b"\xcc" * 0x1000)
    for address, payload in codes.items():
        m.mem_write(BASE + address, payload)
    m.mem_map(construction.IMPORT, 0x1000)
    m.mem_write(construction.IMPORT, b"\xcc")
    m.mem_map(expected["endpoint"] & ~0xFFF, 0x1000)
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in fixture["registers"]}
    for r, value in fixture["registers"].items():
        m.reg_write(ids[r], value)
    m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(p["rva"], 16) for p in points}
    visited, events, summaries = [], [], []
    resume = None

    def on_code(machine, address, size, user):
        nonlocal resume
        if address == construction.IMPORT:
            sp = machine.reg_read(x.UC_X86_REG_ESP)
            words = [
                int.from_bytes(machine.mem_read(sp + 4 * i, 4), "little")
                for i in range(4)
            ]
            _require(
                expected["allocate"]
                and not summaries
                and sp == o - 96
                and words == [BASE + 0x389463, construction.HEAP, 0, 24],
                "insertion heap handoff differs",
            )
            for reg, value in (
                (x.UC_X86_REG_EAX, fixture["node"]),
                (x.UC_X86_REG_ECX, 0xA0000001),
                (x.UC_X86_REG_EDX, 0xB0000001),
                (x.UC_X86_REG_EFLAGS, 0x246),
                (x.UC_X86_REG_ESP, sp + 16),
            ):
                machine.reg_write(reg, value)
            summaries.append(dict(entry_esp=sp, request=24, continuation=words[0]))
            resume = words[0]
            machine.emu_stop()
            return
        if address == expected["endpoint"] or address == BASE + 0x3574D5:
            machine.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "insertion escaped selected bodies")
        visited.append(f"0x{pc:08x}")
        if negative == "seh" and pc == 0x2E84CE:
            machine.mem_write(0, (vector["previous_seh"] ^ 1).to_bytes(4, "little"))
        if negative == "cookie" and pc == 0x3574CA:
            machine.mem_write(
                empty.COOKIE, (vector["cookie"] ^ 1).to_bytes(4, "little")
            )
        if negative == "local_result" and pc == 0x2E8270:
            machine.mem_write(o - 8, (fixture["node"] ^ 1).to_bytes(4, "little"))
        if pc == START:
            at = (
                o + 12
                if negative == "ancestor"
                else fixture["node"] + 14 if negative == "padding" else None
            )
            if at is not None:
                machine.mem_write(
                    at, bytes([int.from_bytes(machine.mem_read(at, 1), "little") ^ 1])
                )

    def memory(machine, access, address, size, value, user):
        _require(size in (1, 2, 4), "unexpected insertion access width")
        write = access == uc.UC_MEM_WRITE
        events.append(
            dict(
                access="write" if write else "read",
                address=address,
                width=size,
                value=(
                    value
                    if write
                    else int.from_bytes(machine.mem_read(address, size), "little")
                ),
            )
        )

    m.hook_add(uc.UC_HOOK_CODE, on_code)
    m.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, memory)
    m.emu_start(BASE + START, 0, count=10000)
    if resume is not None:
        m.emu_start(resume, 0, count=10000)
    if negative == "cookie":
        _require(
            m.reg_read(x.UC_X86_REG_EIP) == BASE + 0x3574D5,
            "cookie control failed at unrelated frontier",
        )
    _require(
        m.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "insertion endpoint differs",
    )
    _require(len(summaries) == int(expected["allocate"]), "insertion API count differs")
    actual = {r: m.reg_read(i) for r, i in ids.items()}
    flags = m.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        actual == expected["registers"]
        and flags & expected["flag_mask"] == expected["flags"] & expected["flag_mask"]
        and not flags & 0x400,
        "insertion registers or flags differ",
    )
    _require(events == expected["events"], "insertion ordered events differ")
    stack_pages = {construction.STACK, construction.STACK + 0x1000}
    _require(
        all(bytes(m.mem_read(p, 0x1000)) == expected["pages"][p] for p in stack_pages),
        "insertion ancestor memory differs",
    )
    _require(
        all(
            bytes(m.mem_read(p, 0x1000)) == v
            for p, v in expected["pages"].items()
            if p not in stack_pages
        ),
        "insertion protected memory differs",
    )
    return dict(
        inputs=vector,
        registers=actual,
        flags=flags & expected["flag_mask"],
        flag_mask=expected["flag_mask"],
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        memory_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(v).hexdigest()
                for p, v in expected["pages"].items()
            }
        ),
        heap_api_summaries=summaries,
        mode=expected["mode"],
        allocate=expected["allocate"],
        hint_entry=expected["hint_entry"],
        child_iterations=expected["child_iterations"],
        child_rotations=expected["child_rotations"],
    )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _load_code(data, image, sources):
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    owner = [
        _point(r) for r in _decode_body(data, image, sources["program_facts"], START)
    ]
    witnessed = {p["rva"]: p for p in owner}
    ranges = [(START, END)]
    for address, body in sources["construction"]["bodies"].items():
        a = int(address, 16)
        ranges.append((a, a + body["instruction_bytes"]))
        for p in body["points"]:
            _require(
                p["rva"] not in witnessed or witnessed[p["rva"]] == p,
                "construction owner witness differs",
            )
            witnessed[p["rva"]] = p
    for name in ("empty_hint", "extreme_hint", "interior_hint"):
        body = sources[name]["body"]
        ranges.extend(
            (int(r["start_rva"], 16), int(r["end_rva"], 16)) for r in body["ranges"]
        )
        for p in body["points"]:
            _require(
                p["rva"] not in witnessed or witnessed[p["rva"]] == p,
                "hint source witness differs",
            )
            witnessed[p["rva"]] = p
    merged = []
    for a, b in sorted(ranges):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    codes, points = {}, []
    for a, b in merged:
        offset = image.rva_to_file_offset(a)
        payload = data[offset : offset + b - a]
        part = [_point(r) for r in decoder.disasm(payload, BASE + a)]
        _require(
            sum(p["size"] for p in part) == b - a
            and all(witnessed.get(p["rva"]) == p for p in part),
            "native insertion source extent differs",
        )
        codes[a] = payload
        points.extend(part)
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
            claim="Whole insertion owner on a finite canonical corpus, existing pair or native successful construction hint rebalancing and inserted pair",
            premises=[
                "At most31 existing nodes generated by independent red-black insertion, fixed-width hexadecimal ordered keys, disjoint writable fresh allocation",
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
