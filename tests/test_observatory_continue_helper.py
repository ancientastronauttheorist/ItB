from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import build_itb_observatory_continue_helper as helper_build


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "native" / "observatory_continue.c"
NATIVE = ROOT / "data" / "observatory" / "native"
BUILD_RECEIPT = (
    NATIVE
    / "windows_build_13725832_31fe35265598_callback_gameflow_helper_receipt.json"
)
REPRODUCIBILITY_RECEIPT = (
    NATIVE
    / "windows_build_13725832_31fe35265598_callback_gameflow_helper_reproducibility.json"
)


def test_callback_gameflow_helper_has_one_narrow_export_and_no_input_surface():
    source = SOURCE.read_text(encoding="utf-8")
    assert source.count("__declspec(dllexport)") == 1
    assert "luaopen_itb_observatory_continue" in source
    assert "OBS_HOST_GLOBAL_RVA 0x004b9cf8u" in source
    assert "OBS_TITLE_KEY_ACTION_RVA 0x0021c650u" in source
    assert "OBS_NEW_GAME_ACTION_RVA 0x00217900u" in source
    assert "OBS_MENU_BUTTON_VTABLE_RVA 0x004358f4u" in source
    assert "OBS_SCREEN_ROOT_POINTER_OFFSET 0x00000010u" in source
    assert "OBS_SCREEN_ROOT_VTABLE_RVA 0x0043544cu" in source
    assert "OBS_ACTIVE_SCREEN_POINTER_OFFSET 0x0000c204u" in source
    assert "OBS_BATTLE_UI_VTABLE_RVA 0x00430148u" in source
    assert "OBS_END_TURN_ACTION_RVA 0x00186b40u" in source
    assert "OBS_RENDER_PRESENT_IAT_RVA 0x003d6384u" in source
    assert "OBS_GL_SWAP_IAT_RVA 0x003d63b4u" in source
    assert "end_player_turn" in source
    assert "observatory_render_present" in source
    assert "observatory_gl_swap" in source
    assert source.index("restore_frame_hooks()") < source.index(
        "invoke_title_continue(g_executable_base, menu)"
    )
    assert source.count(
        "key_action(menu, NULL, OBS_KEY_EVENT_TYPE, OBS_KEY_DOWN);"
    ) == 1
    assert (
        "key_action(menu, NULL, OBS_KEY_EVENT_TYPE, OBS_KEY_ACTIVATE);" in source
    )
    assert '"Button_MainContinue"' in source
    assert "fade_progress >= fade_duration" in source
    assert "continue_status" in source
    assert helper_build.EXPECTED_EXECUTABLE_SHA256 in source
    assert helper_build.EXPECTED_SDL2_SHA256 in source
    assert "VirtualProtect" in source
    assert "memcpy(&value, (const void *)slot, sizeof(value))" in source
    assert "InterlockedCompareExchangePointer(slot, NULL, NULL)" not in source
    assert "OBS_FRAME_HOOK_TIMEOUT_MS 30000u" in source
    assert "OBS_GAME_MODE_RVA" not in source
    assert source.index("battle screen registry identity mismatch") < source.index(
        "battle UI identity mismatch"
    )
    for forbidden in (
        "SendInput",
        "SetCursorPos",
        "PostMessage",
        "SendMessage",
        "SetWindowsHookEx",
        "CreateThread",
        "WriteProcessMemory",
        "CreateRemoteThread",
        "OpenProcess",
        "CreateFile",
        "WinHttp",
        "socket(",
    ):
        assert forbidden not in source


def test_continue_builder_rejects_an_unpinned_executable(tmp_path):
    executable = tmp_path / "Breach.exe"
    executable.write_bytes(b"not the pinned executable")
    with pytest.raises(helper_build.ContinueHelperBuildError, match="pinned Continue"):
        helper_build._validate_executable(executable)


def test_builder_pins_both_reviewed_gameflow_boundaries():
    assert helper_build.TITLE_KEY_ACTION_RVA == 0x0021C650
    assert helper_build.TITLE_KEY_ACTION_SIZE == 0x402
    assert helper_build.TITLE_KEY_ACTION_RELOCATIONS == (6, 24, 321, 343, 957, 979)
    assert helper_build.TITLE_KEY_ACTION_SHA256 in SOURCE.read_text(encoding="utf-8")
    assert helper_build.NEW_GAME_ACTION_RVA == 0x00217900
    assert helper_build.NEW_GAME_ACTION_RELOCATIONS == (6, 22, 82, 135)
    assert helper_build.SCREEN_ROOT_VTABLE_RVA == 0x0043544C
    assert helper_build.END_TURN_ACTION_RVA == 0x00186B40
    assert helper_build.END_TURN_ACTION_RELOCATIONS == (6, 22, 59, 89, 132, 154)
    assert helper_build.END_TURN_ACTION_SHA256 in SOURCE.read_text(encoding="utf-8")
    assert helper_build.RENDER_PRESENT_IAT_RVA == 0x003D6384
    assert helper_build.GL_SWAP_IAT_RVA == 0x003D63B4


def test_continue_builder_rejects_an_unpinned_sdl2(tmp_path):
    library = tmp_path / "SDL2.dll"
    library.write_bytes(b"not the pinned frame bridge")
    with pytest.raises(helper_build.ContinueHelperBuildError, match="pinned frame"):
        helper_build._validate_sdl2(library)


def test_continue_build_receipt_normalizes_random_temporary_directory():
    first = helper_build._normalize_compiler_stdout(
        "Creating library C:\\Temp\\build_one\\helper.lib",
        Path("C:/Temp/build_one"),
    )
    second = helper_build._normalize_compiler_stdout(
        "Creating library C:\\Temp\\build_two\\helper.lib",
        Path("C:/Temp/build_two"),
    )
    assert first == second == "Creating library <temporary-build>\\helper.lib"


def test_committed_callback_gameflow_helper_receipts_bind_two_identical_builds():
    build = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
    reproducibility = json.loads(
        REPRODUCIBILITY_RECEIPT.read_text(encoding="utf-8")
    )

    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == build["source_sha256"]
    assert hashlib.sha256(BUILD_RECEIPT.read_bytes()).hexdigest() == (
        reproducibility["helper_receipt_sha256"]
    )
    assert reproducibility["independent_build_count"] == 2
    assert reproducibility["module_bytes_identical"] is True
    assert reproducibility["receipt_bytes_identical"] is True
    assert reproducibility["module_sha256"] == build["module_sha256"]
    assert reproducibility["module_size"] == build["module_size"] == 78848
    assert reproducibility["source_sha256"] == build["source_sha256"]
    assert build["module_sha256"] in build["module_filename"]
    assert build["helper_version"] == "observatory-callback-gameflow-helper/6"
    assert build["export_name"] == "luaopen_itb_observatory_continue"
    assert "<temporary-build>" in build["compiler_stdout"]
    assert not any((ROOT / "data" / "observatory").rglob("*.dll"))
