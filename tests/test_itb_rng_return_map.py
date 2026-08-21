"""Focused tests for exact-build native RNG return-address IDs."""

from __future__ import annotations

import copy
import json
import struct
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import itb_rng_return_map  # noqa: E402

from src.observatory.rng_return_map import (  # noqa: E402
    RNGReturnMapError,
    build_rng_return_map,
    validate_rng_return_map,
)
from tests.test_itb_pe_anchor_map import _inventory  # noqa: E402
from tests.test_itb_pe_boundary_map import _boundary_pe, _evidence  # noqa: E402


def _rng_pe() -> bytes:
    data = bytearray(_boundary_pe())
    call_rva = 0x1060
    target_rva = 0x1050
    data[0x260] = 0xE8
    struct.pack_into("<i", data, 0x261, target_rva - (call_rva + 5))
    return bytes(data)


def _rng_boundaries(data: bytes) -> dict:
    evidence = _evidence(data)
    for region in evidence["regions"]:
        if region["id"] == "target":
            region["id"] = "rng_core"
    for edge in evidence["direct_call_edges"]:
        target = edge["target"]
        if target.get("type") == "region" and target.get("region") == "target":
            target["region"] = "rng_core"
    for finding in evidence["findings"]:
        finding["regions"] = [
            "rng_core" if item == "target" else item
            for item in finding["regions"]
        ]
    return evidence


def test_builds_stable_ids_for_reviewed_and_unclassified_raw_calls(tmp_path: Path):
    executable = tmp_path / "Breach.exe"
    data = _rng_pe()
    executable.write_bytes(data)

    result = build_rng_return_map(
        executable,
        _rng_boundaries(data),
        inventory=_inventory(data),
    )

    assert [item["caller_id"] for item in result["callers"]] == [1, 2]
    assert [item["call_rva"] for item in result["callers"]] == [
        "0x00001020",
        "0x00001060",
    ]
    assert result["callers"][0]["classification"]["status"] == (
        "reviewed_direct_call"
    )
    assert result["callers"][1]["classification"]["status"] == (
        "unclassified_raw_candidate"
    )
    assert result["rng_core"]["unknown_caller_id"] == 0


def test_validator_rebuilds_complete_catalog_and_rejects_drift(tmp_path: Path):
    executable = tmp_path / "Breach.exe"
    data = _rng_pe()
    executable.write_bytes(data)
    boundaries = _rng_boundaries(data)
    inventory = _inventory(data)
    catalog = build_rng_return_map(
        executable,
        boundaries,
        inventory=inventory,
    )

    result = validate_rng_return_map(
        executable,
        catalog,
        boundaries,
        inventory=inventory,
    )
    assert result["status"] == "verified"

    for mutation in (
        lambda item: item["callers"][0].update(caller_id=0),
        lambda item: item["callers"].pop(),
        lambda item: item["identity"].update(build_id="wrong"),
    ):
        altered = copy.deepcopy(catalog)
        mutation(altered)
        with pytest.raises(RNGReturnMapError, match="differs"):
            validate_rng_return_map(
                executable,
                altered,
                boundaries,
                inventory=inventory,
            )


def test_boundary_or_executable_identity_drift_fails_before_catalog_use(
    tmp_path: Path,
):
    executable = tmp_path / "Breach.exe"
    data = _rng_pe()
    executable.write_bytes(data)
    boundaries = _rng_boundaries(data)

    boundaries["regions"][0]["sha256"] = "0" * 64
    with pytest.raises(RNGReturnMapError, match="SHA-256 mismatch"):
        build_rng_return_map(
            executable,
            boundaries,
            inventory=_inventory(data),
        )


def test_cli_builds_file_then_verifies_it(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
):
    executable = tmp_path / "Breach.exe"
    inventory_path = tmp_path / "inventory.json"
    boundaries_path = tmp_path / "boundaries.json"
    catalog_path = tmp_path / "catalog.json"
    data = _rng_pe()
    monkeypatch.setattr(itb_rng_return_map, "_NATIVE_ROOT", tmp_path.resolve())
    executable.write_bytes(data)
    inventory_path.write_text(json.dumps(_inventory(data)), encoding="utf-8")
    boundaries_path.write_text(
        json.dumps(_rng_boundaries(data)),
        encoding="utf-8",
    )

    common = [
        "--executable",
        str(executable),
        "--inventory",
        str(inventory_path),
        "--boundaries",
        str(boundaries_path),
    ]
    assert (
        itb_rng_return_map.main(["build", *common, "--output", str(catalog_path)])
        == 0
    )
    assert catalog_path.is_file()
    assert (
        itb_rng_return_map.main(["build", *common, "--output", str(catalog_path)])
        == 2
    )
    assert "create-only" in capsys.readouterr().err
    assert (
        itb_rng_return_map.main(
            ["verify", *common, "--catalog", str(catalog_path)]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "verified"


def test_cli_rejects_file_output_outside_native_artifact_root(
    tmp_path: Path,
    capsys,
):
    executable = tmp_path / "Breach.exe"
    inventory_path = tmp_path / "inventory.json"
    boundaries_path = tmp_path / "boundaries.json"
    data = _rng_pe()
    executable.write_bytes(data)
    inventory_path.write_text(json.dumps(_inventory(data)), encoding="utf-8")
    boundaries_path.write_text(json.dumps(_rng_boundaries(data)), encoding="utf-8")

    assert (
        itb_rng_return_map.main(
            [
                "build",
                "--executable",
                str(executable),
                "--inventory",
                str(inventory_path),
                "--boundaries",
                str(boundaries_path),
                "--output",
                str(tmp_path / "outside.json"),
            ]
        )
        == 2
    )
    assert "restricted" in capsys.readouterr().err


def test_cli_rejects_duplicate_json_keys(tmp_path: Path, capsys):
    bad = tmp_path / "inventory.json"
    bad.write_text('{"platform":"windows","platform":"windows"}', encoding="utf-8")

    assert (
        itb_rng_return_map.main(
            [
                "build",
                "--executable",
                str(tmp_path / "missing.exe"),
                "--inventory",
                str(bad),
                "--boundaries",
                str(bad),
            ]
        )
        == 2
    )
    assert "duplicate JSON key" in capsys.readouterr().err
