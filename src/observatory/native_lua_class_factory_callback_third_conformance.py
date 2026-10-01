"""Third callback on retained actual factory receiver and two-record vector."""

from __future__ import annotations
import copy
import hashlib
from pathlib import Path
from src.observatory import native_lua_class_factory_callback_tree_conformance as tree
from src.observatory import native_lua_class_old_vector_return_conformance as old
from src.observatory import native_lua_class_factory_callback_third_semantics as model

from src.observatory import (
    native_lua_class_factory_callback_repeat_conformance as repeat,
)

normal, full, factory, callback = tree.normal, tree.full, tree.factory, tree.callback
BASE, ConformanceError, _require = tree.BASE, tree.ConformanceError, tree._require
_canonical_sha256, _canonical_bytes = tree._canonical_sha256, tree._canonical_bytes
ANALYSIS_KIND = "pe_native_lua_class_factory_callback_third_conformance"
SEALED_SHA256 = "2e12f3b7af5475178f0660fbdab0aae7a7478fc684d1ad8f68e8bec7a96a7832"
from src.observatory import (
    native_lua_class_factory_callback_extend_conformance as extend,
)

SOURCE_PINS = {
    **extend.SOURCE_PINS,
    "factory_callback_extend": (extend.ANALYSIS_KIND, extend.SEALED_SHA256),
}


def vectors():
    return [v for v in extend.vectors() if v["source_profile"] == 3]


def _produce_second(payload, fp, continuation, codes, points, vector):
    produced, producer, first_fixture, first_capture = extend._produce_first(
        payload, fp, continuation, codes, points, vector
    )
    second_fixture = extend._resume(produced, first_fixture, first_capture, vector)
    second_capture = {}

    def capture(machine, ids, expected, lua):
        second_capture.update(
            pages={
                p: bytes(machine.mem_read(p, 4096)) for p in second_fixture["pages"]
            },
            registers={r: machine.reg_read(i) for r, i in ids.items()},
        )

    second_capture["observation"] = extend._run_case(
        codes, points, second_fixture, produced, vector, capture=capture
    )
    return (
        produced,
        producer,
        first_fixture,
        first_capture,
        second_fixture,
        second_capture,
    )


def _prior(fixture):
    return model.extend_model.apply(
        first_arguments=fixture["first_arguments"],
        second_source_state=fixture["prototype"]["source_state"],
        new_vector_pointer=fixture["vector_begin"],
        second_entry=fixture["entry"],
        second_registers=fixture["registers"],
    )["second"]


def _check_second(produced, second_fixture, captured):
    observation = captured["observation"]
    _require(
        captured["registers"] == observation["registers"]
        and repeat._page_sha(captured["pages"]) == observation["memory_sha256"],
        "verified second callback capture differs",
    )
    second = _prior(second_fixture)
    source = second_fixture["prototype"]
    nodes = list(source["destination_addresses"]) + [
        a["node"] for a in observation["allocations"] if a["request"] == 24
    ]
    state = second["class_transfer"]["destination"]
    sentinel = produced["fixture"]["record"]
    at = lambda i: sentinel if i is None else nodes[i]
    _require(len(nodes) == second["tree_count"], "retained second callback differs")
    pointers = {
        n["key"]: factory._raw(second_fixture["pages"], a + 16)
        for n, a in zip(
            source["destination_state"]["tree"]["nodes"],
            source["destination_addresses"],
        )
    }
    for n, a in zip(
        source["source_state"]["tree"]["nodes"], source["source_addresses"]
    ):
        pointers.setdefault(n["key"], factory._raw(second_fixture["pages"], a + 16))
    pages = captured["pages"]
    links = second["sentinel_link_ids"]
    u = second_fixture["receiver"]
    updates = second["normal_field_updates"]
    _require(
        captured["registers"] == second["full_return"]["registers"]
        and [factory._raw(pages, sentinel + o) for o in (0, 4, 8)]
        == [at(links["leftmost"]), at(links["root"]), at(links["rightmost"])]
        and all(
            factory._raw(pages, sentinel + i, 1)
            == factory._raw(second_fixture["pages"], sentinel + i, 1)
            for i in range(12, 24)
        )
        and all(
            factory._raw(pages, u + o)
            == updates.get(o, factory._raw(second_fixture["pages"], u + o))
            for o in range(0, 72, 4)
        )
        and [
            factory._raw(pages, second_fixture["vector_begin"] + 4 * i)
            for i in range(4)
        ]
        == [0, second_fixture["source_pointer"], 0, second_fixture["source_pointer"]],
        "retained second callback differs",
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
        "retained second callback differs",
    )
    _require(
        [
            factory._raw(pages, second_fixture["first_arguments"]["vector_pointer"] + o)
            for o in (0, 4)
        ]
        == [0, second_fixture["source_pointer"]]
        and all(
            factory._raw(pages, a) == factory._raw(second_fixture["pages"], a)
            for a in (0, 0x00893F28)
        ),
        "retained second callback differs",
    )
    return second, nodes


