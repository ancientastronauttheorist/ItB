"""Independent frame overlays, sealed receipts and safe publication."""

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

from scripts import itb_native_assertion_helper_frame_stores as cli
from src.observatory import native_assertion_helper_frame_stores as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
CANONICAL = "69afa7ae52de9fe086d15f92350394518db88be433f7b9b3f5607c1a0a36d0b1"
RAW = "09515f803d5b7bf9e6534a62540fbfb740f89d9b32216f2d6508e9ae1a54aef0"
Error = helper.StoreError


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
        "caller": "native_assertion_helper_caller_fill",
        "program_facts": "program_facts",
        "evidence": "native_assertion_helper_frame_stores",
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


# Authored independently from the decoder and overlay table. These are frame
# offsets and data values, never instruction encodings or executable bytes.
DWORDS = {
    -808: "frame_minus_800",
    -804: "frame_minus_720",
    -544: "frame_minus_720",
    -548: "ecx",
    -552: "edx",
    -556: "ebx",
    -560: "esi",
    -564: "edi",
    -816: "pushed_flags_image",
    -528: "pushed_flags_image",
    -536: "return_word",
    -524: "frame_plus_4",
    -720: "constant_65537",
    -540: "saved_ebp",
    -800: "incoming_word_12",
    -796: "incoming_word_16",
    -788: "return_word",
}
WORDS = {-520: "ss", -532: "cs", -568: "ds", -572: "es", -576: "fs", -580: "gs"}


def _inputs() -> dict[str, int]:
    return {
        "frame_minus_800": 0x2001CE0,
        "frame_minus_720": 0x2001D30,
        "frame_plus_4": 0x2002004,
        "ecx": 0x12345678,
        "edx": 0x89ABCDEF,
        "ebx": 0xFEDCBA98,
        "esi": 0x24681357,
        "edi": 0xFFFFFFFF,
        "ss": 0x103,
        "cs": 0x207,
        "ds": 0x30B,
        "es": 0x40F,
        "fs": 0x513,
        "gs": 0x617,
        "pushed_flags_image": 0x8D7,
        "return_word": 0x10203040,
        "constant_65537": 65537,
        "saved_ebp": 0x55667788,
        "incoming_word_12": 0x11223344,
        "incoming_word_16": 0xFFEEDDCC,
    }


@pytest.mark.parametrize("alignment", [0, 1, 7, 15])
def test_independent_overlay_arbitrary_bytes_and_canaries(alignment: int) -> None:
    frame = 1024 + alignment
    before = bytes((index * 71 + 29) % 256 for index in range(1400))
    inputs = _inputs()
    expected = bytearray(before)
    written = set()
    for slots, width in [(DWORDS, 4), (WORDS, 2)]:
        for offset, name in slots.items():
            at = frame + offset
            expected[at : at + width] = inputs[name].to_bytes(width, "little")
            written.update(range(at, at + width))
    actual = helper.overlay_spec(before, frame, inputs)
    assert isinstance(actual, bytes) and len(actual) == len(before)
    assert actual == bytes(expected)
    assert len(written) == 80
    assert all(
        actual[index] == before[index]
        for index in range(len(before))
        if index not in written
    )
    for offset in WORDS:
        assert (
            actual[frame + offset + 2 : frame + offset + 4]
            == before[frame + offset + 2 : frame + offset + 4]
        )
    # PUSHFD leaves a stale temporary below saved EDI; POP does not erase it.
    assert actual[frame - 816 : frame - 812] == (0x8D7).to_bytes(4, "little")
    for start, stop in [(-812, -808), (-4, 0), (0, 20), (-792, -788)]:
        assert (
            actual[frame + start : frame + stop] == before[frame + start : frame + stop]
        )
    assert set(helper.FIELDS) == {(o, 4, n) for o, n in DWORDS.items()} | {
        (o, 2, n) for o, n in WORDS.items()
    }
    assert len(helper.FIELDS) == 23


