"""Actual callback table-helper frames, retained arguments and prefix one."""

import copy
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from src.observatory import native_lua_table_transfer_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "windows_build_13725832_31fe35265598_"


def put(pages, address, value):
    for i, byte in enumerate(value.to_bytes(4, "little")):
        page = (address + i) & ~4095
        payload = bytearray(pages[page])
        payload[(address + i) & 4095] = byte
        pages[page] = bytes(payload)


def caller_case(which, alignment, kinds):
    frame = 0x30001000 + alignment
    entry = frame - (64 if which == 0 else 40)
    endpoint = c.BASE + (0x2EC1E0 if which == 0 else 0x2EC203)
    vector = dict(
        kinds=kinds, alignment=alignment, prefix_length=1 if which == 0 else 3
    )
    pages = {
        0x30000000 + 4096 * j: bytes((i * 31 + j * 17) % 256 for i in range(4096))
        for j in range(2)
    }
    if which == 0:
        for offset, value in (
            (-60, 0x12000000),
            (-56, 0xFFFFD8F0),
            (-52, 23),
            (-48, 0x12000000),
            (-44, 0xFFFFD8F0),
            (-40, 17),
        ):
            put(pages, frame + offset, value)
    put(pages, frame - 16, 0)
    put(pages, frame - 12, 0x14000000)
    put(pages, entry, endpoint)
    registers = dict(
        eax=0xA2345678,
        ebx=0x12000000,
        ecx=0x12000000,
        edx=0xB2345678,
        esi=0x05000900,
        edi=0x14000000,
        ebp=frame,
        esp=entry,
    )
    return vector, dict(
        entry=entry, return_address=endpoint, registers=registers, stack_pages=pages
    )


@pytest.mark.parametrize(
    "which,alignment,kinds",
    itertools.product(
        (0, 1), (0, 15), ([], ["init"], ["finalize"], ["other", "init", "finalize"])
    ),
)
def test_actual_call_frames_and_ancestor_storage(which, alignment, kinds):
    vector, caller = caller_case(which, alignment, kinds)
    before = copy.deepcopy(caller)
    fixture = c._fixture(vector, caller=caller)
    expected = c._expected(vector, fixture)
    assert caller == before
    assert expected["registers"]["esp"] == caller["entry"] + 4
    assert expected["registers"]["eax"] == 0
    for reg in ("ebx", "esi", "edi", "ebp"):
        assert expected["registers"][reg] == caller["registers"][reg]
    for address in range(caller["entry"] + 4, 0x30002000):
        assert (
            expected["pages"][address & ~4095][address & 4095]
            == caller["stack_pages"][address & ~4095][address & 4095]
        )
    assert expected["relation"]["assignments"] == [
        i for i, kind in enumerate(kinds) if kind == "other"
    ]
    assert expected["endpoint"] == caller["return_address"]


@pytest.mark.parametrize(
    "mutation",
    (
        "wrap",
        "underflow",
        "bool",
        "return",
        "code_return",
        "api_return",
        "stack_return",
        "missing_page",
        "mutable_page",
        "code_page",
        "register",
        "null_state",
    ),
)
def test_invalid_caller_rejected(mutation):
    vector, caller = caller_case(0, 0, ["other"])
    if mutation == "wrap":
        caller["entry"] = 2**32 - 4
    elif mutation == "underflow":
        caller["entry"] = 47
    elif mutation == "bool":
        caller["entry"] = True
    elif mutation == "return":
        put(caller["stack_pages"], caller["entry"], 0)
    elif mutation == "code_return":
        caller["return_address"] = c.BASE + c.START
    elif mutation == "api_return":
        caller["return_address"] = c.IMPORT
    elif mutation == "stack_return":
        caller["return_address"] = caller["entry"] + 256
    elif mutation == "missing_page":
        caller["stack_pages"].pop(0x30000000)
    elif mutation == "mutable_page":
        caller["stack_pages"][0x30000000] = bytearray(4096)
    elif mutation == "code_page":
        caller["stack_pages"][(c.BASE + c.START) & ~4095] = bytes(4096)
    elif mutation == "register":
        caller["registers"]["edi"] = True
    elif mutation == "null_state":
        caller["registers"]["ecx"] = 0
    with pytest.raises(c.ConformanceError):
        c._fixture(vector, caller=caller)


def test_tampered_fixture_contract_rejected():
    vector, caller = caller_case(0, 0, ["other"])
    fixture = c._fixture(vector, caller=caller)
    fixture["relation"]["assignments"] = []
    with pytest.raises(c.ConformanceError, match="relation"):
        c._expected(vector, fixture)


def test_exact_actual_callback_frames_subprocess():
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private dependencies")
    code = """
import json,runpy,sys
from pathlib import Path
from src.observatory import native_lua_table_transfer_conformance as c
case=runpy.run_path('tests/test_itb_native_lua_table_transfer_caller_mapping.py')['caller_case']
p=Path('data/observatory/programs'); prefix='windows_build_13725832_31fe35265598_'
sources={'program_facts':json.loads((p/(prefix+'program_facts.json')).read_text()),'class_chain':json.loads((p/(prefix+'native_lua_class_return_helper_chain.json')).read_text())}
data,image,digest=c._load_executable(Path(sys.argv[1]))
assert digest == c.EXE_SHA256 and image.image_base == c.BASE
c._preflight(sources)
code,points=c._load_code(data,image,sources)
count=0
for which in (0,1):
 for alignment in (0,15):
  for kinds in ([],['init'],['finalize'],['other','init','finalize']):
   v,caller=case(which,alignment,kinds)
   c._run_case(code,points,v,fixture=c._fixture(v,caller=caller));count+=1
print(count)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, executable],
        cwd=ROOT,
        capture_output=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == b"16"
