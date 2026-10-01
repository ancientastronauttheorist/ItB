"""Two native callbacks retaining actual factory and first-return state."""

from __future__ import annotations
import copy
import hashlib
from pathlib import Path
from src.observatory import native_lua_class_factory_callback_tree_conformance as tree
from src.observatory import native_lua_class_old_vector_return_conformance as old
from src.observatory import native_lua_class_factory_callback_repeat_semantics as model

normal, full, factory, callback = tree.normal, tree.full, tree.factory, tree.callback
BASE, ConformanceError, _require = tree.BASE, tree.ConformanceError, tree._require
_canonical_sha256, _canonical_bytes = tree._canonical_sha256, tree._canonical_bytes
ANALYSIS_KIND = "pe_native_lua_class_factory_callback_repeat_conformance"
SEALED_SHA256 = "b4b28a9a2f8675705257af3a100f50b72082d1c543a12aff2a5d76e17950966e"
SOURCE_PINS = {
    **tree.SOURCE_PINS,
    **old.SOURCE_PINS,
    "class_old": (old.ANALYSIS_KIND, old.SEALED_SHA256),
    "factory_callback_tree": (tree.ANALYSIS_KIND, tree.SEALED_SHA256),
}


def vectors():
    return [v for v in tree.vectors() if v["node_alignment"] == 31]


def _page_sha(pages):
    return _canonical_sha256(
        {str(p): hashlib.sha256(b).hexdigest() for p, b in pages.items()}
    )


def _first_arguments(fixture, produced):
    cv = fixture["callback_vector"]
    return dict(
        source_state=copy.deepcopy(fixture["prototype"]["source_state"]),
        state=fixture["state"],
        userdata=fixture["receiver"],
        record_pointer=produced["fixture"]["record"],
        source_pointer=fixture["source_pointer"],
        callback_entry=fixture["entry"],
        registers=copy.deepcopy(fixture["registers"]),
        closure_target=produced["closure"][1],
        closure_upvalues=[produced["closure"][2][1]],
        upvalue_has_metatable=True,
        argument_has_metatable=True,
        upvalue_marker_kind="zero",
        argument_marker_kind="table",
        vector_pointer=fixture["vector_begin"],
        cookie=cv["cookie"],
        source_word=cv["source_word"],
        destination_word=cv["destination_word"],
        destination_refs=copy.deepcopy(cv["destination_refs"]),
        source_refs=copy.deepcopy(cv["source_refs"]),
        transfers=copy.deepcopy(cv["transfers"]),
    )


def _produce_first(payload, fp, continuation, codes, points, vector):
    produced, producer = normal.first._produce(
        payload, fp, continuation, normal._first_vector(tree._normal_vector(vector))
    )
    fixture = tree._resume(produced, vector)
    captured = {}

    def capture(machine, ids, expected, lua):
        captured.update(
            pages={p: bytes(machine.mem_read(p, 4096)) for p in fixture["pages"]},
            registers={r: machine.reg_read(i) for r, i in ids.items()},
        )

    observation = tree._run_case(
        codes, points, fixture, produced, vector, capture=capture
    )
    captured["observation"] = observation
    return produced, producer, fixture, captured


def _resume(produced, first_fixture, captured, vector):
    observation = captured["observation"]
    _require(
        captured["registers"] == observation["registers"]
        and _page_sha(captured["pages"]) == observation["memory_sha256"],
        "verified callback capture differs",
    )
    first_arguments = _first_arguments(first_fixture, produced)
    first_result = model.tree_model.apply(**first_arguments)
    current = dict(produced, pages=captured["pages"], registers=captured["registers"])
    fixture = normal.first.entry._resume(
        current, tree._normal_vector(vector), callback_entry=first_fixture["entry"]
    )
    pages = {p: bytearray(b) for p, b in fixture["pages"].items()}
    patches = list(fixture["patches"])

    def put(address, value):
        for i, byte in enumerate(value.to_bytes(4, "little")):
            p, off = (address + i) & ~4095, (address + i) & 4095
            patches.append(dict(address=address + i, before=pages[p][off], after=byte))
            pages[p][off] = byte

    put(old.growth.FREE_IAT, normal.layout.HEAP_TARGET)
    source_state = copy.deepcopy(first_fixture["prototype"]["source_state"])
    for i, address in enumerate(first_fixture["prototype"]["source_addresses"]):
        source_state["payloads"][i] ^= 0xFFFFFFFF
        put(address + 20, source_state["payloads"][i])
    cv = dict(
        copy.deepcopy(first_fixture["callback_vector"]), old_size=1, old_alignment=0
    )
    destination = copy.deepcopy(first_result["class_transfer"]["destination"])
    new_begin = old.construction.DATA + 0x1000 + vector["vector_alignment"]
    destination_addresses = [a["node"] for a in observation["allocations"][:-1]]
    _require(
        len(destination_addresses) == vector["source_size"],
        "retained tree address count differs",
    )
    prototype = dict(
        copy.deepcopy(first_fixture["prototype"]),
        source_state=source_state,
        destination_state=destination,
        destination_addresses=destination_addresses,
        old_begin=first_fixture["vector_begin"],
        old_size=1,
        old_base=first_fixture["vector_begin"] & ~4095,
        new_page_count=2,
        vector_begin=new_begin,
        vector_end=new_begin + 8,
        vector_capacity=new_begin + 16,
    )
    prototype["transfer"] = old.prefix.model.transfer(source_state, destination)
    logical = callback.model.apply(
        source_state,
        destination,
        dict(records=[[0, first_fixture["source_pointer"]]], capacity=1),
        source_pointer=first_fixture["source_pointer"],
        source_word=cv["source_word"],
        destination_word=cv["source_word"],
        source_refs=cv["source_refs"],
        destination_refs=cv["destination_refs"],
        transfers=cv["transfers"],
        allow_growth=True,
    )
    frozen = {p: bytes(b) for p, b in pages.items()}
    u, p = fixture["receiver"], produced["fixture"]["record"]
    _require(
        all(
            factory._raw(frozen, a + i, 1) == factory._raw(captured["pages"], a + i, 1)
            for a, width in ((u, 72), (p, 24), (first_fixture["vector_begin"], 8))
            for i in range(width)
        ),
        "repeat host changed retained receiver sentinel or vector",
    )
    return dict(
        fixture,
        pages=frozen,
        patches=patches,
        source_pointer=first_fixture["source_pointer"],
        prototype=prototype,
        logical=logical,
        callback_vector=cv,
        endpoint=callback.RETURN,
        vector_begin=new_begin,
        first_arguments=first_arguments,
        captured_pages_sha256=_page_sha(captured["pages"]),
    )


