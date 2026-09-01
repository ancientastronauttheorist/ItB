"""Focused checks for the opaque three-byte ``CALL EAX; RET`` child."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts import (
    itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary as cli,
)
from src.observatory import (
    native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary as helper,
)

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "windows_build_13725832_31fe35265598_"
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
RAW_SHA256 = "61e0571607dd92e2861f06297a410c9766135c718b0420afbf3d7351d160b570"
CANONICAL_SHA256 = "71f87f861758ba8ef7f7d9a6ac435bb05df38d81e7ff5c8e7fe8c95a4fb0e193"
Error = (
    helper.NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeChildStaticBoundaryError
)


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values():
    names = {
        "fourth": "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary.json",
        "second": "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary.json",
        "direct": "native_lua_direct_call_census.json",
        "facts": "program_facts.json",
        "evidence": "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary.json",
    }
    paths = {key: PROGRAMS / (PREFIX + value) for key, value in names.items()}
    paths["inventory"] = INVENTORIES / (
        PREFIX + "full_decompile_baseline_20260830.json"
    )
    return {**{key: _read(path) for key, path in paths.items()}, "paths": paths}


def _common(values):
    return values["fourth"], values["second"], values["direct"], values["facts"]


def _structure(values, evidence=None):
    return helper.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary_structure(
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


def test_decoder_cfg_and_opaque_control_partition():
    rows = helper._decode()
    assert [row.mnemonic for row in rows] == ["call", "ret"]
    assert b"".join(bytes(row.bytes) for row in rows).hex() == "ffd0c3"
    graph = helper._graph(rows)
    assert (graph["node_count"], graph["edge_count"]) == (2, 1)
    assert helper._canonical_sha256(graph) == helper._CFG

    controls = helper._native_controls(rows)
    assert controls["outgoing_direct"] == []
    assert controls["direct_lua_calls"] == []
    assert controls["staged_lua_dispatches"] == []
    assert controls["pe_address_operands"] == []
    assert controls["non_pe_immediate_literals"] == []
    assert controls["segment_qualified_memory_syntax"] == []
    assert controls["explicit_ret_immediates"] == []
    assert controls["opaque_indirect_controls"] == [
        {
            "instruction": helper._instruction(0x378A34, "ffd0"),
            "control_kind": "x86_call_r32",
            "register": "eax",
            "static_target_proved": False,
            "target_and_runtime_effect_opaque": True,
        }
    ]
    assert controls["decoded_access"]["call_instruction"]["registers_read"] == [
        "eax",
        "esp",
    ]
    assert (
        controls["decoded_access"]["return_instruction"]["explicit_operand_count"] == 0
    )
    assert next(
        row for row in controls["call_r32_audit"] if row["register"].lower() == "eax"
    )["call_rvas"] == ["0x00378a34"]


def test_committed_artifact_identity_reconstruction_and_rejoins(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary(
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
    scan = evidence["whole_atlas_reference_scan"]
    assert [
        (row["instruction_rva"], row["owner_entry_rva"]) for row in scan["references"]
    ] == [
        ("0x003789d0", "0x00378965"),
        ("0x00378abb", "0x00378a40"),
    ]
    assert scan["partition_sha256"] == helper._PARTITION_HASHES
    assert scan["references_canonical_sha256"] == helper._REFERENCE_HASH

    slices = evidence["caller_provenance_slices"]
    assert [row["loader_instruction"]["rva"] for row in slices] == [
        "0x003789cc",
        "0x00378ab8",
    ]
    assert [row["loader_memory_expression"] for row in slices] == [
        {
            "segment_register": None,
            "base_register": "ebx",
            "index_register": "esi",
            "scale": 4,
            "displacement": 8,
        },
        {
            "segment_register": None,
            "base_register": "ebx",
            "index_register": None,
            "scale": 1,
            "displacement": 8,
        },
    ]
    assert all(row["loader_is_unique_cfg_predecessor"] for row in slices)
    assert all(row["eax_reloaded_after_prior_call"] for row in slices)
    assert all(row["static_target_proved"] is False for row in slices)
    rejoins = evidence["dependent_receipt_rejoins"]
    assert rejoins["fourth_callee_left_neighbor_matches_child"] is True
    assert rejoins["second_callee_right_neighbor_matches_child"] is True
    assert [
        row["instruction_rva"] for row in rejoins["second_callee_prior_call_rejoins"]
    ] == ["0x003789c7", "0x00378aae"]
    assert evidence["summary"]["static_indirect_target_count"] == 0


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("analysis_kind",), "changed"),
        (("build_identity", "executable_sha256"), "0" * 64),
        (("program_facts", "canonical_sha256"), "0" * 64),
        (("fourth_callee_static_boundary", "canonical_sha256"), "0" * 64),
        (("second_callee_static_boundary", "canonical_sha256"), "0" * 64),
        (("function_body", "body_sha256"), "0" * 64),
        (("function_body", "target_pe_backing", "file_offset"), "0x00000000"),
        (
            (
                "function_body",
                "adjacent_atlas_boundaries",
                "right_un_atlased_gap",
                "bytes_sha256",
            ),
            "0" * 64,
        ),
        (
            (
                "function_body",
                "adjacent_atlas_boundaries",
                "left_neighbor",
                "entry_rva",
            ),
            "0x00000000",
        ),
        (("control_flow_graph", "nodes", 0, "flow_kind"), "changed"),
        (
            ("native_controls", "opaque_indirect_controls", 0, "register"),
            "ecx",
        ),
        (
            (
                "native_controls",
                "decoded_access",
                "call_instruction",
                "registers_read",
            ),
            ["eax"],
        ),
        (
            (
                "caller_provenance_slices",
                0,
                "caller_control_flow_graph",
                "canonical_sha256",
            ),
            "0" * 64,
        ),
        (
            ("caller_provenance_slices", 0, "loader_memory_expression", "scale"),
            1,
        ),
        (
            ("caller_provenance_slices", 1, "loader_call_window", "sha256"),
            "0" * 64,
        ),
        (("caller_provenance_slices", 1, "static_target_proved"), True),
        (
            ("whole_atlas_reference_scan", "references", 0, "owner_entry_rva"),
            "0x00000000",
        ),
        (
            (
                "whole_atlas_reference_scan",
                "partition_sha256",
                "owner_partition",
            ),
            "0" * 64,
        ),
        (
            (
                "dependent_receipt_rejoins",
                "fourth_callee_declared_edge",
                "target_entry_rva",
            ),
            "0x00000000",
        ),
        (("method", "structural_boundary"), "changed"),
        (("summary", "static_indirect_target_count"), 1),
    ],
)
def test_structure_fails_closed_on_retained_mutations(values, path, replacement):
    with pytest.raises(Error):
        _structure(values, _replace(values["evidence"], path, replacement))


@pytest.mark.parametrize("raw", ("ffd1c3", "ffe0c3"))
def test_register_or_control_kind_mutation_fails_closed(raw):
    with pytest.raises(Error, match="raw bytes differ"):
        helper._decode(bytes.fromhex(raw))


def test_prerequisite_mutations_fail_closed(values):
    fourth = copy.deepcopy(values["fourth"])
    fourth["method"]["structural_boundary"] = "changed"
    with pytest.raises(Error, match="fourth-callee receipt"):
        helper._evidence(fourth, values["second"], values["direct"], values["facts"])

    second = copy.deepcopy(values["second"])
    second["method"]["structural_boundary"] = "changed"
    with pytest.raises(Error, match="second-callee receipt"):
        helper._evidence(values["fourth"], second, values["direct"], values["facts"])


def test_public_apis_reject_non_object_or_non_json_roots(values):
    with pytest.raises(Error):
        _structure(values, [])
    for index in range(4):
        common = list(_common(values))
        common[index] = []
        with pytest.raises(Error):
            helper.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary_structure(
                values["evidence"], *common
            )
    with pytest.raises(Error):
        helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary(
            []
        )
    with pytest.raises(Error):
        helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary(
            {"x": float("nan")}
        )


def _cli_structure_args(values, evidence=None):
    paths = values["paths"]
    return [
        "verify-structure",
        "--fourth-callee-static-boundary",
        str(paths["fourth"]),
        "--second-callee-static-boundary",
        str(paths["second"]),
        "--direct-calls",
        str(paths["direct"]),
        "--program-facts",
        str(paths["facts"]),
        "--evidence",
        str(paths["evidence"] if evidence is None else evidence),
    ]


def test_cli_parser_structure_and_read_error(values, tmp_path, capsys):
    common = [
        "--fourth-callee-static-boundary",
        "f.json",
        "--second-callee-static-boundary",
        "s.json",
        "--direct-calls",
        "d.json",
        "--program-facts",
        "p.json",
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
    assert parsed.fourth_callee_static_boundary == Path("f.json")

    assert cli.main(_cli_structure_args(values)) == 0
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["status"] == "structurally_verified"
    assert certificate["evidence_sha256"] == CANONICAL_SHA256

    arguments = _cli_structure_args(values)
    arguments[arguments.index("--fourth-callee-static-boundary") + 1] = str(
        tmp_path / "missing.json"
    )
    assert cli.main(arguments) == 1
    assert "error:" in capsys.readouterr().err


def test_cli_rejects_nondeterministic_evidence(values, tmp_path, capsys):
    compact = tmp_path / "compact.json"
    compact.write_text(json.dumps(values["evidence"]), encoding="utf-8")
    assert cli.main(_cli_structure_args(values, compact)) == 1
    assert "not deterministically encoded" in capsys.readouterr().err


def _patch_output_root(monkeypatch, temporary):
    before = temporary.stat()
    monkeypatch.setattr(
        cli, "_prepare_output_root", lambda: (temporary, temporary, before)
    )
    monkeypatch.setattr(cli, "_recheck_output_root", lambda *_args: None)


def test_cli_writer_is_immutable_and_preserves_differing_output(
    values, tmp_path, monkeypatch
):
    _patch_output_root(monkeypatch, tmp_path)
    value = values["evidence"]
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary(
        value
    )
    output = tmp_path / "evidence.json"
    cli._write_immutably(output, rendered, value)
    cli._write_immutably(output, rendered, value)
    output.write_bytes(rendered.encode("utf-8") + b" ")
    with pytest.raises(Error, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, value)
    assert output.read_bytes() == rendered.encode("utf-8") + b" "

    with pytest.raises(Error, match="direct child"):
        cli._write_immutably(tmp_path / "nested" / "evidence.json", rendered, value)
    with pytest.raises(Error, match="direct child"):
        cli._write_immutably(
            tmp_path.parent / (tmp_path.name + "-outside.json"), rendered, value
        )


def test_cli_writer_final_validation_cleans_failed_publication(
    values, tmp_path, monkeypatch
):
    _patch_output_root(monkeypatch, tmp_path)
    value = values["evidence"]
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary(
        value
    )
    output = tmp_path / "evidence.json"
    original = cli._read_locked_json_document

    def corrupt(descriptor, label):
        parsed, payload = original(descriptor, label)
        return parsed, payload + b" "

    monkeypatch.setattr(cli, "_read_locked_json_document", corrupt)
    with pytest.raises(Error, match="final content validation"):
        cli._write_immutably(output, rendered, value)
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
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary(
        values["evidence"]
    )

    def fail(*_args):
        raise upstream_error("upstream")

    monkeypatch.setattr(cli, "_write_immutably_impl", fail)
    with pytest.raises(Error, match="upstream"):
        cli._write_immutably(tmp_path / "evidence.json", rendered, values["evidence"])


def test_exact_rebuild_and_validate(values):
    executable = _exact_executable()
    rebuilt = helper.build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary(
        executable,
        *_common(values),
        inventory=values["inventory"],
    )
    assert rebuilt == values["evidence"]
    certificate = helper.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary(
        executable,
        rebuilt,
        *_common(values),
        inventory=values["inventory"],
    )
    assert certificate["status"] == "verified"
    assert certificate["evidence_sha256"] == CANONICAL_SHA256


def test_exact_whole_atlas_immediate_and_memory_injection_seams(values, monkeypatch):
    executable = _exact_executable()
    data, image, digest = helper._load_executable(executable)
    assert digest == EXE_SHA256
    original = helper._decode_range
    import capstone

    for injected in ("b8348a7700", "a1348a7700"):

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
        decoder, _version = helper._decoder()
        with pytest.raises(Error, match="all-operand"):
            helper._whole_atlas_reference_scan(data, image, decoder, values["facts"])
        monkeypatch.setattr(helper, "_decode_range", original)


def test_exact_pe_gap_neighbor_control_and_caller_mutation_seams(values):
    executable = _exact_executable()
    data, image, digest = helper._load_executable(executable)
    assert digest == EXE_SHA256
    assert helper._target_pe_backing(image)["file_offset"] == "0x00377e34"
    assert (
        helper._boundaries(values["facts"], image)["right_un_atlased_gap"]["size"] == 9
    )

    changed = bytearray(data)
    changed[image.rva_span_to_file_offset(0x378A34, 3)] ^= 0x01
    with pytest.raises(Error, match="child PE backing"):
        helper._target_pe_backing(type(image)(bytes(changed)))

    changed = bytearray(data)
    changed[image.rva_span_to_file_offset(0x378A3F, 1)] ^= 0x01
    with pytest.raises(Error, match="right gap backing"):
        helper._boundaries(values["facts"], type(image)(bytes(changed)))

    for neighbor in (0x378A15, 0x378A40):
        changed = bytearray(data)
        changed[image.rva_span_to_file_offset(neighbor, 1)] ^= 0x01
        with pytest.raises(Error, match="neighbor PE backing"):
            helper._boundaries(values["facts"], type(image)(bytes(changed)))

    import capstone

    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    disassembler.detail = True
    for raw in ("ffd1c3", "ffe0c3"):
        rows = list(disassembler.disasm(bytes.fromhex(raw), 0x778A34))
        with pytest.raises(Error, match="CALL EAX or RET"):
            helper._native_controls(rows)

    decoder, _version = helper._decoder()
    for rva, delta in (
        (0x3789CD, 0x08),
        (0x3789CF, 0x04),
        (0x378AB9, 0x08),
        (0x378ABA, 0x04),
        (0x3789D4, 0x01),
        (0x378ABF, 0x01),
    ):
        changed = bytearray(data)
        changed[image.rva_span_to_file_offset(rva, 1)] ^= delta
        changed_image = type(image)(bytes(changed))
        with pytest.raises(Error):
            helper._caller_provenance(
                values["facts"], changed_image, bytes(changed), decoder
            )
