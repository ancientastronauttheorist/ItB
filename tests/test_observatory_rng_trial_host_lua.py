"""Lua 5.1 tests for the one-shot Observatory RNG trial host."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from lupa import lua51
except ImportError:
    pytest.skip(
        "exact Lua 5.1 RNG trial host harness requires lupa.lua51",
        allow_module_level=True,
    )

from tests.test_observatory_controller_lua import (
    CONTROLLER_SOURCE,
    PRELUDE,
    RUNTIME_SOURCE,
)


ROOT = Path(__file__).resolve().parents[1]
HOST_SOURCE = (
    ROOT / "src" / "bridge" / "observatory_rng_trial_host.lua"
).read_bytes().decode("utf-8")
MODLOADER_SOURCE = (
    ROOT / "src" / "bridge" / "modloader.lua"
).read_bytes().decode("utf-8")

HOST_PRELUDE = r"""
function trial_capsule()
    local packet = packet_for("random_int")
    packet.build_identity = {
        platform = "windows",
        architecture = "x86",
        build_id = "13725832",
        executable_sha256 = sha("a"),
    }
    return {
        schema_version = 2,
        kind = "observatory_rng_trial_capsule",
        capture_track = "owner_local_modified",
        arm_packet_sha256 = sha("8"),
        packet = packet,
        probe = {kind = "random_int", upper_bound = 7},
        rng_control = {
            kind = "build_keyed_seed",
            seed = 1234,
            expected_result = 1,
            helper_version = "observatory-rng-seed-helper/1",
            helper_sha256 = sha("7"),
            executable_sha256 = packet.build_identity.executable_sha256,
            build_id = packet.build_identity.build_id,
            architecture = "x86",
            rng_seed_rva = "0x00387f37",
            rng_seed_region_sha256 = sha("6"),
        },
        expected_save = {
            mission_id = "Mission_Test",
            mission_slot = "Mission2",
            turn = 2,
            master_seed = -17,
            region_id = "Archive_A",
            ai_seed = 991,
        },
    }
end

function trial_bool_capsule()
    local capsule = trial_capsule()
    local packet = packet_for("random_bool")
    packet.build_identity = capsule.packet.build_identity
    capsule.packet = packet
    capsule.probe = {kind = "random_bool", argument = 2}
    capsule.rng_control.seed = 0
    capsule.rng_control.expected_result = true
    return capsule
end

NATIVE_SEED_CALLS = 0
EXPECTED_NATIVE_SEED = 1234
NATIVE_HELPER = {
    VERSION = "observatory-rng-seed-helper/1",
    BUILD_ID = "13725832",
    EXECUTABLE_SHA256 = sha("a"),
    ARCHITECTURE = "x86",
    RNG_SEED_RVA = "0x00387f37",
    RNG_SEED_REGION_SHA256 = sha("6"),
    seed = function(value)
        assert(value == EXPECTED_NATIVE_SEED)
        NATIVE_SEED_CALLS = NATIVE_SEED_CALLS + 1
        return true
    end,
}

CURRENT_RUNTIME = runtime_state()
function live_state()
    local result = {}
    for key, value in pairs(CURRENT_RUNTIME) do result[key] = value end
    return result
end

function make_host(condition, raw_writer, result_writer)
    return RNG_HOST.new({
        condition = condition,
        activation_nonce = string.rep("f", 32),
        capsule_sha256 = sha("9"),
        capsule = trial_capsule(),
        controller_module = BOUND,
        rng_seed_helper = NATIVE_HELPER,
        hook_holder = _G,
        live_state_provider = live_state,
        raw_writer = raw_writer,
        result_writer = result_writer,
    })
end


function make_bool_host(condition, raw_writer, result_writer)
    return RNG_HOST.new({
        condition = condition,
        activation_nonce = string.rep("f", 32),
        capsule_sha256 = sha("9"),
        capsule = trial_bool_capsule(),
        controller_module = BOUND,
        rng_seed_helper = NATIVE_HELPER,
        hook_holder = _G,
        live_state_provider = live_state,
        raw_writer = raw_writer,
        result_writer = result_writer,
    })
