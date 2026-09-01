import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts import (
    itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary as cli,
)
from src.observatory import (
    native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary as target,
)
from src.observatory.native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary import (
    NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
PREFIX = "windows_build_13725832_31fe35265598_"
EXE = Path(os.environ.get("ITB_EXACT_EXE", ""))
RAW = "2f56d4bc7413036890013f70de5e202835f3254491048f17612a76c80a072f9b"
CANONICAL = "1222126b3527186a823ffb252a97ddc2beb7a0c4dc49b45e15e462fb244b2a5b"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values():
    paths = {
        "parent": PROGRAMS
        / (
            PREFIX
            + "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json"
        ),
        "direct": PROGRAMS / (PREFIX + "native_lua_direct_call_census.json"),
        "facts": PROGRAMS / (PREFIX + "program_facts.json"),
        "inventory": INVENTORIES / (PREFIX + "full_decompile_baseline_20260830.json"),
        "evidence": PROGRAMS
        / (
            PREFIX
            + "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary.json"
        ),
    }
    result = {key: _read(path) for key, path in paths.items()}
    result["paths"] = paths
    return result


def _replace(value, path, replacement):
    result = copy.deepcopy(value)
    cursor = result
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement
    return result


def _changed(value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        return "changed"
    raise AssertionError(type(value))


def _reject(values, evidence, monkeypatch):
    monkeypatch.setattr(
        target,
        "validate_native_lua_direct_call_structure",
        lambda *_args, **_kwargs: {
            "status": "structurally_verified",
            "evidence_sha256": target._DIRECT,
        },
    )
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError
    ):
        target.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary_structure(
            evidence, values["parent"], values["direct"], values["facts"]
        )


def test_committed_artifact_identity_and_structural_reconstruction(values):
    raw = values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW
    assert raw == target.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
        values["evidence"]
    ).encode(
        "utf-8"
    )
    assert target._canonical_sha256(values["evidence"]) == CANONICAL
    assert values["evidence"] == target._evidence(
        values["parent"], values["direct"], values["facts"]
    )
    certificate = target.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary_structure(
        values["evidence"], values["parent"], values["direct"], values["facts"]
    )
    assert certificate["status"] == "structurally_verified"
    assert certificate["evidence_sha256"] == CANONICAL


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("schema_version",), 2),
        (("analysis_kind",), "wrong"),
        (("build_identity", "executable_sha256"), "0" * 64),
        (("atlas", "canonical_sha256"), "0" * 64),
        (("parent_static_boundary", "canonical_sha256"), "0" * 64),
        (("direct_call_census", "canonical_sha256"), "0" * 64),
        (("decoder", "sealed_instruction_count"), 2),
        (("function_body", "body_size"), 7),
        (("function_body", "body_sha256"), "0" * 64),
        (("function_body", "target_atlas_metadata", "name"), "changed"),
        (("function_body", "target_pe_backing", "file_offset"), "0x0"),
        (("function_body", "reviewed_points", 0, "rva"), "0x0"),
        (("function_body", "reviewed_points", 0, "sha256"), "0" * 64),
        (("control_flow_graph", "node_count"), 2),
        (("control_flow_graph", "nodes", 0, "flow_kind"), "return"),
        (("parent_rejoin_edge", "source_body_sha256"), "0" * 64),
        (("parent_rejoin_edge", "target_atlas_record_sha256"), "0" * 64),
        (("native_calls", "opaque_indirect_controls", 0, "control_encoding"), "ff15"),
        (("native_calls", "pe_address_operands", 0, "operand_rva"), "0x0"),
        (
            (
                "native_calls",
                "pe_address_operands",
                0,
                "raw_pe_import_table_binding",
                "descriptor_index",
            ),
            8,
        ),
        (
            (
                "native_calls",
                "pe_address_operands",
                0,
                "raw_pe_import_table_binding",
                "lookup_thunk_raw_value",
            ),
            "0x0",
        ),
        (
            (
                "native_calls",
                "pe_address_operands",
                0,
                "raw_pe_import_table_binding",
                "hint",
            ),
            0,
        ),
        (("whole_atlas_reference_scan", "references", 0, "instruction_rva"), "0x0"),
        (("whole_atlas_reference_scan", "references", 1, "owner_entry_rva"), "0x0"),
        (
            (
                "whole_atlas_reference_scan",
                "references",
                2,
                "ghidra_declared_direct_edge",
                "target_name_sha256",
            ),
            "0" * 64,
        ),
        (
            ("whole_atlas_reference_scan", "partition_sha256", "owner_partition"),
            "0" * 64,
        ),
        (("whole_atlas_reference_scan", "references_canonical_sha256"), "0" * 64),
        (
            ("whole_atlas_iat_slot_use_scan", "references", 0, "control_syntax"),
            "changed",
        ),
        (
            ("whole_atlas_iat_slot_use_scan", "references", 1, "instruction_sha256"),
            "0" * 64,
        ),
        (
            ("whole_atlas_iat_slot_use_scan", "owner_partition", 0, "owner_entry_rva"),
            "0x0",
        ),
        (
            ("whole_atlas_iat_slot_use_scan", "partition_sha256", "owner_partition"),
            "0" * 64,
        ),
        (("method", "structural_boundary"), "changed"),
        (("method", "not_claimed", 0), "changed"),
        (("summary", "iat_slot_reference_count"), 1),
        (("summary", "target_reference_count"), 4),
    ],
)
def test_structural_receipt_mutations_reject(values, path, replacement, monkeypatch):
    _reject(values, _replace(values["evidence"], path, replacement), monkeypatch)


