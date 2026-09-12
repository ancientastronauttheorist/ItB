"""Whole native class return with order-preserving variable-length byte keys."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_lua_class_tree_conformance as prefix
from src.observatory import (
    native_lua_class_internal_growth_return_conformance as joined,
)
from src.observatory import native_lua_class_vector_return_conformance as returned
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _load_executable,
    _point,
    _source_identity,
    _canonical_bytes,
    _canonical_sha256,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "pe_native_lua_class_byte_key_return_conformance"
SEALED_SHA256 = "cf3cadf46b1a06a4744ccd276ca2c7551a9d1010370cb7e6f24c52ed0b7020f4"
SOURCE_PINS = {
    "program_facts": prefix.SOURCE_PINS["program_facts"],
    "internal_growth_return": (joined.ANALYSIS_KIND, joined.SEALED_SHA256),
    "class_prefix": (prefix.ANALYSIS_KIND, prefix.SEALED_SHA256),
}
START = prefix.START
RECEIVER, ARGUMENT, SOURCE_HEAD = prefix.RECEIVER, prefix.ARGUMENT, prefix.SOURCE_HEAD
construction = prefix.construction
ConformanceError, _require = prefix.ConformanceError, prefix._require
PROFILES = ("prefixes", "unsigned_boundary", "long_common_prefix")


def vectors():
    return [
        dict(
            v,
            old_size=3,
            argument_index=index,
            vector_alignment=(0, 31)[(i + index) % 2],
            key_profile=profile,
        )
        for i, v in enumerate(prefix.vectors())
        for index in (0, 2)
        for profile in PROFILES
    ]


def encoded_keys(vector):
    profile = vector["key_profile"]
    _require(profile in PROFILES, "invalid class byte-key profile")
    keys = sorted(set(vector["source_keys"] + vector["destination_keys"]))
    _require(len(keys) <= 14, "class byte-key rank corpus exceeded")
    encode = {
        "prefixes": lambda rank: b"a" * rank,
        "unsigned_boundary": lambda rank: bytes([0x78 + rank]),
        "long_common_prefix": lambda rank: b"Q" * 63 + bytes([rank + 1]),
    }[profile]
    return {key: encode(rank) for rank, key in enumerate(keys)}


def _fixture(vector):
    fixture = joined._fixture(vector)
    mapping = encoded_keys(vector)
    fixture["key_bytes"] = mapping
    prefix._checked_key_bytes(fixture)
    pages = {p: bytearray(v) for p, v in fixture["pages"].items()}

    def put(a, value, width=4):
        for i, b in enumerate(value.to_bytes(width, "little")):
            pages[(a + i) & ~0xFFF][(a + i) & 0xFFF] = b

    strings = {}
    for i, node in enumerate(fixture["destination_state"]["tree"]["nodes"]):
        strings[prefix.leaf.KEYS + 256 * i] = mapping[node["key"]] + b"\0"
    for i, node in enumerate(fixture["source_state"]["tree"]["nodes"]):
        address = prefix.SOURCE_KEYS + 128 * i
        strings[address] = mapping[node["key"]] + b"\0"
        put(fixture["source_addresses"][i] + 16, address)
    # Keep unrelated initial query storage represented, although owner calls use source-node key fields.
    strings[prefix.leaf.QUERY] = fixture["strings"][prefix.leaf.QUERY]
    for address, payload in strings.items():
        for i, b in enumerate(payload):
            a = address + i
            _require(a & ~0xFFF in pages, "class byte string outside mapped storage")
            pages[a & ~0xFFF][a & 0xFFF] = b
    fixture.update(pages={p: bytes(v) for p, v in pages.items()}, strings=strings)
    return fixture


def _expected(vector, fixture):
    return joined._expected(vector, fixture)


def _model_pages(fixture, expected):
    return joined._model_pages(fixture, expected)


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
    endpoint_page = expected["endpoint"] & ~0xFFF
    _require(
        endpoint_page not in code_pages and endpoint_page not in fixture["pages"],
        "return endpoint overlaps mapping",
    )
    machine.mem_map(endpoint_page, 0x1000)
    machine.mem_write(endpoint_page, b"\xcc" * 0x1000)
    machine.mem_map(construction.IMPORT, 0x1000)
    machine.mem_write(construction.IMPORT, b"\xcc")
    ids = {r: getattr(x, "UC_X86_REG_" + r.upper()) for r in fixture["registers"]}
    for register, value in fixture["registers"].items():
        machine.reg_write(ids[register], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(p["rva"], 16) for p in points}
    events, visited, allocations, frees = [], [], [], []
    frame = fixture["stack"] - 4
    resume = None

    def on_code(m, address, size, user):
        nonlocal resume
        if address == construction.IMPORT:
            sp = m.reg_read(x.UC_X86_REG_ESP)
            api_return = int.from_bytes(m.mem_read(sp, 4), "little")
            if api_return == BASE + 0x389172:
                if negative == "heap_free_request":
                    m.mem_write(
                        sp + 12, (fixture["old_begin"] ^ 1).to_bytes(4, "little")
                    )
                words = [
                    int.from_bytes(m.mem_read(sp + i * 4, 4), "little")
                    for i in range(4)
                ]
                _require(
                    len(frees) == 0
                    and len(allocations) == len(expected["heap_nodes"])
                    and sp == frame - 128
                    and words
                    == [BASE + 0x389172, construction.HEAP, 0, fixture["old_begin"]],
                    "class free handoff differs",
                )
                for register, value in (
                    (x.UC_X86_REG_EAX, 1),
                    (x.UC_X86_REG_ECX, 0xA0000001),
                    (x.UC_X86_REG_EDX, 0xB0000001),
                    (x.UC_X86_REG_EFLAGS, 0x2D7),
                    (x.UC_X86_REG_ESP, sp + 16),
                ):
                    m.reg_write(register, value)
                frees.append(
                    dict(
                        pointer=words[3], entry_esp=sp, result=1, continuation=words[0]
                    )
                )
                resume = words[0]
                m.emu_stop()
                return
            if (
                negative == "heap_request"
                and len(allocations) == expected["tree_heap_count"]
            ):
                m.mem_write(sp + 12, (9).to_bytes(4, "little"))
            words = [
                int.from_bytes(m.mem_read(sp + i * 4, 4), "little") for i in range(4)
            ]
            tree_allocation = len(allocations) < expected["tree_heap_count"]
            request = 24 if tree_allocation else 8 * (vector["old_size"] + 1)
            _require(
                len(allocations) < len(expected["heap_nodes"])
                and sp == frame - (140 if tree_allocation else 136)
                and words == [BASE + 0x389463, construction.HEAP, 0, request],
                "class heap handoff differs",
            )
            node = expected["heap_nodes"][len(allocations)]
            if negative == "heap_response" and not tree_allocation:
                node ^= 1
            for register, value in (
                (x.UC_X86_REG_EAX, node),
                (x.UC_X86_REG_ECX, 0xA0000001),
                (x.UC_X86_REG_EDX, 0xB0000001),
                (x.UC_X86_REG_EFLAGS, 0x246),
                (x.UC_X86_REG_ESP, sp + 16),
            ):
                m.reg_write(register, value)
            allocations.append(
                dict(node=node, entry_esp=sp, request=request, continuation=words[0])
            )
            resume = words[0]
            m.emu_stop()
            return
        if address == BASE + 0x3574D5 and negative == "cookie":
            m.emu_stop()
            return
        if address == BASE + 0x2EB222 and negative == "cookie":
            m.mem_write(returned.COOKIE, (vector["cookie"] ^ 1).to_bytes(4, "little"))
        if address == expected["endpoint"]:
            if negative == "iterator":
                m.mem_write(frame - 8, (SOURCE_HEAD ^ 1).to_bytes(4, "little"))
            if negative == "payload":
                last = expected["insertions"][-1]
                m.mem_write(
                    last["destination_address"] + 20,
                    (last["payload"] ^ 1).to_bytes(4, "little"),
                )
            if negative == "old":
                at = fixture["old_begin"]
                m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))
            if negative == "vector":
                at = fixture["vector_end"]
                m.mem_write(at, bytes([m.mem_read(at, 1)[0] ^ 1]))
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
    for _ in range(len(expected["heap_nodes"]) + 2):
        resume = None
        machine.emu_start(next_pc, 0, count=50000)
        if resume is None:
            break
        next_pc = resume
    if negative == "cookie":
        _require(
            machine.reg_read(x.UC_X86_REG_EIP) == BASE + 0x3574D5
            and machine.reg_read(x.UC_X86_REG_ESP) == frame - 24,
            "class cookie failure frontier differs",
        )
        _require(
            events
            == expected["events"][: -3 - 1]
            + [
                dict(
                    access="read",
                    address=returned.COOKIE,
                    width=4,
                    value=vector["cookie"] ^ 1,
                )
            ],
            "class cookie prefix events differ",
        )
        failure_regs = dict(expected["registers"], ebp=frame, esp=frame - 24)
        failure_flags = returned.return_spec(
            frame, vector["cookie"], vector["cookie"] ^ 1
        )["flags"]
        _require(
            {r: machine.reg_read(i) for r, i in ids.items()} == failure_regs
            and machine.reg_read(x.UC_X86_REG_EFLAGS) & 0x8D5 == failure_flags
            and not machine.reg_read(x.UC_X86_REG_EFLAGS) & 0x400,
            "class cookie failure ABI differs",
        )
        failure_pages = {p: bytearray(v) for p, v in expected["pages"].items()}
        for i, b in enumerate((vector["cookie"] ^ 1).to_bytes(4, "little")):
            at = returned.COOKIE + i
            failure_pages[at & ~0xFFF][at & 0xFFF] = b
        _require(
            all(
                bytes(machine.mem_read(p, 4096)) == bytes(v)
                for p, v in failure_pages.items()
            ),
            "class cookie failure memory differs",
        )
        return dict(kind="cookie", rejected=True, endpoint="0x003574d5")
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "class prefix endpoint differs",
    )
    _require(
        len(allocations) == len(expected["heap_nodes"]) and len(frees) == 1,
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
        frees=frees,
        events_sha256=_canonical_sha256(events),
        memory_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(v).hexdigest()
                for p, v in expected["pages"].items()
            }
        ),
    )


def _preflight(sources):
    _require(
        set(sources) == set(SOURCE_PINS), "class byte-key source partition differs"
    )
    return {
        key: _source_identity(sources[key], *pin, key)
        for key, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    body = sources["internal_growth_return"]["body"]
    witnesses = {p["rva"]: p for p in body["points"]}
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    codes, points = {}, []
    for span in body["ranges"]:
        a, b = (int(span[k], 16) for k in ("start_rva", "end_rva"))
        offset = image.rva_to_file_offset(a)
        payload = data[offset : offset + b - a]
        part = [_point(r) for r in decoder.disasm(payload, BASE + a)]
        _require(
            sum(p["size"] for p in part) == b - a
            and all(witnesses.get(p["rva"]) == p for p in part),
            "class byte-key selected code differs",
        )
        codes[a] = payload
        points.extend(part)
    return codes, points


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE,
        "class byte-key exact PE differs",
    )
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({p for o in observations for p in o["trace_rvas"]})
    required = {
        p
        for p in sources["internal_growth_return"]["executed_rvas"]
        if START <= int(p, 16) < 0x2EB22D
    }
    _require(required <= set(union), "class byte-key whole owner coverage differs")
    controls = []
    sample = next(
        v
        for v in vectors()
        if v["profile"] == "all_new"
        and v["source_keys"]
        and v["key_profile"] == "long_common_prefix"
    )
    for kind, message in (
        ("ancestor", "class ancestor memory differs"),
        ("source", "class protected memory differs"),
        ("payload", "class protected memory differs"),
        ("vector", "class protected memory differs"),
        ("iterator", "class ancestor memory differs"),
        ("heap_request", "class heap handoff differs"),
        ("heap_response", "class registers or flags differ"),
        ("old", "class protected memory differs"),
        ("heap_free_request", "class free handoff differs"),
    ):
        try:
            _run_case(codes, points, sample, kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "class byte-key mutation failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("class byte-key mutation survived")
    controls.append(_run_case(codes, points, sample, "cookie"))
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(start_rva=f"0x{a:08x}", end_rva=f"0x{a+len(v):08x}")
                for a, v in codes.items()
            ],
            points=points,
        ),
        vectors=vectors(),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        executed_rvas=union,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            instruction_bytes=sum(map(len, codes.values())),
            static_sites=len(points),
            executed_sites=len(union),
            iterations=sum(len(o["insertions"]) for o in observations),
            allocated_insertions=sum(len(o["allocations"]) - 1 for o in observations),
            existing_insertions=sum(
                sum(not i["inserted"] for i in o["insertions"]) for o in observations
            ),
            vector_allocations=len(observations),
            free_requests=sum(len(o["frees"]) for o in observations),
            grown_vector_records=4 * len(observations),
            max_iterations=max(len(o["insertions"]) for o in observations),
            key_profiles={
                profile: sum(v["key_profile"] == profile for v in vectors())
                for profile in PROFILES
            },
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Whole native class transfer and internal-argument vector growth return on a finite variable byte-key corpus",
            premises=[
                "At most seven source and seven destination nodes; checked strictly order-preserving bytes encode each canonical numeric key",
                "Keys include empty prefixes, unsigned boundary bytes and64-byte common-prefix records, with no embedded NUL and complete mapped string pages",
                "Three old vector records surround the argument in source storage, argument index zero or two; scalar copy and selected record read use new storage after successful free",
                "Every descendant instruction executes natively except supplied successful HeapAlloc and HeapFree responses; full protected memory, ordered events and caller ABI checked",
            ],
            not_claimed=[
                "All byte strings or trees, allocation or deallocation failure, assertion, exceptions, hardware execution or accounting promotion"
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "class byte-key executable changed",
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
        "sealed class byte-key return differs",
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
        "exact class byte-key return differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
