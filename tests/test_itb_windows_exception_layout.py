"""Independent x86 layout, partial stores and SDK measurement parsing."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.observatory import windows_exception_layout as layout
from scripts import itb_windows_exception_layout as cli

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.fixture(scope="module")
def evidence_chain():
    paths = {
        "stores": PROGRAMS / (PREFIX + "native_assertion_helper_frame_stores.json"),
        "handoff": PROGRAMS / (PREFIX + "native_assertion_helper_import_handoff.json"),
        "evidence": PROGRAMS / (PREFIX + "windows_exception_layout.json"),
    }
    loaded = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, {k: loaded[k] for k in layout.SOURCE_PINS}, loaded["evidence"]


def test_receipt_identity(evidence_chain):
    paths, sources, evidence = evidence_chain
    assert (
        layout._canonical_sha256(evidence)
        == "c71a3142e5fc172a6a686a1b83f3bce3a9af181142c8386276ed481f2861acef"
    )
    assert (
        hashlib.sha256(paths["evidence"].read_bytes()).hexdigest()
        == "dc11ac81b491707444e5b54cbe6edbf8b25d9985b757d9e4fe4c444e8fb5cd55"
    )
    assert layout.encode_layout(evidence).encode() == paths["evidence"].read_bytes()
    assert (
        layout.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("raw_bytes", "private"),
        ("sdk_layout", {}),
        ("frame_overlap", {}),
        ("scope", {}),
        ("summary", {}),
    ],
)
def test_receipt_mutation_rejected(evidence_chain, key, value):
    _, sources, evidence = evidence_chain
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(layout.LayoutError):
        layout.validate_structure(changed, sources)


@pytest.mark.parametrize("key", ["stores", "handoff"])
def test_source_mutation_rejected(evidence_chain, key):
    _, sources, evidence = evidence_chain
    changed = dict(sources)
    changed[key] = dict(sources[key], extra=0)
    with pytest.raises(layout.LayoutError):
        layout.validate_structure(evidence, changed)


def cli_args(evidence_chain, command):
    paths, _, _ = evidence_chain
    return [
        command,
        "--evidence",
        str(paths["evidence"]),
        "--stores",
        str(paths["stores"]),
        "--handoff",
        str(paths["handoff"]),
    ]


def test_structure_check_requires_no_windows_compiler(
    evidence_chain, monkeypatch, capsys
):
    def forbidden():
        raise AssertionError("structure check must not compile")

    monkeypatch.setattr(layout, "_probe", forbidden)
    assert cli.main(cli_args(evidence_chain, "verify-structure")) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out)["status"] == "structurally_verified"


def test_exact_sdk_probe(evidence_chain):
    if os.environ.get("ITB_EXACT_SDK") != "1":
        pytest.skip("set ITB_EXACT_SDK=1 to compile the pinned x86 SDK probe")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_windows_exception_layout.py"),
            *cli_args(evidence_chain, "verify"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "verified"
    # Raw capture catches Windows stdout CRLF changes hidden by text=True.
    paths, _, _ = evidence_chain
    built = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_windows_exception_layout.py"),
            "build",
            "--stores",
            str(paths["stores"]),
            "--handoff",
            str(paths["handoff"]),
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=120,
    )
    assert built.returncode == 0, built.stderr
    assert built.stderr == b""
    assert built.stdout == paths["evidence"].read_bytes()
    assert b"\r\n" not in built.stdout


def independent_measurements():
    values = {
        "pointer": 4,
        "CONTEXT_CONTROL": 65537,
        "CONTEXT": 716,
        "EXCEPTION_RECORD": 80,
        "EXCEPTION_POINTERS": 8,
    }
    fields = {
        "CONTEXT": [
            ("ContextFlags", 0, 4),
            ("Dr0", 4, 4),
            ("Dr1", 8, 4),
            ("Dr2", 12, 4),
            ("Dr3", 16, 4),
            ("Dr6", 20, 4),
            ("Dr7", 24, 4),
            ("FloatSave", 28, 112),
            ("SegGs", 140, 4),
            ("SegFs", 144, 4),
            ("SegEs", 148, 4),
            ("SegDs", 152, 4),
            ("Edi", 156, 4),
            ("Esi", 160, 4),
            ("Ebx", 164, 4),
            ("Edx", 168, 4),
            ("Ecx", 172, 4),
            ("Eax", 176, 4),
            ("Ebp", 180, 4),
            ("Eip", 184, 4),
            ("SegCs", 188, 4),
            ("EFlags", 192, 4),
            ("Esp", 196, 4),
            ("SegSs", 200, 4),
            ("ExtendedRegisters", 204, 512),
        ],
        "EXCEPTION_RECORD": [
            ("ExceptionCode", 0, 4),
            ("ExceptionFlags", 4, 4),
            ("ExceptionRecord", 8, 4),
            ("ExceptionAddress", 12, 4),
            ("NumberParameters", 16, 4),
            ("ExceptionInformation", 20, 60),
        ],
        "EXCEPTION_POINTERS": [("ExceptionRecord", 0, 4), ("ContextRecord", 4, 4)],
    }
    for name, rows in fields.items():
        for field, offset, width in rows:
            values[name + "." + field] = [offset, width]
    return values


def rendered(measurements):
    return (
        "\n".join(
            k + "=" + (",".join(map(str, v)) if isinstance(v, list) else str(v))
            for k, v in measurements.items()
        )
        + "\n"
    )


def test_sdk_independent_measurement_partition():
    measured = independent_measurements()
    assert layout.parse_probe(rendered(measured)) == measured
    spec = layout.sdk_layout_spec()
    assert spec["pointer_size"] == 4
    assert spec["constants"] == {"CONTEXT_CONTROL": 65537}
    for name, record in spec["structures"].items():
        assert record["size"] == measured[name]
        assert sum(f["width"] for f in record["fields"]) == record["size"]
        for field in record["fields"]:
            assert [field["offset"], field["width"]] == measured[
                name + "." + field["name"]
            ]


@pytest.mark.parametrize(
    "key,replacement",
    [
        ("pointer", 8),
        ("CONTEXT", 1232),
        ("CONTEXT_CONTROL", 65539),
        ("CONTEXT.SegSs", [200, 2]),
        ("CONTEXT.Eax", [180, 4]),
        ("EXCEPTION_RECORD.ExceptionInformation", [20, 64]),
    ],
)
def test_wrong_abi_measurements_rejected(key, replacement):
    measured = independent_measurements()
    measured[key] = replacement
    with pytest.raises(layout.LayoutError):
        layout.parse_probe(rendered(measured))


@pytest.mark.parametrize("suffix", ["pointer=4\n", "extra=1\n", "broken\n"])
def test_extra_duplicate_or_malformed_measurement_rejected(suffix):
    with pytest.raises(layout.LayoutError):
        layout.parse_probe(rendered(independent_measurements()) + suffix)


def test_missing_measurement_rejected():
    measured = independent_measurements()
    measured.pop("CONTEXT.Eax")
    with pytest.raises(layout.LayoutError):
        layout.parse_probe(rendered(measured))


def test_all_frame_stores_match_unique_fields_without_widening():
    result = layout.frame_overlap_spec()
    rows = result["stores"]
    assert len(rows) == 22
    assert len({r["frame_offset"] for r in rows}) == 22
    assert sum(r["store_width"] for r in rows) == 76
    words = {r["sdk_field"]: r for r in rows if r["store_width"] == 2}
    assert set(words) == {"SegGs", "SegFs", "SegEs", "SegDs", "SegCs", "SegSs"}
    assert all(
        r["field_width"] == 4 and r["unwritten_upper_bytes"] == 2
        for r in words.values()
    )
    counts = {
        name: sum(r["sdk_structure"] == name for r in rows)
        for name in ["CONTEXT", "EXCEPTION_RECORD", "EXCEPTION_POINTERS"]
    }
    assert counts == {"CONTEXT": 17, "EXCEPTION_RECORD": 3, "EXCEPTION_POINTERS": 2}
    eax = next(r for r in rows if r["sdk_field"] == "Eax")
    assert eax["frame_offset"] == -544 and eax["source"] == "frame_minus_720"
    assert result["temporary_outside_records"] == [
        {"frame_offset": -816, "width": 4, "source": "pushed_flags_image"}
    ]


def test_probe_is_queries_not_redeclared_sdk():
    source = layout.probe_source()
    assert "#include <windows.h>" in source
    assert "offsetof" in source and "sizeof" in source
    assert "typedef" not in source
