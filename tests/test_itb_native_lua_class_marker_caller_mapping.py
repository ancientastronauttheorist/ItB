"""Checked marker caller frames; native execution stays in isolated subprocesses."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_class_marker_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


def representative_vectors():
    return [
        dict(
            alignment=a,
            prefix_length=3,
            has_metatable=present,
            value_kind=kind,
            final_void_eax=0x12345678,
        )
        for a, present, kind in [
            (0, False, "nil"),
            (7, True, "false"),
            (15, True, "zero"),
        ]
    ]


def caller_for(vector, second=False, cross_page=False):
    entry = 0x30001010 if cross_page else 0x30001000 + vector["alignment"] - 40
    endpoint = c.BASE + (0x2EC184 if second else 0x2EC160)
    pages = {
        0x30000000 + j * 4096: bytearray((i * 31 + j * 7) % 256 for i in range(4096))
        for j in range(2)
    }
    for i, byte in enumerate(endpoint.to_bytes(4, "little")):
        pages[(entry + i) & ~4095][(entry + i) & 4095] = byte
    registers = dict(c._fixture(vector)["registers"])
    registers.update(
        esp=entry,
        ecx=0x17001230,
        edx=1 if second else (-10003 & 0xFFFFFFFF),
        ebx=0x17001230,
        esi=0x81928374,
        edi=0xA1B2C3D4,
        ebp=entry + 40,
    )
    return dict(
        entry=entry,
        return_address=endpoint,
        registers=registers,
        stack_pages={p: bytes(v) for p, v in pages.items()},
    )


@pytest.mark.parametrize("vector", representative_vectors())
@pytest.mark.parametrize(
    "second,cross_page", [(False, False), (True, False), (False, True)]
)
def test_actual_caller_arguments_cdecl_frames_and_ancestor_preservation(
    vector, second, cross_page
):
    caller = caller_for(vector, second, cross_page)
    original = copy.deepcopy(caller)
    fixture = c._fixture(vector, caller=caller)
    expected = c._expected(vector, fixture)
    assert caller == original
    assert expected["endpoint"] == caller["return_address"]
    assert expected["registers"]["esp"] == caller["entry"] + 4
    for name in ("ebx", "esi", "edi", "ebp"):
        assert expected["registers"][name] == caller["registers"][name]
    truth = vector["has_metatable"] and vector["value_kind"] not in ("nil", "false")
    assert expected["registers"]["eax"] == (
        (0x12345600 | int(truth)) if vector["has_metatable"] else 0
    )
    assert expected["calls"][0]["arguments"] == [
        caller["registers"]["ecx"],
        caller["registers"]["edx"],
    ]
    assert [v["entry_esp"] - caller["entry"] for v in expected["calls"]] == (
        [-16, -16, -24, -32, -16] if vector["has_metatable"] else [-16]
    )
    assert expected["pages"] == c._stack_model(vector, fixture)
    assert not any(c.STACK <= p < c.STACK + 0x4000 for p in fixture["pages"])
    for page, before in caller["stack_pages"].items():
        after = expected["pages"][page]
        assert all(
            before[i] == after[i]
            for i in range(4096)
            if not caller["entry"] - 32 <= page + i < caller["entry"]
        )


def test_explicit_default_mapping_is_identical():
    for vector in representative_vectors():
        original = c._fixture(vector)
        caller = dict(
            entry=original["entry"],
            return_address=original["endpoint"],
            registers=original["registers"],
            stack_pages={
                p: v
                for p, v in original["pages"].items()
                if c.STACK <= p < c.STACK + 0x4000
            },
        )
        mapped = c._fixture(vector, caller=caller)
        assert mapped == original
        assert c._expected(vector, mapped) == c._expected(vector, original)


@pytest.mark.parametrize("entry", [True, -1, 31, 2**32 - 4, 2**32])
def test_invalid_and_ret_wrapping_entry_rejected(entry):
    vector = representative_vectors()[0]
    caller = caller_for(vector)
    caller["entry"] = caller["registers"]["esp"] = entry
    with pytest.raises(RuntimeError, match="entry address"):
        c._fixture(vector, caller=caller)


@pytest.mark.parametrize(
    "mutation",
    [
        "register_bool",
        "missing_register",
        "wrong_esp",
        "null_state",
        "wrong_return",
        "missing_page",
        "short_page",
        "unaligned_page",
        "return_bool",
    ],
)
def test_malformed_mapping_rejected(mutation):
    vector = representative_vectors()[0]
    caller = caller_for(vector)
    if mutation == "register_bool":
        caller["registers"]["esi"] = True
    elif mutation == "missing_register":
        del caller["registers"]["edi"]
    elif mutation == "wrong_esp":
        caller["registers"]["esp"] += 4
    elif mutation == "null_state":
        caller["registers"]["ecx"] = 0
    elif mutation == "wrong_return":
        caller["return_address"] += 4
    elif mutation == "missing_page":
        del caller["stack_pages"][0x30000000]
    elif mutation == "short_page":
        caller["stack_pages"][0x30000000] = bytes(4095)
    elif mutation == "unaligned_page":
        caller["stack_pages"][0x30000001] = bytes(4096)
    else:
        caller["return_address"] = True
    with pytest.raises(RuntimeError):
        c._fixture(vector, caller=caller)


@pytest.mark.parametrize("kind", ["literal", "iat", "code", "api", "endpoint"])
def test_caller_stack_reserved_page_alias_rejected(kind):
    vector = representative_vectors()[0]
    caller = caller_for(vector)
    page = {
        "literal": c.LITERAL & ~4095,
        "iat": c._fixture(vector)["iat_page"],
        "code": (c.BASE + c.START) & ~4095,
        "api": c.IMPORT,
        "endpoint": caller["return_address"] & ~4095,
    }[kind]
    caller["stack_pages"][page] = bytes(4096)
    with pytest.raises(RuntimeError, match="aliases reserved"):
        c._fixture(vector, caller=caller)


def test_runner_fixture_cannot_bypass_return_and_literal_checks():
    vector = representative_vectors()[0]
    fixture = c._fixture(vector, caller=caller_for(vector))
    changed = copy.deepcopy(fixture)
    changed["endpoint"] += 4
    with pytest.raises(RuntimeError, match="return word"):
        c._expected(vector, changed)
    changed = copy.deepcopy(fixture)
    changed["entry"] = changed["registers"]["esp"] = c.LITERAL + 64
    with pytest.raises(RuntimeError, match="aliases literal"):
        c._expected(vector, changed)


def test_exact_default_receipt_and_relocated_native_subprocesses():
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    paths = {
        key: PROGRAMS
        / (
            PREFIX
            + ("program_facts" if key == "program_facts" else kind.removeprefix("pe_"))
            + ".json"
        )
        for key, (kind, _) in c.SOURCE_PINS.items()
    }
    command = [
        sys.executable,
        str(ROOT / "scripts/itb_native_lua_class_marker_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key, path in paths.items():
        command += ["--" + key.replace("_", "-"), str(path)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert (
        result.stdout
        == (
            PROGRAMS / (PREFIX + "native_lua_class_marker_conformance.json")
        ).read_bytes()
    )
    script = """
import json, os, runpy
from pathlib import Path
ns = runpy.run_path(TEST_PATH)
c = ns['c']
sources = {key: json.loads(Path(path).read_text()) for key, path in SOURCE_PATHS.items()}
data, image, digest = c._load_executable(Path(os.environ['ITB_EXACT_EXE']))
code, points = c._load_code(data, image, sources)
count = 0
for vector in ns['representative_vectors']():
    for second, cross_page in [(False, False), (True, False), (False, True)]:
        caller = ns['caller_for'](vector, second, cross_page)
        fixture = c._fixture(vector, caller=caller)
        c._run_case(code, points, vector, fixture=fixture)
        count += 1
print(count)
"""
    script = (
        "TEST_PATH = "
        + repr(str(Path(__file__).resolve()))
        + "\nSOURCE_PATHS = "
        + repr({k: str(p) for k, p in paths.items()})
        + "\n"
        + script
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, capture_output=True, timeout=90
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == b"9"
