"""Independent nested initializer fields/frame laws before the first helper."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_factory_initializer_prefix_conformance as c
from src.observatory import native_lua_class_initializer_prefix_semantics as model

factory = c.factory
ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_initializer_prefix_conformance.py"
CANONICAL = "abd888a364076edd037f460a0515b9586610218f9e5437aa4f67ab0cd972c47e"
RAW = "9f64ec4a0124e1ad7f52cda34c7faaa949e924484df55e9a8f40c24ab23e827f"


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


def fields(fixture):
    return [
        (0, 0x0089D1D4),
        (4, 0),
        (8, 0),
        (12, 0),
        (16, fixture["second_pointer"]),
        (20, 0),
        (24, 0xFFFFFFFE),
        (28, 0),
        (32, 0xFFFFFFFE),
        (36, 0),
        (40, 0xFFFFFFFE),
        (44, 1),
        (52, 0),
        (56, 0),
    ]


@pytest.fixture(scope="module")
def cases():
    selected = [
        v
        for v in c.vectors()
        if v["name_alignment"] == {"ascii": 0, "low": 7, "high": 4095}[v["pattern"]]
        and v["equal_pointers"] == bool((v["length"] + v["profile"]) % 2)
    ]
    assert len(selected) == 36
    result = []
    for vector in selected:
        fixture = factory._fixture(vector)
        parent = factory._expected(vector, fixture)
        result.append(
            (vector, fixture, parent, c._extend_expected(vector, fixture, parent))
        )
    return result


def independent_pages(fixture, parent):
    pages, registers = parent["pages"], parent["registers"]
    frame = registers["esp"] - 4
    userdata = fixture["userdata"]
    stores = {
        frame: registers["ebp"],
        frame - 4: 3,
        frame - 8: c.BASE + 0x3D107C,
        frame - 12: registers["ebp"] - 12,
        frame - 16: userdata,
        frame - 20: registers["ebx"],
        frame - 24: registers["esi"],
        frame - 28: registers["edi"],
        frame - 32: raw(parent["pages"], factory.COOKIE) ^ frame,
        frame - 36: c.BASE + c.END,
        frame + 12: userdata + 52,
        0: frame - 12,
    }
    for offset, value in fields(fixture):
        stores[userdata + offset] = value
    for address, value in stores.items():
        pages = change(pages, address, value)
    return pages


def independent_suffix_events(fixture, parent):
    frame, registers, events = parent["registers"]["esp"] - 4, parent["registers"], []
    userdata = fixture["userdata"]

    def event(access, address, value, width=4):
        events.append(dict(access=access, address=address, width=width, value=value))

    for address, value in (
        (frame, registers["ebp"]),
        (frame - 4, 0xFFFFFFFF),
        (frame - 8, c.BASE + 0x3D107C),
    ):
        event("write", address, value)
    event("read", 0, registers["ebp"] - 12)
    for address, value in (
        (frame - 12, registers["ebp"] - 12),
        (frame - 16, userdata),
        (frame - 20, registers["ebx"]),
        (frame - 24, registers["esi"]),
        (frame - 28, registers["edi"]),
    ):
        event("write", address, value)
    cookie = raw(parent["pages"], factory.COOKIE)
    event("read", factory.COOKIE, cookie)
    event("write", frame - 32, cookie ^ frame)
    event("write", 0, frame - 12)
    event("write", frame - 16, userdata)
    for offset, value in fields(fixture)[:4]:
        event("write", userdata + offset, value)
    event("read", frame + 12, fixture["second_pointer"])
    event("write", frame - 4, 0)
    for offset, value in fields(fixture)[4:11]:
        event("write", userdata + offset, value)
    event("write", frame - 4, 3, 1)
    event("write", userdata + 44, 1)
    event("write", frame + 12, userdata + 52)
    event("write", userdata + 52, 0)
    event("write", userdata + 56, 0)
    event("write", frame - 36, c.BASE + c.END)
    return events


def test_vector_geometry_preserved_from_sealed_factory():
    vectors = c.vectors()
    assert vectors == factory.vectors() and len(vectors) == 216
    assert {v["length"] for v in vectors} == {0, 1, 2, 15, 16, 255}
    assert {v["name_alignment"] for v in vectors} == {0, 7, 4095}
    assert {v["profile"] for v in vectors} == {0, 1}
    assert {v["equal_pointers"] for v in vectors} == {False, True}


def test_independent_complete_pages_exact_suffix_events_and_model(cases):
    for _, fixture, parent, expected in cases:
        assert expected["pages"] == independent_pages(fixture, parent)
        assert expected["events"] == parent["events"] + independent_suffix_events(
            fixture, parent
        )
        logical = model.apply(
            userdata=fixture["userdata"], name_pointer=fixture["second_pointer"]
        )
        assert expected["logical"] == dict(
            factory=parent["logical"], initializer_prefix=logical
        )
        assert logical["ordered_offset_writes"] == [
            dict(offset=offset, size=4, value=value)
            for offset, value in fields(fixture)
        ]
        assert logical["instruction_count"] == 37
        assert expected["calls"] == parent["calls"] and len(expected["calls"]) == 7
        field_events = [
            e
            for e in expected["events"][len(parent["events"]) :]
            if e["access"] == "write"
            and fixture["userdata"] <= e["address"] < fixture["userdata"] + 72
        ]
        assert field_events == [
            dict(
                access="write",
                address=fixture["userdata"] + offset,
                width=4,
                value=value,
            )
            for offset, value in fields(fixture)
        ]


def test_nested_fs_outer_frame_cookie_and_overwritten_argument(cases):
    for _, fixture, parent, expected in cases:
        outer = parent["registers"]["ebp"]
        entry = parent["registers"]["esp"]
        frame = entry - 4
        assert entry == outer - 48 and frame == fixture["entry"] - 56
        pages = expected["pages"]
        assert raw(pages, frame) == outer
        assert raw(pages, 0) == frame - 12
        assert raw(pages, frame - 12) == outer - 12
        assert raw(pages, outer - 12) == raw(fixture["pages"], 0)
        assert raw(pages, frame - 8) == c.BASE + 0x3D107C
        assert raw(pages, frame - 32) == raw(fixture["pages"], factory.COOKIE) ^ frame
        assert raw(pages, frame - 4) == 3
        assert raw(pages, frame - 16) == fixture["userdata"]
        assert raw(parent["pages"], frame + 12) == fixture["second_pointer"]
        assert raw(pages, frame + 12) == fixture["userdata"] + 52
        assert raw(pages, fixture["userdata"] + 16) == fixture["second_pointer"]
        suffix = expected["events"][len(parent["events"]) :]
        read_index = next(
            i
            for i, e in enumerate(suffix)
            if e
            == dict(
                access="read",
                address=frame + 12,
                width=4,
                value=fixture["second_pointer"],
            )
        )
        overwrite_index = next(
            i
            for i, e in enumerate(suffix)
            if e
            == dict(
                access="write",
                address=frame + 12,
                width=4,
                value=fixture["userdata"] + 52,
            )
        )
        assert read_index < overwrite_index
        for page in (factory.STACK, factory.STACK + 4096):
            offset = max(0, min(4096, fixture["entry"] - page))
            assert pages[page][offset:] == fixture["pages"][page][offset:]


def test_vtable_fourteen_words_untouched_userdata_and_source_bytes(cases):
    for _, fixture, parent, expected in cases:
        userdata = fixture["userdata"]
        written = {
            userdata + offset + i for offset, _ in fields(fixture) for i in range(4)
        }
        assert len(written) == 56
        for offset, value in fields(fixture):
            assert raw(expected["pages"], userdata + offset) == value
        for offset in (48, 60, 64, 68):
            assert raw(expected["pages"], userdata + offset) == raw(
                parent["pages"], userdata + offset
            )
        page = userdata & ~4095
        for address in range(page, page + 4096):
            if address not in written:
                assert raw(expected["pages"], address, 1) == raw(
                    parent["pages"], address, 1
                )
        for page in (factory.FIRST, factory.FIRST + 4096, factory.SECOND):
            assert expected["pages"][page] == parent["pages"][page]
        # The second pointer is a copied word; the initializer never reads its bytes.
        assert not any(
            e["access"] == "read" and e["width"] == 1
            for e in expected["events"][len(parent["events"]) :]
        )


def test_exact_helper_handoff_gprs_defined_xor_flags_and_live_stack(cases):
    for _, fixture, parent, expected in cases:
        frame = parent["registers"]["esp"] - 4
        userdata = fixture["userdata"]
        assert expected["registers"] == dict(
            eax=fixture["second_pointer"],
            ebx=parent["registers"]["ebx"],
            ecx=userdata,
            edx=parent["registers"]["edx"],
            esi=userdata + 52,
            edi=userdata,
            ebp=frame,
            esp=frame - 36,
        )
        assert raw(expected["pages"], frame - 36) == c.BASE + c.END
        assert (
            expected["logical"]["initializer_prefix"]["native_handoff"]["target_rva"]
            == c.HELPER
        )
        cookie = raw(fixture["pages"], factory.COOKIE) ^ frame
        flags = (
            (4 if (cookie & 255).bit_count() % 2 == 0 else 0)
            | (0x40 if cookie == 0 else 0)
            | (0x80 if cookie & 0x80000000 else 0)
        )
        assert (
            expected["flags"] == flags and expected["flags"] & ~factory.FLAG_MASK == 0
        )
        for offset, register in ((-20, "ebx"), (-24, "esi"), (-28, "edi")):
            assert (
                raw(expected["pages"], frame + offset) == parent["registers"][register]
            )


@pytest.mark.parametrize(
    "offset", [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68]
)
def test_independent_userdata_page_oracle_rejects_forged_written_and_untouched_fields(
    cases, offset
):
    _, fixture, parent, expected = cases[-1]
    address = fixture["userdata"] + offset
    forged = change(expected["pages"], address, raw(expected["pages"], address) ^ 1)
    assert independent_pages(fixture, parent) == expected["pages"] != forged


@pytest.mark.parametrize(
    "kind",
    [
        "active_fs",
        "inner_fs",
        "outer_fs",
        "inner_ebp",
        "cookie",
        "saved_edi",
        "argument",
        "return",
        "ancestor",
    ],
)
def test_independent_nested_frame_oracle_rejects_forged_outputs(cases, kind):
    _, fixture, parent, expected = cases[-1]
    frame, outer = parent["registers"]["esp"] - 4, parent["registers"]["ebp"]
    address = {
        "active_fs": 0,
        "inner_fs": frame - 12,
        "outer_fs": outer - 12,
        "inner_ebp": frame,
        "cookie": frame - 32,
        "saved_edi": frame - 28,
        "argument": frame + 12,
        "return": frame - 36,
        "ancestor": fixture["entry"] + 8,
    }[kind]
    forged = change(expected["pages"], address, raw(expected["pages"], address) ^ 1)
    assert independent_pages(fixture, parent) == expected["pages"] != forged


def test_extend_expected_deterministic_and_preserves_live_parent(cases):
    vector, fixture, parent, expected = cases[-1]
    before = copy.deepcopy((vector, fixture, parent))
    assert c._extend_expected(vector, fixture, parent) == expected
    assert (vector, fixture, parent) == before


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (
        PREFIX + "native_lua_class_factory_initializer_prefix_conformance.json"
    )
    if not path.exists() or c.SEALED_SHA256 in ("UNSEALED", "PENDING"):
        pytest.skip("awaiting reviewed continuous initializer prefix seal")
    evidence = json.loads(path.read_text())
    paths, sources = {}, {}
    for key, (kind, digest) in c.SOURCE_PINS.items():
        suffix = "program_facts" if key == "program_facts" else kind.removeprefix("pe_")
        source_path = PROGRAMS / (PREFIX + suffix + ".json")
        sources[key] = json.loads(source_path.read_text())
        assert c._canonical_sha256(sources[key]) == digest
        paths[key] = source_path
    return path, evidence, paths, sources


def test_sealed_encoding_complete_prefix_coverage_all_controls_and_stopping_scope(
    receipts,
):
    path, evidence, _, sources = receipts
    assert len(c.SOURCE_PINS) == 4
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    for key, value in dict(
        cases=216,
        static_sites=120,
        executed_sites=108,
        instruction_bytes=391,
        native_instructions=64944,
        supplied_api_calls=1512,
        controls=22,
        initializer_instructions=7992,
        self_linked_helper_instructions=0,
        opaque_native_instructions=0,
        accounting_promotions=0,
    ).items():
        assert evidence["summary"][key] == value
    points = evidence["body"]["points"]
    assert len(points) == 120
    required = {
        p["rva"]
        for p in points
        if not any(a <= int(p["rva"], 16) < b for a, b in factory.ERROR_RANGES)
    }
    assert set(evidence["executed_rvas"]) == required
    initializer = {p["rva"] for p in points if c.START <= int(p["rva"], 16) < c.END}
    assert len(initializer) == 37 and initializer <= required
    assert f"0x{c.HELPER:08x}" not in required
    assert set(sources["factory_prefix"]["executed_rvas"]) <= required
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    assert len(controls) == len(evidence["negative_controls"]) == 22
    assert set(controls) == set(factory.CONTROLS) | {
        "initializer_name",
        "initializer_sentinel",
        "initializer_unwritten",
        "outer_fs",
        "inner_fs",
        "overwritten_argument",
        "helper_return",
    }
    assert all(
        row["rejected"] and row["reason"] == c.CONTROLS[kind]
        for kind, row in controls.items()
    )
    assert evidence["scope"]["continuous_machine"] is True
    excluded = " ".join(evidence["scope"]["excluded"])
    assert "Self-linked helper" in excluded and "initializer return" in excluded
    assert (
        "Real Lua VM" in excluded
        and "heap ownership" in excluded
        and "No accounting promotion" in excluded
    )


@pytest.mark.parametrize("mutation", ["summary", "vector", "control", "body", "kind"])
def test_modified_receipt_rejected(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    if mutation == "summary":
        changed["summary"]["self_linked_helper_instructions"] = 1
    elif mutation == "vector":
        changed["vectors"][0]["equal_pointers"] = True
    elif mutation == "control":
        changed["negative_controls"][0]["rejected"] = False
    elif mutation == "body":
        changed["body"]["initializer_owner_sha256"] = "0" * 64
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ["missing", "extra", "pin", "kind"])
def test_strict_source_partition_and_pin_preflight(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["factory_prefix"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["factory_prefix"]["schema_version"] += 1
    else:
        changed["initializer_chain"]["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c._preflight(changed)
    with pytest.raises(RuntimeError):
        c.validate_structure(evidence, changed)


def command_for(command, paths):
    result = [sys.executable, str(CLI), command]
    for key, path in paths.items():
        result += ["--" + key.replace("_", "-"), str(path)]
    return result


def test_cli_verify_structure_strict_bytes_and_noncanonical_rejection(
    receipts, tmp_path
):
    path, evidence, paths, sources = receipts
    command = command_for("verify-structure", paths)
    result = subprocess.run(
        command + ["--evidence", str(path)], cwd=ROOT, capture_output=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == c.encode_conformance(
        c.validate_structure(evidence, sources)
    ).encode("utf-8")
    noncanonical = tmp_path / "initializer.json"
    noncanonical.write_text(json.dumps(evidence), encoding="utf-8")
    result = subprocess.run(
        command + ["--evidence", str(noncanonical)],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 1 and result.stdout == b""
    assert b"not deterministically encoded" in result.stderr


def test_exact_full_cli_rebuild_in_isolated_native_subprocess(receipts):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    path, _, paths, _ = receipts
    result = subprocess.run(
        command_for("build", paths) + ["--executable", executable],
        cwd=ROOT,
        capture_output=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == path.read_bytes()
