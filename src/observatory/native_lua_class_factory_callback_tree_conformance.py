"""Actual factory receiver through bounded nonempty-source callback return."""

from __future__ import annotations
import copy
import hashlib
from pathlib import Path
from src.observatory import (
    native_lua_class_factory_callback_return_conformance as normal,
)
from src.observatory import native_lua_class_factory_callback_tree_semantics as model

full, factory, callback, empty = (
    normal.full,
    normal.factory,
    normal.callback,
    normal.empty,
)
BASE, ConformanceError, _require = normal.BASE, normal.ConformanceError, normal._require
_canonical_sha256, _canonical_bytes = normal._canonical_sha256, normal._canonical_bytes
ANALYSIS_KIND = "pe_native_lua_class_factory_callback_tree_conformance"
SEALED_SHA256 = "a924cb10e338afa823ced7bf0fb3de20e8b8bb4b1e962fdcc299fec2f2b77614"
SOURCE_PINS = {
    **normal.SOURCE_PINS,
    **empty.prefix.SOURCE_PINS,
    "class_tree": (empty.prefix.ANALYSIS_KIND, empty.prefix.SEALED_SHA256),
    "factory_callback_return": (normal.ANALYSIS_KIND, normal.SEALED_SHA256),
}
SOURCE_KEYS = (0, 1, 16, 255, 0x80000000, 0xFFFFFFFE, 0xFFFFFFFF)
KEY_STORAGE = 0x1C000FFF


def vectors():
    return [
        dict(v, transfer_profile=t, source_size=n, node_alignment=a)
        for v in normal.first.vectors()
        for n in (0, 1, 3, 7)
        for a in (0, 7, 31)
        for t in (0, 4)
    ]


def _normal_vector(vector):
    return {
        k: v for k, v in vector.items() if k not in ("source_size", "node_alignment")
    }


def _resume(produced, vector):
    _require(
        type(vector["source_size"]) is int
        and vector["source_size"] in (0, 1, 3, 7)
        and type(vector["node_alignment"]) is int
        and vector["node_alignment"] in (0, 7, 31)
        and type(vector["transfer_profile"]) is int
        and vector["transfer_profile"] in (0, 4),
        "unreviewed factory callback tree source profile",
    )
    fixture = normal._resume(produced, _normal_vector(vector))
    cv = dict(
        fixture["callback_vector"],
        source_keys=list(reversed(SOURCE_KEYS[: vector["source_size"]])),
        node_alignment=vector["node_alignment"],
        previous_seh=factory._raw(fixture["pages"], 0),
    )
    prototype = empty._fixture(cv)
    pages = {p: bytearray(b) for p, b in fixture["pages"].items()}
    patches = list(fixture["patches"])
    fresh_pages = list(fixture["fresh_pages"])

    def put(address, value, width=4):
        for i, byte in enumerate(value.to_bytes(width, "little")):
            a = address + i
            p, off = a & ~4095, a & 4095
            if p not in pages:
                pages[p] = bytearray(b"\xa5" * 4096)
                fresh_pages.append(p)
            patches.append(dict(address=a, before=pages[p][off], after=byte))
            pages[p][off] = byte

    # The source's explicit links/marker/node/key bytes are supplied host state.
    # Neither original receiver nor allocated sentinel bytes are overwritten.
    for i in range(14):
        put(
            empty.SOURCE_HEAD + i,
            factory._raw(prototype["pages"], empty.SOURCE_HEAD + i, 1),
            1,
        )
    strings = {}
    key_bindings = []
    for i, address in enumerate(prototype["source_addresses"]):
        for j in range(24):
            put(address + j, factory._raw(prototype["pages"], address + j, 1), 1)
        old = factory._raw(prototype["pages"], address + 16)
        key_bytes = prototype["strings"][old]
        pointer = KEY_STORAGE + 32 * i + vector["node_alignment"] % 4
        _require(
            pointer > 0x1C000000 and pointer + len(key_bytes) <= 0x1C002000,
            "relocated source key extent differs",
        )
        put(address + 16, pointer)
        strings[pointer] = key_bytes
        key_bindings.append(
            dict(
                node=address,
                key_pointer=pointer,
                bytes=len(key_bytes),
                sha256=hashlib.sha256(key_bytes).hexdigest(),
            )
        )
        for j, byte in enumerate(key_bytes):
            put(pointer + j, byte, 1)
    prototype = dict(prototype, strings=strings)
    frozen = {p: bytes(b) for p, b in pages.items()}
    for start, size in (
        (normal.first.alignment.USERDATA, 72),
        (normal.first.alignment.RECORD, 24),
    ):
        _require(
            all(
                factory._raw(frozen, start + i, 1)
                == factory._raw(produced["pages"], start + i, 1)
                for i in range(size)
            ),
            "tree source host changed factory storage",
        )
    logical = callback.model.apply(
        prototype["source_state"],
        prototype["destination_state"],
        dict(records=[], capacity=0),
        source_pointer=fixture["source_pointer"],
        source_word=cv["source_word"],
        destination_word=cv["destination_word"],
        destination_refs=cv["destination_refs"],
        source_refs=cv["source_refs"],
        transfers=cv["transfers"],
        allow_growth=True,
    )
    return dict(
        fixture,
        pages=frozen,
        patches=patches,
        fresh_pages=fresh_pages,
        prototype=prototype,
        logical=logical,
        callback_vector=cv,
        key_bindings=key_bindings,
    )


