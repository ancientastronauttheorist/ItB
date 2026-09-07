"""Growth capacity requests, spare storage and complete ancestor-frame contract."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_small_vector_growth_conformance as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


def vector(size, capacity, requested, has_old=True):
    return dict(
        has_old=has_old,
        old_size=size,
        old_capacity=capacity,
        requested=requested,
        new_alignment=7,
        old_alignment=3,
        stack_alignment=15,
    )


@pytest.mark.parametrize("size,requested", [(0, 1), (1, 2), (2, 3), (3, 4)])
def test_full_capacity_uses_checked_growth_request(size, requested):
    value = helper.geometry(vector(size, size, requested))
    assert value["grows"] and value["request"] == 8 * requested
    assert value["new_end"] - value["new_begin"] == 8 * size


@pytest.mark.parametrize("size", range(4))
def test_spare_capacity_preserves_all_vector_pointers(size):
    value = helper.geometry(vector(size, 4, size))
    assert not value["grows"] and value["request"] is None
    for suffix in ("begin", "end", "capacity"):
        assert value["new_" + suffix] == value["old_" + suffix]


def test_null_empty_vector_requires_allocation_but_no_free():
    value = helper.geometry(vector(0, 0, 1, False))
    assert value["old_begin"] == 0 and value["new_begin"] > 0 and value["grows"]


@pytest.mark.parametrize("g", [96, 0x20002000, 0x2000200F, 2**32 - 9])
def test_unused_argument_is_consumed_after_nested_resize(g):
    frame = helper.frame_join(g)
    assert frame["resize_entry"] == g - 20
    assert (
        frame["heap_allocation_entry"] == g - 96 and frame["heap_free_entry"] == g - 88
    )
    assert frame["returned"] == g + 8 and frame["protected_end"] == g + 8


@pytest.mark.parametrize(
    "value", [vector(3, 3, 3), vector(3, 5, 3), vector(4, 4, 6), vector(1, 1, 2, False)]
)
def test_outside_growth_domain_rejected(value):
    with pytest.raises(helper.ConformanceError):
        helper.geometry(value)


def test_matrix_keeps_growth_and_spare_paths_distinct():
    values = helper.vectors()
    assert len(values) == 1152
    assert sum(helper.geometry(v)["grows"] for v in values) == 640
    assert sum(helper.geometry(v)["grows"] and v["has_old"] for v in values) == 512


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "owner": "native_vector_resize_semantics",
        "allocation_composition": "native_vector_allocation_composition",
        "allocation_conformance": "native_vector_allocation_conformance",
        "small_copy": "native_small_copy_semantics",
        "deallocation_composition": "native_vector_deallocation_composition",
        "deallocation_conformance": "native_vector_deallocation_conformance_joined",
        "resize_conformance": "native_small_vector_resize_conformance",
        "growth": "native_lua_vector_growth_semantics",
        "conformance": "native_small_vector_growth_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_sealed_native_growth_receipt(receipts):
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
        evidence["summary"]["executed_sites"] == 198
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
        str(ROOT / "scripts/itb_native_small_vector_growth_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["conformance"].read_bytes()
