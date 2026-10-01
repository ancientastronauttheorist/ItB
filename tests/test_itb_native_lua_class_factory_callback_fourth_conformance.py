"""Independent fourth-call capture and physical laws; native replay is CLI gated."""

import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.observatory import native_lua_class_factory_callback_fourth_conformance as c

ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "src/observatory").is_dir()
)
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_callback_fourth_conformance.py"
U, P, SOURCE = 0x0FFFFFCC, 0x10000100, 0x14000000
DATA = 0x06000000
FIRST_KEYS = ((0, 1, 16), (1, 16, 255))
SECOND_KEYS = (0, 1, 7, 17, 255, 0x80000000, 0xFFFFFFFF)
CANONICAL = "3b0727908ddef36b171733a0c686e0ad2dbe1a08ac3e7937834cd9158feced5a"  # Sealed receipt: canonical SHA-256.
RAW = "0261f2a79114245ef8b96cc7d8597d0ebacd6c5cf6eee9adc5c4212ff4b6432e"  # Sealed receipt: exact LF-encoded receipt SHA-256.
RECEIPT_BYTES = 359299  # Sealed receipt: raw receipt length.
FOURTH_INSTRUCTIONS = 537840  # Sealed receipt: measured fourth instruction total.
CALLBACK_API_CALLS = 35424  # Sealed receipt: measured four-stage API total.
FOURTH_SITES = 548  # Sealed receipt: measured fourth executed-site count.
UNION_SITES = 881  # Sealed receipt: four-stage executed-site union.
CLASS_SITES = 707  # Sealed receipt: class-operation partition count.
EXCLUDED_SITES = 234  # Sealed receipt: excluded partition count.


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


def capture(expected, allocations):
    result = dict(
        pages=copy.deepcopy(expected["pages"]),
        registers=copy.deepcopy(expected["registers"]),
    )
    result["observation"] = dict(
        registers=copy.deepcopy(result["registers"]),
        memory_sha256=page_sha(result["pages"]),
        allocations=copy.deepcopy(allocations),
    )
    return result


@pytest.fixture(scope="module")
def cases():
    # These are synthetic physical-law packets, not native observations. Exact
    # native replay occurs only in the explicitly gated CLI test below.
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
        f1 = c.extend._resume_first(produced, vector)
        e1 = c.callback._expected(f1["callback_vector"], f1, class_module=c.tree.empty)
        nodes1 = class_result(e1)["destination_addresses"]
        cap1 = capture(
            e1,
            [dict(node=node, request=24) for node in nodes1]
            + [dict(node=f1["vector_begin"], request=8)],
        )
        f2 = c.extend._resume(produced, f1, cap1, vector)
        e2 = c.callback._expected(f2["callback_vector"], f2, class_module=c.old)
        nodes2 = class_result(e2)["destination_addresses"]
        cap2 = capture(
            e2,
            [dict(node=node, request=24) for node in nodes2[3:]]
            + [dict(node=f2["vector_begin"], request=16)],
        )
        f3 = c.third._resume(produced, f2, cap2, vector)
        e3 = c.callback._expected(f3["callback_vector"], f3, class_module=c.old)
        # This sole 24-byte allocation is a vector, never an additional node.
        cap3 = capture(e3, [dict(node=f3["vector_begin"], request=24)])
        cap3["observation"]["frees"] = [
            dict(
                pointer=f3["second_vector_pointer"],
                entry_esp=f3["entry"] - 180,
                result=1,
                continuation=0x789172,
            )
        ]
        f4 = c._resume(produced, f3, cap3, vector)
        e4 = c.callback._expected(f4["callback_vector"], f4, class_module=c.old)
        result.append(
            dict(
                v=vector,
                produced=produced,
                f1=f1,
                e1=e1,
                cap1=cap1,
                f2=f2,
                e2=e2,
                cap2=cap2,
                f3=f3,
                e3=e3,
                cap3=cap3,
                f4=f4,
                e4=e4,
            )
        )
    assert len(producers) == 2 and len(result) == 24
    return result


