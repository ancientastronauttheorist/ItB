"""Independent retained-tree union laws; exact native replay is CLI gated."""

import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.observatory import native_lua_class_factory_callback_extend_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_callback_extend_conformance.py"
CANONICAL = "c0cc89b3af1cecb03d752cf7e17fde6c621631bcbb43046475124609bd589797"
RAW = "c1997e061f2f161538ec5dc953a185a251585b6affff078115e3c1a701c447e8"
U, P, SOURCE = 0x0FFFFFCC, 0x10000100, 0x14000000
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


def selected_keys(vector):
    return (
        FIRST_KEYS[vector["first_key_profile"]],
        SECOND_KEYS[vector["first_key_profile"]][vector["source_profile"]],
    )


def assert_canonical_tree(state, keys):
    # Check ordering, parent reciprocity, color restrictions and black height
    # without using the balancing implementation or its validator.
    tree, seen = state["tree"], set()
    nodes, root = tree["nodes"], tree["root"]
    assert len(nodes) == len(state["payloads"]) == len(keys)
    assert root is not None and nodes[root]["color"] == 1

    def walk(identity, parent, lo, hi):
        if identity is None:
            return [], 1
        assert identity not in seen and 0 <= identity < len(nodes)
        seen.add(identity)
        node = nodes[identity]
        assert node["parent"] == parent and lo < node["key"] < hi
        assert node["color"] in (0, 1)
        if node["color"] == 0:
            assert all(
                child is None or nodes[child]["color"] == 1
                for child in (node["left"], node["right"])
            )
        left, lb = walk(node["left"], identity, lo, node["key"])
        right, rb = walk(node["right"], identity, node["key"], hi)
        assert lb == rb
        return left + [node["key"]] + right, lb + node["color"]

    order, _ = walk(root, None, -1, 2**32)
    assert order == sorted(keys) and seen == set(range(len(nodes)))


@pytest.fixture(scope="module")
def cases():
    # Synthetic producer/capture packets exercise the physical adapters without
    # claiming a native execution. The gated CLI below supplies native evidence.
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
        first_fixture = c._resume_first(produced, vector)
        first_expected = c.callback._expected(
            first_fixture["callback_vector"], first_fixture, class_module=c.tree.empty
        )
        nodes = class_result(first_expected)["destination_addresses"]
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
    assert len(producers) == 2 and len(result) == 96
    return result


