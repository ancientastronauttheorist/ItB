"""Mixed second-source keys on retained actual factory receiver state."""

from __future__ import annotations
import copy
import hashlib
from pathlib import Path
from src.observatory import native_lua_class_factory_callback_tree_conformance as tree
from src.observatory import native_lua_class_old_vector_return_conformance as old
from src.observatory import native_lua_class_factory_callback_extend_semantics as model

from src.observatory import (
    native_lua_class_factory_callback_repeat_conformance as repeat,
)

normal, full, factory, callback = tree.normal, tree.full, tree.factory, tree.callback
BASE, ConformanceError, _require = tree.BASE, tree.ConformanceError, tree._require
_canonical_sha256, _canonical_bytes = tree._canonical_sha256, tree._canonical_bytes
ANALYSIS_KIND = "pe_native_lua_class_factory_callback_extend_conformance"
SEALED_SHA256 = "c0cc89b3af1cecb03d752cf7e17fde6c621631bcbb43046475124609bd589797"
SOURCE_PINS = {
    **repeat.SOURCE_PINS,
    "factory_callback_repeat": (repeat.ANALYSIS_KIND, repeat.SEALED_SHA256),
}
FIRST_KEYS = ((0, 1, 16), (1, 16, 255))
SECOND_KEYS = (
    ((7,), (255,), (0, 7, 255), (0, 1, 7, 17, 255, 0x80000000, 0xFFFFFFFF)),
    (
        (7,),
        (0,),
        (0, 1, 7, 255, 0x80000000),
        (0, 1, 7, 17, 255, 0x80000000, 0xFFFFFFFF),
    ),
)
SECOND_KEY_STORAGE = 0x1D000FFF


def vectors():
    return [
        dict(v, first_key_profile=f, source_profile=s)
        for v in repeat.vectors()
        if v["source_size"] == 3
        for f in (0, 1)
        for s in range(4)
    ]


def _base_vector(vector):
    return {
        k: v
        for k, v in vector.items()
        if k not in ("first_key_profile", "source_profile")
    }


def _produce_first(payload, fp, continuation, codes, points, vector):
    base = _base_vector(vector)
    produced, producer = normal.first._produce(
        payload, fp, continuation, normal._first_vector(tree._normal_vector(base))
    )
    fixture = _resume_first(produced, vector)
    captured = {}

    def capture(machine, ids, expected, lua):
        captured.update(
            pages={p: bytes(machine.mem_read(p, 4096)) for p in fixture["pages"]},
            registers={r: machine.reg_read(i) for r, i in ids.items()},
        )

    observation = tree._run_case(
        codes, points, fixture, produced, base, capture=capture
    )
    captured["observation"] = observation
    return produced, producer, fixture, captured


def _rekey_first(fixture):
    fixture = copy.deepcopy(fixture)
    pages = {p: bytearray(b) for p, b in fixture["pages"].items()}
    remap = dict(zip(FIRST_KEYS[0], FIRST_KEYS[1]))
    prototype = fixture["prototype"]
    for i, node in enumerate(prototype["source_state"]["tree"]["nodes"]):
        node["key"] = remap[node["key"]]
        address = prototype["source_addresses"][i]
        pointer = factory._raw(fixture["pages"], address + 16)
        value = f"{node['key']:08x}".encode() + b"\0"
        prototype["strings"][pointer] = value
        for j, b in enumerate(value):
            a = pointer + j
            p, off = a & ~4095, a & 4095
            fixture["patches"].append(dict(address=a, before=pages[p][off], after=b))
            pages[p][off] = b
        fixture["key_bindings"][i]["sha256"] = hashlib.sha256(value).hexdigest()
    fixture["callback_vector"]["source_keys"] = list(reversed(FIRST_KEYS[1]))
    prototype["transfer"] = old.prefix.model.transfer(
        prototype["source_state"], prototype["destination_state"]
    )
    cv = fixture["callback_vector"]
    fixture["logical"] = callback.model.apply(
        prototype["source_state"],
        prototype["destination_state"],
        dict(records=[], capacity=0),
        source_pointer=fixture["source_pointer"],
        source_word=cv["source_word"],
        destination_word=cv["destination_word"],
        source_refs=cv["source_refs"],
        destination_refs=cv["destination_refs"],
        transfers=cv["transfers"],
        allow_growth=True,
    )
    fixture["pages"] = {p: bytes(b) for p, b in pages.items()}
    return fixture


