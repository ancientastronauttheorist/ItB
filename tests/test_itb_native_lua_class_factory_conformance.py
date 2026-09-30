"""Complete factory laws with independent final pages and Lua identities."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_factory_conformance as c
from src.observatory import native_lua_class_factory_semantics as model

factory, record = c.factory, c.record
ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_factory_conformance.py"
CANONICAL = "d8b36d30d732467edb54396ba22a3cd2a167dca15780f3020df18256c617dbcf"
RAW = "29dc4376f28a537d0052c2dbd39c90328e8213fc029932fe3c16ee9ec1df291a"
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
    0x2EAE90,
    0x2EAE99,
    0x2EAEA2,
    0x2EAEDA,
    0x2EAEF2,
    0x2EAEFE,
    0x2EAF07,
    0x2EAF0F,
    0x2EAF1B,
    0x2EAF27,
    0x2EAF30,
    0x2EAF3B,
    0x2EC30B,
    0x2EC314,
    0x2EC320,
    0x2EC32E,
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


def logical_for(fixture, vector):
    return model.apply(
        state=fixture["state"],
        first_pointer=fixture["first_pointer"],
        second_pointer=fixture["second_pointer"],
        userdata=fixture["userdata"],
        name_bytes=factory._name(vector),
        **fixture["spec"],
    )


@pytest.fixture(scope="module")
def cases():
    bases = [
        v
        for v in factory.vectors()
        if v["name_alignment"] == {"ascii": 0, "low": 7, "high": 4095}[v["pattern"]]
        and v["equal_pointers"] == bool((v["length"] + v["profile"]) % 2)
    ]
    result = []
    geometries = [
        (bias, alignment) for bias in (0x100, 0xFFF) for alignment in (0, 7, 15, 31)
    ]
    for index, base in enumerate(bases):
        bias, alignment = geometries[index % 8]
        vector = dict(
            base,
            record_bias=bias,
            record_alignment=alignment,
            registry_profile=index % 3,
        )
        fixture = c._extend_fixture(vector, factory._fixture(base))
        original = factory._expected(base, fixture)
        before = record._extend_expected(c._record_vector(vector), fixture, original)
        result.append(
            (
                vector,
                fixture,
                original,
                before,
                c._extend_expected(vector, fixture, original),
            )
        )
    assert len(result) == 36
    return result


def independent_pages_and_api_frames(fixture, before, logical):
    # Closed physical call groups retain cdecl arguments until documented group
    # cleanups. The first zero was pushed by the native initializer resume.
    pages = before["pages"]
    inner, outer = before["registers"]["ebp"], fixture["entry"] - 4
    stack = inner - 36
    frames = []
    cleanups = {2: 28, 5: 28, 10: 40, 13: 28, 21: 64, 22: 8}
    for index, (call, continuation) in enumerate(
        zip(logical["calls"][7:], CONTINUATIONS)
    ):
        if index == 23:
            stack = outer - 36  # Initializer RET consumes its two arguments.
        arguments = call["arguments"][:-1] if index == 0 else call["arguments"]
        for word in reversed(arguments):
            stack -= 4
            pages = change(pages, stack, word & 0xFFFFFFFF)
        stack -= 4
        pages = change(pages, stack, c.BASE + continuation)
        frames.append((stack, inner if index < 23 else outer))
        stack += 4
        stack += cleanups.get(index, 0)
    assert stack == outer - 72
    final_fields = dict(logical["final_fields"])
    final_fields[52] = fixture["record"]
    assert set(final_fields) == set(range(0, 72, 4))
    for offset, value in final_fields.items():
        pages = change(pages, fixture["userdata"] + offset, value)
    pages = change(pages, 0, raw(fixture["pages"], 0))
    return pages, frames


def arithmetic_flags(left, right):
    total, result = left + right, (left + right) & 0xFFFFFFFF
    flags = int(total > 0xFFFFFFFF)
    flags |= 4 if (result & 255).bit_count() % 2 == 0 else 0
    flags |= 16 if (left & 15) + (right & 15) > 15 else 0
    flags |= 64 if result == 0 else 0
    flags |= 128 if result & 0x80000000 else 0
    signed_left = left if left < 0x80000000 else left - 0x100000000
    signed_right = right if right < 0x80000000 else right - 0x100000000
    flags |= 2048 if not -0x80000000 <= signed_left + signed_right <= 0x7FFFFFFF else 0
    return flags


def test_full_vector_corpus_registry_profiles_and_record_geometries():
    vectors = c.vectors()
    assert len(vectors) == 5184
    assert len({c._canonical_sha256(v) for v in vectors}) == 5184
    assert {v["registry_profile"] for v in vectors} == {0, 1, 2}
    assert {(v["record_bias"], v["record_alignment"]) for v in vectors} == {
        (bias, alignment) for bias in (0x100, 0xFFF) for alignment in (0, 7, 15, 31)
    }
    assert {
        len([v for v in vectors if v["registry_profile"] == profile])
        for profile in range(3)
    } == {1728}
    assert {v["length"] for v in vectors} == {0, 1, 2, 15, 16, 255}


def test_fixture_all_bindings_literals_and_registry_context_geometries(cases):
    assert {v["registry_profile"] for v, *_ in cases} == {0, 1, 2}
    for vector, fixture, _, _, _ in cases:
        profile, spec = vector["registry_profile"], fixture["spec"]
        assert spec == dict(
            context_pointer=0x17000100 + 7 * profile,
            context_word=(0, 0x12345678, 0xFFFFFFFF)[profile],
            context_guard=(0, 1, 0xFFFFFFFF)[profile],
            metatable_reference=31 + 100 * profile,
            graph_pointer=0x18000100 + 7 * profile,
            id_map_pointer=0x19000100 + 31 * profile,
            references=[17 + 100 * profile, 19 + 100 * profile, 23 + 100 * profile],
        )
        for api, slot in c.ALL_SLOTS.items():
            assert raw(fixture["pages"], c.BASE + slot) == c.ALL_TARGETS[api]
        assert len(set(c.ALL_TARGETS.values())) == len(c.ALL_TARGETS)
        assert factory.IMPORT not in c.ALL_TARGETS.values()
        for address, text in c.LITERALS.items():
            assert (
                bytes(
                    raw(fixture["pages"], address + i, 1) for i in range(len(text) + 1)
                )
                == text.encode() + b"\0"
            )
        for offset, key in (
            (8, "context_word"),
            (12, "context_guard"),
            (16, "metatable_reference"),
        ):
            assert raw(fixture["pages"], spec["context_pointer"] + offset) == spec[key]


def test_independent_entire_final_pages_eighteen_fields_and_deferred_api_frames(cases):
    for vector, fixture, _, before, expected in cases:
        logical = logical_for(fixture, vector)
        pages, frames = independent_pages_and_api_frames(fixture, before, logical)
        assert expected["pages"] == pages
        assert expected["logical"]["factory"] == logical
        assert expected["logical"]["record"] == before["logical"]["record"]
        assert raw(pages, fixture["userdata"] + 52) == fixture["record"]
        assert len(expected["calls"]) == 34 and len(expected["heap_calls"]) == 1
        assert expected["heap_calls"] == before["heap_calls"]
        for call, requested in zip(expected["calls"], logical["calls"]):
            assert (call["api"], call["arguments"], call["response"]["eax"]) == (
                requested["api"],
                [arg & 0xFFFFFFFF for arg in requested["arguments"]],
                requested["result"],
            )
            assert call["target"] == c.ALL_TARGETS[call["api"]]
        for call, (entry, ebp), continuation in zip(
            expected["calls"][7:], frames, CONTINUATIONS
        ):
            assert call["entry_esp"] == call["entry_registers"]["esp"] == entry
            assert call["entry_registers"]["ebp"] == ebp
            assert call["continuation"] == c.BASE + continuation
        for page in (
            0x17000000,
            0x18000000,
            0x19000000,
            factory.FIRST,
            factory.FIRST + 4096,
            factory.SECOND,
        ):
            assert pages[page] == fixture["pages"][page]


def test_actual_complete_return_original_gprs_fs_restoration_add_flags_and_ancestors(
    cases,
):
    for vector, fixture, _, before, expected in cases:
        outer, inner = fixture["entry"] - 4, before["registers"]["ebp"]
        registers = dict(
            fixture["registers"],
            eax=1,
            esp=fixture["entry"] + 4,
            ecx=raw(fixture["pages"], factory.COOKIE) ^ outer,
            edx=0xB1000021 + 0x100 * vector["profile"],
        )
        assert expected["registers"] == registers
        assert expected["flags"] == arithmetic_flags(outer - 72, 36)
        assert not expected["flags"] & 0x400
        assert raw(expected["pages"], 0) == raw(fixture["pages"], 0)
        fs_writes = [
            e["value"]
            for e in expected["events"]
            if e["access"] == "write" and e["address"] == 0
        ]
        assert fs_writes == [
            outer - 12,
            inner - 12,
            outer - 12,
            raw(fixture["pages"], 0),
        ]
        assert raw(expected["pages"], fixture["entry"]) == c.RETURN
        for page in (factory.STACK, factory.STACK + 4096):
            offset = max(0, min(4096, fixture["entry"] - page))
            assert expected["pages"][page][offset:] == fixture["pages"][page][offset:]
        assert (
            raw(expected["pages"], fixture["userdata"] + 16)
            == fixture["second_pointer"]
        )


def test_runtime_lua_observer_matches_all_independent_before_after_requests(cases):
    for vector, fixture, _, _, expected in cases:
        logical = logical_for(fixture, vector)
        lua = c._Lua(vector, fixture)
        for call, wanted in zip(expected["calls"], logical["calls"]):
            assert lua.stack == wanted["before"]
            assert lua.apply(call["api"], call["arguments"]) == wanted["result"]
            assert lua.stack == wanted["after"]
        assert lua.result() == expected["lua_result"]
        assert lua.result()["calls"] == normalized(
            [
                {
                    key: call[key]
                    for key in ("api", "arguments", "result", "before", "after")
                }
                for call in logical["calls"]
            ]
        )
        assert lua.registry == {
            r: value
            for r, value in zip(
                fixture["spec"]["references"],
                [("table", 1), ("table", 2), ("userdata", fixture["userdata"])],
            )
        }
        assert lua.metatables == [
            dict(
                userdata=fixture["userdata"],
                reference=fixture["spec"]["metatable_reference"],
            )
        ]
        assert lua.assignments == [
            dict(name_pointer=fixture["second_pointer"], userdata=fixture["userdata"])
        ]
        assert lua.stack == [
            ("argument", 1),
            ("closure", c.BASE + 0x2EC110, ("userdata", fixture["userdata"])),
        ]
        assert logical["result_count"] == 1 and logical["closure"]["upvalues"] == [
            ("userdata", fixture["userdata"])
        ]
        assert not any(call["api"] == "luaL_unref" for call in expected["calls"])


@pytest.mark.parametrize(
    "mutation,message",
    [
        ("state", "factory Lua state identity differs"),
        ("argument", "factory Lua argument identity differs"),
        ("context", "factory Lua context identity differs"),
        ("metatable", "factory Lua metatable identity differs"),
        ("global", "factory Lua global assignment identity differs"),
        ("closure", "factory Lua closure identity differs"),
        ("raw_reference", "factory Lua raw lookup differs"),
    ],
)
def test_runtime_observer_rejects_wrong_identities_at_concrete_requests(
    cases, mutation, message
):
    vector, fixture, _, _, expected = cases[-1]
    lua = c._Lua(vector, fixture)
    target = {
        "state": 0,
        "argument": 1,
        "context": 16,
        "metatable": 19,
        "global": 32,
        "closure": 33,
        "raw_reference": 18,
    }[mutation]
    for call in expected["calls"][:target]:
        lua.apply(call["api"], call["arguments"])
    call = expected["calls"][target]
    arguments = list(call["arguments"])
    if mutation == "state":
        arguments[0] ^= 1
    elif mutation == "argument":
        lua.stack[0] = ("argument", 2)
    elif mutation == "context":
        lua.stack[-1] = ("userdata", fixture["userdata"])
    elif mutation == "metatable":
        lua.stack[-1] = ("metatable", fixture["spec"]["metatable_reference"] ^ 1)
    elif mutation == "global":
        lua.stack[-2] = ("name_pointer", fixture["second_pointer"] ^ 1)
    elif mutation == "closure":
        lua.stack[-1] = ("userdata", fixture["userdata"] ^ 1)
    else:
        arguments[2] ^= 1
    with pytest.raises(RuntimeError, match=message):
        lua.apply(call["api"], arguments)


def test_context_guard_premise_blocks_both_logical_and_native_frame_oracles(cases):
    vector, fixture, original, _, _ = cases[-1]
    spec = dict(fixture["spec"], context_guard=0xFFFFFFFE)
    with pytest.raises(model.FactoryError, match="excluded assertion arm"):
        model.apply(
            state=fixture["state"],
            first_pointer=fixture["first_pointer"],
            second_pointer=fixture["second_pointer"],
            userdata=fixture["userdata"],
            name_bytes=factory._name(vector),
            **spec,
        )
    forged = copy.deepcopy(fixture)
    forged["pages"] = change(
        forged["pages"], fixture["spec"]["context_pointer"] + 12, 0xFFFFFFFE
    )
    original_forged = factory._expected(
        record._base_vector(c._record_vector(vector)), forged
    )
    with pytest.raises(
        RuntimeError, match="factory full context guard premise differs"
    ):
        c._extend_expected(vector, forged, original_forged)


@pytest.mark.parametrize("offset", range(0, 72, 4))
def test_independent_full_userdata_page_model_rejects_forged_dword(cases, offset):
    vector, fixture, _, before, expected = cases[-1]
    address = fixture["userdata"] + offset
    forged = change(expected["pages"], address, raw(expected["pages"], address) ^ 1)
    pages, _ = independent_pages_and_api_frames(
        fixture, before, logical_for(fixture, vector)
    )
    assert pages == expected["pages"] != forged


@pytest.mark.parametrize(
    "kind",
    [
        "context",
        "inner_frame",
        "outer_frame",
        "cdecl_return",
        "fs",
        "ancestor",
        "record",
    ],
)
def test_independent_final_pages_reject_forged_context_frames_and_record(cases, kind):
    vector, fixture, _, before, expected = cases[-1]
    outer, inner = fixture["entry"] - 4, before["registers"]["ebp"]
    address = {
        "context": fixture["spec"]["context_pointer"] + 8,
        "inner_frame": inner - 24,
        "outer_frame": outer - 36,
        "cdecl_return": outer - 76,
        "fs": 0,
        "ancestor": fixture["entry"] + 8,
        "record": fixture["record"],
    }[kind]
    forged = change(expected["pages"], address, raw(expected["pages"], address) ^ 1)
    pages, _ = independent_pages_and_api_frames(
        fixture, before, logical_for(fixture, vector)
    )
    assert pages == expected["pages"] != forged


def test_full_oracle_deterministic_and_preserves_live_inputs(cases):
    vector, fixture, original, _, expected = cases[-1]
    before = copy.deepcopy((vector, fixture, original))
    assert c._extend_expected(vector, fixture, original) == expected
    assert (vector, fixture, original) == before


@pytest.mark.parametrize("value", [True, False, -1, 3, 0.0, "1", None])
def test_registry_profile_strict_finite_guard(value):
    vector = dict(c.vectors()[0], registry_profile=value)
    with pytest.raises(RuntimeError):
        c._record_vector(vector)


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (PREFIX + "native_lua_class_factory_conformance.json")
    if not path.exists() or c.SEALED_SHA256 in ("UNSEALED", "PENDING"):
        pytest.skip("awaiting reviewed complete native factory seal")
    evidence = json.loads(path.read_text())
    paths, sources = {}, {}
    for key, (kind, digest) in c.SOURCE_PINS.items():
        suffix = "program_facts" if key == "program_facts" else kind.removeprefix("pe_")
        source_path = PROGRAMS / (PREFIX + suffix + ".json")
        sources[key] = json.loads(source_path.read_text())
        assert c._canonical_sha256(sources[key]) == digest
        paths[key] = source_path
    return path, evidence, paths, sources


def test_receipt_seal_exact_normal_coverage_thirty_eight_controls_and_conditional_scope(
    receipts,
):
    path, evidence, _, sources = receipts
    assert len(c.SOURCE_PINS) == 8
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    for key, value in dict(
        cases=5184,
        static_sites=365,
        executed_sites=302,
        instruction_bytes=1089,
        native_instructions=2564352,
        supplied_api_calls=176256,
        heap_calls=5184,
        controls=38,
        initializer_instructions=813888,
        self_linked_helper_instructions=82944,
        allocation_native_instructions=176256,
        factory_tail_instructions=124416,
        result_count=1,
        closure_upvalues=1,
        opaque_native_instructions=0,
        accounting_promotions=0,
    ).items():
        assert evidence["summary"][key] == value
    points = evidence["body"]["points"]
    required = set(sources["record_conformance"]["executed_rvas"])
    required.update(
        p["rva"]
        for p in points
        if factory.END <= int(p["rva"], 16) < factory.START + 296
    )
    required.update(
        p["rva"]
        for p in points
        if record.END <= int(p["rva"], 16) < c.parent.START + 612
        and not any(a <= int(p["rva"], 16) < b for a, b in c.EXCLUDED)
    )
    assert set(evidence["executed_rvas"]) == required and len(required) == 302
    assert f"0x{c.RETURN:08x}" not in required
    initializer = {
        p["rva"]
        for p in points
        if c.parent.START <= int(p["rva"], 16) < c.parent.START + 612
    }
    assert len(initializer.intersection(required)) == 157
    # Twenty-four unref/assert body instructions and four skipped unref guards
    # remain outside this normal initializer corpus.
    assert len(initializer - required) == 28
    assert not any(a <= int(pc, 16) < b for pc in required for a, b in c.EXCLUDED)
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    assert len(controls) == len(evidence["negative_controls"]) == 38
    assert set(controls) == set(c.CONTROLS)
    assert {
        "context_guard",
        "return_count",
        "lua_identity",
        "closure_identity",
        "stored_record",
    } <= set(controls)
    assert all(
        row["rejected"] and row["reason"] == c.CONTROLS[kind]
        for kind, row in controls.items()
    )
    assert evidence["scope"]["continuous_machine"] is True
    assert (
        "HeapAlloc" in evidence["scope"]["supplied_apis"]
        and "luaL_unref" not in evidence["scope"]["supplied_apis"]
    )
    excluded = " ".join(evidence["scope"]["excluded"])
    assert (
        "Actual imported DLL or Lua VM" in excluded
        and "second name pointer contents" in excluded
    )
    assert (
        "Invocation of returned closure" in excluded
        and "accounting promotion" in excluded
    )


@pytest.mark.parametrize("mutation", ["summary", "vector", "control", "body", "kind"])
def test_modified_receipt_rejected(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    if mutation == "summary":
        changed["summary"]["result_count"] = 2
    elif mutation == "vector":
        changed["vectors"][0]["registry_profile"] = 2
    elif mutation == "control":
        changed["negative_controls"][0]["rejected"] = False
    elif mutation == "body":
        changed["body"]["ranges"][0]["sha256"] = "0" * 64
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ["missing", "extra", "pin", "kind"])
def test_source_partition_and_pin_preflight(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["record_conformance"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    elif mutation == "pin":
        changed["record_conformance"]["schema_version"] += 1
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
        timeout=1200,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == path.read_bytes()
