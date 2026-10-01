"""Actual factory receiver through native callback and first-null class return."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from src.observatory import native_lua_class_factory_callback_entry_conformance as entry
from src.observatory import native_lua_class_factory_receiver_alignment as alignment
from src.observatory import native_lua_class_empty_vector_return_conformance as empty
from src.observatory import (
    native_lua_class_factory_callback_empty_class_semantics as model,
)

full, factory, callback, layout = (
    entry.full,
    entry.factory,
    entry.callback,
    entry.layout,
)
BASE, ConformanceError, _require = entry.BASE, entry.ConformanceError, entry._require
_canonical_sha256, _canonical_bytes = entry._canonical_sha256, entry._canonical_bytes
ANALYSIS_KIND = "pe_native_lua_class_factory_callback_empty_class_conformance"
SEALED_SHA256 = "09117544ab5c8c4366aec36ee3bd295263157cdbd22455b1a1597d6eaf73851a"
ENDPOINT = BASE + 0x2EC1BD
SOURCE_PINS = {
    **entry.SOURCE_PINS,
    **empty.SOURCE_PINS,
    "factory_callback_entry": (entry.ANALYSIS_KIND, entry.SEALED_SHA256),
    "class_empty": (empty.ANALYSIS_KIND, empty.SEALED_SHA256),
}
# Straight empty-source, first-null growth and successful cookie-return paths.
# Each selected site is independently byte-pinned by the source witnesses.
NORMAL_CLASS_RANGES = (
    (0x8A920, 0x8A92A),
    (0x8A932, 0x8A943),
    (0x8A962, 0x8A971),
    (0x2EB140, 0x2EB15F),
    (0x2EB179, 0x2EB188),
    (0x2EB1BB, 0x2EB1C5),
    (0x2EB1F7, 0x2EB22D),
    (0x2EB620, 0x2EB674),
    (0x2EB680, 0x2EB6B7),
    (0x2EB6CB, 0x2EB6E5),
    (0x3574CA, 0x3574D5),
    (0x3574DB, 0x3574E0),
    (0x3574FF, 0x35750E),
    (0x36E580, 0x36E5A9),
    (0x36EA7B, 0x36EA80),
    (0x36EAB0, 0x36EAB7),
    (0x379F52, 0x379F5D),
    (0x38942B, 0x38943D),
    (0x389454, 0x389469),
    (0x389476, 0x389479),
)


def vectors():
    return [
        dict(v, vector_alignment=a) for v in alignment.vectors() for a in (0, 7, 31)
    ]


def _producer_vector(vector):
    return {k: v for k, v in vector.items() if k != "vector_alignment"}


def _produce(payload, points, continuation, vector):
    vector = _producer_vector(vector)
    base = full.record._base_vector(full._record_vector(vector))
    captured = {}

    def capture(machine, negative, fixture, expected, lua, ids):
        captured.update(
            fixture=fixture,
            pages={p: bytes(machine.mem_read(p, 4096)) for p in fixture["pages"]},
            closure=lua.stack[-1],
            lua_result=lua.result(),
            registers={r: machine.reg_read(i) for r, i in ids.items()},
        )

    installed = dict(
        continuation,
        extend_fixture=lambda v, p: alignment.install(vector, p),
        lua_observer=lambda v, p: full._Lua(base, p),
        endpoint_mutation=capture,
    )
    observation = factory._run_case(payload, points, base, continuation=installed)
    _require(
        captured["closure"]
        == ("closure", BASE + callback.START, ("userdata", alignment.USERDATA)),
        "aligned factory returned closure differs",
    )
    return captured, observation


def _class_vector(vector, pages):
    return dict(
        profile="empty_source",
        source_keys=[],
        destination_keys=[],
        node_alignment=0,
        frame_alignment=15 * vector["profile"],
        nil_flag=1,
        previous_seh=0,
        cookie=factory._raw(pages, factory.COOKIE),
        payload_seed=0x75310000,
        vector_alignment=vector["vector_alignment"],
    )


def _resume(produced, vector):
    # Reuse the reviewed byte-scoped API binder with the supplied host frame.
    # No generated child page replaces any native producer page.
    t = factory.STACK + 0x1030 + 15 * vector["profile"]
    old = entry._resume(produced, vector, callback_entry=t)
    pages = {p: bytearray(b) for p, b in old["pages"].items()}
    patches = list(old["patches"])

    def put(address, value, width=4):
        for i, byte in enumerate(value.to_bytes(width, "little")):
            a = address + i
            p, off = a & ~4095, a & 4095
            pages.setdefault(p, bytearray(b"\xa5" * 4096))
            patches.append(dict(address=a, before=pages[p][off], after=byte))
            pages[p][off] = byte

    a, h = empty.prefix.SOURCE_OBJECT, empty.SOURCE_HEAD
    put(a + 52, h)
    for offset in (0, 4, 8):
        put(h + offset, h)
    put(h + 12, 1, 1)
    put(h + 13, 1, 1)
    fresh_pages = []
    for i in range(4):
        p = empty.construction.DATA + 4096 * i
        _require(p not in pages, "class construction storage overlaps factory pages")
        pages[p] = bytearray(b"\xa5" * 4096)
        fresh_pages.append(p)
    frozen = {p: bytes(b) for p, b in pages.items()}
    for start, size in ((alignment.USERDATA, 72), (alignment.RECORD, 24)):
        _require(
            all(
                factory._raw(frozen, start + i, 1)
                == factory._raw(produced["pages"], start + i, 1)
                for i in range(size)
            ),
            "class host boundary changed factory storage",
        )
    return dict(
        old,
        entry=t,
        registers=dict(produced["registers"], esp=t),
        source_pointer=a,
        pages=frozen,
        endpoint=ENDPOINT,
        patches=patches,
        fresh_pages=fresh_pages,
        vector_begin=empty.construction.DATA + 0x2000 + vector["vector_alignment"],
    )


def _logical(fixture, produced, vector):
    return model.apply(
        state=fixture["state"],
        userdata=fixture["receiver"],
        record_pointer=produced["fixture"]["record"],
        source_pointer=fixture["source_pointer"],
        callback_entry=fixture["entry"],
        registers=fixture["registers"],
        closure_target=produced["closure"][1],
        closure_upvalues=[produced["closure"][2][1]],
        upvalue_has_metatable=True,
        argument_has_metatable=True,
        upvalue_marker_kind="zero",
        argument_marker_kind="table",
        vector_pointer=fixture["vector_begin"],
        cookie=factory._raw(fixture["pages"], factory.COOKIE),
    )


def _joined_expected(prefix, fixture, vector):
    cv = _class_vector(vector, fixture["pages"])
    prototype = empty._fixture(cv)
    child_fixture = dict(
        prototype,
        pages=prefix["pages"],
        registers=prefix["registers"],
        stack=fixture["entry"] - 48,
        return_address=ENDPOINT,
    )
    child = empty._expected(cv, child_fixture)
    _require(child["tree_heap_count"] == 0, "empty source unexpectedly inserts")
    return dict(
        prefix,
        prefix=prefix,
        child_fixture=child_fixture,
        child=child,
        events=prefix["events"] + child["events"],
        pages=child["pages"],
        registers=child["registers"],
        flags=child["flags"],
    )


def _run_case(codes, points, fixture, produced, vector, negative=None):
    from unicorn import x86_const as x

    logical = _logical(fixture, produced, vector)
    allocations = []
    class_entries = []

    def before(m, address, ids, expected, prefix_logical, negative):
        regs = lambda: {r: m.reg_read(i) for r, i in ids.items()}
        words = lambda a, n: [
            int.from_bytes(m.mem_read(a + i * 4, 4), "little") for i in range(n)
        ]
        if address == BASE + empty.START:
            if negative == "class_entry_flags":
                m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 0x10)
            caller = logical["class_caller"]
            _require(
                not class_entries
                and regs() == caller["registers"]
                and m.reg_read(x.UC_X86_REG_EFLAGS) & 0xCD5
                == expected["prefix"]["flags"]
                and words(regs()["esp"], 2)
                == [caller["return_address"], caller["argaddress"]]
                and words(caller["argaddress"], 2) == caller["argument_record"]
                and all(
                    bytes(m.mem_read(p, 4096)) == b
                    for p, b in expected["prefix"]["pages"].items()
                ),
                "factory callback class entry differs",
            )
            class_entries.append(address)
        if address == layout.IMPORT:
            sp = m.reg_read(ids["esp"])
            if negative == "heap_request":
                m.mem_write(sp + 12, (9).to_bytes(4, "little"))
            if negative == "heap_register":
                m.reg_write(ids["edx"], 0)
            if negative == "heap_flags":
                m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 1)
            _require(
                not allocations
                and sp == fixture["entry"] - 188
                and words(sp, 4) == [0x789463, 0x12345678, 0, 8],
                "factory callback heap request differs",
            )
            _require(
                regs()
                == dict(
                    eax=8,
                    ebx=0x1FFFFFFF,
                    ecx=alignment.USERDATA + 4,
                    edx=1,
                    esi=8,
                    edi=0,
                    ebp=fixture["entry"] - 168,
                    esp=sp,
                )
                and m.reg_read(x.UC_X86_REG_EFLAGS) & 0xCC5 == 0,
                "factory callback heap ABI differs",
            )
            pointer = fixture["vector_begin"] + int(negative == "heap_response")
            for r, value in dict(
                eax=pointer, ecx=0xA0000001, edx=0xB0000001, esp=sp + 16
            ).items():
                m.reg_write(ids[r], value)
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            allocations.append(dict(pointer=pointer, entry_esp=sp, bytes=8))
            return True, 0x789463
        if address == ENDPOINT:
            corrupt = {
                "source": empty.SOURCE_HEAD + 14,
                "record_padding": alignment.RECORD + 23,
                "vector": fixture["vector_begin"],
                "capacity": alignment.USERDATA + 12,
                "cookie": factory.COOKIE,
                "context": alignment.USERDATA + 48,
            }
            if negative in corrupt:
                a = corrupt[negative]
                m.mem_write(a, bytes([m.mem_read(a, 1)[0] ^ 1]))
        return False, None

    def verify_return(machine, ids, prefix_logical, expected):
        _require(
            len(allocations) == len(class_entries) == 1,
            "factory callback allocation count differs",
        )
        final = logical["class_return"]
        _require(
            {r: machine.reg_read(i) for r, i in ids.items()} == final["registers"]
            and expected["flags"] == final["flags"]
            and all(
                int.from_bytes(
                    machine.mem_read(alignment.USERDATA + offset, 4), "little"
                )
                == value
                for offset, value in logical["field_updates"].items()
            )
            and bytes(machine.mem_read(fixture["vector_begin"], 8))
            == b"\0" * 4 + fixture["source_pointer"].to_bytes(4, "little"),
            "factory callback independent class return differs",
        )

    observation = entry._run_prefix(
        codes,
        points,
        fixture,
        produced,
        vector,
        negative,
        continuation=dict(
            endpoint=ENDPOINT,
            extend_expected=lambda p: _joined_expected(p, fixture, vector),
            before_instruction=before,
            verify_return=verify_return,
            extra_responses=1,
        ),
    )
    return dict(observation, allocations=allocations, class_entries=len(class_entries))


def _load_code(data, image, sources):
    payload, fp, continuation, codes, points = entry._load_code(data, image, sources)
    child_codes, child_points, selected = empty._load_code(data, image, sources)
    joined = dict(codes)
    witnesses = {p["rva"]: p for p in points}
    for a, b in child_codes.items():
        _require(
            all(a + len(b) <= c or c + len(d) <= a for c, d in joined.items()),
            "factory callback code ranges overlap",
        )
        joined[a] = b
    for p in child_points:
        _require(
            p["rva"] not in witnesses or witnesses[p["rva"]] == p,
            "factory callback witness conflict",
        )
        witnesses[p["rva"]] = p
    return (
        payload,
        fp,
        continuation,
        joined,
        sorted(witnesses.values(), key=lambda p: p["rva"]),
    )


def _preflight(sources):
    _require(
        set(sources) == set(SOURCE_PINS), "factory empty-class source partition differs"
    )
    return {
        k: factory._source_identity(sources[k], *pin, k)
        for k, pin in SOURCE_PINS.items()
    }


CONTROLS = {
    **entry.CONTROLS,
    **{
        k: "callback entry protected pages differ"
        for k in ("source", "record_padding", "vector", "capacity", "cookie", "context")
    },
    "heap_request": "factory callback heap request differs",
    "heap_register": "factory callback heap ABI differs",
    "heap_flags": "factory callback heap ABI differs",
    "class_entry_flags": "factory callback class entry differs",
    "heap_response": "callback entry ordered events differ",
}


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = full._load_executable(Path(executable))
    _require(
        digest == full.EXE_SHA256 and image.image_base == BASE,
        "exact factory empty-class executable differs",
    )
    payload, fp, continuation, codes, points = _load_code(data, image, sources)
    observations, producer = [], []
    sample = None
    for vector in vectors():
        produced, observation = _produce(payload, fp, continuation, vector)
        fixture = _resume(produced, vector)
        observations.append(_run_case(codes, points, fixture, produced, vector))
        producer.append(observation)
        if sample is None:
            sample = (produced, fixture, vector)
    controls = []
    for kind, reason in CONTROLS.items():
        try:
            _run_case(codes, points, sample[1], sample[0], sample[2], kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "factory empty-class incidental control: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("factory empty-class control survived: " + kind)
    union = sorted({r for o in observations for r in o["trace_rvas"]})
    prefix_sites = set(sources["factory_callback_entry"]["executed_rvas"])
    class_sites = {
        p["rva"]
        for p in points
        if any(a <= int(p["rva"], 16) < b for a, b in NORMAL_CLASS_RANGES)
    }
    _require(
        len(prefix_sites) == 67
        and len(class_sites) == 194
        and not prefix_sites & class_sites
        and set(union) == prefix_sites | class_sites,
        "factory empty-class normal site partition differs",
    )
    _require(
        len(observations) == 54
        and all(len(o["trace_rvas"]) == 288 for o in observations)
        and f"0x{ENDPOINT-BASE:08x}" not in union,
        "factory empty-class coverage differs",
    )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{a:08x}",
                    end_rva=f"0x{a+len(b):08x}",
                    sha256=hashlib.sha256(b).hexdigest(),
                )
                for a, b in sorted(codes.items())
            ],
            points=points,
        ),
        vectors=vectors(),
        normal_site_partition=dict(
            callback_and_markers=sorted(prefix_sites),
            empty_class=sorted(class_sites),
            excluded=sorted({p["rva"] for p in points} - set(union)),
        ),
        executed_rvas=union,
        negative_controls=controls,
        observations_sha256=_canonical_sha256(observations),
        producer_observations_sha256=_canonical_sha256(producer),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=54,
            static_sites=len(points),
            executed_sites=len(union),
            instruction_bytes=sum(map(len, codes.values())),
            factory_instructions=sum(len(o["trace_rvas"]) for o in producer),
            callback_and_class_instructions=54 * 288,
            factory_api_calls=54 * 34,
            callback_api_calls=54 * 12,
            factory_heap_calls=54,
            class_heap_calls=54,
            class_heap_bytes=54 * 8,
            marker_calls=54 * 2,
            tree_insertions=0,
            free_calls=0,
            controls=len(controls),
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            continuous_factory=True,
            continuous_callback_markers_and_class=True,
            continuous_across_host=False,
            checked=[
                "Actual aligned factory receiver and allocated sentinel retained",
                "Native callback original local pair reaches class and first-null allocation",
                "Twelve Lua requests ordered data events all pages GPRs and defined flags",
                "Class normal RET4 reaches suspended callback with one appended pair",
            ],
            premises=[
                "Explicit supplied host closure invocation and empty source bytes",
                "Byte scoped API literals frame and existing source page reuse",
                "Successful eight byte heap response and compatible truthy markers",
            ],
            excluded=[
                "Lua VM invocation metatable registry and callback suffix effects",
                "Nonempty source tree insertion key reads and successor traversal",
                "Heap ownership assertion delivery and global accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory empty-class executable changed",
    )
    entry._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    entry._validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors(),
        "sealed factory empty-class differs",
    )
    entry._assert_publication_safe(evidence)
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
        "exact factory empty-class differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


encode_conformance = entry.encode_conformance
