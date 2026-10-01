"""Independent third-call capture and physical laws; native replay is CLI gated."""

import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.observatory import native_lua_class_factory_callback_third_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_callback_third_conformance.py"
U, P, SOURCE = 0x0FFFFFCC, 0x10000100, 0x14000000
FIRST_KEYS = ((0, 1, 16), (1, 16, 255))
SECOND_KEYS = (0, 1, 7, 17, 255, 0x80000000, 0xFFFFFFFF)
CANONICAL = "2e12f3b7af5475178f0660fbdab0aae7a7478fc684d1ad8f68e8bec7a96a7832"
RAW = "f3da47c838db5835c969359dda92143c02bf79179117d98f26330911070e3cbf"


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


def class_result(expected):
    return next(row["result"] for row in expected["children"] if row["kind"] == "class")


@pytest.fixture(scope="module")
def cases():
    # Captures are synthetic physical-law packets. Native instructions run only
    # in the explicitly gated CLI test below, which verifies real capture data.
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
                "first_key_profile",
                "source_profile",
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
        first_fixture = c.extend._resume_first(produced, vector)
        first_expected = c.callback._expected(
            first_fixture["callback_vector"], first_fixture, class_module=c.tree.empty
        )
        first_nodes = class_result(first_expected)["destination_addresses"]
        first_capture = dict(
            pages=copy.deepcopy(first_expected["pages"]),
            registers=copy.deepcopy(first_expected["registers"]),
        )
        first_capture["observation"] = dict(
            registers=copy.deepcopy(first_capture["registers"]),
            memory_sha256=page_sha(first_capture["pages"]),
            allocations=[dict(node=node, request=24) for node in first_nodes]
            + [dict(node=first_fixture["vector_begin"], request=8)],
        )
        second_fixture = c.extend._resume(
            produced, first_fixture, first_capture, vector
        )
        second_expected = c.callback._expected(
            second_fixture["callback_vector"], second_fixture, class_module=c.old
        )
        second_nodes = class_result(second_expected)["destination_addresses"]
        second_capture = dict(
            pages=copy.deepcopy(second_expected["pages"]),
            registers=copy.deepcopy(second_expected["registers"]),
        )
        second_capture["observation"] = dict(
            registers=copy.deepcopy(second_capture["registers"]),
            memory_sha256=page_sha(second_capture["pages"]),
            allocations=[dict(node=node, request=24) for node in second_nodes[3:]]
            + [dict(node=second_fixture["vector_begin"], request=16)],
        )
        fixture = c._resume(produced, second_fixture, second_capture, vector)
        expected = c.callback._expected(
            fixture["callback_vector"], fixture, class_module=c.old
        )
        result.append(
            (
                vector,
                produced,
                first_fixture,
                first_expected,
                first_capture,
                second_fixture,
                second_expected,
                second_capture,
                fixture,
                expected,
            )
        )
    assert len(producers) == 2 and len(result) == 24
    return result


def test_exact_216_product_and_independent_three_call_arithmetic():
    vectors = c.vectors()
    assert len(vectors) == 216
    assert vectors == [
        vector for vector in c.extend.vectors() if vector["source_profile"] == 3
    ]
    assert all(
        vector["source_size"] == 3
        and vector["node_alignment"] == 31
        and vector["source_profile"] == 3
        for vector in vectors
    )
    counts = {}
    for vector in vectors:
        group = tuple(
            vector[key]
            for key in ("vector_alignment", "first_key_profile", "transfer_profile")
        )
        counts[group] = counts.get(group, 0) + 1
        assert len(set(FIRST_KEYS[vector["first_key_profile"]]) | set(SECOND_KEYS)) == 8
        assert len(set(SECOND_KEYS) - set(FIRST_KEYS[vector["first_key_profile"]])) == 5
    assert counts == {
        group: 18 for group in itertools.product((0, 7, 31), (0, 1), (0, 4))
    }
    producer_keys = {
        tuple(
            sorted(
                {
                    key: value
                    for key, value in vector.items()
                    if key
                    not in (
                        "vector_alignment",
                        "first_key_profile",
                        "source_profile",
                        "transfer_profile",
                        "source_size",
                        "node_alignment",
                    )
                }.items()
            )
        )
        for vector in vectors
    }
    assert len(producer_keys) == 18
    assert {vector["profile"] for vector in vectors} == {0, 1}
    assert {vector["length"] for vector in vectors} == {0, 16, 255}
    assert {vector["registry_profile"] for vector in vectors} == {0, 1, 2}
    assert 3 * len(vectors) == 648 and 4 * len(vectors) == 864
    assert 5 * len(vectors) == 1080 and 6 * len(vectors) == 1296
    assert 7 * len(vectors) == 1512 and 8 * len(vectors) == 1728