def _resume(produced, second_fixture, captured, vector):
    second, nodes = _check_second(produced, second_fixture, captured)
    current = dict(produced, pages=captured["pages"], registers=captured["registers"])
    fixture = normal.first.entry._resume(
        current,
        tree._normal_vector(extend._base_vector(vector)),
        callback_entry=second_fixture["entry"],
    )
    pages = {p: bytearray(b) for p, b in fixture["pages"].items()}
    patches = fixture["patches"]

    def put(address, value):
        for i, b in enumerate(value.to_bytes(4, "little")):
            a = address + i
            p, off = a & ~4095, a & 4095
            patches.append(dict(address=a, before=pages[p][off], after=b))
            pages[p][off] = b

    source_state = copy.deepcopy(second_fixture["prototype"]["source_state"])
    for i, address in enumerate(second_fixture["prototype"]["source_addresses"]):
        source_state["payloads"][i] ^= 0xFFFFFFFF
        put(address + 20, source_state["payloads"][i])
    cv = copy.deepcopy(second_fixture["callback_vector"])
    cv.update(old_size=2, old_alignment=0)
    new_begin = old.construction.DATA + 0x800 + vector["vector_alignment"]
    prototype = dict(
        copy.deepcopy(second_fixture["prototype"]),
        source_state=source_state,
        destination_state=copy.deepcopy(second["class_transfer"]["destination"]),
        destination_addresses=nodes,
        old_begin=second_fixture["vector_begin"],
        old_size=2,
        old_base=second_fixture["vector_begin"] & ~4095,
        new_page_count=1,
        vector_begin=new_begin,
        vector_end=new_begin + 16,
        vector_capacity=new_begin + 24,
        node=old.construction.DATA + 0x600 + 31,
    )
    prototype["transfer"] = old.prefix.model.transfer(
        source_state, prototype["destination_state"]
    )
    logical = callback.model.apply(
        source_state,
        prototype["destination_state"],
        dict(records=[[0, second_fixture["source_pointer"]]] * 2, capacity=2),
        source_pointer=second_fixture["source_pointer"],
        source_word=cv["source_word"],
        destination_word=cv["source_word"],
        source_refs=cv["source_refs"],
        destination_refs=cv["destination_refs"],
        transfers=cv["transfers"],
        allow_growth=True,
    )
    frozen = {p: bytes(b) for p, b in pages.items()}
    retained = (
        [
            (fixture["receiver"], 72),
            (produced["fixture"]["record"], 24),
            (second_fixture["vector_begin"], 16),
            (second_fixture["first_arguments"]["vector_pointer"], 8),
        ]
        + [(a, 24) for a in nodes]
        + [(p, len(b)) for p, b in prototype["strings"].items()]
    )
    _require(
        all(
            factory._raw(frozen, a + i, 1) == factory._raw(captured["pages"], a + i, 1)
            for a, n in retained
            for i in range(n)
        ),
        "third host changed retained storage",
    )
    return dict(
        fixture,
        pages=frozen,
        prototype=prototype,
        logical=logical,
        callback_vector=cv,
        source_pointer=second_fixture["source_pointer"],
        endpoint=callback.RETURN,
        vector_begin=new_begin,
        first_arguments=copy.deepcopy(second_fixture["first_arguments"]),
        second_source_state=copy.deepcopy(second_fixture["prototype"]["source_state"]),
        second_vector_pointer=second_fixture["vector_begin"],
        second_entry=second_fixture["entry"],
        second_registers=copy.deepcopy(second_fixture["registers"]),
        captured_pages_sha256=repeat._page_sha(captured["pages"]),
    )


