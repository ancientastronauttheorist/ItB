"""Independent allocation/frame/record laws for a continuous factory prefix."""

import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_factory_record_conformance as c
from src.observatory import native_self_linked_record_semantics as model

factory, parent = c.factory, c.parent
ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_record_conformance.py"
CANONICAL = "94fb1682f5d89c131e6fe2eab62e926f0f4b71494d0fa12a5e89762dd8253a79"
RAW = "bc514c41fd8c2779e4e8c97aee406d4c05b4cbada41aa5daaf9e474e57372c23"
GEOMETRIES = list(itertools.product((0x100, 0xFFF), (0, 7, 15, 31)))


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


@pytest.fixture(scope="module")
def cases():
    bases = [
        v
        for v in factory.vectors()
        if v["name_alignment"] == {"ascii": 0, "low": 7, "high": 4095}[v["pattern"]]
        and v["equal_pointers"] == bool((v["length"] + v["profile"]) % 2)
    ]
    assert len(bases) == 36
    result = []
    for index, base in enumerate(bases):
        bias, alignment = GEOMETRIES[index % len(GEOMETRIES)]
        vector = dict(base, record_bias=bias, record_alignment=alignment)
        fixture = c._extend_fixture(vector, factory._fixture(base))
        original = factory._expected(base, fixture)
        before = parent._extend_expected(base, fixture, original)
        result.append(
            (
                vector,
                fixture,
                original,
                before,
                c._extend_expected(vector, fixture, original),
            )
        )
    return result


def independent_pages(fixture, before):
    frame, record = before["registers"]["ebp"], fixture["record"]
    stores = {
        frame - 36: 0,
        frame - 40: 24,
        frame - 44: c.BASE + 0x7C607,
        frame - 48: frame,
        frame - 52: 24,
        frame - 56: c.BASE + 0x357507,
        frame - 60: frame - 48,
        frame - 64: fixture["userdata"] + 52,
        frame - 68: 24,
        frame - 72: 0,
        frame - 76: c.allocation.HEAP_HANDLE,
        frame - 80: c.BASE + 0x389463,
        fixture["userdata"] + 52: record,
        record: record,
        record + 4: record,
        record + 8: record,
    }
    pages = before["pages"]
    for address, value in stores.items():
        pages = change(pages, address, value)
    return change(pages, record + 12, 0x0101, 2)


def independent_suffix_events(fixture, before):
    frame, record = before["registers"]["ebp"], fixture["record"]
    events = []

    def event(access, address, value, width=4):
        events.append(dict(access=access, address=address, width=width, value=value))

    # Retry entry N=G-44, its EBP=G-48; thunk and heap EBP=G-60.
    for address, value in (
        (frame - 40, 24),
        (frame - 44, c.BASE + 0x7C607),
        (frame - 48, frame),
    ):
        event("write", address, value)
    event("read", frame - 40, 24)
    for address, value in (
        (frame - 52, 24),
        (frame - 56, c.BASE + 0x357507),
        (frame - 60, frame - 48),
    ):
        event("write", address, value)
    event("read", frame - 60, frame - 48)
    event("write", frame - 60, frame - 48)
    event("write", frame - 64, fixture["userdata"] + 52)
    event("read", frame - 52, 24)
    event("write", frame - 68, 24)
    event("write", frame - 72, 0)
    event("read", c.allocation.HEAP_GLOBAL, c.allocation.HEAP_HANDLE)
    event("write", frame - 76, c.allocation.HEAP_HANDLE)
    event("read", c.allocation.IAT, factory.IMPORT)
    event("write", frame - 80, c.BASE + 0x389463)
    # The supplied stdcall response consumes return+three arguments; all later
    # pops/returns are actual reads in the native caller chain.
    for address, value in (
        (frame - 64, fixture["userdata"] + 52),
        (frame - 60, frame - 48),
        (frame - 56, c.BASE + 0x357507),
        (frame - 52, 24),
        (frame - 48, frame),
        (frame - 44, c.BASE + 0x7C607),
    ):
        event("read", address, value)
    for offset, width, value in (
        (0, 4, record),
        (4, 4, record),
        (8, 4, record),
        (12, 2, 0x0101),
    ):
        event("write", record + offset, value, width)
    event("read", frame - 36, c.BASE + parent.END)
    event("write", frame - 36, 0)
    event("write", fixture["userdata"] + 52, record)
    return events


