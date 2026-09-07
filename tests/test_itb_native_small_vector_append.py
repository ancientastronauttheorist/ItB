"""Relocated append arguments and complete native ancestor-frame contract."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_small_vector_append_conformance as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


def vector(size=2, capacity=2, kind="internal", index=1):
    return dict(
        has_old=True,
        old_size=size,
        old_capacity=capacity,
        requested=max(size + 1, capacity + capacity // 2) if size == capacity else size,
        new_alignment=7,
        old_alignment=3,
        stack_alignment=15,
        argument_kind=kind,
        internal_index=index,
    )


@pytest.mark.parametrize("size", [1, 2, 3])
@pytest.mark.parametrize("grow", [False, True])
def test_internal_argument_tracks_element_across_relocation(size, grow):
    v = vector(size, size if grow else 4, index=size - 1)
    g = helper.geometry(v)
    assert g["source"] == g["new_begin"] + 8 * (size - 1)
    assert (g["source"] != g["argument"]) == grow
    assert g["destination"] == g["new_begin"] + 8 * size
    assert g["final_end"] == g["destination"] + 8 <= g["new_capacity"]


@pytest.mark.parametrize("kind", ["external_low", "external_high"])
def test_external_argument_remains_independent_of_growth(kind):
    g = helper.geometry(vector(kind=kind, index=0))
    assert g["source"] == g["argument"]
    assert not helper.OLD <= g["source"] < helper.OLD + 0x4000
    assert not helper.NEW <= g["source"] < helper.NEW + 0x4000


@pytest.mark.parametrize("s", [104, 0x20002000, 0x2000200F, 2**32 - 49])
def test_nested_calls_preserve_append_frame_local_and_stack_position(s):
    f = helper.frame_join(s)
    assert f["owner_local"] == f["frame"] - 12 == s + 20
    assert f["growth_entry"] == s - 8 and f["resize_entry"] == s - 28
    assert f["heap_allocation_entry"] == s - 104 and f["heap_free_entry"] == s - 96
    assert f["exit_esp"] == s
    assert f["protected_start"] <= s - 104 and f["protected_end"] >= s + 24


@pytest.mark.parametrize(
    "update",
    [
        {"internal_index": -1},
        {"internal_index": 2},
        {"internal_index": True},
        {"argument_kind": "other"},
        {"argument_kind": "external_low", "internal_index": 1},
        {"old_size": 4, "old_capacity": 4, "requested": 6},
    ],
)
def test_unproven_arguments_rejected(update):
    v = vector()
    v.update(update)
    with pytest.raises(helper.ConformanceError):
        helper.geometry(v)


def test_matrix_covers_internal_and_both_external_classifications():
    values = helper.vectors()
    assert len(values) == 3584
    assert {v["argument_kind"] for v in values} == {
        "internal",
        "external_low",
        "external_high",
    }
    assert any(not v["has_old"] for v in values)
    assert all(
        helper.geometry(v)["final_end"] <= helper.geometry(v)["new_capacity"]
        for v in values
    )


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
        "growth_conformance": "native_small_vector_growth_conformance",
        "append": "native_lua_class_vector_append_semantics",
        "conformance": "native_small_vector_append_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_sealed_native_append_receipt(receipts):
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
        evidence["summary"]["executed_sites"] == 234
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
        str(ROOT / "scripts/itb_native_small_vector_append_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["conformance"].read_bytes()
