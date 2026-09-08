"""Attachment extrema, count rejection, preserved node bytes and exact replay."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_tree_attachment_conformance as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


def read(pages, address, width=4):
    return int.from_bytes(
        bytes(
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] for i in range(width)
        ),
        "little",
    )


@pytest.mark.parametrize(
    "count,accepted",
    [
        (0, True),
        (helper.LIMIT - 1, True),
        (helper.LIMIT, False),
        (helper.LIMIT + 1, False),
        (0x80000000, False),
        (0xFFFFFFFF, False),
    ],
)
def test_unsigned_count_guard(count, accepted):
    assert helper.guard_spec(count)["accepted"] is accepted


@pytest.mark.parametrize("count", [-1, 2**32, True, 1.5])
def test_invalid_count_rejected(count):
    with pytest.raises(helper.ConformanceError):
        helper.guard_spec(count)


@pytest.mark.parametrize(
    "profile",
    [
        "empty",
        "root_left",
        "root_right",
        "min_left",
        "max_right",
        "max_left",
        "min_right",
    ],
)
def test_attachment_updates_only_selected_links_and_extrema(profile):
    v = next(v for v in helper.vectors() if v["profile"] == profile)
    f = helper._fixture(v)
    e = helper._expected(v, f)
    p = f["node"]
    assert read(e["pages"], helper.TREE + 4) == v["count"] + 1
    assert read(e["pages"], p + 4) == f["parent"]
    assert read(e["pages"], p + 12, 12) == read(f["pages"], p + 12, 12)
    if profile == "empty":
        assert [read(e["pages"], helper.HEAD + i) for i in (0, 4, 8)] == [p] * 3
        assert all(event["address"] != f["s"] + 8 for event in e["events"])
    else:
        offset = 0 if v["selector"] else 8
        assert read(e["pages"], f["parent"] + offset) == p
        changed = profile in ("root_left", "root_right", "min_left", "max_right")
        assert read(e["pages"], helper.HEAD + offset) == (
            p if changed else read(f["pages"], helper.HEAD + offset)
        )
    assert e["endpoint"] == helper.BASE + helper.STOP
    assert e["registers"]["esp"] == f["s"] - 12


@pytest.mark.parametrize(
    "count", [helper.LIMIT, helper.LIMIT + 1, 0x80000000, 0xFFFFFFFF]
)
def test_rejection_does_not_access_node_or_arguments(count):
    v = next(
        v for v in helper.vectors() if v["profile"] == "failure" and v["count"] == count
    )
    f = helper._fixture(v)
    e = helper._expected(v, f)
    assert e["endpoint"] == helper.BASE + helper.FAILURE
    assert [event["address"] for event in e["events"] if event["access"] == "read"] == [
        helper.TREE + 4
    ]
    assert e["pages"][helper.TREE] == f["pages"][helper.TREE]
    assert helper.DATA not in f["pages"]


@pytest.fixture(scope="module")
def receipts():
    paths = {
        k: PROGRAMS / (PREFIX + suffix + ".json")
        for k, suffix in {
            "program_facts": "program_facts",
            "conformance": "native_tree_attachment_conformance",
        }.items()
    }
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {"program_facts": data["program_facts"]}


def test_sealed_receipt(receipts):
    paths, data, sources = receipts
    assert (
        helper.validate_structure(data["conformance"], sources)["status"]
        == "structurally_verified"
    )
    assert (
        helper.encode_conformance(data["conformance"]).encode()
        == paths["conformance"].read_bytes()
    )
    assert data["conformance"]["summary"]["executed_sites"] == 35


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
    paths, _, _ = receipts
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_tree_attachment_conformance.py"),
            "build",
            "--executable",
            executable,
            "--program-facts",
            str(paths["program_facts"]),
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["conformance"].read_bytes()
