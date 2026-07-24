"""Focused tests for the read-only PE named-anchor mapper."""

from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import itb_pe_anchor_map  # noqa: E402

from src.observatory.pe_anchor_map import (
    PEImage,
    PEAnchorError,
    build_pe_anchor_map,
    encode_anchor_map,
)


def _synthetic_pe(anchor: bytes = b"random_int\0") -> bytes:
    data = bytearray(0x600)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into(
        "<HHIIIHH",
        data,
        0x84,
        0x014C,
        1,
        0x12345678,
        0,
        0,
        0xE0,
        0x010F,
    )
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x10B)
    struct.pack_into("<I", data, optional + 16, 0x1000)
    struct.pack_into("<I", data, optional + 28, 0x400000)
    struct.pack_into("<I", data, optional + 32, 0x1000)
    struct.pack_into("<I", data, optional + 36, 0x200)
    struct.pack_into("<I", data, optional + 56, 0x2000)
    struct.pack_into("<I", data, optional + 60, 0x200)
    struct.pack_into("<I", data, optional + 92, 16)
    struct.pack_into(
        "<II", data, optional + 96 + 1 * 8, 0x1280, 40
    )
    struct.pack_into(
        "<II", data, optional + 96 + 6 * 8, 0x1200, 28
    )
    section = optional + 0xE0
    data[section : section + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, section + 8, 0x400, 0x1000, 0x400, 0x200)
    struct.pack_into("<I", data, section + 36, 0x60000020)
    anchor_offset = 0x300
    data[anchor_offset : anchor_offset + len(anchor)] = anchor
    anchor_va = 0x400000 + 0x1000 + (anchor_offset - 0x200)
    data[0x220] = 0x68
    struct.pack_into("<I", data, 0x221, anchor_va)
    codeview = (
        b"RSDS"
        + bytes.fromhex("1eb242a87c6bb543ac68b0231cef7684")
        + struct.pack("<I", 1)
        + b"D:\\build\\Breach.pdb\0"
    )
    struct.pack_into(
        "<IIHHIIII",
        data,
        0x400,
        0,
        0x12345678,
        0,
        0,
        2,
        len(codeview),
        0x1240,
        0x440,
    )
    data[0x440 : 0x440 + len(codeview)] = codeview
    struct.pack_into(
        "<IIIII",
        data,
        0x480,
        0x12E0,
        0,
        0,
        0x12C0,
        0x1300,
    )
    data[0x4C0 : 0x4C0 + len(b"lua5.1.dll\0")] = b"lua5.1.dll\0"
    struct.pack_into("<II", data, 0x4E0, 0x1320, 0)
    struct.pack_into("<II", data, 0x500, 0x1320, 0)
    struct.pack_into("<H", data, 0x520, 7)
    import_name = b"lua_pushcclosure\0"
    data[0x522 : 0x522 + len(import_name)] = import_name
    return bytes(data)


def _inventory(data: bytes) -> dict:
    return {
        "platform": "windows",
        "label": "synthetic-test",
        "executable": {
            "path": "Breach.exe",
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "format": "pe",
            "architecture": "x86",
        },
        "steam": {
            "build_id": "123",
            "installed_depots": [
                {"depot_id": "590381", "manifest": "456"}
            ],
            "evidence": {"sha256": "d" * 64},
        },
        "content": {
            "scripts": {"revision_sha256": "a" * 64},
            "maps": {"revision_sha256": "b" * 64},
        },
        "native_libraries": [],
    }


