#!/usr/bin/env python3
"""Build and attest the build-keyed callback-campaign game-flow helper."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pefile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "native" / "observatory_continue.c"
HELPER_VERSION = "observatory-callback-gameflow-helper/6"
EXPORT_NAME = "luaopen_itb_observatory_continue"
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_BUILD_ID = "13725832"
EXPECTED_ARCHITECTURE = "x86"
EXPECTED_PE_TIMESTAMP = 0x65F16972
EXPECTED_SIZE_OF_IMAGE = 0x0056F000
HOST_GLOBAL_RVA = 0x004B9CF8
GAME_APP_VTABLE_RVA = 0x00435014
MENU_VTABLE_RVA = 0x0043597C
MENU_BUTTON_VTABLE_RVA = 0x004358F4
TITLE_KEY_ACTION_RVA = 0x0021C650
TITLE_KEY_ACTION_SIZE = 0x402
TITLE_KEY_ACTION_SHA256 = (
    "981a2a39bfcc7ae40d5aa7e4c049b3ad97877404807b979a938a0bf10bd0f481"
)
TITLE_KEY_ACTION_RELOCATIONS = (6, 24, 321, 343, 957, 979)
NEW_GAME_ACTION_RVA = 0x00217900
NEW_GAME_ACTION_SIZE = 0x11B
NEW_GAME_ACTION_SHA256 = (
    "4ae664238c4b6678a7c0c769c72d5850014e4cd5b8fdb2c6d034a16d2ee3eceb"
)
NEW_GAME_ACTION_RELOCATIONS = (6, 22, 82, 135)
SCREEN_ROOT_VTABLE_RVA = 0x0043544C
BATTLE_UI_VTABLE_RVA = 0x00430148
END_TURN_ACTION_RVA = 0x00186B40
END_TURN_ACTION_SIZE = 0xDE
END_TURN_ACTION_SHA256 = (
    "3eff056cdd650e48c1c508f48da151d39bcd987afc1043257acc4d33bf1ea756"
)
END_TURN_ACTION_RELOCATIONS = (6, 22, 59, 89, 132, 154)
RENDER_PRESENT_IAT_RVA = 0x003D6384
GL_SWAP_IAT_RVA = 0x003D63B4
EXPECTED_SDL2_SHA256 = (
    "cb7161fff576ab9a0288c14029bc98d138c3f660e764860dbd37640f06cb7f10"
)
EXPECTED_SDL2_SIZE = 891_904
EXPECTED_SDL2_PE_TIMESTAMP = 0x5DDBFEE9
EXPECTED_SDL2_SIZE_OF_IMAGE = 0x000DF000
SDL2_EXPORTS = {
    "SDL_RenderPresent": (0x000118C0, 0x000CF66C),
    "SDL_GL_SwapWindow": (0x0000FFF0, 0x000CF9D0),
}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContinueHelperBuildError(RuntimeError):
    """Raised when Continue-helper compilation or attestation is unsafe."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def _stable_bytes(path: Path, label: str) -> bytes:
    path = Path(os.path.abspath(path.expanduser()))
    if path.is_symlink() or not path.is_file():
        raise ContinueHelperBuildError(f"{label} is not a regular file: {path}")
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(data) != before.st_size
    ):
        raise ContinueHelperBuildError(f"{label} changed while being read")
    return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_executable(executable: Path) -> dict[str, Any]:
    data = _stable_bytes(executable, "Breach.exe")
    digest = _sha256(data)
    if digest != EXPECTED_EXECUTABLE_SHA256 or len(data) != EXPECTED_EXECUTABLE_SIZE:
        raise ContinueHelperBuildError("Breach.exe does not match the pinned Continue build")
    try:
        pe = pefile.PE(data=data, fast_load=False)
    except pefile.PEFormatError as exc:
        raise ContinueHelperBuildError(f"invalid pinned Breach.exe: {exc}") from exc
    if (
        pe.FILE_HEADER.Machine != 0x014C
        or pe.FILE_HEADER.TimeDateStamp != EXPECTED_PE_TIMESTAMP
        or pe.OPTIONAL_HEADER.Magic != 0x010B
        or pe.OPTIONAL_HEADER.SizeOfImage != EXPECTED_SIZE_OF_IMAGE
    ):
        raise ContinueHelperBuildError("Breach.exe PE identity is not pinned")
    title_key_region = pe.get_data(TITLE_KEY_ACTION_RVA, TITLE_KEY_ACTION_SIZE)
    if (
        len(title_key_region) != TITLE_KEY_ACTION_SIZE
        or _sha256(title_key_region) != TITLE_KEY_ACTION_SHA256
    ):
        raise ContinueHelperBuildError("title Continue key-action boundary is not pinned")
    title_key_relocations = sorted(
        entry.rva - TITLE_KEY_ACTION_RVA
        for block in pe.DIRECTORY_ENTRY_BASERELOC
        for entry in block.entries
        if TITLE_KEY_ACTION_RVA
        <= entry.rva
        < TITLE_KEY_ACTION_RVA + TITLE_KEY_ACTION_SIZE
        and entry.type == pefile.RELOCATION_TYPE["IMAGE_REL_BASED_HIGHLOW"]
    )
    if tuple(title_key_relocations) != TITLE_KEY_ACTION_RELOCATIONS:
        raise ContinueHelperBuildError(
            "title Continue key-action relocation map is not pinned"
        )
    new_game_region = pe.get_data(NEW_GAME_ACTION_RVA, NEW_GAME_ACTION_SIZE)
    if (
        len(new_game_region) != NEW_GAME_ACTION_SIZE
        or _sha256(new_game_region) != NEW_GAME_ACTION_SHA256
    ):
        raise ContinueHelperBuildError("title New Game action boundary is not pinned")
    new_game_relocations = sorted(
        entry.rva - NEW_GAME_ACTION_RVA
        for block in pe.DIRECTORY_ENTRY_BASERELOC
        for entry in block.entries
        if NEW_GAME_ACTION_RVA
        <= entry.rva
        < NEW_GAME_ACTION_RVA + NEW_GAME_ACTION_SIZE
        and entry.type == pefile.RELOCATION_TYPE["IMAGE_REL_BASED_HIGHLOW"]
    )
    if tuple(new_game_relocations) != NEW_GAME_ACTION_RELOCATIONS:
        raise ContinueHelperBuildError("title New Game relocation map is not pinned")
    end_turn_region = pe.get_data(END_TURN_ACTION_RVA, END_TURN_ACTION_SIZE)
    if (
        len(end_turn_region) != END_TURN_ACTION_SIZE
        or _sha256(end_turn_region) != END_TURN_ACTION_SHA256
    ):
        raise ContinueHelperBuildError("player End Turn action boundary is not pinned")
    end_turn_relocations = sorted(
        entry.rva - END_TURN_ACTION_RVA
        for block in pe.DIRECTORY_ENTRY_BASERELOC
        for entry in block.entries
        if END_TURN_ACTION_RVA
        <= entry.rva
        < END_TURN_ACTION_RVA + END_TURN_ACTION_SIZE
        and entry.type == pefile.RELOCATION_TYPE["IMAGE_REL_BASED_HIGHLOW"]
    )
    if tuple(end_turn_relocations) != END_TURN_ACTION_RELOCATIONS:
        raise ContinueHelperBuildError("player End Turn relocation map is not pinned")
    sdl_imports = {
        item.name.decode("ascii"): item.address - pe.OPTIONAL_HEADER.ImageBase
        for descriptor in pe.DIRECTORY_ENTRY_IMPORT
        if descriptor.dll.lower() == b"sdl2.dll"
        for item in descriptor.imports
        if item.name is not None
    }
    expected_iat = {
        "SDL_RenderPresent": RENDER_PRESENT_IAT_RVA,
        "SDL_GL_SwapWindow": GL_SWAP_IAT_RVA,
    }
    if {name: sdl_imports.get(name) for name in expected_iat} != expected_iat:
        raise ContinueHelperBuildError("Breach.exe SDL frame IAT is not pinned")
    return {
        "executable_sha256": digest,
        "title_key_action_sha256": _sha256(title_key_region),
        "title_key_action_relocations": title_key_relocations,
        "new_game_action_sha256": _sha256(new_game_region),
        "new_game_action_relocations": new_game_relocations,
        "end_turn_action_sha256": _sha256(end_turn_region),
        "end_turn_action_relocations": end_turn_relocations,
        "render_present_iat_rva": RENDER_PRESENT_IAT_RVA,
        "gl_swap_iat_rva": GL_SWAP_IAT_RVA,
    }