def _resume(produced, first_fixture, captured, vector):
    base = _base_vector(vector)
    _check_retained_first(produced, first_fixture, captured)
    fixture = repeat._resume(produced, first_fixture, captured, base)
    cv = fixture["callback_vector"]
    cv["source_keys"] = list(
        reversed(SECOND_KEYS[vector["first_key_profile"]][vector["source_profile"]])
    )
    cv["payload_seed"] = 0xAD7300FF
    supplied = old.prefix._fixture(cv)
    pages = {p: bytearray(b) for p, b in fixture["pages"].items()}
    patches = fixture["patches"]
    fresh_pages = list(fixture.get("fresh_pages", []))

    def put(address, value, width=4):
        for i, byte in enumerate(value.to_bytes(width, "little")):
            a = address + i
            p, off = a & ~4095, a & 4095
            if p not in pages:
                pages[p] = bytearray(b"\xa5" * 4096)
                fresh_pages.append(p)
            patches.append(dict(address=a, before=pages[p][off], after=byte))
            pages[p][off] = byte

    for i in range(14):
        put(
            old.prefix.SOURCE_HEAD + i,
            factory._raw(supplied["pages"], old.prefix.SOURCE_HEAD + i, 1),
            1,
        )
    prototype = fixture["prototype"]
    bindings = []
    for i, address in enumerate(supplied["source_addresses"]):
        for j in range(24):
            put(address + j, factory._raw(supplied["pages"], address + j, 1), 1)
        pointer = SECOND_KEY_STORAGE + 32 * i + 3
        value = supplied["strings"][factory._raw(supplied["pages"], address + 16)]
        put(address + 16, pointer)
        for j, byte in enumerate(value):
            put(pointer + j, byte, 1)
        prototype["strings"][pointer] = value
        bindings.append(
            dict(
                node=address,
                key_pointer=pointer,
                bytes=len(value),
                sha256=hashlib.sha256(value).hexdigest(),
            )
        )
    prototype.update(
        source_state=copy.deepcopy(supplied["source_state"]),
        source_addresses=list(supplied["source_addresses"]),
        node=old.construction.DATA + 0x400 + 31,
    )
    prototype["transfer"] = old.prefix.model.transfer(
        prototype["source_state"], prototype["destination_state"]
    )
    fixture["logical"] = callback.model.apply(
        prototype["source_state"],
        prototype["destination_state"],
        dict(records=[[0, fixture["source_pointer"]]], capacity=1),
        source_pointer=fixture["source_pointer"],
        source_word=cv["source_word"],
        destination_word=cv["source_word"],
        source_refs=cv["source_refs"],
        destination_refs=cv["destination_refs"],
        transfers=cv["transfers"],
        allow_growth=True,
    )
    frozen = {p: bytes(b) for p, b in pages.items()}
    retained = [
        (fixture["receiver"], 72),
        (produced["fixture"]["record"], 24),
        (first_fixture["vector_begin"], 8),
    ]
    retained += [(a, 24) for a in prototype["destination_addresses"]]
    retained += [(p, len(b)) for p, b in first_fixture["prototype"]["strings"].items()]
    _require(
        all(
            factory._raw(frozen, a + i, 1) == factory._raw(captured["pages"], a + i, 1)
            for a, n in retained
            for i in range(n)
        ),
        "extension host changed retained storage",
    )
    _require(
        prototype["node"] >= max(a + 24 for a in prototype["destination_addresses"])
        and prototype["node"] + 32 * 7 < fixture["vector_begin"],
        "extension node schedule overlaps retained storage",
    )
    return dict(
        fixture, pages=frozen, fresh_pages=fresh_pages, second_key_bindings=bindings
    )


