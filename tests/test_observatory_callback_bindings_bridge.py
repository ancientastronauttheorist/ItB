"""Static safety contract for inert callback-slot bridge operations."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "bridge" / "modloader.lua").read_text(encoding="utf-8")


def _command_block() -> str:
    start = SOURCE.index('elseif cmd == "OBS_CALLBACK_BINDINGS" then')
    end = SOURCE.index('elseif cmd == "OBS_NATIVE_RNG_SEED" then', start)
    return SOURCE[start:end]


def test_binding_modules_are_deferred_siblings():
    assert 'return directory .. "/observatory_callback_bindings.lua"' in SOURCE
    definition = SOURCE.index(
        "local function load_observatory_callback_bindings_module()"
    )
    trial = SOURCE.index("local function initialize_observatory_callback_trial")
    trial_end = SOURCE.index(
        "local function consume_observatory_callback_trial_startup_request",
        trial,
    )
    command = SOURCE.index('elseif cmd == "OBS_CALLBACK_BINDINGS" then')
    trial_invocation = SOURCE.index(
        "load_observatory_callback_bindings_module()",
        definition + len("local function load_observatory_callback_bindings_module()"),
    )
    command_invocation = SOURCE.index(
        "load_observatory_callback_bindings_module()", command
    )
    assert definition < trial < trial_invocation < trial_end < command
    assert command < command_invocation


def test_bindings_command_is_no_argument_inert_and_file_first():
    block = _command_block()
    assert "if #parts ~= 1 then" in block
    assert "accepts no arguments" in block
    assert 'rawget(bindings_module, "enumerate")' in block
    assert "write_observatory_callback_bindings(" in block
    assert block.index("write_observatory_callback_bindings(") < block.index(
        'write_ack(\n            "OK OBS_CALLBACK_BINDINGS'
    )
    assert "Board:" not in block
    assert "FireWeapon" not in block
    assert "GetTargetArea(" not in block
    assert "GetTargetScore(" not in block
    assert "GetSkillEffect(" not in block
    assert "ScorePositioning(" not in block


def test_binding_startup_request_is_fixed_bounded_and_literal():
    start = SOURCE.index(
        "local function consume_observatory_callback_bindings_startup_request()"
    )
    end = SOURCE.index("-- Clean up stale files from previous session", start)
    block = SOURCE[start:end]
    assert 'file:read(128)' in block
    assert 'file:read(1)' in block
    assert 'file:read("*a")' not in block
    assert "os.remove(CALLBACK_BINDINGS_REQUEST_FILE)" in block
    assert block.index("os.remove(CALLBACK_BINDINGS_REQUEST_FILE)") < block.index(
        'execute_command("OBS_CALLBACK_BINDINGS")'
    )
    assert 'execute_command("OBS_CALLBACK_BINDINGS")' in block
    assert "execute_command(content)" not in block
    assert '"observatory-callback-bindings-request/1"' in SOURCE