def test_exact_864_case_product_and_independent_union_arithmetic():
    vectors = c.vectors()
    assert len(vectors) == 864
    assert c.FIRST_KEYS == FIRST_KEYS and c.SECOND_KEYS == SECOND_KEYS
    assert all(
        vector["source_size"] == 3 and vector["node_alignment"] == 31
        for vector in vectors
    )
    counts = {}
    for vector in vectors:
        group = tuple(
            vector[key]
            for key in (
                "vector_alignment",
                "first_key_profile",
                "source_profile",
                "transfer_profile",
            )
        )
        counts[group] = counts.get(group, 0) + 1
    assert counts == {
        group: 18 for group in itertools.product((0, 7, 31), (0, 1), range(4), (0, 4))
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
    assert sum(len(selected_keys(vector)[1]) for vector in vectors) == 2808
    assert (
        sum(
            len(set(selected_keys(vector)[1]) - set(selected_keys(vector)[0]))
            for vector in vectors
        )
        == 2052
    )
    assert 3 * len(vectors) == 2592 and 4 * len(vectors) == 3456
    assert 2052 + len(vectors) == 2916


def test_first_rekey_preserves_source_topology_and_payloads_and_factory_names(cases):
    for vector, produced, fixture, expected, _, _, _ in cases:
        base = c.tree._resume(produced, c._base_vector(vector))
        first_keys, _ = selected_keys(vector)
        assert fixture["callback_vector"]["source_keys"] == list(reversed(first_keys))
        assert (
            fixture["prototype"]["source_state"]["payloads"]
            == base["prototype"]["source_state"]["payloads"]
        )
        assert (
            fixture["prototype"]["source_addresses"]
            == base["prototype"]["source_addresses"]
        )
        for index, key in enumerate(reversed(first_keys)):
            node = fixture["prototype"]["source_addresses"][index]
            assert span(fixture["pages"], node, 24) == span(base["pages"], node, 24)
            pointer = raw(fixture["pages"], node + 16)
            key_bytes = f"{key:08x}".encode() + b"\0"
            assert pointer == 0x1C000FFF + 32 * index + 3
            assert span(fixture["pages"], pointer, 9) == key_bytes
            assert fixture["key_bindings"][index] == dict(
                node=node,
                key_pointer=pointer,
                bytes=9,
                sha256=hashlib.sha256(key_bytes).hexdigest(),
            )
            original = base["prototype"]["source_state"]["tree"]["nodes"][index]
            current = fixture["prototype"]["source_state"]["tree"]["nodes"][index]
            assert {k: v for k, v in current.items() if k != "key"} == {
                k: v for k, v in original.items() if k != "key"
            }
        assert_canonical_tree(fixture["prototype"]["source_state"], first_keys)
        assert [
            node["key"]
            for node in fixture["logical"]["class_operation"]["destination"]["tree"][
                "nodes"
            ]
        ] == list(first_keys)
        for name in ("first_pointer", "second_pointer"):
            pointer = produced["fixture"][name]
            assert span(expected["pages"], pointer, vector["length"] + 1) == span(
                produced["pages"], pointer, vector["length"] + 1
            )


def test_capture_every_gpr_and_page_digest_matches_before_second_host(cases):
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
def test_corrupted_captured_gpr_rejected_before_host(cases, monkeypatch, register):
    vector, produced, first_fixture, _, capture, _, _ = cases[-1]
    corrupted = copy.deepcopy(capture)
    corrupted["registers"][register] ^= 1
    before, reached = copy.deepcopy(corrupted), []

    def forbidden(*args, **kwargs):
        reached.append(True)
        raise AssertionError("host binder reached before capture rejection")

    monkeypatch.setattr(c.normal.first.entry, "_resume", forbidden)
    with pytest.raises(RuntimeError, match="verified callback capture differs"):
        c._resume(produced, first_fixture, corrupted, vector)
    assert corrupted == before and reached == []


@pytest.mark.parametrize(
    "region",
    (
        "userdata",
        "sentinel",
        "old_vector",
        "source_payload",
        "first_node_key",
        "key_bytes",
        "stack",
        "fs",
    ),
)
def test_corrupted_captured_page_rejected_before_host(cases, monkeypatch, region):
    vector, produced, first_fixture, first_expected, capture, _, _ = cases[-1]
    source_node = first_fixture["prototype"]["source_addresses"][0]
    destination_node = class_result(first_expected)["destination_addresses"][0]
    address = dict(
        userdata=U,
        sentinel=P + 14,
        old_vector=first_fixture["vector_begin"],
        source_payload=source_node + 20,
        first_node_key=destination_node + 16,
        key_bytes=raw(capture["pages"], destination_node + 16),
        stack=first_fixture["entry"] - 12,
        fs=0,
    )[region]
    corrupted = copy.deepcopy(capture)
    corrupted["pages"] = change(
        corrupted["pages"], address, raw(corrupted["pages"], address, 1) ^ 1, 1
    )
    before, reached = copy.deepcopy(corrupted), []

    def forbidden(*args, **kwargs):
        reached.append(True)
        raise AssertionError("host binder reached before capture rejection")

    monkeypatch.setattr(c.normal.first.entry, "_resume", forbidden)
    with pytest.raises(RuntimeError, match="verified callback capture differs"):
        c._resume(produced, first_fixture, corrupted, vector)
    assert corrupted == before and reached == []


def test_second_host_byte_patch_replay_and_disjoint_explicit_key_storage(cases):
    for vector, produced, first_fixture, _, capture, fixture, _ in cases:
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
        first_keys, second_keys = selected_keys(vector)
        assert fixture["callback_vector"]["source_keys"] == list(reversed(second_keys))
        assert fixture["callback_vector"]["payload_seed"] == 0xAD7300FF
        assert len(fixture["second_key_bindings"]) == len(second_keys)
        for index, key in enumerate(reversed(second_keys)):
            node = fixture["prototype"]["source_addresses"][index]
            pointer = 0x1D000FFF + 32 * index + 3
            value = f"{key:08x}".encode() + b"\0"
            assert node == 0x14001000 + 64 * index + 31
            assert raw(fixture["pages"], node + 16) == pointer
            assert span(fixture["pages"], pointer, 9) == value
            assert fixture["prototype"]["strings"][pointer] == value
            assert fixture["second_key_bindings"][index] == dict(
                node=node,
                key_pointer=pointer,
                bytes=9,
                sha256=hashlib.sha256(value).hexdigest(),
            )
            assert (
                raw(fixture["pages"], node + 20)
                == (0xAD7300FF ^ (index * 0x01010101)) & 0xFFFFFFFF
            )
        for index, key in enumerate(reversed(first_keys)):
            pointer = 0x1C000FFF + 32 * index + 3
            assert span(fixture["pages"], pointer, 9) == f"{key:08x}".encode() + b"\0"
            assert span(fixture["pages"], pointer, 9) == span(
                capture["pages"], pointer, 9
            )
        assert all(
            binding["key_pointer"] not in first_fixture["prototype"]["strings"]
            for binding in fixture["second_key_bindings"]
        )
        assert_canonical_tree(fixture["prototype"]["source_state"], second_keys)
        source_tree = fixture["prototype"]["source_state"]["tree"]
        addresses = fixture["prototype"]["source_addresses"]
        at = lambda identity: 0x14000100 if identity is None else addresses[identity]
        for identity, node in enumerate(source_tree["nodes"]):
            assert [
                raw(fixture["pages"], addresses[identity] + offset)
                for offset in (0, 4, 8)
            ] == [at(node[field]) for field in ("left", "parent", "right")]
            assert raw(fixture["pages"], addresses[identity] + 12, 1) == node["color"]
            assert raw(fixture["pages"], addresses[identity] + 13, 1) == 0
        assert [raw(fixture["pages"], 0x14000100 + offset) for offset in (0, 4, 8)] == [
            addresses[-1],
            at(source_tree["root"]),
            addresses[0],
        ]
        assert raw(fixture["pages"], 0x14000100 + 12, 1) == 1
        assert (
            raw(fixture["pages"], 0x14000100 + 13, 1)
            == fixture["callback_vector"]["nil_flag"]
        )
        for name in ("first_pointer", "second_pointer"):
            pointer = produced["fixture"][name]
            assert span(fixture["pages"], pointer, vector["length"] + 1) == span(
                produced["pages"], pointer, vector["length"] + 1
            )


@pytest.mark.parametrize(
    "field",
    ("key_pointer", "key_bytes", "payload", "left", "parent", "right", "color", "nil"),
)
def test_coordinated_retained_node_corruption_rejected_before_host_even_with_new_sha(
    cases, monkeypatch, field
):
    vector, produced, first_fixture, first_expected, capture, _, _ = cases[-1]
    corrupted = copy.deepcopy(capture)
    node = class_result(first_expected)["destination_addresses"][0]
    address, width = (
        (raw(corrupted["pages"], node + 16), 1)
        if field == "key_bytes"
        else (
            node
            + {
                "key_pointer": 16,
                "payload": 20,
                "left": 0,
                "parent": 4,
                "right": 8,
                "color": 12,
                "nil": 13,
            }[field],
            1 if field in ("color", "nil") else 4,
        )
    )
    corrupted["pages"] = change(
        corrupted["pages"], address, raw(corrupted["pages"], address, width) ^ 1, width
    )
    corrupted["observation"]["memory_sha256"] = page_sha(corrupted["pages"])
    before, reached = copy.deepcopy(corrupted), []

    def forbidden(*args, **kwargs):
        reached.append(True)
        raise AssertionError("host binder reached before retained-tree rejection")

    monkeypatch.setattr(c.normal.first.entry, "_resume", forbidden)
    with pytest.raises(RuntimeError, match="extension retained first tree differs"):
        c._resume(produced, first_fixture, corrupted, vector)
    assert corrupted == before and reached == []


@pytest.mark.parametrize(
    "register", ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
)
def test_coordinated_first_return_gpr_and_observation_rejected_before_host(
    cases, monkeypatch, register
):
    vector, produced, first_fixture, _, capture, _, _ = cases[-1]
    corrupted = copy.deepcopy(capture)
    corrupted["registers"][register] ^= 1
    corrupted["observation"]["registers"][register] ^= 1
    before, reached = copy.deepcopy(corrupted), []

    def forbidden(*args, **kwargs):
        reached.append(True)
        raise AssertionError(
            "host binder reached before independent first-return rejection"
        )

    monkeypatch.setattr(c.normal.first.entry, "_resume", forbidden)
    with pytest.raises(RuntimeError, match="extension retained first tree differs"):
        c._resume(produced, first_fixture, corrupted, vector)
    assert corrupted == before and reached == []


@pytest.mark.parametrize(
    "region",
    (
        "receiver_word",
        "vector_pointer",
        "tree_count",
        "userdata_tail",
        "sentinel_link",
        "sentinel_tail",
        "old_record",
    ),
)
def test_coordinated_retained_receiver_sentinel_record_corruption_rejected_before_host(
    cases, monkeypatch, region
):
    vector, produced, first_fixture, _, capture, _, _ = cases[-1]
    address = dict(
        receiver_word=U,
        vector_pointer=U + 4,
        tree_count=U + 56,
        userdata_tail=U + 68,
        sentinel_link=P + 4,
        sentinel_tail=P + 16,
        old_record=first_fixture["vector_begin"] + 4,
    )[region]
    corrupted = copy.deepcopy(capture)
    corrupted["pages"] = change(
        corrupted["pages"], address, raw(corrupted["pages"], address) ^ 1
    )
    corrupted["observation"]["memory_sha256"] = page_sha(corrupted["pages"])
    before, reached = copy.deepcopy(corrupted), []

    def forbidden(*args, **kwargs):
        reached.append(True)
        raise AssertionError("host binder reached before retained-storage rejection")

    monkeypatch.setattr(c.normal.first.entry, "_resume", forbidden)
    with pytest.raises(RuntimeError, match="extension retained first tree differs"):
        c._resume(produced, first_fixture, corrupted, vector)
    assert corrupted == before and reached == []


def test_second_host_retains_actual_receiver_sentinel_old_vector_and_first_nodes(cases):
    for vector, _, first_fixture, first_expected, capture, fixture, expected in cases:
        retained = [(U, 72), (P, 24), (first_fixture["vector_begin"], 8)]
        retained += [
            (node, 24) for node in class_result(first_expected)["destination_addresses"]
        ]
        retained += [
            (pointer, len(value))
            for pointer, value in first_fixture["prototype"]["strings"].items()
        ]
        for address, width in retained:
            assert span(fixture["pages"], address, width) == span(
                capture["pages"], address, width
            )
        cv = fixture["callback_vector"]
        assert (
            raw(fixture["pages"], 0) == cv["previous_seh"] == raw(capture["pages"], 0)
        )
        assert raw(expected["pages"], 0) == raw(capture["pages"], 0)
        assert cv["cookie"] == raw(capture["pages"], 0x00893F28)
        for field in ("source_word", "source_refs", "destination_refs", "transfers"):
            assert cv[field] == first_fixture["callback_vector"][field]
        assert raw(fixture["pages"], U) == cv["source_word"]
        assert (
            fixture["prototype"]["old_begin"]
            == first_fixture["vector_begin"]
            == 0x06002000 + vector["vector_alignment"]
        )
        assert fixture["prototype"]["old_base"] == first_fixture["vector_begin"] & ~4095
        assert fixture["prototype"]["new_page_count"] == 2
        assert fixture["vector_begin"] == 0x06001000 + vector["vector_alignment"]
        assert fixture["prototype"]["node"] == c.old.construction.DATA + 0x400 + 31


def test_union_preserves_existing_ids_unvisited_payload_and_routes_sorted_new_keys(
    cases,
):
    modes = set()
    for vector, _, _, first_expected, capture, fixture, expected in cases:
        first_keys, second_keys = selected_keys(vector)
        first_nodes = class_result(first_expected)["destination_addresses"]
        child = class_result(expected)
        new_keys = sorted(set(second_keys) - set(first_keys))
        keys_by_id = list(first_keys) + new_keys
        nodes = first_nodes + [
            c.old.construction.DATA + 0x400 + 31 + 32 * i for i in range(len(new_keys))
        ]
        assert child["destination_addresses"] == nodes
        assert fixture["prototype"]["destination_addresses"] == first_nodes
        assert child["tree_heap_count"] == len(new_keys)
        assert child["heap_nodes"] == nodes[3:] + [fixture["vector_begin"]]
        expected_copies, current_keys = [], set(first_keys)
        for index, key in enumerate(sorted(second_keys)):
            source_id = len(second_keys) - index - 1
            destination_id = keys_by_id.index(key)
            inserted = key not in current_keys
            mode = (
                "existing"
                if not inserted
                else (
                    "minimum"
                    if key < min(current_keys)
                    else "end" if key > max(current_keys) else "interior"
                )
            )
            modes.add(mode)
            value = (0xAD7300FF ^ (source_id * 0x01010101)) & 0xFFFFFFFF
            expected_copies.append(
                dict(
                    source=source_id,
                    key=key,
                    destination_address=nodes[destination_id],
                    inserted=inserted,
                    mode=mode,
                    payload=value,
                    heap_node=nodes[destination_id] if inserted else None,
                )
            )
            current_keys.add(key)
            assert raw(expected["pages"], nodes[destination_id] + 20) == value
            pointer = (
                raw(
                    fixture["pages"],
                    fixture["prototype"]["source_addresses"][source_id] + 16,
                )
                if inserted
                else raw(capture["pages"], nodes[destination_id] + 16)
            )
            assert raw(expected["pages"], nodes[destination_id] + 16) == pointer
            assert span(expected["pages"], pointer, 9) == f"{key:08x}".encode() + b"\0"
        assert child["insertions"] == expected_copies
        for index, key in enumerate(first_keys):
            assert raw(expected["pages"], nodes[index] + 16) == raw(
                capture["pages"], nodes[index] + 16
            )
            if key not in second_keys:
                assert raw(expected["pages"], nodes[index] + 20) == raw(
                    capture["pages"], nodes[index] + 20
                )
        assert 16 not in second_keys
        omitted = first_keys.index(16)
        assert raw(expected["pages"], nodes[omitted] + 20) == raw(
            capture["pages"], nodes[omitted] + 20
        )
        logical = c._logical(fixture)
        state = logical["callback_operation"]["destination"]
        assert [node["key"] for node in state["tree"]["nodes"]] == keys_by_id
        assert_canonical_tree(state, current_keys)
        at = lambda identity: P if identity is None else nodes[identity]
        for identity, node in enumerate(state["tree"]["nodes"]):
            assert [
                raw(expected["pages"], nodes[identity] + offset) for offset in (0, 4, 8)
            ] == [at(node[field]) for field in ("left", "parent", "right")]
            assert raw(expected["pages"], nodes[identity] + 12, 1) == node["color"]
        assert (
            raw(expected["pages"], U + 56) == logical["tree_count"] == len(current_keys)
        )
        links = logical["sentinel_link_ids"]
        assert links["leftmost"] == keys_by_id.index(min(current_keys))
        assert links["rightmost"] == keys_by_id.index(max(current_keys))
        assert links["root"] == state["tree"]["root"]
        assert [raw(expected["pages"], P + offset) for offset in (0, 4, 8)] == [
            at(links[field]) for field in ("leftmost", "root", "rightmost")
        ]
    assert modes == {"existing", "minimum", "interior", "end"}


def test_vector_copy_append_free_and_preserved_bytes(cases):
    for vector, _, first_fixture, _, capture, fixture, expected in cases:
        logical = c._logical(fixture)
        pointer, old_begin = fixture["vector_begin"], first_fixture["vector_begin"]
        pair = b"\0" * 4 + SOURCE.to_bytes(4, "little")
        assert (
            span(capture["pages"], old_begin, 8)
            == span(expected["pages"], old_begin, 8)
            == pair
        )
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
        first_keys, second_keys = selected_keys(vector)
        assert logical["tree_heap_requests"] == [
            dict(continuation=0x789463, handle=0x12345678, flags=0, bytes=24)
        ] * len(set(second_keys) - set(first_keys))
        assert logical["sentinel_preserved_offsets"] == list(range(12, 24))
        assert span(expected["pages"], P + 12, 12) == span(capture["pages"], P + 12, 12)
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


def test_both_normal_abi_returns_and_identity_bound_lua_are_independent_of_union(cases):
    for _, produced, first_fixture, first_expected, capture, fixture, expected in cases:
        result = c.model.apply(
            first_arguments=fixture["first_arguments"],
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
        assert fixture["first_arguments"] == c.repeat._first_arguments(
            first_fixture, produced
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
    (
        "allocation_count",
        "closure_target",
        "upvalue",
        "source_payload",
        "source_tree",
        "register",
    ),
)
def test_strict_retained_identity_payload_topology_and_register_premises(
    cases, mutation
):
    vector, produced, first_fixture, _, capture, fixture, _ = cases[-1]
    produced, first_fixture, capture, fixture = copy.deepcopy(
        (produced, first_fixture, capture, fixture)
    )
    if mutation == "allocation_count":
        capture["observation"]["allocations"].pop(0)
        with pytest.raises(RuntimeError, match="extension retained first tree differs"):
            c._resume(produced, first_fixture, capture, vector)
        return
    if mutation == "closure_target":
        fixture["first_arguments"]["closure_target"] ^= 1
    elif mutation == "upvalue":
        fixture["first_arguments"]["closure_upvalues"][0] ^= 1
    elif mutation == "source_payload":
        fixture["prototype"]["source_state"]["payloads"][0] = True
    elif mutation == "source_tree":
        fixture["prototype"]["source_state"]["tree"]["nodes"][0]["color"] = True
    else:
        fixture["registers"]["eax"] ^= 1
    with pytest.raises(RuntimeError):
        c._logical(fixture)


def test_all_adapter_metadata_outputs_detached_from_first_fixture_capture_and_producer(
    cases,
):
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
    resumed["second_key_bindings"][0]["key_pointer"] ^= 1
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
        PREFIX + "native_lua_class_factory_callback_extend_conformance.json"
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


def test_sealed_receipt_encoding_sources_and_independent_extension_arithmetic(receipts):
    path, evidence, _, sources = receipts
    assert c.SEALED_SHA256 != "UNSEALED" and len(c.SEALED_SHA256) == 64
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert len(path.read_bytes()) == 590914
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert path.read_bytes().endswith(b"\n") and b"\r" not in path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert set(sources) == set(c.SOURCE_PINS) and len(sources) == 32
    assert c.SOURCE_PINS["factory_callback_repeat"] == (
        c.repeat.ANALYSIS_KIND,
        c.repeat.SEALED_SHA256,
    )
    assert c.SOURCE_PINS["factory_callback_tree"] == (
        c.tree.ANALYSIS_KIND,
        c.tree.SEALED_SHA256,
    )
    summary = evidence["summary"]
    assert summary["cases"] == 864 and summary["callback_invocations"] == 1728
    assert summary["static_sites"] == 1115
    assert summary["executed_sites"] == 881
    assert summary["instruction_bytes"] == 2905
    assert summary["factory_instructions"] == 573120
    assert summary["first_callback_instructions"] == 1305504
    assert summary["second_callback_instructions"] == 1599804
    assert summary["factory_api_calls"] == 29376
    assert summary["callback_api_calls"] == 70848
    assert summary["factory_heap_calls"] == 864
    assert summary["first_class_heap_calls"] == 3456
    assert summary["first_tree_nodes"] == 2592
    assert summary["second_class_heap_calls"] == 2916
    assert summary["second_tree_allocations"] == 2052
    assert summary["second_payload_updates"] == 756
    assert summary["second_source_copies"] == 2808
    assert summary["final_tree_nodes"] == 4644
    assert summary["copied_old_vector_bytes"] == 6912
    assert summary["second_vector_bytes"] == 13824
    assert summary["free_calls"] == 864
    assert summary["marker_calls"] == summary["table_calls"] == 3456
    assert summary["requested_assignments"] == 1728
    assert summary["retained_lua_values_per_call"] == 5 and summary["result_count"] == 0
    assert (
        summary["opaque_native_instructions"] == summary["accounting_promotions"] == 0
    )
    assert evidence["scope"]["continuous_each_callback"] is True
    assert evidence["scope"]["continuous_across_host"] is False


def test_selected_site_partition_and_first_corpus_overlap_are_explicit(receipts):
    _, evidence, _, sources = receipts
    first, second, union = (
        set(evidence[key])
        for key in ("first_executed_rvas", "second_executed_rvas", "executed_rvas")
    )
    assert union == first | second and second - first
    assert first <= set(sources["factory_callback_tree"]["executed_rvas"])
    assert first == set(
        sources["factory_callback_tree"]["families"]["3"]["executed_rvas"]
    )
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
    assert len(first) == 701 and len(second) == 864
    assert tuple(map(len, groups)) == (76, 707, 27, 71)
    assert len(partition["excluded"]) == 234
    assert (
        sum(point["size"] for point in evidence["body"]["points"])
        == evidence["summary"]["instruction_bytes"]
    )


def test_native_free_cookie_capture_and_retained_tree_controls_are_independently_scoped(
    receipts,
):
    _, evidence, _, _ = receipts
    reasons = dict(c.tree.CONTROLS)
    reasons.update(
        free_request="callback free handoff differs",
        free_register="factory return free ABI differs",
        free_flags="factory return free ABI differs",
        free_identity="factory return free response identity differs",
        old="callback protected memory differs",
    )
    assert c.CONTROLS == reasons and len(reasons) == 33
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
    assert len(controls) == evidence["summary"]["controls"] == 40
    for key, reason in reasons.items():
        assert controls[key] == dict(kind=key, rejected=True, reason=reason)
    for key in retained:
        assert controls[key] == dict(
            kind=key, rejected=True, reason="extension retained first tree differs"
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
        "first_sites",
        "second_sites",
        "callback",
        "class_operation",
        "markers",
        "tables",
        "excluded",
        "host_claim",
    ),
)
def test_tampered_receipt_rejected_by_seal(receipts, mutation):
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


@pytest.mark.parametrize("mutation", ("missing", "extra", "pin", "kind"))
def test_strict_source_partition_and_content_pins(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["factory_callback_repeat"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["factory_callback_repeat"]["schema_version"] += 1
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
    noncanonical = tmp_path / "callback-extend.json"
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