def _synthetic_pe64() -> bytes:
    data = bytearray(0x600)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into(
        "<HHIIIHH",
        data,
        0x84,
        0x8664,
        1,
        0x12345678,
        0,
        0,
        0xF0,
        0x0022,
    )
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<I", data, optional + 16, 0x1000)
    struct.pack_into("<Q", data, optional + 24, 0x140000000)
    struct.pack_into("<I", data, optional + 32, 0x1000)
    struct.pack_into("<I", data, optional + 36, 0x200)
    struct.pack_into("<I", data, optional + 56, 0x2000)
    struct.pack_into("<I", data, optional + 60, 0x200)
    struct.pack_into("<I", data, optional + 108, 16)
    struct.pack_into(
        "<II", data, optional + 112 + 1 * 8, 0x1280, 40
    )
    section = optional + 0xF0
    data[section : section + 8] = b".text\0\0\0"
    struct.pack_into(
        "<IIII", data, section + 8, 0x400, 0x1000, 0x400, 0x200
    )
    struct.pack_into("<I", data, section + 36, 0x60000020)
    struct.pack_into(
        "<IIIII",
        data,
        0x480,
        0x12E0,
        0,
        0,
        0x12C0,
        0x1300,
    )
    data[0x4C0 : 0x4C0 + len(b"lua5.1.dll\0")] = b"lua5.1.dll\0"
    ordinal = (1 << 63) | 42
    struct.pack_into("<QQQ", data, 0x4E0, 0x1320, ordinal, 0)
    struct.pack_into("<QQQ", data, 0x500, 0x1320, ordinal, 0)
    struct.pack_into("<H", data, 0x520, 9)
    name = b"lua_setfield\0"
    data[0x522 : 0x522 + len(name)] = name
    return bytes(data)


def test_maps_string_and_push_address_candidate(tmp_path: Path):
    executable = tmp_path / "Breach.exe"
    data = _synthetic_pe()
    executable.write_bytes(data)

    result = build_pe_anchor_map(
        executable,
        anchors=["random_int", "missing"],
        inventory=_inventory(data),
    )

    assert result["identity"]["executable_sha256"] == hashlib.sha256(
        data
    ).hexdigest()
    assert result["identity"]["build_id"] == "123"
    assert result["pe"]["codeview"] == [
        {
            "evidence_class": "fact",
            "format": "RSDS",
            "guid": "a842b21e-6b7c-43b5-ac68-b0231cef7684",
            "raw_guid_bytes_hex": "1eb242a87c6bb543ac68b0231cef7684",
            "age": 1,
            "pdb_path": "D:\\build\\Breach.pdb",
            "debug_timestamp": 0x12345678,
            "debug_version": "0.0",
        }
    ]
    assert result["pe"]["lua_api_imports"] == [
        {
            "evidence_class": "fact",
            "library": "lua5.1.dll",
            "name": "lua_pushcclosure",
            "ordinal": None,
            "hint": 7,
            "iat_rva": "0x00001300",
        }
    ]
    by_name = {item["name"]: item for item in result["anchors"]}
    occurrence = by_name["random_int"]["string_occurrences"][0]
    assert occurrence == {
        "evidence_class": "fact",
        "file_offset": "0x00000300",
        "rva": "0x00001100",
        "virtual_address": "0x00401100",
        "section": ".text",
        "null_terminated": True,
    }
    reference = by_name["random_int"]["address_reference_candidates"][0]
    assert reference["evidence_class"] == "inference"
    assert reference["candidate_kind"] == "push_imm_address_candidate"
    assert reference["instruction_rva"] == "0x00001020"
    assert by_name["missing"]["status"] == "not_found"
    assert result["summary"] == {
        "requested_anchors": 2,
        "anchors_found": 1,
        "string_occurrences": 1,
        "address_reference_candidates": 1,
        "lua_api_imports": 1,
    }


def test_output_is_deterministic_and_has_no_input_path(tmp_path: Path):
    executable = tmp_path / "private" / "Breach.exe"
    executable.parent.mkdir()
    executable.write_bytes(_synthetic_pe())
    first = encode_anchor_map(
        build_pe_anchor_map(executable, anchors=["random_int"])
    )
    second = encode_anchor_map(
        build_pe_anchor_map(executable, anchors=["random_int"])
    )
    assert first == second
    assert str(tmp_path) not in first
    json.loads(first)


