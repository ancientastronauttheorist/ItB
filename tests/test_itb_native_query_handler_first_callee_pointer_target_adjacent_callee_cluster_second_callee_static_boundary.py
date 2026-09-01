"""Focused checks for the opaque 0x00378a15 static receipt."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts import (
    itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary as cli,
)
from src.observatory import (
    native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary as helper,
)

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "windows_build_13725832_31fe35265598_"
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
RAW_SHA256 = "f5f42474bb049805e9844ac5cb6bffe25f4a20b8caea22ef0120620fdaabd6b8"
CANONICAL_SHA256 = "ec66ae66eb932cb59f52ca3ad9095c31bb887723ed7647aef4eeeb0aaa64389d"
Error = (
    helper.NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterSecondCalleeStaticBoundaryError
)


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values():
    names = {
        "parent": "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json",
        "direct": "native_lua_direct_call_census.json",
        "facts": "program_facts.json",
        "evidence": "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary.json",
    }
    paths = {key: PROGRAMS / (PREFIX + value) for key, value in names.items()}
    paths["inventory"] = INVENTORIES / (
        PREFIX + "full_decompile_baseline_20260830.json"
    )
    return {**{key: _read(path) for key, path in paths.items()}, "paths": paths}


def _common(values):
    return values["parent"], values["direct"], values["facts"]


def _structure(values, evidence=None):
    return helper.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary_structure(
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


def test_decoder_points_cfg_and_opaque_partitions():
    rows = helper._decode()
    assert b"".join(bytes(row.bytes) for row in rows).hex() == helper._RAW
    assert len(rows) == 16 and rows[-1].mnemonic == "ret" and rows[-1].op_str == "4"
    graph = helper._graph(rows)
    assert (
        graph["node_count"],
        graph["edge_count"],
        helper._canonical_sha256(graph),
    ) == (16, 15, helper._CFG)
    calls = helper._native_calls(_read(PROGRAMS / (PREFIX + "program_facts.json")))
    assert (
        calls["outgoing_direct"]
        == calls["direct_lua_calls"]
        == calls["staged_lua_dispatches"]
        == []
    )
    assert calls["pe_address_operands"] == [
        {
            "role": "opaque_absolute_immediate_operand",
            "instruction": helper._instruction(0x378A17, "bb10408900"),
            "operand_class": "immediate",
            "operand_index": 1,
            "operand_access": "none",
            "operand_va": "0x00894010",
            "operand_rva": "0x00494010",
            "section_name": ".data",
            "section_rva": "0x00492000",
            "section_characteristics": "0xc0000040",
            "section_writable": True,
            "virtual_size": "0x000471cc",
            "raw_size": "0x00024800",
            "raw_offset": "0x00490200",
            "file_backed": True,
            "file_offset": "0x00492210",
            "opaque_file_bytes_size": 4,
            "opaque_file_bytes_sha256": "f0a19effaf081c6247b43afd3bc9f70ea771353137f4cce3ac38833893543af1",
            "contents_or_runtime_behavior_opaque": True,
        }
    ]
    assert calls["non_pe_immediate_literals"] == [
        {
            "instruction_rva": "0x00378a31",
            "operand_index": 0,
            "value": "0x00000004",
            "syntax": "x86_ret_imm16",
        }
    ]


def test_committed_artifact_identity_and_structural_reconstruction(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW_SHA256
    assert raw == helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary(
        evidence
    ).encode(
        "utf-8"
    )
    assert helper._canonical_sha256(evidence) == CANONICAL_SHA256
    assert evidence == helper._evidence(*_common(values))
    certificate = _structure(values)
    assert certificate["status"] == "structurally_verified"
    assert certificate["evidence_sha256"] == CANONICAL_SHA256
    scan = evidence["whole_atlas_reference_scan"]
    assert [
        (row["instruction_rva"], row["owner_entry_rva"]) for row in scan["references"]
    ] == [
        ("0x003788ca", "0x00378840"),
        ("0x003789c7", "0x00378965"),
        ("0x00378aae", "0x00378a40"),
        ("0x00378b5d", "0x00378b55"),
    ]
    assert (
        evidence["predecessor_parent_edges"][0]["instruction"]["rva"]
        == scan["references"][-1]["instruction_rva"]
    )


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("analysis_kind",), "changed"),
        (("build_identity", "executable_sha256"), "0" * 64),
        (("function_body", "body_sha256"), "0" * 64),
        (
            ("function_body", "target_pe_backing", "section_raw_offset"),
            "0x00000000",
        ),
        (
            (
                "function_body",
                "adjacent_atlas_boundaries",
                "left_neighbor",
                "body_sha256",
            ),
            "0" * 64,
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
        (("native_calls", "pe_address_operands", 0, "file_offset"), "0x00000000"),
        (
            (
                "native_calls",
                "pe_address_operands",
                0,
                "opaque_file_bytes_sha256",
            ),
            "0" * 64,
        ),
        (
            ("whole_atlas_reference_scan", "references", 0, "owner_entry_rva"),
            "0x00000000",
        ),
        (
            ("whole_atlas_reference_scan", "partition_sha256", "owner_partition"),
            "0" * 64,
        ),
        (("method", "structural_boundary"), "changed"),
        (("summary", "sealed_adjacent_boundary_count"), 1),
        (("summary", "sealed_target_pe_backing_count"), 0),
        (("summary", "target_reference_count"), 3),
    ],
)
def test_structure_fails_closed_on_retained_mutations(values, path, replacement):
    with pytest.raises(Error):
        _structure(values, _replace(values["evidence"], path, replacement))


def test_structure_rejects_unknown_and_malformed(values):
    bad = copy.deepcopy(values["evidence"])
    bad["unexpected"] = True
    with pytest.raises(Error):
        _structure(values, bad)
    with pytest.raises(Error):
        helper.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary_structure(
            [], values["parent"], values["direct"], values["facts"]
        )
    with pytest.raises(Error):
        helper.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary_structure(
            values["evidence"], [], values["direct"], values["facts"]
        )
    with pytest.raises(Error):
        helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary(
            []
        )
    with pytest.raises(Error):
        helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary(
            {"x": float("nan")}
        )


def _cli_structure_args(values, evidence=None):
    paths = values["paths"]
    return [
        "verify-structure",
        "--adjacent-callee-cluster-static-boundary",
        str(paths["parent"]),
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
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary(
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
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary(
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
    (cli.NativeLuaDirectCallError, cli.NativeLuaCClosurePublicationError),
)
def test_cli_writer_normalizes_upstream_domain_errors(
    values, tmp_path, monkeypatch, upstream_error
):
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary(
        values["evidence"]
    )

    def fail(*_args):
        raise upstream_error("upstream")

    monkeypatch.setattr(cli, "_write_immutably_impl", fail)
    with pytest.raises(Error, match="upstream"):
        cli._write_immutably(tmp_path / "evidence.json", rendered, values["evidence"])


def test_exact_rebuild_validate_and_nonvacuous_scan_mutations(values, monkeypatch):
    executable = _exact_executable()
    data, image, digest = helper._load_executable(executable)
    assert digest == EXE_SHA256
    rebuilt = helper.build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary(
        executable,
        *_common(values),
        inventory=values["inventory"],
    )
    assert rebuilt == values["evidence"]
    certificate = helper.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary(
        executable,
        rebuilt,
        *_common(values),
        inventory=values["inventory"],
    )
    assert certificate["status"] == "verified"
    assert certificate["evidence_sha256"] == CANONICAL_SHA256

    original = helper._decode_range
    import capstone

    for injected in ("b8158a7700", "a1158a7700"):

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


def test_exact_pe_backing_and_opaque_data_bytes_reject_mutations(values):
    executable = _exact_executable()
    data, image, _digest = helper._load_executable(executable)
    assert helper._target_pe_backing(image)["file_offset"] == "0x00377e15"
    assert (
        helper._native_calls(values["facts"], image)["pe_address_operands"][0][
            "file_offset"
        ]
        == "0x00492210"
    )

    changed = bytearray(data)
    changed[image.rva_span_to_file_offset(0x378A15, 31)] ^= 0x01
    with pytest.raises(Error, match="target PE bytes"):
        helper._target_pe_backing(type(image)(bytes(changed)))

    changed = bytearray(data)
    changed[image.rva_span_to_file_offset(0x494010, 4)] ^= 0x01
    with pytest.raises(Error, match="opaque PE immediate bytes"):
        helper._native_calls(values["facts"], type(image)(bytes(changed)))