def test_exact_216_product_and_independent_four_call_arithmetic():
    vectors = c.vectors()
    assert vectors == c.third.vectors() and len(vectors) == 216
    assert all(
        v["source_size"] == 3 and v["node_alignment"] == 31 and v["source_profile"] == 3
        for v in vectors
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
                (key, value)
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
            )
        )
        for vector in vectors
    }
    assert len(producer_keys) == 18
    assert {v["profile"] for v in vectors} == {0, 1}
    assert {v["length"] for v in vectors} == {0, 16, 255}
    assert {v["registry_profile"] for v in vectors} == {0, 1, 2}
    assert 4 * len(vectors) == 864 and 3 * len(vectors) == 648
    assert 5 * len(vectors) == 1080 and 8 * len(vectors) == 1728


def test_third_captured_pages_and_all_gprs_match_verified_return_before_fourth_host(
    cases,
):
    for row in cases:
        cap, f3, f4 = row["cap3"], row["f3"], row["f4"]
        assert cap["pages"] == row["e3"]["pages"]
        assert (
            cap["registers"]
            == row["e3"]["registers"]
            == cap["observation"]["registers"]
            == c._prior(f3)["full_return"]["registers"]
        )
        assert (
            page_sha(cap["pages"])
            == cap["observation"]["memory_sha256"]
            == f4["captured_pages_sha256"]
        )
        assert f4["registers"] == dict(cap["registers"], esp=f4["entry"])


@pytest.mark.parametrize(
    "register", ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
)
@pytest.mark.parametrize("coordinated", (False, True))
def test_corrupted_third_gpr_rejected_before_fourth_host(
    cases, monkeypatch, register, coordinated
):
    row = cases[-1]
    corrupted = copy.deepcopy(row["cap3"])
    corrupted["registers"][register] ^= 1
    if coordinated:
        corrupted["observation"]["registers"][register] ^= 1
    before, reached = copy.deepcopy(corrupted), []

    def forbidden(*args, **kwargs):
        reached.append(True)
        raise AssertionError("fourth host binder reached before GPR rejection")

    monkeypatch.setattr(c.normal.first.entry, "_resume", forbidden)
    reason = (
        "retained third callback differs"
        if coordinated
        else "verified third callback capture differs"
    )
    with pytest.raises(RuntimeError, match=reason):
        c._resume(row["produced"], row["f3"], corrupted, row["v"])
    assert corrupted == before and reached == []


def protected_region(row, region):
    cap, f3 = row["cap3"], row["f3"]
    node = class_result(row["e3"])["destination_addresses"][0]
    source_node = f3["prototype"]["source_addresses"][0]
    old_key = next(
        pointer
        for pointer in f3["prototype"]["strings"]
        if 0x1C000000 <= pointer < 0x1D000000
    )
    return dict(
        left=(node, 4),
        parent=(node + 4, 4),
        right=(node + 8, 4),
        color=(node + 12, 1),
        nil=(node + 13, 1),
        padding14=(node + 14, 1),
        padding15=(node + 15, 1),
        key_pointer=(node + 16, 4),
        payload=(node + 20, 4),
        old_key_bytes=(old_key, 1),
        new_key_bytes=(raw(cap["pages"], source_node + 16), 1),
        receiver_word=(U, 4),
        vector_pointer=(U + 4, 4),
        count=(U + 56, 4),
        userdata_tail=(U + 68, 4),
        sentinel_link=(P + 4, 4),
        sentinel_tail=(P + 16, 4),
        third_vector_record=(f3["vector_begin"] + 20, 4),
        second_vector_record=(f3["second_vector_pointer"] + 12, 4),
        first_vector_record=(f3["first_arguments"]["vector_pointer"] + 4, 4),
        fs=(0, 4),
        cookie=(0x00893F28, 4),
        new_page3=(DATA + 0x3FF0, 4),
        source_payload=(source_node + 20, 4),
        stack=(f3["entry"] - 24, 4),
    )[region]


