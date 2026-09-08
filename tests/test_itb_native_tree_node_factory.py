"""Relocated append arguments and complete native ancestor-frame contract."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_tree_node_factory_conformance as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize(
    "n", [60, helper.STACK + 0x2000, helper.STACK + 0x200F, 2**32 - 17]
)
def test_factory_reaches_heap_and_consumes_three_arguments(n):
    f = helper.frame_join(n)
    assert f["initializer"] == n - 8 and f["retry"] == n - 24
    assert f["heap_api"] == n - 60 and f["returned"] == n + 16


@pytest.mark.parametrize("alignment", range(32))
def test_header_clear_preserves_padding_and_sets_three_head_links(alignment):
    v = dict(
        alignment=alignment, frame_alignment=7, head=0x87654321, key=0xABCDEF01, seed=7
    )
    fixture = helper._fixture(v)
    expected = helper._expected(v, fixture)
    at = fixture["p"] - helper.DATA
    block = expected["data"][at : at + 24]
    assert block[:12] == v["head"].to_bytes(4, "little") * 3
    assert block[12:14] == b"\0\0"
    assert block[14:16] == fixture["data"][at + 14 : at + 16]
    assert block[16:20] == v["key"].to_bytes(4, "little") and block[20:24] == bytes(4)
    assert expected["data"][:at] == fixture["data"][:at]
    assert expected["data"][at + 24 :] == fixture["data"][at + 24 :]
    assert expected["registers"]["eax"] == fixture["p"]
    assert expected["registers"]["edx"] == fixture["p"] + 16


@pytest.mark.parametrize(
    "update",
    [
        {"alignment": 32},
        {"frame_alignment": True},
        {"head": -1},
        {"key": 2**32},
        {"seed": 16},
    ],
)
def test_unmodeled_geometry_and_words_rejected(update):
    v = helper.vectors()[0]
    v.update(update)
    with pytest.raises(helper.ConformanceError):
        helper._fixture(v)


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "allocation_conformance": "native_vector_allocation_conformance",
        "conformance": "native_tree_node_factory_conformance",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_sealed_factory_receipt(receipts):
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
        evidence["summary"]["executed_sites"] == 73
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
        str(ROOT / "scripts/itb_native_tree_node_factory_conformance.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["conformance"].read_bytes()