def test_inventory_mismatch_fails_closed(tmp_path: Path):
    executable = tmp_path / "Breach.exe"
    data = _synthetic_pe()
    executable.write_bytes(data)
    inventory = _inventory(data)
    inventory["executable"]["sha256"] = "0" * 64
    with pytest.raises(PEAnchorError, match="does not match"):
        build_pe_anchor_map(executable, inventory=inventory)


@pytest.mark.parametrize(
    "inventory",
    [
        [],
        {"platform": "windows", "executable": {}},
        {
            "platform": "windows",
            "executable": {},
            "steam": [],
            "content": {},
            "native_libraries": [],
        },
    ],
)
def test_malformed_inventory_shapes_fail_closed(
    tmp_path: Path, inventory
):
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(_synthetic_pe())
    with pytest.raises(PEAnchorError):
        build_pe_anchor_map(executable, inventory=inventory)


@pytest.mark.parametrize("data", [b"", b"MZ" + b"\0" * 80])
def test_malformed_pe_is_rejected(tmp_path: Path, data: bytes):
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(data)
    with pytest.raises(PEAnchorError):
        build_pe_anchor_map(executable)


def test_optional_header_bounds_and_machine_bitness_are_enforced(
    tmp_path: Path,
):
    executable = tmp_path / "Breach.exe"

    undersized = bytearray(_synthetic_pe())
    struct.pack_into("<H", undersized, 0x94, 2)
    executable.write_bytes(undersized)
    with pytest.raises(PEAnchorError, match="undersized"):
        build_pe_anchor_map(executable)

    impossible_directories = bytearray(_synthetic_pe())
    struct.pack_into("<H", impossible_directories, 0x94, 96)
    executable.write_bytes(impossible_directories)
    with pytest.raises(PEAnchorError, match="data-directory count"):
        build_pe_anchor_map(executable)

    incompatible = bytearray(_synthetic_pe())
    struct.pack_into("<H", incompatible, 0x84, 0x8664)
    executable.write_bytes(incompatible)
    with pytest.raises(PEAnchorError, match="incompatible"):
        build_pe_anchor_map(executable)

    overflowing = bytearray(_synthetic_pe())
    section = 0x98 + 0xE0
    struct.pack_into("<I", overflowing, section + 12, 0xFFFFFFF0)
    executable.write_bytes(overflowing)
    with pytest.raises(PEAnchorError, match="address width"):
        build_pe_anchor_map(executable)


def test_non_x86_images_receive_only_generic_reference_labels(
    tmp_path: Path,
):
    executable = tmp_path / "Breach.exe"
    arm = bytearray(_synthetic_pe())
    struct.pack_into("<H", arm, 0x84, 0x01C0)
    executable.write_bytes(arm)
    result = build_pe_anchor_map(executable, anchors=["random_int"])
    kinds = {
        item["candidate_kind"]
        for item in result["anchors"][0]["address_reference_candidates"]
    }
    assert kinds == {"literal_address_candidate"}


def test_import_directory_requires_descriptor_terminator(tmp_path: Path):
    executable = tmp_path / "Breach.exe"
    malformed = bytearray(_synthetic_pe())
    optional = 0x98
    struct.pack_into(
        "<II", malformed, optional + 96 + 1 * 8, 0x1280, 20
    )
    executable.write_bytes(malformed)
    with pytest.raises(PEAnchorError, match="descriptor table"):
        build_pe_anchor_map(executable)