def test_overlay_word_sources_preserve_high_half_and_use_low_word() -> None:
    inputs = _inputs()
    inputs["ss"] = 0xABCD1234
    before = bytes([0xA5]) * 1400
    actual = helper.overlay_spec(before, 1024, inputs)
    assert actual[504:508] == (0xA5A51234).to_bytes(4, "little")


@pytest.mark.parametrize(
    "before,frame",
    [
        (bytearray(1400), 1024),
        (None, 1024),
        (bytes(1400), True),
        (bytes(1400), 1024.0),
        (bytes(1400), -1),
        (bytes(1400), 815),
        (bytes(1400), 2000),
    ],
)
def test_overlay_rejects_invalid_buffer(before: Any, frame: Any) -> None:
    with pytest.raises(Error):
        helper.overlay_spec(before, frame, _inputs())


@pytest.mark.parametrize("bad", [None, [], "inputs", {"ecx": 0}])
def test_overlay_requires_exact_mapping(bad: Any) -> None:
    with pytest.raises(Error):
        helper.overlay_spec(bytes(1400), 1024, bad)


@pytest.mark.parametrize("bad", [True, 1.0, -1, 0x100000000, "7", None])
def test_overlay_rejects_non_u32(bad: Any) -> None:
    inputs = _inputs()
    inputs["ecx"] = bad
    with pytest.raises(Error):
        helper.overlay_spec(bytes(1400), 1024, inputs)


def test_overlay_rejects_extra_input() -> None:
    with pytest.raises(Error):
        helper.overlay_spec(bytes(1400), 1024, _inputs() | {"extra": 0})


def test_complete_independent_matrix() -> None:
    expected = list(
        itertools.product(range(16), range(2), range(2), [2, 0x202, 0x246, 0x8D7])
    )
    assert helper.cases() == expected
    assert len(expected) == len(set(expected)) == 256
    assert (
        _digest([list(v) for v in expected])
        == "1c348306d1ff4e5ebc655c6cc277130d74efd597bae674e5f8f40fb22b1d9fc4"
    )
    assert helper.MATRIX["segment_selectors"] == dict.fromkeys(
        ["ss", "cs", "ds", "es", "fs", "gs"], 0
    )
    assert len(helper.MATRIX["register_sets"]) == len(helper.MATRIX["input_sets"]) == 2