def _check_retained_first(produced, first_fixture, captured):
    observation = captured["observation"]
    _require(
        captured["registers"] == observation["registers"]
        and repeat._page_sha(captured["pages"]) == observation["memory_sha256"],
        "verified callback capture differs",
    )
    first = model.tree_model.apply(**repeat._first_arguments(first_fixture, produced))
    state = first["class_transfer"]["destination"]
    nodes = [a["node"] for a in observation["allocations"][:-1]]
    _require(len(nodes) == 3, "extension retained first tree differs")
    source = first_fixture["prototype"]
    pointers = {
        n["key"]: factory._raw(first_fixture["pages"], a + 16)
        for n, a in zip(
            source["source_state"]["tree"]["nodes"], source["source_addresses"]
        )
    }
    sentinel = produced["fixture"]["record"]
    at = lambda i: sentinel if i is None else nodes[i]
    pages = captured["pages"]
    links = first["sentinel_link_ids"]
    userdata = first_fixture["receiver"]
    updates = first["normal_field_updates"]
    _require(
        captured["registers"] == first["full_return"]["registers"]
        and [factory._raw(pages, sentinel + o) for o in (0, 4, 8)]
        == [at(links["leftmost"]), at(links["root"]), at(links["rightmost"])]
        and all(
            factory._raw(pages, sentinel + i, 1)
            == factory._raw(first_fixture["pages"], sentinel + i, 1)
            for i in range(12, 24)
        )
        and all(
            factory._raw(pages, userdata + o)
            == updates.get(o, factory._raw(first_fixture["pages"], userdata + o))
            for o in range(0, 72, 4)
        )
        and [factory._raw(pages, first_fixture["vector_begin"] + o) for o in (0, 4)]
        == [0, first_fixture["source_pointer"]],
        "extension retained first tree differs",
    )
    _require(
        all(
            [factory._raw(pages, a + o) for o in (0, 4, 8, 16, 20)]
            == [
                at(n["left"]),
                at(n["parent"]),
                at(n["right"]),
                pointers[n["key"]],
                state["payloads"][i],
            ]
            and factory._raw(pages, a + 12, 1) == n["color"]
            and factory._raw(pages, a + 13, 1) == 0
            for i, (a, n) in enumerate(zip(nodes, state["tree"]["nodes"]))
        )
        and all(
            factory._raw(pages, p + i, 1) == b
            for p, value in source["strings"].items()
            for i, b in enumerate(value)
        ),
        "extension retained first tree differs",
    )


def _logical(fixture):
    return model.apply(
        first_arguments=fixture["first_arguments"],
        second_source_state=fixture["prototype"]["source_state"],
        new_vector_pointer=fixture["vector_begin"],
        second_entry=fixture["entry"],
        second_registers=fixture["registers"],
    )["second"]


def _run_case(codes, points, fixture, produced, vector, negative=None, *, capture=None):
    logical = _logical(fixture)
    result = normal._run_case(
        codes,
        points,
        fixture,
        produced,
        _base_vector(vector),
        negative,
        logical=logical,
        class_module=old,
        capture=capture,
    )
    if negative == "cookie":
        return result
    expected = callback._expected(fixture["callback_vector"], fixture, class_module=old)
    child = next(c for c in expected["children"] if c["kind"] == "class")["result"]
    copies = logical["class_transfer"]["copies"]
    n = sum(c["inserted"] for c in copies)
    _require(
        child["tree_heap_count"] == n
        and [a["request"] for a in result["allocations"]] == [24] * n + [16]
        and len(result["frees"]) == 1
        and result["frees"][0]["pointer"] == logical["old_vector_pointer"],
        "extension allocation free partition differs",
    )
    nodes = child["destination_addresses"]
    existing = fixture["prototype"]["destination_addresses"]
    _require(
        nodes[: len(existing)] == existing
        and nodes[len(existing) :]
        == [fixture["prototype"]["node"] + 32 * i for i in range(n)],
        "extension stable node addresses differ",
    )
    _require(
        child["insertions"]
        == [
            dict(
                source=c["source"],
                key=c["key"],
                destination_address=nodes[c["destination"]],
                inserted=c["inserted"],
                mode=old.prefix._mode(
                    [
                        x["key"]
                        for x in fixture["prototype"]["destination_state"]["tree"][
                            "nodes"
                        ]
                    ]
                    + [v["key"] for v in copies[:i] if v["inserted"]],
                    c["key"],
                ),
                payload=c["payload"],
                heap_node=nodes[c["destination"]] if c["inserted"] else None,
            )
            for i, c in enumerate(copies)
        ],
        "extension independent copy routing differs",
    )
    final = expected["pages"]
    p = produced["fixture"]["record"]
    at = lambda i: p if i is None else nodes[i]
    links = logical["sentinel_link_ids"]
    _require(
        [factory._raw(final, p + o) for o in (0, 4, 8)]
        == [at(links["leftmost"]), at(links["root"]), at(links["rightmost"])]
        and factory._raw(final, fixture["receiver"] + 56) == logical["tree_count"],
        "extension independent sentinel count differs",
    )
    _require(
        all(
            factory._raw(final, p + i, 1) == factory._raw(fixture["pages"], p + i, 1)
            for i in range(12, 24)
        )
        and all(
            factory._raw(final, fixture["receiver"] + o)
            == factory._raw(fixture["pages"], fixture["receiver"] + o)
            for o in logical["normal_preserved_userdata_offsets"]
        ),
        "extension independent preserved fields differ",
    )
    selected = {c["destination"] for c in copies}
    _require(
        all(
            factory._raw(final, a + 16) == factory._raw(fixture["pages"], a + 16)
            and (
                i in selected
                or factory._raw(final, a + 20) == factory._raw(fixture["pages"], a + 20)
            )
            for i, a in enumerate(existing)
        ),
        "extension retained key pointer or omitted payload differs",
    )
    _require(
        [factory._raw(final, fixture["vector_begin"] + 4 * i) for i in range(4)]
        == [0, fixture["source_pointer"], 0, fixture["source_pointer"]]
        and all(
            factory._raw(final, logical["old_vector_pointer"] + i, 1)
            == factory._raw(fixture["pages"], logical["old_vector_pointer"] + i, 1)
            for i in range(8)
        ),
        "extension independent retained record copy differs",
    )
    return dict(
        result,
        new_tree_nodes=n,
        existing_payload_updates=len(copies) - n,
        source_copies=len(copies),
        final_tree_count=logical["tree_count"],
        captured_pages_sha256=fixture["captured_pages_sha256"],
        second_key_bindings_sha256=_canonical_sha256(fixture["second_key_bindings"]),
    )