def test_second_captured_pages_and_all_gprs_match_verified_return_before_third_host(
    cases,
):
    for _, _, _, _, _, second_fixture, second_expected, capture, fixture, _ in cases:
        assert capture["pages"] == second_expected["pages"]
        assert (
            capture["registers"]
            == second_expected["registers"]
            == capture["observation"]["registers"]
        )
        assert (
            capture["registers"] == c._prior(second_fixture)["full_return"]["registers"]
        )
        assert (
            page_sha(capture["pages"])
            == capture["observation"]["memory_sha256"]
            == fixture["captured_pages_sha256"]
        )
        assert fixture["registers"] == dict(capture["registers"], esp=fixture["entry"])


@pytest.mark.parametrize(
    "register", ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
)
@pytest.mark.parametrize("coordinated", (False, True))
def test_corrupted_second_gpr_rejected_before_third_host(
    cases, monkeypatch, register, coordinated
):
    vector, produced, _, _, _, second_fixture, _, capture, _, _ = cases[-1]
    corrupted = copy.deepcopy(capture)
    corrupted["registers"][register] ^= 1
    if coordinated:
        corrupted["observation"]["registers"][register] ^= 1
    before, reached = copy.deepcopy(corrupted), []

    def forbidden(*args, **kwargs):
        reached.append(True)
        raise AssertionError("third host binder reached before capture rejection")

    monkeypatch.setattr(c.normal.first.entry, "_resume", forbidden)
    reason = (
        "retained second callback differs"
        if coordinated
        else "verified second callback capture differs"
    )
    with pytest.raises(RuntimeError, match=reason):
        c._resume(produced, second_fixture, corrupted, vector)
    assert corrupted == before and reached == []


@pytest.mark.parametrize(
    "region",
    (
        "userdata",
        "count",
        "sentinel",
        "old_vector",
        "first_vector",
        "source_payload",
        "old_key",
        "new_key",
        "stack",
        "fs",
        "cookie",
    ),
)
def test_corrupted_second_page_digest_rejected_before_third_host(
    cases, monkeypatch, region
):
    vector, produced, first_fixture, _, _, second_fixture, _, capture, _, _ = cases[-1]
    source_node = second_fixture["prototype"]["source_addresses"][0]
    old_key = next(
        pointer
        for pointer in second_fixture["prototype"]["strings"]
        if 0x1C000000 <= pointer < 0x1D000000
    )
    address = dict(
        userdata=U,
        count=U + 56,
        sentinel=P + 14,
        old_vector=second_fixture["vector_begin"],
        first_vector=first_fixture["vector_begin"],
        source_payload=source_node + 20,
        old_key=old_key,
        new_key=raw(capture["pages"], source_node + 16),
        stack=second_fixture["entry"] - 12,
        fs=0,
        cookie=0x00893F28,
    )[region]
    corrupted = copy.deepcopy(capture)
    corrupted["pages"] = change(
        corrupted["pages"], address, raw(corrupted["pages"], address, 1) ^ 1, 1
    )
    before, reached = copy.deepcopy(corrupted), []

    def forbidden(*args, **kwargs):
        reached.append(True)
        raise AssertionError("third host binder reached before capture rejection")

    monkeypatch.setattr(c.normal.first.entry, "_resume", forbidden)
    with pytest.raises(RuntimeError, match="verified second callback capture differs"):
        c._resume(produced, second_fixture, corrupted, vector)
    assert corrupted == before and reached == []


