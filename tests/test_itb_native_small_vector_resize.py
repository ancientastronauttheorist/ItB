"""Joined native resize storage, deepest frames and source-sealed replay."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_small_vector_resize_conformance as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


def vector(**changes):
    value = dict(
        has_old=True,
        old_size=3,
        old_capacity=512,
        requested=513,
        new_alignment=0,
        old_alignment=0,
        stack_alignment=0,
    )
    value.update(changes)
    return value


@pytest.mark.parametrize("alignment", range(32))
def test_large_metadata_and_payload_extents_fit_mapped_blocks(alignment):
    g = helper.geometry(vector(new_alignment=alignment, old_alignment=alignment))
    assert g["new_begin"] % 32 == g["old_begin"] % 32 == 0
    assert 4 <= g["new_begin"] - g["new_raw"] <= 35
    assert 4 <= g["old_begin"] - g["old_raw"] <= 35
    assert (
        g["new_metadata"] == g["new_begin"] - 4
        and g["old_metadata"] == g["old_begin"] - 4
    )
    assert g["copy_bytes"] == 24 and g["new_end"] - g["new_begin"] == 24
    assert g["new_capacity"] <= g["new_raw"] + g["request"]


@pytest.mark.parametrize("has_old", [False, True])
def test_zero_requested_storage_has_no_heap_allocation(has_old):
    g = helper.geometry(
        vector(has_old=has_old, old_size=0, old_capacity=0, requested=0)
    )
    assert (
        g["request"] is None
        and g["new_begin"] == g["new_end"] == g["new_capacity"] == 0
    )
    assert bool(g["old_begin"]) == has_old


@pytest.mark.parametrize("s", [76, 0x20002000, 0x2000200F, 2**32 - 9])
def test_nested_api_and_copy_frames_are_freshly_rebased(s):
    frame = helper.frame_join(s)
    assert frame["heap_allocation_entry"] == s - 76
    assert frame["copy_saved_esi"] == s - 44 and frame["copy_saved_edi"] == s - 40
    assert frame["heap_free_entry"] == s - 68 and frame["returned"] == s + 8


@pytest.mark.parametrize(
    "changes",
    [
        dict(old_size=4),
        dict(requested=2),
        dict(old_capacity=513),
        dict(has_old=False),
        dict(new_alignment=32),
        dict(stack_alignment=True),
        dict(requested=514),
    ],
)
def test_outside_integrated_domain_rejected(changes):
    with pytest.raises(helper.ConformanceError):
        helper.geometry(vector(**changes))


def test_matrix_pairing_covers_each_block_alignment_without_full_cross_claim():
    values = helper.vectors()
    assert len(values) == 5120
    assert {v["new_alignment"] for v in values} == set(range(32))
    assert {v["old_alignment"] for v in values} == set(range(32))
    assert len({(v["new_alignment"], v["old_alignment"]) for v in values}) == 32


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "owner": "native_vector_resize_semantics",
        "allocation_composition": "native_vector_allocation_composition",
        "allocation_conformance": "native_vector_allocation_conformance",
        "small_copy": "native_small_copy_semantics",
        "deallocation_composition": "native_vector_deallocation_composition",
        "deallocation_conformance": "native_vector_deallocation_conformance_joined",
        "conformance": "native_small_vector_resize_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_integrated_receipt_only_summarizes_heap_apis(receipts):
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
    assert evidence["summary"]["executed_sites"] == 187
    assert evidence["summary"]["allocation_api_summaries"] == 4608
    assert evidence["summary"]["free_api_summaries"] == 4608
    assert evidence["summary"]["opaque_instructions"] == 0


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
        str(ROOT / "scripts/itb_native_small_vector_resize_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=600)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["conformance"].read_bytes()
