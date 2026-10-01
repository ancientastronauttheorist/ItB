"""Independent retained-capture laws; exact native replay stays CLI gated."""

import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.observatory import native_lua_class_factory_callback_repeat_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_callback_repeat_conformance.py"
CANONICAL = "b4b28a9a2f8675705257af3a100f50b72082d1c543a12aff2a5d76e17950966e"
RAW = "b2999b07fe273580a4c49a93ec87a008db9decf2e1e67449ab4ed86665094355"
U, P, SOURCE = 0x0FFFFFCC, 0x10000100, 0x14000000
KEYS = (0, 1, 16, 255, 0x80000000, 0xFFFFFFFE, 0xFFFFFFFF)


def span(pages, address, width):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(width)
    )


def raw(pages, address, width=4):
    return int.from_bytes(span(pages, address, width), "little")


def change(pages, address, value, width=4):
    result = dict(pages)
    for offset, byte in enumerate(value.to_bytes(width, "little")):
        page = (address + offset) & ~4095
        payload = bytearray(result[page])
        payload[(address + offset) & 4095] = byte
        result[page] = bytes(payload)
    return result


def page_sha(pages):
    return c._canonical_sha256(
        {
            str(page): hashlib.sha256(payload).hexdigest()
            for page, payload in pages.items()
        }
    )


@pytest.fixture(scope="module")
def cases():
    # The capture below is an explicitly synthetic physical-law packet. Only
    # the gated CLI invokes native instructions and verifies a real capture.
    producers, result = {}, []
    for vector in c.vectors():
        profile = vector["profile"]
        if (
            vector["length"] != (0, 255)[profile]
            or vector["registry_profile"] != (0, 2)[profile]
        ):
            continue
        pv = {
            key: value
            for key, value in vector.items()
            if key
            not in (
                "source_size",
                "node_alignment",
                "transfer_profile",
                "vector_alignment",
            )
        }
        key = tuple(sorted(pv.items()))
        if key not in producers:
            base = c.full.record._base_vector(c.full._record_vector(pv))
            fixture = c.normal.first.alignment.install(pv, c.factory._fixture(base))
            physical = c.full._extend_expected(
                pv, fixture, c.factory._expected(base, fixture)
            )
            producers[key] = dict(
                fixture=fixture,
                pages=physical["pages"],
                registers=physical["registers"],
                lua_result=physical["lua_result"],
                closure=("closure", 0x006EC110, ("userdata", U)),
            )
        produced = producers[key]
        first_fixture = c.tree._resume(produced, vector)
        first_expected = c.callback._expected(
            first_fixture["callback_vector"], first_fixture, class_module=c.tree.empty
        )
        child = next(
            row for row in first_expected["children"] if row["kind"] == "class"
        )
        nodes = child["result"]["destination_addresses"]
        capture = dict(
            pages=copy.deepcopy(first_expected["pages"]),
            registers=copy.deepcopy(first_expected["registers"]),
        )
        capture["observation"] = dict(
            registers=copy.deepcopy(capture["registers"]),
            memory_sha256=page_sha(capture["pages"]),
            allocations=[dict(node=node, request=24) for node in nodes]
            + [dict(node=first_fixture["vector_begin"], request=8)],
        )
        fixture = c._resume(produced, first_fixture, capture, vector)
        expected = c.callback._expected(
            fixture["callback_vector"], fixture, class_module=c.old
        )
        result.append(
            (
                vector,
                produced,
                first_fixture,
                first_expected,
                capture,
                fixture,
                expected,
            )
        )
    assert len(producers) == 2 and len(result) == 48
    return result