def test_vector_geometry_full_corpus_and_strict_new_dimensions():
    vectors = c.vectors()
    assert len(vectors) == 1728
    assert len({c._canonical_sha256(v) for v in vectors}) == 1728
    assert {tuple((v["record_bias"], v["record_alignment"])) for v in vectors} == set(
        GEOMETRIES
    )
    assert all(c._base_vector(v) in factory.vectors() for v in vectors)
    assert all(
        type(v["record_bias"]) is int and type(v["record_alignment"]) is int
        for v in vectors
    )


def test_extended_fixture_heap_binding_and_cross_page_record_extent(cases):
    assert {(v["record_bias"], v["record_alignment"]) for v, *_ in cases} == set(
        GEOMETRIES
    )
    crossed = False
    for vector, fixture, _, _, _ in cases:
        pointer = fixture["record"]
        assert pointer == c.RECORD + vector["record_bias"] + vector["record_alignment"]
        assert (
            raw(fixture["pages"], c.allocation.HEAP_GLOBAL) == c.allocation.HEAP_HANDLE
        )
        assert raw(fixture["pages"], c.allocation.IAT) == factory.IMPORT
        assert (
            bytes(raw(fixture["pages"], pointer + i, 1) for i in range(24))
            == b"\xc7" * 24
        )
        crossed |= pointer & ~4095 != (pointer + 23) & ~4095
    assert crossed


def test_complete_independent_pages_and_ordered_native_suffix_events(cases):
    for _, fixture, original, before, expected in cases:
        assert expected["pages"] == independent_pages(fixture, before)
        assert expected["events"] == before["events"] + independent_suffix_events(
            fixture, before
        )
        assert expected["calls"] == original["calls"] == before["calls"]
        assert len(expected["calls"]) == 7
        assert expected["logical"]["prefix"] == before["logical"]
        assert expected["logical"]["record"] == model.apply(pointer=fixture["record"])


def test_three_links_two_marker_bytes_padding_and_actual_userdata_store(cases):
    for _, fixture, _, before, expected in cases:
        pointer, pages = fixture["record"], expected["pages"]
        assert expected["record"] == pointer
        assert [raw(pages, pointer + offset) for offset in (0, 4, 8)] == [pointer] * 3
        assert raw(pages, pointer + 12, 2) == 0x0101
        assert raw(pages, fixture["userdata"] + 52) == pointer
        assert raw(pages, fixture["userdata"] + 56) == 0
        for offset in range(14, 24):
            assert (
                raw(pages, pointer + offset, 1)
                == raw(before["pages"], pointer + offset, 1)
                == 0xC7
            )
        changed_addresses = set(range(pointer, pointer + 14))
        for page in (c.RECORD, c.RECORD + 4096):
            for offset, byte in enumerate(pages[page]):
                if page + offset not in changed_addresses:
                    assert byte == before["pages"][page][offset]
        assert expected["logical"]["record"]["untouched_offsets"] == list(range(14, 24))


def test_exact_stdcall_heap_request_gprs_response_and_native_frame_cleanup(cases):
    for _, fixture, _, before, expected in cases:
        regs, frame = before["registers"], before["registers"]["ebp"]
        helper = regs["esp"]
        retry = helper - 8
        assert helper == frame - 36 and retry == frame - 44
        assert expected["heap_calls"] == [
            dict(
                entry_esp=retry - 36,
                continuation=c.BASE + 0x389463,
                arguments=[c.allocation.HEAP_HANDLE, 0, 24],
                entry_registers=dict(
                    eax=regs["eax"],
                    ebx=regs["ebx"],
                    ecx=regs["ecx"],
                    edx=regs["edx"],
                    esi=24,
                    edi=regs["edi"],
                    ebp=retry - 16,
                    esp=retry - 36,
                ),
                response=dict(
                    eax=fixture["record"], ecx=0xA0000001, edx=0xB0000001, eflags=0x246
                ),
            )
        ]
        final = expected["registers"]
        assert final == dict(
            eax=fixture["record"],
            ebx=regs["ebx"],
            ecx=fixture["record"] + 8,
            edx=0xB0000001,
            esi=fixture["userdata"] + 52,
            edi=regs["edi"],
            ebp=frame,
            esp=helper,
        )
        word = fixture["record"] + 8
        flags = (4 if (word & 255).bit_count() % 2 == 0 else 0) | (
            0x80 if word & 0x80000000 else 0
        )
        assert expected["flags"] == flags
        assert raw(expected["pages"], helper) == 0
        assert raw(before["pages"], helper) == c.BASE + parent.END
        # ADD ESP,4 removes the retry request and RET removes helper RA;
        # initializer PUSH0 reuses precisely that former return-address cell.
        assert raw(expected["pages"], retry + 4) == 24
        assert raw(expected["pages"], retry) == c.BASE + 0x7C607