@pytest.mark.parametrize(
    "region",
    (
        "left",
        "parent",
        "right",
        "color",
        "nil",
        "key_pointer",
        "payload",
        "old_key_bytes",
        "new_key_bytes",
        "receiver_word",
        "vector_pointer",
        "count",
        "userdata_tail",
        "sentinel_link",
        "sentinel_tail",
        "old_vector_record",
        "first_vector_record",
        "fs",
        "cookie",
    ),
)
def test_coordinated_retained_second_storage_corruption_rejected_before_host(
    cases, monkeypatch, region
):
    vector, produced, _, _, _, second_fixture, second_expected, capture, _, _ = cases[
        -1
    ]
    node = class_result(second_expected)["destination_addresses"][0]
    source_node = second_fixture["prototype"]["source_addresses"][0]
    old_key = next(
        pointer
        for pointer in second_fixture["prototype"]["strings"]
        if 0x1C000000 <= pointer < 0x1D000000
    )
    address, width = dict(
        left=(node, 4),
        parent=(node + 4, 4),
        right=(node + 8, 4),
        color=(node + 12, 1),
        nil=(node + 13, 1),
        key_pointer=(node + 16, 4),
        payload=(node + 20, 4),
        old_key_bytes=(old_key, 1),
        new_key_bytes=(raw(capture["pages"], source_node + 16), 1),
        receiver_word=(U, 4),
        vector_pointer=(U + 4, 4),
        count=(U + 56, 4),
        userdata_tail=(U + 68, 4),
        sentinel_link=(P + 4, 4),
        sentinel_tail=(P + 16, 4),
        old_vector_record=(second_fixture["vector_begin"] + 12, 4),
        first_vector_record=(
            second_fixture["first_arguments"]["vector_pointer"] + 4,
            4,
        ),
        fs=(0, 4),
        cookie=(0x00893F28, 4),
    )[region]
    corrupted = copy.deepcopy(capture)
    corrupted["pages"] = change(
        corrupted["pages"], address, raw(corrupted["pages"], address, width) ^ 1, width
    )
    corrupted["observation"]["memory_sha256"] = page_sha(corrupted["pages"])
    before, reached = copy.deepcopy(corrupted), []

    def forbidden(*args, **kwargs):
        reached.append(True)
        raise AssertionError(
            "third host binder reached before retained-state rejection"
        )

    monkeypatch.setattr(c.normal.first.entry, "_resume", forbidden)
    with pytest.raises(RuntimeError, match="retained second callback differs"):
        c._resume(produced, second_fixture, corrupted, vector)
    assert corrupted == before and reached == []


def test_third_host_exact_byte_patch_replay_only_source_payloads_change(cases):
    for vector, produced, _, _, _, second_fixture, _, capture, fixture, _ in cases:
        current = dict(produced, pages=capture["pages"], registers=capture["registers"])
        boundary = c.normal.first.entry._resume(
            current,
            c.tree._normal_vector(c.extend._base_vector(vector)),
            callback_entry=second_fixture["entry"],
        )
        assert fixture["patches"][: len(boundary["patches"])] == boundary["patches"]
        addresses = second_fixture["prototype"]["source_addresses"]
        assert [
            row["address"] for row in fixture["patches"][len(boundary["patches"]) :]
        ] == [node + 20 + index for node in addresses for index in range(4)]
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
            fixture["prototype"]["source_state"]["tree"]
            == second_fixture["prototype"]["source_state"]["tree"]
        )
        for index, node in enumerate(addresses):
            before = raw(capture["pages"], node + 20)
            assert span(fixture["pages"], node, 20) == span(capture["pages"], node, 20)
            assert raw(fixture["pages"], node + 20) == before ^ 0xFFFFFFFF
            assert (
                fixture["prototype"]["source_state"]["payloads"][index]
                == before ^ 0xFFFFFFFF
            )
        assert (
            raw(fixture["pages"], c.old.growth.FREE_IAT) == c.normal.layout.HEAP_TARGET
        )