def test_exact_432_case_product_with_two_invocations_and_node_alignment31():
    vectors = c.vectors()
    assert len(vectors) == 432 and all(
        vector["node_alignment"] == 31 for vector in vectors
    )
    assert (
        len(
            {
                tuple(
                    sorted(
                        c.normal._first_vector(c.tree._normal_vector(vector)).items()
                    )
                )
                for vector in vectors
            }
        )
        == 54
    )
    counts = {}
    for vector in vectors:
        group = vector["source_size"], vector["transfer_profile"]
        counts[group] = counts.get(group, 0) + 1
    assert counts == {group: 54 for group in itertools.product((0, 1, 3, 7), (0, 4))}
    assert {vector["vector_alignment"] for vector in vectors} == {0, 7, 31}
    assert {vector["profile"] for vector in vectors} == {0, 1}
    assert {vector["length"] for vector in vectors} == {0, 16, 255}
    assert {vector["registry_profile"] for vector in vectors} == {0, 1, 2}
    assert sum(vector["source_size"] for vector in vectors) == 1188


def test_capture_registers_and_every_page_digest_match_before_second_host(cases):
    for _, _, _, expected, capture, fixture, _ in cases:
        assert (
            capture["registers"]
            == expected["registers"]
            == capture["observation"]["registers"]
        )
        assert capture["pages"] == expected["pages"]
        assert (
            page_sha(capture["pages"])
            == capture["observation"]["memory_sha256"]
            == fixture["captured_pages_sha256"]
        )
        assert fixture["registers"] == dict(capture["registers"], esp=fixture["entry"])


@pytest.mark.parametrize(
    "register", ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
)
def test_each_corrupted_captured_gpr_rejected_before_host_patches(
    cases, monkeypatch, register
):
    vector, produced, first_fixture, _, capture, _, _ = cases[-1]
    corrupted = copy.deepcopy(capture)
    corrupted["registers"][register] ^= 1
    before = copy.deepcopy(corrupted)
    reached = []

    def forbidden(*args, **kwargs):
        reached.append(True)
        raise AssertionError("host binder reached before capture rejection")

    monkeypatch.setattr(c.normal.first.entry, "_resume", forbidden)
    with pytest.raises(RuntimeError, match="verified callback capture differs"):
        c._resume(produced, first_fixture, corrupted, vector)
    assert corrupted == before and reached == []


@pytest.mark.parametrize(
    "region",
    ["userdata", "sentinel", "old_vector", "source_payload", "key", "stack", "fs"],
)
def test_corrupted_captured_page_rejected_before_host_patches(
    cases, monkeypatch, region
):
    vector, produced, first_fixture, _, capture, _, _ = cases[-1]
    node = first_fixture["prototype"]["source_addresses"][0]
    address = dict(
        userdata=U,
        sentinel=P + 14,
        old_vector=first_fixture["vector_begin"],
        source_payload=node + 20,
        key=raw(capture["pages"], node + 16),
        stack=first_fixture["entry"] - 12,
        fs=0,
    )[region]
    corrupted = copy.deepcopy(capture)
    corrupted["pages"] = change(
        corrupted["pages"], address, raw(corrupted["pages"], address, 1) ^ 1, 1
    )
    before = copy.deepcopy(corrupted)
    reached = []

    def forbidden(*args, **kwargs):
        reached.append(True)
        raise AssertionError("host binder reached before capture rejection")

    monkeypatch.setattr(c.normal.first.entry, "_resume", forbidden)
    with pytest.raises(RuntimeError, match="verified callback capture differs"):
        c._resume(produced, first_fixture, corrupted, vector)
    assert corrupted == before and reached == []


