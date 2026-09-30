"""Callback local record through null/full vector growth and checked return."""

import copy
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_tree_conformance as prefix
from src.observatory import native_lua_class_empty_vector_return_conformance as empty
from src.observatory import native_lua_class_old_vector_return_conformance as old

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
RECEIPT_PREFIX = "windows_build_13725832_31fe35265598_"
MODULES = (empty, old)


def read(pages, address, width=4):
    return int.from_bytes(
        bytes(pages[(address + i) & ~4095][(address + i) & 4095] for i in range(width)),
        "little",
    )


def changed(pages, address, value, width=4):
    result = dict(pages)
    for i, byte in enumerate(value.to_bytes(width, "little")):
        page = (address + i) & ~4095
        payload = bytearray(result[page])
        payload[(address + i) & 4095] = byte
        result[page] = bytes(payload)
    return result


def representative_vectors():
    # Largest recipes include empty, new, existing, and mixed source paths with
    # every frame/node alignment. Also vary the zero-through-three old records.
    return [
        dict(
            v,
            vector_alignment=(0, 7, 31)[i % 3],
            old_size=i % 4,
            old_alignment=(7 + 13 * (0, 7, 31)[i % 3]) % 32,
        )
        for i, v in enumerate(prefix.vectors()[-24:])
    ]


def caller_for(vector):
    fixture = prefix._fixture(vector)
    entry = fixture["stack"]
    registers = dict(fixture["registers"])
    registers.update(
        eax=entry + 28,
        ebx=0x12001000 + 32 * vector["node_alignment"],
        ecx=prefix.RECEIVER,
        edx=0xB1000002,
        esi=prefix.RECEIVER,
        edi=prefix.SOURCE_OBJECT,
        ebp=entry + 44,
    )
    return dict(
        argument_address=entry + 28,
        argument_record=[0, prefix.SOURCE_OBJECT],
        return_address=prefix.BASE + 0x2EC1BD,
        registers=registers,
    )


def event(access, address, value, width=4):
    return dict(access=access, address=address, width=width, value=value)


def contains(events, sequence):
    return any(
        events[i : i + len(sequence)] == sequence
        for i in range(len(events) - len(sequence) + 1)
    )


def test_representatives_cover_growth_and_caller_shapes():
    vectors = representative_vectors()
    assert len(vectors) == 24
    assert {v["profile"] for v in vectors} == {
        "empty_source",
        "all_new",
        "all_existing",
        "mixed",
    }
    assert {len(v["source_keys"]) for v in vectors} == {0, 7}
    assert {v["node_alignment"] for v in vectors} == {0, 7, 31}
    assert {v["frame_alignment"] for v in vectors} == {0, 15}
    assert {v["vector_alignment"] for v in vectors} == {0, 7, 31}
    assert {v["old_size"] for v in vectors} == {0, 1, 2, 3}


