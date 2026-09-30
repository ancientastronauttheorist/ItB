"""Continuous growth callback laws, with native execution isolated in a child."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_callback_growth_conformance as g

c = g.joined
ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CLI = ROOT / "scripts/itb_native_lua_class_callback_growth_conformance.py"
CANONICAL = "59a2123f649633045e35102d2900cf936048f7252095152a27cee6774d60d443"
RAW = "b0fb268b5e364c807fd3b62ae5f6716aa137665ba0c24cfd99a01d8d4cd7c723"


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


def class_child(expected):
    return next(child for child in expected["children"] if child["kind"] == "class")


@pytest.fixture(scope="module")
def cases():
    selected = []
    for family, module in g.FAMILIES.items():
        vectors = [v for v in g.vectors() if v["class_family"] == family]
        for profile in ("empty_source", "all_new", "all_existing", "mixed"):
            profile_vectors = [v for v in vectors if v["profile"] == profile]
            selected.extend(
                (module, v)
                for v in (
                    profile_vectors[0],
                    next(
                        v
                        for v in reversed(profile_vectors)
                        if v["node_alignment"] == 7 and v["frame_alignment"] == 0
                    ),
                    profile_vectors[-1],
                )
            )
        selected.extend((module, v) for v in vectors[-6:])
    return [
        (module, v, fixture, c._expected(v, fixture, class_module=module))
        for module, v in selected
        for fixture in [c._fixture(v, class_module=module)]
    ]


def test_vector_families_geometry_transfer_shapes_and_detachment():
    vectors = g.vectors()
    assert len(vectors) == 2304
    assert len({g._canonical_sha256(v) for v in vectors}) == 2304
    assert g.FAMILIES == {"first_null": g.empty, "old_full": g.old}
    for family in g.FAMILIES:
        selected = [v for v in vectors if v["class_family"] == family]
        assert len(selected) == 1152
        assert {v["vector_alignment"] for v in selected} == {0, 7, 31}
        assert {v["frame_alignment"] for v in selected} == {0, 15}
        assert {v["node_alignment"] for v in selected} == {0, 7, 31}
        assert {len(v["source_keys"]) for v in selected} == set(range(8))
        assert {v["old_size"] for v in selected} == (
            {0} if family == "first_null" else set(range(4))
        )
        assert {tuple(map(tuple, v["transfers"])) for v in selected} == {
            tuple(map(tuple, pair)) for pair in c.TRANSFER_PAIRS
        }
        assert all(
            not {"buffer_address", "spare_records"}.intersection(v) for v in selected
        )
    pristine = g.vectors()
    vectors[0]["transfers"][0].append("other")
    vectors[0]["destination_refs"][0] = 0
    assert g.vectors() == pristine and vectors[1:] == pristine[1:]


def test_initial_actual_old_records_and_shared_heap_free_binding(cases):
    layout = c.layout.make_layout()
    for module, vector, fixture, expected in cases:
        prototype, pages = fixture["prototype"], fixture["pages"]
        assert fixture["entry"] == prototype["stack"] + 48
        assert fixture["entry"] - 20 > prototype["vector_capacity"]
        begin, end, capacity = (
            raw(pages, c.RECEIVER + offset) for offset in (4, 8, 12)
        )
        size = vector["old_size"]
        if module is g.empty:
            assert (begin, end, capacity) == (0, 0, 0)
        else:
            assert begin == prototype["old_begin"]
            assert end == capacity == begin + 8 * size
            assert raw(pages, module.growth.FREE_IAT) == c.layout.HEAP_TARGET
            assert c.layout.HEAP_TARGET not in c.layout.TARGETS.values()
        original_records = [
            [raw(pages, begin + 8 * i + 4 * j) for j in range(2)] for i in range(size)
        ]
        logical = fixture["logical"]["class_operation"]
        assert logical["grew"] is True and logical["argument_kind"] == "external"
        assert logical["vector"] == dict(
            records=original_records + [[0, c.SOURCE_OBJECT]], capacity=size + 1
        )
        for name, slot in c.layout.SLOTS.items():
            assert raw(pages, c.BASE + slot) == c.layout.TARGETS[name]
        assert raw(pages, c.BASE + c.layout.HEAP_SLOT) == c.layout.HEAP_TARGET
        for page, payload in layout["pages"].items():
            wanted = payload
            if module is g.old and page == module.growth.FREE_IAT & ~4095:
                wanted = change(
                    {page: wanted}, module.growth.FREE_IAT, c.layout.HEAP_TARGET
                )[page]
            assert pages[page] == expected["pages"][page] == wanted


def test_all_old_copy_append_words_fields_source_and_return_laws(cases):
    for module, vector, fixture, expected in cases:
        prototype, pages = fixture["prototype"], expected["pages"]
        logical = fixture["logical"]["class_operation"]
        begin, stack = prototype["vector_begin"], prototype["stack"]
        for i, record in enumerate(logical["vector"]["records"]):
            assert [raw(pages, begin + 8 * i + 4 * j) for j in range(2)] == record
        for offset, value in (
            (4, begin),
            (8, begin + 8 * (vector["old_size"] + 1)),
            (12, begin + 8 * logical["vector"]["capacity"]),
        ):
            assert raw(pages, c.RECEIVER + offset) == value
        if module is g.old:
            assert pages[module.growth.OLD] == fixture["pages"][module.growth.OLD]
        assert raw(pages, stack + 28, 8) == c.SOURCE_OBJECT << 32
        assert raw(pages, c.RECEIVER) == vector["source_word"]
        assert (
            pages[c.SOURCE_OBJECT & ~4095] == fixture["pages"][c.SOURCE_OBJECT & ~4095]
        )
        for page in {address & ~4095 for address in prototype["source_addresses"]}:
            assert pages[page] == fixture["pages"][page]
        for object_address, refs in (
            (c.RECEIVER, vector["destination_refs"]),
            (c.SOURCE_OBJECT, vector["source_refs"]),
        ):
            for offset, reference in zip((32, 40), refs):
                assert raw(pages, object_address + offset) == reference
        for page in (c.STACK, c.STACK + 4096):
            offset = max(0, min(4096, fixture["entry"] - page))
            assert pages[page][offset:] == fixture["pages"][page][offset:]
        regs = expected["registers"]
        assert expected["endpoint"] == c.RETURN and regs["esp"] == fixture["entry"] + 4
        assert regs["eax"] == 0 and regs["ecx"] == vector["cookie"]
        assert expected["flags"] == 0x44
        for register in ("ebx", "esi", "edi", "ebp"):
            assert regs[register] == fixture["registers"][register]
        assert raw(pages, 0) == vector["previous_seh"]


def test_current_child_pages_and_exact_growth_heap_frames_cleanup(cases):
    continuations = (0x2EC160, 0x2EC184, 0x2EC1BD, 0x2EC1E0, 0x2EC203)
    for module, vector, fixture, expected in cases:
        pages, cursor = fixture["pages"], 0
        for child, continuation in zip(expected["children"], continuations):
            entry = child["fixture"]["registers"]["esp"]
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
                pytest.fail("missing joined child call")
            assert pages == child["fixture"]["pages"]
            assert child["result"]["endpoint"] == c.BASE + continuation
            assert child["result"]["registers"]["esp"] == entry + (
                8 if child["kind"] == "class" else 4
            )
            assert (
                expected["events"][cursor : cursor + len(child["result"]["events"])]
                == child["result"]["events"]
            )
        child = class_child(expected)
        assert child["fixture"]["registers"]["esp"] == fixture["prototype"]["stack"]
        for register in ("ebx", "esi", "edi", "ebp"):
            assert (
                child["result"]["registers"][register]
                == child["fixture"]["registers"][register]
            )
        assert child["result"]["registers"]["eax"] == c.SOURCE_OBJECT
        assert child["result"]["registers"]["ecx"] == vector["cookie"]
        assert (
            raw(child["fixture"]["pages"], child["fixture"]["stack"] + 4)
            == fixture["entry"] - 20
        )
        assert child["result"]["heap_nodes"][-1] == fixture["prototype"]["vector_begin"]
        assert (
            len(child["result"]["heap_nodes"]) == child["result"]["tree_heap_count"] + 1
        )
        # Read each exact heap dispatch frame from ordered writes; these are the
        # arguments at the import entry, before the supplied stdcall response.
        current = child["fixture"]["pages"]
        allocation_dispatches = free_dispatches = 0
        stack = fixture["prototype"]["stack"]
        for event in child["result"]["events"]:
            if event["access"] != "write":
                continue
            current = change(current, event["address"], event["value"], event["width"])
            if event["width"] != 4:
                continue
            if event["value"] == c.BASE + 0x389463:
                tree = allocation_dispatches < child["result"]["tree_heap_count"]
                sp = stack - (144 if tree else 140)
                assert event["address"] == sp
                request = (
                    24
                    if tree
                    else 8 * fixture["logical"]["class_operation"]["vector"]["capacity"]
                )
                assert [raw(current, sp + 4 * i) for i in range(4)] == [
                    c.BASE + 0x389463,
                    c.spare.construction.HEAP,
                    0,
                    request,
                ]
                allocation_dispatches += 1
            elif event["value"] == c.BASE + 0x389172:
                sp = stack - 132
                assert module is g.old and event["address"] == sp
                assert [raw(current, sp + 4 * i) for i in range(4)] == [
                    c.BASE + 0x389172,
                    c.spare.construction.HEAP,
                    0,
                    fixture["prototype"]["old_begin"],
                ]
                free_dispatches += 1
        assert allocation_dispatches == len(child["result"]["heap_nodes"])
        assert free_dispatches == (1 if module is g.old else 0)


def test_continuous_lua_identities_filtered_requests_and_zero_results(cases):
    for module, vector, fixture, expected in cases:
        logical, lua = fixture["logical"], c._Lua(vector)
        for call in expected["calls"]:
            lua.apply(call)
            assert call["target"] == c.layout.TARGETS[call["api"]]
            assert call["arguments"][0] == fixture["state"]
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
        assert logical["return_count"] == 0 and logical["lua_stack_delta"] == 4
        assert (
            c._model_pages(vector, fixture, expected, class_module=module)
            == expected["pages"]
        )
        assert (
            class_child(expected)["fixture"]["transfer"]["destination"]
            == logical["class_operation"]["destination"]
        )


@pytest.mark.parametrize("family", list(g.FAMILIES))
@pytest.mark.parametrize(
    "kind",
    [
        "ancestor",
        "local_record",
        "append",
        "begin",
        "end",
        "capacity",
        "child_capacity",
        "tree_payload",
        "tree_link",
        "finalword",
        "reference",
    ],
)
def test_independent_parent_and_child_models_reject_forged_outputs(cases, family, kind):
    module, vector, fixture, expected = next(
        case
        for case in reversed(cases)
        if case[1]["class_family"] == family and case[1]["source_keys"]
    )
    child = class_child(expected)
    node = child["result"]["insertions"][-1]["destination_address"]
    address = {
        "ancestor": fixture["entry"] + 8,
        "local_record": fixture["entry"] - 20,
        "append": fixture["prototype"]["vector_end"],
        "begin": c.RECEIVER + 4,
        "end": c.RECEIVER + 8,
        "capacity": c.RECEIVER + 12,
        "child_capacity": c.RECEIVER + 12,
        "tree_payload": node + 20,
        "tree_link": node + 4,
        "finalword": c.RECEIVER,
        "reference": c.SOURCE_OBJECT + 40,
    }[kind]
    forged = copy.deepcopy(expected)
    value = raw(expected["pages"], address) ^ 1
    forged["pages"] = change(forged["pages"], address, value)
    forged_child = class_child(forged)
    forged_child["result"]["pages"] = change(
        forged_child["result"]["pages"], address, value
    )
    if kind == "child_capacity":
        forged_child["fixture"]["vector_capacity"] += 8
    if kind in ("local_record", "append"):
        # Corrupt both final copies together to defeat a circular copy check.
        for at in (fixture["entry"] - 20, fixture["prototype"]["vector_end"]):
            forged["pages"] = change(forged["pages"], at, 0xDEADBEEF)
            forged_child["result"]["pages"] = change(
                forged_child["result"]["pages"], at, 0xDEADBEEF
            )
    assert (
        c._model_pages(vector, fixture, forged, class_module=module)
        == expected["pages"]
    )
    assert forged["pages"] != expected["pages"]


def test_independent_old_live_bytes_reject_forged_original_and_copied_pages(cases):
    module, vector, fixture, expected = next(
        case
        for case in cases
        if case[1]["class_family"] == "old_full" and case[1]["old_size"] == 3
    )
    for offset in (0, 8, 20):
        forged = copy.deepcopy(expected)
        child = class_child(forged)
        value = raw(fixture["pages"], fixture["prototype"]["old_begin"] + offset) ^ 1
        for address in (
            fixture["prototype"]["old_begin"] + offset,
            fixture["prototype"]["vector_begin"] + offset,
        ):
            forged["pages"] = change(forged["pages"], address, value)
            child["result"]["pages"] = change(child["result"]["pages"], address, value)
        assert (
            c._model_pages(vector, fixture, forged, class_module=module)
            == expected["pages"]
        )


@pytest.mark.parametrize("family", list(g.FAMILIES))
@pytest.mark.parametrize("field", ["destination", "copies"])
def test_joined_class_outputs_must_match_independent_logical_model(
    cases, family, field
):
    module, vector, fixture, expected = next(
        case
        for case in reversed(cases)
        if case[1]["class_family"] == family and case[1]["source_keys"]
    )
    forged = copy.deepcopy(expected)
    transfer = class_child(forged)["fixture"]["transfer"]
    if field == "destination":
        transfer[field]["payloads"][0] ^= 1
    else:
        transfer[field][-1]["payload"] ^= 1
    with pytest.raises(
        RuntimeError, match="independent callback class transfer differs"
    ):
        c._model_pages(vector, fixture, forged, class_module=module)


@pytest.mark.parametrize("family", list(g.FAMILIES))
def test_expected_preserves_inputs_and_is_deterministic(cases, family):
    module, vector, fixture, expected = next(
        case for case in reversed(cases) if case[1]["class_family"] == family
    )
    before = copy.deepcopy((vector, fixture))
    assert c._expected(vector, fixture, class_module=module) == expected
    assert (vector, fixture) == before


@pytest.fixture(scope="module")
def receipts():
    path = PROGRAMS / (PREFIX + "native_lua_class_callback_growth_conformance.json")
    if not path.exists() or g.SEALED_SHA256 in ("UNSEALED", "PENDING"):
        pytest.skip("awaiting reviewed continuous growth callback seal")
    evidence = json.loads(path.read_text())
    paths, sources = {}, {}
    for key, (kind, digest) in g.SOURCE_PINS.items():
        suffix = "program_facts" if key == "program_facts" else kind.removeprefix("pe_")
        source_path = PROGRAMS / (PREFIX + suffix + ".json")
        sources[key] = json.loads(source_path.read_text())
        assert g._canonical_sha256(sources[key]) == digest
        paths[key] = source_path
    return path, evidence, paths, sources


def test_receipt_pins_encoding_family_coverage_all_controls_and_scope(receipts):
    path, evidence, _, sources = receipts
    assert len(g.SOURCE_PINS) == 7
    assert g._canonical_sha256(evidence) == g.SEALED_SHA256 == CANONICAL
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RAW
    assert g.encode_conformance(evidence).encode("utf-8") == path.read_bytes()
    assert g.validate_structure(evidence, sources)["status"] == "structurally_verified"
    summary = evidence["summary"]
    for key, value in dict(
        cases=2304,
        callback_bytes=269,
        retained_lua_values=4,
        result_count=0,
        opaque_native_instructions=0,
        accounting_promotions=0,
    ).items():
        assert summary[key] == value
    assert summary["static_sites"] == len(evidence["body"]["points"])
    assert summary["executed_sites"] == len(evidence["executed_rvas"])
    assert set(evidence["executed_rvas_by_family"]) == set(g.FAMILIES)
    assert set(evidence["executed_rvas"]) == set().union(
        *(set(v) for v in evidence["executed_rvas_by_family"].values())
    )
    common_controls = {
        "ancestor",
        "record",
        "word",
        "reference",
        "literal",
        "iat",
        "vector",
        "capacity",
        "result",
        "lua_prefix",
        "heap_request",
        "cookie",
    }
    controls = {
        (row["family"], row["kind"]): row for row in evidence["negative_controls"]
    }
    wanted = {
        (family, kind)
        for family in g.FAMILIES
        for kind in common_controls
        | ({"old", "free_request"} if family == "old_full" else set())
    }
    assert len(evidence["negative_controls"]) == len(controls) == 26
    assert set(controls) == wanted and all(row["rejected"] for row in controls.values())
    for family, source in (("first_null", "class_empty"), ("old_full", "class_old")):
        union = set(evidence["executed_rvas_by_family"][family])
        assert set(sources[source]["executed_rvas"]) <= union
        assert set(sources["table"]["executed_rvas"]) <= union
        assert not c.CLASS_ARGUMENT_BELOW_END_SITES.intersection(union)
        assert not any(
            a <= int(pc, 16) < b
            for pc in union
            for a, b in (
                (0x2EC140, 0x2EC154),
                (0x2EC164, 0x2EC178),
                (0x2EC188, 0x2EC19E),
            )
        )
        parent_required = {
            p["rva"]
            for p in evidence["body"]["points"]
            if c.START <= int(p["rva"], 16) < c.END
            and not any(
                a <= int(p["rva"], 16) < b
                for a, b in (
                    (0x2EC140, 0x2EC154),
                    (0x2EC164, 0x2EC178),
                    (0x2EC188, 0x2EC19E),
                )
            )
        }
        assert parent_required <= union
        assert controls[family, "cookie"]["endpoint"] == "0x003574d5"
        stats = summary["families"][family]
        assert stats["cases"] == 1152 and stats["executed_sites"] == len(union)
        assert stats["allocations"] >= stats["cases"]
        assert stats["frees"] == (1152 if family == "old_full" else 0)
    assert evidence["scope"]["continuous_machine"] is True
    assert {"HeapAlloc", "HeapFree"} <= set(evidence["scope"]["supplied_apis"])
    excluded = " ".join(evidence["scope"]["excluded"])
    assert (
        "Real Lua VM" in excluded
        and "Actual heap ownership" in excluded
        and "No accounting promotion" in excluded
    )


@pytest.mark.parametrize("mutation", ["summary", "family", "controls", "kind"])
def test_tampered_receipt_rejected(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(evidence)
    if mutation == "summary":
        changed["summary"]["cases"] += 1
    elif mutation == "family":
        changed["executed_rvas_by_family"]["old_full"].pop()
    elif mutation == "controls":
        changed["negative_controls"][0]["rejected"] = False
    else:
        changed["analysis_kind"] = "pe_other"
    with pytest.raises(RuntimeError):
        g.validate_structure(changed, sources)


@pytest.mark.parametrize("mutation", ["missing", "extra", "pin"])
def test_source_preflight_rejects_unreviewed_partition_and_pins(receipts, mutation):
    _, evidence, _, sources = receipts
    changed = copy.deepcopy(sources)
    if mutation == "missing":
        del changed["class_old"]
    elif mutation == "extra":
        changed["unreviewed"] = {}
    else:
        changed["class_empty"]["schema_version"] += 1
    with pytest.raises(RuntimeError):
        g._preflight(changed)
    with pytest.raises(RuntimeError):
        g.validate_structure(evidence, changed)


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
    assert result.stderr == b""
    assert result.stdout == g.encode_conformance(
        g.validate_structure(evidence, sources)
    ).encode("utf-8")
    changed = tmp_path / "noncanonical.json"
    changed.write_text(json.dumps(evidence), encoding="utf-8")
    result = subprocess.run(
        command + ["--evidence", str(changed)],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 1 and result.stdout == b""
    assert b"not deterministically encoded" in result.stderr


def test_exact_full_cli_build_in_isolated_native_subprocess(receipts):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    path, _, paths, _ = receipts
    result = subprocess.run(
        command_for("build", paths) + ["--executable", executable],
        cwd=ROOT,
        capture_output=True,
        timeout=1800,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == path.read_bytes()