def test_second_host_patch_replay_payload_flip_and_named_free_import(cases):
    for vector, produced, first_fixture, _, capture, fixture, _ in cases:
        current = dict(produced, pages=capture["pages"], registers=capture["registers"])
        boundary = c.normal.first.entry._resume(
            current,
            c.tree._normal_vector(vector),
            callback_entry=first_fixture["entry"],
        )
        assert fixture["patches"][: len(boundary["patches"])] == boundary["patches"]
        extra = fixture["patches"][len(boundary["patches"]) :]
        addresses = first_fixture["prototype"]["source_addresses"]
        assert [row["address"] for row in extra] == [
            c.old.growth.FREE_IAT + i for i in range(4)
        ] + [node + 20 + i for node in addresses for i in range(4)]
        replay = {
            page: bytearray(payload) for page, payload in capture["pages"].items()
        }
        for row in fixture["patches"]:
            page, offset = row["address"] & ~4095, row["address"] & 4095
            replay.setdefault(page, bytearray(b"\xa5" * 4096))
            assert replay[page][offset] == row["before"]
            replay[page][offset] = row["after"]
        assert {page: bytes(payload) for page, payload in replay.items()} == fixture[
            "pages"
        ]
        assert (
            raw(fixture["pages"], c.old.growth.FREE_IAT) == c.normal.layout.HEAP_TARGET
        )
        for index, node in enumerate(addresses):
            old_payload = raw(capture["pages"], node + 20)
            assert raw(fixture["pages"], node + 20) == old_payload ^ 0xFFFFFFFF
            assert (
                fixture["prototype"]["source_state"]["payloads"][index]
                == old_payload ^ 0xFFFFFFFF
            )
            assert span(fixture["pages"], node, 20) == span(capture["pages"], node, 20)
        touched = {row["address"] for row in fixture["patches"]}
        for page, payload in capture["pages"].items():
            assert all(
                fixture["pages"][page][index] == byte
                for index, byte in enumerate(payload)
                if page + index not in touched
            )


def test_retained_receiver_sentinel_old_vector_fs_cookie_and_key_bytes(cases):
    for vector, produced, first_fixture, _, capture, fixture, expected in cases:
        old_begin = first_fixture["vector_begin"]
        for address, width in ((U, 72), (P, 24), (old_begin, 8)):
            assert span(fixture["pages"], address, width) == span(
                capture["pages"], address, width
            )
        assert span(expected["pages"], P, 24) == span(capture["pages"], P, 24)
        assert span(expected["pages"], old_begin, 8) == span(
            capture["pages"], old_begin, 8
        )
        cv = fixture["callback_vector"]
        assert (
            cv["previous_seh"] == raw(fixture["pages"], 0) == raw(capture["pages"], 0)
        )
        assert raw(expected["pages"], 0) == raw(capture["pages"], 0)
        assert cv["cookie"] == raw(capture["pages"], 0x00893F28)
        for field in ("source_word", "source_refs", "destination_refs", "transfers"):
            assert cv[field] == first_fixture["callback_vector"][field]
        assert raw(fixture["pages"], U) == cv["source_word"]
        assert fixture["prototype"]["old_begin"] == old_begin
        assert fixture["prototype"]["old_base"] == old_begin & ~4095
        assert fixture["prototype"]["new_page_count"] == 2
        assert fixture["vector_begin"] == 0x06001000 + vector["vector_alignment"]
        for node, key in zip(
            first_fixture["prototype"]["source_addresses"],
            reversed(KEYS[: vector["source_size"]]),
        ):
            pointer = raw(fixture["pages"], node + 16)
            assert span(expected["pages"], pointer, 9) == f"{key:08x}".encode() + b"\0"
            assert span(fixture["pages"], pointer, 9) == span(
                capture["pages"], pointer, 9
            )
        for name in ("first_pointer", "second_pointer"):
            pointer = produced["fixture"][name]
            assert span(expected["pages"], pointer, vector["length"] + 1) == span(
                produced["pages"], pointer, vector["length"] + 1
            )


def test_same_tree_node_ids_links_and_existing_payload_routing(cases):
    for vector, _, first_fixture, first_expected, capture, fixture, expected in cases:
        first_child = next(
            row for row in first_expected["children"] if row["kind"] == "class"
        )
        second_child = next(
            row for row in expected["children"] if row["kind"] == "class"
        )
        nodes = first_child["result"]["destination_addresses"]
        assert fixture["prototype"]["destination_addresses"] == nodes
        assert second_child["result"]["destination_addresses"] == nodes
        assert second_child["result"]["tree_heap_count"] == 0
        assert second_child["result"]["heap_nodes"] == [fixture["vector_begin"]]
        size = vector["source_size"]
        expected_copies = []
        for index, key in enumerate(KEYS[:size]):
            source_id = size - 1 - index
            source_node = first_fixture["prototype"]["source_addresses"][source_id]
            value = raw(capture["pages"], source_node + 20) ^ 0xFFFFFFFF
            expected_copies.append(
                dict(
                    source=source_id,
                    key=key,
                    destination_address=nodes[index],
                    inserted=False,
                    mode="existing",
                    payload=value,
                    heap_node=None,
                )
            )
            assert raw(expected["pages"], nodes[index] + 20) == value
            assert span(expected["pages"], nodes[index], 20) == span(
                capture["pages"], nodes[index], 20
            )
        assert second_child["result"]["insertions"] == expected_copies
        assert raw(expected["pages"], U + 56) == raw(capture["pages"], U + 56) == size
        assert span(expected["pages"], P, 24) == span(capture["pages"], P, 24)
        logical = c._logical(fixture)
        links = logical["sentinel_link_ids"]
        assert [raw(expected["pages"], P + offset) for offset in (0, 4, 8)] == [
            P if links[field] is None else nodes[links[field]]
            for field in ("leftmost", "root", "rightmost")
        ]
        assert all(
            raw(expected["pages"], U + offset) == raw(capture["pages"], U + offset)
            for offset in (16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 60, 64, 68)
        )


