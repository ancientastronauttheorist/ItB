"""Independent caller frame arithmetic, sealed receipts and safe publication."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import itb_native_assertion_helper_caller_fill as cli
from src.observatory import native_assertion_helper_caller_fill as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CANONICAL = "b89d1873e56c4afb27c96229c05a1a0516732a5bdc3d2151173baeb5d4a5b653"
RAW = "4206855ecf4c727e3a85ab9bb8fa5c2f37ecb1c51b2f7eb1f696c049d9754d48"
Error = helper.CallerError


def _digest(value: Any) -> str:
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
def values() -> dict[str, Any]:
    suffixes = {
        "pair": "native_assertion_helper_descendant_pair",
        "leaves": "native_assertion_helper_leaf_callees",
        "conformance": "native_assertion_helper_fill_conformance",
        "program_facts": "program_facts",
        "evidence": "native_assertion_helper_caller_fill",
    }
    paths = {
        key: PROGRAMS / (PREFIX + suffix + ".json") for key, suffix in suffixes.items()
    }
    loaded = {
        key: json.loads(path.read_text(encoding="utf-8")) for key, path in paths.items()
    }
    return {
        "paths": paths,
        "sources": {key: loaded[key] for key in helper.SOURCE_PINS},
        "evidence": loaded["evidence"],
    }


def test_frame_intervals_and_preserved_slots_independently() -> None:
    layout = helper.frame_layout()
    first, second = layout["regions"]
    assert [(r["start"], r["end"], r["length"]) for r in (first, second)] == [
        (-800, -720, 80),
        (-720, -4, 716),
    ]
    first_bytes = set(range(first["start"], first["end"]))
    second_bytes = set(range(second["start"], second["end"]))
    assert first_bytes.isdisjoint(second_bytes)
    zeroed = first_bytes | second_bytes
    assert zeroed == set(range(-800, -4))
    assert len(zeroed) == layout["zero_bytes"] == 796
    assert layout["zero_union"] == [-800, -4]
    expected_slots = {
        "untouched_locals": [-808, -800],
        "protected_cookie": [-4, 0],
        "saved_edi": [-812, -808],
        "saved_ebp": [0, 4],
    }
    protected = set()
    for name, expected in expected_slots.items():
        assert layout[name] == expected
        slot = set(range(*layout[name]))
        assert zeroed.isdisjoint(slot) and protected.isdisjoint(slot)
        protected |= slot
    assert layout["allocation"] == [-808, 0]
    assert set(range(-808, 0)) == zeroed | set(range(-808, -800)) | set(range(-4, 0))
    # Saved EDI lies immediately below the allocation. Each cdecl call pushes
    # three dwords and a return address; its arguments remain until shared cleanup.
    initial_sp = -808 - 4
    assert first["callee_sp"] == initial_sp - 3 * 4 - 4 == -828
    after_first_return = first["callee_sp"] + 4
    assert second["callee_sp"] == after_first_return - 3 * 4 - 4 == -840
    assert layout["lowest_outgoing_stack_offset"] == second["callee_sp"]
    assert layout["cleanup_bytes"] == 2 * 3 * 4
    assert (
        second["callee_sp"] + 4 + layout["cleanup_bytes"]
        == layout["stop_sp_offset"]
        == initial_sp
    )
    assert layout["stop_eax_offset"] == first["start"]
    assert layout["alignment_shared_with_ebp"] is True
    assert all(r["start"] % 16 == 0 for r in (first, second))


def test_complete_independent_matrix() -> None:
    expected = [
        (a, r, s, v, c)
        for a, (r, s), v, c in itertools.product(
            range(16),
            [(0, 0), (0, 2), (2, 0), (2, 2)],
            [0, 0xFFFFFFFF],
            [0, 0x6B8B4567],
        )
    ]
    actual = helper.cases()
    assert actual == expected
    assert len(actual) == len(set(actual)) == 256
    for index, domain in enumerate(
        [range(16), [0, 2], [0, 2], [0, 0xFFFFFFFF], [0, 0x6B8B4567]]
    ):
        assert {case[index] for case in actual} == set(domain)
    assert (
        _digest([list(case) for case in actual])
        == "13c0e01f9674875167bd2891612d840172c149f0f24d2799a57d1f2cd6185c47"
    )


def test_committed_receipt_identity_and_source_joins(values: dict[str, Any]) -> None:
    evidence, sources = values["evidence"], values["sources"]
    assert _digest(evidence) == CANONICAL == helper.SEALED_SHA256
    assert hashlib.sha256(values["paths"]["evidence"].read_bytes()).hexdigest() == RAW
    assert (
        helper.encode_caller(evidence).encode()
        == values["paths"]["evidence"].read_bytes()
    )
    assert evidence["build_identity"] == sources["program_facts"]["identity"]
    for name, (kind, digest) in helper.SOURCE_PINS.items():
        assert _digest(sources[name]) == digest
        assert evidence["source_receipts"][name] == {
            "analysis_kind": kind,
            "canonical_sha256": digest,
        }
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )
    assert evidence["setup"]["layout"] == helper.frame_layout()
    for join, region in zip(
        evidence["setup"]["source_joins"],
        evidence["setup"]["layout"]["regions"],
        strict=True,
    ):
        for source, path_key in [("pair", "pair_path"), ("leaves", "leaf_path")]:
            node = sources[source]
            for key in join[path_key]:
                node = node[key]
            assert (node["edge"] if source == "leaves" else node) == join["edge"]
        assert join["edge"]["instruction"]["rva"] == region["call_rva"]
        assert join["edge"]["target_entry_rva"] == "0x00370960"


def test_receipt_scope_counts_and_exclusive_boundary(values: dict[str, Any]) -> None:
    evidence = values["evidence"]
    assert evidence["summary"] == {
        "prefix_cases": 256,
        "fill_observations": 512,
        "optional_helper_executions": 128,
        "prefix_nodes": 25,
        "all_visited_nodes": 111,
        "zero_region_bytes": 796,
        "negative_controls": 1,
    }
    setup = evidence["setup"]
    points = setup["prefix_points"]
    assert len(points) == 25
    assert points[0]["rva"] == "0x00379d28"
    assert sum(point["size"] for point in points) == setup["prefix_size"] == 81
    for left, right in zip(points, points[1:]):
        assert int(left["rva"], 16) + left["size"] == int(right["rva"], 16)
    assert (
        int(points[-1]["rva"], 16) + points[-1]["size"]
        == int(setup["exclusive_stop_rva"], 16)
        == 0x379D79
    )
    visited = evidence["visited_rvas"]
    assert len(visited) == len(set(visited)) == 111
    assert {p["rva"] for p in points} <= set(visited)
    assert setup["exclusive_stop_rva"] not in visited
    assert evidence["direction_control"] == {
        "input_df": 1,
        "vector": [0, 2, 0, 0xFFFFFFFF, 0],
        "expected_rejection": "fill write escaped destination",
    }
    assert evidence["scope"]["positive_df"] == 0
    assert evidence["emulator"]["version"] == "2.1.4"
    assert evidence["emulator"]["timeout_microseconds"] == 5_000_000
    exclusions = " ".join(evidence["scope"]["not_claimed"])
    for phrase in [
        "All caller inputs",
        "Whole caller return",
        "Real game execution",
        "accounting promotion",
    ]:
        assert phrase in exclusions
    assert (
        evidence["results_sha256"]
        == "94eb646885a5b8d87b0d6b1287ba54cac1b759b39c35cce964d37c9b299068bd"
    )


@pytest.mark.parametrize("source", list(helper.SOURCE_PINS))
def test_source_pin_rejects_mutation(values: dict[str, Any], source: str) -> None:
    sources = dict(values["sources"])
    sources[source] = dict(sources[source], unexpected=True)
    with pytest.raises(Error):
        helper.validate_structure(values["evidence"], sources)


@pytest.mark.parametrize("extra", [True, False])
def test_source_partition_is_exact(values: dict[str, Any], extra: bool) -> None:
    sources = dict(values["sources"])
    if extra:
        sources["extra"] = {}
    else:
        sources.pop("pair")
    with pytest.raises(Error):
        helper.validate_structure(values["evidence"], sources)


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("schema_version",), True),
        (("schema_version",), 1.0),
        (("analysis_kind",), "other"),
        (("unknown",), "extra"),
        (("raw_bytes",), "proprietary"),
        (("results_sha256",), "0" * 64),
        (("vector_sha256",), "0" * 64),
        (("visited_rvas",), []),
        (("source_receipts", "pair", "canonical_sha256"), "0" * 64),
        (("setup", "layout", "protected_cookie"), [-8, -4]),
        (("setup", "layout", "cleanup_bytes"), 12),
        (("setup", "source_joins"), []),
        (("setup", "prefix_points"), []),
        (("setup", "exclusive_stop_rva"), "0x00379d7a"),
        (("matrix", "selectors"), [0]),
        (("summary", "prefix_cases"), 255),
        (("direction_control", "input_df"), 0),
        (("scope", "not_claimed"), []),
        (("emulator", "version"), "other"),
    ],
)
def test_strict_seal_rejects_mutations(
    values: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    path: tuple[str, ...],
    replacement: Any,
) -> None:
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
    with pytest.raises(Error, match="sealed caller identity"):
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
            str(ROOT / "scripts/itb_native_assertion_helper_caller_fill.py"),
            *_args(values, "verify"),
            "--executable",
            str(executable),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "verified"