def test_import_thunks_and_iat_slots_must_stay_in_mapped_image(
    tmp_path: Path,
):
    executable = tmp_path / "Breach.exe"

    overlay_terminator = bytearray(_synthetic_pe())
    struct.pack_into("<I", overlay_terminator, 0x480, 0x13FC)
    struct.pack_into("<I", overlay_terminator, 0x5FC, 0x1320)
    overlay_terminator.extend(b"\0\0\0\0")
    executable.write_bytes(overlay_terminator)
    with pytest.raises(PEAnchorError, match="thunk"):
        build_pe_anchor_map(executable)

    unmapped_iat = bytearray(_synthetic_pe())
    struct.pack_into("<I", unmapped_iat, 0x480 + 16, 0x00700000)
    executable.write_bytes(unmapped_iat)
    with pytest.raises(PEAnchorError, match="IAT slot"):
        build_pe_anchor_map(executable)


def test_pe32_plus_named_and_ordinal_imports_use_64_bit_thunks():
    imports = PEImage(_synthetic_pe64()).imports()
    assert imports == [
        {
            "evidence_class": "fact",
            "library": "lua5.1.dll",
            "name": "lua_setfield",
            "ordinal": None,
            "hint": 9,
            "iat_rva": "0x00001300",
        },
        {
            "evidence_class": "fact",
            "library": "lua5.1.dll",
            "name": None,
            "ordinal": 42,
            "hint": None,
            "iat_rva": "0x00001308",
        },
    ]


def test_anchors_must_be_ascii_and_nonempty(tmp_path: Path):
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(_synthetic_pe())
    with pytest.raises(PEAnchorError, match="ASCII"):
        build_pe_anchor_map(executable, anchors=[""])
    with pytest.raises(PEAnchorError, match="ASCII"):
        build_pe_anchor_map(executable, anchors=["résist"])
    with pytest.raises(PEAnchorError, match="unique"):
        build_pe_anchor_map(
            executable, anchors=["random_int", "random_int"]
        )


def test_cli_writes_only_to_atomic_evidence_root(
    tmp_path: Path, capsys, monkeypatch
):
    game = tmp_path / "game"
    game.mkdir()
    executable = game / "Breach.exe"
    executable.write_bytes(_synthetic_pe())
    executable_before = executable.read_bytes()
    output_root = tmp_path / "evidence"
    monkeypatch.setattr(itb_pe_anchor_map, "_OUTPUT_ROOT", output_root)

    refused = game / "anchors.json"
    assert (
        itb_pe_anchor_map.main(
            [
                "--executable",
                str(executable),
                "--output",
                str(refused),
            ]
        )
        == 2
    )
    assert not refused.exists()
    assert "direct child" in capsys.readouterr().err

    profile_state = tmp_path / "profile" / "itb_bridge" / "state.json"
    profile_state.parent.mkdir(parents=True)
    profile_state.write_text("LIVE", encoding="utf-8")
    assert (
        itb_pe_anchor_map.main(
            [
                "--executable",
                str(executable),
                "--output",
                str(profile_state),
            ]
        )
        == 2
    )
    assert profile_state.read_text(encoding="utf-8") == "LIVE"

    allowed = output_root / "anchors.json"
    assert (
        itb_pe_anchor_map.main(
            [
                "--executable",
                str(executable),
                "--output",
                str(allowed),
            ]
        )
        == 0
    )
    assert json.loads(allowed.read_text(encoding="utf-8"))[
        "analysis_kind"
    ] == "pe_named_anchor_map"

    hardlink = output_root / "hardlink.json"
    os.link(executable, hardlink)
    assert (
        itb_pe_anchor_map.main(
            [
                "--executable",
                str(executable),
                "--output",
                str(hardlink),
            ]
        )
        == 2
    )
    assert executable.read_bytes() == executable_before


def test_cli_rejects_nonstandard_inventory_json(
    tmp_path: Path, capsys
):
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(_synthetic_pe())
    inventory = tmp_path / "inventory.json"
    inventory.write_text('{"label": NaN}', encoding="utf-8")
    assert (
        itb_pe_anchor_map.main(
            [
                "--executable",
                str(executable),
                "--inventory",
                str(inventory),
            ]
        )
        == 2
    )
    assert "invalid inventory JSON constant" in capsys.readouterr().err