def test_new_vector_original_pair_copy_append_one_allocation_and_one_free(cases):
    for _, _, first_fixture, _, capture, fixture, expected in cases:
        logical = c._logical(fixture)
        pointer, old_begin = fixture["vector_begin"], first_fixture["vector_begin"]
        pair = b"\0" * 4 + SOURCE.to_bytes(4, "little")
        assert span(capture["pages"], old_begin, 8) == pair
        assert span(expected["pages"], pointer, 16) == pair * 2
        assert [raw(expected["pages"], U + offset) for offset in (4, 8, 12)] == [
            pointer,
            pointer + 16,
            pointer + 16,
        ]
        assert (
            logical["vector"]["records"] == [[0, SOURCE], [0, SOURCE]]
            and logical["vector"]["capacity"] == 2
        )
        assert logical["vector_heap_request"] == dict(
            continuation=0x789463, handle=0x12345678, flags=0, bytes=16
        )
        assert logical["vector_free_request"] == dict(
            continuation=0x789172, handle=0x12345678, flags=0, pointer=old_begin
        )
        assert logical["tree_heap_requests"] == []
        assert logical["sentinel_preserved_offsets"] == list(range(24))
        assert len(logical["normal_preserved_userdata_offsets"]) == 13


def test_both_normal_returns_actual_second_registers_and_identity_bound_lua(cases):
    for _, produced, first_fixture, first_expected, capture, fixture, expected in cases:
        result = c.model.apply(
            first_arguments=c._first_arguments(first_fixture, produced),
            second_source_state=fixture["prototype"]["source_state"],
            new_vector_pointer=fixture["vector_begin"],
            second_entry=fixture["entry"],
            second_registers=fixture["registers"],
        )
        first, second = result["first"], result["second"]
        assert (
            first["full_return"]["registers"]
            == first_expected["registers"]
            == capture["registers"]
        )
        assert second == c._logical(fixture)
        assert second["full_return"]["registers"] == expected["registers"]
        assert second["full_return"]["flags"] == expected["flags"] == 0x44
        assert second["full_return"]["endpoint"] == expected["endpoint"] == 0x0400A000
        assert first["class_return"]["registers"]["edx"] == 0
        assert second["class_return"]["registers"]["edx"] == 0xB0000001
        assert first["normal_requests"] == second["normal_requests"]
        observer, lua = c.normal._IdentityPrefix(fixture), c.callback._Lua(
            fixture["callback_vector"]
        )
        for index, call in enumerate(expected["calls"]):
            if index < 12:
                observer.apply(call, call["arguments"])
            lua.apply(call)

        def bound(snapshot):
            return [
                ("argument", SOURCE) if token == ("argument", 0) else token
                for token in snapshot
            ]

        suffix = copy.deepcopy(lua.trace)
        for call in suffix:
            call["before"], call["after"] = bound(call["before"]), bound(call["after"])
        assert (
            observer.trace == second["prefix_calls"]
            and suffix == second["registry_table_calls"]
        )
        assert (
            bound(lua.stack) == second["normal_final_lua_stack"] and len(lua.stack) == 5
        )
        assert (
            lua.assignments == second["requested_assignments"]
            and second["return_count"] == 0
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "allocation_count",
        "closure_target",
        "upvalue",
        "source_payload",
        "source_tree",
        "register",
    ],
)
def test_strict_retained_address_identity_payload_topology_and_register_premises(
    cases, mutation
):
    vector, produced, first_fixture, _, capture, fixture, _ = cases[-1]
    produced, first_fixture, capture, fixture = copy.deepcopy(
        (produced, first_fixture, capture, fixture)
    )
    if mutation == "allocation_count":
        capture["observation"]["allocations"].pop(0)
        with pytest.raises(RuntimeError, match="retained tree address count differs"):
            c._resume(produced, first_fixture, capture, vector)
        return
    if mutation == "closure_target":
        fixture["first_arguments"]["closure_target"] ^= 1
    elif mutation == "upvalue":
        fixture["first_arguments"]["closure_upvalues"][0] ^= 1
    elif mutation == "source_payload":
        fixture["prototype"]["source_state"]["payloads"][0] = True
    elif mutation == "source_tree":
        fixture["prototype"]["source_state"]["tree"]["nodes"][0]["key"] ^= 1
    else:
        fixture["registers"]["eax"] ^= 1
    with pytest.raises(RuntimeError):
        c._logical(fixture)