@pytest.mark.parametrize(
    "region",
    (
        "receiver_word",
        "count",
        "sentinel_tail",
        "third_vector_record",
        "second_vector_record",
        "first_vector_record",
        "payload",
        "old_key_bytes",
        "new_key_bytes",
        "fs",
        "cookie",
        "new_page3",
        "source_payload",
        "stack",
    ),
)
def test_stale_captured_memory_digest_rejected_before_fourth_host(
    cases, monkeypatch, region
):
    row = cases[-1]
    address, width = protected_region(row, region)
    corrupted = copy.deepcopy(row["cap3"])
    corrupted["pages"] = change(
        corrupted["pages"], address, raw(corrupted["pages"], address, width) ^ 1, width
    )
    before, reached = copy.deepcopy(corrupted), []

    def forbidden(*args, **kwargs):
        reached.append(True)
        raise AssertionError("fourth host binder reached before digest rejection")

    monkeypatch.setattr(c.normal.first.entry, "_resume", forbidden)
    with pytest.raises(RuntimeError, match="verified third callback capture differs"):
        c._resume(row["produced"], row["f3"], corrupted, row["v"])
    assert corrupted == before and reached == []


@pytest.mark.parametrize(
    "region",
    (
        "left",
        "parent",
        "right",
        "color",
        "nil",
        "padding14",
        "padding15",
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
        "third_vector_record",
        "second_vector_record",
        "first_vector_record",
        "fs",
        "cookie",
        "new_page3",
    ),
)
def test_refreshed_capture_digest_cannot_hide_retained_third_corruption(
    cases, monkeypatch, region
):
    row = cases[-1]
    address, width = protected_region(row, region)
    corrupted = copy.deepcopy(row["cap3"])
    corrupted["pages"] = change(
        corrupted["pages"], address, raw(corrupted["pages"], address, width) ^ 1, width
    )
    corrupted["observation"]["memory_sha256"] = page_sha(corrupted["pages"])
    before, reached = copy.deepcopy(corrupted), []

    def forbidden(*args, **kwargs):
        reached.append(True)
        raise AssertionError(
            "fourth host binder reached before retained-state rejection"
        )

    monkeypatch.setattr(c.normal.first.entry, "_resume", forbidden)
    with pytest.raises(RuntimeError, match="retained third callback differs"):
        c._resume(row["produced"], row["f3"], corrupted, row["v"])
    assert corrupted == before and reached == []


def test_fourth_exact_named_byte_replay_changes_only_invocation_and_source_payloads(
    cases,
):
    for row in cases:
        produced, f3, cap, f4 = row["produced"], row["f3"], row["cap3"], row["f4"]
        boundary = c.normal.first.entry._resume(
            dict(produced, pages=cap["pages"], registers=cap["registers"]),
            c.tree._normal_vector(c.extend._base_vector(row["v"])),
            callback_entry=f3["entry"],
        )
        assert f4["patches"][: len(boundary["patches"])] == boundary["patches"]
        addresses = f3["prototype"]["source_addresses"]
        assert [
            patch["address"] for patch in f4["patches"][len(boundary["patches"]) :]
        ] == [node + 20 + index for node in addresses for index in range(4)]
        replay = {page: bytearray(payload) for page, payload in cap["pages"].items()}
        for patch in f4["patches"]:
            page, offset = patch["address"] & ~4095, patch["address"] & 4095
            assert page in replay  # Every page is an actual captured page.
            assert replay[page][offset] == patch["before"]
            replay[page][offset] = patch["after"]
        assert {page: bytes(payload) for page, payload in replay.items()} == f4["pages"]
        assert f4["pages"][DATA + 0x3000] == cap["pages"][DATA + 0x3000]
        assert (
            f4["prototype"]["source_state"]["tree"]
            == f3["prototype"]["source_state"]["tree"]
        )
        for identity, node in enumerate(addresses):
            before = raw(cap["pages"], node + 20)
            assert span(f4["pages"], node, 20) == span(cap["pages"], node, 20)
            assert (
                raw(f4["pages"], node + 20)
                == f4["prototype"]["source_state"]["payloads"][identity]
                == before ^ 0xFFFFFFFF
            )
        assert raw(f4["pages"], c.old.growth.FREE_IAT) == c.normal.layout.HEAP_TARGET