def _logical(fixture):
    return model.apply(
        first_arguments=fixture["first_arguments"],
        second_source_state=fixture["prototype"]["source_state"],
        new_vector_pointer=fixture["vector_begin"],
        second_entry=fixture["entry"],
        second_registers=fixture["registers"],
    )["second"]


def _run_case(codes, points, fixture, produced, vector, negative=None):
    logical = _logical(fixture)
    result = normal._run_case(
        codes,
        points,
        fixture,
        produced,
        vector,
        negative,
        logical=logical,
        class_module=old,
    )
    if negative == "cookie":
        return result
    expected = callback._expected(fixture["callback_vector"], fixture, class_module=old)
    child = next(c for c in expected["children"] if c["kind"] == "class")
    _require(
        child["result"]["tree_heap_count"] == 0
        and [a["request"] for a in result["allocations"]] == [16]
        and len(result["frees"]) == 1
        and result["frees"][0]["pointer"] == logical["old_vector_pointer"],
        "repeat allocation free partition differs",
    )
    nodes = fixture["prototype"]["destination_addresses"]
    _require(
        child["result"]["insertions"]
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
        "repeat independent existing payload routing differs",
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
        "repeat independent preserved fields differ",
    )
    _require(
        [factory._raw(final, fixture["vector_begin"] + 4 * i) for i in range(4)]
        == [0, fixture["source_pointer"], 0, fixture["source_pointer"]]
        and all(
            factory._raw(final, logical["old_vector_pointer"] + i, 1)
            == factory._raw(fixture["pages"], logical["old_vector_pointer"] + i, 1)
            for i in range(8)
        ),
        "repeat independent retained record copy differs",
    )
    return dict(
        result,
        payload_updates=vector["source_size"],
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
    _require(
        set(sources) == set(SOURCE_PINS), "factory repeat source partition differs"
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
        "exact factory repeat executable differs",
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
            and vector["source_size"] == 7
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
                "repeat incidental control: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("repeat control survived: " + kind)
    failure = _run_case(codes, points, sample[3], sample[0], sample[4], "cookie")
    _require(
        failure == dict(kind="cookie", rejected=True, endpoint="0x003574d5"),
        "repeat cookie failure differs",
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
                "repeat capture incidental rejection",
            )
            controls.append(dict(kind=kind, rejected=True, reason=str(exc)))
        else:
            raise ConformanceError("repeat capture control survived")
    first_sites = sorted({r for o in firsts for r in o["trace_rvas"]})
    second_sites = sorted({r for o in seconds for r in o["trace_rvas"]})
    union = sorted(set(first_sites) | set(second_sites))
    selected = {p["rva"] for p in points}
    _require(
        set(first_sites) == set(sources["factory_callback_tree"]["executed_rvas"])
        and set(union) <= selected
        and not any(
            a <= int(r, 16) < b for r in union for a, b in normal.PARENT_EXCLUDED
        ),
        "repeat normal site partition differs",
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
        first_observations_sha256=_canonical_sha256(firsts),
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
            second_class_heap_calls=count,
            first_tree_nodes=sum(v["source_size"] for v in vectors()),
            second_tree_allocations=0,
            second_payload_updates=sum(o["payload_updates"] for o in seconds),
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
                "Same source keys updated payloads existing destination IDs preserved sentinel and retained vector record",
                "Native old vector growth copy successful free response append identity bound requests and both normal returns",
            ],
            premises=[
                "Explicit host invocation source payload patches free import binding and repeated source word registry and transfer premises",
                "Successful bounded allocations and free response with retained freed bytes",
            ],
            excluded=[
                "New second pass keys tree allocations arbitrary insertion orders more than two callbacks",
                "Real Lua VM ownership invalidation allocator reuse assertion delivery and global accounting",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory repeat executable changed",
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
        "sealed factory repeat differs",
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
        "exact factory repeat differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


encode_conformance = normal.encode_conformance