def test_resume_and_logical_outputs_detached_from_capture_and_prior_fixture(cases):
    vector, produced, first_fixture, _, capture, fixture, _ = cases[-1]
    before = copy.deepcopy((vector, produced, first_fixture, capture, fixture))
    resumed, logical = c._resume(produced, first_fixture, capture, vector), c._logical(
        fixture
    )
    untouched = copy.deepcopy(logical)
    assert resumed == fixture
    resumed["prototype"]["source_state"]["payloads"][0] ^= 1
    resumed["prototype"]["destination_state"]["payloads"][0] ^= 1
    resumed["callback_vector"]["source_keys"].clear()
    resumed["callback_vector"]["source_refs"][0] ^= 1
    resumed["callback_vector"]["destination_refs"][0] ^= 1
    resumed["callback_vector"]["transfers"][0].append("other")
    resumed["prototype"]["source_addresses"][0] ^= 1
    resumed["prototype"]["destination_addresses"][0] ^= 1
    resumed["prototype"]["strings"].clear()
    resumed["prototype"]["source_state"]["tree"]["nodes"][0]["key"] ^= 1
    resumed["prototype"]["destination_state"]["tree"]["nodes"][0]["key"] ^= 1
    resumed["prototype"]["tree"]["nodes"].append({"changed": True})
    resumed["prototype"]["transfer"]["copies"][0]["payload"] ^= 1
    resumed["first_arguments"]["registers"]["eax"] ^= 1
    resumed["patches"][0]["after"] ^= 1
    logical["normal_requests"][0]["after"].clear()
    logical["callback_operation"]["vector"]["records"][0][1] ^= 1
    logical["vector_free_request"]["pointer"] ^= 1
    assert (vector, produced, first_fixture, capture, fixture) == before
    assert c._resume(produced, first_fixture, capture, vector) == fixture
    assert c._logical(fixture) == untouched
    assert (vector, produced, first_fixture, capture, fixture) == before


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (
        PREFIX + "native_lua_class_factory_callback_repeat_conformance.json"
    )
    evidence = json.loads(path.read_text(encoding="utf-8"))
    sources, paths = {}, {}
    for key, (kind, digest) in c.SOURCE_PINS.items():
        suffix = "program_facts" if key == "program_facts" else kind.removeprefix("pe_")
        source_path = PROGRAMS / (PREFIX + suffix + ".json")
        sources[key] = json.loads(source_path.read_text(encoding="utf-8"))
        assert c._canonical_sha256(sources[key]) == digest
        paths[key] = source_path
    return path, evidence, paths, sources