@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize("vector", representative_vectors())
def test_actual_callback_original_record_return_abi_and_ancestors(module, vector):
    caller = caller_for(vector)
    before = copy.deepcopy(caller)
    fixture = module._fixture(vector, caller=caller)
    pristine = copy.deepcopy(fixture)
    expected = module._expected(vector, fixture)
    assert caller == before and fixture == pristine
    entry, record = fixture["stack"], caller["argument_address"]
    assert record == entry + 28
    assert read(fixture["pages"], entry + 4) == record
    assert read(expected["pages"], record, 8) == prefix.SOURCE_OBJECT << 32
    assert read(expected["pages"], fixture["vector_end"], 8) == read(
        fixture["pages"], record, 8
    )
    assert expected["pages"] == module._model_pages(fixture, expected)
    assert expected["endpoint"] == caller["return_address"]
    assert expected["registers"]["esp"] == entry + 8
    assert expected["registers"]["eax"] == prefix.SOURCE_OBJECT
    assert expected["registers"]["ecx"] == vector["cookie"]
    assert expected["registers"]["edx"] == (0 if module is empty else 0xB0000001)
    assert expected["flags"] == 0x44
    for register in ("ebx", "esi", "edi", "ebp"):
        assert expected["registers"][register] == caller["registers"][register]
    for page in (prefix.construction.STACK, prefix.construction.STACK + 4096):
        offset = max(0, min(4096, entry + 8 - page))
        assert expected["pages"][page][offset:] == fixture["pages"][page][offset:]
    assert read(expected["pages"], 0) == vector["previous_seh"]
    assert read(expected["pages"], module.returned.COOKIE) == vector["cookie"]
    for offset, value in (
        (4, fixture["vector_begin"]),
        (8, fixture["vector_end"] + 8),
        (12, fixture["vector_capacity"]),
    ):
        assert read(expected["pages"], module.RECEIVER + offset) == value
    if module is empty:
        assert all(
            read(fixture["pages"], module.RECEIVER + offset) == 0
            for offset in (4, 8, 12)
        )
    else:
        assert (
            read(fixture["pages"], module.RECEIVER + 8)
            == read(fixture["pages"], module.RECEIVER + 12)
            == fixture["old_begin"] + 8 * vector["old_size"]
        )
        assert (
            expected["pages"][module.growth.OLD] == fixture["pages"][module.growth.OLD]
        )
        for i in range(8 * vector["old_size"]):
            assert read(expected["pages"], fixture["vector_begin"] + i, 1) == read(
                fixture["pages"], fixture["old_begin"] + i, 1
            )


@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize("vector", representative_vectors())
def test_dynamic_argument_growth_heap_and_free_event_contracts(module, vector):
    caller = caller_for(vector)
    fixture = module._fixture(vector, caller=caller)
    expected = module._expected(vector, fixture)
    before = prefix._expected(vector, fixture)
    events = expected["events"][len(before["events"]) :]
    frame = fixture["stack"] - 4
    request = 8 if module is empty else 8 * (vector["old_size"] + 1)
    assert expected["heap_nodes"] == before["heap_nodes"] + [fixture["vector_begin"]]
    assert expected["tree_heap_count"] == len(before["heap_nodes"])
    for address, value in (
        (frame - 136, module.BASE + 0x389463),
        (frame - 124, request),
        (frame - 128, 0),
    ):
        assert event("write", address, value) in events
    index = events.index(event("write", frame - 136, module.BASE + 0x389463))
    assert events[index - 1] == event(
        "read", module.growth.ALLOC_IAT, module.construction.IMPORT
    )
    argument, end = caller["argument_address"], fixture["vector_end"]
    assert contains(
        events,
        [
            event("read", argument, 0),
            event("write", end, 0),
            event("read", argument + 4, prefix.SOURCE_OBJECT),
            event("write", end + 4, prefix.SOURCE_OBJECT),
        ],
    )
    assert not any(
        e["access"] == "read" and e["address"] in (prefix.ARGUMENT, prefix.ARGUMENT + 4)
        for e in events
    )
    if module is empty:
        assert not any(
            e["access"] == "read" and e["address"] == module.growth.FREE_IAT
            for e in events
        )
    else:
        assert (
            sum(
                e["access"] == "read" and e["address"] == module.growth.FREE_IAT
                for e in events
            )
            == 1
        )
        for address, value in (
            (frame - 128, module.BASE + 0x389172),
            (frame - 124, module.construction.HEAP),
            (frame - 120, 0),
            (frame - 116, fixture["old_begin"]),
        ):
            assert event("write", address, value) in events
        for i in range(0, 8 * vector["old_size"], 4):
            value = read(fixture["pages"], fixture["old_begin"] + i)
            assert contains(
                events,
                [
                    event("read", fixture["old_begin"] + i, value),
                    event("write", fixture["vector_begin"] + i, value),
                ],
            )


