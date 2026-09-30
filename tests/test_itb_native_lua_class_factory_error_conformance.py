"""Independent rejection-frame laws, ending before lua_error executes."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_factory_error_conformance as c
from src.observatory import native_lua_class_factory_error_semantics as model

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_error_conformance.py"
CANONICAL = "0e454398b0a47423e880932db975c82643358d6781115ced8989bb37a6a15952"
RAW = "e43927841c891c22621ae2821e3e0f01c2d89487cde5aa22d45e23c9b1ec1d45"
SLOTS = dict(
    lua_gettop=0x7D650C,
    lua_type=0x7D64FC,
    lua_isnumber=0x7D6480,
    lua_tolstring=0x7D6500,
    lua_objlen=0x7D64A8,
    lua_pushstring=0x7D6494,
)
TARGETS = dict(
    lua_gettop=0x05000100,
    lua_type=0x05000700,
    lua_isnumber=0x05000200,
    lua_tolstring=0x05000600,
    lua_objlen=0x05000400,
    lua_pushstring=0x05000500,
)


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


def name_for(vector):
    n = vector["length"]
    pattern = {"ascii": b"Class", "low": b"\x01\x02", "high": b"\x80\xff"}[
        vector["pattern"]
    ]
    return (pattern * (n // len(pattern) + 1))[:n] + b"\0opaque\xff\0"


def logical_for(vector, fixture):
    family = vector["family"]
    return model.apply(
        state=fixture["state"],
        argument_count=vector["response"] if family == "count" else 1,
        type_result=vector["response"] if family == "type" else 4,
        number_result=vector["response"] if family == "number" else 0,
        first_pointer=fixture["first_pointer"],
        name_bytes=name_for(vector),
        object_length=vector["response"] if family == "length" else None,
    )


def requests_for(vector, fixture):
    """Independent reached API list; no native expected object is consulted."""
    family, state = vector["family"], fixture["state"]
    rows = [
        (
            "lua_gettop",
            [state],
            vector["response"] if family == "count" else 1,
            0x2EC24C,
            0x6EC252,
        )
    ]
    if family != "count":
        rows.append(
            (
                "lua_type",
                [state, 1],
                vector["response"] if family == "type" else 4,
                0x2EC263,
                0x6EC269,
            )
        )
    if family in ("number", "length"):
        rows.append(
            (
                "lua_isnumber",
                [state, 1],
                vector["response"] if family == "number" else 0,
                0x2EC274,
                0x6EC27A,
            )
        )
    if family == "length":
        rows += [
            (
                "lua_tolstring",
                [state, 1, 0],
                fixture["first_pointer"],
                0x2EC298,
                0x6EC29E,
            ),
            ("lua_objlen", [state, 1], vector["response"], 0x2EC2B2, 0x6EC2B8),
        ]
    literal = 0x83CA88 if family == "length" else 0x83CA60
    rows.append(
        (
            "lua_pushstring",
            [state, literal],
            0,
            0x2EC2C5 if family == "length" else 0x2EC287,
            0x6EC2C7 if family == "length" else 0x6EC289,
        )
    )
    return rows


def independent_pages(vector, fixture):
    """Closed final-cell law: transient API cells are overwritten by error entry."""
    frame, state = fixture["entry"] - 4, fixture["state"]
    before = fixture["pages"]
    cells = {
        frame: fixture["registers"]["ebp"],
        frame - 4: 0xFFFFFFFF,
        frame - 8: 0x7A6111,
        frame - 12: raw(before, 0),
        frame - 24: fixture["registers"]["ebx"],
        frame - 28: fixture["registers"]["esi"],
        frame - 32: fixture["registers"]["edi"],
        frame - 36: raw(before, 0x893F28) ^ frame,
        frame - 40: 0x83CA88 if vector["family"] == "length" else 0x83CA60,
        frame - 44: state,
        frame - 48: state,
        frame - 52: 0x6EC2CE if vector["family"] == "length" else 0x6EC290,
        0: frame - 12,
    }
    result = dict(before)
    for address, value in cells.items():
        result = change(result, address, value)
    return result


def independent_events(vector, fixture):
    """Reached stack writes and explicit operand reads in source order."""
    frame, state = fixture["entry"] - 4, fixture["state"]
    pages, events = fixture["pages"], []

    def read(address, width=4):
        events.append(
            dict(
                access="read",
                address=address,
                width=width,
                value=raw(pages, address, width),
            )
        )

    def write(address, value):
        nonlocal pages
        events.append(dict(access="write", address=address, width=4, value=value))
        pages = change(pages, address, value)

    write(frame, fixture["registers"]["ebp"])
    write(frame - 4, 0xFFFFFFFF)
    write(frame - 8, 0x7A6111)
    read(0)
    write(frame - 12, raw(pages, 0))
    for displacement, register in ((24, "ebx"), (28, "esi"), (32, "edi")):
        write(frame - displacement, fixture["registers"][register])
    read(0x893F28)
    write(frame - 36, raw(pages, 0x893F28) ^ frame)
    write(0, frame - 12)
    read(frame + 8)
    for index, (api, arguments, _, _, continuation) in enumerate(
        requests_for(vector, fixture)
    ):
        if api == "lua_objlen":
            for offset in range(vector["length"] + 1):
                read(fixture["first_pointer"] + offset, 1)
        for i, value in enumerate(reversed(arguments), 1):
            write(frame - 36 - 4 * i, value)
        if api != "lua_pushstring":
            read(SLOTS[api])
        write(frame - 40 - 4 * len(arguments), continuation)
        if index == 0:
            read(SLOTS["lua_pushstring"])
    write(frame - 48, state)
    read(0x7D6498)
    write(frame - 52, 0x6EC2CE if vector["family"] == "length" else 0x6EC290)
    return events


@pytest.fixture(scope="module")
def cases():
    # Every early response/profile; bounded length cases cover every length,
    # pattern and profile, and rotate all mismatching object-length responses.
    selected = []
    for vector in c.vectors():
        if vector["family"] != "length":
            selected.append(vector)
        elif (
            vector["name_alignment"]
            == {"ascii": 0, "low": 7, "high": 4095}[vector["pattern"]]
        ):
            choices = (vector["length"] + 1, vector["length"] + 2, 0xFFFFFFFF)
            index = (
                vector["length"]
                + vector["profile"]
                + ("ascii", "low", "high").index(vector["pattern"])
            ) % 3
            if vector["response"] == choices[index]:
                selected.append(vector)
    result = []
    for vector in selected:
        fixture = c._fixture(vector)
        result.append((vector, fixture, c._expected(vector, fixture)))
    assert len(result) == 56
    return result


def test_exact_finite_corpus_dimensions_and_deterministic_detached_vectors():
    first = c.vectors()
    assert len(first) == 344 and first == c.vectors()
    assert len({tuple(sorted(v.items())) for v in first}) == 344
    assert {
        family: sum(v["family"] == family for v in first)
        for family in ("count", "type", "number", "length")
    } == dict(count=8, type=8, number=4, length=324)
    length = [v for v in first if v["family"] == "length"]
    assert {v["length"] for v in length} == {0, 1, 2, 15, 16, 255}
    assert {v["name_alignment"] for v in length} == {0, 7, 4095}
    assert {v["pattern"] for v in length} == {"ascii", "low", "high"}
    assert all(
        v["response"] in (v["length"] + 1, v["length"] + 2, 0xFFFFFFFF) for v in length
    )
    first[0]["profile"] = 99
    assert c.vectors()[0]["profile"] == 0


def test_fixture_geometry_bindings_literals_and_opaque_second_pointer(cases):
    for vector, fixture, _ in cases:
        profile = vector["profile"]
        assert fixture["entry"] == 0x30001000 + 15 * profile
        assert fixture["state"] == 0x12001000 + 0x100 * profile
        assert fixture["first_pointer"] == 0x13000000 + vector["name_alignment"]
        assert fixture["second_pointer"] == 0x15000000 + 7 * profile
        pages = fixture["pages"]
        assert raw(pages, fixture["entry"]) == 0x0400A000
        assert raw(pages, fixture["entry"] + 4) == fixture["state"]
        assert raw(pages, 0) == (0, 0xF1234567)[profile]
        assert raw(pages, 0x893F28) == (0x12345678, 0xFFFFFFFF)[profile]
        assert raw(pages, 0x7D6498) == 0x05000F00
        assert all(raw(pages, SLOTS[api]) == target for api, target in TARGETS.items())
        assert bytes(
            raw(pages, fixture["first_pointer"] + i, 1)
            for i in range(len(name_for(vector)))
        ) == name_for(vector)
        for pointer, text in (
            (0x83CA60, b"invalid construct, expected class name"),
            (0x83CA88, b"luabind does not support class names with extra nulls"),
        ):
            assert (
                bytes(raw(pages, pointer + i, 1) for i in range(len(text) + 1))
                == text + b"\0"
            )
        assert all(type(page) is bytes and len(page) == 4096 for page in pages.values())


def test_complete_pages_active_fs_saved_frame_and_untouched_ancestors(cases):
    for vector, fixture, expected in cases:
        assert expected["pages"] == independent_pages(vector, fixture)
        frame = fixture["entry"] - 4
        assert raw(expected["pages"], 0) == frame - 12
        assert raw(expected["pages"], frame - 12) == raw(fixture["pages"], 0)
        for displacement in (16, 20):
            assert raw(expected["pages"], frame - displacement) == raw(
                fixture["pages"], frame - displacement
            )
        for page, payload in fixture["pages"].items():
            if (
                page == 0
                or page <= frame < page + 4096
                or page <= frame - 52 < page + 4096
            ):
                continue
            assert expected["pages"][page] == payload
        assert bytes(
            raw(expected["pages"], fixture["entry"] + i, 1) for i in range(64)
        ) == bytes(raw(fixture["pages"], fixture["entry"] + i, 1) for i in range(64))


def test_ordered_events_first_nul_and_no_allocator_or_initializer(cases):
    for vector, fixture, expected in cases:
        assert expected["events"] == independent_events(vector, fixture)
        byte_reads = [
            e for e in expected["events"] if e["access"] == "read" and e["width"] == 1
        ]
        assert len(byte_reads) == (
            vector["length"] + 1 if vector["family"] == "length" else 0
        )
        if byte_reads:
            assert [e["address"] for e in byte_reads] == list(
                range(
                    fixture["first_pointer"],
                    fixture["first_pointer"] + vector["length"] + 1,
                )
            )
            assert byte_reads[-1]["value"] == 0 and all(
                e["value"] for e in byte_reads[:-1]
            )
        assert not any(
            e["address"] == fixture["second_pointer"] for e in expected["events"]
        )
        assert not any(e["address"] == fixture["userdata"] for e in expected["events"])
        assert "lua_newuserdata" not in [call["api"] for call in expected["calls"]]


def test_physical_api_short_circuit_frames_and_retained_error_arguments(cases):
    for vector, fixture, expected in cases:
        frame = fixture["entry"] - 4
        rows = requests_for(vector, fixture)
        assert [
            (
                call["api"],
                call["arguments"],
                call["response"]["eax"],
                int(call["site_rva"], 16),
                call["continuation"],
            )
            for call in expected["calls"]
        ] == rows
        for index, (call, row) in enumerate(zip(expected["calls"], rows)):
            api, args, value, _, _ = row
            assert call["target"] == TARGETS[api]
            assert call["entry_esp"] == frame - 40 - 4 * len(args)
            regs = call["entry_registers"]
            assert regs["esp"] == call["entry_esp"] and regs["ebp"] == frame
            assert regs["esi"] == fixture["state"]
            assert regs["ebx"] == (
                fixture["registers"]["ebx"] if index == 0 else 0x05000500
            )
            assert regs["edi"] == (
                vector["length"]
                if api in ("lua_objlen", "lua_pushstring")
                and vector["family"] == "length"
                else fixture["registers"]["edi"]
            )
            if index == 0:
                assert regs["eax"] == frame - 12
                assert regs["ecx"] == fixture["registers"]["ecx"]
                assert regs["edx"] == fixture["registers"]["edx"]
            else:
                ecx = 0xA1000000 + 0x100 * vector["profile"] + index - 1
                assert regs["edx"] == 0xB1000000 + 0x100 * vector["profile"] + index - 1
                assert regs["ecx"] == (ecx & 0xFFFFFF00 if api == "lua_objlen" else ecx)
                assert regs["eax"] == (
                    fixture["first_pointer"] + 1
                    if api == "lua_objlen"
                    else rows[index - 1][2]
                )
            assert call["response"] == dict(
                eax=value,
                ecx=0xA1000000 + 0x100 * vector["profile"] + index,
                edx=0xB1000000 + 0x100 * vector["profile"] + index,
                eflags=0x202 | ((index * 0x95) & 0x8D5),
            )
        error = expected["error_request"]
        assert error["target"] == 0x05000F00 and error["arguments"] == [
            fixture["state"]
        ]
        assert error["entry_esp"] == frame - 52
        assert error["retained_stack_words"] == [
            raw(expected["pages"], frame - 52 + 4 * i) for i in range(4)
        ]
        assert (
            error["retained_stack_words"]
            == logical_for(vector, fixture)["frame"]["error_stack_words"]
        )
        assert error["entry_registers"] == expected["registers"]


def test_final_gprs_defined_flags_and_unrestored_active_frame(cases):
    for vector, fixture, expected in cases:
        index = {"count": 1, "type": 2, "number": 3, "length": 5}[vector["family"]]
        frame = fixture["entry"] - 4
        wanted = dict(
            fixture["registers"],
            eax=0,
            ebx=0x05000500,
            ecx=0xA1000000 + 0x100 * vector["profile"] + index,
            edx=0xB1000000 + 0x100 * vector["profile"] + index,
            esi=fixture["state"],
            ebp=frame,
            esp=frame - 52,
        )
        if vector["family"] == "length":
            wanted["edi"] = vector["length"]
        assert expected["registers"] == wanted
        assert expected["flags"] == (0x202 | ((index * 0x95) & 0x8D5)) & 0xCD5
        assert expected["error_request"]["continuation"] == (
            0x6EC2CE if vector["family"] == "length" else 0x6EC290
        )


def test_independent_lua_controller_replays_complete_model_and_terminal_no_result(
    cases,
):
    for vector, fixture, expected in cases:
        logical = logical_for(vector, fixture)
        observer = c._Lua(vector, fixture)
        for call in logical["calls"]:
            assert observer.apply(call["api"], call["arguments"]) == call["result"]
        assert (
            normalized(observer.calls)
            == normalized(logical["calls"])
            == expected["logical"]["calls"]
        )
        assert normalized(observer.stack) == normalized(
            logical["error_entry_lua_stack"]
        )
        assert (
            logical["calls"][-1]["api"] == "lua_error"
            and logical["calls"][-1]["result"] is None
        )
        assert logical["lua_stack_delta"] == 1
        assert (
            logical["reason"]
            == {
                "count": "argument_count",
                "type": "type",
                "number": "numeric",
                "length": "name_length",
            }[vector["family"]]
        )
        assert logical["byte_reads"] == (
            vector["length"] + 1 if vector["family"] == "length" else 0
        )
        assert logical["argument_prefix_is_compact"] == (
            vector["family"] == "count" and vector["response"] > 3
        )


@pytest.mark.parametrize("mutation", ["state", "index", "literal", "identity"])
def test_runtime_observer_wrong_request_or_message_identity_rejected(cases, mutation):
    vector, fixture, _ = next(row for row in cases if row[0]["family"] == "length")
    observer = c._Lua(vector, fixture)
    logical = logical_for(vector, fixture)
    if mutation == "state":
        api, args = "lua_gettop", [fixture["state"] ^ 1]
    elif mutation == "index":
        api, args = "lua_type", [fixture["state"], 2]
    elif mutation == "literal":
        api, args = "lua_pushstring", [fixture["state"], 0x83CA60]
    else:
        for call in logical["calls"][:-1]:
            observer.apply(call["api"], call["arguments"])
        observer.stack[-1] = ("message", "invalid_construct")
        api, args = "lua_error", [fixture["state"]]
    with pytest.raises(RuntimeError, match="factory error Lua"):
        observer.apply(api, args)


def test_expected_deterministic_inputs_immutable_and_results_detached(cases):
    for vector, fixture, expected in cases[::7]:
        original = copy.deepcopy((vector, fixture))
        second = c._expected(vector, fixture)
        assert second == expected and (vector, fixture) == original
        second["registers"]["eax"] = 99
        second["error_request"]["retained_stack_words"][0] ^= 1
        second["logical"]["calls"].clear()
        assert (
            c._expected(vector, fixture) == expected and (vector, fixture) == original
        )


def test_early_rejections_leave_later_name_and_userdata_contracts_opaque(cases):
    for family in ("count", "type", "number"):
        vector, fixture, expected = next(
            row for row in cases if row[0]["family"] == family
        )
        changed = copy.deepcopy(fixture)
        changed["pages"] = change(
            changed["pages"], fixture["first_pointer"], 0xDEADBEEF
        )
        changed["pages"] = change(
            changed["pages"], fixture["second_pointer"], 0x12345678
        )
        changed["pages"] = change(changed["pages"], fixture["userdata"], 0x87654321)
        alternative = c._expected(vector, changed)
        for field in (
            "registers",
            "flags",
            "events",
            "calls",
            "error_request",
            "logical",
            "trace_rvas",
        ):
            assert alternative[field] == expected[field]
        assert alternative["pages"] == independent_pages(vector, changed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("response", True),
        ("response", 0.0),
        ("response", -1),
        ("response", 0x100000000),
        ("profile", False),
        ("profile", 2),
        ("length", False),
        ("length", 256),
        ("name_alignment", False),
        ("name_alignment", 8),
        ("family", "other"),
        ("pattern", None),
    ],
)
def test_strict_finite_fixture_field_types_and_domain(field, value):
    vector = dict(c.vectors()[0], **{field: value})
    with pytest.raises(RuntimeError):
        c._fixture(vector)


@pytest.mark.parametrize("shape", ["missing", "extra", "list", "none"])
def test_strict_fixture_dictionary_schema(shape):
    vector = c.vectors()[0]
    if shape == "missing":
        del vector["response"]
    elif shape == "extra":
        vector["unreviewed"] = 0
    elif shape == "list":
        vector = list(vector.items())
    else:
        vector = None
    with pytest.raises(RuntimeError):
        c._fixture(vector)


@pytest.mark.parametrize(
    "cell",
    [
        "ancestor",
        "cookie",
        "fs",
        "saved",
        "scope",
        "return",
        "retained",
        "name",
        "literal",
        "userdata",
    ],
)
def test_forged_pages_and_consistently_forged_boundary_fail_independent_page_law(
    cases, cell
):
    vector, fixture, expected = next(
        row for row in cases if row[0]["family"] == "length" and row[0]["length"] == 16
    )
    frame = fixture["entry"] - 4
    address = dict(
        ancestor=fixture["entry"] + 8,
        cookie=0x893F28,
        fs=0,
        saved=frame - 28,
        scope=frame - 4,
        return_=frame - 52,
        retained=frame - 40,
        name=fixture["first_pointer"] + 17,
        literal=0x83CA88,
        userdata=fixture["userdata"],
    )["return_" if cell == "return" else cell]
    forged = copy.deepcopy(expected)
    forged["pages"] = change(
        forged["pages"], address, raw(forged["pages"], address) ^ 1
    )
    if cell in ("return", "retained"):
        i = 0 if cell == "return" else 3
        forged["error_request"]["retained_stack_words"][i] ^= 1
        forged["logical"]["frame"]["error_stack_words"][i] ^= 1
    assert forged["pages"] != independent_pages(vector, fixture)
    assert expected["pages"] == independent_pages(vector, fixture)


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (PREFIX + "native_lua_class_factory_error_conformance.json")
    evidence = json.loads(path.read_text())
    paths, sources = {}, {}
    for key, (kind, digest) in c.SOURCE_PINS.items():
        suffix = "program_facts" if key == "program_facts" else kind.removeprefix("pe_")
        source_path = PROGRAMS / (PREFIX + suffix + ".json")
        sources[key] = json.loads(source_path.read_text())
        assert c._canonical_sha256(sources[key]) == digest
        paths[key] = source_path
    return path, evidence, paths, sources


def test_receipt_seal_static_path_partition_all_fifteen_controls_and_conditional_scope(
    receipts,
):
    path, evidence, _, sources = receipts
    assert set(c.SOURCE_PINS) == {"program_facts", "factory_chain"}
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert evidence["summary"] == dict(
        cases=344,
        static_sites=63,
        executed_sites=62,
        instruction_bytes=174,
        native_instructions=81528,
        supplied_api_calls=2000,
        error_boundaries=344,
        controls=15,
        families=dict(count=8, type=8, number=4, length=324),
        opaque_native_instructions=0,
        accounting_promotions=0,
    )
    body = evidence["body"]
    assert body["start_rva"] == "0x002ec220" and body["end_rva"] == "0x002ec2ce"
    points = {p["rva"] for p in body["points"]}
    union = set(evidence["executed_rvas"])
    assert points - union == {"0x002ec290"} and union <= points
    assert "0x002ec2ce" not in points and "0x002ead94" not in union
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    wanted = {
        "ancestor",
        "name",
        "literal",
        "iat_padding",
        "cookie",
        "fs_chain",
        "saved_register",
        "error_return",
        "retained_literal",
        "result",
        "flags",
        "api_argument",
        "push_response",
        "error_argument",
        "lua_identity",
    }
    assert (
        set(controls) == wanted == set(c.CONTROLS)
        and len(evidence["negative_controls"]) == 15
    )
    assert all(
        row["rejected"] and row["reason"] == c.CONTROLS[kind]
        for kind, row in controls.items()
    )
    excluded = " ".join(evidence["scope"]["excluded"])
    assert (
        "Execution or return of lua_error" in excluded
        and "exception unwinding" in excluded
    )
    assert (
        "allocation and initializer execution" in excluded
        and "accounting promotion" in excluded
    )


def test_independent_native_path_lengths_and_union_cover_the_entire_finite_domain(
    receipts,
):
    _, evidence, _, _ = receipts
    traces = [c._trace(v) for v in c.vectors()]
    for vector, trace in zip(c.vectors(), traces):
        assert (
            len(trace)
            == {
                "count": 27,
                "type": 33,
                "number": 39,
                "length": 57 + 4 * vector["length"],
            }[vector["family"]]
        )
        assert trace[0] == "0x002ec220"
        assert trace[-1] == (
            "0x002ec2c8" if vector["family"] == "length" else "0x002ec28a"
        )
        assert "0x002ec290" not in trace
        for pc in ("0x002ec2a6", "0x002ec2a8", "0x002ec2a9", "0x002ec2ab"):
            assert trace.count(pc) == (
                vector["length"] + 1 if vector["family"] == "length" else 0
            )
        if vector["family"] != "length":
            assert "0x002ec298" not in trace and "0x002ec2b2" not in trace
        if vector["family"] == "count":
            assert "0x002ec263" not in trace
        if vector["family"] in ("count", "type"):
            assert "0x002ec274" not in trace
    assert sum(map(len, traces)) == 81528
    assert sorted({pc for trace in traces for pc in trace}) == evidence["executed_rvas"]


def test_pe_free_static_extent_and_nonreturning_error_call_witnesses(receipts):
    _, evidence, _, _ = receipts
    rows = evidence["body"]["points"]
    assert len(rows) == 63 and sum(p["size"] for p in rows) == 174
    assert all(
        int(left["rva"], 16) + left["size"] == int(right["rva"], 16)
        for left, right in zip(rows, rows[1:])
    )
    assert int(rows[-1]["rva"], 16) + rows[-1]["size"] == 0x2EC2CE
    by_rva = {p["rva"]: p for p in rows}
    witnesses = {
        "0x002ec220": b"\x55",
        "0x002ec223": b"\x6a\xff",
        "0x002ec28a": bytes.fromhex("ff1598647d00"),
        "0x002ec2c8": bytes.fromhex("ff1598647d00"),
    }
    for rva, payload in witnesses.items():
        assert by_rva[rva]["size"] == len(payload)
        assert by_rva[rva]["sha256"] == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize(
    "mutation", ["summary", "vector", "control", "body", "kind", "observations"]
)
def test_modified_receipt_rejected(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    if mutation == "summary":
        changed["summary"]["error_boundaries"] -= 1
    elif mutation == "vector":
        changed["vectors"][0]["response"] = 1
    elif mutation == "control":
        changed["negative_controls"][0]["rejected"] = False
    elif mutation == "body":
        changed["body"]["sha256"] = "0" * 64
    elif mutation == "observations":
        changed["observations_sha256"] = "0" * 64
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ["missing", "extra", "pin", "kind"])
def test_strict_source_partition_and_pin_preflight(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["factory_chain"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["factory_chain"]["schema_version"] += 1
    else:
        changed["program_facts"]["analysis_kind"] = "pe_other"
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
    noncanonical = tmp_path / "error.json"
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
        timeout=600,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == path.read_bytes()
