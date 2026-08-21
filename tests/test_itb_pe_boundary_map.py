"""Focused tests for reviewed, build-keyed PE boundary evidence."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

import capstone
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import itb_pe_boundary_map  # noqa: E402

from src.observatory.pe_anchor_map import (  # noqa: E402
    PEImage,
    _inventory_identity,
)
from src.observatory.pe_boundary_map import (  # noqa: E402
    PEBoundaryError,
    validate_pe_boundary_map,
)
from tests.test_itb_pe_anchor_map import (  # noqa: E402
    _inventory,
    _synthetic_pe,
)


def _boundary_pe() -> bytes:
    data = bytearray(_synthetic_pe())
    source_file_offset = 0x220
    source_rva = 0x1020
    target_rva = 0x1050
    data[source_file_offset] = 0xE8
    struct.pack_into(
        "<i",
        data,
        source_file_offset + 1,
        target_rva - (source_rva + 5),
    )
    data[source_file_offset + 5 : source_file_offset + 11] = (
        b"\xff\x15" + struct.pack("<I", 0x401300)
    )
    data[0x250] = 0xC3
    return bytes(data)


def _region(
    data: bytes,
    region_id: str,
    start: int,
    end: int,
) -> dict:
    image = PEImage(data)
    offset = image.rva_span_to_file_offset(start, end - start)
    assert offset is not None
    body = data[offset : offset + end - start]
    return {
        "id": region_id,
        "evidence_class": "fact",
        "start_rva": f"0x{start:08x}",
        "end_rva_exclusive": f"0x{end:08x}",
        "size": end - start,
        "sha256": hashlib.sha256(body).hexdigest(),
        "section": ".text",
        "boundary_basis": "synthetic decoded function extent",
    }


def _evidence(data: bytes) -> dict:
    inventory = _inventory(data)
    identity = _inventory_identity(
        inventory,
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
        architecture="x86",
    )
    return {
        "schema_version": 1,
        "analysis_kind": "pe_reviewed_boundary_map",
        "identity": identity,
        "pe": {"bits": 32, "image_base": "0x00400000"},
        "method": {
            "tools": [
                {
                    "name": "synthetic decoder",
                    "version": "1",
                    "role": "test direct calls",
                }
            ],
            "procedure": ["Decode selected call sites and hash their regions."],
            "limitations": ["Synthetic evidence does not describe game behavior."],
        },
        "regions": [
            _region(data, "source", 0x1020, 0x102B),
            _region(data, "target", 0x1050, 0x1051),
        ],
        "direct_call_edges": [
            {
                "id": "source_to_target",
                "evidence_class": "fact",
                "source_region": "source",
                "from_rva": "0x00001020",
                "kind": "direct_rel32",
                "target": {
                    "type": "region",
                    "region": "target",
                    "rva": "0x00001050",
                },
                "meaning": "Synthetic direct call.",
            },
            {
                "id": "source_to_lua_pushcclosure",
                "evidence_class": "fact",
                "source_region": "source",
                "from_rva": "0x00001025",
                "kind": "iat_indirect",
                "target": {
                    "type": "import",
                    "library": "lua5.1.dll",
                    "name": "lua_pushcclosure",
                    "iat_rva": "0x00001300",
                },
                "meaning": "Synthetic IAT call.",
            },
        ],
        "findings": [
            {
                "id": "synthetic_finding",
                "evidence_class": "fact",
                "regions": ["source", "target"],
                "claim": "The selected synthetic call edge is decoded.",
                "implications": ["The verifier can pin rel32 calls."],
                "limitations": ["No runtime behavior is claimed."],
            }
        ],
        "hook_boundaries": [
            {
                "id": "synthetic_hook",
                "evidence_class": "inference",
                "status": "partial_static_boundary",
                "boundary": "Synthetic source function",
                "regions": ["source"],
                "captures": ["Synthetic calls"],
                "misses": [],
                "runtime_proof_required": ["Behavior-neutral detour trial"],
            }
        ],
        "unresolved": [
            {
                "id": "synthetic_runtime",
                "question": "Does a synthetic detour preserve behavior?",
                "static_status": "Static evidence cannot answer this.",
                "next_evidence": "Matched runtime trials.",
            }
        ],
        "summary": {
            "region_count": 2,
            "direct_call_edge_count": 2,
            "finding_count": 1,
            "hook_boundary_count": 1,
            "unresolved_count": 1,
        },
    }


def test_validates_region_hashes_rel32_and_iat_calls(tmp_path: Path):
    executable = tmp_path / "Breach.exe"
    data = _boundary_pe()
    executable.write_bytes(data)

    result = validate_pe_boundary_map(
        executable,
        _evidence(data),
        inventory=_inventory(data),
    )

    assert result["status"] == "verified"
    assert result["identity"]["executable_sha256"] == hashlib.sha256(
        data
    ).hexdigest()
    assert result["summary"] == {
        "region_count": 2,
        "direct_call_edge_count": 2,
        "finding_count": 1,
        "hook_boundary_count": 1,
        "unresolved_count": 1,
    }


def test_region_hash_and_call_edges_fail_closed(tmp_path: Path):
    executable = tmp_path / "Breach.exe"
    data = _boundary_pe()
    executable.write_bytes(data)

    bad_hash = _evidence(data)
    bad_hash["regions"][0]["sha256"] = "0" * 64
    with pytest.raises(PEBoundaryError, match="SHA-256 mismatch"):
        validate_pe_boundary_map(
            executable,
            bad_hash,
            inventory=_inventory(data),
        )

    bad_rel32 = _evidence(data)
    bad_rel32["direct_call_edges"][0]["from_rva"] = "0x00001021"
    with pytest.raises(PEBoundaryError, match="instruction boundary"):
        validate_pe_boundary_map(
            executable,
            bad_rel32,
            inventory=_inventory(data),
        )

    bad_import = _evidence(data)
    bad_import["direct_call_edges"][1]["target"]["name"] = "lua_setfield"
    with pytest.raises(PEBoundaryError, match="not the named PE import"):
        validate_pe_boundary_map(
            executable,
            bad_import,
            inventory=_inventory(data),
        )


def test_embedded_call_opcodes_are_not_instruction_boundaries(tmp_path: Path):
    executable = tmp_path / "Breach.exe"

    rel32_bytes = bytearray(_boundary_pe())
    rel32_bytes[0x260:0x267] = b"\xb8\xe8\xff\xff\xff\xff\xc3"
    rel32_data = bytes(rel32_bytes)
    executable.write_bytes(rel32_data)
    embedded_rel32 = _evidence(rel32_data)
    embedded_rel32["regions"].append(
        _region(rel32_data, "embedded_rel32", 0x1060, 0x1067)
    )
    embedded_rel32["direct_call_edges"].append(
        {
            "id": "embedded_rel32_false_edge",
            "evidence_class": "fact",
            "source_region": "embedded_rel32",
            "from_rva": "0x00001061",
            "kind": "direct_rel32",
            "target": {
                "type": "region",
                "region": "embedded_rel32",
                "rva": "0x00001065",
            },
            "meaning": "Opcode-looking bytes embedded in MOV EAX, imm32.",
        }
    )
    embedded_rel32["summary"]["region_count"] += 1
    embedded_rel32["summary"]["direct_call_edge_count"] += 1
    with pytest.raises(PEBoundaryError, match="instruction boundary"):
        validate_pe_boundary_map(
            executable,
            embedded_rel32,
            inventory=_inventory(rel32_data),
        )

    iat_bytes = bytearray(_boundary_pe())
    iat_bytes[0x270:0x278] = b"\xb8\xff\x15\x00\x13\x40\x00\xc3"
    iat_data = bytes(iat_bytes)
    executable.write_bytes(iat_data)
    embedded_iat = _evidence(iat_data)
    embedded_iat["regions"].append(
        _region(iat_data, "embedded_iat", 0x1070, 0x1078)
    )
    embedded_iat["direct_call_edges"].append(
        {
            "id": "embedded_iat_false_edge",
            "evidence_class": "fact",
            "source_region": "embedded_iat",
            "from_rva": "0x00001071",
            "kind": "iat_indirect",
            "target": {
                "type": "import",
                "library": "lua5.1.dll",
                "name": "lua_pushcclosure",
                "iat_rva": "0x00001300",
            },
            "meaning": "Opcode-looking bytes embedded in MOV EAX, imm32.",
        }
    )
    embedded_iat["summary"]["region_count"] += 1
    embedded_iat["summary"]["direct_call_edge_count"] += 1
    with pytest.raises(PEBoundaryError, match="instruction boundary"):
        validate_pe_boundary_map(
            executable,
            embedded_iat,
            inventory=_inventory(iat_data),
        )


def test_unreviewed_capstone_version_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    executable = tmp_path / "Breach.exe"
    data = _boundary_pe()
    executable.write_bytes(data)
    monkeypatch.setattr(capstone, "__version__", "5.0.8")

    with pytest.raises(PEBoundaryError, match="unsupported Capstone version"):
        validate_pe_boundary_map(
            executable,
            _evidence(data),
            inventory=_inventory(data),
        )


def test_identity_schema_references_and_summary_are_strict(tmp_path: Path):
    executable = tmp_path / "Breach.exe"
    data = _boundary_pe()
    executable.write_bytes(data)

    wrong_identity = _evidence(data)
    wrong_identity["identity"]["build_id"] = "different"
    with pytest.raises(PEBoundaryError, match="identity"):
        validate_pe_boundary_map(
            executable,
            wrong_identity,
            inventory=_inventory(data),
        )

    unknown_region = _evidence(data)
    unknown_region["findings"][0]["regions"] = ["missing"]
    with pytest.raises(PEBoundaryError, match="unknown region"):
        validate_pe_boundary_map(
            executable,
            unknown_region,
            inventory=_inventory(data),
        )

    bad_summary = _evidence(data)
    bad_summary["summary"]["finding_count"] = 2
    with pytest.raises(PEBoundaryError, match="summary counts"):
        validate_pe_boundary_map(
            executable,
            bad_summary,
            inventory=_inventory(data),
        )

    unknown_field = _evidence(data)
    unknown_field["surprise"] = True
    with pytest.raises(PEBoundaryError, match="fields differ"):
        validate_pe_boundary_map(
            executable,
            unknown_field,
            inventory=_inventory(data),
        )


def test_cli_emits_only_verified_summary(tmp_path: Path, capsys):
    executable = tmp_path / "Breach.exe"
    inventory = tmp_path / "inventory.json"
    evidence = tmp_path / "boundaries.json"
    data = _boundary_pe()
    executable.write_bytes(data)
    inventory.write_text(json.dumps(_inventory(data)), encoding="utf-8")
    evidence.write_text(json.dumps(_evidence(data)), encoding="utf-8")

    assert (
        itb_pe_boundary_map.main(
            [
                "--executable",
                str(executable),
                "--inventory",
                str(inventory),
                "--evidence",
                str(evidence),
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "verified"
    assert "regions" not in result
    assert "findings" not in result


def test_cli_rejects_nonstandard_json(tmp_path: Path, capsys):
    executable = tmp_path / "Breach.exe"
    inventory = tmp_path / "inventory.json"
    evidence = tmp_path / "boundaries.json"
    data = _boundary_pe()
    executable.write_bytes(data)
    inventory.write_text(json.dumps(_inventory(data)), encoding="utf-8")
    evidence.write_text('{"schema_version": NaN}', encoding="utf-8")

    assert (
        itb_pe_boundary_map.main(
            [
                "--executable",
                str(executable),
                "--inventory",
                str(inventory),
                "--evidence",
                str(evidence),
            ]
        )
        == 2
    )
    assert "invalid JSON constant" in capsys.readouterr().err