@pytest.mark.parametrize("module", MODULES)
def test_explicit_legacy_mapping_remains_identical(module):
    for vector in representative_vectors():
        original = module._fixture(vector)
        caller = dict(
            argument_address=prefix.ARGUMENT,
            argument_record=[0xA3125678, prefix.SOURCE_OBJECT],
            return_address=original["return_address"],
            registers=original["registers"],
        )
        mapped = module._fixture(vector, caller=caller)
        assert mapped == original
        assert module._expected(vector, mapped) == module._expected(vector, original)


@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize("offset", [8, 28, 32, 36, 255])
def test_independent_model_restores_ancestors_and_original_local_record(module, offset):
    vector = representative_vectors()[-1]
    fixture = module._fixture(vector, caller=caller_for(vector))
    expected = module._expected(vector, fixture)
    address = fixture["stack"] + offset
    forged = dict(
        expected,
        pages=changed(expected["pages"], address, read(expected["pages"], address) ^ 1),
    )
    assert module._model_pages(fixture, forged) == expected["pages"]
    assert forged["pages"] != expected["pages"]


@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize("offset", [0, 4])
def test_append_uses_initial_record_even_when_both_final_copies_are_forged(
    module, offset
):
    vector = representative_vectors()[-1]
    caller = caller_for(vector)
    fixture = module._fixture(vector, caller=caller)
    expected = module._expected(vector, fixture)
    address = caller["argument_address"] + offset
    value = read(fixture["pages"], address) ^ 1
    pages = changed(expected["pages"], address, value)
    pages = changed(pages, fixture["vector_end"] + offset, value)
    assert (
        module._model_pages(fixture, dict(expected, pages=pages)) == expected["pages"]
    )


def test_old_live_copy_uses_initial_storage_when_both_final_copies_are_forged():
    vector = representative_vectors()[-1]
    fixture = old._fixture(vector, caller=caller_for(vector))
    expected = old._expected(vector, fixture)
    assert vector["old_size"] == 3
    for offset in (0, 8, 20):
        value = read(fixture["pages"], fixture["old_begin"] + offset) ^ 1
        pages = changed(expected["pages"], fixture["old_begin"] + offset, value)
        pages = changed(pages, fixture["vector_begin"] + offset, value)
        assert (
            old._model_pages(fixture, dict(expected, pages=pages)) == expected["pages"]
        )


@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize("first", [0, 1, 0xFFFFFFFF])
def test_dynamic_record_first_word_survives_growth(first, module):
    vector = representative_vectors()[-1]
    caller = caller_for(vector)
    caller["argument_record"][0] = first
    fixture = module._fixture(vector, caller=caller)
    expected = module._expected(vector, fixture)
    assert read(expected["pages"], caller["argument_address"], 8) == first | (
        prefix.SOURCE_OBJECT << 32
    )
    assert read(expected["pages"], fixture["vector_end"], 8) == first | (
        prefix.SOURCE_OBJECT << 32
    )


@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize(
    "mutation,message",
    [
        ("matching_unreviewed_return", "unreviewed class caller return"),
        ("bool_register", "invalid class caller registers"),
        ("null_receiver", "invalid class caller registers"),
        ("mismatched_esp", "invalid class caller registers"),
        ("mutable_page", "invalid class caller pages"),
        ("unreviewed_argument", "unreviewed class argument address"),
        ("wrong_source", "invalid class argument source"),
        ("wrong_return_word", "class caller return word differs"),
    ],
)
def test_direct_fixture_cannot_bypass_checked_caller(module, mutation, message):
    vector = representative_vectors()[-1]
    fixture = module._fixture(vector, caller=caller_for(vector))
    if mutation == "matching_unreviewed_return":
        fixture["return_address"] = prefix.BASE + 0x2EC1C1
        fixture["pages"] = changed(
            fixture["pages"], fixture["stack"], fixture["return_address"]
        )
    elif mutation == "bool_register":
        fixture["registers"]["ebx"] = True
    elif mutation == "null_receiver":
        fixture["registers"]["ecx"] = 0
    elif mutation == "mismatched_esp":
        fixture["registers"]["esp"] += 4
    elif mutation == "mutable_page":
        page = fixture["stack"] & ~4095
        fixture["pages"][page] = bytearray(fixture["pages"][page])
    elif mutation == "unreviewed_argument":
        fixture["pages"] = changed(
            fixture["pages"], fixture["stack"] + 4, fixture["stack"] + 32
        )
    elif mutation == "wrong_source":
        fixture["pages"] = changed(
            fixture["pages"], fixture["stack"] + 32, prefix.SOURCE_OBJECT + 4
        )
    else:
        fixture["pages"] = changed(
            fixture["pages"], fixture["stack"], fixture["return_address"] + 1
        )
    with pytest.raises(module.ConformanceError, match=message):
        module._expected(vector, fixture)


