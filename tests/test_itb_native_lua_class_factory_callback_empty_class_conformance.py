"""Independent host/frame/memory laws; real factory capture stays subprocess-only."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import (
    native_lua_class_factory_callback_empty_class_conformance as c,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_callback_empty_class_conformance.py"
CANONICAL = "09117544ab5c8c4366aec36ee3bd295263157cdbd22455b1a1597d6eaf73851a"
RAW = "4352b1a18d11b76a4ec99ba46103886a647d1af48dfa6789001d5350ff215fc2"
U, P, SOURCE, HEAD = 0x0FFFFFCC, 0x10000100, 0x14000000, 0x14000100


def raw(pages, address, width=4):
    return int.from_bytes(span(pages, address, width), "little")


def span(pages, address, width):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(width)
    )


def change(pages, address, value, width=4):
    result = dict(pages)
    for offset, byte in enumerate(value.to_bytes(width, "little")):
        page = (address + offset) & ~4095
        payload = bytearray(result[page])
        payload[(address + offset) & 4095] = byte
        result[page] = bytes(payload)
    return result


def independent_host_boundary(produced, vector):
    """Install named byte writes; copy all other bytes from producer or A5."""
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
    # Synthetic aligned factory pages satisfy the physical producer oracle's
    # premises. Native production is checked only by the gated CLI rebuild.
    producers, result = {}, []
    for vector in c.vectors():
        producer_vector = {k: v for k, v in vector.items() if k != "vector_alignment"}
        key = tuple(sorted(producer_vector.items()))
        if key not in producers:
            base = c.full.record._base_vector(c.full._record_vector(producer_vector))
            fixture = c.alignment.install(producer_vector, c.factory._fixture(base))
            original = c.factory._expected(base, fixture)
            physical = c.full._extend_expected(producer_vector, fixture, original)
            producers[key] = dict(
                fixture=fixture,
                pages=physical["pages"],
                registers=physical["registers"],
                lua_result=physical["lua_result"],
                closure=("closure", 0x006EC110, ("userdata", U)),
            )
        produced = producers[key]
        fixture = c._resume(produced, vector)
        prefix = c.callback._expected(
            dict(
                frame_alignment=15 * vector["profile"],
                marker_words=[(0, 0x12345678)[vector["profile"]], 0xFFFFFFFF],
            ),
            fixture,
            class_entry_only=True,
        )
        joined = c._joined_expected(prefix, fixture, vector)
        result.append((vector, produced, fixture, prefix, joined))
    assert len(producers) == 18 and len(result) == 54
    return result


def test_exact_fifty_four_case_domain_from_eighteen_aligned_producers(cases):
    vectors = [row[0] for row in cases]
    assert vectors == c.vectors()
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


def test_independent_minimal_host_patch_law_and_all_unmentioned_producer_bytes(cases):
    for vector, produced, fixture, _, _ in cases:
        pages, patches, fresh = independent_host_boundary(produced, vector)
        assert fixture["pages"] == pages and fixture["patches"] == patches
        assert fixture["fresh_pages"] == fresh
        touched = {row["address"] for row in patches}
        assert set(fixture["pages"]) >= set(produced["pages"])
        for page, payload in produced["pages"].items():
            assert all(
                fixture["pages"][page][i] == byte
                for i, byte in enumerate(payload)
                if page + i not in touched
            )
        for page in set(pages) - set(produced["pages"]):
            assert all(
                byte == 0xA5
                for i, byte in enumerate(pages[page])
                if page + i not in touched
            )


def test_empty_source_only_named_bytes_and_four_fresh_a5_construction_pages(cases):
    for _, produced, fixture, _, _ in cases:
        pages = fixture["pages"]
        assert fixture["source_pointer"] == SOURCE
        assert raw(pages, SOURCE + 52) == HEAD
        assert span(pages, HEAD, 14) == HEAD.to_bytes(4, "little") * 3 + b"\x01\x01"
        source_touched = set(range(SOURCE + 52, SOURCE + 56)) | set(
            range(HEAD, HEAD + 14)
        )
        assert {
            p["address"]
            for p in fixture["patches"]
            if SOURCE <= p["address"] < SOURCE + 4096
        } == source_touched
        old = produced["pages"].get(SOURCE, b"\xa5" * 4096)
        assert all(
            pages[SOURCE][i] == byte
            for i, byte in enumerate(old)
            if SOURCE + i not in source_touched
        )
        assert fixture["fresh_pages"] == [
            0x06000000,
            0x06001000,
            0x06002000,
            0x06003000,
        ]
        assert all(pages[page] == b"\xa5" * 4096 for page in fixture["fresh_pages"])
        assert span(pages, U, 72) == span(produced["pages"], U, 72)
        assert span(pages, P, 24) == span(produced["pages"], P, 24)


def test_callback_entry_class_frame_and_cookie_derive_from_current_factory_pages(cases):
    for vector, produced, fixture, prefix, joined in cases:
        t = 0x30001030 + 15 * vector["profile"]
        cv = c._class_vector(vector, fixture["pages"])
        assert fixture["entry"] == t and t - 48 == 0x30001000 + 15 * vector["profile"]
        assert fixture["registers"] == dict(produced["registers"], esp=t)
        assert cv == dict(
            profile="empty_source",
            source_keys=[],
            destination_keys=[],
            node_alignment=0,
            frame_alignment=15 * vector["profile"],
            nil_flag=1,
            previous_seh=0,
            cookie=raw(produced["pages"], 0x00893F28),
            payload_seed=0x75310000,
            vector_alignment=vector["vector_alignment"],
        )
        altered = change(fixture["pages"], 0x00893F28, 0xDD112233)
        assert c._class_vector(vector, altered)["cookie"] == 0xDD112233
        child = joined["child_fixture"]
        assert child["pages"] == prefix["pages"]
        assert child["registers"] == prefix["registers"]
        assert child["stack"] == t - 48 and child["return_address"] == 0x006EC1BD
        assert raw(child["pages"], t - 48) == 0x006EC1BD
        assert raw(child["pages"], t - 44) == t - 20
        assert span(child["pages"], t - 20, 8) == b"\0" * 4 + SOURCE.to_bytes(
            4, "little"
        )
        assert raw(child["pages"], U + 52) == P
        assert span(child["pages"], P, 24) == span(produced["pages"], P, 24)


def test_join_uses_current_prefix_pages_and_keeps_opaque_bytes_instead_of_prototype(
    cases,
):
    for vector, _, fixture, prefix, _ in cases[::9]:
        current = dict(prefix, pages=change(prefix["pages"], SOURCE + 500, 0x67342501))
        expected = c._joined_expected(current, fixture, vector)
        assert raw(expected["child_fixture"]["pages"], SOURCE + 500) == 0x67342501
        assert raw(expected["pages"], SOURCE + 500) == 0x67342501
        assert expected["events"] == current["events"] + expected["child"]["events"]


def test_independent_ordered_write_replay_reconstructs_every_final_page(cases):
    for _, _, fixture, prefix, joined in cases:
        pages = dict(fixture["pages"])
        for event in joined["events"]:
            assert event["access"] in ("read", "write")
            if event["access"] == "write":
                pages = change(pages, event["address"], event["value"], event["width"])
        assert pages == joined["pages"]
        assert joined["events"][: len(prefix["events"])] == prefix["events"]
        assert joined["events"][len(prefix["events"]) :] == joined["child"]["events"]


def test_independent_final_vector_cells_fifteen_userdata_words_record_and_other_domains(
    cases,
):
    preserved = [0, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68]
    for vector, produced, fixture, prefix, joined in cases:
        pages, initial = joined["pages"], produced["pages"]
        pointer = 0x06002000 + vector["vector_alignment"]
        assert [raw(pages, U + offset) for offset in (4, 8, 12)] == [
            pointer,
            pointer + 8,
            pointer + 8,
        ]
        assert span(pages, pointer, 8) == b"\0" * 4 + SOURCE.to_bytes(4, "little")
        assert span(pages, fixture["entry"] - 20, 8) == span(pages, pointer, 8)
        assert all(
            raw(pages, U + offset) == raw(initial, U + offset) for offset in preserved
        )
        assert span(pages, P, 24) == span(initial, P, 24)
        assert raw(pages, U + 52) == P
        assert span(pages, P, 14) == P.to_bytes(4, "little") * 3 + b"\x01\x01"
        assert pages[SOURCE] == fixture["pages"][SOURCE]
        for address in (0, 0x00893F28, 0x008B7634):
            assert raw(pages, address) == raw(initial, address)
        spec = produced["fixture"]["spec"]
        assert [raw(pages, U + offset) for offset in (24, 32, 40)] == [
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
        assert span(pages, t + 8, 0x30002000 - (t + 8)) == span(
            initial, t + 8, 0x30002000 - (t + 8)
        )
        assert all(
            raw(pages, t - offset) == raw(prefix["pages"], t - offset)
            for offset in (4, 12, 32, 36, 40)
        )


def test_all_final_gprs_defined_flags_class_cookie_and_one_original_pair_allocation(
    cases,
):
    for vector, produced, fixture, prefix, joined in cases:
        t, cookie = fixture["entry"], raw(produced["pages"], 0x00893F28)
        logical = c._logical(fixture, produced, vector)
        expected_registers = dict(
            eax=SOURCE,
            ebx=fixture["state"],
            ecx=cookie,
            edx=0,
            esi=U,
            edi=SOURCE,
            ebp=t - 4,
            esp=t - 40,
        )
        assert (
            joined["registers"]
            == expected_registers
            == logical["class_return"]["registers"]
        )
        assert joined["flags"] == logical["class_return"]["flags"] == 0x44
        assert logical["class_return"]["flag_mask"] == 0xCD5
        assert joined["child"]["endpoint"] == 0x006EC1BD
        assert raw(joined["pages"], t - 56) == cookie ^ (t - 52)
        assert raw(joined["pages"], t - 52) == t - 4
        assert raw(joined["pages"], t - 48) == 0x006EC1BD
        assert raw(joined["pages"], t - 44) == t - 20
        assert joined["child"]["tree_heap_count"] == 0
        assert joined["child"]["heap_nodes"] == [fixture["vector_begin"]]
        assert joined["child"]["insertions"] == []
        assert logical["heap_request"] == dict(
            continuation=0x789463, handle=0x12345678, flags=0, bytes=8
        )
        assert (
            len(prefix["calls"]) == len(joined["calls"]) == len(logical["calls"]) == 12
        )
        assert logical["vector"]["records"] == [[0, SOURCE]]
        assert not any(
            call["api"] in ("HeapFree", "lua_newuserdata") for call in joined["calls"]
        )


def test_resume_logical_and_join_inputs_immutable_outputs_detached(cases):
    for vector, produced, fixture, prefix, joined in cases[::18]:
        before = copy.deepcopy((vector, produced, fixture, prefix))
        resumed = c._resume(produced, vector)
        assert resumed == fixture
        logical = c._logical(fixture, produced, vector)
        again = c._logical(fixture, produced, vector)
        fresh_join = c._joined_expected(prefix, fixture, vector)
        assert fresh_join == joined
        assert (vector, produced, fixture, prefix) == before
        resumed["registers"]["eax"] ^= 1
        resumed["patches"][0]["after"] ^= 1
        resumed["fresh_pages"].clear()
        logical["vector"]["records"][0][1] = 0
        logical["calls"][1]["after"].clear()
        assert c._resume(produced, vector) == fixture
        assert c._logical(fixture, produced, vector) == again
        assert (vector, produced, fixture, prefix) == before


@pytest.mark.parametrize("mutation", ["target", "upvalue"])
def test_logical_join_rejects_forged_factory_closure(cases, mutation):
    vector, produced, fixture, _, _ = cases[-1]
    forged = copy.deepcopy(produced)
    forged["closure"] = (
        "closure",
        0x006EC111 if mutation == "target" else 0x006EC110,
        ("userdata", U ^ int(mutation == "upvalue")),
    )
    with pytest.raises(RuntimeError):
        c._logical(fixture, forged, vector)


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (
        PREFIX + "native_lua_class_factory_callback_empty_class_conformance.json"
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


def test_sealed_receipt_exact_bytes_summary_nineteen_source_pins_and_bounded_scope(
    receipts,
):
    path, evidence, _, sources = receipts
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert b"\r" not in path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert len(sources) == len(c.SOURCE_PINS) == 19
    assert {
        "full_factory",
        "factory_callback_entry",
        "class_empty",
        "marker",
        "small_copy",
    } <= set(sources)
    assert evidence["summary"] == dict(
        cases=54,
        static_sites=955,
        executed_sites=261,
        instruction_bytes=2470,
        factory_instructions=35820,
        callback_and_class_instructions=15552,
        factory_api_calls=1836,
        callback_api_calls=648,
        factory_heap_calls=54,
        class_heap_calls=54,
        class_heap_bytes=432,
        marker_calls=108,
        tree_insertions=0,
        free_calls=0,
        controls=22,
        opaque_native_instructions=0,
        accounting_promotions=0,
    )
    assert evidence["scope"]["continuous_factory"] is True
    assert evidence["scope"]["continuous_callback_markers_and_class"] is True
    assert evidence["scope"]["continuous_across_host"] is False
    excluded = " ".join(evidence["scope"]["excluded"])
    assert all(
        text in excluded
        for text in (
            "Lua VM invocation",
            "callback suffix",
            "Nonempty source",
            "Heap ownership",
            "accounting promotion",
        )
    )


def test_exact_normal_partition_sixty_seven_prefix_plus_194_class_and_694_excluded(
    receipts,
):
    _, evidence, _, sources = receipts
    partition = evidence["normal_site_partition"]
    prefix, child, excluded = (
        set(partition[key])
        for key in ("callback_and_markers", "empty_class", "excluded")
    )
    selected = {point["rva"] for point in evidence["body"]["points"]}
    executed = set(evidence["executed_rvas"])
    assert len(selected) == 955 and len(executed) == 261
    assert (len(prefix), len(child), len(excluded)) == (67, 194, 694)
    assert prefix == set(sources["factory_callback_entry"]["executed_rvas"])
    assert not prefix & child and not executed & excluded
    assert prefix | child == executed and executed | excluded == selected
    assert child == {
        point["rva"]
        for point in evidence["body"]["points"]
        if any(
            start <= int(point["rva"], 16) < end for start, end in c.NORMAL_CLASS_RANGES
        )
    }
    assert {
        "0x002eb140",
        "0x002eb200",
        "0x002eb216",
        "0x002eb22a",
        "0x003574ca",
    } <= child
    assert "0x002ec1bd" not in selected
    assert {"0x002eb15f", "0x002eb1c5"} <= excluded
    assert "0x003574d5" not in executed
    assert sum(point["size"] for point in evidence["body"]["points"]) == 2470


def test_all_twenty_two_negative_controls_have_independent_exact_reasons(receipts):
    _, evidence, _, _ = receipts
    reasons = {
        **{
            key: "callback entry protected pages differ"
            for key in (
                "userdata",
                "record",
                "local_record",
                "continuation",
                "ancestor",
                "reference",
                "source",
                "record_padding",
                "vector",
                "capacity",
                "cookie",
                "context",
            )
        },
        "receiver_register": "callback entry registers or flags differ",
        "flags": "callback entry registers or flags differ",
        "upvalue_response": "callback entry userdata identity differs",
        "marker_response": "callback entry left prefix",
        "argument_marker": "callback entry left prefix",
        "heap_request": "factory callback heap request differs",
        "heap_register": "factory callback heap ABI differs",
        "heap_flags": "factory callback heap ABI differs",
        "class_entry_flags": "factory callback class entry differs",
        "heap_response": "callback entry ordered events differ",
    }
    assert c.CONTROLS == reasons
    assert len(evidence["negative_controls"]) == len(reasons) == 22
    assert {
        row["kind"]: row["reason"] for row in evidence["negative_controls"]
    } == reasons
    assert all(row["rejected"] is True for row in evidence["negative_controls"])


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
        "prefix_partition",
        "class_partition",
        "excluded_partition",
        "host_claim",
    ],
)
def test_modified_receipt_rejected_by_seal(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    if mutation == "summary":
        changed["summary"]["class_heap_bytes"] -= 8
    elif mutation == "vector":
        changed["vectors"][0]["vector_alignment"] = 1
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
    elif mutation.endswith("partition"):
        key = {
            "prefix_partition": "callback_and_markers",
            "class_partition": "empty_class",
            "excluded_partition": "excluded",
        }[mutation]
        changed["normal_site_partition"][key].pop()
    elif mutation == "host_claim":
        changed["scope"]["continuous_across_host"] = True
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ["missing", "extra", "pin", "kind"])
def test_strict_nineteen_source_partition_and_content_identity(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["factory_callback_entry"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["class_empty"]["schema_version"] += 1
    else:
        changed["marker"]["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c._preflight(changed)
    with pytest.raises(RuntimeError):
        c.validate_structure(evidence, changed)


def command_for(command, paths):
    result = [sys.executable, str(CLI), command]
    for key, path in paths.items():
        result += ["--" + key.replace("_", "-"), str(path)]
    return result


def test_cli_structure_exact_utf8_lf_and_noncanonical_rejection(receipts, tmp_path):
    path, evidence, paths, sources = receipts
    command = command_for("verify-structure", paths)
    result = subprocess.run(
        command + ["--evidence", str(path)], cwd=ROOT, capture_output=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    expected = c.encode_conformance(c.validate_structure(evidence, sources)).encode(
        "utf-8"
    )
    assert result.stderr == b"" and result.stdout == expected
    assert result.stdout.endswith(b"\n") and b"\r" not in result.stdout
    noncanonical = tmp_path / "empty-class.json"
    noncanonical.write_text(json.dumps(evidence), encoding="utf-8")
    result = subprocess.run(
        command + ["--evidence", str(noncanonical)],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 1 and result.stdout == b""
    assert b"not deterministically encoded" in result.stderr


def test_exact_native_capture_class_allocation_controls_and_rebuild_subprocess(
    receipts,
):
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