def test_fourth_retains_receiver_sentinel_all_vectors_nodes_keys_fs_cookie_and_page3(
    cases,
):
    for row in cases:
        f3, f4, cap = row["f3"], row["f4"], row["cap3"]
        retained = [
            (U, 72),
            (P, 24),
            (row["f1"]["vector_begin"], 8),
            (row["f2"]["vector_begin"], 16),
            (f3["vector_begin"], 24),
            (DATA + 0x3000, 4096),
        ]
        retained += [
            (node, 24) for node in class_result(row["e3"])["destination_addresses"]
        ]
        retained += [
            (pointer, len(value))
            for pointer, value in f3["prototype"]["strings"].items()
        ]
        for address, width in retained:
            assert span(f4["pages"], address, width) == span(
                cap["pages"], address, width
            )
        cv = f4["callback_vector"]
        assert (
            raw(f4["pages"], 0)
            == raw(row["e4"]["pages"], 0)
            == cv["previous_seh"]
            == raw(cap["pages"], 0)
        )
        assert (
            cv["cookie"]
            == raw(f4["pages"], 0x00893F28)
            == raw(cap["pages"], 0x00893F28)
        )
        for field in (
            "source_word",
            "source_refs",
            "destination_refs",
            "transfers",
            "source_keys",
        ):
            assert cv[field] == f3["callback_vector"][field]
        proto = f4["prototype"]
        assert cv["old_size"] == proto["old_size"] == 3
        assert (
            proto["old_base"] == DATA
            and proto["old_begin"]
            == f3["vector_begin"]
            == DATA + 0x800 + row["v"]["vector_alignment"]
        )
        assert proto["new_base"] == DATA + 0x3000 and proto["new_page_count"] == 1
        assert f4["vector_begin"] == DATA + 0x3800 + row["v"]["vector_alignment"]
        assert proto["node"] == f3["prototype"]["node"]
        assert f4["third_vector_pointer"] == f3["vector_begin"]
        assert f4["third_source_state"] == f3["prototype"]["source_state"]
        assert (
            f4["third_registers"] == f3["registers"]
            and f4["third_entry"] == f3["entry"]
        )
        for name in ("first_pointer", "second_pointer"):
            pointer = row["produced"]["fixture"][name]
            assert span(row["e4"]["pages"], pointer, row["v"]["length"] + 1) == span(
                row["produced"]["pages"], pointer, row["v"]["length"] + 1
            )


def test_fourth_existing_payload_routing_retains_eight_ids_links_and_omitted_key16(
    cases,
):
    for row in cases:
        f3, f4, cap, expected = row["f3"], row["f4"], row["cap3"], row["e4"]
        nodes = class_result(row["e3"])["destination_addresses"]
        child = class_result(expected)
        assert nodes[:3] == class_result(row["e1"])["destination_addresses"]
        assert (
            f4["prototype"]["destination_addresses"]
            == child["destination_addresses"]
            == nodes
        )
        assert (
            len(nodes) == 8
            and child["tree_heap_count"] == 0
            and child["heap_nodes"] == [f4["vector_begin"]]
        )
        assert span(expected["pages"], f4["prototype"]["node"], 24) == span(
            cap["pages"], f4["prototype"]["node"], 24
        )
        first_keys = FIRST_KEYS[row["v"]["first_key_profile"]]
        keys_by_id = list(first_keys) + sorted(set(SECOND_KEYS) - set(first_keys))
        copies = []
        for index, key in enumerate(SECOND_KEYS):
            source_id, destination_id = 6 - index, keys_by_id.index(key)
            source_node = f3["prototype"]["source_addresses"][source_id]
            value = raw(cap["pages"], source_node + 20) ^ 0xFFFFFFFF
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
        for identity, node in enumerate(nodes):
            assert span(expected["pages"], node, 20) == span(cap["pages"], node, 20)
            pointer = raw(expected["pages"], node + 16)
            assert (
                span(expected["pages"], pointer, 9)
                == f"{keys_by_id[identity]:08x}".encode() + b"\0"
            )
        assert raw(expected["pages"], nodes[keys_by_id.index(16)] + 20) == raw(
            cap["pages"], nodes[keys_by_id.index(16)] + 20
        )
        logical, prior = c._logical(f4), c._prior(f3)
        assert (
            logical["callback_operation"]["destination"]["tree"]
            == prior["callback_operation"]["destination"]["tree"]
        )
        assert (
            raw(expected["pages"], U + 56)
            == raw(cap["pages"], U + 56)
            == logical["tree_count"]
            == 8
        )
        assert span(expected["pages"], P, 24) == span(cap["pages"], P, 24)
        links = logical["sentinel_link_ids"]
        assert links == prior["sentinel_link_ids"]
        assert [raw(expected["pages"], P + offset) for offset in (0, 4, 8)] == [
            P if links[field] is None else nodes[links[field]]
            for field in ("leftmost", "root", "rightmost")
        ]