def test_sealed_receipt_lf_sources_and_independent_repeat_arithmetic(receipts):
    path, evidence, _, sources = receipts
    assert c.SEALED_SHA256 != "UNSEALED" and len(c.SEALED_SHA256) == 64
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert len(path.read_bytes()) == 389842
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert path.read_bytes().endswith(b"\n") and b"\r" not in path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert set(sources) == set(c.SOURCE_PINS)
    assert len(sources) == 31
    assert {
        "class_old",
        "factory_callback_tree",
        "class_tree",
        "factory_callback_return",
        "growth_conformance",
        "deallocation_composition",
        "small_copy",
    } <= set(sources)
    assert c.SOURCE_PINS["factory_callback_tree"] == (
        c.tree.ANALYSIS_KIND,
        c.tree.SEALED_SHA256,
    )
    assert c.SOURCE_PINS["class_old"] == (c.old.ANALYSIS_KIND, c.old.SEALED_SHA256)
    summary = evidence["summary"]
    expected = dict(
        cases=432,
        callback_invocations=864,
        static_sites=1115,
        executed_sites=797,
        instruction_bytes=2905,
        factory_instructions=286560,
        first_callback_instructions=622188,
        second_callback_instructions=520560,
        factory_api_calls=14688,
        callback_api_calls=35424,
        factory_heap_calls=432,
        first_class_heap_calls=1620,
        second_class_heap_calls=432,
        first_tree_nodes=1188,
        second_tree_allocations=0,
        second_payload_updates=1188,
        copied_old_vector_bytes=3456,
        second_vector_bytes=6912,
        free_calls=432,
        marker_calls=1728,
        table_calls=1728,
        requested_assignments=864,
        retained_lua_values_per_call=5,
        result_count=0,
        controls=33,
        opaque_native_instructions=0,
        accounting_promotions=0,
    )
    assert summary == expected
    assert evidence["scope"]["continuous_each_callback"] is True
    assert evidence["scope"]["continuous_across_host"] is False
    excluded = " ".join(evidence["scope"]["excluded"])
    assert all(
        text in excluded
        for text in (
            "New second pass keys",
            "more than two",
            "Lua VM",
            "ownership",
            "global accounting",
        )
    )


def test_first_sites_match_tree_predecessor_and_second_adds_old_vector_free_paths(
    receipts,
):
    _, evidence, _, sources = receipts
    first, second, union = (
        set(evidence[key])
        for key in ("first_executed_rvas", "second_executed_rvas", "executed_rvas")
    )
    assert first == set(sources["factory_callback_tree"]["executed_rvas"])
    assert union == first | second and second - first
    selected = {point["rva"] for point in evidence["body"]["points"]}
    partition = evidence["normal_site_partition"]
    groups = [
        set(partition[key])
        for key in ("callback", "class_operation", "markers", "tables")
    ]
    assert all(not left & right for left, right in itertools.combinations(groups, 2))
    assert set.union(*groups) == union
    assert union | set(partition["excluded"]) == selected and not union & set(
        partition["excluded"]
    )
    for key in ("callback", "markers", "tables"):
        assert (
            partition[key]
            == sources["factory_callback_tree"]["normal_site_partition"][key]
        )
    assert not any(
        a <= int(rva, 16) < b for rva in union for a, b in c.normal.PARENT_EXCLUDED
    )
    assert "0x003574d5" not in union and "0x002ec1bd" in first & second
    assert "0x0038916c" in second and "0x00007851" in second
    assert len(selected) == evidence["summary"]["static_sites"]
    assert len(union) == evidence["summary"]["executed_sites"]
    assert len(first) == 713 and len(second) == 546
    assert tuple(map(len, groups)) == (76, 623, 27, 71)
    assert len(partition["excluded"]) == 318
    assert (
        sum(point["size"] for point in evidence["body"]["points"])
        == evidence["summary"]["instruction_bytes"]
    )