def _logical(fixture):
    return model.apply(
        first_arguments=fixture["first_arguments"],
        second_source_state=fixture["second_source_state"],
        second_vector_pointer=fixture["second_vector_pointer"],
        second_entry=fixture["second_entry"],
        second_registers=fixture["second_registers"],
        third_source_state=fixture["prototype"]["source_state"],
        new_vector_pointer=fixture["vector_begin"],
        third_entry=fixture["entry"],
        third_registers=fixture["registers"],
    )["third"]


def _run_case(codes, points, fixture, produced, vector, negative=None, *, capture=None):
    logical = _logical(fixture)
    result = normal._run_case(
        codes,
        points,
        fixture,
        produced,
        extend._base_vector(vector),
        negative,
        logical=logical,
        class_module=old,
        capture=capture,
    )
    if negative == "cookie":
        return result
    expected = callback._expected(fixture["callback_vector"], fixture, class_module=old)
    child = next(c for c in expected["children"] if c["kind"] == "class")["result"]
    _require(
        child["tree_heap_count"] == 0
        and [a["request"] for a in result["allocations"]] == [24]
        and len(result["frees"]) == 1
        and result["frees"][0]["pointer"] == fixture["second_vector_pointer"],
        "third allocation free partition differs",
    )
    nodes = fixture["prototype"]["destination_addresses"]
    _require(
        child["destination_addresses"] == nodes
        and child["insertions"]
        == [
            dict(
                source=c["source"],
                key=c["key"],
                destination_address=nodes[c["destination"]],
                inserted=False,
                mode="existing",
                payload=c["payload"],
                heap_node=None,
            )
            for c in logical["class_transfer"]["copies"]
        ],
        "third independent existing routing differs",
    )
    final = expected["pages"]
    p = produced["fixture"]["record"]
    _require(
        all(
            factory._raw(final, p + i, 1) == factory._raw(fixture["pages"], p + i, 1)
            for i in range(24)
        )
        and all(
            factory._raw(final, fixture["receiver"] + o)
            == factory._raw(fixture["pages"], fixture["receiver"] + o)
            for o in logical["normal_preserved_userdata_offsets"]
        ),
        "third independent preserved fields differ",
    )
    selected = {c["destination"] for c in logical["class_transfer"]["copies"]}
    _require(
        all(
            factory._raw(final, a + 16) == factory._raw(fixture["pages"], a + 16)
            and (
                i in selected
                or factory._raw(final, a + 20) == factory._raw(fixture["pages"], a + 20)
            )
            for i, a in enumerate(nodes)
        ),
        "third retained key or omitted payload differs",
    )
    _require(
        [factory._raw(final, fixture["vector_begin"] + 4 * i) for i in range(6)]
        == [0, fixture["source_pointer"]] * 3
        and all(
            factory._raw(final, fixture["second_vector_pointer"] + i, 1)
            == factory._raw(fixture["pages"], fixture["second_vector_pointer"] + i, 1)
            for i in range(16)
        )
        and all(
            factory._raw(final, fixture["first_arguments"]["vector_pointer"] + i, 1)
            == factory._raw(
                fixture["pages"], fixture["first_arguments"]["vector_pointer"] + i, 1
            )
            for i in range(8)
        ),
        "third independent retained vector copies differ",
    )
    return dict(
        result,
        payload_updates=len(logical["class_transfer"]["copies"]),
        captured_pages_sha256=fixture["captured_pages_sha256"],
    )


