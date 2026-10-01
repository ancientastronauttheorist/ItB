"""Fourth callback on retained factory receiver and three-record vector."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from src.observatory import native_lua_class_factory_callback_third_conformance as third
from src.observatory import native_lua_class_factory_callback_fourth_semantics as model

tree, extend, repeat, old = third.tree, third.extend, third.repeat, third.old
normal, full, factory, callback = (
    third.normal,
    third.full,
    third.factory,
    third.callback,
)
BASE, ConformanceError, _require = third.BASE, third.ConformanceError, third._require
_canonical_sha256, _canonical_bytes = third._canonical_sha256, third._canonical_bytes
ANALYSIS_KIND = "pe_native_lua_class_factory_callback_fourth_conformance"
SEALED_SHA256 = "3b0727908ddef36b171733a0c686e0ad2dbe1a08ac3e7937834cd9158feced5a"
SOURCE_PINS = {
    **third.SOURCE_PINS,
    "factory_callback_third": (third.ANALYSIS_KIND, third.SEALED_SHA256),
}


def vectors():
    return third.vectors()


def _produce_third(payload, fp, continuation, codes, points, vector):
    produced, producer, f1, cap1, f2, cap2 = third._produce_second(
        payload, fp, continuation, codes, points, vector
    )
    f3 = third._resume(produced, f2, cap2, vector)
    cap3 = {}

    def capture(machine, ids, expected, lua):
        cap3.update(
            pages={page: bytes(machine.mem_read(page, 4096)) for page in f3["pages"]},
            registers={
                register: machine.reg_read(identity)
                for register, identity in ids.items()
            },
        )

    cap3["observation"] = third._run_case(
        codes, points, f3, produced, vector, capture=capture
    )
    return produced, producer, f1, cap1, f2, cap2, f3, cap3


def _prior(fixture):
    return model.third_model.apply(
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


def _check_third(produced, third_fixture, captured):
    observation = captured["observation"]
    _require(
        captured["registers"] == observation["registers"]
        and repeat._page_sha(captured["pages"]) == observation["memory_sha256"],
        "verified third callback capture differs",
    )
    prior = _prior(third_fixture)
    prototype = third_fixture["prototype"]
    new_base = old.construction.DATA + 0x3000
    _require(
        new_base in captured["pages"]
        and new_base in third_fixture["pages"]
        and len(captured["pages"][new_base]) == 4096
        and captured["pages"][new_base] == third_fixture["pages"][new_base],
        "retained third callback differs",
    )
    # The sole third request is twenty-four bytes for the vector. Destination
    # nodes are retained identities, never reconstructed from that allocation.
    nodes = list(prototype["destination_addresses"])
    allocations = observation["allocations"]
    _require(
        len(nodes) == prior["tree_count"] == 8
        and len(allocations) == 1
        and allocations[0]["request"] == 24
        and allocations[0]["node"] == third_fixture["vector_begin"],
        "retained third callback differs",
    )
    _require(
        observation["frees"]
        == [
            dict(
                pointer=third_fixture["second_vector_pointer"],
                entry_esp=third_fixture["entry"] - 180,
                result=1,
                continuation=0x00789172,
            )
        ],
        "retained third callback differs",
    )
    state = prior["class_transfer"]["destination"]
    sentinel = produced["fixture"]["record"]
    at = lambda identity: sentinel if identity is None else nodes[identity]
    pointers = {
        node["key"]: factory._raw(third_fixture["pages"], address + 16)
        for node, address in zip(prototype["destination_state"]["tree"]["nodes"], nodes)
    }
    pages = captured["pages"]
    links, updates = prior["sentinel_link_ids"], prior["normal_field_updates"]
    receiver, source_pointer = (
        third_fixture["receiver"],
        third_fixture["source_pointer"],
    )
    _require(
        captured["registers"] == prior["full_return"]["registers"]
        and [factory._raw(pages, sentinel + offset) for offset in (0, 4, 8)]
        == [at(links[field]) for field in ("leftmost", "root", "rightmost")]
        and all(
            factory._raw(pages, sentinel + offset, 1)
            == factory._raw(third_fixture["pages"], sentinel + offset, 1)
            for offset in range(12, 24)
        )
        and all(
            factory._raw(pages, receiver + offset)
            == updates.get(
                offset, factory._raw(third_fixture["pages"], receiver + offset)
            )
            for offset in range(0, 72, 4)
        ),
        "retained third callback differs",
    )
    _require(
        all(
            [factory._raw(pages, address + offset) for offset in (0, 4, 8, 16, 20)]
            == [
                at(node["left"]),
                at(node["parent"]),
                at(node["right"]),
                pointers[node["key"]],
                state["payloads"][identity],
            ]
            and factory._raw(pages, address + 12, 1) == node["color"]
            and factory._raw(pages, address + 13, 1) == 0
            and all(
                factory._raw(pages, address + offset, 1)
                == factory._raw(third_fixture["pages"], address + offset, 1)
                for offset in (14, 15)
            )
            for identity, (address, node) in enumerate(
                zip(nodes, state["tree"]["nodes"])
            )
        )
        and all(
            factory._raw(pages, pointer + offset, 1) == byte
            for pointer, value in prototype["strings"].items()
            for offset, byte in enumerate(value)
        ),
        "retained third callback differs",
    )
    _require(
        all(
            [factory._raw(pages, pointer + 4 * index) for index in range(2 * count)]
            == [0, source_pointer] * count
            for pointer, count in (
                (third_fixture["vector_begin"], 3),
                (third_fixture["second_vector_pointer"], 2),
                (third_fixture["first_arguments"]["vector_pointer"], 1),
            )
        )
        and all(
            factory._raw(pages, address)
            == factory._raw(third_fixture["pages"], address)
            for address in (0, 0x00893F28)
        ),
        "retained third callback differs",
    )
    return prior, nodes


def _resume(produced, third_fixture, captured, vector):
    prior, nodes = _check_third(produced, third_fixture, captured)
    new_base = old.construction.DATA + 0x3000
    _require(
        new_base in captured["pages"] and len(captured["pages"][new_base]) == 4096,
        "fourth captured allocation page differs",
    )
    current = dict(produced, pages=captured["pages"], registers=captured["registers"])
    fixture = normal.first.entry._resume(
        current,
        tree._normal_vector(extend._base_vector(vector)),
        callback_entry=third_fixture["entry"],
    )
    pages = {page: bytearray(payload) for page, payload in fixture["pages"].items()}
    patches = list(fixture["patches"])

    def put(address, value):
        for offset, byte in enumerate(value.to_bytes(4, "little")):
            absolute = address + offset
            page, index = absolute & ~4095, absolute & 4095
            patches.append(
                dict(address=absolute, before=pages[page][index], after=byte)
            )
            pages[page][index] = byte

    source_state = copy.deepcopy(third_fixture["prototype"]["source_state"])
    for identity, address in enumerate(third_fixture["prototype"]["source_addresses"]):
        source_state["payloads"][identity] ^= 0xFFFFFFFF
        put(address + 20, source_state["payloads"][identity])
    cv = copy.deepcopy(third_fixture["callback_vector"])
    cv.update(old_size=3, old_alignment=0)
    new_begin = new_base + 0x800 + vector["vector_alignment"]
    prototype = dict(
        copy.deepcopy(third_fixture["prototype"]),
        source_state=source_state,
        destination_state=copy.deepcopy(prior["class_transfer"]["destination"]),
        destination_addresses=nodes,
        old_begin=third_fixture["vector_begin"],
        old_size=3,
        old_base=third_fixture["vector_begin"] & ~4095,
        new_base=new_base,
        new_page_count=1,
        vector_begin=new_begin,
        vector_end=new_begin + 24,
        vector_capacity=new_begin + 32,
        node=old.construction.DATA + 0x600 + 31,
    )
    prototype["transfer"] = old.prefix.model.transfer(
        source_state, prototype["destination_state"]
    )
    logical = callback.model.apply(
        source_state,
        prototype["destination_state"],
        dict(records=[[0, third_fixture["source_pointer"]]] * 3, capacity=3),
        source_pointer=third_fixture["source_pointer"],
        source_word=cv["source_word"],
        destination_word=cv["source_word"],
        source_refs=cv["source_refs"],
        destination_refs=cv["destination_refs"],
        transfers=cv["transfers"],
        allow_growth=True,
    )
    frozen = {page: bytes(payload) for page, payload in pages.items()}
    retained = (
        [
            (fixture["receiver"], 72),
            (produced["fixture"]["record"], 24),
            (third_fixture["vector_begin"], 24),
            (third_fixture["second_vector_pointer"], 16),
            (third_fixture["first_arguments"]["vector_pointer"], 8),
            (0, 4),
            (0x00893F28, 4),
        ]
        + [(address, 24) for address in nodes]
        + [(pointer, len(value)) for pointer, value in prototype["strings"].items()]
    )
    _require(
        all(
            factory._raw(frozen, address + offset, 1)
            == factory._raw(captured["pages"], address + offset, 1)
            for address, width in retained
            for offset in range(width)
        ),
        "fourth host changed retained storage",
    )
    _require(
        frozen[new_base] == captured["pages"][new_base],
        "fourth host changed captured allocation page",
    )
    return dict(
        fixture,
        pages=frozen,
        patches=patches,
        prototype=prototype,
        logical=logical,
        callback_vector=cv,
        source_pointer=third_fixture["source_pointer"],
        endpoint=callback.RETURN,
        vector_begin=new_begin,
        first_arguments=copy.deepcopy(third_fixture["first_arguments"]),
        second_source_state=copy.deepcopy(third_fixture["second_source_state"]),
        second_vector_pointer=third_fixture["second_vector_pointer"],
        second_entry=third_fixture["second_entry"],
        second_registers=copy.deepcopy(third_fixture["second_registers"]),
        third_source_state=copy.deepcopy(third_fixture["prototype"]["source_state"]),
        third_vector_pointer=third_fixture["vector_begin"],
        third_entry=third_fixture["entry"],
        third_registers=copy.deepcopy(third_fixture["registers"]),
        captured_pages_sha256=repeat._page_sha(captured["pages"]),
    )


def _logical(fixture):
    return model.apply(
        first_arguments=fixture["first_arguments"],
        second_source_state=fixture["second_source_state"],
        second_vector_pointer=fixture["second_vector_pointer"],
        second_entry=fixture["second_entry"],
        second_registers=fixture["second_registers"],
        third_source_state=fixture["third_source_state"],
        third_vector_pointer=fixture["third_vector_pointer"],
        third_entry=fixture["third_entry"],
        third_registers=fixture["third_registers"],
        fourth_source_state=fixture["prototype"]["source_state"],
        new_vector_pointer=fixture["vector_begin"],
        fourth_entry=fixture["entry"],
        fourth_registers=fixture["registers"],
    )["fourth"]


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
    child = next(row for row in expected["children"] if row["kind"] == "class")[
        "result"
    ]
    _require(
        child["tree_heap_count"] == 0
        and [row["request"] for row in result["allocations"]] == [32]
        and len(result["frees"]) == 1
        and result["frees"][0]["pointer"] == fixture["third_vector_pointer"],
        "fourth allocation free partition differs",
    )
    nodes = fixture["prototype"]["destination_addresses"]
    _require(
        child["destination_addresses"] == nodes
        and child["insertions"]
        == [
            dict(
                source=copy["source"],
                key=copy["key"],
                destination_address=nodes[copy["destination"]],
                inserted=False,
                mode="existing",
                payload=copy["payload"],
                heap_node=None,
            )
            for copy in logical["class_transfer"]["copies"]
        ],
        "fourth independent existing routing differs",
    )
    final, entry_pages = expected["pages"], fixture["pages"]
    sentinel, receiver = produced["fixture"]["record"], fixture["receiver"]
    _require(
        all(
            factory._raw(final, sentinel + offset, 1)
            == factory._raw(entry_pages, sentinel + offset, 1)
            for offset in range(24)
        )
        and factory._raw(final, receiver + 56) == logical["tree_count"] == 8
        and all(
            factory._raw(final, receiver + offset)
            == factory._raw(entry_pages, receiver + offset)
            for offset in logical["normal_preserved_userdata_offsets"]
        ),
        "fourth independent preserved fields differ",
    )
    selected = {copy["destination"] for copy in logical["class_transfer"]["copies"]}
    _require(
        all(
            all(
                factory._raw(final, address + offset, 1)
                == factory._raw(entry_pages, address + offset, 1)
                for offset in range(20)
            )
            and (
                identity in selected
                or factory._raw(final, address + 20)
                == factory._raw(entry_pages, address + 20)
            )
            for identity, address in enumerate(nodes)
        ),
        "fourth retained key or omitted payload differs",
    )
    _require(
        [factory._raw(final, fixture["vector_begin"] + 4 * index) for index in range(8)]
        == [0, fixture["source_pointer"]] * 4
        and all(
            factory._raw(final, pointer + offset, 1)
            == factory._raw(entry_pages, pointer + offset, 1)
            for pointer, width in (
                (fixture["third_vector_pointer"], 24),
                (fixture["second_vector_pointer"], 16),
                (fixture["first_arguments"]["vector_pointer"], 8),
            )
            for offset in range(width)
        )
        and all(
            factory._raw(final, fixture["vector_begin"] + offset, 1)
            == factory._raw(entry_pages, fixture["third_vector_pointer"] + offset, 1)
            for offset in range(24)
        ),
        "fourth independent retained vector copies differ",
    )
    new_base = fixture["prototype"]["new_base"]
    _require(
        all(
            final[new_base][offset] == entry_pages[new_base][offset]
            for offset in range(4096)
            if not fixture["vector_begin"] - new_base
            <= offset
            < fixture["vector_begin"] - new_base + 32
        ),
        "fourth allocation page outside vector differs",
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
    _require(
        set(sources) == set(SOURCE_PINS), "factory fourth source partition differs"
    )
    return {
        key: factory._source_identity(sources[key], *pin, key)
        for key, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    return third._load_code(data, image, sources)


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = full._load_executable(Path(executable))
    _require(
        digest == full.EXE_SHA256 and image.image_base == BASE,
        "exact factory fourth executable differs",
    )
    payload, fp, continuation, codes, points = _load_code(data, image, sources)
    firsts, seconds, thirds, fourths, producers = [], [], [], [], []
    sample = None
    for vector in vectors():
        produced, producer, f1, cap1, f2, cap2, f3, cap3 = _produce_third(
            payload, fp, continuation, codes, points, vector
        )
        fixture = _resume(produced, f3, cap3, vector)
        firsts.append(cap1["observation"])
        seconds.append(cap2["observation"])
        thirds.append(cap3["observation"])
        fourths.append(_run_case(codes, points, fixture, produced, vector))
        producers.append(producer)
        if (
            vector["profile"] == 1
            and vector["first_key_profile"] == 1
            and vector["transfer_profile"] == 4
        ):
            sample = (produced, f3, cap3, fixture, vector)
    controls = []
    for kind, reason in CONTROLS.items():
        try:
            _run_case(codes, points, sample[3], sample[0], sample[4], kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "fourth incidental control: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("fourth control survived: " + kind)
    failure = _run_case(codes, points, sample[3], sample[0], sample[4], "cookie")
    _require(
        failure == dict(kind="cookie", rejected=True, endpoint="0x003574d5"),
        "fourth cookie failure differs",
    )
    controls.append(dict(failure, kind="native_callback_cookie"))
    for kind in ("capture_pages", "capture_registers"):
        captured = copy.deepcopy(sample[2])
        if kind == "capture_registers":
            captured["registers"]["eax"] ^= 1
        else:
            address = sample[1]["vector_begin"]
            page = address & ~4095
            changed = bytearray(captured["pages"][page])
            changed[address & 4095] ^= 1
            captured["pages"][page] = bytes(changed)
        try:
            _resume(sample[0], sample[1], captured, sample[4])
        except ConformanceError as exc:
            _require(
                str(exc) == "verified third callback capture differs",
                "fourth capture incidental rejection",
            )
            controls.append(dict(kind=kind, rejected=True, reason=str(exc)))
        else:
            raise ConformanceError("fourth capture control survived")
    for kind in (
        "retained_key_pointer",
        "retained_payload",
        "retained_key_bytes",
        "retained_link",
    ):
        captured = copy.deepcopy(sample[2])
        node = sample[1]["prototype"]["destination_addresses"][0]
        address = (
            factory._raw(captured["pages"], node + 16)
            if kind == "retained_key_bytes"
            else node
            + {"retained_key_pointer": 16, "retained_payload": 20, "retained_link": 0}[
                kind
            ]
        )
        page = address & ~4095
        changed = bytearray(captured["pages"][page])
        changed[address & 4095] ^= 1
        captured["pages"][page] = bytes(changed)
        captured["observation"]["memory_sha256"] = repeat._page_sha(captured["pages"])
        try:
            _resume(sample[0], sample[1], captured, sample[4])
        except ConformanceError as exc:
            _require(
                str(exc) == "retained third callback differs",
                "fourth retained control incidental rejection",
            )
            controls.append(dict(kind=kind, rejected=True, reason=str(exc)))
        else:
            raise ConformanceError("fourth retained control survived")
    first_sites, second_sites, third_sites, fourth_sites = (
        sorted({rva for observation in group for rva in observation["trace_rvas"]})
        for group in (firsts, seconds, thirds, fourths)
    )
    union = sorted(
        set(first_sites) | set(second_sites) | set(third_sites) | set(fourth_sites)
    )
    selected = {point["rva"] for point in points}
    predecessor = sources["factory_callback_third"]
    _require(
        first_sites == predecessor["first_executed_rvas"]
        and second_sites == predecessor["second_executed_rvas"]
        and third_sites == predecessor["third_executed_rvas"]
        and set(union) <= selected
        and not any(
            start <= int(rva, 16) < end
            for rva in union
            for start, end in normal.PARENT_EXCLUDED
        ),
        "fourth normal site partition differs",
    )
    base = sources["factory_callback_tree"]["normal_site_partition"]
    parent, markers, tables = (
        set(base[key]) for key in ("callback", "markers", "tables")
    )
    count = len(fourths)
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{start:08x}",
                    end_rva=f"0x{start + len(body):08x}",
                    sha256=hashlib.sha256(body).hexdigest(),
                )
                for start, body in sorted(codes.items())
            ],
            points=points,
        ),
        vectors=vectors(),
        executed_rvas=union,
        first_executed_rvas=first_sites,
        second_executed_rvas=second_sites,
        third_executed_rvas=third_sites,
        fourth_executed_rvas=fourth_sites,
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
        third_observations_sha256=_canonical_sha256(thirds),
        fourth_observations_sha256=_canonical_sha256(fourths),
        producer_observations_sha256=_canonical_sha256(producers),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=count,
            callback_invocations=4 * count,
            static_sites=len(points),
            executed_sites=len(union),
            instruction_bytes=len(
                {
                    start + offset
                    for start, body in codes.items()
                    for offset in range(len(body))
                }
            ),
            factory_instructions=sum(
                len(observation["trace_rvas"]) for observation in producers
            ),
            first_callback_instructions=sum(
                len(observation["trace_rvas"]) for observation in firsts
            ),
            second_callback_instructions=sum(
                len(observation["trace_rvas"]) for observation in seconds
            ),
            third_callback_instructions=sum(
                len(observation["trace_rvas"]) for observation in thirds
            ),
            fourth_callback_instructions=sum(
                len(observation["trace_rvas"]) for observation in fourths
            ),
            factory_api_calls=34 * count,
            callback_api_calls=sum(
                observation["api_calls"]
                for observation in firsts + seconds + thirds + fourths
            ),
            factory_heap_calls=count,
            first_class_heap_calls=sum(
                len(observation["allocations"]) for observation in firsts
            ),
            second_class_heap_calls=sum(
                len(observation["allocations"]) for observation in seconds
            ),
            third_class_heap_calls=sum(
                len(observation["allocations"]) for observation in thirds
            ),
            fourth_class_heap_calls=sum(
                len(observation["allocations"]) for observation in fourths
            ),
            first_tree_nodes=sum(vector["source_size"] for vector in vectors()),
            second_tree_allocations=sum(
                observation["new_tree_nodes"] for observation in seconds
            ),
            second_payload_updates=sum(
                observation["existing_payload_updates"] for observation in seconds
            ),
            third_payload_updates=sum(
                observation["payload_updates"] for observation in thirds
            ),
            fourth_payload_updates=sum(
                observation["payload_updates"] for observation in fourths
            ),
            third_tree_allocations=0,
            fourth_tree_allocations=0,
            second_source_copies=sum(
                observation["source_copies"] for observation in seconds
            ),
            final_tree_nodes=sum(
                observation["final_tree_count"] for observation in seconds
            ),
            second_copied_old_vector_bytes=8 * count,
            third_copied_old_vector_bytes=16 * count,
            fourth_copied_old_vector_bytes=24 * count,
            second_vector_bytes=16 * count,
            third_vector_bytes=24 * count,
            fourth_vector_bytes=32 * count,
            free_calls=3 * count,
            marker_calls=8 * count,
            table_calls=8 * count,
            requested_assignments=sum(
                sum(map(len, observation["assignments"]))
                for observation in firsts + seconds + thirds + fourths
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
                "Actual factory receiver and verified first second and third return pages retained across explicit host invocations",
                "Verified third capture retains existing IDs omitted payloads sentinel links original key strings all earlier vector bytes FS and cookie before fourth payload update",
                "Captured separate fourth allocation page is preserved until native allocation and only the thirty-two-byte vector changes there",
                "Native three-record old vector grows to capacity four with twenty-four-byte copy successful free response append and all four normal returns",
            ],
            premises=[
                "Explicit host invocations source topology and payloads free import binding repeated source word registry and finite transfer responses",
                "Successful disjoint bounded tree and vector allocations and free responses with retained freed bytes",
            ],
            excluded=[
                "New fourth pass keys other source recipes more than four callbacks and native unions larger than eight",
                "Real Lua VM ownership invalidation allocator reuse assertion delivery and global accounting",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory fourth executable changed",
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
        "sealed factory fourth differs",
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
        "exact factory fourth differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


encode_conformance = normal.encode_conformance