def test_fourth_copy24_append8_alloc32_capacity4_free_third24_preserves_older_vectors(
    cases,
):
    for row in cases:
        f4, cap, expected = row["f4"], row["cap3"], row["e4"]
        logical, pointer, old = (
            c._logical(f4),
            f4["vector_begin"],
            row["f3"]["vector_begin"],
        )
        pair = b"\0" * 4 + SOURCE.to_bytes(4, "little")
        assert span(cap["pages"], old, 24) == pair * 3
        assert span(expected["pages"], pointer, 24) == span(cap["pages"], old, 24)
        assert span(expected["pages"], pointer + 24, 8) == pair
        for fixture, width in ((row["f1"], 8), (row["f2"], 16), (row["f3"], 24)):
            assert (
                span(expected["pages"], fixture["vector_begin"], width)
                == span(cap["pages"], fixture["vector_begin"], width)
                == pair * (width // 8)
            )
        assert [raw(expected["pages"], U + offset) for offset in (4, 8, 12)] == [
            pointer,
            pointer + 32,
            pointer + 32,
        ]
        assert logical["vector"] == dict(
            records=[[0, SOURCE] for _ in range(4)],
            capacity=4,
            begin=pointer,
            end=pointer + 32,
            capacity_pointer=pointer + 32,
        )
        assert logical["vector_heap_request"] == dict(
            continuation=0x789463, handle=0x12345678, flags=0, bytes=32
        )
        assert logical["vector_free_request"] == dict(
            continuation=0x789172, handle=0x12345678, flags=0, pointer=old
        )
        assert logical["tree_heap_requests"] == [] and logical[
            "sentinel_preserved_offsets"
        ] == list(range(24))
        preserved = [
            offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12, 56)
        ]
        assert (
            logical["normal_preserved_userdata_offsets"] == preserved
            and len(preserved) == 13
        )
        for offset in preserved:
            assert raw(expected["pages"], U + offset) == raw(cap["pages"], U + offset)
        # New allocation touches only its named extent within the retained page.
        new_page = DATA + 0x3000
        begin = pointer - new_page
        assert expected["pages"][new_page][:begin] == cap["pages"][new_page][:begin]
        assert (
            expected["pages"][new_page][begin + 32 :]
            == cap["pages"][new_page][begin + 32 :]
        )


def test_successful_free_preserves_protected_old_page0_except_named_tree_payload_updates(
    cases,
):
    for row in cases:
        # Page0 contains both the old 24-byte vector and retained tree nodes.
        # Existing-key copies legitimately update seven payload DWORDs; free
        # must preserve every other page0 byte, including all tree structure.
        original = row["cap3"]["pages"][DATA]
        predicted = bytearray(original)
        child = class_result(row["e4"])
        first_keys = FIRST_KEYS[row["v"]["first_key_profile"]]
        keys_by_id = list(first_keys) + sorted(set(SECOND_KEYS) - set(first_keys))
        nodes = class_result(row["e3"])["destination_addresses"]
        for index, key in enumerate(SECOND_KEYS):
            source_node = row["f3"]["prototype"]["source_addresses"][6 - index]
            payload = raw(row["cap3"]["pages"], source_node + 20) ^ 0xFFFFFFFF
            address = nodes[keys_by_id.index(key)] + 20
            assert address & ~4095 == DATA
            predicted[address - DATA : address - DATA + 4] = payload.to_bytes(
                4, "little"
            )
        assert child["pages"][DATA] == row["e4"]["pages"][DATA] == bytes(predicted)
        assert span(row["e4"]["pages"], row["f3"]["vector_begin"], 24) == span(
            row["cap3"]["pages"], row["f3"]["vector_begin"], 24
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "bool",
        "negative",
        "unaligned",
        "unmapped",
        "wrapping",
        "vector_before",
        "vector_tail",
        "new_old_alias",
    ),
)
def test_direct_callback_expected_rejects_invalid_relocated_new_span(cases, mutation):
    fixture = copy.deepcopy(cases[-1]["f4"])
    prototype = fixture["prototype"]
    if mutation == "vector_before":
        prototype["vector_begin"] = prototype["new_base"] - 1
    elif mutation == "vector_tail":
        prototype["vector_begin"] = prototype["new_base"] + 4096 - 31
    else:
        prototype["new_base"] = dict(
            bool=True,
            negative=-4096,
            unaligned=DATA + 0x3001,
            unmapped=DATA + 0x4000,
            wrapping=0x100000000,
            new_old_alias=DATA,
        )[mutation]
    if mutation in ("vector_before", "vector_tail"):
        prototype["vector_end"] = prototype["vector_begin"] + 24
        prototype["vector_capacity"] = prototype["vector_begin"] + 32
    before = copy.deepcopy(fixture)
    with pytest.raises(RuntimeError):
        c.callback._expected(fixture["callback_vector"], fixture, class_module=c.old)
    assert fixture == before