def test_third_retains_receiver_sentinel_first_and_second_vectors_nodes_keys_fs_and_cookie(
    cases,
):
    for (
        vector,
        produced,
        first_fixture,
        _,
        _,
        second_fixture,
        second_expected,
        capture,
        fixture,
        expected,
    ) in cases:
        nodes = class_result(second_expected)["destination_addresses"]
        retained = [
            (U, 72),
            (P, 24),
            (first_fixture["vector_begin"], 8),
            (second_fixture["vector_begin"], 16),
        ]
        retained += [(node, 24) for node in nodes]
        retained += [
            (pointer, len(value))
            for pointer, value in second_fixture["prototype"]["strings"].items()
        ]
        for address, width in retained:
            assert span(fixture["pages"], address, width) == span(
                capture["pages"], address, width
            )
        cv = fixture["callback_vector"]
        assert (
            raw(fixture["pages"], 0)
            == raw(expected["pages"], 0)
            == cv["previous_seh"]
            == raw(capture["pages"], 0)
        )
        assert (
            cv["cookie"]
            == raw(fixture["pages"], 0x00893F28)
            == raw(capture["pages"], 0x00893F28)
        )
        for field in (
            "source_word",
            "source_refs",
            "destination_refs",
            "transfers",
            "source_keys",
        ):
            assert cv[field] == second_fixture["callback_vector"][field]
        assert cv["old_size"] == fixture["prototype"]["old_size"] == 2
        assert (
            fixture["prototype"]["old_base"] == second_fixture["vector_begin"] & ~4095
        )
        assert (
            fixture["prototype"]["old_begin"]
            == fixture["second_vector_pointer"]
            == second_fixture["vector_begin"]
        )
        assert fixture["prototype"]["new_page_count"] == 1
        assert (
            fixture["vector_begin"]
            == c.old.construction.DATA + 0x800 + vector["vector_alignment"]
        )
        assert fixture["prototype"]["node"] == c.old.construction.DATA + 0x600 + 31
        assert (
            fixture["second_source_state"]
            == second_fixture["prototype"]["source_state"]
        )
        assert fixture["second_registers"] == second_fixture["registers"]
        assert fixture["second_entry"] == second_fixture["entry"]
        for name in ("first_pointer", "second_pointer"):
            pointer = produced["fixture"][name]
            assert span(expected["pages"], pointer, vector["length"] + 1) == span(
                produced["pages"], pointer, vector["length"] + 1
            )


def test_third_existing_payload_routing_same_eight_nodes_links_and_omitted_key16(cases):
    for (
        vector,
        _,
        _,
        first_expected,
        _,
        second_fixture,
        second_expected,
        capture,
        fixture,
        expected,
    ) in cases:
        child = class_result(expected)
        nodes = class_result(second_expected)["destination_addresses"]
        assert nodes[:3] == class_result(first_expected)["destination_addresses"]
        assert (
            fixture["prototype"]["destination_addresses"]
            == child["destination_addresses"]
            == nodes
        )
        assert len(nodes) == 8 and child["tree_heap_count"] == 0
        assert child["heap_nodes"] == [fixture["vector_begin"]]
        assert span(expected["pages"], fixture["prototype"]["node"], 24) == span(
            capture["pages"], fixture["prototype"]["node"], 24
        )
        first_keys = FIRST_KEYS[vector["first_key_profile"]]
        keys_by_id = list(first_keys) + sorted(set(SECOND_KEYS) - set(first_keys))
        copies = []
        for index, key in enumerate(SECOND_KEYS):
            source_id = 6 - index
            destination_id = keys_by_id.index(key)
            source_node = second_fixture["prototype"]["source_addresses"][source_id]
            value = raw(capture["pages"], source_node + 20) ^ 0xFFFFFFFF
            copies.append(
                dict(
                    source=source_id,
                    key=key,
                    destination_address=nodes[destination_id],
                    inserted=False,
                    mode="existing",
                    payload=value,
                    heap_node=None,
                )
            )
            assert raw(expected["pages"], nodes[destination_id] + 20) == value
        assert child["insertions"] == copies
        for index, node in enumerate(nodes):
            assert span(expected["pages"], node, 20) == span(capture["pages"], node, 20)
            pointer = raw(expected["pages"], node + 16)
            assert (
                span(expected["pages"], pointer, 9)
                == f"{keys_by_id[index]:08x}".encode() + b"\0"
            )
        omitted = keys_by_id.index(16)
        assert raw(expected["pages"], nodes[omitted] + 20) == raw(
            capture["pages"], nodes[omitted] + 20
        )
        logical = c._logical(fixture)
        prior = c._prior(second_fixture)
        assert (
            logical["callback_operation"]["destination"]["tree"]
            == prior["callback_operation"]["destination"]["tree"]
        )
        assert logical["sentinel_link_ids"] == prior["sentinel_link_ids"]
        assert (
            raw(expected["pages"], U + 56)
            == raw(capture["pages"], U + 56)
            == logical["tree_count"]
            == 8
        )
        assert span(expected["pages"], P, 24) == span(capture["pages"], P, 24)
        links = logical["sentinel_link_ids"]
        assert [raw(expected["pages"], P + offset) for offset in (0, 4, 8)] == [
            P if links[field] is None else nodes[links[field]]
            for field in ("leftmost", "root", "rightmost")
        ]