def test_committed_receipt_and_source_joins(values: dict[str, Any]) -> None:
    evidence, sources = values["evidence"], values["sources"]
    assert _digest(evidence) == CANONICAL == helper.SEALED_SHA256
    assert hashlib.sha256(values["paths"]["evidence"].read_bytes()).hexdigest() == RAW
    assert (
        helper.encode_stores(evidence).encode()
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
    assert (
        evidence["entry_join"]["caller_stop_rva"]
        == sources["caller"]["setup"]["exclusive_stop_rva"]
        == evidence["slice"]["start_rva"]
    )
    assert (
        evidence["entry_join"]["zero_union"]
        == sources["caller"]["setup"]["layout"]["zero_union"]
        == [-800, -4]
    )
    assert evidence["entry_join"]["eax_ebp_offset"] == -800
    assert evidence["entry_join"]["esp_ebp_offset"] == -812
    assert evidence["vector_sha256"] == _digest([list(v) for v in helper.cases()])


def test_receipt_facts_and_exclusive_boundary(values: dict[str, Any]) -> None:
    evidence = values["evidence"]
    assert evidence["summary"] == {
        "cases": 256,
        "instructions_per_case": 30,
        "frame_stores_per_case": 22,
        "temporary_stores_per_case": 1,
        "write_events_per_case": 23,
        "read_events_per_case": 6,
        "frame_written_bytes": 76,
        "temporary_written_bytes": 4,
        "negative_controls": 2,
    }
    section = evidence["slice"]
    assert section["owner_entry_rva"] == "0x00379d28"
    assert section["start_rva"] == "0x00379d79"
    assert section["exclusive_stop_rva"] == "0x00379e20"
    points = section["points"]
    assert (
        len(points) == 30 and sum(p["size"] for p in points) == section["size"] == 167
    )
    assert points[0]["rva"] == section["start_rva"]
    for left, right in zip(
        points, points[1:] + [section["unexecuted_stop_instruction"]]
    ):
        assert int(left["rva"], 16) + left["size"] == int(right["rva"], 16)
    assert (
        section["unexecuted_stop_instruction"]["rva"] == section["exclusive_stop_rva"]
    )
    assert all(p["rva"] != section["exclusive_stop_rva"] for p in points)
    owner = values["sources"]["pair"]["bodies"][0]["points"]
    assert [p for p in owner if 0x379D79 <= int(p["rva"], 16) < 0x379E20] == points
    grammar = evidence["grammar"]
    assert len(grammar["stores"]) == 23 and len(grammar["reads"]) == 6
    assert [(s["offset"], s["width"]) for s in grammar["stores"] if s["temporary"]] == [
        (-816, 4)
    ]
    assert {(s["offset"], s["width"], s["source"]) for s in grammar["stores"]} == set(
        helper.FIELDS
    )
    assert grammar["final_eax"] == "return_word" and grammar["final_esp_offset"] == -812
    assert {c["mutation"] for c in evidence["oracle_controls"]} == {
        "widen_segment",
        "wrong_register",
    }
    assert all(
        c["expected_rejection"] == "write event differs"
        for c in evidence["oracle_controls"]
    )
    excluded = " ".join(evidence["scope"]["not_claimed"])
    for phrase in [
        "reachable",
        "Nonzero segment",
        "Original caller-entry",
        "whole-function",
        "accounting promotion",
    ]:
        assert phrase in excluded
    assert evidence["emulator"]["version"] == "2.1.4"
    assert (
        evidence["results_sha256"]
        == "2b39610da5dc48357fa6544bc1edf1482159a23af3dedeffcecd39958f590107"
    )


@pytest.mark.parametrize("source", ["pair", "caller", "program_facts"])
def test_source_pin_rejects_mutation(values: dict[str, Any], source: str) -> None:
    sources = dict(values["sources"])
    sources[source] = dict(sources[source], unexpected=True)
    with pytest.raises(Error):
        helper.validate_structure(values["evidence"], sources)


@pytest.mark.parametrize("extra", [True, False])
def test_exact_source_partition(values: dict[str, Any], extra: bool) -> None:
    sources = dict(values["sources"])
    if extra:
        sources["extra"] = {}
    else:
        sources.pop("caller")
    with pytest.raises(Error):
        helper.validate_structure(values["evidence"], sources)


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("schema_version",), True),
        (("schema_version",), 1.0),
        (("analysis_kind",), "other"),
        (("extra",), 0),
        (("raw_bytes",), "private"),
        (("results_sha256",), "0" * 64),
        (("vector_sha256",), "0" * 64),
        (("source_receipts", "caller", "canonical_sha256"), "0" * 64),
        (("slice", "exclusive_stop_rva"), "0x00379e21"),
        (("slice", "points"), []),
        (("entry_join", "esp_ebp_offset"), -816),
        (("entry_join", "zero_union"), [-800, 0]),
        (("grammar", "stores"), []),
        (("grammar", "reads"), []),
        (("overlay_fields",), []),
        (("matrix", "eflags_values"), [2]),
        (("summary", "frame_written_bytes"), 80),
        (("oracle_controls",), []),
        (("scope", "not_claimed"), []),
        (("emulator", "version"), "other"),
    ],
)
def test_strict_receipt_mutations(
    values: dict[str, Any], path: tuple[str, ...], replacement: Any
) -> None:
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
    with pytest.raises(Error, match="sealed stores identity"):
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
    environment = os.environ.copy()
    runtime = str(ROOT / ".local_decompile/fill_runtime")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in [runtime, environment.get("PYTHONPATH", "")] if part
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_assertion_helper_frame_stores.py"),
            *_args(values, "verify"),
            "--executable",
            str(executable),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "verified"