def test_all_four_abi_packets_identity_bound_lua_and_fourth_cookie(cases):
    for row in cases:
        f4, f3, expected = row["f4"], row["f3"], row["e4"]
        result = c.model.apply(
            first_arguments=f4["first_arguments"],
            second_source_state=f4["second_source_state"],
            second_vector_pointer=f4["second_vector_pointer"],
            second_entry=f4["second_entry"],
            second_registers=f4["second_registers"],
            third_source_state=f4["third_source_state"],
            third_vector_pointer=f4["third_vector_pointer"],
            third_entry=f4["third_entry"],
            third_registers=f4["third_registers"],
            fourth_source_state=f4["prototype"]["source_state"],
            new_vector_pointer=f4["vector_begin"],
            fourth_entry=f4["entry"],
            fourth_registers=f4["registers"],
        )
        for stage, label in (("first", "1"), ("second", "2"), ("third", "3")):
            assert (
                result[stage]["full_return"]["registers"]
                == row["e" + label]["registers"]
                == row["cap" + label]["registers"]
            )
        fourth = result["fourth"]
        assert (
            fourth == c._logical(f4)
            and fourth["full_return"]["registers"] == expected["registers"]
        )
        assert fourth["full_return"]["flags"] == expected["flags"] == 0x44
        assert fourth["full_return"]["endpoint"] == expected["endpoint"] == 0x0400A000
        assert result["first"]["class_return"]["registers"]["edx"] == 0
        assert all(
            result[stage]["class_return"]["registers"]["edx"] == 0xB0000001
            for stage in ("second", "third", "fourth")
        )
        assert all(
            result[stage]["normal_requests"] == fourth["normal_requests"]
            for stage in ("first", "second", "third")
        )
        observer, lua = c.normal._IdentityPrefix(f4), c.callback._Lua(
            f4["callback_vector"]
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
            observer.trace == fourth["prefix_calls"]
            and suffix == fourth["registry_table_calls"]
        )
        assert (
            bound(lua.stack) == fourth["normal_final_lua_stack"] and len(lua.stack) == 5
        )
        assert (
            lua.assignments == fourth["requested_assignments"]
            and fourth["return_count"] == 0
        )
        entry, cookie = f4["entry"], f4["callback_vector"]["cookie"]
        assert fourth["native_cookie"] == dict(
            frame=entry - 52,
            protected_address=entry - 56,
            stored_word=cookie ^ (entry - 52),
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "allocation_count",
        "allocation_node",
        "allocation_request",
        "free_count",
        "free_pointer",
        "free_result",
        "free_continuation",
        "free_stack",
        "closure_target",
        "upvalue",
        "source_payload",
        "source_tree",
        "register",
        "third_register",
        "third_vector",
    ),
)
def test_strict_third_capture_identity_schema_topology_and_register_premises(
    cases, mutation
):
    row = copy.deepcopy(cases[-1])
    f4, cap = row["f4"], row["cap3"]
    if mutation.startswith("allocation_"):
        if mutation == "allocation_count":
            cap["observation"]["allocations"].append(
                dict(node=DATA + 0x61F, request=24)
            )
        elif mutation == "allocation_node":
            cap["observation"]["allocations"][0]["node"] ^= 1
        else:
            cap["observation"]["allocations"][0]["request"] = 32
        with pytest.raises(RuntimeError, match="retained third callback differs"):
            c._resume(row["produced"], row["f3"], cap, row["v"])
        return
    if mutation.startswith("free_"):
        if mutation == "free_count":
            cap["observation"]["frees"].clear()
        else:
            field = dict(
                free_pointer="pointer",
                free_result="result",
                free_continuation="continuation",
                free_stack="entry_esp",
            )[mutation]
            cap["observation"]["frees"][0][field] ^= 1
        with pytest.raises(RuntimeError, match="retained third callback differs"):
            c._resume(row["produced"], row["f3"], cap, row["v"])
        return
    if mutation == "closure_target":
        f4["first_arguments"]["closure_target"] ^= 1
    elif mutation == "upvalue":
        f4["first_arguments"]["closure_upvalues"][0] ^= 1
    elif mutation == "source_payload":
        f4["prototype"]["source_state"]["payloads"][0] = True
    elif mutation == "source_tree":
        f4["prototype"]["source_state"]["tree"]["nodes"][0]["color"] = True
    elif mutation == "third_register":
        f4["third_registers"]["eax"] ^= 1
    elif mutation == "third_vector":
        f4["third_vector_pointer"] = f4["vector_begin"]
    else:
        f4["registers"]["eax"] ^= 1
    with pytest.raises(RuntimeError):
        c._logical(f4)


