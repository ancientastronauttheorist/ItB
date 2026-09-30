"""Independent finite factory prefix frame/events/pages and sealed replay."""

import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_factory_prefix_conformance as c
from src.observatory import native_lua_class_factory_prefix_semantics as model

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_prefix_conformance.py"
CANONICAL = "cebf742aac9945f22829e2d3b1b387ff618840217b3c9a2330a8335ca3a0d0ed"
RAW = "dc56cc73bf36a0f1e642638f5d5f1b7ad80f7121f45dde197f0256f642bd9955"


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


def name_for(vector):
    pattern = {"ascii": b"Class", "low": b"\x01\x02", "high": b"\x80\xff"}[
        vector["pattern"]
    ]
    length = vector["length"]
    return (pattern * (length // len(pattern) + 1))[:length] + b"\0opaque\xff\0"


@pytest.fixture(scope="module")
def cases():
    # Thirty-six bounded page graphs; the sealed rebuild covers all 216 shapes.
    selected = [
        v
        for v in c.vectors()
        if v["name_alignment"] == {"ascii": 0, "low": 7, "high": 4095}[v["pattern"]]
        and v["equal_pointers"] == bool((v["length"] + v["profile"]) % 2)
    ]
    assert len(selected) == 36
    return [(v, f, c._expected(v, f)) for v in selected for f in [c._fixture(v)]]


def independent_pages(vector, fixture):
    frame = fixture["entry"] - 4
    pages = fixture["pages"]
    saved = fixture["registers"]
    words = {
        frame: saved["ebp"],
        frame - 4: 0,
        frame - 8: c.BASE + 0x3A6111,
        frame - 12: raw(pages, 0),
        frame - 16: fixture["userdata"],
        frame - 20: fixture["userdata"],
        frame - 24: saved["ebx"],
        frame - 28: saved["esi"],
        frame - 32: saved["edi"],
        frame - 36: raw(pages, c.COOKIE) ^ frame,
        frame - 40: fixture["second_pointer"],
        frame - 44: fixture["state"],
        frame - 48: c.BASE + c.END,
        frame - 52: c.BASE + 0x2EC2DC,
        0: frame - 12,
    }
    for address, value in words.items():
        pages = change(pages, address, value)
    return pages


def independent_events(vector, fixture):
    frame = fixture["entry"] - 4
    pages, registers, events = fixture["pages"], fixture["registers"], []

    def event(access, address, value, width=4):
        events.append(dict(access=access, address=address, width=width, value=value))

    for address, value in (
        (frame, registers["ebp"]),
        (frame - 4, 0xFFFFFFFF),
        (frame - 8, c.BASE + 0x3A6111),
    ):
        event("write", address, value)
    event("read", 0, raw(pages, 0))
    event("write", frame - 12, raw(pages, 0))
    for offset, register in ((-24, "ebx"), (-28, "esi"), (-32, "edi")):
        event("write", frame + offset, registers[register])
    event("read", c.COOKIE, raw(pages, c.COOKIE))
    event("write", frame - 36, raw(pages, c.COOKIE) ^ frame)
    event("write", 0, frame - 12)
    event("read", frame + 8, fixture["state"])
    state = fixture["state"]
    rows = [
        ("lua_gettop", [state], 0x2EC252),
        ("lua_type", [state, 1], 0x2EC269),
        ("lua_isnumber", [state, 1], 0x2EC27A),
        ("lua_tolstring", [state, 1, 0], 0x2EC29E),
        ("lua_objlen", [state, 1], 0x2EC2B8),
        ("lua_tolstring", [state, 1, 0], 0x2EC2DC),
        ("lua_newuserdata", [state, 72], 0x2EC2EA),
    ]
    for index, (api, arguments, continuation) in enumerate(rows):
        if index == 1:
            event(
                "read", c.BASE + c.SLOTS["lua_pushstring"], c.TARGETS["lua_pushstring"]
            )
        if index == 4:
            for offset, byte in enumerate(name_for(vector)[: vector["length"] + 1]):
                event("read", fixture["first_pointer"] + offset, byte, 1)
        for index_arg, value in enumerate(reversed(arguments), 1):
            event("write", frame - 36 - 4 * index_arg, value)
        event("read", c.BASE + c.SLOTS[api], c.TARGETS[api])
        event("write", frame - 40 - 4 * len(arguments), c.BASE + continuation)
    for address, value in (
        (frame - 16, fixture["userdata"]),
        (frame - 20, fixture["userdata"]),
        (frame - 4, 0),
        (frame - 40, fixture["second_pointer"]),
        (frame - 44, state),
        (frame - 48, c.BASE + c.END),
    ):
        event("write", address, value)
    return events


def test_vector_geometry_exact_cartesian_corpus_and_detachment():
    vectors = c.vectors()
    assert len(vectors) == 216
    tuples = {
        (
            v["length"],
            v["pattern"],
            v["name_alignment"],
            v["equal_pointers"],
            v["profile"],
        )
        for v in vectors
    }
    assert len(tuples) == len(vectors)
    assert tuples == set(
        itertools.product(
            (0, 1, 2, 15, 16, 255),
            ("ascii", "low", "high"),
            (0, 7, 4095),
            (False, True),
            (0, 1),
        )
    )
    assert all(
        type(v["length"]) is int and type(v["equal_pointers"]) is bool for v in vectors
    )
    pristine = c.vectors()
    vectors[0]["length"] = 99
    assert c.vectors() == pristine and vectors[1:] == pristine[1:]


def test_fixture_name_geometry_and_disjoint_userdata_pages(cases):
    for vector, fixture, _ in cases:
        assert fixture["entry"] == c.STACK + 4096 + 15 * vector["profile"]
        assert fixture["registers"]["esp"] == fixture["entry"]
        assert fixture["first_pointer"] == c.FIRST + vector["name_alignment"]
        assert fixture["second_pointer"] == (
            fixture["first_pointer"]
            if vector["equal_pointers"]
            else c.SECOND + 7 * vector["profile"]
        )
        assert fixture["userdata"] == c.USERDATA + 0x80 + 7 * vector["profile"]
        assert raw(fixture["pages"], fixture["entry"]) == 0x0400A000
        assert raw(fixture["pages"], fixture["entry"] + 4) == fixture["state"]
        assert all(
            type(page) is int and type(payload) is bytes and len(payload) == 4096
            for page, payload in fixture["pages"].items()
        )
        assert c._name(vector) == name_for(vector)
        assert bytes(
            raw(fixture["pages"], fixture["first_pointer"] + i, 1)
            for i in range(len(name_for(vector)))
        ) == name_for(vector)
        for api, slot in c.SLOTS.items():
            assert raw(fixture["pages"], c.BASE + slot) == c.TARGETS[api]
        if not vector["equal_pointers"]:
            assert fixture["second_pointer"] & ~4095 == c.SECOND
        if vector["name_alignment"] == 4095:
            assert fixture["first_pointer"] + len(name_for(vector)) > c.FIRST + 4096


def test_independent_whole_event_and_page_frame_oracles(cases):
    for vector, fixture, expected in cases:
        assert expected["events"] == independent_events(vector, fixture)
        assert expected["pages"] == independent_pages(vector, fixture)
        frame = fixture["entry"] - 4
        for page in (c.STACK, c.STACK + 4096):
            offset = max(0, min(4096, fixture["entry"] - page))
            assert expected["pages"][page][offset:] == fixture["pages"][page][offset:]
        for page, payload in fixture["pages"].items():
            if page not in (0, c.STACK, c.STACK + 4096):
                assert expected["pages"][page] == payload
        assert raw(expected["pages"], 0) == frame - 12
        assert raw(expected["pages"], frame - 12) == raw(fixture["pages"], 0)


def test_pointer_routing_scan_reads_api_frames_and_defined_gprs(cases):
    sites = (0x2EC24C, 0x2EC263, 0x2EC274, 0x2EC298, 0x2EC2B2, 0x2EC2D6, 0x2EC2E4)
    continuations = (
        0x2EC252,
        0x2EC269,
        0x2EC27A,
        0x2EC29E,
        0x2EC2B8,
        0x2EC2DC,
        0x2EC2EA,
    )
    for vector, fixture, expected in cases:
        logical = model.apply(
            name_for(vector),
            state=fixture["state"],
            first_pointer=fixture["first_pointer"],
            second_pointer=fixture["second_pointer"],
            userdata=fixture["userdata"],
        )
        assert expected["logical"] == logical
        byte_reads = [
            e for e in expected["events"] if e["access"] == "read" and e["width"] == 1
        ]
        assert byte_reads == [
            dict(
                access="read", address=fixture["first_pointer"] + i, width=1, value=byte
            )
            for i, byte in enumerate(name_for(vector)[: vector["length"] + 1])
        ]
        assert (
            logical["measured_length"] == vector["length"]
            and logical["byte_reads"] == vector["length"] + 1
        )
        frame, idle = fixture["entry"] - 4, fixture["entry"] - 40
        for index, (call, requested) in enumerate(
            zip(expected["calls"], logical["calls"])
        ):
            assert (call["api"], call["arguments"], call["response"]["eax"]) == (
                requested["api"],
                requested["arguments"],
                requested["result"],
            )
            assert call["target"] == c.TARGETS[call["api"]]
            assert (
                call["site_rva"] == f"0x{sites[index]:08x}"
                and call["continuation"] == c.BASE + continuations[index]
            )
            assert call["entry_esp"] == idle + requested["entry_esp_delta_from_idle"]
            assert call["entry_registers"]["esp"] == call["entry_esp"]
            assert (
                call["response"]["edx"]
                == 0xB1000000 + 0x100 * vector["profile"] + index
            )
        assert expected["calls"][4]["entry_registers"]["edi"] == vector["length"]
        assert (
            expected["calls"][6]["entry_registers"]["edi"] == fixture["second_pointer"]
        )
        assert expected["registers"] == dict(
            eax=fixture["userdata"],
            ebx=c.TARGETS["lua_pushstring"],
            ecx=fixture["userdata"],
            edx=0xB1000006 + 0x100 * vector["profile"],
            esi=fixture["state"],
            edi=fixture["second_pointer"],
            ebp=frame,
            esp=frame - 48,
        )
        assert expected["flags"] == (
            4 if (fixture["userdata"] & 255).bit_count() % 2 == 0 else 0
        )
        assert [raw(expected["pages"], frame - 48 + 4 * i) for i in range(3)] == [
            c.BASE + c.END,
            fixture["state"],
            fixture["second_pointer"],
        ]
        assert logical["initializer"]["arguments"] == [
            fixture["state"],
            fixture["second_pointer"],
        ]
        assert logical["initial_lua_stack"] == [("argument", 1)]
        assert logical["final_lua_stack"] == [
            ("argument", 1),
            ("userdata", fixture["userdata"]),
        ]
        assert logical["lua_stack_delta"] == 1


@pytest.mark.parametrize(
    "kind",
    [
        "ancestor",
        "saved_ebp",
        "saved_esi",
        "local_userdata",
        "handoff_pointer",
        "cookie",
        "fs",
        "first_name",
        "second_bytes",
        "userdata",
    ],
)
def test_independent_page_oracle_rejects_forged_expected_memory(cases, kind):
    vector, fixture, expected = next(
        case for case in reversed(cases) if not case[0]["equal_pointers"]
    )
    frame = fixture["entry"] - 4
    address = {
        "ancestor": fixture["entry"] + 8,
        "saved_ebp": frame,
        "saved_esi": frame - 28,
        "local_userdata": frame - 16,
        "handoff_pointer": frame - 40,
        "cookie": c.COOKIE,
        "fs": 0,
        "first_name": fixture["first_pointer"] + vector["length"] + 2,
        "second_bytes": fixture["second_pointer"],
        "userdata": fixture["userdata"],
    }[kind]
    forged = dict(
        expected,
        pages=change(
            expected["pages"], address, raw(expected["pages"], address, 1) ^ 1, 1
        ),
    )
    assert independent_pages(vector, fixture) == expected["pages"] != forged["pages"]


def test_expected_deterministic_and_preserves_inputs(cases):
    vector, fixture, expected = cases[-1]
    before = copy.deepcopy((vector, fixture))
    assert c._expected(vector, fixture) == expected
    assert (vector, fixture) == before


@pytest.mark.parametrize(
    "mutation", ["length", "pattern", "alignment", "profile", "missing", "extra"]
)
def test_out_of_corpus_fixture_rejected(mutation):
    vector = c.vectors()[0]
    if mutation == "length":
        vector["length"] = 256
    elif mutation == "pattern":
        vector["pattern"] = "unknown"
    elif mutation == "alignment":
        vector["name_alignment"] = 8
    elif mutation == "profile":
        vector["profile"] = 2
    elif mutation == "missing":
        del vector["equal_pointers"]
    else:
        vector["unreviewed"] = 0
    with pytest.raises(RuntimeError):
        c._fixture(vector)


@pytest.mark.parametrize(
    "field,value",
    [
        ("length", True),
        ("length", 1.0),
        ("name_alignment", False),
        ("name_alignment", 0.0),
        ("profile", False),
        ("profile", 0.0),
        ("equal_pointers", 0),
        ("equal_pointers", 1),
    ],
)
def test_finite_fixture_rejects_numeric_type_aliases(field, value):
    vector = dict(c.vectors()[0], **{field: value})
    with pytest.raises(RuntimeError):
        c._fixture(vector)


@pytest.mark.parametrize("value", [None, [], (), "factory"])
def test_fixture_requires_dictionary(value):
    with pytest.raises(RuntimeError):
        c._fixture(value)


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (PREFIX + "native_lua_class_factory_prefix_conformance.json")
    if not path.exists() or c.SEALED_SHA256 in ("UNSEALED", "PENDING"):
        pytest.skip("awaiting reviewed native factory prefix seal")
    evidence = json.loads(path.read_text())
    paths, sources = {}, {}
    for key, (kind, digest) in c.SOURCE_PINS.items():
        suffix = "program_facts" if key == "program_facts" else kind.removeprefix("pe_")
        source_path = PROGRAMS / (PREFIX + suffix + ".json")
        sources[key] = json.loads(source_path.read_text())
        assert c._canonical_sha256(sources[key]) == digest
        paths[key] = source_path
    return path, evidence, paths, sources


def test_seal_encoding_exact_normal_coverage_controls_and_stopping_scope(receipts):
    path, evidence, _, sources = receipts
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    for key, value in dict(
        cases=216,
        executed_sites=71,
        instruction_bytes=231,
        native_instructions=56952,
        supplied_api_calls=1512,
        controls=15,
        initializer_instructions=0,
        opaque_native_instructions=0,
        accounting_promotions=0,
    ).items():
        assert evidence["summary"][key] == value
    assert evidence["summary"]["static_sites"] == len(evidence["body"]["points"])
    required = {
        p["rva"]
        for p in evidence["body"]["points"]
        if not any(a <= int(p["rva"], 16) < b for a, b in c.ERROR_RANGES)
    }
    assert set(evidence["executed_rvas"]) == required
    assert f"0x{c.INITIALIZER:08x}" not in required
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    assert set(controls) == {
        "ancestor",
        "name",
        "second_buffer",
        "userdata",
        "iat_padding",
        "cookie",
        "fs_chain",
        "saved_register",
        "local_userdata",
        "handoff_pointer",
        "result",
        "flags",
        "api_argument",
        "second_response",
        "length_response",
    }
    assert len(controls) == len(evidence["negative_controls"]) == 15
    assert all(
        row["rejected"] and row["reason"] == c.CONTROLS[kind]
        for kind, row in controls.items()
    )
    assert evidence["scope"]["continuous_machine"] is True
    assert "lua_pushstring" not in evidence["scope"]["supplied_apis"]
    excluded = " ".join(evidence["scope"]["excluded"])
    assert "Initializer behavior" in excluded and "full factory return" in excluded
    assert (
        "Equality of separately returned string pointers" in excluded
        and "Actual Lua VM" in excluded
    )


@pytest.mark.parametrize("mutation", ["summary", "vectors", "control", "body", "kind"])
def test_modified_receipt_rejected(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    if mutation == "summary":
        changed["summary"]["initializer_instructions"] = 1
    elif mutation == "vectors":
        changed["vectors"][0]["equal_pointers"] = True
    elif mutation == "control":
        changed["negative_controls"][0]["rejected"] = False
    elif mutation == "body":
        changed["body"]["sha256"] = "0" * 64
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ["missing", "extra", "pin", "kind"])
def test_strict_source_preflight_partition_and_identity(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["initializer_chain"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["factory_chain"]["schema_version"] += 1
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
    noncanonical = tmp_path / "factory.json"
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
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == path.read_bytes()
