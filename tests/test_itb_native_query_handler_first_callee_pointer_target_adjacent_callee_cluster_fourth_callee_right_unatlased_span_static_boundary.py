"""Focused tests for the sealed 0x00378ad0 un-atlased-span receipt."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts import (
    itb_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary as cli,
)
from src.observatory import (
    native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary as helper,
)

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "windows_build_13725832_31fe35265598_"
PROGRAMS = ROOT / "data" / "observatory" / "programs"
INVENTORIES = ROOT / "data" / "observatory" / "inventories"
EXE_SHA256 = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
RAW_SHA256 = "43db988b412d01cfbe06adfb258e2dfb2a3dbba98bfcf8a65e4092165a86eec1"
CANONICAL_SHA256 = "02a4e933250820874a6b8876e8092636747f780bde25f28103b4585651dc0359"
Error = (
    helper.NativeQueryHandlerFirstCalleePointerTargetAdjacentCalleeClusterFourthCalleeRightUnatlasedSpanStaticBoundaryError
)


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def values():
    names = {
        "fourth": "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary.json",
        "child": "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary.json",
        "residual": "native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json",
        "residual_callee": "native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.json",
        "direct": "native_lua_direct_call_census.json",
        "facts": "program_facts.json",
        "evidence": "native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary.json",
    }
    paths = {key: PROGRAMS / (PREFIX + value) for key, value in names.items()}
    paths["inventory"] = INVENTORIES / (
        PREFIX + "full_decompile_baseline_20260830.json"
    )
    if not paths["evidence"].is_file():
        pytest.skip("un-atlased-span evidence artifact has not been committed yet")
    return {**{key: _read(path) for key, path in paths.items()}, "paths": paths}


def _common(values):
    return (
        values["fourth"],
        values["child"],
        values["residual"],
        values["residual_callee"],
        values["direct"],
        values["facts"],
    )


def _structure(values, evidence=None):
    return helper.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary_structure(
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


def test_raw_decode_components_cfg_operand_and_call_facts():
    rows = helper._decode()
    assert len(rows) == 34
    assert b"".join(bytes(row.bytes) for row in rows).hex() == helper._RAW
    components, union = helper._graphs(rows)
    assert [(row["role"], row["size"]) for row in components] == [
        ("component_a", 70),
        ("component_b", 40),
    ]
    assert [
        (
            row["control_flow_graph"]["node_count"],
            row["control_flow_graph"]["edge_count"],
        )
        for row in components
    ] == [(21, 21), (13, 12)]
    assert union["canonical_sha256"] == helper._UNION_CFG
    assert (union["node_count"], union["edge_count"]) == (34, 33)
    operands = helper._operand_frontier(rows)
    assert [
        (row["instruction"]["rva"], row["instruction"]["sha256"], row["immediate"])
        for row in operands["explicit_ret_immediates"]
    ] == [("0x00378b3b", helper._instruction(0x378B3B, "c20400")["sha256"], 4)]
    assert operands["internal_direct_branch_syntax"] == [
        {
            "instruction": helper._instruction(0x378AE0, "7433"),
            "target_rva": "0x00378b15",
            "internal_span_target": True,
        }
    ]


def test_sealed_decode_mutation_seams_fail_closed():
    raw = bytearray(bytes.fromhex(helper._RAW))
    for offset in (0, 69, 70, 109):
        changed = bytearray(raw)
        changed[offset] ^= 1
        with pytest.raises(Error):
            helper._decode(bytes(changed))


def test_committed_artifact_identity_reconstruction_and_rejoins(values):
    evidence = values["evidence"]
    raw = values["paths"]["evidence"].read_bytes()
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary(
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
    assert evidence["span"]["role"] == "code_candidate_components"
    assert evidence["span"]["atlas_owned"] is False
    assert (
        evidence["whole_atlas_reference_scan"]["references"][0]["instruction_rva"]
        == "0x00378a54"
    )
    assert (
        evidence["whole_file_and_relocations"]["base_relocation_scan"]["references"][0][
            "entry_raw"
        ]
        == "553a"
    )
    assert (
        evidence["dependent_receipt_rejoins"]["fourth_right_un_atlased_gap"]["rejoined"]
        is True
    )
    assert (
        evidence["dependent_receipt_rejoins"]["child_right_neighbor"]["rejoined"]
        is True
    )
    assert (
        evidence["dependent_receipt_rejoins"]["outgoing_target_receipt_rejoin_count"]
        == 3
    )
    assert evidence["summary"]["outgoing_direct_e8_count"] == 4


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("analysis_kind",), "changed"),
        (("build_identity", "executable_sha256"), "0" * 64),
        (("program_facts", "canonical_sha256"), "0" * 64),
        (("fourth_callee_static_boundary", "canonical_sha256"), "0" * 64),
        (("fourth_callee_child_static_boundary", "canonical_sha256"), "0" * 64),
        (("residual_direct_target_set_static_boundary", "canonical_sha256"), "0" * 64),
        (
            ("residual_direct_target_set_callee_static_boundary", "canonical_sha256"),
            "0" * 64,
        ),
        (("span", "raw_bytes_sha256"), "0" * 64),
        (("span", "geometry", "left_neighbor", "entry_rva"), "0x00000000"),
        (("span", "code_candidate_components", 0, "body_sha256"), "0" * 64),
        (
            (
                "span",
                "code_candidate_components",
                1,
                "control_flow_graph",
                "nodes",
                0,
                "flow_kind",
            ),
            "changed",
        ),
        (("span", "union_control_flow_graph", "canonical_sha256"), "0" * 64),
        (("native_controls", "outgoing_direct", 0, "target_entry_rva"), "0x00000000"),
        (("operand_frontier", "explicit_ret_immediates", 0, "immediate"), 0),
        (
            ("operand_frontier", "internal_direct_branch_syntax", 0, "target_rva"),
            "0x00000000",
        ),
        (("whole_atlas_reference_scan", "references", 0, "target_rva"), "0x00378b16"),
        (("whole_file_and_relocations", "whole_file_dword_scan", "reference_count"), 0),
        (
            (
                "whole_file_and_relocations",
                "base_relocation_scan",
                "references",
                0,
                "type",
            ),
            "ABSOLUTE",
        ),
        (
            (
                "dependent_receipt_rejoins",
                "fourth_endpoint_reference_scan",
                "references_canonical_sha256",
            ),
            "0" * 64,
        ),
        (("method", "relationship_only"), False),
        (("summary", "code_candidate_component_count"), 1),
    ],
)
def test_structure_fails_closed_on_retained_mutations(values, path, replacement):
    with pytest.raises(Error):
        _structure(values, _replace(values["evidence"], path, replacement))


def test_prerequisite_mutations_fail_closed(values):
    for key in ("fourth", "child", "residual", "residual_callee"):
        changed = copy.deepcopy(values[key])
        changed["analysis_kind"] = "changed"
        supplied = dict(values)
        supplied[key] = changed
        with pytest.raises(Error):
            helper._evidence(*_common(supplied))


def test_counterfeit_atlas_range_and_declared_edge_fail_closed(values):
    range_facts = dict(values["facts"])
    functions = list(range_facts["functions"])
    index = next(
        i for i, row in enumerate(functions) if row.get("entry_rva") == "0x00378b6e"
    )
    owner = dict(functions[index])
    owner["ranges"] = [
        *owner["ranges"],
        {"start_rva": "0x00378ad0", "size": 1},
    ]
    functions[index] = owner
    range_facts["functions"] = functions
    with pytest.raises(Error, match="overlaps"):
        helper._geometry(range_facts)

    edge_facts = dict(values["facts"])
    edges = list(edge_facts["ghidra_declared_direct_calls"])
    edge = dict(edges[0])
    edge["source_entry_rva"] = "0x00378ad0"
    edges.append(edge)
    edge_facts["ghidra_declared_direct_calls"] = edges
    with pytest.raises(Error, match="declared direct edge"):
        helper._declared_edges(edge_facts)


def test_public_apis_reject_non_object_or_non_json_roots(values):
    with pytest.raises(Error):
        _structure(values, [])
    for index in range(6):
        common = list(_common(values))
        common[index] = []
        with pytest.raises(Error):
            helper.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary_structure(
                values["evidence"], *common
            )
    with pytest.raises(Error):
        helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary(
            []
        )
    with pytest.raises(Error):
        helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary(
            {"x": float("nan")}
        )


def _cli_structure_args(values, evidence=None):
    paths = values["paths"]
    args = ["verify-structure"]
    for key, flag in (
        ("fourth", "fourth-callee-static-boundary"),
        ("child", "fourth-callee-child-static-boundary"),
        ("residual", "residual-direct-target-set-static-boundary"),
        ("residual_callee", "residual-direct-target-set-callee-static-boundary"),
        ("direct", "direct-calls"),
        ("facts", "program-facts"),
    ):
        args.extend(("--" + flag, str(paths[key])))
    return [
        *args,
        "--evidence",
        str(paths["evidence"] if evidence is None else evidence),
    ]


def test_cli_parser_structure_and_read_error(values, tmp_path, capsys):
    common = [
        "--fourth-callee-static-boundary",
        "f.json",
        "--fourth-callee-child-static-boundary",
        "c.json",
        "--residual-direct-target-set-static-boundary",
        "r.json",
        "--residual-direct-target-set-callee-static-boundary",
        "rc.json",
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
    assert parsed.fourth_callee_child_static_boundary == Path("c.json")
    assert cli.main(_cli_structure_args(values)) == 0
    assert json.loads(capsys.readouterr().out)["evidence_sha256"] == CANONICAL_SHA256
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
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary(
        values["evidence"]
    )
    output = tmp_path / "evidence.json"
    cli._write_immutably(output, rendered, values["evidence"])
    cli._write_immutably(output, rendered, values["evidence"])
    output.write_bytes(rendered.encode("utf-8") + b" ")
    with pytest.raises(Error, match="refusing to overwrite"):
        cli._write_immutably(output, rendered, values["evidence"])
    with pytest.raises(Error, match="direct child"):
        cli._write_immutably(
            tmp_path / "nested" / "evidence.json", rendered, values["evidence"]
        )


def test_cli_writer_final_validation_cleans_failed_publication(
    values, tmp_path, monkeypatch
):
    _patch_output_root(monkeypatch, tmp_path)
    rendered = helper.encode_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary(
        values["evidence"]
    )
    output = tmp_path / "evidence.json"
    original = cli._read_locked_json_document

    def corrupt(descriptor, label):
        parsed, payload = original(descriptor, label)
        return parsed, payload + b" "

    monkeypatch.setattr(cli, "_read_locked_json_document", corrupt)
    with pytest.raises(Error, match="final content validation"):
        cli._write_immutably(output, rendered, values["evidence"])
    assert not output.exists()


def test_exact_rebuild_validate_and_pe_mutation_seams(values, monkeypatch):
    executable = _exact_executable()
    rebuilt = helper.build_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary(
        executable, *_common(values), inventory=values["inventory"]
    )
    assert rebuilt == values["evidence"]
    assert (
        helper.validate_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary(
            executable, rebuilt, *_common(values), inventory=values["inventory"]
        )[
            "status"
        ]
        == "verified"
    )
    data, image, digest = helper._load_executable(executable)
    assert digest == EXE_SHA256
    for rva in (
        0x378AD0,
        0x378B15,
        0x378B16,
        0x378B3B,
        0x378AE1,
        0x378AEB,
        0x378AFD,
        0x378B1B,
        0x378B32,
    ):
        changed = bytearray(data)
        changed[image.rva_span_to_file_offset(rva, 1)] ^= 1
        decoder, _ = helper._decoder()
        decoder.detail = True
        with pytest.raises(Error):
            helper._evidence(
                *_common(values),
                data=bytes(changed),
                image=type(image)(bytes(changed)),
                decoder=decoder,
            )


def test_exact_neighbor_pointer_directory_and_relocation_mutations_fail_closed(values):
    executable = _exact_executable()
    data, image, digest = helper._load_executable(executable)
    assert digest == EXE_SHA256

    for rva in (0x378A40, 0x378B3E):
        changed = bytearray(data)
        changed[image.rva_span_to_file_offset(rva, 1)] ^= 1
        with pytest.raises(Error, match="neighbor PE backing"):
            helper._geometry(values["facts"], type(image)(bytes(changed)))

    for file_offset in (0x377E55, 0x48DCA4, 0x532E08):
        changed = bytearray(data)
        changed[file_offset] ^= 1
        with pytest.raises(Error):
            helper._file_and_relocations(type(image)(bytes(changed)))


@pytest.mark.parametrize(
    "raw",
    (
        "b8d08a7700",  # MOV EAX, span start
        "a1e28a7700",  # MOV EAX, [span interior]
        "b8168b7700",  # MOV EAX, component-B start
    ),
)
def test_exact_synthetic_atlas_reference_injections_fail_closed(values, raw):
    executable = _exact_executable()
    data, image, digest = helper._load_executable(executable)
    assert digest == EXE_SHA256
    changed = bytearray(data)
    offset = image.rva_span_to_file_offset(0x378B77, 5)
    changed[offset : offset + 5] = bytes.fromhex(raw)
    mutated = bytes(changed)
    mutated_image = type(image)(mutated)
    decoder, _ = helper._decoder()
    decoder.detail = True
    with pytest.raises(Error, match="whole-atlas span reference scan"):
        helper._atlas_reference_scan(
            mutated,
            mutated_image,
            decoder,
            values["facts"],
        )
