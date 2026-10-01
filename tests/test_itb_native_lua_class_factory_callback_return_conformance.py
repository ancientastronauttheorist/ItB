"""Independent host, stack and memory laws; native execution stays in the CLI."""

import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.observatory import (
    native_lua_class_factory_callback_return_conformance as c,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_callback_return_conformance.py"
CANONICAL = "6b0f0ced057240a366ccd5c9545d482feb2d7fbcd3af70aaa5186779c3ad885e"
RAW = "80c3c514d6ebe07d5dec4a25a900ffa30f6dc064a4822d6910c59a2ddd8035c7"
SUMMARY = dict(
    cases=324,
    static_sites=1062,
    executed_sites=368,
    instruction_bytes=2746,
    factory_instructions=214920,
    callback_instructions=142236,
    factory_api_calls=11016,
    callback_api_calls=12096,
    factory_heap_calls=324,
    class_heap_calls=324,
    marker_calls=648,
    table_calls=648,
    requested_assignments=324,
    retained_lua_values=5,
    result_count=0,
    tree_insertions=0,
    free_calls=0,
    controls=26,
    opaque_native_instructions=0,
    accounting_promotions=0,
)
U, P, SOURCE, HEAD = 0x0FFFFFCC, 0x10000100, 0x14000000, 0x14000100
TRANSFER_PAIRS = (
    ([], []),
    (["init"], ["finalize"]),
    (["other"], []),
    ([], ["other"]),
    (["other", "init", "finalize"], ["finalize", "other", "init"]),
    (["init", "other"], ["other", "finalize"]),
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


def independent_host_boundary(produced, vector):
    """Install named host/source writes and preserve every other producer byte."""
    pages, patches = dict(produced["pages"]), []
    t = 0x30001030 + 15 * vector["profile"]
    writes = [
        (0x400000 + slot, c.layout.TARGETS[name].to_bytes(4, "little"))
        for name, slot in c.layout.SLOTS.items()
    ]
    writes += list(c.layout.LITERALS.items())
    writes += [
        (t, (0x0400A000).to_bytes(4, "little")),
        (t + 4, produced["fixture"]["state"].to_bytes(4, "little")),
        (SOURCE + 52, HEAD.to_bytes(4, "little")),
        (HEAD, HEAD.to_bytes(4, "little") * 3 + b"\x01\x01"),
    ]
    source_word = (0, 0xFFFFFFFF)[vector["profile"]]
    writes += [
        (SOURCE, source_word.to_bytes(4, "little")),
        (SOURCE + 32, (23 + 100 * vector["profile"]).to_bytes(4, "little")),
        (SOURCE + 40, (29 + 100 * vector["profile"]).to_bytes(4, "little")),
    ]
    for start, payload in writes:
        for offset, byte in enumerate(payload):
            address = start + offset
            pages.setdefault(address & ~4095, b"\xa5" * 4096)
            patches.append(
                dict(address=address, before=raw(pages, address, 1), after=byte)
            )
            pages = change(pages, address, byte, 1)
    fresh = [0x06000000 + 4096 * i for i in range(4)]
    assert not set(fresh).intersection(pages)
    pages.update({page: b"\xa5" * 4096 for page in fresh})
    return pages, patches, fresh


@pytest.fixture(scope="module")
def cases():
    # All producer pages are synthetic physical-law outputs. Real execution is
    # checked only by the explicitly gated subprocess build and verify modes.
    producers, result = {}, []
    for vector in c.vectors():
        pv = {
            key: value
            for key, value in vector.items()
            if key not in ("vector_alignment", "transfer_profile")
        }
        key = tuple(sorted(pv.items()))
        if key not in producers:
            base = c.full.record._base_vector(c.full._record_vector(pv))
            fixture = c.first.alignment.install(pv, c.factory._fixture(base))
            original = c.factory._expected(base, fixture)
            physical = c.full._extend_expected(pv, fixture, original)
            producers[key] = dict(
                fixture=fixture,
                pages=physical["pages"],
                registers=physical["registers"],
                lua_result=physical["lua_result"],
                closure=("closure", 0x006EC110, ("userdata", U)),
            )
        produced = producers[key]
        fixture = c._resume(produced, vector)
        cv = fixture["callback_vector"]
        expected = c.callback._expected(cv, fixture, class_module=c.empty)
        result.append((vector, produced, fixture, expected))
    assert len(producers) == 18 and len(result) == 324
    return result


def test_exact_324_outer_cases_54_physical_frames_and_six_transfer_recipes(cases):
    vectors = [row[0] for row in cases]
    assert vectors == c.vectors()
    assert len({tuple(sorted(c._first_vector(v).items())) for v in vectors}) == 54
    assert {v["transfer_profile"] for v in vectors} == set(range(6))
    assert c.callback.TRANSFER_PAIRS == TRANSFER_PAIRS
    assert {v["vector_alignment"] for v in vectors} == {0, 7, 31}
    assert {v["profile"] for v in vectors} == {0, 1}
    assert {v["length"] for v in vectors} == {0, 16, 255}
    assert {v["registry_profile"] for v in vectors} == {0, 1, 2}
    assert all(
        v["pattern"] == "high"
        and v["name_alignment"] == 4095
        and v["equal_pointers"] is False
        and v["record_bias"] == 0x100
        and v["record_alignment"] == 0
        for v in vectors
    )


def test_independent_host_patch_law_extra_12_source_bytes_and_all_other_bytes(cases):
    for vector, produced, fixture, _ in cases:
        pages, patches, fresh = independent_host_boundary(produced, vector)
        assert fixture["pages"] == pages and fixture["patches"] == patches
        assert fixture["fresh_pages"] == fresh
        earlier = c.first._resume(produced, c._first_vector(vector))
        assert fixture["patches"][:-12] == earlier["patches"]
        assert [patch["address"] for patch in fixture["patches"][-12:]] == [
            SOURCE + offset + byte for offset in (0, 32, 40) for byte in range(4)
        ]
        touched = {row["address"] for row in patches}
        for page, payload in produced["pages"].items():
            assert all(
                pages[page][i] == byte
                for i, byte in enumerate(payload)
                if page + i not in touched
            )
        for page in set(pages) - set(produced["pages"]):
            assert all(
                byte == 0xA5
                for i, byte in enumerate(pages[page])
                if page + i not in touched
            )
        assert span(pages, U, 72) == span(produced["pages"], U, 72)
        assert span(pages, P, 24) == span(produced["pages"], P, 24)
        assert raw(pages, SOURCE + 52) == HEAD
        assert span(pages, HEAD, 14) == HEAD.to_bytes(4, "little") * 3 + b"\x01\x01"


def test_callback_vector_uses_actual_producer_word_refs_cookie_and_current_pages(cases):
    for vector, produced, fixture, expected in cases:
        cv = fixture["callback_vector"]
        assert cv["source_word"] == raw(fixture["pages"], SOURCE)
        assert cv["source_refs"] == [
            23 + 100 * vector["profile"],
            29 + 100 * vector["profile"],
        ]
        assert cv["destination_word"] == raw(produced["pages"], U)
        assert cv["destination_refs"] == [
            raw(produced["pages"], U + o) for o in (32, 40)
        ]
        assert cv["cookie"] == raw(produced["pages"], 0x00893F28)
        assert cv["transfers"] == list(TRANSFER_PAIRS[vector["transfer_profile"]])
        child = next(
            child for child in expected["children"] if child["kind"] == "class"
        )
        prefix = c.callback._expected(cv, fixture, class_entry_only=True)
        assert child["fixture"]["pages"] == prefix["pages"]
        assert child["fixture"]["registers"] == prefix["registers"]
        assert child["fixture"]["return_address"] == 0x006EC1BD
        assert child["fixture"]["stack"] == fixture["entry"] - 48
        assert span(child["fixture"]["pages"], P, 24) == span(produced["pages"], P, 24)


def test_prototype_bytes_cannot_replace_current_factory_word_refs_or_opaque_pages(
    cases,
):
    for vector, produced, fixture, expected in cases[::54]:
        forged = copy.deepcopy(fixture)
        forged["prototype"]["pages"] = change(
            forged["prototype"]["pages"], U, 0x11112222
        )
        for offset in (32, 40):
            forged["prototype"]["pages"] = change(
                forged["prototype"]["pages"], U + offset, 0x33334444
            )
        assert (
            c.callback._expected(
                forged["callback_vector"], forged, class_module=c.empty
            )
            == expected
        )
        current = dict(
            fixture, pages=change(fixture["pages"], SOURCE + 500, 0x67342501)
        )
        changed = c.callback._expected(
            current["callback_vector"], current, class_module=c.empty
        )
        child = next(child for child in changed["children"] if child["kind"] == "class")
        assert raw(child["fixture"]["pages"], SOURCE + 500) == 0x67342501
        assert raw(changed["pages"], SOURCE + 500) == 0x67342501
        mutated_producer = dict(
            produced, pages=change(produced["pages"], U, 0xABCDEF12)
        )
        for offset, reference in ((32, 0xFFFFFFFF), (40, 0)):
            mutated_producer["pages"] = change(
                mutated_producer["pages"], U + offset, reference
            )
        resumed = c._resume(mutated_producer, vector)
        assert resumed["callback_vector"]["destination_word"] == 0xABCDEF12
        assert resumed["callback_vector"]["destination_refs"] == [0xFFFFFFFF, 0]


def test_independent_every_ordered_write_replays_every_final_page(cases):
    for _, _, fixture, expected in cases:
        pages = dict(fixture["pages"])
        for event in expected["events"]:
            assert event["access"] in ("read", "write")
            if event["access"] == "write":
                pages = change(pages, event["address"], event["value"], event["width"])
        assert pages == expected["pages"]


def test_independent_final_four_fields_14_preserved_words_sentinel_and_all_domains(
    cases,
):
    for vector, produced, fixture, expected in cases:
        pages, initial = expected["pages"], produced["pages"]
        pointer = 0x06002000 + vector["vector_alignment"]
        assert [raw(pages, U + o) for o in (0, 4, 8, 12)] == [
            (0, 0xFFFFFFFF)[vector["profile"]],
            pointer,
            pointer + 8,
            pointer + 8,
        ]
        assert all(raw(pages, U + o) == raw(initial, U + o) for o in range(16, 72, 4))
        assert span(pages, pointer, 8) == b"\0" * 4 + SOURCE.to_bytes(4, "little")
        assert span(pages, fixture["entry"] - 20, 8) == span(pages, pointer, 8)
        assert span(pages, P, 24) == span(initial, P, 24)
        assert raw(pages, U + 52) == P
        assert span(pages, P, 14) == P.to_bytes(4, "little") * 3 + b"\x01\x01"
        assert pages[SOURCE] == fixture["pages"][SOURCE]
        for address in (0, 0x00893F28, 0x008B7634):
            assert raw(pages, address) == raw(initial, address)
        spec = produced["fixture"]["spec"]
        assert [raw(pages, U + o) for o in (24, 32, 40)] == [
            spec["references"][2],
            spec["references"][0],
            spec["references"][1],
        ]
        context = spec["context_pointer"]
        assert span(pages, context, 20) == span(initial, context, 20)
        for field in ("first_pointer", "second_pointer"):
            address = produced["fixture"][field]
            assert span(pages, address, vector["length"] + 1) == span(
                initial, address, vector["length"] + 1
            )
        t = fixture["entry"]
        assert span(pages, t, 8) == span(fixture["pages"], t, 8)
        assert span(pages, t + 8, 0x30002000 - t - 8) == span(
            initial, t + 8, 0x30002000 - t - 8
        )


def test_complete_normal_return_original_allocation_and_both_actual_cookie_frames(
    cases,
):
    for _, produced, fixture, expected in cases:
        t, cv = fixture["entry"], fixture["callback_vector"]
        cookie, incoming = cv["cookie"], fixture["registers"]
        second_count = 2 + sum(
            {"init": 4, "finalize": 7, "other": 10}[k] for k in cv["transfers"][1]
        )
        assert expected["registers"] == dict(
            eax=0,
            ebx=incoming["ebx"],
            ecx=cookie,
            edx=0xB0000300 + second_count,
            esi=incoming["esi"],
            edi=incoming["edi"],
            ebp=incoming["ebp"],
            esp=t + 4,
        )
        logical = c._logical(fixture, produced)
        assert logical["full_return"]["registers"] == expected["registers"]
        assert expected["flags"] == logical["full_return"]["flags"] == 0x44
        assert logical["full_return"]["flag_mask"] == 0xCD5
        assert expected["endpoint"] == logical["full_return"]["endpoint"] == 0x0400A000
        assert raw(expected["pages"], t - 12) == cookie ^ (t - 4)
        child = next(
            child for child in expected["children"] if child["kind"] == "class"
        )
        assert raw(child["result"]["pages"], t - 56) == cookie ^ (t - 52)
        assert child["result"]["heap_nodes"] == [fixture["vector_begin"]]
        assert (
            child["result"]["tree_heap_count"] == 0
            and child["result"]["insertions"] == []
        )
        assert logical["heap_request"] == dict(
            continuation=0x789463, handle=0x12345678, flags=0, bytes=8
        )
        assert not any(
            call["api"] in ("HeapFree", "lua_newuserdata") for call in expected["calls"]
        )


def identity_bound(snapshot):
    return [
        ("argument", SOURCE) if token == ("argument", 0) else token
        for token in snapshot
    ]


def test_actual_api_packets_interpreted_as_identity_prefix_and_legacy_suffix(cases):
    for _, produced, fixture, expected in cases:
        observer, lua = c._IdentityPrefix(fixture), c.callback._Lua(
            fixture["callback_vector"]
        )
        for index, call in enumerate(expected["calls"]):
            assert call["arguments"][0] == fixture["state"]
            if index < 12:
                observer.apply(call, call["arguments"])
            lua.apply(call)
        logical = c._logical(fixture, produced)
        assert observer.trace == logical["prefix_calls"]
        suffix = copy.deepcopy(lua.trace)
        for call in suffix:
            call["before"] = identity_bound(call["before"])
            call["after"] = identity_bound(call["after"])
        assert suffix == logical["registry_table_calls"]
        assert (
            identity_bound(lua.stack)
            == logical["normal_final_lua_stack"]
            == [
                ("argument", SOURCE),
                ("registry", fixture["callback_vector"]["destination_refs"][0]),
                ("registry", fixture["callback_vector"]["source_refs"][0]),
                ("registry", fixture["callback_vector"]["destination_refs"][1]),
                ("registry", fixture["callback_vector"]["source_refs"][1]),
            ]
        )
        assert logical["return_count"] == 0 and len(lua.stack) == 5
        assert logical["requested_assignments"] == lua.assignments
        assert len(expected["calls"]) == 20 + sum(
            {"init": 4, "finalize": 7, "other": 10}[kind]
            for recipe in fixture["callback_vector"]["transfers"]
            for kind in recipe
        )


@pytest.mark.parametrize("profile", [False, True, -1, 6, 1.0, None])
def test_strict_transfer_profile_rejected_without_mutating_producer(cases, profile):
    vector, produced, _, _ = cases[0]
    changed = dict(vector, transfer_profile=profile)
    before = copy.deepcopy(produced)
    with pytest.raises(RuntimeError, match="transfer profile"):
        c._resume(produced, changed)
    assert produced == before


@pytest.mark.parametrize(
    "mutation", ["target", "upvalue", "source_word", "source_memory"]
)
def test_invalid_closure_or_source_word_packet_rejected(cases, mutation):
    _, produced, fixture, _ = cases[-1]
    produced, fixture = copy.deepcopy(produced), copy.deepcopy(fixture)
    if mutation in ("target", "upvalue"):
        produced["closure"] = (
            "closure",
            0x006EC110 + int(mutation == "target"),
            ("userdata", U ^ int(mutation == "upvalue")),
        )
    elif mutation == "source_word":
        fixture["callback_vector"]["source_word"] = True
    else:
        fixture["pages"] = change(
            fixture["pages"], SOURCE, raw(fixture["pages"], SOURCE) ^ 1
        )
    with pytest.raises(RuntimeError):
        if mutation == "source_memory":
            c.callback._expected(
                fixture["callback_vector"], fixture, class_module=c.empty
            )
        else:
            c._logical(fixture, produced)


def test_resume_logical_and_expected_inputs_immutable_outputs_detached(cases):
    for vector, produced, fixture, expected in cases[::108]:
        before = copy.deepcopy((vector, produced, fixture))
        resumed = c._resume(produced, vector)
        logical = c._logical(fixture, produced)
        untouched = copy.deepcopy(logical)
        assert resumed == fixture
        assert (
            c.callback._expected(
                resumed["callback_vector"], resumed, class_module=c.empty
            )
            == expected
        )
        resumed["callback_vector"]["transfers"][0].append("other")
        resumed["callback_vector"]["source_refs"][0] ^= 1
        resumed["registers"]["eax"] ^= 1
        resumed["patches"][0]["after"] ^= 1
        resumed["fresh_pages"].clear()
        logical["normal_requests"][0]["after"].clear()
        logical["registry_requests"][0]["arguments"].clear()
        logical["callback_operation"]["vector"]["records"][0][1] = 0
        assert c._resume(produced, vector) == fixture
        assert c._logical(fixture, produced) == untouched
        assert (vector, produced, fixture) == before


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (
        PREFIX + "native_lua_class_factory_callback_return_conformance.json"
    )
    evidence = json.loads(path.read_text())
    sources, paths = {}, {}
    for key, (kind, digest) in c.SOURCE_PINS.items():
        suffix = "program_facts" if key == "program_facts" else kind.removeprefix("pe_")
        source_path = PROGRAMS / (PREFIX + suffix + ".json")
        sources[key] = json.loads(source_path.read_text())
        assert c._canonical_sha256(sources[key]) == digest
        paths[key] = source_path
    return path, evidence, paths, sources


def test_sealed_receipt_bytes_summary_21_sources_and_bounded_scope(receipts):
    path, evidence, _, sources = receipts
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert b"\r" not in path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert len(sources) == len(c.SOURCE_PINS) == 21
    assert {
        "full_factory",
        "factory_callback_entry",
        "factory_empty_class",
        "class_empty",
        "marker",
        "table",
        "small_copy",
    } <= set(sources)
    assert evidence["summary"] == SUMMARY
    assert evidence["scope"]["continuous_factory"] is True
    assert evidence["scope"]["continuous_callback_and_all_helpers"] is True
    assert evidence["scope"]["continuous_across_host"] is False
    excluded = " ".join(evidence["scope"]["excluded"])
    assert all(
        text in excluded
        for text in (
            "Lua VM",
            "Nonempty tree",
            "Heap ownership",
            "accounting promotion",
        )
    )


def test_normal_site_partition_is_exact_callback_class_marker_and_full_table_union(
    receipts,
):
    _, evidence, _, sources = receipts
    partition = evidence["normal_site_partition"]
    callback, child, markers, tables, excluded = (
        set(partition[k])
        for k in ("callback", "empty_class", "markers", "tables", "excluded")
    )
    selected = {point["rva"] for point in evidence["body"]["points"]}
    executed = set(evidence["executed_rvas"])
    expected_callback = {
        point["rva"]
        for point in evidence["body"]["points"]
        if 0x2EC110 <= int(point["rva"], 16) < 0x2EC21D
        and not any(
            a <= int(point["rva"], 16) < b
            for a, b in (
                (0x2EC140, 0x2EC154),
                (0x2EC164, 0x2EC178),
                (0x2EC188, 0x2EC19E),
            )
        )
    }
    assert callback == expected_callback
    assert child == set(
        sources["factory_empty_class"]["normal_site_partition"]["empty_class"]
    )
    assert tuple(map(len, (callback, child, markers, tables, excluded))) == (
        76,
        194,
        27,
        71,
        694,
    )
    assert markers == {
        rva
        for rva in sources["factory_callback_entry"]["executed_rvas"]
        if not 0x2EC110 <= int(rva, 16) < 0x2EC21D
    }
    assert tables == set(sources["table"]["executed_rvas"])
    assert all(
        not left & right
        for left, right in itertools.combinations((callback, child, markers, tables), 2)
    )
    assert callback | child | markers | tables == executed
    assert executed | excluded == selected and not executed & excluded
    assert "0x002ec1bd" in callback and "0x003574d5" not in executed
    assert {
        "0x002eb15f",
        "0x002eb1c5",
        "0x002ec140",
        "0x002ec164",
        "0x002ec188",
    } <= excluded
    assert (
        sum(point["size"] for point in evidence["body"]["points"])
        == evidence["summary"]["instruction_bytes"]
    )


def test_independent_exact_25_corruption_reasons_and_native_cookie_failure(receipts):
    _, evidence, _, _ = receipts
    reasons = {
        **{key: "callback ancestor memory differs" for key in ("ancestor", "record")},
        **{
            key: "callback protected memory differs"
            for key in (
                "word",
                "reference",
                "literal",
                "iat",
                "vector",
                "capacity",
                "sentinel_padding",
                "factory_reference",
                "source_padding",
                "cookie_page",
            )
        },
        **{
            key: "callback registers or flags differ"
            for key in ("result", "return_cookie", "return_flags")
        },
        "lua_prefix": "callback Lua request trace differs",
        "heap_request": "callback heap handoff differs",
        "upvalue_identity": "factory return native userdata identity differs",
        "argument_identity": "factory return native userdata identity differs",
        "marker_guard": "factory return entered excluded parent arm",
        "argument_guard": "factory return entered excluded parent arm",
        "class_flags": "factory return class entry differs",
        "heap_register": "factory return heap ABI differs",
        "heap_flags": "factory return heap ABI differs",
        "heap_identity": "factory return heap response identity differs",
    }
    assert c.CONTROLS == reasons and len(reasons) == 25
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    assert set(controls) == set(reasons) | {"native_callback_cookie"}
    assert all(
        controls[k] == dict(kind=k, rejected=True, reason=reason)
        for k, reason in reasons.items()
    )
    assert controls["native_callback_cookie"] == dict(
        kind="native_callback_cookie", rejected=True, endpoint="0x003574d5"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "summary",
        "vector",
        "control",
        "body",
        "kind",
        "producer",
        "observations",
        "callback",
        "empty_class",
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
        changed["summary"]["callback_api_calls"] += 1
    elif mutation == "vector":
        changed["vectors"][0]["transfer_profile"] = 1
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
    elif mutation in ("callback", "empty_class", "markers", "tables", "excluded"):
        changed["normal_site_partition"][mutation].pop()
    elif mutation == "host_claim":
        changed["scope"]["continuous_across_host"] = True
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ["missing", "extra", "pin", "kind"])
def test_strict_source_partition_and_content_identity(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["factory_empty_class"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["class_empty"]["schema_version"] += 1
    else:
        changed["table"]["analysis_kind"] = "pe_other"
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
    noncanonical = tmp_path / "callback-return.json"
    noncanonical.write_text(json.dumps(evidence), encoding="utf-8")
    result = subprocess.run(
        command + ["--evidence", str(noncanonical)],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 1 and result.stdout == b""
    assert b"not deterministically encoded" in result.stderr


def test_exact_native_capture_rebuild_and_verify_are_subprocess_only(receipts):
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
    assert verified.stderr == b""
    assert json.loads(verified.stdout) == dict(
        status="verified", evidence_sha256=CANONICAL
    )
