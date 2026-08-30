"""Tests for the metadata-only ITB resource archive inventory."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import itb_resource_inventory  # noqa: E402

from src.observatory.content_inventory import create_inventory  # noqa: E402
from src.observatory.resource_archive import (  # noqa: E402
    ResourceArchiveError,
    build_resource_inventory,
    encode_resource_inventory,
    scan_resource_archive,
    validate_resource_inventory,
)


_PNG = b"\x89PNG\r\n\x1a\n" + b"png-payload"
_TTF = b"\x00\x01\x00\x00" + b"font-payload"


def _archive(entries: list[tuple[str, bytes]]) -> bytes:
    table_end = 4 + 4 * len(entries)
    offsets: list[int] = []
    records: list[bytes] = []
    cursor = table_end
    for path, payload in entries:
        path_bytes = path.encode("utf-8")
        record = struct.pack("<II", len(payload), len(path_bytes)) + path_bytes + payload
        offsets.append(cursor)
        records.append(record)
        cursor += len(record)
    return (
        struct.pack("<I", len(entries))
        + struct.pack(f"<{len(offsets)}I", *offsets)
        + b"".join(records)
    )


def _write_pe(path: Path) -> None:
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<H", data, 132, 0x014C)
    path.write_bytes(data)


def _installation(tmp_path: Path) -> tuple[Path, Path, bytes, dict]:
    steamapps = tmp_path / "Steam/steamapps"
    root = steamapps / "common/Into the Breach"
    (root / "scripts").mkdir(parents=True)
    (root / "maps").mkdir()
    (root / "resources").mkdir()
    (root / "scripts/global.lua").write_text("return 1\n", encoding="utf-8")
    (root / "maps/example.map").write_text("map\n", encoding="utf-8")
    _write_pe(root / "Breach.exe")
    data = _archive(
        [
            ("img/example.png", _PNG),
            ("fonts/custom.font", b"custom-font"),
            ("fonts/example.ttf", _TTF),
        ]
    )
    archive = root / "resources/resource.dat"
    archive.write_bytes(data)
    (steamapps / "appmanifest_590380.acf").write_text(
        '''
"AppState"
{
    "appid" "590380"
    "installdir" "Into the Breach"
    "buildid" "123"
    "InstalledDepots"
    {
        "590381" { "manifest" "456" "size" "1234" }
    }
}
''',
        encoding="utf-8",
    )
    inventory = create_inventory(
        root,
        platform_name="windows",
        label="synthetic resource test",
    )
    return root, archive, data, inventory


def _write_archive(tmp_path: Path) -> tuple[Path, bytes]:
    data = _archive(
        [
            ("img/example.png", _PNG),
            ("fonts/custom.font", b"custom-font"),
            ("fonts/example.ttf", _TTF),
        ]
    )
    path = tmp_path / "resource.dat"
    path.write_bytes(data)
    return path, data


def test_scans_contiguous_archive_without_returning_payloads(tmp_path: Path):
    archive, data = _write_archive(tmp_path)

    result = scan_resource_archive(archive)

    assert result["path"] == "resources/resource.dat"
    assert result["size"] == len(data)
    assert result["sha256"] == hashlib.sha256(data).hexdigest()
    assert result["entry_count"] == 3
    assert [record["path"] for record in result["records"]] == [
        "img/example.png",
        "fonts/custom.font",
        "fonts/example.ttf",
    ]
    assert [record["kind"] for record in result["records"]] == [
        "png",
        "custom_font",
        "truetype_font",
    ]
    assert result["records"][0]["payload_sha256"] == hashlib.sha256(_PNG).hexdigest()
    assert all("payload" not in record for record in result["records"])
    assert result["types"] == [
        {"kind": "custom_font", "file_count": 1, "payload_bytes": 11},
        {"kind": "png", "file_count": 1, "payload_bytes": len(_PNG)},
        {"kind": "truetype_font", "file_count": 1, "payload_bytes": len(_TTF)},
    ]


def test_build_and_verify_are_deterministic_and_path_free(tmp_path: Path):
    root, _archive_path, _data, inventory = _installation(tmp_path)

    evidence = build_resource_inventory(root, inventory=inventory)
    verification = validate_resource_inventory(
        root, evidence, inventory=inventory
    )

    assert evidence["analysis_kind"] == "itb_resource_archive_inventory"
    assert evidence["summary"]["entry_count"] == 3
    assert verification["status"] == "verified"
    assert verification["summary"] == evidence["summary"]
    assert encode_resource_inventory(evidence) == encode_resource_inventory(
        build_resource_inventory(root, inventory=inventory)
    )
    assert str(tmp_path) not in encode_resource_inventory(evidence)


@pytest.mark.parametrize(
    "entries, message",
    [
        (
            [("img/A.png", _PNG), ("img/a.png", _PNG)],
            "duplicate resource path",
        ),
        ([("../escape.png", _PNG)], "path is not canonical"),
        ([("img/bad.png", b"not-png")], "invalid signature"),
        ([("fonts/bad.ttf", b"BAD!font")], "invalid signature"),
    ],
)
def test_rejects_invalid_paths_and_signatures(
    tmp_path: Path, entries: list[tuple[str, bytes]], message: str
):
    archive = tmp_path / "resource.dat"
    archive.write_bytes(_archive(entries))

    with pytest.raises(ResourceArchiveError, match=message):
        scan_resource_archive(archive)


def test_rejects_offset_gaps_and_trailing_bytes(tmp_path: Path):
    archive, data = _write_archive(tmp_path)
    broken = bytearray(data)
    first_offset = struct.unpack_from("<I", broken, 4)[0]
    struct.pack_into("<I", broken, 4, first_offset + 1)
    archive.write_bytes(broken)
    with pytest.raises(ResourceArchiveError, match="first record"):
        scan_resource_archive(archive)

    archive.write_bytes(data + b"trailing")
    with pytest.raises(ResourceArchiveError, match="record 2 span"):
        scan_resource_archive(archive)


def test_verifier_rejects_metadata_drift(tmp_path: Path):
    root, _archive_path, _data, inventory = _installation(tmp_path)
    evidence = build_resource_inventory(root, inventory=inventory)
    evidence["records"][0]["payload_size"] += 1

    with pytest.raises(ResourceArchiveError, match="does not match"):
        validate_resource_inventory(root, evidence, inventory=inventory)


def test_builder_rejects_malformed_build_identity(tmp_path: Path):
    root, _archive_path, _data, inventory = _installation(tmp_path)
    inventory["executable"]["sha256"] = "not-a-hash"

    with pytest.raises(ResourceArchiveError, match="sealed inventory"):
        build_resource_inventory(root, inventory=inventory)


def test_builder_rejects_archive_not_in_sealed_inventory(tmp_path: Path):
    root, archive, _data, inventory = _installation(tmp_path)
    archive.write_bytes(_archive([("img/replacement.png", _PNG)]))

    with pytest.raises(ResourceArchiveError, match="sealed inventory"):
        build_resource_inventory(root, inventory=inventory)


def test_cli_build_and_verify_round_trip(tmp_path: Path, capsys):
    root, _archive_path, _data, inventory_value = _installation(tmp_path)
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps(inventory_value), encoding="utf-8")

    assert (
        itb_resource_inventory.main(
            [
                "build",
                "--install-dir",
                str(root),
                "--inventory",
                str(inventory),
            ]
        )
        == 0
    )
    evidence = tmp_path / "evidence.json"
    evidence.write_text(capsys.readouterr().out, encoding="utf-8")

    assert (
        itb_resource_inventory.main(
            [
                "verify",
                "--install-dir",
                str(root),
                "--inventory",
                str(inventory),
                "--evidence",
                str(evidence),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "verified"


@pytest.mark.parametrize("malformation", ["platform", "native_library", "depot"])
def test_cli_reports_malformed_inventory_without_traceback(
    tmp_path: Path,
    capsys,
    malformation: str,
):
    root, _archive_path, _data, inventory_value = _installation(tmp_path)
    if malformation == "platform":
        inventory_value["platform"] = 7
    elif malformation == "native_library":
        inventory_value["native_libraries"].append({"path": "bad.dll"})
    else:
        inventory_value["steam"]["installed_depots"][0]["manifest"] = "invalid"
    inventory = tmp_path / f"{malformation}.json"
    inventory.write_text(json.dumps(inventory_value), encoding="utf-8")

    assert (
        itb_resource_inventory.main(
            [
                "build",
                "--install-dir",
                str(root),
                "--inventory",
                str(inventory),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "Traceback" not in captured.err


def test_output_guard_is_bounded_and_rejects_other_artifacts(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(itb_resource_inventory, "_OUTPUT_ROOT", tmp_path)
    monkeypatch.setattr(itb_resource_inventory, "_MAX_JSON_BYTES", 8)
    destination = tmp_path / "inventory.json"
    destination.write_text(
        json.dumps({"analysis_kind": "itb_resource_archive_inventory"}),
        encoding="utf-8",
    )
    with pytest.raises(
        ResourceArchiveError,
        match="existing non-resource-inventory artifact",
    ):
        itb_resource_inventory._write_evidence_atomically(destination, "{}\n")
