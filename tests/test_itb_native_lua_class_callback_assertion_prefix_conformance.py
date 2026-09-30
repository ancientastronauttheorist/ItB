"""Independent native callback failures stopped before assertion-helper execution."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_callback_assertion_prefix_conformance as c
from src.observatory import (
    native_lua_class_callback_assertion_prefix_semantics as model,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_callback_assertion_prefix_conformance.py"
CANONICAL = "b6486105640001ae644f9ea2023c98ca62626df5f1ab2c2041ba2dea2879484e"
RAW = "566da6057527a877f2441b7b29075a4742cc32c1bb65e6952f3e50c1ae0eb861"
SLOTS = dict(
    lua_getmetatable=0x7D6534,
    lua_gettable=0x7D64BC,
    lua_pushstring=0x7D6494,
    lua_settop=0x7D6510,
    lua_toboolean=0x7D64F8,
    lua_touserdata=0x7D649C,
)
TARGETS = dict(
    lua_getmetatable=0x05000200,
    lua_gettable=0x05000300,
    lua_pushstring=0x05000700,
    lua_settop=0x05000B00,
    lua_toboolean=0x05000C00,
    lua_touserdata=0x05000D00,
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


def boundary_for(vector):
    null = vector["family"] == "null"
    return dict(
        target=0x779CC2,
        arguments=[0x83CA00 if null else 0x83C908, 0x83C9C8, 69 if null else 70],
        continuation=0x6EC151 if null else 0x6EC175,
    )


def logical_for(vector, fixture):
    return model.apply(
        state=fixture["state"],
        userdata=fixture["userdata"],
        has_metatable=vector["family"] != "absent",
        value_kind="false" if vector["family"] == "false" else "nil",
    )


def marker_vector_for(vector):
    return dict(
        alignment=vector["alignment"],
        prefix_length=1,
        has_metatable=vector["family"] != "absent",
        value_kind="false" if vector["family"] == "false" else "nil",
        final_void_eax=(0, 0x12345678, 0xFFFFFFFF)[vector["profile"]],
    )


def independent_pages(vector, fixture):
    """Closed final cells, with only reached native marker scratch retained."""
    frame = fixture["entry"] - 4
    boundary = boundary_for(vector)
    cells = {
        frame: fixture["registers"]["ebp"],
        frame - 8: raw(fixture["pages"], 0x893F28) ^ frame,
        frame - 20: fixture["userdata"],
        frame - 28: fixture["registers"]["ebx"],
        frame - 32: fixture["registers"]["esi"],
        frame - 36: fixture["registers"]["edi"],
        frame - 40: boundary["arguments"][2],
        frame - 44: boundary["arguments"][1],
        frame - 48: boundary["arguments"][0],
        frame - 52: boundary["continuation"],
    }
    if vector["family"] != "null":
        cells[frame - 56] = 0x6EB56B if vector["family"] == "absent" else 0x6EB5AD
    if vector["family"] in ("nil", "false"):
        cells.update(
            {
                frame - 60: fixture["state"],
                frame - 64: 0xFFFFFFFF,
                frame - 68: fixture["state"],
                frame - 72: 0x6EB590,
            }
        )
    result = dict(fixture["pages"])
    for address, value in cells.items():
        result = change(result, address, value)
    return result


def independent_composition(vector, fixture):
    """Handwritten parent/child operand events and exact reached import frames.

    Marker page composition uses the separate closed stack corollary, with
    child entry pages reconstructed from the running parent rather than copied
    from the conformance expected object.
    """
    frame, state = fixture["entry"] - 4, fixture["state"]
    pages, events, calls = fixture["pages"], [], []

    def read(address):
        events.append(
            dict(access="read", address=address, width=4, value=raw(pages, address))
        )

    def write(address, value):
        nonlocal pages
        events.append(dict(access="write", address=address, width=4, value=value))
        pages = change(pages, address, value)

    original = fixture["registers"]
    write(frame, original["ebp"])
    read(0x893F28)
    cookie = raw(pages, 0x893F28) ^ frame
    write(frame - 8, cookie)
    write(frame - 28, original["ebx"])
    read(frame + 8)
    write(frame - 32, original["esi"])
    write(frame - 36, original["edi"])
    read(SLOTS["lua_touserdata"])
    write(frame - 40, 0xFFFFD8ED)
    write(frame - 44, state)
    write(frame - 48, 0x6EC134)
    response = dict(
        eax=fixture["userdata"],
        ecx=0xA1000001 + 0x100 * vector["profile"],
        edx=0xB1000001 + 0x100 * vector["profile"],
        eflags=0x297,
    )
    calls.append(
        dict(
            api="lua_touserdata",
            site_rva="0x002ec132",
            target=0x05000D00,
            arguments=[state, 0xFFFFD8ED],
            continuation=0x6EC134,
            entry_esp=frame - 48,
            entry_registers=dict(
                original,
                eax=cookie,
                ebx=state,
                edi=0x05000D00,
                ebp=frame,
                esp=frame - 48,
            ),
            response=response,
            group="direct",
        )
    )
    write(frame - 20, fixture["userdata"])
    regs = dict(
        original,
        eax=fixture["userdata"],
        ebx=state,
        ecx=response["ecx"],
        edx=response["edx"],
        esi=fixture["userdata"],
        edi=0x05000D00,
        ebp=frame,
        esp=frame - 36,
    )
    child = None
    if vector["family"] != "null":
        mv = marker_vector_for(vector)
        entry = frame - 40
        write(entry, 0x6EC160)
        regs.update(ecx=state, edx=0xFFFFD8ED, esp=entry)
        incoming = dict(regs)
        child_fixture = dict(
            entry=entry, endpoint=0x6EC160, registers=incoming, pages=dict(pages)
        )
        corollary = c.marker._stack_model(mv, child_fixture)
        write(entry - 4, incoming["esi"])
        write(entry - 8, incoming["edx"])
        write(entry - 12, state)
        regs["esi"] = state
        api_rows = [("lua_getmetatable", 0xFFFFD8ED, -16, 0x2EB565, 0x6EB56B)]
        if mv["has_metatable"]:
            api_rows += [
                ("lua_pushstring", 0x83C738, -16, 0x2EB578, 0x6EB57E),
                ("lua_gettable", 0xFFFFFFFE, -24, 0x2EB581, 0x6EB587),
                ("lua_toboolean", 0xFFFFFFFF, -32, 0x2EB58A, 0x6EB590),
                ("lua_settop", 0xFFFFFFFD, -16, 0x2EB5A7, 0x6EB5AD),
            ]
        for index, (api, argument, displacement, site, after) in enumerate(api_rows, 1):
            if index != 1:
                write(entry + displacement + 8, argument)
                write(entry + displacement + 4, state)
            read(SLOTS[api])
            write(entry + displacement, after)
            eax = (0x91A2B300 + 17 * index + vector["alignment"]) & 0xFFFFFFFF
            if api == "lua_getmetatable":
                eax = int(mv["has_metatable"])
            elif api == "lua_toboolean":
                eax = 0
            elif api == "lua_settop":
                eax = mv["final_void_eax"]
            response = dict(
                eax=eax,
                ecx=0xA0000000 + 256 * vector["alignment"] + index,
                edx=0xB0000100 + index,
                eflags=0x202 | ((index * 0x95) & 0x8D5),
            )
            calls.append(
                dict(
                    api=api,
                    site_rva=f"0x{site:08x}",
                    target=TARGETS[api],
                    arguments=[state, argument],
                    continuation=after,
                    entry_esp=entry + displacement,
                    entry_registers=dict(regs, esp=entry + displacement),
                    response=response,
                    group="upvalue_marker",
                )
            )
            regs.update({r: response[r] for r in ("eax", "ecx", "edx")})
        read(entry - 4)
        read(entry)
        regs.update(
            esi=incoming["esi"],
            esp=entry + 4,
            eax=mv["final_void_eax"] & 0xFFFFFF00 if mv["has_metatable"] else 0,
        )
        assert pages == corollary
        child = dict(
            vector=mv, fixture=child_fixture, pages=corollary, registers=dict(regs)
        )
    boundary = boundary_for(vector)
    for displacement, value in zip((40, 44, 48), reversed(boundary["arguments"])):
        write(frame - displacement, value)
    write(frame - 52, boundary["continuation"])
    regs["esp"] = frame - 52
    return dict(pages=pages, events=events, calls=calls, child=child, registers=regs)


@pytest.fixture(scope="module")
def cases():
    families = ("null", "absent", "nil", "false")
    selected = [
        v
        for v in c.vectors()
        if v["alignment"] == families.index(v["family"]) * 4 + v["profile"]
    ]
    selected += [
        v
        for v in c.vectors()
        if v["alignment"] in (3, 7, 11, 15)
        and v["profile"] == v["alignment"] % 3
        and v["family"] == families[v["alignment"] // 4]
    ]
    assert len(selected) == 16 and {v["alignment"] for v in selected} == set(range(16))
    return [(v, f, c._expected(v, f)) for v in selected for f in [c._fixture(v)]]


def test_finite_corpus_all_four_families_geometry_and_detached_determinism():
    vectors = c.vectors()
    assert (
        len(vectors) == 192 and len({tuple(sorted(v.items())) for v in vectors}) == 192
    )
    assert {v["alignment"] for v in vectors} == set(range(16))
    assert {v["profile"] for v in vectors} == {0, 1, 2}
    assert {v["family"] for v in vectors} == {"null", "absent", "nil", "false"}
    assert all(
        sum(v["family"] == family for v in vectors) == 48
        for family in ("null", "absent", "nil", "false")
    )
    assert vectors == c.vectors()
    vectors[0]["family"] = "other"
    assert c.vectors()[0]["family"] == "null"


def test_fixture_geometry_userdata_response_cookie_shared_imports_and_no_fs(cases):
    for vector, fixture, expected in cases:
        assert fixture["entry"] == 0x30001000 + vector["alignment"]
        assert fixture["state"] == 0x12001000 + 0x100 * vector["profile"]
        assert fixture["userdata"] == (
            0 if vector["family"] == "null" else 0x11000FFF + 7 * vector["profile"]
        )
        assert raw(fixture["pages"], fixture["entry"]) == 0x0400A000
        assert raw(fixture["pages"], fixture["entry"] + 4) == fixture["state"]
        assert (
            raw(fixture["pages"], 0x893F28)
            == (0, 0x12345678, 0xFFFFFFFF)[vector["profile"]]
        )
        assert all(
            raw(fixture["pages"], SLOTS[api]) == target
            for api, target in TARGETS.items()
        )
        assert 0 not in fixture["pages"] and not any(
            e["address"] == 0 for e in expected["events"]
        )
        assert 0x779000 not in fixture["pages"]
        assert all(
            type(payload) is bytes and len(payload) == 4096
            for payload in fixture["pages"].values()
        )


def test_complete_final_pages_ordered_events_and_current_child_page_corollary(cases):
    for vector, fixture, expected in cases:
        independent = independent_composition(vector, fixture)
        assert (
            expected["pages"]
            == independent["pages"]
            == independent_pages(vector, fixture)
        )
        assert expected["events"] == independent["events"]
        assert expected["registers"] == independent["registers"]
        if vector["family"] == "null":
            assert expected["children"] == [] and independent["child"] is None
        else:
            assert len(expected["children"]) == 1
            actual, oracle = expected["children"][0], independent["child"]
            assert actual["fixture"]["pages"] == oracle["fixture"]["pages"]
            assert actual["fixture"]["registers"] == oracle["fixture"]["registers"]
            assert actual["result"]["pages"] == oracle["pages"]
            assert actual["result"]["registers"] == oracle["registers"]


def test_all_incoming_import_gprs_physical_frames_and_supplied_response_words(cases):
    for vector, fixture, expected in cases:
        independent = independent_composition(vector, fixture)
        assert (
            len(expected["calls"])
            == {"null": 1, "absent": 2, "nil": 6, "false": 6}[vector["family"]]
        )
        assert expected["calls"][0]["entry_esp"] == fixture["entry"] - 52
        for actual, oracle in zip(expected["calls"], independent["calls"]):
            for field in (
                "api",
                "site_rva",
                "target",
                "arguments",
                "continuation",
                "entry_esp",
                "entry_registers",
                "response",
                "group",
            ):
                assert actual[field] == oracle[field]


def test_native_marker_ret_full_eax_false_al_and_parent_nonvolatile_restoration(cases):
    for vector, fixture, expected in cases:
        if vector["family"] == "null":
            continue
        child = expected["children"][0]
        mv = marker_vector_for(vector)
        frame = fixture["entry"] - 4
        assert child["vector"] == c._marker_vector(vector) == mv
        assert child["fixture"]["entry"] == frame - 40
        assert child["fixture"]["endpoint"] == child["result"]["endpoint"] == 0x6EC160
        assert child["fixture"]["registers"]["ecx"] == fixture["state"]
        assert child["fixture"]["registers"]["edx"] == 0xFFFFD8ED
        assert child["result"]["registers"]["esp"] == frame - 36
        eax = mv["final_void_eax"] & 0xFFFFFF00 if mv["has_metatable"] else 0
        assert child["result"]["registers"]["eax"] == eax and eax & 255 == 0
        assert (
            child["result"]["flags"] == 0x44 and child["result"]["flag_mask"] == 0x8C5
        )
        for register in ("ebx", "esi", "edi", "ebp"):
            assert (
                child["result"]["registers"][register]
                == child["fixture"]["registers"][register]
            )


def test_exact_assertion_boundary_three_arguments_continuations_gprs_and_test_flags(
    cases,
):
    for vector, fixture, expected in cases:
        frame = fixture["entry"] - 4
        null, absent = vector["family"] == "null", vector["family"] == "absent"
        eax = (
            0
            if null or absent
            else (0, 0x12345678, 0xFFFFFFFF)[vector["profile"]] & 0xFFFFFF00
        )
        ecx = (
            0xA1000001 + 0x100 * vector["profile"]
            if null
            else 0xA0000000 + 256 * vector["alignment"] + (1 if absent else 5)
        )
        edx = (
            0xB1000001 + 0x100 * vector["profile"]
            if null
            else 0xB0000100 + (1 if absent else 5)
        )
        assert expected["registers"] == dict(
            fixture["registers"],
            eax=eax,
            ecx=ecx,
            edx=edx,
            ebx=fixture["state"],
            esi=fixture["userdata"],
            edi=0x05000D00,
            ebp=frame,
            esp=frame - 52,
        )
        assert expected["flags"] == 0x44 and expected["flags"] & 0x400 == 0
        wanted = boundary_for(vector)
        assert expected["boundary_request"] == dict(
            wanted,
            entry_esp=frame - 52,
            entry_registers=expected["registers"],
            retained_stack_words=[wanted["continuation"], *wanted["arguments"]],
        )
        assert [raw(expected["pages"], frame - 52 + 4 * i) for i in range(4)] == [
            wanted["continuation"],
            *wanted["arguments"],
        ]
        assert (
            expected["logical"]["frame"]["stack_words"]
            == expected["boundary_request"]["retained_stack_words"]
        )


def test_local_userdata_cookie_saved_words_ancestors_and_nonstack_pages_preserved(
    cases,
):
    for vector, fixture, expected in cases:
        frame = fixture["entry"] - 4
        assert (
            raw(expected["pages"], frame - 8) == raw(fixture["pages"], 0x893F28) ^ frame
        )
        assert raw(expected["pages"], frame - 20) == fixture["userdata"]
        for displacement, register in ((28, "ebx"), (32, "esi"), (36, "edi")):
            assert (
                raw(expected["pages"], frame - displacement)
                == fixture["registers"][register]
            )
        for offset in (4, 12, 16, 24):
            assert raw(expected["pages"], frame - offset) == raw(
                fixture["pages"], frame - offset
            )
        assert bytes(
            raw(expected["pages"], fixture["entry"] + i, 1) for i in range(64)
        ) == bytes(raw(fixture["pages"], fixture["entry"] + i, 1) for i in range(64))
        assert all(
            expected["pages"][p] == payload
            for p, payload in fixture["pages"].items()
            if p not in (0x30000000, 0x30001000)
        )


def test_runtime_lua_controller_replay_short_circuit_and_restored_prefix_without_error_call(
    cases,
):
    for vector, fixture, expected in cases:
        logical = logical_for(vector, fixture)
        assert expected["logical"] == normalized(logical)
        observer = c._Lua(vector, fixture)
        for call in logical["calls"]:
            assert (
                observer.apply(
                    call["api"], [word & 0xFFFFFFFF for word in call["arguments"]]
                )
                == call["result"]
            )
        assert normalized(observer.calls) == normalized(logical["calls"])
        assert (
            observer.stack
            == logical["initial_lua_stack"]
            == logical["final_lua_stack"]
            == [("argument", 1)]
        )
        assert logical["lua_stack_delta"] == 0
        assert not any(
            call["api"] in ("lua_error", "lua_newuserdata") for call in logical["calls"]
        )
        assert logical["marker_al"] == (None if vector["family"] == "null" else 0)
        assert logical["reason"] == (
            "null_upvalue" if vector["family"] == "null" else "false_upvalue_marker"
        )
        if vector["family"] == "null":
            assert [call["api"] for call in logical["calls"]] == ["lua_touserdata"]


@pytest.mark.parametrize(
    "mutation",
    [
        "state",
        "upvalue_index",
        "repeated_marker",
        "lookup_index",
        "marker_key_identity",
        "marker_value_identity",
    ],
)
def test_runtime_observer_wrong_request_and_marker_identity_rejected(cases, mutation):
    vector, fixture, _ = next(row for row in cases if row[0]["family"] == "false")
    observer, state = c._Lua(vector, fixture), fixture["state"]
    logical = logical_for(vector, fixture)
    if mutation == "state":
        api, args = "lua_touserdata", [state ^ 1, 0xFFFFD8ED]
    elif mutation == "upvalue_index":
        api, args = "lua_getmetatable", [state, 1]
    else:
        stop = (
            2
            if mutation == "repeated_marker"
            else 3 if mutation in ("lookup_index", "marker_key_identity") else 4
        )
        for call in logical["calls"][:stop]:
            observer.apply(
                call["api"], [word & 0xFFFFFFFF for word in call["arguments"]]
            )
        if mutation == "repeated_marker":
            api, args = "lua_getmetatable", [state, 0xFFFFD8ED]
        elif mutation == "lookup_index":
            api, args = "lua_gettable", [state, 0xFFFFFFFF]
        elif mutation == "marker_key_identity":
            observer.stack[-1] = ("literal", "wrong")
            api, args = "lua_gettable", [state, 0xFFFFFFFE]
        else:
            observer.stack[-1] = ("marker_value", "upvalue", "zero")
            api, args = "lua_toboolean", [state, 0xFFFFFFFF]
    with pytest.raises(RuntimeError, match="callback (assertion prefix )?(error )?Lua"):
        observer.apply(api, args)


def test_boundary_pointer_contents_are_opaque_protected_input_pages(cases):
    for family in ("null", "absent", "nil", "false"):
        vector, fixture, expected = next(
            row for row in cases if row[0]["family"] == family
        )
        altered = copy.deepcopy(fixture)
        boundary = boundary_for(vector)
        for pointer in boundary["arguments"][:2]:
            altered["pages"] = change(altered["pages"], pointer, 0xFEEDFACE)
        alternative = c._expected(vector, altered)
        for field in (
            "registers",
            "flags",
            "events",
            "calls",
            "logical",
            "boundary_request",
            "trace_rvas",
        ):
            assert alternative[field] == expected[field]
        assert alternative["pages"] == independent_pages(vector, altered)
        assert not any(
            e["address"] in boundary["arguments"][:2] for e in alternative["events"]
        )


def test_expected_inputs_immutable_deterministic_and_outputs_detached(cases):
    for vector, fixture, expected in cases[::3]:
        original = copy.deepcopy((vector, fixture))
        second = c._expected(vector, fixture)
        assert second == expected and (vector, fixture) == original
        second["registers"]["eax"] = 99
        second["boundary_request"]["retained_stack_words"][0] ^= 1
        second["logical"]["calls"].clear()
        assert (
            c._expected(vector, fixture) == expected and (vector, fixture) == original
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("alignment", False),
        ("alignment", 0.0),
        ("alignment", -1),
        ("alignment", 16),
        ("profile", False),
        ("profile", 0.0),
        ("profile", -1),
        ("profile", 3),
        ("family", "zero"),
        ("family", "table"),
        ("family", None),
        ("family", False),
    ],
)
def test_strict_finite_vector_types_and_domain(field, value):
    with pytest.raises(RuntimeError):
        c._fixture(dict(c.vectors()[0], **{field: value}))


@pytest.mark.parametrize("shape", ["missing", "extra", "list", "none"])
def test_strict_fixture_dictionary_schema(shape):
    vector = c.vectors()[0]
    if shape == "missing":
        del vector["family"]
    elif shape == "extra":
        vector["unreviewed"] = 1
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
        "saved_ebp",
        "saved_esi",
        "local_userdata",
        "expression",
        "filename",
        "boundary_return",
        "boundary_argument",
        "child_scratch",
        "userdata",
    ],
)
def test_joined_boundary_and_logical_page_forgeries_fail_independent_cell_law(
    cases, cell
):
    vector, fixture, expected = next(
        row for row in cases if row[0]["family"] == "false"
    )
    frame = fixture["entry"] - 4
    address = dict(
        ancestor=fixture["entry"] + 8,
        cookie=0x893F28,
        saved_ebp=frame,
        saved_esi=frame - 32,
        local_userdata=frame - 20,
        expression=0x83C908,
        filename=0x83C9C8,
        boundary_return=frame - 52,
        boundary_argument=frame - 48,
        child_scratch=frame - 72,
        userdata=fixture["userdata"],
    )[cell]
    forged = copy.deepcopy(expected)
    forged["pages"] = change(
        forged["pages"], address, raw(forged["pages"], address) ^ 1
    )
    if cell in ("boundary_return", "boundary_argument"):
        index = 0 if cell == "boundary_return" else 1
        forged["boundary_request"]["retained_stack_words"][index] ^= 1
        forged["logical"]["frame"]["stack_words"][index] ^= 1
    assert expected["pages"] == independent_pages(vector, fixture) != forged["pages"]


@pytest.mark.parametrize(
    "mutation", ["child_pages", "child_registers", "events", "boundary_registers"]
)
def test_child_entry_page_and_full_eax_event_gpr_forgeries_rejected_by_independent_composition(
    cases, mutation
):
    vector, fixture, expected = next(
        row for row in cases if row[0]["family"] == "false"
    )
    independent = independent_composition(vector, fixture)
    forged = copy.deepcopy(expected)
    if mutation == "child_pages":
        child = forged["children"][0]["fixture"]
        child["pages"] = change(
            child["pages"],
            fixture["entry"] - 32,
            raw(child["pages"], fixture["entry"] - 32) ^ 1,
        )
        assert child["pages"] != independent["child"]["fixture"]["pages"]
    elif mutation == "child_registers":
        forged["children"][0]["result"]["registers"]["eax"] ^= 0x100
        assert (
            forged["children"][0]["result"]["registers"]
            != independent["child"]["registers"]
        )
    elif mutation == "events":
        forged["events"][0]["value"] ^= 1
        assert forged["events"] != independent["events"]
    else:
        forged["registers"]["ecx"] ^= 1
        forged["boundary_request"]["entry_registers"]["ecx"] = forged["registers"][
            "ecx"
        ]
        assert forged["registers"] != independent["registers"]


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (
        PREFIX + "native_lua_class_callback_assertion_prefix_conformance.json"
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


def test_sealed_receipt_deterministic_bytes_all_sixteen_controls_and_entry_only_scope(
    receipts,
):
    path, evidence, _, sources = receipts
    assert set(c.SOURCE_PINS) == {
        "program_facts",
        "factory_chain",
        "marker_semantics",
        "marker_conformance",
        "callback_error",
    }
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    for key, value in dict(
        cases=192,
        static_sites=65,
        executed_sites=59,
        instruction_bytes=185,
        native_instructions=8256,
        supplied_api_calls=720,
        assertion_boundaries=192,
        marker_calls=144,
        controls=16,
        opaque_native_instructions=0,
        accounting_promotions=0,
        families=dict(null=48, absent=48, nil=48, false=48),
    ).items():
        assert evidence["summary"][key] == value
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    wanted = {
        "ancestor",
        "userdata",
        "expression_page",
        "cookie",
        "saved_register",
        "local_userdata",
        "boundary_return",
        "boundary_word",
        "iat_padding",
        "result",
        "flags",
        "api_argument",
        "boundary_argument",
        "api_response",
        "lua_identity",
        "upvalue_guard",
    }
    assert (
        set(controls) == wanted == set(c.CONTROLS)
        and len(evidence["negative_controls"]) == 16
    )
    assert all(
        row["rejected"] and row["reason"] == c.CONTROLS[kind]
        for kind, row in controls.items()
    )
    excluded = " ".join(evidence["scope"]["excluded"])
    assert "Assertion-helper execution" in excluded and "callback return" in excluded
    assert (
        "Interpretation or validation of expression and filename pointer contents"
        in excluded
    )
    assert (
        "Argument marker, class operation, table transfer" in excluded
        and "accounting promotion" in excluded
    )


def test_exact_native_path_counts_short_circuit_marker_ret_and_no_helper_instruction(
    receipts,
):
    _, evidence, _, _ = receipts
    traces = [c._trace(vector) for vector in c.vectors()]
    for vector, trace in zip(c.vectors(), traces):
        assert (
            len(trace)
            == {"null": 23, "absent": 39, "nil": 55, "false": 55}[vector["family"]]
        )
        assert trace[0] == "0x002ec110"
        assert trace[-1] == (
            "0x002ec14c" if vector["family"] == "null" else "0x002ec170"
        )
        assert (
            "0x00379cc2" not in trace
            and "0x002ec151" not in trace
            and "0x002ec175" not in trace
        )
        assert trace.count("0x002eb560") == int(vector["family"] != "null")
        assert trace.count("0x002eb5b3") == int(vector["family"] != "null")
        assert trace.count("0x002eb581") == int(vector["family"] in ("nil", "false"))
        assert "0x002eb59a" not in trace and "0x002ec195" not in trace
    union = {pc for trace in traces for pc in trace}
    assert sum(map(len, traces)) == 8256
    assert sorted(union) == evidence["executed_rvas"]
    assert evidence["summary"]["executed_sites"] == len(union)
    static = {p["rva"] for p in evidence["body"]["points"]}
    assert static - union == {
        "0x002ec151",
        "0x002eb59a",
        "0x002eb5a0",
        "0x002eb5a3",
        "0x002eb5a5",
        "0x002eb5a6",
    }


def test_pe_free_static_extents_actual_marker_receipt_and_native_boundary_call_witnesses(
    receipts,
):
    _, evidence, _, sources = receipts
    points = evidence["body"]["points"]
    ranges = evidence["body"]["ranges"]
    assert [(int(r["start_rva"], 16), int(r["end_rva"], 16)) for r in ranges] == [
        (0x2EB560, 0x2EB5B4),
        (0x2EC110, 0x2EC175),
    ]
    assert sum(p["size"] for p in points) == 185
    assert evidence["summary"]["static_sites"] == len(points)
    assert [p for p in points if int(p["rva"], 16) < 0x2EC110] == sources[
        "marker_conformance"
    ]["body"]["points"]
    by_rva = {p["rva"]: p for p in points}
    for rva, payload in {"0x002ec110": b"\x55", "0x002eb5b3": b"\xc3"}.items():
        assert by_rva[rva]["size"] == len(payload)
        assert by_rva[rva]["sha256"] == hashlib.sha256(payload).hexdigest()
    for call in (0x2EC14C, 0x2EC170):
        payload = b"\xe8" + (0x379CC2 - (call + 5)).to_bytes(4, "little", signed=True)
        point = by_rva[f"0x{call:08x}"]
        assert (
            point["size"] == 5
            and point["sha256"] == hashlib.sha256(payload).hexdigest()
        )


@pytest.mark.parametrize(
    "mutation", ["summary", "vector", "control", "body", "kind", "observations"]
)
def test_modified_receipt_rejected(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    if mutation == "summary":
        changed["summary"]["assertion_boundaries"] -= 1
    elif mutation == "vector":
        changed["vectors"][0]["family"] = "zero"
    elif mutation == "control":
        changed["negative_controls"][0]["rejected"] = False
    elif mutation == "body":
        changed["body"]["ranges"][0]["sha256"] = "0" * 64
    elif mutation == "observations":
        changed["observations_sha256"] = "0" * 64
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ["missing", "extra", "pin", "kind"])
def test_strict_five_source_partition_and_pin_preflight(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["callback_error"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["callback_error"]["schema_version"] += 1
    else:
        changed["marker_semantics"]["analysis_kind"] = "pe_other"
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
    noncanonical = tmp_path / "callback-assertion-prefix.json"
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