CONTROLS = {
    **normal.CONTROLS,
    "free_request": "callback free handoff differs",
    "free_register": "factory return free ABI differs",
    "free_flags": "factory return free ABI differs",
    "free_identity": "factory return free response identity differs",
    "old": "callback protected memory differs",
}


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "factory third source partition differs")
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
        "exact factory third executable differs",
    )
    payload, fp, continuation, codes, points = _load_code(data, image, sources)
    firsts, seconds, thirds, producers = [], [], [], []
    sample = None
    for vector in vectors():
        produced, producer, f1, cap1, f2, cap2 = _produce_second(
            payload, fp, continuation, codes, points, vector
        )
        fixture = _resume(produced, f2, cap2, vector)
        firsts.append(cap1["observation"])
        seconds.append(cap2["observation"])
        thirds.append(_run_case(codes, points, fixture, produced, vector))
        producers.append(producer)
        if (
            vector["profile"] == 1
            and vector["first_key_profile"] == 1
            and vector["transfer_profile"] == 4
        ):
            sample = (produced, f2, cap2, fixture, vector)
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
                str(exc) == "verified second callback capture differs",
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
        node = sample[1]["prototype"]["destination_addresses"][0]
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
                str(exc) == "retained second callback differs",
                "extension retained control incidental rejection",
            )
            controls.append(dict(kind=kind, rejected=True, reason=str(exc)))
        else:
            raise ConformanceError("extension retained control survived")
    first_sites = sorted({r for o in firsts for r in o["trace_rvas"]})
    second_sites = sorted({r for o in seconds for r in o["trace_rvas"]})
    third_sites = sorted({r for o in thirds for r in o["trace_rvas"]})
    union = sorted(set(first_sites) | set(second_sites) | set(third_sites))
    selected = {p["rva"] for p in points}
    _require(
        set(first_sites)
        == set(sources["factory_callback_tree"]["families"]["3"]["executed_rvas"])
        and set(second_sites)
        <= set(sources["factory_callback_extend"]["second_executed_rvas"])
        and set(union) <= selected
        and not any(
            a <= int(r, 16) < b for r in union for a, b in normal.PARENT_EXCLUDED
        ),
        "third normal site partition differs",
    )
    base = sources["factory_callback_tree"]["normal_site_partition"]
    parent, markers, tables = (set(base[k]) for k in ("callback", "markers", "tables"))
    count = len(thirds)
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
        third_executed_rvas=third_sites,
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
        third_observations_sha256=_canonical_sha256(thirds),
        producer_observations_sha256=_canonical_sha256(producers),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=count,
            callback_invocations=3 * count,
            static_sites=len(points),
            executed_sites=len(union),
            instruction_bytes=len(
                {a + i for a, b in codes.items() for i in range(len(b))}
            ),
            factory_instructions=sum(len(o["trace_rvas"]) for o in producers),
            first_callback_instructions=sum(len(o["trace_rvas"]) for o in firsts),
            second_callback_instructions=sum(len(o["trace_rvas"]) for o in seconds),
            third_callback_instructions=sum(len(o["trace_rvas"]) for o in thirds),
            factory_api_calls=34 * count,
            callback_api_calls=sum(o["api_calls"] for o in firsts + seconds + thirds),
            factory_heap_calls=count,
            first_class_heap_calls=sum(len(o["allocations"]) for o in firsts),
            second_class_heap_calls=sum(len(o["allocations"]) for o in seconds),
            third_class_heap_calls=count,
            first_tree_nodes=sum(v["source_size"] for v in vectors()),
            second_tree_allocations=sum(o["new_tree_nodes"] for o in seconds),
            second_payload_updates=sum(o["existing_payload_updates"] for o in seconds),
            third_payload_updates=sum(o["payload_updates"] for o in thirds),
            third_tree_allocations=0,
            second_source_copies=sum(o["source_copies"] for o in seconds),
            final_tree_nodes=sum(o["final_tree_count"] for o in seconds),
            second_copied_old_vector_bytes=8 * count,
            third_copied_old_vector_bytes=16 * count,
            second_vector_bytes=16 * count,
            third_vector_bytes=24 * count,
            free_calls=2 * count,
            marker_calls=6 * count,
            table_calls=6 * count,
            requested_assignments=sum(
                sum(map(len, o["assignments"])) for o in firsts + seconds + thirds
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
                "Actual produced receiver and verified first and second return pages retained across explicit host invocations",
                "Verified second capture retains existing IDs omitted payloads sentinel links and all original key strings before third payload update",
                "Native two record old vector growth to capacity three copy successful free response append and all three normal returns",
            ],
            premises=[
                "Explicit host invocation source topology nodes new query strings free import binding and repeated source word registry and transfer premises",
                "Successful disjoint bounded tree and vector allocations and free response with retained freed bytes",
            ],
            excluded=[
                "New third pass keys other source recipes more than three callbacks and native unions larger than eight",
                "Real Lua VM ownership invalidation allocator reuse assertion delivery and global accounting",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory third executable changed",
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
        "sealed factory third differs",
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
        "exact factory third differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


encode_conformance = normal.encode_conformance
