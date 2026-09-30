"""Host byte patches and callback entry laws; native capture stays subprocess-only."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_factory_callback_entry_conformance as c

factory, full, record, callback, marker, layout = (
    c.factory,
    c.full,
    c.record,
    c.callback,
    c.marker,
    c.layout,
)
ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_callback_entry_conformance.py"
CANONICAL = "cca405ff5c16dfebb85f23c07e5333c14b300c209ad24dfab42033d17c89b94e"
RAW = "b7485db988408f110547fe5475ebbf55dabbea908c9b86699393549fbcbf1a0b"


def normalized(value):
    return json.loads(json.dumps(value))


def raw(pages, address, width=4):
    return int.from_bytes(
        bytes(pages[(address + i) & ~4095][(address + i) & 4095] for i in range(width)),
        "little",
    )


def change(pages, address, value, width=4):
    result = dict(pages)
    for i, byte in enumerate(value.to_bytes(width, "little")):
        page = (address + i) & ~4095
        payload = bytearray(result[page])
        payload[(address + i) & 4095] = byte
        result[page] = bytes(payload)
    return result


def independent_host_boundary(produced, vector):
    """Patch only named bytes; newly required pages start with synthetic A5."""
    pages = dict(produced["pages"])
    patches = []
    entry = 0x30000800 + 15 * vector["profile"]
    writes = [
        (0x400000 + slot, layout.TARGETS[name].to_bytes(4, "little"))
        for name, slot in layout.SLOTS.items()
    ]
    writes += list(layout.LITERALS.items())
    writes += [
        (entry, (0x0400A000).to_bytes(4, "little")),
        (entry + 4, produced["fixture"]["state"].to_bytes(4, "little")),
    ]
    for start, payload in writes:
        for offset, byte in enumerate(payload):
            address = start + offset
            pages.setdefault(address & ~4095, b"\xa5" * 4096)
            patches.append(
                dict(address=address, before=raw(pages, address, 1), after=byte)
            )
            pages = change(pages, address, byte, 1)
    return pages, patches


def independent_prefix_pages(fixture):
    """Closed endpoint cells after two truthy native marker bodies and direct APIs."""
    entry, state = fixture["entry"], fixture["state"]
    frame = entry - 4
    cells = {
        frame: fixture["registers"]["ebp"],
        frame - 8: raw(fixture["pages"], 0x893F28) ^ frame,
        frame - 20: fixture["receiver"],
        frame - 28: fixture["registers"]["ebx"],
        frame - 32: fixture["registers"]["esi"],
        frame - 36: fixture["registers"]["edi"],
        frame - 16: 0,
        frame - 12: fixture["source_pointer"],
        frame - 40: entry - 20,
        frame - 44: 0x6EC1BD,
        frame - 48: 0x6EC1A3,
        frame - 52: state,
        frame - 56: 0x6EB5A0,
        frame - 60: state,
        frame - 64: 0xFFFFFFFF,
        frame - 68: state,
        frame - 72: 0x6EB590,
    }
    pages = dict(fixture["pages"])
    for address, value in cells.items():
        pages = change(pages, address, value)
    return pages


def add_flags(left, right):
    total, value = left + right, (left + right) & 0xFFFFFFFF
    return (
        int(total > 0xFFFFFFFF)
        | (4 if (value & 255).bit_count() % 2 == 0 else 0)
        | ((left ^ right ^ value) & 0x10)
        | (0x40 if value == 0 else 0)
        | (0x80 if value & 0x80000000 else 0)
        | (0x800 if (~(left ^ right) & (left ^ value)) & 0x80000000 else 0)
    )


@pytest.fixture(scope="module")
def cases():
    # These are synthetic pages from the existing pure physical factory oracle.
    # They test the host/prefix laws under explicit premises. Only the gated
    # native CLI test captures real Unicorn factory output through _produce.
    selected = [
        v
        for v in c.vectors()
        if v["record_bias"]
        == (0xFFF if (v["registry_profile"] + v["profile"]) % 2 else 0x100)
    ]
    assert len(selected) == 24
    result = []
    for vector in selected:
        base = record._base_vector(full._record_vector(vector))
        original_fixture = full._extend_fixture(vector, factory._fixture(base))
        original = factory._expected(base, original_fixture)
        physical = full._extend_expected(vector, original_fixture, original)
        produced = dict(
            fixture=original_fixture,
            pages=physical["pages"],
            registers=physical["registers"],
            lua_result=physical["lua_result"],
            closure=("closure", 0x6EC110, ("userdata", original_fixture["userdata"])),
        )
        fixture = c._resume(produced, vector)
        prefix_vector = dict(
            frame_alignment=15 * vector["profile"],
            marker_words=[(0, 0x12345678)[vector["profile"]], 0xFFFFFFFF],
        )
        expected = callback._expected(prefix_vector, fixture, class_entry_only=True)
        result.append((vector, produced, fixture, expected))
    return result


def test_exact_bounded_corpus_factory_profiles_registry_profiles_and_crossing_names():
    vectors = c.vectors()
    assert len(vectors) == 48 and len({c._canonical_sha256(v) for v in vectors}) == 48
    assert {v["profile"] for v in vectors} == {0, 1}
    assert {v["registry_profile"] for v in vectors} == {0, 1, 2}
    assert {v["length"] for v in vectors} == {0, 1, 16, 255}
    assert all(
        v["pattern"] == "high"
        and v["name_alignment"] == 4095
        and not v["equal_pointers"]
        and v["record_alignment"] == 0
        for v in vectors
    )
    assert {v["record_bias"] for v in vectors} == {0x100, 0xFFF}
    assert vectors == c.vectors()
    vectors[0]["length"] = 99
    assert c.vectors()[0]["length"] == 0


def test_independent_host_patch_sequence_and_all_original_unrelated_bytes_preserved(
    cases,
):
    for vector, produced, fixture, _ in cases:
        pages, patches = independent_host_boundary(produced, vector)
        assert fixture["pages"] == pages and fixture["patches"] == patches
        assert len(patches) == 97 and len({p["address"] for p in patches}) == 97
        addresses = {p["address"] for p in patches}
        for page, original in produced["pages"].items():
            actual = fixture["pages"][page]
            assert all(
                actual[i] == byte
                for i, byte in enumerate(original)
                if page + i not in addresses
            )
        for patch in patches:
            assert raw(fixture["pages"], patch["address"], 1) == patch["after"]
        assert fixture["entry"] == 0x30000800 + 15 * vector["profile"]
        assert fixture["registers"] == dict(produced["registers"], esp=fixture["entry"])
        assert (
            layout.validate_targets_and_pages(layout.TARGETS, fixture["pages"])
            == layout.TARGETS
        )


def test_host_new_pages_a5_padding_and_preexisting_page_identity_without_page_replacement(
    cases,
):
    _, produced, fixture, _ = cases[0]
    patches = {p["address"] for p in fixture["patches"]}
    added = set(fixture["pages"]) - set(produced["pages"])
    assert added
    assert added == {a & ~4095 for a in patches} - set(produced["pages"])
    for page in added:
        assert all(
            byte == 0xA5
            for i, byte in enumerate(fixture["pages"][page])
            if page + i not in patches
        )
    for page in set(produced["pages"]) - {a & ~4095 for a in patches}:
        assert fixture["pages"][page] == produced["pages"][page]


def test_complete_factory_storage_all_userdata_bytes_record_bytes_and_registry_refs_retained(
    cases,
):
    for vector, produced, fixture, expected in cases:
        u, p = produced["fixture"]["userdata"], produced["fixture"]["record"]
        assert (
            fixture["receiver"] == u
            and fixture["source_pointer"] == 0x18000001 + vector["profile"]
        )
        for start, size in ((u, 72), (p, 24)):
            original = bytes(raw(produced["pages"], start + i, 1) for i in range(size))
            assert (
                bytes(raw(fixture["pages"], start + i, 1) for i in range(size))
                == original
            )
            assert (
                bytes(raw(expected["pages"], start + i, 1) for i in range(size))
                == original
            )
        refs = produced["fixture"]["spec"]["references"]
        assert [raw(expected["pages"], u + offset) for offset in (24, 32, 40)] == [
            refs[2],
            refs[0],
            refs[1],
        ]
        assert raw(expected["pages"], u + 52) == p
        assert all(raw(expected["pages"], p + offset) == p for offset in (0, 4, 8))
        assert raw(expected["pages"], p + 12, 2) == 0x0101


def test_independent_all_final_prefix_pages_and_native_class_caller_join(cases):
    for vector, produced, fixture, expected in cases:
        logical = c._logical(fixture, produced, vector)
        assert expected["pages"] == independent_prefix_pages(fixture)
        assert (
            expected["endpoint"] == 0x6EB140
            and expected["registers"] == logical["class_caller"]["registers"]
        )
        caller = logical["class_caller"]
        assert caller["return_address"] == 0x6EC1BD
        assert caller["argaddress"] == fixture["entry"] - 20
        assert caller["argument_record"] == [0, fixture["source_pointer"]]
        assert [
            raw(expected["pages"], caller["registers"]["esp"] + 4 * i) for i in range(2)
        ] == [caller["return_address"], caller["argaddress"]]
        assert [
            raw(expected["pages"], caller["argaddress"] + 4 * i) for i in range(2)
        ] == caller["argument_record"]
        assert logical["record_extent"] == dict(
            pointer=produced["fixture"]["record"], size=24
        )
        assert logical["userdata_extent"] == dict(pointer=fixture["receiver"], size=72)


def test_parent_cookie_original_nvs_fs_and_factory_ancestors_preserved_at_class_entry(
    cases,
):
    for _, produced, fixture, expected in cases:
        frame = fixture["entry"] - 4
        assert raw(expected["pages"], frame) == fixture["registers"]["ebp"]
        assert (
            raw(expected["pages"], frame - 8)
            == raw(produced["pages"], 0x893F28) ^ frame
        )
        for displacement, register in ((28, "ebx"), (32, "esi"), (36, "edi")):
            assert (
                raw(expected["pages"], frame - displacement)
                == fixture["registers"][register]
            )
        assert raw(expected["pages"], 0) == raw(produced["pages"], 0)
        for page in (0x30000000, 0x30001000):
            offset = max(0, min(4096, fixture["entry"] + 8 - page))
            assert expected["pages"][page][offset:] == produced["pages"][page][offset:]
        assert not any(
            e["access"] == "write" and e["address"] == 0 for e in expected["events"]
        )


def test_actual_marker_child_entry_pages_from_running_parent_and_full_eax_truth_guards(
    cases,
):
    for vector, _, fixture, expected in cases:
        assert [(ch["kind"], ch["index"]) for ch in expected["children"]] == [
            ("marker", 0),
            ("marker", 1),
        ]
        pages, cursor = fixture["pages"], 0
        for index, child in enumerate(expected["children"]):
            cf, result = child["fixture"], child["result"]
            entry = fixture["entry"] - 44
            assert (
                cf["entry"] == entry and cf["endpoint"] == (0x6EC160, 0x6EC184)[index]
            )
            while cursor < len(expected["events"]):
                event = expected["events"][cursor]
                cursor += 1
                if event["access"] == "write":
                    pages = change(
                        pages, event["address"], event["value"], event["width"]
                    )
                if event == dict(
                    access="write", address=entry, width=4, value=cf["endpoint"]
                ):
                    break
            else:
                pytest.fail("missing actual child call frame")
            assert cf["pages"] == pages
            mv = dict(
                alignment=15 * vector["profile"],
                prefix_length=1,
                has_metatable=True,
                value_kind=("zero", "table")[index],
                final_void_eax=((0, 0x12345678)[vector["profile"]], 0xFFFFFFFF)[index],
            )
            assert result["pages"] == marker._stack_model(mv, cf)
            assert (
                expected["events"][cursor : cursor + len(result["events"])]
                == result["events"]
            )
            assert result["registers"]["eax"] == (mv["final_void_eax"] & 0xFFFFFF00) | 1
            assert result["registers"]["esp"] == fixture["entry"] - 40
            for register in ("ebx", "esi", "edi", "ebp"):
                assert result["registers"][register] == cf["registers"][register]


def test_logical_twelve_requests_exact_groups_identities_and_direct_native_frames(
    cases,
):
    for vector, produced, fixture, expected in cases:
        logical = c._logical(fixture, produced, vector)
        assert len(expected["calls"]) == len(logical["calls"]) == 12
        assert (
            logical["initial_lua_stack"]
            == logical["boundary_lua_stack"]
            == [("argument", fixture["source_pointer"])]
        )
        for native, request in zip(expected["calls"], logical["calls"]):
            assert (native["api"], native["arguments"], native["group"]) == (
                request["api"],
                [word & 0xFFFFFFFF for word in request["arguments"]],
                request["group"],
            )
            assert native["target"] == layout.TARGETS[native["api"]]
            if native["api"] in ("lua_touserdata", "lua_getmetatable", "lua_toboolean"):
                assert native["response"]["eax"] == request["result"]
        direct = [call for call in expected["calls"] if call["group"] == "direct"]
        assert [call["entry_esp"] for call in direct] == [fixture["entry"] - 52] * 2
        assert [call["continuation"] for call in direct] == [0x6EC134, 0x6EC1A3]
        assert [call["response"] for call in direct] == [
            callback._direct_response(1, fixture["receiver"]),
            callback._direct_response(2, fixture["source_pointer"]),
        ]


def test_native_endpoint_add_flags_including_af_and_clear_df_are_separate_from_logical_model(
    cases,
):
    assert {v["profile"] for v, *_ in cases} == {0, 1}
    for vector, produced, fixture, expected in cases:
        assert expected["flags"] == add_flags(fixture["entry"] - 48, 8)
        assert expected["flags"] == (0x4, 0x14)[vector["profile"]]
        assert expected["flags"] & 0x400 == 0
        assert "flags" not in c._logical(fixture, produced, vector)


def test_marker_incoming_all_gprs_and_exact_nested_cdecl_frames(cases):
    for vector, _, fixture, expected in cases:
        entry, state, userdata = fixture["entry"], fixture["state"], fixture["receiver"]
        for index, child in enumerate(expected["children"]):
            incoming = dict(
                eax=(
                    userdata
                    if index == 0
                    else ((0, 0x12345678)[vector["profile"]] & 0xFFFFFF00) | 1
                ),
                ebx=state,
                ecx=state,
                edx=(0xFFFFD8ED, 1)[index],
                esi=userdata,
                edi=layout.TARGETS["lua_touserdata"],
                ebp=entry - 4,
                esp=entry - 44,
            )
            assert child["fixture"]["registers"] == incoming
            calls = child["result"]["calls"]
            assert [call["entry_esp"] for call in calls] == [
                entry - 60,
                entry - 60,
                entry - 68,
                entry - 76,
                entry - 60,
            ]
            assert [call["continuation"] for call in calls] == [
                0x6EB56B,
                0x6EB57E,
                0x6EB587,
                0x6EB590,
                0x6EB5A0,
            ]
            assert [call["arguments"] for call in calls] == [
                [state, (0xFFFFD8ED, 1)[index]],
                [state, 0x83C738],
                [state, 0xFFFFFFFE],
                [state, 0xFFFFFFFF],
                [state, 0xFFFFFFFD],
            ]


def test_resume_and_logical_inputs_immutable_deterministic_and_detached(cases):
    for vector, produced, fixture, _ in cases[::6]:
        before = copy.deepcopy((vector, produced))
        second = c._resume(produced, vector)
        assert second == fixture and (vector, produced) == before
        second["registers"]["eax"] ^= 1
        second["patches"][0]["after"] ^= 1
        assert c._resume(produced, vector) == fixture
        assert (vector, produced) == before


@pytest.mark.parametrize("mutation", ["target", "upvalue"])
def test_logical_handoff_rejects_wrong_returned_closure_identity(cases, mutation):
    vector, produced, fixture, _ = cases[-1]
    forged = copy.deepcopy(produced)
    target = 0x6EC111 if mutation == "target" else 0x6EC110
    userdata = produced["fixture"]["userdata"] ^ int(mutation == "upvalue")
    forged["closure"] = ("closure", target, ("userdata", userdata))
    with pytest.raises(RuntimeError):
        c._logical(fixture, forged, vector)


@pytest.mark.parametrize(
    "cell",
    [
        "userdata",
        "record",
        "reference",
        "local_record",
        "continuation",
        "argument_pointer",
        "cookie",
        "ancestor",
        "factory_frame",
        "fs",
    ],
)
def test_independent_page_law_rejects_factory_and_class_caller_forgeries(cases, cell):
    _, produced, fixture, expected = cases[-1]
    entry = fixture["entry"]
    address = dict(
        userdata=fixture["receiver"],
        record=produced["fixture"]["record"] + 13,
        reference=fixture["receiver"] + 32,
        local_record=entry - 16,
        continuation=entry - 48,
        argument_pointer=entry - 44,
        cookie=entry - 12,
        ancestor=entry + 8,
        factory_frame=produced["fixture"]["entry"] - 16,
        fs=0,
    )[cell]
    forged = change(
        expected["pages"], address, raw(expected["pages"], address, 1) ^ 1, 1
    )
    assert expected["pages"] == independent_prefix_pages(fixture) != forged


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (
        PREFIX + "native_lua_class_factory_callback_entry_conformance.json"
    )
    evidence = json.loads(path.read_text())
    paths, sources = {}, {}
    for key, (kind, digest) in c.SOURCE_PINS.items():
        suffix = "program_facts" if key == "program_facts" else kind.removeprefix("pe_")
        source_path = PROGRAMS / (PREFIX + suffix + ".json")
        sources[key] = json.loads(source_path.read_text())
        assert c._canonical_sha256(sources[key]) == digest
        paths[key] = source_path
    return path, evidence, paths, sources


def test_receipt_seal_eleven_sources_all_eleven_controls_and_explicit_host_boundary(
    receipts,
):
    path, evidence, _, sources = receipts
    assert len(c.SOURCE_PINS) == 11 and {"full_factory", "callback", "marker"} <= set(
        c.SOURCE_PINS
    )
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert evidence["summary"] == dict(
        cases=48,
        static_sites=88,
        executed_sites=67,
        instruction_bytes=257,
        factory_instructions=27552,
        callback_instructions=4512,
        factory_api_calls=1632,
        callback_api_calls=576,
        heap_calls=48,
        marker_calls=96,
        controls=11,
        opaque_native_instructions=0,
        accounting_promotions=0,
    )
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    assert (
        set(controls)
        == set(c.CONTROLS)
        == {
            "userdata",
            "record",
            "local_record",
            "continuation",
            "ancestor",
            "reference",
            "receiver_register",
            "flags",
            "upvalue_response",
            "marker_response",
            "argument_marker",
        }
    )
    assert len(evidence["negative_controls"]) == 11
    assert all(
        row["rejected"] and row["reason"] == c.CONTROLS[kind]
        for kind, row in controls.items()
    )
    assert evidence["scope"]["continuous_factory"] is True
    assert evidence["scope"]["continuous_callback_and_markers"] is True
    assert evidence["scope"]["continuous_across_host"] is False
    excluded = " ".join(evidence["scope"]["excluded"])
    assert (
        "Class helper execution and callback return" in excluded
        and "accounting promotion" in excluded
    )


def test_static_ranges_exact_executed_partition_and_native_class_call_witness(receipts):
    _, evidence, _, sources = receipts
    points, ranges = evidence["body"]["points"], evidence["body"]["ranges"]
    assert [(int(r["start_rva"], 16), int(r["end_rva"], 16)) for r in ranges] == [
        (0x2EB560, 0x2EB5B4),
        (0x2EC110, 0x2EC1BD),
    ]
    assert sum(p["size"] for p in points) == 257
    assert [p for p in points if int(p["rva"], 16) < 0x2EC110] == sources["marker"][
        "body"
    ]["points"]
    unused_marker = {
        "0x002eb5a7",
        "0x002eb5ad",
        "0x002eb5b0",
        "0x002eb5b2",
        "0x002eb5b3",
    }
    required = {
        p["rva"]
        for p in points
        if p["rva"] not in unused_marker
        and not any(
            a <= int(p["rva"], 16) < b
            for a, b in (
                (0x2EC140, 0x2EC154),
                (0x2EC164, 0x2EC178),
                (0x2EC188, 0x2EC19E),
            )
        )
    }
    assert set(evidence["executed_rvas"]) == required and len(required) == 67
    assert (
        "0x002eb140" not in required
        and "0x002ec1bd" not in required
        and "0x002ec1b8" in required
    )
    by_rva = {p["rva"]: p for p in points}
    payload = b"\xe8" + (0x2EB140 - 0x2EC1BD).to_bytes(4, "little", signed=True)
    assert (
        by_rva["0x002ec1b8"]["size"] == 5
        and by_rva["0x002ec1b8"]["sha256"] == hashlib.sha256(payload).hexdigest()
    )


@pytest.mark.parametrize(
    "mutation",
    ["summary", "vector", "control", "body", "kind", "producer", "observations"],
)
def test_modified_receipt_rejected(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    if mutation == "summary":
        changed["summary"]["callback_api_calls"] -= 1
    elif mutation == "vector":
        changed["vectors"][0]["equal_pointers"] = True
    elif mutation == "control":
        changed["negative_controls"][0]["rejected"] = False
    elif mutation == "body":
        changed["body"]["ranges"][0]["sha256"] = "0" * 64
    elif mutation == "producer":
        changed["producer_observations_sha256"] = "0" * 64
    elif mutation == "observations":
        changed["observations_sha256"] = "0" * 64
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ["missing", "extra", "pin", "kind"])
def test_strict_eleven_source_partition_and_pin_preflight(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["full_factory"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["callback"]["schema_version"] += 1
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


def test_cli_structure_strict_utf8_lf_bytes_and_noncanonical_rejection(
    receipts, tmp_path
):
    path, evidence, paths, sources = receipts
    command = command_for("verify-structure", paths)
    result = subprocess.run(
        command + ["--evidence", str(path)], cwd=ROOT, capture_output=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    expected = c.encode_conformance(c.validate_structure(evidence, sources)).encode(
        "utf-8"
    )
    assert (
        result.stderr == b""
        and result.stdout == expected
        and result.stdout.endswith(b"\n")
    )
    assert b"\r" not in result.stdout
    noncanonical = tmp_path / "factory-callback-entry.json"
    noncanonical.write_text(json.dumps(evidence), encoding="utf-8")
    result = subprocess.run(
        command + ["--evidence", str(noncanonical)],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 1 and result.stdout == b""
    assert b"not deterministically encoded" in result.stderr


def test_exact_native_factory_capture_and_callback_rebuild_isolated_subprocess(
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
