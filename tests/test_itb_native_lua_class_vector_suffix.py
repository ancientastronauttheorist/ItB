"""Relocated append arguments and complete native ancestor-frame contract."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_lua_class_vector_suffix_conformance as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize("size", [0, 1, 3, 4, 16, 256])
@pytest.mark.parametrize("delta", [0, 1])
def test_combined_domains_retain_cookie_comparison_and_append_extent(size, delta):
    values = [
        v
        for v in helper.vectors()
        if v["old_size"] == size and v["global_delta"] == delta
    ]
    assert values
    for v in values:
        g = helper.geometry(v)
        assert g["equal"] == (delta == 0)
        assert g["current_cookie"] == (v["cookie"] + delta) & 0xFFFFFFFF
        assert g["destination"] + 8 == g["final_end"] <= g["new_capacity"]


@pytest.mark.parametrize("s", [104, helper.STACK + 0x2000, helper.STACK + 0x200F])
def test_caller_frame_extends_through_real_return_and_consumed_argument(s):
    f = helper.frame_join(s)
    assert f["frame"] == s + 32 and f["checker_entry"] == s + 8
    assert f["saved_ebp"] == s + 32 and f["return_word"] == s + 36
    assert f["caller_return"] == s + 44 and f["mismatch_esp"] == s + 8
    assert f["protected_end"] >= f["caller_return"]


@pytest.mark.parametrize(
    "update",
    [
        {"cookie": True},
        {"cookie": -1},
        {"global_delta": 2**32},
        {"global_delta": False},
    ],
)
def test_invalid_cookie_state_rejected(update):
    v = helper.vectors()[0]
    v.update(update)
    with pytest.raises(helper.ConformanceError):
        helper.geometry(v)


def test_matrix_keeps_both_append_domains_and_cookie_endpoints():
    values = helper.vectors()
    assert len(values) == 5920
    assert sum(v["old_size"] < 4 for v in values) == 1120
    assert sum(v["global_delta"] == 0 for v in values) == 2960
    assert {v["new_alignment"] for v in values} == {0, 1, 7, 15, 31}
    assert {v["stack_alignment"] for v in values} == {0, 15}


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "owner": "native_vector_resize_semantics",
        "allocation_composition": "native_vector_allocation_composition",
        "allocation_conformance": "native_vector_allocation_conformance",
        "scalar_copy": "native_scalar_copy_semantics",
        "deallocation_composition": "native_vector_deallocation_composition",
        "deallocation_conformance": "native_vector_deallocation_conformance_joined",
        "resize_conformance": "native_scalar_vector_resize_conformance",
        "growth": "native_lua_vector_growth_semantics",
        "growth_conformance": "native_scalar_vector_growth_conformance",
        "append": "native_lua_class_vector_append_semantics",
        "small_append_conformance": "native_small_vector_append_conformance",
        "scalar_append_conformance": "native_scalar_vector_append_conformance",
        "return_conformance": "native_lua_class_vector_return_conformance",
        "conformance": "native_lua_class_vector_suffix_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_sealed_native_suffix_receipt(receipts):
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
        evidence["summary"]["executed_sites"] == 304
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
        str(ROOT / "scripts/itb_native_lua_class_vector_suffix_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=600)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["conformance"].read_bytes()
