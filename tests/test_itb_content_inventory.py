"""Focused tests for deterministic, read-only ITB content inventories."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

from src.observatory import content_inventory as inventory_module
from src.observatory.content_inventory import (
    InventoryError,
    build_manifest,
    compare_inventories,
    create_inventory,
    detect_installations,
    inspect_executable_format,
    parse_vdf,
    write_json,
)


def _write_pe(path: Path, machine: int = 0x014C) -> None:
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<H", data, 132, machine)
    path.write_bytes(data)


def _installation(tmp_path: Path, *, script_body: bytes = b"return 1\n") -> Path:
    root = tmp_path / "Into the Breach"
    (root / "scripts/advanced").mkdir(parents=True)
    (root / "maps").mkdir()
    (root / "scripts/global.lua").write_bytes(script_body)
    (root / "scripts/advanced/feature.lua").write_bytes(b"return 2\n")
    (root / "maps/archive.map").write_bytes(b"map bytes\r\n")
    _write_pe(root / "Breach.exe")
    _write_pe(root / "lua5.1.dll")
    return root


def test_manifest_is_sorted_normalized_and_content_addressed(tmp_path: Path):
    root = _installation(tmp_path)
    manifest = build_manifest(root, "scripts")
    assert [entry["path"] for entry in manifest["files"]] == [
        "scripts/advanced/feature.lua",
        "scripts/global.lua",
    ]
    global_entry = manifest["files"][1]
    assert global_entry["sha256"] == hashlib.sha256(b"return 1\n").hexdigest()
    assert manifest["file_count"] == 2
    assert manifest["byte_count"] == len(b"return 1\n") + len(b"return 2\n")


def test_manifest_size_and_hash_come_from_one_stable_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root = _installation(tmp_path, script_body=b"x")
    target = root / "scripts/global.lua"
    original_sha256_file = inventory_module.sha256_file

    def mutate_before_legacy_hash(path: Path, chunk_size: int = 1024 * 1024):
        if path == target:
            path.write_bytes(b"replacement")
        return original_sha256_file(path, chunk_size)

    # The legacy manifest path read size first and called this public helper
    # afterward, producing an old-size/new-hash record under this mutation.
    monkeypatch.setattr(
        inventory_module,
        "sha256_file",
        mutate_before_legacy_hash,
    )
    manifest = build_manifest(root, "scripts")
    entry = next(
        item
        for item in manifest["files"]
        if item["path"] == "scripts/global.lua"
    )
    observed = target.read_bytes()
    assert entry["size"] == len(observed)
    assert entry["sha256"] == hashlib.sha256(observed).hexdigest()


def test_inventory_rejects_change_between_format_inspection_and_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root = _installation(tmp_path)
    executable = root / "Breach.exe"
    original_inspect = inventory_module.inspect_executable_format

    def mutate_after_inspection(path: Path):
        result = original_inspect(path)
        if path == executable:
            path.write_bytes(path.read_bytes() + b"replacement")
        return result

    monkeypatch.setattr(
        inventory_module,
        "inspect_executable_format",
        mutate_after_inspection,
    )
    with pytest.raises(InventoryError, match="changed while"):
        create_inventory(root, platform_name="windows")


def test_inventory_is_deterministic_and_reads_steam_evidence(tmp_path: Path):
    steamapps = tmp_path / "Steam/steamapps"
    root = _installation(steamapps / "common")
    (steamapps / "appmanifest_590380.acf").write_text(
        '''
"AppState"
{
    "appid" "590380"
    "installdir" "Into the Breach"
    "buildid" "13725832"
    "SizeOnDisk" "1234"
    "LastUpdated" "1700000000"
    "InstalledDepots"
    {
        "590381" { "manifest" "abc" "size" "1234" }
    }
}
''',
        encoding="utf-8",
    )
    first = create_inventory(root, platform_name="windows", label="synthetic")
    second = create_inventory(root, platform_name="windows", label="synthetic")
    assert first == second
    assert first["executable"]["format"] == "pe"
    assert first["executable"]["architecture"] == "x86"
    assert first["steam"]["build_id"] == "13725832"
    assert "install_root" not in first
    assert first["steam"]["evidence"]["path"] == "appmanifest_590380.acf"
    assert len(first["steam"]["evidence"]["sha256"]) == 64
    assert first["steam"]["installed_depots"] == [
        {"depot_id": "590381", "manifest": "abc", "size": 1234}
    ]
    assert first["native_libraries"][0]["path"] == "lua5.1.dll"


def test_macos_app_bundle_layout_is_supported(tmp_path: Path):
    root = tmp_path / "Into the Breach"
    resources = root / "Into the Breach.app/Contents/Resources"
    (resources / "scripts").mkdir(parents=True)
    (resources / "maps").mkdir()
    (resources / "scripts/global.lua").write_text("return 1\n")
    executable = root / "Into the Breach.app/Contents/MacOS/Into the Breach"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"\xcf\xfa\xed\xfe" + struct.pack("<I", 0x0100000C) + b"\0" * 32)
    framework = root / "Into the Breach.app/Contents/Frameworks/SDL2.framework/SDL2"
    framework.parent.mkdir(parents=True)
    framework.write_bytes(b"\xcf\xfa\xed\xfe" + struct.pack("<I", 0x0100000C) + b"\0" * 32)
    inventory = create_inventory(root, platform_name="macos")
    assert inventory["content_root"] == "Into the Breach.app/Contents/Resources"
    assert inventory["executable"]["format"] == "mach-o"
    assert inventory["executable"]["architecture"] == "arm64"
    assert [library["path"] for library in inventory["native_libraries"]] == [
        "Into the Breach.app/Contents/Frameworks/SDL2.framework/SDL2"
    ]


def test_compare_uses_hashes_and_distinguishes_platform_specific(tmp_path: Path):
    left_root = _installation(tmp_path / "left")
    right_root = _installation(tmp_path / "right", script_body=b"return 99\n")
    (right_root / "maps/archive.map").unlink()
    (right_root / "lua5.1.dll").unlink()
    (right_root / "libgame.so").write_bytes(b"\x7fELF" + bytes([1, 1]) + b"\0" * 12 + struct.pack("<H", 3))
    left = create_inventory(left_root, platform_name="windows", label="left")
    right = create_inventory(right_root, platform_name="windows", label="right")
    right["platform"] = "linux"
    comparison = compare_inventories(left, right)
    by_key = {
        (entry["collection"], entry["path"]): entry
        for entry in comparison["entries"]
    }
    assert by_key[("scripts", "scripts/advanced/feature.lua")]["status"] == "identical"
    assert by_key[("scripts", "scripts/global.lua")]["status"] == "changed"
    assert by_key[("maps", "maps/archive.map")]["status"] == "missing"
    assert by_key[("native_libraries", "lua5.1.dll")]["status"] == "platform_specific"
    assert by_key[("native_libraries", "libgame.so")]["status"] == "platform_specific"


def test_detect_installation_from_synthetic_libraryfolders(tmp_path: Path):
    steam = tmp_path / "Steam"
    library = tmp_path / "Library"
    (steam / "steamapps").mkdir(parents=True)
    (library / "steamapps/common/Into the Breach").mkdir(parents=True)
    (library / "steamapps/appmanifest_590380.acf").write_text(
        '"AppState" { "appid" "590380" "installdir" "Into the Breach" }'
    )
    escaped_library = str(library).replace("\\", "\\\\")
    (steam / "steamapps/libraryfolders.vdf").write_text(
        f'"libraryfolders" {{ "1" {{ "path" "{escaped_library}" }} }}'
    )
    found = detect_installations(
        platform_name="linux",
        environ={"HOME": str(tmp_path / "empty-home")},
        extra_steam_roots=[steam],
    )
    assert found == [(library / "steamapps/common/Into the Breach").resolve()]


def test_vdf_parser_and_stable_json(tmp_path: Path):
    parsed = parse_vdf('"root" { "path" "B:\\\\SteamLibrary" "id" "590380" }')
    assert parsed == {"root": {"path": r"B:\SteamLibrary", "id": "590380"}}
    output = tmp_path / "nested/inventory.json"
    rendered = write_json({"z": 1, "a": 2}, output)
    assert rendered == '{\n  "a": 2,\n  "z": 1\n}\n'
    assert json.loads(output.read_text()) == {"a": 2, "z": 1}


def test_elf_header_detection(tmp_path: Path):
    path = tmp_path / "Breach"
    path.write_bytes(b"\x7fELF" + bytes([2, 1]) + b"\0" * 12 + struct.pack("<H", 62))
    assert inspect_executable_format(path) == {
        "format": "elf",
        "architecture": "x86_64",
        "bits": 64,
    }


def test_platform_is_inferred_from_binary_and_mismatch_is_rejected(tmp_path: Path):
    root = _installation(tmp_path)
    inventory = create_inventory(root)
    assert inventory["platform"] == "windows"
    with pytest.raises(InventoryError, match="requested linux build but executable is pe"):
        create_inventory(root, platform_name="linux")


def test_large_pe_header_offset_is_supported(tmp_path: Path):
    path = tmp_path / "large-header.exe"
    data = bytearray(8192)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 6000)
    data[6000:6004] = b"PE\0\0"
    struct.pack_into("<H", data, 6004, 0x8664)
    path.write_bytes(data)
    assert inspect_executable_format(path) == {
        "format": "pe",
        "architecture": "x86_64",
    }


def test_fat_macho_architectures_are_reported(tmp_path: Path):
    path = tmp_path / "universal"
    data = bytearray(b"\xca\xfe\xba\xbe" + struct.pack(">I", 2))
    data.extend(struct.pack(">IIIII", 0x01000007, 0, 0, 0, 0))
    data.extend(struct.pack(">IIIII", 0x0100000C, 0, 0, 0, 0))
    path.write_bytes(data)
    assert inspect_executable_format(path) == {
        "format": "mach-o-fat",
        "architecture": "universal",
        "architectures": ["x86_64", "arm64"],
    }


def test_fat64_macho_architectures_are_reported(tmp_path: Path):
    path = tmp_path / "universal64"
    data = bytearray(b"\xca\xfe\xba\xbf" + struct.pack(">I", 1))
    data.extend(struct.pack(">IIQQII", 0x0100000C, 0, 0, 0, 0, 0))
    path.write_bytes(data)
    assert inspect_executable_format(path) == {
        "format": "mach-o-fat64",
        "architecture": "universal",
        "architectures": ["arm64"],
    }


def test_steam_manifest_must_describe_inventory_root(tmp_path: Path):
    steamapps = tmp_path / "Steam/steamapps"
    root = _installation(steamapps / "other")
    (steamapps / "appmanifest_590380.acf").write_text(
        '"AppState" { "appid" "590380" "installdir" "Different" }'
    )
    with pytest.raises(InventoryError, match="does not describe"):
        create_inventory(root, platform_name="windows")


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="creating file symlinks is not reliably unprivileged on Windows",
)
def test_content_manifest_does_not_follow_symlink_escape(tmp_path: Path):
    root = _installation(tmp_path)
    secret = tmp_path / "secret.lua"
    secret.write_text("outside")
    (root / "scripts/escape.lua").symlink_to(secret)
    manifest = build_manifest(root, "scripts")
    assert "scripts/escape.lua" not in {
        entry["path"] for entry in manifest["files"]
    }


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="creating file symlinks is not reliably unprivileged on Windows",
)
def test_install_does_not_follow_external_executable_symlink(tmp_path: Path):
    root = _installation(tmp_path / "inside")
    (root / "Breach.exe").unlink()
    external = _installation(tmp_path / "outside") / "Breach.exe"
    (root / "Breach.exe").symlink_to(external)
    with pytest.raises(InventoryError, match="no native executable"):
        create_inventory(root, platform_name="windows")


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="creating directory symlinks is not reliably unprivileged on Windows",
)
def test_install_does_not_follow_external_app_resources_symlink(tmp_path: Path):
    root = tmp_path / "inside"
    external = tmp_path / "outside-resources"
    (external / "scripts").mkdir(parents=True)
    (external / "maps").mkdir()
    resources = root / "Into the Breach.app/Contents/Resources"
    resources.parent.mkdir(parents=True)
    resources.symlink_to(external, target_is_directory=True)
    with pytest.raises(InventoryError, match="does not contain scripts"):
        create_inventory(root, platform_name="macos")