def test_nested_fs_cookie_outer_ancestors_and_prior_userdata_fields_preserved(cases):
    for _, fixture, _, before, expected in cases:
        frame = before["registers"]["ebp"]
        pages = expected["pages"]
        outer = raw(pages, frame)
        assert raw(pages, 0) == frame - 12
        assert raw(pages, frame - 12) == outer - 12
        assert raw(pages, outer - 12) == raw(fixture["pages"], 0)
        assert raw(pages, frame - 32) == raw(fixture["pages"], factory.COOKIE) ^ frame
        for offset in (0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 56, 60, 64, 68):
            assert raw(pages, fixture["userdata"] + offset) == raw(
                before["pages"], fixture["userdata"] + offset
            )
        for page in (factory.STACK, factory.STACK + 4096):
            offset = max(0, min(4096, fixture["entry"] - page))
            assert pages[page][offset:] == fixture["pages"][page][offset:]
        for page in (factory.FIRST, factory.FIRST + 4096, factory.SECOND):
            assert pages[page] == before["pages"][page]


@pytest.mark.parametrize("offset", [0, 4, 8, 12, 14, 23])
def test_independent_record_page_oracle_rejects_forged_links_marker_padding(
    cases, offset
):
    _, fixture, _, before, expected = cases[-1]
    address = fixture["record"] + offset
    forged = change(
        expected["pages"], address, raw(expected["pages"], address, 1) ^ 1, 1
    )
    assert independent_pages(fixture, before) == expected["pages"] != forged


@pytest.mark.parametrize(
    "kind",
    [
        "stored_record",
        "fs",
        "cookie",
        "heap_return",
        "retry_saved_frame",
        "heap_saved_esi",
        "reused_return_cell",
        "ancestor",
        "heap_global",
    ],
)
def test_independent_frame_and_userdata_oracle_rejects_forged_outputs(cases, kind):
    _, fixture, _, before, expected = cases[-1]
    frame = before["registers"]["ebp"]
    address = {
        "stored_record": fixture["userdata"] + 52,
        "fs": 0,
        "cookie": frame - 32,
        "heap_return": frame - 80,
        "retry_saved_frame": frame - 48,
        "heap_saved_esi": frame - 64,
        "reused_return_cell": frame - 36,
        "ancestor": fixture["entry"] + 8,
        "heap_global": c.allocation.HEAP_GLOBAL,
    }[kind]
    forged = change(expected["pages"], address, raw(expected["pages"], address) ^ 1)
    if kind == "stored_record":
        # Matching forged self links must not replace the supplied allocation pointer.
        for offset in (0, 4, 8):
            forged = change(forged, fixture["record"] + offset, fixture["record"] ^ 1)
    assert independent_pages(fixture, before) == expected["pages"] != forged


def test_extension_deterministic_and_preserves_prior_live_pages(cases):
    vector, fixture, original, _, expected = cases[-1]
    before = copy.deepcopy((vector, fixture, original))
    assert c._extend_expected(vector, fixture, original) == expected
    assert (vector, fixture, original) == before
    base = c._base_vector(vector)
    fixture_original = factory._fixture(base)
    pristine = copy.deepcopy(fixture_original)
    assert c._extend_fixture(vector, fixture_original) == fixture
    assert fixture_original == pristine


@pytest.mark.parametrize(
    "field,value",
    [
        ("record_bias", True),
        ("record_bias", 0x100 + 1),
        ("record_bias", 256.0),
        ("record_alignment", False),
        ("record_alignment", -1),
        ("record_alignment", 32),
        ("record_alignment", 7.0),
    ],
)
def test_record_geometry_type_and_corpus_guards(field, value):
    vector = dict(c.vectors()[0], **{field: value})
    with pytest.raises(RuntimeError):
        c._base_vector(vector)


@pytest.mark.parametrize("mutation", ["missing", "extra", "nondict", "mapping_overlap"])
def test_record_extension_rejects_schema_or_mapping_overlap(mutation):
    vector = c.vectors()[0]
    if mutation == "missing":
        del vector["record_bias"]
        with pytest.raises(RuntimeError):
            c._base_vector(vector)
    elif mutation == "extra":
        vector["unreviewed"] = 0
        with pytest.raises(RuntimeError):
            c._base_vector(vector)
    elif mutation == "nondict":
        with pytest.raises(RuntimeError):
            c._base_vector([])
    else:
        fixture = factory._fixture(c._base_vector(vector))
        fixture["pages"][c.RECORD] = bytes(4096)
        with pytest.raises(RuntimeError):
            c._extend_fixture(vector, fixture)


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (PREFIX + "native_lua_class_factory_record_conformance.json")
    if not path.exists() or c.SEALED_SHA256 in ("UNSEALED", "PENDING"):
        pytest.skip("awaiting reviewed continuous factory record seal")
    evidence = json.loads(path.read_text())
    paths, sources = {}, {}
    for key, (kind, digest) in c.SOURCE_PINS.items():
        suffix = "program_facts" if key == "program_facts" else kind.removeprefix("pe_")
        source_path = PROGRAMS / (PREFIX + suffix + ".json")
        sources[key] = json.loads(source_path.read_text())
        assert c._canonical_sha256(sources[key]) == digest
        paths[key] = source_path
    return path, evidence, paths, sources