def _validate_sdl2(path: Path) -> dict[str, Any]:
    data = _stable_bytes(path, "SDL2.dll")
    digest = _sha256(data)
    if digest != EXPECTED_SDL2_SHA256 or len(data) != EXPECTED_SDL2_SIZE:
        raise ContinueHelperBuildError("SDL2.dll does not match the pinned frame bridge")
    try:
        pe = pefile.PE(data=data, fast_load=False)
    except pefile.PEFormatError as exc:
        raise ContinueHelperBuildError(f"invalid pinned SDL2.dll: {exc}") from exc
    if (
        pe.FILE_HEADER.Machine != 0x014C
        or pe.FILE_HEADER.TimeDateStamp != EXPECTED_SDL2_PE_TIMESTAMP
        or pe.OPTIONAL_HEADER.Magic != 0x010B
        or pe.OPTIONAL_HEADER.SizeOfImage != EXPECTED_SDL2_SIZE_OF_IMAGE
    ):
        raise ContinueHelperBuildError("SDL2.dll PE identity is not pinned")
    exports = {
        symbol.name.decode("ascii"): symbol.address
        for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols
        if symbol.name is not None
    }
    relocations = {
        entry.rva
        for block in pe.DIRECTORY_ENTRY_BASERELOC
        for entry in block.entries
        if entry.type == pefile.RELOCATION_TYPE["IMAGE_REL_BASED_HIGHLOW"]
    }
    for name, (export_rva, target_rva) in SDL2_EXPORTS.items():
        if exports.get(name) != export_rva:
            raise ContinueHelperBuildError(f"SDL2.dll export is not pinned: {name}")
        stub = pe.get_data(export_rva, 16)
        expected_stub = (
            b"\xff\x25"
            + struct.pack("<I", pe.OPTIONAL_HEADER.ImageBase + target_rva)
            + b"\xcc" * 10
        )
        if stub != expected_stub or export_rva + 2 not in relocations:
            raise ContinueHelperBuildError(f"SDL2.dll frame stub is not pinned: {name}")
    return {
        "sdl2_sha256": digest,
        "sdl2_size": len(data),
        "sdl2_exports": {
            name: f"0x{export_rva:08x}"
            for name, (export_rva, _) in sorted(SDL2_EXPORTS.items())
        },
    }


