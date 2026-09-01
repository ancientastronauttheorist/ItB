"""Focused checks for the opaque 0x00378a40 static-boundary receipt."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts import (
    itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary as cli,
)
from src.observatory import (
    native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary as helper,
)

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "windows_build_13725832_31fe35265598_"
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
RAW_SHA256 = "105170018df7456821dc09c7e762b933f490eb9544131cb94a4b8c49810669ed"
CANONICAL_SHA256 = "1faeeefe0ee5d9bc9a85ad673133dc7936a02cfea50beb5cd70d72fc36bcb9c5"
Error = (
    helper.NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeStaticBoundaryError
)


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values():
    names = {
        "parent": "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json",
        "second": "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary.json",
        "direct": "native_lua_direct_call_census.json",
        "facts": "program_facts.json",
        "evidence": "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary.json",
    }
    paths = {key: PROGRAMS / (PREFIX + value) for key, value in names.items()}
    paths["inventory"] = INVENTORIES / (
        PREFIX + "full_decompile_baseline_20260830.json"
    )
    return {**{key: _read(path) for key, path in paths.items()}, "paths": paths}


def _common(values):
    return (
        values["parent"],
        values["second"],
        values["direct"],
        values["facts"],
    )


def _structure(values, evidence=None):
    return helper.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary_structure(
        values["evidence"] if evidence is None else evidence, *_common(values)
    )


def _replace(value, path, replacement):
    result = copy.deepcopy(value)
    cursor = result
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement
    return result


def _exact_executable():
    configured = os.environ.get("ITB_EXACT_EXE")
    if not configured:
        pytest.skip("set ITB_EXACT_EXE for expensive exact PE checks")
    path = Path(configured)
    if (
        not path.is_file()
        or hashlib.sha256(path.read_bytes()).hexdigest() != EXE_SHA256
    ):
        pytest.skip("ITB_EXACT_EXE is not the sealed executable")
    return path


def test_decoder_cfg_native_partitions_and_dependent_rejoin(values):
    rows = helper._decode()
    assert len(rows) == 48
    assert b"".join(bytes(row.bytes) for row in rows).hex() == helper._RAW
    assert rows[-1].mnemonic == "ret"
    graph = helper._graph(rows)
    assert (graph["node_count"], graph["edge_count"]) == (48, 51)
    assert helper._canonical_sha256(graph) == helper._CFG

    calls = helper._native_calls(values["facts"], values["second"])
    assert [
        (row["instruction"]["rva"], row["target_entry_rva"])
        for row in calls["outgoing_direct"]
    ] == [
        ("0x00378aae", "0x00378a15"),
        ("0x00378abb", "0x00378a34"),
    ]
    assert calls["direct_lua_calls"] == calls["staged_lua_dispatches"] == []
    assert calls["opaque_indirect_controls"] == []
    assert len(calls["pe_address_operands"]) == 9
    assert [row["operand_class"] for row in calls["pe_address_operands"]].count(
        "immediate"
    ) == 8
    assert [row["operand_class"] for row in calls["pe_address_operands"]].count(
        "absolute_memory"
    ) == 1
    assert len(calls["non_pe_immediate_literals"]) == 6
    assert [
        row["instruction"]["rva"] for row in calls["segment_qualified_memory_syntax"]
    ] == ["0x00378a59", "0x00378a6b", "0x00378ac2"]
    assert calls["second_callee_dependent_rejoin"] == {
        "dependent_analysis_kind": helper.SECOND_KIND,
        "dependent_canonical_sha256": helper._SECOND,
        "instruction_rva": "0x00378aae",
        "owner_entry_rva": "0x00378a40",
        "target_entry_rva": "0x00378a15",
        "reference_rejoined": True,
    }


def test_committed_artifact_identity_and_structural_reconstruction(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary(
        evidence
    ).encode(
        "utf-8"
    )
    assert hashlib.sha256(raw).hexdigest() == RAW_SHA256
    assert raw == rendered
    assert helper._canonical_sha256(evidence) == CANONICAL_SHA256
    assert evidence == helper._evidence(*_common(values))

    certificate = _structure(values)
    assert certificate["status"] == "structurally_verified"
    assert certificate["evidence_sha256"] == CANONICAL_SHA256
    assert evidence["predecessor_static_boundary"]["canonical_sha256"] == helper._PARENT
    assert (
        evidence["second_callee_static_boundary"]["canonical_sha256"] == helper._SECOND
    )

    entry_scan = evidence["whole_atlas_reference_scan"]
    assert [
        (row["instruction_rva"], row["owner_entry_rva"])
        for row in entry_scan["references"]
    ] == [
        ("0x00378b92", "0x00378b87"),
        ("0x00386e8f", "0x00386dc7"),
        ("0x00386fb7", "0x00386ef2"),
    ]
    endpoint_scan = evidence["whole_atlas_target_end_pointer_scan"]
    assert [
        (
            row["instruction_rva"],
            row["owner_entry_rva"],
            row["target_rva"],
            row["use_class"],
        )
        for row in endpoint_scan["references"]
    ] == [("0x00378a54", "0x00378a40", "0x00378ad0", "other_address")]
    assert entry_scan["scope"] == endpoint_scan["scope"]
    assert entry_scan["scope"]["atlas_function_count"] == 25312
    assert entry_scan["scope"]["atlas_body_range_count"] == 25490


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("analysis_kind",), "changed"),
        (("build_identity", "executable_sha256"), "0" * 64),
        (("program_facts", "canonical_sha256"), "0" * 64),
        (("predecessor_static_boundary", "canonical_sha256"), "0" * 64),
        (("second_callee_static_boundary", "canonical_sha256"), "0" * 64),
        (("function_body", "body_sha256"), "0" * 64),
        (("function_body", "target_pe_backing", "file_offset"), "0x00000000"),
        (
            (
                "function_body",
                "adjacent_atlas_boundaries",
                "left_gap",
                "bytes_sha256",
            ),
            "0" * 64,
        ),
        (
            (
                "function_body",
                "adjacent_atlas_boundaries",
                "right_un_atlased_gap",
                "size",
            ),
            109,
        ),
        (
            (
                "function_body",
                "adjacent_atlas_boundaries",
                "right_neighbor",
                "range_start_rva",
            ),
            "0x00000000",
        ),
        (("control_flow_graph", "nodes", -1, "flow_kind"), "changed"),
        (("predecessor_parent_edges", 0, "source_body_sha256"), "0" * 64),
        (("native_calls", "outgoing_direct", 1, "target_body_sha256"), "0" * 64),
        (
            (
                "native_calls",
                "second_callee_dependent_rejoin",
                "target_entry_rva",
            ),
            "0x00000000",
        ),
        (
            ("native_calls", "pe_address_operands", 1, "opaque_file_bytes_sha256"),
            "0" * 64,
        ),
        (("native_calls", "non_pe_immediate_literals", 0, "value"), "0x0"),
        (
            ("native_calls", "segment_qualified_memory_syntax", 0, "operand_access"),
            "write",
        ),
        (
            ("whole_atlas_reference_scan", "references", 0, "owner_entry_rva"),
            "0x00000000",
        ),
        (
            (
                "whole_atlas_target_end_pointer_scan",
                "references",
                0,
                "target_rva",
            ),
            "0x00000000",
        ),
        (("method", "structural_boundary"), "changed"),
        (("summary", "sealed_gap_count"), 1),
    ],
)
def test_structure_fails_closed_on_retained_mutations(values, path, replacement):
    with pytest.raises(Error):
        _structure(values, _replace(values["evidence"], path, replacement))


def test_public_apis_reject_non_object_roots(values):
    with pytest.raises(Error):
        _structure(values, [])
    for index in range(4):
        common = list(_common(values))
        common[index] = []
        with pytest.raises(Error):
            helper.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary_structure(
                values["evidence"], *common
            )
    with pytest.raises(Error):
        helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary(
            []
        )
    with pytest.raises(Error):
        helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary(
            {"x": float("nan")}
        )


def _cli_structure_args(values, evidence=None):
    paths = values["paths"]
    return [
        "verify-structure",
        "--adjacent-callee-cluster-static-boundary",
        str(paths["parent"]),
        "--second-callee-static-boundary",
        str(paths["second"]),
        "--direct-calls",
        str(paths["direct"]),
        "--program-facts",
        str(paths["facts"]),
        "--evidence",
        str(paths["evidence"] if evidence is None else evidence),
    ]


def test_cli_parser_verify_structure_and_read_error(values, tmp_path, capsys):
    common = [
        "--adjacent-callee-cluster-static-boundary",
        "p.json",
        "--second-callee-static-boundary",
        "s.json",
        "--direct-calls",
        "d.json",
        "--program-facts",
        "f.json",
    ]
    parsed = cli.build_parser().parse_args(
        [
            "build",
            *common,
            "--executable",
            "Breach.exe",
            "--inventory",
            "i.json",
            "--output",
            "o.json",
        ]
    )
    assert parsed.command == "build"
    assert parsed.second_callee_static_boundary == Path("s.json")

    assert cli.main(_cli_structure_args(values)) == 0
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["status"] == "structurally_verified"
    assert certificate["evidence_sha256"] == CANONICAL_SHA256

    missing = tmp_path / "missing-parent.json"
    arguments = _cli_structure_args(values)
    arguments[arguments.index("--adjacent-callee-cluster-static-boundary") + 1] = str(
        missing
    )
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
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary(
        values["evidence"]
    )
    cli._write_immutably(output, rendered, values["evidence"])
    cli._write_immutably(output, rendered, values["evidence"])
    output.write_bytes(rendered.encode("utf-8") + b" ")
    with pytest.raises(Error, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, values["evidence"])
    assert output.read_bytes() == rendered.encode("utf-8") + b" "

    with pytest.raises(Error, match="direct child"):
        cli._write_immutably(
            tmp_path / "nested" / "evidence.json", rendered, values["evidence"]
        )
    outside = tmp_path.parent / (tmp_path.name + "-outside.json")
    with pytest.raises(Error, match="direct child"):
        cli._write_immutably(outside, rendered, values["evidence"])


def test_cli_writer_final_validation_cleans_failed_new_publication(
    values, tmp_path, monkeypatch
):
    _patch_output_root(monkeypatch, tmp_path)
    output = tmp_path / "evidence.json"
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary(
        values["evidence"]
    )
    original = cli._read_locked_json_document

    def corrupt(descriptor, label):
        value, payload = original(descriptor, label)
        return value, payload + b" "

    monkeypatch.setattr(cli, "_read_locked_json_document", corrupt)
    with pytest.raises(Error, match="final content validation"):
        cli._write_immutably(output, rendered, values["evidence"])
    assert not output.exists()


@pytest.mark.parametrize(
    "upstream_error",
    (
        cli.NativeAssertionHelperStaticBoundaryError,
        cli.NativeLuaCClosurePublicationError,
        cli.NativeLuaDirectCallError,
        cli.NativeLuaPropertyFactoryChainError,
    ),
)
def test_cli_writer_normalizes_upstream_domain_errors(
    values, tmp_path, monkeypatch, upstream_error
):
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary(
        values["evidence"]
    )

    def fail(*_args):
        raise upstream_error("upstream")

    monkeypatch.setattr(cli, "_write_immutably_impl", fail)
    with pytest.raises(Error, match="upstream"):
        cli._write_immutably(tmp_path / "evidence.json", rendered, values["evidence"])


def test_exact_rebuild_and_validate(values):
    executable = _exact_executable()
    rebuilt = helper.build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary(
        executable,
        *_common(values),
        inventory=values["inventory"],
    )
    assert rebuilt == values["evidence"]
    certificate = helper.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary(
        executable,
        rebuilt,
        *_common(values),
        inventory=values["inventory"],
    )
    assert certificate["status"] == "verified"
    assert certificate["evidence_sha256"] == CANONICAL_SHA256


def test_exact_target_and_endpoint_scan_mutation_seams(values, monkeypatch):
    executable = _exact_executable()
    data, image, digest = helper._load_executable(executable)
    assert digest == EXE_SHA256
    original = helper._decode_range
    import capstone

    for injected in (
        "b8408a7700",
        "a1408a7700",
        "b8d08a7700",
        "a1d08a7700",
    ):

        def altered(data, image, start, size, decoder, injected=injected):
            rows = original(data, image, start, size, decoder)
            if start == 0x378B6E:
                assert rows[7].address == image.image_base + 0x378B77
                disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
                disassembler.detail = True
                replacement = list(
                    disassembler.disasm(
                        bytes.fromhex(injected), image.image_base + 0x378B77
                    )
                )
                assert len(replacement) == 1 and replacement[0].size == rows[7].size
                rows[7] = replacement[0]
            return rows

        monkeypatch.setattr(helper, "_decode_range", altered)
        decoder, _ = helper._decoder()
        with pytest.raises(Error, match="all-operand"):
            helper._whole_atlas_reference_scan(data, image, decoder, values["facts"])
        monkeypatch.setattr(helper, "_decode_range", original)


def test_exact_pe_body_gap_and_data_mutation_seams(values):
    executable = _exact_executable()
    data, image, _digest = helper._load_executable(executable)
    assert helper._target_pe_backing(image)["file_offset"] == "0x00377e40"
    boundaries = helper._adjacent_atlas_boundaries(values["facts"], image)
    assert boundaries["left_gap"]["size"] == 9
    assert boundaries["right_un_atlased_gap"]["size"] == 110
    assert values["evidence"]["summary"]["sealed_un_atlased_gap_bytes"] == 119
    calls = helper._native_calls(values["facts"], values["second"], image)
    assert calls["pe_address_operands"][1]["file_offset"] == "0x00492128"

    changed = bytearray(data)
    changed[image.rva_span_to_file_offset(0x378A40, 144)] ^= 0x01
    with pytest.raises(Error, match="target PE bytes"):
        helper._target_pe_backing(type(image)(bytes(changed)))

    changed = bytearray(data)
    changed[image.rva_span_to_file_offset(0x378A37, 9)] ^= 0x01
    with pytest.raises(Error, match="left gap backing"):
        helper._adjacent_atlas_boundaries(values["facts"], type(image)(bytes(changed)))

    changed = bytearray(data)
    changed[image.rva_span_to_file_offset(0x378AD4, 1)] ^= 0x01
    with pytest.raises(Error, match="right gap backing"):
        helper._adjacent_atlas_boundaries(values["facts"], type(image)(bytes(changed)))

    changed = bytearray(data)
    changed[image.rva_span_to_file_offset(0x493F28, 4)] ^= 0x01
    with pytest.raises(Error, match="PE-address operand backing"):
        helper._native_calls(
            values["facts"], values["second"], type(image)(bytes(changed))
        )
