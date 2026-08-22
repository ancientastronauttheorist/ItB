"""Static safety contract for the dormant Mod Loader manifest command."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "bridge" / "modloader.lua").read_text(
    encoding="utf-8"
)


def _command_block() -> str:
    start = SOURCE.index('elseif cmd == "OBS_CALLBACK_MANIFEST" then')
    end = SOURCE.index('elseif cmd == "OBS_CALLBACK_BINDINGS" then', start)
    return SOURCE[start:end]


def test_callback_module_is_deferred_and_sibling_only():
    assert (
        'return directory .. "/observatory_callback_manifest.lua"' in SOURCE
    )
    assert SOURCE.count("load_observatory_callback_module()") == 4
    definition = SOURCE.index("local function load_observatory_callback_module()")
    trial = SOURCE.index("local function initialize_observatory_callback_trial")
    trial_end = SOURCE.index(
        "local function consume_observatory_callback_trial_startup_request",
        trial,
    )
    command = SOURCE.index('elseif cmd == "OBS_CALLBACK_MANIFEST" then')
    trial_invocation = SOURCE.index(
        "load_observatory_callback_module()",
        definition + len("local function load_observatory_callback_module()"),
    )
    command_invocation = SOURCE.index(
        "load_observatory_callback_module()", command
    )
    assert definition < trial < trial_invocation < trial_end < command
    assert command < command_invocation


def test_manifest_command_is_no_argument_read_only_and_file_first():
    block = _command_block()
    assert "if #parts ~= 1 then" in block
    assert "accepts no arguments" in block
    assert "discover_enemy_skill_roots" in block
    assert 'rawget(module, "enumerate")' in block
    assert "write_observatory_callback_manifest(" in block
    assert block.index("write_observatory_callback_manifest(") < block.index(
        'write_ack(\n            "OK OBS_CALLBACK_MANIFEST'
    )
    assert "Board:" not in block
    assert "Set" not in block
    assert "FireWeapon" not in block
    assert "GetTargetArea(" not in block
    assert "GetTargetScore(" not in block
    assert "GetSkillEffect(" not in block
    assert "ScorePositioning(" not in block


def test_manifest_command_does_not_join_normal_play_hooks():
    hooks = SOURCE[
        SOURCE.index("-- Game hooks (with re-execution guard)") :
        SOURCE.index("-- Startup")
    ]
    assert "OBS_CALLBACK_MANIFEST" not in hooks
    assert "observatory_callback_manifest" not in hooks


def test_startup_request_is_fixed_bounded_one_shot_and_not_command_text():
    start = SOURCE.index(
        "local function "
        "consume_observatory_callback_manifest_startup_request()"
    )
    end = SOURCE.index("-- Clean up stale files from previous session", start)
    block = SOURCE[start:end]
    assert 'file:read(128)' in block
    assert 'file:read(1)' in block
    assert 'file:read("*a")' not in block
    assert "os.remove(CALLBACK_MANIFEST_REQUEST_FILE)" in block
    assert block.index("os.remove(CALLBACK_MANIFEST_REQUEST_FILE)") < block.index(
        'execute_command("OBS_CALLBACK_MANIFEST")'
    )
    assert 'execute_command("OBS_CALLBACK_MANIFEST")' in block
    assert "execute_command(content)" not in block
    assert (
        '"observatory-callback-manifest-request/1"'
        in SOURCE
    )