def test_fourth_adapter_metadata_detached_from_all_prior_fixtures_captures_and_producer(
    cases,
):
    row = cases[-1]
    before = copy.deepcopy(row)
    resumed, logical = c._resume(
        row["produced"], row["f3"], row["cap3"], row["v"]
    ), c._logical(row["f4"])
    untouched = copy.deepcopy(logical)
    assert resumed == row["f4"]
    resumed["prototype"]["source_state"]["payloads"][0] ^= 1
    resumed["prototype"]["destination_state"]["payloads"][0] ^= 1
    resumed["callback_vector"]["source_keys"].clear()
    resumed["callback_vector"]["source_refs"][0] ^= 1
    resumed["callback_vector"]["destination_refs"][0] ^= 1
    resumed["callback_vector"]["transfers"][0].append("other")
    resumed["prototype"]["source_addresses"][0] ^= 1
    resumed["prototype"]["destination_addresses"][0] ^= 1
    resumed["prototype"]["strings"].clear()
    resumed["prototype"]["tree"]["nodes"].append({"changed": True})
    resumed["prototype"]["transfer"]["copies"][0]["payload"] ^= 1
    for field in ("second_source_state", "third_source_state"):
        resumed[field]["payloads"][0] ^= 1
    for field in ("second_registers", "third_registers"):
        resumed[field]["eax"] ^= 1
    resumed["first_arguments"]["registers"]["eax"] ^= 1
    resumed["patches"][0]["after"] ^= 1
    logical["normal_requests"][0]["after"].clear()
    logical["callback_operation"]["vector"]["records"][0][1] ^= 1
    logical["vector_free_request"]["pointer"] ^= 1
    assert row == before
    assert c._resume(row["produced"], row["f3"], row["cap3"], row["v"]) == row["f4"]
    assert c._logical(row["f4"]) == untouched and row == before


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (
        PREFIX + "native_lua_class_factory_callback_fourth_conformance.json"
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


def test_sealed_receipt_lf_sources_and_independent_four_call_arithmetic(receipts):
    path, evidence, _, sources = receipts
    assert CANONICAL is not None and RAW is not None and RECEIPT_BYTES is not None
    assert c.SEALED_SHA256 == CANONICAL
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest() == RAW
        and len(path.read_bytes()) == RECEIPT_BYTES
    )
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert path.read_bytes().endswith(b"\n") and b"\r" not in path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert set(sources) == set(c.SOURCE_PINS) and len(sources) == 34
    assert c.SOURCE_PINS["factory_callback_third"] == (
        c.third.ANALYSIS_KIND,
        c.third.SEALED_SHA256,
    )
    expected = dict(
        cases=216,
        callback_invocations=864,
        static_sites=1115,
        executed_sites=UNION_SITES,
        instruction_bytes=2905,
        factory_instructions=143280,
        first_callback_instructions=326376,
        second_callback_instructions=710316,
        third_callback_instructions=534816,
        fourth_callback_instructions=FOURTH_INSTRUCTIONS,
        factory_heap_calls=216,
        first_class_heap_calls=864,
        second_class_heap_calls=1296,
        third_class_heap_calls=216,
        fourth_class_heap_calls=216,
        first_tree_nodes=648,
        second_tree_allocations=1080,
        second_payload_updates=432,
        second_source_copies=1512,
        third_payload_updates=1512,
        third_tree_allocations=0,
        fourth_payload_updates=1512,
        fourth_tree_allocations=0,
        final_tree_nodes=1728,
        second_copied_old_vector_bytes=1728,
        third_copied_old_vector_bytes=3456,
        fourth_copied_old_vector_bytes=5184,
        second_vector_bytes=3456,
        third_vector_bytes=5184,
        fourth_vector_bytes=6912,
        free_calls=648,
        marker_calls=1728,
        table_calls=1728,
        requested_assignments=864,
        factory_api_calls=7344,
        callback_api_calls=CALLBACK_API_CALLS,
        retained_lua_values_per_call=5,
        result_count=0,
        controls=37,
        opaque_native_instructions=0,
        accounting_promotions=0,
    )
    assert all(value is not None for value in expected.values())
    assert {key: evidence["summary"][key] for key in expected} == expected
    assert {
        key: len(rows) for key, rows in evidence["normal_site_partition"].items()
    } == dict(
        callback=76,
        class_operation=CLASS_SITES,
        markers=27,
        tables=71,
        excluded=EXCLUDED_SITES,
    )
    assert [
        len(evidence[key + "_executed_rvas"])
        for key in ("first", "second", "third", "fourth")
    ] == [701, 864, 546, FOURTH_SITES]
    assert (
        evidence["scope"]["continuous_each_callback"] is True
        and evidence["scope"]["continuous_across_host"] is False
    )