def test_third_copies_actual16_appends_pair_allocates24_capacity3_and_frees_second16(
    cases,
):
    for (
        _,
        _,
        first_fixture,
        _,
        first_capture,
        second_fixture,
        _,
        capture,
        fixture,
        expected,
    ) in cases:
        logical = c._logical(fixture)
        pointer, old_begin, first_begin = (
            fixture["vector_begin"],
            second_fixture["vector_begin"],
            first_fixture["vector_begin"],
        )
        pair = b"\0" * 4 + SOURCE.to_bytes(4, "little")
        assert span(capture["pages"], old_begin, 16) == pair * 2
        assert span(expected["pages"], pointer, 16) == span(
            capture["pages"], old_begin, 16
        )
        assert span(expected["pages"], pointer + 16, 8) == pair
        assert span(expected["pages"], old_begin, 16) == span(
            capture["pages"], old_begin, 16
        )
        assert (
            span(expected["pages"], first_begin, 8)
            == span(first_capture["pages"], first_begin, 8)
            == pair
        )
        assert [raw(expected["pages"], U + offset) for offset in (4, 8, 12)] == [
            pointer,
            pointer + 24,
            pointer + 24,
        ]
        assert logical["vector"] == dict(
            records=[[0, SOURCE], [0, SOURCE], [0, SOURCE]],
            capacity=3,
            begin=pointer,
            end=pointer + 24,
            capacity_pointer=pointer + 24,
        )
        assert logical["vector_heap_request"] == dict(
            continuation=0x789463, handle=0x12345678, flags=0, bytes=24
        )
        assert logical["vector_free_request"] == dict(
            continuation=0x789172, handle=0x12345678, flags=0, pointer=old_begin
        )
        assert logical["tree_heap_requests"] == []
        assert logical["sentinel_preserved_offsets"] == list(range(24))
        assert logical["normal_preserved_userdata_offsets"] == [
            16,
            20,
            24,
            28,
            32,
            36,
            40,
            44,
            48,
            52,
            60,
            64,
            68,
        ]
        for offset in logical["normal_preserved_userdata_offsets"]:
            assert raw(expected["pages"], U + offset) == raw(
                capture["pages"], U + offset
            )


def test_all_three_normal_abi_packets_identity_bound_lua_and_actual_third_gprs(cases):
    for (
        _,
        _,
        _,
        first_expected,
        first_capture,
        _,
        second_expected,
        capture,
        fixture,
        expected,
    ) in cases:
        result = c.model.apply(
            first_arguments=fixture["first_arguments"],
            second_source_state=fixture["second_source_state"],
            second_vector_pointer=fixture["second_vector_pointer"],
            second_entry=fixture["second_entry"],
            second_registers=fixture["second_registers"],
            third_source_state=fixture["prototype"]["source_state"],
            new_vector_pointer=fixture["vector_begin"],
            third_entry=fixture["entry"],
            third_registers=fixture["registers"],
        )
        first, second, third = (result[key] for key in ("first", "second", "third"))
        assert (
            first["full_return"]["registers"]
            == first_expected["registers"]
            == first_capture["registers"]
        )
        assert (
            second["full_return"]["registers"]
            == second_expected["registers"]
            == capture["registers"]
        )
        assert third == c._logical(fixture)
        assert third["full_return"]["registers"] == expected["registers"]
        assert third["full_return"]["flags"] == expected["flags"] == 0x44
        assert third["full_return"]["endpoint"] == expected["endpoint"] == 0x0400A000
        assert first["class_return"]["registers"]["edx"] == 0
        assert (
            second["class_return"]["registers"]["edx"]
            == third["class_return"]["registers"]["edx"]
            == 0xB0000001
        )
        assert (
            first["normal_requests"]
            == second["normal_requests"]
            == third["normal_requests"]
        )
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
            observer.trace == third["prefix_calls"]
            and suffix == third["registry_table_calls"]
        )
        assert (
            bound(lua.stack) == third["normal_final_lua_stack"] and len(lua.stack) == 5
        )
        assert (
            lua.assignments == third["requested_assignments"]
            and third["return_count"] == 0
        )
        entry, cookie = fixture["entry"], fixture["callback_vector"]["cookie"]
        assert third["native_cookie"] == dict(
            frame=entry - 52,
            protected_address=entry - 56,
            stored_word=cookie ^ (entry - 52),
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "allocation_count",
        "closure_target",
        "upvalue",
        "source_payload",
        "source_tree",
        "register",
        "second_register",
        "second_vector",
    ),
)
def test_strict_retained_second_identity_schema_topology_and_actual_register_premises(
    cases, mutation
):
    vector, produced, _, _, _, second_fixture, _, capture, fixture, _ = cases[-1]
    produced, second_fixture, capture, fixture = copy.deepcopy(
        (produced, second_fixture, capture, fixture)
    )
    if mutation == "allocation_count":
        capture["observation"]["allocations"].pop(0)
        with pytest.raises(RuntimeError, match="retained second callback differs"):
            c._resume(produced, second_fixture, capture, vector)
        return
    if mutation == "closure_target":
        fixture["first_arguments"]["closure_target"] ^= 1
    elif mutation == "upvalue":
        fixture["first_arguments"]["closure_upvalues"][0] ^= 1
    elif mutation == "source_payload":
        fixture["prototype"]["source_state"]["payloads"][0] = True
    elif mutation == "source_tree":
        fixture["prototype"]["source_state"]["tree"]["nodes"][0]["color"] = True
    elif mutation == "second_register":
        fixture["second_registers"]["eax"] ^= 1
    elif mutation == "second_vector":
        fixture["second_vector_pointer"] = fixture["vector_begin"]
    else:
        fixture["registers"]["eax"] ^= 1
    with pytest.raises(RuntimeError):
        c._logical(fixture)


