"""Independent boundary expectations and immutable end-to-end receipts."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import itb_native_assertion_helper_import_handoff as cli
from src.observatory import native_assertion_helper_import_handoff as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
        + b"\n"
    ).hexdigest()


@pytest.fixture(scope="module")
def values():
    suffixes = {
        "pair": "native_assertion_helper_descendant_pair",
        "leaves": "native_assertion_helper_leaf_callees",
        "conformance": "native_assertion_helper_fill_conformance",
        "program_facts": "program_facts",
        "caller": "native_assertion_helper_caller_fill",
        "stores": "native_assertion_helper_frame_stores",
        "evidence": "native_assertion_helper_import_handoff",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffixes.items()}
    loaded = {k: json.loads(v.read_text(encoding="utf-8")) for k, v in paths.items()}
    return (
        paths,
        {k: loaded[k] for k in suffixes if k != "evidence"},
        loaded["evidence"],
    )


def test_matrix_independently_enumerates_caller_inputs():
    expected = [
        (a, r, s, v, c)
        for a, (r, s), v, c in itertools.product(
            range(16),
            [(0, 0), (0, 2), (2, 0), (2, 2)],
            [0, 0xFFFFFFFF],
            [0, 0x6B8B4567],
        )
    ]
    assert helper.cases() == expected
    assert len(set(expected)) == 256


@pytest.mark.parametrize(
    "alignment,flags",
    enumerate([22, 18, 18, 22, 6, 2, 2, 6, 2, 6, 6, 2, 18, 22, 22, 18]),
)
@pytest.mark.parametrize("rep,simd", [(0, 0), (0, 2), (2, 0), (2, 2)])
def test_independent_boundary_values(alignment, flags, rep, simd):
    result = helper.boundary_spec(0x02002000 + alignment, rep, simd)
    assert result["ecx"] == ((28 + alignment) % 32 if rep == 0 and simd == 2 else 0)
    assert result["edx"] == 0x3456789A
    assert result["eflags"] == flags
    assert result["eax"] == 0x02002000 + alignment - 800
    assert result["esp"] == 0x02002000 + alignment - 812
    assert result["ebp"] == 0x02002000 + alignment


@pytest.mark.parametrize(
    "frame,rep,simd",
    [
        (True, 0, 0),
        (0x02002000 - 1, 0, 0),
        (0x02002010, 0, 0),
        (float(0x02002000), 0, 0),
        (0x02002000, True, 0),
        (0x02002000, 0, False),
        (0x02002000, 1, 0),
        (0x02002000, 0, 3),
    ],
)
def test_boundary_spec_rejects_outside_declared_matrix(frame, rep, simd):
    with pytest.raises(helper.HandoffError):
        helper.boundary_spec(frame, rep, simd)


def test_receipt_boundary_values_and_writers(values):
    _, _, evidence = values
    observations = evidence["boundary_observations"]
    assert [r["vector"] for r in observations] == [list(v) for v in helper.cases()]
    flags = [22, 18, 18, 22, 6, 2, 2, 6, 2, 6, 6, 2, 18, 22, 22, 18]
    for row in observations:
        a, rep, simd, _, _ = row["vector"]
        frame = 0x02002000 + a
        assert row["values"] == {
            "eax": frame - 800,
            "ebp": frame,
            "esp": frame - 812,
            "ecx": (28 + a) % 32 if rep == 0 and simd == 2 else 0,
            "edx": 0x3456789A,
            "eflags": flags[a],
        }
        assert row["last_writers"] == {
            "ecx": "0x0037099c" if rep else "0x00370a41" if simd else "0x00370aa8",
            "edx": "0x00370969",
            "eflags": "0x00379d76",
        }
    prefix = evidence["prefix"]
    assert (prefix["entry_rva"], prefix["join_rva"], prefix["exclusive_stop_rva"]) == (
        "0x00379d28",
        "0x00379d79",
        "0x00379e20",
    )
    assert prefix["size"] == 248
    assert len(prefix["points"]) == 55
    assert "0x00379e20" not in evidence["visited_rvas"]
    assert sum(p["size"] for p in prefix["points"]) == 248
    assert (
        evidence["negative_control"]["expected_rejection"] == "handoff register differs"
    )


def test_receipt_source_joins(values):
    paths, sources, evidence = values
    assert digest(evidence) == helper.SEALED_SHA256
    assert (
        digest(evidence)
        == "21ed5942d039ec0e16c94f40447f0e15bebea6d74298a1af448eb93f55ce7712"
    )
    assert (
        hashlib.sha256(paths["evidence"].read_bytes()).hexdigest()
        == "c8262ccee8149477fc52f49e5a5fdc22cf4b7d6898f1eea26a763ab169c7af39"
    )
    assert helper.encode_handoff(evidence).encode() == paths["evidence"].read_bytes()
    assert evidence["build_identity"] == sources["program_facts"]["identity"]
    for key, (kind, sha) in helper.SOURCE_PINS.items():
        assert digest(sources[key]) == sha
        assert evidence["source_receipts"][key] == {
            "analysis_kind": kind,
            "canonical_sha256": sha,
        }
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )


@pytest.mark.parametrize(
    "key", ["pair", "leaves", "conformance", "program_facts", "caller", "stores"]
)
def test_source_mutation_rejected(values, key):
    _, sources, evidence = values
    changed = dict(sources)
    changed[key] = dict(sources[key], unexpected=True)
    with pytest.raises(helper.HandoffError):
        helper.validate_structure(evidence, changed)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("schema_version", 1.0),
        ("analysis_kind", "other"),
        ("results_sha256", "0" * 64),
        ("vector_sha256", "0" * 64),
        ("raw_bytes", "private"),
        ("summary", {}),
        ("scope", {}),
    ],
)
def test_receipt_mutations_rejected(values, key, value):
    _, sources, evidence = values
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.HandoffError):
        helper.validate_structure(changed, sources)


def args(values, command="verify-structure"):
    paths, sources, _ = values
    result = [command, "--evidence", str(paths["evidence"])]
    for key in sources:
        result += ["--" + key.replace("_", "-"), str(paths[key])]
    return result


def test_cli_structure_without_runtime(values, monkeypatch, capsys):
    def forbidden(*a, **kw):
        raise AssertionError("structure check loaded emulator")

    from src.observatory import native_assertion_helper_caller_fill as caller

    monkeypatch.setattr(caller, "_runtime", forbidden)
    assert cli.main(args(values)) == 0
    first = capsys.readouterr()
    assert first.err == ""
    assert json.loads(first.out)["status"] == "structurally_verified"
    assert cli.main(args(values)) == 0
    assert capsys.readouterr() == first


def test_publication_is_immutable(values, monkeypatch, tmp_path):
    _, _, evidence = values
    monkeypatch.setattr(
        cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, tmp_path.stat())
    )
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *a: None)
    output = tmp_path / "handoff.json"
    rendered = helper.encode_handoff(evidence)
    cli._write_immutably(output, rendered, evidence)
    inode = output.stat().st_ino
    cli._write_immutably(output, rendered, evidence)
    assert output.stat().st_ino == inode
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(rendered.encode() + b" ")
    os.replace(replacement, output)
    with pytest.raises(helper.HandoffError):
        cli._write_immutably(output, rendered, evidence)
    assert output.read_bytes() == rendered.encode() + b" "
    assert (
        cli._retained_stage_path(tmp_path, rendered.encode()).read_bytes()
        == rendered.encode()
    )


@pytest.mark.parametrize("payload", [b"{bad", b"[]", b'{"a":1,"a":2}'])
def test_malformed_cli_receipt_rejected(values, tmp_path, capsys, payload):
    evidence = tmp_path / "bad.json"
    evidence.write_bytes(payload)
    arguments = args(values)
    arguments[2] = str(evidence)
    assert cli.main(arguments) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "error:" in captured.err


def test_exact_cli_replay(values):
    configured = os.environ.get("ITB_EXACT_EXE")
    if not configured:
        pytest.skip("set ITB_EXACT_EXE and install Unicorn 2.1.4 for exact replay")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(
            None,
            [
                str(ROOT / ".local_decompile/fill_runtime"),
                environment.get("PYTHONPATH", ""),
            ],
        )
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_assertion_helper_import_handoff.py"),
            *args(values, "verify"),
            "--executable",
            configured,
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "verified"
