"""Actual callback record/ABI mapping; native execution is subprocess-only."""

import copy
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_tree_conformance as prefix
from src.observatory import native_lua_class_spare_return_conformance as spare

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
RECEIPT_PREFIX = "windows_build_13725832_31fe35265598_"


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
    # Largest finite recipes exercise allocation, duplicate, mixed and empty paths.
    return [
        dict(
            v,
            buffer_address=(0x13000100, 0x16000100)[i % 2],
            old_size=(0, 1, 3)[i % 3],
            spare_records=2,
        )
        for i, v in enumerate(prefix.vectors()[-24:])
    ]


def caller_for(vector):
    fixture = prefix._fixture(vector)
    entry = fixture["stack"]
    registers = dict(fixture["registers"])
    registers.update(
        eax=entry + 28,
        ebx=0x17001230,
        ecx=prefix.RECEIVER,
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


@pytest.mark.parametrize("module", [prefix, spare])
@pytest.mark.parametrize("vector", representative_vectors())
def test_actual_callback_record_abi_and_ancestor_bytes(module, vector):
    caller = caller_for(vector)
    original = copy.deepcopy(caller)
    fixture = module._fixture(vector, caller=caller)
    pristine = copy.deepcopy(fixture)
    expected = module._expected(vector, fixture)
    assert caller == original and fixture == pristine
    entry, record = fixture["stack"], caller["argument_address"]
    assert read(fixture["pages"], entry + 4) == record
    assert read(expected["pages"], record, 8) == prefix.SOURCE_OBJECT << 32
    assert expected["pages"] == module._model_pages(fixture, expected)
    for page in (prefix.construction.STACK, prefix.construction.STACK + 4096):
        offset = max(0, entry + 8 - page)
        assert expected["pages"][page][offset:] == fixture["pages"][page][offset:]
    if module is spare:
        assert expected["endpoint"] == caller["return_address"]
        assert expected["registers"]["esp"] == entry + 8
        for register in ("ebx", "esi", "edi", "ebp"):
            assert expected["registers"][register] == caller["registers"][register]
        assert read(expected["pages"], fixture["vector_end"], 8) == read(
            fixture["pages"], record, 8
        )
    else:
        assert expected["registers"]["edi"] == record


@pytest.mark.parametrize("module", [prefix, spare])
def test_explicit_legacy_mapping_is_identical(module):
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


@pytest.mark.parametrize("module", [prefix, spare])
@pytest.mark.parametrize("offset", [8, 28, 32, 36, 255])
def test_independent_model_rejects_ancestor_and_record_corruption(module, offset):
    vector = representative_vectors()[-1]
    fixture = module._fixture(vector, caller=caller_for(vector))
    expected = module._expected(vector, fixture)
    address = fixture["stack"] + offset
    forged = dict(
        expected,
        pages=changed(expected["pages"], address, read(expected["pages"], address) ^ 1),
    )
    rebuilt = module._model_pages(fixture, forged)
    assert rebuilt != forged["pages"]
    assert rebuilt == expected["pages"]


def test_append_model_uses_initial_record_when_both_final_copies_are_forged():
    vector = representative_vectors()[-1]
    caller = caller_for(vector)
    fixture = spare._fixture(vector, caller=caller)
    expected = spare._expected(vector, fixture)
    pages = changed(expected["pages"], caller["argument_address"], 0xDEADBEEF)
    pages = changed(pages, fixture["vector_end"], 0xDEADBEEF)
    assert spare._model_pages(fixture, dict(expected, pages=pages)) == expected["pages"]


@pytest.mark.parametrize("first", [0, 1, 0xFFFFFFFF])
def test_supplied_record_first_word_survives_append(first):
    vector = representative_vectors()[-1]
    caller = caller_for(vector)
    caller["argument_record"][0] = first
    fixture = spare._fixture(vector, caller=caller)
    expected = spare._expected(vector, fixture)
    assert read(expected["pages"], fixture["vector_end"], 8) == (
        first | (prefix.SOURCE_OBJECT << 32)
    )
    assert read(expected["pages"], caller["argument_address"]) == first


@pytest.mark.parametrize(
    "mutation",
    [
        "address_bool",
        "address_negative",
        "address_wrapped",
        "address_unreviewed",
        "record_short",
        "record_long",
        "record_bool",
        "record_negative",
        "record_wrapped",
        "wrong_source",
        "missing_register",
        "register_bool",
        "register_negative",
        "register_wrapped",
        "wrong_esp",
        "wrong_receiver",
        "return_bool",
        "wrong_return",
    ],
)
def test_malformed_or_out_of_scope_caller_rejected(mutation):
    vector = representative_vectors()[-1]
    caller = caller_for(vector)
    if mutation.startswith("address_"):
        caller["argument_address"] = {
            "address_bool": True,
            "address_negative": -1,
            "address_wrapped": 2**32,
            "address_unreviewed": caller["argument_address"] + 4,
        }[mutation]
    elif mutation.startswith("record_"):
        caller["argument_record"] = {
            "record_short": [0],
            "record_long": [0, prefix.SOURCE_OBJECT, 0],
            "record_bool": [True, prefix.SOURCE_OBJECT],
            "record_negative": [-1, prefix.SOURCE_OBJECT],
            "record_wrapped": [2**32, prefix.SOURCE_OBJECT],
        }[mutation]
    elif mutation == "wrong_source":
        caller["argument_record"][1] += 4
    elif mutation == "missing_register":
        del caller["registers"]["edi"]
    elif mutation.startswith("register_"):
        caller["registers"]["edx"] = {
            "register_bool": True,
            "register_negative": -1,
            "register_wrapped": 2**32,
        }[mutation]
    elif mutation == "wrong_esp":
        caller["registers"]["esp"] += 4
    elif mutation == "wrong_receiver":
        caller["registers"]["ecx"] += 4
    else:
        caller["return_address"] = True if mutation == "return_bool" else 0x12345678
    for module in (prefix, spare):
        with pytest.raises(RuntimeError):
            module._fixture(vector, caller=caller)


@pytest.mark.parametrize("module", [prefix, spare])
@pytest.mark.parametrize(
    "mutation,message",
    [
        ("matching_unreviewed_return", "unreviewed class caller return"),
        ("bool_register", "invalid class caller registers"),
        ("null_receiver", "invalid class caller registers"),
        ("mismatched_esp", "invalid class caller registers"),
        ("mutable_page", "invalid class caller pages"),
    ],
)
def test_supplied_fixture_cannot_bypass_checked_caller(module, mutation, message):
    vector = representative_vectors()[-1]
    fixture = module._fixture(vector, caller=caller_for(vector))
    if mutation == "matching_unreviewed_return":
        # Internal consistency must not admit a new, unreviewed continuation.
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
    else:
        page = fixture["stack"] & ~4095
        fixture["pages"][page] = bytearray(fixture["pages"][page])
    with pytest.raises(module.ConformanceError, match=message):
        module._expected(vector, fixture)


def test_actual_frames_native_subprocess():
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    script = "TEST_PATH = " + repr(str(Path(__file__).resolve())) + "\n" + """
import json, os, runpy
from pathlib import Path
ns = runpy.run_path(TEST_PATH)
count = controls = 0
for module in (ns['prefix'], ns['spare']):
    sources = {}
    for key, (kind, digest) in module.SOURCE_PINS.items():
        suffix = 'program_facts' if key == 'program_facts' else kind.removeprefix('pe_')
        path = ns['PROGRAMS'] / (ns['RECEIPT_PREFIX'] + suffix + '.json')
        sources[key] = json.loads(path.read_text())
    module._preflight(sources)
    data, image, digest = module._load_executable(Path(os.environ['ITB_EXACT_EXE']))
    assert digest == module.EXE_SHA256 and image.image_base == module.BASE
    codes, points = module._load_code(data, image, sources)[:2]
    for vector in ns['representative_vectors']():
        fixture = module._fixture(vector, caller=ns['caller_for'](vector))
        module._run_case(codes, points, vector, fixture=fixture)
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
        [sys.executable, "-c", script], cwd=ROOT, capture_output=True, timeout=180
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == b"48 4"