def _logical(fixture, produced):
    cv = fixture["callback_vector"]
    return model.apply(
        source_state=fixture["prototype"]["source_state"],
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
        cookie=cv["cookie"],
        source_word=cv["source_word"],
        destination_word=cv["destination_word"],
        destination_refs=cv["destination_refs"],
        source_refs=cv["source_refs"],
        transfers=cv["transfers"],
    )


def _run_case(codes, points, fixture, produced, vector, negative=None, *, capture=None):
    logical = _logical(fixture, produced)
    _require(
        logical["tree_count"] == vector["source_size"],
        "factory source logical count differs",
    )
    observation = normal._run_case(
        codes,
        points,
        fixture,
        produced,
        vector,
        negative,
        logical=logical,
        capture=capture,
    )
    if negative == "cookie":
        return observation
    expected = callback._expected(
        fixture["callback_vector"], fixture, class_module=empty
    )
    child = next(c for c in expected["children"] if c["kind"] == "class")
    pages = expected["pages"]
    u, p = fixture["receiver"], produced["fixture"]["record"]
    _require(
        len(observation["allocations"]) == vector["source_size"] + 1
        and [a["request"] for a in observation["allocations"]]
        == [24] * vector["source_size"] + [8],
        "factory source allocation partition differs",
    )
    _require(
        all(
            factory._raw(pages, u + o) == factory._raw(produced["pages"], u + o)
            for o in logical["normal_preserved_userdata_offsets"]
        )
        and all(
            factory._raw(pages, p + i, 1) == factory._raw(produced["pages"], p + i, 1)
            for i in logical["sentinel_preserved_offsets"]
        ),
        "factory source independent preservation differs",
    )
    nodes = child["result"]["destination_addresses"]
    at = lambda i: p if i is None else nodes[i]
    links = logical["sentinel_link_ids"]
    _require(
        [factory._raw(pages, p + o) for o in (0, 4, 8)]
        == [at(links["leftmost"]), at(links["root"]), at(links["rightmost"])],
        "factory source independent sentinel links differ",
    )
    _require(
        child["result"]["insertions"]
        == [
            dict(
                source=c["source"],
                key=c["key"],
                destination_address=nodes[c["destination"]],
                inserted=True,
                mode="empty" if i == 0 else "end",
                payload=c["payload"],
                heap_node=nodes[c["destination"]],
            )
            for i, c in enumerate(logical["class_transfer"]["copies"])
        ],
        "factory source independent copy routing differs",
    )
    return dict(
        observation,
        key_bindings_sha256=_canonical_sha256(fixture["key_bindings"]),
        tree_nodes=vector["source_size"],
        tree_heap_bytes=24 * vector["source_size"],
    )


def _preflight(sources):
    _require(
        set(sources) == set(SOURCE_PINS),
        "factory callback tree source partition differs",
    )
    return {
        k: factory._source_identity(sources[k], *pin, k)
        for k, pin in SOURCE_PINS.items()
    }


