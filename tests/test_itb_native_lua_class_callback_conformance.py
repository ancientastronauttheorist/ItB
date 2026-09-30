"""Finite continuous callback laws; exact x86 replay stays in a subprocess."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_callback_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_callback_conformance.py"


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
    # All receipt vectors are replayed by the gated rebuild. Keep public oracle
    # tests bounded while exercising every tree profile, layout, and transfer.
    vectors = c.vectors()
    selected = []
    for profile in ("empty_source", "all_new", "all_existing", "mixed"):
        candidates = [v for v in vectors if v["profile"] == profile]
        selected.extend(
            (candidates[0], candidates[len(candidates) // 2], candidates[-1])
        )
    selected.extend(vectors[-6:])
    return [(v, f, c._expected(v, f)) for v in selected for f in [c._fixture(v)]]


def test_finite_vector_shapes_and_detachment():
    vectors = c.vectors()
    assert len(vectors) == 1152
    assert len({c._canonical_sha256(v) for v in vectors}) == 1152
    assert {len(v["source_keys"]) for v in vectors} == set(range(8))
    assert {v["frame_alignment"] for v in vectors} == {0, 15}
    assert {v["node_alignment"] for v in vectors} == {0, 7, 31}
    assert {v["buffer_address"] for v in vectors} == {0x13000100, 0x16000100}
    assert {v["old_size"] for v in vectors} == {0, 1, 3}
    assert {v["spare_records"] for v in vectors} == {1, 2}
    assert {tuple(map(tuple, v["transfers"])) for v in vectors} == {
        tuple(map(tuple, pair)) for pair in c.TRANSFER_PAIRS
    }
    assert {v["source_word"] for v in vectors} == {0, 0x12345678, 0xFFFFFFFF}
    assert {tuple(v["destination_refs"]) for v in vectors} == {(17, 19), (117, 119)}
    assert {tuple(v["source_refs"]) for v in vectors} == {(23, 29), (123, 129)}
    pristine = c.vectors()
    vectors[0]["transfers"][0].append("other")
    vectors[0]["source_refs"][0] = 0
    assert c.vectors() == pristine
    assert vectors[1:] == pristine[1:]


def test_fixture_shared_imports_objects_and_external_record(cases):
    layout = c.layout.make_layout()
    for vector, fixture, expected in cases:
        prototype = fixture["prototype"]
        assert fixture["entry"] == prototype["stack"] + 48
        assert fixture["entry"] - 20 > prototype["vector_capacity"]
        assert raw(fixture["pages"], fixture["entry"]) == c.RETURN
        assert raw(fixture["pages"], fixture["entry"] + 4) == fixture["state"]
        for object_address, word, refs in (
            (c.RECEIVER, vector["destination_word"], vector["destination_refs"]),
            (c.SOURCE_OBJECT, vector["source_word"], vector["source_refs"]),
        ):
            assert raw(fixture["pages"], object_address) == word
            for offset, ref in zip((32, 40), refs):
                assert raw(fixture["pages"], object_address + offset) == ref
                assert raw(expected["pages"], object_address + offset) == ref
        for page, payload in layout["pages"].items():
            assert fixture["pages"][page] == expected["pages"][page] == payload
        assert (
            raw(expected["pages"], prototype["vector_end"], 8) == c.SOURCE_OBJECT << 32
        )
        assert raw(expected["pages"], c.RECEIVER + 4) == prototype["vector_begin"]
        assert raw(expected["pages"], c.RECEIVER + 8) == prototype["vector_end"] + 8
        assert raw(expected["pages"], c.RECEIVER + 12) == prototype["vector_capacity"]
        for address in range(prototype["vector_begin"], prototype["vector_end"]):
            assert raw(expected["pages"], address, 1) == raw(
                fixture["pages"], address, 1
            )


def test_exact_callback_gprs_frame_record_and_ancestor_laws(cases):
    for vector, fixture, expected in cases:
        stack = fixture["prototype"]["stack"]
        frame = fixture["entry"] - 4
        regs = expected["registers"]
        assert expected["endpoint"] == c.RETURN
        assert regs["esp"] == fixture["entry"] + 4
        assert regs["eax"] == 0 and regs["ecx"] == vector["cookie"]
        assert expected["flags"] == 0x44
        assert regs["edx"] == expected["children"][-1]["result"]["registers"]["edx"]
        for register in ("ebx", "esi", "edi", "ebp"):
            assert regs[register] == fixture["registers"][register]
        for offset, value in {
            8: fixture["registers"]["edi"],
            12: fixture["registers"]["esi"],
            16: c.BASE + 0x2EC219,
            24: c.RECEIVER,
            28: 0,
            32: c.SOURCE_OBJECT,
            36: vector["cookie"] ^ frame,
            44: fixture["registers"]["ebp"],
            48: c.RETURN,
            52: fixture["state"],
        }.items():
            assert raw(expected["pages"], stack + offset) == value
        for page in (c.STACK, c.STACK + 4096):
            offset = max(0, min(4096, fixture["entry"] - page))
            assert expected["pages"][page][offset:] == fixture["pages"][page][offset:]
        assert raw(expected["pages"], 0) == vector["previous_seh"]
        assert raw(expected["pages"], c.spare.returned.COOKIE) == vector["cookie"]


def test_api_cleanup_and_child_entry_pages_come_from_running_parent(cases):
    continuations = (0x2EC160, 0x2EC184, 0x2EC1BD, 0x2EC1E0, 0x2EC203)
    for _, fixture, expected in cases:
        assert [(ch["kind"], ch["index"]) for ch in expected["children"]] == [
            ("marker", 0),
            ("marker", 1),
            ("class", 0),
            ("table", 0),
            ("table", 1),
        ]
        pages, cursor = fixture["pages"], 0
        for child, continuation in zip(expected["children"], continuations):
            child_fixture, result = child["fixture"], child["result"]
            entry = child_fixture["registers"]["esp"]
            while cursor < len(expected["events"]):
                event = expected["events"][cursor]
                cursor += 1
                if event["access"] == "write":
                    pages = change(
                        pages, event["address"], event["value"], event["width"]
                    )
                if event == dict(
                    access="write", address=entry, width=4, value=c.BASE + continuation
                ):
                    break
            else:
                pytest.fail("missing joined child call frame")
            assert pages == child_fixture["pages"]
            assert result["endpoint"] == c.BASE + continuation
            assert result["registers"]["esp"] == entry + (
                8 if child["kind"] == "class" else 4
            )
            assert (
                expected["events"][cursor : cursor + len(result["events"])]
                == result["events"]
            )
            if child["kind"] != "class":
                assert all(
                    result["pages"][p] == payload
                    for p, payload in pages.items()
                    if p not in (c.STACK, c.STACK + 4096)
                )
        direct = [call for call in expected["calls"] if call["group"] == "direct"]
        assert [call["api"] for call in direct] == ["lua_touserdata"] * 2 + [
            "lua_rawgeti"
        ] * 4
        stack = fixture["prototype"]["stack"]
        assert [call["entry_esp"] for call in direct] == [
            stack - 4,
            stack - 4,
            stack - 8,
            stack - 20,
            stack - 32,
            stack - 44,
        ]
        assert all(
            call["arguments"][0] == fixture["state"] for call in expected["calls"]
        )
        assert all(
            call["target"] == c.layout.TARGETS[call["api"]]
            for call in expected["calls"]
        )


def test_model_tree_endword_and_continuous_lua_token_effects(cases):
    for vector, fixture, expected in cases:
        logical = fixture["logical"]
        child = next(ch for ch in expected["children"] if ch["kind"] == "class")
        assert (
            child["fixture"]["transfer"]["destination"]
            == logical["class_operation"]["destination"]
        )
        assert (
            child["fixture"]["transfer"]["copies"]
            == logical["class_operation"]["copies"]
        )
        assert raw(expected["pages"], c.RECEIVER) == vector["source_word"]
        assert logical["return_count"] == 0 and logical["lua_stack_delta"] == 4
        assert logical["class_operation"]["vector"]["records"][-1] == [
            0,
            c.SOURCE_OBJECT,
        ]
        lua = c._Lua(vector)
        for call in expected["calls"]:
            lua.apply(call)
        assert lua.trace == logical["calls"]
        assert (
            lua.stack
            == logical["final_lua_stack"]
            == [
                ("argument", 0),
                ("registry", vector["destination_refs"][0]),
                ("registry", vector["source_refs"][0]),
                ("registry", vector["destination_refs"][1]),
                ("registry", vector["source_refs"][1]),
            ]
        )
        assert (
            lua.assignments
            == logical["requested_assignments"]
            == [
                [i for i, kind in enumerate(kinds) if kind == "other"]
                for kinds in vector["transfers"]
            ]
        )
        assert c._model_pages(vector, fixture, expected) == expected["pages"]


@pytest.mark.parametrize(
    "kind",
    [
        "saved_edi",
        "saved_esi",
        "cookie_return",
        "receiver_local",
        "record_first",
        "record_second",
        "cookie_local",
        "saved_ebp",
        "ancestor",
        "source_ref",
        "destination_ref",
        "finalword",
        "vector_record",
        "tree_payload",
        "tree_link",
    ],
)
def test_independent_model_rejects_forged_parent_and_joined_child_memory(cases, kind):
    vector, fixture, expected = next(
        case for case in reversed(cases) if case[0]["source_keys"]
    )
    stack = fixture["prototype"]["stack"]
    child = next(ch for ch in expected["children"] if ch["kind"] == "class")
    node = child["result"]["insertions"][-1]["destination_address"]
    address = {
        "saved_edi": stack + 8,
        "saved_esi": stack + 12,
        "cookie_return": stack + 16,
        "receiver_local": stack + 24,
        "record_first": stack + 28,
        "record_second": stack + 32,
        "cookie_local": stack + 36,
        "saved_ebp": stack + 44,
        "ancestor": fixture["entry"] + 8,
        "source_ref": c.SOURCE_OBJECT + 40,
        "destination_ref": c.RECEIVER + 32,
        "finalword": c.RECEIVER,
        "vector_record": fixture["prototype"]["vector_end"],
        "tree_payload": node + 20,
        "tree_link": node + 4,
    }[kind]
    forged = copy.deepcopy(expected)
    forged["pages"] = change(
        expected["pages"], address, raw(expected["pages"], address) ^ 1
    )
    if kind in ("tree_payload", "tree_link"):
        forged_child = next(ch for ch in forged["children"] if ch["kind"] == "class")
        forged_child["result"]["pages"] = change(
            forged_child["result"]["pages"],
            address,
            raw(forged_child["result"]["pages"], address) ^ 1,
        )
    rebuilt = c._model_pages(vector, fixture, forged)
    assert rebuilt != forged["pages"]
    assert raw(rebuilt, address) == raw(expected["pages"], address)


def test_expected_is_deterministic_and_preserves_inputs(cases):
    vector, fixture, expected = cases[-1]
    before = copy.deepcopy((vector, fixture))
    assert c._expected(vector, fixture) == expected
    assert (vector, fixture) == before


@pytest.mark.parametrize("field", ["destination", "copies"])
def test_independent_model_rejects_forged_class_outputs(cases, field):
    vector, fixture, expected = cases[-1]
    forged = copy.deepcopy(expected)
    child = next(ch for ch in forged["children"] if ch["kind"] == "class")
    if field == "destination":
        child["fixture"]["transfer"][field]["payloads"][0] ^= 1
    else:
        child["fixture"]["transfer"][field][-1]["payload"] ^= 1
    with pytest.raises(
        RuntimeError, match="independent callback class transfer differs"
    ):
        c._model_pages(vector, fixture, forged)


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (PREFIX + "native_lua_class_callback_conformance.json")
    if not path.exists() or c.SEALED_SHA256 in ("UNSEALED", "PENDING"):
        pytest.skip("awaiting reviewed continuous callback seal")
    evidence = json.loads(path.read_text())
    paths, sources = {}, {}
    for key, (kind, digest) in c.SOURCE_PINS.items():
        suffix = "program_facts" if key == "program_facts" else kind.removeprefix("pe_")
        source = PROGRAMS / (PREFIX + suffix + ".json")
        value = json.loads(source.read_text())
        assert c._canonical_sha256(value) == digest
        paths[key], sources[key] = source, value
    return path, evidence, paths, sources


def test_receipt_encoding_scope_coverage_and_controls(receipts):
    path, evidence, _, sources = receipts
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256
    assert c.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    result = c.validate_structure(evidence, sources)
    assert result["status"] == "structurally_verified"
    assert result["evidence_sha256"] == c.SEALED_SHA256
    summary = evidence["summary"]
    for key, value in dict(
        cases=1152,
        callback_bytes=269,
        retained_lua_values=4,
        result_count=0,
        opaque_native_instructions=0,
        accounting_promotions=0,
    ).items():
        assert summary[key] == value
    assert summary["static_sites"] == len(evidence["body"]["points"])
    assert summary["executed_sites"] == len(evidence["executed_rvas"])
    assert summary["native_instructions"] > summary["executed_sites"]
    executed = set(evidence["executed_rvas"])
    unreachable = {"0x002eb1c5", "0x002eb1c8", "0x002eb1ca"}
    assert set(sources["class_spare"]["executed_rvas"]) - executed == unreachable
    assert not unreachable.intersection(executed)
    assert set(evidence["body"]["unreachable_class_argument_sites"]) == unreachable
    assert set(sources["table"]["executed_rvas"]) <= executed
    assert not any(
        a <= int(pc, 16) < b
        for pc in executed
        for a, b in ((0x2EC140, 0x2EC154), (0x2EC164, 0x2EC178), (0x2EC188, 0x2EC19E))
    )
    controls = {row["kind"]: row for row in evidence["negative_controls"]}
    assert set(controls) == {
        "ancestor",
        "record",
        "word",
        "reference",
        "literal",
        "iat",
        "vector",
        "result",
        "lua_prefix",
        "cookie",
    }
    assert all(row["rejected"] for row in controls.values())
    assert controls["cookie"]["endpoint"] == "0x003574d5"
    assert evidence["scope"]["continuous_machine"] is True
    excluded = " ".join(evidence["scope"]["excluded"])
    assert "Real Lua VM" in excluded and "destination-table effects" in excluded
    assert "allocation growth" in excluded and "No accounting promotion" in excluded


@pytest.mark.parametrize("mutation", ["summary", "vectors", "controls", "kind"])
def test_modified_receipt_rejected(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    if mutation == "summary":
        changed["summary"]["api_calls"] += 1
    elif mutation == "vectors":
        changed["vectors"][0]["source_word"] ^= 1
    elif mutation == "controls":
        changed["negative_controls"][0]["rejected"] = False
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        c.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ["missing", "extra", "identity"])
def test_source_preflight_rejects_partition_and_pin_changes(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["factory_chain"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    else:
        changed["marker"]["schema_version"] += 1
    with pytest.raises(RuntimeError):
        c._preflight(changed)
    with pytest.raises(RuntimeError):
        c.validate_structure(evidence, changed)


def command_for(command, paths):
    argv = [sys.executable, str(CLI), command]
    for key, path in paths.items():
        argv += ["--" + key.replace("_", "-"), str(path)]
    return argv


def test_cli_verify_structure_and_reject_noncanonical_encoding(receipts, tmp_path):
    path, evidence, paths, sources = receipts
    command = command_for("verify-structure", paths)
    result = subprocess.run(
        command + ["--evidence", str(path)], cwd=ROOT, capture_output=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b""
    assert json.loads(result.stdout) == c.validate_structure(evidence, sources)
    noncanonical = tmp_path / "callback.json"
    noncanonical.write_text(json.dumps(evidence), encoding="utf-8")
    result = subprocess.run(
        command + ["--evidence", str(noncanonical)],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 1 and result.stdout == b""
    assert b"not deterministically encoded" in result.stderr


def test_exact_native_full_rebuild_in_isolated_subprocess(receipts):
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