def test_four_site_sets_union_partition_and_predecessor_coverage_are_explicit(receipts):
    _, evidence, _, sources = receipts
    stages = [
        set(evidence[stage + "_executed_rvas"])
        for stage in ("first", "second", "third", "fourth")
    ]
    union = set(evidence["executed_rvas"])
    assert union == set.union(*stages)
    for stage, sites in zip(("first", "second", "third"), stages):
        assert sites == set(sources["factory_callback_third"][stage + "_executed_rvas"])
    assert stages[0] == set(
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
            == sources["factory_callback_third"]["normal_site_partition"][key]
        )
    assert not any(
        a <= int(rva, 16) < b for rva in union for a, b in c.normal.PARENT_EXCLUDED
    )
    assert "0x003574d5" not in union and "0x002ec1bd" in set.intersection(*stages)
    assert "0x0038916c" in set.intersection(
        *stages[1:]
    ) and "0x00007851" in set.intersection(*stages[1:])
    assert (
        len(selected) == evidence["summary"]["static_sites"]
        and len(union) == evidence["summary"]["executed_sites"]
    )
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
            kind=key, rejected=True, reason="retained third callback differs"
        )
    for key in ("capture_pages", "capture_registers"):
        assert controls[key] == dict(
            kind=key, rejected=True, reason="verified third callback capture differs"
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
        "fourth_observation",
        "first_sites",
        "second_sites",
        "third_sites",
        "fourth_sites",
        "callback",
        "class_operation",
        "markers",
        "tables",
        "excluded",
        "host_claim",
    ),
)
def test_tampered_fourth_receipt_rejected_by_seal(receipts, mutation):
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
        "fourth_observation",
    ):
        field = (
            "producer_observations_sha256"
            if mutation == "producer"
            else mutation.replace("_observation", "_observations_sha256")
        )
        changed[field] = "0" * 64
    elif mutation.endswith("_sites"):
        changed[mutation.replace("_sites", "_executed_rvas")].pop()
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
        del changed["factory_callback_third"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["factory_callback_third"]["schema_version"] += 1
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
    noncanonical = tmp_path / "callback-fourth.json"
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