@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize("mutation", ["argument", "record", "register", "return"])
def test_growth_fixture_propagates_caller_validation(module, mutation):
    vector = representative_vectors()[-1]
    caller = caller_for(vector)
    if mutation == "argument":
        caller["argument_address"] += 4
    elif mutation == "record":
        caller["argument_record"] = [True, prefix.SOURCE_OBJECT]
    elif mutation == "register":
        caller["registers"]["edx"] = 2**32
    else:
        caller["return_address"] = 0x12345678
    before = copy.deepcopy(caller)
    with pytest.raises(RuntimeError):
        module._fixture(vector, caller=caller)
    assert caller == before


def test_actual_growth_frames_and_heap_traces_native_subprocess():
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    script = "TEST_PATH = " + repr(str(Path(__file__).resolve())) + "\n" + """
import json, os, runpy
from pathlib import Path
ns = runpy.run_path(TEST_PATH)
count = controls = 0
for module in ns['MODULES']:
    sources = {}
    for key, (kind, pinned) in module.SOURCE_PINS.items():
        suffix = 'program_facts' if key == 'program_facts' else kind.removeprefix('pe_')
        path = ns['PROGRAMS'] / (ns['RECEIPT_PREFIX'] + suffix + '.json')
        sources[key] = json.loads(path.read_text())
        assert module._canonical_sha256(sources[key]) == pinned
    module._preflight(sources)
    data, image, digest = module._load_executable(Path(os.environ['ITB_EXACT_EXE']))
    assert digest == module.EXE_SHA256 and image.image_base == module.BASE
    codes, points = module._load_code(data, image, sources)[:2]
    for vector in ns['representative_vectors']():
        fixture = module._fixture(vector, caller=ns['caller_for'](vector))
        result = module._run_case(codes, points, vector, fixture=fixture)
        expected = module._expected(vector, fixture)
        frame = fixture['stack'] - 4
        tree_count = expected['tree_heap_count']
        assert result['registers'] == expected['registers']
        assert result['flags'] == 0x44
        allocations = result['allocations']
        assert len(allocations) == tree_count + 1
        for index, allocation in enumerate(allocations):
            tree = index < tree_count
            assert allocation['node'] == expected['heap_nodes'][index]
            assert allocation['entry_esp'] == frame - (140 if tree else 136)
            assert allocation['request'] == (24 if tree else
                8 if module is ns['empty'] else 8 * (vector['old_size'] + 1))
            assert allocation['continuation'] == module.BASE + 0x389463
        if module is ns['old']:
            assert result['frees'] == [dict(pointer=fixture['old_begin'],
                entry_esp=frame-128, result=1, continuation=module.BASE + 0x389172)]
        else:
            assert not result.get('frees', [])
        count += 1
    for negative in ('ancestor', 'argument'):
        try:
            module._run_case(codes, points, vector, negative=negative, fixture=fixture)
        except module.ConformanceError as error:
            assert str(error) == 'class ancestor memory differs', str(error)
            controls += 1
        else:
            raise AssertionError('accepted native corruption: ' + negative)
print(count, controls)
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, capture_output=True, timeout=300
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout.strip() == b"48 4"
