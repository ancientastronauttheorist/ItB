"""Exact and adversarial checks for the assertion-helper first callee."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

import pytest

from scripts import itb_native_assertion_helper_first_callee_static_boundary as cli
from src.observatory import (
    native_assertion_helper_first_callee_static_boundary as helper,
)
from src.observatory.native_assertion_helper_first_callee_static_boundary import (
    NativeAssertionHelperFirstCalleeStaticBoundaryError,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE_SHA256 = helper._EXE
RAW_SHA256 = "bc6e195e133fba208b13344aea8e211e44fc57e0399d860af38f2ab9ed3383f0"
CANONICAL_SHA256 = "e99d2b76879c1456c6ec44bf3fcbc38f2f50a456aae6416687f0cf1f09898da0"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    paths = {
        "inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"),
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "predecessor": PROGRAMS
        / (PREFIX + "native_assertion_helper_static_boundary.json"),
        "evidence": PROGRAMS
        / (PREFIX + "native_assertion_helper_first_callee_static_boundary.json"),
    }
    if any(not path.is_file() for path in paths.values()):
        pytest.skip("assertion-helper first-callee prerequisites are unavailable")
    result = {name: _read(path) for name, path in paths.items()}
    result["paths"] = paths
    return result


def _common(
    values: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return values["predecessor"], values["direct"], values["facts"]


def _structure(
    values: dict[str, Any], evidence: dict[str, Any] | None = None
) -> dict[str, Any]:
    return (
        helper.validate_native_assertion_helper_first_callee_static_boundary_structure(
            values["evidence"] if evidence is None else evidence, *_common(values)
        )
    )


def _replace(value: Any, path: tuple[Any, ...], replacement: Any) -> Any:
    if not path:
        return replacement
    clone = dict(value) if isinstance(value, dict) else list(value)
    clone[path[0]] = _replace(value[path[0]], path[1:], replacement)
    return clone


def _fast_structure(
    monkeypatch: pytest.MonkeyPatch,
    values: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    target = helper._atlas_functions(values["facts"])[helper._ENTRY]
    monkeypatch.setattr(helper, "_validate_json_tree", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        helper, "_assert_publication_safe", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        helper,
        "validate_native_lua_direct_call_structure",
        lambda *args, **kwargs: {
            "status": "structurally_verified",
            "evidence_sha256": helper._DIRECT,
        },
    )
    monkeypatch.setattr(
        helper,
        "_preflight",
        lambda *args, **kwargs: {
            "program_facts": copy.deepcopy(values["evidence"]["program_facts"]),
            "predecessor_static_boundary": copy.deepcopy(
                values["evidence"]["predecessor_static_boundary"]
            ),
            "direct_call_census": copy.deepcopy(
                values["evidence"]["direct_call_census"]
            ),
        },
    )
    monkeypatch.setattr(helper, "_target_function", lambda *args, **kwargs: target)
    monkeypatch.setattr(
        helper,
        "_expected_scan",
        lambda *args, **kwargs: copy.deepcopy(
            values["evidence"]["whole_atlas_reference_scan"]
        ),
    )
    return _structure(values, evidence)


def _reject(
    monkeypatch: pytest.MonkeyPatch,
    values: dict[str, Any],
    path: tuple[Any, ...],
    replacement: Any,
) -> None:
    with pytest.raises(NativeAssertionHelperFirstCalleeStaticBoundaryError):
        _fast_structure(
            monkeypatch, values, _replace(values["evidence"], path, replacement)
        )


def test_static_contract_constants_are_stable() -> None:
    assert (
        helper._ENTRY,
        helper._SIZE,
        helper._RAW,
        helper._BODY,
        helper._ATLAS,
        helper._CFG,
    ) == (
        0x38E392,
        63,
        "8bff558bec8b4d0885c9781e83f9027e0c83f9037514a134758b005dc3a134758b00890d34758b005dc3e80b78ffffc70016000000e826bbfeff83c8ff5dc3",
        "9ccce0d1b341bdf834edec2dc6c9626c73f97a7e4df7917e4c7d202ae906039d",
        "4608b7afb2563887aeb78c99d4dfddc8af5cb60e146f46104b94c6dc919d7efd",
        "f47565f73f6bf3721d4d6a4bc73dfafbe570574da654e0bed72ea49d39368843",
    )


def test_decode_graph_and_operand_partitions(values: dict[str, Any]) -> None:
    evidence = values["evidence"]
    body = evidence["function_body"]
    graph = evidence["control_flow_graph"]
    calls = evidence["native_calls"]
    assert (
        body["entry_rva"],
        body["body_size"],
        body["body_sha256"],
        len(body["reviewed_points"]),
    ) == ("0x0038e392", 63, helper._BODY, 23)
    assert (
        graph["node_count"],
        graph["edge_count"],
        helper._canonical_sha256(graph),
    ) == (
        23,
        23,
        helper._CFG,
    )
    assert [row["rva"] for row in graph["nodes"] if row["flow_kind"] == "terminal"] == [
        "0x0038e3ae",
        "0x0038e3bb",
        "0x0038e3d0",
    ]
    assert [
        (row["instruction"]["rva"], row["target_entry_rva"])
        for row in calls["outgoing_direct"]
    ] == [("0x0038e3bc", "0x00385bcc"), ("0x0038e3c7", "0x00379ef2")]
    assert [
        (row["instruction"]["rva"], row["operand_index"], row["operand_access"])
        for row in calls["pe_address_operands"]
    ] == [
        ("0x0038e3a8", 1, "read"),
        ("0x0038e3af", 1, "read"),
        ("0x0038e3b4", 0, "write"),
    ]
    assert all(
        row["operand_rva"] == "0x004b7534"
        and row["file_backed"] is False
        and row["file_offset"] is None
        for row in calls["pe_address_operands"]
    )
    assert [row["value_u32"] for row in calls["non_pe_immediate_literals"]] == [
        "0x00000002",
        "0x00000003",
        "0x00000016",
        "0xffffffff",
    ]
    relocations = calls["base_relocation_scan"]
    assert relocations["highlow_site_count_inside_body"] == 3
    assert [
        (row["site_rva"], row["entry_file_offset"], row["entry_raw"])
        for row in relocations["highlow_sites"]
    ] == [
        ("0x0038e3a9", "0x005334ce", "a933"),
        ("0x0038e3b0", "0x005334d0", "b033"),
        ("0x0038e3b6", "0x005334d2", "b633"),
    ]
    assert all(
        row["type"] == "HIGHLOW"
        and row["value_va"] == "0x008b7534"
        and row["value_rva"] == "0x004b7534"
        for row in relocations["highlow_sites"]
    )
    for key in (
        "direct_lua_calls",
        "staged_lua_dispatches",
        "opaque_indirect_controls",
        "segment_qualified_memory_syntax",
        "bnd_prefixed_control_syntax",
        "opaque_interrupt_syntax",
    ):
        assert calls[key] == []


def test_structure_parent_and_reference_join(values: dict[str, Any]) -> None:
    result = _structure(values)
    scan = values["evidence"]["whole_atlas_reference_scan"]
    assert result["status"] == "structurally_verified"
    assert result["summary"] == values["evidence"]["summary"]
    assert [
        (row["instruction_rva"], row["owner_entry_rva"], row["target_rva"])
        for row in scan["references"]
    ] == [("0x00379ccd", "0x00379cc2", "0x0038e392")]
    assert (
        values["evidence"]["predecessor_parent_edges"][0]["instruction"]["rva"]
        == scan["references"][0]["instruction_rva"]
    )


def _changed(value: Any) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        return "tampered"
    if value is None:
        return "tampered"
    if isinstance(value, list):
        return ["tampered"]
    if isinstance(value, dict):
        return {"tampered": True}
    raise AssertionError(f"unsupported mutation value {value!r}")


TAMPER_PATHS = [
    ("schema_version",),
    ("analysis_kind",),
    ("build_identity", "architecture"),
    ("program_facts", "canonical_sha256"),
    ("predecessor_static_boundary", "canonical_sha256"),
    ("direct_call_census", "canonical_sha256"),
    ("decoder", "name"),
    ("decoder", "register_call_encoding_audit", 0, "encoding"),
    ("function_body", "role"),
    ("function_body", "entry_rva"),
    ("function_body", "atlas_record_sha256"),
    ("function_body", "body_size"),
    ("function_body", "body_sha256"),
    ("function_body", "range_start_rva"),
    ("function_body", "control_flow_graph_canonical_sha256"),
    ("function_body", "reviewed_points", 5, "rva"),
    ("function_body", "reviewed_points", 5, "sha256"),
    ("function_body", "reviewed_points", 0, "writes_edi"),
    ("function_body", "ghidra_analysis_metadata", "metadata_only"),
    ("function_body", "semantic_facts", "analysis_labels_opaque"),
    ("control_flow_graph", "caller_entry_rva"),
    ("control_flow_graph", "nodes", 5, "successor_rvas"),
    ("control_flow_graph", "nodes", 12, "flow_kind"),
    ("predecessor_parent_edges", 0, "source_atlas_record_sha256"),
    ("predecessor_parent_edges", 0, "instruction", "sha256"),
    ("native_calls", "outgoing_direct", 0, "target_entry_rva"),
    (
        "native_calls",
        "outgoing_direct",
        1,
        "ghidra_declared_direct_edge",
        "target_name_sha256",
    ),
    ("native_calls", "outgoing_direct_partition_complete"),
    ("native_calls", "direct_lua_calls"),
    ("native_calls", "staged_lua_dispatches"),
    ("native_calls", "opaque_indirect_controls"),
    ("native_calls", "call_r32_audit", 0, "call_rvas"),
    ("native_calls", "pe_address_operands", 0, "operand_index"),
    ("native_calls", "pe_address_operands", 1, "operand_rva"),
    ("native_calls", "pe_address_operands", 2, "operand_access"),
    ("native_calls", "pe_address_operands", 2, "file_backed"),
    ("native_calls", "non_pe_immediate_literals", 0, "value_u32"),
    ("native_calls", "non_pe_immediate_literals", 3, "instruction", "sha256"),
    ("native_calls", "base_relocation_scan", "directory", "sha256"),
    ("native_calls", "base_relocation_scan", "highlow_site_count_inside_body"),
    ("native_calls", "base_relocation_scan", "highlow_sites", 0, "site_rva"),
    ("native_calls", "base_relocation_scan", "highlow_sites", 1, "entry_file_offset"),
    ("native_calls", "base_relocation_scan", "highlow_sites", 2, "entry_raw"),
    ("whole_atlas_reference_scan", "references", 0, "owner_entry_rva"),
    ("whole_atlas_reference_scan", "references", 0, "instruction_sha256"),
    ("whole_atlas_reference_scan", "target_partition", 0, "reference_count"),
    ("whole_atlas_reference_scan", "owner_partition", 0, "reference_count"),
    ("whole_atlas_reference_scan", "target_owner_partition", 0, "owner_entry_rva"),
    ("whole_atlas_reference_scan", "target_reference_partition", 0, "reference_count"),
    ("whole_atlas_reference_scan", "partition_sha256", "target_partition"),
    ("whole_atlas_reference_scan", "partition_sha256", "owner_partition"),
    ("whole_atlas_reference_scan", "references_canonical_sha256"),
    ("whole_atlas_reference_scan", "aggregates", "direct_call_count"),
    ("method", "not_claimed", 0),
    ("summary", "native_direct_edge_count"),
]


@pytest.mark.parametrize("path", TAMPER_PATHS)
def test_structure_rejects_every_retained_partition(
    values: dict[str, Any], path: tuple[Any, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    value: Any = values["evidence"]
    for key in path:
        value = value[key]
    _reject(monkeypatch, values, path, _changed(value))


@pytest.mark.parametrize(
    "path",
    [
        ("unexpected",),
        ("function_body", "unexpected"),
        ("native_calls", "unexpected"),
        ("whole_atlas_reference_scan", "references", 0, "unexpected"),
        ("summary", "unexpected"),
    ],
)
def test_structure_rejects_unknown_keys(
    values: dict[str, Any], path: tuple[Any, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = copy.deepcopy(values["evidence"])
    node: Any = evidence
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = "injected"
    with pytest.raises(NativeAssertionHelperFirstCalleeStaticBoundaryError):
        _fast_structure(monkeypatch, values, evidence)


def test_outgoing_partition_fails_on_injected_edge(values: dict[str, Any]) -> None:
    facts = copy.deepcopy(values["facts"])
    facts["ghidra_declared_direct_calls"].append(
        {
            "instruction_rva": "0x0038e392",
            "source_entry_rva": "0x0038e392",
            "target_entry_rva": "0x0038e392",
            "target_rva": "0x0038e392",
            "target_name": "injected",
        }
    )
    with pytest.raises(
        NativeAssertionHelperFirstCalleeStaticBoundaryError, match="outgoing native"
    ):
        helper._native_calls(facts)


def test_encodes_deterministically_and_rejects_invalid_tree(
    values: dict[str, Any],
) -> None:
    rendered = helper.encode_native_assertion_helper_first_callee_static_boundary(
        values["evidence"]
    )
    assert rendered.encode() == values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(rendered.encode()).hexdigest() == RAW_SHA256
    assert helper._canonical_sha256(values["evidence"]) == CANONICAL_SHA256
    with pytest.raises(NativeAssertionHelperFirstCalleeStaticBoundaryError):
        helper.encode_native_assertion_helper_first_callee_static_boundary(
            {"x": float("nan")}
        )


def _patch_output_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = tmp_path.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def test_immutable_writer_and_differing_destination(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helper.encode_native_assertion_helper_first_callee_static_boundary(
        values["evidence"]
    )
    cli._write_immutably(output, rendered, values["evidence"])
    cli._write_immutably(output, rendered, values["evidence"])
    output.write_bytes(rendered.encode() + b" ")
    with pytest.raises(
        NativeAssertionHelperFirstCalleeStaticBoundaryError,
        match="refusing to overwrite",
    ):
        cli._write_immutably(output, rendered, values["evidence"])


def test_writer_detects_post_read_race(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helper.encode_native_assertion_helper_first_callee_static_boundary(
        values["evidence"]
    )
    output.write_bytes(rendered.encode())
    original, calls = cli._read_json_document, []

    def mutate(path: Path, label: str):
        result = original(path, label)
        calls.append(1)
        if len(calls) == 1:
            with path.open("ab") as stream:
                stream.write(b" ")
        return result

    monkeypatch.setattr(cli, "_read_json_document", mutate)
    with pytest.raises(
        NativeAssertionHelperFirstCalleeStaticBoundaryError,
        match="final content validation",
    ):
        cli._write_immutably(output, rendered, values["evidence"])


def test_writer_final_lock_blocks_cooperating_writer(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helper.encode_native_assertion_helper_first_callee_static_boundary(
        values["evidence"]
    )
    output.write_bytes(rendered.encode())
    original, attempts = cli._read_locked_json_document, []

    def contender() -> None:
        try:
            with output.open("ab") as stream:
                stream.write(b" ")
        except OSError:
            attempts.append("blocked")
        else:
            attempts.append("mutated")

    def during(descriptor: int, label: str):
        result = original(descriptor, label)
        worker = threading.Thread(target=contender)
        worker.start()
        worker.join(5)
        return result

    monkeypatch.setattr(cli, "_read_locked_json_document", during)
    cli._write_immutably(output, rendered, values["evidence"])
    assert attempts == ["blocked"]


def test_writer_final_validation_cleans_failed_publication(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helper.encode_native_assertion_helper_first_callee_static_boundary(
        values["evidence"]
    )
    altered = copy.deepcopy(values["evidence"])
    altered["summary"]["reviewed_target_bytes"] += 1
    monkeypatch.setattr(
        cli,
        "_read_locked_json_document",
        lambda *args: (altered, helper._canonical_bytes(altered)),
    )
    with pytest.raises(
        NativeAssertionHelperFirstCalleeStaticBoundaryError,
        match="final content validation",
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    assert not output.exists()


def test_cli_parser_and_strict_json_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    parsed = cli.build_parser().parse_args(
        [
            "build",
            "--assertion-helper-static-boundary",
            "a.json",
            "--direct-calls",
            "b.json",
            "--program-facts",
            "c.json",
            "--inventory",
            "d.json",
            "--executable",
            "Breach.exe",
        ]
    )
    assert parsed.command == "build"
    bad = tmp_path / "bad.json"
    bad.write_bytes(b'{"x":NaN}')
    args = [
        "verify-structure",
        "--assertion-helper-static-boundary",
        str(bad),
        "--direct-calls",
        str(bad),
        "--program-facts",
        str(bad),
        "--evidence",
        str(bad),
    ]
    assert cli.main(args) == 1
    assert capsys.readouterr().err.startswith("error: ")


def _exact_executable() -> Path:
    configured = os.environ.get("ITB_EXACT_EXE")
    if not configured:
        pytest.skip("set ITB_EXACT_EXE to run expensive exact PE checks")
    path = Path(configured)
    if (
        not path.is_file()
        or hashlib.sha256(path.read_bytes()).hexdigest() != EXE_SHA256
    ):
        pytest.skip("exact installed Breach.exe is unavailable")
    return path


def test_exact_rebuild_verify_cli_and_nonvacuous_scanner(
    values: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executable = _exact_executable()
    rebuilt = helper.build_native_assertion_helper_first_callee_static_boundary(
        executable, *_common(values), inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    data, image, _ = helper._load_executable(executable)
    altered_data = bytearray(data)
    altered_data[0x5334CE:0x5334D0] = bytes.fromhex("a903")
    altered_directory = bytes(altered_data[0x510A00 : 0x510A00 + 218648])
    original_sha256 = helper.hashlib.sha256

    class PinnedDirectoryDigest:
        def hexdigest(self) -> str:
            return helper._RELOCATION_DIRECTORY[3]

    def allow_only_the_pinned_directory_mutation(payload: bytes = b""):
        if bytes(payload) == altered_directory:
            return PinnedDirectoryDigest()
        return original_sha256(payload)

    monkeypatch.setattr(
        helper.hashlib, "sha256", allow_only_the_pinned_directory_mutation
    )
    with pytest.raises(
        NativeAssertionHelperFirstCalleeStaticBoundaryError,
        match="base-relocation operand frontier",
    ):
        helper._native_calls(values["facts"], type(image)(bytes(altered_data)))
    monkeypatch.setattr(helper.hashlib, "sha256", original_sha256)
    decoder, _ = helper._decoder()
    assert helper._whole_atlas_reference_scan(
        data, image, decoder, values["facts"]
    ) == helper._expected_scan(values["facts"])
    original = helper._decode_range
    import capstone

    for encoded in ("b892e37800", "a192e37800"):

        def altered(
            data: bytes,
            image: Any,
            start: int,
            size: int,
            decoder: Any,
            encoded: str = encoded,
        ):
            rows = original(data, image, start, size, decoder)
            if start == 0x379CC2:
                altered_decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
                altered_decoder.detail = True
                replacement = list(
                    altered_decoder.disasm(
                        bytes.fromhex(encoded), image.image_base + 0x379CCD
                    )
                )
                assert rows[6].address - image.image_base == 0x379CCD
                assert len(replacement) == 1 and replacement[0].size == rows[6].size
                rows[6] = replacement[0]
            return rows

        monkeypatch.setattr(helper, "_decode_range", altered)
        changed, _ = helper._decoder()
        with pytest.raises(
            NativeAssertionHelperFirstCalleeStaticBoundaryError, match="all-operand"
        ):
            helper._whole_atlas_reference_scan(data, image, changed, values["facts"])
        monkeypatch.setattr(helper, "_decode_range", original)
    receipt = helper.validate_native_assertion_helper_first_callee_static_boundary(
        executable,
        values["evidence"],
        *_common(values),
        inventory=values["inventory"],
    )
    assert receipt["status"] == "verified"
    paths = values["paths"]
    assert (
        cli.main(
            [
                "verify",
                "--assertion-helper-static-boundary",
                str(paths["predecessor"]),
                "--direct-calls",
                str(paths["direct"]),
                "--program-facts",
                str(paths["facts"]),
                "--inventory",
                str(paths["inventory"]),
                "--executable",
                str(executable),
                "--evidence",
                str(paths["evidence"]),
            ]
        )
        == 0
    )
    assert '"status": "verified"' in capsys.readouterr().out