def _vswhere() -> Path:
    candidate = Path(os.environ.get("ProgramFiles(x86)", "")) / (
        "Microsoft Visual Studio/Installer/vswhere.exe"
    )
    if not candidate.is_file():
        raise ContinueHelperBuildError("Visual Studio vswhere.exe is unavailable")
    return candidate


def _msvc_environment() -> tuple[dict[str, str], str]:
    result = subprocess.run(
        [
            str(_vswhere()),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    vcvars = Path(result.stdout.strip()) / "VC" / "Auxiliary" / "Build" / "vcvars32.bat"
    if not vcvars.is_file():
        raise ContinueHelperBuildError("Visual C++ x86 environment is unavailable")
    with tempfile.TemporaryDirectory(prefix="itb_observatory_continue_env_") as raw:
        script = Path(raw) / "environment.cmd"
        script.write_text(f'@call "{vcvars}" >nul\n@set\n', encoding="utf-8")
        configured = subprocess.run(
            ["cmd.exe", "/d", "/c", str(script)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    if configured.returncode != 0:
        raise ContinueHelperBuildError("vcvars32.bat failed to configure MSVC")
    environment = {key.upper(): value for key, value in os.environ.items()}
    for line in configured.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            environment[key.upper()] = value
    compiler_path = shutil.which("cl.exe", path=environment.get("PATH"))
    if compiler_path is None:
        raise ContinueHelperBuildError("cl.exe was not configured by vcvars32.bat")
    version = subprocess.run(
        [compiler_path], env=environment, capture_output=True, text=True, timeout=15
    )
    banner = (version.stderr or version.stdout).splitlines()
    return environment, (banner[0].strip() if banner else "unknown MSVC")


def _machine(data: bytes) -> int:
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ContinueHelperBuildError("compiled helper is not a PE image")
    (pe_offset,) = struct.unpack_from("<I", data, 0x3C)
    if pe_offset + 6 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ContinueHelperBuildError("compiled helper has an invalid PE header")
    return struct.unpack_from("<H", data, pe_offset + 4)[0]


def _write_create_only(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ContinueHelperBuildError(f"immutable output already exists: {path.name}") from exc


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _normalize_compiler_stdout(value: str, temporary_root: Path) -> str:
    result = value.strip()
    for spelling in {str(temporary_root), temporary_root.as_posix()}:
        result = result.replace(spelling, "<temporary-build>")
    return result


def build_helper(args: argparse.Namespace) -> int:
    identities = _validate_executable(args.executable)
    sdl2_identities = _validate_sdl2(args.executable.parent / "SDL2.dll")
    source_data = _stable_bytes(SOURCE, "helper source")
    environment, compiler = _msvc_environment()
    with tempfile.TemporaryDirectory(prefix="itb_observatory_continue_") as raw:
        temporary = Path(raw)
        dll = temporary / "itb_observatory_continue.dll"
        obj = temporary / "observatory_continue.obj"
        compiler_path = shutil.which("cl.exe", path=environment.get("PATH"))
        assert compiler_path is not None
        command = [
            compiler_path,
            "/nologo",
            "/LD",
            "/O2",
            "/MT",
            "/W4",
            "/WX",
            "/GS-",
            f"/Fo{obj}",
            f"/Fe{dll}",
            str(SOURCE),
            "/link",
            "/NOLOGO",
            "/INCREMENTAL:NO",
            "/Brepro",
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise ContinueHelperBuildError(
                "MSVC failed to build the Continue helper"
                + (f": {detail}" if detail else "")
            )
        compiler_stdout = _normalize_compiler_stdout(completed.stdout, temporary)
        helper_data = _stable_bytes(dll, "compiled helper")
        if _machine(helper_data) != 0x014C:
            raise ContinueHelperBuildError("compiled helper is not x86")
        helper_pe = pefile.PE(data=helper_data, fast_load=False)
        exports = [
            symbol.name.decode("ascii")
            for symbol in helper_pe.DIRECTORY_ENTRY_EXPORT.symbols
            if symbol.name is not None
        ]
        if exports != [EXPORT_NAME]:
            raise ContinueHelperBuildError("compiled helper export surface is not exact")
        helper_sha = _sha256(helper_data)
        if _SHA256_RE.fullmatch(helper_sha) is None:
            raise ContinueHelperBuildError("compiled helper digest is invalid")

    output_root = Path(os.path.abspath(args.output_root.expanduser()))
    filename = f"itb_observatory_continue_{helper_sha}.dll"
    helper_path = output_root / filename
    receipt_path = output_root / f"{filename}.receipt.json"
    _write_create_only(helper_path, helper_data)
    receipt = {
        "schema_version": 1,
        "kind": "observatory_callback_gameflow_helper_build",
        "helper_version": HELPER_VERSION,
        "module_filename": filename,
        "module_sha256": helper_sha,
        "module_size": len(helper_data),
        "architecture": EXPECTED_ARCHITECTURE,
        "export_name": EXPORT_NAME,
        "source_path": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": _sha256(source_data),
        "compiler": compiler,
        "compiler_stdout": compiler_stdout,
        "executable_sha256": identities["executable_sha256"],
        "build_id": EXPECTED_BUILD_ID,
        "host_global_rva": f"0x{HOST_GLOBAL_RVA:08x}",
        "game_app_vtable_rva": f"0x{GAME_APP_VTABLE_RVA:08x}",
        "menu_vtable_rva": f"0x{MENU_VTABLE_RVA:08x}",
        "menu_button_vtable_rva": f"0x{MENU_BUTTON_VTABLE_RVA:08x}",
        "title_key_action_rva": f"0x{TITLE_KEY_ACTION_RVA:08x}",
        "title_key_action_size": TITLE_KEY_ACTION_SIZE,
        "title_key_action_region_sha256": identities[
            "title_key_action_sha256"
        ],
        "title_key_action_relocations": identities[
            "title_key_action_relocations"
        ],
        "new_game_action_rva": f"0x{NEW_GAME_ACTION_RVA:08x}",
        "new_game_action_size": NEW_GAME_ACTION_SIZE,
        "new_game_action_region_sha256": identities["new_game_action_sha256"],
        "new_game_action_relocations": identities["new_game_action_relocations"],
        "screen_root_vtable_rva": f"0x{SCREEN_ROOT_VTABLE_RVA:08x}",
        "battle_ui_vtable_rva": f"0x{BATTLE_UI_VTABLE_RVA:08x}",
        "end_turn_action_rva": f"0x{END_TURN_ACTION_RVA:08x}",
        "end_turn_action_size": END_TURN_ACTION_SIZE,
        "end_turn_action_region_sha256": identities["end_turn_action_sha256"],
        "end_turn_action_relocations": identities["end_turn_action_relocations"],
        "render_present_iat_rva": (
            f"0x{identities['render_present_iat_rva']:08x}"
        ),
        "gl_swap_iat_rva": f"0x{identities['gl_swap_iat_rva']:08x}",
        "sdl2_sha256": sdl2_identities["sdl2_sha256"],
        "sdl2_size": sdl2_identities["sdl2_size"],
        "sdl2_exports": sdl2_identities["sdl2_exports"],
    }
    _write_create_only(receipt_path, _canonical_json(receipt))
    if _stable_bytes(helper_path, "published helper") != helper_data:
        raise ContinueHelperBuildError("published helper failed byte verification")
    print(
        f"helper={helper_path} sha256={helper_sha} size={len(helper_data)} "
        f"receipt={receipt_path}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return build_helper(args)
    except (ContinueHelperBuildError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
