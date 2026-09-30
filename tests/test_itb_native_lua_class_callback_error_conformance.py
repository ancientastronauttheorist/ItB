"""Independent continuous marker composition ending at callback lua_error entry."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_callback_error_conformance as c
from src.observatory import native_lua_class_callback_error_semantics as model

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_callback_error_conformance.py"
CANONICAL = "1c720f1a11c848aa2e5c9ef31dbb4aea6eb9e24bcb1867b30f463cb2d35ff988"
RAW = "970e677a0ea99e2ae9eabf27fb825fd70f0efdd2845e991b7d7f6ce89d2b9a6e"
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


def logical_for(vector, fixture):
    return model.apply(
        state=fixture["state"],
        userdata=fixture["userdata"],
        upvalue_kind=vector["upvalue_kind"],
        argument_has_metatable=vector["argument_mode"] != "absent",
        argument_kind=(
            "nil" if vector["argument_mode"] == "absent" else vector["argument_mode"]
        ),
    )


def marker_vector_for(vector, index):
    return dict(
        alignment=vector["alignment"],
        prefix_length=1,
        has_metatable=index == 0 or vector["argument_mode"] != "absent",
        value_kind=(
            vector["upvalue_kind"]
            if index == 0
            else (
                "nil"
                if vector["argument_mode"] == "absent"
                else vector["argument_mode"]
            )
        ),
        final_void_eax=(
            (0, 0x12345678, 0xFFFFFFFF) if index == 0 else (0xFFFFFFFF, 0, 0x12345678)
        )[vector["profile"]],
    )


def independent_final_pages(vector, fixture):
    """Closed parent cells plus retained scratch from the two nested markers."""
    frame, state = fixture["entry"] - 4, fixture["state"]
    cells = {
        frame: fixture["registers"]["ebp"],
        frame - 8: raw(fixture["pages"], 0x893F28) ^ frame,
        frame - 20: fixture["userdata"],
        frame - 28: fixture["registers"]["ebx"],
        frame - 32: fixture["registers"]["esi"],
        frame - 36: fixture["registers"]["edi"],
        frame - 40: 0x83C99C,
        frame - 44: state,
        frame - 48: state,
        frame - 52: 0x6EC19B,
        frame - 56: 0x6EB56B if vector["argument_mode"] == "absent" else 0x6EB5AD,
        frame - 60: state,
        frame - 64: 0xFFFFFFFF,
        frame - 68: state,
        frame - 72: 0x6EB590,
    }
    result = dict(fixture["pages"])
    for address, value in cells.items():
        result = change(result, address, value)
    return result


def independent_composition(vector, fixture):
    """Hand-authored reached frames/events composed with marker stack corollaries.

    Child pages come from the existing independent closed stack law, never
    from this module's expected child result or its event replay.
    """
    frame, state = fixture["entry"] - 4, fixture["state"]
    pages, events, calls, children = fixture["pages"], [], [], []

    def read(address):
        events.append(
            dict(access="read", address=address, width=4, value=raw(pages, address))
        )

    def write(address, value):
        nonlocal pages
        events.append(dict(access="write", address=address, width=4, value=value))
        pages = change(pages, address, value)

    def call(api, sp, args, continuation, incoming, response, group):
        read(SLOTS[api])
        write(sp, continuation)
        calls.append(
            dict(
                api=api,
                target=TARGETS[api],
                entry_esp=sp,
                arguments=args,
                continuation=continuation,
                entry_registers=dict(incoming, esp=sp),
                response=response,
                group=group,
            )
        )

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
    first_response = dict(
        eax=fixture["userdata"],
        ecx=0xA1000001 + 0x100 * vector["profile"],
        edx=0xB1000001 + 0x100 * vector["profile"],
        eflags=0x297,
    )
    calls.append(
        dict(
            api="lua_touserdata",
            target=0x05000D00,
            entry_esp=frame - 48,
            arguments=[state, 0xFFFFD8ED],
            continuation=0x6EC134,
            entry_registers=dict(
                original,
                eax=cookie,
                ebx=state,
                edi=0x05000D00,
                ebp=frame,
                esp=frame - 48,
            ),
            response=first_response,
            group="direct",
        )
    )
    write(frame - 20, fixture["userdata"])
    regs = dict(
        original,
        eax=fixture["userdata"],
        ebx=state,
        ecx=state,
        edx=0xFFFFD8ED,
        esi=fixture["userdata"],
        edi=0x05000D00,
        ebp=frame,
        esp=frame - 40,
    )
    for index, continuation in enumerate((0x6EC160, 0x6EC184)):
        mv = marker_vector_for(vector, index)
        regs.update(ecx=state, edx=0xFFFFD8ED if index == 0 else 1, esp=frame - 40)
        write(frame - 40, continuation)
        incoming = dict(regs)
        child_fixture = dict(
            entry=frame - 40,
            endpoint=continuation,
            registers=incoming,
            pages=dict(pages),
        )
        corollary = c.marker._stack_model(mv, child_fixture)
        entry = frame - 40
        group = "upvalue_marker" if index == 0 else "argument_marker"
        write(entry - 4, incoming["esi"])
        write(entry - 8, incoming["edx"])
        write(entry - 12, state)
        regs["esi"] = state
        api_rows = [("lua_getmetatable", incoming["edx"], -16, 0x6EB56B)]
        if mv["has_metatable"]:
            api_rows += [
                ("lua_pushstring", 0x83C738, -16, 0x6EB57E),
                ("lua_gettable", 0xFFFFFFFE, -24, 0x6EB587),
                ("lua_toboolean", 0xFFFFFFFF, -32, 0x6EB590),
                ("lua_settop", 0xFFFFFFFD, -16, 0x6EB5A0 if index == 0 else 0x6EB5AD),
            ]
        for response_index, (api, argument, displacement, after) in enumerate(
            api_rows, 1
        ):
            if response_index != 1:
                write(entry + displacement + 8, argument)
                write(entry + displacement + 4, state)
            eax = (0x91A2B300 + 17 * response_index + vector["alignment"]) & 0xFFFFFFFF
            if api == "lua_getmetatable":
                eax = int(mv["has_metatable"])
            elif api == "lua_toboolean":
                eax = int(index == 0)
            elif api == "lua_settop":
                eax = mv["final_void_eax"]
            response = dict(
                eax=eax,
                ecx=0xA0000000 + 256 * vector["alignment"] + response_index,
                edx=0xB0000100 + response_index,
                eflags=0x202 | ((response_index * 0x95) & 0x8D5),
            )
            call(
                api,
                entry + displacement,
                [state, argument],
                after,
                regs,
                response,
                group,
            )
            regs.update({r: response[r] for r in ("eax", "ecx", "edx")})
        read(entry - 4)
        read(entry)
        regs.update(esi=incoming["esi"], esp=entry + 4)
        regs["eax"] = (
            (mv["final_void_eax"] & 0xFFFFFF00) | int(index == 0)
            if mv["has_metatable"]
            else 0
        )
        assert pages == corollary
        children.append(
            dict(
                vector=mv, fixture=child_fixture, pages=corollary, registers=dict(regs)
            )
        )
    write(frame - 40, 0x83C99C)
    write(frame - 44, state)
    response = dict(
        eax=0,
        ecx=0xA1000002 + 0x100 * vector["profile"],
        edx=0xB1000002 + 0x100 * vector["profile"],
        eflags=0x202 | ((2 * 0x95) & 0x8D5),
    )
    call(
        "lua_pushstring",
        frame - 48,
        [state, 0x83C99C],
        0x6EC194,
        regs,
        response,
        "direct",
    )
    write(frame - 48, state)
    read(0x7D6498)
    write(frame - 52, 0x6EC19B)
    return dict(pages=pages, events=events, calls=calls, children=children)


@pytest.fixture(scope="module")
def cases():
    selected = []
    for vector in c.vectors():
        kind = ("zero", "empty_string", "table").index(vector["upvalue_kind"])
        mode = ("absent", "nil", "false").index(vector["argument_mode"])
        if vector["alignment"] == (kind * 5 + mode * 3 + vector["profile"]) % 16:
            selected.append(vector)
    assert len(selected) == 27 and {v["alignment"] for v in selected} == set(range(16))
    return [(v, f, c._expected(v, f)) for v in selected for f in [c._fixture(v)]]


def test_exact_finite_corpus_shapes_and_detached_determinism():
    vectors = c.vectors()
    assert (
        len(vectors) == 432 and len({tuple(sorted(v.items())) for v in vectors}) == 432
    )
    assert {v["alignment"] for v in vectors} == set(range(16))
    assert {v["profile"] for v in vectors} == {0, 1, 2}
    assert {v["upvalue_kind"] for v in vectors} == {"zero", "empty_string", "table"}
    assert {v["argument_mode"] for v in vectors} == {"absent", "nil", "false"}
    assert vectors == c.vectors()
    vectors[0]["profile"] = 99
    assert c.vectors()[0]["profile"] == 0


def test_fixture_geometry_shared_bindings_message_and_userdata_are_preserved(cases):
    for vector, fixture, expected in cases:
        profile, entry = vector["profile"], fixture["entry"]
        assert entry == 0x30001000 + vector["alignment"]
        assert fixture["state"] == 0x12001000 + 0x100 * profile
        assert fixture["userdata"] == 0x11000FFF + 7 * profile
        assert raw(fixture["pages"], entry) == 0x0400A000
        assert raw(fixture["pages"], entry + 4) == fixture["state"]
        assert raw(fixture["pages"], 0x893F28) == (0, 0x12345678, 0xFFFFFFFF)[profile]
        assert raw(fixture["pages"], 0x7D6498) == 0x05000F00
        assert all(
            raw(fixture["pages"], SLOTS[name]) == target
            for name, target in TARGETS.items()
        )
        for pointer, literal in (
            (0x83C738, b"__luabind_classrep\0"),
            (0x83C99C, b"expected class to derive from or a newline\0"),
        ):
            assert (
                bytes(
                    raw(fixture["pages"], pointer + i, 1) for i in range(len(literal))
                )
                == literal
            )
        assert all(
            type(page) is bytes and len(page) == 4096
            for page in fixture["pages"].values()
        )
        assert 0 not in fixture["pages"] and not any(
            e["address"] == 0 for e in expected["events"]
        )
        assert expected["pages"][0x11000000] == fixture["pages"][0x11000000]
        assert expected["pages"][0x11001000] == fixture["pages"][0x11001000]


def test_complete_page_oracle_child_stack_composition_and_ordered_events(cases):
    for vector, fixture, expected in cases:
        independent = independent_composition(vector, fixture)
        assert (
            independent["pages"]
            == independent_final_pages(vector, fixture)
            == expected["pages"]
        )
        assert independent["events"] == expected["events"]
        for child, oracle in zip(expected["children"], independent["children"]):
            assert child["fixture"]["pages"] == oracle["fixture"]["pages"]
            assert child["fixture"]["registers"] == oracle["fixture"]["registers"]
            assert child["result"]["pages"] == oracle["pages"]
            assert child["result"]["registers"] == oracle["registers"]


def test_reached_import_arguments_frames_responses_and_all_incoming_gprs(cases):
    for vector, fixture, expected in cases:
        independent = independent_composition(vector, fixture)
        assert len(expected["calls"]) == (
            8 if vector["argument_mode"] == "absent" else 12
        )
        for actual, oracle in zip(expected["calls"], independent["calls"]):
            for field in (
                "api",
                "target",
                "entry_esp",
                "arguments",
                "continuation",
                "entry_registers",
                "response",
                "group",
            ):
                assert actual[field] == oracle[field]
        direct = [call for call in expected["calls"] if call["group"] == "direct"]
        assert [call["api"] for call in direct] == ["lua_touserdata", "lua_pushstring"]
        assert [call["entry_esp"] for call in direct] == [fixture["entry"] - 52] * 2


def test_actual_marker_returns_restore_parent_prefix_and_preserve_full_eax_above_al(
    cases,
):
    for vector, fixture, expected in cases:
        frame = fixture["entry"] - 4
        assert len(expected["children"]) == 2
        for index, child in enumerate(expected["children"]):
            mv = marker_vector_for(vector, index)
            assert child["vector"] == c._marker_vector(vector, index) == mv
            assert child["fixture"]["entry"] == frame - 40
            assert child["fixture"]["endpoint"] == (0x6EC160, 0x6EC184)[index]
            assert child["fixture"]["registers"]["ecx"] == fixture["state"]
            assert child["fixture"]["registers"]["edx"] == (0xFFFFD8ED, 1)[index]
            returned = child["result"]["registers"]
            assert returned["esp"] == frame - 36
            for register in ("ebx", "esi", "edi", "ebp"):
                assert returned[register] == child["fixture"]["registers"][register]
            eax = (
                (mv["final_void_eax"] & 0xFFFFFF00) | int(index == 0)
                if mv["has_metatable"]
                else 0
            )
            assert returned["eax"] == eax and returned["eax"] & 255 == int(index == 0)
            assert child["result"]["relation"]["api_calls"] == (
                5 if mv["has_metatable"] else 1
            )
            if index == 1:
                assert (
                    child["result"]["flags"] == 0x44
                    and child["result"]["flag_mask"] == 0x8C5
                )


def test_final_error_entry_registers_flags_deferred_cleanup_cookie_and_ancestors(cases):
    for vector, fixture, expected in cases:
        frame, state = fixture["entry"] - 4, fixture["state"]
        assert expected["registers"] == dict(
            fixture["registers"],
            eax=0,
            ebx=state,
            ecx=0xA1000002 + 0x100 * vector["profile"],
            edx=0xB1000002 + 0x100 * vector["profile"],
            esi=fixture["userdata"],
            edi=0x05000D00,
            esp=frame - 52,
            ebp=frame,
        )
        assert expected["flags"] == (0x202 | ((2 * 0x95) & 0x8D5)) & 0xCD5
        request = expected["error_request"]
        assert request == dict(
            target=0x05000F00,
            arguments=[state],
            continuation=0x6EC19B,
            entry_esp=frame - 52,
            entry_registers=expected["registers"],
            retained_stack_words=[0x6EC19B, state, state, 0x83C99C],
        )
        assert [
            raw(expected["pages"], frame - 52 + 4 * i) for i in range(4)
        ] == request["retained_stack_words"]
        assert (
            raw(expected["pages"], frame - 8) == raw(fixture["pages"], 0x893F28) ^ frame
        )
        assert raw(expected["pages"], frame - 20) == fixture["userdata"]
        for offset in (4, 12, 16, 24):
            assert raw(expected["pages"], frame - offset) == raw(
                fixture["pages"], frame - offset
            )
        assert bytes(
            raw(expected["pages"], fixture["entry"] + i, 1) for i in range(64)
        ) == bytes(raw(fixture["pages"], fixture["entry"] + i, 1) for i in range(64))
        assert all(
            expected["pages"][page] == payload
            for page, payload in fixture["pages"].items()
            if page not in (0x30000000, 0x30001000)
        )


def test_all_nine_semantic_modes_lua_tokens_prefix_restoration_and_terminal_no_result(
    cases,
):
    assert {(v["upvalue_kind"], v["argument_mode"]) for v, _, _ in cases} == {
        (u, m)
        for u in ("zero", "empty_string", "table")
        for m in ("absent", "nil", "false")
    }
    for vector, fixture, expected in cases:
        logical = logical_for(vector, fixture)
        assert expected["logical"] == normalized(logical)
        assert len(logical["calls"]) == (
            9 if vector["argument_mode"] == "absent" else 13
        )
        assert logical["closure_upvalue"] == ("userdata", fixture["userdata"])
        assert logical["marker_results"] == dict(upvalue_al=1, argument_al=0)
        observer = c._Lua(vector, fixture)
        for call in logical["calls"]:
            args = [value & 0xFFFFFFFF for value in call["arguments"]]
            assert observer.apply(call["api"], args) == call["result"]
        assert normalized(observer.calls) == normalized(logical["calls"])
        assert observer.stack == [("argument", 1), ("message", "argument_marker_error")]
        assert (
            logical["lua_stack_delta"] == 1 and logical["calls"][-1]["result"] is None
        )
        assert logical["calls"][-2]["before"] == [("argument", 1)]
        for call in logical["calls"]:
            if call["api"] == "lua_settop":
                assert call["after"] == [("argument", 1)]
        assert (
            logical["frame"]["error_stack_words"]
            == expected["error_request"]["retained_stack_words"]
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "state",
        "upvalue_index",
        "argument_index",
        "lookup_index",
        "literal",
        "marker_identity",
        "error_identity",
    ],
)
def test_runtime_lua_observer_rejects_wrong_requests_and_identity(cases, mutation):
    vector, fixture, _ = next(
        row for row in cases if row[0]["argument_mode"] == "false"
    )
    observer, state = c._Lua(vector, fixture), fixture["state"]
    logical = logical_for(vector, fixture)
    if mutation == "state":
        api, args = "lua_touserdata", [state ^ 1, 0xFFFFD8ED]
    elif mutation == "upvalue_index":
        api, args = "lua_getmetatable", [state, 1]
    elif mutation == "argument_index":
        for call in logical["calls"][:6]:
            observer.apply(
                call["api"], [value & 0xFFFFFFFF for value in call["arguments"]]
            )
        api, args = "lua_getmetatable", [state, 0xFFFFD8ED]
    elif mutation in ("lookup_index", "literal", "marker_identity"):
        for call in logical["calls"][:3]:
            observer.apply(
                call["api"], [value & 0xFFFFFFFF for value in call["arguments"]]
            )
        if mutation == "marker_identity":
            observer.stack[-1] = ("literal", "wrong")
            api, args = "lua_gettable", [state, 0xFFFFFFFE]
        elif mutation == "lookup_index":
            api, args = "lua_gettable", [state, 0xFFFFFFFF]
        else:
            api, args = "lua_pushstring", [state, 0x83C738 ^ 1]
    else:
        for call in logical["calls"][:-1]:
            observer.apply(
                call["api"], [value & 0xFFFFFFFF for value in call["arguments"]]
            )
        observer.stack[-1] = ("message", "wrong")
        api, args = "lua_error", [state]
    with pytest.raises(RuntimeError, match="callback error Lua"):
        observer.apply(api, args)


def test_expected_determinism_immutable_inputs_and_detached_outputs(cases):
    for vector, fixture, expected in cases[::5]:
        original = copy.deepcopy((vector, fixture))
        second = c._expected(vector, fixture)
        assert second == expected and (vector, fixture) == original
        second["registers"]["eax"] = 7
        second["children"][0]["fixture"]["registers"]["edx"] = 2
        second["error_request"]["retained_stack_words"][0] ^= 1
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
        ("upvalue_kind", "nil"),
        ("upvalue_kind", "false"),
        ("upvalue_kind", None),
        ("argument_mode", "zero"),
        ("argument_mode", True),
    ],
)
def test_strict_finite_vector_types_and_domain(field, value):
    with pytest.raises(RuntimeError):
        c._fixture(dict(c.vectors()[0], **{field: value}))


@pytest.mark.parametrize("shape", ["missing", "extra", "list", "none"])
def test_strict_fixture_dictionary_schema(shape):
    vector = c.vectors()[0]
    if shape == "missing":
        del vector["argument_mode"]
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
        "message",
        "marker_literal",
        "error_return",
        "retained",
        "child_scratch",
        "userdata",
    ],
)
def test_coordinated_expected_page_and_boundary_forgeries_fail_independent_cells(
    cases, cell
):
    vector, fixture, expected = cases[-1]
    frame = fixture["entry"] - 4
    address = dict(
        ancestor=fixture["entry"] + 8,
        cookie=0x893F28,
        saved_ebp=frame,
        saved_esi=frame - 32,
        local_userdata=frame - 20,
        message=0x83C99C,
        marker_literal=0x83C738,
        error_return=frame - 52,
        retained=frame - 40,
        child_scratch=frame - 72,
        userdata=fixture["userdata"],
    )[cell]
    forged = copy.deepcopy(expected)
    forged["pages"] = change(
        forged["pages"], address, raw(forged["pages"], address) ^ 1
    )
    if cell in ("error_return", "retained"):
        index = 0 if cell == "error_return" else 3
        forged["error_request"]["retained_stack_words"][index] ^= 1
        forged["logical"]["frame"]["error_stack_words"][index] ^= 1
    assert forged["pages"] != independent_final_pages(vector, fixture)
    assert expected["pages"] == independent_final_pages(vector, fixture)


@pytest.mark.parametrize(
    "mutation", ["child_pages", "child_registers", "event", "final_registers"]
)
def test_independent_composition_rejects_joined_child_event_and_register_forgeries(
    cases, mutation
):
    vector, fixture, expected = cases[-1]
    independent = independent_composition(vector, fixture)
    forged = copy.deepcopy(expected)
    if mutation == "child_pages":
        child = forged["children"][1]["fixture"]
        child["pages"] = change(child["pages"], fixture["entry"] - 76, 0)
        assert child["pages"] != independent["children"][1]["fixture"]["pages"]
    elif mutation == "child_registers":
        forged["children"][0]["result"]["registers"]["eax"] ^= 0x100
        assert (
            forged["children"][0]["result"]["registers"]
            != independent["children"][0]["registers"]
        )
    elif mutation == "event":
        forged["events"][0]["value"] ^= 1
        assert forged["events"] != independent["events"]
    else:
        forged["registers"]["esi"] ^= 1
        assert forged["registers"]["esi"] != fixture["userdata"]


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (PREFIX + "native_lua_class_callback_error_conformance.json")
    evidence = json.loads(path.read_text())
    paths, sources = {}, {}
    for key, (kind, digest) in c.SOURCE_PINS.items():
        suffix = "program_facts" if key == "program_facts" else kind.removeprefix("pe_")
        source_path = PROGRAMS / (PREFIX + suffix + ".json")
        sources[key] = json.loads(source_path.read_text())
        assert c._canonical_sha256(sources[key]) == digest
        paths[key] = source_path
    return path, evidence, paths, sources


def test_receipt_seal_deterministic_encoding_all_eighteen_controls_and_boundary_scope(
    receipts,
):
    path, evidence, _, sources = receipts
    assert set(c.SOURCE_PINS) == {
        "program_facts",
        "factory_chain",
        "marker_semantics",
        "marker_conformance",
    }
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    for key, value in dict(
        cases=432,
        static_sites=76,
        executed_sites=66,
        instruction_bytes=223,
        native_instructions=35712,
        supplied_api_calls=4608,
        error_boundaries=432,
        marker_calls=864,
        controls=18,
        opaque_native_instructions=0,
        accounting_promotions=0,
    ).items():
        assert evidence["summary"][key] == value
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    wanted = {
        "ancestor",
        "userdata",
        "message",
        "marker_literal",
        "cookie",
        "saved_register",
        "local_userdata",
        "error_return",
        "retained_literal",
        "iat_padding",
        "result",
        "flags",
        "api_argument",
        "error_argument",
        "push_response",
        "lua_identity",
        "upvalue_guard",
        "argument_guard",
    }
    assert (
        set(controls) == wanted == set(c.CONTROLS)
        and len(evidence["negative_controls"]) == 18
    )
    assert all(
        row["rejected"] and row["reason"] == c.CONTROLS[kind]
        for kind, row in controls.items()
    )
    excluded = " ".join(evidence["scope"]["excluded"])
    assert (
        "Execution or response of lua_error" in excluded
        and "callback return" in excluded
    )
    assert (
        "Assertion paths, class operation, table transfers" in excluded
        and "accounting promotion" in excluded
    )


def test_finite_native_trace_totals_marker_rets_and_parent_site_partition(receipts):
    _, evidence, _, sources = receipts
    traces = [c._trace(vector) for vector in c.vectors()]
    parent_union = set()
    for vector, trace in zip(c.vectors(), traces):
        assert len(trace) == (72 if vector["argument_mode"] == "absent" else 88)
        assert trace[0] == "0x002ec110" and trace[-1] == "0x002ec195"
        assert trace.count("0x002eb560") == 2 and trace.count("0x002eb5a6") == 1
        assert trace.count("0x002eb5b3") == 1
        assert trace.count("0x002eb581") == (
            1 if vector["argument_mode"] == "absent" else 2
        )
        parent = [pc for pc in trace if 0x2EC110 <= int(pc, 16) < 0x2EC19B]
        assert len(parent) == 34
        parent_union.update(parent)
        assert "0x002ec19b" not in trace and "0x002ec1ad" not in trace
    union = {pc for trace in traces for pc in trace}
    assert sum(map(len, traces)) == 35712 and len(parent_union) == 34
    assert sorted(union) == evidence["executed_rvas"]
    assert evidence["summary"]["executed_sites"] == len(union)
    marker_sites = {p["rva"] for p in sources["marker_conformance"]["body"]["points"]}
    assert union - parent_union == marker_sites


def test_pe_free_static_extents_exact_marker_receipt_and_error_call_witness(receipts):
    _, evidence, _, sources = receipts
    points = evidence["body"]["points"]
    ranges = evidence["body"]["ranges"]
    assert [(int(r["start_rva"], 16), int(r["end_rva"], 16)) for r in ranges] == [
        (0x2EB560, 0x2EB5B4),
        (0x2EC110, 0x2EC19B),
    ]
    assert sum(p["size"] for p in points) == 223
    assert evidence["summary"]["static_sites"] == len(points)
    marker_points = [p for p in points if int(p["rva"], 16) < 0x2EC110]
    assert marker_points == sources["marker_conformance"]["body"]["points"]
    by_rva = {p["rva"]: p for p in points}
    for rva, payload in {
        "0x002ec110": b"\x55",
        "0x002ec195": bytes.fromhex("ff1598647d00"),
        "0x002eb5a6": b"\xc3",
        "0x002eb5b3": b"\xc3",
    }.items():
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
        changed["vectors"][0]["argument_mode"] = "table"
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
def test_strict_four_source_partition_and_pin_preflight(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["marker_conformance"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["marker_conformance"]["schema_version"] += 1
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
    noncanonical = tmp_path / "callback-error.json"
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