def test_third_adapter_metadata_detached_from_second_fixture_capture_and_producer(
    cases,
):
    vector, produced, _, _, _, second_fixture, _, capture, fixture, _ = cases[-1]
    before = copy.deepcopy((vector, produced, second_fixture, capture, fixture))
    resumed, logical = c._resume(produced, second_fixture, capture, vector), c._logical(
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
    resumed["second_source_state"]["payloads"][0] ^= 1
    resumed["second_registers"]["eax"] ^= 1
    resumed["patches"][0]["after"] ^= 1
    logical["normal_requests"][0]["after"].clear()
    logical["callback_operation"]["vector"]["records"][0][1] ^= 1
    logical["vector_free_request"]["pointer"] ^= 1
    assert (vector, produced, second_fixture, capture, fixture) == before
    assert c._resume(produced, second_fixture, capture, vector) == fixture
    assert c._logical(fixture) == untouched
    assert (vector, produced, second_fixture, capture, fixture) == before


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (
        PREFIX + "native_lua_class_factory_callback_third_conformance.json"
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


def test_sealed_receipt_lf_sources_and_independent_three_call_arithmetic(receipts):
    path, evidence, _, sources = receipts
    assert c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert len(path.read_bytes()) == 348679
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert path.read_bytes().endswith(b"\n") and b"\r" not in path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert set(sources) == set(c.SOURCE_PINS) and len(sources) == 33
    assert c.SOURCE_PINS["factory_callback_extend"] == (
        c.extend.ANALYSIS_KIND,
        c.extend.SEALED_SHA256,
    )
    summary = evidence["summary"]
    expected = dict(
        cases=216,
        callback_invocations=648,
        static_sites=1115,
        executed_sites=881,
        instruction_bytes=2905,
        factory_instructions=143280,
        first_callback_instructions=326376,
        second_callback_instructions=710316,
        third_callback_instructions=534816,
        factory_heap_calls=216,
        first_class_heap_calls=864,
        second_class_heap_calls=1296,
        third_class_heap_calls=216,
        first_tree_nodes=648,
        second_tree_allocations=1080,
        second_payload_updates=432,
        second_source_copies=1512,
        third_payload_updates=1512,
        third_tree_allocations=0,
        final_tree_nodes=1728,
        second_copied_old_vector_bytes=1728,
        third_copied_old_vector_bytes=3456,
        second_vector_bytes=3456,
        third_vector_bytes=5184,
        free_calls=432,
        marker_calls=1296,
        table_calls=1296,
        requested_assignments=648,
        factory_api_calls=7344,
        callback_api_calls=26568,
        retained_lua_values_per_call=5,
        result_count=0,
        controls=37,
        opaque_native_instructions=0,
        accounting_promotions=0,
    )
    assert {key: summary[key] for key in expected} == expected
    assert {
        key: len(rows) for key, rows in evidence["normal_site_partition"].items()
    } == dict(callback=76, class_operation=707, markers=27, tables=71, excluded=234)
    assert [
        len(evidence[key + "_executed_rvas"]) for key in ("first", "second", "third")
    ] == [701, 864, 546]
    assert evidence["scope"]["continuous_each_callback"] is True
    assert evidence["scope"]["continuous_across_host"] is False


def test_three_site_sets_union_partition_and_predecessor_coverage_are_explicit(
    receipts,
):
    _, evidence, _, sources = receipts
    first, second, third, union = (
        set(evidence[key])
        for key in (
            "first_executed_rvas",
            "second_executed_rvas",
            "third_executed_rvas",
            "executed_rvas",
        )
    )
    assert union == first | second | third
    assert first == set(
        sources["factory_callback_tree"]["families"]["3"]["executed_rvas"]
    )
    assert second <= set(sources["factory_callback_extend"]["second_executed_rvas"])
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
    assert "0x003574d5" not in union and "0x002ec1bd" in first & second & third
    assert "0x0038916c" in second & third and "0x00007851" in second & third
    assert len(selected) == evidence["summary"]["static_sites"]
    assert len(union) == evidence["summary"]["executed_sites"]
    assert (
        sum(point["size"] for point in evidence["body"]["points"])
        == evidence["summary"]["instruction_bytes"]
    )


def test_cookie_capture_retained_tree_and_free_controls_have_independent_reasons(
    receipts,
):
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
    retained = {
        "retained_key_pointer",
        "retained_payload",
        "retained_key_bytes",
        "retained_link",
    }
    assert set(controls) == set(reasons) | retained | {
        "native_callback_cookie",
        "capture_pages",
        "capture_registers",
    }
    assert len(controls) == evidence["summary"]["controls"] == 37
    for key, reason in reasons.items():
        assert controls[key] == dict(kind=key, rejected=True, reason=reason)
    for key in retained:
        assert controls[key] == dict(
            kind=key, rejected=True, reason="retained second callback differs"
        )
    for key in ("capture_pages", "capture_registers"):
        assert controls[key] == dict(
            kind=key, rejected=True, reason="verified second callback capture differs"
        )
    assert controls["native_callback_cookie"] == dict(
        kind="native_callback_cookie", rejected=True, endpoint="0x003574d5"
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "summary",
        "first_profile",
        "second_profile",
        "alignment",
        "control",
        "body",
        "kind",
        "producer",
        "first_observation",
        "second_observation",
        "third_observation",
        "first_sites",
        "second_sites",
        "third_sites",
        "callback",
        "class_operation",
        "markers",
        "tables",
        "excluded",
        "host_claim",
    ),
)
def test_tampered_third_receipt_rejected_by_seal(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    if mutation == "summary":
        changed["summary"]["free_calls"] += 1
    elif mutation in ("first_profile", "second_profile"):
        changed["vectors"][0][
            "first_key_profile" if mutation == "first_profile" else "source_profile"
        ] = 99
    elif mutation == "alignment":
        changed["vectors"][0]["node_alignment"] = 7
    elif mutation == "control":
        changed["negative_controls"][0]["rejected"] = False
    elif mutation == "body":
        changed["body"]["ranges"][0]["sha256"] = "0" * 64
    elif mutation in (
        "producer",
        "first_observation",
        "second_observation",
        "third_observation",
    ):
        field = {
            "producer": "producer_observations_sha256",
            "first_observation": "first_observations_sha256",
            "second_observation": "second_observations_sha256",
            "third_observation": "third_observations_sha256",
        }[mutation]
        changed[field] = "0" * 64
    elif mutation in ("first_sites", "second_sites", "third_sites"):
        changed[
            {
                "first_sites": "first_executed_rvas",
                "second_sites": "second_executed_rvas",
                "third_sites": "third_executed_rvas",
            }[mutation]
        ].pop()
    elif mutation in ("callback", "class_operation", "markers", "tables", "excluded"):
        changed["normal_site_partition"][mutation].pop()
    elif mutation == "host_claim":
        changed["scope"]["continuous_across_host"] = True
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ("missing", "extra", "pin", "kind"))
def test_strict_source_partition_and_content_pins(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["factory_callback_extend"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["factory_callback_extend"]["schema_version"] += 1
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
    noncanonical = tmp_path / "callback-third.json"
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
