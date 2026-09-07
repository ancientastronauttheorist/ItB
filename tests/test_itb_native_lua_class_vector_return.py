"""Relocated append arguments and complete native ancestor-frame contract."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_lua_class_vector_return_conformance as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize("frame", [32, 0x20002000, 0x2000200F, 2**32 - 13])
def test_equal_return_consumes_owner_argument(frame):
    result = helper.return_spec(frame, 0xFFFFFFFF, 0xFFFFFFFF)
    assert result["entry_esp"] == frame - 32
    assert result["checker_entry"] == frame - 24
    assert result["final_esp"] == frame + 12 and result["endpoint"] == helper.RETURN
    assert result["flags"] & 0x8D5 == 0x44


@pytest.mark.parametrize(
    "cookie,current", [(0, 1), (1, 0), (0x80000000, 0), (0, 0xFFFFFFFF)]
)
def test_mismatch_preserves_this_callers_frame_at_external_boundary(cookie, current):
    f = helper.STACK + 0x200F
    result = helper.return_spec(f, cookie, current)
    assert not result["equal"] and result["endpoint"] == helper.ESCAPE
    assert result["final_esp"] == f - 24
    assert result["continuation"] == helper.BASE + 0x2EB227
    assert not result["flags"] & 0x40


@pytest.mark.parametrize(
    "frame,cookie,current",
    [
        (31, 0, 0),
        (2**32 - 12, 0, 0),
        (True, 0, 0),
        (100, True, 0),
        (100, 0, -1),
        (100, 2**32, 0),
    ],
)
def test_invalid_frame_or_cookie_words_rejected(frame, cookie, current):
    with pytest.raises(helper.ConformanceError):
        helper.return_spec(frame, cookie, current)


@pytest.mark.parametrize("delta", [0, 1])
def test_saved_ebx_is_read_before_checker_continuation_overwrites_its_slot(delta):
    v = dict(frame_alignment=7, cookie=0x6B8B4567, global_delta=delta, df=1, seed=7)
    fixture = helper._fixture(v)
    expected = helper._expected(fixture)
    f = fixture["frame"]
    at = [e for e in expected["events"] if e["address"] == f - 24]
    assert [(e["access"], e["value"]) for e in at] == [
        ("read", fixture["saved"]["ebx"]),
        ("write", helper.CONTINUATION),
    ] + ([("read", helper.CONTINUATION)] if not delta else [])
    assert expected["registers"]["ebx"] == fixture["saved"]["ebx"]
    assert expected["registers"]["eax"] == fixture["registers"]["eax"]
    assert expected["registers"]["edx"] == fixture["registers"]["edx"]
    assert expected["registers"]["ecx"] == v["cookie"]


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "chain": "native_lua_class_return_helper_chain",
        "append": "native_lua_class_vector_append_semantics",
        "checker": "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary",
        "prior_tail": "native_assertion_helper_return_tail",
        "conformance": "native_lua_class_vector_return_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_sealed_return_receipt(receipts):
    paths, data, sources = receipts
    evidence = data["conformance"]
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )
    assert (
        helper.encode_conformance(evidence).encode()
        == paths["conformance"].read_bytes()
    )
    assert (
        evidence["summary"]["executed_sites"] == 13
        and evidence["summary"]["opaque_instructions"] == 0
    )


def test_changed_receipt_rejected(receipts):
    _, data, sources = receipts
    changed = copy.deepcopy(data["conformance"])
    changed["schema_version"] = 99
    with pytest.raises(helper.ConformanceError):
        helper.validate_structure(changed, sources)


def test_exact_cli_rebuild(receipts):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    paths, _, sources = receipts
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_lua_class_vector_return_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["conformance"].read_bytes()