def test_empty_and_complete_partitions_are_pinned(values):
    evidence = values["evidence"]
    assert evidence["native_calls"]["outgoing_direct"] == []
    assert evidence["native_calls"]["outgoing_direct_partition_complete"] is True
    assert evidence["native_calls"]["segment_qualified_memory_syntax"] == []
    assert evidence["native_calls"]["bnd_prefixed_control_syntax"] == []
    assert evidence["native_calls"]["opaque_interrupt_syntax"] == []
    assert evidence["native_calls"]["non_pe_immediate_operands"] == []
    assert evidence["function_body"]["direct_lua_partition_complete"] is True
    assert evidence["function_body"]["staged_lua_partition_complete"] is True
    assert evidence["whole_atlas_reference_scan"]["aggregates"]["reference_count"] == 3
    assert (
        evidence["whole_atlas_iat_slot_use_scan"]["aggregates"]["reference_count"] == 2
    )


def test_public_api_rejects_non_object_roots_with_domain_error(values):
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError
    ):
        target.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary_structure(
            values["evidence"], [], values["direct"], values["facts"]
        )
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError
    ):
        target.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
            []
        )


def test_raw_import_binding_rejects_every_published_field(monkeypatch):
    if not EXE.is_file():
        pytest.skip("ITB_EXACT_EXE is not set to the sealed executable")
    from src.observatory.native_lua_direct_calls import _load_executable

    _data, image, _digest = _load_executable(EXE)
    baseline = dict(target._RAW_BINDING)
    assert target._raw_import_binding(image) == baseline
    for field, value in baseline.items():
        altered = dict(baseline)
        altered[field] = _changed(value)
        monkeypatch.setattr(target, "_RAW_BINDING", altered)
        with pytest.raises(
            NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError,
            match="differ",
        ):
            target._raw_import_binding(image)
    monkeypatch.setattr(target, "_RAW_BINDING", baseline)


def _cli_structure_args(values, evidence=None):
    paths = values["paths"]
    return [
        "verify-structure",
        "--parent-static-boundary",
        str(paths["parent"]),
        "--direct-calls",
        str(paths["direct"]),
        "--program-facts",
        str(paths["facts"]),
        "--evidence",
        str(paths["evidence"] if evidence is None else evidence),
    ]