def test_free_capture_and_cookie_controls_have_exact_independent_reasons(receipts):
    _, evidence, _, _ = receipts
    reasons = dict(c.normal.CONTROLS)
    reasons.update(
        free_request="callback free handoff differs",
        free_register="factory return free ABI differs",
        free_flags="factory return free ABI differs",
        free_identity="factory return free response identity differs",
        old="callback protected memory differs",
    )
    assert c.CONTROLS == reasons and len(reasons) == 30
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    assert set(controls) == set(reasons) | {
        "native_callback_cookie",
        "capture_pages",
        "capture_registers",
    }
    assert all(
        controls[key] == dict(kind=key, rejected=True, reason=reason)
        for key, reason in reasons.items()
    )
    for key in ("capture_pages", "capture_registers"):
        assert controls[key] == dict(
            kind=key, rejected=True, reason="verified callback capture differs"
        )
    assert controls["native_callback_cookie"] == dict(
        kind="native_callback_cookie", rejected=True, endpoint="0x003574d5"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "summary",
        "vector",
        "alignment",
        "control",
        "body",
        "kind",
        "producer",
        "first_observation",
        "second_observation",
        "first_sites",
        "second_sites",
        "callback",
        "class_operation",
        "markers",
        "tables",
        "excluded",
        "host_claim",
    ],
)
def test_tampered_receipt_rejected_by_seal(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    if mutation == "summary":
        changed["summary"]["free_calls"] += 1
    elif mutation == "vector":
        changed["vectors"][0]["source_size"] = 2
    elif mutation == "alignment":
        changed["vectors"][0]["node_alignment"] = 7
    elif mutation == "control":
        changed["negative_controls"][0]["rejected"] = False
    elif mutation == "body":
        changed["body"]["ranges"][0]["sha256"] = "0" * 64
    elif mutation in ("producer", "first_observation", "second_observation"):
        field = {
            "producer": "producer_observations_sha256",
            "first_observation": "first_observations_sha256",
            "second_observation": "second_observations_sha256",
        }[mutation]
        changed[field] = "0" * 64
    elif mutation in ("first_sites", "second_sites"):
        changed[
            (
                "first_executed_rvas"
                if mutation == "first_sites"
                else "second_executed_rvas"
            )
        ].pop()
    elif mutation in ("callback", "class_operation", "markers", "tables", "excluded"):
        changed["normal_site_partition"][mutation].pop()
    elif mutation == "host_claim":
        changed["scope"]["continuous_across_host"] = True
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ["missing", "extra", "pin", "kind"])
def test_strict_source_partition_and_content_pins(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["class_old"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["factory_callback_tree"]["schema_version"] += 1
    else:
        changed["deallocation_composition"]["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c._preflight(changed)
    with pytest.raises(RuntimeError):
        c.validate_structure(evidence, changed)


def command_for(command, paths):
    result = [sys.executable, str(CLI), command]
    for key, path in paths.items():
        result += ["--" + key.replace("_", "-"), str(path)]
    return result


def test_cli_structure_exact_lf_and_noncanonical_rejection(receipts, tmp_path):
    path, evidence, paths, sources = receipts
    command = command_for("verify-structure", paths)
    result = subprocess.run(
        command + ["--evidence", str(path)], cwd=ROOT, capture_output=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == c.encode_conformance(
        c.validate_structure(evidence, sources)
    ).encode("utf-8")
    assert result.stdout.endswith(b"\n") and b"\r" not in result.stdout
    noncanonical = tmp_path / "callback-repeat.json"
    noncanonical.write_text(json.dumps(evidence), encoding="utf-8")
    result = subprocess.run(
        command + ["--evidence", str(noncanonical)],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
    )
    assert (
        result.returncode == 1
        and result.stdout == b""
        and b"not deterministically encoded" in result.stderr
    )


def test_exact_native_build_and_verify_use_only_gated_subprocesses(receipts):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    path, _, paths, _ = receipts
    built = subprocess.run(
        command_for("build", paths) + ["--executable", executable],
        cwd=ROOT,
        capture_output=True,
        timeout=1200,
    )
    assert built.returncode == 0, built.stderr
    assert built.stderr == b"" and built.stdout == path.read_bytes()
    verified = subprocess.run(
        command_for("verify", paths)
        + ["--executable", executable, "--evidence", str(path)],
        cwd=ROOT,
        capture_output=True,
        timeout=1200,
    )
    assert verified.returncode == 0, verified.stderr
    assert verified.stderr == b"" and json.loads(verified.stdout) == dict(
        status="verified", evidence_sha256=c.SEALED_SHA256
    )