end
"""


@pytest.fixture
def lua():
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    runtime_module = runtime.execute(RUNTIME_SOURCE)
    controller_module = runtime.execute(CONTROLLER_SOURCE)
    runtime.globals().BOUND = controller_module.bind_runtime(runtime_module)
    runtime.globals().RNG_HOST = runtime.execute(HOST_SOURCE)
    runtime.execute(PRELUDE)
    runtime.execute(HOST_PRELUDE)
    return runtime


def test_host_module_load_is_inert():
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    runtime.execute(
        r"""
        io.open = function() error("unexpected I/O") end
        os.getenv = function() error("unexpected environment lookup") end
        _G.random_int = function(bound) return bound - 1 end
        """
    )
    runtime.execute("ORIGINAL_RANDOM_INT = _G.random_int")
    before = set(runtime.globals().keys())
    module = runtime.execute(HOST_SOURCE)
    after = set(runtime.globals().keys())
    assert module.VERSION == "observatory-rng-trial-host/2"
    assert before == after
    assert runtime.eval("_G.random_int == ORIGINAL_RANDOM_INT") is True


def test_modloader_trial_integration_compiles_and_uses_fixed_file_protocol():
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    runtime.execute("function compile_only(source) return assert(loadstring(source)) end")
    assert runtime.globals().compile_only(MODLOADER_SOURCE) is not None
    assert "observatory-rng-trial-request/1" in MODLOADER_SOURCE
    assert '"^observatory%-rng%-trial%-request/1"' in MODLOADER_SOURCE
    assert 'condition=([a-z_]+)' in MODLOADER_SOURCE
    assert 'execute_command("OBS_RNG' not in MODLOADER_SOURCE
    assert "load_observatory_trial_artifact" in MODLOADER_SOURCE
    assert "load_observatory_rng_seed_helper" in MODLOADER_SOURCE
    assert "luaopen_itb_observatory_rng_seed" in MODLOADER_SOURCE
    assert "write_observatory_create_only_json" in MODLOADER_SOURCE


def test_modloader_samples_trial_before_original_base_update():
    base_update = MODLOADER_SOURCE.split(
        "Mission.BaseUpdate = function(self)", 1
    )[1].split("Mission.NextTurn = function(self)", 1)[0]
    cache_index = base_update.index("_ITB_CURRENT_MISSION = self")
    trial_index = base_update.index("step_observatory_rng_trial()")
    original_index = base_update.index("_orig_BaseUpdate(self)")
    assert cache_index < trial_index < original_index


def test_control_makes_one_probe_without_installing_or_writing_trace(lua):
    lua.execute(
        r"""
        local calls = 0
        _G.random_int = function(bound)
            calls = calls + 1
            return 1
        end
        local original = _G.random_int
        local raw = nil
        local result = nil
        local host = make_host(
            "control",
            function(snapshot) raw = snapshot; return true end,
            function(document) result = document; return true end
        )
        assert(type(rawget(host, "step")) == "function")
        assert(type(rawget(host, "status")) == "function")
        assert(type(rawget(host, "abort")) == "function")
        assert(_G.random_int == original)
        local status, err = host:step()
        assert(status == "complete" and err == nil)
        assert(calls == 1 and NATIVE_SEED_CALLS == 1)
        assert(raw == nil)
        assert(result.status == "complete")
        assert(result.schema_version == 2)
        assert(result.capture_track == "owner_local_modified")
        assert(result.condition == "control")
        assert(result.probe.result == 1)
        assert(result.rng_control.seed_applied)
        assert(result.rng_control.expected_result == 1)
        assert(not result.raw_written)
        assert(result.target_restored)
        assert(_G.random_int == original)
        local final = host:status()
        assert(final.state == "complete" and final.result_published)
        """
    )


def test_random_bool_exact_hook_records_boolean_and_restores(lua):
    lua.execute(
        r"""
        EXPECTED_NATIVE_SEED = 0
        local calls = 0
        _G.random_bool = function(argument)
            calls = calls + 1
            assert(argument == 2)
            return true
        end
        local original = _G.random_bool
        local raw = nil
        local result = nil
        local host = make_bool_host(
            "exact_hook",
            function(snapshot)
                assert(_G.random_bool == original)
                raw = snapshot
                return true
            end,
            function(document)
                assert(_G.random_bool == original)
                result = document
                return true
            end
        )
        assert(host:step() == "complete")
        assert(calls == 1 and NATIVE_SEED_CALLS == 1)
        assert(_G.random_bool == original)
        assert(raw.events[1].kind == "random_bool")
        assert(raw.events[1].payload.argument == 2)
        assert(raw.events[1].payload.result == true)
        assert(result.schema_version == 2)
        assert(result.probe.kind == "random_bool")
        assert(result.probe.argument == 2)
        assert(result.probe.result == true)
        assert(result.rng_control.expected_result == true)
        assert(result.raw_written and result.target_restored)
        local status = host:status()
        assert(status.target_restored)
        """
    )


def test_exact_hook_records_one_event_and_restores_before_writers(lua):
    lua.execute(
        r"""
        local calls = 0
        _G.random_int = function(bound)
            calls = calls + 1
            return 1
        end
        local original = _G.random_int
        local raw = nil
        local result = nil
        local restored_at_raw = false
        local restored_at_result = false
        local host = make_host(
            "exact_hook",
            function(snapshot)
                restored_at_raw = _G.random_int == original
                raw = snapshot
                return true
            end,
            function(document)
                restored_at_result = _G.random_int == original
                result = document
                return true
            end
        )
        assert(host:step() == "complete")
        assert(calls == 1)
        assert(restored_at_raw and restored_at_result)
        assert(_G.random_int == original)
        assert(raw ~= nil)
        assert(#raw.events == 1)
        assert(raw.events[1].kind == "random_int")
        assert(raw.events[1].payload.upper_bound == 7)
        assert(raw.events[1].payload.result == 1)
        assert(raw.events[1].payload.call_order == 0)
        assert(raw.summary.accepted_events == 1)
        assert(raw.summary.restore_conflicts == 0)
        assert(result.status == "complete")
        assert(result.condition == "exact_hook")
        assert(result.raw_written and result.target_restored)
        assert(result.controller_status.written)
        """
    )


def test_host_waits_without_touching_target_until_exact_enemy_phase(lua):
    lua.execute(
        r"""
        local calls = 0
        _G.random_int = function(bound) calls = calls + 1; return 1 end
        local original = _G.random_int
        local writes = 0
        local host = make_host(
            "exact_hook",
            function() writes = writes + 1; return true end,
            function() writes = writes + 1; return true end
        )
        CURRENT_RUNTIME.phase = "combat_player"
        assert(host:step() == "waiting")
        assert(calls == 0 and writes == 0 and _G.random_int == original)
        CURRENT_RUNTIME.phase = "combat_enemy"
        assert(host:step() == "complete")
        assert(calls == 1 and writes == 2 and _G.random_int == original)
        """
    )


def test_raw_writer_failure_fails_closed_after_restore(lua):
    lua.execute(
        r"""
        _G.random_int = function() return 1 end
        local original = _G.random_int
        local result = nil
        local restored_at_result = false
        local host = make_host(
            "exact_hook",
            function()
                assert(_G.random_int == original)
                return false, "raw collision"
            end,
            function(document)
                restored_at_result = _G.random_int == original
                result = document
                return true
            end
        )
        local status, err = host:step()
        assert(status == "failed")
        assert(string.find(err, "raw collision", 1, true))
        assert(restored_at_result and _G.random_int == original)
        assert(result.status == "failed")
        assert(not result.raw_written and result.target_restored)
        """
    )


def test_expired_or_wrong_identity_never_calls_probe(lua):
    lua.execute(
        r"""
        local calls = 0
        _G.random_int = function() calls = calls + 1; return 0 end
        local results = 0
        local host = make_host(
            "control",
            function() error("must not write raw") end,
            function(document)
                results = results + 1
                assert(document.status == "failed")
                return true
            end
        )
        CURRENT_RUNTIME.mission_id = "Mission_Other"
        local status, err = host:step()
        assert(status == "failed")
        assert(string.find(err, "unexpected active mission", 1, true))
        assert(calls == 0 and results == 1)
        """
    )