def test_cli_verify_structure_and_read_error_status(values, tmp_path, capsys):
    assert cli.main(_cli_structure_args(values)) == 0
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["status"] == "structurally_verified"
    assert certificate["evidence_sha256"] == CANONICAL

    missing = tmp_path / "missing-parent.json"
    arguments = _cli_structure_args(values)
    arguments[arguments.index("--parent-static-boundary") + 1] = str(missing)
    assert cli.main(arguments) == 1
    assert "error:" in capsys.readouterr().err


def test_cli_rejects_nondeterministic_evidence(values, tmp_path, capsys):
    compact = tmp_path / "compact-evidence.json"
    compact.write_text(json.dumps(values["evidence"]), encoding="utf-8")
    assert cli.main(_cli_structure_args(values, compact)) == 1
    assert "not deterministically encoded" in capsys.readouterr().err


def _patch_output_root(monkeypatch, temporary):
    before = temporary.stat()
    monkeypatch.setattr(
        cli, "_prepare_output_root", lambda: (temporary, temporary, before)
    )
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *args: None)


def test_cli_writer_is_immutable_and_preserves_differing_output(
    values, tmp_path, monkeypatch
):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = target.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
        values["evidence"]
    )
    cli._write_immutably(output, rendered, values["evidence"])
    cli._write_immutably(output, rendered, values["evidence"])
    output.write_bytes(rendered.encode("utf-8") + b" ")
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError,
        match="refusing to overwrite",
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode("utf-8") + b" "
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError,
        match="direct child",
    ):
        cli._write_immutably(
            tmp_path / "nested" / "evidence.json", rendered, values["evidence"]
        )


def test_cli_writer_final_validation_cleans_failed_new_publication(
    values, tmp_path, monkeypatch
):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = target.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
        values["evidence"]
    )
    original = cli._read_locked_json_document

    def corrupt(descriptor, label):
        value, payload = original(descriptor, label)
        return value, payload + b" "

    monkeypatch.setattr(cli, "_read_locked_json_document", corrupt)
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError,
        match="final content validation",
    ):
        cli._write_immutably(output, rendered, values["evidence"])
    assert not output.exists()


def test_exact_rebuild_and_artifact_when_executable_is_available(values):
    if not EXE.is_file():
        pytest.skip("sealed executable unavailable")
    rebuilt = target.build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
        EXE,
        values["parent"],
        values["direct"],
        values["facts"],
        inventory=values["inventory"],
    )
    assert rebuilt == values["evidence"]
    assert (
        target.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary(
            EXE,
            rebuilt,
            values["parent"],
            values["direct"],
            values["facts"],
            inventory=values["inventory"],
        )[
            "status"
        ]
        == "verified"
    )


@pytest.mark.parametrize("encoded", ("b898cb7900", "a198cb7900"))
def test_exact_target_scan_rejects_nonvacuous_parent_operand_mutations(values, encoded):
    if not EXE.is_file():
        pytest.skip("ITB_EXACT_EXE is not set to the sealed executable")
    from src.observatory.native_lua_direct_calls import _decoder, _load_executable

    data, image, _digest = _load_executable(EXE)
    changed = bytearray(data)
    offset = image.rva_to_file_offset(0x378B77)
    changed[offset : offset + 5] = bytes.fromhex(encoded)
    decoder, _ = _decoder()
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError
    ):
        target._scan(values["facts"], bytes(changed), image, decoder)


def test_exact_iat_slot_scan_rejects_root_displacement_mutation(values):
    if not EXE.is_file():
        pytest.skip("ITB_EXACT_EXE is not set to the sealed executable")
    from src.observatory.native_lua_direct_calls import _decoder, _load_executable

    data, image, _digest = _load_executable(EXE)
    changed = bytearray(data)
    offset = image.rva_to_file_offset(target._ENTRY)
    changed[offset + 2 : offset + 6] = (0x007D6174).to_bytes(4, "little")
    decoder, _ = _decoder()
    with pytest.raises(
        NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterThirdCalleeImportThunkStaticBoundaryError
    ):
        target._iat_scan(values["facts"], bytes(changed), image, decoder)