def _resume_first(produced, vector):
    _require(vector in vectors(), "unreviewed factory callback extension profile")
    fixture = tree._resume(produced, _base_vector(vector))
    return _rekey_first(fixture) if vector["first_key_profile"] else fixture


CONTROLS = {
    **tree.CONTROLS,
    "free_request": "callback free handoff differs",
    "free_register": "factory return free ABI differs",
    "free_flags": "factory return free ABI differs",
    "free_identity": "factory return free response identity differs",
    "old": "callback protected memory differs",
}


def _preflight(sources):
    _require(
        set(sources) == set(SOURCE_PINS), "factory extension source partition differs"
    )
    return {
        k: factory._source_identity(sources[k], *pin, k)
        for k, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    payload, fp, continuation, _, _ = normal._load_code(data, image, sources)
    codes, points = callback._load_code(
        data, image, dict(sources, class_spare=sources["class_old"])
    )
    return payload, fp, continuation, codes, points


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = full._load_executable(Path(executable))
    _require(
        digest == full.EXE_SHA256 and image.image_base == BASE,
        "exact factory extension executable differs",
    )
    payload, fp, continuation, codes, points = _load_code(data, image, sources)
    firsts, seconds, producers = [], [], []
    sample = None
    for vector in vectors():
        produced, producer, f1, captured = _produce_first(
            payload, fp, continuation, codes, points, vector
        )
        fixture = _resume(produced, f1, captured, vector)
        firsts.append(captured["observation"])
        seconds.append(_run_case(codes, points, fixture, produced, vector))
        producers.append(producer)
        if (
            vector["profile"] == 1
            and vector["source_profile"] == 3
            and vector["first_key_profile"] == 1
            and vector["transfer_profile"] == 4
        ):
            sample = (produced, f1, captured, fixture, vector)
    controls = []
    for kind, reason in CONTROLS.items():
        try:
            _run_case(codes, points, sample[3], sample[0], sample[4], kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "extension incidental control: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("extension control survived: " + kind)
    failure = _run_case(codes, points, sample[3], sample[0], sample[4], "cookie")
    _require(
        failure == dict(kind="cookie", rejected=True, endpoint="0x003574d5"),
        "extension cookie failure differs",
    )
    controls.append(dict(failure, kind="native_callback_cookie"))
    for kind in ("capture_pages", "capture_registers"):
        cap = copy.deepcopy(sample[2])
        if kind == "capture_registers":
            cap["registers"]["eax"] ^= 1
        else:
            page = sample[1]["vector_begin"] & ~4095
            b = bytearray(cap["pages"][page])
            b[sample[1]["vector_begin"] & 4095] ^= 1
            cap["pages"][page] = bytes(b)
        try:
            _resume(sample[0], sample[1], cap, sample[4])
        except ConformanceError as exc:
            _require(
                str(exc) == "verified callback capture differs",
                "extension capture incidental rejection",
            )
            controls.append(dict(kind=kind, rejected=True, reason=str(exc)))
        else:
            raise ConformanceError("extension capture control survived")
    for kind in (
        "retained_key_pointer",
        "retained_payload",
        "retained_key_bytes",
        "retained_link",
    ):
        cap = copy.deepcopy(sample[2])
        node = cap["observation"]["allocations"][0]["node"]
        address = (
            factory._raw(cap["pages"], node + 16)
            if kind == "retained_key_bytes"
            else node
            + {"retained_key_pointer": 16, "retained_payload": 20, "retained_link": 0}[
                kind
            ]
        )
        page = address & ~4095
        b = bytearray(cap["pages"][page])
        b[address & 4095] ^= 1
        cap["pages"][page] = bytes(b)
        cap["observation"]["memory_sha256"] = repeat._page_sha(cap["pages"])
        try:
            _resume(sample[0], sample[1], cap, sample[4])
        except ConformanceError as exc:
            _require(
                str(exc) == "extension retained first tree differs",
                "extension retained control incidental rejection",
            )
            controls.append(dict(kind=kind, rejected=True, reason=str(exc)))
        else:
            raise ConformanceError("extension retained control survived")
    first_sites = sorted({r for o in firsts for r in o["trace_rvas"]})
    second_sites = sorted({r for o in seconds for r in o["trace_rvas"]})
    union = sorted(set(first_sites) | set(second_sites))
    selected = {p["rva"] for p in points}
    _require(
        set(first_sites)
        == set(sources["factory_callback_tree"]["families"]["3"]["executed_rvas"])
        and set(union) <= selected
        and not any(
            a <= int(r, 16) < b for r in union for a, b in normal.PARENT_EXCLUDED
        ),
        "extension normal site partition differs",
    )
    base = sources["factory_callback_tree"]["normal_site_partition"]
    parent, markers, tables = (set(base[k]) for k in ("callback", "markers", "tables"))
    count = len(seconds)
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
        executed_rvas=union,
        first_executed_rvas=first_sites,
        second_executed_rvas=second_sites,
        normal_site_partition=dict(
            callback=sorted(parent),
            class_operation=sorted(set(union) - parent - markers - tables),
            markers=sorted(markers),
            tables=sorted(tables),
            excluded=sorted(selected - set(union)),
        ),
        negative_controls=controls,
        first_observations_sha256=repeat._canonical_sha256(firsts),
        second_observations_sha256=_canonical_sha256(seconds),
        producer_observations_sha256=_canonical_sha256(producers),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=count,
            callback_invocations=2 * count,
            static_sites=len(points),
            executed_sites=len(union),
            instruction_bytes=len(
                {a + i for a, b in codes.items() for i in range(len(b))}
            ),
            factory_instructions=sum(len(o["trace_rvas"]) for o in producers),
            first_callback_instructions=sum(len(o["trace_rvas"]) for o in firsts),
            second_callback_instructions=sum(len(o["trace_rvas"]) for o in seconds),
            factory_api_calls=34 * count,
            callback_api_calls=sum(o["api_calls"] for o in firsts + seconds),
            factory_heap_calls=count,
            first_class_heap_calls=sum(len(o["allocations"]) for o in firsts),
            second_class_heap_calls=sum(len(o["allocations"]) for o in seconds),
            first_tree_nodes=sum(v["source_size"] for v in vectors()),
            second_tree_allocations=sum(o["new_tree_nodes"] for o in seconds),
            second_payload_updates=sum(o["existing_payload_updates"] for o in seconds),
            second_source_copies=sum(o["source_copies"] for o in seconds),
            final_tree_nodes=sum(o["final_tree_count"] for o in seconds),
            copied_old_vector_bytes=8 * count,
            second_vector_bytes=16 * count,
            free_calls=count,
            marker_calls=4 * count,
            table_calls=4 * count,
            requested_assignments=sum(
                sum(map(len, o["assignments"])) for o in firsts + seconds
            ),
            retained_lua_values_per_call=5,
            result_count=0,
            controls=len(controls),
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            continuous_each_callback=True,
            continuous_across_host=False,
            checked=[
                "Actual produced receiver and verified first return pages retained across explicit second invocation",
                "New minimum interior and end keys and existing updates retain existing IDs omitted payloads and original key strings",
                "Native old vector growth copy successful free response append identity bound requests and both normal returns",
            ],
            premises=[
                "Explicit host invocation source topology nodes new query strings free import binding and repeated source word registry and transfer premises",
                "Successful disjoint bounded tree and vector allocations and free response with retained freed bytes",
            ],
            excluded=[
                "Other source recipes arbitrary insertion orders more than two callbacks and native unions larger than eight",
                "Real Lua VM ownership invalidation allocator reuse assertion delivery and global accounting",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory extension executable changed",
    )
    normal.first.entry._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    normal.first.entry._validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors(),
        "sealed factory extension differs",
    )
    normal.first.entry._assert_publication_safe(evidence)
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
        "exact factory extension differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


encode_conformance = normal.encode_conformance
