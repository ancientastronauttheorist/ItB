"""Static fail-closed contract for callback-trial Mod Loader integration."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from lupa import lua51
except ImportError:
    lua51 = None


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "bridge" / "modloader.lua").read_text(encoding="utf-8")


def test_modloader_compiles_and_uses_fixed_callback_trial_protocol():
    if lua51 is None:
        pytest.skip("exact Lua 5.1 harness requires lupa.lua51")
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    runtime.execute("function compile_only(source) return assert(loadstring(source)) end")
    assert runtime.globals().compile_only(SOURCE) is not None
    assert '"observatory-callback-trial-request/1"' in SOURCE
    assert '"^observatory%-callback%-trial%-request/1"' in SOURCE
    assert 'file:read(512)' in SOURCE
    assert 'file:read(1)' in SOURCE
    assert "itb_observatory_callback_capsule_" in SOURCE
    assert "observatory_callback_trial_host.lua" in SOURCE
    assert "observatory-callback-controller/1" in SOURCE


def test_callback_host_is_advanced_only_at_reviewed_mission_boundaries():
    assert 'step_observatory_callback_trial("next_turn")' in SOURCE
    assert 'step_observatory_callback_trial("base_update_after")' in SOURCE
    next_turn = SOURCE.index("Mission.NextTurn = function(self)")
    next_end = SOURCE.index("-- BaseStart:", next_turn)
    next_block = SOURCE[next_turn:next_end]
    assert next_block.index("_orig_NextTurn(self)") < next_block.index(
        'step_observatory_callback_trial("next_turn")'
    )
    base = SOURCE.index("Mission.BaseUpdate = function(self)")
    base_end = SOURCE.index("-- NextTurn:", base)
    base_block = SOURCE[base:base_end]
    assert base_block.index("_orig_BaseUpdate(self)") < base_block.index(
        'step_observatory_callback_trial("base_update_after")'
    )
    assert base_block.index(
        'step_observatory_callback_trial("base_update_after")'
    ) < base_block.index("pcall(poll_commands)")


def test_startup_arbitration_includes_callback_trials():
    start = SOURCE.index("local _callback_startup_requested")
    startup = SOURCE[start:]
    assert "_callback_trial_startup_requested" in startup
    count = startup.index("local _observatory_startup_request_count")
    reject = startup.index("if _observatory_startup_request_count > 1")
    callback_branch = startup.index("elseif _callback_trial_startup_requested then")
    assert count < reject < callback_branch
    assert "consume_observatory_callback_trial_startup_request" in startup
    assert "OK OBS CALLBACK TRIAL ARMED" in startup


def test_callback_trial_uses_cached_save_and_create_only_outputs():
    start = SOURCE.index("local function initialize_observatory_callback_trial")
    end = SOURCE.index("local function consume_observatory_callback_trial_startup_request", start)
    block = SOURCE[start:end]
    assert "local save_data = _read_save_data()" in block
    provider = block.index("local live_state_provider = function()")
    assert "_read_save_data" not in block[provider:]
    assert "write_observatory_create_only_json(" in block
    assert "itb_observatory_callback_trial_" in block
    assert "itb_observatory_trace_" in block