CONTROLS = {
    **normal.CONTROLS,
    **{
        k: "factory return tree heap ABI differs"
        for k in ("tree_request", "tree_register", "tree_flags")
    },
}


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = full._load_executable(Path(executable))
    _require(
        digest == full.EXE_SHA256 and image.image_base == BASE,
        "exact factory callback tree executable differs",
    )
    payload, fp, continuation, codes, points = normal._load_code(data, image, sources)
    observations, producer = [], []
    sample = None
    for vector in vectors():
        nv = _normal_vector(vector)
        produced, observation = normal.first._produce(
            payload, fp, continuation, normal._first_vector(nv)
        )
        fixture = _resume(produced, vector)
        observations.append(_run_case(codes, points, fixture, produced, vector))
        producer.append(observation)
        if (
            vector["profile"] == 1
            and vector["source_size"] == 7
            and vector["node_alignment"] == 31
            and vector["transfer_profile"] == 4
        ):
            sample = (produced, fixture, vector)
    controls = []
    for kind, reason in CONTROLS.items():
        try:
            _run_case(codes, points, sample[1], sample[0], sample[2], kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "factory callback tree incidental control: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("factory callback tree control survived: " + kind)
    failure = _run_case(codes, points, sample[1], sample[0], sample[2], "cookie")
    _require(
        failure == dict(kind="cookie", rejected=True, endpoint="0x003574d5"),
        "factory tree cookie failure differs",
    )
    controls.append(dict(failure, kind="native_callback_cookie"))
    union = sorted({r for o in observations for r in o["trace_rvas"]})
    base = sources["factory_callback_return"]["normal_site_partition"]
    parent = set(base["callback"])
    markers = set(base["markers"])
    tables = set(base["tables"])
    class_sites = set(union) - parent - markers - tables
    selected = {p["rva"] for p in points}
    _require(
        set(base["empty_class"]) <= class_sites
        and set(union) <= selected
        and not any(
            a <= int(r, 16) < b for r in union for a, b in normal.PARENT_EXCLUDED
        ),
        "factory callback tree normal site partition differs",
    )
    families = {
        str(n): dict(
            cases=sum(v["source_size"] == n for v in vectors()),
            executed_rvas=sorted(
                {
                    r
                    for o in observations
                    if o["vector"]["source_size"] == n
                    for r in o["trace_rvas"]
                }
            ),
        )
        for n in (0, 1, 3, 7)
    }
    _require(
        set(families["0"]["executed_rvas"])
        == set(sources["factory_callback_return"]["executed_rvas"]),
        "factory empty-source predecessor coverage differs",
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
        executed_rvas=union,
        families=families,
        normal_site_partition=dict(
            callback=sorted(parent),
            class_operation=sorted(class_sites),
            markers=sorted(markers),
            tables=sorted(tables),
            excluded=sorted(selected - set(union)),
        ),
        negative_controls=controls,
        observations_sha256=_canonical_sha256(observations),
        producer_observations_sha256=_canonical_sha256(producer),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=len(observations),
            static_sites=len(points),
            executed_sites=len(union),
            instruction_bytes=len(
                {a + i for a, b in codes.items() for i in range(len(b))}
            ),
            factory_instructions=sum(len(o["trace_rvas"]) for o in producer),
            callback_instructions=sum(len(o["trace_rvas"]) for o in observations),
            factory_api_calls=34 * len(observations),
            callback_api_calls=sum(o["api_calls"] for o in observations),
            factory_heap_calls=len(observations),
            class_heap_calls=sum(len(o["allocations"]) for o in observations),
            tree_nodes=sum(o["tree_nodes"] for o in observations),
            tree_heap_bytes=sum(o["tree_heap_bytes"] for o in observations),
            vector_heap_calls=len(observations),
            marker_calls=2 * len(observations),
            table_calls=2 * len(observations),
            requested_assignments=sum(
                sum(map(len, o["assignments"])) for o in observations
            ),
            retained_lua_values=5,
            result_count=0,
            free_calls=0,
            controls=len(controls),
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            continuous_factory=True,
            continuous_callback_and_all_helpers=True,
            continuous_across_host=False,
            checked=[
                "Actual factory initially empty destination retains sentinel marker padding references names and context",
                "Supplied reversed source tree copied in sorted key order with actual native insertion balancing and successor instructions",
                "Relocated key strings retain source payload routing and avoid producer name storage",
                "Identity bound Lua requests complete native pages ordered events normal return and allocation partition",
            ],
            premises=[
                "Explicit supplied host closure source nodes key bytes class word and registry references",
                "Successful bounded tree and vector heap responses and compatible Lua registry table responses",
                "Initially empty destination source population zero one three or seven",
            ],
            excluded=[
                "Arbitrary destination insertion orders unexecuted balancing arms and existing key updates",
                "Real Lua VM registry table metamethod and ownership effects",
                "Heap ownership assertion handler delivery and global accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory callback tree executable changed",
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
        "sealed factory callback tree differs",
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
        "exact factory callback tree differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


encode_conformance = normal.encode_conformance
