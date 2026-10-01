"""Bounded physical tree laws; native replay is explicitly subprocess gated."""

import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.observatory import native_lua_class_factory_callback_tree_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_callback_tree_conformance.py"
CANONICAL = "a924cb10e338afa823ced7bf0fb3de20e8b8bb4b1e962fdcc299fec2f2b77614"
RAW = "0d73e76a3be7e1a3b51d4be8662936a1e310d65f5c7924e0fb7eaac0cc5f0555"
U, P, SOURCE, HEAD = 0x0FFFFFCC, 0x10000100, 0x14000000, 0x14000100
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


@pytest.fixture(scope="module")
def cases():
    # These are detached synthetic physical producer packets, not native captures.
    # The full 1296-case native witness is checked only by gated CLI subprocesses.
    producers, result = {}, []
    for vector in c.vectors():
        profile = vector["profile"]
        if (
            vector["length"] != (0, 255)[profile]
            or vector["registry_profile"] != (0, 2)[profile]
            or vector["vector_alignment"] != vector["node_alignment"]
        ):
            continue
        pv = {
            key: value
            for key, value in vector.items()
            if key
            not in (
                "vector_alignment",
                "transfer_profile",
                "source_size",
                "node_alignment",
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
        fixture = c._resume(produced, vector)
        expected = c.callback._expected(
            fixture["callback_vector"], fixture, class_module=c.empty
        )
        result.append((vector, produced, fixture, expected))
    assert len(producers) == 2 and len(result) == 48
    return result


def test_exact_1296_vector_product_and_reversed_unsigned_source_keys():
    vectors = c.vectors()
    assert len(vectors) == 1296
    assert c.SOURCE_KEYS == KEYS and c.KEY_STORAGE == 0x1C000FFF
    assert (
        len(
            {
                tuple(sorted(c.normal._first_vector(c._normal_vector(v)).items()))
                for v in vectors
            }
        )
        == 54
    )
    counts = {}
    for vector in vectors:
        group = (
            vector["source_size"],
            vector["node_alignment"],
            vector["transfer_profile"],
        )
        counts[group] = counts.get(group, 0) + 1
        assert vector["pattern"] == "high" and vector["name_alignment"] == 4095
        assert vector["equal_pointers"] is False
        assert vector["record_bias"] == 0x100 and vector["record_alignment"] == 0
    assert counts == {
        group: 54 for group in itertools.product((0, 1, 3, 7), (0, 7, 31), (0, 4))
    }
    assert {v["profile"] for v in vectors} == {0, 1}
    assert {v["length"] for v in vectors} == {0, 16, 255}
    assert {v["registry_profile"] for v in vectors} == {0, 1, 2}
    assert {v["vector_alignment"] for v in vectors} == {0, 7, 31}


def test_host_adapter_preserves_actual_factory_bytes_and_replays_every_patch(cases):
    for vector, produced, fixture, _ in cases:
        baseline = c.normal._resume(produced, c._normal_vector(vector))
        assert fixture["patches"][: len(baseline["patches"])] == baseline["patches"]
        # Each declared patch must start with the current byte, including writes
        # that deliberately replace an earlier source-head/key-pointer patch.
        replay = {
            page: bytearray(payload) for page, payload in produced["pages"].items()
        }
        for patch in fixture["patches"]:
            page, offset = patch["address"] & ~4095, patch["address"] & 4095
            replay.setdefault(page, bytearray(b"\xa5" * 4096))
            assert replay[page][offset] == patch["before"]
            replay[page][offset] = patch["after"]
        for page in fixture["fresh_pages"]:
            replay.setdefault(page, bytearray(b"\xa5" * 4096))
        assert {page: bytes(payload) for page, payload in replay.items()} == fixture[
            "pages"
        ]
        assert len(fixture["fresh_pages"]) == len(set(fixture["fresh_pages"]))
        assert (
            len(fixture["patches"]) - len(baseline["patches"])
            == 14 + 37 * vector["source_size"]
        )
        assert span(fixture["pages"], U, 72) == span(produced["pages"], U, 72)
        assert span(fixture["pages"], P, 24) == span(produced["pages"], P, 24)
        touched = {patch["address"] for patch in fixture["patches"]}
        for page, payload in produced["pages"].items():
            assert all(
                fixture["pages"][page][index] == byte
                for index, byte in enumerate(payload)
                if page + index not in touched
            )


def test_source_nodes_key_bytes_payloads_and_name_storage_are_disjoint(cases):
    for vector, produced, fixture, _ in cases:
        cv, prototype, pages = (
            fixture["callback_vector"],
            fixture["prototype"],
            fixture["pages"],
        )
        keys = list(reversed(KEYS[: vector["source_size"]]))
        assert cv["source_keys"] == keys and cv["destination_keys"] == []
        assert prototype["destination_state"] == dict(
            tree=dict(root=None, nodes=[]), payloads=[]
        )
        assert [
            node["key"] for node in prototype["source_state"]["tree"]["nodes"]
        ] == keys
        assert raw(pages, SOURCE + 52) == HEAD
        assert span(pages, HEAD + 12, 2) == b"\x01\x01"
        assert (
            len(fixture["key_bindings"])
            == len(prototype["source_addresses"])
            == len(keys)
        )
        names = [
            (produced["fixture"][name], vector["length"] + 1)
            for name in ("first_pointer", "second_pointer")
        ]
        extents = []
        for index, (address, key, binding) in enumerate(
            zip(prototype["source_addresses"], keys, fixture["key_bindings"])
        ):
            pointer = raw(pages, address + 16)
            payload = f"{key:08x}".encode() + b"\0"
            assert address == 0x14001000 + 64 * index + vector["node_alignment"]
            assert pointer == 0x1C000FFF + 32 * index + vector["node_alignment"] % 4
            assert span(pages, pointer, 9) == payload
            assert prototype["strings"][pointer] == payload
            assert binding == dict(
                node=address,
                key_pointer=pointer,
                bytes=9,
                sha256=hashlib.sha256(payload).hexdigest(),
            )
            assert (
                raw(pages, address + 20)
                == (cv["payload_seed"] ^ (index * 0x01010101)) & 0xFFFFFFFF
            )
            extents.append((pointer, 9))
            assert all(
                pointer + 9 <= start or start + width <= pointer
                for start, width in names
            )
        assert all(
            a + width <= b or b + other_width <= a
            for (a, width), (b, other_width) in itertools.combinations(extents, 2)
        )
        for start, width in names:
            assert span(pages, start, width) == span(produced["pages"], start, width)
        assert set(prototype["strings"]) == {
            binding["key_pointer"] for binding in fixture["key_bindings"]
        }


def test_current_producer_fs_cookie_word_refs_and_callback_frame_are_preserved(cases):
    for vector, produced, fixture, expected in cases:
        pages, initial, cv = (
            expected["pages"],
            produced["pages"],
            fixture["callback_vector"],
        )
        assert cv["previous_seh"] == raw(initial, 0)
        assert raw(pages, 0) == raw(initial, 0)
        assert cv["cookie"] == raw(initial, 0x00893F28)
        assert cv["destination_word"] == raw(initial, U)
        assert cv["destination_refs"] == [
            raw(initial, U + offset) for offset in (32, 40)
        ]
        assert cv["source_word"] == (0, 0xFFFFFFFF)[vector["profile"]]
        assert cv["source_refs"] == [
            23 + 100 * vector["profile"],
            29 + 100 * vector["profile"],
        ]
        assert cv["transfers"] == list(
            c.callback.TRANSFER_PAIRS[vector["transfer_profile"]]
        )
        assert fixture["entry"] == 0x30001030 + 15 * vector["profile"]
        assert fixture["registers"] == dict(produced["registers"], esp=fixture["entry"])
        assert span(pages, fixture["entry"], 8) == span(
            fixture["pages"], fixture["entry"], 8
        )
        assert span(pages, SOURCE, 72) == span(fixture["pages"], SOURCE, 72)
        spec = produced["fixture"]["spec"]
        assert span(pages, spec["context_pointer"], 20) == span(
            initial, spec["context_pointer"], 20
        )
        assert [raw(pages, U + offset) for offset in (24, 32, 40)] == [
            spec["references"][2],
            spec["references"][0],
            spec["references"][1],
        ]


@pytest.mark.parametrize(
    "field,address,width",
    [
        ("word", U, 4),
        ("reference", U + 32, 4),
        ("padding", U + 68, 4),
        ("sentinel_padding", P + 14, 1),
        ("fs", 0, 4),
        ("cookie", 0x00893F28, 4),
    ],
)
def test_adapter_uses_current_captured_producer_instead_of_prototype(
    cases, field, address, width
):
    vector, original, _, _ = cases[-1]
    produced = copy.deepcopy(original)
    produced["pages"] = change(
        produced["pages"], address, raw(produced["pages"], address, width) ^ 1, width
    )
    before = copy.deepcopy(produced)
    fixture = c._resume(produced, vector)
    assert span(fixture["pages"], U, 72) == span(produced["pages"], U, 72)
    assert span(fixture["pages"], P, 24) == span(produced["pages"], P, 24)
    if field == "word":
        assert fixture["callback_vector"]["destination_word"] == raw(
            produced["pages"], U
        )
    elif field == "reference":
        assert fixture["callback_vector"]["destination_refs"][0] == raw(
            produced["pages"], U + 32
        )
    elif field == "fs":
        assert fixture["callback_vector"]["previous_seh"] == raw(produced["pages"], 0)
    elif field == "cookie":
        assert fixture["callback_vector"]["cookie"] == raw(
            produced["pages"], 0x00893F28
        )
    assert produced == before


def test_sorted_copy_routing_uses_relocated_current_node_key_pointers(cases):
    for vector, produced, fixture, expected in cases:
        child = next(row for row in expected["children"] if row["kind"] == "class")
        result, pages, cv = (
            child["result"],
            expected["pages"],
            fixture["callback_vector"],
        )
        logical = c._logical(fixture, produced)
        nodes, size = result["destination_addresses"], vector["source_size"]
        assert len(nodes) == result["tree_heap_count"] == size
        assert result["heap_nodes"] == nodes + [fixture["vector_begin"]]
        copies = []
        for index, key in enumerate(KEYS[:size]):
            source_id = size - 1 - index
            source_node = fixture["prototype"]["source_addresses"][source_id]
            source_pointer = raw(fixture["pages"], source_node + 16)
            payload = (cv["payload_seed"] ^ (source_id * 0x01010101)) & 0xFFFFFFFF
            copies.append(
                dict(
                    source=source_id,
                    key=key,
                    destination_address=nodes[index],
                    inserted=True,
                    mode="empty" if index == 0 else "end",
                    payload=payload,
                    heap_node=nodes[index],
                )
            )
            assert raw(pages, nodes[index] + 16) == source_pointer
            assert span(pages, source_pointer, 9) == f"{key:08x}".encode() + b"\0"
            assert raw(pages, nodes[index] + 20) == payload
            assert span(pages, source_node, 24) == span(
                fixture["pages"], source_node, 24
            )
        assert result["insertions"] == copies
        links = logical["sentinel_link_ids"]
        assert [raw(pages, P + offset) for offset in (0, 4, 8)] == [
            P if links[key] is None else nodes[links[key]]
            for key in ("leftmost", "root", "rightmost")
        ]
        assert span(pages, P + 12, 12) == span(produced["pages"], P + 12, 12)
        assert raw(pages, U + 56) == size
        assert all(
            raw(pages, U + offset) == raw(produced["pages"], U + offset)
            for offset in (16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 60, 64, 68)
        )
        assert logical["tree_heap_requests"] == [
            dict(continuation=0x789463, handle=0x12345678, flags=0, bytes=24)
            for _ in range(size)
        ]
        assert logical["vector_heap_request"] == dict(
            continuation=0x789463, handle=0x12345678, flags=0, bytes=8
        )
        assert span(pages, fixture["vector_begin"], 8) == b"\0" * 4 + SOURCE.to_bytes(
            4, "little"
        )


def test_complete_return_abi_and_identity_bound_lua_requests_agree(cases):
    for _, produced, fixture, expected in cases:
        logical = c._logical(fixture, produced)
        assert expected["registers"] == logical["full_return"]["registers"]
        assert expected["flags"] == logical["full_return"]["flags"] == 0x44
        assert expected["endpoint"] == logical["full_return"]["endpoint"] == 0x0400A000
        assert (
            logical["full_return"]["flag_mask"] == 0xCD5
            and logical["return_count"] == 0
        )
        observer, lua = c.normal._IdentityPrefix(fixture), c.callback._Lua(
            fixture["callback_vector"]
        )
        for index, call in enumerate(expected["calls"]):
            assert call["arguments"][0] == fixture["state"]
            if index < 12:
                observer.apply(call, call["arguments"])
            lua.apply(call)
        assert observer.trace == logical["prefix_calls"]

        def bound(snapshot):
            return [
                ("argument", SOURCE) if token == ("argument", 0) else token
                for token in snapshot
            ]

        suffix = copy.deepcopy(lua.trace)
        for call in suffix:
            call["before"], call["after"] = bound(call["before"]), bound(call["after"])
        assert suffix == logical["registry_table_calls"]
        assert (
            bound(lua.stack) == logical["normal_final_lua_stack"]
            and len(lua.stack) == 5
        )
        assert lua.assignments == logical["requested_assignments"]
        assert logical["class_return"]["registers"]["eax"] == SOURCE
        assert logical["class_return"]["registers"]["edx"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        (field, value)
        for field, invalid in (
            ("source_size", (False, True, -1, 2, 8, 1.0, None)),
            ("node_alignment", (False, True, -1, 1, 32, 7.0, None)),
            ("transfer_profile", (False, True, -1, 1, 5, 4.0, None)),
        )
        for value in invalid
    ],
)
def test_unreviewed_profiles_rejected_without_mutating_producer(cases, field, value):
    vector, produced, _, _ = cases[0]
    before = copy.deepcopy(produced)
    with pytest.raises(
        RuntimeError, match="unreviewed factory callback tree source profile"
    ):
        c._resume(produced, dict(vector, **{field: value}))
    assert produced == before


@pytest.mark.parametrize(
    "mutation", ["target", "upvalue", "payload", "word", "node_key_pointer"]
)
def test_invalid_closure_or_corrupted_source_packet_rejected(cases, mutation):
    _, produced, fixture, _ = cases[-1]
    produced, fixture = copy.deepcopy(produced), copy.deepcopy(fixture)
    if mutation in ("target", "upvalue"):
        produced["closure"] = (
            "closure",
            0x006EC110 + int(mutation == "target"),
            ("userdata", U ^ int(mutation == "upvalue")),
        )
    elif mutation == "payload":
        fixture["prototype"]["source_state"]["payloads"][0] = True
    elif mutation == "word":
        fixture["callback_vector"]["source_word"] = True
    else:
        address = fixture["prototype"]["source_addresses"][0] + 16
        fixture["pages"] = change(
            fixture["pages"], address, raw(fixture["pages"], address) ^ 0x100000
        )
    with pytest.raises(RuntimeError):
        if mutation == "node_key_pointer":
            c.callback._expected(
                fixture["callback_vector"], fixture, class_module=c.empty
            )
        else:
            c._logical(fixture, produced)


def test_detached_resume_requests_tree_views_and_key_binding_records(cases):
    vector, produced, fixture, expected = cases[-1]
    before = copy.deepcopy((vector, produced, fixture))
    resumed, logical = c._resume(produced, vector), c._logical(fixture, produced)
    untouched = copy.deepcopy(logical)
    assert resumed == fixture
    assert (
        c.callback._expected(resumed["callback_vector"], resumed, class_module=c.empty)
        == expected
    )
    resumed["key_bindings"][0]["key_pointer"] ^= 1
    resumed["callback_vector"]["source_keys"].clear()
    resumed["prototype"]["source_state"]["payloads"][0] ^= 1
    resumed["patches"][0]["after"] ^= 1
    logical["class_transfer"]["copies"][0]["payload"] ^= 1
    logical["normal_requests"][0]["after"].clear()
    assert c._resume(produced, vector) == fixture
    assert c._logical(fixture, produced) == untouched
    assert (vector, produced, fixture) == before


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (
        PREFIX + "native_lua_class_factory_callback_tree_conformance.json"
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


def test_sealed_receipt_canonical_lf_pins_and_independent_bounded_summary(receipts):
    path, evidence, _, sources = receipts
    assert c.SEALED_SHA256 != "UNSEALED" and len(c.SEALED_SHA256) == 64
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert len(path.read_bytes()) == 692724
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert path.read_bytes().endswith(b"\n") and b"\r" not in path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert set(sources) == set(c.SOURCE_PINS)
    assert len(sources) == 26
    assert {
        "class_tree",
        "factory_callback_return",
        "insertion_return",
        "successor",
        "class_empty",
        "small_copy",
        "marker",
        "table",
        "full_factory",
    } <= set(sources)
    assert c.SOURCE_PINS["factory_callback_return"] == (
        c.normal.ANALYSIS_KIND,
        c.normal.SEALED_SHA256,
    )
    assert c.SOURCE_PINS["class_tree"] == (
        c.empty.prefix.ANALYSIS_KIND,
        c.empty.prefix.SEALED_SHA256,
    )
    summary = evidence["summary"]
    assert summary["factory_instructions"] == 859680
    assert summary["callback_instructions"] == 1866564
    assert {
        key: summary[key]
        for key in (
            "cases",
            "factory_api_calls",
            "callback_api_calls",
            "factory_heap_calls",
            "class_heap_calls",
            "tree_nodes",
            "tree_heap_bytes",
            "vector_heap_calls",
            "marker_calls",
            "table_calls",
            "requested_assignments",
            "retained_lua_values",
            "result_count",
            "free_calls",
            "opaque_native_instructions",
            "accounting_promotions",
        )
    } == dict(
        cases=1296,
        factory_api_calls=44064,
        callback_api_calls=53136,
        factory_heap_calls=1296,
        class_heap_calls=4860,
        tree_nodes=3564,
        tree_heap_bytes=85536,
        vector_heap_calls=1296,
        marker_calls=2592,
        table_calls=2592,
        requested_assignments=1296,
        retained_lua_values=5,
        result_count=0,
        free_calls=0,
        opaque_native_instructions=0,
        accounting_promotions=0,
    )
    assert evidence["scope"]["continuous_factory"] is True
    assert evidence["scope"]["continuous_callback_and_all_helpers"] is True
    assert evidence["scope"]["continuous_across_host"] is False
    excluded = " ".join(evidence["scope"]["excluded"])
    assert all(
        text in excluded
        for text in (
            "Arbitrary destination",
            "Lua VM",
            "Heap ownership",
            "accounting promotion",
        )
    )


def test_normal_site_partition_and_zero_source_family_match_predecessor_exactly(
    receipts,
):
    _, evidence, _, sources = receipts
    partition = evidence["normal_site_partition"]
    groups = [
        set(partition[key])
        for key in ("callback", "class_operation", "markers", "tables")
    ]
    executed, selected = set(evidence["executed_rvas"]), {
        point["rva"] for point in evidence["body"]["points"]
    }
    assert all(not left & right for left, right in itertools.combinations(groups, 2))
    assert set.union(*groups) == executed
    assert executed | set(partition["excluded"]) == selected
    assert not executed & set(partition["excluded"])
    predecessor = sources["factory_callback_return"]
    for key in ("callback", "markers", "tables"):
        assert partition[key] == predecessor["normal_site_partition"][key]
    assert set(predecessor["normal_site_partition"]["empty_class"]) <= groups[1]
    assert groups[1] - set(predecessor["normal_site_partition"]["empty_class"])
    assert set(evidence["families"]) == {"0", "1", "3", "7"}
    assert all(family["cases"] == 324 for family in evidence["families"].values())
    assert set(evidence["families"]["0"]["executed_rvas"]) == set(
        predecessor["executed_rvas"]
    )
    assert all(
        set(family["executed_rvas"]) <= executed
        for family in evidence["families"].values()
    )
    assert not any(
        a <= int(rva, 16) < b for rva in executed for a, b in c.normal.PARENT_EXCLUDED
    )
    assert "0x003574d5" not in executed and "0x002ec1bd" in executed
    assert len(selected) == evidence["summary"]["static_sites"]
    assert len(executed) == evidence["summary"]["executed_sites"]
    assert tuple(map(len, groups)) == (76, 539, 27, 71)
    assert len(partition["excluded"]) == 349
    assert len(selected) == 1062 and len(executed) == 713
    assert {
        key: len(value["executed_rvas"]) for key, value in evidence["families"].items()
    } == {
        "0": 368,
        "1": 572,
        "3": 701,
        "7": 713,
    }
    assert (
        sum(point["size"] for point in evidence["body"]["points"])
        == evidence["summary"]["instruction_bytes"]
    )


def test_tree_heap_corruption_controls_and_native_cookie_failure_are_explicit(receipts):
    _, evidence, _, _ = receipts
    expected = dict(c.normal.CONTROLS)
    expected.update(
        {
            key: "factory return tree heap ABI differs"
            for key in ("tree_request", "tree_register", "tree_flags")
        }
    )
    assert c.CONTROLS == expected and len(expected) == 28
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    assert set(controls) == set(expected) | {"native_callback_cookie"}
    assert all(
        controls[key] == dict(kind=key, rejected=True, reason=reason)
        for key, reason in expected.items()
    )
    assert controls["native_callback_cookie"] == dict(
        kind="native_callback_cookie", rejected=True, endpoint="0x003574d5"
    )
    assert evidence["summary"]["controls"] == 29


@pytest.mark.parametrize(
    "mutation",
    [
        "summary",
        "vector",
        "key_profile",
        "control",
        "body",
        "kind",
        "producer",
        "observations",
        "callback",
        "class_operation",
        "markers",
        "tables",
        "excluded",
        "host_claim",
        "family",
    ],
)
def test_tampered_receipt_rejected_by_seal(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    if mutation == "summary":
        changed["summary"]["tree_nodes"] += 1
    elif mutation == "vector":
        changed["vectors"][0]["source_size"] = 2
    elif mutation == "key_profile":
        changed["vectors"][0]["node_alignment"] = 1
    elif mutation == "control":
        changed["negative_controls"][0]["rejected"] = False
    elif mutation == "body":
        changed["body"]["ranges"][0]["sha256"] = "0" * 64
    elif mutation in ("producer", "observations"):
        changed[
            (
                "producer_observations_sha256"
                if mutation == "producer"
                else "observations_sha256"
            )
        ] = ("0" * 64)
    elif mutation in ("callback", "class_operation", "markers", "tables", "excluded"):
        changed["normal_site_partition"][mutation].pop()
    elif mutation == "host_claim":
        changed["scope"]["continuous_across_host"] = True
    elif mutation == "family":
        changed["families"]["7"]["cases"] += 1
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ["missing", "extra", "pin", "kind"])
def test_strict_source_partition_and_pin_content_identity(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["class_tree"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["factory_callback_return"]["schema_version"] += 1
    else:
        changed["successor"]["analysis_kind"] = "pe_other"
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
    noncanonical = tmp_path / "callback-tree.json"
    noncanonical.write_text(json.dumps(evidence), encoding="utf-8")
    result = subprocess.run(
        command + ["--evidence", str(noncanonical)],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 1 and result.stdout == b""
    assert b"not deterministically encoded" in result.stderr


def test_exact_native_capture_build_and_verify_are_subprocess_only(receipts):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    path, _, paths, _ = receipts
    result = subprocess.run(
        command_for("build", paths) + ["--executable", executable],
        cwd=ROOT,
        capture_output=True,
        timeout=1200,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == path.read_bytes()
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
