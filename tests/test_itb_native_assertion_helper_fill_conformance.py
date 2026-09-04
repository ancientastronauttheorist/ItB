"""Independent fill examples, finite-domain receipts, and immutable publication."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import itb_native_assertion_helper_fill_conformance as cli
from src.observatory import native_assertion_helper_fill_conformance as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CANONICAL = "6f4bba8750713184f5de2bf119b36605078e4386e05712a2f686b6e744801246"
RAW = "2b252e9dfa988551c8a110d90abe539f20c00bbc62bea27c34f6441d6d67bcbf"
Error = helper.ConformanceError


@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    suffixes = {
        "leaves": "native_assertion_helper_leaf_callees",
        "program_facts": "program_facts",
        "evidence": "native_assertion_helper_fill_conformance",
    }
    paths = {
        key: PROGRAMS / (PREFIX + suffix + ".json") for key, suffix in suffixes.items()
    }
    # Committed receipts are mandatory even when exact emulation is not enabled.
    loaded = {
        key: json.loads(path.read_text(encoding="utf-8")) for key, path in paths.items()
    }
    return {
        "paths": paths,
        "sources": {key: loaded[key] for key in helper.SOURCE_PINS},
        "evidence": loaded["evidence"],
    }


@pytest.mark.parametrize(
    "before,offset,length,value,expected",
    [
        (b"abcdef", 2, 3, 0x123456AB, b"ab" + bytes([171]) * 3 + b"f"),
        (b"abcdef", 1, 4, 0x100, b"a" + bytes(4) + b"f"),
        (b"abcdef", 0, 6, 0xFFFFFFFF, bytes([255]) * 6),
        (b"abcdef", 0, 0, 0, b"abcdef"),
        (b"abcdef", 6, 0, 0xFFFFFFFF, b"abcdef"),
        (b"", 0, 0, 0, b""),
    ],
)
def test_independent_spec_examples(
    before: bytes, offset: int, length: int, value: int, expected: bytes
) -> None:
    assert helper.fill_spec(before, offset, length, value) == expected


def test_spec_preserves_every_sentinel_and_uses_only_low_byte() -> None:
    before = bytes(range(256)) * 3
    for offset, length in [(1, 1), (15, 33), (17, 129), (256, 400)]:
        for value in (0, 127, 128, 255, 0xABCDEF80):
            after = helper.fill_spec(before, offset, length, value)
            assert len(after) == len(before)
            assert all(
                byte == (value % 256 if offset <= i < offset + length else before[i])
                for i, byte in enumerate(after)
            )
    assert before == bytes(range(256)) * 3


@pytest.mark.parametrize(
    "before,offset,length,value",
    [
        (bytearray(b"a"), 0, 1, 0),
        ("a", 0, 1, 0),
        (b"a", True, 0, 0),
        (b"a", 0, False, 0),
        (b"a", 0, 1, True),
        (b"a", 0.0, 1, 0),
        (b"a", 0, 1.0, 0),
        (b"a", 0, 1, 0.0),
        (b"a", -1, 0, 0),
        (b"a", 2, 0, 0),
        (b"a", 0, -1, 0),
        (b"a", 1, 1, 0),
        (b"a", 0, 2, 0),
        (b"a", 0, 1, -1),
        (b"a", 0, 1, 0x100000000),
    ],
)
def test_spec_rejects_invalid_inputs(
    before: Any, offset: Any, length: Any, value: Any
) -> None:
    with pytest.raises(Error):
        helper.fill_spec(before, offset, length, value)


def test_matrix_is_unique_deterministic_and_covers_thresholds() -> None:
    vectors = helper.cases()
    actual = set(vectors)
    assert vectors == sorted(actual) == helper.cases()
    assert len(vectors) == 14616
    modes = ((0, 0), (0, 2), (2, 0), (2, 2))
    for alignment in range(16):
        lengths = set(range(41))
        for center in (64, 96, 128, 256, 384, 512, 1024, 4096):
            lengths.update((center - 1, center, center + 1))
        for center in (144 - alignment, 400 - alignment):
            lengths.update((center - 1, center, center + 1))
        assert all(
            (alignment, length, value, rep, simd) in actual
            for length in lengths
            for value in (0, 0x123456AB, 0xFFFFFFFF)
            for rep, simd in modes
        )
        assert all(
            (alignment, length, value, rep, simd) in actual
            for length in (1, 33, 129)
            for value in (1, 127, 128, 255, 256)
            for rep, simd in modes
        )
    assert all(
        (alignment, length, 0x123456AB, rep, simd) in actual
        for alignment in (0, 1, 15)
        for length in (0, 1, 32, 33, 127, 128, 129, 512)
        for rep in (0xFFFFFFFD, 0xFFFFFFFF)
        for simd in (0xFFFFFFFD, 0xFFFFFFFF)
    )
    assert min(v[1] for v in vectors) == 0
    assert max(v[1] for v in vectors) == 4097


def test_pinned_encoding_and_structure(values: dict[str, Any]) -> None:
    evidence = values["evidence"]
    payload = values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(payload).hexdigest() == RAW
    assert helper._canonical_sha256(evidence) == CANONICAL == helper.SEALED_SHA256
    assert helper.encode_conformance(evidence).encode() == payload
    assert helper.validate_structure(evidence, values["sources"]) == {
        "status": "structurally_verified",
        "evidence_sha256": CANONICAL,
        "summary": evidence["summary"],
    }


def test_coverage_is_joined_to_sealed_cfg_and_dispatch_modes(
    values: dict[str, Any],
) -> None:
    evidence = values["evidence"]
    body = values["sources"]["leaves"]["bodies"][1]
    assert evidence["body"] == {
        "entry_rva": "0x00370960",
        "size": 346,
        "sha256": "2607fbcc1ed351e6ec2189f6d8dbc41cd852954cce218e92cd8bf4b6aa976aa9",
    }
    summary, coverage = evidence["summary"], evidence["coverage"]
    assert summary["ordinary_cases"] == 14616
    assert summary["null_zero_cases"] == 4
    assert summary["conforming_cases"] == 14620
    assert summary["negative_controls"] == 1
    declared_nodes = {node["rva"] for node in body["control_flow_graph"]["nodes"]}
    declared_edges = {
        (node["rva"], successor)
        for node in body["control_flow_graph"]["nodes"]
        for successor in node["successor_rvas"]
    }
    nodes = set(coverage["nodes"])
    edges = {tuple(edge) for edge in coverage["edges"]}
    assert len(nodes) == summary["covered_nodes"] == 89
    assert len(edges) == summary["covered_edges"] == 102
    assert len(declared_nodes) == summary["sealed_nodes"] == 89
    assert len(declared_edges) == summary["sealed_edges"] == 102
    assert nodes <= declared_nodes and edges <= declared_edges
    assert set(coverage["uncovered_nodes"]) == declared_nodes - nodes
    assert {tuple(e) for e in coverage["uncovered_edges"]} == declared_edges - edges
    assert coverage["uncovered_nodes"] == coverage["uncovered_edges"] == []
    groups = coverage["dispatch_groups"]
    assert set(groups) == {"00", "01", "10", "11"}
    for mode, group in groups.items():
        expected = sum(
            f"{(rep >> 1) & 1}{(simd >> 1) & 1}" == mode
            for _, _, _, rep, simd in helper.cases()
        )
        assert group["cases"] == expected + 1
        assert set(group["nodes"]) <= nodes
        assert {tuple(edge) for edge in group["edges"]} <= edges
    assert set().union(*(set(g["nodes"]) for g in groups.values())) == nodes
    assert (
        set().union(*({tuple(e) for e in g["edges"]} for g in groups.values())) == edges
    )
    assert evidence["vector_sha256"] == helper._canonical_sha256(
        [list(v) for v in helper.cases()]
    )
    assert (
        evidence["vector_sha256"]
        == "d108735740858467b5cc43d19765bfdb406d1e9a5aa8239fda71f17685bf6b34"
    )
    assert (
        evidence["results_sha256"]
        == "2be2bfe9321e8a80862b720685e3dc942e3ebffb48419159df28c50766703331"
    )


def test_scope_and_direction_negative_control_are_explicit(
    values: dict[str, Any],
) -> None:
    evidence = values["evidence"]
    assert evidence["emulator"]["name"] == "Unicorn"
    assert evidence["emulator"]["version"] == "2.1.4"
    assert evidence["emulator"]["native_core_version"] == [2, 1, 33621247]
    assert evidence["emulator"]["cpu_model"] == {"id": 19, "name": "UC_CPU_X86_HASWELL"}
    assert evidence["emulator"]["bits"] == 32
    assert (
        evidence["scope"]["evidence_class"] == "finite_exact_body_emulation_conformance"
    )
    assert evidence["scope"]["positive_direction_flag"] == 0
    assert (
        evidence["scope"]["specification_independent_of_native_path_algorithm"] is True
    )
    assert evidence["specification"]["direction_control"] == {
        "input_df": 1,
        "length": 128,
        "rep_word": 2,
        "simd_word": 0,
        "expected_rejection": "write escaped destination",
    }
    exclusions = " ".join(evidence["scope"]["not_claimed"])
    for phrase in (
        "real CPU",
        "CRT identity",
        "accounting promotion",
        "finite matrix",
        "address wrapping",
        "flags",
        "REP micro-iteration",
    ):
        assert phrase in exclusions


@pytest.mark.parametrize("source", list(helper.SOURCE_PINS))
def test_source_pin_rejects_mutation(values: dict[str, Any], source: str) -> None:
    sources = dict(values["sources"])
    sources[source] = dict(sources[source], unexpected=True)
    with pytest.raises(Error):
        helper.validate_structure(values["evidence"], sources)


@pytest.mark.parametrize("extra", [False, True])
def test_source_partition_is_exact(values: dict[str, Any], extra: bool) -> None:
    sources = dict(values["sources"])
    if extra:
        sources["extra"] = {}
    else:
        sources.pop("leaves")
    with pytest.raises(Error):
        helper.validate_structure(values["evidence"], sources)


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("schema_version",), True),
        (("schema_version",), 1.0),
        (("analysis_kind",), "other"),
        (("body", "size"), 345),
        (("body", "sha256"), "0" * 64),
        (("source_receipts", "leaves", "canonical_sha256"), "0" * 64),
        (("emulator", "version"), "other"),
        (("matrix", "dense_lengths"), [0, 39]),
        (("vector_sha256",), "0" * 64),
        (("results_sha256",), "0" * 64),
        (("summary", "null_zero_cases"), 0),
        (("coverage", "nodes"), []),
        (("coverage", "edges"), []),
        (("coverage", "dispatch_groups", "00", "cases"), 0),
        (("specification", "direction_control", "input_df"), 0),
        (("scope", "not_claimed"), []),
        (("unknown",), "extra"),
        (("raw_bytes",), "proprietary"),
    ],
)
def test_receipt_seal_rejects_tampering(
    values: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    path: tuple[str, ...],
    replacement: Any,
) -> None:
    # Keep the real JSON and seal checks; source pin rejection has separate tests.
    monkeypatch.setattr(
        helper, "_preflight", lambda _: values["evidence"]["source_receipts"]
    )
    changed = copy.deepcopy(values["evidence"])
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    with pytest.raises(Error):
        helper.validate_structure(changed, values["sources"])


def _args(values: dict[str, Any], command: str = "verify-structure") -> list[str]:
    args = [command, "--evidence", str(values["paths"]["evidence"])]
    for name in helper.SOURCE_PINS:
        args += ["--" + name.replace("_", "-"), str(values["paths"][name])]
    return args


def _writer_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = tmp_path.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("immutable publication must not delete a pathname")

    monkeypatch.setattr(cli.os, "unlink", forbidden)
    monkeypatch.setattr(Path, "unlink", forbidden)


def test_writer_idempotence_and_no_overwrite(
    values: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _writer_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = cli.encode(values["evidence"])
    cli._write_immutably(output, rendered, values["evidence"])
    identity = output.stat().st_ino
    cli._write_immutably(output, rendered, values["evidence"])
    assert output.stat().st_ino == identity
    stage = cli._retained_stage_path(tmp_path, rendered.encode())
    assert os.path.samefile(stage, output)
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(rendered.encode() + b" ")
    os.replace(replacement, output)
    with pytest.raises(Error, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode() + b" "
    assert stage.read_bytes() == rendered.encode()


@pytest.mark.parametrize("matching", [True, False])
def test_writer_retains_concurrent_winner(
    values: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    matching: bool,
) -> None:
    _writer_root(monkeypatch, tmp_path)
    output = tmp_path / "winner.json"
    rendered = cli.encode(values["evidence"])
    winner = rendered.encode() if matching else rendered.encode() + b" "

    def concurrent_create(source: Path, destination: Path, **kwargs: Any) -> None:
        destination.write_bytes(winner)
        raise FileExistsError("another publisher won")

    monkeypatch.setattr(cli.os, "link", concurrent_create)
    if matching:
        cli._write_immutably(output, rendered, values["evidence"])
    else:
        with pytest.raises(Error, match="refusing to overwrite"):
            cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == winner
    assert (
        cli._retained_stage_path(tmp_path, rendered.encode()).read_bytes()
        == rendered.encode()
    )


def test_writer_rejects_replaced_stage_identity(
    values: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _writer_root(monkeypatch, tmp_path)
    output = tmp_path / "race.json"
    rendered = cli.encode(values["evidence"])
    contender = tmp_path / "contender.json"
    contender.write_bytes(rendered.encode())
    original_link = cli.os.link

    def replace_then_link(source: Path, destination: Path, **kwargs: Any) -> None:
        os.replace(contender, source)
        original_link(source, destination, **kwargs)

    monkeypatch.setattr(cli.os, "link", replace_then_link)
    with pytest.raises(Error, match="identity check"):
        cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode()


def test_writer_rejects_unsealed_evidence_before_creating_files(
    values: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _writer_root(monkeypatch, tmp_path)
    changed = dict(values["evidence"], schema_version=True)
    with pytest.raises(Error, match="sealed conformance identity"):
        cli._write_immutably(tmp_path / "bad.json", cli.encode(changed), changed)
    assert list(tmp_path.iterdir()) == []


def test_cli_structure_is_deterministic_without_emulator(
    values: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden() -> None:
        raise AssertionError("structural verification must not load the emulator")

    monkeypatch.setattr(helper, "_runtime", forbidden)
    assert cli.main(_args(values)) == 0
    first = capsys.readouterr()
    assert first.err == ""
    assert json.loads(first.out)["status"] == "structurally_verified"
    assert cli.main(_args(values)) == 0
    second = capsys.readouterr()
    assert second.out == first.out and second.err == ""


@pytest.mark.parametrize(
    "payload", [b"{bad json", b'{"schema_version":1,"schema_version":1}', b"[]"]
)
def test_cli_rejects_malformed_evidence(
    values: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    payload: bytes,
) -> None:
    evidence = tmp_path / "bad.json"
    evidence.write_bytes(payload)
    args = _args(values)
    args[2] = str(evidence)
    assert cli.main(args) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "error:" in captured.err


def test_exact_cli_replay(values: dict[str, Any]) -> None:
    configured = os.environ.get("ITB_EXACT_EXE")
    if not configured:
        pytest.skip("set ITB_EXACT_EXE and install Unicorn 2.1.4 for exact replay")
    executable = Path(configured)
    assert hashlib.sha256(executable.read_bytes()).hexdigest() == helper.EXE_SHA256
    # CLI verify rebuilds the whole matrix and compares the sealed receipt.
    # Keep Unicorn outside pytest's faulthandler: its Windows first-chance
    # exceptions otherwise produce spurious access-violation diagnostics.
    # The child inherits PYTHONPATH, and a missing runtime fails rather than skips.
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_assertion_helper_fill_conformance.py"),
            *_args(values, "verify"),
            "--executable",
            str(executable),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "verified"
