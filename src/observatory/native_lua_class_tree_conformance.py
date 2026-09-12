"""Native class tree-copy prefix with successful insertion and successor joins."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import capstone

from src.observatory import native_tree_insert_return_conformance as insertion
from src.observatory import native_lua_tree_successor_conformance as successor
from src.observatory import native_lua_class_tree_semantics as model
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

ANALYSIS_KIND = "pe_native_lua_class_tree_conformance"
SEALED_SHA256 = "0e03dd20ee8451eafd6aa848c8a405e924c38dd6abde121c7c06fdba9ea8358d"
SOURCE_PINS = {
    "program_facts": insertion.SOURCE_PINS["program_facts"],
    "class_chain": (
        "pe_native_lua_class_return_helper_chain",
        "33ad87a98131700dce12bd34a7febea3159b6f461710f0b8296d95ded1b37095",
    ),
    "insertion_return": (insertion.ANALYSIS_KIND, insertion.SEALED_SHA256),
    "successor": (successor.ANALYSIS_KIND, successor.SEALED_SHA256),
}
START, STOP = 0x2EB140, 0x2EB1BB
OWNER_SHA256 = "2184616f615a261d2b3781fe7f0840780afd79150544323341f668f58f9b821b"
leaf, construction = insertion.leaf, insertion.construction
RECEIVER = leaf.TREE - 0x34
SOURCE_OBJECT, SOURCE_HEAD, SOURCE_NODES, SOURCE_KEYS, ARGUMENT = (
    0x14000000,
    0x14000100,
    0x14001000,
    0x15000000,
    0x14000200,
)
ConformanceError = insertion.ConformanceError
_require = insertion._require


def _mode(keys, key):
    return (
        "empty"
        if not keys
        else (
            "existing"
            if key in keys
            else (
                "minimum"
                if key < min(keys)
                else "end" if key > max(keys) else "interior"
            )
        )
    )


def vectors():
    recipes = []
    for size in range(8):
        for profile in ("empty_source", "all_new", "all_existing", "mixed"):
            source = [] if profile == "empty_source" else list(range(1, size + 1))
            destination = (
                list(range(11, 11 + size))
                if profile in ("empty_source", "all_new")
                else (
                    list(reversed(source))
                    if profile == "all_existing"
                    else [2 * i for i in range(1, size + 1)]
                )
            )
            if profile == "all_new" and size % 2 == 0:
                destination = []
            if size % 2:
                source.reverse()
            recipes.append((profile, source, destination))
    return [
        dict(
            profile=profile,
            source_keys=source,
            destination_keys=destination,
            node_alignment=alignment,
            frame_alignment=frame,
            nil_flag=(1, 255)[index % 2],
            previous_seh=(0, 0xFFFFFFFF, 0x18001000, 0x87654321)[index % 4],
            cookie=(0, 1, 0xA12598FD, 0xFFFFFFFF)[(index // 4) % 4],
            payload_seed=(0x75310000, 0xFFFFFFFF)[(index // 16) % 2],
        )
        for index, (profile, source, destination, alignment, frame) in enumerate(
            (p, s, d, a, f) for p, s, d in recipes for a in (0, 7, 31) for f in (0, 15)
        )
    ]


def _fixture(vector):
    for name in ("source_keys", "destination_keys"):
        _require(
            type(vector[name]) is list
            and len(vector[name]) <= 7
            and all(type(k) is int and 0 <= k < 2**32 for k in vector[name]),
            "invalid class key sequence",
        )
    _require(
        type(vector["payload_seed"]) is int and 0 <= vector["payload_seed"] < 2**32,
        "invalid payload seed",
    )
    key = vector["source_keys"][0] if vector["source_keys"] else 0
    iv = dict(
        keys=vector["destination_keys"],
        key=key,
        mode=_mode(vector["destination_keys"], key),
        node_alignment=vector["node_alignment"],
        frame_alignment=vector["frame_alignment"],
        nil_flag=vector["nil_flag"],
        previous_seh=vector["previous_seh"],
        cookie=vector["cookie"],
    )
    fixture = insertion._fixture(iv)
    entry = fixture["stack"]
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}

    def ensure(address):
        pages.setdefault(address & ~0xFFF, bytearray(b"\xa5" * 0x1000))

    def put(address, value, width=4):
        for i, byte in enumerate(value.to_bytes(width, "little")):
            ensure(address + i)
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte

    source_tree = insertion.model.from_keys(vector["source_keys"])
    source_payloads = [
        (vector["payload_seed"] ^ (i * 0x01010101)) & 0xFFFFFFFF
        for i in range(len(source_tree["nodes"]))
    ]
    dest_payloads = [
        (0x34560000 + i * 0x1234) & 0xFFFFFFFF
        for i in range(len(fixture["tree"]["nodes"]))
    ]
    addresses = [
        SOURCE_NODES + 64 * i + vector["node_alignment"]
        for i in range(len(source_tree["nodes"]))
    ]
    at = lambda i: SOURCE_HEAD if i is None else addresses[i]
    ensure(RECEIVER)
    put(SOURCE_OBJECT + 0x34, SOURCE_HEAD)
    put(ARGUMENT, 0xA3125678)
    put(ARGUMENT + 4, SOURCE_OBJECT)
    put(entry + 4, ARGUMENT)
    put(SOURCE_HEAD + 12, 1, 1)
    put(SOURCE_HEAD + 13, vector["nil_flag"], 1)
    strings = dict(fixture["strings"])
    for i, node in enumerate(source_tree["nodes"]):
        for offset, field in ((0, "left"), (4, "parent"), (8, "right")):
            put(at(i) + offset, at(node[field]))
        put(at(i) + 12, node["color"], 1)
        put(at(i) + 13, 0, 1)
        ptr = SOURCE_KEYS + 32 * i + (vector["node_alignment"] % 4)
        payload = f'{node["key"]:08x}'.encode() + b"\0"
        strings[ptr] = payload
        for j, byte in enumerate(payload):
            put(ptr + j, byte, 1)
        put(at(i) + 16, ptr)
        put(at(i) + 20, source_payloads[i])
    order = sorted(range(len(addresses)), key=lambda i: source_tree["nodes"][i]["key"])
    for offset, identity in (
        (0, order[0] if order else None),
        (4, source_tree["root"]),
        (8, order[-1] if order else None),
    ):
        put(SOURCE_HEAD + offset, at(identity))
    for i, payload in enumerate(dest_payloads):
        put(fixture["addresses"][i] + 20, payload)
    registers = {
        r: (0x16273849 + i * 0x01010101 + vector["frame_alignment"]) & 0xFFFFFFFF
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    registers.update(ecx=RECEIVER, esp=entry)
    fixture.update(
        pages={p: bytes(v) for p, v in pages.items()},
        registers=registers,
        source_state=dict(tree=source_tree, payloads=source_payloads),
        destination_state=dict(tree=fixture["tree"], payloads=dest_payloads),
        source_addresses=addresses,
        destination_addresses=fixture["addresses"][:-1],
        strings=strings,
    )
    fixture["transfer"] = model.transfer(
        fixture["source_state"], fixture["destination_state"]
    )
    return fixture


def _expected(vector, fixture):
    entry = fixture["stack"]
    frame = entry - 4
    initial = fixture["registers"]
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    events, insertions, heap_nodes = [], [], []
    registers = dict(initial)

    def raw(address, width=4):
        return sum(
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] << (8 * i)
            for i in range(width)
        )

    def read(address, width=4):
        value = raw(address, width)
        events.append(dict(access="read", address=address, width=width, value=value))
        return value

    def write(address, value, width=4):
        events.append(dict(access="write", address=address, width=width, value=value))
        for i, byte in enumerate(value.to_bytes(width, "little")):
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte

    write(frame, initial["ebp"])
    cookie = read(insertion.empty.COOKIE)
    write(frame - 4, cookie ^ frame)
    for offset, name in ((-24, "ebx"), (-28, "esi"), (-32, "edi")):
        write(frame + offset, initial[name])
    argument = read(frame + 8)
    _require(argument == ARGUMENT, "class argument differs")
    write(frame - 12, RECEIVER)
    _require(read(argument + 4) != 0, "nonzero source object required")
    source_object = read(argument + 4)
    head = read(source_object + 0x34)
    current = read(head)
    write(frame - 8, current)
    registers.update(
        eax=head,
        ebx=source_object,
        esi=current,
        edi=argument,
        ebp=frame,
        esp=frame - 32,
    )
    destination = fixture["destination_state"]["tree"]
    addresses = list(fixture["destination_addresses"])
    key_pointers = [raw(a + 16) for a in addresses]
    source_nodes = {}
    for address in [SOURCE_HEAD] + fixture["source_addresses"]:
        source_nodes[address] = dict(
            left=raw(address),
            parent=raw(address + 4),
            right=raw(address + 8),
            sentinel=raw(address + 13, 1),
        )
    while current != head:
        _require(
            len(insertions) < len(fixture["source_addresses"]),
            "class traversal exceeded source population",
        )
        source_id = fixture["source_addresses"].index(current)
        key = fixture["source_state"]["tree"]["nodes"][source_id]["key"]
        query_argument = current + 16
        query_pointer = raw(query_argument)
        output = frame - 20
        call_entry = frame - 44
        write(frame - 36, query_argument)
        write(frame - 40, output)
        write(call_entry, BASE + 0x2EB19F)
        keys = [node["key"] for node in destination["nodes"]]
        mode = _mode(keys, key)
        fresh = (
            construction.DATA + 0x100 + 32 * len(heap_nodes) + vector["node_alignment"]
        )
        cv = dict(
            nodes=[
                dict(
                    key=list(f'{node["key"]:08x}'.encode()),
                    left=node["left"],
                    right=node["right"],
                )
                for node in destination["nodes"]
            ],
            root=destination["root"],
            query=list(f"{key:08x}".encode()),
            frame_alignment=vector["frame_alignment"],
            nil_flag=vector["nil_flag"],
            seed=7,
            node_alignment=vector["node_alignment"],
        )
        iv = dict(vector, keys=keys, key=key, mode=mode)
        parent, cursor, selector = None, destination["root"], 0
        while cursor is not None:
            parent = cursor
            selector = int(key < destination["nodes"][cursor]["key"])
            cursor = destination["nodes"][cursor]["left" if selector else "right"]
        at = lambda i: leaf.HEAD if i is None else addresses[i]
        result = (
            None if mode == "existing" else insertion.model.insert(destination, key)
        )
        child = dict(
            fixture,
            stack=call_entry,
            output=output,
            query_argument=query_argument,
            query_pointer=query_pointer,
            node_addresses=list(addresses),
            key_pointers=list(key_pointers),
            addresses=list(addresses) + [fresh],
            node=fresh,
            return_address=BASE + 0x2EB19F,
            pages={p: bytes(v) for p, v in pages.items()},
            registers=dict(
                registers, eax=output, ecx=leaf.TREE, edi=leaf.TREE, esp=call_entry
            ),
            construction_vector=cv,
            tree=destination,
            result=result,
            parent=at(parent),
            selector=selector,
            relation=insertion.balancing.attachment.guard_spec(len(addresses)),
            strings=fixture["strings"],
        )
        returned = insertion._expected(iv, child)
        _require(
            returned["endpoint"] == BASE + 0x2EB19F
            and returned["registers"]["esp"] == frame - 32,
            "class insertion frame differs",
        )
        pages = {p: bytearray(v) for p, v in returned["pages"].items()}
        events.extend(returned["events"])
        registers = dict(returned["registers"])
        if returned["allocate"]:
            heap_nodes.append(fresh)
            addresses.append(fresh)
            key_pointers.append(query_pointer)
            destination = result["tree"]
        returned_node = read(output)
        payload = read(current + 20)
        write(returned_node + 20, payload)
        insertions.append(
            dict(
                source=source_id,
                key=key,
                destination_address=returned_node,
                inserted=returned["allocate"],
                mode=mode,
                payload=payload,
                heap_node=fresh if returned["allocate"] else None,
            )
        )
        write(frame - 36, BASE + 0x2EB1B0)
        memory = {
            address + i: raw(address + i, 1)
            for address in source_nodes
            for i in range(24)
        }
        for address in (frame - 8, frame - 36):
            for i in range(4):
                memory[address + i] = raw(address + i, 1)
        advanced = successor.oracle(
            dict(start=current),
            dict(
                memory=memory,
                nodes=source_nodes,
                slot=frame - 8,
                stack=frame - 36,
                registers=dict(
                    registers, eax=returned_node, ecx=frame - 8, esp=frame - 36
                ),
            ),
        )
        _require(
            advanced["endpoint"] == BASE + 0x2EB1B0
            and advanced["registers"]["esp"] == frame - 32,
            "class successor frame differs",
        )
        for address, value in advanced["memory"].items():
            pages[address & ~0xFFF][address & 0xFFF] = value
        events.extend(advanced["events"])
        registers = dict(advanced["registers"])
        current = read(frame - 8)
        _require(read(source_object + 0x34) == head, "source head changed")
        registers["esi"] = current
    if insertions:
        registers["edi"] = read(frame + 8)
    expected = dict(
        registers=registers,
        pages={p: bytes(v) for p, v in pages.items()},
        events=events,
        flags=0x44,
        endpoint=BASE + STOP,
        insertions=insertions,
        heap_nodes=heap_nodes,
        destination_addresses=addresses,
        destination_key_pointers=key_pointers,
    )
    _require(
        expected["pages"] == _model_pages(fixture, expected),
        "independent class transfer differs",
    )
    return expected


def _model_pages(fixture, expected):
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}
    result = fixture["transfer"]
    tree = result["destination"]["tree"]
    addresses = expected["destination_addresses"]
    at = lambda i: leaf.HEAD if i is None else addresses[i]

    def put(address, value, width=4):
        for i, byte in enumerate(value.to_bytes(width, "little")):
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte

    initial_count = len(fixture["destination_addresses"])
    expected_addresses = list(fixture["destination_addresses"])
    expected_keys = [
        int.from_bytes(
            fixture["pages"][a & ~0xFFF][(a & 0xFFF) + 16 : (a & 0xFFF) + 20], "little"
        )
        for a in expected_addresses
    ]
    for copy in result["copies"]:
        if copy["inserted"]:
            expected_addresses.append(
                construction.DATA
                + 0x100
                + 32 * (len(expected_addresses) - initial_count)
                + (fixture["node"] - construction.DATA - 0x100)
            )
            source = fixture["source_addresses"][copy["source"]]
            expected_keys.append(
                int.from_bytes(
                    fixture["pages"][source & ~0xFFF][
                        (source & 0xFFF) + 16 : (source & 0xFFF) + 20
                    ],
                    "little",
                )
            )
    _require(
        addresses == expected_addresses
        and expected["destination_key_pointers"] == expected_keys,
        "destination identity mapping differs",
    )
    for i, node in enumerate(tree["nodes"]):
        for offset, field in ((0, "left"), (4, "parent"), (8, "right")):
            put(at(i) + offset, at(node[field]))
        put(at(i) + 12, node["color"], 1)
        put(at(i) + 13, 0, 1)
        put(at(i) + 16, expected_keys[i])
        put(at(i) + 20, result["destination"]["payloads"][i])
    order = sorted(range(len(addresses)), key=lambda i: tree["nodes"][i]["key"])
    for offset, identity in (
        (0, order[0] if order else None),
        (4, tree["root"]),
        (8, order[-1] if order else None),
    ):
        put(leaf.HEAD + offset, at(identity))
    put(leaf.TREE + 4, len(addresses))
    for page in (construction.STACK, construction.STACK + 0x1000):
        pages[page] = bytearray(expected["pages"][page])
    frame = fixture["stack"] - 4
    put(frame - 8, SOURCE_HEAD)
    if result["copies"]:
        final = result["copies"][-1]
        put(frame - 20, at(final["destination"]))
        put(frame - 16, int(final["inserted"]), 1)
    return {p: bytes(v) for p, v in pages.items()}


def _run_case(codes, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    fixture = _fixture(vector)
    expected = _expected(vector, fixture)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    for page, payload in fixture["pages"].items():
        machine.mem_map(page, 0x1000)
        machine.mem_write(page, payload)
    code_pages = {
        (BASE + a + i) & ~0xFFF
        for a, payload in codes.items()
        for i in range(len(payload))
    }
    for page in sorted(code_pages):
        _require(page not in fixture["pages"], "class code overlaps data")
        machine.mem_map(page, 0x1000)
        machine.mem_write(page, b"\xcc" * 0x1000)
    for address, payload in codes.items():
        machine.mem_write(BASE + address, payload)
    machine.mem_map(construction.IMPORT, 0x1000)
    machine.mem_write(construction.IMPORT, b"\xcc")
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in fixture["registers"]}
    for register, value in fixture["registers"].items():
        machine.reg_write(ids[register], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(p["rva"], 16) for p in points}
    events, visited, allocations = [], [], []
    frame = fixture["stack"] - 4
    resume = None

    def on_code(m, address, size, user):
        nonlocal resume
        if address == construction.IMPORT:
            sp = m.reg_read(x.UC_X86_REG_ESP)
            words = [
                int.from_bytes(m.mem_read(sp + i * 4, 4), "little") for i in range(4)
            ]
            _require(
                len(allocations) < len(expected["heap_nodes"])
                and sp == frame - 140
                and words == [BASE + 0x389463, construction.HEAP, 0, 24],
                "class heap handoff differs",
            )
            node = expected["heap_nodes"][len(allocations)]
            for register, value in (
                (x.UC_X86_REG_EAX, node),
                (x.UC_X86_REG_ECX, 0xA0000001),
                (x.UC_X86_REG_EDX, 0xB0000001),
                (x.UC_X86_REG_EFLAGS, 0x246),
                (x.UC_X86_REG_ESP, sp + 16),
            ):
                m.reg_write(register, value)
            allocations.append(
                dict(node=node, entry_esp=sp, request=24, continuation=words[0])
            )
            resume = words[0]
            m.emu_stop()
            return
        if address == BASE + STOP:
            if negative == "iterator":
                m.mem_write(frame - 8, (SOURCE_HEAD ^ 1).to_bytes(4, "little"))
            if negative == "payload":
                last = expected["insertions"][-1]
                m.mem_write(
                    last["destination_address"] + 20,
                    (last["payload"] ^ 1).to_bytes(4, "little"),
                )
            m.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "class prefix escaped selected bodies")
        visited.append(f"0x{pc:08x}")
        if pc == START and negative in ("ancestor", "source"):
            at = fixture["stack"] + 8 if negative == "ancestor" else SOURCE_HEAD + 14
            m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))

    def on_memory(m, access, address, width, value, user):
        _require(width in (1, 2, 4), "unexpected class memory width")
        writing = access == uc.UC_MEM_WRITE
        events.append(
            dict(
                access="write" if writing else "read",
                address=address,
                width=width,
                value=(
                    value
                    if writing
                    else int.from_bytes(m.mem_read(address, width), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    next_pc = BASE + START
    for _ in range(len(expected["heap_nodes"]) + 1):
        resume = None
        machine.emu_start(next_pc, 0, count=50000)
        if resume is None:
            break
        next_pc = resume
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "class prefix endpoint differs",
    )
    _require(
        len(allocations) == len(expected["heap_nodes"]),
        "class allocation count differs",
    )
    actual = {r: machine.reg_read(i) for r, i in ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        actual == expected["registers"]
        and flags & 0x8D5 == expected["flags"]
        and not flags & 0x400,
        "class registers or flags differ",
    )
    _require(events == expected["events"], "class ordered events differ")
    _require(
        all(
            bytes(machine.mem_read(p, 0x1000)) == expected["pages"][p]
            for p in (construction.STACK, construction.STACK + 0x1000)
        ),
        "class ancestor memory differs",
    )
    _require(
        all(
            bytes(machine.mem_read(p, 0x1000)) == payload
            for p, payload in expected["pages"].items()
            if p not in (construction.STACK, construction.STACK + 0x1000)
        ),
        "class protected memory differs",
    )
    return dict(
        vector=vector,
        registers=actual,
        flags=flags & 0x8D5,
        trace_rvas=visited,
        insertions=expected["insertions"],
        allocations=allocations,
        events_sha256=_canonical_sha256(events),
        memory_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(v).hexdigest()
                for p, v in expected["pages"].items()
            }
        ),
    )


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "class source partition differs")
    return {
        key: _source_identity(sources[key], *pin, key)
        for key, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    owner = _decode_body(data, image, sources["program_facts"], START)
    _require(
        sum(r.size for r in owner) == 237
        and hashlib.sha256(b"".join(bytes(r.bytes) for r in owner)).hexdigest()
        == OWNER_SHA256,
        "class owner body differs",
    )
    prefix = [_point(r) for r in owner if r.address < BASE + STOP]
    for site, target in ((0x2EB19A, insertion.START), (0x2EB1AB, successor.START)):
        edges = [
            edge
            for edge in sources["class_chain"]["native_edges"]
            if edge["instruction"]["rva"] == f"0x{site:08x}"
        ]
        instruction = next(r for r in owner if r.address == BASE + site)
        _require(
            len(edges) == 1
            and edges[0]["source_entry_rva"] == f"0x{START:08x}"
            and edges[0]["target_entry_rva"] == f"0x{target:08x}"
            and edges[0]["instruction"] == _point(instruction)
            and instruction.mnemonic == "call"
            and instruction.operands[0].imm == BASE + target,
            "class child call edge differs",
        )
    witnesses = {p["rva"]: p for p in prefix}
    ranges = [(START, STOP), (successor.START, successor.END)]
    for p in sources["successor"]["body"]["points"]:
        witnesses[p["rva"]] = p
    body = sources["insertion_return"]["body"]
    ranges.extend(
        (int(span["start_rva"], 16), int(span["end_rva"], 16))
        for span in body["ranges"]
    )
    for p in body["points"]:
        _require(
            p["rva"] not in witnesses or witnesses[p["rva"]] == p,
            "class child witness overlap differs",
        )
        witnesses[p["rva"]] = p
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    codes, points = {}, []
    for a, b in sorted(ranges):
        offset = image.rva_to_file_offset(a)
        payload = data[offset : offset + b - a]
        part = [_point(r) for r in decoder.disasm(payload, BASE + a)]
        _require(
            sum(p["size"] for p in part) == b - a
            and all(witnesses.get(p["rva"]) == p for p in part),
            "class selected code differs",
        )
        codes[a] = payload
        points.extend(part)
    return codes, points, prefix


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE,
        "exact class executable differs",
    )
    codes, points, prefix = _load_code(data, image, sources)
    observations = [_run_case(codes, points, vector) for vector in vectors()]
    union = sorted(
        {pc for observation in observations for pc in observation["trace_rvas"]}
    )
    normal = {p["rva"] for p in prefix if not 0x2EB15F <= int(p["rva"], 16) < 0x2EB179}
    _require(
        normal <= set(union)
        and not any(0x2EB15F <= int(pc, 16) < 0x2EB179 for pc in union),
        "class normal prefix coverage differs",
    )
    controls = []
    sample = next(
        vector
        for vector in vectors()
        if vector["source_keys"] and vector["profile"] == "all_new"
    )
    for kind, message in (
        ("ancestor", "class ancestor memory differs"),
        ("source", "class protected memory differs"),
        ("payload", "class protected memory differs"),
        ("iterator", "class ancestor memory differs"),
    ):
        try:
            _run_case(codes, points, sample, kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "class mutation failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("class mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(start_rva=f"0x{a:08x}", end_rva=f"0x{a+len(payload):08x}")
                for a, payload in codes.items()
            ],
            points=points,
            prefix_points=prefix,
        ),
        vectors=vectors(),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        executed_rvas=union,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            prefix_bytes=STOP - START,
            prefix_sites=len(prefix),
            normal_prefix_sites=len(normal),
            instruction_bytes=sum(map(len, codes.values())),
            static_sites=len(points),
            executed_sites=len(union),
            iterations=sum(len(o["insertions"]) for o in observations),
            allocated_insertions=sum(len(o["allocations"]) for o in observations),
            existing_insertions=sum(
                sum(not i["inserted"] for i in o["insertions"]) for o in observations
            ),
            max_iterations=max(len(o["insertions"]) for o in observations),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Native class tree-copy prefix through complete insertion and successor calls on a finite disjoint canonical corpus",
            premises=[
                "Nonzero argument second word names a source object with stable source tree and fixed-width hexadecimal keys",
                "At most seven source and seven initial destination nodes, source payload DWORD copied even on existing insertion",
                "Each fresh node uses one supplied successful HeapAlloc response; every descendant instruction otherwise native and DF clear",
                "Independent class transfer model checks destination topology keys and payloads, source storage and final iterator and result pair",
            ],
            not_claimed=[
                "Assertion failure, aliased source and destination trees, vector append or whole class owner return",
                "Heap implementation, failed allocation, exception delivery, arbitrary strings, hardware execution or accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "class executable changed",
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
        "sealed class prefix differs",
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
        "exact class prefix differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