def test_receipt_seal_complete_coverage_counts_controls_and_conditional_scope(receipts):
    path, evidence, _, sources = receipts
    assert len(c.SOURCE_PINS) == 7
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    for key, value in dict(
        cases=1728,
        static_sites=195,
        executed_sites=160,
        instruction_bytes=576,
        native_instructions=609408,
        supplied_api_calls=12096,
        heap_calls=1728,
        controls=30,
        initializer_instructions=67392,
        self_linked_helper_instructions=27648,
        allocation_native_instructions=58752,
        opaque_native_instructions=0,
        accounting_promotions=0,
    ).items():
        assert evidence["summary"][key] == value
    points = evidence["body"]["points"]
    assert len(points) == 195
    required = set(sources["initializer_prefix"]["executed_rvas"])
    required.update(
        p["rva"]
        for p in points
        if c.HELPER <= int(p["rva"], 16) < c.HELPER_END
        or parent.END <= int(p["rva"], 16) < c.END
    )
    allocation_ranges = [
        c.allocation.BODIES[k] for k in ("retry", "thunk", "heap_wrapper")
    ]
    required.update(
        pc
        for pc in sources["allocation"]["executed_rvas"]
        if any(a <= int(pc, 16) < b for a, b in allocation_ranges)
    )
    assert set(evidence["executed_rvas"]) == required and len(required) == 160
    assert f"0x{c.END:08x}" not in required
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    assert len(controls) == len(evidence["negative_controls"]) == 30
    assert set(controls) == set(parent.CONTROLS) | {
        "record_link",
        "record_marker",
        "record_padding",
        "record_tail",
        "heap_global",
        "stored_record",
        "heap_request",
        "heap_response",
    }
    assert all(
        row["rejected"] and row["reason"] == c.CONTROLS[kind]
        for kind, row in controls.items()
    )
    assert evidence["scope"]["continuous_machine"] is True
    assert "HeapAlloc" in evidence["scope"]["supplied_apis"]
    excluded = " ".join(evidence["scope"]["excluded"])
    assert (
        "Actual allocator DLL instructions" in excluded and "heap ownership" in excluded
    )
    assert "initializer return" in excluded and "No accounting promotion" in excluded


@pytest.mark.parametrize("mutation", ["summary", "vector", "control", "body", "kind"])
def test_modified_receipt_rejected(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    if mutation == "summary":
        changed["summary"]["heap_calls"] += 1
    elif mutation == "vector":
        changed["vectors"][0]["record_bias"] = 0xFFF
    elif mutation == "control":
        changed["negative_controls"][0]["rejected"] = False
    elif mutation == "body":
        changed["body"]["ranges"][0]["sha256"] = "0" * 64
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ["missing", "extra", "pin", "kind"])
def test_strict_source_partition_and_identity_preflight(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["allocation"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["initializer_prefix"]["schema_version"] += 1
    else:
        changed["record_helper_chain"]["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c._preflight(changed)
    with pytest.raises(RuntimeError):
        c.validate_structure(evidence, changed)


def command_for(command, paths):
    result = [sys.executable, str(CLI), command]
    for key, path in paths.items():
        result += ["--" + key.replace("_", "-"), str(path)]
    return result


def test_cli_structure_strict_bytes_and_noncanonical_rejection(receipts, tmp_path):
    path, evidence, paths, sources = receipts
    command = command_for("verify-structure", paths)
    result = subprocess.run(
        command + ["--evidence", str(path)], cwd=ROOT, capture_output=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == c.encode_conformance(
        c.validate_structure(evidence, sources)
    ).encode("utf-8")
    noncanonical = tmp_path / "record.json"
    noncanonical.write_text(json.dumps(evidence), encoding="utf-8")
    result = subprocess.run(
        command + ["--evidence", str(noncanonical)],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 1 and result.stdout == b""
    assert b"not deterministically encoded" in result.stderr


def test_exact_full_cli_rebuild_isolated_native_subprocess(receipts):
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
