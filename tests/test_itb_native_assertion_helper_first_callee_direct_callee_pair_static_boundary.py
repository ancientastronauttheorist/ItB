"""Exact and adversarial checks for the assertion-helper first-callee pair."""

from __future__ import annotations

import copy
import errno
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

import pytest

from scripts import (
    itb_native_assertion_helper_first_callee_direct_callee_pair_static_boundary as cli,
)
from src.observatory import (
    native_assertion_helper_first_callee_direct_callee_pair_static_boundary as helper,
)
from src.observatory.native_assertion_helper_first_callee_direct_callee_pair_static_boundary import (
    NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError,
)
from src.observatory.native_assertion_helper_static_boundary import (
    NativeAssertionHelperStaticBoundaryError,
)
from src.observatory.native_lua_property_factory_chain import (
    NativeLuaPropertyFactoryChainError,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE_SHA256 = helper._EXE
RAW_SHA256 = "40a83312f9867bcf385e836eb9547398803d8628a29c3d4716aec7ba4c21a493"
CANONICAL_SHA256 = "e1a04d9e847b1ec61e57e24cb02c03eea6b35aae5a1ad059cdd4339ebb939378"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values() -> dict[str, Any]:
    paths = {
        "inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"),
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "predecessor": PROGRAMS
        / (PREFIX + "native_assertion_helper_first_callee_static_boundary.json"),
        "evidence": PROGRAMS
        / (
            PREFIX
            + "native_assertion_helper_first_callee_direct_callee_pair_static_boundary.json"
        ),
    }
    if any(not path.is_file() for path in paths.values()):
        pytest.skip("assertion-helper first-callee pair prerequisites are unavailable")
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
    return helper.validate_native_assertion_helper_first_callee_direct_callee_pair_static_boundary_structure(
        values["evidence"] if evidence is None else evidence, *_common(values)
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
    monkeypatch.setattr(helper, "_target_function", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        helper,
        "_expected_scan",
        lambda *args, **kwargs: copy.deepcopy(
            values["evidence"]["whole_atlas_reference_scan"]
        ),
    )
    return _structure(values, evidence)


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


def test_static_contract_constants_are_stable() -> None:
    assert helper._PREDECESSOR == (
        "e99d2b76879c1456c6ec44bf3fcbc38f2f50a456aae6416687f0cf1f09898da0"
    )
    assert [
        (
            item["entry"],
            item["size"],
            item["body"],
            item["atlas"],
            item["instructions"],
            item["nodes"],
            item["edges"],
            item["cfg"],
        )
        for item in helper._TARGETS
    ] == [
        (
            0x385BCC,
            19,
            "28c011bc3ef2bcde2aa753d405ed6eb2be53c64f42af3613725ba23fb91ae619",
            "a8859e2355301186727a01e26a0ba71246f402b520df1907d3949e338b077b42",
            7,
            7,
            6,
            "11949588cdafd6ed16fc06369d47e49d1dc92550d60d279bb596bc47d101a740",
        ),
        (
            0x379EF2,
            16,
            "518dd4976a3fd19ac24d226d76a4e153c9abd83272da1a8ff0e1bc541c29c7ff",
            "6835b0add89fbccbc3b5d3b7cc62209df6ad0833f48dba6047797d5769a449c6",
            9,
            9,
            8,
            "93e1f9ae1f6c272859a61fd7d6b3f6a9b2e5742984d9da2dab01102e12410f63",
        ),
    ]


def test_bodies_graphs_calls_and_operands(values: dict[str, Any]) -> None:
    evidence = values["evidence"]
    assert [
        (body["entry_rva"], body["body_size"], len(body["reviewed_points"]))
        for body in evidence["function_bodies"]
    ] == [("0x00385bcc", 19, 7), ("0x00379ef2", 16, 9)]
    assert [
        (graph["caller_entry_rva"], graph["node_count"], graph["edge_count"])
        for graph in evidence["control_flow_graphs"]
    ] == [("0x00385bcc", 7, 6), ("0x00379ef2", 9, 8)]
    assert [
        helper._canonical_sha256(graph) for graph in evidence["control_flow_graphs"]
    ] == [item["cfg"] for item in helper._TARGETS]
    calls = evidence["native_calls"]
    assert [
        (
            target["entry_rva"],
            target["outgoing_direct"][0]["instruction"]["rva"],
            target["outgoing_direct"][0]["target_entry_rva"],
        )
        for target in calls["targets"]
    ] == [
        ("0x00385bcc", "0x00385bcc", "0x0038edb6"),
        ("0x00379ef2", "0x00379ef9", "0x00379e77"),
    ]
    assert calls["pe_address_operands"] == [
        {
            "role": "opaque_pe_immediate_data_address_syntax",
            "instruction": helper._instruction(0x385BD5, "b8d0408900"),
            "operand_class": "immediate",
            "operand_index": 1,
            "operand_access": "read",
            "operand_va": "0x008940d0",
            "operand_rva": "0x004940d0",
            "section_name": ".data",
            "section_rva": "0x00492000",
            "section_characteristics": "0xc0000040",
            "section_writable": True,
            "section_virtual_size": "0x000471cc",
            "section_raw_size": "0x00024800",
            "section_raw_offset": "0x00490200",
            "file_backed": True,
            "file_offset": "0x004922d0",
            "contents_or_runtime_behavior_opaque": True,
        }
    ]
    assert [row["value_u32"] for row in calls["non_pe_immediate_literals"]] == [
        "0x00000010",
        "0x00000014",
    ]
    assert calls["first_target_base_relocation_scan"]["highlow_sites"] == [
        {
            "site_rva": "0x00385bd6",
            "file_offset": "0x00384fd6",
            "entry_file_offset": "0x00533160",
            "entry_raw": "d63b",
            "type": "HIGHLOW",
            "value_va": "0x008940d0",
            "value_rva": "0x004940d0",
        }
    ]
    assert calls["second_target_base_relocation_scan"] == {
        "highlow_site_count_inside_target": 0,
        "highlow_sites": [],
    }
    for key in (
        "direct_lua_calls",
        "staged_lua_dispatches",
        "opaque_indirect_controls",
        "segment_qualified_memory_syntax",
        "bnd_prefixed_control_syntax",
        "opaque_interrupt_syntax",
        "import_and_iat_body_controls",
    ):
        assert calls[key] == []


def test_parent_joins_and_complete_reference_partitions(values: dict[str, Any]) -> None:
    result = _structure(values)
    evidence = values["evidence"]
    scan = evidence["whole_atlas_reference_scan"]
    assert result["status"] == "structurally_verified"
    assert [
        row["instruction"]["rva"] for row in evidence["predecessor_parent_edges"]
    ] == [
        "0x0038e3bc",
        "0x0038e3c7",
    ]
    assert [
        (row["target_rva"], row["reference_count"], row["owner_count"])
        for row in scan["target_partition"]
    ] == [
        ("0x00385bcc", 308, 202),
        ("0x00379ef2", 171, 148),
    ]
    assert scan["aggregates"] == {
        "reference_count": 479,
        "target_count": 2,
        "owner_count": 202,
        "target_owner_count": 350,
        "direct_call_count": 479,
        "comparison_count": 0,
        "other_address_count": 0,
        "memory_operand_count": 0,
    }
    assert scan["partition_sha256"] == helper._SCAN_HASHES
    assert {
        (row["instruction_rva"], row["target_rva"])
        for row in scan["references"]
        if row["owner_entry_rva"] == "0x0038e392"
    } == {
        ("0x0038e3bc", "0x00385bcc"),
        ("0x0038e3c7", "0x00379ef2"),
    }


TAMPER_PATHS = [
    ("schema_version",),
    ("analysis_kind",),
    ("build_identity", "architecture"),
    ("program_facts", "canonical_sha256"),
    ("predecessor_static_boundary", "canonical_sha256"),
    ("direct_call_census", "canonical_sha256"),
    ("decoder", "name"),
    ("decoder", "sealed_instruction_count_total"),
    ("decoder", "register_call_encoding_audit", 0, "encoding"),
    ("function_bodies", 0, "role"),
    ("function_bodies", 0, "entry_rva"),
    ("function_bodies", 0, "atlas_record_sha256"),
    ("function_bodies", 0, "body_sha256"),
    ("function_bodies", 0, "reviewed_points", 3, "rva"),
    ("function_bodies", 0, "ghidra_analysis_metadata", "metadata_only"),
    ("function_bodies", 1, "body_size"),
    ("function_bodies", 1, "control_flow_graph_canonical_sha256"),
    ("function_bodies", 1, "reviewed_points", 6, "sha256"),
    ("function_bodies", 1, "semantic_facts", "analysis_labels_opaque"),
    ("control_flow_graphs", 0, "nodes", 2, "successor_rvas"),
    ("control_flow_graphs", 1, "nodes", 8, "flow_kind"),
    ("predecessor_parent_edges", 0, "instruction", "sha256"),
    ("predecessor_parent_edges", 1, "target_entry_rva"),
    ("native_calls", "targets", 0, "outgoing_direct", 0, "target_entry_rva"),
    (
        "native_calls",
        "targets",
        1,
        "outgoing_direct",
        0,
        "ghidra_declared_direct_edge",
        "target_name_sha256",
    ),
    ("native_calls", "targets", 0, "outgoing_direct_partition_complete"),
    ("native_calls", "direct_lua_calls"),
    ("native_calls", "staged_lua_dispatches"),
    ("native_calls", "opaque_indirect_controls"),
    ("native_calls", "call_r32_audit", 0, "call_rvas"),
    ("native_calls", "pe_address_operands", 0, "operand_rva"),
    ("native_calls", "pe_address_operands", 0, "file_offset"),
    ("native_calls", "non_pe_immediate_literals", 0, "value_u32"),
    ("native_calls", "non_pe_immediate_literals", 1, "instruction", "sha256"),
    ("native_calls", "first_target_base_relocation_scan", "directory", "sha256"),
    (
        "native_calls",
        "first_target_base_relocation_scan",
        "highlow_sites",
        0,
        "entry_raw",
    ),
    (
        "native_calls",
        "second_target_base_relocation_scan",
        "highlow_site_count_inside_target",
    ),
    ("native_calls", "import_and_iat_body_control_partition_complete"),
    ("whole_atlas_reference_scan", "references", 0, "instruction_sha256"),
    ("whole_atlas_reference_scan", "references", 478, "owner_entry_rva"),
    ("whole_atlas_reference_scan", "target_partition", 0, "reference_count"),
    ("whole_atlas_reference_scan", "owner_partition", 0, "reference_count"),
    ("whole_atlas_reference_scan", "target_owner_partition", 1, "owner_entry_rva"),
    ("whole_atlas_reference_scan", "target_reference_partition", 1, "reference_count"),
    ("whole_atlas_reference_scan", "partition_sha256", "references"),
    ("whole_atlas_reference_scan", "partition_sha256", "target_owner_partition"),
    ("whole_atlas_reference_scan", "aggregates", "owner_count"),
    ("method", "not_claimed", 0),
    ("summary", "target_reference_count"),
]


@pytest.mark.parametrize("path", TAMPER_PATHS)
def test_structure_rejects_every_retained_partition(
    values: dict[str, Any], path: tuple[Any, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    current: Any = values["evidence"]
    for key in path:
        current = current[key]
    altered = _replace(values["evidence"], path, _changed(current))
    with pytest.raises(
        NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError
    ):
        _fast_structure(monkeypatch, values, altered)


@pytest.mark.parametrize(
    "path",
    [
        ("unexpected",),
        ("function_bodies", 0, "unexpected"),
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
    with pytest.raises(
        NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError
    ):
        _fast_structure(monkeypatch, values, evidence)


def test_outgoing_partition_rejects_an_injected_edge(values: dict[str, Any]) -> None:
    facts = copy.deepcopy(values["facts"])
    facts["ghidra_declared_direct_calls"].append(
        {
            "instruction_rva": "0x00385bd1",
            "source_entry_rva": "0x00385bcc",
            "target_entry_rva": "0x00385bcc",
            "target_rva": "0x00385bcc",
            "target_name": "injected",
        }
    )
    with pytest.raises(
        NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError,
        match="outgoing direct-edge partition",
    ):
        helper._native_calls(facts)


def test_deterministic_encoding_and_pinned_hashes(values: dict[str, Any]) -> None:
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
        values["evidence"]
    )
    assert rendered.encode() == values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(rendered.encode()).hexdigest() == RAW_SHA256
    assert helper._canonical_sha256(values["evidence"]) == CANONICAL_SHA256
    with pytest.raises(
        NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError
    ):
        helper.encode_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
            {"x": float("nan")}
        )


def _patch_output_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    info = tmp_path.stat()
    monkeypatch.setattr(cli, "_prepare_output_root", lambda: (tmp_path, tmp_path, info))
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def _forbid_unlink(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("publication must not unlink any pathname")

    monkeypatch.setattr(cli.os, "unlink", forbidden)
    monkeypatch.setattr(Path, "unlink", forbidden)


def test_writer_is_immutable_and_preserves_differing_output(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
        values["evidence"]
    )
    cli._write_immutably(output, rendered, values["evidence"])
    stage = cli._retained_stage_path(tmp_path, rendered.encode())
    assert stage.is_file()
    assert os.path.samefile(stage, output)
    cli._write_immutably(output, rendered, values["evidence"])
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(rendered.encode() + b" ")
    os.replace(replacement, output)
    with pytest.raises(
        NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError,
        match="refusing to overwrite",
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode() + b" "
    assert stage.read_bytes() == rendered.encode()


def test_writer_normalizes_imported_publication_errors(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "existing.json"
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
        values["evidence"]
    )
    output.write_bytes(rendered.encode())
    original_locked_output = cli._locked_output

    def lock_failure(*args: Any, **kwargs: Any) -> None:
        raise NativeAssertionHelperStaticBoundaryError("injected lock failure")

    monkeypatch.setattr(cli, "_locked_output", lock_failure)
    with pytest.raises(
        NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError,
        match="injected lock failure",
    ):
        cli._write_immutably(output, rendered, values["evidence"])

    monkeypatch.setattr(cli, "_locked_output", original_locked_output)

    def root_failure() -> None:
        raise NativeLuaPropertyFactoryChainError("injected root failure")

    monkeypatch.setattr(cli, "_prepare_output_root", root_failure)
    with pytest.raises(
        NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError,
        match="injected root failure",
    ):
        cli._write_immutably(output, rendered, values["evidence"])


def test_writer_retains_content_addressed_stage_after_early_io_failure(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    _forbid_unlink(monkeypatch)
    output = tmp_path / "early.json"
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
        values["evidence"]
    )

    def fsync_failure(descriptor: int) -> None:
        raise OSError("injected fsync failure")

    monkeypatch.setattr(cli.os, "fsync", fsync_failure)
    with pytest.raises(OSError, match="injected fsync failure"):
        cli._write_immutably(output, rendered, values["evidence"])
    stage = cli._retained_stage_path(tmp_path, rendered.encode())
    assert stage.is_file()
    assert not output.exists()


def test_writer_final_lock_matches_platform_semantics(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "existing.json"
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
        values["evidence"]
    )
    output.write_bytes(rendered.encode())
    original, attempts = cli._read_locked_json_document, []

    def contender() -> None:
        try:
            with output.open("ab") as stream:
                if os.name != "nt":
                    import fcntl

                    try:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except OSError as exc:
                        if exc.errno not in (errno.EACCES, errno.EAGAIN):
                            raise
                        attempts.append("blocked")
                        return
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


def test_writer_preserves_created_output_on_final_validation_failure(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    _forbid_unlink(monkeypatch)
    output = tmp_path / "new.json"
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
        values["evidence"]
    )
    altered = copy.deepcopy(values["evidence"])
    altered["summary"]["reviewed_target_bytes"] += 1
    original = cli._read_locked_json_document

    def fail_final_created(descriptor: int, label: str):
        if label == "final created output":
            return altered, helper._canonical_bytes(altered)
        return original(descriptor, label)

    monkeypatch.setattr(cli, "_read_locked_json_document", fail_final_created)
    with pytest.raises(
        NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError,
        match="created output changed during final content validation",
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    stage = cli._retained_stage_path(tmp_path, rendered.encode())
    assert output.read_bytes() == rendered.encode()
    assert os.path.samefile(stage, output)


def test_writer_preserves_destination_replacement_after_link(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    _forbid_unlink(monkeypatch)
    output = tmp_path / "replaced.json"
    replacement = tmp_path / "contender.json"
    replacement.write_bytes(b"contender replacement")
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
        values["evidence"]
    )
    original_link = cli.os.link

    def link_then_replace(source: Path, destination: Path, **kwargs: Any) -> None:
        original_link(source, destination, **kwargs)
        os.replace(replacement, destination)

    monkeypatch.setattr(cli.os, "link", link_then_replace)
    with pytest.raises(
        NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError,
        match="identity check",
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    stage = cli._retained_stage_path(tmp_path, rendered.encode())
    assert output.read_bytes() == b"contender replacement"
    assert stage.read_bytes() == rendered.encode()


def test_writer_rejects_stage_replacement_between_validation_and_link(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    _forbid_unlink(monkeypatch)
    output = tmp_path / "stage-race.json"
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
        values["evidence"]
    )
    stage = cli._retained_stage_path(tmp_path, rendered.encode())
    stage.write_bytes(rendered.encode())
    contender = tmp_path / "stage-contender.json"
    contender.write_bytes(b"stage contender")
    original_link = cli.os.link

    def replace_then_link(source: Path, destination: Path, **kwargs: Any) -> None:
        os.replace(contender, source)
        original_link(source, destination, **kwargs)

    monkeypatch.setattr(cli.os, "link", replace_then_link)
    with pytest.raises(
        NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError,
        match="identity check",
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    assert stage.read_bytes() == b"stage contender"
    assert output.read_bytes() == b"stage contender"
    assert os.path.samefile(stage, output)


def test_writer_rejects_differing_retained_stage_without_mutation(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    _forbid_unlink(monkeypatch)
    output = tmp_path / "blocked.json"
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
        values["evidence"]
    )
    stage = cli._retained_stage_path(tmp_path, rendered.encode())
    stage.write_bytes(b"{}")
    with pytest.raises(
        NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    assert stage.read_bytes() == b"{}"
    assert not output.exists()


def test_writer_reuses_exact_precreated_stage_idempotently(
    values: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    _forbid_unlink(monkeypatch)
    output = tmp_path / "reused.json"
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
        values["evidence"]
    )
    stage = cli._retained_stage_path(tmp_path, rendered.encode())
    stage.write_bytes(rendered.encode())
    cli._write_immutably(output, rendered, values["evidence"])
    cli._write_immutably(output, rendered, values["evidence"])
    assert os.path.samefile(stage, output)


@pytest.mark.parametrize("phase", ["link", "root", "lock"])
def test_writer_retains_stage_and_created_output_across_publication_failures(
    phase: str,
    values: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_output_root(monkeypatch, tmp_path)
    _forbid_unlink(monkeypatch)
    output = tmp_path / f"{phase}.json"
    rendered = helper.encode_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
        values["evidence"]
    )
    if phase == "link":
        monkeypatch.setattr(
            cli.os,
            "link",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                OSError("injected link failure")
            ),
        )
    elif phase == "root":
        calls = 0

        def root_failure(*args: Any) -> None:
            nonlocal calls
            calls += 1
            if calls == 4:
                raise NativeLuaPropertyFactoryChainError(
                    "injected post-link root failure"
                )

        monkeypatch.setattr(cli, "_recheck_output_root", root_failure)
    else:
        original_locked_output = cli._locked_output

        def lock_failure(path: Path, *args: Any, **kwargs: Any):
            if path == output:
                raise NativeAssertionHelperStaticBoundaryError(
                    "injected created-output lock failure"
                )
            return original_locked_output(path, *args, **kwargs)

        monkeypatch.setattr(cli, "_locked_output", lock_failure)

    with pytest.raises(
        (
            OSError
            if phase == "link"
            else NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError
        )
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    stage = cli._retained_stage_path(tmp_path, rendered.encode())
    assert stage.is_file()
    if phase == "link":
        assert not output.exists()
    else:
        assert output.is_file()
        assert os.path.samefile(stage, output)


def test_cli_parser_and_strict_json_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    parsed = cli.build_parser().parse_args(
        [
            "build",
            "--first-callee-static-boundary",
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
    assert (
        cli.main(
            [
                "verify-structure",
                "--first-callee-static-boundary",
                str(bad),
                "--direct-calls",
                str(bad),
                "--program-facts",
                str(bad),
                "--evidence",
                str(bad),
            ]
        )
        == 1
    )
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


def _allow_altered_relocation_directory(
    monkeypatch: pytest.MonkeyPatch, altered_data: bytes
) -> None:
    offset, size = helper._RELOCATION_DIRECTORY[2], helper._RELOCATION_DIRECTORY[1]
    altered_directory = altered_data[offset : offset + size]
    original_sha256 = helper.hashlib.sha256

    class PinnedDirectoryDigest:
        def hexdigest(self) -> str:
            return helper._RELOCATION_DIRECTORY[3]

    def digest(payload: bytes = b""):
        if bytes(payload) == altered_directory:
            return PinnedDirectoryDigest()
        return original_sha256(payload)

    monkeypatch.setattr(helper.hashlib, "sha256", digest)


def test_exact_rebuild_relocation_and_reference_scanners(
    values: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _exact_executable()
    rebuilt = helper.build_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
        executable, *_common(values), inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    data, image, _ = helper._load_executable(executable)

    original_sha256 = helper.hashlib.sha256
    for entry_offset, replacement in ((0x533160, "d603"), (0x532E38, "f23e")):
        altered = bytearray(data)
        altered[entry_offset : entry_offset + 2] = bytes.fromhex(replacement)
        _allow_altered_relocation_directory(monkeypatch, bytes(altered))
        with pytest.raises(
            NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError,
            match="HIGHLOW relocation frontier",
        ):
            helper._native_calls(values["facts"], type(image)(bytes(altered)))
        monkeypatch.setattr(helper.hashlib, "sha256", original_sha256)

    decoder, _ = helper._decoder()
    assert helper._whole_atlas_reference_scan(
        data, image, decoder, values["facts"]
    ) == helper._expected_scan(values["facts"])
    original_decode = helper._decode_range
    import capstone

    mutations = (
        (0x38E3BC, 17, "b8cc5b7800"),
        (0x38E3BC, 17, "a1cc5b7800"),
        (0x38E3C7, 19, "b8f29e7700"),
        (0x38E3C7, 19, "a1f29e7700"),
    )
    for site, index, encoded in mutations:

        def altered_decode(
            data: bytes,
            image: Any,
            start: int,
            size: int,
            decoder: Any,
            site: int = site,
            index: int = index,
            encoded: str = encoded,
        ):
            rows = original_decode(data, image, start, size, decoder)
            if start == 0x38E392:
                changed = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
                changed.detail = True
                replacement = list(
                    changed.disasm(bytes.fromhex(encoded), image.image_base + site)
                )
                assert rows[index].address - image.image_base == site
                assert len(replacement) == 1 and replacement[0].size == rows[index].size
                rows[index] = replacement[0]
            return rows

        monkeypatch.setattr(helper, "_decode_range", altered_decode)
        changed_decoder, _ = helper._decoder()
        with pytest.raises(
            NativeAssertionHelperFirstCalleeDirectCalleePairStaticBoundaryError,
            match="all-operand paired",
        ):
            helper._whole_atlas_reference_scan(
                data, image, changed_decoder, values["facts"]
            )
        monkeypatch.setattr(helper, "_decode_range", original_decode)


def test_exact_validator_and_cli(
    values: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    executable = _exact_executable()
    receipt = helper.validate_native_assertion_helper_first_callee_direct_callee_pair_static_boundary(
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
                "--first-callee-static-boundary",
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
