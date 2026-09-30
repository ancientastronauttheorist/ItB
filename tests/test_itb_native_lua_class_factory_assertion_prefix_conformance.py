"""Independent continuous factory state before its context assertion helper."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_factory_assertion_prefix_conformance as c
from src.observatory import native_lua_class_factory_assertion_prefix_semantics as model

factory, record, full = c.factory, c.record, c.full
ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_assertion_prefix_conformance.py"
CANONICAL = "c164d95f08507d66c26fae898a1f00dff84ce1db64a14b380122f66ed00ae59f"
RAW = "a0dcaf08f40f8aa82baa07524765c88eaebefc69103682ed8ed01b44af2e06db"
CONTINUATIONS = (
    0x2EADA7,
    0x2EADB0,
    0x2EADBC,
    0x2EADF1,
    0x2EADFA,
    0x2EAE06,
    0x2EAE35,
    0x2EAE41,
    0x2EAE4D,
    0x2EAE56,
    0x2EAE5E,
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
    spec = fixture["spec"]
    return model.apply(
        state=fixture["state"],
        first_pointer=fixture["first_pointer"],
        second_pointer=fixture["second_pointer"],
        userdata=fixture["userdata"],
        name_bytes=factory._name(vector),
        context_pointer=spec["context_pointer"],
        context_guard=0xFFFFFFFE,
        references=spec["references"][:2],
    )


def independent_pages_and_frames(fixture, before, logical):
    """Sealed record baseline plus eleven retained cdecl groups and boundary."""
    pages = before["pages"]
    inner = before["registers"]["ebp"]
    stack = inner - 36  # Actual record-helper return has pushed the first zero.
    frames = []
    for index, (call, continuation) in enumerate(
        zip(logical["calls"][7:], CONTINUATIONS)
    ):
        arguments = call["arguments"][:-1] if index == 0 else call["arguments"]
        for word in reversed(arguments):
            stack -= 4
            pages = change(pages, stack, word & 0xFFFFFFFF)
        stack -= 4
        pages = change(pages, stack, 0x400000 + continuation)
        frames.append(stack)
        stack += 4 + {2: 28, 5: 28, 10: 40}.get(index, 0)
    assert stack == inner - 32
    for offset, value in logical["final_fields"].items():
        pages = change(pages, fixture["userdata"] + offset, value)
    pages = change(pages, inner + 12, fixture["spec"]["context_pointer"])
    for word in reversed((0x83C6B0, 0x83C680, 96)):
        stack -= 4
        pages = change(pages, stack, word)
    stack -= 4
    pages = change(pages, stack, 0x6EAE7B)
    assert stack == inner - 48
    return pages, frames


def independent_suffix(vector, fixture, before):
    """Reached operand events, incoming API GPRs and active assertion frame."""
    pages, regs = dict(before["pages"]), dict(before["registers"])
    events, calls = [], []
    inner, state, userdata = regs["ebp"], fixture["state"], fixture["userdata"]
    refs, context = fixture["spec"]["references"], fixture["spec"]["context_pointer"]

    def read(address):
        value = raw(pages, address)
        events.append(dict(access="read", address=address, width=4, value=value))
        return value

    def write(address, value):
        nonlocal pages
        events.append(dict(access="write", address=address, width=4, value=value))
        pages = change(pages, address, value)

    def push(value):
        regs["esp"] -= 4
        write(regs["esp"], value & 0xFFFFFFFF)

    def args(*words):
        for word in reversed(words):
            push(word)

    def api(name, site, continuation, arguments, value=0, staged=False):
        target = full.ALL_TARGETS[name]
        if staged:
            assert regs["ebx"] == target
        else:
            assert read(0x400000 + full.ALL_SLOTS[name]) == target
        push(0x400000 + continuation)
        index = 7 + len(calls)
        response = dict(
            eax=value,
            ecx=0xA1000000 + 0x100 * vector["profile"] + index,
            edx=0xB1000000 + 0x100 * vector["profile"] + index,
            eflags=0x202 | ((index * 0x95) & 0x8D5),
        )
        calls.append(
            dict(
                api=name,
                site_rva=f"0x{site:08x}",
                target=target,
                arguments=[w & 0xFFFFFFFF for w in arguments],
                continuation=0x400000 + continuation,
                entry_esp=regs["esp"],
                entry_registers=dict(regs),
                response=response,
            )
        )
        regs.update({r: response[r] for r in ("eax", "ecx", "edx")})
        regs["esp"] += 4

    regs["esi"] = read(inner + 8)
    args(state, 0)
    write(userdata + 60, 0)
    api("lua_createtable", 0x2EADA1, 0x2EADA7, [state, 0, 0])
    args(state, -1)
    api("lua_pushvalue", 0x2EADAA, 0x2EADB0, [state, -1])
    args(state, -10000)
    api("luaL_ref", 0x2EADB6, 0x2EADBC, [state, -10000], refs[0])
    regs["edx"] = read(userdata + 28)
    regs["esp"] += 28
    regs["ebx"] = read(0x400000 + full.SLOTS["luaL_unref"])
    write(userdata + 28, state)
    regs["ecx"] = read(userdata + 32)
    write(userdata + 32, refs[0])
    args(state, 0, 0)
    api("lua_createtable", 0x2EADEB, 0x2EADF1, [state, 0, 0])
    args(state, -1)
    api("lua_pushvalue", 0x2EADF4, 0x2EADFA, [state, -1])
    args(state, -10000)
    api("luaL_ref", 0x2EAE00, 0x2EAE06, [state, -10000], refs[1])
    regs["edx"] = read(userdata + 36)
    regs["esp"] += 28
    write(userdata + 36, state)
    regs["ecx"] = read(userdata + 40)
    write(userdata + 40, refs[1])
    regs["ebx"] = read(0x400000 + full.SLOTS["lua_settop"])
    args(state, -3)
    api("lua_settop", 0x2EAE33, 0x2EAE35, [state, -3], staged=True)
    args(state, 0x83BF18)
    api("lua_pushstring", 0x2EAE3B, 0x2EAE41, [state, 0x83BF18])
    args(state, -10000)
    api("lua_gettable", 0x2EAE47, 0x2EAE4D, [state, -10000])
    args(state, -1)
    api("lua_touserdata", 0x2EAE50, 0x2EAE56, [state, -1], context)
    args(state, -2)
    write(inner + 12, context)
    api("lua_settop", 0x2EAE5C, 0x2EAE5E, [state, -2], staged=True)
    regs["eax"] = read(inner + 12)
    regs["esp"] += 40
    assert read(context + 12) == 0xFFFFFFFE
    args(0x83C6B0, 0x83C680, 96)
    push(0x6EAE7B)
    return dict(pages=pages, events=events, calls=calls, registers=regs)


@pytest.fixture(scope="module")
def cases():
    bases = [
        v
        for v in factory.vectors()
        if v["name_alignment"] == {"ascii": 0, "low": 7, "high": 4095}[v["pattern"]]
        and v["equal_pointers"] == bool((v["length"] + v["profile"]) % 2)
    ]
    geometries = [
        (bias, alignment) for bias in (0x100, 0xFFF) for alignment in (0, 7, 15, 31)
    ]
    selected = []
    for index, base in enumerate(bases):
        bias, alignment = geometries[index % 8]
        vector = dict(
            base,
            record_bias=bias,
            record_alignment=alignment,
            registry_profile=index % 3,
        )
        fixture = c._fixture(vector, factory._fixture(base))
        original = factory._expected(base, fixture)
        before = record._extend_expected(full._record_vector(vector), fixture, original)
        selected.append(
            (
                vector,
                fixture,
                original,
                before,
                c._extend_expected(vector, fixture, original),
            )
        )
    assert len(selected) == 36
    return selected


def test_corpus_registry_profiles_record_geometries_and_fixture_guard(cases):
    vectors = c.vectors()
    assert len(vectors) == 5184 and vectors == full.vectors()
    assert len({c._canonical_sha256(v) for v in vectors}) == 5184
    assert {v["registry_profile"] for v in vectors} == {0, 1, 2}
    assert {(v["record_bias"], v["record_alignment"]) for v in vectors} == {
        (bias, a) for bias in (0x100, 0xFFF) for a in (0, 7, 15, 31)
    }
    for vector, fixture, *_ in cases:
        spec = fixture["spec"]
        assert (
            spec["context_guard"]
            == raw(fixture["pages"], spec["context_pointer"] + 12)
            == 0xFFFFFFFE
        )
        assert spec["context_pointer"] == 0x17000100 + 7 * vector["registry_profile"]
        assert (
            fixture["record"]
            == 0x16000000 + vector["record_bias"] + vector["record_alignment"]
        )
        assert all(
            raw(fixture["pages"], 0x400000 + slot) == full.ALL_TARGETS[name]
            for name, slot in full.ALL_SLOTS.items()
        )
    vectors[0]["registry_profile"] = 99
    assert c.vectors()[0]["registry_profile"] == 0


def test_independent_complete_pages_fourteen_fields_record_and_all_physical_suffix_frames(
    cases,
):
    for vector, fixture, _, before, expected in cases:
        logical = logical_for(vector, fixture)
        pages, frames = independent_pages_and_frames(fixture, before, logical)
        assert pages == expected["pages"]
        assert expected["logical"]["factory"] == normalized(logical)
        assert expected["logical"]["record"] == before["logical"]["record"]
        for offset, value in logical["final_fields"].items():
            assert raw(pages, fixture["userdata"] + offset) == value
        assert raw(pages, fixture["userdata"] + 52) == fixture["record"]
        for offset in (48, 64, 68):
            assert raw(pages, fixture["userdata"] + offset) == raw(
                fixture["pages"], fixture["userdata"] + offset
            )
        for offset in (0, 4, 8):
            assert raw(pages, fixture["record"] + offset) == fixture["record"]
        assert raw(pages, fixture["record"] + 12, 2) == 0x0101
        for offset in range(14, 24):
            assert raw(pages, fixture["record"] + offset, 1) == raw(
                fixture["pages"], fixture["record"] + offset, 1
            )
        assert [call["entry_esp"] for call in expected["calls"][7:]] == frames
        assert [call["continuation"] for call in expected["calls"][7:]] == [
            0x400000 + r for r in CONTINUATIONS
        ]


def test_independent_ordered_suffix_events_incoming_api_gprs_and_supplied_responses(
    cases,
):
    for vector, fixture, _, before, expected in cases:
        oracle = independent_suffix(vector, fixture, before)
        assert oracle["pages"] == expected["pages"]
        assert expected["events"] == before["events"] + oracle["events"]
        assert expected["registers"] == oracle["registers"]
        for actual, independent in zip(expected["calls"][7:], oracle["calls"]):
            for field in (
                "api",
                "site_rva",
                "target",
                "arguments",
                "continuation",
                "entry_esp",
                "entry_registers",
                "response",
            ):
                assert actual[field] == independent[field]


def test_assertion_entry_active_nested_fs_cookies_original_ancestors_and_defined_cmp_flags(
    cases,
):
    for vector, fixture, _, before, expected in cases:
        outer = fixture["entry"] - 4
        inner = outer - 52
        assert before["registers"]["ebp"] == inner
        assert expected["registers"] == dict(
            before["registers"],
            eax=fixture["spec"]["context_pointer"],
            ebx=full.ALL_TARGETS["lua_settop"],
            esi=fixture["state"],
            ecx=0xA1000011 + 0x100 * vector["profile"],
            edx=0xB1000011 + 0x100 * vector["profile"],
            esp=inner - 48,
        )
        assert expected["flags"] == 0x44 and expected["flags"] & 0x410 == 0
        assert [raw(expected["pages"], inner - 48 + 4 * i) for i in range(4)] == [
            0x6EAE7B,
            0x83C6B0,
            0x83C680,
            96,
        ]
        assert raw(expected["pages"], 0) == inner - 12
        assert raw(expected["pages"], inner - 12) == outer - 12
        assert raw(expected["pages"], outer - 12) == raw(fixture["pages"], 0)
        cookie = raw(fixture["pages"], factory.COOKIE)
        assert raw(expected["pages"], outer - 36) == cookie ^ outer
        assert raw(expected["pages"], inner - 32) == cookie ^ inner
        assert [
            e["value"]
            for e in expected["events"]
            if e["access"] == "write" and e["address"] == 0
        ] == [outer - 12, inner - 12]
        assert bytes(
            raw(expected["pages"], fixture["entry"] + i, 1) for i in range(64)
        ) == bytes(raw(fixture["pages"], fixture["entry"] + i, 1) for i in range(64))


def test_heap_response_record_geometry_and_native_chain_unchanged_at_assertion(cases):
    assert {(v["record_bias"], v["record_alignment"]) for v, *_ in cases} == {
        (bias, a) for bias in (0x100, 0xFFF) for a in (0, 7, 15, 31)
    }
    for _, fixture, _, before, expected in cases:
        assert (
            expected["heap_calls"] == before["heap_calls"]
            and len(expected["heap_calls"]) == 1
        )
        assert expected["record"] == fixture["record"]
        call = expected["heap_calls"][0]
        assert call["entry_esp"] == before["registers"]["ebp"] - 80
        assert call["arguments"][-2:] == [0, 24]
        assert call["response"]["eax"] == fixture["record"]


def test_runtime_lua_controller_eighteen_requests_two_refs_and_argument_userdata_prefix(
    cases,
):
    for vector, fixture, _, _, expected in cases:
        logical = logical_for(vector, fixture)
        observer = full._Lua(vector, fixture)
        for call in logical["calls"]:
            assert (
                observer.apply(
                    call["api"], [word & 0xFFFFFFFF for word in call["arguments"]]
                )
                == call["result"]
            )
        observed = observer.result()
        assert observed == expected["lua_result"]
        assert observed["final_lua_stack"] == normalized(logical["boundary_lua_stack"])
        assert observed["registry_bindings"] == normalized(logical["registry_bindings"])
        assert len(observed["calls"]) == len(expected["calls"]) == 18
        assert (
            observed["metatable_setting_requests"]
            == observed["global_assignment_requests"]
            == []
        )
        assert not any(call["api"] == "lua_pushcclosure" for call in observed["calls"])


@pytest.mark.parametrize(
    "mutation",
    ["state", "string_contract", "table_index", "lookup_key", "context_identity"],
)
def test_runtime_lua_controller_wrong_state_indices_and_context_tokens_rejected(
    cases, mutation
):
    vector, fixture, *_ = cases[-1]
    logical = logical_for(vector, fixture)
    observer, state = full._Lua(vector, fixture), fixture["state"]
    if mutation == "state":
        api, args = "lua_gettop", [state ^ 1]
    elif mutation == "string_contract":
        api, args = "lua_tolstring", [state, 1, 1]
    else:
        stop = {"table_index": 8, "lookup_key": 15, "context_identity": 16}[mutation]
        for call in logical["calls"][:stop]:
            observer.apply(
                call["api"], [word & 0xFFFFFFFF for word in call["arguments"]]
            )
        if mutation == "table_index":
            api, args = "lua_pushvalue", [state, 1]
        elif mutation == "lookup_key":
            observer.stack[-1] = ("literal", "wrong")
            api, args = "lua_gettable", [state, 0xFFFFD8F0]
        else:
            observer.stack[-1] = ("userdata", fixture["userdata"])
            api, args = "lua_touserdata", [state, 0xFFFFFFFF]
    with pytest.raises(RuntimeError, match="factory Lua"):
        observer.apply(api, args)


def test_context_reads_only_guard_and_later_contracts_are_opaque_protected(cases):
    for vector, fixture, original, _, expected in cases[::9]:
        context = fixture["spec"]["context_pointer"]
        reads = [
            e
            for e in expected["events"]
            if e["access"] == "read" and context <= e["address"] < context + 20
        ]
        assert reads == [
            dict(access="read", address=context + 12, width=4, value=0xFFFFFFFE)
        ]
        changed = copy.deepcopy(fixture)
        changed["pages"] = change(changed["pages"], context + 8, 0xDEADBEEF)
        changed["pages"] = change(changed["pages"], context + 16, 0xFEEDFACE)
        changed["spec"]["references"][2] = None
        changed["spec"]["context_word"] = None
        changed["spec"]["metatable_reference"] = None
        changed_original = factory._expected(
            record._base_vector(full._record_vector(vector)), changed
        )
        alternative = c._extend_expected(vector, changed, changed_original)
        for field in (
            "registers",
            "flags",
            "events",
            "calls",
            "heap_calls",
            "logical",
            "lua_result",
        ):
            assert alternative[field] == expected[field]
        assert all(
            raw(alternative["pages"], context + offset) == value
            for offset, value in ((8, 0xDEADBEEF), (16, 0xFEEDFACE))
        )


def test_deterministic_expected_inputs_immutable_and_outputs_detached(cases):
    for vector, fixture, original, _, expected in cases[::9]:
        before = copy.deepcopy((vector, fixture, original))
        second = c._extend_expected(vector, fixture, original)
        assert second == expected and (vector, fixture, original) == before
        second["registers"]["eax"] ^= 1
        second["logical"]["factory"]["calls"].clear()
        second["lua_result"]["registry_bindings"][0]["reference"] = 0
        assert c._extend_expected(vector, fixture, original) == expected
        assert (vector, fixture, original) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("registry_profile", False),
        ("registry_profile", 0.0),
        ("registry_profile", 3),
        ("record_bias", True),
        ("record_bias", 0x101),
        ("record_alignment", False),
        ("record_alignment", 8),
        ("length", False),
        ("length", 256),
        ("profile", False),
        ("name_alignment", False),
        ("equal_pointers", 0),
    ],
)
def test_strict_finite_fixture_types_and_domain(field, value):
    vector = dict(c.vectors()[0], **{field: value})
    with pytest.raises(RuntimeError):
        base = record._base_vector(full._record_vector(vector))
        c._fixture(vector, factory._fixture(base))


@pytest.mark.parametrize("shape", ["missing", "extra", "list", "none"])
def test_strict_fixture_vector_dictionary_schema(shape):
    vector = c.vectors()[0]
    if shape == "missing":
        del vector["registry_profile"]
    elif shape == "extra":
        vector["unreviewed"] = 1
    elif shape == "list":
        vector = list(vector.items())
    else:
        vector = None
    with pytest.raises(RuntimeError):
        c._fixture(vector, factory._fixture(factory.vectors()[0]))


@pytest.mark.parametrize(
    "cell",
    [
        "ancestor",
        "inner_cookie",
        "outer_cookie",
        "fs",
        "record",
        "stored_record",
        "reference",
        "unreached_field",
        "context_guard",
        "boundary_return",
        "expression",
        "scalar",
    ],
)
def test_coordinated_final_page_logical_and_boundary_forgeries_fail_independent_law(
    cases, cell
):
    vector, fixture, _, before, expected = cases[-1]
    inner, outer = before["registers"]["ebp"], fixture["entry"] - 4
    address = dict(
        ancestor=fixture["entry"] + 8,
        inner_cookie=inner - 32,
        outer_cookie=outer - 36,
        fs=0,
        record=fixture["record"],
        stored_record=fixture["userdata"] + 52,
        reference=fixture["userdata"] + 32,
        unreached_field=fixture["userdata"] + 64,
        context_guard=fixture["spec"]["context_pointer"] + 12,
        boundary_return=inner - 48,
        expression=inner - 44,
        scalar=inner - 36,
    )[cell]
    forged = copy.deepcopy(expected)
    forged["pages"] = change(
        forged["pages"], address, raw(forged["pages"], address) ^ 1
    )
    if cell == "reference":
        forged["logical"]["factory"]["final_fields"]["32"] ^= 1
    elif cell in ("boundary_return", "expression", "scalar"):
        index = {"boundary_return": 0, "expression": 1, "scalar": 3}[cell]
        forged["logical"]["factory"]["frame"]["stack_words"][index] ^= 1
    assert (
        expected["pages"]
        == independent_pages_and_frames(fixture, before, logical_for(vector, fixture))[
            0
        ]
        != forged["pages"]
    )


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (
        PREFIX + "native_lua_class_factory_assertion_prefix_conformance.json"
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


def test_sealed_receipt_nine_sources_deterministic_encoding_controls_and_entry_only_scope(
    receipts,
):
    path, evidence, _, sources = receipts
    assert len(c.SOURCE_PINS) == 9 and "full_factory" in c.SOURCE_PINS
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    for key, value in dict(
        cases=5184,
        static_sites=270,
        executed_sites=221,
        instruction_bytes=807,
        native_instructions=2144448,
        controls=41,
        supplied_api_calls=93312,
        heap_calls=5184,
        initializer_instructions=518400,
        assertion_boundaries=5184,
        opaque_native_instructions=0,
        accounting_promotions=0,
    ).items():
        assert evidence["summary"][key] == value
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    assert (
        set(controls) == set(c.CONTROLS)
        and len(controls) == len(evidence["negative_controls"]) == 41
    )
    assert {
        "assertion_return",
        "assertion_expression",
        "assertion_file",
        "assertion_scalar",
        "context_guard_word",
        "guard_response",
        "boundary_register",
        "lua_identity",
    } <= set(controls)
    assert all(
        row["rejected"] and row["reason"] == c.CONTROLS[kind]
        for kind, row in controls.items()
    )
    excluded = " ".join(evidence["scope"]["excluded"])
    assert (
        "Assertion-helper execution or response" in excluded
        and "both function returns" in excluded
    )
    assert (
        "later metatable or registry requests, closure creation" in excluded
        and "accounting promotion" in excluded
    )


def test_exact_selected_code_partition_record_baseline_and_no_helper_execution(
    receipts,
):
    _, evidence, _, sources = receipts
    points = evidence["body"]["points"]
    required = set(sources["record_conformance"]["executed_rvas"])
    required.update(
        p["rva"]
        for p in points
        if record.END <= int(p["rva"], 16) < 0x2EAE7B
        and not any(a <= int(p["rva"], 16) < b for a, b in full.EXCLUDED[:2])
    )
    assert set(evidence["executed_rvas"]) == required and len(required) == 221
    assert (
        "0x002eae76" in required
        and "0x002eae7b" not in required
        and "0x00379cc2" not in required
    )
    assert "0x002ec307" not in required and "0x002eaf3b" not in required
    assert sum(p["size"] for p in points) == 807
    assert evidence["summary"]["static_sites"] == len(points)
    by_rva = {p["rva"]: p for p in points}
    call = 0x2EAE76
    payload = b"\xe8" + (0x379CC2 - (call + 5)).to_bytes(4, "little", signed=True)
    assert by_rva["0x002eae76"]["size"] == 5
    assert by_rva["0x002eae76"]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert evidence["summary"]["native_instructions"] == sum(
        221 + 4 * v["length"] for v in c.vectors()
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
        changed["vectors"][0]["registry_profile"] = 4
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
def test_strict_nine_source_partition_and_pin_preflight(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["full_factory"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["full_factory"]["schema_version"] += 1
    else:
        changed["allocation"]["analysis_kind"] = "pe_other"
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
    noncanonical = tmp_path / "factory-assertion-prefix.json"
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
